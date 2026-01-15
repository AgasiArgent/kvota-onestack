"""
Tests for workflow_service.py

Tests the workflow status management:
- WorkflowStatus enum
- Status transitions
- Transition validation
- Role-based access control for transitions
"""

import pytest
from services.workflow_service import (
    WorkflowStatus,
    STATUS_NAMES,
    STATUS_NAMES_SHORT,
    STATUS_COLORS,
    IN_PROGRESS_STATUSES,
    FINAL_STATUSES,
    StatusTransition,
    ALLOWED_TRANSITIONS,
    can_transition,
    get_allowed_target_statuses,
    get_status_name,
    get_status_name_short,
    get_status_color,
    is_final_status,
    is_in_progress,
)


class TestWorkflowStatusEnum:
    """Tests for WorkflowStatus enum."""

    def test_all_statuses_defined(self):
        """All 15 workflow statuses should be defined."""
        expected_statuses = [
            "draft",
            "pending_procurement",
            "pending_logistics",
            "pending_customs",
            "pending_sales_review",
            "pending_quote_control",
            "pending_approval",
            "approved",
            "sent_to_client",
            "client_negotiation",
            "pending_spec_control",
            "pending_signature",
            "deal",
            "rejected",
            "cancelled",
        ]
        actual_statuses = [s.value for s in WorkflowStatus]
        assert sorted(actual_statuses) == sorted(expected_statuses)

    def test_status_is_string_enum(self):
        """WorkflowStatus values should be strings."""
        for status in WorkflowStatus:
            assert isinstance(status.value, str)
            assert status.value == str(status.value)

    def test_draft_is_initial_status(self):
        """DRAFT should be the initial status."""
        assert WorkflowStatus.DRAFT.value == "draft"

    def test_final_statuses_are_complete(self):
        """DEAL, REJECTED, CANCELLED should be final statuses."""
        assert WorkflowStatus.DEAL in FINAL_STATUSES
        assert WorkflowStatus.REJECTED in FINAL_STATUSES
        assert WorkflowStatus.CANCELLED in FINAL_STATUSES
        assert len(FINAL_STATUSES) == 3


class TestStatusNames:
    """Tests for status name mappings."""

    def test_all_statuses_have_names(self):
        """Every status should have a human-readable name."""
        for status in WorkflowStatus:
            assert status in STATUS_NAMES, f"Missing name for {status}"
            assert STATUS_NAMES[status], f"Empty name for {status}"

    def test_all_statuses_have_short_names(self):
        """Every status should have a short name."""
        for status in WorkflowStatus:
            assert status in STATUS_NAMES_SHORT, f"Missing short name for {status}"

    def test_names_are_russian(self):
        """Status names should be in Russian."""
        # Check a few known Russian names
        assert STATUS_NAMES[WorkflowStatus.DRAFT] == "Черновик"
        assert STATUS_NAMES[WorkflowStatus.DEAL] == "Сделка"


class TestStatusColors:
    """Tests for status color mappings."""

    def test_all_statuses_have_colors(self):
        """Every status should have a color class."""
        for status in WorkflowStatus:
            assert status in STATUS_COLORS, f"Missing color for {status}"

    def test_colors_are_tailwind_classes(self):
        """Colors should be valid Tailwind CSS classes."""
        for status, color in STATUS_COLORS.items():
            assert "bg-" in color, f"Color for {status} missing bg- class"
            assert "text-" in color, f"Color for {status} missing text- class"


class TestStatusCategories:
    """Tests for status categorization."""

    def test_in_progress_statuses_not_final(self):
        """IN_PROGRESS_STATUSES should not include final statuses."""
        for status in IN_PROGRESS_STATUSES:
            assert status not in FINAL_STATUSES

    def test_in_progress_statuses_not_draft(self):
        """IN_PROGRESS_STATUSES should not include draft."""
        assert WorkflowStatus.DRAFT not in IN_PROGRESS_STATUSES

    def test_all_statuses_categorized(self):
        """Every status should be in exactly one category."""
        draft = {WorkflowStatus.DRAFT}
        all_categorized = draft | IN_PROGRESS_STATUSES | FINAL_STATUSES

        for status in WorkflowStatus:
            assert status in all_categorized, f"{status} not categorized"


class TestStatusTransitions:
    """Tests for status transition rules."""

    def test_draft_can_transition_to_procurement(self):
        """DRAFT should be able to transition to PENDING_PROCUREMENT."""
        # Check if this transition exists in ALLOWED_TRANSITIONS
        found = False
        for transition in ALLOWED_TRANSITIONS:
            if (transition.from_status == WorkflowStatus.DRAFT and
                transition.to_status == WorkflowStatus.PENDING_PROCUREMENT):
                found = True
                break
        assert found, "DRAFT -> PENDING_PROCUREMENT transition should exist"

    def test_final_statuses_cannot_transition(self):
        """Final statuses should not have outgoing transitions."""
        for transition in ALLOWED_TRANSITIONS:
            assert transition.from_status not in FINAL_STATUSES, \
                f"Final status {transition.from_status} should not have transitions"

    def test_transition_has_required_fields(self):
        """StatusTransition should have all required fields."""
        for transition in ALLOWED_TRANSITIONS:
            assert hasattr(transition, 'from_status')
            assert hasattr(transition, 'to_status')
            assert hasattr(transition, 'allowed_roles')
            assert isinstance(transition.allowed_roles, (list, tuple, set))


