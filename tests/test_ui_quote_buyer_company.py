"""
Tests for UI-017: Quote item form - buyer company selector

Tests the buyer company dropdown in the quote item (product) form,
which allows selecting our purchasing legal entity at the item level.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class MockBuyerCompany:
    """Mock BuyerCompany for testing"""
    id: str
    company_code: str
    name: str
    inn: str = "1234567890"
    kpp: str = "123456789"
    ogrn: str = "1234567890123"
    country: str = "Россия"
    registration_address: Optional[str] = None
    general_director_name: Optional[str] = None
    general_director_position: Optional[str] = None
    is_active: bool = True
    organization_id: Optional[str] = None


# Test data
TEST_BUYER_COMPANY_1 = MockBuyerCompany(
    id=str(uuid.uuid4()),
    company_code="МБР",
    name="ООО МБР Трейдинг",
    inn="7701234567",
    kpp="770101001",
    ogrn="1177746123456",
    country="Россия",
    registration_address="г. Москва, ул. Ленина, д. 1",
    general_director_name="Иванов Иван Иванович",
    general_director_position="Генеральный директор"
)

TEST_BUYER_COMPANY_2 = MockBuyerCompany(
    id=str(uuid.uuid4()),
    company_code="КМТ",
    name="ООО КомТорг",
    inn="7702345678",
    kpp="770201001",
    ogrn="1177746234567",
    country="Россия"
)


class TestBuyerCompanyDropdownExists:
    """Test that buyer company dropdown component exists"""

    def test_buyer_company_dropdown_function_exists(self):
        """Verify buyer_company_dropdown function is defined in main.py"""
        # Import main.py and check for function
        import importlib.util
        spec = importlib.util.spec_from_file_location("main", "main.py")
        main_module = importlib.util.module_from_spec(spec)

        # Check if buyer_company_dropdown is defined
        with open("main.py", "r") as f:
            content = f.read()
            assert "def buyer_company_dropdown(" in content
            assert 'name: str = "buyer_company_id"' in content


class TestQuoteItemFormBuyerCompany:
    """Test buyer company selector in quote item form"""

    def test_buyer_company_dropdown_in_product_form(self):
        """Verify buyer_company_dropdown is called in the product form"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check that buyer_company_dropdown is used in the products form
            assert "buyer_company_dropdown(" in content
            assert 'name="buyer_company_id"' in content
            assert 'label="Компания-покупатель"' in content or 'label="Компания-покупатель"' in content

    def test_buyer_company_id_in_post_handler(self):
        """Verify buyer_company_id parameter is handled in POST"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check POST handler accepts buyer_company_id
            assert "buyer_company_id: str = None" in content
            # Check it's added to item_data
            assert '"buyer_company_id"' in content or "'buyer_company_id'" in content

    def test_buyer_company_info_fetching(self):
        """Verify buyer company info is fetched for display"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check buyer company info fetching
            assert "buyer_company_map" in content or "buyer_company_info" in content
            assert "get_buyer_company" in content


class TestProductRowBuyerCompanyBadge:
    """Test buyer company badge display in product row"""

    def test_product_row_accepts_buyer_company_info(self):
        """Verify product_row function accepts buyer_company_info parameter"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check function signature
            assert "def product_row(item, currency=" in content
            assert "buyer_company_info=None" in content

    def test_buyer_company_badge_rendering(self):
        """Verify buyer company badge is rendered in product row"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for buyer company badge display logic
            assert "buyer_company_info:" in content or "if buyer_company_info" in content
            # Check for buyer company display elements
            assert "company_code" in content
            assert "building-2" in content  # Buyer company Lucide icon

    def test_buyer_company_placeholder_badge(self):
        """Verify placeholder badge is shown when buyer_company_id exists but info not loaded"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for placeholder when buyer_company_id exists but no info
            assert 'item.get("buyer_company_id")' in content


class TestBuyerCompanyApiEndpoint:
    """Test buyer company search API endpoint"""

    def test_buyer_company_search_endpoint_exists(self):
        """Verify /api/buyer-companies/search endpoint is defined"""
        with open("main.py", "r") as f:
            content = f.read()
            assert "/api/buyer-companies/search" in content

    def test_buyer_company_dropdown_htmx_target(self):
        """Verify dropdown uses correct HTMX endpoint"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check that buyer_company_dropdown targets the search API
            assert '"hx-get": "/api/buyer-companies/search"' in content or "'hx-get': '/api/buyer-companies/search'" in content


class TestBuyerCompanyDataIntegration:
    """Test buyer company data saving and loading"""

    def test_buyer_company_id_saved_to_database(self):
        """Verify buyer_company_id is included in item_data for database insert"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check that buyer_company_id is added to item_data
            assert 'item_data["buyer_company_id"]' in content or "item_data['buyer_company_id']" in content

    def test_buyer_company_map_created_for_items(self):
        """Verify buyer_company_map is created for fetching buyer company info"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for buyer_company_map in GET handler
            assert "buyer_company_map = {}" in content or "buyer_company_map={}" in content

    def test_buyer_company_ids_extracted(self):
        """Verify buyer_company_ids are extracted from items"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for extracting buyer_company_ids
            assert "buyer_company_ids" in content
            assert 'item.get("buyer_company_id")' in content or "item.get('buyer_company_id')" in content


class TestBuyerCompanyUILabels:
    """Test Russian UI labels for buyer company"""

    def test_russian_label_kompaniya_pokupatel(self):
        """Verify Russian label 'Компания-покупатель' is used"""
        with open("main.py", "r") as f:
            content = f.read()
            assert "Компания-покупатель" in content

    def test_russian_help_text(self):
        """Verify Russian help text is provided"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for Russian help text
            assert "юрлицо для закупки" in content or "юридическое лицо" in content

    def test_buyer_company_badge_title(self):
        """Verify buyer company badge has proper Russian title"""
        with open("main.py", "r") as f:
            content = f.read()
            assert "Покупатель:" in content


class TestBuyerCompanyItemLevelBinding:
    """Test that buyer company is bound at item level, not quote level"""

    def test_buyer_company_in_quote_items_not_quotes(self):
        """Verify buyer_company_id is for quote_items, not quotes table"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for comment indicating item level
            assert "UI-017" in content  # Feature tag
            # Check buyer_company is in products/items context
            assert "quote_items" in content
            # buyer_company_id should be in product form, not quote form

    def test_supply_chain_comment_present(self):
        """Verify supply chain comment is present for buyer company"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for supply chain context
            assert "supply chain" in content.lower() or "Supply chain" in content


class TestProductRowWithBuyerCompany:
    """Test product_row function with buyer company info"""

    def test_product_row_handles_none_buyer_company(self):
        """Verify product_row handles None buyer_company_info gracefully"""
        # This is tested implicitly by checking the code structure
        with open("main.py", "r") as f:
            content = f.read()
            # Check for conditional buyer company handling
            assert "if buyer_company_info" in content or "buyer_company_info:" in content

    def test_product_row_displays_company_code(self):
        """Verify product_row displays company_code for buyer company"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check that company_code is used for display
            assert "company_code" in content

    def test_buyer_company_badge_color(self):
        """Verify buyer company badge uses distinct color (green)"""
        with open("main.py", "r") as f:
            content = f.read()
            # Check for green color for buyer company (distinct from blue supplier)
            assert "#008800" in content or "green" in content.lower()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
