"""External integrations — Telegram BotAPI webhook.

Handler module (not router). Registered via thin wrapper in
api/routers/integrations.py. The Telegram webhook is listed in
api.auth.PUBLIC_API_PATHS so ApiAuthMiddleware passes it through without
JWT; Telegram signs the request via the secret token in the URL path and
request headers. Handler returns 200 OK even on partial failure to prevent
Telegram from retrying.

Moved verbatim from main.py @rt("/api/telegram/webhook") in Phase 6B-8.
"""

from __future__ import annotations

import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

from services.telegram_service import (
    WebhookResult,
    get_user_telegram_id,
    handle_approve_callback,
    handle_reject_callback,
    is_bot_configured,
    process_webhook_update,
    respond_to_command,
    send_callback_response,
)

logger = logging.getLogger(__name__)


async def telegram_webhook(request: Request) -> JSONResponse:
    """Handle incoming Telegram webhook updates.

    Path: POST /api/telegram/webhook
    Auth: Public — no JWT/session. Telegram signs requests via secret URL
        suffix + X-Telegram-Bot-Api-Secret-Token header (verified by
        PUBLIC_API_PATHS bypass in api/auth.py).
    Body: Telegram Update object (JSON).
    Returns:
        {"ok": True} (always, even on error, to prevent Telegram retries).
    Side Effects:
        - Dispatch to telegram_service handlers (commands, callbacks).
        - Update kvota.telegram_users via service layer.
        - Send outbound Telegram messages.
    Roles: none.
    """
    # Check if bot is configured
    if not is_bot_configured():
        logger.warning("Telegram webhook received but bot is not configured")
        return JSONResponse({"ok": True, "message": "Bot not configured"})

    # Get the request body
    try:
        # FastHTML provides the body through request
        body = await request.body()
        json_data = json.loads(body)
    except Exception as e:
        logger.error(f"Failed to parse webhook request: {e}")
        return JSONResponse({"ok": False, "error": "Invalid request body"})

    # Log the incoming update (for debugging)
    logger.info(f"Telegram webhook received update: {json_data.get('update_id', 'unknown')}")

    # Process the update asynchronously
    try:
        result: WebhookResult = await process_webhook_update(json_data)

        if result.success:
            # Handle different update types
            if result.update_type == "command" and result.telegram_id and result.text:
                # Respond to commands, passing any arguments (e.g., /start ABC123)
                # Also pass telegram_username for verification (Feature #55)
                await respond_to_command(result.telegram_id, result.text, result.args, result.telegram_username)

            elif result.update_type == "callback_query" and result.callback_data:
                # Handle callback queries (inline button presses)
                callback_data = result.callback_data
                logger.info(f"Callback query: {callback_data.action} for {callback_data.quote_id}")

                # Feature #60: Handle approve callback
                if callback_data.action == "approve":
                    approve_result = await handle_approve_callback(
                        telegram_id=result.telegram_id,
                        quote_id=callback_data.quote_id
                    )
                    logger.info(f"Approve callback result: success={approve_result.success}, quote={approve_result.quote_idn}")

                    # Get message_id from the original update to edit the message
                    message_id = ((json_data.get("callback_query") or {}).get("message") or {}).get("message_id")
                    if message_id and result.telegram_id:
                        await send_callback_response(result.telegram_id, message_id, approve_result)

                # Feature #61: Handle reject callback
                elif callback_data.action == "reject":
                    reject_result = await handle_reject_callback(
                        telegram_id=result.telegram_id,
                        quote_id=callback_data.quote_id
                    )
                    logger.info(f"Reject callback result: success={reject_result.success}, quote={reject_result.quote_idn}")

                    # Get message_id from the original update to edit the message
                    message_id = ((json_data.get("callback_query") or {}).get("message") or {}).get("message_id")
                    if message_id and result.telegram_id:
                        await send_callback_response(result.telegram_id, message_id, reject_result)

                # Handle details callback - just log for now
                elif callback_data.action == "details":
                    logger.info(f"Details callback for quote {callback_data.quote_id}")

            elif result.update_type == "message":
                # Regular text message — if unlinked, tell them; if linked, ignore
                logger.info(f"Text message from {result.telegram_id}: {result.text}")
                if result.telegram_id:
                    linked_user = get_user_telegram_id(result.telegram_id)
                    if not linked_user:
                        await respond_to_command(result.telegram_id, "/unlinked", [], result.telegram_username)

            logger.info(f"Webhook processed: {result.message}")
        else:
            logger.warning(f"Webhook processing failed: {result.error}")

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Still return 200 to prevent Telegram from retrying
        return JSONResponse({"ok": True, "error": str(e)})

    # Always return 200 OK to Telegram
    return JSONResponse({"ok": True})
