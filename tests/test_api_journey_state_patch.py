"""Tests for Task 12 — ``PATCH /api/journey/node/{node_id}/state``.

The endpoint writes impl_status / qa_status / notes on ``kvota.journey_node_state``
with two guards on top of the plain UPDATE:

1. **Optimistic concurrency** via ``version``. The client echoes the version it
   last saw; if it doesn't match the stored version, the server returns 409
   ``STALE_VERSION`` with the *current* state under ``data`` so the UI can
   show a conflict toast and refresh without a second round-trip
   (Req 6.1 / 6.2).
2. **Field-aware ACL**. Each caller role holds write permission for a subset
   of ``{impl_status, qa_status, notes}``. A PATCH that touches any field
   outside the caller's allowed set fails atomically with 403
   ``FORBIDDEN_FIELD`` — no partial writes, version is NOT incremented
   (Req 6.4 / 6.5 / 6.6).

The ACL matrix is the source of truth codified in
``services.journey_service.ROLE_FIELD_PERMISSIONS`` — derived strictly from
Req 6.4 / 6.5 / 6.8 in ``.kiro/specs/customer-journey-map/requirements.md``:

    | Role                      | impl_status | qa_status | notes |
    |---------------------------|:-----------:|:---------:|:-----:|
    | admin                     |     yes     |    yes    |  yes  |
    | head_of_sales             |     yes     |    no     |  yes  |
    | head_of_procurement       |     yes     |    no     |  yes  |
    | head_of_logistics         |     yes     |    no     |  yes  |
    | quote_controller          |     no      |    yes    |  yes  |
    | spec_controller           |     no      |    yes    |  yes  |
    | top_manager               |     no      |    no     |  no   |
    | everyone else (sales, ...)|     no      |    no     |  no   |

``notes`` is writable by any role that can write at least one status — the
requirements doc doesn't name notes explicitly but Req 6 describes notes as
part of the same state row, so writing notes is a strictly-weaker operation
than writing a status. ``top_manager`` is denied everything (Req 6.8).

Tests mock Supabase via ``services.journey_service.get_supabase`` — same
pattern as ``tests/test_api_journey_node_detail.py`` and
``tests/test_api_journey_webhook.py``.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_app  # noqa: E402


# ---------------------------------------------------------------------------
# Supabase fluent-chain stub — supports select/eq/execute + insert/update
# ---------------------------------------------------------------------------


class _FakeStateChain:
    """Supabase-py fluent stub for ``kvota.journey_node_state``.

    Records every INSERT / UPDATE into ``calls`` so tests can verify that
    failed-ACL PATCHes DID NOT touch the stored row.
    """

    def __init__(
        self,
        rows: list[dict[str, Any]],
        calls: list[dict[str, Any]],
    ) -> None:
        self._rows = rows
        self._calls = calls
        self._filters: dict[str, Any] = {}
        self._pending_update: dict[str, Any] | None = None
        self._pending_insert: dict[str, Any] | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeStateChain":
        return self

    def eq(self, col: str, val: Any) -> "_FakeStateChain":
        self._filters[col] = val
        return self

    def update(self, payload: dict[str, Any]) -> "_FakeStateChain":
        self._pending_update = dict(payload)
        return self

    def insert(self, payload: dict[str, Any]) -> "_FakeStateChain":
        self._pending_insert = dict(payload)
        return self

    def execute(self) -> MagicMock:
        resp = MagicMock()
        if self._pending_update is not None:
            # Apply update in-place to matching rows, record the call, return
            # the updated row list.
            updated: list[dict[str, Any]] = []
            for row in self._rows:
                if all(row.get(k) == v for k, v in self._filters.items()):
                    row.update(self._pending_update)
                    updated.append(row)
            self._calls.append(
                {
                    "op": "update",
                    "payload": dict(self._pending_update),
                    "filters": dict(self._filters),
                }
            )
            resp.data = updated
            return resp
        if self._pending_insert is not None:
            self._rows.append(dict(self._pending_insert))
            self._calls.append(
                {"op": "insert", "payload": dict(self._pending_insert)}
            )
            resp.data = [dict(self._pending_insert)]
            return resp
        # Plain SELECT — apply filters.
        filtered = [
            row for row in self._rows
            if all(row.get(k) == v for k, v in self._filters.items())
        ]
        resp.data = filtered
        resp.count = len(filtered)
        return resp


def _mk_state_supabase(
    state_rows: list[dict[str, Any]],
) -> tuple[MagicMock, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    sb = MagicMock()

    def table(name: str) -> _FakeStateChain:
        if name == "journey_node_state":
            return _FakeStateChain(state_rows, calls)
        return _FakeStateChain([], calls)

    sb.table.side_effect = table
    return sb, calls


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(api_app)


# ---------------------------------------------------------------------------
# Shared caller-context patching
# ---------------------------------------------------------------------------


def _patch_caller(role_slugs: set[str], user_id: str = "caller-user") -> Any:
    """Return a context manager that makes ``resolve_caller_context`` return
    ``(user_id, frozenset(role_slugs))``.
    """
    from services import journey_service

    return patch.object(
        journey_service,
        "resolve_caller_context",
        return_value=(user_id, frozenset(role_slugs)),
    )


# ---------------------------------------------------------------------------
# Tests — happy path, concurrency guard, ACL
# ---------------------------------------------------------------------------


class TestPatchNodeStateEndpoint:
    """HTTP contract for ``PATCH /api/journey/node/{node_id}/state``."""

    def test_patch_state_happy_path_increments_version(
        self, api_client: TestClient
    ) -> None:
        """Existing row v1 + client sends v1 → stored becomes v2 with new status."""
        from services import journey_service

        state_rows = [
            {
                "node_id": "app:/quotes",
                "impl_status": None,
                "qa_status": None,
                "notes": None,
                "version": 1,
                "updated_at": "2026-04-22T12:00:00+00:00",
                "updated_by": "prior-editor",
            }
        ]
        sb, calls = _mk_state_supabase(state_rows)

        with patch.object(journey_service, "get_supabase", return_value=sb), _patch_caller(
            {"admin"}
        ):
            response = api_client.patch(
                "/api/journey/node/app:/quotes/state",
                json={"version": 1, "impl_status": "done"},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("success") is True, body
        data = body["data"]
        assert data["node_id"] == "app:/quotes"
        assert data["impl_status"] == "done"
        assert data["version"] == 2, "version must be bumped on write"

        # Exactly one update call was issued, not a partial double-write.
        updates = [c for c in calls if c["op"] == "update"]
        assert len(updates) == 1, f"expected 1 update, got {calls}"
        assert updates[0]["payload"]["version"] == 2
        assert updates[0]["payload"]["impl_status"] == "done"

    def test_patch_state_stale_version_returns_409_with_current(
        self, api_client: TestClient
    ) -> None:
        """Stored v2, client sends v1 → 409 STALE_VERSION + current state in data."""
        from services import journey_service

        state_rows = [
            {
                "node_id": "app:/quotes",
                "impl_status": "partial",
                "qa_status": "verified",
                "notes": "already edited",
                "version": 2,
                "updated_at": "2026-04-22T13:00:00+00:00",
                "updated_by": "other-user",
            }
        ]
        sb, calls = _mk_state_supabase(state_rows)

        with patch.object(journey_service, "get_supabase", return_value=sb), _patch_caller(
            {"admin"}
        ):
            response = api_client.patch(
                "/api/journey/node/app:/quotes/state",
                json={"version": 1, "impl_status": "done"},
            )

        assert response.status_code == 409, response.text
        body = response.json()
        assert body.get("success") is False, body
        assert body["error"]["code"] == "STALE_VERSION"
        # Current state is shipped under ``data`` so the UI can re-render
        # without a follow-up GET (Req 6.2).
        assert "data" in body, "409 body must include data={current state}"
        current = body["data"]
        # Shape: contains at least version and the status fields.
        assert current.get("version") == 2
        assert current.get("impl_status") == "partial"
        assert current.get("qa_status") == "verified"

        # Stale write must NOT have touched the stored row.
        updates = [c for c in calls if c["op"] == "update"]
        assert updates == [], f"stale-version write leaked through: {updates}"
        assert state_rows[0]["version"] == 2

    def test_patch_impl_rejected_for_qa_role_with_403_forbidden_field(
        self, api_client: TestClient
    ) -> None:
        """quote_controller + spec_controller can do qa, not impl → 403."""
        from services import journey_service

        for role in ("quote_controller", "spec_controller"):
            state_rows = [
                {
                    "node_id": "app:/quotes",
                    "impl_status": None,
                    "qa_status": None,
                    "notes": None,
                    "version": 1,
                    "updated_at": "2026-04-22T12:00:00+00:00",
                    "updated_by": None,
                }
            ]
            sb, calls = _mk_state_supabase(state_rows)

            with patch.object(
                journey_service, "get_supabase", return_value=sb
            ), _patch_caller({role}):
                response = api_client.patch(
                    "/api/journey/node/app:/quotes/state",
                    json={"version": 1, "impl_status": "done"},
                )

            assert response.status_code == 403, (
                f"role={role}: {response.status_code} {response.text}"
            )
            body = response.json()
            assert body.get("success") is False, body
            assert body["error"]["code"] == "FORBIDDEN_FIELD"
            # No partial write for a role that lacks the field.
            updates = [c for c in calls if c["op"] == "update"]
            assert updates == []
            assert state_rows[0]["version"] == 1

    def test_patch_qa_rejected_for_head_of_sales(
        self, api_client: TestClient
    ) -> None:
        """head_of_sales can write impl + notes but NOT qa_status → 403 FORBIDDEN_FIELD."""
        from services import journey_service

        state_rows = [
            {
                "node_id": "app:/quotes",
                "impl_status": None,
                "qa_status": None,
                "notes": None,
                "version": 1,
                "updated_at": "2026-04-22T12:00:00+00:00",
                "updated_by": None,
            }
        ]
        sb, calls = _mk_state_supabase(state_rows)

        with patch.object(journey_service, "get_supabase", return_value=sb), _patch_caller(
            {"head_of_sales"}
        ):
            response = api_client.patch(
                "/api/journey/node/app:/quotes/state",
                json={"version": 1, "qa_status": "verified"},
            )

        assert response.status_code == 403, response.text
        body = response.json()
        assert body["error"]["code"] == "FORBIDDEN_FIELD"
        # Row untouched.
        assert [c for c in calls if c["op"] == "update"] == []
        assert state_rows[0]["version"] == 1

    def test_patch_mixed_rejects_without_partial_write(
        self, api_client: TestClient
    ) -> None:
        """head_of_sales has impl permission but NOT qa; sending both fields →
        403 with full rollback (stored row unchanged; version NOT incremented).
        """
        from services import journey_service

        state_rows = [
            {
                "node_id": "app:/quotes",
                "impl_status": None,
                "qa_status": None,
                "notes": None,
                "version": 1,
                "updated_at": "2026-04-22T12:00:00+00:00",
                "updated_by": None,
            }
        ]
        sb, calls = _mk_state_supabase(state_rows)

        with patch.object(journey_service, "get_supabase", return_value=sb), _patch_caller(
            {"head_of_sales"}
        ):
            response = api_client.patch(
                "/api/journey/node/app:/quotes/state",
                json={
                    "version": 1,
                    "impl_status": "done",
                    "qa_status": "verified",
                },
            )

        assert response.status_code == 403, response.text
        body = response.json()
        assert body["error"]["code"] == "FORBIDDEN_FIELD"
        # Critical: NO partial write. Row unchanged.
        updates = [c for c in calls if c["op"] == "update"]
        assert updates == [], f"partial write leaked: {updates}"
        assert state_rows[0]["impl_status"] is None
        assert state_rows[0]["qa_status"] is None
        assert state_rows[0]["version"] == 1

    def test_top_manager_cannot_patch_state(
        self, api_client: TestClient
    ) -> None:
        """top_manager is view-only (Req 6.8) → every field write is 403."""
        from services import journey_service

        # Test each field separately to lock in "every field denied".
        for field, value in (
            ("impl_status", "done"),
            ("qa_status", "verified"),
            ("notes", "some note"),
        ):
            state_rows = [
                {
                    "node_id": "app:/quotes",
                    "impl_status": None,
                    "qa_status": None,
                    "notes": None,
                    "version": 1,
                    "updated_at": "2026-04-22T12:00:00+00:00",
                    "updated_by": None,
                }
            ]
            sb, calls = _mk_state_supabase(state_rows)

            with patch.object(
                journey_service, "get_supabase", return_value=sb
            ), _patch_caller({"top_manager"}):
                response = api_client.patch(
                    "/api/journey/node/app:/quotes/state",
                    json={"version": 1, field: value},
                )

            assert response.status_code == 403, (
                f"field={field}: {response.status_code} {response.text}"
            )
            body = response.json()
            assert body["error"]["code"] == "FORBIDDEN_FIELD"
            updates = [c for c in calls if c["op"] == "update"]
            assert updates == [], f"top_manager write leaked on {field}: {updates}"


# ---------------------------------------------------------------------------
# ACL matrix sanity — Req 6.4 / 6.5 / 6.8 encoded as constants
# ---------------------------------------------------------------------------


class TestRoleFieldPermissions:
    """Lock the ACL matrix so Task 19 (drawer UI) can import it unchanged."""

    def test_role_field_permissions_matches_req_6(self) -> None:
        from services.journey_service import ROLE_FIELD_PERMISSIONS

        # Req 6.4 — impl_status: admin, head_of_sales, head_of_procurement,
        # head_of_logistics
        assert "impl_status" in ROLE_FIELD_PERMISSIONS["admin"]
        assert "impl_status" in ROLE_FIELD_PERMISSIONS["head_of_sales"]
        assert "impl_status" in ROLE_FIELD_PERMISSIONS["head_of_procurement"]
        assert "impl_status" in ROLE_FIELD_PERMISSIONS["head_of_logistics"]

        # Req 6.5 — qa_status: admin, quote_controller, spec_controller
        assert "qa_status" in ROLE_FIELD_PERMISSIONS["admin"]
        assert "qa_status" in ROLE_FIELD_PERMISSIONS["quote_controller"]
        assert "qa_status" in ROLE_FIELD_PERMISSIONS["spec_controller"]

        # Head-of-X roles cannot write qa.
        assert "qa_status" not in ROLE_FIELD_PERMISSIONS["head_of_sales"]
        assert "qa_status" not in ROLE_FIELD_PERMISSIONS["head_of_procurement"]
        assert "qa_status" not in ROLE_FIELD_PERMISSIONS["head_of_logistics"]

        # QA roles cannot write impl.
        assert "impl_status" not in ROLE_FIELD_PERMISSIONS["quote_controller"]
        assert "impl_status" not in ROLE_FIELD_PERMISSIONS["spec_controller"]

        # Req 6.8 — top_manager has no permissions at all.
        assert ROLE_FIELD_PERMISSIONS.get("top_manager", frozenset()) == frozenset()
