"""NTTデータエージェント — AgentCore Runtime エントリポイント。

Strands Agents で構築した AI エージェントを BedrockAgentCoreApp にデプロイする。
エージェントはユーザーの自然言語クエリを受け取り、CRM / BI ツールを使って
顧客・商談・売上データを分析して回答する。

Usage（ローカル実行）:
    uv run python -m ntt_data_agent.agent.main

Usage（AgentCore へデプロイ）:
    agentcore deploy
"""

import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from opentelemetry import trace
from strands import Agent
from strands.models import BedrockModel

from ntt_data_agent.tools.bi import (
    get_customer_analysis,
    get_pipeline_summary,
    get_sales_report,
)
from ntt_data_agent.tools.crm import (
    get_customer_detail,
    get_customers,
    get_opportunities,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "jp.anthropic.claude-sonnet-4-6")
_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1")

SYSTEM_PROMPT = """あなたは営業支援 AI エージェントです。
CRM と BI ツールを使って、顧客データや売上データを分析し、
営業担当者の質問に日本語で回答します。

利用可能なツール:
- get_customers: 顧客一覧を取得（地域でフィルタ可能）
- get_customer_detail: 特定の顧客詳細を取得
- get_opportunities: 商談一覧を取得（顧客ID・ステージでフィルタ可能）
- get_sales_report: 四半期売上レポートを取得
- get_customer_analysis: 顧客の LTV・チャーンリスク・推奨アクションを取得
- get_pipeline_summary: 商談パイプライン全体のサマリーを取得

常にツールで取得した最新データに基づいて回答してください。"""

_agent: Agent | None = None


def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        model = BedrockModel(
            model_id=_MODEL_ID,
            region_name=_REGION,
        )
        _agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[
                get_customers,
                get_customer_detail,
                get_opportunities,
                get_sales_report,
                get_customer_analysis,
                get_pipeline_summary,
            ],
        )
    return _agent


@app.entrypoint
async def invoke(payload: dict, context: object):
    """AgentCore から呼び出されるエントリポイント。"""
    tracer = trace.get_tracer("ntt_data_agent", "1.0.0")
    user_query: str = payload.get("prompt", "")
    session_id: str = payload.get("session_id", "unknown")

    log.info("invoke: session=%s query=%.80s", session_id, user_query)

    with tracer.start_as_current_span("agent_invoke") as span:
        span.set_attribute("session.id", session_id)
        span.set_attribute("query.preview", user_query[:200])

        agent = _get_agent()
        stream = agent.stream_async(user_query)
        async for event in stream:
            if "data" in event and isinstance(event["data"], str):
                yield event["data"]

        span.set_attribute("status", "ok")


if __name__ == "__main__":
    app.run()
