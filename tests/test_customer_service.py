"""
Tests for Customer Service - CRUD operations for customers and contacts

Feature: API-004
Tests: Customer validation, CRUD operations, contact management, dropdown helpers
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the service module
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.customer_service import (
    # Data classes
    Customer,
    CustomerContact,
    # Validation functions
    validate_inn,
    validate_kpp,
    validate_ogrn,
    validate_email,
    validate_phone,
    # Customer CRUD
    create_customer,
    get_customer,
    get_customer_with_contacts,
    get_customer_by_inn,
    get_all_customers,
    get_active_customers,
    count_customers,
    search_customers,
    customer_exists,
    update_customer,
    activate_customer,
    deactivate_customer,
    add_warehouse_address,
    remove_warehouse_address,
    delete_customer,
    # Contact CRUD
    create_contact,
    get_contact,
    get_contacts_for_customer,
    get_signatory_contact,
    get_primary_contact,
    count_contacts,
    update_contact,
    set_signatory,
    set_primary,
    delete_contact,
    delete_all_contacts,
    # Utility functions
    get_customer_stats,
    get_customer_display_name,
    format_customer_for_dropdown,
    get_customers_for_dropdown,
    get_customer_for_document,
    get_customer_for_idn,
    get_signatory_for_specification,
    # Internal functions for parsing
    _parse_customer,
    _parse_contact,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_customer_data():
    """Sample customer database row."""
    return {
        "id": "cust-123",
        "organization_id": "org-456",
        "name": "ООО Ромашка",
        "inn": "7712345678",
        "kpp": "771201001",
        "ogrn": "1027712345678",
        "legal_address": "г. Москва, ул. Ленина, д. 1",
        "actual_address": "г. Москва, ул. Мира, д. 5",
        "general_director_name": "Петров Петр Петрович",
        "general_director_position": "Генеральный директор",
        "warehouse_addresses": ["Склад 1", "Склад 2"],
        "is_active": True,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_contact_data():
    """Sample contact database row."""
    return {
        "id": "contact-123",
        "customer_id": "cust-123",
        "name": "Иванов Иван Иванович",
        "position": "Директор по закупкам",
        "email": "ivanov@romashka.ru",
        "phone": "+7 (495) 123-45-67",
        "is_signatory": True,
        "is_primary": True,
        "notes": "Основной контакт",
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_customer(sample_customer_data):
    """Sample Customer object."""
    return _parse_customer(sample_customer_data)


@pytest.fixture
def sample_contact(sample_contact_data):
    """Sample CustomerContact object."""
    return _parse_contact(sample_contact_data)


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestValidation:
    """Test validation functions."""

    # INN validation
    def test_validate_inn_valid_10_digits(self):
        """Valid INN with 10 digits (legal entity)."""
        assert validate_inn("7712345678") is True

    def test_validate_inn_valid_12_digits(self):
        """Valid INN with 12 digits (individual entrepreneur)."""
        assert validate_inn("771234567890") is True

    def test_validate_inn_invalid_9_digits(self):
        """Invalid INN with 9 digits."""
        assert validate_inn("771234567") is False

    def test_validate_inn_invalid_11_digits(self):
        """Invalid INN with 11 digits."""
        assert validate_inn("77123456789") is False

    def test_validate_inn_invalid_letters(self):
        """Invalid INN with letters."""
        assert validate_inn("77123A5678") is False

    def test_validate_inn_empty(self):
        """Empty INN is valid (optional field)."""
        assert validate_inn("") is True
        assert validate_inn(None) is True

    # KPP validation
    def test_validate_kpp_valid(self):
        """Valid KPP with 9 digits."""
        assert validate_kpp("771201001") is True

    def test_validate_kpp_invalid_8_digits(self):
        """Invalid KPP with 8 digits."""
        assert validate_kpp("77120100") is False

    def test_validate_kpp_invalid_10_digits(self):
        """Invalid KPP with 10 digits."""
        assert validate_kpp("7712010011") is False

    def test_validate_kpp_empty(self):
        """Empty KPP is valid (optional field)."""
        assert validate_kpp("") is True
        assert validate_kpp(None) is True

    # OGRN validation
    def test_validate_ogrn_valid_13_digits(self):
        """Valid OGRN with 13 digits (legal entity)."""
        assert validate_ogrn("1027712345678") is True

    def test_validate_ogrn_valid_15_digits(self):
        """Valid OGRN with 15 digits (individual entrepreneur)."""
        assert validate_ogrn("304770000123456") is True

    def test_validate_ogrn_invalid_12_digits(self):
        """Invalid OGRN with 12 digits."""
        assert validate_ogrn("102771234567") is False

    def test_validate_ogrn_empty(self):
        """Empty OGRN is valid (optional field)."""
        assert validate_ogrn("") is True
        assert validate_ogrn(None) is True

    # Email validation
    def test_validate_email_valid(self):
        """Valid email addresses."""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@company.ru") is True
        assert validate_email("user@sub.domain.org") is True

    def test_validate_email_invalid_no_at(self):
        """Invalid email without @."""
        assert validate_email("testexample.com") is False

    def test_validate_email_invalid_no_domain(self):
        """Invalid email without domain."""
        assert validate_email("test@") is False

    def test_validate_email_empty(self):
        """Empty email is valid (optional field)."""
        assert validate_email("") is True
        assert validate_email(None) is True

    # Phone validation
    def test_validate_phone_valid(self):
        """Valid phone numbers."""
        assert validate_phone("+7 (495) 123-45-67") is True
        assert validate_phone("84951234567") is True
        assert validate_phone("1234567") is True

    def test_validate_phone_invalid_too_short(self):
        """Invalid phone too short."""
        assert validate_phone("123456") is False

    def test_validate_phone_invalid_letters(self):
        """Invalid phone with letters."""
        assert validate_phone("abc-def-ghij") is False

    def test_validate_phone_empty(self):
        """Empty phone is valid (optional field)."""
        assert validate_phone("") is True
        assert validate_phone(None) is True


# =============================================================================
# PARSING TESTS
# =============================================================================

class TestParsing:
    """Test data parsing functions."""

    def test_parse_customer(self, sample_customer_data):
        """Parse customer from database row."""
        customer = _parse_customer(sample_customer_data)

        assert customer.id == "cust-123"
        assert customer.organization_id == "org-456"
        assert customer.name == "ООО Ромашка"
        assert customer.inn == "7712345678"
        assert customer.kpp == "771201001"
        assert customer.ogrn == "1027712345678"
        assert customer.legal_address == "г. Москва, ул. Ленина, д. 1"
        assert customer.actual_address == "г. Москва, ул. Мира, д. 5"
        assert customer.general_director_name == "Петров Петр Петрович"
        assert customer.warehouse_addresses == ["Склад 1", "Склад 2"]
        assert customer.is_active is True
        assert customer.contacts == []

    def test_parse_customer_with_contacts(self, sample_customer_data, sample_contact_data):
        """Parse customer with contacts."""
        customer = _parse_customer(sample_customer_data, [sample_contact_data])

        assert len(customer.contacts) == 1
        assert customer.contacts[0].name == "Иванов Иван Иванович"

    def test_parse_contact(self, sample_contact_data):
        """Parse contact from database row."""
        contact = _parse_contact(sample_contact_data)

        assert contact.id == "contact-123"
        assert contact.customer_id == "cust-123"
        assert contact.name == "Иванов Иван Иванович"
        assert contact.position == "Директор по закупкам"
        assert contact.email == "ivanov@romashka.ru"
        assert contact.phone == "+7 (495) 123-45-67"
        assert contact.is_signatory is True
        assert contact.is_primary is True

    def test_parse_customer_with_null_warehouse(self):
        """Parse customer with null warehouse addresses."""
        data = {
            "id": "cust-123",
            "organization_id": "org-456",
            "name": "Test",
            "warehouse_addresses": None,
            "created_at": "2025-01-15T10:00:00Z",
        }
        customer = _parse_customer(data)
        assert customer.warehouse_addresses == []


# =============================================================================
# CUSTOMER CRUD TESTS (WITH MOCKS)
# =============================================================================

class TestCustomerCRUD:
    """Test customer CRUD operations with mocked database."""

    @patch('services.customer_service._get_supabase')
    def test_create_customer_success(self, mock_get_supabase, sample_customer_data):
        """Create customer successfully."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_customer_data]
        )

        customer = create_customer(
            organization_id="org-456",
            name="ООО Ромашка",
            inn="7712345678",
            kpp="771201001",
        )

        assert customer is not None
        assert customer.name == "ООО Ромашка"
        mock_client.table.assert_called_with("customers")

    def test_create_customer_invalid_inn(self):
        """Create customer with invalid INN raises error."""
        with pytest.raises(ValueError) as excinfo:
            create_customer(
                organization_id="org-456",
                name="Test",
                inn="invalid",
            )
        assert "Invalid INN format" in str(excinfo.value)

    def test_create_customer_invalid_kpp(self):
        """Create customer with invalid KPP raises error."""
        with pytest.raises(ValueError) as excinfo:
            create_customer(
                organization_id="org-456",
                name="Test",
                kpp="12345",
            )
        assert "Invalid KPP format" in str(excinfo.value)

    @patch('services.customer_service._get_supabase')
    def test_get_customer_found(self, mock_get_supabase, sample_customer_data):
        """Get existing customer."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_customer_data]
        )

        customer = get_customer("cust-123")

        assert customer is not None
        assert customer.id == "cust-123"

    @patch('services.customer_service._get_supabase')
    def test_get_customer_not_found(self, mock_get_supabase):
        """Get non-existing customer returns None."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        customer = get_customer("nonexistent")

        assert customer is None

    @patch('services.customer_service._get_supabase')
    def test_get_all_customers(self, mock_get_supabase, sample_customer_data):
        """Get all customers for organization."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value = mock_query
        mock_query.range.return_value.execute.return_value = MagicMock(
            data=[sample_customer_data]
        )

        customers = get_all_customers("org-456")

        assert len(customers) == 1
        assert customers[0].name == "ООО Ромашка"

    @patch('services.customer_service._get_supabase')
    def test_search_customers(self, mock_get_supabase, sample_customer_data):
        """Search customers by name."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.ilike.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_customer_data]
        )

        customers = search_customers("org-456", "Ромашка")

        assert len(customers) == 1
        assert customers[0].name == "ООО Ромашка"

    @patch('services.customer_service._get_supabase')
    def test_update_customer(self, mock_get_supabase, sample_customer_data):
        """Update customer name."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        updated_data = {**sample_customer_data, "name": "ООО Ромашка-2"}
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        customer = update_customer("cust-123", name="ООО Ромашка-2")

        assert customer is not None
        assert customer.name == "ООО Ромашка-2"

    @patch('services.customer_service._get_supabase')
    def test_delete_customer(self, mock_get_supabase):
        """Delete customer."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        result = delete_customer("cust-123")

        assert result is True
        # Should delete contacts first
        assert mock_client.table.call_count >= 2


