"""
Tests for Supplier Service

Feature #API-001: CRUD API for suppliers

Tests cover:
- Validation functions
- Data class parsing
- CRUD operations (unit tests without DB)
- Utility functions
"""

import pytest
from datetime import datetime
from services.supplier_service import (
    # Data class
    Supplier,
    # Validation functions
    validate_supplier_code,
    validate_inn,
    validate_kpp,
    # Parsing functions
    _parse_supplier,
    _supplier_to_dict,
    # Utility functions
    get_supplier_display_name,
    format_supplier_for_dropdown,
)


# =============================================================================
# TESTS: Validation Functions
# =============================================================================

class TestValidateSupplierCode:
    """Tests for validate_supplier_code function"""

    def test_valid_3_letter_code(self):
        """Test valid 3-letter uppercase codes"""
        assert validate_supplier_code("CMT") is True
        assert validate_supplier_code("RAR") is True
        assert validate_supplier_code("MBR") is True
        assert validate_supplier_code("ABC") is True

    def test_invalid_lowercase(self):
        """Test that lowercase codes are rejected"""
        assert validate_supplier_code("cmt") is False
        assert validate_supplier_code("Cmt") is False
        assert validate_supplier_code("CMt") is False

    def test_invalid_length(self):
        """Test that wrong length codes are rejected"""
        assert validate_supplier_code("AB") is False  # Too short
        assert validate_supplier_code("ABCD") is False  # Too long
        assert validate_supplier_code("A") is False
        assert validate_supplier_code("ABCDE") is False

    def test_invalid_characters(self):
        """Test that non-letter characters are rejected"""
        assert validate_supplier_code("AB1") is False
        assert validate_supplier_code("A1B") is False
        assert validate_supplier_code("123") is False
        assert validate_supplier_code("AB-") is False

    def test_empty_and_none(self):
        """Test empty and None inputs"""
        assert validate_supplier_code("") is False
        assert validate_supplier_code(None) is False


class TestValidateINN:
    """Tests for validate_inn function"""

    def test_valid_10_digit_inn(self):
        """Test valid 10-digit INN (legal entity)"""
        assert validate_inn("1234567890") is True
        assert validate_inn("0000000000") is True
        assert validate_inn("9999999999") is True

    def test_valid_12_digit_inn(self):
        """Test valid 12-digit INN (individual)"""
        assert validate_inn("123456789012") is True
        assert validate_inn("000000000000") is True

    def test_invalid_length(self):
        """Test invalid INN lengths"""
        assert validate_inn("123456789") is False  # 9 digits
        assert validate_inn("12345678901") is False  # 11 digits
        assert validate_inn("1234567890123") is False  # 13 digits

    def test_invalid_characters(self):
        """Test non-digit characters"""
        assert validate_inn("123456789a") is False
        assert validate_inn("12345678901a") is False
        assert validate_inn("abcdefghij") is False

    def test_empty_and_none(self):
        """Test empty and None inputs (should be valid - INN is optional)"""
        assert validate_inn("") is True
        assert validate_inn(None) is True


class TestValidateKPP:
    """Tests for validate_kpp function"""

    def test_valid_9_digit_kpp(self):
        """Test valid 9-digit KPP"""
        assert validate_kpp("123456789") is True
        assert validate_kpp("000000000") is True
        assert validate_kpp("999999999") is True

    def test_invalid_length(self):
        """Test invalid KPP lengths"""
        assert validate_kpp("12345678") is False  # 8 digits
        assert validate_kpp("1234567890") is False  # 10 digits

    def test_invalid_characters(self):
        """Test non-digit characters"""
        assert validate_kpp("12345678a") is False
        assert validate_kpp("abcdefghi") is False

    def test_empty_and_none(self):
        """Test empty and None inputs (should be valid - KPP is optional)"""
        assert validate_kpp("") is True
        assert validate_kpp(None) is True


# =============================================================================
# TESTS: Data Class
# =============================================================================

