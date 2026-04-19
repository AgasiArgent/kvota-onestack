"""
Phase 5c Task 7 — Regression guard.

Ensures Phase 4a semantics are fully removed: ``invoices.sent_at`` must
not act as an edit gate. The column and its setter code remain (used by
commit_invoice_send for send-history metadata) but must have no blocking
side effect on subsequent edits.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.invoice_send_service import (  # noqa: E402
    check_edit_permission,
    commit_invoice_send,
)


def _mock_supabase_unlocked_quote() -> MagicMock:
    """Mock: invoice has sent_at set; parent quote has procurement_completed_at IS NULL.

    Phase 5c chain shapes:
    - invoices: .select().eq().single().execute()
    - quotes:   .select().eq().is_().single().execute()
      (`.is_("deleted_at", None)` is a soft-delete safety filter.)
    """
    mock_sb = MagicMock()

    def table_router(table_name: str):
        table_mock = MagicMock()
        if table_name == "invoices":
            chain = table_mock.select.return_value.eq.return_value.single.return_value
            chain.execute.return_value.data = {"quote_id": "quote-001"}
        elif table_name == "quotes":
            chain = (
                table_mock.select.return_value
                .eq.return_value
                .is_.return_value
                .single.return_value
            )
            chain.execute.return_value.data = {"procurement_completed_at": None}
        return table_mock

    mock_sb.table.side_effect = table_router
    return mock_sb


class TestSentAtHasNoGateEffect:
    """Invoice with sent_at != null must remain editable if procurement is still active."""

    @patch("services.invoice_send_service.get_supabase")
    def test_sent_invoice_editable_when_procurement_active(self, mock_get_sb):
        """sent_at set + procurement_completed_at NULL → editable by all roles."""
        mock_get_sb.return_value = _mock_supabase_unlocked_quote()

        assert check_edit_permission("inv-001", ["procurement"]) is True
        assert check_edit_permission("inv-001", ["sales"]) is True
        assert check_edit_permission("inv-001", ["finance"]) is True
        assert check_edit_permission("inv-001", ["quote_controller"]) is True

    def test_sent_at_remains_queryable(self):
        """sent_at column still exists — service writers (commit_invoice_send) still reference it."""
        # Static import check: sent_at is still named in the service layer
        import inspect

        from services import invoice_send_service

        source = inspect.getsource(invoice_send_service)
        assert '"sent_at"' in source, "sent_at column must remain referenced"
        assert "commit_invoice_send" in source, "commit_invoice_send function must remain"

    @patch("services.invoice_send_service.get_supabase")
    def test_commit_invoice_send_still_writes_sent_at(self, mock_get_sb):
        """commit_invoice_send must still write sent_at — it is the send audit signal."""
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        draft_row = {
            "id": "draft-001",
            "invoice_id": "inv-001",
            "sent_at": "2026-04-18T10:00:00+00:00",
        }
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [draft_row]

        commit_invoice_send(
            invoice_id="inv-001",
            user_id="user-001",
            method="letter_draft",
            language="ru",
            recipient_email="supplier@example.com",
            subject="Request for pricing",
            body_text="Please quote.",
        )

        # At least two writes: insert letter_drafts, then update invoices.sent_at
        insert_calls = [c for c in mock_sb.table.call_args_list if c.args[0] == "invoice_letter_drafts"]
        update_calls = [c for c in mock_sb.table.call_args_list if c.args[0] == "invoices"]

        assert len(insert_calls) >= 1, "commit_invoice_send must insert a letter_drafts row"
        assert len(update_calls) >= 1, "commit_invoice_send must update invoices.sent_at"
