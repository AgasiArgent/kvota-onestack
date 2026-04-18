"""
Tests for Composition Service — Phase 5c.

Covers the invoice_items + invoice_item_coverage schema:
- get_composed_items: 1:1, split, merge, no composition, uncovered, swap,
  frozen rows, N+1 guard
- get_composition_view: alternatives grouped by invoice, coverage summary
  for 1:1 / split / merge
- apply_composition: validation-first, merge case (N quote_items updated
  for one invoice), concurrency check
- validate_composition: coverage existence check
- freeze_composition: walks coverage → invoice_items, merge dedup,
  idempotency
- Locked files: ensures composition_service does not import from the
  calc engine
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
    """Build a MagicMock that chains select/eq/in_/order/limit/single/is_ and
    terminates at execute() returning a result with .data=return_value."""
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.in_.return_value = q
    q.order.return_value = q
    q.limit.return_value = q
    q.single.return_value = q
    q.is_.return_value = q
    result = MagicMock()
    result.data = return_value
    result.error = None
    q.execute.return_value = result
    return q


def make_table_router(table_data):
    """Return a side_effect function that routes .table(name) to chainable
    mocks whose data comes from ``table_data`` (dict name -> rows OR callable
    that accepts the name and returns rows).
    """
    def _lookup(name):
        if callable(table_data):
            rows = table_data(name) or []
        else:
            rows = table_data.get(name, []) or []
        return _chainable(rows)

    return _lookup


# ============================================================================
# get_composed_items
# ============================================================================

class TestGetComposedItems1to1:
    """1:1 composition (legacy-equivalent)."""

    def test_single_qi_single_ii_ratio1_emits_one_calc_item(self):
        """1 quote_item → 1 invoice_item (ratio=1) → 1 calc item with
        invoice_item's supplier-side fields and quote_item's customer flags."""
        quote_id = "q-1"
        qi_id = "qi-1"
        inv_id = "inv-1"
        ii_id = "ii-1"

        def rows(name):
            if name == "quote_items":
                return [{
                    "id": qi_id,
                    "quote_id": quote_id,
                    "composition_selected_invoice_id": inv_id,
                    "product_name": "Bolt",
                    "brand": "ACME",
                    "quantity": 100,
                    "is_unavailable": False,
                    "import_banned": False,
                    "markup": 15,
                    "supplier_discount": 0,
                    "vat_rate": 20,
                }]
            if name == "invoice_item_coverage":
                return [{
                    "invoice_item_id": ii_id,
                    "quote_item_id": qi_id,
                    "ratio": 1,
                    "invoice_items": {
                        "id": ii_id,
                        "invoice_id": inv_id,
                        "product_name": "Bolt M8",
                        "supplier_sku": "SUP-BOLT-001",
                        "brand": "Bosch",
                        "quantity": 100,
                        "purchase_price_original": 50.00,
                        "purchase_currency": "EUR",
                        "base_price_vat": 60.00,
                        "price_includes_vat": False,
                        "weight_in_kg": 0.25,
                        "customs_code": "7318",
                        "supplier_country": "Germany",
                    },
                }]
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        result = get_composed_items(quote_id, sb)

        assert len(result) == 1
        row = result[0]
        # Supplier-side fields from invoice_item
        assert row["product_name"] == "Bolt M8"
        assert row["supplier_sku"] == "SUP-BOLT-001"
        assert row["quantity"] == 100
        assert row["purchase_price_original"] == 50.00
        assert row["purchase_currency"] == "EUR"
        assert row["weight_in_kg"] == 0.25
        assert row["customs_code"] == "7318"
        assert row["supplier_country"] == "Germany"
        # Customer-side fields from quote_item
        assert row["is_unavailable"] is False
        assert row["import_banned"] is False
        assert row["markup"] == 15
        assert row["supplier_discount"] == 0
        assert row["vat_rate"] == 20
        # Traceability
        assert row["quote_item_id"] == qi_id
        assert row["invoice_item_id"] == ii_id
        assert row["invoice_id"] == inv_id
        assert row["coverage_ratio"] == 1


class TestGetComposedItemsSplit:
    """Split composition: 1 quote_item → N invoice_items."""

    def test_one_qi_split_into_two_ii_emits_two_calc_items(self):
        """quote_item "fastener ×100" covered by invoice_items
        "bolt ×100" (ratio=1) + "washer ×200" (ratio=2) → 2 calc items."""
        quote_id = "q-1"
        qi_id = "qi-1"
        inv_id = "inv-1"

        def rows(name):
            if name == "quote_items":
                return [{
                    "id": qi_id,
                    "quote_id": quote_id,
                    "product_name": "Fastener",
                    "composition_selected_invoice_id": inv_id,
                    "quantity": 100,
                    "markup": 10,
                }]
            if name == "invoice_item_coverage":
                return [
                    {
                        "invoice_item_id": "ii-bolt",
                        "quote_item_id": qi_id,
                        "ratio": 1,
                        "invoice_items": {
                            "id": "ii-bolt",
                            "invoice_id": inv_id,
                            "product_name": "Bolt",
                            "quantity": 100,
                            "purchase_price_original": 5.0,
                            "purchase_currency": "EUR",
                        },
                    },
                    {
                        "invoice_item_id": "ii-washer",
                        "quote_item_id": qi_id,
                        "ratio": 2,
                        "invoice_items": {
                            "id": "ii-washer",
                            "invoice_id": inv_id,
                            "product_name": "Washer",
                            "quantity": 200,
                            "purchase_price_original": 1.0,
                            "purchase_currency": "EUR",
                        },
                    },
                ]
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        result = get_composed_items(quote_id, sb)

        assert len(result) == 2
        names = {r["product_name"] for r in result}
        assert names == {"Bolt", "Washer"}
        # Each calc item carries its own quantity (supplier-side)
        quantities_by_name = {r["product_name"]: r["quantity"] for r in result}
        assert quantities_by_name == {"Bolt": 100, "Washer": 200}
        # Each emitted calc item inherits markup from parent qi
        for r in result:
            assert r["markup"] == 10


class TestGetComposedItemsMerge:
    """Merge composition: N quote_items → 1 invoice_item."""

    def test_three_qi_merged_into_one_ii_emits_single_calc_item(self):
        """3 quote_items (bolt, nut, washer) all point to invoice inv-1
        whose single invoice_item "fastener kit" covers all three → calc
        engine receives ONE item (merged appears once)."""
        quote_id = "q-1"
        inv_id = "inv-1"
        ii_id = "ii-kit"

        def rows(name):
            if name == "quote_items":
                return [
                    {
                        "id": "qi-bolt",
                        "quote_id": quote_id,
                        "product_name": "Bolt",
                        "composition_selected_invoice_id": inv_id,
                        "quantity": 100,
                        "markup": 15,
                    },
                    {
                        "id": "qi-nut",
                        "quote_id": quote_id,
                        "product_name": "Nut",
                        "composition_selected_invoice_id": inv_id,
                        "quantity": 100,
                        "markup": 15,
                    },
                    {
                        "id": "qi-washer",
                        "quote_id": quote_id,
                        "product_name": "Washer",
                        "composition_selected_invoice_id": inv_id,
                        "quantity": 100,
                        "markup": 15,
                    },
                ]
            if name == "invoice_item_coverage":
                # 3 coverage rows all pointing to the SAME invoice_item
                merged_ii = {
                    "id": ii_id,
                    "invoice_id": inv_id,
                    "product_name": "Fastener Kit",
                    "quantity": 100,
                    "purchase_price_original": 12.0,
                    "purchase_currency": "EUR",
                }
                return [
                    {
                        "invoice_item_id": ii_id,
                        "quote_item_id": "qi-bolt",
                        "ratio": 1,
                        "invoice_items": merged_ii,
                    },
                    {
                        "invoice_item_id": ii_id,
                        "quote_item_id": "qi-nut",
                        "ratio": 1,
                        "invoice_items": merged_ii,
                    },
                    {
                        "invoice_item_id": ii_id,
                        "quote_item_id": "qi-washer",
                        "ratio": 1,
                        "invoice_items": merged_ii,
                    },
                ]
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        result = get_composed_items(quote_id, sb)

        # Merge: one calc item, not three
        assert len(result) == 1
        assert result[0]["product_name"] == "Fastener Kit"
        assert result[0]["invoice_item_id"] == ii_id


class TestGetComposedItemsNoComposition:
    """No composition selected — legacy fallback for pre-Phase-5c data."""

    def test_pointer_null_emits_legacy_shape_with_none_prices(self):
        """quote_item with NULL composition_selected_invoice_id → calc
        dict with None price fields (engine skips such items)."""
        quote_id = "q-1"

        def rows(name):
            if name == "quote_items":
                return [{
                    "id": "qi-1",
                    "quote_id": quote_id,
                    "composition_selected_invoice_id": None,
                    "product_name": "Uncomposed",
                    "quantity": 5,
                    "markup": 10,
                }]
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        result = get_composed_items(quote_id, sb)

        assert len(result) == 1
        row = result[0]
        assert row["purchase_price_original"] is None
        assert row["purchase_currency"] is None
        assert row["weight_in_kg"] is None
        # Customer-side still preserved
        assert row["product_name"] == "Uncomposed"
        assert row["markup"] == 10

    def test_no_pointers_skips_coverage_query(self):
        """When NO quote_item has a pointer, the coverage query is never
        issued — only a single quote_items read."""
        calls = []

        def rows(name):
            calls.append(name)
            if name == "quote_items":
                return [
                    {"id": "qi-1", "composition_selected_invoice_id": None, "quantity": 1},
                    {"id": "qi-2", "composition_selected_invoice_id": None, "quantity": 1},
                ]
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        get_composed_items("q-1", sb)

        assert calls == ["quote_items"]


class TestGetComposedItemsUncovered:
    """Pointer set but no coverage in the pointed invoice → skip."""

    def test_uncovered_quote_item_is_skipped(self):
        """qi-1 points to inv-missing but has no coverage row there — skip."""
        quote_id = "q-1"

        def rows(name):
            if name == "quote_items":
                return [
                    {
                        "id": "qi-1",
                        "quote_id": quote_id,
                        "composition_selected_invoice_id": "inv-missing",
                        "product_name": "Uncovered",
                        "quantity": 1,
                    },
                    {
                        "id": "qi-2",
                        "quote_id": quote_id,
                        "composition_selected_invoice_id": "inv-ok",
                        "product_name": "Covered",
                        "quantity": 1,
                    },
                ]
            if name == "invoice_item_coverage":
                return [{
                    "invoice_item_id": "ii-ok",
                    "quote_item_id": "qi-2",
                    "ratio": 1,
                    "invoice_items": {
                        "id": "ii-ok",
                        "invoice_id": "inv-ok",
                        "product_name": "Covered",
                        "quantity": 1,
                        "purchase_price_original": 10.0,
                        "purchase_currency": "USD",
                    },
                }]
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        result = get_composed_items(quote_id, sb)

        # Only qi-2 appears in output
        assert len(result) == 1
        assert result[0]["quote_item_id"] == "qi-2"


class TestGetComposedItemsSupplierSwap:
    """Multi-supplier swap: changing composition pointer swaps coverage."""

    def test_swapping_invoice_changes_output_shape(self):
        """Same qi has different structure per invoice:
         - invoice A = 1:1 (1 calc item)
         - invoice B = split into 2 (2 calc items).
        Switching the pointer must switch the output shape."""
        quote_id = "q-1"
        qi_id = "qi-1"

        coverage_rows = [
            # Invoice A: 1:1
            {
                "invoice_item_id": "ii-a",
                "quote_item_id": qi_id,
                "ratio": 1,
                "invoice_items": {
                    "id": "ii-a",
                    "invoice_id": "inv-a",
                    "product_name": "Bolt",
                    "quantity": 100,
                    "purchase_price_original": 10.0,
                    "purchase_currency": "EUR",
                },
            },
            # Invoice B: split into 2
            {
                "invoice_item_id": "ii-b1",
                "quote_item_id": qi_id,
                "ratio": 1,
                "invoice_items": {
                    "id": "ii-b1",
                    "invoice_id": "inv-b",
                    "product_name": "Bolt",
                    "quantity": 100,
                    "purchase_price_original": 8.0,
                    "purchase_currency": "EUR",
                },
            },
            {
                "invoice_item_id": "ii-b2",
                "quote_item_id": qi_id,
                "ratio": 2,
                "invoice_items": {
                    "id": "ii-b2",
                    "invoice_id": "inv-b",
                    "product_name": "Washer",
                    "quantity": 200,
                    "purchase_price_original": 1.0,
                    "purchase_currency": "EUR",
                },
            },
        ]

        def make_rows(pointer):
            def _rows(name):
                if name == "quote_items":
                    return [{
                        "id": qi_id,
                        "quote_id": quote_id,
                        "composition_selected_invoice_id": pointer,
                        "product_name": "Bolt",
                        "quantity": 100,
                    }]
                if name == "invoice_item_coverage":
                    return coverage_rows
                return []
            return _rows

        sb_a = MagicMock()
        sb_a.table.side_effect = make_table_router(make_rows("inv-a"))
        result_a = get_composed_items(quote_id, sb_a)
        assert len(result_a) == 1

        sb_b = MagicMock()
        sb_b.table.side_effect = make_table_router(make_rows("inv-b"))
        result_b = get_composed_items(quote_id, sb_b)
        assert len(result_b) == 2


class TestGetComposedItemsFrozenRows:
    """Frozen invoice_items remain visible to the calc pipeline."""

    def test_frozen_invoice_items_are_returned(self):
        """frozen_at NOT NULL does NOT hide the row — frozen means
        "committed history", calc must still see it for regen/preview."""
        quote_id = "q-1"

        def rows(name):
            if name == "quote_items":
                return [{
                    "id": "qi-1",
                    "quote_id": quote_id,
                    "composition_selected_invoice_id": "inv-1",
                    "product_name": "Bolt",
                    "quantity": 100,
                }]
            if name == "invoice_item_coverage":
                return [{
                    "invoice_item_id": "ii-frozen",
                    "quote_item_id": "qi-1",
                    "ratio": 1,
                    "invoice_items": {
                        "id": "ii-frozen",
                        "invoice_id": "inv-1",
                        "product_name": "Bolt",
                        "quantity": 100,
                        "purchase_price_original": 5.0,
                        "purchase_currency": "EUR",
                        "frozen_at": "2026-04-15T10:00:00+00:00",
                        "frozen_by": "user-1",
                    },
                }]
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        result = get_composed_items(quote_id, sb)

        assert len(result) == 1
        assert result[0]["product_name"] == "Bolt"


class TestGetComposedItemsQueryCount:
    """N+1 guard — queries must not scale with item count."""

    @pytest.mark.parametrize("n", [10, 50, 200])
    def test_at_most_two_table_reads_regardless_of_item_count(self, n):
        """For any number of items, only 2 .table() reads: quote_items +
        invoice_item_coverage. The engine-side invoice/supplier lookup is
        only in the view, not the calc path."""
        quote_id = "q-1"
        items = [
            {
                "id": f"qi-{i}",
                "quote_id": quote_id,
                "composition_selected_invoice_id": f"inv-{i % 3}",
                "product_name": f"Item {i}",
                "quantity": 1,
            }
            for i in range(n)
        ]

        def rows(name):
            if name == "quote_items":
                return items
            if name == "invoice_item_coverage":
                return []
            return []

        sb = MagicMock()
        sb.table.side_effect = make_table_router(rows)

        get_composed_items(quote_id, sb)

        table_calls = [c.args[0] for c in sb.table.call_args_list]
        assert table_calls.count("quote_items") == 1
        assert table_calls.count("invoice_item_coverage") == 1
        assert len(table_calls) == 2


# ============================================================================
# validate_composition
# ============================================================================

class TestValidateComposition:

    def test_happy_path_returns_valid(self):
        coverage_rows = [
            {
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-a",
                "ratio": 1,
                "invoice_items": {"id": "ii-a", "invoice_id": "inv-a"},
            },
            {
                "quote_item_id": "qi-2",
                "invoice_item_id": "ii-b",
                "ratio": 1,
                "invoice_items": {"id": "ii-b", "invoice_id": "inv-b"},
            },
        ]
        sb = MagicMock()
        sb.table.side_effect = make_table_router({"invoice_item_coverage": coverage_rows})

        result = validate_composition("q-1", {"qi-1": "inv-a", "qi-2": "inv-b"}, sb)
        assert result.valid is True
        assert result.errors == []

    def test_rejects_pair_with_no_coverage_row(self):
        coverage_rows = [
            {
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-a",
                "ratio": 1,
                "invoice_items": {"id": "ii-a", "invoice_id": "inv-a"},
            },
        ]
        sb = MagicMock()
        sb.table.side_effect = make_table_router({"invoice_item_coverage": coverage_rows})

        result = validate_composition(
            "q-1", {"qi-1": "inv-a", "qi-2": "inv-nonexistent"}, sb
        )
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0]["quote_item_id"] == "qi-2"
        assert result.errors[0]["invoice_id"] == "inv-nonexistent"

    def test_empty_selection_is_valid(self):
        sb = MagicMock()
        result = validate_composition("q-1", {}, sb)
        assert result.valid is True


# ============================================================================
# apply_composition
# ============================================================================

class TestApplyComposition:

    def test_updates_pointer_on_happy_path(self):
        coverage_rows = [{
            "quote_item_id": "qi-1",
            "invoice_item_id": "ii-a",
            "ratio": 1,
            "invoice_items": {"id": "ii-a", "invoice_id": "inv-a"},
        }]
        quote_rows = [{"updated_at": "2026-04-10T12:00:00+00:00"}]

        tables = {
            "invoice_item_coverage": _chainable(coverage_rows),
            "quote_items": _chainable([]),
            "quotes": _chainable(quote_rows),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        apply_composition(
            quote_id="q-1",
            selection_map={"qi-1": "inv-a"},
            supabase=sb,
            user_id="user-1",
            quote_updated_at="2026-04-10T12:00:00+00:00",
        )

        qi_update_calls = tables["quote_items"].update.call_args_list
        assert len(qi_update_calls) == 1
        assert qi_update_calls[0].args[0] == {"composition_selected_invoice_id": "inv-a"}
        assert len(tables["quotes"].update.call_args_list) == 1

    def test_raises_validation_error_when_coverage_missing(self):
        """ValidationError when (qi, inv) pair has no coverage row."""
        tables = {
            "invoice_item_coverage": _chainable([]),
            "quote_items": _chainable([]),
            "quotes": _chainable([{"updated_at": "2026-04-10T12:00:00+00:00"}]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        with pytest.raises(ValidationError) as exc_info:
            apply_composition(
                quote_id="q-1",
                selection_map={"qi-1": "inv-a"},
                supabase=sb,
                user_id="user-1",
                quote_updated_at=None,
            )

        assert len(exc_info.value.errors) == 1
        assert tables["quote_items"].update.call_count == 0

    def test_raises_concurrency_error_on_stale_updated_at(self):
        """ConcurrencyError when quote_updated_at mismatches."""
        coverage_rows = [{
            "quote_item_id": "qi-1",
            "invoice_item_id": "ii-a",
            "ratio": 1,
            "invoice_items": {"id": "ii-a", "invoice_id": "inv-a"},
        }]
        quote_rows = [{"updated_at": "2026-04-10T13:00:00+00:00"}]  # newer

        tables = {
            "invoice_item_coverage": _chainable(coverage_rows),
            "quote_items": _chainable([]),
            "quotes": _chainable(quote_rows),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        with pytest.raises(ConcurrencyError):
            apply_composition(
                quote_id="q-1",
                selection_map={"qi-1": "inv-a"},
                supabase=sb,
                user_id="user-1",
                quote_updated_at="2026-04-10T12:00:00+00:00",
            )

        assert tables["quote_items"].update.call_count == 0

    def test_merge_case_updates_all_covered_quote_items(self):
        """Picker submits N entries with the same invoice_id for a merged
        invoice → apply_composition updates composition_selected_invoice_id
        on every covered quote_item in one pass."""
        inv_id = "inv-1"
        coverage_rows = [
            {
                "quote_item_id": "qi-bolt",
                "invoice_item_id": "ii-kit",
                "ratio": 1,
                "invoice_items": {"id": "ii-kit", "invoice_id": inv_id},
            },
            {
                "quote_item_id": "qi-nut",
                "invoice_item_id": "ii-kit",
                "ratio": 1,
                "invoice_items": {"id": "ii-kit", "invoice_id": inv_id},
            },
            {
                "quote_item_id": "qi-washer",
                "invoice_item_id": "ii-kit",
                "ratio": 1,
                "invoice_items": {"id": "ii-kit", "invoice_id": inv_id},
            },
        ]

        tables = {
            "invoice_item_coverage": _chainable(coverage_rows),
            "quote_items": _chainable([]),
            "quotes": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        apply_composition(
            quote_id="q-1",
            selection_map={
                "qi-bolt": inv_id,
                "qi-nut": inv_id,
                "qi-washer": inv_id,
            },
            supabase=sb,
            user_id="user-1",
            quote_updated_at=None,
        )

        # Three separate UPDATE calls, each setting the pointer to inv_id
        qi_update_calls = tables["quote_items"].update.call_args_list
        assert len(qi_update_calls) == 3
        for call_ in qi_update_calls:
            assert call_.args[0] == {"composition_selected_invoice_id": inv_id}


# ============================================================================
# freeze_composition
# ============================================================================

class TestFreezeComposition:

    def test_freezes_invoice_items_in_active_coverage(self):
        """Only invoice_items whose invoice matches the qi pointer get
        frozen_at stamped."""
        items = [
            {"id": "qi-1", "composition_selected_invoice_id": "inv-a"},
            {"id": "qi-2", "composition_selected_invoice_id": "inv-b"},
        ]
        coverage_rows = [
            {
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-a",
                "ratio": 1,
                "invoice_items": {
                    "id": "ii-a",
                    "invoice_id": "inv-a",
                    "frozen_at": None,
                },
            },
            {
                "quote_item_id": "qi-2",
                "invoice_item_id": "ii-b",
                "ratio": 1,
                "invoice_items": {
                    "id": "ii-b",
                    "invoice_id": "inv-b",
                    "frozen_at": None,
                },
            },
            # Coverage for qi-1 in a different invoice — not active, skip
            {
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-other",
                "ratio": 1,
                "invoice_items": {
                    "id": "ii-other",
                    "invoice_id": "inv-other",
                    "frozen_at": None,
                },
            },
        ]

        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
            "invoice_items": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        count = freeze_composition("q-1", "user-1", sb)

        # 2 active invoice_items frozen (ii-a and ii-b), ii-other skipped
        assert count == 2
        ii_update_calls = tables["invoice_items"].update.call_args_list
        assert len(ii_update_calls) == 2
        for call_ in ii_update_calls:
            payload = call_.args[0]
            assert "frozen_at" in payload
            assert payload["frozen_by"] == "user-1"

    def test_idempotent_skipping_already_frozen(self):
        items = [{"id": "qi-1", "composition_selected_invoice_id": "inv-a"}]
        coverage_rows = [{
            "quote_item_id": "qi-1",
            "invoice_item_id": "ii-a",
            "ratio": 1,
            "invoice_items": {
                "id": "ii-a",
                "invoice_id": "inv-a",
                "frozen_at": "2026-04-10T12:00:00+00:00",
            },
        }]

        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
            "invoice_items": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        count = freeze_composition("q-1", "user-1", sb)
        assert count == 0
        assert tables["invoice_items"].update.call_count == 0

    def test_merge_freezes_invoice_item_once(self):
        """A merged invoice_item is reached from multiple qi — freeze once."""
        items = [
            {"id": "qi-1", "composition_selected_invoice_id": "inv-a"},
            {"id": "qi-2", "composition_selected_invoice_id": "inv-a"},
            {"id": "qi-3", "composition_selected_invoice_id": "inv-a"},
        ]
        merged_ii = {
            "id": "ii-kit",
            "invoice_id": "inv-a",
            "frozen_at": None,
        }
        coverage_rows = [
            {
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-kit",
                "ratio": 1,
                "invoice_items": merged_ii,
            },
            {
                "quote_item_id": "qi-2",
                "invoice_item_id": "ii-kit",
                "ratio": 1,
                "invoice_items": merged_ii,
            },
            {
                "quote_item_id": "qi-3",
                "invoice_item_id": "ii-kit",
                "ratio": 1,
                "invoice_items": merged_ii,
            },
        ]

        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
            "invoice_items": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        count = freeze_composition("q-1", "user-1", sb)
        assert count == 1
        assert tables["invoice_items"].update.call_count == 1

    def test_returns_zero_when_no_composition_set(self):
        items = [{"id": "qi-1", "composition_selected_invoice_id": None}]
        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable([]),
            "invoice_items": _chainable([]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        count = freeze_composition("q-1", "user-1", sb)
        assert count == 0


# ============================================================================
# get_composition_view
# ============================================================================

class TestGetCompositionView:

    def test_alternatives_grouped_by_invoice_1to1(self):
        """1:1 alternative has empty coverage_summary."""
        items = [{
            "id": "qi-1",
            "brand": "ACME",
            "idn_sku": "SKU-1",
            "product_name": "Bolt",
            "quantity": 100,
            "composition_selected_invoice_id": "inv-a",
        }]
        coverage_rows = [{
            "quote_item_id": "qi-1",
            "invoice_item_id": "ii-a",
            "ratio": 1,
            "invoice_items": {
                "id": "ii-a",
                "invoice_id": "inv-a",
                "product_name": "Bolt M8",
                "purchase_price_original": 10.0,
                "purchase_currency": "EUR",
            },
        }]
        invoices = [{"id": "inv-a", "supplier_id": "sup-1"}]
        suppliers = [{"id": "sup-1", "name": "Supplier A", "country": "Germany"}]

        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
            "invoices": _chainable(invoices),
            "suppliers": _chainable(suppliers),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        view = get_composition_view("q-1", sb)

        assert view["quote_id"] == "q-1"
        assert len(view["items"]) == 1
        item = view["items"][0]
        assert len(item["alternatives"]) == 1
        alt = item["alternatives"][0]
        assert alt["invoice_id"] == "inv-a"
        assert alt["supplier_name"] == "Supplier A"
        assert alt["coverage_summary"] == ""  # 1:1 → empty

    def test_split_alternative_shows_coverage_summary(self):
        """Split: one invoice has 2 invoice_items for 1 quote_item →
        coverage_summary contains both names with ratios."""
        items = [{
            "id": "qi-1",
            "product_name": "Fastener",
            "quantity": 100,
            "composition_selected_invoice_id": None,
        }]
        coverage_rows = [
            {
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-bolt",
                "ratio": 1,
                "invoice_items": {
                    "id": "ii-bolt",
                    "invoice_id": "inv-split",
                    "product_name": "Bolt",
                    "quantity": 100,
                    "purchase_price_original": 5.0,
                    "purchase_currency": "EUR",
                },
            },
            {
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-washer",
                "ratio": 2,
                "invoice_items": {
                    "id": "ii-washer",
                    "invoice_id": "inv-split",
                    "product_name": "Washer",
                    "quantity": 200,
                    "purchase_price_original": 1.0,
                    "purchase_currency": "EUR",
                },
            },
        ]
        invoices = [{"id": "inv-split", "supplier_id": "sup-1"}]
        suppliers = [{"id": "sup-1", "name": "Supplier A", "country": "Germany"}]

        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
            "invoices": _chainable(invoices),
            "suppliers": _chainable(suppliers),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        view = get_composition_view("q-1", sb)

        assert len(view["items"]) == 1
        alts = view["items"][0]["alternatives"]
        # Only ONE alternative per invoice, even for a split
        assert len(alts) == 1
        alt = alts[0]
        assert alt["invoice_id"] == "inv-split"
        summary = alt["coverage_summary"]
        assert summary.startswith("→ ")
        assert "Bolt" in summary and "Washer" in summary
        assert "×1" in summary and "×2" in summary

    def test_merge_alternative_shows_coverage_summary(self):
        """Merge: same invoice_item covers 3 qi → alternative appears
        on each qi with coverage_summary listing the merged sibling names."""
        items = [
            {"id": "qi-bolt", "product_name": "Bolt", "quantity": 100,
             "composition_selected_invoice_id": None},
            {"id": "qi-nut", "product_name": "Nut", "quantity": 100,
             "composition_selected_invoice_id": None},
            {"id": "qi-washer", "product_name": "Washer", "quantity": 100,
             "composition_selected_invoice_id": None},
        ]
        merged_ii = {
            "id": "ii-kit",
            "invoice_id": "inv-merge",
            "product_name": "Fastener Kit",
            "quantity": 100,
            "purchase_price_original": 12.0,
            "purchase_currency": "EUR",
        }
        coverage_rows = [
            {"quote_item_id": "qi-bolt", "invoice_item_id": "ii-kit",
             "ratio": 1, "invoice_items": merged_ii},
            {"quote_item_id": "qi-nut", "invoice_item_id": "ii-kit",
             "ratio": 1, "invoice_items": merged_ii},
            {"quote_item_id": "qi-washer", "invoice_item_id": "ii-kit",
             "ratio": 1, "invoice_items": merged_ii},
        ]
        invoices = [{"id": "inv-merge", "supplier_id": "sup-1"}]
        suppliers = [{"id": "sup-1", "name": "Supplier A", "country": "Germany"}]

        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
            "invoices": _chainable(invoices),
            "suppliers": _chainable(suppliers),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

        view = get_composition_view("q-1", sb)

        assert len(view["items"]) == 3
        # Each qi has exactly ONE alternative (merge case — one invoice)
        for vi in view["items"]:
            assert len(vi["alternatives"]) == 1
            summary = vi["alternatives"][0]["coverage_summary"]
            assert summary.startswith("← ")
            # Should mention all three covered product_names
            assert "Bolt" in summary
            assert "Nut" in summary
            assert "Washer" in summary

    def test_composition_complete_false_when_any_item_unselected(self):
        items = [
            {"id": "qi-1", "product_name": "I1", "quantity": 1,
             "composition_selected_invoice_id": "inv-a"},
            {"id": "qi-2", "product_name": "I2", "quantity": 1,
             "composition_selected_invoice_id": None},
        ]
        coverage_rows = [{
            "quote_item_id": "qi-1",
            "invoice_item_id": "ii-a",
            "ratio": 1,
            "invoice_items": {
                "id": "ii-a",
                "invoice_id": "inv-a",
                "product_name": "I1",
                "purchase_price_original": 10.0,
                "purchase_currency": "USD",
            },
        }]
        tables = {
            "quote_items": _chainable(items),
            "invoice_item_coverage": _chainable(coverage_rows),
            "invoices": _chainable([{"id": "inv-a", "supplier_id": "sup-1"}]),
            "suppliers": _chainable([{"id": "sup-1", "name": "A", "country": "US"}]),
        }
        sb = MagicMock()
        sb.table.side_effect = lambda name: tables[name]

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
