"""
Tests for Buyer Company Service (Feature #API-002)

Tests CRUD operations for buyer_companies table:
- Create/Read/Update/Delete buyer companies
- Validation functions for company code, INN, KPP, OGRN
- Search and dropdown functions
- Utility functions
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.buyer_company_service import (
    # Data class
    BuyerCompany,
    # Validation functions
    validate_company_code,
    validate_inn,
    validate_kpp,
    validate_ogrn,
    # Parser functions
    _parse_buyer_company,
    _buyer_company_to_dict,
    # Create
    create_buyer_company,
    # Read
    get_buyer_company,
    get_buyer_company_by_code,
    get_buyer_company_by_inn,
    get_all_buyer_companies,
    count_buyer_companies,
    search_buyer_companies,
    get_active_buyer_companies,
    buyer_company_exists,
    # Update
    update_buyer_company,
    activate_buyer_company,
    deactivate_buyer_company,
    # Delete
    delete_buyer_company,
    # Utility
    get_buyer_company_stats,
    get_buyer_company_display_name,
    format_buyer_company_for_dropdown,
    get_buyer_companies_for_dropdown,
    get_buyer_company_for_document,
    _format_full_requisites,
)


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestCompanyCodeValidation:
    """Tests for company code validation."""

    def test_valid_company_code_three_letters(self):
        """Valid company code is 3 uppercase letters."""
        assert validate_company_code("ZAK") is True
        assert validate_company_code("CMT") is True
        assert validate_company_code("ABC") is True

    def test_invalid_company_code_lowercase(self):
        """Lowercase letters are invalid."""
        assert validate_company_code("zak") is False
        assert validate_company_code("Zak") is False

    def test_invalid_company_code_wrong_length(self):
        """Must be exactly 3 letters."""
        assert validate_company_code("ZA") is False
        assert validate_company_code("ZAKK") is False
        assert validate_company_code("") is False

    def test_invalid_company_code_numbers(self):
        """Numbers not allowed."""
        assert validate_company_code("ZA1") is False
        assert validate_company_code("123") is False

    def test_invalid_company_code_none(self):
        """None is invalid."""
        assert validate_company_code(None) is False


class TestINNValidation:
    """Tests for Russian INN validation (legal entities = 10 digits)."""

    def test_valid_inn_10_digits(self):
        """Legal entity INN is 10 digits."""
        assert validate_inn("7712345678") is True
        assert validate_inn("1234567890") is True

    def test_invalid_inn_12_digits(self):
        """12-digit INN is for individual entrepreneurs, not legal entities."""
        assert validate_inn("771234567890") is False

    def test_invalid_inn_wrong_length(self):
        """Wrong length INNs are invalid."""
        assert validate_inn("12345") is False
        assert validate_inn("123456789") is False
        assert validate_inn("12345678901") is False

    def test_invalid_inn_letters(self):
        """Letters not allowed."""
        assert validate_inn("771234567A") is False

    def test_valid_inn_empty_optional(self):
        """Empty INN is valid (optional field)."""
        assert validate_inn("") is True
        assert validate_inn(None) is True


class TestKPPValidation:
    """Tests for Russian KPP validation."""

    def test_valid_kpp_9_digits(self):
        """Valid KPP is 9 digits."""
        assert validate_kpp("771201001") is True
        assert validate_kpp("123456789") is True

    def test_invalid_kpp_wrong_length(self):
        """Wrong length KPPs are invalid."""
        assert validate_kpp("12345678") is False
        assert validate_kpp("1234567890") is False

    def test_invalid_kpp_letters(self):
        """Letters not allowed."""
        assert validate_kpp("77120100A") is False

    def test_valid_kpp_empty_optional(self):
        """Empty KPP is valid (optional field)."""
        assert validate_kpp("") is True
        assert validate_kpp(None) is True


class TestOGRNValidation:
    """Tests for Russian OGRN validation."""

    def test_valid_ogrn_13_digits(self):
        """Valid legal entity OGRN is 13 digits."""
        assert validate_ogrn("1027700123456") is True
        assert validate_ogrn("1234567890123") is True

    def test_invalid_ogrn_15_digits(self):
        """15-digit OGRN is for individual entrepreneurs."""
        assert validate_ogrn("123456789012345") is False

    def test_invalid_ogrn_wrong_length(self):
        """Wrong length OGRNs are invalid."""
        assert validate_ogrn("123456789012") is False
        assert validate_ogrn("12345678901234") is False

    def test_invalid_ogrn_letters(self):
        """Letters not allowed."""
        assert validate_ogrn("102770012345A") is False

    def test_valid_ogrn_empty_optional(self):
        """Empty OGRN is valid (optional field)."""
        assert validate_ogrn("") is True
        assert validate_ogrn(None) is True


# =============================================================================
# PARSER TESTS
# =============================================================================

class TestBuyerCompanyParser:
    """Tests for buyer company parsing functions."""

    def test_parse_buyer_company_full_data(self):
        """Parse complete buyer company data from database row."""
        data = {
            "id": "test-id-123",
            "organization_id": "org-id-456",
            "name": "ООО Закупка",
            "company_code": "ZAK",
            "country": "Россия",
            "inn": "7712345678",
            "kpp": "771201001",
            "ogrn": "1027700123456",
            "registration_address": "г. Москва, ул. Тестовая, д. 1",
            "general_director_name": "Иванов Иван Иванович",
            "general_director_position": "Генеральный директор",
            "is_active": True,
            "created_at": "2024-01-15T12:00:00Z",
            "updated_at": "2024-01-15T12:00:00Z",
            "created_by": "user-id-789",
        }

        company = _parse_buyer_company(data)

        assert company.id == "test-id-123"
        assert company.organization_id == "org-id-456"
        assert company.name == "ООО Закупка"
        assert company.company_code == "ZAK"
        assert company.country == "Россия"
        assert company.inn == "7712345678"
        assert company.kpp == "771201001"
        assert company.ogrn == "1027700123456"
        assert company.registration_address == "г. Москва, ул. Тестовая, д. 1"
        assert company.general_director_name == "Иванов Иван Иванович"
        assert company.general_director_position == "Генеральный директор"
        assert company.is_active is True
        assert company.created_at is not None
        assert company.updated_at is not None
        assert company.created_by == "user-id-789"

    def test_parse_buyer_company_minimal_data(self):
        """Parse buyer company with minimal required fields."""
        data = {
            "id": "test-id-123",
            "organization_id": "org-id-456",
            "name": "Test Company",
            "company_code": "TST",
        }

        company = _parse_buyer_company(data)

        assert company.id == "test-id-123"
        assert company.name == "Test Company"
        assert company.company_code == "TST"
        assert company.country is None
        assert company.inn is None
        assert company.is_active is True  # Default
        assert company.general_director_position == "Генеральный директор"  # Default

    def test_buyer_company_to_dict(self):
        """Convert BuyerCompany object to dict for database."""
        company = BuyerCompany(
            id="test-id-123",
            organization_id="org-id-456",
            name="ООО Закупка",
            company_code="ZAK",
            country="Россия",
            inn="7712345678",
            kpp="771201001",
            is_active=True,
            created_by="user-id-789",
        )

        data = _buyer_company_to_dict(company)

        assert data["organization_id"] == "org-id-456"
        assert data["name"] == "ООО Закупка"
        assert data["company_code"] == "ZAK"
        assert data["country"] == "Россия"
        assert data["inn"] == "7712345678"
        assert data["kpp"] == "771201001"
        assert data["is_active"] is True
        assert "id" not in data  # ID is auto-generated


# =============================================================================
# CREATE TESTS (with mocking)
# =============================================================================

class TestCreateBuyerCompany:
    """Tests for buyer company creation."""

    def test_create_buyer_company_validation_errors(self):
        """Invalid data raises ValueError before database call."""
        with pytest.raises(ValueError, match="Invalid company code"):
            create_buyer_company(
                organization_id="org-123",
                name="Test",
                company_code="invalid",
            )

        with pytest.raises(ValueError, match="Invalid INN"):
            create_buyer_company(
                organization_id="org-123",
                name="Test",
                company_code="TST",
                inn="12345",
            )

        with pytest.raises(ValueError, match="Invalid KPP"):
            create_buyer_company(
                organization_id="org-123",
                name="Test",
                company_code="TST",
                kpp="12345",
            )

        with pytest.raises(ValueError, match="Invalid OGRN"):
            create_buyer_company(
                organization_id="org-123",
                name="Test",
                company_code="TST",
                ogrn="12345",
            )

    @patch('services.buyer_company_service._get_supabase')
    def test_create_buyer_company_success(self, mock_supabase):
        """Successful buyer company creation."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "new-id",
            "organization_id": "org-123",
            "name": "ООО Закупка",
            "company_code": "ZAK",
            "country": "Россия",
            "inn": "7712345678",
            "kpp": "771201001",
            "ogrn": "1027700123456",
            "is_active": True,
            "created_at": "2024-01-15T12:00:00Z",
        }]

        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result

        company = create_buyer_company(
            organization_id="org-123",
            name="ООО Закупка",
            company_code="ZAK",
            country="Россия",
            inn="7712345678",
            kpp="771201001",
            ogrn="1027700123456",
        )

        assert company is not None
        assert company.name == "ООО Закупка"
        assert company.company_code == "ZAK"

    @patch('services.buyer_company_service._get_supabase')
    def test_create_buyer_company_duplicate_code(self, mock_supabase):
        """Duplicate company code returns None."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_client.table.return_value.insert.return_value.execute.side_effect = Exception(
            "duplicate key value violates unique constraint idx_buyer_companies_org_code"
        )

        company = create_buyer_company(
            organization_id="org-123",
            name="Test",
            company_code="ZAK",
        )

        assert company is None


# =============================================================================
# READ TESTS (with mocking)
# =============================================================================

class TestReadBuyerCompany:
    """Tests for buyer company read operations."""

    @patch('services.buyer_company_service._get_supabase')
    def test_get_buyer_company_found(self, mock_supabase):
        """Get buyer company by ID returns company."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "company-id-123",
            "organization_id": "org-456",
            "name": "Test Company",
            "company_code": "TST",
        }]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        company = get_buyer_company("company-id-123")

        assert company is not None
        assert company.id == "company-id-123"

    @patch('services.buyer_company_service._get_supabase')
    def test_get_buyer_company_not_found(self, mock_supabase):
        """Get buyer company by ID returns None if not found."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = []

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        company = get_buyer_company("nonexistent-id")

        assert company is None

    @patch('services.buyer_company_service._get_supabase')
    def test_get_buyer_company_by_code(self, mock_supabase):
        """Get buyer company by code within organization."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "company-id-123",
            "organization_id": "org-456",
            "name": "Test Company",
            "company_code": "TST",
        }]

        mock_query = MagicMock()
        mock_query.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_client.table.return_value.select.return_value = mock_query

        company = get_buyer_company_by_code("org-456", "TST")

        assert company is not None
        assert company.company_code == "TST"

    @patch('services.buyer_company_service._get_supabase')
    def test_get_buyer_company_by_inn(self, mock_supabase):
        """Get buyer company by INN within organization."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "company-id-123",
            "organization_id": "org-456",
            "name": "Test Company",
            "company_code": "TST",
            "inn": "7712345678",
        }]

        mock_query = MagicMock()
        mock_query.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_client.table.return_value.select.return_value = mock_query

        company = get_buyer_company_by_inn("org-456", "7712345678")

        assert company is not None
        assert company.inn == "7712345678"

    @patch('services.buyer_company_service._get_supabase')
    def test_count_buyer_companies(self, mock_supabase):
        """Count buyer companies in organization."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.count = 5

        mock_query = MagicMock()
        mock_query.eq.return_value.execute.return_value = mock_result
        mock_client.table.return_value.select.return_value = mock_query

        count = count_buyer_companies("org-456")

        assert count == 5

    @patch('services.buyer_company_service._get_supabase')
    def test_buyer_company_exists(self, mock_supabase):
        """Check if buyer company exists by code."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "company-id-123",
            "organization_id": "org-456",
            "name": "Test",
            "company_code": "TST",
        }]

        mock_query = MagicMock()
        mock_query.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_client.table.return_value.select.return_value = mock_query

        exists = buyer_company_exists("org-456", "TST")

        assert exists is True


# =============================================================================
# UPDATE TESTS (with mocking)
# =============================================================================

class TestUpdateBuyerCompany:
    """Tests for buyer company update operations."""

    def test_update_buyer_company_validation_errors(self):
        """Invalid update data raises ValueError."""
        with pytest.raises(ValueError, match="Invalid company code"):
            update_buyer_company("id", company_code="invalid")

        with pytest.raises(ValueError, match="Invalid INN"):
            update_buyer_company("id", inn="12345")

        with pytest.raises(ValueError, match="Invalid KPP"):
            update_buyer_company("id", kpp="12345")

        with pytest.raises(ValueError, match="Invalid OGRN"):
            update_buyer_company("id", ogrn="12345")

    @patch('services.buyer_company_service._get_supabase')
    def test_update_buyer_company_success(self, mock_supabase):
        """Successful buyer company update."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "company-id-123",
            "organization_id": "org-456",
            "name": "Updated Name",
            "company_code": "UPD",
        }]

        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        company = update_buyer_company("company-id-123", name="Updated Name", company_code="UPD")

        assert company is not None
        assert company.name == "Updated Name"

    @patch('services.buyer_company_service._get_supabase')
    def test_activate_buyer_company(self, mock_supabase):
        """Activate buyer company sets is_active=True."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "company-id-123",
            "organization_id": "org-456",
            "name": "Test",
            "company_code": "TST",
            "is_active": True,
        }]

        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        company = activate_buyer_company("company-id-123")

        assert company.is_active is True

    @patch('services.buyer_company_service._get_supabase')
    def test_deactivate_buyer_company(self, mock_supabase):
        """Deactivate buyer company sets is_active=False."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "company-id-123",
            "organization_id": "org-456",
            "name": "Test",
            "company_code": "TST",
            "is_active": False,
        }]

        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        company = deactivate_buyer_company("company-id-123")

        assert company.is_active is False


