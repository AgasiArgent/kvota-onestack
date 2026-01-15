"""
Tests for Seller Company Service (Feature API-003)

Tests CRUD operations for seller_companies table:
- Validation functions
- Create/Read/Update/Delete operations
- Search and dropdown helpers
- Document formatting utilities
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Import service functions
from services.seller_company_service import (
    # Data class
    SellerCompany,
    # Validation functions
    validate_supplier_code,
    validate_inn,
    validate_kpp,
    validate_ogrn,
    # Create operations
    create_seller_company,
    # Read operations
    get_seller_company,
    get_seller_company_by_code,
    get_seller_company_by_inn,
    get_all_seller_companies,
    count_seller_companies,
    search_seller_companies,
    get_active_seller_companies,
    seller_company_exists,
    # Update operations
    update_seller_company,
    activate_seller_company,
    deactivate_seller_company,
    # Delete operations
    delete_seller_company,
    # Utility functions
    get_seller_company_stats,
    get_seller_company_display_name,
    format_seller_company_for_dropdown,
    get_seller_companies_for_dropdown,
    get_seller_company_for_document,
    get_seller_company_for_idn,
    get_unique_countries,
    _format_full_requisites,
    _parse_seller_company,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_seller_company():
    """Sample seller company data for testing."""
    return SellerCompany(
        id="550e8400-e29b-41d4-a716-446655440000",
        organization_id="org-123",
        name="МАСТЕР БЭРИНГ ООО",
        supplier_code="MBR",
        country="Россия",
        inn="7712345678",
        kpp="771201001",
        ogrn="1027700123456",
        registration_address="123456, г. Москва, ул. Примерная, д. 1",
        general_director_name="Иванов Иван Иванович",
        general_director_position="Генеральный директор",
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by="user-123",
    )


@pytest.fixture
def sample_db_row():
    """Sample database row for testing parsing."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "organization_id": "org-123",
        "name": "МАСТЕР БЭРИНГ ООО",
        "supplier_code": "MBR",
        "country": "Россия",
        "inn": "7712345678",
        "kpp": "771201001",
        "ogrn": "1027700123456",
        "registration_address": "123456, г. Москва, ул. Примерная, д. 1",
        "general_director_name": "Иванов Иван Иванович",
        "general_director_position": "Генеральный директор",
        "is_active": True,
        "created_at": "2026-01-15T12:00:00Z",
        "updated_at": "2026-01-15T12:00:00Z",
        "created_by": "user-123",
    }


