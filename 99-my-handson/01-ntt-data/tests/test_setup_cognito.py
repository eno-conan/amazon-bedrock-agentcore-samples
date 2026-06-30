"""Cognito セットアップスクリプトの単体テスト。moto でモック。"""

import json
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws


@mock_aws
def test_setup_cognito_creates_pool(tmp_path: Path) -> None:
    """setup_cognito() が User Pool / Domain / App Client を作成することを検証。"""
    from boto3.session import Session

    # OUTPUT_FILE をテンポラリに向ける
    with patch(
        "ntt_data_agent.setup.cognito.OUTPUT_FILE", tmp_path / "cognito_config.json"
    ):
        from ntt_data_agent.setup.cognito import setup_cognito

        session = Session(region_name="ap-northeast-1")
        config = setup_cognito(session=session)

    # 必須キーがある
    assert "pool_id" in config
    assert "client_id" in config
    assert "discovery_url" in config
    assert "m2m_client_id" in config
    assert "m2m_client_secret" in config
    assert "m2m_token_endpoint" in config
    assert "m2m_scope" in config

    # discovery_url に pool_id が含まれる
    assert config["pool_id"] in config["discovery_url"]

    # cognito_config.json が書き出されている
    output = tmp_path / "cognito_config.json"
    assert output.exists()
    saved = json.loads(output.read_text())
    assert saved["pool_id"] == config["pool_id"]


@mock_aws
def test_setup_cognito_user_pool_exists(tmp_path: Path) -> None:
    """作成された User Pool が AWS 側に存在することを確認。"""
    from boto3.session import Session

    with patch(
        "ntt_data_agent.setup.cognito.OUTPUT_FILE", tmp_path / "cognito_config.json"
    ):
        from ntt_data_agent.setup.cognito import setup_cognito

        session = Session(region_name="ap-northeast-1")
        config = setup_cognito(session=session)

    cognito = boto3.client("cognito-idp", region_name="ap-northeast-1")
    pools = cognito.list_user_pools(MaxResults=10)["UserPools"]
    pool_ids = [p["Id"] for p in pools]
    assert config["pool_id"] in pool_ids
