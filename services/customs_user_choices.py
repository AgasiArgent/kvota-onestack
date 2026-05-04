"""History service for ``kvota.tnved_user_choices`` (Phase A Req 10).

Mirror of :func:`services.classifier.log_classification_choice` pattern.
Fire-and-forget INSERT, swallow errors. Lookup is org-scoped + best-effort
matching against actual variants from the resolver (LOOSE match —
``category_code`` AND ``value_1_number``; ``description`` differences
are tolerated, Alta sometimes rephrases category labels).

Tariff freshness — Alta is source-of-truth; ``valid_until`` is NOT
stored for tariff choices. Cost-aware expiry for certificates is
Phase B scope.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime
from typing import Any

from services.alta_client import Rate
from services.database import get_supabase

logger = logging.getLogger(__name__)


# All payment_type slots persisted as separate JSONB columns. Order matters
# only for stable serialisation in tests — runtime is dict-keyed.
_PAYMENT_TYPES: tuple[str, ...] = (
    "IMP",
    "IMPDEMP",
    "IMPCOMP",
    "IMPDOP",
    "IMPTMP",
    "NDS",
)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoryMatch:
    """Найденная история для (org, tnved_code, country).

    ``is_actual`` is computed via LOOSE match against today's resolver
    variants — True when every chosen variant's ``category_code`` AND
    ``value_1_number`` are still found among actual variants for the
    same payment_type. Description differences tolerated. False → UI
    shows warning «Alta изменила варианты».
    """
    user_id: str
    user_email: str | None      # joined from auth.users (best-effort)
    chosen_variants: dict[str, Rate]  # by payment_type
    manual_override: bool
    manual_rate_payload: dict[str, Any] | None
    created_at: datetime
    is_actual: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_choice(
    *,
    organization_id: str,
    user_id: str,
    tnved_code: str,
    country_oksm: int,
    chosen_variants: dict[str, Rate],   # by payment_type
    manual_override: bool = False,
    manual_rate_payload: dict[str, Any] | None = None,
) -> None:
    """Persist customs tariff choice. Suppresses DB errors — never blocks save.

    Writes one row to ``kvota.tnved_user_choices`` with a JSONB snapshot of
    every chosen variant (by payment_type) plus the optional manual override
    payload. Fire-and-forget — losing an audit row must never break the
    user-visible save flow (mirror of classifier.log_classification_choice).
    """
    sb = get_supabase()
    try:
        sb.table("tnved_user_choices").insert({
            "organization_id": organization_id,
            "user_id": user_id,
            "tnved_code": tnved_code,
            "country_oksm": country_oksm,
            "chosen_imp_variant":     _serialize_rate(chosen_variants.get("IMP")),
            "chosen_impdemp_variant": _serialize_rate(chosen_variants.get("IMPDEMP")),
            "chosen_impcomp_variant": _serialize_rate(chosen_variants.get("IMPCOMP")),
            "chosen_impdop_variant":  _serialize_rate(chosen_variants.get("IMPDOP")),
            "chosen_imptmp_variant":  _serialize_rate(chosen_variants.get("IMPTMP")),
            "chosen_nds_variant":     _serialize_rate(chosen_variants.get("NDS")),
            "manual_override": manual_override,
            "manual_rate_payload": manual_rate_payload,
        }).execute()
    except Exception as e:
        logger.warning(
            "customs_user_choices: failed to log choice for org=%s code=%s: %s",
            organization_id, tnved_code, e,
        )


def find_recent(
    *,
    organization_id: str,
    tnved_code: str,
    country_oksm: int,
    actual_variants: dict[str, list[Rate]] | None = None,
) -> HistoryMatch | None:
    """Lookup last record for (org, code, country). Returns None if absent.

    When ``actual_variants`` is provided, computes the ``is_actual`` flag via
    LOOSE match: every chosen variant's ``category_code`` AND
    ``value_1_number`` must still appear among today's resolver variants
    (``description`` differences tolerated, Alta sometimes rephrases
    category labels). False → UI shows warning «Alta изменила варианты».

    When ``actual_variants`` is None (caller doesn't want the freshness
    check), ``is_actual`` defaults to True so the UI can still offer
    autofill as a suggestion.
    """
    sb = get_supabase()
    try:
        resp = (
            sb.table("tnved_user_choices")
              .select(
                  "user_id,"
                  "chosen_imp_variant,"
                  "chosen_impdemp_variant,"
                  "chosen_impcomp_variant,"
                  "chosen_impdop_variant,"
                  "chosen_imptmp_variant,"
                  "chosen_nds_variant,"
                  "manual_override,"
                  "manual_rate_payload,"
                  "created_at"
              )
              .eq("organization_id", organization_id)
              .eq("tnved_code", tnved_code)
              .eq("country_oksm", country_oksm)
              .order("created_at", desc=True)
              .limit(1)
              .execute()
        )
    except Exception as e:
        logger.warning(
            "customs_user_choices: find_recent failed for org=%s code=%s: %s",
            organization_id, tnved_code, e,
        )
        return None

    rows = getattr(resp, "data", []) or []
    if not rows:
        return None

    row = rows[0]
    chosen_variants: dict[str, Rate] = {}
    for pt in _PAYMENT_TYPES:
        col = f"chosen_{pt.lower()}_variant"
        raw = row.get(col)
        if raw:
            rate = _deserialize_rate(raw)
            if rate is not None:
                chosen_variants[pt] = rate

    is_actual = (
        _compute_is_actual(chosen_variants, actual_variants)
        if actual_variants is not None
        else True
    )

    user_email = _fetch_user_email(row["user_id"])

    return HistoryMatch(
        user_id=row["user_id"],
        user_email=user_email,
        chosen_variants=chosen_variants,
        manual_override=bool(row.get("manual_override", False)),
        manual_rate_payload=row.get("manual_rate_payload"),
        created_at=_parse_iso_timestamp(row["created_at"]),
        is_actual=is_actual,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _serialize_rate(rate: Rate | None) -> dict | None:
    """Rate dataclass → JSONB-friendly dict. Returns None if rate is None.

    Stores every Rate field including the introduction-rate slots
    (value_1/2/3 + signs + units + currencies) so manual_override
    payloads round-trip exactly (Req 10 AC#7).
    """
    if rate is None:
        return None
    return {
        "tnved_code": rate.tnved_code,
        "payment_type": rate.payment_type,
        "country_or_areal": rate.country_or_areal,
        "valid_from": rate.valid_from.isoformat() if rate.valid_from else None,
        "valid_to": rate.valid_to.isoformat() if rate.valid_to else None,
        "value_1_number": (
            float(rate.value_1_number)
            if rate.value_1_number is not None
            else None
        ),
        "value_1_unit": rate.value_1_unit,
        "value_1_currency": rate.value_1_currency,
        "value_2_number": (
            float(rate.value_2_number)
            if rate.value_2_number is not None
            else None
        ),
        "value_2_unit": rate.value_2_unit,
        "value_2_currency": rate.value_2_currency,
        "sign_1": rate.sign_1,
        "value_3_number": (
            float(rate.value_3_number)
            if rate.value_3_number is not None
            else None
        ),
        "value_3_unit": rate.value_3_unit,
        "value_3_currency": rate.value_3_currency,
        "sign_2": rate.sign_2,
        "raw_value_string": rate.raw_value_string,
        "certificate_required": rate.certificate_required,
        "sp_certificate_required": rate.sp_certificate_required,
        "description": rate.description,
        "category_code": rate.category_code,
        "category_ru": rate.category_ru,
        "condition_text": rate.condition_text,
        "legal_document": rate.legal_document,
        "legal_link": rate.legal_link,
        "order_ref": rate.order_ref,
        "is_default": rate.is_default,
        "source": rate.source,
    }


def _deserialize_rate(d: dict) -> Rate | None:
    """JSONB dict → Rate dataclass. Returns None on parse failure.

    Tolerates missing optional fields (older snapshots may predate the
    full Rate schema). Critical fields (``tnved_code``, ``payment_type``,
    ``valid_from``) must be present — otherwise the row is unusable.
    """
    try:
        valid_from_raw = d.get("valid_from")
        valid_from = (
            _date.fromisoformat(valid_from_raw)
            if valid_from_raw
            else _date.today()
        )
        valid_to_raw = d.get("valid_to")
        valid_to = (
            _date.fromisoformat(valid_to_raw) if valid_to_raw else None
        )
        return Rate(
            tnved_code=d["tnved_code"],
            payment_type=d["payment_type"],
            country_or_areal=d.get("country_or_areal"),
            valid_from=valid_from,
            valid_to=valid_to,
            value_1_number=d.get("value_1_number"),
            value_1_unit=d.get("value_1_unit"),
            value_1_currency=d.get("value_1_currency"),
            value_2_number=d.get("value_2_number"),
            value_2_unit=d.get("value_2_unit"),
            value_2_currency=d.get("value_2_currency"),
            sign_1=d.get("sign_1"),
            value_3_number=d.get("value_3_number"),
            value_3_unit=d.get("value_3_unit"),
            value_3_currency=d.get("value_3_currency"),
            sign_2=d.get("sign_2"),
            raw_value_string=d.get("raw_value_string"),
            certificate_required=bool(d.get("certificate_required", False)),
            sp_certificate_required=bool(d.get("sp_certificate_required", False)),
            description=d.get("description"),
            category_code=d.get("category_code"),
            category_ru=d.get("category_ru"),
            condition_text=d.get("condition_text"),
            legal_document=d.get("legal_document"),
            legal_link=d.get("legal_link"),
            order_ref=d.get("order_ref"),
            is_default=bool(d.get("is_default", False)),
            source=d.get("source"),
        )
    except Exception as e:
        logger.warning(
            "customs_user_choices: failed to deserialize Rate snapshot: %s", e,
        )
        return None


def _compute_is_actual(
    chosen: dict[str, Rate],
    actual: dict[str, list[Rate]],
) -> bool:
    """LOOSE match — ``category_code`` AND ``value_1_number`` must match.

    ``description`` differences tolerated (Alta sometimes rephrases category
    descriptions without changing semantic meaning). Returns False if any
    chosen variant's payment_type is missing from ``actual`` or none of the
    actual variants for that payment_type carry the same
    (category_code, value_1_number) pair.
    """
    for pt, chosen_rate in chosen.items():
        actual_list = actual.get(pt, [])
        match_found = any(
            a.category_code == chosen_rate.category_code
            and a.value_1_number == chosen_rate.value_1_number
            for a in actual_list
        )
        if not match_found:
            return False
    return True


def _fetch_user_email(user_id: str) -> str | None:
    """Best-effort email lookup via Supabase admin auth API.

    Returns None on any error so the UI never breaks on a stale or
    deleted ``user_id`` (mirror of api/notes.py:_fetch_user_profiles
    pattern, scaled down to a single user).
    """
    try:
        sb = get_supabase()
        resp = sb.auth.admin.get_user_by_id(user_id)
        user = getattr(resp, "user", None) or resp
        return getattr(user, "email", None)
    except Exception as e:
        logger.warning(
            "customs_user_choices: failed to fetch email for user=%s: %s",
            user_id, e,
        )
        return None


def _parse_iso_timestamp(value: str) -> datetime:
    """ISO 8601 → aware datetime. Tolerates trailing 'Z' (UTC marker)."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
