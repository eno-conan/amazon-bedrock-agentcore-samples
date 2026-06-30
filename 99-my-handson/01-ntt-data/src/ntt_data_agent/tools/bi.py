"""BI ツール — モックBI API を呼び出す Strands エージェントツール。

本番では AgentCore Gateway 経由で QuickSight に接続する。
開発時は MOCK_BI_API_URL 環境変数でモックAPIを指定する。
"""

import os

import httpx
from opentelemetry import trace
from strands import tool

_tracer = trace.get_tracer("ntt_data_agent.tools.bi", "1.0.0")

_BASE_URL = os.getenv("MOCK_BI_API_URL", "http://localhost:8002")


def _client() -> httpx.Client:
    return httpx.Client(base_url=_BASE_URL, timeout=10.0)


@tool
def get_sales_report(period: str = "") -> str:
    """売上レポートを取得する。

    Args:
        period: 対象期間（例: 2026-Q1、2026-Q2）。
                空文字の場合は全期間のレポート一覧を返す。

    Returns:
        売上レポートの JSON 文字列。
    """
    with _tracer.start_as_current_span("bi.get_sales_report") as span:
        span.set_attribute("bi.period", period or "all")
        with _client() as client:
            if period:
                res = client.get(f"/reports/sales/{period}")
                if res.status_code == 404:
                    span.set_attribute("bi.not_found", True)
                    return f"期間 {period!r} の売上レポートは存在しません。"
            else:
                res = client.get("/reports/sales")
            res.raise_for_status()
        span.set_attribute("bi.response.status", res.status_code)
    return res.text


@tool
def get_customer_analysis(customer_id: str) -> str:
    """指定顧客の分析レポートを取得する（LTV・チャーンリスク・推奨アクション）。

    Args:
        customer_id: 顧客ID（例: C001）。

    Returns:
        顧客分析レポートの JSON 文字列。顧客が存在しない場合はエラーメッセージ。
    """
    with _tracer.start_as_current_span("bi.get_customer_analysis") as span:
        span.set_attribute("bi.customer_id", customer_id)
        with _client() as client:
            res = client.get(f"/reports/customers/{customer_id}")
            if res.status_code == 404:
                span.set_attribute("bi.not_found", True)
                return f"顧客 {customer_id!r} の分析データは存在しません。"
            res.raise_for_status()
        span.set_attribute("bi.response.status", res.status_code)
    return res.text


@tool
def get_pipeline_summary() -> str:
    """商談パイプライン全体のサマリーを取得する。

    Returns:
        パイプラインサマリーの JSON 文字列（総額・ステージ別件数・翌四半期予測）。
    """
    with _tracer.start_as_current_span("bi.get_pipeline_summary") as span:
        with _client() as client:
            res = client.get("/reports/pipeline")
            res.raise_for_status()
        span.set_attribute("bi.response.status", res.status_code)
    return res.text
