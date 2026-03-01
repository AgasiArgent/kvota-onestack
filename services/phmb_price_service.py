"""
PHMB Price Service

Data access for PHMB price lists, brand-type discounts, settings, and quote items.
Supports the PHMB quotation workflow: price lookup -> discount application -> calculation -> quote items.
"""

from decimal import Decimal
from typing import Optional
import logging

from services.database import get_supabase

logger = logging.getLogger(__name__)


# =============================================================================
# Settings CRUD
# =============================================================================

def get_phmb_settings(org_id: str) -> dict | None:
    """Get PHMB settings for an organization.

    Returns settings dict or None if not configured yet.
    """
    sb = get_supabase()
    result = sb.table("phmb_settings").select("*").eq("org_id", org_id).execute()
    return result.data[0] if result.data else None


def upsert_phmb_settings(org_id: str, data: dict) -> dict:
    """Create or update PHMB settings for an organization.

    Args:
        org_id: Organization UUID.
        data: Settings fields to upsert (logistics_price_per_pallet,
              base_price_per_pallet, exchange_rate_insurance_pct, etc.).

    Returns:
        The upserted settings row.
    """
    sb = get_supabase()
    payload = {**data, "org_id": org_id}
    result = sb.table("phmb_settings").upsert(
        payload, on_conflict="org_id"
    ).execute()
    return result.data[0] if result.data else {}


# =============================================================================
# Brand-Type Discounts
# =============================================================================

def get_brand_type_discounts(org_id: str) -> list[dict]:
    """Get all brand-type discount records for an organization.

    Returns list of dicts sorted by brand, then product_classification.
    """
    sb = get_supabase()
    result = (
        sb.table("phmb_brand_type_discounts")
        .select("*")
        .eq("org_id", org_id)
        .order("brand")
        .order("product_classification")
        .execute()
    )
    return result.data or []


def get_discount_for_brand_type(
    org_id: str, brand: str, product_classification: str
) -> Decimal:
    """Get the discount percentage for a specific brand + product classification.

    Returns Decimal("0") if no matching discount is configured.
    """
    sb = get_supabase()
    result = (
        sb.table("phmb_brand_type_discounts")
        .select("discount_pct")
        .eq("org_id", org_id)
        .eq("brand", brand)
        .eq("product_classification", product_classification)
        .limit(1)
        .execute()
    )
    if result.data:
        return Decimal(str(result.data[0]["discount_pct"]))
    return Decimal("0")


def upsert_brand_type_discount(
    org_id: str, brand: str, product_classification: str, discount_pct: float
) -> dict:
    """Create or update a brand-type discount.

    Args:
        org_id: Organization UUID.
        brand: Brand name (e.g. "Grundfos").
        product_classification: Product type/class (e.g. "Pumps").
        discount_pct: Discount percentage (e.g. 15.0 for 15%).

    Returns:
        The upserted discount row.
    """
    sb = get_supabase()
    payload = {
        "org_id": org_id,
        "brand": brand,
        "product_classification": product_classification,
        "discount_pct": discount_pct,
    }
    result = sb.table("phmb_brand_type_discounts").upsert(
        payload, on_conflict="org_id,brand,product_classification"
    ).execute()
    return result.data[0] if result.data else {}


# =============================================================================
# Price List Search
# =============================================================================

