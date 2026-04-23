"""Customer Journey Map backend service — aggregation + related helpers.

Task 10: ``get_nodes_aggregated`` — merges the static manifest with mutable
state / pin / feedback rows so the ``GET /api/journey/nodes`` endpoint can
return a canvas-ready list in one round-trip.

Why a service module?
    Tasks 11 (per-node detail), 12 (state PATCH), and 13 (Playwright
    webhook) extend this module with more helpers. Keeping read-side
    aggregation separate from the HTTP layer means the handlers stay thin
    and the merge logic is unit-testable without FastAPI's test client.

Design decisions (design.md §4.4, §5.2, requirements.md §4 / §11):
    * Manifest comes from ``frontend/public/journey-manifest.json`` (Task 7
      output). The path is configurable via ``JOURNEY_MANIFEST_PATH`` so
      tests can point at a fixture without touching the real file.
    * Supabase queries use the service-role client (the codebase pattern).
      Feedback visibility is enforced in Python by filtering on ``user_id``
      for non-admin callers — mirroring the ``/admin/feedback`` page,
      which is admin-gated in the frontend (Req 11.2). When RLS is later
      added to ``kvota.user_feedback`` this filter can be removed.
    * The helper is pure: no side effects, no caching — TanStack Query on
      the Next.js side owns read-through caching.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.models.journey import (
    JourneyFeedbackSummary,
    JourneyNodeAggregated,
    JourneyNodeDetail,
    JourneyNodeHistoryEntry,
    JourneyNodeState,
    JourneyPin,
    JourneyStatePatchRequest,
    JourneyVerification,
    PlaywrightWebhookPinUpdate,
)
from services.database import get_supabase

logger = logging.getLogger(__name__)

# Env var used to override the manifest path in tests / local dev where the
# file may live outside the default frontend/public/ tree.
JOURNEY_MANIFEST_PATH_ENV = "JOURNEY_MANIFEST_PATH"

# Roles allowed to see every feedback row. Mirrors the frontend
# `/admin/feedback` gate (`user.roles.includes("admin")`). Any role outside
# this set only sees feedback rows they submitted themselves.
_ADMIN_FEEDBACK_ROLES: frozenset[str] = frozenset({"admin"})


# ---------------------------------------------------------------------------
# Manifest loader
# ---------------------------------------------------------------------------


def _default_manifest_path() -> Path:
    """Resolve the default manifest path relative to the repo root.

    Repo layout (post-Phase 6C): ``frontend/public/journey-manifest.json``.
    This file lives at ``services/journey_service.py`` so the repo root is
    the parent of our ``services/`` dir.
    """
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "frontend" / "public" / "journey-manifest.json"


def _resolve_manifest_path() -> Path:
    """Pick the manifest path — env override wins, else the committed file."""
    env_value = os.environ.get(JOURNEY_MANIFEST_PATH_ENV)
    if env_value:
        return Path(env_value)
    return _default_manifest_path()


def _load_manifest() -> dict[str, Any]:
    """Read the manifest JSON. Returns empty skeleton on missing / invalid file.

    The endpoint must never crash because the manifest is absent — that is
    a build-time failure reported elsewhere (design.md §6, ManifestError).
    An empty manifest still lets the canvas render ghost nodes alone.
    """
    path = _resolve_manifest_path()
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.warning("journey manifest not found at %s", path)
        return {"nodes": [], "edges": [], "clusters": []}
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("failed to load journey manifest at %s: %s", path, exc)
        return {"nodes": [], "edges": [], "clusters": []}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _rows(response: Any) -> list[dict[str, Any]]:
    """Normalise supabase-py execute() responses to a list."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _count_by_node_id(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Bucket a list of annotation rows into ``{node_id: count}``."""
    counts: dict[str, int] = {}
    for row in rows:
        nid = row.get("node_id")
        if isinstance(nid, str) and nid:
            counts[nid] = counts.get(nid, 0) + 1
    return counts


def _filter_feedback_visible(
    rows: list[dict[str, Any]],
    *,
    user_id: str | None,
    role_slugs: set[str] | frozenset[str],
) -> list[dict[str, Any]]:
    """Apply Req 11.2 — admin sees every row, others only their own.

    The rule intentionally matches ``/admin/feedback`` (admin-gated in the
    frontend). When RLS lands on ``kvota.user_feedback`` this helper becomes
    a no-op and the filter can be dropped.
    """
    if role_slugs & _ADMIN_FEEDBACK_ROLES:
        return rows
    if not user_id:
        return []
    return [r for r in rows if r.get("user_id") == user_id]


