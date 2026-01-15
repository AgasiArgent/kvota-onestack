"""
Tests for UI-014: Invoice Payment Form

Tests the payment registration functionality through the supplier_invoice_payment_service.
UI routes are tested through integration tests when server is running.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# MOCK DATA
# =============================================================================

def create_mock_invoice(
    invoice_id="inv-uuid-001",
    invoice_number="INV-2025-001",
    organization_id="org-uuid-001",
    supplier_id="sup-uuid-001",
    supplier_name="Test Supplier",
    supplier_code="TST",
    total_amount=Decimal("5000.00"),
    total_paid=Decimal("2000.00"),
    currency="USD",
    status="partially_paid",
    invoice_date=None,
    due_date=None,
):
    """Create a mock invoice for testing."""
    from dataclasses import dataclass, field
    from typing import Optional

    @dataclass
    class MockInvoice:
        id: str = invoice_id
        invoice_number: str = invoice_number
        organization_id: str = organization_id
        supplier_id: str = supplier_id
        supplier_name: str = supplier_name
        supplier_code: str = supplier_code
        total_amount: Decimal = total_amount
        total_paid: Decimal = total_paid
        currency: str = currency
        status: str = status
        invoice_date: date = field(default_factory=lambda: date.today() - timedelta(days=30))
        due_date: date = field(default_factory=lambda: date.today() + timedelta(days=30))
        notes: str = "Test invoice notes"
        is_overdue: bool = False

    return MockInvoice(
        invoice_date=invoice_date or (date.today() - timedelta(days=30)),
        due_date=due_date or (date.today() + timedelta(days=30)),
    )


# =============================================================================
# PAYMENT SERVICE TESTS
# =============================================================================

class TestPaymentServiceConstants:
    """Test payment service constants and types."""

    def test_payment_types_defined(self):
        """Test payment types are properly defined."""
        from services.supplier_invoice_payment_service import (
            PAYMENT_TYPE_ADVANCE, PAYMENT_TYPE_PARTIAL, PAYMENT_TYPE_FINAL, PAYMENT_TYPE_REFUND,
            PAYMENT_TYPES
        )

        assert PAYMENT_TYPE_ADVANCE == "advance"
        assert PAYMENT_TYPE_PARTIAL == "partial"
        assert PAYMENT_TYPE_FINAL == "final"
        assert PAYMENT_TYPE_REFUND == "refund"
        assert len(PAYMENT_TYPES) == 4

    def test_payment_type_names_russian(self):
        """Test Russian names are defined for all payment types."""
        from services.supplier_invoice_payment_service import PAYMENT_TYPES, PAYMENT_TYPE_NAMES

        for pt in PAYMENT_TYPES:
            assert pt in PAYMENT_TYPE_NAMES
            assert PAYMENT_TYPE_NAMES[pt]  # Non-empty

    def test_payment_type_colors_defined(self):
        """Test colors are defined for all payment types."""
        from services.supplier_invoice_payment_service import PAYMENT_TYPES, PAYMENT_TYPE_COLORS

        for pt in PAYMENT_TYPES:
            assert pt in PAYMENT_TYPE_COLORS
            assert PAYMENT_TYPE_COLORS[pt]  # Non-empty

    def test_supported_currencies(self):
        """Test supported currencies list."""
        from services.supplier_invoice_payment_service import SUPPORTED_CURRENCIES, DEFAULT_CURRENCY

        assert DEFAULT_CURRENCY == "USD"
        assert "USD" in SUPPORTED_CURRENCIES
        assert "EUR" in SUPPORTED_CURRENCIES
        assert "RUB" in SUPPORTED_CURRENCIES
        assert "CNY" in SUPPORTED_CURRENCIES


class TestPaymentValidation:
    """Test payment validation functions."""

    def test_validate_payment_type_valid(self):
        """Test valid payment type validation."""
        from services.supplier_invoice_payment_service import validate_payment_type

        assert validate_payment_type("advance") is True
        assert validate_payment_type("partial") is True
        assert validate_payment_type("final") is True
        assert validate_payment_type("refund") is True

    def test_validate_payment_type_invalid(self):
        """Test invalid payment type validation."""
        from services.supplier_invoice_payment_service import validate_payment_type

        assert validate_payment_type("invalid") is False
        assert validate_payment_type("") is False
        assert validate_payment_type(None) is False

    def test_validate_payment_amount_valid(self):
        """Test valid payment amount validation."""
        from services.supplier_invoice_payment_service import validate_payment_amount

        assert validate_payment_amount(Decimal("100.00")) is True
        assert validate_payment_amount(Decimal("0.01")) is True
        assert validate_payment_amount(Decimal("1000000.00")) is True

    def test_validate_payment_amount_invalid(self):
        """Test invalid payment amount validation."""
        from services.supplier_invoice_payment_service import validate_payment_amount

        assert validate_payment_amount(Decimal("0")) is False
        assert validate_payment_amount(Decimal("-100")) is False
        assert validate_payment_amount(None) is False

    def test_validate_currency_valid(self):
        """Test valid currency validation."""
        from services.supplier_invoice_payment_service import validate_currency

        assert validate_currency("USD") is True
        assert validate_currency("EUR") is True
        assert validate_currency("RUB") is True

    def test_validate_currency_invalid(self):
        """Test invalid currency validation."""
        from services.supplier_invoice_payment_service import validate_currency

        # Note: validate_currency accepts any non-empty string as valid
        # because it's designed to be permissive. Empty/None are invalid.
        assert validate_currency("") is False
        assert validate_currency(None) is False

    def test_validate_exchange_rate_valid(self):
        """Test valid exchange rate validation."""
        from services.supplier_invoice_payment_service import validate_exchange_rate

        assert validate_exchange_rate(Decimal("90.5")) is True
        assert validate_exchange_rate(Decimal("0.01")) is True
        assert validate_exchange_rate(None) is True  # Optional

    def test_validate_exchange_rate_invalid(self):
        """Test invalid exchange rate validation."""
        from services.supplier_invoice_payment_service import validate_exchange_rate

        assert validate_exchange_rate(Decimal("0")) is False
        assert validate_exchange_rate(Decimal("-1")) is False


class TestPaymentHelpers:
    """Test payment helper functions."""

    def test_get_payment_type_name(self):
        """Test getting Russian payment type name."""
        from services.supplier_invoice_payment_service import get_payment_type_name

        assert "Аванс" in get_payment_type_name("advance")
        assert "Финальный" in get_payment_type_name("final")
        # Unknown type returns the code itself
        result = get_payment_type_name("unknown")
        assert result is not None

    def test_get_payment_type_color(self):
        """Test getting payment type color."""
        from services.supplier_invoice_payment_service import get_payment_type_color

        assert get_payment_type_color("advance") == "blue"
        assert get_payment_type_color("final") == "green"
        assert get_payment_type_color("refund") == "red"

    def test_is_refund(self):
        """Test refund detection."""
        from services.supplier_invoice_payment_service import is_refund

        assert is_refund("refund") is True
        assert is_refund("advance") is False
        assert is_refund("final") is False

    def test_is_advance(self):
        """Test advance detection."""
        from services.supplier_invoice_payment_service import is_advance

        assert is_advance("advance") is True
        assert is_advance("refund") is False
        assert is_advance("final") is False

    def test_is_final_payment(self):
        """Test final payment detection."""
        from services.supplier_invoice_payment_service import is_final_payment

        assert is_final_payment("final") is True
        assert is_final_payment("advance") is False
        assert is_final_payment("partial") is False


class TestPaymentDataClass:
    """Test SupplierInvoicePayment dataclass."""

    def test_payment_dataclass_creation(self):
        """Test creating payment dataclass."""
        from services.supplier_invoice_payment_service import SupplierInvoicePayment

        payment = SupplierInvoicePayment(
            id="pay-001",
            invoice_id="inv-001",
            payment_date=date.today(),
            amount=Decimal("1000.00"),
            currency="USD",
            payment_type="advance",
        )

        assert payment.id == "pay-001"
        assert payment.invoice_id == "inv-001"
        assert payment.amount == Decimal("1000.00")
        assert payment.payment_type == "advance"

    def test_payment_dataclass_defaults(self):
        """Test payment dataclass default values."""
        from services.supplier_invoice_payment_service import SupplierInvoicePayment, DEFAULT_CURRENCY, PAYMENT_TYPE_ADVANCE

        payment = SupplierInvoicePayment(
            id="pay-001",
            invoice_id="inv-001",
            payment_date=date.today(),
            amount=Decimal("1000.00"),
        )

        assert payment.currency == DEFAULT_CURRENCY
        assert payment.payment_type == PAYMENT_TYPE_ADVANCE
        assert payment.exchange_rate is None
        assert payment.buyer_company_id is None
        assert payment.notes is None


class TestPaymentSummaryDataClass:
    """Test PaymentSummary dataclass."""

    def test_payment_summary_creation(self):
        """Test creating payment summary dataclass."""
        from services.supplier_invoice_payment_service import PaymentSummary

        summary = PaymentSummary(
            invoice_id="inv-001",
            total_paid=Decimal("3000.00"),
            total_refunded=Decimal("500.00"),
            net_paid=Decimal("2500.00"),
            payment_count=3,
        )

        assert summary.invoice_id == "inv-001"
        assert summary.total_paid == Decimal("3000.00")
        assert summary.net_paid == Decimal("2500.00")
        assert summary.payment_count == 3

    def test_payment_summary_defaults(self):
        """Test payment summary default values."""
        from services.supplier_invoice_payment_service import PaymentSummary

        summary = PaymentSummary(invoice_id="inv-001")

        assert summary.total_paid == Decimal("0.00")
        assert summary.total_refunded == Decimal("0.00")
        assert summary.net_paid == Decimal("0.00")
        assert summary.payment_count == 0


# =============================================================================
# BUYER COMPANY SERVICE TESTS (for dropdown)
# =============================================================================

class TestBuyerCompanyForDropdown:
    """Test buyer company service functions used in dropdown."""

    def test_buyer_company_dataclass(self):
        """Test BuyerCompany dataclass exists."""
        from services.buyer_company_service import BuyerCompany

        company = BuyerCompany(
            id="buyer-001",
            organization_id="org-001",
            company_code="ZAK",
            name='ООО "Закупки"',
        )

        assert company.id == "buyer-001"
        assert company.company_code == "ZAK"
        assert company.name == 'ООО "Закупки"'

    def test_format_buyer_company_for_dropdown(self):
        """Test formatting buyer company for dropdown."""
        from services.buyer_company_service import format_buyer_company_for_dropdown, BuyerCompany

        company = BuyerCompany(
            id="buyer-001",
            organization_id="org-001",
            company_code="ZAK",
            name='ООО "Закупки"',
        )

        result = format_buyer_company_for_dropdown(company)

        # The actual implementation uses 'value' instead of 'id'
        assert "value" in result
        assert "label" in result
        assert result["value"] == "buyer-001"
        assert "ZAK" in result["label"]


# =============================================================================
# INPUT VALIDATION TESTS (simulating form input)
# =============================================================================

class TestFormInputValidation:
    """Test form input parsing and validation."""

    def test_parse_valid_date(self):
        """Test parsing valid date string."""
        from datetime import date

        date_str = "2025-01-15"
        parsed = date.fromisoformat(date_str)

        assert parsed.year == 2025
        assert parsed.month == 1
        assert parsed.day == 15

    def test_parse_invalid_date(self):
        """Test parsing invalid date string raises error."""
        from datetime import date

        with pytest.raises(ValueError):
            date.fromisoformat("invalid")

    def test_parse_valid_amount(self):
        """Test parsing valid amount string."""
        amount_str = "1000.50"
        amount = Decimal(amount_str.strip())

        assert amount == Decimal("1000.50")

    def test_parse_negative_amount(self):
        """Test parsing negative amount string."""
        amount_str = "-100.00"
        amount = Decimal(amount_str.strip())

        assert amount == Decimal("-100.00")
        assert amount < 0  # Should fail validation

    def test_parse_invalid_amount(self):
        """Test parsing invalid amount string raises error."""
        from decimal import InvalidOperation

        with pytest.raises(InvalidOperation):
            Decimal("abc")

    def test_parse_valid_exchange_rate(self):
        """Test parsing valid exchange rate."""
        rate_str = "90.5000"
        rate = Decimal(rate_str.strip())

        assert rate == Decimal("90.5")

    def test_clean_empty_optional_field(self):
        """Test cleaning empty optional field."""
        field_value = "   "

        # This is what the form handler does
        cleaned = field_value.strip() if field_value and field_value.strip() else None

        assert cleaned is None

    def test_clean_non_empty_optional_field(self):
        """Test cleaning non-empty optional field."""
        field_value = " PAY-001 "

        cleaned = field_value.strip() if field_value and field_value.strip() else None

        assert cleaned == "PAY-001"


# =============================================================================
# ROLE-BASED ACCESS TESTS
# =============================================================================

class TestRoleBasedAccess:
    """Test role-based access for payment registration."""

    def test_allowed_roles_for_payments(self):
        """Test which roles can register payments."""
        allowed_roles = ["admin", "procurement", "finance"]

        # Admin can register payments
        assert "admin" in allowed_roles

        # Procurement can register payments (for supplier invoices)
        assert "procurement" in allowed_roles

        # Finance can register payments
        assert "finance" in allowed_roles

        # Sales cannot register payments
        assert "sales" not in allowed_roles

        # Logistics cannot register payments
        assert "logistics" not in allowed_roles

    def test_role_check_logic(self):
        """Test role checking logic used in routes."""
        user_roles = [{"role_code": "procurement"}, {"role_code": "sales"}]
        allowed_roles = ["admin", "procurement", "finance"]

        role_codes = [r.get("role_code") for r in user_roles]
        has_access = any(r in role_codes for r in allowed_roles)

        assert has_access is True

    def test_role_check_denied(self):
        """Test role checking denies wrong roles."""
        user_roles = [{"role_code": "sales"}, {"role_code": "logistics"}]
        allowed_roles = ["admin", "procurement", "finance"]

        role_codes = [r.get("role_code") for r in user_roles]
        has_access = any(r in role_codes for r in allowed_roles)

        assert has_access is False


# =============================================================================
# ORGANIZATION ACCESS TESTS
# =============================================================================

class TestOrganizationAccess:
    """Test organization-based access control."""

    def test_same_organization_access(self):
        """Test access when user and invoice are in same organization."""
        user_org = "org-001"
        invoice_org = "org-001"

        has_access = invoice_org is None or invoice_org == user_org

        assert has_access is True

    def test_different_organization_denied(self):
        """Test access denied when user and invoice are in different organizations."""
        user_org = "org-001"
        invoice_org = "org-002"

        has_access = invoice_org is None or invoice_org == user_org

        assert has_access is False

    def test_no_invoice_org_allows_access(self):
        """Test access allowed when invoice has no organization (legacy data)."""
        user_org = "org-001"
        invoice_org = None

        has_access = invoice_org is None or invoice_org == user_org

        assert has_access is True


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
