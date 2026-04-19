"""
Quote Version Service

Creates immutable quote snapshots for audit trail.
Stores calculation variables, products, exchange rates, and results at point in time.

Phase 5d (Pattern A): the products snapshot is sourced from
``composition_service.get_composed_items(quote_id, supabase)`` at snapshot
creation time, NOT from legacy ``quote_items`` columns passed by callers.
This makes the snapshot layer the single source of truth for "what the
composition looked like at this instant" and removes the risk of a caller
accidentally passing raw quote_items rows.

See: .kiro/specs/phase-5d-legacy-refactor/design.md §1.1, §2.1.7
     .kiro/specs/phase-5d-legacy-refactor/requirements.md REQ-1.6
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from services.database import get_supabase
from services import composition_service


# ============================================================================
# Internal helpers
# ============================================================================

def _build_products_snapshot(composed_items: List[Dict]) -> List[Dict]:
    """Serialize composed items into the products snapshot shape.

    Composed items come from ``composition_service.get_composed_items`` and
    carry identity + supplier-side pricing + traceability fields. The snapshot
    preserves the composed shape verbatim, normalising numeric fields to float
    so they are JSON-serializable inside the ``input_variables`` JSONB column.
    """
    products: List[Dict] = []
    for item in composed_items:
        products.append({
            # Identity — from invoice_item (supplier-side) via composition
            "product_name": item.get("product_name"),
            "supplier_sku": item.get("supplier_sku"),
            "brand": item.get("brand"),
            "quantity": item.get("quantity"),

            # Pricing — from invoice_item
            "purchase_price_original": (
                float(item["purchase_price_original"])
                if item.get("purchase_price_original") is not None
                else None
            ),
            "purchase_currency": item.get("purchase_currency"),
            "base_price_vat": (
                float(item["base_price_vat"])
                if item.get("base_price_vat") is not None
                else None
            ),

            # Supplier-side attrs — from invoice_item
            "weight_in_kg": (
                float(item["weight_in_kg"])
                if item.get("weight_in_kg") is not None
                else None
            ),
            "customs_code": item.get("customs_code"),
            "supplier_country": item.get("supplier_country"),

            # Traceability — carries split/merge structure forward for audit
            "quote_item_id": item.get("quote_item_id"),
            "invoice_item_id": item.get("invoice_item_id"),
            "invoice_id": item.get("invoice_id"),
            "coverage_ratio": item.get("coverage_ratio"),
        })
    return products


# ============================================================================
# Public API
# ============================================================================

def create_quote_version(
    quote_id: str,
    user_id: str,
    variables: Dict[str, Any],
    results: List[Dict],
    totals: Dict[str, Any],
    change_reason: str = "Calculation",
    customer_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create immutable snapshot of quote state.

    The products snapshot is sourced from
    ``composition_service.get_composed_items(quote_id, supabase)`` at snapshot
    creation time — callers do NOT pass items in. This guarantees the snapshot
    captures the authoritative composed shape at this instant, independent of
    whatever the caller happened to fetch earlier.

    Args:
        quote_id: Quote UUID
        user_id: User UUID creating the version
        variables: Calculation variables used
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

    # Source items from composition_service at snapshot time (Phase 5d Pattern A)
    composed_items = composition_service.get_composed_items(quote_id, supabase)
    products_snapshot = _build_products_snapshot(composed_items)

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
        .is_("deleted_at", None) \
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
        .is_("deleted_at", None) \
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
        "total_quote_currency": (input_vars.get("totals") or {}).get("total_with_vat", 0),
        "change_reason": input_vars.get("change_reason", ""),
        "created_at": v.get("created_at"),
        "created_by": v.get("created_by"),
        "seller_company": v.get("seller_company"),
        "offer_incoterms": v.get("offer_incoterms"),
        "currency_of_quote": v.get("currency_of_quote")
    }


def get_current_quote_version(quote_id: str, org_id: str) -> Optional[Dict]:
    """
    Get the current (latest) version for a quote.

    Args:
        quote_id: Quote UUID
        org_id: Organization UUID (for security)

    Returns:
        Latest version record or None if no versions exist
    """
    supabase = get_supabase()

    # Verify quote belongs to org
    quote = supabase.table("quotes") \
        .select("id, current_version_id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote.data:
        return None

    # Get latest version by version number
    result = supabase.table("quote_versions") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("version", desc=True) \
        .limit(1) \
        .execute()

    if not result.data:
        return None

    v = result.data[0]
    input_vars = v.get("input_variables") or {}

    return {
        "id": v["id"],
        "quote_id": v["quote_id"],
        "version_number": v.get("version", 1),
        "status": v.get("status", "sent"),
        "quote_variables": input_vars.get("variables", {}),
        "products_snapshot": input_vars.get("products", []),
        "exchange_rates_used": input_vars.get("exchange_rate", {}),
        "calculation_results": input_vars.get("results", []),
        "totals": input_vars.get("totals", {}),
        "total_quote_currency": (input_vars.get("totals") or {}).get("total_with_vat", 0),
        "change_reason": input_vars.get("change_reason", ""),
        "created_at": v.get("created_at"),
        "created_by": v.get("created_by"),
        "seller_company": v.get("seller_company"),
        "offer_incoterms": v.get("offer_incoterms"),
        "currency_of_quote": v.get("currency_of_quote")
    }


def can_update_version(quote_id: str, org_id: str) -> tuple[bool, str]:
    """
    Check if the current version can be updated (based on КП workflow_status).

    Protection rule: If КП is sent_to_client → versions are immutable.
    Only create new versions, can't update existing ones.

    Args:
        quote_id: Quote UUID
        org_id: Organization UUID (for security)

    Returns:
        Tuple of (can_update: bool, reason: str)
    """
    supabase = get_supabase()

    quote = supabase.table("quotes") \
        .select("id, workflow_status") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote.data:
        return False, "КП не найдено"

    workflow_status = quote.data[0].get("workflow_status", "draft")

    # КП sent to client → versions are immutable
    protected_statuses = ["sent_to_client", "client_negotiation", "deal", "pending_spec_control", "pending_signature"]
    if workflow_status in protected_statuses:
        return False, f"КП уже отправлено клиенту (статус: {workflow_status}). Можно только создать новую версию."

    return True, "OK"


def update_quote_version(
    version_id: str,
    quote_id: str,
    org_id: str,
    user_id: str,
    variables: Dict[str, Any],
    results: List[Dict],
    totals: Dict[str, Any],
    change_reason: str = "Updated"
) -> Dict[str, Any]:
    """
    Update existing version (if КП not sent to client).

    Like ``create_quote_version``, the products snapshot is sourced from
    ``composition_service.get_composed_items(quote_id, supabase)`` at call
    time. Callers do NOT pass items in.

    Args:
        version_id: Version UUID to update
        quote_id: Quote UUID
        org_id: Organization UUID (for security)
        user_id: User UUID making the update
        variables: Calculation variables used
        results: List of calculation results
        totals: Quote totals
        change_reason: Reason for update

    Returns:
        Updated version record

    Raises:
        ValueError: If version can't be updated (КП sent to client)
    """
    supabase = get_supabase()

    # Check if version can be updated
    can_update, reason = can_update_version(quote_id, org_id)
    if not can_update:
        raise ValueError(reason)

    # Convert Decimal to float in variables
    vars_for_storage = {
        k: float(v) if isinstance(v, Decimal) else v
        for k, v in variables.items()
    }

    # Source items from composition_service at snapshot time (Phase 5d Pattern A)
    composed_items = composition_service.get_composed_items(quote_id, supabase)
    products_snapshot = _build_products_snapshot(composed_items)

    # Build input_variables JSONB
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
        "change_reason": change_reason,
        "updated_at": datetime.now().isoformat(),
        "updated_by": user_id
    }

    # Update version
    update_data = {
        "input_variables": input_variables,
        "seller_company": variables.get("seller_company", ""),
        "offer_sale_type": variables.get("offer_sale_type", "поставка"),
        "offer_incoterms": variables.get("offer_incoterms", "DDP"),
        "currency_of_quote": variables.get("currency_of_quote", "USD"),
    }

    result = supabase.table("quote_versions") \
        .update(update_data) \
        .eq("id", version_id) \
        .eq("quote_id", quote_id) \
        .execute()

    if not result.data:
        raise ValueError("Не удалось обновить версию")

    version = result.data[0]

    # Update quote timestamp
    try:
        supabase.table("quotes").update({
            "delivery_terms": variables.get("offer_incoterms", ""),
            "updated_at": datetime.now().isoformat()
        }).eq("id", quote_id).execute()
    except Exception:
        pass

    return version
