"""
Plan-Fact Service

CRUD operations for the plan_fact_items and plan_fact_categories tables.
Handles plan-fact tracking for deals - planned vs actual payments.

Feature #81 from features.json
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
from .database import get_supabase


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PlanFactCategory:
    """Represents a plan-fact category (payment type)."""
    id: str
    code: str
    name: str
    is_income: bool
    sort_order: int
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> 'PlanFactCategory':
        """Create a PlanFactCategory instance from a dictionary."""
        return cls(
            id=data['id'],
            code=data['code'],
            name=data['name'],
            is_income=data.get('is_income', False),
            sort_order=data.get('sort_order', 0),
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')) if isinstance(data['created_at'], str) else data['created_at'],
        )


@dataclass
class PlanFactItem:
    """Represents a plan-fact item (planned/actual payment)."""
    id: str
    deal_id: str
    category_id: str

    # Description
    description: Optional[str]

    # Planned payment info
    planned_amount: Decimal
    planned_currency: str
    planned_date: date

    # Actual payment info (null if not yet paid)
    actual_amount: Optional[Decimal]
    actual_currency: Optional[str]
    actual_date: Optional[date]
    actual_exchange_rate: Optional[Decimal]

    # Variance tracking
    variance_amount: Optional[Decimal]

    # Documentation
    payment_document: Optional[str]
    notes: Optional[str]

    # Audit
    created_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_dict(cls, data: dict) -> 'PlanFactItem':
        """Create a PlanFactItem instance from a dictionary."""
        return cls(
            id=data['id'],
            deal_id=data['deal_id'],
            category_id=data['category_id'],

            # Description
            description=data.get('description'),

            # Planned
            planned_amount=Decimal(str(data['planned_amount'])) if data.get('planned_amount') is not None else Decimal('0'),
            planned_currency=data.get('planned_currency', 'RUB'),
            planned_date=datetime.strptime(data['planned_date'], '%Y-%m-%d').date() if isinstance(data.get('planned_date'), str) else data.get('planned_date'),

            # Actual
            actual_amount=Decimal(str(data['actual_amount'])) if data.get('actual_amount') is not None else None,
            actual_currency=data.get('actual_currency'),
            actual_date=datetime.strptime(data['actual_date'], '%Y-%m-%d').date() if isinstance(data.get('actual_date'), str) else data.get('actual_date'),
            actual_exchange_rate=Decimal(str(data['actual_exchange_rate'])) if data.get('actual_exchange_rate') is not None else None,

            # Variance
            variance_amount=Decimal(str(data['variance_amount'])) if data.get('variance_amount') is not None else None,

            # Documentation
            payment_document=data.get('payment_document'),
            notes=data.get('notes'),

            # Audit
            created_by=data.get('created_by'),
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')) if isinstance(data['created_at'], str) else data['created_at'],
            updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')) if data.get('updated_at') and isinstance(data['updated_at'], str) else data.get('updated_at'),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'deal_id': self.deal_id,
            'category_id': self.category_id,
            'description': self.description,
            'planned_amount': float(self.planned_amount) if self.planned_amount else None,
            'planned_currency': self.planned_currency,
            'planned_date': self.planned_date.isoformat() if self.planned_date else None,
            'actual_amount': float(self.actual_amount) if self.actual_amount else None,
            'actual_currency': self.actual_currency,
            'actual_date': self.actual_date.isoformat() if self.actual_date else None,
            'actual_exchange_rate': float(self.actual_exchange_rate) if self.actual_exchange_rate else None,
            'payment_document': self.payment_document,
            'notes': self.notes,
            'created_by': self.created_by,
        }

    @property
    def is_paid(self) -> bool:
        """Check if this item has been paid."""
        return self.actual_amount is not None and self.actual_date is not None


# ============================================================================
# Category Functions
# ============================================================================

def get_all_categories() -> List[PlanFactCategory]:
    """
    Get all plan-fact categories ordered by sort_order.

    Returns:
        List of PlanFactCategory objects
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_categories').select('*') \
            .order('sort_order') \
            .execute()

        return [PlanFactCategory.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting categories: {e}")
        return []


def get_category(category_id: str) -> Optional[PlanFactCategory]:
    """
    Get a category by ID.

    Args:
        category_id: UUID of the category

    Returns:
        PlanFactCategory object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_categories').select('*') \
            .eq('id', category_id) \
            .execute()

        if result.data:
            return PlanFactCategory.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting category: {e}")
        return None


def get_category_by_code(code: str) -> Optional[PlanFactCategory]:
    """
    Get a category by code.

    Args:
        code: Category code (e.g., 'client_payment', 'supplier_payment')

    Returns:
        PlanFactCategory object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_categories').select('*') \
            .eq('code', code) \
            .execute()

        if result.data:
            return PlanFactCategory.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting category by code: {e}")
        return None


def get_income_categories() -> List[PlanFactCategory]:
    """Get all income categories."""
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_categories').select('*') \
            .eq('is_income', True) \
            .order('sort_order') \
            .execute()

        return [PlanFactCategory.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting income categories: {e}")
        return []


def get_expense_categories() -> List[PlanFactCategory]:
    """Get all expense categories."""
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_categories').select('*') \
            .eq('is_income', False) \
            .order('sort_order') \
            .execute()

        return [PlanFactCategory.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting expense categories: {e}")
        return []


# ============================================================================
# CREATE Operations
# ============================================================================

def create_plan_fact_item(
    deal_id: str,
    category_id: str,
    planned_amount: float,
    planned_date: date,
    planned_currency: str = 'RUB',
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> Optional[PlanFactItem]:
    """
    Create a new plan-fact item.

    Args:
        deal_id: ID of the deal this item belongs to
        category_id: ID of the payment category
        planned_amount: Planned payment amount
        planned_date: Planned payment date
        planned_currency: Currency of planned payment (default: RUB)
        description: Optional description of the payment
        created_by: ID of the user creating the item

    Returns:
        PlanFactItem object if created successfully, None on error

    Example:
        item = create_plan_fact_item(
            deal_id='deal-123',
            category_id='cat-456',
            planned_amount=100000.00,
            planned_date=date(2025, 2, 15),
            description='First client payment (50%)',
            created_by='user-789'
        )
    """
    supabase = get_supabase()

    try:
        item_data = {
            'deal_id': deal_id,
            'category_id': category_id,
            'planned_amount': planned_amount,
            'planned_currency': planned_currency,
            'planned_date': planned_date.isoformat() if isinstance(planned_date, date) else planned_date,
        }

        if description:
            item_data['description'] = description
        if created_by:
            item_data['created_by'] = created_by

        result = supabase.table('plan_fact_items').insert(item_data).execute()

        if result.data:
            return PlanFactItem.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error creating plan-fact item: {e}")
        return None


def create_plan_fact_item_with_category_code(
    deal_id: str,
    category_code: str,
    planned_amount: float,
    planned_date: date,
    planned_currency: str = 'RUB',
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> Optional[PlanFactItem]:
    """
    Create a new plan-fact item using category code instead of ID.

    Args:
        deal_id: ID of the deal
        category_code: Category code (e.g., 'client_payment')
        planned_amount: Planned payment amount
        planned_date: Planned payment date
        planned_currency: Currency (default: RUB)
        description: Optional description
        created_by: ID of the user

    Returns:
        PlanFactItem object if created successfully, None on error
    """
    category = get_category_by_code(category_code)
    if not category:
        print(f"Category not found: {category_code}")
        return None

    return create_plan_fact_item(
        deal_id=deal_id,
        category_id=category.id,
        planned_amount=planned_amount,
        planned_date=planned_date,
        planned_currency=planned_currency,
        description=description,
        created_by=created_by
    )


def bulk_create_plan_fact_items(
    deal_id: str,
    items: List[Dict[str, Any]],
    created_by: Optional[str] = None
) -> List[PlanFactItem]:
    """
    Create multiple plan-fact items at once.

    Args:
        deal_id: ID of the deal
        items: List of item dicts with keys: category_id/category_code, planned_amount, planned_date, etc.
        created_by: ID of the user

    Returns:
        List of created PlanFactItem objects

    Example:
        items = bulk_create_plan_fact_items('deal-123', [
            {'category_code': 'client_payment', 'planned_amount': 50000, 'planned_date': date(2025, 1, 15), 'description': 'First payment'},
            {'category_code': 'supplier_payment', 'planned_amount': 30000, 'planned_date': date(2025, 1, 20)},
        ])
    """
    created_items = []

    for item in items:
        # Support both category_id and category_code
        category_id = item.get('category_id')
        if not category_id and item.get('category_code'):
            cat = get_category_by_code(item['category_code'])
            if cat:
                category_id = cat.id

        if not category_id:
            print(f"Skipping item - no valid category: {item}")
            continue

        created = create_plan_fact_item(
            deal_id=deal_id,
            category_id=category_id,
            planned_amount=item['planned_amount'],
            planned_date=item['planned_date'],
            planned_currency=item.get('planned_currency', 'RUB'),
            description=item.get('description'),
            created_by=created_by
        )

        if created:
            created_items.append(created)

    return created_items


# ============================================================================
# READ Operations
# ============================================================================

def get_plan_fact_item(item_id: str) -> Optional[PlanFactItem]:
    """
    Get a single plan-fact item by ID.

    Args:
        item_id: UUID of the item

    Returns:
        PlanFactItem object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_items').select('*') \
            .eq('id', item_id) \
            .execute()

        if result.data:
            return PlanFactItem.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting plan-fact item: {e}")
        return None


def get_plan_fact_items_for_deal(
    deal_id: str,
    include_category: bool = False
) -> List[Any]:
    """
    Get all plan-fact items for a deal.

    Args:
        deal_id: UUID of the deal
        include_category: Whether to include category details

    Returns:
        List of PlanFactItem objects (or dicts if include_category=True)
    """
    supabase = get_supabase()

    try:
        if include_category:
            result = supabase.table('plan_fact_items').select(
                '*, plan_fact_categories(id, code, name, is_income, sort_order)'
            ).eq('deal_id', deal_id).order('planned_date').execute()

            return result.data if result.data else []
        else:
            result = supabase.table('plan_fact_items').select('*') \
                .eq('deal_id', deal_id) \
                .order('planned_date') \
                .execute()

            return [PlanFactItem.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting plan-fact items for deal: {e}")
        return []


def get_plan_fact_items_by_category(
    deal_id: str,
    category_id: str
) -> List[PlanFactItem]:
    """
    Get all plan-fact items for a specific category in a deal.

    Args:
        deal_id: UUID of the deal
        category_id: UUID of the category

    Returns:
        List of PlanFactItem objects
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_items').select('*') \
            .eq('deal_id', deal_id) \
            .eq('category_id', category_id) \
            .order('planned_date') \
            .execute()

        return [PlanFactItem.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting items by category: {e}")
        return []


def get_unpaid_items_for_deal(deal_id: str) -> List[PlanFactItem]:
    """
    Get all unpaid plan-fact items for a deal.

    Args:
        deal_id: UUID of the deal

    Returns:
        List of unpaid PlanFactItem objects
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_items').select('*') \
            .eq('deal_id', deal_id) \
            .is_('actual_amount', 'null') \
            .order('planned_date') \
            .execute()

        return [PlanFactItem.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting unpaid items: {e}")
        return []


def get_paid_items_for_deal(deal_id: str) -> List[PlanFactItem]:
    """
    Get all paid plan-fact items for a deal.

    Args:
        deal_id: UUID of the deal

    Returns:
        List of paid PlanFactItem objects
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_items').select('*') \
            .eq('deal_id', deal_id) \
            .not_.is_('actual_amount', 'null') \
            .order('actual_date', desc=True) \
            .execute()

        return [PlanFactItem.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting paid items: {e}")
        return []


def get_overdue_items_for_deal(deal_id: str) -> List[PlanFactItem]:
    """
    Get all overdue (unpaid and past planned date) items for a deal.

    Args:
        deal_id: UUID of the deal

    Returns:
        List of overdue PlanFactItem objects
    """
    supabase = get_supabase()
    today = date.today().isoformat()

    try:
        result = supabase.table('plan_fact_items').select('*') \
            .eq('deal_id', deal_id) \
            .is_('actual_amount', 'null') \
            .lt('planned_date', today) \
            .order('planned_date') \
            .execute()

        return [PlanFactItem.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting overdue items: {e}")
        return []


def count_items_for_deal(deal_id: str) -> Dict[str, int]:
    """
    Count plan-fact items by status for a deal.

    Args:
        deal_id: UUID of the deal

    Returns:
        Dict with counts: {'total': N, 'paid': N, 'unpaid': N, 'overdue': N}
    """
    supabase = get_supabase()
    today = date.today().isoformat()
    counts = {'total': 0, 'paid': 0, 'unpaid': 0, 'overdue': 0}

    try:
        # Total count
        total_result = supabase.table('plan_fact_items').select('id', count='exact') \
            .eq('deal_id', deal_id).execute()
        counts['total'] = total_result.count or 0

        # Paid count
        paid_result = supabase.table('plan_fact_items').select('id', count='exact') \
            .eq('deal_id', deal_id) \
            .not_.is_('actual_amount', 'null') \
            .execute()
        counts['paid'] = paid_result.count or 0

        # Unpaid count
        counts['unpaid'] = counts['total'] - counts['paid']

        # Overdue count
        overdue_result = supabase.table('plan_fact_items').select('id', count='exact') \
            .eq('deal_id', deal_id) \
            .is_('actual_amount', 'null') \
            .lt('planned_date', today) \
            .execute()
        counts['overdue'] = overdue_result.count or 0

        return counts
    except Exception as e:
        print(f"Error counting items: {e}")
        return counts


# ============================================================================
# UPDATE Operations
# ============================================================================

def update_plan_fact_item(
    item_id: str,
    **kwargs
) -> Optional[PlanFactItem]:
    """
    Update plan-fact item fields.

    Args:
        item_id: UUID of the item
        **kwargs: Fields to update

    Returns:
        Updated PlanFactItem object if successful, None on error

    Example:
        item = update_plan_fact_item(
            item_id='item-123',
            planned_amount=150000.00,
            description='Updated payment description'
        )
    """
    supabase = get_supabase()

    try:
        # Convert date/Decimal objects
        update_data = {}
        for key, value in kwargs.items():
            if isinstance(value, date):
                update_data[key] = value.isoformat()
            elif isinstance(value, Decimal):
                update_data[key] = float(value)
            else:
                update_data[key] = value

        result = supabase.table('plan_fact_items').update(update_data) \
            .eq('id', item_id) \
            .execute()

        if result.data:
            return PlanFactItem.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error updating plan-fact item: {e}")
        return None


def record_actual_payment(
    item_id: str,
    actual_amount: float,
    actual_date: date,
    actual_currency: str = 'RUB',
    actual_exchange_rate: Optional[float] = None,
    payment_document: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[PlanFactItem]:
    """
    Record an actual payment for a plan-fact item.

    The database trigger will automatically calculate variance_amount.

    Args:
        item_id: UUID of the item
        actual_amount: Actual payment amount
        actual_date: Date of actual payment
        actual_currency: Currency of payment (default: RUB)
        actual_exchange_rate: Exchange rate to RUB (required for non-RUB)
        payment_document: Payment document number/reference
        notes: Additional notes

    Returns:
        Updated PlanFactItem object if successful, None on error

    Example:
        item = record_actual_payment(
            item_id='item-123',
            actual_amount=98500.00,
            actual_date=date(2025, 2, 14),
            payment_document='PP-2025-001'
        )
    """
    update_kwargs = {
        'actual_amount': actual_amount,
        'actual_date': actual_date,
        'actual_currency': actual_currency,
    }

    if actual_exchange_rate is not None:
        update_kwargs['actual_exchange_rate'] = actual_exchange_rate
    if payment_document:
        update_kwargs['payment_document'] = payment_document
    if notes is not None:
        update_kwargs['notes'] = notes

    return update_plan_fact_item(item_id, **update_kwargs)


def clear_actual_payment(item_id: str) -> Optional[PlanFactItem]:
    """
    Clear the actual payment data for an item (mark as unpaid).

    Args:
        item_id: UUID of the item

    Returns:
        Updated PlanFactItem object if successful, None on error
    """
    supabase = get_supabase()

    try:
        # Set actual fields to NULL
        result = supabase.table('plan_fact_items').update({
            'actual_amount': None,
            'actual_date': None,
            'actual_currency': None,
            'actual_exchange_rate': None,
            'variance_amount': None,
            'payment_document': None,
            'notes': None,
        }).eq('id', item_id).execute()

        if result.data:
            return PlanFactItem.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error clearing actual payment: {e}")
        return None


def update_planned_payment(
    item_id: str,
    planned_amount: Optional[float] = None,
    planned_date: Optional[date] = None,
    planned_currency: Optional[str] = None,
    description: Optional[str] = None
) -> Optional[PlanFactItem]:
    """
    Update the planned payment info for an item.

    Args:
        item_id: UUID of the item
        planned_amount: New planned amount
        planned_date: New planned date
        planned_currency: New planned currency
        description: New description

    Returns:
        Updated PlanFactItem object if successful, None on error
    """
    update_kwargs = {}

    if planned_amount is not None:
        update_kwargs['planned_amount'] = planned_amount
    if planned_date is not None:
        update_kwargs['planned_date'] = planned_date
    if planned_currency is not None:
        update_kwargs['planned_currency'] = planned_currency
    if description is not None:
        update_kwargs['description'] = description

    if not update_kwargs:
        # Nothing to update
        return get_plan_fact_item(item_id)

    return update_plan_fact_item(item_id, **update_kwargs)


# ============================================================================
# DELETE Operations
# ============================================================================

def delete_plan_fact_item(item_id: str) -> bool:
    """
    Delete a plan-fact item.

    Args:
        item_id: UUID of the item

    Returns:
        True if deleted successfully, False otherwise
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_items').delete() \
            .eq('id', item_id) \
            .execute()

        return len(result.data) > 0 if result.data else False
    except Exception as e:
        print(f"Error deleting plan-fact item: {e}")
        return False


def delete_all_items_for_deal(deal_id: str) -> int:
    """
    Delete all plan-fact items for a deal.

    Use with caution - typically only for deal cleanup.

    Args:
        deal_id: UUID of the deal

    Returns:
        Number of items deleted
    """
    supabase = get_supabase()

    try:
        result = supabase.table('plan_fact_items').delete() \
            .eq('deal_id', deal_id) \
            .execute()

        return len(result.data) if result.data else 0
    except Exception as e:
        print(f"Error deleting items for deal: {e}")
        return 0


# ============================================================================
# Summary and Statistics Functions
# ============================================================================

def get_deal_plan_fact_summary(deal_id: str) -> Dict[str, Any]:
    """
    Get a complete plan-fact summary for a deal.

    Args:
        deal_id: UUID of the deal

    Returns:
        Dict with summary data:
        {
            'planned_income': Decimal,
            'planned_expense': Decimal,
            'planned_margin': Decimal,
            'actual_income': Decimal,
            'actual_expense': Decimal,
            'actual_margin': Decimal,
            'total_variance': Decimal,
            'items_count': {'total': N, 'paid': N, 'unpaid': N, 'overdue': N}
        }
    """
    supabase = get_supabase()

    summary = {
        'planned_income': Decimal('0'),
        'planned_expense': Decimal('0'),
        'planned_margin': Decimal('0'),
        'actual_income': Decimal('0'),
        'actual_expense': Decimal('0'),
        'actual_margin': Decimal('0'),
        'total_variance': Decimal('0'),
        'items_count': {'total': 0, 'paid': 0, 'unpaid': 0, 'overdue': 0}
    }

    try:
        # Get all items with category info
        result = supabase.table('plan_fact_items').select(
            '*, plan_fact_categories(is_income)'
        ).eq('deal_id', deal_id).execute()

        items = result.data if result.data else []

        for item in items:
            category = item.get('plan_fact_categories', {}) or {}
            is_income = category.get('is_income', False)

            # Planned amounts
            planned = Decimal(str(item.get('planned_amount', 0)))
            if is_income:
                summary['planned_income'] += planned
            else:
                summary['planned_expense'] += planned

            # Actual amounts
            if item.get('actual_amount') is not None:
                actual = Decimal(str(item['actual_amount']))
                if is_income:
                    summary['actual_income'] += actual
                else:
                    summary['actual_expense'] += actual

            # Variance
            if item.get('variance_amount') is not None:
                summary['total_variance'] += Decimal(str(item['variance_amount']))

        # Calculate margins
        summary['planned_margin'] = summary['planned_income'] - summary['planned_expense']
        summary['actual_margin'] = summary['actual_income'] - summary['actual_expense']

        # Get item counts
        summary['items_count'] = count_items_for_deal(deal_id)

        return summary
    except Exception as e:
        print(f"Error getting deal summary: {e}")
        return summary


def get_items_grouped_by_category(deal_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get plan-fact items grouped by category.

    Args:
        deal_id: UUID of the deal

    Returns:
        Dict with category codes as keys and lists of items as values
    """
    items_with_category = get_plan_fact_items_for_deal(deal_id, include_category=True)

    grouped = {}
    for item in items_with_category:
        category = item.get('plan_fact_categories', {}) or {}
        code = category.get('code', 'other')

        if code not in grouped:
            grouped[code] = []
        grouped[code].append(item)

    return grouped


def get_upcoming_payments(
    deal_id: str,
    days_ahead: int = 7
) -> List[PlanFactItem]:
    """
    Get upcoming unpaid payments within specified days.

    Args:
        deal_id: UUID of the deal
        days_ahead: Number of days to look ahead (default: 7)

    Returns:
        List of upcoming PlanFactItem objects
    """
    from datetime import timedelta

    supabase = get_supabase()
    today = date.today()
    future = today + timedelta(days=days_ahead)

    try:
        result = supabase.table('plan_fact_items').select('*') \
            .eq('deal_id', deal_id) \
            .is_('actual_amount', 'null') \
            .gte('planned_date', today.isoformat()) \
            .lte('planned_date', future.isoformat()) \
            .order('planned_date') \
            .execute()

        return [PlanFactItem.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting upcoming payments: {e}")
        return []


def get_payments_for_period(
    deal_id: str,
    start_date: date,
    end_date: date,
    paid_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Get plan-fact items for a specific period.

    Args:
        deal_id: UUID of the deal
        start_date: Start of period (inclusive)
        end_date: End of period (inclusive)
        paid_only: If True, only return paid items

    Returns:
        List of item dicts with category info
    """
    supabase = get_supabase()

    try:
        query = supabase.table('plan_fact_items').select(
            '*, plan_fact_categories(id, code, name, is_income)'
        ).eq('deal_id', deal_id)

        if paid_only:
            query = query.not_.is_('actual_date', 'null') \
                .gte('actual_date', start_date.isoformat()) \
                .lte('actual_date', end_date.isoformat()) \
                .order('actual_date')
        else:
            query = query.gte('planned_date', start_date.isoformat()) \
                .lte('planned_date', end_date.isoformat()) \
                .order('planned_date')

        result = query.execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting payments for period: {e}")
        return []


# ============================================================================
# Validation Functions
# ============================================================================

def validate_item_for_payment(item_id: str) -> Dict[str, Any]:
    """
    Validate if an item can have payment recorded.

    Args:
        item_id: UUID of the item

    Returns:
        Dict with 'valid': bool and 'errors': list
    """
    item = get_plan_fact_item(item_id)

    errors = []

    if not item:
        return {'valid': False, 'errors': ['Item not found']}

    if item.is_paid:
        errors.append('Payment already recorded')

    if not item.planned_amount or item.planned_amount <= 0:
        errors.append('Invalid planned amount')

    if not item.planned_date:
        errors.append('No planned date set')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'item': item
    }


def validate_deal_plan_fact(deal_id: str) -> Dict[str, Any]:
    """
    Validate plan-fact data for a deal.

    Checks for:
    - Missing income items
    - Missing expense items
    - Dates consistency
    - Amount balance

    Args:
        deal_id: UUID of the deal

    Returns:
        Dict with validation results
    """
    summary = get_deal_plan_fact_summary(deal_id)
    grouped = get_items_grouped_by_category(deal_id)

    warnings = []
    errors = []

    # Check for missing key categories
    if 'client_payment' not in grouped:
        errors.append('No client payment planned')

    if 'supplier_payment' not in grouped:
        warnings.append('No supplier payment planned')

    # Check planned margin
    if summary['planned_margin'] < 0:
        warnings.append(f'Negative planned margin: {summary["planned_margin"]}')

    # Check for overdue items
    if summary['items_count']['overdue'] > 0:
        warnings.append(f'{summary["items_count"]["overdue"]} overdue payment(s)')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'summary': summary
    }
