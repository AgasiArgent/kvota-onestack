"""Quote-related /api/quotes/* endpoints.

Expanded in 6B-4 to cover procurement kanban + substatus workflow and
quote composition (multi-supplier). Expanded in 6B-5 with admin-only
soft-delete / restore (entity lifecycle). 6B-6a adds the calculate
endpoint (recalc pipeline). Grows further in 6B-6b (remaining quote
actions: submit-procurement, cancel, workflow transition).

Route order matters: FastAPI matches routes in registration order within a
router. Static paths (``/search``, ``/kanban``) MUST be declared BEFORE any
parameterized ``/{quote_id}/*`` route or they would be captured by the
path variable.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.composition import (
    apply_composition_endpoint as _apply_composition,
    get_composition as _get_composition,
)
from api.plan_fact import quotes_search as _quotes_search
from api.procurement import (
    get_kanban as _get_kanban,
    get_status_history as _get_status_history,
    post_substatus as _post_substatus,
)
from api.quotes import calculate_quote as _calculate_quote
from api.soft_delete import (
    restore_quote as _restore_quote,
    soft_delete_quote as _soft_delete_quote,
)

router = APIRouter(tags=["quotes"])


# --- Static paths (must precede parameterized routes) ---


@router.get("/search")
async def get_quotes_search(request: Request) -> JSONResponse:
    """Search quotes for plan-fact UI."""
    return await _quotes_search(request)


@router.get("/kanban")
async def get_kanban(request: Request) -> JSONResponse:
    """Return (quote, brand) cards grouped by procurement_substatus."""
    return await _get_kanban(request)


# --- Parameterized paths ---


@router.post("/{quote_id}/substatus")
async def post_substatus(request: Request, quote_id: str) -> JSONResponse:
    """Transition a (quote, brand) procurement sub-status."""
    return await _post_substatus(request, quote_id)


@router.get("/{quote_id}/status-history")
async def get_status_history(request: Request, quote_id: str) -> JSONResponse:
    """Return full audit log of status/substatus transitions for a quote."""
    return await _get_status_history(request, quote_id)


@router.get("/{quote_id}/composition")
async def get_composition(request: Request, quote_id: str) -> JSONResponse:
    """Fetch current multi-supplier composition for a quote."""
    return await _get_composition(request, quote_id)


@router.post("/{quote_id}/composition")
async def post_composition(request: Request, quote_id: str) -> JSONResponse:
    """Apply (validate + persist) a composition plan for a quote."""
    return await _apply_composition(request, quote_id)


@router.post("/{quote_id}/soft-delete")
async def post_soft_delete(request: Request, quote_id: str) -> JSONResponse:
    """Admin-only soft-delete of a quote (cascades to spec + deal)."""
    return await _soft_delete_quote(request, quote_id)


@router.post("/{quote_id}/restore")
async def post_restore(request: Request, quote_id: str) -> JSONResponse:
    """Admin-only restore of a previously soft-deleted quote."""
    return await _restore_quote(request, quote_id)


@router.post("/{quote_id}/calculate")
async def post_calculate(request: Request, quote_id: str) -> JSONResponse:
    """Recalculate totals for a quote. Delegates to api.quotes.calculate_quote.

    Dual auth: JWT (Next.js) first, then legacy session (FastHTML) via
    ``request.session`` (provided by Starlette's SessionMiddleware).
    """
    return await _calculate_quote(request, quote_id)
