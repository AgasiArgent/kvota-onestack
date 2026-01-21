"""
Brand Assignment Service - CRUD operations for brand_assignments table

This module provides functions for managing brand-to-procurement-manager assignments:
- Create/Update/Delete brand assignments
- Query assignments by organization, brand, or user
- Get all unique brands in an organization
- Utility functions for brand management

Based on app_spec.xml brand_assignments table definition.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
import os
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
class BrandAssignment:
    """
    Represents a brand assignment record.

    Maps a brand to its assigned procurement manager within an organization.
    """
    id: str
    organization_id: str
    brand: str
    user_id: str
    created_at: datetime
    created_by: Optional[str] = None

    # Optional: joined user data
    user_email: Optional[str] = None
    user_name: Optional[str] = None


def _parse_assignment(data: dict) -> BrandAssignment:
    """Parse database row into BrandAssignment object."""
    return BrandAssignment(
        id=data["id"],
        organization_id=data["organization_id"],
        brand=data["brand"],
        user_id=data["user_id"],
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        created_by=data.get("created_by"),
        user_email=data.get("user_email"),
        user_name=data.get("user_name"),
    )


# =============================================================================
# CREATE Operations
# =============================================================================

def create_brand_assignment(
    organization_id: str,
    brand: str,
    user_id: str,
    created_by: str
) -> Optional[BrandAssignment]:
    """
    Create a new brand assignment.

    Args:
        organization_id: Organization UUID
        brand: Brand name to assign
        user_id: Procurement manager's user UUID
        created_by: Admin user UUID who is creating this assignment

    Returns:
        BrandAssignment object if successful, None if assignment already exists

    Example:
        assignment = create_brand_assignment(
            organization_id="org-uuid",
            brand="BOSCH",
            user_id="procurement-user-uuid",
            created_by="admin-uuid"
        )
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments").insert({
            "organization_id": organization_id,
            "brand": brand,
            "user_id": user_id,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation (brand already assigned)
        if "unique_brand_per_org" in str(e) or "duplicate key" in str(e).lower():
            return None
        raise


def upsert_brand_assignment(
    organization_id: str,
    brand: str,
    user_id: str,
    created_by: str
) -> Optional[BrandAssignment]:
    """
    Create or update a brand assignment (upsert).

    If the brand is already assigned in the organization, updates the assigned user.
    Otherwise, creates a new assignment.

    Args:
        organization_id: Organization UUID
        brand: Brand name to assign
        user_id: New procurement manager's user UUID
        created_by: Admin user UUID

    Returns:
        BrandAssignment object with updated/created record

    Example:
        # Will create if doesn't exist, or update user_id if exists
        assignment = upsert_brand_assignment(
            organization_id="org-uuid",
            brand="SIEMENS",
            user_id="new-procurement-user-uuid",
            created_by="admin-uuid"
        )
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments").upsert(
            {
                "organization_id": organization_id,
                "brand": brand,
                "user_id": user_id,
                "created_by": created_by,
            },
            on_conflict="organization_id,brand"
        ).execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error upserting brand assignment: {e}")
        return None


def bulk_create_assignments(
    organization_id: str,
    assignments: List[Dict[str, str]],
    created_by: str
) -> List[BrandAssignment]:
    """
    Create multiple brand assignments at once.

    Args:
        organization_id: Organization UUID
        assignments: List of dicts with {"brand": "...", "user_id": "..."}
        created_by: Admin user UUID

    Returns:
        List of successfully created BrandAssignment objects

    Example:
        created = bulk_create_assignments(
            organization_id="org-uuid",
            assignments=[
                {"brand": "BOSCH", "user_id": "user-1"},
                {"brand": "SIEMENS", "user_id": "user-2"},
            ],
            created_by="admin-uuid"
        )
    """
    created = []
    for assignment in assignments:
        result = create_brand_assignment(
            organization_id=organization_id,
            brand=assignment["brand"],
            user_id=assignment["user_id"],
            created_by=created_by
        )
        if result:
            created.append(result)
    return created


# =============================================================================
# READ Operations
# =============================================================================

def get_brand_assignment(assignment_id: str) -> Optional[BrandAssignment]:
    """
    Get a single brand assignment by ID.

    Args:
        assignment_id: UUID of the assignment

    Returns:
        BrandAssignment if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments")\
            .select("*")\
            .eq("id", assignment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting brand assignment: {e}")
        return None


