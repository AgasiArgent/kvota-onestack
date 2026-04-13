"""
Tests for api/procurement.py — Phase 4c Kanban + sub-status endpoints.

Covers:
- GET  /api/quotes/kanban                 — grouping, days_in_state, auth, role gate, status validation
- POST /api/quotes/{id}/substatus          — happy path, validation errors, auth, role gate
- GET  /api/quotes/{id}/status-history     — ordered list, actor name enrichment, empty case, auth
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.procurement import get_kanban, get_status_history, post_substatus  # noqa: E402


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_request(
    query: dict | None = None,
    body: dict | None = None,
    api_user_id: str | None = "user-1",
):
    """Build a minimal Starlette-style request mock."""
    req = MagicMock()
    req.state = SimpleNamespace(api_user=SimpleNamespace(id=api_user_id) if api_user_id else None)
    req.query_params = query or {}

    async def _json():
        if body is None:
            raise ValueError("no body")
        return body

    req.json = _json
    return req


def _mock_supabase_with_user(role_slugs: list[str], org_id: str = "org-1"):
    """Return a MagicMock supabase client that answers the auth lookups.

    organization_members → [{"organization_id": org_id}]
    user_roles           → one row per role slug
    Any further .table() calls should be chained by the caller via .configure_mock.
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
        return tbl

    sb.table.side_effect = table_side_effect
    return sb


