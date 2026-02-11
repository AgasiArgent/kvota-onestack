"""
Logistics Service

CRUD operations for logistics_stages table.
Handles the 7-stage logistics lifecycle per deal:
  first_mile -> hub -> hub_hub -> transit -> post_transit -> gtd_upload -> last_mile

Each stage tracks status (pending/in_progress/completed) with timestamps.
Expenses are stored as plan_fact_items with a logistics_stage_id FK.
The gtd_upload stage has NO expense capability (status flag only).

Feature P2.7+P2.8
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from .database import get_supabase


# ============================================================================
# Constants
# ============================================================================

STAGE_CODES = [
    'first_mile',
    'hub',
    'hub_hub',
    'transit',
    'post_transit',
    'gtd_upload',
    'last_mile',
]

STAGE_NAMES = {
    'first_mile': 'Первая миля',
    'hub': 'Хаб',
    'hub_hub': 'Хаб — Хаб',
    'transit': 'Транзит',
    'post_transit': 'Пост-транзит',
    'gtd_upload': 'Загрузка ГТД',
    'last_mile': 'Последняя миля',
}

# Valid status transitions: pending -> in_progress -> completed, or pending -> completed
STAGE_TRANSITIONS = {
    'pending': ['in_progress', 'completed'],
    'in_progress': ['completed'],
    'completed': [],  # Terminal status
}

# Stage code -> plan_fact_category code mapping
STAGE_CATEGORY_MAP = {
    'first_mile': 'logistics_first_mile',
    'hub': 'logistics_hub',
    'hub_hub': 'logistics_hub_hub',
    'transit': 'logistics_transit',
    'post_transit': 'logistics_post_transit',
    'last_mile': 'logistics_last_mile',
    # gtd_upload has no category (no expenses)
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class LogisticsStage:
    """Represents a logistics stage for a deal."""
    id: str
    deal_id: str
    stage_code: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    responsible_person: Optional[str]
    notes: Optional[str]
    svh_id: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict) -> 'LogisticsStage':
        """Create a LogisticsStage instance from a dictionary."""
        return cls(
            id=data['id'],
            deal_id=data['deal_id'],
            stage_code=data['stage_code'],
            status=data.get('status', 'pending'),
            started_at=data.get('started_at'),
            completed_at=data.get('completed_at'),
            responsible_person=data.get('responsible_person'),
            notes=data.get('notes'),
            svh_id=data.get('svh_id'),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
        )


# ============================================================================
# Helper Functions
# ============================================================================

def stage_allows_expenses(stage_code: str) -> bool:
    """Check if a stage allows expense tracking.

    All stages except gtd_upload allow expenses.
    """
    return stage_code != 'gtd_upload'


def _sort_stages(stages: list) -> list:
    """Sort stages by the predefined STAGE_CODES order."""
    code_order = {code: idx for idx, code in enumerate(STAGE_CODES)}

    def sort_key(stage):
        if hasattr(stage, 'stage_code'):
            code = stage.stage_code
        elif isinstance(stage, dict):
            code = stage.get('stage_code', '')
        else:
            code = ''
        return code_order.get(code, 999)

    return sorted(stages, key=sort_key)


# ============================================================================
# Initialize Stages
# ============================================================================

def initialize_logistics_stages(deal_id: str, user_id: str) -> List[LogisticsStage]:
    """
    Create all 7 logistics stages for a deal.

    Called automatically when a deal is created.
    All stages start with status='pending'.

    Args:
        deal_id: UUID of the deal
        user_id: UUID of the user creating the stages

    Returns:
        List of 7 LogisticsStage objects
    """
    supabase = get_supabase()

    rows = []
    for code in STAGE_CODES:
        rows.append({
            'deal_id': deal_id,
            'stage_code': code,
            'status': 'pending',
        })

    try:
        result = supabase.table('logistics_stages').insert(rows).execute()
        if result.data:
            return [LogisticsStage.from_dict(row) for row in result.data]
        return []
    except Exception as e:
        print(f"Error initializing logistics stages: {e}")
        return []


# ============================================================================
# Read Operations
# ============================================================================

def get_stages_for_deal(deal_id: str) -> List[LogisticsStage]:
    """
    Get all logistics stages for a deal, sorted in the predefined order.

    Args:
        deal_id: UUID of the deal

    Returns:
        List of LogisticsStage objects in order: first_mile -> last_mile
    """
    supabase = get_supabase()

    try:
        result = supabase.table('logistics_stages') \
            .select('*') \
            .eq('deal_id', deal_id) \
            .order('created_at') \
            .execute()

        if not result.data:
            return []

        stages = [LogisticsStage.from_dict(row) for row in result.data]
        return _sort_stages(stages)
    except Exception as e:
        print(f"Error getting stages for deal: {e}")
        return []


# ============================================================================
# Update Stage Status
# ============================================================================

def update_stage_status(stage_id: str, new_status: str, deal_id: str = None) -> Optional[LogisticsStage]:
    """
    Update a stage's status with transition validation.

    Valid transitions:
      pending -> in_progress  (auto-sets started_at)
      pending -> completed    (auto-sets completed_at)
      in_progress -> completed (auto-sets completed_at)
      completed -> * is REJECTED (terminal status)

    Args:
        stage_id: UUID of the stage
        new_status: Target status
        deal_id: UUID of the deal (for IDOR protection - validates stage belongs to deal)

    Returns:
        Updated LogisticsStage if valid, None if invalid transition or deal mismatch
    """
    supabase = get_supabase()

    try:
        # Fetch current stage
        current_result = supabase.table('logistics_stages') \
            .select('*') \
            .eq('id', stage_id) \
            .execute()

        if not current_result.data:
            return None

        current = current_result.data[0]

        # IDOR protection: verify stage belongs to the expected deal
        if deal_id and current.get('deal_id') != deal_id:
            return None

        current_status = current.get('status', 'pending')

        # Validate transition
        allowed = STAGE_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            return None

        # Build update payload
        update_data = {'status': new_status}
        now = datetime.now().isoformat()

        if new_status == 'in_progress' and not current.get('started_at'):
            update_data['started_at'] = now

        if new_status == 'completed':
            update_data['completed_at'] = now
            # Also set started_at if skipping directly from pending
            if not current.get('started_at'):
                update_data['started_at'] = now

        result = supabase.table('logistics_stages') \
            .update(update_data) \
            .eq('id', stage_id) \
            .execute()

        if result.data:
            return LogisticsStage.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error updating stage status: {e}")
        return None


# ============================================================================
# Expense Operations
# ============================================================================

def get_expenses_for_stage(stage_id: str) -> list:
    """
    Get all plan_fact_items linked to a logistics stage.

    Args:
        stage_id: UUID of the logistics stage

    Returns:
        List of plan_fact_item dicts
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_items') \
            .select('*') \
            .eq('logistics_stage_id', stage_id) \
            .order('created_at') \
            .execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting expenses for stage: {e}")
        return []


