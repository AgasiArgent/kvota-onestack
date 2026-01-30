"""
Price Offer Service

Manages multiple supplier price offers per quote item.
Allows procurement to compare 2-5 offers and select the best one.

Based on Gemini code with organization_id support and max 5 offers limit.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from services.database import get_supabase


MAX_OFFERS_PER_ITEM = 5


@dataclass
class PriceOffer:
    """Represents a supplier price offer for a quote item."""
    id: UUID
    quote_item_id: UUID
    supplier_id: UUID
    organization_id: UUID
    price: Decimal
    currency: str
    production_days: int
    is_selected: bool
    notes: Optional[str]
    created_at: datetime
    created_by: Optional[UUID]
    # Joined fields
    supplier_name: Optional[str] = None
    supplier_country: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "PriceOffer":
        """Create PriceOffer from database row."""
        # Handle joined supplier data
        supplier_name = None
        supplier_country = None
        if "suppliers" in data and data["suppliers"]:
            supplier_name = data["suppliers"].get("name")
            supplier_country = data["suppliers"].get("country")

        return cls(
            id=UUID(data["id"]),
            quote_item_id=UUID(data["quote_item_id"]),
            supplier_id=UUID(data["supplier_id"]),
            organization_id=UUID(data["organization_id"]),
            price=Decimal(str(data["price"])),
            currency=data["currency"],
            production_days=data.get("production_days") or 0,
            is_selected=data.get("is_selected", False),
            notes=data.get("notes"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            created_by=UUID(data["created_by"]) if data.get("created_by") else None,
            supplier_name=supplier_name,
            supplier_country=supplier_country,
        )


def get_offers_for_item(quote_item_id: str) -> List[PriceOffer]:
    """
    Get all price offers for a quote item.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        List of PriceOffer objects, selected first, then by price ascending
    """
    supabase = get_supabase()

    result = supabase.table("item_price_offers") \
        .select("*, suppliers(name, country)") \
        .eq("quote_item_id", quote_item_id) \
        .order("is_selected", desc=True) \
        .order("price", desc=False) \
        .execute()

    return [PriceOffer.from_dict(row) for row in (result.data or [])]


def get_offer_by_id(offer_id: str) -> Optional[PriceOffer]:
    """
    Get a single price offer by ID.

    Args:
        offer_id: UUID of the offer

    Returns:
        PriceOffer or None if not found
    """
    supabase = get_supabase()

    result = supabase.table("item_price_offers") \
        .select("*, suppliers(name, country)") \
        .eq("id", offer_id) \
        .limit(1) \
        .execute()

    if not result.data:
        return None

    return PriceOffer.from_dict(result.data[0])


def count_offers_for_item(quote_item_id: str) -> int:
    """
    Count offers for a quote item.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        Number of offers
    """
    supabase = get_supabase()

    result = supabase.table("item_price_offers") \
        .select("id", count="exact") \
        .eq("quote_item_id", quote_item_id) \
        .execute()

    return result.count or 0


def get_organization_id_for_item(quote_item_id: str) -> Optional[str]:
    """
    Get organization_id for a quote_item by traversing through quote.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        Organization UUID string or None
    """
    supabase = get_supabase()

    result = supabase.table("quote_items") \
        .select("quotes(organization_id)") \
        .eq("id", quote_item_id) \
        .limit(1) \
        .execute()

    if result.data and result.data[0].get("quotes"):
        return result.data[0]["quotes"].get("organization_id")
    return None


def create_offer(
    quote_item_id: str,
    supplier_id: str,
    price: Decimal,
    currency: str,
    production_days: int = 0,
    notes: Optional[str] = None,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None
) -> PriceOffer:
    """
    Create a new price offer.

    Args:
        quote_item_id: UUID of the quote item
        supplier_id: UUID of the supplier
        price: Price amount
        currency: Currency code (USD, EUR, RUB, etc.)
        production_days: Production time in days
        notes: Optional notes
        user_id: UUID of the user creating the offer
        organization_id: Organization UUID (fetched automatically if not provided)

    Returns:
        Created PriceOffer

    Raises:
        ValueError: If max offers limit reached
    """
    # Check max offers limit
    current_count = count_offers_for_item(quote_item_id)
    if current_count >= MAX_OFFERS_PER_ITEM:
        raise ValueError(f"Максимум {MAX_OFFERS_PER_ITEM} предложений на позицию. Удалите старые предложения.")

    # Get organization_id if not provided
    if not organization_id:
        organization_id = get_organization_id_for_item(quote_item_id)
        if not organization_id:
            raise ValueError("Не удалось определить организацию для позиции")

    supabase = get_supabase()

    data = {
        "quote_item_id": quote_item_id,
        "supplier_id": supplier_id,
        "organization_id": organization_id,
        "price": float(price),
        "currency": currency,
        "production_days": production_days,
        "notes": notes,
        "created_by": user_id,
    }

    print(f"[DEBUG] create_offer: Inserting data: {data}")

    try:
        result = supabase.table("item_price_offers") \
            .insert(data) \
            .execute()
        print(f"[DEBUG] create_offer: Insert result.data={result.data}, count={result.count}")
    except Exception as e:
        print(f"[DEBUG] create_offer: Insert exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise

    if not result.data:
        print(f"[DEBUG] create_offer: result.data is empty!")
        raise ValueError("Не удалось создать предложение")

    # Fetch with joined supplier name
    return get_offer_by_id(result.data[0]["id"])


def select_offer(offer_id: str) -> bool:
    """
    Select a price offer (deselects all others for same item).
    Uses atomic stored procedure for race condition safety.
    Also syncs selected data to quote_items table.

    Args:
        offer_id: UUID of the offer to select

    Returns:
        True if successful, False on error
    """
    try:
        supabase = get_supabase()
        # Stored procedure handles: deselect old → select new → sync to quote_items
        supabase.rpc("select_price_offer", {"p_offer_id": offer_id}).execute()
        return True
    except Exception as e:
        print(f"Error selecting offer {offer_id}: {e}")
        return False


def deselect_all_for_item(quote_item_id: str) -> bool:
    """
    Deselect all offers for a quote item.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        True if successful
    """
    try:
        supabase = get_supabase()
        supabase.table("item_price_offers") \
            .update({"is_selected": False, "updated_at": datetime.utcnow().isoformat()}) \
            .eq("quote_item_id", quote_item_id) \
            .execute()
        return True
    except Exception as e:
        print(f"Error deselecting offers for item {quote_item_id}: {e}")
        return False


def delete_offer(offer_id: str) -> bool:
    """
    Delete a price offer.

    Args:
        offer_id: UUID of the offer to delete

    Returns:
        True if deleted, False if not found
    """
    supabase = get_supabase()

    result = supabase.table("item_price_offers") \
        .delete() \
        .eq("id", offer_id) \
        .execute()

    return len(result.data or []) > 0


def get_selected_offer(quote_item_id: str) -> Optional[PriceOffer]:
    """
    Get the currently selected offer for a quote item.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        Selected PriceOffer or None
    """
    supabase = get_supabase()

    result = supabase.table("item_price_offers") \
        .select("*, suppliers(name, country)") \
        .eq("quote_item_id", quote_item_id) \
        .eq("is_selected", True) \
        .limit(1) \
        .execute()

    if not result.data:
        return None

    return PriceOffer.from_dict(result.data[0])


def clear_quote_item_price(quote_item_id: str) -> bool:
    """
    Clear price-related fields from quote_items when selected offer is deleted.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        True if successful
    """
    try:
        supabase = get_supabase()
        supabase.table("quote_items") \
            .update({
                "purchase_price_original": None,
                "purchase_currency": None,
                "supplier_id": None,
                "production_time_days": None,
            }) \
            .eq("id", quote_item_id) \
            .execute()
        return True
    except Exception as e:
        print(f"Error clearing quote item price {quote_item_id}: {e}")
        return False


def get_offers_summary_for_quote(quote_id: str) -> dict:
    """
    Get a summary of offers for all items in a quote.

    Args:
        quote_id: UUID of the quote

    Returns:
        Dict mapping item_id -> {count: int, has_selected: bool}
    """
    supabase = get_supabase()

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .execute()

    if not items_result.data:
        return {}

    item_ids = [item["id"] for item in items_result.data]

    # Get all offers for these items
    offers_result = supabase.table("item_price_offers") \
        .select("quote_item_id, is_selected") \
        .in_("quote_item_id", item_ids) \
        .execute()

    # Build summary
    summary = {item_id: {"count": 0, "has_selected": False} for item_id in item_ids}

    for offer in (offers_result.data or []):
        item_id = offer["quote_item_id"]
        if item_id in summary:
            summary[item_id]["count"] += 1
            if offer["is_selected"]:
                summary[item_id]["has_selected"] = True

    return summary
