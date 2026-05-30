"""Tests for compute_effective_quantities (supplier-quantity override for exports).

Pure function: given quote_items + coverage rows (the _load_coverage_with_items
shape), returns {quote_item_id: effective qty}. The effective qty for a covered
quote_item is based on the SELECTED invoice_item's own quantity + MOQ — the SAME
base the calc engine uses (_build_calc_item) — so the displayed qty multiplies
out against the engine totals on the customer document. Uncovered / no-selection
items fall back to the ordered quote_item.quantity.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.composition_service import compute_effective_quantities  # noqa: E402


def _cov(quote_item_id, invoice_id, moq, ii_quantity, ii_id="ii"):
    """Build a coverage row in the _load_coverage_with_items shape."""
    return {
        "quote_item_id": quote_item_id,
        "ratio": 1,
        "invoice_items": {
            "id": ii_id,
            "invoice_id": invoice_id,
            "quantity": ii_quantity,
            "minimum_order_quantity": moq,
        },
    }


def test_override_up():
    qi = [{"id": "qi-1", "quantity": 32, "composition_selected_invoice_id": "inv-1"}]
    cov = [_cov("qi-1", "inv-1", moq=738, ii_quantity=32)]
    assert compute_effective_quantities(qi, cov) == {"qi-1": 738}


def test_override_down():
    qi = [{"id": "qi-1", "quantity": 20, "composition_selected_invoice_id": "inv-1"}]
    cov = [_cov("qi-1", "inv-1", moq=10, ii_quantity=20)]
    assert compute_effective_quantities(qi, cov) == {"qi-1": 10}


def test_moq_unset_uses_invoice_item_quantity():
    qi = [{"id": "qi-1", "quantity": 7, "composition_selected_invoice_id": "inv-1"}]
    cov = [_cov("qi-1", "inv-1", moq=None, ii_quantity=7)]
    assert compute_effective_quantities(qi, cov) == {"qi-1": 7}


def test_moq_zero_uses_invoice_item_quantity():
    qi = [{"id": "qi-1", "quantity": 7, "composition_selected_invoice_id": "inv-1"}]
    cov = [_cov("qi-1", "inv-1", moq=0, ii_quantity=7)]
    assert compute_effective_quantities(qi, cov) == {"qi-1": 7}


def test_moq_unset_engine_consistency_uses_ii_quantity_not_ordered():
    """Regression: when MOQ is unset and invoice_item.quantity differs from the
    ordered quote_item.quantity, the export must use invoice_item.quantity (the
    engine's base) so qty × per-unit = total holds on the legal document.
    """
    qi = [{"id": "qi-1", "quantity": 10, "composition_selected_invoice_id": "inv-1"}]
    cov = [_cov("qi-1", "inv-1", moq=None, ii_quantity=25)]
    # ii.quantity (25), NOT the ordered 10
    assert compute_effective_quantities(qi, cov) == {"qi-1": 25}


def test_no_composition_selected_uses_ordered():
    qi = [{"id": "qi-1", "quantity": 5, "composition_selected_invoice_id": None}]
    cov = [_cov("qi-1", "inv-1", moq=738, ii_quantity=99)]  # exists but not selected
    assert compute_effective_quantities(qi, cov) == {"qi-1": 5}


def test_selected_but_uncovered_uses_ordered():
    # quote_item points at inv-2, but the only coverage is for inv-1
    qi = [{"id": "qi-1", "quantity": 5, "composition_selected_invoice_id": "inv-2"}]
    cov = [_cov("qi-1", "inv-1", moq=738, ii_quantity=99)]
    assert compute_effective_quantities(qi, cov) == {"qi-1": 5}


def test_split_uses_first_covering_invoice_item():
    # 1 quote_item covered by 2 invoice_items in the selected invoice → first wins
    qi = [{"id": "qi-1", "quantity": 4, "composition_selected_invoice_id": "inv-1"}]
    cov = [
        _cov("qi-1", "inv-1", moq=None, ii_quantity=100, ii_id="ii-a"),
        _cov("qi-1", "inv-1", moq=None, ii_quantity=200, ii_id="ii-b"),
    ]
    assert compute_effective_quantities(qi, cov) == {"qi-1": 100}


def test_only_selected_invoice_item_counts_when_multiple_invoices():
    # qi covered in inv-1 and inv-2; selected = inv-2 → uses inv-2's invoice_item
    qi = [{"id": "qi-1", "quantity": 3, "composition_selected_invoice_id": "inv-2"}]
    cov = [
        _cov("qi-1", "inv-1", moq=None, ii_quantity=10, ii_id="ii-1"),
        _cov("qi-1", "inv-2", moq=999, ii_quantity=50, ii_id="ii-2"),
    ]
    assert compute_effective_quantities(qi, cov) == {"qi-1": 999}


def test_multiple_quote_items():
    qi = [
        {"id": "qi-1", "quantity": 20, "composition_selected_invoice_id": "inv-1"},
        {"id": "qi-2", "quantity": 5, "composition_selected_invoice_id": "inv-1"},
        {"id": "qi-3", "quantity": 8, "composition_selected_invoice_id": None},
    ]
    cov = [
        _cov("qi-1", "inv-1", moq=10, ii_quantity=20, ii_id="ii-1"),  # down → 10
        _cov("qi-2", "inv-1", moq=None, ii_quantity=5, ii_id="ii-2"),  # unset → ii.qty 5
    ]
    assert compute_effective_quantities(qi, cov) == {
        "qi-1": 10,
        "qi-2": 5,
        "qi-3": 8,
    }
