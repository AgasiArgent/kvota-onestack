"""
Customer Contract Service - CRUD operations for customer_contracts table

This module provides functions for managing customer supply contracts:
- Create/Update/Delete contracts
- Query contracts by organization, customer, status
- Search contracts for HTMX dropdowns
- Manage specification numbering within contracts

Based on app_spec.xml customer_contracts table definition (Feature API-005).

Level: CUSTOMER (multiple contracts per customer)

Each contract has a next_specification_number counter used for generating
sequential specification numbers when creating specifications for quotes.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import os
import re
from supabase import create_client
from supabase.lib.client_options import ClientOptions


# Initialize Supabase client with service role for admin operations
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _get_supabase():
    """Get Supabase client with service role key for admin operations."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    opts = ClientOptions(schema="kvota")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY, options=opts)


# =============================================================================
# CONSTANTS
# =============================================================================

# Valid contract statuses
CONTRACT_STATUSES = ["active", "suspended", "terminated"]

# Status display names in Russian
CONTRACT_STATUS_NAMES = {
    "active": "Действующий",
    "suspended": "Приостановлен",
    "terminated": "Расторгнут",
}

# Status colors for UI
CONTRACT_STATUS_COLORS = {
    "active": "green",
    "suspended": "yellow",
    "terminated": "red",
}


# =============================================================================
# DATA CLASS
# =============================================================================

@dataclass
class CustomerContract:
    """
    Represents a customer supply contract.

    Maps to customer_contracts table in database.
    """
    id: str
    organization_id: str
    customer_id: str
    contract_number: str
    contract_date: date

    # Contract status
    status: str = "active"

    # Specification numbering counter
    next_specification_number: int = 1

    # Notes
    notes: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Optional: Customer name (populated by get_contract_with_customer)
    customer_name: Optional[str] = None


def _parse_contract(data: dict) -> CustomerContract:
    """Parse database row into CustomerContract object."""
    # Parse contract_date
    contract_date = data.get("contract_date")
    if isinstance(contract_date, str):
        contract_date = date.fromisoformat(contract_date)
    elif not isinstance(contract_date, date):
        contract_date = date.today()

    return CustomerContract(
        id=data["id"],
        organization_id=data["organization_id"],
        customer_id=data["customer_id"],
        contract_number=data["contract_number"],
        contract_date=contract_date,
        status=data.get("status", "active"),
        next_specification_number=data.get("next_specification_number", 1),
        notes=data.get("notes"),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        customer_name=data.get("customer_name"),
    )


# =============================================================================
# VALIDATION
# =============================================================================

def validate_contract_number(contract_number: str) -> bool:
    """
    Validate contract number format.

    Contract numbers should not be empty and should contain
    alphanumeric characters, dashes, slashes, and spaces.

    Args:
        contract_number: Contract number to validate

    Returns:
        True if valid format, False otherwise
    """
    if not contract_number or not contract_number.strip():
        return False
    # Allow alphanumeric, dashes, slashes, dots, and spaces
    return bool(re.match(r'^[\w\d\-/\.\s№]+$', contract_number))


def validate_contract_status(status: str) -> bool:
    """
    Validate contract status value.

    Args:
        status: Status to validate

    Returns:
        True if valid status, False otherwise
    """
    return status in CONTRACT_STATUSES


# =============================================================================
# STATUS HELPERS
# =============================================================================

def get_contract_status_name(status: str) -> str:
    """
    Get human-readable status name in Russian.

    Args:
        status: Status code

    Returns:
        Russian name for the status
    """
    return CONTRACT_STATUS_NAMES.get(status, status)


def get_contract_status_color(status: str) -> str:
    """
    Get color for status display.

    Args:
        status: Status code

    Returns:
        Color name for UI
    """
    return CONTRACT_STATUS_COLORS.get(status, "gray")


def is_contract_active(contract: CustomerContract) -> bool:
    """
    Check if contract is active.

    Args:
        contract: CustomerContract object

    Returns:
        True if contract status is 'active'
    """
    return contract.status == "active"