def get_nodes_aggregated(
    *,
    user_id: str | None,
    role_slugs: set[str] | frozenset[str],
) -> list[JourneyNodeAggregated]:
    """Return the canvas-level merged view for every node.

    Path: invoked by ``GET /api/journey/nodes`` handler.
    Params:
        user_id: ``auth.users.id`` of the caller — may be ``None`` for
            anonymous / pre-auth requests (Wave 4 handlers currently accept
            unauthenticated reads to keep the scaffold lean). Used to filter
            feedback counts for non-admin callers.
        role_slugs: role slugs held by the caller in their active org. Admin
            membership is what gates unrestricted feedback visibility per
            Req 11.2.
    Returns:
        list[JourneyNodeAggregated] — one entry per manifest node + one per
        ghost-nodes row. Ordering is stable (sorted by node_id) so the
        Next.js canvas can render without re-sorting.
    Side Effects: none.
    Roles: any authenticated user. Non-admin callers see feedback_count
        filtered to rows they themselves submitted.
    """
    manifest = _load_manifest()
    manifest_nodes: list[dict[str, Any]] = manifest.get("nodes", []) or []

    sb = get_supabase()

    # Load every annotation table in one pass — cheap, no N+1.
    state_rows = _rows(sb.table("journey_node_state").select("*").execute())
    ghost_rows = _rows(sb.table("journey_ghost_nodes").select("*").execute())
    pin_rows = _rows(sb.table("journey_pins").select("node_id").execute())
    feedback_rows_raw = _rows(
        sb.table("user_feedback").select("node_id,user_id").execute()
    )

    # Visibility filter BEFORE bucketing so counts respect Req 11.2.
    feedback_rows = _filter_feedback_visible(
        feedback_rows_raw, user_id=user_id, role_slugs=role_slugs
    )

    state_by_id: dict[str, dict[str, Any]] = {
        r["node_id"]: r for r in state_rows if r.get("node_id")
    }
    pins_count = _count_by_node_id(pin_rows)
    feedback_count = _count_by_node_id(feedback_rows)

    # -- Merge ------------------------------------------------------------
    aggregated: list[JourneyNodeAggregated] = []

    # 1. Manifest nodes.
    for node in manifest_nodes:
        node_id = node.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            continue
        state = state_by_id.get(node_id, {})
        aggregated.append(
            JourneyNodeAggregated.model_validate(
                {
                    "node_id": node_id,
                    "route": node.get("route", ""),
                    "title": node.get("title", ""),
                    "cluster": node.get("cluster", ""),
                    "roles": list(node.get("roles") or []),
                    "impl_status": state.get("impl_status"),
                    "qa_status": state.get("qa_status"),
                    "version": int(state.get("version") or 0),
                    "stories_count": len(node.get("stories") or []),
                    "pins_count": pins_count.get(node_id, 0),
                    "feedback_count": feedback_count.get(node_id, 0),
                    "ghost_status": None,
                    "proposed_route": None,
                    "updated_at": state.get("updated_at"),
                }
            )
        )

    # 2. Ghost nodes. Absent from the manifest, carry their own metadata.
    for ghost in ghost_rows:
        node_id = ghost.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            continue
        state = state_by_id.get(node_id, {})
        aggregated.append(
            JourneyNodeAggregated.model_validate(
                {
                    "node_id": node_id,
                    "route": ghost.get("proposed_route") or "",
                    "title": ghost.get("title") or "",
                    "cluster": ghost.get("cluster") or "ghost",
                    "roles": [],
                    "impl_status": state.get("impl_status"),
                    "qa_status": state.get("qa_status"),
                    "version": int(state.get("version") or 0),
                    "stories_count": 0,
                    "pins_count": pins_count.get(node_id, 0),
                    "feedback_count": feedback_count.get(node_id, 0),
                    "ghost_status": ghost.get("status"),
                    "proposed_route": ghost.get("proposed_route"),
                    "updated_at": state.get("updated_at"),
                }
            )
        )

    aggregated.sort(key=lambda n: n.node_id)
    return aggregated


# ---------------------------------------------------------------------------
# Per-node detail — Task 11 (GET /api/journey/node/{node_id})
# ---------------------------------------------------------------------------


