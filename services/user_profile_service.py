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

    # Get user from auth.users
    user_result = supabase.auth.admin.get_user_by_id(user_id)
    if not user_result or not user_result.user:
        return None

    user = user_result.user

    # Get user profile
    profile_result = supabase.table("user_profiles") \
        .select("*, department:departments(name), sales_group:sales_groups(name), manager:auth.users!manager_id(email)") \
        .eq("user_id", user_id) \
        .eq("organization_id", organization_id) \
        .maybe_single() \
        .execute()

    profile = profile_result.data if profile_result.data else {}

    # Get user role
    role_result = supabase.table("organization_members") \
        .select("role:roles(name, slug)") \
        .eq("user_id", user_id) \
        .eq("organization_id", organization_id) \
        .eq("status", "active") \
        .maybe_single() \
        .execute()

    role = None
    if role_result.data and role_result.data.get("role"):
        role = role_result.data["role"]

    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "created_at": user.created_at,
        # From profile
        "full_name": profile.get("full_name"),
        "position": profile.get("position"),
        "department": profile.get("department", {}).get("name") if profile.get("department") else None,
        "sales_group": profile.get("sales_group", {}).get("name") if profile.get("sales_group") else None,
        "manager_email": profile.get("manager", {}).get("email") if profile.get("manager") else None,
        "location": profile.get("location"),
        # Role
        "role_name": role.get("name") if role else None,
        "role_slug": role.get("slug") if role else None,
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

    # Get customers with their quotes
    result = supabase.table("customers") \
        .select("""
            id,
            name,
            inn,
            industry,
            updated_at,
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
        .or_(f"created_by.eq.{user_id},quotes.created_by_user_id.eq.{user_id}") \
        .order("updated_at", desc=True) \
        .execute()

    customers_map = {}

    for customer in result.data:
        customer_id = customer.get("id")
        quotes = customer.get("quotes", [])

        # Filter quotes created by this user
        user_quotes = [q for q in quotes if q.get("created_by_user_id") == user_id]

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
