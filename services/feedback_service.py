"""
Feedback Service — orchestrates feedback status updates with notifications.

Handles: DB update + ClickUp sync + Telegram notification in a single call.
Used by both the admin UI endpoint and the internal API.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from services.database import get_supabase
from services.telegram_service import get_user_telegram_id, send_feedback_resolved_notification
from services.clickup_service import update_clickup_task_status

logger = logging.getLogger(__name__)

VALID_STATUSES = {"new", "in_progress", "resolved", "closed"}


@dataclass(frozen=True)
class FeedbackUpdateResult:
    success: bool
    message: str
    telegram_notified: bool = False
    clickup_synced: bool = False


async def update_feedback_status(short_id: str, status: str) -> FeedbackUpdateResult:
    """Update feedback status with ClickUp sync and Telegram notification.

    Args:
        short_id: Feedback short ID (e.g., 'FB-260407-114057-dfb9')
        status: New status ('new', 'in_progress', 'resolved', 'closed')

    Returns:
        FeedbackUpdateResult with success flag and notification outcomes.
    """
    if status not in VALID_STATUSES:
        return FeedbackUpdateResult(success=False, message=f"Invalid status: {status}")

    supabase = get_supabase()
    telegram_notified = False
    clickup_synced = False

    # Fetch feedback record first (need user_id, clickup_task_id for notifications)
    try:
        result = supabase.table("user_feedback").select(
            "short_id, user_id, feedback_type, description, clickup_task_id"
        ).eq("short_id", short_id).limit(1).execute()

        if not result.data:
            return FeedbackUpdateResult(success=False, message=f"Feedback {short_id} not found")

        record = result.data[0]
    except Exception as e:
        logger.error(f"Failed to fetch feedback {short_id}: {e}")
        return FeedbackUpdateResult(success=False, message=f"DB error: {e}")

    # Update status
    try:
        supabase.table("user_feedback").update({
            "status": status,
            "updated_at": datetime.now().isoformat()
        }).eq("short_id", short_id).execute()
    except Exception as e:
        logger.error(f"Failed to update feedback status {short_id}: {e}")
        return FeedbackUpdateResult(success=False, message=f"DB update error: {e}")

    # Sync to ClickUp
    task_id = record.get("clickup_task_id")
    if task_id:
        try:
            clickup_synced = await update_clickup_task_status(task_id, status)
        except Exception as e:
            logger.warning(f"ClickUp sync failed for {short_id}: {e}")

    # Telegram notification for resolved/closed
    if status in ("resolved", "closed") and record.get("user_id"):
        try:
            reporter_tg_id = await get_user_telegram_id(record["user_id"])
            if reporter_tg_id:
                telegram_notified = await send_feedback_resolved_notification(
                    telegram_id=reporter_tg_id,
                    short_id=short_id,
                    feedback_type=record.get("feedback_type", ""),
                    description=record.get("description", ""),
                    new_status=status
                )
        except Exception as e:
            logger.warning(f"Telegram notification failed for {short_id}: {e}")

    return FeedbackUpdateResult(
        success=True,
        message=f"Status updated to {status}",
        telegram_notified=telegram_notified,
        clickup_synced=clickup_synced,
    )
