"""Logistics /api/logistics/* endpoints — route constructor, templates, SLA.

Handler module (not router). Registered via thin wrapper in
api/routers/logistics.py. Implements Wave 1 Task 4.5 of
logistics-customs-redesign spec (design.md §6.1).

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.
Roles: logistics, head_of_logistics, admin.

Endpoints:
  - Route segments CRUD + reorder (one route per invoice)
  - Segment expenses (freeform cost lines inside a segment)
  - Org-scoped route templates (scaffold → concrete segments when applied)
  - Complete invoice (set logistics_completed_at, blocked by pending review)
  - Acknowledge review (clear logistics_needs_review_since)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from services.database import get_supabase
from services.role_service import get_user_role_codes

logger = logging.getLogger(__name__)

_LOGISTICS_ROLES = {"logistics", "head_of_logistics", "admin"}
_LOCATION_TYPES = {"supplier", "hub", "customs", "own_warehouse", "client"}


# ---------------------------------------------------------------------------
# Auth + helpers
# ---------------------------------------------------------------------------


def _resolve_dual_auth(request: Request) -> tuple[dict | None, list[str]]:
    """Resolve authenticated user + effective role codes.

    Mirrors api/customs.py — JWT (Next.js) or legacy session (FastHTML).
    Session path honors admin ``impersonated_role`` for role gating.
    Returns (user_dict, role_codes) or (None, []) when unauthenticated.
    user_dict contains at least: id, org_id.
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


def _err(code: str, message: str, status: int) -> JSONResponse:
    """Structured error response envelope."""
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


def _ok(data: dict | list | None = None, status: int = 200) -> JSONResponse:
    """Success response envelope."""
    payload: dict = {"success": True}
    if data is not None:
        payload["data"] = data
    return JSONResponse(payload, status_code=status)


def _authorize(
    request: Request,
) -> tuple[dict, list[str]] | JSONResponse:
    """Reject unauthorized callers; return (user, roles) on success."""
    user, role_codes = _resolve_dual_auth(request)
    if not user:
        return _err("UNAUTHORIZED", "Not authenticated", 401)
    if not user.get("org_id"):
        return _err("UNAUTHORIZED", "No organization context", 401)
    if not (set(role_codes) & _LOGISTICS_ROLES):
        return _err("FORBIDDEN", "Logistics role required", 403)
    return user, role_codes


def _assert_invoice_in_org(invoice_id: str, org_id: str) -> dict | None:
    """Return invoice row if it belongs to org; None otherwise."""
    sb = get_supabase()
    res = (
        sb.table("invoices")
        .select(
            "id, quote_id, logistics_completed_at, logistics_needs_review_since, "
            "quotes!inner(id, organization_id, deleted_at)"
        )
        .eq("id", invoice_id)
        .eq("quotes.organization_id", org_id)
        .is_("quotes.deleted_at", None)
        .execute()
    )
    return res.data[0] if res.data else None


def _assert_segment_in_org(segment_id: str, org_id: str) -> dict | None:
    """Return segment row if it belongs to an invoice in the user's org."""
    sb = get_supabase()
    res = (
        sb.table("logistics_route_segments")
        .select(
            "id, invoice_id, sequence_order, from_location_id, to_location_id, "
            "label, transit_days, main_cost_rub, carrier, notes, "
            "invoices!inner(id, quote_id, quotes!inner(organization_id, deleted_at))"
        )
        .eq("id", segment_id)
        .eq("invoices.quotes.organization_id", org_id)
        .is_("invoices.quotes.deleted_at", None)
        .execute()
    )
    return res.data[0] if res.data else None


# ---------------------------------------------------------------------------
# Route segments
# ---------------------------------------------------------------------------


