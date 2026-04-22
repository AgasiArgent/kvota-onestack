"""Customs /api/customs/* endpoints.

Thin wrapper over api.customs handlers. Mounted with prefix="/customs".
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.customs import (
    autofill_handler as _autofill_handler,
    bulk_update_items as _bulk_update_items,
    create_item_expense as _create_item_expense,
    create_quote_expense as _create_quote_expense,
    delete_item_expense as _delete_item_expense,
    delete_quote_expense as _delete_quote_expense,
)

router = APIRouter(tags=["customs"])


@router.patch("/{quote_id}/items/bulk")
async def patch_items_bulk(request: Request, quote_id: str) -> JSONResponse:
    """Bulk update hs_code, customs_duty, and license fields on quote items."""
    return await _bulk_update_items(request, quote_id)


@router.post("/autofill")
async def post_autofill(request: Request) -> JSONResponse:
    """Return historical customs-field suggestions for given (brand, product_code) pairs."""
    return await _autofill_handler(request)


@router.post("/items/{item_id}/expenses")
async def post_item_expense(request: Request, item_id: str) -> JSONResponse:
    """Create a per-item customs expense (RUB)."""
    return await _create_item_expense(request, item_id)


@router.delete("/items/expenses/{expense_id}")
async def delete_item_expense_route(request: Request, expense_id: str) -> JSONResponse:
    """Delete a per-item customs expense."""
    return await _delete_item_expense(request, expense_id)


@router.post("/quotes/{quote_id}/expenses")
async def post_quote_expense(request: Request, quote_id: str) -> JSONResponse:
    """Create a per-quote customs overhead expense (RUB)."""
    return await _create_quote_expense(request, quote_id)


@router.delete("/quotes/expenses/{expense_id}")
async def delete_quote_expense_route(request: Request, expense_id: str) -> JSONResponse:
    """Delete a per-quote customs overhead expense."""
    return await _delete_quote_expense(request, expense_id)
