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


# ============================================================================
# Auto-Generation Functions (Feature #82)
# ============================================================================

@dataclass
class GeneratePlanFactResult:
    """Result of auto-generating plan-fact items from deal conditions."""
    success: bool
    items_created: List[PlanFactItem]
    items_count: int
    error: Optional[str]
    source_data: Dict[str, Any]  # Shows what data was used


def generate_plan_fact_from_deal(
    deal_id: str,
    created_by: Optional[str] = None,
    replace_existing: bool = False
) -> GeneratePlanFactResult:
    """
    Auto-generate planned payments from deal conditions.

    This function reads the deal's specification and quote data, extracts
    calculation variables (advance percentages, payment timing, etc.),
    and creates plan_fact_items for each payment category.

    Args:
        deal_id: UUID of the deal to generate plan-fact for
        created_by: ID of the user triggering generation
        replace_existing: If True, delete existing items before creating new ones
                         If False, skip generation if items already exist

    Returns:
        GeneratePlanFactResult with success flag, created items, and source data

    Payment categories generated:
        - client_payment: Based on advance_from_client % and timing
        - supplier_payment: Based on total_purchase and advance_to_supplier %
        - logistics: Based on logistics_total from calculation
        - customs: Based on customs costs from calculation
        - finance_commission: Based on bank_commission_percent

    Example:
        result = generate_plan_fact_from_deal('deal-123', created_by='user-456')
        if result.success:
            print(f"Created {result.items_count} plan-fact items")
    """
    from datetime import timedelta

    supabase = get_supabase()
    source_data = {}

    try:
        # Step 1: Get deal with related spec and quote
        deal_result = supabase.table('deals').select(
            '*, specifications(*, quotes(id, idn_quote, total_amount, currency, organization_id))'
        ).eq('id', deal_id).execute()

        if not deal_result.data:
            return GeneratePlanFactResult(
                success=False,
                items_created=[],
                items_count=0,
                error=f"Deal not found: {deal_id}",
                source_data={}
            )

        deal = deal_result.data[0]
        spec = deal.get('specifications', {}) or {}
        quote = spec.get('quotes', {}) or {}
        quote_id = spec.get('quote_id') or quote.get('id')

        source_data['deal'] = {
            'id': deal_id,
            'deal_number': deal.get('deal_number'),
            'total_amount': deal.get('total_amount'),
            'currency': deal.get('currency'),
            'signed_at': deal.get('signed_at'),
        }
        source_data['quote_id'] = quote_id

        # Step 2: Check for existing items
        existing_count = count_items_for_deal(deal_id).get('total', 0)

        if existing_count > 0 and not replace_existing:
            return GeneratePlanFactResult(
                success=False,
                items_created=[],
                items_count=0,
                error=f"Plan-fact items already exist ({existing_count} items). Use replace_existing=True to regenerate.",
                source_data=source_data
            )

        if replace_existing and existing_count > 0:
            delete_all_items_for_deal(deal_id)

        # Step 3: Get calculation variables from quote
        if quote_id:
            vars_result = supabase.table('quote_calculation_variables') \
                .select('*') \
                .eq('quote_id', quote_id) \
                .execute()

            calc_vars = vars_result.data[0] if vars_result.data else {}
        else:
            calc_vars = {}

        source_data['calc_vars'] = {
            'advance_from_client': calc_vars.get('advance_from_client', 100),
            'advance_to_supplier': calc_vars.get('advance_to_supplier', 100),
            'time_to_advance': calc_vars.get('time_to_advance', 0),
            'time_to_advance_on_receiving': calc_vars.get('time_to_advance_on_receiving', 0),
            'bank_commission_percent': calc_vars.get('bank_commission_percent', 0),
        }

        # Step 4: Get calculation results for totals
        if quote_id:
            calc_result = supabase.table('quote_item_calculations') \
                .select('*') \
                .eq('quote_id', quote_id) \
                .execute()

            calc_items = calc_result.data if calc_result.data else []
        else:
            calc_items = []

        # Calculate totals from items
        total_purchase = Decimal('0')
        total_logistics = Decimal('0')
        total_customs = Decimal('0')
        total_sale = Decimal('0')

        for item in calc_items:
            total_purchase += Decimal(str(item.get('purchase_price_total', 0) or 0))
            total_logistics += Decimal(str(item.get('logistics_total', 0) or 0))
            # Customs costs may include duty and processing fees
            customs_duty = Decimal(str(item.get('customs_duty_total', 0) or 0))
            customs_processing = Decimal(str(item.get('customs_processing_total', 0) or 0))
            total_customs += customs_duty + customs_processing
            total_sale += Decimal(str(item.get('sales_price_total_with_vat', 0) or 0))

        # Use deal's total_amount as the primary source for client payments
        deal_total = Decimal(str(deal.get('total_amount', 0) or 0))
        if deal_total == 0:
            deal_total = total_sale

        source_data['totals'] = {
            'deal_total': float(deal_total),
            'total_purchase': float(total_purchase),
            'total_logistics': float(total_logistics),
            'total_customs': float(total_customs),
            'total_sale': float(total_sale),
        }

        # Step 5: Determine base date (deal signed_at or today)
        try:
            if deal.get('signed_at'):
                if isinstance(deal['signed_at'], str):
                    base_date = datetime.strptime(deal['signed_at'], '%Y-%m-%d').date()
                else:
                    base_date = deal['signed_at']
            else:
                base_date = date.today()
        except:
            base_date = date.today()

        source_data['base_date'] = base_date.isoformat()

        currency = deal.get('currency') or spec.get('specification_currency') or 'RUB'

        # Step 6: Generate planned payments
        items_to_create = []

        # --- Client Payments ---
        advance_pct = float(calc_vars.get('advance_from_client', 100) or 100)
        time_to_advance = int(calc_vars.get('time_to_advance', 0) or 0)
        time_to_final = int(calc_vars.get('time_to_advance_on_receiving', 0) or 0)

        if advance_pct > 0 and deal_total > 0:
            advance_amount = deal_total * Decimal(str(advance_pct)) / 100
            advance_date = base_date + timedelta(days=time_to_advance)

            items_to_create.append({
                'category_code': 'client_payment',
                'planned_amount': float(advance_amount),
                'planned_date': advance_date,
                'planned_currency': currency,
                'description': f'Аванс от клиента ({advance_pct:.0f}%)',
            })

        # If not 100% prepayment, add final payment
        if advance_pct < 100 and deal_total > 0:
            remaining_pct = 100 - advance_pct
            remaining_amount = deal_total * Decimal(str(remaining_pct)) / 100
            final_date = base_date + timedelta(days=time_to_final) if time_to_final > 0 else base_date + timedelta(days=30)

            items_to_create.append({
                'category_code': 'client_payment',
                'planned_amount': float(remaining_amount),
                'planned_date': final_date,
                'planned_currency': currency,
                'description': f'Остаток от клиента ({remaining_pct:.0f}%)',
            })

        # --- Supplier Payment ---
        if total_purchase > 0:
            supplier_advance_pct = float(calc_vars.get('advance_to_supplier', 100) or 100)

            if supplier_advance_pct > 0:
                supplier_advance = total_purchase * Decimal(str(supplier_advance_pct)) / 100
                # Supplier payment typically shortly after deal signing
                supplier_date = base_date + timedelta(days=3)

                items_to_create.append({
                    'category_code': 'supplier_payment',
                    'planned_amount': float(supplier_advance),
                    'planned_date': supplier_date,
                    'planned_currency': currency,
                    'description': f'Оплата поставщику ({supplier_advance_pct:.0f}%)',
                })

            # If not 100% advance to supplier, add remaining
            if supplier_advance_pct < 100:
                remaining_pct = 100 - supplier_advance_pct
                remaining_supplier = total_purchase * Decimal(str(remaining_pct)) / 100
                supplier_final_date = base_date + timedelta(days=20)  # Typically after goods arrive

                items_to_create.append({
                    'category_code': 'supplier_payment',
                    'planned_amount': float(remaining_supplier),
                    'planned_date': supplier_final_date,
                    'planned_currency': currency,
                    'description': f'Остаток поставщику ({remaining_pct:.0f}%)',
                })

        # --- Logistics Payment ---
        if total_logistics > 0:
            logistics_date = base_date + timedelta(days=14)  # Typically paid during transit

            items_to_create.append({
                'category_code': 'logistics',
                'planned_amount': float(total_logistics),
                'planned_date': logistics_date,
                'planned_currency': currency,
                'description': 'Оплата логистики',
            })

        # --- Customs Payment ---
        if total_customs > 0:
            customs_date = base_date + timedelta(days=21)  # Typically at customs clearance

            items_to_create.append({
                'category_code': 'customs',
                'planned_amount': float(total_customs),
                'planned_date': customs_date,
                'planned_currency': currency,
                'description': 'Таможенные платежи',
            })

        # --- Bank/Finance Commission ---
        bank_commission_pct = float(calc_vars.get('bank_commission_percent', 0) or 0)
        if bank_commission_pct > 0 and deal_total > 0:
            commission_amount = deal_total * Decimal(str(bank_commission_pct)) / 100
            commission_date = base_date + timedelta(days=7)

            items_to_create.append({
                'category_code': 'finance_commission',
                'planned_amount': float(commission_amount),
                'planned_date': commission_date,
                'planned_currency': currency,
                'description': f'Банковская комиссия ({bank_commission_pct:.1f}%)',
            })

        # Step 7: Create all items
        created_items = bulk_create_plan_fact_items(
            deal_id=deal_id,
            items=items_to_create,
            created_by=created_by
        )

        source_data['items_planned'] = len(items_to_create)
        source_data['items_created'] = len(created_items)

        return GeneratePlanFactResult(
            success=True,
            items_created=created_items,
            items_count=len(created_items),
            error=None,
            source_data=source_data
        )

    except Exception as e:
        print(f"Error generating plan-fact items: {e}")
        import traceback
        traceback.print_exc()
        return GeneratePlanFactResult(
            success=False,
            items_created=[],
            items_count=0,
            error=str(e),
            source_data=source_data
        )


