"""
Tests for /api/quotes/{id}/pause, /unpause, and /pause-history endpoints
(Testing 2 row 74 — mandatory pause reason + activity log).

Covers:
- POST   /api/quotes/{id}/pause          — happy path, empty reason → 400,
                                            auth, role gate, validation errors
- POST   /api/quotes/{id}/unpause        — happy path, auth, role gate
- GET    /api/quotes/{id}/pause-history  — sorted list with actor enrichment,
                                            auth, role gate, empty case
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.procurement import (  # noqa: E402
    get_pause_history_endpoint,
    post_pause,
    post_unpause,
)


# ----------------------------------------------------------------------------
# Helpers (mirror tests/test_api_procurement.py)
# ----------------------------------------------------------------------------


def _make_request(
    body: dict | None = None,
    api_user_id: str | None = "user-1",
):
    req = MagicMock()
    req.state = SimpleNamespace(
        api_user=SimpleNamespace(id=api_user_id) if api_user_id else None
    )
    req.query_params = {}

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
# POST /api/quotes/{id}/pause
# ----------------------------------------------------------------------------


class TestPostPause:
    @patch("api.procurement.get_supabase")
    def test_requires_authentication(self, mock_get_sb):
        req = _make_request(
            body={"brand": "ABB", "reason": "supplier afk"},
            api_user_id=None,
        )
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 401

    @patch("api.procurement.get_supabase")
    def test_rejects_sales_role(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["sales"])
        req = _make_request(body={"brand": "ABB", "reason": "supplier afk"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 403

    @patch("api.procurement.pause_quote")
    @patch("api.procurement.get_supabase")
    def test_happy_path(self, mock_get_sb, mock_pause):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_pause.return_value = {
            "quote_id": "q1", "brand": "ABB", "substatus": "paused"
        }
        req = _make_request(body={"brand": "ABB", "reason": "supplier afk"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["success"] is True
        assert payload["data"]["procurement_substatus"] == "paused"
        # pause_quote called with the right kwargs.
        _, kwargs = mock_pause.call_args
        assert kwargs["brand"] == "ABB"
        assert kwargs["reason"] == "supplier afk"

    @patch("api.procurement.get_supabase")
    def test_empty_reason_is_400(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={"brand": "ABB", "reason": "   "})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 400
        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "REASON_REQUIRED"

    @patch("api.procurement.get_supabase")
    def test_missing_reason_is_400(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={"brand": "ABB"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 400
        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "REASON_REQUIRED"

    @patch("api.procurement.get_supabase")
    def test_missing_brand_is_validation_error(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={"reason": "stuck"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 400
        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "VALIDATION_ERROR"
        assert "brand" in payload["error"]["message"].lower()

    @patch("api.procurement.pause_quote")
    @patch("api.procurement.get_supabase")
    def test_unbranded_pause_accepted(self, mock_get_sb, mock_pause):
        """brand='' is valid (unbranded slice)."""
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_pause.return_value = {
            "quote_id": "q1", "brand": "", "substatus": "paused"
        }
        req = _make_request(body={"brand": "", "reason": "stuck"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 200

    @patch("api.procurement.pause_quote")
    @patch("api.procurement.get_supabase")
    def test_quote_not_found_maps_to_404(self, mock_get_sb, mock_pause):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_pause.side_effect = ValueError("Quote/brand not found: q-x/'ABB'")
        req = _make_request(body={"brand": "ABB", "reason": "stuck"})
        resp = _run(post_pause(req, "q-x"))
        assert resp.status_code == 404

    @patch("api.procurement.pause_quote")
    @patch("api.procurement.get_supabase")
    def test_invalid_transition_maps_to_400(self, mock_get_sb, mock_pause):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_pause.side_effect = ValueError(
            "Invalid substatus transition: pending_procurement/paused → paused for roles ['procurement']"
        )
        req = _make_request(body={"brand": "ABB", "reason": "stuck"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 400
        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "INVALID_TRANSITION"

    @patch("api.procurement.pause_quote")
    @patch("api.procurement.get_supabase")
    def test_admin_can_pause(self, mock_get_sb, mock_pause):
        mock_get_sb.return_value = _mock_supabase_with_user(["admin"])
        mock_pause.return_value = {
            "quote_id": "q1", "brand": "ABB", "substatus": "paused"
        }
        req = _make_request(body={"brand": "ABB", "reason": "stuck"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 200

    @patch("api.procurement.pause_quote")
    @patch("api.procurement.get_supabase")
    def test_procurement_senior_can_pause(self, mock_get_sb, mock_pause):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement_senior"])
        mock_pause.return_value = {
            "quote_id": "q1", "brand": "ABB", "substatus": "paused"
        }
        req = _make_request(body={"brand": "ABB", "reason": "stuck"})
        resp = _run(post_pause(req, "q1"))
        assert resp.status_code == 200


# ----------------------------------------------------------------------------
# POST /api/quotes/{id}/unpause
# ----------------------------------------------------------------------------


class TestPostUnpause:
    @patch("api.procurement.get_supabase")
    def test_requires_authentication(self, mock_get_sb):
        req = _make_request(
            body={"brand": "ABB"},
            api_user_id=None,
        )
        resp = _run(post_unpause(req, "q1"))
        assert resp.status_code == 401

    @patch("api.procurement.get_supabase")
    def test_rejects_sales_role(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["sales"])
        req = _make_request(body={"brand": "ABB"})
        resp = _run(post_unpause(req, "q1"))
        assert resp.status_code == 403

    @patch("api.procurement.unpause_quote")
    @patch("api.procurement.get_supabase")
    def test_happy_path_default_target(self, mock_get_sb, mock_unpause):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_unpause.return_value = {
            "quote_id": "q1", "brand": "ABB", "substatus": "searching_supplier"
        }
        req = _make_request(body={"brand": "ABB"})
        resp = _run(post_unpause(req, "q1"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["data"]["procurement_substatus"] == "searching_supplier"
        # Default target is searching_supplier when client omits to_substatus.
        _, kwargs = mock_unpause.call_args
        assert kwargs["to_substatus"] == "searching_supplier"

    @patch("api.procurement.unpause_quote")
    @patch("api.procurement.get_supabase")
    def test_happy_path_explicit_target(self, mock_get_sb, mock_unpause):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_unpause.return_value = {
            "quote_id": "q1", "brand": "ABB", "substatus": "waiting_prices"
        }
        req = _make_request(body={"brand": "ABB", "to_substatus": "waiting_prices"})
        resp = _run(post_unpause(req, "q1"))
        assert resp.status_code == 200
        _, kwargs = mock_unpause.call_args
        assert kwargs["to_substatus"] == "waiting_prices"

    @patch("api.procurement.get_supabase")
    def test_target_paused_rejected(self, mock_get_sb):
        """Cannot 'unpause' to 'paused' — that's a no-op masquerading as unpause."""
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={"brand": "ABB", "to_substatus": "paused"})
        resp = _run(post_unpause(req, "q1"))
        assert resp.status_code == 400

    @patch("api.procurement.get_supabase")
    def test_missing_brand_is_validation_error(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        req = _make_request(body={"to_substatus": "searching_supplier"})
        resp = _run(post_unpause(req, "q1"))
        assert resp.status_code == 400
        import json

        payload = json.loads(resp.body)
        assert payload["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.procurement.unpause_quote")
    @patch("api.procurement.get_supabase")
    def test_quote_not_found_maps_to_404(self, mock_get_sb, mock_unpause):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_unpause.side_effect = ValueError("Quote/brand not found: q-x/'ABB'")
        req = _make_request(body={"brand": "ABB"})
        resp = _run(post_unpause(req, "q-x"))
        assert resp.status_code == 404


# ----------------------------------------------------------------------------
# GET /api/quotes/{id}/pause-history
# ----------------------------------------------------------------------------


class TestGetPauseHistory:
    @patch("api.procurement.get_supabase")
    def test_requires_authentication(self, mock_get_sb):
        req = _make_request(api_user_id=None)
        resp = _run(get_pause_history_endpoint(req, "q1"))
        assert resp.status_code == 401

    @patch("api.procurement.get_supabase")
    def test_rejects_sales_role(self, mock_get_sb):
        mock_get_sb.return_value = _mock_supabase_with_user(["sales"])
        req = _make_request()
        resp = _run(get_pause_history_endpoint(req, "q1"))
        assert resp.status_code == 403

    @patch("api.procurement.get_pause_history")
    @patch("api.procurement.get_supabase")
    def test_empty_history(self, mock_get_sb, mock_history):
        mock_get_sb.return_value = _mock_supabase_with_user(["procurement"])
        mock_history.return_value = []
        req = _make_request()
        resp = _run(get_pause_history_endpoint(req, "q1"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        assert payload["data"] == []

    @patch("api.procurement.get_pause_history")
    @patch("api.procurement.get_supabase")
    def test_returns_enriched_rows_with_actor_names(self, mock_get_sb, mock_history):
        """Rows include paused_by_name + unpaused_by_name from user_profiles."""
        mock_history.return_value = [
            {
                "id": "log-1",
                "quote_id": "q1",
                "paused_at": "2026-05-25T10:00:00+00:00",
                "paused_by": "user-1",
                "reason": "supplier afk",
                "unpaused_at": "2026-05-25T18:00:00+00:00",
                "unpaused_by": "user-2",
            },
            {
                "id": "log-2",
                "quote_id": "q1",
                "paused_at": "2026-05-26T09:00:00+00:00",
                "paused_by": "user-2",
                "reason": "client review",
                "unpaused_at": None,
                "unpaused_by": None,
            },
        ]

        # Mock supabase with proper user_profiles return for enrichment.
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
            elif name == "user_profiles":
                tbl.select.return_value.in_.return_value.execute.return_value.data = [
                    {"user_id": "user-1", "full_name": "Алексей Иванов"},
                    {"user_id": "user-2", "full_name": "Мария Петрова"},
                ]
            return tbl

        sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = sb

        req = _make_request()
        resp = _run(get_pause_history_endpoint(req, "q1"))
        assert resp.status_code == 200

        import json

        payload = json.loads(resp.body)
        rows = payload["data"]
        assert len(rows) == 2
        # First row is closed (has unpaused_at).
        assert rows[0]["paused_by_name"] == "Алексей Иванов"
        assert rows[0]["unpaused_by_name"] == "Мария Петрова"
        assert rows[0]["reason"] == "supplier afk"
        # Second row is open.
        assert rows[1]["paused_by_name"] == "Мария Петрова"
        assert rows[1]["unpaused_by_name"] is None
        assert rows[1]["unpaused_at"] is None
