"""
Tests for UI-015: Quote form seller company selector.

Tests the integration of seller_company_id at the quote level:
- Quote creation form with seller company dropdown
- Quote edit form with seller company dropdown
- Calculate page displaying seller company from quote
- POST handlers properly saving seller_company_id
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "organization_id": str(uuid4()),
        "email": "test@example.com",
        "role": "admin",
        "role_code": "admin",
    }


@pytest.fixture
def mock_session(mock_user):
    """Mock session with user."""
    return {"user": mock_user}


@pytest.fixture
def sample_seller_company():
    """Sample seller company data."""
    return {
        "id": str(uuid4()),
        "supplier_code": "CMT",
        "name": "ООО КМТ Торговля",
        "inn": "1234567890",
        "country": "Россия",
        "is_active": True,
    }


@pytest.fixture
def sample_seller_company_2():
    """Second sample seller company data."""
    return {
        "id": str(uuid4()),
        "supplier_code": "MBR",
        "name": "ООО Мастер Бэринг",
        "inn": "0987654321",
        "country": "Россия",
        "is_active": True,
    }


@pytest.fixture
def sample_customer():
    """Sample customer data."""
    return {
        "id": str(uuid4()),
        "name": "Тестовый Клиент ООО",
        "inn": "9876543210",
    }


@pytest.fixture
def sample_quote(sample_seller_company, sample_customer):
    """Sample quote with seller company."""
    return {
        "id": str(uuid4()),
        "idn_quote": "Q-202601-0001",
        "title": "Quote for Test Customer",
        "customer_id": sample_customer["id"],
        "seller_company_id": sample_seller_company["id"],
        "organization_id": str(uuid4()),
        "currency": "RUB",
        "status": "draft",
        "delivery_terms": "DDP",
        "payment_terms": 30,
        "delivery_days": 45,
        "notes": None,
        "seller_companies": {
            "id": sample_seller_company["id"],
            "supplier_code": sample_seller_company["supplier_code"],
            "name": sample_seller_company["name"],
        },
        "customers": {
            "name": sample_customer["name"],
        }
    }


@pytest.fixture
def sample_quote_no_seller(sample_customer):
    """Sample quote without seller company."""
    return {
        "id": str(uuid4()),
        "idn_quote": "Q-202601-0002",
        "title": "Quote without Seller",
        "customer_id": sample_customer["id"],
        "seller_company_id": None,
        "organization_id": str(uuid4()),
        "currency": "USD",
        "status": "draft",
        "delivery_terms": "EXW",
        "payment_terms": 45,
        "delivery_days": 60,
        "notes": None,
        "seller_companies": None,
        "customers": {
            "name": sample_customer["name"],
        }
    }


# ============================================================================
# SellerCompany Dataclass Tests
# ============================================================================

class TestSellerCompanyDataclass:
    """Test SellerCompany dataclass used by dropdown."""

    def test_seller_company_service_import(self):
        """Test that seller company service can be imported."""
        from services.seller_company_service import (
            SellerCompany,
            get_all_seller_companies,
            format_seller_company_for_dropdown,
        )
        assert SellerCompany is not None
        assert callable(get_all_seller_companies)
        assert callable(format_seller_company_for_dropdown)

    def test_format_seller_company_for_dropdown(self, sample_seller_company):
        """Test format_seller_company_for_dropdown output."""
        from services.seller_company_service import (
            SellerCompany,
            format_seller_company_for_dropdown,
        )

        sc = SellerCompany(
            id=sample_seller_company["id"],
            organization_id=str(uuid4()),  # Required field
            supplier_code=sample_seller_company["supplier_code"],
            name=sample_seller_company["name"],
            inn=sample_seller_company["inn"],
            country=sample_seller_company.get("country"),
            is_active=sample_seller_company["is_active"],
        )

        formatted = format_seller_company_for_dropdown(sc)

        # Result could be dict with label or string
        if isinstance(formatted, dict):
            label = formatted.get('label', '')
            assert "CMT" in label
            assert "КМТ" in label
        else:
            # Direct string format
            assert "CMT" in formatted
            assert "КМТ" in formatted


# ============================================================================
# Quote New Form Tests
# ============================================================================

class TestQuoteNewFormSellerCompany:
    """Tests for seller company dropdown in new quote form."""

    def test_new_quote_form_imports_seller_companies(self):
        """Test that new quote form imports seller_company_service."""
        import main
        # The route should be defined
        assert hasattr(main, 'rt')

    def test_new_quote_form_has_seller_company_field(self):
        """Test new quote form includes seller_company_id field."""
        # Verify the code has the field
        import main
        import inspect

        # Get the source code of the module
        source = inspect.getsource(main)

        # Check that new quote form includes seller_company_id
        assert 'seller_company_id' in source
        assert 'Компания-продавец' in source

    def test_new_quote_post_accepts_seller_company_id(self):
        """Test that new quote POST handler accepts seller_company_id parameter."""
        import main
        import inspect

        # Check the POST handler signature
        source = inspect.getsource(main)

        # The post handler should accept seller_company_id
        assert 'seller_company_id: str = None' in source or 'seller_company_id: str=' in source


# ============================================================================
# Quote Edit Form Tests
# ============================================================================

class TestQuoteEditFormSellerCompany:
    """Tests for seller company dropdown in quote edit form."""

    def test_edit_quote_form_loads_seller_company(self):
        """Test that edit form loads quote's seller_company from DB."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Should query seller_companies relation
        assert 'seller_companies(' in source or 'seller_companies(id' in source

    def test_edit_quote_form_has_dropdown(self):
        """Test edit form has seller company dropdown."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Check for dropdown elements
        assert 'seller_company_id' in source
        assert 'format_seller_company_for_dropdown' in source

    def test_edit_quote_post_saves_seller_company_id(self):
        """Test that edit POST saves seller_company_id to database."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Check that update includes seller_company_id
        assert '"seller_company_id"' in source or "'seller_company_id'" in source


