"""
Customer Service - CRUD operations for customers and customer_contacts tables

This module provides functions for managing customers (external buyers) and their contacts:
- Create/Update/Delete customers
- Create/Update/Delete customer contacts (ЛПР - decision makers)
- Query customers by organization, INN
- Search customers for HTMX dropdowns
- Manage signatory and primary contact flags

Based on app_spec.xml customers and customer_contacts table definitions (Feature API-004).

Supply chain level: QUOTE (one customer per quote)

Customers are external companies that buy from us.
Customer contacts are decision makers (ЛПР) within those companies.
The is_signatory contact is used for specification PDF generation.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import re
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


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CustomerContact:
    """
    Represents a customer contact (ЛПР - decision maker).

    Maps to customer_contacts table in database.
    """
    id: str
    customer_id: str
    name: str  # Имя (First name)

    # Full name parts (ФИО раздельно)
    last_name: Optional[str] = None  # Фамилия (Last name)
    patronymic: Optional[str] = None  # Отчество (Middle name/Patronymic)

    # Contact details
    position: Optional[str] = None  # Job title (e.g., "Директор", "Главный инженер")
    email: Optional[str] = None
    phone: Optional[str] = None

    # Special flags
    is_signatory: bool = False  # Used in specification PDF
    is_primary: bool = False    # Primary contact for communication

    # Notes
    notes: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def get_full_name(self) -> str:
        """Get full name in Russian format: Фамилия Имя Отчество"""
        parts = []
        if self.last_name:
            parts.append(self.last_name)
        parts.append(self.name)
        if self.patronymic:
            parts.append(self.patronymic)
        return " ".join(parts)


@dataclass
class Customer:
    """
    Represents a customer (external buyer company).

    Maps to customers table in database.
    """
    id: str
    organization_id: str
    name: str

    # Legal identifiers (Russian)
    inn: Optional[str] = None   # ИНН (10 digits for legal entities, 12 for IE)
    kpp: Optional[str] = None   # КПП (9 digits)
    ogrn: Optional[str] = None  # ОГРН (13 digits for legal entities, 15 for IE)

    # Addresses
    legal_address: Optional[str] = None   # Юридический адрес
    actual_address: Optional[str] = None  # Фактический адрес
    postal_address: Optional[str] = None  # Почтовый адрес (если отличается)

    # Director information (ЛПР подписант - signatory)
    general_director_name: Optional[str] = None
    general_director_position: Optional[str] = "Генеральный директор"

    # Warehouse addresses (JSONB array)
    warehouse_addresses: List[str] = field(default_factory=list)

    # Status
    is_active: bool = True

    # Notes (free-form text)
    notes: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Nested contacts (populated by get_customer_with_contacts)
    contacts: List[CustomerContact] = field(default_factory=list)


def _parse_contact(data: dict) -> CustomerContact:
    """Parse database row into CustomerContact object."""
    return CustomerContact(
        id=data["id"],
        customer_id=data["customer_id"],
        name=data["name"],
        position=data.get("position"),
        email=data.get("email"),
        phone=data.get("phone"),
        is_signatory=data.get("is_signatory", False),
        is_primary=data.get("is_primary", False),
        notes=data.get("notes"),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
    )


def _parse_customer(data: dict, contacts: Optional[List[dict]] = None) -> Customer:
    """Parse database row into Customer object."""
    warehouse_addresses = data.get("warehouse_addresses") or []
    if isinstance(warehouse_addresses, str):
        # Handle JSON string from database
        import json
        try:
            warehouse_addresses = json.loads(warehouse_addresses)
        except (json.JSONDecodeError, TypeError):
            warehouse_addresses = []

    parsed_contacts = []
    if contacts:
        parsed_contacts = [_parse_contact(c) for c in contacts]

    return Customer(
        id=data["id"],
        organization_id=data["organization_id"],
        name=data["name"],
        inn=data.get("inn"),
        kpp=data.get("kpp"),
        ogrn=data.get("ogrn"),
        legal_address=data.get("legal_address"),
        actual_address=data.get("actual_address"),
        postal_address=data.get("postal_address"),
        general_director_name=data.get("general_director_name"),
        general_director_position=data.get("general_director_position", "Генеральный директор"),
        warehouse_addresses=warehouse_addresses,
        is_active=data.get("is_active", True),
        notes=data.get("notes"),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        contacts=parsed_contacts,
    )


# =============================================================================
# VALIDATION
# =============================================================================

def validate_inn(inn: str) -> bool:
    """
    Validate Russian INN format.

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
    return bool(re.match(r'^\d{13}$', ogrn) or re.match(r'^\d{15}$', ogrn))


