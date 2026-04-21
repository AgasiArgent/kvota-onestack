"""Feedback /api/feedback endpoint.

Thin wrapper over the api.feedback handler module. Registered on the
FastAPI sub-app in api/app.py with prefix="/feedback" (full path:
/api/feedback). JSON body only — the legacy FastHTML form-encoded path was
dropped in Phase 6C-4.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.feedback import submit_feedback as _submit_feedback

router = APIRouter(tags=["feedback"])


@router.post("", response_model=None)
async def post_feedback(request: Request) -> JSONResponse:
    """Submit user feedback (JSON body).

    ``response_model=None`` disables FastAPI's auto pydantic serialization —
    the handler returns a ``JSONResponse`` directly, which is not a valid
    pydantic field type for the OpenAPI response schema.
    """
    return await _submit_feedback(request)
