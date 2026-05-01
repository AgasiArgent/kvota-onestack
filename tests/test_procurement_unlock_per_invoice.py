"""Regression tests for the per-invoice procurement-unlock flow.

Post PR #74 the lock lives on ``invoices.procurement_completed_at``
(per-invoice КП closure). The unlock-request gate must read this column
on the target invoice, and approving an ``edit_completed_procurement``
approval must clear the lock fields on that specific invoice.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_uuid() -> str:
    return str(uuid4())


def _mock_api_user(user_id: str) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.email = "head@example.com"
    u.user_metadata = {"org_id": "org-x"}
    return u


def _mock_request(api_user: MagicMock, body: dict | None = None) -> MagicMock:
    request = MagicMock()
    if body is None:
        request.json = AsyncMock(return_value={})
    else:
        request.json = AsyncMock(return_value=body)
    request.state = MagicMock()
    request.state.api_user = api_user
    return request


def _chain_mock() -> MagicMock:
    m = MagicMock()
    for method in ("select", "insert", "update", "eq", "in_", "order", "limit", "single", "is_"):
        getattr(m, method).return_value = m
    return m


def _make_org_and_role_mocks(org_id: str, role_slugs: list[str]) -> dict:
    org_mock = _chain_mock()
    org_mock.execute.return_value = MagicMock(data=[{"organization_id": org_id}])

    roles_mock = _chain_mock()
    roles_mock.execute.return_value = MagicMock(
        data=[{"roles": {"slug": s}} for s in role_slugs]
    )

    return {"organization_members": org_mock, "user_roles": roles_mock}


# ============================================================================
# Approve → invoice unlocked
# ============================================================================


class TestApproveProcurementUnlockClearsInvoiceLock:
    """The approve handler must clear the per-invoice lock on grant."""

    @pytest.mark.asyncio
    async def test_approve_clears_procurement_completed_fields(self):
        """Approving an edit_completed_procurement approval clears
        procurement_completed_at + procurement_completed_by on the target
        invoice — even when the diff carries no field updates."""
        head_user = _make_uuid()
        org_id = "org-x"
        invoice_id = _make_uuid()
        approval_id = _make_uuid()
        api_user = _mock_api_user(head_user)

        # Capture the update payload landing on invoices
        captured_invoice_update = {}
        captured_approval_update = {}

        with patch("api.composition.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_and_role_mocks(org_id, ["head_of_procurement"])

            invoice_mock = _chain_mock()
            invoice_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": _make_uuid(),
                "supplier_id": _make_uuid(),
                "verified_at": None,
                "verified_by": None,
                "status": None,
                "quotes": {"id": _make_uuid(), "organization_id": org_id},
            }])

            def invoice_update_capture(payload):
                captured_invoice_update.update(payload)
                inner = _chain_mock()
                inner.execute.return_value = MagicMock(data=[{}])
                return inner

            invoice_mock.update.side_effect = invoice_update_capture
            tables["invoices"] = invoice_mock

            approval_lookup = _chain_mock()
            approval_lookup.execute.return_value = MagicMock(data=[{
                "id": approval_id,
                "approval_type": "edit_completed_procurement",
                "status": "pending",
                "modifications": {
                    "invoice_id": invoice_id,
                    "diff": {},  # No field changes — pure unlock request
                },
            }])

            def approval_update_capture(payload):
                captured_approval_update.update(payload)
                inner = _chain_mock()
                inner.execute.return_value = MagicMock(data=[{}])
                return inner

            approval_lookup.update.side_effect = approval_update_capture
            tables["approvals"] = approval_lookup

            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.composition import approve_procurement_unlock

            request = _mock_request(api_user)
            response = await approve_procurement_unlock(request, invoice_id, approval_id)

        assert response.status_code == 200
        assert "procurement_completed_at" in captured_invoice_update
        assert captured_invoice_update["procurement_completed_at"] is None
        assert "procurement_completed_by" in captured_invoice_update
        assert captured_invoice_update["procurement_completed_by"] is None
        assert captured_approval_update.get("status") == "approved"

    @pytest.mark.asyncio
    async def test_approve_keeps_diff_fields_alongside_unlock(self):
        """Approval with a diff (typo correction) applies the diff AND
        clears the lock — both behaviours are additive."""
        head_user = _make_uuid()
        org_id = "org-x"
        invoice_id = _make_uuid()
        approval_id = _make_uuid()
        api_user = _mock_api_user(head_user)

        captured_invoice_update = {}

        with patch("api.composition.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_and_role_mocks(org_id, ["head_of_procurement"])

            invoice_mock = _chain_mock()
            invoice_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": _make_uuid(),
                "supplier_id": _make_uuid(),
                "verified_at": None,
                "verified_by": None,
                "status": None,
                "quotes": {"id": _make_uuid(), "organization_id": org_id},
            }])

            def invoice_update_capture(payload):
                captured_invoice_update.update(payload)
                inner = _chain_mock()
                inner.execute.return_value = MagicMock(data=[{}])
                return inner

            invoice_mock.update.side_effect = invoice_update_capture
            tables["invoices"] = invoice_mock

            approval_lookup = _chain_mock()
            approval_lookup.execute.return_value = MagicMock(data=[{
                "id": approval_id,
                "approval_type": "edit_completed_procurement",
                "status": "pending",
                "modifications": {
                    "invoice_id": invoice_id,
                    "diff": {
                        "supplier_notes": {"old": "old", "new": "fixed-typo"},
                    },
                },
            }])

            def approval_update_capture(payload):
                inner = _chain_mock()
                inner.execute.return_value = MagicMock(data=[{}])
                return inner

            approval_lookup.update.side_effect = approval_update_capture
            tables["approvals"] = approval_lookup

            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.composition import approve_procurement_unlock

            request = _mock_request(api_user)
            response = await approve_procurement_unlock(request, invoice_id, approval_id)

        assert response.status_code == 200
        # Lock cleared
        assert captured_invoice_update.get("procurement_completed_at") is None
        assert captured_invoice_update.get("procurement_completed_by") is None
        # Diff applied
        assert captured_invoice_update.get("supplier_notes") == "fixed-typo"

    @pytest.mark.asyncio
    async def test_approve_skips_unlock_for_legacy_invoice_edit_type(self):
        """Historical Phase 5b ``invoice_edit`` approvals must NOT clear
        the per-invoice lock — they were created against a different
        gate semantic and may not target the closure flag at all."""
        head_user = _make_uuid()
        org_id = "org-x"
        invoice_id = _make_uuid()
        approval_id = _make_uuid()
        api_user = _mock_api_user(head_user)

        captured_invoice_update = {}

        with patch("api.composition.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_and_role_mocks(org_id, ["head_of_procurement"])

            invoice_mock = _chain_mock()
            invoice_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": _make_uuid(),
                "supplier_id": _make_uuid(),
                "verified_at": None,
                "verified_by": None,
                "status": None,
                "quotes": {"id": _make_uuid(), "organization_id": org_id},
            }])

            def invoice_update_capture(payload):
                captured_invoice_update.update(payload)
                inner = _chain_mock()
                inner.execute.return_value = MagicMock(data=[{}])
                return inner

            invoice_mock.update.side_effect = invoice_update_capture
            tables["invoices"] = invoice_mock

            approval_lookup = _chain_mock()
            approval_lookup.execute.return_value = MagicMock(data=[{
                "id": approval_id,
                "approval_type": "invoice_edit",  # Legacy Phase 5b literal
                "status": "pending",
                "modifications": {
                    "invoice_id": invoice_id,
                    "diff": {
                        "supplier_notes": {"old": "old", "new": "new"},
                    },
                },
            }])

            def approval_update_capture(payload):
                inner = _chain_mock()
                inner.execute.return_value = MagicMock(data=[{}])
                return inner

            approval_lookup.update.side_effect = approval_update_capture
            tables["approvals"] = approval_lookup

            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.composition import approve_procurement_unlock

            request = _mock_request(api_user)
            response = await approve_procurement_unlock(request, invoice_id, approval_id)

        assert response.status_code == 200
        # Diff still applied
        assert captured_invoice_update.get("supplier_notes") == "new"
        # But lock is NOT auto-cleared for legacy approvals
        assert "procurement_completed_at" not in captured_invoice_update
        assert "procurement_completed_by" not in captured_invoice_update


# ============================================================================
# Request gate reads invoices.procurement_completed_at
# ============================================================================


class TestRequestUnlockUsesPerInvoiceGate:
    """The request endpoint must consult the per-invoice gate, not the
    legacy quote-level flag."""

    @pytest.mark.asyncio
    async def test_request_imports_invoice_level_gate(self):
        """``api.invoices.request_procurement_unlock`` must call
        ``is_invoice_procurement_locked`` (the per-invoice gate),
        not the legacy ``is_quote_procurement_locked`` lookup."""
        import inspect

        from api import invoices as inv_mod

        source = inspect.getsource(inv_mod.request_procurement_unlock)
        assert "is_invoice_procurement_locked" in source, (
            "request_procurement_unlock must call the per-invoice gate"
        )