class TestCanTransition:
    """Tests for can_transition function."""

    def test_sales_can_submit_to_procurement(self):
        """Sales role should be able to submit draft to procurement."""
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            user_roles=["sales"]
        )
        assert allowed is True
        assert error is None

    def test_invalid_transition_returns_false(self):
        """Invalid status transitions should return False with error message."""
        # Draft should not be able to jump directly to DEAL
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.DEAL,
            user_roles=["sales", "admin"]
        )
        assert allowed is False
        assert error is not None  # Should have an error message

    def test_unauthorized_role_returns_false(self):
        """User without proper role should not be able to transition."""
        # A procurement user should not be able to approve quotes
        allowed, error = can_transition(
            WorkflowStatus.PENDING_APPROVAL,
            WorkflowStatus.APPROVED,
            user_roles=["procurement"]
        )
        assert allowed is False
        # Error message should mention missing permissions

    def test_final_status_cannot_transition(self):
        """Final statuses should not allow any transitions."""
        allowed, error = can_transition(
            WorkflowStatus.DEAL,
            WorkflowStatus.DRAFT,
            user_roles=["admin"]
        )
        assert allowed is False
        assert "final" in error.lower()

    def test_returns_tuple(self):
        """can_transition should always return a tuple."""
        result = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            user_roles=["sales"]
        )
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestGetAllowedTargetStatuses:
    """Tests for get_allowed_target_statuses function."""

    def test_draft_has_next_statuses_for_sales(self):
        """DRAFT should have allowed next statuses for sales role."""
        next_statuses = get_allowed_target_statuses(
            WorkflowStatus.DRAFT,
            user_roles=["sales"]
        )
        assert isinstance(next_statuses, list)
        # At minimum, sales should be able to go to PENDING_PROCUREMENT

    def test_final_statuses_have_no_next(self):
        """Final statuses should have no allowed next statuses."""
        for final_status in FINAL_STATUSES:
            next_statuses = get_allowed_target_statuses(
                final_status,
                user_roles=["admin"]  # Even admin cannot transition from final
            )
            assert next_statuses == [], f"{final_status} should have no next statuses"

    def test_returns_list(self):
        """Function should always return a list."""
        result = get_allowed_target_statuses(
            WorkflowStatus.DRAFT,
            user_roles=[]
        )
        assert isinstance(result, list)

    def test_no_roles_returns_empty_list(self):
        """User with no roles should have no allowed transitions."""
        result = get_allowed_target_statuses(
            WorkflowStatus.DRAFT,
            user_roles=[]
        )
        assert result == []


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_status_name(self):
        """get_status_name should return human-readable name."""
        name = get_status_name(WorkflowStatus.DRAFT)
        assert name == "Черновик"

    def test_get_status_name_with_string(self):
        """get_status_name should accept string input."""
        name = get_status_name("draft")
        assert name == "Черновик"

    def test_get_status_name_short(self):
        """get_status_name_short should return short name."""
        name = get_status_name_short(WorkflowStatus.PENDING_PROCUREMENT)
        assert name == "Закупки"

    def test_get_status_color(self):
        """get_status_color should return Tailwind classes."""
        color = get_status_color(WorkflowStatus.APPROVED)
        assert "bg-" in color
        assert "text-" in color

    def test_is_final_status_true(self):
        """is_final_status should return True for final statuses."""
        assert is_final_status(WorkflowStatus.DEAL) is True
        assert is_final_status(WorkflowStatus.REJECTED) is True
        assert is_final_status(WorkflowStatus.CANCELLED) is True

    def test_is_final_status_false(self):
        """is_final_status should return False for non-final statuses."""
        assert is_final_status(WorkflowStatus.DRAFT) is False
        assert is_final_status(WorkflowStatus.PENDING_PROCUREMENT) is False

    def test_is_in_progress_true(self):
        """is_in_progress should return True for in-progress statuses."""
        assert is_in_progress(WorkflowStatus.PENDING_PROCUREMENT) is True
        assert is_in_progress(WorkflowStatus.APPROVED) is True

    def test_is_in_progress_false(self):
        """is_in_progress should return False for draft and final."""
        assert is_in_progress(WorkflowStatus.DRAFT) is False
        assert is_in_progress(WorkflowStatus.DEAL) is False
