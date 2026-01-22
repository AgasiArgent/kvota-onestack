"""
Quote Version Service

Creates immutable quote snapshots for audit trail.
Stores calculation variables, products, exchange rates, and results at point in time.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from services.database import get_supabase


def create_quote_version(
    quote_id: str,
    user_id: str,
    variables: Dict[str, Any],
    items: List[Dict],
    results: List[Dict],
    totals: Dict[str, Any],
    change_reason: str = "Calculation",
    customer_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create immutable snapshot of quote state.

    Args:
        quote_id: Quote UUID
        user_id: User UUID creating the version
        variables: Calculation variables used
        items: List of quote items with product info
        results: List of calculation results (phase_results JSONB)
        totals: Quote totals (total_usd, total_no_vat, total_with_vat, etc.)
        change_reason: Reason for creating version
        customer_id: Customer UUID (required by DB schema)

    Returns:
        Created version record
    """
    supabase = get_supabase()

    # Get current version number (column is 'version' not 'version_number')
    existing = supabase.table("quote_versions") \
        .select("version") \
        .eq("quote_id", quote_id) \
        .order("version", desc=True) \
        .limit(1) \
        .execute()

    version_num = 1
    if existing.data and existing.data[0].get("version"):
        version_num = existing.data[0]["version"] + 1

    # Convert Decimal to float in variables
    vars_for_storage = {
        k: float(v) if isinstance(v, Decimal) else v
        for k, v in variables.items()
    }

    # Build products snapshot for input_variables JSONB
    products_snapshot = []
    for item in items:
        products_snapshot.append({
            "id": item.get("id"),
            "product_name": item.get("product_name"),
            "product_code": item.get("product_code"),
            "quantity": item.get("quantity"),
            "base_price_vat": float(item.get("base_price_vat", 0)),
            "weight_in_kg": float(item.get("weight_in_kg", 0)) if item.get("weight_in_kg") else None,
            "customs_code": item.get("customs_code"),
            "supplier_country": item.get("supplier_country"),
        })

    # Combine all data into input_variables JSONB (actual DB column)
    input_variables = {
        "variables": vars_for_storage,
        "products": products_snapshot,
        "results": results,
        "totals": {k: float(v) if isinstance(v, Decimal) else v for k, v in totals.items()},
        "exchange_rate": {
            "rate": float(variables.get("exchange_rate", 1.0)),
            "from_currency": variables.get("currency_of_base_price", "USD"),
            "to_currency": variables.get("currency_of_quote", "USD"),
        },
        "change_reason": change_reason
    }

    # Build version record using actual DB columns
    # Note: status must match quote_versions_status_check constraint (sent, pending, approved, rejected)
    version_record = {
        "quote_id": quote_id,
        "version": version_num,
        "status": "sent",  # Using "sent" as it's a valid status value
        "customer_id": customer_id,
        "seller_company": variables.get("seller_company", ""),
        "offer_sale_type": variables.get("offer_sale_type", "поставка"),
        "offer_incoterms": variables.get("offer_incoterms", "DDP"),
        "currency_of_quote": variables.get("currency_of_quote", "USD"),
        "input_variables": input_variables,
        "created_by": user_id,
        "created_at": datetime.now().isoformat()
    }

    # Insert version
    result = supabase.table("quote_versions") \
        .insert(version_record) \
        .execute()

    version = result.data[0] if result.data else None

    # Update quote with current version info
    if version:
        try:
            supabase.table("quotes").update({
                "current_version_id": version["id"],
                "delivery_terms": variables.get("offer_incoterms", ""),
                "updated_at": datetime.now().isoformat()
            }).eq("id", quote_id).execute()
        except Exception:
            pass  # Some columns may not exist

    return version


def list_quote_versions(quote_id: str, org_id: str) -> List[Dict]:
    """
    List all versions for a quote.

    Args:
        quote_id: Quote UUID
        org_id: Organization UUID (for security)

    Returns:
        List of versions ordered by version desc
    """
    supabase = get_supabase()

    # Verify quote belongs to org
    quote = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote.data:
        return []

    # Get versions using actual DB columns
    result = supabase.table("quote_versions") \
        .select("id, version, status, input_variables, created_at, seller_company, offer_incoterms") \
        .eq("quote_id", quote_id) \
        .order("version", desc=True) \
        .execute()

    # Transform for UI compatibility
    versions = []
    for v in (result.data or []):
        input_vars = v.get("input_variables") or {}
        totals = input_vars.get("totals", {})
        versions.append({
            "id": v["id"],
            "version_number": v.get("version", 1),
            "status": v.get("status", "sent"),
            "total_quote_currency": totals.get("total_with_vat", 0),
            "change_reason": input_vars.get("change_reason", "Calculation"),
            "created_at": v.get("created_at"),
            "seller_company": v.get("seller_company"),
            "offer_incoterms": v.get("offer_incoterms")
        })

    return versions


def get_quote_version(quote_id: str, version_number: int, org_id: str) -> Optional[Dict]:
    """
    Get specific version with full details.

    Args:
        quote_id: Quote UUID
        version_number: Version to retrieve
        org_id: Organization UUID (for security)

    Returns:
        Version record with all snapshots, or None if not found
    """
    supabase = get_supabase()

    # Verify quote belongs to org
    quote = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote.data:
        return None

    # Get version using actual DB column name
    result = supabase.table("quote_versions") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .eq("version", version_number) \
        .execute()

    if not result.data:
        return None

    # Transform for compatibility
    v = result.data[0]
    input_vars = v.get("input_variables") or {}

    return {
        "id": v["id"],
        "quote_id": v["quote_id"],
        "version_number": v.get("version", 1),
        "status": v.get("status", "draft"),
        "quote_variables": input_vars.get("variables", {}),
        "products_snapshot": input_vars.get("products", []),
        "exchange_rates_used": input_vars.get("exchange_rate", {}),
        "calculation_results": input_vars.get("results", []),
        "total_quote_currency": input_vars.get("totals", {}).get("total_with_vat", 0),
        "change_reason": input_vars.get("change_reason", ""),
        "created_at": v.get("created_at"),
        "created_by": v.get("created_by"),
        "seller_company": v.get("seller_company"),
        "offer_incoterms": v.get("offer_incoterms"),
        "currency_of_quote": v.get("currency_of_quote")
    }