def _find_manifest_node(
    manifest: dict[str, Any], node_id: str
) -> dict[str, Any] | None:
    """Locate a manifest node by ``node_id`` (linear scan — list is small)."""
    for node in manifest.get("nodes", []) or []:
        if isinstance(node, dict) and node.get("node_id") == node_id:
            return node
    return None


def _latest_verification_per_pin(
    rows: list[dict[str, Any]],
) -> dict[str, JourneyVerification]:
    """Reduce verification rows to ``{pin_id: latest_JourneyVerification}``.

    Rows are sorted by ``tested_at`` DESC first so the first row seen per
    pin is the most recent — mirrors the SQL pattern
    ``ORDER BY tested_at DESC, take first per pin_id``.
    """
    sorted_rows = sorted(
        rows,
        key=lambda r: r.get("tested_at") or "",
        reverse=True,
    )
    latest: dict[str, JourneyVerification] = {}
    for row in sorted_rows:
        pin_id = row.get("pin_id")
        if not isinstance(pin_id, str) or not pin_id or pin_id in latest:
            continue
        try:
            latest[pin_id] = JourneyVerification.model_validate(row)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("skipping malformed verification row %s: %s", row.get("id"), exc)
    return latest


def get_node_detail(
    *,
    node_id: str,
    user_id: str | None,
    role_slugs: set[str] | frozenset[str],
) -> JourneyNodeDetail | None:
    """Return the full drawer payload for a single node.

    Path: invoked by ``GET /api/journey/node/{node_id}`` handler.
    Params:
        node_id: stable node identifier (``app:/route`` or ``ghost:slug``).
        user_id: caller's ``auth.users.id``; ``None`` for anonymous requests.
            Used to filter the feedback top-3 for non-admin callers.
        role_slugs: caller's role slugs for their active org — admin sees
            every feedback row, others see only their own (Req 11.2).
    Returns:
        JourneyNodeDetail on success.
        None when the node_id is unknown (not in manifest, not in
        ``journey_ghost_nodes``) — the handler translates this to HTTP 404
        with the ``NOT_FOUND`` error code.
    Side Effects: none (pure read).
    Roles: any authenticated user. Feedback visibility is filtered per
        Req 11.2; pins and verifications are shown to every caller.
    """
    manifest = _load_manifest()
    manifest_node = _find_manifest_node(manifest, node_id)

    sb = get_supabase()

    ghost_row: dict[str, Any] | None = None
    if manifest_node is None:
        ghost_rows = _rows(
            sb.table("journey_ghost_nodes")
            .select("*")
            .eq("node_id", node_id)
            .execute()
        )
        if ghost_rows:
            ghost_row = ghost_rows[0]
        else:
            return None  # Unknown node — handler returns 404.

    # State row (may be absent — defaults below).
    state_rows = _rows(
        sb.table("journey_node_state")
        .select("*")
        .eq("node_id", node_id)
        .execute()
    )
    state = state_rows[0] if state_rows else {}

    # Pins for this node.
    pin_rows = _rows(
        sb.table("journey_pins").select("*").eq("node_id", node_id).execute()
    )
    pins: list[JourneyPin] = []
    for row in pin_rows:
        try:
            pins.append(JourneyPin.model_validate(row))
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("skipping malformed pin row %s: %s", row.get("id"), exc)

    # Latest verification per pin (one SELECT, reduced in Python — pins-per-node
    # is small enough that a server-side GROUP BY isn't worth a round-trip).
    verification_rows = _rows(
        sb.table("journey_verifications")
        .select("*")
        .eq("node_id", node_id)
        .execute()
    )
    verifications_by_pin = _latest_verification_per_pin(verification_rows)

    # Feedback top-3 (access-filtered, ordered by created_at DESC).
    feedback_raw = _rows(
        sb.table("user_feedback")
        .select("*")
        .eq("node_id", node_id)
        .order("created_at", desc=True)
        .execute()
    )
    feedback_visible = _filter_feedback_visible(
        feedback_raw, user_id=user_id, role_slugs=role_slugs
    )
    feedback_top = feedback_visible[:3]
    feedback_summaries: list[JourneyFeedbackSummary] = []
    for row in feedback_top:
        # Project only the fields the summary model declares (extra='forbid'
        # would reject e.g. 'page_url', 'metadata' passed verbatim).
        feedback_summaries.append(
            JourneyFeedbackSummary.model_validate(
                {
                    "id": str(row.get("id") or ""),
                    "short_id": row.get("short_id"),
                    "node_id": row.get("node_id"),
                    "user_id": row.get("user_id"),
                    "description": row.get("description"),
                    "feedback_type": row.get("feedback_type"),
                    "status": row.get("status"),
                    "created_at": row.get("created_at"),
                }
            )
        )

    # Build the DTO — manifest vs ghost branches differ in source fields only.
    if manifest_node is not None:
        payload: dict[str, Any] = {
            "node_id": node_id,
            "route": manifest_node.get("route", ""),
            "title": manifest_node.get("title", ""),
            "cluster": manifest_node.get("cluster", ""),
            "roles": list(manifest_node.get("roles") or []),
            "stories_count": len(manifest_node.get("stories") or []),
            "ghost_status": None,
            "proposed_route": None,
        }
    else:
        assert ghost_row is not None  # narrowing for the type-checker
        payload = {
            "node_id": node_id,
            "route": ghost_row.get("proposed_route") or "",
            "title": ghost_row.get("title") or "",
            "cluster": ghost_row.get("cluster") or "ghost",
            "roles": [],
            "stories_count": 0,
            "ghost_status": ghost_row.get("status"),
            "proposed_route": ghost_row.get("proposed_route"),
        }

    payload.update(
        {
            "impl_status": state.get("impl_status"),
            "qa_status": state.get("qa_status"),
            "version": int(state.get("version") or 0),
            "notes": state.get("notes"),
            "updated_at": state.get("updated_at"),
            "pins": [p.model_dump() for p in pins],
            "verifications_by_pin": {
                pid: v.model_dump() for pid, v in verifications_by_pin.items()
            },
            "feedback": [f.model_dump() for f in feedback_summaries],
        }
    )

    return JourneyNodeDetail.model_validate(payload)


