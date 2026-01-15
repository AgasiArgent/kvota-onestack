"""
Tests for Supplier Invoice Service (API-010)

Tests cover:
- Data class creation and parsing
- Validation functions
- Invoice CRUD operations
- Invoice item operations
- Status management
- Utility functions
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
import uuid

# Import service under test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.supplier_invoice_service import (
    # Data classes
    SupplierInvoice,
    SupplierInvoiceItem,
    InvoiceSummary,
    # Constants
    INVOICE_STATUS_PENDING,
    INVOICE_STATUS_PARTIALLY_PAID,
    INVOICE_STATUS_PAID,
    INVOICE_STATUS_OVERDUE,
    INVOICE_STATUS_CANCELLED,
    INVOICE_STATUSES,
    INVOICE_STATUS_NAMES,
    INVOICE_STATUS_COLORS,
    DEFAULT_CURRENCY,
    SUPPORTED_CURRENCIES,
    # Validation functions
    validate_invoice_number,
    validate_invoice_status,
    validate_currency,
    validate_amount,
    # Status helpers
    get_invoice_status_name,
    get_invoice_status_color,
    is_invoice_payable,
    is_invoice_editable,
    # Parsing
    _parse_date,
    _parse_datetime,
    _parse_decimal,
    _parse_invoice,
    _parse_invoice_item,
    # CRUD functions
    create_invoice,
    get_invoice,
    get_invoice_by_number,
    get_invoices_for_supplier,
    get_all_invoices,
    count_invoices,
    search_invoices,
    invoice_exists,
    update_invoice,
    update_invoice_status,
    cancel_invoice,
    delete_invoice,
    # Item functions
    add_invoice_item,
    get_invoice_item,
    get_invoice_items,
    update_invoice_item,
    delete_invoice_item,
    # Utility
    get_invoice_summary,
    format_invoice_for_display,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    with patch('services.supplier_invoice_service._get_supabase') as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_org_id():
    """Sample organization ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_supplier_id():
    """Sample supplier ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_invoice_data(sample_org_id, sample_supplier_id):
    """Sample invoice database row."""
    return {
        "id": str(uuid.uuid4()),
        "organization_id": sample_org_id,
        "supplier_id": sample_supplier_id,
        "invoice_number": "INV-2025-001",
        "invoice_date": "2025-01-15",
        "due_date": "2025-02-15",
        "total_amount": "5000.00",
        "currency": "USD",
        "status": INVOICE_STATUS_PENDING,
        "notes": "Test invoice",
        "invoice_file_url": None,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "created_by": str(uuid.uuid4()),
    }


@pytest.fixture
def sample_invoice_item_data():
    """Sample invoice item database row."""
    return {
        "id": str(uuid.uuid4()),
        "invoice_id": str(uuid.uuid4()),
        "quote_item_id": str(uuid.uuid4()),
        "description": "Product A",
        "quantity": "100.00",
        "unit_price": "50.0000",
        "total_price": "5000.00",
        "unit": "pcs",
        "created_at": "2025-01-15T10:00:00Z",
    }


# =============================================================================
# TEST: Constants
# =============================================================================

class TestConstants:
    """Test invoice constants."""

    def test_invoice_statuses_list(self):
        """Test that all statuses are defined."""
        assert len(INVOICE_STATUSES) == 5
        assert INVOICE_STATUS_PENDING in INVOICE_STATUSES
        assert INVOICE_STATUS_PARTIALLY_PAID in INVOICE_STATUSES
        assert INVOICE_STATUS_PAID in INVOICE_STATUSES
        assert INVOICE_STATUS_OVERDUE in INVOICE_STATUSES
        assert INVOICE_STATUS_CANCELLED in INVOICE_STATUSES

    def test_status_names_defined(self):
        """Test that all statuses have names."""
        for status in INVOICE_STATUSES:
            assert status in INVOICE_STATUS_NAMES

    def test_status_colors_defined(self):
        """Test that all statuses have colors."""
        for status in INVOICE_STATUSES:
            assert status in INVOICE_STATUS_COLORS

    def test_default_currency(self):
        """Test default currency is USD."""
        assert DEFAULT_CURRENCY == "USD"

    def test_supported_currencies(self):
        """Test supported currencies list."""
        assert "USD" in SUPPORTED_CURRENCIES
        assert "EUR" in SUPPORTED_CURRENCIES
        assert "RUB" in SUPPORTED_CURRENCIES
        assert "CNY" in SUPPORTED_CURRENCIES


# =============================================================================
# TEST: Validation Functions
# =============================================================================

class TestValidationFunctions:
    """Test validation functions."""

    def test_validate_invoice_number_valid(self):
        """Test valid invoice numbers."""
        assert validate_invoice_number("INV-2025-001") is True
        assert validate_invoice_number("123") is True
        assert validate_invoice_number("A") is True

    def test_validate_invoice_number_invalid(self):
        """Test invalid invoice numbers."""
        assert validate_invoice_number("") is False
        assert validate_invoice_number(None) is False
        assert validate_invoice_number("   ") is False
        assert validate_invoice_number("A" * 101) is False  # Too long

    def test_validate_invoice_status_valid(self):
        """Test valid statuses."""
        for status in INVOICE_STATUSES:
            assert validate_invoice_status(status) is True

    def test_validate_invoice_status_invalid(self):
        """Test invalid statuses."""
        assert validate_invoice_status("invalid") is False
        assert validate_invoice_status("") is False
        assert validate_invoice_status(None) is False

    def test_validate_currency_valid(self):
        """Test valid currency codes."""
        assert validate_currency("USD") is True
        assert validate_currency("EUR") is True
        assert validate_currency("RUB") is True
        assert validate_currency("CNY") is True

    def test_validate_currency_invalid(self):
        """Test invalid currency codes."""
        assert validate_currency("") is False
        assert validate_currency(None) is False
        assert validate_currency("usd") is False  # Lowercase
        assert validate_currency("US") is False  # Too short
        assert validate_currency("USDD") is False  # Too long
        assert validate_currency("123") is False  # Numbers

    def test_validate_amount_valid(self):
        """Test valid amounts."""
        assert validate_amount(100) is True
        assert validate_amount(0.01) is True
        assert validate_amount("1000.50") is True
        assert validate_amount(Decimal("5000.00")) is True

    def test_validate_amount_invalid(self):
        """Test invalid amounts."""
        assert validate_amount(0) is False
        assert validate_amount(-100) is False
        assert validate_amount("invalid") is False
        assert validate_amount(None) is False


# =============================================================================
# TEST: Status Helper Functions
# =============================================================================

class TestStatusHelpers:
    """Test status helper functions."""

    def test_get_invoice_status_name(self):
        """Test getting status name."""
        assert get_invoice_status_name(INVOICE_STATUS_PENDING) == "Ожидает оплаты"
        assert get_invoice_status_name(INVOICE_STATUS_PAID) == "Оплачен"
        assert get_invoice_status_name("unknown") == "unknown"  # Returns input if unknown

    def test_get_invoice_status_color(self):
        """Test getting status color."""
        assert get_invoice_status_color(INVOICE_STATUS_PENDING) == "yellow"
        assert get_invoice_status_color(INVOICE_STATUS_PAID) == "green"
        assert get_invoice_status_color(INVOICE_STATUS_OVERDUE) == "red"
        assert get_invoice_status_color("unknown") == "gray"

    def test_is_invoice_payable(self):
        """Test payable status check."""
        assert is_invoice_payable(INVOICE_STATUS_PENDING) is True
        assert is_invoice_payable(INVOICE_STATUS_PARTIALLY_PAID) is True
        assert is_invoice_payable(INVOICE_STATUS_OVERDUE) is True
        assert is_invoice_payable(INVOICE_STATUS_PAID) is False
        assert is_invoice_payable(INVOICE_STATUS_CANCELLED) is False

    def test_is_invoice_editable(self):
        """Test editable status check."""
        assert is_invoice_editable(INVOICE_STATUS_PENDING) is True
        assert is_invoice_editable(INVOICE_STATUS_PARTIALLY_PAID) is True
        assert is_invoice_editable(INVOICE_STATUS_OVERDUE) is True
        assert is_invoice_editable(INVOICE_STATUS_PAID) is False
        assert is_invoice_editable(INVOICE_STATUS_CANCELLED) is False


# =============================================================================
# TEST: Parsing Functions
# =============================================================================

class TestParsingFunctions:
    """Test parsing functions."""

    def test_parse_date_string(self):
        """Test parsing date from string."""
        result = _parse_date("2025-01-15")
        assert result == date(2025, 1, 15)

    def test_parse_date_none(self):
        """Test parsing None date."""
        assert _parse_date(None) is None

    def test_parse_date_object(self):
        """Test parsing date object."""
        d = date(2025, 1, 15)
        assert _parse_date(d) == d

    def test_parse_datetime_string(self):
        """Test parsing datetime from string."""
        result = _parse_datetime("2025-01-15T10:00:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_parse_datetime_none(self):
        """Test parsing None datetime."""
        assert _parse_datetime(None) is None

    def test_parse_decimal_number(self):
        """Test parsing decimal from number."""
        assert _parse_decimal(100) == Decimal("100")
        assert _parse_decimal(100.50) == Decimal("100.5")

    def test_parse_decimal_string(self):
        """Test parsing decimal from string."""
        assert _parse_decimal("5000.00") == Decimal("5000.00")

    def test_parse_decimal_none(self):
        """Test parsing None decimal."""
        assert _parse_decimal(None) == Decimal("0.00")

    def test_parse_invoice(self, sample_invoice_data):
        """Test parsing invoice from database row."""
        invoice = _parse_invoice(sample_invoice_data)

        assert isinstance(invoice, SupplierInvoice)
        assert invoice.id == sample_invoice_data["id"]
        assert invoice.invoice_number == "INV-2025-001"
        assert invoice.invoice_date == date(2025, 1, 15)
        assert invoice.due_date == date(2025, 2, 15)
        assert invoice.total_amount == Decimal("5000.00")
        assert invoice.currency == "USD"
        assert invoice.status == INVOICE_STATUS_PENDING

    def test_parse_invoice_item(self, sample_invoice_item_data):
        """Test parsing invoice item from database row."""
        item = _parse_invoice_item(sample_invoice_item_data)

        assert isinstance(item, SupplierInvoiceItem)
        assert item.description == "Product A"
        assert item.quantity == Decimal("100.00")
        assert item.unit_price == Decimal("50.0000")
        assert item.total_price == Decimal("5000.00")


# =============================================================================
# TEST: Invoice CRUD
# =============================================================================

class TestInvoiceCRUD:
    """Test invoice CRUD operations."""

    def test_create_invoice_success(self, mock_supabase, sample_org_id, sample_supplier_id, sample_invoice_data):
        """Test successful invoice creation."""
        mock_supabase.table().insert().execute.return_value = MagicMock(data=[sample_invoice_data])

        invoice = create_invoice(
            organization_id=sample_org_id,
            supplier_id=sample_supplier_id,
            invoice_number="INV-2025-001",
            invoice_date=date(2025, 1, 15),
            total_amount=Decimal("5000.00"),
        )

        assert invoice is not None
        assert invoice.invoice_number == "INV-2025-001"

    def test_create_invoice_invalid_number(self, mock_supabase, sample_org_id, sample_supplier_id):
        """Test creating invoice with invalid number."""
        with pytest.raises(ValueError, match="Invalid invoice number"):
            create_invoice(
                organization_id=sample_org_id,
                supplier_id=sample_supplier_id,
                invoice_number="",
                invoice_date=date(2025, 1, 15),
                total_amount=Decimal("5000.00"),
            )

    def test_create_invoice_invalid_amount(self, mock_supabase, sample_org_id, sample_supplier_id):
        """Test creating invoice with invalid amount."""
        with pytest.raises(ValueError, match="Invalid total amount"):
            create_invoice(
                organization_id=sample_org_id,
                supplier_id=sample_supplier_id,
                invoice_number="INV-001",
                invoice_date=date(2025, 1, 15),
                total_amount=Decimal("0.00"),
            )

    def test_create_invoice_due_before_invoice_date(self, mock_supabase, sample_org_id, sample_supplier_id):
        """Test creating invoice with due date before invoice date."""
        with pytest.raises(ValueError, match="Due date cannot be before invoice date"):
            create_invoice(
                organization_id=sample_org_id,
                supplier_id=sample_supplier_id,
                invoice_number="INV-001",
                invoice_date=date(2025, 2, 15),
                total_amount=Decimal("5000.00"),
                due_date=date(2025, 1, 15),
            )

    def test_get_invoice_success(self, mock_supabase, sample_invoice_data):
        """Test getting invoice by ID."""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[sample_invoice_data])

        invoice = get_invoice(sample_invoice_data["id"])

        assert invoice is not None
        assert invoice.id == sample_invoice_data["id"]

    def test_get_invoice_not_found(self, mock_supabase):
        """Test getting non-existent invoice."""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[])

        invoice = get_invoice(str(uuid.uuid4()))

        assert invoice is None

    def test_get_invoice_by_number(self, mock_supabase, sample_org_id, sample_supplier_id, sample_invoice_data):
        """Test getting invoice by number."""
        mock_supabase.table().select().eq().eq().eq().execute.return_value = MagicMock(data=[sample_invoice_data])

        invoice = get_invoice_by_number(
            sample_org_id,
            sample_supplier_id,
            "INV-2025-001",
        )

        assert invoice is not None
        assert invoice.invoice_number == "INV-2025-001"

    def test_count_invoices(self, mock_supabase, sample_org_id):
        """Test counting invoices."""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(count=5)

        count = count_invoices(sample_org_id)

        assert count == 5

    def test_update_invoice_status(self, mock_supabase, sample_invoice_data):
        """Test updating invoice status."""
        sample_invoice_data["status"] = INVOICE_STATUS_PAID
        mock_supabase.table().update().eq().execute.return_value = MagicMock(data=[sample_invoice_data])

        invoice = update_invoice_status(sample_invoice_data["id"], INVOICE_STATUS_PAID)

        assert invoice is not None
        assert invoice.status == INVOICE_STATUS_PAID

    def test_update_invoice_status_invalid(self, mock_supabase, sample_invoice_data):
        """Test updating invoice with invalid status."""
        with pytest.raises(ValueError, match="Invalid status"):
            update_invoice_status(sample_invoice_data["id"], "invalid")

    def test_cancel_invoice_success(self, mock_supabase, sample_invoice_data):
        """Test cancelling invoice."""
        # First call is get_invoice - invoice is pending
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[sample_invoice_data])
        # Then update call with cancellation
        cancelled_data = dict(sample_invoice_data)
        cancelled_data["status"] = INVOICE_STATUS_CANCELLED
        cancelled_data["notes"] = "Отменено: Customer cancelled order"
        mock_supabase.table().update().eq().execute.return_value = MagicMock(data=[cancelled_data])

        invoice = cancel_invoice(sample_invoice_data["id"], "Customer cancelled order")

        assert invoice is not None
        assert invoice.status == INVOICE_STATUS_CANCELLED

    def test_cancel_paid_invoice_fails(self, mock_supabase, sample_invoice_data):
        """Test that cancelling a paid invoice fails."""
        sample_invoice_data["status"] = INVOICE_STATUS_PAID
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[sample_invoice_data])

        with pytest.raises(ValueError, match="Cannot cancel a paid invoice"):
            cancel_invoice(sample_invoice_data["id"])

    def test_delete_invoice(self, mock_supabase, sample_invoice_data):
        """Test deleting invoice."""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[sample_invoice_data])
        mock_supabase.table().delete().eq().execute.return_value = MagicMock(data=[])

        result = delete_invoice(sample_invoice_data["id"])

        assert result is True


# =============================================================================
# TEST: Invoice Item Operations
# =============================================================================

class TestInvoiceItemOperations:
    """Test invoice item operations."""

    def test_add_invoice_item_success(self, mock_supabase, sample_invoice_item_data):
        """Test adding item to invoice."""
        mock_supabase.table().insert().execute.return_value = MagicMock(data=[sample_invoice_item_data])

        item = add_invoice_item(
            invoice_id=sample_invoice_item_data["invoice_id"],
            quantity=Decimal("100.00"),
            unit_price=Decimal("50.00"),
            description="Product A",
        )

        assert item is not None
        assert item.description == "Product A"

    def test_add_invoice_item_invalid_quantity(self, mock_supabase):
        """Test adding item with invalid quantity."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            add_invoice_item(
                invoice_id=str(uuid.uuid4()),
                quantity=Decimal("0"),
                unit_price=Decimal("50.00"),
            )

    def test_add_invoice_item_negative_price(self, mock_supabase):
        """Test adding item with negative price."""
        with pytest.raises(ValueError, match="Unit price cannot be negative"):
            add_invoice_item(
                invoice_id=str(uuid.uuid4()),
                quantity=Decimal("100"),
                unit_price=Decimal("-10.00"),
            )

    def test_get_invoice_items(self, mock_supabase, sample_invoice_item_data):
        """Test getting invoice items."""
        mock_supabase.table().select().eq().order().execute.return_value = MagicMock(
            data=[sample_invoice_item_data, sample_invoice_item_data]
        )

        items = get_invoice_items(sample_invoice_item_data["invoice_id"])

        assert len(items) == 2

    def test_update_invoice_item(self, mock_supabase, sample_invoice_item_data):
        """Test updating invoice item."""
        sample_invoice_item_data["quantity"] = "200.00"
        mock_supabase.table().update().eq().execute.return_value = MagicMock(data=[sample_invoice_item_data])

        item = update_invoice_item(
            sample_invoice_item_data["id"],
            quantity=Decimal("200.00"),
        )

        assert item is not None

    def test_delete_invoice_item(self, mock_supabase, sample_invoice_item_data):
        """Test deleting invoice item."""
        mock_supabase.table().delete().eq().execute.return_value = MagicMock(data=[])

        result = delete_invoice_item(sample_invoice_item_data["id"])

        assert result is True


