"""Tests for Task 13 — node history endpoint + Playwright webhook.

Two endpoints land together in this task:

1. ``GET /api/journey/node/{node_id}/history`` — reads the append-only audit
   log at ``kvota.journey_node_state_history`` (populated by the AFTER UPDATE
   trigger from migration 500). Returns up to 50 rows ordered by ``changed_at``
   DESC so the drawer's "history" tab can render a reverse-chronological list.

2. ``POST /api/journey/playwright-webhook`` — protected by the
   ``X-Journey-Webhook-Token`` header compared to env ``JOURNEY_WEBHOOK_TOKEN``
   via ``hmac.compare_digest`` (constant-time). Body is a batch of pin-bbox
   refreshes: each update either writes new ``last_rel_*`` / flips
   ``selector_broken=false`` (bbox present) or flips ``selector_broken=true``
   without touching bbox fields (bbox absent / null).

Tests mock Supabase via ``services.journey_service.get_supabase``. No live DB.
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(api_app)


@pytest.fixture
def webhook_token(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "s3cret-playwright-token"
    monkeypatch.setenv("JOURNEY_WEBHOOK_TOKEN", token)
    return token


class _FakeHistoryChain:
    """Supabase-py fluent chain stub supporting select/eq/order/limit/execute."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data
        self._filters: dict[str, Any] = {}
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeHistoryChain":
        return self

    def eq(self, col: str, val: Any) -> "_FakeHistoryChain":
        self._filters[col] = val
        return self

    def order(self, col: str, desc: bool = False) -> "_FakeHistoryChain":
        self._order = (col, desc)
        return self

    def limit(self, n: int) -> "_FakeHistoryChain":
        self._limit = n
        return self

    def execute(self) -> MagicMock:
        rows = [row for row in self._data if all(row.get(k) == v for k, v in self._filters.items())]
        if self._order is not None:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        resp = MagicMock()
        resp.data = rows
        resp.count = len(rows)
        return resp


class _FakeUpdateChain:
    """Supabase-py update-chain stub: ``.table(x).update({...}).eq(...).execute()``.

    Records every update call into ``calls`` on the parent so tests can assert
    which pins were touched and with what payload.
    """

    def __init__(self, pins: dict[str, dict[str, Any]], calls: list[dict[str, Any]]) -> None:
        self._pins = pins
        self._calls = calls
        self._pending: dict[str, Any] | None = None
        self._filters: dict[str, Any] = {}
        self._is_update = False

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeUpdateChain":
        return self

    def update(self, payload: dict[str, Any]) -> "_FakeUpdateChain":
        self._pending = dict(payload)
        self._is_update = True
        return self

    def eq(self, col: str, val: Any) -> "_FakeUpdateChain":
        self._filters[col] = val
        return self

    def execute(self) -> MagicMock:
        if self._is_update and self._pending is not None:
            pin_id = self._filters.get("id")
            self._calls.append({"pin_id": pin_id, "payload": self._pending, "filters": dict(self._filters)})
            if pin_id in self._pins:
                self._pins[pin_id].update(self._pending)
        resp = MagicMock()
        resp.data = []
        return resp


def _mk_history_supabase(history_rows: list[dict[str, Any]]) -> MagicMock:
    sb = MagicMock()

    def table(name: str) -> _FakeHistoryChain:
        if name == "journey_node_state_history":
            return _FakeHistoryChain(history_rows)
        return _FakeHistoryChain([])

    sb.table.side_effect = table
    return sb