# ---------------------------------------------------------------------------
# Caller-context helper — used by the HTTP handler to resolve role slugs
# from ``request.state.api_user`` without re-implementing the pattern in
# every route. Deliberately small so Tasks 11 / 12 can reuse it.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _noop_role_cache() -> None:
    """Placeholder — kept so future tasks have a hook for memoisation."""
    return None


def resolve_caller_context(api_user: Any | None) -> tuple[str | None, frozenset[str]]:
    """Extract ``(user_id, role_slugs)`` from a Supabase ``api_user`` object.

    Path: invoked by the journey router.
    Params:
        api_user: the object attached to ``request.state.api_user`` by
            ``ApiAuthMiddleware`` (or ``None`` for anonymous calls).
    Returns:
        (user_id | None, frozenset[str]) — user_id is ``str(api_user.id)``
        when the caller has a valid JWT; role_slugs is the set of slugs
        attached via ``kvota.user_roles`` for the caller's first active
        org membership. Empty set if no roles / no membership.
    Side Effects: one SELECT on ``organization_members`` + one on
        ``user_roles`` per call.
    Roles: any — this is a pure read helper.
    """
    if api_user is None:
        return None, frozenset()

    user_id = str(getattr(api_user, "id", "") or "")
    if not user_id:
        return None, frozenset()

    sb = get_supabase()

    try:
        om_rows = _rows(
            sb.table("organization_members")
            .select("organization_id")
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )
    except Exception as exc:  # pragma: no cover — log + continue
        logger.warning("failed to load organization_members for %s: %s", user_id, exc)
        om_rows = []

    if not om_rows:
        return user_id, frozenset()

    org_id = str(om_rows[0].get("organization_id", ""))
    try:
        role_response = (
            sb.table("user_roles")
            .select("roles!inner(slug)")
            .eq("user_id", user_id)
            .eq("organization_id", org_id)
            .execute()
        )
    except Exception as exc:  # pragma: no cover — log + continue
        logger.warning("failed to load user_roles for %s: %s", user_id, exc)
        return user_id, frozenset()

    slugs: set[str] = set()
    for row in _rows(role_response):
        role_data = row.get("roles")
        if isinstance(role_data, dict) and role_data.get("slug"):
            slugs.add(str(role_data["slug"]))
    return user_id, frozenset(slugs)


# ---------------------------------------------------------------------------
# History read — Task 13 (GET /api/journey/node/{node_id}/history)
# ---------------------------------------------------------------------------


