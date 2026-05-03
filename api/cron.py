"""
Cron API endpoints for scheduled background tasks.

GET  /api/cron/check-overdue     — Find overdue quotes and send Telegram notifications
POST /api/cron/sla-check         — Send invoice SLA reminders/overdue pings (Task 12)
POST /api/cron/revalidate-rates  — Weekly customs rate revalidation (REQ-6 customs-phase-1)

Auth: X-Cron-Secret header validated against CRON_SECRET env var.
These endpoints are in PUBLIC_API_PATHS (no JWT required).
"""

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from starlette.responses import JSONResponse

from services.alta_client import AltaApiError, notify_admin
from services.database import get_supabase
from services.rate_resolver import _bulk_upsert
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


# ----------------------------------------------------------------------------
# REQ-6 customs-phase-1 — weekly revalidation of top-1000 most-used rates
# ----------------------------------------------------------------------------

# Stale window: anything older than this is a candidate for re-fetch.
REVALIDATE_STALE_WINDOW = timedelta(days=7)

# Top-N pairs (tnved_code × country_or_areal) processed per run.
REVALIDATE_BATCH_SIZE = 1000

# Bound for the initial DB pull. The handler groups in Python after the
# fetch — keeping this finite caps memory regardless of how stale the
# cache gets.
REVALIDATE_MAX_FETCH = 5000

# Packet floor — abort the loop and admin-alert when Alta packet drops
# below this. Tighter than the AltaClient warning threshold (100) so we
# stop *before* the resolver-driven user requests start failing.
REVALIDATE_PACKET_FLOOR = 50

# Periodic progress logging frequency (every Nth processed pair).
REVALIDATE_LOG_EVERY = 100

# Failure-ratio threshold above which an admin alert fires at end of run.
# Tuned to catch the "Alta partially up — most calls error" case without
# false-firing on a handful of bad TNVED codes (M8 review fix).
REVALIDATE_FAILURE_RATIO_THRESHOLD = 0.5

# Poison-pill backoff (M9 review fix):
#   - Skip pairs whose consecutive failure count >= POISON_PILL_FAILURE_THRESHOLD
#     while their last failure is more recent than POISON_PILL_BACKOFF.
#   - After the backoff window expires, retry once: if Alta has restored
#     the code, the success branch resets the counter; if it fails again,
#     the count keeps climbing and the next backoff starts from now().
#   - When the *current run* leaves >= POISON_PILL_ALERT_COUNT pairs in
#     this state, fire one Telegram alert (throttled 1/day).
POISON_PILL_FAILURE_THRESHOLD = 3
POISON_PILL_BACKOFF = timedelta(days=7)
POISON_PILL_ALERT_COUNT = 10

# Throttle for cron-level Telegram alerts. Truncation, failure-ratio,
# and poison-pill alerts each get their own key so they don't suppress
# one another.
_CRON_ALERT_THROTTLE = timedelta(hours=1)
_POISON_PILL_ALERT_THROTTLE = timedelta(hours=24)
_cron_last_alert_at: dict[str, datetime] = {}


async def _maybe_alert_truncation(stale_row_count: int) -> None:
    """Telegram-alert when REVALIDATE_MAX_FETCH cap was hit (M6).

    Throttled to at most one alert per hour per cron host. Uses a
    dedicated throttle key so it doesn't compete with the failure-ratio
    alert (M8) on the same hourly bucket.
    """
    key = "revalidate_truncation"
    now = datetime.now(timezone.utc)
    last = _cron_last_alert_at.get(key)
    if last is not None and (now - last) < _CRON_ALERT_THROTTLE:
        return
    _cron_last_alert_at[key] = now

    message = (
        f"⚠️ cron_revalidate_rates: stale-row count hit hard cap "
        f"{REVALIDATE_MAX_FETCH} (fetched {stale_row_count}) — coverage "
        f"may be incomplete; consider raising REVALIDATE_MAX_FETCH or "
        f"running revalidate more frequently."
    )
    logger.warning(message)
    await notify_admin(message)


