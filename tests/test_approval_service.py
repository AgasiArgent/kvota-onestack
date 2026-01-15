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


# =============================================================================
# WF-005: APPROVAL WITH MODIFICATIONS TESTS (v3.0)
# =============================================================================

from services.approval_service import (
    # New v3.0 exports
    ModificationValidationResult,
    ApprovalWithModificationsResult,
    ApplyModificationsResult,
    ALLOWED_QUOTE_MODIFICATIONS,
    ALLOWED_ITEM_MODIFICATIONS,
    validate_modifications,
    approve_with_modifications,
    apply_modifications_to_quote,
    get_approval_modifications,
    get_modifications_summary,
    get_approvals_with_modifications,
)


class TestModificationValidation:
    """Tests for validate_modifications function."""

    def test_validate_empty_modifications(self):
        """Empty dict should be valid."""
        result = validate_modifications({})
        assert result.is_valid is True
        assert result.sanitized_modifications == {} or result.sanitized_modifications is None

    def test_validate_non_dict_should_fail(self):
        """Non-dict input should fail validation."""
        result = validate_modifications("not a dict")
        assert result.is_valid is False
        assert "dictionary" in result.errors[0].lower()

    def test_validate_margin_percent_valid(self):
        """Valid margin_percent should pass."""
        result = validate_modifications({'margin_percent': 15.5})
        assert result.is_valid is True
        assert result.sanitized_modifications['margin_percent'] == 15.5

    def test_validate_margin_percent_invalid_type(self):
        """Non-numeric margin_percent should fail."""
        result = validate_modifications({'margin_percent': 'fifteen'})
        assert result.is_valid is False
        assert any('margin_percent' in e for e in result.errors)

    def test_validate_margin_percent_out_of_range(self):
        """margin_percent > 100 should fail."""
        result = validate_modifications({'margin_percent': 150})
        assert result.is_valid is False
        assert any('100' in e for e in result.errors)

    def test_validate_margin_percent_negative(self):
        """Negative margin_percent should fail."""
        result = validate_modifications({'margin_percent': -5})
        assert result.is_valid is False

    def test_validate_payment_terms_valid(self):
        """Valid payment_terms string should pass."""
        result = validate_modifications({'payment_terms': '50% advance'})
        assert result.is_valid is True
        assert result.sanitized_modifications['payment_terms'] == '50% advance'

    def test_validate_payment_terms_strips_whitespace(self):
        """Payment terms should be stripped."""
        result = validate_modifications({'payment_terms': '  50% advance  '})
        assert result.sanitized_modifications['payment_terms'] == '50% advance'

    def test_validate_unknown_field_warning(self):
        """Unknown fields should generate warnings, not errors."""
        result = validate_modifications({'unknown_field': 'value', 'margin_percent': 10})
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert 'unknown' in result.warnings[0].lower()

    def test_validate_items_valid_structure(self):
        """Valid items array should pass."""
        result = validate_modifications({
            'items': [
                {'item_id': 'uuid-1', 'sale_price': 1500.00},
                {'item_id': 'uuid-2', 'quantity': 10}
            ]
        })
        assert result.is_valid is True
        assert len(result.sanitized_modifications['items']) == 2

    def test_validate_items_missing_item_id(self):
        """Items without item_id should fail."""
        result = validate_modifications({
            'items': [
                {'sale_price': 1500.00}  # Missing item_id
            ]
        })
        assert result.is_valid is False
        assert any('item_id' in e for e in result.errors)

    def test_validate_items_invalid_sale_price(self):
        """Negative sale_price should fail."""
        result = validate_modifications({
            'items': [
                {'item_id': 'uuid-1', 'sale_price': -100}
            ]
        })
        assert result.is_valid is False

    def test_validate_items_invalid_quantity(self):
        """Zero or negative quantity should fail."""
        result = validate_modifications({
            'items': [
                {'item_id': 'uuid-1', 'quantity': 0}
            ]
        })
        assert result.is_valid is False

    def test_validate_items_not_array(self):
        """items as non-array should fail."""
        result = validate_modifications({
            'items': {'item_id': 'uuid-1'}  # Should be array
        })
        assert result.is_valid is False
        assert any('array' in e for e in result.errors)

    def test_validate_complex_modifications(self):
        """Complex valid modifications should pass."""
        result = validate_modifications({
            'margin_percent': 12.5,
            'payment_terms': '30% advance, 70% on delivery',
            'notes': 'Approved with adjustments',
            'items': [
                {'item_id': 'uuid-1', 'sale_price': 1500.00, 'notes': 'Reduced price'},
                {'item_id': 'uuid-2', 'quantity': 100}
            ]
        })
        assert result.is_valid is True
        assert result.sanitized_modifications['margin_percent'] == 12.5
        assert len(result.sanitized_modifications['items']) == 2


