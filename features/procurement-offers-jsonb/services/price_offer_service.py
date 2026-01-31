"""
Price Offer Service (JSONB Version)

Manages multiple supplier price offers stored as JSONB array in quote_items.
Single source of truth - no sync needed between tables.

Architecture: price_offers JSONB column in quote_items
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from services.database import get_supabase


@dataclass
class PriceOffer:
    """Represents a supplier price offer (from JSONB)."""
    id: str
    supplier_id: str
    supplier_name: str
    price: Decimal
    currency: str
    production_days: int
    is_selected: bool
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "PriceOffer":
        """Create PriceOffer from JSONB dict."""
        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(
                    str(data["created_at"]).replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return cls(
            id=data["id"],
            supplier_id=data["supplier_id"],
            supplier_name=data.get("supplier_name", "Unknown"),
            price=Decimal(str(data["price"])),
            currency=data["currency"],
            production_days=data.get("production_days") or 0,
            is_selected=data.get("is_selected", False),
            created_at=created_at,
        )


def get_offers_for_item(quote_item_id: str) -> List[PriceOffer]:
    """
    Get all price offers for a quote item.
    Reads directly from quote_items.price_offers JSONB.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        List of PriceOffer objects, selected first, then by price
    """
    supabase = get_supabase()

    result = supabase.table("quote_items") \
        .select("price_offers") \
        .eq("id", quote_item_id) \
        .limit(1) \
        .execute()

    if not result.data or not result.data[0].get("price_offers"):
        return []

    offers_json = result.data[0]["price_offers"]
    offers = [PriceOffer.from_dict(o) for o in offers_json]

    # Sort: selected first, then by price ascending
    return sorted(offers, key=lambda o: (not o.is_selected, o.price))


def get_offer_by_id(quote_item_id: str, offer_id: str) -> Optional[PriceOffer]:
    """
    Get a single offer by ID from JSONB array.

    Args:
        quote_item_id: UUID of the quote item
        offer_id: ID of the offer within JSONB

    Returns:
        PriceOffer or None
    """
    offers = get_offers_for_item(quote_item_id)
    return next((o for o in offers if o.id == offer_id), None)


def create_offer(
    quote_item_id: str,
    supplier_id: str,
    supplier_name: str,
    price: Decimal,
    currency: str,
    production_days: int = 0,
) -> str:
    """
    Create a new price offer (adds to JSONB array).
    Uses stored procedure for atomicity and validation.

    Args:
        quote_item_id: UUID of the quote item
        supplier_id: UUID of the supplier
        supplier_name: Supplier name (denormalized for display)
        price: Price amount
        currency: Currency code
        production_days: Production time in days

    Returns:
        ID of created offer

    Raises:
        ValueError: If max offers (5) reached
    """
    supabase = get_supabase()

    result = supabase.rpc("add_jsonb_offer", {
        "p_item_id": quote_item_id,
        "p_supplier_id": supplier_id,
        "p_supplier_name": supplier_name,
        "p_price": float(price),
        "p_currency": currency,
        "p_production_days": production_days,
    }).execute()

    # RPC returns the new offer ID
    return result.data


def select_offer(quote_item_id: str, offer_id: str) -> bool:
    """
    Select a price offer (deselects all others).
    Also updates main quote_item fields (supplier_id, price, etc.)
    Uses atomic stored procedure.

    Args:
        quote_item_id: UUID of the quote item
        offer_id: ID of the offer to select

    Returns:
        True if successful
    """
    try:
        supabase = get_supabase()
        supabase.rpc("select_jsonb_offer", {
            "p_item_id": quote_item_id,
            "p_offer_id": offer_id,
        }).execute()
        return True
    except Exception as e:
        print(f"Error selecting offer {offer_id}: {e}")
        return False


def delete_offer(quote_item_id: str, offer_id: str) -> bool:
    """
    Delete a price offer from JSONB array.
    If deleted offer was selected, clears main quote_item fields.

    Args:
        quote_item_id: UUID of the quote item
        offer_id: ID of the offer to delete

    Returns:
        True if deleted offer was selected (main fields cleared)
    """
    try:
        supabase = get_supabase()
        result = supabase.rpc("delete_jsonb_offer", {
            "p_item_id": quote_item_id,
            "p_offer_id": offer_id,
        }).execute()
        return result.data  # Returns whether deleted offer was selected
    except Exception as e:
        print(f"Error deleting offer {offer_id}: {e}")
        return False


def get_selected_offer(quote_item_id: str) -> Optional[PriceOffer]:
    """
    Get the currently selected offer.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        Selected PriceOffer or None
    """
    offers = get_offers_for_item(quote_item_id)
    return next((o for o in offers if o.is_selected), None)


def count_offers_for_item(quote_item_id: str) -> int:
    """
    Count offers for a quote item.

    Args:
        quote_item_id: UUID of the quote item

    Returns:
        Number of offers (0-5)
    """
    return len(get_offers_for_item(quote_item_id))


# ============================================================================
# Convenience functions for UI
# ============================================================================

def get_item_with_offers(quote_item_id: str) -> dict:
    """
    Get quote item with parsed offers in one call.
    Useful for rendering procurement form.

    Returns:
        dict with item fields + 'offers' list of PriceOffer
    """
    supabase = get_supabase()

    result = supabase.table("quote_items") \
        .select("*, suppliers(name, supplier_code)") \
        .eq("id", quote_item_id) \
        .limit(1) \
        .execute()

    if not result.data:
        return None

    item = result.data[0]
    offers_json = item.get("price_offers") or []
    item["offers"] = [PriceOffer.from_dict(o) for o in offers_json]
    item["offers"].sort(key=lambda o: (not o.is_selected, o.price))

    return item
