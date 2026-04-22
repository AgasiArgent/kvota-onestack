"""Notes /api/notes/* endpoints — polymorphic entity_notes CRUD.

Handler module (not router). Registered via thin wrapper in
api/routers/notes.py. Implements Wave 1 Task 5.2 of
logistics-customs-redesign spec (design.md §6.4).

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.

Access model:
  - Reads: DB RLS (m291) filters by visible_to[] (role slug membership +
    '*' wildcard + author bypass).
  - Writes: INSERT requires author_id = auth.uid(); UPDATE/DELETE allowed
    only for the note author or an admin. Enforced here + by RLS.

author_role is frozen at write time — the slug of the user's active role
when the note is posted. Role changes later do not retroactively rewrite
historical notes.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

from services.database import get_supabase
from services.role_service import get_user_role_codes

logger = logging.getLogger(__name__)

_ALLOWED_ENTITY_TYPES = {"quote", "customer", "invoice", "supplier"}


# ---------------------------------------------------------------------------
# Auth + helpers
# ---------------------------------------------------------------------------


def _resolve_dual_auth(request: Request) -> tuple[dict | None, list[str]]:
    """Resolve authenticated user + effective role codes.

    Mirrors api/customs.py. JWT (Next.js) or legacy session (FastHTML).
    Session path honors admin ``impersonated_role`` for role gating.
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


def _pick_author_role(role_codes: list[str]) -> str:
    """Pick a role slug to freeze into author_role.

    Preference order: non-admin first (actual working role), then admin, then
    the literal string "user" for accounts with zero active roles (edge case
    during onboarding — the note is still useful, just not tied to a role).
    """
    if not role_codes:
        return "user"
    non_admin = [r for r in role_codes if r != "admin"]
    if non_admin:
        return non_admin[0]
    return role_codes[0]


def _is_admin(role_codes: list[str]) -> bool:
    return "admin" in (role_codes or [])