@pytest.fixture
def turkish_seller_company():
    """Turkish seller company for testing international companies."""
    return SellerCompany(
        id="660e8400-e29b-41d4-a716-446655440001",
        organization_id="org-123",
        name="GESTUS DIŞ TİCARET",
        supplier_code="GES",
        country="Турция",
        inn=None,
        kpp=None,
        ogrn=None,
        registration_address="Istanbul, Turkey",
        general_director_name="Ahmet Yilmaz",
        general_director_position="Director",
        is_active=True,
    )


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    """Tests for validation functions."""

    def test_validate_supplier_code_valid(self):
        """Valid 3-letter uppercase codes should pass."""
        assert validate_supplier_code("MBR") is True
        assert validate_supplier_code("RAR") is True
        assert validate_supplier_code("CMT") is True
        assert validate_supplier_code("GES") is True
        assert validate_supplier_code("TEX") is True

    def test_validate_supplier_code_invalid(self):
        """Invalid codes should fail."""
        assert validate_supplier_code("") is False
        assert validate_supplier_code("MB") is False  # Too short
        assert validate_supplier_code("MBRX") is False  # Too long
        assert validate_supplier_code("mbr") is False  # Lowercase
        assert validate_supplier_code("M1R") is False  # Contains digit
        assert validate_supplier_code("MB-") is False  # Contains dash
        assert validate_supplier_code(None) is False

    def test_validate_inn_valid(self):
        """Valid INN formats should pass."""
        assert validate_inn("7712345678") is True  # 10 digits (legal entity)
        assert validate_inn("771234567890") is True  # 12 digits (IE)
        assert validate_inn("") is True  # Empty is OK (optional)
        assert validate_inn(None) is True  # None is OK (optional)

    def test_validate_inn_invalid(self):
        """Invalid INN formats should fail."""
        assert validate_inn("771234567") is False  # 9 digits
        assert validate_inn("77123456789") is False  # 11 digits
        assert validate_inn("7712345678901") is False  # 13 digits
        assert validate_inn("ABCDEFGHIJ") is False  # Letters

    def test_validate_kpp_valid(self):
        """Valid KPP formats should pass."""
        assert validate_kpp("771201001") is True  # 9 digits
        assert validate_kpp("") is True  # Empty is OK
        assert validate_kpp(None) is True  # None is OK

    def test_validate_kpp_invalid(self):
        """Invalid KPP formats should fail."""
        assert validate_kpp("77120100") is False  # 8 digits
        assert validate_kpp("7712010010") is False  # 10 digits
        assert validate_kpp("ABCDEFGHI") is False  # Letters

    def test_validate_ogrn_valid(self):
        """Valid OGRN formats should pass."""
        assert validate_ogrn("1027700123456") is True  # 13 digits (legal entity)
        assert validate_ogrn("312774612345678") is True  # 15 digits (IE)
        assert validate_ogrn("") is True  # Empty is OK
        assert validate_ogrn(None) is True  # None is OK

    def test_validate_ogrn_invalid(self):
        """Invalid OGRN formats should fail."""
        assert validate_ogrn("102770012345") is False  # 12 digits
        assert validate_ogrn("10277001234567") is False  # 14 digits
        assert validate_ogrn("ABCDEFGHIJKLM") is False  # Letters


# =============================================================================
# Parsing Tests
# =============================================================================

class TestParsing:
    """Tests for parsing functions."""

    def test_parse_seller_company(self, sample_db_row):
        """Test parsing database row into SellerCompany object."""
        company = _parse_seller_company(sample_db_row)

        assert company.id == "550e8400-e29b-41d4-a716-446655440000"
        assert company.organization_id == "org-123"
        assert company.name == "МАСТЕР БЭРИНГ ООО"
        assert company.supplier_code == "MBR"
        assert company.country == "Россия"
        assert company.inn == "7712345678"
        assert company.kpp == "771201001"
        assert company.ogrn == "1027700123456"
        assert company.registration_address == "123456, г. Москва, ул. Примерная, д. 1"
        assert company.general_director_name == "Иванов Иван Иванович"
        assert company.general_director_position == "Генеральный директор"
        assert company.is_active is True
        assert company.created_at is not None

    def test_parse_seller_company_minimal(self):
        """Test parsing with minimal required fields."""
        minimal_row = {
            "id": "test-id",
            "organization_id": "org-123",
            "name": "Test Company",
            "supplier_code": "TST",
        }
        company = _parse_seller_company(minimal_row)

        assert company.id == "test-id"
        assert company.name == "Test Company"
        assert company.supplier_code == "TST"
        assert company.country is None
        assert company.inn is None
        assert company.is_active is True  # Default


# =============================================================================
# Display Formatting Tests
# =============================================================================

