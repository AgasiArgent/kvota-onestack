"""
TDD Tests for P2.7+P2.8: Logistics Stages Model + Per-Stage Expenses

Feature P2.7: Logistics Stages Model
- 7 predefined stages for transit delivery
- Each stage has: status (pending/in_progress/completed), started_at, completed_at,
  responsible_person, notes
- Stage codes: first_mile, hub, hub_hub, transit, post_transit, gtd_upload, last_mile
- gtd_upload stage has NO expense capability (just a status flag)

Feature P2.8: Expenses Per Stage
- Expenses are plan_fact_items with logistics_stage_id FK
- Each expense has: description, amount, currency, expense_date
- Stage summary: total planned, total actual, variance, expense count
- Multiple currencies supported (USD, EUR, RUB, etc.)

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the feature is implemented.

Service file to create: services/logistics_service.py
"""

import pytest
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==============================================================================
# Helpers
# ==============================================================================

def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Constants expected from logistics_service
# ==============================================================================

EXPECTED_STAGE_CODES = [
    'first_mile',
    'hub',
    'hub_hub',
    'transit',
    'post_transit',
    'gtd_upload',
    'last_mile',
]

EXPECTED_STAGE_COUNT = 7

# Stages that allow expenses (all except gtd_upload)
EXPENSE_ALLOWED_STAGES = [
    'first_mile', 'hub', 'hub_hub', 'transit', 'post_transit', 'last_mile'
]

VALID_STATUSES = ['pending', 'in_progress', 'completed']


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def deal_id():
    return _make_uuid()


@pytest.fixture
def org_id():
    return _make_uuid()


@pytest.fixture
def user_id():
    return _make_uuid()


@pytest.fixture
def stage_id():
    return _make_uuid()