def validate_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email to validate

    Returns:
        True if valid format, False otherwise
    """
    if not email:
        return True  # Email is optional
    # Basic email regex
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))


def validate_phone(phone: str) -> bool:
    """
    Validate phone format (basic).

    Args:
        phone: Phone to validate

    Returns:
        True if looks like a phone number, False otherwise
    """
    if not phone:
        return True  # Phone is optional
    # Remove common separators and check for digits
    digits = re.sub(r'[\s\-\(\)\+]', '', phone)
    return len(digits) >= 7 and digits.isdigit()


# =============================================================================
# CUSTOMER CRUD - CREATE
# =============================================================================

def create_customer(
    organization_id: str,
    name: str,
    *,
    inn: Optional[str] = None,
    kpp: Optional[str] = None,
    ogrn: Optional[str] = None,
    legal_address: Optional[str] = None,
    actual_address: Optional[str] = None,
    postal_address: Optional[str] = None,
    general_director_name: Optional[str] = None,
    general_director_position: Optional[str] = "Генеральный директор",
    warehouse_addresses: Optional[List[str]] = None,
    is_active: bool = True,
) -> Optional[Customer]:
    """
    Create a new customer.

    Args:
        organization_id: Organization UUID
        name: Customer company name
        inn: Russian tax ID (ИНН)
        kpp: Russian tax registration code (КПП)
        ogrn: Russian state registration number (ОГРН)
        legal_address: Legal registration address
        actual_address: Actual business address
        postal_address: Postal address (if different from actual)
        general_director_name: Director name for documents
        general_director_position: Director position title
        warehouse_addresses: List of warehouse addresses
        is_active: Whether customer is active

    Returns:
        Customer object if successful, None otherwise

    Raises:
        ValueError: If any validation fails

    Example:
        customer = create_customer(
            organization_id="org-uuid",
            name="ООО Ромашка",
            inn="7712345678",
            kpp="771201001",
            general_director_name="Петров Петр Петрович"
        )
    """
    # Validate fields
    if inn and not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}. Must be 10 or 12 digits.")
    if kpp and not validate_kpp(kpp):
        raise ValueError(f"Invalid KPP format: {kpp}. Must be 9 digits.")
    if ogrn and not validate_ogrn(ogrn):
        raise ValueError(f"Invalid OGRN format: {ogrn}. Must be 13 or 15 digits.")

    try:
        supabase = _get_supabase()

        result = supabase.table("customers").insert({
            "organization_id": organization_id,
            "name": name,
            "inn": inn,
            "kpp": kpp,
            "ogrn": ogrn,
            "legal_address": legal_address,
            "actual_address": actual_address,
            "postal_address": postal_address,
            "general_director_name": general_director_name,
            "general_director_position": general_director_position,
            "warehouse_addresses": warehouse_addresses or [],
            "is_active": is_active,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_customer(result.data[0])
        return None

    except Exception as e:
        print(f"Error creating customer: {e}")
        return None


# =============================================================================
# CUSTOMER CRUD - READ
# =============================================================================

def get_customer(customer_id: str) -> Optional[Customer]:
    """
    Get a customer by ID.

    Args:
        customer_id: Customer UUID

    Returns:
        Customer object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customers").select("*").eq("id", customer_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_customer(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting customer: {e}")
        return None


def get_customer_with_contacts(customer_id: str) -> Optional[Customer]:
    """
    Get a customer with all their contacts.

    Args:
        customer_id: Customer UUID

    Returns:
        Customer object with contacts populated, None if not found
    """
    try:
        supabase = _get_supabase()

        # Get customer
        customer_result = supabase.table("customers").select("*").eq("id", customer_id).execute()

        if not customer_result.data or len(customer_result.data) == 0:
            return None

        # Get contacts
        contacts_result = supabase.table("customer_contacts").select("*")\
            .eq("customer_id", customer_id)\
            .order("is_primary", desc=True)\
            .order("name")\
            .execute()

        contacts = contacts_result.data if contacts_result.data else []

        return _parse_customer(customer_result.data[0], contacts)

    except Exception as e:
        print(f"Error getting customer with contacts: {e}")
        return None


