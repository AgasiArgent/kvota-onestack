"""Tests for api/quotes.py action handlers — Phase 6B-6b extraction.

Covers the three quote-action handlers extracted from main.py in 6B-6b:
- ``submit_procurement`` — POST /api/quotes/{quote_id}/submit-procurement
- ``cancel_quote`` — POST /api/quotes/{quote_id}/cancel
- ``transition_workflow`` — POST /api/quotes/{quote_id}/workflow/transition

Each handler is tested for:
- Route registration (via the FastAPI sub-app, lives in
  ``test_api_routers_quotes.py``).
- Happy path: JWT-authed POST returns 200 + expected envelope shape.
- Error case: a representative validation / auth failure.

The Supabase client is mocked at ``api.quotes.get_supabase``. Workflow-
service functions are patched on ``api.quotes`` so each handler runs as a
pure unit (no DB, no workflow transition side effects).
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.quotes import cancel_quote, submit_procurement, transition_workflow  # noqa: E402


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def _make_request(
    api_user_id: str | None = "user-1",
    body: dict | None = None,
    raw_body: bytes | None = None,
    email: str = "u@x.com",
    user_metadata: dict | None = None,
    content_type: str = "application/json",
):
    """Build a minimal Starlette-style request with JWT user + body."""
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
    req.headers = {"content-type": content_type}

    async def _json():
        return body or {}

    async def _form():
        return body or {}

    async def _body_bytes():
        if raw_body is not None:
            return raw_body
        if body is not None:
            return json.dumps(body).encode()
        return b""

    req.json = _json
    req.form = _form
    req.body = _body_bytes
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
# submit_procurement
# ----------------------------------------------------------------------------


class TestSubmitProcurement:
    """POST /api/quotes/{quote_id}/submit-procurement."""

    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_no_auth_returns_401(self, mock_get_sb, mock_roles):
        """No JWT + no session → 401."""
        req = _make_request(api_user_id=None)
        resp = _run(submit_procurement(req, "q-1"))
        assert resp.status_code == 401
        assert _body(resp) == {"error": "Unauthorized"}

    @patch("api.quotes.transition_to_pending_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_happy_path_transitions_and_returns_redirect(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """JWT + valid checklist → quotes update + transition + redirect JSON."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"organization_id": "org-1"}
        ]
        sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_get_sb.return_value = sb
        mock_roles.return_value = ["sales"]
        mock_transition.return_value = SimpleNamespace(
            success=True, error_message=None
        )

        req = _make_request(
            api_user_id="u-1",
            body={
                "checklist": {
                    "is_estimate": True,
                    "is_tender": False,
                    "direct_request": True,
                    "trading_org_request": False,
                    "equipment_description": "Насос A, 3 шт.",
                }
            },
            user_metadata={"org_id": "org-1"},
        )
        resp = _run(submit_procurement(req, "q-1"))

        assert resp.status_code == 200, _body(resp)
        assert _body(resp) == {"redirect": "/quotes/q-1"}
        mock_transition.assert_called_once()

    @patch("api.quotes.transition_to_pending_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_missing_equipment_description_returns_400(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """Checklist present but equipment_description empty → 400."""
        sb = MagicMock()
        mock_get_sb.return_value = sb
        mock_roles.return_value = ["sales"]

        req = _make_request(
            api_user_id="u-1",
            body={
                "checklist": {
                    "is_estimate": False,
                    "equipment_description": "   ",  # whitespace only
                }
            },
            user_metadata={"org_id": "org-1"},
        )
        resp = _run(submit_procurement(req, "q-1"))

        assert resp.status_code == 400
        assert "контрольный список" in _body(resp)["error"]
        mock_transition.assert_not_called()


# ----------------------------------------------------------------------------
# cancel_quote
# ----------------------------------------------------------------------------


def _mock_supabase_for_cancel(
    *,
    org_id: str | None = "org-1",
    quote: dict | None = None,
):
    """Build a chainable Supabase mock for the cancel_quote handler."""
    sb = MagicMock()

    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "organization_members":
            data = [{"organization_id": org_id}] if org_id else []
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = data
        elif name == "quotes":
            data = [quote] if quote else []
            tbl.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = data
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock()
        return tbl

    sb.table.side_effect = table_side_effect
    return sb


class TestCancelQuote:
    """POST /api/quotes/{quote_id}/cancel."""

    def test_no_auth_returns_401(self):
        """No JWT + no session → 401."""
        req = _make_request(api_user_id=None)
        resp = _run(cancel_quote(req, "q-1"))
        assert resp.status_code == 401
        assert _body(resp) == {"error": "Unauthorized"}

    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_missing_reason_returns_400(self, mock_get_sb, mock_roles):
        """Empty reason → 400 (mandatory)."""
        mock_get_sb.return_value = _mock_supabase_for_cancel(
            quote={"id": "q-1", "workflow_status": "pending_procurement"}
        )
        mock_roles.return_value = ["sales"]

        req = _make_request(api_user_id="u-1", body={"reason": "   "})
        resp = _run(cancel_quote(req, "q-1"))

        assert resp.status_code == 400
        assert _body(resp) == {"error": "Причина отмены обязательна"}

    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_non_sales_role_returns_403(self, mock_get_sb, mock_roles):
        """Role not in {sales, head_of_sales, admin} → 403."""
        mock_get_sb.return_value = _mock_supabase_for_cancel()
        mock_roles.return_value = ["procurement"]

        req = _make_request(
            api_user_id="u-1", body={"reason": "Client cancelled"}
        )
        resp = _run(cancel_quote(req, "q-1"))

        assert resp.status_code == 403
        assert "прав для отмены" in _body(resp)["error"]

    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_happy_path_cancels_and_returns_success(
        self, mock_get_sb, mock_roles
    ):
        """Valid role + reason + pending_procurement quote → {success: True}."""
        quote = {
            "id": "q-1",
            "workflow_status": "draft",
            "idn_quote": "Q-202601-0001",
            "customer_id": None,
        }
        mock_get_sb.return_value = _mock_supabase_for_cancel(quote=quote)
        mock_roles.return_value = ["sales"]

        req = _make_request(
            api_user_id="u-1", body={"reason": "Client withdrew request"}
        )
        resp = _run(cancel_quote(req, "q-1"))

        assert resp.status_code == 200, _body(resp)
        assert _body(resp) == {"success": True}


# ----------------------------------------------------------------------------
# transition_workflow
# ----------------------------------------------------------------------------


def _mock_supabase_for_workflow(*, org_id: str | None = "org-1"):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
        [{"organization_id": org_id}] if org_id else []
    )
    return sb


class TestTransitionWorkflow:
    """POST /api/quotes/{quote_id}/workflow/transition."""

    def test_no_auth_returns_401(self):
        """No JWT + no session → 401."""
        req = _make_request(api_user_id=None)
        resp = _run(transition_workflow(req, "q-1"))
        assert resp.status_code == 401
        assert _body(resp) == {"error": "Unauthorized"}

    @patch("api.quotes.transition_quote_status")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_missing_params_returns_400(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """Neither to_status nor action set → 400."""
        mock_get_sb.return_value = _mock_supabase_for_workflow()
        mock_roles.return_value = ["sales"]

        req = _make_request(api_user_id="u-1", body={})
        resp = _run(transition_workflow(req, "q-1"))

        assert resp.status_code == 400
        assert (
            _body(resp)["error"] == "to_status or action is required"
        )
        mock_transition.assert_not_called()

    @patch("api.quotes.transition_quote_status")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_happy_path_returns_transition_envelope(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """Valid to_status → {success, from_status, to_status} envelope."""
        mock_get_sb.return_value = _mock_supabase_for_workflow()
        mock_roles.return_value = ["sales"]
        mock_transition.return_value = SimpleNamespace(
            success=True,
            from_status="draft",
            to_status="pending_sales_review",
            error_message=None,
        )

        req = _make_request(
            api_user_id="u-1",
            body={
                "to_status": "pending_sales_review",
                "comment": "Ready for review",
            },
        )
        resp = _run(transition_workflow(req, "q-1"))

        assert resp.status_code == 200, _body(resp)
        assert _body(resp) == {
            "success": True,
            "from_status": "draft",
            "to_status": "pending_sales_review",
        }
        mock_transition.assert_called_once_with(
            quote_id="q-1",
            to_status="pending_sales_review",
            actor_id="u-1",
            actor_roles=["sales"],
            comment="Ready for review",
        )

    @patch("api.quotes.complete_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_complete_procurement_action_dispatches_to_dedicated_fn(
        self, mock_get_sb, mock_roles, mock_complete_proc
    ):
        """``action=complete_procurement`` routes to complete_procurement()."""
        mock_get_sb.return_value = _mock_supabase_for_workflow()
        mock_roles.return_value = ["procurement"]
        mock_complete_proc.return_value = SimpleNamespace(
            success=True,
            from_status="pending_procurement",
            to_status="pending_logistics_and_customs",
            error_message=None,
        )

        req = _make_request(
            api_user_id="u-1", body={"action": "complete_procurement"}
        )
        resp = _run(transition_workflow(req, "q-1"))

        assert resp.status_code == 200, _body(resp)
        mock_complete_proc.assert_called_once()