async def _maybe_alert_failure_ratio(
    processed: int, failures: int
) -> None:
    """Telegram-alert when failure ratio crosses threshold at end of run (M8).

    Catches the case where Alta is partially up (random 5xx, schema
    drift, etc.) — the loop didn't trigger the AltaApiError(140) abort,
    yet most rows fail anyway.
    """
    if processed <= 0:
        return
    ratio = failures / processed
    if ratio <= REVALIDATE_FAILURE_RATIO_THRESHOLD:
        return

    key = "revalidate_failure_ratio"
    now = datetime.now(timezone.utc)
    last = _cron_last_alert_at.get(key)
    if last is not None and (now - last) < _CRON_ALERT_THROTTLE:
        return
    _cron_last_alert_at[key] = now

    message = (
        f"⚠️ cron_revalidate_rates: high failure ratio "
        f"{ratio * 100:.0f}% ({failures}/{processed}) — possible Alta "
        f"outage or schema drift."
    )
    logger.warning(message)
    await notify_admin(message)


async def cron_revalidate_rates(request, alta_client) -> JSONResponse:
    """POST /api/cron/revalidate-rates

    Weekly revalidation of the top-1000 most-recently-used customs rates
    that have gone stale (``source_fetched_at < now() - 7 days``).

    Path: POST /api/cron/revalidate-rates
    Auth: X-Cron-Secret header (PUBLIC_API_PATHS, no JWT middleware)
    Returns: {success, data: {processed, hits, updates, failures, packet_left_at_end}}
    Side Effects:
        - INSERT/UPDATE rows in kvota.tnved_rates with source='alta-revalidate'
          (race-safe via the same UNIQUE constraint as rate_resolver).
        - When Alta returns the same valid_from for an existing rate the
          row is updated in place (refreshes source_fetched_at and value
          fields). When Alta returns a new valid_from the fresh row is
          inserted alongside the existing one — history preserved
          automatically by the UNIQUE constraint, no explicit
          ``UPDATE … SET valid_to = now()`` needed (REQ-6 AC#3).
        - Telegram admin alert on AltaApiError(140) (insufficient funds)
          or packet_left below the floor — loop aborts immediately.
    Roles: cron-only (no user role check; X-Cron-Secret is the gate).

    The handler is idempotent — a re-run within 7 days finds no stale
    rows and returns processed=0 without contacting Alta.
    """
    err = _validate_cron_secret(request)
    if err:
        return err

    sb = get_supabase()
    now_dt = datetime.now(timezone.utc)

    # Fetch stale rows (bounded). PostgREST has no MAX() aggregation in
    # select so we group/sort in Python — bounded by REVALIDATE_MAX_FETCH
    # so memory stays predictable even for cold caches. Pull the
    # poison-pill columns too so we can filter chronically-failing pairs
    # without an extra round-trip (M9 review fix).
    cutoff = (now_dt - REVALIDATE_STALE_WINDOW).isoformat()
    resp = (
        sb.table("tnved_rates")
        .select(
            "tnved_code, country_or_areal, last_used_at, "
            "revalidate_failure_count, revalidate_failed_at"
        )
        .lt("source_fetched_at", cutoff)
        .execute()
    )
    stale_rows: list[dict[str, Any]] = list(getattr(resp, "data", None) or [])
    if len(stale_rows) >= REVALIDATE_MAX_FETCH:
        # Defensive: should never happen in practice for a 7-day window
        # since the cache is bounded by user activity. When it does, ops
        # need to know — top-1000 ranking only sees the truncated slice
        # and stale-coverage may be incomplete (M6 review fix).
        original_count = len(stale_rows)
        stale_rows = stale_rows[:REVALIDATE_MAX_FETCH]
        await _maybe_alert_truncation(original_count)

    # Drop poison-pill rows BEFORE ranking — a chronically-failing pair
    # otherwise keeps burning Alta packet quota every weekly cron run
    # (M9 review fix). Backoff expires after 7 days so we re-try in case
    # Alta has restored the code.
    poison_cutoff = (now_dt - POISON_PILL_BACKOFF).isoformat()
    stale_rows = [
        row for row in stale_rows
        if not _is_poison_pill(row, poison_cutoff_iso=poison_cutoff)
    ]

    pairs = _rank_revalidation_pairs(stale_rows, limit=REVALIDATE_BATCH_SIZE)

    stats: dict[str, Any] = {
        "processed": 0,
        "hits": 0,
        "updates": 0,
        "failures": 0,
        "packet_left_at_end": None,
    }

    today = date.today()
    for tnved_code, country_or_areal in pairs:
        oksm = _country_or_areal_to_oksm(country_or_areal)
        if oksm is None:
            # Areal-keyed rows can't be re-fetched per-country (Alta is
            # country-bound). Base rates (NULL country) likewise have no
            # per-country lookup. Skip silently — they refresh organically
            # when a user-driven resolve hits them.
            continue

        try:
            new_rates = await alta_client.get_rates(
                tncode=tnved_code,
                country=oksm,
                date_=today,
            )
        except AltaApiError as exc:
            stats["failures"] += 1
            if exc.code == 140:
                logger.error(
                    "Cron revalidate-rates: AltaApiError(140) insufficient "
                    "funds — aborting after %d processed",
                    stats["processed"],
                )
                await notify_admin(
                    "🛑 Cron revalidate-rates aborted: Alta API returned "
                    "code 140 (insufficient funds). Top up the Alta "
                    "packet to resume revalidation."
                )
                break
            logger.warning(
                "Cron revalidate-rates: AltaApiError(%d) for tnved=%s "
                "country=%s — skipping",
                exc.code, tnved_code, oksm,
            )
            _record_poison_pill_failure(sb, tnved_code, country_or_areal)
            continue
        except Exception as exc:
            stats["failures"] += 1
            logger.warning(
                "Cron revalidate-rates: Alta call failed for tnved=%s "
                "country=%s: %s",
                tnved_code, oksm, exc,
            )
            _record_poison_pill_failure(sb, tnved_code, country_or_areal)
            continue

        # Pragmatic upsert (REQ-6 AC#3): the UNIQUE constraint
        # (tnved_code, payment_type, country_or_areal, valid_from,
        #  certificate_required, sp_certificate_required) means a rate
        # with unchanged valid_from is updated in place — refreshing
        # source_fetched_at and value fields. If Alta returns a new
        # valid_from (rate change with new effective date), a fresh row
        # is inserted alongside the existing one, preserving history.
        try:
            _bulk_upsert(sb, new_rates, source="alta-revalidate")
            if new_rates:
                stats["updates"] += 1
            else:
                stats["hits"] += 1
        except Exception as exc:
            stats["failures"] += 1
            logger.warning(
                "Cron revalidate-rates: upsert failed for tnved=%s "
                "country=%s: %s",
                tnved_code, oksm, exc,
            )
            _record_poison_pill_failure(sb, tnved_code, country_or_areal)
            continue

        # Success path — clear any prior poison-pill state for this pair
        # (M9 review fix). Reset is per-pair (matches all valid_from
        # generations) because the poison-pill signal is pair-level.
        _reset_poison_pill_failure(sb, tnved_code, country_or_areal)
        stats["processed"] += 1

        # Periodic progress log
        if stats["processed"] % REVALIDATE_LOG_EVERY == 0:
            logger.info(
                "Cron revalidate-rates progress: processed=%d hits=%d "
                "updates=%d failures=%d packet_left=%s",
                stats["processed"], stats["hits"], stats["updates"],
                stats["failures"],
                getattr(alta_client, "last_packet_left", None),
            )

        # Packet floor check — bail out before we starve real users.
        packet_left = getattr(alta_client, "last_packet_left", None)
        if packet_left is not None and packet_left < REVALIDATE_PACKET_FLOOR:
            logger.error(
                "Cron revalidate-rates: packet_left=%d below floor %d — "
                "aborting after %d processed",
                packet_left, REVALIDATE_PACKET_FLOOR, stats["processed"],
            )
            await notify_admin(
                f"🛑 Cron revalidate-rates aborted: Alta packet_left="
                f"{packet_left} below floor {REVALIDATE_PACKET_FLOOR}. "
                f"Top up the Alta packet to resume."
            )
            break

    stats["packet_left_at_end"] = getattr(
        alta_client, "last_packet_left", None
    )
    logger.info(
        "Cron revalidate-rates: %s",
        ", ".join(f"{k}={v}" for k, v in stats.items()),
    )
    # Failure-ratio alert: catches partial-Alta-outage where most calls
    # fail but no single error triggered the abort path (M8 review fix).
    await _maybe_alert_failure_ratio(
        processed=stats["processed"], failures=stats["failures"]
    )
    # Poison-pill alert: count how many pairs are currently parked under
    # the failure-threshold backoff. Fires once if the count crosses
    # POISON_PILL_ALERT_COUNT, throttled to 1/day (M9 review fix).
    await _maybe_alert_poison_pill_count(sb)
    return JSONResponse({"success": True, "data": stats})


