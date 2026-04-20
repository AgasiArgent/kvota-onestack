"""Chat /api/chat/* endpoints.

Thin wrapper over the api.chat handler module. Registered on the FastAPI
sub-app in api/app.py with prefix="/chat" (full path: /api/chat/...).
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.chat import notify as _notify

router = APIRouter(tags=["chat"])


@router.post("/notify")
async def post_notify(request: Request) -> JSONResponse:
    """Notify subscribers of a new chat message via Telegram (best-effort)."""
    return await _notify(request)
