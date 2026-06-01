"""Tests for the mandatory supplier-offer file gate on procurement completion.

КПП requirement (product owner): «Файл КП поставщика» is OPTIONAL at create
and edit, but MANDATORY to FINISH the procurement stage. The authoritative
gate lives in the backend handler
`api.invoices.complete_invoice_procurement` (after ownership-verify) and
returns HTTP 422 with a structured `MISSING_SUPPLIER_FILE` error when
`invoices.invoice_file_url` is null/empty.

Covers:
- 422 + MISSING_SUPPLIER_FILE when invoice_file_url is null.
- 422 when invoice_file_url is empty/whitespace-only.
- 200 (delegates to workflow service) when invoice_file_url is set.
- The gate never calls the workflow service when it blocks.
"""

from __future__ import annotations

import json
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


def _mock_request(api_user: MagicMock | None = None):
    request = MagicMock()
    request.json = AsyncMock(return_value={})
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


def _make_org_roles_mocks(org_id, role_slugs):
    org_mock = _chain_mock()
    org_mock.execute.return_value = MagicMock(data=[{"organization_id": org_id}])

    roles_mock = _chain_mock()
    roles_mock.execute.return_value = MagicMock(
        data=[{"roles": {"slug": s}} for s in role_slugs]
    )

    return {"organization_members": org_mock, "user_roles": roles_mock}


def _invoice_row(invoice_id, quote_id, org_id, *, invoice_file_url):
    """Ownership-shaped row. The mock ignores `.select()` so this single row
    serves BOTH the ownership query and the file-gate query — `invoice_file_url`
    is what the gate reads."""
    return {
        "id": invoice_id,
        "quote_id": quote_id,
        "invoice_number": "INV-01",
        "sent_at": None,
        "invoice_file_url": invoice_file_url,
        "quotes": {"organization_id": org_id},
    }


class TestSupplierFileGate:
    @pytest.mark.asyncio
    async def test_422_when_file_url_is_null(self):
        user_id, org_id = make_uuid(), "org-x"
        invoice_id, quote_id = make_uuid(), make_uuid()

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            tables = _make_org_roles_mocks(org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(
                data=[_invoice_row(invoice_id, quote_id, org_id, invoice_file_url=None)]
            )
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch(
                "services.workflow_service.complete_procurement_for_invoice"
            ) as mock_helper:
                from api.invoices import complete_invoice_procurement

                response = await complete_invoice_procurement(
                    _mock_request(_mock_api_user(user_id)), invoice_id
                )

        assert response.status_code == 422
        body = json.loads(response.body)
        assert body["success"] is False
        assert body["error"]["code"] == "MISSING_SUPPLIER_FILE"
        assert "файл" in body["error"]["message"].lower()
        # The gate must short-circuit before the workflow service runs.
        mock_helper.assert_not_called()

    @pytest.mark.asyncio
    async def test_422_when_file_url_is_whitespace(self):
        user_id, org_id = make_uuid(), "org-x"
        invoice_id, quote_id = make_uuid(), make_uuid()

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            tables = _make_org_roles_mocks(org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(
                data=[_invoice_row(invoice_id, quote_id, org_id, invoice_file_url="   ")]
            )
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch(
                "services.workflow_service.complete_procurement_for_invoice"
            ) as mock_helper:
                from api.invoices import complete_invoice_procurement

                response = await complete_invoice_procurement(
                    _mock_request(_mock_api_user(user_id)), invoice_id
                )

        assert response.status_code == 422
        assert json.loads(response.body)["error"]["code"] == "MISSING_SUPPLIER_FILE"
        mock_helper.assert_not_called()

    @pytest.mark.asyncio
    async def test_200_when_file_url_is_set(self):
        user_id, org_id = make_uuid(), "org-x"
        invoice_id, quote_id = make_uuid(), make_uuid()

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
            tables = _make_org_roles_mocks(org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(
                data=[
                    _invoice_row(
                        invoice_id,
                        quote_id,
                        org_id,
                        invoice_file_url="https://example.test/kp.pdf",
                    )
                ]
            )
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch(
                "services.workflow_service.complete_procurement_for_invoice",
                return_value=helper_result,
            ) as mock_helper:
                from api.invoices import complete_invoice_procurement

                response = await complete_invoice_procurement(
                    _mock_request(_mock_api_user(user_id)), invoice_id
                )

        assert response.status_code == 200
        body = json.loads(response.body)
        assert body["success"] is True
        assert body["data"]["workflow_advanced"] is True
        # With the file present, the gate passes and the workflow service runs.
        mock_helper.assert_called_once()
