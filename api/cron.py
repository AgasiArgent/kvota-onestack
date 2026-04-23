"""
Cron API endpoints for scheduled background tasks.

GET /api/cron/check-overdue  — Find overdue quotes and send Telegram notifications
POST /api/cron/sla-check     — Send invoice SLA reminders/overdue pings (Task 12)

Auth: X-Cron-Secret header validated against CRON_SECRET env var.
These endpoints are in PUBLIC_API_PATHS (no JWT required).
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

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


# ----------------------------------------------------------------------------
# Task 12 — invoice SLA timers + Telegram pings
# ----------------------------------------------------------------------------

# Reminder is sent inside (deadline - REMINDER_WINDOW_HOURS, deadline).
# 24h is the spec default; kept as module constant for future per-org config.
REMINDER_WINDOW_HOURS: int = 24

# Stable literals matching the CHECK constraint in migration 295.
KIND_LOGISTICS_REMINDER = "logistics_reminder"
KIND_LOGISTICS_OVERDUE = "logistics_overdue"
KIND_CUSTOMS_REMINDER = "customs_reminder"
KIND_CUSTOMS_OVERDUE = "customs_overdue"

_ALL_SLA_KINDS: tuple[str, ...] = (
    KIND_LOGISTICS_REMINDER,
    KIND_LOGISTICS_OVERDUE,
    KIND_CUSTOMS_REMINDER,
    KIND_CUSTOMS_OVERDUE,
)


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp into a UTC-aware datetime, tolerating None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _try_mark_sent(sb: Any, invoice_id: str, kind: str) -> bool:
    """Insert a dedupe row. Returns True if newly inserted, False if already present.

    Relies on UNIQUE(invoice_id, kind) in kvota.invoice_sla_notifications_sent.
    A unique_violation is the only "already sent" signal we trust — we never
    read-then-write (that would race across concurrent cron invocations).
    """
    try:
        sb.table("invoice_sla_notifications_sent").insert(
            {"invoice_id": invoice_id, "kind": kind}
        ).execute()
        return True
    except Exception as exc:  # supabase-py wraps PostgREST errors
        msg = str(exc).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            return False
        logger.error(
            f"SLA dedupe insert failed for invoice={invoice_id} kind={kind}: {exc}"
        )
        raise


def _head_user_ids_for_org(sb: Any, org_id: str, role_slug: str) -> list[str]:
    """Return user_ids with role_slug in the given org. Empty on missing role."""
    roles_resp = sb.table("roles").select("id").eq("slug", role_slug).execute()
    rows = roles_resp.data or []
    if not rows:
        return []
    role_id = rows[0]["id"]
    ur_resp = (
        sb.table("user_roles")
        .select("user_id")
        .eq("organization_id", org_id)
        .eq("role_id", role_id)
        .execute()
    )
    return [r["user_id"] for r in (ur_resp.data or []) if r.get("user_id")]


def _quote_org_id(sb: Any, quote_id: str | None) -> str | None:
    """Resolve organization_id for the invoice's quote."""
    if not quote_id:
        return None
    resp = (
        sb.table("quotes").select("organization_id").eq("id", quote_id).execute()
    )
    rows = resp.data or []
    return rows[0].get("organization_id") if rows else None


