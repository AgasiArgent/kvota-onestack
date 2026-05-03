"""Customs /api/customs/* endpoints — bulk item update + autofill + expenses.

Handler module (not router). Registered via thin wrapper in
api/routers/customs.py. Originally moved from main.py in Phase 6B-9; the
autofill + expense handlers below were added in Wave 1 of the
logistics-customs-redesign spec (Tasks 3 + 9).

REQ-5 customs-phase-1 (Task 5) added two new handlers — ``resolve_rates_handler``
and ``non_tariff_measures_handler`` — and extended ``autofill_handler`` with
an additive ``force_live`` flag plus optional Alta-resolved fields appended
to ``_AUTOFILL_FIELDS`` (strictly additive — never reorder/rename).

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.
Roles: customs, admin, head_of_customs.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from postgrest.exceptions import APIError as PostgrestAPIError

from services import rate_resolver
from services.alta_client import AltaApiError
from services.database import get_supabase
from services.role_service import get_user_role_codes

logger = logging.getLogger(__name__)

_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}
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
    "license_ds_cost",
    "license_ss_cost",
    "license_sgr_cost",
    # --- REQ-5 additions (customs-phase-1) — appended only ---
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
            license_ds_cost / license_ss_cost / license_sgr_cost (number)
    Returns:
        success: bool
        error: str — on failure
    Side Effects:
        - Updates hs_code, customs_duty, license_* fields on quote_items rows
          scoped to the given quote_id.
    Roles: customs, admin, head_of_customs.

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

        license_ds_cost = _safe_float(item.get("license_ds_cost"))
        license_ss_cost = _safe_float(item.get("license_ss_cost"))
        license_sgr_cost = _safe_float(item.get("license_sgr_cost"))

        supabase.table("quote_items").update(
            {
                "hs_code": hs_code if hs_code else None,
                "customs_duty": customs_duty,
                "license_ds_required": license_ds_required,
                "license_ds_cost": license_ds_cost,
                "license_ss_required": license_ss_required,
                "license_ss_cost": license_ss_cost,
                "license_sgr_required": license_sgr_required,
                "license_sgr_cost": license_sgr_cost,
            }
        ).eq("id", item_id).eq("quote_id", quote_id).execute()

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
            license_ds_cost, license_ss_cost, license_sgr_cost,
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
    Roles: customs, admin, head_of_customs.

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
        select_cols = ", ".join(("id", "quote_id", "created_at", *_AUTOFILL_FIELDS))
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
# Customs expenses — per-item + per-quote CRUD
# ---------------------------------------------------------------------------


def _expense_error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


def _parse_amount_rub(value) -> float | None:
    """Parse non-negative RUB amount. Returns None on invalid input."""
    if value is None:
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _require_customs_auth(request: Request) -> tuple[dict, None] | tuple[None, JSONResponse]:
    """Gate a request to authenticated users with a customs role.

    Returns (user, None) on success or (None, JSONResponse) on failure.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return None, _expense_error("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return None, _expense_error("FORBIDDEN", "Forbidden", 403)
    return user, None


async def create_item_expense(request: Request, item_id: str) -> JSONResponse:
    """POST /api/customs/items/{item_id}/expenses — create per-item expense.

    Path: POST /api/customs/items/{item_id}/expenses
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        label: str (required, non-empty)
        amount_rub: number (required, >= 0, RUB only)
        notes: str (optional)
    Returns: { success, data: { expense_id } }.
    Side Effects: inserts a row into ``customs_item_expenses``.
    Roles: customs, admin, head_of_customs.
    """
    user, err = _require_customs_auth(request)
    if err:
        return err

    try:
        body = await request.json()
    except Exception:
        return _expense_error("BAD_REQUEST", "Invalid JSON", 400)

    label = (body.get("label") or "").strip()
    if not label:
        return _expense_error("BAD_REQUEST", "label is required", 400)

    amount = _parse_amount_rub(body.get("amount_rub"))
    if amount is None:
        return _expense_error("BAD_REQUEST", "amount_rub must be a non-negative number", 400)

    notes = body.get("notes")
    if notes is not None:
        notes = str(notes).strip() or None

    supabase = get_supabase()

    # Scope check: ensure quote_item belongs to caller's org (via quote → org).
    qi_result = (
        supabase.table("quote_items")
        .select("id, quote_id, quotes!inner(organization_id)")
        .eq("id", item_id)
        .eq("quotes.organization_id", user["org_id"])
        .limit(1)
        .execute()
    )
    if not qi_result.data:
        return _expense_error("NOT_FOUND", "Quote item not found", 404)

    inserted = (
        supabase.table("customs_item_expenses")
        .insert(
            {
                "quote_item_id": item_id,
                "label": label,
                "amount_rub": amount,
                "notes": notes,
                "created_by": user["id"],
            }
        )
        .execute()
    )
    if not inserted.data:
        return _expense_error("INTERNAL", "Failed to create expense", 500)

    return JSONResponse(
        {"success": True, "data": {"expense_id": inserted.data[0]["id"]}}
    )


async def delete_item_expense(request: Request, expense_id: str) -> JSONResponse:
    """DELETE /api/customs/items/expenses/{expense_id} — delete per-item expense.

    Path: DELETE /api/customs/items/expenses/{expense_id}
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Returns: { success }.
    Side Effects: removes the row from ``customs_item_expenses``.
    Roles: customs, admin, head_of_customs.
    """
    user, err = _require_customs_auth(request)
    if err:
        return err

    supabase = get_supabase()
    # Org-scope check: join via quote_items → quotes → organization_id.
    scope_check = (
        supabase.table("customs_item_expenses")
        .select("id, quote_items!inner(quotes!inner(organization_id))")
        .eq("id", expense_id)
        .eq("quote_items.quotes.organization_id", user["org_id"])
        .limit(1)
        .execute()
    )
    if not scope_check.data:
        return _expense_error("NOT_FOUND", "Expense not found", 404)

    supabase.table("customs_item_expenses").delete().eq("id", expense_id).execute()
    return JSONResponse({"success": True})


async def create_quote_expense(request: Request, quote_id: str) -> JSONResponse:
    """POST /api/customs/quotes/{quote_id}/expenses — create per-quote expense.

    Path: POST /api/customs/quotes/{quote_id}/expenses
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        label: str (required, non-empty)
        amount_rub: number (required, >= 0, RUB only)
        notes: str (optional)
    Returns: { success, data: { expense_id } }.
    Side Effects: inserts a row into ``customs_quote_expenses``.
    Roles: customs, admin, head_of_customs.
    """
    user, err = _require_customs_auth(request)
    if err:
        return err

    try:
        body = await request.json()
    except Exception:
        return _expense_error("BAD_REQUEST", "Invalid JSON", 400)

    label = (body.get("label") or "").strip()
    if not label:
        return _expense_error("BAD_REQUEST", "label is required", 400)

    amount = _parse_amount_rub(body.get("amount_rub"))
    if amount is None:
        return _expense_error("BAD_REQUEST", "amount_rub must be a non-negative number", 400)

    notes = body.get("notes")
    if notes is not None:
        notes = str(notes).strip() or None

    supabase = get_supabase()

    q_result = (
        supabase.table("quotes")
        .select("id, organization_id")
        .eq("id", quote_id)
        .eq("organization_id", user["org_id"])
        .limit(1)
        .execute()
    )
    if not q_result.data:
        return _expense_error("NOT_FOUND", "Quote not found", 404)

    inserted = (
        supabase.table("customs_quote_expenses")
        .insert(
            {
                "quote_id": quote_id,
                "label": label,
                "amount_rub": amount,
                "notes": notes,
                "created_by": user["id"],
            }
        )
        .execute()
    )
    if not inserted.data:
        return _expense_error("INTERNAL", "Failed to create expense", 500)

    return JSONResponse(
        {"success": True, "data": {"expense_id": inserted.data[0]["id"]}}
    )


async def delete_quote_expense(request: Request, expense_id: str) -> JSONResponse:
    """DELETE /api/customs/quotes/expenses/{expense_id} — delete per-quote expense.

    Path: DELETE /api/customs/quotes/expenses/{expense_id}
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Returns: { success }.
    Side Effects: removes the row from ``customs_quote_expenses``.
    Roles: customs, admin, head_of_customs.
    """
    user, err = _require_customs_auth(request)
    if err:
        return err

    supabase = get_supabase()
    scope_check = (
        supabase.table("customs_quote_expenses")
        .select("id, quotes!inner(organization_id)")
        .eq("id", expense_id)
        .eq("quotes.organization_id", user["org_id"])
        .limit(1)
        .execute()
    )
    if not scope_check.data:
        return _expense_error("NOT_FOUND", "Expense not found", 404)

    supabase.table("customs_quote_expenses").delete().eq("id", expense_id).execute()
    return JSONResponse({"success": True})


# ---------------------------------------------------------------------------
# REQ-5 — resolve-rates + non-tariff-measures
# ---------------------------------------------------------------------------


def _err(code: str, message: str, status: int) -> JSONResponse:
    """Standard error envelope used by the REQ-5 handlers."""
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


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
        return _err(
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
        return _err(
            "DB_ERROR",
            "Country verification failed; please retry",
            503,
        )
    if not (result.data or []):
        return _err(
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
        return None, _err("BAD_REQUEST", "date must be ISO date string", 400)
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, _err(
            "BAD_REQUEST", f"date {raw!r} is not a valid ISO date", 400,
        )


def _serialize_rate(resolved) -> dict:
    """Project a ResolvedRate into the JSON envelope shape consumed by Next.js.

    Keeps the field names aligned with ``kvota.tnved_rates`` so frontend code
    can reuse generated DB types.
    """
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
    Roles: customs, admin, head_of_customs.
    """
    started = time.monotonic()

    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return _err("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return _err("FORBIDDEN", "Forbidden", 403)

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return _err("BAD_REQUEST", "body must be a JSON object", 400)

    tnved_code = (body.get("tnved_code") or "").strip()
    if not tnved_code or not _TNVED_RE.match(tnved_code):
        return _err(
            "INVALID_TNVED_CODE",
            "tnved_code must be a 10-digit ТН ВЭД code (got %r)" % tnved_code,
            400,
        )

    country_oksm_raw = body.get("country_oksm")
    try:
        country_oksm = int(country_oksm_raw)
    except (TypeError, ValueError):
        return _err(
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
        return _err(
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
    for payment_type in payment_types:
        try:
            result = await rate_resolver.resolve_rate(
                tnved_code=tnved_code,
                payment_type=payment_type,
                country_oksm=country_oksm,
                target_date=target_date,
                has_certificate=has_certificate,
                has_sp_certificate=has_sp_certificate,
                alta_client=alta_client,
                quote_item_id=quote_item_id,
            )
        except Exception as exc:
            # Resolver itself crashed (defensive — should not normally happen
            # since the resolver swallows AltaApiError internally). Treat as
            # ALTA_ERROR for outcome aggregation purposes.
            logger.warning(
                "resolve_rates: resolver crashed for payment_type=%s: %s",
                payment_type, exc,
            )
            outcomes_by_payment_type[payment_type] = "ALTA_ERROR"
            saw_alta_error = True
            continue

        outcomes_by_payment_type[payment_type] = result.outcome.name

        if result.outcome == rate_resolver.ResolveOutcome.ALTA_ERROR:
            saw_alta_error = True
            continue
        if result.outcome == rate_resolver.ResolveOutcome.NOT_FOUND:
            saw_not_found = True
            continue

        # FOUND
        r = result.rate
        resolved_rates.append(r)
        sources.add(r.source)
        # cache_hit = served from cache (anything not freshly fetched live).
        # The resolver populates Rate.source from the DB row's source column;
        # an Alta-live row served from the same call counts as a fetch (not
        # a hit), but we have no separate signal here, so approximate via
        # the rate's age relative to the request start.
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
            return _err(
                "ALTA_UNAVAILABLE",
                "Alta API недоступен. Попробуйте позже.",
                503,
            )
        # All requested payment_types resolved to NOT_FOUND — Alta succeeded
        # but has no data for this combination. No amount of retrying will
        # change that; the user must enter the rate manually.
        return _err(
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
    Roles: customs, admin, head_of_customs.
    """
    started = time.monotonic()

    user, role_codes = _resolve_dual_auth(request)
    if not user or not user.get("org_id"):
        return _err("UNAUTHORIZED", "Not authenticated", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return _err("FORBIDDEN", "Forbidden", 403)

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)
    if not isinstance(body, dict):
        return _err("BAD_REQUEST", "body must be a JSON object", 400)

    tnved_code = (body.get("tnved_code") or "").strip()
    if not tnved_code or not _TNVED_RE.match(tnved_code):
        return _err(
            "INVALID_TNVED_CODE",
            "tnved_code must be a 10-digit ТН ВЭД code (got %r)" % tnved_code,
            400,
        )

    country_oksm_raw = body.get("country_oksm")
    try:
        country_oksm = int(country_oksm_raw)
    except (TypeError, ValueError):
        return _err(
            "BAD_REQUEST",
            "country_oksm must be an integer (got %r)" % country_oksm_raw,
            400,
        )

    mode = body.get("mode", "import")
    if mode not in ("import", "export"):
        return _err(
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
        return _err(
            "ALTA_UNAVAILABLE",
            "Alta API недоступен, попробуйте позже.",
            503,
        )
    except Exception as exc:
        logger.warning(
            "non_tariff_measures: Alta call failed for tnved_code=%s: %s",
            tnved_code, exc,
        )
        return _err(
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
        return _err("UNAUTHORIZED", "Authentication required", 401)
    if not (set(role_codes) & _CUSTOMS_ROLES):
        return _err(
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
        return _err("NOT_FOUND", f"quote {quote_id} not found", 404)
    except Exception as exc:
        # JSON decode failures, connection errors, anything we did not expect.
        logger.error(
            "refresh_customs_snapshot: quote lookup failed for %s: %s",
            quote_id, exc,
        )
        return _err(
            "DB_ERROR",
            "Quote lookup failed; please retry",
            500,
        )

    quote = getattr(quote_resp, "data", None)
    if not quote:
        return _err("NOT_FOUND", f"quote {quote_id} not found", 404)

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
        return _err(
            "NO_VERSION",
            f"No quote_versions row exists for quote {quote_id} — calculate first",
            409,
        )

    latest = (latest_resp.data or [None])[0]
    if latest is None:
        return _err(
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
        return _err(
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
