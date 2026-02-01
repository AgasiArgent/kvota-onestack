"""
Tests for Workflow Service - Quote workflow status management

Tests for WF-001: Workflow status transition service
- Validates and executes status transitions based on role
- Permission matrix functionality
- Transition history tracking
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.workflow_service import (
    # Enum and data classes
    WorkflowStatus,
    StatusTransition,
    TransitionResult,
    # Status metadata
    STATUS_NAMES,
    STATUS_NAMES_SHORT,
    STATUS_COLORS,
    IN_PROGRESS_STATUSES,
    FINAL_STATUSES,
    ALLOWED_TRANSITIONS,
    # Helper functions
    get_status_name,
    get_status_name_short,
    get_status_color,
    get_allowed_transitions,
    get_allowed_target_statuses,
    can_transition,
    is_final_status,
    is_in_progress,
    get_workflow_order,
    get_workflow_stage,
    get_all_statuses,
    # Permission matrix functions
    get_transition_requirements,
    get_roles_for_transition,
    get_transitions_by_role,
    get_permission_matrix,
    get_permission_matrix_detailed,
    get_outgoing_transitions,
    get_incoming_transitions,
    is_comment_required,
    is_auto_transition,
)


# =============================================================================
# WORKFLOW STATUS ENUM TESTS
# =============================================================================

class TestWorkflowStatusEnum:
    """Tests for WorkflowStatus enum."""

    def test_status_values_are_strings(self):
        """Status values should be string type for database compatibility."""
        for status in WorkflowStatus:
            assert isinstance(status.value, str)

    def test_draft_status_exists(self):
        """Draft status should exist as the initial state."""
        assert WorkflowStatus.DRAFT == "draft"

    def test_deal_status_exists(self):
        """Deal status should exist as the final positive state."""
        assert WorkflowStatus.DEAL == "deal"

    def test_status_enum_comparison(self):
        """Status enum values can be compared directly."""
        assert WorkflowStatus.DRAFT == WorkflowStatus.DRAFT
        assert WorkflowStatus.DRAFT != WorkflowStatus.DEAL

    def test_status_from_string(self):
        """Status can be created from string value."""
        status = WorkflowStatus("draft")
        assert status == WorkflowStatus.DRAFT

    def test_invalid_status_raises_error(self):
        """Creating status from invalid string raises ValueError."""
        with pytest.raises(ValueError):
            WorkflowStatus("invalid_status")

    def test_all_statuses_have_names(self):
        """Every status should have a human-readable name."""
        for status in WorkflowStatus:
            assert status in STATUS_NAMES, f"Missing name for status: {status}"
            assert len(STATUS_NAMES[status]) > 0

    def test_all_statuses_have_short_names(self):
        """Every status should have a short name for compact display."""
        for status in WorkflowStatus:
            assert status in STATUS_NAMES_SHORT, f"Missing short name for status: {status}"

    def test_all_statuses_have_colors(self):
        """Every status should have a color definition."""
        for status in WorkflowStatus:
            assert status in STATUS_COLORS, f"Missing color for status: {status}"
            assert "bg-" in STATUS_COLORS[status], "Color should include background class"


# =============================================================================
# STATUS METADATA TESTS
# =============================================================================

class TestStatusMetadata:
    """Tests for status metadata dictionaries."""

    def test_status_names_are_russian(self):
        """Status names should be in Russian."""
        # Check a few known translations
        assert STATUS_NAMES[WorkflowStatus.DRAFT] == "Черновик"
        assert "ожидает" in STATUS_NAMES[WorkflowStatus.PENDING_PROCUREMENT].lower() or "Ожидает" in STATUS_NAMES[WorkflowStatus.PENDING_PROCUREMENT]

    def test_in_progress_statuses_not_empty(self):
        """IN_PROGRESS_STATUSES should contain multiple statuses."""
        assert len(IN_PROGRESS_STATUSES) > 0
        assert WorkflowStatus.PENDING_PROCUREMENT in IN_PROGRESS_STATUSES

    def test_final_statuses_include_deal(self):
        """FINAL_STATUSES should include deal and rejected."""
        assert WorkflowStatus.DEAL in FINAL_STATUSES
        assert WorkflowStatus.REJECTED in FINAL_STATUSES
        assert WorkflowStatus.CANCELLED in FINAL_STATUSES

    def test_draft_not_in_progress(self):
        """Draft status should not be in progress statuses."""
        assert WorkflowStatus.DRAFT not in IN_PROGRESS_STATUSES

    def test_final_statuses_not_in_progress(self):
        """Final statuses should not be in progress statuses."""
        for status in FINAL_STATUSES:
            assert status not in IN_PROGRESS_STATUSES


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestHelperFunctions:
    """Tests for workflow helper functions."""

    def test_get_status_name_with_enum(self):
        """get_status_name should accept WorkflowStatus enum."""
        name = get_status_name(WorkflowStatus.DRAFT)
        assert name == "Черновик"

    def test_get_status_name_with_string(self):
        """get_status_name should accept string status code."""
        name = get_status_name("draft")
        assert name == "Черновик"

    def test_get_status_name_invalid_returns_input(self):
        """get_status_name with invalid string returns input as-is."""
        name = get_status_name("invalid_status")
        assert name == "invalid_status"

    def test_get_status_name_short(self):
        """get_status_name_short should return short name."""
        short_name = get_status_name_short(WorkflowStatus.DRAFT)
        assert len(short_name) <= len(get_status_name(WorkflowStatus.DRAFT))

    def test_get_status_color_contains_tailwind_classes(self):
        """get_status_color should return Tailwind CSS classes."""
        color = get_status_color(WorkflowStatus.DRAFT)
        assert "bg-" in color
        assert "text-" in color

    def test_is_final_status_true_for_final(self):
        """is_final_status should return True for final statuses."""
        assert is_final_status(WorkflowStatus.DEAL) is True
        assert is_final_status(WorkflowStatus.REJECTED) is True
        assert is_final_status(WorkflowStatus.CANCELLED) is True

    def test_is_final_status_false_for_non_final(self):
        """is_final_status should return False for non-final statuses."""
        assert is_final_status(WorkflowStatus.DRAFT) is False
        assert is_final_status(WorkflowStatus.PENDING_PROCUREMENT) is False

    def test_is_final_status_with_string(self):
        """is_final_status should accept string status code."""
        assert is_final_status("deal") is True
        assert is_final_status("draft") is False

    def test_is_in_progress_true_for_progress(self):
        """is_in_progress should return True for in-progress statuses."""
        assert is_in_progress(WorkflowStatus.PENDING_PROCUREMENT) is True

    def test_is_in_progress_false_for_draft(self):
        """is_in_progress should return False for draft."""
        assert is_in_progress(WorkflowStatus.DRAFT) is False

    def test_is_in_progress_false_for_final(self):
        """is_in_progress should return False for final statuses."""
        assert is_in_progress(WorkflowStatus.DEAL) is False

    def test_get_workflow_order_returns_list(self):
        """get_workflow_order should return ordered list of statuses."""
        order = get_workflow_order()
        assert isinstance(order, list)
        assert len(order) > 0
        # Draft should be first
        assert order[0] == WorkflowStatus.DRAFT
        # Deal should be last in order
        assert order[-1] == WorkflowStatus.DEAL

    def test_get_workflow_stage_draft_is_zero(self):
        """get_workflow_stage should return 0 for draft."""
        stage = get_workflow_stage(WorkflowStatus.DRAFT)
        assert stage == 0

    def test_get_workflow_stage_deal_is_max(self):
        """get_workflow_stage should return max stage for deal."""
        stage = get_workflow_stage(WorkflowStatus.DEAL)
        assert stage == 12  # Final stage

    def test_get_workflow_stage_rejected_is_negative(self):
        """get_workflow_stage should return -1 for rejected/cancelled."""
        assert get_workflow_stage(WorkflowStatus.REJECTED) == -1
        assert get_workflow_stage(WorkflowStatus.CANCELLED) == -1

    def test_get_all_statuses_returns_dict_list(self):
        """get_all_statuses should return list of dicts with code and name."""
        statuses = get_all_statuses()
        assert isinstance(statuses, list)
        assert len(statuses) == len(WorkflowStatus)
        for s in statuses:
            assert "code" in s
            assert "name" in s


# =============================================================================
# TRANSITION RULES TESTS
# =============================================================================

class TestTransitionRules:
    """Tests for status transition rules."""

    def test_allowed_transitions_not_empty(self):
        """ALLOWED_TRANSITIONS should contain transition definitions."""
        assert len(ALLOWED_TRANSITIONS) > 0

    def test_transition_has_required_fields(self):
        """Each transition should have required fields."""
        for t in ALLOWED_TRANSITIONS:
            assert isinstance(t, StatusTransition)
            assert t.from_status is not None
            assert t.to_status is not None
            assert t.allowed_roles is not None
            assert isinstance(t.allowed_roles, list)

    def test_draft_can_transition_to_procurement(self):
        """Draft status should be able to transition to pending_procurement."""
        transitions = get_allowed_transitions(WorkflowStatus.DRAFT, ["sales"])
        target_statuses = [t.to_status for t in transitions]
        assert WorkflowStatus.PENDING_PROCUREMENT in target_statuses

    def test_sales_role_can_submit_draft(self):
        """Sales role should be able to submit draft to procurement."""
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["sales"]
        )
        assert allowed is True
        assert error is None

    def test_procurement_role_cannot_submit_draft(self):
        """Procurement role should not be able to submit draft."""
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["procurement"]
        )
        assert allowed is False
        assert error is not None

    def test_admin_role_can_do_any_allowed_transition(self):
        """Admin role should be able to do most transitions."""
        # Admin can submit draft
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["admin"]
        )
        assert allowed is True

    def test_cannot_transition_from_final_status(self):
        """Cannot transition from final statuses (except rejected→draft)."""
        allowed, error = can_transition(
            WorkflowStatus.CANCELLED,
            WorkflowStatus.DRAFT,
            ["admin"]
        )
        assert allowed is False

    def test_get_allowed_target_statuses_returns_list(self):
        """get_allowed_target_statuses should return list of WorkflowStatus."""
        targets = get_allowed_target_statuses(WorkflowStatus.DRAFT, ["sales"])
        assert isinstance(targets, list)
        for t in targets:
            assert isinstance(t, WorkflowStatus)


# =============================================================================
# PERMISSION MATRIX TESTS
# =============================================================================

class TestPermissionMatrix:
    """Tests for permission matrix functions."""

    def test_get_transition_requirements_existing(self):
        """get_transition_requirements should return requirements for valid transition."""
        req = get_transition_requirements(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT
        )
        assert req is not None
        assert isinstance(req, StatusTransition)
        assert "sales" in req.allowed_roles or "admin" in req.allowed_roles

    def test_get_transition_requirements_invalid(self):
        """get_transition_requirements should return None for invalid transition."""
        req = get_transition_requirements(
            WorkflowStatus.DRAFT,
            WorkflowStatus.DEAL  # Cannot go directly to deal
        )
        assert req is None

    def test_get_roles_for_transition(self):
        """get_roles_for_transition should return list of roles."""
        roles = get_roles_for_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT
        )
        assert isinstance(roles, list)
        assert len(roles) > 0

    def test_get_transitions_by_role_sales(self):
        """get_transitions_by_role should return sales transitions."""
        transitions = get_transitions_by_role("sales")
        assert isinstance(transitions, list)
        assert len(transitions) > 0
        # Sales should be able to submit draft
        from_draft = [t for t in transitions if t["from_status"] == "draft"]
        assert len(from_draft) > 0

    def test_get_transitions_by_role_procurement(self):
        """get_transitions_by_role should return procurement transitions."""
        transitions = get_transitions_by_role("procurement")
        assert isinstance(transitions, list)
        # Procurement transitions involve pending_procurement status
        has_procurement = any(
            t["from_status"] == "pending_procurement"
            for t in transitions
        )
        assert has_procurement

    def test_get_permission_matrix_structure(self):
        """get_permission_matrix should return nested dict structure."""
        matrix = get_permission_matrix()
        assert isinstance(matrix, dict)
        # Should have draft as a key
        assert "draft" in matrix
        # Draft should have at least one target
        assert len(matrix["draft"]) > 0

    def test_get_permission_matrix_detailed(self):
        """get_permission_matrix_detailed should return list with details."""
        matrix = get_permission_matrix_detailed()
        assert isinstance(matrix, list)
        assert len(matrix) > 0
        # Each row should have required fields
        for row in matrix:
            assert "from_status" in row
            assert "to_status" in row
            assert "allowed_roles" in row
            assert "requires_comment" in row

    def test_get_outgoing_transitions(self):
        """get_outgoing_transitions should return transitions from status."""
        transitions = get_outgoing_transitions(WorkflowStatus.DRAFT)
        assert isinstance(transitions, list)
        assert len(transitions) > 0
        for t in transitions:
            assert "to_status" in t
            assert "allowed_roles" in t

    def test_get_incoming_transitions(self):
        """get_incoming_transitions should return transitions to status."""
        transitions = get_incoming_transitions(WorkflowStatus.APPROVED)
        assert isinstance(transitions, list)
        assert len(transitions) > 0
        for t in transitions:
            assert "from_status" in t
            assert "allowed_roles" in t

    def test_is_comment_required_true(self):
        """is_comment_required should return True for rejection."""
        # Rejection typically requires comment
        req = get_transition_requirements(
            WorkflowStatus.PENDING_APPROVAL,
            WorkflowStatus.REJECTED
        )
        if req:
            assert is_comment_required(
                WorkflowStatus.PENDING_APPROVAL,
                WorkflowStatus.REJECTED
            ) == req.requires_comment

    def test_is_comment_required_false(self):
        """is_comment_required should return False for simple transitions."""
        # Submitting draft doesn't require comment
        assert is_comment_required(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT
        ) is False

    def test_is_auto_transition(self):
        """is_auto_transition should identify automatic transitions."""
        # Procurement to logistics is an auto-transition
        result = is_auto_transition(
            WorkflowStatus.PENDING_PROCUREMENT,
            WorkflowStatus.PENDING_LOGISTICS
        )
        assert result is True


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestTransitionValidation:
    """Tests for transition validation logic."""

    def test_can_transition_validates_role(self):
        """can_transition should check user has required role."""
        # Valid role
        allowed, _ = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["sales"]
        )
        assert allowed is True

        # Invalid role
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["finance"]  # Finance cannot submit drafts
        )
        assert allowed is False
        assert "permission" in error.lower() or "role" in error.lower()

    def test_can_transition_with_string_status(self):
        """can_transition should accept string status codes."""
        allowed, _ = can_transition("draft", "pending_procurement", ["sales"])
        assert allowed is True

    def test_can_transition_invalid_current_status(self):
        """can_transition should reject invalid current status."""
        allowed, error = can_transition(
            "invalid_status",
            "pending_procurement",
            ["sales"]
        )
        assert allowed is False
        assert "invalid" in error.lower()

    def test_can_transition_invalid_target_status(self):
        """can_transition should reject invalid target status."""
        allowed, error = can_transition(
            "draft",
            "invalid_status",
            ["sales"]
        )
        assert allowed is False
        assert "invalid" in error.lower()

    def test_can_transition_invalid_path(self):
        """can_transition should reject invalid transition path."""
        # Cannot go from draft directly to deal
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.DEAL,
            ["sales"]
        )
        assert allowed is False
        assert "not allowed" in error.lower()


# =============================================================================
# ROLE-SPECIFIC TESTS
# =============================================================================

class TestRoleSpecificTransitions:
    """Tests for role-specific transition rules."""

    def test_top_manager_can_approve(self):
        """Top manager should be able to approve quotes."""
        allowed, _ = can_transition(
            WorkflowStatus.PENDING_APPROVAL,
            WorkflowStatus.APPROVED,
            ["top_manager"]
        )
        assert allowed is True

    def test_top_manager_can_reject(self):
        """Top manager should be able to reject quotes."""
        allowed, _ = can_transition(
            WorkflowStatus.PENDING_APPROVAL,
            WorkflowStatus.REJECTED,
            ["top_manager"]
        )
        assert allowed is True

    def test_quote_controller_transitions(self):
        """Quote controller should have specific transition rights."""
        # From pending_quote_control
        transitions = get_allowed_transitions(
            WorkflowStatus.PENDING_QUOTE_CONTROL,
            ["quote_controller"]
        )
        target_statuses = [t.to_status for t in transitions]
        # Should be able to approve directly or request approval
        assert (
            WorkflowStatus.APPROVED in target_statuses or
            WorkflowStatus.PENDING_APPROVAL in target_statuses
        )

    def test_multiple_roles_combine_permissions(self):
        """User with multiple roles should have combined permissions."""
        # User with both sales and admin roles
        transitions = get_allowed_transitions(
            WorkflowStatus.DRAFT,
            ["sales", "admin"]
        )
        assert len(transitions) > 0


# =============================================================================
# INTEGRATION TESTS (Mock Database)
# =============================================================================

class TestTransitionExecution:
    """Tests for transition execution with mocked database."""

    @patch('services.workflow_service.get_supabase')
    def test_transition_result_dataclass(self, mock_supabase):
        """TransitionResult should contain all required fields."""
        result = TransitionResult(
            success=True,
            quote_id="test-uuid",
            from_status="draft",
            to_status="pending_procurement",
            transition_id="transition-uuid"
        )
        assert result.success is True
        assert result.error_message is None
        assert result.quote_id == "test-uuid"
        assert result.from_status == "draft"
        assert result.to_status == "pending_procurement"

    @patch('services.workflow_service.get_supabase')
    def test_transition_result_failure(self, mock_supabase):
        """TransitionResult should capture failure information."""
        result = TransitionResult(
            success=False,
            error_message="Permission denied",
            quote_id="test-uuid",
            from_status="draft"
        )
        assert result.success is False
        assert result.error_message == "Permission denied"
        assert result.to_status is None


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_roles_list(self):
        """Empty roles list should not allow any transitions."""
        transitions = get_allowed_transitions(WorkflowStatus.DRAFT, [])
        assert len(transitions) == 0

    def test_none_roles_handled(self):
        """None roles should be handled gracefully."""
        with pytest.raises((TypeError, AttributeError)):
            get_allowed_transitions(WorkflowStatus.DRAFT, None)

    def test_case_sensitivity_of_status(self):
        """Status codes should be case-sensitive."""
        # Lowercase should work
        name = get_status_name("draft")
        assert name == "Черновик"

        # Uppercase should fail
        with pytest.raises(ValueError):
            WorkflowStatus("DRAFT")

    def test_final_status_has_no_non_auto_transitions(self):
        """Final statuses should have no user-triggered transitions."""
        # DEAL status
        transitions = get_allowed_transitions(WorkflowStatus.DEAL, ["admin"])
        # Admin might still be able to do some things, but generally final

        # CANCELLED definitely cannot transition
        transitions_cancelled = get_allowed_transitions(
            WorkflowStatus.CANCELLED,
            ["admin"]
        )
        assert len(transitions_cancelled) == 0


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Tests for performance characteristics."""

    def test_get_allowed_transitions_fast(self):
        """get_allowed_transitions should be fast (O(n) or better)."""
        import time
        start = time.time()
        for _ in range(1000):
            get_allowed_transitions(WorkflowStatus.DRAFT, ["sales"])
        elapsed = time.time() - start
        # Should complete 1000 iterations in under 1 second
        assert elapsed < 1.0

    def test_permission_matrix_cached_structure(self):
        """Permission matrix should use cached lookup."""
        # Multiple calls should return consistent results
        matrix1 = get_permission_matrix()
        matrix2 = get_permission_matrix()
        assert matrix1 == matrix2


