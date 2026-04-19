"""
Tests for api/composition.py — Phase 5b composition + Phase 5c
procurement-unlock approve/reject handlers.

Covers:
- GET  /api/quotes/{quote_id}/composition
- POST /api/quotes/{quote_id}/composition
- POST /api/invoices/{invoice_id}/verify
- POST /api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/approve
- POST /api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/reject

Test style mirrors tests/test_api_deals.py — MagicMock chainable query
stubs + patch on api.composition.get_supabase + AsyncMock for request.json.
"""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.composition import (  # noqa: E402
    apply_composition_endpoint,
    approve_procurement_unlock,
    get_composition,
    reject_procurement_unlock,
    verify_invoice,
)


def make_uuid() -> str:
    return str(uuid4())


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def org_id():
    return make_uuid()


@pytest.fixture
def user_id():
    return make_uuid()


@pytest.fixture
def quote_id():
    return make_uuid()


@pytest.fixture
def invoice_id():
    return make_uuid()


def _make_api_user(user_id: str, org_id: str, email: str = "test@example.com"):
    """Build a MagicMock that mimics a Supabase auth user object."""
    u = MagicMock()
    u.id = user_id
    u.email = email
    u.user_metadata = {"org_id": org_id}
    return u


def _make_request(body: dict | None, api_user=None):
    """Build a mock Starlette request with optional JSON body + api_user state."""
    request = MagicMock()
    if body is None:
        request.json = AsyncMock(side_effect=Exception("no body"))
    else:
        request.json = AsyncMock(return_value=body)
    request.state = MagicMock()
    request.state.api_user = api_user
    return request


def _chain(return_data=None, return_count=None):
    """Chainable query mock. .execute() yields data/count."""
    m = MagicMock()
    m.select.return_value = m
    m.eq.return_value = m
    m.in_.return_value = m
    m.order.return_value = m
    m.limit.return_value = m
    m.single.return_value = m
    m.insert.return_value = m
    m.update.return_value = m
    m.delete.return_value = m
    result = MagicMock()
    result.data = return_data if return_data is not None else []
    result.count = return_count
    result.error = None
    m.execute.return_value = result
    return m


def _make_supabase(table_map: dict):
    """Build a mock supabase where .table(name) returns tables_map[name] (a _chain mock).

    When a name is not in table_map, returns an empty chain.
    """
    sb = MagicMock()

    def _get_table(name):
        return table_map.get(name) or _chain()

    sb.table.side_effect = _get_table
    return sb


def _role_rows(roles: list[str]) -> list[dict]:
    """Shape a user_roles query result: [{roles: {slug: ...}}, ...]."""
    return [{"roles": {"slug": r}} for r in roles]


# ============================================================================
# GET /api/quotes/{quote_id}/composition
# ============================================================================

class TestGetComposition:

    @pytest.mark.asyncio
    async def test_happy_path_returns_view_with_can_edit(self, quote_id, user_id, org_id):
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))

        user_roles_chain = _chain(return_data=_role_rows(["sales"]))
        quotes_chain = _chain(return_data=[{
            "id": quote_id,
            "organization_id": org_id,
            "updated_at": "2026-04-10T12:00:00+00:00",
        }])
        table_map = {
            "user_roles": user_roles_chain,
            "quotes": quotes_chain,
        }
        sb = _make_supabase(table_map)

        fake_view = {
            "quote_id": quote_id,
            "items": [{"quote_item_id": "qi-1", "alternatives": [], "selected_invoice_id": None}],
            "composition_complete": False,
        }
        with patch("api.composition.get_supabase", return_value=sb), \
             patch("api.composition.get_composition_view", return_value=fake_view) as mock_view:
            response = await get_composition(request, quote_id)

        assert response.status_code == 200
        payload = json.loads(response.body)
        assert payload["success"] is True
        assert payload["data"]["quote_id"] == quote_id
        assert payload["data"]["can_edit"] is True, "sales role must have edit permission"
        mock_view.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_401_when_no_jwt(self, quote_id):
        request = _make_request(None, api_user=None)
        response = await get_composition(request, quote_id)
        assert response.status_code == 401
        payload = json.loads(response.body)
        assert payload["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_returns_403_when_role_not_in_read_set(self, quote_id, user_id, org_id):
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))
        user_roles_chain = _chain(return_data=_role_rows(["logistics"]))  # not in read set
        sb = _make_supabase({"user_roles": user_roles_chain})
        with patch("api.composition.get_supabase", return_value=sb):
            response = await get_composition(request, quote_id)
        assert response.status_code == 403
        assert json.loads(response.body)["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    @pytest.mark.asyncio
    async def test_returns_404_when_quote_in_different_org(self, quote_id, user_id, org_id):
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))
        user_roles_chain = _chain(return_data=_role_rows(["admin"]))
        quotes_chain = _chain(return_data=[{
            "id": quote_id,
            "organization_id": make_uuid(),  # different org
            "updated_at": "2026-04-10T12:00:00+00:00",
        }])
        sb = _make_supabase({"user_roles": user_roles_chain, "quotes": quotes_chain})
        with patch("api.composition.get_supabase", return_value=sb):
            response = await get_composition(request, quote_id)
        assert response.status_code == 404, "cross-org access must return 404 per access-control.md"
        assert json.loads(response.body)["error"]["code"] == "NOT_FOUND"