def get_brand_assignment_by_brand(
    organization_id: str,
    brand: str
) -> Optional[BrandAssignment]:
    """
    Get brand assignment for a specific brand in an organization.

    Args:
        organization_id: Organization UUID
        brand: Brand name to look up

    Returns:
        BrandAssignment if found, None otherwise

    Example:
        assignment = get_brand_assignment_by_brand("org-uuid", "BOSCH")
        if assignment:
            print(f"BOSCH is managed by {assignment.user_id}")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments")\
            .select("*")\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting brand assignment by brand: {e}")
        return None


def get_all_brand_assignments(organization_id: str) -> List[BrandAssignment]:
    """
    Get all brand assignments for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        List of all BrandAssignment records for the organization

    Example:
        all_assignments = get_all_brand_assignments("org-uuid")
        for a in all_assignments:
            print(f"{a.brand} -> {a.user_id}")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments")\
            .select("*")\
            .eq("organization_id", organization_id)\
            .order("brand")\
            .execute()

        return [_parse_assignment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all brand assignments: {e}")
        return []


def get_user_brand_assignments(
    user_id: str,
    organization_id: Optional[str] = None
) -> List[BrandAssignment]:
    """
    Get all brands assigned to a specific user.

    Args:
        user_id: User UUID
        organization_id: Optional organization UUID to filter by

    Returns:
        List of BrandAssignment records for this user

    Example:
        my_brands = get_user_brand_assignments("user-uuid")
        brand_names = [a.brand for a in my_brands]
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("brand_assignments")\
            .select("*")\
            .eq("user_id", user_id)

        if organization_id:
            query = query.eq("organization_id", organization_id)

        result = query.order("brand").execute()

        return [_parse_assignment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting user brand assignments: {e}")
        return []


def get_assignments_with_user_details(organization_id: str) -> List[Dict]:
    """
    Get all brand assignments with joined user information.

    Useful for admin UI to show brand-manager mappings with names.

    Args:
        organization_id: Organization UUID

    Returns:
        List of dicts with assignment and user details

    Example:
        assignments = get_assignments_with_user_details("org-uuid")
        for a in assignments:
            print(f"{a['brand']} -> {a['user_email']}")
    """
    try:
        supabase = _get_supabase()

        # Get assignments with user info from organization_members
        result = supabase.table("brand_assignments")\
            .select("*, organization_members!inner(user_id, role)")\
            .eq("organization_id", organization_id)\
            .order("brand")\
            .execute()

        assignments = []
        for row in result.data or []:
            assignments.append({
                "id": row["id"],
                "organization_id": row["organization_id"],
                "brand": row["brand"],
                "user_id": row["user_id"],
                "created_at": row["created_at"],
                "created_by": row.get("created_by"),
            })

        return assignments

    except Exception as e:
        print(f"Error getting assignments with user details: {e}")
        return []


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_brand_assignment(
    assignment_id: str,
    user_id: str
) -> Optional[BrandAssignment]:
    """
    Update the assigned user for a brand assignment.

    Args:
        assignment_id: UUID of the assignment to update
        user_id: New procurement manager's user UUID

    Returns:
        Updated BrandAssignment if successful, None otherwise

    Example:
        updated = update_brand_assignment(
            assignment_id="assignment-uuid",
            user_id="new-user-uuid"
        )
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments")\
            .update({"user_id": user_id})\
            .eq("id", assignment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating brand assignment: {e}")
        return None


def reassign_brand(
    organization_id: str,
    brand: str,
    new_user_id: str
) -> Optional[BrandAssignment]:
    """
    Reassign a brand to a different procurement manager.

    Args:
        organization_id: Organization UUID
        brand: Brand name to reassign
        new_user_id: New procurement manager's user UUID

    Returns:
        Updated BrandAssignment if found and updated, None otherwise

    Example:
        result = reassign_brand("org-uuid", "BOSCH", "new-user-uuid")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments")\
            .update({"user_id": new_user_id})\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error reassigning brand: {e}")
        return None


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_brand_assignment(assignment_id: str) -> bool:
    """
    Delete a brand assignment by ID.

    Args:
        assignment_id: UUID of the assignment to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments")\
            .delete()\
            .eq("id", assignment_id)\
            .execute()

        return result.data is not None and len(result.data) > 0

    except Exception as e:
        print(f"Error deleting brand assignment: {e}")
        return False