def regenerate_plan_fact_for_deal(
    deal_id: str,
    created_by: Optional[str] = None
) -> GeneratePlanFactResult:
    """
    Regenerate plan-fact items for a deal, replacing existing ones.

    This is a convenience wrapper around generate_plan_fact_from_deal
    with replace_existing=True.

    Args:
        deal_id: UUID of the deal
        created_by: ID of the user triggering regeneration

    Returns:
        GeneratePlanFactResult with success flag and created items

    Warning:
        This will DELETE all existing plan-fact items for the deal,
        including any with recorded actual payments!
    """
    return generate_plan_fact_from_deal(
        deal_id=deal_id,
        created_by=created_by,
        replace_existing=True
    )


def get_plan_fact_generation_preview(deal_id: str) -> Dict[str, Any]:
    """
    Preview what plan-fact items would be generated for a deal.

    This does NOT create any items - just shows what would be generated.

    Args:
        deal_id: UUID of the deal

    Returns:
        Dict with preview data:
        {
            'deal_info': {...},
            'source_data': {...},
            'planned_items': [{...}, ...],
            'totals': {...},
            'can_generate': bool,
            'existing_items': int
        }
    """
    from datetime import timedelta

    supabase = get_supabase()
    preview = {
        'deal_info': {},
        'source_data': {},
        'planned_items': [],
        'totals': {},
        'can_generate': False,
        'existing_items': 0
    }

    try:
        # Get deal with related data
        deal_result = supabase.table('deals').select(
            '*, specifications(*, quotes(id, idn_quote, total_amount, currency))'
        ).eq('id', deal_id).execute()

        if not deal_result.data:
            preview['error'] = 'Deal not found'
            return preview

        deal = deal_result.data[0]
        spec = deal.get('specifications', {}) or {}
        quote = spec.get('quotes', {}) or {}
        quote_id = spec.get('quote_id') or quote.get('id')

        preview['deal_info'] = {
            'deal_number': deal.get('deal_number'),
            'total_amount': deal.get('total_amount'),
            'currency': deal.get('currency'),
            'signed_at': deal.get('signed_at'),
            'status': deal.get('status'),
        }

        # Check existing items
        preview['existing_items'] = count_items_for_deal(deal_id).get('total', 0)

        # Get calculation variables
        if quote_id:
            vars_result = supabase.table('quote_calculation_variables') \
                .select('*') \
                .eq('quote_id', quote_id) \
                .execute()

            calc_vars = vars_result.data[0] if vars_result.data else {}

            # Get calculation totals
            calc_result = supabase.table('quote_item_calculations') \
                .select('purchase_price_total, logistics_total, customs_duty_total, customs_processing_total, sales_price_total_with_vat') \
                .eq('quote_id', quote_id) \
                .execute()

            calc_items = calc_result.data if calc_result.data else []
        else:
            calc_vars = {}
            calc_items = []

        preview['source_data'] = {
            'advance_from_client': calc_vars.get('advance_from_client', 100),
            'advance_to_supplier': calc_vars.get('advance_to_supplier', 100),
            'time_to_advance': calc_vars.get('time_to_advance', 0),
            'time_to_advance_on_receiving': calc_vars.get('time_to_advance_on_receiving', 0),
            'bank_commission_percent': calc_vars.get('bank_commission_percent', 0),
        }

        # Calculate totals
        total_purchase = sum(Decimal(str(item.get('purchase_price_total', 0) or 0)) for item in calc_items)
        total_logistics = sum(Decimal(str(item.get('logistics_total', 0) or 0)) for item in calc_items)
        total_customs = sum(
            Decimal(str(item.get('customs_duty_total', 0) or 0)) +
            Decimal(str(item.get('customs_processing_total', 0) or 0))
            for item in calc_items
        )
        total_sale = sum(Decimal(str(item.get('sales_price_total_with_vat', 0) or 0)) for item in calc_items)
        deal_total = Decimal(str(deal.get('total_amount', 0) or 0)) or total_sale

        preview['totals'] = {
            'deal_total': float(deal_total),
            'total_purchase': float(total_purchase),
            'total_logistics': float(total_logistics),
            'total_customs': float(total_customs),
            'total_sale': float(total_sale),
        }

        # Generate preview items
        try:
            if deal.get('signed_at'):
                if isinstance(deal['signed_at'], str):
                    base_date = datetime.strptime(deal['signed_at'], '%Y-%m-%d').date()
                else:
                    base_date = deal['signed_at']
            else:
                base_date = date.today()
        except:
            base_date = date.today()

        currency = deal.get('currency', 'RUB')
        planned_items = []

        advance_pct = float(calc_vars.get('advance_from_client', 100) or 100)
        time_to_advance = int(calc_vars.get('time_to_advance', 0) or 0)
        time_to_final = int(calc_vars.get('time_to_advance_on_receiving', 0) or 0)

        if advance_pct > 0 and deal_total > 0:
            planned_items.append({
                'category': 'client_payment',
                'category_name': 'Оплата от клиента',
                'description': f'Аванс от клиента ({advance_pct:.0f}%)',
                'amount': float(deal_total * Decimal(str(advance_pct)) / 100),
                'currency': currency,
                'date': (base_date + timedelta(days=time_to_advance)).isoformat(),
                'is_income': True,
            })

        if advance_pct < 100 and deal_total > 0:
            remaining_pct = 100 - advance_pct
            planned_items.append({
                'category': 'client_payment',
                'category_name': 'Оплата от клиента',
                'description': f'Остаток от клиента ({remaining_pct:.0f}%)',
                'amount': float(deal_total * Decimal(str(remaining_pct)) / 100),
                'currency': currency,
                'date': (base_date + timedelta(days=time_to_final if time_to_final > 0 else 30)).isoformat(),
                'is_income': True,
            })

        if total_purchase > 0:
            supplier_pct = float(calc_vars.get('advance_to_supplier', 100) or 100)
            if supplier_pct > 0:
                planned_items.append({
                    'category': 'supplier_payment',
                    'category_name': 'Оплата поставщику',
                    'description': f'Оплата поставщику ({supplier_pct:.0f}%)',
                    'amount': float(total_purchase * Decimal(str(supplier_pct)) / 100),
                    'currency': currency,
                    'date': (base_date + timedelta(days=3)).isoformat(),
                    'is_income': False,
                })
            if supplier_pct < 100:
                remaining_pct = 100 - supplier_pct
                planned_items.append({
                    'category': 'supplier_payment',
                    'category_name': 'Оплата поставщику',
                    'description': f'Остаток поставщику ({remaining_pct:.0f}%)',
                    'amount': float(total_purchase * Decimal(str(remaining_pct)) / 100),
                    'currency': currency,
                    'date': (base_date + timedelta(days=20)).isoformat(),
                    'is_income': False,
                })

        if total_logistics > 0:
            planned_items.append({
                'category': 'logistics',
                'category_name': 'Логистика',
                'description': 'Оплата логистики',
                'amount': float(total_logistics),
                'currency': currency,
                'date': (base_date + timedelta(days=14)).isoformat(),
                'is_income': False,
            })

        if total_customs > 0:
            planned_items.append({
                'category': 'customs',
                'category_name': 'Таможня',
                'description': 'Таможенные платежи',
                'amount': float(total_customs),
                'currency': currency,
                'date': (base_date + timedelta(days=21)).isoformat(),
                'is_income': False,
            })

        bank_pct = float(calc_vars.get('bank_commission_percent', 0) or 0)
        if bank_pct > 0 and deal_total > 0:
            planned_items.append({
                'category': 'finance_commission',
                'category_name': 'Банковская комиссия',
                'description': f'Банковская комиссия ({bank_pct:.1f}%)',
                'amount': float(deal_total * Decimal(str(bank_pct)) / 100),
                'currency': currency,
                'date': (base_date + timedelta(days=7)).isoformat(),
                'is_income': False,
            })

        preview['planned_items'] = planned_items
        preview['can_generate'] = len(planned_items) > 0

        return preview

    except Exception as e:
        preview['error'] = str(e)
        return preview


