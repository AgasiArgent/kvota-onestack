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
        assert _body(resp) == {
            "success": False,
            "error": {"code": "UNAUTHORIZED", "message": "Unauthorized"},
        }

    @patch("api.quotes.get_supabase")
    def test_jwt_without_org_returns_403(self, mock_get_sb):
        """JWT valid but user has no organization_members row → 403."""
        mock_get_sb.return_value = _mock_supabase_for_calc(org_id=None)
        req = _make_request(api_user_id="u-no-org")

        resp = _run(calculate_quote(req, "q-1"))
        assert resp.status_code == 403
        assert _body(resp) == {
            "success": False,
            "error": {"code": "FORBIDDEN", "message": "No organization"},
        }


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
        assert _body(resp) == {
            "success": False,
            "error": {"code": "NOT_FOUND", "message": "Quote not found"},
        }
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
        assert _body(resp) == {
            "success": False,
            "error": {
                "code": "EMPTY_QUOTE",
                "message": "Cannot calculate - no products in quote",
            },
        }

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
        assert body["success"] is False
        assert body["error"] == {
            "code": "MISSING_PRICES",
            "message": "Not all items have prices",
        }
        assert body["items_without_price"] == ["Acme — Widget"]


# ----------------------------------------------------------------------------
# Hard-stop 5% markup (Testing 2 row 47)
# ----------------------------------------------------------------------------


class TestCalculateMarkupHardStop:
    """Defense-in-depth: even if the FE-side disable is bypassed, the
    backend rejects markup < 5 with a structured 400 the FE can surface."""

    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_markup_below_5_returns_400(self, mock_get_sb, mock_composed):
        """markup=4 → 400 MARKUP_TOO_LOW before the engine is touched."""
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

        req = _make_request(api_user_id="u-1", body={"markup": "4"})
        resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 400
        assert _body(resp) == {
            "success": False,
            "error": {
                "code": "MARKUP_TOO_LOW",
                "message": "Наценка должна быть не менее 5%",
            },
        }

    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_markup_exactly_5_is_not_blocked(self, mock_get_sb, mock_composed):
        """markup=5 → MARKUP_TOO_LOW guard does NOT fire. The handler may
        still 500 deeper in the pipeline because we have not mocked the
        engine — that's fine. The point of this assertion is to prove the
        guard is strictly <, not <=."""
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

        req = _make_request(api_user_id="u-1", body={"markup": "5"})
        resp = _run(calculate_quote(req, "q-1"))

        body = _body(resp)
        # The MARKUP_TOO_LOW guard MUST NOT match at exactly 5.
        err = body.get("error")
        if isinstance(err, dict):
            assert err.get("code") != "MARKUP_TOO_LOW", (
                f"5% must be valid, got 400 MARKUP_TOO_LOW: {body!r}"
            )

    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_markup_4_9_returns_400(self, mock_get_sb, mock_composed):
        """Edge case: 4.9% (decimal just below threshold) → 400 MARKUP_TOO_LOW."""
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

        req = _make_request(api_user_id="u-1", body={"markup": "4.9"})
        resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 400
        body = _body(resp)
        assert body["error"]["code"] == "MARKUP_TOO_LOW"


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
    def test_calc_engine_exception_returns_500_with_engine_error_code(
        self, mock_get_sb, mock_composed, mock_calc
    ):
        """Calculation engine blows up → 500 CALC_ENGINE_ERROR with exception_class detail."""
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
        payload = _body(resp)
        assert payload["success"] is False
        assert payload["error"]["code"] == "CALC_ENGINE_ERROR"
        assert "Calculation engine" in payload["error"]["message"]
        # Raw exception message must NOT leak; only safe class name in detail.
        assert "engine exploded" not in json.dumps(payload)
        assert payload["error"]["detail"]["exception_class"] == "RuntimeError"

    @patch("api.quotes.calculate_multiproduct_quote")
    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_build_inputs_exception_returns_500_with_build_error_code(
        self, mock_get_sb, mock_composed, mock_calc
    ):
        """build_calculation_inputs raises → 500 BUILD_INPUTS_ERROR.

        Note: build_calculation_inputs is imported inside the handler from
        services.calculation_helpers, so we patch at the services boundary.
        """
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
        # Patch the function as actually imported by the handler
        with patch(
            "services.calculation_helpers.build_calculation_inputs",
            side_effect=KeyError("missing_field"),
        ):
            req = _make_request(api_user_id="u-1", body={})
            resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 500
        payload = _body(resp)
        assert payload["error"]["code"] == "BUILD_INPUTS_ERROR"
        assert "prepare calculation inputs" in payload["error"]["message"]
        # Raw key name must NOT leak; only class name.
        assert "missing_field" not in json.dumps(payload)
        assert payload["error"]["detail"]["exception_class"] == "KeyError"
        # calc engine must NOT have been called when build failed.
        mock_calc.assert_not_called()

    @patch("api.quotes.calculate_multiproduct_quote")
    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_db_write_exception_returns_500_with_unexpected_error_code(
        self, mock_get_sb, mock_composed, mock_calc
    ):
        """Failure outside the per-phase buckets (e.g., DB write) → 500
        UNEXPECTED_CALC_ERROR with exception_class detail. Confirms the
        outer safety net catches and structures errors that bypass the
        granular catches.
        """
        sb = _mock_supabase_for_calc(quote={"id": "q-1", "currency": "USD"})

        def boom_table(name: str):
            tbl = MagicMock()
            if name == "organization_members":
                tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"organization_id": "org-1"}
                ]
            elif name == "quotes":
                (
                    tbl.select.return_value.eq.return_value
                    .eq.return_value.is_.return_value.execute.return_value.data
                ) = [{"id": "q-1", "currency": "USD"}]
                tbl.update.return_value.eq.return_value.execute.side_effect = (
                    ConnectionError("supabase down")
                )
            elif name == "invoices":
                tbl.select.return_value.eq.return_value.execute.return_value.data = []
            return tbl

        sb.table.side_effect = boom_table
        mock_get_sb.return_value = sb
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
        mock_calc.return_value = [_fake_calc_result()]

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(calculate_quote(req, "q-1"))

        assert resp.status_code == 500
        payload = _body(resp)
        assert payload["error"]["code"] == "UNEXPECTED_CALC_ERROR"
        assert "supabase down" not in json.dumps(payload)
        assert payload["error"]["detail"]["exception_class"] == "ConnectionError"