# ============================================================================
# POST /api/quotes/{quote_id}/composition
# ============================================================================

class TestApplyComposition:

    @pytest.mark.asyncio
    async def test_happy_path_calls_service_and_returns_completeness(self, quote_id, user_id, org_id):
        request = _make_request(
            {"selection": {"qi-1": "inv-a"}, "quote_updated_at": "2026-04-10T12:00:00+00:00"},
            api_user=_make_api_user(user_id, org_id),
        )
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["sales"])),
            "quotes": _chain(return_data=[{"id": quote_id, "organization_id": org_id, "updated_at": "2026-04-10T12:00:00+00:00"}]),
        })

        with patch("api.composition.get_supabase", return_value=sb), \
             patch("api.composition.apply_composition") as mock_apply, \
             patch("api.composition.get_composition_view", return_value={"composition_complete": True}) as mock_view:
            response = await apply_composition_endpoint(request, quote_id)

        assert response.status_code == 200
        payload = json.loads(response.body)
        assert payload["success"] is True
        assert payload["data"]["composition_complete"] is True
        mock_apply.assert_called_once()
        call_kwargs = mock_apply.call_args.kwargs
        assert call_kwargs["quote_id"] == quote_id
        assert call_kwargs["selection_map"] == {"qi-1": "inv-a"}
        assert call_kwargs["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_400_on_non_dict_selection(self, quote_id, user_id, org_id):
        request = _make_request({"selection": "not-a-dict"}, api_user=_make_api_user(user_id, org_id))
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["sales"])),
            "quotes": _chain(return_data=[{"id": quote_id, "organization_id": org_id, "updated_at": "x"}]),
        })
        with patch("api.composition.get_supabase", return_value=sb):
            response = await apply_composition_endpoint(request, quote_id)
        assert response.status_code == 400
        assert json.loads(response.body)["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_400_when_service_raises_validation_error(self, quote_id, user_id, org_id):
        from services.composition_service import ValidationError

        request = _make_request(
            {"selection": {"qi-1": "inv-bad"}},
            api_user=_make_api_user(user_id, org_id),
        )
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["sales"])),
            "quotes": _chain(return_data=[{"id": quote_id, "organization_id": org_id, "updated_at": "x"}]),
        })
        err = ValidationError([{"quote_item_id": "qi-1", "invoice_id": "inv-bad", "reason": "no match"}])

        with patch("api.composition.get_supabase", return_value=sb), \
             patch("api.composition.apply_composition", side_effect=err):
            response = await apply_composition_endpoint(request, quote_id)

        assert response.status_code == 400
        body = json.loads(response.body)
        assert body["error"]["code"] == "COMPOSITION_INVALID_SELECTION"
        assert body["error"]["fields"][0]["quote_item_id"] == "qi-1"

    @pytest.mark.asyncio
    async def test_409_when_service_raises_concurrency_error(self, quote_id, user_id, org_id):
        from services.composition_service import ConcurrencyError

        request = _make_request(
            {"selection": {"qi-1": "inv-a"}, "quote_updated_at": "stale"},
            api_user=_make_api_user(user_id, org_id),
        )
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["sales"])),
            "quotes": _chain(return_data=[{"id": quote_id, "organization_id": org_id, "updated_at": "fresh"}]),
        })
        with patch("api.composition.get_supabase", return_value=sb), \
             patch("api.composition.apply_composition", side_effect=ConcurrencyError("stale")):
            response = await apply_composition_endpoint(request, quote_id)

        assert response.status_code == 409
        assert json.loads(response.body)["error"]["code"] == "STALE_QUOTE"


# ============================================================================
# POST /api/invoices/{invoice_id}/verify
# ============================================================================

class TestVerifyInvoice:

    @pytest.mark.asyncio
    async def test_happy_path_stamps_verified_at(self, invoice_id, user_id, org_id, quote_id):
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))
        invoices_chain = _chain(return_data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "supplier_id": make_uuid(),
            "verified_at": None,
            "verified_by": None,
            "status": "pending_procurement",
            "quotes": {"id": quote_id, "organization_id": org_id},
        }])
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["procurement"])),
            "invoices": invoices_chain,
        })

        with patch("api.composition.get_supabase", return_value=sb):
            response = await verify_invoice(request, invoice_id)

        assert response.status_code == 200
        payload = json.loads(response.body)
        assert payload["data"]["verified_by"] == user_id
        assert payload["data"]["verified_at"] is not None
        # update called on invoices
        invoices_chain.update.assert_called_once()
        update_payload = invoices_chain.update.call_args.args[0]
        assert update_payload["verified_by"] == user_id
        assert "verified_at" in update_payload

    @pytest.mark.asyncio
    async def test_403_when_role_not_procurement(self, invoice_id, user_id, org_id, quote_id):
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["sales"])),  # not procurement
        })
        with patch("api.composition.get_supabase", return_value=sb):
            response = await verify_invoice(request, invoice_id)
        assert response.status_code == 403


