# デプロイ手順

本ドキュメントでは、`infra/` の AWS CDK スタックを AWS 環境にデプロイし、
エージェントを起動するまでの手順を説明します。

## 前提条件

以下がインストール・設定済みであること。

| ツール | 確認コマンド | 備考 |
|--------|------------|------|
| AWS CLI | `aws sts get-caller-identity` | `aws configure` で認証情報設定済み |
| Node.js | `node --version` | v18 以上推奨 |
| CDK CLI | `cdk --version` | `npm install -g aws-cdk` でインストール |
| uv | `uv --version` | Python パッケージ管理 |

---

## Step 0: 依存関係のインストール

```bash
task setup
# または
uv sync
```

---

## Step 1: CDK Bootstrap（初回のみ）

CDK が AWS アカウントにデプロイ用リソース（S3バケット等）を作成する。
**同一アカウント・リージョンに対して初回 1 回だけ実行すればよい。**

```bash
cdk bootstrap
```

成功すると `CDKToolkit` スタックが AWS に作成される。

---

## Step 2: テンプレート検証（任意）

AWS にアクセスせず、CloudFormation テンプレートを生成して構文を確認する。

```bash
task infra:synth
```

`Successfully synthesized to cdk.out` と表示されれば問題なし。

---

## Step 3: 差分確認（任意）

既存のデプロイ済みスタックと現在のコードの差分を確認する。

```bash
task infra:diff
```

初回デプロイ時は全リソースが新規扱いになる。

---

## Step 4: デプロイ

```bash
task infra:deploy
```

内部で `cdk deploy --all --require-approval never` を実行する。
デプロイされるスタックと順序：

1. **NttDataAgentStorage** — S3 Output Bucket + Secrets Manager
2. **NttDataAgentCognito** — Cognito User Pool + Domain + App Clients
3. **NttDataAgentMockApi** — Lambda (CRM/BI/Interceptor) + API Gateway × 2

完了まで **5〜10 分** 程度かかる。

### Cognito Domain のコンフリクトについて

Cognito の Domain Prefix はグローバルに一意である必要がある。
デフォルト値 `ntt-data-agent` が他のアカウントで使用済みの場合はエラーになる。

その場合は `cdk.json` の `cognito_domain_prefix` を変更するか、デプロイ時に `-c` で指定する：

```bash
cdk deploy --all -c cognito_domain_prefix=my-unique-prefix-2026
```

---

## Step 5: 出力値の確認と .env への転記

デプロイ完了後、各スタックの **Outputs** に接続情報が表示される。

```
NttDataAgentCognito
  DiscoveryUrl   = https://cognito-idp.ap-northeast-1.amazonaws.com/<pool-id>/.well-known/openid-configuration
  UserPoolId     = ap-northeast-1_XXXXXXX
  UserClientId   = xxxxxxxxxxxxxxxxxxxxxxxxxx
  TokenEndpoint  = https://ntt-data-agent.auth.ap-northeast-1.amazoncognito.com/oauth2/token

NttDataAgentMockApi
  CrmApiUrl          = https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/v1/
  BiApiUrl           = https://yyyyyyyyyy.execute-api.ap-northeast-1.amazonaws.com/v1/
  InterceptorFunctionArn = arn:aws:lambda:ap-northeast-1:...

NttDataAgentStorage
  OutputBucketName   = nttdataagentstorage-outputbucket-xxxx
```

`.env.example` を `.env` にコピーし、上記の値を転記する：

```bash
cp .env.example .env
```

```dotenv
AWS_DEFAULT_REGION=ap-northeast-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6-20250514-v1:0

COGNITO_USER_POOL_ID=ap-northeast-1_XXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx

MOCK_CRM_API_URL=https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/v1
MOCK_BI_API_URL=https://yyyyyyyyyy.execute-api.ap-northeast-1.amazonaws.com/v1

OUTPUT_BUCKET=nttdataagentstorage-outputbucket-xxxx
```

> **注意:** `MOCK_CRM_API_URL` / `MOCK_BI_API_URL` は末尾のスラッシュを除いた形で設定する。

---

## Step 6: Cognito テストユーザーの作成

CDK は Cognito ユーザーを作成しないため、boto3 スクリプトで別途作成する。
このスクリプトは Step 4 でデプロイした `NttDataAgentCognito` スタックの
CloudFormation Outputs を読み取り、既存プールにテストユーザーを追加する。

```bash
task setup:cognito
```

成功すると `cognito_config.json` が出力される（セキュリティのため `.gitignore` 対象）。

> **注意:** `task infra:deploy` の完了後に実行すること。スタックが存在しない場合はエラーになる。

---

## Step 7: AgentCore Gateway の設定

AgentCore は CDK での管理が難しいため、boto3 スクリプトで設定する。
**Step 6 (`task setup:cognito`) の完了後に実行すること。**

```bash
task setup:agentcore
```

スクリプトが以下を自動で実行する:

| # | 処理 | 詳細 |
|---|------|------|
| 1 | IAM ロール作成 | `NttDataAgentGatewayRole`（サービス主体: `bedrock-agentcore.amazonaws.com`） |
| 2 | Gateway 作成 | `ntt-data-agent-gateway`（プロトコル: MCP / 認可: CUSTOM_JWT） |
| 3 | CRM ターゲット登録 | `NttDataAgentMockApi` の `CrmApiUrl` を指す API Gateway ターゲット |
| 4 | BI ターゲット登録 | `NttDataAgentMockApi` の `BiApiUrl` を指す API Gateway ターゲット |

**JWT 認可の設定:**

- **Discovery URL**: `cognito_config.json` の `discovery_url`（Cognito OIDC エンドポイント）
- **Allowed clients**: `cognito_config.json` の `client_id`（UserClient ID）

**Lambda Interceptor:**

- `NttDataAgentMockApi` スタックの `InterceptorFunctionArn` が Gateway の `interceptorConfigurations` に自動登録される
- リクエスト・レスポンスの両方向で intercept（`interceptionPoints: [REQUEST, RESPONSE]`）

成功すると `agentcore_config.json` が出力される（セキュリティのため `.gitignore` 対象）:

```json
{
  "gateway_id": "...",
  "gateway_url": "https://xxxx.gateway.bedrock-agentcore.ap-northeast-1.amazonaws.com",
  "crm_target_id": "...",
  "bi_target_id": "...",
  "gateway_role_arn": "arn:aws:iam::123456789012:role/NttDataAgentGatewayRole"
}
```

> **注意:** Gateway の READY 待ちを含むため、完了まで **2〜5 分** かかる。

---

## Step 8: エージェントのローカル実行

`.env` の設定が完了したら、エージェントをローカルで起動する。

```bash
task agent:dev
```

---

## リソースの削除

検証が終わったら以下のコマンドで全リソースを削除できる。

```bash
task infra:destroy
```

内部で `cdk destroy --all --force` を実行する。S3 バケットは `autoDeleteObjects: true` で設定済みのため、中身があっても削除される。

> **注意:** Cognito テストユーザーは `task infra:destroy` では削除されない。
> Cognito User Pool 自体は CDK で管理しているため、`task infra:destroy` で削除される。

---

## 再デプロイ

しばらく経ってから再度デプロイしたい場合は Step 4 から実行する。
（`cdk bootstrap` は再実行不要）

```bash
task infra:deploy
```
