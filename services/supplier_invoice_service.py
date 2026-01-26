"""
Supplier Invoice Service - CRUD operations for supplier_invoices and supplier_invoice_items tables

This module provides functions for managing supplier invoices in the supply chain:
- Create/Update/Delete supplier invoices
- Add/Update/Remove invoice items (with optional quote_item links)
- Track invoice status: pending → partially_paid → paid (or overdue/cancelled)
- Query invoices by organization, supplier, status
- Search and filter for registry views
- Calculate payment summaries

Based on app_spec.xml supplier_invoices and supplier_invoice_items tables (Feature API-010).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import os
from supabase import create_client


# Initialize Supabase client with service role for admin operations
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _get_supabase():
    """Get Supabase client with service role key for admin operations."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# =============================================================================
# CONSTANTS
# =============================================================================

# Invoice status constants
INVOICE_STATUS_PENDING = "pending"
INVOICE_STATUS_PARTIALLY_PAID = "partially_paid"
INVOICE_STATUS_PAID = "paid"
INVOICE_STATUS_OVERDUE = "overdue"
INVOICE_STATUS_CANCELLED = "cancelled"

INVOICE_STATUSES = [
    INVOICE_STATUS_PENDING,
    INVOICE_STATUS_PARTIALLY_PAID,
    INVOICE_STATUS_PAID,
    INVOICE_STATUS_OVERDUE,
    INVOICE_STATUS_CANCELLED,
]

INVOICE_STATUS_NAMES = {
    INVOICE_STATUS_PENDING: "Ожидает оплаты",
    INVOICE_STATUS_PARTIALLY_PAID: "Частично оплачен",
    INVOICE_STATUS_PAID: "Оплачен",
    INVOICE_STATUS_OVERDUE: "Просрочен",
    INVOICE_STATUS_CANCELLED: "Отменён",
}

INVOICE_STATUS_COLORS = {
    INVOICE_STATUS_PENDING: "yellow",
    INVOICE_STATUS_PARTIALLY_PAID: "blue",
    INVOICE_STATUS_PAID: "green",
    INVOICE_STATUS_OVERDUE: "red",
    INVOICE_STATUS_CANCELLED: "gray",
}

# Currency constants
DEFAULT_CURRENCY = "USD"
SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB", "CNY", "TRY"]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SupplierInvoice:
    """
    Represents a supplier invoice record.

    Registry entry for invoices received from suppliers.
    Maps to supplier_invoices table in database.
    """
    id: str
    organization_id: str
    supplier_id: str

    # Invoice details
    invoice_number: str
    invoice_date: date
    due_date: Optional[date] = None

    # Financial info
    total_amount: Decimal = Decimal("0.00")
    currency: str = DEFAULT_CURRENCY

    # Status
    status: str = INVOICE_STATUS_PENDING

    # Additional info
    notes: Optional[str] = None
    invoice_file_url: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    # Joined data (optional, from views)
    supplier_name: Optional[str] = None
    supplier_code: Optional[str] = None
    paid_amount: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    payment_count: Optional[int] = None
    is_overdue: Optional[bool] = None
    days_until_due: Optional[int] = None


@dataclass
class SupplierInvoiceItem:
    """
    Represents an invoice line item.

    Can be linked to a quote_item for traceability.
    Maps to supplier_invoice_items table in database.
    """
    id: str
    invoice_id: str

    # Link to quote item (optional)
    quote_item_id: Optional[str] = None

    # Item details
    description: Optional[str] = None
    quantity: Decimal = Decimal("1.00")
    unit_price: Decimal = Decimal("0.00")
    total_price: Decimal = Decimal("0.00")  # Auto-calculated
    unit: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None

    # Joined data (optional, from views)
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    quote_idn: Optional[str] = None


@dataclass
class InvoiceSummary:
    """Summary statistics for invoices."""
    total: int = 0
    pending: int = 0
    partially_paid: int = 0
    paid: int = 0
    overdue: int = 0
    cancelled: int = 0
    total_amount: Decimal = Decimal("0.00")
    pending_amount: Decimal = Decimal("0.00")
    paid_amount: Decimal = Decimal("0.00")


@dataclass
class QuoteInvoicingItem:
    """
    Invoicing status for a single quote item.

    Used in quote controller checklist to verify supplier invoices
    are present for all quote items.
    """
    quote_item_id: str
    product_name: str = ""

    # Quote item details
    quote_quantity: Decimal = Decimal("0.00")
    quote_unit_price: Decimal = Decimal("0.00")

    # Invoicing status
    invoiced_quantity: Decimal = Decimal("0.00")
    invoiced_amount: Decimal = Decimal("0.00")
    invoice_count: int = 0
    is_fully_invoiced: bool = False


