"""エージェントツール（CRM / BI）の単体テスト。httpx をモックして検証。"""

import json
from unittest.mock import MagicMock, patch

import httpx


def _make_response(status_code: int, data: object) -> httpx.Response:
    req = httpx.Request("GET", "http://localhost/")
    return httpx.Response(status_code=status_code, json=data, request=req)


# ---- CRM ツール ----


class TestGetCustomers:
    def test_returns_all_customers(self) -> None:
        customers = [{"id": "C001", "name": "株式会社アルファ"}]
        mock_res = _make_response(200, customers)

        with patch("ntt_data_agent.tools.crm._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.crm import get_customers

            result = get_customers._tool_func(region="")

        assert json.loads(result) == customers

    def test_passes_region_param(self) -> None:
        mock_res = _make_response(200, [])

        with patch("ntt_data_agent.tools.crm._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.crm import get_customers

            get_customers._tool_func(region="東京")
            ctx.get.assert_called_with("/customers", params={"region": "東京"})


class TestGetCustomerDetail:
    def test_returns_customer(self) -> None:
        customer = {"id": "C001", "name": "株式会社アルファ"}
        mock_res = _make_response(200, customer)

        with patch("ntt_data_agent.tools.crm._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.crm import get_customer_detail

            result = get_customer_detail._tool_func(customer_id="C001")

        assert json.loads(result) == customer

    def test_not_found_returns_message(self) -> None:
        mock_res = _make_response(404, {"detail": "not found"})

        with patch("ntt_data_agent.tools.crm._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.crm import get_customer_detail

            result = get_customer_detail._tool_func(customer_id="ZZZZ")

        assert "存在しません" in result


# ---- BI ツール ----


class TestGetSalesReport:
    def test_list_all_reports(self) -> None:
        reports = [{"period": "2026-Q1", "total_revenue": 250_000_000}]
        mock_res = _make_response(200, reports)

        with patch("ntt_data_agent.tools.bi._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.bi import get_sales_report

            result = get_sales_report._tool_func(period="")

        assert json.loads(result) == reports

    def test_get_specific_period(self) -> None:
        report = {"period": "2026-Q1", "total_revenue": 250_000_000}
        mock_res = _make_response(200, report)

        with patch("ntt_data_agent.tools.bi._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.bi import get_sales_report

            result = get_sales_report._tool_func(period="2026-Q1")

        assert json.loads(result) == report

    def test_period_not_found(self) -> None:
        mock_res = _make_response(404, {})

        with patch("ntt_data_agent.tools.bi._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.bi import get_sales_report

            result = get_sales_report._tool_func(period="9999-Q9")

        assert "存在しません" in result


class TestGetPipelineSummary:
    def test_returns_summary(self) -> None:
        summary = {
            "total_open_amount": 245_000_000,
            "forecast_next_quarter": 200_000_000,
        }
        mock_res = _make_response(200, summary)

        with patch("ntt_data_agent.tools.bi._client") as mock_client_fn:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = mock_res
            mock_client_fn.return_value = ctx

            from ntt_data_agent.tools.bi import get_pipeline_summary

            result = get_pipeline_summary._tool_func()

        assert json.loads(result) == summary