def search_price_list(
    org_id: str, query: str, limit: int = 20
) -> list[dict]:
    """Search the PHMB price list by catalog number or product name.

    Uses ILIKE for trigram-indexed search. Each result is enriched with
    the applicable discount_pct from phmb_brand_type_discounts (0 if none).

    Args:
        org_id: Organization UUID.
        query: Search string (matched against cat_number and product_name).
        limit: Maximum results to return.

    Returns:
        List of price list dicts, each with an added "discount_pct" field.
    """
    sb = get_supabase()
    escaped = query.replace("%", "\\%").replace("_", "\\_")
    result = (
        sb.table("phmb_price_list")
        .select("*")
        .eq("org_id", org_id)
        .or_(f"cat_number.ilike.%{escaped}%,product_name.ilike.%{escaped}%")
        .limit(limit)
        .execute()
    )
    items = result.data or []

    if not items:
        return []

    # Batch-fetch discounts for unique brand+classification combos in results
    brand_class_pairs = {
        (item.get("brand", ""), item.get("product_classification", ""))
        for item in items
    }
    discounts = _get_discount_map(org_id, brand_class_pairs)

    for item in items:
        key = (item.get("brand", ""), item.get("product_classification", ""))
        item["discount_pct"] = float(discounts.get(key, Decimal("0")))

    return items


def _get_discount_map(
    org_id: str, brand_class_pairs: set[tuple[str, str]]
) -> dict[tuple[str, str], Decimal]:
    """Fetch discount percentages for a set of (brand, classification) pairs.

    Returns a dict mapping (brand, classification) -> Decimal discount_pct.
    """
    if not brand_class_pairs:
        return {}

    sb = get_supabase()
    result = (
        sb.table("phmb_brand_type_discounts")
        .select("brand,product_classification,discount_pct")
        .eq("org_id", org_id)
        .execute()
    )
    discount_map: dict[tuple[str, str], Decimal] = {}
    for row in result.data or []:
        key = (row["brand"], row["product_classification"])
        if key in brand_class_pairs:
            discount_map[key] = Decimal(str(row["discount_pct"]))
    return discount_map


# =============================================================================
# PHMB Quote Items
# =============================================================================

def add_phmb_item(
    quote_id: str, price_list_id: Optional[str], item_data: dict
) -> dict:
    """Add a PHMB item to a quote.

    Args:
        quote_id: Quote UUID.
        price_list_id: Optional reference to phmb_price_list row.
        item_data: Dict with item fields (cat_number, product_name, brand,
                   product_classification, quantity, list_price_rmb,
                   discount_pct, hs_code, duty_pct, delivery_days, etc.).

    Returns:
        The inserted phmb_quote_items row.
    """
    sb = get_supabase()
    payload = {
        **item_data,
        "quote_id": quote_id,
        "phmb_price_list_id": price_list_id,
    }
    result = sb.table("phmb_quote_items").insert(payload).execute()
    return result.data[0] if result.data else {}


def get_phmb_items(quote_id: str) -> list[dict]:
    """Get all PHMB items for a quote, ordered by creation time.

    Returns:
        List of phmb_quote_items dicts.
    """
    sb = get_supabase()
    result = (
        sb.table("phmb_quote_items")
        .select("*")
        .eq("quote_id", quote_id)
        .order("created_at")
        .execute()
    )
    return result.data or []


def update_phmb_items_calculated(
    quote_id: str, calculated_items: list[dict]
) -> None:
    """Bulk update calculated fields on PHMB quote items.

    Each dict in calculated_items must contain "id" plus any calculated fields
    to update (exw_price_usd, cogs_usd, financial_cost_usd, total_price_usd,
    total_price_with_vat_usd).

    Args:
        quote_id: Quote UUID (used for safety filter).
        calculated_items: List of dicts, each with "id" and calculated fields.
    """
    sb = get_supabase()
    for item in calculated_items:
        item_id = item.pop("id", None)
        if not item_id:
            logger.warning("Skipping calculated item update: missing 'id'")
            continue
        sb.table("phmb_quote_items").update(item).eq(
            "id", item_id
        ).eq("quote_id", quote_id).execute()


def delete_phmb_item(item_id: str) -> bool:
    """Delete a PHMB quote item by ID.

    Returns:
        True if an item was deleted, False otherwise.
    """
    sb = get_supabase()
    result = sb.table("phmb_quote_items").delete().eq("id", item_id).execute()
    return bool(result.data)