def get_customer_by_inn(organization_id: str, inn: str) -> Optional[Customer]:
    """
    Get a customer by INN within an organization.

    Args:
        organization_id: Organization UUID
        inn: Russian tax ID

    Returns:
        Customer object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customers").select("*")\
            .eq("organization_id", organization_id)\
            .eq("inn", inn)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_customer(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting customer by INN: {e}")
        return None


def get_all_customers(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Customer]:
    """
    Get all customers for an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status (None = all)
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of Customer objects
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("customers").select("*")\
            .eq("organization_id", organization_id)\
            .order("name")

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_customer(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all customers: {e}")
        return []


def get_active_customers(organization_id: str) -> List[Customer]:
    """
    Get all active customers for an organization.

    Convenience function for dropdown lists.

    Args:
        organization_id: Organization UUID

    Returns:
        List of active Customer objects
    """
    return get_all_customers(organization_id, is_active=True, limit=1000)


def count_customers(
    organization_id: str,
    *,
    is_active: Optional[bool] = None,
) -> int:
    """
    Count customers in an organization.

    Args:
        organization_id: Organization UUID
        is_active: Filter by active status

    Returns:
        Number of customers
    """
    try:
        supabase = _get_supabase()

        query = supabase.table("customers").select("id", count="exact")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting customers: {e}")
        return 0


def search_customers(
    organization_id: str,
    query: str,
    *,
    is_active: Optional[bool] = True,
    limit: int = 20,
) -> List[Customer]:
    """
    Search customers by name or INN.

    Used for HTMX dropdown autocomplete.

    Args:
        organization_id: Organization UUID
        query: Search query (matches name or inn)
        is_active: Filter by active status
        limit: Maximum number of results

    Returns:
        List of matching Customer objects
    """
    if not query or len(query) < 1:
        return []

    try:
        supabase = _get_supabase()

        search_pattern = f"%{query}%"

        # Search in name (primary)
        base_query = supabase.table("customers").select("*")\
            .eq("organization_id", organization_id)

        if is_active is not None:
            base_query = base_query.eq("is_active", is_active)

        result = base_query.ilike("name", search_pattern)\
            .order("name")\
            .limit(limit)\
            .execute()

        customers = [_parse_customer(row) for row in result.data] if result.data else []

        # If not enough results and query is digits, also search by INN
        if len(customers) < limit and query.isdigit():
            inn_query = supabase.table("customers").select("*")\
                .eq("organization_id", organization_id)\
                .ilike("inn", search_pattern)

            if is_active is not None:
                inn_query = inn_query.eq("is_active", is_active)

            inn_result = inn_query.limit(limit - len(customers)).execute()

            if inn_result.data:
                existing_ids = {c.id for c in customers}
                for row in inn_result.data:
                    if row["id"] not in existing_ids:
                        customers.append(_parse_customer(row))

        return customers

    except Exception as e:
        print(f"Error searching customers: {e}")
        return []


def customer_exists(organization_id: str, inn: str) -> bool:
    """
    Check if a customer with given INN exists.

    Args:
        organization_id: Organization UUID
        inn: INN to check

    Returns:
        True if customer exists, False otherwise
    """
    return get_customer_by_inn(organization_id, inn) is not None


# =============================================================================
# CUSTOMER CRUD - UPDATE
# =============================================================================

def update_customer(
    customer_id: str,
    *,
    name: Optional[str] = None,
    inn: Optional[str] = None,
    kpp: Optional[str] = None,
    ogrn: Optional[str] = None,
    legal_address: Optional[str] = None,
    actual_address: Optional[str] = None,
    postal_address: Optional[str] = None,
    general_director_name: Optional[str] = None,
    general_director_position: Optional[str] = None,
    warehouse_addresses: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
    notes: Optional[str] = None,
) -> Optional[Customer]:
    """
    Update a customer.

    Args:
        customer_id: Customer UUID
        name: New customer name
        inn: New INN
        kpp: New KPP
        ogrn: New OGRN
        legal_address: New legal address
        actual_address: New actual address
        postal_address: New postal address
        general_director_name: New director name
        general_director_position: New director position
        warehouse_addresses: New warehouse addresses
        is_active: New active status

    Returns:
        Updated Customer object if successful, None otherwise

    Raises:
        ValueError: If any validation fails
    """
    # Validate fields if provided
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
        if inn is not None:
            update_data["inn"] = inn
        if kpp is not None:
            update_data["kpp"] = kpp
        if ogrn is not None:
            update_data["ogrn"] = ogrn
        if legal_address is not None:
            update_data["legal_address"] = legal_address
        if actual_address is not None:
            update_data["actual_address"] = actual_address
        if postal_address is not None:
            update_data["postal_address"] = postal_address
        if general_director_name is not None:
            update_data["general_director_name"] = general_director_name
        if general_director_position is not None:
            update_data["general_director_position"] = general_director_position
        if warehouse_addresses is not None:
            update_data["warehouse_addresses"] = warehouse_addresses
        if is_active is not None:
            update_data["is_active"] = is_active
        if notes is not None:
            update_data["notes"] = notes

        if not update_data:
            # Nothing to update, return current state
            return get_customer(customer_id)

        result = supabase.table("customers").update(update_data)\
            .eq("id", customer_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_customer(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating customer: {e}")
        return None


def activate_customer(customer_id: str) -> Optional[Customer]:
    """
    Activate a customer.

    Args:
        customer_id: Customer UUID

    Returns:
        Updated Customer object
    """
    return update_customer(customer_id, is_active=True)


def deactivate_customer(customer_id: str) -> Optional[Customer]:
    """
    Deactivate a customer (soft delete).

    Args:
        customer_id: Customer UUID

    Returns:
        Updated Customer object
    """
    return update_customer(customer_id, is_active=False)


def add_warehouse_address(customer_id: str, address: str) -> Optional[Customer]:
    """
    Add a warehouse address to a customer.

    Args:
        customer_id: Customer UUID
        address: Warehouse address to add

    Returns:
        Updated Customer object
    """
    customer = get_customer(customer_id)
    if not customer:
        return None

    if address not in customer.warehouse_addresses:
        new_addresses = customer.warehouse_addresses + [address]
        return update_customer(customer_id, warehouse_addresses=new_addresses)

    return customer


def remove_warehouse_address(customer_id: str, address: str) -> Optional[Customer]:
    """
    Remove a warehouse address from a customer.

    Args:
        customer_id: Customer UUID
        address: Warehouse address to remove

    Returns:
        Updated Customer object
    """
    customer = get_customer(customer_id)
    if not customer:
        return None

    if address in customer.warehouse_addresses:
        new_addresses = [a for a in customer.warehouse_addresses if a != address]
        return update_customer(customer_id, warehouse_addresses=new_addresses)

    return customer


# =============================================================================
# CUSTOMER CRUD - DELETE
# =============================================================================

def delete_customer(customer_id: str) -> bool:
    """
    Delete a customer permanently.

    Note: Consider using deactivate_customer() instead for soft delete.
    Warning: This will fail if quotes reference this customer.

    Args:
        customer_id: Customer UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        # First delete all contacts (cascade should handle this, but be explicit)
        supabase.table("customer_contacts").delete().eq("customer_id", customer_id).execute()

        # Then delete customer
        result = supabase.table("customers").delete().eq("id", customer_id).execute()

        return True

    except Exception as e:
        print(f"Error deleting customer: {e}")
        return False


# =============================================================================
# CONTACT CRUD - CREATE
# =============================================================================

def create_contact(
    customer_id: str,
    name: str,
    *,
    position: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    is_signatory: bool = False,
    is_primary: bool = False,
    notes: Optional[str] = None,
) -> Optional[CustomerContact]:
    """
    Create a new customer contact.

    Args:
        customer_id: Customer UUID
        name: Contact full name
        position: Job title
        email: Contact email
        phone: Contact phone
        is_signatory: If True, used as signatory in specification PDF
        is_primary: If True, this is the primary contact
        notes: Additional notes

    Returns:
        CustomerContact object if successful, None otherwise

    Raises:
        ValueError: If email validation fails

    Example:
        contact = create_contact(
            customer_id="customer-uuid",
            name="Иванов Иван Иванович",
            position="Директор по закупкам",
            email="ivanov@company.ru",
            phone="+7 (495) 123-45-67",
            is_signatory=True
        )
    """
    if email and not validate_email(email):
        raise ValueError(f"Invalid email format: {email}")
    if phone and not validate_phone(phone):
        raise ValueError(f"Invalid phone format: {phone}")

    try:
        supabase = _get_supabase()

        # If this is being set as signatory, unset other signatories
        if is_signatory:
            supabase.table("customer_contacts").update({"is_signatory": False})\
                .eq("customer_id", customer_id)\
                .execute()

        # If this is being set as primary, unset other primaries
        if is_primary:
            supabase.table("customer_contacts").update({"is_primary": False})\
                .eq("customer_id", customer_id)\
                .execute()

        result = supabase.table("customer_contacts").insert({
            "customer_id": customer_id,
            "name": name,
            "position": position,
            "email": email,
            "phone": phone,
            "is_signatory": is_signatory,
            "is_primary": is_primary,
            "notes": notes,
        }).execute()

        if result.data and len(result.data) > 0:
            return _parse_contact(result.data[0])
        return None

    except Exception as e:
        print(f"Error creating contact: {e}")
        return None


# =============================================================================
# CONTACT CRUD - READ
# =============================================================================

def get_contact(contact_id: str) -> Optional[CustomerContact]:
    """
    Get a contact by ID.

    Args:
        contact_id: Contact UUID

    Returns:
        CustomerContact object if found, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contacts").select("*").eq("id", contact_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_contact(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting contact: {e}")
        return None


def get_contacts_for_customer(customer_id: str) -> List[CustomerContact]:
    """
    Get all contacts for a customer.

    Args:
        customer_id: Customer UUID

    Returns:
        List of CustomerContact objects, ordered by primary first then by name
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contacts").select("*")\
            .eq("customer_id", customer_id)\
            .order("is_primary", desc=True)\
            .order("name")\
            .execute()

        return [_parse_contact(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting contacts for customer: {e}")
        return []


def get_signatory_contact(customer_id: str) -> Optional[CustomerContact]:
    """
    Get the signatory contact for a customer.

    Used for specification PDF generation.

    Args:
        customer_id: Customer UUID

    Returns:
        CustomerContact object if signatory exists, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contacts").select("*")\
            .eq("customer_id", customer_id)\
            .eq("is_signatory", True)\
            .limit(1)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_contact(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting signatory contact: {e}")
        return None


def get_primary_contact(customer_id: str) -> Optional[CustomerContact]:
    """
    Get the primary contact for a customer.

    Args:
        customer_id: Customer UUID

    Returns:
        CustomerContact object if primary exists, None otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contacts").select("*")\
            .eq("customer_id", customer_id)\
            .eq("is_primary", True)\
            .limit(1)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_contact(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting primary contact: {e}")
        return None


def count_contacts(customer_id: str) -> int:
    """
    Count contacts for a customer.

    Args:
        customer_id: Customer UUID

    Returns:
        Number of contacts
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contacts").select("id", count="exact")\
            .eq("customer_id", customer_id)\
            .execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting contacts: {e}")
        return 0


