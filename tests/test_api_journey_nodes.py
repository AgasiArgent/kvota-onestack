"""Tests for ``GET /api/journey/nodes`` — the aggregate canvas endpoint (Task 10).

The endpoint merges three data sources into a flat list of
``JourneyNodeAggregated`` DTOs:

1. Manifest nodes (``frontend/public/journey-manifest.json`` — Task 7) give
   the immutable route / cluster / title / roles / stories skeleton.
2. ``kvota.journey_node_state`` rows give mutable impl/qa status + version;
   nodes with no row surface with ``impl_status=None`` / ``qa_status=None``.
3. ``kvota.journey_ghost_nodes`` rows add planned-but-unshipped nodes that
   are not in the manifest.

Per-node counts (``pins_count``, ``feedback_count``, ``stories_count``) are
computed server-side so the canvas does not have to page through related
tables. ``feedback_count`` is filtered by application-level access rules
(Req 11.2): ``admin`` sees every feedback row, any other role only sees
rows they themselves submitted — mirroring the `/admin/feedback` page
which is admin-gated in the frontend.

These tests mock ``services.database.get_supabase`` (the canonical pattern
used throughout this codebase — see ``test_api_customs.py``,
``test_api_app_mount.py``). No live DB access required.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Ensure project root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_app  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers — mock Supabase chains + a minimal manifest on disk
# ---------------------------------------------------------------------------


def _mk_manifest_nodes() -> list[dict[str, Any]]:
    """Three-node manifest fixture covering: no-state, with-state, stories>0."""
    return [
        {
            "node_id": "app:/quotes",
            "route": "/quotes",
            "title": "Quotes",
            "cluster": "quotes",
            "source_files": ["frontend/src/app/(app)/quotes/page.tsx"],
            "roles": ["sales", "quote_controller"],
            "stories": [
                {
                    "ref": "phase-5b#1",
                    "actor": "sales",
                    "goal": "Create quote",
                    "spec_file": ".kiro/specs/quotes.md",
                },
                {
                    "ref": "phase-5b#2",
                    "actor": "quote_controller",
                    "goal": "Review quote",
                    "spec_file": ".kiro/specs/quotes.md",
                },
            ],
            "parent_node_id": None,
            "children": [],
        },
        {
            "node_id": "app:/admin/users",
            "route": "/admin/users",
            "title": "Users",
            "cluster": "admin",
            "source_files": ["frontend/src/app/(app)/admin/users/page.tsx"],
            "roles": ["admin"],
            "stories": [],
            "parent_node_id": None,
            "children": [],
        },
        {
            "node_id": "app:/deals",
            "route": "/deals",
            "title": "Deals",
            "cluster": "deals",
            "source_files": ["frontend/src/app/(app)/deals/page.tsx"],
            "roles": ["sales"],
            "stories": [],
            "parent_node_id": None,
            "children": [],
        },
    ]


@pytest.fixture
def manifest_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a stub manifest file and point the service at it via env var.

    ``journey_service.JOURNEY_MANIFEST_PATH_ENV`` lets the test override the
    default ``frontend/public/journey-manifest.json`` lookup. This keeps the
    real committed manifest out of the unit-test contract.
    """
    manifest_file = tmp_path / "journey-manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-04-22T22:17:59.000Z",
                "commit": "deadbeef",
                "nodes": _mk_manifest_nodes(),
                "edges": [],
                "clusters": [],
            }
        )
    )
    monkeypatch.setenv("JOURNEY_MANIFEST_PATH", str(manifest_file))
    return manifest_file


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(api_app)


class _FakeChain:
    """Minimal stand-in for the supabase-py fluent query API.

    Supports the calls ``journey_service`` uses:
        table(name).select(...).execute()
        table(name).select(..., count="exact").execute()
        table(name).select(...).eq(col, v).execute()
    """

    def __init__(self, data: list[dict[str, Any]], count: int | None = None) -> None:
        self._data = data
        self._count = count if count is not None else len(data)
        self._filters: dict[str, Any] = {}

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeChain":
        return self

    def eq(self, col: str, val: Any) -> "_FakeChain":
        self._filters[col] = val
        return self

    def execute(self) -> MagicMock:
        result = [row for row in self._data if _matches(row, self._filters)]
        resp = MagicMock()
        resp.data = result
        resp.count = len([row for row in self._data if _matches(row, self._filters)])
        return resp