async def create_segment(request: Request) -> JSONResponse:
    """POST /api/logistics/segments — create a route segment.

    Path: POST /api/logistics/segments
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Body (JSON):
        invoice_id: str (required)
        from_location_id: str (required)
        to_location_id: str (required)
        sequence_order: int (optional — defaults to MAX+1)
        label: str (optional)
        transit_days: int (optional)
        main_cost_rub: number (optional, default 0)
        carrier: str (optional)
        notes: str (optional)
    Returns:
        data: created segment row
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    invoice_id = body.get("invoice_id")
    from_location_id = body.get("from_location_id")
    to_location_id = body.get("to_location_id")

    if not invoice_id or not from_location_id or not to_location_id:
        return _err(
            "VALIDATION_ERROR",
            "invoice_id, from_location_id, to_location_id are required",
            400,
        )

    if not _assert_invoice_in_org(invoice_id, org_id):
        return _err("NOT_FOUND", "Invoice not found", 404)

    sb = get_supabase()

    sequence_order = body.get("sequence_order")
    if sequence_order is None:
        existing = (
            sb.table("logistics_route_segments")
            .select("sequence_order")
            .eq("invoice_id", invoice_id)
            .order("sequence_order", desc=True)
            .limit(1)
            .execute()
        )
        sequence_order = (
            (existing.data[0]["sequence_order"] + 1) if existing.data else 1
        )

    payload = {
        "invoice_id": invoice_id,
        "sequence_order": int(sequence_order),
        "from_location_id": from_location_id,
        "to_location_id": to_location_id,
        "label": body.get("label"),
        "transit_days": body.get("transit_days"),
        "main_cost_rub": body.get("main_cost_rub") or 0,
        "carrier": body.get("carrier"),
        "notes": body.get("notes"),
        "created_by": user["id"],
    }

    res = sb.table("logistics_route_segments").insert(payload).execute()
    if not res.data:
        return _err("INTERNAL_ERROR", "Failed to create segment", 500)

    return _ok(res.data[0], status=201)


async def list_segments(request: Request) -> JSONResponse:
    """GET /api/logistics/segments?invoice_id=<uuid> — list segments for invoice.

    Path: GET /api/logistics/segments
    Query:
        invoice_id: str (required)
    Returns:
        data: list of segment rows, ordered by sequence_order ASC
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    invoice_id = request.query_params.get("invoice_id")
    if not invoice_id:
        return _err("VALIDATION_ERROR", "invoice_id is required", 400)

    if not _assert_invoice_in_org(invoice_id, org_id):
        return _err("NOT_FOUND", "Invoice not found", 404)

    sb = get_supabase()
    res = (
        sb.table("logistics_route_segments")
        .select("*")
        .eq("invoice_id", invoice_id)
        .order("sequence_order")
        .execute()
    )
    return _ok(res.data or [])


async def update_segment(request: Request, segment_id: str) -> JSONResponse:
    """PATCH /api/logistics/segments/{id} — update a segment.

    Path: PATCH /api/logistics/segments/{id}
    Body (JSON, all optional):
        from_location_id, to_location_id, label, transit_days, main_cost_rub,
        carrier, notes
    Returns:
        data: updated segment row
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    if not _assert_segment_in_org(segment_id, org_id):
        return _err("NOT_FOUND", "Segment not found", 404)

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    allowed = {
        "from_location_id",
        "to_location_id",
        "label",
        "transit_days",
        "main_cost_rub",
        "carrier",
        "notes",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return _err("VALIDATION_ERROR", "No updatable fields provided", 400)

    sb = get_supabase()
    res = (
        sb.table("logistics_route_segments")
        .update(updates)
        .eq("id", segment_id)
        .execute()
    )
    if not res.data:
        return _err("INTERNAL_ERROR", "Failed to update segment", 500)
    return _ok(res.data[0])


async def delete_segment(request: Request, segment_id: str) -> JSONResponse:
    """DELETE /api/logistics/segments/{id} — remove a segment.

    Cascades to logistics_segment_expenses via FK ON DELETE CASCADE.

    Path: DELETE /api/logistics/segments/{id}
    Returns: { success: true }
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    if not _assert_segment_in_org(segment_id, org_id):
        return _err("NOT_FOUND", "Segment not found", 404)

    sb = get_supabase()
    sb.table("logistics_route_segments").delete().eq("id", segment_id).execute()
    return _ok()


