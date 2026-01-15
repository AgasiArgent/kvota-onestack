"""
Role Service - Functions for managing user roles in organizations

This module provides functions to:
- Get user roles in an organization
- Check if user has a specific role
- Assign/remove roles (admin operations)

Based on database tables:
- roles: Reference table with role definitions
- user_roles: Junction table linking users to roles per organization
"""

from typing import List, Optional
from dataclasses import dataclass
from uuid import UUID
from .database import get_supabase


@dataclass
class Role:
    """Role data class"""
    id: UUID
    code: str
    name: str
    description: Optional[str] = None


@dataclass
class UserRole:
    """User role assignment data class"""
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: Role
    created_at: str
    created_by: Optional[UUID] = None


def get_user_roles(user_id: str | UUID, organization_id: str | UUID) -> List[Role]:
    """
    Get all roles for a user in a specific organization.

    Args:
        user_id: User's UUID
        organization_id: Organization's UUID

    Returns:
        List of Role objects assigned to the user in this organization

    Example:
        >>> roles = get_user_roles("user-uuid", "org-uuid")
        >>> for role in roles:
        ...     print(f"{role.code}: {role.name}")
    """
    supabase = get_supabase()

    # Query user_roles joined with roles to get role details
    response = supabase.table("user_roles") \
        .select("id, user_id, organization_id, created_at, created_by, roles(id, code, name, description)") \
        .eq("user_id", str(user_id)) \
        .eq("organization_id", str(organization_id)) \
        .execute()

    roles = []
    for item in response.data:
        role_data = item.get("roles")
        if role_data:
            roles.append(Role(
                id=UUID(role_data["id"]),
                code=role_data["code"],
                name=role_data["name"],
                description=role_data.get("description")
            ))

    return roles


def get_user_role_codes(user_id: str | UUID, organization_id: str | UUID) -> List[str]:
    """
    Get role codes for a user in a specific organization.

    This is a convenience function that returns just the role codes
    rather than full Role objects.

    Args:
        user_id: User's UUID
        organization_id: Organization's UUID

    Returns:
        List of role code strings (e.g., ['sales', 'admin'])
    """
    roles = get_user_roles(user_id, organization_id)
    return [role.code for role in roles]


def has_role(user_id: str | UUID, organization_id: str | UUID, role_code: str) -> bool:
    """
    Check if a user has a specific role in an organization.

    This is the primary function for role-based access control checks.

    Args:
        user_id: User's UUID
        organization_id: Organization's UUID
        role_code: Role code to check for (e.g., 'admin', 'sales', 'procurement')

    Returns:
        True if user has the specified role, False otherwise

    Example:
        >>> if has_role(user_id, org_id, 'admin'):
        ...     # User is admin, allow operation
        ...     pass
    """
    user_roles = get_user_role_codes(user_id, organization_id)
    return role_code in user_roles


def has_any_role(user_id: str | UUID, organization_id: str | UUID, role_codes: List[str]) -> bool:
    """
    Check if a user has any of the specified roles in an organization.

    Useful for checking if user has permission for an action that
    can be performed by multiple roles.

    Args:
        user_id: User's UUID
        organization_id: Organization's UUID
        role_codes: List of role codes to check for

    Returns:
        True if user has at least one of the specified roles, False otherwise

    Example:
        >>> # Check if user can modify quotes (either sales or admin)
        >>> if has_any_role(user_id, org_id, ['sales', 'admin']):
        ...     # User can modify quotes
        ...     pass
    """
    user_roles = get_user_role_codes(user_id, organization_id)
    return any(code in user_roles for code in role_codes)


def has_all_roles(user_id: str | UUID, organization_id: str | UUID, role_codes: List[str]) -> bool:
    """
    Check if a user has ALL of the specified roles in an organization.

    Useful for checking if user has a combination of required permissions.

    Args:
        user_id: User's UUID
        organization_id: Organization's UUID
        role_codes: List of role codes that user must have all of

    Returns:
        True if user has all of the specified roles, False otherwise

    Example:
        >>> # Check if user is both admin and finance (rare but possible)
        >>> if has_all_roles(user_id, org_id, ['admin', 'finance']):
        ...     # User has both roles
        ...     pass
    """
    user_roles = get_user_role_codes(user_id, organization_id)
    return all(code in user_roles for code in role_codes)