# ============================================================================
# Actual Payment Registration (Feature DEAL-003)
# ============================================================================

@dataclass
class RegisterPaymentResult:
    """Result of registering an actual payment for a plan-fact item."""
    success: bool
    item: Optional[PlanFactItem]
    error: Optional[str]
    warnings: List[str]
    variance_amount: Optional[Decimal]
    variance_percent: Optional[Decimal]
    is_late: bool  # Payment after planned_date
    is_overpayment: bool  # Actual > planned
    is_underpayment: bool  # Actual < planned (and significantly lower)


# Constants for payment validation
SUPPORTED_PAYMENT_CURRENCIES = ['RUB', 'USD', 'EUR', 'CNY', 'TRY', 'AED']
MIN_EXCHANGE_RATE = Decimal('0.001')
MAX_EXCHANGE_RATE = Decimal('10000.0')
SIGNIFICANT_VARIANCE_THRESHOLD = Decimal('0.01')  # 1% variance is significant
MAX_OVERPAYMENT_RATIO = Decimal('1.5')  # Max 50% overpayment without warning


def validate_payment_amount(
    amount: float,
    planned_amount: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Validate a payment amount.

    Args:
        amount: The amount to validate
        planned_amount: Optional planned amount for comparison

    Returns:
        Dict with 'valid': bool, 'errors': list, 'warnings': list
    """
    errors = []
    warnings = []

    if amount is None:
        errors.append('Payment amount is required')
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    if amount <= 0:
        errors.append('Payment amount must be greater than 0')
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    if planned_amount is not None and planned_amount > 0:
        amount_decimal = Decimal(str(amount))

        # Check for significant overpayment
        if amount_decimal > planned_amount * MAX_OVERPAYMENT_RATIO:
            warnings.append(
                f'Payment ({amount_decimal}) exceeds planned amount ({planned_amount}) by more than 50%'
            )

        # Check for significant underpayment
        variance_ratio = abs(amount_decimal - planned_amount) / planned_amount
        if amount_decimal < planned_amount and variance_ratio > SIGNIFICANT_VARIANCE_THRESHOLD:
            warnings.append(
                f'Payment ({amount_decimal}) is {variance_ratio*100:.1f}% less than planned ({planned_amount})'
            )

    return {'valid': True, 'errors': errors, 'warnings': warnings}


def validate_payment_date(
    payment_date: date,
    planned_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Validate a payment date.

    Args:
        payment_date: The date to validate
        planned_date: Optional planned date for comparison

    Returns:
        Dict with 'valid': bool, 'errors': list, 'warnings': list, 'is_late': bool
    """
    errors = []
    warnings = []
    is_late = False

    if payment_date is None:
        errors.append('Payment date is required')
        return {'valid': False, 'errors': errors, 'warnings': warnings, 'is_late': False}

    # Check if date is in the future
    today = date.today()
    if payment_date > today:
        warnings.append(f'Payment date ({payment_date}) is in the future')

    # Check if payment is late
    if planned_date is not None and payment_date > planned_date:
        is_late = True
        days_late = (payment_date - planned_date).days
        if days_late > 0:
            warnings.append(f'Payment is {days_late} day(s) late')

    return {'valid': True, 'errors': errors, 'warnings': warnings, 'is_late': is_late}


def validate_payment_currency(
    currency: str,
    planned_currency: Optional[str] = None,
    exchange_rate: Optional[float] = None
) -> Dict[str, Any]:
    """
    Validate payment currency and exchange rate.

    Args:
        currency: Currency code to validate
        planned_currency: Expected currency for comparison
        exchange_rate: Exchange rate if currency differs from RUB

    Returns:
        Dict with 'valid': bool, 'errors': list, 'warnings': list, 'needs_exchange_rate': bool
    """
    errors = []
    warnings = []
    needs_exchange_rate = False

    if not currency:
        errors.append('Currency is required')
        return {'valid': False, 'errors': errors, 'warnings': warnings, 'needs_exchange_rate': False}

    currency = currency.upper()

    if currency not in SUPPORTED_PAYMENT_CURRENCIES:
        errors.append(f'Unsupported currency: {currency}. Supported: {", ".join(SUPPORTED_PAYMENT_CURRENCIES)}')
        return {'valid': False, 'errors': errors, 'warnings': warnings, 'needs_exchange_rate': False}

    # Check if exchange rate is needed
    if currency != 'RUB':
        needs_exchange_rate = True
        if exchange_rate is None:
            warnings.append(f'Exchange rate recommended for {currency} payments for accurate RUB tracking')
        else:
            rate_decimal = Decimal(str(exchange_rate))
            if rate_decimal < MIN_EXCHANGE_RATE or rate_decimal > MAX_EXCHANGE_RATE:
                errors.append(
                    f'Exchange rate {exchange_rate} is out of valid range ({MIN_EXCHANGE_RATE} - {MAX_EXCHANGE_RATE})'
                )

    # Check currency mismatch with planned
    if planned_currency and currency != planned_currency:
        warnings.append(
            f'Payment currency ({currency}) differs from planned currency ({planned_currency})'
        )

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'needs_exchange_rate': needs_exchange_rate
    }


