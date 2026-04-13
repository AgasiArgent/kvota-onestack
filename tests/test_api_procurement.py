"""
Tests for api/procurement.py — Kanban at (quote, brand) grain + sub-status endpoints.

Covers:
- GET  /api/quotes/kanban                 — (quote, brand) cards, days_in_state, auth, role gate, status validation
- POST /api/quotes/{id}/substatus          — happy path, brand required, validation errors, auth, role gate
- GET  /api/quotes/{id}/status-history     — ordered list with brand field, actor name enrichment, empty case, auth
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
    def test_happy_path_groups_cards_by_substatus(self, mock_get_sb):
        """Two quotes, three cards: q1 has two brands (two cards), q2 has one unbranded card."""
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

        # qbs rows — one per (quote, brand). q1 has both Siemens (distributing)
        # and ABB (distributing); q2 has '' (waiting_prices).
        qbs_rows = [
            {
                "quote_id": "q1",
                "brand": "Siemens",
                "substatus": "distributing",
                "updated_at": three_days_ago,
                "quotes": {
                    "id": "q1",
                    "idn_quote": "Q-202604-0001",
                    "workflow_status": "pending_procurement",
                    "organization_id": "org-1",
                    "created_by": "creator-1",
                    "customers": {"name": "Acme"},
                },
            },
            {
                "quote_id": "q1",
                "brand": "ABB",
                "substatus": "distributing",
                "updated_at": three_days_ago,
                "quotes": {
                    "id": "q1",
                    "idn_quote": "Q-202604-0001",
                    "workflow_status": "pending_procurement",
                    "organization_id": "org-1",
                    "created_by": "creator-1",
                    "customers": {"name": "Acme"},
                },
            },
            {
                "quote_id": "q2",
                "brand": "",
                "substatus": "waiting_prices",
                "updated_at": three_days_ago,
                "quotes": {
                    "id": "q2",
                    "idn_quote": "Q-202604-0002",
                    "workflow_status": "pending_procurement",
                    "organization_id": "org-1",
                    "created_by": None,
                    "customers": {"name": "Beta"},
                },
            },
        ]
        history_rows = [
            {
                "quote_id": "q1",
                "brand": "Siemens",
                "to_substatus": "distributing",
                "transitioned_at": three_days_ago,
                "reason": "",
            },
            {
                "quote_id": "q1",
                "brand": "ABB",
                "to_substatus": "distributing",
                "transitioned_at": three_days_ago,
                "reason": "",
            },
            {
                "quote_id": "q2",
                "brand": "",
                "to_substatus": "waiting_prices",
                "transitioned_at": three_days_ago,
                "reason": "price delayed",
            },
        ]
        # Items: q1 has 1 Siemens item (qty 2, assigned u1) + 1 ABB item (qty 5, assigned u2);
        # q2 has 1 unbranded item (qty 1, no assignee).
        quote_items_rows = [
            {"id": "item-1", "quote_id": "q1", "brand": "Siemens", "quantity": 2, "assigned_procurement_user": "u1"},
            {"id": "item-2", "quote_id": "q1", "brand": "ABB", "quantity": 5, "assigned_procurement_user": "u2"},
            {"id": "item-3", "quote_id": "q2", "brand": None, "quantity": 1, "assigned_procurement_user": None},
        ]
        invoices_rows = [
            {
                "id": "inv-1",
                "quote_id": "q1",
                "invoice_number": "INV-01-Q-202604-0001",
                "currency": "USD",
            },
        ]
        invoice_item_prices_rows = [
            # item-1 is Siemens → this invoice line belongs to (q1, Siemens): 100 × 2 = 200
            {
                "invoice_id": "inv-1",
                "quote_item_id": "item-1",
                "purchase_price_original": 100.0,
                "purchase_currency": "USD",
            },
            # item-2 is ABB → this invoice line belongs to (q1, ABB): 50 × 5 = 250
            {
                "invoice_id": "inv-1",
                "quote_item_id": "item-2",
                "purchase_price_original": 50.0,
                "purchase_currency": "USD",
            },
        ]
        user_profiles_rows = [
            {"user_id": "creator-1", "full_name": "Алиса Петрова"},
            {"user_id": "u1", "full_name": "Борис Сидоров"},
            {"user_id": "u2", "full_name": "Виктор Орлов"},
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
            elif name == "quote_brand_substates":
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = qbs_rows
            elif name == "status_history":
                tbl.select.return_value.in_.return_value.order.return_value.execute.return_value.data = history_rows
            elif name == "quote_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = quote_items_rows
            elif name == "invoices":
                tbl.select.return_value.in_.return_value.execute.return_value.data = invoices_rows
            elif name == "invoice_item_prices":
                tbl.select.return_value.in_.return_value.execute.return_value.data = invoice_item_prices_rows
            elif name == "user_profiles":
                tbl.select.return_value.in_.return_value.execute.return_value.data = user_profiles_rows
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

        # q1 contributes TWO cards to distributing (one per brand).
        distributing_cards = cols["distributing"]
        assert len(distributing_cards) == 2

        by_brand = {c["brand"]: c for c in distributing_cards}
        assert set(by_brand.keys()) == {"Siemens", "ABB"}

        siemens_card = by_brand["Siemens"]
        assert siemens_card["quote_id"] == "q1"
        assert siemens_card["idn_quote"] == "Q-202604-0001"
        assert siemens_card["customer_name"] == "Acme"
        assert siemens_card["procurement_substatus"] == "distributing"
        assert siemens_card["days_in_state"] == 3
        assert siemens_card["manager_name"] == "Алиса Петрова"
        assert siemens_card["procurement_user_names"] == ["Борис Сидоров"]
        assert siemens_card["invoice_sums"] == [
            {"invoice_number": "INV-01-Q-202604-0001", "currency": "USD", "total": 200.0}
        ]

        abb_card = by_brand["ABB"]
        assert abb_card["procurement_user_names"] == ["Виктор Орлов"]
        assert abb_card["invoice_sums"] == [
            {"invoice_number": "INV-01-Q-202604-0001", "currency": "USD", "total": 250.0}
        ]

        # q2 — unbranded card in waiting_prices.
        assert len(cols["waiting_prices"]) == 1
        q2_card = cols["waiting_prices"][0]
        assert q2_card["quote_id"] == "q2"
        assert q2_card["brand"] == ""
        assert q2_card["latest_reason"] == "price delayed"
        assert q2_card["manager_name"] is None
        assert q2_card["procurement_user_names"] == []
        assert q2_card["invoice_sums"] == []

        # Empty columns remain empty.
        assert cols["searching_supplier"] == []
        assert cols["prices_ready"] == []


# ----------------------------------------------------------------------------
# POST /api/quotes/{id}/substatus
# ----------------------------------------------------------------------------


class TestPostSubstatus:
    @patch("api.procurement.get_supabase")
    def test_requires_authentication(self, mock_get_sb):
        req = _make_request(
            body={"brand": "ABB", "to_substatus": "searching_supplier"},
            api_user_id=None,
        )
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 401

    @patch("api.procurement.get_supabase")
    def test_rejects_sales_role(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["sales"])
        req = _make_request(body={"brand": "ABB", "to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 403

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_happy_path_forward_transition(self, mock_get_sb, mock_transition):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.return_value = {
            "quote_id": "q1", "brand": "ABB", "substatus": "searching_supplier"
        }
        req = _make_request(body={"brand": "ABB", "to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["success"] is True
        assert payload["data"]["brand"] == "ABB"
        assert payload["data"]["procurement_substatus"] == "searching_supplier"
        # Transition called with brand kw.
        _, kwargs = mock_transition.call_args
        assert kwargs["brand"] == "ABB"

    @patch("api.procurement.get_supabase")
    def test_missing_brand_is_validation_error(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={"to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 400
        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "VALIDATION_ERROR"
        assert "brand" in payload["error"]["message"].lower()

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_empty_string_brand_is_accepted(self, mock_get_sb, mock_transition):
        """brand='' is valid (unbranded items)."""
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.return_value = {
            "quote_id": "q1", "brand": "", "substatus": "searching_supplier"
        }
        req = _make_request(body={"brand": "", "to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 200

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_reason_required_error(self, mock_get_sb, mock_transition):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.side_effect = ValueError("Reason required for backward transitions")
        req = _make_request(body={"brand": "ABB", "to_substatus": "distributing"})
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
        req = _make_request(body={"brand": "ABB", "to_substatus": "prices_ready"})
        resp = _run(post_substatus(req, "q1"))
        assert resp.status_code == 400

        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "INVALID_TRANSITION"

    @patch("api.procurement.transition_substatus")
    @patch("api.procurement.get_supabase")
    def test_quote_brand_not_found_error(self, mock_get_sb, mock_transition):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_transition.side_effect = ValueError("Quote/brand not found: q-missing/'ABB'")
        req = _make_request(body={"brand": "ABB", "to_substatus": "searching_supplier"})
        resp = _run(post_substatus(req, "q-missing"))
        assert resp.status_code == 404

        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "QUOTE_NOT_FOUND"

    @patch("api.procurement.get_supabase")
    def test_missing_to_substatus_is_validation_error(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={"brand": "ABB"})
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
    def test_returns_ordered_list_with_brand_and_actor(self, mock_get_sb):
        history_rows = [
            {
                "id": "h2",
                "brand": "ABB",
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
                "brand": None,  # quote-level historical row (pre-refactor)
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
        assert payload["data"][0]["brand"] == "ABB"
        assert payload["data"][0]["transitioned_by_name"] == "Иван Иванов"
        assert payload["data"][1]["brand"] is None  # pre-brand rows stay nullable

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
