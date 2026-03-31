"""
Tests for Stage Timer Service — timer computation, formatting, and overdue detection.

Tests cover:
- format_elapsed() with various hour inputs (minutes, hours, days)
- Timer status computation logic (_compute_status, _build_timer)
- Terminal status handling (draft, deal, rejected, cancelled → no_timer)
- get_quote_timer() with mocked Supabase
- get_bulk_timers() returns dict keyed by quote_id
- get_overdue_quotes() filters correctly
- mark_overdue_notified() calls update
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    return str(uuid4())


@pytest.fixture
def quote_id():
    return str(uuid4())


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client with chained query builder."""
    client = MagicMock()
    return client


def _make_chain(client, data=None):
    """Configure a mock supabase client table chain to return given data."""
    if data is None:
        data = []
    table = MagicMock()
    client.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.in_.return_value = table
    table.is_.return_value = table
    table.update.return_value = table
    table.execute.return_value = MagicMock(data=data)
    return table


# =============================================================================
# FORMAT ELAPSED TESTS
# =============================================================================

class TestFormatElapsed:
    """Test format_elapsed() with various hour inputs."""

    def test_zero_hours(self):
        from services.stage_timer_service import format_elapsed
        assert format_elapsed(0.0) == "0м"

    def test_minutes_only(self):
        from services.stage_timer_service import format_elapsed
        result = format_elapsed(0.75)  # 45 minutes
        assert result == "45м"

    def test_half_hour(self):
        from services.stage_timer_service import format_elapsed
        assert format_elapsed(0.5) == "30м"

    def test_one_hour_exact(self):
        from services.stage_timer_service import format_elapsed
        assert format_elapsed(1.0) == "1ч"

    def test_hours_and_minutes(self):
        from services.stage_timer_service import format_elapsed
        result = format_elapsed(2.25)  # 2h 15m
        assert result == "2ч 15м"

    def test_hours_exact_no_minutes(self):
        from services.stage_timer_service import format_elapsed
        assert format_elapsed(5.0) == "5ч"

    def test_23_hours(self):
        from services.stage_timer_service import format_elapsed
        result = format_elapsed(23.5)  # 23h 30m
        assert result == "23ч 30м"

    def test_one_day_exact(self):
        from services.stage_timer_service import format_elapsed
        assert format_elapsed(24.0) == "1д"

    def test_days_and_hours(self):
        from services.stage_timer_service import format_elapsed
        result = format_elapsed(77.0)  # 3d 5h
        assert result == "3д 5ч"

    def test_multiple_days_exact(self):
        from services.stage_timer_service import format_elapsed
        assert format_elapsed(48.0) == "2д"

    def test_negative_hours_treated_as_zero(self):
        from services.stage_timer_service import format_elapsed
        assert format_elapsed(-5.0) == "0м"

    def test_large_value(self):
        from services.stage_timer_service import format_elapsed
        result = format_elapsed(100.0)  # 4d 4h
        assert result == "4д 4ч"


# =============================================================================
# COMPUTE STATUS TESTS
# =============================================================================

class TestComputeStatus:
    """Test _compute_status() with various elapsed/deadline combinations."""

    def test_no_deadline_returns_no_deadline(self):
        from services.stage_timer_service import _compute_status
        assert _compute_status(10.0, None) == "no_deadline"

    def test_ok_status(self):
        from services.stage_timer_service import _compute_status
        # 10h elapsed, 48h deadline → 10/48 = 20.8% < 80%
        assert _compute_status(10.0, 48) == "ok"

    def test_warning_at_threshold(self):
        from services.stage_timer_service import _compute_status
        # 40h elapsed, 50h deadline → 40/50 = 80% exactly (no float precision issue)
        assert _compute_status(40.0, 50) == "warning"

    def test_warning_above_threshold(self):
        from services.stage_timer_service import _compute_status
        # 40h elapsed, 48h deadline → 83%
        assert _compute_status(40.0, 48) == "warning"

    def test_overdue_at_deadline(self):
        from services.stage_timer_service import _compute_status
        # elapsed == deadline
        assert _compute_status(48.0, 48) == "overdue"

    def test_overdue_past_deadline(self):
        from services.stage_timer_service import _compute_status
        assert _compute_status(60.0, 48) == "overdue"

    def test_zero_deadline(self):
        from services.stage_timer_service import _compute_status
        # 0h deadline means immediately overdue if any time elapsed
        assert _compute_status(0.1, 0) == "overdue"

    def test_zero_elapsed_zero_deadline(self):
        from services.stage_timer_service import _compute_status
        assert _compute_status(0.0, 0) == "overdue"


# =============================================================================
# BUILD TIMER TESTS
# =============================================================================