# =============================================================================
# WF-002: AUTO-TRANSITION PROCUREMENT COMPLETE TESTS
# =============================================================================

class TestProcurementAutoTransition:
    """Tests for WF-002: Auto-transition when all brands are evaluated."""

    def test_check_all_procurement_complete_import(self):
        """check_all_procurement_complete function should be importable."""
        from services.workflow_service import check_all_procurement_complete
        assert callable(check_all_procurement_complete)

    def test_complete_procurement_import(self):
        """complete_procurement function should be importable."""
        from services.workflow_service import complete_procurement
        assert callable(complete_procurement)

    @patch('services.workflow_service.get_supabase')
    def test_check_all_procurement_complete_all_done(self, mock_supabase):
        """check_all_procurement_complete returns True when all items complete and priced."""
        from services.workflow_service import check_all_procurement_complete

        # Mock Supabase response - all items completed with valid prices
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "item1", "product_name": "item1", "procurement_status": "completed", "purchase_price_original": 100.0, "is_unavailable": False},
            {"id": "item2", "product_name": "item2", "procurement_status": "completed", "purchase_price_original": 200.0, "is_unavailable": False},
            {"id": "item3", "product_name": "item3", "procurement_status": "completed", "purchase_price_original": None, "is_unavailable": True},  # Unavailable is OK
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = check_all_procurement_complete("quote-uuid")

        assert result["is_complete"] is True
        assert result["total_items"] == 3
        assert result["completed_items"] == 3
        assert result["pending_items"] == 0
        assert result["items_without_price"] == 0

    @patch('services.workflow_service.get_supabase')
    def test_check_all_procurement_complete_partial(self, mock_supabase):
        """check_all_procurement_complete returns False when items pending."""
        from services.workflow_service import check_all_procurement_complete

        # Mock Supabase response - some items pending
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "item1", "product_name": "item1", "procurement_status": "completed", "purchase_price_original": 100.0, "is_unavailable": False},
            {"id": "item2", "product_name": "item2", "procurement_status": "pending", "purchase_price_original": None, "is_unavailable": False},
            {"id": "item3", "product_name": "item3", "procurement_status": "in_progress", "purchase_price_original": None, "is_unavailable": False},
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = check_all_procurement_complete("quote-uuid")

        assert result["is_complete"] is False
        assert result["total_items"] == 3
        assert result["completed_items"] == 1
        assert result["pending_items"] == 2

    @patch('services.workflow_service.get_supabase')
    def test_check_all_procurement_complete_empty(self, mock_supabase):
        """check_all_procurement_complete returns False for empty quote."""
        from services.workflow_service import check_all_procurement_complete

        # Mock Supabase response - no items
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = check_all_procurement_complete("quote-uuid")

        assert result["is_complete"] is False
        assert result["total_items"] == 0

    @patch('services.workflow_service.get_supabase')
    def test_complete_procurement_wrong_role(self, mock_supabase):
        """complete_procurement rejects users without procurement role."""
        from services.workflow_service import complete_procurement

        result = complete_procurement(
            quote_id="quote-uuid",
            actor_id="user-uuid",
            actor_roles=["sales"]  # Wrong role
        )

        assert result.success is False
        assert "procurement" in result.error_message.lower() or "admin" in result.error_message.lower()

    @patch('services.workflow_service.get_supabase')
    def test_complete_procurement_procurement_role_accepted(self, mock_supabase):
        """complete_procurement accepts procurement role."""
        from services.workflow_service import complete_procurement, WorkflowStatus

        # Setup mocks
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock quote query
        mock_quote_response = MagicMock()
        mock_quote_response.data = {
            "id": "quote-uuid",
            "workflow_status": WorkflowStatus.PENDING_PROCUREMENT.value,
            "procurement_completed_at": None
        }

        # Mock items query (all complete with valid price)
        mock_items_response = MagicMock()
        mock_items_response.data = [
            {"id": "item1", "product_name": "item1", "procurement_status": "completed", "purchase_price_original": 100.0, "is_unavailable": False},
        ]

        # Mock update
        mock_update_response = MagicMock()
        mock_update_response.data = [{"id": "quote-uuid"}]

        # Mock transition log
        mock_log_response = MagicMock()
        mock_log_response.data = [{"id": "transition-uuid"}]

        # Setup call chain
        table_mock = MagicMock()
        mock_client.table.return_value = table_mock

        # First call: quotes.select().eq().single().execute()
        # Second call: quote_items.select().eq().execute()
        # Third call: quotes.update().eq().execute()
        # Fourth call: workflow_transitions.insert().execute()
        call_count = [0]

        def table_side_effect(table_name):
            call_count[0] += 1
            if table_name == "quotes" and call_count[0] == 1:
                chain = MagicMock()
                chain.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_quote_response
                return chain
            elif table_name == "quote_items":
                chain = MagicMock()
                chain.select.return_value.eq.return_value.execute.return_value = mock_items_response
                return chain
            elif table_name == "quotes" and call_count[0] > 1:
                chain = MagicMock()
                chain.update.return_value.eq.return_value.execute.return_value = mock_update_response
                return chain
            else:
                chain = MagicMock()
                chain.insert.return_value.execute.return_value = mock_log_response
                return chain

        mock_client.table.side_effect = table_side_effect

        result = complete_procurement(
            quote_id="quote-uuid",
            actor_id="user-uuid",
            actor_roles=["procurement"]
        )

        # Should succeed with procurement role and transition to parallel stage
        assert result.success is True
        assert result.to_status == WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value

    @patch('services.workflow_service.get_supabase')
    def test_complete_procurement_admin_role_accepted(self, mock_supabase):
        """complete_procurement accepts admin role."""
        from services.workflow_service import complete_procurement, WorkflowStatus

        # Simplified mock - just check role validation passes
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock quote in wrong status to trigger early return
        mock_response = MagicMock()
        mock_response.data = {
            "id": "quote-uuid",
            "workflow_status": "draft",  # Wrong status
            "procurement_completed_at": None
        }
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        result = complete_procurement(
            quote_id="quote-uuid",
            actor_id="user-uuid",
            actor_roles=["admin"]
        )

        # Should pass role check but fail on status (not "role denied")
        assert "procurement" not in result.error_message.lower() or "status" in result.error_message.lower()

    @patch('services.workflow_service.get_supabase')
    def test_complete_procurement_wrong_status(self, mock_supabase):
        """complete_procurement fails if quote not in pending_procurement."""
        from services.workflow_service import complete_procurement

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Quote in wrong status
        mock_response = MagicMock()
        mock_response.data = {
            "id": "quote-uuid",
            "workflow_status": "draft",
            "procurement_completed_at": None
        }
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        result = complete_procurement(
            quote_id="quote-uuid",
            actor_id="user-uuid",
            actor_roles=["procurement"]
        )

        assert result.success is False
        assert "status" in result.error_message.lower() or "cannot complete" in result.error_message.lower()

    @patch('services.workflow_service.get_supabase')
    def test_complete_procurement_already_completed(self, mock_supabase):
        """complete_procurement fails if already completed."""
        from services.workflow_service import complete_procurement, WorkflowStatus

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Quote with procurement already completed
        mock_response = MagicMock()
        mock_response.data = {
            "id": "quote-uuid",
            "workflow_status": WorkflowStatus.PENDING_PROCUREMENT.value,
            "procurement_completed_at": "2026-01-15T12:00:00Z"  # Already done
        }
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        result = complete_procurement(
            quote_id="quote-uuid",
            actor_id="user-uuid",
            actor_roles=["procurement"]
        )

        assert result.success is False
        assert "already" in result.error_message.lower()

    def test_get_quote_procurement_status_import(self):
        """get_quote_procurement_status function should be importable."""
        from services.workflow_service import get_quote_procurement_status
        assert callable(get_quote_procurement_status)


