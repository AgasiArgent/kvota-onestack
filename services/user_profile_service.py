"""User Profile Service

Handles user profile operations:
- Fetching user profile with extended information
- Getting user statistics
- Getting user's clients and quotes/specifications
"""

from typing import Dict, Any, List, Optional
from services.database import get_supabase


def get_user_profile(user_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile with all related information.

    Returns user profile with:
    - Basic auth.users fields (email, phone)
    - Extended profile (full_name, position, department, sales_group, manager, location)
    - Role information
    """
    supabase = get_supabase()

    # Get user profile with email from organization_members
    # Since auth.admin API is not available, we get email through RPC or directly
    member_result = supabase.rpc(
        "get_user_profile_data",
        {"p_user_id": user_id, "p_organization_id": organization_id}
    ).execute()

    if not member_result.data or len(member_result.data) == 0:
        return None

    data = member_result.data[0]

    return {
        "id": user_id,
        "email": data.get("email"),
        "phone": data.get("phone"),
        "created_at": data.get("created_at"),
        # From profile
        "full_name": data.get("full_name"),
        "position": data.get("position"),
        "department": data.get("department_name"),
        "sales_group": data.get("sales_group_name"),
        "manager_email": data.get("manager_email"),
        "location": data.get("location"),
        # Role
        "role_name": data.get("role_name"),
        "role_slug": data.get("role_slug"),
    }


def get_user_statistics(user_id: str, organization_id: str) -> Dict[str, Any]:
    """
    Get user statistics using the user_statistics view.

    Returns:
    - total_customers: number of customers
    - total_quotes: number of quotes
    - total_quotes_sum_usd: sum of quotes in USD
    - total_quotes_sum: sum of quotes in local currency
    - total_specifications: number of specifications
    - total_specifications_sum_usd: sum of specifications in USD
    - total_specifications_sum: sum of specifications in local currency
    - total_profit_usd: total profit from specifications
    """
    supabase = get_supabase()

    # Use the function to get statistics
    result = supabase.rpc(
        "get_user_statistics",
        {"target_user_id": user_id, "target_organization_id": organization_id}
    ).execute()

    if not result.data or len(result.data) == 0:
        # Return zero stats if no data
        return {
            "total_customers": 0,
            "total_quotes": 0,
            "total_quotes_sum_usd": 0,
            "total_quotes_sum": 0,
            "total_specifications": 0,
            "total_specifications_sum_usd": 0,
            "total_specifications_sum": 0,
            "total_profit_usd": 0,
        }

    stats = result.data[0]
    return {
        "total_customers": int(stats.get("total_customers", 0)),
        "total_quotes": int(stats.get("total_quotes", 0)),
        "total_quotes_sum_usd": float(stats.get("total_quotes_sum_usd", 0)),
        "total_quotes_sum": float(stats.get("total_quotes_sum", 0)),
        "total_specifications": int(stats.get("total_specifications", 0)),
        "total_specifications_sum_usd": float(stats.get("total_specifications_sum_usd", 0)),
        "total_specifications_sum": float(stats.get("total_specifications_sum", 0)),
        "total_profit_usd": float(stats.get("total_profit_usd", 0)),
    }


def get_user_specifications(user_id: str, organization_id: str) -> List[Dict[str, Any]]:
    """
    Get list of specifications created by user with related customer and quote info.

    Returns list with:
    - customer_name
    - customer_inn
    - customer_industry (category)
    - quote_sum
    - spec_sum (from quote total_amount)
    - last_quote_date
    - updated_at
    """
    supabase = get_supabase()

    result = supabase.table("specifications") \
        .select("""
            id,
            specification_number,
            created_at,
            updated_at,
            quote:quotes(
                id,
                idn_quote,
                total_amount,
                total_usd,
                quote_date,
                customer:customers(
                    id,
                    name,
                    inn,
                    industry
                )
            )
        """) \
        .eq("created_by", user_id) \
        .eq("organization_id", organization_id) \
        .order("updated_at", desc=True) \
        .execute()

    specifications = []
    for spec in result.data:
        quote = spec.get("quote", {})
        customer = quote.get("customer", {}) if quote else {}

        specifications.append({
            "spec_id": spec.get("id"),
            "spec_number": spec.get("specification_number"),
            "customer_name": customer.get("name") if customer else "—",
            "customer_inn": customer.get("inn") if customer else "—",
            "customer_category": customer.get("industry") if customer else "—",
            "quote_sum": float(quote.get("total_amount", 0)) if quote else 0,
            "spec_sum": float(quote.get("total_usd", 0)) if quote else 0,
            "last_quote_date": quote.get("quote_date") if quote else None,
            "updated_at": spec.get("updated_at"),
        })

    return specifications


def get_user_customers(user_id: str, organization_id: str) -> List[Dict[str, Any]]:
    """
    Get list of customers for a user.

    Includes:
    - Customers created by user (customers.created_by = user_id)
    - Customers with quotes from user (quotes.created_by_user_id = user_id)

    Returns list with:
    - customer_name
    - customer_inn
    - customer_category (industry)
    - quotes_sum
    - specs_sum
    - last_quote_date
    - updated_at
    """
    supabase = get_supabase()

    # Get all customers in organization with their quotes
    # We'll filter in Python to avoid complex OR conditions
    result = supabase.table("customers") \
        .select("""
            id,
            name,
            inn,
            industry,
            updated_at,
            created_by,
            quotes:quotes(
                id,
                total_amount,
                total_usd,
                quote_date,
                created_by_user_id,
                specifications:specifications(id)
            )
        """) \
        .eq("organization_id", organization_id) \
        .order("updated_at", desc=True) \
        .execute()

    customers_map = {}

    for customer in result.data:
        customer_id = customer.get("id")
        quotes = customer.get("quotes", [])

        # Filter quotes created by this user
        user_quotes = [q for q in quotes if q.get("created_by_user_id") == user_id]

        # Include customer if: user created it OR user has quotes for it
        if not user_quotes and customer.get("created_by") != user_id:
            # Skip if user didn't create customer and has no quotes
            continue

        # Calculate sums
        quotes_sum = sum(float(q.get("total_amount", 0)) for q in user_quotes)
        specs_sum = sum(float(q.get("total_usd", 0)) for q in user_quotes if q.get("specifications"))

        # Get last quote date
        last_quote_date = None
        if user_quotes:
            last_quote_date = max(q.get("quote_date") for q in user_quotes if q.get("quote_date"))

        customers_map[customer_id] = {
            "customer_id": customer_id,
            "customer_name": customer.get("name", "—"),
            "customer_inn": customer.get("inn", "—"),
            "customer_category": customer.get("industry", "—"),
            "quotes_sum": quotes_sum,
            "specs_sum": specs_sum,
            "last_quote_date": last_quote_date,
            "updated_at": customer.get("updated_at"),
        }

    return list(customers_map.values())


def update_user_profile(user_id: str, organization_id: str, **update_data) -> bool:
    """
    Update user profile fields.

    Args:
        user_id: User ID
        organization_id: Organization ID
        **update_data: Fields to update (full_name, position, phone, location, etc.)

    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase()

    try:
        # Check if profile exists
        result = supabase.table("user_profiles") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("organization_id", organization_id) \
            .execute()

        if result.data and len(result.data) > 0:
            # Update existing profile
            supabase.table("user_profiles") \
                .update(update_data) \
                .eq("user_id", user_id) \
                .eq("organization_id", organization_id) \
                .execute()
        else:
            # Create new profile
            insert_data = {
                "user_id": user_id,
                "organization_id": organization_id,
                **update_data
            }
            supabase.table("user_profiles") \
                .insert(insert_data) \
                .execute()

        return True
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return False


def get_departments(organization_id: str) -> List[Dict[str, Any]]:
    """Get list of departments for organization."""
    supabase = get_supabase()

    result = supabase.table("departments") \
        .select("id, name") \
        .eq("organization_id", organization_id) \
        .order("name") \
        .execute()

    return result.data


def get_sales_groups(organization_id: str) -> List[Dict[str, Any]]:
    """Get list of sales groups for organization."""
    supabase = get_supabase()

    result = supabase.table("sales_groups") \
        .select("id, name") \
        .eq("organization_id", organization_id) \
        .order("name") \
        .execute()

    return result.data


def get_organization_users(organization_id: str) -> List[Dict[str, Any]]:
    """Get list of users in organization (for manager selection)."""
    supabase = get_supabase()

    # Get users through RPC to access email from auth.users
    result = supabase.rpc(
        "get_organization_users_list",
        {"p_organization_id": organization_id}
    ).execute()

    return result.data if result.data else []
