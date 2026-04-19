"""
Tests for Quote Version Service - Quote versioning during client_negotiation

Tests for WF-006: Quote versioning service
- Create immutable quote snapshots for audit trail
- List versions for a quote
- Get specific version details
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.quote_version_service import (
    create_quote_version,
    list_quote_versions,
    get_quote_version,
)


# =============================================================================
# CREATE VERSION TESTS
# =============================================================================

class TestCreateQuoteVersion:
    """Tests for create_quote_version function."""

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_create_version_first_version(self, mock_supabase, mock_composition_service):
        """First version should have version number 1."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_composition_service.get_composed_items.return_value = []

        # Mock empty existing versions
        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        # Mock insert response
        mock_insert = MagicMock()
        mock_insert.data = [{
            "id": "version-uuid",
            "quote_id": "quote-uuid",
            "version": 1,
            "status": "sent",
            "input_variables": {}
        }]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_insert

        # Mock quote update
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={"exchange_rate": 90.0},
            results=[],
            totals={"total_with_vat": 100000},
            change_reason="Initial version"
        )

        assert result is not None
        assert result["version"] == 1

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_create_version_increments_number(self, mock_supabase, mock_composition_service):
        """Version number should increment from existing versions."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_composition_service.get_composed_items.return_value = []

        # Mock existing version 3
        mock_existing = MagicMock()
        mock_existing.data = [{"version": 3}]
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "quote_id": "quote-uuid",
            "version": 4,
            "status": "sent"
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain

        # Mock quote update
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Updated pricing"
        )

        # Verify version was incremented
        insert_call = mock_client.table.return_value.insert.call_args
        assert insert_call[0][0]["version"] == 4

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_create_version_converts_decimals(self, mock_supabase, mock_composition_service):
        """Decimal values should be converted to float."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_composition_service.get_composed_items.return_value = []

        # Mock empty existing versions
        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1,
            "status": "sent"
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain

        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={
                "exchange_rate": Decimal("90.50"),
                "markup_percent": Decimal("15.0"),
            },
            results=[],
            totals={"total_with_vat": Decimal("150000.75")},
            change_reason="Test"
        )

        # Verify decimals converted
        insert_call = mock_client.table.return_value.insert.call_args
        input_vars = insert_call[0][0]["input_variables"]

        # Check variables converted
        assert isinstance(input_vars["variables"]["exchange_rate"], float)
        assert input_vars["variables"]["exchange_rate"] == 90.50

        # Check totals converted
        assert isinstance(input_vars["totals"]["total_with_vat"], float)

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_create_version_stores_products_snapshot(self, mock_supabase, mock_composition_service):
        """Product data should be snapshotted in input_variables, using composed shape."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1,
            "status": "sent"
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Composed shape (Phase 5d): items come from composition_service
        composed = [{
            "product_name": "Test Product",
            "supplier_sku": "TEST-001",
            "brand": "ACME",
            "quantity": 100,
            "purchase_price_original": 40.0,
            "purchase_currency": "USD",
            "base_price_vat": 50.0,
            "weight_in_kg": 2.5,
            "customs_code": None,
            "supplier_country": None,
            "quote_item_id": "qi-uuid",
            "invoice_item_id": "ii-uuid",
            "invoice_id": "inv-uuid",
            "coverage_ratio": 1,
        }]
        mock_composition_service.get_composed_items.return_value = composed

        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Test"
        )

        # Verify products snapshot
        insert_call = mock_client.table.return_value.insert.call_args
        input_vars = insert_call[0][0]["input_variables"]
        products = input_vars["products"]

        assert len(products) == 1
        assert products[0]["product_name"] == "Test Product"
        assert products[0]["supplier_sku"] == "TEST-001"
        assert products[0]["quantity"] == 100

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_create_version_stores_exchange_rate(self, mock_supabase, mock_composition_service):
        """Exchange rate info should be stored in input_variables."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_composition_service.get_composed_items.return_value = []

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={
                "exchange_rate": 92.5,
                "currency_of_base_price": "EUR",
                "currency_of_quote": "RUB",
            },
            results=[],
            totals={},
            change_reason="Currency update"
        )

        insert_call = mock_client.table.return_value.insert.call_args
        input_vars = insert_call[0][0]["input_variables"]
        exchange_rate = input_vars["exchange_rate"]

        assert exchange_rate["rate"] == 92.5
        assert exchange_rate["from_currency"] == "EUR"
        assert exchange_rate["to_currency"] == "RUB"


# =============================================================================
# LIST VERSIONS TESTS
# =============================================================================

