"""
Tests for Supplier Invoice Payment Service (Feature API-011)

Tests cover:
- Payment registration (advance, partial, final, refund)
- Payment retrieval with and without details
- Payment updates
- Payment deletion
- Summary and statistics functions
- Utility functions
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from services.supplier_invoice_payment_service import (
    # Data classes
    SupplierInvoicePayment,
    PaymentSummary,
    SupplierPaymentSummary,
    BuyerCompanyPaymentSummary,
    # Constants
    PAYMENT_TYPE_ADVANCE,
    PAYMENT_TYPE_PARTIAL,
    PAYMENT_TYPE_FINAL,
    PAYMENT_TYPE_REFUND,
    PAYMENT_TYPES,
    PAYMENT_TYPE_NAMES,
    PAYMENT_TYPE_COLORS,
    DEFAULT_CURRENCY,
    SUPPORTED_CURRENCIES,
    # Validation functions
    validate_payment_type,
    validate_payment_amount,
    validate_exchange_rate,
    validate_currency,
    validate_payment_document,
    # Payment type helpers
    get_payment_type_name,
    get_payment_type_color,
    is_refund,
    is_advance,
    is_final_payment,
    # Create operations
    register_payment,
    register_advance_payment,
    register_final_payment,
    register_refund,
    # Read operations
    get_payment,
    get_payment_with_details,
    get_payments_for_invoice,
    get_payments_for_invoice_with_details,
    get_all_payments,
    count_payments,
    get_recent_payments,
    get_payments_by_buyer_company,
    get_refunds_for_invoice,
    # Update operations
    update_payment,
    update_payment_document,
    update_payment_exchange_rate,
    # Delete operations
    delete_payment,
    delete_all_payments_for_invoice,
    # Summary and statistics
    get_invoice_payment_summary,
    get_supplier_payment_summary,
    get_payments_summary_by_buyer_company,
    get_payment_stats,
    # Utility functions
    get_remaining_amount,
    is_invoice_fully_paid,
    format_payment_for_display,
    get_payments_for_display,
    # Parsing
    _parse_payment,
    _parse_date,
    _parse_datetime,
    _parse_decimal,
)


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

class TestConstants:
    """Test payment type constants."""

    def test_payment_types_defined(self):
        """Test that all payment types are defined."""
        assert len(PAYMENT_TYPES) == 4
        assert PAYMENT_TYPE_ADVANCE in PAYMENT_TYPES
        assert PAYMENT_TYPE_PARTIAL in PAYMENT_TYPES
        assert PAYMENT_TYPE_FINAL in PAYMENT_TYPES
        assert PAYMENT_TYPE_REFUND in PAYMENT_TYPES

    def test_payment_type_values(self):
        """Test payment type string values."""
        assert PAYMENT_TYPE_ADVANCE == "advance"
        assert PAYMENT_TYPE_PARTIAL == "partial"
        assert PAYMENT_TYPE_FINAL == "final"
        assert PAYMENT_TYPE_REFUND == "refund"

    def test_payment_type_names(self):
        """Test localized names exist for all types."""
        for ptype in PAYMENT_TYPES:
            assert ptype in PAYMENT_TYPE_NAMES
            assert len(PAYMENT_TYPE_NAMES[ptype]) > 0

    def test_payment_type_colors(self):
        """Test colors exist for all types."""
        for ptype in PAYMENT_TYPES:
            assert ptype in PAYMENT_TYPE_COLORS
            assert PAYMENT_TYPE_COLORS[ptype] in ["blue", "yellow", "green", "red", "gray"]

    def test_supported_currencies(self):
        """Test supported currencies."""
        assert "USD" in SUPPORTED_CURRENCIES
        assert "EUR" in SUPPORTED_CURRENCIES
        assert "RUB" in SUPPORTED_CURRENCIES
        assert "CNY" in SUPPORTED_CURRENCIES
        assert DEFAULT_CURRENCY == "USD"


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestValidation:
    """Test validation functions."""

    def test_validate_payment_type_valid(self):
        """Test valid payment types."""
        assert validate_payment_type("advance") is True
        assert validate_payment_type("partial") is True
        assert validate_payment_type("final") is True
        assert validate_payment_type("refund") is True

    def test_validate_payment_type_invalid(self):
        """Test invalid payment types."""
        assert validate_payment_type("invalid") is False
        assert validate_payment_type("") is False
        assert validate_payment_type("ADVANCE") is False  # Case sensitive

    def test_validate_payment_amount_valid(self):
        """Test valid payment amounts."""
        assert validate_payment_amount(100) is True
        assert validate_payment_amount(Decimal("100.50")) is True
        assert validate_payment_amount("100") is True
        assert validate_payment_amount(0.01) is True

    def test_validate_payment_amount_invalid(self):
        """Test invalid payment amounts."""
        assert validate_payment_amount(0) is False
        assert validate_payment_amount(-100) is False
        assert validate_payment_amount("abc") is False
        assert validate_payment_amount(None) is False

    def test_validate_exchange_rate_valid(self):
        """Test valid exchange rates."""
        assert validate_exchange_rate(None) is True  # Optional
        assert validate_exchange_rate(95.50) is True
        assert validate_exchange_rate(Decimal("95.50")) is True
        assert validate_exchange_rate(0.01) is True

    def test_validate_exchange_rate_invalid(self):
        """Test invalid exchange rates."""
        assert validate_exchange_rate(0) is False
        assert validate_exchange_rate(-1) is False
        assert validate_exchange_rate("abc") is False

    def test_validate_currency_valid(self):
        """Test valid currency codes."""
        assert validate_currency("USD") is True
        assert validate_currency("EUR") is True
        assert validate_currency("RUB") is True
        assert validate_currency("CNY") is True

    def test_validate_currency_invalid(self):
        """Test invalid currency codes."""
        assert validate_currency("") is False
        assert validate_currency("US") is False  # Too short
        assert validate_currency("USDD") is False  # Too long
        assert validate_currency("123") is False  # Not letters
        assert validate_currency("usd") is False  # Not uppercase

    def test_validate_payment_document_valid(self):
        """Test valid payment documents."""
        assert validate_payment_document(None) is True  # Optional
        assert validate_payment_document("") is True  # Optional
        assert validate_payment_document("PAY-2025-001") is True
        assert validate_payment_document("123456") is True

    def test_validate_payment_document_invalid(self):
        """Test invalid payment documents."""
        assert validate_payment_document("   ") is False  # Only whitespace
        assert validate_payment_document("x" * 101) is False  # Too long


# =============================================================================
# PAYMENT TYPE HELPER TESTS
# =============================================================================

class TestPaymentTypeHelpers:
    """Test payment type helper functions."""

    def test_get_payment_type_name(self):
        """Test getting localized name."""
        assert get_payment_type_name("advance") == "Аванс"
        assert get_payment_type_name("partial") == "Частичная оплата"
        assert get_payment_type_name("final") == "Финальный платеж"
        assert get_payment_type_name("refund") == "Возврат"

    def test_get_payment_type_name_unknown(self):
        """Test getting name for unknown type."""
        assert get_payment_type_name("unknown") == "unknown"

    def test_get_payment_type_color(self):
        """Test getting color."""
        assert get_payment_type_color("advance") == "blue"
        assert get_payment_type_color("partial") == "yellow"
        assert get_payment_type_color("final") == "green"
        assert get_payment_type_color("refund") == "red"
        assert get_payment_type_color("unknown") == "gray"

    def test_is_refund(self):
        """Test refund detection."""
        assert is_refund("refund") is True
        assert is_refund("advance") is False
        assert is_refund("partial") is False
        assert is_refund("final") is False

    def test_is_advance(self):
        """Test advance detection."""
        assert is_advance("advance") is True
        assert is_advance("refund") is False
        assert is_advance("partial") is False

    def test_is_final_payment(self):
        """Test final payment detection."""
        assert is_final_payment("final") is True
        assert is_final_payment("advance") is False
        assert is_final_payment("partial") is False


# =============================================================================
# PARSING TESTS
# =============================================================================

class TestParsing:
    """Test parsing functions."""

    def test_parse_date_from_string(self):
        """Test parsing date from string."""
        result = _parse_date("2025-01-15")
        assert result == date(2025, 1, 15)

    def test_parse_date_from_datetime_string(self):
        """Test parsing date from datetime string."""
        result = _parse_date("2025-01-15T10:30:00")
        assert result == date(2025, 1, 15)

    def test_parse_date_from_date(self):
        """Test parsing date from date object."""
        result = _parse_date(date(2025, 1, 15))
        assert result == date(2025, 1, 15)

    def test_parse_date_none(self):
        """Test parsing None date."""
        assert _parse_date(None) is None

    def test_parse_datetime_from_string(self):
        """Test parsing datetime from string."""
        result = _parse_datetime("2025-01-15T10:30:00Z")
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_datetime_none(self):
        """Test parsing None datetime."""
        assert _parse_datetime(None) is None

    def test_parse_decimal_from_string(self):
        """Test parsing decimal from string."""
        result = _parse_decimal("100.50")
        assert result == Decimal("100.50")

    def test_parse_decimal_from_number(self):
        """Test parsing decimal from number."""
        result = _parse_decimal(100.50)
        assert result == Decimal("100.5")

    def test_parse_decimal_none(self):
        """Test parsing None decimal."""
        assert _parse_decimal(None) == Decimal("0.00")

    def test_parse_payment(self):
        """Test parsing payment from dict."""
        data = {
            "id": "pay-uuid-123",
            "invoice_id": "inv-uuid-456",
            "payment_date": "2025-01-15",
            "amount": "2500.00",
            "currency": "USD",
            "exchange_rate": "95.50",
            "payment_type": "advance",
            "buyer_company_id": "buyer-uuid",
            "payment_document": "PAY-001",
            "notes": "Test payment",
            "created_at": "2025-01-15T10:00:00Z",
            "supplier_name": "Test Supplier",
        }

        payment = _parse_payment(data)

        assert payment.id == "pay-uuid-123"
        assert payment.invoice_id == "inv-uuid-456"
        assert payment.payment_date == date(2025, 1, 15)
        assert payment.amount == Decimal("2500.00")
        assert payment.currency == "USD"
        assert payment.exchange_rate == Decimal("95.50")
        assert payment.payment_type == "advance"
        assert payment.buyer_company_id == "buyer-uuid"
        assert payment.payment_document == "PAY-001"
        assert payment.notes == "Test payment"
        assert payment.supplier_name == "Test Supplier"


# =============================================================================
# DATA CLASS TESTS
# =============================================================================

class TestDataClasses:
    """Test data class initialization."""

    def test_payment_defaults(self):
        """Test SupplierInvoicePayment default values."""
        payment = SupplierInvoicePayment(
            id="test-id",
            invoice_id="invoice-id",
            payment_date=date(2025, 1, 15),
            amount=Decimal("1000.00"),
        )

        assert payment.currency == DEFAULT_CURRENCY
        assert payment.exchange_rate is None
        assert payment.payment_type == PAYMENT_TYPE_ADVANCE
        assert payment.buyer_company_id is None
        assert payment.payment_document is None

    def test_payment_summary_defaults(self):
        """Test PaymentSummary default values."""
        summary = PaymentSummary(invoice_id="test-id")

        assert summary.total_paid == Decimal("0.00")
        assert summary.total_refunded == Decimal("0.00")
        assert summary.net_paid == Decimal("0.00")
        assert summary.payment_count == 0
        assert summary.last_payment_date is None

    def test_supplier_payment_summary_defaults(self):
        """Test SupplierPaymentSummary default values."""
        summary = SupplierPaymentSummary(supplier_id="test-id")

        assert summary.total_invoiced == Decimal("0.00")
        assert summary.outstanding == Decimal("0.00")
        assert summary.invoice_count == 0
        assert summary.payment_count == 0


# =============================================================================
# REGISTER PAYMENT TESTS (with mocking)
# =============================================================================

class TestRegisterPayment:
    """Test payment registration functions."""

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_register_payment_success(self, mock_get_supabase):
        """Test successful payment registration."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "new-payment-id",
            "invoice_id": "inv-123",
            "payment_date": "2025-01-15",
            "amount": "2500.00",
            "currency": "USD",
            "payment_type": "advance",
        }]

        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = register_payment(
            invoice_id="inv-123",
            payment_date=date(2025, 1, 15),
            amount=Decimal("2500.00"),
            payment_type="advance",
        )

        assert result is not None
        assert result.id == "new-payment-id"
        assert result.amount == Decimal("2500.00")

    def test_register_payment_invalid_amount(self):
        """Test registration with invalid amount."""
        with pytest.raises(ValueError, match="Invalid payment amount"):
            register_payment(
                invoice_id="inv-123",
                payment_date=date(2025, 1, 15),
                amount=Decimal("-100"),
            )

    def test_register_payment_invalid_type(self):
        """Test registration with invalid payment type."""
        with pytest.raises(ValueError, match="Invalid payment type"):
            register_payment(
                invoice_id="inv-123",
                payment_date=date(2025, 1, 15),
                amount=Decimal("100"),
                payment_type="invalid",
            )

    def test_register_payment_invalid_currency(self):
        """Test registration with invalid currency."""
        with pytest.raises(ValueError, match="Invalid currency"):
            register_payment(
                invoice_id="inv-123",
                payment_date=date(2025, 1, 15),
                amount=Decimal("100"),
                currency="usd",  # lowercase
            )

    def test_register_payment_invalid_exchange_rate(self):
        """Test registration with invalid exchange rate."""
        with pytest.raises(ValueError, match="Invalid exchange rate"):
            register_payment(
                invoice_id="inv-123",
                payment_date=date(2025, 1, 15),
                amount=Decimal("100"),
                exchange_rate=Decimal("-1"),
            )

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_register_advance_payment(self, mock_get_supabase):
        """Test advance payment convenience function."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-id",
            "invoice_id": "inv-123",
            "payment_date": "2025-01-15",
            "amount": "1000.00",
            "currency": "USD",
            "payment_type": "advance",
        }]

        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = register_advance_payment(
            invoice_id="inv-123",
            payment_date=date(2025, 1, 15),
            amount=Decimal("1000.00"),
        )

        assert result.payment_type == "advance"

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_register_final_payment(self, mock_get_supabase):
        """Test final payment convenience function."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-id",
            "invoice_id": "inv-123",
            "payment_date": "2025-01-15",
            "amount": "1000.00",
            "currency": "USD",
            "payment_type": "final",
        }]

        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = register_final_payment(
            invoice_id="inv-123",
            payment_date=date(2025, 1, 15),
            amount=Decimal("1000.00"),
        )

        assert result.payment_type == "final"

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_register_refund(self, mock_get_supabase):
        """Test refund registration."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-id",
            "invoice_id": "inv-123",
            "payment_date": "2025-01-15",
            "amount": "500.00",
            "currency": "USD",
            "payment_type": "refund",
        }]

        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = register_refund(
            invoice_id="inv-123",
            payment_date=date(2025, 1, 15),
            amount=Decimal("500.00"),
            notes="Product returned",
        )

        assert result.payment_type == "refund"


# =============================================================================
# READ OPERATIONS TESTS
# =============================================================================

class TestReadOperations:
    """Test payment read operations."""

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_payment(self, mock_get_supabase):
        """Test getting payment by ID."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-123",
            "invoice_id": "inv-456",
            "payment_date": "2025-01-15",
            "amount": "1000.00",
            "currency": "USD",
            "payment_type": "advance",
        }]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = get_payment("pay-123")

        assert result is not None
        assert result.id == "pay-123"

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_payment_not_found(self, mock_get_supabase):
        """Test getting non-existent payment."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = []

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = get_payment("non-existent")

        assert result is None

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_payments_for_invoice(self, mock_get_supabase):
        """Test getting all payments for an invoice."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [
            {
                "id": "pay-1",
                "invoice_id": "inv-123",
                "payment_date": "2025-01-10",
                "amount": "500.00",
                "currency": "USD",
                "payment_type": "advance",
            },
            {
                "id": "pay-2",
                "invoice_id": "inv-123",
                "payment_date": "2025-01-15",
                "amount": "500.00",
                "currency": "USD",
                "payment_type": "final",
            },
        ]

        mock_client.table.return_value.select.return_value.eq.return_value\
            .order.return_value.order.return_value.execute.return_value = mock_response

        result = get_payments_for_invoice("inv-123")

        assert len(result) == 2
        assert result[0].id == "pay-1"
        assert result[1].id == "pay-2"

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_count_payments(self, mock_get_supabase):
        """Test counting payments."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.count = 5

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = count_payments("org-123")

        assert result == 5

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_refunds_for_invoice(self, mock_get_supabase):
        """Test getting refunds only."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [
            {
                "id": "pay-1",
                "invoice_id": "inv-123",
                "payment_date": "2025-01-15",
                "amount": "200.00",
                "currency": "USD",
                "payment_type": "refund",
            },
        ]

        mock_client.table.return_value.select.return_value.eq.return_value\
            .eq.return_value.order.return_value.execute.return_value = mock_response

        result = get_refunds_for_invoice("inv-123")

        assert len(result) == 1
        assert result[0].payment_type == "refund"


