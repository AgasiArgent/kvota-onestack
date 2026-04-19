"""
Tests for invoice_send_service.

Tests:
- commit_invoice_send writes draft row + updates sent_at (mock DB)
- save_draft creates new draft
- save_draft updates existing draft
- get_active_draft returns None when no draft
- get_send_history returns ordered list
- check_edit_permission logic (gated on procurement_completed_at)
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.invoice_send_service import (
    commit_invoice_send,
    save_draft,
    get_active_draft,
    get_send_history,
    check_edit_permission,
    is_quote_procurement_locked,
)


def _mock_supabase():
    """Create a mock Supabase client with chainable table methods."""
    mock = MagicMock()
    return mock


class TestCommitInvoiceSend:
    """Tests for commit_invoice_send — the atomic commit point."""

    @patch("services.invoice_send_service.get_supabase")
    def test_writes_draft_row_and_updates_sent_at(self, mock_get_sb):
        """commit_invoice_send inserts a letter_drafts row and updates invoices.sent_at."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        # Mock insert returning created row
        draft_row = {
            "id": "draft-uuid",
            "invoice_id": "inv-001",
            "created_by": "user-001",
            "method": "xls_download",
            "language": "ru",
            "sent_at": "2026-04-11T10:00:00+00:00",
        }
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [draft_row]
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "inv-001"}]

        result = commit_invoice_send(
            invoice_id="inv-001",
            user_id="user-001",
            method="xls_download",
            language="ru",
        )

        # Verify letter_drafts insert was called
        calls = mock_sb.table.call_args_list
        table_names = [c[0][0] for c in calls]
        assert "invoice_letter_drafts" in table_names
        assert "invoices" in table_names

        assert result["id"] == "draft-uuid"

    @patch("services.invoice_send_service.get_supabase")
    def test_commit_with_letter_draft_method(self, mock_get_sb):
        """commit_invoice_send for letter_draft includes email, subject, body."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        draft_row = {
            "id": "draft-uuid",
            "invoice_id": "inv-001",
            "created_by": "user-001",
            "method": "letter_draft",
            "language": "ru",
            "recipient_email": "supplier@example.com",
            "subject": "Запрос цен",
            "body_text": "Уважаемый поставщик...",
            "sent_at": "2026-04-11T10:00:00+00:00",
        }
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [draft_row]
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "inv-001"}]

        result = commit_invoice_send(
            invoice_id="inv-001",
            user_id="user-001",
            method="letter_draft",
            language="ru",
            recipient_email="supplier@example.com",
            subject="Запрос цен",
            body_text="Уважаемый поставщик...",
        )

        assert result["method"] == "letter_draft"
        assert result["recipient_email"] == "supplier@example.com"


class TestSaveDraft:
    """Tests for save_draft — upsert active draft."""

    @patch("services.invoice_send_service.get_supabase")
    def test_creates_new_draft_when_none_exists(self, mock_get_sb):
        """save_draft creates a new draft when no active draft exists."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        # get_active_draft returns no existing draft
        mock_sb.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = []

        # insert returns new draft
        new_draft = {
            "id": "new-draft-uuid",
            "invoice_id": "inv-001",
            "created_by": "user-001",
            "language": "ru",
            "method": "letter_draft",
            "recipient_email": "supplier@example.com",
            "subject": "Subject",
            "body_text": "Body",
        }
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [new_draft]

        result = save_draft(
            invoice_id="inv-001",
            user_id="user-001",
            data={
                "language": "ru",
                "recipient_email": "supplier@example.com",
                "subject": "Subject",
                "body_text": "Body",
            },
        )

        assert result["id"] == "new-draft-uuid"

    @patch("services.invoice_send_service.get_supabase")
    def test_updates_existing_draft(self, mock_get_sb):
        """save_draft updates existing active draft instead of creating new one."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        # get_active_draft returns existing draft
        existing_draft = {"id": "existing-draft-uuid", "invoice_id": "inv-001"}
        mock_sb.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [existing_draft]

        # update returns updated draft
        updated_draft = {
            "id": "existing-draft-uuid",
            "invoice_id": "inv-001",
            "subject": "Updated Subject",
        }
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [updated_draft]

        result = save_draft(
            invoice_id="inv-001",
            user_id="user-001",
            data={
                "subject": "Updated Subject",
                "body_text": "Updated Body",
            },
        )

        assert result["id"] == "existing-draft-uuid"


class TestGetActiveDraft:
    """Tests for get_active_draft."""

    @patch("services.invoice_send_service.get_supabase")
    def test_returns_none_when_no_draft(self, mock_get_sb):
        """get_active_draft returns None when no unsent draft exists."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        mock_sb.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = []

        result = get_active_draft("inv-001")
        assert result is None

    @patch("services.invoice_send_service.get_supabase")
    def test_returns_draft_when_exists(self, mock_get_sb):
        """get_active_draft returns the unsent draft when one exists."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        draft = {
            "id": "draft-uuid",
            "invoice_id": "inv-001",
            "sent_at": None,
            "subject": "Draft Subject",
        }
        mock_sb.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [draft]

        result = get_active_draft("inv-001")
        assert result is not None
        assert result["id"] == "draft-uuid"


class TestGetSendHistory:
    """Tests for get_send_history."""

    @patch("services.invoice_send_service.get_supabase")
    def test_returns_ordered_list(self, mock_get_sb):
        """get_send_history returns sent drafts ordered by sent_at DESC."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        history = [
            {"id": "draft-2", "sent_at": "2026-04-11T12:00:00+00:00", "method": "letter_draft"},
            {"id": "draft-1", "sent_at": "2026-04-11T10:00:00+00:00", "method": "xls_download"},
        ]
        # Supabase .not_.is_("col", "null") — .not_ is a property, .is_() is the call
        mock_chain = mock_sb.table.return_value.select.return_value.eq.return_value
        mock_chain.not_.is_.return_value.order.return_value.execute.return_value.data = history

        result = get_send_history("inv-001")

        assert len(result) == 2
        assert result[0]["id"] == "draft-2"
        assert result[1]["id"] == "draft-1"

    @patch("services.invoice_send_service.get_supabase")
    def test_returns_empty_list_when_no_history(self, mock_get_sb):
        """get_send_history returns empty list when nothing has been sent."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        mock_chain = mock_sb.table.return_value.select.return_value.eq.return_value
        mock_chain.not_.is_.return_value.order.return_value.execute.return_value.data = []

        result = get_send_history("inv-001")
        assert result == []


class TestCheckEditPermission:
    """Tests for check_edit_permission (Phase 5c: gated on procurement_completed_at)."""

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_returns_true_when_unlocked(self, mock_locked):
        """Unlocked quotes (procurement active) are always editable."""
        mock_locked.return_value = False

        assert check_edit_permission("inv-001", ["procurement"]) is True

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_returns_true_for_admin_on_locked_quote(self, mock_locked):
        """Admin can edit procurement-locked invoices."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["admin"]) is True

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_returns_true_for_head_of_procurement_on_locked_quote(self, mock_locked):
        """Head of procurement can edit procurement-locked invoices."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["head_of_procurement"]) is True

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_returns_false_for_procurement_on_locked_quote(self, mock_locked):
        """Regular procurement user cannot edit procurement-locked invoices."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["procurement"]) is False

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_returns_false_for_sales_on_locked_quote(self, mock_locked):
        """Sales user cannot edit procurement-locked invoices."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["sales"]) is False

    @patch("services.invoice_send_service.is_quote_procurement_locked")
    def test_multiple_roles_checked(self, mock_locked):
        """User with multiple roles — if any is admin/head_of_procurement, edit allowed."""
        mock_locked.return_value = True

        assert check_edit_permission("inv-001", ["procurement", "admin"]) is True
        assert check_edit_permission("inv-001", ["sales", "head_of_procurement"]) is True
        assert check_edit_permission("inv-001", ["sales", "procurement"]) is False


class TestIsQuoteProcurementLocked:
    """Tests for is_quote_procurement_locked (Phase 5c: soft-delete aware)."""

    @patch("services.invoice_send_service.get_supabase")
    def test_locked_when_procurement_completed(self, mock_get_sb):
        """Quote with non-null procurement_completed_at → locked."""
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # invoices lookup returns quote_id
        inv_chain = MagicMock()
        inv_chain.execute.return_value.data = {"quote_id": "q-001"}
        # quotes lookup returns procurement_completed_at set
        q_chain = MagicMock()
        q_chain.execute.return_value.data = {
            "procurement_completed_at": "2026-04-11T10:00:00+00:00"
        }

        def table_side_effect(name):
            table_mock = MagicMock()
            if name == "invoices":
                table_mock.select.return_value.eq.return_value.single.return_value = inv_chain
            else:  # quotes
                table_mock.select.return_value.eq.return_value.is_.return_value.single.return_value = q_chain
            return table_mock

        mock_sb.table.side_effect = table_side_effect

        assert is_quote_procurement_locked("inv-001") is True

    @patch("services.invoice_send_service.get_supabase")
    def test_locked_excludes_soft_deleted_quote(self, mock_get_sb):
        """Soft-deleted quote (deleted_at IS NOT NULL) must NOT trigger the lock.

        Even if procurement_completed_at is set, a soft-deleted quote is
        effectively gone — the edit-gate should fail open so the invoice row
        remains editable by legacy flows that have not yet filtered on it.
        The ``.is_("deleted_at", None)`` filter in the PostgREST query makes
        the quotes lookup return no data for soft-deleted quotes, which the
        fail-open branch treats as "not locked".
        """
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        inv_chain = MagicMock()
        inv_chain.execute.return_value.data = {"quote_id": "q-deleted"}
        # Soft-deleted quote: PostgREST .is_("deleted_at", None) filter
        # excludes it, so data is empty.
        q_chain = MagicMock()
        q_chain.execute.return_value.data = None

        def table_side_effect(name):
            table_mock = MagicMock()
            if name == "invoices":
                table_mock.select.return_value.eq.return_value.single.return_value = inv_chain
            else:  # quotes
                table_mock.select.return_value.eq.return_value.is_.return_value.single.return_value = q_chain
            return table_mock

        mock_sb.table.side_effect = table_side_effect

        assert is_quote_procurement_locked("inv-001") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_unlocked_when_procurement_completed_at_null(self, mock_get_sb):
        """Active quote without procurement_completed_at → not locked."""
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        inv_chain = MagicMock()
        inv_chain.execute.return_value.data = {"quote_id": "q-001"}
        q_chain = MagicMock()
        q_chain.execute.return_value.data = {"procurement_completed_at": None}

        def table_side_effect(name):
            table_mock = MagicMock()
            if name == "invoices":
                table_mock.select.return_value.eq.return_value.single.return_value = inv_chain
            else:
                table_mock.select.return_value.eq.return_value.is_.return_value.single.return_value = q_chain
            return table_mock

        mock_sb.table.side_effect = table_side_effect

        assert is_quote_procurement_locked("inv-001") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_soft_delete_filter_uses_none_not_string_literal(self, mock_get_sb):
        """The `.is_("deleted_at", ...)` filter must pass Python ``None``.

        Regression guard for the services-layer soft-delete audit
        (``tests/test_services_soft_delete_audit.py``) which scans for the
        canonical ``.is_("deleted_at", None)`` form. The string literal
        ``"null"`` also works at the PostgREST level but is not recognised
        by the audit regex — a read with the string form silently bypasses
        the guardrail and shows up as a violation on every CI run.
        """
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        inv_chain = MagicMock()
        inv_chain.execute.return_value.data = {"quote_id": "q-001"}
        q_chain = MagicMock()
        q_chain.execute.return_value.data = {"procurement_completed_at": None}

        # Capture the .is_() call args from the quotes query chain.
        quotes_is_mock = MagicMock()
        quotes_is_mock.single.return_value = q_chain

        def table_side_effect(name):
            table_mock = MagicMock()
            if name == "invoices":
                table_mock.select.return_value.eq.return_value.single.return_value = inv_chain
            else:  # quotes
                table_mock.select.return_value.eq.return_value.is_ = quotes_is_mock
                quotes_is_mock.return_value = quotes_is_mock
            return table_mock

        mock_sb.table.side_effect = table_side_effect

        is_quote_procurement_locked("inv-001")

        quotes_is_mock.assert_called_once_with("deleted_at", None)