def _rank_revalidation_pairs(
    rows: list[dict[str, Any]], *, limit: int
) -> list[tuple[str, str | None]]:
    """Group stale rows by (tnved_code, country_or_areal) and rank by
    MAX(last_used_at) descending, NULLs last. Returns the top ``limit``
    pairs (REQ-6 AC#2).

    PostgREST has no native MAX() aggregation in select; doing this in
    Python keeps the cron handler dependency-free.
    """
    grouped: dict[tuple[str, str | None], str | None] = {}
    for row in rows:
        code = row.get("tnved_code")
        country = row.get("country_or_areal")  # may be None for base rates
        if not code:
            continue
        key = (code, country)
        last_used = row.get("last_used_at")
        prev = grouped.get(key)
        # Keep the maximum last_used_at per pair. None < any timestamp.
        if prev is None or (last_used is not None and last_used > prev):
            grouped[key] = last_used

    # Sort: non-null timestamps descending (NULLs last).
    def _sort_key(item: tuple[tuple[str, str | None], str | None]) -> tuple:
        last_used = item[1]
        # (is_null, negated_ts) — non-nulls first, then by descending ts
        return (last_used is None, _invert_string(last_used or ""))

    ordered = sorted(grouped.items(), key=_sort_key)
    return [pair for pair, _ in ordered[:limit]]


