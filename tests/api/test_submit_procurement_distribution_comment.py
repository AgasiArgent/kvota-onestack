"""Tests for the optional «Комментарий для распределения» (`distribution_comment`)
field on ``POST /api/quotes/{quote_id}/submit-procurement``.

User feedback: МОП fills the existing "Контрольный список" modal when handing
a quote off to procurement. A free-text comment is needed for the
distribution stage (where МОЗ + МОЛ + МОТ get auto-assigned in
«Нераспределено»). The comment must persist into
``kvota.quotes.sales_checklist.distribution_comment`` (JSONB) so the kanban
card and the quote/deal body can surface it later.

Field semantics:
- Optional — empty / missing must be accepted without 400.
- Trimmed before persistence ("  hi  " → "hi"). Empty after trim → ``None``.

The Supabase client is mocked at ``api.quotes.get_supabase`` so the auth +
org branch and the ``quotes`` UPDATE both run in-memory without a DB. The
workflow service is mocked too — we are pinning the handler wiring, not the
state machine.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.quotes import submit_procurement  # noqa: E402


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_request(body: bytes | None, api_user_id: str | None = "u-1"):
    """Build a minimal Starlette-style request with a JSON body."""
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email="u@x.com",
                user_metadata={"org_id": "org-1", "name": "U"},
            )
        )
    req.headers = {"content-type": "application/json"}
    type(req).session = property(
        lambda _self: (_ for _ in ()).throw(AssertionError("no session"))
    )

    async def _body():
        return body if body is not None else b""

    req.body = _body
    return req


def _encode(payload: dict) -> bytes:
    """JSON-encode a dict to UTF-8 bytes (Cyrillic-safe)."""
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _mock_supabase_capturing_update():
    """Mock Supabase so we can capture the payload passed to quotes.update().

    The handler chain is:
        sb.table("quotes").update({...}).eq("id", ...).eq("organization_id", ...).execute()

    We intercept the dict passed to .update() and stash it on the returned
    sentinel so the test can assert on the persisted shape.
    """
    captured: dict = {"update_payload": None}
    sb = MagicMock()

    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "organization_members":
            tbl.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
                {"organization_id": "org-1"}
            ]
        elif name == "quotes":
            def update_side_effect(payload):
                captured["update_payload"] = payload
                chain = MagicMock()
                chain.eq.return_value.eq.return_value.execute.return_value = MagicMock()
                return chain

            tbl.update.side_effect = update_side_effect
        return tbl

    sb.table.side_effect = table_side_effect
    return sb, captured


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _ok_transition():
    """Mocked successful workflow transition (handler returns 200 then)."""
    return SimpleNamespace(success=True, error_message=None)


def _checklist_body(**overrides) -> bytes:
    """Construct a valid checklist body, optionally tweaking fields."""
    base = {
        "is_estimate": False,
        "is_tender": False,
        "direct_request": False,
        "trading_org_request": False,
        "equipment_description": "Сервер DL380",
    }
    base.update(overrides)
    return _encode({"checklist": base})


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


class TestSubmitProcurementDistributionComment:
    @patch("api.quotes.transition_to_pending_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_distribution_comment_persisted_when_present(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """Non-empty distribution_comment lands in sales_checklist."""
        sb, captured = _mock_supabase_capturing_update()
        mock_get_sb.return_value = sb
        mock_roles.return_value = ["sales"]
        mock_transition.return_value = _ok_transition()

        req = _make_request(
            _checklist_body(distribution_comment="Срочно к Алейне, клиент знакомый")
        )

        resp = _run(submit_procurement(req, "q-1"))
        assert resp.status_code == 200, resp.body
        payload = captured["update_payload"]
        assert payload is not None, "quotes.update() was never called"
        checklist = payload["sales_checklist"]
        assert (
            checklist["distribution_comment"]
            == "Срочно к Алейне, клиент знакомый"
        )

    @patch("api.quotes.transition_to_pending_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_distribution_comment_trimmed_before_persist(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """Leading/trailing whitespace is stripped (defensive against textareas)."""
        sb, captured = _mock_supabase_capturing_update()
        mock_get_sb.return_value = sb
        mock_roles.return_value = ["sales"]
        mock_transition.return_value = _ok_transition()

        req = _make_request(_checklist_body(distribution_comment="   to-mol   "))

        resp = _run(submit_procurement(req, "q-1"))
        assert resp.status_code == 200, resp.body
        assert (
            captured["update_payload"]["sales_checklist"][
                "distribution_comment"
            ]
            == "to-mol"
        )

    @patch("api.quotes.transition_to_pending_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_distribution_comment_omitted_yields_none(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """Missing field → optional → stored as None (not absent, not empty str).

        Keeps the JSONB shape stable for downstream readers and lets
        ``sales_checklist.distribution_comment ?? null`` work in TypeScript.
        """
        sb, captured = _mock_supabase_capturing_update()
        mock_get_sb.return_value = sb
        mock_roles.return_value = ["sales"]
        mock_transition.return_value = _ok_transition()

        # No distribution_comment key in the checklist payload at all.
        req = _make_request(_checklist_body())

        resp = _run(submit_procurement(req, "q-1"))
        assert resp.status_code == 200, resp.body
        assert (
            captured["update_payload"]["sales_checklist"][
                "distribution_comment"
            ]
            is None
        )

    @patch("api.quotes.transition_to_pending_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_whitespace_only_distribution_comment_is_normalized_to_none(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """A textarea that only contains spaces is semantically empty."""
        sb, captured = _mock_supabase_capturing_update()
        mock_get_sb.return_value = sb
        mock_roles.return_value = ["sales"]
        mock_transition.return_value = _ok_transition()

        req = _make_request(_checklist_body(distribution_comment="   "))

        resp = _run(submit_procurement(req, "q-1"))
        assert resp.status_code == 200, resp.body
        assert (
            captured["update_payload"]["sales_checklist"][
                "distribution_comment"
            ]
            is None
        )

    @patch("api.quotes.transition_to_pending_procurement")
    @patch("api.quotes.get_user_role_codes")
    @patch("api.quotes.get_supabase")
    def test_distribution_comment_does_not_bypass_equipment_description_gate(
        self, mock_get_sb, mock_roles, mock_transition
    ):
        """Filling only the optional comment must NOT pass the required-field check."""
        sb, _captured = _mock_supabase_capturing_update()
        mock_get_sb.return_value = sb
        mock_roles.return_value = ["sales"]
        mock_transition.return_value = _ok_transition()

        req = _make_request(
            _checklist_body(
                equipment_description="",
                distribution_comment="Срочно",
            )
        )

        resp = _run(submit_procurement(req, "q-1"))
        assert resp.status_code == 400