def validate_payment_document(document: Optional[str]) -> Dict[str, Any]:
    """
    Validate payment document reference.

    Args:
        document: Document reference string

    Returns:
        Dict with 'valid': bool, 'errors': list, 'warnings': list
    """
    errors = []
    warnings = []

    if document:
        # Check length
        if len(document) > 100:
            errors.append('Payment document reference too long (max 100 characters)')

        # Check for invalid characters
        if '<' in document or '>' in document or ';' in document:
            errors.append('Payment document contains invalid characters')

    else:
        warnings.append('No payment document reference provided')

    return {'valid': len(errors) == 0, 'errors': errors, 'warnings': warnings}


def validate_payment_data(
    item_id: str,
    actual_amount: float,
    actual_date: date,
    actual_currency: str = 'RUB',
    actual_exchange_rate: Optional[float] = None,
    payment_document: Optional[str] = None
) -> Dict[str, Any]:
    """
    Comprehensive validation of payment data before registration.

    Args:
        item_id: ID of the plan-fact item
        actual_amount: Payment amount
        actual_date: Payment date
        actual_currency: Currency code
        actual_exchange_rate: Exchange rate (if non-RUB)
        payment_document: Document reference

    Returns:
        Dict with validation results including item data if found
    """
    result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'item': None,
        'is_late': False,
        'needs_exchange_rate': False
    }

    # Get the item
    item = get_plan_fact_item(item_id)
    if not item:
        result['valid'] = False
        result['errors'].append(f'Plan-fact item not found: {item_id}')
        return result

    result['item'] = item

    # Check if already paid
    if item.is_paid:
        result['valid'] = False
        result['errors'].append('Payment already recorded for this item. Use clear_actual_payment() first to modify.')
        return result

    # Validate amount
    amount_validation = validate_payment_amount(actual_amount, item.planned_amount)
    result['errors'].extend(amount_validation['errors'])
    result['warnings'].extend(amount_validation['warnings'])

    # Validate date
    date_validation = validate_payment_date(actual_date, item.planned_date)
    result['errors'].extend(date_validation['errors'])
    result['warnings'].extend(date_validation['warnings'])
    result['is_late'] = date_validation.get('is_late', False)

    # Validate currency
    currency_validation = validate_payment_currency(
        actual_currency,
        item.planned_currency,
        actual_exchange_rate
    )
    result['errors'].extend(currency_validation['errors'])
    result['warnings'].extend(currency_validation['warnings'])
    result['needs_exchange_rate'] = currency_validation.get('needs_exchange_rate', False)

    # Validate document
    doc_validation = validate_payment_document(payment_document)
    result['errors'].extend(doc_validation['errors'])
    result['warnings'].extend(doc_validation['warnings'])

    result['valid'] = len(result['errors']) == 0

    return result


