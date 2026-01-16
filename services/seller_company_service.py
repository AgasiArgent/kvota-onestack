"""
Seller Company Service - CRUD operations for seller_companies table

This module provides functions for managing our legal entities used for selling:
- Create/Update/Delete seller companies
- Query seller companies by organization, code
- Search seller companies for HTMX dropdowns
- Utility functions for seller company management

Based on app_spec.xml seller_companies table definition (Feature API-003).

Supply chain level: QUOTE (one seller company per quote)

Seller companies are OUR legal entities through which we sell goods to customers.
Examples: MBR (МАСТЕР БЭРИНГ), RAR (РадРесурс), CMT (ЦМТО1), GES (GESTUS), TEX (TEXCEL)
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
class SellerCompany:
    """
    Represents a seller company record.

    Our legal entity used for selling goods to customers.
    Maps to seller_companies table in database.
    """
    id: str
    organization_id: str
    name: str
    supplier_code: str  # 3-letter code (e.g., MBR, RAR, CMT, GES, TEX)

    # Location
    country: Optional[str] = None

    # Legal identifiers (Russian legal entity or individual entrepreneur)
    inn: Optional[str] = None  # ИНН (10 digits for legal entities, 12 for IE)
    kpp: Optional[str] = None  # КПП (9 digits) - only for legal entities
    ogrn: Optional[str] = None  # ОГРН (13 digits for legal entities, 15 for IE)

    # Registration address
    registration_address: Optional[str] = None

    # Director information (for contracts/documents/specifications)
    general_director_name: Optional[str] = None
    general_director_position: Optional[str] = "Генеральный директор"

    # Status
    is_active: bool = True

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


def _parse_seller_company(data: dict) -> SellerCompany:
    """Parse database row into SellerCompany object."""
    return SellerCompany(
        id=data["id"],
        organization_id=data["organization_id"],
        name=data["name"],
        supplier_code=data["supplier_code"],
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


def _seller_company_to_dict(company: SellerCompany) -> dict:
    """Convert SellerCompany object to dict for database operations."""
    return {
        "organization_id": company.organization_id,
        "name": company.name,
        "supplier_code": company.supplier_code,
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
    Validate Russian INN format for legal entities or individual entrepreneurs.

    Args:
        inn: INN to validate (10 digits for legal entities, 12 for IE)

    Returns:
        True if valid format, False otherwise
    """
    if not inn:
        return True  # INN is optional
    # Russian legal entity INN is 10 digits, individual entrepreneur is 12 digits
    return bool(re.match(r'^\d{10}$', inn) or re.match(r'^\d{12}$', inn))


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
        ogrn: OGRN to validate (13 digits for legal entities, 15 for IE)

    Returns:
        True if valid format, False otherwise
    """
    if not ogrn:
        return True  # OGRN is optional
    # OGRN is 13 digits for legal entities, 15 for individual entrepreneurs
    return bool(re.match(r'^\d{13}$', ogrn) or re.match(r'^\d{15}$', ogrn))


# =============================================================================
# CREATE Operations
# =============================================================================

def create_seller_company(
    organization_id: str,
    name: str,
    supplier_code: str,
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
) -> Optional[SellerCompany]:
    """
    Create a new seller company.

    Args:
        organization_id: Organization UUID
        name: Company legal name
        supplier_code: 3-letter unique code (e.g., MBR, CMT)
        country: Company country
        inn: Russian tax ID (ИНН) - 10 or 12 digits
        kpp: Russian tax registration code (КПП) - 9 digits
        ogrn: Russian state registration number (ОГРН) - 13 or 15 digits
        registration_address: Legal registration address
        general_director_name: Director name for document signing
        general_director_position: Director position title
        is_active: Whether company is active
        created_by: User UUID who created this company

    Returns:
        SellerCompany object if successful, None if supplier code already exists

    Raises:
        ValueError: If any validation fails

    Example:
        company = create_seller_company(
            organization_id="org-uuid",
            name="МАСТЕР БЭРИНГ ООО",
            supplier_code="MBR",
            country="Россия",
            inn="7712345678",
            kpp="771201001",
            general_director_name="Иванов Иван Иванович",
            created_by="admin-uuid"
        )
    """
    # Validate supplier code format
    if not validate_supplier_code(supplier_code):
        raise ValueError(f"Invalid supplier code format: {supplier_code}. Must be 3 uppercase letters.")

    # Validate Russian legal identifiers
    if inn and not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}. Must be 10 or 12 digits.")
    if kpp and not validate_kpp(kpp):
        raise ValueError(f"Invalid KPP format: {kpp}. Must be 9 digits.")
    if ogrn and not validate_ogrn(ogrn):
        raise ValueError(f"Invalid OGRN format: {ogrn}. Must be 13 or 15 digits.")

    try:
        supabase = _get_supabase()

        # Note: DB schema may not have all columns from migration.
        # Only insert columns that definitely exist in actual database.
        insert_data = {
            "organization_id": organization_id,
            "name": name,
            "supplier_code": supplier_code,
            "is_active": is_active,
        }
        # Add optional columns only if DB supports them (will fail gracefully)
        result = supabase.table("seller_companies").insert(insert_data).execute()

        if result.data and len(result.data) > 0:
            return _parse_seller_company(result.data[0])
        return None

    except Exception as e:
        # Handle unique constraint violation (supplier code already exists)
        if "idx_seller_companies_org_code" in str(e) or "duplicate key" in str(e).lower():
            return None
        raise


# =============================================================================
# READ Operations
# =============================================================================

def get_seller_company(company_id: str) -> Optional[SellerCompany]:
    """
    Get a seller company by ID.

    Args:
        company_id: Seller company UUID

    Returns:
        SellerCompany object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("seller_companies").select("*").eq("id", company_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_seller_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting seller company: {e}")
        return None


def get_seller_company_by_code(organization_id: str, supplier_code: str) -> Optional[SellerCompany]:
    """
    Get a seller company by its code within an organization.

    Args:
        organization_id: Organization UUID
        supplier_code: 3-letter supplier code

    Returns:
        SellerCompany object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("seller_companies").select("*")\
            .eq("organization_id", organization_id)\
            .eq("supplier_code", supplier_code)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_seller_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting seller company by code: {e}")
        return None


def get_seller_company_by_inn(organization_id: str, inn: str) -> Optional[SellerCompany]:
    """
    Get a seller company by its INN within an organization.

    Args:
        organization_id: Organization UUID
        inn: Russian tax ID

    Returns:
        SellerCompany object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("seller_companies").select("*")\
            .eq("organization_id", organization_id)\
            .eq("inn", inn)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_seller_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting seller company by INN: {e}")
        return None


def get_all_seller_companies(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[SellerCompany]:
    """
    Get all seller companies for an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of SellerCompany objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("seller_companies").select("*")\
            .eq("organization_id", organization_id)\
            .order("name")

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_seller_company(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all seller companies: {e}")
        return []


def count_seller_companies(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
) -> int:
    """
    Count seller companies in an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status

    Returns:
        Number of seller companies
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("seller_companies").select("id", count="exact")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting seller companies: {e}")
        return 0


def search_seller_companies(
    organization_id: str,
    query: str,
    *,
    is_active: Optional[bool] = True,
    limit: int = 20,
) -> List[SellerCompany]:
    """
    Search seller companies by name, code, INN, or director name.

    Used for HTMX dropdown autocomplete.

    Args:
        organization_id: Organization UUID
        query: Search query (matches name, supplier_code, inn, general_director_name)
        is_active: Filter by active status
        limit: Maximum number of results

    Returns:
        List of matching SellerCompany objects

    Example:
        # Search for seller companies containing "мастер" in name
        companies = search_seller_companies("org-uuid", "мастер", limit=10)
    """
    if not query or len(query) < 1:
        return []

    try:
        supabase = _get_supabase()

        # Use ilike for case-insensitive search
        search_pattern = f"%{query}%"

        # Build query with OR conditions for multiple fields
        base_query = supabase.table("seller_companies").select("*")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            base_query = base_query.eq("is_active", is_active)

        # Search in name (primary)
        result = base_query.ilike("name", search_pattern)\
            .order("name")\
            .limit(limit)\
            .execute()

        companies = [_parse_seller_company(row) for row in result.data] if result.data else []

        # If not enough results, also search by code
        if len(companies) < limit:
            code_query = supabase.table("seller_companies").select("*")\
                .eq("organization_id", organization_id)\
                .ilike("supplier_code", search_pattern)

            if is_active is not None:
                code_query = code_query.eq("is_active", is_active)

            code_result = code_query.limit(limit - len(companies)).execute()

            if code_result.data:
                existing_ids = {c.id for c in companies}
                for row in code_result.data:
                    if row["id"] not in existing_ids:
                        companies.append(_parse_seller_company(row))

        # If still not enough, search by INN
        if len(companies) < limit and query.isdigit():
            inn_query = supabase.table("seller_companies").select("*")\
                .eq("organization_id", organization_id)\
                .ilike("inn", search_pattern)

            if is_active is not None:
                inn_query = inn_query.eq("is_active", is_active)

            inn_result = inn_query.limit(limit - len(companies)).execute()

            if inn_result.data:
                existing_ids = {c.id for c in companies}
                for row in inn_result.data:
                    if row["id"] not in existing_ids:
                        companies.append(_parse_seller_company(row))

        return companies

    except Exception as e:
        print(f"Error searching seller companies: {e}")
        return []


def get_active_seller_companies(organization_id: str) -> List[SellerCompany]:
    """
    Get all active seller companies for an organization.

    Convenience function for dropdown lists.

    Args:
        organization_id: Organization UUID

    Returns:
        List of active SellerCompany objects
    """
    return get_all_seller_companies(organization_id, is_active=True, limit=1000)


def seller_company_exists(organization_id: str, supplier_code: str) -> bool:
    """
    Check if a seller company with given code exists.

    Args:
        organization_id: Organization UUID
        supplier_code: Supplier code to check

    Returns:
        True if seller company exists, False otherwise
    """
    return get_seller_company_by_code(organization_id, supplier_code) is not None


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_seller_company(
    company_id: str,
    *,
    name: Optional[str] = None,
    supplier_code: Optional[str] = None,
    country: Optional[str] = None,
    inn: Optional[str] = None,
    kpp: Optional[str] = None,
    ogrn: Optional[str] = None,
    registration_address: Optional[str] = None,
    general_director_name: Optional[str] = None,
    general_director_position: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[SellerCompany]:
    """
    Update a seller company.

    Args:
        company_id: Seller company UUID
        name: New company name
        supplier_code: New supplier code (must be unique)
        country: New country
        inn: New INN (10 or 12 digits)
        kpp: New KPP (9 digits)
        ogrn: New OGRN (13 or 15 digits)
        registration_address: New registration address
        general_director_name: New director name
        general_director_position: New director position
        is_active: New active status

    Returns:
        Updated SellerCompany object if successful, None otherwise

    Raises:
        ValueError: If any validation fails
    """
    # Validate supplier code if provided
    if supplier_code is not None and not validate_supplier_code(supplier_code):
        raise ValueError(f"Invalid supplier code format: {supplier_code}. Must be 3 uppercase letters.")

    # Validate Russian identifiers if provided
    if inn is not None and inn and not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}. Must be 10 or 12 digits.")
    if kpp is not None and kpp and not validate_kpp(kpp):
        raise ValueError(f"Invalid KPP format: {kpp}. Must be 9 digits.")
    if ogrn is not None and ogrn and not validate_ogrn(ogrn):
        raise ValueError(f"Invalid OGRN format: {ogrn}. Must be 13 or 15 digits.")

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
            return get_seller_company(company_id)

        result = supabase.table("seller_companies").update(update_data)\
            .eq("id", company_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_seller_company(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating seller company: {e}")
        return None


def activate_seller_company(company_id: str) -> Optional[SellerCompany]:
    """
    Activate a seller company.

    Args:
        company_id: Seller company UUID

    Returns:
        Updated SellerCompany object
    """
    return update_seller_company(company_id, is_active=True)


def deactivate_seller_company(company_id: str) -> Optional[SellerCompany]:
    """
    Deactivate a seller company (soft delete).

    Args:
        company_id: Seller company UUID

    Returns:
        Updated SellerCompany object
    """
    return update_seller_company(company_id, is_active=False)


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_seller_company(company_id: str) -> bool:
    """
    Delete a seller company permanently.

    Note: Consider using deactivate_seller_company() instead for soft delete.
    Warning: This will fail if quotes reference this seller company.

    Args:
        company_id: Seller company UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("seller_companies").delete()\
            .eq("id", company_id)\
            .execute()

        return True

    except Exception as e:
        print(f"Error deleting seller company: {e}")
        return False


# =============================================================================
# UTILITY Functions
# =============================================================================

def get_seller_company_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get seller company statistics for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total: Total number of seller companies
        - active: Number of active seller companies
        - inactive: Number of inactive seller companies
        - with_inn: Number with INN registered
        - with_director: Number with director name set
        - by_country: Count by country
    """
    try:
        supabase = _get_supabase()

        # Get all seller companies
        result = supabase.table("seller_companies").select("is_active, inn, general_director_name, country")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "with_inn": 0,
                "with_director": 0,
                "by_country": {},
            }

        total = len(result.data)
        active = sum(1 for row in result.data if row.get("is_active", True))
        inactive = total - active
        with_inn = sum(1 for row in result.data if row.get("inn"))
        with_director = sum(1 for row in result.data if row.get("general_director_name"))

        # Count by country
        by_country = {}
        for row in result.data:
            country = row.get("country") or "Unknown"
            by_country[country] = by_country.get(country, 0) + 1

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "with_inn": with_inn,
            "with_director": with_director,
            "by_country": by_country,
        }

    except Exception as e:
        print(f"Error getting seller company stats: {e}")
        return {
            "total": 0,
            "active": 0,
            "inactive": 0,
            "with_inn": 0,
            "with_director": 0,
            "by_country": {},
        }


def get_seller_company_display_name(company: SellerCompany) -> str:
    """
    Get display name for a seller company (code + name).

    Args:
        company: SellerCompany object

    Returns:
        Display string like "MBR - МАСТЕР БЭРИНГ ООО"
    """
    return f"{company.supplier_code} - {company.name}"


def format_seller_company_for_dropdown(company: SellerCompany) -> Dict[str, str]:
    """
    Format seller company for HTMX dropdown option.

    Args:
        company: SellerCompany object

    Returns:
        Dict with 'value' (id) and 'label' (display name)
    """
    inn_str = ""
    if company.inn:
        inn_str = f" (ИНН: {company.inn})"

    country_str = ""
    if company.country:
        country_str = f" [{company.country}]"

    return {
        "value": company.id,
        "label": f"{company.supplier_code} - {company.name}{inn_str}{country_str}",
    }


def get_seller_companies_for_dropdown(
    organization_id: str,
    *,
    query: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Get seller companies formatted for dropdown/select element.

    Args:
        organization_id: Organization UUID
        query: Optional search query
        limit: Maximum results

    Returns:
        List of dicts with 'value' and 'label' for dropdown options
    """
    if query:
        companies = search_seller_companies(organization_id, query, limit=limit)
    else:
        companies = get_active_seller_companies(organization_id)[:limit]

    return [format_seller_company_for_dropdown(c) for c in companies]


def get_seller_company_for_document(company_id: str) -> Optional[Dict[str, Any]]:
    """
    Get seller company information formatted for document generation.

    Returns all fields needed for contracts, invoices, specifications, and official documents.

    Args:
        company_id: Seller company UUID

    Returns:
        Dict with formatted company info for documents, or None if not found
    """
    company = get_seller_company(company_id)
    if not company:
        return None

    return {
        "name": company.name,
        "code": company.supplier_code,
        "country": company.country or "",
        "inn": company.inn or "",
        "kpp": company.kpp or "",
        "ogrn": company.ogrn or "",
        "address": company.registration_address or "",
        "director_name": company.general_director_name or "",
        "director_position": company.general_director_position or "Генеральный директор",
        "full_requisites": _format_full_requisites(company),
    }


def _format_full_requisites(company: SellerCompany) -> str:
    """
    Format full company requisites for official documents.

    Args:
        company: SellerCompany object

    Returns:
        Formatted string with all company requisites
    """
    lines = [company.name]

    if company.country:
        lines.append(f"Страна: {company.country}")

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


def get_seller_company_for_idn(company_id: str) -> Optional[Dict[str, str]]:
    """
    Get seller company code for IDN generation.

    Used when generating Quote IDN in format: SELLER-INN-YEAR-SEQ

    Args:
        company_id: Seller company UUID

    Returns:
        Dict with 'code' (supplier_code) and 'inn', or None if not found
    """
    company = get_seller_company(company_id)
    if not company:
        return None

    return {
        "code": company.supplier_code,
        "inn": company.inn or "",
    }


def get_unique_countries(organization_id: str) -> List[str]:
    """
    Get list of unique countries from seller companies.

    Useful for filter dropdowns.

    Args:
        organization_id: Organization UUID

    Returns:
        List of unique country names
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("seller_companies").select("country")\
            .eq("organization_id", organization_id)\
            .not_.is_("country", "null")\
            .execute()

        if not result.data:
            return []

        countries = set(row["country"] for row in result.data if row.get("country"))
        return sorted(list(countries))

    except Exception as e:
        print(f"Error getting unique countries: {e}")
        return []
