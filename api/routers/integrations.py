"""Integrations /api/telegram/* + /api/internal/* endpoints.

Thin wrapper over the api.integrations and api.feedback handler modules.
Registered on the FastAPI sub-app in api/app.py WITHOUT a prefix because
the router spans two unrelated path namespaces (/telegram/* webhook,
/internal/feedback/* admin). Full paths in decorators (relative to the
/api mount) are: /telegram/webhook and /internal/feedback/{short_id}/status.

Auth notes:
    - /telegram/webhook is listed in api.auth.PUBLIC_API_PATHS so
      ApiAuthMiddleware passes it through without JWT.
    - /internal/feedback/{short_id}/status is NOT public; the handler
      validates the X-Internal-Key header itself.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.feedback import update_feedback_status as _update_feedback_status
from api.integrations import telegram_webhook as _telegram_webhook

router = APIRouter(tags=["integrations"])


@router.post("/telegram/webhook")
async def post_telegram_webhook(request: Request) -> JSONResponse:
    """POST /api/telegram/webhook — inbound updates from Telegram BotAPI."""
    return await _telegram_webhook(request)


@router.post("/internal/feedback/{short_id}/status")
async def post_internal_feedback_status(
    request: Request, short_id: str
) -> JSONResponse:
    """POST /api/internal/feedback/{short_id}/status — resolve feedback."""
    return await _update_feedback_status(request, short_id)
