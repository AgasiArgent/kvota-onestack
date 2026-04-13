"""
Procurement sub-status state machine API endpoints for Next.js frontend and AI agents.

GET    /api/quotes/kanban                      — Quotes grouped by procurement_substatus
POST   /api/quotes/{id}/substatus                — Transition a quote's sub-status
GET    /api/quotes/{id}/status-history           — Full audit log for a quote

Auth: JWT via ApiAuthMiddleware (request.state.api_user).
Roles: procurement, admin, head_of_procurement (sales can read status-history).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from starlette.responses import JSONResponse

from services.database import get_supabase
from services.workflow_service import transition_substatus

logger = logging.getLogger(__name__)

_PROCUREMENT_ROLES = {"procurement", "admin", "head_of_procurement"}
_READ_HISTORY_ROLES = {"procurement", "admin", "head_of_procurement", "sales", "head_of_sales"}

# Fixed set of procurement sub-statuses — matches migration 272 check constraint
_PROCUREMENT_SUBSTATUSES = ("distributing", "searching_supplier", "waiting_prices", "prices_ready")


def _rows(response: Any) -> list[dict[str, Any]]:
    """Extract typed rows from Supabase response."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _resolve_user_context(request, allowed_roles: set[str]) -> tuple[dict | None, JSONResponse | None]:
    """Authenticate via JWT and authorize against `allowed_roles`.

    Returns (user_dict, None) on success or (None, error_response).
    user_dict contains: id, org_id, role_slugs.
    """
    api_user = getattr(request.state, "api_user", None)
    if not api_user:
        return None, JSONResponse(
            {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication required"}},
            status_code=401,
        )

    user_id = str(api_user.id)
    sb = get_supabase()

    om = (
        sb.table("organization_members")
        .select("organization_id")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    om_rows = _rows(om)
    if not om_rows:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "User has no active organization"}},
            status_code=403,
        )

    org_id: str = str(om_rows[0].get("organization_id", ""))

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

    if not role_slugs & allowed_roles:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Insufficient permissions"}},
            status_code=403,
        )

    return {"id": user_id, "org_id": org_id, "role_slugs": role_slugs}, None


def _days_since(iso_timestamp: str | None) -> int:
    """Compute integer days between `iso_timestamp` and now (UTC). Returns 0 if parsing fails."""
    if not iso_timestamp:
        return 0
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(delta.days, 0)
    except Exception:
        return 0


# ============================================================================
# GET /api/quotes/kanban
# ============================================================================


