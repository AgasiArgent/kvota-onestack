"""Customs /api/customs/* endpoints — bulk item update + autofill + expenses.

Handler module (not router). Registered via thin wrapper in
api/routers/customs.py. Originally moved from main.py in Phase 6B-9; the
autofill + expense handlers below were added in Wave 1 of the
logistics-customs-redesign spec (Tasks 3 + 9).

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.
Roles: customs, admin, head_of_customs.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

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

# Fields propagated by the autofill endpoint from historical quote_items.
# Kept narrow: hs_code + numeric duties + license flags/costs + honest mark.
_AUTOFILL_FIELDS = (
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


async def autofill_handler(request: Request) -> JSONResponse:
    """POST /api/customs/autofill — suggest customs fields from history.

    Path: POST /api/customs/autofill
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        items: list of objects — { id, brand, product_code }.
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
        }
    Side Effects: none (read-only).
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

    # Build unique (brand, product_code) keys; remember which item_ids map to each key.
    keys_by_pair: dict[tuple[str, str], list[str]] = {}
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        brand = (entry.get("brand") or "").strip()
        product_code = (entry.get("product_code") or "").strip()
        if not item_id or not brand or not product_code:
            continue
        keys_by_pair.setdefault((brand, product_code), []).append(item_id)

    if not keys_by_pair:
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

    return JSONResponse({"success": True, "data": {"suggestions": suggestions}})


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
