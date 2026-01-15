"""
Specification Service

CRUD operations for the specifications table.
Handles specification lifecycle from creation through signing.

Feature #73 from features.json
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
class Specification:
    """Represents a specification for a quote."""
    id: str
    quote_id: str
    organization_id: str
    quote_version_id: Optional[str]

    # Identification
    specification_number: Optional[str]
    proposal_idn: Optional[str]
    item_ind_sku: Optional[str]

    # Dates and validity
    sign_date: Optional[date]
    validity_period: Optional[str]
    readiness_period: Optional[str]
    logistics_period: Optional[str]

    # Currency and payment
    specification_currency: Optional[str]
    exchange_rate_to_ruble: Optional[Decimal]
    client_payment_term_after_upd: Optional[int]
    client_payment_terms: Optional[str]

    # Origin and shipping
    cargo_pickup_country: Optional[str]
    goods_shipment_country: Optional[str]
    delivery_city_russia: Optional[str]
    cargo_type: Optional[str]
    supplier_payment_country: Optional[str]

    # Legal entities
    our_legal_entity: Optional[str]
    client_legal_entity: Optional[str]

    # Status and files
    status: str  # 'draft', 'pending_review', 'approved', 'signed'
    signed_scan_url: Optional[str]

    # Audit
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_dict(cls, data: dict) -> 'Specification':
        """Create a Specification instance from a dictionary."""
        return cls(
            id=data['id'],
            quote_id=data['quote_id'],
            organization_id=data['organization_id'],
            quote_version_id=data.get('quote_version_id'),

            # Identification
            specification_number=data.get('specification_number'),
            proposal_idn=data.get('proposal_idn'),
            item_ind_sku=data.get('item_ind_sku'),

            # Dates and validity
            sign_date=datetime.strptime(data['sign_date'], '%Y-%m-%d').date() if data.get('sign_date') else None,
            validity_period=data.get('validity_period'),
            readiness_period=data.get('readiness_period'),
            logistics_period=data.get('logistics_period'),

            # Currency and payment
            specification_currency=data.get('specification_currency'),
            exchange_rate_to_ruble=Decimal(str(data['exchange_rate_to_ruble'])) if data.get('exchange_rate_to_ruble') else None,
            client_payment_term_after_upd=data.get('client_payment_term_after_upd'),
            client_payment_terms=data.get('client_payment_terms'),

            # Origin and shipping
            cargo_pickup_country=data.get('cargo_pickup_country'),
            goods_shipment_country=data.get('goods_shipment_country'),
            delivery_city_russia=data.get('delivery_city_russia'),
            cargo_type=data.get('cargo_type'),
            supplier_payment_country=data.get('supplier_payment_country'),

            # Legal entities
            our_legal_entity=data.get('our_legal_entity'),
            client_legal_entity=data.get('client_legal_entity'),

            # Status and files
            status=data.get('status', 'draft'),
            signed_scan_url=data.get('signed_scan_url'),

            # Audit
            created_by=data['created_by'],
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')) if isinstance(data['created_at'], str) else data['created_at'],
            updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')) if data.get('updated_at') and isinstance(data['updated_at'], str) else data.get('updated_at'),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'quote_id': self.quote_id,
            'organization_id': self.organization_id,
            'quote_version_id': self.quote_version_id,
            'specification_number': self.specification_number,
            'proposal_idn': self.proposal_idn,
            'item_ind_sku': self.item_ind_sku,
            'sign_date': self.sign_date.isoformat() if self.sign_date else None,
            'validity_period': self.validity_period,
            'readiness_period': self.readiness_period,
            'logistics_period': self.logistics_period,
            'specification_currency': self.specification_currency,
            'exchange_rate_to_ruble': float(self.exchange_rate_to_ruble) if self.exchange_rate_to_ruble else None,
            'client_payment_term_after_upd': self.client_payment_term_after_upd,
            'client_payment_terms': self.client_payment_terms,
            'cargo_pickup_country': self.cargo_pickup_country,
            'goods_shipment_country': self.goods_shipment_country,
            'delivery_city_russia': self.delivery_city_russia,
            'cargo_type': self.cargo_type,
            'supplier_payment_country': self.supplier_payment_country,
            'our_legal_entity': self.our_legal_entity,
            'client_legal_entity': self.client_legal_entity,
            'status': self.status,
            'signed_scan_url': self.signed_scan_url,
            'created_by': self.created_by,
        }


# Valid specification statuses
SPEC_STATUSES = ['draft', 'pending_review', 'approved', 'signed']

# Status names for display
SPEC_STATUS_NAMES = {
    'draft': 'Черновик',
    'pending_review': 'На проверке',
    'approved': 'Утверждено',
    'signed': 'Подписано',
}

# Status colors for UI
SPEC_STATUS_COLORS = {
    'draft': '#6b7280',  # gray
    'pending_review': '#f59e0b',  # amber
    'approved': '#10b981',  # green
    'signed': '#3b82f6',  # blue
}

# Allowed status transitions
SPEC_TRANSITIONS = {
    'draft': ['pending_review'],
    'pending_review': ['draft', 'approved'],
    'approved': ['pending_review', 'signed'],
    'signed': [],  # Terminal status
}


# ============================================================================
# Status Helper Functions
# ============================================================================

def get_spec_status_name(status: str) -> str:
    """Get human-readable status name."""
    return SPEC_STATUS_NAMES.get(status, status)


def get_spec_status_color(status: str) -> str:
    """Get color for status display."""
    return SPEC_STATUS_COLORS.get(status, '#6b7280')


def can_transition_spec(from_status: str, to_status: str) -> bool:
    """Check if a specification can transition between statuses."""
    allowed = SPEC_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def get_allowed_spec_transitions(from_status: str) -> List[str]:
    """Get list of allowed target statuses from current status."""
    return SPEC_TRANSITIONS.get(from_status, [])


# ============================================================================
# CREATE Operations
# ============================================================================

def create_specification(
    quote_id: str,
    organization_id: str,
    created_by: str,
    specification_number: Optional[str] = None,
    proposal_idn: Optional[str] = None,
    item_ind_sku: Optional[str] = None,
    sign_date: Optional[date] = None,
    validity_period: Optional[str] = None,
    readiness_period: Optional[str] = None,
    logistics_period: Optional[str] = None,
    specification_currency: Optional[str] = None,
    exchange_rate_to_ruble: Optional[float] = None,
    client_payment_term_after_upd: Optional[int] = None,
    client_payment_terms: Optional[str] = None,
    cargo_pickup_country: Optional[str] = None,
    goods_shipment_country: Optional[str] = None,
    delivery_city_russia: Optional[str] = None,
    cargo_type: Optional[str] = None,
    supplier_payment_country: Optional[str] = None,
    our_legal_entity: Optional[str] = None,
    client_legal_entity: Optional[str] = None,
    quote_version_id: Optional[str] = None,
    status: str = 'draft'
) -> Optional[Specification]:
    """
    Create a new specification.

    Args:
        quote_id: ID of the quote this specification is for
        organization_id: ID of the organization
        created_by: ID of the user creating the specification
        ... (all 18 spec fields)
        status: Initial status (default: 'draft')

    Returns:
        Specification object if created successfully, None on error

    Example:
        spec = create_specification(
            quote_id='abc-123',
            organization_id='org-456',
            created_by='user-789',
            specification_number='SPEC-2025-001',
            specification_currency='USD'
        )
    """
    if status not in SPEC_STATUSES:
        print(f"Invalid specification status: {status}")
        return None

    supabase = get_supabase()

    try:
        spec_data = {
            'quote_id': quote_id,
            'organization_id': organization_id,
            'created_by': created_by,
            'quote_version_id': quote_version_id,
            'specification_number': specification_number,
            'proposal_idn': proposal_idn,
            'item_ind_sku': item_ind_sku,
            'sign_date': sign_date.isoformat() if sign_date else None,
            'validity_period': validity_period,
            'readiness_period': readiness_period,
            'logistics_period': logistics_period,
            'specification_currency': specification_currency,
            'exchange_rate_to_ruble': exchange_rate_to_ruble,
            'client_payment_term_after_upd': client_payment_term_after_upd,
            'client_payment_terms': client_payment_terms,
            'cargo_pickup_country': cargo_pickup_country,
            'goods_shipment_country': goods_shipment_country,
            'delivery_city_russia': delivery_city_russia,
            'cargo_type': cargo_type,
            'supplier_payment_country': supplier_payment_country,
            'our_legal_entity': our_legal_entity,
            'client_legal_entity': client_legal_entity,
            'status': status,
        }

        # Remove None values to use database defaults
        spec_data = {k: v for k, v in spec_data.items() if v is not None}

        result = supabase.table('specifications').insert(spec_data).execute()

        if result.data:
            return Specification.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error creating specification: {e}")
        return None


# ============================================================================
# READ Operations
# ============================================================================

def get_specification(spec_id: str, organization_id: Optional[str] = None) -> Optional[Specification]:
    """
    Get a single specification by ID.

    Args:
        spec_id: UUID of the specification
        organization_id: Optional org ID for security check

    Returns:
        Specification object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('specifications').select('*').eq('id', spec_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        result = query.execute()

        if result.data:
            return Specification.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting specification: {e}")
        return None


def get_specification_by_quote(quote_id: str, organization_id: Optional[str] = None) -> Optional[Specification]:
    """
    Get specification for a quote.

    Args:
        quote_id: UUID of the quote
        organization_id: Optional org ID for security check

    Returns:
        Specification object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('specifications').select('*').eq('quote_id', quote_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        result = query.order('created_at', desc=True).limit(1).execute()

        if result.data:
            return Specification.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting specification by quote: {e}")
        return None


def get_specifications_by_status(
    organization_id: str,
    status: str,
    limit: int = 50
) -> List[Specification]:
    """
    Get all specifications with a given status.

    Args:
        organization_id: UUID of the organization
        status: Specification status ('draft', 'pending_review', 'approved', 'signed')
        limit: Maximum number of results

    Returns:
        List of Specification objects
    """
    supabase = get_supabase()

    try:
        result = supabase.table('specifications').select('*') \
            .eq('organization_id', organization_id) \
            .eq('status', status) \
            .order('created_at', desc=True) \
            .limit(limit) \
            .execute()

        return [Specification.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting specifications by status: {e}")
        return []


def get_all_specifications(
    organization_id: str,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Specification]:
    """
    Get all specifications for an organization.

    Args:
        organization_id: UUID of the organization
        status: Optional status filter
        limit: Maximum number of results

    Returns:
        List of Specification objects
    """
    supabase = get_supabase()

    try:
        query = supabase.table('specifications').select('*') \
            .eq('organization_id', organization_id)

        if status:
            query = query.eq('status', status)

        result = query.order('created_at', desc=True).limit(limit).execute()

        return [Specification.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting all specifications: {e}")
        return []


def get_specifications_with_details(
    organization_id: str,
    status: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """
    Get specifications with quote and customer details.

    Args:
        organization_id: UUID of the organization
        status: Optional status filter
        limit: Maximum number of results

    Returns:
        List of dicts with specification, quote, and customer details
    """
    supabase = get_supabase()

    try:
        query = supabase.table('specifications').select(
            '*, quotes(id, idn_quote, customer_name, total_amount, currency, workflow_status, customers(id, name, inn, company_name))'
        ).eq('organization_id', organization_id)

        if status:
            query = query.eq('status', status)

        result = query.order('created_at', desc=True).limit(limit).execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting specifications with details: {e}")
        return []


def count_specifications_by_status(organization_id: str) -> Dict[str, int]:
    """
    Count specifications by status for an organization.

    Args:
        organization_id: UUID of the organization

    Returns:
        Dict with counts per status: {'draft': 5, 'pending_review': 3, ...}
    """
    supabase = get_supabase()

    counts = {status: 0 for status in SPEC_STATUSES}

    try:
        for status in SPEC_STATUSES:
            result = supabase.table('specifications').select('id', count='exact') \
                .eq('organization_id', organization_id) \
                .eq('status', status) \
                .execute()

            counts[status] = result.count if result.count else 0

        counts['total'] = sum(counts.values())
        return counts
    except Exception as e:
        print(f"Error counting specifications: {e}")
        return counts


def specification_exists_for_quote(quote_id: str, organization_id: Optional[str] = None) -> bool:
    """
    Check if a specification already exists for a quote.

    Args:
        quote_id: UUID of the quote
        organization_id: Optional org ID for security check

    Returns:
        True if specification exists, False otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('specifications').select('id', count='exact').eq('quote_id', quote_id)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        result = query.execute()

        return (result.count or 0) > 0
    except Exception as e:
        print(f"Error checking specification existence: {e}")
        return False


# ============================================================================
# UPDATE Operations
# ============================================================================

def update_specification(
    spec_id: str,
    organization_id: str,
    **kwargs
) -> Optional[Specification]:
    """
    Update specification fields.

    Args:
        spec_id: UUID of the specification
        organization_id: UUID of the organization (for security)
        **kwargs: Fields to update (any of the 18 spec fields)

    Returns:
        Updated Specification object if successful, None on error

    Example:
        spec = update_specification(
            spec_id='abc-123',
            organization_id='org-456',
            specification_number='SPEC-2025-002',
            sign_date=date.today()
        )
    """
    supabase = get_supabase()

    # Validate status if being updated
    if 'status' in kwargs and kwargs['status'] not in SPEC_STATUSES:
        print(f"Invalid specification status: {kwargs['status']}")
        return None

    try:
        # Convert date objects to ISO strings
        update_data = {}
        for key, value in kwargs.items():
            if isinstance(value, date):
                update_data[key] = value.isoformat()
            elif isinstance(value, Decimal):
                update_data[key] = float(value)
            else:
                update_data[key] = value

        # Add updated_at timestamp
        update_data['updated_at'] = datetime.now().isoformat()

        result = supabase.table('specifications').update(update_data) \
            .eq('id', spec_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if result.data:
            return Specification.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error updating specification: {e}")
        return None


def update_specification_status(
    spec_id: str,
    organization_id: str,
    new_status: str,
    validate_transition: bool = True
) -> Optional[Specification]:
    """
    Update specification status with optional transition validation.

    Args:
        spec_id: UUID of the specification
        organization_id: UUID of the organization
        new_status: Target status
        validate_transition: Whether to validate the transition (default: True)

    Returns:
        Updated Specification object if successful, None on error
    """
    if new_status not in SPEC_STATUSES:
        print(f"Invalid specification status: {new_status}")
        return None

    supabase = get_supabase()

    try:
        # Get current status for validation
        if validate_transition:
            current = get_specification(spec_id, organization_id)
            if not current:
                print(f"Specification not found: {spec_id}")
                return None

            if not can_transition_spec(current.status, new_status):
                print(f"Cannot transition from {current.status} to {new_status}")
                return None

        result = supabase.table('specifications').update({
            'status': new_status,
            'updated_at': datetime.now().isoformat()
        }).eq('id', spec_id).eq('organization_id', organization_id).execute()

        if result.data:
            return Specification.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error updating specification status: {e}")
        return None


def set_signed_scan_url(
    spec_id: str,
    organization_id: str,
    signed_scan_url: str
) -> Optional[Specification]:
    """
    Set the signed scan URL for a specification.

    Args:
        spec_id: UUID of the specification
        organization_id: UUID of the organization
        signed_scan_url: Public URL of the signed scan

    Returns:
        Updated Specification object if successful, None on error
    """
    return update_specification(
        spec_id=spec_id,
        organization_id=organization_id,
        signed_scan_url=signed_scan_url
    )


# ============================================================================
# DELETE Operations
# ============================================================================

def delete_specification(spec_id: str, organization_id: str) -> bool:
    """
    Delete a specification.

    Note: Typically specifications should not be deleted once they have
    progressed beyond draft status. Consider using soft delete instead.

    Args:
        spec_id: UUID of the specification
        organization_id: UUID of the organization

    Returns:
        True if deleted successfully, False otherwise
    """
    supabase = get_supabase()

    try:
        # Check current status - only allow deletion of drafts
        spec = get_specification(spec_id, organization_id)
        if not spec:
            print(f"Specification not found: {spec_id}")
            return False

        if spec.status != 'draft':
            print(f"Cannot delete specification with status: {spec.status}")
            return False

        result = supabase.table('specifications').delete() \
            .eq('id', spec_id) \
            .eq('organization_id', organization_id) \
            .execute()

        return len(result.data) > 0 if result.data else False
    except Exception as e:
        print(f"Error deleting specification: {e}")
        return False


# ============================================================================
# Utility Functions
# ============================================================================

def generate_specification_number(organization_id: str, prefix: str = "SPEC") -> str:
    """
    Generate a unique specification number.

    Format: PREFIX-YYYY-NNNN (e.g., SPEC-2025-0001)

    Args:
        organization_id: UUID of the organization
        prefix: Prefix for the spec number (default: "SPEC")

    Returns:
        Generated specification number
    """
    supabase = get_supabase()
    year = datetime.now().year

    try:
        # Count existing specs this year
        result = supabase.table('specifications').select('id', count='exact') \
            .eq('organization_id', organization_id) \
            .gte('created_at', f'{year}-01-01') \
            .execute()

        count = (result.count or 0) + 1
        return f"{prefix}-{year}-{count:04d}"
    except Exception as e:
        print(f"Error generating specification number: {e}")
        # Fallback with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{prefix}-{timestamp}"


def get_specification_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get specification statistics for an organization.

    Args:
        organization_id: UUID of the organization

    Returns:
        Dict with various statistics
    """
    counts = count_specifications_by_status(organization_id)

    return {
        'total': counts.get('total', 0),
        'draft': counts.get('draft', 0),
        'pending_review': counts.get('pending_review', 0),
        'approved': counts.get('approved', 0),
        'signed': counts.get('signed', 0),
        'needs_attention': counts.get('pending_review', 0),  # Alias for dashboard
        'ready_for_signing': counts.get('approved', 0),  # Alias for dashboard
    }


def get_specifications_for_signing(organization_id: str, limit: int = 20) -> List[dict]:
    """
    Get specifications that are ready for signing (approved status with no signed scan).

    Args:
        organization_id: UUID of the organization
        limit: Maximum number of results

    Returns:
        List of specification dicts with quote details
    """
    supabase = get_supabase()

    try:
        result = supabase.table('specifications').select(
            '*, quotes(id, idn_quote, customer_name, customers(name, company_name))'
        ) \
            .eq('organization_id', organization_id) \
            .eq('status', 'approved') \
            .is_('signed_scan_url', 'null') \
            .order('created_at', desc=True) \
            .limit(limit) \
            .execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting specifications for signing: {e}")
        return []


def get_recently_signed_specifications(
    organization_id: str,
    days: int = 30,
    limit: int = 20
) -> List[dict]:
    """
    Get recently signed specifications.

    Args:
        organization_id: UUID of the organization
        days: Number of days to look back
        limit: Maximum number of results

    Returns:
        List of specification dicts
    """
    supabase = get_supabase()

    try:
        from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from_date = from_date.replace(day=from_date.day - days) if from_date.day > days else from_date.replace(month=from_date.month - 1, day=28)

        result = supabase.table('specifications').select(
            '*, quotes(id, idn_quote, customer_name)'
        ) \
            .eq('organization_id', organization_id) \
            .eq('status', 'signed') \
            .gte('updated_at', from_date.isoformat()) \
            .order('updated_at', desc=True) \
            .limit(limit) \
            .execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting recently signed specifications: {e}")
        return []


# ============================================================================
# Create Specification from Quote (Feature #74)
# ============================================================================

@dataclass
class CreateSpecFromQuoteResult:
    """Result of creating a specification from a quote."""
    success: bool
    specification: Optional[Specification] = None
    error: Optional[str] = None
    prefilled_fields: Optional[Dict[str, Any]] = None


def create_specification_from_quote(
    quote_id: str,
    organization_id: str,
    created_by: str,
    version_id: Optional[str] = None,
    additional_fields: Optional[Dict[str, Any]] = None
) -> CreateSpecFromQuoteResult:
    """
    Create a new specification by extracting data from an existing quote.

    This function fetches the quote data (and optionally a specific version),
    extracts relevant fields, and creates a new specification in 'draft' status.

    Args:
        quote_id: UUID of the quote to create specification from
        organization_id: UUID of the organization
        created_by: UUID of the user creating the specification
        version_id: Optional UUID of a specific quote version to use
        additional_fields: Optional dict of additional spec fields to set

    Returns:
        CreateSpecFromQuoteResult with:
        - success: bool indicating if creation succeeded
        - specification: The created Specification object (if success)
        - error: Error message (if failure)
        - prefilled_fields: Dict showing which fields were prefilled from quote

    Example:
        result = create_specification_from_quote(
            quote_id='abc-123',
            organization_id='org-456',
            created_by='user-789',
            version_id='version-111',
            additional_fields={'our_legal_entity': 'Company LLC'}
        )
        if result.success:
            print(f"Created spec: {result.specification.id}")
    """
    supabase = get_supabase()

    try:
        # 1. Check if specification already exists for this quote
        if specification_exists_for_quote(quote_id, organization_id):
            return CreateSpecFromQuoteResult(
                success=False,
                error="Specification already exists for this quote"
            )

        # 2. Fetch quote with customer info
        quote_result = supabase.table('quotes').select(
            '*, customers(id, name, company_name, inn)'
        ).eq('id', quote_id).eq('organization_id', organization_id).execute()

        if not quote_result.data:
            return CreateSpecFromQuoteResult(
                success=False,
                error="Quote not found or access denied"
            )

        quote = quote_result.data[0]
        customer = quote.get('customers', {}) or {}

        # 3. Fetch calculation variables for additional prefill data
        vars_result = supabase.table('quote_calculation_variables').select(
            'variables'
        ).eq('quote_id', quote_id).execute()

        calc_vars = vars_result.data[0].get('variables', {}) if vars_result.data else {}

        # 4. If version_id specified, fetch version data
        version_data = None
        if version_id:
            version_result = supabase.table('quote_versions').select(
                'id, version, input_variables, currency_of_quote, seller_company, offer_sale_type, offer_incoterms'
            ).eq('id', version_id).eq('quote_id', quote_id).execute()

            if version_result.data:
                version_data = version_result.data[0]
                # Extract variables from version's input_variables
                input_vars = version_data.get('input_variables', {})
                if input_vars.get('variables'):
                    calc_vars = input_vars.get('variables')

        # 5. Build prefilled data from quote and calculation variables
        prefilled_fields = {}

        # Identification
        prefilled_fields['proposal_idn'] = quote.get('idn_quote')
        prefilled_fields['specification_number'] = generate_specification_number(organization_id)

        # Currency and payment
        prefilled_fields['specification_currency'] = (
            version_data.get('currency_of_quote') if version_data
            else quote.get('currency', 'USD')
        )

        # Extract exchange rate if available
        if version_data and version_data.get('input_variables', {}).get('exchange_rate'):
            rate_data = version_data['input_variables']['exchange_rate']
            prefilled_fields['exchange_rate_to_ruble'] = rate_data.get('rate')

        # Payment terms from calculation variables
        if calc_vars.get('time_to_advance_on_receiving'):
            prefilled_fields['client_payment_term_after_upd'] = int(calc_vars['time_to_advance_on_receiving'])

        # Build client payment terms string from variables
        payment_terms_parts = []
        if calc_vars.get('advance_from_client'):
            advance_pct = float(calc_vars.get('advance_from_client', 0))
            if advance_pct > 0:
                payment_terms_parts.append(f"{advance_pct:.0f}% аванс")
            if advance_pct < 100:
                remaining = 100 - advance_pct
                payment_terms_parts.append(f"{remaining:.0f}% после доставки")
        if payment_terms_parts:
            prefilled_fields['client_payment_terms'] = ", ".join(payment_terms_parts)

        # Origin and shipping from calculation variables
        if calc_vars.get('supplier_country'):
            prefilled_fields['cargo_pickup_country'] = calc_vars['supplier_country']

        if calc_vars.get('delivery_city'):
            prefilled_fields['delivery_city_russia'] = calc_vars['delivery_city']

        # Legal entities
        if customer.get('company_name'):
            prefilled_fields['client_legal_entity'] = customer['company_name']
        elif customer.get('name'):
            prefilled_fields['client_legal_entity'] = customer['name']

        # Seller company from calculation variables or version
        if version_data and version_data.get('seller_company'):
            prefilled_fields['our_legal_entity'] = version_data['seller_company']
        elif calc_vars.get('seller_company'):
            prefilled_fields['our_legal_entity'] = calc_vars['seller_company']

        # Logistics period from delivery time
        if calc_vars.get('delivery_time'):
            delivery_days = int(calc_vars['delivery_time'])
            prefilled_fields['logistics_period'] = f"{delivery_days} дней"

        # Readiness period from production days if available
        if calc_vars.get('production_days'):
            prod_days = int(calc_vars['production_days'])
            prefilled_fields['readiness_period'] = f"{prod_days} дней"

        # 6. Merge additional fields (override prefilled)
        if additional_fields:
            prefilled_fields.update(additional_fields)

        # 7. Create the specification
        spec = create_specification(
            quote_id=quote_id,
            organization_id=organization_id,
            created_by=created_by,
            quote_version_id=version_id,
            specification_number=prefilled_fields.get('specification_number'),
            proposal_idn=prefilled_fields.get('proposal_idn'),
            specification_currency=prefilled_fields.get('specification_currency'),
            exchange_rate_to_ruble=prefilled_fields.get('exchange_rate_to_ruble'),
            client_payment_term_after_upd=prefilled_fields.get('client_payment_term_after_upd'),
            client_payment_terms=prefilled_fields.get('client_payment_terms'),
            cargo_pickup_country=prefilled_fields.get('cargo_pickup_country'),
            delivery_city_russia=prefilled_fields.get('delivery_city_russia'),
            our_legal_entity=prefilled_fields.get('our_legal_entity'),
            client_legal_entity=prefilled_fields.get('client_legal_entity'),
            logistics_period=prefilled_fields.get('logistics_period'),
            readiness_period=prefilled_fields.get('readiness_period'),
            goods_shipment_country=prefilled_fields.get('goods_shipment_country'),
            cargo_type=prefilled_fields.get('cargo_type'),
            supplier_payment_country=prefilled_fields.get('supplier_payment_country'),
            validity_period=prefilled_fields.get('validity_period'),
            item_ind_sku=prefilled_fields.get('item_ind_sku'),
            sign_date=prefilled_fields.get('sign_date'),
            status='draft'
        )

        if spec:
            return CreateSpecFromQuoteResult(
                success=True,
                specification=spec,
                prefilled_fields=prefilled_fields
            )
        else:
            return CreateSpecFromQuoteResult(
                success=False,
                error="Failed to create specification record"
            )

    except Exception as e:
        print(f"Error creating specification from quote: {e}")
        return CreateSpecFromQuoteResult(
            success=False,
            error=str(e)
        )