def _format_sla_message(
    *,
    kind: str,
    invoice_number: str,
    deadline_at: datetime,
    now: datetime,
) -> str:
    """Build Russian notification text for Telegram (Markdown-safe)."""
    invoice_label = invoice_number or "—"
    if kind == KIND_LOGISTICS_REMINDER:
        hours_left = max(0, int((deadline_at - now).total_seconds() // 3600))
        return (
            f"⏰ Напоминание: инвойс *{invoice_label}* — "
            f"дедлайн логистики через {hours_left} ч."
        )
    if kind == KIND_LOGISTICS_OVERDUE:
        return f"🚨 Просрочено: инвойс *{invoice_label}* — логистика."
    if kind == KIND_CUSTOMS_REMINDER:
        hours_left = max(0, int((deadline_at - now).total_seconds() // 3600))
        return (
            f"⏰ Напоминание: инвойс *{invoice_label}* — "
            f"дедлайн таможни через {hours_left} ч."
        )
    if kind == KIND_CUSTOMS_OVERDUE:
        return f"🚨 Просрочено: инвойс *{invoice_label}* — таможня."
    return f"Инвойс {invoice_label}: {kind}"


async def _notify_users(
    user_ids: list[str],
    text: str,
) -> int:
    """Send Telegram message to each linked user. Returns count of successful sends."""
    from services.telegram_service import get_user_telegram_id, send_message

    sent = 0
    seen: set[str] = set()
    for uid in user_ids:
        if not uid or uid in seen:
            continue
        seen.add(uid)
        tg_id = await get_user_telegram_id(uid)
        if not tg_id:
            logger.debug(f"SLA ping skipped: user {uid} has no linked Telegram")
            continue
        msg_id = await send_message(telegram_id=tg_id, text=text)
        if msg_id is not None:
            sent += 1
    return sent


async def _process_invoice_sla(
    sb: Any,
    invoice: dict,
    now: datetime,
    counters: dict[str, int],
) -> None:
    """Evaluate one invoice and, if due, send reminder/overdue for each side."""
    invoice_id = invoice["id"]
    invoice_number = invoice.get("invoice_number") or ""
    quote_id = invoice.get("quote_id")

    # Resolve org lazily — only when we're about to notify a head role.
    org_id: str | None = None

    for side in ("logistics", "customs"):
        completed_at = invoice.get(f"{side}_completed_at")
        if completed_at:
            continue  # Work finished — no SLA pings needed.

        deadline_at = _parse_ts(invoice.get(f"{side}_deadline_at"))
        if not deadline_at:
            continue  # No deadline configured — nothing to track.

        reminder_kind = (
            KIND_LOGISTICS_REMINDER if side == "logistics" else KIND_CUSTOMS_REMINDER
        )
        overdue_kind = (
            KIND_LOGISTICS_OVERDUE if side == "logistics" else KIND_CUSTOMS_OVERDUE
        )

        # --- Overdue (takes precedence over reminder when both windows elapsed) ---
        if now >= deadline_at:
            if _try_mark_sent(sb, invoice_id, overdue_kind):
                if org_id is None:
                    org_id = _quote_org_id(sb, quote_id)
                head_slug = (
                    "head_of_logistics" if side == "logistics" else "head_of_customs"
                )
                recipients = (
                    _head_user_ids_for_org(sb, org_id, head_slug) if org_id else []
                )
                text = _format_sla_message(
                    kind=overdue_kind,
                    invoice_number=invoice_number,
                    deadline_at=deadline_at,
                    now=now,
                )
                await _notify_users(recipients, text)
                counters[overdue_kind] += 1
            # If overdue already sent, don't also send reminder retroactively.
            continue

        # --- Reminder: within 24h window before deadline ---
        reminder_start = deadline_at - timedelta(hours=REMINDER_WINDOW_HOURS)
        if reminder_start <= now < deadline_at:
            if _try_mark_sent(sb, invoice_id, reminder_kind):
                assignee_col = (
                    "assigned_logistics_user"
                    if side == "logistics"
                    else "assigned_customs_user"
                )
                assignee_id = invoice.get(assignee_col)
                recipients = [assignee_id] if assignee_id else []
                text = _format_sla_message(
                    kind=reminder_kind,
                    invoice_number=invoice_number,
                    deadline_at=deadline_at,
                    now=now,
                )
                await _notify_users(recipients, text)
                counters[reminder_kind] += 1


async def cron_sla_check(request) -> JSONResponse:
    """POST /api/cron/sla-check

    Scan all invoices with open logistics/customs deadlines and send
    Telegram pings:

      - At (deadline - 24h) through deadline: reminder to the assignee.
      - At or past deadline: overdue notification to head-of-<role> users.

    Dedupe is enforced by UNIQUE(invoice_id, kind) in
    `kvota.invoice_sla_notifications_sent` (migration 295). Safe to call
    repeatedly (every ~10 min).

    Auth: X-Cron-Secret header.
    Returns: {"success": true, "data": {"scanned": N, "sent": {kind: count, ...}}}
    """
    err = _validate_cron_secret(request)
    if err:
        return err

    sb = get_supabase()
    now = datetime.now(timezone.utc)

    # Candidate window: deadline is in past OR within the reminder window.
    # Filter down in Python (simpler than composing an OR-of-ranges in PostgREST).
    horizon = (now + timedelta(hours=REMINDER_WINDOW_HOURS)).isoformat()

    resp = (
        sb.table("invoices")
        .select(
            "id, quote_id, invoice_number, "
            "logistics_deadline_at, logistics_completed_at, assigned_logistics_user, "
            "customs_deadline_at, customs_completed_at, assigned_customs_user"
        )
        .or_(
            f"logistics_deadline_at.lte.{horizon},"
            f"customs_deadline_at.lte.{horizon}"
        )
        .execute()
    )
    invoices = resp.data or []

    counters: dict[str, int] = {k: 0 for k in _ALL_SLA_KINDS}
    scanned = 0
    for inv in invoices:
        if not isinstance(inv, dict):
            continue
        if inv.get("logistics_completed_at") and inv.get("customs_completed_at"):
            continue
        scanned += 1
        await _process_invoice_sla(sb, inv, now, counters)

    logger.info(
        f"Cron sla-check: scanned {scanned} invoices, sent={counters}"
    )

    return JSONResponse(
        {"success": True, "data": {"scanned": scanned, "sent": counters}}
    )
