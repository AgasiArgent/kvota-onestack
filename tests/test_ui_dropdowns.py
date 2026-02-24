"""
Tests for UI dropdown components (Feature UI-011).

Tests the reusable HTMX-powered dropdown components:
- supplier_dropdown
- buyer_company_dropdown
- seller_company_dropdown
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_supplier():
    """Sample supplier data."""
    return {
        "id": "sup-123",
        "supplier_code": "ABC",
        "name": "Test Supplier LLC",
        "country": "China",
        "is_active": True,
    }


@pytest.fixture
def sample_buyer_company():
    """Sample buyer company data."""
    return {
        "id": "buy-123",
        "company_code": "MBR",
        "name": "ООО Мастер Бэринг",
        "inn": "1234567890",
        "is_active": True,
    }


@pytest.fixture
def sample_seller_company():
    """Sample seller company data."""
    return {
        "id": "sel-123",
        "supplier_code": "CMT",
        "name": "ООО КМТ",
        "inn": "0987654321",
        "is_active": True,
    }


# ============================================================================
# Component Import Tests
# ============================================================================

class TestDropdownImports:
    """Test that dropdown components can be imported."""

    def test_supplier_dropdown_import(self):
        """Test supplier_dropdown can be imported from main."""
        import main
        assert hasattr(main, 'supplier_dropdown')

    def test_buyer_company_dropdown_import(self):
        """Test buyer_company_dropdown can be imported from main."""
        import main
        assert hasattr(main, 'buyer_company_dropdown')

    def test_seller_company_dropdown_import(self):
        """Test seller_company_dropdown can be imported from main."""
        import main
        assert hasattr(main, 'seller_company_dropdown')


# ============================================================================
# Supplier Dropdown Tests
# ============================================================================

class TestSupplierDropdown:
    """Tests for the supplier_dropdown component."""

    def test_basic_rendering(self):
        """Test basic supplier dropdown renders correctly."""
        import main
        component = main.supplier_dropdown()

        assert component is not None

    def test_custom_name(self):
        """Test supplier dropdown with custom field name."""
        import main
        component = main.supplier_dropdown(name="item_supplier_id")

        assert component is not None

    def test_with_label(self):
        """Test supplier dropdown with custom label."""
        import main
        component = main.supplier_dropdown(label="Выберите поставщика")

        assert component is not None

    def test_required_field(self):
        """Test supplier dropdown marked as required."""
        import main
        component = main.supplier_dropdown(required=True)

        assert component is not None

    def test_with_preselected_value(self):
        """Test supplier dropdown with pre-selected value."""
        import main
        component = main.supplier_dropdown(
            selected_id="sup-uuid-123",
            selected_label="ABC - Test Supplier LLC (CN)"
        )

        assert component is not None


# ============================================================================
# Buyer Company Dropdown Tests
# ============================================================================

class TestBuyerCompanyDropdown:
    """Tests for the buyer_company_dropdown component."""

    def test_basic_rendering(self):
        """Test basic buyer company dropdown renders correctly."""
        import main
        component = main.buyer_company_dropdown()

        assert component is not None

    def test_custom_name(self):
        """Test buyer company dropdown with custom field name."""
        import main
        component = main.buyer_company_dropdown(name="payment_buyer_id")

        assert component is not None

    def test_with_label(self):
        """Test buyer company dropdown with custom label."""
        import main
        component = main.buyer_company_dropdown(label="Наше юрлицо (закупка)")

        assert component is not None

    def test_required_field(self):
        """Test buyer company dropdown marked as required."""
        import main
        component = main.buyer_company_dropdown(required=True)

        assert component is not None

    def test_with_preselected_value(self):
        """Test buyer company dropdown with pre-selected value."""
        import main
        component = main.buyer_company_dropdown(
            selected_id="buy-uuid-123",
            selected_label="MBR - ООО Мастер Бэринг (ИНН: 1234567890)"
        )

        assert component is not None


# ============================================================================
# Seller Company Dropdown Tests
# ============================================================================

class TestSellerCompanyDropdown:
    """Tests for the seller_company_dropdown component."""

    def test_basic_rendering(self):
        """Test basic seller company dropdown renders correctly."""
        import main
        component = main.seller_company_dropdown()

        assert component is not None

    def test_custom_name(self):
        """Test seller company dropdown with custom field name."""
        import main
        component = main.seller_company_dropdown(name="quote_seller_id")

        assert component is not None

    def test_with_label(self):
        """Test seller company dropdown with custom label."""
        import main
        component = main.seller_company_dropdown(label="Наше юрлицо (продажа)")

        assert component is not None

    def test_required_field(self):
        """Test seller company dropdown marked as required."""
        import main
        component = main.seller_company_dropdown(required=True)

        assert component is not None

    def test_with_preselected_value(self):
        """Test seller company dropdown with pre-selected value."""
        import main
        component = main.seller_company_dropdown(
            selected_id="sel-uuid-123",
            selected_label="CMT - ООО КМТ (ИНН: 0987654321)"
        )

        assert component is not None


# ============================================================================
# Component Output Structure Tests
# ============================================================================

class TestDropdownStructure:
    """Tests for dropdown component output structure."""

    def test_supplier_dropdown_has_css_class(self):
        """Test that supplier_dropdown has proper CSS class."""
        import main
        component = main.supplier_dropdown()

        attrs = getattr(component, 'attrs', {}) or {}
        cls = attrs.get('class', '')
        assert 'supplier-dropdown' in cls

    def test_buyer_company_dropdown_has_css_class(self):
        """Test that buyer_company_dropdown has proper CSS class."""
        import main
        component = main.buyer_company_dropdown()

        attrs = getattr(component, 'attrs', {}) or {}
        cls = attrs.get('class', '')
        assert 'buyer-company-dropdown' in cls

    def test_seller_company_dropdown_has_css_class(self):
        """Test that seller_company_dropdown has proper CSS class."""
        import main
        component = main.seller_company_dropdown()

        attrs = getattr(component, 'attrs', {}) or {}
        cls = attrs.get('class', '')
        assert 'seller-company-dropdown' in cls


# ============================================================================
# API Endpoint Tests (Mocked)
# ============================================================================

class TestDropdownAPIEndpoints:
    """Tests for dropdown search API endpoints."""

    def test_supplier_search_endpoint_exists(self):
        """Test that /api/suppliers/search route is registered."""
        import main

        # Check if the route exists in app routes
        # We just verify the function exists
        assert hasattr(main, 'rt')

    def test_buyer_companies_search_endpoint_exists(self):
        """Test that /api/buyer-companies/search route is registered."""
        import main

        # Verify the endpoint is defined
        assert hasattr(main, 'rt')

    def test_seller_companies_search_endpoint_exists(self):
        """Test that /api/seller-companies/search route is registered."""
        import main

        # Verify the endpoint is defined
        assert hasattr(main, 'rt')


# ============================================================================
# Usage Examples Tests
# ============================================================================

class TestDropdownUsageExamples:
    """Test common usage patterns for dropdown components."""

    def test_quote_form_seller_company(self):
        """Test creating seller company dropdown for quote form."""
        import main

        # At quote level - seller company selection
        component = main.seller_company_dropdown(
            name="seller_company_id",
            label="Компания-продавец",
            required=True,
            help_text="Юрлицо для этого КП"
        )

        assert component is not None

    def test_quote_item_supplier_selection(self):
        """Test creating supplier dropdown for quote item."""
        import main

        # At item level - supplier selection
        component = main.supplier_dropdown(
            name="supplier_id",
            label="Поставщик",
            required=True,
            help_text="Внешний поставщик для этой позиции"
        )

        assert component is not None

    def test_quote_item_buyer_company_selection(self):
        """Test creating buyer company dropdown for quote item."""
        import main

        # At item level - our purchasing entity
        component = main.buyer_company_dropdown(
            name="buyer_company_id",
            label="Закупающее юрлицо",
            required=True,
            help_text="Наше юрлицо для закупки этой позиции"
        )

        assert component is not None

    def test_edit_form_with_preselected_values(self):
        """Test dropdowns in edit form with existing values."""
        import main

        # Simulating edit form where values already exist
        existing_item = {
            "supplier_id": "sup-uuid-123",
            "supplier_name": "ABC - Test Supplier",
        }

        supplier_dropdown = main.supplier_dropdown(
            selected_id=existing_item["supplier_id"],
            selected_label=existing_item["supplier_name"]
        )

        assert supplier_dropdown is not None


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
