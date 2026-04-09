"""
Deal Creation API endpoint for Next.js frontend and AI agents.

POST /api/deals — Create a deal from a confirmed specification

Auth: During migration, body contains user_id, org_id (trusted internal call).
      Post-migration: JWT via ApiAuthMiddleware (request.state.api_user).
Roles: sales, admin
"""

import logging
from datetime import date, datetime

from starlette.responses import JSONResponse

from services.database import get_supabase
from services.deal_data_service import fetch_items_with_buyer_companies, fetch_enrichment_data
from services.logistics_service import initialize_logistics_stages
from services.currency_invoice_service import generate_currency_invoices, save_currency_invoices

logger = logging.getLogger(__name__)


def _generate_deal_number(sb, org_id: str) -> str:
    """Generate sequential deal number: DEAL-{year}-{NNNN}.

    Counts existing deals for the current year within the organization.
    """
    year = date.today().year
    count_result = (
        sb.table("deals")
        .select("id", count="exact")
        .eq("organization_id", org_id)
        .gte("created_at", f"{year}-01-01")
        .execute()
    )
    seq_num = (count_result.count or 0) + 1
    return f"DEAL-{year}-{seq_num:04d}"


def _try_generate_invoices(
    sb, deal_id: str, quote_id: str, quote_idn: str,
    seller_company: dict, org_id: str,
) -> tuple[int, str | None]:
    """Attempt to generate and save currency invoices.

    Returns (invoices_created, skip_reason).
    Non-fatal: deal creation succeeds even if invoices fail.
    """
    try:
        items, bc_lookup = fetch_items_with_buyer_companies(sb, quote_id)
    except Exception as e:
        logger.error("Failed to fetch items for invoice generation (deal %s): %s", deal_id, e)
        return 0, f"Invoice generation failed: {e}"

    if not items:
        return 0, "No items in quote"

    if not bc_lookup:
        return 0, "No buyer companies assigned to quote items"

    if not seller_company or not seller_company.get("id"):
        return 0, "No seller company on quote"

    try:
        contracts, bank_accounts = fetch_enrichment_data(sb, org_id)

        invoices = generate_currency_invoices(
            deal_id=deal_id,
            quote_idn=quote_idn,
            items=items,
            buyer_companies=bc_lookup,
            seller_company=seller_company,
            organization_id=org_id,
            contracts=contracts,
            bank_accounts=bank_accounts,
        )

        if invoices:
            save_currency_invoices(sb, invoices)
            return len(invoices), None

        return 0, "No invoices generated (no matching buyer company regions)"
    except Exception as e:
        logger.error("Invoice generation failed for deal %s: %s", deal_id, e)
        return 0, f"Invoice generation failed: {e}"


