"""
Route Logistics Assignment Service - CRUD operations for route_logistics_assignments table

This module provides functions for managing route-to-logistics-manager assignments:
- Create/Update/Delete route assignments
- Match routes to logistics managers using patterns
- Query assignments by organization, user, or route
- Utility functions for route management

Based on migration 027_create_route_logistics_assignments_table.sql (Feature API-009).

Route pattern format: "origin-destination" with optional wildcards (*)
Examples:
- "Китай-*" - All routes from China
- "Турция-Москва" - Specific route Turkey to Moscow
- "*-Санкт-Петербург" - All routes to St. Petersburg
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import re
from supabase import create_client


# Initialize Supabase client with service role for admin operations
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _get_supabase():
    """Get Supabase client with service role key for admin operations."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@dataclass
class RouteLogisticsAssignment:
    """
    Represents a route-to-logistics-manager assignment record.

    Maps a route pattern to a logistics manager within an organization.
    Route patterns support wildcards (*) for flexible matching.
    """
    id: str
    organization_id: str
    route_pattern: str
    user_id: str
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None

    # Optional: parsed route components
    origin: Optional[str] = None
    destination: Optional[str] = None

    # Optional: joined user data
    user_email: Optional[str] = None
    user_name: Optional[str] = None


def _parse_assignment(data: dict) -> RouteLogisticsAssignment:
    """Parse database row into RouteLogisticsAssignment object."""
    assignment = RouteLogisticsAssignment(
        id=data["id"],
        organization_id=data["organization_id"],
        route_pattern=data["route_pattern"],
        user_id=data["user_id"],
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        created_by=data.get("created_by"),
    )

    # Parse route pattern into origin/destination
    if "-" in assignment.route_pattern:
        parts = assignment.route_pattern.split("-", 1)
        assignment.origin = parts[0] if parts[0] != "*" else None
        assignment.destination = parts[1] if len(parts) > 1 and parts[1] != "*" else None

    return assignment


def _parse_assignment_with_user(data: dict) -> RouteLogisticsAssignment:
    """Parse database row with joined user data."""
    assignment = _parse_assignment(data)

    # Handle joined user data from auth.users
    if "users" in data and data["users"]:
        user = data["users"]
        assignment.user_email = user.get("email")
        # auth.users doesn't have name, but raw_user_meta_data might
        if user.get("raw_user_meta_data"):
            assignment.user_name = user["raw_user_meta_data"].get("name") or user["raw_user_meta_data"].get("full_name")

    return assignment


# =============================================================================
# VALIDATION Functions
# =============================================================================

def validate_route_pattern(pattern: str) -> bool:
    """
    Validate a route pattern.

    Args:
        pattern: Route pattern to validate

    Returns:
        True if valid, False otherwise

    Rules:
    - Must contain a hyphen (origin-destination separator)
    - Must not be empty
    - Must contain at least one non-wildcard character
    """
    if not pattern or not pattern.strip():
        return False

    # Must contain a hyphen
    if "-" not in pattern:
        return False

    # Must contain at least one non-wildcard character
    cleaned = pattern.replace("*", "").replace("-", "").strip()
    if not cleaned:
        return False

    return True


def parse_route_pattern(pattern: str) -> Optional[Dict[str, str]]:
    """
    Parse a route pattern into origin and destination components.

    Args:
        pattern: Route pattern string (e.g., "Китай-Москва")

    Returns:
        Dict with 'origin' and 'destination' (None for wildcards), or None if invalid

    Example:
        parse_route_pattern("Китай-*")
        # Returns {'origin': 'Китай', 'destination': None}
    """
    if not validate_route_pattern(pattern):
        return None

    parts = pattern.split("-", 1)
    if len(parts) != 2:
        return None

    origin = parts[0].strip() if parts[0].strip() != "*" else None
    destination = parts[1].strip() if parts[1].strip() != "*" else None

    return {
        "origin": origin,
        "destination": destination,
    }


def build_route_pattern(origin: Optional[str], destination: Optional[str]) -> str:
    """
    Build a route pattern from origin and destination.

    Args:
        origin: Origin country/city (or None for wildcard)
        destination: Destination country/city (or None for wildcard)

    Returns:
        Route pattern string

    Example:
        build_route_pattern("Китай", None)
        # Returns "Китай-*"
    """
    origin_part = origin.strip() if origin else "*"
    dest_part = destination.strip() if destination else "*"
    return f"{origin_part}-{dest_part}"


