"""
Logistics Expense Service
CRUD for kvota.deal_logistics_expenses table.
Feature [86aftzex6]: Actual logistics cost tracking per deal stage.
"""

from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
import logging
import os

from supabase import create_client, ClientOptions

from services.currency_service import SUPPORTED_CURRENCIES

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# ============================================================================
# Constants
# ============================================================================

EXPENSE_SUBTYPE_LABELS = {
    "transport":   "Перевозка",
    "storage":     "Хранение",
    "handling":    "Погрузка/разгрузка",
    "customs_fee": "Таможенные сборы",
    "insurance":   "Страхование",
    "other":       "Прочее",
}

# SUPPORTED_CURRENCIES imported from services.currency_service — single source of truth.

# Maps stage_code -> plan_fact_categories.code
STAGE_TO_PLAN_FACT_CATEGORY = {
    'first_mile':    'logistics_first_mile',
    'hub':           'logistics_hub',
    'hub_hub':       'logistics_hub_hub',
    'transit':       'logistics_transit',
    'post_transit':  'logistics_post_transit',
    'last_mile':     'logistics_last_mile',
    # gtd_upload: no expenses
}


def _get_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY,
        options=ClientOptions(schema="kvota")
    )


# ============================================================================
# Data Class
# ============================================================================

@dataclass
class LogisticsExpense:
    id: str
    deal_id: str
    logistics_stage_id: str
    stage_code: str               # from JOIN with logistics_stages
    expense_subtype: str
    amount: Decimal
    currency: str
    expense_date: date
    description: Optional[str]
    document_id: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    organization_id: str


def _parse_expense(data: dict) -> LogisticsExpense:
    def _d(val):
        if not val:
            return None
        if isinstance(val, str):
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        return val

    def _date(val):
        if not val:
            return date.today()
        if isinstance(val, str):
            return date.fromisoformat(val[:10])
        return val

    # stage_code comes from JOIN with logistics_stages via explicit FK hint
    # FK null safety: (data.get("fk") or {}).get("field", default)
    stage_code = (data.get("logistics_stages") or {}).get("stage_code", "")

    return LogisticsExpense(
        id=data["id"],
        deal_id=data["deal_id"],
        logistics_stage_id=data["logistics_stage_id"],
        stage_code=stage_code,
        expense_subtype=data.get("expense_subtype", "transport"),
        amount=Decimal(str(data.get("amount", 0))),
        currency=data.get("currency", "USD"),
        expense_date=_date(data.get("expense_date")),
        description=data.get("description"),
        document_id=data.get("document_id"),
        created_by=data.get("created_by"),
        created_at=_d(data.get("created_at")) or datetime.now(),
        organization_id=data["organization_id"],
    )


# ============================================================================
# Read Operations
# ============================================================================

def get_expenses_for_deal(deal_id: str) -> List[LogisticsExpense]:
    """Get all expenses for a deal, joined with stage_code from logistics_stages."""
    try:
        client = _get_supabase()
        resp = (
            client.table("deal_logistics_expenses")
            .select("*, logistics_stages!deal_logistics_expenses_logistics_stage_id_fkey(stage_code)")
            .eq("deal_id", deal_id)
            .order("expense_date", desc=True)
            .execute()
        )
        return [_parse_expense(r) for r in (resp.data or [])]
    except Exception as e:
        logger.error(f"Error fetching logistics expenses for deal {deal_id}: {e}")
        return []


def get_expenses_for_stage(stage_id: str) -> List[LogisticsExpense]:
    """Get all expenses for a specific logistics stage."""
    try:
        client = _get_supabase()
        resp = (
            client.table("deal_logistics_expenses")
            .select("*, logistics_stages!deal_logistics_expenses_logistics_stage_id_fkey(stage_code)")
            .eq("logistics_stage_id", stage_id)
            .order("expense_date", desc=True)
            .execute()
        )
        return [_parse_expense(r) for r in (resp.data or [])]
    except Exception as e:
        logger.error(f"Error fetching logistics expenses for stage {stage_id}: {e}")
        return []


def get_expense(expense_id: str) -> Optional[LogisticsExpense]:
    """Get a single expense by ID."""
    try:
        client = _get_supabase()
        resp = (
            client.table("deal_logistics_expenses")
            .select("*, logistics_stages!deal_logistics_expenses_logistics_stage_id_fkey(stage_code)")
            .eq("id", expense_id)
            .execute()
        )
        if resp.data:
            return _parse_expense(resp.data[0])
        return None
    except Exception as e:
        logger.error(f"Error fetching expense {expense_id}: {e}")
        return None


# ============================================================================
# Write Operations
# ============================================================================

