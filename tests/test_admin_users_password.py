"""Tests for api/admin_users.reset_user_password (admin password reset)."""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import admin_users  # noqa: E402
from api.admin_users import reset_user_password  # noqa: E402

ADMIN = {"id": "admin-1", "email": "a@x.com", "org_id": "org-1"}
TARGET = "22222222-2222-2222-2222-222222222222"


def _make_request(*, api_user_id="admin-1", body=None, raw_body_error=False):
    req = MagicMock()
    req.state = SimpleNamespace(
        api_user=None
        if api_user_id is None
        else SimpleNamespace(id=api_user_id, email="a@x.com")
    )
    req.headers = {"content-type": "application/json"}

    async def _json():
        if raw_body_error:
            raise ValueError("bad json")
        return body or {}

    req.json = _json
    return req


def _run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(resp) -> dict:
    return json.loads(resp.body)


def test_no_auth_returns_401():
    """No api_user -> 401 (via _get_admin_user, before any supabase call)."""
    req = _make_request(api_user_id=None)
    resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 401
    assert _body(resp)["error"]["code"] == "UNAUTHORIZED"


def test_missing_password_returns_400():
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)):
        req = _make_request(body={})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


def test_short_password_returns_400():
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)):
        req = _make_request(body={"password": "short"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


def test_target_not_in_org_returns_404():
    from starlette.responses import JSONResponse

    not_found = JSONResponse(
        {"success": False, "error": {"code": "NOT_FOUND", "message": "x"}},
        status_code=404,
    )
    with patch.object(
        admin_users, "_get_admin_user", return_value=(ADMIN, None)
    ), patch.object(
        admin_users, "_verify_user_in_org", return_value=(None, not_found)
    ):
        req = _make_request(body={"password": "validpass123"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 404


def test_success_calls_update_user_by_id_and_returns_200():
    sb = MagicMock()
    with patch.object(
        admin_users, "_get_admin_user", return_value=(ADMIN, None)
    ), patch.object(
        admin_users, "_verify_user_in_org", return_value=({"user_id": TARGET}, None)
    ), patch.object(admin_users, "get_supabase", return_value=sb):
        req = _make_request(body={"password": "validpass123"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 200
    assert _body(resp) == {"success": True, "data": {"user_id": TARGET}}
    sb.auth.admin.update_user_by_id.assert_called_once_with(
        TARGET, {"password": "validpass123"}
    )


def test_supabase_failure_returns_500():
    sb = MagicMock()
    sb.auth.admin.update_user_by_id.side_effect = Exception("boom")
    with patch.object(
        admin_users, "_get_admin_user", return_value=(ADMIN, None)
    ), patch.object(
        admin_users, "_verify_user_in_org", return_value=({"user_id": TARGET}, None)
    ), patch.object(admin_users, "get_supabase", return_value=sb):
        req = _make_request(body={"password": "validpass123"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 500
    assert _body(resp)["error"]["code"] == "SERVER_ERROR"


def test_password_is_never_logged():
    sb = MagicMock()
    with patch.object(
        admin_users, "_get_admin_user", return_value=(ADMIN, None)
    ), patch.object(
        admin_users, "_verify_user_in_org", return_value=({"user_id": TARGET}, None)
    ), patch.object(admin_users, "get_supabase", return_value=sb), patch.object(
        admin_users, "logger"
    ) as mock_logger:
        req = _make_request(body={"password": "secretpw123"})
        _run(reset_user_password(req, TARGET))
    logged = " ".join(str(c) for c in mock_logger.mock_calls)
    assert "secretpw123" not in logged
