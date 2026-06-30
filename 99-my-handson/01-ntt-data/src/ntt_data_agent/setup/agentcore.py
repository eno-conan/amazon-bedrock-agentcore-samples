"""AgentCore Gateway セットアップスクリプト。

CDK (NttDataAgentMockApi / NttDataAgentCognito) デプロイ後・
task setup:cognito 実行後に実行する。

処理内容:
  1. IAM Gateway ロール作成（bedrock-agentcore.amazonaws.com 信頼）
  2. AgentCore Gateway 作成（CUSTOM_JWT + Lambda Interceptor）
  3. CRM / BI API Gateway ターゲット登録

前提:
  - cognito_config.json（task setup:cognito で生成）
  - NttDataAgentMockApi スタックがデプロイ済み

出力:
  agentcore_config.json（gateway_id / gateway_url など）
"""

import json
import re
import time
from pathlib import Path

import boto3
from boto3.session import Session

GATEWAY_NAME = "ntt-data-agent-gateway"
GATEWAY_ROLE_NAME = "NttDataAgentGatewayRole"
MOCK_API_STACK = "NttDataAgentMockApi"

_ROOT = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_FILE = _ROOT / "agentcore_config.json"
COGNITO_CONFIG_FILE = _ROOT / "cognito_config.json"


def _get_stack_outputs(cf_client: object, stack_name: str) -> dict[str, str]:
    resp = cf_client.describe_stacks(StackName=stack_name)  # type: ignore[union-attr]
    outputs = resp["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def _parse_api_id(url: str) -> tuple[str, str]:
    """API Gateway URL から REST API ID とステージ名を抽出。"""
    m = re.match(r"https://([^.]+)\.execute-api\.[^.]+\.amazonaws\.com/([^/]+)/", url)
    if not m:
        raise ValueError(f"API Gateway URL のパースに失敗: {url!r}")
    return m.group(1), m.group(2)


def _create_gateway_role(iam: object, account_id: str, region: str) -> str:
    """Gateway 用 IAM ロールを作成（既存の場合はスキップ）。"""
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                        )
                    },
                },
            }
        ],
    }
    try:
        resp = iam.create_role(  # type: ignore[union-attr]
            RoleName=GATEWAY_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
        )
        print(f"  Created role: {GATEWAY_ROLE_NAME}")
        time.sleep(10)  # IAM 伝播待ち
    except iam.exceptions.EntityAlreadyExistsException:  # type: ignore[union-attr]
        resp = iam.get_role(RoleName=GATEWAY_ROLE_NAME)  # type: ignore[union-attr]
        print(f"  Role exists: {GATEWAY_ROLE_NAME}")
    return resp["Role"]["Arn"]


def _attach_gateway_policy(
    iam: object,
    crm_api_id: str,
    bi_api_id: str,
    interceptor_arn: str,
    region: str,
    account_id: str,
) -> None:
    """Gateway ロールに execute-api:Invoke と lambda:InvokeFunction を付与。"""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "execute-api:Invoke",
                "Resource": [
                    f"arn:aws:execute-api:{region}:{account_id}:{crm_api_id}/*",
                    f"arn:aws:execute-api:{region}:{account_id}:{bi_api_id}/*",
                ],
            },
            {
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": interceptor_arn,
            },
        ],
    }
    iam.put_role_policy(  # type: ignore[union-attr]
        RoleName=GATEWAY_ROLE_NAME,
        PolicyName="NttDataAgentGatewayPolicy",
        PolicyDocument=json.dumps(policy),
    )
    print("  Policy attached.")


