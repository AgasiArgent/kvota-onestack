"""
Composition API endpoints for Phase 5b (Tasks 6 + 7).

GET  /api/quotes/{quote_id}/composition
POST /api/quotes/{quote_id}/composition
POST /api/invoices/{invoice_id}/verify
POST /api/invoices/{invoice_id}/edit-request
POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/approve
POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/reject

Auth: JWT via ApiAuthMiddleware (request.state.api_user). Mirrors the
plan_fact API pattern.

Access control:
  Composition reads/writes — sales, head_of_sales, procurement,
    procurement_senior, head_of_procurement, admin, quote_controller,
    spec_controller, finance, top_manager (org-boundary enforced).
  Invoice verify — procurement, procurement_senior, head_of_procurement, admin.
  Invoice edit-request — procurement, procurement_senior, head_of_procurement, admin.
  Approve/reject invoice edit — head_of_procurement, admin only.

The invoice edit-request flow uses the existing kvota.approvals table
with approval_type='invoice_edit' and a JSON diff stored in the
``modifications`` column. It does NOT route through
``approval_service.request_approval()`` which is hard-coded to the
quote → top_manager approval workflow — Phase 5b invoice edits need a
different target role and no quote status transition.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from starlette.responses import JSONResponse

from services.composition_service import (
    ConcurrencyError,
    ValidationError,
    apply_composition,
    freeze_composition,
    get_composition_view,
)
from services.database import get_supabase

logger = logging.getLogger(__name__)


# ============================================================================
# Role sets
# ============================================================================

# Roles that can read composition (broad audience — matches iip RLS SELECT)
COMPOSITION_READ_ROLES = {
    "admin",
    "top_manager",
    "procurement",
    "procurement_senior",
    "head_of_procurement",
    "sales",
    "head_of_sales",
    "finance",
    "quote_controller",
    "spec_controller",
}

# Roles that can write composition (pick suppliers per item). Same set as
# read because composition is a sales/procurement collaboration surface.
COMPOSITION_WRITE_ROLES = COMPOSITION_READ_ROLES

# Roles that can create/edit supplier invoices and mark them as verified
PROCUREMENT_ROLES = {
    "admin",
    "procurement",
    "procurement_senior",
    "head_of_procurement",
}

# Roles that can approve/reject edits to verified invoices
VERIFY_APPROVAL_ROLES = {"admin", "head_of_procurement"}


# ============================================================================
# Auth + access helpers (mirrors api/plan_fact.py conventions)
# ============================================================================

def _get_api_user(request):
    """Extract authenticated user from JWT middleware state.

    Returns (user_dict, error_response). On failure, error_response is a
    JSONResponse ready to return to the client.
    """
    api_user = getattr(request.state, "api_user", None)
    if not api_user:
        return None, JSONResponse(
            {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication required"}},
            status_code=401,
        )

    user_meta = api_user.user_metadata or {}
    org_id = user_meta.get("org_id")

    # Fallback: look up org_id from user_roles if not in JWT metadata
    if not org_id:
        sb = get_supabase()
        ur = (
            sb.table("user_roles")
            .select("organization_id")
            .eq("user_id", str(api_user.id))
            .limit(1)
            .execute()
        )
        if ur.data:
            row = ur.data[0]
            org_id = row["organization_id"] if isinstance(row, dict) else None

    if not org_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "User has no organization"}},
            status_code=403,
        )

    return {
        "id": str(api_user.id),
        "email": api_user.email or "",
        "org_id": org_id,
    }, None


def _get_user_roles(user_id: str, org_id: str) -> set[str]:
    """Fetch user's role slugs from user_roles table."""
    sb = get_supabase()
    result = (
        sb.table("user_roles")
        .select("roles!inner(slug)")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .execute()
    )
    roles: set[str] = set()
    for row in result.data or []:
        role_data = row.get("roles")
        if isinstance(role_data, dict):
            slug = role_data.get("slug")
            if slug:
                roles.add(slug)
    return roles


def _check_roles(user_roles: set[str], required: set[str], message: str = "Access denied"):
    """Return error response if user lacks any of the required roles, else None."""
    if not user_roles.intersection(required):
        return JSONResponse(
            {"success": False, "error": {"code": "INSUFFICIENT_PERMISSIONS", "message": message}},
            status_code=403,
        )
    return None