class TestDisplayFormatting:
    """Tests for display and formatting functions."""

    def test_get_seller_company_display_name(self, sample_seller_company):
        """Test display name generation."""
        display_name = get_seller_company_display_name(sample_seller_company)
        assert display_name == "MBR - МАСТЕР БЭРИНГ ООО"

    def test_format_seller_company_for_dropdown(self, sample_seller_company):
        """Test dropdown format with INN and country."""
        result = format_seller_company_for_dropdown(sample_seller_company)

        assert result["value"] == "550e8400-e29b-41d4-a716-446655440000"
        assert "MBR" in result["label"]
        assert "МАСТЕР БЭРИНГ ООО" in result["label"]
        assert "ИНН: 7712345678" in result["label"]
        assert "[Россия]" in result["label"]

    def test_format_seller_company_for_dropdown_no_inn(self, turkish_seller_company):
        """Test dropdown format without INN."""
        result = format_seller_company_for_dropdown(turkish_seller_company)

        assert result["value"] == "660e8400-e29b-41d4-a716-446655440001"
        assert "GES" in result["label"]
        assert "GESTUS DIŞ TİCARET" in result["label"]
        assert "ИНН:" not in result["label"]
        assert "[Турция]" in result["label"]

    def test_format_full_requisites(self, sample_seller_company):
        """Test full requisites formatting for documents."""
        requisites = _format_full_requisites(sample_seller_company)

        assert "МАСТЕР БЭРИНГ ООО" in requisites
        assert "Страна: Россия" in requisites
        assert "ИНН/КПП: 7712345678/771201001" in requisites
        assert "ОГРН: 1027700123456" in requisites
        assert "Адрес: 123456, г. Москва" in requisites

    def test_format_full_requisites_minimal(self):
        """Test requisites formatting with minimal data."""
        company = SellerCompany(
            id="test",
            organization_id="org",
            name="Test Company",
            supplier_code="TST",
        )
        requisites = _format_full_requisites(company)

        assert requisites == "Test Company"

    def test_format_full_requisites_inn_no_kpp(self):
        """Test requisites with INN but no KPP."""
        company = SellerCompany(
            id="test",
            organization_id="org",
            name="Test Company",
            supplier_code="TST",
            inn="7712345678",
        )
        requisites = _format_full_requisites(company)

        assert "ИНН: 7712345678" in requisites
        assert "КПП" not in requisites


# =============================================================================
# Document Formatting Tests
# =============================================================================