def register_payment_for_item(
    item_id: str,
    actual_amount: float,
    actual_date: date,
    actual_currency: str = 'RUB',
    actual_exchange_rate: Optional[float] = None,
    payment_document: Optional[str] = None,
    notes: Optional[str] = None,
    skip_validation: bool = False
) -> RegisterPaymentResult:
    """
    Register an actual payment for a plan-fact item with full validation.

    This is the main function for DEAL-003 - registering actual payments
    with comprehensive validation, variance calculation, and result handling.

    Args:
        item_id: UUID of the plan-fact item
        actual_amount: Actual payment amount
        actual_date: Date of actual payment
        actual_currency: Currency of payment (default: RUB)
        actual_exchange_rate: Exchange rate to RUB (required for non-RUB currencies)
        payment_document: Payment document number/reference (e.g., 'PP-2025-001')
        notes: Additional notes about the payment
        skip_validation: Skip validation (use with caution)

    Returns:
        RegisterPaymentResult with success flag, updated item, and variance info

    Example:
        result = register_payment_for_item(
            item_id='item-123',
            actual_amount=98500.00,
            actual_date=date(2025, 2, 14),
            payment_document='PP-2025-001',
            notes='Paid on time via bank transfer'
        )
        if result.success:
            print(f"Payment registered. Variance: {result.variance_amount}")
        else:
            print(f"Error: {result.error}")
    """
    warnings = []

    # Run validation unless skipped
    if not skip_validation:
        validation = validate_payment_data(
            item_id=item_id,
            actual_amount=actual_amount,
            actual_date=actual_date,
            actual_currency=actual_currency,
            actual_exchange_rate=actual_exchange_rate,
            payment_document=payment_document
        )

        if not validation['valid']:
            return RegisterPaymentResult(
                success=False,
                item=validation.get('item'),
                error='; '.join(validation['errors']),
                warnings=validation['warnings'],
                variance_amount=None,
                variance_percent=None,
                is_late=validation.get('is_late', False),
                is_overpayment=False,
                is_underpayment=False
            )

        warnings = validation['warnings']
        item = validation['item']
        is_late = validation.get('is_late', False)
    else:
        item = get_plan_fact_item(item_id)
        if not item:
            return RegisterPaymentResult(
                success=False,
                item=None,
                error=f'Plan-fact item not found: {item_id}',
                warnings=[],
                variance_amount=None,
                variance_percent=None,
                is_late=False,
                is_overpayment=False,
                is_underpayment=False
            )
        is_late = actual_date > item.planned_date if item.planned_date else False

    # Calculate expected variance
    actual_decimal = Decimal(str(actual_amount))
    planned_decimal = item.planned_amount or Decimal('0')

    expected_variance = actual_decimal - planned_decimal
    if planned_decimal > 0:
        expected_variance_percent = (expected_variance / planned_decimal) * 100
    else:
        expected_variance_percent = Decimal('0')

    is_overpayment = actual_decimal > planned_decimal
    is_underpayment = actual_decimal < planned_decimal and abs(expected_variance) > planned_decimal * SIGNIFICANT_VARIANCE_THRESHOLD

    # Record the payment using existing function
    updated_item = record_actual_payment(
        item_id=item_id,
        actual_amount=actual_amount,
        actual_date=actual_date,
        actual_currency=actual_currency,
        actual_exchange_rate=actual_exchange_rate,
        payment_document=payment_document,
        notes=notes
    )

    if not updated_item:
        return RegisterPaymentResult(
            success=False,
            item=None,
            error='Failed to record payment - database error',
            warnings=warnings,
            variance_amount=expected_variance,
            variance_percent=expected_variance_percent,
            is_late=is_late,
            is_overpayment=is_overpayment,
            is_underpayment=is_underpayment
        )

    # Get the actual variance from the updated item (calculated by DB trigger)
    final_variance = updated_item.variance_amount

    return RegisterPaymentResult(
        success=True,
        item=updated_item,
        error=None,
        warnings=warnings,
        variance_amount=final_variance,
        variance_percent=expected_variance_percent,
        is_late=is_late,
        is_overpayment=is_overpayment,
        is_underpayment=is_underpayment
    )


