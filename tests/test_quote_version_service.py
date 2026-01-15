"""
Tests for Quote Version Service - Quote versioning during client_negotiation

Tests for WF-006: Quote versioning service
- Create immutable quote snapshots for audit trail
- List versions for a quote
- Get specific version details
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
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

    @patch('services.quote_version_service.get_supabase')
    def test_create_version_first_version(self, mock_supabase):
        """First version should have version number 1."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

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
            items=[],
            results=[],
            totals={"total_with_vat": 100000},
            change_reason="Initial version"
        )

        assert result is not None
        assert result["version"] == 1

    @patch('services.quote_version_service.get_supabase')
    def test_create_version_increments_number(self, mock_supabase):
        """Version number should increment from existing versions."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock existing version 3
        mock_existing = MagicMock()
        mock_existing.data = [{"version": 3}]
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        # Mock insert - capture the inserted data
        inserted_data = {}
        def capture_insert(data):
            nonlocal inserted_data
            inserted_data = data
            mock_result = MagicMock()
            mock_result.data = [{**data, "id": "version-uuid"}]
            return mock_result.execute.return_value

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

        result = create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            items=[],
            results=[],
            totals={},
            change_reason="Updated pricing"
        )

        # Verify version was incremented
        insert_call = mock_client.table.return_value.insert.call_args
        assert insert_call[0][0]["version"] == 4

    @patch('services.quote_version_service.get_supabase')
    def test_create_version_converts_decimals(self, mock_supabase):
        """Decimal values should be converted to float."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock empty existing versions
        mock_existing = MagicMock()
        mock_existing.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_existing

        # Capture inserted data
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
            items=[],
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

    @patch('services.quote_version_service.get_supabase')
    def test_create_version_stores_products_snapshot(self, mock_supabase):
        """Product data should be snapshotted in input_variables."""
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

        items = [{
            "id": "item-uuid",
            "product_name": "Test Product",
            "product_code": "TEST-001",
            "quantity": 100,
            "base_price_vat": 50.0,
            "weight_in_kg": 2.5,
        }]

        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            items=items,
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
        assert products[0]["product_code"] == "TEST-001"
        assert products[0]["quantity"] == 100

    @patch('services.quote_version_service.get_supabase')
    def test_create_version_stores_exchange_rate(self, mock_supabase):
        """Exchange rate info should be stored in input_variables."""
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

        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={
                "exchange_rate": 92.5,
                "currency_of_base_price": "EUR",
                "currency_of_quote": "RUB",
            },
            items=[],
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

    @patch('services.quote_version_service.get_supabase')
    def test_create_version_handles_none_weight(self, mock_supabase):
        """Should handle None weight values in items."""
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

        items = [{
            "id": "item-uuid",
            "product_name": "Test",
            "product_code": "TEST",
            "quantity": 1,
            "base_price_vat": 100,
            "weight_in_kg": None,  # None weight
        }]

        # Should not raise exception
        create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            items=items,
            results=[],
            totals={},
            change_reason="Test"
        )

        # Verify weight is None in snapshot
        insert_call = mock_client.table.return_value.insert.call_args
        products = insert_call[0][0]["input_variables"]["products"]
        assert products[0]["weight_in_kg"] is None

    @patch('services.quote_version_service.get_supabase')
    def test_create_version_with_empty_items(self, mock_supabase):
        """Should handle empty items list."""
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

        # Should not raise exception with empty items
        result = create_quote_version(
            quote_id="quote-uuid",
            user_id="user-uuid",
            variables={},
            items=[],
            results=[],
            totals={},
            change_reason="Empty quote"
        )

        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