def delete_brand_assignment_by_brand(
    organization_id: str,
    brand: str
) -> bool:
    """
    Delete a brand assignment by brand name.

    Args:
        organization_id: Organization UUID
        brand: Brand name to unassign

    Returns:
        True if deleted successfully, False otherwise

    Example:
        if delete_brand_assignment_by_brand("org-uuid", "BOSCH"):
            print("BOSCH is now unassigned")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("brand_assignments")\
            .delete()\
            .eq("organization_id", organization_id)\
            .ilike("brand", brand)\
            .execute()

        return result.data is not None and len(result.data) > 0

    except Exception as e:
        print(f"Error deleting brand assignment by brand: {e}")
        return False


def delete_all_user_assignments(
    user_id: str,
    organization_id: Optional[str] = None
) -> int:
    """
    Delete all brand assignments for a user.

    Useful when removing a user from procurement role.

    Args:
        user_id: User UUID
        organization_id: Optional organization to limit deletion scope

    Returns:
        Number of assignments deleted
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("brand_assignments")\
            .delete()\
            .eq("user_id", user_id)

        if organization_id:
            query = query.eq("organization_id", organization_id)

        result = query.execute()

        return len(result.data) if result.data else 0

    except Exception as e:
        print(f"Error deleting all user assignments: {e}")
        return 0


# =============================================================================
# Convenience Functions (Features #31, #32)
# =============================================================================

def get_procurement_manager(organization_id: str, brand: str) -> Optional[str]:
    """
    Get the procurement manager user ID for a specific brand.

    Feature #31: Simple function to get manager ID by brand name.

    Args:
        organization_id: Organization UUID
        brand: Brand name to look up (case-insensitive)

    Returns:
        User ID of the assigned procurement manager, or None if not assigned

    Example:
        manager_id = get_procurement_manager("org-uuid", "BOSCH")
        if manager_id:
            print(f"BOSCH is managed by user {manager_id}")
        else:
            print("BOSCH has no assigned manager")
    """
    assignment = get_brand_assignment_by_brand(organization_id, brand)
    return assignment.user_id if assignment else None


def get_assigned_brands(user_id: str, organization_id: str) -> List[str]:
    """
    Get list of brand names assigned to a user in an organization.

    Feature #32: Simple function to get just brand names (not full objects).

    Args:
        user_id: User UUID
        organization_id: Organization UUID

    Returns:
        Sorted list of brand names assigned to this user

    Example:
        my_brands = get_assigned_brands("user-uuid", "org-uuid")
        # Returns: ["ABB", "BOSCH", "SIEMENS"]
    """
    assignments = get_user_brand_assignments(user_id, organization_id)
    return sorted([a.brand for a in assignments])


# =============================================================================
# Utility Functions
# =============================================================================

def get_unique_brands_in_org(organization_id: str) -> List[str]:
    """
    Get all unique brand names that have been assigned in an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Sorted list of unique brand names
    """
    assignments = get_all_brand_assignments(organization_id)
    return sorted(set(a.brand for a in assignments))


def get_unassigned_brands(
    organization_id: str,
    all_brands: List[str]
) -> List[str]:
    """
    Find brands from a list that are not yet assigned to any manager.

    Args:
        organization_id: Organization UUID
        all_brands: List of brand names to check

    Returns:
        List of brands that have no assignment

    Example:
        # Check which brands from quote items need assignment
        quote_brands = ["BOSCH", "SIEMENS", "ABB"]
        unassigned = get_unassigned_brands("org-uuid", quote_brands)
        # Returns brands that don't have a procurement manager
    """
    assigned = set(b.lower() for b in get_unique_brands_in_org(organization_id))
    return [b for b in all_brands if b.lower() not in assigned]


def get_brand_manager_mapping(organization_id: str) -> Dict[str, str]:
    """
    Get a dictionary mapping brand names to manager user IDs.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict mapping brand (lowercase) to user_id

    Example:
        mapping = get_brand_manager_mapping("org-uuid")
        manager_id = mapping.get("bosch")
    """
    assignments = get_all_brand_assignments(organization_id)
    return {a.brand.lower(): a.user_id for a in assignments}


def count_assignments_by_user(organization_id: str) -> Dict[str, int]:
    """
    Count how many brands each user manages in an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict mapping user_id to count of assigned brands

    Example:
        counts = count_assignments_by_user("org-uuid")
        for user_id, count in counts.items():
            print(f"User {user_id} manages {count} brands")
    """
    assignments = get_all_brand_assignments(organization_id)
    counts: Dict[str, int] = {}
    for a in assignments:
        counts[a.user_id] = counts.get(a.user_id, 0) + 1
    return counts


def is_brand_assigned(organization_id: str, brand: str) -> bool:
    """
    Check if a brand has been assigned to any manager.

    Args:
        organization_id: Organization UUID
        brand: Brand name to check

    Returns:
        True if brand is assigned, False otherwise
    """
    return get_brand_assignment_by_brand(organization_id, brand) is not None
