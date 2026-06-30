"""MockApiStack — Lambda + API Gateway。

モック CRM / BI API（Salesforce / Tableau 代替）と
AgentCore Gateway Interceptor を Lambda としてデプロイする。

Lambda Layer に fastapi / mangum をバンドルし、
CRM / BI の各 Function と共有する。

バンドリング戦略:
  1. ローカルバンドラー（Docker 不要）:
     pip install --platform manylinux2014_x86_64 --only-binary=:all:
     で Linux 互換バイナリをダウンロード
  2. Docker フォールバック:
     ローカル失敗時に CDK の Lambda bundling イメージを使用
"""

import os
import subprocess
from typing import Any

import aws_cdk as cdk
import jsii
from aws_cdk import BundlingOptions, Duration, ILocalBundling, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from constructs import Construct


@jsii.implements(ILocalBundling)
class _LayerLocalBundler:
    """Lambda Layer（fastapi + mangum）を Docker なしでビルドするバンドラー。

    pip の --platform / --only-binary オプションで Linux 互換バイナリを取得するため、
    Windows 環境でも Lambda 互換パッケージを生成できる。
    ローカルビルドに失敗した場合は CDK が Docker にフォールバックする。
    """

    _PACKAGES = ["fastapi", "mangum", "pydantic", "starlette", "anyio"]

    def try_bundle(self, output_dir: str, options: BundlingOptions) -> bool:
        python_dir = os.path.join(output_dir, "python")
        try:
            subprocess.run(
                [
                    "pip",
                    "install",
                    *self._PACKAGES,
                    "-t",
                    python_dir,
                    "--platform",
                    "manylinux2014_x86_64",
                    "--python-version",
                    "3.12",
                    "--only-binary=:all:",
                    "--quiet",
                ],
                check=True,
            )
            return True
        except Exception as exc:
            print(f"[LocalBundler] Layer build failed, will try Docker: {exc}")
            return False


class MockApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        output_bucket: s3.Bucket,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- Lambda Layer: FastAPI + Mangum ----
        api_layer = lambda_.LayerVersion(
            self,
            "FastApiLayer",
            code=lambda_.Code.from_asset(
                ".",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        (
                            "pip install fastapi mangum pydantic starlette anyio "
                            "-t /asset-output/python --quiet"
                        ),
                    ],
                    local=_LayerLocalBundler(),  # type: ignore[arg-type]
                ),
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="FastAPI + Mangum (CRM/BI Lambda 用)",
            removal_policy=RemovalPolicy.DESTROY,
        )

        common = {
            "runtime": lambda_.Runtime.PYTHON_3_12,
            "timeout": Duration.seconds(30),
            "environment": {
                "OUTPUT_BUCKET": output_bucket.bucket_name,
            },
        }

        # ---- CRM Lambda ----
        self.crm_fn: lambda_.IFunction = lambda_.Function(
            self,
            "CrmFunction",
            code=lambda_.Code.from_asset("src/ntt_data_agent/mock_api"),
            handler="crm_handler.handler",
            layers=[api_layer],
            description="モック CRM API (Salesforce 代替)",
            **common,  # type: ignore[arg-type]
        )

        # ---- BI Lambda ----
        self.bi_fn: lambda_.IFunction = lambda_.Function(
            self,
            "BiFunction",
            code=lambda_.Code.from_asset("src/ntt_data_agent/mock_api"),
            handler="bi_handler.handler",
            layers=[api_layer],
            description="モック BI API (Tableau 代替)",
            **common,  # type: ignore[arg-type]
        )

        # ---- Gateway Interceptor Lambda（依存関係なし）----
        self.interceptor_fn = lambda_.Function(
            self,
            "InterceptorFunction",
            code=lambda_.Code.from_asset("src/ntt_data_agent/interceptor"),
            handler="handler.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(10),
            description="AgentCore Gateway Interceptor",
        )

        # S3 書き込み権限を CRM/BI Lambda に付与
        output_bucket.grant_write(self.crm_fn)
        output_bucket.grant_write(self.bi_fn)

        cors = apigw.CorsOptions(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=apigw.Cors.ALL_METHODS,
        )
        # AgentCore が OpenAPI スペックを解釈できるよう
        # 200/500 レスポンスと operationId を定義する
        _method_resp = [
            apigw.MethodResponse(status_code="200"),
            apigw.MethodResponse(status_code="500"),
        ]

        def _get(
            resource: apigw.Resource,
            integration: apigw.LambdaIntegration,
            operation_name: str,
        ) -> None:
            resource.add_method(
                "GET",
                integration,
                method_responses=_method_resp,
                operation_name=operation_name,
            )

        # ---- API Gateway: CRM ----
        # LambdaRestApi は /{proxy+} のみ生成するため
        # AgentCore が OpenAPI スペックを解釈できない。
        # RestApi + 明示的リソースを使い、Lambda はプロキシ統合のままにする。
        crm_api = apigw.RestApi(
            self,
            "CrmApi",
            rest_api_name="NttDataAgent-CRM",
            description="モック CRM API エンドポイント",
            deploy_options=apigw.StageOptions(stage_name="v1"),
            default_cors_preflight_options=cors,
        )
        crm_int = apigw.LambdaIntegration(self.crm_fn, proxy=True)
        _get(crm_api.root.add_resource("health"), crm_int, "GetCrmHealth")
        crm_customers = crm_api.root.add_resource("customers")
        _get(crm_customers, crm_int, "ListCustomers")
        _get(crm_customers.add_resource("{customer_id}"), crm_int, "GetCustomer")
        crm_opps = crm_api.root.add_resource("opportunities")
        _get(crm_opps, crm_int, "ListOpportunities")
        _get(crm_opps.add_resource("{opportunity_id}"), crm_int, "GetOpportunity")

        # ---- API Gateway: BI ----
        bi_api = apigw.RestApi(
            self,
            "BiApi",
            rest_api_name="NttDataAgent-BI",
            description="モック BI API エンドポイント",
            deploy_options=apigw.StageOptions(stage_name="v1"),
            default_cors_preflight_options=cors,
        )
        bi_int = apigw.LambdaIntegration(self.bi_fn, proxy=True)
        _get(bi_api.root.add_resource("health"), bi_int, "GetBiHealth")
        bi_reports = bi_api.root.add_resource("reports")
        bi_sales = bi_reports.add_resource("sales")
        _get(bi_sales, bi_int, "GetSalesReport")
        _get(bi_sales.add_resource("{period}"), bi_int, "GetSalesReportByPeriod")
        _get(
            bi_reports.add_resource("customers").add_resource("{customer_id}"),
            bi_int,
            "GetCustomerReport",
        )
        _get(bi_reports.add_resource("pipeline"), bi_int, "GetPipelineReport")

        # ---- Outputs ----
        cdk.CfnOutput(
            self,
            "CrmApiUrl",
            value=crm_api.url,
            export_name="NttDataAgentCrmApiUrl",
            description="MOCK_CRM_API_URL に設定する値（末尾スラッシュなし）",
        )
        cdk.CfnOutput(
            self,
            "BiApiUrl",
            value=bi_api.url,
            export_name="NttDataAgentBiApiUrl",
            description="MOCK_BI_API_URL に設定する値（末尾スラッシュなし）",
        )
        cdk.CfnOutput(
            self,
            "InterceptorFunctionArn",
            value=self.interceptor_fn.function_arn,
            export_name="NttDataAgentInterceptorArn",
            description="AgentCore Gateway Interceptor として登録する Lambda ARN",
        )
