"""Admin /api/admin/* endpoints — user management and VAT rate configuration.

Thin wrapper over api.admin_users and api.geo handlers. Registered on the
FastAPI sub-app in api/app.py with prefix="/admin" (full path: /api/admin/...).

Paths live here instead of at handler definition sites so api.admin_users and
api.geo stay as pure handler modules that existing tests import from directly.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.admin_users import (
    create_user as _create_user,
    update_user_roles as _update_user_roles,
    update_user_status as _update_user_status,
)
from api.geo import update_vat_rate as _update_vat_rate

router = APIRouter(tags=["admin"])


@router.post("/users")
async def post_admin_users(request: Request) -> JSONResponse:
    """Create a new user. Delegates to api.admin_users.create_user."""
    return await _create_user(request)


@router.patch("/users/{user_id}/roles")
async def patch_admin_user_roles(request: Request, user_id: str) -> JSONResponse:
    """Update a user's role assignments."""
    return await _update_user_roles(request, user_id)


@router.patch("/users/{user_id}")
async def patch_admin_user(request: Request, user_id: str) -> JSONResponse:
    """Update a user's status (active/suspended)."""
    return await _update_user_status(request, user_id)


@router.put("/vat-rates")
async def put_admin_vat_rates(request: Request) -> JSONResponse:
    """Update VAT rate configuration for a country."""
    return await _update_vat_rate(request)
