"""
Supplier Invoice Payment Service - CRUD operations for supplier_invoice_payments table

This module provides functions for managing payments against supplier invoices:
- Register advance, partial, final, and refund payments
- Track which buyer_company made the payment
- Support exchange rate tracking for multi-currency payments
- Auto-update invoice status via database triggers (pending → partially_paid → paid)
- Query payments by invoice, date range, buyer company

Based on app_spec.xml supplier_invoice_payments table (Feature API-011).
"""

from dataclasses import dataclass
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

# Payment type constants
PAYMENT_TYPE_ADVANCE = "advance"
PAYMENT_TYPE_PARTIAL = "partial"
PAYMENT_TYPE_FINAL = "final"
PAYMENT_TYPE_REFUND = "refund"

PAYMENT_TYPES = [
    PAYMENT_TYPE_ADVANCE,
    PAYMENT_TYPE_PARTIAL,
    PAYMENT_TYPE_FINAL,
    PAYMENT_TYPE_REFUND,
]

PAYMENT_TYPE_NAMES = {
    PAYMENT_TYPE_ADVANCE: "Аванс",
    PAYMENT_TYPE_PARTIAL: "Частичная оплата",
    PAYMENT_TYPE_FINAL: "Финальный платеж",
    PAYMENT_TYPE_REFUND: "Возврат",
}

PAYMENT_TYPE_COLORS = {
    PAYMENT_TYPE_ADVANCE: "blue",
    PAYMENT_TYPE_PARTIAL: "yellow",
    PAYMENT_TYPE_FINAL: "green",
    PAYMENT_TYPE_REFUND: "red",
}

# Currency constants (duplicated from supplier_invoice_service for independence)
DEFAULT_CURRENCY = "USD"
SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB", "CNY", "TRY"]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SupplierInvoicePayment:
    """
    Represents a payment against a supplier invoice.

    Tracks payment details including which buyer company made the payment,
    exchange rate at payment time, and payment document reference.
    Maps to supplier_invoice_payments table in database.
    """
    id: str
    invoice_id: str

    # Payment details
    payment_date: date
    amount: Decimal
    currency: str = DEFAULT_CURRENCY
    exchange_rate: Optional[Decimal] = None  # To RUB

    # Payment type
    payment_type: str = PAYMENT_TYPE_ADVANCE

    # Which of our legal entities made the payment
    buyer_company_id: Optional[str] = None

    # Payment reference
    payment_document: Optional[str] = None
    notes: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    # Joined data (optional, from views)
    invoice_number: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_code: Optional[str] = None
    buyer_company_name: Optional[str] = None
    buyer_company_code: Optional[str] = None
    amount_rub: Optional[Decimal] = None
    invoice_total: Optional[Decimal] = None
    invoice_status: Optional[str] = None
    organization_id: Optional[str] = None
    created_by_email: Optional[str] = None


@dataclass
class PaymentSummary:
    """Summary statistics for payments on an invoice."""
    invoice_id: str
    total_paid: Decimal = Decimal("0.00")
    total_refunded: Decimal = Decimal("0.00")
    net_paid: Decimal = Decimal("0.00")
    payment_count: int = 0
    last_payment_date: Optional[date] = None
    advance_amount: Decimal = Decimal("0.00")
    partial_amount: Decimal = Decimal("0.00")
    final_amount: Decimal = Decimal("0.00")


@dataclass
class SupplierPaymentSummary:
    """Summary statistics for payments to a supplier."""
    supplier_id: str
    total_invoiced: Decimal = Decimal("0.00")
    total_paid: Decimal = Decimal("0.00")
    total_refunded: Decimal = Decimal("0.00")
    net_paid: Decimal = Decimal("0.00")
    outstanding: Decimal = Decimal("0.00")
    invoice_count: int = 0
    payment_count: int = 0


