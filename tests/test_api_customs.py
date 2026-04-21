"""Tests for api/customs.py — Phase 6B-9 extraction of
PATCH /api/customs/{quote_id}/items/bulk.

Covers the handler in isolation (direct call) plus route registration on
the FastAPI sub-app. Supabase side effects are mocked — we only verify the
handler's request/response envelope and auth/role branches.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_sub_app  # noqa: E402
from api.customs import bulk_update_items  # noqa: E402


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    user_metadata: dict | None = None,
    session_user: dict | None = None,
    body: dict | None = None,
    raw_body_error: bool = False,
):
    """Build a minimal Starlette-style request with optional JWT/session + body."""
    req = MagicMock()
    if api_user_id is not None:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email="u@x.com",
                user_metadata=user_metadata or {"org_id": "o-1"},
            )
        )
    else:
        req.state = SimpleNamespace(api_user=None)

    if session_user is not None:
        session = {"user": session_user}
        type(req).session = property(lambda self: session)
    else:
        type(req).session = property(
            lambda self: (_ for _ in ()).throw(AssertionError("no session"))
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


def _body(response) -> dict:
    return json.loads(response.body)


def _mk_quote_row(
    *,
    workflow_status: str = "pending_customs",
    customs_completed_at: str | None = None,
) -> dict:
    return {
        "id": "q-1",
        "workflow_status": workflow_status,
        "customs_completed_at": customs_completed_at,
    }


def _patch_supabase_quote_ok(workflow_status: str = "pending_customs"):
    """Context manager patching get_supabase so quote lookup returns a ready row."""
    mock_sb = MagicMock()

    # Build the chained call: sb.table(...).select(...).eq(...).eq(...).is_(...).execute()
    quote_exec = MagicMock()
    quote_exec.data = [_mk_quote_row(workflow_status=workflow_status)]

    quote_chain = MagicMock()
    quote_chain.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value = quote_exec

    # Update chain: sb.table("quote_items").update(...).eq(...).eq(...).execute()
    item_update_exec = MagicMock()
    item_update_exec.data = []
    item_chain = MagicMock()
    item_chain.update.return_value.eq.return_value.eq.return_value.execute.return_value = item_update_exec

    def table(name: str):
        if name == "quotes":
            return quote_chain
        return item_chain

    mock_sb.table.side_effect = table
    return mock_sb, item_chain


# ----------------------------------------------------------------------------
# Handler unit tests
# ----------------------------------------------------------------------------


class TestBulkUpdateItems:
    """PATCH /api/customs/{quote_id}/items/bulk handler behaviour."""

    def test_unauthenticated_returns_401(self):
        """No JWT + no session → 401 Not authenticated."""
        req = _make_request(api_user_id=None)
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 401
        assert _body(resp) == {
            "success": False,
            "error": "Not authenticated",
        }

    @patch("api.customs.get_user_role_codes")
    def test_missing_role_returns_403(self, mock_roles):
        """Authenticated but without customs/admin role → 403 Unauthorized."""
        mock_roles.return_value = ["sales"]
        req = _make_request(
            api_user_id="user-1",
            user_metadata={"org_id": "o-1"},
            body={"items": [{"id": "i-1"}]},
        )
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 403
        assert _body(resp) == {"success": False, "error": "Unauthorized"}

    @patch("api.customs.get_user_role_codes")
    def test_invalid_json_returns_400(self, mock_roles):
        """JSON parse error → 400 Invalid JSON."""
        mock_roles.return_value = ["customs"]
        req = _make_request(
            api_user_id="user-1",
            user_metadata={"org_id": "o-1"},
            raw_body_error=True,
        )
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 400
        assert _body(resp) == {"success": False, "error": "Invalid JSON"}

    @patch("api.customs.get_user_role_codes")
    def test_empty_items_returns_success_noop(self, mock_roles):
        """Empty items list → 200 success without DB writes."""
        mock_roles.return_value = ["customs"]
        req = _make_request(
            api_user_id="user-1",
            user_metadata={"org_id": "o-1"},
            body={"items": []},
        )
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 200
        assert _body(resp) == {"success": True}

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_quote_not_found_returns_404(self, mock_roles, mock_get_sb):
        """Quote missing / not in org → 404 Quote not found."""
        mock_roles.return_value = ["customs"]
        mock_sb = MagicMock()
        quote_exec = MagicMock()
        quote_exec.data = []  # Empty — quote not in org
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value = quote_exec
        mock_get_sb.return_value = mock_sb

        req = _make_request(
            api_user_id="user-1",
            user_metadata={"org_id": "o-1"},
            body={"items": [{"id": "i-1"}]},
        )
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 404
        assert _body(resp) == {"success": False, "error": "Quote not found"}

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_quote_wrong_status_returns_400(self, mock_roles, mock_get_sb):
        """Quote not in ready_statuses → 400 waiting for procurement."""
        mock_roles.return_value = ["customs"]
        mock_sb, _ = _patch_supabase_quote_ok(workflow_status="draft")
        mock_get_sb.return_value = mock_sb

        req = _make_request(
            api_user_id="user-1",
            user_metadata={"org_id": "o-1"},
            body={"items": [{"id": "i-1"}]},
        )
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 400
        assert _body(resp)["success"] is False
        assert "waiting for procurement" in _body(resp)["error"]

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_happy_path_updates_items(self, mock_roles, mock_get_sb):
        """Valid body + customs role → updates quote_items + returns success."""
        mock_roles.return_value = ["customs"]
        mock_sb, item_chain = _patch_supabase_quote_ok()
        mock_get_sb.return_value = mock_sb

        req = _make_request(
            api_user_id="user-1",
            user_metadata={"org_id": "o-1"},
            body={
                "items": [
                    {
                        "id": "i-1",
                        "hs_code": "1234.56",
                        "customs_duty": "5.5",
                        "license_ds_required": True,
                        "license_ds_cost": "5000",
                        "license_ss_required": False,
                        "license_ss_cost": 0,
                        "license_sgr_required": False,
                        "license_sgr_cost": "",
                    }
                ]
            },
        )
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 200
        assert _body(resp) == {"success": True}

        # Verify update called with expected payload
        update_call = item_chain.update.call_args
        assert update_call is not None
        payload = update_call[0][0]
        assert payload["hs_code"] == "1234.56"
        assert payload["customs_duty"] == 5.5
        assert payload["license_ds_required"] is True
        assert payload["license_ds_cost"] == 5000.0
        assert payload["license_sgr_cost"] == 0.0  # empty string → 0

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_item_without_id_is_skipped(self, mock_roles, mock_get_sb):
        """Items missing ``id`` → skipped, no update call for them."""
        mock_roles.return_value = ["customs"]
        mock_sb, item_chain = _patch_supabase_quote_ok()
        mock_get_sb.return_value = mock_sb

        req = _make_request(
            api_user_id="user-1",
            user_metadata={"org_id": "o-1"},
            body={"items": [{"hs_code": "x"}]},  # no id
        )
        resp = _run(bulk_update_items(req, "q-1"))
        assert resp.status_code == 200
        assert _body(resp) == {"success": True}
        # Update should not have been called — all items skipped
        assert item_chain.update.call_count == 0


# ----------------------------------------------------------------------------
# Route registration (sub-app)
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_sub_app)


class TestCustomsRoutesRegistered:
    """Assert /customs/{quote_id}/items/bulk is wired on the FastAPI sub-app."""

    def test_patch_bulk_registered(self, subapp_client: TestClient) -> None:
        """PATCH /customs/{quote_id}/items/bulk must exist (not 404)."""
        response = subapp_client.patch(
            "/customs/q-1/items/bulk", json={"items": []}
        )
        # No auth attached → 401. 404 means route not registered.
        assert response.status_code != 404, (
            f"Route not registered: PATCH /customs/.../items/bulk returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_openapi_schema_includes_customs_bulk(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/customs/{quote_id}/items/bulk" in paths
        assert "patch" in paths["/customs/{quote_id}/items/bulk"]
