"""
Deal Data Service

Helper functions for fetching and enriching deal-related data.
Extracted from main.py to enable reuse in api/deals.py and main.py.

Functions:
  fetch_items_with_buyer_companies — Resolve composed items with buyer_company_id
    (Pattern A, Phase 5d §2.1.5 — sources items via composition_service, not raw quote_items)
  fetch_enrichment_data — Fetch contracts and bank accounts for currency invoice enrichment
"""

import logging

from services.composition_service import get_composed_items

logger = logging.getLogger(__name__)


def fetch_items_with_buyer_companies(supabase, quote_id: str) -> tuple[list[dict], dict[str, dict]]:
    """Fetch composition-aware items enriched with buyer_company_id.

    Pattern A (Phase 5d, design.md §2.1.5): items originate from
    ``composition_service.get_composed_items`` — the final calc-ready shape
    already joined with the selected invoice_items (supplier-side pricing).
    We DO NOT read raw ``kvota.quote_items`` here; legacy price columns
    (``purchase_price_original``, ``purchase_currency``) come through the
    composed layer.

    ``buyer_company_id`` lives on the ``invoices`` table (not on
    quote_items and not on invoice_items). Each composed item carries the
    ``invoice_id`` of its selected supplier offer — we resolve the buyer
    company via that link.

    Args:
        supabase: Supabase client instance.
        quote_id: UUID of the quote.

    Returns:
        Tuple of (items_list, bc_lookup_dict).
        items_list: composed items with ``buyer_company_id`` populated.
        bc_lookup_dict: mapping of buyer_company_id to company info dict.
    """
    items = get_composed_items(quote_id, supabase)

    inv_resp = supabase.table("invoices").select(
        "id, buyer_company_id, buyer_companies!buyer_company_id(id, name, country, region)"
    ).eq("quote_id", quote_id).execute()
    inv_data = inv_resp.data or []

    bc_lookup: dict[str, dict] = {}
    inv_bc_map: dict[str, str] = {}
    for inv in inv_data:
        bc = (inv.get("buyer_companies") or {})
        if bc and bc.get("id"):
            bc_lookup[bc["id"]] = bc
            inv_bc_map[inv["id"]] = bc["id"]

    enriched_items: list[dict] = []
    for item in items:
        enriched = {**item}
        if not enriched.get("buyer_company_id") and enriched.get("invoice_id"):
            enriched["buyer_company_id"] = inv_bc_map.get(enriched["invoice_id"])
        enriched_items.append(enriched)

    return enriched_items, bc_lookup


def fetch_enrichment_data(supabase, org_id: str) -> tuple[list[dict], list[dict]]:
    """Fetch active currency contracts and bank accounts for an organization.

    Used to enrich currency invoice generation with contract/bank details.

    Args:
        supabase: Supabase client instance.
        org_id: UUID of the organization.

    Returns:
        Tuple of (contracts_list, bank_accounts_list).
        On failure returns ([], []) so that invoice generation can proceed
        without enrichment.
    """
    try:
        contracts_resp = supabase.table("currency_contracts").select("*").eq(
            "organization_id", org_id
        ).eq("is_active", True).execute()
        contracts = contracts_resp.data or []
    except Exception as e:
        logger.warning("Could not fetch currency_contracts for org %s: %s", org_id, e)
        contracts = []

    try:
        bank_accounts_resp = supabase.table("bank_accounts").select("*").eq(
            "organization_id", org_id
        ).eq("is_active", True).execute()
        bank_accounts = bank_accounts_resp.data or []
    except Exception as e:
        logger.warning("Could not fetch bank_accounts for org %s: %s", org_id, e)
        bank_accounts = []

    return contracts, bank_accounts