def _verify_quote_org(quote_id: str, org_id: str):
    """Verify quote exists and belongs to user's org.

    Returns (quote_row, error_response). 404 on denial per access-control.md
    "404 on denial" rule — never leak existence cross-org.
    """
    sb = get_supabase()
    try:
        result = (
            sb.table("quotes")
            .select("id, organization_id, updated_at")
            .eq("id", quote_id)
            .execute()
        )
    except Exception:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )

    if not result.data:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )

    quote = result.data[0]
    if quote["organization_id"] != org_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )

    return quote, None


def _verify_invoice_org(invoice_id: str, org_id: str):
    """Verify invoice exists and belongs to user's org (via its parent quote).

    Returns (invoice_row, error_response). 404 on denial.
    """
    sb = get_supabase()
    try:
        result = (
            sb.table("invoices")
            .select("id, quote_id, supplier_id, verified_at, verified_by, status, "
                    "quotes!quote_id(id, organization_id)")
            .eq("id", invoice_id)
            .execute()
        )
    except Exception:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Invoice not found"}},
            status_code=404,
        )

    if not result.data:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Invoice not found"}},
            status_code=404,
        )

    invoice = result.data[0]
    quote = (invoice.get("quotes") or {})
    if quote.get("organization_id") != org_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Invoice not found"}},
            status_code=404,
        )

    return invoice, None


def _authenticate_and_load_roles(request):
    """Combined auth step: JWT → user dict → role set.

    Returns (user_dict, user_roles_set, error_response).
    """
    user, err = _get_api_user(request)
    if err:
        return None, None, err
    roles = _get_user_roles(user["id"], user["org_id"])
    return user, roles, None


# ============================================================================
# Task 6 — GET /api/quotes/{quote_id}/composition
# ============================================================================

async def get_composition(request, quote_id: str) -> JSONResponse:
    """Return composition state with alternatives for the CalculationStep picker.

    Path: GET /api/quotes/{quote_id}/composition

    Params:
        quote_id: str (required, path) — Quote UUID.

    Returns:
        quote_id: str
        items: List[{quote_item_id, brand, sku, name, quantity,
                      selected_invoice_id, alternatives: [...]}]
        composition_complete: bool — True iff every item has a selection.
        can_edit: bool — Whether the current user's roles allow POST.

    Errors:
        401 UNAUTHORIZED — no JWT
        403 INSUFFICIENT_PERMISSIONS — role not in COMPOSITION_READ_ROLES
        404 NOT_FOUND — quote not visible to user (cross-org or missing)

    Roles: sales, head_of_sales, procurement, procurement_senior,
        head_of_procurement, admin, top_manager, finance, quote_controller,
        spec_controller
    """
    user, user_roles, err = _authenticate_and_load_roles(request)
    if err:
        return err

    role_err = _check_roles(user_roles, COMPOSITION_READ_ROLES)
    if role_err:
        return role_err

    _, org_err = _verify_quote_org(quote_id, user["org_id"])
    if org_err:
        return org_err

    sb = get_supabase()
    try:
        view = get_composition_view(quote_id, sb, user_id=user["id"])
    except Exception as e:
        logger.error("Failed to load composition view for quote %s: %s", quote_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to load composition"}},
            status_code=500,
        )

    view["can_edit"] = bool(user_roles.intersection(COMPOSITION_WRITE_ROLES))

    return JSONResponse({"success": True, "data": view}, status_code=200)


# ============================================================================
# Task 6 — POST /api/quotes/{quote_id}/composition
# ============================================================================

