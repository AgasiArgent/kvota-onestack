"""Workspace /api/workspace/* endpoints.

Thin wrapper over api.workspace handlers. Mounted with prefix="/workspace".
See api/workspace.py for business logic + docstrings.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.workspace import analytics as _analytics

router = APIRouter(tags=["workspace"])


@router.get("/{domain}/analytics")
async def get_analytics(request: Request, domain: str) -> JSONResponse:
    """Per-user completion analytics for head_of_{domain} / admin."""
    return await _analytics(request, domain)