async def create_deal(request) -> JSONResponse:
    """Create a deal from a confirmed specification.

    Path: POST /api/deals
    Params:
        spec_id: str (required) — Specification to convert to deal
        user_id: str (required) — Acting user
        org_id: str (required) — Organization
    Returns:
        deal_id: str — Created deal UUID
        deal_number: str — Generated deal number (DEAL-{year}-{NNNN})
        logistics_stages: int — Number of logistics stages created (always 7)
        invoices_created: int — Number of currency invoices generated
        invoices_skipped_reason: str | null — Why invoices were skipped
    Side Effects:
        - Updates specification status to 'signed'
        - Updates quote workflow_status to 'deal'
        - Creates 7 logistics stages for the deal
        - Generates currency invoices (when data available)
    Roles: sales, admin
    """
    # --- Parse request body ---
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    spec_id = body.get("spec_id")
    user_id = body.get("user_id")
    org_id = body.get("org_id")

    if not spec_id:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "spec_id is required"}},
            status_code=400,
        )
    if not user_id:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required"}},
            status_code=400,
        )
    if not org_id:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "org_id is required"}},
            status_code=400,
        )

    sb = get_supabase()

    # --- Step 1: Validate specification ---
    try:
        spec_resp = sb.table("specifications").select(
            "id, quote_id, organization_id, sign_date, signed_scan_url, status"
        ).eq("id", spec_id).execute()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid spec_id format"}},
            status_code=400,
        )

    if not spec_resp.data:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Specification not found"}},
            status_code=404,
        )

    spec = spec_resp.data[0]

    if spec["organization_id"] != org_id:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Specification not found"}},
            status_code=404,
        )

    if not spec.get("signed_scan_url"):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Signed scan not uploaded"}},
            status_code=400,
        )

    quote_id = spec["quote_id"]

    # --- Step 2: Fetch quote data ---
    quote_resp = sb.table("quotes").select(
        "id, total_amount, currency, idn_quote, seller_company_id, "
        "seller_companies!seller_company_id(id, name)"
    ).eq("id", quote_id).single().execute()

    if not quote_resp.data:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )

    quote = quote_resp.data
    total_amount = quote.get("total_amount")
    currency = quote.get("currency")
    quote_idn = quote.get("idn_quote", "")
    sc = (quote.get("seller_companies") or {})
    seller_company = {"id": sc.get("id"), "name": sc.get("name"), "entity_type": "seller_company"} if sc.get("id") else {}

    # --- Step 3: Generate deal number ---
    deal_number = _generate_deal_number(sb, org_id)

    # --- Step 4: Update specification status to 'signed' ---
    try:
        sb.table("specifications").update({
            "status": "signed",
            "updated_at": datetime.now().isoformat(),
        }).eq("id", spec_id).execute()
    except Exception as e:
        logger.error("Failed to update specification %s status: %s", spec_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to update specification status"}},
            status_code=500,
        )

    # --- Step 5: Create deal record ---
    deal_sign_date = spec.get("sign_date") or date.today().isoformat()

    deal_data = {
        "specification_id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "deal_number": deal_number,
        "signed_at": deal_sign_date,
        "total_amount": float(total_amount) if total_amount else 0.0,
        "currency": currency,
        "status": "active",
        "created_by": user_id,
    }

    try:
        deal_result = sb.table("deals").insert(deal_data).execute()
    except Exception as e:
        logger.error("Failed to create deal for spec %s: %s", spec_id, e)
        # Rollback spec status
        try:
            sb.table("specifications").update({
                "status": spec.get("status", "draft"),
                "updated_at": datetime.now().isoformat(),
            }).eq("id", spec_id).execute()
        except Exception as rollback_err:
            logger.error("Failed to rollback specification %s status: %s", spec_id, rollback_err)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to create deal"}},
            status_code=500,
        )

    if not deal_result.data:
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Deal insert returned no data"}},
            status_code=500,
        )

    deal_id = deal_result.data[0]["id"]

    # --- Step 6: Update quote workflow_status to 'deal' ---
    try:
        sb.table("quotes").update({
            "workflow_status": "deal",
            "updated_at": datetime.now().isoformat(),
        }).eq("id", quote_id).execute()
    except Exception as e:
        logger.error("Failed to update quote %s workflow_status: %s", quote_id, e)
        # Non-fatal: deal exists, log for manual repair

    # --- Step 7: Initialize logistics stages ---
    try:
        stages = initialize_logistics_stages(deal_id, user_id)
        logistics_stages_count = len(stages) if stages else 0
    except Exception as e:
        logger.error("Failed to initialize logistics stages for deal %s: %s", deal_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to initialize logistics stages"}},
            status_code=500,
        )

    # --- Step 8: Generate currency invoices (non-fatal) ---
    invoices_created, invoices_skipped_reason = _try_generate_invoices(
        sb=sb,
        deal_id=deal_id,
        quote_id=quote_id,
        quote_idn=quote_idn,
        seller_company=seller_company,
        org_id=org_id,
    )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "deal_id": deal_id,
                "deal_number": deal_number,
                "logistics_stages": logistics_stages_count,
                "invoices_created": invoices_created,
                "invoices_skipped_reason": invoices_skipped_reason,
            },
        },
        status_code=201,
    )
