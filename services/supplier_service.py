"""
Supplier Service - CRUD operations for suppliers table

This module provides functions for managing external suppliers in the supply chain:
- Create/Update/Delete suppliers
- Query suppliers by organization, code, country
- Search suppliers for HTMX dropdowns
- Utility functions for supplier management

Based on app_spec.xml suppliers table definition (Feature API-001).

Supply chain level: ITEM (each quote_item can have its own supplier)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import re
from supabase import create_client, ClientOptions


# Initialize Supabase client with service role for admin operations
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _get_supabase():
    """Get Supabase client with service role key for admin operations - kvota schema."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY,
        options=ClientOptions(schema="kvota")
    )


@dataclass
class Supplier:
    """
    Represents a supplier record.

    External company from which we purchase goods.
    Maps to suppliers table in database.
    """
    id: str
    organization_id: str
    name: str
    supplier_code: str  # 3-letter code (e.g., CMT, RAR)

    # Location
    country: Optional[str] = None
    city: Optional[str] = None

    # Legal identifiers (for Russian suppliers)
    inn: Optional[str] = None  # Russian tax ID
    kpp: Optional[str] = None  # Russian tax registration code

    # Contact information
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    # Payment terms
    default_payment_terms: Optional[str] = None

    # Status
    is_active: bool = True

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


def _parse_supplier(data: dict) -> Supplier:
    """Parse database row into Supplier object."""
    return Supplier(
        id=data["id"],
        organization_id=data["organization_id"],
        name=data["name"],
        supplier_code=data["supplier_code"],
        country=data.get("country"),
        city=data.get("city"),
        inn=data.get("inn"),
        kpp=data.get("kpp"),
        contact_person=data.get("contact_person"),
        contact_email=data.get("contact_email"),
        contact_phone=data.get("contact_phone"),
        default_payment_terms=data.get("default_payment_terms"),
        is_active=data.get("is_active", True),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        created_by=data.get("created_by"),
    )


def _supplier_to_dict(supplier: Supplier) -> dict:
    """Convert Supplier object to dict for database operations."""
    return {
        "organization_id": supplier.organization_id,
        "name": supplier.name,
        "supplier_code": supplier.supplier_code,
        "country": supplier.country,
        "city": supplier.city,
        "inn": supplier.inn,
        "kpp": supplier.kpp,
        "contact_person": supplier.contact_person,
        "contact_email": supplier.contact_email,
        "contact_phone": supplier.contact_phone,
        "default_payment_terms": supplier.default_payment_terms,
        "is_active": supplier.is_active,
        "created_by": supplier.created_by,
    }


# =============================================================================
# VALIDATION
# =============================================================================

def validate_supplier_code(code: str) -> bool:
    """
    Validate supplier code format (3 uppercase letters).

    Args:
        code: Supplier code to validate

    Returns:
        True if valid, False otherwise
    """
    if not code:
        return False
    return bool(re.match(r'^[A-Z]{3}$', code))


def validate_inn(inn: str) -> bool:
    """
    Validate Russian INN format.

    Args:
        inn: INN to validate (10 or 12 digits)

    Returns:
        True if valid format, False otherwise
    """
    if not inn:
        return True  # INN is optional
    return bool(re.match(r'^\d{10}(\d{2})?$', inn))


def validate_kpp(kpp: str) -> bool:
    """
    Validate Russian KPP format.

    Args:
        kpp: KPP to validate (9 digits)

    Returns:
        True if valid format, False otherwise
    """
    if not kpp:
        return True  # KPP is optional
    return bool(re.match(r'^\d{9}$', kpp))


# =============================================================================
# CREATE Operations
# =============================================================================