@dataclass
class BuyerCompanyPaymentSummary:
    """Summary statistics for payments by buyer company."""
    buyer_company_id: Optional[str]
    buyer_company_name: Optional[str] = None
    buyer_company_code: Optional[str] = None
    total_amount: Decimal = Decimal("0.00")
    payment_count: int = 0
    currency: str = DEFAULT_CURRENCY


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def _parse_date(value: Any) -> Optional[date]:
    """Parse a date value from database."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])  # Handle ISO format with time
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


def _parse_payment(data: dict) -> SupplierInvoicePayment:
    """Parse database row into SupplierInvoicePayment object."""
    return SupplierInvoicePayment(
        id=data["id"],
        invoice_id=data["invoice_id"],
        payment_date=_parse_date(data["payment_date"]),
        amount=_parse_decimal(data.get("amount", 0)),
        currency=data.get("currency", DEFAULT_CURRENCY),
        exchange_rate=_parse_decimal(data.get("exchange_rate")) if data.get("exchange_rate") else None,
        payment_type=data.get("payment_type", PAYMENT_TYPE_ADVANCE),
        buyer_company_id=data.get("buyer_company_id"),
        payment_document=data.get("payment_document"),
        notes=data.get("notes"),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
        created_by=data.get("created_by"),
        # Joined data from views
        invoice_number=data.get("invoice_number"),
        supplier_id=data.get("supplier_id"),
        supplier_name=data.get("supplier_name"),
        supplier_code=data.get("supplier_code"),
        buyer_company_name=data.get("buyer_company_name"),
        buyer_company_code=data.get("buyer_company_code"),
        amount_rub=_parse_decimal(data.get("amount_rub")) if data.get("amount_rub") else None,
        invoice_total=_parse_decimal(data.get("invoice_total")) if data.get("invoice_total") else None,
        invoice_status=data.get("invoice_status"),
        organization_id=data.get("organization_id"),
        created_by_email=data.get("created_by_email"),
    )


def _parse_payment_summary(data: dict) -> PaymentSummary:
    """Parse database row into PaymentSummary object."""
    return PaymentSummary(
        invoice_id=data.get("invoice_id", ""),
        total_paid=_parse_decimal(data.get("total_paid", 0)),
        total_refunded=_parse_decimal(data.get("total_refunded", 0)),
        net_paid=_parse_decimal(data.get("net_paid", 0)),
        payment_count=int(data.get("payment_count", 0)),
        last_payment_date=_parse_date(data.get("last_payment_date")),
        advance_amount=_parse_decimal(data.get("advance_amount", 0)),
        partial_amount=_parse_decimal(data.get("partial_amount", 0)),
        final_amount=_parse_decimal(data.get("final_amount", 0)),
    )


def _parse_supplier_payment_summary(data: dict) -> SupplierPaymentSummary:
    """Parse database row into SupplierPaymentSummary object."""
    return SupplierPaymentSummary(
        supplier_id=data.get("supplier_id", ""),
        total_invoiced=_parse_decimal(data.get("total_invoiced", 0)),
        total_paid=_parse_decimal(data.get("total_paid", 0)),
        total_refunded=_parse_decimal(data.get("total_refunded", 0)),
        net_paid=_parse_decimal(data.get("net_paid", 0)),
        outstanding=_parse_decimal(data.get("outstanding", 0)),
        invoice_count=int(data.get("invoice_count", 0)),
        payment_count=int(data.get("payment_count", 0)),
    )


def _parse_buyer_company_payment_summary(data: dict) -> BuyerCompanyPaymentSummary:
    """Parse database row into BuyerCompanyPaymentSummary object."""
    return BuyerCompanyPaymentSummary(
        buyer_company_id=data.get("buyer_company_id"),
        buyer_company_name=data.get("buyer_company_name"),
        buyer_company_code=data.get("buyer_company_code"),
        total_amount=_parse_decimal(data.get("total_amount", 0)),
        payment_count=int(data.get("payment_count", 0)),
        currency=data.get("currency", DEFAULT_CURRENCY),
    )


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_payment_type(payment_type: str) -> bool:
    """
    Validate payment type.

    Args:
        payment_type: Payment type to validate

    Returns:
        True if valid, False otherwise
    """
    return payment_type in PAYMENT_TYPES


def validate_payment_amount(amount: Any) -> bool:
    """
    Validate payment amount.

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


def validate_exchange_rate(exchange_rate: Any) -> bool:
    """
    Validate exchange rate.

    Args:
        exchange_rate: Exchange rate to validate

    Returns:
        True if valid positive rate, False otherwise
    """
    if exchange_rate is None:
        return True  # Exchange rate is optional
    try:
        decimal_rate = Decimal(str(exchange_rate))
        return decimal_rate > 0
    except Exception:
        return False


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


