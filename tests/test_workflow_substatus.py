"""
Tests for workflow_service sub-state machine at (quote, brand) grain (Phase 4c refactor).

Tests:
- can_transition_substatus: pure logic, no DB (unchanged)
- transition_substatus: mocked DB — now brand-aware
    - happy path forward for a specific brand
    - backward without reason raises ValueError
    - backward with reason succeeds
    - (quote, brand) not found raises ValueError
    - invalid transition pair raises ValueError
    - wrong role raises ValueError
    - status_history row written with brand field populated
    - parent_status unchanged in history (from_status == to_status)
- maybe_advance_after_distribution: per-brand auto-advance
    - no-op when row missing
    - no-op when already past 'distributing'
    - no-op when at least one item still unrouted
    - advances when every item has assigned_procurement_user
    - advances when mix of assigned + is_unavailable items
    - filters by brand (other brand's unrouted items don't block)
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
    maybe_advance_after_distribution,
)


# ---------------------------------------------------------------------------
# Mock plumbing
# ---------------------------------------------------------------------------


def _build_supabase(handlers: dict):
    """Build a MagicMock supabase whose .table(name) dispatches to handlers[name].

    Each handler receives the fresh MagicMock table, configures it, and returns it.
    """
    sb = MagicMock()

    def _table(name: str):
        tbl = MagicMock()
        if name in handlers:
            handlers[name](tbl)
        return tbl

    sb.table.side_effect = _table
    return sb


def _qbs_row(substatus, quote_id="q-001", brand="ABB"):
    return {"quote_id": quote_id, "brand": brand, "substatus": substatus}


# ---------------------------------------------------------------------------
# Pure logic — unchanged
# ---------------------------------------------------------------------------


class TestCanTransitionSubstatus:
    def test_forward_distributing_to_searching_supplier_allowed(self):
        allowed, transition = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is False

    def test_forward_searching_to_waiting_prices_allowed(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", "searching_supplier", "waiting_prices", ["procurement"]
        )
        assert allowed is True

    def test_forward_waiting_prices_to_prices_ready_allowed(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", "waiting_prices", "prices_ready", ["procurement"]
        )
        assert allowed is True

    def test_wrong_role_denied(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["sales"]
        )
        assert allowed is False

    def test_backward_transition_allowed_for_procurement(self):
        allowed, transition = can_transition_substatus(
            "pending_procurement", "searching_supplier", "distributing", ["procurement"]
        )
        assert allowed is True
        assert transition is not None
        assert transition.requires_reason is True

    def test_backward_waiting_prices_to_searching_requires_reason(self):
        _, transition = can_transition_substatus(
            "pending_procurement", "waiting_prices", "searching_supplier", ["procurement"]
        )
        assert transition is not None
        assert transition.requires_reason is True

    def test_backward_prices_ready_to_waiting_requires_reason(self):
        _, transition = can_transition_substatus(
            "pending_procurement", "prices_ready", "waiting_prices", ["procurement"]
        )
        assert transition is not None
        assert transition.requires_reason is True

    def test_invalid_skip_transition_denied(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", "distributing", "prices_ready", ["procurement"]
        )
        assert allowed is False

    def test_none_from_substatus_denied(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", None, "searching_supplier", ["procurement"]
        )
        assert allowed is False

    def test_wrong_parent_status_denied(self):
        allowed, _ = can_transition_substatus(
            "pending_logistics", "distributing", "searching_supplier", ["procurement"]
        )
        assert allowed is False

    def test_admin_role_allowed(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["admin"]
        )
        assert allowed is True

    def test_head_of_procurement_role_allowed(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", "waiting_prices", "prices_ready", ["head_of_procurement"]
        )
        assert allowed is True

    def test_multiple_roles_any_match_allowed(self):
        allowed, _ = can_transition_substatus(
            "pending_procurement", "distributing", "searching_supplier", ["sales", "procurement"]
        )
        assert allowed is True


# ---------------------------------------------------------------------------
# transition_substatus — brand-aware
# ---------------------------------------------------------------------------


def _setup_qbs_fetch(tbl, row):
    tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
        [row] if row else []
    )


def _setup_qbs_update(tbl, row):
    tbl.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
        [row] if row else []
    )


class TestTransitionSubstatus:
    @patch("services.workflow_service.get_supabase")
    def test_happy_path_forward_transition(self, mock_get_sb):
        sb = MagicMock()

        def _table(name):
            tbl = MagicMock()
            if name == "quote_brand_substates":
                _setup_qbs_fetch(tbl, _qbs_row("distributing"))
                _setup_qbs_update(tbl, _qbs_row("searching_supplier"))
            return tbl

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        result = transition_substatus(
            quote_id="q-001",
            brand="ABB",
            to_substatus="searching_supplier",
            user_id="user-001",
            user_roles=["procurement"],
        )
        assert result["substatus"] == "searching_supplier"
        assert result["brand"] == "ABB"

    @patch("services.workflow_service.get_supabase")
    def test_backward_without_reason_raises(self, mock_get_sb):
        sb = MagicMock()
        sb.table.side_effect = lambda n: (
            _patch_qbs_fetch(MagicMock(), _qbs_row("waiting_prices"))
            if n == "quote_brand_substates" else MagicMock()
        )
        mock_get_sb.return_value = sb

        with pytest.raises(ValueError, match="Reason required"):
            transition_substatus(
                quote_id="q-001",
                brand="ABB",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["procurement"],
                reason="",
            )

    @patch("services.workflow_service.get_supabase")
    def test_backward_with_whitespace_only_reason_raises(self, mock_get_sb):
        sb = MagicMock()
        sb.table.side_effect = lambda n: (
            _patch_qbs_fetch(MagicMock(), _qbs_row("waiting_prices"))
            if n == "quote_brand_substates" else MagicMock()
        )
        mock_get_sb.return_value = sb

        with pytest.raises(ValueError, match="Reason required"):
            transition_substatus(
                quote_id="q-001",
                brand="ABB",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["procurement"],
                reason="   ",
            )

    @patch("services.workflow_service.get_supabase")
    def test_backward_with_reason_succeeds(self, mock_get_sb):
        sb = MagicMock()

        def _table(name):
            tbl = MagicMock()
            if name == "quote_brand_substates":
                _setup_qbs_fetch(tbl, _qbs_row("waiting_prices"))
                _setup_qbs_update(tbl, _qbs_row("searching_supplier"))
            return tbl

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        result = transition_substatus(
            quote_id="q-001",
            brand="ABB",
            to_substatus="searching_supplier",
            user_id="user-001",
            user_roles=["procurement"],
            reason="Supplier unresponsive, retry search",
        )
        assert result["substatus"] == "searching_supplier"

    @patch("services.workflow_service.get_supabase")
    def test_quote_brand_not_found_raises(self, mock_get_sb):
        sb = MagicMock()
        sb.table.side_effect = lambda n: (
            _patch_qbs_fetch(MagicMock(), None)
            if n == "quote_brand_substates" else MagicMock()
        )
        mock_get_sb.return_value = sb

        with pytest.raises(ValueError, match="not found"):
            transition_substatus(
                quote_id="q-missing",
                brand="ABB",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["procurement"],
            )

    @patch("services.workflow_service.get_supabase")
    def test_invalid_transition_pair_raises(self, mock_get_sb):
        sb = MagicMock()
        sb.table.side_effect = lambda n: (
            _patch_qbs_fetch(MagicMock(), _qbs_row("distributing"))
            if n == "quote_brand_substates" else MagicMock()
        )
        mock_get_sb.return_value = sb

        with pytest.raises(ValueError, match="Invalid substatus transition"):
            transition_substatus(
                quote_id="q-001",
                brand="ABB",
                to_substatus="prices_ready",
                user_id="user-001",
                user_roles=["procurement"],
            )

    @patch("services.workflow_service.get_supabase")
    def test_wrong_role_raises(self, mock_get_sb):
        sb = MagicMock()
        sb.table.side_effect = lambda n: (
            _patch_qbs_fetch(MagicMock(), _qbs_row("distributing"))
            if n == "quote_brand_substates" else MagicMock()
        )
        mock_get_sb.return_value = sb

        with pytest.raises(ValueError, match="Invalid substatus transition"):
            transition_substatus(
                quote_id="q-001",
                brand="ABB",
                to_substatus="searching_supplier",
                user_id="user-001",
                user_roles=["sales"],
            )

    @patch("services.workflow_service.get_supabase")
    def test_history_row_fields_include_brand(self, mock_get_sb):
        sb = MagicMock()
        history_tbl = MagicMock()

        def _table(name):
            if name == "quote_brand_substates":
                tbl = MagicMock()
                _setup_qbs_fetch(tbl, _qbs_row("waiting_prices"))
                _setup_qbs_update(tbl, _qbs_row("searching_supplier"))
                return tbl
            if name == "status_history":
                return history_tbl
            return MagicMock()

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        transition_substatus(
            quote_id="q-001",
            brand="ABB",
            to_substatus="searching_supplier",
            user_id="user-007",
            user_roles=["procurement"],
            reason="Need to re-verify suppliers",
        )

        insert_calls = history_tbl.insert.call_args_list
        assert len(insert_calls) >= 1
        payload = insert_calls[0][0][0]
        assert payload["quote_id"] == "q-001"
        assert payload["brand"] == "ABB"
        assert payload["from_substatus"] == "waiting_prices"
        assert payload["to_substatus"] == "searching_supplier"
        assert payload["reason"] == "Need to re-verify suppliers"
        assert payload["transitioned_by"] == "user-007"

    @patch("services.workflow_service.get_supabase")
    def test_history_row_parent_status_unchanged(self, mock_get_sb):
        sb = MagicMock()
        history_tbl = MagicMock()

        def _table(name):
            if name == "quote_brand_substates":
                tbl = MagicMock()
                _setup_qbs_fetch(tbl, _qbs_row("distributing"))
                _setup_qbs_update(tbl, _qbs_row("searching_supplier"))
                return tbl
            if name == "status_history":
                return history_tbl
            return MagicMock()

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        transition_substatus(
            quote_id="q-001",
            brand="ABB",
            to_substatus="searching_supplier",
            user_id="user-001",
            user_roles=["procurement"],
        )
        payload = history_tbl.insert.call_args_list[0][0][0]
        assert payload["from_status"] == "pending_procurement"
        assert payload["to_status"] == "pending_procurement"


def _patch_qbs_fetch(tbl, row):
    """Helper used inline by lambdas — configures fetch chain and returns tbl."""
    tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
        [row] if row else []
    )
    return tbl


# ---------------------------------------------------------------------------
# maybe_advance_after_distribution
# ---------------------------------------------------------------------------


def _setup_items_fetch(tbl, items):
    tbl.select.return_value.eq.return_value.execute.return_value.data = items


class TestMaybeAdvanceAfterDistribution:
    @patch("services.workflow_service.get_supabase")
    def test_no_row_is_noop(self, mock_get_sb):
        sb = MagicMock()
        sb.table.side_effect = lambda n: _patch_qbs_fetch(MagicMock(), None) \
            if n == "quote_brand_substates" else MagicMock()
        mock_get_sb.return_value = sb

        assert maybe_advance_after_distribution("q-001", "ABB", "u-1") is None

    @patch("services.workflow_service.get_supabase")
    def test_past_distributing_is_noop(self, mock_get_sb):
        sb = MagicMock()
        sb.table.side_effect = lambda n: _patch_qbs_fetch(MagicMock(), _qbs_row("waiting_prices")) \
            if n == "quote_brand_substates" else MagicMock()
        mock_get_sb.return_value = sb

        assert maybe_advance_after_distribution("q-001", "ABB", "u-1") is None

    @patch("services.workflow_service.get_supabase")
    def test_unrouted_item_blocks_advance(self, mock_get_sb):
        sb = MagicMock()

        def _table(name):
            tbl = MagicMock()
            if name == "quote_brand_substates":
                _patch_qbs_fetch(tbl, _qbs_row("distributing"))
            elif name == "quote_items":
                _setup_items_fetch(tbl, [
                    {"id": "i-1", "brand": "ABB", "assigned_procurement_user": "u-2", "is_unavailable": False},
                    {"id": "i-2", "brand": "ABB", "assigned_procurement_user": None, "is_unavailable": False},
                ])
            return tbl

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        assert maybe_advance_after_distribution("q-001", "ABB", "u-1") is None

    @patch("services.workflow_service.get_supabase")
    def test_all_assigned_advances(self, mock_get_sb):
        sb = MagicMock()
        qbs_tbl = MagicMock()
        _patch_qbs_fetch(qbs_tbl, _qbs_row("distributing"))
        _setup_qbs_update(qbs_tbl, _qbs_row("searching_supplier"))

        def _table(name):
            if name == "quote_brand_substates":
                return qbs_tbl
            if name == "quote_items":
                tbl = MagicMock()
                _setup_items_fetch(tbl, [
                    {"id": "i-1", "brand": "ABB", "assigned_procurement_user": "u-2", "is_unavailable": False},
                    {"id": "i-2", "brand": "ABB", "assigned_procurement_user": "u-3", "is_unavailable": False},
                ])
                return tbl
            return MagicMock()

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        result = maybe_advance_after_distribution("q-001", "ABB", "u-1")
        assert result is not None
        assert result["substatus"] == "searching_supplier"

    @patch("services.workflow_service.get_supabase")
    def test_mix_of_assigned_and_unavailable_advances(self, mock_get_sb):
        sb = MagicMock()
        qbs_tbl = MagicMock()
        _patch_qbs_fetch(qbs_tbl, _qbs_row("distributing"))
        _setup_qbs_update(qbs_tbl, _qbs_row("searching_supplier"))

        def _table(name):
            if name == "quote_brand_substates":
                return qbs_tbl
            if name == "quote_items":
                tbl = MagicMock()
                _setup_items_fetch(tbl, [
                    {"id": "i-1", "brand": "ABB", "assigned_procurement_user": "u-2", "is_unavailable": False},
                    {"id": "i-2", "brand": "ABB", "assigned_procurement_user": None, "is_unavailable": True},
                ])
                return tbl
            return MagicMock()

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        result = maybe_advance_after_distribution("q-001", "ABB", "u-1")
        assert result is not None
        assert result["substatus"] == "searching_supplier"

    @patch("services.workflow_service.get_supabase")
    def test_other_brand_items_do_not_block(self, mock_get_sb):
        """Items belonging to a different brand are filtered out client-side."""
        sb = MagicMock()
        qbs_tbl = MagicMock()
        _patch_qbs_fetch(qbs_tbl, _qbs_row("distributing", brand="ABB"))
        _setup_qbs_update(qbs_tbl, _qbs_row("searching_supplier", brand="ABB"))

        def _table(name):
            if name == "quote_brand_substates":
                return qbs_tbl
            if name == "quote_items":
                tbl = MagicMock()
                _setup_items_fetch(tbl, [
                    {"id": "i-1", "brand": "ABB", "assigned_procurement_user": "u-2", "is_unavailable": False},
                    {"id": "i-2", "brand": "Siemens", "assigned_procurement_user": None, "is_unavailable": False},
                ])
                return tbl
            return MagicMock()

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        result = maybe_advance_after_distribution("q-001", "ABB", "u-1")
        assert result is not None
        assert result["substatus"] == "searching_supplier"

    @patch("services.workflow_service.get_supabase")
    def test_no_items_for_brand_is_noop(self, mock_get_sb):
        sb = MagicMock()
        qbs_tbl = MagicMock()
        _patch_qbs_fetch(qbs_tbl, _qbs_row("distributing", brand="ABB"))

        def _table(name):
            if name == "quote_brand_substates":
                return qbs_tbl
            if name == "quote_items":
                tbl = MagicMock()
                _setup_items_fetch(tbl, [
                    {"id": "i-2", "brand": "Siemens", "assigned_procurement_user": "u-2", "is_unavailable": False},
                ])
                return tbl
            return MagicMock()

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        assert maybe_advance_after_distribution("q-001", "ABB", "u-1") is None


class TestTransitionsCatalog:
    def test_catalog_not_empty(self):
        assert len(PROCUREMENT_SUBSTATUS_TRANSITIONS) > 0

    def test_all_entries_are_substatetransition(self):
        assert all(isinstance(t, SubStateTransition) for t in PROCUREMENT_SUBSTATUS_TRANSITIONS)

    def test_backward_transitions_require_reason(self):
        forward_pairs = {
            ("distributing", "searching_supplier"),
            ("searching_supplier", "waiting_prices"),
            ("waiting_prices", "prices_ready"),
        }
        for t in PROCUREMENT_SUBSTATUS_TRANSITIONS:
            reverse = (t.to_substatus, t.from_substatus)
            if reverse in forward_pairs:
                assert t.requires_reason is True
