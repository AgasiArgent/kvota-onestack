"""Quote-related /api/quotes/* endpoints.

Expanded in 6B-4 to cover procurement kanban + substatus workflow and
quote composition (multi-supplier). Expanded in 6B-5 with admin-only
soft-delete / restore (entity lifecycle). 6B-6a adds the calculate
endpoint (recalc pipeline). 6B-6b adds the remaining quote actions:
submit-procurement, cancel, and workflow transition.

Route order matters: FastAPI matches routes in registration order within a
router. Static paths (``/search``, ``/kanban``) MUST be declared BEFORE any
parameterized ``/{quote_id}/*`` route or they would be captured by the
path variable.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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
from api.customs import (
    refresh_customs_snapshot_handler as _refresh_customs_snapshot,
)
from api.calc_step_info import get_calc_step_info as _get_calc_step_info
from api.quotes import (
    calculate_quote as _calculate_quote,
    cancel_quote as _cancel_quote,
    export_validation as _export_validation,
    submit_procurement as _submit_procurement,
    transition_workflow as _transition_workflow,
)
from fastapi import Depends
from services.alta_client import AltaClient, get_alta_client
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


@router.post("/{quote_id}/submit-procurement")
async def post_submit_procurement(
    request: Request, quote_id: str
) -> JSONResponse:
    """Submit a draft quote for procurement evaluation with sales checklist."""
    return await _submit_procurement(request, quote_id)


@router.post("/{quote_id}/cancel")
async def post_cancel(request: Request, quote_id: str) -> JSONResponse:
    """Cancel a quote with mandatory reason (sales/admin only)."""
    return await _cancel_quote(request, quote_id)


@router.post("/{quote_id}/workflow/transition")
async def post_workflow_transition(
    request: Request, quote_id: str
) -> JSONResponse:
    """Execute a workflow status transition (to_status or action)."""
    return await _transition_workflow(request, quote_id)


@router.post("/{quote_id}/refresh-customs-snapshot")
async def post_refresh_customs_snapshot(
    request: Request,
    quote_id: str,
    alta_client: AltaClient = Depends(get_alta_client),
) -> JSONResponse:
    """Re-fetch and replace the customs rate snapshot on the latest quote_version.

    REQ-8 explicit "Пересчитать по текущим ставкам" trigger. Three-tier
    fallback (Q4): live → 30-day cache → 409 FREEZE_ABORTED. Customs roles only.
    """
    return await _refresh_customs_snapshot(request, quote_id, alta_client)


@router.get("/{quote_id}/calc-step-info")
async def get_calc_step_info_route(
    request: Request, quote_id: str
) -> JSONResponse:
    """Return per-invoice logistics + per-item customs + certifications.

    Powers the calc-step info card (Testing 2 rows 36 + 48). Read-only.
    Dual auth: JWT (Next.js) first, then legacy session (FastHTML).
    """
    return await _get_calc_step_info(request, quote_id)


@router.get("/{quote_id}/export/validation")
async def get_export_validation(
    request: Request, quote_id: str
) -> Response:
    """Download validation Excel (.xlsm) for a quote.

    Replaces the archived FastHTML route
    ``/quotes/{quote_id}/export/validation`` (Phase 6C-2B-Mega-C, 2026-04-20).
    Dual auth: JWT (Next.js) first, then legacy session (FastHTML).
    """
    return await _export_validation(request, quote_id)
