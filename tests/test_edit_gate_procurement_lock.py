"""
Edit-gate tests for the per-invoice procurement-lock model.

Post PR #74 the lock lives on ``invoices.procurement_completed_at`` —
each КП is locked independently. The gate function was renamed
``is_quote_procurement_locked → is_invoice_procurement_locked`` and
reads the invoice row directly. The override roles (admin,
head_of_procurement) still bypass the gate when locked.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.invoice_send_service import (  # noqa: E402
    check_edit_permission,
    is_invoice_procurement_locked,
    is_quote_procurement_locked,  # backwards-compat alias
)


def _mock_supabase_invoice(invoice_row: dict | None) -> tuple[MagicMock, dict]:
    """Build a mock supabase client answering one query:
    invoices.select("procurement_completed_at").eq().single().execute() → invoice_row
    """
    mock_sb = MagicMock()
    call_count = {"invoices": 0}

    def make_single_executor(row):
        exec_mock = MagicMock()
        exec_mock.data = row
        return exec_mock

    def table_router(table_name: str):
        table_mock = MagicMock()
        if table_name == "invoices":
            chain = table_mock.select.return_value.eq.return_value.single.return_value

            def count_invoices():
                call_count["invoices"] += 1
                return make_single_executor(invoice_row)

            chain.execute.side_effect = count_invoices
        return table_mock

    mock_sb.table.side_effect = table_router
    return mock_sb, call_count


class TestIsInvoiceProcurementLocked:
    """Direct tests of the per-invoice gate lookup."""

    @patch("services.invoice_send_service.get_supabase")
    def test_unlocked_when_procurement_not_completed(self, mock_get_sb):
        """procurement_completed_at IS NULL → not locked."""
        mock_sb, _ = _mock_supabase_invoice(
            invoice_row={"procurement_completed_at": None},
        )
        mock_get_sb.return_value = mock_sb

        assert is_invoice_procurement_locked("inv-001") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_locked_when_procurement_completed(self, mock_get_sb):
        """procurement_completed_at IS NOT NULL → locked."""
        mock_sb, _ = _mock_supabase_invoice(
            invoice_row={"procurement_completed_at": "2026-05-01T12:00:00+00:00"},
        )
        mock_get_sb.return_value = mock_sb

        assert is_invoice_procurement_locked("inv-001") is True

    @patch("services.invoice_send_service.get_supabase")
    def test_missing_invoice_fails_open(self, mock_get_sb):
        """Invoice row missing → fail-open (no lock)."""
        mock_sb, _ = _mock_supabase_invoice(invoice_row=None)
        mock_get_sb.return_value = mock_sb

        assert is_invoice_procurement_locked("inv-missing") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_lookup_uses_single_query(self, mock_get_sb):
        """Per-invoice gate is a single Supabase query (no quote join)."""
        mock_sb, call_count = _mock_supabase_invoice(
            invoice_row={"procurement_completed_at": "2026-05-01T12:00:00+00:00"},
        )
        mock_get_sb.return_value = mock_sb

        is_invoice_procurement_locked("inv-001")

        assert call_count["invoices"] == 1

    @patch("services.invoice_send_service.get_supabase")
    def test_legacy_alias_resolves_to_new_function(self, mock_get_sb):
        """``is_quote_procurement_locked`` is preserved as an alias."""
        mock_sb, _ = _mock_supabase_invoice(
            invoice_row={"procurement_completed_at": "2026-05-01T12:00:00+00:00"},
        )
        mock_get_sb.return_value = mock_sb

        assert is_quote_procurement_locked is is_invoice_procurement_locked
        assert is_quote_procurement_locked("inv-001") is True


class TestCheckEditPermissionProcurementGate:
    """Tests for check_edit_permission using the new per-invoice gate."""

    @patch("services.invoice_send_service.is_invoice_procurement_locked")
    def test_unlocked_invoice_allows_edit(self, mock_locked):
        """Invoice with procurement_completed_at IS NULL → editable by all roles."""
        mock_locked.return_value = False

        assert check_edit_permission("inv-001", ["procurement"]) is True
        assert check_edit_permission("inv-001", ["sales"]) is True
        assert check_edit_permission("inv-001", ["finance"]) is True

    @patch("services.invoice_send_service.is_invoice_procurement_locked")
    def test_locked_invoice_blocks_regular_user(self, mock_locked):
        """Locked invoice denies procurement/sales/finance (regular) roles."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["procurement"]) is False
        assert check_edit_permission("inv-001", ["sales"]) is False
        assert check_edit_permission("inv-001", ["finance"]) is False

    @patch("services.invoice_send_service.is_invoice_procurement_locked")
    def test_locked_invoice_allows_admin(self, mock_locked):
        """Admin bypasses lock."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["admin"]) is True

    @patch("services.invoice_send_service.is_invoice_procurement_locked")
    def test_locked_invoice_allows_head_of_procurement(self, mock_locked):
        """head_of_procurement bypasses lock."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["head_of_procurement"]) is True

    @patch("services.invoice_send_service.is_invoice_procurement_locked")
    def test_missing_invoice_fails_open_via_permission(self, mock_locked):
        """Invoice that can't be resolved → not locked → all roles can edit."""
        mock_locked.return_value = False  # mirrors fail-open behavior

        assert check_edit_permission("inv-orphan", ["procurement"]) is True
