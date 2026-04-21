"""
Tests for Phase 5c Task 6 — verify the calc entry points flow through the
rewritten composition_service.get_composed_items().

Originally 3 call sites in main.py (Phase 5c Task 6). After Phase 6B-6a
the /api/quotes/{id}/calculate handler moved to api/quotes.py, leaving 2
call sites in main.py plus 1 in api/quotes.py — total still 3 across the
codebase.

Current call sites:
  - main.py — POST /quotes/{quote_id}/preview (HTMX preview)
  - main.py — POST /quotes/{quote_id}/calculate (full calc run)
  - api/quotes.py — POST /api/quotes/{quote_id}/calculate (JSON API,
    extracted in Phase 6B-6a)

All three read ``items = get_composed_items(quote_id, supabase)`` and pass
that list directly into ``build_calculation_inputs(items, variables)``.

These tests verify:
  1. Each call site uses ``get_composed_items(quote_id, supabase)``
     literally — no bypass via direct ``quote_items`` SELECT.
  2. After migration 284 drops legacy quote_items pricing columns, the
     data observed at each call site comes from invoice_items (via
     coverage) — i.e. product_name/purchase_price/weight/customs_code
     come from the new schema, not from the soon-to-be-dropped quote_items
     columns.
  3. ``build_calculation_inputs`` consumes the composed list without error
     when it is shaped per the new schema.

The tests use AST inspection for (1) and a mock supabase client for (2,3).
They do NOT instantiate the full FastHTML route handlers — that requires
a full session+auth setup out of scope here. The seam we test is the
call-site → composition_service → build_calculation_inputs chain, which
is the integration point migration 284 can break.
"""

import ast
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MAIN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"
)
API_QUOTES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "api",
    "quotes.py",
)

# Call sites after Phase 6C-2B Mega-C (2026-04-20): 0 in main.py
# (preview + full-calc handlers archived to
# legacy-fasthtml/quote_detail_and_workflow.py) and 1 in api/quotes.py
# (the JSON API handler). build_calculation_inputs itself stays in
# main.py because api/quotes.py imports it directly. Total across the
# codebase is now 1 call site.
EXPECTED_CALL_SITES = 0
EXPECTED_API_QUOTES_CALL_SITES = 1


# ============================================================================
# (1) Static check: all 3 call sites use get_composed_items
# ============================================================================

def test_api_quotes_imports_get_composed_items():
    """After Phase 6C-2B Mega-C (2026-04-20) the main.py /quotes/{id}/calculate
    and /quotes/{id}/preview handlers were archived to
    legacy-fasthtml/quote_detail_and_workflow.py, removing both
    get_composed_items call sites from main.py. The remaining caller is
    the FastAPI handler in api/quotes.py, which this test now verifies.
    """
    with open(API_QUOTES_PATH, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "") == "services.composition_service":
                names = {alias.name for alias in node.names}
                if "get_composed_items" in names:
                    found = True
                    break
    assert found, (
        "api/quotes.py must import get_composed_items from "
        "services.composition_service"
    )


def test_api_quotes_calculate_uses_composed_items():
    """After Phase 6B-6a the JSON calc handler lives in api/quotes.py.

    The invariant from Phase 5c Task 6 still applies: every
    build_calculation_inputs call must be preceded by
    ``items = get_composed_items(...)`` so migration 284 (legacy
    quote_items column drop) doesn't break the calc flow.
    """
    with open(API_QUOTES_PATH, "r") as f:
        source = f.read()
    tree = ast.parse(source)

    bci_call_count = 0
    bci_sites_missing_composed: list[str] = []

    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        bci_nodes = []
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id == "build_calculation_inputs":
                    bci_nodes.append(node)

        if not bci_nodes:
            continue

        has_composed_items_assignment = False
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == "items":
                        value = node.value
                        if (
                            isinstance(value, ast.Call)
                            and isinstance(value.func, ast.Name)
                            and value.func.id == "get_composed_items"
                        ):
                            has_composed_items_assignment = True
                            break
            if has_composed_items_assignment:
                break

        bci_call_count += len(bci_nodes)
        if not has_composed_items_assignment:
            bci_sites_missing_composed.append(func.name)

    assert bci_call_count == EXPECTED_API_QUOTES_CALL_SITES, (
        f"Expected {EXPECTED_API_QUOTES_CALL_SITES} call site(s) to "
        f"build_calculation_inputs in api/quotes.py; found {bci_call_count}."
    )
    assert not bci_sites_missing_composed, (
        f"Found build_calculation_inputs call(s) without a preceding "
        f"items = get_composed_items(...) assignment in api/quotes.py: "
        f"{bci_sites_missing_composed}. Migration 284 will break these sites."
    )