@dataclass
class QuoteInvoicingSummary:
    """
    Overall invoicing summary for a quote.

    Shows how many items have invoices and total amounts.
    """
    total_items: int = 0
    items_with_invoices: int = 0
    items_fully_invoiced: int = 0
    total_expected: Decimal = Decimal("0.00")
    total_invoiced: Decimal = Decimal("0.00")
    items: List[QuoteInvoicingItem] = field(default_factory=list)

    @property
    def all_invoiced(self) -> bool:
        """Check if all items are invoiced."""
        return self.items_with_invoices == self.total_items and self.total_items > 0

    @property
    def coverage_percent(self) -> float:
        """Calculate invoicing coverage percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.items_with_invoices / self.total_items) * 100


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def _parse_date(value: Any) -> Optional[date]:
    """Parse a date value from database."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a datetime value from database."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _parse_decimal(value: Any) -> Decimal:
    """Parse a decimal value from database."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _parse_invoice(data: dict) -> SupplierInvoice:
    """Parse database row into SupplierInvoice object."""
    return SupplierInvoice(
        id=data["id"],
        organization_id=data["organization_id"],
        supplier_id=data["supplier_id"],
        invoice_number=data["invoice_number"],
        invoice_date=_parse_date(data["invoice_date"]),
        due_date=_parse_date(data.get("due_date")),
        total_amount=_parse_decimal(data.get("total_amount", 0)),
        currency=data.get("currency", DEFAULT_CURRENCY),
        status=data.get("status", INVOICE_STATUS_PENDING),
        notes=data.get("notes"),
        invoice_file_url=data.get("invoice_file_url"),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
        created_by=data.get("created_by"),
        # Joined data from views
        supplier_name=data.get("supplier_name"),
        supplier_code=data.get("supplier_code"),
        paid_amount=_parse_decimal(data.get("paid_amount")) if "paid_amount" in data else None,
        remaining_amount=_parse_decimal(data.get("remaining_amount")) if "remaining_amount" in data else None,
        payment_count=data.get("payment_count"),
        is_overdue=data.get("is_overdue"),
        days_until_due=data.get("days_until_due"),
    )


def _parse_invoice_item(data: dict) -> SupplierInvoiceItem:
    """Parse database row into SupplierInvoiceItem object."""
    return SupplierInvoiceItem(
        id=data["id"],
        invoice_id=data["invoice_id"],
        quote_item_id=data.get("quote_item_id"),
        description=data.get("description"),
        quantity=_parse_decimal(data.get("quantity", 1)),
        unit_price=_parse_decimal(data.get("unit_price", 0)),
        total_price=_parse_decimal(data.get("total_price", 0)),
        unit=data.get("unit"),
        created_at=_parse_datetime(data.get("created_at")),
        # Joined data
        product_name=data.get("product_name"),
        product_sku=data.get("product_sku"),
        quote_idn=data.get("quote_idn"),
    )


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_invoice_number(invoice_number: str) -> bool:
    """
    Validate invoice number format.

    Args:
        invoice_number: Invoice number to validate

    Returns:
        True if valid, False otherwise
    """
    if not invoice_number:
        return False
    # Invoice number should be non-empty string, max 100 chars
    return len(invoice_number.strip()) > 0 and len(invoice_number) <= 100


def validate_invoice_status(status: str) -> bool:
    """
    Validate invoice status.

    Args:
        status: Status to validate

    Returns:
        True if valid status, False otherwise
    """
    return status in INVOICE_STATUSES


def validate_currency(currency: str) -> bool:
    """
    Validate currency code.

    Args:
        currency: 3-letter currency code

    Returns:
        True if valid currency, False otherwise
    """
    if not currency:
        return False
    return len(currency) == 3 and currency.isalpha() and currency.isupper()


def validate_amount(amount: Any) -> bool:
    """
    Validate invoice amount.

    Args:
        amount: Amount to validate

    Returns:
        True if valid positive amount, False otherwise
    """
    try:
        decimal_amount = Decimal(str(amount))
        return decimal_amount > 0
    except Exception:
        return False


# =============================================================================
# STATUS HELPERS
# =============================================================================

def get_invoice_status_name(status: str) -> str:
    """Get localized status name."""
    return INVOICE_STATUS_NAMES.get(status, status)


def get_invoice_status_color(status: str) -> str:
    """Get status color for UI."""
    return INVOICE_STATUS_COLORS.get(status, "gray")


def is_invoice_payable(status: str) -> bool:
    """Check if invoice can receive payments."""
    return status in [INVOICE_STATUS_PENDING, INVOICE_STATUS_PARTIALLY_PAID, INVOICE_STATUS_OVERDUE]


def is_invoice_editable(status: str) -> bool:
    """Check if invoice can be edited."""
    return status in [INVOICE_STATUS_PENDING, INVOICE_STATUS_PARTIALLY_PAID, INVOICE_STATUS_OVERDUE]


# =============================================================================
# INVOICE CREATE OPERATIONS
# =============================================================================

def create_invoice(
    organization_id: str,
    supplier_id: str,
    invoice_number: str,
    invoice_date: date,
    total_amount: Decimal,
    *,
    currency: str = DEFAULT_CURRENCY,
    due_date: Optional[date] = None,
    notes: Optional[str] = None,
    invoice_file_url: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[SupplierInvoice]:
    """
    Create a new supplier invoice.

    Args:
        organization_id: Organization UUID
        supplier_id: Supplier UUID
        invoice_number: Invoice number from supplier
        invoice_date: Invoice date
        total_amount: Total invoice amount
        currency: Currency code (default: USD)
        due_date: Payment due date (optional)
        notes: Additional notes
        invoice_file_url: URL to uploaded invoice file
        created_by: User UUID who created this

    Returns:
        SupplierInvoice object if successful, None if duplicate invoice number

    Raises:
        ValueError: If validation fails

    Example:
        invoice = create_invoice(
            organization_id="org-uuid",
            supplier_id="supplier-uuid",
            invoice_number="INV-2025-001",
            invoice_date=date(2025, 1, 15),
            total_amount=Decimal("5000.00"),
            due_date=date(2025, 2, 15)
        )
    """
    # Validate inputs
    if not validate_invoice_number(invoice_number):
        raise ValueError(f"Invalid invoice number: {invoice_number}")
    if not validate_amount(total_amount):
        raise ValueError(f"Invalid total amount: {total_amount}")
    if not validate_currency(currency):
        raise ValueError(f"Invalid currency: {currency}")
    if due_date and due_date < invoice_date:
        raise ValueError("Due date cannot be before invoice date")

    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoices").insert({
            "organization_id": organization_id,
            "supplier_id": supplier_id,
            "invoice_number": invoice_number.strip(),
            "invoice_date": invoice_date.isoformat(),
            "due_date": due_date.isoformat() if due_date else None,
            "total_amount": str(total_amount),
            "currency": currency,
            "status": INVOICE_STATUS_PENDING,
            "notes": notes,
            "invoice_file_url": invoice_file_url,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation
        if "idx_supplier_invoices_unique_number" in str(e) or "duplicate key" in str(e).lower():
            return None
        raise


def create_invoice_with_items(
    organization_id: str,
    supplier_id: str,
    invoice_number: str,
    invoice_date: date,
    items: List[Dict[str, Any]],
    *,
    currency: str = DEFAULT_CURRENCY,
    due_date: Optional[date] = None,
    notes: Optional[str] = None,
    invoice_file_url: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[SupplierInvoice]:
    """
    Create a new supplier invoice with items.

    The total_amount will be calculated from items.

    Args:
        organization_id: Organization UUID
        supplier_id: Supplier UUID
        invoice_number: Invoice number from supplier
        invoice_date: Invoice date
        items: List of item dicts with keys:
            - quantity: Decimal
            - unit_price: Decimal
            - description: Optional[str]
            - quote_item_id: Optional[str]
            - unit: Optional[str]
        currency: Currency code
        due_date: Payment due date
        notes: Additional notes
        invoice_file_url: URL to uploaded invoice file
        created_by: User UUID

    Returns:
        SupplierInvoice object if successful

    Example:
        invoice = create_invoice_with_items(
            organization_id="org-uuid",
            supplier_id="supplier-uuid",
            invoice_number="INV-2025-001",
            invoice_date=date(2025, 1, 15),
            items=[
                {"quantity": Decimal("100"), "unit_price": Decimal("50.00"), "description": "Product A"},
                {"quantity": Decimal("50"), "unit_price": Decimal("80.00"), "quote_item_id": "item-uuid"},
            ]
        )
    """
    if not items:
        raise ValueError("Invoice must have at least one item")

    # Calculate total from items
    total_amount = Decimal("0.00")
    for item in items:
        quantity = _parse_decimal(item.get("quantity", 1))
        unit_price = _parse_decimal(item.get("unit_price", 0))
        total_amount += quantity * unit_price

    # Create invoice first
    invoice = create_invoice(
        organization_id=organization_id,
        supplier_id=supplier_id,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        total_amount=total_amount,
        currency=currency,
        due_date=due_date,
        notes=notes,
        invoice_file_url=invoice_file_url,
        created_by=created_by,
    )

    if not invoice:
        return None

    # Add items
    for item in items:
        add_invoice_item(
            invoice_id=invoice.id,
            quantity=_parse_decimal(item.get("quantity", 1)),
            unit_price=_parse_decimal(item.get("unit_price", 0)),
            description=item.get("description"),
            quote_item_id=item.get("quote_item_id"),
            unit=item.get("unit"),
        )

    # Return refreshed invoice with updated total
    return get_invoice(invoice.id)


# =============================================================================
# INVOICE READ OPERATIONS
# =============================================================================

def get_invoice(invoice_id: str) -> Optional[SupplierInvoice]:
    """
    Get an invoice by ID.

    Args:
        invoice_id: Invoice UUID

    Returns:
        SupplierInvoice object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoices").select("*")\
            .eq("id", invoice_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting invoice: {e}")
        return None


