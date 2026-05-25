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
    def test_regular_procurement_with_assignments_sees_only_own_brand_cards(self, mock_get_sb):
        """Regular МОЗ scope: caller sees only brand-slices they own AND past distribution.

        Mix of cards covering all filter dimensions:
        - q1/Siemens (searching_supplier, item assigned to caller)   → visible
        - q1/ABB    (searching_supplier, item assigned to other)     → filtered out (not owned)
        - q2/''     (waiting_prices, no assignee)                    → filtered out (not owned)
        - q3/Siemens (distributing, item assigned to caller)         → filtered out (distributing column hidden from МОЗ)

        Verifies the visible card retains the full payload (manager_name, МОЗ
        names, invoice totals from invoice_items) so we don't regress shape.
        """
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

        qbs_rows = [
            {
                "quote_id": "q1",
                "brand": "Siemens",
                "substatus": "searching_supplier",
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
                "substatus": "searching_supplier",
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
            {
                "quote_id": "q3",
                "brand": "Siemens",
                "substatus": "distributing",
                "updated_at": three_days_ago,
                "quotes": {
                    "id": "q3",
                    "idn_quote": "Q-202604-0003",
                    "workflow_status": "pending_procurement",
                    "organization_id": "org-1",
                    "created_by": "creator-1",
                    "customers": {"name": "Gamma"},
                },
            },
        ]
        history_rows = [
            {
                "quote_id": "q1",
                "brand": "Siemens",
                "to_substatus": "searching_supplier",
                "transitioned_at": three_days_ago,
                "reason": "",
            },
            {
                "quote_id": "q1",
                "brand": "ABB",
                "to_substatus": "searching_supplier",
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
            {
                "quote_id": "q3",
                "brand": "Siemens",
                "to_substatus": "distributing",
                "transitioned_at": three_days_ago,
                "reason": "",
            },
        ]
        # q1/Siemens assigned to caller (user-1); q1/ABB assigned to u2;
        # q2 unassigned; q3/Siemens assigned to caller but in distributing.
        quote_items_rows = [
            {"id": "item-1", "quote_id": "q1", "brand": "Siemens", "quantity": 2, "assigned_procurement_user": "user-1"},
            {"id": "item-2", "quote_id": "q1", "brand": "ABB", "quantity": 5, "assigned_procurement_user": "u2"},
            {"id": "item-3", "quote_id": "q2", "brand": None, "quantity": 1, "assigned_procurement_user": None},
            {"id": "item-4", "quote_id": "q3", "brand": "Siemens", "quantity": 4, "assigned_procurement_user": "user-1"},
        ]
        invoices_rows = [
            {
                "id": "inv-1",
                "quote_id": "q1",
                "invoice_number": "INV-01-Q-202604-0001",
                "currency": "USD",
            },
        ]
        # invoice_items rows — Phase 5d: kanban aggregate now reads invoice_items
        # directly. Brand and quantity live on invoice_items, not quote_items.
        invoice_items_rows = [
            # (q1 via inv-1, Siemens): 100 × 2 = 200
            {
                "invoice_id": "inv-1",
                "brand": "Siemens",
                "quantity": 2,
                "purchase_price_original": 100.0,
                "purchase_currency": "USD",
            },
            # (q1 via inv-1, ABB): 50 × 5 = 250 — present in source data, but
            # the ABB card is scope-filtered out so its sum should not appear.
            {
                "invoice_id": "inv-1",
                "brand": "ABB",
                "quantity": 5,
                "purchase_price_original": 50.0,
                "purchase_currency": "USD",
            },
        ]
        user_profiles_rows = [
            {"user_id": "creator-1", "full_name": "Алиса Петрова"},
            {"user_id": "user-1", "full_name": "Борис Сидоров"},
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
                tbl.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = qbs_rows
            elif name == "status_history":
                tbl.select.return_value.in_.return_value.order.return_value.execute.return_value.data = history_rows
            elif name == "quote_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = quote_items_rows
            elif name == "invoices":
                tbl.select.return_value.in_.return_value.execute.return_value.data = invoices_rows
            elif name == "invoice_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = invoice_items_rows
            elif name == "user_profiles":
                tbl.select.return_value.in_.return_value.execute.return_value.data = user_profiles_rows
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb

        req = _make_request(query={"status": "pending_procurement"})
        resp = _run(get_kanban(req))
        assert resp.status_code == 200

        # Phase 5d Group 3 Task 9: kanban reads invoice_items, NOT legacy
        # invoice_item_prices. Pattern B — direct per-invoice read.
        table_names_queried = [c.args[0] for c in sb.table.call_args_list]
        assert "invoice_items" in table_names_queried
        assert "invoice_item_prices" not in table_names_queried

        import json

        payload = json.loads(resp.body)
        assert payload["success"] is True
        cols = payload["data"]["columns"]
        assert set(cols.keys()) == {
            "distributing",
            "searching_supplier",
            "waiting_prices",
            "prices_ready",
            "paused",
        }

        # МОЗ never sees the «Распределение» column.
        assert cols["distributing"] == []

        # Only q1/Siemens passes the scope filter.
        searching = cols["searching_supplier"]
        assert len(searching) == 1
        siemens_card = searching[0]
        assert siemens_card["quote_id"] == "q1"
        assert siemens_card["brand"] == "Siemens"
        assert siemens_card["idn_quote"] == "Q-202604-0001"
        assert siemens_card["customer_name"] == "Acme"
        assert siemens_card["procurement_substatus"] == "searching_supplier"
        assert siemens_card["days_in_state"] == 3
        assert siemens_card["manager_name"] == "Алиса Петрова"
        assert siemens_card["procurement_user_names"] == ["Борис Сидоров"]
        assert siemens_card["invoice_sums"] == [
            {"invoice_number": "INV-01-Q-202604-0001", "currency": "USD", "total": 200.0}
        ]

        # q2 (no assignment) and q1/ABB (other user's brand) are scoped out.
        assert cols["waiting_prices"] == []
        assert cols["prices_ready"] == []
        assert cols["paused"] == []

    @patch("api.procurement.get_supabase")
    def test_regular_procurement_with_no_assignment_sees_no_cards(self, mock_get_sb):
        """Regular МОЗ with zero owned items: every column returns empty.

        Items exist for the org's quotes but none are assigned to the caller,
        so the scope filter strips every card. Distribution cards are also
        suppressed regardless of ownership.
        """
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

        qbs_rows = [
            {
                "quote_id": "q1",
                "brand": "Siemens",
                "substatus": "searching_supplier",
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
        ]
        # All items assigned to other procurement users — caller user-1 owns nothing.
        quote_items_rows = [
            {"id": "item-1", "quote_id": "q1", "brand": "Siemens", "quantity": 2, "assigned_procurement_user": "u2"},
            {"id": "item-2", "quote_id": "q1", "brand": "ABB", "quantity": 5, "assigned_procurement_user": "u3"},
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
                tbl.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = qbs_rows
            elif name == "status_history":
                tbl.select.return_value.in_.return_value.order.return_value.execute.return_value.data = []
            elif name == "quote_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = quote_items_rows
            elif name == "invoices":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            elif name == "invoice_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            elif name == "user_profiles":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
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
        assert cols["distributing"] == []
        assert cols["searching_supplier"] == []
        assert cols["waiting_prices"] == []
        assert cols["prices_ready"] == []
        assert cols["paused"] == []

    @patch("api.procurement.get_supabase")
    def test_head_of_procurement_sees_org_wide_cards(self, mock_get_sb):
        """head_of_procurement bypasses the per-user assignment filter.

        Even with zero items assigned to the caller, every org card is
        visible — including the «Распределение» column that МОЗ never sees.
        """
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

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
                "substatus": "searching_supplier",
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
        ]
        # No items assigned to caller user-1; broader scope ignores ownership.
        quote_items_rows = [
            {"id": "item-1", "quote_id": "q1", "brand": "Siemens", "quantity": 2, "assigned_procurement_user": "u2"},
            {"id": "item-2", "quote_id": "q1", "brand": "ABB", "quantity": 5, "assigned_procurement_user": "u3"},
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
                    {"roles": {"slug": "head_of_procurement"}}
                ]
            elif name == "quote_brand_substates":
                tbl.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = qbs_rows
            elif name == "status_history":
                tbl.select.return_value.in_.return_value.order.return_value.execute.return_value.data = []
            elif name == "quote_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = quote_items_rows
            elif name == "invoices":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            elif name == "invoice_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            elif name == "user_profiles":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb

        req = _make_request(query={"status": "pending_procurement"})
        resp = _run(get_kanban(req))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        cols = payload["data"]["columns"]

        distributing = cols["distributing"]
        assert len(distributing) == 1
        assert distributing[0]["quote_id"] == "q1"
        assert distributing[0]["brand"] == "Siemens"

        searching = cols["searching_supplier"]
        assert len(searching) == 1
        assert searching[0]["brand"] == "ABB"

    @patch("api.procurement.get_supabase")
    def test_procurement_senior_sees_org_wide_cards(self, mock_get_sb):
        """procurement_senior also bypasses the per-user assignment filter.

        Mirrors `test_head_of_procurement_sees_org_wide_cards` for the
        third role in `_BROADER_SCOPE_ROLES`.
        """
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

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
        ]
        # Item assigned to a different user — senior sees it anyway.
        quote_items_rows = [
            {"id": "item-1", "quote_id": "q1", "brand": "Siemens", "quantity": 2, "assigned_procurement_user": "u2"},
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
                    {"roles": {"slug": "procurement_senior"}}
                ]
            elif name == "quote_brand_substates":
                tbl.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = qbs_rows
            elif name == "status_history":
                tbl.select.return_value.in_.return_value.order.return_value.execute.return_value.data = []
            elif name == "quote_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = quote_items_rows
            elif name == "invoices":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            elif name == "invoice_items":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            elif name == "user_profiles":
                tbl.select.return_value.in_.return_value.execute.return_value.data = []
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb

        req = _make_request(query={"status": "pending_procurement"})
        resp = _run(get_kanban(req))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        cols = payload["data"]["columns"]
        # Distributing card is visible — broader scope keeps it.
        assert len(cols["distributing"]) == 1
        assert cols["distributing"][0]["quote_id"] == "q1"


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
