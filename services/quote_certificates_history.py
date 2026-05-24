"""Loose 2-of-3 history matcher for ``kvota.quote_certificates`` (Phase B Req 5).

Mirror of :mod:`services.customs_user_choices` (Phase A blueprint, fire-and-forget
DB-error handling pattern). One public dataclass + one public function.

Design contract: ``services/quote_certificates_history.find_match`` returns
the most recent certificate (``ORDER BY created_at DESC LIMIT 1``) whose any
attached ``quote_items`` row matches at least 2 of 3 inputs (``hs_code``,
``brand``, ``supplier_id``), filtered to:

  * Same organization (multi-tenant isolation, Req 5 AC#1).
  * 12-month window (``created_at >= NOW() - INTERVAL '12 months'``).
  * Not the current quote (Req 5 AC#1 last bullet).
  * ``is_custom_expense = FALSE`` (custom expenses don't propagate, Req 5 AC#1).

PostgREST cannot express the 2-of-3 CASE-WHEN counter directly, so the loose
match is computed in Python after a broader server-side filter pulls candidate
certs (already DESC-ordered). Each candidate carries its joined attached
``quote_items`` rows; the first cert with at least one ≥2-of-3 hit wins.

``is_actual`` is computed in Python from ``valid_until`` (NULL or > today →
True) — semantically equal to the SQL expression ``(valid_until IS NULL OR
valid_until > CURRENT_DATE)`` from design.md §4.5.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from services.database import get_supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoryCertMatch:
    """Loose 2-of-3 match from previous quotes (12-month, same org).

    Returned by :func:`find_match` — ``None`` if no match.

    ``is_actual`` is True when ``valid_until IS NULL OR valid_until > today``.
    The frontend uses this to switch ``HistoryBanner`` between the "Apply"
    (info-blue) and "Create new" (amber/warning) variants per Req 4 AC#5/#6.
    """

    cert_id: str
    type: str
    number: str | None
    issuer: str | None
    legal_doc: str | None
    issued_at: date | None
    valid_until: date | None
    cost_rub: Decimal
    created_at: datetime
    source_quote_id: str
    source_item_id: str
    is_actual: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_match(
    *,
    organization_id: str,
    current_quote_id: str,
    hs_code: str | None,
    brand: str | None,
    supplier_id: str | None,
) -> HistoryCertMatch | None:
    """Find the most recent cert matching ≥2-of-3 loose criteria.

    Filters applied (per design.md §4.5 + Req 5 AC#1):

    * ``quote_certificates.created_at >= NOW() - INTERVAL '12 months'``
    * ``quote_certificates.is_custom_expense = FALSE``
    * Joined ``quotes.organization_id = :organization_id``
    * Joined ``quotes.id != :current_quote_id``
    * Joined ``quote_items`` ≥2 of (hs_code, brand, supplier_id) match.

    Order: ``ORDER BY quote_certificates.created_at DESC LIMIT 1``.

    Args:
        organization_id: Tenant isolation key (current user's org).
        current_quote_id: Exclude any cert attached to this quote.
        hs_code: Item HS-code (optional — null criteria don't count toward match).
        brand:   Item brand (optional).
        supplier_id: Item supplier UUID (optional).

    Returns:
        ``HistoryCertMatch`` with the freshness flag ``is_actual``, or ``None``
        when no candidate satisfies the loose match (history is best-effort —
        on any DB error we log a warning and return ``None`` rather than raise,
        per Phase A precedent ``services.customs_user_choices.find_recent``).
    """
    # Fast path: with fewer than 2 non-null inputs the loose-match counter
    # cannot reach 2; skip the round-trip entirely.
    non_null_inputs = sum(
        1 for v in (hs_code, brand, supplier_id) if v is not None
    )
    if non_null_inputs < 2:
        return None

    sb = get_supabase()
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=365)
    ).isoformat()

    try:
        resp = (
            sb.table("quote_certificates")
            .select(
                "id, type, number, issuer, legal_doc, issued_at, "
                "valid_until, cost_original, cost_currency, "
                "created_at, quote_id, "
                "quotes!inner(organization_id), "
                "quote_certificate_items!inner("
                "item_id, "
                "quote_items!inner(id, hs_code, brand, supplier_id)"
                ")"
            )
            .eq("is_custom_expense", False)
            .eq("quotes.organization_id", organization_id)
            .neq("quote_id", current_quote_id)
            .gte("created_at", cutoff_iso)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        logger.warning(
            "quote_certificates_history: find_match failed for org=%s "
            "current_quote=%s: %s",
            organization_id, current_quote_id, exc,
        )
        return None

    rows = getattr(resp, "data", []) or []
    for row in rows:
        attachments = row.get("quote_certificate_items") or []
        for attachment in attachments:
            qi = attachment.get("quote_items") or {}
            if _matches_two_of_three(qi, hs_code, brand, supplier_id):
                return _to_history_cert_match(row, attachment, qi)

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _matches_two_of_three(
    qi: dict,
    hs_code: str | None,
    brand: str | None,
    supplier_id: str | None,
) -> bool:
    """Return True iff ≥ 2 of (hs_code, brand, supplier_id) match this item.

    A null input contributes 0 to the counter (matches design.md §4.5 SQL —
    the CASE-WHEN counts only non-null inputs that equal the joined column).
    """
    matches = 0
    if hs_code is not None and qi.get("hs_code") == hs_code:
        matches += 1
    if brand is not None and qi.get("brand") == brand:
        matches += 1
    if supplier_id is not None and qi.get("supplier_id") == supplier_id:
        matches += 1
    return matches >= 2


def _to_history_cert_match(
    cert_row: dict,
    attachment: dict,
    qi: dict,
) -> HistoryCertMatch:
    """Convert raw PostgREST payload into typed dataclass.

    ``cost_rub`` is parsed via ``Decimal`` to preserve kopek precision. After
    migration 322 the canonical DB column is ``cost_original`` + a separate
    ``cost_currency`` field; we read both and convert to RUB so the
    dataclass stays a RUB-only view (downstream consumers — the
    HistoryBanner — still display in RUB). Legacy rows that lack
    ``cost_original`` fall back to ``cost_rub`` so test fixtures stubbing
    the old shape keep working.
    Date/timestamp fields tolerate both ISO strings and pre-parsed values
    (Supabase Python client returns strings).
    """
    cost_original = _parse_decimal(
        cert_row.get("cost_original")
        if cert_row.get("cost_original") is not None
        else cert_row.get("cost_rub")
    )
    cost_currency_raw = cert_row.get("cost_currency")
    cost_currency = (
        cost_currency_raw.strip().upper()
        if isinstance(cost_currency_raw, str) and cost_currency_raw.strip()
        else "RUB"
    )
    if cost_currency == "RUB" or cost_original == 0:
        cost_rub = cost_original
    else:
        from services.currency_service import convert_amount
        cost_rub = _parse_decimal(
            convert_amount(cost_original, cost_currency, "RUB")
        )
    return HistoryCertMatch(
        cert_id=cert_row["id"],
        type=cert_row["type"],
        number=cert_row.get("number"),
        issuer=cert_row.get("issuer"),
        legal_doc=cert_row.get("legal_doc"),
        issued_at=_parse_date(cert_row.get("issued_at")),
        valid_until=_parse_date(cert_row.get("valid_until")),
        cost_rub=cost_rub,
        created_at=_parse_iso_timestamp(cert_row["created_at"]),
        source_quote_id=cert_row["quote_id"],
        source_item_id=qi.get("id") or attachment["item_id"],
        is_actual=_compute_is_actual(cert_row.get("valid_until")),
    )


def _compute_is_actual(valid_until_raw: str | date | None) -> bool:
    """Mirror SQL ``valid_until IS NULL OR valid_until > CURRENT_DATE``."""
    if valid_until_raw is None:
        return True
    valid_until = _parse_date(valid_until_raw)
    if valid_until is None:
        return True
    return valid_until > date.today()


def _parse_date(value: str | date | None) -> date | None:
    """ISO string or already-a-date → date. None tolerated."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_decimal(value: object) -> Decimal:
    """Numeric (str | int | float | Decimal | None) → Decimal. Defaults to 0."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _parse_iso_timestamp(value: str) -> datetime:
    """ISO 8601 → aware datetime. Tolerates trailing 'Z' (UTC marker)."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
