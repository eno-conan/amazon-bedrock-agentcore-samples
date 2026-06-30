# ハンズオン
https://aws.amazon.com/jp/blogs/psa/agentcore-usecase-for-multi-saas-ai-agents-by-nttdata/

## 2. システムアーキテクチャ

本章では、Amazon Bedrock AgentCore を中心とした、外部サービス（自前モックAPI、Amazon QuickSight）とセキュアに連携する AI エージェント基盤のアーキテクチャを紹介します。

本構成は、以下の設計要件を満たすことを目的としました。

- 外部サービスを横断する自然言語ベースのデータ分析
- ユーザー単位の認証・認可の厳密な制御
- サービスごとに異なる認証方式への対応
- 実行ログのトレーサビリティ確保
- スケーラブルかつ拡張可能な構成

これらを実現するため、AgentCore の各コンポーネント（Runtime・Identity・Gateway・Observability）を組み合わせたアーキテクチャを採用しました。

なお本構成は個人開発での検証を目的としており、実運用を想定した Salesforce / Tableau / Okta の代わりに、それぞれ以下を採用しています。

| 役割 | 本来想定 | 本構成での代替 | 採用理由 |
|---|---|---|---|
| 認証基盤 | Okta | **Amazon Cognito** | AWS 内で完結し、OAuth 2.0 / OIDC 標準に準拠。Identity 連携の実装パターンを Okta と同様の形で検証可能 |
| SaaS①（CRM相当） | Salesforce | **自前モックAPI（API Gateway + Lambda）** | OAuth 2.0 フローおよび Gateway Interceptors の挙動を完全にコントロールしながら検証可能 |
| SaaS②（BI相当） | Tableau | **Amazon QuickSight** | AWS 内で完結し、Bedrock AgentCore との連携を低コストで検証可能 |

### AgentCore Runtime

AI エージェント（Strands Agents で構築）をデプロイし、Python 実行環境上で分析処理を実行します。AgentCore Runtime はエージェントごとに独立した実行環境を提供するため、セキュアな実行分離が可能です。

### AgentCore Identity

ユーザー認証およびトークン管理を担います。AgentCore Identity により、AI エージェントは常に「認証済みユーザーコンテキスト」で動作します。

- Amazon Cognito を用いたユーザー認証をサポートする OAuth 2.0 プロバイダ設定
- 外部 API 呼び出し時のトークン管理

### AgentCore Gateway

外部サービスとの接続を管理します。AgentCore Gateway を利用することで、エージェントと外部 API の結合度を下げ、拡張性を確保しています。

- MCP による API 統合
- OAuth 2.0 フロー管理
- Gateway Interceptors によるリクエスト変換
- 自前モックAPI（API Gateway + Lambda）に対する OAuth 2.0 認証フローの検証

### AgentCore Observability

AI エージェントの実行トレースおよびツール実行ログを収集します。標準機能に加え、カスタムトレースを追加することでユーザー単位の監査ログ取得を実現しています。

### 処理フロー

本アーキテクチャでは、以下の流れで処理が実行されます。

1. ユーザーが自然言語でエージェントを実行
2. AgentCore Identity が Amazon Cognito を通じてユーザー認証
3. 認証済みコンテキストを保持したまま AgentCore Runtime 上で処理開始
4. 必要に応じて AgentCore Gateway 経由で自前モックAPI または Amazon QuickSight を呼び出し
5. AgentCore Gateway が OAuth 2.0 認証およびリクエスト制御を実施
6. Python 実行環境でデータ加工・分析
7. 分析結果を Amazon S3 に保存
8. AgentCore Observability により全処理のトレースを記録