@pytest.fixture
def sample_stage_row(deal_id, stage_id):
    """A single logistics stage row as returned from DB."""
    return {
        "id": stage_id,
        "deal_id": deal_id,
        "stage_code": "first_mile",
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "responsible_person": None,
        "notes": None,
        "svh_id": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_seven_stages(deal_id):
    """All 7 logistics stages for a deal (as returned from DB)."""
    stages = []
    for i, code in enumerate(EXPECTED_STAGE_CODES):
        stages.append({
            "id": _make_uuid(),
            "deal_id": deal_id,
            "stage_code": code,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "responsible_person": None,
            "notes": None,
            "svh_id": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
    return stages


@pytest.fixture
def sample_expense_items(deal_id, stage_id):
    """Sample plan_fact_items linked to a logistics stage."""
    return [
        {
            "id": _make_uuid(),
            "deal_id": deal_id,
            "category_id": _make_uuid(),
            "description": "Delivery to warehouse",
            "planned_amount": 15000.00,
            "planned_currency": "RUB",
            "planned_date": "2026-02-15",
            "actual_amount": 14500.00,
            "actual_currency": "RUB",
            "actual_date": "2026-02-14",
            "variance_amount": -500.00,
            "logistics_stage_id": stage_id,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": _make_uuid(),
            "deal_id": deal_id,
            "category_id": _make_uuid(),
            "description": "Insurance for first mile",
            "planned_amount": 5000.00,
            "planned_currency": "RUB",
            "planned_date": "2026-02-16",
            "actual_amount": None,
            "actual_currency": None,
            "actual_date": None,
            "variance_amount": None,
            "logistics_stage_id": stage_id,
            "created_at": datetime.now().isoformat(),
        },
    ]


# ==============================================================================
# PART 1: Module Import and Data Classes
# ==============================================================================

class TestLogisticsServiceImport:
    """The logistics_service module must exist and be importable."""

    def test_logistics_service_module_exists(self):
        """services/logistics_service.py must exist."""
        from services import logistics_service
        assert logistics_service is not None

    def test_logistics_stage_dataclass_exists(self):
        """LogisticsStage dataclass must be defined."""
        from services.logistics_service import LogisticsStage
        assert LogisticsStage is not None

    def test_stage_codes_constant_exists(self):
        """STAGE_CODES constant must be defined with exactly 7 codes."""
        from services.logistics_service import STAGE_CODES
        assert isinstance(STAGE_CODES, (list, tuple))
        assert len(STAGE_CODES) == EXPECTED_STAGE_COUNT

    def test_stage_codes_match_expected(self):
        """STAGE_CODES must contain the exact expected codes in order."""
        from services.logistics_service import STAGE_CODES
        for code in EXPECTED_STAGE_CODES:
            assert code in STAGE_CODES, (
                f"Stage code '{code}' must be in STAGE_CODES"
            )

    def test_stage_codes_order(self):
        """STAGE_CODES must be in the correct order (first_mile -> last_mile)."""
        from services.logistics_service import STAGE_CODES
        assert list(STAGE_CODES) == EXPECTED_STAGE_CODES, (
            f"Stage codes must be ordered: {EXPECTED_STAGE_CODES}"
        )


# ==============================================================================
# PART 2: Initialize Logistics Stages
# ==============================================================================

class TestInitializeLogisticsStages:
    """initialize_logistics_stages must create all 7 stages for a deal."""

    def test_function_exists(self):
        """initialize_logistics_stages must be importable."""
        from services.logistics_service import initialize_logistics_stages
        assert callable(initialize_logistics_stages)

    def test_creates_exactly_seven_stages(self, deal_id, user_id):
        """Must create exactly 7 stages when called."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # Mock insert to return data with generated IDs
            created_stages = []
            for code in EXPECTED_STAGE_CODES:
                created_stages.append({
                    "id": _make_uuid(),
                    "deal_id": deal_id,
                    "stage_code": code,
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "responsible_person": None,
                    "notes": None,
                    "svh_id": None,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                })

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.insert.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=created_stages)

            from services.logistics_service import initialize_logistics_stages
            result = initialize_logistics_stages(deal_id, user_id)

            assert result is not None
            assert len(result) == EXPECTED_STAGE_COUNT, (
                f"Expected {EXPECTED_STAGE_COUNT} stages, got {len(result)}"
            )

    def test_all_stages_start_as_pending(self, deal_id, user_id):
        """All 7 stages must start with status='pending'."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            created_stages = []
            for code in EXPECTED_STAGE_CODES:
                created_stages.append({
                    "id": _make_uuid(),
                    "deal_id": deal_id,
                    "stage_code": code,
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "responsible_person": None,
                    "notes": None,
                    "svh_id": None,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                })

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.insert.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=created_stages)

            from services.logistics_service import initialize_logistics_stages
            result = initialize_logistics_stages(deal_id, user_id)

            for stage in result:
                # stage may be a dataclass or dict
                status = stage.status if hasattr(stage, 'status') else stage.get('status')
                assert status == 'pending', (
                    f"Stage {stage} must start with status='pending'"
                )

    def test_stage_codes_are_correct(self, deal_id, user_id):
        """The 7 stages must have codes matching the expected list."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            created_stages = []
            for code in EXPECTED_STAGE_CODES:
                created_stages.append({
                    "id": _make_uuid(),
                    "deal_id": deal_id,
                    "stage_code": code,
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "responsible_person": None,
                    "notes": None,
                    "svh_id": None,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                })

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.insert.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=created_stages)

            from services.logistics_service import initialize_logistics_stages
            result = initialize_logistics_stages(deal_id, user_id)

            result_codes = []
            for stage in result:
                code = stage.stage_code if hasattr(stage, 'stage_code') else stage.get('stage_code')
                result_codes.append(code)

            assert sorted(result_codes) == sorted(EXPECTED_STAGE_CODES), (
                f"Stage codes mismatch. Expected {sorted(EXPECTED_STAGE_CODES)}, "
                f"got {sorted(result_codes)}"
            )

    def test_inserts_into_logistics_stages_table(self, deal_id, user_id):
        """Must insert into 'logistics_stages' table."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.insert.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[{
                "id": _make_uuid(),
                "deal_id": deal_id,
                "stage_code": "first_mile",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }] * 7)

            from services.logistics_service import initialize_logistics_stages
            initialize_logistics_stages(deal_id, user_id)

            mock_client.table.assert_called_with('logistics_stages')


