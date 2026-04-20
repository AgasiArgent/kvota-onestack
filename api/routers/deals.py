"""Deals /api/deals/* endpoints.

Currently hosts only POST /api/deals; subsequent GET/PATCH endpoints migrate
here as they're added.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.deals import create_deal as _create_deal

router = APIRouter(tags=["deals"])


@router.post("")
async def post_deals(request: Request) -> JSONResponse:
    """Create a deal from a confirmed specification."""
    return await _create_deal(request)
