"""
Procurement sub-status state machine API endpoints for Next.js frontend and AI agents.

GET    /api/quotes/kanban                      — (Quote, brand) cards grouped by substatus
POST   /api/quotes/{id}/substatus              — Transition a (quote, brand)'s sub-status
POST   /api/quotes/{id}/pause                  — Pause a (quote, brand) with mandatory reason
POST   /api/quotes/{id}/unpause                — Unpause a (quote, brand), closing the open pause row
GET    /api/quotes/{id}/pause-history          — Full pause activity log (Testing 2 row 74)
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
from services.workflow_service import (
    get_pause_history,
    pause_quote,
    transition_substatus,
    unpause_quote,
)

logger = logging.getLogger(__name__)

_PROCUREMENT_ROLES = {"procurement", "procurement_senior", "admin", "head_of_procurement"}
_READ_HISTORY_ROLES = {"procurement", "procurement_senior", "admin", "head_of_procurement", "sales", "head_of_sales"}

# Roles that grant org-wide kanban visibility. Regular `procurement` (МОЗ) is
# excluded — they only see brand-slices where they personally own at least one
# item AND the slice has moved past distribution. Distribution is a senior task;
# regular МОЗ has no business with the «Распределение» column.
_BROADER_SCOPE_ROLES = {"admin", "head_of_procurement", "procurement_senior"}

# Fixed set of procurement sub-statuses — matches migrations 274 + 326 check constraint
_PROCUREMENT_SUBSTATUSES = (
    "distributing",
    "searching_supplier",
    "waiting_prices",
    "prices_ready",
    "paused",
)


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
          - procurement_completed_at (str | None) — quote-level completion
              timestamp (Testing 2 row 83). Non-null cards represent slices
              whose workflow already moved past procurement but should remain
              visible to procurement roles.
          - distribution_comment (str | None) — МОП hand-off note from
              `quotes.sales_checklist.distribution_comment` (Testing 2 row 67
              follow-up). Trimmed; null when empty / absent. Procurement card
              renders it inline so МОЗ doesn't have to open the quote.
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
    # `tender_type` (Testing 2 row 67) lets the kanban card flag tender quotes.
    # `customers.id` (Testing 2 row 66) lets the kanban filter bar group cards
    # by customer id rather than by name (names alone collide for chains with
    # identical labels).
    #
    # Visibility window (Testing 2 row 83): two overlapping cohorts surface on
    # the procurement kanban —
    #   (a) `workflow_status = 'pending_procurement'` — work in progress, and
    #   (b) `procurement_completed_at IS NOT NULL` — quotes that already
    #       finished procurement and advanced past `pending_procurement`.
    # Tester report: when the last invoice on a quote was completed the quote
    # vanished from /procurement for РОЗ / СтМОЗ / МОЗ alike, which made it
    # look like the data had been hidden. Procurement should still see those
    # slices (the rows remain in `quote_brand_substates` after the workflow
    # advances). The МОЗ scope filter further down keeps regular МОЗ to their
    # own brand-slices for both cohorts.
    qbs_result = (
        sb.table("quote_brand_substates")
        .select(
            "quote_id, brand, substatus, updated_at, "
            "quotes!inner(id, idn_quote, workflow_status, organization_id, created_by, tender_type, "
            "procurement_completed_at, sales_checklist, "
            "customers!customer_id(id, name))"
        )
        .or_(
            "workflow_status.eq.pending_procurement,procurement_completed_at.not.is.null",
            reference_table="quotes",
        )
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

    # Batch-fetch items: group by (quote_id, brand) for МОЗ resolution only.
    # Invoice totals are derived from invoice_items directly (Phase 5d).
    items_by_key: dict[tuple[str, str], list[dict]] = {}
    if quote_ids:
        items_result = (
            sb.table("quote_items")
            .select("quote_id, brand, assigned_procurement_user")
            .in_("quote_id", quote_ids)
            .execute()
        )
        for it in _rows(items_result):
            qid = str(it.get("quote_id"))
            brand = it.get("brand") or ""
            items_by_key.setdefault((qid, brand), []).append(it)

    # Per-user scope filter (МОЗ visibility).
    # Org-wide scope is reserved for admin / head_of_procurement /
    # procurement_senior. Regular `procurement` (МОЗ) only sees brand-slices
    # where they personally own at least one item AND the slice has progressed
    # past «Распределение» — distribution belongs to senior, and a stray
    # distributing card would expose the «Распределить» button to МОЗ
    # (which the assignBrandGroup server action rejects anyway, but the
    # button shouldn't appear in the first place).
    has_broader_scope = bool(user["role_slugs"] & _BROADER_SCOPE_ROLES)
    if not has_broader_scope:
        own_brand_keys: set[tuple[str, str]] = set()
        for (qid, brand), items in items_by_key.items():
            for it in items:
                if str(it.get("assigned_procurement_user") or "") == user["id"]:
                    own_brand_keys.add((qid, brand))
                    break
        qbs_rows = [
            r
            for r in qbs_rows
            if (
                (r.get("substatus") or "distributing") != "distributing"
                and (str(r.get("quote_id")), r.get("brand") or "") in own_brand_keys
            )
        ]
        # Recompute quote_ids set so downstream batch fetches don't waste work
        # on quotes the user can't see. Keeps invoice/history queries scoped.
        quote_ids = list({str(r["quote_id"]) for r in qbs_rows if r.get("quote_id")})

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

    # Batch-fetch invoice_items (Phase 5d Pattern B). Each row is a supplier's
    # own line with its own brand, quantity, and price — no indirection through
    # quote_items. Accumulate per (quote_id, brand, invoice_id); quote_id is
    # derived from the invoice, brand and per-row totals live on the row itself.
    sums_by_card_inv: dict[tuple[str, str, str], float] = {}
    currency_fallback_by_inv: dict[str, str] = {}
    invoice_ids = list(invoice_meta_by_id.keys())
    if invoice_ids:
        invoice_items_result = (
            sb.table("invoice_items")
            .select("invoice_id, brand, quantity, purchase_price_original, purchase_currency")
            .in_("invoice_id", invoice_ids)
            .execute()
        )
        for ii in _rows(invoice_items_result):
            inv_id = str(ii.get("invoice_id"))
            meta = invoice_meta_by_id.get(inv_id) or {}
            qid = meta.get("quote_id") or ""
            if not qid:
                continue
            brand = ii.get("brand") or ""
            try:
                price = float(ii.get("purchase_price_original") or 0)
            except (TypeError, ValueError):
                price = 0.0
            try:
                qty = float(ii.get("quantity") or 0)
            except (TypeError, ValueError):
                qty = 0.0
            card_inv_key = (qid, brand, inv_id)
            sums_by_card_inv[card_inv_key] = sums_by_card_inv.get(card_inv_key, 0.0) + price * qty
            cur = ii.get("purchase_currency")
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

    # Batch-fetch latest open pause log per quote (Testing 2 row 74). Used to
    # display the mandatory pause reason inline on «На паузе» cards plus the
    # actor + paused_at timestamp. We scope to quotes that have at least one
    # paused brand so the query stays small.
    paused_quote_ids = {
        str(r["quote_id"])
        for r in qbs_rows
        if (r.get("substatus") or "") == "paused" and r.get("quote_id")
    }
    pause_log_by_quote: dict[str, dict] = {}
    if paused_quote_ids:
        pause_rows_result = (
            sb.table("procurement_pause_log")
            .select("id, quote_id, paused_at, paused_by, reason")
            .in_("quote_id", list(paused_quote_ids))
            .is_("unpaused_at", "null")
            .order("paused_at", desc=True)
            .execute()
        )
        # Newest-first; for each quote, keep the first encountered (latest).
        for prow in _rows(pause_rows_result):
            qid_p = str(prow.get("quote_id"))
            if qid_p in pause_log_by_quote:
                continue
            pause_log_by_quote[qid_p] = prow

        # Enrich actor names from user_profiles — extend name_by_user
        # in-place so the same lookup powers МОП/МОЗ resolution below.
        new_actor_ids = {
            str(p.get("paused_by"))
            for p in pause_log_by_quote.values()
            if p.get("paused_by") and str(p.get("paused_by")) not in name_by_user
        }
        if new_actor_ids:
            extra_profiles = (
                sb.table("user_profiles")
                .select("user_id, full_name")
                .in_("user_id", list(new_actor_ids))
                .execute()
            )
            for p in _rows(extra_profiles):
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
        if isinstance(customer_data, dict):
            customer_name = customer_data.get("name")
            customer_id = (
                str(customer_data.get("id")) if customer_data.get("id") else None
            )
        else:
            customer_name = None
            customer_id = None

        creator_id = str(parent.get("created_by")) if parent.get("created_by") else None
        manager_name = name_by_user.get(creator_id) if creator_id else None
        if not manager_name:
            manager_name = None

        # МОЗ: distinct assigned_procurement_user UUIDs among items for this (quote, brand).
        # We emit both names (display) and ids (filtering). Sorted by name for
        # stable rendering; ids are sorted the same way to keep the two arrays
        # index-aligned when consumers want a per-user chip render.
        moz_ids_set: set[str] = set()
        for it in items_by_key.get((qid, brand), []):
            uid = it.get("assigned_procurement_user")
            if uid:
                moz_ids_set.add(str(uid))
        named_moz = [
            (name_by_user.get(uid) or "", uid)
            for uid in moz_ids_set
            if name_by_user.get(uid)
        ]
        named_moz.sort(key=lambda pair: pair[0])
        procurement_user_names = [name for name, _ in named_moz]
        procurement_user_ids = [uid for _, uid in named_moz]

        invoice_sums = invoice_sums_by_key.get((qid, brand), [])

        # tender_type lives on the parent quote — empty string for regular
        # КП, populated for tender-flow quotes. Mirrored to the card model so
        # the frontend can render the «Тендер» badge (Testing 2 row 67).
        tender_type = parent.get("tender_type") or None

        # Testing 2 row 67 follow-up (FB-260525): the МОП-authored
        # «Контрольный список» distribution_comment is captured at hand-off
        # to procurement (см. context-panel/sales-checklist-block.tsx) but
        # was previously visible only on the quote detail page. Procurement
        # leads complained that МОЗ had to open every card to read «Срочно
        # / клиент знакомый / т.д.» hints. Mirroring the workspace-kanban
        # pattern (`KanbanCard.distributionComment` — кросс-кванти линки в
        # «Нераспределено»), we surface the trimmed comment on the
        # procurement card. The field is null when the МОП left the
        # checklist empty or skipped it entirely (legacy quotes).
        sales_checklist = parent.get("sales_checklist") or {}
        if isinstance(sales_checklist, dict):
            raw_comment = sales_checklist.get("distribution_comment")
            distribution_comment = (
                raw_comment.strip()
                if isinstance(raw_comment, str) and raw_comment.strip()
                else None
            )
        else:
            distribution_comment = None

        # Pause log (Testing 2 row 74): for paused cards we surface the latest
        # open pause row's reason + actor + timestamp inline so МОЗ doesn't
        # have to open the history drawer to learn why a card is on pause.
        pause_log = None
        if substatus == "paused":
            plog = pause_log_by_quote.get(qid)
            if plog:
                actor_id = str(plog.get("paused_by") or "")
                pause_log = {
                    "id": str(plog.get("id")),
                    "paused_at": plog.get("paused_at"),
                    "paused_by_name": name_by_user.get(actor_id, "") or None,
                    "reason": plog.get("reason") or "",
                }

        columns[substatus].append({
            "quote_id": qid,
            "brand": brand,
            "idn_quote": parent.get("idn_quote"),
            "customer_id": customer_id,
            "customer_name": customer_name,
            "procurement_substatus": substatus,
            "days_in_state": days,
            "updated_at": r.get("updated_at"),
            "manager_id": creator_id,
            "manager_name": manager_name,
            "procurement_user_ids": procurement_user_ids,
            "procurement_user_names": procurement_user_names,
            "invoice_sums": invoice_sums,
            "latest_reason": latest_reason,
            "tender_type": tender_type,
            "pause_log": pause_log,
            # Testing 2 row 83: surface the quote-level completion flag so the
            # UI can mark post-procurement cards as «Готово» rather than
            # hiding them entirely.
            "procurement_completed_at": parent.get("procurement_completed_at"),
            # Testing 2 row 67 follow-up: МОП distribution_comment captured at
            # the sales→procurement hand-off (kvota.quotes.sales_checklist
            # JSONB → distribution_comment). Null when the checklist is empty
            # or absent. UI surfaces it inline on the card so МОЗ reads the
            # hint without opening the quote.
            "distribution_comment": distribution_comment,
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
# POST /api/quotes/{id}/pause
# ============================================================================


def _validate_brand_body(body: dict) -> tuple[str | None, JSONResponse | None]:
    """Extract + validate the `brand` field from a pause/unpause request body.

    Returns (brand, None) on success or (None, error_response). Brand may be
    "" (unbranded items) but must be present + a string — matches post_substatus.
    """
    if "brand" not in body:
        return None, JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "brand is required"}},
            status_code=400,
        )
    brand = body.get("brand")
    if not isinstance(brand, str):
        return None, JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "brand must be a string"}},
            status_code=400,
        )
    return brand, None


def _map_transition_error(msg: str) -> JSONResponse:
    """Map a ValueError msg from workflow_service to the canonical envelope."""
    lower = msg.lower()
    if "not found" in lower:
        return JSONResponse(
            {"success": False, "error": {"code": "QUOTE_NOT_FOUND", "message": msg}},
            status_code=404,
        )
    if lower.startswith("reason required"):
        return JSONResponse(
            {"success": False, "error": {"code": "REASON_REQUIRED", "message": msg}},
            status_code=400,
        )
    if "invalid substatus transition" in lower:
        return JSONResponse(
            {"success": False, "error": {"code": "INVALID_TRANSITION", "message": msg}},
            status_code=400,
        )
    return JSONResponse(
        {"success": False, "error": {"code": "VALIDATION_ERROR", "message": msg}},
        status_code=400,
    )


async def post_pause(request, id: str) -> JSONResponse:
    """Pause a (quote, brand) card with a mandatory reason (Testing 2 row 74).

    Path: POST /api/quotes/{id}/pause
    Params (JSON body):
        brand: str (required) — brand of the card. Use "" for unbranded.
        reason: str (required, non-empty after trim)
    Returns:
        {"quote_id": ..., "brand": ..., "procurement_substatus": "paused"}
    Side Effects:
        - Inserts a procurement_pause_log row (unpaused_at=NULL).
        - Writes status_history audit row via transition_substatus.
        - Updates quote_brand_substates.substatus → 'paused'.
    Roles: admin, procurement, procurement_senior, head_of_procurement
    """
    user, err = _resolve_user_context(request, _PROCUREMENT_ROLES)
    if err:
        return err
    assert user is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    brand, brand_err = _validate_brand_body(body)
    if brand_err:
        return brand_err

    reason = (body.get("reason") or "").strip()
    if not reason:
        return JSONResponse(
            {"success": False, "error": {"code": "REASON_REQUIRED", "message": "Reason is required for pause"}},
            status_code=400,
        )

    try:
        updated = pause_quote(
            quote_id=id,
            brand=brand or "",
            user_id=user["id"],
            user_roles=list(user["role_slugs"]),
            reason=reason,
        )
    except ValueError as e:
        return _map_transition_error(str(e))

    return JSONResponse(
        {
            "success": True,
            "data": {
                "quote_id": str(updated.get("quote_id", id)),
                "brand": updated.get("brand", brand or ""),
                "procurement_substatus": updated.get("substatus", "paused"),
            },
        },
        status_code=200,
    )


# ============================================================================
# POST /api/quotes/{id}/unpause
# ============================================================================


async def post_unpause(request, id: str) -> JSONResponse:
    """Unpause a (quote, brand) card by moving it to an active substatus.

    Path: POST /api/quotes/{id}/unpause
    Params (JSON body):
        brand: str (required) — brand of the card. Use "" for unbranded.
        to_substatus: str (optional, default 'searching_supplier') — target
            active column. Must be one of distributing/searching_supplier/
            waiting_prices/prices_ready.
    Returns:
        {"quote_id": ..., "brand": ..., "procurement_substatus": <new>}
    Side Effects:
        - Closes the latest open procurement_pause_log row (unpaused_at, unpaused_by).
        - Writes status_history audit row via transition_substatus.
        - Updates quote_brand_substates.substatus.
    Roles: admin, procurement, procurement_senior, head_of_procurement
    """
    user, err = _resolve_user_context(request, _PROCUREMENT_ROLES)
    if err:
        return err
    assert user is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    brand, brand_err = _validate_brand_body(body)
    if brand_err:
        return brand_err

    to_substatus = (body.get("to_substatus") or "searching_supplier").strip()
    if to_substatus == "paused":
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "to_substatus cannot be 'paused' on unpause"}},
            status_code=400,
        )

    try:
        updated = unpause_quote(
            quote_id=id,
            brand=brand or "",
            to_substatus=to_substatus,
            user_id=user["id"],
            user_roles=list(user["role_slugs"]),
        )
    except ValueError as e:
        return _map_transition_error(str(e))

    return JSONResponse(
        {
            "success": True,
            "data": {
                "quote_id": str(updated.get("quote_id", id)),
                "brand": updated.get("brand", brand or ""),
                "procurement_substatus": updated.get("substatus", to_substatus),
            },
        },
        status_code=200,
    )


# ============================================================================
# GET /api/quotes/{id}/pause-history
# ============================================================================


async def get_pause_history_endpoint(request, id: str) -> JSONResponse:
    """Return full pause activity log for a quote (Testing 2 row 74).

    Path: GET /api/quotes/{id}/pause-history
    Returns:
        List of pause_log rows ordered by paused_at DESC. Each row:
        id, paused_at, paused_by, paused_by_name, reason,
        unpaused_at, unpaused_by, unpaused_by_name.
    Roles: admin, procurement, procurement_senior, head_of_procurement
    """
    _, err = _resolve_user_context(request, _PROCUREMENT_ROLES)
    if err:
        return err

    rows = get_pause_history(id)

    # Batch-resolve actor names (paused_by + unpaused_by).
    user_ids: set[str] = set()
    for r in rows:
        if r.get("paused_by"):
            user_ids.add(str(r["paused_by"]))
        if r.get("unpaused_by"):
            user_ids.add(str(r["unpaused_by"]))

    name_by_user: dict[str, str] = {}
    if user_ids:
        sb = get_supabase()
        profiles_result = (
            sb.table("user_profiles")
            .select("user_id, full_name")
            .in_("user_id", list(user_ids))
            .execute()
        )
        for p in _rows(profiles_result):
            uid = str(p.get("user_id"))
            name_by_user[uid] = p.get("full_name") or ""

    enriched = []
    for r in rows:
        paused_by = str(r.get("paused_by")) if r.get("paused_by") else None
        unpaused_by = str(r.get("unpaused_by")) if r.get("unpaused_by") else None
        enriched.append({
            "id": str(r.get("id")),
            "paused_at": r.get("paused_at"),
            "paused_by": paused_by,
            "paused_by_name": name_by_user.get(paused_by or "", "") or None,
            "reason": r.get("reason") or "",
            "unpaused_at": r.get("unpaused_at"),
            "unpaused_by": unpaused_by,
            "unpaused_by_name": name_by_user.get(unpaused_by or "", "") or None,
        })

    return JSONResponse({"success": True, "data": enriched}, status_code=200)


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