def _invert_string(value: str) -> str:
    """Inverse-lex compare key: produces a string that sorts in reverse
    order of the input under default ``str < str`` comparison.

    ISO-8601 timestamps are ASCII so flipping each char by subtracting
    from 0x10FFFF (BMP-safe upper bound) yields a key that sorts in
    descending order via plain ``sorted()``.
    """
    return "".join(chr(0x10FFFF - ord(c)) for c in value)


def _country_or_areal_to_oksm(value: str | None) -> int | None:
    """Decode the ``country_or_areal`` storage prefix back to ОКСМ digital.

    - 'C:643' → 643 (per-country rate — re-fetchable via Alta)
    - 'A:EAEU' → None (areal — Alta can't query an areal as a country)
    - None    → None (base rate — no per-country lookup)
    """
    if not value:
        return None
    if value.startswith("C:"):
        try:
            return int(value[2:])
        except ValueError:
            return None
    return None


# ----------------------------------------------------------------------------
# Poison-pill helpers (M9 review fix)
# ----------------------------------------------------------------------------


def _is_poison_pill(row: dict[str, Any], *, poison_cutoff_iso: str) -> bool:
    """Return True if the row should be skipped under poison-pill backoff.

    A row is poison-pilled when:
      - revalidate_failure_count >= POISON_PILL_FAILURE_THRESHOLD, AND
      - revalidate_failed_at is more recent than (now - POISON_PILL_BACKOFF).

    After the backoff window expires, the row is re-tried; success will
    reset the counter via ``_reset_poison_pill_failure``, another failure
    will bump it via ``_record_poison_pill_failure``.
    """
    count = row.get("revalidate_failure_count") or 0
    if count < POISON_PILL_FAILURE_THRESHOLD:
        return False
    failed_at = row.get("revalidate_failed_at")
    if not failed_at:
        # No timestamp — treat as expired backoff and let the loop retry.
        # A retry with another failure will set both columns coherently.
        return False
    return str(failed_at) >= poison_cutoff_iso