# =============================================================================
# CONTACT CRUD - UPDATE
# =============================================================================

def update_contact(
    contact_id: str,
    *,
    name: Optional[str] = None,
    position: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    is_signatory: Optional[bool] = None,
    is_primary: Optional[bool] = None,
    notes: Optional[str] = None,
) -> Optional[CustomerContact]:
    """
    Update a contact.

    Args:
        contact_id: Contact UUID
        name: New name
        position: New position
        email: New email
        phone: New phone
        is_signatory: New signatory status
        is_primary: New primary status
        notes: New notes

    Returns:
        Updated CustomerContact object if successful, None otherwise
    """
    if email is not None and email and not validate_email(email):
        raise ValueError(f"Invalid email format: {email}")
    if phone is not None and phone and not validate_phone(phone):
        raise ValueError(f"Invalid phone format: {phone}")

    try:
        supabase = _get_supabase()

        # Get existing contact to know the customer_id
        existing = get_contact(contact_id)
        if not existing:
            return None

        # If setting as signatory, unset other signatories
        if is_signatory is True:
            supabase.table("customer_contacts").update({"is_signatory": False})\
                .eq("customer_id", existing.customer_id)\
                .neq("id", contact_id)\
                .execute()

        # If setting as primary, unset other primaries
        if is_primary is True:
            supabase.table("customer_contacts").update({"is_primary": False})\
                .eq("customer_id", existing.customer_id)\
                .neq("id", contact_id)\
                .execute()

        # Build update dict
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if position is not None:
            update_data["position"] = position
        if email is not None:
            update_data["email"] = email
        if phone is not None:
            update_data["phone"] = phone
        if is_signatory is not None:
            update_data["is_signatory"] = is_signatory
        if is_primary is not None:
            update_data["is_primary"] = is_primary
        if notes is not None:
            update_data["notes"] = notes

        if not update_data:
            return existing

        result = supabase.table("customer_contacts").update(update_data)\
            .eq("id", contact_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_contact(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating contact: {e}")
        return None


def set_signatory(contact_id: str) -> Optional[CustomerContact]:
    """
    Set a contact as the signatory (unsets other signatories).

    Args:
        contact_id: Contact UUID

    Returns:
        Updated CustomerContact object
    """
    return update_contact(contact_id, is_signatory=True)


def set_primary(contact_id: str) -> Optional[CustomerContact]:
    """
    Set a contact as primary (unsets other primaries).

    Args:
        contact_id: Contact UUID

    Returns:
        Updated CustomerContact object
    """
    return update_contact(contact_id, is_primary=True)


# =============================================================================
# CONTACT CRUD - DELETE
# =============================================================================

def delete_contact(contact_id: str) -> bool:
    """
    Delete a contact permanently.

    Args:
        contact_id: Contact UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contacts").delete().eq("id", contact_id).execute()

        return True

    except Exception as e:
        print(f"Error deleting contact: {e}")
        return False


def delete_all_contacts(customer_id: str) -> bool:
    """
    Delete all contacts for a customer.

    Args:
        customer_id: Customer UUID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contacts").delete().eq("customer_id", customer_id).execute()

        return True

    except Exception as e:
        print(f"Error deleting contacts: {e}")
        return False


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_customer_stats(organization_id: str) -> Dict[str, Any]:
    """
    Get customer statistics for an organization.

    Args:
        organization_id: Organization UUID

    Returns:
        Dict with statistics:
        - total: Total number of customers
        - active: Number of active customers
        - inactive: Number of inactive customers
        - with_inn: Number with INN registered
        - with_contacts: Number with at least one contact
        - with_signatory: Number with a designated signatory
    """
    try:
        supabase = _get_supabase()

        # Get all customers
        result = supabase.table("customers").select("id, is_active, inn")\
            .eq("organization_id", organization_id)\
            .execute()

        if not result.data:
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "with_inn": 0,
                "with_contacts": 0,
                "with_signatory": 0,
            }

        total = len(result.data)
        active = sum(1 for row in result.data if row.get("is_active", True))
        inactive = total - active
        with_inn = sum(1 for row in result.data if row.get("inn"))

        # Count customers with contacts and signatories
        customer_ids = [row["id"] for row in result.data]

        contacts_result = supabase.table("customer_contacts").select("customer_id, is_signatory")\
            .in_("customer_id", customer_ids)\
            .execute()

        customers_with_contacts = set()
        customers_with_signatory = set()

        if contacts_result.data:
            for contact in contacts_result.data:
                customers_with_contacts.add(contact["customer_id"])
                if contact.get("is_signatory"):
                    customers_with_signatory.add(contact["customer_id"])

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "with_inn": with_inn,
            "with_contacts": len(customers_with_contacts),
            "with_signatory": len(customers_with_signatory),
        }

    except Exception as e:
        print(f"Error getting customer stats: {e}")
        return {
            "total": 0,
            "active": 0,
            "inactive": 0,
            "with_inn": 0,
            "with_contacts": 0,
            "with_signatory": 0,
        }