def normalize_route_pattern(pattern: str) -> str:
    """
    Normalize a route pattern (trim whitespace, ensure proper format).

    Args:
        pattern: Route pattern to normalize

    Returns:
        Normalized pattern
    """
    if "-" not in pattern:
        return pattern.strip()

    parts = pattern.split("-", 1)
    origin = parts[0].strip() or "*"
    destination = parts[1].strip() if len(parts) > 1 else "*"
    destination = destination or "*"

    return f"{origin}-{destination}"


# =============================================================================
# CREATE Operations
# =============================================================================

def create_route_logistics_assignment(
    organization_id: str,
    route_pattern: str,
    user_id: str,
    *,
    created_by: Optional[str] = None,
) -> Optional[RouteLogisticsAssignment]:
    """
    Create a new route-logistics manager assignment.

    Args:
        organization_id: Organization UUID
        route_pattern: Route pattern (e.g., "Китай-*", "Турция-Москва")
        user_id: Logistics manager user UUID
        created_by: User UUID who is creating this assignment

    Returns:
        RouteLogisticsAssignment object if successful, None if assignment already exists or invalid

    Example:
        assignment = create_route_logistics_assignment(
            organization_id="org-uuid",
            route_pattern="Китай-*",
            user_id="logistics-manager-uuid",
            created_by="admin-uuid"
        )
    """
    # Validate and normalize pattern
    normalized_pattern = normalize_route_pattern(route_pattern)
    if not validate_route_pattern(normalized_pattern):
        return None

    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments").insert({
            "organization_id": organization_id,
            "route_pattern": normalized_pattern,
            "user_id": user_id,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation (pattern already assigned)
        if "route_logistics_assignments_unique_pattern" in str(e) or "duplicate key" in str(e).lower():
            return None
        # Handle invalid pattern constraint
        if "route_logistics_assignments_valid_pattern" in str(e):
            return None
        raise


def bulk_create_route_logistics_assignments(
    organization_id: str,
    assignments: List[Dict[str, str]],
    created_by: Optional[str] = None,
) -> List[RouteLogisticsAssignment]:
    """
    Create multiple route-logistics assignments at once.

    Args:
        organization_id: Organization UUID
        assignments: List of dicts with {"route_pattern": "...", "user_id": "..."}
        created_by: User UUID

    Returns:
        List of successfully created RouteLogisticsAssignment objects

    Example:
        created = bulk_create_route_logistics_assignments(
            organization_id="org-uuid",
            assignments=[
                {"route_pattern": "Китай-*", "user_id": "user-1"},
                {"route_pattern": "Турция-Москва", "user_id": "user-2"},
            ],
            created_by="admin-uuid"
        )
    """
    created = []
    for assignment in assignments:
        result = create_route_logistics_assignment(
            organization_id=organization_id,
            route_pattern=assignment["route_pattern"],
            user_id=assignment["user_id"],
            created_by=created_by,
        )
        if result:
            created.append(result)
    return created


# =============================================================================
# READ Operations
# =============================================================================