def _matches(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(row.get(k) == v for k, v in filters.items())


def _mk_supabase_mock(
    *,
    state_rows: list[dict[str, Any]] | None = None,
    ghost_rows: list[dict[str, Any]] | None = None,
    pin_rows: list[dict[str, Any]] | None = None,
    feedback_rows: list[dict[str, Any]] | None = None,
    role_rows: list[dict[str, Any]] | None = None,
    org_member_rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a mock Supabase client with predictable per-table data."""
    tables = {
        "journey_node_state": state_rows or [],
        "journey_ghost_nodes": ghost_rows or [],
        "journey_pins": pin_rows or [],
        "user_feedback": feedback_rows or [],
        "user_roles": role_rows or [],
        "organization_members": org_member_rows or [],
    }

    sb = MagicMock()

    def table(name: str) -> _FakeChain:
        return _FakeChain(tables.get(name, []))

    sb.table.side_effect = table
    return sb


# ---------------------------------------------------------------------------
# Tests — unit tests on the service, then handler-level integration
# ---------------------------------------------------------------------------


class TestJourneyServiceAggregation:
    """``services.journey_service.get_nodes_aggregated`` — merge semantics."""

    def test_get_nodes_returns_merged_manifest_state_counts(
        self, manifest_path: Path
    ) -> None:
        """Happy path: manifest × state × counts merged per node.

        Asserts every node from the manifest appears with its impl_status,
        qa_status, pins_count, feedback_count, stories_count fields set
        from the joined data (Req 4.3–4.8).
        """
        from services import journey_service

        state_rows = [
            {
                "node_id": "app:/quotes",
                "impl_status": "done",
                "qa_status": "verified",
                "notes": None,
                "version": 3,
                "updated_at": "2026-04-22T10:00:00+00:00",
            }
        ]
        pin_rows = [
            {"id": "p1", "node_id": "app:/quotes"},
            {"id": "p2", "node_id": "app:/quotes"},
            {"id": "p3", "node_id": "app:/deals"},
        ]
        feedback_rows = [
            {"id": "f1", "node_id": "app:/quotes", "user_id": "admin-user"},
            {"id": "f2", "node_id": "app:/quotes", "user_id": "someone-else"},
            {"id": "f3", "node_id": "app:/deals", "user_id": "admin-user"},
        ]
        role_rows = [{"user_id": "admin-user", "roles": {"slug": "admin"}}]

        sb = _mk_supabase_mock(
            state_rows=state_rows,
            pin_rows=pin_rows,
            feedback_rows=feedback_rows,
            role_rows=role_rows,
            org_member_rows=[
                {"user_id": "admin-user", "organization_id": "org-1", "status": "active"}
            ],
        )

        with patch("services.journey_service.get_supabase", return_value=sb):
            nodes = journey_service.get_nodes_aggregated(
                user_id="admin-user", role_slugs={"admin"}
            )

        by_id = {n.node_id: n for n in nodes}

        # Req 4.4 / 4.6 / 4.8 — /quotes has a state row + pins + feedback.
        quotes = by_id["app:/quotes"]
        assert quotes.impl_status == "done"
        assert quotes.qa_status == "verified"
        assert quotes.version == 3
        assert quotes.pins_count == 2
        assert quotes.feedback_count == 2  # admin sees both feedback rows
        assert quotes.stories_count == 2  # from manifest

        # Req 4.4 — /admin/users has no state row, counts default to 0.
        admin_users = by_id["app:/admin/users"]
        assert admin_users.impl_status is None
        assert admin_users.qa_status is None
        assert admin_users.version == 0
        assert admin_users.pins_count == 0
        assert admin_users.feedback_count == 0
        assert admin_users.stories_count == 0

        # Scalar counts for /deals (1 pin, 1 feedback, 0 stories).
        deals = by_id["app:/deals"]
        assert deals.pins_count == 1
        assert deals.feedback_count == 1
        assert deals.stories_count == 0

    def test_get_nodes_feedback_count_respects_access_rules(
        self, manifest_path: Path
    ) -> None:
        """Non-admin caller sees only feedback they submitted themselves.

        Mirrors the `/admin/feedback` page which is admin-gated in the
        frontend (Req 11.2). The API must enforce the same rule server-side
        so the per-node feedback badge never leaks other users' rows.
        """
        from services import journey_service

        feedback_rows = [
            {"id": "f1", "node_id": "app:/quotes", "user_id": "sales-user"},
            {"id": "f2", "node_id": "app:/quotes", "user_id": "someone-else"},
            {"id": "f3", "node_id": "app:/quotes", "user_id": "admin-user"},
        ]

        sb = _mk_supabase_mock(feedback_rows=feedback_rows)

        with patch("services.journey_service.get_supabase", return_value=sb):
            nodes = journey_service.get_nodes_aggregated(
                user_id="sales-user", role_slugs={"sales"}
            )

        quotes = next(n for n in nodes if n.node_id == "app:/quotes")
        # Only the row owned by sales-user counts toward the badge.
        assert quotes.feedback_count == 1

    def test_get_nodes_includes_nodes_with_no_state(
        self, manifest_path: Path
    ) -> None:
        """Manifest nodes without a state row still appear in the response.

        Default status is ``impl_status=None``, ``qa_status=None`` — the
        UI renders these as grey dots (Req 4.4 "grey=unset").
        """
        from services import journey_service

        # No state, no pins, no feedback — pure manifest.
        sb = _mk_supabase_mock()

        with patch("services.journey_service.get_supabase", return_value=sb):
            nodes = journey_service.get_nodes_aggregated(
                user_id="u-1", role_slugs={"sales"}
            )

        node_ids = {n.node_id for n in nodes}
        # All three manifest nodes must be present.
        assert node_ids == {"app:/quotes", "app:/admin/users", "app:/deals"}

        for n in nodes:
            assert n.impl_status is None
            assert n.qa_status is None
            assert n.version == 0
            assert n.updated_at is None

    def test_get_nodes_includes_ghost_nodes(self, manifest_path: Path) -> None:
        """Ghost-node rows surface alongside ``app:*`` entries.

        Ghost nodes carry their own ``title``/``cluster``/``proposed_route``
        (they're absent from the manifest) and a ``ghost_status`` field that
        is ``None`` for ``app:*`` rows.
        """
        from services import journey_service

        ghost_rows = [
            {
                "id": "g1",
                "node_id": "ghost:future-payments",
                "proposed_route": "/payments",
                "title": "Payments (planned)",
                "planned_in": "phase-7",
                "cluster": "finance",
                "status": "proposed",
            }
        ]

        sb = _mk_supabase_mock(ghost_rows=ghost_rows)

        with patch("services.journey_service.get_supabase", return_value=sb):
            nodes = journey_service.get_nodes_aggregated(
                user_id="u-1", role_slugs={"admin"}
            )

        by_id = {n.node_id: n for n in nodes}
        assert "ghost:future-payments" in by_id
        ghost = by_id["ghost:future-payments"]
        assert ghost.title == "Payments (planned)"
        assert ghost.cluster == "finance"
        assert ghost.proposed_route == "/payments"
        assert ghost.ghost_status == "proposed"
        # Real nodes have no ghost_status.
        assert by_id["app:/quotes"].ghost_status is None


class TestGetNodesEndpoint:
    """``GET /api/journey/nodes`` — handler-level envelope + wiring contract."""

    def test_endpoint_returns_success_envelope_with_list(
        self, api_client: TestClient, manifest_path: Path
    ) -> None:
        """Hitting ``/api/journey/nodes`` returns the standard envelope.

        Shape: ``{success: true, data: [...]}``. The handler must accept a
        missing Authorization header (dual-auth fallback) and produce data
        for unauthenticated calls during the scaffold era — this test just
        locks in the envelope contract, not the unauth-visibility policy.
        """
        from services import journey_service

        sb = _mk_supabase_mock()

        with patch.object(journey_service, "get_supabase", return_value=sb):
            response = api_client.get("/api/journey/nodes")

        # Must not 404 (router mounted) nor 500.
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("success") is True, body
        assert "data" in body
        assert isinstance(body["data"], list)

    def test_endpoint_data_shape_matches_aggregated_model(
        self, api_client: TestClient, manifest_path: Path
    ) -> None:
        """Each row in ``data`` must carry the canvas-required fields.

        Locks in the wire-level contract consumed by the Next.js canvas:
        node_id, route, cluster, impl_status, qa_status, stories_count,
        feedback_count, pins_count — Req 4.3–4.8.
        """
        from services import journey_service

        sb = _mk_supabase_mock()

        with patch.object(journey_service, "get_supabase", return_value=sb):
            response = api_client.get("/api/journey/nodes")

        assert response.status_code == 200
        rows = response.json()["data"]
        assert rows, "expected at least one manifest node"
        sample = rows[0]
        for key in (
            "node_id",
            "route",
            "title",
            "cluster",
            "roles",
            "impl_status",
            "qa_status",
            "version",
            "stories_count",
            "feedback_count",
            "pins_count",
        ):
            assert key in sample, f"Missing key {key!r} in aggregated row: {sample}"
