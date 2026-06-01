"""Tests for the per-invoice procurement completion endpoint and helper.

Covers:
- POST /api/invoices/{id}/complete-procurement endpoint registration via FastAPI sub-app.
- Auth + ownership gating (401, 403, 404).
- Already-completed conflict (409).
- Happy path delegation to services.workflow_service.complete_procurement_for_invoice.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_uuid() -> str:
    return str(uuid4())


def _mock_api_user(user_id: str) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.email = "test@example.com"
    u.user_metadata = {"org_id": "org-x"}
    return u


def _mock_request(body: dict | None = None, api_user: MagicMock | None = None):
    request = MagicMock()
    if body is None:
        request.json = AsyncMock(side_effect=Exception("no body"))
    else:
        request.json = AsyncMock(return_value=body)
    request.state = MagicMock()
    request.state.api_user = api_user
    return request


def _chain_mock():
    m = MagicMock()
    m.select.return_value = m
    m.insert.return_value = m
    m.update.return_value = m
    m.eq.return_value = m
    m.in_.return_value = m
    m.is_.return_value = m
    m.order.return_value = m
    m.limit.return_value = m
    m.single.return_value = m
    return m


def _make_org_roles_mocks(_sb, _user_id, org_id, role_slugs):
    """Mock organization_members + user_roles lookups for _get_procurement_user."""
    org_mock = _chain_mock()
    org_mock.execute.return_value = MagicMock(
        data=[{"organization_id": org_id}]
    )

    roles_mock = _chain_mock()
    roles_mock.execute.return_value = MagicMock(
        data=[{"roles": {"slug": s}} for s in role_slugs]
    )

    return {"organization_members": org_mock, "user_roles": roles_mock}


# ============================================================================
# Endpoint route registration
# ============================================================================


class TestCompleteProcurementRouteRegistered:
    """Verify the new endpoint is wired into the FastAPI router."""

    def test_endpoint_exists_in_subapp(self):
        from starlette.testclient import TestClient

        from api.app import api_sub_app

        client = TestClient(api_sub_app)
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = client.post(
            f"/invoices/{invoice_id}/complete-procurement", json={}
        )
        # No auth → 401. 404 would mean the route isn't registered.
        assert response.status_code != 404, (
            "Route POST /invoices/{id}/complete-procurement not registered. "
            f"Got {response.status_code}: {response.text[:200]}"
        )

    def test_endpoint_exists_via_outer_mount(self):
        from starlette.testclient import TestClient

        from api.app import api_app

        client = TestClient(api_app)
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = client.post(
            f"/api/invoices/{invoice_id}/complete-procurement", json={}
        )
        assert response.status_code != 404


# ============================================================================
# Auth / ownership / conflict
# ============================================================================


class TestCompleteProcurementAuth:
    """Auth and ownership checks on the endpoint handler."""

    @pytest.mark.asyncio
    async def test_401_without_jwt(self):
        from api.invoices import complete_invoice_procurement

        request = _mock_request(body={}, api_user=None)
        response = await complete_invoice_procurement(request, make_uuid())
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_403_when_role_missing(self):
        user_id = make_uuid()
        org_id = "org-x"
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["sales"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.invoices import complete_invoice_procurement

            request = _mock_request(body={}, api_user=api_user)
            response = await complete_invoice_procurement(request, make_uuid())

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_404_when_invoice_not_found(self):
        user_id = make_uuid()
        org_id = "org-x"
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(data=[])  # not found
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.invoices import complete_invoice_procurement

            request = _mock_request(body={}, api_user=api_user)
            response = await complete_invoice_procurement(request, make_uuid())

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_when_invoice_belongs_to_other_org(self):
        user_id = make_uuid()
        org_id = "org-x"
        invoice_id = make_uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": make_uuid(),
                "invoice_number": "INV-01",
                "sent_at": None,
                "quotes": {"organization_id": "other-org"},
            }])
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.invoices import complete_invoice_procurement

            request = _mock_request(body={}, api_user=api_user)
            response = await complete_invoice_procurement(request, invoice_id)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_200_happy_path_delegates_to_service(self):
        user_id = make_uuid()
        org_id = "org-x"
        invoice_id = make_uuid()
        quote_id = make_uuid()
        api_user = _mock_api_user(user_id)

        # Mock the helper return so we don't need to mock the entire
        # workflow_service execution path here — that is covered in
        # tests/test_workflow_service.py.
        from services.workflow_service import InvoiceProcurementCompletionResult

        # logistics_assigned / customs_assigned are always False since
        # auto-distribution was removed (logistics-customs-kanban REQ-3) —
        # assignment is now manual via the workspace kanban.
        helper_result = InvoiceProcurementCompletionResult(
            success=True,
            invoice_id=invoice_id,
            quote_id=quote_id,
            workflow_advanced=True,
        )

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": quote_id,
                "invoice_number": "INV-01",
                "sent_at": None,
                # Supplier-offer file present so the mandatory-to-complete gate
                # (MISSING_SUPPLIER_FILE / 422) passes — these cases assert the
                # downstream 200/409 behaviour, not the file gate itself (that
                # is covered in test_complete_procurement_supplier_file_gate.py).
                "invoice_file_url": "https://example.test/kp.pdf",
                "quotes": {"organization_id": org_id},
            }])
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch(
                "services.workflow_service.complete_procurement_for_invoice",
                return_value=helper_result,
            ) as mock_helper:
                from api.invoices import complete_invoice_procurement

                request = _mock_request(body={}, api_user=api_user)
                response = await complete_invoice_procurement(request, invoice_id)

        assert response.status_code == 200
        # Body should expose the side-effect flags.
        import json
        body = json.loads(response.body)
        assert body["success"] is True
        assert body["data"]["workflow_advanced"] is True
        # No auto-distribution — flags are always False (REQ-3).
        assert body["data"]["logistics_assigned"] is False
        assert body["data"]["customs_assigned"] is False

        # Helper was called with the actor + roles.
        mock_helper.assert_called_once()
        call_kwargs = mock_helper.call_args.kwargs
        assert call_kwargs["invoice_id"] == invoice_id
        assert call_kwargs["actor_id"] == user_id
        assert "procurement" in call_kwargs["actor_roles"]

    @pytest.mark.asyncio
    async def test_200_when_actor_is_procurement_senior(self):
        """Regression for Testing 2 row 57.

        СтМОЗ (`procurement_senior`) was excluded from the API role gate even
        though the frontend (`invoice-card.tsx`) shows them the
        «Завершить закупку» button. The result: clicking returned 403 with
        «Procurement role required», the toast surfaced the error, and the
        quote workflow_status never advanced. This test exercises the gate
        with `procurement_senior` and asserts a 200 — and that the actor's
        role is forwarded to the workflow service.
        """
        user_id = make_uuid()
        org_id = "org-x"
        invoice_id = make_uuid()
        quote_id = make_uuid()
        api_user = _mock_api_user(user_id)

        from services.workflow_service import InvoiceProcurementCompletionResult

        helper_result = InvoiceProcurementCompletionResult(
            success=True,
            invoice_id=invoice_id,
            quote_id=quote_id,
            workflow_advanced=True,
        )

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(
                sb, user_id, org_id, ["procurement_senior"]
            )
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": quote_id,
                "invoice_number": "INV-01",
                "sent_at": None,
                # Supplier-offer file present so the mandatory-to-complete gate
                # (MISSING_SUPPLIER_FILE / 422) passes — these cases assert the
                # downstream 200/409 behaviour, not the file gate itself (that
                # is covered in test_complete_procurement_supplier_file_gate.py).
                "invoice_file_url": "https://example.test/kp.pdf",
                "quotes": {"organization_id": org_id},
            }])
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch(
                "services.workflow_service.complete_procurement_for_invoice",
                return_value=helper_result,
            ) as mock_helper:
                from api.invoices import complete_invoice_procurement

                request = _mock_request(body={}, api_user=api_user)
                response = await complete_invoice_procurement(
                    request, invoice_id
                )

        # Without the fix this asserted 403, not 200 — the gate rejected the
        # role before the helper was ever called.
        assert response.status_code == 200, (
            f"procurement_senior must pass the role gate. Got: {response.body!r}"
        )
        import json
        body = json.loads(response.body)
        assert body["success"] is True
        assert body["data"]["workflow_advanced"] is True
        # Actor role was forwarded so the workflow service can audit-log the
        # correct procurement role (not the "admin" fallback).
        mock_helper.assert_called_once()
        call_kwargs = mock_helper.call_args.kwargs
        assert "procurement_senior" in call_kwargs["actor_roles"]

    @pytest.mark.asyncio
    async def test_409_when_already_completed(self):
        user_id = make_uuid()
        org_id = "org-x"
        invoice_id = make_uuid()
        quote_id = make_uuid()
        api_user = _mock_api_user(user_id)

        from services.workflow_service import InvoiceProcurementCompletionResult

        helper_result = InvoiceProcurementCompletionResult(
            success=False,
            error_message="Procurement already completed for this invoice",
            invoice_id=invoice_id,
            quote_id=quote_id,
        )

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": quote_id,
                "invoice_number": "INV-01",
                "sent_at": None,
                # Supplier-offer file present so the mandatory-to-complete gate
                # (MISSING_SUPPLIER_FILE / 422) passes — these cases assert the
                # downstream 200/409 behaviour, not the file gate itself (that
                # is covered in test_complete_procurement_supplier_file_gate.py).
                "invoice_file_url": "https://example.test/kp.pdf",
                "quotes": {"organization_id": org_id},
            }])
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch(
                "services.workflow_service.complete_procurement_for_invoice",
                return_value=helper_result,
            ):
                from api.invoices import complete_invoice_procurement

                request = _mock_request(body={}, api_user=api_user)
                response = await complete_invoice_procurement(request, invoice_id)

        assert response.status_code == 409
        import json
        body = json.loads(response.body)
        assert body["success"] is False
        assert body["error"]["code"] == "ALREADY_COMPLETED"
