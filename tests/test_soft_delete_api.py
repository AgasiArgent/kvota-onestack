"""
Tests for api/soft_delete.py — admin-only soft-delete / restore endpoints.

Covers (per REQ-004):
- 401 without auth
- 403 for any non-admin authenticated role
- 404 for non-existent quote
- 200 + counts for admin happy path (new delete, new restore)
- 200 + zero counts for idempotent re-calls (already-deleted / never-deleted)

The rpc is mocked at `api.soft_delete.get_supabase` so these tests are
pure unit tests (no DB dependency, no network).
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.soft_delete import restore_quote, soft_delete_quote  # noqa: E402


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_request(api_user_id: str | None = "user-1"):
    """Build a minimal Starlette-style request with request.state.api_user."""
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(api_user=SimpleNamespace(id=api_user_id))
    return req


def _mock_supabase(
    role_slugs: list[str],
    quote_exists: bool,
    rpc_counts: tuple[int, int, int] = (0, 0, 0),
    org_id: str = "org-1",
):
    """Build a chainable Supabase mock covering the three touchpoints:

    1) organization_members lookup  → returns [{organization_id: org_id}]
    2) user_roles lookup            → returns [{roles: {slug: s}} for s in role_slugs]
    3) quotes existence probe       → returns [{id: ...}] if quote_exists else []
    4) rpc("soft_delete_quote" | "restore_quote") → returns a row with counts
    """
    sb = MagicMock()

    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "organization_members":
            tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"organization_id": org_id}
            ]
        elif name == "user_roles":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {"roles": {"slug": s}} for s in role_slugs
            ]
        elif name == "quotes":
            data = [{"id": "q-1"}] if quote_exists else []
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = data
        return tbl

    sb.table.side_effect = table_side_effect

    # RPC mock — a single row with the three count columns.
    quote_aff, spec_aff, deal_aff = rpc_counts
    rpc_resp = MagicMock()
    rpc_resp.data = [{
        "quote_affected": quote_aff,
        "spec_affected": spec_aff,
        "deal_affected": deal_aff,
    }]
    sb.rpc.return_value.execute.return_value = rpc_resp

    return sb


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
# POST /api/quotes/{id}/soft-delete
# ----------------------------------------------------------------------------


class TestSoftDelete:
    @patch("api.soft_delete.get_supabase")
    def test_soft_delete_no_auth_returns_401(self, mock_get_sb):
        req = _make_request(api_user_id=None)
        resp = _run(soft_delete_quote(req, "q-1"))
        assert resp.status_code == 401
        assert _body(resp)["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.parametrize(
        "role",
        ["sales", "head_of_sales", "top_manager", "procurement", "logistics"],
    )
    @patch("api.soft_delete.get_supabase")
    def test_soft_delete_non_admin_returns_403(self, mock_get_sb, role):
        """Any non-admin role is rejected — admin-only is intentional."""
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=[role], quote_exists=True
        )
        req = _make_request()
        resp = _run(soft_delete_quote(req, "q-1"))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"

    @patch("api.soft_delete.get_supabase")
    def test_soft_delete_missing_quote_returns_404(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["admin"], quote_exists=False
        )
        req = _make_request()
        resp = _run(soft_delete_quote(req, "q-missing"))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"

    @patch("api.soft_delete.get_supabase")
    def test_soft_delete_admin_happy_path_returns_counts(self, mock_get_sb):
        sb = _mock_supabase(
            role_slugs=["admin"], quote_exists=True, rpc_counts=(1, 1, 1)
        )
        mock_get_sb.return_value = sb
        req = _make_request(api_user_id="actor-42")

        resp = _run(soft_delete_quote(req, "q-1"))

        assert resp.status_code == 200
        payload = _body(resp)
        assert payload["success"] is True
        assert payload["data"] == {
            "quote_affected": 1,
            "spec_affected": 1,
            "deal_affected": 1,
        }
        # Verify rpc invoked with the authenticated actor id.
        sb.rpc.assert_called_once_with(
            "soft_delete_quote",
            {"p_quote_id": "q-1", "p_actor_id": "actor-42"},
        )

    @patch("api.soft_delete.get_supabase")
    def test_soft_delete_already_deleted_returns_zero_counts(self, mock_get_sb):
        """Idempotency: quote exists (row in table) but all counts are zero."""
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["admin"], quote_exists=True, rpc_counts=(0, 0, 0)
        )
        req = _make_request()

        resp = _run(soft_delete_quote(req, "q-1"))

        assert resp.status_code == 200
        payload = _body(resp)
        assert payload["success"] is True
        assert payload["data"] == {
            "quote_affected": 0,
            "spec_affected": 0,
            "deal_affected": 0,
        }


# ----------------------------------------------------------------------------
# POST /api/quotes/{id}/restore
# ----------------------------------------------------------------------------


class TestRestore:
    @patch("api.soft_delete.get_supabase")
    def test_restore_no_auth_returns_401(self, mock_get_sb):
        req = _make_request(api_user_id=None)
        resp = _run(restore_quote(req, "q-1"))
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "role",
        ["sales", "head_of_sales", "top_manager", "procurement", "logistics"],
    )
    @patch("api.soft_delete.get_supabase")
    def test_restore_non_admin_returns_403(self, mock_get_sb, role):
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=[role], quote_exists=True
        )
        req = _make_request()
        resp = _run(restore_quote(req, "q-1"))
        assert resp.status_code == 403

    @patch("api.soft_delete.get_supabase")
    def test_restore_missing_quote_returns_404(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["admin"], quote_exists=False
        )
        req = _make_request()
        resp = _run(restore_quote(req, "q-ghost"))
        assert resp.status_code == 404

    @patch("api.soft_delete.get_supabase")
    def test_restore_happy_path(self, mock_get_sb):
        sb = _mock_supabase(
            role_slugs=["admin"], quote_exists=True, rpc_counts=(1, 1, 1)
        )
        mock_get_sb.return_value = sb
        req = _make_request()

        resp = _run(restore_quote(req, "q-1"))

        assert resp.status_code == 200
        payload = _body(resp)
        assert payload["success"] is True
        assert payload["data"] == {
            "quote_affected": 1,
            "spec_affected": 1,
            "deal_affected": 1,
        }
        # restore_quote signature has only p_quote_id — no actor param.
        sb.rpc.assert_called_once_with(
            "restore_quote",
            {"p_quote_id": "q-1"},
        )

    @patch("api.soft_delete.get_supabase")
    def test_restore_never_deleted_returns_zero_counts(self, mock_get_sb):
        """Idempotency: restoring a live quote is a no-op, not an error."""
        mock_get_sb.return_value = _mock_supabase(
            role_slugs=["admin"], quote_exists=True, rpc_counts=(0, 0, 0)
        )
        req = _make_request()

        resp = _run(restore_quote(req, "q-1"))

        assert resp.status_code == 200
        payload = _body(resp)
        assert payload["success"] is True
        assert payload["data"] == {
            "quote_affected": 0,
            "spec_affected": 0,
            "deal_affected": 0,
        }