async def reorder_segments(request: Request) -> JSONResponse:
    """POST /api/logistics/segments/reorder — set a new sequence order for all segments of an invoice.

    Renumbers in a single pass without UNIQUE (invoice_id, sequence_order)
    violations by first pushing each segment to a high temporary slot, then
    writing the final sequence. Only segments listed in the payload are
    reordered; unlisted segments keep their current sequence_order.

    Path: POST /api/logistics/segments/reorder
    Body (JSON):
        invoice_id: str (required)
        sequence: list[str] (required) — segment ids in desired order (1-based)
    Returns:
        data: list of updated segments ordered by new sequence_order
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    invoice_id = body.get("invoice_id")
    sequence = body.get("sequence")
    if not invoice_id or not isinstance(sequence, list) or not sequence:
        return _err(
            "VALIDATION_ERROR",
            "invoice_id and non-empty sequence[] are required",
            400,
        )

    if not _assert_invoice_in_org(invoice_id, org_id):
        return _err("NOT_FOUND", "Invoice not found", 404)

    sb = get_supabase()

    # Verify every segment belongs to this invoice before we touch anything.
    existing = (
        sb.table("logistics_route_segments")
        .select("id")
        .eq("invoice_id", invoice_id)
        .in_("id", sequence)
        .execute()
    )
    found_ids = {row["id"] for row in (existing.data or [])}
    if found_ids != set(sequence):
        return _err(
            "VALIDATION_ERROR",
            "Some segment ids do not belong to this invoice",
            400,
        )

    # Two-phase to avoid UNIQUE (invoice_id, sequence_order) collisions.
    # Phase 1: bump every listed segment to a large negative offset.
    for idx, seg_id in enumerate(sequence, start=1):
        sb.table("logistics_route_segments").update(
            {"sequence_order": -idx}
        ).eq("id", seg_id).execute()

    # Phase 2: assign the final 1..N ordering.
    for idx, seg_id in enumerate(sequence, start=1):
        sb.table("logistics_route_segments").update(
            {"sequence_order": idx}
        ).eq("id", seg_id).execute()

    res = (
        sb.table("logistics_route_segments")
        .select("*")
        .eq("invoice_id", invoice_id)
        .order("sequence_order")
        .execute()
    )
    return _ok(res.data or [])


# ---------------------------------------------------------------------------
# Segment expenses
# ---------------------------------------------------------------------------


async def create_expense(request: Request) -> JSONResponse:
    """POST /api/logistics/expenses — add a freeform cost line to a segment.

    Path: POST /api/logistics/expenses
    Body (JSON):
        segment_id: str (required)
        label: str (required)
        cost_rub: number (required, >= 0)
        days: int (optional)
        notes: str (optional)
    Returns:
        data: created expense row
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    segment_id = body.get("segment_id")
    label = body.get("label")
    cost_rub = body.get("cost_rub")
    if not segment_id or not label or cost_rub is None:
        return _err(
            "VALIDATION_ERROR",
            "segment_id, label, cost_rub are required",
            400,
        )

    if not _assert_segment_in_org(segment_id, org_id):
        return _err("NOT_FOUND", "Segment not found", 404)

    sb = get_supabase()
    payload = {
        "segment_id": segment_id,
        "label": label,
        "cost_rub": cost_rub,
        "days": body.get("days"),
        "notes": body.get("notes"),
    }
    res = sb.table("logistics_segment_expenses").insert(payload).execute()
    if not res.data:
        return _err("INTERNAL_ERROR", "Failed to create expense", 500)
    return _ok(res.data[0], status=201)


async def delete_expense(request: Request, expense_id: str) -> JSONResponse:
    """DELETE /api/logistics/expenses/{id} — remove a segment expense.

    Path: DELETE /api/logistics/expenses/{id}
    Returns: { success: true }
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    sb = get_supabase()

    # Scope check: expense → segment → invoice → quote.organization_id
    res = (
        sb.table("logistics_segment_expenses")
        .select(
            "id, logistics_route_segments!inner("
            "invoice_id, invoices!inner(quote_id, quotes!inner(organization_id, deleted_at))"
            ")"
        )
        .eq("id", expense_id)
        .eq(
            "logistics_route_segments.invoices.quotes.organization_id",
            org_id,
        )
        .is_("logistics_route_segments.invoices.quotes.deleted_at", None)
        .execute()
    )
    if not res.data:
        return _err("NOT_FOUND", "Expense not found", 404)

    sb.table("logistics_segment_expenses").delete().eq("id", expense_id).execute()
    return _ok()


# ---------------------------------------------------------------------------
# Route templates
# ---------------------------------------------------------------------------


async def list_templates(request: Request) -> JSONResponse:
    """GET /api/logistics/templates — list org route templates.

    Path: GET /api/logistics/templates
    Returns:
        data: list of templates (each with nested segments ordered by sequence_order ASC)
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    sb = get_supabase()
    res = (
        sb.table("logistics_route_templates")
        .select(
            "id, organization_id, name, description, created_by, created_at, updated_at, "
            "logistics_route_template_segments(id, sequence_order, from_location_type, "
            "to_location_type, default_label, default_days)"
        )
        .eq("organization_id", org_id)
        .order("name")
        .execute()
    )

    # Sort nested segments client-side — Supabase PostgREST doesn't support
    # nested order in the select string reliably.
    templates = res.data or []
    for tpl in templates:
        segs = tpl.get("logistics_route_template_segments") or []
        segs.sort(key=lambda s: s.get("sequence_order") or 0)
        tpl["segments"] = segs
        tpl.pop("logistics_route_template_segments", None)
    return _ok(templates)


