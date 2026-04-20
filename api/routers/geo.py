"""Geo /api/geo/* endpoints — VAT rate lookup + city autocomplete.

Thin wrapper over api.geo handlers. Mounted with prefix="/geo" (full path:
/api/geo/...). Paths live here instead of at handler definition sites so
api.geo stays as a pure handler module that existing tests import from
directly.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.geo import (
    get_cities_search as _get_cities_search,
    get_vat_rate as _get_vat_rate,
)

router = APIRouter(tags=["geo"])


@router.get("/vat-rate")
async def get_vat_rate(request: Request) -> JSONResponse:
    """Fetch VAT rate for a country. Used by Next.js invoice forms."""
    return await _get_vat_rate(request)


@router.get("/cities/search")
async def get_cities_search(request: Request) -> JSONResponse:
    """City autocomplete via HERE Geocoding API."""
    return await _get_cities_search(request)