class TestDocumentFormatting:
    """Tests for document generation helpers."""

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_for_document(self, mock_supabase, sample_db_row):
        """Test document data extraction."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_db_row]
        )

        result = get_seller_company_for_document("test-id")

        assert result is not None
        assert result["name"] == "МАСТЕР БЭРИНГ ООО"
        assert result["code"] == "MBR"
        assert result["country"] == "Россия"
        assert result["inn"] == "7712345678"
        assert result["kpp"] == "771201001"
        assert result["ogrn"] == "1027700123456"
        assert result["director_name"] == "Иванов Иван Иванович"
        assert result["director_position"] == "Генеральный директор"
        assert "full_requisites" in result

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_for_document_not_found(self, mock_supabase):
        """Test document data when company not found."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_seller_company_for_document("nonexistent-id")
        assert result is None

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_for_idn(self, mock_supabase, sample_db_row):
        """Test IDN data extraction."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_db_row]
        )

        result = get_seller_company_for_idn("test-id")

        assert result is not None
        assert result["code"] == "MBR"
        assert result["inn"] == "7712345678"


# =============================================================================
# CRUD Operation Tests (Mocked)
# =============================================================================

class TestCRUDOperations:
    """Tests for CRUD operations with mocked database."""

    @patch("services.seller_company_service._get_supabase")
    def test_create_seller_company_success(self, mock_supabase, sample_db_row):
        """Test successful company creation."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_db_row]
        )

        result = create_seller_company(
            organization_id="org-123",
            name="МАСТЕР БЭРИНГ ООО",
            supplier_code="MBR",
            country="Россия",
            inn="7712345678",
            kpp="771201001",
        )

        assert result is not None
        assert result.name == "МАСТЕР БЭРИНГ ООО"
        assert result.supplier_code == "MBR"

    def test_create_seller_company_invalid_code(self):
        """Test creation with invalid supplier code."""
        with pytest.raises(ValueError) as excinfo:
            create_seller_company(
                organization_id="org-123",
                name="Test",
                supplier_code="invalid",
            )
        assert "Invalid supplier code" in str(excinfo.value)

    def test_create_seller_company_invalid_inn(self):
        """Test creation with invalid INN."""
        with pytest.raises(ValueError) as excinfo:
            create_seller_company(
                organization_id="org-123",
                name="Test",
                supplier_code="TST",
                inn="123",  # Invalid
            )
        assert "Invalid INN" in str(excinfo.value)

    def test_create_seller_company_invalid_kpp(self):
        """Test creation with invalid KPP."""
        with pytest.raises(ValueError) as excinfo:
            create_seller_company(
                organization_id="org-123",
                name="Test",
                supplier_code="TST",
                kpp="12345",  # Invalid - should be 9 digits
            )
        assert "Invalid KPP" in str(excinfo.value)

    def test_create_seller_company_invalid_ogrn(self):
        """Test creation with invalid OGRN."""
        with pytest.raises(ValueError) as excinfo:
            create_seller_company(
                organization_id="org-123",
                name="Test",
                supplier_code="TST",
                ogrn="12345",  # Invalid - should be 13 or 15 digits
            )
        assert "Invalid OGRN" in str(excinfo.value)

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company(self, mock_supabase, sample_db_row):
        """Test getting company by ID."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_db_row]
        )

        result = get_seller_company("test-id")

        assert result is not None
        assert result.supplier_code == "MBR"

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_not_found(self, mock_supabase):
        """Test getting non-existent company."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_seller_company("nonexistent-id")
        assert result is None

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_by_code(self, mock_supabase, sample_db_row):
        """Test getting company by code."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_result = MagicMock()
        mock_result.execute.return_value = MagicMock(data=[sample_db_row])
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_result

        result = get_seller_company_by_code("org-123", "MBR")

        assert result is not None
        assert result.supplier_code == "MBR"

    @patch("services.seller_company_service._get_supabase")
    def test_get_all_seller_companies(self, mock_supabase, sample_db_row):
        """Test getting all companies."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_range = MagicMock()
        mock_range.execute.return_value = MagicMock(data=[sample_db_row, sample_db_row])
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value = mock_range

        result = get_all_seller_companies("org-123")

        assert len(result) == 2

    @patch("services.seller_company_service._get_supabase")
    def test_count_seller_companies(self, mock_supabase):
        """Test counting companies."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            count=5
        )

        result = count_seller_companies("org-123")
        assert result == 5

    @patch("services.seller_company_service._get_supabase")
    def test_update_seller_company(self, mock_supabase, sample_db_row):
        """Test updating company."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        updated_row = {**sample_db_row, "name": "Updated Name"}
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_row]
        )

        result = update_seller_company("test-id", name="Updated Name")

        assert result is not None
        assert result.name == "Updated Name"

    def test_update_seller_company_invalid_code(self):
        """Test update with invalid supplier code."""
        with pytest.raises(ValueError) as excinfo:
            update_seller_company("test-id", supplier_code="invalid")
        assert "Invalid supplier code" in str(excinfo.value)

    @patch("services.seller_company_service._get_supabase")
    def test_delete_seller_company(self, mock_supabase):
        """Test deleting company."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        result = delete_seller_company("test-id")
        assert result is True

    @patch("services.seller_company_service._get_supabase")
    def test_activate_deactivate_seller_company(self, mock_supabase, sample_db_row):
        """Test activate/deactivate functions."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Test deactivate
        deactivated_row = {**sample_db_row, "is_active": False}
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[deactivated_row]
        )

        result = deactivate_seller_company("test-id")
        assert result is not None
        assert result.is_active is False


# =============================================================================
# Search Tests
# =============================================================================

