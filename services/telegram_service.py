"""
Telegram Bot Service for OneStack Workflow

Feature #52: Create Telegram bot infrastructure

This module provides:
- Bot initialization and configuration
- Message sending functions
- Notification templates
- Inline keyboard builders for approvals

The bot handles:
- /start - Account verification
- /status - Current tasks
- /help - Help information
- Callback queries for approval/rejection

Usage:
    from services.telegram_service import (
        get_bot,
        send_notification,
        send_approval_request,
        is_bot_configured
    )
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# Telegram bot imports - handle import gracefully if not installed
try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    Update = None
    TelegramError = Exception

from dotenv import load_dotenv
from services.database import get_supabase

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5001")


def is_bot_configured() -> bool:
    """Check if Telegram bot is properly configured.

    Returns:
        True if bot token is set and telegram library is available
    """
    return bool(TELEGRAM_BOT_TOKEN) and TELEGRAM_AVAILABLE


def get_bot() -> Optional['Bot']:
    """Get the Telegram bot instance.

    Returns:
        Bot instance if configured, None otherwise

    Example:
        bot = get_bot()
        if bot:
            await bot.send_message(chat_id=12345, text="Hello!")
    """
    if not is_bot_configured():
        logger.warning("Telegram bot is not configured. Set TELEGRAM_BOT_TOKEN.")
        return None

    return Bot(token=TELEGRAM_BOT_TOKEN)


# ============================================================================
# Notification Types
# ============================================================================

class NotificationType(Enum):
    """Types of notifications that can be sent via Telegram."""
    TASK_ASSIGNED = "task_assigned"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_DECISION = "approval_decision"
    STATUS_CHANGED = "status_changed"
    RETURNED_FOR_REVISION = "returned_for_revision"
    COMMENT_ADDED = "comment_added"
    DEADLINE_REMINDER = "deadline_reminder"
    SYSTEM_MESSAGE = "system_message"


@dataclass
class NotificationPayload:
    """Data structure for notification content."""
    notification_type: NotificationType
    title: str
    message: str
    quote_id: Optional[str] = None
    quote_idn: Optional[str] = None
    customer_name: Optional[str] = None
    actor_name: Optional[str] = None
    action_required: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


# ============================================================================
# Message Templates
# ============================================================================

NOTIFICATION_TEMPLATES = {
    NotificationType.TASK_ASSIGNED: """
📋 *Новая задача*

КП: {quote_idn}
Клиент: {customer_name}
Действие: {action_required}

[Открыть в системе]({quote_url})
""",

    NotificationType.APPROVAL_REQUIRED: """
🔔 *Требуется согласование*

КП: {quote_idn}
Клиент: {customer_name}
Сумма: {total_amount}
Причина: {approval_reason}

*Детали:*
• Наценка: {markup}%
• Условия: {payment_terms}
""",

    NotificationType.STATUS_CHANGED: """
📝 *Статус изменён*

КП: {quote_idn}
Новый статус: {new_status}
Изменил: {actor_name}

[Открыть в системе]({quote_url})
""",

    NotificationType.RETURNED_FOR_REVISION: """
⚠️ *Возвращено на доработку*

КП: {quote_idn}
Причина: {comment}
Вернул: {actor_name}

[Открыть в системе]({quote_url})
""",

    NotificationType.APPROVAL_DECISION: """
{emoji} *Решение по согласованию*

КП: {quote_idn}
Решение: {decision}
{comment_section}

[Открыть в системе]({quote_url})
""",

    NotificationType.SYSTEM_MESSAGE: """
ℹ️ *Системное уведомление*

{message}
""",
}


def format_notification(
    notification_type: NotificationType,
    **kwargs
) -> str:
    """Format a notification message using the appropriate template.

    Args:
        notification_type: Type of notification
        **kwargs: Template variables

    Returns:
        Formatted message string

    Example:
        message = format_notification(
            NotificationType.TASK_ASSIGNED,
            quote_idn="КП-2025-001",
            customer_name="ООО Компания",
            action_required="Оценить закупочные цены",
            quote_url="http://localhost:5001/quotes/xxx"
        )
    """
    template = NOTIFICATION_TEMPLATES.get(notification_type, NOTIFICATION_TEMPLATES[NotificationType.SYSTEM_MESSAGE])

    # Add default values for missing fields
    defaults = {
        "quote_idn": "N/A",
        "customer_name": "N/A",
        "actor_name": "Система",
        "action_required": "",
        "quote_url": APP_BASE_URL,
        "message": "",
        "comment": "",
        "new_status": "",
        "total_amount": "N/A",
        "approval_reason": "",
        "markup": "N/A",
        "payment_terms": "N/A",
        "emoji": "📋",
        "decision": "",
        "comment_section": "",
    }
    defaults.update(kwargs)

    try:
        return template.format(**defaults).strip()
    except KeyError as e:
        logger.error(f"Missing template variable: {e}")
        return f"Уведомление: {notification_type.value}"


# ============================================================================
# Inline Keyboards
# ============================================================================

def build_approval_keyboard(quote_id: str) -> Optional['InlineKeyboardMarkup']:
    """Build inline keyboard for approval requests.

    Args:
        quote_id: UUID of the quote

    Returns:
        InlineKeyboardMarkup with Approve/Reject/Details buttons

    Example:
        keyboard = build_approval_keyboard("uuid-xxx")
        await bot.send_message(
            chat_id=12345,
            text="Требуется согласование",
            reply_markup=keyboard
        )
    """
    if not TELEGRAM_AVAILABLE:
        return None

    keyboard = [
        [
            InlineKeyboardButton("✅ Согласовать", callback_data=f"approve_{quote_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{quote_id}"),
        ],
        [
            InlineKeyboardButton("📋 Подробнее", callback_data=f"details_{quote_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_open_quote_keyboard(quote_id: str) -> Optional['InlineKeyboardMarkup']:
    """Build inline keyboard with link to open quote.

    Args:
        quote_id: UUID of the quote

    Returns:
        InlineKeyboardMarkup with Open button
    """
    if not TELEGRAM_AVAILABLE:
        return None

    quote_url = f"{APP_BASE_URL}/quotes/{quote_id}"
    keyboard = [
        [InlineKeyboardButton("📋 Открыть в системе", url=quote_url)],
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# Message Sending Functions
# ============================================================================

async def send_message(
    telegram_id: int,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: Optional['InlineKeyboardMarkup'] = None
) -> Optional[int]:
    """Send a message to a Telegram user.

    Args:
        telegram_id: Telegram user ID
        text: Message text
        parse_mode: Message parse mode (Markdown, HTML)
        reply_markup: Optional inline keyboard

    Returns:
        Message ID if sent successfully, None otherwise

    Example:
        message_id = await send_message(
            telegram_id=12345678,
            text="Hello, World!",
            reply_markup=build_open_quote_keyboard("uuid-xxx")
        )
    """
    bot = get_bot()
    if not bot:
        logger.warning("Cannot send message: bot not configured")
        return None

    try:
        message = await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        logger.info(f"Message sent to {telegram_id}: {message.message_id}")
        return message.message_id
    except TelegramError as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")
        return None


async def send_notification(
    telegram_id: int,
    notification_type: NotificationType,
    quote_id: Optional[str] = None,
    include_open_button: bool = True,
    **kwargs
) -> Optional[int]:
    """Send a formatted notification to a Telegram user.

    Args:
        telegram_id: Telegram user ID
        notification_type: Type of notification
        quote_id: Optional quote ID for building links
        include_open_button: Whether to include "Open in system" button
        **kwargs: Template variables

    Returns:
        Message ID if sent successfully, None otherwise

    Example:
        await send_notification(
            telegram_id=12345678,
            notification_type=NotificationType.TASK_ASSIGNED,
            quote_id="uuid-xxx",
            quote_idn="КП-2025-001",
            customer_name="ООО Компания",
            action_required="Оценить закупочные цены"
        )
    """
    # Build quote URL if quote_id provided
    if quote_id:
        kwargs["quote_url"] = f"{APP_BASE_URL}/quotes/{quote_id}"

    # Format message
    text = format_notification(notification_type, **kwargs)

    # Build keyboard
    reply_markup = None
    if include_open_button and quote_id:
        reply_markup = build_open_quote_keyboard(quote_id)

    return await send_message(
        telegram_id=telegram_id,
        text=text,
        reply_markup=reply_markup
    )


async def send_approval_request(
    telegram_id: int,
    quote_id: str,
    quote_idn: str,
    customer_name: str,
    total_amount: str,
    approval_reason: str,
    markup: str = "N/A",
    payment_terms: str = "N/A"
) -> Optional[int]:
    """Send an approval request with inline buttons.

    This is a specialized function for sending approval requests to
    top managers with Approve/Reject buttons.

    Args:
        telegram_id: Telegram user ID (top manager)
        quote_id: UUID of the quote
        quote_idn: Quote identifier (e.g., "КП-2025-001")
        customer_name: Customer name
        total_amount: Total quote amount formatted
        approval_reason: Reason approval is needed
        markup: Markup percentage
        payment_terms: Payment terms

    Returns:
        Message ID if sent successfully, None otherwise

    Example:
        await send_approval_request(
            telegram_id=12345678,
            quote_id="uuid-xxx",
            quote_idn="КП-2025-001",
            customer_name="ООО Компания",
            total_amount="1 000 000 RUB",
            approval_reason="Валюта в рублях",
            markup="15",
            payment_terms="50% предоплата"
        )
    """
    text = format_notification(
        NotificationType.APPROVAL_REQUIRED,
        quote_idn=quote_idn,
        customer_name=customer_name,
        total_amount=total_amount,
        approval_reason=approval_reason,
        markup=markup,
        payment_terms=payment_terms
    )

    keyboard = build_approval_keyboard(quote_id)

    return await send_message(
        telegram_id=telegram_id,
        text=text,
        reply_markup=keyboard
    )


async def edit_message(
    telegram_id: int,
    message_id: int,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: Optional['InlineKeyboardMarkup'] = None
) -> bool:
    """Edit an existing message.

    Args:
        telegram_id: Telegram user ID
        message_id: ID of the message to edit
        text: New message text
        parse_mode: Message parse mode
        reply_markup: Optional inline keyboard

    Returns:
        True if edited successfully, False otherwise
    """
    bot = get_bot()
    if not bot:
        return False

    try:
        await bot.edit_message_text(
            chat_id=telegram_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        logger.info(f"Message {message_id} edited for {telegram_id}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to edit message {message_id}: {e}")
        return False


# ============================================================================
# Webhook Setup
# ============================================================================

async def setup_webhook(webhook_url: Optional[str] = None) -> bool:
    """Set up the webhook for receiving Telegram updates.

    Args:
        webhook_url: URL for webhook (defaults to TELEGRAM_WEBHOOK_URL env var)

    Returns:
        True if webhook was set successfully, False otherwise

    Example:
        success = await setup_webhook("https://your-domain.com/api/telegram/webhook")
    """
    bot = get_bot()
    if not bot:
        return False

    url = webhook_url or TELEGRAM_WEBHOOK_URL
    if not url:
        logger.error("No webhook URL provided")
        return False

    try:
        await bot.set_webhook(url=url)
        logger.info(f"Webhook set to: {url}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to set webhook: {e}")
        return False


async def delete_webhook() -> bool:
    """Delete the webhook (switch to polling mode).

    Returns:
        True if webhook was deleted successfully, False otherwise
    """
    bot = get_bot()
    if not bot:
        return False

    try:
        await bot.delete_webhook()
        logger.info("Webhook deleted")
        return True
    except TelegramError as e:
        logger.error(f"Failed to delete webhook: {e}")
        return False


async def get_webhook_info() -> Optional[Dict[str, Any]]:
    """Get current webhook information.

    Returns:
        Dict with webhook info or None if failed
    """
    bot = get_bot()
    if not bot:
        return None

    try:
        info = await bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "ip_address": info.ip_address,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
            "allowed_updates": info.allowed_updates,
        }
    except TelegramError as e:
        logger.error(f"Failed to get webhook info: {e}")
        return None


# ============================================================================
# Bot Info
# ============================================================================

async def get_bot_info() -> Optional[Dict[str, Any]]:
    """Get information about the bot.

    Returns:
        Dict with bot info or None if failed

    Example:
        info = await get_bot_info()
        print(f"Bot username: @{info['username']}")
    """
    bot = get_bot()
    if not bot:
        return None

    try:
        me = await bot.get_me()
        return {
            "id": me.id,
            "is_bot": me.is_bot,
            "first_name": me.first_name,
            "username": me.username,
            "can_join_groups": me.can_join_groups,
            "can_read_all_group_messages": me.can_read_all_group_messages,
            "supports_inline_queries": me.supports_inline_queries,
        }
    except TelegramError as e:
        logger.error(f"Failed to get bot info: {e}")
        return None


# ============================================================================
# Callback Data Parsing
# ============================================================================

@dataclass
class CallbackData:
    """Parsed callback data from inline button."""
    action: str
    quote_id: str
    raw: str


def parse_callback_data(callback_data: str) -> Optional[CallbackData]:
    """Parse callback data from inline button press.

    Expected format: action_quoteId
    Examples:
        - approve_uuid-xxx → action="approve", quote_id="uuid-xxx"
        - reject_uuid-xxx → action="reject", quote_id="uuid-xxx"
        - details_uuid-xxx → action="details", quote_id="uuid-xxx"

    Args:
        callback_data: Raw callback data string

    Returns:
        CallbackData object or None if parsing failed
    """
    if not callback_data:
        return None

    # Split on first underscore
    parts = callback_data.split("_", 1)
    if len(parts) != 2:
        logger.warning(f"Invalid callback data format: {callback_data}")
        return None

    action, quote_id = parts

    # Validate action
    valid_actions = {"approve", "reject", "details"}
    if action not in valid_actions:
        logger.warning(f"Unknown callback action: {action}")
        return None

    return CallbackData(
        action=action,
        quote_id=quote_id,
        raw=callback_data
    )


# ============================================================================
# Account Verification (Feature #55)
# ============================================================================

@dataclass
class VerificationResult:
    """Result of account verification attempt."""
    success: bool
    user_id: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


async def verify_telegram_account(
    verification_code: str,
    telegram_id: int,
    telegram_username: Optional[str] = None
) -> VerificationResult:
    """Verify a Telegram account using the provided verification code.

    Feature #55: Account verification (привязка telegram_id к user через код)

    This function calls the database function verify_telegram_account() which:
    1. Looks up the verification code in telegram_users table
    2. Checks if code is valid and not expired
    3. Links the telegram_id to the user
    4. Marks the account as verified

    Args:
        verification_code: 6-character verification code from the user
        telegram_id: Telegram user ID
        telegram_username: Optional Telegram username

    Returns:
        VerificationResult with success status and user_id if successful

    Example:
        result = await verify_telegram_account("ABC123", 12345678, "username")
        if result.success:
            print(f"Verified user: {result.user_id}")
    """
    try:
        supabase = get_supabase()
        if not supabase:
            logger.error("Cannot get service Supabase client")
            return VerificationResult(
                success=False,
                error="Database connection error",
                message="Не удалось подключиться к базе данных. Попробуйте позже."
            )

        # Call the database function
        # Using RPC call to verify_telegram_account
        response = supabase.rpc(
            "verify_telegram_account",
            {
                "p_verification_code": verification_code.upper(),
                "p_telegram_id": telegram_id,
                "p_telegram_username": telegram_username
            }
        ).execute()

        logger.info(f"Verification response: {response.data}")

        if response.data and len(response.data) > 0:
            result = response.data[0]
            if result.get("success"):
                logger.info(f"Successfully verified Telegram account {telegram_id} for user {result.get('user_id')}")
                return VerificationResult(
                    success=True,
                    user_id=result.get("user_id"),
                    message=result.get("message", "Аккаунт успешно привязан!")
                )
            else:
                # Verification failed (invalid/expired code or already linked)
                error_msg = result.get("message", "Неверный или устаревший код")
                logger.warning(f"Verification failed for {telegram_id}: {error_msg}")
                return VerificationResult(
                    success=False,
                    error=error_msg,
                    message=error_msg
                )
        else:
            logger.error(f"Empty response from verify_telegram_account for {telegram_id}")
            return VerificationResult(
                success=False,
                error="Empty response",
                message="Не удалось проверить код. Попробуйте позже."
            )

    except Exception as e:
        logger.error(f"Error verifying Telegram account: {e}")
        return VerificationResult(
            success=False,
            error=str(e),
            message="Произошла ошибка при проверке кода. Попробуйте позже."
        )


async def get_telegram_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get the linked user for a Telegram ID.

    Args:
        telegram_id: Telegram user ID

    Returns:
        Dict with user_id and other info if linked, None otherwise
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return None

        response = supabase.table("telegram_users").select(
            "id, user_id, telegram_username, is_verified, verified_at"
        ).eq("telegram_id", telegram_id).eq("is_verified", True).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    except Exception as e:
        logger.error(f"Error getting Telegram user: {e}")
        return None


async def is_telegram_linked(telegram_id: int) -> bool:
    """Check if a Telegram ID is linked to a user.

    Args:
        telegram_id: Telegram user ID

    Returns:
        True if linked, False otherwise
    """
    user = await get_telegram_user(telegram_id)
    return user is not None


# ============================================================================
# Verification Code Request (Feature #56)
# ============================================================================

@dataclass
class TelegramStatus:
    """Status of user's Telegram connection."""
    is_linked: bool
    is_verified: bool
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None
    verified_at: Optional[str] = None
    verification_code: Optional[str] = None
    code_expires_at: Optional[str] = None