def add_expense_to_stage(
    deal_id: str,
    stage_id: str,
    description: str,
    amount: float,
    currency: str,
    expense_date: str,
    created_by: str,
    category_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Add an expense (plan_fact_item) linked to a logistics stage.

    Rejects expenses on gtd_upload stage.

    Args:
        deal_id: UUID of the deal
        stage_id: UUID of the logistics stage
        description: Expense description
        amount: Actual amount spent
        currency: Currency code (RUB, USD, EUR, etc.)
        expense_date: Actual date of expense (YYYY-MM-DD)
        created_by: UUID of the user
        category_id: Optional UUID of the plan_fact_category.
                     If not provided, looked up from STAGE_CATEGORY_MAP.

    Returns:
        Created plan_fact_item dict, or None if rejected
    """
    supabase = get_supabase()

    try:
        # Fetch the stage to check if expenses are allowed
        stage_result = supabase.table('logistics_stages') \
            .select('*') \
            .eq('id', stage_id) \
            .execute()

        if not stage_result.data:
            return None

        stage = stage_result.data[0]

        # IDOR protection: verify stage belongs to the expected deal
        if stage.get('deal_id') != deal_id:
            return None

        stage_code = stage.get('stage_code', '')

        # Reject expenses on gtd_upload stage
        if not stage_allows_expenses(stage_code):
            return None

        # Resolve category_id: use provided value or look up from STAGE_CATEGORY_MAP
        resolved_category_id = category_id
        if not resolved_category_id:
            cat_code = STAGE_CATEGORY_MAP.get(stage_code)
            if cat_code:
                cat_result = supabase.table('plan_fact_categories') \
                    .select('id') \
                    .eq('code', cat_code) \
                    .execute()
                if cat_result.data:
                    resolved_category_id = cat_result.data[0]['id']

        if not resolved_category_id:
            print(f"Error adding expense: no category found for stage_code={stage_code}")
            return None

        # Build insert data
        item_data = {
            'deal_id': deal_id,
            'category_id': resolved_category_id,
            'description': description,
            'actual_amount': amount,
            'actual_currency': currency,
            'actual_date': expense_date,
            'logistics_stage_id': stage_id,
            'created_by': created_by,
        }

        result = supabase.table('plan_fact_items').insert(item_data).execute()

        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error adding expense to stage: {e}")
        return None


# ============================================================================
# Stage Summary
# ============================================================================

def get_stage_summary(stage_id: str) -> dict:
    """
    Calculate summary totals for a logistics stage.

    Args:
        stage_id: UUID of the logistics stage

    Returns:
        Dict with total_planned, total_actual, expense_count
    """
    expenses = get_expenses_for_stage(stage_id)

    total_planned = 0.0
    total_actual = 0.0
    expense_count = len(expenses)

    for item in expenses:
        planned = item.get('planned_amount')
        if planned is not None:
            total_planned += float(planned)

        actual = item.get('actual_amount')
        if actual is not None:
            total_actual += float(actual)

    return {
        'total_planned': total_planned,
        'total_actual': total_actual,
        'expense_count': expense_count,
    }