# =============================================================================
# UPDATE OPERATIONS TESTS
# =============================================================================

class TestUpdateOperations:
    """Test payment update operations."""

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_update_payment(self, mock_get_supabase):
        """Test updating a payment."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-123",
            "invoice_id": "inv-456",
            "payment_date": "2025-01-20",
            "amount": "1500.00",
            "currency": "USD",
            "payment_type": "partial",
        }]

        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response

        result = update_payment(
            "pay-123",
            amount=Decimal("1500.00"),
            payment_type="partial",
        )

        assert result is not None
        assert result.amount == Decimal("1500.00")

    def test_update_payment_invalid_amount(self):
        """Test update with invalid amount."""
        with pytest.raises(ValueError, match="Invalid payment amount"):
            update_payment("pay-123", amount=Decimal("-100"))

    def test_update_payment_invalid_type(self):
        """Test update with invalid type."""
        with pytest.raises(ValueError, match="Invalid payment type"):
            update_payment("pay-123", payment_type="invalid")

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_update_payment_document(self, mock_get_supabase):
        """Test updating payment document."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-123",
            "invoice_id": "inv-456",
            "payment_date": "2025-01-15",
            "amount": "1000.00",
            "currency": "USD",
            "payment_type": "advance",
            "payment_document": "NEW-DOC-001",
        }]

        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response

        result = update_payment_document("pay-123", "NEW-DOC-001")

        assert result.payment_document == "NEW-DOC-001"

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_update_exchange_rate(self, mock_get_supabase):
        """Test updating exchange rate."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-123",
            "invoice_id": "inv-456",
            "payment_date": "2025-01-15",
            "amount": "1000.00",
            "currency": "USD",
            "payment_type": "advance",
            "exchange_rate": "96.50",
        }]

        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response

        result = update_payment_exchange_rate("pay-123", Decimal("96.50"))

        assert result.exchange_rate == Decimal("96.50")


# =============================================================================
# DELETE OPERATIONS TESTS
# =============================================================================

class TestDeleteOperations:
    """Test payment delete operations."""

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_delete_payment(self, mock_get_supabase):
        """Test deleting a payment."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = Mock()

        result = delete_payment("pay-123")

        assert result is True

    @patch('services.supplier_invoice_payment_service.get_payments_for_invoice')
    @patch('services.supplier_invoice_payment_service.delete_payment')
    def test_delete_all_payments_for_invoice(self, mock_delete, mock_get_payments):
        """Test deleting all payments for an invoice."""
        mock_get_payments.return_value = [
            SupplierInvoicePayment(id="pay-1", invoice_id="inv-123", payment_date=date(2025, 1, 15), amount=Decimal("500")),
            SupplierInvoicePayment(id="pay-2", invoice_id="inv-123", payment_date=date(2025, 1, 20), amount=Decimal("500")),
        ]
        mock_delete.return_value = True

        result = delete_all_payments_for_invoice("inv-123")

        assert result == 2
        assert mock_delete.call_count == 2


