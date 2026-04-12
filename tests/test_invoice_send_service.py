"""
Tests for invoice_send_service.

Tests:
- commit_invoice_send writes draft row + updates sent_at (mock DB)
- save_draft creates new draft
- save_draft updates existing draft
- get_active_draft returns None when no draft
- get_send_history returns ordered list
- is_invoice_sent returns True/False correctly
- check_edit_permission logic
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
    is_invoice_sent,
    check_edit_permission,
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
        # Supabase .not_("col", "is", "null") returns a chainable object
        mock_chain = mock_sb.table.return_value.select.return_value.eq.return_value
        mock_chain.not_.return_value.order.return_value.execute.return_value.data = history

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
        mock_chain.not_.return_value.order.return_value.execute.return_value.data = []

        result = get_send_history("inv-001")
        assert result == []


class TestIsInvoiceSent:
    """Tests for is_invoice_sent."""

    @patch("services.invoice_send_service.get_supabase")
    def test_returns_true_when_sent(self, mock_get_sb):
        """is_invoice_sent returns True when invoices.sent_at is not null."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"sent_at": "2026-04-11T10:00:00+00:00"}
        ]

        assert is_invoice_sent("inv-001") is True

    @patch("services.invoice_send_service.get_supabase")
    def test_returns_false_when_not_sent(self, mock_get_sb):
        """is_invoice_sent returns False when invoices.sent_at is null."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"sent_at": None}
        ]

        assert is_invoice_sent("inv-001") is False

    @patch("services.invoice_send_service.get_supabase")
    def test_returns_false_when_invoice_not_found(self, mock_get_sb):
        """is_invoice_sent returns False when invoice doesn't exist."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        assert is_invoice_sent("nonexistent") is False


class TestCheckEditPermission:
    """Tests for check_edit_permission."""

    @patch("services.invoice_send_service.is_invoice_sent")
    def test_returns_true_when_unsent(self, mock_is_sent):
        """Unsent invoices are always editable."""
        mock_is_sent.return_value = False

        assert check_edit_permission("inv-001", ["procurement"]) is True

    @patch("services.invoice_send_service.is_invoice_sent")
    def test_returns_true_for_admin_on_sent_invoice(self, mock_is_sent):
        """Admin can edit sent invoices."""
        mock_is_sent.return_value = True

        assert check_edit_permission("inv-001", ["admin"]) is True

    @patch("services.invoice_send_service.is_invoice_sent")
    def test_returns_true_for_head_of_procurement_on_sent_invoice(self, mock_is_sent):
        """Head of procurement can edit sent invoices."""
        mock_is_sent.return_value = True

        assert check_edit_permission("inv-001", ["head_of_procurement"]) is True

    @patch("services.invoice_send_service.is_invoice_sent")
    def test_returns_false_for_procurement_on_sent_invoice(self, mock_is_sent):
        """Regular procurement user cannot edit sent invoices."""
        mock_is_sent.return_value = True

        assert check_edit_permission("inv-001", ["procurement"]) is False

    @patch("services.invoice_send_service.is_invoice_sent")
    def test_returns_false_for_sales_on_sent_invoice(self, mock_is_sent):
        """Sales user cannot edit sent invoices."""
        mock_is_sent.return_value = True

        assert check_edit_permission("inv-001", ["sales"]) is False

    @patch("services.invoice_send_service.is_invoice_sent")
    def test_multiple_roles_checked(self, mock_is_sent):
        """User with multiple roles — if any is admin/head_of_procurement, edit allowed."""
        mock_is_sent.return_value = True

        assert check_edit_permission("inv-001", ["procurement", "admin"]) is True
        assert check_edit_permission("inv-001", ["sales", "head_of_procurement"]) is True
        assert check_edit_permission("inv-001", ["sales", "procurement"]) is False