def create_expense(
    deal_id: str,
    logistics_stage_id: str,
    organization_id: str,
    expense_subtype: str,
    amount: Decimal,
    currency: str,
    expense_date: date,
    description: Optional[str] = None,
    created_by: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Optional[LogisticsExpense]:
    """Create a new logistics expense record."""
    try:
        client = _get_supabase()
        data = {
            "deal_id": deal_id,
            "logistics_stage_id": logistics_stage_id,
            "organization_id": organization_id,
            "expense_subtype": expense_subtype,
            "amount": float(amount),
            "currency": currency,
            "expense_date": expense_date.isoformat() if hasattr(expense_date, 'isoformat') else str(expense_date),
        }
        if description:
            data["description"] = description
        if created_by:
            data["created_by"] = created_by
        if document_id:
            data["document_id"] = document_id

        resp = client.table("deal_logistics_expenses").insert(data).execute()
        if resp.data:
            # Re-fetch with JOIN for stage_code
            return get_expense(resp.data[0]["id"])
        return None
    except Exception as e:
        logger.error(f"Error creating logistics expense: {e}")
        return None


def delete_expense(expense_id: str) -> bool:
    """Delete an expense record. Caller is responsible for deleting the document."""
    try:
        client = _get_supabase()
        client.table("deal_logistics_expenses").delete().eq("id", expense_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting expense {expense_id}: {e}")
        return False


# ============================================================================
# Plan-Fact Sync
# ============================================================================

def sync_plan_fact_for_stage(
    deal_id: str,
    stage_id: str,
    stage_code: str,
    org_id: str,
) -> bool:
    """
    Compute total USD amount for all expenses in this stage and
    upsert a single plan_fact_items row (actual_amount=total, actual_currency='USD').

    Uses the expense_date of the LATEST expense for the exchange rate lookup.
    If no expenses remain (all deleted), sets actual_amount to NULL.

    Returns True on success, False on error.
    """
    from services.currency_service import convert_to_usd
    from decimal import Decimal as _Dec

    category_code = STAGE_TO_PLAN_FACT_CATEGORY.get(stage_code)
    if not category_code:
        return True  # gtd_upload — skip silently

    expenses = get_expenses_for_stage(stage_id)

    try:
        client = _get_supabase()

        # Get the plan_fact_categories.id for this stage's category
        cat_resp = client.table("plan_fact_categories").select("id").eq("code", category_code).execute()
        if not cat_resp.data:
            logger.error(f"plan_fact_category not found for code: {category_code}")
            return False
        category_id = cat_resp.data[0]["id"]

        if not expenses:
            # No expenses: null out the actual_amount if a row exists
            client.table("plan_fact_items") \
                .update({"actual_amount": None, "actual_currency": None, "actual_date": None}) \
                .eq("deal_id", deal_id) \
                .eq("category_id", category_id) \
                .eq("logistics_stage_id", stage_id) \
                .execute()
            return True

        # Sum all expenses converted to USD
        total_usd = _Dec(0)
        latest_date = None
        for exp in expenses:
            usd = convert_to_usd(exp.amount, exp.currency, exp.expense_date)
            total_usd += usd
            if latest_date is None or exp.expense_date > latest_date:
                latest_date = exp.expense_date

        # Upsert: find existing row or insert new
        existing = client.table("plan_fact_items") \
            .select("id") \
            .eq("deal_id", deal_id) \
            .eq("category_id", category_id) \
            .eq("logistics_stage_id", stage_id) \
            .execute()

        if existing.data:
            pfi_id = existing.data[0]["id"]
            client.table("plan_fact_items").update({
                "actual_amount": float(total_usd),
                "actual_currency": "USD",
                "actual_date": latest_date.isoformat() if latest_date else None,
            }).eq("id", pfi_id).execute()
        else:
            client.table("plan_fact_items").insert({
                "deal_id": deal_id,
                "category_id": category_id,
                "logistics_stage_id": stage_id,
                "description": f"Факт логистика: {stage_code}",
                "actual_amount": float(total_usd),
                "actual_currency": "USD",
                "actual_date": latest_date.isoformat() if latest_date else None,
            }).execute()

        return True

    except Exception as e:
        logger.error(f"Error syncing plan_fact for stage {stage_id}: {e}")
        return False


def get_deal_logistics_summary(deal_id: str) -> dict:
    """
    Return per-stage totals and a grand total in USD for display in the tab header.
    Returns: {stage_code: {total_usd, expense_count}, ..., "grand_total_usd": ...}
    """
    from services.currency_service import convert_to_usd
    from decimal import Decimal as _Dec

    expenses = get_expenses_for_deal(deal_id)
    by_stage: dict = {}

    for exp in expenses:
        code = exp.stage_code
        if code not in by_stage:
            by_stage[code] = {"total_usd": _Dec(0), "expense_count": 0}
        usd = convert_to_usd(exp.amount, exp.currency, exp.expense_date)
        by_stage[code]["total_usd"] += usd
        by_stage[code]["expense_count"] += 1

    grand_total = sum(v["total_usd"] for v in by_stage.values())
    return {**by_stage, "grand_total_usd": grand_total}