# =============================================================================
# TEST: Utility Functions
# =============================================================================

class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_invoice_summary_empty(self, mock_supabase, sample_org_id):
        """Test getting empty summary."""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[])

        summary = get_invoice_summary(sample_org_id)

        assert isinstance(summary, InvoiceSummary)
        assert summary.total == 0
        assert summary.total_amount == Decimal("0.00")

    def test_get_invoice_summary_with_data(self, mock_supabase, sample_org_id):
        """Test getting summary with invoices."""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[
            {"status": INVOICE_STATUS_PENDING, "total_amount": "1000.00"},
            {"status": INVOICE_STATUS_PENDING, "total_amount": "2000.00"},
            {"status": INVOICE_STATUS_PAID, "total_amount": "3000.00"},
            {"status": INVOICE_STATUS_OVERDUE, "total_amount": "500.00"},
        ])

        summary = get_invoice_summary(sample_org_id)

        assert summary.total == 4
        assert summary.pending == 2
        assert summary.paid == 1
        assert summary.overdue == 1
        assert summary.pending_amount == Decimal("3500.00")  # pending + overdue
        assert summary.paid_amount == Decimal("3000.00")

    def test_format_invoice_for_display(self, sample_invoice_data):
        """Test formatting invoice for display."""
        invoice = _parse_invoice(sample_invoice_data)
        invoice.supplier_name = "Test Supplier"
        invoice.supplier_code = "TST"
        invoice.paid_amount = Decimal("1000.00")
        invoice.remaining_amount = Decimal("4000.00")

        display = format_invoice_for_display(invoice)

        assert display["invoice_number"] == "INV-2025-001"
        assert display["supplier_name"] == "Test Supplier"
        assert display["status"] == INVOICE_STATUS_PENDING
        assert display["status_name"] == "Ожидает оплаты"
        assert display["status_color"] == "yellow"
        assert display["total_amount"] == "5,000.00"
        assert display["paid_amount"] == "1,000.00"
        assert display["remaining_amount"] == "4,000.00"


