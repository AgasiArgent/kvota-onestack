"""
Procurement sub-status state machine API endpoints for Next.js frontend and AI agents.

GET    /api/quotes/kanban                      — (Quote, brand) cards grouped by substatus
POST   /api/quotes/{id}/substatus              — Transition a (quote, brand)'s sub-status
GET    /api/quotes/{id}/status-history         — Full audit log for a quote

Unit of work on the kanban is (quote_id, brand) — a quote with N distinct
brands flows through the procurement pipeline as N independent cards.

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

# Fixed set of procurement sub-statuses — matches migration 274 check constraint
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
    """Return (quote, brand) cards grouped by procurement_substatus for Kanban board.

    Path: GET /api/quotes/kanban
    Params:
        status: str (required) — Currently only 'pending_procurement' is supported.
    Returns:
        {
          "status": "pending_procurement",
          "columns": { <substatus>: [card_row, ...] }
        }
        Each card row is keyed by (quote_id, brand). A quote with 2 distinct
        brands produces 2 cards.
          - quote_id (str)
          - brand (str) — '' for unbranded items
          - idn_quote (str)
          - customer_name (str | None)
          - procurement_substatus (str)
          - days_in_state (int)
          - manager_name (str | None) — МОП (quotes.created_by → full_name)
          - procurement_user_names (list[str]) — МОЗ (distinct item.assigned_procurement_user for this brand → full_name)
          - invoice_sums (list[dict]) — per-supplier-invoice totals restricted to this brand:
              [{"invoice_number": str, "currency": str, "total": float}, ...]
          - latest_reason (str | None)
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

    # Pull (quote, brand) rows joined with their parent quote + customer.
    qbs_result = (
        sb.table("quote_brand_substates")
        .select(
            "quote_id, brand, substatus, updated_at, "
            "quotes!inner(id, idn_quote, workflow_status, organization_id, created_by, "
            "customers!customer_id(name))"
        )
        .eq("quotes.workflow_status", "pending_procurement")
        .eq("quotes.organization_id", user["org_id"])
        # Exclude soft-deleted quotes — their quote_brand_substates rows
        # survive via CASCADE only on HARD delete; soft delete (deleted_at
        # IS NOT NULL) leaves orphans that would otherwise show on kanban.
        .is_("quotes.deleted_at", "null")
        .execute()
    )
    qbs_rows = _rows(qbs_result)

    quote_ids = list({str(r["quote_id"]) for r in qbs_rows if r.get("quote_id")})

    # Batch-fetch status_history: latest row per (quote_id, brand, to_substatus=current).
    history_by_key: dict[tuple[str, str], list[dict]] = {}
    if quote_ids:
        history_result = (
            sb.table("status_history")
            .select("quote_id, brand, to_substatus, transitioned_at, reason")
            .in_("quote_id", quote_ids)
            .order("transitioned_at", desc=True)
            .execute()
        )
        for row in _rows(history_result):
            qid = str(row.get("quote_id"))
            brand = row.get("brand") or ""
            history_by_key.setdefault((qid, brand), []).append(row)

    # Batch-fetch items: group by (quote_id, brand) for МОЗ + invoice_sums scoping.
    items_by_key: dict[tuple[str, str], list[dict]] = {}
    item_qty_by_id: dict[str, float] = {}
    item_key_by_id: dict[str, tuple[str, str]] = {}  # item_id -> (quote_id, brand)
    if quote_ids:
        items_result = (
            sb.table("quote_items")
            .select("id, quote_id, brand, quantity, assigned_procurement_user")
            .in_("quote_id", quote_ids)
            .execute()
        )
        for it in _rows(items_result):
            qid = str(it.get("quote_id"))
            brand = it.get("brand") or ""
            key = (qid, brand)
            items_by_key.setdefault(key, []).append(it)
            item_id = it.get("id")
            if item_id:
                item_qty_by_id[str(item_id)] = float(it.get("quantity") or 0)
                item_key_by_id[str(item_id)] = key

    # Batch-fetch supplier invoices for these quotes.
    invoice_meta_by_id: dict[str, dict] = {}  # inv_id -> {invoice_number, currency, quote_id}
    if quote_ids:
        invoices_result = (
            sb.table("invoices")
            .select("id, quote_id, invoice_number, currency")
            .in_("quote_id", quote_ids)
            .execute()
        )
        for inv in _rows(invoices_result):
            inv_id = str(inv.get("id"))
            invoice_meta_by_id[inv_id] = {
                "invoice_number": inv.get("invoice_number") or "",
                "currency": inv.get("currency") or "",
                "quote_id": str(inv.get("quote_id") or ""),
            }

    # Batch-fetch invoice_item_prices. Per (invoice, item) line: price × item qty.
    # Accumulate per (quote_id, brand, invoice_id) because each line's brand is
    # derived from the item's brand.
    sums_by_card_inv: dict[tuple[str, str, str], float] = {}
    currency_fallback_by_inv: dict[str, str] = {}
    invoice_ids = list(invoice_meta_by_id.keys())
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
            key = item_key_by_id.get(item_id)
            if not key:
                continue
            qid, brand = key
            card_inv_key = (qid, brand, inv_id)
            sums_by_card_inv[card_inv_key] = sums_by_card_inv.get(card_inv_key, 0.0) + price * qty
            cur = p.get("purchase_currency")
            if cur and inv_id not in currency_fallback_by_inv:
                currency_fallback_by_inv[inv_id] = str(cur)

    # Build invoice_sums list per (quote, brand) — one entry per invoice with priced items in this brand.
    invoice_sums_by_key: dict[tuple[str, str], list[dict]] = {}
    for (qid, brand, inv_id), total in sums_by_card_inv.items():
        if total == 0:
            continue
        meta = invoice_meta_by_id.get(inv_id, {})
        currency = meta.get("currency") or currency_fallback_by_inv.get(inv_id, "")
        invoice_sums_by_key.setdefault((qid, brand), []).append({
            "invoice_number": meta.get("invoice_number", ""),
            "currency": currency,
            "total": round(total, 2),
        })

    # Batch-resolve user names: МОП (quotes.created_by) + МОЗ (items.assigned_procurement_user).
    user_ids_to_resolve: set[str] = set()
    for r in qbs_rows:
        parent = r.get("quotes") or {}
        if isinstance(parent, dict):
            creator = parent.get("created_by")
            if creator:
                user_ids_to_resolve.add(str(creator))
    for items in items_by_key.values():
        for it in items:
            uid = it.get("assigned_procurement_user")
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

    for r in qbs_rows:
        qid = str(r.get("quote_id"))
        brand = r.get("brand") or ""
        substatus = r.get("substatus") or "distributing"
        if substatus not in columns:
            continue

        parent = r.get("quotes") or {}
        if not isinstance(parent, dict):
            continue

        # days_in_state + latest_reason: first history row matching this (quote, brand, current substatus).
        days = 0
        latest_reason = None
        history_rows = history_by_key.get((qid, brand), [])
        matched = next(
            (h for h in history_rows if h.get("to_substatus") == substatus),
            None,
        )
        if matched:
            days = _days_since(matched.get("transitioned_at"))
            latest_reason = matched.get("reason") or None
        else:
            days = _days_since(r.get("updated_at"))

        customer_data = parent.get("customers") or {}
        customer_name = customer_data.get("name") if isinstance(customer_data, dict) else None

        creator_id = str(parent.get("created_by")) if parent.get("created_by") else None
        manager_name = name_by_user.get(creator_id) if creator_id else None
        if not manager_name:
            manager_name = None

        # МОЗ: distinct assigned_procurement_user UUIDs among items for this (quote, brand).
        moz_ids: set[str] = set()
        for it in items_by_key.get((qid, brand), []):
            uid = it.get("assigned_procurement_user")
            if uid:
                moz_ids.add(str(uid))
        procurement_user_names = sorted(
            (name_by_user[uid] for uid in moz_ids if name_by_user.get(uid))
        )

        invoice_sums = invoice_sums_by_key.get((qid, brand), [])

        columns[substatus].append({
            "quote_id": qid,
            "brand": brand,
            "idn_quote": parent.get("idn_quote"),
            "customer_name": customer_name,
            "procurement_substatus": substatus,
            "days_in_state": days,
            "manager_name": manager_name,
            "procurement_user_names": procurement_user_names,
            "invoice_sums": invoice_sums,
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
    """Transition a (quote, brand)'s procurement sub-status.

    Path: POST /api/quotes/{id}/substatus
    Params (JSON body):
        brand: str (required) — brand of the card. Use "" for unbranded.
        to_substatus: str (required) — target sub-status
        reason: str (optional) — required for backward transitions
    Returns:
        { "quote_id": ..., "brand": ..., "procurement_substatus": <new_substatus> }
    Side Effects:
        - Writes status_history audit row (brand populated)
        - Updates quote_brand_substates.substatus + updated_at + updated_by
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
    # brand is required but may be "" (unbranded) — distinguish absence from empty.
    if "brand" not in body:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "brand is required"}},
            status_code=400,
        )
    brand = body.get("brand")
    if not isinstance(brand, str):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "brand must be a string"}},
            status_code=400,
        )

    if not to_substatus:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "to_substatus is required"}},
            status_code=400,
        )

    try:
        updated = transition_substatus(
            quote_id=id,
            brand=brand,
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
                "quote_id": str(updated.get("quote_id", id)),
                "brand": updated.get("brand", brand),
                "procurement_substatus": updated.get("substatus", to_substatus),
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
        id, brand, from_status, from_substatus, to_status, to_substatus,
        transitioned_at, transitioned_by, transitioned_by_name, reason.
        `brand` is null for quote-level transitions, non-null for per-brand ones.
    Roles: procurement, admin, head_of_procurement, sales, head_of_sales
    """
    _, err = _resolve_user_context(request, _READ_HISTORY_ROLES)
    if err:
        return err

    sb = get_supabase()

    history_result = (
        sb.table("status_history")
        .select("id, brand, from_status, from_substatus, to_status, to_substatus, "
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
            "brand": r.get("brand"),  # None for quote-level rows, str for per-brand rows
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
