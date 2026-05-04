"""Customs /api/customs/* endpoints.

Thin wrapper over api.customs handlers. Mounted with prefix="/customs".
"""

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.customs import (
    attach_item_handler as _attach_item_handler,
    autofill_handler as _autofill_handler,
    bulk_update_items as _bulk_update_items,
    classify_handler as _classify_handler,
    classify_select_handler as _classify_select_handler,
    create_certificate_handler as _create_certificate_handler,
    delete_certificate_handler as _delete_certificate_handler,
    detach_item_handler as _detach_item_handler,
    history_certificate_handler as _history_certificate_handler,
    history_lookup_handler as _history_lookup_handler,
    list_certificates_handler as _list_certificates_handler,
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


# Phase B (customs-shared-certificates) Task 5 — certificates CRUD.
# Route ordering: most-specific paths come BEFORE generic paths (FastAPI
# matches in registration order). `/certificates/history` must precede
# `/certificates/{cert_id}`; `/certificates/{cert_id}/items/{item_id}` must
# precede `/certificates/{cert_id}` (FastAPI's path-converter would not
# accidentally match "history" as a cert_id, but explicit ordering keeps
# the surface easier to audit).


@router.get("/certificates/history")
async def get_certificates_history(request: Request) -> JSONResponse:
    """Find previous certificate by loose 2-of-3 match — see history_certificate_handler."""
    return await _history_certificate_handler(request)


@router.post("/certificates")
async def post_certificates(request: Request) -> JSONResponse:
    """Create cert + N attachments atomically — see create_certificate_handler."""
    return await _create_certificate_handler(request)


@router.get("/certificates")
async def get_certificates(request: Request) -> JSONResponse:
    """List certs (and custom expenses) for a quote — see list_certificates_handler."""
    return await _list_certificates_handler(request)


@router.post("/certificates/{cert_id}/items")
async def post_certificate_items(
    request: Request, cert_id: str
) -> JSONResponse:
    """Attach an item — see attach_item_handler."""
    return await _attach_item_handler(request, cert_id)


@router.delete("/certificates/{cert_id}/items/{item_id}")
async def delete_certificate_items(
    request: Request, cert_id: str, item_id: str
) -> JSONResponse:
    """Detach an item — see detach_item_handler."""
    return await _detach_item_handler(request, cert_id, item_id)


@router.delete("/certificates/{cert_id}")
async def delete_certificate(request: Request, cert_id: str) -> JSONResponse:
    """Cascade delete a certificate — see delete_certificate_handler."""
    return await _delete_certificate_handler(request, cert_id)


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
