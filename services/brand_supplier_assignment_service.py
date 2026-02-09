"""
Brand Supplier Assignment Service - CRUD operations for brand_supplier_assignments table

This module provides functions for managing brand-to-supplier assignments:
- Create/Update/Delete brand-supplier assignments
- Query assignments by organization, brand, or supplier
- Get primary supplier for a brand
- Utility functions for brand-supplier management

Based on migration 025_create_brand_supplier_assignments_table.sql (Feature API-008).

Note: This is different from brand_service.py which manages brand-to-procurement-manager assignments.
Supply chain: Brand -> Supplier (external company that provides the brand)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
from supabase import create_client
from supabase.client import ClientOptions


# Initialize Supabase client with service role for admin operations
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _get_supabase():
    """Get Supabase client with service role key for admin operations."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY, options=ClientOptions(schema="kvota"))


@dataclass
class BrandSupplierAssignment:
    """
    Represents a brand-supplier assignment record.

    Maps a brand to its supplier within an organization.
    One brand can have multiple suppliers, with one marked as primary.
    """
    id: str
    organization_id: str
    brand: str
    supplier_id: str
    is_primary: bool
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    # Optional: joined supplier data
    supplier_name: Optional[str] = None
    supplier_code: Optional[str] = None
    supplier_country: Optional[str] = None


def _parse_assignment(data: dict) -> BrandSupplierAssignment:
    """Parse database row into BrandSupplierAssignment object."""
    # Handle is_primary: could be True, False, or None
    is_primary_value = data.get("is_primary")
    if is_primary_value is None:
        is_primary_value = False

    return BrandSupplierAssignment(
        id=data["id"],
        organization_id=data["organization_id"],
        brand=data["brand"],
        supplier_id=data["supplier_id"],
        is_primary=is_primary_value,
        notes=data.get("notes"),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        created_by=data.get("created_by"),
        supplier_name=data.get("supplier_name"),
        supplier_code=data.get("supplier_code"),
        supplier_country=data.get("supplier_country"),
    )


def _parse_assignment_with_supplier(data: dict) -> BrandSupplierAssignment:
    """Parse database row with joined supplier data."""
    assignment = _parse_assignment(data)

    # Handle joined supplier data
    if "suppliers" in data and data["suppliers"]:
        supplier = data["suppliers"]
        assignment.supplier_name = supplier.get("name")
        assignment.supplier_code = supplier.get("supplier_code")
        assignment.supplier_country = supplier.get("country")

    return assignment


# =============================================================================
# CREATE Operations
# =============================================================================