def get_user_telegram_status(user_id: str) -> TelegramStatus:
    """Get the Telegram connection status for a user.

    Feature #56: Used by /settings/telegram page to show current status.

    Args:
        user_id: UUID of the system user

    Returns:
        TelegramStatus with connection details

    Example:
        status = get_user_telegram_status(user["id"])
        if status.is_verified:
            print(f"Linked to @{status.telegram_username}")
        elif status.verification_code:
            print(f"Pending code: {status.verification_code}")
    """
    try:
        supabase = get_supabase()
        if not supabase:
            logger.error("Cannot get service Supabase client")
            return TelegramStatus(is_linked=False, is_verified=False)

        response = supabase.table("telegram_users").select(
            "telegram_id, telegram_username, is_verified, verified_at, verification_code, verification_code_expires_at"
        ).eq("user_id", user_id).execute()

        if response.data and len(response.data) > 0:
            record = response.data[0]
            return TelegramStatus(
                is_linked=True,
                is_verified=record.get("is_verified", False),
                telegram_id=record.get("telegram_id") if record.get("telegram_id") != 0 else None,
                telegram_username=record.get("telegram_username"),
                verified_at=record.get("verified_at"),
                verification_code=record.get("verification_code") if not record.get("is_verified") else None,
                code_expires_at=record.get("verification_code_expires_at") if not record.get("is_verified") else None
            )

        return TelegramStatus(is_linked=False, is_verified=False)

    except Exception as e:
        logger.error(f"Error getting Telegram status for user {user_id}: {e}")
        return TelegramStatus(is_linked=False, is_verified=False)


def request_verification_code(user_id: str) -> Optional[str]:
    """Request a new verification code for Telegram linking.

    Feature #56: Called when user clicks "Get verification code" button.

    This function calls the database function request_telegram_verification() which:
    1. Checks if user already has a verified account (returns NULL)
    2. Generates a new 6-character verification code
    3. Sets expiration to 30 minutes from now
    4. Returns the code

    Args:
        user_id: UUID of the system user

    Returns:
        6-character verification code, or None if already verified or error

    Example:
        code = request_verification_code(user["id"])
        if code:
            print(f"Your code: {code}")
        else:
            print("Already verified or error occurred")
    """
    try:
        supabase = get_supabase()
        if not supabase:
            logger.error("Cannot get service Supabase client")
            return None

        # Call the database function
        response = supabase.rpc(
            "request_telegram_verification",
            {"p_user_id": user_id}
        ).execute()

        logger.info(f"Verification code request response: {response.data}")

        # The function returns the code directly (not in a record)
        if response.data:
            return response.data

        return None

    except Exception as e:
        logger.error(f"Error requesting verification code for user {user_id}: {e}")
        return None


def unlink_telegram_account(user_id: str) -> bool:
    """Remove the Telegram link for a user.

    Feature #56: Called when user clicks "Unlink Telegram" button.

    Args:
        user_id: UUID of the system user

    Returns:
        True if successfully unlinked, False otherwise
    """
    try:
        supabase = get_supabase()
        if not supabase:
            logger.error("Cannot get service Supabase client")
            return False

        # Delete the telegram_users record
        response = supabase.table("telegram_users").delete().eq("user_id", user_id).execute()

        logger.info(f"Unlinked Telegram for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error unlinking Telegram for user {user_id}: {e}")
        return False


# ============================================================================
# Webhook Processing
# ============================================================================

@dataclass
class WebhookResult:
    """Result of processing a webhook update."""
    success: bool
    update_type: str  # "message", "callback_query", "command", "unknown"
    message: Optional[str] = None
    callback_data: Optional[CallbackData] = None
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None  # Username for verification (Feature #55)
    text: Optional[str] = None
    args: Optional[List[str]] = None  # Command arguments (e.g., /start ABC123 → args=["ABC123"])
    error: Optional[str] = None


def parse_telegram_update(json_data: Dict[str, Any]) -> Optional['Update']:
    """Parse JSON data into a Telegram Update object.

    Args:
        json_data: Raw JSON data from webhook

    Returns:
        Update object or None if parsing failed

    Example:
        update = parse_telegram_update({"update_id": 123, "message": {...}})
    """
    if not TELEGRAM_AVAILABLE or Update is None:
        logger.warning("Telegram library not available, cannot parse update")
        return None

    try:
        return Update.de_json(json_data, get_bot())
    except Exception as e:
        logger.error(f"Failed to parse Telegram update: {e}")
        return None


async def process_webhook_update(json_data: Dict[str, Any]) -> WebhookResult:
    """Process an incoming webhook update from Telegram.

    This function handles:
    - Text messages (commands like /start, /status, /help)
    - Callback queries from inline buttons (approve, reject, details)

    Args:
        json_data: Raw JSON data from webhook request

    Returns:
        WebhookResult with processing details

    Example:
        result = await process_webhook_update(request_json)
        if result.success:
            # Handle based on update_type
            if result.update_type == "callback_query":
                # Handle approval/rejection
                pass
    """
    # Parse the update
    update = parse_telegram_update(json_data)
    if not update:
        return WebhookResult(
            success=False,
            update_type="unknown",
            error="Failed to parse update"
        )

    # Handle callback queries (inline button presses)
    if update.callback_query:
        callback_query = update.callback_query
        telegram_id = callback_query.from_user.id

        # Parse the callback data
        callback_data = parse_callback_data(callback_query.data or "")

        # Acknowledge the callback to remove loading state
        try:
            await callback_query.answer()
        except TelegramError as e:
            logger.warning(f"Failed to answer callback query: {e}")

        if callback_data:
            return WebhookResult(
                success=True,
                update_type="callback_query",
                callback_data=callback_data,
                telegram_id=telegram_id,
                message=f"Received {callback_data.action} for quote {callback_data.quote_id}"
            )
        else:
            return WebhookResult(
                success=False,
                update_type="callback_query",
                telegram_id=telegram_id,
                error=f"Invalid callback data: {callback_query.data}"
            )

    # Handle regular messages
    if update.message:
        message = update.message
        telegram_id = message.from_user.id if message.from_user else None
        telegram_username = message.from_user.username if message.from_user else None
        text = message.text or ""

        # Check if it's a command
        if text.startswith("/"):
            command = text.split()[0].lower()
            # Extract command argument if present
            args = text.split()[1:] if len(text.split()) > 1 else []

            return WebhookResult(
                success=True,
                update_type="command",
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                text=command,
                args=args if args else None,
                message=f"Command {command} received" + (f" with args: {args}" if args else "")
            )
        else:
            # Regular text message
            return WebhookResult(
                success=True,
                update_type="message",
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                text=text,
                message="Text message received"
            )

    # Unknown update type
    return WebhookResult(
        success=False,
        update_type="unknown",
        error="Unsupported update type"
    )