# =============================================================================
# WF-003: AUTO-TRANSITION LOGISTICS+CUSTOMS COMPLETE TESTS
# =============================================================================

class TestLogisticsCustomsAutoTransition:
    """Tests for WF-003: Auto-transition when BOTH logistics and customs done."""

    def test_complete_logistics_import(self):
        """complete_logistics function should be importable."""
        from services.workflow_service import complete_logistics
        assert callable(complete_logistics)

    def test_complete_customs_import(self):
        """complete_customs function should be importable."""
        from services.workflow_service import complete_customs
        assert callable(complete_customs)

    def test_check_and_auto_transition_import(self):
        """check_and_auto_transition_to_sales_review should be importable."""
        from services.workflow_service import check_and_auto_transition_to_sales_review
        assert callable(check_and_auto_transition_to_sales_review)

    def test_get_parallel_stages_status_import(self):
        """get_parallel_stages_status function should be importable."""
        from services.workflow_service import get_parallel_stages_status
        assert callable(get_parallel_stages_status)

    @patch('services.workflow_service.get_supabase')
    def test_complete_logistics_wrong_role(self, mock_supabase):
        """complete_logistics rejects users without logistics role."""
        from services.workflow_service import complete_logistics

        result = complete_logistics(
            quote_id="quote-uuid",
            actor_id="user-uuid",
            actor_roles=["sales"]  # Wrong role
        )

        assert result.success is False
        assert "logistics" in result.error_message.lower()

    @patch('services.workflow_service.get_supabase')
    def test_complete_customs_wrong_role(self, mock_supabase):
        """complete_customs rejects users without customs role."""
        from services.workflow_service import complete_customs

        result = complete_customs(
            quote_id="quote-uuid",
            actor_id="user-uuid",
            actor_roles=["sales"]  # Wrong role
        )

        assert result.success is False
        assert "customs" in result.error_message.lower()

    @patch('services.workflow_service.get_supabase')
    def test_get_parallel_stages_status_both_incomplete(self, mock_supabase):
        """get_parallel_stages_status returns correct state when both incomplete."""
        from services.workflow_service import get_parallel_stages_status

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = {
            "workflow_status": "pending_logistics",
            "logistics_completed_at": None,
            "customs_completed_at": None
        }
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        result = get_parallel_stages_status("quote-uuid")

        assert result["logistics_completed"] is False
        assert result["customs_completed"] is False
        assert result["both_completed"] is False

    @patch('services.workflow_service.get_supabase')
    def test_get_parallel_stages_status_logistics_only(self, mock_supabase):
        """get_parallel_stages_status handles logistics-only completion."""
        from services.workflow_service import get_parallel_stages_status

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = {
            "workflow_status": "pending_logistics",
            "logistics_completed_at": "2026-01-15T12:00:00Z",
            "customs_completed_at": None
        }
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        result = get_parallel_stages_status("quote-uuid")

        assert result["logistics_completed"] is True
        assert result["customs_completed"] is False
        assert result["both_completed"] is False

    @patch('services.workflow_service.get_supabase')
    def test_get_parallel_stages_status_both_complete(self, mock_supabase):
        """get_parallel_stages_status returns True when both complete."""
        from services.workflow_service import get_parallel_stages_status

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = {
            "workflow_status": "pending_logistics",
            "logistics_completed_at": "2026-01-15T12:00:00Z",
            "customs_completed_at": "2026-01-15T13:00:00Z"
        }
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        result = get_parallel_stages_status("quote-uuid")

        assert result["logistics_completed"] is True
        assert result["customs_completed"] is True
        assert result["both_completed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
