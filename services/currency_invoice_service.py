"""
Currency Invoice Generation Service

Pure-logic service for generating internal currency invoices between group
companies. No database calls in generation functions -- they return plain
dicts ready for persistence.

Segments:
  EURTR -- EU supplier sells to Turkish intermediary
  TRRU  -- Turkish intermediary sells to Russian buyer (seller_company)

Price markup is applied cumulatively:
  EURTR: base_price * (1 + markup/100)
  TRRU from EU chain: base_price * (1 + eurtr_markup/100) * (1 + trru_markup/100)
  TRRU from TR chain: base_price * (1 + markup/100)
"""

from decimal import Decimal
from collections import defaultdict


def calculate_segment_price(
    base_price: Decimal,
    segment: str,
    markup_percent: Decimal,
    prior_markup_percent: Decimal | None,
) -> Decimal:
    """Calculate the marked-up price for a given segment.

    Args:
        base_price: Original purchase price.
        segment: 'EURTR' or 'TRRU'.
        markup_percent: Markup percentage for this segment.
        prior_markup_percent: Markup from the prior segment (EURTR) if this
            item comes from an EU chain. None for direct chains.

    Returns:
        Price after applying markup(s).
    """
    if prior_markup_percent is not None:
        # Cumulative: apply prior markup first, then current
        price = base_price * (1 + prior_markup_percent / Decimal("100")) * (1 + markup_percent / Decimal("100"))
    else:
        # Single markup
        price = base_price * (1 + markup_percent / Decimal("100"))
    return price


def build_invoice_number(
    quote_idn: str,
    currency: str,
    segment: str,
    sequence: int,
) -> str:
    """Build a deterministic invoice number.

    Format: CI-{quote_idn}-{currency}-{segment}-{sequence}

    Args:
        quote_idn: Quote IDN (e.g. 'Q202601-0004').
        currency: Three-letter currency code (e.g. 'EUR').
        segment: 'EURTR' or 'TRRU'.
        sequence: Sequential number within the same currency+segment.

    Returns:
        Invoice number string.
    """
    return f"CI-{quote_idn}-{currency}-{segment}-{sequence}"


def group_items_by_buyer_company(items: list[dict]) -> dict[str, list]:
    """Group deal items by their buyer_company_id.

    Args:
        items: List of item dicts, each must have 'buyer_company_id'.

    Returns:
        Dict mapping buyer_company_id to list of items.
    """
    groups: dict[str, list] = defaultdict(list)
    for item in items:
        bc_id = item.get("buyer_company_id")
        if bc_id:
            groups[bc_id].append(item)
        else:
            print(f"Warning: item {item.get('id')} has no buyer_company_id, skipping from currency invoices")
    return dict(groups)


def _build_item_snapshot(
    item: dict,
    segment: str,
    markup_percent: Decimal,
    prior_markup_percent: Decimal | None,
    sort_order: int,
) -> dict:
    """Create an invoice item snapshot dict from a source item.

    Maps source field names to invoice item field names:
      brand -> manufacturer
      purchase_price_original -> base_price
    """
    base_price = Decimal(str(item.get("purchase_price_original") or 0))
    price = calculate_segment_price(base_price, segment, markup_percent, prior_markup_percent)
    price = price.quantize(Decimal("0.0001"))
    quantity = Decimal(str(item.get("quantity") or 0))
    total = (quantity * price).quantize(Decimal("0.01"))

    return {
        "source_item_id": item.get("id"),
        "product_name": item.get("product_name", ""),
        "sku": item.get("sku", ""),
        "idn_sku": item.get("idn_sku", ""),
        "manufacturer": item.get("brand", ""),
        "quantity": quantity,
        "unit": item.get("unit", "pcs"),
        "hs_code": item.get("hs_code", ""),
        "base_price": base_price,
        "price": price,
        "total": total,
        "sort_order": sort_order,
    }