async def apply_composition_endpoint(request, quote_id: str) -> JSONResponse:
    """Persist per-item supplier selection for the quote.

    Path: POST /api/quotes/{quote_id}/composition

    Params (JSON body):
        selection: Dict[quote_item_id, invoice_id] (required)
        quote_updated_at: str (optional) — ISO timestamp for optimistic
            concurrency check. When omitted, the check is skipped.

    Returns:
        quote_id: str
        composition_complete: bool — True iff every item now has a selection.

    Errors:
        400 BAD_REQUEST          — malformed JSON body
        400 VALIDATION_ERROR     — selection is missing or non-dict
        400 COMPOSITION_INVALID_SELECTION — (quote_item, invoice) pair has no iip row
        401 UNAUTHORIZED         — no JWT
        403 INSUFFICIENT_PERMISSIONS — role not in COMPOSITION_WRITE_ROLES
        404 NOT_FOUND            — quote not visible
        409 STALE_QUOTE          — quote_updated_at doesn't match current value

    Side Effects:
        Updates quote_items.composition_selected_invoice_id for affected items.
        Bumps quotes.updated_at.

    Roles: sales, head_of_sales, procurement, procurement_senior,
        head_of_procurement, admin, top_manager, finance, quote_controller,
        spec_controller
    """
    user, user_roles, err = _authenticate_and_load_roles(request)
    if err:
        return err

    role_err = _check_roles(user_roles, COMPOSITION_WRITE_ROLES)
    if role_err:
        return role_err

    _, org_err = _verify_quote_org(quote_id, user["org_id"])
    if org_err:
        return org_err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    selection = body.get("selection")
    if not isinstance(selection, dict):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "selection must be a dict of quote_item_id -> invoice_id"}},
            status_code=400,
        )
    quote_updated_at = body.get("quote_updated_at")  # optional

    sb = get_supabase()
    try:
        apply_composition(
            quote_id=quote_id,
            selection_map=selection,
            supabase=sb,
            user_id=user["id"],
            quote_updated_at=quote_updated_at,
        )
    except ValidationError as ve:
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "COMPOSITION_INVALID_SELECTION",
                    "message": str(ve),
                    "fields": ve.errors,
                },
            },
            status_code=400,
        )
    except ConcurrencyError as ce:
        return JSONResponse(
            {"success": False, "error": {"code": "STALE_QUOTE", "message": str(ce)}},
            status_code=409,
        )
    except Exception as e:
        logger.error("apply_composition failed for quote %s: %s", quote_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to apply composition"}},
            status_code=500,
        )

    # Reload composition_complete flag after the update
    try:
        view_after = get_composition_view(quote_id, sb, user_id=user["id"])
        composition_complete = bool(view_after.get("composition_complete", False))
    except Exception:
        composition_complete = False

    return JSONResponse(
        {"success": True, "data": {"quote_id": quote_id, "composition_complete": composition_complete}},
        status_code=200,
    )


# ============================================================================
# Task 7 — POST /api/invoices/{invoice_id}/verify
# ============================================================================

async def verify_invoice(request, invoice_id: str) -> JSONResponse:
    """Mark a supplier invoice as verified (ready for composition).

    Path: POST /api/invoices/{invoice_id}/verify

    Returns:
        invoice_id: str
        verified_at: ISO timestamp
        verified_by: user_id

    Errors:
        401 UNAUTHORIZED
        403 INSUFFICIENT_PERMISSIONS — role not in PROCUREMENT_ROLES
        404 NOT_FOUND — invoice not visible

    Side Effects:
        Sets invoices.verified_at = now(), invoices.verified_by = current_user.

    Roles: procurement, procurement_senior, head_of_procurement, admin
    """
    user, user_roles, err = _authenticate_and_load_roles(request)
    if err:
        return err

    role_err = _check_roles(user_roles, PROCUREMENT_ROLES)
    if role_err:
        return role_err

    _, org_err = _verify_invoice_org(invoice_id, user["org_id"])
    if org_err:
        return org_err

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        sb.table("invoices").update({
            "verified_at": now_iso,
            "verified_by": user["id"],
        }).eq("id", invoice_id).execute()
    except Exception as e:
        logger.error("Failed to verify invoice %s: %s", invoice_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to verify invoice"}},
            status_code=500,
        )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "invoice_id": invoice_id,
                "verified_at": now_iso,
                "verified_by": user["id"],
            },
        },
        status_code=200,
    )


# ============================================================================
# Task 7 — POST /api/invoices/{invoice_id}/edit-request
# ============================================================================

