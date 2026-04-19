"""
Invoice Send Flow API endpoints for Next.js frontend and AI agents.

POST   /api/invoices/{id}/download-xls               — Generate XLS + commit as sent
GET    /api/invoices/{id}/letter-draft                — Fetch active (unsent) draft
POST   /api/invoices/{id}/letter-draft                — Create/update active draft
POST   /api/invoices/{id}/letter-draft/send           — Mark draft as sent (commit)
DELETE /api/invoices/{id}/letter-draft/{draft_id}      — Delete unsent draft
GET    /api/invoices/{id}/letter-drafts/history       — Fetch all sent drafts
POST   /api/invoices/{id}/procurement-unlock-request  — Request unlock approval
                                                         for a procurement-locked quote

Auth: JWT via ApiAuthMiddleware (request.state.api_user).
Roles: procurement, admin, head_of_procurement
"""

import logging
from datetime import datetime, timezone
from typing import Any

from starlette.responses import JSONResponse, Response

from services.database import get_supabase

logger = logging.getLogger(__name__)

_PROCUREMENT_ROLES = {"procurement", "admin", "head_of_procurement"}


def _rows(response: Any) -> list[dict[str, Any]]:
    """Extract typed rows from Supabase response."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _get_procurement_user(request) -> tuple[dict | None, JSONResponse | None]:
    """Authenticate and authorize user for procurement invoice operations.

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

    # Resolve org_id
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

    # Resolve role slugs
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

    if not role_slugs & _PROCUREMENT_ROLES:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Procurement role required"}},
            status_code=403,
        )

    return {
        "id": user_id,
        "org_id": org_id,
        "role_slugs": role_slugs,
    }, None


def _verify_invoice_ownership(invoice_id: str, org_id: str) -> tuple[dict | None, JSONResponse | None]:
    """Verify invoice exists and belongs to user's organization.

    Returns (invoice_row, None) on success or (None, error_response).
    """
    sb = get_supabase()
    result = (
        sb.table("invoices")
        .select("id, quote_id, invoice_number, sent_at, quotes!inner(organization_id)")
        .eq("id", invoice_id)
        .execute()
    )
    rows = _rows(result)
    if not rows:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Invoice not found"}},
            status_code=404,
        )

    invoice = rows[0]
    quote_data = invoice.get("quotes") or {}
    if quote_data.get("organization_id") != org_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Invoice not found"}},
            status_code=404,
        )

    return invoice, None


# ============================================================================
# POST /api/invoices/{id}/download-xls
# ============================================================================


async def download_invoice_xls(request, id: str) -> Response:
    """Generate and download invoice as XLS, committing it as sent.

    Path: POST /api/invoices/{id}/download-xls
    Params:
        language: str (optional, default 'ru') — 'ru' or 'en' (query param or JSON body)
    Returns:
        Binary XLS file (Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
    Side Effects:
        - Writes invoice_letter_drafts row with method='xls_download', sent_at=NOW()
        - Updates invoices.sent_at
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _get_procurement_user(request)
    if err:
        return err

    invoice, err = _verify_invoice_ownership(id, user["org_id"])
    if err:
        return err

    # Parse language from query param or body
    language = request.query_params.get("language", "ru").strip().lower()
    if language not in ("ru", "en"):
        language = "ru"

    from services.xls_export_service import generate_invoice_xls
    from services.invoice_send_service import commit_invoice_send

    # TRANSACTIONAL: generate first, commit only on success
    try:
        xls_bytes = generate_invoice_xls(invoice_id=id, language=language)
    except Exception as e:
        logger.error("XLS generation failed for invoice %s: %s", id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "GENERATION_FAILED", "message": "Failed to generate XLS file"}},
            status_code=500,
        )

    # Commit the send record
    try:
        commit_invoice_send(
            invoice_id=id,
            user_id=user["id"],
            method="xls_download",
            language=language,
        )
    except Exception as e:
        logger.error("Failed to commit invoice send for %s: %s", id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "COMMIT_FAILED", "message": "File generated but failed to record send"}},
            status_code=500,
        )

    # Build filename: KP-{invoice_number}-{date}.xlsx
    invoice_number = invoice.get("invoice_number", id[:8])
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"KP-{invoice_number}-{date_str}.xlsx"

    return Response(
        content=xls_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ============================================================================
# GET /api/invoices/{id}/letter-draft
# ============================================================================


async def get_letter_draft(request, id: str) -> JSONResponse:
    """Fetch active (unsent) letter draft for an invoice.

    Path: GET /api/invoices/{id}/letter-draft
    Returns:
        200 with `data: <draft>` when an active draft exists, or
        200 with `data: null` when no active draft exists (per API contract).
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _get_procurement_user(request)
    if err:
        return err

    _, err = _verify_invoice_ownership(id, user["org_id"])
    if err:
        return err

    from services.invoice_send_service import get_active_draft

    draft = get_active_draft(id)
    return JSONResponse({"success": True, "data": draft}, status_code=200)


# ============================================================================
# POST /api/invoices/{id}/letter-draft
# ============================================================================