async def respond_to_command(telegram_id: int, command: str, args: List[str] = None, telegram_username: str = None) -> bool:
    """Send a response to a bot command.

    Handles the main bot commands:
    - /start: Greeting and verification instructions (Feature #54, #55)
    - /status: Show current tasks (Feature #57)
    - /help: Show help information

    Args:
        telegram_id: User's Telegram ID
        command: Command received (e.g., "/start")
        args: Optional command arguments
        telegram_username: Optional Telegram username (for verification)

    Returns:
        True if response was sent successfully
    """
    bot = get_bot()
    if not bot:
        return False

    args = args or []

    # Handle /start command specially (Feature #54, #55)
    if command == "/start":
        return await handle_start_command(telegram_id, args, telegram_username)

    # Handle /status command (Feature #57)
    if command == "/status":
        return await handle_status_command(telegram_id)

    # Other commands
    responses = {
        "/help": """📚 *Справка по боту OneStack*

*Доступные команды:*
• /start — Начало работы, привязка аккаунта
• /status — Показать мои текущие задачи
• /help — Показать эту справку

*Как привязать аккаунт:*
1. Откройте OneStack в браузере
2. Перейдите в Настройки → Telegram
3. Нажмите "Получить код привязки"
4. Отправьте код боту

*Уведомления:*
После привязки вы будете получать:
• Уведомления о новых задачах
• Запросы на согласование
• Изменения статусов КП

По вопросам работы бота обратитесь к администратору.""",
    }

    response_text = responses.get(command, f"❓ Неизвестная команда: `{command}`\n\nИспользуйте /help для списка доступных команд.")

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=response_text,
            parse_mode="Markdown"
        )
        logger.info(f"Sent response for {command} to {telegram_id}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to send command response: {e}")
        return False


async def handle_start_command(telegram_id: int, args: List[str] = None, telegram_username: str = None) -> bool:
    """Handle the /start command with greeting and verification instructions.

    Feature #54: Команда /start (приветствие и инструкция по привязке)
    Feature #55: Верификация аккаунта (account verification)

    The /start command can be called in two ways:
    1. /start - Shows welcome message and instructions
    2. /start <code> - Attempts to verify account with the provided code

    Args:
        telegram_id: User's Telegram ID
        args: Optional arguments (verification code)
        telegram_username: Optional Telegram username (for storing during verification)

    Returns:
        True if message was sent successfully
    """
    bot = get_bot()
    if not bot:
        return False

    args = args or []

    # If a code is provided, attempt verification (Feature #55)
    if args:
        code = args[0].strip().upper()
        logger.info(f"Verification code received from {telegram_id}: {code}")

        # Call the verification function
        verification_result = await verify_telegram_account(
            verification_code=code,
            telegram_id=telegram_id,
            telegram_username=telegram_username
        )

        if verification_result.success:
            # Success message
            response_text = f"""✅ *Аккаунт успешно привязан!*

Ваш Telegram аккаунт теперь связан с системой OneStack.

*Что будет дальше:*
• Вы будете получать уведомления о новых задачах
• Сможете согласовывать КП прямо в этом чате
• Будете в курсе изменений статусов

━━━━━━━━━━━━━━━━━━━━━━

📋 Используйте /status для просмотра ваших задач
📚 Используйте /help для справки"""
        else:
            # Error message with specific reason
            error_msg = verification_result.message
            response_text = f"""❌ *Не удалось привязать аккаунт*

{error_msg}

━━━━━━━━━━━━━━━━━━━━━━

*Возможные причины:*
• Код неверный или устарел (действует 15 минут)
• Этот Telegram уже привязан к другому пользователю
• Код уже был использован

*Что делать:*
1. Откройте OneStack в браузере
2. Перейдите в Настройки → Telegram
3. Нажмите "Получить новый код"
4. Отправьте новый код боту"""
    else:
        # Standard greeting without code
        response_text = """👋 *Добро пожаловать в OneStack Bot!*

Этот бот поможет вам:
• Получать уведомления о новых задачах
• Согласовывать КП прямо в Telegram
• Отслеживать статусы ваших заявок

━━━━━━━━━━━━━━━━━━━━━━

*Как привязать аккаунт:*

1️⃣ Откройте OneStack в браузере
   → Войдите в свой аккаунт

2️⃣ Перейдите в Настройки
   → Раздел "Telegram"

3️⃣ Нажмите "Получить код привязки"
   → Скопируйте 6-значный код

4️⃣ Отправьте код этому боту
   → Или нажмите кнопку в системе

━━━━━━━━━━━━━━━━━━━━━━

💡 *Подсказка:* Код действует 15 минут.
Если код устарел, получите новый.

📚 Используйте /help для справки."""

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=response_text,
            parse_mode="Markdown"
        )
        logger.info(f"Sent /start response to {telegram_id}" + (" (with code)" if args else ""))
        return True
    except TelegramError as e:
        logger.error(f"Failed to send /start response: {e}")
        return False


# ============================================================================
# /status Command - Show user's current tasks (Feature #57)
# ============================================================================

@dataclass
class UserTask:
    """Represents a task/quote for the user."""
    quote_id: str
    quote_idn: str
    customer_name: str
    status: str
    status_name: str
    task_type: str  # e.g., "procurement", "logistics", "review"
    url: str