class TestListQuoteVersions:
    """Tests for list_quote_versions function."""

    @patch('services.quote_version_service.get_supabase')
    def test_list_versions_returns_ordered(self, mock_supabase):
        """Versions should be returned in descending order."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock quote verification
        mock_quote = MagicMock()
        mock_quote.data = [{"id": "quote-uuid"}]

        # Mock versions query
        mock_versions = MagicMock()
        mock_versions.data = [
            {
                "id": "v3-uuid",
                "version": 3,
                "status": "sent",
                "input_variables": {"totals": {"total_with_vat": 150000}},
                "created_at": "2026-01-15T14:00:00Z",
            },
            {
                "id": "v2-uuid",
                "version": 2,
                "status": "sent",
                "input_variables": {"totals": {"total_with_vat": 140000}},
                "created_at": "2026-01-15T12:00:00Z",
            },
        ]

        # Setup mock chain
        def mock_table(table_name):
            if table_name == "quotes":
                chain = MagicMock()
                chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_quote
                return chain
            else:
                chain = MagicMock()
                chain.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_versions
                return chain

        mock_client.table.side_effect = mock_table

        result = list_quote_versions("quote-uuid", "org-uuid")

        assert len(result) == 2
        assert result[0]["version_number"] == 3
        assert result[1]["version_number"] == 2

    @patch('services.quote_version_service.get_supabase')
    def test_list_versions_empty_for_invalid_quote(self, mock_supabase):
        """Should return empty list for invalid quote."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock quote not found
        mock_quote = MagicMock()
        mock_quote.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_quote

        result = list_quote_versions("invalid-uuid", "org-uuid")

        assert result == []

    @patch('services.quote_version_service.get_supabase')
    def test_list_versions_transforms_data(self, mock_supabase):
        """Response should transform DB data for UI compatibility."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock quote verification
        mock_quote = MagicMock()
        mock_quote.data = [{"id": "quote-uuid"}]

        # Mock version data
        mock_versions = MagicMock()
        mock_versions.data = [{
            "id": "version-uuid",
            "version": 1,
            "status": "sent",
            "input_variables": {
                "totals": {"total_with_vat": 100000},
                "change_reason": "Initial quote"
            },
            "created_at": "2026-01-15T10:00:00Z",
            "seller_company": "ООО Квота",
            "offer_incoterms": "DDP",
        }]

        def mock_table(table_name):
            if table_name == "quotes":
                chain = MagicMock()
                chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_quote
                return chain
            else:
                chain = MagicMock()
                chain.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_versions
                return chain

        mock_client.table.side_effect = mock_table

        result = list_quote_versions("quote-uuid", "org-uuid")

        assert len(result) == 1
        version = result[0]
        assert version["version_number"] == 1
        assert version["total_quote_currency"] == 100000
        assert version["change_reason"] == "Initial quote"
        assert version["seller_company"] == "ООО Квота"


# =============================================================================
# GET VERSION TESTS
# =============================================================================

class TestGetQuoteVersion:
    """Tests for get_quote_version function."""

    @patch('services.quote_version_service.get_supabase')
    def test_get_version_returns_none_for_invalid_quote(self, mock_supabase):
        """Should return None if quote doesn't belong to org."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock quote not found
        mock_quote = MagicMock()
        mock_quote.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_quote

        result = get_quote_version("quote-uuid", 1, "wrong-org-uuid")

        assert result is None

    @patch('services.quote_version_service.get_supabase')
    def test_get_version_fetches_specific_version(self, mock_supabase):
        """Should fetch specific version by number."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock quote verification
        mock_quote = MagicMock()
        mock_quote.data = [{"id": "quote-uuid"}]

        # Mock version data - get_quote_version uses .execute() not .single().execute()
        mock_version = MagicMock()
        mock_version.data = [{
            "id": "version-uuid",
            "quote_id": "quote-uuid",
            "version": 2,
            "status": "sent",
            "input_variables": {
                "variables": {"exchange_rate": 90.0},
                "products": [],
                "results": [],
                "totals": {"total_with_vat": 200000}
            }
        }]

        def mock_table(table_name):
            if table_name == "quotes":
                chain = MagicMock()
                chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_quote
                return chain
            else:
                chain = MagicMock()
                chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_version
                return chain

        mock_client.table.side_effect = mock_table

        result = get_quote_version("quote-uuid", 2, "org-uuid")

        assert result is not None
        assert result["version_number"] == 2
        assert result["total_quote_currency"] == 200000


# =============================================================================
# IMPORT VERIFICATION TESTS
# =============================================================================

class TestImports:
    """Tests to verify all functions are importable."""

    def test_import_create_quote_version(self):
        """create_quote_version should be importable."""
        from services.quote_version_service import create_quote_version
        assert callable(create_quote_version)

    def test_import_list_quote_versions(self):
        """list_quote_versions should be importable."""
        from services.quote_version_service import list_quote_versions
        assert callable(list_quote_versions)

    def test_import_get_quote_version(self):
        """get_quote_version should be importable."""
        from services.quote_version_service import get_quote_version
        assert callable(get_quote_version)

    def test_exported_from_services_init(self):
        """Functions should be exported from services/__init__.py."""
        from services import (
            create_quote_version,
            list_quote_versions,
            get_quote_version
        )
        assert all(callable(f) for f in [
            create_quote_version,
            list_quote_versions,
            get_quote_version
        ])


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_create_version_handles_none_weight(self, mock_supabase, mock_composition_service):
        """Should handle None weight values in composed items."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        composed = [{
            "product_name": "Test",
            "supplier_sku": "TEST",
            "brand": None,
            "quantity": 1,
            "purchase_price_original": None,
            "purchase_currency": None,
            "base_price_vat": 100,
            "weight_in_kg": None,  # None weight
            "customs_code": None,
            "supplier_country": None,
            "quote_item_id": "qi-uuid",
            "invoice_item_id": None,
            "invoice_id": None,
            "coverage_ratio": None,
        }]
        mock_composition_service.get_composed_items.return_value = composed

        # Should not raise exception
        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Test"
        )

        # Verify weight is None in snapshot
        insert_call = mock_client.table.return_value.insert.call_args
        products = insert_call[0][0]["input_variables"]["products"]
        assert products[0]["weight_in_kg"] is None

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_create_version_with_empty_items(self, mock_supabase, mock_composition_service):
        """Should handle empty composition (no items in quote)."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_composition_service.get_composed_items.return_value = []

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Should not raise exception with empty composition
        result = create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Empty quote"
        )

        assert result is not None


# =============================================================================
# PHASE 5d — PATTERN A: snapshot sources composed items at snapshot time
# =============================================================================


class TestSnapshotSourcesComposedItems:
    """Phase 5d Task 7 — snapshot must source items from
    composition_service.get_composed_items() at snapshot creation time, NOT
    from legacy quote_items columns passed by the caller.

    See: .kiro/specs/phase-5d-legacy-refactor/design.md §2.1.7 + §1.1
         .kiro/specs/phase-5d-legacy-refactor/requirements.md REQ-1.6
    """

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_snapshot_input_variables_contain_composed_item_shape(
        self, mock_supabase, mock_composition_service
    ):
        """Snapshot products JSONB stores composed item shape, not legacy quote_items columns.

        Composed shape carries: product_name, supplier_sku, brand, quantity,
        purchase_price_original, purchase_currency, base_price_vat, weight_in_kg,
        customs_code, supplier_country, quote_item_id, invoice_item_id,
        invoice_id, coverage_ratio.
        """
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1,
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Composition service returns composed items (Phase 5c shape)
        composed_item = {
            "product_name": "Bolt M8",
            "supplier_sku": "SUP-BOLT-8",
            "brand": "ACME",
            "quantity": 100,
            "purchase_price_original": 2.5,
            "purchase_currency": "EUR",
            "base_price_vat": 3.0,
            "weight_in_kg": 0.05,
            "customs_code": "7318.15.20",
            "supplier_country": "DE",
            "quote_item_id": "qi-uuid",
            "invoice_item_id": "ii-uuid",
            "invoice_id": "inv-uuid",
            "coverage_ratio": 1,
        }
        mock_composition_service.get_composed_items.return_value = [composed_item]

        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Test composed shape",
        )

        insert_call = mock_client.table.return_value.insert.call_args
        input_vars = insert_call[0][0]["input_variables"]
        products = input_vars["products"]

        assert len(products) == 1
        snap = products[0]
        # Composed shape identity fields
        assert snap["product_name"] == "Bolt M8"
        assert snap["supplier_sku"] == "SUP-BOLT-8"
        assert snap["brand"] == "ACME"
        assert snap["quantity"] == 100
        # Composed pricing fields — purchase price must be from invoice_item
        assert snap["purchase_price_original"] == 2.5
        assert snap["purchase_currency"] == "EUR"
        assert snap["base_price_vat"] == 3.0
        # Composed supplier-side attrs
        assert snap["weight_in_kg"] == 0.05
        assert snap["customs_code"] == "7318.15.20"
        assert snap["supplier_country"] == "DE"
        # Traceability IDs — must be preserved for audit
        assert snap["quote_item_id"] == "qi-uuid"
        assert snap["invoice_item_id"] == "ii-uuid"
        assert snap["invoice_id"] == "inv-uuid"
        assert snap["coverage_ratio"] == 1

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_snapshot_sources_from_get_composed_items(
        self, mock_supabase, mock_composition_service
    ):
        """composition_service.get_composed_items must be called at snapshot time
        with (quote_id, supabase_client)."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1,
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        mock_composition_service.get_composed_items.return_value = []

        create_quote_version(
            quote_id="quote-uuid-xyz",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Spy on composition_service call",
        )

        mock_composition_service.get_composed_items.assert_called_once()
        call_args = mock_composition_service.get_composed_items.call_args
        # First positional arg = quote_id, second = supabase client
        assert call_args[0][0] == "quote-uuid-xyz"
        assert call_args[0][1] is mock_client

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_snapshot_of_split_quote_produces_multi_item_shape(
        self, mock_supabase, mock_composition_service
    ):
        """Split: 1 quote_item covered by 2 invoice_items → snapshot has 2 entries."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1,
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Split: same quote_item_id, two distinct invoice_item_ids
        split_items = [
            {
                "product_name": "Part A",
                "supplier_sku": "SUP-A",
                "brand": "ACME",
                "quantity": 60,
                "purchase_price_original": 1.0,
                "purchase_currency": "USD",
                "base_price_vat": 1.2,
                "weight_in_kg": 0.1,
                "customs_code": None,
                "supplier_country": "CN",
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-a",
                "invoice_id": "inv-1",
                "coverage_ratio": 0.6,
            },
            {
                "product_name": "Part B",
                "supplier_sku": "SUP-B",
                "brand": "ACME",
                "quantity": 40,
                "purchase_price_original": 2.0,
                "purchase_currency": "USD",
                "base_price_vat": 2.4,
                "weight_in_kg": 0.2,
                "customs_code": None,
                "supplier_country": "CN",
                "quote_item_id": "qi-1",
                "invoice_item_id": "ii-b",
                "invoice_id": "inv-1",
                "coverage_ratio": 0.4,
            },
        ]
        mock_composition_service.get_composed_items.return_value = split_items

        create_quote_version(
            quote_id="quote-split",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Split snapshot",
        )

        insert_call = mock_client.table.return_value.insert.call_args
        products = insert_call[0][0]["input_variables"]["products"]
        assert len(products) == 2
        # Both entries must share the quote_item_id (split semantics)
        assert {p["quote_item_id"] for p in products} == {"qi-1"}
        # Distinct invoice_item_ids (different supplier lines)
        assert {p["invoice_item_id"] for p in products} == {"ii-a", "ii-b"}

    @patch('services.quote_version_service.composition_service')
    @patch('services.quote_version_service.get_supabase')
    def test_snapshot_of_merged_quote_produces_single_item_shape(
        self, mock_supabase, mock_composition_service
    ):
        """Merge: 2 quote_items covered by 1 invoice_item → composed output
        has 1 entry (dedup), snapshot matches."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        mock_insert_chain = MagicMock()
        mock_insert_chain.execute.return_value = MagicMock(data=[{
            "id": "version-uuid",
            "version": 1,
        }])
        mock_client.table.return_value.insert.return_value = mock_insert_chain
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Merge: composition_service dedups — single invoice_item covering
        # multiple quote_items appears ONCE in get_composed_items output.
        merged_items = [
            {
                "product_name": "Kit",
                "supplier_sku": "KIT-1",
                "brand": "ACME",
                "quantity": 1,
                "purchase_price_original": 50.0,
                "purchase_currency": "USD",
                "base_price_vat": 60.0,
                "weight_in_kg": 5.0,
                "customs_code": "8481.80",
                "supplier_country": "IT",
                # First qi referenced (composition_service behavior)
                "quote_item_id": "qi-first",
                "invoice_item_id": "ii-merged",
                "invoice_id": "inv-1",
                "coverage_ratio": 1,
            },
        ]
        mock_composition_service.get_composed_items.return_value = merged_items

        create_quote_version(
            quote_id="quote-merge",
            user_id="user-uuid",
            variables={},
            results=[],
            totals={},
            change_reason="Merge snapshot",
        )

        insert_call = mock_client.table.return_value.insert.call_args
        products = insert_call[0][0]["input_variables"]["products"]
        # 1 snapshot entry aggregating the merged supplier line
        assert len(products) == 1
        assert products[0]["invoice_item_id"] == "ii-merged"
        # Price + supplier attrs must come from invoice_item (composed shape)
        assert products[0]["purchase_price_original"] == 50.0
        assert products[0]["weight_in_kg"] == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