async def create_template(request: Request) -> JSONResponse:
    """POST /api/logistics/templates — create a reusable route scaffold.

    Path: POST /api/logistics/templates
    Body (JSON):
        name: str (required)
        description: str (optional)
        segments: list[{from_location_type, to_location_type, default_label?, default_days?}]
            (required, non-empty)
    Returns:
        data: created template row with nested segments
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    name = (body.get("name") or "").strip()
    segments = body.get("segments") or []
    if not name:
        return _err("VALIDATION_ERROR", "name is required", 400)
    if not isinstance(segments, list) or not segments:
        return _err("VALIDATION_ERROR", "segments[] must be non-empty", 400)

    for seg in segments:
        ft = seg.get("from_location_type")
        tt = seg.get("to_location_type")
        if ft not in _LOCATION_TYPES or tt not in _LOCATION_TYPES:
            return _err(
                "VALIDATION_ERROR",
                f"Invalid location type. Allowed: {sorted(_LOCATION_TYPES)}",
                400,
            )

    sb = get_supabase()
    tpl_res = (
        sb.table("logistics_route_templates")
        .insert(
            {
                "organization_id": org_id,
                "name": name,
                "description": body.get("description"),
                "created_by": user["id"],
            }
        )
        .execute()
    )
    if not tpl_res.data:
        return _err("INTERNAL_ERROR", "Failed to create template", 500)
    template = tpl_res.data[0]
    template_id = template["id"]

    seg_rows = [
        {
            "template_id": template_id,
            "sequence_order": idx,
            "from_location_type": seg["from_location_type"],
            "to_location_type": seg["to_location_type"],
            "default_label": seg.get("default_label"),
            "default_days": seg.get("default_days"),
        }
        for idx, seg in enumerate(segments, start=1)
    ]
    seg_res = (
        sb.table("logistics_route_template_segments").insert(seg_rows).execute()
    )
    template["segments"] = seg_res.data or []
    return _ok(template, status=201)


async def update_template(request: Request, template_id: str) -> JSONResponse:
    """PATCH /api/logistics/templates/{id} — replace template body.

    Path: PATCH /api/logistics/templates/{id}
    Body:
        name: str (required)
        description: str (optional)
        segments: list (required, non-empty) — replaces all existing segments
    Returns: { success, data: { template_id } }
    Side effects:
        - Updates logistics_route_templates row (name, description)
        - DELETEs all logistics_route_template_segments for this template,
          INSERTs the new segments (sequence_order starts at 1).
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    name = (body.get("name") or "").strip()
    segments = body.get("segments") or []
    if not name:
        return _err("VALIDATION_ERROR", "name is required", 400)
    if not isinstance(segments, list) or not segments:
        return _err("VALIDATION_ERROR", "segments[] must be non-empty", 400)

    for seg in segments:
        ft = seg.get("from_location_type")
        tt = seg.get("to_location_type")
        if ft not in _LOCATION_TYPES or tt not in _LOCATION_TYPES:
            return _err(
                "VALIDATION_ERROR",
                f"Invalid location type. Allowed: {sorted(_LOCATION_TYPES)}",
                400,
            )

    sb = get_supabase()
    existing = (
        sb.table("logistics_route_templates")
        .select("id")
        .eq("id", template_id)
        .eq("organization_id", org_id)
        .execute()
    )
    if not existing.data:
        return _err("NOT_FOUND", "Template not found", 404)

    sb.table("logistics_route_templates").update(
        {"name": name, "description": body.get("description")}
    ).eq("id", template_id).execute()

    # Replace segments atomically-ish: delete old, insert new.
    sb.table("logistics_route_template_segments").delete().eq(
        "template_id", template_id
    ).execute()

    seg_rows = [
        {
            "template_id": template_id,
            "sequence_order": idx,
            "from_location_type": seg["from_location_type"],
            "to_location_type": seg["to_location_type"],
            "default_label": seg.get("default_label"),
            "default_days": seg.get("default_days"),
        }
        for idx, seg in enumerate(segments, start=1)
    ]
    sb.table("logistics_route_template_segments").insert(seg_rows).execute()

    return _ok({"template_id": template_id})


