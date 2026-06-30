"""StorageStack — S3 Output Bucket + Secrets Manager。

分析結果の保存先 S3 バケットと、OAuth 認証情報を格納する
Secrets Manager シークレットを管理する。
"""

from typing import Any

import aws_cdk as cdk
from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as sm
from constructs import Construct


class StorageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- S3 Output Bucket ----
        self.output_bucket = s3.Bucket(
            self,
            "OutputBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=False,
        )

        # ---- Secrets Manager ----
        # モックAPI の OAuth 認証情報（本番では実際の値を格納）
        self.mock_api_secret = sm.Secret(
            self,
            "MockApiSecret",
            description="モックAPI OAuth 認証情報",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template='{"client_id": "mock-client-id"}',
                generate_string_key="client_secret",
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---- Outputs ----
        cdk.CfnOutput(
            self,
            "OutputBucketName",
            value=self.output_bucket.bucket_name,
            export_name="NttDataAgentOutputBucket",
            description="エージェント分析結果の保存先 S3 バケット名",
        )
        cdk.CfnOutput(
            self,
            "MockApiSecretArn",
            value=self.mock_api_secret.secret_arn,
            export_name="NttDataAgentMockApiSecretArn",
            description="モックAPI OAuth 認証情報 Secrets Manager ARN",
        )