def _run(coro):
    """Run a coroutine from a sync test in a fresh event loop."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ----------------------------------------------------------------------------
# GET /api/quotes/kanban
# ----------------------------------------------------------------------------


class TestGetKanban:
    @patch("api.procurement.get_supabase")
    def test_requires_authentication(self, mock_get_sb):
        req = _make_request(query={"status": "pending_procurement"}, api_user_id=None)
        resp = _run(get_kanban(req))
        assert resp.status_code == 401

    @patch("api.procurement.get_supabase")
    def test_rejects_sales_role(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["sales"])
        req = _make_request(query={"status": "pending_procurement"})
        resp = _run(get_kanban(req))
        assert resp.status_code == 403

    @patch("api.procurement.get_supabase")
    def test_rejects_invalid_status(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(query={"status": "draft"})
        resp = _run(get_kanban(req))
        assert resp.status_code == 400
        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "INVALID_STATUS"

    @patch("api.procurement.get_supabase")
    def test_happy_path_groups_quotes_by_substatus(self, mock_get_sb):
        # Separate mock: same side_effect handler across all calls
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

        quote_rows = [
            {
                "id": "q1",
                "idn": "Q-202604-0001",
                "procurement_substatus": "distributing",
                "updated_at": three_days_ago,
                "assigned_procurement_users": ["u1"],
                "customers": {"name": "Acme"},
            },
            {
                "id": "q2",
                "idn": "Q-202604-0002",
                "procurement_substatus": "waiting_prices",
                "updated_at": three_days_ago,
                "assigned_procurement_users": [],
                "customers": {"name": "Beta"},
            },
        ]
        history_rows = [
            {
                "quote_id": "q1",
                "to_substatus": "distributing",
                "transitioned_at": three_days_ago,
                "reason": "",
            },
            {
                "quote_id": "q2",
                "to_substatus": "waiting_prices",
                "transitioned_at": three_days_ago,
                "reason": "price delayed",
            },
        ]

        sb = MagicMock()

        def table_side_effect(name: str):
            tbl = MagicMock()
            if name == "organization_members":
                tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"organization_id": "org-1"}
                ]
            elif name == "user_roles":
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                    {"roles": {"slug": "procurement"}}
                ]
            elif name == "quotes":
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = quote_rows
            elif name == "status_history":
                tbl.select.return_value.in_.return_value.order.return_value.execute.return_value.data = history_rows
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb

        req = _make_request(query={"status": "pending_procurement"})
        resp = _run(get_kanban(req))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["success"] is True
        cols = payload["data"]["columns"]
        assert set(cols.keys()) == {
            "distributing",
            "searching_supplier",
            "waiting_prices",
            "prices_ready",
        }
        assert len(cols["distributing"]) == 1
        assert cols["distributing"][0]["id"] == "q1"
        assert cols["distributing"][0]["customer_name"] == "Acme"
        assert cols["distributing"][0]["days_in_state"] == 3
        assert cols["distributing"][0]["assignees"] == ["u1"]
        assert len(cols["waiting_prices"]) == 1
        assert cols["waiting_prices"][0]["latest_reason"] == "price delayed"
        assert cols["searching_supplier"] == []
        assert cols["prices_ready"] == []


# ----------------------------------------------------------------------------
# POST /api/quotes/{id}/substatus
# ----------------------------------------------------------------------------


class TestPostSubstatus:
    @patch("api.procurement.get_supabase")
    def test_requires_authentication(self, mock_get_sb):
        req = _make_request(body={"to_substatus": "searching_supplier"}, api_user_id=None)
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 401

    @patch("api.procurement.get_supabase")
    def test_rejects_sales_role(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["sales"])
        req = _make_request(body={"to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 403

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_happy_path_forward_transition(self, mock_get_sb, mock_transition):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.return_value = {"id": "q1", "procurement_substatus": "searching_supplier"}
        req = _make_request(body={"to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["success"] is True
        assert payload["data"]["procurement_substatus"] == "searching_supplier"
        mock_transition.assert_called_once()

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_reason_required_error(self, mock_get_sb, mock_transition):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.side_effect = ValueError("Reason required for backward transitions")
        req = _make_request(body={"to_substatus": "distributing"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 400

        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "REASON_REQUIRED"

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_invalid_transition_error(self, mock_get_sb, mock_transition):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.side_effect = ValueError(
            "Invalid substatus transition: pending_procurement/distributing → prices_ready"
        )
        req = _make_request(body={"to_substatus": "prices_ready"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 400

        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "INVALID_TRANSITION"

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_quote_not_found_error(self, mock_get_sb, mock_transition):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.side_effect = ValueError("Quote q-missing not found")
        req = _make_request(body={"to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q-missing"))
        assert resp.status_code == 404

        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "QUOTE_NOT_FOUND"

    @patch("api.procurement.get_supabase")
    def test_missing_to_substatus_is_validation_error(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 400

        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "VALIDATION_ERROR"


# ----------------------------------------------------------------------------
# GET /api/quotes/{id}/status-history
# ----------------------------------------------------------------------------


class TestGetStatusHistory:
    @patch("api.procurement.get_supabase")
    def test_requires_authentication(self, mock_get_sb):
        req = _make_request(api_user_id=None)
        resp = _run(get_status_history(req, "q1"))
        assert resp.status_code == 401

    @patch("api.procurement.get_supabase")
    def test_returns_ordered_list_with_actor_name(self, mock_get_sb):
        history_rows = [
            {
                "id": "h2",
                "from_status": "pending_procurement",
                "from_substatus": "searching_supplier",
                "to_status": "pending_procurement",
                "to_substatus": "waiting_prices",
                "transitioned_at": "2026-04-12T10:00:00+00:00",
                "transitioned_by": "user-1",
                "reason": "",
            },
            {
                "id": "h1",
                "from_status": "pending_procurement",
                "from_substatus": "distributing",
                "to_status": "pending_procurement",
                "to_substatus": "searching_supplier",
                "transitioned_at": "2026-04-11T09:00:00+00:00",
                "transitioned_by": "user-1",
                "reason": "",
            },
        ]

        sb = MagicMock()

        def table_side_effect(name: str):
            tbl = MagicMock()
            if name == "organization_members":
                tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"organization_id": "org-1"}
                ]
            elif name == "user_roles":
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                    {"roles": {"slug": "procurement"}}
                ]
            elif name == "status_history":
                tbl.select.return_value.eq.return_value.order.return_value.execute.return_value.data = history_rows
            elif name == "user_profiles":
                tbl.select.return_value.in_.return_value.execute.return_value.data = [
                    {"user_id": "user-1", "full_name": "Иван Иванов"}
                ]
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb

        req = _make_request()
        resp = _run(get_status_history(req, "q1"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["success"] is True
        assert len(payload["data"]) == 2
        assert payload["data"][0]["id"] == "h2"
        assert payload["data"][0]["transitioned_by_name"] == "Иван Иванов"

    @patch("api.procurement.get_supabase")
    def test_empty_history(self, mock_get_sb):
        sb = MagicMock()

        def table_side_effect(name: str):
            tbl = MagicMock()
            if name == "organization_members":
                tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"organization_id": "org-1"}
                ]
            elif name == "user_roles":
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                    {"roles": {"slug": "procurement"}}
                ]
            elif name == "status_history":
                tbl.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb

        req = _make_request()
        resp = _run(get_status_history(req, "q-empty"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["data"] == []