def get_user_tasks(user_id: str) -> Dict[str, Any]:
    """Get all pending tasks for a user based on their roles.

    Feature #57: Команда /status - показать мои текущие задачи

    This function:
    1. Gets user's roles from user_roles table
    2. Based on roles, queries relevant quotes:
       - sales: quotes they created in draft or pending_sales_review
       - procurement: quotes with their brands in pending_procurement
       - logistics: quotes in pending_logistics
       - customs: quotes in pending_customs
       - quote_controller: quotes in pending_quote_control
       - top_manager: quotes in pending_approval (approvals table)

    Args:
        user_id: UUID of the system user

    Returns:
        Dict with:
        - success: bool
        - user_name: str
        - roles: list of role codes
        - tasks: dict of task_type -> list of UserTask
        - total_tasks: int
        - error: str if failed

    Example:
        >>> tasks = get_user_tasks(user_id)
        >>> if tasks["success"]:
        ...     print(f"You have {tasks['total_tasks']} tasks")
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {
                "success": False,
                "error": "Database connection error"
            }

        # Get user info
        user_response = supabase.table("organization_members").select(
            "user_id, organization_id, profile:profiles(email, full_name)"
        ).eq("user_id", user_id).execute()

        if not user_response.data or len(user_response.data) == 0:
            return {
                "success": False,
                "error": "User not found in any organization"
            }

        member_data = user_response.data[0]
        org_id = member_data.get("organization_id")
        profile = member_data.get("profile", {})
        user_name = profile.get("full_name") or profile.get("email", "Пользователь")

        # Get user roles
        roles_response = supabase.table("user_roles").select(
            "role:roles(code, name)"
        ).eq("user_id", user_id).eq("organization_id", org_id).execute()

        roles = []
        if roles_response.data:
            for r in roles_response.data:
                role_info = r.get("role", {})
                if role_info and role_info.get("code"):
                    roles.append(role_info.get("code"))

        if not roles:
            return {
                "success": True,
                "user_name": user_name,
                "roles": [],
                "tasks": {},
                "total_tasks": 0,
                "message": "У вас пока нет назначенных ролей в системе."
            }

        tasks: Dict[str, List[UserTask]] = {}
        total_tasks = 0

        # ---- SALES role: drafts and pending_sales_review quotes they created ----
        if "sales" in roles or "admin" in roles:
            sales_quotes_response = supabase.table("quotes").select(
                "id, idn, workflow_status, customer:customers(name)"
            ).eq("organization_id", org_id).eq("created_by", user_id).in_(
                "workflow_status", ["draft", "pending_sales_review"]
            ).limit(20).execute()

            if sales_quotes_response.data:
                sales_tasks = []
                for q in sales_quotes_response.data:
                    customer = q.get("customer", {})
                    status = q.get("workflow_status", "draft")
                    task_type = "Мои КП" if status == "draft" else "Требует доработки"
                    sales_tasks.append(UserTask(
                        quote_id=q.get("id"),
                        quote_idn=q.get("idn", "N/A"),
                        customer_name=customer.get("name", "N/A") if customer else "N/A",
                        status=status,
                        status_name=_get_status_name_ru(status),
                        task_type=task_type,
                        url=f"{APP_BASE_URL}/quotes/{q.get('id')}"
                    ))
                if sales_tasks:
                    tasks["sales"] = sales_tasks
                    total_tasks += len(sales_tasks)

        # ---- PROCUREMENT role: quotes with their brands ----
        if "procurement" in roles or "admin" in roles:
            # Get user's assigned brands
            brands_response = supabase.table("brand_assignments").select(
                "brand"
            ).eq("organization_id", org_id).eq("user_id", user_id).execute()

            user_brands = []
            if brands_response.data:
                user_brands = [b.get("brand", "").lower() for b in brands_response.data if b.get("brand")]

            if user_brands:
                # Get quotes in pending_procurement with items matching user's brands
                proc_quotes_response = supabase.table("quotes").select(
                    "id, idn, workflow_status, customer:customers(name), quote_items(brand)"
                ).eq("organization_id", org_id).eq(
                    "workflow_status", "pending_procurement"
                ).limit(50).execute()

                if proc_quotes_response.data:
                    proc_tasks = []
                    seen_quote_ids = set()
                    for q in proc_quotes_response.data:
                        if q.get("id") in seen_quote_ids:
                            continue
                        # Check if quote has items with user's brands
                        items = q.get("quote_items", [])
                        has_my_brand = any(
                            item.get("brand", "").lower() in user_brands
                            for item in items
                        )
                        if has_my_brand:
                            customer = q.get("customer", {})
                            proc_tasks.append(UserTask(
                                quote_id=q.get("id"),
                                quote_idn=q.get("idn", "N/A"),
                                customer_name=customer.get("name", "N/A") if customer else "N/A",
                                status="pending_procurement",
                                status_name=_get_status_name_ru("pending_procurement"),
                                task_type="Оценка закупок",
                                url=f"{APP_BASE_URL}/procurement"
                            ))
                            seen_quote_ids.add(q.get("id"))
                    if proc_tasks:
                        tasks["procurement"] = proc_tasks
                        total_tasks += len(proc_tasks)

        # ---- LOGISTICS role: quotes in pending_logistics ----
        if "logistics" in roles or "admin" in roles:
            logistics_quotes_response = supabase.table("quotes").select(
                "id, idn, workflow_status, customer:customers(name)"
            ).eq("organization_id", org_id).eq(
                "workflow_status", "pending_logistics"
            ).limit(20).execute()

            if logistics_quotes_response.data:
                logistics_tasks = []
                for q in logistics_quotes_response.data:
                    customer = q.get("customer", {})
                    logistics_tasks.append(UserTask(
                        quote_id=q.get("id"),
                        quote_idn=q.get("idn", "N/A"),
                        customer_name=customer.get("name", "N/A") if customer else "N/A",
                        status="pending_logistics",
                        status_name=_get_status_name_ru("pending_logistics"),
                        task_type="Логистика",
                        url=f"{APP_BASE_URL}/logistics/{q.get('id')}"
                    ))
                if logistics_tasks:
                    tasks["logistics"] = logistics_tasks
                    total_tasks += len(logistics_tasks)

        # ---- CUSTOMS role: quotes in pending_customs or pending_logistics (parallel) ----
        if "customs" in roles or "admin" in roles:
            customs_quotes_response = supabase.table("quotes").select(
                "id, idn, workflow_status, customer:customers(name)"
            ).eq("organization_id", org_id).in_(
                "workflow_status", ["pending_customs", "pending_logistics"]
            ).limit(20).execute()

            if customs_quotes_response.data:
                customs_tasks = []
                for q in customs_quotes_response.data:
                    customer = q.get("customer", {})
                    customs_tasks.append(UserTask(
                        quote_id=q.get("id"),
                        quote_idn=q.get("idn", "N/A"),
                        customer_name=customer.get("name", "N/A") if customer else "N/A",
                        status=q.get("workflow_status"),
                        status_name=_get_status_name_ru(q.get("workflow_status", "")),
                        task_type="Таможня",
                        url=f"{APP_BASE_URL}/customs/{q.get('id')}"
                    ))
                if customs_tasks:
                    tasks["customs"] = customs_tasks
                    total_tasks += len(customs_tasks)

        # ---- QUOTE_CONTROLLER role: quotes in pending_quote_control ----
        if "quote_controller" in roles or "admin" in roles:
            qc_quotes_response = supabase.table("quotes").select(
                "id, idn, workflow_status, customer:customers(name)"
            ).eq("organization_id", org_id).eq(
                "workflow_status", "pending_quote_control"
            ).limit(20).execute()

            if qc_quotes_response.data:
                qc_tasks = []
                for q in qc_quotes_response.data:
                    customer = q.get("customer", {})
                    qc_tasks.append(UserTask(
                        quote_id=q.get("id"),
                        quote_idn=q.get("idn", "N/A"),
                        customer_name=customer.get("name", "N/A") if customer else "N/A",
                        status="pending_quote_control",
                        status_name=_get_status_name_ru("pending_quote_control"),
                        task_type="Проверка КП",
                        url=f"{APP_BASE_URL}/quote-control/{q.get('id')}"
                    ))
                if qc_tasks:
                    tasks["quote_control"] = qc_tasks
                    total_tasks += len(qc_tasks)

        # ---- TOP_MANAGER role: pending approvals ----
        if "top_manager" in roles or "admin" in roles:
            approvals_response = supabase.table("approvals").select(
                "id, quote_id, reason, quote:quotes(idn, customer:customers(name))"
            ).eq("status", "pending").limit(20).execute()

            if approvals_response.data:
                approval_tasks = []
                for a in approvals_response.data:
                    quote = a.get("quote", {})
                    customer = quote.get("customer", {}) if quote else {}
                    approval_tasks.append(UserTask(
                        quote_id=a.get("quote_id"),
                        quote_idn=quote.get("idn", "N/A") if quote else "N/A",
                        customer_name=customer.get("name", "N/A") if customer else "N/A",
                        status="pending_approval",
                        status_name=_get_status_name_ru("pending_approval"),
                        task_type="Согласование",
                        url=f"{APP_BASE_URL}/quotes/{a.get('quote_id')}"
                    ))
                if approval_tasks:
                    tasks["approvals"] = approval_tasks
                    total_tasks += len(approval_tasks)

        return {
            "success": True,
            "user_name": user_name,
            "roles": roles,
            "tasks": tasks,
            "total_tasks": total_tasks,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error getting user tasks: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _get_status_name_ru(status: str) -> str:
    """Get Russian status name."""
    status_names = {
        "draft": "Черновик",
        "pending_procurement": "Оценка закупок",
        "pending_logistics": "Логистика",
        "pending_customs": "Таможня",
        "pending_sales_review": "Доработка",
        "pending_quote_control": "Проверка КП",
        "pending_approval": "Согласование",
        "approved": "Одобрено",
        "sent_to_client": "Отправлено клиенту",
        "client_negotiation": "Торги",
        "pending_spec_control": "Спецификация",
        "pending_signature": "Подписание",
        "deal": "Сделка",
        "rejected": "Отклонено",
        "cancelled": "Отменено",
    }
    return status_names.get(status, status)


def _format_tasks_message(tasks_data: Dict[str, Any]) -> str:
    """Format tasks data into a Telegram message.

    Args:
        tasks_data: Result from get_user_tasks()

    Returns:
        Formatted message string for Telegram
    """
    if not tasks_data.get("success"):
        return f"❌ *Ошибка*\n\n{tasks_data.get('error', 'Не удалось получить задачи')}"

    user_name = tasks_data.get("user_name", "Пользователь")
    roles = tasks_data.get("roles", [])
    tasks = tasks_data.get("tasks", {})
    total_tasks = tasks_data.get("total_tasks", 0)

    # Build message
    lines = [f"👤 *{user_name}*\n"]

    # Show roles
    if roles:
        role_names = {
            "sales": "Продажи",
            "procurement": "Закупки",
            "logistics": "Логистика",
            "customs": "Таможня",
            "quote_controller": "Контроль КП",
            "spec_controller": "Спецификации",
            "finance": "Финансы",
            "top_manager": "Руководство",
            "admin": "Администратор"
        }
        role_str = ", ".join([role_names.get(r, r) for r in roles])
        lines.append(f"🔑 Роли: {role_str}\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━\n")

    if total_tasks == 0:
        lines.append("✅ *Нет активных задач!*\n")
        lines.append("\nВсе текущие задачи выполнены.")
    else:
        lines.append(f"📋 *Активных задач: {total_tasks}*\n")

        # Task type icons
        type_icons = {
            "sales": "📝",
            "procurement": "💰",
            "logistics": "🚚",
            "customs": "🛃",
            "quote_control": "✓",
            "approvals": "⏳"
        }

        # Group names
        group_names = {
            "sales": "Мои КП",
            "procurement": "Оценка закупок",
            "logistics": "Логистика",
            "customs": "Таможня",
            "quote_control": "Проверка КП",
            "approvals": "Согласования"
        }

        for task_type, task_list in tasks.items():
            if not task_list:
                continue

            icon = type_icons.get(task_type, "📌")
            group_name = group_names.get(task_type, task_type)
            lines.append(f"\n{icon} *{group_name}* ({len(task_list)}):\n")

            # Show first 5 tasks per category
            for i, task in enumerate(task_list[:5]):
                lines.append(f"  • {task.quote_idn} — {task.customer_name}\n")
                lines.append(f"    _{task.task_type}_\n")

            if len(task_list) > 5:
                lines.append(f"  ... и ещё {len(task_list) - 5}\n")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"\n🌐 [Открыть систему]({APP_BASE_URL})")

    return "".join(lines)


async def handle_status_command(telegram_id: int) -> bool:
    """Handle the /status command - show user's current tasks.

    Feature #57: Команда /status (показать мои текущие задачи)

    This function:
    1. Checks if Telegram account is linked to a system user
    2. If not linked, shows instructions to link account
    3. If linked, queries all tasks for the user based on their roles
    4. Sends a formatted message with task summary

    Args:
        telegram_id: User's Telegram ID

    Returns:
        True if message was sent successfully
    """
    bot = get_bot()
    if not bot:
        return False

    # Check if Telegram is linked to a user
    telegram_user = await get_telegram_user(telegram_id)

    if not telegram_user:
        # Not linked - show instructions
        response_text = """📋 *Проверка статуса*

Ваш Telegram аккаунт не привязан к системе OneStack.

━━━━━━━━━━━━━━━━━━━━━━

*Как привязать:*
1. Откройте OneStack в браузере
2. Перейдите в Настройки → Telegram
3. Нажмите "Получить код привязки"
4. Отправьте код этому боту

💡 После привязки вы сможете:
• Просматривать свои задачи
• Получать уведомления
• Согласовывать КП"""

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=response_text,
                parse_mode="Markdown"
            )
            logger.info(f"Sent /status (not linked) response to {telegram_id}")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send /status response: {e}")
            return False

    # Account is linked - get user's tasks
    user_id = telegram_user.get("user_id")
    tasks_data = get_user_tasks(user_id)
    response_text = _format_tasks_message(tasks_data)

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=response_text,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        logger.info(f"Sent /status response to {telegram_id} (user_id={user_id}, tasks={tasks_data.get('total_tasks', 0)})")
        return True
    except TelegramError as e:
        logger.error(f"Failed to send /status response: {e}")
        return False


# ============================================================================
# Task Assigned Notification (Feature #58)
# ============================================================================

@dataclass
class TaskAssignedNotification:
    """Data for task_assigned notification."""
    user_id: str
    quote_id: str
    quote_idn: str
    customer_name: str
    action_required: str
    role: str  # e.g., "procurement", "logistics", "customs", etc.


async def get_user_telegram_id(user_id: str) -> Optional[int]:
    """Get the Telegram ID for a user if they have linked their account.

    Args:
        user_id: UUID of the system user

    Returns:
        Telegram ID if linked and verified, None otherwise
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return None

        response = supabase.table("telegram_users").select(
            "telegram_id"
        ).eq("user_id", user_id).eq("is_verified", True).execute()

        if response.data and len(response.data) > 0:
            telegram_id = response.data[0].get("telegram_id")
            if telegram_id and telegram_id != 0:
                return telegram_id

        return None

    except Exception as e:
        logger.error(f"Error getting Telegram ID for user {user_id}: {e}")
        return None


