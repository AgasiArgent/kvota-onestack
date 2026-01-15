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
# Webhook Processing
# ============================================================================

@dataclass
class WebhookResult:
    """Result of processing a webhook update."""
    success: bool
    update_type: str  # "message", "callback_query", "unknown"
    message: Optional[str] = None
    callback_data: Optional[CallbackData] = None
    telegram_id: Optional[int] = None
    text: Optional[str] = None
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
                text=command,
                message=f"Command {command} received" + (f" with args: {args}" if args else "")
            )
        else:
            # Regular text message
            return WebhookResult(
                success=True,
                update_type="message",
                telegram_id=telegram_id,
                text=text,
                message="Text message received"
            )

    # Unknown update type
    return WebhookResult(
        success=False,
        update_type="unknown",
        error="Unsupported update type"
    )


async def respond_to_command(telegram_id: int, command: str, args: List[str] = None) -> bool:
    """Send a response to a bot command.

    This is a placeholder that will be expanded in later features.

    Args:
        telegram_id: User's Telegram ID
        command: Command received (e.g., "/start")
        args: Optional command arguments

    Returns:
        True if response was sent successfully

    Note: Full implementations for /start, /status, /help will be
    added in Features #54, #55, #57.
    """
    bot = get_bot()
    if not bot:
        return False

    args = args or []

    # Basic command responses (placeholders - will be enhanced in later features)
    responses = {
        "/start": "👋 Добро пожаловать в OneStack Bot!\n\nДля привязки аккаунта введите ваш код верификации.",
        "/help": "📚 Справка по боту:\n\n/start - Начало работы, привязка аккаунта\n/status - Показать мои текущие задачи\n/help - Показать эту справку",
        "/status": "📋 Для просмотра задач необходимо привязать ваш аккаунт.\n\nИспользуйте /start для начала.",
    }

    response_text = responses.get(command, f"Неизвестная команда: {command}\n\nИспользуйте /help для справки.")

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