class TestBuildTimer:
    """Test _build_timer() with various quote states."""

    def test_terminal_status_draft(self):
        from services.stage_timer_service import _build_timer
        quote = {"workflow_status": "draft", "stage_entered_at": None}
        result = _build_timer(quote, {})
        assert result["status"] == "no_timer"
        assert result["stage"] == "draft"

    def test_terminal_status_deal(self):
        from services.stage_timer_service import _build_timer
        quote = {"workflow_status": "deal", "stage_entered_at": "2026-01-01T00:00:00Z"}
        result = _build_timer(quote, {})
        assert result["status"] == "no_timer"

    def test_terminal_status_rejected(self):
        from services.stage_timer_service import _build_timer
        quote = {"workflow_status": "rejected"}
        result = _build_timer(quote, {})
        assert result["status"] == "no_timer"

    def test_terminal_status_cancelled(self):
        from services.stage_timer_service import _build_timer
        quote = {"workflow_status": "cancelled"}
        result = _build_timer(quote, {})
        assert result["status"] == "no_timer"

    def test_no_stage_entered_at_returns_no_timer(self):
        from services.stage_timer_service import _build_timer
        quote = {"workflow_status": "pending_procurement", "stage_entered_at": None}
        result = _build_timer(quote, {"pending_procurement": 48})
        assert result["status"] == "no_timer"

    def test_active_quote_with_deadline(self):
        from services.stage_timer_service import _build_timer
        now = datetime.now(timezone.utc)
        entered = (now - timedelta(hours=10)).isoformat()
        quote = {
            "workflow_status": "pending_procurement",
            "stage_entered_at": entered,
            "stage_deadline_override_hours": None,
        }
        result = _build_timer(quote, {"pending_procurement": 48})
        assert result["status"] == "ok"
        assert 9.5 < result["elapsed_hours"] < 10.5
        assert result["deadline_hours"] == 48
        assert result["stage"] == "pending_procurement"

    def test_override_takes_precedence(self):
        from services.stage_timer_service import _build_timer
        now = datetime.now(timezone.utc)
        entered = (now - timedelta(hours=10)).isoformat()
        quote = {
            "workflow_status": "pending_procurement",
            "stage_entered_at": entered,
            "stage_deadline_override_hours": 12,
        }
        # Global deadline is 48, but override is 12 → warning at 80% of 12 = 9.6h
        result = _build_timer(quote, {"pending_procurement": 48})
        assert result["deadline_hours"] == 12
        assert result["status"] == "warning"

    def test_no_deadline_configured(self):
        from services.stage_timer_service import _build_timer
        now = datetime.now(timezone.utc)
        entered = (now - timedelta(hours=10)).isoformat()
        quote = {
            "workflow_status": "some_unknown_stage",
            "stage_entered_at": entered,
            "stage_deadline_override_hours": None,
        }
        result = _build_timer(quote, {})
        assert result["status"] == "no_deadline"


# =============================================================================
# GET QUOTE TIMER TESTS (with mock Supabase)
# =============================================================================

class TestGetQuoteTimer:
    """Test get_quote_timer() with mocked database calls."""

    def test_quote_not_found(self, quote_id, org_id, mock_supabase):
        from services.stage_timer_service import get_quote_timer

        _make_chain(mock_supabase, data=[])

        with patch("services.stage_timer_service._get_supabase", return_value=mock_supabase):
            result = get_quote_timer(quote_id, org_id)

        assert result["status"] == "no_timer"

    def test_terminal_quote(self, quote_id, org_id, mock_supabase):
        from services.stage_timer_service import get_quote_timer

        call_count = 0
        def table_side_effect(name):
            nonlocal call_count
            call_count += 1
            t = MagicMock()
            t.select.return_value = t
            t.eq.return_value = t
            t.in_.return_value = t
            t.is_.return_value = t
            t.execute.return_value = MagicMock(data=[])

            if name == "quotes":
                t.execute.return_value = MagicMock(data=[{
                    "id": quote_id,
                    "workflow_status": "deal",
                    "stage_entered_at": None,
                    "stage_deadline_override_hours": None,
                }])
            return t

        mock_supabase.table.side_effect = table_side_effect

        with patch("services.stage_timer_service._get_supabase", return_value=mock_supabase):
            result = get_quote_timer(quote_id, org_id)

        assert result["status"] == "no_timer"
        assert result["stage"] == "deal"


# =============================================================================
# GET BULK TIMERS TESTS
# =============================================================================

class TestGetBulkTimers:
    """Test get_bulk_timers() returns dict keyed by quote_id."""

    def test_empty_list(self, org_id):
        from services.stage_timer_service import get_bulk_timers
        assert get_bulk_timers([], org_id) == {}

    def test_multiple_quotes(self, org_id, mock_supabase):
        from services.stage_timer_service import get_bulk_timers

        q1, q2 = str(uuid4()), str(uuid4())
        now = datetime.now(timezone.utc)

        def table_side_effect(name):
            t = MagicMock()
            t.select.return_value = t
            t.eq.return_value = t
            t.in_.return_value = t
            t.is_.return_value = t
            if name == "quotes":
                t.execute.return_value = MagicMock(data=[
                    {
                        "id": q1,
                        "workflow_status": "pending_procurement",
                        "stage_entered_at": (now - timedelta(hours=5)).isoformat(),
                        "stage_deadline_override_hours": None,
                    },
                    {
                        "id": q2,
                        "workflow_status": "deal",
                        "stage_entered_at": None,
                        "stage_deadline_override_hours": None,
                    },
                ])
            else:
                t.execute.return_value = MagicMock(data=[
                    {"stage": "pending_procurement", "deadline_hours": 48}
                ])
            return t

        mock_supabase.table.side_effect = table_side_effect

        with patch("services.stage_timer_service._get_supabase", return_value=mock_supabase):
            result = get_bulk_timers([q1, q2], org_id)

        assert q1 in result
        assert q2 in result
        assert result[q1]["status"] == "ok"
        assert result[q2]["status"] == "no_timer"


