"""
TDD Tests for P2.2: IDN-SKU Validation at Spec Signing.

FEATURE: Before a specification can be signed (status -> "signed"), all quote_items
for the associated quote must have a non-null, non-empty idn_sku value.

Validation function: validate_quote_items_have_idn_sku(quote_id) in specification_service.py
- Returns (True, None) when all items have idn_sku
- Returns (False, error_message) listing positions missing idn_sku
- Empty quote (no items) passes validation

Integration points:
1. User path: /spec-control/{spec_id}/confirm-signature POST handler
2. Admin path: /spec-control/{spec_id} POST with action="admin_change_status" when new_status == "signed"

These tests are written BEFORE implementation (TDD).
All tests should FAIL until the feature is implemented.
"""

import pytest
import re
import os
import sys
from uuid import uuid4
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
SPEC_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "specification_service.py")


def _get_validate_function():
    """
    Try to import validate_quote_items_have_idn_sku.
    Returns the function or None if not yet implemented.
    """
    try:
        from services.specification_service import validate_quote_items_have_idn_sku
        return validate_quote_items_have_idn_sku
    except ImportError:
        return None


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


def _read_spec_service_source():
    """Read specification_service.py source code."""
    with open(SPEC_SERVICE_PY) as f:
        return f.read()


def _make_uuid():
    return str(uuid4())


# ============================================================================
# Test Data Factories
# ============================================================================

ORG_ID = _make_uuid()
QUOTE_ID = _make_uuid()


def make_quote_item(
    item_id=None,
    quote_id=None,
    idn_sku="SKU-001",
    product_name="Test Product",
    position=1,
):
    """Create a mock quote_item dict with idn_sku field."""
    return {
        "id": item_id or _make_uuid(),
        "quote_id": quote_id or QUOTE_ID,
        "idn_sku": idn_sku,
        "product_name": product_name,
        "position": position,
        "quantity": 10,
        "base_price": "100.00",
    }


# ============================================================================
# 1. Validation Function: validate_quote_items_have_idn_sku
# ============================================================================

