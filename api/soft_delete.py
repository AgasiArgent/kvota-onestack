"""
Soft-delete / restore API endpoints for quotes (and their specs/deals via cascade).

POST /api/quotes/{quote_id}/soft-delete — admin-only soft delete
POST /api/quotes/{quote_id}/restore     — admin-only restore

Both endpoints call PL/pgSQL functions provided by migration 279:
  kvota.soft_delete_quote(p_quote_id uuid, p_actor_id uuid)
    RETURNS TABLE(quote_affected int, spec_affected int, deal_affected int)
  kvota.restore_quote(p_quote_id uuid)
    RETURNS TABLE(quote_affected int, spec_affected int, deal_affected int)

The RPC is invoked via the SERVICE_ROLE client (`get_supabase()`), so
`auth.uid()` inside the function is NULL and the anti-spoof guard's
"IF auth.uid() IS NOT NULL AND p_actor_id IS DISTINCT FROM auth.uid()"
branch does not trigger. We still pass the authenticated user's id as
`p_actor_id` so the `deleted_by` column records the real actor.

Auth: JWT via ApiAuthMiddleware (request.state.api_user).
Roles: admin ONLY — soft-delete is intentionally an administrative
       operation with cross-org impact (quote → spec → deal cascade).
"""

import logging
from typing import Any

from starlette.responses import JSONResponse

from services.database import get_supabase

logger = logging.getLogger(__name__)

# Only admins can soft-delete / restore. Spec REQ-004 is explicit: NOT
# sales, head_of_sales, top_manager, or procurement — admin only.
_ADMIN_ONLY: set[str] = {"admin"}


