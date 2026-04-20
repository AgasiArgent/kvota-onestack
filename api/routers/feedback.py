"""Feedback /api/feedback endpoint.

Thin wrapper over the api.feedback handler module. Registered on the
FastAPI sub-app in api/app.py with prefix="/feedback" (full path:
/api/feedback). Accepts both JSON (Next.js) and form-encoded (legacy
FastHTML) bodies — the handler dispatches on Content-Type.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from api.feedback import submit_feedback as _submit_feedback

router = APIRouter(tags=["feedback"])


@router.post("", response_model=None)
async def post_feedback(request: Request) -> JSONResponse | HTMLResponse:
    """Submit user feedback (dual form/JSON body support).

    ``response_model=None`` disables FastAPI's auto pydantic serialization:
    the handler returns either a ``JSONResponse`` (Next.js) or an
    ``HTMLResponse`` (legacy FastHTML form), which are not valid pydantic
    field types for the OpenAPI response schema.
    """
    return await _submit_feedback(request)
