"""
Stage Timer Service — elapsed time computation, deadline status, and overdue detection.

Functions: get_quote_timer, get_bulk_timers, get_overdue_quotes,
           format_elapsed, mark_overdue_notified
"""

import logging
from datetime import datetime, timezone

from services.database import get_supabase

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"draft", "deal", "rejected", "cancelled"}
WARNING_THRESHOLD = 0.8

_NO_TIMER_RESULT = {
    "elapsed_hours": 0.0,
    "deadline_hours": None,
    "status": "no_timer",
    "stage_entered_at": None,
    "stage": "",
}


def _get_supabase():
    """Internal wrapper for mocking in tests."""
    return get_supabase()


def _parse_dt(val: str | None) -> datetime | None:
    """Parse ISO timestamp string into a timezone-aware datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val.replace("Z", "+00:00"))


def _compute_status(elapsed_hours: float, deadline_hours: int | None) -> str:
    """Determine timer status from elapsed hours and deadline."""
    if deadline_hours is None:
        return "no_deadline"
    if elapsed_hours >= deadline_hours:
        return "overdue"
    if elapsed_hours >= deadline_hours * WARNING_THRESHOLD:
        return "warning"
    return "ok"


def _build_timer(quote: dict, deadlines_map: dict[str, int]) -> dict:
    """Build timer dict for a single quote row."""
    stage = quote.get("workflow_status", "")

    if stage in TERMINAL_STATUSES:
        return {**_NO_TIMER_RESULT, "stage": stage}

    stage_entered_at = _parse_dt(quote.get("stage_entered_at"))
    if not stage_entered_at:
        return {**_NO_TIMER_RESULT, "stage": stage}

    now = datetime.now(timezone.utc)
    if stage_entered_at.tzinfo is None:
        stage_entered_at = stage_entered_at.replace(tzinfo=timezone.utc)
    elapsed_hours = (now - stage_entered_at).total_seconds() / 3600.0

    override = quote.get("stage_deadline_override_hours")
    deadline_hours = override if override is not None else deadlines_map.get(stage)

    return {
        "elapsed_hours": round(elapsed_hours, 2),
        "deadline_hours": deadline_hours,
        "status": _compute_status(elapsed_hours, deadline_hours),
        "stage_entered_at": stage_entered_at,
        "stage": stage,
    }


def _fetch_deadlines_map(org_id: str) -> dict[str, int]:
    """Fetch {stage: deadline_hours} for an org from stage_deadlines table."""
    client = _get_supabase()
    resp = (
        client.table("stage_deadlines")
        .select("stage, deadline_hours")
        .eq("organization_id", org_id)
        .execute()
    )
    return {row["stage"]: row["deadline_hours"] for row in (resp.data or [])}


def get_quote_timer(quote_id: str, org_id: str) -> dict:
    """Return {elapsed_hours, deadline_hours, status, stage_entered_at, stage} for a quote.

    Status: ok | warning | overdue | no_timer | no_deadline.
    """
    client = _get_supabase()
    resp = (
        client.table("quotes")
        .select("id, workflow_status, stage_entered_at, stage_deadline_override_hours")
        .eq("id", quote_id)
        .execute()
    )
    if not resp.data:
        return {**_NO_TIMER_RESULT}

    return _build_timer(resp.data[0], _fetch_deadlines_map(org_id))


def get_bulk_timers(quote_ids: list[str], org_id: str) -> dict[str, dict]:
    """Return {quote_id: timer_data} for all given quotes in a single query (no N+1)."""
    if not quote_ids:
        return {}

    client = _get_supabase()
    resp = (
        client.table("quotes")
        .select("id, workflow_status, stage_entered_at, stage_deadline_override_hours")
        .in_("id", quote_ids)
        .execute()
    )
    deadlines_map = _fetch_deadlines_map(org_id)
    return {q["id"]: _build_timer(q, deadlines_map) for q in (resp.data or [])}


def get_overdue_quotes(org_id: str) -> list[dict]:
    """Find quotes past deadline with overdue_notified_at IS NULL.

    Returns [{quote_id, idn, stage, elapsed_hours, deadline_hours,
              assigned_user_id, manager_id}].
    """
    client = _get_supabase()
    resp = (
        client.table("quotes")
        .select("id, idn, workflow_status, stage_entered_at, "
                "stage_deadline_override_hours, overdue_notified_at, "
                "assigned_user_id, manager_id")
        .eq("organization_id", org_id)
        .is_("overdue_notified_at", "null")
        .execute()
    )
    deadlines_map = _fetch_deadlines_map(org_id)

    overdue = []
    for q in (resp.data or []):
        timer = _build_timer(q, deadlines_map)
        if timer["status"] == "overdue":
            overdue.append({
                "quote_id": q["id"],
                "idn": q.get("idn", ""),
                "stage": timer["stage"],
                "elapsed_hours": timer["elapsed_hours"],
                "deadline_hours": timer["deadline_hours"],
                "assigned_user_id": q.get("assigned_user_id"),
                "manager_id": q.get("manager_id"),
            })
    return overdue


def format_elapsed(hours: float) -> str:
    """Format elapsed hours as Russian string: <1h → '45м', <24h → '2ч 15м', >=24h → '3д 5ч'."""
    if hours < 0:
        hours = 0.0
    total_minutes = int(hours * 60)

    if hours < 1:
        return f"{total_minutes}м"
    if hours < 24:
        h = int(hours)
        m = total_minutes - h * 60
        return f"{h}ч {m}м" if m > 0 else f"{h}ч"

    days = int(hours // 24)
    remaining_hours = int(hours % 24)
    return f"{days}д {remaining_hours}ч" if remaining_hours > 0 else f"{days}д"


def mark_overdue_notified(quote_id: str) -> None:
    """Set overdue_notified_at = NOW() for the given quote."""
    client = _get_supabase()
    client.table("quotes").update(
        {"overdue_notified_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", quote_id).execute()