def assign_role(
    user_id: str | UUID,
    organization_id: str | UUID,
    role_code: str,
    assigned_by: str | UUID
) -> Optional[UserRole]:
    """
    Assign a role to a user in an organization.

    This function is an admin operation that creates a new user_role record.
    If the user already has this role, returns None without creating a duplicate.

    Args:
        user_id: User's UUID to assign role to
        organization_id: Organization's UUID
        role_code: Role code to assign (e.g., 'sales', 'admin')
        assigned_by: UUID of the user performing the assignment

    Returns:
        UserRole object if role was assigned, None if user already had role
        or if role_code is invalid

    Raises:
        Exception: If there's a database error

    Example:
        >>> # Assign sales role to a user
        >>> result = assign_role(user_id, org_id, 'sales', admin_user_id)
        >>> if result:
        ...     print(f"Role assigned: {result.role.code}")
        ... else:
        ...     print("User already has this role or role is invalid")
    """
    # Check if user already has this role
    if has_role(user_id, organization_id, role_code):
        return None

    # Get the role ID
    role = get_role_by_code(role_code)
    if not role:
        return None

    supabase = get_supabase()

    # Insert new user_role record
    response = supabase.table("user_roles").insert({
        "user_id": str(user_id),
        "organization_id": str(organization_id),
        "role_id": str(role.id),
        "created_by": str(assigned_by)
    }).execute()

    if response.data and len(response.data) > 0:
        item = response.data[0]
        return UserRole(
            id=UUID(item["id"]),
            user_id=UUID(item["user_id"]),
            organization_id=UUID(item["organization_id"]),
            role=role,
            created_at=item["created_at"],
            created_by=UUID(item["created_by"]) if item.get("created_by") else None
        )

    return None


def get_all_roles() -> List[Role]:
    """
    Get all available roles from the roles reference table.

    Returns:
        List of all Role objects defined in the system
    """
    supabase = get_supabase()

    response = supabase.table("roles") \
        .select("id, code, name, description") \
        .order("code") \
        .execute()

    return [
        Role(
            id=UUID(item["id"]),
            code=item["code"],
            name=item["name"],
            description=item.get("description")
        )
        for item in response.data
    ]


def get_role_by_code(code: str) -> Optional[Role]:
    """
    Get a single role by its code.

    Args:
        code: Role code (e.g., 'sales', 'admin')

    Returns:
        Role object if found, None otherwise
    """
    supabase = get_supabase()

    response = supabase.table("roles") \
        .select("id, code, name, description") \
        .eq("code", code) \
        .limit(1) \
        .execute()

    if response.data:
        item = response.data[0]
        return Role(
            id=UUID(item["id"]),
            code=item["code"],
            name=item["name"],
            description=item.get("description")
        )

    return None


def get_users_by_role(organization_id: str | UUID, role_code: str) -> List[dict]:
    """
    Get all users with a specific role in an organization.

    Args:
        organization_id: Organization's UUID
        role_code: Role code to filter by

    Returns:
        List of dicts with user_id and role assignment info
    """
    supabase = get_supabase()

    # First get the role ID
    role = get_role_by_code(role_code)
    if not role:
        return []

    # Query user_roles for this role
    response = supabase.table("user_roles") \
        .select("user_id, created_at, created_by") \
        .eq("organization_id", str(organization_id)) \
        .eq("role_id", str(role.id)) \
        .execute()

    return response.data


def get_users_by_any_role(organization_id: str | UUID, role_codes: List[str]) -> List[dict]:
    """
    Get all users with any of the specified roles in an organization.

    Args:
        organization_id: Organization's UUID
        role_codes: List of role codes to filter by

    Returns:
        List of dicts with user_id, role_code pairs
    """
    supabase = get_supabase()

    # Get role IDs for the specified codes
    roles_response = supabase.table("roles") \
        .select("id, code") \
        .in_("code", role_codes) \
        .execute()

    role_id_map = {item["id"]: item["code"] for item in roles_response.data}
    role_ids = list(role_id_map.keys())

    if not role_ids:
        return []

    # Query user_roles for these roles
    response = supabase.table("user_roles") \
        .select("user_id, role_id, created_at") \
        .eq("organization_id", str(organization_id)) \
        .in_("role_id", role_ids) \
        .execute()

    # Add role code to each result
    result = []
    for item in response.data:
        item["role_code"] = role_id_map.get(item["role_id"])
        result.append(item)

    return result
