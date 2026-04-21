"""Tests for api/cost_analysis.py — GET /api/quotes/{id}/cost-analysis.

Covers:
- 401 without JWT
- 403 without a permitted role
- 403 for wrong organization
- 404 for missing / soft-deleted quote
- 200 + has_calculation=false when no calc rows
- 200 + aggregated totals + derived metrics for a 2-item quote
- markup_pct zero-division safety when purchase is 0

The Supabase client is mocked at ``api.cost_analysis.get_supabase`` so these
tests are pure unit tests (no DB, no network).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.cost_analysis import get_cost_analysis  # noqa: E402


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_request(api_user_id: str | None = "user-1"):
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(api_user=SimpleNamespace(id=api_user_id))
    return req


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


def _mock_supabase(
    *,
    role_slugs: list[str],
    org_id: str = "org-1",
    quote: dict | None = None,
    calc_rows: list[dict] | None = None,
    variables: dict | None = None,
):
    """Build a chainable Supabase mock for the cost-analysis handler.

    Handled tables:
      - organization_members  → returns [{organization_id: org_id}]
      - user_roles            → returns [{roles: {slug: s}} for s in role_slugs]
      - quotes                → returns [quote] if quote is not None else []
      - quote_calculation_results → returns calc_rows (or [])
      - quote_calculation_variables → returns [{variables: variables}] or []
    """
    sb = MagicMock()

    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "organization_members":
            tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"organization_id": org_id}
            ]
        elif name == "user_roles":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {"roles": {"slug": s}} for s in role_slugs
            ]
        elif name == "quotes":
            data = [quote] if quote else []
            # The handler chains .select(...).eq(...).is_(...).limit(...).execute()
            tbl.select.return_value.eq.return_value.is_.return_value.limit.return_value.execute.return_value.data = data
        elif name == "quote_calculation_results":
            rows = calc_rows if calc_rows is not None else []
            tbl.select.return_value.eq.return_value.execute.return_value.data = rows
        elif name == "quote_calculation_variables":
            rows = [{"variables": variables}] if variables is not None else []
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = rows
        return tbl

    sb.table.side_effect = table_side_effect
    return sb


def _quote_row(
    *,
    quote_id: str = "q-1",
    org_id: str = "org-1",
    customer_name: str = "ACME",
    currency: str = "USD",
    workflow_status: str = "approved",
    title: str = "Test Quote",
    idn_quote: str = "Q-1",
):
    return {
        "id": quote_id,
        "organization_id": org_id,
        "idn_quote": idn_quote,
        "title": title,
        "currency": currency,
        "workflow_status": workflow_status,
        "customers": {"name": customer_name},
    }


# ----------------------------------------------------------------------------
# Auth tests
# ----------------------------------------------------------------------------


class TestAuth:
    @patch("api.cost_analysis.get_supabase")
    def test_no_jwt_returns_401(self, mock_get_sb):
        req = _make_request(api_user_id=None)
        resp = _run(get_cost_analysis(req, "q-1"))
        assert resp.status_code == 401
        assert _body(resp)["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.parametrize(
        "role",
        ["sales", "procurement", "logistics", "customs", "head_of_sales"],
    )
    @patch("api.cost_analysis.get_supabase")
    def test_disallowed_role_returns_403(self, mock_get_sb, role):
        mock_get_sb.return_value = _mock_supabase(role_slugs=[role])
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"

    @patch("api.cost_analysis.get_supabase")
    def test_user_with_no_org_returns_403(self, mock_get_sb):
        sb = MagicMock()

        def table_side_effect(name: str):
            tbl = MagicMock()
            if name == "organization_members":
                tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))
        assert resp.status_code == 403

    @patch("api.cost_analysis.get_supabase")
    def test_quote_in_other_org_returns_403(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["finance"],
            quote=_quote_row(org_id="org-OTHER"),
        )
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"


# ----------------------------------------------------------------------------
# Not-found
# ----------------------------------------------------------------------------


class TestNotFound:
    @patch("api.cost_analysis.get_supabase")
    def test_missing_quote_returns_404(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["finance"], quote=None
        )
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-ghost"))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"


# ----------------------------------------------------------------------------
# has_calculation = false
# ----------------------------------------------------------------------------


class TestNoCalculation:
    @patch("api.cost_analysis.get_supabase")
    def test_no_calc_rows_returns_has_calculation_false(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["finance"],
            quote=_quote_row(),
            calc_rows=[],
        )
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))

        assert resp.status_code == 200
        payload = _body(resp)
        assert payload["success"] is True
        assert payload["data"]["has_calculation"] is False
        # Totals are zeroed
        assert payload["data"]["totals"]["revenue_no_vat"] == 0
        assert payload["data"]["totals"]["purchase"] == 0
        # Quote payload is still populated
        assert payload["data"]["quote"]["id"] == "q-1"
        assert payload["data"]["quote"]["customer_name"] == "ACME"


# ----------------------------------------------------------------------------
# Happy path + aggregation
# ----------------------------------------------------------------------------


class TestAggregation:
    @patch("api.cost_analysis.get_supabase")
    def test_two_items_sum_phase_results(self, mock_get_sb):
        """Handler SUMs phase_results across every calc row."""
        calc_rows = [
            {
                "quote_item_id": "i-1",
                "phase_results": {
                    "AK16": 1000.0,
                    "AL16": 1200.0,
                    "S16": 500.0,
                    "V16": 100.0,
                    "Y16": 50.0,
                    "Z16": 10.0,
                    "AG16": 20.0,
                    "AH16": 15.0,
                    "AI16": 25.0,
                    "BB16": 30.0,
                },
            },
            {
                "quote_item_id": "i-2",
                "phase_results": {
                    "AK16": 500.0,
                    "AL16": 600.0,
                    "S16": 250.0,
                    "V16": 50.0,
                    "Y16": 25.0,
                    "Z16": 5.0,
                    "AG16": 10.0,
                    "AH16": 5.0,
                    "AI16": 15.0,
                    "BB16": 20.0,
                },
            },
        ]
        variables = {
            "logistics_supplier_hub": 10.0,
            "logistics_hub_customs": 20.0,
            "logistics_customs_client": 30.0,
            "brokerage_hub": 40.0,
            "brokerage_customs": 50.0,
            "warehousing_at_customs": 60.0,
            "customs_documentation": 70.0,
            "brokerage_extra": 80.0,
            "rate_insurance": 90.0,
        }
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["finance"],
            quote=_quote_row(),
            calc_rows=calc_rows,
            variables=variables,
        )
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))

        assert resp.status_code == 200
        data = _body(resp)["data"]
        assert data["has_calculation"] is True

        # Aggregated SUMs
        totals = data["totals"]
        assert totals["revenue_no_vat"] == 1500.0
        assert totals["revenue_with_vat"] == 1800.0
        assert totals["purchase"] == 750.0
        assert totals["logistics"] == 150.0
        assert totals["customs"] == 75.0
        assert totals["excise"] == 15.0
        assert totals["dm_fee"] == 30.0
        assert totals["forex"] == 20.0
        assert totals["financial_agent_fee"] == 40.0
        assert totals["financing"] == 50.0

        # Logistics breakdown mapped 1:1 from variables
        breakdown = data["logistics_breakdown"]
        assert breakdown["W2_supplier_hub"] == 10.0
        assert breakdown["W3_hub_customs"] == 20.0
        assert breakdown["W4_customs_client"] == 30.0
        assert breakdown["W5_brokerage_hub"] == 40.0
        assert breakdown["W6_brokerage_customs"] == 50.0
        assert breakdown["W7_warehousing"] == 60.0
        assert breakdown["W8_documentation"] == 70.0
        assert breakdown["W9_extra"] == 80.0
        assert breakdown["W10_insurance"] == 90.0

        # Derived P&L metrics
        derived = data["derived"]
        # direct_costs = 750 + 150 + 75 + 15 = 990
        assert derived["direct_costs"] == 990.0
        # gross_profit = 1500 - 990 = 510
        assert derived["gross_profit"] == 510.0
        # financial_expenses = 30 + 20 + 40 + 50 = 140
        assert derived["financial_expenses"] == 140.0
        # net_profit = 510 - 140 = 370
        assert derived["net_profit"] == 370.0
        # markup_pct = (1500 / 750 - 1) * 100 = 100
        assert derived["markup_pct"] == pytest.approx(100.0)
        # sale_purchase_ratio = 1500 / 750 = 2.0
        assert derived["sale_purchase_ratio"] == pytest.approx(2.0)

    @patch("api.cost_analysis.get_supabase")
    def test_missing_variables_defaults_to_zero_breakdown(self, mock_get_sb):
        """No quote_calculation_variables row → W2..W10 all zero."""
        calc_rows = [
            {"quote_item_id": "i-1", "phase_results": {"AK16": 100.0, "S16": 50.0}}
        ]
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["finance"],
            quote=_quote_row(),
            calc_rows=calc_rows,
            variables=None,
        )
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))

        assert resp.status_code == 200
        data = _body(resp)["data"]
        breakdown = data["logistics_breakdown"]
        for key in (
            "W2_supplier_hub",
            "W3_hub_customs",
            "W4_customs_client",
            "W5_brokerage_hub",
            "W6_brokerage_customs",
            "W7_warehousing",
            "W8_documentation",
            "W9_extra",
            "W10_insurance",
        ):
            assert breakdown[key] == 0


# ----------------------------------------------------------------------------
# Zero-division safety
# ----------------------------------------------------------------------------


class TestMarkupZeroDivision:
    @patch("api.cost_analysis.get_supabase")
    def test_zero_purchase_returns_zero_markup(self, mock_get_sb):
        """markup_pct and sale_purchase_ratio must be 0 when purchase is 0."""
        calc_rows = [
            {
                "quote_item_id": "i-1",
                "phase_results": {
                    "AK16": 1000.0,
                    "S16": 0.0,  # <— zero purchase
                },
            }
        ]
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["finance"],
            quote=_quote_row(),
            calc_rows=calc_rows,
            variables=None,
        )
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))

        assert resp.status_code == 200
        derived = _body(resp)["data"]["derived"]
        assert derived["markup_pct"] == 0.0
        assert derived["sale_purchase_ratio"] == 0.0


# ----------------------------------------------------------------------------
# Role permutations (happy path)
# ----------------------------------------------------------------------------


class TestAllowedRoles:
    @pytest.mark.parametrize(
        "role", ["finance", "top_manager", "admin", "quote_controller"]
    )
    @patch("api.cost_analysis.get_supabase")
    def test_each_allowed_role_can_access(self, mock_get_sb, role):
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=[role],
            quote=_quote_row(),
            calc_rows=[],
        )
        req = _make_request()
        resp = _run(get_cost_analysis(req, "q-1"))
        assert resp.status_code == 200