def validate_payment_document(payment_document: str) -> bool:
    """
    Validate payment document reference.

    Args:
        payment_document: Payment document number to validate

    Returns:
        True if valid, False otherwise
    """
    if not payment_document:
        return True  # Payment document is optional
    return len(payment_document.strip()) > 0 and len(payment_document) <= 100


# =============================================================================
# PAYMENT TYPE HELPERS
# =============================================================================

def get_payment_type_name(payment_type: str) -> str:
    """Get localized payment type name."""
    return PAYMENT_TYPE_NAMES.get(payment_type, payment_type)


def get_payment_type_color(payment_type: str) -> str:
    """Get payment type color for UI."""
    return PAYMENT_TYPE_COLORS.get(payment_type, "gray")


def is_refund(payment_type: str) -> bool:
    """Check if payment type is a refund."""
    return payment_type == PAYMENT_TYPE_REFUND


def is_advance(payment_type: str) -> bool:
    """Check if payment type is an advance."""
    return payment_type == PAYMENT_TYPE_ADVANCE


def is_final_payment(payment_type: str) -> bool:
    """Check if payment type is a final payment."""
    return payment_type == PAYMENT_TYPE_FINAL


# =============================================================================
# CREATE OPERATIONS
# =============================================================================

def register_payment(
    invoice_id: str,
    payment_date: date,
    amount: Decimal,
    *,
    currency: str = DEFAULT_CURRENCY,
    exchange_rate: Optional[Decimal] = None,
    payment_type: str = PAYMENT_TYPE_ADVANCE,
    buyer_company_id: Optional[str] = None,
    payment_document: Optional[str] = None,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[SupplierInvoicePayment]:
    """
    Register a payment against a supplier invoice.

    The invoice status will be auto-updated via database trigger:
    - pending → partially_paid when first payment is made
    - partially_paid → paid when total paid >= invoice amount

    Args:
        invoice_id: Invoice UUID to pay against
        payment_date: Date of payment
        amount: Payment amount
        currency: Currency code (default: USD)
        exchange_rate: Exchange rate to RUB (optional)
        payment_type: Type of payment (advance, partial, final, refund)
        buyer_company_id: Which of our legal entities made the payment
        payment_document: Payment reference (e.g., bank transfer number)
        notes: Additional notes
        created_by: User UUID who registered this

    Returns:
        SupplierInvoicePayment object if successful

    Raises:
        ValueError: If validation fails

    Example:
        payment = register_payment(
            invoice_id="inv-uuid",
            payment_date=date(2025, 1, 20),
            amount=Decimal("2500.00"),
            payment_type="advance",
            buyer_company_id="buyer-uuid",
            payment_document="PAY-2025-001"
        )
    """
    # Validate inputs
    if not validate_payment_amount(amount):
        raise ValueError(f"Invalid payment amount: {amount}")
    if not validate_payment_type(payment_type):
        raise ValueError(f"Invalid payment type: {payment_type}")
    if not validate_currency(currency):
        raise ValueError(f"Invalid currency: {currency}")
    if not validate_exchange_rate(exchange_rate):
        raise ValueError(f"Invalid exchange rate: {exchange_rate}")
    if not validate_payment_document(payment_document):
        raise ValueError(f"Invalid payment document: {payment_document}")

    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoice_payments").insert({
            "invoice_id": invoice_id,
            "payment_date": payment_date.isoformat(),
            "amount": str(amount),
            "currency": currency,
            "exchange_rate": str(exchange_rate) if exchange_rate else None,
            "payment_type": payment_type,
            "buyer_company_id": buyer_company_id,
            "payment_document": payment_document.strip() if payment_document else None,
            "notes": notes,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_payment(result.data[0])
        return None

    except Exception as e:
        print(f"Error registering payment: {e}")
        raise


def register_advance_payment(
    invoice_id: str,
    payment_date: date,
    amount: Decimal,
    *,
    buyer_company_id: Optional[str] = None,
    payment_document: Optional[str] = None,
    exchange_rate: Optional[Decimal] = None,
    currency: str = DEFAULT_CURRENCY,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[SupplierInvoicePayment]:
    """
    Register an advance payment against a supplier invoice.

    Convenience function for registering advance payments.

    Args:
        invoice_id: Invoice UUID
        payment_date: Date of payment
        amount: Payment amount
        buyer_company_id: Which legal entity paid
        payment_document: Payment reference
        exchange_rate: Exchange rate to RUB
        currency: Currency code
        notes: Additional notes
        created_by: User UUID

    Returns:
        SupplierInvoicePayment object
    """
    return register_payment(
        invoice_id=invoice_id,
        payment_date=payment_date,
        amount=amount,
        currency=currency,
        exchange_rate=exchange_rate,
        payment_type=PAYMENT_TYPE_ADVANCE,
        buyer_company_id=buyer_company_id,
        payment_document=payment_document,
        notes=notes,
        created_by=created_by,
    )


def register_final_payment(
    invoice_id: str,
    payment_date: date,
    amount: Decimal,
    *,
    buyer_company_id: Optional[str] = None,
    payment_document: Optional[str] = None,
    exchange_rate: Optional[Decimal] = None,
    currency: str = DEFAULT_CURRENCY,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[SupplierInvoicePayment]:
    """
    Register a final payment against a supplier invoice.

    Convenience function for registering final payments.

    Args:
        invoice_id: Invoice UUID
        payment_date: Date of payment
        amount: Payment amount
        buyer_company_id: Which legal entity paid
        payment_document: Payment reference
        exchange_rate: Exchange rate to RUB
        currency: Currency code
        notes: Additional notes
        created_by: User UUID

    Returns:
        SupplierInvoicePayment object
    """
    return register_payment(
        invoice_id=invoice_id,
        payment_date=payment_date,
        amount=amount,
        currency=currency,
        exchange_rate=exchange_rate,
        payment_type=PAYMENT_TYPE_FINAL,
        buyer_company_id=buyer_company_id,
        payment_document=payment_document,
        notes=notes,
        created_by=created_by,
    )


def register_refund(
    invoice_id: str,
    payment_date: date,
    amount: Decimal,
    *,
    buyer_company_id: Optional[str] = None,
    payment_document: Optional[str] = None,
    exchange_rate: Optional[Decimal] = None,
    currency: str = DEFAULT_CURRENCY,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[SupplierInvoicePayment]:
    """
    Register a refund from a supplier.

    Refunds subtract from the total paid amount, potentially changing
    invoice status from paid → partially_paid → pending.

    Args:
        invoice_id: Invoice UUID
        payment_date: Date of refund
        amount: Refund amount
        buyer_company_id: Which legal entity received the refund
        payment_document: Refund reference
        exchange_rate: Exchange rate to RUB
        currency: Currency code
        notes: Reason for refund
        created_by: User UUID

    Returns:
        SupplierInvoicePayment object
    """
    return register_payment(
        invoice_id=invoice_id,
        payment_date=payment_date,
        amount=amount,
        currency=currency,
        exchange_rate=exchange_rate,
        payment_type=PAYMENT_TYPE_REFUND,
        buyer_company_id=buyer_company_id,
        payment_document=payment_document,
        notes=notes,
        created_by=created_by,
    )


# =============================================================================
# READ OPERATIONS
# =============================================================================

def get_payment(payment_id: str) -> Optional[SupplierInvoicePayment]:
    """
    Get a payment by ID.

    Args:
        payment_id: Payment UUID

    Returns:
        SupplierInvoicePayment object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoice_payments").select("*")\
            .eq("id", payment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_payment(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting payment: {e}")
        return None


def get_payment_with_details(payment_id: str) -> Optional[SupplierInvoicePayment]:
    """
    Get a payment with full context (invoice, supplier, buyer company).

    Uses v_supplier_invoice_payments_full view.

    Args:
        payment_id: Payment UUID

    Returns:
        SupplierInvoicePayment with joined data
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("v_supplier_invoice_payments_full").select("*")\
            .eq("payment_id", payment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            # View uses payment_id as column name
            data = result.data[0]
            data["id"] = data.get("payment_id", payment_id)
            return _parse_payment(data)
        return None

    except Exception as e:
        print(f"Error getting payment with details: {e}")
        # Fallback to basic query
        return get_payment(payment_id)


def get_payments_for_invoice(invoice_id: str) -> List[SupplierInvoicePayment]:
    """
    Get all payments for an invoice.

    Args:
        invoice_id: Invoice UUID

    Returns:
        List of SupplierInvoicePayment objects
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoice_payments").select("*")\
            .eq("invoice_id", invoice_id)\
            .order("payment_date", desc=True)\
            .order("created_at", desc=True)\
            .execute()

        return [_parse_payment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting payments for invoice: {e}")
        return []


def get_payments_for_invoice_with_details(invoice_id: str) -> List[SupplierInvoicePayment]:
    """
    Get all payments for an invoice with buyer company details.

    Uses v_supplier_invoice_payments_full view.

    Args:
        invoice_id: Invoice UUID

    Returns:
        List of SupplierInvoicePayment with joined data
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("v_supplier_invoice_payments_full").select("*")\
            .eq("invoice_id", invoice_id)\
            .order("payment_date", desc=True)\
            .order("created_at", desc=True)\
            .execute()

        payments = []
        for row in result.data or []:
            row["id"] = row.get("payment_id", row.get("id"))
            payments.append(_parse_payment(row))
        return payments

    except Exception as e:
        print(f"Error getting payments with details: {e}")
        # Fallback to basic query
        return get_payments_for_invoice(invoice_id)


def get_all_payments(
    organization_id: str,
    *,
    payment_type: Optional[str] = None,
    buyer_company_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[SupplierInvoicePayment]:
    """
    Get all payments for an organization with filters.

    Uses v_supplier_invoice_payments_full view.

    Args:
        organization_id: Organization UUID
        payment_type: Filter by payment type
        buyer_company_id: Filter by buyer company
        from_date: Filter by payment date >= from_date
        to_date: Filter by payment date <= to_date
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of SupplierInvoicePayment objects with details
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("v_supplier_invoice_payments_full").select("*")\
            .eq("organization_id", organization_id)\
            .order("payment_date", desc=True)\
            .order("created_at", desc=True)

        if payment_type:
            query = query.eq("payment_type", payment_type)
        if buyer_company_id:
            query = query.eq("buyer_company_id", buyer_company_id)
        if from_date:
            query = query.gte("payment_date", from_date.isoformat())
        if to_date:
            query = query.lte("payment_date", to_date.isoformat())

        result = query.range(offset, offset + limit - 1).execute()

        payments = []
        for row in result.data or []:
            row["id"] = row.get("payment_id", row.get("id"))
            payments.append(_parse_payment(row))
        return payments

    except Exception as e:
        print(f"Error getting all payments: {e}")
        return []


def count_payments(
    organization_id: str,
    *,
    invoice_id: Optional[str] = None,
    payment_type: Optional[str] = None,
    buyer_company_id: Optional[str] = None,
) -> int:
    """
    Count payments in an organization.

    Args:
        organization_id: Organization UUID
        invoice_id: Filter by invoice
        payment_type: Filter by payment type
        buyer_company_id: Filter by buyer company

    Returns:
        Number of payments
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("v_supplier_invoice_payments_full").select("payment_id", count="exact")\
            .eq("organization_id", organization_id)

        if invoice_id:
            query = query.eq("invoice_id", invoice_id)
        if payment_type:
            query = query.eq("payment_type", payment_type)
        if buyer_company_id:
            query = query.eq("buyer_company_id", buyer_company_id)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting payments: {e}")
        return 0


def get_recent_payments(
    organization_id: str,
    *,
    days: int = 30,
    limit: int = 50,
) -> List[SupplierInvoicePayment]:
    """
    Get recent payments within a number of days.

    Args:
        organization_id: Organization UUID
        days: Number of days to look back
        limit: Maximum results

    Returns:
        List of recent payments
    """
    from_date = date.today()
    from datetime import timedelta
    from_date = from_date - timedelta(days=days)

    return get_all_payments(
        organization_id,
        from_date=from_date,
        limit=limit,
    )


def get_payments_by_buyer_company(
    organization_id: str,
    buyer_company_id: str,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 100,
) -> List[SupplierInvoicePayment]:
    """
    Get all payments made by a specific buyer company.

    Args:
        organization_id: Organization UUID
        buyer_company_id: Buyer company UUID
        from_date: Filter from date
        to_date: Filter to date
        limit: Maximum results

    Returns:
        List of payments by buyer company
    """
    return get_all_payments(
        organization_id,
        buyer_company_id=buyer_company_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


def get_refunds_for_invoice(invoice_id: str) -> List[SupplierInvoicePayment]:
    """
    Get all refunds for an invoice.

    Args:
        invoice_id: Invoice UUID

    Returns:
        List of refund payments
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("supplier_invoice_payments").select("*")\
            .eq("invoice_id", invoice_id)\
            .eq("payment_type", PAYMENT_TYPE_REFUND)\
            .order("payment_date", desc=True)\
            .execute()

        return [_parse_payment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting refunds: {e}")
        return []


# =============================================================================
# UPDATE OPERATIONS
# =============================================================================

def update_payment(
    payment_id: str,
    *,
    payment_date: Optional[date] = None,
    amount: Optional[Decimal] = None,
    currency: Optional[str] = None,
    exchange_rate: Optional[Decimal] = None,
    payment_type: Optional[str] = None,
    buyer_company_id: Optional[str] = None,
    payment_document: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[SupplierInvoicePayment]:
    """
    Update a payment.

    Note: Updating amount or payment_type will auto-update invoice status.

    Args:
        payment_id: Payment UUID
        payment_date: New payment date
        amount: New amount
        currency: New currency
        exchange_rate: New exchange rate
        payment_type: New payment type
        buyer_company_id: New buyer company
        payment_document: New payment document
        notes: New notes

    Returns:
        Updated SupplierInvoicePayment

    Raises:
        ValueError: If validation fails
    """
    # Validate inputs
    if amount is not None and not validate_payment_amount(amount):
        raise ValueError(f"Invalid payment amount: {amount}")
    if payment_type is not None and not validate_payment_type(payment_type):
        raise ValueError(f"Invalid payment type: {payment_type}")
    if currency is not None and not validate_currency(currency):
        raise ValueError(f"Invalid currency: {currency}")
    if exchange_rate is not None and not validate_exchange_rate(exchange_rate):
        raise ValueError(f"Invalid exchange rate: {exchange_rate}")
    if payment_document is not None and not validate_payment_document(payment_document):
        raise ValueError(f"Invalid payment document: {payment_document}")

    try:
        supabase = _get_supabase()

        # Build update dict
        update_data = {}
        if payment_date is not None:
            update_data["payment_date"] = payment_date.isoformat()
        if amount is not None:
            update_data["amount"] = str(amount)
        if currency is not None:
            update_data["currency"] = currency
        if exchange_rate is not None:
            update_data["exchange_rate"] = str(exchange_rate)
        if payment_type is not None:
            update_data["payment_type"] = payment_type
        if buyer_company_id is not None:
            update_data["buyer_company_id"] = buyer_company_id
        if payment_document is not None:
            update_data["payment_document"] = payment_document.strip() if payment_document else None
        if notes is not None:
            update_data["notes"] = notes

        if not update_data:
            return get_payment(payment_id)

        result = supabase.table("supplier_invoice_payments").update(update_data)\
            .eq("id", payment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_payment(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating payment: {e}")
        raise


def update_payment_document(
    payment_id: str,
    payment_document: str,
) -> Optional[SupplierInvoicePayment]:
    """
    Update the payment document reference.

    Args:
        payment_id: Payment UUID
        payment_document: New payment document

    Returns:
        Updated payment
    """
    return update_payment(payment_id, payment_document=payment_document)


def update_payment_exchange_rate(
    payment_id: str,
    exchange_rate: Decimal,
) -> Optional[SupplierInvoicePayment]:
    """
    Update the exchange rate for a payment.

    Useful when exchange rate was not known at registration time.

    Args:
        payment_id: Payment UUID
        exchange_rate: New exchange rate to RUB

    Returns:
        Updated payment
    """
    return update_payment(payment_id, exchange_rate=exchange_rate)


# =============================================================================
# DELETE OPERATIONS
# =============================================================================

def delete_payment(payment_id: str) -> bool:
    """
    Delete a payment permanently.

    The invoice status will be auto-updated via database trigger.

    Args:
        payment_id: Payment UUID

    Returns:
        True if deleted
    """
    try:
        supabase = _get_supabase()

        supabase.table("supplier_invoice_payments").delete()\
            .eq("id", payment_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting payment: {e}")
        return False


def delete_all_payments_for_invoice(invoice_id: str) -> int:
    """
    Delete all payments for an invoice.

    Use with caution - this will reset invoice to pending status.

    Args:
        invoice_id: Invoice UUID

    Returns:
        Number of payments deleted
    """
    try:
        payments = get_payments_for_invoice(invoice_id)
        count = 0

        for payment in payments:
            if delete_payment(payment.id):
                count += 1

        return count

    except Exception as e:
        print(f"Error deleting all payments: {e}")
        return 0


# =============================================================================
# SUMMARY AND STATISTICS
# =============================================================================

def get_invoice_payment_summary(invoice_id: str) -> PaymentSummary:
    """
    Get payment summary for an invoice.

    Uses database function get_invoice_payments_summary().

    Args:
        invoice_id: Invoice UUID

    Returns:
        PaymentSummary with totals by payment type
    """
    try:
        supabase = _get_supabase()

        # Call database function
        result = supabase.rpc(
            "get_invoice_payments_summary",
            {"p_invoice_id": invoice_id}
        ).execute()

        if result.data and len(result.data) > 0:
            return _parse_payment_summary(result.data[0])

        return PaymentSummary(invoice_id=invoice_id)

    except Exception as e:
        print(f"Error getting payment summary: {e}")
        # Calculate from payments directly
        return _calculate_payment_summary(invoice_id)


def _calculate_payment_summary(invoice_id: str) -> PaymentSummary:
    """Calculate payment summary from payments (fallback)."""
    payments = get_payments_for_invoice(invoice_id)

    summary = PaymentSummary(invoice_id=invoice_id)
    summary.payment_count = len(payments)

    for payment in payments:
        if payment.payment_type == PAYMENT_TYPE_REFUND:
            summary.total_refunded += payment.amount
            summary.net_paid -= payment.amount
        else:
            summary.total_paid += payment.amount
            summary.net_paid += payment.amount

            if payment.payment_type == PAYMENT_TYPE_ADVANCE:
                summary.advance_amount += payment.amount
            elif payment.payment_type == PAYMENT_TYPE_PARTIAL:
                summary.partial_amount += payment.amount
            elif payment.payment_type == PAYMENT_TYPE_FINAL:
                summary.final_amount += payment.amount

        # Track last payment date
        if payment.payment_date:
            if summary.last_payment_date is None or payment.payment_date > summary.last_payment_date:
                summary.last_payment_date = payment.payment_date

    return summary


def get_supplier_payment_summary(
    supplier_id: str,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> SupplierPaymentSummary:
    """
    Get payment summary for a supplier.

    Uses database function get_supplier_payment_summary().

    Args:
        supplier_id: Supplier UUID
        from_date: Filter from date
        to_date: Filter to date

    Returns:
        SupplierPaymentSummary with invoice and payment totals
    """
    try:
        supabase = _get_supabase()

        # Call database function
        result = supabase.rpc(
            "get_supplier_payment_summary",
            {
                "p_supplier_id": supplier_id,
                "p_from_date": from_date.isoformat() if from_date else None,
                "p_to_date": to_date.isoformat() if to_date else None,
            }
        ).execute()

        if result.data and len(result.data) > 0:
            return _parse_supplier_payment_summary(result.data[0])

        return SupplierPaymentSummary(supplier_id=supplier_id)

    except Exception as e:
        print(f"Error getting supplier payment summary: {e}")
        return SupplierPaymentSummary(supplier_id=supplier_id)


def get_payments_summary_by_buyer_company(
    organization_id: str,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[BuyerCompanyPaymentSummary]:
    """
    Get payment totals grouped by buyer company.

    Uses database function get_payments_by_buyer_company().

    Args:
        organization_id: Organization UUID
        from_date: Filter from date
        to_date: Filter to date

    Returns:
        List of BuyerCompanyPaymentSummary objects
    """
    try:
        supabase = _get_supabase()

        # Call database function
        result = supabase.rpc(
            "get_payments_by_buyer_company",
            {
                "p_organization_id": organization_id,
                "p_from_date": from_date.isoformat() if from_date else None,
                "p_to_date": to_date.isoformat() if to_date else None,
            }
        ).execute()

        if result.data:
            return [_parse_buyer_company_payment_summary(row) for row in result.data]

        return []

    except Exception as e:
        print(f"Error getting buyer company summaries: {e}")
        return []


def get_payment_stats(
    organization_id: str,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Get overall payment statistics for an organization.

    Args:
        organization_id: Organization UUID
        from_date: Filter from date
        to_date: Filter to date

    Returns:
        Dict with payment statistics
    """
    try:
        payments = get_all_payments(
            organization_id,
            from_date=from_date,
            to_date=to_date,
            limit=10000,  # Get all for stats
        )

        stats = {
            "total_payments": len(payments),
            "total_amount": Decimal("0.00"),
            "total_refunds": Decimal("0.00"),
            "net_amount": Decimal("0.00"),
            "by_type": {
                PAYMENT_TYPE_ADVANCE: {"count": 0, "amount": Decimal("0.00")},
                PAYMENT_TYPE_PARTIAL: {"count": 0, "amount": Decimal("0.00")},
                PAYMENT_TYPE_FINAL: {"count": 0, "amount": Decimal("0.00")},
                PAYMENT_TYPE_REFUND: {"count": 0, "amount": Decimal("0.00")},
            },
            "by_currency": {},
        }

        for payment in payments:
            amount = payment.amount
            ptype = payment.payment_type
            currency = payment.currency

            stats["by_type"][ptype]["count"] += 1
            stats["by_type"][ptype]["amount"] += amount

            if ptype == PAYMENT_TYPE_REFUND:
                stats["total_refunds"] += amount
                stats["net_amount"] -= amount
            else:
                stats["total_amount"] += amount
                stats["net_amount"] += amount

            # By currency
            if currency not in stats["by_currency"]:
                stats["by_currency"][currency] = {"count": 0, "amount": Decimal("0.00")}
            stats["by_currency"][currency]["count"] += 1
            if ptype == PAYMENT_TYPE_REFUND:
                stats["by_currency"][currency]["amount"] -= amount
            else:
                stats["by_currency"][currency]["amount"] += amount

        return stats

    except Exception as e:
        print(f"Error getting payment stats: {e}")
        return {"total_payments": 0}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_remaining_amount(invoice_id: str, invoice_total: Decimal) -> Decimal:
    """
    Calculate remaining amount to pay for an invoice.

    Args:
        invoice_id: Invoice UUID
        invoice_total: Total invoice amount

    Returns:
        Remaining amount
    """
    summary = get_invoice_payment_summary(invoice_id)
    return invoice_total - summary.net_paid


def is_invoice_fully_paid(invoice_id: str, invoice_total: Decimal) -> bool:
    """
    Check if an invoice is fully paid.

    Args:
        invoice_id: Invoice UUID
        invoice_total: Total invoice amount

    Returns:
        True if fully paid
    """
    remaining = get_remaining_amount(invoice_id, invoice_total)
    return remaining <= Decimal("0.00")


def format_payment_for_display(payment: SupplierInvoicePayment) -> Dict[str, Any]:
    """
    Format payment for display in UI.

    Args:
        payment: SupplierInvoicePayment object

    Returns:
        Dict with formatted values
    """
    return {
        "id": payment.id,
        "invoice_id": payment.invoice_id,
        "invoice_number": payment.invoice_number or "",
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "amount": f"{payment.amount:,.2f}",
        "amount_numeric": float(payment.amount),
        "currency": payment.currency,
        "exchange_rate": f"{payment.exchange_rate:,.4f}" if payment.exchange_rate else None,
        "amount_rub": f"{payment.amount_rub:,.2f}" if payment.amount_rub else None,
        "payment_type": payment.payment_type,
        "payment_type_name": get_payment_type_name(payment.payment_type),
        "payment_type_color": get_payment_type_color(payment.payment_type),
        "is_refund": is_refund(payment.payment_type),
        "buyer_company_id": payment.buyer_company_id,
        "buyer_company_name": payment.buyer_company_name or "",
        "buyer_company_code": payment.buyer_company_code or "",
        "payment_document": payment.payment_document or "",
        "supplier_name": payment.supplier_name or "",
        "supplier_code": payment.supplier_code or "",
        "notes": payment.notes or "",
    }


def get_payments_for_display(
    invoice_id: str,
) -> List[Dict[str, Any]]:
    """
    Get payments formatted for display.

    Args:
        invoice_id: Invoice UUID

    Returns:
        List of formatted payment dicts
    """
    payments = get_payments_for_invoice_with_details(invoice_id)
    return [format_payment_for_display(p) for p in payments]
