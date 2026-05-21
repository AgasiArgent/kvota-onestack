"""Customs /api/customs/* endpoints — bulk item update + autofill + certificates.

Handler module (not router). Registered via thin wrapper in
api/routers/customs.py. Originally moved from main.py in Phase 6B-9; the
autofill handler below was added in Wave 1 of the
logistics-customs-redesign spec (Task 3).

REQ-5 customs-phase-1 (Task 5) added two new handlers — ``resolve_rates_handler``
and ``non_tariff_measures_handler`` — and extended ``autofill_handler`` with
an additive ``force_live`` flag plus optional Alta-resolved fields appended
to ``_AUTOFILL_FIELDS`` (strictly additive — never reorder/rename).

Phase B (customs-shared-certificates) Task 5 replaced the per-item +
per-quote expense handlers with the unified certificates CRUD endpoints
(``create_certificate_handler`` / ``list_certificates_handler`` /
``attach_item_handler`` / ``detach_item_handler`` / ``delete_certificate_handler``
/ ``history_certificate_handler``). The old ``/api/customs/expenses/*``
handlers were deleted in the same PR per REQ-2 AC#16 (no-dead-code rule).

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.
Roles: customs, admin, head_of_customs, head_of_logistics (write); plus sales,
quote_controller, spec_controller, finance, top_manager (read on certificates).
head_of_logistics added per PR #105 — dual-hat role in this org.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from postgrest.exceptions import APIError as PostgrestAPIError

from api.lib.errors import error_response
from services import rate_resolver
from services.alta_client import AltaApiError
from services.database import get_supabase
from services.role_service import get_user_role_codes

logger = logging.getLogger(__name__)

_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs", "head_of_logistics"}

# Phase B Req 1 AC#6 + Req 2 AC#10 — read-side role list for certificates.
# Writes (POST/DELETE on /certificates) remain gated by `_CUSTOMS_ROLES`;
# reads (GET /certificates and GET /certificates/history) allow extended
# roles so sales/finance/top-manager can see attached docs without granting
# them edit rights. Frozenset for safe module-level reuse.
_CERT_READ_ROLES: frozenset[str] = frozenset({
    "customs", "admin", "head_of_customs", "head_of_logistics",
    "sales", "quote_controller", "spec_controller", "finance", "top_manager",
})
_READY_STATUSES = {
    "pending_customs",
    "pending_logistics",
    "pending_logistics_and_customs",
    "pending_sales_review",
}

# REQ-5: default payment types resolved by /resolve-rates when caller omits
# include_payment_types. EXP is intentionally excluded — Phase 1 import flow.
_DEFAULT_RESOLVE_PAYMENT_TYPES = (
    "IMP",
    "NDS",
    "AKC",
    "IMPCOMP",
    "IMPDEMP",
    "IMPTMP",
    "IMPDOP",
)

# REQ-5: tnved_code must be exactly 10 digits (ТН ВЭД).
_TNVED_RE = re.compile(r"^\d{10}$")

# Fields propagated by the autofill endpoint from historical quote_items.
# REQ-5 AC#3: STRICTLY ADDITIVE — never reorder, rename, or remove existing
# fields. The frontend ``CustomsAutofillSuggestion`` TS interface mirrors this
# tuple and only marks new entries as optional.
_AUTOFILL_FIELDS = (
    # --- Original fields (Phase 6B-9 logistics-customs-redesign) ---
    # license_*_cost columns were dropped from kvota.quote_items in
    # migration 284 (Phase 5d, 2026-04-18) — they live on invoice_items
    # only. Removed from the autofill contract on 2026-05-12 alongside
    # the FE ghost-key cleanup (FB-260511-212235-0384).
    "hs_code",
    "customs_duty",
    "customs_duty_per_kg",
    "customs_util_fee",
    "customs_excise",
    "customs_eco_fee",
    "customs_honest_mark",
    "license_ds_required",
    "license_ss_required",
    "license_sgr_required",
    # --- REQ-5 additions (customs-phase-1) — appended only ---
    "country_of_origin_oksm",
    "has_origin_certificate",
    "has_fta_certificate",
)

# Subset of _AUTOFILL_FIELDS that actually maps to columns on
# ``kvota.quote_items``. Currently identical to _AUTOFILL_FIELDS since the
# ghost license_*_cost columns were removed (see comment above).
#
# Defined as a literal tuple (not a generator filter) so the static
# schema-drift lint at ``tools/check_select_columns.py`` can resolve it.
_AUTOFILL_SELECT_FIELDS = (
    "hs_code",
    "customs_duty",
    "customs_duty_per_kg",
    "customs_util_fee",
    "customs_excise",
    "customs_eco_fee",
    "customs_honest_mark",
    "license_ds_required",
    "license_ss_required",
    "license_sgr_required",
    "country_of_origin_oksm",
    "has_origin_certificate",
    "has_fta_certificate",
)


def _resolve_dual_auth(request: Request) -> tuple[dict | None, list[str]]:
    """Resolve authenticated user + effective role codes.

    Supports JWT (Next.js) and legacy session (FastHTML). Session path honors
    admin ``impersonated_role`` for role gating (matches user_has_any_role).
    Returns (user_dict, role_codes) or (None, []) when unauthenticated.
    """
    api_user = getattr(request.state, "api_user", None)
    if api_user:
        user_id = str(api_user.id)
        user_meta = api_user.user_metadata or {}
        org_id = user_meta.get("org_id")
        if not org_id:
            try:
                sb = get_supabase()
                om = (
                    sb.table("organization_members")
                    .select("organization_id")
                    .eq("user_id", user_id)
                    .eq("status", "active")
                    .order("created_at")
                    .limit(1)
                    .execute()
                )
                if om.data:
                    org_id = om.data[0]["organization_id"]
            except Exception:
                org_id = None
        role_codes = get_user_role_codes(user_id, org_id) if org_id else []
        return (
            {"id": user_id, "org_id": org_id, "email": api_user.email or ""},
            role_codes,
        )

    try:
        session = request.session
    except (AssertionError, AttributeError):
        return None, []

    user = session.get("user") if session else None
    if not user:
        return None, []

    impersonated_role = session.get("impersonated_role")
    if impersonated_role:
        return user, [impersonated_role]

    return user, user.get("roles", [])


def _safe_float(value) -> float:
    """Coerce value to float, defaulting to 0 on failure/empty."""
    if not value:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def bulk_update_items(request: Request, quote_id: str) -> JSONResponse:
    """PATCH /api/customs/{quote_id}/items/bulk — bulk update customs fields.

    Path: PATCH /api/customs/{quote_id}/items/bulk
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        items: list of objects with fields:
            id (required) — quote_item id
            hs_code (optional str)
            customs_duty (optional number)
            license_ds_required / license_ss_required / license_sgr_required (bool)
    Returns:
        success: bool
        error: str — on failure
    Side Effects:
        - Updates hs_code, customs_duty, license_*_required fields on
          quote_items rows scoped to the given quote_id.
    Roles: customs, admin, head_of_customs, head_of_logistics.

    Response envelope mirrors the legacy FastHTML dict return (no ``data``
    wrapper) for byte-identical compatibility with existing UI callers.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user:
        return JSONResponse(
            {"success": False, "error": "Not authenticated"}, status_code=401
        )

    org_id = user.get("org_id")
    if not org_id:
        return JSONResponse(
            {"success": False, "error": "Not authenticated"}, status_code=401
        )

    if not (set(role_codes) & _CUSTOMS_ROLES):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": "Invalid JSON"}, status_code=400
        )

    items = body.get("items", [])
    if not items:
        return JSONResponse({"success": True})  # Nothing to update

    supabase = get_supabase()

    # Verify quote exists, belongs to org, is not soft-deleted.
    quote_result = (
        supabase.table("quotes")
        .select("id, workflow_status, customs_completed_at")
        .eq("id", quote_id)
        .eq("organization_id", org_id)
        .is_("deleted_at", None)
        .execute()
    )

    if not quote_result.data:
        return JSONResponse(
            {"success": False, "error": "Quote not found"}, status_code=404
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Procurement must be completed before customs edits are allowed.
    if workflow_status not in _READY_STATUSES or quote.get("customs_completed_at"):
        return JSONResponse(
            {
                "success": False,
                "error": "Quote not editable - waiting for procurement",
            },
            status_code=400,
        )

    # Update each item
    for item in items:
        item_id = item.get("id")
        if not item_id:
            continue

        hs_code = item.get("hs_code", "")
        customs_duty = _safe_float(item.get("customs_duty"))

        license_ds_required = bool(item.get("license_ds_required", False))
        license_ss_required = bool(item.get("license_ss_required", False))
        license_sgr_required = bool(item.get("license_sgr_required", False))

        # license_*_cost columns were dropped from kvota.quote_items in
        # migration 284 (Phase 5d) — they live on invoice_items only. Any
        # cost payload from legacy clients is silently ignored here so a
        # stale FE build can't crash with PGRST204.
        supabase.table("quote_items").update(
            {
                "hs_code": hs_code if hs_code else None,
                "customs_duty": customs_duty,
                "license_ds_required": license_ds_required,
                "license_ss_required": license_ss_required,
                "license_sgr_required": license_sgr_required,
            }
        ).eq("id", item_id).eq("quote_id", quote_id).execute()

        # Phase A Req 10 — fire-and-forget audit log of customs choice.
        # Only logs when both tnved_code (10-digit hs_code) and country_oksm
        # are present in the payload. UI will populate proper chosen_variants
        # in Task 11; for now we record the (org, code, country) triple so
        # subsequent identical inputs surface a history banner. Errors must
        # never block the user-visible save (mirror of classifier audit log).
        country_oksm_raw = item.get("country_of_origin_oksm")
        log_tnved_code = (hs_code or "").strip()
        if log_tnved_code and _TNVED_RE.match(log_tnved_code) and country_oksm_raw:
            try:
                country_oksm_int = int(country_oksm_raw)
            except (TypeError, ValueError):
                country_oksm_int = None
            if country_oksm_int and country_oksm_int > 0:
                try:
                    from services.customs_user_choices import log_choice

                    log_choice(
                        organization_id=user["org_id"],
                        user_id=user["id"],
                        tnved_code=log_tnved_code,
                        country_oksm=country_oksm_int,
                        chosen_variants={},
                        manual_override=bool(item.get("manual_override", False)),
                        manual_rate_payload=item.get("manual_rate_payload"),
                    )
                except Exception:
                    # Never block save on audit-log failure.
                    pass

    return JSONResponse({"success": True})


# ---------------------------------------------------------------------------
# Autofill — suggestions from historical quote_items
# ---------------------------------------------------------------------------


async def autofill_handler(
    request: Request, alta_client=None
) -> JSONResponse:
    """POST /api/customs/autofill — suggest customs fields from history.

    Path: POST /api/customs/autofill
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        items: list of objects — { id, brand, product_code,
            tnved_code (optional), country_oksm (optional) }.
        force_live: bool (optional, default False) — REQ-5 AC#3:
            when True AND the historical lookup yielded no suggestion for
            an item that supplied tnved_code+country_oksm, fall back to
            ``services.rate_resolver.resolve_rate(...)`` and emit a
            suggestion populated from the live (or cached) Alta result.
    Returns (envelope: {"success": true, "data": ...}):
        suggestions: list of {
            item_id,                  — quote_item id from input
            source_quote_id,          — historical quote that provided match
            source_quote_idn,         — human-readable Q-number (if resolvable)
            source_created_at,        — ISO timestamp of source quote_item
            hs_code, customs_duty, customs_duty_per_kg,
            customs_util_fee, customs_excise, customs_eco_fee,
            customs_honest_mark,
            license_ds_required, license_ss_required, license_sgr_required,
            country_of_origin_oksm,    — REQ-5 (additive)
            has_origin_certificate,    — REQ-5 (additive)
            has_fta_certificate,       — REQ-5 (additive)
            customs_rates_source,      — REQ-5 (force_live only)
            customs_rates_fetched_at,  — REQ-5 (force_live only)
            customs_rates_summary,     — REQ-5 (force_live only)
        }
    Side Effects: none (read-only). When ``force_live=True`` triggers
        ``rate_resolver.resolve_rate``, that function may UPDATE
        ``tnved_rates.last_used_at`` (cron revalidation hint) — see
        ``services/rate_resolver.py``.
    Roles: customs, admin, head_of_customs, head_of_logistics.

    Strategy: for each (brand, product_code) pair, fetch the newest
    quote_items row WHERE hs_code IS NOT NULL and the hit belongs to the
    caller's organization. Results are scoped to org via quote.organization_id.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user:
        return JSONResponse(
            {
                "success": False,
                "error": {"code": "UNAUTHORIZED", "message": "Not authenticated"},
            },
            status_code=401,
        )

    org_id = user.get("org_id")
    if not org_id:
        return JSONResponse(
            {
                "success": False,
                "error": {"code": "UNAUTHORIZED", "message": "Not authenticated"},
            },
            status_code=401,
        )

    if not (set(role_codes) & _CUSTOMS_ROLES):
        return JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Forbidden"}},
            status_code=403,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON"}},
            status_code=400,
        )

    raw_items = body.get("items") or []
    if not isinstance(raw_items, list):
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "items must be a list"}},
            status_code=400,
        )
    force_live = bool(body.get("force_live", False))

    # Build unique (brand, product_code) keys; remember which item_ids map to each key.
    # Also remember per-item context (tnved_code, country_oksm, certs) so that
    # ``force_live`` fallback can reach the resolver with the right inputs.
    keys_by_pair: dict[tuple[str, str], list[str]] = {}
    item_context: dict[str, dict] = {}
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        brand = (entry.get("brand") or "").strip()
        product_code = (entry.get("product_code") or "").strip()
        if not item_id:
            continue
        item_context[item_id] = {
            "tnved_code": (entry.get("tnved_code") or "").strip() or None,
            "country_oksm": entry.get("country_oksm"),
            "has_origin_certificate": bool(entry.get("has_origin_certificate", False)),
            "has_fta_certificate": bool(entry.get("has_fta_certificate", False)),
        }
        if not brand or not product_code:
            continue
        keys_by_pair.setdefault((brand, product_code), []).append(item_id)

    if not keys_by_pair and not force_live:
        return JSONResponse({"success": True, "data": {"suggestions": []}})

    supabase = get_supabase()

    # Per-pair newest-with-hs-code lookup. Using PostgREST ordering + limit(1)
    # instead of SQL LATERAL since we don't have raw SQL execution available
    # here — N small round-trips scale fine for N=typical quote size (10-30).
    suggestions: list[dict] = []
    source_quote_ids: set[str] = set()
    resolved: list[tuple[list[str], dict]] = []

    for (brand, product_code), item_ids in keys_by_pair.items():
        select_cols = ", ".join(
            ("id", "quote_id", "created_at", *_AUTOFILL_SELECT_FIELDS)
        )
        try:
            result = (
                supabase.table("quote_items")
                .select(f"{select_cols}, quotes!inner(organization_id)")
                .eq("brand", brand)
                .eq("product_code", product_code)
                .not_.is_("hs_code", None)
                .eq("quotes.organization_id", org_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.warning("customs.autofill lookup failed: %s", exc)
            continue

        row = (result.data or [None])[0]
        if not row:
            continue
        source_quote_ids.add(row["quote_id"])
        resolved.append((item_ids, row))

    # Resolve Q-numbers (idn) for source quotes in one round-trip.
    idn_by_quote: dict[str, str] = {}
    if source_quote_ids:
        try:
            q_result = (
                supabase.table("quotes")
                .select("id, idn_quote")
                .in_("id", list(source_quote_ids))
                .execute()
            )
            for qrow in q_result.data or []:
                idn_by_quote[qrow["id"]] = qrow.get("idn_quote") or ""
        except Exception as exc:
            logger.warning("customs.autofill idn lookup failed: %s", exc)

    items_with_history: set[str] = set()
    for item_ids, row in resolved:
        base = {
            "source_quote_id": row["quote_id"],
            "source_quote_idn": idn_by_quote.get(row["quote_id"], ""),
            "source_created_at": row.get("created_at"),
        }
        for field in _AUTOFILL_FIELDS:
            base[field] = row.get(field)
        for item_id in item_ids:
            suggestions.append({"item_id": item_id, **base})
            items_with_history.add(item_id)

    # REQ-5 AC#3 — force_live fallback: items with tnved_code+country_oksm but
    # no historical hit get a suggestion synthesised from the live resolver.
    # The Alta client is injected by the router via Depends; if absent (e.g.
    # legacy callers that haven't been updated yet, or test env without
    # credentials) the fallback is skipped silently — historical lookup
    # response shape is preserved.
    if force_live:
        client = alta_client
        if client is None:
            try:
                from services.alta_client import get_alta_client

                client = get_alta_client()
            except Exception as exc:
                logger.warning(
                    "customs.autofill force_live: Alta client unavailable: %s",
                    exc,
                )
                client = None
        if client is not None:
            await _append_resolver_suggestions(
                suggestions, item_context, items_with_history,
                alta_client=client,
            )

    return JSONResponse({"success": True, "data": {"suggestions": suggestions}})


async def _append_resolver_suggestions(
    suggestions: list[dict],
    item_context: dict[str, dict],
    items_with_history: set[str],
    *,
    alta_client,
) -> None:
    """Synthesise suggestions for items without a historical match via the resolver.

    Only runs when ``force_live=True`` was set on the autofill request. The
    resolver is consulted once per item that supplied tnved_code+country_oksm
    and lacks a historical hit. New optional fields are appended to each
    suggestion: ``customs_rates_source``, ``customs_rates_fetched_at``,
    ``customs_rates_summary``. Existing ``_AUTOFILL_FIELDS`` are populated
    from the resolved rate where derivable (``customs_duty`` from a percent
    slot 1; otherwise None to keep the contract additive).
    """
    today = date.today()
    for item_id, ctx in item_context.items():
        if item_id in items_with_history:
            continue
        tnved_code = ctx.get("tnved_code")
        country_oksm = ctx.get("country_oksm")
        if not tnved_code or not _TNVED_RE.match(tnved_code):
            continue
        try:
            country_oksm_int = int(country_oksm)
        except (TypeError, ValueError):
            continue

        try:
            result = await rate_resolver.resolve_rate(
                tnved_code=tnved_code,
                payment_type="IMP",
                country_oksm=country_oksm_int,
                target_date=today,
                has_certificate=ctx.get("has_origin_certificate", False),
                alta_client=alta_client,
            )
        except Exception as exc:
            logger.warning(
                "customs.autofill force_live resolve failed for %s: %s",
                item_id, exc,
            )
            continue
        # Autofill is best-effort — both NOT_FOUND and ALTA_ERROR mean
        # we have no suggestion to emit. Skip silently either way.
        if result.outcome != rate_resolver.ResolveOutcome.FOUND:
            continue
        resolved = result.rate

        # Best-effort customs_duty extraction from a percent slot 1.
        customs_duty = None
        if resolved.value_1_unit == "percent" and resolved.value_1_number is not None:
            customs_duty = float(resolved.value_1_number)

        sug: dict = {"item_id": item_id}
        for field in _AUTOFILL_FIELDS:
            sug[field] = None
        sug["customs_duty"] = customs_duty
        sug["country_of_origin_oksm"] = country_oksm_int
        sug["has_origin_certificate"] = ctx.get("has_origin_certificate", False)
        sug["has_fta_certificate"] = ctx.get("has_fta_certificate", False)
        sug["customs_rates_source"] = resolved.source
        sug["customs_rates_fetched_at"] = (
            resolved.source_fetched_at.isoformat()
            if resolved.source_fetched_at else None
        )
        sug["customs_rates_summary"] = resolved.raw_value_string or ""
        suggestions.append(sug)


# ---------------------------------------------------------------------------
# REQ-5 — resolve-rates + non-tariff-measures
# ---------------------------------------------------------------------------


def _validate_country_oksm(country_oksm: int) -> JSONResponse | None:
    """Verify country_oksm exists in kvota.countries; None on success.

    Distinguishes a genuine missing-country (400 INVALID_OKSM) from supabase
    connectivity / query failures (503 DB_ERROR) so callers can retry on the
    latter without misleading users that their input is invalid.
    """
    sb = get_supabase()
    try:
        result = (
            sb.table("countries")
            .select("oksm_digital")
            .eq("oksm_digital", country_oksm)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        # Connectivity / RLS / network failure — never treat as bad input.
        logger.warning("countries lookup failed: %s", exc)
        return error_response(
            "DB_ERROR",
            "Country verification failed; please retry",
            503,
        )
    # `result is None` shouldn't happen on the supabase-py path, but guard
    # defensively — same DB_ERROR signal as a raised exception.
    if result is None:
        logger.warning(
            "countries lookup returned None for oksm=%s", country_oksm
        )
        return error_response(
            "DB_ERROR",
            "Country verification failed; please retry",
            503,
        )
    if not (result.data or []):
        return error_response(
            "INVALID_OKSM",
            f"country_oksm {country_oksm} not found in kvota.countries",
            400,
        )
    return None


def _parse_target_date(raw: str | None) -> tuple[date | None, JSONResponse | None]:
    """Parse optional ISO date string from request body. Defaults to today."""
    if raw is None:
        return date.today(), None
    if not isinstance(raw, str):
        return None, error_response("BAD_REQUEST", "date must be ISO date string", 400)
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, error_response(
            "BAD_REQUEST", f"date {raw!r} is not a valid ISO date", 400,
        )


def _serialize_rate(resolved) -> dict:
    """Project a ResolvedRate into the JSON envelope shape consumed by Next.js.

    Includes Migration 301 variant metadata (``description``, ``category_*``,
    ``is_default``, etc.) so the UI can render a льготная-aware selector.
    """
    inner = resolved.rate
    return {
        "payment_type": resolved.payment_type,
        "value_1_number": (
            float(resolved.value_1_number)
            if resolved.value_1_number is not None else None
        ),
        "value_1_unit": resolved.value_1_unit,
        "value_1_currency": resolved.value_1_currency,
        "value_2_number": (
            float(resolved.value_2_number)
            if resolved.value_2_number is not None else None
        ),
        "value_2_unit": resolved.value_2_unit,
        "value_2_currency": resolved.value_2_currency,
        "sign_1": resolved.sign_1,
        "raw_value_string": resolved.raw_value_string,
        # Variant metadata (migration 301) — let UI render льготные options
        # with full context: which products this rate applies to, and the
        # legal document backing it.
        "description": inner.description,
        "category_code": inner.category_code,
        "category_ru": inner.category_ru,
        "condition_text": inner.condition_text,
        "legal_document": inner.legal_document,
        "legal_link": inner.legal_link,
        "order_ref": inner.order_ref,
        "is_default": inner.is_default,
        # Phase 1 returns rates for inspection only — see docstring of
        # resolve_rates_handler. Caller-supplied customs_value/weight/quantity
        # would let us call services.customs_calc.calculate_duty here.
        "calculated_amount_rub": None,
    }


async def resolve_rates_handler(request: Request, alta_client) -> JSONResponse:
    """Resolve customs rates for a tnved+country+date.

    Path: POST /api/customs/resolve-rates
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Params (JSON body):
        tnved_code: str (required) — 10-digit ТН ВЭД code
        country_oksm: int (required) — ОКСМ digital code
        date: str (optional, ISO) — defaults to today
        certificate: bool (optional) — origin certificate
        sp_certificate: bool (optional) — SP certificate
        quote_item_id: str (optional, UUID) — triggers UPDATE quote_items
        force_live: bool (optional) — bypass cache (passed through to resolver
            once it gains a flag; ignored in Phase 1 — resolver always honors
            its own 30-day TTL)
        include_payment_types: list[str] (optional) — defaults to
            (IMP, NDS, AKC, IMPCOMP, IMPDEMP, IMPTMP, IMPDOP).
    Returns:
        Success (200): {success: true, data: {rates, total_rub, source,
            fetched_at}, meta: {partial: bool, outcomes: dict}}
        Errors:
            - 503 ALTA_UNAVAILABLE — Alta API errored on EVERY requested
              payment_type AND no cache. Retry-worthy.
            - 404 RATE_NOT_FOUND — Alta succeeded but reported no rates
              for this (tnved_code, country_oksm). Terminal — user must
              enter the rate manually. (Review fix M4 PR #83.)
            - 400 INVALID_TNVED_CODE / INVALID_OKSM / BAD_REQUEST.

        ``meta.partial`` is True when at least one payment_type came back
        empty/errored but at least one other payment_type FOUND a rate.
        ``meta.outcomes`` is per-payment_type {FOUND, NOT_FOUND, ALTA_ERROR}
        for UI nudges.

        Phase 1 caveat: rates are returned for inspection only —
        ``calculated_amount_rub`` is None per rate and ``total_rub`` is None
        because the request body does not carry customs_value/weight/quantity/
        currency_rates. Callers wanting computed amounts must extend this
        endpoint to accept those inputs and call
        ``services.customs_calc.calculate_duty(...)``.

    Side Effects:
        - On quote_item_id: UPDATE kvota.quote_items SET
          country_of_origin_oksm, has_origin_certificate, has_fta_certificate.
          (customs_duty / customs_duty_percent are intentionally NOT updated
          in Phase 1 because we don't compute amounts — see caveat above.)
        - rate_resolver may UPDATE kvota.tnved_rates SET last_used_at = now().
        - May trigger an Alta API call on cache miss — counts against packet quota.
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    started = time.monotonic()

    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return error_response("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return error_response("FORBIDDEN", "Forbidden", 403)

    try:
        body = await request.json()
    except Exception:
        return error_response("BAD_REQUEST", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return error_response("BAD_REQUEST", "body must be a JSON object", 400)

    tnved_code = (body.get("tnved_code") or "").strip()
    if not tnved_code or not _TNVED_RE.match(tnved_code):
        return error_response(
            "INVALID_TNVED_CODE",
            "tnved_code must be a 10-digit ТН ВЭД code (got %r)" % tnved_code,
            400,
        )

    country_oksm_raw = body.get("country_oksm")
    try:
        country_oksm = int(country_oksm_raw)
    except (TypeError, ValueError):
        return error_response(
            "BAD_REQUEST",
            "country_oksm must be an integer (got %r)" % country_oksm_raw,
            400,
        )

    target_date, date_err = _parse_target_date(body.get("date"))
    if date_err is not None:
        return date_err

    has_certificate = bool(body.get("certificate", False))
    has_sp_certificate = bool(body.get("sp_certificate", False))
    quote_item_id = body.get("quote_item_id") or None
    include_payment_types = body.get("include_payment_types")
    if include_payment_types is None:
        payment_types: tuple[str, ...] = _DEFAULT_RESOLVE_PAYMENT_TYPES
    elif isinstance(include_payment_types, list) and all(
        isinstance(p, str) for p in include_payment_types
    ):
        payment_types = tuple(include_payment_types)
    else:
        return error_response(
            "BAD_REQUEST",
            "include_payment_types must be a list of strings",
            400,
        )

    # Country existence check (REQ-5 AC: 400 INVALID_OKSM)
    country_err = _validate_country_oksm(country_oksm)
    if country_err is not None:
        return country_err

    # Resolve each requested payment_type. Track per-payment_type outcomes
    # (M4 review fix) so we can distinguish "Alta down" from "rate doesn't
    # exist" in the all-empty case.
    resolved_rates: list = []
    outcomes_by_payment_type: dict[str, str] = {}  # debug/meta only
    saw_alta_error = False
    saw_not_found = False
    sources: set[str] = set()
    cache_hit_count = 0
    fetched_at: datetime | None = None
    # Packet-efficiency optimisation: ONE Alta call covers all payment_types
    # (Alta Такса response is comprehensive). Saves ~6 packets per autofill.
    try:
        by_payment_type, outcomes = await rate_resolver.resolve_all_payment_types(
            tnved_code=tnved_code,
            country_oksm=country_oksm,
            target_date=target_date,
            payment_types=payment_types,
            has_certificate=has_certificate,
            has_sp_certificate=has_sp_certificate,
            alta_client=alta_client,
        )
    except Exception as exc:
        logger.warning(
            "resolve_rates: bulk resolver crashed: %s — falling back to all-error",
            exc,
        )
        by_payment_type = {pt: [] for pt in payment_types}
        outcomes = {pt: rate_resolver.ResolveOutcome.ALTA_ERROR for pt in payment_types}

    for payment_type in payment_types:
        outcome = outcomes.get(payment_type, rate_resolver.ResolveOutcome.ALTA_ERROR)
        outcomes_by_payment_type[payment_type] = outcome.name

        if outcome == rate_resolver.ResolveOutcome.ALTA_ERROR:
            saw_alta_error = True
            continue
        if outcome == rate_resolver.ResolveOutcome.NOT_FOUND:
            saw_not_found = True
            continue

        # FOUND — emit every variant. UI shows them as a льготная-aware
        # selector pre-seeded to is_default=true.
        for r in by_payment_type.get(payment_type, []):
            resolved_rates.append(r)
            sources.add(r.source)
            if (
                r.source_fetched_at is not None
                and (datetime.now(timezone.utc) - r.source_fetched_at).total_seconds() > 5
            ):
                cache_hit_count += 1
            if fetched_at is None or (
                r.source_fetched_at is not None and r.source_fetched_at > fetched_at
            ):
                fetched_at = r.source_fetched_at

    if not resolved_rates:
        # M4 review fix (PR #83): distinguish "Alta down" (retry-worthy, 503)
        # from "rate genuinely doesn't exist for this code+country" (terminal,
        # 404). The resolver now reports outcome per call so we can route
        # accurately. Precedence rule: any ALTA_ERROR seen → 503 (could be
        # transient; user should retry). Otherwise all NOT_FOUND → 404 with
        # actionable message ("enter manually").
        if saw_alta_error:
            return error_response(
                "ALTA_UNAVAILABLE",
                "Alta API недоступен. Попробуйте позже.",
                503,
            )
        # All requested payment_types resolved to NOT_FOUND — Alta succeeded
        # but has no data for this combination. No amount of retrying will
        # change that; the user must enter the rate manually.
        return error_response(
            "RATE_NOT_FOUND",
            (
                f"Ставки для {tnved_code} с {country_oksm} не найдены в Alta — "
                "возможно, код требует ручного ввода"
            ),
            404,
        )

    # Optional side-effect: UPDATE quote_items with country + cert flags.
    # We do NOT update customs_duty / customs_duty_percent here because Phase 1
    # does not compute the amount in this endpoint (see docstring caveat).
    if quote_item_id:
        try:
            sb = get_supabase()
            sb.table("quote_items").update(
                {
                    "country_of_origin_oksm": country_oksm,
                    "has_origin_certificate": has_certificate,
                    "has_fta_certificate": bool(body.get("has_fta_certificate", False)),
                }
            ).eq("id", quote_item_id).execute()
        except Exception as exc:
            logger.warning(
                "resolve_rates: failed to update quote_item %s: %s",
                quote_item_id, exc,
            )

    cache_hit = cache_hit_count == len(resolved_rates)
    source_label = (
        "cache" if cache_hit else (sorted(sources)[0] if sources else "unknown")
    )
    # Partial = some payment_types resolved, others didn't (NOT_FOUND or
    # ALTA_ERROR). Surface this so the UI can decide whether to nudge the
    # user about specific missing types (e.g. NDS) without blocking them.
    partial = saw_not_found or saw_alta_error
    latency_ms = int((time.monotonic() - started) * 1000)

    logger.info(
        "customs_resolve_rates",
        extra={
            "user_id": user.get("id"),
            "tnved_code": tnved_code,
            "country_oksm": country_oksm,
            "source": source_label,
            "latency_ms": latency_ms,
            "cache_hit": cache_hit,
            "partial": partial,
        },
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "rates": [_serialize_rate(r) for r in resolved_rates],
                "total_rub": None,  # see docstring caveat
                "source": source_label,
                "fetched_at": (
                    fetched_at.isoformat() if fetched_at else None
                ),
            },
            "meta": {
                "partial": partial,
                "outcomes": outcomes_by_payment_type,
            },
        }
    )


def _serialize_measure(measure) -> dict:
    return {
        "measure_type": measure.measure_type,
        "name": measure.name,
        "description": measure.description,
        "document_basis": measure.document_basis,
        "document_link": measure.document_link,
        "valid_from": measure.valid_from.isoformat() if measure.valid_from else None,
        "valid_to": measure.valid_to.isoformat() if measure.valid_to else None,
    }


async def non_tariff_measures_handler(
    request: Request, alta_client
) -> JSONResponse:
    """Fetch non-tariff regulation measures from Alta xml_nodes.

    Path: POST /api/customs/non-tariff-measures
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Params (JSON body):
        tnved_code: str (required) — 10-digit ТН ВЭД code
        country_oksm: int (required) — ОКСМ digital code
        mode: str (optional) — "import" (default) | "export".
    Returns:
        {success: true, data: {measures, source, fetched_at}}.
        On Alta failure: 503 ALTA_UNAVAILABLE.

    Side Effects: triggers a billed Alta API call (gotcha #5: ~3₽/call,
        billed separately from Такса). Endpoint is invoked only when the UI
        explicitly asks for measures — never on every customs page render.
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    started = time.monotonic()

    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return error_response("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return error_response("FORBIDDEN", "Forbidden", 403)

    try:
        body = await request.json()
    except Exception:
        return error_response("BAD_REQUEST", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return error_response("BAD_REQUEST", "body must be a JSON object", 400)

    tnved_code = (body.get("tnved_code") or "").strip()
    if not tnved_code or not _TNVED_RE.match(tnved_code):
        return error_response(
            "INVALID_TNVED_CODE",
            "tnved_code must be a 10-digit ТН ВЭД code (got %r)" % tnved_code,
            400,
        )

    country_oksm_raw = body.get("country_oksm")
    try:
        country_oksm = int(country_oksm_raw)
    except (TypeError, ValueError):
        return error_response(
            "BAD_REQUEST",
            "country_oksm must be an integer (got %r)" % country_oksm_raw,
            400,
        )

    mode = body.get("mode", "import")
    if mode not in ("import", "export"):
        return error_response(
            "BAD_REQUEST",
            "mode must be 'import' or 'export' (got %r)" % mode,
            400,
        )

    country_err = _validate_country_oksm(country_oksm)
    if country_err is not None:
        return country_err

    try:
        measures = await alta_client.get_non_tariff_measures(
            tncode=tnved_code, country=country_oksm, mode=mode,
        )
    except AltaApiError as exc:
        logger.warning(
            "non_tariff_measures: Alta error %s for tnved_code=%s country=%s",
            exc.code, tnved_code, country_oksm,
        )
        return error_response(
            "ALTA_UNAVAILABLE",
            "Alta API недоступен, попробуйте позже.",
            503,
        )
    except Exception as exc:
        logger.warning(
            "non_tariff_measures: Alta call failed for tnved_code=%s: %s",
            tnved_code, exc,
        )
        return error_response(
            "ALTA_UNAVAILABLE",
            "Alta API недоступен, попробуйте позже.",
            503,
        )

    # Best-effort persistence to kvota.tnved_non_tariff_measures — never fail
    # the response on upsert errors. Cron + manual ingest already keep this
    # table populated; this is just a freshness hint.
    #
    # Use UPSERT against the (tnved_code, country_or_areal, measure_type, name,
    # valid_from) UNIQUE constraint added in migration 299. Without that
    # constraint repeated calls would accumulate duplicate rows (review fix M3).
    try:
        sb = get_supabase()
        if measures:
            now_iso = datetime.now(timezone.utc).isoformat()
            payload = [
                {
                    "tnved_code": m.tnved_code,
                    "country_or_areal": m.country_or_areal,
                    "measure_type": m.measure_type,
                    "name": m.name,
                    "description": m.description,
                    "document_basis": m.document_basis,
                    "document_link": m.document_link,
                    "valid_from": m.valid_from.isoformat() if m.valid_from else None,
                    "valid_to": m.valid_to.isoformat() if m.valid_to else None,
                    "source": "alta-live",
                    "source_fetched_at": now_iso,
                }
                for m in measures
            ]
            sb.table("tnved_non_tariff_measures").upsert(
                payload,
                on_conflict="tnved_code,country_or_areal,measure_type,name,valid_from",
            ).execute()
    except Exception as exc:
        logger.warning(
            "non_tariff_measures: persistence failed for tnved_code=%s: %s",
            tnved_code, exc,
        )

    fetched_at = datetime.now(timezone.utc)
    latency_ms = int((time.monotonic() - started) * 1000)
    # Explicit cost-tracking signal so log search can find every billed call.
    logger.info(
        "customs_non_tariff_measures (3RUB billed)",
        extra={
            "user_id": user.get("id"),
            "tnved_code": tnved_code,
            "country_oksm": country_oksm,
            "mode": mode,
            "measure_count": len(measures),
            "latency_ms": latency_ms,
        },
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "measures": [_serialize_measure(m) for m in measures],
                "source": "alta-live",
                "fetched_at": fetched_at.isoformat(),
            },
        }
    )


async def refresh_customs_snapshot_handler(
    request: Request, quote_id: str, alta_client,
) -> JSONResponse:
    """Re-fetch customs rates and replace the snapshot on the latest version.

    Path: POST /api/quotes/{quote_id}/refresh-customs-snapshot
    Auth: dual JWT/session, customs roles only.
    Body: optional ``{"reason": str}`` for audit purposes.
    Returns:
        success: {success, data: {status, source_at_freeze, warnings, message?}}
        Tier 3 abort: 409 with ``error.code = 'FREEZE_ABORTED'``.

    Behavior (REQ-8 + Q4):
        1. Build a fresh snapshot via customs_freeze_service.build_snapshot().
        2. On Tier 3 abort: return 409 FREEZE_ABORTED with the message
           build_snapshot already constructed; Telegram alert was emitted
           inside build_snapshot.
        3. On Tier 1/2 success: merge the new snapshot into the latest
           quote_versions row's input_variables.customs_rates, overwriting
           any prior snapshot. Warnings are returned to the UI for
           Tier 2 cache-stale display.

    Q5 audit-log is deferred — services/changelog_service.py turned out
    to be a markdown reader, not an event log; a dedicated
    customs_audit_log table is the follow-up scope.
    """
    user, role_codes = _resolve_dual_auth(request)
    if user is None:
        return error_response("UNAUTHORIZED", "Authentication required", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return error_response(
            "FORBIDDEN",
            f"Customs role required (got {role_codes!r})",
            403,
        )

    sb = get_supabase()

    # Verify quote exists and belongs to user's org (cheap permission check).
    # PostgrestAPIError covers .single()'s "no rows" and other PostgREST-level
    # failures (RLS denial, schema mismatch). Genuine network/JSON parsing
    # failures bubble up via the bare except below as 500 DB_ERROR — we never
    # want to mask infra issues behind a misleading 404.
    try:
        quote_resp = (
            sb.table("quotes")
              .select("id, organization_id")
              .eq("id", quote_id)
              .single()
              .execute()
        )
    except PostgrestAPIError as exc:
        # PGRST116 = no rows for .single(); other codes (PGRST301 = RLS, etc.)
        # legitimately mean "not visible to this caller" → still 404.
        logger.info(
            "refresh_customs_snapshot: quote lookup PostgrestAPIError code=%s msg=%s",
            getattr(exc, "code", None), exc,
        )
        return error_response("NOT_FOUND", f"quote {quote_id} not found", 404)
    except Exception as exc:
        # JSON decode failures, connection errors, anything we did not expect.
        logger.error(
            "refresh_customs_snapshot: quote lookup failed for %s: %s",
            quote_id, exc,
        )
        return error_response(
            "DB_ERROR",
            "Quote lookup failed; please retry",
            500,
        )

    quote = getattr(quote_resp, "data", None)
    if not quote:
        return error_response("NOT_FOUND", f"quote {quote_id} not found", 404)

    # Optional reason for audit (recorded in quote_versions.input_variables.change_reason)
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    reason = (body.get("reason") if isinstance(body, dict) else None) or "manual_refresh"

    # Build snapshot — three-tier fallback handled inside
    from services import customs_freeze_service

    started = time.monotonic()
    snapshot_result = await customs_freeze_service.build_snapshot(
        quote_id, alta_client=alta_client,
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    if snapshot_result.status == "abort":
        logger.warning(
            "customs_snapshot_refresh ABORT",
            extra={
                "user_id": user.get("id"),
                "quote_id": quote_id,
                "latency_ms": latency_ms,
                "reason": reason,
            },
        )
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "FREEZE_ABORTED",
                    "message": snapshot_result.message
                                or "Не удалось зафиксировать таможенные ставки",
                },
                "data": {"warnings": snapshot_result.warnings},
            },
            status_code=409,
        )

    # Persist into latest quote_versions row's input_variables
    try:
        latest_resp = (
            sb.table("quote_versions")
              .select("id, input_variables")
              .eq("quote_id", quote_id)
              .order("version", desc=True)
              .limit(1)
              .execute()
        )
    except Exception as exc:
        logger.warning("quote_versions lookup failed for %s: %s", quote_id, exc)
        return error_response(
            "NO_VERSION",
            f"No quote_versions row exists for quote {quote_id} — calculate first",
            409,
        )

    latest = (latest_resp.data or [None])[0]
    if latest is None:
        return error_response(
            "NO_VERSION",
            f"No quote_versions row exists for quote {quote_id} — calculate first",
            409,
        )

    existing_iv = latest.get("input_variables") or {}
    if not isinstance(existing_iv, dict):
        existing_iv = {}
    merged_iv = dict(existing_iv)
    merged_iv["customs_rates"] = snapshot_result.items
    merged_iv["source_at_freeze"] = snapshot_result.source_at_freeze
    # Stash the reason so future audit can read it without a separate table.
    merged_iv["change_reason"] = (
        f"customs_rates_snapshot_replaced: {reason} (by user {user.get('id')})"
    )

    try:
        sb.table("quote_versions") \
          .update({"input_variables": merged_iv}) \
          .eq("id", latest["id"]) \
          .execute()
    except Exception as exc:
        logger.error(
            "Failed to persist refreshed customs snapshot for quote %s: %s",
            quote_id, exc,
        )
        return error_response(
            "DB_ERROR",
            "Snapshot built but persistence failed; please retry",
            500,
        )

    logger.info(
        "customs_snapshot_refresh OK",
        extra={
            "user_id": user.get("id"),
            "quote_id": quote_id,
            "version_id": latest["id"],
            "source_at_freeze": snapshot_result.source_at_freeze,
            "tier": snapshot_result.status,
            "warning_count": len(snapshot_result.warnings),
            "latency_ms": latency_ms,
            "reason": reason,
        },
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "status": snapshot_result.status,
                "source_at_freeze": snapshot_result.source_at_freeze,
                "warnings": snapshot_result.warnings,
                "version_id": latest["id"],
                "item_count": len(snapshot_result.items),
            },
        }
    )


# ===========================================================================
# Phase 2 — TN ВЭД classification by product name (Alta Express)
# ===========================================================================
# Two endpoints:
#   POST /api/customs/classify         — single or batch classification
#   POST /api/customs/classify/select  — record the customs-specialist's pick


def _serialize_candidate(c) -> dict:
    return {
        "code": c.code,
        "probability": c.probability,
        "code_weight": c.code_weight,
        "description": c.description,
    }


def _serialize_classify_result(r) -> dict:
    return {
        "input_idx": r.input_idx,
        "name": r.name,
        "quote_item_id": r.quote_item_id,
        "candidates": [_serialize_candidate(c) for c in r.candidates],
        "error": r.error,
    }


async def classify_handler(request: Request, alta_client) -> JSONResponse:
    """Classify product descriptions to TN ВЭД codes via Alta Express.

    Path: POST /api/customs/classify
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Params (JSON body):
        items: list[{name: str, brand?: str, description?: str,
                     quote_item_id?: uuid}]  (required, non-empty)
    Returns:
        Success (200): {success: true, data: {results, packet_left,
            packet_used, request_id}}
        Errors:
            - 400 BAD_REQUEST — empty items list, malformed JSON
            - 401 UNAUTHORIZED — no auth
            - 403 FORBIDDEN — non-customs role
            - 429 PACKET_EXHAUSTED — Alta packet quota too low to spend
              on classification (cron revalidation budget protected)
            - 503 ALTA_UNAVAILABLE — Alta API errored or unreachable

    Side Effects:
        - Burns 1 Alta Express packet per batch (idempotent on same-day
          retries via stable request_id).
        - Writes one audit row per item to kvota.tnved_classification_log
          (method='express'). chosen_code is filled by /select later.
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return error_response("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return error_response("FORBIDDEN", "Forbidden", 403)

    try:
        body = await request.json()
    except Exception:
        return error_response("BAD_REQUEST", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return error_response("BAD_REQUEST", "body must be a JSON object", 400)

    raw_items = body.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return error_response(
            "BAD_REQUEST",
            "items must be a non-empty list of {name, brand?, description?, quote_item_id?}",
            400,
        )

    from services.classifier import (
        ClassifierError,
        ClassifyInput,
        classify_items,
    )

    inputs: list = []
    for idx, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            return error_response(
                "BAD_REQUEST",
                f"items[{idx}] must be an object",
                400,
            )
        name = (raw.get("name") or "").strip()
        if not name:
            return error_response(
                "BAD_REQUEST",
                f"items[{idx}].name must be a non-empty string",
                400,
            )
        inputs.append(
            ClassifyInput(
                name=name,
                brand=(raw.get("brand") or None),
                description=(raw.get("description") or None),
                quote_item_id=(raw.get("quote_item_id") or None),
            )
        )

    try:
        outcome = await classify_items(
            inputs,
            alta_client=alta_client,
            user_id=user.get("id"),
        )
    except ClassifierError as e:
        # Map service-level error codes to HTTP status.
        status = {
            "BAD_REQUEST": 400,
            "PACKET_EXHAUSTED": 429,
            "ALTA_UNAVAILABLE": 503,
        }.get(e.code, 500)
        return error_response(e.code, e.message, status)
    except Exception as e:
        logger.error("classify_handler: unexpected error: %s", e)
        return error_response("INTERNAL", "Classification failed", 500)

    logger.info(
        "customs_classify",
        extra={
            "user_id": user.get("id"),
            "item_count": len(inputs),
            "request_id": outcome.request_id,
            "packet_left": outcome.packet_left,
        },
    )

    return JSONResponse({
        "success": True,
        "data": {
            "results": [_serialize_classify_result(r) for r in outcome.results],
            "packet_left": outcome.packet_left,
            "packet_used": outcome.packet_used,
            "request_id": outcome.request_id,
        },
    })


async def history_lookup_handler(
    request: Request,
    tnved_code: str,
    country_oksm: int,
) -> JSONResponse:
    """Find last user choice for (org, tnved_code, country) — Phase A Req 10.

    Path: GET /api/customs/items/history?tnved_code=...&country_oksm=...
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Params (query string):
        tnved_code: str (required) — 10-digit ТН ВЭД code
        country_oksm: int (required) — ОКСМ digital code
    Returns:
        Success (200, match found): {success: true, data: {
            user_id, user_email, created_at, chosen_variants,
            manual_override, manual_rate_payload, is_actual
        }}
        Success (200, no match): {success: true, data: null}
        Errors:
            - 401 UNAUTHORIZED — missing auth
            - 403 FORBIDDEN — non-customs role
            - 400 BAD_REQUEST — invalid tnved_code / country_oksm

    Side Effects: read-only — no DB writes.
    Roles: customs, admin, head_of_customs, head_of_logistics.

    Used by the Phase A history banner inside the customs item dialog
    (Task 11) — surfaces the previous customs choice for the same code +
    country combination so the specialist can re-apply the chosen
    variants without re-deriving them from scratch.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return error_response("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return error_response("FORBIDDEN", "Forbidden", 403)

    tnved_code = (tnved_code or "").strip()
    if not _TNVED_RE.match(tnved_code):
        return error_response(
            "BAD_REQUEST",
            f"tnved_code must be a 10-digit ТН ВЭД code (got {tnved_code!r})",
            400,
        )
    if not isinstance(country_oksm, int) or country_oksm <= 0:
        return error_response(
            "BAD_REQUEST",
            f"country_oksm must be a positive integer (got {country_oksm!r})",
            400,
        )

    from services.customs_user_choices import (
        _serialize_rate as _serialize_history_rate,
        find_recent,
    )

    match = find_recent(
        organization_id=user["org_id"],
        tnved_code=tnved_code,
        country_oksm=country_oksm,
    )
    if match is None:
        return JSONResponse({"success": True, "data": None})

    return JSONResponse(
        {
            "success": True,
            "data": {
                "user_id": match.user_id,
                "user_email": match.user_email,
                "created_at": match.created_at.isoformat(),
                "chosen_variants": {
                    pt: _serialize_history_rate(rate)
                    for pt, rate in match.chosen_variants.items()
                },
                "manual_override": match.manual_override,
                "manual_rate_payload": match.manual_rate_payload,
                "is_actual": match.is_actual,
            },
        }
    )


async def classify_select_handler(request: Request) -> JSONResponse:
    """Record the customs-specialist's chosen code and write hs_code.

    Path: POST /api/customs/classify/select
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Params (JSON body):
        quote_item_id:    str (uuid, required)
        chosen_code:      str (10 digits, required)
        candidates_shown: list[{code, probability, code_weight}]
                          (optional — for audit completeness)
        input_text:       str (optional — what user typed when classifying)
    Returns:
        Success (200): {success: true, data: {quote_item_id, hs_code}}
        Errors:
            - 400 INVALID_TNVED_CODE / BAD_REQUEST
            - 401 UNAUTHORIZED / 403 FORBIDDEN
            - 404 NOT_FOUND — quote_item_id doesn't exist
            - 500 DB_ERROR — write failure
    Side Effects:
        - UPDATE kvota.quote_items SET hs_code = chosen_code WHERE id=...
        - INSERT into kvota.tnved_classification_log with chosen_code set.
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return error_response("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return error_response("FORBIDDEN", "Forbidden", 403)

    try:
        body = await request.json()
    except Exception:
        return error_response("BAD_REQUEST", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return error_response("BAD_REQUEST", "body must be a JSON object", 400)

    quote_item_id = (body.get("quote_item_id") or "").strip()
    if not quote_item_id:
        return error_response("BAD_REQUEST", "quote_item_id is required", 400)

    chosen_code = (body.get("chosen_code") or "").strip()
    if not _TNVED_RE.match(chosen_code):
        return error_response(
            "INVALID_TNVED_CODE",
            f"chosen_code must be a 10-digit ТН ВЭД code (got {chosen_code!r})",
            400,
        )

    raw_candidates = body.get("candidates_shown") or []
    if not isinstance(raw_candidates, list):
        return error_response("BAD_REQUEST", "candidates_shown must be a list", 400)
    input_text = (body.get("input_text") or "").strip()

    from services.classifier import Candidate, log_classification_choice

    candidates: list[Candidate] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        try:
            candidates.append(
                Candidate(
                    code=str(raw.get("code") or "").strip(),
                    probability=float(raw.get("probability") or 0.0),
                    code_weight=int(raw.get("code_weight") or 0),
                    description=raw.get("description"),
                )
            )
        except (TypeError, ValueError):
            continue  # skip malformed audit entries — don't block save

    sb = get_supabase()
    try:
        update_resp = (
            sb.table("quote_items")
              .update({"hs_code": chosen_code})
              .eq("id", quote_item_id)
              .execute()
        )
        if not getattr(update_resp, "data", None):
            return error_response(
                "NOT_FOUND",
                f"Quote item {quote_item_id} not found",
                404,
            )
    except Exception as e:
        logger.error(
            "classify_select: failed to update quote_items.hs_code for %s: %s",
            quote_item_id, e,
        )
        return error_response("DB_ERROR", "Failed to save hs_code", 500)

    log_classification_choice(
        quote_item_id=quote_item_id,
        chosen_code=chosen_code,
        candidates=candidates,
        user_id=user.get("id"),
        method="express",
        input_text=input_text,
    )

    logger.info(
        "customs_classify_select",
        extra={
            "user_id": user.get("id"),
            "quote_item_id": quote_item_id,
            "chosen_code": chosen_code,
            "candidate_count": len(candidates),
        },
    )

    return JSONResponse({
        "success": True,
        "data": {
            "quote_item_id": quote_item_id,
            "hs_code": chosen_code,
        },
    })


# ---------------------------------------------------------------------------
# Phase B (customs-shared-certificates) Task 5 — certificates CRUD handlers
# ---------------------------------------------------------------------------
#
# 6 endpoints replace the deleted Phase A `/api/customs/expenses/*` paths:
#   POST   /api/customs/certificates                   create cert + N atts
#   GET    /api/customs/certificates?quote_id=         list with shares
#   POST   /api/customs/certificates/{cid}/items       attach + recompute
#   DELETE /api/customs/certificates/{cid}/items/{id}  detach + recompute
#   DELETE /api/customs/certificates/{cid}             cascade delete
#   GET    /api/customs/certificates/history?...       loose 2-of-3 match
#
# Auth: dual (request.state.api_user OR session.user). Writes are gated by
# `_CUSTOMS_ROLES`; reads by `_CERT_READ_ROLES` (REQ-2 AC#10, REQ-1 AC#6).
# Cross-quote isolation enforced inline before every attachment INSERT
# (REQ-2 AC#11). Atomicity: POST /certificates uses a manual DELETE-cert
# rollback when item attachments fail (Supabase Python client lacks
# transactions; design.md §4.6 step 3 — verify item_ids first, then INSERT
# cert + items; on item-INSERT failure, DELETE the just-created cert).
# Share computation: `_compute_attached_items_payload` fetches the joined
# quote_items, derives RUB cost basis via `customs_value_rub_for_item`,
# and feeds the list into `services.cost_split.split_cost_batch`.


_CERT_FIELDS_PUBLIC = (
    "id",
    "quote_id",
    "type",
    "number",
    "issuer",
    "legal_doc",
    "issued_at",
    "valid_until",
    "cost_rub",
    "notes",
    "display_name",
    "is_custom_expense",
    "created_at",
    "updated_at",
    "created_by",
)


def _require_cert_write_auth(
    request: Request,
) -> tuple[dict, None] | tuple[None, JSONResponse]:
    """Gate to authenticated user with a customs-write role.

    Returns (user, None) on success or (None, JSONResponse) carrying the
    appropriate 401/403 error envelope. Writes use the narrow
    ``_CUSTOMS_ROLES`` set (customs/admin/head_of_customs).
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return None, error_response("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return None, error_response("FORBIDDEN", "Forbidden", 403)
    return user, None


def _require_cert_read_auth(
    request: Request,
) -> tuple[dict, None] | tuple[None, JSONResponse]:
    """Gate to authenticated user with any cert-read role.

    Returns (user, None) on success or (None, JSONResponse) on failure.
    Read endpoints widen the role list to ``_CERT_READ_ROLES``
    (customs/admin/head_of_customs + sales/quote_controller/spec_controller/
    finance/top_manager) per Phase B Req 1 AC#6.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return None, error_response("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CERT_READ_ROLES):
        return None, error_response("FORBIDDEN", "Forbidden", 403)
    return user, None


def _parse_cost_rub(value) -> tuple[float | None, JSONResponse | None]:
    """Parse non-negative RUB amount. Returns (value, error)."""
    if value is None:
        return None, error_response(
            "VALIDATION_ERROR", "cost_rub is required", 400,
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None, error_response(
            "VALIDATION_ERROR", "cost_rub must be a non-negative number", 400,
        )
    if parsed < 0:
        return None, error_response(
            "VALIDATION_ERROR", "cost_rub must be a non-negative number", 400,
        )
    return parsed, None


def _verify_quote_in_org(supabase, quote_id: str, org_id: str) -> dict | None:
    """Verify quote exists, belongs to org, not soft-deleted. Returns row or None."""
    res = (
        supabase.table("quotes")
        .select("id, organization_id, currency")
        .eq("id", quote_id)
        .eq("organization_id", org_id)
        .is_("deleted_at", None)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def _verify_items_in_quote(
    supabase, item_ids: list[str], quote_id: str
) -> tuple[list[dict] | None, JSONResponse | None]:
    """Cross-quote isolation guard (REQ-2 AC#11).

    Verify ALL item_ids belong to ``quote_id`` in a single SELECT. Returns
    (rows, None) on success or (None, JSONResponse) with the appropriate
    422 NOT_IN_QUOTE / 404 NOT_FOUND envelope.
    """
    if not item_ids:
        return [], None

    res = (
        supabase.table("quote_items")
        .select("id, quote_id")
        .in_("id", item_ids)
        .execute()
    )
    rows = res.data or []

    found_ids = {row["id"] for row in rows}
    missing = [iid for iid in item_ids if iid not in found_ids]
    if missing:
        return None, error_response(
            "NOT_FOUND",
            f"Quote item(s) not found: {', '.join(missing)}",
            404,
        )

    wrong_quote = [row["id"] for row in rows if row["quote_id"] != quote_id]
    if wrong_quote:
        return None, error_response(
            "NOT_IN_QUOTE",
            "Позиция не принадлежит КП сертификата",
            422,
        )

    return rows, None


def _compute_attached_items_payload(
    supabase, cert_row: dict, attached_item_ids: list[str]
) -> list[dict]:
    """Compute ``attached_items[]`` shares for a certificate.

    For each item_id in ``attached_item_ids``:
      1. Fetch invoice-level pricing via ``invoice_item_coverage`` JOIN to
         ``invoice_items`` (post-Phase 5d the price columns moved off
         ``quote_items``; the canonical source is ``invoice_items``).
      2. Sum ``purchase_price_original × invoice_items.quantity × ratio``
         across coverage rows for the quote_item, then convert that sum
         to RUB once via ``services.currency_service.convert_amount``.
      3. Pass the list of RUB bases into ``split_cost_batch``.

    Returns ``[{item_id, share_rub, share_percent}]`` rounded to 1
    decimal on share_percent. Empty list if ``attached_item_ids`` is empty.

    Edge cases:
      - quote_item with no coverage rows (item attached to cert but never
        had an invoice picked) → basis = 0; ``split_cost_batch`` falls
        through its zero-sum branch and equal-splits.
      - ``invoice_items.purchase_price_original`` or ``quantity`` NULL →
        treated as 0 (no contribution).
      - currency mismatch across coverage rows for the same quote_item
        violates Phase 5c invariants → raises ``RuntimeError`` with
        diagnostic context (should never happen in practice).
    """
    if not attached_item_ids:
        return []

    from decimal import Decimal

    from services.cost_split import split_cost_batch
    from services.currency_service import convert_amount

    cert_cost = Decimal(str(cert_row.get("cost_rub") or 0))

    # Query 1 — quote_items: validates the IDs resolve and is the public
    # entry-point for the JOIN. ``_verify_items_in_quote`` upstream already
    # gates by quote membership; this call is the per-helper authority on
    # which IDs exist.
    qi_resp = (
        supabase.table("quote_items")
        .select("id, composition_selected_invoice_id, quantity")
        .in_("id", attached_item_ids)
        .execute()
    )
    valid_ids = {row["id"] for row in (qi_resp.data or [])}

    # Query 2 — invoice_item_coverage embedded with invoice_items via
    # PostgREST ``!inner`` join. The pattern mirrors
    # ``services/composition_service.py:371-381`` (proven, in production).
    coverage_resp = (
        supabase.table("invoice_item_coverage")
        .select(
            "quote_item_id, ratio, "
            "invoice_items!inner("
            "id, purchase_price_original, purchase_currency, quantity"
            ")"
        )
        .in_("quote_item_id", attached_item_ids)
        .execute()
    )
    coverage_rows = coverage_resp.data or []

    # Compute per-quote-item RUB basis preserving attachment order.
    bases: list[Decimal] = []
    for qi_id in attached_item_ids:
        if qi_id not in valid_ids:
            # Item disappeared mid-flight — treat as zero basis.
            bases.append(Decimal("0"))
            continue

        qi_coverage = [
            c for c in coverage_rows if c.get("quote_item_id") == qi_id
        ]
        total_in_currency = Decimal("0")
        currency: str | None = None
        for cov in qi_coverage:
            inv = cov.get("invoice_items") or {}
            price = Decimal(str(inv.get("purchase_price_original") or 0))
            inv_qty = Decimal(str(inv.get("quantity") or 0))
            ratio = Decimal(str(cov.get("ratio") or 0))
            inv_currency = inv.get("purchase_currency")
            if inv_currency is None:
                # NOT NULL constraint at the DB level — defensive only.
                continue
            if currency is None:
                currency = inv_currency
            elif currency != inv_currency:
                raise RuntimeError(
                    f"Currency mismatch in invoice_item_coverage for "
                    f"quote_item {qi_id}: {currency!r} vs {inv_currency!r}. "
                    f"Phase 5c invariant violation."
                )
            total_in_currency += price * inv_qty * ratio

        if total_in_currency <= 0 or currency is None:
            bases.append(Decimal("0"))
            continue

        if currency == "RUB":
            # Short-circuit: avoid an unnecessary rate lookup. Mirrors the
            # legacy ``_customs_value_in_rub`` behaviour.
            bases.append(total_in_currency)
            continue

        rub_basis = convert_amount(total_in_currency, currency, "RUB")
        bases.append(Decimal(str(rub_basis)))

    shares = split_cost_batch(bases, cert_cost)

    payload: list[dict] = []
    for iid, share in zip(attached_item_ids, shares):
        if cert_cost > 0:
            pct = (share / cert_cost) * Decimal("100")
            share_percent = float(pct.quantize(Decimal("0.1")))
        else:
            share_percent = 0.0
        payload.append(
            {
                "item_id": iid,
                "share_rub": float(share),
                "share_percent": share_percent,
            }
        )
    return payload


def _serialize_cert(cert_row: dict, attached_items: list[dict]) -> dict:
    """Project a quote_certificates row + attached_items into the API envelope.

    Filters columns to ``_CERT_FIELDS_PUBLIC`` and appends the computed
    ``attached_items: [{item_id, share_rub, share_percent}]`` array.
    """
    out = {k: cert_row.get(k) for k in _CERT_FIELDS_PUBLIC}
    out["cost_rub"] = (
        float(out["cost_rub"]) if out.get("cost_rub") is not None else 0.0
    )
    out["attached_items"] = attached_items
    return out


def _fetch_attached_item_ids_ordered(supabase, cert_id: str) -> list[str]:
    """Fetch attachment item_ids for a cert, ordered by created_at ASC."""
    res = (
        supabase.table("quote_certificate_items")
        .select("item_id, created_at")
        .eq("certificate_id", cert_id)
        .order("created_at")
        .execute()
    )
    return [row["item_id"] for row in (res.data or [])]


async def create_certificate_handler(request: Request) -> JSONResponse:
    """Create a certificate + N item attachments atomically.

    Path: POST /api/customs/certificates
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        quote_id: str (uuid, required)
        type: str (required) — e.g. "СС", "ДС ТР ТС", or "custom_expense"
        number: str (optional)
        issuer: str (optional)
        legal_doc: str (optional)
        issued_at: str (ISO date, optional)
        valid_until: str (ISO date, optional)
        cost_rub: number (required, >= 0)
        notes: str (optional)
        display_name: str (optional, only for is_custom_expense=true)
        is_custom_expense: bool (optional, default false)
        item_ids: list[uuid] (required, may be empty)
    Returns:
        Success (200): {success: true, data: {...cert, attached_items}}
        Errors:
            - 400 VALIDATION_ERROR — bad body / cost_rub negative
            - 401 UNAUTHORIZED / 403 FORBIDDEN
            - 404 NOT_FOUND — quote or item missing
            - 422 NOT_IN_QUOTE — item_id from a different quote
            - 500 INTERNAL — DB write failure (rollback applied)
    Side Effects:
        - INSERT 1 row into kvota.quote_certificates
        - INSERT len(item_ids) rows into kvota.quote_certificate_items
        - On any item-attachment failure, DELETE the just-created cert
          (manual rollback — Supabase Python client lacks transactions).
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    user, err = _require_cert_write_auth(request)
    if err:
        return err

    try:
        body = await request.json()
    except Exception:
        return error_response("VALIDATION_ERROR", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return error_response("VALIDATION_ERROR", "body must be a JSON object", 400)

    quote_id = (body.get("quote_id") or "").strip()
    if not quote_id:
        return error_response("VALIDATION_ERROR", "quote_id is required", 400)

    cert_type = (body.get("type") or "").strip()
    if not cert_type:
        return error_response("VALIDATION_ERROR", "type is required", 400)

    cost_rub, cost_err = _parse_cost_rub(body.get("cost_rub"))
    if cost_err:
        return cost_err

    item_ids_raw = body.get("item_ids")
    if not isinstance(item_ids_raw, list):
        return error_response("VALIDATION_ERROR", "item_ids must be a list", 400)
    item_ids: list[str] = []
    for raw in item_ids_raw:
        if not isinstance(raw, str) or not raw.strip():
            return error_response(
                "VALIDATION_ERROR",
                "item_ids[] must be a list of non-empty strings",
                400,
            )
        item_ids.append(raw.strip())

    is_custom_expense = bool(body.get("is_custom_expense", False))

    supabase = get_supabase()

    quote = _verify_quote_in_org(supabase, quote_id, user["org_id"])
    if not quote:
        return error_response("NOT_FOUND", "Quote not found", 404)

    # Cross-quote isolation guard BEFORE we INSERT anything (REQ-2 AC#11).
    _items, items_err = _verify_items_in_quote(supabase, item_ids, quote_id)
    if items_err:
        return items_err

    # Build the cert payload, omitting unset optional keys to leave DB
    # defaults intact.
    cert_payload = {
        "quote_id": quote_id,
        "type": cert_type,
        "cost_rub": cost_rub,
        "is_custom_expense": is_custom_expense,
        "created_by": user["id"],
    }
    for key in ("number", "issuer", "legal_doc", "issued_at",
                "valid_until", "notes", "display_name"):
        val = body.get(key)
        if val is not None and val != "":
            cert_payload[key] = val

    try:
        inserted = (
            supabase.table("quote_certificates")
            .insert(cert_payload)
            .execute()
        )
    except Exception as exc:
        logger.error("create_certificate: cert insert failed: %s", exc)
        return error_response("INTERNAL", "Failed to create certificate", 500)

    if not inserted.data:
        return error_response("INTERNAL", "Failed to create certificate", 500)

    cert_row = inserted.data[0]
    cert_id = cert_row["id"]

    # Attach items — manual rollback on failure (delete the just-created cert).
    if item_ids:
        attachment_payload = [
            {"certificate_id": cert_id, "item_id": iid} for iid in item_ids
        ]
        try:
            (
                supabase.table("quote_certificate_items")
                .insert(attachment_payload)
                .execute()
            )
        except Exception as exc:
            logger.warning(
                "create_certificate: attachment insert failed for cert=%s "
                "(rolling back): %s",
                cert_id, exc,
            )
            try:
                supabase.table("quote_certificates").delete().eq(
                    "id", cert_id
                ).execute()
            except Exception as rollback_exc:
                logger.error(
                    "create_certificate: rollback DELETE failed for cert=%s: %s",
                    cert_id, rollback_exc,
                )
            return error_response(
                "INTERNAL",
                "Failed to attach items to certificate",
                500,
            )

    # Compute attached_items shares (uses split_cost_batch + RUB derivation).
    attached_items = _compute_attached_items_payload(
        supabase, cert_row, item_ids
    )

    return JSONResponse(
        {"success": True, "data": _serialize_cert(cert_row, attached_items)}
    )


async def list_certificates_handler(request: Request) -> JSONResponse:
    """List certificates (and custom expenses) for a quote with computed shares.

    Path: GET /api/customs/certificates?quote_id={uuid}
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Query params:
        quote_id: str (uuid, required)
    Returns:
        Success (200): {success: true, data: {certificates: [{...cert,
                                                              attached_items}]}}
        Errors:
            - 400 VALIDATION_ERROR — missing quote_id
            - 401 UNAUTHORIZED / 403 FORBIDDEN
            - 404 NOT_FOUND — quote missing or different org
    Side Effects: read-only.
    Roles: customs, admin, head_of_customs, head_of_logistics, sales, quote_controller,
           spec_controller, finance, top_manager.
    """
    user, err = _require_cert_read_auth(request)
    if err:
        return err

    quote_id = (request.query_params.get("quote_id") or "").strip()
    if not quote_id:
        return error_response("VALIDATION_ERROR", "quote_id is required", 400)

    supabase = get_supabase()
    quote = _verify_quote_in_org(supabase, quote_id, user["org_id"])
    if not quote:
        return error_response("NOT_FOUND", "Quote not found", 404)

    certs_res = (
        supabase.table("quote_certificates")
        .select(",".join(_CERT_FIELDS_PUBLIC))
        .eq("quote_id", quote_id)
        .order("created_at", desc=True)
        .execute()
    )
    cert_rows = certs_res.data or []

    certificates: list[dict] = []
    for cert_row in cert_rows:
        attached_item_ids = _fetch_attached_item_ids_ordered(
            supabase, cert_row["id"]
        )
        attached_items = _compute_attached_items_payload(
            supabase, cert_row, attached_item_ids
        )
        certificates.append(_serialize_cert(cert_row, attached_items))

    return JSONResponse(
        {"success": True, "data": {"certificates": certificates}}
    )


def _fetch_cert_in_org(supabase, cert_id: str, org_id: str) -> dict | None:
    """Fetch cert row scoped to org via quote → organization_id. Returns row or None."""
    res = (
        supabase.table("quote_certificates")
        .select(
            ",".join(_CERT_FIELDS_PUBLIC) + ",quotes!inner(organization_id)"
        )
        .eq("id", cert_id)
        .eq("quotes.organization_id", org_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    row = rows[0]
    # Strip the joined quotes payload — callers only need the cert columns.
    row.pop("quotes", None)
    return row


async def attach_item_handler(request: Request, cert_id: str) -> JSONResponse:
    """Attach a quote_item to an existing certificate, returning recomputed shares.

    Path: POST /api/customs/certificates/{cert_id}/items
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        item_id: str (uuid, required)
    Returns:
        Success (200): {success: true, data: {...cert, attached_items}}
        Errors:
            - 400 VALIDATION_ERROR — bad body
            - 401 UNAUTHORIZED / 403 FORBIDDEN
            - 404 NOT_FOUND — cert or item missing (or wrong org)
            - 409 CONFLICT — item already attached (UNIQUE constraint)
            - 422 NOT_IN_QUOTE — item_id from a different quote
            - 500 INTERNAL — DB write failure
    Side Effects: INSERT 1 row into kvota.quote_certificate_items.
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    user, err = _require_cert_write_auth(request)
    if err:
        return err

    try:
        body = await request.json()
    except Exception:
        return error_response("VALIDATION_ERROR", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return error_response("VALIDATION_ERROR", "body must be a JSON object", 400)

    item_id = (body.get("item_id") or "").strip()
    if not item_id:
        return error_response("VALIDATION_ERROR", "item_id is required", 400)

    supabase = get_supabase()

    cert_row = _fetch_cert_in_org(supabase, cert_id, user["org_id"])
    if not cert_row:
        return error_response("NOT_FOUND", "Certificate not found", 404)

    _items, items_err = _verify_items_in_quote(
        supabase, [item_id], cert_row["quote_id"]
    )
    if items_err:
        return items_err

    try:
        (
            supabase.table("quote_certificate_items")
            .insert({"certificate_id": cert_id, "item_id": item_id})
            .execute()
        )
    except PostgrestAPIError as exc:
        # UNIQUE (certificate_id, item_id) → 23505 unique_violation.
        code = getattr(exc, "code", None) or ""
        if code == "23505":
            return error_response(
                "CONFLICT",
                "Item already attached to this certificate",
                409,
            )
        logger.error("attach_item: insert failed for cert=%s: %s", cert_id, exc)
        return error_response("INTERNAL", "Failed to attach item", 500)
    except Exception as exc:
        logger.error("attach_item: insert failed for cert=%s: %s", cert_id, exc)
        return error_response("INTERNAL", "Failed to attach item", 500)

    attached_item_ids = _fetch_attached_item_ids_ordered(supabase, cert_id)
    attached_items = _compute_attached_items_payload(
        supabase, cert_row, attached_item_ids
    )
    return JSONResponse(
        {"success": True, "data": _serialize_cert(cert_row, attached_items)}
    )


async def detach_item_handler(
    request: Request, cert_id: str, item_id: str
) -> JSONResponse:
    """Detach a quote_item from a certificate, returning recomputed shares.

    Path: DELETE /api/customs/certificates/{cert_id}/items/{item_id}
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Returns:
        Success (200): {success: true, data: {...cert, attached_items}}
            attached_items may be [] if this was the last attachment.
        Errors:
            - 401 UNAUTHORIZED / 403 FORBIDDEN
            - 404 NOT_FOUND — cert missing (or wrong org) or attachment missing
    Side Effects: DELETE 1 row from kvota.quote_certificate_items.
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    user, err = _require_cert_write_auth(request)
    if err:
        return err

    supabase = get_supabase()

    cert_row = _fetch_cert_in_org(supabase, cert_id, user["org_id"])
    if not cert_row:
        return error_response("NOT_FOUND", "Certificate not found", 404)

    delete_res = (
        supabase.table("quote_certificate_items")
        .delete()
        .eq("certificate_id", cert_id)
        .eq("item_id", item_id)
        .execute()
    )
    if not (delete_res.data or []):
        return error_response("NOT_FOUND", "Attachment not found", 404)

    attached_item_ids = _fetch_attached_item_ids_ordered(supabase, cert_id)
    attached_items = _compute_attached_items_payload(
        supabase, cert_row, attached_item_ids
    )
    return JSONResponse(
        {"success": True, "data": _serialize_cert(cert_row, attached_items)}
    )


async def delete_certificate_handler(
    request: Request, cert_id: str
) -> JSONResponse:
    """Delete a certificate (cascades to attachments via FK ON DELETE CASCADE).

    Path: DELETE /api/customs/certificates/{cert_id}
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Returns:
        Success (200): {success: true, data: {deleted_id: cert_id}}
        Errors:
            - 401 UNAUTHORIZED / 403 FORBIDDEN
            - 404 NOT_FOUND — cert missing (or wrong org)
    Side Effects:
        - DELETE 1 row from kvota.quote_certificates
        - Cascades to N rows in kvota.quote_certificate_items.
    Roles: customs, admin, head_of_customs, head_of_logistics.
    """
    user, err = _require_cert_write_auth(request)
    if err:
        return err

    supabase = get_supabase()

    cert_row = _fetch_cert_in_org(supabase, cert_id, user["org_id"])
    if not cert_row:
        return error_response("NOT_FOUND", "Certificate not found", 404)

    supabase.table("quote_certificates").delete().eq("id", cert_id).execute()

    return JSONResponse(
        {"success": True, "data": {"deleted_id": cert_id}}
    )


async def history_certificate_handler(request: Request) -> JSONResponse:
    """Find a previous certificate by loose 2-of-3 match (12-month window).

    Path: GET /api/customs/certificates/history
        ?hs_code={code}&brand={brand}&supplier_id={uuid}&current_quote_id={uuid}
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Query params:
        hs_code: str (optional)
        brand: str (optional)
        supplier_id: str (uuid, optional)
        current_quote_id: str (uuid, required) — exclude from match
    Returns:
        Success (200, match): {success: true, data: {match: HistoryCertMatch}}
        Success (200, no match or DB error): {success: true, data: {match: null}}
        Errors:
            - 400 VALIDATION_ERROR — missing current_quote_id
            - 401 UNAUTHORIZED / 403 FORBIDDEN
    Side Effects: read-only.
    Roles: customs, admin, head_of_customs, head_of_logistics, sales, quote_controller,
           spec_controller, finance, top_manager.
    """
    user, err = _require_cert_read_auth(request)
    if err:
        return err

    qp = request.query_params
    current_quote_id = (qp.get("current_quote_id") or "").strip()
    if not current_quote_id:
        return error_response("VALIDATION_ERROR", "current_quote_id is required", 400)

    hs_code = (qp.get("hs_code") or "").strip() or None
    brand = (qp.get("brand") or "").strip() or None
    supplier_id = (qp.get("supplier_id") or "").strip() or None

    from services.quote_certificates_history import find_match

    match = find_match(
        organization_id=user["org_id"],
        current_quote_id=current_quote_id,
        hs_code=hs_code,
        brand=brand,
        supplier_id=supplier_id,
    )
    if match is None:
        return JSONResponse({"success": True, "data": {"match": None}})

    return JSONResponse(
        {
            "success": True,
            "data": {
                "match": {
                    "cert_id": match.cert_id,
                    "type": match.type,
                    "number": match.number,
                    "issuer": match.issuer,
                    "legal_doc": match.legal_doc,
                    "issued_at": (
                        match.issued_at.isoformat()
                        if match.issued_at is not None else None
                    ),
                    "valid_until": (
                        match.valid_until.isoformat()
                        if match.valid_until is not None else None
                    ),
                    "cost_rub": float(match.cost_rub),
                    "created_at": match.created_at.isoformat(),
                    "source_quote_id": match.source_quote_id,
                    "source_item_id": match.source_item_id,
                    "is_actual": match.is_actual,
                }
            },
        }
    )
