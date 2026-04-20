"""Documents /api/documents/* endpoints.

Thin wrapper over api.documents handlers. Mounted with prefix="/documents".

Note: ``download_document`` returns an HTTP 302 RedirectResponse — DO NOT
convert to a JSON payload. Frontend ``<a href>`` tags rely on the browser
following the redirect to trigger downloads.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.documents import (
    delete_document_api as _delete_document,
    download_document as _download_document,
)

router = APIRouter(tags=["documents"])


@router.get("/{document_id}/download")
async def get_download(request: Request, document_id: str) -> Response:
    """Issue 302 redirect to the signed storage URL."""
    return await _download_document(request, document_id)


@router.delete("/{document_id}")
async def delete_doc(request: Request, document_id: str) -> JSONResponse:
    """Delete a document (storage + DB row). Requires procurement/admin role."""
    return await _delete_document(request, document_id)