def generate_currency_invoices(
    deal_id: str,
    quote_idn: str,
    items: list[dict],
    buyer_companies: dict[str, dict],
    seller_company: dict,
    organization_id: str,
    markup_percent: Decimal = Decimal("2.0"),
) -> list[dict]:
    """Generate currency invoice dicts from deal items (pure logic, no DB).

    Business rules:
      - EU buyer_company -> 2 segments: EURTR + TRRU
      - TR buyer_company -> 1 segment: TRRU only
      - TRRU invoice aggregates ALL items across chains
      - EU items in TRRU carry cumulative markup (EURTR + TRRU)
      - TR items in TRRU carry single markup

    Args:
        deal_id: UUID of the deal.
        quote_idn: Quote IDN for invoice numbering.
        items: List of quote item dicts with buyer_company_id, purchase_price_original, etc.
        buyer_companies: Dict mapping buyer_company_id to company info (must have 'country').
        seller_company: Seller company dict with 'id', 'name', 'entity_type'.
        organization_id: Organization UUID.
        markup_percent: Markup percentage per segment (default 2.0%).

    Returns:
        List of invoice dicts ready for DB insertion.
    """
    groups = group_items_by_buyer_company(items)

    invoices: list[dict] = []
    # Collect all TRRU items across groups
    trru_items: list[dict] = []
    trru_source_invoice_ids: list[str] = []
    trru_item_currencies: list[str] = []
    # Track sequence numbers per (currency, segment)
    seq_counters: dict[tuple[str, str], int] = defaultdict(int)

    for bc_id, group_items in groups.items():
        bc = buyer_companies.get(bc_id, {})
        country = bc.get("country", "")

        if country == "EU":
            # --- EURTR invoice: EU buyer sells to Turkish intermediary ---
            currency = group_items[0].get("purchase_currency", "EUR")
            seq_counters[(currency, "EURTR")] += 1
            seq = seq_counters[(currency, "EURTR")]

            eurtr_items_snapshot = []
            eurtr_total = Decimal("0")
            for idx, item in enumerate(group_items):
                snapshot = _build_item_snapshot(
                    item, "EURTR", markup_percent, prior_markup_percent=None, sort_order=idx,
                )
                eurtr_items_snapshot.append(snapshot)
                eurtr_total += snapshot["total"]

            eurtr_invoice = {
                "deal_id": deal_id,
                "segment": "EURTR",
                "invoice_number": build_invoice_number(quote_idn, currency, "EURTR", seq),
                "seller_entity_type": "buyer_company",
                "seller_entity_id": bc.get("id"),
                "buyer_entity_type": None,
                "buyer_entity_id": None,
                "markup_percent": markup_percent,
                "total_amount": eurtr_total,
                "currency": currency,
                "status": "draft",
                "source_invoice_ids": [],
                "organization_id": organization_id,
                "items": eurtr_items_snapshot,
            }
            invoices.append(eurtr_invoice)

            # Prepare TRRU items for EU chain (cumulative markup)
            for idx, item in enumerate(group_items):
                snapshot = _build_item_snapshot(
                    item, "TRRU", markup_percent, prior_markup_percent=markup_percent, sort_order=idx,
                )
                trru_items.append(snapshot)
                trru_item_currencies.append(item.get("purchase_currency", "USD"))

        elif country == "TR":
            # TR buyer -> TRRU only (single markup)
            for idx, item in enumerate(group_items):
                snapshot = _build_item_snapshot(
                    item, "TRRU", markup_percent, prior_markup_percent=None, sort_order=idx,
                )
                trru_items.append(snapshot)
                trru_item_currencies.append(item.get("purchase_currency", "USD"))

    # --- TRRU invoice: Turkish intermediary sells to Russian buyer ---
    if trru_items:
        # Re-number sort_order sequentially across all TRRU items
        for idx, item in enumerate(trru_items):
            item["sort_order"] = idx

        trru_total = sum(item["total"] for item in trru_items)
        # Determine currency by majority vote among TRRU items, default USD if tied
        if trru_item_currencies:
            currency_counts: dict[str, int] = defaultdict(int)
            for c in trru_item_currencies:
                currency_counts[c] += 1
            max_count = max(currency_counts.values())
            most_common = [c for c, cnt in currency_counts.items() if cnt == max_count]
            trru_currency = most_common[0] if len(most_common) == 1 else "USD"
        else:
            trru_currency = "USD"

        seq_counters[(trru_currency, "TRRU")] += 1
        seq = seq_counters[(trru_currency, "TRRU")]

        trru_invoice = {
            "deal_id": deal_id,
            "segment": "TRRU",
            "invoice_number": build_invoice_number(quote_idn, trru_currency, "TRRU", seq),
            "seller_entity_type": None,
            "seller_entity_id": None,
            "buyer_entity_type": seller_company.get("entity_type", "seller_company"),
            "buyer_entity_id": seller_company.get("id"),
            "markup_percent": markup_percent,
            "total_amount": trru_total,
            "currency": trru_currency,
            "status": "draft",
            "source_invoice_ids": trru_source_invoice_ids,
            "organization_id": organization_id,
            "items": trru_items,
        }
        invoices.append(trru_invoice)

    return invoices


def save_currency_invoices(supabase, invoices: list[dict]) -> list[dict]:
    """Persist generated currency invoices to the database.

    Inserts into currency_invoices and currency_invoice_items tables.

    Args:
        supabase: Supabase client instance.
        invoices: List of invoice dicts from generate_currency_invoices.

    Returns:
        List of inserted invoice records (with IDs).
    """
    saved = []
    for inv in invoices:
        items = inv.get("items", [])
        # Convert Decimal fields to float for JSON serialization
        inv_to_insert = {k: v for k, v in inv.items() if k != "items"}
        if isinstance(inv_to_insert.get("markup_percent"), Decimal):
            inv_to_insert["markup_percent"] = float(inv_to_insert["markup_percent"])
        if isinstance(inv_to_insert.get("total_amount"), Decimal):
            inv_to_insert["total_amount"] = float(inv_to_insert["total_amount"])
        resp = supabase.table("currency_invoices").insert(inv_to_insert).execute()
        invoice_record = resp.data[0] if resp.data else {}
        invoice_id = invoice_record.get("id")

        if invoice_id and items:
            items_to_insert = []
            for item in items:
                serialized = {**item, "currency_invoice_id": invoice_id}
                for field in ("base_price", "price", "total", "quantity"):
                    if isinstance(serialized.get(field), Decimal):
                        serialized[field] = float(serialized[field])
                items_to_insert.append(serialized)
            supabase.table("currency_invoice_items").insert(items_to_insert).execute()

        invoice_record["items"] = items
        saved.append(invoice_record)
    return saved