async def delete_template(request: Request, template_id: str) -> JSONResponse:
    """DELETE /api/logistics/templates/{id} — remove a template.

    Cascades to logistics_route_template_segments via FK ON DELETE CASCADE.

    Path: DELETE /api/logistics/templates/{id}
    Returns: { success: true }
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    sb = get_supabase()
    tpl = (
        sb.table("logistics_route_templates")
        .select("id")
        .eq("id", template_id)
        .eq("organization_id", org_id)
        .execute()
    )
    if not tpl.data:
        return _err("NOT_FOUND", "Template not found", 404)

    sb.table("logistics_route_templates").delete().eq("id", template_id).execute()
    return _ok()


async def apply_template(request: Request, template_id: str) -> JSONResponse:
    """POST /api/logistics/templates/{id}/apply?invoice_id=<uuid>
    — materialize template segments into concrete invoice segments.

    Uses pickup_location_id (from invoice) for from_location_type='supplier'
    and delivery_location_id (from quote) for to_location_type='client' when
    they match. For other location types, the caller-supplied overrides in
    `location_map` are used; if not provided, the first org-scoped location of
    that type is chosen as a placeholder — the logistician then edits per
    segment.

    Path: POST /api/logistics/templates/{id}/apply
    Query:
        invoice_id: str (required)
    Body (JSON, optional):
        location_map: { <location_type>: <location_id> }
            Overrides the default placeholder resolution for that type.
        replace: bool (default false) — when true, existing segments of the
            invoice are deleted before materializing.
    Returns:
        data: list of newly created segment rows
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    invoice_id = request.query_params.get("invoice_id")
    if not invoice_id:
        return _err("VALIDATION_ERROR", "invoice_id is required", 400)

    invoice = _assert_invoice_in_org(invoice_id, org_id)
    if not invoice:
        return _err("NOT_FOUND", "Invoice not found", 404)

    body: dict = {}
    try:
        if await request.body():
            body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    location_map: dict = body.get("location_map") or {}
    replace = bool(body.get("replace"))

    sb = get_supabase()

    tpl = (
        sb.table("logistics_route_templates")
        .select(
            "id, organization_id, "
            "logistics_route_template_segments(sequence_order, from_location_type, "
            "to_location_type, default_label, default_days)"
        )
        .eq("id", template_id)
        .eq("organization_id", org_id)
        .execute()
    )
    if not tpl.data:
        return _err("NOT_FOUND", "Template not found", 404)

    template_segments = tpl.data[0].get("logistics_route_template_segments") or []
    if not template_segments:
        return _err("VALIDATION_ERROR", "Template has no segments", 400)
    template_segments.sort(key=lambda s: s.get("sequence_order") or 0)

    # Resolve a placeholder location id for each type referenced by the template.
    # Precedence: caller override → org-scoped location with matching type →
    # fall back to any org-scoped location (last resort, so apply never fails
    # silently and logistician can edit afterwards).
    needed_types = {s["from_location_type"] for s in template_segments} | {
        s["to_location_type"] for s in template_segments
    }
    resolved: dict[str, str] = {}
    for loc_type in needed_types:
        override = location_map.get(loc_type)
        if override:
            resolved[loc_type] = override
            continue
        loc = (
            sb.table("locations")
            .select("id")
            .eq("organization_id", org_id)
            .eq("location_type", loc_type)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if loc.data:
            resolved[loc_type] = loc.data[0]["id"]

    missing = needed_types - set(resolved.keys())
    if missing:
        return _err(
            "VALIDATION_ERROR",
            f"No location available for type(s): {sorted(missing)}. "
            "Provide location_map overrides or create matching locations.",
            400,
        )

    if replace:
        sb.table("logistics_route_segments").delete().eq(
            "invoice_id", invoice_id
        ).execute()
        starting_order = 1
    else:
        existing = (
            sb.table("logistics_route_segments")
            .select("sequence_order")
            .eq("invoice_id", invoice_id)
            .order("sequence_order", desc=True)
            .limit(1)
            .execute()
        )
        starting_order = (
            (existing.data[0]["sequence_order"] + 1) if existing.data else 1
        )

    new_rows = [
        {
            "invoice_id": invoice_id,
            "sequence_order": starting_order + idx,
            "from_location_id": resolved[ts["from_location_type"]],
            "to_location_id": resolved[ts["to_location_type"]],
            "label": ts.get("default_label"),
            "transit_days": ts.get("default_days"),
            "main_cost_rub": 0,
            "created_by": user["id"],
        }
        for idx, ts in enumerate(template_segments)
    ]
    res = sb.table("logistics_route_segments").insert(new_rows).execute()
    return _ok(res.data or [], status=201)


# ---------------------------------------------------------------------------
# Workflow: complete + acknowledge review
# ---------------------------------------------------------------------------


async def complete(request: Request) -> JSONResponse:
    """POST /api/logistics/complete — mark logistics pricing done.

    Fails with 409 if a pending review flag is set
    (logistics_needs_review_since is not NULL — procurement changed items
    after previous completion).

    Path: POST /api/logistics/complete
    Body (JSON):
        invoice_id: str (required)
    Returns:
        data: { invoice_id, logistics_completed_at, logistics_completed_by }
    Side Effects:
        - Sets logistics_completed_at = NOW() on the invoice.
        - Sets logistics_completed_by = user.id
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    invoice_id = body.get("invoice_id")
    if not invoice_id:
        return _err("VALIDATION_ERROR", "invoice_id is required", 400)

    invoice = _assert_invoice_in_org(invoice_id, org_id)
    if not invoice:
        return _err("NOT_FOUND", "Invoice not found", 404)

    if invoice.get("logistics_needs_review_since"):
        return _err(
            "CONFLICT",
            "Pending review: procurement changed items since last completion. "
            "Acknowledge review first.",
            409,
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    sb = get_supabase()
    res = (
        sb.table("invoices")
        .update(
            {
                "logistics_completed_at": now_iso,
                "logistics_completed_by": user["id"],
            }
        )
        .eq("id", invoice_id)
        .execute()
    )
    if not res.data:
        return _err("INTERNAL_ERROR", "Failed to complete logistics", 500)
    row = res.data[0]
    return _ok(
        {
            "invoice_id": row["id"],
            "logistics_completed_at": row.get("logistics_completed_at"),
            "logistics_completed_by": row.get("logistics_completed_by"),
        }
    )


async def acknowledge_review(request: Request) -> JSONResponse:
    """POST /api/logistics/acknowledge-review — clear the review flag.

    Called when a logistician has re-checked pricing after a smart-delta
    procurement change and confirms no adjustment is needed (or after they've
    re-edited). The actual re-completion is a separate /complete call.

    Path: POST /api/logistics/acknowledge-review
    Body (JSON):
        invoice_id: str (required)
    Returns:
        data: { invoice_id, logistics_needs_review_since: null }
    Roles: logistics, head_of_logistics, admin.
    """
    auth = _authorize(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, _roles = auth
    org_id = user["org_id"]

    try:
        body = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    invoice_id = body.get("invoice_id")
    if not invoice_id:
        return _err("VALIDATION_ERROR", "invoice_id is required", 400)

    if not _assert_invoice_in_org(invoice_id, org_id):
        return _err("NOT_FOUND", "Invoice not found", 404)

    sb = get_supabase()
    res = (
        sb.table("invoices")
        .update({"logistics_needs_review_since": None})
        .eq("id", invoice_id)
        .execute()
    )
    if not res.data:
        return _err("INTERNAL_ERROR", "Failed to acknowledge review", 500)
    return _ok(
        {
            "invoice_id": invoice_id,
            "logistics_needs_review_since": None,
        }
    )