def _record_poison_pill_failure(
    sb: Any, tnved_code: str, country_or_areal: str | None
) -> None:
    """Bump revalidate_failure_count and stamp revalidate_failed_at for the
    pair. Per-pair update (matches all valid_from generations) so the
    poison-pill signal stays coherent across rate revisions.

    Failures here are non-critical — log and swallow so a flaky write
    doesn't abort the whole cron run.
    """
    try:
        # PostgREST UPDATE doesn't support ``column = column + 1`` directly
        # via the python client; read-then-write is acceptable because the
        # cron handler is the sole writer of these columns and runs at
        # most once a week.
        resp = (
            sb.table("tnved_rates")
            .select("id, revalidate_failure_count")
            .eq("tnved_code", tnved_code)
            .eq("country_or_areal", country_or_areal)
            .execute()
        )
        rows = list(getattr(resp, "data", None) or [])
        now_iso = datetime.now(timezone.utc).isoformat()
        for row in rows:
            row_id = row.get("id")
            if not row_id:
                continue
            current = row.get("revalidate_failure_count") or 0
            (
                sb.table("tnved_rates")
                .update({
                    "revalidate_failure_count": current + 1,
                    "revalidate_failed_at": now_iso,
                })
                .eq("id", row_id)
                .execute()
            )
    except Exception as exc:  # noqa: BLE001 — non-critical fire-and-forget
        logger.warning(
            "Cron revalidate-rates: failed to record poison-pill failure "
            "for tnved=%s country=%s: %s",
            tnved_code, country_or_areal, exc,
        )


def _reset_poison_pill_failure(
    sb: Any, tnved_code: str, country_or_areal: str | None
) -> None:
    """Clear poison-pill state for the pair after a successful Alta fetch.

    Idempotent — a no-op write against rows that were already at zero.
    """
    try:
        (
            sb.table("tnved_rates")
            .update({
                "revalidate_failure_count": 0,
                "revalidate_failed_at": None,
            })
            .eq("tnved_code", tnved_code)
            .eq("country_or_areal", country_or_areal)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 — non-critical fire-and-forget
        logger.warning(
            "Cron revalidate-rates: failed to reset poison-pill state "
            "for tnved=%s country=%s: %s",
            tnved_code, country_or_areal, exc,
        )


async def _maybe_alert_poison_pill_count(sb: Any) -> None:
    """Telegram-alert when too many pairs are parked under poison-pill backoff.

    Fires once when the count of currently-poisoned pairs (failure_count
    >= threshold AND failed_at within backoff window) crosses
    POISON_PILL_ALERT_COUNT. Throttled to 1/day so a persistent state
    doesn't spam ops every cron run.
    """
    try:
        cutoff = (
            datetime.now(timezone.utc) - POISON_PILL_BACKOFF
        ).isoformat()
        resp = (
            sb.table("tnved_rates")
            .select("id")
            .gte("revalidate_failure_count", POISON_PILL_FAILURE_THRESHOLD)
            .gte("revalidate_failed_at", cutoff)
            .execute()
        )
        rows = list(getattr(resp, "data", None) or [])
        count = len(rows)
    except Exception as exc:  # noqa: BLE001 — diagnostic alert is best-effort
        logger.warning(
            "Cron revalidate-rates: poison-pill count query failed: %s", exc
        )
        return

    if count < POISON_PILL_ALERT_COUNT:
        return

    key = "poison_pill"
    now = datetime.now(timezone.utc)
    last = _cron_last_alert_at.get(key)
    if last is not None and (now - last) < _POISON_PILL_ALERT_THROTTLE:
        return
    _cron_last_alert_at[key] = now

    message = (
        f"⚠️ cron_revalidate_rates: {count} pairs in poison-pill state — "
        f"Alta may have schema-changed or these codes are retired. "
        f"Threshold: {POISON_PILL_FAILURE_THRESHOLD} consecutive failures, "
        f"backoff: {POISON_PILL_BACKOFF.days}d."
    )
    logger.warning(message)
    await notify_admin(message)
