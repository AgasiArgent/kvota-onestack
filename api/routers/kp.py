"""KP Builder /api/kp/render-pdf router.

Thin wrapper over ``api.kp.render_pdf``. Registered on the FastAPI sub-app
in ``api/app.py`` with ``prefix="/kp"`` (full path: ``/api/kp/render-pdf``).
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from api.kp import render_pdf as _render_pdf

router = APIRouter(tags=["kp"])


@router.post("/render-pdf", response_model=None)
async def post_render_pdf(request: Request) -> Response:
    """Render a КП commercial proposal as PDF — see ``api.kp.render_pdf``.

    ``response_model=None`` disables FastAPI's pydantic serialization — the
    handler returns either a ``Response`` (binary PDF) or a ``JSONResponse``
    (error envelope), neither of which fits a static pydantic schema.
    """
    return await _render_pdf(request)