async def request_invoice_edit(request, invoice_id: str) -> JSONResponse:
    """Request head_of_procurement approval to edit a verified invoice.

    Path: POST /api/invoices/{invoice_id}/edit-request

    Params (JSON body):
        proposed_changes: Dict[str, dict] (required) — Per-field diff
            {"field_name": {"old": <value>, "new": <value>}, ...}
        reason: str (required, min 10 chars) — Justification for the edit.

    Returns:
        approval_id: str — Created row in kvota.approvals
        status: "pending"

    Side Effects:
        Creates a kvota.approvals row with:
          approval_type = 'invoice_edit'
          quote_id = invoice.quote_id (approvals table is keyed on quote_id;
            the invoice_id is stored in modifications.invoice_id for lookup)
          modifications = { "invoice_id": ..., "diff": ..., "reason": ... }
          status = 'pending'

    Errors:
        400 VALIDATION_ERROR     — missing proposed_changes or reason
        401 UNAUTHORIZED
        403 INSUFFICIENT_PERMISSIONS
        404 NOT_FOUND            — invoice not visible
        409 INVOICE_NOT_VERIFIED — invoice.verified_at IS NULL (no approval
            needed for unverified invoices — edit them directly)

    Roles: procurement, procurement_senior, head_of_procurement, admin
    """
    user, user_roles, err = _authenticate_and_load_roles(request)
    if err:
        return err

    role_err = _check_roles(user_roles, PROCUREMENT_ROLES)
    if role_err:
        return role_err

    invoice, org_err = _verify_invoice_org(invoice_id, user["org_id"])
    if org_err:
        return org_err

    if not invoice.get("verified_at"):
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "INVOICE_NOT_VERIFIED",
                    "message": "Invoice is not in verified state — edit it directly",
                },
            },
            status_code=409,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    proposed_changes = body.get("proposed_changes")
    reason = body.get("reason")

    if not isinstance(proposed_changes, dict) or not proposed_changes:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "proposed_changes must be a non-empty dict"}},
            status_code=400,
        )
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "reason must be at least 10 characters"}},
            status_code=400,
        )

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    approval_payload = {
        "quote_id": invoice["quote_id"],
        "requested_by": user["id"],
        "approval_type": "invoice_edit",
        "reason": reason.strip(),
        "status": "pending",
        "requested_at": now_iso,
        "modifications": {
            "invoice_id": invoice_id,
            "diff": proposed_changes,
            "reason": reason.strip(),
        },
    }

    try:
        result = sb.table("approvals").insert(approval_payload).execute()
    except Exception as e:
        logger.error("Failed to create invoice-edit approval for %s: %s", invoice_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to create approval"}},
            status_code=500,
        )

    if not result.data:
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Approval insert returned no data"}},
            status_code=500,
        )

    approval_id = result.data[0]["id"]

    logger.info(
        "Invoice-edit approval requested: approval_id=%s invoice_id=%s requester=%s",
        approval_id, invoice_id, user["id"],
    )

    return JSONResponse(
        {"success": True, "data": {"approval_id": approval_id, "status": "pending"}},
        status_code=201,
    )


# ============================================================================
# Task 7 — POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/approve
# ============================================================================

async def approve_invoice_edit(request, invoice_id: str, approval_id: str) -> JSONResponse:
    """Approve a pending invoice edit request and apply the diff.

    Path: POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/approve

    Returns:
        approval_id: str
        status: "approved"
        applied_changes: Dict[str, <new_value>] — fields that were updated

    Side Effects:
        Reads modifications.diff from the approval row and applies the
        new values to the invoices table. Marks the approval row as
        approved with decided_at = now(), approver_id = current_user.

    Errors:
        401 UNAUTHORIZED
        403 INSUFFICIENT_PERMISSIONS — role not in VERIFY_APPROVAL_ROLES
        404 NOT_FOUND — approval not found, already processed, or not
            targeting this invoice

    Roles: head_of_procurement, admin
    """
    user, user_roles, err = _authenticate_and_load_roles(request)
    if err:
        return err

    role_err = _check_roles(user_roles, VERIFY_APPROVAL_ROLES, message="Only head_of_procurement or admin may approve invoice edits")
    if role_err:
        return role_err

    # Verify invoice belongs to user's org
    _, org_err = _verify_invoice_org(invoice_id, user["org_id"])
    if org_err:
        return org_err

    approval_row, err = _fetch_pending_invoice_edit_approval(approval_id, invoice_id)
    if err:
        return err

    diff = (approval_row.get("modifications") or {}).get("diff") or {}
    new_values: dict = {}
    for field_name, change in diff.items():
        if isinstance(change, dict) and "new" in change:
            new_values[field_name] = change["new"]

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Apply diff to invoice
    if new_values:
        try:
            sb.table("invoices").update(new_values).eq("id", invoice_id).execute()
        except Exception as e:
            logger.error("Failed to apply invoice-edit diff to %s: %s", invoice_id, e)
            return JSONResponse(
                {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to apply approved changes"}},
                status_code=500,
            )

    # Mark approval as approved
    try:
        sb.table("approvals").update({
            "status": "approved",
            "approver_id": user["id"],
            "decided_at": now_iso,
        }).eq("id", approval_id).execute()
    except Exception as e:
        logger.error("Failed to mark approval %s as approved: %s", approval_id, e)
        # The invoice change already went through — log and surface error.
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Approved changes applied but failed to update approval status"}},
            status_code=500,
        )

    logger.info(
        "Invoice-edit approval approved: approval_id=%s invoice_id=%s approver=%s fields=%d",
        approval_id, invoice_id, user["id"], len(new_values),
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "approval_id": approval_id,
                "status": "approved",
                "applied_changes": new_values,
            },
        },
        status_code=200,
    )