def record_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    channel: str = "telegram",
    quote_id: Optional[str] = None,
    deal_id: Optional[str] = None,
    sent: bool = True,
    error_message: Optional[str] = None
) -> Optional[str]:
    """Record a notification in the notifications table.

    Args:
        user_id: UUID of the recipient
        notification_type: Type of notification (e.g., "task_assigned")
        title: Short notification title
        message: Full notification message
        channel: Notification channel ("telegram", "email", "in_app")
        quote_id: Optional quote ID
        deal_id: Optional deal ID
        sent: Whether the notification was sent successfully
        error_message: Error message if sending failed

    Returns:
        UUID of the created notification record, or None if failed
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return None

        data = {
            "user_id": user_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "channel": channel,
            "sent": sent,
            "read": False
        }

        if quote_id:
            data["quote_id"] = quote_id
        if deal_id:
            data["deal_id"] = deal_id
        if error_message:
            data["error_message"] = error_message

        response = supabase.table("notifications").insert(data).execute()

        if response.data and len(response.data) > 0:
            return response.data[0].get("id")

        return None

    except Exception as e:
        logger.error(f"Error recording notification: {e}")
        return None


def _get_action_required_for_status(status: str) -> str:
    """Get action required description based on status.

    Args:
        status: Workflow status code

    Returns:
        Russian description of required action
    """
    actions = {
        "pending_procurement": "Оценить закупочные цены",
        "pending_logistics": "Рассчитать логистику",
        "pending_customs": "Рассчитать таможенные платежи",
        "pending_sales_review": "Проверить и доработать КП",
        "pending_quote_control": "Проверить и согласовать КП",
        "pending_approval": "Согласовать КП",
        "pending_spec_control": "Подготовить спецификацию",
        "pending_signature": "Получить подпись клиента",
    }
    return actions.get(status, "Обработать задачу")


async def send_task_assigned_notification(
    user_id: str,
    quote_id: str,
    quote_idn: str,
    customer_name: str,
    new_status: str,
    action_required: Optional[str] = None
) -> Dict[str, Any]:
    """Send a task_assigned notification to a user via Telegram.

    Feature #58: Отправка уведомления task_assigned

    This function:
    1. Gets the user's Telegram ID (if linked)
    2. Formats the notification message
    3. Sends via Telegram with "Open in system" button
    4. Records the notification in the database

    Args:
        user_id: UUID of the user to notify
        quote_id: UUID of the quote
        quote_idn: Quote identifier (e.g., "КП-2025-001")
        customer_name: Customer name
        new_status: The new workflow status
        action_required: Optional custom action text (defaults to status-based text)

    Returns:
        Dict with:
        - success: bool
        - telegram_sent: bool - Whether Telegram message was sent
        - notification_id: str - ID of recorded notification
        - error: str - Error message if failed

    Example:
        >>> result = await send_task_assigned_notification(
        ...     user_id="user-uuid",
        ...     quote_id="quote-uuid",
        ...     quote_idn="КП-2025-001",
        ...     customer_name="ООО Компания",
        ...     new_status="pending_procurement"
        ... )
        >>> if result["success"]:
        ...     print("Notification sent!")
    """
    # Determine action required
    action = action_required or _get_action_required_for_status(new_status)

    # Build notification content
    title = "Новая задача"
    quote_url = f"{APP_BASE_URL}/quotes/{quote_id}"

    # Format the Telegram message
    telegram_message = format_notification(
        NotificationType.TASK_ASSIGNED,
        quote_idn=quote_idn,
        customer_name=customer_name,
        action_required=action,
        quote_url=quote_url
    )

    # Try to send via Telegram
    telegram_sent = False
    telegram_error = None

    telegram_id = await get_user_telegram_id(user_id)

    if telegram_id:
        try:
            message_id = await send_notification(
                telegram_id=telegram_id,
                notification_type=NotificationType.TASK_ASSIGNED,
                quote_id=quote_id,
                quote_idn=quote_idn,
                customer_name=customer_name,
                action_required=action
            )
            telegram_sent = message_id is not None
            if not telegram_sent:
                telegram_error = "Failed to send message"
        except Exception as e:
            telegram_error = str(e)
            logger.error(f"Error sending Telegram notification to {user_id}: {e}")
    else:
        telegram_error = "User has no linked Telegram account"
        logger.info(f"User {user_id} has no linked Telegram - notification will be in-app only")

    # Record the notification in the database
    notification_id = record_notification(
        user_id=user_id,
        notification_type="task_assigned",
        title=title,
        message=f"{quote_idn} - {customer_name}\n{action}",
        channel="telegram" if telegram_sent else "in_app",
        quote_id=quote_id,
        sent=telegram_sent,
        error_message=telegram_error if not telegram_sent else None
    )

    return {
        "success": True,  # Notification recorded even if Telegram failed
        "telegram_sent": telegram_sent,
        "notification_id": notification_id,
        "telegram_id": telegram_id,
        "error": telegram_error
    }


async def notify_users_of_task_assignment(
    user_ids: List[str],
    quote_id: str,
    quote_idn: str,
    customer_name: str,
    new_status: str
) -> Dict[str, Any]:
    """Send task_assigned notifications to multiple users.

    Convenience function for notifying multiple users about a task.
    Used when a quote transitions to a status that assigns work to users.

    Args:
        user_ids: List of user UUIDs to notify
        quote_id: UUID of the quote
        quote_idn: Quote identifier
        customer_name: Customer name
        new_status: The new workflow status

    Returns:
        Dict with:
        - total: int - Total users
        - sent: int - Successfully sent via Telegram
        - failed: int - Failed to send
        - results: list - Individual results for each user

    Example:
        >>> result = await notify_users_of_task_assignment(
        ...     user_ids=["user1", "user2"],
        ...     quote_id="quote-uuid",
        ...     quote_idn="КП-2025-001",
        ...     customer_name="ООО Компания",
        ...     new_status="pending_procurement"
        ... )
        >>> print(f"Sent to {result['sent']} of {result['total']} users")
    """
    results = []
    sent_count = 0
    failed_count = 0

    for user_id in user_ids:
        result = await send_task_assigned_notification(
            user_id=user_id,
            quote_id=quote_id,
            quote_idn=quote_idn,
            customer_name=customer_name,
            new_status=new_status
        )
        results.append({
            "user_id": user_id,
            **result
        })
        if result.get("telegram_sent"):
            sent_count += 1
        else:
            failed_count += 1

    return {
        "total": len(user_ids),
        "sent": sent_count,
        "failed": failed_count,
        "results": results
    }


async def notify_role_users_of_task(
    organization_id: str,
    role_codes: List[str],
    quote_id: str,
    quote_idn: str,
    customer_name: str,
    new_status: str
) -> Dict[str, Any]:
    """Send task_assigned notifications to all users with specific roles.

    Used when a quote transitions to a status where all users with certain
    roles should be notified (e.g., logistics, customs, quote_controller).

    Args:
        organization_id: UUID of the organization
        role_codes: List of role codes to notify (e.g., ["logistics", "admin"])
        quote_id: UUID of the quote
        quote_idn: Quote identifier
        customer_name: Customer name
        new_status: The new workflow status

    Returns:
        Dict with notification results

    Example:
        >>> result = await notify_role_users_of_task(
        ...     organization_id="org-uuid",
        ...     role_codes=["logistics"],
        ...     quote_id="quote-uuid",
        ...     quote_idn="КП-2025-001",
        ...     customer_name="ООО Компания",
        ...     new_status="pending_logistics"
        ... )
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {
                "total": 0,
                "sent": 0,
                "failed": 0,
                "error": "Database connection error"
            }

        # Get all users with the specified roles in this organization
        user_ids = set()

        for role_code in role_codes:
            # Get role ID
            role_response = supabase.table("roles").select("id").eq("code", role_code).execute()
            if not role_response.data:
                continue

            role_id = role_response.data[0].get("id")

            # Get users with this role
            users_response = supabase.table("user_roles").select(
                "user_id"
            ).eq("organization_id", organization_id).eq("role_id", role_id).execute()

            if users_response.data:
                for u in users_response.data:
                    user_ids.add(u.get("user_id"))

        if not user_ids:
            logger.info(f"No users found with roles {role_codes} in org {organization_id}")
            return {
                "total": 0,
                "sent": 0,
                "failed": 0,
                "error": None
            }

        # Send notifications to all found users
        return await notify_users_of_task_assignment(
            user_ids=list(user_ids),
            quote_id=quote_id,
            quote_idn=quote_idn,
            customer_name=customer_name,
            new_status=new_status
        )

    except Exception as e:
        logger.error(f"Error notifying role users: {e}")
        return {
            "total": 0,
            "sent": 0,
            "failed": 0,
            "error": str(e)
        }


# ============================================================================
# Approval Required Notification (Feature #59)
# ============================================================================

@dataclass
class ApprovalRequiredNotification:
    """Data for approval_required notification."""
    quote_id: str
    quote_idn: str
    customer_name: str
    total_amount: str  # Formatted total (e.g., "1 000 000 RUB")
    approval_reason: str  # Why approval is needed
    markup_percent: str  # Current markup percentage
    payment_terms: str  # Payment conditions
    requested_by: str  # Who requested the approval
    organization_id: str