def get_route_logistics_assignment(assignment_id: str) -> Optional[RouteLogisticsAssignment]:
    """
    Get a single route-logistics assignment by ID.

    Args:
        assignment_id: UUID of the assignment

    Returns:
        RouteLogisticsAssignment if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments")\
            .select("*")\
            .eq("id", assignment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting route-logistics assignment: {e}")
        return None


def get_route_logistics_assignment_by_pattern(
    organization_id: str,
    route_pattern: str,
) -> Optional[RouteLogisticsAssignment]:
    """
    Get a route-logistics assignment by exact pattern match.

    Args:
        organization_id: Organization UUID
        route_pattern: Route pattern to find

    Returns:
        RouteLogisticsAssignment if found, None otherwise
    """
    try:
        supabase = _get_supabase()
        normalized_pattern = normalize_route_pattern(route_pattern)

        result = supabase.table("route_logistics_assignments")\
            .select("*")\
            .eq("organization_id", organization_id)\
            .eq("route_pattern", normalized_pattern)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting assignment by pattern: {e}")
        return None


def get_assignments_for_user(
    organization_id: str,
    user_id: str,
) -> List[RouteLogisticsAssignment]:
    """
    Get all route assignments for a specific logistics manager.

    Args:
        organization_id: Organization UUID
        user_id: Logistics manager user UUID

    Returns:
        List of RouteLogisticsAssignment records

    Example:
        routes = get_assignments_for_user("org-uuid", "user-uuid")
        for r in routes:
            print(f"Route: {r.route_pattern}")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments")\
            .select("*")\
            .eq("organization_id", organization_id)\
            .eq("user_id", user_id)\
            .order("route_pattern")\
            .execute()

        return [_parse_assignment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting assignments for user: {e}")
        return []


def get_all_route_logistics_assignments(
    organization_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> List[RouteLogisticsAssignment]:
    """
    Get all route-logistics assignments for an organization.

    Args:
        organization_id: Organization UUID
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of RouteLogisticsAssignment records
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments")\
            .select("*")\
            .eq("organization_id", organization_id)\
            .order("route_pattern")\
            .range(offset, offset + limit - 1)\
            .execute()

        return [_parse_assignment(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all route-logistics assignments: {e}")
        return []


def count_route_logistics_assignments(
    organization_id: str,
    *,
    user_id: Optional[str] = None,
) -> int:
    """
    Count route-logistics assignments.

    Args:
        organization_id: Organization UUID
        user_id: Optional user filter

    Returns:
        Number of assignments
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("route_logistics_assignments")\
            .select("id", count="exact")\
            .eq("organization_id", organization_id)

        if user_id:
            query = query.eq("user_id", user_id)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting route-logistics assignments: {e}")
        return 0


def get_unique_route_patterns(organization_id: str) -> List[str]:
    """
    Get all unique route patterns for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Sorted list of unique route patterns
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments")\
            .select("route_pattern")\
            .eq("organization_id", organization_id)\
            .execute()

        if result.data:
            patterns = set(row["route_pattern"] for row in result.data)
            return sorted(list(patterns))
        return []

    except Exception as e:
        print(f"Error getting unique route patterns: {e}")
        return []


def get_unique_origins(organization_id: str) -> List[str]:
    """
    Get all unique origin values from route patterns.

    Args:
        organization_id: Organization UUID

    Returns:
        Sorted list of unique origin values (excluding wildcards)
    """
    patterns = get_unique_route_patterns(organization_id)
    origins = set()
    for pattern in patterns:
        parsed = parse_route_pattern(pattern)
        if parsed and parsed["origin"]:
            origins.add(parsed["origin"])
    return sorted(list(origins))


def get_unique_destinations(organization_id: str) -> List[str]:
    """
    Get all unique destination values from route patterns.

    Args:
        organization_id: Organization UUID

    Returns:
        Sorted list of unique destination values (excluding wildcards)
    """
    patterns = get_unique_route_patterns(organization_id)
    destinations = set()
    for pattern in patterns:
        parsed = parse_route_pattern(pattern)
        if parsed and parsed["destination"]:
            destinations.add(parsed["destination"])
    return sorted(list(destinations))


def assignment_exists(organization_id: str, route_pattern: str) -> bool:
    """
    Check if a route pattern is already assigned.

    Args:
        organization_id: Organization UUID
        route_pattern: Route pattern to check

    Returns:
        True if assignment exists, False otherwise
    """
    return get_route_logistics_assignment_by_pattern(organization_id, route_pattern) is not None


# =============================================================================
# ROUTE MATCHING Functions
# =============================================================================

def match_route_to_logistics_manager(
    organization_id: str,
    route: str,
) -> Optional[str]:
    """
    Match a route against patterns to find the responsible logistics manager.

    Uses the database function match_route_to_logistics_manager() for accurate matching.

    Args:
        organization_id: Organization UUID
        route: Route string (e.g., "Китай-Москва")

    Returns:
        User ID of the matched logistics manager, or None if no match

    Example:
        user_id = match_route_to_logistics_manager("org-uuid", "Китай-Москва")
    """
    try:
        supabase = _get_supabase()

        result = supabase.rpc(
            "match_route_to_logistics_manager",
            {
                "p_organization_id": organization_id,
                "p_route": route,
            }
        ).execute()

        if result.data is not None:
            return result.data
        return None

    except Exception as e:
        print(f"Error matching route to logistics manager: {e}")
        # Fallback to Python-based matching
        return _match_route_python(organization_id, route)


def _match_route_python(organization_id: str, route: str) -> Optional[str]:
    """
    Python fallback for route matching when DB function is unavailable.

    Priority:
    1. Exact match
    2. Patterns with fewer wildcards (more specific)
    3. Longer patterns
    """
    assignments = get_all_route_logistics_assignments(organization_id, limit=1000)

    # Try exact match first
    for assignment in assignments:
        if assignment.route_pattern == route:
            return assignment.user_id

    # Try wildcard matching
    matches = []
    for assignment in assignments:
        pattern = assignment.route_pattern
        # Convert pattern to regex
        regex_pattern = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
        if re.match(regex_pattern, route, re.IGNORECASE):
            wildcard_count = pattern.count("*")
            matches.append((wildcard_count, -len(pattern), assignment.user_id))

    if matches:
        # Sort by: fewer wildcards, then longer patterns
        matches.sort()
        return matches[0][2]

    return None


def get_logistics_manager_for_locations(
    organization_id: str,
    origin_country: Optional[str],
    destination_city: Optional[str],
) -> Optional[str]:
    """
    Find logistics manager for a route given origin and destination.

    Uses the database function get_logistics_manager_for_locations().

    Args:
        organization_id: Organization UUID
        origin_country: Origin country (e.g., "Китай")
        destination_city: Destination city (e.g., "Москва")

    Returns:
        User ID of the matched logistics manager, or None if no match

    Example:
        user_id = get_logistics_manager_for_locations("org-uuid", "Китай", "Москва")
    """
    try:
        supabase = _get_supabase()

        result = supabase.rpc(
            "get_logistics_manager_for_locations",
            {
                "p_organization_id": organization_id,
                "p_origin_country": origin_country or "*",
                "p_destination_city": destination_city or "*",
            }
        ).execute()

        if result.data is not None:
            return result.data
        return None

    except Exception as e:
        print(f"Error getting logistics manager for locations: {e}")
        # Fallback to building route and matching
        route = build_route_pattern(origin_country, destination_city)
        return match_route_to_logistics_manager(organization_id, route)


def find_matching_routes(
    organization_id: str,
    route: str,
) -> List[RouteLogisticsAssignment]:
    """
    Find all route assignments that match a given route.

    Useful for debugging which patterns would match.

    Args:
        organization_id: Organization UUID
        route: Route string to match against patterns

    Returns:
        List of matching RouteLogisticsAssignment records, sorted by priority
    """
    assignments = get_all_route_logistics_assignments(organization_id, limit=1000)
    matches = []

    for assignment in assignments:
        pattern = assignment.route_pattern

        # Check exact match
        if pattern == route:
            matches.append((0, -len(pattern), assignment))
            continue

        # Check wildcard match
        regex_pattern = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
        if re.match(regex_pattern, route, re.IGNORECASE):
            wildcard_count = pattern.count("*")
            matches.append((wildcard_count, -len(pattern), assignment))

    # Sort by priority
    matches.sort(key=lambda x: (x[0], x[1]))
    return [m[2] for m in matches]


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_route_logistics_assignment(
    assignment_id: str,
    *,
    route_pattern: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[RouteLogisticsAssignment]:
    """
    Update a route-logistics assignment.

    Args:
        assignment_id: UUID of the assignment to update
        route_pattern: New route pattern
        user_id: New logistics manager user ID

    Returns:
        Updated RouteLogisticsAssignment if successful, None otherwise
    """
    try:
        supabase = _get_supabase()

        update_data = {}
        if route_pattern is not None:
            normalized = normalize_route_pattern(route_pattern)
            if not validate_route_pattern(normalized):
                return None
            update_data["route_pattern"] = normalized
        if user_id is not None:
            update_data["user_id"] = user_id

        if not update_data:
            return get_route_logistics_assignment(assignment_id)

        result = supabase.table("route_logistics_assignments")\
            .update(update_data)\
            .eq("id", assignment_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_assignment(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation
        if "route_logistics_assignments_unique_pattern" in str(e) or "duplicate key" in str(e).lower():
            return None
        print(f"Error updating route-logistics assignment: {e}")
        return None


def reassign_route_to_user(
    organization_id: str,
    route_pattern: str,
    new_user_id: str,
) -> Optional[RouteLogisticsAssignment]:
    """
    Reassign a route pattern to a different logistics manager.

    Args:
        organization_id: Organization UUID
        route_pattern: Route pattern to reassign
        new_user_id: New logistics manager user ID

    Returns:
        Updated RouteLogisticsAssignment if successful, None otherwise
    """
    assignment = get_route_logistics_assignment_by_pattern(organization_id, route_pattern)
    if not assignment:
        return None

    return update_route_logistics_assignment(
        assignment.id,
        user_id=new_user_id,
    )


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_route_logistics_assignment(assignment_id: str) -> bool:
    """
    Delete a route-logistics assignment by ID.

    Args:
        assignment_id: UUID of the assignment to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        supabase.table("route_logistics_assignments")\
            .delete()\
            .eq("id", assignment_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting route-logistics assignment: {e}")
        return False


def delete_route_logistics_assignment_by_pattern(
    organization_id: str,
    route_pattern: str,
) -> bool:
    """
    Delete a route-logistics assignment by pattern.

    Args:
        organization_id: Organization UUID
        route_pattern: Route pattern to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()
        normalized = normalize_route_pattern(route_pattern)

        supabase.table("route_logistics_assignments")\
            .delete()\
            .eq("organization_id", organization_id)\
            .eq("route_pattern", normalized)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting assignment by pattern: {e}")
        return False


def delete_all_assignments_for_user(
    organization_id: str,
    user_id: str,
) -> int:
    """
    Delete all route assignments for a logistics manager.

    Useful when removing a user from logistics role.

    Args:
        organization_id: Organization UUID
        user_id: Logistics manager user ID

    Returns:
        Number of assignments deleted
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments")\
            .delete()\
            .eq("organization_id", organization_id)\
            .eq("user_id", user_id)\
            .execute()

        return len(result.data) if result.data else 0

    except Exception as e:
        print(f"Error deleting all assignments for user: {e}")
        return 0


# =============================================================================
# UTILITY Functions
# =============================================================================

def get_route_user_mapping(organization_id: str) -> Dict[str, str]:
    """
    Get a dictionary mapping route patterns to user IDs.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict mapping route_pattern to user_id

    Example:
        mapping = get_route_user_mapping("org-uuid")
        user_id = mapping.get("Китай-*")
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments")\
            .select("route_pattern, user_id")\
            .eq("organization_id", organization_id)\
            .execute()

        mapping = {}
        if result.data:
            for row in result.data:
                mapping[row["route_pattern"]] = row["user_id"]
        return mapping

    except Exception as e:
        print(f"Error getting route-user mapping: {e}")
        return {}


def get_routes_count_by_user(organization_id: str) -> Dict[str, int]:
    """
    Get count of routes assigned to each user.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict mapping user_id to count of assigned routes
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("route_logistics_assignments")\
            .select("user_id")\
            .eq("organization_id", organization_id)\
            .execute()

        counts: Dict[str, int] = {}
        if result.data:
            for row in result.data:
                user_id = row["user_id"]
                counts[user_id] = counts.get(user_id, 0) + 1
        return counts

    except Exception as e:
        print(f"Error getting routes count by user: {e}")
        return {}


def get_route_logistics_assignment_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get statistics about route-logistics assignments.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total_assignments: Total number of route assignments
        - unique_users: Number of unique logistics managers assigned
        - unique_origins: Number of unique origin values
        - unique_destinations: Number of unique destination values
        - wildcard_patterns: Number of patterns using wildcards
        - exact_patterns: Number of exact route patterns
    """
    try:
        assignments = get_all_route_logistics_assignments(organization_id, limit=1000)

        if not assignments:
            return {
                "total_assignments": 0,
                "unique_users": 0,
                "unique_origins": 0,
                "unique_destinations": 0,
                "wildcard_patterns": 0,
                "exact_patterns": 0,
            }

        users = set()
        origins = set()
        destinations = set()
        wildcard_count = 0
        exact_count = 0

        for assignment in assignments:
            users.add(assignment.user_id)
            parsed = parse_route_pattern(assignment.route_pattern)
            if parsed:
                if parsed["origin"]:
                    origins.add(parsed["origin"])
                if parsed["destination"]:
                    destinations.add(parsed["destination"])

            if "*" in assignment.route_pattern:
                wildcard_count += 1
            else:
                exact_count += 1

        return {
            "total_assignments": len(assignments),
            "unique_users": len(users),
            "unique_origins": len(origins),
            "unique_destinations": len(destinations),
            "wildcard_patterns": wildcard_count,
            "exact_patterns": exact_count,
        }

    except Exception as e:
        print(f"Error getting route-logistics assignment stats: {e}")
        return {
            "total_assignments": 0,
            "unique_users": 0,
            "unique_origins": 0,
            "unique_destinations": 0,
            "wildcard_patterns": 0,
            "exact_patterns": 0,
        }


def get_route_assignments_summary(organization_id: str) -> List[Dict[str, Any]]:
    """
    Get a summary of route assignments grouped by user.

    Uses the database function get_route_assignments_summary() if available.

    Args:
        organization_id: Organization UUID

    Returns:
        List of dicts with user_id, user_email, routes_count, patterns
    """
    try:
        supabase = _get_supabase()

        result = supabase.rpc(
            "get_route_assignments_summary",
            {"p_organization_id": organization_id}
        ).execute()

        return result.data if result.data else []

    except Exception as e:
        print(f"Error getting route assignments summary: {e}")
        # Fallback to Python-based summary
        return _get_route_assignments_summary_python(organization_id)


def _get_route_assignments_summary_python(organization_id: str) -> List[Dict[str, Any]]:
    """Python fallback for route assignments summary."""
    assignments = get_all_route_logistics_assignments(organization_id, limit=1000)

    user_data: Dict[str, Dict[str, Any]] = {}
    for assignment in assignments:
        user_id = assignment.user_id
        if user_id not in user_data:
            user_data[user_id] = {
                "user_id": user_id,
                "user_email": None,  # Would need to join with auth.users
                "routes_count": 0,
                "patterns": [],
            }
        user_data[user_id]["routes_count"] += 1
        user_data[user_id]["patterns"].append(assignment.route_pattern)

    # Sort by routes_count descending
    summary = sorted(user_data.values(), key=lambda x: -x["routes_count"])
    return summary


def format_route_assignment_for_display(assignment: RouteLogisticsAssignment) -> str:
    """
    Format a route-logistics assignment for display.

    Args:
        assignment: RouteLogisticsAssignment object

    Returns:
        Display string like "Китай-* -> logistics@company.com"
    """
    user_info = assignment.user_email or assignment.user_name or assignment.user_id[:8]
    return f"{assignment.route_pattern} -> {user_info}"


def get_routes_for_dropdown(organization_id: str) -> List[Dict[str, str]]:
    """
    Get route patterns formatted for dropdown.

    Args:
        organization_id: Organization UUID

    Returns:
        List of dicts with 'value' (pattern) and 'label' for dropdown options
    """
    assignments = get_all_route_logistics_assignments(organization_id)

    options = []
    for a in assignments:
        label = a.route_pattern
        parsed = parse_route_pattern(a.route_pattern)
        if parsed:
            origin = parsed["origin"] or "Любой"
            dest = parsed["destination"] or "Любой"
            label = f"{origin} → {dest}"

        options.append({
            "value": a.route_pattern,
            "label": label,
        })

    return options


def check_route_coverage(
    organization_id: str,
    routes: List[str],
) -> Dict[str, Optional[str]]:
    """
    Check which routes have logistics managers assigned.

    Useful for validating quote items have logistics coverage.

    Args:
        organization_id: Organization UUID
        routes: List of route strings to check (e.g., ["Китай-Москва", "Турция-СПб"])

    Returns:
        Dict mapping route to user_id (None if no assignment)

    Example:
        coverage = check_route_coverage("org-uuid", ["Китай-Москва", "Турция-СПб"])
        uncovered = [r for r, u in coverage.items() if u is None]
    """
    coverage = {}
    for route in routes:
        user_id = match_route_to_logistics_manager(organization_id, route)
        coverage[route] = user_id
    return coverage


def get_uncovered_routes(
    organization_id: str,
    routes: List[str],
) -> List[str]:
    """
    Get routes that don't have any logistics manager assigned.

    Args:
        organization_id: Organization UUID
        routes: List of route strings to check

    Returns:
        List of routes without assignments

    Example:
        uncovered = get_uncovered_routes("org-uuid", ["Китай-Москва", "США-Москва"])
    """
    coverage = check_route_coverage(organization_id, routes)
    return [route for route, user_id in coverage.items() if user_id is None]