class TestSearch:
    """Tests for search functionality."""

    @patch("services.seller_company_service._get_supabase")
    def test_search_seller_companies_by_name(self, mock_supabase, sample_db_row):
        """Test searching by company name."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # First query - name search
        mock_limit = MagicMock()
        mock_limit.execute.return_value = MagicMock(data=[sample_db_row])
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.ilike.return_value.order.return_value.limit.return_value = mock_limit

        result = search_seller_companies("org-123", "мастер")

        assert len(result) >= 1

    def test_search_seller_companies_empty_query(self):
        """Test search with empty query returns empty list."""
        result = search_seller_companies("org-123", "")
        assert result == []

        result = search_seller_companies("org-123", None)
        assert result == []

    @patch("services.seller_company_service._get_supabase")
    def test_seller_company_exists(self, mock_supabase, sample_db_row):
        """Test existence check."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_result = MagicMock()
        mock_result.execute.return_value = MagicMock(data=[sample_db_row])
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_result

        assert seller_company_exists("org-123", "MBR") is True

    @patch("services.seller_company_service._get_supabase")
    def test_seller_company_not_exists(self, mock_supabase):
        """Test existence check for non-existent company."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_result = MagicMock()
        mock_result.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_result

        assert seller_company_exists("org-123", "XXX") is False


# =============================================================================
# Statistics Tests
# =============================================================================

class TestStatistics:
    """Tests for statistics functions."""

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_stats(self, mock_supabase):
        """Test statistics calculation."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"is_active": True, "inn": "7712345678", "general_director_name": "Ivan", "country": "Россия"},
                {"is_active": True, "inn": "7712345679", "general_director_name": None, "country": "Россия"},
                {"is_active": False, "inn": None, "general_director_name": "Peter", "country": "Турция"},
            ]
        )

        stats = get_seller_company_stats("org-123")

        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["inactive"] == 1
        assert stats["with_inn"] == 2
        assert stats["with_director"] == 2
        assert stats["by_country"]["Россия"] == 2
        assert stats["by_country"]["Турция"] == 1

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_stats_empty(self, mock_supabase):
        """Test statistics with no companies."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        stats = get_seller_company_stats("org-123")

        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["by_country"] == {}

    @patch("services.seller_company_service._get_supabase")
    def test_get_unique_countries(self, mock_supabase):
        """Test getting unique countries."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # The chain is: table().select().eq().not_.is_().execute()
        # not_ is a property that returns a builder, is_() is called on it
        mock_result = MagicMock(
            data=[
                {"country": "Россия"},
                {"country": "Турция"},
                {"country": "Россия"},
                {"country": "Китай"},
            ]
        )
        # Configure the entire chain to return our mock result
        mock_client.table.return_value\
            .select.return_value\
            .eq.return_value\
            .not_.is_.return_value\
            .execute.return_value = mock_result

        countries = get_unique_countries("org-123")

        assert len(countries) == 3
        assert "Россия" in countries
        assert "Турция" in countries
        assert "Китай" in countries


# =============================================================================
# Dropdown Tests
# =============================================================================

class TestDropdown:
    """Tests for dropdown helper functions."""

    @patch("services.seller_company_service.search_seller_companies")
    def test_get_seller_companies_for_dropdown_with_query(self, mock_search, sample_seller_company):
        """Test dropdown data with search query."""
        mock_search.return_value = [sample_seller_company]

        result = get_seller_companies_for_dropdown("org-123", query="мастер")

        assert len(result) == 1
        assert result[0]["value"] == sample_seller_company.id
        assert "MBR" in result[0]["label"]

    @patch("services.seller_company_service.get_active_seller_companies")
    def test_get_seller_companies_for_dropdown_no_query(self, mock_get_active, sample_seller_company):
        """Test dropdown data without search query."""
        mock_get_active.return_value = [sample_seller_company]

        result = get_seller_companies_for_dropdown("org-123")

        assert len(result) == 1
        mock_get_active.assert_called_once_with("org-123")


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("services.seller_company_service._get_supabase")
    def test_create_duplicate_code_returns_none(self, mock_supabase):
        """Test that duplicate code returns None instead of raising."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.side_effect = Exception(
            "duplicate key value violates unique constraint idx_seller_companies_org_code"
        )

        result = create_seller_company(
            organization_id="org-123",
            name="Test",
            supplier_code="MBR",
        )

        assert result is None

    @patch("services.seller_company_service._get_supabase")
    def test_get_seller_company_handles_error(self, mock_supabase):
        """Test that errors are handled gracefully."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB Error")

        result = get_seller_company("test-id")
        assert result is None

    def test_ie_validation_12_digit_inn(self):
        """Test 12-digit INN validation for individual entrepreneurs."""
        assert validate_inn("771234567890") is True  # 12 digits
        assert validate_inn("7712345678") is True  # 10 digits

    def test_ie_validation_15_digit_ogrn(self):
        """Test 15-digit OGRN validation for individual entrepreneurs."""
        assert validate_ogrn("312774612345678") is True  # 15 digits
        assert validate_ogrn("1027700123456") is True  # 13 digits