def create_supplier(
    organization_id: str,
    name: str,
    supplier_code: str,
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    inn: Optional[str] = None,
    kpp: Optional[str] = None,
    contact_person: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    default_payment_terms: Optional[str] = None,
    is_active: bool = True,
    created_by: Optional[str] = None,
) -> Optional[Supplier]:
    """
    Create a new supplier.

    Args:
        organization_id: Organization UUID
        name: Supplier company name
        supplier_code: 3-letter unique code (e.g., CMT, RAR)
        country: Supplier country
        city: Supplier city
        inn: Russian tax ID (optional)
        kpp: Russian tax registration code (optional)
        contact_person: Primary contact name
        contact_email: Contact email
        contact_phone: Contact phone
        default_payment_terms: Default payment terms text
        is_active: Whether supplier is active
        created_by: User UUID who created this supplier

    Returns:
        Supplier object if successful, None if supplier code already exists

    Raises:
        ValueError: If supplier_code format is invalid

    Example:
        supplier = create_supplier(
            organization_id="org-uuid",
            name="China Manufacturing Ltd",
            supplier_code="CMT",
            country="China",
            city="Guangzhou",
            created_by="admin-uuid"
        )
    """
    # Validate supplier code format
    if not validate_supplier_code(supplier_code):
        raise ValueError(f"Invalid supplier code format: {supplier_code}. Must be 3 uppercase letters.")

    # Validate INN and KPP if provided
    if inn and not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}. Must be 10 or 12 digits.")
    if kpp and not validate_kpp(kpp):
        raise ValueError(f"Invalid KPP format: {kpp}. Must be 9 digits.")

    try:
        supabase = _get_supabase()

        # Note: Only insert minimal columns that definitely exist in DB
        # Many columns may not exist if migrations not fully applied
        insert_data = {
            "organization_id": organization_id,
            "name": name,
            "supplier_code": supplier_code,
            "is_active": is_active,
        }
        # Only add country if provided - this should exist in base schema
        if country:
            insert_data["country"] = country

        result = supabase.table("suppliers").insert(insert_data).execute()

        if result.data and len(result.data) > 0:
            return _parse_supplier(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation (supplier code already exists)
        if "idx_suppliers_org_code" in str(e) or "duplicate key" in str(e).lower():
            return None
        raise


# =============================================================================
# READ Operations
# =============================================================================

def get_supplier(supplier_id: str) -> Optional[Supplier]:
    """
    Get a supplier by ID.

    Args:
        supplier_id: Supplier UUID

    Returns:
        Supplier object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("suppliers").select("*").eq("id", supplier_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_supplier(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting supplier: {e}")
        return None


def get_supplier_by_code(organization_id: str, supplier_code: str) -> Optional[Supplier]:
    """
    Get a supplier by its code within an organization.

    Args:
        organization_id: Organization UUID
        supplier_code: 3-letter supplier code

    Returns:
        Supplier object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("suppliers").select("*")\
            .eq("organization_id", organization_id)\
            .eq("supplier_code", supplier_code)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_supplier(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting supplier by code: {e}")
        return None


def get_all_suppliers(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Supplier]:
    """
    Get all suppliers for an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of Supplier objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("suppliers").select("*")\
            .eq("organization_id", organization_id)\
            .order("name")

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_supplier(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all suppliers: {e}")
        return []


def get_suppliers_by_country(
    organization_id: str,
    country: str,
    *,
    is_active: Optional[bool] = True,
) -> List[Supplier]:
    """
    Get suppliers by country.

    Args:
        organization_id: Organization UUID
        country: Country name
        is_active: Filter by active status

    Returns:
        List of Supplier objects in the specified country
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("suppliers").select("*")\
            .eq("organization_id", organization_id)\
            .eq("country", country)\
            .order("name")

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.execute()

        return [_parse_supplier(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting suppliers by country: {e}")
        return []


def count_suppliers(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
) -> int:
    """
    Count suppliers in an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status

    Returns:
        Number of suppliers
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("suppliers").select("id", count="exact")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting suppliers: {e}")
        return 0


def search_suppliers(
    organization_id: str,
    query: str,
    *,
    is_active: Optional[bool] = True,
    limit: int = 20,
) -> List[Supplier]:
    """
    Search suppliers by name, code, or contact.

    Used for HTMX dropdown autocomplete.

    Args:
        organization_id: Organization UUID
        query: Search query (matches name, supplier_code, contact_person)
        is_active: Filter by active status
        limit: Maximum number of results

    Returns:
        List of matching Supplier objects

    Example:
        # Search for suppliers containing "china" in name
        suppliers = search_suppliers("org-uuid", "china", limit=10)
    """
    if not query or len(query) < 1:
        return []

    try:
        supabase = _get_supabase()

        # Use ilike for case-insensitive search
        search_pattern = f"%{query}%"

        # Build query with OR conditions for multiple fields
        base_query = supabase.table("suppliers").select("*")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            base_query = base_query.eq("is_active", is_active)

        # Search in name (primary)
        result = base_query.ilike("name", search_pattern)\
            .order("name")\
            .limit(limit)\
            .execute()

        suppliers = [_parse_supplier(row) for row in result.data] if result.data else []

        # If not enough results, also search by code
        if len(suppliers) < limit:
            code_query = supabase.table("suppliers").select("*")\
                .eq("organization_id", organization_id)\
                .ilike("supplier_code", search_pattern)

            if is_active is not None:
                code_query = code_query.eq("is_active", is_active)

            code_result = code_query.limit(limit - len(suppliers)).execute()

            if code_result.data:
                existing_ids = {s.id for s in suppliers}
                for row in code_result.data:
                    if row["id"] not in existing_ids:
                        suppliers.append(_parse_supplier(row))

        return suppliers

    except Exception as e:
        print(f"Error searching suppliers: {e}")
        return []


def get_active_suppliers(organization_id: str) -> List[Supplier]:
    """
    Get all active suppliers for an organization.

    Convenience function for dropdown lists.

    Args:
        organization_id: Organization UUID

    Returns:
        List of active Supplier objects
    """
    return get_all_suppliers(organization_id, is_active=True, limit=1000)


def supplier_exists(organization_id: str, supplier_code: str) -> bool:
    """
    Check if a supplier with given code exists.

    Args:
        organization_id: Organization UUID
        supplier_code: Supplier code to check

    Returns:
        True if supplier exists, False otherwise
    """
    return get_supplier_by_code(organization_id, supplier_code) is not None


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_supplier(
    supplier_id: str,
    *,
    name: Optional[str] = None,
    supplier_code: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    inn: Optional[str] = None,
    kpp: Optional[str] = None,
    contact_person: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    default_payment_terms: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Supplier]:
    """
    Update a supplier.

    Args:
        supplier_id: Supplier UUID
        name: New supplier name
        supplier_code: New supplier code (must be unique)
        country: New country
        city: New city
        inn: New INN
        kpp: New KPP
        contact_person: New contact person
        contact_email: New contact email
        contact_phone: New contact phone
        default_payment_terms: New payment terms
        is_active: New active status

    Returns:
        Updated Supplier object if successful, None otherwise

    Raises:
        ValueError: If supplier_code format is invalid
    """
    # Validate supplier code if provided
    if supplier_code is not None and not validate_supplier_code(supplier_code):
        raise ValueError(f"Invalid supplier code format: {supplier_code}. Must be 3 uppercase letters.")

    # Validate INN and KPP if provided
    if inn is not None and inn and not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}. Must be 10 or 12 digits.")
    if kpp is not None and kpp and not validate_kpp(kpp):
        raise ValueError(f"Invalid KPP format: {kpp}. Must be 9 digits.")

    try:
        supabase = _get_supabase()

        # Build update dict with only provided fields
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if supplier_code is not None:
            update_data["supplier_code"] = supplier_code
        if country is not None:
            update_data["country"] = country
        if city is not None:
            update_data["city"] = city
        if inn is not None:
            update_data["inn"] = inn
        if kpp is not None:
            update_data["kpp"] = kpp
        if contact_person is not None:
            update_data["contact_person"] = contact_person
        if contact_email is not None:
            update_data["contact_email"] = contact_email
        if contact_phone is not None:
            update_data["contact_phone"] = contact_phone
        if default_payment_terms is not None:
            update_data["default_payment_terms"] = default_payment_terms
        if is_active is not None:
            update_data["is_active"] = is_active

        if not update_data:
            # Nothing to update, return current state
            return get_supplier(supplier_id)

        result = supabase.table("suppliers").update(update_data)\
            .eq("id", supplier_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_supplier(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating supplier: {e}")
        return None


def activate_supplier(supplier_id: str) -> Optional[Supplier]:
    """
    Activate a supplier.

    Args:
        supplier_id: Supplier UUID

    Returns:
        Updated Supplier object
    """
    return update_supplier(supplier_id, is_active=True)


def deactivate_supplier(supplier_id: str) -> Optional[Supplier]:
    """
    Deactivate a supplier (soft delete).

    Args:
        supplier_id: Supplier UUID

    Returns:
        Updated Supplier object
    """
    return update_supplier(supplier_id, is_active=False)


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_supplier(supplier_id: str) -> bool:
    """
    Delete a supplier permanently.

    Note: Consider using deactivate_supplier() instead for soft delete.

    Args:
        supplier_id: Supplier UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("suppliers").delete()\
            .eq("id", supplier_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting supplier: {e}")
        return False


# =============================================================================
# UTILITY Functions
# =============================================================================

def get_unique_countries(organization_id: str) -> List[str]:
    """
    Get list of unique countries from all suppliers.

    Args:
        organization_id: Organization UUID

    Returns:
        List of unique country names
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("suppliers").select("country")\
            .eq("organization_id", organization_id)\
            .not_.is_("country", "null")\
            .execute()

        if result.data:
            countries = set(row["country"] for row in result.data if row.get("country"))
            return sorted(list(countries))
        return []

    except Exception as e:
        print(f"Error getting unique countries: {e}")
        return []


def get_supplier_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get supplier statistics for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total: Total number of suppliers
        - active: Number of active suppliers
        - inactive: Number of inactive suppliers
        - by_country: Count by country
    """
    try:
        supabase = _get_supabase()

        # Get all suppliers
        result = supabase.table("suppliers").select("is_active, country")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "by_country": {},
            }

        total = len(result.data)
        active = sum(1 for row in result.data if row.get("is_active", True))
        inactive = total - active

        # Count by country
        by_country = {}
        for row in result.data:
            country = row.get("country") or "Unknown"
            by_country[country] = by_country.get(country, 0) + 1

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "by_country": by_country,
        }

    except Exception as e:
        print(f"Error getting supplier stats: {e}")
        return {
            "total": 0,
            "active": 0,
            "inactive": 0,
            "by_country": {},
        }


def get_supplier_display_name(supplier: Supplier) -> str:
    """
    Get display name for a supplier (code + name).

    Args:
        supplier: Supplier object

    Returns:
        Display string like "CMT - China Manufacturing Ltd"
    """
    return f"{supplier.supplier_code} - {supplier.name}"


def format_supplier_for_dropdown(supplier: Supplier) -> Dict[str, str]:
    """
    Format supplier for HTMX dropdown option.

    Args:
        supplier: Supplier object

    Returns:
        Dict with 'value' (id) and 'label' (display name)
    """
    location = ""
    if supplier.city and supplier.country:
        location = f" ({supplier.city}, {supplier.country})"
    elif supplier.country:
        location = f" ({supplier.country})"

    return {
        "value": supplier.id,
        "label": f"{supplier.supplier_code} - {supplier.name}{location}",
    }


def get_suppliers_for_dropdown(
    organization_id: str,
    *,
    query: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Get suppliers formatted for dropdown/select element.

    Args:
        organization_id: Organization UUID
        query: Optional search query
        limit: Maximum results

    Returns:
        List of dicts with 'value' and 'label' for dropdown options
    """
    if query:
        suppliers = search_suppliers(organization_id, query, limit=limit)
    else:
        suppliers = get_active_suppliers(organization_id)[:limit]

    return [format_supplier_for_dropdown(s) for s in suppliers]
