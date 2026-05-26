"""Testing 2 row 90 — МОП-controlled КПП inclusion + position ordering.

Two behaviours covered:

1. quote_items are ordered by ``position`` on every composition query.
   The picker UI and calc engine input must reflect the request order МОП
   entered, not the physical/insertion order PostgREST returns by default.

2. ``included_in_calc=False`` excludes the row from the calc engine inputs
   built by ``build_calculation_inputs()``. Distinct from ``is_unavailable``
   (system N/A) and ``import_banned`` (customs auto-block): МОП-controlled.

The migration adds the column with ``DEFAULT TRUE`` so legacy rows pass
through unchanged. These tests assert the new behaviours without touching
the locked calculation engine.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.calculation_helpers import build_calculation_inputs  # noqa: E402
from services.composition_service import (  # noqa: E402
    apply_included_in_calc,
    get_composed_items,
    get_composition_view,
    is_procurement_complete,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _chainable(return_value):
    """Build a MagicMock that chains select/eq/order/in_/is_/limit/single and
    terminates at execute() returning .data=return_value."""
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.in_.return_value = q
    q.order.return_value = q
    q.is_.return_value = q
    q.limit.return_value = q
    q.single.return_value = q
    q.update.return_value = q
    result = MagicMock()
    result.data = return_value
    result.error = None
    q.execute.return_value = result
    return q


def _make_minimal_variables() -> dict:
    """Shape matches services.calculation_helpers.build_calculation_inputs."""
    return {
        "currency_of_quote": "RUB",
        "markup": Decimal("15"),
        "supplier_discount": Decimal("0"),
        "offer_incoterms": "DDP",
        "delivery_time": 30,
        "seller_company": "МАСТЕР БЭРИНГ ООО",
        "offer_sale_type": "поставка",
        "logistics_supplier_hub": Decimal("0"),
        "logistics_hub_customs": Decimal("0"),
        "logistics_customs_client": Decimal("0"),
        "brokerage_hub": Decimal("0"),
        "brokerage_hub_currency": "RUB",
        "brokerage_customs": Decimal("0"),
        "brokerage_customs_currency": "RUB",
        "warehousing_at_customs": Decimal("0"),
        "warehousing_at_customs_currency": "RUB",
        "customs_documentation": Decimal("0"),
        "customs_documentation_currency": "RUB",
        "brokerage_extra": Decimal("0"),
        "brokerage_extra_currency": "RUB",
        "advance_from_client": Decimal("100"),
        "advance_to_supplier": Decimal("100"),
        "time_to_advance": 0,
        "time_to_advance_on_receiving": 0,
        "dm_fee_type": "fixed",
        "dm_fee_value": Decimal("0"),
        "dm_fee_currency": "RUB",
        "exchange_rate": Decimal("1.0"),
    }


def _make_item(**overrides) -> dict:
    base = {
        "id": "qi-1",
        "purchase_price_original": Decimal("1000"),
        "purchase_currency": "RUB",
        "quantity": 1,
        "weight_in_kg": Decimal("10"),
        "customs_code": "1234567890",
        "customs_duty": Decimal("5"),
        "customs_duty_per_kg": Decimal("0"),
        "supplier_country": "RU",
        "price_includes_vat": False,
        "markup": Decimal("15"),
        "supplier_discount": Decimal("0"),
        "is_unavailable": False,
        "import_banned": False,
        "included_in_calc": True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# build_calculation_inputs — included_in_calc=False filter
# ---------------------------------------------------------------------------


class TestBuildCalculationInputsInclusion:
    """build_calculation_inputs() must drop rows with included_in_calc=False."""

    def test_excluded_item_is_dropped(self):
        included = _make_item(id="qi-included", included_in_calc=True)
        excluded = _make_item(id="qi-excluded", included_in_calc=False)

        inputs = build_calculation_inputs([included, excluded], _make_minimal_variables())

        assert len(inputs) == 1, (
            "build_calculation_inputs must drop rows where included_in_calc is False"
        )

    def test_included_in_calc_default_true_preserves_legacy_rows(self):
        """Pre-migration rows lack the column entirely — treat them as included."""
        legacy = _make_item(id="qi-legacy")
        legacy.pop("included_in_calc", None)

        inputs = build_calculation_inputs([legacy], _make_minimal_variables())

        assert len(inputs) == 1

    def test_excluded_takes_precedence_over_other_filters(self):
        """Excluded + N/A + banned all produce zero inputs (no double-counting)."""
        rows = [
            _make_item(id="qi-1", included_in_calc=False),
            _make_item(id="qi-2", is_unavailable=True),
            _make_item(id="qi-3", import_banned=True),
        ]
        inputs = build_calculation_inputs(rows, _make_minimal_variables())
        assert inputs == []

    def test_all_excluded_returns_empty_list(self):
        rows = [
            _make_item(id="qi-1", included_in_calc=False),
            _make_item(id="qi-2", included_in_calc=False),
        ]
        inputs = build_calculation_inputs(rows, _make_minimal_variables())
        assert inputs == []


# ---------------------------------------------------------------------------
# get_composed_items / get_composition_view — ORDER BY position
# ---------------------------------------------------------------------------


class TestCompositionOrderByPosition:
    """Both composition queries must request ORDER BY position ascending."""

    def test_get_composed_items_orders_quote_items_by_position(self):
        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable([])

        get_composed_items("q-1", sb)

        # Find the quote_items query and assert it called .order("position", ...)
        qi_table_calls = [
            call for call in sb.table.call_args_list if call.args == ("quote_items",)
        ]
        assert qi_table_calls, "get_composed_items must query quote_items"

        # MagicMock side_effect bypasses return_value, so we need to walk
        # the per-table chainables — re-run get_composed_items with a
        # capture-based router and inspect that .order("position", ...) was
        # called on at least one quote_items chainable.
        captured = []

        def capture(name):
            ch = _chainable([])
            captured.append((name, ch))
            return ch

        sb2 = MagicMock()
        sb2.table.side_effect = capture
        get_composed_items("q-2", sb2)
        qi_chains = [ch for (name, ch) in captured if name == "quote_items"]
        assert qi_chains, "expected get_composed_items to hit quote_items"
        # The chainable's .order should have been called with ("position", ...)
        order_calls = [
            args for ch in qi_chains for args in ch.order.call_args_list
        ]
        assert any(
            ("position" in tuple(c.args) for c in order_calls)
        ), f"expected .order('position', ...) call, got: {order_calls}"

    def test_get_composition_view_orders_quote_items_by_position(self):
        captured = []

        def capture(name):
            ch = _chainable([])
            captured.append((name, ch))
            return ch

        sb = MagicMock()
        sb.table.side_effect = capture

        get_composition_view("q-1", sb)

        qi_chains = [ch for (name, ch) in captured if name == "quote_items"]
        assert qi_chains, "expected get_composition_view to hit quote_items"
        order_calls = [
            args for ch in qi_chains for args in ch.order.call_args_list
        ]
        assert any(
            ("position" in tuple(c.args) for c in order_calls)
        ), f"expected .order('position', ...) call, got: {order_calls}"


# ---------------------------------------------------------------------------
# get_composition_view — surface included_in_calc on view rows
# ---------------------------------------------------------------------------


class TestCompositionViewIncludedFlag:
    """The picker payload must expose `included_in_calc` per item."""

    def test_view_includes_flag_default_true(self):
        captured = {}

        def router(name):
            if name == "quote_items":
                captured[name] = _chainable([
                    {
                        "id": "qi-A",
                        "position": 1,
                        "product_name": "Bolt",
                        "quantity": 100,
                        "composition_selected_invoice_id": None,
                        "included_in_calc": True,
                    },
                    {
                        "id": "qi-B",
                        "position": 2,
                        "product_name": "Nut",
                        "quantity": 50,
                        "composition_selected_invoice_id": None,
                        "included_in_calc": False,
                    },
                ])
                return captured[name]
            return _chainable([])

        sb = MagicMock()
        sb.table.side_effect = router

        view = get_composition_view("q-1", sb)
        items = view["items"]
        assert len(items) == 2
        by_id = {it["quote_item_id"]: it for it in items}
        assert by_id["qi-A"]["included_in_calc"] is True
        assert by_id["qi-B"]["included_in_calc"] is False

    def test_excluded_items_do_not_make_composition_incomplete(self):
        """An excluded item without a selected supplier MUST NOT flip
        composition_complete to False — it is intentionally out of the calc."""
        def router(name):
            if name == "quote_items":
                return _chainable([
                    {
                        "id": "qi-1",
                        "position": 1,
                        "product_name": "Bolt",
                        "composition_selected_invoice_id": "inv-1",
                        "included_in_calc": True,
                    },
                    {
                        "id": "qi-2",
                        "position": 2,
                        "product_name": "Excluded",
                        "composition_selected_invoice_id": None,
                        "included_in_calc": False,
                    },
                ])
            return _chainable([])

        sb = MagicMock()
        sb.table.side_effect = router

        view = get_composition_view("q-1", sb)
        assert view["composition_complete"] is True


# ---------------------------------------------------------------------------
# apply_included_in_calc — service function
# ---------------------------------------------------------------------------


class TestApplyIncludedInCalc:

    def test_writes_each_entry_to_quote_items(self):
        sb = MagicMock()
        chainable = _chainable([])
        sb.table.return_value = chainable

        apply_included_in_calc(
            quote_id="q-1",
            inclusion_map={"qi-A": False, "qi-B": True},
            supabase=sb,
            user_id="user-1",
        )

        # 2 quote_items updates + 1 quotes.updated_at bump = 3 .update() calls
        assert chainable.update.call_count == 3
        # Check the payloads we sent
        update_payloads = [c.args[0] for c in chainable.update.call_args_list]
        assert {"included_in_calc": False} in update_payloads
        assert {"included_in_calc": True} in update_payloads

    def test_empty_inclusion_map_is_noop(self):
        sb = MagicMock()
        chainable = _chainable([])
        sb.table.return_value = chainable

        apply_included_in_calc(
            quote_id="q-1",
            inclusion_map={},
            supabase=sb,
            user_id="user-1",
        )

        assert chainable.update.call_count == 0


# ---------------------------------------------------------------------------
# is_procurement_complete respects exclusion
# ---------------------------------------------------------------------------


class TestProcurementCompleteRespectsExclusion:
    """Excluded items are not required for procurement-complete (parity with
    is_unavailable). Without this, an МОП-excluded item with no КПП would
    keep the quote stuck in pending_procurement forever."""

    def test_excluded_item_without_supplier_still_complete(self):
        items = [
            {
                "id": "qi-priced",
                "is_unavailable": False,
                "included_in_calc": True,
                "composition_selected_invoice_id": "inv-1",
            },
            {
                "id": "qi-excluded",
                "is_unavailable": False,
                "included_in_calc": False,
                "composition_selected_invoice_id": None,
            },
        ]
        coverage_rows = [
            {
                "quote_item_id": "qi-priced",
                "invoice_items": {
                    "invoice_id": "inv-1",
                    "purchase_price_original": 10.0,
                },
            },
        ]
        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        assert is_procurement_complete("q-1", sb) is True

    def test_legacy_rows_without_column_still_required(self):
        """Rows from pre-migration data have no included_in_calc — treat as True."""
        items = [
            {
                "id": "qi-1",
                "is_unavailable": False,
                # No included_in_calc key
                "composition_selected_invoice_id": None,
            },
        ]
        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        # Legacy row treated as required → not complete (no price)
        assert is_procurement_complete("q-1", sb) is False


# ---------------------------------------------------------------------------
# Calc-item shape: included_in_calc flows through get_composed_items
# ---------------------------------------------------------------------------


class TestComposedItemsCarryInclusionFlag:
    """get_composed_items output must carry included_in_calc so the downstream
    build_calculation_inputs() filter has something to look at."""

    def test_legacy_shape_carries_flag(self):
        """Quote_item with no composition pointer → legacy shape with the flag."""
        def router(name):
            if name == "quote_items":
                return _chainable([
                    {
                        "id": "qi-1",
                        "position": 1,
                        "product_name": "Bolt",
                        "quantity": 100,
                        "is_unavailable": False,
                        "import_banned": False,
                        "included_in_calc": False,
                        "composition_selected_invoice_id": None,
                    },
                ])
            return _chainable([])

        sb = MagicMock()
        sb.table.side_effect = router

        result = get_composed_items("q-1", sb)
        assert len(result) == 1
        assert result[0]["included_in_calc"] is False

    def test_composed_shape_carries_flag(self):
        """1:1 composition → included_in_calc from quote_item (customer-side)."""
        ii = {
            "id": "ii-1",
            "invoice_id": "inv-1",
            "product_name": "Bolt M8",
            "quantity": 100,
            "purchase_price_original": 50.0,
            "purchase_currency": "EUR",
        }

        def router(name):
            if name == "quote_items":
                return _chainable([
                    {
                        "id": "qi-1",
                        "position": 1,
                        "product_name": "Bolt",
                        "quantity": 100,
                        "is_unavailable": False,
                        "import_banned": False,
                        "included_in_calc": False,
                        "composition_selected_invoice_id": "inv-1",
                        "markup": 15,
                    },
                ])
            if name == "invoice_item_coverage":
                return _chainable([
                    {
                        "invoice_item_id": "ii-1",
                        "quote_item_id": "qi-1",
                        "ratio": 1,
                        "invoice_items": ii,
                    },
                ])
            return _chainable([])

        sb = MagicMock()
        sb.table.side_effect = router

        result = get_composed_items("q-1", sb)
        assert len(result) == 1
        assert result[0]["included_in_calc"] is False