# =============================================================================
# CONTACT CRUD TESTS (WITH MOCKS)
# =============================================================================

class TestContactCRUD:
    """Test contact CRUD operations with mocked database."""

    @patch('services.customer_service._get_supabase')
    def test_create_contact_success(self, mock_get_supabase, sample_contact_data):
        """Create contact successfully."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_contact_data]
        )

        contact = create_contact(
            customer_id="cust-123",
            name="Иванов Иван Иванович",
            email="ivanov@test.com",
            is_signatory=True,
        )

        assert contact is not None
        assert contact.name == "Иванов Иван Иванович"

    def test_create_contact_invalid_email(self):
        """Create contact with invalid email raises error."""
        with pytest.raises(ValueError) as excinfo:
            create_contact(
                customer_id="cust-123",
                name="Test",
                email="invalid-email",
            )
        assert "Invalid email format" in str(excinfo.value)

    @patch('services.customer_service._get_supabase')
    def test_get_contacts_for_customer(self, mock_get_supabase, sample_contact_data):
        """Get all contacts for customer."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=[sample_contact_data]
        )

        contacts = get_contacts_for_customer("cust-123")

        assert len(contacts) == 1
        assert contacts[0].name == "Иванов Иван Иванович"

    @patch('services.customer_service._get_supabase')
    def test_get_signatory_contact(self, mock_get_supabase, sample_contact_data):
        """Get signatory contact for customer."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_query
        mock_query.limit.return_value.execute.return_value = MagicMock(
            data=[sample_contact_data]
        )

        contact = get_signatory_contact("cust-123")

        assert contact is not None
        assert contact.is_signatory is True


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_customer_display_name_with_inn(self, sample_customer):
        """Display name includes INN."""
        display = get_customer_display_name(sample_customer)
        assert "ООО Ромашка" in display
        assert "7712345678" in display

    def test_get_customer_display_name_without_inn(self):
        """Display name without INN shows just name."""
        customer = Customer(
            id="test",
            organization_id="org",
            name="Test Company",
        )
        display = get_customer_display_name(customer)
        assert display == "Test Company"

    def test_format_customer_for_dropdown(self, sample_customer):
        """Format customer for dropdown includes id and label."""
        dropdown = format_customer_for_dropdown(sample_customer)

        assert dropdown["value"] == "cust-123"
        assert "ООО Ромашка" in dropdown["label"]

    @patch('services.customer_service.get_customer')
    def test_get_customer_for_idn(self, mock_get_customer, sample_customer):
        """Get customer INN for IDN generation."""
        mock_get_customer.return_value = sample_customer

        result = get_customer_for_idn("cust-123")

        assert result is not None
        assert result["inn"] == "7712345678"

    @patch('services.customer_service.get_signatory_contact')
    @patch('services.customer_service.get_customer')
    def test_get_signatory_for_specification_from_contact(
        self, mock_get_customer, mock_get_signatory, sample_contact
    ):
        """Get signatory from contact for specification."""
        mock_get_signatory.return_value = sample_contact
        mock_get_customer.return_value = None

        result = get_signatory_for_specification("cust-123")

        assert result is not None
        assert result["name"] == "Иванов Иван Иванович"
        assert result["position"] == "Директор по закупкам"

    @patch('services.customer_service.get_signatory_contact')
    @patch('services.customer_service.get_customer')
    def test_get_signatory_for_specification_fallback_to_director(
        self, mock_get_customer, mock_get_signatory, sample_customer
    ):
        """Get signatory falls back to director when no contact."""
        mock_get_signatory.return_value = None
        mock_get_customer.return_value = sample_customer

        result = get_signatory_for_specification("cust-123")

        assert result is not None
        assert result["name"] == "Петров Петр Петрович"
        assert result["position"] == "Генеральный директор"


# =============================================================================
# WAREHOUSE ADDRESS TESTS
# =============================================================================

class TestWarehouseAddresses:
    """Test warehouse address management."""

    @patch('services.customer_service.get_customer')
    @patch('services.customer_service.update_customer')
    def test_add_warehouse_address(self, mock_update, mock_get, sample_customer):
        """Add warehouse address to customer."""
        mock_get.return_value = sample_customer
        mock_update.return_value = sample_customer

        result = add_warehouse_address("cust-123", "Новый склад")

        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert "Новый склад" in call_args.kwargs["warehouse_addresses"]

    @patch('services.customer_service.get_customer')
    @patch('services.customer_service.update_customer')
    def test_add_duplicate_warehouse_address(self, mock_update, mock_get, sample_customer):
        """Adding duplicate warehouse address doesn't change list."""
        mock_get.return_value = sample_customer

        result = add_warehouse_address("cust-123", "Склад 1")

        # Should not call update since address already exists
        mock_update.assert_not_called()

    @patch('services.customer_service.get_customer')
    @patch('services.customer_service.update_customer')
    def test_remove_warehouse_address(self, mock_update, mock_get, sample_customer):
        """Remove warehouse address from customer."""
        mock_get.return_value = sample_customer
        mock_update.return_value = sample_customer

        result = remove_warehouse_address("cust-123", "Склад 1")

        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert "Склад 1" not in call_args.kwargs["warehouse_addresses"]