async def send_approval_required_notification(
    organization_id: str,
    quote_id: str,
    quote_idn: str,
    customer_name: str,
    total_amount: str,
    approval_reason: str,
    markup_percent: str = "N/A",
    payment_terms: str = "N/A",
    requested_by: str = "Система"
) -> Dict[str, Any]:
    """Send approval_required notifications to all top managers in the organization.

    Feature #59: Отправка уведомления approval_required (уведомление топ-менеджеру с кнопками)

    This function:
    1. Gets all users with top_manager or admin role in the organization
    2. Sends Telegram notifications with inline approve/reject buttons
    3. Records notifications in the database

    Args:
        organization_id: UUID of the organization
        quote_id: UUID of the quote
        quote_idn: Quote identifier (e.g., "КП-2025-001")
        customer_name: Customer name
        total_amount: Formatted total amount (e.g., "1 000 000 RUB")
        approval_reason: Why approval is required (e.g., "Валюта в рублях")
        markup_percent: Markup percentage (e.g., "15")
        payment_terms: Payment conditions (e.g., "50% предоплата")
        requested_by: Name of person who requested approval

    Returns:
        Dict with:
        - success: bool
        - total_managers: int - Number of top managers found
        - telegram_sent: int - Successfully sent via Telegram
        - failed: int - Failed to send
        - results: list - Individual results for each manager

    Example:
        >>> result = await send_approval_required_notification(
        ...     organization_id="org-uuid",
        ...     quote_id="quote-uuid",
        ...     quote_idn="КП-2025-001",
        ...     customer_name="ООО Компания",
        ...     total_amount="1 500 000 USD",
        ...     approval_reason="Валюта в рублях, Наценка ниже 15%",
        ...     markup_percent="12",
        ...     payment_terms="30% предоплата, 70% по отгрузке"
        ... )
        >>> print(f"Sent to {result['telegram_sent']} of {result['total_managers']} managers")
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {
                "success": False,
                "total_managers": 0,
                "telegram_sent": 0,
                "failed": 0,
                "error": "Database connection error"
            }

        # Get users with top_manager or admin role
        manager_user_ids = set()

        for role_code in ["top_manager", "admin"]:
            # Get role ID
            role_response = supabase.table("roles").select("id").eq("code", role_code).execute()
            if not role_response.data:
                continue

            role_id = role_response.data[0].get("id")

            # Get users with this role in the organization
            users_response = supabase.table("user_roles").select(
                "user_id"
            ).eq("organization_id", organization_id).eq("role_id", role_id).execute()

            if users_response.data:
                for u in users_response.data:
                    manager_user_ids.add(u.get("user_id"))

        if not manager_user_ids:
            logger.warning(f"No top_manager/admin users found in org {organization_id} for approval notification")
            return {
                "success": True,  # Not an error, just no managers
                "total_managers": 0,
                "telegram_sent": 0,
                "failed": 0,
                "error": None,
                "warning": "No top_manager or admin users found in organization"
            }

        # Send notifications to each manager
        results = []
        sent_count = 0
        failed_count = 0
        title = "Требуется согласование"

        for user_id in manager_user_ids:
            telegram_sent = False
            telegram_error = None
            notification_id = None

            # Get user's Telegram ID
            telegram_id = await get_user_telegram_id(user_id)

            if telegram_id:
                try:
                    # Send using the existing send_approval_request function
                    message_id = await send_approval_request(
                        telegram_id=telegram_id,
                        quote_id=quote_id,
                        quote_idn=quote_idn,
                        customer_name=customer_name,
                        total_amount=total_amount,
                        approval_reason=approval_reason,
                        markup=markup_percent,
                        payment_terms=payment_terms
                    )
                    telegram_sent = message_id is not None
                    if not telegram_sent:
                        telegram_error = "Failed to send message"
                except Exception as e:
                    telegram_error = str(e)
                    logger.error(f"Error sending approval notification to manager {user_id}: {e}")
            else:
                telegram_error = "User has no linked Telegram account"
                logger.info(f"Manager {user_id} has no linked Telegram - notification will be in-app only")

            # Record the notification in database
            notification_id = record_notification(
                user_id=user_id,
                notification_type="approval_required",
                title=title,
                message=f"{quote_idn} - {customer_name}\n{approval_reason}\nСумма: {total_amount}",
                channel="telegram" if telegram_sent else "in_app",
                quote_id=quote_id,
                sent=telegram_sent,
                error_message=telegram_error if not telegram_sent else None
            )

            if telegram_sent:
                sent_count += 1
            else:
                failed_count += 1

            results.append({
                "user_id": user_id,
                "telegram_id": telegram_id,
                "telegram_sent": telegram_sent,
                "notification_id": notification_id,
                "error": telegram_error
            })

        logger.info(f"Approval notification sent: {sent_count}/{len(manager_user_ids)} managers for quote {quote_idn}")

        return {
            "success": True,
            "total_managers": len(manager_user_ids),
            "telegram_sent": sent_count,
            "failed": failed_count,
            "results": results,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error sending approval notifications: {e}")
        return {
            "success": False,
            "total_managers": 0,
            "telegram_sent": 0,
            "failed": 0,
            "error": str(e)
        }


async def send_approval_notification_for_quote(
    quote_id: str,
    approval_reason: str,
    requested_by_user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to send approval notification for a quote.

    This function loads quote details from the database and sends approval
    notifications to all top managers. Use this when you have just the quote_id.

    Args:
        quote_id: UUID of the quote
        approval_reason: Why approval is required
        requested_by_user_id: Optional user ID who requested the approval

    Returns:
        Result of send_approval_required_notification

    Example:
        >>> result = await send_approval_notification_for_quote(
        ...     quote_id="quote-uuid",
        ...     approval_reason="Валюта в рублях",
        ...     requested_by_user_id="user-uuid"
        ... )
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {
                "success": False,
                "error": "Database connection error"
            }

        # Get quote details
        quote_response = supabase.table("quotes").select(
            "id, idn, organization_id, total_client_price, currency, payment_condition_prepayment, customer:customers(name)"
        ).eq("id", quote_id).execute()

        if not quote_response.data or len(quote_response.data) == 0:
            return {
                "success": False,
                "error": f"Quote {quote_id} not found"
            }

        quote = quote_response.data[0]
        organization_id = quote.get("organization_id")
        quote_idn = quote.get("idn", "N/A")
        customer = quote.get("customer", {})
        customer_name = customer.get("name", "N/A") if customer else "N/A"

        # Format total amount
        total_price = quote.get("total_client_price", 0) or 0
        currency = quote.get("currency", "USD")
        total_amount = f"{total_price:,.0f} {currency}".replace(",", " ")

        # Get markup (calculate from quote_calculation_variables or default)
        # For now, use payment condition as payment_terms
        prepayment = quote.get("payment_condition_prepayment", 100)
        payment_terms = f"{prepayment}% предоплата"

        # Get requester name
        requested_by = "Система"
        if requested_by_user_id:
            profile_response = supabase.table("profiles").select(
                "full_name, email"
            ).eq("id", requested_by_user_id).execute()
            if profile_response.data and len(profile_response.data) > 0:
                profile = profile_response.data[0]
                requested_by = profile.get("full_name") or profile.get("email", "Система")

        # Try to get markup from calculation variables
        markup_percent = "N/A"
        calc_response = supabase.table("quote_calculation_variables").select(
            "markup_percent"
        ).eq("quote_id", quote_id).execute()
        if calc_response.data and len(calc_response.data) > 0:
            mp = calc_response.data[0].get("markup_percent")
            if mp is not None:
                markup_percent = str(mp)

        return await send_approval_required_notification(
            organization_id=organization_id,
            quote_id=quote_id,
            quote_idn=quote_idn,
            customer_name=customer_name,
            total_amount=total_amount,
            approval_reason=approval_reason,
            markup_percent=markup_percent,
            payment_terms=payment_terms,
            requested_by=requested_by
        )

    except Exception as e:
        logger.error(f"Error sending approval notification for quote {quote_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Approve Callback Handler (Feature #60)
# ============================================================================

@dataclass
class ApprovalCallbackResult:
    """Result of processing an approval callback."""
    success: bool
    quote_id: str
    quote_idn: str = ""
    action: str = ""  # "approved" or "rejected"
    message: str = ""  # Message to display to the user
    error: Optional[str] = None
    new_status: Optional[str] = None


async def handle_approve_callback(
    telegram_id: int,
    quote_id: str
) -> ApprovalCallbackResult:
    """Handle the 'approve' inline button callback from Telegram.

    Feature #60: Inline-кнопка Согласовать (Callback handler для approve_{quote_id})

    This function:
    1. Checks if Telegram account is linked and verified
    2. Gets the user's roles in the organization
    3. Verifies they have top_manager or admin role
    4. Checks the quote is in pending_approval status
    5. Transitions the quote to approved status
    6. Updates the original Telegram message to show success

    Args:
        telegram_id: Telegram user ID who pressed the button
        quote_id: UUID of the quote to approve

    Returns:
        ApprovalCallbackResult with success status and details

    Example:
        >>> result = await handle_approve_callback(12345678, "quote-uuid")
        >>> if result.success:
        ...     print(f"Quote {result.quote_idn} approved!")
    """
    from services.workflow_service import (
        transition_quote_status,
        WorkflowStatus,
        get_quote_workflow_status
    )
    from services.role_service import get_user_role_codes

    try:
        supabase = get_supabase()
        if not supabase:
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                action="approved",
                error="Database connection error",
                message="❌ Ошибка подключения к базе данных"
            )

        # Step 1: Check if Telegram account is linked
        telegram_user = await get_telegram_user(telegram_id)
        if not telegram_user:
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                action="approved",
                error="Telegram account not linked",
                message="❌ Ваш Telegram аккаунт не привязан к системе.\n\nИспользуйте /start для инструкций по привязке."
            )

        user_id = telegram_user.get("user_id")
        logger.info(f"Approve callback: telegram_id={telegram_id}, user_id={user_id}, quote_id={quote_id}")

        # Step 2: Get quote details to verify organization
        quote_response = supabase.table("quotes").select(
            "id, idn, organization_id, workflow_status, customer:customers(name)"
        ).eq("id", quote_id).execute()

        if not quote_response.data or len(quote_response.data) == 0:
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                action="approved",
                error="Quote not found",
                message="❌ КП не найдено в системе"
            )

        quote = quote_response.data[0]
        org_id = quote.get("organization_id")
        quote_idn = quote.get("idn", "N/A")
        current_status = quote.get("workflow_status")
        customer = quote.get("customer", {})
        customer_name = customer.get("name", "N/A") if customer else "N/A"

        # Step 3: Check user's roles in the organization
        user_roles = get_user_role_codes(user_id, org_id)

        # Step 4: Verify user has top_manager or admin role
        if not any(role in ["top_manager", "admin"] for role in user_roles):
            logger.warning(f"User {user_id} tried to approve quote {quote_id} without permission. Roles: {user_roles}")
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="approved",
                error="Permission denied",
                message="❌ У вас нет прав на согласование КП.\n\nТребуется роль: топ-менеджер или администратор"
            )

        # Step 5: Check quote is in pending_approval status
        if current_status != WorkflowStatus.PENDING_APPROVAL.value:
            status_name = _get_status_name_ru(current_status)
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="approved",
                error=f"Invalid status: {current_status}",
                message=f"❌ КП не может быть согласовано\n\nТекущий статус: {status_name}\n\nТребуется статус: Ожидает согласования"
            )

        # Step 6: Transition to approved status
        result = transition_quote_status(
            quote_id=quote_id,
            to_status=WorkflowStatus.APPROVED,
            actor_id=user_id,
            actor_roles=user_roles,
            comment="Согласовано через Telegram"
        )

        if result.success:
            logger.info(f"Quote {quote_id} approved by user {user_id} via Telegram")
            return ApprovalCallbackResult(
                success=True,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="approved",
                message=f"✅ КП {quote_idn} успешно согласовано!\n\nКлиент: {customer_name}\n\nТеперь КП можно отправить клиенту.",
                new_status=WorkflowStatus.APPROVED.value
            )
        else:
            logger.error(f"Failed to approve quote {quote_id}: {result.error_message}")
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="approved",
                error=result.error_message,
                message=f"❌ Ошибка при согласовании КП\n\n{result.error_message}"
            )

    except Exception as e:
        logger.error(f"Error handling approve callback for quote {quote_id}: {e}")
        return ApprovalCallbackResult(
            success=False,
            quote_id=quote_id,
            action="approved",
            error=str(e),
            message=f"❌ Произошла ошибка: {str(e)}"
        )


async def send_callback_response(
    telegram_id: int,
    message_id: int,
    result: ApprovalCallbackResult
) -> bool:
    """Send response to a callback and update the original message.

    This function updates the original approval request message to show
    the result of the approval action.

    Args:
        telegram_id: Telegram user ID
        message_id: ID of the original message to edit
        result: ApprovalCallbackResult from handle_approve_callback

    Returns:
        True if message was updated successfully
    """
    bot = get_bot()
    if not bot:
        return False

    # Build the updated message
    if result.success:
        if result.action == "approved":
            emoji = "✅"
            decision = "СОГЛАСОВАНО"
        else:  # rejected
            emoji = "❌"
            decision = "ОТКЛОНЕНО"

        updated_text = f"""{emoji} *{decision}*

КП: {result.quote_idn}
{result.message.replace(f"✅ КП {result.quote_idn} успешно согласовано!", "").strip()}"""
    else:
        updated_text = f"""⚠️ *Ошибка обработки*

