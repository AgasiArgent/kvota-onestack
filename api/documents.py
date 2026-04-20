"""Document /api/documents/* endpoints — signed-URL download + delete.

Handler module (not router). Registered via thin wrapper in
api/routers/documents.py. Moved verbatim from main.py @rt decorators
in Phase 6B-9.

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.

The download endpoint returns an HTTP 302 RedirectResponse pointing at a
Supabase storage signed URL. Frontend <a href> tags rely on the 302 to
trigger browser downloads — DO NOT convert to JSON.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from services.database import get_supabase
from services.document_service import delete_document, get_download_url
from services.role_service import get_user_role_codes

logger = logging.getLogger(__name__)


def _resolve_dual_auth(request: Request) -> tuple[dict | None, list[str]]:
    """Resolve authenticated user + effective role codes.

    Supports two auth modes:
      - JWT (Next.js) via ApiAuthMiddleware — request.state.api_user populated
      - Legacy session (FastHTML) via SessionMiddleware — request.session.user

    Returns (user_dict, role_codes) or (None, []) if unauthenticated.
    user_dict contains at least: id, org_id.

    Mirrors ``user_has_any_role`` semantics: session-based callers respect
    admin ``impersonated_role``. JWT callers resolve roles from the DB.
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

    # Impersonation replaces real roles for role gating (matches user_has_any_role)
    impersonated_role = session.get("impersonated_role")
    if impersonated_role:
        return user, [impersonated_role]

    return user, user.get("roles", [])


async def download_document(request: Request, document_id: str) -> Response:
    """GET /api/documents/{document_id}/download — issue 302 to storage signed URL.

    Path: GET /api/documents/{document_id}/download
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Returns:
        302 RedirectResponse to the Supabase storage signed URL (expires in 1h).
        404 JSONResponse when the document is missing.
        303 RedirectResponse to /login when unauthenticated via session.
    Roles: any authenticated user.
    """
    user, _ = _resolve_dual_auth(request)
    if not user:
        # Preserve legacy FastHTML behaviour: redirect to /login when unauth.
        return RedirectResponse("/login", status_code=303)

    download_url = get_download_url(document_id, expires_in=3600, force_download=True)
    if not download_url:
        return JSONResponse(
            {"success": False, "error": "Document not found"}, status_code=404
        )

    return RedirectResponse(download_url, status_code=302)


async def delete_document_api(request: Request, document_id: str) -> JSONResponse:
    """DELETE /api/documents/{document_id}.

    Path: DELETE /api/documents/{document_id}
    Auth: dual — JWT (Next.js) or legacy session (FastHTML).
    Returns:
        200 JSONResponse(success=True) on success.
        401 JSONResponse when unauthenticated.
        403 JSONResponse when user lacks procurement/admin role.
        500 JSONResponse when the storage/db delete fails.
    Side Effects:
        - Removes storage object + document row from DB.
    Roles: procurement, admin, head_of_procurement.
    """
    user, role_codes = _resolve_dual_auth(request)
    if not user:
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=401
        )

    allowed_roles = {"procurement", "admin", "head_of_procurement"}
    if not (set(role_codes) & allowed_roles):
        return JSONResponse(
            {"success": False, "error": "Forbidden"}, status_code=403
        )

    success, error = delete_document(document_id)
    if success:
        return JSONResponse({"success": True})
    return JSONResponse(
        {"success": False, "error": error or "Delete failed"}, status_code=500
    )