class TestValidateQuoteItemsHaveIdnSku:
    """
    Tests for validate_quote_items_have_idn_sku(quote_id) function
    in services/specification_service.py.
    """

    def test_function_is_importable(self):
        """
        validate_quote_items_have_idn_sku should be importable from
        services.specification_service.
        """
        fn = _get_validate_function()
        assert fn is not None, (
            "validate_quote_items_have_idn_sku must be importable from "
            "services.specification_service (function not found)"
        )
        assert callable(fn)

    def test_function_exists_in_source(self):
        """
        The function definition must exist in specification_service.py.
        """
        source = _read_spec_service_source()
        assert "def validate_quote_items_have_idn_sku" in source, (
            "Function validate_quote_items_have_idn_sku must be defined in "
            "services/specification_service.py"
        )

    @patch('services.specification_service.get_supabase')
    def test_all_items_have_idn_sku_returns_true(self, mock_get_supabase):
        """
        When all quote_items have non-null, non-empty idn_sku,
        the function should return (True, None).
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        items = [
            make_quote_item(idn_sku="SKU-001", product_name="Product A", position=1),
            make_quote_item(idn_sku="SKU-002", product_name="Product B", position=2),
            make_quote_item(idn_sku="SKU-003", product_name="Product C", position=3),
        ]
        mock_response = MagicMock()
        mock_response.data = items
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        is_valid, error_msg = fn(QUOTE_ID)

        assert is_valid is True
        assert error_msg is None

    @patch('services.specification_service.get_supabase')
    def test_one_item_missing_idn_sku_returns_false(self, mock_get_supabase):
        """
        When one item has null idn_sku, the function should return
        (False, error_message) with that position listed.
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        items = [
            make_quote_item(idn_sku="SKU-001", product_name="Product A", position=1),
            make_quote_item(idn_sku=None, product_name="Product B Missing", position=2),
            make_quote_item(idn_sku="SKU-003", product_name="Product C", position=3),
        ]
        mock_response = MagicMock()
        mock_response.data = items
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        is_valid, error_msg = fn(QUOTE_ID)

        assert is_valid is False
        assert error_msg is not None
        assert "Product B Missing" in error_msg

    @patch('services.specification_service.get_supabase')
    def test_multiple_items_missing_idn_sku_lists_all(self, mock_get_supabase):
        """
        When multiple items are missing idn_sku, the error message
        should list ALL positions that are missing.
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        items = [
            make_quote_item(idn_sku=None, product_name="Missing Item A", position=1),
            make_quote_item(idn_sku="SKU-002", product_name="OK Item", position=2),
            make_quote_item(idn_sku=None, product_name="Missing Item C", position=3),
            make_quote_item(idn_sku=None, product_name="Missing Item D", position=4),
        ]
        mock_response = MagicMock()
        mock_response.data = items
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        is_valid, error_msg = fn(QUOTE_ID)

        assert is_valid is False
        assert error_msg is not None
        # All three missing items should be mentioned
        assert "Missing Item A" in error_msg
        assert "Missing Item C" in error_msg
        assert "Missing Item D" in error_msg

    @patch('services.specification_service.get_supabase')
    def test_empty_quote_no_items_passes_validation(self, mock_get_supabase):
        """
        A quote with zero items should pass validation: (True, None).
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        is_valid, error_msg = fn(QUOTE_ID)

        assert is_valid is True
        assert error_msg is None

    @patch('services.specification_service.get_supabase')
    def test_empty_string_idn_sku_treated_as_missing(self, mock_get_supabase):
        """
        An item with idn_sku="" (empty string) should be treated as missing.
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        items = [
            make_quote_item(idn_sku="", product_name="Empty SKU Item", position=1),
            make_quote_item(idn_sku="SKU-002", product_name="OK Item", position=2),
        ]
        mock_response = MagicMock()
        mock_response.data = items
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        is_valid, error_msg = fn(QUOTE_ID)

        assert is_valid is False
        assert "Empty SKU Item" in error_msg

    @patch('services.specification_service.get_supabase')
    def test_whitespace_only_idn_sku_treated_as_missing(self, mock_get_supabase):
        """
        An item with idn_sku="   " (whitespace only) should be treated as missing.
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        items = [
            make_quote_item(idn_sku="   ", product_name="Whitespace SKU Item", position=1),
        ]
        mock_response = MagicMock()
        mock_response.data = items
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        is_valid, error_msg = fn(QUOTE_ID)

        assert is_valid is False
        assert "Whitespace SKU Item" in error_msg

    @patch('services.specification_service.get_supabase')
    def test_long_product_name_truncated_in_error(self, mock_get_supabase):
        """
        When a product name is longer than 50 characters, it should be
        truncated in the error message (with "..." or similar).
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        long_name = "A" * 80  # 80 characters
        items = [
            make_quote_item(idn_sku=None, product_name=long_name, position=1),
        ]
        mock_response = MagicMock()
        mock_response.data = items
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        is_valid, error_msg = fn(QUOTE_ID)

        assert is_valid is False
        # The full 80-char name should NOT appear -- it should be truncated
        assert long_name not in error_msg
        # But the first 50 chars should appear
        assert long_name[:50] in error_msg

    @patch('services.specification_service.get_supabase')
    def test_return_type_is_tuple(self, mock_get_supabase):
        """
        The function must return a tuple of (bool, str_or_none).
        """
        fn = _get_validate_function()
        assert fn is not None, "validate_quote_items_have_idn_sku not yet implemented"

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [make_quote_item(idn_sku="SKU-001")]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = fn(QUOTE_ID)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)


# TestConfirmSignatureHandlerIntegration + TestAdminChangeStatusHandlerIntegration
# removed in Phase 6C-2B Mega-B — both classes searched main.py for the
# /spec-control/{spec_id}/confirm-signature and /spec-control/{spec_id}
# POST handlers, which were archived to legacy-fasthtml/control_flow.py.
# The live `services/specification_service.py.validate_quote_items_have_idn_sku`
# function is still covered by TestValidateQuoteItemsHaveIdnSku above and
# TestFunctionExport below.


# ============================================================================
# 4. Function exported from services/__init__.py
# ============================================================================

class TestFunctionExport:
    """Test that the validation function is properly exported."""

    def test_exported_from_services_init(self):
        """
        validate_quote_items_have_idn_sku should be importable from
        the services package (services/__init__.py).
        """
        import services
        fn = getattr(services, 'validate_quote_items_have_idn_sku', None)
        assert fn is not None, (
            "validate_quote_items_have_idn_sku must be exported from "
            "services/__init__.py (not found in services namespace)"
        )
        assert callable(fn)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