def _rows(response: Any) -> list[dict[str, Any]]:
    """Extract typed rows from a Supabase response."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _resolve_admin_user(request) -> tuple[dict | None, JSONResponse | None]:
    """Authenticate via JWT and require role slug == 'admin'.

    Returns (user_dict, None) on success or (None, error_response).
    user_dict keys: id, org_id.
    """
    api_user = getattr(request.state, "api_user", None)
    if not api_user:
        return None, JSONResponse(
            {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication required"}},
            status_code=401,
        )

    user_id = str(api_user.id)
    sb = get_supabase()

    om_result = (
        sb.table("organization_members")
        .select("organization_id")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    om_rows = _rows(om_result)
    if not om_rows:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "User has no active organization"}},
            status_code=403,
        )
    org_id = str(om_rows[0].get("organization_id", ""))

    roles_result = (
        sb.table("user_roles")
        .select("roles!inner(slug)")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .execute()
    )
    role_slugs: set[str] = set()
    for row in _rows(roles_result):
        role_data = row.get("roles")
        if isinstance(role_data, dict) and role_data.get("slug"):
            role_slugs.add(str(role_data["slug"]))

    if not role_slugs & _ADMIN_ONLY:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Admin role required"}},
            status_code=403,
        )

    return {"id": user_id, "org_id": org_id}, None


def _quote_exists(sb, quote_id: str) -> bool:
    """Check whether a quote row exists at all (regardless of deleted_at).

    Used to disambiguate the rpc's (0,0,0) result: zero counts mean either
    "quote does not exist" (→ 404) or "already in target state" (→ 200
    with zero counts, idempotent).
    """
    try:
        result = (
            sb.table("quotes")
            .select("id")
            .eq("id", quote_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        # Malformed UUID etc. — treat as not-found for the caller.
        logger.warning("quote lookup failed for %s: %s", quote_id, e)
        return False
    return bool(_rows(result))


def _extract_counts(rpc_response: Any) -> dict[str, int]:
    """Normalize the rpc payload into {quote_affected, spec_affected, deal_affected}.

    Supabase returns a list of rows for TABLE-returning functions; each row
    has the three integer columns. Missing/odd shapes default to zero so
    the endpoint always returns the contract shape.
    """
    data = getattr(rpc_response, "data", None)
    row: dict[str, Any] = {}
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            row = first
    elif isinstance(data, dict):
        row = data

    def _int(key: str) -> int:
        try:
            return int(row.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    return {
        "quote_affected": _int("quote_affected"),
        "spec_affected": _int("spec_affected"),
        "deal_affected": _int("deal_affected"),
    }


async def soft_delete_quote(request, quote_id: str) -> JSONResponse:
    """Soft-delete a quote and cascade to its specification and deal.

    Path: POST /api/quotes/{quote_id}/soft-delete
    Params:
        quote_id: str (path, required) — UUID of quote to soft-delete
    Returns:
        success: true
        data:
            quote_affected: int — 1 if quote was newly soft-deleted, 0 if already deleted
            spec_affected:  int — number of specifications cascaded (0 or 1)
            deal_affected:  int — number of deals cascaded (0 or 1)
    Side Effects:
        - Sets deleted_at = now(), deleted_by = <actor> on kvota.quotes
        - Cascades to linked kvota.specifications and kvota.deals rows
        - Idempotent: re-calling on an already-deleted quote returns zero counts, not an error
    Roles: admin
    Errors:
        401 UNAUTHORIZED — no JWT / session
        403 FORBIDDEN    — authenticated user is not an admin
        404 NOT_FOUND    — quote with this UUID does not exist
        500 INTERNAL_ERROR — database error during rpc call
    """
    user, err = _resolve_admin_user(request)
    if err:
        return err
    assert user is not None

    sb = get_supabase()

    # Disambiguate "not found" vs "already soft-deleted" — both make the
    # rpc return (0,0,0), but the HTTP contract is different.
    if not _quote_exists(sb, quote_id):
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )

    try:
        rpc_resp = sb.rpc(
            "soft_delete_quote",
            {"p_quote_id": quote_id, "p_actor_id": user["id"]},
        ).execute()
    except Exception:
        # Full traceback is captured in logs via logger.exception — the client
        # gets a generic message to avoid leaking DB / driver internals
        # (per .claude/rules/common/error-handling.md).
        logger.exception("soft_delete_quote rpc failed for quote %s", quote_id)
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Soft-delete failed. Please try again later.",
                },
            },
            status_code=500,
        )

    counts = _extract_counts(rpc_resp)
    return JSONResponse({"success": True, "data": counts}, status_code=200)


async def restore_quote(request, quote_id: str) -> JSONResponse:
    """Restore a soft-deleted quote (and cascade to spec/deal).

    Path: POST /api/quotes/{quote_id}/restore
    Params:
        quote_id: str (path, required) — UUID of quote to restore
    Returns:
        success: true
        data:
            quote_affected: int — 1 if quote was newly restored, 0 if already live
            spec_affected:  int — number of specifications restored (0 or 1)
            deal_affected:  int — number of deals restored (0 or 1)
    Side Effects:
        - Sets deleted_at = NULL, deleted_by = NULL on kvota.quotes
        - Cascades the same reset to linked specifications and deals
        - Idempotent: re-calling on a never-deleted quote returns zero counts, not an error
    Roles: admin
    Errors:
        401 UNAUTHORIZED — no JWT / session
        403 FORBIDDEN    — authenticated user is not an admin
        404 NOT_FOUND    — quote with this UUID does not exist
        500 INTERNAL_ERROR — database error during rpc call
    """
    user, err = _resolve_admin_user(request)
    if err:
        return err
    assert user is not None

    sb = get_supabase()

    if not _quote_exists(sb, quote_id):
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )

    try:
        rpc_resp = sb.rpc(
            "restore_quote",
            {"p_quote_id": quote_id},
        ).execute()
    except Exception:
        logger.exception("restore_quote rpc failed for quote %s", quote_id)
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Restore failed. Please try again later.",
                },
            },
            status_code=500,
        )

    counts = _extract_counts(rpc_resp)
    return JSONResponse({"success": True, "data": counts}, status_code=200)
