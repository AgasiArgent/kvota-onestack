"""
Tests for Approval Service - Approval request workflow

Tests for:
- WF-004: Approval request creation (request_approval)
- Feature #64: Basic approval CRUD
- Feature #65: High-level request_approval
- Feature #66: High-level process_approval_decision
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.approval_service import (
    # Data classes
    Approval,
    ApprovalRequestResult,
    ApprovalDecisionResult,
    # Create operations
    create_approval,
    create_approvals_for_role,
    # Read operations
    get_approval,
    get_approval_by_quote,
    get_approvals_for_quote,
    get_pending_approval_for_quote,
    get_pending_approvals_for_user,
    get_approvals_requested_by,
    get_approvals_with_details,
    count_pending_approvals,
    # Update operations
    update_approval_status,
    approve_quote_approval,
    reject_quote_approval,
    # Delete operations
    cancel_pending_approvals_for_quote,
    # Utility functions
    has_pending_approval,
    get_latest_approval_decision,
    get_approval_stats_for_user,
    # High-level workflow functions
    request_approval,
    process_approval_decision,
)


# =============================================================================
# APPROVAL DATA CLASS TESTS
# =============================================================================

class TestApprovalDataClass:
    """Tests for Approval dataclass."""

    def test_approval_dataclass_creation(self):
        """Approval dataclass should be creatable with required fields."""
        approval = Approval(
            id="approval-uuid",
            quote_id="quote-uuid",
            requested_by="user-uuid",
            approver_id="manager-uuid",
            approval_type="top_manager",
            reason="RUB currency, markup below 15%",
            status="pending",
            decision_comment=None,
            requested_at=datetime.now(timezone.utc),
            decided_at=None
        )

        assert approval.id == "approval-uuid"
        assert approval.status == "pending"
        assert approval.decision_comment is None

    def test_approval_from_dict_minimal(self):
        """Approval.from_dict should create approval from minimal dict."""
        data = {
            "id": "approval-uuid",
            "quote_id": "quote-uuid",
            "requested_by": "user-uuid",
            "approver_id": "manager-uuid",
            "reason": "Low markup",
            "status": "pending",
            "requested_at": "2026-01-15T12:00:00Z"
        }

        approval = Approval.from_dict(data)

        assert approval.id == "approval-uuid"
        assert approval.status == "pending"
        assert approval.approval_type == "top_manager"  # default

    def test_approval_from_dict_full(self):
        """Approval.from_dict should handle all fields."""
        data = {
            "id": "approval-uuid",
            "quote_id": "quote-uuid",
            "requested_by": "user-uuid",
            "approver_id": "manager-uuid",
            "approval_type": "custom_type",
            "reason": "Custom reason",
            "status": "approved",
            "decision_comment": "Одобрено без замечаний",
            "requested_at": "2026-01-15T12:00:00Z",
            "decided_at": "2026-01-15T14:00:00Z"
        }

        approval = Approval.from_dict(data)

        assert approval.approval_type == "custom_type"
        assert approval.decision_comment == "Одобрено без замечаний"
        assert approval.decided_at is not None

    def test_approval_from_dict_with_datetime_object(self):
        """Approval.from_dict should handle datetime objects."""
        data = {
            "id": "approval-uuid",
            "quote_id": "quote-uuid",
            "requested_by": "user-uuid",
            "approver_id": "manager-uuid",
            "reason": "Test",
            "status": "pending",
            "requested_at": datetime.now(timezone.utc)
        }

        approval = Approval.from_dict(data)
        assert approval.requested_at is not None


# =============================================================================
# RESULT DATA CLASS TESTS
# =============================================================================

class TestResultDataClasses:
    """Tests for ApprovalRequestResult and ApprovalDecisionResult."""

    def test_approval_request_result_success(self):
        """ApprovalRequestResult should capture success state."""
        result = ApprovalRequestResult(
            success=True,
            quote_id="quote-uuid",
            approvals_created=2,
            notifications_sent=2,
            transition_success=True,
            error_message=None
        )

        assert result.success is True
        assert result.approvals_created == 2
        assert result.error_message is None

    def test_approval_request_result_failure(self):
        """ApprovalRequestResult should capture failure state."""
        result = ApprovalRequestResult(
            success=False,
            quote_id="quote-uuid",
            approvals_created=0,
            notifications_sent=0,
            transition_success=False,
            error_message="КП не найдено"
        )

        assert result.success is False
        assert result.error_message == "КП не найдено"

    def test_approval_decision_result_approved(self):
        """ApprovalDecisionResult should capture approved decision."""
        result = ApprovalDecisionResult(
            success=True,
            approval_id="approval-uuid",
            quote_id="quote-uuid",
            quote_idn="KP-2025-001",
            decision="approved",
            new_status="approved",
            other_approvals_cancelled=1,
            notifications_sent=1
        )

        assert result.success is True
        assert result.decision == "approved"
        assert result.new_status == "approved"

    def test_approval_decision_result_rejected(self):
        """ApprovalDecisionResult should capture rejected decision."""
        result = ApprovalDecisionResult(
            success=True,
            approval_id="approval-uuid",
            quote_id="quote-uuid",
            quote_idn="KP-2025-001",
            decision="rejected",
            new_status="rejected",
            other_approvals_cancelled=1,
            notifications_sent=1
        )

        assert result.decision == "rejected"
        assert result.new_status == "rejected"

    def test_approval_decision_result_failure(self):
        """ApprovalDecisionResult should capture error state."""
        result = ApprovalDecisionResult(
            success=False,
            approval_id="approval-uuid",
            quote_id=None,
            quote_idn=None,
            decision="approved",
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message="Approval not found"
        )

        assert result.success is False
        assert result.error_message == "Approval not found"


# =============================================================================
# PROCESS APPROVAL DECISION VALIDATION TESTS
# =============================================================================

class TestProcessApprovalDecisionValidation:
    """Tests for process_approval_decision validation logic."""

    def test_invalid_decision_value_should_fail(self):
        """process_approval_decision should reject invalid decision values."""
        result = process_approval_decision(
            approval_id="approval-uuid",
            decision="invalid_decision"
        )

        assert result.success is False
        assert result.decision == "invalid_decision"
        assert "недопустимое" in result.error_message.lower() or "решение" in result.error_message.lower()

    def test_valid_approved_decision(self):
        """process_approval_decision should accept 'approved' as valid."""
        # This will fail at get_approval, but we're just testing validation passes
        with patch('services.approval_service.get_approval') as mock_get:
            mock_get.return_value = None  # Approval not found
            result = process_approval_decision(
                approval_id="approval-uuid",
                decision="approved"
            )
            # Should fail with "not found", not "invalid decision"
            assert "недопустимое" not in result.error_message.lower()

    def test_valid_rejected_decision(self):
        """process_approval_decision should accept 'rejected' as valid."""
        with patch('services.approval_service.get_approval') as mock_get:
            mock_get.return_value = None
            result = process_approval_decision(
                approval_id="approval-uuid",
                decision="rejected"
            )
            assert "недопустимое" not in result.error_message.lower()

    def test_approval_not_found_should_fail(self):
        """process_approval_decision should fail if approval not found."""
        with patch('services.approval_service.get_approval') as mock_get:
            mock_get.return_value = None

            result = process_approval_decision(
                approval_id="nonexistent-uuid",
                decision="approved"
            )

            assert result.success is False
            assert "не найден" in result.error_message.lower()

    def test_already_processed_should_fail(self):
        """process_approval_decision should fail if already processed."""
        mock_approval = Approval(
            id="approval-uuid",
            quote_id="quote-uuid",
            requested_by="user-uuid",
            approver_id="manager-uuid",
            approval_type="top_manager",
            reason="Test",
            status="approved",  # Already processed
            decision_comment=None,
            requested_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc)
        )

        with patch('services.approval_service.get_approval') as mock_get:
            mock_get.return_value = mock_approval

            result = process_approval_decision(
                approval_id="approval-uuid",
                decision="approved"
            )

            assert result.success is False
            assert "обработан" in result.error_message.lower()


# =============================================================================
# CREATE OPERATIONS TESTS
# =============================================================================

class TestCreateOperations:
    """Tests for approval create operations."""

    @patch('services.approval_service.get_supabase')
    def test_create_approval_calls_insert(self, mock_supabase):
        """create_approval should call Supabase insert with correct data."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{
            "id": "new-approval-uuid",
            "quote_id": "quote-uuid",
            "requested_by": "user-uuid",
            "approver_id": "manager-uuid",
            "approval_type": "top_manager",
            "reason": "Low markup",
            "status": "pending",
            "decision_comment": None,
            "requested_at": "2026-01-15T12:00:00Z",
            "decided_at": None
        }]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = create_approval(
            quote_id="quote-uuid",
            requested_by="user-uuid",
            approver_id="manager-uuid",
            reason="Low markup"
        )

        # Verify insert was called
        mock_client.table.assert_called_with('approvals')
        insert_call = mock_client.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]

        assert inserted_data['quote_id'] == 'quote-uuid'
        assert inserted_data['requested_by'] == 'user-uuid'
        assert inserted_data['approver_id'] == 'manager-uuid'
        assert inserted_data['reason'] == 'Low markup'
        assert inserted_data['status'] == 'pending'

    @patch('services.approval_service.get_supabase')
    def test_create_approval_with_custom_type(self, mock_supabase):
        """create_approval should accept custom approval type."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{
            "id": "approval-uuid",
            "quote_id": "quote-uuid",
            "requested_by": "user-uuid",
            "approver_id": "manager-uuid",
            "approval_type": "finance_review",
            "reason": "High value deal",
            "status": "pending",
            "requested_at": "2026-01-15T12:00:00Z"
        }]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        create_approval(
            quote_id="quote-uuid",
            requested_by="user-uuid",
            approver_id="manager-uuid",
            reason="High value deal",
            approval_type="finance_review"
        )

        # Verify custom type in insert data
        insert_call = mock_client.table.return_value.insert.call_args
        assert insert_call[0][0]['approval_type'] == 'finance_review'

    @patch('services.approval_service.get_supabase')
    def test_create_approval_error_handling(self, mock_supabase):
        """create_approval should return None on error."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.side_effect = Exception("DB Error")

        result = create_approval(
            quote_id="quote-uuid",
            requested_by="user-uuid",
            approver_id="manager-uuid",
            reason="Test"
        )

        assert result is None


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""

    @patch('services.approval_service.get_supabase')
    def test_count_pending_approvals(self, mock_supabase):
        """count_pending_approvals should return correct count."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.count = 5
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        result = count_pending_approvals("user-uuid")

        assert result == 5


# =============================================================================
# IMPORT VERIFICATION TESTS
# =============================================================================

class TestImports:
    """Tests to verify all functions are importable."""

    def test_import_approval_dataclass(self):
        """Approval dataclass should be importable."""
        from services.approval_service import Approval
        assert Approval is not None

    def test_import_result_dataclasses(self):
        """Result dataclasses should be importable."""
        from services.approval_service import ApprovalRequestResult, ApprovalDecisionResult
        assert ApprovalRequestResult is not None
        assert ApprovalDecisionResult is not None

    def test_import_create_operations(self):
        """Create operations should be importable."""
        from services.approval_service import create_approval, create_approvals_for_role
        assert callable(create_approval)
        assert callable(create_approvals_for_role)

    def test_import_read_operations(self):
        """Read operations should be importable."""
        from services.approval_service import (
            get_approval,
            get_approvals_for_quote,
            get_pending_approvals_for_user,
            count_pending_approvals,
            get_pending_approval_for_quote,
            get_approval_by_quote,
            has_pending_approval
        )
        assert all(callable(f) for f in [
            get_approval,
            get_approvals_for_quote,
            get_pending_approvals_for_user,
            count_pending_approvals,
            get_pending_approval_for_quote,
            get_approval_by_quote,
            has_pending_approval
        ])

    def test_import_update_operations(self):
        """Update operations should be importable."""
        from services.approval_service import (
            update_approval_status,
            approve_quote_approval,
            reject_quote_approval
        )
        assert all(callable(f) for f in [
            update_approval_status,
            approve_quote_approval,
            reject_quote_approval
        ])

    def test_import_high_level_functions(self):
        """High-level workflow functions should be importable."""
        from services.approval_service import request_approval, process_approval_decision
        assert callable(request_approval)
        assert callable(process_approval_decision)

    def test_import_utility_functions(self):
        """Utility functions should be importable."""
        from services.approval_service import (
            get_latest_approval_decision,
            cancel_pending_approvals_for_quote,
            get_approval_stats_for_user
        )
        assert all(callable(f) for f in [
            get_latest_approval_decision,
            cancel_pending_approvals_for_quote,
            get_approval_stats_for_user
        ])


# =============================================================================
# SERVICE INTEGRATION VERIFICATION
# =============================================================================

class TestServiceIntegration:
    """Tests to verify service integrations."""

    def test_request_approval_imports_workflow_service(self):
        """request_approval should use workflow_service for transitions."""
        from services.approval_service import request_approval
        from services.workflow_service import transition_quote_status
        assert callable(request_approval)
        assert callable(transition_quote_status)

    def test_workflow_status_enum_available(self):
        """WorkflowStatus enum should be importable for validation."""
        from services.workflow_service import WorkflowStatus
        assert WorkflowStatus.PENDING_APPROVAL is not None
        assert WorkflowStatus.PENDING_QUOTE_CONTROL is not None

    def test_telegram_service_integration(self):
        """Telegram service functions should be importable for notifications."""
        from services.telegram_service import send_approval_notification_for_quote
        assert callable(send_approval_notification_for_quote)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