class TestModificationsSummary:
    """Tests for get_modifications_summary function."""

    def test_summary_empty(self):
        """Empty modifications should return 'Без изменений'."""
        result = get_modifications_summary({})
        assert result == "Без изменений"

    def test_summary_none(self):
        """None should return 'Без изменений'."""
        result = get_modifications_summary(None)
        assert result == "Без изменений"

    def test_summary_margin_only(self):
        """Margin-only modification should show margin."""
        result = get_modifications_summary({'margin_percent': 15})
        assert 'маржа' in result.lower()
        assert '15' in result

    def test_summary_payment_terms(self):
        """Payment terms modification should be mentioned."""
        result = get_modifications_summary({'payment_terms': '50% advance'})
        assert 'оплаты' in result.lower()

    def test_summary_items_count(self):
        """Items modifications should show count."""
        result = get_modifications_summary({
            'items': [
                {'item_id': 'a', 'sale_price': 100},
                {'item_id': 'b', 'sale_price': 200}
            ]
        })
        assert '2' in result
        assert 'позиц' in result.lower()

    def test_summary_multiple_modifications(self):
        """Multiple modifications should all be mentioned."""
        result = get_modifications_summary({
            'margin_percent': 10,
            'payment_terms': '100% advance',
            'items': [{'item_id': 'a', 'sale_price': 100}]
        })
        assert 'маржа' in result.lower()
        assert 'оплаты' in result.lower()
        assert '1' in result

    def test_summary_notes_only(self):
        """Notes-only should show truncated notes."""
        result = get_modifications_summary({
            'notes': 'This is a very long note that explains the approval decision in detail'
        })
        assert 'примечание' in result.lower()


class TestApprovalWithModificationsResult:
    """Tests for ApprovalWithModificationsResult dataclass."""

    def test_result_success(self):
        """Success result should have expected fields."""
        result = ApprovalWithModificationsResult(
            success=True,
            approval_id='approval-uuid',
            quote_id='quote-uuid',
            modifications_applied=True,
            items_modified=2,
            new_status='approved'
        )
        assert result.success is True
        assert result.items_modified == 2
        assert result.error_message is None

    def test_result_failure(self):
        """Failure result should have error message."""
        result = ApprovalWithModificationsResult(
            success=False,
            approval_id='approval-uuid',
            quote_id=None,
            modifications_applied=False,
            items_modified=0,
            new_status=None,
            error_message="Approval not found"
        )
        assert result.success is False
        assert result.error_message == "Approval not found"


class TestApproveWithModifications:
    """Tests for approve_with_modifications function."""

    def test_invalid_modifications_should_fail(self):
        """Invalid modifications structure should fail early."""
        result = approve_with_modifications(
            approval_id='approval-uuid',
            modifications={'margin_percent': 'invalid'}
        )
        assert result.success is False
        assert 'Invalid modifications' in result.error_message

    @patch('services.approval_service.get_approval')
    def test_approval_not_found(self, mock_get):
        """Missing approval should fail."""
        mock_get.return_value = None

        result = approve_with_modifications(
            approval_id='nonexistent-uuid',
            modifications={'margin_percent': 15}
        )
        assert result.success is False
        assert 'не найден' in result.error_message.lower()

    @patch('services.approval_service.get_approval')
    def test_already_processed_approval(self, mock_get):
        """Already processed approval should fail."""
        mock_approval = Approval(
            id='approval-uuid',
            quote_id='quote-uuid',
            requested_by='user-uuid',
            approver_id='manager-uuid',
            approval_type='top_manager',
            reason='Test',
            status='approved',  # Already processed
            decision_comment=None,
            requested_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc)
        )
        mock_get.return_value = mock_approval

        result = approve_with_modifications(
            approval_id='approval-uuid',
            modifications={'margin_percent': 15}
        )
        assert result.success is False
        assert 'обработан' in result.error_message.lower()