def get_node_history(
    *,
    node_id: str,
    limit: int = 50,
) -> list[JourneyNodeHistoryEntry]:
    """Return the audit log for a node, reverse-chronological, capped at ``limit``.

    Path: invoked by ``GET /api/journey/node/{node_id}/history`` handler.
    Params:
        node_id: stable node identifier (``app:/...`` or ``ghost:...``).
        limit: maximum rows to return (default 50 — matches the drawer's
            history tab). Caller is free to pass smaller values; values ≤ 0
            are normalised to 1 to avoid a DB request for zero rows.
    Returns:
        list[JourneyNodeHistoryEntry] — ordered by ``changed_at`` DESC (newest
        first). Empty list when the node has no history yet.
    Side Effects: none.
    Roles: any authenticated user — history is read-only, filtered by node.

    Notes:
        The history table is populated by the ``trg_journey_node_state_history``
        trigger (migration 500). Rows capture the *pre-image* of each update;
        clients interested in the current value should also call
        ``get_node_detail``.
    """
    clamped_limit = max(1, limit)

    sb = get_supabase()
    rows = _rows(
        sb.table("journey_node_state_history")
        .select("*")
        .eq("node_id", node_id)
        .order("changed_at", desc=True)
        .limit(clamped_limit)
        .execute()
    )

    entries: list[JourneyNodeHistoryEntry] = []
    for row in rows:
        try:
            entries.append(
                JourneyNodeHistoryEntry.model_validate(
                    {
                        "id": str(row.get("id") or ""),
                        "node_id": row.get("node_id"),
                        "impl_status": row.get("impl_status"),
                        "qa_status": row.get("qa_status"),
                        "notes": row.get("notes"),
                        "version": int(row.get("version") or 0),
                        "changed_by": (
                            str(row["changed_by"]) if row.get("changed_by") else None
                        ),
                        "changed_at": row.get("changed_at"),
                    }
                )
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("skipping malformed history row %s: %s", row.get("id"), exc)
    return entries


# ---------------------------------------------------------------------------
# Playwright webhook — Task 13 (POST /api/journey/playwright-webhook)
# ---------------------------------------------------------------------------


def apply_playwright_webhook_batch(
    updates: list[PlaywrightWebhookPinUpdate],
) -> int:
    """Apply a Playwright-produced batch of pin-bbox refreshes.

    Path: invoked by ``POST /api/journey/playwright-webhook`` handler.
    Params:
        updates: list of per-pin payloads. Each update either carries a fresh
            ``bbox`` (rel_x/y/width/height) — in which case the pin's
            ``last_rel_*`` + ``last_position_update`` are refreshed and
            ``selector_broken`` is cleared — or omits the bbox, in which case
            ``selector_broken`` is flipped to true without touching the
            existing bbox fields.
    Returns:
        int — number of pins that received an UPDATE (equal to
        ``len(updates)`` on success; caller re-runs the webhook on partial
        failure since it is idempotent).
    Side Effects:
        UPDATE on ``kvota.journey_pins`` — one row per update. The batch is
        applied sequentially via supabase-py; supabase-py does not expose a
        transactional wrapper, so this is best-effort. The webhook is
        idempotent (same input → same final state) so re-running on partial
        failure is safe.
    Roles: service-role only — the handler gates on a shared secret header
        (``X-Journey-Webhook-Token``), no per-user auth.
    """
    if not updates:
        return 0

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0

    for update in updates:
        if update.bbox is None:
            payload: dict[str, Any] = {"selector_broken": True}
        else:
            payload = {
                "last_rel_x": update.bbox.rel_x,
                "last_rel_y": update.bbox.rel_y,
                "last_rel_width": update.bbox.rel_width,
                "last_rel_height": update.bbox.rel_height,
                "last_position_update": now_iso,
                "selector_broken": False,
            }
        try:
            sb.table("journey_pins").update(payload).eq("id", update.pin_id).execute()
            updated += 1
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "playwright webhook: failed to update pin %s: %s",
                update.pin_id,
                exc,
            )
    return updated


# ---------------------------------------------------------------------------
# State PATCH — Task 12 (PATCH /api/journey/node/{node_id}/state)
# ---------------------------------------------------------------------------


