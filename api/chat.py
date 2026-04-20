"""Chat API — inbound notifications of new chat messages.

Handler module (not router). Registered via thin wrapper in api/routers/chat.py.
Moved verbatim from main.py @rt("/api/chat/notify") in Phase 6B-7.

Auth: dual — JWT (Next.js) first via ApiAuthMiddleware, then legacy session
(FastHTML) via Starlette's SessionMiddleware.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

from services.telegram_service import send_chat_message_notification

logger = logging.getLogger(__name__)


async def notify(request: Request) -> JSONResponse:
    """Send Telegram notifications for new chat messages.

    Path: POST /api/chat/notify
    Auth: dual — JWT (Next.js) first, then legacy session (FastHTML).
    Body (JSON):
        quote_id: str (required) — quote whose chat received the message
        body: str (required) — message text
        mentions: list[str] (optional) — @-mentioned user ids
    Returns:
        success: bool
        data: dict — notified_count and optional error string
    Side Effects:
        - Sends Telegram notifications to subscribers and mentioned users
    Roles: authenticated (any role).
    """
    # Dual auth: JWT (Next.js) or session (FastHTML)
    api_user = getattr(request.state, "api_user", None)
    if api_user:
        user_id = str(api_user.id)
    else:
        try:
            session = request.session
        except (AssertionError, AttributeError):
            session = None
        if not session:
            return JSONResponse(
                {"success": False, "error": "Unauthorized"}, status_code=401
            )
        user = session.get("user", {})
        user_id = user.get("id")

    if not user_id:
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=401
        )

    # Parse JSON body
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": "Invalid JSON"}, status_code=400
        )

    quote_id = body.get("quote_id", "").strip()
    message_body = body.get("body", "").strip()
    mentions = body.get("mentions") or []

    if not quote_id or not message_body:
        return JSONResponse(
            {
                "success": False,
                "error": "quote_id and body are required",
            },
            status_code=400,
        )

    try:
        result = await send_chat_message_notification(
            quote_id=quote_id,
            sender_user_id=user_id,
            message_body=message_body,
            mentions=mentions,
        )
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Chat notification error: {e}")
        # Best-effort: never fail chat send because of notification glitches.
        return JSONResponse(
            {"success": True, "data": {"notified_count": 0, "error": str(e)}}
        )