# =============================================================================
# CREATE OPERATIONS
# =============================================================================

def create_contract(
    organization_id: str,
    customer_id: str,
    contract_number: str,
    contract_date: date,
    *,
    status: str = "active",
    notes: Optional[str] = None,
) -> Optional[CustomerContract]:
    """
    Create a new customer contract.

    Args:
        organization_id: Organization UUID
        customer_id: Customer UUID
        contract_number: Contract number (unique within organization)
        contract_date: Date when contract was signed
        status: Contract status (default: active)
        notes: Optional notes

    Returns:
        CustomerContract object if successful, None otherwise

    Raises:
        ValueError: If validation fails or contract number is not unique

    Example:
        contract = create_contract(
            organization_id="org-uuid",
            customer_id="customer-uuid",
            contract_number="ДП-001/2025",
            contract_date=date(2025, 1, 15),
        )
    """
    # Validate fields
    if not validate_contract_number(contract_number):
        raise ValueError(f"Invalid contract number format: {contract_number}")
    if not validate_contract_status(status):
        raise ValueError(f"Invalid contract status: {status}. Must be one of: {CONTRACT_STATUSES}")

    try:
        supabase = _get_supabase()

        # Convert date to string for JSON
        contract_date_str = contract_date.isoformat() if isinstance(contract_date, date) else contract_date

        result = supabase.table("customer_contracts").insert({
            "organization_id": organization_id,
            "customer_id": customer_id,
            "contract_number": contract_number,
            "contract_date": contract_date_str,
            "status": status,
            "notes": notes,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_contract(result.data[0])
        return None

    except Exception as e:
        error_str = str(e)
        if "uq_customer_contracts_org_number" in error_str or "duplicate" in error_str.lower():
            raise ValueError(f"Contract number '{contract_number}' already exists in this organization")
        print(f"Error creating contract: {e}")
        return None


# =============================================================================
# READ OPERATIONS
# =============================================================================

def get_contract(contract_id: str) -> Optional[CustomerContract]:
    """
    Get a contract by ID.

    Args:
        contract_id: Contract UUID

    Returns:
        CustomerContract object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contracts").select("*").eq("id", contract_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_contract(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting contract: {e}")
        return None


def get_contract_with_customer(contract_id: str) -> Optional[CustomerContract]:
    """
    Get a contract with customer name.

    Args:
        contract_id: Contract UUID

    Returns:
        CustomerContract object with customer_name populated, None if not found
    """
    try:
        supabase = _get_supabase()

        # Join with customers table to get customer name
        result = supabase.table("customer_contracts").select(
            "*, customers(name)"
        ).eq("id", contract_id).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            # Extract customer name from nested object
            if row.get("customers"):
                row["customer_name"] = row["customers"].get("name")
            return _parse_contract(row)
        return None

    except Exception as e:
        print(f"Error getting contract with customer: {e}")
        return None


def get_contract_by_number(organization_id: str, contract_number: str) -> Optional[CustomerContract]:
    """
    Get a contract by number within an organization.

    Args:
        organization_id: Organization UUID
        contract_number: Contract number

    Returns:
        CustomerContract object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contracts").select("*")\
            .eq("organization_id", organization_id)\
            .eq("contract_number", contract_number)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_contract(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting contract by number: {e}")
        return None


def get_contracts_for_customer(
    customer_id: str,
    *,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[CustomerContract]:
    """
    Get all contracts for a customer.

    Args:
        customer_id: Customer UUID
        status: Filter by status (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of CustomerContract objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("customer_contracts").select("*")\
            .eq("customer_id", customer_id)\
            .order("contract_date", desc=True)

        if status is not None:
            query = query.eq("status", status)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_contract(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting contracts for customer: {e}")
        return []


def get_active_contracts_for_customer(customer_id: str) -> List[CustomerContract]:
    """
    Get all active contracts for a customer.

    Convenience function for dropdown lists.

    Args:
        customer_id: Customer UUID

    Returns:
        List of active CustomerContract objects
    """
    return get_contracts_for_customer(customer_id, status="active", limit=1000)


def get_all_contracts(
    organization_id: str,
    *,
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[CustomerContract]:
    """
    Get all contracts for an organization.

    Args:
        organization_id: Organization UUID
        status: Filter by status (None = all)
        customer_id: Filter by customer (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of CustomerContract objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("customer_contracts").select("*")\
            .eq("organization_id", organization_id)\
            .order("contract_date", desc=True)

        if status is not None:
            query = query.eq("status", status)

        if customer_id is not None:
            query = query.eq("customer_id", customer_id)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_contract(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all contracts: {e}")
        return []


def get_contracts_with_customer_names(
    organization_id: str,
    *,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[CustomerContract]:
    """
    Get contracts with customer names for display.

    Args:
        organization_id: Organization UUID
        status: Filter by status (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of CustomerContract objects with customer_name populated
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("customer_contracts").select(
            "*, customers(name)"
        ).eq("organization_id", organization_id)\
            .order("contract_date", desc=True)

        if status is not None:
            query = query.eq("status", status)

        result = query.range(offset, offset + limit - 1).execute()

        if not result.data:
            return []

        contracts = []
        for row in result.data:
            if row.get("customers"):
                row["customer_name"] = row["customers"].get("name")
            contracts.append(_parse_contract(row))

        return contracts

    except Exception as e:
        print(f"Error getting contracts with customer names: {e}")
        return []


def count_contracts(
    organization_id: str,
    *,
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> int:
    """
    Count contracts in an organization.

    Args:
        organization_id: Organization UUID
        status: Filter by status
        customer_id: Filter by customer

    Returns:
        Number of contracts
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("customer_contracts").select("id", count="exact")\
            .eq("organization_id", organization_id)

        if status is not None:
            query = query.eq("status", status)

        if customer_id is not None:
            query = query.eq("customer_id", customer_id)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting contracts: {e}")
        return 0


def search_contracts(
    organization_id: str,
    query: str,
    *,
    status: Optional[str] = "active",
    customer_id: Optional[str] = None,
    limit: int = 20,
) -> List[CustomerContract]:
    """
    Search contracts by contract number.

    Used for HTMX dropdown autocomplete.

    Args:
        organization_id: Organization UUID
        query: Search query (matches contract_number)
        status: Filter by status
        customer_id: Filter by customer
        limit: Maximum number of results

    Returns:
        List of matching CustomerContract objects
    """
    if not query or len(query) < 1:
        return []

    try:
        supabase = _get_supabase()

        search_pattern = f"%{query}%"

        base_query = supabase.table("customer_contracts").select("*")\
            .eq("organization_id", organization_id)

        if status is not None:
            base_query = base_query.eq("status", status)

        if customer_id is not None:
            base_query = base_query.eq("customer_id", customer_id)

        result = base_query.ilike("contract_number", search_pattern)\
            .order("contract_date", desc=True)\
            .limit(limit)\
            .execute()

        return [_parse_contract(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error searching contracts: {e}")
        return []


def contract_exists(organization_id: str, contract_number: str) -> bool:
    """
    Check if a contract with given number exists.

    Args:
        organization_id: Organization UUID
        contract_number: Contract number to check

    Returns:
        True if contract exists, False otherwise
    """
    return get_contract_by_number(organization_id, contract_number) is not None


# =============================================================================
# UPDATE OPERATIONS
# =============================================================================

def update_contract(
    contract_id: str,
    *,
    contract_number: Optional[str] = None,
    contract_date: Optional[date] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[CustomerContract]:
    """
    Update a contract.

    Args:
        contract_id: Contract UUID
        contract_number: New contract number
        contract_date: New contract date
        status: New status
        notes: New notes

    Returns:
        Updated CustomerContract object if successful, None otherwise

    Raises:
        ValueError: If validation fails
    """
    # Validate fields if provided
    if contract_number is not None and not validate_contract_number(contract_number):
        raise ValueError(f"Invalid contract number format: {contract_number}")
    if status is not None and not validate_contract_status(status):
        raise ValueError(f"Invalid contract status: {status}. Must be one of: {CONTRACT_STATUSES}")

    try:
        supabase = _get_supabase()

        # Build update dict with only provided fields
        update_data = {}
        if contract_number is not None:
            update_data["contract_number"] = contract_number
        if contract_date is not None:
            update_data["contract_date"] = contract_date.isoformat() if isinstance(contract_date, date) else contract_date
        if status is not None:
            update_data["status"] = status
        if notes is not None:
            update_data["notes"] = notes

        if not update_data:
            # Nothing to update, return current state
            return get_contract(contract_id)

        result = supabase.table("customer_contracts").update(update_data)\
            .eq("id", contract_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_contract(result.data[0])
        return None

    except Exception as e:
        error_str = str(e)
        if "uq_customer_contracts_org_number" in error_str or "duplicate" in error_str.lower():
            raise ValueError(f"Contract number '{contract_number}' already exists in this organization")
        print(f"Error updating contract: {e}")
        return None


def suspend_contract(contract_id: str) -> Optional[CustomerContract]:
    """
    Suspend a contract.

    Args:
        contract_id: Contract UUID

    Returns:
        Updated CustomerContract object
    """
    return update_contract(contract_id, status="suspended")


def terminate_contract(contract_id: str) -> Optional[CustomerContract]:
    """
    Terminate a contract.

    Args:
        contract_id: Contract UUID

    Returns:
        Updated CustomerContract object
    """
    return update_contract(contract_id, status="terminated")


def activate_contract(contract_id: str) -> Optional[CustomerContract]:
    """
    Reactivate a suspended/terminated contract.

    Args:
        contract_id: Contract UUID

    Returns:
        Updated CustomerContract object
    """
    return update_contract(contract_id, status="active")


# =============================================================================
# SPECIFICATION NUMBERING
# =============================================================================

def get_next_specification_number(contract_id: str) -> Optional[int]:
    """
    Get and increment the next specification number for a contract.

    This atomically increments the counter and returns the number to use.
    Uses the database function get_next_specification_number().

    Args:
        contract_id: Contract UUID

    Returns:
        Next specification number to use, or None on error
    """
    try:
        supabase = _get_supabase()

        # Call the database function
        result = supabase.rpc("get_next_specification_number", {
            "p_contract_id": contract_id
        }).execute()

        if result.data is not None:
            return result.data
        return None

    except Exception as e:
        print(f"Error getting next specification number: {e}")
        return None


def get_current_specification_number(contract_id: str) -> int:
    """
    Get current next_specification_number without incrementing.

    Args:
        contract_id: Contract UUID

    Returns:
        Current next_specification_number value
    """
    contract = get_contract(contract_id)
    if contract:
        return contract.next_specification_number
    return 1


def reset_specification_number(contract_id: str, new_value: int = 1) -> Optional[CustomerContract]:
    """
    Reset the specification number counter.

    WARNING: Use with caution. Only for admin operations.

    Args:
        contract_id: Contract UUID
        new_value: New counter value (default: 1)

    Returns:
        Updated CustomerContract object
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contracts").update({
            "next_specification_number": new_value
        }).eq("id", contract_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_contract(result.data[0])
        return None

    except Exception as e:
        print(f"Error resetting specification number: {e}")
        return None


# =============================================================================
# DELETE OPERATIONS
# =============================================================================

def delete_contract(contract_id: str) -> bool:
    """
    Delete a contract permanently.

    Note: Consider using terminate_contract() instead.
    Warning: This will fail if specifications reference this contract.

    Args:
        contract_id: Contract UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contracts").delete().eq("id", contract_id).execute()

        return True

    except Exception as e:
        print(f"Error deleting contract: {e}")
        return False


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_contract_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get contract statistics for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total: Total number of contracts
        - active: Number of active contracts
        - suspended: Number of suspended contracts
        - terminated: Number of terminated contracts
        - by_customer_count: Number of unique customers with contracts
    """
    try:
        supabase = _get_supabase()

        # Get all contracts
        result = supabase.table("customer_contracts").select("status, customer_id")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return {
                "total": 0,
                "active": 0,
                "suspended": 0,
                "terminated": 0,
                "by_customer_count": 0,
            }

        total = len(result.data)
        active = sum(1 for row in result.data if row.get("status") == "active")
        suspended = sum(1 for row in result.data if row.get("status") == "suspended")
        terminated = sum(1 for row in result.data if row.get("status") == "terminated")
        unique_customers = len(set(row["customer_id"] for row in result.data))

        return {
            "total": total,
            "active": active,
            "suspended": suspended,
            "terminated": terminated,
            "by_customer_count": unique_customers,
        }

    except Exception as e:
        print(f"Error getting contract stats: {e}")
        return {
            "total": 0,
            "active": 0,
            "suspended": 0,
            "terminated": 0,
            "by_customer_count": 0,
        }


def get_contract_display_name(contract: CustomerContract) -> str:
    """
    Get display name for a contract.

    Args:
        contract: CustomerContract object

    Returns:
        Display string like "ДП-001/2025 от 15.01.2025"
    """
    date_str = contract.contract_date.strftime("%d.%m.%Y") if contract.contract_date else ""
    return f"{contract.contract_number} от {date_str}"


def format_contract_for_dropdown(contract: CustomerContract) -> Dict[str, str]:
    """
    Format contract for HTMX dropdown option.

    Args:
        contract: CustomerContract object

    Returns:
        Dict with 'value' (id) and 'label' (display name)
    """
    return {
        "value": contract.id,
        "label": get_contract_display_name(contract),
    }


def get_contracts_for_dropdown(
    customer_id: str,
    *,
    query: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Get contracts formatted for dropdown/select element.

    Args:
        customer_id: Customer UUID
        query: Optional search query
        limit: Maximum results

    Returns:
        List of dicts with 'value' and 'label' for dropdown options
    """
    # Get organization_id from customer first
    try:
        supabase = _get_supabase()
        customer_result = supabase.table("customers").select("organization_id")\
            .eq("id", customer_id)\
            .limit(1)\
            .execute()

        if not customer_result.data:
            return []

        organization_id = customer_result.data[0]["organization_id"]

        if query:
            contracts = search_contracts(
                organization_id,
                query,
                status="active",
                customer_id=customer_id,
                limit=limit
            )
        else:
            contracts = get_active_contracts_for_customer(customer_id)[:limit]

        return [format_contract_for_dropdown(c) for c in contracts]

    except Exception as e:
        print(f"Error getting contracts for dropdown: {e}")
        return []


def get_contract_for_specification(contract_id: str) -> Optional[Dict[str, Any]]:
    """
    Get contract information for specification generation.

    Returns contract details needed for specification PDF header.

    Args:
        contract_id: Contract UUID

    Returns:
        Dict with contract info for specification, or None if not found
    """
    contract = get_contract_with_customer(contract_id)
    if not contract:
        return None

    return {
        "contract_number": contract.contract_number,
        "contract_date": contract.contract_date.strftime("%d.%m.%Y") if contract.contract_date else "",
        "contract_date_long": _format_date_long(contract.contract_date) if contract.contract_date else "",
        "customer_name": contract.customer_name or "",
        "full_reference": f"Договор №{contract.contract_number} от {contract.contract_date.strftime('%d.%m.%Y')}" if contract.contract_date else f"Договор №{contract.contract_number}",
    }


def _format_date_long(d: date) -> str:
    """
    Format date in long Russian format.

    Args:
        d: Date object

    Returns:
        String like "15 января 2025 г."
    """
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    return f"{d.day} {months[d.month - 1]} {d.year} г."