def _mk_webhook_supabase(
    pins: dict[str, dict[str, Any]],
) -> tuple[MagicMock, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    sb = MagicMock()

    def table(name: str) -> _FakeUpdateChain:
        if name == "journey_pins":
            return _FakeUpdateChain(pins, calls)
        return _FakeUpdateChain({}, calls)

    sb.table.side_effect = table
    return sb, calls


# ---------------------------------------------------------------------------
# 1. GET /api/journey/node/{node_id}/history
# ---------------------------------------------------------------------------


class TestGetNodeHistoryEndpoint:
    def test_get_node_history_returns_reverse_chronological_50(
        self, api_client: TestClient
    ) -> None:
        """Seed 60 rows → response has 50, ordered DESC by ``changed_at``."""
        from services import journey_service

        rows: list[dict[str, Any]] = []
        for i in range(60):
            # Pad i to keep ISO string comparison stable (lexicographic ==
            # chronological for fixed-width zero-padded seconds).
            rows.append(
                {
                    "id": f"hist-{i:02d}",
                    "node_id": "app:/quotes",
                    "impl_status": "partial",
                    "qa_status": "untested",
                    "notes": f"change {i}",
                    "version": i + 1,
                    "changed_by": "admin-user",
                    "changed_at": f"2026-04-22T00:{i // 60:02d}:{i % 60:02d}+00:00",
                }
            )
        # Add an unrelated node's row that must NOT appear in response.
        rows.append(
            {
                "id": "hist-other",
                "node_id": "app:/other",
                "impl_status": "done",
                "qa_status": "verified",
                "notes": "unrelated",
                "version": 1,
                "changed_by": "admin-user",
                "changed_at": "2026-04-25T00:00:00+00:00",
            }
        )

        sb = _mk_history_supabase(rows)
        with patch.object(journey_service, "get_supabase", return_value=sb):
            response = api_client.get("/api/journey/node/app:/quotes/history")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("success") is True, body
        data = body["data"]
        assert isinstance(data, list)
        assert len(data) == 50, f"expected 50 rows, got {len(data)}"

        # Reverse-chronological: first > last.
        timestamps = [row["changed_at"] for row in data]
        assert timestamps == sorted(timestamps, reverse=True), "not DESC by changed_at"

        # No rows from a different node.
        node_ids = {row["node_id"] for row in data}
        assert node_ids == {"app:/quotes"}


# ---------------------------------------------------------------------------
# 2. POST /api/journey/playwright-webhook
# ---------------------------------------------------------------------------


class TestPlaywrightWebhookEndpoint:
    def test_playwright_webhook_without_token_returns_401(
        self, api_client: TestClient, webhook_token: str
    ) -> None:
        """No token header → 401 UNAUTHORIZED."""
        response = api_client.post(
            "/api/journey/playwright-webhook",
            json={"updates": []},
        )
        assert response.status_code == 401, response.text
        body = response.json()
        assert body.get("success") is False, body
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_playwright_webhook_batch_updates_all_pins_in_transaction(
        self, api_client: TestClient, webhook_token: str
    ) -> None:
        """Valid batch of 3 bbox updates → all 3 pins updated + selector_broken=false."""
        from services import journey_service

        pins: dict[str, dict[str, Any]] = {
            "pin-1": {"id": "pin-1", "selector_broken": True, "last_rel_x": None},
            "pin-2": {"id": "pin-2", "selector_broken": True, "last_rel_x": None},
            "pin-3": {"id": "pin-3", "selector_broken": False, "last_rel_x": None},
        }
        sb, calls = _mk_webhook_supabase(pins)

        payload = {
            "updates": [
                {
                    "pin_id": "pin-1",
                    "bbox": {
                        "rel_x": 0.1,
                        "rel_y": 0.2,
                        "rel_width": 0.3,
                        "rel_height": 0.4,
                    },
                },
                {
                    "pin_id": "pin-2",
                    "bbox": {
                        "rel_x": 0.5,
                        "rel_y": 0.6,
                        "rel_width": 0.1,
                        "rel_height": 0.1,
                    },
                },
                {
                    "pin_id": "pin-3",
                    "bbox": {
                        "rel_x": 0.7,
                        "rel_y": 0.8,
                        "rel_width": 0.2,
                        "rel_height": 0.05,
                    },
                },
            ]
        }

        with patch.object(journey_service, "get_supabase", return_value=sb):
            response = api_client.post(
                "/api/journey/playwright-webhook",
                headers={"X-Journey-Webhook-Token": webhook_token},
                json=payload,
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("success") is True, body
        assert body["data"]["updated_count"] == 3

        # Exactly 3 UPDATE calls.
        assert len(calls) == 3, calls
        by_pin = {c["pin_id"]: c["payload"] for c in calls}

        for pin_id, expected in [
            ("pin-1", (0.1, 0.2, 0.3, 0.4)),
            ("pin-2", (0.5, 0.6, 0.1, 0.1)),
            ("pin-3", (0.7, 0.8, 0.2, 0.05)),
        ]:
            p = by_pin[pin_id]
            assert p["last_rel_x"] == expected[0]
            assert p["last_rel_y"] == expected[1]
            assert p["last_rel_width"] == expected[2]
            assert p["last_rel_height"] == expected[3]
            assert p["selector_broken"] is False
            assert "last_position_update" in p and p["last_position_update"], (
                "last_position_update should be set to a non-empty timestamp"
            )

    def test_playwright_webhook_selector_broken_flag_set_when_no_bbox(
        self, api_client: TestClient, webhook_token: str
    ) -> None:
        """Update without a bbox → selector_broken=true and bbox fields untouched."""
        from services import journey_service

        pins: dict[str, dict[str, Any]] = {
            "pin-x": {
                "id": "pin-x",
                "selector_broken": False,
                "last_rel_x": 0.11,
                "last_rel_y": 0.22,
                "last_rel_width": 0.33,
                "last_rel_height": 0.44,
            },
        }
        sb, calls = _mk_webhook_supabase(pins)

        payload = {"updates": [{"pin_id": "pin-x", "bbox": None}]}

        with patch.object(journey_service, "get_supabase", return_value=sb):
            response = api_client.post(
                "/api/journey/playwright-webhook",
                headers={"X-Journey-Webhook-Token": webhook_token},
                json=payload,
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("success") is True, body
        assert body["data"]["updated_count"] == 1

        assert len(calls) == 1
        payload_sent = calls[0]["payload"]
        assert payload_sent.get("selector_broken") is True
        # Bbox fields must NOT be rewritten when bbox is absent.
        for field in ("last_rel_x", "last_rel_y", "last_rel_width", "last_rel_height"):
            assert field not in payload_sent, (
                f"{field} should not be in update payload when bbox is missing, got {payload_sent}"
            )
