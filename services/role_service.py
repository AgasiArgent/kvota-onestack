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
