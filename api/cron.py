"""
Cron API endpoints for scheduled background tasks.

GET /api/cron/check-overdue  — Find overdue quotes and send Telegram notifications

Auth: X-Cron-Secret header validated against CRON_SECRET env var.
These endpoints are in PUBLIC_API_PATHS (no JWT required).
"""

import logging
import os

from starlette.responses import JSONResponse

from services.database import get_supabase
from services.stage_timer_service import (
    format_elapsed,
    get_overdue_quotes,
    mark_overdue_notified,
)

logger = logging.getLogger(__name__)

# Russian stage names for notification messages.
# Mirrors _get_status_name_ru in telegram_service.py but includes all stages
# that have deadlines configured (see migration 240).
_STATUS_NAMES_RU: dict[str, str] = {
    "draft": "Черновик",
    "pending_procurement": "Оценка закупок",
    "pending_logistics": "Логистика",
    "pending_customs": "Таможня",
    "pending_logistics_and_customs": "Логистика и таможня",
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


def _validate_cron_secret(request) -> JSONResponse | None:
    """Validate X-Cron-Secret header. Returns error response or None if valid."""
    expected = os.environ.get("CRON_SECRET", "")
    if not expected:
        logger.error("CRON_SECRET env var is not set")
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Cron secret not configured"}},
            status_code=500,
        )

    actual = request.headers.get("X-Cron-Secret", "")
    if actual != expected:
        return JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Invalid or missing cron secret"}},
            status_code=403,
        )

    return None


async def cron_check_overdue(request) -> JSONResponse:
    """GET /api/cron/check-overdue

    Find all overdue quotes across all organizations and send Telegram
    notifications to the assigned user and quote manager.

    Auth: X-Cron-Secret header.
    Returns: {"success": true, "notified": <count>}
    """
    err = _validate_cron_secret(request)
    if err:
        return err

    sb = get_supabase()

    # Fetch all organizations
    orgs_resp = sb.table("organizations").select("id").execute()
    orgs = orgs_resp.data or []

    from services.telegram_service import send_overdue_notification

    notified_count = 0

    for org in orgs:
        org_id = org["id"]
        overdue = get_overdue_quotes(org_id)

        for q in overdue:
            quote_id = q["quote_id"]
            stage = q["stage"]
            stage_name = _STATUS_NAMES_RU.get(stage, stage)
            elapsed = format_elapsed(q["elapsed_hours"])
            deadline_hours = q["deadline_hours"]

            # Collect unique user IDs to notify (assigned user + manager)
            user_ids: set[str] = set()
            if q.get("assigned_user_id"):
                user_ids.add(q["assigned_user_id"])
            if q.get("manager_id"):
                user_ids.add(q["manager_id"])

            for user_id in user_ids:
                sent = await send_overdue_notification(
                    user_id=user_id,
                    quote_id=quote_id,
                    quote_idn=q.get("idn", ""),
                    stage_name=stage_name,
                    elapsed=elapsed,
                    deadline_hours=deadline_hours,
                )
                if sent:
                    notified_count += 1

            mark_overdue_notified(quote_id)

    logger.info(f"Cron check-overdue: {notified_count} notifications sent across {len(orgs)} orgs")

    return JSONResponse({"success": True, "notified": notified_count})
