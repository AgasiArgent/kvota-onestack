"""
VAT Rate Service — lookup, default fallback, admin CRUD.

Phase 4a: Provides VAT rate lookup by country code (ISO 3166-1 alpha-2).
EAEU countries are seeded at 0%, major import origins at 20%.
Unknown countries default to 20.00% (standard Russian import VAT).

Table: kvota.vat_rates_by_country (Migration 269)
"""

from decimal import Decimal
from datetime import datetime, timezone

from services.database import get_supabase


# Default VAT rate for countries not in the table
DEFAULT_VAT_RATE = Decimal("20.00")


def _get_supabase():
    """Get Supabase client. Wrapped for testability (tests mock this function)."""
    return get_supabase()


def get_vat_rate(country_code: str) -> Decimal:
    """Lookup VAT rate for a country. Returns 20.00 default for unknown countries.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'CN', 'KZ')

    Returns:
        VAT rate as Decimal (e.g., Decimal('0.00') for EAEU, Decimal('20.00') for imports)
    """
    supabase = _get_supabase()
    code = country_code.upper()

    try:
        result = (
            supabase.table("vat_rates_by_country")
            .select("rate")
            .eq("country_code", code)
            .single()
            .execute()
        )
        return Decimal(str(result.data["rate"]))
    except Exception:
        return DEFAULT_VAT_RATE


def list_all_rates() -> list[dict]:
    """Return all VAT rate rows for admin display.

    Returns:
        List of dicts with keys: country_code, rate, notes, updated_at, updated_by
    """
    supabase = _get_supabase()

    result = (
        supabase.table("vat_rates_by_country")
        .select("*")
        .order("country_code")
        .execute()
    )
    return result.data


def upsert_rate(
    country_code: str,
    rate: Decimal,
    notes: str | None,
    user_id: str,
) -> dict:
    """Insert or update a VAT rate. Used by admin UI.

    Args:
        country_code: ISO 3166-1 alpha-2 country code
        rate: VAT rate percentage (e.g., Decimal('20.00'))
        notes: Optional admin note
        user_id: UUID of the user making the change

    Returns:
        The upserted row as a dict
    """
    supabase = _get_supabase()

    row = {
        "country_code": country_code.upper(),
        "rate": float(rate),
        "notes": notes,
        "updated_by": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    result = (
        supabase.table("vat_rates_by_country")
        .upsert(row)
        .execute()
    )
    return result.data[0]