#: Field-level write ACL for ``kvota.journey_node_state``. Source of truth:
#: Req 6.4 / 6.5 / 6.8 in ``.kiro/specs/customer-journey-map/requirements.md``.
#:
#: | Role                      | impl_status | qa_status | notes |
#: |---------------------------|:-----------:|:---------:|:-----:|
#: | admin                     |     yes     |    yes    |  yes  |
#: | head_of_sales             |     yes     |    no     |  yes  |
#: | head_of_procurement       |     yes     |    no     |  yes  |
#: | head_of_logistics         |     yes     |    no     |  yes  |
#: | quote_controller          |     no      |    yes    |  yes  |
#: | spec_controller           |     no      |    yes    |  yes  |
#: | top_manager               |     no      |    no     |  no   |
#: | everyone else             |     no      |    no     |  no   |
#:
#: ``notes`` is allowed for any role that can write at least one status — the
#: requirements doc describes notes as part of the same state row, so writing
#: notes is strictly-weaker than writing a status. ``top_manager`` is the one
#: explicit exception (Req 6.8 — view-only tier).
#:
#: Exported so Task 19 (the drawer UI) can import the matrix verbatim and
#: stay in lockstep with the API's 403 ``FORBIDDEN_FIELD`` surface.
ROLE_FIELD_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"impl_status", "qa_status", "notes"}),
    "head_of_sales": frozenset({"impl_status", "notes"}),
    "head_of_procurement": frozenset({"impl_status", "notes"}),
    "head_of_logistics": frozenset({"impl_status", "notes"}),
    "quote_controller": frozenset({"qa_status", "notes"}),
    "spec_controller": frozenset({"qa_status", "notes"}),
    "top_manager": frozenset(),
}

#: Fields that participate in a PATCH. ``version`` is metadata, not payload.
_PATCHABLE_FIELDS: tuple[str, ...] = ("impl_status", "qa_status", "notes")