def register_partial_payment(
    item_id: str,
    partial_amount: float,
    payment_date: date,
    currency: str = 'RUB',
    exchange_rate: Optional[float] = None,
    payment_document: Optional[str] = None,
    notes: Optional[str] = None
) -> RegisterPaymentResult:
    """
    Register a partial payment for a plan-fact item.

    This is used when only part of the planned amount is received.
    Creates a note indicating it's a partial payment and how much remains.

    Args:
        item_id: UUID of the plan-fact item
        partial_amount: Partial payment amount (less than planned)
        payment_date: Date of payment
        currency: Currency code
        exchange_rate: Exchange rate if non-RUB
        payment_document: Document reference
        notes: Additional notes

    Returns:
        RegisterPaymentResult with success flag and partial payment info

    Example:
        result = register_partial_payment(
            item_id='item-123',
            partial_amount=25000,  # Out of 50000 planned
            payment_date=date(2025, 2, 10),
            payment_document='PP-2025-001',
            notes='First partial payment'
        )
    """
    item = get_plan_fact_item(item_id)
    if not item:
        return RegisterPaymentResult(
            success=False,
            item=None,
            error=f'Plan-fact item not found: {item_id}',
            warnings=[],
            variance_amount=None,
            variance_percent=None,
            is_late=False,
            is_overpayment=False,
            is_underpayment=False
        )

    # Calculate remaining amount
    planned = item.planned_amount or Decimal('0')
    partial = Decimal(str(partial_amount))
    remaining = planned - partial

    # Enhance notes with partial payment info
    partial_note = f'Частичная оплата: {partial_amount} из {planned}. Остаток: {remaining}'
    if notes:
        full_notes = f'{partial_note}. {notes}'
    else:
        full_notes = partial_note

    # Register using the main function
    return register_payment_for_item(
        item_id=item_id,
        actual_amount=partial_amount,
        actual_date=payment_date,
        actual_currency=currency,
        actual_exchange_rate=exchange_rate,
        payment_document=payment_document,
        notes=full_notes
    )


