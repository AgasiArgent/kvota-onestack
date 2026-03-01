"""
PHMB Price Service

Data access for PHMB price lists, brand-type discounts, settings, and quote items.
Supports the PHMB quotation workflow: price lookup -> discount application -> calculation -> quote items.
"""

from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone
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
        item_id = item.get("id")
        if not item_id:
            logger.warning("Skipping calculated item update: missing 'id'")
            continue
        update_payload = {k: v for k, v in item.items() if k != "id"}
        sb.table("phmb_quote_items").update(update_payload).eq(
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


# =============================================================================
# Brand Groups
# =============================================================================

def resolve_brand_group(brand: str | None, groups: list[dict]) -> str | None:
    """Resolve which brand group a brand belongs to (pure function, no DB).

    Loops groups sorted by sort_order, checks if brand (case-insensitive)
    matches any pattern in brand_patterns. Falls back to the catchall group
    if no pattern matches.

    Args:
        brand: Brand name to resolve (case-insensitive). None/empty -> catchall.
        groups: List of brand group dicts with keys: id, brand_patterns,
                is_catchall, sort_order.

    Returns:
        The group_id (str) of the matching group, or None if no match
        and no catchall group exists.
    """
    if not groups:
        return None

    brand_lower = (brand or "").strip().lower()

    # Sort by sort_order to ensure deterministic priority
    sorted_groups = sorted(groups, key=lambda g: g.get("sort_order", 0))

    catchall_id = None

    for group in sorted_groups:
        if group.get("is_catchall"):
            catchall_id = group["id"]
            continue

        patterns = group.get("brand_patterns") or []
        for pattern in patterns:
            if pattern.lower() == brand_lower:
                return group["id"]

    # No pattern matched — return catchall if exists
    return catchall_id


def get_brand_groups(org_id: str) -> list[dict]:
    """Get all brand groups for an organization, sorted by sort_order.

    Returns:
        List of brand group dicts.
    """
    sb = get_supabase()
    result = (
        sb.table("phmb_brand_groups")
        .select("*")
        .eq("org_id", org_id)
        .order("sort_order")
        .execute()
    )
    return result.data or []


def upsert_brand_group(
    org_id: str,
    group_id: str | None,
    name: str,
    brand_patterns: list[str],
    is_catchall: bool,
    sort_order: int,
) -> dict:
    """Create or update a brand group.

    Args:
        org_id: Organization UUID.
        group_id: Existing group UUID to update, or None to create new.
        name: Group display name.
        brand_patterns: List of brand strings belonging to this group.
        is_catchall: Whether this is the catchall group.
        sort_order: Sort order for display and priority.

    Returns:
        The upserted brand group row.
    """
    sb = get_supabase()
    payload = {
        "org_id": org_id,
        "name": name,
        "brand_patterns": brand_patterns,
        "is_catchall": is_catchall,
        "sort_order": sort_order,
    }
    if group_id:
        payload["id"] = group_id

    result = sb.table("phmb_brand_groups").upsert(payload).execute()
    return result.data[0] if result.data else {}


def delete_brand_group(group_id: str, org_id: str) -> bool:
    """Delete a brand group by ID (scoped to org).

    Returns:
        True if a group was deleted, False otherwise.
    """
    sb = get_supabase()
    result = (
        sb.table("phmb_brand_groups")
        .delete()
        .eq("id", group_id)
        .eq("org_id", org_id)
        .execute()
    )
    return bool(result.data)


# =============================================================================
# Procurement Queue
# =============================================================================

def get_procurement_queue(
    org_id: str,
    brand_group_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Get procurement queue items for an org with optional filters.

    Joins with phmb_quote_items and quotes for display data.

    Args:
        org_id: Organization UUID.
        brand_group_id: Optional filter by brand group.
        status: Optional filter by queue status ('new', 'requested', 'priced').

    Returns:
        List of queue item dicts with FK join data.
    """
    sb = get_supabase()
    query = (
        sb.table("phmb_procurement_queue")
        .select("*, phmb_quote_items!quote_item_id(*), quotes!quote_id(*)")
        .eq("org_id", org_id)
    )

    if brand_group_id:
        query = query.eq("brand_group_id", brand_group_id)
    if status:
        query = query.eq("status", status)

    query = query.order("created_at")
    result = query.execute()
    return result.data or []


def enqueue_phmb_item(
    org_id: str,
    quote_item_id: str,
    quote_id: str,
    brand: str,
    groups: list[dict],
) -> dict:
    """Insert a single item into the procurement queue.

    Resolves the brand group and creates the queue entry with status='new'.

    Args:
        org_id: Organization UUID.
        quote_item_id: PHMB quote item UUID.
        quote_id: Quote UUID.
        brand: Brand name for group resolution.
        groups: List of brand group dicts for resolve_brand_group().

    Returns:
        The inserted queue row.
    """
    sb = get_supabase()
    brand_group_id = resolve_brand_group(brand, groups)

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "org_id": org_id,
        "quote_item_id": quote_item_id,
        "quote_id": quote_id,
        "brand": brand or "",
        "brand_group_id": brand_group_id,
        "status": "new",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    result = sb.table("phmb_procurement_queue").insert(payload).execute()
    return result.data[0] if result.data else {}


def update_queue_item_status(
    queue_item_id: str,
    status: str,
    priced_rmb: float | None = None,
) -> dict:
    """Update the status of a queue item.

    Args:
        queue_item_id: Queue item UUID.
        status: New status ('new', 'requested', 'priced').
        priced_rmb: Price in RMB (required when status='priced').

    Returns:
        The updated queue row.
    """
    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    update_data = {
        "status": status,
        "updated_at": now_iso,
    }
    if priced_rmb is not None:
        update_data["priced_rmb"] = priced_rmb

    result = (
        sb.table("phmb_procurement_queue")
        .update(update_data)
        .eq("id", queue_item_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def price_queue_item(
    org_id: str,
    queue_item_id: str,
    priced_rmb: float,
) -> dict:
    """Price a queue item: write back to quote item + upsert into price list.

    This is the critical write-back flow:
    1. Validate priced_rmb > 0
    2. Fetch queue row with FK join to phmb_quote_items
    3. Update queue status to 'priced' with priced_rmb
    4. Write list_price_rmb back to phmb_quote_items
    5. Upsert into phmb_price_list (if cat_number is not empty)

    Args:
        org_id: Organization UUID.
        queue_item_id: Queue item UUID.
        priced_rmb: Price in RMB (must be > 0).

    Returns:
        The queue row dict.

    Raises:
        ValueError: If priced_rmb <= 0 or queue item not found.
    """
    if priced_rmb <= 0:
        raise ValueError(f"priced_rmb must be > 0, got {priced_rmb}")

    sb = get_supabase()

    # 1. Fetch queue row with FK join to get quote item data
    q_result = (
        sb.table("phmb_procurement_queue")
        .select("*, phmb_quote_items!quote_item_id(*)")
        .eq("id", queue_item_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not q_result.data:
        raise ValueError(f"Queue item {queue_item_id} not found")

    queue_row = q_result.data[0]
    quote_item = (queue_row.get("phmb_quote_items") or {})

    now_iso = datetime.now(timezone.utc).isoformat()

    # 2. Update queue status to 'priced'
    sb.table("phmb_procurement_queue").update({
        "status": "priced",
        "priced_rmb": priced_rmb,
        "updated_at": now_iso,
    }).eq("id", queue_item_id).execute()

    # 3. Write price back to quote item
    sb.table("phmb_quote_items").update({
        "list_price_rmb": priced_rmb,
        "updated_at": now_iso,
    }).eq("id", queue_row["quote_item_id"]).execute()

    # 4. Upsert into price list (skip if cat_number is empty)
    cat_number = quote_item.get("cat_number", "")
    if cat_number:
        sb.table("phmb_price_list").upsert({
            "org_id": org_id,
            "cat_number": cat_number,
            "product_name": quote_item.get("product_name", ""),
            "brand": quote_item.get("brand", ""),
            "product_classification": quote_item.get("product_classification", ""),
            "list_price_rmb": priced_rmb,
        }, on_conflict="org_id,cat_number").execute()

    return queue_row


def ensure_queue_entries(quote_id: str, org_id: str) -> None:
    """Backfill queue entries for unpriced items in a quote.

    Finds items with phmb_price_list_id IS NULL and no existing queue entry,
    then enqueues them. This is a lazy backfill called on PHMB tab load.

    IMPORTANT: This function must never raise exceptions -- it logs errors
    and returns silently. It must not break the tab load.

    Args:
        quote_id: Quote UUID.
        org_id: Organization UUID.
    """
    try:
        sb = get_supabase()

        # Fetch all quote items
        items_result = (
            sb.table("phmb_quote_items")
            .select("*")
            .eq("quote_id", quote_id)
            .is_("phmb_price_list_id", "null")
            .order("created_at")
            .execute()
        )
        unpriced_items = items_result.data or []

        if not unpriced_items:
            return

        # Fetch existing queue entries for this quote
        queue_result = (
            sb.table("phmb_procurement_queue")
            .select("quote_item_id")
            .eq("quote_id", quote_id)
            .execute()
        )
        existing_queue_item_ids = {
            row["quote_item_id"] for row in (queue_result.data or [])
        }

        # Get brand groups for resolution
        groups = get_brand_groups(org_id)

        # Enqueue items that are not yet in the queue
        for item in unpriced_items:
            if item["id"] not in existing_queue_item_ids:
                try:
                    enqueue_phmb_item(
                        org_id=org_id,
                        quote_item_id=item["id"],
                        quote_id=quote_id,
                        brand=item.get("brand", ""),
                        groups=groups,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to enqueue item {item['id']}: {e}"
                    )

    except Exception as e:
        logger.warning(f"ensure_queue_entries failed for quote {quote_id}: {e}")
