"""
Tests for Export Validation Service — Phase 5d Task 6.

Asserts that column mapping and item extraction references invoice_items
columns (weight_in_kg, base_price_vat), not legacy quote_items columns
(weight_kg, purchase_price_original).

Design contract: .kiro/specs/phase-5d-legacy-refactor/design.md §2.1.6
Requirement: REQ-1.5
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.export_validation_service import (  # noqa: E402
    PRODUCT_INPUT_COLUMNS,
    create_validation_excel,
)


# ============================================================================
# Column mapping tests — Pattern B — source is invoice_items
# ============================================================================


def test_column_mapping_references_invoice_items_weight_in_kg():
    """Column G maps to weight_in_kg — matches invoice_items.weight_in_kg."""
    field, display_name = PRODUCT_INPUT_COLUMNS["G"]
    assert field == "weight_in_kg", (
        f"Column G must map to invoice_items.weight_in_kg, got '{field}'"
    )


def test_column_mapping_references_invoice_items_base_price_vat():
    """Column K maps to base_price_vat — matches invoice_items.base_price_vat."""
    field, display_name = PRODUCT_INPUT_COLUMNS["K"]
    assert field == "base_price_vat", (
        f"Column K must map to invoice_items.base_price_vat, got '{field}'"
    )


# ============================================================================
# Item extraction tests — product_inputs dict is built from invoice_items
# ============================================================================


def _make_export_data(items):
    """Build a minimal ExportData-like object for create_validation_excel."""
    data = MagicMock()
    data.quote = {
        "id": "q-001",
        "quote_number": "Q-2026-0001",
        "currency": "USD",
    }
    data.items = items
    data.variables = {
        "markup": 15,
        "supplier_discount": 0,
    }
    data.calculations = {}
    return data


@patch("services.export_validation_service.ExportValidationService.generate_validation_export")
@patch("services.export_validation_service._get_exchange_rate_to_quote", return_value=1.0)
@patch("services.export_validation_service._get_usd_to_quote_rate", return_value=1.0)
def test_create_validation_excel_reads_weight_in_kg_from_item(
    mock_usd_rate, mock_exchange, mock_generate
):
    """Items built from invoice_items expose weight_in_kg, not legacy weight_kg."""
    mock_generate.return_value = b"XLSM"
    items = [
        {
            "id": "ii-001",
            "product_name": "Bearing",
            "brand": "SKF",
            "quantity": 10,
            "weight_in_kg": 2.5,  # invoice_items column
            "base_price_vat": 100.0,  # invoice_items column
            "purchase_currency": "EUR",
            "supplier_country": "DE",
            "customs_code": "12345",
            "calc": {},
        }
    ]
    data = _make_export_data(items)

    create_validation_excel(data)

    # The service.generate_validation_export was called with product_inputs
    # as the second positional argument.
    call_args = mock_generate.call_args
    product_inputs = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["product_inputs"]

    assert len(product_inputs) == 1
    assert product_inputs[0]["weight_in_kg"] == 2.5, (
        "weight_in_kg must be sourced from invoice_items.weight_in_kg"
    )


@patch("services.export_validation_service.ExportValidationService.generate_validation_export")
@patch("services.export_validation_service._get_exchange_rate_to_quote", return_value=1.0)
@patch("services.export_validation_service._get_usd_to_quote_rate", return_value=1.0)
def test_create_validation_excel_reads_base_price_vat_from_item(
    mock_usd_rate, mock_exchange, mock_generate
):
    """Items built from invoice_items expose base_price_vat directly."""
    mock_generate.return_value = b"XLSM"
    items = [
        {
            "id": "ii-001",
            "product_name": "Bearing",
            "brand": "SKF",
            "quantity": 10,
            "weight_in_kg": 2.5,
            "base_price_vat": 123.45,  # invoice_items column
            "purchase_currency": "EUR",
            "supplier_country": "DE",
            "customs_code": "12345",
            "calc": {},
        }
    ]
    data = _make_export_data(items)

    create_validation_excel(data)

    call_args = mock_generate.call_args
    product_inputs = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["product_inputs"]

    assert len(product_inputs) == 1
    assert product_inputs[0]["base_price_vat"] == 123.45, (
        "base_price_vat must be sourced from invoice_items.base_price_vat, "
        "not via legacy purchase_price_original fallback"
    )


@patch("services.export_validation_service.ExportValidationService.generate_validation_export")
@patch("services.export_validation_service._get_exchange_rate_to_quote", return_value=1.0)
@patch("services.export_validation_service._get_usd_to_quote_rate", return_value=1.0)
def test_create_validation_excel_ignores_legacy_weight_kg(
    mock_usd_rate, mock_exchange, mock_generate
):
    """Legacy weight_kg column must NOT be read; only invoice_items.weight_in_kg."""
    mock_generate.return_value = b"XLSM"
    items = [
        {
            "id": "ii-001",
            "product_name": "Bearing",
            "brand": "SKF",
            "quantity": 10,
            # Only new column populated — legacy weight_kg absent
            "weight_in_kg": 4.0,
            "base_price_vat": 50.0,
            "purchase_currency": "USD",
            "supplier_country": "CN",
            "customs_code": "67890",
            "calc": {},
        }
    ]
    data = _make_export_data(items)

    create_validation_excel(data)

    call_args = mock_generate.call_args
    product_inputs = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["product_inputs"]

    assert product_inputs[0]["weight_in_kg"] == 4.0


@patch("services.export_validation_service.ExportValidationService.generate_validation_export")
@patch("services.export_validation_service._get_exchange_rate_to_quote", return_value=1.0)
@patch("services.export_validation_service._get_usd_to_quote_rate", return_value=1.0)
def test_create_validation_excel_ignores_legacy_purchase_price_original(
    mock_usd_rate, mock_exchange, mock_generate
):
    """Legacy purchase_price_original must NOT be preferred over invoice_items.base_price_vat.

    If both present (stale legacy column + canonical new column), the new
    column wins. Guards against the old fallback chain
    `purchase_price_original, base_price_vat` that preferred legacy.
    """
    mock_generate.return_value = b"XLSM"
    items = [
        {
            "id": "ii-001",
            "product_name": "Bearing",
            "brand": "SKF",
            "quantity": 10,
            "weight_in_kg": 4.0,
            # Stale legacy value (what was in quote_items.purchase_price_original)
            "purchase_price_original": 999.0,
            # Canonical invoice_items value
            "base_price_vat": 200.0,
            "purchase_currency": "USD",
            "supplier_country": "CN",
            "customs_code": "67890",
            "calc": {},
        }
    ]
    data = _make_export_data(items)

    create_validation_excel(data)

    call_args = mock_generate.call_args
    product_inputs = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["product_inputs"]

    assert product_inputs[0]["base_price_vat"] == 200.0, (
        "base_price_vat must come from invoice_items.base_price_vat, "
        "not fall back through legacy purchase_price_original"
    )
