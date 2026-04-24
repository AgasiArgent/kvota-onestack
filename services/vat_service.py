"""
VAT Rate Service — lookup, resolver, admin CRUD.

Provides:
- get_vat_rate(country_code): direct lookup of domestic VAT rate by country
  (used internally by the resolver; returns 20.00 default for unknown).
- resolve_vat_for_invoice(...): buyer-supplier match resolver per REQ-3.
  Returns domestic rate when codes match, 0% when they differ, 0% "unknown"
  when either code is missing (fail-closed).
- list_all_rates / upsert_rate: admin CRUD.

Table: kvota.vat_rates_by_country (Migration 269, reseeded by Migration 296)
"""

import logging
import re
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from services.database import get_supabase

logger = logging.getLogger(__name__)


# Default VAT rate for countries not in the table (used by get_vat_rate; the
# resolver never returns this — it fails closed to 0).
DEFAULT_VAT_RATE = Decimal("20.00")

# ISO 3166-1 alpha-2: exactly 2 ASCII letters
_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")


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
    except Exception as e:
        logger.warning(
            "[vat_service] Failed to fetch VAT rate for %s: %s", code, e
        )
        return DEFAULT_VAT_RATE


def resolve_vat_for_invoice(
    supplier_country_code: str | None,
    buyer_company_id: str,
    supabase_client: Any,
) -> dict:
    """Resolve VAT rate for an invoice line based on country match.

    Rule: rate = domestic rate for country if buyer.country_code == supplier.country_code,
    else 0 (export zero-rated). Fail-closed to 0 on unknown codes.

    Args:
        supplier_country_code: ISO 3166-1 alpha-2 country code of the supplier (or None).
        buyer_company_id: UUID of the buyer company whose country_code to look up.
        supabase_client: Supabase client used to fetch buyer_companies.country_code.

    Returns:
        Dict with keys:
            rate: Decimal — resolved VAT rate percentage.
            reason: "domestic" | "export_zero_rated" | "unknown".

    Raises:
        ValueError: supplier_country_code is a non-empty string with invalid format.
        LookupError: buyer_company_id not found in kvota.buyer_companies.
    """
    # Validate supplier code format (allow None — treated as unknown below)
    supplier_code: str | None = None
    if supplier_country_code is not None:
        normalized = supplier_country_code.strip().upper()
        if not normalized:
            supplier_code = None
        elif not _COUNTRY_CODE_RE.match(normalized):
            raise ValueError(
                f"supplier_country_code must be ISO 3166-1 alpha-2, got: "
                f"{supplier_country_code!r}"
            )
        else:
            supplier_code = normalized

    # Fetch buyer country_code
    result = (
        supabase_client.table("buyer_companies")
        .select("country_code")
        .eq("id", buyer_company_id)
        .maybe_single()
        .execute()
    )
    if result is None or getattr(result, "data", None) is None:
        raise LookupError(
            f"buyer_company_id not found: {buyer_company_id}"
        )

    buyer_raw = result.data.get("country_code")
    buyer_code: str | None = None
    if buyer_raw is not None:
        stripped = str(buyer_raw).strip().upper()
        if stripped and _COUNTRY_CODE_RE.match(stripped):
            buyer_code = stripped

    # Fail-closed: either code missing → 0% unknown
    if supplier_code is None or buyer_code is None:
        return {"rate": Decimal("0"), "reason": "unknown"}

    # Country match → domestic rate; else export zero-rated
    if supplier_code == buyer_code:
        return {"rate": get_vat_rate(supplier_code), "reason": "domestic"}

    return {"rate": Decimal("0"), "reason": "export_zero_rated"}


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