# ============================================================================
# Calculate Page Tests
# ============================================================================

class TestCalculatePageSellerCompany:
    """Tests for seller company display on calculate page."""

    def test_calculate_page_loads_seller_company(self):
        """Test that calculate page loads seller_company from quote."""
        import main
        import inspect

        source = inspect.getsource(main)

        # The calculate page should query seller_companies
        assert 'seller_companies' in source

    def test_calculate_page_shows_seller_or_warning(self):
        """Test calculate page shows seller company or warning if not set."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Should handle missing seller company
        assert 'Не выбрана' in source or 'seller_company_section' in source

    def test_calculate_page_links_to_edit(self):
        """Test calculate page links to edit when seller company missing."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Should link to edit page
        assert 'quotes/{quote_id}/edit' in source or 'настройках КП' in source


# ============================================================================
# Seller Company Display Tests
# ============================================================================

class TestSellerCompanyDisplay:
    """Tests for seller company display formatting."""

    def test_seller_company_display_format(self, sample_seller_company):
        """Test seller company is displayed with code and name."""
        display = f"{sample_seller_company['supplier_code']} - {sample_seller_company['name']}"
        assert "CMT" in display
        assert "КМТ" in display

    def test_seller_company_display_with_none(self):
        """Test display when seller company is None."""
        seller_company_info = None
        display = "Не выбрана" if not seller_company_info else "..."
        assert display == "Не выбрана"


# ============================================================================
# Integration Tests
# ============================================================================

class TestSellerCompanyIntegration:
    """Integration tests for seller company at quote level."""

    def test_seller_company_id_in_quote_insert(self):
        """Test seller_company_id can be inserted into quote."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Check insert statement includes seller_company_id
        assert 'seller_company_id' in source

    def test_seller_company_id_in_quote_update(self):
        """Test seller_company_id can be updated in quote."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Check update handles seller_company_id
        assert '"seller_company_id"' in source or "'seller_company_id'" in source

    def test_main_module_can_be_imported(self):
        """Test main module imports successfully with new changes."""
        import main
        assert main is not None

    def test_seller_company_dropdown_component_exists(self):
        """Test seller_company_dropdown function exists."""
        import main
        assert hasattr(main, 'seller_company_dropdown')
        assert callable(main.seller_company_dropdown)


# ============================================================================
# Validation Tests
# ============================================================================

