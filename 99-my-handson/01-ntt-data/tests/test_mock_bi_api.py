"""モックBI API エンドポイントの単体テスト。"""

from fastapi.testclient import TestClient

from ntt_data_agent.mock_api.bi_handler import app

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_sales_reports() -> None:
    res = client.get("/reports/sales")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    periods = {r["period"] for r in data}
    assert "2026-Q1" in periods
    assert "2026-Q2" in periods


def test_get_sales_report_found() -> None:
    res = client.get("/reports/sales/2026-Q1")
    assert res.status_code == 200
    data = res.json()
    assert data["period"] == "2026-Q1"
    assert data["total_revenue"] == 250_000_000
    assert "growth_rate_pct" in data


def test_get_sales_report_not_found() -> None:
    res = client.get("/reports/sales/2099-Q9")
    assert res.status_code == 404


def test_get_customer_analysis_found() -> None:
    res = client.get("/reports/customers/C002")
    assert res.status_code == 200
    data = res.json()
    assert data["customer_id"] == "C002"
    assert "churn_risk" in data
    assert "recommended_action" in data


def test_get_customer_analysis_not_found() -> None:
    res = client.get("/reports/customers/ZZZZ")
    assert res.status_code == 404


def test_get_pipeline_summary() -> None:
    res = client.get("/reports/pipeline")
    assert res.status_code == 200
    data = res.json()
    assert "total_open_amount" in data
    assert "weighted_amount" in data
    assert "deals_by_stage" in data
    assert "forecast_next_quarter" in data
