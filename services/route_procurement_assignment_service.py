"""
Route Procurement Group Assignment Service - CRUD operations for route_procurement_group_assignments table

This module provides functions for managing sales-group-to-procurement-user assignments:
- Create/Update/Delete group assignments
- Query assignments by organization, group, or user
- Get procurement user for a given sales group
- Get full group->user mapping for an organization

Based on migration 204_create_route_procurement_group_assignments.sql.

The routing cascade is:
1. Sales Group (this table) - highest priority
2. Brand (brand_assignments table) - fallback
3. Manual override (future)
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
    """Get Supabase client with service role key for admin operations."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY, options=ClientOptions(schema="kvota"))


@dataclass
class ProcurementGroupAssignment:
    """
    Represents a sales-group-to-procurement-user assignment record.

    Maps a sales group to its assigned procurement user within an organization.
    When a quote is created by a sales manager belonging to this sales group,
    ALL items in the quote are routed to the assigned procurement user.
    """
    id: str
    organization_id: str
    sales_group_id: str
    user_id: str
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None

    # Optional: joined data
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    sales_group_name: Optional[str] = None


def _parse_assignment(data: dict) -> ProcurementGroupAssignment:
    """Parse database row into ProcurementGroupAssignment object."""
    return ProcurementGroupAssignment(
        id=data["id"],
        organization_id=data["organization_id"],
        sales_group_id=data["sales_group_id"],
        user_id=data["user_id"],
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        created_by=data.get("created_by"),
    )


# =============================================================================
# CREATE Operations
# =============================================================================

def create_assignment(
    organization_id: str,
    sales_group_id: str,
    user_id: str,
    created_by: Optional[str] = None,
) -> Optional[ProcurementGroupAssignment]:
    """
    Create a new sales-group-to-procurement-user assignment.

    Args:
        organization_id: Organization UUID
        sales_group_id: Sales group UUID
        user_id: Procurement user UUID
        created_by: Admin user UUID who is creating this assignment

    Returns:
        ProcurementGroupAssignment if successful, None if already exists
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments").insert({
            "organization_id": organization_id,
            "sales_group_id": sales_group_id,
            "user_id": user_id,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        if "route_procurement_group_unique" in str(e) or "duplicate key" in str(e).lower():
            return None
        raise


def upsert_assignment(
    organization_id: str,
    sales_group_id: str,
    user_id: str,
    created_by: Optional[str] = None,
) -> Optional[ProcurementGroupAssignment]:
    """
    Create or update a sales-group assignment (upsert).

    If the sales group is already assigned in the organization, updates the user.
    Otherwise, creates a new assignment.

    Args:
        organization_id: Organization UUID
        sales_group_id: Sales group UUID
        user_id: Procurement user UUID
        created_by: Admin user UUID

    Returns:
        ProcurementGroupAssignment with updated/created record
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments").upsert(
            {
                "organization_id": organization_id,
                "sales_group_id": sales_group_id,
                "user_id": user_id,
                "created_by": created_by,
            },
            on_conflict="organization_id,sales_group_id"
        ).execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error upserting procurement group assignment: {e}")
        return None


# =============================================================================
# READ Operations
# =============================================================================

def get_assignment(assignment_id: str) -> Optional[ProcurementGroupAssignment]:
    """
    Get a single assignment by ID.

    Args:
        assignment_id: UUID of the assignment

    Returns:
        ProcurementGroupAssignment if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments") \
            .select("*") \
            .eq("id", assignment_id) \
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting procurement group assignment: {e}")
        return None


def get_assignment_by_group(
    organization_id: str,
    sales_group_id: str,
) -> Optional[ProcurementGroupAssignment]:
    """
    Get assignment for a specific sales group in an organization.

    Args:
        organization_id: Organization UUID
        sales_group_id: Sales group UUID

    Returns:
        ProcurementGroupAssignment if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments") \
            .select("*") \
            .eq("organization_id", organization_id) \
            .eq("sales_group_id", sales_group_id) \
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting assignment by group: {e}")
        return None


def get_all_assignments(organization_id: str) -> List[ProcurementGroupAssignment]:
    """
    Get all procurement group assignments for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        List of ProcurementGroupAssignment records
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments") \
            .select("*") \
            .eq("organization_id", organization_id) \
            .order("created_at") \
            .execute()

        return [_parse_assignment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all procurement group assignments: {e}")
        return []


def get_all_with_details(organization_id: str) -> List[Dict]:
    """
    Get all assignments with joined sales group and user details.

    Args:
        organization_id: Organization UUID

    Returns:
        List of dicts with assignment, group name, and user info
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments") \
            .select("*, sales_groups!sales_group_id(name)") \
            .eq("organization_id", organization_id) \
            .order("created_at") \
            .execute()

        assignments = []
        for row in result.data or []:
            group_data = row.get("sales_groups") or {}
            assignments.append({
                "id": row["id"],
                "organization_id": row["organization_id"],
                "sales_group_id": row["sales_group_id"],
                "sales_group_name": group_data.get("name", ""),
                "user_id": row["user_id"],
                "created_at": row.get("created_at"),
                "created_by": row.get("created_by"),
            })

        return assignments

    except Exception as e:
        print(f"Error getting assignments with details: {e}")
        return []


def get_procurement_user_for_group(
    organization_id: str,
    sales_group_id: str,
) -> Optional[str]:
    """
    Get the procurement user ID for a given sales group.

    This is the primary lookup function used in the routing cascade.

    Args:
        organization_id: Organization UUID
        sales_group_id: Sales group UUID

    Returns:
        User ID of the assigned procurement user, or None if no mapping exists
    """
    assignment = get_assignment_by_group(organization_id, sales_group_id)
    return assignment.user_id if assignment else None


def get_group_mapping(organization_id: str) -> Dict[str, str]:
    """
    Get a dictionary mapping sales_group_id -> procurement user_id.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict mapping sales_group_id to user_id
    """
    assignments = get_all_assignments(organization_id)
    return {a.sales_group_id: a.user_id for a in assignments}


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_assignment(
    assignment_id: str,
    user_id: str,
) -> Optional[ProcurementGroupAssignment]:
    """
    Update the assigned procurement user for an assignment.

    Args:
        assignment_id: UUID of the assignment to update
        user_id: New procurement user UUID

    Returns:
        Updated ProcurementGroupAssignment if successful, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments") \
            .update({"user_id": user_id}) \
            .eq("id", assignment_id) \
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating procurement group assignment: {e}")
        return None


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_assignment(assignment_id: str) -> bool:
    """
    Delete an assignment by ID.

    Args:
        assignment_id: UUID of the assignment to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_procurement_group_assignments") \
            .delete() \
            .eq("id", assignment_id) \
            .execute()

        return result.data is not None and len(result.data) > 0

    except Exception as e:
        print(f"Error deleting procurement group assignment: {e}")
        return False
