"""
Tests for workflow_service sub-state machine (Phase 4c).

Tests:
- can_transition_substatus: pure logic, no DB
    - forward transitions allowed for valid roles
    - forward transition denied for wrong role
    - backward transitions allowed for valid roles
    - invalid from→to pair denied
    - from_substatus=None denied
    - wrong parent_status denied
    - admin and head_of_procurement roles work
- transition_substatus: mocked DB
    - happy path forward
    - backward without reason raises ValueError
    - backward with reason succeeds
    - quote not found raises ValueError
    - invalid transition pair raises ValueError
    - wrong role raises ValueError
    - status_history row written with correct fields
    - parent_status unchanged in history (from_status == to_status)
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.workflow_service import (
    SubStateTransition,
    PROCUREMENT_SUBSTATUS_TRANSITIONS,
    can_transition_substatus,
    transition_substatus,
)


def _mock_supabase():
    """Create a mock Supabase client with chainable table methods."""
    return MagicMock()


def _setup_quote_fetch(mock_sb, quote_data):
    """Configure the select(...).eq(...).execute() chain for fetching a quote."""
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
        [quote_data] if quote_data else []
    )


class TestCanTransitionSubstatus:
    """Pure logic tests — no DB required."""

    def test_forward_distributing_to_searching_supplier_allowed(self):
        """Procurement role can move distributing → searching_supplier."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is False

    def test_forward_searching_to_waiting_prices_allowed(self):
        """Procurement role can move searching_supplier → waiting_prices."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "searching_supplier", "waiting_prices", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is False

    def test_forward_waiting_prices_to_prices_ready_allowed(self):
        """Procurement role can move waiting_prices → prices_ready."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "waiting_prices", "prices_ready", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is False

    def test_wrong_role_denied(self):
        """Sales role cannot perform procurement sub-state transitions."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["sales"]
        )
        assert allowed is False
        assert transition is None

    def test_backward_transition_allowed_for_procurement(self):
        """Backward searching_supplier → distributing allowed (reason checked at transition_substatus)."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "searching_supplier", "distributing", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is True

    def test_backward_waiting_prices_to_searching_requires_reason(self):
        """Backward waiting_prices → searching_supplier marked requires_reason."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "waiting_prices", "searching_supplier", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is True

    def test_backward_prices_ready_to_waiting_requires_reason(self):
        """Backward prices_ready → waiting_prices marked requires_reason."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "prices_ready", "waiting_prices", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is True

    def test_invalid_skip_transition_denied(self):
        """distributing → prices_ready is not in the list (skip forward)."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "distributing", "prices_ready", ["procurement"]
        )
        assert allowed is False
        assert transition is None

    def test_none_from_substatus_denied(self):
        """from_substatus=None always denied (cannot transition from nothing)."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", None, "searching_supplier", ["procurement"]
        )
        assert allowed is False
        assert transition is None

    def test_wrong_parent_status_denied(self):
        """pending_logistics parent has no registered sub-state transitions yet."""
        allowed, transition = can_transition_substatus(
            "pending_logistics", "distributing", "searching_supplier", ["procurement"]
        )
        assert allowed is False
        assert transition is None

    def test_admin_role_allowed(self):
        """admin role can perform procurement sub-state transitions."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["admin"]
        )
        assert allowed is True

    def test_head_of_procurement_role_allowed(self):
        """head_of_procurement role can perform procurement sub-state transitions."""
        allowed, transition = can_transition_substatus(
            "pending_procurement", "waiting_prices", "prices_ready", ["head_of_procurement"]
        )
        assert allowed is True

    def test_multiple_roles_any_match_allowed(self):
        """User with multiple roles — if any matches, transition allowed."""
        allowed, _ = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["sales", "procurement"]
        )
        assert allowed is True


class TestTransitionSubstatus:
    """Integration tests with mocked Supabase client."""

    @patch("services.workflow_service.get_supabase")
    def test_happy_path_forward_transition(self, mock_get_sb):
        """Forward transition fetches quote, writes history, updates substatus."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        # Fetch returns quote in pending_procurement/distributing
        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "distributing",
        })
        # Update returns the updated quote
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {"id": "q-001", "procurement_substatus": "searching_supplier"}
        ]

        result = transition_substatus(
            quote_id="q-001",
            to_substatus="searching_supplier",
            user_id="user-001",
            user_roles=["procurement"],
        )

        # Verify the tables touched
        table_names = [c[0][0] for c in mock_sb.table.call_args_list]
        assert "quotes" in table_names
        assert "status_history" in table_names

        assert result["id"] == "q-001"
        assert result["procurement_substatus"] == "searching_supplier"

    @patch("services.workflow_service.get_supabase")
    def test_backward_without_reason_raises(self, mock_get_sb):
        """Backward transition without a reason raises ValueError."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "waiting_prices",
        })

        with pytest.raises(ValueError, match="Reason required"):
            transition_substatus(
                quote_id="q-001",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["procurement"],
                reason="",
            )

    @patch("services.workflow_service.get_supabase")
    def test_backward_with_whitespace_only_reason_raises(self, mock_get_sb):
        """Reason consisting of only whitespace is rejected."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "waiting_prices",
        })

        with pytest.raises(ValueError, match="Reason required"):
            transition_substatus(
                quote_id="q-001",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["procurement"],
                reason="   ",
            )

    @patch("services.workflow_service.get_supabase")
    def test_backward_with_reason_succeeds(self, mock_get_sb):
        """Backward transition succeeds when reason is provided."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "waiting_prices",
        })
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {"id": "q-001", "procurement_substatus": "searching_supplier"}
        ]

        result = transition_substatus(
            quote_id="q-001",
            to_substatus="searching_supplier",
            user_id="user-001",
            user_roles=["procurement"],
            reason="Supplier unresponsive, retry search",
        )

        assert result["procurement_substatus"] == "searching_supplier"

    @patch("services.workflow_service.get_supabase")
    def test_quote_not_found_raises(self, mock_get_sb):
        """Non-existent quote raises ValueError."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb
        _setup_quote_fetch(mock_sb, None)

        with pytest.raises(ValueError, match="not found"):
            transition_substatus(
                quote_id="q-missing",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["procurement"],
            )

    @patch("services.workflow_service.get_supabase")
    def test_invalid_transition_pair_raises(self, mock_get_sb):
        """Invalid from→to pair (skip forward) raises ValueError with clear message."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "distributing",
        })

        with pytest.raises(ValueError, match="Invalid substatus transition"):
            transition_substatus(
                quote_id="q-001",
                to_substatus="prices_ready",
                user_id="user-001",
                user_roles=["procurement"],
            )

    @patch("services.workflow_service.get_supabase")
    def test_wrong_role_raises(self, mock_get_sb):
        """Sales role cannot do procurement substate transition."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "distributing",
        })

        with pytest.raises(ValueError, match="Invalid substatus transition"):
            transition_substatus(
                quote_id="q-001",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["sales"],
            )

    @patch("services.workflow_service.get_supabase")
    def test_history_row_fields(self, mock_get_sb):
        """status_history insert receives correct from/to substatus and reason."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "waiting_prices",
        })
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {"id": "q-001", "procurement_substatus": "searching_supplier"}
        ]

        transition_substatus(
            quote_id="q-001",
            to_substatus="searching_supplier",
            user_id="user-007",
            user_roles=["procurement"],
            reason="Need to re-verify suppliers",
        )

        # Inspect insert calls to status_history
        insert_calls = mock_sb.table.return_value.insert.call_args_list
        assert len(insert_calls) >= 1
        history_payload = insert_calls[0][0][0]
        assert history_payload["quote_id"] == "q-001"
        assert history_payload["from_substatus"] == "waiting_prices"
        assert history_payload["to_substatus"] == "searching_supplier"
        assert history_payload["reason"] == "Need to re-verify suppliers"
        assert history_payload["transitioned_by"] == "user-007"

    @patch("services.workflow_service.get_supabase")
    def test_history_row_parent_status_unchanged(self, mock_get_sb):
        """For sub-state moves, from_status == to_status (parent workflow unchanged)."""
        mock_sb = _mock_supabase()
        mock_get_sb.return_value = mock_sb

        _setup_quote_fetch(mock_sb, {
            "id": "q-001",
            "workflow_status": "pending_procurement",
            "procurement_substatus": "distributing",
        })
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {"id": "q-001", "procurement_substatus": "searching_supplier"}
        ]

        transition_substatus(
            quote_id="q-001",
            to_substatus="searching_supplier",
            user_id="user-001",
            user_roles=["procurement"],
        )

        history_payload = mock_sb.table.return_value.insert.call_args_list[0][0][0]
        assert history_payload["from_status"] == "pending_procurement"
        assert history_payload["to_status"] == "pending_procurement"


class TestTransitionsCatalog:
    """Basic sanity checks on the transitions catalog itself."""

    def test_catalog_not_empty(self):
        assert len(PROCUREMENT_SUBSTATUS_TRANSITIONS) > 0

    def test_all_entries_are_substatetransition(self):
        assert all(isinstance(t, SubStateTransition) for t in PROCUREMENT_SUBSTATUS_TRANSITIONS)

    def test_backward_transitions_require_reason(self):
        """All transitions matching a reverse pair must require_reason=True."""
        forward_pairs = {
            ("distributing", "searching_supplier"),
            ("searching_supplier", "waiting_prices"),
            ("waiting_prices", "prices_ready"),
        }
        for t in PROCUREMENT_SUBSTATUS_TRANSITIONS:
            reverse = (t.to_substatus, t.from_substatus)
            if reverse in forward_pairs:
                assert t.requires_reason is True, (
                    f"Backward {t.from_substatus}→{t.to_substatus} must require reason"
                )
