"""Tests for api/integrations.py + /api/internal/feedback/... — Phase 6B-8.

Covers:
- api.integrations.telegram_webhook (handler)
- api.feedback.update_feedback_status (handler, internal auth)
- Route registration on the FastAPI sub-app for both paths.
- OpenAPI schema contains both paths.

Telegram + Supabase side effects are mocked; we verify the handler's
request/response envelope, auth gates, and dispatch branches.
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

from api.app import api_sub_app  # noqa: E402
from api.feedback import update_feedback_status  # noqa: E402
from api.integrations import telegram_webhook  # noqa: E402


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def _make_webhook_request(
    body_bytes: bytes | None = None,
    raise_on_body: bool = False,
):
    """Build a minimal Starlette-style request for the telegram webhook."""
    req = MagicMock()
    req.headers = {"content-type": "application/json"}

    async def _body():
        if raise_on_body:
            raise RuntimeError("body read failed")
        return body_bytes or b"{}"

    req.body = _body
    return req


def _make_internal_request(
    *,
    key_header: str | None = "correct-key",
    status: str = "resolved",
):
    """Build a request for /api/internal/feedback/{short_id}/status."""
    req = MagicMock()
    headers = {}
    if key_header is not None:
        headers["x-internal-key"] = key_header
    req.headers = headers
    req.query_params = {"status": status}
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
# Telegram webhook handler tests
# ----------------------------------------------------------------------------


class TestTelegramWebhookHandler:
    """api.integrations.telegram_webhook behaviour."""

    @patch("api.integrations.is_bot_configured", return_value=False)
    def test_bot_not_configured_returns_ok_with_message(self, _mock_cfg):
        """Unconfigured bot → 200 ok with 'Bot not configured' note."""
        req = _make_webhook_request()
        resp = _run(telegram_webhook(req))
        assert resp.status_code == 200
        assert _body(resp) == {"ok": True, "message": "Bot not configured"}

    @patch("api.integrations.is_bot_configured", return_value=True)
    def test_invalid_json_returns_error_envelope(self, _mock_cfg):
        """Body that fails to parse as JSON → 200 ok:false with error."""
        req = _make_webhook_request(body_bytes=b"not-json{")
        resp = _run(telegram_webhook(req))
        assert resp.status_code == 200
        assert _body(resp) == {"ok": False, "error": "Invalid request body"}

    @patch("api.integrations.process_webhook_update", new_callable=AsyncMock)
    @patch("api.integrations.is_bot_configured", return_value=True)
    def test_valid_update_returns_ok(self, _mock_cfg, mock_process):
        """Valid Telegram update body → 200 ok:true after dispatch."""
        mock_process.return_value = SimpleNamespace(
            success=True,
            update_type="other",
            telegram_id=None,
            text=None,
            args=None,
            telegram_username=None,
            callback_data=None,
            message="ok",
            error=None,
        )
        req = _make_webhook_request(body_bytes=b'{"update_id": 42}')

        resp = _run(telegram_webhook(req))

        assert resp.status_code == 200
        assert _body(resp) == {"ok": True}
        mock_process.assert_awaited_once()

    @patch("api.integrations.process_webhook_update", new_callable=AsyncMock)
    @patch("api.integrations.is_bot_configured", return_value=True)
    def test_process_exception_returns_ok_to_prevent_retries(
        self, _mock_cfg, mock_process
    ):
        """Internal failure still returns 200 so Telegram doesn't retry."""
        mock_process.side_effect = RuntimeError("telegram-down")
        req = _make_webhook_request(body_bytes=b'{"update_id": 1}')

        resp = _run(telegram_webhook(req))

        assert resp.status_code == 200
        payload = _body(resp)
        assert payload["ok"] is True
        assert "telegram-down" in payload["error"]


# ----------------------------------------------------------------------------
# Internal feedback status handler tests
# ----------------------------------------------------------------------------


