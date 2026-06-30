"""CognitoStack — Cognito User Pool + Domain + App Clients。

AgentCore Identity に登録する認証基盤（Okta 代替）。
- ユーザー認証用クライアント（USER_PASSWORD_AUTH）
- M2M 用クライアント（client_credentials）
の 2 種類を用意する。

Cognito Domain prefix は cdk.json の context key "cognito_domain_prefix" で変更可能。
グローバルに一意な必要があるため、デフォルト値でコンフリクトする場合は変更すること。
"""

from typing import Any

import aws_cdk as cdk
from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from constructs import Construct

_RESOURCE_SERVER_ID = "https://api.ntt-data-agent.internal"


class CognitoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domain_prefix: str = (
            self.node.try_get_context("cognito_domain_prefix") or "ntt-data-agent"
        )

        # ---- User Pool ----
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="NttDataAgentPool",
            self_sign_up_enabled=False,
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=False,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---- Cognito Domain（OAuth トークンエンドポイント用）----
        self.domain = self.user_pool.add_domain(
            "UserPoolDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_prefix,
            ),
        )

        # ---- Resource Server（M2M スコープ定義）----
        resource_server = self.user_pool.add_resource_server(
            "ResourceServer",
            identifier=_RESOURCE_SERVER_ID,
            user_pool_resource_server_name="ntt-data-agent-api",
            scopes=[
                cognito.ResourceServerScope(
                    scope_name="read",
                    scope_description="Read access",
                )
            ],
        )

        # ---- ユーザー認証用 App Client ----
        self.user_client = self.user_pool.add_client(
            "UserClient",
            user_pool_client_name="NttDataAgentUserClient",
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
            generate_secret=False,
        )

        # ---- M2M 用 App Client（client_credentials）----
        self.machine_client = self.user_pool.add_client(
            "MachineClient",
            user_pool_client_name="NttDataAgentMachineClient",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(
                        resource_server,
                        cognito.ResourceServerScope(
                            scope_name="read",
                            scope_description="Read access",
                        ),
                    )
                ],
            ),
        )

        # ---- Outputs ----
        region = Stack.of(self).region
        discovery_url = (
            f"https://cognito-idp.{region}.amazonaws.com/"
            f"{self.user_pool.user_pool_id}/.well-known/openid-configuration"
        )
        token_endpoint = self.domain.base_url() + "/oauth2/token"

        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            export_name="NttDataAgentUserPoolId",
        )
        cdk.CfnOutput(
            self,
            "UserClientId",
            value=self.user_client.user_pool_client_id,
            export_name="NttDataAgentUserClientId",
        )
        cdk.CfnOutput(
            self,
            "DiscoveryUrl",
            value=discovery_url,
            export_name="NttDataAgentDiscoveryUrl",
            description="AgentCore Identity に登録する OIDC Discovery URL",
        )
        cdk.CfnOutput(
            self,
            "TokenEndpoint",
            value=token_endpoint,
            export_name="NttDataAgentTokenEndpoint",
            description="M2M client_credentials 用トークンエンドポイント",
        )
        cdk.CfnOutput(
            self,
            "MachineClientId",
            value=self.machine_client.user_pool_client_id,
            export_name="NttDataAgentMachineClientId",
        )
