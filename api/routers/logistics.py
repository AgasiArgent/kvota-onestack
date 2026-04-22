"""Logistics /api/logistics/* endpoints.

Thin wrapper over api.logistics handlers. Mounted with prefix="/logistics".
See api/logistics.py for business logic + docstrings.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.logistics import (
    acknowledge_review as _acknowledge_review,
    apply_template as _apply_template,
    complete as _complete,
    create_expense as _create_expense,
    create_segment as _create_segment,
    create_template as _create_template,
    delete_expense as _delete_expense,
    delete_segment as _delete_segment,
    delete_template as _delete_template,
    list_segments as _list_segments,
    list_templates as _list_templates,
    reorder_segments as _reorder_segments,
    update_segment as _update_segment,
    update_template as _update_template,
)

router = APIRouter(tags=["logistics"])


# Segments ------------------------------------------------------------------


@router.post("/segments")
async def post_segment(request: Request) -> JSONResponse:
    """Create a route segment on an invoice."""
    return await _create_segment(request)


@router.get("/segments")
async def get_segments(request: Request) -> JSONResponse:
    """List segments for an invoice."""
    return await _list_segments(request)


@router.patch("/segments/{segment_id}")
async def patch_segment(request: Request, segment_id: str) -> JSONResponse:
    """Update fields on a segment."""
    return await _update_segment(request, segment_id)


@router.delete("/segments/{segment_id}")
async def delete_segment_endpoint(
    request: Request, segment_id: str
) -> JSONResponse:
    """Delete a segment (cascades to expenses)."""
    return await _delete_segment(request, segment_id)


@router.post("/segments/reorder")
async def post_segments_reorder(request: Request) -> JSONResponse:
    """Set new sequence order for invoice segments (two-phase to avoid UNIQUE collisions)."""
    return await _reorder_segments(request)


# Expenses ------------------------------------------------------------------


@router.post("/expenses")
async def post_expense(request: Request) -> JSONResponse:
    """Add a freeform cost line to a segment."""
    return await _create_expense(request)


@router.delete("/expenses/{expense_id}")
async def delete_expense_endpoint(
    request: Request, expense_id: str
) -> JSONResponse:
    """Remove a segment expense."""
    return await _delete_expense(request, expense_id)


# Templates -----------------------------------------------------------------


@router.get("/templates")
async def get_templates(request: Request) -> JSONResponse:
    """List org route templates with their scaffold segments."""
    return await _list_templates(request)


@router.post("/templates")
async def post_template(request: Request) -> JSONResponse:
    """Create a reusable route template (scaffold)."""
    return await _create_template(request)


@router.patch("/templates/{template_id}")
async def patch_template(
    request: Request, template_id: str
) -> JSONResponse:
    """Replace template name/description/segments."""
    return await _update_template(request, template_id)


@router.delete("/templates/{template_id}")
async def delete_template_endpoint(
    request: Request, template_id: str
) -> JSONResponse:
    """Remove a route template (cascades to scaffold segments)."""
    return await _delete_template(request, template_id)


@router.post("/templates/{template_id}/apply")
async def post_template_apply(
    request: Request, template_id: str
) -> JSONResponse:
    """Materialize template scaffold into concrete invoice segments."""
    return await _apply_template(request, template_id)


# Workflow ------------------------------------------------------------------


@router.post("/complete")
async def post_complete(request: Request) -> JSONResponse:
    """Mark logistics pricing complete (blocked by pending review flag)."""
    return await _complete(request)


@router.post("/acknowledge-review")
async def post_acknowledge_review(request: Request) -> JSONResponse:
    """Clear the logistics_needs_review_since flag."""
    return await _acknowledge_review(request)
