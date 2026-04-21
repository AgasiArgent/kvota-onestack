"""Tests for api/feedback.py — Phase 6B-7 extraction of /api/feedback.

The feedback handler supports dual body shapes (JSON for Next.js, form-encoded
for legacy FastHTML) and dual auth (JWT or session). Supabase / ClickUp /
Telegram side effects are mocked — we only verify the handler's
request/response envelope, body dispatch, and auth branches.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import FormData
from starlette.responses import HTMLResponse
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_sub_app  # noqa: E402
from api.feedback import submit_feedback  # noqa: E402


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    email: str = "u@x.com",
    user_metadata: dict | None = None,
    body: dict | None = None,
    content_type: str = "application/json",
    user_agent: str = "tests/ua",
):
    """Build a minimal Starlette-style request for the feedback handler."""
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email=email,
                user_metadata=user_metadata or {},
            )
        )
    req.headers = {"content-type": content_type, "user-agent": user_agent}

    async def _json():
        return body or {}

    async def _form():
        return FormData(list((body or {}).items()))

    req.json = _json
    req.form = _form
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


def _json_body(response) -> dict:
    return json.loads(response.body)


def _make_supabase_mock():
    """Build a Supabase mock covering organization lookup + feedback insert.

    Returns stable per-table mocks so tests can re-fetch
    ``sb.table("user_feedback")`` and inspect ``.insert.call_args``.
    """
    sb = MagicMock()

    orgs_tbl = MagicMock()
    orgs_tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "org-1"}
    ]

    feedback_tbl = MagicMock()
    feedback_tbl.insert.return_value.execute.return_value = MagicMock(data=[{}])
    feedback_tbl.update.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[{}])
    )

    members_tbl = MagicMock()
    members_tbl.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"organization_id": "org-1"}
    ]

    tables = {
        "organizations": orgs_tbl,
        "user_feedback": feedback_tbl,
        "organization_members": members_tbl,
    }

    sb.table.side_effect = lambda name: tables.get(name, MagicMock())
    return sb


# ----------------------------------------------------------------------------
# Handler unit tests
# ----------------------------------------------------------------------------


class TestFeedbackHandler:
    """POST /api/feedback handler behaviour (JSON + form)."""

    def test_no_auth_json_returns_401(self):
        """No JWT + no session + JSON → 401 with UNAUTHORIZED envelope."""
        req = _make_request(api_user_id=None)
        resp = _run(submit_feedback(req))
        assert resp.status_code == 401
        body = _json_body(resp)
        assert body["success"] is False
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_no_auth_form_returns_html(self):
        """No JWT + no session + form → HTML error snippet."""
        req = _make_request(
            api_user_id=None,
            content_type="application/x-www-form-urlencoded",
        )
        resp = _run(submit_feedback(req))
        assert isinstance(resp, HTMLResponse)
        html = resp.body.decode()
        assert "Требуется авторизация" in html

    @patch("api.feedback.send_admin_bug_report_with_photo", new_callable=AsyncMock)
    @patch("api.feedback.create_clickup_bug_task", new_callable=AsyncMock)
    @patch("api.feedback.get_supabase")
    def test_happy_path_json_returns_short_id(
        self, mock_get_sb, mock_clickup, mock_telegram
    ):
        """Valid JWT + JSON body → 200 with short_id in data."""
        sb = _make_supabase_mock()
        mock_get_sb.return_value = sb
        mock_clickup.return_value = "CU-123"

        req = _make_request(
            body={
                "feedback_type": "bug",
                "description": "Something broke",
                "page_url": "https://kvotaflow.ru/quotes/1",
                "page_title": "Quote 1",
                "debug_context": '{"lang":"ru"}',
            },
            user_metadata={"org_id": "org-1"},
        )

        resp = _run(submit_feedback(req))

        assert resp.status_code == 200
        body = _json_body(resp)
        assert body["success"] is True
        short_id = body["data"]["short_id"]
        assert short_id.startswith("FB-")

        # Insert fired with the expected core fields
        insert_call = sb.table("user_feedback").insert.call_args
        assert insert_call is not None
        payload = insert_call.args[0]
        assert payload["feedback_type"] == "bug"
        assert payload["description"] == "Something broke"
        assert payload["user_id"] == "user-1"
        # debug_context parsed from JSON string
        assert payload["debug_context"] == {"lang": "ru"}

        # Fanout calls were awaited with the matching short_id
        assert mock_clickup.await_count == 1
        assert mock_telegram.await_count == 1
        assert mock_clickup.await_args.kwargs["short_id"] == short_id
        assert mock_telegram.await_args.kwargs["short_id"] == short_id

    @patch("api.feedback.send_admin_bug_report_with_photo", new_callable=AsyncMock)
    @patch("api.feedback.create_clickup_bug_task", new_callable=AsyncMock)
    @patch("api.feedback.get_supabase")
    def test_happy_path_form_returns_html_snippet(
        self, mock_get_sb, mock_clickup, mock_telegram
    ):
        """Valid JWT + form body → HTML success snippet for FastHTML modal."""
        sb = _make_supabase_mock()
        mock_get_sb.return_value = sb
        mock_clickup.return_value = None  # ClickUp disabled path

        req = _make_request(
            content_type="application/x-www-form-urlencoded",
            body={
                "feedback_type": "bug",
                "description": "Form bug",
                "page_url": "https://kvotaflow.ru/quotes/1",
                "page_title": "Quote 1",
            },
            user_metadata={"org_id": "org-1"},
        )

        resp = _run(submit_feedback(req))

        assert isinstance(resp, HTMLResponse)
        html = resp.body.decode()
        assert "feedback-success-marker" in html
        assert "Спасибо за обратную связь" in html
        assert "FB-" in html  # short_id rendered
        # Insert was still invoked
        assert sb.table("user_feedback").insert.called

    @patch("api.feedback.get_supabase")
    def test_empty_description_json_returns_400(self, mock_get_sb):
        """Missing description on JSON path → 400 VALIDATION_ERROR."""
        mock_get_sb.return_value = _make_supabase_mock()

        req = _make_request(
            body={"feedback_type": "bug", "description": "   "},
            user_metadata={"org_id": "org-1"},
        )
        resp = _run(submit_feedback(req))

        assert resp.status_code == 400
        body = _json_body(resp)
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.feedback.send_admin_bug_report_with_photo", new_callable=AsyncMock)
    @patch("api.feedback.create_clickup_bug_task", new_callable=AsyncMock)
    @patch.dict(
        os.environ,
        {"SUPABASE_URL": "https://abc.supabase.co"},
        clear=False,
    )
    @patch("api.feedback.get_supabase")
    def test_screenshot_url_outside_supabase_is_dropped(
        self, mock_get_sb, mock_clickup, mock_telegram
    ):
        """Only Supabase-hosted screenshot_url should be persisted."""
        sb = _make_supabase_mock()
        mock_get_sb.return_value = sb
        mock_clickup.return_value = None

        req = _make_request(
            body={
                "description": "hi",
                "screenshot_url": "https://evil.example/steal.png",
            },
            user_metadata={"org_id": "org-1"},
        )
        _run(submit_feedback(req))

        payload = sb.table("user_feedback").insert.call_args.args[0]
        assert "screenshot_url" not in payload


# ----------------------------------------------------------------------------
# Route registration (sub-app)
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_sub_app)


class TestFeedbackRoutesRegistered:
    """Assert /feedback is wired on the FastAPI sub-app."""

    def test_post_feedback_registered(self, subapp_client: TestClient) -> None:
        """POST /feedback must exist (not 404)."""
        response = subapp_client.post("/feedback", json={})
        # No auth → handler returns 401. 404 means route not registered.
        assert response.status_code != 404, (
            f"Route not registered: POST /feedback returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_openapi_schema_includes_feedback(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/feedback" in paths
        assert "post" in paths["/feedback"]