def get_invoice_with_details(invoice_id: str) -> Optional[SupplierInvoice]:
    """
    Get an invoice with supplier name and payment info.

    Uses v_supplier_invoices_with_payments view.

    Args:
        invoice_id: Invoice UUID

    Returns:
        SupplierInvoice with joined data
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("v_supplier_invoices_with_payments").select("*")\
            .eq("id", invoice_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting invoice with details: {e}")
        # Fallback to basic query
        return get_invoice(invoice_id)


def get_invoice_by_number(
    organization_id: str,
    supplier_id: str,
    invoice_number: str,
) -> Optional[SupplierInvoice]:
    """
    Get an invoice by its number for a specific supplier.

    Args:
        organization_id: Organization UUID
        supplier_id: Supplier UUID
        invoice_number: Invoice number

    Returns:
        SupplierInvoice if found
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoices").select("*")\
            .eq("organization_id", organization_id)\
            .eq("supplier_id", supplier_id)\
            .eq("invoice_number", invoice_number)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting invoice by number: {e}")
        return None


def get_invoices_for_supplier(
    supplier_id: str,
    *,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[SupplierInvoice]:
    """
    Get all invoices for a supplier.

    Args:
        supplier_id: Supplier UUID
        status: Filter by status (optional)
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of SupplierInvoice objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("supplier_invoices").select("*")\
            .eq("supplier_id", supplier_id)\
            .order("invoice_date", desc=True)

        if status:
            query = query.eq("status", status)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_invoice(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting invoices for supplier: {e}")
        return []


def get_all_invoices(
    organization_id: str,
    *,
    status: Optional[str] = None,
    supplier_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    is_overdue: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[SupplierInvoice]:
    """
    Get all invoices for an organization with filters.

    Uses v_supplier_invoices_with_payments view for payment info.

    Args:
        organization_id: Organization UUID
        status: Filter by status
        supplier_id: Filter by supplier
        from_date: Filter by invoice date >= from_date
        to_date: Filter by invoice date <= to_date
        is_overdue: Filter by overdue status
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of SupplierInvoice objects with payment details
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("v_supplier_invoices_with_payments").select("*")\
            .eq("organization_id", organization_id)\
            .order("invoice_date", desc=True)

        if status:
            query = query.eq("status", status)
        if supplier_id:
            query = query.eq("supplier_id", supplier_id)
        if from_date:
            query = query.gte("invoice_date", from_date.isoformat())
        if to_date:
            query = query.lte("invoice_date", to_date.isoformat())
        if is_overdue is not None:
            query = query.eq("is_overdue", is_overdue)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_invoice(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all invoices: {e}")
        return []


def count_invoices(
    organization_id: str,
    *,
    status: Optional[str] = None,
    supplier_id: Optional[str] = None,
) -> int:
    """
    Count invoices in an organization.

    Args:
        organization_id: Organization UUID
        status: Filter by status
        supplier_id: Filter by supplier

    Returns:
        Number of invoices
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("supplier_invoices").select("id", count="exact")\
            .eq("organization_id", organization_id)

        if status:
            query = query.eq("status", status)
        if supplier_id:
            query = query.eq("supplier_id", supplier_id)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting invoices: {e}")
        return 0


def search_invoices(
    organization_id: str,
    query_text: str,
    *,
    limit: int = 20,
) -> List[SupplierInvoice]:
    """
    Search invoices by invoice number.

    Args:
        organization_id: Organization UUID
        query_text: Search text
        limit: Maximum results

    Returns:
        List of matching invoices
    """
    if not query_text or len(query_text) < 1:
        return []

    try:
        supabase = _get_supabase()

        search_pattern = f"%{query_text}%"

        result = supabase.table("v_supplier_invoices_with_payments").select("*")\
            .eq("organization_id", organization_id)\
            .ilike("invoice_number", search_pattern)\
            .order("invoice_date", desc=True)\
            .limit(limit)\
            .execute()

        return [_parse_invoice(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error searching invoices: {e}")
        return []


def invoice_exists(
    organization_id: str,
    supplier_id: str,
    invoice_number: str,
) -> bool:
    """
    Check if invoice with given number exists for supplier.

    Args:
        organization_id: Organization UUID
        supplier_id: Supplier UUID
        invoice_number: Invoice number

    Returns:
        True if exists
    """
    return get_invoice_by_number(organization_id, supplier_id, invoice_number) is not None


def get_overdue_invoices(
    organization_id: str,
    *,
    limit: int = 100,
) -> List[SupplierInvoice]:
    """
    Get all overdue invoices.

    Args:
        organization_id: Organization UUID
        limit: Maximum results

    Returns:
        List of overdue invoices
    """
    return get_all_invoices(
        organization_id,
        is_overdue=True,
        limit=limit,
    )


def get_pending_invoices(
    organization_id: str,
    *,
    limit: int = 100,
) -> List[SupplierInvoice]:
    """
    Get all pending invoices (not yet paid).

    Args:
        organization_id: Organization UUID
        limit: Maximum results

    Returns:
        List of pending invoices
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("v_supplier_invoices_with_payments").select("*")\
            .eq("organization_id", organization_id)\
            .in_("status", [INVOICE_STATUS_PENDING, INVOICE_STATUS_PARTIALLY_PAID, INVOICE_STATUS_OVERDUE])\
            .order("due_date")\
            .limit(limit)\
            .execute()

        return [_parse_invoice(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting pending invoices: {e}")
        return []


# =============================================================================
# INVOICE UPDATE OPERATIONS
# =============================================================================

def update_invoice(
    invoice_id: str,
    *,
    invoice_number: Optional[str] = None,
    invoice_date: Optional[date] = None,
    due_date: Optional[date] = None,
    total_amount: Optional[Decimal] = None,
    currency: Optional[str] = None,
    notes: Optional[str] = None,
    invoice_file_url: Optional[str] = None,
) -> Optional[SupplierInvoice]:
    """
    Update an invoice.

    Note: Status is managed separately via dedicated functions.

    Args:
        invoice_id: Invoice UUID
        invoice_number: New invoice number
        invoice_date: New invoice date
        due_date: New due date
        total_amount: New total (not recommended if items exist)
        currency: New currency
        notes: New notes
        invoice_file_url: New file URL

    Returns:
        Updated SupplierInvoice

    Raises:
        ValueError: If validation fails
    """
    # Validate inputs
    if invoice_number is not None and not validate_invoice_number(invoice_number):
        raise ValueError(f"Invalid invoice number: {invoice_number}")
    if total_amount is not None and not validate_amount(total_amount):
        raise ValueError(f"Invalid total amount: {total_amount}")
    if currency is not None and not validate_currency(currency):
        raise ValueError(f"Invalid currency: {currency}")

    try:
        supabase = _get_supabase()

        # Get current invoice to check if editable
        current = get_invoice(invoice_id)
        if not current:
            return None
        if not is_invoice_editable(current.status):
            raise ValueError(f"Cannot edit invoice with status: {current.status}")

        # Validate date ordering
        new_invoice_date = invoice_date or current.invoice_date
        new_due_date = due_date or current.due_date
        if new_due_date and new_due_date < new_invoice_date:
            raise ValueError("Due date cannot be before invoice date")

        # Build update dict
        update_data = {}
        if invoice_number is not None:
            update_data["invoice_number"] = invoice_number.strip()
        if invoice_date is not None:
            update_data["invoice_date"] = invoice_date.isoformat()
        if due_date is not None:
            update_data["due_date"] = due_date.isoformat()
        if total_amount is not None:
            update_data["total_amount"] = str(total_amount)
        if currency is not None:
            update_data["currency"] = currency
        if notes is not None:
            update_data["notes"] = notes
        if invoice_file_url is not None:
            update_data["invoice_file_url"] = invoice_file_url

        if not update_data:
            return current

        result = supabase.table("supplier_invoices").update(update_data)\
            .eq("id", invoice_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating invoice: {e}")
        raise


def update_invoice_status(
    invoice_id: str,
    status: str,
) -> Optional[SupplierInvoice]:
    """
    Update invoice status.

    Note: Status is typically managed automatically by payment triggers.
    Use this for manual status changes (e.g., cancel).

    Args:
        invoice_id: Invoice UUID
        status: New status

    Returns:
        Updated SupplierInvoice
    """
    if not validate_invoice_status(status):
        raise ValueError(f"Invalid status: {status}")

    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoices").update({"status": status})\
            .eq("id", invoice_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating invoice status: {e}")
        return None


def cancel_invoice(invoice_id: str, reason: Optional[str] = None) -> Optional[SupplierInvoice]:
    """
    Cancel an invoice.

    Args:
        invoice_id: Invoice UUID
        reason: Cancellation reason (optional)

    Returns:
        Updated SupplierInvoice
    """
    current = get_invoice(invoice_id)
    if not current:
        return None

    # Can't cancel already paid invoice
    if current.status == INVOICE_STATUS_PAID:
        raise ValueError("Cannot cancel a paid invoice")

    try:
        supabase = _get_supabase()

        # Build update dict
        update_data = {"status": INVOICE_STATUS_CANCELLED}

        # Add reason to notes if provided
        if reason:
            notes = f"{current.notes or ''}\n\nОтменено: {reason}".strip()
            update_data["notes"] = notes

        result = supabase.table("supplier_invoices").update(update_data)\
            .eq("id", invoice_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice(result.data[0])
        return None

    except Exception as e:
        print(f"Error cancelling invoice: {e}")
        return None


def mark_invoice_overdue(invoice_id: str) -> Optional[SupplierInvoice]:
    """
    Mark an invoice as overdue.

    Args:
        invoice_id: Invoice UUID

    Returns:
        Updated SupplierInvoice
    """
    current = get_invoice(invoice_id)
    if not current:
        return None

    # Only mark pending/partially_paid as overdue
    if current.status not in [INVOICE_STATUS_PENDING, INVOICE_STATUS_PARTIALLY_PAID]:
        return current

    return update_invoice_status(invoice_id, INVOICE_STATUS_OVERDUE)


def update_overdue_invoices(organization_id: str) -> int:
    """
    Mark all overdue invoices in organization.

    Calls the database function update_overdue_supplier_invoices().

    Args:
        organization_id: Organization UUID

    Returns:
        Number of invoices marked overdue
    """
    try:
        supabase = _get_supabase()

        # Call the database function
        result = supabase.rpc("update_overdue_supplier_invoices").execute()

        return result.data if result.data else 0

    except Exception as e:
        print(f"Error updating overdue invoices: {e}")
        return 0


# =============================================================================
# INVOICE DELETE OPERATIONS
# =============================================================================

def delete_invoice(invoice_id: str) -> bool:
    """
    Delete an invoice permanently.

    Note: Consider using cancel_invoice() instead.

    Args:
        invoice_id: Invoice UUID

    Returns:
        True if deleted
    """
    try:
        # Check if invoice can be deleted
        current = get_invoice(invoice_id)
        if current and current.status == INVOICE_STATUS_PAID:
            raise ValueError("Cannot delete a paid invoice")

        supabase = _get_supabase()

        # Items will be deleted via CASCADE
        supabase.table("supplier_invoices").delete()\
            .eq("id", invoice_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting invoice: {e}")
        return False


# =============================================================================
# INVOICE ITEM OPERATIONS
# =============================================================================

def add_invoice_item(
    invoice_id: str,
    quantity: Decimal,
    unit_price: Decimal,
    *,
    description: Optional[str] = None,
    quote_item_id: Optional[str] = None,
    unit: Optional[str] = None,
) -> Optional[SupplierInvoiceItem]:
    """
    Add an item to an invoice.

    The invoice total will be auto-updated via database trigger.

    Args:
        invoice_id: Invoice UUID
        quantity: Item quantity
        unit_price: Price per unit
        description: Item description
        quote_item_id: Link to quote_item (optional)
        unit: Unit of measure

    Returns:
        SupplierInvoiceItem if successful
    """
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    if unit_price < 0:
        raise ValueError("Unit price cannot be negative")

    try:
        supabase = _get_supabase()

        # total_price is auto-calculated by trigger
        result = supabase.table("supplier_invoice_items").insert({
            "invoice_id": invoice_id,
            "quantity": str(quantity),
            "unit_price": str(unit_price),
            "total_price": str(quantity * unit_price),  # Will be recalculated by trigger
            "description": description,
            "quote_item_id": quote_item_id,
            "unit": unit,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice_item(result.data[0])
        return None

    except Exception as e:
        print(f"Error adding invoice item: {e}")
        return None


def get_invoice_item(item_id: str) -> Optional[SupplierInvoiceItem]:
    """
    Get an invoice item by ID.

    Args:
        item_id: Item UUID

    Returns:
        SupplierInvoiceItem if found
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoice_items").select("*")\
            .eq("id", item_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice_item(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting invoice item: {e}")
        return None


def get_invoice_items(invoice_id: str) -> List[SupplierInvoiceItem]:
    """
    Get all items for an invoice.

    Args:
        invoice_id: Invoice UUID

    Returns:
        List of SupplierInvoiceItem objects
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoice_items").select("*")\
            .eq("invoice_id", invoice_id)\
            .order("created_at")\
            .execute()

        return [_parse_invoice_item(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting invoice items: {e}")
        return []


def get_invoice_items_with_details(invoice_id: str) -> List[SupplierInvoiceItem]:
    """
    Get invoice items with product and quote details.

    Uses v_supplier_invoice_items_full view.

    Args:
        invoice_id: Invoice UUID

    Returns:
        List of SupplierInvoiceItem with joined data
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("v_supplier_invoice_items_full").select("*")\
            .eq("invoice_id", invoice_id)\
            .order("created_at")\
            .execute()

        return [_parse_invoice_item(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting invoice items with details: {e}")
        # Fallback to basic query
        return get_invoice_items(invoice_id)


def update_invoice_item(
    item_id: str,
    *,
    quantity: Optional[Decimal] = None,
    unit_price: Optional[Decimal] = None,
    description: Optional[str] = None,
    unit: Optional[str] = None,
) -> Optional[SupplierInvoiceItem]:
    """
    Update an invoice item.

    The invoice total will be auto-updated via database trigger.

    Args:
        item_id: Item UUID
        quantity: New quantity
        unit_price: New unit price
        description: New description
        unit: New unit

    Returns:
        Updated SupplierInvoiceItem
    """
    if quantity is not None and quantity <= 0:
        raise ValueError("Quantity must be positive")
    if unit_price is not None and unit_price < 0:
        raise ValueError("Unit price cannot be negative")

    try:
        supabase = _get_supabase()

        # Build update dict
        update_data = {}
        if quantity is not None:
            update_data["quantity"] = str(quantity)
        if unit_price is not None:
            update_data["unit_price"] = str(unit_price)
        if description is not None:
            update_data["description"] = description
        if unit is not None:
            update_data["unit"] = unit

        if not update_data:
            return get_invoice_item(item_id)

        result = supabase.table("supplier_invoice_items").update(update_data)\
            .eq("id", item_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_invoice_item(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating invoice item: {e}")
        return None


def delete_invoice_item(item_id: str) -> bool:
    """
    Delete an invoice item.

    The invoice total will be auto-updated via database trigger.

    Args:
        item_id: Item UUID

    Returns:
        True if deleted
    """
    try:
        supabase = _get_supabase()

        supabase.table("supplier_invoice_items").delete()\
            .eq("id", item_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting invoice item: {e}")
        return False


def get_items_for_quote_item(quote_item_id: str) -> List[SupplierInvoiceItem]:
    """
    Get all invoice items linked to a quote item.

    Useful for seeing invoicing history for a quote item.

    Args:
        quote_item_id: Quote item UUID

    Returns:
        List of SupplierInvoiceItem objects
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("v_supplier_invoice_items_full").select("*")\
            .eq("quote_item_id", quote_item_id)\
            .order("created_at")\
            .execute()

        return [_parse_invoice_item(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting items for quote item: {e}")
        return []


def get_total_invoiced_for_quote_item(quote_item_id: str) -> Decimal:
    """
    Get total amount invoiced for a quote item.

    Args:
        quote_item_id: Quote item UUID

    Returns:
        Total invoiced amount
    """
    try:
        supabase = _get_supabase()

        # Call database function
        result = supabase.rpc(
            "get_quote_item_invoiced_total",
            {"p_quote_item_id": quote_item_id}
        ).execute()

        return _parse_decimal(result.data) if result.data else Decimal("0.00")

    except Exception as e:
        print(f"Error getting total invoiced: {e}")
        return Decimal("0.00")


def get_quote_invoicing_summary(quote_id: str) -> QuoteInvoicingSummary:
    """
    Get invoicing summary for all items in a quote.

    Used by quote controller to verify that supplier invoices exist
    for all quote items before approval.

    Calls database function get_quote_invoicing_summary which returns:
    - quote_item_id, product_name, quote_quantity, quote_unit_price
    - invoiced_quantity, invoiced_amount, invoice_count, is_fully_invoiced

    Args:
        quote_id: Quote UUID

    Returns:
        QuoteInvoicingSummary with list of QuoteInvoicingItem
    """
    try:
        supabase = _get_supabase()

        # Call database function (in kvota schema)
        result = supabase.schema("kvota").rpc(
            "get_quote_invoicing_summary",
            {"p_quote_id": quote_id}
        ).execute()

        summary = QuoteInvoicingSummary()

        if not result.data:
            return summary

        # Parse each item from the result
        for row in result.data:
            item = QuoteInvoicingItem(
                quote_item_id=row.get("quote_item_id", ""),
                product_name=row.get("product_name", "") or "",
                quote_quantity=_parse_decimal(row.get("quote_quantity", 0)),
                quote_unit_price=_parse_decimal(row.get("quote_unit_price", 0)),
                invoiced_quantity=_parse_decimal(row.get("invoiced_quantity", 0)),
                invoiced_amount=_parse_decimal(row.get("invoiced_amount", 0)),
                invoice_count=int(row.get("invoice_count", 0) or 0),
                is_fully_invoiced=bool(row.get("is_fully_invoiced", False)),
            )
            summary.items.append(item)

            # Calculate totals
            summary.total_items += 1
            summary.total_expected += item.quote_quantity * item.quote_unit_price

            if item.invoice_count > 0:
                summary.items_with_invoices += 1
                summary.total_invoiced += item.invoiced_amount

            if item.is_fully_invoiced:
                summary.items_fully_invoiced += 1

        return summary

    except Exception as e:
        print(f"Error getting quote invoicing summary: {e}")
        return QuoteInvoicingSummary()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_invoice_summary(organization_id: str) -> InvoiceSummary:
    """
    Get invoice summary statistics for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        InvoiceSummary with counts and amounts
    """
    try:
        supabase = _get_supabase()

        # Get all invoices for counting
        result = supabase.table("supplier_invoices").select("status, total_amount")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return InvoiceSummary()

        summary = InvoiceSummary()
        summary.total = len(result.data)

        for row in result.data:
            status = row.get("status", INVOICE_STATUS_PENDING)
            amount = _parse_decimal(row.get("total_amount", 0))

            summary.total_amount += amount

            if status == INVOICE_STATUS_PENDING:
                summary.pending += 1
                summary.pending_amount += amount
            elif status == INVOICE_STATUS_PARTIALLY_PAID:
                summary.partially_paid += 1
                summary.pending_amount += amount
            elif status == INVOICE_STATUS_PAID:
                summary.paid += 1
                summary.paid_amount += amount
            elif status == INVOICE_STATUS_OVERDUE:
                summary.overdue += 1
                summary.pending_amount += amount
            elif status == INVOICE_STATUS_CANCELLED:
                summary.cancelled += 1

        return summary

    except Exception as e:
        print(f"Error getting invoice summary: {e}")
        return InvoiceSummary()


def get_invoice_stats_by_supplier(
    organization_id: str,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Get invoice statistics grouped by supplier.

    Args:
        organization_id: Organization UUID
        from_date: Filter from date
        to_date: Filter to date

    Returns:
        List of dicts with supplier_id, supplier_name, invoice_count, total_amount
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("v_supplier_invoices_with_payments").select(
            "supplier_id, supplier_name, supplier_code, total_amount"
        ).eq("organization_id", organization_id)

        if from_date:
            query = query.gte("invoice_date", from_date.isoformat())
        if to_date:
            query = query.lte("invoice_date", to_date.isoformat())

        result = query.execute()

        if not result.data:
            return []

        # Group by supplier
        stats = {}
        for row in result.data:
            supplier_id = row["supplier_id"]
            if supplier_id not in stats:
                stats[supplier_id] = {
                    "supplier_id": supplier_id,
                    "supplier_name": row.get("supplier_name"),
                    "supplier_code": row.get("supplier_code"),
                    "invoice_count": 0,
                    "total_amount": Decimal("0.00"),
                }
            stats[supplier_id]["invoice_count"] += 1
            stats[supplier_id]["total_amount"] += _parse_decimal(row.get("total_amount", 0))

        return sorted(stats.values(), key=lambda x: x["total_amount"], reverse=True)

    except Exception as e:
        print(f"Error getting invoice stats by supplier: {e}")
        return []


def format_invoice_for_display(invoice: SupplierInvoice) -> Dict[str, Any]:
    """
    Format invoice for display in UI.

    Args:
        invoice: SupplierInvoice object

    Returns:
        Dict with formatted values
    """
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "supplier_name": invoice.supplier_name or "",
        "supplier_code": invoice.supplier_code or "",
        "total_amount": f"{invoice.total_amount:,.2f}",
        "currency": invoice.currency,
        "status": invoice.status,
        "status_name": get_invoice_status_name(invoice.status),
        "status_color": get_invoice_status_color(invoice.status),
        "paid_amount": f"{invoice.paid_amount:,.2f}" if invoice.paid_amount else "0.00",
        "remaining_amount": f"{invoice.remaining_amount:,.2f}" if invoice.remaining_amount else f"{invoice.total_amount:,.2f}",
        "is_overdue": invoice.is_overdue or False,
        "days_until_due": invoice.days_until_due,
    }


def get_invoices_for_dropdown(
    organization_id: str,
    *,
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Get invoices formatted for dropdown selection.

    Args:
        organization_id: Organization UUID
        supplier_id: Filter by supplier
        status: Filter by status
        limit: Maximum results

    Returns:
        List of dicts with 'value' and 'label'
    """
    invoices = get_all_invoices(
        organization_id,
        supplier_id=supplier_id,
        status=status,
        limit=limit,
    )

    return [
        {
            "value": inv.id,
            "label": f"{inv.invoice_number} - {inv.supplier_name or 'Unknown'} ({inv.total_amount:,.2f} {inv.currency})",
        }
        for inv in invoices
    ]