# ----------------------------------------------------------------------------
# Excluded items: is_unavailable + import_banned (Testing 2 row 87)
# ----------------------------------------------------------------------------
#
# Customer-decided exclusions on quote_items must NOT crash the calc step and
# MUST NOT participate in totals. Two flags live on quote_items:
#
#   * is_unavailable=True  — refused by procurement (МОП/МОЗ): item is N/A,
#     no КПП was raised, no price will ever exist.
#   * import_banned=True  — disallowed by customs (e.g. "В наличии в РФ"): item
#     reaches КПП but is dropped at customs.
#
# Both behave identically at the calc layer: skip from price validation, skip
# from build_calculation_inputs, skip from the per-item result persistence
# zip. The composition_service.get_composed_items adapter already emits a
# _legacy_shape dict (no purchase_price_original) for such items; we just need
# to teach the price-validation loop and the result-persistence zip to skip
# them.
#
# The current bug (Row 87, quote ec48c1fc-...): an import_banned item with no
# price reaches the MISSING_PRICES guard before build_calculation_inputs has a
# chance to filter it. Result: every calc call returns 400 instead of dropping
# the banned item and proceeding with the remaining items. Tester observed
# this on quote ec48c1fc-... position 25 "Миксер пневматический PM-3/TJ3".


class TestCalculateExcludedItems:
    """Excluded items (is_unavailable / import_banned) must be dropped, not
    block the calc. See Testing 2 row 87."""

    @patch("api.quotes.list_quote_versions")
    @patch("api.quotes.create_quote_version")
    @patch("api.quotes.calculate_multiproduct_quote")
    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_import_banned_item_without_price_does_not_block_calc(
        self,
        mock_get_sb,
        mock_composed,
        mock_calc,
        mock_create_version,
        mock_list_versions,
    ):
        """import_banned item with no price + one priced item → 200, banned
        item is dropped from totals, MISSING_PRICES is NOT raised.

        Reproduces Testing 2 row 87 directly: МОП refused position 25 at the
        customs stage (import_banned=True), but the rest of the КПП has prices.
        The calc must succeed against the priced items and treat the banned
        one as silently excluded.
        """
        mock_get_sb.return_value = _mock_supabase_for_calc(
            quote={"id": "q-1", "currency": "USD", "customer_id": "cust-1"}
        )
        mock_composed.return_value = [
            {
                "id": "item-priced",
                "is_unavailable": False,
                "import_banned": False,
                "purchase_price_original": 100,
                "base_price_vat": 120,
                "product_name": "Регулятор давления Graco",
                "brand": "GRACO",
                "quantity": 1,
            },
            {
                "id": "item-banned",
                "is_unavailable": False,
                "import_banned": True,
                "import_ban_reason": "В наличии в РФ",
                # No price — this is the exact shape that crashed in prod.
                "purchase_price_original": None,
                "base_price_vat": None,
                "product_name": "Миксер пневматический PM-3/TJ3",
                "brand": "Китайский бренд",
                "quantity": 1,
            },
        ]
        mock_calc.return_value = [_fake_calc_result()]
        mock_list_versions.return_value = []

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(calculate_quote(req, "q-1"))

        # MUST NOT crash with MISSING_PRICES — banned item is excluded, not
        # missing-priced.
        assert resp.status_code == 200, _body(resp)
        payload = _body(resp)
        assert payload["success"] is True

    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_only_excluded_items_returns_missing_prices(
        self, mock_get_sb, mock_composed
    ):
        """Edge case: every item is excluded → no priced items → still a 400,
        but it must come from MISSING_PRICES (or EMPTY) — not a 500."""
        mock_get_sb.return_value = _mock_supabase_for_calc(
            quote={"id": "q-1", "currency": "USD"}
        )
        mock_composed.return_value = [
            {
                "id": "item-banned-1",
                "is_unavailable": False,
                "import_banned": True,
                "purchase_price_original": None,
                "product_name": "Widget A",
                "brand": "Acme",
                "quantity": 1,
            },
            {
                "id": "item-banned-2",
                "is_unavailable": True,
                "import_banned": False,
                "purchase_price_original": None,
                "product_name": "Widget B",
                "brand": "Acme",
                "quantity": 1,
            },
        ]

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(calculate_quote(req, "q-1"))

        # Either MISSING_PRICES or NO_CALCULABLE_ITEMS — both are structured
        # 4xx, neither is a 500. The exact code is fine to evolve; the
        # important invariant is "no 5xx and no MISSING_PRICES naming an
        # already-excluded item."
        assert resp.status_code in (400, 422), _body(resp)
        body = _body(resp)
        assert body["success"] is False
        # If MISSING_PRICES is emitted, the items_without_price list MUST NOT
        # contain items we already excluded (banned/unavailable).
        if body.get("error", {}).get("code") == "MISSING_PRICES":
            assert body.get("items_without_price", []) == [], (
                f"Excluded items leaked into MISSING_PRICES: {body!r}"
            )

    @patch("api.quotes.get_composed_items")
    @patch("api.quotes.get_supabase")
    def test_is_unavailable_without_price_does_not_appear_in_missing_prices(
        self, mock_get_sb, mock_composed
    ):
        """Regression: is_unavailable items must not appear in MISSING_PRICES.

        Already covered by the pre-existing skip on line 225 of api/quotes.py,
        but pinning it as a test so symmetry with import_banned is enforced —
        i.e. removing one skip without the other would fail this.
        """
        mock_get_sb.return_value = _mock_supabase_for_calc(
            quote={"id": "q-1", "currency": "USD"}
        )
        mock_composed.return_value = [
            {
                "id": "item-priced",
                "is_unavailable": False,
                "import_banned": False,
                "purchase_price_original": 50,
                "base_price_vat": 60,
                "product_name": "Priced",
                "brand": "Acme",
                "quantity": 1,
            },
            {
                "id": "item-na",
                "is_unavailable": True,
                "import_banned": False,
                "purchase_price_original": None,
                "product_name": "Unavailable",
                "brand": "Acme",
                "quantity": 1,
            },
        ]

        req = _make_request(api_user_id="u-1", body={"markup": "15"})
        resp = _run(calculate_quote(req, "q-1"))

        # Either the calc proceeds (200) or it errors for some other reason,
        # but it MUST NOT raise MISSING_PRICES on the is_unavailable item.
        body = _body(resp)
        if body.get("error", {}).get("code") == "MISSING_PRICES":
            assert "Unavailable" not in json.dumps(body, ensure_ascii=False), (
                f"is_unavailable item leaked into MISSING_PRICES: {body!r}"
            )
