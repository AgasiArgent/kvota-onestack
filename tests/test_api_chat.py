"""Tests for api/chat.py — Phase 6B-7 extraction of /api/chat/notify.

Covers the handler in isolation (direct call) plus route registration on the
FastAPI sub-app. Supabase / Telegram side effects are mocked — we only
verify the handler's request/response envelope and auth branches.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_app  # noqa: E402
from api.chat import notify  # noqa: E402


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    body: dict | None = None,
    raw_body_error: bool = False,
    content_type: str = "application/json",
):
    """Build a minimal Starlette-style request with JWT user + body."""
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(id=api_user_id, email="u@x.com")
        )
    req.headers = {"content-type": content_type}

    async def _json():
        if raw_body_error:
            raise ValueError("bad json")
        return body or {}

    req.json = _json
    # Mimic Starlette: session raises AssertionError when SessionMiddleware absent.
    type(req).session = property(
        lambda self: (_ for _ in ()).throw(AssertionError("no session"))
    )
    return req


def _run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


# ----------------------------------------------------------------------------
# Handler unit tests
# ----------------------------------------------------------------------------


class TestChatNotifyHandler:
    """POST /api/chat/notify handler behaviour."""

    def test_no_auth_returns_401(self):
        """No JWT + no session → 401 with success=False envelope."""
        req = _make_request(api_user_id=None)
        resp = _run(notify(req))
        assert resp.status_code == 401
        assert _body(resp) == {"success": False, "error": "Unauthorized"}

    def test_invalid_json_returns_400(self):
        """Body that fails to parse as JSON → 400 Invalid JSON."""
        req = _make_request(raw_body_error=True)
        resp = _run(notify(req))
        assert resp.status_code == 400
        assert _body(resp) == {"success": False, "error": "Invalid JSON"}

    def test_missing_quote_id_returns_400(self):
        """JSON body without quote_id or body → 400 validation envelope."""
        req = _make_request(body={"quote_id": "", "body": "hi"})
        resp = _run(notify(req))
        assert resp.status_code == 400
        assert _body(resp) == {
            "success": False,
            "error": "quote_id and body are required",
        }

    @patch("api.chat.send_chat_message_notification", new_callable=AsyncMock)
    def test_happy_path_returns_notification_result(self, mock_notify):
        """Valid JWT + body → calls service and echoes its result."""
        mock_notify.return_value = {"notified_count": 2}
        req = _make_request(
            body={
                "quote_id": "q-1",
                "body": "hello",
                "mentions": ["user-2"],
            }
        )

        resp = _run(notify(req))

        assert resp.status_code == 200
        assert _body(resp) == {
            "success": True,
            "data": {"notified_count": 2},
        }
        mock_notify.assert_awaited_once_with(
            quote_id="q-1",
            sender_user_id="user-1",
            message_body="hello",
            mentions=["user-2"],
        )

    @patch("api.chat.send_chat_message_notification", new_callable=AsyncMock)
    def test_service_exception_is_swallowed(self, mock_notify):
        """Chat send is best-effort: service failure → 200 with error detail."""
        mock_notify.side_effect = RuntimeError("telegram down")
        req = _make_request(body={"quote_id": "q-1", "body": "msg"})

        resp = _run(notify(req))

        assert resp.status_code == 200
        payload = _body(resp)
        assert payload["success"] is True
        assert payload["data"]["notified_count"] == 0
        assert "telegram down" in payload["data"]["error"]


# ----------------------------------------------------------------------------
# Route registration (sub-app)
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_app)


class TestChatRoutesRegistered:
    """Assert /chat/notify is wired on the FastAPI sub-app."""

    def test_post_notify_registered(self, subapp_client: TestClient) -> None:
        """POST /chat/notify must exist (not 404)."""
        response = subapp_client.post("/chat/notify", json={})
        # No auth attached → handler returns 401. 404 means route not registered.
        assert response.status_code != 404, (
            f"Route not registered: POST /chat/notify returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_openapi_schema_includes_chat_notify(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/chat/notify" in paths
        assert "post" in paths["/chat/notify"]
