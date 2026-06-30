#!/usr/bin/env python3
"""CDK アプリのエントリポイント。

スタック構成:
  NttDataAgentStorage  — S3 Output Bucket + Secrets Manager
  NttDataAgentCognito  — Cognito User Pool + Domain + App Clients
  NttDataAgentMockApi  — Lambda (CRM/BI/Interceptor) + API Gateway

デプロイ:
  cdk deploy --all                     # 全スタックをデプロイ
  cdk deploy NttDataAgentStorage       # 個別デプロイ
  cdk destroy --all                    # 全リソースを削除

Cognito Domain Prefix の変更（デフォルト: ntt-data-agent）:
  cdk deploy --all -c cognito_domain_prefix=my-unique-prefix
"""

import sys
from pathlib import Path

# infra/ パッケージを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent))

import aws_cdk as cdk
from stacks.cognito_stack import CognitoStack
from stacks.mock_api_stack import MockApiStack
from stacks.storage_stack import StorageStack

app = cdk.App()

region: str = app.node.try_get_context("region") or "ap-northeast-1"
env = cdk.Environment(region=region)

storage = StorageStack(app, "NttDataAgentStorage", env=env)
cognito = CognitoStack(app, "NttDataAgentCognito", env=env)
mock_api = MockApiStack(
    app,
    "NttDataAgentMockApi",
    output_bucket=storage.output_bucket,
    env=env,
)

# デプロイ順序を明示
mock_api.add_dependency(storage)

cdk.Tags.of(app).add("Project", "NttDataAgent")
cdk.Tags.of(app).add("ManagedBy", "CDK")

app.synth()
