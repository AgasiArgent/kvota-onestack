"""FastHTML ops-post-deal bundle (Mega-A: /deals/{deal_id} detail +
/finance HTMX tail + /customs cluster + /logistics cluster) — archived
2026-04-20 during Phase 6C-2B Mega-A.

These four coherent post-deal operational-stage lifecycle slices are
replaced by Next.js pages reading `/api/customs/*`, `/api/deals/*`,
`/api/logistics/*`, `/api/finance/*` FastAPI routers, plus the preserved
`_finance_*_tab_content` helpers in main.py rendering via /quotes/{id}
finance tabs. Routes unreachable post-Caddy-cutover: kvotaflow.ru
301→app.kvotaflow.ru, which doesn't proxy these paths back to this
Python container. Preserved here for reference / future copy-back.

Bundle rationale (Mega-A):
    The four areas — /deals/{deal_id} redirect, /finance HTMX tail
    (stages + logistics-expenses + generate-currency-invoices), /customs
    cluster (detail page + GTD declarations + return-to-control), and
    /logistics cluster (detail page + return-to-control) — are all
    operational-stage lifecycle surfaces that activate AFTER
    spec-control approval turns a quote into a deal. They co-locate
    cleanly in one archive file because (a) each area is independent
    so no cross-referencing helpers exist, and (b) a single Mega-A PR
    reduces archive review overhead versus 4 separate PRs.

Contents (24 @rt routes + 1 exclusive helper, ~4,338 LOC total):

Area 1 — /deals/{deal_id} redirect (1 route):
  - GET    /deals/{deal_id}                                        — Redirect to /finance/{deal_id} (301,
                                                                     legacy bookmark compat; /finance/{deal_id}
                                                                     itself was archived in 10c1)

Area 2 — /finance HTMX tail (6 routes, 10c2 scope rolled into Mega-A):
  - POST   /finance/{deal_id}/stages/{stage_id}/expenses           — DEPRECATED redirect (inline expense
                                                                     forms removed; expenses now via plan-fact
                                                                     tab)
  - POST   /finance/{deal_id}/stages/{stage_id}/status             — Update stage status (wraps
                                                                     `update_stage_status` from
                                                                     logistics_service)
  - GET    /finance/{deal_id}/logistics-expenses/new-form          — Inline HTMX form for adding logistics
                                                                     expense to a stage
  - POST   /finance/{deal_id}/logistics-expenses                   — Create a new logistics expense record
                                                                     + re-render stage section + OOB total
  - DELETE /finance/{deal_id}/logistics-expenses/{expense_id}      — Delete a logistics expense + re-render
                                                                     stage section + OOB total
  - POST   /finance/{deal_id}/generate-currency-invoices           — Fallback endpoint to (re)generate
                                                                     currency invoices for a deal

Area 3 — /customs cluster (12 routes):
  - GET    /customs                                                — Redirect to /dashboard?tab=customs
  - GET    /customs/declarations                                   — Registry of uploaded GTD customs
                                                                     declarations with HTMX-expandable item
                                                                     rows
  - GET    /customs/declarations/upload                            — GTD XML upload file-selector form
  - POST   /customs/declarations/upload                            — Parse uploaded XML + write to temp
                                                                     file + redirect to preview
  - GET    /customs/declarations/upload/preview                    — Preview parsed GTD data before saving
  - POST   /customs/declarations/upload/confirm                    — Save parsed GTD to DB + run item
                                                                     matching
  - GET    /customs/declarations/{declaration_id}/items            — HTMX partial: items table for a
                                                                     declaration (lazy-loaded on expand)
  - GET    /customs/{quote_id}                                     — Customs detail page (Handsontable
                                                                     for item-level customs data +
                                                                     quote-level brokerage/SVH/doc costs +
                                                                     license columns)
  - POST   /customs/{quote_id}                                     — Save customs data (notes +
                                                                     quote-level costs; item-level done via
                                                                     /api/customs bulk) + optional complete
  - PATCH  /customs/{quote_id}/items/{item_id}                     — Legacy per-item field update (kept
                                                                     for compat; main path is
                                                                     /api/customs bulk)
  - GET    /customs/{quote_id}/return-to-control                   — Form to return a revised quote back
                                                                     to quote control
  - POST   /customs/{quote_id}/return-to-control                   — Submit return-to-control with comment

Area 4 — /logistics cluster (5 routes):
  - GET    /logistics                                              — Redirect to /dashboard?tab=logistics
  - GET    /logistics/{quote_id}                                   — Logistics detail page (invoice-level
                                                                     logistics cards: routes, pricing,
                                                                     weights, dimensions)
  - POST   /logistics/{quote_id}                                   — Save invoice-level logistics fields
                                                                     + optional complete logistics
  - GET    /logistics/{quote_id}/return-to-control                 — Form to return a revised quote back
                                                                     to quote control
  - POST   /logistics/{quote_id}/return-to-control                 — Submit return-to-control with comment

Exclusive helper archived with its callers:
  - _finance_logistics_expenses_stage_section — re-renders a single stage section for HTMX swap after
                                                create/delete; only callers were the archived
                                                /finance/{deal_id}/logistics-expenses POST + DELETE

Preserved in main.py (consumed by /quotes/{quote_id} finance tabs that
stay alive):
  - _finance_fetch_deal_data, _finance_main_tab_content,
    _finance_plan_fact_tab_content, _finance_logistics_tab_content,
    _finance_currency_invoices_tab_content, _logistics_expenses_total_el,
    _finance_logistics_expenses_tab_content, _finance_payment_modal,
    _deals_logistics_tab — all called by /quotes/{quote_id} GET at
    main.py:6124-6160 when tab in {finance_main, plan_fact,
    logistics_stages, currency_invoices, logistics_expenses}
  - _ci_segment_badge, _ci_status_badge, _resolve_company_name,
    _fetch_items_with_buyer_companies, _fetch_enrichment_data — still
    alive, consumed by /quotes/{id}/documents +
    _finance_currency_invoices_tab_content

Preserved service layers (all alive):
  - services/customs_declaration_service.py — parse_gtd_xml, save_declaration,
    list_declarations, get_declaration_items, match_items_to_deals,
    GTDParseResult, GTDItem. Consumed only by the archived /customs/declarations/*
    routes; after archive it has no runtime callers in main.py but is still
    covered by tests/test_customs_declarations.py and may be rewired via
    Next.js + /api/customs post-cutover.
  - services/logistics_service.py — get_stages_for_deal, update_stage_status,
    get_expenses_for_stage, get_stage_summary, stage_allows_expenses,
    STAGE_NAMES, STAGE_CODES, STAGE_CATEGORY_MAP, initialize_logistics_stages.
    Consumed by preserved _finance_logistics_expenses_tab_content,
    _deals_logistics_tab in main.py plus api/routers/logistics and tests.
  - services/logistics_expense_service.py — create_expense, delete_expense,
    get_expense, get_expenses_for_stage, sync_plan_fact_for_stage,
    get_deal_logistics_summary, EXPENSE_SUBTYPE_LABELS, SUPPORTED_CURRENCIES.
    Consumed by preserved _finance_logistics_expenses_tab_content and FastAPI.
  - services/plan_fact_service.py, services/deal_service.py, services/workflow_service.py,
    services/currency_invoice_service.py — all alive, consumed by FastAPI +
    preserved helpers.

NOT included (separate archive decisions):
  - /admin/* (main.py lines 21143-23592) — separate archive decision
  - /quote-control/* (main.py lines 16899-19100) — Mega-B scope
  - /spec-control/* (main.py lines 19207-20857) — Mega-B scope
  - /quotes/*, /procurement/* — Mega-C scope
  - /deals (list), /payments/calendar, /finance (main page), /finance/{deal_id}
    redirect, /finance/{deal_id}/payments/*, /finance/{deal_id}/plan-fact/*
    — already archived in Phase 6C-2B-10c1 (legacy-fasthtml/finance_lifecycle.py)
  - /api/customs/*, /api/deals/*, /api/logistics/*, /api/finance/*,
    /api/plan-fact/* — FastAPI sub-app, alive
  - calculation_engine.py, calculation_models.py, calculation_mapper.py
    — locked, never touched

Sidebar/nav entries for /customs, /logistics, /deals, /finance, /payments/calendar
in main.py left intact post-archive — they become dead links but are safe
per the Caddy cutover plan (kvotaflow.ru → app.kvotaflow.ru).

This file is NOT imported by main.py or api/app.py. Effectively dead
code preserved for reference. To resurrect a handler: copy back to
main.py, restore imports (page_layout, require_login, user_has_any_role,
get_supabase, icon, btn, btn_link, format_money, format_date_russian,
cast, json, os, uuid, Decimal, datetime/date, workflow_status_badge,
workflow_progress_bar, quote_header, quote_detail_tabs,
workflow_transition_history, STATUS_NAMES, WorkflowStatus,
transition_quote_status, complete_logistics, complete_customs,
get_user_roles_from_session, COUNTRY_NAME_MAP, fasthtml components,
starlette RedirectResponse, services.customs_declaration_service.*,
services.logistics_service.*, services.logistics_expense_service.*,
services.currency_service.convert_amount,
services.currency_invoice_service.{generate_currency_invoices,
save_currency_invoices}, services.location_service.{get_location,
format_location_for_dropdown}, services.supplier_service.{get_supplier,
format_supplier_for_dropdown}), re-apply the @rt decorator, and
regenerate tests if needed. Not recommended — rewrite via Next.js +
FastAPI instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime, date
from decimal import Decimal

from fasthtml.common import (
    A, Button, Div, Form, H1, H3, H4, Hidden, I, Input, Label, Option, P,
    Script, Select, Small, Span, Strong, Style, Table, Tbody, Td, Textarea,
    Th, Thead, Tr,
)
from starlette.responses import RedirectResponse



# ============================================================================
# LOGISTICS CLUSTER (Feature #38)
# 5 routes: /logistics (redirect), /logistics/{quote_id} GET+POST,
# /logistics/{quote_id}/return-to-control GET+POST
# ============================================================================
# ============================================================================
# LOGISTICS WORKSPACE (Feature #38)
# ============================================================================

# @rt("/logistics")
def get(session, status_filter: str = None):
    """
    Redirect to unified dashboard logistics tab.
    Old URL preserved for backwards compatibility.
    """
    url = "/dashboard?tab=logistics"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


# ============================================================================
# LOGISTICS DETAIL PAGE
# ============================================================================

# @rt("/logistics/{quote_id}")
def get(session, quote_id: str):
    """
    Logistics detail page - view and edit logistics data for a quote.

    Feature UI-020 (v4.0): Invoice-based logistics workspace
    - Shows invoices (not individual items)
    - Displays weight/volume per invoice (filled by procurement)
    - Single logistics cost field per invoice (not per item)
    - Only editable when quote is in pending_logistics or pending_customs status
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has logistics role
    if not user_has_any_role(session, ["logistics", "admin", "head_of_logistics"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("Quote Not Found"),
            P("The requested quote was not found or you don't have access."),
            A("← Назад к задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    customer_name = (quote.get("customers") or {}).get("name", "Unknown")
    currency = quote.get("currency", "RUB")

    # Check for revision status (returned from quote control)
    revision_department = quote.get("revision_department")
    revision_comment = quote.get("revision_comment")
    is_revision = revision_department == "logistics" and workflow_status == "pending_logistics"

    # Check if quote is ready for logistics (procurement must be done first)
    ready_for_logistics_statuses = ["pending_logistics", "pending_customs", "pending_logistics_and_customs", "pending_sales_review"]
    is_ready_for_logistics = workflow_status in ready_for_logistics_statuses

    # Check if logistics is editable (only when ready and not completed)
    is_editable = is_ready_for_logistics and quote.get("logistics_completed_at") is None
    logistics_done = quote.get("logistics_completed_at") is not None

    # Fetch invoices for this quote
    invoices_result = supabase.table("invoices") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    invoices = invoices_result.data or []

    # For each invoice, fetch its items and related data (location, supplier)
    invoices_with_items = []
    for invoice in invoices:
        items_result = supabase.table("quote_items") \
            .select("id, brand, product_name, quantity, purchase_price_original, purchase_currency, supplier_country, weight_in_kg, volume_m3") \
            .eq("invoice_id", invoice["id"]) \
            .execute()

        invoice_data = dict(invoice)
        invoice_data["items"] = items_result.data or []

        # Load pickup location info
        pickup_location_id = invoice.get("pickup_location_id")
        if pickup_location_id:
            try:
                from services.location_service import get_location
                loc = get_location(pickup_location_id)
                if loc:
                    invoice_data["pickup_location"] = {
                        "city": loc.city,
                        "country": loc.country
                    }
            except:
                pass

        # Load supplier info
        supplier_id = invoice.get("supplier_id")
        if supplier_id:
            try:
                from services.supplier_service import get_supplier
                sup = get_supplier(supplier_id)
                if sup:
                    invoice_data["supplier"] = {
                        "name": sup.name,
                        "country": sup.country
                    }
            except:
                pass

        invoices_with_items.append(invoice_data)

    # Calculate summary stats from invoices
    # Import currency conversion for multi-currency logistics
    from services.currency_service import convert_amount
    from decimal import Decimal

    total_invoices = len(invoices)
    invoices_with_logistics = 0
    total_logistics_cost = Decimal(0)  # Will be in quote currency
    total_weight = 0
    total_volume = 0
    total_items = 0
    unique_countries = set()

    for inv in invoices_with_items:
        total_items += len(inv["items"])
        total_weight += float(inv.get("total_weight_kg") or 0)
        total_volume += float(inv.get("total_volume_m3") or 0)

        # Count logistics completion per invoice
        # Each segment may be in different currency - convert to quote currency before summing
        s2h = Decimal(str(inv.get("logistics_supplier_to_hub") or 0))
        s2h_currency = inv.get("logistics_supplier_to_hub_currency") or "USD"
        h2c = Decimal(str(inv.get("logistics_hub_to_customs") or 0))
        h2c_currency = inv.get("logistics_hub_to_customs_currency") or "USD"
        c2c = Decimal(str(inv.get("logistics_customs_to_customer") or 0))
        c2c_currency = inv.get("logistics_customs_to_customer_currency") or "USD"

        # Convert each segment to quote currency
        s2h_converted = convert_amount(s2h, s2h_currency, currency) if s2h > 0 else Decimal(0)
        h2c_converted = convert_amount(h2c, h2c_currency, currency) if h2c > 0 else Decimal(0)
        c2c_converted = convert_amount(c2c, c2c_currency, currency) if c2c > 0 else Decimal(0)

        inv_total = s2h_converted + h2c_converted + c2c_converted
        if inv_total > 0 or inv.get("logistics_total_days"):
            invoices_with_logistics += 1
        total_logistics_cost += inv_total

        # Collect countries from items
        for item in inv["items"]:
            if item.get("supplier_country"):
                unique_countries.add(item["supplier_country"])

    # Convert total to float for display
    total_logistics_cost = float(total_logistics_cost)

    # Build invoice form cards for v4.0 invoice-level logistics
    def logistics_invoice_card(invoice, idx):
        invoice_id = invoice.get("id")
        invoice_number = invoice.get("invoice_number", f"Invoice #{idx+1}")
        inv_currency = invoice.get("currency", currency)

        # Get current invoice logistics values
        s2h = invoice.get("logistics_supplier_to_hub") or 0
        h2c = invoice.get("logistics_hub_to_customs") or 0
        c2c = invoice.get("logistics_customs_to_customer") or 0
        days = invoice.get("logistics_total_days") or ""
        # Currency values for each segment (default: USD)
        s2h_currency = invoice.get("logistics_supplier_to_hub_currency") or "USD"
        h2c_currency = invoice.get("logistics_hub_to_customs_currency") or "USD"
        c2c_currency = invoice.get("logistics_customs_to_customer_currency") or "USD"
        invoice_logistics_total = float(s2h) + float(h2c) + float(c2c)  # Note: mixed currencies, for display only

        # Invoice completion indicator
        has_logistics = invoice_logistics_total > 0 or days
        status_icon_elem = icon("check-circle", size=16) if has_logistics else icon("clock", size=16)
        status_color = "#22c55e" if has_logistics else "#f59e0b"

        # Weight/volume from procurement
        weight = invoice.get("total_weight_kg") or 0
        volume = invoice.get("total_volume_m3") or 0

        # Items list
        items = invoice.get("items", [])
        total_items_in_invoice = len(items)

        # Country code/name to Russian name mapping
        country_names = {
            # ISO codes
            "DE": "Германия", "CN": "Китай", "TR": "Турция", "IT": "Италия",
            "RU": "Россия", "US": "США", "KR": "Корея", "JP": "Япония",
            "FR": "Франция", "GB": "Великобритания", "ES": "Испания", "PL": "Польша",
            "CZ": "Чехия", "NL": "Нидерланды", "BE": "Бельгия", "AT": "Австрия",
            "CH": "Швейцария", "SE": "Швеция", "FI": "Финляндия", "DK": "Дания",
            "IN": "Индия", "TW": "Тайвань", "VN": "Вьетнам", "TH": "Таиланд",
            "MY": "Малайзия", "SG": "Сингапур", "AE": "ОАЭ", "SA": "Саудовская Аравия",
            "OTHER": "Другое",
            # English names
            "Germany": "Германия", "China": "Китай", "Turkey": "Турция", "Italy": "Италия",
            "Russia": "Россия", "United States": "США", "USA": "США",
            "South Korea": "Корея", "Korea": "Корея", "Japan": "Япония",
            "France": "Франция", "United Kingdom": "Великобритания", "UK": "Великобритания",
            "Spain": "Испания", "Poland": "Польша", "Czech Republic": "Чехия",
            "Netherlands": "Нидерланды", "Belgium": "Бельгия", "Austria": "Австрия",
            "Switzerland": "Швейцария", "Sweden": "Швеция", "Finland": "Финляндия",
            "Denmark": "Дания", "India": "Индия", "Taiwan": "Тайвань",
            "Vietnam": "Вьетнам", "Thailand": "Таиланд", "Malaysia": "Малайзия",
            "Singapore": "Сингапур", "UAE": "ОАЭ", "Saudi Arabia": "Саудовская Аравия",
        }

        # Get origin location text: invoice.pickup_city > pickup_location.city
        origin_city = (
            invoice.get("pickup_city", "")
            or ((invoice.get("pickup_location") or {}).get("city", "")
                if invoice.get("pickup_location") else "")
        )
        # Origin country: pickup_location > invoice.pickup_country > supplier.country
        raw_origin_country = (
            (invoice.get("pickup_location") or {}).get("country", "")
            if invoice.get("pickup_location") and (invoice.get("pickup_location") or {}).get("country")
            else invoice.get("pickup_country", "")
            if invoice.get("pickup_country") and invoice.get("pickup_country") != "OTHER"
            else ((invoice.get("supplier") or {}).get("country", ""))
            if invoice.get("supplier") and (invoice.get("supplier") or {}).get("country")
            else invoice.get("pickup_country", "")
        )
        # Convert country code to name if needed
        origin_country = country_names.get(raw_origin_country, raw_origin_country) if raw_origin_country else ""

        dest_city = quote.get('delivery_city', '')
        raw_dest_country = quote.get('delivery_country', '')
        dest_country = country_names.get(raw_dest_country, raw_dest_country) if raw_dest_country else ""
        delivery_method_text = {"air": "Авиа", "auto": "Авто", "sea": "Море", "multimodal": "Мульти"}.get(
            quote.get("delivery_method", ""), "—"
        )
        delivery_method_icon = {"air": icon("plane", size=14), "auto": icon("truck", size=14), "sea": icon("ship", size=14), "multimodal": icon("package", size=14)}.get(
            quote.get("delivery_method", ""), icon("package", size=14)
        )

        # Styles
        card_style = f"""
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            overflow: hidden;
        """
        header_style = f"""
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: {'linear-gradient(90deg, #f0fdf4 0%, #fafbfc 100%)' if has_logistics else '#fafbfc'};
            border-bottom: 1px solid #e2e8f0;
        """
        body_style = """
            display: flex;
            padding: 16px;
            gap: 20px;
        """
        route_card_style = """
            background: white;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            border: 1px solid #e8ecf1;
            flex: 0 0 280px;
            display: flex;
            flex-direction: column;
        """
        pricing_card_style = """
            background: white;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border: 1px solid #e2e8f0;
            flex: 1;
            min-width: 300px;
        """
        input_row_style = """
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f1f5f9;
        """
        input_row_last_style = """
            display: flex;
            align-items: center;
            padding: 8px 0;
        """
        label_style = """
            font-size: 13px;
            color: #64748b;
            width: 90px;
            font-weight: 500;
        """
        input_style = """
            width: 90px;
            padding: 8px 10px;
            font-size: 14px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            background: #f8fafc;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        """
        select_style = """
            width: 62px;
            padding: 8px 4px;
            font-size: 13px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            background: #f8fafc;
            margin-left: 8px;
            color: #64748b;
            cursor: pointer;
            flex-shrink: 0;
        """

        return Div(
            # Invoice header
            Div(
                Div(
                    Span(status_icon_elem, style=f"color: {status_color}; margin-right: 8px;"),
                    Span(invoice_number, style="font-weight: 600; color: #1e293b; font-size: 14px;"),
                    Span(f"  •  {inv_currency}", style="color: #94a3b8; font-size: 13px; margin-left: 4px;"),
                    style="display: flex; align-items: center;"
                ),
                Span(f"#{idx+1}", style="color: #94a3b8; font-size: 12px; font-weight: 500; background: #f1f5f9; padding: 2px 8px; border-radius: 4px;"),
                style=header_style
            ),

            # Two-column layout
            Div(
                # LEFT: Route visualization
                Div(
                    # Origin
                    Div(
                        Div("ОТКУДА", style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;"),
                        Div(origin_city, style="font-size: 15px; color: #059669; font-weight: 600;") if origin_city else None,
                        Div(origin_country or "—", style=f"font-size: {'12px' if origin_city else '15px'}; color: {'#64748b' if origin_city else '#059669'}; font-weight: {'400' if origin_city else '600'};"),
                        style="margin-bottom: 12px;"
                    ),
                    # Arrow
                    Div(
                        Div(
                            Span("", style="display: block; width: 2px; height: 20px; background: linear-gradient(to bottom, #059669, #3b82f6); margin: 0 auto;"),
                            Span("▼", style="color: #3b82f6; font-size: 8px; display: block; text-align: center; margin-top: -2px;"),
                        ),
                        style="padding: 4px 0;"
                    ),
                    # Destination
                    Div(
                        Div("КУДА", style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;"),
                        Div(dest_city, style="font-size: 15px; color: #3b82f6; font-weight: 600;") if dest_city else None,
                        Div(dest_country or "—", style=f"font-size: {'12px' if dest_city else '15px'}; color: {'#64748b' if dest_city else '#3b82f6'}; font-weight: {'400' if dest_city else '600'};"),
                        style="margin-bottom: 12px;"
                    ),
                    # Delivery method badge
                    Div(
                        Span(delivery_method_icon, f" {delivery_method_text}",
                             style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); color: #92400e; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;"),
                        style="margin-top: auto; padding-top: 8px; border-top: 1px solid #f1f5f9;"
                    ),
                    # Weight & items
                    Div(
                        Div(
                            Span(f"{weight} кг" if weight > 0 else "—", style=f"font-weight: 600; color: {'#059669' if weight > 0 else '#94a3b8'};"),
                            style="font-size: 13px;"
                        ),
                        Span("•", style="color: #cbd5e1; margin: 0 8px;"),
                        Div(
                            Span(f"{total_items_in_invoice} поз.", style="color: #64748b;"),
                            style="font-size: 13px;"
                        ),
                        style="display: flex; align-items: center; margin-top: 10px; padding-top: 10px; border-top: 1px dashed #e2e8f0;"
                    ),
                    # Dimensions and package count from procurement
                    Div(
                        Span(f"Габариты: {invoice.get('height_m')} \u00d7 {invoice.get('length_m')} \u00d7 {invoice.get('width_m')} м",
                             style="color: #64748b; font-size: 12px;") if (invoice.get('height_m') and invoice.get('length_m') and invoice.get('width_m')) else None,
                        Span(f"  \u2022  {invoice.get('package_count')} мест", style="color: #64748b; font-size: 12px;") if invoice.get('package_count') else None,
                        style="display: flex; align-items: center; gap: 8px; padding: 4px 0;"
                    ) if (invoice.get('height_m') or invoice.get('package_count')) else None,
                    # Procurement notes
                    Div(
                        icon("info", size=14, color="#f59e0b"),
                        Span(f" {invoice.get('procurement_notes')}", style="color: #64748b; font-size: 12px;"),
                        style="display: flex; align-items: start; gap: 4px; padding: 6px 8px; background: #fefce8; border-radius: 6px; margin-top: 4px;"
                    ) if invoice.get('procurement_notes') else None,
                    # Items list (always visible)
                    Div(
                        Div("ТОВАРЫ ДЛЯ ЛОГИСТИКИ", style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px; font-weight: 600; margin-bottom: 6px;"),
                        Div(
                            *[Div(
                                Span(f"{item.get('brand', '—')} — {item.get('product_name', '—')[:30]}", style="flex: 1; color: #475569;"),
                                Span(f"{item.get('weight_in_kg', 0) or 0} кг", style="color: #64748b; margin-right: 8px;") if item.get('weight_in_kg') else None,
                                Span(f"{item.get('volume_m3', 0) or 0} м³", style="color: #64748b; margin-right: 8px;") if item.get('volume_m3') else None,
                                Span(
                                    f"{item.get('purchase_price_original', 0)} {item.get('purchase_currency', '')}",
                                    style="color: #059669; font-weight: 500; margin-right: 8px;"
                                ) if item.get('purchase_price_original') else None,
                                Span(f"x{item.get('quantity', 0)}", style="color: #94a3b8; font-weight: 500;"),
                                style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 12px; border-bottom: 1px solid #f1f5f9;"
                            ) for item in items],
                            style="padding: 8px; background: #f8fafc; border-radius: 6px;"
                        ),
                        style="margin-top: 8px;"
                    ) if items else None,
                    style=route_card_style
                ),

                # RIGHT: Pricing card (elevated)
                Div(
                    # Two-column layout: pricing on left, comment on right
                    Div(
                        # LEFT: Pricing inputs
                        Div(
                            Div("СТОИМОСТЬ ДОСТАВКИ", style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px; font-weight: 600; margin-bottom: 10px;"),
                            # Row 1
                            Div(
                                Span("Поставщик → Хаб", style=label_style),
                                Input(name=f"logistics_supplier_to_hub_{invoice_id}", type="number", value=str(s2h),
                                      min="0", step="0.01", disabled=not is_editable, style=input_style),
                                Select(
                                    Option("USD", value="USD", selected=s2h_currency == "USD"),
                                    Option("EUR", value="EUR", selected=s2h_currency == "EUR"),
                                    Option("RUB", value="RUB", selected=s2h_currency == "RUB"),
                                    Option("CNY", value="CNY", selected=s2h_currency == "CNY"),
                                    Option("TRY", value="TRY", selected=s2h_currency == "TRY"),
                                    name=f"logistics_supplier_to_hub_currency_{invoice_id}",
                                    disabled=not is_editable, style=select_style
                                ),
                                style=input_row_style
                            ),
                            # Row 2
                            Div(
                                Span("Хаб → Таможня", style=label_style),
                                Input(name=f"logistics_hub_to_customs_{invoice_id}", type="number", value=str(h2c),
                                      min="0", step="0.01", disabled=not is_editable, style=input_style),
                                Select(
                                    Option("USD", value="USD", selected=h2c_currency == "USD"),
                                    Option("EUR", value="EUR", selected=h2c_currency == "EUR"),
                                    Option("RUB", value="RUB", selected=h2c_currency == "RUB"),
                                    Option("CNY", value="CNY", selected=h2c_currency == "CNY"),
                                    Option("TRY", value="TRY", selected=h2c_currency == "TRY"),
                                    name=f"logistics_hub_to_customs_currency_{invoice_id}",
                                    disabled=not is_editable, style=select_style
                                ),
                                style=input_row_style
                            ),
                            # Row 3
                            Div(
                                Span("Таможня → Клиент", style=label_style),
                                Input(name=f"logistics_customs_to_customer_{invoice_id}", type="number", value=str(c2c),
                                      min="0", step="0.01", disabled=not is_editable, style=input_style),
                                Select(
                                    Option("USD", value="USD", selected=c2c_currency == "USD"),
                                    Option("EUR", value="EUR", selected=c2c_currency == "EUR"),
                                    Option("RUB", value="RUB", selected=c2c_currency == "RUB"),
                                    Option("CNY", value="CNY", selected=c2c_currency == "CNY"),
                                    Option("TRY", value="TRY", selected=c2c_currency == "TRY"),
                                    name=f"logistics_customs_to_customer_currency_{invoice_id}",
                                    disabled=not is_editable, style=select_style
                                ),
                                style=input_row_style
                            ),
                            # Row 4: Days
                            Div(
                                Span("Срок доставки", style=label_style),
                                Input(name=f"logistics_total_days_{invoice_id}", type="number",
                                      value=str(days) if days else "", min="1", max="365",
                                      disabled=not is_editable, style=input_style),
                                Span("дней", style="margin-left: 8px; color: #94a3b8; font-size: 13px;"),
                                style=input_row_last_style
                            ),
                            style="flex: 0 0 auto;"
                        ),
                        # RIGHT: Comment box
                        Div(
                            Div("КОММЕНТАРИЙ", style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px; font-weight: 600; margin-bottom: 10px;"),
                            Textarea(
                                invoice.get("logistics_notes", ""),
                                name=f"logistics_notes_{invoice_id}",
                                placeholder="Заметки по доставке, особые условия, контакты перевозчика...",
                                disabled=not is_editable,
                                rows="5",
                                style="width: 100%; height: 100%; min-height: 120px; padding: 10px 12px; font-size: 13px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; resize: none; flex: 1; font-family: inherit; line-height: 1.5;"
                            ),
                            style="flex: 1; min-width: 200px; display: flex; flex-direction: column;"
                        ),
                        style="display: flex; gap: 24px;"
                    ),
                    style=pricing_card_style
                ),
                style=body_style
            ),
            style=card_style
        )

    # Procurement totals (weight/volume) - prominent display
    proc_total_weight = quote.get("procurement_total_weight_kg") or 0
    proc_total_volume = quote.get("procurement_total_volume_m3") or 0
    procurement_totals_card = Div(
        Div(
            Div(
                Div(icon("package", size=18), " Общий вес (закупки)", style="font-size: 12px; color: #64748b; display: flex; align-items: center; gap: 6px; margin-bottom: 4px;"),
                Div(f"{proc_total_weight} кг", style=f"font-size: 20px; font-weight: 700; color: {'#059669' if proc_total_weight else '#94a3b8'};"),
                style="flex: 1; text-align: center; padding: 12px;"
            ),
            Div(style="width: 1px; background: #e2e8f0; margin: 8px 0;"),
            Div(
                Div(icon("box", size=18), " Общий объём (закупки)", style="font-size: 12px; color: #64748b; display: flex; align-items: center; gap: 6px; margin-bottom: 4px;"),
                Div(f"{proc_total_volume} м³" if proc_total_volume else "—", style=f"font-size: 20px; font-weight: 700; color: {'#3b82f6' if proc_total_volume else '#94a3b8'};"),
                style="flex: 1; text-align: center; padding: 12px;"
            ),
            style="display: flex; align-items: center; gap: 0;"
        ),
        style="background: linear-gradient(135deg, #f0fdf4 0%, #ecfeff 100%); border: 1px solid #d1fae5; border-radius: 10px; margin-bottom: 16px;"
    ) if (proc_total_weight or proc_total_volume) else None

    # Build the invoice-level logistics form
    invoice_logistics_section = Div(
        H3(icon("file-text", size=20), " Логистика по инвойсам (v4.0)", style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;"),
        P("Введите стоимость доставки для каждого инвойса. Вес/габариты заполнены закупками.",
          style="color: #666; margin-bottom: 1rem;"),
        procurement_totals_card,
        *[logistics_invoice_card(invoice, idx) for idx, invoice in enumerate(invoices_with_items)],
    ) if invoices_with_items else Div(
        P("Нет инвойсов для расчёта логистики. Закупки должны создать инвойсы сначала.", style="color: #666;"),
        cls="card"
    )


    # Form wrapper
    logistics_form = Form(
        # Invoice-level logistics (v4.0)
        invoice_logistics_section,

        # Action buttons - sticky footer bar
        Div(
            Div(
                btn("Сохранить данные", variant="secondary", icon_name="save", type="submit", name="action", value="save") if is_editable else None,
                btn("✓ Завершить логистику", variant="success", icon_name=None, type="submit", name="action", value="complete") if is_editable else None,
                Span(icon("check-circle", size=16), " Логистика завершена", style="color: #22c55e; font-weight: bold; display: inline-flex; align-items: center; gap: 0.25rem;") if logistics_done else None,
                style="display: inline-flex; gap: 1rem; align-items: center;"
            ),
            style="margin-top: 1.5rem; padding: 1rem; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;"
        ) if is_editable or logistics_done else None,

        method="post",
        action=f"/logistics/{quote_id}"
    )

    # Status banners
    # Not ready for logistics (still in procurement/draft)
    not_ready_banner = Div(
        P(icon("clock", size=16), " КП ещё не готово для логистики. Ожидается завершение этапа закупок.",
          style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"),
        P(f"Текущий статус: {STATUS_NAMES.get(workflow_status, workflow_status)}",
          style="margin: 0.5rem 0 0; font-size: 0.875rem; color: #666;"),
        style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if not is_ready_for_logistics and not logistics_done else None

    # Other non-editable status
    status_banner = Div(
        P(icon("alert-triangle", size=16), f" Данный КП в статусе '{STATUS_NAMES.get(workflow_status, workflow_status)}' — редактирование логистики недоступно.",
          style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"),
        style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if is_ready_for_logistics and not is_editable and not logistics_done else None

    success_banner = Div(
        P(icon("check-circle", size=16), " Логистика по данному КП завершена.",
          style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"),
        style="background-color: #dcfce7; border: 1px solid #22c55e; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if logistics_done else None

    return page_layout(f"Logistics - {quote.get('idn_quote', '')}",
        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "logistics", user.get("roles", []), quote=quote, user_id=user_id),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(workflow_status),

        # Partial recalculation banner - shown when returned from client for logistics-only changes
        Div(
            Div(
                Span("🔄 Частичный пересчёт: только логистика", style="font-weight: 600; font-size: 1.1rem;"),
                style="margin-bottom: 0.5rem;"
            ),
            Div(
                P("Клиент запросил изменение логистики. Данные закупки и таможни сохранены.", style="margin: 0 0 0.5rem;"),
                P("После обновления логистики КП автоматически вернётся клиенту.", style="margin: 0; font-size: 0.875rem; color: #666;"),
            ),
            cls="card",
            style="background: #e0f2fe; border: 2px solid #0891b2; margin-bottom: 1rem;"
        ) if quote.get("partial_recalc") == "logistics" else None,

        # Revision banner - shown when returned from quote control (Feature: multi-department return)
        Div(
            Div(
                Span("↩ Возвращено на доработку", style="font-weight: 600; font-size: 1.1rem;"),
                style="margin-bottom: 0.5rem;"
            ),
            Div(
                Span("Комментарий контроллёра КП:", style="font-weight: 500;"),
                P(revision_comment, style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap;"),
                style="margin-bottom: 1rem;"
            ) if revision_comment else None,
            Div(
                P("После внесения исправлений верните КП на проверку.", style="margin: 0 0 0.75rem; font-size: 0.875rem;"),
                A("✓ Вернуть на проверку", href=f"/logistics/{quote_id}/return-to-control",
                  role="button", style="background: #22c55e; border-color: #22c55e;"),
            ),
            cls="card",
            style="background: #fef3c7; border: 2px solid #f59e0b; margin-bottom: 1rem;"
        ) if is_revision else None,

        # Status banners
        not_ready_banner,
        success_banner,
        status_banner,

        # Logistics form with item-level editing (v4.0 compact design)
        logistics_form,

        # Transition history (Feature #88)
        workflow_transition_history(quote_id),

        session=session
    )


# @rt("/logistics/{quote_id}")
async def post(session, quote_id: str, request):
    """
    Save logistics data and optionally mark logistics as complete.

    Feature UI-020 (v4.0): Invoice-based logistics POST handler
    - Saves invoice-level logistics costs to invoices table
    - Handles 'complete' action to mark logistics as done
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role
    if not user_has_any_role(session, ["logistics", "admin", "head_of_logistics"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify quote exists and belongs to org
    quote_result = supabase.table("quotes") \
        .select("id, workflow_status, logistics_completed_at") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return RedirectResponse("/logistics", status_code=303)

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is ready for logistics (procurement must be done first)
    ready_statuses = ["pending_logistics", "pending_customs", "pending_logistics_and_customs", "pending_sales_review"]
    if workflow_status not in ready_statuses or quote.get("logistics_completed_at"):
        return RedirectResponse(f"/logistics/{quote_id}", status_code=303)

    # Get form data
    form_data = await request.form()

    # Helper functions
    def safe_decimal(val, default="0"):
        try:
            return float(val) if val else float(default)
        except:
            return float(default)

    def safe_int(val, default=None):
        try:
            return int(val) if val else default
        except:
            return default

    # ==========================================
    # v4.0: Save invoice-level logistics to invoices table
    # ==========================================

    # Get all invoices for this quote
    invoices_result = supabase.table("invoices") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .execute()

    invoices = invoices_result.data or []

    # Update each invoice's logistics fields
    for invoice in invoices:
        invoice_id = invoice["id"]

        # Get invoice-specific logistics values from form
        s2h = form_data.get(f"logistics_supplier_to_hub_{invoice_id}")
        h2c = form_data.get(f"logistics_hub_to_customs_{invoice_id}")
        c2c = form_data.get(f"logistics_customs_to_customer_{invoice_id}")
        days = form_data.get(f"logistics_total_days_{invoice_id}")
        notes = form_data.get(f"logistics_notes_{invoice_id}")
        # Currency values for each segment
        s2h_currency = form_data.get(f"logistics_supplier_to_hub_currency_{invoice_id}")
        h2c_currency = form_data.get(f"logistics_hub_to_customs_currency_{invoice_id}")
        c2c_currency = form_data.get(f"logistics_customs_to_customer_currency_{invoice_id}")

        # Build update data
        update_data = {}

        if s2h is not None:
            update_data["logistics_supplier_to_hub"] = safe_decimal(s2h)
        if h2c is not None:
            update_data["logistics_hub_to_customs"] = safe_decimal(h2c)
        if c2c is not None:
            update_data["logistics_customs_to_customer"] = safe_decimal(c2c)
        if days is not None:
            days_val = safe_int(days)
            update_data["logistics_total_days"] = days_val if days_val and days_val > 0 else None
        if notes is not None:
            update_data["logistics_notes"] = notes
        # Save currency values
        if s2h_currency:
            update_data["logistics_supplier_to_hub_currency"] = s2h_currency
        if h2c_currency:
            update_data["logistics_hub_to_customs_currency"] = h2c_currency
        if c2c_currency:
            update_data["logistics_customs_to_customer_currency"] = c2c_currency

        # Update invoice if we have data
        if update_data:
            try:
                supabase.table("invoices") \
                    .update(update_data) \
                    .eq("id", invoice_id) \
                    .execute()
            except Exception as e:
                print(f"Error updating logistics for invoice {invoice_id}: {e}")

    # Get action
    action = form_data.get("action", "save")

    # If action is complete, mark logistics as done
    if action == "complete":
        user_roles = get_user_roles_from_session(session)
        result = complete_logistics(quote_id, user_id, user_roles)

        if not result.success:
            # Log error but still redirect
            print(f"Error completing logistics: {result.error_message}")
        else:
            # Check for partial recalculation mode
            try:
                partial_check = supabase.table("quotes") \
                    .select("partial_recalc") \
                    .eq("id", quote_id) \
                    .single() \
                    .is_("deleted_at", None) \
                    .execute()

                partial_recalc = partial_check.data.get("partial_recalc") if partial_check.data else None

                if partial_recalc == "logistics":
                    # Partial recalculation - skip customs, return to client negotiation
                    # Clear partial_recalc flag and transition to client_negotiation
                    supabase.table("quotes").update({
                        "partial_recalc": None
                    }).eq("id", quote_id).execute()

                    # Transition directly to client_negotiation
                    transition_quote_status(
                        quote_id=quote_id,
                        to_status="client_negotiation",
                        actor_id=user_id,
                        actor_roles=user_roles,
                        comment="Partial recalculation: logistics updated, returning to client negotiation"
                    )
            except Exception as e:
                print(f"Error checking partial_recalc: {e}")

    return RedirectResponse(f"/logistics/{quote_id}", status_code=303)


# ============================================================================
# LOGISTICS - RETURN TO QUOTE CONTROL (Feature: multi-department return)
# ============================================================================

# @rt("/logistics/{quote_id}/return-to-control")
def get(quote_id: str, session):
    """
    Form for logistics to return a revised quote back to quote control.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["logistics", "admin", "head_of_logistics"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data
    workflow_status = quote.get("workflow_status", "draft")
    revision_comment = quote.get("revision_comment", "")
    idn_quote = quote.get("idn_quote", f"#{quote_id[:8]}")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    if workflow_status != "pending_logistics":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}»."),
            A("← Назад", href=f"/logistics/{quote_id}"),
            session=session
        )

    # Design system styles
    header_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 24px;
    """

    form_card_style = """
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 24px;
    """

    section_header_style = """
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    """

    comment_box_style = """
        background: #fef3c7;
        border-left: 3px solid #f59e0b;
        padding: 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 24px;
    """

    textarea_style = """
        width: 100%;
        min-height: 120px;
        padding: 12px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-size: 14px;
        background: #f8fafc;
        font-family: inherit;
        resize: vertical;
        box-sizing: border-box;
    """

    return page_layout(f"Вернуть на проверку - {idn_quote}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), f" Назад к логистике", href=f"/logistics/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1("Вернуть КП на проверку",
               style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            Div(
                icon("file-text", size=14, style="color: #64748b;"),
                Span(f"КП: {idn_quote}", style="color: #475569; font-weight: 500;"),
                Span(" • ", style="color: #cbd5e1;"),
                Span(f"Клиент: {customer_name}", style="color: #64748b;"),
                style="display: flex; align-items: center; gap: 8px; font-size: 14px;"
            ),
            style=header_style
        ),

        # Original comment (if present)
        Div(
            Div(icon("message-circle", size=14), " Исходный комментарий контроллёра", style=section_header_style),
            P(revision_comment if revision_comment else "— нет комментария —",
              style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.5;"),
            style=comment_box_style
        ) if revision_comment else None,

        # Form
        Form(
            Div(
                Div(icon("edit-3", size=14), " Комментарий об исправлениях *", style=section_header_style),
                P("Опишите, какие исправления были внесены:",
                  style="color: #64748b; font-size: 13px; margin: 0 0 12px 0;"),
                Textarea(
                    name="comment",
                    placeholder="Исправлены расчёты доставки...\nИзменены маршруты...\nОбновлены сроки...",
                    required=True,
                    style=textarea_style
                ),
                style="margin-bottom: 24px;"
            ),
            Div(
                Button(icon("check", size=14), " Вернуть на проверку", type="submit",
                       style="padding: 10px 20px; background: #22c55e; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/logistics/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                style="display: flex; gap: 12px;"
            ),
            action=f"/logistics/{quote_id}/return-to-control",
            method="post",
            style=form_card_style
        ),
        session=session
    )


# @rt("/logistics/{quote_id}/return-to-control")
def post(quote_id: str, session, comment: str = ""):
    """
    Handle return to quote control from logistics.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["logistics", "admin", "head_of_logistics"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий об исправлениях."),
            A("← Вернуться", href=f"/logistics/{quote_id}/return-to-control"),
            session=session
        )

    supabase = get_supabase()

    quote_result = supabase.table("quotes") \
        .select("workflow_status") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            A("← К задачам", href="/tasks"),
            session=session
        )

    current_status = quote_result.data[0].get("workflow_status", "draft")

    if current_status != "pending_logistics":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}»."),
            A("← Назад", href=f"/logistics/{quote_id}"),
            session=session
        )

    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_QUOTE_CONTROL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"Исправления от логистики: {comment.strip()}"
    )

    if result.success:
        supabase.table("quotes").update({
            "revision_department": None,
            "revision_comment": None,
            "revision_returned_at": None
        }).eq("id", quote_id).execute()

        return page_layout("Успешно",
            H1(icon("check", size=28), " КП возвращено на проверку"),
            P("КП отправлено контроллёру КП для повторной проверки."),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось вернуть КП: {result.error_message}"),
            A("← Назад", href=f"/logistics/{quote_id}/return-to-control"),
            session=session
        )

# ============================================================================
# CUSTOMS CLUSTER (Feature #42, #44, #45 + GTD import [86aftzmne])
# 12 routes: /customs (redirect), /customs/declarations (registry),
# /customs/declarations/upload GET+POST, /customs/declarations/upload/preview,
# /customs/declarations/upload/confirm,
# /customs/declarations/{declaration_id}/items, /customs/{quote_id} GET+POST,
# /customs/{quote_id}/items/{item_id} PATCH,
# /customs/{quote_id}/return-to-control GET+POST
# ============================================================================
# ============================================================================
# CUSTOMS WORKSPACE (Feature #42)
# ============================================================================

# @rt("/customs")
def get(session, status_filter: str = None):
    """
    Redirect to unified dashboard customs tab.
    Old URL preserved for backwards compatibility.
    """
    url = "/dashboard?tab=customs"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


# ============================================================================
# CUSTOMS DECLARATIONS (GTD) - XML IMPORT & REGISTRY
# Feature [86aftzmne]: GTD XML import + customs payments in plan-fact
# ============================================================================

# @rt("/customs/declarations")
def get(session, uploaded: str = "", matched: str = ""):
    """Registry of all uploaded GTD customs declarations with HTMX-expandable item rows."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["customs", "admin", "finance"]):
        return RedirectResponse("/unauthorized", status_code=303)

    user = session["user"]
    org_id = user["org_id"]

    declarations = list_declarations(org_id)

    th = "padding:10px 14px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;background:#f8fafc;border-bottom:2px solid #e2e8f0;"
    td_base = "padding:10px 14px;font-size:13px;color:#1e293b;border-bottom:1px solid #f1f5f9;"

    rows = []
    for d in declarations:
        decl_id = d["id"]
        item_count = d.get("item_count", 0)
        matched_count = d.get("matched_count", 0)
        match_badge = (
            Span(f"{matched_count}/{item_count} совпад.", style="background:#d1fae5;color:#059669;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;")
            if matched_count > 0
            else Span("Нет совпадений", style="background:#f1f5f9;color:#94a3b8;padding:2px 8px;border-radius:4px;font-size:11px;")
        )

        decl_date = d.get("declaration_date") or "—"
        rows.append(Tr(
            Td(
                Span("▶", id=f"arrow-{decl_id}", style="margin-right:6px;font-size:10px;color:#94a3b8;transition:transform 0.2s;"),
                A(d.get("regnum", "—"), href="#",
                  onclick=f"toggleGTDItems('{decl_id}'); return false;",
                  style="color:#3b82f6;text-decoration:none;font-weight:500;"),
                style=td_base
            ),
            Td(str(decl_date)[:10], style=td_base),
            Td((d.get("sender_name") or "—")[:40], style=td_base),
            Td(d.get("internal_ref") or "—", style=td_base),
            Td(f"{float(d.get('total_customs_value_rub') or 0):,.0f}", style=f"{td_base} text-align:right;"),
            Td(f"{float(d.get('total_duty_rub') or 0):,.0f}", style=f"{td_base} text-align:right;"),
            Td(f"{float(d.get('total_fee_rub') or 0):,.0f}", style=f"{td_base} text-align:right;"),
            Td(str(item_count), style=f"{td_base} text-align:center;"),
            Td(match_badge, style=td_base),
            style="cursor:pointer;",
            onclick=f"toggleGTDItems('{decl_id}')"
        ))
        # Expandable items row (collapsed by default, lazy-loaded via HTMX)
        rows.append(Tr(
            Td(
                Div(id=f"gtd-items-{decl_id}",
                    hx_get=f"/customs/declarations/{decl_id}/items",
                    hx_trigger="load-items",
                    hx_swap="innerHTML",
                    style="display:none;"),
                colspan="9", style="padding:0;border-bottom:1px solid #e2e8f0;"
            ),
            id=f"gtd-row-{decl_id}",
            style="display:none;"
        ))

    toggle_js = Script("""
        function toggleGTDItems(declId) {
            var row = document.getElementById('gtd-row-' + declId);
            var div = document.getElementById('gtd-items-' + declId);
            var arrow = document.getElementById('arrow-' + declId);
            if (!row) return;
            if (row.style.display === 'none' || row.style.display === '') {
                row.style.display = 'table-row';
                div.style.display = 'block';
                if (arrow) arrow.style.transform = 'rotate(90deg)';
                // Trigger HTMX load on first expand
                if (div && div.innerHTML.trim() === '') {
                    htmx.trigger(div, 'load-items');
                }
            } else {
                row.style.display = 'none';
                div.style.display = 'none';
                if (arrow) arrow.style.transform = 'rotate(0deg)';
            }
        }
    """)

    success_banner = None
    if uploaded:
        success_banner = Div(
            f"Декларация {uploaded} успешно загружена. Совпадений с позициями сделок: {matched}.",
            style="background:#d1fae5;border-left:4px solid #10b981;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:14px;"
        )

    return page_layout(
        "Реестр таможенных деклараций",
        success_banner,
        Div(
            Div(
                icon("file-text", size=24, color="#8b5cf6"),
                Span("Таможенные декларации (ДТ)", style="font-size:22px;font-weight:600;color:#1e293b;margin-left:10px;"),
                Span(str(len(declarations)), style="background:#ede9fe;color:#7c3aed;font-size:12px;font-weight:600;padding:4px 10px;border-radius:12px;margin-left:12px;"),
                style="display:flex;align-items:center;flex:1;"
            ),
            btn_link("Загрузить ДТ", href="/customs/declarations/upload", variant="primary", icon_name="upload"),
            style="display:flex;align-items:center;justify-content:space-between;background:linear-gradient(135deg,#fafbfc 0%,#f4f5f7 100%);border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:20px;"
        ),
        Div(
            Div(
                Table(
                    Thead(Tr(
                        Th("Номер ДТ", style=th), Th("Дата", style=th),
                        Th("Отправитель", style=th), Th("Внутр. ссылка", style=th),
                        Th("Там. стоимость, руб.", style=f"{th} text-align:right;"),
                        Th("Пошлина, руб.", style=f"{th} text-align:right;"),
                        Th("Сбор, руб.", style=f"{th} text-align:right;"),
                        Th("Позиций", style=f"{th} text-align:center;"),
                        Th("Совпадения", style=th),
                    )),
                    Tbody(*rows) if rows else Tbody(
                        Tr(Td("Декларации ещё не загружены", colspan="9",
                               style="text-align:center;padding:40px;color:#94a3b8;"))
                    ),
                    style="width:100%;border-collapse:collapse;"
                ),
                style="overflow-x:auto;"
            ),
            toggle_js,
            style="background:white;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.04);border:1px solid #e2e8f0;"
        ),
        session=session,
        current_path="/customs/declarations"
    )


# @rt("/customs/declarations/upload")
def get(session):
    """GTD XML upload page - file selector form."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["customs", "admin", "finance"]):
        return RedirectResponse("/unauthorized", status_code=303)

    return page_layout(
        "Загрузка ДТ",
        Div(
            Div(
                icon("file-text", size=24, color="#8b5cf6"),
                Span("Загрузка таможенной декларации (ДТ)", style="font-size:22px;font-weight:600;color:#1e293b;margin-left:10px;"),
                style="display:flex;align-items:center;margin-bottom:8px;"
            ),
            P("Загрузите XML-файл в формате AltaGTD (кодировка windows-1251)", style="color:#64748b;font-size:14px;margin:0;"),
            style="background:linear-gradient(135deg,#fafbfc 0%,#f4f5f7 100%);border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.04);"
        ),
        Div(
            Form(
                Div(
                    Label("XML-файл декларации (.xml)", style="display:block;font-size:13px;font-weight:500;color:#374151;margin-bottom:6px;"),
                    Input(type="file", name="gtd_file", accept=".xml", required=True,
                          style="width:100%;padding:10px;border:2px dashed #d1d5db;border-radius:8px;font-size:14px;cursor:pointer;"),
                    style="margin-bottom:16px;"
                ),
                Div(
                    btn("Загрузить и проверить", variant="primary", icon_name="upload", type="submit"),
                    btn_link("Отмена", href="/customs/declarations", variant="secondary", icon_name="arrow-left"),
                    style="display:flex;gap:12px;align-items:center;"
                ),
                action="/customs/declarations/upload",
                method="POST",
                enctype="multipart/form-data",
            ),
            style="background:white;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.04);border:1px solid #e2e8f0;"
        ),
        session=session,
        current_path="/customs/declarations"
    )


# @rt("/customs/declarations/upload")
async def post(session, request):
    """Parse uploaded GTD XML, write to temp file, redirect to preview."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["customs", "admin", "finance"]):
        return RedirectResponse("/unauthorized", status_code=303)

    form = await request.form()
    gtd_file = form.get("gtd_file")

    if not gtd_file or not hasattr(gtd_file, 'filename') or not gtd_file.filename:
        return page_layout("Ошибка",
            Div("Файл не выбран.", style="background:#fee2e2;border-left:4px solid #dc2626;border-radius:8px;padding:16px;"),
            btn_link("Назад", href="/customs/declarations/upload", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    xml_bytes = await gtd_file.read()

    if not xml_bytes:
        return page_layout("Ошибка",
            Div("Файл пустой.", style="background:#fee2e2;border-left:4px solid #dc2626;border-radius:8px;padding:16px;"),
            btn_link("Назад", href="/customs/declarations/upload", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Write to temp file for preview (avoid session cookie 4KB limit)
    user = session["user"]
    user_id = user["id"]
    import uuid as _uuid
    tmp_filename = f"/tmp/gtd_{user_id}_{_uuid.uuid4().hex}.xml"
    with open(tmp_filename, "wb") as f:
        f.write(xml_bytes)

    # Quick validation parse
    result = parse_gtd_xml(tmp_filename)

    if result.errors and not result.regnum:
        # Fatal parsing error - clean up temp file
        try:
            os.unlink(tmp_filename)
        except Exception:
            pass
        return page_layout("Ошибка парсинга",
            Div(
                P("Не удалось прочитать XML-файл:"),
                *[P(f"* {e}", style="color:#dc2626;font-size:13px;") for e in result.errors],
                style="background:#fee2e2;border-left:4px solid #dc2626;border-radius:8px;padding:16px;"
            ),
            btn_link("Назад", href="/customs/declarations/upload", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Store temp file path in session (small string, fits in cookie)
    session["pending_gtd_tmp_file"] = tmp_filename
    session["pending_gtd_filename"] = gtd_file.filename

    return RedirectResponse("/customs/declarations/upload/preview", status_code=303)


# @rt("/customs/declarations/upload/preview")
def get(session):
    """Preview parsed GTD data before saving to database."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["customs", "admin", "finance"]):
        return RedirectResponse("/unauthorized", status_code=303)

    tmp_file = session.get("pending_gtd_tmp_file")
    if not tmp_file:
        return RedirectResponse("/customs/declarations/upload", status_code=303)

    # Check file still exists
    if not os.path.exists(tmp_file):
        session.pop("pending_gtd_tmp_file", None)
        session.pop("pending_gtd_filename", None)
        return RedirectResponse("/customs/declarations/upload", status_code=303)

    result = parse_gtd_xml(tmp_file)

    th = "padding:8px 12px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;background:#f8fafc;border-bottom:1px solid #e2e8f0;"
    td = "padding:8px 12px;font-size:13px;color:#1e293b;border-bottom:1px solid #f1f5f9;"

    items_rows = []
    for item in result.items:
        desc = item.description or ""
        items_rows.append(
            Tr(
                Td(item.hs_code or "—", style=td),
                Td(item.sku or "—", style=td),
                Td(desc[:60] + ("..." if len(desc) > 60 else ""), style=td),
                Td(item.brand or "—", style=td),
                Td(f"{int(item.quantity)} {item.unit or ''}", style=td),
                Td(f"{float(item.invoice_cost):,.2f} {result.currency or ''}", style=td),
                Td(f"{float(item.customs_value_rub):,.2f}", style=td),
                Td(f"{float(item.duty_rub):,.2f}", style=td),
                Td(f"{float(item.fee_rub):,.2f}", style=td),
                Td(f"{float(item.vat_rub):,.2f}", style=td),
            )
        )

    # Warnings section
    warnings = None
    if result.errors:
        warnings = Div(
            *[Div(f"Предупреждение: {e}", style="background:#fef3c7;border-left:4px solid #f59e0b;border-radius:6px;padding:10px 14px;margin-bottom:8px;font-size:13px;")
              for e in result.errors],
        )

    return page_layout(
        "Предпросмотр ДТ",
        # Header summary card
        Div(
            Div(H3(f"ДТ No {result.regnum}", style="margin:0;font-size:18px;font-weight:700;"),
                P(f"Дата: {result.declaration_date} | Внутр. ссылка: {result.internal_ref or '—'}", style="color:#64748b;font-size:13px;margin:4px 0 0 0;"),
                style="flex:1;"),
            Div(
                P(f"Отправитель: {result.sender_name} ({result.sender_country})", style="font-size:13px;margin:0 0 4px 0;"),
                P(f"Получатель: {result.receiver_name} (ИНН: {result.receiver_inn})", style="font-size:13px;margin:0 0 4px 0;"),
                P(f"Валюта: {result.currency} | Курс: {result.exchange_rate}", style="font-size:13px;margin:0;"),
                style="flex:1;"
            ),
            Div(
                P(f"Там. стоимость: {float(result.total_customs_value_rub):,.2f} руб.", style="font-size:13px;font-weight:600;margin:0 0 4px 0;"),
                P(f"Сбор (1010): {float(result.total_fee_rub):,.2f} руб.", style="font-size:13px;margin:0 0 4px 0;"),
                P(f"Пошлина (2010): {float(result.total_duty_rub):,.2f} руб.", style="font-size:13px;margin:0 0 4px 0;"),
                P(f"НДС (5010): {float(result.total_vat_rub):,.2f} руб.", style="font-size:13px;margin:0;"),
                style="flex:1;"
            ),
            style="display:flex;gap:24px;background:white;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:16px;"
        ),
        # Warnings
        warnings,
        # Items table
        Div(
            H4(f"Позиции ({len(result.items)} шт.)", style="margin:0 0 12px 0;font-size:15px;font-weight:600;"),
            Div(
                Table(
                    Thead(Tr(
                        Th("Код ТН ВЭД", style=th), Th("SKU", style=th), Th("Описание", style=th),
                        Th("Бренд", style=th), Th("Кол-во", style=th), Th("Ст-ть инвойса", style=th),
                        Th("Там. ст-ть, руб.", style=th), Th("Пошлина, руб.", style=th),
                        Th("Сбор, руб.", style=th), Th("НДС, руб.", style=th),
                    )),
                    Tbody(*items_rows) if items_rows else Tbody(
                        Tr(Td("Нет позиций", colspan="10", style="text-align:center;padding:20px;color:#94a3b8;"))
                    ),
                    style="width:100%;border-collapse:collapse;"
                ),
                style="overflow-x:auto;"
            ),
            style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:16px;"
        ),
        # Confirm / Cancel buttons
        Div(
            Form(
                btn("Сохранить декларацию", variant="primary", icon_name="save", type="submit"),
                action="/customs/declarations/upload/confirm",
                method="POST",
                style="display:inline;"
            ),
            btn_link("Отмена", href="/customs/declarations/upload", variant="secondary", icon_name="x"),
            style="display:flex;gap:12px;align-items:center;"
        ),
        session=session,
        current_path="/customs/declarations"
    )


# @rt("/customs/declarations/upload/confirm")
def post(session):
    """Save parsed GTD from temp file to database, then run deal matching."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["customs", "admin", "finance"]):
        return RedirectResponse("/unauthorized", status_code=303)

    user = session["user"]
    org_id = user["org_id"]
    user_id = user["id"]

    tmp_file = session.get("pending_gtd_tmp_file")
    if not tmp_file:
        return RedirectResponse("/customs/declarations/upload", status_code=303)

    if not os.path.exists(tmp_file):
        session.pop("pending_gtd_tmp_file", None)
        session.pop("pending_gtd_filename", None)
        return RedirectResponse("/customs/declarations/upload", status_code=303)

    result = parse_gtd_xml(tmp_file)

    # Read raw XML for storage
    try:
        with open(tmp_file, "rb") as f:
            raw_bytes = f.read()
        xml_text = raw_bytes.decode("windows-1251", errors="replace")
    except Exception:
        xml_text = ""

    try:
        declaration_id = save_declaration(result, org_id, xml_text, user_id)
    except Exception as e:
        error_str = str(e)
        if "customs_declarations_regnum_organization_id" in error_str or "duplicate" in error_str.lower():
            return page_layout("Ошибка",
                Div(f"Декларация {result.regnum} уже загружена.", style="background:#fee2e2;border-left:4px solid #dc2626;border-radius:8px;padding:16px;font-size:14px;"),
                btn_link("Назад", href="/customs/declarations", variant="secondary", icon_name="arrow-left"),
                session=session
            )
        return page_layout("Ошибка",
            Div(f"Ошибка сохранения: {error_str}", style="background:#fee2e2;border-left:4px solid #dc2626;border-radius:8px;padding:16px;font-size:14px;"),
            btn_link("Назад", href="/customs/declarations/upload", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Clean up temp file and session
    try:
        os.unlink(tmp_file)
    except Exception:
        pass
    session.pop("pending_gtd_tmp_file", None)
    session.pop("pending_gtd_filename", None)

    # Run matching (best-effort, non-blocking)
    try:
        matched_count = match_items_to_deals(declaration_id, org_id)
    except Exception as e:
        print(f"Warning: GTD matching failed (non-fatal): {e}")
        matched_count = 0

    return RedirectResponse(f"/customs/declarations?uploaded={result.regnum}&matched={matched_count}", status_code=303)


# @rt("/customs/declarations/{declaration_id}/items")
def get(session, declaration_id: str):
    """HTMX partial: return items table for a declaration (lazy-loaded on first expand)."""
    redirect = require_login(session)
    if redirect:
        return Div("Требуется вход", style="color:#ef4444;padding:12px;")

    if not user_has_any_role(session, ["customs", "admin", "finance"]):
        return Div("Нет доступа", style="color:#ef4444;padding:12px;")

    user = session["user"]
    org_id = user["org_id"]

    items = get_declaration_items(declaration_id, org_id)

    if not items:
        return Div("Позиции не найдены", style="padding:16px;color:#94a3b8;font-size:13px;")

    sub_th = "padding:6px 10px;font-size:11px;font-weight:600;color:#64748b;background:#f8fafc;border-bottom:1px solid #e2e8f0;text-align:left;"
    sub_td = "padding:6px 10px;font-size:12px;color:#374151;border-bottom:1px solid #f8fafc;"

    rows = []
    for item in items:
        match_cell = (
            Td(A("Сделка", href=f"/finance/{item['deal_id']}", style="color:#3b82f6;font-size:11px;"),
               style=sub_td)
            if item.get("deal_id")
            else Td(Span("—", style="color:#94a3b8;"), style=sub_td)
        )
        rows.append(Tr(
            Td(f"{item.get('block_number', '')}.{item.get('item_number', '')}", style=sub_td),
            Td(item.get("sku") or "—", style=sub_td),
            Td((item.get("description") or "")[:50], style=sub_td),
            Td(item.get("brand") or "—", style=sub_td),
            Td(item.get("hs_code") or "—", style=sub_td),
            Td(f"{float(item.get('quantity') or 0):,.2f} {item.get('unit') or ''}", style=sub_td),
            Td(f"{float(item.get('invoice_cost') or 0):,.2f} {item.get('invoice_currency') or ''}", style=sub_td),
            Td(f"{float(item.get('customs_value_rub') or 0):,.2f}", style=sub_td),
            Td(f"{float(item.get('duty_amount_rub') or 0):,.2f}", style=sub_td),
            Td(f"{float(item.get('fee_amount_rub') or 0):,.2f}", style=sub_td),
            Td(f"{float(item.get('vat_amount_rub') or 0):,.2f}", style=sub_td),
            match_cell,
        ))

    return Div(
        Table(
            Thead(Tr(
                Th("Блок.поз.", style=sub_th), Th("SKU", style=sub_th),
                Th("Описание", style=sub_th), Th("Бренд", style=sub_th),
                Th("Код ТН ВЭД", style=sub_th), Th("Кол-во", style=sub_th),
                Th("Ст-ть инвойса", style=sub_th), Th("Там. ст-ть, руб.", style=sub_th),
                Th("Пошлина, руб.", style=sub_th), Th("Сбор, руб.", style=sub_th),
                Th("НДС, руб.", style=sub_th), Th("Сделка", style=sub_th),
            )),
            Tbody(*rows),
            style="width:100%;border-collapse:collapse;"
        ),
        style="padding:0 0 8px 0;overflow-x:auto;background:#fafbff;"
    )


# ============================================================================
# CUSTOMS DETAIL PAGE (Feature #44, #45)
# ============================================================================

# @rt("/customs/{quote_id}")
def get(session, quote_id: str, error: str = ""):
    """
    Customs detail page - view and edit customs data for each item in a quote.

    Feature UI-021 (v3.0): Customs workspace view
    - Shows quote summary and items with item-level customs data (hs_code, duty %)
    - Shows quote-level costs section (5 fields: brokerage, SVH, documentation)
    - Pickup location and supplier display for each item (v3.0 supply chain)
    - Only editable when quote is in pending_customs or pending_logistics status
    - Uses v3.0 field names: hs_code, customs_duty (no per-item extra costs)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has customs role (includes head_of_customs for v3.0)
    if not user_has_any_role(session, ["customs", "admin", "head_of_customs"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("Quote Not Found"),
            P("The requested quote was not found or you don't have access."),
            A("← Назад к задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    customer_name = (quote.get("customers") or {}).get("name", "Unknown")
    currency = quote.get("currency", "RUB")

    # Check for revision status (returned from quote control)
    revision_department = quote.get("revision_department")
    revision_comment = quote.get("revision_comment")
    is_revision = revision_department == "customs" and workflow_status == "pending_customs"

    # Fetch quote items with v3.0 customs and supply chain fields (extra costs at quote level)
    # License columns: license_ds_required (checkbox), license_ds_cost (numeric),
    #   license_ss_required (checkbox), license_ss_cost (numeric),
    #   license_sgr_required (checkbox), license_sgr_cost (numeric)
    items_result = supabase.table("quote_items") \
        .select("""
            id, brand, product_code, product_name, quantity, unit,
            base_price_vat, purchase_price_original, purchase_currency,
            weight_in_kg, volume_m3, supplier_country,
            pickup_location_id, supplier_id,
            hs_code, customs_duty,
            license_ds_required, license_ds_cost,
            license_ss_required, license_ss_cost,
            license_sgr_required, license_sgr_cost
        """) \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    items = items_result.data or []

    # Fetch invoices for procurement notes display
    invoices_result = supabase.table("invoices") \
        .select("id, invoice_number, procurement_notes") \
        .eq("quote_id", quote_id) \
        .execute()
    customs_invoices = invoices_result.data or []
    procurement_notes_list = [inv for inv in customs_invoices if inv.get("procurement_notes")]

    # Load calculation variables (for quote-level costs)
    calc_vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_vars = {}
    if calc_vars_result.data:
        calc_vars = calc_vars_result.data[0].get("variables", {})

    # Extract quote-level customs costs (defaults to 0)
    brokerage_hub = calc_vars.get("brokerage_hub", 0)
    brokerage_customs = calc_vars.get("brokerage_customs", 0)
    warehousing_at_customs = calc_vars.get("warehousing_at_customs", 0)
    customs_documentation = calc_vars.get("customs_documentation", 0)
    brokerage_extra = calc_vars.get("brokerage_extra", 0)

    # Extract currency for each brokerage field (default RUB - as per user feedback these are typically in rubles)
    brokerage_hub_currency = calc_vars.get("brokerage_hub_currency", "RUB")
    brokerage_customs_currency = calc_vars.get("brokerage_customs_currency", "RUB")
    warehousing_at_customs_currency = calc_vars.get("warehousing_at_customs_currency", "RUB")
    customs_documentation_currency = calc_vars.get("customs_documentation_currency", "RUB")
    brokerage_extra_currency = calc_vars.get("brokerage_extra_currency", "RUB")

    # Check if quote is ready for customs (procurement must be done first)
    ready_for_customs_statuses = ["pending_customs", "pending_logistics", "pending_logistics_and_customs", "pending_sales_review"]
    is_ready_for_customs = workflow_status in ready_for_customs_statuses

    # Check if customs is editable (only when ready and not completed)
    is_editable = is_ready_for_customs and quote.get("customs_completed_at") is None
    customs_done = quote.get("customs_completed_at") is not None

    # Check if customs can be completed
    can_complete_customs = is_ready_for_customs and not customs_done

    # v3.0: Fetch pickup location info for items
    pickup_location_map = {}
    pickup_location_ids = [item.get("pickup_location_id") for item in items if item.get("pickup_location_id")]
    if pickup_location_ids:
        try:
            from services.location_service import get_location, format_location_for_dropdown
            for pickup_location_id in set(pickup_location_ids):
                try:
                    loc = get_location(pickup_location_id)
                    if loc:
                        pickup_location_map[pickup_location_id] = {
                            "id": loc.id,
                            "label": format_location_for_dropdown(loc).get("label", loc.display_name or f"{loc.city}, {loc.country}"),
                            "city": loc.city,
                            "country": loc.country
                        }
                except Exception:
                    pass
        except ImportError:
            pass

    # v3.0: Fetch supplier info for items
    supplier_map = {}
    supplier_ids = [item.get("supplier_id") for item in items if item.get("supplier_id")]
    if supplier_ids:
        try:
            from services.supplier_service import get_supplier, format_supplier_for_dropdown
            for supplier_id in set(supplier_ids):
                try:
                    sup = get_supplier(supplier_id)
                    if sup:
                        supplier_map[supplier_id] = {
                            "id": sup.id,
                            "label": format_supplier_for_dropdown(sup).get("label", sup.name),
                            "country": sup.country
                        }
                except Exception:
                    pass
        except ImportError:
            pass

    # Calculate summary stats with v3.0 fields
    total_items = len(items)
    items_with_hs = sum(1 for item in items if item.get("hs_code"))
    items_with_customs = 0
    total_customs_cost = 0

    for item in items:
        duty_percent = float(item.get("customs_duty") or 0)
        purchase_price = float(item.get("purchase_price_original") or item.get("base_price_vat") or 0)
        quantity = float(item.get("quantity") or 1)

        # Calculate duty amount based on purchase price * duty percent (extra costs now at quote level)
        duty_amount = purchase_price * quantity * (duty_percent / 100)
        item_customs_total = duty_amount

        if item.get("hs_code") and item.get("customs_duty") is not None:
            items_with_customs += 1
        total_customs_cost += item_customs_total

    # Calculate license summary stats
    _license_types = ["ds", "ss", "sgr"]
    license_counts = {}
    for _lt in _license_types:
        _key = f"license_{_lt}_required"
        license_counts[_lt] = sum(1 for item in items if item.get(_key))
    total_license_cost = sum(
        sum(float(item.get(f"license_{_lt}_cost") or 0) for _lt in _license_types)
        for item in items
    )

    # Prepare items data for Handsontable (JSON)
    def _build_customs_item(item, idx):
        row = {
            'id': item.get('id'),
            'row_num': idx + 1,
            'brand': item.get('brand', ''),
            'product_code': item.get('product_code', ''),
            'product_name': item.get('product_name', ''),
            'quantity': item.get('quantity', 1),
            'supplier_country': COUNTRY_NAME_MAP.get(item.get('supplier_country', ''), item.get('supplier_country', '')),
            'hs_code': item.get('hs_code') or '',
            'customs_duty': float(item.get('customs_duty') or 0),
        }
        for _lt in _license_types:
            row[f"license_{_lt}_required"] = bool(item.get(f"license_{_lt}_required") or False)
            row[f"license_{_lt}_cost"] = float(item.get(f"license_{_lt}_cost") or 0)
        return row
    items_for_handsontable = [_build_customs_item(item, idx) for idx, item in enumerate(items)]
    items_json = json.dumps(items_for_handsontable)

    # Build item cards for v3.0 item-level customs data (DEPRECATED - replaced by Handsontable)
    def customs_item_card(item, idx):
        item_id = item.get("id")
        pickup_info = pickup_location_map.get(item.get("pickup_location_id"))
        supplier_info = supplier_map.get(item.get("supplier_id"))

        # Get current item customs values (v3.0 fields)
        hs_code = item.get("hs_code") or ""
        duty_percent = item.get("customs_duty") or 0

        # Calculate duty amount for display (extra costs now at quote level)
        purchase_price = float(item.get("purchase_price_original") or item.get("base_price_vat") or 0)
        quantity = float(item.get("quantity") or 1)
        duty_amount = purchase_price * quantity * (float(duty_percent) / 100)
        item_customs_total = duty_amount

        # Item completion indicator
        has_customs = hs_code and duty_percent is not None
        status_icon_elem = icon("check-circle", size=16) if has_customs else icon("clock", size=16)
        status_color = "#22c55e" if has_customs else "#f59e0b"

        # Weight/volume reference
        weight = item.get("weight_kg") or item.get("weight_in_kg") or 0
        volume = item.get("volume_m3") or 0

        return Div(
            # Item header
            Div(
                Div(
                    Span(status_icon_elem, style=f"color: {status_color}; margin-right: 0.25rem;"),
                    Strong(item.get("brand", "—")),
                    Span(f" — {(item.get('product_name') or '—')[:50]}", style="color: #666;"),
                    style="flex: 1; display: flex; align-items: center;"
                ),
                Span(f"#{idx+1}", style="color: #999; font-size: 0.875rem;"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;"
            ),

            # Item info badges
            Div(
                Span(icon("package", size=14), f" Кол-во: {item.get('quantity', 0)}", style="margin-right: 1rem; font-size: 0.875rem; display: inline-flex; align-items: center; gap: 0.25rem;"),
                Span(icon("scale", size=14), f" Вес: {weight} кг", style="margin-right: 1rem; font-size: 0.875rem; display: inline-flex; align-items: center; gap: 0.25rem;") if weight else None,
                Span(icon("globe", size=14), f" {item.get('supplier_country', '—')}", style="margin-right: 1rem; font-size: 0.875rem; display: inline-flex; align-items: center; gap: 0.25rem;"),
                # Pickup location badge (v3.0)
                Span(
                    icon("map-pin", size=14), f" {pickup_info['label'] if pickup_info else '—'}",
                    style="font-size: 0.875rem; color: #cc6600;",
                    title=f"Точка отгрузки: {pickup_info['city']}, {pickup_info['country']}" if pickup_info else "Точка отгрузки не указана"
                ) if pickup_info or item.get("pickup_location_id") else None,
                # Supplier badge (v3.0)
                Span(
                    icon("building-2", size=14), f" {supplier_info['label'][:30] if supplier_info else '—'}",
                    style="font-size: 0.875rem; color: #3b82f6; margin-left: 0.5rem;",
                    title=f"Поставщик: {supplier_info['label']}" if supplier_info else "Поставщик не указан"
                ) if supplier_info or item.get("supplier_id") else None,
                style="margin-bottom: 1rem; display: flex; flex-wrap: wrap; gap: 0.25rem;"
            ),

            # Customs data inputs (v3.0 - item level)
            Div(
                H4(icon("shield-check", size=18), " Таможенные данные", style="margin: 0 0 0.75rem; font-size: 0.95rem; color: #374151; display: flex; align-items: center; gap: 0.5rem;"),
                Div(
                    # HS Code (ТН ВЭД)
                    Div(
                        Label("Код ТН ВЭД",
                            Input(
                                name=f"hs_code_{item_id}",
                                type="text",
                                value=hs_code,
                                placeholder="8482.10.10",
                                maxlength="20",
                                disabled=not is_editable,
                                style="width: 100%;"
                            ),
                            style="display: block; font-size: 0.875rem;"
                        ),
                        Small("Формат: XXXX.XX.XX", style="color: #999;"),
                        style="flex: 1;"
                    ),
                    # Duty Percent
                    Div(
                        Label("Пошлина %",
                            Input(
                                name=f"customs_duty_{item_id}",
                                type="number",
                                value=str(duty_percent),
                                min="0",
                                max="100",
                                step="0.01",
                                disabled=not is_editable,
                                style="width: 100%;"
                            ),
                            style="display: block; font-size: 0.875rem;"
                        ),
                        style="flex: 0 0 150px;"
                    ),
                    style="display: flex; gap: 0.75rem;"
                ),
                style="background: #f9fafb; padding: 1rem; border-radius: 4px;"
            ),

            cls="card",
            style="margin-bottom: 1rem; border-left: 3px solid " + (status_color if has_customs else "#e5e7eb") + ";"
        )

    # ==========================================================================
    # CUSTOMS PAGE STYLING (Logistics-inspired compact design)
    # ==========================================================================
    customs_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 16px;
        margin-bottom: 12px;
    """
    customs_section_header_style = "font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; display: flex; align-items: center; gap: 6px;"
    customs_input_row_style = "display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9;"
    customs_field_label_style = "font-size: 13px; color: #64748b; width: 140px; font-weight: 500;"
    customs_input_style = "width: 90px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"

    # Build the item-level customs section with Handsontable
    item_customs_section = Div(
        # Section header with gradient accent
        Div(
            Span(icon("package", size=14), style="color: #64748b;"),
            Span("ТАМОЖНЯ ПО ПОЗИЦИЯМ", style=customs_section_header_style[len("font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; "):]),
            Span(id="customs-items-count", style="margin-left: 0.5rem; color: #64748b; font-size: 12px;"),
            style=customs_section_header_style
        ),
        # Status and description row
        Div(
            P("Заполните код ТН ВЭД и процент пошлины для каждой позиции. Можно копировать из Excel.",
              style="color: #64748b; margin: 0 0 12px 0; font-size: 13px;"),
            Span(id="customs-save-status", style="font-size: 12px; color: #64748b;"),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),
        # Handsontable container with enhanced styling
        Div(
            Div(id="customs-spreadsheet", style="width: 100%; height: 350px; overflow: hidden;"),
            cls="handsontable-container"
        ),
        Small("* Стоимость лицензий (ДС, СС, СГР) указана в рублях (RUB)", style="display: block; margin-top: 8px; color: #64748b; font-size: 12px;"),
        style=customs_card_style
    ) if items else Div(
        Div(
            Span(icon("package", size=14), style="color: #64748b;"),
            Span("ТАМОЖНЯ ПО ПОЗИЦИЯМ", style=customs_section_header_style[len("font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; "):]),
            style=customs_section_header_style
        ),
        P("Нет позиций в КП для таможенного оформления.", style="color: #64748b; font-size: 13px;"),
        style=customs_card_style
    )

    # Helper to create currency options for brokerage fields
    def brokerage_currency_options(selected_currency):
        currencies = [("RUB", "₽ RUB"), ("USD", "$ USD"), ("EUR", "€ EUR"), ("CNY", "¥ CNY"), ("TRY", "₺ TRY")]
        return [Option(label, value=code, selected=(code == selected_currency)) for code, label in currencies]

    # Quote-level costs section (customs/brokerage expenses) - with gradient styling
    customs_costs_card_style = """
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        border-radius: 12px;
        border: 1px solid #fcd34d;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 16px;
        margin-bottom: 12px;
    """
    customs_costs_input_style = "width: 90px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: white;"
    customs_costs_select_style = "width: 70px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; margin-left: 6px;"

    quote_level_costs_section = Div(
        # Section header
        Div(
            Span(icon("wallet", size=14), style="color: #b45309;"),
            Span("ОБЩИЕ РАСХОДЫ НА КП", style="font-size: 11px; font-weight: 600; color: #b45309; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
            style="display: flex; align-items: center; margin-bottom: 12px;"
        ),
        P("Укажите общие расходы на всю квоту. Выберите валюту для каждого поля.",
          style="color: #92400e; margin: 0 0 16px 0; font-size: 13px;"),
        Div(
            # Row 1: brokerage_hub + brokerage_customs
            Div(
                Div(
                    Span("Брокерские (хаб)", style=customs_field_label_style),
                    Div(
                        Input(
                            name="brokerage_hub",
                            type="number",
                            value=str(brokerage_hub),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style=customs_costs_input_style
                        ),
                        Select(
                            *brokerage_currency_options(brokerage_hub_currency),
                            name="brokerage_hub_currency",
                            disabled=not is_editable,
                            style=customs_costs_select_style
                        ),
                        style="display: flex; align-items: center;"
                    ),
                    style=customs_input_row_style
                ),
                Div(
                    Span("Брокерские (таможня)", style=customs_field_label_style),
                    Div(
                        Input(
                            name="brokerage_customs",
                            type="number",
                            value=str(brokerage_customs),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style=customs_costs_input_style
                        ),
                        Select(
                            *brokerage_currency_options(brokerage_customs_currency),
                            name="brokerage_customs_currency",
                            disabled=not is_editable,
                            style=customs_costs_select_style
                        ),
                        style="display: flex; align-items: center;"
                    ),
                    style=customs_input_row_style
                ),
                style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;"
            ),
            # Row 2: warehousing_at_customs + customs_documentation
            Div(
                Div(
                    Span("СВХ", style=customs_field_label_style),
                    Div(
                        Input(
                            name="warehousing_at_customs",
                            type="number",
                            value=str(warehousing_at_customs),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style=customs_costs_input_style
                        ),
                        Select(
                            *brokerage_currency_options(warehousing_at_customs_currency),
                            name="warehousing_at_customs_currency",
                            disabled=not is_editable,
                            style=customs_costs_select_style
                        ),
                        style="display: flex; align-items: center;"
                    ),
                    style=customs_input_row_style
                ),
                Div(
                    Span("Документация", style=customs_field_label_style),
                    Div(
                        Input(
                            name="customs_documentation",
                            type="number",
                            value=str(customs_documentation),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style=customs_costs_input_style
                        ),
                        Select(
                            *brokerage_currency_options(customs_documentation_currency),
                            name="customs_documentation_currency",
                            disabled=not is_editable,
                            style=customs_costs_select_style
                        ),
                        style="display: flex; align-items: center;"
                    ),
                    style=customs_input_row_style
                ),
                style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 8px;"
            ),
            # Row 3: brokerage_extra (half width)
            Div(
                Div(
                    Span("Доп. брокерские", style=customs_field_label_style),
                    Div(
                        Input(
                            name="brokerage_extra",
                            type="number",
                            value=str(brokerage_extra),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style=customs_costs_input_style
                        ),
                        Select(
                            *brokerage_currency_options(brokerage_extra_currency),
                            name="brokerage_extra_currency",
                            disabled=not is_editable,
                            style=customs_costs_select_style
                        ),
                        style="display: flex; align-items: center;"
                    ),
                    style="display: flex; align-items: center; padding: 8px 0;"
                ),
                style="margin-top: 8px; width: 50%;"
            ),
        ),
        style=customs_costs_card_style
    )

    # Quote-level notes section - with gradient styling
    quote_level_section = Div(
        # Section header
        Div(
            Span(icon("message-square", size=14), style="color: #64748b;"),
            Span("ПРИМЕЧАНИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
            style="display: flex; align-items: center; margin-bottom: 12px;"
        ),
        Div(
            Span("Примечания таможенника", style="font-size: 13px; color: #64748b; font-weight: 500; display: block; margin-bottom: 8px;"),
            Textarea(
                quote.get("customs_notes") or "",
                name="customs_notes",
                rows="3",
                disabled=not is_editable,
                style="width: 100%; padding: 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; resize: vertical;"
            ),
        ),
        style=customs_card_style
    )

    # Form wrapper (only for quote-level costs - items saved via Handsontable)
    customs_form = Form(
        # Quote-level costs (brokerage, SVH, documentation)
        quote_level_costs_section,

        # Quote-level notes
        quote_level_section,

        # Action buttons - sticky footer bar
        Div(
            Div(
                btn("Сохранить данные", variant="secondary", icon_name="save", type="submit", name="action", value="save") if is_editable else None,
                btn("✓ Завершить таможню", variant="success", icon_name=None, type="submit", name="action", value="complete") if can_complete_customs else None,
                # Show message when editable but waiting for procurement
                Span(icon("clock", size=16), " Ожидание завершения закупок",
                     style="color: #f59e0b; font-weight: 500; display: inline-flex; align-items: center; gap: 0.25rem;"
                ) if is_editable and not can_complete_customs else None,
                Span(icon("check-circle", size=16), " Таможня завершена", style="color: #22c55e; font-weight: bold; display: inline-flex; align-items: center; gap: 0.25rem;") if customs_done else None,
                style="display: inline-flex; gap: 1rem; align-items: center;"
            ),
            style="margin-top: 1.5rem; padding: 1rem; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;"
        ) if is_editable or customs_done else None,

        method="post",
        action=f"/customs/{quote_id}",
        id="customs-form"
    )

    # Status banners
    # Not ready for customs (still in procurement/draft)
    not_ready_banner = Div(
        P(icon("clock", size=16), " КП ещё не готово для таможни. Ожидается завершение этапа закупок.",
          style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"),
        P(f"Текущий статус: {STATUS_NAMES.get(workflow_status, workflow_status)}",
          style="margin: 0.5rem 0 0; font-size: 0.875rem; color: #666;"),
        style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if not is_ready_for_customs and not customs_done else None

    # Other non-editable status
    status_banner = Div(
        P(icon("alert-triangle", size=16), f" Данный КП в статусе '{STATUS_NAMES.get(workflow_status, workflow_status)}' — редактирование таможни недоступно.",
          style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"),
        style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if is_ready_for_customs and not is_editable and not customs_done else None

    success_banner = Div(
        P(icon("check-circle", size=16), " Таможня по данному КП завершена.",
          style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"),
        style="background-color: #dcfce7; border: 1px solid #22c55e; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if customs_done else None

    error_banner = Div(
        P(
            icon("alert-circle", size=16),
            " Невозможно завершить таможню: не все позиции заполнены кодом ТН ВЭД. Проверьте таблицу и нажмите «Сохранить данные» перед завершением.",
            style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"
        ),
        style="background-color: #fee2e2; border: 1px solid #ef4444; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if error == "hs_code_missing" else None

    # Progress indicator
    progress_percent = int(items_with_hs / total_items * 100) if total_items > 0 else 0

    return page_layout(f"Customs - {quote.get('idn_quote', '')}",
        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "customs", user.get("roles", []), quote=quote, user_id=user_id),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(workflow_status),

        # Revision banner - shown when returned from quote control (Feature: multi-department return)
        Div(
            Div(
                Span("↩ Возвращено на доработку", style="font-weight: 600; font-size: 1.1rem;"),
                style="margin-bottom: 0.5rem;"
            ),
            Div(
                Span("Комментарий контроллёра КП:", style="font-weight: 500;"),
                P(revision_comment, style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap;"),
                style="margin-bottom: 1rem;"
            ) if revision_comment else None,
            Div(
                P("После внесения исправлений верните КП на проверку.", style="margin: 0 0 0.75rem; font-size: 0.875rem;"),
                A("✓ Вернуть на проверку", href=f"/customs/{quote_id}/return-to-control",
                  role="button", style="background: #22c55e; border-color: #22c55e;"),
            ),
            cls="card",
            style="background: #fef3c7; border: 2px solid #f59e0b; margin-bottom: 1rem;"
        ) if is_revision else None,

        # Status banners
        not_ready_banner,
        success_banner,
        error_banner,
        status_banner,

        # Quote summary with customs stats (v3.0) - gradient styling
        Div(
            # Section header
            Div(
                Span(icon("file-text", size=14), style="color: #64748b;"),
                Span("СВОДКА ПО КП", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 12px;"
            ),
            Div(
                Div(
                    Div(str(total_items), cls="stat-value"),
                    Div("Позиций", style="font-size: 12px; color: #64748b;"),
                    cls="stat-card-mini"
                ),
                Div(
                    Div(f"{items_with_hs}/{total_items}", cls="stat-value"),
                    Div("Заполнено ТН ВЭД", style="font-size: 12px; color: #64748b;"),
                    cls="stat-card-mini"
                ),
                Div(
                    Div(f"{items_with_customs}/{total_items}", cls="stat-value"),
                    Div("С пошлиной", style="font-size: 12px; color: #64748b;"),
                    cls="stat-card-mini"
                ),
                style="display: flex; gap: 12px; margin-bottom: 12px;"
            ),
            # Progress bar
            Div(
                Div(
                    Div(style=f"width: {progress_percent}%; height: 100%; background: linear-gradient(90deg, {'#22c55e' if progress_percent == 100 else '#3b82f6'} 0%, {'#4ade80' if progress_percent == 100 else '#60a5fa'} 100%); border-radius: 4px;"),
                    style="background-color: #e2e8f0; height: 8px; border-radius: 4px; overflow: hidden;"
                ),
                P(f"Прогресс: {progress_percent}% ({items_with_hs} из {total_items} позиций)", style="margin-top: 6px; font-size: 12px; color: #64748b;"),
            ),
            cls="customs-summary-card"
        ),

        # Instructions - gradient info card
        Div(
            Div(
                Span(icon("info", size=14), style="color: #1e40af;"),
                Span("ИНСТРУКЦИЯ", style="font-size: 11px; font-weight: 600; color: #1e40af; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 8px;"
            ),
            P("Заполните код ТН ВЭД и пошлину в таблице. Нажмите 'Сохранить данные' для сохранения. Можно копировать из Excel.", style="margin: 0; font-size: 13px; color: #1e40af;"),
            style="background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%); border-radius: 12px; border: 1px solid #93c5fd; padding: 16px; margin-bottom: 12px;"
        ) if is_editable else None,

        # Procurement notes for customs
        Div(
            Div(
                icon("info", size=16, color="#f59e0b"),
                Span(" Комментарии от закупок", style="font-weight: 600; color: #92400e; margin-left: 4px;"),
                style="display: flex; align-items: center; margin-bottom: 8px;"
            ),
            *[Div(
                Span(f"Инвойс {inv.get('invoice_number', '\u2014')}: ", style="font-weight: 500; color: #475569;"),
                Span(inv.get('procurement_notes', ''), style="color: #64748b;"),
                style="padding: 4px 0; font-size: 13px; border-bottom: 1px solid #fef3c7;"
            ) for inv in procurement_notes_list],
            style="background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;"
        ) if procurement_notes_list else None,

        # Items table (Handsontable - explicit save on button click)
        item_customs_section,

        # Quote-level costs form
        customs_form,

        # Transition history (Feature #88)
        workflow_transition_history(quote_id),

        # Additional styles - enhanced with gradient design
        Style("""
            .stat-card-mini {
                background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
                padding: 0.75rem 1rem;
                border-radius: 8px;
                text-align: center;
                border: 1px solid #e2e8f0;
            }
            .stat-card-mini .stat-value {
                font-size: 1.5rem;
                font-weight: bold;
                color: #1e40af;
            }
            .customs-summary-card {
                background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
                border-radius: 12px;
                border: 1px solid #e2e8f0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
                padding: 16px;
                margin-bottom: 12px;
            }
        """),

        # Handsontable initialization script for customs (explicit save, no auto-save)
        Script(f"""
            (function() {{
                var quoteId = '{quote_id}';
                var initialData = {items_json};
                var isEditable = {'true' if is_editable else 'false'};
                var hot = null;
                var hasUnsavedChanges = false;

                function updateCount() {{
                    var count = hot ? hot.countRows() : 0;
                    var el = document.getElementById('customs-items-count');
                    if (el) el.textContent = '(' + count + ' позиций)';
                }}

                function showSaveStatus(status) {{
                    var el = document.getElementById('customs-save-status');
                    if (!el) return;
                    if (status === 'saving') {{
                        el.textContent = 'Сохранение...';
                        el.style.color = '#f59e0b';
                    }} else if (status === 'saved') {{
                        el.textContent = 'Сохранено';
                        el.style.color = '#10b981';
                        setTimeout(function() {{ el.textContent = ''; }}, 2000);
                    }} else if (status === 'error') {{
                        el.textContent = 'Ошибка сохранения';
                        el.style.color = '#ef4444';
                    }}
                }}

                // Save all customs items data (called on form submit)
                window.saveCustomsItems = function() {{
                    if (!hot) return Promise.resolve({{ success: true }});
                    // IMPORTANT: getSourceData() may strip fields not in columns config (like id).
                    // Use initialData array (set at render time) for stable id lookup by row index.
                    hot.deselectCell();
                    var sourceData = hot.getSourceData();
                    var items = sourceData.map(function(row, rowIndex) {{
                        var originalRow = initialData[rowIndex] || {{}};
                        return {{
                            id: originalRow.id,
                            hs_code: row.hs_code || '',
                            customs_duty: parseFloat(row.customs_duty) || 0,
                            license_ds_required: !!row.license_ds_required,
                            license_ds_cost: parseFloat(row.license_ds_cost) || 0,
                            license_ss_required: !!row.license_ss_required,
                            license_ss_cost: parseFloat(row.license_ss_cost) || 0,
                            license_sgr_required: !!row.license_sgr_required,
                            license_sgr_cost: parseFloat(row.license_sgr_cost) || 0
                        }};
                    }}).filter(function(item) {{ return item.id; }});

                    if (items.length === 0) return Promise.resolve({{ success: true }});

                    showSaveStatus('saving');
                    return fetch('/api/customs/' + quoteId + '/items/bulk', {{
                        method: 'PATCH',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ items: items }})
                    }})
                    .then(function(r) {{ return r.json(); }})
                    .then(function(data) {{
                        if (data.success) {{
                            showSaveStatus('saved');
                            hasUnsavedChanges = false;
                        }} else {{
                            showSaveStatus('error');
                        }}
                        return data;
                    }})
                    .catch(function(err) {{
                        showSaveStatus('error');
                        return {{ success: false, error: err.message }};
                    }});
                }};

                function initTable() {{
                    var container = document.getElementById('customs-spreadsheet');
                    if (!container || typeof Handsontable === 'undefined') return;

                    hot = new Handsontable(container, {{
                        licenseKey: 'non-commercial-and-evaluation',
                        data: initialData,
                        colHeaders: ['№', 'Бренд', 'Артикул', 'Наименование', 'Кол-во', 'Страна закупки', 'Код ТН ВЭД', 'Пошлина %', 'ДС', 'Ст-ть ДС', 'СС', 'Ст-ть СС', 'СГР', 'Ст-ть СГР'],
                        columns: [
                            {{data: 'row_num', readOnly: true, type: 'numeric', width: 40,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  td.innerHTML = row + 1;
                                  td.style.textAlign = 'center';
                                  td.style.color = '#666';
                                  td.style.background = '#f9fafb';
                                  return td;
                              }}
                            }},
                            {{data: 'brand', readOnly: true, type: 'text', width: 100,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  td.innerHTML = value || '—';
                                  td.style.color = '#666';
                                  td.style.background = '#f9fafb';
                                  return td;
                              }}
                            }},
                            {{data: 'product_code', readOnly: true, type: 'text', width: 100,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  td.innerHTML = value || '—';
                                  td.style.color = '#666';
                                  td.style.background = '#f9fafb';
                                  return td;
                              }}
                            }},
                            {{data: 'product_name', readOnly: true, type: 'text', width: 250,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  td.innerHTML = (value || '—').substring(0, 50);
                                  td.style.color = '#666';
                                  td.style.background = '#f9fafb';
                                  return td;
                              }}
                            }},
                            {{data: 'quantity', readOnly: true, type: 'numeric', width: 60,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  td.innerHTML = value || 0;
                                  td.style.textAlign = 'center';
                                  td.style.color = '#666';
                                  td.style.background = '#f9fafb';
                                  return td;
                              }}
                            }},
                            {{data: 'supplier_country', readOnly: true, type: 'text', width: 80,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  td.innerHTML = value || '—';
                                  td.style.color = '#666';
                                  td.style.background = '#f9fafb';
                                  return td;
                              }}
                            }},
                            {{data: 'hs_code', type: 'text', width: 120, readOnly: !isEditable}},
                            {{data: 'customs_duty', type: 'numeric', width: 80, readOnly: !isEditable,
                              numericFormat: {{pattern: '0.00'}}
                            }},
                            {{data: 'license_ds_required', type: 'checkbox', width: 40, readOnly: !isEditable, className: 'htCenter'}},
                            {{data: 'license_ds_cost', type: 'numeric', width: 80, readOnly: !isEditable,
                              numericFormat: {{pattern: '0.00'}}
                            }},
                            {{data: 'license_ss_required', type: 'checkbox', width: 40, readOnly: !isEditable, className: 'htCenter'}},
                            {{data: 'license_ss_cost', type: 'numeric', width: 80, readOnly: !isEditable,
                              numericFormat: {{pattern: '0.00'}}
                            }},
                            {{data: 'license_sgr_required', type: 'checkbox', width: 40, readOnly: !isEditable, className: 'htCenter'}},
                            {{data: 'license_sgr_cost', type: 'numeric', width: 80, readOnly: !isEditable,
                              numericFormat: {{pattern: '0.00'}}
                            }}
                        ],
                        rowHeaders: false,
                        stretchH: 'all',
                        autoWrapRow: true,
                        autoWrapCol: true,
                        contextMenu: isEditable ? ['copy', 'cut'] : ['copy'],
                        manualColumnResize: true,
                        afterChange: function(changes, source) {{
                            if (source === 'loadData' || !changes) return;
                            hasUnsavedChanges = true;
                        }}
                    }});

                    updateCount();
                    window.customsHot = hot;

                    // Intercept form submission to save items first
                    var form = document.getElementById('customs-form');
                    if (form && isEditable) {{
                        form.addEventListener('submit', function(e) {{
                            e.preventDefault();
                            var submitBtn = e.submitter;
                            var action = submitBtn ? submitBtn.value : 'save';

                            // Save items first, then submit form
                            window.saveCustomsItems().then(function(result) {{
                                if (result.success) {{
                                    // Create hidden input for action and submit
                                    var actionInput = document.createElement('input');
                                    actionInput.type = 'hidden';
                                    actionInput.name = 'action';
                                    actionInput.value = action;
                                    form.appendChild(actionInput);

                                    // Remove event listener and submit
                                    form.removeEventListener('submit', arguments.callee);
                                    form.submit();
                                }} else {{
                                    alert('Ошибка сохранения данных таможни');
                                }}
                            }});
                        }});
                    }}
                }}

                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initTable);
                }} else {{
                    initTable();
                }}
            }})();
        """) if items else None,

        session=session
    )


# @rt("/customs/{quote_id}")
async def post(session, quote_id: str, request):
    """
    Save customs data for all items and optionally mark customs as complete.

    Feature UI-021 (v3.0): Customs workspace POST handler
    - Saves item-level customs data to quote_items table (hs_code, customs_duty)
    - Saves quote-level costs to quote_calculation_variables (5 fields)
    - Saves quote-level customs_notes
    - Handles 'complete' action to mark customs as done
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Get form data
    form_data = await request.form()
    action = form_data.get("action", "save")
    customs_notes = form_data.get("customs_notes", "")

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role (includes head_of_customs for v3.0)
    if not user_has_any_role(session, ["customs", "admin", "head_of_customs"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify quote exists and belongs to org
    quote_result = supabase.table("quotes") \
        .select("id, workflow_status, customs_completed_at") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return RedirectResponse("/customs", status_code=303)

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is ready for customs (procurement must be done first)
    ready_statuses = ["pending_customs", "pending_logistics", "pending_logistics_and_customs", "pending_sales_review"]
    if workflow_status not in ready_statuses or quote.get("customs_completed_at"):
        return RedirectResponse(f"/customs/{quote_id}", status_code=303)

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    # Helper function for safe decimal conversion
    def safe_decimal(val, default=0):
        try:
            return float(val) if val else default
        except:
            return default

    # NOTE: Item-level customs data (hs_code, customs_duty) is saved via
    # JavaScript bulk PATCH to /api/customs/{quote_id}/items/bulk on form submit.
    # DO NOT add a loop here to update item fields from form_data - the form
    # doesn't contain these fields and it would overwrite saved data with nulls.

    # Save customs notes at quote level
    if customs_notes:
        supabase.table("quotes") \
            .update({"customs_notes": customs_notes}) \
            .eq("id", quote_id) \
            .execute()

    # Save quote-level costs to quote_calculation_variables
    brokerage_hub = safe_decimal(form_data.get("brokerage_hub", 0))
    brokerage_customs = safe_decimal(form_data.get("brokerage_customs", 0))
    warehousing_at_customs = safe_decimal(form_data.get("warehousing_at_customs", 0))
    customs_documentation = safe_decimal(form_data.get("customs_documentation", 0))
    brokerage_extra = safe_decimal(form_data.get("brokerage_extra", 0))

    # Get currency values for each brokerage field (default RUB)
    brokerage_hub_currency = form_data.get("brokerage_hub_currency", "RUB")
    brokerage_customs_currency = form_data.get("brokerage_customs_currency", "RUB")
    warehousing_at_customs_currency = form_data.get("warehousing_at_customs_currency", "RUB")
    customs_documentation_currency = form_data.get("customs_documentation_currency", "RUB")
    brokerage_extra_currency = form_data.get("brokerage_extra_currency", "RUB")

    # Load existing variables or create empty dict
    calc_vars_result = supabase.table("quote_calculation_variables") \
        .select("id, variables") \
        .eq("quote_id", quote_id) \
        .execute()

    if calc_vars_result.data:
        # Update existing record
        calc_var_id = calc_vars_result.data[0]["id"]
        existing_vars = calc_vars_result.data[0].get("variables", {})

        # Update the 5 cost fields and their currencies
        existing_vars["brokerage_hub"] = brokerage_hub
        existing_vars["brokerage_customs"] = brokerage_customs
        existing_vars["warehousing_at_customs"] = warehousing_at_customs
        existing_vars["customs_documentation"] = customs_documentation
        existing_vars["brokerage_extra"] = brokerage_extra
        existing_vars["brokerage_hub_currency"] = brokerage_hub_currency
        existing_vars["brokerage_customs_currency"] = brokerage_customs_currency
        existing_vars["warehousing_at_customs_currency"] = warehousing_at_customs_currency
        existing_vars["customs_documentation_currency"] = customs_documentation_currency
        existing_vars["brokerage_extra_currency"] = brokerage_extra_currency

        supabase.table("quote_calculation_variables") \
            .update({"variables": existing_vars}) \
            .eq("id", calc_var_id) \
            .execute()
    else:
        # Create new record with 5 cost fields and currencies
        import uuid
        supabase.table("quote_calculation_variables") \
            .insert({
                "id": str(uuid.uuid4()),
                "quote_id": quote_id,
                "variables": {
                    "brokerage_hub": brokerage_hub,
                    "brokerage_customs": brokerage_customs,
                    "warehousing_at_customs": warehousing_at_customs,
                    "customs_documentation": customs_documentation,
                    "brokerage_extra": brokerage_extra,
                    "brokerage_hub_currency": brokerage_hub_currency,
                    "brokerage_customs_currency": brokerage_customs_currency,
                    "warehousing_at_customs_currency": warehousing_at_customs_currency,
                    "customs_documentation_currency": customs_documentation_currency,
                    "brokerage_extra_currency": brokerage_extra_currency
                }
            }) \
            .execute()

    # If action is complete, mark customs as done
    if action == "complete":
        # Validate all items have hs_code before completing customs
        hs_check = supabase.table("quote_items") \
            .select("id, hs_code, product_name") \
            .eq("quote_id", quote_id) \
            .execute()
        hs_items = hs_check.data or []
        missing_hs = [item for item in hs_items if not (item.get("hs_code") or "").strip()]
        if missing_hs:
            missing_names = ", ".join(
                item.get("product_name", f"ID {item['id']}")[:30] for item in missing_hs[:3]
            )
            suffix = f" и ещё {len(missing_hs) - 3}" if len(missing_hs) > 3 else ""
            print(f"Customs completion blocked: {len(missing_hs)} items without hs_code: {missing_names}{suffix}")
            return RedirectResponse(f"/customs/{quote_id}?error=hs_code_missing", status_code=303)

        user_roles = get_user_roles_from_session(session)
        result = complete_customs(quote_id, user_id, user_roles)

        if not result.success:
            # Log error but still redirect
            print(f"Error completing customs: {result.error_message}")

    return RedirectResponse(f"/customs/{quote_id}", status_code=303)


# ============================================================================
# CUSTOMS ITEM API (bulk save on form submit)
# ============================================================================
# Phase 6B-9: PATCH /api/customs/{quote_id}/items/bulk moved to api/customs.py
# + routed via api/routers/customs.py on the FastAPI sub-app mounted at /api.


# @rt("/customs/{quote_id}/items/{item_id}")
async def patch(session, quote_id: str, item_id: str, request):
    """Update a single customs item field (legacy - kept for compatibility)"""
    redirect = require_login(session)
    if redirect:
        return {"success": False, "error": "Not authenticated"}

    user = session["user"]
    org_id = user["org_id"]

    # Check role
    if not user_has_any_role(session, ["customs", "admin", "head_of_customs"]):
        return {"success": False, "error": "Unauthorized"}

    try:
        body = await request.json()
    except:
        return {"success": False, "error": "Invalid JSON"}

    supabase = get_supabase()

    # Verify quote exists and belongs to org
    quote_result = supabase.table("quotes") \
        .select("id, workflow_status, customs_completed_at") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return {"success": False, "error": "Quote not found"}

    quote = cast(dict, quote_result.data[0])
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is ready for customs (procurement must be done first)
    ready_statuses = ["pending_customs", "pending_logistics", "pending_logistics_and_customs", "pending_sales_review"]
    if workflow_status not in ready_statuses or quote.get("customs_completed_at"):
        return {"success": False, "error": "Quote not editable - waiting for procurement"}

    # Verify item belongs to quote
    item_result = supabase.table("quote_items") \
        .select("id") \
        .eq("id", item_id) \
        .eq("quote_id", quote_id) \
        .execute()

    if not item_result.data:
        return {"success": False, "error": "Item not found"}

    # Build update dict for allowed fields only
    allowed_fields = ["hs_code", "customs_duty", "license_ds_required", "license_ds_cost", "license_ss_required", "license_ss_cost", "license_sgr_required", "license_sgr_cost"]
    update_data = {}

    for field in allowed_fields:
        if field in body:
            val = body[field]
            if field in ("customs_duty", "license_ds_cost", "license_ss_cost", "license_sgr_cost"):
                try:
                    update_data[field] = float(val) if val is not None else 0
                except:
                    update_data[field] = 0
            elif field in ("license_ds_required", "license_ss_required", "license_sgr_required"):
                update_data[field] = bool(val)
            else:
                update_data[field] = val if val else None

    if not update_data:
        return {"success": False, "error": "No valid fields to update"}

    # Update item
    supabase.table("quote_items") \
        .update(update_data) \
        .eq("id", item_id) \
        .execute()

    return {"success": True}


# ============================================================================
# CUSTOMS - RETURN TO QUOTE CONTROL (Feature: multi-department return)
# ============================================================================

# @rt("/customs/{quote_id}/return-to-control")
def get(quote_id: str, session):
    """
    Form for customs to return a revised quote back to quote control.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["customs", "admin", "head_of_customs"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data
    workflow_status = quote.get("workflow_status", "draft")
    revision_comment = quote.get("revision_comment", "")
    idn_quote = quote.get("idn_quote", f"#{quote_id[:8]}")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    if workflow_status != "pending_customs":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}»."),
            A("← Назад", href=f"/customs/{quote_id}"),
            session=session
        )

    # Design system styles
    header_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 24px;
    """

    form_card_style = """
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 24px;
    """

    section_header_style = """
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    """

    comment_box_style = """
        background: #fef3c7;
        border-left: 3px solid #f59e0b;
        padding: 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 24px;
    """

    textarea_style = """
        width: 100%;
        min-height: 120px;
        padding: 12px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-size: 14px;
        background: #f8fafc;
        font-family: inherit;
        resize: vertical;
        box-sizing: border-box;
    """

    return page_layout(f"Вернуть на проверку - {idn_quote}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), f" Назад к таможне", href=f"/customs/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1("Вернуть КП на проверку",
               style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            Div(
                icon("file-text", size=14, style="color: #64748b;"),
                Span(f"КП: {idn_quote}", style="color: #475569; font-weight: 500;"),
                Span(" • ", style="color: #cbd5e1;"),
                Span(f"Клиент: {customer_name}", style="color: #64748b;"),
                style="display: flex; align-items: center; gap: 8px; font-size: 14px;"
            ),
            style=header_style
        ),

        # Original comment (if present)
        Div(
            Div(icon("message-circle", size=14), " Исходный комментарий контроллёра", style=section_header_style),
            P(revision_comment if revision_comment else "— нет комментария —",
              style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.5;"),
            style=comment_box_style
        ) if revision_comment else None,

        # Form
        Form(
            Div(
                Div(icon("edit-3", size=14), " Комментарий об исправлениях *", style=section_header_style),
                P("Опишите, какие исправления были внесены:",
                  style="color: #64748b; font-size: 13px; margin: 0 0 12px 0;"),
                Textarea(
                    name="comment",
                    placeholder="Исправлены HS-коды...\nОбновлены пошлины...\nИзменены таможенные расходы...",
                    required=True,
                    style=textarea_style
                ),
                style="margin-bottom: 24px;"
            ),
            Div(
                Button(icon("check", size=14), " Вернуть на проверку", type="submit",
                       style="padding: 10px 20px; background: #22c55e; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/customs/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                style="display: flex; gap: 12px;"
            ),
            action=f"/customs/{quote_id}/return-to-control",
            method="post",
            style=form_card_style
        ),
        session=session
    )


# @rt("/customs/{quote_id}/return-to-control")
def post(quote_id: str, session, comment: str = ""):
    """
    Handle return to quote control from customs.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["customs", "admin", "head_of_customs"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий об исправлениях."),
            A("← Вернуться", href=f"/customs/{quote_id}/return-to-control"),
            session=session
        )

    supabase = get_supabase()

    quote_result = supabase.table("quotes") \
        .select("workflow_status") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            A("← К задачам", href="/tasks"),
            session=session
        )

    current_status = quote_result.data[0].get("workflow_status", "draft")

    if current_status != "pending_customs":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}»."),
            A("← Назад", href=f"/customs/{quote_id}"),
            session=session
        )

    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_QUOTE_CONTROL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"Исправления от таможни: {comment.strip()}"
    )

    if result.success:
        supabase.table("quotes").update({
            "revision_department": None,
            "revision_comment": None,
            "revision_returned_at": None
        }).eq("id", quote_id).execute()

        return page_layout("Успешно",
            H1(icon("check", size=28), " КП возвращено на проверку"),
            P("КП отправлено контроллёру КП для повторной проверки."),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось вернуть КП: {result.error_message}"),
            A("← Назад", href=f"/customs/{quote_id}/return-to-control"),
            session=session
        )

# ============================================================================
# /DEALS/{deal_id} LEGACY REDIRECT
# 1 route: /deals/{deal_id} GET → 301 /finance/{deal_id}
# ============================================================================
# @rt("/deals/{deal_id}")
def get(session, deal_id: str, tab: str = "info"):
    """Redirect to /finance/{deal_id} - logistics now lives on the finance page."""
    return RedirectResponse(f"/finance/{deal_id}", status_code=301)


# ============================================================================
# /FINANCE HTMX TAIL (Feature [86aftzex6] + fallback generate-currency-invoices)
# 6 routes + 1 exclusive helper:
#   - /finance/{deal_id}/stages/{stage_id}/expenses POST (deprecated redirect)
#   - /finance/{deal_id}/stages/{stage_id}/status POST
#   - /finance/{deal_id}/logistics-expenses/new-form GET
#   - /finance/{deal_id}/logistics-expenses POST
#   - /finance/{deal_id}/logistics-expenses/{expense_id} DELETE
#   - /finance/{deal_id}/generate-currency-invoices POST
#   - _finance_logistics_expenses_stage_section helper (exclusive)
# ============================================================================
# @rt("/finance/{deal_id}/stages/{stage_id}/expenses")
def post(session, deal_id: str, stage_id: str,
         description: str = "", amount: float = 0, currency: str = "RUB",
         expense_date: str = ""):
    """POST /finance/{deal_id}/stages/{stage_id}/expenses - DEPRECATED.

    Inline expense forms have been removed. Expenses are now added via the
    unified plan-fact tab. This route redirects to the deal page.
    """
    return RedirectResponse(f"/finance/{deal_id}?tab=logistics", status_code=303)


# @rt("/finance/{deal_id}/stages/{stage_id}/status")
def post(session, deal_id: str, stage_id: str, status: str = ""):
    """POST /finance/{deal_id}/stages/{stage_id}/status - Update stage status.

    Calls update_stage_status from logistics_service.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["finance", "admin", "logistics"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify deal belongs to org
    deal_check = supabase.table("deals").select("id").eq("id", deal_id).eq("organization_id", org_id).is_("deleted_at", None).execute()
    if not deal_check.data:
        return RedirectResponse("/deals", status_code=303)

    result = update_stage_status(stage_id, status, deal_id=deal_id)

    return RedirectResponse(f"/finance/{deal_id}?tab=logistics", status_code=303)


# ============================================================================
# Logistics Expenses Routes (Feature [86aftzex6])
# ============================================================================

# @rt("/finance/{deal_id}/logistics-expenses/new-form")
def get(session, deal_id: str, stage_id: str = ""):
    """Return an inline form for adding a new logistics expense to a stage."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["finance", "logistics", "admin", "top_manager"]):
        return P("Нет доступа", style="color: #ef4444;")

    from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS, SUPPORTED_CURRENCIES
    from datetime import date as _date

    today = _date.today().isoformat()

    subtype_options = [Option(label, value=code, selected=(code == "transport"))
                       for code, label in EXPENSE_SUBTYPE_LABELS.items()]

    currency_options = [Option(c, value=c, selected=(c == "USD"))
                        for c in SUPPORTED_CURRENCIES]

    return Div(
        Form(
            Div(
                Div(
                    Label("Тип расхода", style="font-size: 12px; font-weight: 500; color: #374151; margin-bottom: 4px;"),
                    Select(*subtype_options, name="expense_subtype",
                           style="width: 100%; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px;"),
                    style="flex: 1;"
                ),
                Div(
                    Label("Сумма", style="font-size: 12px; font-weight: 500; color: #374151; margin-bottom: 4px;"),
                    Input(type="number", name="amount", step="0.01", min="0.01", required=True, placeholder="0.00",
                          style="width: 100%; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px;"),
                    style="flex: 1;"
                ),
                Div(
                    Label("Валюта", style="font-size: 12px; font-weight: 500; color: #374151; margin-bottom: 4px;"),
                    Select(*currency_options, name="currency",
                           style="width: 100%; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px;"),
                    style="flex: 0 0 100px;"
                ),
                style="display: flex; gap: 10px; margin-bottom: 8px;"
            ),
            Div(
                Div(
                    Label("Дата расхода", style="font-size: 12px; font-weight: 500; color: #374151; margin-bottom: 4px;"),
                    Input(type="date", name="expense_date", value=today, required=True,
                          style="width: 100%; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px;"),
                    style="flex: 0 0 160px;"
                ),
                Div(
                    Label("Описание (необязательно)", style="font-size: 12px; font-weight: 500; color: #374151; margin-bottom: 4px;"),
                    Input(type="text", name="description", placeholder="Описание расхода...", maxlength="500",
                          style="width: 100%; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px;"),
                    style="flex: 1;"
                ),
                style="display: flex; gap: 10px; margin-bottom: 10px;"
            ),
            Input(type="hidden", name="stage_id", value=stage_id),
            Div(
                Button(
                    "Сохранить",
                    type="submit",
                    style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; border: none; border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: 500; cursor: pointer;"
                ),
                Button(
                    "Отмена",
                    type="button",
                    onclick=f"document.getElementById('expense-form-{stage_id}').innerHTML = ''",
                    style="background: #f1f5f9; color: #64748b; border: 1px solid #d1d5db; border-radius: 6px; padding: 6px 16px; font-size: 12px; cursor: pointer; margin-left: 6px;"
                ),
                style="display: flex; gap: 6px;"
            ),
            hx_post=f"/finance/{deal_id}/logistics-expenses",
            hx_target=f"#stage-expenses-{stage_id}",
            hx_swap="outerHTML",
        ),
        style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 10px;"
    )


# @rt("/finance/{deal_id}/logistics-expenses")
def post(session, deal_id: str, stage_id: str = "", expense_subtype: str = "transport",
         amount: str = "0", currency: str = "USD", expense_date: str = "",
         description: str = ""):
    """Create a new logistics expense record."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["finance", "logistics", "admin", "top_manager"]):
        return P("Нет доступа", style="color: #ef4444;")

    user = session["user"]
    org_id = user.get("org_id", "")

    from services.logistics_expense_service import create_expense, sync_plan_fact_for_stage, get_deal_logistics_summary
    from services.logistics_service import get_stages_for_deal
    from decimal import Decimal
    from datetime import date as _date

    # Verify deal belongs to user's org
    supabase = get_supabase()
    deal_check = supabase.table("deals").select("id").eq("id", deal_id).eq("organization_id", org_id).is_("deleted_at", None).execute()
    if not deal_check.data:
        return P("Сделка не найдена", style="color: #ef4444;")

    # Parse and validate amount
    try:
        exp_amount = Decimal(amount)
    except Exception:
        exp_amount = Decimal("0")

    if exp_amount <= 0:
        return P("Сумма должна быть больше нуля", style="color: #ef4444; font-size: 13px; padding: 8px;")

    # Parse date
    try:
        exp_date = _date.fromisoformat(expense_date) if expense_date else _date.today()
    except Exception:
        exp_date = _date.today()

    # Create the expense
    created = create_expense(
        deal_id=deal_id,
        logistics_stage_id=stage_id,
        organization_id=org_id,
        expense_subtype=expense_subtype,
        amount=exp_amount,
        currency=currency,
        expense_date=exp_date,
        description=description if description else None,
        created_by=user.get("id"),
    )

    # Sync plan-fact for this stage
    if created:
        # Find stage code for sync
        stages = get_stages_for_deal(deal_id)
        for s in stages:
            if s.id == stage_id:
                sync_plan_fact_for_stage(deal_id, stage_id, s.stage_code, org_id)
                break

    # Re-render the stage section + OOB total header update
    summary = get_deal_logistics_summary(deal_id)
    total_oob = _logistics_expenses_total_el(summary.get("grand_total_usd", 0), oob=True)
    return (_finance_logistics_expenses_stage_section(deal_id, stage_id, org_id), total_oob)


# @rt("/finance/{deal_id}/logistics-expenses/{expense_id}")
def delete(session, deal_id: str, expense_id: str):
    """Delete a logistics expense record."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["finance", "logistics", "admin", "top_manager"]):
        return P("Нет доступа", style="color: #ef4444;")

    user = session["user"]
    org_id = user.get("org_id", "")

    from services.logistics_expense_service import get_expense, delete_expense, sync_plan_fact_for_stage
    from services.logistics_service import get_stages_for_deal

    # Get expense and verify org ownership (IDOR prevention)
    expense = get_expense(expense_id)
    if not expense:
        return P("Расход не найден", style="color: #ef4444;")
    if expense.organization_id != org_id:
        return P("Нет доступа", style="color: #ef4444;")

    stage_id = expense.logistics_stage_id

    # Delete the expense
    delete_expense(expense_id)

    # Sync plan-fact for this stage after deletion
    stages = get_stages_for_deal(deal_id)
    for s in stages:
        if s.id == stage_id:
            sync_plan_fact_for_stage(deal_id, stage_id, s.stage_code, org_id)
            break

    # Re-render the stage section + OOB total header update
    from services.logistics_expense_service import get_deal_logistics_summary as get_del_summary
    summary = get_del_summary(deal_id)
    total_oob = _logistics_expenses_total_el(summary.get("grand_total_usd", 0), oob=True)
    return (_finance_logistics_expenses_stage_section(deal_id, stage_id, org_id), total_oob)


def _finance_logistics_expenses_stage_section(deal_id: str, stage_id: str, org_id: str):
    """Re-render a single stage section (used after create/delete for HTMX swap)."""
    from services.logistics_service import get_stages_for_deal, STAGE_NAMES, stage_allows_expenses
    from services.logistics_expense_service import (
        get_expenses_for_stage as get_stage_expenses, EXPENSE_SUBTYPE_LABELS, get_deal_logistics_summary
    )

    # Find the stage
    stages = get_stages_for_deal(deal_id)
    target_stage = None
    for s in stages:
        if s.id == stage_id:
            target_stage = s
            break
    if not target_stage:
        return P("Этап не найден", style="color: #ef4444;")

    stage = target_stage
    stage_expenses = get_stage_expenses(stage_id)
    stage_name = STAGE_NAMES.get(stage.stage_code, stage.stage_code)
    summary = get_deal_logistics_summary(deal_id)
    stage_summary = summary.get(stage.stage_code, {})
    stage_total_usd = stage_summary.get("total_usd", 0) if isinstance(stage_summary, dict) else 0

    # Expense rows table
    expense_rows = []
    for exp in stage_expenses:
        subtype_label = EXPENSE_SUBTYPE_LABELS.get(exp.expense_subtype, exp.expense_subtype)
        amount_fmt = f"{float(exp.amount):,.2f} {exp.currency}"
        date_fmt = exp.expense_date.strftime("%d.%m.%Y") if exp.expense_date else "—"
        doc_link = ""
        if exp.document_id:
            doc_link = A(
                icon("paperclip", size=12),
                href=f"/documents/{exp.document_id}/download",
                style="color: #3b82f6; margin-left: 4px;",
                target="_blank"
            )
        expense_rows.append(
            Tr(
                Td(date_fmt, style="padding: 8px 12px; font-size: 13px; color: #374151;"),
                Td(subtype_label, style="padding: 8px 12px; font-size: 13px; color: #374151;"),
                Td(amount_fmt, style="padding: 8px 12px; font-size: 13px; font-weight: 500; text-align: right;"),
                Td(exp.description or "—", style="padding: 8px 12px; font-size: 12px; color: #64748b;"),
                Td(doc_link, style="padding: 8px 12px; text-align: center;"),
                Td(
                    Button(
                        icon("trash-2", size=12),
                        hx_delete=f"/finance/{deal_id}/logistics-expenses/{exp.id}",
                        hx_target=f"#stage-expenses-{stage.id}",
                        hx_swap="outerHTML",
                        hx_confirm="Удалить расход?",
                        style="background: none; border: none; cursor: pointer; color: #ef4444; padding: 2px 4px;"
                    ),
                    style="padding: 8px 12px; text-align: center;"
                ),
                style="border-bottom: 1px solid #f1f5f9;"
            )
        )

    expenses_table = ""
    if expense_rows:
        expenses_table = Table(
            Thead(Tr(
                Th("Дата", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: left;"),
                Th("Тип", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: left;"),
                Th("Сумма", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: right;"),
                Th("Описание", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: left;"),
                Th("Файл", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: center;"),
                Th("", style="padding: 8px 12px; background: #f8fafc;"),
            )),
            Tbody(*expense_rows),
            style="width: 100%; border-collapse: collapse;"
        )

    stage_total_display = Div(
        Span(f"Итого по этапу: ", style="font-size: 12px; color: #64748b;"),
        Span(f"${float(stage_total_usd):,.2f}", style="font-size: 14px; font-weight: 600; color: #1e293b;"),
        style="margin-bottom: 8px;"
    ) if stage_expenses else ""

    add_btn = Button(
        icon("plus", size=12),
        " Добавить расход",
        hx_get=f"/finance/{deal_id}/logistics-expenses/new-form?stage_id={stage.id}",
        hx_target=f"#expense-form-{stage.id}",
        hx_swap="innerHTML",
        style="background: #3b82f6; color: white; border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 500; cursor: pointer; display: inline-flex; align-items: center; gap: 5px;"
    )

    return Div(
        Div(
            Span(stage_name, style="font-weight: 600; font-size: 14px; color: #1e293b;"),
            add_btn,
            style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;"
        ),
        Div(id=f"expense-form-{stage.id}"),
        stage_total_display,
        expenses_table if expense_rows else P("Нет расходов", style="color: #94a3b8; font-size: 13px;"),
        id=f"stage-expenses-{stage.id}",
        style="background: white; border-radius: 10px; padding: 16px; border: 1px solid #e2e8f0; margin-bottom: 16px;"
    )


# @rt("/finance/{deal_id}/generate-currency-invoices")
def post(session, deal_id: str):
    """Generate currency invoices for a deal that has none.

    Fallback button for deals where invoice generation was missed
    (e.g., created via admin status change before the fix).
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller", "finance"]):
        return RedirectResponse("/unauthorized", status_code=303)

    user = session["user"]
    org_id = user.get("org_id", "")

    supabase = get_supabase()

    # Verify deal belongs to org
    deal_check = supabase.table("deals").select(
        "id, quote_id, organization_id"
    ).eq("id", deal_id).eq("organization_id", org_id).is_("deleted_at", None).execute()
    if not deal_check.data:
        return RedirectResponse("/deals", status_code=303)

    deal = deal_check.data[0]
    quote_id = deal.get("quote_id")

    if not quote_id:
        return RedirectResponse(f"/finance/{deal_id}?tab=currency_invoices", status_code=303)

    # Idempotency: skip if invoices already exist
    existing_ci = supabase.table("currency_invoices").select("id", count="exact").eq("deal_id", deal_id).execute()
    if existing_ci.data:
        print(f"Currency invoices already exist for deal {deal_id}, skipping generation")
        return RedirectResponse(f"/finance/{deal_id}?tab=currency_invoices", status_code=303)

    try:
        from services.currency_invoice_service import generate_currency_invoices, save_currency_invoices

        ci_items, bc_lookup = _fetch_items_with_buyer_companies(supabase, quote_id)

        # Get seller_company and quote IDN
        ci_quote_resp = supabase.table("quotes").select(
            "idn_quote, seller_companies!seller_company_id(id, name)"
        ).eq("id", quote_id).single().is_("deleted_at", None).execute()
        ci_quote_data = ci_quote_resp.data or {}
        sc = (ci_quote_data.get("seller_companies") or {})
        ci_seller_company = {"id": sc.get("id"), "name": sc.get("name"), "entity_type": "seller_company"}
        ci_quote_idn = ci_quote_data.get("idn_quote", "")

        if bc_lookup and ci_seller_company.get("id"):
            ci_contracts, ci_bank_accounts = _fetch_enrichment_data(supabase, org_id)
            ci_invoices = generate_currency_invoices(
                deal_id=str(deal_id),
                quote_idn=ci_quote_idn,
                items=ci_items,
                buyer_companies=bc_lookup,
                seller_company=ci_seller_company,
                organization_id=org_id,
                contracts=ci_contracts,
                bank_accounts=ci_bank_accounts,
            )
            if ci_invoices:
                save_currency_invoices(supabase, ci_invoices)
                print(f"Currency invoices generated (fallback): {len(ci_invoices)} for deal {deal_id}")
            else:
                print(f"No currency invoices generated (fallback) for deal {deal_id}")
        else:
            print(f"Currency invoice generation skipped (fallback): no buyer/seller company for deal {deal_id}")
    except Exception as e:
        print(f"Error generating currency invoices (fallback) for deal {deal_id}: {e}")

    return RedirectResponse(f"/finance/{deal_id}?tab=currency_invoices", status_code=303)