def get_customer_display_name(customer: Customer) -> str:
    """
    Get display name for a customer.

    Args:
        customer: Customer object

    Returns:
        Display string like "ООО Ромашка (ИНН: 7712345678)"
    """
    if customer.inn:
        return f"{customer.name} (ИНН: {customer.inn})"
    return customer.name


def format_customer_for_dropdown(customer: Customer) -> Dict[str, str]:
    """
    Format customer for HTMX dropdown option.

    Args:
        customer: Customer object

    Returns:
        Dict with 'value' (id) and 'label' (display name)
    """
    return {
        "value": customer.id,
        "label": get_customer_display_name(customer),
    }


def get_customers_for_dropdown(
    organization_id: str,
    *,
    query: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Get customers formatted for dropdown/select element.

    Args:
        organization_id: Organization UUID
        query: Optional search query
        limit: Maximum results

    Returns:
        List of dicts with 'value' and 'label' for dropdown options
    """
    if query:
        customers = search_customers(organization_id, query, limit=limit)
    else:
        customers = get_active_customers(organization_id)[:limit]

    return [format_customer_for_dropdown(c) for c in customers]


def get_customer_for_document(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get customer information formatted for document generation.

    Returns all fields needed for contracts, invoices, specifications, and official documents.
    Includes signatory information from customer_contacts.

    Args:
        customer_id: Customer UUID

    Returns:
        Dict with formatted customer info for documents, or None if not found
    """
    customer = get_customer_with_contacts(customer_id)
    if not customer:
        return None

    # Find signatory
    signatory = None
    for contact in customer.contacts:
        if contact.is_signatory:
            signatory = contact
            break

    # Find primary contact
    primary = None
    for contact in customer.contacts:
        if contact.is_primary:
            primary = contact
            break

    return {
        "name": customer.name,
        "inn": customer.inn or "",
        "kpp": customer.kpp or "",
        "ogrn": customer.ogrn or "",
        "legal_address": customer.legal_address or "",
        "actual_address": customer.actual_address or "",
        "director_name": customer.general_director_name or "",
        "director_position": customer.general_director_position or "Генеральный директор",
        "warehouse_addresses": customer.warehouse_addresses,
        "full_requisites": _format_full_requisites(customer),
        "signatory_name": signatory.name if signatory else customer.general_director_name or "",
        "signatory_position": signatory.position if signatory else customer.general_director_position or "Генеральный директор",
        "primary_contact_name": primary.name if primary else "",
        "primary_contact_email": primary.email if primary else "",
        "primary_contact_phone": primary.phone if primary else "",
    }


def _format_full_requisites(customer: Customer) -> str:
    """
    Format full customer requisites for official documents.

    Args:
        customer: Customer object

    Returns:
        Formatted string with all customer requisites
    """
    lines = [customer.name]

    if customer.legal_address:
        lines.append(f"Юридический адрес: {customer.legal_address}")

    if customer.actual_address and customer.actual_address != customer.legal_address:
        lines.append(f"Фактический адрес: {customer.actual_address}")

    if customer.inn:
        if customer.kpp:
            lines.append(f"ИНН/КПП: {customer.inn}/{customer.kpp}")
        else:
            lines.append(f"ИНН: {customer.inn}")

    if customer.ogrn:
        lines.append(f"ОГРН: {customer.ogrn}")

    return "\n".join(lines)


def get_customer_for_idn(customer_id: str) -> Optional[Dict[str, str]]:
    """
    Get customer INN for IDN generation.

    Used when generating Quote IDN in format: SELLER-INN-YEAR-SEQ

    Args:
        customer_id: Customer UUID

    Returns:
        Dict with 'inn', or None if not found
    """
    customer = get_customer(customer_id)
    if not customer:
        return None

    return {
        "inn": customer.inn or "",
    }


def get_signatory_for_specification(customer_id: str) -> Optional[Dict[str, str]]:
    """
    Get signatory information for specification PDF generation.

    This uses the customer_contacts.is_signatory = true contact.
    Falls back to customer.general_director_name if no signatory contact.

    Args:
        customer_id: Customer UUID

    Returns:
        Dict with 'name' and 'position' for signatory, or None if not found
    """
    # First try to get signatory contact
    signatory = get_signatory_contact(customer_id)
    if signatory:
        return {
            "name": signatory.name,
            "position": signatory.position or "Представитель",
        }

    # Fall back to customer director
    customer = get_customer(customer_id)
    if customer and customer.general_director_name:
        return {
            "name": customer.general_director_name,
            "position": customer.general_director_position or "Генеральный директор",
        }

    return None


# =============================================================================
# CUSTOMER RELATED DATA - For Customer Detail Page Tabs
# =============================================================================

def get_customer_contracts(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get all contracts for a customer.

    Args:
        customer_id: Customer UUID

    Returns:
        List of contract dicts with fields:
        - id, contract_number, contract_date, status, notes, created_at
    """
    try:
        supabase = _get_supabase()

        result = supabase.table("customer_contracts").select("*")\
            .eq("customer_id", customer_id)\
            .order("contract_date", desc=True)\
            .execute()

        return result.data if result.data else []

    except Exception as e:
        print(f"Error getting customer contracts: {e}")
        return []


def get_customer_quotes(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get all quotes (КП) for a customer with calculated sums and profit.

    Args:
        customer_id: Customer UUID

    Returns:
        List of quote dicts with fields:
        - id, idn, workflow_status, deal_type, created_at
        - total_sum: sum of all items (unit_price * quantity)
        - total_profit: difference between sale and purchase prices
    """
    try:
        supabase = _get_supabase()

        # Get quotes
        quotes_result = supabase.table("quotes").select("*")\
            .eq("customer_id", customer_id)\
            .order("created_at", desc=True)\
            .execute()

        if not quotes_result.data:
            return []

        quotes = quotes_result.data
        quote_ids = [q["id"] for q in quotes]

        # Get quote items for all quotes
        items_result = supabase.table("quote_items").select(
            "quote_id, quantity, unit_price, supplier_price"
        ).in_("quote_id", quote_ids).execute()

        # Calculate sums and profits per quote
        quote_totals = {}
        if items_result.data:
            for item in items_result.data:
                quote_id = item["quote_id"]
                if quote_id not in quote_totals:
                    quote_totals[quote_id] = {"sum": 0, "profit": 0}

                quantity = item.get("quantity", 0) or 0
                unit_price = item.get("unit_price", 0) or 0
                supplier_price = item.get("supplier_price", 0) or 0

                item_total = quantity * unit_price
                item_profit = quantity * (unit_price - supplier_price)

                quote_totals[quote_id]["sum"] += item_total
                quote_totals[quote_id]["profit"] += item_profit

        # Add totals to quotes
        for quote in quotes:
            quote_id = quote["id"]
            if quote_id in quote_totals:
                quote["total_sum"] = quote_totals[quote_id]["sum"]
                quote["total_profit"] = quote_totals[quote_id]["profit"]
            else:
                quote["total_sum"] = 0
                quote["total_profit"] = 0

        return quotes

    except Exception as e:
        print(f"Error getting customer quotes: {e}")
        return []


def get_customer_specifications(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get all specifications for a customer (through quotes) with calculated sums and profit.

    Args:
        customer_id: Customer UUID

    Returns:
        List of specification dicts with quote info, total_sum, and total_profit
    """
    try:
        supabase = _get_supabase()

        # First get all quote IDs for this customer
        quotes_result = supabase.table("quotes").select("id")\
            .eq("customer_id", customer_id)\
            .execute()

        if not quotes_result.data:
            return []

        quote_ids = [q["id"] for q in quotes_result.data]

        # Get specifications for these quotes
        specs_result = supabase.table("specifications").select("*, quotes(idn, customer_id)")\
            .in_("quote_id", quote_ids)\
            .order("sign_date", desc=True)\
            .execute()

        if not specs_result.data:
            return []

        specifications = specs_result.data
        spec_quote_ids = [s["quote_id"] for s in specifications if s.get("quote_id")]

        # Get quote items to calculate sums
        items_result = supabase.table("quote_items").select(
            "quote_id, quantity, unit_price, supplier_price"
        ).in_("quote_id", spec_quote_ids).execute()

        # Calculate sums and profits per quote
        quote_totals = {}
        if items_result.data:
            for item in items_result.data:
                quote_id = item["quote_id"]
                if quote_id not in quote_totals:
                    quote_totals[quote_id] = {"sum": 0, "profit": 0}

                quantity = item.get("quantity", 0) or 0
                unit_price = item.get("unit_price", 0) or 0
                supplier_price = item.get("supplier_price", 0) or 0

                item_total = quantity * unit_price
                item_profit = quantity * (unit_price - supplier_price)

                quote_totals[quote_id]["sum"] += item_total
                quote_totals[quote_id]["profit"] += item_profit

        # Add totals to specifications
        for spec in specifications:
            quote_id = spec.get("quote_id")
            if quote_id and quote_id in quote_totals:
                spec["total_sum"] = quote_totals[quote_id]["sum"]
                spec["total_profit"] = quote_totals[quote_id]["profit"]
            else:
                spec["total_sum"] = 0
                spec["total_profit"] = 0

        return specifications

    except Exception as e:
        print(f"Error getting customer specifications: {e}")
        return []


def get_customer_statistics(customer_id: str) -> Dict[str, Any]:
    """
    Get aggregated statistics for a customer.

    Args:
        customer_id: Customer UUID

    Returns:
        Dict with statistics:
        - quotes_count: Number of quotes
        - quotes_sum: Total sum of all quotes
        - specifications_count: Number of specifications
        - specifications_sum: Total sum of all specifications
    """
    try:
        supabase = _get_supabase()

        # Get all quotes for this customer
        quotes_result = supabase.table("quotes").select("id")\
            .eq("customer_id", customer_id)\
            .execute()

        if not quotes_result.data:
            return {
                "quotes_count": 0,
                "quotes_sum": 0,
                "specifications_count": 0,
                "specifications_sum": 0
            }

        quote_ids = [q["id"] for q in quotes_result.data]
        quotes_count = len(quote_ids)

        # Get all quote items to calculate quotes sum
        items_result = supabase.table("quote_items").select(
            "quote_id, quantity, unit_price"
        ).in_("quote_id", quote_ids).execute()

        quotes_sum = 0
        if items_result.data:
            for item in items_result.data:
                quantity = item.get("quantity", 0) or 0
                unit_price = item.get("unit_price", 0) or 0
                quotes_sum += quantity * unit_price

        # Get specifications count
        specs_result = supabase.table("specifications").select("id, quote_id")\
            .in_("quote_id", quote_ids)\
            .execute()

        specifications_count = len(specs_result.data) if specs_result.data else 0

        # Calculate specifications sum (same as quote items sums for those quotes with specs)
        specifications_sum = 0
        if specs_result.data:
            spec_quote_ids = [s["quote_id"] for s in specs_result.data if s.get("quote_id")]
            if spec_quote_ids:
                spec_items_result = supabase.table("quote_items").select(
                    "quote_id, quantity, unit_price"
                ).in_("quote_id", spec_quote_ids).execute()

                if spec_items_result.data:
                    for item in spec_items_result.data:
                        quantity = item.get("quantity", 0) or 0
                        unit_price = item.get("unit_price", 0) or 0
                        specifications_sum += quantity * unit_price

        return {
            "quotes_count": quotes_count,
            "quotes_sum": round(quotes_sum, 2),
            "specifications_count": specifications_count,
            "specifications_sum": round(specifications_sum, 2)
        }

    except Exception as e:
        print(f"Error getting customer statistics: {e}")
        return {
            "quotes_count": 0,
            "quotes_sum": 0,
            "specifications_count": 0,
            "specifications_sum": 0
        }


def get_customer_requested_items(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get all unique items (products) ever requested by customer with detailed info.

    This returns all products from all quote_items for all quotes of this customer,
    even if no price was given.

    Args:
        customer_id: Customer UUID

    Returns:
        List of unique products with aggregated info:
        - product details
        - times_requested (count)
        - total_quantity (sum of all quantities requested)
        - last_price (most recent unit_price)
        - last_requested_at
        - brands requested
        - was_sold (boolean - was this item in a deal?)
    """
    try:
        supabase = _get_supabase()

        # Get all quote IDs for this customer
        quotes_result = supabase.table("quotes").select("id, workflow_status")\
            .eq("customer_id", customer_id)\
            .execute()

        if not quotes_result.data:
            return []

        quote_ids = [q["id"] for q in quotes_result.data]

        # Track which quotes resulted in deals
        deal_quote_ids = set([
            q["id"] for q in quotes_result.data
            if q.get("workflow_status") == "deal"
        ])

        # Get all quote items with product details
        result = supabase.table("quote_items").select(
            "*, products(id, name, sku, brand, unit), quotes(id, idn, created_at, workflow_status)"
        )\
            .in_("quote_id", quote_ids)\
            .order("created_at", desc=True)\
            .execute()

        if not result.data:
            return []

        # Group by product_id and aggregate
        from collections import defaultdict

        product_map = defaultdict(lambda: {
            "product": None,
            "times_requested": 0,
            "total_quantity": 0,
            "last_price": None,
            "last_requested_at": None,
            "brands": set(),
            "quotes": [],
            "was_sold": False
        })

        for item in result.data:
            product_id = item["product_id"]
            quote_id = item["quote_id"]

            product_map[product_id]["product"] = item.get("products")
            product_map[product_id]["times_requested"] += 1

            # Add quantity
            quantity = item.get("quantity", 0) or 0
            product_map[product_id]["total_quantity"] += quantity

            # Track latest price
            if item.get("unit_price"):
                # Update price if this is the most recent request
                if item.get("quotes") and item["quotes"].get("created_at"):
                    request_date = item["quotes"]["created_at"]
                    if not product_map[product_id]["last_requested_at"] or \
                       request_date > product_map[product_id]["last_requested_at"]:
                        product_map[product_id]["last_price"] = item["unit_price"]
                        product_map[product_id]["last_requested_at"] = request_date

            # Track brands
            if item.get("brand"):
                product_map[product_id]["brands"].add(item["brand"])

            # Track quotes
            if item.get("quotes"):
                quote_idn = item["quotes"].get("idn")
                if quote_idn and quote_idn not in product_map[product_id]["quotes"]:
                    product_map[product_id]["quotes"].append(quote_idn)

            # Check if was sold (quote became a deal)
            if quote_id in deal_quote_ids:
                product_map[product_id]["was_sold"] = True

        # Convert to list
        items = []
        for product_id, data in product_map.items():
            items.append({
                "product_id": product_id,
                "product": data["product"],
                "times_requested": data["times_requested"],
                "total_quantity": data["total_quantity"],
                "last_price": data["last_price"],
                "last_requested_at": data["last_requested_at"],
                "brands": list(data["brands"]),
                "quotes": data["quotes"],
                "was_sold": data["was_sold"]
            })

        # Sort by times requested (most requested first)
        items.sort(key=lambda x: x["times_requested"], reverse=True)

        return items

    except Exception as e:
        print(f"Error getting customer requested items: {e}")
        return []
