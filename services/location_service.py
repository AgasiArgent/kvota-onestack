"""
Location Service - CRUD operations for locations table

This module provides functions for managing locations directory:
- Create/Update/Delete locations
- Query locations by organization, country, type (hub/customs)
- Search locations for HTMX dropdown with trigram search
- Seed default locations for new organizations

Based on app_spec.xml locations table definition (Feature API-006).
Database migration: 024_create_locations_table.sql

Location usage: pickup_location_id in quote_items
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
class Location:
    """
    Represents a location record from the locations directory.

    Used for dropdown search when selecting pickup/delivery locations
    in quote_items (pickup_location_id).

    Maps to locations table in database.
    """
    id: str
    organization_id: str
    country: str  # Required - country name

    # Optional location details
    city: Optional[str] = None
    code: Optional[str] = None  # Short code (e.g., "MSK", "SPB", "SH")
    address: Optional[str] = None  # Full address for specific pickup points

    # Classification flags
    is_hub: bool = False  # Logistics hub
    is_customs_point: bool = False  # Customs clearance point
    is_active: bool = True

    # Computed fields (from database GENERATED columns)
    display_name: Optional[str] = None  # e.g., "MSK - Москва, Россия"
    search_text: Optional[str] = None  # Lowercase search text

    # Metadata
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


def _parse_location(data: dict) -> Location:
    """Parse database row into Location object."""
    return Location(
        id=data["id"],
        organization_id=data["organization_id"],
        country=data["country"],
        city=data.get("city"),
        code=data.get("code"),
        address=data.get("address"),
        is_hub=data.get("is_hub", False),
        is_customs_point=data.get("is_customs_point", False),
        is_active=data.get("is_active", True),
        display_name=data.get("display_name"),
        search_text=data.get("search_text"),
        notes=data.get("notes"),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        created_by=data.get("created_by"),
    )


def _location_to_dict(location: Location) -> dict:
    """Convert Location object to dict for database operations."""
    return {
        "organization_id": location.organization_id,
        "country": location.country,
        "city": location.city,
        "code": location.code,
        "address": location.address,
        "is_hub": location.is_hub,
        "is_customs_point": location.is_customs_point,
        "is_active": location.is_active,
        "notes": location.notes,
        "created_by": location.created_by,
    }


# =============================================================================
# VALIDATION
# =============================================================================

def validate_location_code(code: str) -> bool:
    """
    Validate location code format (2-5 uppercase letters).

    Args:
        code: Location code to validate

    Returns:
        True if valid, False otherwise

    Examples:
        validate_location_code("MSK")  # True
        validate_location_code("SH")   # True
        validate_location_code("ABCDE")  # True
        validate_location_code("123")  # False
    """
    if not code:
        return True  # Code is optional
    return bool(re.match(r'^[A-Z]{2,5}$', code))


def validate_country(country: str) -> bool:
    """
    Validate country name.

    Args:
        country: Country name to validate

    Returns:
        True if valid (non-empty), False otherwise
    """
    return bool(country and country.strip())


# =============================================================================
# CREATE Operations
# =============================================================================

def create_location(
    organization_id: str,
    country: str,
    *,
    city: Optional[str] = None,
    code: Optional[str] = None,
    address: Optional[str] = None,
    is_hub: bool = False,
    is_customs_point: bool = False,
    is_active: bool = True,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[Location]:
    """
    Create a new location.

    Args:
        organization_id: Organization UUID
        country: Country name (required)
        city: City name (optional)
        code: Short code like MSK, SPB, SH (2-5 uppercase letters)
        address: Full address for specific pickup points
        is_hub: Whether this is a logistics hub
        is_customs_point: Whether this is a customs clearance point
        is_active: Whether location is active
        notes: Additional notes
        created_by: User UUID who created this location

    Returns:
        Location object if successful, None on failure

    Raises:
        ValueError: If country is empty or code format is invalid

    Example:
        location = create_location(
            organization_id="org-uuid",
            country="Россия",
            city="Москва",
            code="MSK",
            is_hub=True,
            created_by="admin-uuid"
        )
    """
    # Validate country
    if not validate_country(country):
        raise ValueError("Country is required and cannot be empty")

    # Uppercase code before validation (for convenience)
    if code:
        code = code.upper()

    # Validate code format if provided
    if code and not validate_location_code(code):
        raise ValueError(f"Invalid location code format: {code}. Must be 2-5 uppercase letters.")

    try:
        supabase = _get_supabase()

        result = supabase.table("locations").insert({
            "organization_id": organization_id,
            "country": country.strip(),
            "city": city.strip() if city else None,
            "code": code,  # Already uppercased above
            "address": address.strip() if address else None,
            "is_hub": is_hub,
            "is_customs_point": is_customs_point,
            "is_active": is_active,
            "notes": notes.strip() if notes else None,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_location(result.data[0])
        return None

    except Exception as e:
        print(f"Error creating location: {e}")
        return None


def create_location_if_not_exists(
    organization_id: str,
    country: str,
    *,
    city: Optional[str] = None,
    code: Optional[str] = None,
    **kwargs,
) -> Optional[Location]:
    """
    Create a location only if it doesn't already exist.

    Checks by code (if provided) or by country+city combination.

    Args:
        organization_id: Organization UUID
        country: Country name
        city: City name
        code: Location code
        **kwargs: Additional fields for create_location

    Returns:
        Existing or newly created Location
    """
    # Check if location exists
    if code:
        existing = get_location_by_code(organization_id, code)
        if existing:
            return existing

    # If no code, check by country+city
    if city:
        existing = get_location_by_country_city(organization_id, country, city)
        if existing:
            return existing

    # Create new location
    return create_location(
        organization_id=organization_id,
        country=country,
        city=city,
        code=code,
        **kwargs,
    )


# =============================================================================
# READ Operations
# =============================================================================

def get_location(location_id: str) -> Optional[Location]:
    """
    Get a location by ID.

    Args:
        location_id: Location UUID

    Returns:
        Location object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("locations").select("*").eq("id", location_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_location(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting location: {e}")
        return None


def get_location_by_code(organization_id: str, code: str) -> Optional[Location]:
    """
    Get a location by its code within an organization.

    Args:
        organization_id: Organization UUID
        code: Location code (e.g., "MSK", "SPB")

    Returns:
        Location object if found, None otherwise
    """
    if not code:
        return None

    try:
        supabase = _get_supabase()

        result = supabase.table("locations").select("*")\
            .eq("organization_id", organization_id)\
            .eq("code", code.upper())\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_location(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting location by code: {e}")
        return None


def get_location_by_country_city(
    organization_id: str,
    country: str,
    city: str,
) -> Optional[Location]:
    """
    Get a location by country and city.

    Args:
        organization_id: Organization UUID
        country: Country name
        city: City name

    Returns:
        Location object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("locations").select("*")\
            .eq("organization_id", organization_id)\
            .eq("country", country)\
            .eq("city", city)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_location(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting location by country/city: {e}")
        return None


def get_all_locations(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
    is_hub: Optional[bool] = None,
    is_customs_point: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Location]:
    """
    Get all locations for an organization with optional filters.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status (None = all)
        is_hub: Filter by hub status (None = all)
        is_customs_point: Filter by customs point status (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of Location objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("locations").select("*")\
            .eq("organization_id", organization_id)\
            .order("display_name")

        if is_active is not None:
            query = query.eq("is_active", is_active)
        if is_hub is not None:
            query = query.eq("is_hub", is_hub)
        if is_customs_point is not None:
            query = query.eq("is_customs_point", is_customs_point)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_location(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all locations: {e}")
        return []


def get_locations_by_country(
    organization_id: str,
    country: str,
    *,
    is_active: Optional[bool] = True,
) -> List[Location]:
    """
    Get locations by country.

    Args:
        organization_id: Organization UUID
        country: Country name
        is_active: Filter by active status

    Returns:
        List of Location objects in the specified country
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("locations").select("*")\
            .eq("organization_id", organization_id)\
            .eq("country", country)\
            .order("display_name")

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.execute()

        return [_parse_location(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting locations by country: {e}")
        return []


def get_hub_locations(organization_id: str) -> List[Location]:
    """
    Get all logistics hub locations.

    Args:
        organization_id: Organization UUID

    Returns:
        List of hub Location objects
    """
    return get_all_locations(organization_id, is_active=True, is_hub=True, limit=1000)


def get_customs_point_locations(organization_id: str) -> List[Location]:
    """
    Get all customs clearance point locations.

    Args:
        organization_id: Organization UUID

    Returns:
        List of customs point Location objects
    """
    return get_all_locations(organization_id, is_active=True, is_customs_point=True, limit=1000)


def count_locations(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
    is_hub: Optional[bool] = None,
    is_customs_point: Optional[bool] = None,
) -> int:
    """
    Count locations in an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status
        is_hub: Filter by hub status
        is_customs_point: Filter by customs point status

    Returns:
        Number of locations
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("locations").select("id", count="exact")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            query = query.eq("is_active", is_active)
        if is_hub is not None:
            query = query.eq("is_hub", is_hub)
        if is_customs_point is not None:
            query = query.eq("is_customs_point", is_customs_point)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting locations: {e}")
        return 0


def location_exists(organization_id: str, code: str) -> bool:
    """
    Check if a location with given code exists.

    Args:
        organization_id: Organization UUID
        code: Location code to check

    Returns:
        True if location exists, False otherwise
    """
    return get_location_by_code(organization_id, code) is not None


# =============================================================================
# SEARCH Operations (for HTMX dropdown)
# =============================================================================

def search_locations(
    organization_id: str,
    query: str,
    *,
    is_hub_only: bool = False,
    is_customs_only: bool = False,
    limit: int = 20,
) -> List[Location]:
    """
    Search locations using trigram-based search.

    This function uses the database search_locations() function
    which leverages pg_trgm extension for fast partial matching.

    Used for HTMX dropdown autocomplete.

    Args:
        organization_id: Organization UUID
        query: Search query (matches code, city, country, address)
        is_hub_only: Return only hub locations
        is_customs_only: Return only customs point locations
        limit: Maximum number of results

    Returns:
        List of matching Location objects, ordered by:
        1. Exact code match first
        2. Hubs first
        3. Alphabetically by display_name

    Example:
        # Search for locations containing "моск" (Moscow)
        locations = search_locations("org-uuid", "моск", limit=10)

        # Search for hubs only
        hubs = search_locations("org-uuid", "china", is_hub_only=True)
    """
    try:
        supabase = _get_supabase()

        # Call the database function search_locations()
        result = supabase.rpc("search_locations", {
            "p_organization_id": organization_id,
            "p_query": query,
            "p_limit": limit,
            "p_hub_only": is_hub_only,
            "p_customs_only": is_customs_only,
        }).execute()

        if not result.data:
            return []

        # The function returns a subset of columns, fetch full records
        location_ids = [row["id"] for row in result.data]

        if not location_ids:
            return []

        # Get full location records
        full_result = supabase.table("locations").select("*")\
            .in_("id", location_ids)\
            .execute()

        if not full_result.data:
            return []

        # Maintain the search order from the RPC result
        id_to_location = {row["id"]: _parse_location(row) for row in full_result.data}
        return [id_to_location[loc_id] for loc_id in location_ids if loc_id in id_to_location]

    except Exception as e:
        # Fallback to simple ILIKE search if RPC fails
        print(f"RPC search_locations failed, using fallback: {e}")
        return _search_locations_fallback(
            organization_id, query,
            is_hub_only=is_hub_only,
            is_customs_only=is_customs_only,
            limit=limit,
        )


def _search_locations_fallback(
    organization_id: str,
    query: str,
    *,
    is_hub_only: bool = False,
    is_customs_only: bool = False,
    limit: int = 20,
) -> List[Location]:
    """
    Fallback search using ILIKE if RPC is not available.

    Args:
        organization_id: Organization UUID
        query: Search query
        is_hub_only: Return only hub locations
        is_customs_only: Return only customs point locations
        limit: Maximum results

    Returns:
        List of matching Location objects
    """
    if not query or len(query) < 1:
        # Return top locations by display name if no query
        return get_all_locations(
            organization_id,
            is_active=True,
            is_hub=True if is_hub_only else None,
            is_customs_point=True if is_customs_only else None,
            limit=limit,
        )

    try:
        supabase = _get_supabase()

        search_pattern = f"%{query.lower()}%"

        base_query = supabase.table("locations").select("*")\
            .eq("organization_id", organization_id)\
            .eq("is_active", True)\
            .ilike("search_text", search_pattern)

        if is_hub_only:
            base_query = base_query.eq("is_hub", True)
        if is_customs_only:
            base_query = base_query.eq("is_customs_point", True)

        result = base_query\
            .order("is_hub", desc=True)\
            .order("display_name")\
            .limit(limit)\
            .execute()

        return [_parse_location(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error in fallback search: {e}")
        return []


def get_active_locations(organization_id: str) -> List[Location]:
    """
    Get all active locations for an organization.

    Convenience function for dropdown lists.

    Args:
        organization_id: Organization UUID

    Returns:
        List of active Location objects
    """
    return get_all_locations(organization_id, is_active=True, limit=1000)


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_location(
    location_id: str,
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    code: Optional[str] = None,
    address: Optional[str] = None,
    is_hub: Optional[bool] = None,
    is_customs_point: Optional[bool] = None,
    is_active: Optional[bool] = None,
    notes: Optional[str] = None,
) -> Optional[Location]:
    """
    Update a location.

    Args:
        location_id: Location UUID
        country: New country name
        city: New city name
        code: New location code
        address: New address
        is_hub: New hub status
        is_customs_point: New customs point status
        is_active: New active status
        notes: New notes

    Returns:
        Updated Location object if successful, None otherwise

    Raises:
        ValueError: If country is empty or code format is invalid
    """
    # Validate country if provided
    if country is not None and not validate_country(country):
        raise ValueError("Country cannot be empty")

    # Validate code format if provided
    if code is not None and code and not validate_location_code(code):
        raise ValueError(f"Invalid location code format: {code}. Must be 2-5 uppercase letters.")

    try:
        supabase = _get_supabase()

        # Build update dict with only provided fields
        update_data = {}
        if country is not None:
            update_data["country"] = country.strip()
        if city is not None:
            update_data["city"] = city.strip() if city else None
        if code is not None:
            update_data["code"] = code.upper() if code else None
        if address is not None:
            update_data["address"] = address.strip() if address else None
        if is_hub is not None:
            update_data["is_hub"] = is_hub
        if is_customs_point is not None:
            update_data["is_customs_point"] = is_customs_point
        if is_active is not None:
            update_data["is_active"] = is_active
        if notes is not None:
            update_data["notes"] = notes.strip() if notes else None

        if not update_data:
            # Nothing to update, return current state
            return get_location(location_id)

        result = supabase.table("locations").update(update_data)\
            .eq("id", location_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_location(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating location: {e}")
        return None


def activate_location(location_id: str) -> Optional[Location]:
    """
    Activate a location.

    Args:
        location_id: Location UUID

    Returns:
        Updated Location object
    """
    return update_location(location_id, is_active=True)


def deactivate_location(location_id: str) -> Optional[Location]:
    """
    Deactivate a location (soft delete).

    Args:
        location_id: Location UUID

    Returns:
        Updated Location object
    """
    return update_location(location_id, is_active=False)


def set_as_hub(location_id: str, is_hub: bool = True) -> Optional[Location]:
    """
    Set or unset location as a logistics hub.

    Args:
        location_id: Location UUID
        is_hub: Whether it's a hub

    Returns:
        Updated Location object
    """
    return update_location(location_id, is_hub=is_hub)


def set_as_customs_point(location_id: str, is_customs_point: bool = True) -> Optional[Location]:
    """
    Set or unset location as a customs clearance point.

    Args:
        location_id: Location UUID
        is_customs_point: Whether it's a customs point

    Returns:
        Updated Location object
    """
    return update_location(location_id, is_customs_point=is_customs_point)


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_location(location_id: str) -> bool:
    """
    Delete a location permanently.

    Note: Consider using deactivate_location() instead for soft delete.

    Args:
        location_id: Location UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("locations").delete()\
            .eq("id", location_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting location: {e}")
        return False


# =============================================================================
# UTILITY Functions
# =============================================================================

def get_unique_countries(organization_id: str) -> List[str]:
    """
    Get list of unique countries from all locations.

    Args:
        organization_id: Organization UUID

    Returns:
        List of unique country names, sorted alphabetically
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("locations").select("country")\
            .eq("organization_id", organization_id)\
            .eq("is_active", True)\
            .execute()

        if result.data:
            countries = set(row["country"] for row in result.data if row.get("country"))
            return sorted(list(countries))
        return []

    except Exception as e:
        print(f"Error getting unique countries: {e}")
        return []


def get_location_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get location statistics for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total: Total number of locations
        - active: Number of active locations
        - inactive: Number of inactive locations
        - hubs: Number of hub locations
        - customs_points: Number of customs points
        - by_country: Count by country
    """
    try:
        supabase = _get_supabase()

        # Get all locations
        result = supabase.table("locations").select("is_active, is_hub, is_customs_point, country")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "hubs": 0,
                "customs_points": 0,
                "by_country": {},
            }

        total = len(result.data)
        active = sum(1 for row in result.data if row.get("is_active", True))
        inactive = total - active
        hubs = sum(1 for row in result.data if row.get("is_hub", False))
        customs_points = sum(1 for row in result.data if row.get("is_customs_point", False))

        # Count by country
        by_country = {}
        for row in result.data:
            country = row.get("country") or "Unknown"
            by_country[country] = by_country.get(country, 0) + 1

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "hubs": hubs,
            "customs_points": customs_points,
            "by_country": by_country,
        }

    except Exception as e:
        print(f"Error getting location stats: {e}")
        return {
            "total": 0,
            "active": 0,
            "inactive": 0,
            "hubs": 0,
            "customs_points": 0,
            "by_country": {},
        }


def get_location_display_name(location: Location) -> str:
    """
    Get display name for a location.

    Uses the computed display_name from database if available,
    otherwise generates it.

    Args:
        location: Location object

    Returns:
        Display string like "MSK - Москва, Россия"
    """
    if location.display_name:
        return location.display_name

    # Generate display name
    if location.code and location.city:
        return f"{location.code} - {location.city}, {location.country}"
    elif location.city:
        return f"{location.city}, {location.country}"
    else:
        return location.country


def format_location_for_dropdown(location: Location) -> Dict[str, str]:
    """
    Format location for HTMX dropdown option.

    Args:
        location: Location object

    Returns:
        Dict with 'value' (id) and 'label' (display name)
    """
    label = get_location_display_name(location)

    # Add badges for hub/customs
    badges = []
    if location.is_hub:
        badges.append("хаб")
    if location.is_customs_point:
        badges.append("таможня")

    if badges:
        label += f" [{', '.join(badges)}]"

    return {
        "value": location.id,
        "label": label,
    }


def get_locations_for_dropdown(
    organization_id: str,
    *,
    query: Optional[str] = None,
    is_hub_only: bool = False,
    is_customs_only: bool = False,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Get locations formatted for dropdown/select element.

    Args:
        organization_id: Organization UUID
        query: Optional search query
        is_hub_only: Return only hub locations
        is_customs_only: Return only customs points
        limit: Maximum results

    Returns:
        List of dicts with 'value' and 'label' for dropdown options
    """
    if query:
        locations = search_locations(
            organization_id, query,
            is_hub_only=is_hub_only,
            is_customs_only=is_customs_only,
            limit=limit,
        )
    else:
        locations = get_all_locations(
            organization_id,
            is_active=True,
            is_hub=True if is_hub_only else None,
            is_customs_point=True if is_customs_only else None,
            limit=limit,
        )

    return [format_location_for_dropdown(loc) for loc in locations]


# =============================================================================
# SEED DATA Functions
# =============================================================================

def seed_default_locations(
    organization_id: str,
    created_by: Optional[str] = None,
) -> int:
    """
    Seed default locations for a new organization.

    Uses the database function create_default_locations() if available,
    otherwise creates locations directly.

    Args:
        organization_id: Organization UUID
        created_by: User UUID who is seeding the locations

    Returns:
        Number of locations created
    """
    try:
        supabase = _get_supabase()

        # Try to use database function first
        result = supabase.rpc("create_default_locations", {
            "p_organization_id": organization_id,
            "p_created_by": created_by,
        }).execute()

        if result.data is not None:
            return result.data

    except Exception as e:
        print(f"RPC create_default_locations failed, using fallback: {e}")

    # Fallback: create locations directly
    return _seed_default_locations_fallback(organization_id, created_by)


def _seed_default_locations_fallback(
    organization_id: str,
    created_by: Optional[str] = None,
) -> int:
    """
    Fallback seed function if database RPC is not available.

    Creates default locations for common supply chain routes.
    """
    default_locations = [
        # China
        {"country": "Китай", "city": "Шанхай", "code": "SH", "is_hub": True},
        {"country": "Китай", "city": "Шэньчжэнь", "code": "SZ", "is_hub": True},
        {"country": "Китай", "city": "Гуанчжоу", "code": "GZ", "is_hub": True},
        {"country": "Китай", "city": "Иу", "code": "YW", "is_hub": True},
        {"country": "Китай", "city": "Нинбо", "code": "NB", "is_hub": True},
        {"country": "Китай", "city": "Пекин", "code": "BJ", "is_hub": False},
        {"country": "Китай", "city": "Циндао", "code": "TAO", "is_hub": True},
        {"country": "Китай", "city": "Тяньцзинь", "code": "TSN", "is_hub": True},

        # Russia
        {"country": "Россия", "city": "Москва", "code": "MSK", "is_hub": True, "is_customs_point": False},
        {"country": "Россия", "city": "Санкт-Петербург", "code": "SPB", "is_hub": True, "is_customs_point": False},
        {"country": "Россия", "city": "Владивосток", "code": "VVO", "is_hub": True, "is_customs_point": True},
        {"country": "Россия", "city": "Новосибирск", "code": "OVB", "is_hub": True, "is_customs_point": False},
        {"country": "Россия", "city": "Екатеринбург", "code": "SVX", "is_hub": True, "is_customs_point": False},
        {"country": "Россия", "city": "Забайкальск", "code": "ZBK", "is_hub": False, "is_customs_point": True},
        {"country": "Россия", "city": "Благовещенск", "code": "BQS", "is_hub": False, "is_customs_point": True},

        # CIS
        {"country": "Казахстан", "city": "Алматы", "code": "ALA", "is_hub": True},
        {"country": "Казахстан", "city": "Хоргос", "code": "KHG", "is_hub": False, "is_customs_point": True},

        # Europe
        {"country": "Германия", "city": "Гамбург", "code": "HAM", "is_hub": True},
        {"country": "Нидерланды", "city": "Роттердам", "code": "RTM", "is_hub": True},
        {"country": "Италия", "city": "Милан", "code": "MXP", "is_hub": True},

        # Turkey
        {"country": "Турция", "city": "Стамбул", "code": "IST", "is_hub": True},
    ]

    count = 0
    for loc_data in default_locations:
        try:
            location = create_location_if_not_exists(
                organization_id=organization_id,
                created_by=created_by,
                **loc_data,
            )
            if location:
                count += 1
        except Exception as e:
            print(f"Error creating location {loc_data}: {e}")

    return count


def get_location_for_route(
    organization_id: str,
    country: str,
    city: Optional[str] = None,
) -> Optional[Location]:
    """
    Get the best matching location for a route.

    Tries to find by city first, then falls back to country.

    Args:
        organization_id: Organization UUID
        country: Country name
        city: Optional city name

    Returns:
        Best matching Location or None
    """
    if city:
        location = get_location_by_country_city(organization_id, country, city)
        if location:
            return location

    # Try to find any location in the country
    locations = get_locations_by_country(organization_id, country, is_active=True)
    if locations:
        # Prefer hubs
        hubs = [loc for loc in locations if loc.is_hub]
        if hubs:
            return hubs[0]
        return locations[0]

    return None