# ==============================================================================
# PART 3: Get Stages for Deal
# ==============================================================================

class TestGetStagesForDeal:
    """get_stages_for_deal must return stages in correct order."""

    def test_function_exists(self):
        """get_stages_for_deal must be importable."""
        from services.logistics_service import get_stages_for_deal
        assert callable(get_stages_for_deal)

    def test_returns_stages_in_correct_order(self, deal_id, sample_seven_stages):
        """Stages must be returned in the predefined order."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # Return stages in random order from DB
            import random
            shuffled = list(sample_seven_stages)
            random.shuffle(shuffled)

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=shuffled)

            from services.logistics_service import get_stages_for_deal
            result = get_stages_for_deal(deal_id)

            # Result should be ordered by stage sequence
            result_codes = []
            for stage in result:
                code = stage.stage_code if hasattr(stage, 'stage_code') else stage.get('stage_code')
                result_codes.append(code)

            assert result_codes == EXPECTED_STAGE_CODES, (
                f"Stages must be ordered: {EXPECTED_STAGE_CODES}, got {result_codes}"
            )

    def test_returns_empty_list_for_nonexistent_deal(self):
        """Must return empty list if deal has no stages."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[])

            from services.logistics_service import get_stages_for_deal
            result = get_stages_for_deal(_make_uuid())

            assert result == [] or len(result) == 0


# ==============================================================================
# PART 4: Update Stage Status
# ==============================================================================