# ============================================================================
# POST /api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/approve
# ============================================================================

class TestApproveInvoiceEdit:

    @pytest.mark.asyncio
    async def test_happy_path_applies_diff_and_marks_approved(self, invoice_id, user_id, org_id, quote_id):
        approval_id = make_uuid()
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))

        invoices_chain = _chain(return_data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "supplier_id": make_uuid(),
            "verified_at": "2026-04-10T10:00:00+00:00",
            "verified_by": make_uuid(),
            "status": "pending_procurement",
            "quotes": {"id": quote_id, "organization_id": org_id},
        }])
        approvals_chain = _chain(return_data=[{
            "id": approval_id,
            "approval_type": "invoice_edit",
            "status": "pending",
            "modifications": {
                "invoice_id": invoice_id,
                "diff": {"pickup_country": {"old": "Italy", "new": "Germany"}},
            },
        }])
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["head_of_procurement"])),
            "invoices": invoices_chain,
            "approvals": approvals_chain,
        })

        with patch("api.composition.get_supabase", return_value=sb):
            response = await approve_procurement_unlock(request, invoice_id, approval_id)

        assert response.status_code == 200
        payload = json.loads(response.body)
        assert payload["data"]["status"] == "approved"
        assert payload["data"]["applied_changes"] == {"pickup_country": "Germany"}

        # Verify the invoice update was called with the new value
        # (invoices_chain was used for both org-verify SELECT and the diff UPDATE)
        # First update call should be the diff application
        update_calls = invoices_chain.update.call_args_list
        assert any(
            call.args[0] == {"pickup_country": "Germany"} for call in update_calls
        ), "invoice.update should have been called with the diff's new values"

        # Verify approval was marked approved
        approvals_chain.update.assert_called()

    @pytest.mark.asyncio
    async def test_403_when_role_not_head_of_procurement(self, invoice_id, user_id, org_id):
        approval_id = make_uuid()
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["procurement"])),  # NOT head_of_procurement
        })
        with patch("api.composition.get_supabase", return_value=sb):
            response = await approve_procurement_unlock(request, invoice_id, approval_id)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_404_when_approval_already_processed(self, invoice_id, user_id, org_id, quote_id):
        approval_id = make_uuid()
        request = _make_request(None, api_user=_make_api_user(user_id, org_id))

        invoices_chain = _chain(return_data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "verified_at": "x",
            "quotes": {"id": quote_id, "organization_id": org_id},
        }])
        approvals_chain = _chain(return_data=[{
            "id": approval_id,
            "approval_type": "invoice_edit",
            "status": "approved",  # already processed
            "modifications": {"invoice_id": invoice_id, "diff": {}},
        }])
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["head_of_procurement"])),
            "invoices": invoices_chain,
            "approvals": approvals_chain,
        })

        with patch("api.composition.get_supabase", return_value=sb):
            response = await approve_procurement_unlock(request, invoice_id, approval_id)

        assert response.status_code == 404


# ============================================================================
# POST /api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/reject
# ============================================================================

class TestRejectInvoiceEdit:

    @pytest.mark.asyncio
    async def test_happy_path_marks_rejected(self, invoice_id, user_id, org_id, quote_id):
        approval_id = make_uuid()
        request = _make_request(
            {"decision_comment": "Prices already locked for client"},
            api_user=_make_api_user(user_id, org_id),
        )
        invoices_chain = _chain(return_data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "verified_at": "x",
            "quotes": {"id": quote_id, "organization_id": org_id},
        }])
        approvals_chain = _chain(return_data=[{
            "id": approval_id,
            "approval_type": "invoice_edit",
            "status": "pending",
            "modifications": {"invoice_id": invoice_id, "diff": {"x": {"old": 1, "new": 2}}},
        }])
        sb = _make_supabase({
            "user_roles": _chain(return_data=_role_rows(["head_of_procurement"])),
            "invoices": invoices_chain,
            "approvals": approvals_chain,
        })

        with patch("api.composition.get_supabase", return_value=sb):
            response = await reject_procurement_unlock(request, invoice_id, approval_id)

        assert response.status_code == 200
        payload = json.loads(response.body)
        assert payload["data"]["status"] == "rejected"

        # approvals.update called with status=rejected + comment
        approvals_chain.update.assert_called_once()
        update_payload = approvals_chain.update.call_args.args[0]
        assert update_payload["status"] == "rejected"
        assert update_payload["decision_comment"] == "Prices already locked for client"
        # The invoice MUST NOT be updated on reject
        assert invoices_chain.update.call_count == 0