class JourneyStatePatchError(Exception):
    """Base class for patch_node_state failures the handler should translate.

    Distinct from ``Exception`` so the handler can catch a narrow type and
    let any other unexpected error propagate to the Starlette 500 path.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


def _resolve_allowed_fields(role_slugs: set[str] | frozenset[str]) -> frozenset[str]:
    """Union the fields writable by any role the caller holds."""
    allowed: set[str] = set()
    for slug in role_slugs:
        allowed |= ROLE_FIELD_PERMISSIONS.get(slug, frozenset())
    return frozenset(allowed)


def _requested_fields(patch: JourneyStatePatchRequest) -> list[str]:
    """Return the patchable fields the client set to a non-None value."""
    return [
        field for field in _PATCHABLE_FIELDS
        if getattr(patch, field) is not None
    ]


def _state_row_to_model(row: dict[str, Any]) -> JourneyNodeState:
    """Project a raw supabase row into the ``JourneyNodeState`` DTO."""
    return JourneyNodeState.model_validate(
        {
            "node_id": row.get("node_id"),
            "impl_status": row.get("impl_status"),
            "qa_status": row.get("qa_status"),
            "notes": row.get("notes"),
            "version": int(row.get("version") or 0),
            "last_tested_at": row.get("last_tested_at"),
            "updated_at": row.get("updated_at") or "",
            "updated_by": (
                str(row["updated_by"]) if row.get("updated_by") else None
            ),
        }
    )


def patch_node_state(
    *,
    node_id: str,
    patch: JourneyStatePatchRequest,
    caller_user_id: str,
    caller_role_slugs: set[str] | frozenset[str],
) -> JourneyNodeState:
    """Apply a field-aware, optimistically-concurrent PATCH to journey_node_state.

    Path: invoked by ``PATCH /api/journey/node/{node_id}/state`` handler.
    Params:
        node_id: stable node identifier (``app:/...`` or ``ghost:...``).
        patch: validated request body (version + optional impl/qa/notes).
        caller_user_id: ``auth.users.id`` of the editor (required — the handler
            rejects anonymous callers before this is called).
        caller_role_slugs: role slugs active for the caller's org membership.
    Returns:
        JourneyNodeState — the post-write row (with ``version`` bumped by 1).
    Raises:
        JourneyStatePatchError with one of:
            - ``EMPTY_PATCH`` (400) — no patchable field set.
            - ``FORBIDDEN_FIELD`` (403) — any requested field lacks ACL.
            - ``STALE_VERSION`` (409) — client version ≠ stored version. The
              exception's ``data`` attribute carries the current state row so
              the handler ships it under response ``data`` per Req 6.2.
    Side Effects:
        UPDATE on ``kvota.journey_node_state`` (when a row exists) or INSERT
        (when version=0 and no row yet). The AFTER UPDATE trigger from
        migration 500 copies the pre-image to ``journey_node_state_history``.
    Roles: enforced here via ``ROLE_FIELD_PERMISSIONS`` (Req 6.4 / 6.5 / 6.6).
    """
    # 1. Reject empty patches (400).
    requested = _requested_fields(patch)
    if not requested:
        raise JourneyStatePatchError(
            code="EMPTY_PATCH",
            message=(
                "Request must set at least one of impl_status, qa_status, "
                "or notes."
            ),
            status_code=400,
        )

    # 2. Field-level ACL. Any requested field outside the caller's union of
    # allowed fields → 403 FORBIDDEN_FIELD, no partial write.
    allowed = _resolve_allowed_fields(caller_role_slugs)
    forbidden = [field for field in requested if field not in allowed]
    if forbidden:
        # Name the first offending field so the UI can highlight it. Role
        # list is included for operator debugging (Req 6.4 error message).
        field = forbidden[0]
        roles_debug = ",".join(sorted(caller_role_slugs)) or "<none>"
        raise JourneyStatePatchError(
            code="FORBIDDEN_FIELD",
            message=(
                f"Role(s) [{roles_debug}] cannot write field {field!r} on "
                f"kvota.journey_node_state."
            ),
            status_code=403,
        )

    # 3. Load current state row (if any).
    sb = get_supabase()
    existing_rows = _rows(
        sb.table("journey_node_state")
        .select("*")
        .eq("node_id", node_id)
        .execute()
    )
    existing = existing_rows[0] if existing_rows else None
    stored_version = int(existing.get("version") or 0) if existing else 0

    # 4. Optimistic concurrency check.
    if patch.version != stored_version:
        # STALE_VERSION: ship the current state so the UI can re-render
        # without a second round-trip (Req 6.2).
        if existing is not None:
            current_payload: dict[str, Any] = _state_row_to_model(
                existing
            ).model_dump()
        else:
            # No row yet but client sent version != 0. Surface an empty
            # placeholder with version=0 so the UI knows to send 0 next.
            current_payload = {
                "node_id": node_id,
                "impl_status": None,
                "qa_status": None,
                "notes": None,
                "version": 0,
                "last_tested_at": None,
                "updated_at": "",
                "updated_by": None,
            }
        raise JourneyStatePatchError(
            code="STALE_VERSION",
            message=(
                "State was updated by another editor; reload before retrying."
            ),
            status_code=409,
            data=current_payload,
        )

    # 5. Build the write payload. Only requested fields are set so untouched
    # columns keep their stored values.
    now_iso = datetime.now(timezone.utc).isoformat()
    new_version = stored_version + 1
    write_payload: dict[str, Any] = {
        "version": new_version,
        "updated_at": now_iso,
        "updated_by": caller_user_id,
    }
    for field in requested:
        write_payload[field] = getattr(patch, field)

    # 6. Apply UPDATE (existing row) or INSERT (no row yet).
    if existing is not None:
        response = (
            sb.table("journey_node_state")
            .update(write_payload)
            .eq("node_id", node_id)
            .execute()
        )
    else:
        insert_payload = {"node_id": node_id, **write_payload}
        # Fill non-requested fields explicitly so the INSERT matches the
        # schema's NOT NULL + CHECK constraints cleanly.
        for field in _PATCHABLE_FIELDS:
            insert_payload.setdefault(field, None)
        response = (
            sb.table("journey_node_state").insert(insert_payload).execute()
        )

    rows = _rows(response)
    if rows:
        return _state_row_to_model(rows[0])

    # Defensive fallback: supabase returned no row echo. Reconstruct from
    # what we know was written — the version and requested fields are the
    # authoritative post-write values.
    reconstructed = {
        "node_id": node_id,
        "impl_status": (existing or {}).get("impl_status"),
        "qa_status": (existing or {}).get("qa_status"),
        "notes": (existing or {}).get("notes"),
        **write_payload,
    }
    return _state_row_to_model(reconstructed)


__all__ = [
    "JOURNEY_MANIFEST_PATH_ENV",
    "ROLE_FIELD_PERMISSIONS",
    "JourneyStatePatchError",
    "get_nodes_aggregated",
    "get_node_detail",
    "get_node_history",
    "apply_playwright_webhook_batch",
    "patch_node_state",
    "resolve_caller_context",
]
