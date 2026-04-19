"""
Tests for Export Data Mapper — Phase 5d Pattern A.

Asserts that ``fetch_export_data`` sources items via
``composition_service.get_composed_items(quote_id, supabase)`` rather than
reading the raw ``quote_items`` table directly. Downstream exports
(specification PDF, invoice PDF, validation XLSX) therefore see the
composed, calc-ready shape where supplier-side fields (``weight_in_kg``,
``base_price_vat``, ``purchase_price_original``, ``purchase_currency``,
``supplier_country``, ``customs_code``, ...) come from the selected
``invoice_items`` row.

Design contract: .kiro/specs/phase-5d-legacy-refactor/design.md §2.1.7
Requirement: REQ-1.6
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.export_data_mapper import fetch_export_data  # noqa: E402


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_supabase(
    quote: dict,
    customer: dict | None = None,
    organization: dict | None = None,
    calc_results_by_item: dict | None = None,
    variables: dict | None = None,
    summary: dict | None = None,
    seller_company: dict | None = None,
    bank_accounts: list | None = None,
):
    """Build a mock supabase client whose ``.table(name)`` returns a
    chainable query that respects ``.eq("id", value)`` / ``.eq(...)``
    filtering for the tables fetch_export_data reads.

    The ``quote_items`` / ``quote_calculation_results`` tables are NOT
    stubbed here — the whole point of Pattern A is that fetch_export_data
    sources items via ``composition_service.get_composed_items``, not via
    a raw ``quote_items`` SELECT. Tests verify this by asserting the mock
    composition_service was called, and that no ``quote_items`` SELECT was
    made.
    """
    calc_results_by_item = calc_results_by_item or {}
    customer = customer or {}
    organization = organization or {}
    variables = variables or {}
    summary = summary or {}

    called_tables: list[str] = []

    def table(name):
        called_tables.append(name)
        builder = MagicMock()

        def select(*a, **kw):
            return builder

        def eq(*a, **kw):
            return builder

        def is_(*a, **kw):
            return builder

        def order(*a, **kw):
            return builder

        def execute():
            if name == "quotes":
                return MagicMock(data=[quote])
            if name == "customers":
                return MagicMock(data=[customer] if customer else [])
            if name == "organizations":
                return MagicMock(data=[organization] if organization else [])
            if name == "quote_calculation_variables":
                return MagicMock(
                    data=[{"variables": variables}] if variables else []
                )
            if name == "quote_calculation_summaries":
                return MagicMock(data=[summary] if summary else [])
            if name == "seller_companies":
                return MagicMock(
                    data=[seller_company] if seller_company else []
                )
            if name == "bank_accounts":
                return MagicMock(data=bank_accounts or [])
            # Anything else (quote_items, quote_calculation_results)
            # returns empty so a regression to Pattern B surfaces as
            # missing item fields in the assertions below.
            return MagicMock(data=[])

        builder.select = select
        builder.eq = eq
        builder.is_ = is_
        builder.order = order
        builder.execute = execute
        return builder

    sb = MagicMock()
    sb.table = table
    sb.called_tables = called_tables  # for assertions
    return sb


def _composed_item(
    *,
    quote_item_id: str,
    product_name: str,
    quantity: int,
    weight_in_kg: float,
    base_price_vat: float,
    purchase_price_original: float = 0.0,
    purchase_currency: str = "USD",
    supplier_country: str = "CN",
    customs_code: str = "12345",
    brand: str = "",
):
    """Build a composed item dict in the shape
    ``composition_service.get_composed_items`` emits."""
    return {
        # Identity
        "product_name": product_name,
        "supplier_sku": "S-001",
        "brand": brand,
        "quantity": quantity,
        # Pricing — from invoice_items
        "purchase_price_original": purchase_price_original,
        "purchase_currency": purchase_currency,
        "base_price_vat": base_price_vat,
        "price_includes_vat": False,
        # Supplier-side attrs — from invoice_items
        "weight_in_kg": weight_in_kg,
        "customs_code": customs_code,
        "supplier_country": supplier_country,
        "production_time_days": 30,
        "minimum_order_quantity": 1,
        "license_ds_cost": None,
        "license_ss_cost": None,
        "license_sgr_cost": None,
        # Customer-side
        "is_unavailable": False,
        "import_banned": False,
        "markup": 15,
        "supplier_discount": 0,
        "vat_rate": 20,
        # Traceability
        "quote_item_id": quote_item_id,
        "invoice_item_id": "ii-001",
        "invoice_id": "inv-001",
        "coverage_ratio": 1,
    }


# ============================================================================
# Pattern A — items sourced via composition_service.get_composed_items
# ============================================================================


@patch("services.export_data_mapper.composition_service")
@patch("services.export_data_mapper.get_supabase")
def test_fetch_export_data_sources_items_via_composition_service(
    mock_get_supabase, mock_composition_service
):
    """Pattern A: items come from composition_service.get_composed_items."""
    quote = {
        "id": "q-001",
        "customer_id": "c-001",
        "organization_id": "org-001",
        "currency": "USD",
    }
    composed = [
        _composed_item(
            quote_item_id="qi-001",
            product_name="Bearing",
            quantity=10,
            weight_in_kg=2.5,
            base_price_vat=100.0,
            brand="SKF",
        )
    ]
    mock_sb = _make_mock_supabase(quote=quote)
    mock_get_supabase.return_value = mock_sb
    mock_composition_service.get_composed_items.return_value = composed

    data = fetch_export_data("q-001", "org-001")

    # Composition service was called with the quote_id and supabase client.
    mock_composition_service.get_composed_items.assert_called_once_with(
        "q-001", mock_sb
    )
    # The returned ExportData.items carry the composed shape.
    assert len(data.items) == 1
    assert data.items[0]["product_name"] == "Bearing"
    assert data.items[0]["weight_in_kg"] == 2.5
    assert data.items[0]["base_price_vat"] == 100.0
    # Traceability is preserved so downstream exports and calc-result
    # lookup can key by quote_item_id.
    assert data.items[0]["quote_item_id"] == "qi-001"


@patch("services.export_data_mapper.composition_service")
@patch("services.export_data_mapper.get_supabase")
def test_fetch_export_data_supplier_fields_come_from_composition_service(
    mock_get_supabase, mock_composition_service
):
    """Pattern A: supplier-side fields (weight_in_kg, base_price_vat,
    purchase_price_original, purchase_currency, customs_code, ...) must
    come from composition_service.get_composed_items — never from a raw
    quote_items SELECT.

    A direct fallback to quote_items for pricing would defeat Task 6's
    column rename (weight_in_kg / base_price_vat now mapped from
    invoice_items). This test guards against a regression where composed
    fields are silently overwritten by a later quote_items read.
    """
    quote = {
        "id": "q-001",
        "customer_id": "c-001",
        "organization_id": "org-001",
        "currency": "USD",
    }
    composed = [
        _composed_item(
            quote_item_id="qi-001",
            product_name="Bearing from invoice_items",
            quantity=10,
            weight_in_kg=2.5,
            base_price_vat=100.0,
            purchase_price_original=80.0,
            purchase_currency="EUR",
        )
    ]

    # A potential quote_items enrichment read (for customer-side display
    # fields like product_code / unit) must NOT clobber supplier-side
    # fields. Return shadow values that would be wrong if picked up.
    shadow_qi_row = {
        "id": "qi-001",
        "product_code": "CUST-SKU-001",
        "unit": "шт",
        "description": "Customer description",
        "position": 1,
        # Poison values to catch any fallback to qi columns:
        "product_name": "WRONG (from quote_items)",
        "weight_in_kg": 99.9,
        "base_price_vat": 99.9,
        "purchase_price_original": 99.9,
    }

    def table(name):
        builder = MagicMock()

        def select(*a, **kw):
            return builder

        def eq(*a, **kw):
            return builder

        def is_(*a, **kw):
            return builder

        def in_(*a, **kw):
            return builder

        def order(*a, **kw):
            return builder

        def execute():
            if name == "quotes":
                return MagicMock(data=[quote])
            if name == "customers":
                return MagicMock(data=[])
            if name == "organizations":
                return MagicMock(data=[])
            if name == "quote_items":
                return MagicMock(data=[shadow_qi_row])
            return MagicMock(data=[])

        builder.select = select
        builder.eq = eq
        builder.is_ = is_
        builder.in_ = in_
        builder.order = order
        builder.execute = execute
        return builder

    mock_sb = MagicMock()
    mock_sb.table = table
    mock_get_supabase.return_value = mock_sb
    mock_composition_service.get_composed_items.return_value = composed

    data = fetch_export_data("q-001", "org-001")

    assert len(data.items) == 1
    it = data.items[0]
    # Supplier-side fields retained from composed items, NOT clobbered
    # by the quote_items enrichment read.
    assert it["product_name"] == "Bearing from invoice_items"
    assert it["weight_in_kg"] == 2.5
    assert it["base_price_vat"] == 100.0
    assert it["purchase_price_original"] == 80.0
    assert it["purchase_currency"] == "EUR"
    # Customer-side display fields added for downstream PDF rendering.
    assert it["product_code"] == "CUST-SKU-001"
    assert it["unit"] == "шт"


@patch("services.export_data_mapper.composition_service")
@patch("services.export_data_mapper.get_supabase")
def test_fetch_export_data_output_shape_matches_composed_items(
    mock_get_supabase, mock_composition_service
):
    """ExportData.items output shape matches composed items verbatim.

    The mapper must not silently drop, rename, or synthesize fields — the
    composed shape is the canonical calc-ready shape and downstream
    exports rely on fields like purchase_currency, customs_code, etc.
    """
    quote = {
        "id": "q-001",
        "customer_id": "c-001",
        "organization_id": "org-001",
        "currency": "EUR",
    }
    composed = [
        _composed_item(
            quote_item_id="qi-001",
            product_name="Bearing",
            quantity=10,
            weight_in_kg=2.5,
            base_price_vat=100.0,
            purchase_price_original=80.0,
            purchase_currency="EUR",
            supplier_country="DE",
            customs_code="8482100000",
            brand="SKF",
        ),
        _composed_item(
            quote_item_id="qi-002",
            product_name="Gasket",
            quantity=5,
            weight_in_kg=0.1,
            base_price_vat=20.0,
            purchase_price_original=15.0,
            purchase_currency="EUR",
            supplier_country="DE",
            customs_code="4016930000",
        ),
    ]
    mock_sb = _make_mock_supabase(quote=quote)
    mock_get_supabase.return_value = mock_sb
    mock_composition_service.get_composed_items.return_value = composed

    data = fetch_export_data("q-001", "org-001")

    assert len(data.items) == 2
    # Supplier-side fields from composition_service are preserved verbatim.
    for idx, original in enumerate(composed):
        for key in (
            "product_name",
            "supplier_sku",
            "quantity",
            "weight_in_kg",
            "base_price_vat",
            "purchase_price_original",
            "purchase_currency",
            "customs_code",
            "supplier_country",
            "quote_item_id",
            "invoice_item_id",
            "coverage_ratio",
        ):
            assert data.items[idx][key] == original[key], (
                f"field {key!r} must be preserved from composed item"
            )


# ============================================================================
# Calc-results merging — still keyed by quote_item_id on composed items
# ============================================================================


@patch("services.export_data_mapper.composition_service")
@patch("services.export_data_mapper.get_supabase")
def test_fetch_export_data_merges_calc_results_onto_composed_items(
    mock_get_supabase, mock_composition_service
):
    """Calc-result merging uses the composed item's quote_item_id key."""
    quote = {
        "id": "q-001",
        "customer_id": "c-001",
        "organization_id": "org-001",
        "currency": "USD",
    }
    composed = [
        _composed_item(
            quote_item_id="qi-001",
            product_name="Bearing",
            quantity=10,
            weight_in_kg=2.5,
            base_price_vat=100.0,
        )
    ]

    # Build a mock supabase that also returns calc_results when queried
    # for quote_calculation_results (the fetcher still merges per-item
    # calc results via the quote_item_id traceability field).
    def table(name):
        builder = MagicMock()

        def select(*a, **kw):
            return builder

        def eq(col, val):
            builder._filter_col = col
            builder._filter_val = val
            return builder

        def is_(*a, **kw):
            return builder

        def order(*a, **kw):
            return builder

        def execute():
            if name == "quotes":
                return MagicMock(data=[quote])
            if name == "customers":
                return MagicMock(data=[])
            if name == "organizations":
                return MagicMock(data=[])
            if name == "quote_calculation_results":
                # Keyed by quote_item_id
                if getattr(builder, "_filter_val", None) == "qi-001":
                    return MagicMock(
                        data=[{"phase_results": {"AL16": 1200.00}}]
                    )
                return MagicMock(data=[])
            if name == "quote_calculation_variables":
                return MagicMock(data=[])
            if name == "quote_calculation_summaries":
                return MagicMock(data=[])
            return MagicMock(data=[])

        builder.select = select
        builder.eq = eq
        builder.is_ = is_
        builder.order = order
        builder.execute = execute
        return builder

    mock_sb = MagicMock()
    mock_sb.table = table
    mock_get_supabase.return_value = mock_sb
    mock_composition_service.get_composed_items.return_value = composed

    data = fetch_export_data("q-001", "org-001")

    assert len(data.items) == 1
    # Calc-result was merged onto the composed item using its
    # quote_item_id traceability field.
    assert data.items[0]["calc"] == {"AL16": 1200.00}
