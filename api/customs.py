"""Customs /api/customs/* endpoints — bulk item update.

Handler module (not router). Registered via thin wrapper in
api/routers/customs.py. Moved verbatim from main.py
@rt("/api/customs/{quote_id}/items/bulk") in Phase 6B-9.

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
