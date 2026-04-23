"""Workspace /api/workspace/* endpoints — head-of-* analytics.

Handler module (not router). Registered via thin wrapper in
api/routers/workspace.py. Implements Task 16 of the
logistics-customs-redesign spec: "Кто сколько отработал" —
per-user completion counts + median time-to-complete + on-time %.

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.
Access: admin, top_manager, head_of_logistics (for domain=logistics),
head_of_customs (for domain=customs). Other roles get 403.

Aggregation is computed in Python over raw invoice rows instead of via a
SQL RPC: org-scale data (< ~10k invoices) makes this trivial and keeps
the endpoint free of new migrations.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime
from collections.abc import Sequence
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from services.database import get_supabase
from services.role_service import get_user_role_codes

logger = logging.getLogger(__name__)

_ALLOWED_DOMAINS = ("logistics", "customs")

# Role that grants access to analytics, per domain. admin + top_manager always
# pass.
_DOMAIN_HEAD_ROLE: dict[str, str] = {
    "logistics": "head_of_logistics",
    "customs": "head_of_customs",
}


# ---------------------------------------------------------------------------
# Auth helpers (mirrors api/customs.py + api/notes.py)
# ---------------------------------------------------------------------------


def _resolve_dual_auth(request: Request) -> tuple[dict | None, list[str]]:
    """Resolve authenticated user + effective role codes.

    JWT (Next.js) or legacy session (FastHTML). Session path honors admin
    ``impersonated_role``. Returns (user_dict, role_codes) or (None, [])
    when unauthenticated.
    """
    api_user = getattr(request.state, "api_user", None)
    if api_user:
        user_id = str(api_user.id)
        user_meta = api_user.user_metadata or {}
        org_id = user_meta.get("org_id")
        if not org_id:
            try:
                sb = get_supabase()
                om = (
                    sb.table("organization_members")
                    .select("organization_id")
                    .eq("user_id", user_id)
                    .eq("status", "active")
                    .order("created_at")
                    .limit(1)
                    .execute()
                )
                if om.data and isinstance(om.data[0], dict):
                    org_id = om.data[0].get("organization_id")
            except Exception:
                org_id = None
        role_codes = (
            get_user_role_codes(user_id, str(org_id)) if org_id else []
        )
        return (
            {"id": user_id, "org_id": org_id, "email": api_user.email or ""},
            role_codes,
        )

    try:
        session = request.session
    except (AssertionError, AttributeError):
        return None, []

    user = session.get("user") if session else None
    if not user:
        return None, []

    impersonated_role = session.get("impersonated_role")
    if impersonated_role:
        return user, [impersonated_role]

    return user, user.get("roles", [])


def _err(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


def _ok(data: dict | list | None = None, status: int = 200) -> JSONResponse:
    payload: dict = {"success": True}
    if data is not None:
        payload["data"] = data
    return JSONResponse(payload, status_code=status)


def _has_analytics_access(role_codes: list[str], domain: str) -> bool:
    """Admin + top_manager always in; head_of_<domain> for their domain."""
    allowed = {"admin", "top_manager", _DOMAIN_HEAD_ROLE[domain]}
    return any(r in allowed for r in (role_codes or []))


# ---------------------------------------------------------------------------
# User name resolution
# ---------------------------------------------------------------------------


def _resolve_user_names(sb: Any, user_ids: list[str]) -> dict[str, str]:
    """Resolve a display name for each user id.

    Uses auth.admin.list_users() via supabase-py admin client. Unknown ids are
    returned with their short id as display fallback (never crashes on
    deleted users). Called once per request with all distinct ids.
    """
    names: dict[str, str] = {}
    if not user_ids:
        return names

    try:
        # supabase-py v2: sb.auth.admin.list_users() returns a list of User
        # objects. For small orgs listing all is cheaper than N per-id lookups;
        # for large orgs it's still one network call.
        page = sb.auth.admin.list_users()
        # Normalize shape — can be list[User] or .users depending on version.
        users_iter = getattr(page, "users", None) or page or []
        wanted = set(user_ids)
        for u in users_iter:
            uid = getattr(u, "id", None)
            if uid is None or uid not in wanted:
                continue
            meta = getattr(u, "user_metadata", {}) or {}
            email = getattr(u, "email", None) or ""
            display = meta.get("full_name") or meta.get("name") or email or str(uid)[:8]
            names[uid] = display
    except Exception as exc:  # noqa: BLE001 — degrade gracefully, never 500
        logger.warning("analytics: failed to resolve user names: %s", exc)

    for uid in user_ids:
        names.setdefault(uid, str(uid)[:8])
    return names


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    # Supabase returns ISO 8601 with trailing Z or +00:00.
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _aggregate(rows: Sequence[Any], domain: str) -> list[dict]:
    """Group invoice rows by assigned user; compute stats.

    Each output row (one per user that has completed >=1 invoice):
      user_id, completed_count, median_hours, on_time_count, on_time_pct

    median_hours is over (completed_at - created_at) in hours.
    on_time_count counts rows where deadline_at exists AND completed_at
    <= deadline_at.
    """
    user_col = f"assigned_{domain}_user"
    completed_col = f"{domain}_completed_at"
    deadline_col = f"{domain}_deadline_at"

    by_user: dict[str, dict[str, Any]] = {}
    for row in rows:
        user_id = row.get(user_col)
        completed_at = _parse_iso(row.get(completed_col))
        created_at = _parse_iso(row.get("created_at"))
        if not user_id or completed_at is None or created_at is None:
            continue

        hours = (completed_at - created_at).total_seconds() / 3600.0
        if hours < 0:
            continue

        bucket = by_user.setdefault(
            user_id,
            {
                "user_id": user_id,
                "completed_count": 0,
                "durations_hours": [],
                "on_time_count": 0,
            },
        )
        bucket["completed_count"] += 1
        bucket["durations_hours"].append(hours)

        deadline_at = _parse_iso(row.get(deadline_col))
        if deadline_at is not None and completed_at <= deadline_at:
            bucket["on_time_count"] += 1

    results: list[dict] = []
    for bucket in by_user.values():
        durations = bucket.pop("durations_hours")
        median_hours = statistics.median(durations) if durations else 0.0
        completed = bucket["completed_count"]
        on_time = bucket["on_time_count"]
        on_time_pct = (on_time / completed * 100.0) if completed else 0.0
        results.append(
            {
                "user_id": bucket["user_id"],
                "completed_count": completed,
                "median_hours": round(median_hours, 1),
                "on_time_count": on_time,
                "on_time_pct": round(on_time_pct, 1),
            }
        )
    results.sort(key=lambda r: r["completed_count"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


async def analytics(request: Request, domain: str) -> JSONResponse:
    """GET /api/workspace/{domain}/analytics — per-user completion stats.

    Path: GET /api/workspace/{domain}/analytics
    Params:
        domain: logistics | customs (path)
    Returns:
        data.rows: list[{user_id, user_name, completed_count, median_hours,
                         on_time_count, on_time_pct}]
    Roles: admin, top_manager, head_of_logistics (logistics),
           head_of_customs (customs)
    """
    if domain not in _ALLOWED_DOMAINS:
        return _err(
            "VALIDATION_ERROR",
            f"domain must be one of {list(_ALLOWED_DOMAINS)}",
            400,
        )

    user, role_codes = _resolve_dual_auth(request)
    if not user:
        return _err("UNAUTHORIZED", "Not authenticated", 401)
    org_id = user.get("org_id")
    if not org_id:
        return _err("UNAUTHORIZED", "No organization context", 401)
    if not _has_analytics_access(role_codes, domain):
        return _err(
            "FORBIDDEN",
            "Analytics access requires head_of_* or admin role",
            403,
        )

    user_col = f"assigned_{domain}_user"
    completed_col = f"{domain}_completed_at"
    deadline_col = f"{domain}_deadline_at"

    sb = get_supabase()
    select_clause = (
        f"id, created_at, {user_col}, {completed_col}, {deadline_col}, "
        "quote:quotes!inner(organization_id, deleted_at)"
    )

    try:
        res = (
            sb.table("invoices")
            .select(select_clause)
            .eq("quote.organization_id", org_id)
            .is_("quote.deleted_at", None)
            .not_.is_(user_col, None)
            .not_.is_(completed_col, None)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("analytics: invoice query failed: %s", exc)
        return _err("INTERNAL_ERROR", "Failed to load analytics", 500)

    rows = res.data or []
    aggregated = _aggregate(rows, domain)

    user_ids = [r["user_id"] for r in aggregated]
    name_map = _resolve_user_names(sb, user_ids)
    for r in aggregated:
        r["user_name"] = name_map.get(r["user_id"], str(r["user_id"])[:8])

    return _ok({"rows": aggregated})