class TestUpdateStageStatus:
    """update_stage_status must handle status transitions correctly."""

    def test_function_exists(self):
        """update_stage_status must be importable."""
        from services.logistics_service import update_stage_status
        assert callable(update_stage_status)

    def test_pending_to_in_progress_sets_started_at(self, stage_id):
        """Transitioning to in_progress must auto-set started_at."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # Current stage is pending
            current_stage = {
                "id": stage_id,
                "deal_id": _make_uuid(),
                "stage_code": "first_mile",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # Updated stage with started_at set
            updated_stage = dict(current_stage)
            updated_stage["status"] = "in_progress"
            updated_stage["started_at"] = datetime.now().isoformat()

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.update.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[updated_stage])

            # First call returns current stage (for validation)
            mock_query.execute.side_effect = [
                MagicMock(data=[current_stage]),
                MagicMock(data=[updated_stage]),
            ]

            from services.logistics_service import update_stage_status
            result = update_stage_status(stage_id, 'in_progress')

            assert result is not None
            # Check started_at is set
            started_at = result.started_at if hasattr(result, 'started_at') else result.get('started_at')
            assert started_at is not None, (
                "Transitioning to in_progress must set started_at timestamp"
            )

    def test_in_progress_to_completed_sets_completed_at(self, stage_id):
        """Transitioning to completed must auto-set completed_at."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            current_stage = {
                "id": stage_id,
                "deal_id": _make_uuid(),
                "stage_code": "transit",
                "status": "in_progress",
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            updated_stage = dict(current_stage)
            updated_stage["status"] = "completed"
            updated_stage["completed_at"] = datetime.now().isoformat()

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.update.return_value = mock_query
            mock_query.execute.side_effect = [
                MagicMock(data=[current_stage]),
                MagicMock(data=[updated_stage]),
            ]

            from services.logistics_service import update_stage_status
            result = update_stage_status(stage_id, 'completed')

            assert result is not None
            completed_at = result.completed_at if hasattr(result, 'completed_at') else result.get('completed_at')
            assert completed_at is not None, (
                "Transitioning to completed must set completed_at timestamp"
            )

    def test_invalid_transition_completed_to_pending_rejected(self, stage_id):
        """completed -> pending transition must be rejected (invalid)."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            current_stage = {
                "id": stage_id,
                "deal_id": _make_uuid(),
                "stage_code": "first_mile",
                "status": "completed",
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[current_stage])

            from services.logistics_service import update_stage_status
            result = update_stage_status(stage_id, 'pending')

            # Should return None or raise an error for invalid transition
            assert result is None, (
                "completed -> pending is an invalid transition and must be rejected"
            )

    def test_invalid_transition_completed_to_in_progress_rejected(self, stage_id):
        """completed -> in_progress transition must be rejected (no rollback)."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            current_stage = {
                "id": stage_id,
                "deal_id": _make_uuid(),
                "stage_code": "hub",
                "status": "completed",
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[current_stage])

            from services.logistics_service import update_stage_status
            result = update_stage_status(stage_id, 'in_progress')

            assert result is None, (
                "completed -> in_progress is an invalid transition and must be rejected"
            )

    def test_pending_to_completed_direct_transition(self, stage_id):
        """pending -> completed may be allowed (skip in_progress)."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            current_stage = {
                "id": stage_id,
                "deal_id": _make_uuid(),
                "stage_code": "gtd_upload",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            updated_stage = dict(current_stage)
            updated_stage["status"] = "completed"
            updated_stage["completed_at"] = datetime.now().isoformat()

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.update.return_value = mock_query
            mock_query.execute.side_effect = [
                MagicMock(data=[current_stage]),
                MagicMock(data=[updated_stage]),
            ]

            from services.logistics_service import update_stage_status
            result = update_stage_status(stage_id, 'completed')

            # For gtd_upload, direct pending->completed should work
            assert result is not None, (
                "pending -> completed should be allowed (especially for gtd_upload)"
            )


# ==============================================================================
# PART 5: Get Expenses for Stage
# ==============================================================================

class TestGetExpensesForStage:
    """get_expenses_for_stage must return plan_fact_items linked to the stage."""

    def test_function_exists(self):
        """get_expenses_for_stage must be importable."""
        from services.logistics_service import get_expenses_for_stage
        assert callable(get_expenses_for_stage)

    def test_returns_only_expenses_for_given_stage(self, stage_id, sample_expense_items):
        """Must return only items where logistics_stage_id matches."""
        other_stage_id = _make_uuid()
        other_stage_item = {
            "id": _make_uuid(),
            "deal_id": sample_expense_items[0]["deal_id"],
            "category_id": _make_uuid(),
            "description": "Different stage expense",
            "planned_amount": 8000.00,
            "planned_currency": "USD",
            "planned_date": "2026-03-01",
            "actual_amount": None,
            "actual_currency": None,
            "actual_date": None,
            "variance_amount": None,
            "logistics_stage_id": other_stage_id,
            "created_at": datetime.now().isoformat(),
        }

        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # DB should only return items for the requested stage
            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=sample_expense_items)

            from services.logistics_service import get_expenses_for_stage
            result = get_expenses_for_stage(stage_id)

            assert len(result) == len(sample_expense_items), (
                f"Expected {len(sample_expense_items)} expenses, got {len(result)}"
            )

    def test_returns_empty_list_for_stage_with_no_expenses(self, stage_id):
        """Must return empty list if stage has no expenses."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[])

            from services.logistics_service import get_expenses_for_stage
            result = get_expenses_for_stage(stage_id)

            assert result == [] or len(result) == 0

    def test_queries_plan_fact_items_table(self, stage_id):
        """Must query plan_fact_items with logistics_stage_id filter."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[])

            from services.logistics_service import get_expenses_for_stage
            get_expenses_for_stage(stage_id)

            mock_client.table.assert_called_with('plan_fact_items')


# ==============================================================================
# PART 6: Stage Summary
# ==============================================================================

class TestGetStageSummary:
    """get_stage_summary must calculate totals correctly."""

    def test_function_exists(self):
        """get_stage_summary must be importable."""
        from services.logistics_service import get_stage_summary
        assert callable(get_stage_summary)

    def test_calculates_totals_correctly(self, stage_id, sample_expense_items):
        """Summary must include total_planned, total_actual, expense_count."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=sample_expense_items)

            from services.logistics_service import get_stage_summary
            result = get_stage_summary(stage_id)

            assert isinstance(result, dict), "Summary must be a dict"

            # Total planned: 15000 + 5000 = 20000
            total_planned = result.get('total_planned', 0)
            assert float(total_planned) == 20000.0, (
                f"Expected total_planned=20000.0, got {total_planned}"
            )

            # Total actual: 14500 + 0(None) = 14500
            total_actual = result.get('total_actual', 0)
            assert float(total_actual) == 14500.0, (
                f"Expected total_actual=14500.0, got {total_actual}"
            )

            # Expense count
            expense_count = result.get('expense_count', 0)
            assert expense_count == 2, (
                f"Expected expense_count=2, got {expense_count}"
            )

    def test_empty_stage_returns_zeroes(self, stage_id):
        """Summary for stage with no expenses must return all zeroes."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[])

            from services.logistics_service import get_stage_summary
            result = get_stage_summary(stage_id)

            assert isinstance(result, dict), "Summary must be a dict"
            assert float(result.get('total_planned', -1)) == 0.0
            assert float(result.get('total_actual', -1)) == 0.0
            assert result.get('expense_count', -1) == 0


# ==============================================================================
# PART 7: GTD Upload Stage Has No Expense Capability
# ==============================================================================

class TestGtdUploadStageNoExpenses:
    """gtd_upload stage must not allow expenses."""

    def test_stage_has_expense_capability_function_exists(self):
        """stage_allows_expenses (or similar) function must exist."""
        from services.logistics_service import stage_allows_expenses
        assert callable(stage_allows_expenses)

    def test_gtd_upload_does_not_allow_expenses(self):
        """gtd_upload stage must return False for expense capability."""
        from services.logistics_service import stage_allows_expenses
        assert stage_allows_expenses('gtd_upload') is False, (
            "gtd_upload stage must not allow expenses"
        )

    def test_first_mile_allows_expenses(self):
        """first_mile stage must allow expenses."""
        from services.logistics_service import stage_allows_expenses
        assert stage_allows_expenses('first_mile') is True

    def test_all_non_gtd_stages_allow_expenses(self):
        """All stages except gtd_upload must allow expenses."""
        from services.logistics_service import stage_allows_expenses
        for code in EXPENSE_ALLOWED_STAGES:
            assert stage_allows_expenses(code) is True, (
                f"Stage '{code}' must allow expenses"
            )

    def test_hub_allows_expenses(self):
        """hub stage must allow expenses."""
        from services.logistics_service import stage_allows_expenses
        assert stage_allows_expenses('hub') is True

    def test_last_mile_allows_expenses(self):
        """last_mile stage must allow expenses."""
        from services.logistics_service import stage_allows_expenses
        assert stage_allows_expenses('last_mile') is True


# ==============================================================================
# PART 8: Stage Status Transition Validation
# ==============================================================================

class TestStageStatusTransitions:
    """Valid status transitions: pending->in_progress->completed, pending->completed."""

    def test_valid_transitions_constant_exists(self):
        """STAGE_TRANSITIONS constant must be defined."""
        from services.logistics_service import STAGE_TRANSITIONS
        assert isinstance(STAGE_TRANSITIONS, dict)

    def test_pending_can_transition_to_in_progress(self):
        """pending -> in_progress is a valid transition."""
        from services.logistics_service import STAGE_TRANSITIONS
        allowed = STAGE_TRANSITIONS.get('pending', [])
        assert 'in_progress' in allowed, (
            "pending must be able to transition to in_progress"
        )

    def test_pending_can_transition_to_completed(self):
        """pending -> completed is a valid transition (skip step)."""
        from services.logistics_service import STAGE_TRANSITIONS
        allowed = STAGE_TRANSITIONS.get('pending', [])
        assert 'completed' in allowed, (
            "pending must be able to transition to completed (direct)"
        )

    def test_in_progress_can_transition_to_completed(self):
        """in_progress -> completed is a valid transition."""
        from services.logistics_service import STAGE_TRANSITIONS
        allowed = STAGE_TRANSITIONS.get('in_progress', [])
        assert 'completed' in allowed, (
            "in_progress must be able to transition to completed"
        )

    def test_completed_is_terminal(self):
        """completed is a terminal status (no transitions out)."""
        from services.logistics_service import STAGE_TRANSITIONS
        allowed = STAGE_TRANSITIONS.get('completed', [])
        assert len(allowed) == 0, (
            "completed must be a terminal status with no outgoing transitions"
        )


# ==============================================================================
# PART 9: Add Expense to Stage (Service-Level)
# ==============================================================================

class TestAddExpenseToStage:
    """add_expense_to_stage creates a plan_fact_item linked to the stage."""

    def test_function_exists(self):
        """add_expense_to_stage must be importable."""
        from services.logistics_service import add_expense_to_stage
        assert callable(add_expense_to_stage)

    def test_creates_plan_fact_item_with_logistics_stage_id(self, deal_id, stage_id, user_id):
        """Must create plan_fact_item with logistics_stage_id set."""
        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # Mock stage lookup (to verify it exists and allows expenses)
            stage_data = {
                "id": stage_id,
                "deal_id": deal_id,
                "stage_code": "first_mile",
                "status": "in_progress",
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            created_item = {
                "id": _make_uuid(),
                "deal_id": deal_id,
                "category_id": _make_uuid(),
                "description": "Trucking fee",
                "planned_amount": 25000.00,
                "planned_currency": "RUB",
                "planned_date": "2026-02-20",
                "actual_amount": None,
                "actual_currency": None,
                "actual_date": None,
                "variance_amount": None,
                "logistics_stage_id": stage_id,
                "created_at": datetime.now().isoformat(),
            }

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.insert.return_value = mock_query
            mock_query.execute.side_effect = [
                MagicMock(data=[stage_data]),  # stage lookup
                MagicMock(data=[created_item]),  # item creation
            ]

            from services.logistics_service import add_expense_to_stage
            result = add_expense_to_stage(
                deal_id=deal_id,
                stage_id=stage_id,
                description="Trucking fee",
                amount=25000.00,
                currency="RUB",
                expense_date="2026-02-20",
                created_by=user_id,
            )

            assert result is not None, "add_expense_to_stage must return created item"

    def test_rejects_expense_on_gtd_upload_stage(self, deal_id, user_id):
        """Must reject adding expense to gtd_upload stage."""
        gtd_stage_id = _make_uuid()

        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            gtd_stage = {
                "id": gtd_stage_id,
                "deal_id": deal_id,
                "stage_code": "gtd_upload",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "responsible_person": None,
                "notes": None,
                "svh_id": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[gtd_stage])

            from services.logistics_service import add_expense_to_stage
            result = add_expense_to_stage(
                deal_id=deal_id,
                stage_id=gtd_stage_id,
                description="Should fail",
                amount=1000.00,
                currency="RUB",
                expense_date="2026-02-20",
                created_by=user_id,
            )

            assert result is None, (
                "add_expense_to_stage must reject expenses on gtd_upload stage"
            )

    def test_accepts_multiple_currencies(self, deal_id, stage_id, user_id):
        """Expenses should support USD, EUR, RUB and other currencies."""
        currencies = ['USD', 'EUR', 'RUB', 'CNY', 'GBP']

        for currency in currencies:
            with patch('services.logistics_service.get_supabase') as mock_sb:
                mock_client = MagicMock()
                mock_sb.return_value = mock_client

                stage_data = {
                    "id": stage_id,
                    "deal_id": deal_id,
                    "stage_code": "transit",
                    "status": "in_progress",
                    "started_at": datetime.now().isoformat(),
                    "completed_at": None,
                    "responsible_person": None,
                    "notes": None,
                    "svh_id": None,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }

                created_item = {
                    "id": _make_uuid(),
                    "deal_id": deal_id,
                    "category_id": _make_uuid(),
                    "description": f"Expense in {currency}",
                    "planned_amount": 1000.00,
                    "planned_currency": currency,
                    "planned_date": "2026-03-01",
                    "actual_amount": None,
                    "actual_currency": None,
                    "actual_date": None,
                    "variance_amount": None,
                    "logistics_stage_id": stage_id,
                    "created_at": datetime.now().isoformat(),
                }

                mock_query = MagicMock()
                mock_client.table.return_value = mock_query
                mock_query.select.return_value = mock_query
                mock_query.eq.return_value = mock_query
                mock_query.insert.return_value = mock_query
                mock_query.execute.side_effect = [
                    MagicMock(data=[stage_data]),
                    MagicMock(data=[created_item]),
                ]

                from services.logistics_service import add_expense_to_stage
                result = add_expense_to_stage(
                    deal_id=deal_id,
                    stage_id=stage_id,
                    description=f"Expense in {currency}",
                    amount=1000.00,
                    currency=currency,
                    expense_date="2026-03-01",
                    created_by=user_id,
                )

                assert result is not None, (
                    f"add_expense_to_stage must accept {currency} currency"
                )


# ==============================================================================
# PART 10: Multiple Expenses Per Stage
# ==============================================================================

class TestMultipleExpensesPerStage:
    """A stage can have multiple expenses."""

    def test_multiple_expenses_returned(self, stage_id, sample_expense_items):
        """get_expenses_for_stage must return all expenses for a stage."""
        # Add a third expense to the sample
        third_expense = {
            "id": _make_uuid(),
            "deal_id": sample_expense_items[0]["deal_id"],
            "category_id": _make_uuid(),
            "description": "Third expense for stage",
            "planned_amount": 3000.00,
            "planned_currency": "EUR",
            "planned_date": "2026-02-20",
            "actual_amount": None,
            "actual_currency": None,
            "actual_date": None,
            "variance_amount": None,
            "logistics_stage_id": stage_id,
            "created_at": datetime.now().isoformat(),
        }
        all_expenses = sample_expense_items + [third_expense]

        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=all_expenses)

            from services.logistics_service import get_expenses_for_stage
            result = get_expenses_for_stage(stage_id)

            assert len(result) == 3, (
                f"Expected 3 expenses, got {len(result)}"
            )

    def test_stage_summary_updates_with_multiple_expenses(self, stage_id):
        """Summary totals must reflect all expenses in the stage."""
        expenses = [
            {
                "id": _make_uuid(),
                "planned_amount": 10000.00,
                "actual_amount": 10000.00,
                "logistics_stage_id": stage_id,
            },
            {
                "id": _make_uuid(),
                "planned_amount": 20000.00,
                "actual_amount": 18000.00,
                "logistics_stage_id": stage_id,
            },
            {
                "id": _make_uuid(),
                "planned_amount": 5000.00,
                "actual_amount": None,
                "logistics_stage_id": stage_id,
            },
        ]

        with patch('services.logistics_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=expenses)

            from services.logistics_service import get_stage_summary
            result = get_stage_summary(stage_id)

            # total_planned: 10000 + 20000 + 5000 = 35000
            assert float(result.get('total_planned', 0)) == 35000.0
            # total_actual: 10000 + 18000 + 0 = 28000
            assert float(result.get('total_actual', 0)) == 28000.0
            # expense_count: 3
            assert result.get('expense_count', 0) == 3


# ==============================================================================
# PART 11: Stage Display Names
# ==============================================================================

class TestStageDisplayNames:
    """Each stage code must have a human-readable display name."""

    def test_stage_names_constant_exists(self):
        """STAGE_NAMES dict must be defined."""
        from services.logistics_service import STAGE_NAMES
        assert isinstance(STAGE_NAMES, dict)

    def test_all_stage_codes_have_names(self):
        """Every stage code must have a display name."""
        from services.logistics_service import STAGE_NAMES
        for code in EXPECTED_STAGE_CODES:
            assert code in STAGE_NAMES, (
                f"Stage code '{code}' must have a display name in STAGE_NAMES"
            )

    def test_stage_names_are_non_empty_strings(self):
        """Display names must be non-empty strings."""
        from services.logistics_service import STAGE_NAMES
        for code, name in STAGE_NAMES.items():
            assert isinstance(name, str) and len(name) > 0, (
                f"Stage name for '{code}' must be a non-empty string"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
