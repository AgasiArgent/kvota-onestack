"""
Deal Data Service

Helper functions for fetching and enriching deal-related data.
Extracted from main.py to enable reuse in api/deals.py and main.py.

Functions:
  fetch_items_with_buyer_companies — Resolve quote items with buyer_company_id from invoices
  fetch_enrichment_data — Fetch contracts and bank accounts for currency invoice enrichment
"""

import logging

logger = logging.getLogger(__name__)


def fetch_items_with_buyer_companies(supabase, quote_id: str) -> tuple[list[dict], dict[str, dict]]:
    """Fetch quote items enriched with buyer_company_id from invoices.

    buyer_company_id lives on the invoices table, not on quote_items.
    Items link to invoices via quote_items.invoice_id.
    This function resolves that indirection and returns items with
    buyer_company_id set, plus a bc_lookup dict of buyer companies.

    Args:
        supabase: Supabase client instance.
        quote_id: UUID of the quote.

    Returns:
        Tuple of (items_list, bc_lookup_dict).
        items_list: quote items with buyer_company_id populated.
        bc_lookup_dict: mapping of buyer_company_id to company info dict.
    """
    items_resp = supabase.table("quote_items").select("*").eq("quote_id", quote_id).execute()
    items = items_resp.data or []

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

    enriched_items = []
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
