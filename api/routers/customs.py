"""Customs /api/customs/* endpoints.

Thin wrapper over api.customs handlers. Mounted with prefix="/customs".
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.customs import bulk_update_items as _bulk_update_items

router = APIRouter(tags=["customs"])


@router.patch("/{quote_id}/items/bulk")
async def patch_items_bulk(request: Request, quote_id: str) -> JSONResponse:
    """Bulk update hs_code, customs_duty, and license fields on quote items."""
    return await _bulk_update_items(request, quote_id)
