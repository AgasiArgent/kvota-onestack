"""Quote action endpoints migrated from main.py legacy @rt decorators.

Not a FastAPI router module — this is a handler module (parallel to
``api/procurement.py``, ``api/composition.py``, ``api/soft_delete.py``).
Registered via thin wrappers in ``api/routers/quotes.py``.

Currently hosts:
  - ``calculate_quote`` — POST /api/quotes/{quote_id}/calculate
  - ``submit_procurement`` — POST /api/quotes/{quote_id}/submit-procurement
  - ``cancel_quote`` — POST /api/quotes/{quote_id}/cancel
  - ``transition_workflow`` — POST /api/quotes/{quote_id}/workflow/transition

Auth: dual — JWT via ``ApiAuthMiddleware`` (Next.js) OR legacy session
(FastHTML). Response shape is byte-identical to the pre-extraction handler
in main.py so existing callers (calculation-action-bar.tsx, sales-action-bar
.tsx) continue to work unchanged.
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, cast

from starlette.requests import Request
from starlette.responses import JSONResponse

from calculation_engine import calculate_multiproduct_quote
from calculation_mapper import safe_decimal, safe_int
from services.composition_service import get_composed_items
from services.currency_service import convert_amount
from services.database import get_supabase
from services.quote_version_service import (
    can_update_version,
    create_quote_version,
    get_current_quote_version,
    list_quote_versions,
    update_quote_version,
)
from services.role_service import get_user_role_codes
from services.workflow_service import (
    complete_customs as wf_complete_customs,
    complete_procurement,
    transition_quote_status,
    transition_to_pending_procurement,
)

logger = logging.getLogger(__name__)

__all__ = [
    "calculate_quote",
    "submit_procurement",
    "cancel_quote",
    "transition_workflow",
]


async def calculate_quote(
    request: Request,
    quote_id: str,
) -> JSONResponse:
    """Execute calculation engine and return JSON results.

    Path: POST /api/quotes/{quote_id}/calculate
    Auth: dual — JWT (Next.js) first, then legacy session (FastHTML).
    Params (JSON body or form):
        currency, markup, supplier_discount, exchange_rate, delivery_time,
        seller_company, offer_sale_type, offer_incoterms, version_action,
        change_reason, logistics/brokerage fields, DM fee fields, payment-
        term fields.
    Returns:
        success: bool
        total, total_no_vat, profit, margin, currency, cogs, logistics,
        brokerage, customs, vat: float
    Side Effects:
        - Updates quotes totals + exchange-rate columns
        - Upserts quote_calculation_variables
        - Upserts quote_calculation_results (one row per item)
        - Updates quote_items.base_price_vat
        - Upserts quote_calculation_summaries
        - Creates/updates quote_versions snapshot
        - Transitions workflow when partial_recalc == 'price'
    Roles: sales, admin (authorization delegated to RLS on the underlying
           tables — this handler only checks auth + org membership).
    """

    from services.calculation_helpers import build_calculation_inputs

    # Dual auth: JWT (Next.js) first, then legacy session (FastHTML).
    # Starlette exposes the session via request.session when SessionMiddleware
    # is installed (FastHTML's fast_app does this).
    api_user = getattr(request.state, 'api_user', None)
    if api_user:
        user_id = str(api_user.id)
        # Look up org_id from organization_members (not in JWT metadata)
        supabase = get_supabase()
        om = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
        org_id = om.data[0]["organization_id"] if om.data else None
        user = {
            "id": user_id,
            "email": api_user.email or "",
            "org_id": org_id,
        }
    else:
        try:
            session = request.session
        except (AssertionError, AttributeError):
            session = None
        if not session:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        user = session.get("user", {})

    if not user.get("id"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    org_id = user.get("org_id")
    if not org_id:
        return JSONResponse({"error": "No organization"}, status_code=403)

    # Dual input: JSON (Next.js) or form (FastHTML)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        body = dict(await request.form())

    supabase = get_supabase()

    # Get quote
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"error": "Quote not found"}, status_code=404)

    quote = cast(dict, quote_result.data[0])

    # Get items via composition_service (Phase 5b): overlays purchase price
    # fields from invoice_item_prices when the item has an active composition
    # pointer, otherwise returns the quote_items row unchanged. The dict shape
    # is identical to a plain quote_items SELECT, so build_calculation_inputs()
    # sees no difference.
    items = get_composed_items(quote_id, supabase)

    if not items:
        return JSONResponse({"error": "Cannot calculate - no products in quote"}, status_code=400)

    # Extract parameters from body
    currency = str(body.get("currency") or quote.get("currency") or "USD")
    markup = body.get("markup", "15")
    supplier_discount = body.get("supplier_discount", "0")
    exchange_rate = body.get("exchange_rate", "1.0")
    delivery_time = body.get("delivery_time", "30")
    seller_company = body.get("seller_company", "")
    offer_sale_type = body.get("offer_sale_type", "поставка")
    offer_incoterms = body.get("offer_incoterms", "DDP")
    version_action = body.get("version_action", "auto")
    change_reason = body.get("change_reason", "")

    # Logistics
    logistics_supplier_hub = body.get("logistics_supplier_hub", "0")
    logistics_hub_customs = body.get("logistics_hub_customs", "0")
    logistics_customs_client = body.get("logistics_customs_client", "0")

    # Brokerage
    brokerage_hub = body.get("brokerage_hub", "0")
    brokerage_hub_currency = body.get("brokerage_hub_currency", "RUB")
    brokerage_customs = body.get("brokerage_customs", "0")
    brokerage_customs_currency = body.get("brokerage_customs_currency", "RUB")
    warehousing_at_customs = body.get("warehousing_at_customs", "0")
    warehousing_at_customs_currency = body.get("warehousing_at_customs_currency", "RUB")
    customs_documentation = body.get("customs_documentation", "0")
    customs_documentation_currency = body.get("customs_documentation_currency", "RUB")
    brokerage_extra = body.get("brokerage_extra", "0")
    brokerage_extra_currency = body.get("brokerage_extra_currency", "RUB")

    # Payment terms
    advance_from_client = body.get("advance_from_client", "100")
    advance_to_supplier = body.get("advance_to_supplier", "100")
    time_to_advance = body.get("time_to_advance", "0")
    time_to_advance_on_receiving = body.get("time_to_advance_on_receiving", "0")

    # DM Fee
    dm_fee_type = body.get("dm_fee_type", "fixed")
    dm_fee_value = body.get("dm_fee_value", "0")
    dm_fee_currency = body.get("dm_fee_currency", "RUB")

    # Validate that all available items have prices
    items_without_price = []
    for item in items:
        if item.get("is_unavailable"):
            continue
        price = safe_decimal(item.get("purchase_price_original") or item.get("base_price_vat"))
        if price <= 0:
            item_name = item.get("product_name", "—")
            item_brand = item.get("brand", "")
            item_label = f"{item_brand} — {item_name}" if item_brand else item_name
            items_without_price.append(item_label)

    if items_without_price:
        return JSONResponse({
            "error": "Not all items have prices",
            "items_without_price": items_without_price,
        }, status_code=400)

    try:
        # Aggregate logistics from invoices
        form_logistics_supplier_hub = safe_decimal(logistics_supplier_hub)
        form_logistics_hub_customs = safe_decimal(logistics_hub_customs)
        form_logistics_customs_client = safe_decimal(logistics_customs_client)

        # Aggregate delivery time from invoices + items
        max_logistics_days = 0
        max_production_days = 0

        for item in items:
            prod_days = int(item.get("production_time_days") or 0)
            if prod_days > max_production_days:
                max_production_days = prod_days

        invoices_days_result = supabase.table("invoices") \
            .select("logistics_total_days") \
            .eq("quote_id", quote_id) \
            .execute()

        for inv in (invoices_days_result.data or []):
            log_days = int(inv.get("logistics_total_days") or 0)
            if log_days > max_logistics_days:
                max_logistics_days = log_days

        aggregated_delivery_time = max_logistics_days + max_production_days
        form_delivery_time = safe_int(delivery_time)
        effective_delivery_time = max(aggregated_delivery_time, form_delivery_time)

        # Aggregate logistics from invoices (source of truth)
        invoices_result = supabase.table("invoices") \
            .select("logistics_supplier_to_hub, logistics_hub_to_customs, logistics_customs_to_customer, "
                    "logistics_supplier_to_hub_currency, logistics_hub_to_customs_currency, logistics_customs_to_customer_currency") \
            .eq("quote_id", quote_id) \
            .execute()

        invoices_logistics = invoices_result.data or []

        if invoices_logistics:
            total_logistics_supplier_hub = Decimal(0)
            total_logistics_hub_customs = Decimal(0)
            total_logistics_customs_client = Decimal(0)

            for inv in invoices_logistics:
                s2h_amount = Decimal(str(inv.get("logistics_supplier_to_hub") or 0))
                s2h_currency = str(inv.get("logistics_supplier_to_hub_currency") or "USD")
                if s2h_amount > 0:
                    total_logistics_supplier_hub += convert_amount(s2h_amount, s2h_currency, "USD")

                h2c_amount = Decimal(str(inv.get("logistics_hub_to_customs") or 0))
                h2c_currency = str(inv.get("logistics_hub_to_customs_currency") or "USD")
                if h2c_amount > 0:
                    total_logistics_hub_customs += convert_amount(h2c_amount, h2c_currency, "USD")

                c2c_amount = Decimal(str(inv.get("logistics_customs_to_customer") or 0))
                c2c_currency = str(inv.get("logistics_customs_to_customer_currency") or "USD")
                if c2c_amount > 0:
                    total_logistics_customs_client += convert_amount(c2c_amount, c2c_currency, "USD")

            form_logistics_supplier_hub = total_logistics_supplier_hub
            form_logistics_hub_customs = total_logistics_hub_customs
            form_logistics_customs_client = total_logistics_customs_client

        # Build variables
        variables: Dict[str, Any] = {
            'currency_of_quote': currency,
            'markup': safe_decimal(markup),
            'supplier_discount': safe_decimal(supplier_discount),
            'offer_incoterms': offer_incoterms,
            'delivery_time': effective_delivery_time,
            'seller_company': seller_company,
            'offer_sale_type': offer_sale_type,
            'logistics_supplier_hub': form_logistics_supplier_hub,
            'logistics_hub_customs': form_logistics_hub_customs,
            'logistics_customs_client': form_logistics_customs_client,
            'brokerage_hub': safe_decimal(brokerage_hub),
            'brokerage_hub_currency': brokerage_hub_currency,
            'brokerage_customs': safe_decimal(brokerage_customs),
            'brokerage_customs_currency': brokerage_customs_currency,
            'warehousing_at_customs': safe_decimal(warehousing_at_customs),
            'warehousing_at_customs_currency': warehousing_at_customs_currency,
            'customs_documentation': safe_decimal(customs_documentation),
            'customs_documentation_currency': customs_documentation_currency,
            'brokerage_extra': safe_decimal(brokerage_extra),
            'brokerage_extra_currency': brokerage_extra_currency,
            'advance_from_client': safe_decimal(advance_from_client),
            'advance_to_supplier': safe_decimal(advance_to_supplier),
            'time_to_advance': safe_int(time_to_advance),
            'time_to_advance_on_receiving': safe_int(time_to_advance_on_receiving),
            'dm_fee_type': dm_fee_type,
            'dm_fee_value': safe_decimal(dm_fee_value),
            'dm_fee_currency': dm_fee_currency,
            'exchange_rate': safe_decimal(exchange_rate),
        }

        # Build calculation inputs and run engine
        calc_inputs = build_calculation_inputs(items, variables)
        results = calculate_multiproduct_quote(calc_inputs)

        # Calculate totals
        total_purchase = sum(safe_decimal(r.purchase_price_total_quote_currency) for r in results)
        total_logistics = sum(safe_decimal(r.logistics_total) for r in results)
        total_brokerage = (
            safe_decimal(variables['brokerage_hub']) +
            safe_decimal(variables['brokerage_customs']) +
            safe_decimal(variables['warehousing_at_customs']) +
            safe_decimal(variables['customs_documentation']) +
            safe_decimal(variables['brokerage_extra'])
        )
        total_cogs = sum(safe_decimal(r.cogs_per_product) for r in results)
        total_profit = sum(safe_decimal(r.profit) for r in results)
        total_no_vat = sum(safe_decimal(r.sales_price_total_no_vat) for r in results)
        total_with_vat = sum(safe_decimal(r.sales_price_total_with_vat) for r in results)
        total_vat = sum(safe_decimal(r.vat_net_payable) for r in results)
        total_customs = sum(safe_decimal(r.customs_fee) for r in results)
        avg_margin = (total_profit / total_cogs * 100) if total_cogs else Decimal("0")

        # Exchange rate to USD for analytics
        if currency == 'USD':
            exchange_rate_to_usd = Decimal("1.0")
        else:
            exchange_rate_to_usd = safe_decimal(convert_amount(Decimal("1"), currency, 'USD'))
            if exchange_rate_to_usd == 0:
                exchange_rate_to_usd = Decimal("1.0")

        subtotal_usd = total_purchase * exchange_rate_to_usd
        total_amount_usd = total_with_vat * exchange_rate_to_usd
        total_profit_usd = total_profit * exchange_rate_to_usd

        # Update quote totals
        supabase.table("quotes").update({
            "subtotal": float(total_purchase),
            "total_amount": float(total_with_vat),
            "total_profit_usd": float(total_profit_usd),
            "total_quote_currency": float(total_with_vat),
            "revenue_no_vat_quote_currency": float(total_no_vat),
            "profit_quote_currency": float(total_profit),
            "cogs_quote_currency": float(total_cogs),
            "exchange_rate_to_usd": float(exchange_rate_to_usd),
            "subtotal_usd": float(subtotal_usd),
            "total_amount_usd": float(total_amount_usd),
            "updated_at": datetime.now().isoformat()
        }).eq("id", quote_id).execute()

        # Store calculation variables
        variables_for_storage = {
            k: float(v) if isinstance(v, Decimal) else v
            for k, v in variables.items()
        }
        variables_record = {
            "quote_id": quote_id,
            "variables": variables_for_storage,
            "updated_at": datetime.now().isoformat()
        }
        existing_vars = supabase.table("quote_calculation_variables") \
            .select("quote_id") \
            .eq("quote_id", quote_id) \
            .execute()
        if existing_vars.data:
            supabase.table("quote_calculation_variables") \
                .update(variables_record) \
                .eq("quote_id", quote_id) \
                .execute()
        else:
            supabase.table("quote_calculation_variables") \
                .insert(variables_record) \
                .execute()

        # Store per-item calculation results
        rate = float(exchange_rate_to_usd)
        for item, result in zip(items, results):
            phase_results = {
                "N16": float(result.purchase_price_no_vat or 0),
                "P16": float(result.purchase_price_after_discount or 0),
                "R16": float(result.purchase_price_per_unit_quote_currency or 0),
                "S16": float(result.purchase_price_total_quote_currency or 0),
                "T16": float(result.logistics_first_leg or 0),
                "U16": float(result.logistics_last_leg or 0),
                "V16": float(result.logistics_total or 0),
                "Y16": float(result.customs_fee or 0),
                "Z16": float(result.excise_tax_amount or 0),
                "AA16": float(result.cogs_per_unit or 0),
                "AB16": float(result.cogs_per_product or 0),
                "AD16": float(result.sale_price_per_unit_excl_financial or 0),
                "AE16": float(result.sale_price_total_excl_financial or 0),
                "AF16": float(result.profit or 0),
                "AG16": float(result.dm_fee or 0),
                "AH16": float(result.forex_reserve or 0),
                "AI16": float(result.financial_agent_fee or 0),
                "AJ16": float(result.sales_price_per_unit_no_vat or 0),
                "AK16": float(result.sales_price_total_no_vat or 0),
                "AL16": float(result.sales_price_total_with_vat or 0),
                "AM16": float(result.sales_price_per_unit_with_vat or 0),
                "AN16": float(result.vat_from_sales or 0),
                "AO16": float(result.vat_on_import or 0),
                "AP16": float(result.vat_net_payable or 0),
                "AQ16": float(result.transit_commission or 0),
                "AX16": float(result.internal_sale_price_per_unit or 0),
                "AY16": float(result.internal_sale_price_total or 0),
                "BA16": float(result.financing_cost_initial or 0),
                "BB16": float(result.financing_cost_credit or 0),
            }
            phase_results_usd = {k: v * rate for k, v in phase_results.items()}

            item_result = {
                "quote_id": quote_id,
                "quote_item_id": item["id"],
                "phase_results": phase_results,
                "phase_results_usd": phase_results_usd,
                "calculated_at": datetime.now().isoformat()
            }
            existing_result = supabase.table("quote_calculation_results") \
                .select("quote_item_id") \
                .eq("quote_item_id", item["id"]) \
                .execute()
            if existing_result.data:
                supabase.table("quote_calculation_results") \
                    .update(item_result) \
                    .eq("quote_item_id", item["id"]) \
                    .execute()
            else:
                supabase.table("quote_calculation_results") \
                    .insert(item_result) \
                    .execute()

            # Update quote_items with calculated prices
            quantity = item.get("quantity", 1)
            base_price_vat_per_unit = float(result.sales_price_total_with_vat) / quantity if quantity > 0 else 0
            supabase.table("quote_items").update({
                "base_price_vat": base_price_vat_per_unit
            }).eq("id", item["id"]).execute()

        # Store calculation summary
        calc_summary = {
            "quote_id": quote_id,
            "calc_s16_total_purchase_price": float(total_purchase),
            "calc_v16_total_logistics": float(total_logistics),
            "calc_y16_customs_duty": float(total_customs),
            "calc_total_brokerage": float(total_brokerage),
            "calc_ae16_sale_price_total": float(total_no_vat),
            "calc_al16_total_with_vat": float(total_with_vat),
            "calc_af16_profit_margin": float(avg_margin),
            "exchange_rate_to_usd": rate,
            "calc_s16_total_purchase_price_usd": float(total_purchase) * rate,
            "calc_v16_total_logistics_usd": float(total_logistics) * rate,
            "calc_y16_customs_duty_usd": float(total_customs) * rate,
            "calc_total_brokerage_usd": float(total_brokerage) * rate,
            "calc_ae16_sale_price_total_usd": float(total_no_vat) * rate,
            "calc_al16_total_with_vat_usd": float(total_with_vat) * rate,
            "calc_af16_total_profit_usd": float(total_profit) * rate,
            "calculated_at": datetime.now().isoformat()
        }
        existing_summary = supabase.table("quote_calculation_summaries") \
            .select("quote_id") \
            .eq("quote_id", quote_id) \
            .execute()
        if existing_summary.data:
            supabase.table("quote_calculation_summaries") \
                .update(calc_summary) \
                .eq("quote_id", quote_id) \
                .execute()
        else:
            supabase.table("quote_calculation_summaries") \
                .insert(calc_summary) \
                .execute()

        # Update quote currency if changed
        if quote.get("currency") != currency:
            supabase.table("quotes") \
                .update({"currency": currency}) \
                .eq("id", quote_id) \
                .execute()

        # Handle partial recalculation
        partial_recalc = quote.get("partial_recalc")
        if partial_recalc == "price":
            supabase.table("quotes").update({
                "partial_recalc": None
            }).eq("id", quote_id).execute()

            user_roles = user.get("roles", [])
            transition_quote_status(
                quote_id=quote_id,
                to_status="client_negotiation",
                actor_id=user["id"],
                actor_roles=user_roles,
                comment="Partial recalculation: price updated, returning to client negotiation"
            )

        # Create or update quote version
        all_results = []
        for item, result in zip(items, results):
            all_results.append({
                "item_id": item["id"],
                "N16": float(result.purchase_price_no_vat or 0),
                "S16": float(result.purchase_price_total_quote_currency or 0),
                "V16": float(result.logistics_total or 0),
                "AB16": float(result.cogs_per_product or 0),
                "AJ16": float(result.sales_price_per_unit_no_vat or 0),
                "AK16": float(result.sales_price_total_no_vat or 0),
                "AL16": float(result.sales_price_total_with_vat or 0),
                "AF16": float(result.profit or 0),
            })

        version_totals = {
            "total_purchase": float(total_purchase),
            "total_logistics": float(total_logistics),
            "total_cogs": float(total_cogs),
            "total_profit": float(total_profit),
            "total_no_vat": float(total_no_vat),
            "total_with_vat": float(total_with_vat),
            "avg_margin": float(avg_margin),
        }

        try:
            existing_versions = list_quote_versions(quote_id, org_id)
            current_version = get_current_quote_version(quote_id, org_id) if existing_versions else None
            reason_text = change_reason if change_reason else "Calculation saved"

            # Phase 5d: items sourced from composition_service inside the
            # snapshot function — not passed as kwarg.
            if not existing_versions:
                create_quote_version(
                    quote_id=quote_id,
                    user_id=user["id"],
                    variables=variables,
                    results=all_results,
                    totals=version_totals,
                    change_reason=reason_text,
                    customer_id=quote.get("customer_id")
                )
            elif version_action == "update" and current_version:
                can_update_flag, _ = can_update_version(quote_id, org_id)
                if can_update_flag:
                    update_quote_version(
                        version_id=current_version["id"],
                        quote_id=quote_id,
                        org_id=org_id,
                        user_id=user["id"],
                        variables=variables,
                        results=all_results,
                        totals=version_totals,
                        change_reason=reason_text
                    )
                else:
                    create_quote_version(
                        quote_id=quote_id,
                        user_id=user["id"],
                        variables=variables,
                        results=all_results,
                        totals=version_totals,
                        change_reason=reason_text,
                        customer_id=quote.get("customer_id")
                    )
            else:
                create_quote_version(
                    quote_id=quote_id,
                    user_id=user["id"],
                    variables=variables,
                    results=all_results,
                    totals=version_totals,
                    change_reason=reason_text,
                    customer_id=quote.get("customer_id")
                )
        except Exception as ve:
            print(f"Warning: Failed to create version: {ve}")

        return JSONResponse({
            "success": True,
            "total": float(total_with_vat),
            "total_no_vat": float(total_no_vat),
            "profit": float(total_profit),
            "margin": float(avg_margin),
            "currency": currency,
            "cogs": float(total_cogs),
            "logistics": float(total_logistics),
            "brokerage": float(total_brokerage),
            "customs": float(total_customs),
            "vat": float(total_vat),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


async def submit_procurement(
    request: Request,
    quote_id: str,
) -> JSONResponse:
    """Submit a draft quote for procurement evaluation with sales checklist.

    Path: POST /api/quotes/{quote_id}/submit-procurement
    Auth: dual — JWT (Next.js) first, then legacy session (FastHTML).
    Body (JSON):
        checklist: object (required)
            is_estimate: bool
            is_tender: bool
            direct_request: bool
            trading_org_request: bool
            equipment_description: str (required, non-empty)
    Returns:
        redirect: str — path to the quote page (on success)
        error: str — error message (on failure)
    Side Effects:
        - Updates quotes.sales_checklist
        - Transitions workflow to pending_procurement
    Roles: sales, admin (authorization enforced by the workflow service).
    """
    # Dual auth: JWT (Next.js) or session (FastHTML)
    api_user = getattr(request.state, 'api_user', None)
    if api_user:
        user_meta = api_user.user_metadata or {}
        org_id = user_meta.get("org_id")
        if not org_id:
            try:
                sb = get_supabase()
                om = sb.table("organization_members").select("organization_id").eq("user_id", str(api_user.id)).eq("status", "active").order("created_at").limit(1).execute()
                if om.data:
                    org_id = om.data[0]["organization_id"]
            except Exception:
                pass
        user = {
            "id": str(api_user.id),
            "email": api_user.email or "",
            "name": user_meta.get("name", api_user.email or ""),
            "org_id": org_id,
            "org_name": user_meta.get("org_name", ""),
        }
        user_roles = get_user_role_codes(user["id"], org_id)
    else:
        try:
            session = request.session
        except (AssertionError, AttributeError):
            session = None
        if not session or not session.get("user"):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        user = session["user"]
        user_roles = user.get("roles", [])
        org_id = user["org_id"]

    if not user or not user.get("id"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Parse checklist from JSON body
    checklist_data = None
    body = None
    try:
        body = await request.body()
        print(f"[SUBMIT-PROCUREMENT] quote_id={quote_id}, body_len={len(body) if body else 0}, roles={user_roles}")
        if body:
            data = json.loads(body)
            checklist_data = data.get("checklist")
    except (json.JSONDecodeError, Exception) as e:
        print(f"[SUBMIT-PROCUREMENT] JSON parse error: {e}, body={body[:200] if body else 'empty'}")

    # Validate checklist is present and has required field
    if not checklist_data or not checklist_data.get("equipment_description", "").strip():
        print(f"[SUBMIT-PROCUREMENT] Checklist validation failed: checklist_data={checklist_data}")
        return JSONResponse({"error": "Заполните контрольный список перед передачей в закупки"}, status_code=400)

    # Save checklist to quotes table
    checklist_to_save = {
        "is_estimate": bool(checklist_data.get("is_estimate", False)),
        "is_tender": bool(checklist_data.get("is_tender", False)),
        "direct_request": bool(checklist_data.get("direct_request", False)),
        "trading_org_request": bool(checklist_data.get("trading_org_request", False)),
        "equipment_description": checklist_data["equipment_description"].strip(),
        "completed_at": datetime.utcnow().isoformat(),
        "completed_by": user["id"]
    }

    supabase = get_supabase()
    try:
        supabase.table("quotes") \
            .update({"sales_checklist": checklist_to_save}) \
            .eq("id", quote_id) \
            .eq("organization_id", org_id) \
            .execute()
    except Exception as e:
        return JSONResponse({"error": f"Ошибка сохранения чеклиста: {str(e)}"}, status_code=500)

    # Use the workflow service to transition to pending_procurement
    result = transition_to_pending_procurement(
        quote_id=quote_id,
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Submitted by sales for procurement evaluation"
    )

    if result.success:
        print(f"[SUBMIT-PROCUREMENT] SUCCESS quote_id={quote_id}")
        return JSONResponse({"redirect": f"/quotes/{quote_id}"})
    else:
        print(f"[SUBMIT-PROCUREMENT] TRANSITION FAILED: {result.error_message}")
        return JSONResponse({"error": f"Ошибка перехода: {result.error_message}"}, status_code=400)


async def cancel_quote(
    request: Request,
    quote_id: str,
) -> JSONResponse:
    """Cancel a quote with mandatory reason.

    Path: POST /api/quotes/{quote_id}/cancel
    Auth: dual — JWT (Next.js) first, then legacy session (FastHTML).
    Body (JSON or form):
        reason: str (required, non-empty) — free-text cancellation reason
    Returns:
        success: bool
        error: str — on failure
    Side Effects:
        - Sets quotes.workflow_status = 'cancelled'
        - Records cancellation_reason, cancellation_comment, cancelled_at,
          cancelled_by, stage_entered_at, clears overdue_notified_at
        - Sends Telegram notifications if quote was in
          procurement/logistics/customs stage
    Roles: sales, head_of_sales, admin.
    """
    # Dual auth: JWT (Next.js) or session (FastHTML)
    api_user = getattr(request.state, 'api_user', None)
    if api_user:
        user_id = str(api_user.id)
        supabase = get_supabase()
        om = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
        org_id = om.data[0]["organization_id"] if om.data else None
        user_roles = get_user_role_codes(user_id, org_id) if org_id else []
    else:
        try:
            session = request.session
        except (AssertionError, AttributeError):
            session = None
        if not session or not session.get("user"):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        user_data = session.get("user", {})
        user_id = user_data.get("id")
        org_id = user_data.get("org_id")
        user_roles = user_data.get("roles", [])

    if not user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not org_id:
        return JSONResponse({"error": "No organization"}, status_code=403)

    # Only sales users and admins can cancel
    cancel_roles = {"sales", "head_of_sales", "admin"}
    if not cancel_roles.intersection(user_roles):
        return JSONResponse({"error": "У вас нет прав для отмены КП"}, status_code=403)

    # Parse request body
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        body = dict(await request.form())

    reason = (body.get("reason") or "").strip()
    if not reason:
        return JSONResponse({"error": "Причина отмены обязательна"}, status_code=400)

    supabase = get_supabase()

    # Verify quote exists and belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id, workflow_status, idn_quote, customer_id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"error": "КП не найдено"}, status_code=404)

    quote = cast(dict, quote_result.data[0])
    current_status = quote.get("workflow_status", "draft")

    # Cannot cancel already cancelled quotes
    if current_status == "cancelled":
        return JSONResponse({"error": "КП уже отменена"}, status_code=422)

    # Cannot cancel deals (spec_signed, deal)
    if current_status in ("spec_signed", "deal"):
        return JSONResponse({"error": "Невозможно отменить КП на этапе сделки"}, status_code=422)

    # Determine if we need to notify procurement/logistics users
    notify_statuses = {"pending_procurement", "logistics", "pending_customs", "pending_logistics_and_customs"}
    should_notify = current_status in notify_statuses

    try:
        supabase.table("quotes") \
            .update({
                "workflow_status": "cancelled",
                "cancellation_reason": "cancelled_by_user",
                "cancellation_comment": reason,
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "cancelled_by": user_id,
                "stage_entered_at": datetime.now(timezone.utc).isoformat(),
                "overdue_notified_at": None,
            }) \
            .eq("id", quote_id) \
            .execute()

        # Send Telegram notifications if quote was in procurement/logistics
        if should_notify:
            try:
                from services.telegram_service import (
                    send_notification,
                    NotificationType,
                    get_user_telegram_id,
                    is_bot_configured,
                )
                if is_bot_configured():
                    # Get customer name for notification
                    customer_name = ""
                    if quote.get("customer_id"):
                        cust = supabase.table("customers").select("name").eq("id", quote["customer_id"]).execute()
                        if cust.data:
                            customer_name = cust.data[0].get("name", "")

                    # Get canceller name
                    canceller = supabase.table("user_profiles").select("full_name").eq("user_id", user_id).execute()
                    canceller_name = canceller.data[0].get("full_name", "") if canceller.data else ""

                    # Find users to notify based on current stage
                    notify_role_slugs = []
                    if current_status == "pending_procurement":
                        notify_role_slugs = ["procurement", "head_of_procurement"]
                    elif current_status in ("logistics", "pending_logistics_and_customs"):
                        notify_role_slugs = ["logistics", "head_of_logistics"]
                    elif current_status == "pending_customs":
                        notify_role_slugs = ["customs"]

                    if notify_role_slugs:
                        members = supabase.table("organization_members") \
                            .select("user_id, roles!inner(slug)") \
                            .eq("organization_id", org_id) \
                            .in_("roles.slug", notify_role_slugs) \
                            .execute()

                        for member in (members.data or []):
                            member_telegram_id = await get_user_telegram_id(member["user_id"])
                            if member_telegram_id:
                                message = (
                                    f"❌ КП {quote.get('idn_quote', '')} отменена\n"
                                    f"Клиент: {customer_name}\n"
                                    f"Отменил: {canceller_name}\n"
                                    f"Причина: {reason}"
                                )
                                await send_notification(
                                    telegram_id=member_telegram_id,
                                    notification_type=NotificationType.TASK_ASSIGNED,
                                    quote_id=quote_id,
                                    message=message,
                                )
            except Exception as notify_err:
                logger.error(f"Failed to send cancellation notifications: {notify_err}")

        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Failed to cancel quote {quote_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def transition_workflow(
    request: Request,
    quote_id: str,
) -> JSONResponse:
    """Execute a workflow status transition.

    Path: POST /api/quotes/{quote_id}/workflow/transition
    Auth: dual — JWT (Next.js) first, then legacy session (FastHTML).
    Body (JSON or form):
        to_status: str — target workflow status (required unless action set)
        action: str — special action: ``complete_procurement`` or
                      ``complete_customs``
        comment: str (optional) — transition comment
    Returns:
        success: bool
        from_status: str — status before the transition (on success)
        to_status: str — status after the transition (on success)
        error: str — error message (on failure)
    Side Effects:
        - Transitions workflow via ``workflow_service``
    Roles: role check delegated to the workflow service transition rules.
    """
    # Dual auth: JWT (Next.js) or session (FastHTML)
    api_user = getattr(request.state, 'api_user', None)
    if api_user:
        user_id = str(api_user.id)
        supabase = get_supabase()
        om = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
        org_id = om.data[0]["organization_id"] if om.data else None
        user_roles = get_user_role_codes(user_id, org_id) if org_id else []
    else:
        try:
            session = request.session
        except (AssertionError, AttributeError):
            session = None
        if not session or not session.get("user"):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        user_data = session.get("user", {})
        user_id = user_data.get("id")
        org_id = user_data.get("org_id")
        user_roles = user_data.get("roles", [])

    if not user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not org_id:
        return JSONResponse({"error": "No organization"}, status_code=403)

    # Parse request body
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        body = dict(await request.form())

    to_status = body.get("to_status")
    action = body.get("action")
    comment = body.get("comment")

    if not to_status and not action:
        return JSONResponse({"error": "to_status or action is required"}, status_code=400)

    # Handle special actions that have dedicated workflow functions
    if action == "complete_procurement":
        result = complete_procurement(
            quote_id=quote_id,
            actor_id=user_id,
            actor_roles=user_roles,
        )
    elif action == "complete_customs":
        result = wf_complete_customs(
            quote_id=quote_id,
            actor_id=user_id,
            actor_roles=user_roles,
        )
    else:
        if not to_status:
            return JSONResponse({"error": "to_status is required"}, status_code=400)
        result = transition_quote_status(
            quote_id=quote_id,
            to_status=to_status,
            actor_id=user_id,
            actor_roles=user_roles,
            comment=comment,
        )

    if result.success:
        return JSONResponse({
            "success": True,
            "from_status": result.from_status,
            "to_status": result.to_status,
        })
    else:
        return JSONResponse({
            "success": False,
            "error": result.error_message,
        }, status_code=422)
