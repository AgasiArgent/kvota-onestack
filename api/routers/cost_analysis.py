"""APIRouter wrapper for the cost-analysis JSON endpoint.

Registered in ``api/app.py`` with ``prefix="/quotes"`` so the full path is
``/api/quotes/{quote_id}/cost-analysis``. Kept in its own router module so
the handler stays isolated from the wider ``quotes`` router (which deals
with workflow mutations).
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.cost_analysis import get_cost_analysis as _get_cost_analysis

router = APIRouter(tags=["cost-analysis"])


@router.get("/{quote_id}/cost-analysis")
async def get_quote_cost_analysis(
    request: Request, quote_id: str
) -> JSONResponse:
    """Return P&L waterfall data for a quote.

    Path: GET /api/quotes/{quote_id}/cost-analysis
    Auth: Bearer JWT required.
    Roles: finance, top_manager, admin, quote_controller.
    """
    return await _get_cost_analysis(request, quote_id)
