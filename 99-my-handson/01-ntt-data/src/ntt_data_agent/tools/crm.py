"""CRM ツール — モックCRM API を呼び出す Strands エージェントツール。

本番では AgentCore Gateway 経由で実際の Salesforce に接続する。
開発時は MOCK_CRM_API_URL 環境変数でモックAPIを指定する。
"""

import os

import httpx
from opentelemetry import trace
from strands import tool

_tracer = trace.get_tracer("ntt_data_agent.tools.crm", "1.0.0")

_BASE_URL = os.getenv("MOCK_CRM_API_URL", "http://localhost:8001")


def _client() -> httpx.Client:
    return httpx.Client(base_url=_BASE_URL, timeout=10.0)


@tool
def get_customers(region: str = "") -> str:
    """顧客一覧を取得する。

    Args:
        region: フィルタする地域名（例: 東京、大阪）。空文字で全件取得。

    Returns:
        顧客一覧の JSON 文字列。
    """
    with _tracer.start_as_current_span("crm.get_customers") as span:
        span.set_attribute("crm.filter.region", region or "all")
        params = {"region": region} if region else {}
        with _client() as client:
            res = client.get("/customers", params=params)
            res.raise_for_status()
        span.set_attribute("crm.response.status", res.status_code)
    return res.text


@tool
def get_customer_detail(customer_id: str) -> str:
    """指定IDの顧客詳細を取得する。

    Args:
        customer_id: 顧客ID（例: C001）。

    Returns:
        顧客詳細の JSON 文字列。顧客が存在しない場合はエラーメッセージ。
    """
    with _tracer.start_as_current_span("crm.get_customer_detail") as span:
        span.set_attribute("crm.customer_id", customer_id)
        with _client() as client:
            res = client.get(f"/customers/{customer_id}")
            if res.status_code == 404:
                span.set_attribute("crm.not_found", True)
                return f"顧客 {customer_id!r} は存在しません。"
            res.raise_for_status()
        span.set_attribute("crm.response.status", res.status_code)
    return res.text


@tool
def get_opportunities(customer_id: str = "", stage: str = "") -> str:
    """商談一覧を取得する。

    Args:
        customer_id: 顧客IDでフィルタ（例: C001）。空文字で全件。
        stage: 商談ステージでフィルタ（例: 提案、交渉、受注）。空文字で全件。

    Returns:
        商談一覧の JSON 文字列。
    """
    with _tracer.start_as_current_span("crm.get_opportunities") as span:
        span.set_attribute("crm.filter.customer_id", customer_id or "all")
        span.set_attribute("crm.filter.stage", stage or "all")
        params: dict[str, str] = {}
        if customer_id:
            params["customer_id"] = customer_id
        if stage:
            params["stage"] = stage
        with _client() as client:
            res = client.get("/opportunities", params=params)
            res.raise_for_status()
        span.set_attribute("crm.response.status", res.status_code)
    return res.text