# =============================================================================
# INTEGRATION-STYLE TESTS (STILL MOCKED)
# =============================================================================

class TestCustomerWithContacts:
    """Test customer operations with contacts."""

    @patch('services.customer_service._get_supabase')
    def test_get_customer_with_contacts(self, mock_get_supabase, sample_customer_data, sample_contact_data):
        """Get customer with all contacts populated."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # First call: get customer
        mock_query1 = MagicMock()
        mock_query1.execute.return_value = MagicMock(data=[sample_customer_data])

        # Second call: get contacts
        mock_query2 = MagicMock()
        mock_query2.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=[sample_contact_data]
        )

        # Setup chain
        mock_client.table.return_value.select.return_value.eq.side_effect = [
            mock_query1,  # customer query
            mock_query2,  # contacts query
        ]

        customer = get_customer_with_contacts("cust-123")

        assert customer is not None
        assert len(customer.contacts) == 1
        assert customer.contacts[0].name == "Иванов Иван Иванович"

    @patch('services.customer_service.get_customer_with_contacts')
    def test_get_customer_for_document(self, mock_get_customer, sample_customer):
        """Get customer formatted for document generation."""
        # Add contact to customer
        sample_customer.contacts = [
            CustomerContact(
                id="contact-1",
                customer_id="cust-123",
                name="Сидоров С.С.",
                position="Подписант",
                is_signatory=True,
                is_primary=True,
                email="sidorov@test.com",
                phone="+7 (495) 999-88-77",
            )
        ]
        mock_get_customer.return_value = sample_customer

        result = get_customer_for_document("cust-123")

        assert result is not None
        assert result["name"] == "ООО Ромашка"
        assert result["inn"] == "7712345678"
        assert result["signatory_name"] == "Сидоров С.С."
        assert result["signatory_position"] == "Подписант"
        assert result["primary_contact_name"] == "Сидоров С.С."
        assert result["primary_contact_email"] == "sidorov@test.com"
        assert "ИНН/КПП" in result["full_requisites"]


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_search_customers_empty_query(self):
        """Search with empty query returns empty list."""
        result = search_customers("org-456", "")
        assert result == []

    def test_search_customers_short_query(self):
        """Search with 1-char query still works."""
        with patch('services.customer_service._get_supabase') as mock_get_supabase:
            mock_client = MagicMock()
            mock_get_supabase.return_value = mock_client
            mock_query = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.ilike.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            result = search_customers("org-456", "О")
            # Should still execute the query
            assert result == []

    @patch('services.customer_service._get_supabase')
    def test_update_customer_no_changes(self, mock_get_supabase, sample_customer_data):
        """Update customer with no changes returns current state."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_customer_data]
        )

        customer = update_customer("cust-123")

        assert customer is not None
        assert customer.name == "ООО Ромашка"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
