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
        Each quote row:
          - id (str)
          - idn_quote (str)
          - customer_name (str | None)
          - procurement_substatus (str)
          - days_in_state (int)
          - assignees (list[str]) — raw user UUIDs from quotes.assigned_procurement_users
          - latest_reason (str | None)
          - brands (list[str]) — distinct sorted quote_items.brand values
          - manager_name (str | None) — МОП full name (resolved via quotes.created_by)
          - procurement_user_names (list[str]) — МОЗ full names (resolved from assignees)
          - invoice_sums (list[dict]) — per-supplier-invoice totals:
              [{"invoice_number": str, "currency": str, "total": float}, ...]
    Side Effects: none (read-only)
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
            "id, idn_quote, procurement_substatus, updated_at, assigned_procurement_users, "
            "created_by, customers!customer_id(name)"
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

    # Batch-fetch quote_items: brands + per-item (id, quantity) for invoice totals.
    brands_by_quote: dict[str, set[str]] = {}
    item_qty_by_id: dict[str, float] = {}
    item_quote_by_id: dict[str, str] = {}
    if quote_ids:
        items_result = (
            sb.table("quote_items")
            .select("id, quote_id, brand, quantity")
            .in_("quote_id", quote_ids)
            .execute()
        )
        for it in _rows(items_result):
            qid = str(it.get("quote_id"))
            brand = it.get("brand")
            if brand:
                brands_by_quote.setdefault(qid, set()).add(str(brand))
            item_id = it.get("id")
            if item_id:
                item_qty_by_id[str(item_id)] = float(it.get("quantity") or 0)
                item_quote_by_id[str(item_id)] = qid

    # Batch-fetch supplier invoices for these quotes.
    invoices_by_quote: dict[str, list[dict]] = {}
    invoice_quote_by_id: dict[str, str] = {}
    invoice_meta_by_id: dict[str, dict] = {}
    if quote_ids:
        invoices_result = (
            sb.table("invoices")
            .select("id, quote_id, invoice_number, currency")
            .in_("quote_id", quote_ids)
            .execute()
        )
        for inv in _rows(invoices_result):
            inv_id = str(inv.get("id"))
            qid = str(inv.get("quote_id"))
            invoice_quote_by_id[inv_id] = qid
            invoice_meta_by_id[inv_id] = {
                "invoice_number": inv.get("invoice_number") or "",
                "currency": inv.get("currency") or "",
            }
            invoices_by_quote.setdefault(qid, []).append(inv)

    # Batch-fetch invoice_item_prices for these invoices and accumulate totals.
    # Total = SUM(purchase_price_original × quote_items.quantity) per invoice.
    # Currency falls back to invoice_item_prices.purchase_currency if invoice has none.
    invoice_totals: dict[str, float] = {}
    invoice_currency_from_prices: dict[str, str] = {}
    invoice_ids = list(invoice_quote_by_id.keys())
    if invoice_ids:
        prices_result = (
            sb.table("invoice_item_prices")
            .select("invoice_id, quote_item_id, purchase_price_original, purchase_currency")
            .in_("invoice_id", invoice_ids)
            .execute()
        )
        for p in _rows(prices_result):
            inv_id = str(p.get("invoice_id"))
            item_id = str(p.get("quote_item_id"))
            qty = item_qty_by_id.get(item_id, 0.0)
            try:
                price = float(p.get("purchase_price_original") or 0)
            except (TypeError, ValueError):
                price = 0.0
            invoice_totals[inv_id] = invoice_totals.get(inv_id, 0.0) + price * qty
            # Capture first non-empty purchase_currency seen per invoice (fallback only).
            cur = p.get("purchase_currency")
            if cur and inv_id not in invoice_currency_from_prices:
                invoice_currency_from_prices[inv_id] = str(cur)

    # Build invoice_sums list per quote — one entry per invoice that has priced items.
    invoice_sums_by_quote: dict[str, list[dict]] = {}
    for inv_id, total in invoice_totals.items():
        qid = invoice_quote_by_id.get(inv_id)
        if not qid:
            continue
        meta = invoice_meta_by_id.get(inv_id, {})
        currency = meta.get("currency") or invoice_currency_from_prices.get(inv_id, "")
        invoice_sums_by_quote.setdefault(qid, []).append({
            "invoice_number": meta.get("invoice_number", ""),
            "currency": currency,
            "total": round(total, 2),
        })

    # Batch-resolve user names for МОП (created_by) + МОЗ (assigned_procurement_users).
    user_ids_to_resolve: set[str] = set()
    for q in quote_rows:
        creator = q.get("created_by")
        if creator:
            user_ids_to_resolve.add(str(creator))
        for uid in q.get("assigned_procurement_users") or []:
            if uid:
                user_ids_to_resolve.add(str(uid))

    name_by_user: dict[str, str] = {}
    if user_ids_to_resolve:
        profiles_result = (
            sb.table("user_profiles")
            .select("user_id, full_name")
            .in_("user_id", list(user_ids_to_resolve))
            .execute()
        )
        for p in _rows(profiles_result):
            uid = str(p.get("user_id"))
            name_by_user[uid] = p.get("full_name") or ""

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

        assignees_raw = q.get("assigned_procurement_users") or []
        if not isinstance(assignees_raw, list):
            assignees_raw = []
        assignees = [str(a) for a in assignees_raw if a]

        creator_id = str(q.get("created_by")) if q.get("created_by") else None
        manager_name = name_by_user.get(creator_id) if creator_id else None
        if manager_name == "":
            manager_name = None

        procurement_user_names = [
            name_by_user[uid] for uid in assignees if name_by_user.get(uid)
        ]

        brands = sorted(brands_by_quote.get(qid, set()))

        invoice_sums = invoice_sums_by_quote.get(qid, [])

        columns[substatus].append({
            "id": qid,
            "idn_quote": q.get("idn_quote"),
            "customer_name": customer_name,
            "procurement_substatus": substatus,
            "days_in_state": days,
            "assignees": assignees,
            "latest_reason": latest_reason,
            "brands": brands,
            "manager_name": manager_name,
            "procurement_user_names": procurement_user_names,
            "invoice_sums": invoice_sums,
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
