"""モックCRM API エンドポイントの単体テスト。"""

from fastapi.testclient import TestClient

from ntt_data_agent.mock_api.crm_handler import app

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_customers_all() -> None:
    res = client.get("/customers")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3
    ids = {c["id"] for c in data}
    assert ids == {"C001", "C002", "C003"}


def test_list_customers_filter_by_region() -> None:
    res = client.get("/customers", params={"region": "東京"})
    assert res.status_code == 200
    data = res.json()
    assert all(c["region"] == "東京" for c in data)
    assert len(data) == 1


def test_get_customer_found() -> None:
    res = client.get("/customers/C001")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "C001"
    assert data["name"] == "株式会社アルファ"


def test_get_customer_not_found() -> None:
    res = client.get("/customers/ZZZZ")
    assert res.status_code == 404


def test_list_opportunities_all() -> None:
    res = client.get("/opportunities")
    assert res.status_code == 200
    assert len(res.json()) == 3


def test_list_opportunities_filter_by_customer() -> None:
    res = client.get("/opportunities", params={"customer_id": "C001"})
    assert res.status_code == 200
    data = res.json()
    assert all(o["customer_id"] == "C001" for o in data)


def test_list_opportunities_filter_by_stage() -> None:
    res = client.get("/opportunities", params={"stage": "受注"})
    assert res.status_code == 200
    data = res.json()
    assert all(o["stage"] == "受注" for o in data)


def test_get_opportunity_found() -> None:
    res = client.get("/opportunities/O002")
    assert res.status_code == 200
    assert res.json()["id"] == "O002"


def test_get_opportunity_not_found() -> None:
    res = client.get("/opportunities/XXXX")
    assert res.status_code == 404
