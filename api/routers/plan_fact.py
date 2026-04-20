"""Plan-fact /api/plan-fact/* endpoints — categories and deal items CRUD.

Thin wrapper over api.plan_fact handlers. Mounted with prefix="/plan-fact".
Note: /api/quotes/search also originates from api/plan_fact.py but is
registered in api/routers/quotes.py because its path prefix differs.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.plan_fact import (
    plan_fact_create_item as _create_item,
    plan_fact_delete_item as _delete_item,
    plan_fact_list_categories as _list_categories,
    plan_fact_list_items as _list_items,
    plan_fact_update_item as _update_item,
)

router = APIRouter(tags=["plan-fact"])


@router.get("/categories")
async def get_categories(request: Request) -> JSONResponse:
    """List plan-fact categories."""
    return await _list_categories(request)


@router.get("/{deal_id}/items")
async def get_items(request: Request, deal_id: str) -> JSONResponse:
    """List plan-fact items for a deal."""
    return await _list_items(request, deal_id)


@router.post("/{deal_id}/items")
async def post_items(request: Request, deal_id: str) -> JSONResponse:
    """Create a plan-fact item on a deal."""
    return await _create_item(request, deal_id)


@router.patch("/{deal_id}/items/{id}")
async def patch_item(request: Request, deal_id: str, id: str) -> JSONResponse:
    """Update a plan-fact item on a deal."""
    return await _update_item(request, deal_id, id)


@router.delete("/{deal_id}/items/{id}")
async def delete_item(request: Request, deal_id: str, id: str) -> JSONResponse:
    """Delete a plan-fact item from a deal."""
    return await _delete_item(request, deal_id, id)