class TestSupplierDataClass:
    """Tests for Supplier dataclass"""

    def test_supplier_with_required_fields(self):
        """Test creating Supplier with only required fields"""
        supplier = Supplier(
            id="supplier-uuid",
            organization_id="org-uuid",
            name="China Manufacturing Ltd",
            supplier_code="CMT",
        )

        assert supplier.id == "supplier-uuid"
        assert supplier.organization_id == "org-uuid"
        assert supplier.name == "China Manufacturing Ltd"
        assert supplier.supplier_code == "CMT"
        assert supplier.is_active is True  # Default
        assert supplier.country is None
        assert supplier.city is None

    def test_supplier_with_all_fields(self):
        """Test creating Supplier with all fields"""
        supplier = Supplier(
            id="supplier-uuid",
            organization_id="org-uuid",
            name="Test Supplier Ltd",
            supplier_code="TST",
            country="China",
            city="Guangzhou",
            inn="1234567890",
            kpp="123456789",
            contact_person="John Doe",
            contact_email="john@example.com",
            contact_phone="+86 123 456 7890",
            default_payment_terms="30 days net",
            is_active=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by="user-uuid",
        )

        assert supplier.country == "China"
        assert supplier.city == "Guangzhou"
        assert supplier.inn == "1234567890"
        assert supplier.is_active is False
        assert supplier.contact_person == "John Doe"


class TestParseSupplier:
    """Tests for _parse_supplier function"""

    def test_parse_minimal_data(self):
        """Test parsing minimal database row"""
        data = {
            "id": "supplier-uuid",
            "organization_id": "org-uuid",
            "name": "Test Supplier",
            "supplier_code": "TST",
        }

        supplier = _parse_supplier(data)

        assert supplier.id == "supplier-uuid"
        assert supplier.name == "Test Supplier"
        assert supplier.supplier_code == "TST"
        assert supplier.is_active is True

    def test_parse_full_data(self):
        """Test parsing complete database row"""
        data = {
            "id": "supplier-uuid",
            "organization_id": "org-uuid",
            "name": "China Manufacturing Ltd",
            "supplier_code": "CMT",
            "country": "China",
            "city": "Shenzhen",
            "inn": "1234567890",
            "kpp": "123456789",
            "contact_person": "Wang Wei",
            "contact_email": "wang@company.com",
            "contact_phone": "+86 123 456 7890",
            "default_payment_terms": "50% advance, 50% before shipment",
            "is_active": True,
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T12:00:00Z",
            "created_by": "user-uuid",
        }

        supplier = _parse_supplier(data)

        assert supplier.country == "China"
        assert supplier.city == "Shenzhen"
        assert supplier.inn == "1234567890"
        assert supplier.contact_person == "Wang Wei"
        assert supplier.created_at.year == 2025

    def test_parse_with_null_fields(self):
        """Test parsing with null/None fields"""
        data = {
            "id": "supplier-uuid",
            "organization_id": "org-uuid",
            "name": "Test",
            "supplier_code": "TST",
            "country": None,
            "city": None,
            "inn": None,
            "kpp": None,
            "contact_person": None,
            "contact_email": None,
            "contact_phone": None,
            "default_payment_terms": None,
            "is_active": True,
            "created_at": None,
            "updated_at": None,
            "created_by": None,
        }

        supplier = _parse_supplier(data)

        assert supplier.country is None
        assert supplier.inn is None
        assert supplier.created_at is None


class TestSupplierToDict:
    """Tests for _supplier_to_dict function"""

    def test_convert_supplier_to_dict(self):
        """Test converting Supplier to dict for DB operations"""
        supplier = Supplier(
            id="supplier-uuid",
            organization_id="org-uuid",
            name="Test Supplier",
            supplier_code="TST",
            country="Russia",
            city="Moscow",
            inn="1234567890",
            is_active=True,
            created_by="user-uuid",
        )

        result = _supplier_to_dict(supplier)

        assert result["organization_id"] == "org-uuid"
        assert result["name"] == "Test Supplier"
        assert result["supplier_code"] == "TST"
        assert result["country"] == "Russia"
        assert result["is_active"] is True
        assert "id" not in result  # ID should not be in dict