def _authenticate(request: Request) -> tuple[dict, list[str]] | JSONResponse:
    """Reject unauthenticated callers; return (user, roles) on success."""
    user, role_codes = _resolve_dual_auth(request)
    if not user:
        return _err("UNAUTHORIZED", "Not authenticated", 401)
    if not user.get("org_id"):
        return _err("UNAUTHORIZED", "No organization context", 401)
    return user, role_codes


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def list_notes(request: Request) -> JSONResponse:
    """GET /api/notes?entity_type=<str>&entity_id=<uuid> — list notes for an entity.

    RLS (m291) filters rows by visible_to[] against the caller's role set,
    with author bypass. Pinned notes come first, then newest.

    Path: GET /api/notes
    Query:
        entity_type: str (required) — one of quote, customer, invoice, supplier
        entity_id: str (required)
    Returns:
        data: list of note rows (oldest/pinned first — see ordering)
    """
    auth = _authenticate(request)
    if isinstance(auth, JSONResponse):
        return auth
    _user, _roles = auth

    entity_type = request.query_params.get("entity_type")
    entity_id = request.query_params.get("entity_id")
    if not entity_type or not entity_id:
        return _err("VALIDATION_ERROR", "entity_type and entity_id are required", 400)
    if entity_type not in _ALLOWED_ENTITY_TYPES:
        return _err(
            "VALIDATION_ERROR",
            f"entity_type must be one of {sorted(_ALLOWED_ENTITY_TYPES)}",
            400,
        )

    sb = get_supabase()
    # RLS handles visibility filtering.
    res = (
        sb.table("entity_notes")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .order("pinned", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return _ok(res.data or [])


async def create_note(request: Request) -> JSONResponse:
    """POST /api/notes — create a new note.

    author_id is set from the session user; author_role is frozen from the
    user's active role set at write time. visible_to defaults to ['*'] when
    not provided (visible to all org members).

    Path: POST /api/notes
    Body (JSON):
        entity_type: str (required) — quote | customer | invoice | supplier
        entity_id: str (required)
        body: str (required, trimmed length > 0)
        visible_to: list[str] (optional) — role slugs or '*'. Default: ['*']
        pinned: bool (optional) — default false
    Returns:
        data: created note row
    """
    auth = _authenticate(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, role_codes = auth

    try:
        body_json = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    entity_type = body_json.get("entity_type")
    entity_id = body_json.get("entity_id")
    text = body_json.get("body")
    if not entity_type or not entity_id or not text:
        return _err(
            "VALIDATION_ERROR",
            "entity_type, entity_id, body are required",
            400,
        )
    if entity_type not in _ALLOWED_ENTITY_TYPES:
        return _err(
            "VALIDATION_ERROR",
            f"entity_type must be one of {sorted(_ALLOWED_ENTITY_TYPES)}",
            400,
        )
    if not isinstance(text, str) or not text.strip():
        return _err("VALIDATION_ERROR", "body must be non-empty text", 400)

    visible_to = body_json.get("visible_to")
    if visible_to is None:
        visible_to = ["*"]
    if not isinstance(visible_to, list) or not all(
        isinstance(v, str) for v in visible_to
    ):
        return _err(
            "VALIDATION_ERROR",
            "visible_to must be a list of role slugs (or ['*'])",
            400,
        )
    if not visible_to:
        visible_to = ["*"]

    pinned = bool(body_json.get("pinned", False))

    sb = get_supabase()
    res = (
        sb.table("entity_notes")
        .insert(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "author_id": user["id"],
                "author_role": _pick_author_role(role_codes),
                "visible_to": visible_to,
                "body": text,
                "pinned": pinned,
            }
        )
        .execute()
    )
    if not res.data:
        return _err("INTERNAL_ERROR", "Failed to create note", 500)
    return _ok(res.data[0], status=201)


async def update_note(request: Request, note_id: str) -> JSONResponse:
    """PATCH /api/notes/{id} — update a note.

    Only the author or an admin may update. body, visible_to, pinned are all
    optional — at least one must be provided.

    Path: PATCH /api/notes/{id}
    Body (JSON, all optional):
        body: str — new text (trimmed length > 0 if provided)
        visible_to: list[str] — role slugs or '*' (default preserved)
        pinned: bool
    Returns:
        { success: true }
    """
    auth = _authenticate(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, role_codes = auth

    sb = get_supabase()
    existing = (
        sb.table("entity_notes")
        .select("id, author_id")
        .eq("id", note_id)
        .execute()
    )
    if not existing.data:
        return _err("NOT_FOUND", "Note not found", 404)
    note = existing.data[0]
    if note["author_id"] != user["id"] and not _is_admin(role_codes):
        return _err("FORBIDDEN", "Only author or admin can update this note", 403)

    try:
        body_json = await request.json()
    except Exception:
        return _err("BAD_REQUEST", "Invalid JSON", 400)

    updates: dict = {}
    if "body" in body_json:
        text = body_json["body"]
        if not isinstance(text, str) or not text.strip():
            return _err("VALIDATION_ERROR", "body must be non-empty text", 400)
        updates["body"] = text
    if "visible_to" in body_json:
        visible_to = body_json["visible_to"]
        if not isinstance(visible_to, list) or not all(
            isinstance(v, str) for v in visible_to
        ):
            return _err(
                "VALIDATION_ERROR",
                "visible_to must be a list of role slugs (or ['*'])",
                400,
            )
        if not visible_to:
            visible_to = ["*"]
        updates["visible_to"] = visible_to
    if "pinned" in body_json:
        updates["pinned"] = bool(body_json["pinned"])

    if not updates:
        return _err("VALIDATION_ERROR", "No updatable fields provided", 400)

    res = (
        sb.table("entity_notes").update(updates).eq("id", note_id).execute()
    )
    if not res.data:
        return _err("INTERNAL_ERROR", "Failed to update note", 500)
    return _ok()


async def delete_note(request: Request, note_id: str) -> JSONResponse:
    """DELETE /api/notes/{id} — remove a note.

    Only the author or an admin may delete.

    Path: DELETE /api/notes/{id}
    Returns: { success: true }
    """
    auth = _authenticate(request)
    if isinstance(auth, JSONResponse):
        return auth
    user, role_codes = auth

    sb = get_supabase()
    existing = (
        sb.table("entity_notes")
        .select("id, author_id")
        .eq("id", note_id)
        .execute()
    )
    if not existing.data:
        return _err("NOT_FOUND", "Note not found", 404)
    note = existing.data[0]
    if note["author_id"] != user["id"] and not _is_admin(role_codes):
        return _err("FORBIDDEN", "Only author or admin can delete this note", 403)

    sb.table("entity_notes").delete().eq("id", note_id).execute()
    return _ok()