# ============================================================================
# (2) Behavioural check: composed data round-trips through
#     build_calculation_inputs without legacy quote_items fields
# ============================================================================

@pytest.fixture
def new_schema_supabase():
    """Mock supabase returning invoice_items-shaped data through composition_service.

    Quote has 1 quote_item pointing to invoice inv-1 whose invoice_item
    carries the supplier-side pricing data. If build_calculation_inputs
    crashes or misses fields, it will surface here.
    """
    def rows(name):
        if name == "quote_items":
            # Customer-side only — legacy pricing columns ABSENT
            return [{
                "id": "qi-1",
                "quote_id": "q-1",
                "product_name": "Customer-Facing Name",
                "brand": "ACME",
                "quantity": 100,
                "composition_selected_invoice_id": "inv-1",
                "is_unavailable": False,
                "import_banned": False,
                "markup": 15,
                "supplier_discount": 0,
                "vat_rate": 20,
                # NOTE: no purchase_price_original, no weight_in_kg, etc.
            }]
        if name == "invoice_item_coverage":
            return [{
                "invoice_item_id": "ii-1",
                "quote_item_id": "qi-1",
                "ratio": 1,
                "invoice_items": {
                    "id": "ii-1",
                    "invoice_id": "inv-1",
                    "product_name": "Supplier Product Name",
                    "supplier_sku": "SUP-001",
                    "brand": "Bosch",
                    "quantity": 100,
                    "purchase_price_original": 50.0,
                    "purchase_currency": "EUR",
                    "base_price_vat": 60.0,
                    "price_includes_vat": False,
                    "vat_rate": 19,
                    "weight_in_kg": 0.25,
                    "customs_code": "7318154990",
                    "supplier_country": "Germany",
                    "production_time_days": 30,
                    "license_ds_cost": 0,
                    "license_ss_cost": 0,
                    "license_sgr_cost": 0,
                },
            }]
        return []

    def _table(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.in_.return_value = q
        q.is_.return_value = q
        q.order.return_value = q
        q.limit.return_value = q
        q.single.return_value = q
        result = MagicMock()
        result.data = rows(name)
        result.error = None
        q.execute.return_value = result
        return q

    sb = MagicMock()
    sb.table.side_effect = _table
    return sb


def test_get_composed_items_produces_invoice_items_shape(new_schema_supabase):
    """Round-trip check: composition_service returns invoice_items-style data."""
    from services.composition_service import get_composed_items

    items = get_composed_items("q-1", new_schema_supabase)
    assert len(items) == 1
    item = items[0]

    # Supplier-side fields come from invoice_items — not from quote_items
    assert item["product_name"] == "Supplier Product Name"
    assert item["supplier_sku"] == "SUP-001"
    assert item["purchase_price_original"] == 50.0
    assert item["purchase_currency"] == "EUR"
    assert item["weight_in_kg"] == 0.25
    assert item["customs_code"] == "7318154990"
    assert item["supplier_country"] == "Germany"
    assert item["production_time_days"] == 30

    # Customer-side fields come from quote_items
    assert item["markup"] == 15
    assert item["supplier_discount"] == 0
    assert item["is_unavailable"] is False
    assert item["import_banned"] is False
    assert item["vat_rate"] == 20


def test_build_calculation_inputs_accepts_composed_item_shape(
    new_schema_supabase,
):
    """The dict shape emitted by get_composed_items must satisfy
    build_calculation_inputs without touching legacy quote_items pricing columns.

    If migration 284 drops legacy columns on quote_items, items from the
    new schema must still have everything build_calculation_inputs reads.
    """
    from services.composition_service import get_composed_items

    items = get_composed_items("q-1", new_schema_supabase)

    # Minimum variables expected by build_calculation_inputs
    variables = {
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

    from services.calculation_helpers import build_calculation_inputs

    # Stub convert_amount since test env has no currency service.
    # ``calculation_helpers`` does ``from services.currency_service import
    # convert_amount`` lazily inside the function, so patching the source
    # module is sufficient.
    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        calc_inputs = build_calculation_inputs(items, variables)

    assert len(calc_inputs) == 1, (
        "build_calculation_inputs must emit a calc input for the composed item "
        "that carries invoice_items-style pricing data."
    )
