"""
IDN Service - Identification Number management for quotes and items

Feature #IDN-001: Implement IDN generation for quotes
Feature #IDN-002: Implement IDN generation for quote items

IDN Format:
- Quote IDN: SELLER-INN-YEAR-SEQ (e.g., CMT-1234567890-2025-1)
- Item IDN: QUOTE_IDN-POSITION (e.g., CMT-1234567890-2025-1-001)

The database handles IDN generation via triggers, but this service provides:
1. Manual IDN generation when needed
2. IDN parsing and validation
3. Utility functions for working with IDNs
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from .database import get_supabase


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ParsedQuoteIDN:
    """Parsed components of a Quote IDN"""
    seller_code: str
    customer_inn: str
    year: int
    sequence: int

    @property
    def full_idn(self) -> str:
        """Reconstruct the full IDN"""
        return f"{self.seller_code}-{self.customer_inn}-{self.year}-{self.sequence}"


@dataclass
class ParsedItemIDN:
    """Parsed components of an Item IDN"""
    quote_idn: ParsedQuoteIDN
    position: int

    @property
    def full_idn(self) -> str:
        """Reconstruct the full item IDN"""
        return f"{self.quote_idn.full_idn}-{str(self.position).zfill(3)}"


@dataclass
class IDNGenerationResult:
    """Result of IDN generation operation"""
    success: bool
    idn: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# IDN FORMAT CONSTANTS
# =============================================================================

# Quote IDN format: SELLER-INN-YEAR-SEQ
# Example: CMT-1234567890-2025-1
QUOTE_IDN_PATTERN = re.compile(
    r'^([A-Z]{2,5})-(\d{10,12})-(\d{4})-(\d+)$'
)

# Item IDN format: QUOTE_IDN-POSITION (3-digit padded)
# Example: CMT-1234567890-2025-1-001
ITEM_IDN_PATTERN = re.compile(
    r'^([A-Z]{2,5})-(\d{10,12})-(\d{4})-(\d+)-(\d{3})$'
)


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def parse_quote_idn(idn: str) -> Optional[ParsedQuoteIDN]:
    """
    Parse a Quote IDN into its components.

    Args:
        idn: The quote IDN string (e.g., "CMT-1234567890-2025-1")

    Returns:
        ParsedQuoteIDN if valid, None if invalid format
    """
    if not idn:
        return None

    match = QUOTE_IDN_PATTERN.match(idn)
    if not match:
        return None

    return ParsedQuoteIDN(
        seller_code=match.group(1),
        customer_inn=match.group(2),
        year=int(match.group(3)),
        sequence=int(match.group(4))
    )


def parse_item_idn(idn: str) -> Optional[ParsedItemIDN]:
    """
    Parse an Item IDN into its components.

    Args:
        idn: The item IDN string (e.g., "CMT-1234567890-2025-1-001")

    Returns:
        ParsedItemIDN if valid, None if invalid format
    """
    if not idn:
        return None

    match = ITEM_IDN_PATTERN.match(idn)
    if not match:
        return None

    quote_idn = ParsedQuoteIDN(
        seller_code=match.group(1),
        customer_inn=match.group(2),
        year=int(match.group(3)),
        sequence=int(match.group(4))
    )

    return ParsedItemIDN(
        quote_idn=quote_idn,
        position=int(match.group(5))
    )


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def is_valid_quote_idn(idn: str) -> bool:
    """
    Validate a Quote IDN format.

    Args:
        idn: The quote IDN string to validate

    Returns:
        True if valid format, False otherwise
    """
    return parse_quote_idn(idn) is not None


def is_valid_item_idn(idn: str) -> bool:
    """
    Validate an Item IDN format.

    Args:
        idn: The item IDN string to validate

    Returns:
        True if valid format, False otherwise
    """
    return parse_item_idn(idn) is not None


def validate_seller_code(code: str) -> bool:
    """
    Validate seller company code format.

    Args:
        code: The seller code (e.g., "CMT", "MBR", "RAR")

    Returns:
        True if valid (2-5 uppercase letters), False otherwise
    """
    if not code:
        return False
    return bool(re.match(r'^[A-Z]{2,5}$', code))


def validate_inn(inn: str) -> bool:
    """
    Validate Russian INN format.

    Args:
        inn: The INN string (10 or 12 digits)

    Returns:
        True if valid format, False otherwise
    """
    if not inn:
        return False
    return bool(re.match(r'^\d{10}(\d{2})?$', inn))


# =============================================================================
# QUOTE IDN GENERATION
# =============================================================================

def generate_quote_idn(
    seller_company_id: UUID,
    customer_inn: str
) -> IDNGenerationResult:
    """
    Generate IDN for a quote using the database function.

    This calls the database function generate_quote_idn() which:
    1. Gets seller company code
    2. Gets current year
    3. Increments counter in organization.idn_counters
    4. Returns formatted IDN

    Args:
        seller_company_id: UUID of the seller company
        customer_inn: Customer's INN (tax identification number)

    Returns:
        IDNGenerationResult with generated IDN or error
    """
    if not seller_company_id:
        return IDNGenerationResult(
            success=False,
            error="seller_company_id is required"
        )

    if not customer_inn or not validate_inn(customer_inn):
        return IDNGenerationResult(
            success=False,
            error="Valid customer INN is required (10 or 12 digits)"
        )

    try:
        supabase = get_supabase()

        # Call the database function
        result = supabase.rpc(
            'generate_quote_idn',
            {
                'p_seller_company_id': str(seller_company_id),
                'p_customer_inn': customer_inn
            }
        ).execute()

        if result.data:
            return IDNGenerationResult(
                success=True,
                idn=result.data
            )
        else:
            return IDNGenerationResult(
                success=False,
                error="IDN generation returned no result"
            )

    except Exception as e:
        return IDNGenerationResult(
            success=False,
            error=f"Failed to generate IDN: {str(e)}"
        )


def assign_idn_to_quote(quote_id: UUID) -> IDNGenerationResult:
    """
    Generate and assign IDN to an existing quote.

    This function:
    1. Gets the quote's seller_company_id and customer's INN
    2. Generates IDN using generate_quote_idn()
    3. Updates the quote with the new IDN

    Args:
        quote_id: UUID of the quote to assign IDN to

    Returns:
        IDNGenerationResult with the assigned IDN or error
    """
    try:
        supabase = get_supabase()

        # Get quote with customer and seller company info
        quote_result = supabase.table('quotes').select(
            'id, idn, seller_company_id, customer_id, customers(inn)'
        ).eq('id', str(quote_id)).single().execute()

        if not quote_result.data:
            return IDNGenerationResult(
                success=False,
                error=f"Quote not found: {quote_id}"
            )

        quote = quote_result.data

        # Check if IDN already exists
        if quote.get('idn'):
            return IDNGenerationResult(
                success=True,
                idn=quote['idn'],
                error="Quote already has IDN (no change made)"
            )

        # Validate required fields
        if not quote.get('seller_company_id'):
            return IDNGenerationResult(
                success=False,
                error="Quote must have seller_company_id to generate IDN"
            )

        customer_inn = quote.get('customers', {}).get('inn') if quote.get('customers') else None
        if not customer_inn:
            return IDNGenerationResult(
                success=False,
                error="Customer must have INN to generate IDN"
            )

        # Generate IDN
        gen_result = generate_quote_idn(
            UUID(quote['seller_company_id']),
            customer_inn
        )

        if not gen_result.success:
            return gen_result

        # Update quote with new IDN
        update_result = supabase.table('quotes').update({
            'idn': gen_result.idn
        }).eq('id', str(quote_id)).execute()

        if not update_result.data:
            return IDNGenerationResult(
                success=False,
                error="Failed to update quote with IDN"
            )

        return IDNGenerationResult(
            success=True,
            idn=gen_result.idn
        )

    except Exception as e:
        return IDNGenerationResult(
            success=False,
            error=f"Failed to assign IDN: {str(e)}"
        )


def get_quote_idn(quote_id: UUID) -> Optional[str]:
    """
    Get the IDN for a quote.

    Args:
        quote_id: UUID of the quote

    Returns:
        The quote's IDN or None if not set
    """
    try:
        supabase = get_supabase()
        result = supabase.table('quotes').select('idn').eq(
            'id', str(quote_id)
        ).single().execute()

        return result.data.get('idn') if result.data else None

    except Exception:
        return None


def get_quote_by_idn(idn: str) -> Optional[dict]:
    """
    Find a quote by its IDN.

    Args:
        idn: The quote IDN to search for

    Returns:
        Quote data dict or None if not found
    """
    if not is_valid_quote_idn(idn):
        return None

    try:
        supabase = get_supabase()
        result = supabase.table('quotes').select('*').eq('idn', idn).single().execute()
        return result.data
    except Exception:
        return None


# =============================================================================
# ITEM IDN GENERATION
# =============================================================================

def generate_item_idn(quote_id: UUID, position: int) -> IDNGenerationResult:
    """
    Generate IDN for a quote item using the database function.

    Args:
        quote_id: UUID of the parent quote
        position: Item position in the quote (1-based)

    Returns:
        IDNGenerationResult with generated item IDN or error
    """
    if not quote_id:
        return IDNGenerationResult(
            success=False,
            error="quote_id is required"
        )

    if position < 1:
        return IDNGenerationResult(
            success=False,
            error="Position must be >= 1"
        )

    try:
        supabase = get_supabase()

        # Call the database function
        result = supabase.rpc(
            'generate_item_idn',
            {
                'p_quote_id': str(quote_id),
                'p_position': position
            }
        ).execute()

        if result.data:
            return IDNGenerationResult(
                success=True,
                idn=result.data
            )
        else:
            # NULL result means parent quote doesn't have IDN yet
            return IDNGenerationResult(
                success=False,
                error="Parent quote does not have IDN yet"
            )

    except Exception as e:
        return IDNGenerationResult(
            success=False,
            error=f"Failed to generate item IDN: {str(e)}"
        )


def regenerate_item_idns_for_quote(quote_id: UUID) -> Tuple[bool, int, Optional[str]]:
    """
    Regenerate IDNs for all items in a quote.

    Use this after a quote gets an IDN to update all existing items.

    Args:
        quote_id: UUID of the quote

    Returns:
        Tuple of (success, count_updated, error_message)
    """
    try:
        supabase = get_supabase()

        # Call the database function
        result = supabase.rpc(
            'regenerate_item_idns_for_quote',
            {'p_quote_id': str(quote_id)}
        ).execute()

        count = result.data if result.data is not None else 0
        return (True, count, None)

    except Exception as e:
        return (False, 0, f"Failed to regenerate item IDNs: {str(e)}")


def get_item_idn(item_id: UUID) -> Optional[str]:
    """
    Get the IDN for a quote item.

    Args:
        item_id: UUID of the quote item

    Returns:
        The item's IDN or None if not set
    """
    try:
        supabase = get_supabase()
        result = supabase.table('quote_items').select('item_idn').eq(
            'id', str(item_id)
        ).single().execute()

        return result.data.get('item_idn') if result.data else None

    except Exception:
        return None


def get_item_by_idn(idn: str) -> Optional[dict]:
    """
    Find a quote item by its IDN.

    Args:
        idn: The item IDN to search for

    Returns:
        Quote item data dict or None if not found
    """
    if not is_valid_item_idn(idn):
        return None

    try:
        supabase = get_supabase()
        result = supabase.table('quote_items').select('*').eq('item_idn', idn).single().execute()
        return result.data
    except Exception:
        return None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def extract_quote_idn_from_item_idn(item_idn: str) -> Optional[str]:
    """
    Extract the quote IDN portion from an item IDN.

    Args:
        item_idn: The item IDN (e.g., "CMT-1234567890-2025-1-001")

    Returns:
        The quote IDN portion (e.g., "CMT-1234567890-2025-1") or None
    """
    parsed = parse_item_idn(item_idn)
    if parsed:
        return parsed.quote_idn.full_idn
    return None


def format_item_position(position: int) -> str:
    """
    Format item position as 3-digit padded string.

    Args:
        position: The position number (1-999)

    Returns:
        Zero-padded position string (e.g., "001", "042")
    """
    return str(position).zfill(3)


def get_year_from_idn(idn: str) -> Optional[int]:
    """
    Extract the year from a quote or item IDN.

    Args:
        idn: Quote or item IDN string

    Returns:
        The year as integer or None
    """
    parsed = parse_quote_idn(idn) or parse_item_idn(idn)
    if parsed:
        if isinstance(parsed, ParsedItemIDN):
            return parsed.quote_idn.year
        return parsed.year
    return None


def get_customer_inn_from_idn(idn: str) -> Optional[str]:
    """
    Extract the customer INN from a quote or item IDN.

    Args:
        idn: Quote or item IDN string

    Returns:
        The customer INN or None
    """
    parsed = parse_quote_idn(idn) or parse_item_idn(idn)
    if parsed:
        if isinstance(parsed, ParsedItemIDN):
            return parsed.quote_idn.customer_inn
        return parsed.customer_inn
    return None


def get_seller_code_from_idn(idn: str) -> Optional[str]:
    """
    Extract the seller company code from a quote or item IDN.

    Args:
        idn: Quote or item IDN string

    Returns:
        The seller code (e.g., "CMT") or None
    """
    parsed = parse_quote_idn(idn) or parse_item_idn(idn)
    if parsed:
        if isinstance(parsed, ParsedItemIDN):
            return parsed.quote_idn.seller_code
        return parsed.seller_code
    return None


def get_next_expected_sequence(
    organization_id: UUID,
    customer_inn: str,
    year: Optional[int] = None
) -> Optional[int]:
    """
    Get the next expected sequence number for a customer in a year.

    This looks up the idn_counters in the organization.

    Args:
        organization_id: UUID of the organization
        customer_inn: Customer's INN
        year: Year to check (defaults to current year)

    Returns:
        Next sequence number or None if lookup fails
    """
    try:
        supabase = get_supabase()

        if year is None:
            year = datetime.now().year

        counter_key = f"{year}-{customer_inn}"

        result = supabase.table('organizations').select(
            'idn_counters'
        ).eq('id', str(organization_id)).single().execute()

        if not result.data:
            return 1  # First quote for this org

        counters = result.data.get('idn_counters') or {}
        current = counters.get(counter_key, 0)

        return current + 1

    except Exception:
        return None