# =============================================================================
# GET OVERDUE QUOTES TESTS
# =============================================================================

class TestGetOverdueQuotes:
    """Test get_overdue_quotes() filters and returns overdue items."""

    def test_returns_overdue_only(self, org_id, mock_supabase):
        from services.stage_timer_service import get_overdue_quotes

        now = datetime.now(timezone.utc)
        q_overdue = str(uuid4())
        q_ok = str(uuid4())

        def table_side_effect(name):
            t = MagicMock()
            t.select.return_value = t
            t.eq.return_value = t
            t.in_.return_value = t
            t.is_.return_value = t
            if name == "quotes":
                t.execute.return_value = MagicMock(data=[
                    {
                        "id": q_overdue,
                        "idn": "Q-202603-0001",
                        "workflow_status": "pending_procurement",
                        "stage_entered_at": (now - timedelta(hours=60)).isoformat(),
                        "stage_deadline_override_hours": None,
                        "overdue_notified_at": None,
                        "assigned_user_id": str(uuid4()),
                        "manager_id": str(uuid4()),
                    },
                    {
                        "id": q_ok,
                        "idn": "Q-202603-0002",
                        "workflow_status": "pending_procurement",
                        "stage_entered_at": (now - timedelta(hours=5)).isoformat(),
                        "stage_deadline_override_hours": None,
                        "overdue_notified_at": None,
                        "assigned_user_id": str(uuid4()),
                        "manager_id": str(uuid4()),
                    },
                ])
            else:  # stage_deadlines
                t.execute.return_value = MagicMock(data=[
                    {"stage": "pending_procurement", "deadline_hours": 48}
                ])
            return t

        mock_supabase.table.side_effect = table_side_effect

        with patch("services.stage_timer_service._get_supabase", return_value=mock_supabase):
            result = get_overdue_quotes(org_id)

        assert len(result) == 1
        assert result[0]["quote_id"] == q_overdue
        assert result[0]["idn"] == "Q-202603-0001"
        assert result[0]["stage"] == "pending_procurement"
        assert result[0]["deadline_hours"] == 48


# =============================================================================
# MARK OVERDUE NOTIFIED TESTS
# =============================================================================

class TestMarkOverdueNotified:
    """Test mark_overdue_notified() updates the quote."""

    def test_calls_update(self, quote_id, mock_supabase):
        from services.stage_timer_service import mark_overdue_notified

        table = _make_chain(mock_supabase)

        with patch("services.stage_timer_service._get_supabase", return_value=mock_supabase):
            mark_overdue_notified(quote_id)

        mock_supabase.table.assert_called_with("quotes")
        table.update.assert_called_once()
        update_data = table.update.call_args[0][0]
        assert "overdue_notified_at" in update_data
        assert update_data["overdue_notified_at"] is not None
        table.eq.assert_called_with("id", quote_id)


# =============================================================================
# MODULE IMPORT TESTS
# =============================================================================

class TestModuleImports:
    """Verify module exports expected symbols."""

    def test_import_module(self):
        from services import stage_timer_service
        assert stage_timer_service is not None

    def test_import_get_quote_timer(self):
        from services.stage_timer_service import get_quote_timer
        assert callable(get_quote_timer)

    def test_import_get_bulk_timers(self):
        from services.stage_timer_service import get_bulk_timers
        assert callable(get_bulk_timers)

    def test_import_get_overdue_quotes(self):
        from services.stage_timer_service import get_overdue_quotes
        assert callable(get_overdue_quotes)

    def test_import_format_elapsed(self):
        from services.stage_timer_service import format_elapsed
        assert callable(format_elapsed)

    def test_import_mark_overdue_notified(self):
        from services.stage_timer_service import mark_overdue_notified
        assert callable(mark_overdue_notified)

    def test_terminal_statuses_constant(self):
        from services.stage_timer_service import TERMINAL_STATUSES
        assert "draft" in TERMINAL_STATUSES
        assert "deal" in TERMINAL_STATUSES
        assert "rejected" in TERMINAL_STATUSES
        assert "cancelled" in TERMINAL_STATUSES

    def test_warning_threshold_constant(self):
        from services.stage_timer_service import WARNING_THRESHOLD
        assert WARNING_THRESHOLD == 0.8
