"""
Specification Payment Service - CRUD operations for specification_payments table.

Manages incoming (from client) and outgoing (expense) payments on specifications.
Table: kvota.specification_payments (migration 124)
"""

from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal

from services.database import get_supabase


# =============================================================================
# CONSTANTS
# =============================================================================

VALID_CATEGORIES = ("income", "expense")
VALID_CURRENCIES = ("RUB", "USD", "EUR")


# =============================================================================
# VALIDATION
# =============================================================================

def _validate_amount(amount: Decimal) -> None:
    if not isinstance(amount, (Decimal, int, float)) or Decimal(str(amount)) <= 0:
        raise ValueError(f"Amount must be positive, got {amount}")


def _validate_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Category must be one of {VALID_CATEGORIES}, got '{category}'")


def _validate_currency(currency: str) -> None:
    if currency not in VALID_CURRENCIES:
        raise ValueError(f"Invalid currency: {currency}")


# =============================================================================
# CREATE
# =============================================================================

def create_specification_payment(
    specification_id: str,
    organization_id: str,
    payment_date: date,
    amount: Decimal,
    currency: str = "RUB",
    category: str = "income",
    comment: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a payment record for a specification."""
    _validate_amount(amount)
    _validate_category(category)
    _validate_currency(currency)

    supabase = get_supabase()

    row = {
        "specification_id": specification_id,
        "organization_id": organization_id,
        "payment_date": payment_date.isoformat(),
        "amount": str(amount),
        "currency": currency,
        "category": category,
        "comment": comment,
    }
    if created_by:
        row["created_by"] = created_by

    result = supabase.table("specification_payments").insert(row).execute()
    if result.data:
        return result.data[0]
    return None


# =============================================================================
# READ
# =============================================================================

def get_payments_for_specification(specification_id: str) -> List[Dict[str, Any]]:
    """Get all payments for a specification, ordered by payment_date desc."""
    supabase = get_supabase()
    result = (
        supabase.table("specification_payments")
        .select("*")
        .eq("specification_id", specification_id)
        .order("payment_date", desc=True)
        .execute()
    )
    return result.data or []


def get_income_payments(specification_id: str) -> List[Dict[str, Any]]:
    """Get only income payments for a specification."""
    supabase = get_supabase()
    result = (
        supabase.table("specification_payments")
        .select("*")
        .eq("specification_id", specification_id)
        .eq("category", "income")
        .order("payment_date", desc=True)
        .execute()
    )
    return result.data or []


def get_expense_payments(specification_id: str) -> List[Dict[str, Any]]:
    """Get only expense payments for a specification."""
    supabase = get_supabase()
    result = (
        supabase.table("specification_payments")
        .select("*")
        .eq("specification_id", specification_id)
        .eq("category", "expense")
        .order("payment_date", desc=True)
        .execute()
    )
    return result.data or []


# =============================================================================
# SUMMARY
# =============================================================================

def get_payment_summary(specification_id: str) -> Dict[str, Any]:
    """Calculate income/expense totals and balance for a specification."""
    supabase = get_supabase()
    result = (
        supabase.table("specification_payments")
        .select("category, amount")
        .eq("specification_id", specification_id)
        .execute()
    )

    total_income = Decimal("0")
    total_expense = Decimal("0")

    for row in result.data or []:
        amt = Decimal(str(row["amount"]))
        if row["category"] == "income":
            total_income += amt
        elif row["category"] == "expense":
            total_expense += amt

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
    }