async def save_letter_draft(request, id: str) -> JSONResponse:
    """Create or update the active (unsent) draft for an invoice.

    Path: POST /api/invoices/{id}/letter-draft
    Params:
        recipient_email: str (optional)
        subject: str (optional)
        body_text: str (optional)
        language: str (optional, default 'ru')
    Returns:
        Saved draft object.
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _get_procurement_user(request)
    if err:
        return err

    _, err = _verify_invoice_ownership(id, user["org_id"])
    if err:
        return err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    from services.invoice_send_service import save_draft

    draft_data = {
        "recipient_email": body.get("recipient_email"),
        "subject": body.get("subject"),
        "body_text": body.get("body_text"),
        "language": body.get("language", "ru"),
    }

    draft = save_draft(invoice_id=id, user_id=user["id"], data=draft_data)

    return JSONResponse({"success": True, "data": draft}, status_code=200)


# ============================================================================
# POST /api/invoices/{id}/letter-draft/send
# ============================================================================


async def send_letter_draft(request, id: str) -> JSONResponse:
    """Mark the active letter draft as sent (commit).

    Path: POST /api/invoices/{id}/letter-draft/send
    Returns:
        Committed draft object.
    Side Effects:
        - Sets sent_at on the draft row
        - Updates invoices.sent_at (denormalized)
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _get_procurement_user(request)
    if err:
        return err

    _, err = _verify_invoice_ownership(id, user["org_id"])
    if err:
        return err

    from services.invoice_send_service import get_active_draft, commit_invoice_send

    draft = get_active_draft(id)
    if draft is None:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "No active draft to send"}},
            status_code=404,
        )

    committed = commit_invoice_send(
        invoice_id=id,
        user_id=user["id"],
        method="letter_draft",
        language=draft.get("language", "ru"),
        recipient_email=draft.get("recipient_email"),
        subject=draft.get("subject"),
        body_text=draft.get("body_text"),
    )

    # Delete the original unsent draft (now superseded by the committed row)
    sb = get_supabase()
    sb.table("invoice_letter_drafts").delete().eq("id", draft["id"]).execute()

    return JSONResponse({"success": True, "data": committed}, status_code=200)


# ============================================================================
# DELETE /api/invoices/{id}/letter-draft/{draft_id}
# ============================================================================


async def delete_letter_draft(request, id: str, draft_id: str) -> Response:
    """Delete an unsent draft.

    Path: DELETE /api/invoices/{id}/letter-draft/{draft_id}
    Returns:
        204 No Content on success.
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _get_procurement_user(request)
    if err:
        return err

    _, err = _verify_invoice_ownership(id, user["org_id"])
    if err:
        return err

    sb = get_supabase()

    # Verify draft exists, belongs to this invoice, and is unsent
    draft_result = (
        sb.table("invoice_letter_drafts")
        .select("id, invoice_id, sent_at")
        .eq("id", draft_id)
        .eq("invoice_id", id)
        .execute()
    )
    draft_rows = _rows(draft_result)
    if not draft_rows:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Draft not found"}},
            status_code=404,
        )

    if draft_rows[0].get("sent_at") is not None:
        return JSONResponse(
            {"success": False, "error": {"code": "ALREADY_SENT", "message": "Cannot delete a sent draft"}},
            status_code=400,
        )

    sb.table("invoice_letter_drafts").delete().eq("id", draft_id).execute()

    return Response(status_code=204)


# ============================================================================
# GET /api/invoices/{id}/letter-drafts/history
# ============================================================================


async def get_send_history(request, id: str) -> JSONResponse:
    """Fetch all sent drafts for an invoice (audit trail).

    Path: GET /api/invoices/{id}/letter-drafts/history
    Returns:
        List of sent draft rows, ordered by sent_at DESC.
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _get_procurement_user(request)
    if err:
        return err

    _, err = _verify_invoice_ownership(id, user["org_id"])
    if err:
        return err

    from services.invoice_send_service import get_send_history as fetch_history

    history = fetch_history(id)

    return JSONResponse({"success": True, "data": history}, status_code=200)


# ============================================================================
# POST /api/invoices/{id}/procurement-unlock-request
# ============================================================================


async def request_procurement_unlock(request, id: str) -> JSONResponse:
    """Request approval to edit an invoice whose parent quote is procurement-locked.

    Path: POST /api/invoices/{id}/procurement-unlock-request
    Params:
        reason: str (optional) — User's reason for the unlock request.
    Returns:
        List of created approval objects.
    Side Effects:
        - Creates approval requests for head_of_procurement and admin users
          with approval_type='edit_completed_procurement'.
    Roles: procurement, admin, head_of_procurement
    """
    user, err = _get_procurement_user(request)
    if err:
        return err

    invoice, err = _verify_invoice_ownership(id, user["org_id"])
    if err:
        return err

    # Procurement for the parent quote must be completed (locked) to need unlock approval
    from services.invoice_send_service import is_quote_procurement_locked

    if not is_quote_procurement_locked(id):
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_LOCKED", "message": "Procurement is still active — edit freely without approval"}},
            status_code=400,
        )

    # Parse optional reason
    user_reason = ""
    try:
        body = await request.json()
        user_reason = body.get("reason", "")
    except Exception:
        pass  # No body is acceptable — reason is optional

    from services.approval_service import create_approvals_for_role

    quote_id = invoice.get("quote_id")
    reason = f"Unlock procurement-completed invoice {id}"
    if user_reason:
        reason = f"{reason}: {user_reason}"

    approvals = create_approvals_for_role(
        quote_id=quote_id,
        organization_id=user["org_id"],
        requested_by=user["id"],
        reason=reason,
        role_codes=["head_of_procurement", "admin"],
        approval_type="edit_completed_procurement",
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "approvals_created": len(approvals),
                "approval_ids": [a.id for a in approvals],
            },
        },
        status_code=201,
    )