def create_brand_supplier_assignment(
    organization_id: str,
    brand: str,
    supplier_id: str,
    *,
    is_primary: bool = False,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[BrandSupplierAssignment]:
    """
    Create a new brand-supplier assignment.

    Args:
        organization_id: Organization UUID
        brand: Brand name to assign
        supplier_id: Supplier UUID
        is_primary: Whether this is the primary supplier for the brand
        notes: Optional notes about this assignment
        created_by: User UUID who is creating this assignment

    Returns:
        BrandSupplierAssignment object if successful, None if assignment already exists

    Example:
        assignment = create_brand_supplier_assignment(
            organization_id="org-uuid",
            brand="BOSCH",
            supplier_id="supplier-uuid",
            is_primary=True,
            created_by="admin-uuid"
        )
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments").insert({
            "organization_id": organization_id,
            "brand": brand,
            "supplier_id": supplier_id,
            "is_primary": is_primary,
            "notes": notes,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation (brand-supplier already assigned)
        if "unique_brand_supplier_per_org" in str(e) or "duplicate key" in str(e).lower():
            return None
        raise


def bulk_create_brand_supplier_assignments(
    organization_id: str,
    assignments: List[Dict[str, Any]],
    created_by: Optional[str] = None,
) -> List[BrandSupplierAssignment]:
    """
    Create multiple brand-supplier assignments at once.

    Args:
        organization_id: Organization UUID
        assignments: List of dicts with {"brand": "...", "supplier_id": "...", "is_primary": bool}
        created_by: User UUID

    Returns:
        List of successfully created BrandSupplierAssignment objects

    Example:
        created = bulk_create_brand_supplier_assignments(
            organization_id="org-uuid",
            assignments=[
                {"brand": "BOSCH", "supplier_id": "supplier-1", "is_primary": True},
                {"brand": "SIEMENS", "supplier_id": "supplier-2", "is_primary": False},
            ],
            created_by="admin-uuid"
        )
    """
    created = []
    for assignment in assignments:
        result = create_brand_supplier_assignment(
            organization_id=organization_id,
            brand=assignment["brand"],
            supplier_id=assignment["supplier_id"],
            is_primary=assignment.get("is_primary", False),
            notes=assignment.get("notes"),
            created_by=created_by,
        )
        if result:
            created.append(result)
    return created


# =============================================================================
# READ Operations
# =============================================================================

def get_brand_supplier_assignment(assignment_id: str) -> Optional[BrandSupplierAssignment]:
    """
    Get a single brand-supplier assignment by ID.

    Args:
        assignment_id: UUID of the assignment

    Returns:
        BrandSupplierAssignment if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("*, suppliers(name, supplier_code, country)")\
            .eq("id", assignment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment_with_supplier(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting brand-supplier assignment: {e}")
        return None


def get_assignments_for_brand(
    organization_id: str,
    brand: str,
) -> List[BrandSupplierAssignment]:
    """
    Get all supplier assignments for a specific brand.

    Args:
        organization_id: Organization UUID
        brand: Brand name

    Returns:
        List of BrandSupplierAssignment records (primary first, then by supplier name)

    Example:
        suppliers = get_assignments_for_brand("org-uuid", "BOSCH")
        for s in suppliers:
            print(f"{s.supplier_name} - Primary: {s.is_primary}")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("*, suppliers(name, supplier_code, country)")\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .order("is_primary", desc=True)\
            .execute()

        return [_parse_assignment_with_supplier(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting assignments for brand: {e}")
        return []


def get_primary_supplier_for_brand(
    organization_id: str,
    brand: str,
) -> Optional[BrandSupplierAssignment]:
    """
    Get the primary supplier for a brand.

    Args:
        organization_id: Organization UUID
        brand: Brand name

    Returns:
        BrandSupplierAssignment if a primary supplier exists, None otherwise

    Example:
        primary = get_primary_supplier_for_brand("org-uuid", "BOSCH")
        if primary:
            print(f"Primary supplier for BOSCH: {primary.supplier_name}")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("*, suppliers(name, supplier_code, country)")\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .eq("is_primary", True)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment_with_supplier(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting primary supplier for brand: {e}")
        return None


def get_assignments_for_supplier(
    supplier_id: str,
) -> List[BrandSupplierAssignment]:
    """
    Get all brand assignments for a specific supplier.

    Args:
        supplier_id: Supplier UUID

    Returns:
        List of BrandSupplierAssignment records

    Example:
        brands = get_assignments_for_supplier("supplier-uuid")
        for b in brands:
            print(f"{b.brand} - Primary: {b.is_primary}")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("*")\
            .eq("supplier_id", supplier_id)\
            .order("brand")\
            .execute()

        return [_parse_assignment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting assignments for supplier: {e}")
        return []


def get_all_brand_supplier_assignments(
    organization_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> List[BrandSupplierAssignment]:
    """
    Get all brand-supplier assignments for an organization.

    Args:
        organization_id: Organization UUID
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of BrandSupplierAssignment records
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("*, suppliers(name, supplier_code, country)")\
            .eq("organization_id", organization_id)\
            .order("brand")\
            .order("is_primary", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()

        return [_parse_assignment_with_supplier(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all brand-supplier assignments: {e}")
        return []


def count_brand_supplier_assignments(
    organization_id: str,
    *,
    brand: Optional[str] = None,
    supplier_id: Optional[str] = None,
) -> int:
    """
    Count brand-supplier assignments.

    Args:
        organization_id: Organization UUID
        brand: Optional brand filter
        supplier_id: Optional supplier filter

    Returns:
        Number of assignments
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("brand_supplier_assignments")\
            .select("id", count="exact")\
            .eq("organization_id", organization_id)

        if brand:
            query = query.ilike("brand", brand)
        if supplier_id:
            query = query.eq("supplier_id", supplier_id)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting brand-supplier assignments: {e}")
        return 0


def get_unique_assigned_brands(organization_id: str) -> List[str]:
    """
    Get all unique brand names that have been assigned to suppliers.

    Args:
        organization_id: Organization UUID

    Returns:
        Sorted list of unique brand names
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("brand")\
            .eq("organization_id", organization_id)\
            .execute()

        if result.data:
            brands = set(row["brand"] for row in result.data)
            return sorted(list(brands))
        return []

    except Exception as e:
        print(f"Error getting unique assigned brands: {e}")
        return []


def brand_has_supplier(organization_id: str, brand: str) -> bool:
    """
    Check if a brand has any supplier assigned.

    Args:
        organization_id: Organization UUID
        brand: Brand name

    Returns:
        True if brand has at least one supplier, False otherwise
    """
    return count_brand_supplier_assignments(organization_id, brand=brand) > 0


def brand_has_primary_supplier(organization_id: str, brand: str) -> bool:
    """
    Check if a brand has a primary supplier assigned.

    Args:
        organization_id: Organization UUID
        brand: Brand name

    Returns:
        True if brand has a primary supplier, False otherwise
    """
    return get_primary_supplier_for_brand(organization_id, brand) is not None


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_brand_supplier_assignment(
    assignment_id: str,
    *,
    is_primary: Optional[bool] = None,
    notes: Optional[str] = None,
) -> Optional[BrandSupplierAssignment]:
    """
    Update a brand-supplier assignment.

    Args:
        assignment_id: UUID of the assignment to update
        is_primary: New primary status
        notes: New notes

    Returns:
        Updated BrandSupplierAssignment if successful, None otherwise

    Note: Setting is_primary=True will automatically unset other primaries for the same brand
          (via database trigger ensure_single_primary_brand_supplier)
    """
    try:
        supabase = _get_supabase()

        update_data = {}
        if is_primary is not None:
            update_data["is_primary"] = is_primary
        if notes is not None:
            update_data["notes"] = notes

        if not update_data:
            return get_brand_supplier_assignment(assignment_id)

        result = supabase.table("brand_supplier_assignments")\
            .update(update_data)\
            .eq("id", assignment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating brand-supplier assignment: {e}")
        return None


def set_primary_supplier_for_brand(
    organization_id: str,
    brand: str,
    supplier_id: str,
) -> Optional[BrandSupplierAssignment]:
    """
    Set a supplier as the primary supplier for a brand.

    Args:
        organization_id: Organization UUID
        brand: Brand name
        supplier_id: Supplier UUID to set as primary

    Returns:
        Updated BrandSupplierAssignment if successful, None otherwise

    Note: This will automatically unset any existing primary for the brand
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .update({"is_primary": True})\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .eq("supplier_id", supplier_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error setting primary supplier: {e}")
        return None


def unset_primary_supplier_for_brand(
    organization_id: str,
    brand: str,
) -> bool:
    """
    Unset the primary supplier for a brand (remove primary flag from all suppliers).

    Args:
        organization_id: Organization UUID
        brand: Brand name

    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .update({"is_primary": False})\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .eq("is_primary", True)\
            .execute()

        return True

    except Exception as e:
        print(f"Error unsetting primary supplier: {e}")
        return False


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_brand_supplier_assignment(assignment_id: str) -> bool:
    """
    Delete a brand-supplier assignment by ID.

    Args:
        assignment_id: UUID of the assignment to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .delete()\
            .eq("id", assignment_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting brand-supplier assignment: {e}")
        return False


def delete_brand_supplier_assignment_by_brand_supplier(
    organization_id: str,
    brand: str,
    supplier_id: str,
) -> bool:
    """
    Delete a specific brand-supplier assignment.

    Args:
        organization_id: Organization UUID
        brand: Brand name
        supplier_id: Supplier UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .delete()\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .eq("supplier_id", supplier_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting brand-supplier assignment: {e}")
        return False


def delete_all_assignments_for_brand(
    organization_id: str,
    brand: str,
) -> int:
    """
    Delete all supplier assignments for a brand.

    Args:
        organization_id: Organization UUID
        brand: Brand name

    Returns:
        Number of assignments deleted
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .delete()\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .execute()

        return len(result.data) if result.data else 0

    except Exception as e:
        print(f"Error deleting all assignments for brand: {e}")
        return 0


def delete_all_assignments_for_supplier(supplier_id: str) -> int:
    """
    Delete all brand assignments for a supplier.

    Useful when removing a supplier.

    Args:
        supplier_id: Supplier UUID

    Returns:
        Number of assignments deleted
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .delete()\
            .eq("supplier_id", supplier_id)\
            .execute()

        return len(result.data) if result.data else 0

    except Exception as e:
        print(f"Error deleting all assignments for supplier: {e}")
        return 0


# =============================================================================
# UTILITY Functions
# =============================================================================

def get_brand_supplier_mapping(organization_id: str) -> Dict[str, str]:
    """
    Get a dictionary mapping brand names to primary supplier IDs.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict mapping brand (lowercase) to supplier_id (primary only)

    Example:
        mapping = get_brand_supplier_mapping("org-uuid")
        supplier_id = mapping.get("bosch")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("brand, supplier_id")\
            .eq("organization_id", organization_id)\
            .eq("is_primary", True)\
            .execute()

        mapping = {}
        if result.data:
            for row in result.data:
                mapping[row["brand"].lower()] = row["supplier_id"]
        return mapping

    except Exception as e:
        print(f"Error getting brand-supplier mapping: {e}")
        return {}


def get_suppliers_count_by_brand(organization_id: str) -> Dict[str, int]:
    """
    Get count of suppliers for each brand.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict mapping brand name to count of assigned suppliers
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("brand")\
            .eq("organization_id", organization_id)\
            .execute()

        counts: Dict[str, int] = {}
        if result.data:
            for row in result.data:
                brand = row["brand"]
                counts[brand] = counts.get(brand, 0) + 1
        return counts

    except Exception as e:
        print(f"Error getting suppliers count by brand: {e}")
        return {}


def get_brands_without_supplier(
    organization_id: str,
    all_brands: List[str],
) -> List[str]:
    """
    Find brands from a list that have no supplier assigned.

    Args:
        organization_id: Organization UUID
        all_brands: List of brand names to check

    Returns:
        List of brands without any supplier assignment

    Example:
        quote_brands = ["BOSCH", "SIEMENS", "ABB"]
        unassigned = get_brands_without_supplier("org-uuid", quote_brands)
    """
    assigned = set(b.lower() for b in get_unique_assigned_brands(organization_id))
    return [b for b in all_brands if b.lower() not in assigned]


def get_brands_without_primary_supplier(
    organization_id: str,
    all_brands: List[str],
) -> List[str]:
    """
    Find brands from a list that have no primary supplier assigned.

    Args:
        organization_id: Organization UUID
        all_brands: List of brand names to check

    Returns:
        List of brands without a primary supplier
    """
    primary_mapping = get_brand_supplier_mapping(organization_id)
    return [b for b in all_brands if b.lower() not in primary_mapping]


def get_brand_supplier_assignment_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get statistics about brand-supplier assignments.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total_assignments: Total number of assignments
        - unique_brands: Number of unique brands with suppliers
        - unique_suppliers: Number of unique suppliers assigned
        - brands_with_primary: Number of brands with a primary supplier
        - brands_with_multiple: Number of brands with multiple suppliers
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_supplier_assignments")\
            .select("brand, supplier_id, is_primary")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return {
                "total_assignments": 0,
                "unique_brands": 0,
                "unique_suppliers": 0,
                "brands_with_primary": 0,
                "brands_with_multiple": 0,
            }

        total = len(result.data)
        brands = set()
        suppliers = set()
        brands_with_primary = set()
        brand_counts: Dict[str, int] = {}

        for row in result.data:
            brand = row["brand"]
            brands.add(brand)
            suppliers.add(row["supplier_id"])
            if row.get("is_primary"):
                brands_with_primary.add(brand)
            brand_counts[brand] = brand_counts.get(brand, 0) + 1

        brands_with_multiple = sum(1 for count in brand_counts.values() if count > 1)

        return {
            "total_assignments": total,
            "unique_brands": len(brands),
            "unique_suppliers": len(suppliers),
            "brands_with_primary": len(brands_with_primary),
            "brands_with_multiple": brands_with_multiple,
        }

    except Exception as e:
        print(f"Error getting brand-supplier assignment stats: {e}")
        return {
            "total_assignments": 0,
            "unique_brands": 0,
            "unique_suppliers": 0,
            "brands_with_primary": 0,
            "brands_with_multiple": 0,
        }


def format_brand_supplier_for_display(assignment: BrandSupplierAssignment) -> str:
    """
    Format a brand-supplier assignment for display.

    Args:
        assignment: BrandSupplierAssignment object

    Returns:
        Display string like "BOSCH -> CMT - China Manufacturing [PRIMARY]"
    """
    supplier_info = assignment.supplier_code or assignment.supplier_id[:8]
    if assignment.supplier_name:
        supplier_info = f"{supplier_info} - {assignment.supplier_name}"

    primary_tag = " [PRIMARY]" if assignment.is_primary else ""

    return f"{assignment.brand} -> {supplier_info}{primary_tag}"


def get_suppliers_for_brand_dropdown(
    organization_id: str,
    brand: str,
) -> List[Dict[str, str]]:
    """
    Get suppliers for a brand formatted for dropdown.

    Args:
        organization_id: Organization UUID
        brand: Brand name

    Returns:
        List of dicts with 'value' (supplier_id) and 'label' for dropdown options
    """
    assignments = get_assignments_for_brand(organization_id, brand)

    options = []
    for a in assignments:
        label = a.supplier_code or a.supplier_id[:8]
        if a.supplier_name:
            label = f"{label} - {a.supplier_name}"
        if a.supplier_country:
            label = f"{label} ({a.supplier_country})"
        if a.is_primary:
            label = f"{label} [PRIMARY]"

        options.append({
            "value": a.supplier_id,
            "label": label,
        })

    return options
