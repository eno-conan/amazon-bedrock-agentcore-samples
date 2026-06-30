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
    "C004": {
        "id": "C004",
        "name": "デルタ建設株式会社",
        "industry": "建設",
        "annual_revenue": 800_000_000,
        "contact_email": "info@delta-const.example.com",
        "region": "名古屋",
    },
    "C005": {
        "id": "C005",
        "name": "イプシロンフィナンシャル株式会社",
        "industry": "金融",
        "annual_revenue": 2_500_000_000,
        "contact_email": "contact@epsilon-fin.example.com",
        "region": "東京",
    },
    "C006": {
        "id": "C006",
        "name": "ゼータ物流株式会社",
        "industry": "物流",
        "annual_revenue": 650_000_000,
        "contact_email": "info@zeta-logi.example.com",
        "region": "横浜",
    },
    "C007": {
        "id": "C007",
        "name": "エータ医療機器株式会社",
        "industry": "医療",
        "annual_revenue": 420_000_000,
        "contact_email": "sales@eta-medical.example.com",
        "region": "大阪",
    },
    "C008": {
        "id": "C008",
        "name": "シータエネルギー合同会社",
        "industry": "エネルギー",
        "annual_revenue": 980_000_000,
        "contact_email": "info@theta-energy.example.com",
        "region": "札幌",
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
    "O004": {
        "id": "O004",
        "customer_id": "C004",
        "title": "施工管理システム導入",
        "stage": "ヒアリング",
        "amount": 35_000_000,
        "close_date": "2026-10-31",
        "probability": 30,
    },
    "O005": {
        "id": "O005",
        "customer_id": "C005",
        "title": "リスク管理プラットフォーム刷新",
        "stage": "提案",
        "amount": 200_000_000,
        "close_date": "2026-11-30",
        "probability": 55,
    },
    "O006": {
        "id": "O006",
        "customer_id": "C006",
        "title": "配送ルート最適化 AI 導入",
        "stage": "交渉",
        "amount": 60_000_000,
        "close_date": "2026-08-31",
        "probability": 75,
    },
    "O007": {
        "id": "O007",
        "customer_id": "C001",
        "title": "IoT センサー監視基盤",
        "stage": "受注",
        "amount": 55_000_000,
        "close_date": "2026-07-15",
        "probability": 100,
    },
    "O008": {
        "id": "O008",
        "customer_id": "C007",
        "title": "電子カルテ連携システム",
        "stage": "ヒアリング",
        "amount": 90_000_000,
        "close_date": "2027-03-31",
        "probability": 25,
    },
    "O009": {
        "id": "O009",
        "customer_id": "C008",
        "title": "再生可能エネルギー管理ダッシュボード",
        "stage": "提案",
        "amount": 75_000_000,
        "close_date": "2026-12-15",
        "probability": 50,
    },
    "O010": {
        "id": "O010",
        "customer_id": "C005",
        "title": "顧客向けモバイルバンキング刷新",
        "stage": "失注",
        "amount": 150_000_000,
        "close_date": "2026-06-30",
        "probability": 0,
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
        raise HTTPException(
            status_code=404, detail=f"Customer {customer_id!r} not found"
        )
    return customer


@app.get("/opportunities")
def list_opportunities(
    customer_id: str | None = None, stage: str | None = None
) -> list[dict]:
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
        raise HTTPException(
            status_code=404, detail=f"Opportunity {opportunity_id!r} not found"
        )
    return opp


# Lambda エントリポイント
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