# ============================================================================
# Task 7 — POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/reject
# ============================================================================

async def reject_invoice_edit(request, invoice_id: str, approval_id: str) -> JSONResponse:
    """Reject a pending invoice edit request.

    Path: POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/reject

    Params (JSON body, optional):
        decision_comment: str — Rejector's reason.

    Returns:
        approval_id: str
        status: "rejected"

    Side Effects:
        Marks the approval row as rejected with decided_at = now().
        No changes to the invoice.

    Errors:
        401 UNAUTHORIZED
        403 INSUFFICIENT_PERMISSIONS
        404 NOT_FOUND

    Roles: head_of_procurement, admin
    """
    user, user_roles, err = _authenticate_and_load_roles(request)
    if err:
        return err

    role_err = _check_roles(user_roles, VERIFY_APPROVAL_ROLES, message="Only head_of_procurement or admin may reject invoice edits")
    if role_err:
        return role_err

    _, org_err = _verify_invoice_org(invoice_id, user["org_id"])
    if org_err:
        return org_err

    approval_row, err = _fetch_pending_invoice_edit_approval(approval_id, invoice_id)
    if err:
        return err

    # Optional decision comment from body
    decision_comment: Optional[str] = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            comment = body.get("decision_comment")
            if isinstance(comment, str):
                decision_comment = comment.strip() or None
    except Exception:
        pass  # body is optional for reject

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        update_fields = {
            "status": "rejected",
            "approver_id": user["id"],
            "decided_at": now_iso,
        }
        if decision_comment:
            update_fields["decision_comment"] = decision_comment
        sb.table("approvals").update(update_fields).eq("id", approval_id).execute()
    except Exception as e:
        logger.error("Failed to reject approval %s: %s", approval_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to reject approval"}},
            status_code=500,
        )

    logger.info(
        "Invoice-edit approval rejected: approval_id=%s invoice_id=%s rejector=%s",
        approval_id, invoice_id, user["id"],
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "approval_id": approval_id,
                "status": "rejected",
            },
        },
        status_code=200,
    )


# ============================================================================
# Internal helper shared by approve/reject
# ============================================================================

def _fetch_pending_invoice_edit_approval(approval_id: str, invoice_id: str):
    """Load an approval row, verify it is pending and targets this invoice.

    Returns (approval_row_dict, error_response). On any mismatch returns
    404 to avoid leaking approval existence cross-boundary.
    """
    sb = get_supabase()
    try:
        result = (
            sb.table("approvals")
            .select("id, approval_type, status, modifications")
            .eq("id", approval_id)
            .execute()
        )
    except Exception:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Approval not found"}},
            status_code=404,
        )

    if not result.data:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Approval not found"}},
            status_code=404,
        )

    row = result.data[0]
    if row.get("approval_type") != "invoice_edit":
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Approval not found"}},
            status_code=404,
        )
    if row.get("status") != "pending":
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Approval already processed"}},
            status_code=404,
        )
    modifications = row.get("modifications") or {}
    if modifications.get("invoice_id") != invoice_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Approval does not target this invoice"}},
            status_code=404,
        )

    return row, None
