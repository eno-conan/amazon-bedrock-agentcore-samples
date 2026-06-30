"""Cognito セットアップスクリプトの単体テスト。moto でモック。"""

import json
from pathlib import Path
from unittest.mock import patch

import boto3
from moto import mock_aws

from ntt_data_agent.setup.cognito import USERNAME, setup_cognito


def _bootstrap_cognito(region: str = "ap-northeast-1") -> dict[str, str]:
    """CDK NttDataAgentCognito スタックをシミュレートしてリソースを作成。"""
    client = boto3.client("cognito-idp", region_name=region)

    pool = client.create_user_pool(PoolName="NttDataAgentPool")
    pool_id: str = pool["UserPool"]["Id"]

    client.create_resource_server(
        UserPoolId=pool_id,
        Identifier="https://api.ntt-data-agent.internal",
        Name="ntt-data-agent-api",
        Scopes=[{"ScopeName": "read", "ScopeDescription": "Read access"}],
    )
    user_client = client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName="NttDataAgentUserClient",
        GenerateSecret=False,
    )
    machine_client = client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName="NttDataAgentMachineClient",
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=["https://api.ntt-data-agent.internal/read"],
        AllowedOAuthFlowsUserPoolClient=True,
    )

    return {
        "UserPoolId": pool_id,
        "UserClientId": user_client["UserPoolClient"]["ClientId"],
        "MachineClientId": machine_client["UserPoolClient"]["ClientId"],
        "DiscoveryUrl": (
            f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
            "/.well-known/openid-configuration"
        ),
        "TokenEndpoint": (
            f"https://ntt-data-agent.auth.{region}.amazoncognito.com/oauth2/token"
        ),
    }


@mock_aws
def test_setup_cognito_creates_user(tmp_path: Path) -> None:
    """setup_cognito() が CDK プールにテストユーザーを作成することを検証。"""
    from boto3.session import Session

    outputs = _bootstrap_cognito()

    out_file = tmp_path / "cognito_config.json"
    with (
        patch("ntt_data_agent.setup.cognito.OUTPUT_FILE", out_file),
        patch("ntt_data_agent.setup.cognito._get_stack_outputs", return_value=outputs),
    ):
        config = setup_cognito(session=Session(region_name="ap-northeast-1"))

    for key in (
        "pool_id",
        "client_id",
        "discovery_url",
        "m2m_client_id",
        "m2m_client_secret",
        "m2m_token_endpoint",
        "m2m_scope",
    ):
        assert key in config

    assert config["pool_id"] in config["discovery_url"]

    saved = json.loads((tmp_path / "cognito_config.json").read_text())
    assert saved["pool_id"] == config["pool_id"]


@mock_aws
def test_setup_cognito_user_exists_in_pool(tmp_path: Path) -> None:
    """作成されたテストユーザーが User Pool に存在することを確認。"""
    from boto3.session import Session

    outputs = _bootstrap_cognito()

    out_file = tmp_path / "cognito_config.json"
    with (
        patch("ntt_data_agent.setup.cognito.OUTPUT_FILE", out_file),
        patch("ntt_data_agent.setup.cognito._get_stack_outputs", return_value=outputs),
    ):
        setup_cognito(session=Session(region_name="ap-northeast-1"))

    cognito = boto3.client("cognito-idp", region_name="ap-northeast-1")
    user = cognito.admin_get_user(UserPoolId=outputs["UserPoolId"], Username=USERNAME)
    assert user["Username"] == USERNAME


@mock_aws
def test_setup_cognito_idempotent(tmp_path: Path) -> None:
    """ユーザーが既存でも例外を起こさず正常完了することを確認。"""
    from boto3.session import Session

    outputs = _bootstrap_cognito()

    # 事前にユーザーを作成
    boto3.client("cognito-idp", region_name="ap-northeast-1").admin_create_user(
        UserPoolId=outputs["UserPoolId"],
        Username=USERNAME,
        TemporaryPassword="TempPass123!",
        MessageAction="SUPPRESS",
    )

    out_file = tmp_path / "cognito_config.json"
    with (
        patch("ntt_data_agent.setup.cognito.OUTPUT_FILE", out_file),
        patch("ntt_data_agent.setup.cognito._get_stack_outputs", return_value=outputs),
    ):
        config = setup_cognito(session=Session(region_name="ap-northeast-1"))

    assert config["pool_id"] == outputs["UserPoolId"]
