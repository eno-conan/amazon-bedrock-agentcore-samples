"""Cognito User Pool セットアップスクリプト。

AgentCore Identity が参照する Cognito User Pool / Domain / App Client を作成し、
設定を cognito_config.json に出力する。

参考: amazon-bedrock-agentcore-samples/01-features/05-authenticate-and-authorize/
      03-m2m-3lo/setup_cognito.py
"""

import json
import re
from pathlib import Path

import boto3
from boto3.session import Session

POOL_NAME = "NttDataAgentPool"
USERNAME = "testuser"
PASSWORD = "AgentCoreTest1!"  # pragma: allowlist secret
TEMP_PASSWORD = "TempPass123!"  # pragma: allowlist secret
RESOURCE_SERVER_ID = "https://api.ntt-data-agent.internal"
OUTPUT_FILE = Path(__file__).parent.parent.parent.parent.parent / "cognito_config.json"


def setup_cognito(session: Session | None = None) -> dict:
    """Cognito リソースを作成して設定辞書を返す。"""
    if session is None:
        session = Session()
    region = session.region_name or "ap-northeast-1"
    cognito = boto3.client("cognito-idp", region_name=region)

    print(f"Creating Cognito User Pool '{POOL_NAME}'...")
    pool = cognito.create_user_pool(
        PoolName=POOL_NAME,
        Policies={"PasswordPolicy": {"MinimumLength": 8}},
    )
    pool_id: str = pool["UserPool"]["Id"]
    print(f"  Pool ID: {pool_id}")

    domain_prefix = "ntt-data-agent-" + re.sub(r"[^a-z0-9]", "-", pool_id.lower())[:14]
    print(f"Creating Cognito domain '{domain_prefix}'...")
    cognito.create_user_pool_domain(Domain=domain_prefix, UserPoolId=pool_id)
    token_endpoint = (
        f"https://{domain_prefix}.auth.{region}.amazoncognito.com/oauth2/token"
    )

    print("Creating resource server (M2M scopes)...")
    cognito.create_resource_server(
        UserPoolId=pool_id,
        Identifier=RESOURCE_SERVER_ID,
        Name="NttDataAgentAPI",
        Scopes=[{"ScopeName": "read", "ScopeDescription": "Read access"}],
    )
    m2m_scope = f"{RESOURCE_SERVER_ID}/read"

    print("Creating user app client...")
    user_client = cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=f"{POOL_NAME}UserClient",
        GenerateSecret=False,
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )
    user_client_id: str = user_client["UserPoolClient"]["ClientId"]
    print(f"  User Client ID: {user_client_id}")

    print("Creating machine client (client credentials)...")
    machine_client = cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=f"{POOL_NAME}MachineClient",
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=[m2m_scope],
        AllowedOAuthFlowsUserPoolClient=True,
    )
    machine_client_id: str = machine_client["UserPoolClient"]["ClientId"]
    machine_client_secret: str = machine_client["UserPoolClient"]["ClientSecret"]

    print(f"Creating test user '{USERNAME}'...")
    cognito.admin_create_user(
        UserPoolId=pool_id,
        Username=USERNAME,
        TemporaryPassword=TEMP_PASSWORD,
        MessageAction="SUPPRESS",
    )
    cognito.admin_set_user_password(
        UserPoolId=pool_id,
        Username=USERNAME,
        Password=PASSWORD,
        Permanent=True,
    )

    discovery_url = (
        f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
    )

    config = {
        "pool_id": pool_id,
        "client_id": user_client_id,
        "discovery_url": discovery_url,
        "region": region,
        "username": USERNAME,
        "m2m_client_id": machine_client_id,
        "m2m_client_secret": machine_client_secret,
        "m2m_token_endpoint": token_endpoint,
        "m2m_scope": m2m_scope,
    }

    OUTPUT_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"\nCognito setup complete! Config saved to: {OUTPUT_FILE}")
    print(f"  discovery_url : {discovery_url}")
    print(f"  user_client_id: {user_client_id}")

    return config


if __name__ == "__main__":
    setup_cognito()
