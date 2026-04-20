"""Tests for api/quotes.py::calculate_quote — Phase 6B-6a extraction.

Covers (per task 6B-6a spec):
- Happy path: JWT-authed POST returns 200 + expected envelope keys
- 401 when no JWT and no session
- 403 when JWT user has no organization membership
- 404 when quote does not exist (or belongs to a different org)
- 400 when composition returns no items
- 400 when items exist but none have prices
- 500 when calculation engine raises

The Supabase client is mocked at ``api.quotes.get_supabase``, and the
composition/calc-engine/version services are patched on the ``api.quotes``
module so we exercise the handler as a pure unit (no DB, no engine math,
no network).
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.quotes import calculate_quote  # noqa: E402


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_request(
    api_user_id: str | None = "user-1",
    body: dict | None = None,
    email: str = "u@x.com",
):
    """Build a minimal Starlette-style request with JWT user + JSON body."""
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(id=api_user_id, email=email)
        )

    req.headers = {"content-type": "application/json"}

    async def _json():
        return body or {}

    req.json = _json
    # request.session raises AssertionError on Starlette when SessionMiddleware
    # is absent; mimic that so the JWT-less branch returns 401 cleanly.
    type(req).session = property(
        lambda self: (_ for _ in ()).throw(AssertionError("no session"))
    )
    return req


def _mock_supabase_for_calc(
    *,
    org_id: str | None = "org-1",
    quote: dict | None = None,
):
    """Build a chainable Supabase mock for the calculate handler.

    Covers only the reads/writes up to the composition_service boundary.
    Anything after (calculation_engine, quote_version_service) is patched
    separately on api.quotes in individual tests.
    """
    sb = MagicMock()

    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "organization_members":
            data = [{"organization_id": org_id}] if org_id else []
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = data
        elif name == "quotes":
            data = [quote] if quote else []
            # Three chained .eq + .is_ filters
            (
                tbl.select.return_value.eq.return_value
                .eq.return_value.is_.return_value.execute.return_value.data
            ) = data
            # quote update chain
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock()
        elif name == "invoices":
            tbl.select.return_value.eq.return_value.execute.return_value.data = []
        elif name in (
            "quote_calculation_variables",
            "quote_calculation_results",
            "quote_calculation_summaries",
        ):
            tbl.select.return_value.eq.return_value.execute.return_value.data = []
            tbl.insert.return_value.execute.return_value = MagicMock()
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock()
        elif name == "quote_items":
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock()
        return tbl

    sb.table.side_effect = table_side_effect
    return sb


def _run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


def _fake_calc_result():
    """Build a mock calculation_engine result row with every attribute the
    handler reads. Values are arbitrary but deterministic so tests can
    assert on exact output.
    """
    r = SimpleNamespace(
        purchase_price_total_quote_currency=100.0,
        logistics_total=10.0,
        cogs_per_product=60.0,
        profit=40.0,
        sales_price_total_no_vat=110.0,
        sales_price_total_with_vat=132.0,
        vat_net_payable=22.0,
        customs_fee=5.0,
        purchase_price_no_vat=90.0,
        purchase_price_after_discount=85.0,
        purchase_price_per_unit_quote_currency=50.0,
        logistics_first_leg=5.0,
        logistics_last_leg=5.0,
        excise_tax_amount=0.0,
        cogs_per_unit=30.0,
        sale_price_per_unit_excl_financial=45.0,
        sale_price_total_excl_financial=90.0,
        dm_fee=1.0,
        forex_reserve=0.5,
        financial_agent_fee=0.5,
        sales_price_per_unit_no_vat=55.0,
        sales_price_per_unit_with_vat=66.0,
        vat_from_sales=22.0,
        vat_on_import=5.0,
        transit_commission=0.0,
        internal_sale_price_per_unit=44.0,
        internal_sale_price_total=88.0,
        financing_cost_initial=0.0,
        financing_cost_credit=0.0,
    )
    return r


# ----------------------------------------------------------------------------
# Auth edge cases
# ----------------------------------------------------------------------------


class TestCalculateAuth:
    def test_no_auth_returns_401(self):
        """No JWT + no session → 401."""
        req = _make_request(api_user_id=None)
        resp = _run(calculate_quote(req, "q-1"))
        assert resp.status_code == 401
        assert _body(resp) == {"error": "Unauthorized"}

    @patch("api.quotes.get_supabase")
    def test_jwt_without_org_returns_403(self, mock_get_sb):
        """JWT valid but user has no organization_members row → 403."""
        mock_get_sb.return_value = _mock_supabase_for_calc(org_id=None)
        req = _make_request(api_user_id="u-no-org")

        resp = _run(calculate_quote(req, "q-1"))
        assert resp.status_code == 403
        assert _body(resp) == {"error": "No organization"}


# ----------------------------------------------------------------------------
# Quote + composition edge cases
# ----------------------------------------------------------------------------


class TestCalculateQuoteShape:
    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_missing_quote_returns_404(self, mock_get_sb, mock_composed):
        """Quote row doesn't exist for this org → 404 before touching items."""
        mock_get_sb.return_value = _mock_supabase_for_calc(quote=None)

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(calculate_quote(req, "q-missing"))

        assert resp.status_code == 404
        assert _body(resp) == {"error": "Quote not found"}
        # get_composed_items must NOT have been called — 404 short-circuits
        mock_composed.assert_not_called()

    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_no_items_returns_400(self, mock_get_sb, mock_composed):
        """Quote exists but composition returns empty → 400."""
        mock_get_sb.return_value = _mock_supabase_for_calc(
            quote={"id": "q-1", "currency": "USD"}
        )
        mock_composed.return_value = []

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 400
        assert _body(resp) == {"error": "Cannot calculate - no products in quote"}

    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_items_without_price_returns_400(self, mock_get_sb, mock_composed):
        """Available items but none have a price → 400 with item labels."""
        mock_get_sb.return_value = _mock_supabase_for_calc(
            quote={"id": "q-1", "currency": "USD"}
        )
        mock_composed.return_value = [
            {
                "id": "item-1",
                "is_unavailable": False,
                "purchase_price_original": 0,
                "base_price_vat": 0,
                "product_name": "Widget",
                "brand": "Acme",
            },
        ]

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 400
        body = _body(resp)
        assert body["error"] == "Not all items have prices"
        assert body["items_without_price"] == ["Acme — Widget"]