def _wait_gateway(control: object, gateway_id: str, timeout: int = 180) -> None:
    for _ in range(timeout // 10):
        status = control.get_gateway(  # type: ignore[union-attr]
            gatewayIdentifier=gateway_id
        )["status"]
        if status == "READY":
            return
        if status == "FAILED":
            raise RuntimeError(f"Gateway creation FAILED: {gateway_id}")
        time.sleep(10)
    raise TimeoutError(f"Gateway が {timeout}s 以内に READY にならなかった")


def _wait_target(
    control: object, gateway_id: str, target_id: str, timeout: int = 180
) -> None:
    for _ in range(timeout // 10):
        status = control.get_gateway_target(  # type: ignore[union-attr]
            gatewayIdentifier=gateway_id, targetId=target_id
        )["status"]
        if status == "READY":
            return
        if status == "FAILED":
            raise RuntimeError(f"Target FAILED: {target_id}")
        time.sleep(10)
    raise TimeoutError(f"Target {target_id} が {timeout}s 以内に READY にならなかった")


def _ensure_target(
    control: object,
    gateway_id: str,
    name: str,
    target_cfg: dict,
    cred_cfg: list,
) -> str:
    """ターゲットを作成し targetId を返す。同名が既存なら削除して再作成。"""
    items = control.list_gateway_targets(  # type: ignore[union-attr]
        gatewayIdentifier=gateway_id
    )["items"]
    existing = next((t for t in items if t["name"] == name), None)
    if existing:
        tid = existing["targetId"]
        print(f"  Existing target '{name}' ({tid}) found, deleting...")
        control.delete_gateway_target(  # type: ignore[union-attr]
            gatewayIdentifier=gateway_id, targetId=tid
        )
        for _ in range(18):
            try:
                control.get_gateway_target(  # type: ignore[union-attr]
                    gatewayIdentifier=gateway_id, targetId=tid
                )
                time.sleep(10)
            except Exception:
                break
    resp = control.create_gateway_target(  # type: ignore[union-attr]
        name=name,
        gatewayIdentifier=gateway_id,
        targetConfiguration=target_cfg,
        credentialProviderConfigurations=cred_cfg,
    )
    return resp["targetId"]  # type: ignore[no-any-return]


def setup_agentcore(session: Session | None = None) -> dict:
    """AgentCore Gateway を作成して設定を返す。"""
    if session is None:
        session = Session()
    region = session.region_name or "ap-northeast-1"

    if not COGNITO_CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"{COGNITO_CONFIG_FILE} が見つかりません。"
            "先に task setup:cognito を実行してください。"
        )
    cognito_cfg = json.loads(COGNITO_CONFIG_FILE.read_text())
    discovery_url: str = cognito_cfg["discovery_url"]
    allowed_client: str = cognito_cfg["client_id"]

    cf = boto3.client("cloudformation", region_name=region)
    iam = boto3.client("iam")
    control = boto3.client("bedrock-agentcore-control", region_name=region)
    account_id: str = boto3.client("sts").get_caller_identity()["Account"]

    print(f"Reading CloudFormation outputs from '{MOCK_API_STACK}'...")
    mock_out = _get_stack_outputs(cf, MOCK_API_STACK)
    crm_api_url: str = mock_out["CrmApiUrl"]
    bi_api_url: str = mock_out["BiApiUrl"]
    interceptor_arn: str = mock_out["InterceptorFunctionArn"]

    crm_api_id, crm_stage = _parse_api_id(crm_api_url)
    bi_api_id, bi_stage = _parse_api_id(bi_api_url)
    print(f"  CRM API ID : {crm_api_id}  (stage: {crm_stage})")
    print(f"  BI  API ID : {bi_api_id}  (stage: {bi_stage})")
    print(f"  Interceptor: {interceptor_arn}")

    print("\nCreating Gateway IAM role...")
    role_arn = _create_gateway_role(iam, account_id, region)
    _attach_gateway_policy(
        iam, crm_api_id, bi_api_id, interceptor_arn, region, account_id
    )

    print(f"\nCreating AgentCore Gateway '{GATEWAY_NAME}'...")
    try:
        gw = control.create_gateway(
            name=GATEWAY_NAME,
            roleArn=role_arn,
            protocolType="MCP",
            protocolConfiguration={
                "mcp": {
                    "supportedVersions": ["2025-03-26"],
                    "searchType": "SEMANTIC",
                }
            },
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "allowedClients": [allowed_client],
                    "discoveryUrl": discovery_url,
                }
            },
            interceptorConfigurations=[
                {
                    "interceptor": {"lambda": {"arn": interceptor_arn}},
                    "interceptionPoints": ["REQUEST", "RESPONSE"],
                    "inputConfiguration": {"passRequestHeaders": True},
                }
            ],
        )
        gateway_id = gw["gatewayId"]
        gateway_url = gw["gatewayUrl"]
        print(f"  Gateway ID : {gateway_id}")
        print(f"  Gateway URL: {gateway_url}")
        print("  Waiting for READY...")
        _wait_gateway(control, gateway_id)
        print("  Gateway is READY.")
    except control.exceptions.ConflictException:
        items = control.list_gateways()["items"]
        existing = next(g for g in items if g["name"] == GATEWAY_NAME)
        gateway_id = existing["gatewayId"]
        detail = control.get_gateway(gatewayIdentifier=gateway_id)
        gateway_url = detail["gatewayUrl"]
        print(f"  Gateway exists: {gateway_id}")
        print(f"  Gateway URL   : {gateway_url}")

    _cred = [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]

    print("\nCreating CRM Gateway target...")
    crm_target_id: str = _ensure_target(
        control,
        gateway_id,
        "ntt-data-crm",
        {
            "mcp": {
                "apiGateway": {
                    "restApiId": crm_api_id,
                    "stage": crm_stage,
                    "apiGatewayToolConfiguration": {
                        "toolFilters": [
                            {"filterPath": "/customers", "methods": ["GET"]},
                            {
                                "filterPath": "/customers/{customer_id}",
                                "methods": ["GET"],
                            },
                            {"filterPath": "/opportunities", "methods": ["GET"]},
                            {
                                "filterPath": "/opportunities/{opportunity_id}",
                                "methods": ["GET"],
                            },
                        ]
                    },
                }
            }
        },
        _cred,
    )
    _wait_target(control, gateway_id, crm_target_id)
    print(f"  CRM target READY: {crm_target_id}")

    print("\nCreating BI Gateway target...")
    bi_target_id: str = _ensure_target(
        control,
        gateway_id,
        "ntt-data-bi",
        {
            "mcp": {
                "apiGateway": {
                    "restApiId": bi_api_id,
                    "stage": bi_stage,
                    "apiGatewayToolConfiguration": {
                        "toolFilters": [
                            {"filterPath": "/reports/sales", "methods": ["GET"]},
                            {
                                "filterPath": "/reports/sales/{period}",
                                "methods": ["GET"],
                            },
                            {
                                "filterPath": "/reports/customers/{customer_id}",
                                "methods": ["GET"],
                            },
                            {"filterPath": "/reports/pipeline", "methods": ["GET"]},
                        ]
                    },
                }
            }
        },
        _cred,
    )
    _wait_target(control, gateway_id, bi_target_id)
    print(f"  BI target READY: {bi_target_id}")

    config = {
        "gateway_id": gateway_id,
        "gateway_url": gateway_url,
        "crm_target_id": crm_target_id,
        "bi_target_id": bi_target_id,
        "gateway_role_arn": role_arn,
    }
    OUTPUT_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"\nAgentCore setup complete! Config saved to: {OUTPUT_FILE}")
    print(f"  gateway_url: {gateway_url}")
    return config


if __name__ == "__main__":
    setup_agentcore()