# =============================================================================
# SUMMARY AND STATISTICS TESTS
# =============================================================================

class TestSummaryAndStatistics:
    """Test summary and statistics functions."""

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_invoice_payment_summary(self, mock_get_supabase):
        """Test getting invoice payment summary via RPC."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "invoice_id": "inv-123",
            "total_paid": "1500.00",
            "total_refunded": "200.00",
            "net_paid": "1300.00",
            "payment_count": 3,
            "last_payment_date": "2025-01-20",
            "advance_amount": "500.00",
            "partial_amount": "500.00",
            "final_amount": "500.00",
        }]

        mock_client.rpc.return_value.execute.return_value = mock_response

        result = get_invoice_payment_summary("inv-123")

        assert result.total_paid == Decimal("1500.00")
        assert result.total_refunded == Decimal("200.00")
        assert result.net_paid == Decimal("1300.00")
        assert result.payment_count == 3

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_supplier_payment_summary(self, mock_get_supabase):
        """Test getting supplier payment summary."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [{
            "supplier_id": "sup-123",
            "total_invoiced": "10000.00",
            "total_paid": "7000.00",
            "total_refunded": "500.00",
            "net_paid": "6500.00",
            "outstanding": "3500.00",
            "invoice_count": 5,
            "payment_count": 10,
        }]

        mock_client.rpc.return_value.execute.return_value = mock_response

        result = get_supplier_payment_summary("sup-123")

        assert result.total_invoiced == Decimal("10000.00")
        assert result.outstanding == Decimal("3500.00")
        assert result.invoice_count == 5

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_payments_summary_by_buyer_company(self, mock_get_supabase):
        """Test getting buyer company summaries."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [
            {
                "buyer_company_id": "buyer-1",
                "buyer_company_name": "Company A",
                "buyer_company_code": "CMA",
                "total_amount": "5000.00",
                "payment_count": 10,
                "currency": "USD",
            },
            {
                "buyer_company_id": "buyer-2",
                "buyer_company_name": "Company B",
                "buyer_company_code": "CMB",
                "total_amount": "3000.00",
                "payment_count": 5,
                "currency": "USD",
            },
        ]

        mock_client.rpc.return_value.execute.return_value = mock_response

        result = get_payments_summary_by_buyer_company("org-123")

        assert len(result) == 2
        assert result[0].total_amount == Decimal("5000.00")

    @patch('services.supplier_invoice_payment_service.get_all_payments')
    def test_get_payment_stats(self, mock_get_all):
        """Test getting overall payment statistics."""
        mock_get_all.return_value = [
            SupplierInvoicePayment(id="1", invoice_id="i1", payment_date=date(2025, 1, 15),
                                   amount=Decimal("1000"), payment_type="advance", currency="USD"),
            SupplierInvoicePayment(id="2", invoice_id="i1", payment_date=date(2025, 1, 20),
                                   amount=Decimal("500"), payment_type="partial", currency="USD"),
            SupplierInvoicePayment(id="3", invoice_id="i1", payment_date=date(2025, 1, 25),
                                   amount=Decimal("200"), payment_type="refund", currency="USD"),
        ]

        stats = get_payment_stats("org-123")

        assert stats["total_payments"] == 3
        assert stats["total_amount"] == Decimal("1500.00")
        assert stats["total_refunds"] == Decimal("200.00")
        assert stats["net_amount"] == Decimal("1300.00")
        assert stats["by_type"]["advance"]["count"] == 1
        assert stats["by_type"]["refund"]["amount"] == Decimal("200.00")


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

class TestUtilityFunctions:
    """Test utility functions."""

    @patch('services.supplier_invoice_payment_service.get_invoice_payment_summary')
    def test_get_remaining_amount(self, mock_get_summary):
        """Test calculating remaining amount."""
        mock_get_summary.return_value = PaymentSummary(
            invoice_id="inv-123",
            net_paid=Decimal("3000.00"),
        )

        remaining = get_remaining_amount("inv-123", Decimal("5000.00"))

        assert remaining == Decimal("2000.00")

    @patch('services.supplier_invoice_payment_service.get_remaining_amount')
    def test_is_invoice_fully_paid_true(self, mock_remaining):
        """Test fully paid check - true case."""
        mock_remaining.return_value = Decimal("0.00")

        result = is_invoice_fully_paid("inv-123", Decimal("5000.00"))

        assert result is True

    @patch('services.supplier_invoice_payment_service.get_remaining_amount')
    def test_is_invoice_fully_paid_false(self, mock_remaining):
        """Test fully paid check - false case."""
        mock_remaining.return_value = Decimal("1000.00")

        result = is_invoice_fully_paid("inv-123", Decimal("5000.00"))

        assert result is False

    def test_format_payment_for_display(self):
        """Test formatting payment for display."""
        payment = SupplierInvoicePayment(
            id="pay-123",
            invoice_id="inv-456",
            payment_date=date(2025, 1, 15),
            amount=Decimal("2500.50"),
            currency="USD",
            exchange_rate=Decimal("95.5000"),
            payment_type="advance",
            buyer_company_id="buyer-789",
            buyer_company_name="Test Buyer",
            buyer_company_code="TBY",
            payment_document="PAY-001",
            supplier_name="Test Supplier",
            amount_rub=Decimal("238922.75"),
        )

        formatted = format_payment_for_display(payment)

        assert formatted["id"] == "pay-123"
        assert formatted["amount"] == "2,500.50"
        assert formatted["amount_numeric"] == 2500.5
        assert formatted["payment_type_name"] == "Аванс"
        assert formatted["payment_type_color"] == "blue"
        assert formatted["is_refund"] is False
        assert formatted["buyer_company_name"] == "Test Buyer"
        assert formatted["amount_rub"] == "238,922.75"

    def test_format_payment_for_display_refund(self):
        """Test formatting refund payment."""
        payment = SupplierInvoicePayment(
            id="pay-123",
            invoice_id="inv-456",
            payment_date=date(2025, 1, 15),
            amount=Decimal("500.00"),
            payment_type="refund",
        )

        formatted = format_payment_for_display(payment)

        assert formatted["is_refund"] is True
        assert formatted["payment_type_color"] == "red"

    @patch('services.supplier_invoice_payment_service.get_payments_for_invoice_with_details')
    def test_get_payments_for_display(self, mock_get_payments):
        """Test getting multiple payments formatted."""
        mock_get_payments.return_value = [
            SupplierInvoicePayment(
                id="pay-1", invoice_id="inv-123", payment_date=date(2025, 1, 15),
                amount=Decimal("1000"), payment_type="advance"
            ),
            SupplierInvoicePayment(
                id="pay-2", invoice_id="inv-123", payment_date=date(2025, 1, 20),
                amount=Decimal("500"), payment_type="partial"
            ),
        ]

        result = get_payments_for_display("inv-123")

        assert len(result) == 2
        assert result[0]["id"] == "pay-1"
        assert result[1]["id"] == "pay-2"


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_payment_exception_handling(self, mock_get_supabase):
        """Test exception handling in get_payment."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = get_payment("pay-123")

        assert result is None

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_get_payments_for_invoice_empty(self, mock_get_supabase):
        """Test getting payments for invoice with no payments."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        mock_response = Mock()
        mock_response.data = None

        mock_client.table.return_value.select.return_value.eq.return_value\
            .order.return_value.order.return_value.execute.return_value = mock_response

        result = get_payments_for_invoice("inv-123")

        assert result == []

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_count_payments_exception(self, mock_get_supabase):
        """Test count exception returns 0."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = count_payments("org-123")

        assert result == 0

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_delete_payment_exception(self, mock_get_supabase):
        """Test delete exception returns False."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = delete_payment("pay-123")

        assert result is False

    @patch('services.supplier_invoice_payment_service._get_supabase')
    def test_update_payment_no_changes(self, mock_get_supabase):
        """Test update with no changes returns current payment."""
        mock_client = Mock()
        mock_get_supabase.return_value = mock_client

        # Mock get_payment for "no changes" path
        mock_response = Mock()
        mock_response.data = [{
            "id": "pay-123",
            "invoice_id": "inv-456",
            "payment_date": "2025-01-15",
            "amount": "1000.00",
            "currency": "USD",
            "payment_type": "advance",
        }]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        # Call with no actual updates
        result = update_payment("pay-123")

        assert result is not None
        assert result.id == "pay-123"
