"""
Tests for Composition Service — Phase 5b.

Covers:
- get_composed_items: overlay logic, legacy fallback, non-price field preservation,
  query count bounds
- validate_composition: happy path + rejection of non-existent iip rows
- apply_composition: validation-first, atomic update pattern, optimistic concurrency
- freeze_composition: stamps frozen_at, idempotency, quote scope
- Locked files: ensures composition_service does not import from the calc engine
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.composition_service import (  # noqa: E402
    ConcurrencyError,
    ValidationError,
    apply_composition,
    freeze_composition,
    get_composed_items,
    get_composition_view,
    validate_composition,
)


# ============================================================================
# Test fixtures — lightweight supabase builder
# ============================================================================

def _chainable(return_value):
    """Build a MagicMock that chains select/eq/in_/order/limit/single and
    terminates at execute() returning a result with .data=return_value."""
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.in_.return_value = q
    q.order.return_value = q
    q.limit.return_value = q
    q.single.return_value = q
    result = MagicMock()
    result.data = return_value
    result.error = None
    q.execute.return_value = result
    return q


def make_supabase(table_data: dict) -> MagicMock:
    """Build a mock supabase client where each table returns the given data.

    For read paths (select/eq/in_/execute), the mock ignores filters and
    always returns the table's full data — tests pass only the relevant rows.
    For write paths (update/insert), each .table() call returns the SAME
    chainable mock so tests can inspect `.update.call_args_list` via
    `sb.table.return_value.update.call_args_list`.
    """
    sb = MagicMock()

    def _get_table(name):
        data = table_data.get(name, [])
        return _chainable(data)

    sb.table.side_effect = _get_table
    return sb


def make_write_supabase() -> MagicMock:
    """Build a mock where every .table(X) returns the same chainable mock.

    Use this when you want to spy on update/insert calls — all writes go
    through the same mock so call_args_list accumulates across tables.
    """
    shared = _chainable([])
    sb = MagicMock()
    sb.table.return_value = shared
    return sb


# ============================================================================
# get_composed_items
# ============================================================================

class TestGetComposedItems:
    """Overlay logic for the calculation adapter path."""

    def test_overlays_iip_price_when_pointer_set(self):
        """When composition pointer is set, price fields come from iip row."""
        quote_id = "q-1"
        item_id = "qi-1"
        invoice_id = "inv-1"

        def table_data(name):
            if name == "quote_items":
                return [{
                    "id": item_id,
                    "quote_id": quote_id,
                    "invoice_id": invoice_id,
                    "composition_selected_invoice_id": invoice_id,
                    "purchase_price_original": 100.00,  # legacy price
                    "purchase_currency": "USD",
                    "base_price_vat": 120.00,
                    "price_includes_vat": True,
                    "quantity": 5,
                    "customs_code": "8708",
                }]
            if name == "invoice_item_prices":
                return [{
                    "id": "iip-1",
                    "quote_item_id": item_id,
                    "invoice_id": invoice_id,
                    "purchase_price_original": 85.50,  # overlay price
                    "purchase_currency": "EUR",
                    "base_price_vat": 102.60,
                    "price_includes_vat": False,
                    "version": 1,
                }]
            return []

        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable(table_data(name))

        result = get_composed_items(quote_id, sb)

        assert len(result) == 1
        row = result[0]
        assert row["purchase_price_original"] == 85.50, "price not overlaid from iip"
        assert row["purchase_currency"] == "EUR", "currency not overlaid from iip"
        assert row["base_price_vat"] == 102.60, "base_price_vat not overlaid"
        assert row["price_includes_vat"] is False, "vat flag not overlaid"

    def test_falls_back_to_legacy_when_pointer_null(self):
        """When composition pointer is NULL, quote_items price is used as-is."""
        quote_id = "q-1"

        def table_data(name):
            if name == "quote_items":
                return [{
                    "id": "qi-1",
                    "quote_id": quote_id,
                    "invoice_id": "inv-1",
                    "composition_selected_invoice_id": None,  # legacy path
                    "purchase_price_original": 100.00,
                    "purchase_currency": "USD",
                    "base_price_vat": 120.00,
                    "price_includes_vat": True,
                    "quantity": 5,
                }]
            return []

        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable(table_data(name))

        result = get_composed_items(quote_id, sb)

        assert len(result) == 1
        assert result[0]["purchase_price_original"] == 100.00
        assert result[0]["purchase_currency"] == "USD"

    def test_preserves_non_price_fields(self):
        """Overlay must only touch the 4 price fields, not customs/weight/etc."""
        quote_id = "q-1"

        def table_data(name):
            if name == "quote_items":
                return [{
                    "id": "qi-1",
                    "quote_id": quote_id,
                    "composition_selected_invoice_id": "inv-1",
                    "purchase_price_original": 100.00,
                    "purchase_currency": "USD",
                    "base_price_vat": 120.00,
                    "price_includes_vat": True,
                    "quantity": 5,
                    "customs_code": "8708913509",
                    "weight_in_kg": 25.5,
                    "supplier_country": "China",
                    "is_unavailable": False,
                    "import_banned": False,
                }]
            if name == "invoice_item_prices":
                return [{
                    "id": "iip-1",
                    "quote_item_id": "qi-1",
                    "invoice_id": "inv-1",
                    "purchase_price_original": 50.00,
                    "purchase_currency": "EUR",
                    "base_price_vat": 60.00,
                    "price_includes_vat": False,
                    "version": 1,
                }]
            return []

        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable(table_data(name))

        row = get_composed_items(quote_id, sb)[0]

        assert row["customs_code"] == "8708913509"
        assert row["weight_in_kg"] == 25.5
        assert row["supplier_country"] == "China"
        assert row["quantity"] == 5
        assert row["is_unavailable"] is False
        assert row["import_banned"] is False

    def test_executes_bounded_queries_no_n_plus_1(self):
        """Must issue at most 2 .table() reads regardless of item count."""
        quote_id = "q-1"
        items = [
            {
                "id": f"qi-{i}",
                "quote_id": quote_id,
                "composition_selected_invoice_id": f"inv-{i % 3}",
                "purchase_price_original": 100.0,
                "purchase_currency": "USD",
                "base_price_vat": 120.0,
                "price_includes_vat": True,
                "quantity": 1,
            }
            for i in range(50)
        ]

        def table_data(name):
            if name == "quote_items":
                return items
            if name == "invoice_item_prices":
                return []
            return []

        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable(table_data(name))

        get_composed_items(quote_id, sb)

        # Exactly 2 reads: quote_items + invoice_item_prices
        table_calls = [c.args[0] for c in sb.table.call_args_list]
        assert table_calls.count("quote_items") == 1
        assert table_calls.count("invoice_item_prices") == 1
        assert len(table_calls) == 2

    def test_handles_missing_iip_row_as_legacy_fallback(self):
        """If composition pointer is set but no iip row exists, fall back cleanly."""
        quote_id = "q-1"

        def table_data(name):
            if name == "quote_items":
                return [{
                    "id": "qi-1",
                    "quote_id": quote_id,
                    "composition_selected_invoice_id": "inv-orphan",
                    "purchase_price_original": 100.00,
                    "purchase_currency": "USD",
                    "base_price_vat": 120.00,
                    "price_includes_vat": True,
                    "quantity": 5,
                }]
            if name == "invoice_item_prices":
                return []  # No matching iip row
            return []

        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable(table_data(name))

        row = get_composed_items(quote_id, sb)[0]
        # Legacy price preserved — no crash
        assert row["purchase_price_original"] == 100.00
        assert row["purchase_currency"] == "USD"


# ============================================================================
# validate_composition
# ============================================================================

class TestValidateComposition:

    def test_happy_path_returns_valid(self):
        """All selections have matching iip rows → valid."""
        iip_rows = [
            {"quote_item_id": "qi-1", "invoice_id": "inv-a"},
            {"quote_item_id": "qi-2", "invoice_id": "inv-b"},
        ]
        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable(iip_rows)

        selection = {"qi-1": "inv-a", "qi-2": "inv-b"}
        result = validate_composition("q-1", selection, sb)

        assert result.valid is True
        assert result.errors == []

    def test_rejects_non_existent_iip_pair(self):
        """Selection with no matching iip row → invalid with error."""
        iip_rows = [
            {"quote_item_id": "qi-1", "invoice_id": "inv-a"},
        ]
        sb = MagicMock()
        sb.table.side_effect = lambda name: _chainable(iip_rows)

        selection = {"qi-1": "inv-a", "qi-2": "inv-nonexistent"}
        result = validate_composition("q-1", selection, sb)

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0]["quote_item_id"] == "qi-2"
        assert result.errors[0]["invoice_id"] == "inv-nonexistent"

    def test_empty_selection_is_valid(self):
        """Empty selection map is trivially valid."""
        sb = MagicMock()
        result = validate_composition("q-1", {}, sb)
        assert result.valid is True
        assert result.errors == []


# ============================================================================
# apply_composition
# ============================================================================

class TestApplyComposition:

    def test_updates_composition_pointer_on_happy_path(self):
        """Valid selection → calls .update() on quote_items with the pointer."""
        iip_rows = [{"quote_item_id": "qi-1", "invoice_id": "inv-a"}]
        quote_row = [{"updated_at": "2026-04-10T12:00:00+00:00"}]

        query_by_table = {
            "invoice_item_prices": _chainable(iip_rows),
            "quote_items": _chainable([]),
            "quotes": _chainable(quote_row),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        apply_composition(
            quote_id="q-1",
            selection_map={"qi-1": "inv-a"},
            supabase=sb,
            user_id="user-1",
            quote_updated_at="2026-04-10T12:00:00+00:00",
        )

        # quote_items.update called with {composition_selected_invoice_id: "inv-a"}
        qi_update_calls = query_by_table["quote_items"].update.call_args_list
        assert len(qi_update_calls) == 1
        assert qi_update_calls[0].args[0] == {"composition_selected_invoice_id": "inv-a"}

        # quotes.update called with updated_at bump
        quotes_update_calls = query_by_table["quotes"].update.call_args_list
        assert len(quotes_update_calls) == 1
        assert "updated_at" in quotes_update_calls[0].args[0]

    def test_raises_validation_error_on_invalid_selection(self):
        """Invalid selection → ValidationError, no writes."""
        iip_rows = []  # No iip rows at all

        query_by_table = {
            "invoice_item_prices": _chainable(iip_rows),
            "quote_items": _chainable([]),
            "quotes": _chainable([{"updated_at": "2026-04-10T12:00:00+00:00"}]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        with pytest.raises(ValidationError) as exc_info:
            apply_composition(
                quote_id="q-1",
                selection_map={"qi-1": "inv-a"},
                supabase=sb,
                user_id="user-1",
                quote_updated_at=None,
            )

        assert len(exc_info.value.errors) == 1
        # No writes to quote_items on failure
        assert query_by_table["quote_items"].update.call_count == 0

    def test_raises_concurrency_error_on_stale_updated_at(self):
        """Stale updated_at → ConcurrencyError, no writes."""
        iip_rows = [{"quote_item_id": "qi-1", "invoice_id": "inv-a"}]
        quote_row = [{"updated_at": "2026-04-10T13:00:00+00:00"}]  # newer

        query_by_table = {
            "invoice_item_prices": _chainable(iip_rows),
            "quote_items": _chainable([]),
            "quotes": _chainable(quote_row),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        with pytest.raises(ConcurrencyError):
            apply_composition(
                quote_id="q-1",
                selection_map={"qi-1": "inv-a"},
                supabase=sb,
                user_id="user-1",
                quote_updated_at="2026-04-10T12:00:00+00:00",  # stale
            )

        assert query_by_table["quote_items"].update.call_count == 0

    def test_skips_concurrency_check_when_no_updated_at_provided(self):
        """If caller passes quote_updated_at=None, skip concurrency check."""
        iip_rows = [{"quote_item_id": "qi-1", "invoice_id": "inv-a"}]

        query_by_table = {
            "invoice_item_prices": _chainable(iip_rows),
            "quote_items": _chainable([]),
            "quotes": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        # Should not raise
        apply_composition(
            quote_id="q-1",
            selection_map={"qi-1": "inv-a"},
            supabase=sb,
            user_id="user-1",
            quote_updated_at=None,
        )

        assert query_by_table["quote_items"].update.call_count == 1


# ============================================================================
# freeze_composition
# ============================================================================

class TestFreezeComposition:

    def test_stamps_frozen_at_on_active_iip_rows(self):
        """Unfrozen iip rows pointed to by quote_items get frozen."""
        items = [
            {"id": "qi-1", "composition_selected_invoice_id": "inv-a"},
            {"id": "qi-2", "composition_selected_invoice_id": "inv-b"},
        ]
        iip_rows = [
            {"id": "iip-1", "quote_item_id": "qi-1", "invoice_id": "inv-a", "frozen_at": None},
            {"id": "iip-2", "quote_item_id": "qi-2", "invoice_id": "inv-b", "frozen_at": None},
            {"id": "iip-3", "quote_item_id": "qi-1", "invoice_id": "inv-other", "frozen_at": None},  # not active
        ]

        query_by_table = {
            "quote_items": _chainable(items),
            "invoice_item_prices": _chainable(iip_rows),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        count = freeze_composition("q-1", "user-1", sb)

        # Only the 2 active rows should be frozen
        assert count == 2
        iip_update_calls = query_by_table["invoice_item_prices"].update.call_args_list
        assert len(iip_update_calls) == 2
        for call_ in iip_update_calls:
            payload = call_.args[0]
            assert "frozen_at" in payload
            assert payload["frozen_by"] == "user-1"

    def test_is_idempotent_skipping_already_frozen_rows(self):
        """Re-running freeze on already-frozen rows is a no-op."""
        items = [
            {"id": "qi-1", "composition_selected_invoice_id": "inv-a"},
        ]
        iip_rows = [
            {
                "id": "iip-1",
                "quote_item_id": "qi-1",
                "invoice_id": "inv-a",
                "frozen_at": "2026-04-10T12:00:00+00:00",  # already frozen
            },
        ]

        query_by_table = {
            "quote_items": _chainable(items),
            "invoice_item_prices": _chainable(iip_rows),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        count = freeze_composition("q-1", "user-1", sb)

        assert count == 0
        assert query_by_table["invoice_item_prices"].update.call_count == 0

    def test_returns_zero_when_no_composition_set(self):
        """Quote with no composition pointers → freeze is a no-op."""
        items = [
            {"id": "qi-1", "composition_selected_invoice_id": None},
        ]

        query_by_table = {
            "quote_items": _chainable(items),
            "invoice_item_prices": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        count = freeze_composition("q-1", "user-1", sb)
        assert count == 0


# ============================================================================
# get_composition_view (API shape)
# ============================================================================

class TestGetCompositionView:

    def test_returns_items_with_alternatives_grouped(self):
        """GET view groups alternatives per item and reports selection state."""
        items = [
            {
                "id": "qi-1",
                "brand": "B1",
                "idn_sku": "SKU-1",
                "name": "Item 1",
                "quantity": 5,
                "composition_selected_invoice_id": "inv-a",
            },
        ]
        iip_rows = [
            {
                "id": "iip-1",
                "quote_item_id": "qi-1",
                "invoice_id": "inv-a",
                "purchase_price_original": 50.00,
                "purchase_currency": "USD",
                "base_price_vat": 60.00,
                "price_includes_vat": False,
                "production_time_days": 30,
                "version": 1,
                "frozen_at": None,
            },
            {
                "id": "iip-2",
                "quote_item_id": "qi-1",
                "invoice_id": "inv-b",
                "purchase_price_original": 55.00,
                "purchase_currency": "EUR",
                "base_price_vat": 66.00,
                "price_includes_vat": True,
                "production_time_days": 45,
                "version": 1,
                "frozen_at": None,
            },
        ]
        invoices = [
            {"id": "inv-a", "supplier_id": "sup-1"},
            {"id": "inv-b", "supplier_id": "sup-2"},
        ]
        suppliers = [
            {"id": "sup-1", "name": "Supplier A", "country": "China"},
            {"id": "sup-2", "name": "Supplier B", "country": "Germany"},
        ]

        query_by_table = {
            "quote_items": _chainable(items),
            "invoice_item_prices": _chainable(iip_rows),
            "invoices": _chainable(invoices),
            "suppliers": _chainable(suppliers),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        view = get_composition_view("q-1", sb, user_id="user-1")

        assert view["quote_id"] == "q-1"
        assert len(view["items"]) == 1
        item = view["items"][0]
        assert item["quote_item_id"] == "qi-1"
        assert item["selected_invoice_id"] == "inv-a"
        assert len(item["alternatives"]) == 2
        # Alternatives should include supplier names
        alt_suppliers = {alt["supplier_name"] for alt in item["alternatives"]}
        assert alt_suppliers == {"Supplier A", "Supplier B"}
        assert view["composition_complete"] is True

    def test_composition_complete_false_when_any_item_unselected(self):
        """If any item has no selection, composition_complete is False."""
        items = [
            {"id": "qi-1", "name": "I1", "quantity": 1, "composition_selected_invoice_id": "inv-a"},
            {"id": "qi-2", "name": "I2", "quantity": 1, "composition_selected_invoice_id": None},
        ]
        iip_rows = [
            {
                "id": "iip-1",
                "quote_item_id": "qi-1",
                "invoice_id": "inv-a",
                "purchase_price_original": 50.00,
                "purchase_currency": "USD",
                "base_price_vat": 60.00,
                "price_includes_vat": False,
                "version": 1,
            }
        ]

        query_by_table = {
            "quote_items": _chainable(items),
            "invoice_item_prices": _chainable(iip_rows),
            "invoices": _chainable([{"id": "inv-a", "supplier_id": "sup-1"}]),
            "suppliers": _chainable([{"id": "sup-1", "name": "A", "country": "US"}]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: query_by_table[name]

        view = get_composition_view("q-1", sb)
        assert view["composition_complete"] is False


# ============================================================================
# Locked files invariant
# ============================================================================

class TestLockedFilesInvariant:

    def test_does_not_import_from_calculation_engine(self):
        """composition_service.py must not import from any locked calc file.

        Uses AST parsing so docstring mentions don't trigger false positives.
        """
        import ast

        service_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "services",
            "composition_service.py",
        )
        with open(service_path, "r") as f:
            source = f.read()

        tree = ast.parse(source)
        forbidden = {"calculation_engine", "calculation_models", "calculation_mapper"}

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                assert module not in forbidden, (
                    f"composition_service.py imports from locked module: {node.module}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in forbidden, (
                        f"composition_service.py imports locked module: {alias.name}"
                    )