{result.message}"""

    # Try to edit the original message (remove inline buttons)
    try:
        await bot.edit_message_text(
            chat_id=telegram_id,
            message_id=message_id,
            text=updated_text,
            parse_mode="Markdown"
        )
        logger.info(f"Updated callback response message {message_id} for user {telegram_id}")
        return True
    except TelegramError as e:
        # If edit fails (e.g., message too old), send a new message
        logger.warning(f"Failed to edit message {message_id}, sending new: {e}")
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=result.message,
                parse_mode="Markdown"
            )
            return True
        except TelegramError as e2:
            logger.error(f"Failed to send callback response: {e2}")
            return False


# ============================================================================
# Reject Callback Handler (Feature #61)
# ============================================================================

async def handle_reject_callback(
    telegram_id: int,
    quote_id: str
) -> ApprovalCallbackResult:
    """Handle the 'reject' inline button callback from Telegram.

    Feature #61: Inline-кнопка Отклонить (Callback handler для reject_{quote_id})

    This function:
    1. Checks if Telegram account is linked and verified
    2. Gets the user's roles in the organization
    3. Verifies they have top_manager or admin role
    4. Checks the quote is in pending_approval status
    5. Transitions the quote to rejected status

    Note: Since Telegram inline buttons don't support input, we use a default
    rejection comment. The quote can be further reviewed in the web interface.

    Args:
        telegram_id: Telegram user ID who pressed the button
        quote_id: UUID of the quote to reject

    Returns:
        ApprovalCallbackResult with success status and details

    Example:
        >>> result = await handle_reject_callback(12345678, "quote-uuid")
        >>> if result.success:
        ...     print(f"Quote {result.quote_idn} rejected!")
    """
    from services.workflow_service import (
        transition_quote_status,
        WorkflowStatus,
        get_quote_workflow_status
    )
    from services.role_service import get_user_role_codes

    try:
        supabase = get_supabase()
        if not supabase:
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                action="rejected",
                error="Database connection error",
                message="❌ Ошибка подключения к базе данных"
            )

        # Step 1: Check if Telegram account is linked
        telegram_user = await get_telegram_user(telegram_id)
        if not telegram_user:
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                action="rejected",
                error="Telegram account not linked",
                message="❌ Ваш Telegram аккаунт не привязан к системе.\n\nИспользуйте /start для инструкций по привязке."
            )

        user_id = telegram_user.get("user_id")
        logger.info(f"Reject callback: telegram_id={telegram_id}, user_id={user_id}, quote_id={quote_id}")

        # Step 2: Get quote details to verify organization
        quote_response = supabase.table("quotes").select(
            "id, idn, organization_id, workflow_status, customer:customers(name)"
        ).eq("id", quote_id).execute()

        if not quote_response.data or len(quote_response.data) == 0:
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                action="rejected",
                error="Quote not found",
                message="❌ КП не найдено в системе"
            )

        quote = quote_response.data[0]
        org_id = quote.get("organization_id")
        quote_idn = quote.get("idn", "N/A")
        current_status = quote.get("workflow_status")
        customer = quote.get("customer", {})
        customer_name = customer.get("name", "N/A") if customer else "N/A"

        # Step 3: Check user's roles in the organization
        user_roles = get_user_role_codes(user_id, org_id)

        # Step 4: Verify user has top_manager or admin role
        if not any(role in ["top_manager", "admin"] for role in user_roles):
            logger.warning(f"User {user_id} tried to reject quote {quote_id} without permission. Roles: {user_roles}")
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="rejected",
                error="Permission denied",
                message="❌ У вас нет прав на отклонение КП.\n\nТребуется роль: топ-менеджер или администратор"
            )

        # Step 5: Check quote is in pending_approval status
        if current_status != WorkflowStatus.PENDING_APPROVAL.value:
            status_name = _get_status_name_ru(current_status)
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="rejected",
                error=f"Invalid status: {current_status}",
                message=f"❌ КП не может быть отклонено\n\nТекущий статус: {status_name}\n\nТребуется статус: Ожидает согласования"
            )

        # Step 6: Transition to rejected status
        # Note: Rejection requires a comment per workflow rules,
        # so we provide a default comment for Telegram rejections
        result = transition_quote_status(
            quote_id=quote_id,
            to_status=WorkflowStatus.REJECTED,
            actor_id=user_id,
            actor_roles=user_roles,
            comment="Отклонено через Telegram. Для уточнения причины обратитесь к руководителю."
        )

        if result.success:
            logger.info(f"Quote {quote_id} rejected by user {user_id} via Telegram")
            return ApprovalCallbackResult(
                success=True,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="rejected",
                message=f"❌ КП {quote_idn} отклонено\n\nКлиент: {customer_name}\n\nДля уточнения причины обратитесь к руководителю.",
                new_status=WorkflowStatus.REJECTED.value
            )
        else:
            logger.error(f"Failed to reject quote {quote_id}: {result.error_message}")
            return ApprovalCallbackResult(
                success=False,
                quote_id=quote_id,
                quote_idn=quote_idn,
                action="rejected",
                error=result.error_message,
                message=f"❌ Ошибка при отклонении КП\n\n{result.error_message}"
            )

    except Exception as e:
        logger.error(f"Error handling reject callback for quote {quote_id}: {e}")
        return ApprovalCallbackResult(
            success=False,
            quote_id=quote_id,
            action="rejected",
            error=str(e),
            message=f"❌ Произошла ошибка: {str(e)}"
        )


# ============================================================================
# Status Changed Notification (Feature #62)
# ============================================================================

@dataclass
class StatusChangedNotification:
    """Data for status_changed notification."""
    quote_id: str
    quote_idn: str
    customer_name: str
    old_status: str  # Previous workflow status
    new_status: str  # New workflow status
    old_status_name: str  # Human-readable previous status
    new_status_name: str  # Human-readable new status
    actor_name: str  # Who made the change
    comment: Optional[str] = None  # Optional transition comment


async def send_status_changed_notification(
    user_id: str,
    quote_id: str,
    quote_idn: str,
    customer_name: str,
    old_status: str,
    new_status: str,
    actor_name: str,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """Send a status_changed notification to a user via Telegram.

    Feature #62: Уведомление status_changed (notification when quote status changes)

    This function:
    1. Gets the user's Telegram ID (if linked)
    2. Formats the notification message with old and new status
    3. Sends via Telegram with "Open in system" button
    4. Records the notification in the database

    Args:
        user_id: UUID of the user to notify
        quote_id: UUID of the quote
        quote_idn: Quote identifier (e.g., "КП-2025-001")
        customer_name: Customer name
        old_status: Previous workflow status code
        new_status: New workflow status code
        actor_name: Name of the person who made the change
        comment: Optional transition comment

    Returns:
        Dict with:
        - success: bool
        - telegram_sent: bool - Whether Telegram message was sent
        - notification_id: str - ID of recorded notification
        - error: str - Error message if failed

    Example:
        >>> result = await send_status_changed_notification(
        ...     user_id="user-uuid",
        ...     quote_id="quote-uuid",
        ...     quote_idn="КП-2025-001",
        ...     customer_name="ООО Компания",
        ...     old_status="pending_quote_control",
        ...     new_status="approved",
        ...     actor_name="Иванов И.И."
        ... )
        >>> if result["success"]:
        ...     print("Notification sent!")
    """
    # Get human-readable status names
    old_status_name = _get_status_name_ru(old_status)
    new_status_name = _get_status_name_ru(new_status)

    # Build notification content
    title = "Статус изменён"
    quote_url = f"{APP_BASE_URL}/quotes/{quote_id}"

    # Format the Telegram message using the template
    telegram_message = format_notification(
        NotificationType.STATUS_CHANGED,
        quote_idn=quote_idn,
        new_status=new_status_name,
        actor_name=actor_name,
        quote_url=quote_url
    )

    # Add comment if provided
    if comment:
        telegram_message += f"\n💬 _Комментарий:_ {comment}"

    # Try to send via Telegram
    telegram_sent = False
    telegram_error = None
    telegram_id = await get_user_telegram_id(user_id)

    if telegram_id:
        try:
            # Use send_notification which adds the "Open in system" button
            message_id = await send_notification(
                telegram_id=telegram_id,
                notification_type=NotificationType.STATUS_CHANGED,
                quote_id=quote_id,
                quote_idn=quote_idn,
                customer_name=customer_name,
                new_status=new_status_name,
                actor_name=actor_name
            )
            telegram_sent = message_id is not None
            if not telegram_sent:
                telegram_error = "Failed to send message"
        except Exception as e:
            telegram_error = str(e)
            logger.error(f"Error sending status_changed notification to {user_id}: {e}")
    else:
        telegram_error = "User has no linked Telegram account"
        logger.info(f"User {user_id} has no linked Telegram - notification will be in-app only")

    # Record the notification in the database
    db_message = f"{quote_idn} - {customer_name}\n{old_status_name} → {new_status_name}"
    if comment:
        db_message += f"\nКомментарий: {comment}"

    notification_id = record_notification(
        user_id=user_id,
        notification_type="status_changed",
        title=title,
        message=db_message,
        channel="telegram" if telegram_sent else "in_app",
        quote_id=quote_id,
        sent=telegram_sent,
        error_message=telegram_error if not telegram_sent else None
    )

    return {
        "success": True,  # Notification recorded even if Telegram failed
        "telegram_sent": telegram_sent,
        "notification_id": notification_id,
        "telegram_id": telegram_id,
        "error": telegram_error
    }


async def notify_quote_creator_of_status_change(
    quote_id: str,
    old_status: str,
    new_status: str,
    actor_id: str,
    actor_name: Optional[str] = None,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """Send status_changed notification to the quote creator.

    This is the main convenience function for status change notifications.
    It fetches quote details from DB and notifies the creator.

    Args:
        quote_id: UUID of the quote
        old_status: Previous workflow status code
        new_status: New workflow status code
        actor_id: UUID of the user who made the change
        actor_name: Optional name of actor (fetched from DB if not provided)
        comment: Optional transition comment

    Returns:
        Dict with notification result

    Example:
        >>> result = await notify_quote_creator_of_status_change(
        ...     quote_id="quote-uuid",
        ...     old_status="pending_quote_control",
        ...     new_status="approved",
        ...     actor_id="actor-uuid"
        ... )
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {
                "success": False,
                "error": "Database connection error"
            }

        # Get quote details including creator
        quote_response = supabase.table("quotes").select(
            "id, idn, created_by, organization_id, customer:customers(name)"
        ).eq("id", quote_id).execute()

        if not quote_response.data:
            logger.warning(f"Quote {quote_id} not found for status change notification")
            return {
                "success": False,
                "error": "Quote not found"
            }

        quote = quote_response.data[0]
        quote_idn = quote.get("idn", "N/A")
        creator_id = quote.get("created_by")
        customer = quote.get("customer", {})
        customer_name = customer.get("name", "N/A") if customer else "N/A"

        # Don't notify the actor themselves (they know they made the change)
        if creator_id == actor_id:
            logger.info(f"Skipping status change notification - actor is the creator")
            return {
                "success": True,
                "skipped": True,
                "reason": "Actor is the creator"
            }

        # Get actor name if not provided
        if not actor_name:
            actor_response = supabase.table("organization_members").select(
                "full_name"
            ).eq("user_id", actor_id).execute()

            if actor_response.data:
                actor_name = actor_response.data[0].get("full_name", "Пользователь")
            else:
                actor_name = "Пользователь"

        # Send the notification
        return await send_status_changed_notification(
            user_id=creator_id,
            quote_id=quote_id,
            quote_idn=quote_idn,
            customer_name=customer_name,
            old_status=old_status,
            new_status=new_status,
            actor_name=actor_name,
            comment=comment
        )

    except Exception as e:
        logger.error(f"Error notifying creator of status change for quote {quote_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def notify_assigned_users_of_status_change(
    quote_id: str,
    old_status: str,
    new_status: str,
    actor_id: str,
    actor_name: Optional[str] = None,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """Send status_changed notifications to all assigned users on a quote.

    This notifies:
    - Quote creator
    - Assigned procurement users
    - Assigned logistics user
    - Assigned customs user

    Skips the actor (they don't need to be notified of their own action).

    Args:
        quote_id: UUID of the quote
        old_status: Previous workflow status code
        new_status: New workflow status code
        actor_id: UUID of the user who made the change
        actor_name: Optional name of actor
        comment: Optional transition comment

    Returns:
        Dict with:
        - total: int - Total users to notify
        - sent: int - Successfully sent via Telegram
        - failed: int - Failed to send
        - skipped: int - Skipped (e.g., actor themselves)
        - results: list - Individual results for each user

    Example:
        >>> result = await notify_assigned_users_of_status_change(
        ...     quote_id="quote-uuid",
        ...     old_status="pending_logistics",
        ...     new_status="pending_sales_review",
        ...     actor_id="actor-uuid"
        ... )
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {
                "total": 0,
                "sent": 0,
                "failed": 0,
                "skipped": 0,
                "error": "Database connection error"
            }

        # Get quote details with all assigned users
        quote_response = supabase.table("quotes").select(
            "id, idn, created_by, organization_id, "
            "assigned_procurement_users, assigned_logistics_user, assigned_customs_user, "
            "customer:customers(name)"
        ).eq("id", quote_id).execute()

        if not quote_response.data:
            logger.warning(f"Quote {quote_id} not found for status change notifications")
            return {
                "total": 0,
                "sent": 0,
                "failed": 0,
                "skipped": 0,
                "error": "Quote not found"
            }

        quote = quote_response.data[0]
        quote_idn = quote.get("idn", "N/A")
        customer = quote.get("customer", {})
        customer_name = customer.get("name", "N/A") if customer else "N/A"

        # Collect all user IDs to notify (excluding actor)
        user_ids_to_notify = set()

        # Add creator
        creator_id = quote.get("created_by")
        if creator_id and creator_id != actor_id:
            user_ids_to_notify.add(creator_id)

        # Add procurement users
        procurement_users = quote.get("assigned_procurement_users") or []
        for user_id in procurement_users:
            if user_id and user_id != actor_id:
                user_ids_to_notify.add(user_id)

        # Add logistics user
        logistics_user = quote.get("assigned_logistics_user")
        if logistics_user and logistics_user != actor_id:
            user_ids_to_notify.add(logistics_user)

        # Add customs user
        customs_user = quote.get("assigned_customs_user")
        if customs_user and customs_user != actor_id:
            user_ids_to_notify.add(customs_user)

        if not user_ids_to_notify:
            logger.info(f"No users to notify for status change on quote {quote_id}")
            return {
                "total": 0,
                "sent": 0,
                "failed": 0,
                "skipped": 1,  # Actor was the only one
                "results": []
            }

        # Get actor name if not provided
        if not actor_name:
            actor_response = supabase.table("organization_members").select(
                "full_name"
            ).eq("user_id", actor_id).execute()

            if actor_response.data:
                actor_name = actor_response.data[0].get("full_name", "Пользователь")
            else:
                actor_name = "Пользователь"

        # Send notifications to all users
        results = []
        sent_count = 0
        failed_count = 0

        for user_id in user_ids_to_notify:
            result = await send_status_changed_notification(
                user_id=user_id,
                quote_id=quote_id,
                quote_idn=quote_idn,
                customer_name=customer_name,
                old_status=old_status,
                new_status=new_status,
                actor_name=actor_name,
                comment=comment
            )
            results.append({
                "user_id": user_id,
                **result
            })
            if result.get("telegram_sent"):
                sent_count += 1
            elif result.get("success"):
                failed_count += 1  # In-app notification recorded

        return {
            "total": len(user_ids_to_notify),
            "sent": sent_count,
            "failed": failed_count,
            "skipped": 1 if actor_id in [creator_id, logistics_user, customs_user] or actor_id in procurement_users else 0,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error notifying assigned users of status change for quote {quote_id}: {e}")
        return {
            "total": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "error": str(e)
        }


# ============================================================================
# Returned for Revision Notification (Feature #63)
# ============================================================================

@dataclass
class ReturnedForRevisionNotification:
    """Data for returned_for_revision notification."""
    quote_id: str
    quote_idn: str
    customer_name: str
    actor_name: str  # Who returned the quote (quote_controller)
    comment: str  # Reason for return (required)


async def send_returned_for_revision_notification(
    user_id: str,
    quote_id: str,
    quote_idn: str,
    customer_name: str,
    actor_name: str,
    comment: str
) -> Dict[str, Any]:
    """Send a returned_for_revision notification to a user via Telegram.

    Feature #63: Уведомление returned_for_revision (notification when quote is returned for revision)

    This is sent when a quote_controller returns a quote to the sales manager
    for revision. The notification includes:
    - The quote identifier
    - The reason (comment) for the return
    - Who returned it

    Args:
        user_id: UUID of the user to notify (typically the quote creator)
        quote_id: UUID of the quote
        quote_idn: Quote identifier (e.g., "КП-2025-001")
        customer_name: Customer name
        actor_name: Name of the person who returned the quote
        comment: Reason for the return (from quote_controller)

    Returns:
        Dict with:
        - success: bool
        - telegram_sent: bool - Whether Telegram message was sent
        - notification_id: str - ID of recorded notification
        - error: str - Error message if failed

    Example:
        >>> result = await send_returned_for_revision_notification(
        ...     user_id="user-uuid",
        ...     quote_id="quote-uuid",
        ...     quote_idn="КП-2025-001",
        ...     customer_name="ООО Компания",
        ...     actor_name="Петрова А.В.",
        ...     comment="Необходимо уточнить условия оплаты"
        ... )
        >>> if result["success"]:
        ...     print("Creator notified about return!")
    """
    # Build notification content
    title = "Возвращено на доработку"
    quote_url = f"{APP_BASE_URL}/quotes/{quote_id}"

    # Format the Telegram message using the template
    telegram_message = format_notification(
        NotificationType.RETURNED_FOR_REVISION,
        quote_idn=quote_idn,
        comment=comment,
        actor_name=actor_name,
        quote_url=quote_url
    )

    # Try to send via Telegram
    telegram_sent = False
    telegram_error = None
    telegram_id = await get_user_telegram_id(user_id)

    if telegram_id:
        try:
            # Send message with "Open in system" button
            bot = get_bot()
            if bot:
                keyboard = build_open_quote_keyboard(quote_id)
                sent_msg = await bot.send_message(
                    chat_id=telegram_id,
                    text=telegram_message,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                telegram_sent = sent_msg is not None
                if not telegram_sent:
                    telegram_error = "Failed to send message"
            else:
                telegram_error = "Bot not configured"
        except Exception as e:
            telegram_error = str(e)
            logger.error(f"Error sending returned_for_revision notification to {user_id}: {e}")
    else:
        telegram_error = "User has no linked Telegram account"
        logger.info(f"User {user_id} has no linked Telegram - notification will be in-app only")

    # Record the notification in the database
    db_message = f"{quote_idn} - {customer_name}\nВозвращено: {actor_name}\nПричина: {comment}"

    notification_id = record_notification(
        user_id=user_id,
        notification_type="returned_for_revision",
        title=title,
        message=db_message,
        channel="telegram" if telegram_sent else "in_app",
        quote_id=quote_id,
        sent=telegram_sent,
        error_message=telegram_error if not telegram_sent else None
    )

    return {
        "success": True,  # Notification recorded even if Telegram failed
        "telegram_sent": telegram_sent,
        "notification_id": notification_id,
        "telegram_id": telegram_id,
        "error": telegram_error
    }


async def notify_creator_of_return(
    quote_id: str,
    actor_id: str,
    comment: str,
    actor_name: Optional[str] = None
) -> Dict[str, Any]:
    """Send returned_for_revision notification to the quote creator.

    This is the main convenience function for return notifications.
    It fetches quote details from DB and notifies the creator.

    Args:
        quote_id: UUID of the quote
        actor_id: UUID of the user who returned the quote (quote_controller)
        comment: Reason for the return
        actor_name: Optional name of actor (fetched from DB if not provided)

    Returns:
        Dict with notification result

    Example:
        >>> import asyncio
        >>> result = asyncio.run(notify_creator_of_return(
        ...     quote_id="quote-uuid",
        ...     actor_id="controller-uuid",
        ...     comment="Проверьте наценку на позиции 3 и 7"
        ... ))
        >>> if result["success"]:
        ...     print("Creator notified!")
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {
                "success": False,
                "error": "Database connection error"
            }

        # Get quote details including creator
        quote_response = supabase.table("quotes").select(
            "id, idn, created_by, organization_id, customer:customers(name)"
        ).eq("id", quote_id).execute()

        if not quote_response.data:
            logger.warning(f"Quote {quote_id} not found for return notification")
            return {
                "success": False,
                "error": "Quote not found"
            }

        quote = quote_response.data[0]
        quote_idn = quote.get("idn", "N/A")
        creator_id = quote.get("created_by")
        customer = quote.get("customer", {})
        customer_name = customer.get("name", "N/A") if customer else "N/A"

        if not creator_id:
            logger.warning(f"Quote {quote_id} has no creator - cannot send return notification")
            return {
                "success": False,
                "error": "Quote has no creator"
            }

        # Get actor name if not provided
        if not actor_name:
            actor_response = supabase.table("organization_members").select(
                "full_name"
            ).eq("user_id", actor_id).execute()

            if actor_response.data:
                actor_name = actor_response.data[0].get("full_name", "Контроллер КП")
            else:
                actor_name = "Контроллер КП"

        # Send the notification
        return await send_returned_for_revision_notification(
            user_id=creator_id,
            quote_id=quote_id,
            quote_idn=quote_idn,
            customer_name=customer_name,
            actor_name=actor_name,
            comment=comment
        )

    except Exception as e:
        logger.error(f"Error notifying creator of return for quote {quote_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Admin Bug Reports
# ============================================================================

ADMIN_TELEGRAM_CHAT_ID = os.getenv("ADMIN_TELEGRAM_CHAT_ID", "")


async def send_admin_bug_report(
    short_id: str,
    user_name: str,
    user_email: str,
    org_name: str,
    page_url: str,
    feedback_type: str,
    description: str,
    debug_context: dict = None,
    screenshot_data: str = None,
    clickup_task_id: str = None
) -> bool:
    """Send bug report to admin via Telegram with debug context and optional screenshot.

    Args:
        short_id: Short feedback ID (e.g., FB-2401301435)
        user_name: Name of the user submitting feedback
        user_email: Email of the user
        org_name: Organization name
        page_url: URL where feedback was submitted
        feedback_type: Type of feedback (bug, suggestion, question)
        description: User's description of the issue
        debug_context: Dict with console errors, requests, form state, etc.
        screenshot_data: Base64-encoded PNG screenshot (data:image/png;base64,...)
        clickup_task_id: ClickUp task ID if created

    Returns:
        True if message was sent successfully, False otherwise
    """
    if not ADMIN_TELEGRAM_CHAT_ID:
        logger.warning("ADMIN_TELEGRAM_CHAT_ID not configured, skipping bug report")
        return False

    bot = get_bot()
    if not bot:
        logger.warning("Telegram bot not available for bug report")
        return False

    type_emoji = {
        'bug': '🐛 Ошибка',
        'suggestion': '💡 Предложение',
        'question': '❓ Вопрос'
    }

    # Build main message with short_id in header
    text = f"""
{type_emoji.get(feedback_type, '📝 Обратная связь')}  #{short_id}

👤 {user_name} ({user_email})
🏢 {org_name or 'Не указана'}
📍 {page_url}

💬 {description}
    """.strip()

    # Add ClickUp link if available
    if clickup_task_id:
        text += f"\n\n📋 ClickUp: https://app.clickup.com/t/{clickup_task_id}"

    # Add admin link
    text += f"\n🔗 Админка: https://kvotaflow.ru/admin/feedback?id={short_id}"

    # Add debug context if available
    if debug_context:
        context_lines = ["\n\n📋 Контекст:"]

        # Browser detection
        ua = debug_context.get('userAgent', '')
        if 'Chrome' in ua:
            browser = 'Chrome'
        elif 'Firefox' in ua:
            browser = 'Firefox'
        elif 'Safari' in ua:
            browser = 'Safari'
        elif 'Edge' in ua:
            browser = 'Edge'
        else:
            browser = 'Other'
        context_lines.append(f"• Browser: {browser}")

        # Screen size
        if debug_context.get('screenSize'):
            context_lines.append(f"• Screen: {debug_context['screenSize']}")

        # Console errors
        errors = debug_context.get('consoleErrors', [])
        if errors:
            context_lines.append(f"• Console errors: {len(errors)}")
            for err in errors[:3]:  # Show first 3
                msg = str(err.get('message', ''))[:80]
                context_lines.append(f"  - {msg}")

        # Failed requests
        requests = debug_context.get('recentRequests', [])
        failed = [r for r in requests if isinstance(r.get('status'), int) and r.get('status', 0) >= 400]
        if failed:
            context_lines.append(f"• Failed requests: {len(failed)}")
            for req in failed[:3]:
                context_lines.append(f"  - {req.get('method')} {req.get('url')}: {req.get('status')}")

        # Sentry event ID
        if debug_context.get('sentryEventId'):
            context_lines.append(f"• Sentry: {debug_context['sentryEventId']}")

        text += "\n".join(context_lines)

    try:
        import base64
        import io
        chat_id = int(ADMIN_TELEGRAM_CHAT_ID)

        if screenshot_data and screenshot_data.startswith("data:image"):
            # Send screenshot as photo with caption
            # Extract base64 data after the header
            b64_data = screenshot_data.split(",", 1)[1] if "," in screenshot_data else screenshot_data
            photo_bytes = base64.b64decode(b64_data)
            photo_file = io.BytesIO(photo_bytes)
            photo_file.name = f"screenshot_{short_id}.png"

            # Telegram caption limit is 1024 characters
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_file,
                caption=text[:1024]
            )
            # If text is longer, send remainder as separate message
            if len(text) > 1024:
                await bot.send_message(chat_id=chat_id, text=text[:4096])
        else:
            # Text-only message
            await bot.send_message(chat_id=chat_id, text=text[:4096])

        logger.info(f"Bug report {short_id} sent to admin chat {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send bug report to admin: {e}")
        return False
