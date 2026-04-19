"""
Phase 5c Task 7 — Edit-gate refactor tests.

Verifies the new gate semantics: an invoice's editability depends on the
parent quote's ``procurement_completed_at`` timestamp, NOT on the
invoice's own ``sent_at``. The override roles (admin,
head_of_procurement) still bypass the gate when active.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.invoice_send_service import (  # noqa: E402
    check_edit_permission,
    is_quote_procurement_locked,
)


def _mock_supabase_invoice_quote(
    invoice_row: dict | None,
    quote_row: dict | None,
) -> tuple[MagicMock, dict]:
    """Build a mock supabase client that answers 2 queries:
    - invoices.select("quote_id").eq().single().execute() → invoice_row
    - quotes.select("procurement_completed_at").eq().is_("deleted_at", None).single().execute()
      → quote_row (Phase 5c: soft-delete filter is part of the chain)

    Returns (mock, call_count_tracker).
    """
    mock_sb = MagicMock()
    call_count = {"invoices": 0, "quotes": 0}

    def make_single_executor(row):
        exec_mock = MagicMock()
        exec_mock.data = row
        return exec_mock

    def table_router(table_name: str):
        table_mock = MagicMock()
        if table_name == "invoices":
            # invoices chain: .select().eq().single().execute()
            chain = table_mock.select.return_value.eq.return_value.single.return_value

            def count_invoices():
                call_count["invoices"] += 1
                return make_single_executor(invoice_row)

            chain.execute.side_effect = count_invoices
        elif table_name == "quotes":
            # quotes chain: .select().eq().is_().single().execute()
            # (Phase 5c adds .is_("deleted_at", None) for soft-delete safety)
            chain = (
                table_mock.select.return_value
                .eq.return_value
                .is_.return_value
                .single.return_value
            )

            def count_quotes():
                call_count["quotes"] += 1
                return make_single_executor(quote_row)

            chain.execute.side_effect = count_quotes
        return table_mock

    mock_sb.table.side_effect = table_router
    return mock_sb, call_count


class TestIsQuoteProcurementLocked:
    """Direct tests of the new gate lookup."""

    @patch("services.invoice_send_service.get_supabase")
    def test_unlocked_when_procurement_not_completed(self, mock_get_sb):
        """procurement_completed_at IS NULL → not locked."""
        mock_sb, _ = _mock_supabase_invoice_quote(
            invoice_row={"quote_id": "quote-001"},
            quote_row={"procurement_completed_at": None},
        )
        mock_get_sb.return_value = mock_sb

        assert is_quote_procurement_locked("inv-001") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_locked_when_procurement_completed(self, mock_get_sb):
        """procurement_completed_at IS NOT NULL → locked."""
        mock_sb, _ = _mock_supabase_invoice_quote(
            invoice_row={"quote_id": "quote-001"},
            quote_row={"procurement_completed_at": "2026-04-18T12:00:00+00:00"},
        )
        mock_get_sb.return_value = mock_sb

        assert is_quote_procurement_locked("inv-001") is True

    @patch("services.invoice_send_service.get_supabase")
    def test_missing_invoice_fails_open(self, mock_get_sb):
        """Invoice row missing → fail-open (no lock)."""
        mock_sb, _ = _mock_supabase_invoice_quote(
            invoice_row=None,
            quote_row=None,
        )
        mock_get_sb.return_value = mock_sb

        assert is_quote_procurement_locked("inv-missing") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_missing_quote_fails_open(self, mock_get_sb):
        """Invoice exists but quote missing → fail-open (no lock)."""
        mock_sb, _ = _mock_supabase_invoice_quote(
            invoice_row={"quote_id": "quote-missing"},
            quote_row=None,
        )
        mock_get_sb.return_value = mock_sb

        assert is_quote_procurement_locked("inv-001") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_lookup_efficiency_two_queries(self, mock_get_sb):
        """Lookup uses exactly 2 Supabase queries (invoice → quote)."""
        mock_sb, call_count = _mock_supabase_invoice_quote(
            invoice_row={"quote_id": "quote-001"},
            quote_row={"procurement_completed_at": "2026-04-18T12:00:00+00:00"},
        )
        mock_get_sb.return_value = mock_sb

        is_quote_procurement_locked("inv-001")

        assert call_count["invoices"] == 1
        assert call_count["quotes"] == 1
        assert call_count["invoices"] + call_count["quotes"] <= 2


class TestCheckEditPermissionProcurementGate:
    """Tests for check_edit_permission using the new gate."""

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_unlocked_quote_allows_edit(self, mock_locked):
        """Invoice with procurement_completed_at IS NULL → editable by all roles."""
        mock_locked.return_value = False

        assert check_edit_permission("inv-001", ["procurement"]) is True
        assert check_edit_permission("inv-001", ["sales"]) is True
        assert check_edit_permission("inv-001", ["finance"]) is True

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_locked_quote_blocks_regular_user(self, mock_locked):
        """Locked quote denies procurement/sales/finance (regular) roles."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["procurement"]) is False
        assert check_edit_permission("inv-001", ["sales"]) is False
        assert check_edit_permission("inv-001", ["finance"]) is False

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_locked_quote_allows_admin(self, mock_locked):
        """Admin bypasses lock."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["admin"]) is True

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_locked_quote_allows_head_of_procurement(self, mock_locked):
        """head_of_procurement bypasses lock."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["head_of_procurement"]) is True

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_missing_quote_fails_open_via_permission(self, mock_locked):
        """Invoice whose quote can't be resolved → not locked → all roles can edit."""
        mock_locked.return_value = False  # mirrors fail-open behavior

        assert check_edit_permission("inv-orphan", ["procurement"]) is True
