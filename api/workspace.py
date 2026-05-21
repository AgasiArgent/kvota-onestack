"""Workspace /api/workspace/* endpoints — head-of-* analytics.

Handler module (not router). Registered via thin wrapper in
api/routers/workspace.py. Implements Task 16 of the
logistics-customs-redesign spec: "Кто сколько отработал" —
per-user completion counts + median time-to-complete + on-time %.

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware.
Access: admin, top_manager, or either head_of_logistics or head_of_customs
(dual-hat per PR #105 — either head role grants access in BOTH domains).
Other roles get 403.

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

from api.lib.errors import error_response, success_response
from services.database import get_supabase
from services.role_service import get_user_role_codes

logger = logging.getLogger(__name__)

_ALLOWED_DOMAINS = ("logistics", "customs")

# Roles that grant analytics + queue management access. head_of_logistics and
# head_of_customs are dual-hat (PR #105) — either head role grants access in
# BOTH domains. admin + top_manager always pass.
_HEAD_ROLES: frozenset[str] = frozenset(
    {"head_of_logistics", "head_of_customs", "admin", "top_manager"}
)


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


def _has_analytics_access(role_codes: list[str], domain: str) -> bool:
    """Dual-hat: admin, top_manager, head_of_logistics, head_of_customs all in.

    `domain` is accepted (and validated upstream) for symmetry with other
    workspace endpoints, but doesn't narrow the role gate — both head roles
    have access to both domains per PR #105.
    """
    del domain  # accepted for endpoint symmetry, no longer narrows the gate
    return any(r in _HEAD_ROLES for r in (role_codes or []))


# ---------------------------------------------------------------------------
# User name resolution
# ---------------------------------------------------------------------------


_UNKNOWN_USER_LABEL = "— Неизвестный логист"


def _resolve_user_names(sb: Any, user_ids: list[str]) -> dict[str, str]:
    """Resolve a display name for each user id.

    Resolution order (mirrors api/notes.py `_resolve_author_profiles` — the
    project-wide canonical pattern):
      1. ``kvota.user_profiles.full_name`` — canonical display name, mirrored
         on user creation in api/admin_users.py.
      2. ``auth.users.user_metadata.full_name|name`` — only present for users
         created via the signup flow before user_profiles materialises.
      3. ``auth.users.email`` — last human-readable fallback.
      4. Localized "unknown logist" placeholder — so the UI never surfaces a
         truncated UUID like ``96d797ee`` to a head_of_*.

    Called once per request with all distinct ids.
    """
    names: dict[str, str] = {}
    if not user_ids:
        return names

    # 1) Canonical names from kvota.user_profiles. This is the table the
    #    admin UI writes to (api/admin_users.py:238) and is the source of
    #    truth for human-readable names everywhere else in the codebase.
    profile_names: dict[str, str] = {}
    try:
        resp = (
            sb.table("user_profiles")
            .select("user_id, full_name")
            .in_("user_id", user_ids)
            .execute()
        )
        for p in (resp.data or []):
            uid = p.get("user_id")
            full_name = (p.get("full_name") or "").strip()
            if uid and full_name:
                profile_names[uid] = full_name
    except Exception as exc:  # noqa: BLE001 — never 500 on profile lookup
        logger.warning("analytics: user_profiles lookup failed: %s", exc)

    # 2) auth.users metadata + email as secondary source for users without a
    #    materialised profile row.
    auth_meta: dict[str, dict[str, str | None]] = {}
    try:
        page = sb.auth.admin.list_users()
        users_iter = getattr(page, "users", None) or page or []
        wanted = set(user_ids)
        for u in users_iter:
            uid = getattr(u, "id", None)
            if uid is None or uid not in wanted:
                continue
            meta = getattr(u, "user_metadata", {}) or {}
            auth_meta[uid] = {
                "metadata_name": meta.get("full_name") or meta.get("name"),
                "email": getattr(u, "email", None),
            }
    except Exception as exc:  # noqa: BLE001 — degrade gracefully, never 500
        logger.warning("analytics: failed to resolve user names: %s", exc)

    # 3) Compose: profile name → metadata name → email → localized fallback.
    for uid in user_ids:
        meta = auth_meta.get(uid, {})
        names[uid] = (
            profile_names.get(uid)
            or meta.get("metadata_name")
            or meta.get("email")
            or _UNKNOWN_USER_LABEL
        )
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
    Roles: admin, top_manager, or either head_of_logistics or head_of_customs
           (dual-hat per PR #105 — both head roles access both domains).
    """
    if domain not in _ALLOWED_DOMAINS:
        return error_response(
            "VALIDATION_ERROR",
            f"domain must be one of {list(_ALLOWED_DOMAINS)}",
            400,
        )

    user, role_codes = _resolve_dual_auth(request)
    if not user:
        return error_response("UNAUTHORIZED", "Not authenticated", 401)
    org_id = user.get("org_id")
    if not org_id:
        return error_response("UNAUTHORIZED", "No organization context", 401)
    if not _has_analytics_access(role_codes, domain):
        return error_response(
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
        return error_response("INTERNAL_ERROR", "Failed to load analytics", 500)

    rows = res.data or []
    aggregated = _aggregate(rows, domain)

    user_ids = [r["user_id"] for r in aggregated]
    name_map = _resolve_user_names(sb, user_ids)
    for r in aggregated:
        r["user_name"] = name_map.get(r["user_id"], _UNKNOWN_USER_LABEL)

    return success_response({"rows": aggregated})
