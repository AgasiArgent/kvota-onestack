"""
Buyer Company Service - CRUD operations for buyer_companies table

This module provides functions for managing our legal entities used for purchasing:
- Create/Update/Delete buyer companies
- Query buyer companies by organization, code
- Search buyer companies for HTMX dropdowns
- Utility functions for buyer company management

Based on app_spec.xml buyer_companies table definition (Feature API-002).

Supply chain level: ITEM (each quote_item can have its own buyer company)

Buyer companies are OUR legal entities through which we purchase goods from suppliers.
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
class BuyerCompany:
    """
    Represents a buyer company record.

    Our legal entity used for purchasing goods from suppliers.
    Maps to buyer_companies table in database.
    """
    id: str
    organization_id: str
    name: str
    company_code: str  # 3-letter code (e.g., ZAK, CMT)

    # Location
    country: Optional[str] = None

    # Legal identifiers (Russian legal entity)
    inn: Optional[str] = None  # ИНН (10 digits for legal entities)
    kpp: Optional[str] = None  # КПП (9 digits)
    ogrn: Optional[str] = None  # ОГРН (13 digits)

    # Registration address
    registration_address: Optional[str] = None

    # Director information (for contracts/documents)
    general_director_name: Optional[str] = None
    general_director_position: Optional[str] = "Генеральный директор"

    # Status
    is_active: bool = True

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


def _parse_buyer_company(data: dict) -> BuyerCompany:
    """Parse database row into BuyerCompany object."""
    return BuyerCompany(
        id=data["id"],
        organization_id=data["organization_id"],
        name=data["name"],
        company_code=data["company_code"],
        country=data.get("country"),
        inn=data.get("inn"),
        kpp=data.get("kpp"),
        ogrn=data.get("ogrn"),
        registration_address=data.get("registration_address"),
        general_director_name=data.get("general_director_name"),
        general_director_position=data.get("general_director_position", "Генеральный директор"),
        is_active=data.get("is_active", True),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        created_by=data.get("created_by"),
    )


def _buyer_company_to_dict(company: BuyerCompany) -> dict:
    """Convert BuyerCompany object to dict for database operations."""
    return {
        "organization_id": company.organization_id,
        "name": company.name,
        "company_code": company.company_code,
        "country": company.country,
        "inn": company.inn,
        "kpp": company.kpp,
        "ogrn": company.ogrn,
        "registration_address": company.registration_address,
        "general_director_name": company.general_director_name,
        "general_director_position": company.general_director_position,
        "is_active": company.is_active,
        "created_by": company.created_by,
    }


# =============================================================================
# VALIDATION
# =============================================================================

def validate_company_code(code: str) -> bool:
    """
    Validate company code format (3 uppercase letters).

    Args:
        code: Company code to validate

    Returns:
        True if valid, False otherwise
    """
    if not code:
        return False
    return bool(re.match(r'^[A-Z]{3}$', code))


def validate_inn(inn: str) -> bool:
    """
    Validate Russian INN format for legal entities.

    Args:
        inn: INN to validate (10 digits for legal entities)

    Returns:
        True if valid format, False otherwise
    """
    if not inn:
        return True  # INN is optional
    # Russian legal entity INN is 10 digits
    return bool(re.match(r'^\d{10}$', inn))


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


def validate_ogrn(ogrn: str) -> bool:
    """
    Validate Russian OGRN format.

    Args:
        ogrn: OGRN to validate (13 digits for legal entities)

    Returns:
        True if valid format, False otherwise
    """
    if not ogrn:
        return True  # OGRN is optional
    # OGRN is 13 digits for legal entities
    return bool(re.match(r'^\d{13}$', ogrn))


# =============================================================================
# CREATE Operations
# =============================================================================

def create_buyer_company(
    organization_id: str,
    name: str,
    company_code: str,
    *,
    country: Optional[str] = None,
    inn: Optional[str] = None,
    kpp: Optional[str] = None,
    ogrn: Optional[str] = None,
    registration_address: Optional[str] = None,
    general_director_name: Optional[str] = None,
    general_director_position: Optional[str] = "Генеральный директор",
    is_active: bool = True,
    created_by: Optional[str] = None,
) -> Optional[BuyerCompany]:
    """
    Create a new buyer company.

    Args:
        organization_id: Organization UUID
        name: Company legal name
        company_code: 3-letter unique code (e.g., ZAK)
        country: Company country (typically Russia)
        inn: Russian tax ID (ИНН) - 10 digits
        kpp: Russian tax registration code (КПП) - 9 digits
        ogrn: Russian state registration number (ОГРН) - 13 digits
        registration_address: Legal registration address
        general_director_name: Director name for document signing
        general_director_position: Director position title
        is_active: Whether company is active
        created_by: User UUID who created this company

    Returns:
        BuyerCompany object if successful, None if company code already exists

    Raises:
        ValueError: If any validation fails

    Example:
        company = create_buyer_company(
            organization_id="org-uuid",
            name="ООО Закупка",
            company_code="ZAK",
            country="Россия",
            inn="7712345678",
            kpp="771201001",
            general_director_name="Иванов Иван Иванович",
            created_by="admin-uuid"
        )
    """
    # Validate company code format
    if not validate_company_code(company_code):
        raise ValueError(f"Invalid company code format: {company_code}. Must be 3 uppercase letters.")

    # Validate Russian legal identifiers
    if inn and not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}. Must be 10 digits for legal entities.")
    if kpp and not validate_kpp(kpp):
        raise ValueError(f"Invalid KPP format: {kpp}. Must be 9 digits.")
    if ogrn and not validate_ogrn(ogrn):
        raise ValueError(f"Invalid OGRN format: {ogrn}. Must be 13 digits for legal entities.")

    try:
        supabase = _get_supabase()

        result = supabase.table("buyer_companies").insert({
            "organization_id": organization_id,
            "name": name,
            "company_code": company_code,
            "country": country,
            "inn": inn,
            "kpp": kpp,
            "ogrn": ogrn,
            "registration_address": registration_address,
            "general_director_name": general_director_name,
            "general_director_position": general_director_position,
            "is_active": is_active,
            "created_by": created_by,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_buyer_company(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation (company code already exists)
        if "idx_buyer_companies_org_code" in str(e) or "duplicate key" in str(e).lower():
            return None
        raise


# =============================================================================
# READ Operations
# =============================================================================

def get_buyer_company(company_id: str) -> Optional[BuyerCompany]:
    """
    Get a buyer company by ID.

    Args:
        company_id: Buyer company UUID

    Returns:
        BuyerCompany object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("buyer_companies").select("*").eq("id", company_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_buyer_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting buyer company: {e}")
        return None


def get_buyer_company_by_code(organization_id: str, company_code: str) -> Optional[BuyerCompany]:
    """
    Get a buyer company by its code within an organization.

    Args:
        organization_id: Organization UUID
        company_code: 3-letter company code

    Returns:
        BuyerCompany object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("buyer_companies").select("*")\
            .eq("organization_id", organization_id)\
            .eq("company_code", company_code)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_buyer_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting buyer company by code: {e}")
        return None


def get_buyer_company_by_inn(organization_id: str, inn: str) -> Optional[BuyerCompany]:
    """
    Get a buyer company by its INN within an organization.

    Args:
        organization_id: Organization UUID
        inn: Russian tax ID (10 digits)

    Returns:
        BuyerCompany object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("buyer_companies").select("*")\
            .eq("organization_id", organization_id)\
            .eq("inn", inn)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_buyer_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting buyer company by INN: {e}")
        return None


def get_all_buyer_companies(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[BuyerCompany]:
    """
    Get all buyer companies for an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of BuyerCompany objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("buyer_companies").select("*")\
            .eq("organization_id", organization_id)\
            .order("name")

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_buyer_company(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all buyer companies: {e}")
        return []


def count_buyer_companies(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
) -> int:
    """
    Count buyer companies in an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status

    Returns:
        Number of buyer companies
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("buyer_companies").select("id", count="exact")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting buyer companies: {e}")
        return 0


def search_buyer_companies(
    organization_id: str,
    query: str,
    *,
    is_active: Optional[bool] = True,
    limit: int = 20,
) -> List[BuyerCompany]:
    """
    Search buyer companies by name, code, INN, or director name.

    Used for HTMX dropdown autocomplete.

    Args:
        organization_id: Organization UUID
        query: Search query (matches name, company_code, inn, general_director_name)
        is_active: Filter by active status
        limit: Maximum number of results

    Returns:
        List of matching BuyerCompany objects

    Example:
        # Search for buyer companies containing "закупка" in name
        companies = search_buyer_companies("org-uuid", "закупка", limit=10)
    """
    if not query or len(query) < 1:
        return []

    try:
        supabase = _get_supabase()

        # Use ilike for case-insensitive search
        search_pattern = f"%{query}%"

        # Build query with OR conditions for multiple fields
        base_query = supabase.table("buyer_companies").select("*")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            base_query = base_query.eq("is_active", is_active)

        # Search in name (primary)
        result = base_query.ilike("name", search_pattern)\
            .order("name")\
            .limit(limit)\
            .execute()

        companies = [_parse_buyer_company(row) for row in result.data] if result.data else []

        # If not enough results, also search by code
        if len(companies) < limit:
            code_query = supabase.table("buyer_companies").select("*")\
                .eq("organization_id", organization_id)\
                .ilike("company_code", search_pattern)

            if is_active is not None:
                code_query = code_query.eq("is_active", is_active)

            code_result = code_query.limit(limit - len(companies)).execute()

            if code_result.data:
                existing_ids = {c.id for c in companies}
                for row in code_result.data:
                    if row["id"] not in existing_ids:
                        companies.append(_parse_buyer_company(row))

        # If still not enough, search by INN
        if len(companies) < limit and query.isdigit():
            inn_query = supabase.table("buyer_companies").select("*")\
                .eq("organization_id", organization_id)\
                .ilike("inn", search_pattern)

            if is_active is not None:
                inn_query = inn_query.eq("is_active", is_active)

            inn_result = inn_query.limit(limit - len(companies)).execute()

            if inn_result.data:
                existing_ids = {c.id for c in companies}
                for row in inn_result.data:
                    if row["id"] not in existing_ids:
                        companies.append(_parse_buyer_company(row))

        return companies

    except Exception as e:
        print(f"Error searching buyer companies: {e}")
        return []


def get_active_buyer_companies(organization_id: str) -> List[BuyerCompany]:
    """
    Get all active buyer companies for an organization.

    Convenience function for dropdown lists.

    Args:
        organization_id: Organization UUID

    Returns:
        List of active BuyerCompany objects
    """
    return get_all_buyer_companies(organization_id, is_active=True, limit=1000)


def buyer_company_exists(organization_id: str, company_code: str) -> bool:
    """
    Check if a buyer company with given code exists.

    Args:
        organization_id: Organization UUID
        company_code: Company code to check

    Returns:
        True if buyer company exists, False otherwise
    """
    return get_buyer_company_by_code(organization_id, company_code) is not None


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_buyer_company(
    company_id: str,
    *,
    name: Optional[str] = None,
    company_code: Optional[str] = None,
    country: Optional[str] = None,
    inn: Optional[str] = None,
    kpp: Optional[str] = None,
    ogrn: Optional[str] = None,
    registration_address: Optional[str] = None,
    general_director_name: Optional[str] = None,
    general_director_position: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[BuyerCompany]:
    """
    Update a buyer company.

    Args:
        company_id: Buyer company UUID
        name: New company name
        company_code: New company code (must be unique)
        country: New country
        inn: New INN (10 digits)
        kpp: New KPP (9 digits)
        ogrn: New OGRN (13 digits)
        registration_address: New registration address
        general_director_name: New director name
        general_director_position: New director position
        is_active: New active status

    Returns:
        Updated BuyerCompany object if successful, None otherwise

    Raises:
        ValueError: If any validation fails
    """
    # Validate company code if provided
    if company_code is not None and not validate_company_code(company_code):
        raise ValueError(f"Invalid company code format: {company_code}. Must be 3 uppercase letters.")

    # Validate Russian identifiers if provided
    if inn is not None and inn and not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}. Must be 10 digits for legal entities.")
    if kpp is not None and kpp and not validate_kpp(kpp):
        raise ValueError(f"Invalid KPP format: {kpp}. Must be 9 digits.")
    if ogrn is not None and ogrn and not validate_ogrn(ogrn):
        raise ValueError(f"Invalid OGRN format: {ogrn}. Must be 13 digits for legal entities.")

    try:
        supabase = _get_supabase()

        # Build update dict with only provided fields
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if company_code is not None:
            update_data["company_code"] = company_code
        if country is not None:
            update_data["country"] = country
        if inn is not None:
            update_data["inn"] = inn
        if kpp is not None:
            update_data["kpp"] = kpp
        if ogrn is not None:
            update_data["ogrn"] = ogrn
        if registration_address is not None:
            update_data["registration_address"] = registration_address
        if general_director_name is not None:
            update_data["general_director_name"] = general_director_name
        if general_director_position is not None:
            update_data["general_director_position"] = general_director_position
        if is_active is not None:
            update_data["is_active"] = is_active

        if not update_data:
            # Nothing to update, return current state
            return get_buyer_company(company_id)

        result = supabase.table("buyer_companies").update(update_data)\
            .eq("id", company_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_buyer_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating buyer company: {e}")
        return None


def activate_buyer_company(company_id: str) -> Optional[BuyerCompany]:
    """
    Activate a buyer company.

    Args:
        company_id: Buyer company UUID

    Returns:
        Updated BuyerCompany object
    """
    return update_buyer_company(company_id, is_active=True)


def deactivate_buyer_company(company_id: str) -> Optional[BuyerCompany]:
    """
    Deactivate a buyer company (soft delete).

    Args:
        company_id: Buyer company UUID

    Returns:
        Updated BuyerCompany object
    """
    return update_buyer_company(company_id, is_active=False)


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_buyer_company(company_id: str) -> bool:
    """
    Delete a buyer company permanently.

    Note: Consider using deactivate_buyer_company() instead for soft delete.

    Args:
        company_id: Buyer company UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("buyer_companies").delete()\
            .eq("id", company_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting buyer company: {e}")
        return False


# =============================================================================
# UTILITY Functions
# =============================================================================

def get_buyer_company_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get buyer company statistics for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total: Total number of buyer companies
        - active: Number of active buyer companies
        - inactive: Number of inactive buyer companies
        - with_inn: Number with INN registered
        - with_director: Number with director name set
    """
    try:
        supabase = _get_supabase()

        # Get all buyer companies
        result = supabase.table("buyer_companies").select("is_active, inn, general_director_name")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "with_inn": 0,
                "with_director": 0,
            }

        total = len(result.data)
        active = sum(1 for row in result.data if row.get("is_active", True))
        inactive = total - active
        with_inn = sum(1 for row in result.data if row.get("inn"))
        with_director = sum(1 for row in result.data if row.get("general_director_name"))

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "with_inn": with_inn,
            "with_director": with_director,
        }

    except Exception as e:
        print(f"Error getting buyer company stats: {e}")
        return {
            "total": 0,
            "active": 0,
            "inactive": 0,
            "with_inn": 0,
            "with_director": 0,
        }


def get_buyer_company_display_name(company: BuyerCompany) -> str:
    """
    Get display name for a buyer company (code + name).

    Args:
        company: BuyerCompany object

    Returns:
        Display string like "ZAK - ООО Закупка"
    """
    return f"{company.company_code} - {company.name}"


def format_buyer_company_for_dropdown(company: BuyerCompany) -> Dict[str, str]:
    """
    Format buyer company for HTMX dropdown option.

    Args:
        company: BuyerCompany object

    Returns:
        Dict with 'value' (id) and 'label' (display name)
    """
    inn_str = ""
    if company.inn:
        inn_str = f" (ИНН: {company.inn})"

    return {
        "value": company.id,
        "label": f"{company.company_code} - {company.name}{inn_str}",
    }


def get_buyer_companies_for_dropdown(
    organization_id: str,
    *,
    query: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Get buyer companies formatted for dropdown/select element.

    Args:
        organization_id: Organization UUID
        query: Optional search query
        limit: Maximum results

    Returns:
        List of dicts with 'value' and 'label' for dropdown options
    """
    if query:
        companies = search_buyer_companies(organization_id, query, limit=limit)
    else:
        companies = get_active_buyer_companies(organization_id)[:limit]

    return [format_buyer_company_for_dropdown(c) for c in companies]


def get_buyer_company_for_document(company_id: str) -> Optional[Dict[str, Any]]:
    """
    Get buyer company information formatted for document generation.

    Returns all fields needed for contracts, invoices, and official documents.

    Args:
        company_id: Buyer company UUID

    Returns:
        Dict with formatted company info for documents, or None if not found
    """
    company = get_buyer_company(company_id)
    if not company:
        return None

    return {
        "name": company.name,
        "code": company.company_code,
        "inn": company.inn or "",
        "kpp": company.kpp or "",
        "ogrn": company.ogrn or "",
        "address": company.registration_address or "",
        "director_name": company.general_director_name or "",
        "director_position": company.general_director_position or "Генеральный директор",
        "full_requisites": _format_full_requisites(company),
    }


def _format_full_requisites(company: BuyerCompany) -> str:
    """
    Format full company requisites for official documents.

    Args:
        company: BuyerCompany object

    Returns:
        Formatted string with all company requisites
    """
    lines = [company.name]

    if company.registration_address:
        lines.append(f"Адрес: {company.registration_address}")

    if company.inn:
        if company.kpp:
            lines.append(f"ИНН/КПП: {company.inn}/{company.kpp}")
        else:
            lines.append(f"ИНН: {company.inn}")

    if company.ogrn:
        lines.append(f"ОГРН: {company.ogrn}")

    return "\n".join(lines)