# =============================================================================
# DELETE TESTS (with mocking)
# =============================================================================

class TestDeleteBuyerCompany:
    """Tests for buyer company deletion."""

    @patch('services.buyer_company_service._get_supabase')
    def test_delete_buyer_company_success(self, mock_supabase):
        """Successful buyer company deletion."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = mock_result

        result = delete_buyer_company("company-id-123")

        assert result is True


# =============================================================================
# UTILITY TESTS
# =============================================================================

class TestBuyerCompanyUtility:
    """Tests for utility functions."""

    def test_get_buyer_company_display_name(self):
        """Get display name for buyer company."""
        company = BuyerCompany(
            id="123",
            organization_id="456",
            name="ООО Закупка",
            company_code="ZAK",
        )

        display = get_buyer_company_display_name(company)

        assert display == "ZAK - ООО Закупка"

    def test_format_buyer_company_for_dropdown_with_inn(self):
        """Format buyer company for dropdown with INN."""
        company = BuyerCompany(
            id="123",
            organization_id="456",
            name="ООО Закупка",
            company_code="ZAK",
            inn="7712345678",
        )

        option = format_buyer_company_for_dropdown(company)

        assert option["value"] == "123"
        assert "ZAK - ООО Закупка" in option["label"]
        assert "(ИНН: 7712345678)" in option["label"]

    def test_format_buyer_company_for_dropdown_without_inn(self):
        """Format buyer company for dropdown without INN."""
        company = BuyerCompany(
            id="123",
            organization_id="456",
            name="Test Company",
            company_code="TST",
        )

        option = format_buyer_company_for_dropdown(company)

        assert option["value"] == "123"
        assert option["label"] == "TST - Test Company"

    def test_format_full_requisites(self):
        """Format full requisites for documents."""
        company = BuyerCompany(
            id="123",
            organization_id="456",
            name="ООО Закупка",
            company_code="ZAK",
            inn="7712345678",
            kpp="771201001",
            ogrn="1027700123456",
            registration_address="г. Москва, ул. Тестовая, д. 1",
        )

        requisites = _format_full_requisites(company)

        assert "ООО Закупка" in requisites
        assert "г. Москва, ул. Тестовая, д. 1" in requisites
        assert "7712345678/771201001" in requisites
        assert "1027700123456" in requisites

    @patch('services.buyer_company_service.get_buyer_company')
    def test_get_buyer_company_for_document(self, mock_get):
        """Get buyer company formatted for document generation."""
        mock_get.return_value = BuyerCompany(
            id="123",
            organization_id="456",
            name="ООО Закупка",
            company_code="ZAK",
            inn="7712345678",
            kpp="771201001",
            ogrn="1027700123456",
            registration_address="г. Москва, ул. Тестовая, д. 1",
            general_director_name="Иванов И.И.",
            general_director_position="Генеральный директор",
        )

        doc = get_buyer_company_for_document("123")

        assert doc is not None
        assert doc["name"] == "ООО Закупка"
        assert doc["code"] == "ZAK"
        assert doc["inn"] == "7712345678"
        assert doc["kpp"] == "771201001"
        assert doc["ogrn"] == "1027700123456"
        assert doc["address"] == "г. Москва, ул. Тестовая, д. 1"
        assert doc["director_name"] == "Иванов И.И."
        assert doc["director_position"] == "Генеральный директор"
        assert "full_requisites" in doc

    @patch('services.buyer_company_service.get_buyer_company')
    def test_get_buyer_company_for_document_not_found(self, mock_get):
        """Get buyer company for document returns None if not found."""
        mock_get.return_value = None

        doc = get_buyer_company_for_document("nonexistent")

        assert doc is None


# =============================================================================
# STATS TESTS
# =============================================================================

class TestBuyerCompanyStats:
    """Tests for buyer company statistics."""

    @patch('services.buyer_company_service._get_supabase')
    def test_get_buyer_company_stats(self, mock_supabase):
        """Get buyer company statistics."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [
            {"is_active": True, "inn": "7712345678", "general_director_name": "Иванов И.И."},
            {"is_active": True, "inn": "7709876543", "general_director_name": None},
            {"is_active": False, "inn": None, "general_director_name": "Петров П.П."},
        ]

        mock_query = MagicMock()
        mock_query.eq.return_value.execute.return_value = mock_result
        mock_client.table.return_value.select.return_value = mock_query

        stats = get_buyer_company_stats("org-456")

        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["inactive"] == 1
        assert stats["with_inn"] == 2
        assert stats["with_director"] == 2

    @patch('services.buyer_company_service._get_supabase')
    def test_get_buyer_company_stats_empty(self, mock_supabase):
        """Get stats for organization with no buyer companies."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = []

        mock_query = MagicMock()
        mock_query.eq.return_value.execute.return_value = mock_result
        mock_client.table.return_value.select.return_value = mock_query

        stats = get_buyer_company_stats("org-456")

        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["inactive"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