# =============================================================================
# TESTS: Utility Functions
# =============================================================================

class TestGetSupplierDisplayName:
    """Tests for get_supplier_display_name function"""

    def test_display_name_format(self):
        """Test display name is formatted correctly"""
        supplier = Supplier(
            id="uuid",
            organization_id="org-uuid",
            name="China Manufacturing Ltd",
            supplier_code="CMT",
        )

        result = get_supplier_display_name(supplier)

        assert result == "CMT - China Manufacturing Ltd"

    def test_display_name_different_codes(self):
        """Test display name with different codes"""
        supplier = Supplier(
            id="uuid",
            organization_id="org-uuid",
            name="Test Company",
            supplier_code="TST",
        )

        result = get_supplier_display_name(supplier)

        assert result == "TST - Test Company"


class TestFormatSupplierForDropdown:
    """Tests for format_supplier_for_dropdown function"""

    def test_format_without_location(self):
        """Test dropdown format without location"""
        supplier = Supplier(
            id="supplier-uuid",
            organization_id="org-uuid",
            name="Test Supplier",
            supplier_code="TST",
        )

        result = format_supplier_for_dropdown(supplier)

        assert result["value"] == "supplier-uuid"
        assert result["label"] == "TST - Test Supplier"

    def test_format_with_country_only(self):
        """Test dropdown format with country only"""
        supplier = Supplier(
            id="supplier-uuid",
            organization_id="org-uuid",
            name="Test Supplier",
            supplier_code="TST",
            country="China",
        )

        result = format_supplier_for_dropdown(supplier)

        assert result["label"] == "TST - Test Supplier (China)"

    def test_format_with_city_and_country(self):
        """Test dropdown format with city and country"""
        supplier = Supplier(
            id="supplier-uuid",
            organization_id="org-uuid",
            name="China Manufacturing Ltd",
            supplier_code="CMT",
            country="China",
            city="Guangzhou",
        )

        result = format_supplier_for_dropdown(supplier)

        assert result["value"] == "supplier-uuid"
        assert result["label"] == "CMT - China Manufacturing Ltd (Guangzhou, China)"

    def test_format_with_city_only_no_country(self):
        """Test dropdown format with city but no country"""
        supplier = Supplier(
            id="supplier-uuid",
            organization_id="org-uuid",
            name="Test",
            supplier_code="TST",
            city="Moscow",  # City without country
        )

        result = format_supplier_for_dropdown(supplier)

        # City without country should not add location suffix
        assert result["label"] == "TST - Test"


# =============================================================================
# TESTS: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests"""

    def test_supplier_code_boundary_cases(self):
        """Test boundary cases for supplier code validation"""
        # Exactly 3 characters
        assert validate_supplier_code("AAA") is True
        assert validate_supplier_code("ZZZ") is True

        # Unicode characters (should fail)
        assert validate_supplier_code("ABC") is True  # ASCII
        # Non-ASCII should fail pattern matching
        assert validate_supplier_code("") is False

    def test_inn_boundary_cases(self):
        """Test boundary cases for INN validation"""
        # Exactly 10 digits
        assert validate_inn("0" * 10) is True
        assert validate_inn("9" * 10) is True

        # Exactly 12 digits
        assert validate_inn("0" * 12) is True
        assert validate_inn("9" * 12) is True

        # Edge: 11 digits (invalid)
        assert validate_inn("0" * 11) is False

    def test_special_characters_in_name(self):
        """Test that special characters in name are handled"""
        supplier = Supplier(
            id="uuid",
            organization_id="org-uuid",
            name="Company & Partners \"Test\" Ltd.",
            supplier_code="CMP",
        )

        # Should not raise exception
        display = get_supplier_display_name(supplier)
        assert "Company & Partners" in display

    def test_empty_string_vs_none_handling(self):
        """Test distinction between empty string and None"""
        # Empty strings should be valid for optional fields
        assert validate_inn("") is True  # Empty is OK
        assert validate_kpp("") is True

        # But invalid format should fail
        assert validate_inn("abc") is False
        assert validate_kpp("abc") is False
