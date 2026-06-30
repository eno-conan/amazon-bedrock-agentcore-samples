"""Cognito テストユーザー作成スクリプト。

CDK (NttDataAgentCognito スタック) でデプロイ済みの Cognito User Pool に
テストユーザーを追加し、設定を cognito_config.json に出力する。
"""

import json
from pathlib import Path

import boto3
from boto3.session import Session

STACK_NAME = "NttDataAgentCognito"
USERNAME = "testuser"
PASSWORD = "AgentCoreTest1!"  # pragma: allowlist secret
RESOURCE_SERVER_ID = "https://api.ntt-data-agent.internal"
OUTPUT_FILE = Path(__file__).parent.parent.parent.parent.parent / "cognito_config.json"


def _get_stack_outputs(cf_client: object, stack_name: str) -> dict[str, str]:
    resp = cf_client.describe_stacks(StackName=stack_name)  # type: ignore[union-attr]
    outputs = resp["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def setup_cognito(session: Session | None = None) -> dict:
    """CDK デプロイ済みプールにテストユーザーを追加して設定を返す。"""
    if session is None:
        session = Session()
    region = session.region_name or "ap-northeast-1"
    cognito = boto3.client("cognito-idp", region_name=region)
    cf = boto3.client("cloudformation", region_name=region)

    print(f"Reading CloudFormation outputs from '{STACK_NAME}'...")
    outputs = _get_stack_outputs(cf, STACK_NAME)

    pool_id: str = outputs["UserPoolId"]
    user_client_id: str = outputs["UserClientId"]
    discovery_url: str = outputs["DiscoveryUrl"]
    token_endpoint: str = outputs["TokenEndpoint"]
    machine_client_id: str = outputs["MachineClientId"]
    print(f"  Pool ID: {pool_id}")

    resp = cognito.describe_user_pool_client(
        UserPoolId=pool_id,
        ClientId=machine_client_id,
    )
    machine_client_secret: str = resp["UserPoolClient"]["ClientSecret"]

    print(f"Creating test user '{USERNAME}'...")
    try:
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=USERNAME,
            TemporaryPassword="TempPass123!",  # pragma: allowlist secret
            MessageAction="SUPPRESS",
        )
        cognito.admin_set_user_password(
            UserPoolId=pool_id,
            Username=USERNAME,
            Password=PASSWORD,
            Permanent=True,
        )
        print(f"  Created user '{USERNAME}'")
    except cognito.exceptions.UsernameExistsException:
        print(f"  User '{USERNAME}' already exists, skipping.")

    config = {
        "pool_id": pool_id,
        "client_id": user_client_id,
        "discovery_url": discovery_url,
        "region": region,
        "username": USERNAME,
        "m2m_client_id": machine_client_id,
        "m2m_client_secret": machine_client_secret,
        "m2m_token_endpoint": token_endpoint,
        "m2m_scope": f"{RESOURCE_SERVER_ID}/read",
    }

    OUTPUT_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"\nCognito setup complete! Config saved to: {OUTPUT_FILE}")
    print(f"  discovery_url : {discovery_url}")
    print(f"  user_client_id: {user_client_id}")

    return config


if __name__ == "__main__":
    setup_cognito()
