"""
Deal Service

CRUD operations for the deals table.
Handles deal lifecycle from creation (when specification is signed) through completion.

Feature #75 from features.json
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
class Deal:
    """Represents a deal (signed specification)."""
    id: str
    specification_id: str
    quote_id: str
    organization_id: str

    # Deal identification
    deal_number: str

    # Signing info
    signed_at: date

    # Financial details
    total_amount: Decimal
    currency: str

    # Status tracking
    status: str  # 'active', 'completed', 'cancelled'

    # Audit
    created_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_dict(cls, data: dict) -> 'Deal':
        """Create a Deal instance from a dictionary."""
        return cls(
            id=data['id'],
            specification_id=data['specification_id'],
            quote_id=data['quote_id'],
            organization_id=data['organization_id'],

            # Deal identification
            deal_number=data['deal_number'],

            # Signing info
            signed_at=datetime.strptime(data['signed_at'], '%Y-%m-%d').date() if isinstance(data['signed_at'], str) else data['signed_at'],

            # Financial details
            total_amount=Decimal(str(data['total_amount'])) if data.get('total_amount') else Decimal('0'),
            currency=data.get('currency', 'RUB'),

            # Status
            status=data.get('status', 'active'),

            # Audit
            created_by=data.get('created_by'),
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')) if isinstance(data['created_at'], str) else data['created_at'],
            updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')) if data.get('updated_at') and isinstance(data['updated_at'], str) else data.get('updated_at'),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'specification_id': self.specification_id,
            'quote_id': self.quote_id,
            'organization_id': self.organization_id,
            'deal_number': self.deal_number,
            'signed_at': self.signed_at.isoformat() if self.signed_at else None,
            'total_amount': float(self.total_amount) if self.total_amount else None,
            'currency': self.currency,
            'status': self.status,
            'created_by': self.created_by,
        }


# Valid deal statuses
DEAL_STATUSES = ['active', 'completed', 'cancelled']

# Status names for display
DEAL_STATUS_NAMES = {
    'active': 'В работе',
    'completed': 'Завершена',
    'cancelled': 'Отменена',
}

# Status colors for UI
DEAL_STATUS_COLORS = {
    'active': '#10b981',  # green - active work
    'completed': '#3b82f6',  # blue - success
    'cancelled': '#ef4444',  # red - cancelled
}

# Allowed status transitions
DEAL_TRANSITIONS = {
    'active': ['completed', 'cancelled'],
    'completed': [],  # Terminal status
    'cancelled': [],  # Terminal status
}


# ============================================================================
# Status Helper Functions
# ============================================================================

def get_deal_status_name(status: str) -> str:
    """Get human-readable status name."""
    return DEAL_STATUS_NAMES.get(status, status)


def get_deal_status_color(status: str) -> str:
    """Get color for status display."""
    return DEAL_STATUS_COLORS.get(status, '#6b7280')


def can_transition_deal(from_status: str, to_status: str) -> bool:
    """Check if a deal can transition between statuses."""
    allowed = DEAL_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def get_allowed_deal_transitions(from_status: str) -> List[str]:
    """Get list of allowed target statuses from current status."""
    return DEAL_TRANSITIONS.get(from_status, [])


def is_deal_terminal(status: str) -> bool:
    """Check if a deal status is terminal (completed or cancelled)."""
    return status in ['completed', 'cancelled']


# ============================================================================
# CREATE Operations
# ============================================================================

def create_deal(
    specification_id: str,
    quote_id: str,
    organization_id: str,
    deal_number: str,
    signed_at: date,
    total_amount: float,
    currency: str = 'RUB',
    status: str = 'active',
    created_by: Optional[str] = None
) -> Optional[Deal]:
    """
    Create a new deal.

    Args:
        specification_id: ID of the specification this deal is based on
        quote_id: ID of the original quote
        organization_id: ID of the organization
        deal_number: Human-readable deal number (e.g., DEAL-2025-001)
        signed_at: Date the specification was signed
        total_amount: Total amount of the deal
        currency: Currency of the deal (default: RUB)
        status: Initial status (default: 'active')
        created_by: ID of the user creating the deal

    Returns:
        Deal object if created successfully, None on error

    Example:
        deal = create_deal(
            specification_id='spec-123',
            quote_id='quote-456',
            organization_id='org-789',
            deal_number='DEAL-2025-001',
            signed_at=date.today(),
            total_amount=100000.00,
            currency='RUB',
            created_by='user-111'
        )
    """
    if status not in DEAL_STATUSES:
        print(f"Invalid deal status: {status}")
        return None

    supabase = get_supabase()

    try:
        deal_data = {
            'specification_id': specification_id,
            'quote_id': quote_id,
            'organization_id': organization_id,
            'deal_number': deal_number,
            'signed_at': signed_at.isoformat() if isinstance(signed_at, date) else signed_at,
            'total_amount': total_amount,
            'currency': currency,
            'status': status,
        }

        if created_by:
            deal_data['created_by'] = created_by

        result = supabase.table('deals').insert(deal_data).execute()

        if result.data:
            return Deal.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error creating deal: {e}")
        return None


# ============================================================================
# READ Operations
# ============================================================================

def get_deal(deal_id: str, organization_id: Optional[str] = None) -> Optional[Deal]:
    """
    Get a single deal by ID.

    Args:
        deal_id: UUID of the deal
        organization_id: Optional org ID for security check

    Returns:
        Deal object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select('*').eq('id', deal_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        result = query.execute()

        if result.data:
            return Deal.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting deal: {e}")
        return None


def get_deal_by_specification(specification_id: str, organization_id: Optional[str] = None) -> Optional[Deal]:
    """
    Get deal for a specification.

    Args:
        specification_id: UUID of the specification
        organization_id: Optional org ID for security check

    Returns:
        Deal object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select('*').eq('specification_id', specification_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        result = query.execute()

        if result.data:
            return Deal.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting deal by specification: {e}")
        return None


def get_deal_by_quote(quote_id: str, organization_id: Optional[str] = None) -> Optional[Deal]:
    """
    Get deal for a quote.

    Args:
        quote_id: UUID of the quote
        organization_id: Optional org ID for security check

    Returns:
        Deal object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select('*').eq('quote_id', quote_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        # Get the most recent deal for this quote
        result = query.order('created_at', desc=True).limit(1).execute()

        if result.data:
            return Deal.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting deal by quote: {e}")
        return None


def get_deals_by_status(
    organization_id: str,
    status: str,
    limit: int = 50
) -> List[Deal]:
    """
    Get all deals with a given status.

    Args:
        organization_id: UUID of the organization
        status: Deal status ('active', 'completed', 'cancelled')
        limit: Maximum number of results

    Returns:
        List of Deal objects
    """
    supabase = get_supabase()

    try:
        result = supabase.table('deals').select('*') \
            .eq('organization_id', organization_id) \
            .eq('status', status) \
            .order('signed_at', desc=True) \
            .limit(limit) \
            .execute()

        return [Deal.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting deals by status: {e}")
        return []


def get_all_deals(
    organization_id: str,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Deal]:
    """
    Get all deals for an organization.

    Args:
        organization_id: UUID of the organization
        status: Optional status filter
        limit: Maximum number of results

    Returns:
        List of Deal objects
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select('*') \
            .eq('organization_id', organization_id)

        if status:
            query = query.eq('status', status)

        result = query.order('signed_at', desc=True).limit(limit).execute()

        return [Deal.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting all deals: {e}")
        return []


def get_deals_with_details(
    organization_id: str,
    status: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """
    Get deals with specification, quote, and customer details.

    Args:
        organization_id: UUID of the organization
        status: Optional status filter
        limit: Maximum number of results

    Returns:
        List of dicts with deal, specification, quote, and customer details
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select(
            '*, specifications(id, specification_number, proposal_idn, status), quotes(id, idn_quote, customer_name, customers(id, name, company_name))'
        ).eq('organization_id', organization_id)

        if status:
            query = query.eq('status', status)

        result = query.order('signed_at', desc=True).limit(limit).execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting deals with details: {e}")
        return []


def count_deals_by_status(organization_id: str) -> Dict[str, int]:
    """
    Count deals by status for an organization.

    Args:
        organization_id: UUID of the organization

    Returns:
        Dict with counts per status: {'active': 5, 'completed': 3, ...}
    """
    supabase = get_supabase()

    counts = {status: 0 for status in DEAL_STATUSES}

    try:
        for status in DEAL_STATUSES:
            result = supabase.table('deals').select('id', count='exact') \
                .eq('organization_id', organization_id) \
                .eq('status', status) \
                .execute()

            counts[status] = result.count if result.count else 0

        counts['total'] = sum(counts.values())
        return counts
    except Exception as e:
        print(f"Error counting deals: {e}")
        return counts


def deal_exists_for_specification(specification_id: str, organization_id: Optional[str] = None) -> bool:
    """
    Check if a deal already exists for a specification.

    Args:
        specification_id: UUID of the specification
        organization_id: Optional org ID for security check

    Returns:
        True if deal exists, False otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select('id', count='exact').eq('specification_id', specification_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        result = query.execute()

        return (result.count or 0) > 0
    except Exception as e:
        print(f"Error checking deal existence: {e}")
        return False


def deal_exists_for_quote(quote_id: str, organization_id: Optional[str] = None) -> bool:
    """
    Check if a deal already exists for a quote.

    Args:
        quote_id: UUID of the quote
        organization_id: Optional org ID for security check

    Returns:
        True if deal exists, False otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select('id', count='exact').eq('quote_id', quote_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        result = query.execute()

        return (result.count or 0) > 0
    except Exception as e:
        print(f"Error checking deal existence: {e}")
        return False


# ============================================================================
# UPDATE Operations
# ============================================================================

def update_deal(
    deal_id: str,
    organization_id: str,
    **kwargs
) -> Optional[Deal]:
    """
    Update deal fields.

    Args:
        deal_id: UUID of the deal
        organization_id: UUID of the organization (for security)
        **kwargs: Fields to update (total_amount, currency, status, etc.)

    Returns:
        Updated Deal object if successful, None on error

    Example:
        deal = update_deal(
            deal_id='deal-123',
            organization_id='org-456',
            total_amount=150000.00,
            currency='USD'
        )
    """
    supabase = get_supabase()

    # Validate status if being updated
    if 'status' in kwargs and kwargs['status'] not in DEAL_STATUSES:
        print(f"Invalid deal status: {kwargs['status']}")
        return None

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

        # updated_at is handled by trigger, but we can set it explicitly too
        update_data['updated_at'] = datetime.now().isoformat()

        result = supabase.table('deals').update(update_data) \
            .eq('id', deal_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if result.data:
            return Deal.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error updating deal: {e}")
        return None


def update_deal_status(
    deal_id: str,
    organization_id: str,
    new_status: str,
    validate_transition: bool = True
) -> Optional[Deal]:
    """
    Update deal status with optional transition validation.

    Args:
        deal_id: UUID of the deal
        organization_id: UUID of the organization
        new_status: Target status
        validate_transition: Whether to validate the transition (default: True)

    Returns:
        Updated Deal object if successful, None on error
    """
    if new_status not in DEAL_STATUSES:
        print(f"Invalid deal status: {new_status}")
        return None

    supabase = get_supabase()

    try:
        # Get current status for validation
        if validate_transition:
            current = get_deal(deal_id, organization_id)
            if not current:
                print(f"Deal not found: {deal_id}")
                return None

            if not can_transition_deal(current.status, new_status):
                print(f"Cannot transition from {current.status} to {new_status}")
                return None

        result = supabase.table('deals').update({
            'status': new_status,
            'updated_at': datetime.now().isoformat()
        }).eq('id', deal_id).eq('organization_id', organization_id).execute()

        if result.data:
            return Deal.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error updating deal status: {e}")
        return None


def complete_deal(deal_id: str, organization_id: str) -> Optional[Deal]:
    """
    Mark a deal as completed.

    Args:
        deal_id: UUID of the deal
        organization_id: UUID of the organization

    Returns:
        Updated Deal object if successful, None on error
    """
    return update_deal_status(deal_id, organization_id, 'completed')


def cancel_deal(deal_id: str, organization_id: str) -> Optional[Deal]:
    """
    Mark a deal as cancelled.

    Args:
        deal_id: UUID of the deal
        organization_id: UUID of the organization

    Returns:
        Updated Deal object if successful, None on error
    """
    return update_deal_status(deal_id, organization_id, 'cancelled')


def update_deal_amount(
    deal_id: str,
    organization_id: str,
    total_amount: float,
    currency: Optional[str] = None
) -> Optional[Deal]:
    """
    Update the total amount of a deal.

    Args:
        deal_id: UUID of the deal
        organization_id: UUID of the organization
        total_amount: New total amount
        currency: Optional new currency

    Returns:
        Updated Deal object if successful, None on error
    """
    update_kwargs = {'total_amount': total_amount}
    if currency:
        update_kwargs['currency'] = currency

    return update_deal(deal_id, organization_id, **update_kwargs)


# ============================================================================
# DELETE Operations
# ============================================================================

def delete_deal(deal_id: str, organization_id: str) -> bool:
    """
    Delete a deal.

    Note: Deals should rarely be deleted. Consider cancelling instead.
    Only active deals with no plan-fact items should be deletable.

    Args:
        deal_id: UUID of the deal
        organization_id: UUID of the organization

    Returns:
        True if deleted successfully, False otherwise
    """
    supabase = get_supabase()

    try:
        # Check current status - only allow deletion of active deals
        deal = get_deal(deal_id, organization_id)
        if not deal:
            print(f"Deal not found: {deal_id}")
            return False

        if deal.status != 'active':
            print(f"Cannot delete deal with status: {deal.status}")
            return False

        # Check for plan_fact_items (if implemented)
        # This check would prevent deletion if payments are recorded
        try:
            plan_fact_check = supabase.table('plan_fact_items').select('id', count='exact') \
                .eq('deal_id', deal_id).execute()
            if plan_fact_check.count and plan_fact_check.count > 0:
                print(f"Cannot delete deal with plan-fact items")
                return False
        except Exception:
            # Table might not exist yet, continue with deletion
            pass

        result = supabase.table('deals').delete() \
            .eq('id', deal_id) \
            .eq('organization_id', organization_id) \
            .execute()

        return len(result.data) > 0 if result.data else False
    except Exception as e:
        print(f"Error deleting deal: {e}")
        return False


# ============================================================================
# Utility Functions
# ============================================================================

def generate_deal_number(organization_id: str, prefix: str = "DEAL") -> str:
    """
    Generate a unique deal number.

    Format: PREFIX-YYYY-NNNN (e.g., DEAL-2025-0001)

    Note: There's also a PostgreSQL function for this, but this Python
    version is useful when you need the number before inserting.

    Args:
        organization_id: UUID of the organization
        prefix: Prefix for the deal number (default: "DEAL")

    Returns:
        Generated deal number
    """
    supabase = get_supabase()
    year = datetime.now().year

    try:
        # Count existing deals this year
        result = supabase.table('deals').select('id', count='exact') \
            .eq('organization_id', organization_id) \
            .gte('signed_at', f'{year}-01-01') \
            .execute()

        count = (result.count or 0) + 1
        return f"{prefix}-{year}-{count:04d}"
    except Exception as e:
        print(f"Error generating deal number: {e}")
        # Fallback with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{prefix}-{timestamp}"


def get_deal_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get deal statistics for an organization.

    Args:
        organization_id: UUID of the organization

    Returns:
        Dict with various statistics
    """
    counts = count_deals_by_status(organization_id)

    # Get total amounts by status
    supabase = get_supabase()
    amounts = {'active': Decimal('0'), 'completed': Decimal('0'), 'cancelled': Decimal('0')}

    try:
        for status in DEAL_STATUSES:
            result = supabase.table('deals').select('total_amount, currency') \
                .eq('organization_id', organization_id) \
                .eq('status', status) \
                .execute()

            if result.data:
                # Sum amounts (assuming same currency for simplicity)
                total = sum(Decimal(str(row['total_amount'])) for row in result.data if row.get('total_amount'))
                amounts[status] = total
    except Exception as e:
        print(f"Error calculating deal amounts: {e}")

    return {
        'total': counts.get('total', 0),
        'active': counts.get('active', 0),
        'completed': counts.get('completed', 0),
        'cancelled': counts.get('cancelled', 0),
        'active_amount': float(amounts['active']),
        'completed_amount': float(amounts['completed']),
        'total_amount': float(amounts['active'] + amounts['completed']),
    }


def get_active_deals(organization_id: str, limit: int = 50) -> List[dict]:
    """
    Get active deals with full details (for finance dashboard).

    Args:
        organization_id: UUID of the organization
        limit: Maximum number of results

    Returns:
        List of deal dicts with specification and quote details
    """
    return get_deals_with_details(organization_id, status='active', limit=limit)


def get_recent_deals(
    organization_id: str,
    days: int = 30,
    limit: int = 20
) -> List[dict]:
    """
    Get recently signed deals.

    Args:
        organization_id: UUID of the organization
        days: Number of days to look back
        limit: Maximum number of results

    Returns:
        List of deal dicts
    """
    supabase = get_supabase()

    try:
        from_date = date.today().replace(day=max(1, date.today().day - days))

        result = supabase.table('deals').select(
            '*, specifications(specification_number), quotes(idn_quote, customer_name)'
        ) \
            .eq('organization_id', organization_id) \
            .gte('signed_at', from_date.isoformat()) \
            .order('signed_at', desc=True) \
            .limit(limit) \
            .execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting recent deals: {e}")
        return []


def get_deals_by_date_range(
    organization_id: str,
    start_date: date,
    end_date: date,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Deal]:
    """
    Get deals within a date range.

    Args:
        organization_id: UUID of the organization
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        status: Optional status filter
        limit: Maximum number of results

    Returns:
        List of Deal objects
    """
    supabase = get_supabase()

    try:
        query = supabase.table('deals').select('*') \
            .eq('organization_id', organization_id) \
            .gte('signed_at', start_date.isoformat()) \
            .lte('signed_at', end_date.isoformat())

        if status:
            query = query.eq('status', status)

        result = query.order('signed_at', desc=True).limit(limit).execute()

        return [Deal.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting deals by date range: {e}")
        return []


def search_deals(
    organization_id: str,
    search_term: str,
    limit: int = 20
) -> List[dict]:
    """
    Search deals by deal number, customer name, or quote IDN.

    Args:
        organization_id: UUID of the organization
        search_term: Search term
        limit: Maximum number of results

    Returns:
        List of deal dicts with related data
    """
    supabase = get_supabase()

    try:
        # Search by deal number (ILIKE for case-insensitive)
        result = supabase.table('deals').select(
            '*, specifications(specification_number), quotes(idn_quote, customer_name)'
        ) \
            .eq('organization_id', organization_id) \
            .ilike('deal_number', f'%{search_term}%') \
            .order('signed_at', desc=True) \
            .limit(limit) \
            .execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error searching deals: {e}")
        return []