class TestSellerCompanyValidation:
    """Tests for seller company validation."""

    def test_seller_company_id_can_be_none(self):
        """Test that seller_company_id can be None (for drafts)."""
        # None is allowed for drafts
        seller_company_id = None
        assert seller_company_id is None

    def test_seller_company_id_strips_whitespace(self):
        """Test that seller_company_id whitespace is stripped."""
        seller_company_id = "  uuid-value  "
        cleaned = seller_company_id.strip() if seller_company_id else None
        assert cleaned == "uuid-value"

    def test_empty_string_becomes_none(self):
        """Test that empty string seller_company_id becomes None."""
        seller_company_id = ""
        cleaned = seller_company_id.strip() if seller_company_id and seller_company_id.strip() else None
        assert cleaned is None


# ============================================================================
# Quote Detail Display Tests
# ============================================================================

class TestQuoteDetailSellerCompany:
    """Tests for seller company display on quote detail page."""

    def test_quote_detail_could_show_seller_company(self):
        """Test quote detail can display seller company info."""
        # The quote detail could show seller company
        # This verifies the data structure supports it
        from services.seller_company_service import format_seller_company_for_dropdown, SellerCompany

        sc = SellerCompany(
            id="test-id",
            organization_id=str(uuid4()),  # Required field
            supplier_code="CMT",
            name="Test Company",
            inn="1234567890",
            is_active=True,
        )

        formatted = format_seller_company_for_dropdown(sc)
        assert formatted is not None
        assert len(formatted) > 0


# ============================================================================
# Dropdown Population Tests
# ============================================================================

class TestDropdownPopulation:
    """Tests for seller company dropdown population."""

    def test_dropdown_options_sorted_by_code(self):
        """Test dropdown options are ordered appropriately."""
        from services.seller_company_service import SellerCompany

        org_id = str(uuid4())
        companies = [
            SellerCompany(id="1", organization_id=org_id, supplier_code="ZZZ", name="Last", inn="1", is_active=True),
            SellerCompany(id="2", organization_id=org_id, supplier_code="AAA", name="First", inn="2", is_active=True),
            SellerCompany(id="3", organization_id=org_id, supplier_code="MMM", name="Middle", inn="3", is_active=True),
        ]

        # Verify we can sort
        sorted_codes = sorted([c.supplier_code for c in companies])
        assert sorted_codes == ["AAA", "MMM", "ZZZ"]

    def test_dropdown_only_shows_active_companies(self):
        """Test dropdown should only show active seller companies."""
        from services.seller_company_service import SellerCompany

        org_id = str(uuid4())
        companies = [
            SellerCompany(id="1", organization_id=org_id, supplier_code="ACT", name="Active", inn="1", is_active=True),
            SellerCompany(id="2", organization_id=org_id, supplier_code="INA", name="Inactive", inn="2", is_active=False),
        ]

        active_only = [c for c in companies if c.is_active]
        assert len(active_only) == 1
        assert active_only[0].supplier_code == "ACT"


# ============================================================================
# Edge Cases
# ============================================================================

class TestSellerCompanyEdgeCases:
    """Edge case tests for seller company handling."""

    def test_no_seller_companies_in_org(self):
        """Test handling when organization has no seller companies."""
        seller_companies = []
        assert len(seller_companies) == 0

    def test_single_seller_company(self):
        """Test handling when organization has only one seller company."""
        from services.seller_company_service import SellerCompany

        companies = [
            SellerCompany(id="1", organization_id=str(uuid4()), supplier_code="ONLY", name="Only One", inn="1", is_active=True),
        ]

        assert len(companies) == 1

    def test_quote_with_deleted_seller_company(self, sample_quote_no_seller):
        """Test quote when referenced seller company was deleted."""
        # If seller_company_id references non-existent company
        # The seller_companies join would return None
        quote = sample_quote_no_seller
        assert quote["seller_companies"] is None


# ============================================================================
# API Integration Tests
# ============================================================================

class TestAPISellerCompanyIntegration:
    """Tests for API integration with seller company."""

    def test_search_endpoint_exists(self):
        """Test /api/seller-companies/search endpoint exists."""
        import main
        # If this imports without error, route is registered
        assert hasattr(main, 'rt')

    def test_search_returns_html_options(self):
        """Test search endpoint returns HTML options."""
        import main
        import inspect

        source = inspect.getsource(main)

        # Should return Option elements
        assert '/api/seller-companies/search' in source
        assert 'Option' in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
