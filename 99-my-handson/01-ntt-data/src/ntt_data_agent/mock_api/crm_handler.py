"""モックCRM API — Salesforce 代替。

FastAPI で顧客・商談データを提供し、Mangum で Lambda ハンドラーに変換する。
AgentCore Gateway から OAuth 2.0 認証後に呼び出される想定。
"""

from fastapi import FastAPI, HTTPException
from mangum import Mangum

app = FastAPI(title="Mock CRM API", version="1.0.0")

# ---- サンプルデータ ----

_CUSTOMERS: dict[str, dict] = {
    "C001": {
        "id": "C001",
        "name": "株式会社アルファ",
        "industry": "製造業",
        "annual_revenue": 500_000_000,
        "contact_email": "info@alpha.example.com",
        "region": "東京",
    },
    "C002": {
        "id": "C002",
        "name": "ベータ商事株式会社",
        "industry": "商社",
        "annual_revenue": 1_200_000_000,
        "contact_email": "contact@beta.example.com",
        "region": "大阪",
    },
    "C003": {
        "id": "C003",
        "name": "ガンマテクノロジー合同会社",
        "industry": "IT",
        "annual_revenue": 300_000_000,
        "contact_email": "hello@gamma.example.com",
        "region": "福岡",
    },
}

_OPPORTUNITIES: dict[str, dict] = {
    "O001": {
        "id": "O001",
        "customer_id": "C001",
        "title": "基幹システム刷新プロジェクト",
        "stage": "提案",
        "amount": 80_000_000,
        "close_date": "2026-09-30",
        "probability": 60,
    },
    "O002": {
        "id": "O002",
        "customer_id": "C002",
        "title": "クラウド移行支援",
        "stage": "交渉",
        "amount": 45_000_000,
        "close_date": "2026-07-31",
        "probability": 80,
    },
    "O003": {
        "id": "O003",
        "customer_id": "C003",
        "title": "AI 分析基盤構築",
        "stage": "受注",
        "amount": 120_000_000,
        "close_date": "2026-12-31",
        "probability": 95,
    },
}


# ---- エンドポイント ----


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/customers")
def list_customers(region: str | None = None) -> list[dict]:
    """顧客一覧を返す。region でフィルタ可能。"""
    customers = list(_CUSTOMERS.values())
    if region:
        customers = [c for c in customers if c["region"] == region]
    return customers


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str) -> dict:
    """指定IDの顧客詳細を返す。"""
    customer = _CUSTOMERS.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id!r} not found")
    return customer


@app.get("/opportunities")
def list_opportunities(customer_id: str | None = None, stage: str | None = None) -> list[dict]:
    """商談一覧を返す。customer_id や stage でフィルタ可能。"""
    opps = list(_OPPORTUNITIES.values())
    if customer_id:
        opps = [o for o in opps if o["customer_id"] == customer_id]
    if stage:
        opps = [o for o in opps if o["stage"] == stage]
    return opps


@app.get("/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: str) -> dict:
    """指定IDの商談詳細を返す。"""
    opp = _OPPORTUNITIES.get(opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id!r} not found")
    return opp


# Lambda エントリポイント
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
