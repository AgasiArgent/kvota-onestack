"""Tests for ``GET /api/journey/node/{node_id}`` — the drawer-detail endpoint (Task 11).

The endpoint composes five data sources into the payload consumed by the
node-detail drawer (design.md §4.4 row for ``GET /node/{node_id}``):

1. Manifest node — route / title / cluster / roles / stories (from
   ``frontend/public/journey-manifest.json``). Ghost-only rows come from
   ``kvota.journey_ghost_nodes`` when the node_id is not in the manifest.
2. ``kvota.journey_node_state`` — mutable impl/qa status, version,
   notes. Absent → defaults (impl_status=None, version=0).
3. ``kvota.journey_pins`` — QA and training pins anchored to this node.
4. ``kvota.journey_verifications`` — the *latest* verification per pin
   (ordered by ``tested_at`` DESC, one row per pin). Exposed as
   ``verifications_by_pin: {pin_id: JourneyVerification}``.
5. ``kvota.user_feedback`` — top-3 rows for the node ordered by
   ``created_at`` DESC, filtered by ``_filter_feedback_visible`` so non-admin
   callers only see their own rows (Req 11.2, mirroring the ``/admin/feedback``
   admin-gate).

Tests mock Supabase via ``services.journey_service.get_supabase`` (the same
pattern as ``tests/test_api_journey_nodes.py``). No live DB access required.
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_app  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers — minimal manifest + _FakeChain supporting order+limit
# ---------------------------------------------------------------------------


def _mk_manifest_nodes() -> list[dict[str, Any]]:
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
            ],
            "parent_node_id": None,
            "children": [],
        },
    ]


@pytest.fixture
def manifest_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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
    """Stand-in for supabase-py fluent API — select/eq/order/limit/execute."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data
        self._filters: dict[str, Any] = {}
        self._order: tuple[str, bool] | None = None  # (column, desc)
        self._limit: int | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeChain":
        return self

    def eq(self, col: str, val: Any) -> "_FakeChain":
        self._filters[col] = val
        return self

    def order(self, col: str, desc: bool = False) -> "_FakeChain":
        self._order = (col, desc)
        return self

    def limit(self, n: int) -> "_FakeChain":
        self._limit = n
        return self

    def execute(self) -> MagicMock:
        result = [row for row in self._data if _matches(row, self._filters)]
        if self._order is not None:
            col, desc = self._order
            result = sorted(result, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit is not None:
            result = result[: self._limit]
        resp = MagicMock()
        resp.data = result
        resp.count = len(result)
        return resp


def _matches(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(row.get(k) == v for k, v in filters.items())


def _mk_supabase_mock(
    *,
    state_rows: list[dict[str, Any]] | None = None,
    ghost_rows: list[dict[str, Any]] | None = None,
    pin_rows: list[dict[str, Any]] | None = None,
    verification_rows: list[dict[str, Any]] | None = None,
    feedback_rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    tables = {
        "journey_node_state": state_rows or [],
        "journey_ghost_nodes": ghost_rows or [],
        "journey_pins": pin_rows or [],
        "journey_verifications": verification_rows or [],
        "user_feedback": feedback_rows or [],
    }

    sb = MagicMock()

    def table(name: str) -> _FakeChain:
        return _FakeChain(tables.get(name, []))

    sb.table.side_effect = table
    return sb


# ---------------------------------------------------------------------------
# Service-level tests — get_node_detail
# ---------------------------------------------------------------------------


class TestJourneyServiceGetNodeDetail:
    """``services.journey_service.get_node_detail`` — composition semantics."""

    def test_get_node_returns_state_pins_training_feedback(
        self, manifest_path: Path
    ) -> None:
        """Happy path: state + 3 pins (2 qa, 1 training) + 2 feedback rows.

        Asserts the full response shape: manifest fields (route/title/cluster/
        roles/stories_count) + state fields (impl_status/qa_status/version) +
        pins list + latest verification per pin + top-3 feedback list.
        """
        from services import journey_service

        state_rows = [
            {
                "node_id": "app:/quotes",
                "impl_status": "partial",
                "qa_status": "untested",
                "notes": "needs polish",
                "version": 5,
                "updated_at": "2026-04-22T12:00:00+00:00",
            }
        ]
        pin_rows = [
            {
                "id": "pin-1",
                "node_id": "app:/quotes",
                "selector": "[data-testid='save']",
                "expected_behavior": "clicking save creates quote",
                "mode": "qa",
                "training_step_order": None,
                "linked_story_ref": None,
                "last_rel_x": None,
                "last_rel_y": None,
                "last_rel_width": None,
                "last_rel_height": None,
                "last_position_update": None,
                "selector_broken": False,
                "created_by": "admin-user",
                "created_at": "2026-04-20T10:00:00+00:00",
            },
            {
                "id": "pin-2",
                "node_id": "app:/quotes",
                "selector": "[data-testid='cancel']",
                "expected_behavior": "clicking cancel returns to list",
                "mode": "qa",
                "training_step_order": None,
                "linked_story_ref": None,
                "last_rel_x": None,
                "last_rel_y": None,
                "last_rel_width": None,
                "last_rel_height": None,
                "last_position_update": None,
                "selector_broken": False,
                "created_by": "admin-user",
                "created_at": "2026-04-20T10:05:00+00:00",
            },
            {
                "id": "pin-3",
                "node_id": "app:/quotes",
                "selector": "#onboarding-step-1",
                "expected_behavior": "highlight save button for newcomers",
                "mode": "training",
                "training_step_order": 1,
                "linked_story_ref": "phase-5b#1",
                "last_rel_x": None,
                "last_rel_y": None,
                "last_rel_width": None,
                "last_rel_height": None,
                "last_position_update": None,
                "selector_broken": False,
                "created_by": "admin-user",
                "created_at": "2026-04-20T10:10:00+00:00",
            },
        ]
        # Two verifications on pin-1, one on pin-2, none on pin-3. The
        # latest (tested_at DESC) must win per pin.
        verification_rows = [
            {
                "id": "ver-1a",
                "pin_id": "pin-1",
                "node_id": "app:/quotes",
                "result": "broken",
                "note": "old run",
                "attachment_urls": None,
                "tested_by": "admin-user",
                "tested_at": "2026-04-21T09:00:00+00:00",
            },
            {
                "id": "ver-1b",
                "pin_id": "pin-1",
                "node_id": "app:/quotes",
                "result": "verified",
                "note": "fixed",
                "attachment_urls": None,
                "tested_by": "admin-user",
                "tested_at": "2026-04-22T09:00:00+00:00",
            },
            {
                "id": "ver-2",
                "pin_id": "pin-2",
                "node_id": "app:/quotes",
                "result": "verified",
                "note": None,
                "attachment_urls": None,
                "tested_by": "admin-user",
                "tested_at": "2026-04-22T09:30:00+00:00",
            },
        ]
        feedback_rows = [
            {
                "id": "fb-1",
                "short_id": "FB-001",
                "node_id": "app:/quotes",
                "user_id": "admin-user",
                "description": "oldest",
                "feedback_type": "bug",
                "status": "new",
                "created_at": "2026-04-20T00:00:00+00:00",
            },
            {
                "id": "fb-2",
                "short_id": "FB-002",
                "node_id": "app:/quotes",
                "user_id": "someone-else",
                "description": "newest",
                "feedback_type": "improvement",
                "status": "new",
                "created_at": "2026-04-22T00:00:00+00:00",
            },
        ]

        sb = _mk_supabase_mock(
            state_rows=state_rows,
            pin_rows=pin_rows,
            verification_rows=verification_rows,
            feedback_rows=feedback_rows,
        )

        with patch("services.journey_service.get_supabase", return_value=sb):
            detail = journey_service.get_node_detail(
                node_id="app:/quotes",
                user_id="admin-user",
                role_slugs=frozenset({"admin"}),
            )

        assert detail is not None, "expected a detail payload for a known node"

        # Manifest fields.
        assert detail.node_id == "app:/quotes"
        assert detail.route == "/quotes"
        assert detail.title == "Quotes"
        assert detail.cluster == "quotes"
        assert list(detail.roles) == ["sales", "quote_controller"]
        assert detail.stories_count == 1

        # State fields.
        assert detail.impl_status == "partial"
        assert detail.qa_status == "untested"
        assert detail.version == 5
        assert detail.notes == "needs polish"
        assert detail.updated_at == "2026-04-22T12:00:00+00:00"

        # Pins list — all three, in stable order.
        assert len(detail.pins) == 3
        pin_ids = {p.id for p in detail.pins}
        assert pin_ids == {"pin-1", "pin-2", "pin-3"}
        modes = {p.id: p.mode for p in detail.pins}
        assert modes == {"pin-1": "qa", "pin-2": "qa", "pin-3": "training"}

        # Latest verification per pin.
        assert set(detail.verifications_by_pin.keys()) == {"pin-1", "pin-2"}
        assert detail.verifications_by_pin["pin-1"].id == "ver-1b"
        assert detail.verifications_by_pin["pin-1"].result == "verified"
        assert detail.verifications_by_pin["pin-2"].id == "ver-2"
        # pin-3 has no verification — absent from dict.
        assert "pin-3" not in detail.verifications_by_pin

        # Feedback top-3 ordered by created_at DESC. Admin sees both.
        assert len(detail.feedback) == 2
        assert detail.feedback[0].id == "fb-2"  # newest first
        assert detail.feedback[1].id == "fb-1"

    def test_get_node_returns_none_for_unknown_node_id(
        self, manifest_path: Path
    ) -> None:
        """Unknown node_id → service returns ``None`` (handler translates to 404)."""
        from services import journey_service

        sb = _mk_supabase_mock()

        with patch("services.journey_service.get_supabase", return_value=sb):
            detail = journey_service.get_node_detail(
                node_id="app:/does-not-exist",
                user_id="admin-user",
                role_slugs=frozenset({"admin"}),
            )

        assert detail is None


# ---------------------------------------------------------------------------
# Handler-level tests — GET /api/journey/node/{node_id}
# ---------------------------------------------------------------------------


class TestGetNodeDetailEndpoint:
    """HTTP contract: envelope + 404 behaviour."""

    def test_get_node_returns_state_pins_training_feedback(
        self, api_client: TestClient, manifest_path: Path
    ) -> None:
        """End-to-end: known node → 200 with data envelope containing all sections."""
        from services import journey_service

        sb = _mk_supabase_mock(
            state_rows=[
                {
                    "node_id": "app:/quotes",
                    "impl_status": "done",
                    "qa_status": "verified",
                    "notes": None,
                    "version": 2,
                    "updated_at": "2026-04-22T12:00:00+00:00",
                }
            ],
            pin_rows=[
                {
                    "id": "pin-a",
                    "node_id": "app:/quotes",
                    "selector": "[data-testid='x']",
                    "expected_behavior": "x happens",
                    "mode": "qa",
                    "training_step_order": None,
                    "linked_story_ref": None,
                    "last_rel_x": None,
                    "last_rel_y": None,
                    "last_rel_width": None,
                    "last_rel_height": None,
                    "last_position_update": None,
                    "selector_broken": False,
                    "created_by": "admin-user",
                    "created_at": "2026-04-20T10:00:00+00:00",
                }
            ],
            feedback_rows=[
                {
                    "id": "fb-a",
                    "short_id": "FB-A",
                    "node_id": "app:/quotes",
                    "user_id": "admin-user",
                    "description": "a",
                    "feedback_type": "bug",
                    "status": "new",
                    "created_at": "2026-04-22T00:00:00+00:00",
                }
            ],
        )

        # Patch resolve_caller_context so anonymous test client is treated
        # as admin for the purpose of the feedback visibility filter
        # (Req 11.2 — anonymous callers would see zero feedback rows).
        with patch.object(journey_service, "get_supabase", return_value=sb), patch.object(
            journey_service,
            "resolve_caller_context",
            return_value=("admin-user", frozenset({"admin"})),
        ):
            response = api_client.get("/api/journey/node/app:/quotes")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("success") is True, body
        data = body["data"]
        # Core sections are present on the wire.
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
            "pins",
            "verifications_by_pin",
            "feedback",
        ):
            assert key in data, f"Missing key {key!r} in response: {data}"
        assert data["node_id"] == "app:/quotes"
        assert len(data["pins"]) == 1
        assert len(data["feedback"]) == 1

    def test_get_node_404_when_unknown_node_id(
        self, api_client: TestClient, manifest_path: Path
    ) -> None:
        """Unknown node_id → 404 with standard error envelope + NOT_FOUND code."""
        from services import journey_service

        sb = _mk_supabase_mock()

        with patch.object(journey_service, "get_supabase", return_value=sb):
            response = api_client.get("/api/journey/node/app:/nope")

        assert response.status_code == 404, response.text
        body = response.json()
        assert body.get("success") is False, body
        assert body["error"]["code"] == "NOT_FOUND"
        assert "message" in body["error"]
