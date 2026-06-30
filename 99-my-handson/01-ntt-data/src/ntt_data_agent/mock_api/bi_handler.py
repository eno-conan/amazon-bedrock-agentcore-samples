"""モックBI API — Tableau / QuickSight 代替。

FastAPI で売上・顧客分析レポートを提供し、Mangum で Lambda ハンドラーに変換する。
AgentCore Gateway から呼び出される想定。
"""

from fastapi import FastAPI, HTTPException
from mangum import Mangum

app = FastAPI(title="Mock BI API", version="1.0.0")

# ---- サンプル分析データ ----

_SALES_REPORT: dict[str, dict] = {
    "2026-Q1": {
        "period": "2026-Q1",
        "total_revenue": 250_000_000,
        "deal_count": 12,
        "avg_deal_size": 20_833_333,
        "top_industry": "IT",
        "growth_rate_pct": 15.3,
    },
    "2026-Q2": {
        "period": "2026-Q2",
        "total_revenue": 310_000_000,
        "deal_count": 15,
        "avg_deal_size": 20_666_667,
        "top_industry": "製造業",
        "growth_rate_pct": 24.0,
    },
}

_CUSTOMER_ANALYSIS: dict[str, dict] = {
    "C001": {
        "customer_id": "C001",
        "lifetime_value": 320_000_000,
        "churn_risk": "低",
        "engagement_score": 88,
        "recommended_action": "アップセル提案",
    },
    "C002": {
        "customer_id": "C002",
        "lifetime_value": 980_000_000,
        "churn_risk": "中",
        "engagement_score": 71,
        "recommended_action": "定期レビューミーティングの設定",
    },
    "C003": {
        "customer_id": "C003",
        "lifetime_value": 180_000_000,
        "churn_risk": "低",
        "engagement_score": 95,
        "recommended_action": "クロスセル提案（クラウド移行）",
    },
}

_PIPELINE_SUMMARY: dict = {
    "total_open_amount": 245_000_000,
    "weighted_amount": 176_000_000,
    "deals_by_stage": {
        "提案": {"count": 3, "amount": 80_000_000},
        "交渉": {"count": 5, "amount": 120_000_000},
        "受注": {"count": 2, "amount": 45_000_000},
    },
    "forecast_next_quarter": 200_000_000,
}


# ---- エンドポイント ----


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/reports/sales")
def list_sales_reports() -> list[dict]:
    """四半期売上レポート一覧を返す。"""
    return list(_SALES_REPORT.values())


@app.get("/reports/sales/{period}")
def get_sales_report(period: str) -> dict:
    """指定期間の売上レポートを返す（例: 2026-Q1）。"""
    report = _SALES_REPORT.get(period)
    if not report:
        raise HTTPException(
            status_code=404, detail=f"Sales report for {period!r} not found"
        )
    return report


@app.get("/reports/customers/{customer_id}")
def get_customer_analysis(customer_id: str) -> dict:
    """指定顧客の分析レポート（LTV・チャーンリスク等）を返す。"""
    analysis = _CUSTOMER_ANALYSIS.get(customer_id)
    if not analysis:
        raise HTTPException(
            status_code=404, detail=f"Customer analysis for {customer_id!r} not found"
        )
    return analysis


@app.get("/reports/pipeline")
def get_pipeline_summary() -> dict:
    """商談パイプラインのサマリーを返す。"""
    return _PIPELINE_SUMMARY


# Lambda エントリポイント
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