# ----------------------------------------------------------------------------
# Happy path + calc-engine error
# ----------------------------------------------------------------------------


class TestCalculateHappyPath:
    @patch("api.quotes.list_quote_versions")
    @patch("api.quotes.create_quote_version")
    @patch("api.quotes.calculate_multiproduct_quote")
    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_happy_path_returns_totals(
        self,
        mock_get_sb,
        mock_composed,
        mock_calc,
        mock_create_version,
        mock_list_versions,
    ):
        """Happy path: JWT, quote exists, one priced item → 200 with totals."""
        mock_get_sb.return_value = _mock_supabase_for_calc(
            quote={"id": "q-1", "currency": "USD", "customer_id": "cust-1"}
        )
        mock_composed.return_value = [
            {
                "id": "item-1",
                "is_unavailable": False,
                "purchase_price_original": 100,
                "base_price_vat": 120,
                "product_name": "Widget",
                "brand": "Acme",
                "quantity": 2,
                "production_time_days": 5,
            },
        ]
        mock_calc.return_value = [_fake_calc_result()]
        mock_list_versions.return_value = []  # → create_quote_version branch

        req = _make_request(
            api_user_id="u-1",
            body={
                "currency": "USD",
                "markup": "15",
                "supplier_discount": "0",
                "exchange_rate": "1.0",
            },
        )
        resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 200, _body(resp)
        payload = _body(resp)
        assert payload["success"] is True
        # Envelope must include every key the frontend consumes.
        for key in (
            "total",
            "total_no_vat",
            "profit",
            "margin",
            "currency",
            "cogs",
            "logistics",
            "brokerage",
            "customs",
            "vat",
        ):
            assert key in payload, f"Missing key {key!r} in response"

        # Engine was invoked exactly once.
        mock_calc.assert_called_once()
        # First-time quote → create_quote_version path, not update.
        mock_create_version.assert_called_once()

    @patch("api.quotes.calculate_multiproduct_quote")
    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_calc_engine_exception_returns_500(
        self, mock_get_sb, mock_composed, mock_calc
    ):
        """Calculation engine blows up → 500 with the exception message."""
        mock_get_sb.return_value = _mock_supabase_for_calc(
            quote={"id": "q-1", "currency": "USD"}
        )
        mock_composed.return_value = [
            {
                "id": "item-1",
                "is_unavailable": False,
                "purchase_price_original": 100,
                "base_price_vat": 120,
                "product_name": "Widget",
                "brand": "Acme",
                "quantity": 1,
            },
        ]
        mock_calc.side_effect = RuntimeError("engine exploded")

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 500
        assert _body(resp) == {"error": "engine exploded"}