class TestInternalFeedbackStatusHandler:
    """api.feedback.update_feedback_status (internal/X-Internal-Key path)."""

    def test_missing_key_returns_401(self):
        """No X-Internal-Key → 401 Unauthorized."""
        with patch("api.feedback.INTERNAL_API_KEY", "correct-key"):
            req = _make_internal_request(key_header=None)
            resp = _run(update_feedback_status(req, "FB-TEST"))
        assert resp.status_code == 401
        assert _body(resp) == {"success": False, "error": "Unauthorized"}

    def test_wrong_key_returns_401(self):
        """Mismatching X-Internal-Key → 401 Unauthorized."""
        with patch("api.feedback.INTERNAL_API_KEY", "correct-key"):
            req = _make_internal_request(key_header="bad-key")
            resp = _run(update_feedback_status(req, "FB-TEST"))
        assert resp.status_code == 401
        assert _body(resp) == {"success": False, "error": "Unauthorized"}

    def test_empty_configured_key_rejects_all(self):
        """If INTERNAL_API_KEY is empty, every request is rejected."""
        with patch("api.feedback.INTERNAL_API_KEY", ""):
            req = _make_internal_request(key_header="")
            resp = _run(update_feedback_status(req, "FB-TEST"))
        assert resp.status_code == 401

    def test_valid_key_dispatches_to_service(self):
        """Valid key + resolved status → service called and result echoed."""
        fake_result = SimpleNamespace(
            success=True,
            message="ok",
            telegram_notified=True,
            clickup_synced=False,
        )
        svc_mock = AsyncMock(return_value=fake_result)

        fake_module = MagicMock()
        fake_module.update_feedback_status = svc_mock

        with patch("api.feedback.INTERNAL_API_KEY", "correct-key"):
            with patch.dict(
                "sys.modules", {"services.feedback_service": fake_module}
            ):
                req = _make_internal_request(
                    key_header="correct-key", status="resolved"
                )
                resp = _run(update_feedback_status(req, "FB-XYZ"))

        assert resp.status_code == 200
        assert _body(resp) == {
            "success": True,
            "message": "ok",
            "telegram_notified": True,
            "clickup_synced": False,
        }
        svc_mock.assert_awaited_once_with("FB-XYZ", "resolved")

    def test_service_failure_returns_400(self):
        """Service returning success=False → 400 with the same payload."""
        fake_result = SimpleNamespace(
            success=False,
            message="Invalid status: foo",
            telegram_notified=False,
            clickup_synced=False,
        )
        svc_mock = AsyncMock(return_value=fake_result)
        fake_module = MagicMock()
        fake_module.update_feedback_status = svc_mock

        with patch("api.feedback.INTERNAL_API_KEY", "correct-key"):
            with patch.dict(
                "sys.modules", {"services.feedback_service": fake_module}
            ):
                req = _make_internal_request(
                    key_header="correct-key", status="foo"
                )
                resp = _run(update_feedback_status(req, "FB-ZZZ"))

        assert resp.status_code == 400
        assert _body(resp)["success"] is False


# ----------------------------------------------------------------------------
# Route registration (sub-app)
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_sub_app)


class TestIntegrationsRoutesRegistered:
    """Assert integrations paths are wired on the FastAPI sub-app."""

    def test_telegram_webhook_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /telegram/webhook must exist (not 404)."""
        response = subapp_client.post("/telegram/webhook", json={})
        # No bot config → handler returns 200 with a "not configured" hint or
        # processes the (empty) update. 404 would mean routing is broken.
        assert response.status_code != 404, (
            f"Route not registered: POST /telegram/webhook returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_internal_feedback_status_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /internal/feedback/{short_id}/status must exist (not 404)."""
        response = subapp_client.post("/internal/feedback/FB-X/status")
        # No X-Internal-Key → handler returns 401. 404 means routing is broken.
        assert response.status_code != 404, (
            f"Route not registered: POST /internal/feedback/... returned 404. "
            f"Body: {response.text[:200]}"
        )
        assert response.status_code == 401


# ----------------------------------------------------------------------------
# OpenAPI schema
# ----------------------------------------------------------------------------


class TestIntegrationsOpenApiSchema:
    """Verify integrations endpoints appear in the auto-generated OpenAPI."""

    def test_schema_includes_telegram_webhook(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/telegram/webhook" in paths, (
            f"Missing /telegram/webhook in OpenAPI. "
            f"Present: {sorted(paths.keys())}"
        )
        assert "post" in paths["/telegram/webhook"]

    def test_schema_includes_internal_feedback_status(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/internal/feedback/{short_id}/status" in paths, (
            f"Missing /internal/feedback/{{short_id}}/status in OpenAPI. "
            f"Present: {sorted(paths.keys())}"
        )
        assert "post" in paths["/internal/feedback/{short_id}/status"]


# ----------------------------------------------------------------------------
# Integration via outer FastHTML app (verifies the /api mount routes correctly)
# ----------------------------------------------------------------------------


@pytest.fixture
def outer_app_client() -> TestClient:
    """TestClient wired to the FastHTML app — exercises the real /api mount."""
    try:
        with patch("services.database.get_supabase") as mock_get_sb:
            mock_get_sb.return_value = MagicMock()
            from main import app as outer_app
    except Exception as exc:  # pragma: no cover — diagnostic only
        pytest.skip(f"Cannot import outer app: {exc}")
    return TestClient(outer_app)


class TestIntegrationsMountIntegration:
    """Verify /api/telegram/* + /api/internal/* reach the FastAPI sub-app."""

    def test_telegram_webhook_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/telegram/webhook must resolve through the mount."""
        response = outer_app_client.post("/api/telegram/webhook", json={})
        # Handler always returns 200 (even on failure). 404 would mean routing
        # is broken.
        assert response.status_code != 404, (
            f"Mount routing broken for POST /api/telegram/webhook. "
            f"Body: {response.text[:200]}"
        )

    def test_internal_feedback_status_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/internal/feedback/{id}/status must resolve through mount."""
        response = outer_app_client.post(
            "/api/internal/feedback/FB-NOAUTH/status"
        )
        # No X-Internal-Key → handler returns 401. 404 would mean routing is
        # broken.
        assert response.status_code != 404, (
            f"Mount routing broken for /api/internal/feedback/... "
            f"Body: {response.text[:200]}"
        )