def bulk_register_payments(
    payments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Register multiple payments at once.

    Args:
        payments: List of payment dicts with keys:
            - item_id (required)
            - actual_amount (required)
            - actual_date (required)
            - actual_currency (optional, default 'RUB')
            - actual_exchange_rate (optional)
            - payment_document (optional)
            - notes (optional)

    Returns:
        Dict with:
            - success_count: Number of successful registrations
            - failure_count: Number of failed registrations
            - results: List of RegisterPaymentResult objects
            - total_amount: Total amount registered successfully
    """
    results = []
    success_count = 0
    failure_count = 0
    total_amount = Decimal('0')

    for payment in payments:
        item_id = payment.get('item_id')
        actual_amount = payment.get('actual_amount')
        actual_date = payment.get('actual_date')

        if not all([item_id, actual_amount, actual_date]):
            results.append(RegisterPaymentResult(
                success=False,
                item=None,
                error='Missing required fields (item_id, actual_amount, actual_date)',
                warnings=[],
                variance_amount=None,
                variance_percent=None,
                is_late=False,
                is_overpayment=False,
                is_underpayment=False
            ))
            failure_count += 1
            continue

        result = register_payment_for_item(
            item_id=item_id,
            actual_amount=actual_amount,
            actual_date=actual_date,
            actual_currency=payment.get('actual_currency', 'RUB'),
            actual_exchange_rate=payment.get('actual_exchange_rate'),
            payment_document=payment.get('payment_document'),
            notes=payment.get('notes')
        )

        results.append(result)

        if result.success:
            success_count += 1
            total_amount += Decimal(str(actual_amount))
        else:
            failure_count += 1

    return {
        'success_count': success_count,
        'failure_count': failure_count,
        'results': results,
        'total_amount': float(total_amount)
    }


def get_payment_registration_preview(item_id: str) -> Dict[str, Any]:
    """
    Get preview information before registering a payment.

    Shows what the item looks like and what will change upon payment registration.

    Args:
        item_id: UUID of the plan-fact item

    Returns:
        Dict with preview data for UI display
    """
    item = get_plan_fact_item(item_id)

    if not item:
        return {
            'found': False,
            'error': f'Item not found: {item_id}'
        }

    # Get category info
    category = get_category(item.category_id)

    # Calculate if overdue
    today = date.today()
    is_overdue = item.planned_date and item.planned_date < today and not item.is_paid
    days_overdue = (today - item.planned_date).days if is_overdue else 0

    return {
        'found': True,
        'item_id': item.id,
        'deal_id': item.deal_id,
        'description': item.description,
        'category_code': category.code if category else None,
        'category_name': category.name if category else 'Unknown',
        'is_income': category.is_income if category else False,
        'planned': {
            'amount': float(item.planned_amount) if item.planned_amount else 0,
            'currency': item.planned_currency,
            'date': item.planned_date.isoformat() if item.planned_date else None,
        },
        'is_paid': item.is_paid,
        'is_overdue': is_overdue,
        'days_overdue': days_overdue,
        'can_register': not item.is_paid,
        'current_payment': {
            'amount': float(item.actual_amount) if item.actual_amount else None,
            'currency': item.actual_currency,
            'date': item.actual_date.isoformat() if item.actual_date else None,
            'document': item.payment_document,
            'variance': float(item.variance_amount) if item.variance_amount else None,
        } if item.is_paid else None,
        'suggested_amount': float(item.planned_amount) if item.planned_amount else 0,
        'suggested_currency': item.planned_currency,
        'suggested_date': today.isoformat(),
    }


def get_customer_debt_summary(customer_id: str) -> Dict[str, Any]:
    """
    Get debt summary for a customer by traversing the chain:
    customers -> quotes -> specifications -> deals -> plan_fact_items

    Args:
        customer_id: UUID of the customer

    Returns:
        Dict with keys: total_debt, last_payment_date, last_payment_amount,
        overdue_count, overdue_amount, unpaid_count
    """
    supabase = get_supabase()
    today = date.today()

    result_summary = {
        "total_debt": 0,
        "last_payment_date": None,
        "last_payment_amount": None,
        "overdue_count": 0,
        "overdue_amount": 0,
        "unpaid_count": 0,
    }

    try:
        # Step 1: Get deals for this customer via the chain:
        # customers -> quotes -> specifications -> deals
        deals_result = supabase.table("deals").select(
            "id, specifications(quotes(customer_id))"
        ).execute()

        deal_ids = []
        for deal in (deals_result.data or []):
            specs = deal.get("specifications") or {}
            quotes = specs.get("quotes") or {}
            if quotes.get("customer_id") == customer_id:
                deal_ids.append(deal.get("id"))

        # If customer has no deals, there's no debt — return zeros immediately
        if not deal_ids:
            return result_summary

        # Step 2: Query plan_fact_items for unpaid items (actual_amount IS NULL)
        # These represent the customer's total debt (income items only)
        unpaid_result = supabase.table("plan_fact_items").select(
            "id, deal_id, planned_amount, actual_amount, planned_date, "
            "plan_fact_categories(is_income)"
        ).is_("actual_amount", "null").execute()

        unpaid_items = unpaid_result.data or []
        # Filter to customer's deals
        unpaid_items = [i for i in unpaid_items if i.get("deal_id") in deal_ids]
        # Only income items represent debt owed BY the customer;
        # expense items (supplier/logistics payments) are not customer debt
        unpaid_income = [i for i in unpaid_items if (i.get("plan_fact_categories") or {}).get("is_income")]

        result_summary["unpaid_count"] = len(unpaid_income)
        result_summary["total_debt"] = sum(float(i.get("planned_amount") or 0) for i in unpaid_income)

        # Step 3: Count overdue items (unpaid income + planned_date < today)
        overdue_items = []
        for item in unpaid_income:
            planned_date_str = item.get("planned_date") or ""
            if planned_date_str:
                try:
                    pd = datetime.strptime(str(planned_date_str)[:10], "%Y-%m-%d").date()
                    if pd < today:
                        overdue_items.append(item)
                except Exception:
                    pass

        result_summary["overdue_count"] = len(overdue_items)
        result_summary["overdue_amount"] = sum(float(i.get("planned_amount") or 0) for i in overdue_items)

        # Step 4: Find last payment (most recent actual_date among paid items for this customer)
        paid_result = supabase.table("plan_fact_items").select(
            "id, deal_id, actual_amount, actual_date"
        ).not_("actual_amount", "is", "null").order("actual_date", desc=True).execute()

        paid_items = [i for i in (paid_result.data or []) if i.get("deal_id") in deal_ids]

        if paid_items:
            last_paid = paid_items[0]
            result_summary["last_payment_date"] = last_paid.get("actual_date")
            result_summary["last_payment_amount"] = float(last_paid.get("actual_amount") or 0)

        return result_summary

    except Exception as e:
        print(f"Error getting customer debt summary: {e}")
        return result_summary


def get_variance_summary(item_id: str) -> Dict[str, Any]:
    """
    Get detailed variance analysis for a paid item.

    Args:
        item_id: UUID of the plan-fact item

    Returns:
        Dict with variance analysis
    """
    item = get_plan_fact_item(item_id)

    if not item:
        return {'error': 'Item not found'}

    if not item.is_paid:
        return {
            'error': 'Item not yet paid',
            'is_paid': False
        }

    planned = item.planned_amount or Decimal('0')
    actual = item.actual_amount or Decimal('0')
    variance = item.variance_amount or Decimal('0')

    # Calculate percentage
    variance_percent = (variance / planned * 100) if planned > 0 else Decimal('0')

    # Determine variance type
    if variance > 0:
        variance_type = 'overpayment'
        variance_description = f'Переплата: {abs(variance)} ({abs(variance_percent):.1f}%)'
    elif variance < 0:
        variance_type = 'underpayment'
        variance_description = f'Недоплата: {abs(variance)} ({abs(variance_percent):.1f}%)'
    else:
        variance_type = 'exact'
        variance_description = 'Точное соответствие плану'

    # Check timing
    if item.planned_date and item.actual_date:
        days_diff = (item.actual_date - item.planned_date).days
        if days_diff > 0:
            timing = 'late'
            timing_description = f'Оплачено с опозданием на {days_diff} дней'
        elif days_diff < 0:
            timing = 'early'
            timing_description = f'Оплачено досрочно на {abs(days_diff)} дней'
        else:
            timing = 'on_time'
            timing_description = 'Оплачено в срок'
    else:
        timing = 'unknown'
        timing_description = 'Даты не указаны'

    # Get category for context
    category = get_category(item.category_id)
    is_income = category.is_income if category else False

    # Assess impact
    if is_income:
        # For income: overpayment is good, underpayment is bad
        impact = 'favorable' if variance >= 0 else 'unfavorable'
    else:
        # For expenses: underpayment is good, overpayment is bad
        impact = 'favorable' if variance <= 0 else 'unfavorable'

    return {
        'is_paid': True,
        'planned_amount': float(planned),
        'actual_amount': float(actual),
        'variance_amount': float(variance),
        'variance_percent': float(variance_percent),
        'variance_type': variance_type,
        'variance_description': variance_description,
        'timing': timing,
        'timing_description': timing_description,
        'is_income': is_income,
        'impact': impact,
        'currency': item.actual_currency or item.planned_currency,
        'payment_document': item.payment_document,
        'notes': item.notes,
    }
