"""
Geo API endpoints — VAT rate lookup and admin CRUD.

GET /api/geo/vat-rate   — Lookup VAT rate for a country
PUT /api/admin/vat-rates — Admin-only rate upsert

Auth: JWT via ApiAuthMiddleware (request.state.api_user) OR
      legacy session cookie (dual auth during strangler fig migration).
"""

import logging
import re
from typing import Any

from starlette.responses import JSONResponse

from services.database import get_supabase

logger = logging.getLogger(__name__)

# ISO 3166-1 alpha-2: exactly 2 ASCII letters
_COUNTRY_CODE_RE = re.compile(r"^[A-Za-z]{2}$")

_PROCUREMENT_ROLES = {"procurement", "admin", "head_of_procurement"}


def _rows(response: Any) -> list[dict[str, Any]]:
    """Extract typed rows from Supabase response."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _get_authenticated_user(request) -> tuple[dict | None, JSONResponse | None]:
    """Dual auth: JWT first, reject if neither JWT nor session.

    Returns (user_dict, None) on success or (None, error_response).
    user_dict contains: id, org_id, role_slugs.
    """
    api_user = getattr(request.state, "api_user", None)
    if not api_user:
        return None, JSONResponse(
            {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication required"}},
            status_code=401,
        )

    user_id = str(api_user.id)
    sb = get_supabase()

    # Resolve org_id
    om = (
        sb.table("organization_members")
        .select("organization_id")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    om_rows = _rows(om)
    if not om_rows:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "User has no active organization"}},
            status_code=403,
        )

    org_id: str = str(om_rows[0].get("organization_id", ""))

    # Resolve role slugs
    roles_result = (
        sb.table("user_roles")
        .select("roles!inner(slug)")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .execute()
    )
    role_slugs: set[str] = set()
    for row in _rows(roles_result):
        role_data = row.get("roles")
        if isinstance(role_data, dict) and role_data.get("slug"):
            role_slugs.add(str(role_data["slug"]))

    return {
        "id": user_id,
        "org_id": org_id,
        "role_slugs": role_slugs,
    }, None


# ============================================================================
# GET /api/geo/vat-rate
# ============================================================================


async def get_vat_rate(request) -> JSONResponse:
    """Get VAT rate for a country.

    Path: GET /api/geo/vat-rate
    Params:
        country_code: str (required) — ISO 3166-1 alpha-2 (query param)
    Returns:
        country_code: str
        rate: float — VAT rate percentage (e.g., 20.00)
    Roles: any authenticated user
    """
    # Auth
    user, err = _get_authenticated_user(request)
    if err:
        return err

    # Validate country_code
    country_code = request.query_params.get("country_code", "").strip()
    if not country_code:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "country_code query parameter is required"}},
            status_code=400,
        )
    if not _COUNTRY_CODE_RE.match(country_code):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "country_code must be a valid ISO 3166-1 alpha-2 code (2 letters)"}},
            status_code=400,
        )

    from services.vat_service import get_vat_rate as lookup_vat_rate

    rate = lookup_vat_rate(country_code)

    return JSONResponse(
        {
            "success": True,
            "data": {
                "country_code": country_code.upper(),
                "rate": float(rate),
            },
        },
        status_code=200,
    )


# ============================================================================
# PUT /api/admin/vat-rates
# ============================================================================


async def update_vat_rate(request) -> JSONResponse:
    """Update VAT rate for a country.

    Path: PUT /api/admin/vat-rates
    Params:
        country_code: str (required) — ISO 3166-1 alpha-2
        rate: float (required) — 0.00 to 100.00
        notes: str (optional)
    Returns:
        country_code: str
        rate: float
        updated_at: str
    Roles: admin
    """
    # Auth — admin only
    user, err = _get_authenticated_user(request)
    if err:
        return err

    if "admin" not in user["role_slugs"]:
        return JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Admin role required"}},
            status_code=403,
        )

    # Parse body
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    country_code = (body.get("country_code") or "").strip()
    rate_raw = body.get("rate")
    notes = body.get("notes")

    # Validate country_code
    if not country_code or not _COUNTRY_CODE_RE.match(country_code):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "country_code must be a valid ISO 3166-1 alpha-2 code (2 letters)"}},
            status_code=400,
        )

    # Validate rate
    if rate_raw is None:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "rate is required"}},
            status_code=400,
        )
    try:
        rate_float = float(rate_raw)
    except (TypeError, ValueError):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "rate must be a number"}},
            status_code=400,
        )
    if rate_float < 0 or rate_float > 100:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "rate must be between 0.00 and 100.00"}},
            status_code=400,
        )

    from decimal import Decimal
    from services.vat_service import upsert_rate

    result = upsert_rate(
        country_code=country_code,
        rate=Decimal(str(rate_float)),
        notes=notes,
        user_id=user["id"],
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "country_code": result.get("country_code", country_code.upper()),
                "rate": float(result.get("rate", rate_float)),
                "updated_at": result.get("updated_at", ""),
            },
        },
        status_code=200,
    )