class TestApplyModificationsResult:
    """Tests for ApplyModificationsResult dataclass."""

    def test_result_success(self):
        """Success result should have expected fields."""
        result = ApplyModificationsResult(
            success=True,
            quote_id='quote-uuid',
            fields_updated=['margin_percent', 'payment_terms'],
            items_modified=3,
            errors=[]
        )
        assert result.success is True
        assert len(result.fields_updated) == 2
        assert result.items_modified == 3

    def test_result_with_errors(self):
        """Result with errors should report them."""
        result = ApplyModificationsResult(
            success=False,
            quote_id='quote-uuid',
            fields_updated=['margin_percent'],
            items_modified=0,
            errors=['Failed to update item uuid-1']
        )
        assert result.success is False
        assert len(result.errors) == 1


class TestAllowedModifications:
    """Tests for allowed modification constants."""

    def test_quote_modifications_list(self):
        """ALLOWED_QUOTE_MODIFICATIONS should be a non-empty list."""
        assert isinstance(ALLOWED_QUOTE_MODIFICATIONS, list)
        assert len(ALLOWED_QUOTE_MODIFICATIONS) > 0
        assert 'margin_percent' in ALLOWED_QUOTE_MODIFICATIONS
        assert 'payment_terms' in ALLOWED_QUOTE_MODIFICATIONS

    def test_item_modifications_list(self):
        """ALLOWED_ITEM_MODIFICATIONS should be a non-empty list."""
        assert isinstance(ALLOWED_ITEM_MODIFICATIONS, list)
        assert len(ALLOWED_ITEM_MODIFICATIONS) > 0
        assert 'sale_price' in ALLOWED_ITEM_MODIFICATIONS
        assert 'quantity' in ALLOWED_ITEM_MODIFICATIONS


class TestModificationValidationResult:
    """Tests for ModificationValidationResult dataclass."""

    def test_valid_result(self):
        """Valid result should have no errors."""
        result = ModificationValidationResult(
            is_valid=True,
            errors=[],
            warnings=['Unknown field ignored'],
            sanitized_modifications={'margin_percent': 15}
        )
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_invalid_result(self):
        """Invalid result should have errors."""
        result = ModificationValidationResult(
            is_valid=False,
            errors=['margin_percent must be a number'],
            warnings=[],
            sanitized_modifications=None
        )
        assert result.is_valid is False
        assert len(result.errors) > 0


# =============================================================================
# IMPORTS FOR NEW EXPORTS TESTS
# =============================================================================

class TestNewExports:
    """Tests to verify new v3.0 exports are available."""

    def test_import_modification_result_classes(self):
        """v3.0 result classes should be importable."""
        from services.approval_service import (
            ModificationValidationResult,
            ApprovalWithModificationsResult,
            ApplyModificationsResult
        )
        assert ModificationValidationResult is not None
        assert ApprovalWithModificationsResult is not None
        assert ApplyModificationsResult is not None

    def test_import_modification_constants(self):
        """v3.0 constants should be importable."""
        from services.approval_service import (
            ALLOWED_QUOTE_MODIFICATIONS,
            ALLOWED_ITEM_MODIFICATIONS
        )
        assert isinstance(ALLOWED_QUOTE_MODIFICATIONS, list)
        assert isinstance(ALLOWED_ITEM_MODIFICATIONS, list)

    def test_import_modification_functions(self):
        """v3.0 functions should be importable."""
        from services.approval_service import (
            validate_modifications,
            approve_with_modifications,
            apply_modifications_to_quote,
            get_approval_modifications,
            get_modifications_summary,
            get_approvals_with_modifications
        )
        assert all(callable(f) for f in [
            validate_modifications,
            approve_with_modifications,
            apply_modifications_to_quote,
            get_approval_modifications,
            get_modifications_summary,
            get_approvals_with_modifications
        ])

    def test_import_from_services_init(self):
        """New exports should be available from services package."""
        from services import (
            ModificationValidationResult,
            ApprovalWithModificationsResult,
            ApplyModificationsResult,
            ALLOWED_QUOTE_MODIFICATIONS,
            ALLOWED_ITEM_MODIFICATIONS,
            validate_modifications,
            approve_with_modifications,
            get_modifications_summary
        )
        assert validate_modifications is not None
        assert approve_with_modifications is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