async def get_kanban(request) -> JSONResponse:
    """Return quotes grouped by procurement_substatus for Kanban board.

    Path: GET /api/quotes/kanban
    Params:
        status: str (required) — Currently only 'pending_procurement' is supported.
    Returns:
        {
          "status": "pending_procurement",
          "columns": { <substatus>: [quote_row, ...] }
        }
        Each quote row: id, idn, customer_name, procurement_substatus,
        days_in_state, assignees, latest_reason.
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _resolve_user_context(request, _PROCUREMENT_ROLES)
    if err:
        return err
    assert user is not None  # narrowed by err check above

    status = request.query_params.get("status", "").strip()
    if status != "pending_procurement":
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "INVALID_STATUS",
                    "message": "Only 'pending_procurement' status is supported for Kanban",
                },
            },
            status_code=400,
        )

    sb = get_supabase()

    quotes_result = (
        sb.table("quotes")
        .select(
            "id, idn, procurement_substatus, updated_at, assigned_procurement_users, "
            "customers!customer_id(name)"
        )
        .eq("workflow_status", "pending_procurement")
        .eq("organization_id", user["org_id"])
        .execute()
    )
    quote_rows = _rows(quotes_result)
    quote_ids = [str(q["id"]) for q in quote_rows if q.get("id")]

    # Batch-fetch latest status_history row per quote (single query, no N+1).
    latest_by_quote: dict[str, dict] = {}
    if quote_ids:
        history_result = (
            sb.table("status_history")
            .select("quote_id, to_substatus, transitioned_at, reason")
            .in_("quote_id", quote_ids)
            .order("transitioned_at", desc=True)
            .execute()
        )
        for row in _rows(history_result):
            qid = str(row.get("quote_id"))
            if qid not in latest_by_quote:
                latest_by_quote[qid] = row

    columns: dict[str, list[dict]] = {s: [] for s in _PROCUREMENT_SUBSTATUSES}

    for q in quote_rows:
        qid = str(q.get("id"))
        substatus = q.get("procurement_substatus") or "distributing"
        if substatus not in columns:
            continue

        latest = latest_by_quote.get(qid)
        if latest and latest.get("to_substatus") == substatus:
            days = _days_since(latest.get("transitioned_at"))
            latest_reason = latest.get("reason") or None
        else:
            days = _days_since(q.get("updated_at"))
            latest_reason = None

        customer_data = q.get("customers") or {}
        customer_name = customer_data.get("name") if isinstance(customer_data, dict) else None

        assignees = q.get("assigned_procurement_users") or []
        if not isinstance(assignees, list):
            assignees = []

        columns[substatus].append({
            "id": qid,
            "idn": q.get("idn"),
            "customer_name": customer_name,
            "procurement_substatus": substatus,
            "days_in_state": days,
            "assignees": [str(a) for a in assignees],
            "latest_reason": latest_reason,
        })

    return JSONResponse(
        {"success": True, "data": {"status": status, "columns": columns}},
        status_code=200,
    )


# ============================================================================
# POST /api/quotes/{id}/substatus
# ============================================================================


async def post_substatus(request, id: str) -> JSONResponse:
    """Transition a quote's procurement sub-status.

    Path: POST /api/quotes/{id}/substatus
    Params (JSON body):
        to_substatus: str (required) — target sub-status
        reason: str (optional) — required for backward transitions
    Returns:
        { "id": quote_id, "procurement_substatus": <new_substatus> }
    Side Effects:
        - Writes status_history audit row
        - Updates quotes.procurement_substatus
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _resolve_user_context(request, _PROCUREMENT_ROLES)
    if err:
        return err
    assert user is not None  # narrowed by err check above

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    to_substatus = (body.get("to_substatus") or "").strip()
    reason = (body.get("reason") or "").strip()

    if not to_substatus:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "to_substatus is required"}},
            status_code=400,
        )

    try:
        updated = transition_substatus(
            quote_id=id,
            to_substatus=to_substatus,
            user_id=user["id"],
            user_roles=list(user["role_slugs"]),
            reason=reason,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            return JSONResponse(
                {"success": False, "error": {"code": "QUOTE_NOT_FOUND", "message": msg}},
                status_code=404,
            )
        if msg.lower().startswith("reason required"):
            return JSONResponse(
                {"success": False, "error": {"code": "REASON_REQUIRED", "message": msg}},
                status_code=400,
            )
        if "invalid substatus transition" in msg.lower():
            return JSONResponse(
                {"success": False, "error": {"code": "INVALID_TRANSITION", "message": msg}},
                status_code=400,
            )
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": msg}},
            status_code=400,
        )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "id": str(updated.get("id", id)),
                "procurement_substatus": updated.get("procurement_substatus", to_substatus),
            },
        },
        status_code=200,
    )


# ============================================================================
# GET /api/quotes/{id}/status-history
# ============================================================================


async def get_status_history(request, id: str) -> JSONResponse:
    """Return full audit log of status/substatus transitions for a quote.

    Path: GET /api/quotes/{id}/status-history
    Returns:
        List of history rows ordered by transitioned_at DESC. Each row:
        id, from_status, from_substatus, to_status, to_substatus,
        transitioned_at, transitioned_by, transitioned_by_name, reason.
    Roles: procurement, admin, head_of_procurement, sales, head_of_sales
    """
    _, err = _resolve_user_context(request, _READ_HISTORY_ROLES)
    if err:
        return err

    sb = get_supabase()

    history_result = (
        sb.table("status_history")
        .select("id, from_status, from_substatus, to_status, to_substatus, "
                "transitioned_at, transitioned_by, reason")
        .eq("quote_id", id)
        .order("transitioned_at", desc=True)
        .execute()
    )
    rows = _rows(history_result)

    # Batch-fetch actor names from user_profiles (avoids N+1).
    user_ids = {str(r.get("transitioned_by")) for r in rows if r.get("transitioned_by")}
    names_by_id: dict[str, str] = {}
    if user_ids:
        profiles_result = (
            sb.table("user_profiles")
            .select("user_id, full_name")
            .in_("user_id", list(user_ids))
            .execute()
        )
        for p in _rows(profiles_result):
            uid = str(p.get("user_id"))
            names_by_id[uid] = p.get("full_name") or ""

    enriched = []
    for r in rows:
        actor_id = str(r.get("transitioned_by")) if r.get("transitioned_by") else None
        enriched.append({
            "id": str(r.get("id")),
            "from_status": r.get("from_status"),
            "from_substatus": r.get("from_substatus"),
            "to_status": r.get("to_status"),
            "to_substatus": r.get("to_substatus"),
            "transitioned_at": r.get("transitioned_at"),
            "transitioned_by": actor_id,
            "transitioned_by_name": names_by_id.get(actor_id or "", ""),
            "reason": r.get("reason") or "",
        })

    return JSONResponse({"success": True, "data": enriched}, status_code=200)