# =============================================================================
# TEST: Data Classes
# =============================================================================

class TestDataClasses:
    """Test data class creation."""

    def test_supplier_invoice_defaults(self):
        """Test SupplierInvoice default values."""
        invoice = SupplierInvoice(
            id="test-id",
            organization_id="org-id",
            supplier_id="supplier-id",
            invoice_number="INV-001",
            invoice_date=date(2025, 1, 15),
        )

        assert invoice.total_amount == Decimal("0.00")
        assert invoice.currency == "USD"
        assert invoice.status == INVOICE_STATUS_PENDING
        assert invoice.due_date is None
        assert invoice.notes is None

    def test_supplier_invoice_item_defaults(self):
        """Test SupplierInvoiceItem default values."""
        item = SupplierInvoiceItem(
            id="item-id",
            invoice_id="invoice-id",
        )

        assert item.quantity == Decimal("1.00")
        assert item.unit_price == Decimal("0.00")
        assert item.total_price == Decimal("0.00")
        assert item.quote_item_id is None

    def test_invoice_summary_defaults(self):
        """Test InvoiceSummary default values."""
        summary = InvoiceSummary()

        assert summary.total == 0
        assert summary.pending == 0
        assert summary.paid == 0
        assert summary.total_amount == Decimal("0.00")
        assert summary.pending_amount == Decimal("0.00")
        assert summary.paid_amount == Decimal("0.00")


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
