"""Invoice /api/invoices/* endpoints — send flow + procurement unlock request.

Thin wrapper over api.invoices handlers. Mounted with prefix="/invoices".
Return types vary: XLS download is binary Response, draft delete is 204,
rest are JSONResponse. Use `Response` from starlette as the generic type.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.composition import (
    approve_procurement_unlock as _approve_procurement_unlock,
    reject_procurement_unlock as _reject_procurement_unlock,
    verify_invoice as _verify_invoice,
)
from api.invoices import (
    delete_letter_draft as _delete_letter_draft,
    download_invoice_xls as _download_xls,
    get_letter_draft as _get_letter_draft,
    get_send_history as _get_send_history,
    request_procurement_unlock as _request_procurement_unlock,
    save_letter_draft as _save_letter_draft,
    send_letter_draft as _send_letter_draft,
)

router = APIRouter(tags=["invoices"])


@router.post("/{invoice_id}/download-xls")
async def post_download_xls(request: Request, invoice_id: str) -> Response:
    """Generate and download invoice as XLSX."""
    return await _download_xls(request, invoice_id)


@router.get("/{invoice_id}/letter-draft")
async def get_letter_draft(request: Request, invoice_id: str) -> JSONResponse:
    """Fetch current letter draft for invoice."""
    return await _get_letter_draft(request, invoice_id)


@router.post("/{invoice_id}/letter-draft")
async def post_letter_draft(request: Request, invoice_id: str) -> JSONResponse:
    """Save / update letter draft."""
    return await _save_letter_draft(request, invoice_id)


@router.post("/{invoice_id}/letter-draft/send")
async def post_letter_draft_send(request: Request, invoice_id: str) -> JSONResponse:
    """Send draft as email."""
    return await _send_letter_draft(request, invoice_id)


@router.delete("/{invoice_id}/letter-draft/{draft_id}", status_code=204)
async def delete_letter_draft(
    request: Request, invoice_id: str, draft_id: str
) -> Response:
    """Delete a specific letter draft; returns 204."""
    return await _delete_letter_draft(request, invoice_id, draft_id)


@router.get("/{invoice_id}/letter-drafts/history")
async def get_drafts_history(request: Request, invoice_id: str) -> JSONResponse:
    """Return send history for this invoice."""
    return await _get_send_history(request, invoice_id)


@router.post("/{invoice_id}/procurement-unlock-request")
async def post_procurement_unlock_request(
    request: Request, invoice_id: str
) -> JSONResponse:
    """Procurement lead requests unlock to edit a sent invoice."""
    return await _request_procurement_unlock(request, invoice_id)


@router.post("/{invoice_id}/verify")
async def post_verify(request: Request, invoice_id: str) -> JSONResponse:
    """Mark invoice as verified (composition verification step)."""
    return await _verify_invoice(request, invoice_id)


@router.post("/{invoice_id}/procurement-unlock-approval/{approval_id}/approve")
async def post_procurement_unlock_approve(
    request: Request, invoice_id: str, approval_id: str
) -> JSONResponse:
    """Approve a pending procurement-unlock request."""
    return await _approve_procurement_unlock(request, invoice_id, approval_id)


@router.post("/{invoice_id}/procurement-unlock-approval/{approval_id}/reject")
async def post_procurement_unlock_reject(
    request: Request, invoice_id: str, approval_id: str
) -> JSONResponse:
    """Reject a pending procurement-unlock request."""
    return await _reject_procurement_unlock(request, invoice_id, approval_id)
