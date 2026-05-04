"""Customs /api/customs/* endpoints.

Thin wrapper over api.customs handlers. Mounted with prefix="/customs".
"""

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.customs import (
    autofill_handler as _autofill_handler,
    bulk_update_items as _bulk_update_items,
    classify_handler as _classify_handler,
    classify_select_handler as _classify_select_handler,
    create_item_expense as _create_item_expense,
    create_quote_expense as _create_quote_expense,
    delete_item_expense as _delete_item_expense,
    delete_quote_expense as _delete_quote_expense,
    history_lookup_handler as _history_lookup_handler,
    non_tariff_measures_handler as _non_tariff_measures_handler,
    resolve_rates_handler as _resolve_rates_handler,
)
from services.alta_client import AltaClient, get_alta_client

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


# REQ-5 customs-phase-1 — resolve-rates + non-tariff-measures
# Both endpoints inject ``services.alta_client.AltaClient`` via ``Depends``
# so tests can override with ``app.dependency_overrides`` (decisions Q6).


@router.post("/resolve-rates")
async def post_resolve_rates(
    request: Request,
    alta_client: AltaClient = Depends(get_alta_client),
) -> JSONResponse:
    """Resolve customs rates for a tnved+country+date — see resolve_rates_handler."""
    return await _resolve_rates_handler(request, alta_client)


@router.post("/non-tariff-measures")
async def post_non_tariff_measures(
    request: Request,
    alta_client: AltaClient = Depends(get_alta_client),
) -> JSONResponse:
    """Fetch non-tariff regulation measures — see non_tariff_measures_handler."""
    return await _non_tariff_measures_handler(request, alta_client)


# Phase 2 — TN ВЭД classification by product name (Alta Express)


@router.post("/classify")
async def post_classify(
    request: Request,
    alta_client: AltaClient = Depends(get_alta_client),
) -> JSONResponse:
    """Classify product names → TN ВЭД codes — see classify_handler."""
    return await _classify_handler(request, alta_client)


@router.post("/classify/select")
async def post_classify_select(request: Request) -> JSONResponse:
    """Record customs-specialist's chosen code — see classify_select_handler."""
    return await _classify_select_handler(request)


# Phase A Req 10 — history lookup for repeating (org, tnved_code, country)


@router.get("/items/history")
async def get_items_history(
    request: Request,
    tnved_code: str,
    country_oksm: int,
) -> JSONResponse:
    """Find last customs choice for repeating (org, code, country) — see history_lookup_handler."""
    return await _history_lookup_handler(request, tnved_code, country_oksm)
