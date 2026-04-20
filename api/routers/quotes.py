"""Quote-related /api/quotes/* endpoints.

Expanding in 6B-4 (procurement kanban) and 6B-6 (quote actions). Currently
hosts /api/quotes/search which delegates into the plan_fact module.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.plan_fact import quotes_search as _quotes_search

router = APIRouter(tags=["quotes"])


@router.get("/search")
async def get_quotes_search(request: Request) -> JSONResponse:
    """Search quotes for plan-fact UI."""
    return await _quotes_search(request)
