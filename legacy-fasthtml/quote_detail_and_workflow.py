"""FastHTML quote-detail + workflow + procurement + chat bundle (Mega-C:
38 @rt routes across /quotes cluster + /procurement cluster + quote
chat/comments) — archived 2026-04-20 during Phase 6C-2B Mega-C.

These three logically-related areas — the main /quotes detail surface
(registry + tabbed detail view + workflow-transition actions + edit +
calculate/preview + documents + versions + exports), the /procurement
workspace cluster that gates the procurement-returns workflow, and the
quote chat/comments HTMX helpers that live on the `/quotes/{id}/chat`
tab — are all replaced by Next.js pages reading `/api/quotes/*`,
`/api/deals/*`, `/api/customs/*`, `/api/logistics/*` and related FastAPI
routers. Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→
app.kvotaflow.ru, which doesn't proxy these paths back to this Python
container. Preserved here for reference / future copy-back.

Bundle rationale (Mega-C):
    All 38 routes revolve around a single quote lifecycle — the detail
    view hosts workflow transition forms, exports, chat, documents and
    versions; /procurement shares the same quote context via
    quote_header + workflow_progress_bar helpers and its return-to-
    control form mirrors /quote-control/{quote_id}/return. Bundling all
    three areas in a single archive PR keeps the review surface coherent
    (same helpers, same models) and reduces churn versus 13a + 13b + 13c
    as three separate PRs. Total archived: ~7,456 LOC across 38 routes.

Contents (38 @rt routes + ~40 exclusive helpers, ~7,456 LOC removed
from main.py in 4 extraction ranges):

Area 1 — /quotes cluster (32 routes):
  GET    /quotes                                        — Registry with summary stage blocks + filter bar + table
  GET    /quotes/{quote_id}                             — Tabbed detail view (summary, overview, finance_*, cost_analysis, chat)
  POST   /quotes/{quote_id}/submit-procurement          — Workflow: draft → pending_procurement + sales checklist
  POST   /quotes/{quote_id}/submit-quote-control        — Workflow: pending_sales_review → pending_quote_control
  GET    /quotes/{quote_id}/return-to-control           — Return-for-revision form (sales side)
  POST   /quotes/{quote_id}/return-to-control           — Submit return-for-revision
  GET    /quotes/{quote_id}/submit-justification        — Justification form (Feature: approval justification)
  POST   /quotes/{quote_id}/submit-justification        — Submit justification
  POST   /quotes/{quote_id}/manager-decision            — Top manager approve/reject decision
  GET    /quotes/{quote_id}/approval-return             — Return-from-approval form
  POST   /quotes/{quote_id}/approval-return             — Submit approval return
  POST   /quotes/{quote_id}/send-to-client              — Workflow: approved → sent_to_client
  POST   /quotes/{quote_id}/client-change-request       — Client requested changes
  POST   /quotes/{quote_id}/submit-spec-control         — Workflow: → pending_spec_control
  POST   /quotes/{quote_id}/client-rejected             — Workflow: → rejected
  POST   /quotes/{quote_id}/approve-department          — Multi-department approval (Bug #8 follow-up)
  PATCH  /quotes/{quote_id}/items/{item_id}             — Single-item update
  POST   /quotes/{quote_id}/items/bulk                  — Bulk replace items (Handsontable save)
  PATCH  /quotes/{quote_id}/inline                      — Inline-edit single quote field
  POST   /quotes/{quote_id}/cancel                      — Workflow: → cancelled
  GET    /quotes/{quote_id}/edit                        — Edit form
  POST   /quotes/{quote_id}/edit                        — Save edits
  DELETE /quotes/{quote_id}                             — Delete quote (hard delete — legacy)
  GET    /quotes/{quote_id}/preview                     — Calculation preview HTMX panel
  GET    /quotes/{quote_id}/calculate                   — Calculation workspace
  POST   /quotes/{quote_id}/calculate                   — Submit calculation variables
  GET    /quotes/{quote_id}/documents                   — Documents tab (merged chain + currency invoices)
  GET    /quotes/{quote_id}/versions                    — Version history
  GET    /quotes/{quote_id}/versions/{version_num}      — Single version detail
  GET    /quotes/{quote_id}/export/specification        — Specification PDF download
  GET    /quotes/{quote_id}/export/invoice              — Invoice/КП PDF download
  GET    /quotes/{quote_id}/export/validation           — Validation Excel (XLSM) download

Area 2 — /procurement cluster (4 routes):
  GET    /procurement                                   — 303 redirect to /dashboard?tab=procurement
  GET    /procurement/{quote_id}/return-to-control      — Return-to-control form (procurement side)
  POST   /procurement/{quote_id}/return-to-control      — Submit return-to-control
  GET    /procurement/{quote_id}/export                 — Export procurement items to Excel (per-brand filter)

Area 3 — /quotes chat + comments (2 routes):
  GET    /quotes/{quote_id}/chat                        — Chat tab HTML
  POST   /quotes/{quote_id}/comments                    — Post comment + return rendered bubble + OOB empty-state swap

Exclusive helpers archived alongside their callers (~40 helpers):
  Area 1:
    - version_badge, _lookup_deal_for_quote, _calculate_quotes_stage_stats — /quotes registry helpers
    - _render_summary_tab, _sales_action_toolbar,
      _overview_info_subtab, _overview_products_subtab — /quotes/{id} detail helpers
    - render_preview_panel — /quotes/{id}/preview HTMX panel renderer
    - _build_document_chain, _render_document_chain_section,
      _render_currency_invoices_section — /quotes/{id}/documents helpers
  Area 2:
    - _build_sales_checklist_card — was exclusive to archived
      procurement_workspace.py (PR Phase 6C-1) detail route; post-
      archive it had zero callers in main.py, so it moves here for
      completeness (effectively dead code)
  Area 3:
    - _render_comment_bubble, _render_chat_tab — chat tab + comment POST
      response renderers

Preserved in main.py (live, consumed by other alive surfaces):
  - SUPPLIER_COUNTRY_MAPPING, COUNTRY_NAME_MAP, EU_COUNTRY_VAT_RATES,
    EU_ISO_CODES, normalize_country_to_iso, resolve_vat_zone,
    _calc_combined_duty, build_calculation_inputs — used by
    api/quotes.py (FastAPI calculate handler imports
    `build_calculation_inputs` from main) and by tests/test_design_country_codes.py
  - _format_transition_timestamp, workflow_status_badge, quote_header,
    workflow_progress_bar, workflow_transition_history, quote_detail_tabs —
    used by the preserved /quotes/{id}/cost-analysis `@app.get` handler at
    main.py:13572 + Finance tab helpers (_finance_main_tab_content,
    _finance_plan_fact_tab_content, etc.)
  - _ci_segment_badge — shared with _finance_currency_invoices_tab_content
    (preserved /finance tab content) after this archive; previously
    preserved from Phase 6C-2B-8
  - _quote_documents_section, _resolve_company_name, _ci_status_badge,
    _fetch_items_with_buyer_companies, _fetch_enrichment_data,
    _finance_fetch_deal_data, _finance_main_tab_content,
    _finance_plan_fact_tab_content, _finance_logistics_tab_content,
    _finance_currency_invoices_tab_content, _logistics_expenses_total_el,
    _finance_logistics_expenses_tab_content, _finance_payment_modal,
    _deals_logistics_tab — all consumed by /quotes/{id} finance tab
    entry points that stay alive (the GET /quotes/{id} route itself is
    archived here, but the `@app.get /quotes/{id}/cost-analysis` route
    and finance tabs entry via /api/deals/* FastAPI endpoints preserve
    consumer surface for these helpers)

Preserved service layers (all alive):
  - services/quote_version_service.py (create_quote_version,
    list_quote_versions, get_quote_version, get_current_quote_version,
    can_update_version, update_quote_version) — consumed here by
    /quotes/{id}/versions + /quotes/{id}/versions/{n}; post-archive
    still used by api/quotes.py and tests
  - services/quote_approval_service.py — * still consumed by the
    Mega-B /quote-control handlers (already archived) and stay
    alive via FastAPI migration
  - services/workflow_service.py — check_all_procurement_complete,
    complete_procurement, transition_quote_status,
    transition_to_pending_procurement, show_validation_excel,
    show_quote_pdf, show_invoice_and_spec etc. — all consumed by
    preserved /quotes/{id}/cost-analysis + finance tab surfaces
  - services/approval_service.py — count_pending_approvals consumed
    by sidebar (unchanged from Mega-B cleanup)
  - services/specification_export.py
    (generate_specification_pdf, generate_spec_pdf_from_spec_id) — used
    by archived /quotes/{id}/export/specification; service stays alive
    because post-archive it's still referenced by export helpers
  - services/invoice_export.py (generate_invoice_pdf) — used by
    archived /quotes/{id}/export/invoice; service file stays alive for
    future Next.js+FastAPI rewrites
  - services/export_validation_service.py (create_validation_excel) —
    used by archived /quotes/{id}/export/validation; service stays alive
  - services/procurement_export.py (create_procurement_excel) — used by
    archived /procurement/{id}/export; service stays alive
  - services/composition_service.py (get_composed_items,
    is_procurement_complete) — used by /quotes/{id}/calculate POST for
    multi-supplier price composition; still consumed by api/quotes.py
  - services/document_service.py — consumed by preserved
    _quote_documents_section + api/documents.py
  - services/currency_invoice_service.py,
    services/currency_service.py, services/cbr_rates_service.py —
    consumed by preserved finance tabs + calculation path
  - services/seller_company_service.py (get_all_seller_companies) —
    inline-imported inside archived /quotes/{id} GET; service stays
    alive for customers/suppliers/seller-company surfaces

NOT included (separate archive decisions):
  - /admin/* — Mega-D scope, not this PR
  - /login, /logout, /, /unauthorized — Mega-D scope, not this PR
  - @app.get /quotes/{id}/cost-analysis and /cost-analysis-json —
    preserved (use @app decorator not @rt, out of scope)
  - Preserved calc helpers (build_calculation_inputs etc.) and preserved
    workflow/finance helpers (see above)
  - Previously archived in prior Megas: customers, suppliers, companies,
    settings, profile, training, approvals, changelog, telegram,
    dashboard, tasks, currency-invoices, locations, calls, documents,
    customer-contracts, supplier-invoices, finance lifecycle, deals
    detail, finance HTMX tail, customs, logistics, quote-control,
    spec-control

Sidebar/nav entries for /quotes + /procurement left intact post-archive
— they become dead links but safe per the Caddy cutover plan (kvotaflow.ru →
app.kvotaflow.ru).

This file is NOT imported by main.py or api/app.py. Effectively dead
code preserved for reference. To resurrect a handler: copy back to
main.py, restore imports (page_layout, require_login, user_has_any_role,
get_supabase, get_effective_roles, icon, btn, btn_link, format_money,
format_date_russian, cast, json, os, uuid, Decimal, datetime/date/timedelta,
workflow_status_badge, workflow_progress_bar, quote_header,
quote_detail_tabs, workflow_transition_history, STATUS_NAMES,
WorkflowStatus, transition_quote_status, check_all_procurement_complete,
complete_procurement, transition_to_pending_procurement,
get_quote_transition_history, show_validation_excel, show_quote_pdf,
show_invoice_and_spec, normalize_country_to_iso, resolve_vat_zone,
EU_COUNTRY_VAT_RATES, COUNTRY_NAME_MAP, build_calculation_inputs,
_calc_combined_duty, _quote_documents_section, _resolve_company_name,
_ci_status_badge, _ci_segment_badge,
_fetch_items_with_buyer_companies, _fetch_enrichment_data,
get_assigned_brands, profit_color, create_procurement_excel,
build_export_filename, create_validation_excel,
generate_specification_pdf, generate_spec_pdf_from_spec_id,
generate_invoice_pdf, services.seller_company_service,
services.composition_service.get_composed_items,
services.quote_version_service.*, services.quote_approval_service.*,
services.workflow_service.*, services.currency_service.convert_amount,
services.cbr_rates_service.get_usd_rub_rate,
services.document_service.*, services.currency_invoice_service.*,
fasthtml components, starlette RedirectResponse/Response/JSONResponse),
re-apply the @rt decorator, and regenerate tests if needed. Not
recommended — rewrite via Next.js + FastAPI instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
import html as html_mod
import json
import os

from fasthtml.common import (
    A, Br, Button, Datalist, Div, Form, H1, H2, H3, H4, Hidden, I, Iframe,
    Input, Label, Li, Option, P, Script, Select, Small, Span, Strong, Style,
    Table, Tbody, Td, Textarea, Th, Thead, Tr, Ul,
)
from starlette.responses import JSONResponse, RedirectResponse


# ============================================================================
# AREA 1 — /quotes cluster (32 routes)
# ============================================================================
# Extracted from main.py lines 5026-9450 (registry + detail + workflow +
# items + edit + delete) and lines 9987-12316 (preview + calculate +
# documents + versions + exports).
# ============================================================================

# ============================================================================
# QUOTES LIST
# ============================================================================

def version_badge(quote_id, current_ver, total_count):
    """Render version badge for quotes list. Clickable if multiple versions."""
    if total_count <= 1:
        return Span(f"v{current_ver}", style="color: #94a3b8; font-size: 12px;")

    badge_style = """
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        color: #0369a1;
        border: 1px solid #bae6fd;
        text-decoration: none;
        transition: background-color 0.15s ease, color 0.15s ease;
    """
    return A(
        f"v{current_ver}",
        Span(f"({total_count})", style="opacity: 0.7; margin-left: 4px;"),
        href=f"/quotes/{quote_id}/versions",
        style=badge_style,
        title="Посмотреть историю версий",
        onclick="event.stopPropagation();"
    )


def _lookup_deal_for_quote(quote_id: str, org_id: str):
    """
    Look up the deal associated with a quote via the FK chain:
    quote_id -> specifications.quote_id -> deals.specification_id

    Returns the deal dict with nested specs/quotes if found, or None.
    """
    supabase = get_supabase()
    try:
        # First find the specification for this quote
        spec_result = supabase.table("specifications") \
            .select("id") \
            .eq("quote_id", quote_id) \
            .limit(1) \
            .is_("deleted_at", None) \
            .execute()
        if not spec_result.data:
            return None

        spec_id = spec_result.data[0]["id"]

        # Then find the deal for this specification
        deal_result = supabase.table("deals").select(
            # FK hints resolve ambiguity: !specifications(deals_specification_id_fkey), !quotes(deals_quote_id_fkey)
            "id, deal_number, signed_at, total_amount, currency, status, created_at, "
            "specifications!deals_specification_id_fkey(id, specification_number, proposal_idn, sign_date, validity_period, "
            "  specification_currency, exchange_rate_to_ruble, client_payment_terms, "
            "  our_legal_entity, client_legal_entity), "
            "quotes!deals_quote_id_fkey(id, idn_quote, customers(name))"
        ).eq("specification_id", spec_id).eq("organization_id", org_id).limit(1).is_("deleted_at", None).execute()

        if deal_result.data:
            return deal_result.data[0]
        return None
    except Exception as e:
        print(f"Error looking up deal for quote {quote_id}: {e}")
        return None


def _calculate_quotes_stage_stats(quotes: list) -> dict:
    """
    Group quotes by workflow_status stage and calculate count + total sum per stage.
    Returns dict keyed by stage group with {count, sum, label, icon_name, color} values.

    All workflow statuses are mapped to logical groups so no quotes are silently dropped:
      - draft
      - pending_procurement
      - logistics: pending_logistics, pending_customs, pending_logistics_and_customs
      - control: pending_quote_control, pending_sales_review, pending_approval
      - pending_spec_control
      - client: sent_to_client, client_negotiation, pending_signature
      - approved
      - deal
      - closed: rejected, cancelled
    """
    stage_groups = {
        "draft": {
            "statuses": ["draft"],
            "label": "Черновик", "icon_name": "file-edit",
            "color": "#6b7280", "bg": "#f3f4f6", "border": "#d1d5db",
        },
        "pending_procurement": {
            "statuses": ["pending_procurement"],
            "label": "Закупки", "icon_name": "shopping-cart",
            "color": "#d97706", "bg": "#fffbeb", "border": "#fcd34d",
        },
        "logistics": {
            "statuses": ["pending_logistics", "pending_customs", "pending_logistics_and_customs"],
            "label": "Лог+Там", "icon_name": "truck",
            "color": "#2563eb", "bg": "#eff6ff", "border": "#93c5fd",
        },
        "control": {
            "statuses": ["pending_quote_control", "pending_sales_review", "pending_approval"],
            "label": "Контроль", "icon_name": "clipboard-check",
            "color": "#ea580c", "bg": "#fff7ed", "border": "#fdba74",
        },
        "pending_spec_control": {
            "statuses": ["pending_spec_control"],
            "label": "Проверка", "icon_name": "search",
            "color": "#0891b2", "bg": "#ecfeff", "border": "#67e8f9",
        },
        "client": {
            "statuses": ["sent_to_client", "client_negotiation", "pending_signature"],
            "label": "Клиент", "icon_name": "send",
            "color": "#0d9488", "bg": "#f0fdfa", "border": "#99f6e4",
        },
        "approved": {
            "statuses": ["approved"],
            "label": "Согласован", "icon_name": "check-circle",
            "color": "#059669", "bg": "#ecfdf5", "border": "#6ee7b7",
        },
        "deal": {
            "statuses": ["deal"],
            "label": "Сделка", "icon_name": "briefcase",
            "color": "#16a34a", "bg": "#f0fdf4", "border": "#86efac",
        },
        "closed": {
            "statuses": ["rejected", "cancelled"],
            "label": "Закрыт", "icon_name": "x-circle",
            "color": "#dc2626", "bg": "#fef2f2", "border": "#fecaca",
        },
    }
    stats = {}
    for group_key, cfg in stage_groups.items():
        matched_statuses = set(cfg["statuses"])
        group_quotes = [q for q in quotes if q.get("workflow_status") in matched_statuses]
        total_sum = sum(float(q.get("total_amount") or 0) for q in group_quotes)
        stats[group_key] = {
            "count": len(group_quotes),
            "sum": total_sum,
            "label": cfg["label"],
            "icon_name": cfg["icon_name"],
            "color": cfg["color"],
            "bg": cfg["bg"],
            "border": cfg["border"],
        }
    return stats


# @rt("/quotes")
def get(session, status: str = "", customer_id: str = "", manager_id: str = ""):
    """
    Quotes List page — redesigned with summary stage blocks and compact table.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = get_effective_roles(session)
    # is_sales_only: user has sales role but NOT admin/top_manager/head_of_sales (full visibility)
    has_sales_role = any(r in roles for r in ["sales", "sales_manager"])
    has_full_visibility = any(r in roles for r in ["admin", "top_manager", "head_of_sales"])
    is_sales_only = has_sales_role and not has_full_visibility

    supabase = get_supabase()

    _select = "id, idn_quote, customer_id, customers!customer_id(name, id), workflow_status, total_amount, total_profit_usd, currency, created_at, created_by, quote_versions!quote_versions_quote_id_fkey(version)"

    if is_sales_only:
        # Sales users see quotes for their assigned customers only
        my_customers = supabase.table("customers") \
            .select("id") \
            .eq("organization_id", user["org_id"]) \
            .eq("manager_id", user["id"]) \
            .execute()
        my_customer_ids = [c["id"] for c in (my_customers.data or [])]

        if my_customer_ids:
            result = supabase.table("quotes") \
                .select(_select) \
                .eq("organization_id", user["org_id"]) \
                .in_("customer_id", my_customer_ids) \
                .is_("deleted_at", None) \
                .order("created_at", desc=True) \
                .execute()
        else:
            result = type('Result', (), {'data': []})()
    else:
        result = supabase.table("quotes") \
            .select(_select) \
            .eq("organization_id", user["org_id"]) \
            .is_("deleted_at", None) \
            .order("created_at", desc=True) \
            .execute()

    quotes = result.data or []

    # Process version data for each quote
    for q in quotes:
        versions = q.get("quote_versions") or []
        q["version_count"] = len(versions)
        q["current_version"] = max([v.get("version", 1) for v in versions]) if versions else 1

    # Calculate stage stats for summary blocks (uses UNFILTERED quotes)
    stage_stats = _calculate_quotes_stage_stats(quotes)

    # --- Fetch dropdown data for filters ---
    # Customers list for filter dropdown (sales users see only their assigned customers)
    try:
        cust_query = supabase.table("customers") \
            .select("id, name") \
            .eq("organization_id", user["org_id"])
        if is_sales_only:
            cust_query = cust_query.eq("manager_id", user["id"])
        customers_list = cust_query.order("name").execute().data or []
    except Exception:
        customers_list = []

    # Manager names from distinct created_by values in quotes (for filter + table column)
    managers = []
    creator_ids = list(set(q.get("created_by") for q in quotes if q.get("created_by")))
    manager_names = {}
    if creator_ids:
        try:
            profiles_result = supabase.table("profiles") \
                .select("id, full_name") \
                .in_("id", creator_ids) \
                .order("full_name") \
                .execute()
            managers = profiles_result.data or []
            manager_names = {m["id"]: m.get("full_name", "—") for m in managers}
        except Exception:
            managers = []

    # --- Python-side filtering ---
    filtered_quotes = list(quotes)
    if status:
        filtered_quotes = [q for q in filtered_quotes if q.get("workflow_status") == status]
    if customer_id:
        filtered_quotes = [q for q in filtered_quotes if q.get("customer_id") == customer_id]
    if manager_id:
        filtered_quotes = [q for q in filtered_quotes if q.get("created_by") == manager_id]

    # --- Build filter bar ---
    any_filter_active = bool(status or customer_id or manager_id)

    status_options = [
        Option("Все статусы", value="", selected=(status == "")),
        Option("Черновик", value="draft", selected=(status == "draft")),
        Option("Закупки", value="pending_procurement", selected=(status == "pending_procurement")),
        Option("Логистика", value="pending_logistics", selected=(status == "pending_logistics")),
        Option("Таможня", value="pending_customs", selected=(status == "pending_customs")),
        Option("Контроль КП", value="pending_quote_control", selected=(status == "pending_quote_control")),
        Option("Контроль спец.", value="pending_spec_control", selected=(status == "pending_spec_control")),
        Option("Ревизия", value="pending_sales_review", selected=(status == "pending_sales_review")),
        Option("Согласование", value="pending_approval", selected=(status == "pending_approval")),
        Option("Одобрено", value="approved", selected=(status == "approved")),
        Option("Отправлено", value="sent_to_client", selected=(status == "sent_to_client")),
        Option("Сделка", value="deal", selected=(status == "deal")),
        Option("Отклонено", value="rejected", selected=(status == "rejected")),
        Option("Отменено", value="cancelled", selected=(status == "cancelled")),
    ]

    customer_options = [Option("Все клиенты", value="")]
    for c in customers_list:
        customer_options.append(
            Option(c.get("name", "—"), value=c.get("id", ""), selected=(customer_id == c.get("id", "")))
        )

    manager_select = None
    if not is_sales_only:
        manager_opts = [Option("Все менеджеры", value="", selected=(manager_id == ""))]
        for m in managers:
            manager_opts.append(
                Option(m.get("full_name", "—"), value=m.get("id", ""), selected=(manager_id == m.get("id", "")))
            )
        manager_select = Select(
            *manager_opts,
            name="manager_id",
            style="padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white; flex: 1; min-width: 120px; max-width: 250px;",
            onchange="this.form.submit()",
        )

    reset_link = None
    if any_filter_active:
        reset_link = A(
            "Сбросить",
            href="/quotes",
            style="display: inline-flex; align-items: center; padding: 6px 10px; font-size: 12px; color: #64748b; text-decoration: none; border: 1px solid #e2e8f0; border-radius: 6px; background: white; white-space: nowrap;",
        )

    _filter_select_style = "padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white; flex: 1; min-width: 120px; max-width: 250px;"
    filter_bar = Form(
        Select(
            *status_options,
            name="status",
            style=_filter_select_style,
            onchange="this.form.submit()",
        ),
        Select(
            *customer_options,
            name="customer_id",
            style=_filter_select_style,
            onchange="this.form.submit()",
        ),
        manager_select,
        reset_link,
        method="get",
        action="/quotes",
        style="display: flex; flex-wrap: nowrap; gap: 8px; padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; align-items: center;",
    )

    # -- Styles --
    header_card_style = (
        "background: #fafbfc;"
        "border-radius: 12px; border: 1px solid #e2e8f0;"
        "padding: 16px 24px; margin-bottom: 16px;"
        "display: flex; justify-content: space-between; align-items: center;"
        "flex-wrap: wrap; gap: 12px;"
    )
    page_title_style = (
        "display: flex; align-items: center; gap: 12px;"
        "margin: 0; font-size: 20px; font-weight: 700;"
        "color: #1e293b; letter-spacing: -0.02em;"
    )
    count_badge_style = (
        "display: inline-flex; align-items: center;"
        "padding: 3px 10px; border-radius: 9999px;"
        "font-size: 12px; font-weight: 600;"
        "background: #dbeafe;"
        "color: #1e40af; border: 1px solid #bfdbfe;"
    )
    new_btn_style = (
        "display: inline-flex; align-items: center; gap: 8px;"
        "padding: 8px 16px; font-size: 13px; font-weight: 600;"
        "color: white; background: #3b82f6;"
        "border: none; border-radius: 8px; text-decoration: none;"
    )

    # Build summary stage cards
    stage_card_style_tpl = (
        "display: flex; flex-direction: column; align-items: center; gap: 2px;"
        "padding: 10px 6px; border-radius: 10px; min-width: 80px; flex: 1;"
        "border: 1px solid {border}; background: {bg};"
        "transition: transform 0.15s ease, box-shadow 0.15s ease; cursor: default;"
    )
    stage_cards = []
    for stage_key in ["draft", "pending_procurement", "logistics", "control", "pending_spec_control", "client", "approved", "deal", "closed"]:
        s = stage_stats[stage_key]
        card_style = stage_card_style_tpl.format(border=s["border"], bg=s["bg"])
        stage_cards.append(
            Div(
                Div(
                    icon(s["icon_name"], size=16, style=f"color: {s['color']};"),
                    Span(s["label"], style=f"font-size: 11px; font-weight: 600; color: {s['color']}; text-transform: uppercase; letter-spacing: 0.03em;"),
                    style="display: flex; align-items: center; gap: 4px;"
                ),
                Div(str(s["count"]), style=f"font-size: 22px; font-weight: 700; color: {s['color']}; line-height: 1.2;"),
                Div(
                    format_money(s["sum"]) if s["sum"] else "—",
                    style="font-size: 11px; color: #64748b; font-weight: 500;"
                ),
                style=card_style,
            )
        )

    summary_grid = Div(
        *stage_cards,
        style="display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; margin-bottom: 16px;",
    )

    # Build table rows (uses filtered_quotes for display)
    table_rows = []
    for q in filtered_quotes:
        customer_name = (q.get("customers") or {}).get("name", "—")
        cust_id = (q.get("customers") or {}).get("id")
        created_date = format_date_russian(q.get("created_at")) if q.get("created_at") else "—"
        idn_label = q.get("idn_quote", f"#{q['id'][:8]}")
        quote_currency = q.get("currency", "RUB")

        customer_cell = (
            A(customer_name, href=f"/customers/{cust_id}",
              style="color: #1e293b; text-decoration: none; font-weight: 500;",
              onclick="event.stopPropagation();")
            if cust_id else Span(customer_name, style="color: #94a3b8;")
        )

        manager_name = manager_names.get(q.get("created_by"), "—")

        _cell = "padding: 8px 12px; font-size: 13px;"
        table_rows.append(Tr(
            Td(created_date, style=f"{_cell} color: #64748b; white-space: nowrap;"),
            Td(
                A(idn_label, href=f"/quotes/{q['id']}",
                  style="font-weight: 600; color: #3b82f6; text-decoration: none;",
                  onclick="event.stopPropagation();"),
                style=_cell
            ),
            Td(customer_cell, style=_cell),
            Td(manager_name, style=f"{_cell} color: #374151;"),
            Td(workflow_status_badge(q.get("workflow_status", "draft")), style=_cell),
            Td(version_badge(q['id'], q.get('current_version', 1), q.get('version_count', 1)),
               style=f"{_cell} text-align: center;"),
            Td(format_money(q.get("total_amount"), quote_currency), cls="col-money",
               style=_cell),
            Td(format_money(q.get("total_profit_usd"), "USD"), cls="col-money",
               style=f"{_cell} color: {profit_color(q.get('total_profit_usd'))}; font-weight: 500;"),
            cls="clickable-row",
            onclick=f"window.location='/quotes/{q['id']}'"
        ))

    return page_layout("Коммерческие предложения",
        # Header card with title and actions
        Div(
            Div(
                icon("file-text", size=22, style="color: #3b82f6;"),
                H1("Коммерческие предложения", style=page_title_style),
                Span(f"{len(filtered_quotes)}", style=count_badge_style),
                style="display: flex; align-items: center; gap: 12px;"
            ),
            Div(
                A(
                    icon("plus", size=14),
                    Span("Новое КП"),
                    href="/quotes/new",
                    style=new_btn_style,
                    cls="btn",
                ),
            ),
            style=header_card_style
        ),

        # Summary stage blocks
        summary_grid,

        # Filter bar
        filter_bar,

        # Table content with compact styling
        Div(
            Div(
                Table(
                    Thead(Tr(
                        Th("Дата", style="padding: 10px 12px;"),
                        Th("IDN", style="padding: 10px 12px;"),
                        Th("Клиент", style="padding: 10px 12px;"),
                        Th("Менеджер", style="padding: 10px 12px;"),
                        Th("Статус", style="padding: 10px 12px;"),
                        Th("Версии", style="text-align: center; width: 70px; padding: 10px 12px;"),
                        Th("Сумма", cls="col-money", style="padding: 10px 12px;"),
                        Th("Профит", cls="col-money", style="padding: 10px 12px;"),
                    )),
                    Tbody(
                        *table_rows
                    ) if filtered_quotes else Tbody(Tr(Td(
                        Div(
                            icon("file-text", size=28, style="color: #94a3b8; margin-bottom: 8px;"),
                            Div("Нет коммерческих предложений", style="font-size: 14px; font-weight: 500; color: #64748b; margin-bottom: 6px;"),
                            Div("Создайте первое КП для начала работы", style="font-size: 12px; color: #94a3b8; margin-bottom: 12px;"),
                            A(
                                icon("plus", size=14),
                                Span("Создать первое КП"),
                                href="/quotes/new",
                                style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; color: #3b82f6; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; text-decoration: none;",
                                cls="btn",
                            ),
                            style="text-align: center; padding: 32px 24px;"
                        ),
                        colspan="8"
                    ))),
                    cls="table-enhanced"
                ),
                cls="table-enhanced-container"
            ),
            cls="table-responsive"
        ),

        # Table footer with count
        Div(
            Span(f"Всего: {len(filtered_quotes)} КП", style="font-size: 12px; color: #64748b;"),
            cls="table-footer"
        ) if filtered_quotes else None,

        session=session,
        current_path="/quotes"
    )





# ============================================================================
# QUOTE DETAIL
# ============================================================================


def _render_summary_tab(quote, customer, seller_companies, contacts, items, creator_name,
                        created_at_display, expiry_display,
                        quote_controller_name=None, spec_controller_name=None,
                        customs_user_name=None, logistics_user_name=None,
                        rate_on_quote_date=None, rate_on_spec_date=None):
    """Render read-only summary tab with 6-block layout (3 rows x 2 columns).

    LEFT column:  Block I (Основная), Block II (Дополнительная), Block III (Печать)
    RIGHT column: Block IV (Расчеты), Block V (Доставка), Block VI (Итого)
    Row pairing: [I+IV], [II+V], [III+VI]
    """

    # Lookup seller company object
    seller_company = None
    if quote.get("seller_company_id"):
        seller_company = next(
            (sc for sc in seller_companies if str(sc.id) == str(quote.get("seller_company_id", ""))),
            None
        )

    # Lookup contact person
    contact_person = None
    if quote.get("contact_person_id") and contacts:
        contact_person = next(
            (c for c in contacts if c.get("id") == quote.get("contact_person_id")),
            None
        )

    # Delivery method label
    delivery_method_map = {"air": "Авиа", "auto": "Авто", "sea": "Море", "multimodal": "Мультимодально"}
    delivery_method_label = delivery_method_map.get(quote.get("delivery_method") or "", "—")

    # Currency info
    currency = quote.get("currency") or "RUB"
    currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥", "TRY": "₺"}
    currency_symbol = currency_symbols.get(currency, currency)

    # Totals (prefer quote-currency columns, fallback to total_amount)
    total_with_vat = float(quote.get("total_quote_currency") or quote.get("total_amount") or 0)
    total_no_vat = float(quote.get("revenue_no_vat_quote_currency") or 0)
    total_profit = float(quote.get("profit_quote_currency") or 0)
    total_cogs = float(quote.get("cogs_quote_currency") or 0)

    # Fallback for old quotes without revenue_no_vat: derive from total / (1 + tax_rate%)
    if total_no_vat == 0 and total_with_vat > 0:
        tax_rate = float(quote.get("tax_rate") or 20)
        total_no_vat = total_with_vat / (1 + tax_rate / 100)
    # Fallback for old quotes without cogs: cogs = revenue_no_vat - profit
    if total_cogs == 0 and total_no_vat > 0 and total_profit > 0:
        total_cogs = total_no_vat - total_profit

    # Margin = profit / revenue (excl. VAT), Markup = profit / COGS
    margin_pct = (total_profit / total_no_vat) * 100 if total_no_vat > 0 else 0
    markup_pct = (total_profit / total_cogs) * 100 if total_cogs > 0 else 0

    # Payment terms
    payment_terms = quote.get("payment_terms") or "—"
    advance_percent = quote.get("advance_percent") or 0

    # Common styles
    label_style = "color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"
    value_style = "color: #374151; margin-top: 0.25rem; font-size: 0.875rem;"
    card_style = "background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb; flex: 1;"
    header_style = "display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
    header_text_style = "font-size: 0.75rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"
    grid_2col = "display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;"

    def _field(label_text, value_text, full_width=False):
        """Helper to render a single read-only field."""
        extra_style = "grid-column: 1 / -1;" if full_width else ""
        return Div(
            Div(label_text, style=label_style),
            Div(str(value_text) if value_text else "—", style=value_style),
            style=extra_style
        )

    def _card_header(icon_name, title):
        """Helper to render a card header with icon."""
        return Div(
            icon(icon_name, size=14, color="#6b7280"),
            Span(f" {title}", style=header_text_style),
            style=header_style
        )

    # --- Action buttons row ---
    # Download button only available after quote controller approval
    _download_allowed_statuses = {"pending_approval", "approved", "sent_to_client", "client_negotiation", "pending_spec_control", "deal"}
    _current_wf_status = quote.get("workflow_status") or quote.get("status", "draft")
    _download_btn = btn("Скачать", variant="secondary", icon_name="download",
        onclick=f"location.href='/quotes/{quote.get('id')}/export/specification'") if _current_wf_status in _download_allowed_statuses else None
    # Download button moved to bottom of summary (after all blocks)
    download_row = Div(
        _download_btn,
        style="display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.5rem;"
    ) if _download_btn else None

    # --- Block I: Main info (customer/seller + contact phone) ---
    customer_name = (customer or {}).get("name", "—") or "—"
    customer_inn = (customer or {}).get("inn", "—") or "—"
    seller_name = seller_company.name if seller_company else "—"
    seller_inn = getattr(seller_company, "inn", None) or "—" if seller_company else "—"
    contact_name = (contact_person or {}).get("name", "—") if contact_person else "—"
    contact_phone = (contact_person or {}).get("phone", "—") if contact_person else "—"

    # Customer name as clickable link if customer exists
    customer_display = A(
        customer_name,
        href=f"/customers/{quote.get('customer_id')}",
        style="color: #3b82f6; text-decoration: none; font-weight: 500;"
    ) if quote.get("customer_id") and customer_name != "—" else Span("—", style="color: #9ca3af;")

    card_1 = Div(
        _card_header("info", "ОСНОВНАЯ ИНФОРМАЦИЯ"),
        Div(
            Div(
                Div("Клиент", style=label_style),
                Div(customer_display, style="margin-top: 0.25rem;"),
            ),
            _field("ИНН клиента", customer_inn),
            _field("Организация продавец", seller_name),
            _field("ИНН продавца", seller_inn),
            _field("Контактное лицо", contact_name),
            _field("Телефон", contact_phone),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block IV: ПОРЯДОК РАСЧЕТОВ (exchange rates + payment terms) ---
    has_advance = advance_percent and float(advance_percent) > 0
    advance_display = f"{advance_percent}%" if has_advance else "—"

    # Format exchange rates for display
    def _format_rate(rate):
        if rate is None:
            return "—"
        return f"{rate:.4f} \u20bd"

    rate_kp_display = _format_rate(rate_on_quote_date)
    rate_sp_display = _format_rate(rate_on_spec_date)

    card_4 = Div(
        _card_header("credit-card", "ПОРЯДОК РАСЧЕТОВ"),
        Div(
            _field("Условия расчетов", payment_terms),
            _field("Частичная предоплата", "Да" if has_advance else "Нет"),
            _field("Размер аванса", advance_display),
            _field("Валюта КП", currency),
            _field("Курс USD/RUB на дату КП", rate_kp_display),
            _field("Курс USD/RUB на дату СП", rate_sp_display),
            _field("Курс USD/RUB на дату УПД", "—"),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block II: ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (5 workflow actors + dates) ---
    # Format completion dates
    def _format_date(date_str):
        if not date_str:
            return "—"
        try:
            dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return "—"

    quote_control_date = _format_date(quote.get("quote_control_completed_at"))
    spec_control_date = _format_date(quote.get("spec_control_completed_at"))
    customs_date = _format_date(quote.get("customs_completed_at"))
    logistics_date = _format_date(quote.get("logistics_completed_at"))

    card_2 = Div(
        _card_header("users", "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ"),
        Div(
            _field("Создатель", creator_name or "—"),
            _field("Дата создания", created_at_display),
            _field("Контролер КП", quote_controller_name or "—"),
            _field("Дата проверки КП", quote_control_date),
            _field("Контролер СП", spec_controller_name or "—"),
            _field("Дата проверки СП", spec_control_date),
            _field("Таможенный менеджер", customs_user_name or "—"),
            _field("Дата таможни", customs_date),
            _field("Логистический менеджер", logistics_user_name or "—"),
            _field("Дата логистики", logistics_date),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block V: ДОСТАВКА ---
    card_5 = Div(
        _card_header("truck", "ДОСТАВКА"),
        Div(
            _field("Тип сделки", delivery_method_label),
            _field("Базис поставки", quote.get("delivery_terms") or "—"),
            _field("Страна поставки", quote.get("delivery_country") or "—"),
            _field("Город доставки", quote.get("delivery_city") or "—"),
            _field("Адрес поставки", quote.get("delivery_address") or "—", full_width=True),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block III: ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ ---
    card_3 = Div(
        _card_header("printer", "ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ"),
        Div(
            _field("Дата выставления КП", created_at_display),
            _field("Срок действия КП", expiry_display),
            _field("Срок действия (дней)", str(quote.get("validity_days") or 30)),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block VI: ИТОГО (3-column grid: total, profit, count, margin, markup) ---
    total_amount_display = f"{total_with_vat:,.2f} {currency_symbol}" if total_with_vat else "—"
    total_profit_display = f"{total_profit:,.2f} {currency_symbol}" if total_profit is not None else "—"
    items_count = len(items)
    margin_display = f"{margin_pct:.1f}%"
    markup_display = f"{markup_pct:.1f}%" if total_cogs > 0 else "—"

    _itogo_big = "font-weight: 600; font-size: 1.25rem; margin-top: 0.25rem;"
    card_6 = Div(
        _card_header("dollar-sign", "ИТОГО"),
        Div(
            Div(
                Div("Сумма с НДС", style=label_style),
                Div(total_amount_display, style=f"color: #374151; {_itogo_big}"),
            ),
            Div(
                Div(f"Профит ({currency})", style=label_style),
                Div(total_profit_display,
                    style=f"color: {'#10b981' if total_profit > 0 else '#ef4444' if total_profit < 0 else '#374151'}; {_itogo_big}"),
            ),
            Div(
                Div("Позиции", style=label_style),
                Div(f"{items_count} шт", style=value_style),
            ),
            Div(
                Div("Маржа (профит ÷ выручка без НДС)", style=label_style),
                Div(margin_display,
                    style=f"color: {'#10b981' if margin_pct > 0 else '#374151'}; {_itogo_big}"),
            ),
            Div(
                Div("Наценка (профит ÷ себестоимость)", style=label_style),
                Div(markup_display,
                    style=f"color: {'#10b981' if markup_pct > 0 else '#374151'}; {_itogo_big}"),
            ),
            style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem;"
        ),
        cls="card",
        style=card_style
    )

    # --- Layout: 3 rows x 2 columns ---
    # Row 1: Block I (Основная) + Block IV (Расчеты)
    # Row 2: Block II (Дополнительная) + Block V (Доставка)
    # Row 3: Block III (Печать) + Block VI (Итого)
    return Div(
        # Row 1: Block I + Block IV
        Div(card_1, card_4, style="display: flex; gap: 1rem; margin-bottom: 1rem;"),
        # Row 2: Block II + Block V
        Div(card_2, card_5, style="display: flex; gap: 1rem; margin-bottom: 1rem;"),
        # Row 3: Block III + Block VI
        Div(card_3, card_6, style="display: flex; gap: 1rem; margin-bottom: 1rem;"),
        download_row,
        id="tab-content",
        style="margin-top: 20px;"
    )




def _sales_action_toolbar(quote_id, workflow_status, is_revision, is_justification_needed):
    """Persistent action toolbar shown on BOTH Обзор and Позиции sub-tabs.
    Visually distinct from tab pills: thin bar with sm-sized outline buttons,
    light gray background, top/bottom border separating it from content.
    """
    left_buttons = Div(
        btn_link("Рассчитать", href=f"/quotes/{quote_id}/calculate", variant="secondary", icon_name="calculator", size="sm"),
        btn_link("История версий", href=f"/quotes/{quote_id}/versions", variant="secondary", icon_name="history", size="sm"),
        btn_link("Валидация Excel", href=f"/quotes/{quote_id}/export/validation", variant="secondary", icon_name="table", size="sm") if show_validation_excel(workflow_status) else None,
        btn_link("КП PDF", href=f"/quotes/{quote_id}/export/invoice", variant="secondary", icon_name="file-text", size="sm") if show_quote_pdf(workflow_status) else None,
        btn_link("Счёт PDF", href=f"/quotes/{quote_id}/export/invoice", variant="secondary", icon_name="file-text", size="sm") if show_invoice_and_spec(workflow_status) else None,
        style="display: flex; gap: 0.375rem; flex-wrap: wrap; align-items: center;"
    )
    right_buttons = Div(
        (Form(
            btn("Отправить на контроль", variant="secondary", icon_name="send", type="submit", size="sm"),
            method="post",
            action=f"/quotes/{quote_id}/submit-quote-control",
            style="display: inline;"
        ) if workflow_status == "pending_sales_review" and not is_revision and not is_justification_needed else None),
        btn("Удалить КП", variant="danger", icon_name="trash-2", size="sm",
            id="btn-delete-quote", onclick="showDeleteModal()"),
        style="display: flex; gap: 0.375rem; align-items: center;"
    )
    return Div(
        Div(left_buttons, right_buttons,
            style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;"),
        style=(
            "background: #f8fafc; "
            "border-top: 1px solid #e5e7eb; "
            "border-bottom: 1px solid #e5e7eb; "
            "padding: 0.5rem 0; "
            "margin-bottom: 1rem;"
        )
    )


def _overview_info_subtab(quote, quote_id, customer, customers, seller_companies, contacts,
                          creator_name, created_at_display, expiry_display, is_expired,
                          delivery_terms_options, delivery_method_options,
                          _itogo_total_display, _itogo_profit_display, _itogo_profit_color,
                          _itogo_items_count, _itogo_margin_display, _itogo_margin_color):
    """Render the info sub-tab: ОСНОВНАЯ ИНФОРМАЦИЯ block (full-width, 2-col grid),
    2-column layout with ДОСТАВКА (left) + ИТОГО (right).
    Uses display: grid with grid-template-columns: 1fr 1fr for the bottom row."""
    pass


def _overview_products_subtab(quote, quote_id, items, items_json, workflow_status,
                              is_revision, is_justification_needed, logistics_total,
                              approval_status, session, revision_comment, approval_reason,
                              delivery_terms_options, delivery_method_options,
                              user_has_any_role_fn, user_can_approve_fn):
    """Render the products sub-tab with unified action card.
    Contains: Рассчитать button, История версий, Валидация Excel, КП PDF, Счёт PDF,
    Удалить КП danger button, Отправить на контроль button.
    Includes id="items-spreadsheet" Handsontable container and workflow_transition_history."""
    pass


# @rt("/quotes/{quote_id}")
def get(quote_id: str, session, tab: str = "summary", subtab: str = "info"):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    # Respect role impersonation for tab visibility and access control
    impersonated_role = session.get("impersonated_role")
    effective_roles = [impersonated_role] if impersonated_role else user.get("roles", [])
    supabase = get_supabase()

    # Get quote with customer
    result = supabase.table("quotes") \
        .select("*, customers(name, inn, email)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not result.data:
        return page_layout("Не найдено",
            H1("КП не найден"),
            A("← Назад к списку КП", href="/quotes"),
            session=session
        )

    quote = result.data[0]
    customer = quote.get("customers", {})

    # Get customers for dropdown (for inline editing)
    customers_result = supabase.table("customers") \
        .select("id, name, inn") \
        .eq("organization_id", user["org_id"]) \
        .order("name") \
        .execute()
    customers = customers_result.data or []

    # Get seller companies for dropdown
    from services.seller_company_service import get_all_seller_companies
    seller_companies = get_all_seller_companies(organization_id=user["org_id"], is_active=True)

    # Get customer contacts for contact person dropdown
    contacts = []
    if quote.get("customer_id"):
        try:
            contacts_result = supabase.table("customer_contacts") \
                .select("id, name, position, phone, is_lpr") \
                .eq("customer_id", quote["customer_id"]) \
                .order("is_lpr", desc=True) \
                .order("name") \
                .execute()
            contacts = contacts_result.data or []
        except Exception:
            pass

    # Look up creator name from user_profiles
    creator_name = None
    if quote.get("created_by"):
        try:
            creator_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["created_by"]) \
                .limit(1) \
                .execute()
            if creator_result.data and creator_result.data[0].get("full_name"):
                creator_name = creator_result.data[0]["full_name"]
        except Exception:
            pass

    # Look up workflow actor names from user_profiles (quote_controller, spec_controller, customs, logistics)
    quote_controller_name = None
    if quote.get("quote_controller_id"):
        try:
            qc_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["quote_controller_id"]) \
                .limit(1) \
                .execute()
            if qc_result.data and qc_result.data[0].get("full_name"):
                quote_controller_name = qc_result.data[0]["full_name"]
        except Exception:
            pass

    spec_controller_name = None
    if quote.get("spec_controller_id"):
        try:
            sc_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["spec_controller_id"]) \
                .limit(1) \
                .execute()
            if sc_result.data and sc_result.data[0].get("full_name"):
                spec_controller_name = sc_result.data[0]["full_name"]
        except Exception:
            pass

    customs_user_name = None
    if quote.get("assigned_customs_user"):
        try:
            cu_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["assigned_customs_user"]) \
                .limit(1) \
                .execute()
            if cu_result.data and cu_result.data[0].get("full_name"):
                customs_user_name = cu_result.data[0]["full_name"]
        except Exception:
            pass

    logistics_user_name = None
    if quote.get("assigned_logistics_user"):
        try:
            lu_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["assigned_logistics_user"]) \
                .limit(1) \
                .execute()
            if lu_result.data and lu_result.data[0].get("full_name"):
                logistics_user_name = lu_result.data[0]["full_name"]
        except Exception:
            pass

    # Get quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    items = items_result.data or []

    # Calculate logistics_total from invoices (logistics cost segments)
    # The quotes table does NOT have a logistics_total column — it must be computed
    # by summing logistics_supplier_to_hub + logistics_hub_to_customs + logistics_customs_to_customer
    # from the invoices table, converting each segment to the quote currency.
    logistics_total = 0.0
    try:
        from services.currency_service import convert_amount
        from decimal import Decimal as _Decimal
        _logistics_inv_result = supabase.table("invoices") \
            .select("logistics_supplier_to_hub, logistics_hub_to_customs, logistics_customs_to_customer, logistics_supplier_to_hub_currency, logistics_hub_to_customs_currency, logistics_customs_to_customer_currency") \
            .eq("quote_id", quote_id) \
            .execute()
        _logistics_invoices = _logistics_inv_result.data or []
        _quote_currency = quote.get("currency") or "RUB"
        _logistics_total_dec = _Decimal(0)
        for _linv in _logistics_invoices:
            _s2h = _Decimal(str(_linv.get("logistics_supplier_to_hub") or 0))
            _s2h_cur = _linv.get("logistics_supplier_to_hub_currency") or "USD"
            _h2c = _Decimal(str(_linv.get("logistics_hub_to_customs") or 0))
            _h2c_cur = _linv.get("logistics_hub_to_customs_currency") or "USD"
            _c2c = _Decimal(str(_linv.get("logistics_customs_to_customer") or 0))
            _c2c_cur = _linv.get("logistics_customs_to_customer_currency") or "USD"
            if _s2h > 0:
                _logistics_total_dec += convert_amount(_s2h, _s2h_cur, _quote_currency)
            if _h2c > 0:
                _logistics_total_dec += convert_amount(_h2c, _h2c_cur, _quote_currency)
            if _c2c > 0:
                _logistics_total_dec += convert_amount(_c2c, _c2c_cur, _quote_currency)
        logistics_total = float(_logistics_total_dec)
    except Exception:
        logistics_total = 0.0

    # Prepare items data for Handsontable (JSON)
    items_for_handsontable = [
        {
            'id': item.get('id'),
            'row_num': idx + 1,
            'brand': item.get('brand', ''),
            'product_code': item.get('product_code', ''),
            'product_name': item.get('product_name', ''),
            'quantity': item.get('quantity', 1),
            'unit': item.get('unit', 'шт')
        } for idx, item in enumerate(items)
    ]
    items_json = json.dumps(items_for_handsontable)

    workflow_status = quote.get("workflow_status") or quote.get("status", "draft")

    # Check for revision status (returned from quote control)
    revision_department = quote.get("revision_department")
    revision_comment = quote.get("revision_comment")
    is_revision = revision_department == "sales" and workflow_status == "pending_sales_review"

    # Check for justification status (Feature: approval justification workflow)
    needs_justification = quote.get("needs_justification", False)
    approval_reason = quote.get("approval_reason")
    is_justification_needed = needs_justification and workflow_status == "pending_sales_review"

    # Get approval status for multi-department workflow (Bug #8 follow-up)
    approval_status = get_quote_approval_status(quote_id, user["org_id"]) or {}

    # Delivery terms options
    delivery_terms_options = ["DDP", "DAP", "EXW", "FCA", "CPT", "CIP", "FOB", "CIF"]
    delivery_method_options = [
        ("air", "Авиа"),
        ("auto", "Авто"),
        ("sea", "Море"),
        ("multimodal", "Мультимодально")
    ]
    delivery_priority_options = [
        ("fast", "Лучше быстро"),
        ("cheap", "Лучше дешево"),
        ("normal", "Обычно")
    ]

    # Compute created_at display and expiry info
    created_at_display = "—"
    expiry_display = "—"
    is_expired = False
    if quote.get("created_at"):
        try:
            created_dt = datetime.fromisoformat(quote["created_at"].replace("Z", "+00:00"))
            created_at_display = created_dt.strftime("%d.%m.%Y %H:%M")
            validity = quote.get("validity_days") or 30
            expiry_dt = created_dt + timedelta(days=validity)
            expiry_display = expiry_dt.strftime("%d.%m.%Y")
            is_expired = datetime.now(created_dt.tzinfo) > expiry_dt
        except Exception:
            pass

    # Look up deal for this quote (for finance tabs)
    # Only do the lookup if the tab is a finance tab or we need to check if finance tabs should show
    deal = _lookup_deal_for_quote(quote_id, user["org_id"])
    deal_id = deal["id"] if deal else None

    # If a finance tab is requested but no deal exists, fall back to summary
    if tab in ("finance_main", "plan_fact", "logistics_stages", "currency_invoices", "logistics_expenses") and not deal:
        tab = "summary"

    # Render finance tab content if requested
    if tab in ("finance_main", "plan_fact", "logistics_stages", "currency_invoices", "logistics_expenses") and deal:
        user_roles = effective_roles
        # Check role access for finance tabs
        finance_roles = ["finance", "admin", "top_manager"]
        if tab == "logistics_stages":
            finance_roles.append("logistics")
        if tab == "currency_invoices":
            finance_roles.append("currency_controller")
        if tab == "logistics_expenses":
            finance_roles.append("logistics")
        if not any(r in user_roles for r in finance_roles):
            return RedirectResponse("/unauthorized", status_code=303)

        # Currency invoices tab does not need full deal data fetch
        if tab == "currency_invoices":
            finance_content = _finance_currency_invoices_tab_content(deal_id)
            modal_elements = _finance_payment_modal(deal_id)
            return page_layout(f"Quote {quote.get('idn_quote', '')}",
                quote_header(quote, workflow_status, (customer or {}).get("name")),
                quote_detail_tabs(quote_id, tab, effective_roles, deal=deal, quote=quote, user_id=user["id"]),
                Div(finance_content, id="tab-content", style="margin-top: 20px;"),
                *modal_elements,
                session=session
            )

        # Logistics expenses tab does not need full deal data fetch
        if tab == "logistics_expenses":
            finance_content = _finance_logistics_expenses_tab_content(deal_id, user["org_id"], session)
            modal_elements = _finance_payment_modal(deal_id)
            return page_layout(f"Quote {quote.get('idn_quote', '')}",
                quote_header(quote, workflow_status, (customer or {}).get("name")),
                quote_detail_tabs(quote_id, tab, effective_roles, deal=deal, quote=quote, user_id=user["id"]),
                Div(finance_content, id="tab-content", style="margin-top: 20px;"),
                *modal_elements,
                session=session
            )

        # Fetch full deal data for finance tabs
        deal_full, plan_fact_items_deal, _ = _finance_fetch_deal_data(deal_id, user["org_id"], user_roles)
        if not deal_full:
            tab = "summary"
        else:
            # Build finance tab content
            if tab == "finance_main":
                finance_content = _finance_main_tab_content(deal_id, deal_full, plan_fact_items_deal)
            elif tab == "plan_fact":
                finance_content = _finance_plan_fact_tab_content(deal_id, plan_fact_items_deal)
            elif tab == "logistics_stages":
                finance_content = _finance_logistics_tab_content(deal_id, deal_full, session)

            # Render the quote page with finance tab content
            modal_elements = _finance_payment_modal(deal_id)
            return page_layout(f"Quote {quote.get('idn_quote', '')}",
                quote_header(quote, workflow_status, (customer or {}).get("name")),
                quote_detail_tabs(quote_id, tab, effective_roles, deal=deal, quote=quote, user_id=user["id"]),
                Div(finance_content, id="tab-content", style="margin-top: 20px;"),
                *modal_elements,
                session=session
            )

    # Render summary tab (read-only overview)
    if tab == "summary":
        # Fetch CBR USD/RUB exchange rates for quote and spec dates
        def _fetch_rate_for_date(date_value):
            """Parse a date string/object and fetch CBR USD/RUB rate for that date."""
            if not date_value:
                return None
            try:
                if isinstance(date_value, str):
                    parsed = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
                else:
                    parsed = date_value
                return get_usd_rub_rate(parsed.date() if hasattr(parsed, 'date') else parsed)
            except Exception:
                return None

        rate_on_quote_date = _fetch_rate_for_date(quote.get("created_at"))

        # Fetch spec created_at for rate on spec date
        rate_on_spec_date = None
        try:
            spec_result = supabase.table("specifications") \
                .select("created_at") \
                .eq("quote_id", quote_id) \
                .limit(1) \
                .is_("deleted_at", None) \
                .execute()
            if spec_result.data:
                spec_created_at = spec_result.data[0].get("created_at")
                rate_on_spec_date = _fetch_rate_for_date(spec_created_at)
        except Exception:
            pass

        summary_content = _render_summary_tab(
            quote, customer, seller_companies, contacts, items, creator_name,
            created_at_display, expiry_display,
            quote_controller_name=quote_controller_name,
            spec_controller_name=spec_controller_name,
            customs_user_name=customs_user_name,
            logistics_user_name=logistics_user_name,
            rate_on_quote_date=rate_on_quote_date,
            rate_on_spec_date=rate_on_spec_date,
        )
        return page_layout(f"Quote {quote.get('idn_quote', '')}",
            quote_header(quote, workflow_status, (customer or {}).get("name")),
            quote_detail_tabs(quote_id, "summary", effective_roles, deal=deal, quote=quote, user_id=user["id"]),
            summary_content,
            session=session
        )

    # Precompute ИТОГО block values
    _itogo_total = float(quote.get("total_quote_currency") or quote.get("total_amount") or 0)
    _itogo_revenue_no_vat = float(quote.get("revenue_no_vat_quote_currency") or 0)
    _itogo_profit = float(quote.get("profit_quote_currency") or 0)
    _itogo_cogs = float(quote.get("cogs_quote_currency") or 0)
    _itogo_currency = quote.get("currency", "RUB")
    _itogo_items_count = len(items)
    # Fallback for old quotes without revenue_no_vat
    if _itogo_revenue_no_vat == 0 and _itogo_total > 0:
        _tax_rate = float(quote.get("tax_rate") or 20)
        _itogo_revenue_no_vat = _itogo_total / (1 + _tax_rate / 100)
    # Fallback for old quotes without cogs
    if _itogo_cogs == 0 and _itogo_revenue_no_vat > 0 and _itogo_profit > 0:
        _itogo_cogs = _itogo_revenue_no_vat - _itogo_profit
    # Margin = profit / revenue (excl. VAT); Markup = profit / COGS
    _itogo_margin = (_itogo_profit / _itogo_revenue_no_vat * 100) if _itogo_revenue_no_vat > 0 else 0
    _itogo_markup = (_itogo_profit / _itogo_cogs * 100) if _itogo_cogs > 0 else 0
    _itogo_total_display = format_money(_itogo_total, _itogo_currency) if _itogo_total > 0 else "—"
    _itogo_profit_display = format_money(_itogo_profit, _itogo_currency) if _itogo_profit != 0 else "—"
    _itogo_profit_color = "#16a34a" if _itogo_profit > 0 else "#dc2626" if _itogo_profit < 0 else "#64748b"
    _itogo_margin_display = f"{_itogo_margin:.1f}%" if _itogo_revenue_no_vat > 0 else "—"
    _itogo_markup_display = f"{_itogo_markup:.1f}%" if _itogo_cogs > 0 else "—"
    _itogo_margin_color = "#16a34a" if _itogo_profit > 0 else "#64748b"

    return page_layout(f"Quote {quote.get('idn_quote', '')}",
        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, (customer or {}).get("name")),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "overview", effective_roles, deal=deal, quote=quote, user_id=user["id"]),

        # Workflow progress bar (same as on procurement/logistics/customs pages)
        workflow_progress_bar(workflow_status),

        # Persistent action toolbar

        _sales_action_toolbar(quote_id, workflow_status, is_revision, is_justification_needed),

        # Block I: ОСНОВНАЯ ИНФОРМАЦИЯ (2-column grid)
        Div(
            Div(
                icon("file-text", size=16, color="#64748b"),
                Span(" ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 0.7rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
            ),
            # 2-column grid layout (col 1: dropdowns, col 2: info + additional_info)
            Div(
                # Col 1, Row 1: Seller Company dropdown
                Div(
                    Div("ПРОДАВЕЦ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Select(
                        Option("—", value=""),
                        *[Option(
                            f"{sc.supplier_code} - {sc.name}" if sc.supplier_code else sc.name,
                            value=str(sc.id),
                            selected=(str(sc.id) == str(quote.get("seller_company_id") or ""))
                        ) for sc in seller_companies],
                        name="seller_company_id",
                        id="inline-seller",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "seller_company_id", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 2, Row 1: Creator
                Div(
                    Div("СОЗДАЛ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(creator_name or "—", style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                # Col 1, Row 2: Customer dropdown
                Div(
                    Div("КЛИЕНТ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Select(
                        Option("Выберите клиента...", value="", selected=(not quote.get("customer_id"))),
                        *[Option(
                            f"{c['name']}" + (f" ({c.get('inn', '')})" if c.get('inn') else ""),
                            value=c["id"],
                            selected=(c["id"] == quote.get("customer_id"))
                        ) for c in customers],
                        name="customer_id",
                        id="inline-customer",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;" + (" border-color: #f59e0b; background: #fffbeb;" if not quote.get("customer_id") else ""),
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "customer_id", value: event.target.value}',
                        hx_swap="none"
                    ),
                    Script("""
                        document.getElementById('inline-customer').addEventListener('htmx:afterRequest', function(event) {
                            if (event.detail.successful) { window.location.reload(); }
                        });
                    """),
                ),
                # Col 2, Row 2: Created at
                Div(
                    Div("ДАТА СОЗДАНИЯ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(created_at_display, style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                # Col 1, Row 3: Contact Person
                Div(
                    Div("КОНТАКТНОЕ ЛИЦО", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Select(
                        Option("— Не выбрано —", value=""),
                        *[Option(
                            f"{c['name']}" + (f" ({c.get('position', '')})" if c.get('position') else ""),
                            value=c["id"],
                            selected=(c["id"] == quote.get("contact_person_id"))
                        ) for c in contacts],
                        name="contact_person_id",
                        id="inline-contact-person",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "contact_person_id", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 2, Row 3: Additional info (NEW textarea field)
                Div(
                    Div("ДОП. ИНФОРМАЦИЯ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Textarea(
                        quote.get("additional_info") or "",
                        name="additional_info",
                        id="inline-additional-info",
                        placeholder="Заметки, комментарии...",
                        rows="3",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box; font-family: inherit; resize: vertical;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "additional_info", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 1, Row 4: Validity days (inline-editable)
                Div(
                    Div("СРОК ДЕЙСТВИЯ (ДНЕЙ)", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Input(
                        type="number",
                        value=str(quote.get("validity_days") or 30),
                        min="1",
                        name="validity_days",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box; max-width: 120px;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "validity_days", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 2, Row 4: Expiry date (calculated, with red/green indicator)
                Div(
                    Div("ДЕЙСТВИТЕЛЕН ДО", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Span(
                        expiry_display,
                        style=f"font-size: 14px; padding: 6px 10px; border-radius: 6px; display: inline-block; font-weight: 500; {'background: #fef2f2; color: #dc2626;' if is_expired else 'background: #f0fdf4; color: #16a34a;'}" if expiry_display != "\u2014" else "font-size: 14px; color: #334155; padding: 8px 0; display: block;"
                    ),
                ),
                # Col 1, Row 5: Customs manager (read-only)
                Div(
                    Div("ТАМОЖЕННЫЙ МЕНЕДЖЕР", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(customs_user_name or "—", style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                # Col 2, Row 5: Logistics manager (read-only)
                Div(
                    Div("ЛОГИСТИЧЕСКИЙ МЕНЕДЖЕР", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(logistics_user_name or "—", style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem 1.5rem;"
            ),
            cls="card",
            style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb; margin-bottom: 1rem;"
        ),

        # Block II+III: ДОСТАВКА (left) + summary metrics (right) side-by-side
        Div(
            # Left column: ДОСТАВКА card
            Div(
                Div(
                    icon("truck", size=16, color="#64748b"),
                    Span(" ДОСТАВКА", style="font-size: 0.7rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
                ),

                # Row: Страна, Город, Адрес поставки, Способ, Условия
                Div(
                    # Delivery Country
                    Div(
                        Label("СТРАНА", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Input(
                            type="text",
                            value=quote.get("delivery_country") or "",
                            placeholder="Введите страну",
                            name="delivery_country",
                            id="delivery-country-input",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_country", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 1 1 120px; min-width: 120px;"
                    ),
                    # Delivery City
                    Div(
                        Label("ГОРОД", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Input(
                            type="text",
                            value=quote.get("delivery_city") or "",
                            placeholder="Введите город",
                            name="delivery_city",
                            id="delivery-city-input",
                            list="cities-datalist",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_get="/api/cities/search",
                            hx_trigger="input changed delay:300ms",
                            hx_target="#cities-datalist",
                            hx_vals='js:{"q": document.getElementById("delivery-city-input").value}',
                            hx_swap="innerHTML",
                            onblur="if(typeof saveDeliveryCity==='function') saveDeliveryCity(this.value)",
                            onchange="if(typeof saveDeliveryCity==='function'){saveDeliveryCity(this.value); syncCountryFromCity(this);}",
                        ),
                        Datalist(id="cities-datalist"),
                        # Always-rendered save function for delivery city (not conditional on workflow status)
                        Script(f"""
                            function saveDeliveryCity(value) {{
                                fetch('/quotes/{quote_id}/inline', {{
                                    method: 'PATCH',
                                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                    body: 'field=delivery_city&value=' + encodeURIComponent(value)
                                }});
                            }}
                            function syncCountryFromCity(cityInput) {{
                                var datalist = document.getElementById('cities-datalist');
                                var countryInput = document.getElementById('delivery-country-input');
                                if (!datalist || !countryInput) return;
                                var options = datalist.querySelectorAll('option');
                                for (var i = 0; i < options.length; i++) {{
                                    if (options[i].value === cityInput.value) {{
                                        var country = options[i].getAttribute('data-country');
                                        if (country) {{
                                            countryInput.value = country;
                                            countryInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                                        }}
                                        break;
                                    }}
                                }}
                            }}
                        """),
                        style="flex: 1 1 120px; min-width: 120px;"
                    ),
                    # АДРЕС поставки (delivery_address)
                    Div(
                        Label("АДРЕС", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Input(
                            type="text",
                            value=quote.get("delivery_address") or "",
                            placeholder="Адрес поставки",
                            name="delivery_address",
                            id="delivery-address-input",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_address", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 2 1 200px; min-width: 200px;"
                    ),
                    # Delivery Method
                    Div(
                        Label("СПОСОБ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Select(
                            Option("—", value=""),
                            *[Option(label, value=val, selected=(val == quote.get("delivery_method"))) for val, label in delivery_method_options],
                            name="delivery_method",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_method", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 1 1 160px; min-width: 160px;"
                    ),
                    # Delivery Terms
                    Div(
                        Label("УСЛОВИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Select(
                            *[Option(term, value=term, selected=(term == quote.get("delivery_terms"))) for term in delivery_terms_options],
                            name="delivery_terms",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_terms", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 1 1 100px; min-width: 100px;"
                    ),
                    style="display: flex; flex-wrap: wrap; gap: 1rem;"
                ),
                cls="card",
                style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb;"
            ),
            # Right column: ИТОГО card
            Div(
                Div(
                    icon("bar-chart-2", size=16, color="#64748b"),
                    Span(" ИТОГО", style="font-size: 0.7rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
                ),
                Div(
                    Div(
                        Div("Общая сумма", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_total_display, style="font-size: 1.1rem; font-weight: 600; color: #1e40af;"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Общий профит", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_profit_display, style=f"font-size: 1.1rem; font-weight: 600; color: {_itogo_profit_color};"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Количество позиций", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(str(_itogo_items_count), style="font-size: 1.1rem; font-weight: 600; color: #374151;"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Маржа (профит ÷ выр. без НДС)", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_margin_display, style=f"font-size: 1.1rem; font-weight: 600; color: {_itogo_margin_color};"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Наценка (профит ÷ себест.)", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_markup_display, style=f"font-size: 1.1rem; font-weight: 600; color: {'#16a34a' if _itogo_markup > 0 else '#64748b'};"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb;"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;"
        ),

        # Products (Handsontable spreadsheet)
        Div(
            # Section header with icon
            Div(
                Div(
                    icon("package", size=16, color="#64748b"),
                    Span(" ПОЗИЦИИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    Span(id="items-count", style="margin-left: 0.5rem; font-size: 11px; color: #94a3b8;"),
                    style="display: flex; align-items: center;"
                ),
                Div(
                    Span(id="save-status", style="margin-right: 1rem; font-size: 0.85rem; color: #64748b;"),
                    # Add row button
                    A(icon("plus", size=16), " Добавить", id="btn-add-row", role="button", cls="secondary", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; margin-right: 0.5rem; text-decoration: none; font-size: 0.8125rem;"),
                    # Import button
                    A(icon("upload", size=16), " Загрузить", id="btn-import", role="button", cls="secondary", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; margin-right: 0.5rem; text-decoration: none; font-size: 0.8125rem;"),
                    Input(type="file", id="file-import", accept=".xlsx,.xls,.csv", style="display: none;"),
                    # Draft workflow buttons (only for draft status)
                    (A(icon("save", size=16), " Сохранить", id="btn-save-draft", role="button", cls="secondary", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; margin-right: 0.5rem; text-decoration: none; font-size: 0.8125rem;", onclick="showSaveConfirmation()") if workflow_status == 'draft' else None),
                    (A(icon("send", size=16), " Передать в закупки", id="btn-submit-procurement", role="button", cls="btn-submit-disabled", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; text-decoration: none; border-radius: 6px; font-size: 0.8125rem;", onclick="showChecklistModal()") if workflow_status == 'draft' else None),
                    style="display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem;"
                ),
                style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0;"
            ),
            # Handsontable container with enhanced styling
            Div(
                Div(id="items-spreadsheet", style="width: 100%; height: 400px; overflow: hidden;"),
                cls="handsontable-container"
            ),
            # Footer with count
            Div(
                Span(id="footer-count", style="color: #64748b;"),
                style="padding: 0.5rem 1rem; border-top: 1px solid #e2e8f0; font-size: 0.8125rem;"
            ),
            style="margin: 0; background: #fafbfc; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;"
        ),
        # Handsontable initialization script - EXPLICIT SAVE ONLY (no auto-save)
        Script(f"""
            (function() {{
                var quoteId = '{quote_id}';
                var quoteIdn = '{quote.get("idn_quote", "")}';
                var initialData = {items_json};
                var hot = null;
                var hasUnsavedChanges = false;

                function updateCount() {{
                    var count = hot ? hot.countRows() : 0;
                    var el = document.getElementById('items-count');
                    if (el) el.textContent = '(' + count + ')';
                    var footer = document.getElementById('footer-count');
                    if (footer) footer.textContent = 'Всего: ' + count + ' позиций';
                }}

                function showSaveStatus(status) {{
                    var el = document.getElementById('save-status');
                    if (!el) return;
                    if (status === 'saving') {{
                        el.textContent = 'Сохранение...';
                        el.style.color = '#f59e0b';
                    }} else if (status === 'saved') {{
                        el.textContent = 'Сохранено ✓';
                        el.style.color = '#10b981';
                        hasUnsavedChanges = false;
                        setTimeout(function() {{ el.textContent = ''; }}, 2000);
                    }} else if (status === 'error') {{
                        el.textContent = 'Не удалось сохранить';
                        el.style.color = '#ef4444';
                        setTimeout(function() {{ el.textContent = ''; }}, 5000);
                    }}
                }}

                // Bulk save all items - replaces everything in DB
                function saveAllItems() {{
                    // IMPORTANT: Finish any active cell edit before reading data
                    if (hot) hot.deselectCell();
                    var sourceData = hot.getSourceData();
                    var items = sourceData.filter(function(row) {{
                        return row.product_name && row.product_name.trim();
                    }});

                    if (items.length === 0) {{
                        alert('Нет позиций для сохранения');
                        return Promise.resolve(false);
                    }}

                    showSaveStatus('saving');

                    return fetch('/quotes/' + quoteId + '/items/bulk', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ items: items }})
                    }})
                    .then(function(r) {{ return r.json(); }})
                    .then(function(data) {{
                        if (data.success) {{
                            // Update IDs in table data
                            if (data.items) {{
                                var validIdx = 0;
                                for (var i = 0; i < sourceData.length; i++) {{
                                    if (sourceData[i].product_name && sourceData[i].product_name.trim()) {{
                                        if (data.items[validIdx]) {{
                                            sourceData[i].id = data.items[validIdx].id;
                                        }}
                                        validIdx++;
                                    }}
                                }}
                            }}
                            showSaveStatus('saved');
                            return true;
                        }} else {{
                            showSaveStatus('error');
                            alert('Ошибка сохранения: ' + (data.error || 'Неизвестная ошибка'));
                            return false;
                        }}
                    }})
                    .catch(function(e) {{
                        showSaveStatus('error');
                        alert('Ошибка сети: ' + e.message);
                        return false;
                    }});
                }}

                // Make saveAllItems available globally
                window.saveAllItems = saveAllItems;

                // Warn on page leave with unsaved changes
                window.addEventListener('beforeunload', function(e) {{
                    if (hasUnsavedChanges) {{
                        e.preventDefault();
                        e.returnValue = 'Есть несохранённые изменения. Уйти?';
                    }}
                }});

                // Row numbers are assigned on save, not during editing
                function updateRowNumbers() {{
                    updateCount();
                }}

                function initTable() {{
                    var container = document.getElementById('items-spreadsheet');
                    if (!container || typeof Handsontable === 'undefined') return;

                    hot = new Handsontable(container, {{
                        licenseKey: 'non-commercial-and-evaluation',
                        data: initialData.length > 0 ? initialData : [{{row_num: 1, brand: '', product_code: '', product_name: '', quantity: 1, unit: 'шт'}}],
                        colHeaders: ['№', 'Бренд', 'Артикул', 'Наименование', 'Кол-во', 'Ед.изм.'],
                        columns: [
                            {{data: 'row_num', readOnly: true, type: 'numeric', width: 50,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  // Always show visual row number (1-based), regardless of stored value
                                  td.innerHTML = row + 1;
                                  td.style.textAlign = 'center';
                                  td.style.color = '#666';
                                  return td;
                              }}
                            }},
                            {{data: 'brand', type: 'text', width: 120}},
                            {{data: 'product_code', type: 'text', width: 140}},
                            {{data: 'product_name', type: 'text', width: 300}},
                            {{data: 'quantity', type: 'numeric', width: 80}},
                            {{data: 'unit', type: 'dropdown', source: ['шт', 'упак', 'компл', 'кг', 'г', 'т', 'м', 'мм', 'см', 'м²', 'м³', 'л', 'мл'], width: 80}}
                        ],
                        rowHeaders: false,
                        stretchH: 'all',
                        autoWrapRow: true,
                        autoWrapCol: true,
                        contextMenu: ['row_above', 'row_below', 'remove_row', '---------', 'copy', 'cut'],
                        manualColumnResize: true,
                        minSpareRows: 0,
                        afterChange: function(changes, source) {{
                            if (source === 'loadData' || !changes) return;
                            // Mark as having unsaved changes (no auto-save)
                            hasUnsavedChanges = true;
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }},
                        afterCreateRow: function(index, amount, source) {{
                            hasUnsavedChanges = true;
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }},
                        afterRemoveRow: function() {{
                            hasUnsavedChanges = true;
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }},
                        cells: function(row, col) {{
                            var cellProperties = {{}};
                            var rowData = this.instance.getSourceDataAtRow(row);
                            if (rowData && rowData.id) {{
                                cellProperties.title = quoteIdn + '-' + (row + 1);
                            }}
                            return cellProperties;
                        }}
                    }});

                    updateCount();
                    // Make hot available globally for validation
                    window.hot = hot;
                    if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();

                    var btnAdd = document.getElementById('btn-add-row');
                    if (btnAdd) {{
                        btnAdd.addEventListener('click', function() {{
                            // Add empty row - row_num will be assigned on save
                            // The renderer shows visual row index automatically
                            hot.alter('insert_row_below');
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }});
                    }}

                    var btnFileImport = document.getElementById('btn-import');
                    var fileInput = document.getElementById('file-import');
                    if (btnFileImport && fileInput) {{
                        btnFileImport.addEventListener('click', function() {{
                            fileInput.click();
                        }});
                        fileInput.addEventListener('change', function(e) {{
                            var file = e.target.files[0];
                            if (!file) return;
                            var reader = new FileReader();
                            reader.onload = function(evt) {{
                                var data = new Uint8Array(evt.target.result);
                                var workbook = XLSX.read(data, {{type: 'array'}});
                                var firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                                var jsonData = XLSX.utils.sheet_to_json(firstSheet, {{header: 1}});
                                showFileImportModal(jsonData);
                            }};
                            reader.readAsArrayBuffer(file);
                            e.target.value = '';
                        }});
                    }}

                    window.switchTab = function(tab) {{
                        document.querySelectorAll('.tab-btn').forEach(function(btn) {{ btn.classList.remove('active'); }});
                        var tabBtn = document.getElementById('tab-' + tab);
                        if (tabBtn) tabBtn.classList.add('active');
                    }};
                }}

                function showFileImportModal(jsonData) {{
                    if (jsonData.length < 2) {{
                        alert('Файл пустой или содержит только заголовки');
                        return;
                    }}
                    var headers = jsonData[0];
                    var preview = jsonData.slice(1, 6);

                    function buildOptions(defaultText) {{
                        var opts = '<option value="">' + defaultText + '</option>';
                        for (var i = 0; i < headers.length; i++) {{
                            opts += '<option value="' + i + '">' + (headers[i] || 'Колонка ' + (i+1)) + '</option>';
                        }}
                        return opts;
                    }}

                    function buildPreviewTable() {{
                        var html = '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;"><thead><tr style="background:#f3f4f6;">';
                        for (var i = 0; i < headers.length; i++) {{
                            html += '<th style="padding:0.5rem;border:1px solid #e5e7eb;text-align:left;">' + (headers[i] || '—') + '</th>';
                        }}
                        html += '</tr></thead><tbody>';
                        for (var r = 0; r < preview.length; r++) {{
                            html += '<tr>';
                            for (var c = 0; c < headers.length; c++) {{
                                html += '<td style="padding:0.5rem;border:1px solid #e5e7eb;">' + (preview[r][c] || '') + '</td>';
                            }}
                            html += '</tr>';
                        }}
                        html += '</tbody></table>';
                        return html;
                    }}

                    var modal = document.createElement('div');
                    modal.id = 'file-import-modal';
                    modal.innerHTML = '<div style="position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;">' +
                        '<div style="background:white;padding:2rem;border-radius:12px;max-width:800px;width:90%;max-height:80vh;overflow:auto;">' +
                        '<h3 style="margin-top:0;">Импорт из файла</h3>' +
                        '<p>Найдено строк: ' + (jsonData.length - 1) + '</p>' +
                        '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin-bottom:1.5rem;">' +
                        '<div><label>Наименование *</label><select id="map-name" style="width:100%;padding:0.5rem;">' + buildOptions('-- Выберите колонку --') + '</select></div>' +
                        '<div><label>Артикул</label><select id="map-code" style="width:100%;padding:0.5rem;">' + buildOptions('-- Не выбрано --') + '</select></div>' +
                        '<div><label>Бренд</label><select id="map-brand" style="width:100%;padding:0.5rem;">' + buildOptions('-- Не выбрано --') + '</select></div>' +
                        '<div><label>Количество</label><select id="map-qty" style="width:100%;padding:0.5rem;">' + buildOptions('-- По умолчанию 1 --') + '</select></div>' +
                        '</div>' +
                        '<h4>Превью данных:</h4>' +
                        '<div style="overflow-x:auto;margin-bottom:1.5rem;">' + buildPreviewTable() + '</div>' +
                        '<div style="display:flex;gap:1rem;justify-content:flex-end;">' +
                        '<button onclick="closeFileImportModal()" style="padding:0.75rem 1.5rem;border:1px solid #d1d5db;background:white;border-radius:8px;cursor:pointer;">Отмена</button>' +
                        '<button onclick="runFileImport()" style="padding:0.75rem 1.5rem;background:#6366f1;color:white;border:none;border-radius:8px;cursor:pointer;">Импортировать</button>' +
                        '</div></div></div>';
                    document.body.appendChild(modal);

                    headers.forEach(function(h, i) {{
                        var lower = (h || '').toString().toLowerCase();
                        if (lower.indexOf('наименование') >= 0 || lower.indexOf('название') >= 0 || lower.indexOf('name') >= 0) {{
                            document.getElementById('map-name').value = i;
                        }}
                        if (lower.indexOf('артикул') >= 0 || lower.indexOf('код') >= 0 || lower.indexOf('sku') >= 0) {{
                            document.getElementById('map-code').value = i;
                        }}
                        if (lower.indexOf('бренд') >= 0 || lower.indexOf('brand') >= 0) {{
                            document.getElementById('map-brand').value = i;
                        }}
                        if (lower.indexOf('кол') >= 0 || lower.indexOf('qty') >= 0 || lower.indexOf('quantity') >= 0) {{
                            document.getElementById('map-qty').value = i;
                        }}
                    }});

                    window.closeFileImportModal = function() {{
                        var m = document.getElementById('file-import-modal');
                        if (m) m.remove();
                    }};

                    window.runFileImport = function() {{
                        var nameIdx = document.getElementById('map-name').value;
                        if (nameIdx === '') {{
                            alert('Выберите колонку для наименования');
                            return;
                        }}
                        var codeIdx = document.getElementById('map-code').value;
                        var brandIdx = document.getElementById('map-brand').value;
                        var qtyIdx = document.getElementById('map-qty').value;

                        var newItems = [];
                        var currentCount = hot.countRows();
                        for (var i = 1; i < jsonData.length; i++) {{
                            var row = jsonData[i];
                            var name = row[nameIdx];
                            if (!name) continue;
                            newItems.push({{
                                row_num: currentCount + newItems.length,
                                brand: brandIdx !== '' ? (row[brandIdx] || '') : '',
                                product_code: codeIdx !== '' ? (row[codeIdx] || '') : '',
                                product_name: name,
                                quantity: qtyIdx !== '' ? (parseInt(row[qtyIdx]) || 1) : 1,
                                unit: 'шт'
                            }});
                        }}

                        if (newItems.length === 0) {{
                            alert('Нет данных для импорта');
                            return;
                        }}

                        // Add items to table (in memory) - user will click Save to persist
                        var sourceData = hot.getSourceData();
                        var filtered = sourceData.filter(function(r) {{ return r.product_name && r.product_name.trim(); }});
                        hot.loadData(filtered.concat(newItems));
                        hasUnsavedChanges = true;
                        updateCount();
                        closeFileImportModal();
                        alert('Импортировано ' + newItems.length + ' позиций. Нажмите "Сохранить" для сохранения.');
                        if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                    }};
                }}

                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initTable);
                }} else {{
                    initTable();
                }}
            }})();
        """),
        # Handsontable styles
        Style("""
            #items-spreadsheet .htCore {
                font-size: 14px;
            }
            #items-spreadsheet th {
                background: #f9fafb !important;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 0.75rem;
                letter-spacing: 0.05em;
            }
        """),

        # Multi-department approval progress (Bug #8 follow-up)
        Div(
            H3(icon("file-check", size=20), " Прогресс согласования КП", style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;"),

            # Progress bar visual with 5 departments
            Div(
                *[Div(
                    Div(dept_name, style="font-weight: 600; font-size: 0.75rem; margin-bottom: 0.25rem;"),
                    Div(
                        icon("check-circle", size=28) if approval_status.get(dept, {}).get('approved') else
                        icon("clock", size=28) if approval_status.get(dept, {}).get('can_approve') else icon("x-circle", size=28),
                        style="color: #10b981;" if approval_status.get(dept, {}).get('approved') else ("color: #f59e0b;" if approval_status.get(dept, {}).get('can_approve') else "color: #9ca3af;")
                    ),
                    style="flex: 1; text-align: center; padding: 0.5rem; border-right: 2px solid #e5e7eb;" if dept != 'control' else "flex: 1; text-align: center; padding: 0.5rem;"
                ) for dept, dept_name in [('procurement', 'Закупки'), ('logistics', 'Логистика'), ('customs', 'Таможня'), ('sales', 'Продажи'), ('control', 'Контроль')]],
                style="display: flex; margin-bottom: 1.5rem; background: white; border: 1px solid #e5e7eb; border-radius: 6px;"
            ),

            # Department status details
            *[
                Div(
                    # Header with status
                    Div(
                        Span(
                            icon("check-circle", size=18) if dept_status.get('approved') else
                            icon("clock", size=18) if dept_status.get('can_approve') else icon("x-circle", size=18),
                            f" {QUOTE_DEPARTMENT_NAMES[dept]}",
                            style=f"font-weight: 600; font-size: 1.1rem; color: {'#10b981' if dept_status.get('approved') else ('#f59e0b' if dept_status.get('can_approve') else '#9ca3af')}; display: inline-flex; align-items: center; gap: 0.25rem;"
                        ),
                        Span(
                            " - Одобрено" if dept_status.get('approved') else
                            " - Ожидает проверки" if dept_status.get('can_approve') else
                            " - Недоступно",
                            style="color: #059669;" if dept_status.get('approved') else
                            "color: #d97706;" if dept_status.get('can_approve') else "color: #6b7280;"
                        ),
                        style="margin-bottom: 0.75rem;"
                    ),

                    # If approved - show details
                    (Div(
                        P(f"Одобрил: {dept_status.get('approved_by', 'N/A')}", style="margin: 0.25rem 0; font-size: 0.875rem; color: #6b7280;"),
                        P(f"Дата: {dept_status.get('approved_at', '')[:10]}", style="margin: 0.25rem 0; font-size: 0.875rem; color: #6b7280;") if dept_status.get('approved_at') else None,
                        P(f"Комментарий: {dept_status.get('comments')}", style="margin: 0.25rem 0; font-size: 0.875rem;") if dept_status.get('comments') else None,
                    ) if dept_status.get('approved') else None),

                    # If can approve and user has role - show approve form
                    (Div(
                        Form(
                            Input(type="hidden", name="department", value=dept),
                            Textarea(
                                name="comments",
                                placeholder="Комментарий (необязательно)",
                                style="width: 100%; margin-bottom: 0.5rem; min-height: 60px;"
                            ),
                            btn("Одобрить", variant="success", icon_name="check", type="submit"),
                            action=f"/quotes/{quote_id}/approve-department",
                            method="POST"
                        ),
                        style="margin-top: 0.75rem;"
                    ) if dept_status.get('can_approve') and user_can_approve_quote_department(session, dept) else None),

                    # If blocked - show blocking message
                    (P(
                        f"Требуется одобрение: {', '.join([QUOTE_DEPARTMENT_NAMES[d] for d in dept_status.get('blocking_departments', [])])}",
                        style="margin-top: 0.5rem; font-size: 0.875rem; color: #dc2626;"
                    ) if dept_status.get('blocking_departments') and not dept_status.get('approved') else None),

                    cls="card",
                    style="margin-bottom: 1rem; padding: 1rem; background: #f9fafb;"
                )
                for dept, dept_status in [(d, approval_status.get(d, {})) for d in QUOTE_DEPARTMENTS]
            ],

            cls="card",
            style="background: #f0fdf4; border-left: 4px solid #10b981; margin-bottom: 1.5rem;"
        ) if workflow_status in ['pending_review', 'pending_procurement', 'pending_logistics', 'pending_customs', 'pending_sales', 'pending_control', 'pending_spec_control'] and approval_status else None,

        # CSS for submit button states (using high specificity to override Pico)
        Style("""
            a[role="button"].btn-submit-disabled,
            a[role="button"].btn-submit-disabled:hover,
            a.btn-submit-disabled[role="button"],
            #btn-submit-procurement.btn-submit-disabled {
                background: #e5e7eb !important;
                background-color: #e5e7eb !important;
                color: #9ca3af !important;
                border: 1px solid #d1d5db !important;
                pointer-events: none !important;
                cursor: not-allowed !important;
            }
            a[role="button"].btn-submit-enabled,
            a[role="button"].btn-submit-enabled:hover,
            a.btn-submit-enabled[role="button"],
            #btn-submit-procurement.btn-submit-enabled {
                background: #16a34a !important;
                background-color: #16a34a !important;
                color: white !important;
                border: 1px solid #16a34a !important;
                pointer-events: auto !important;
                cursor: pointer !important;
            }
        """) if workflow_status == 'draft' else None,

        # Draft validation script (moved to header buttons)
        Script(f"""
            // Save all items when clicking Save button
            function showSaveConfirmation() {{
                var btn = document.getElementById('btn-save-draft');
                if (!btn) return;
                var originalHTML = btn.innerHTML;
                btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg> Сохранение...';
                btn.style.pointerEvents = 'none';

                // Save delivery city before saving items (BUG-2 fix)
                var cityInput = document.getElementById('delivery-city-input');
                if (cityInput) saveDeliveryCity(cityInput.value);

                // Call global saveAllItems function
                if (typeof window.saveAllItems === 'function') {{
                    window.saveAllItems().then(function(success) {{
                        if (success) {{
                            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Сохранено!';
                            btn.style.background = '#dcfce7';
                            btn.style.borderColor = '#16a34a';
                            btn.style.color = '#16a34a';
                        }} else {{
                            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg> Ошибка';
                            btn.style.background = '#fee2e2';
                            btn.style.borderColor = '#ef4444';
                            btn.style.color = '#ef4444';
                        }}
                        btn.style.pointerEvents = '';
                        setTimeout(function() {{
                            btn.innerHTML = originalHTML;
                            btn.style.background = '';
                            btn.style.borderColor = '';
                            btn.style.color = '';
                        }}, 2000);
                    }});
                }} else {{
                    btn.innerHTML = originalHTML;
                    btn.style.pointerEvents = '';
                    alert('Таблица не загружена');
                }}
            }}

            // Server-side quote values (for validation when fields are on another sub-tab)
            var _quoteData = {{
                customer_id: {json.dumps(str(quote.get("customer_id") or ""))},
                seller_company_id: {json.dumps(str(quote.get("seller_company_id") or ""))},
                delivery_city: {json.dumps(quote.get("delivery_city") or "")},
                delivery_country: {json.dumps(quote.get("delivery_country") or "")},
                delivery_method: {json.dumps(quote.get("delivery_method") or "")},
                delivery_terms: {json.dumps(quote.get("delivery_terms") or "")}
            }};

            // Validation for submit to procurement
            function validateForProcurement() {{
                var errors = [];

                // Check header fields — use DOM if available (info subtab), else server-side data
                var customerEl = document.getElementById('inline-customer');
                var customerVal = customerEl ? customerEl.value : _quoteData.customer_id;
                if (!customerVal) errors.push('Клиент');

                var sellerEl = document.getElementById('inline-seller');
                var sellerVal = sellerEl ? sellerEl.value : _quoteData.seller_company_id;
                if (!sellerVal) errors.push('Продавец');

                var cityEl = document.querySelector('input[name="delivery_city"]');
                var cityVal = cityEl ? cityEl.value.trim() : _quoteData.delivery_city.trim();
                if (!cityVal) errors.push('Город доставки');

                var countryEl = document.querySelector('input[name="delivery_country"]');
                var countryVal = countryEl ? countryEl.value.trim() : _quoteData.delivery_country.trim();
                if (!countryVal) errors.push('Страна');

                var methodEl = document.querySelector('select[name="delivery_method"]');
                var methodVal = methodEl ? methodEl.value : _quoteData.delivery_method;
                if (!methodVal) errors.push('Способ доставки');

                var termsEl = document.querySelector('select[name="delivery_terms"]');
                var termsVal = termsEl ? termsEl.value : _quoteData.delivery_terms;
                if (!termsVal) errors.push('Условия поставки');

                // Check items in Handsontable
                if (typeof hot !== 'undefined' && hot) {{
                    var data = hot.getSourceData();
                    var validItems = 0;
                    for (var i = 0; i < data.length; i++) {{
                        var row = data[i];
                        if (row && row.product_name && row.product_name.trim() &&
                            row.quantity && !isNaN(row.quantity) && row.quantity > 0 &&
                            row.unit && row.unit.trim()) {{
                            validItems++;
                        }}
                    }}
                    if (validItems === 0) {{
                        errors.push('Хотя бы одна позиция (наименование, количество, ед.изм.)');
                    }}
                }} else {{
                    errors.push('Позиции не загружены');
                }}

                return errors;
            }}

            // Update submit button state based on validation
            function updateSubmitButtonState() {{
                var btn = document.getElementById('btn-submit-procurement');
                if (!btn) return;

                var errors = validateForProcurement();
                if (errors.length === 0) {{
                    btn.classList.remove('btn-submit-disabled');
                    btn.classList.add('btn-submit-enabled');
                    btn.title = 'Передать КП в отдел закупок';
                }} else {{
                    btn.classList.remove('btn-submit-enabled');
                    btn.classList.add('btn-submit-disabled');
                    btn.title = 'Заполните: ' + errors.join(', ');
                }}
            }}

            // Submit to procurement with validation - saves first, then submits
            function submitToProcurement() {{
                var errors = validateForProcurement();
                if (errors.length > 0) {{
                    alert('Заполните обязательные поля:\\n- ' + errors.join('\\n- '));
                    return false;
                }}

                var btn = document.getElementById('btn-submit-procurement');
                if (btn) {{
                    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg> Сохранение...';
                    btn.style.pointerEvents = 'none';
                }}

                // Save delivery city before saving items (BUG-2 fix)
                var cityInput = document.getElementById('delivery-city-input');
                if (cityInput) saveDeliveryCity(cityInput.value);

                // First save all items, then submit
                if (typeof window.saveAllItems === 'function') {{
                    window.saveAllItems().then(function(saved) {{
                        if (saved) {{
                            // Now submit via POST
                            var form = document.createElement('form');
                            form.method = 'POST';
                            form.action = '/quotes/{quote_id}/submit-procurement';
                            document.body.appendChild(form);
                            form.submit();
                        }} else {{
                            if (btn) {{
                                btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"></path><path d="M22 2 11 13"></path></svg> Передать в закупки';
                                btn.style.pointerEvents = '';
                            }}
                        }}
                    }});
                }} else {{
                    alert('Таблица не загружена');
                    if (btn) btn.style.pointerEvents = '';
                }}
                return true;
            }}

            // saveDeliveryCity and syncCountryFromCity are defined globally
            // in the delivery city input Script block (always rendered).

            // Run validation on page load and on changes
            document.addEventListener('DOMContentLoaded', function() {{
                updateSubmitButtonState();

                // Listen for changes to update button state
                document.querySelectorAll('input, select').forEach(function(el) {{
                    el.addEventListener('change', updateSubmitButtonState);
                }});
            }});

            // Also update after Handsontable changes
            window.updateSubmitButtonState = updateSubmitButtonState;
        """) if workflow_status == "draft" else None,

        # Sales checklist modal (gate for draft -> pending_procurement transition)
        Div(
            Div(
                # Modal header
                Div(
                    icon("clipboard-check", size=20),
                    Span("Контрольный список", style="font-size: 16px; font-weight: 600; margin-left: 8px;"),
                    style="display: flex; align-items: center; margin-bottom: 16px;"
                ),
                P("Заполните информацию перед передачей в закупки:", style="color: #64748b; margin-bottom: 16px; font-size: 0.875rem;"),
                # Checkboxes
                Div(
                    Label(
                        Input(type="checkbox", id="chk_is_estimate", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Это проценка?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    Label(
                        Input(type="checkbox", id="chk_is_tender", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Это тендер?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    Label(
                        Input(type="checkbox", id="chk_direct_request", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Запрашивал ли клиент напрямую?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    Label(
                        Input(type="checkbox", id="chk_trading_org", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Запрашивал ли клиент через торгующих организаций?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    style="margin-bottom: 16px;"
                ),
                # Textarea (required)
                Div(
                    Label(
                        "Что это за оборудование и для чего оно необходимо? ",
                        Span("*", style="color: #ef4444;"),
                        fr="checklist_equipment",
                        style="font-size: 0.875rem; font-weight: 500; display: block; margin-bottom: 6px;"
                    ),
                    Textarea(
                        id="checklist_equipment",
                        placeholder="Опишите оборудование и его назначение...",
                        style="width: 100%; min-height: 80px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; font-family: inherit; resize: vertical;"
                    ),
                    Span("", id="checklist_error", style="color: #ef4444; font-size: 0.75rem; display: none; margin-top: 4px;"),
                    style="margin-bottom: 20px;"
                ),
                # Dialog buttons
                Div(
                    Button("Отмена", type="button", id="checklist_cancel",
                           style="padding: 10px 24px; background: #f1f5f9; color: #374151; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; font-size: 14px;"),
                    Button(
                        icon("send", size=14),
                        " Передать в закупки",
                        type="button", id="checklist_submit",
                        style="padding: 10px 24px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-weight: 500; cursor: pointer; margin-left: 8px; font-size: 14px; display: inline-flex; align-items: center; gap: 6px;"
                    ),
                    style="display: flex; justify-content: flex-end;"
                ),
                style="background: white; padding: 24px; border-radius: 12px; max-width: 500px; width: 90%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);"
            ),
            id="checklist_modal",
            style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.5); z-index: 1000; justify-content: center; align-items: center;"
        ) if workflow_status == "draft" else None,

        # JavaScript for sales checklist modal
        Script(f"""
            function showChecklistModal() {{
                var errors = validateForProcurement();
                if (errors.length > 0) {{
                    alert('Заполните обязательные поля:\\n- ' + errors.join('\\n- '));
                    return;
                }}
                document.getElementById('checklist_modal').style.display = 'flex';
            }}

            (function() {{
                var modal = document.getElementById('checklist_modal');
                if (!modal) return;

                var cancelBtn = document.getElementById('checklist_cancel');
                var submitBtn = document.getElementById('checklist_submit');
                var errorEl = document.getElementById('checklist_error');

                function closeModal() {{
                    modal.style.display = 'none';
                }}

                cancelBtn.addEventListener('click', closeModal);

                // Close on backdrop click
                modal.addEventListener('click', function(e) {{
                    if (e.target === modal) closeModal();
                }});

                // Close on Escape key
                document.addEventListener('keydown', function(e) {{
                    if (e.key === 'Escape' && modal.style.display === 'flex') closeModal();
                }});

                submitBtn.addEventListener('click', function() {{
                    var desc = document.getElementById('checklist_equipment').value.trim();
                    if (!desc) {{
                        errorEl.textContent = 'Это поле обязательно для заполнения';
                        errorEl.style.display = 'block';
                        document.getElementById('checklist_equipment').style.borderColor = '#ef4444';
                        return;
                    }}
                    errorEl.style.display = 'none';
                    document.getElementById('checklist_equipment').style.borderColor = '#e2e8f0';

                    submitBtn.disabled = true;
                    submitBtn.textContent = 'Отправка...';

                    var checklist = {{
                        is_estimate: document.getElementById('chk_is_estimate').checked,
                        is_tender: document.getElementById('chk_is_tender').checked,
                        direct_request: document.getElementById('chk_direct_request').checked,
                        trading_org_request: document.getElementById('chk_trading_org').checked,
                        equipment_description: desc
                    }};

                    // Save delivery city first
                    var cityInput = document.getElementById('delivery-city-input');
                    if (cityInput) saveDeliveryCity(cityInput.value);

                    // Save all items first, then save checklist + submit
                    var savePromise = (typeof window.saveAllItems === 'function')
                        ? window.saveAllItems()
                        : Promise.resolve(true);

                    savePromise.then(function(saved) {{
                        if (!saved) {{
                            submitBtn.disabled = false;
                            submitBtn.textContent = 'Передать в закупки';
                            return;
                        }}

                        fetch('/quotes/{quote_id}/submit-procurement', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{checklist: checklist}})
                        }}).then(function(res) {{
                            if (res.redirected) {{
                                window.location.href = res.url;
                            }} else {{
                                return res.json();
                            }}
                        }}).then(function(data) {{
                            if (data && data.redirect) {{
                                window.location.href = data.redirect;
                            }} else if (data && data.error) {{
                                alert('Ошибка: ' + data.error);
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Передать в закупки';
                            }}
                        }}).catch(function(err) {{
                            alert('Ошибка при отправке: ' + err.message);
                            submitBtn.disabled = false;
                            submitBtn.textContent = 'Передать в закупки';
                        }});
                    }});
                }});
            }})();
        """) if workflow_status == "draft" else None,

        # Revision banner for sales (Feature: multi-department return)
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
            P("После внесения исправлений верните КП на проверку.", style="margin: 0; font-size: 0.875rem;"),
            cls="card",
            style="background: #fef3c7; border: 2px solid #f59e0b; margin-bottom: 1rem;"
        ) if is_revision else None,

        # Justification banner (Feature: approval justification workflow)
        Div(
            Div(
                Span("📝 Требуется обоснование для согласования", style="font-weight: 600; font-size: 1.1rem;"),
                style="margin-bottom: 0.5rem;"
            ),
            Div(
                Span("Причина согласования (от контроллёра КП):", style="font-weight: 500;"),
                P(approval_reason, style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap;"),
                style="margin-bottom: 1rem;"
            ) if approval_reason else None,
            P("Укажите бизнес-обоснование для согласования этого КП топ-менеджером.", style="margin: 0; font-size: 0.875rem;"),
            cls="card",
            style="background: #dbeafe; border: 2px solid #3b82f6; margin-bottom: 1rem;"
        ) if is_justification_needed else None,

        # Workflow Actions (for pending_sales_review - submit for Quote Control, return after revision, or submit justification)
        Div(
            H3("Действия"),
            # Justification flow: Submit justification for approval (Feature: approval justification workflow)
            Div(
                btn_link("Отправить обоснование", href=f"/quotes/{quote_id}/submit-justification", variant="primary", icon_name="check", size="lg"),
                P("Заполнить обоснование и отправить на согласование топ-менеджеру.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
            ) if is_justification_needed else None,
            # Normal flow: Submit for Quote Control
            Form(
                btn("Отправить на контроль КП", variant="primary", icon_name="file-text", size="lg", type="submit"),
                P("Отправить рассчитанный КП на проверку контроллёру.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
                method="post",
                action=f"/quotes/{quote_id}/submit-quote-control"
            ) if not is_revision and not is_justification_needed else None,
            # Revision flow: Return to Quote Control with comment
            Div(
                btn_link("Вернуть на проверку", href=f"/quotes/{quote_id}/return-to-control", variant="success", icon_name="check", size="lg"),
                P("Отправить КП контроллёру после исправлений.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
            ) if is_revision else None,
            cls="card", style="border-left: 4px solid #3b82f6;" if is_justification_needed else ("border-left: 4px solid #ec4899;" if not is_revision else "border-left: 4px solid #22c55e;")
        ) if workflow_status == "pending_sales_review" else None,

        # Workflow Actions (for pending_approval - Top Manager approval)
        Div(
            H3(icon("clock", size=20), " Согласование", cls="card-header"),
            P("Этот КП требует вашего одобрения.", style="margin-bottom: 1rem;"),

            # Show approval context (approval_reason from controller, approval_justification from sales)
            Div(
                Div(
                    Span("📋 Причина согласования (от контроллёра):", style="font-weight: 500;"),
                    P(approval_reason, style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap; background: #fef3c7; padding: 0.5rem; border-radius: 4px;"),
                    style="margin-bottom: 0.75rem;"
                ) if approval_reason else None,
                Div(
                    Span("💼 Обоснование менеджера:", style="font-weight: 500;"),
                    P(quote.get("approval_justification", ""), style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap; background: #dbeafe; padding: 0.5rem; border-radius: 4px;"),
                    style="margin-bottom: 1rem;"
                ) if quote.get("approval_justification") else None,
                style="margin-bottom: 1rem;"
            ) if approval_reason or quote.get("approval_justification") else None,

            Form(
                Div(
                    Label("Комментарий (необязательно):", for_="approval_comment"),
                    Input(type="text", name="comment", id="approval_comment",
                          placeholder="Ваш комментарий...", style="width: 100%; margin-bottom: 1rem;"),
                ),
                Div(
                    btn("Одобрить", variant="success", icon_name="check", type="submit", name="action", value="approve"),
                    btn("Отклонить", variant="danger", icon_name="x", type="submit", name="action", value="reject", cls="ml-3"),
                    btn_link("На доработку", href=f"/quotes/{quote_id}/approval-return", variant="secondary", icon_name="arrow-left", cls="ml-3"),
                    style="display: flex; gap: 0.75rem; flex-wrap: wrap;"
                ),
                method="post",
                action=f"/quotes/{quote_id}/manager-decision"
            ),
            cls="card", style="border-left: 4px solid #f59e0b;"
        ) if workflow_status == "pending_approval" and user_has_any_role(session, ["top_manager", "admin"]) else None,

        # Workflow Actions (for approved/sent_to_client - Client Response)
        Div(
            H3(icon("message-circle", size=20), " Ответ клиента", style="display: flex; align-items: center; gap: 0.5rem;"),
            P("КП одобрено. Какой результат от клиента?", style="margin-bottom: 1rem; color: #666;"),
            Div(
                Form(
                    btn("Клиент согласен → Спецификация", variant="success", icon_name="check", type="submit"),
                    method="post",
                    action=f"/quotes/{quote_id}/submit-spec-control",
                    style="display: inline;"
                ),
                style="margin-bottom: 1rem;"
            ),
            # Compact "mark as sent" — only shown when status is still "approved"
            Div(
                Form(
                    btn("Отметить: отправлено клиенту", variant="secondary", icon_name="send", size="sm", type="submit"),
                    method="post",
                    action=f"/quotes/{quote_id}/send-to-client",
                    style="display: inline;"
                ),
                style="border-top: 1px solid #e2e8f0; padding-top: 0.75rem; margin-top: 0.5rem;"
            ) if workflow_status == "approved" else None,
            cls="card", style="border-left: 4px solid #14b8a6;"
        ) if workflow_status in ("approved", "sent_to_client") and user_has_any_role(session, ["sales", "admin"]) else None,

        # Client Change Request Section (for sent_to_client)
        Div(
            H3(icon("rotate-ccw", size=20), " Клиент просит изменения", style="display: flex; align-items: center; gap: 0.5rem;"),
            P("Выберите тип изменений:", style="margin-bottom: 1rem; color: #666;"),
            Form(
                Div(
                    # Change type radio buttons
                    Div(
                        Input(type="radio", name="change_type", value="add_item", id="change_add_item", required=True),
                        Label(" Добавить позицию → Закупка", fr="change_add_item", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),
                    Div(
                        Input(type="radio", name="change_type", value="logistics", id="change_logistics"),
                        Label(" Изменить логистику → Логистика", fr="change_logistics", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),
                    Div(
                        Input(type="radio", name="change_type", value="price", id="change_price"),
                        Label(" Изменить цену → Расчёт", fr="change_price", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),
                    Div(
                        Input(type="radio", name="change_type", value="full", id="change_full"),
                        Label(" Полный пересчёт → Начало", fr="change_full", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 1rem;"
                    ),
                    style="margin-bottom: 1rem;"
                ),
                # Client comment
                Div(
                    Label("Комментарий клиента:", fr="client_comment", style="font-weight: 500;"),
                    Textarea(name="client_comment", id="client_comment", placeholder="Опишите, что именно хочет изменить клиент...",
                             rows="3", style="width: 100%; margin-top: 0.25rem;"),
                    style="margin-bottom: 1rem;"
                ),
                Div(
                    btn("Отправить на доработку", variant="secondary", icon_name="rotate-ccw", size="lg", type="submit"),
                ),
                method="post",
                action=f"/quotes/{quote_id}/client-change-request"
            ),
            cls="card", style="border-left: 4px solid #f59e0b;"
        ) if workflow_status in ("approved", "sent_to_client") and user_has_any_role(session, ["sales", "admin"]) else None,

        # Client Rejected Section (for sent_to_client)
        Div(
            H3(icon("x-circle", size=20), " Клиент отказался", style="display: flex; align-items: center; gap: 0.5rem; color: #dc2626;"),
            Form(
                Div(
                    Label("Причина отказа *", fr="rejection_reason", style="font-weight: 500;"),
                    Select(
                        Option("-- Выберите причину --", value="", disabled=True, selected=True),
                        Option("Цена слишком высокая", value="price_too_high"),
                        Option("Сроки не устраивают", value="delivery_time"),
                        Option("Выбрали другого поставщика", value="competitor"),
                        Option("Проект отменён / заморожен", value="project_cancelled"),
                        Option("Нет бюджета", value="no_budget"),
                        Option("Изменились требования", value="requirements_changed"),
                        Option("Другое", value="other"),
                        name="rejection_reason",
                        id="rejection_reason",
                        required=True,
                        style="width: 100%; margin-top: 0.25rem;"
                    ),
                    style="margin-bottom: 1rem;"
                ),
                Div(
                    Label("Комментарий:", fr="rejection_comment", style="font-weight: 500;"),
                    Textarea(name="rejection_comment", id="rejection_comment",
                             placeholder="Дополнительные детали об отказе...",
                             rows="2", style="width: 100%; margin-top: 0.25rem;"),
                    style="margin-bottom: 1rem;"
                ),
                btn("Отметить как отказ", variant="danger", icon_name="x", type="submit"),
                method="post",
                action=f"/quotes/{quote_id}/client-rejected"
            ),
            cls="card", style="border-left: 4px solid #dc2626;"
        ) if workflow_status in ("approved", "sent_to_client") and user_has_any_role(session, ["sales", "admin"]) else None,

        # Activity log (workflow transitions history)
        workflow_transition_history(quote_id, limit=50, collapsed=True),

        # Back button removed — toolbar at top has all navigation

        # Delete confirmation modal
        Script(f"""
            function showDeleteModal() {{
                const modal = document.createElement('div');
                modal.id = 'delete-modal';
                modal.innerHTML = `
                    <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;">
                        <div style="background: white; padding: 2rem; border-radius: 12px; max-width: 400px; width: 90%;">
                            <h3 style="margin-top: 0; color: #dc2626;">Удалить КП?</h3>
                            <p>КП будет отмечен как отменённый. Это действие можно отменить.</p>
                            <div style="display: flex; gap: 1rem; justify-content: flex-end; margin-top: 1.5rem;">
                                <button onclick="document.getElementById('delete-modal').remove()" style="padding: 0.75rem 1.5rem; border: 1px solid #d1d5db; background: white; border-radius: 8px; cursor: pointer;">Отмена</button>
                                <button onclick="deleteQuote()" style="padding: 0.75rem 1.5rem; background: #dc2626; color: white; border: none; border-radius: 8px; cursor: pointer;">Удалить</button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            }}

            function deleteQuote() {{
                fetch('/quotes/{quote_id}/cancel', {{
                    method: 'POST'
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.success) {{
                        window.location.href = data.redirect || '/quotes';
                    }} else {{
                        alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                        document.getElementById('delete-modal').remove();
                    }}
                }})
                .catch(err => {{
                    alert('Ошибка: ' + err.message);
                    document.getElementById('delete-modal').remove();
                }});
            }}
        """),
        session=session
    )


# ============================================================================
# SUBMIT QUOTE FOR PROCUREMENT
# ============================================================================

# @rt("/quotes/{quote_id}/submit-procurement", methods=["POST"])
async def post(quote_id: str, session, request):
    """Submit a draft quote for procurement evaluation with sales checklist."""
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
        redirect = require_login(session)
        if redirect:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        user = session["user"]
        user_roles = user.get("roles", [])
        org_id = user["org_id"]

    if not user or not user.get("id"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Parse checklist from JSON body
    checklist_data = None
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


# ============================================================================
# SUBMIT QUOTE FOR QUOTE CONTROL
# ============================================================================

# @rt("/quotes/{quote_id}/submit-quote-control")
def post(quote_id: str, session):
    """Submit a quote from pending_sales_review to pending_quote_control."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    # Use the workflow service to transition to pending_quote_control
    result = transition_quote_status(
        quote_id=quote_id,
        to_status="pending_quote_control",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Submitted by sales for quote control review"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error submitting quote: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SALES - RETURN TO QUOTE CONTROL AFTER REVISION (Feature: multi-department return)
# ============================================================================

# @rt("/quotes/{quote_id}/return-to-control")
def get(quote_id: str, session):
    """
    Form for sales to return a revised quote back to quote control.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
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

    if workflow_status != "pending_sales_review":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
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
                A(icon("arrow-left", size=16), f" Назад к КП {idn_quote}", href=f"/quotes/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1("Вернуть КП на проверку",
               style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            Div(
                icon("users", size=14, style="color: #64748b;"),
                Span(f"Клиент: {customer_name}", style="color: #475569;"),
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
                    placeholder="Исправлена наценка...\nОбновлены условия оплаты...\nИзменены данные клиента...",
                    required=True,
                    style=textarea_style
                ),
                style="margin-bottom: 24px;"
            ),
            Div(
                Button(icon("check", size=14), " Вернуть на проверку", type="submit",
                       style="padding: 10px 20px; background: #22c55e; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/quotes/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                style="display: flex; gap: 12px;"
            ),
            action=f"/quotes/{quote_id}/return-to-control",
            method="post",
            style=form_card_style
        ),
        session=session
    )


# @rt("/quotes/{quote_id}/return-to-control")
def post(quote_id: str, session, comment: str = ""):
    """
    Handle return to quote control from sales.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий об исправлениях."),
            A("← Вернуться", href=f"/quotes/{quote_id}/return-to-control"),
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

    if current_status != "pending_sales_review":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_QUOTE_CONTROL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"Исправления от продаж: {comment.strip()}"
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
            A("← Назад", href=f"/quotes/{quote_id}/return-to-control"),
            session=session
        )


# ============================================================================
# SUBMIT JUSTIFICATION (Feature: approval justification workflow)
# ============================================================================

# @rt("/quotes/{quote_id}/submit-justification")
def get(session, quote_id: str):
    """
    Justification form - sales manager provides business case for approval.

    Feature: Approval justification workflow (Variant B)
    - Controller specifies why approval is needed (approval_reason)
    - Sales manager provides business justification (approval_justification)
    - Then quote goes to top manager with full context
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has sales role
    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    needs_justification = quote.get("needs_justification", False)
    approval_reason = quote.get("approval_reason", "")

    # Check if quote is in correct status and needs justification
    if workflow_status != "pending_sales_review" or not needs_justification:
        return page_layout("Обоснование не требуется",
            H1("Обоснование не требуется"),
            P("Это КП не требует обоснования для согласования."),
            A("← Вернуться к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    idn_quote = quote.get("idn_quote", "")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    return page_layout(f"Обоснование - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к КП", href=f"/quotes/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(icon("file-text", size=28), f" Обоснование для согласования {idn_quote}", cls="page-header"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Approval reason from controller
        Div(
            H3("Причина согласования (от контроллёра КП)"),
            P(approval_reason, style="font-style: italic; white-space: pre-wrap; background: #f3f4f6; padding: 1rem; border-radius: 6px;"),
            cls="card",
            style="margin-bottom: 1rem; background: #fef3c7;"
        ) if approval_reason else None,

        # Form
        Form(
            Div(
                H3("Ваше обоснование", style="margin-bottom: 0.5rem;"),
                P("Объясните, почему эта сделка важна для компании и почему предложенные условия обоснованы.",
                  style="color: #666; font-size: 0.875rem; margin-bottom: 1rem;"),
                Textarea(
                    name="justification",
                    id="justification",
                    placeholder="Укажите бизнес-обоснование...\n\nНапример:\n- Стратегический клиент с большим потенциалом\n- Первая сделка для входа в новый сегмент\n- Конкурентная ситуация требует гибкости по цене",
                    required=True,
                    style="width: 100%; min-height: 200px; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; resize: vertical;"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Action buttons
            Div(
                btn("Отправить на согласование", variant="primary", icon_name="send", type="submit"),
                btn_link("Отмена", href=f"/quotes/{quote_id}", variant="ghost"),
                style="display: flex; align-items: center; gap: 1rem;"
            ),

            action=f"/quotes/{quote_id}/submit-justification",
            method="post",
            cls="card"
        ),

        session=session
    )


# @rt("/quotes/{quote_id}/submit-justification")
def post(session, quote_id: str, justification: str = ""):
    """
    Handle justification form submission.

    1. Validate justification is provided
    2. Save approval_justification
    3. Clear needs_justification flag
    4. Call request_approval to send to top manager
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has sales role
    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Validate justification
    if not justification or not justification.strip():
        return page_layout("Ошибка",
            H1("Ошибка отправки"),
            P("Необходимо указать обоснование для согласования."),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/submit-justification"),
            session=session
        )

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("workflow_status, needs_justification, idn_quote, total_amount, currency, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    needs_justification = quote.get("needs_justification", False)
    idn_quote = quote.get("idn_quote", "")
    customer_name = (quote.get("customers") or {}).get("name", "")
    total_amount = quote.get("total_amount")

    # Verify quote is in correct status
    if workflow_status != "pending_sales_review" or not needs_justification:
        return page_layout("Ошибка",
            H1("Обоснование не требуется"),
            P("Это КП не находится в статусе ожидания обоснования."),
            A("← Вернуться к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Save justification and clear flag
    supabase.table("quotes").update({
        "approval_justification": justification.strip(),
        "needs_justification": False
    }).eq("id", quote_id).execute()

    # Get user's role codes for transition
    user_roles = get_user_roles_from_session(session)

    # Transition directly from pending_sales_review to pending_approval
    # (using new transition added for justification workflow)
    from services.workflow_service import transition_quote_status, WorkflowStatus
    from services.approval_service import create_approvals_for_role
    from services.telegram_service import send_approval_notification_for_quote
    import asyncio

    transition_result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_APPROVAL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"[С обоснованием] {justification.strip()[:200]}..."
    )

    if not transition_result.success:
        return page_layout("Ошибка",
            H1("Ошибка отправки"),
            P(f"Не удалось отправить КП на согласование: {transition_result.error_message}"),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/submit-justification"),
            session=session
        )

    # Create approval records for top_manager/admin users
    approvals = create_approvals_for_role(
        quote_id=quote_id,
        organization_id=org_id,
        requested_by=user_id,
        reason=f"[С обоснованием менеджера] {justification.strip()[:200]}...",
        role_codes=['top_manager', 'admin'],
        approval_type='top_manager'
    )
    approvals_created = len(approvals)

    # Send Telegram notifications
    notifications_sent = 0
    if approvals_created > 0:
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            notification_result = loop.run_until_complete(
                send_approval_notification_for_quote(
                    quote_id=quote_id,
                    approval_reason=f"[С обоснованием менеджера] {justification.strip()[:100]}...",
                    requester_id=user_id
                )
            )
            notifications_sent = notification_result.get('telegram_sent', 0)
        except Exception as e:
            print(f"Error sending approval notifications: {e}")

    details = []
    if approvals_created > 0:
        details.append(P(f"Создано запросов на согласование: {approvals_created}"))
    if notifications_sent > 0:
        details.append(P(f"Отправлено уведомлений в Telegram: {notifications_sent}"))

    return page_layout("Успешно",
        H1(icon("check", size=28), " КП отправлено на согласование", cls="page-header"),
        P(f"КП {idn_quote} с вашим обоснованием отправлено на согласование топ-менеджеру."),
        *details,
        P("Вы получите уведомление о решении.", style="color: #666;"),
        btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
        session=session
    )


# ============================================================================
# MANAGER APPROVAL/REJECTION
# ============================================================================

# @rt("/quotes/{quote_id}/manager-decision")
def post(quote_id: str, session, action: str = "", comment: str = ""):
    """Top manager approves or rejects a quote."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    # Check role
    if not user_has_any_role(session, ["top_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if action == "approve":
        to_status = "approved"
        comment = comment or "Одобрено топ-менеджером"
    elif action == "reject":
        to_status = "rejected"
        if not comment:
            return page_layout("Error",
                Div("Для отклонения необходимо указать причину.", cls="alert alert-error"),
                A("← Назад к КП", href=f"/quotes/{quote_id}"),
                session=session
            )
    else:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    # Use the workflow service to transition
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=to_status,
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=comment
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# TOP MANAGER - RETURN FOR REVISION (Feature: multi-department return)
# ============================================================================

# @rt("/quotes/{quote_id}/approval-return")
def get(session, quote_id: str):
    """
    Return for revision form for top manager.
    Similar to quote controller's return form - can return to any department.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has top_manager role
    if not user_has_any_role(session, ["top_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is in pending_approval status
    if workflow_status != "pending_approval":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП не находится в статусе ожидания согласования."),
            A("← Вернуться к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    idn_quote = quote.get("idn_quote", "")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    return page_layout(f"Возврат на доработку - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к КП", href=f"/quotes/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(icon("arrow-left", size=28), f" Возврат КП {idn_quote} на доработку", cls="page-header"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Department selection form
        Form(
            Div(
                H3("Выберите отдел для доработки", style="margin-bottom: 1rem;"),
                Div(
                    Input(type="radio", name="department", value="quote_control", id="dept_control", checked=True),
                    Label(" Контроль КП", for_="dept_control"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="sales", id="dept_sales"),
                    Label(" Продажи", for_="dept_sales"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="procurement", id="dept_procurement"),
                    Label(" Закупки", for_="dept_procurement"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="logistics", id="dept_logistics"),
                    Label(" Логистика", for_="dept_logistics"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="customs", id="dept_customs"),
                    Label(" Таможня", for_="dept_customs"),
                    style="margin-bottom: 1rem;"
                ),
                style="margin-bottom: 1rem;"
            ),

            Div(
                H3("Комментарий", style="margin-bottom: 0.5rem;"),
                P("Укажите, что необходимо исправить.", style="color: #666; font-size: 0.875rem; margin-bottom: 1rem;"),
                Textarea(
                    name="comment",
                    id="comment",
                    placeholder="Укажите, что необходимо исправить...",
                    required=True,
                    style="width: 100%; min-height: 120px; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; resize: vertical;"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Action buttons
            Div(
                btn("Вернуть на доработку", variant="secondary", icon_name="arrow-left", type="submit"),
                btn_link("Отмена", href=f"/quotes/{quote_id}", variant="ghost"),
                style="display: flex; align-items: center; gap: 1rem;"
            ),

            action=f"/quotes/{quote_id}/approval-return",
            method="post",
            cls="card"
        ),

        session=session
    )


# @rt("/quotes/{quote_id}/approval-return")
def post(session, quote_id: str, department: str = "quote_control", comment: str = ""):
    """
    Handle return for revision from top manager.
    Routes to the selected department with revision tracking.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has top_manager role
    if not user_has_any_role(session, ["top_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Validate comment
    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий с описанием необходимых исправлений."),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/approval-return"),
            session=session
        )

    # Map department to workflow status
    department_status_map = {
        "quote_control": WorkflowStatus.PENDING_QUOTE_CONTROL,
        "sales": WorkflowStatus.PENDING_SALES_REVIEW,
        "procurement": WorkflowStatus.PENDING_PROCUREMENT,
        "logistics": WorkflowStatus.PENDING_LOGISTICS,
        "customs": WorkflowStatus.PENDING_CUSTOMS,
    }

    department_names = {
        "quote_control": "Контроль КП",
        "sales": "Продажи",
        "procurement": "Закупки",
        "logistics": "Логистика",
        "customs": "Таможня",
    }

    to_status = department_status_map.get(department, WorkflowStatus.PENDING_QUOTE_CONTROL)
    department_name = department_names.get(department, "Контроль КП")

    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=to_status,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"[Возврат от топ-менеджера] {comment.strip()}"
    )

    if result.success:
        # Save revision tracking info
        supabase = get_supabase()
        supabase.table("quotes").update({
            "revision_department": department if department != "quote_control" else None,
            "revision_comment": comment.strip() if department != "quote_control" else None,
            "revision_returned_at": datetime.now(timezone.utc).isoformat() if department != "quote_control" else None
        }).eq("id", quote_id).execute()

        return page_layout("Успешно",
            H1(icon("check", size=28), " КП возвращено на доработку"),
            P(f"КП отправлено в отдел «{department_name}» для доработки."),
            P(f"Комментарий: {comment.strip()}", style="color: #666; font-style: italic;"),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось вернуть КП: {result.error_message}"),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/approval-return"),
            session=session
        )


# ============================================================================
# SEND TO CLIENT
# ============================================================================

# @rt("/quotes/{quote_id}/send-to-client")
def post(quote_id: str, session, sent_to_email: str = ""):
    """Send approved quote to client."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Save sent_at timestamp and sent_to_email
    from datetime import datetime
    supabase = get_supabase()
    supabase.table("quotes").update({
        "sent_at": datetime.utcnow().isoformat(),
        "sent_to_email": sent_to_email.strip() if sent_to_email else None
    }).eq("id", quote_id).execute()

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="sent_to_client",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=f"Quote sent to client at {sent_to_email}" if sent_to_email else "Quote sent to client"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# CLIENT CHANGE REQUEST
# ============================================================================

# @rt("/quotes/{quote_id}/client-change-request")
def post(quote_id: str, session, change_type: str = "", client_comment: str = ""):
    """Handle client change request - route to appropriate workflow stage."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Validate change type
    valid_types = ["add_item", "logistics", "price", "full"]
    if change_type not in valid_types:
        return page_layout("Error",
            Div("Invalid change type", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Record the change request
    from datetime import datetime
    try:
        supabase.table("quote_change_requests").insert({
            "quote_id": quote_id,
            "change_type": change_type,
            "client_comment": client_comment.strip() if client_comment else None,
            "requested_by": user["id"],
            "requested_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        # Table might not exist yet if migration not applied - continue anyway
        pass

    # Map change type to target workflow status
    status_map = {
        "add_item": "pending_procurement",
        "logistics": "pending_logistics",
        "price": "pending_sales_review",
        "full": "pending_procurement"
    }

    target_status = status_map.get(change_type, "pending_procurement")

    # Update quote with partial_recalc flag
    try:
        supabase.table("quotes").update({
            "partial_recalc": change_type
        }).eq("id", quote_id).execute()
    except Exception:
        pass

    # Transition quote status
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=target_status,
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=f"Client change request: {change_type}. Comment: {client_comment}" if client_comment else f"Client change request: {change_type}"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SUBMIT FOR SPEC CONTROL
# ============================================================================

# @rt("/quotes/{quote_id}/submit-spec-control")
def post(quote_id: str, session):
    """Submit quote for specification control."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="pending_spec_control",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Client accepted, submitted for specification"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# @rt("/quotes/{quote_id}/client-rejected")
def post(quote_id: str, session, rejection_reason: str = "", rejection_comment: str = ""):
    """
    Mark quote as rejected by client with reason.
    Transitions to 'rejected' status and stores rejection reason.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Map rejection reason codes to human-readable labels
    reason_labels = {
        "price_too_high": "Цена слишком высокая",
        "delivery_time": "Сроки не устраивают",
        "competitor": "Выбрали другого поставщика",
        "project_cancelled": "Проект отменён / заморожен",
        "no_budget": "Нет бюджета",
        "requirements_changed": "Изменились требования",
        "other": "Другое",
    }

    reason_label = reason_labels.get(rejection_reason, rejection_reason)

    # Build comment with reason
    comment_parts = [f"Причина отказа: {reason_label}"]
    if rejection_comment and rejection_comment.strip():
        comment_parts.append(f"Комментарий: {rejection_comment.strip()}")

    full_comment = ". ".join(comment_parts)

    # Store rejection reason in quote metadata
    supabase = get_supabase()
    try:
        supabase.table("quotes").update({
            "rejection_reason": rejection_reason,
            "rejection_comment": rejection_comment.strip() if rejection_comment else None,
            "rejected_at": datetime.now().isoformat(),
            "rejected_by": user["id"]
        }).eq("id", quote_id).execute()
    except Exception as e:
        print(f"Error storing rejection reason: {e}")
        # Continue even if metadata update fails

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="rejected",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=full_comment
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Ошибка",
            Div(f"Ошибка: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# @rt("/quotes/{quote_id}/approve-department")
def post(quote_id: str, session, department: str = "", comments: str = ""):
    """
    Approve quote for a specific department.

    Bug #8 follow-up: Multi-department approval workflow
    POST handler for department approval form.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    # Validate department parameter
    if not department:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    # Check if user has permission to approve for this department
    if not user_can_approve_quote_department(session, department):
        return RedirectResponse("/unauthorized", status_code=303)

    # Perform approval
    success, message = approve_quote_department(
        quote_id=quote_id,
        organization_id=user["org_id"],
        department=department,
        user_id=user["id"],
        comments=comments if comments else None
    )

    # Debug logging
    print(f"[DEBUG] Approve department: dept={department}, success={success}, message={message}")

    # Redirect back to quote detail page
    # TODO: Add flash message with success/error message
    return RedirectResponse(f"/quotes/{quote_id}", status_code=303)


# ============================================================================
# QUOTE PRODUCTS
# ============================================================================

# ============================================================================
# QUOTE ITEM API (Handsontable)
# ============================================================================
# Note: /quotes/{quote_id}/products page was removed (2026-01-29)
# Product entry is now done via Handsontable on /quotes/{quote_id} overview page

# @rt("/quotes/{quote_id}/items/{item_id}", methods=["PATCH"])
async def patch_quote_item(quote_id: str, item_id: str, session, request):
    """Update a single quote item field (for Handsontable auto-save)"""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    # Parse JSON body
    body = await request.body()
    try:
        data = json.loads(body)
    except:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    # Allowed fields for update
    item_update_fields = ['product_name', 'product_code', 'brand', 'quantity', 'unit']
    update_data = {k: v for k, v in data.items() if k in item_update_fields}

    if not update_data:
        return JSONResponse({"success": False, "error": "No valid fields to update"}, status_code=400)

    try:
        result = supabase.table("quote_items") \
            .update(update_data) \
            .eq("id", item_id) \
            .eq("quote_id", quote_id) \
            .execute()

        if result.data:
            return JSONResponse({"success": True, "item": result.data[0]})
        else:
            return JSONResponse({"success": False, "error": "Item not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/quotes/{quote_id}/items/bulk", methods=["POST"])
async def bulk_insert_quote_items(quote_id: str, session, request):
    """Bulk insert quote items (for import functionality)"""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id, organization_id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    # Parse JSON body
    body = await request.body()
    try:
        data = json.loads(body)
    except:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    items_data = data.get("items", [])
    if not items_data:
        return JSONResponse({"success": False, "error": "No items provided"}, status_code=400)

    # First, delete existing items for this quote (we're replacing all)
    try:
        supabase.table("quote_items") \
            .delete() \
            .eq("quote_id", quote_id) \
            .execute()
    except Exception as e:
        pass  # Ignore if no items existed

    # Prepare items for insert
    # base_price_vat is nullable with default 0, so we don't pass it
    # row_num column doesn't exist - ordering is by created_at
    insert_items = []
    for idx, item in enumerate(items_data, start=1):
        insert_items.append({
            "quote_id": quote_id,
            "product_name": item.get("product_name", ""),
            "product_code": item.get("product_code", ""),
            "brand": item.get("brand", ""),
            "quantity": int(item.get("quantity", 1)),
            "unit": item.get("unit", "шт")
        })

    try:
        result = supabase.table("quote_items") \
            .insert(insert_items) \
            .execute()

        return JSONResponse({
            "success": True,
            "items": [{"id": item["id"]} for item in result.data],
            "count": len(result.data)
        })
    except Exception as e:
        print(f"Bulk insert error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/quotes/{quote_id}/inline", methods=["PATCH"])
async def inline_update_quote(quote_id: str, session, request):
    """Inline update a single quote field via HTMX"""
    redirect = require_login(session)
    if redirect:
        return ""

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return ""

    # Parse form data from HTMX
    form = await request.form()
    field = form.get("field")
    value = form.get("value")

    # Debug logging to track "undefined" issue
    print(f"[INLINE UPDATE] quote_id={quote_id}, field={field}, value={repr(value)}")

    if not field:
        return ""

    # Editable fields for inline update
    editable_fields = [
        'customer_id', 'seller_company_id', 'contact_person_id',
        'delivery_city', 'delivery_country', 'delivery_method',
        'delivery_priority', 'delivery_terms', 'delivery_address',
        'currency', 'payment_terms', 'notes', 'validity_days',
        'additional_info'
    ]

    if field not in editable_fields:
        return ""

    # Handle empty values and the string "undefined" (JavaScript serialization bug)
    if value == "" or value is None or value == "undefined":
        value = None

    # Convert integer fields
    if field == "validity_days" and value is not None:
        try:
            value = max(1, int(value))
        except (ValueError, TypeError):
            value = 30

    try:
        update_data = {field: value}
        # When customer changes, clear contact_person_id (belongs to old customer)
        if field == "customer_id":
            update_data["contact_person_id"] = None
        supabase.table("quotes") \
            .update(update_data) \
            .eq("id", quote_id) \
            .execute()
        return ""  # HTMX swap="none", no response needed
    except Exception as e:
        print(f"Inline update error: {e}")
        return ""


# @rt("/quotes/{quote_id}/cancel", methods=["POST"])
def cancel_quote(quote_id: str, session):
    """Soft delete quote by setting workflow_status to 'cancelled'"""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    try:
        result = supabase.table("quotes") \
            .update({
                "workflow_status": "cancelled",
                "stage_entered_at": datetime.now(timezone.utc).isoformat(),
                "overdue_notified_at": None,
            }) \
            .eq("id", quote_id) \
            .execute()

        return JSONResponse({"success": True, "redirect": "/quotes"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ============================================================================
# QUOTE EDIT
# ============================================================================

# @rt("/quotes/{quote_id}/edit")
def get(quote_id: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote (seller_company_id column may not exist if migration not applied)
    result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = result.data[0]

    # Get customers
    customers_result = supabase.table("customers") \
        .select("id, name, inn") \
        .eq("organization_id", user["org_id"]) \
        .order("name") \
        .execute()

    customers = customers_result.data or []

    # Get seller companies for dropdown
    from services.seller_company_service import get_all_seller_companies, format_seller_company_for_dropdown
    seller_companies = get_all_seller_companies(organization_id=user["org_id"], is_active=True)

    # Get customer contacts for contact person dropdown
    edit_contacts = []
    if quote.get("customer_id"):
        try:
            edit_contacts_result = supabase.table("customer_contacts") \
                .select("id, name, position, phone, is_lpr") \
                .eq("customer_id", quote["customer_id"]) \
                .order("is_lpr", desc=True) \
                .order("name") \
                .execute()
            edit_contacts = edit_contacts_result.data or []
        except Exception:
            pass

    # Prepare seller company info for pre-selected value
    # Note: seller_company_id column may not exist if migration 028 not applied
    selected_seller_id = quote.get("seller_company_id")
    selected_seller_label = None
    # We no longer join seller_companies since FK may not exist

    # Design system styles
    header_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 24px;
    """

    section_header_style = """
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    """

    form_card_style = """
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    input_style = """
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
        width: 100%;
        box-sizing: border-box;
    """

    select_style = """
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
        width: 100%;
        box-sizing: border-box;
    """

    label_style = "display: block; font-size: 13px; color: #475569; margin-bottom: 6px; font-weight: 500;"

    form_group_style = "margin-bottom: 16px;"

    grid_2col_style = "display: grid; grid-template-columns: 1fr 1fr; gap: 20px;"

    return page_layout(f"Редактирование {quote.get('idn_quote', '')}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), " Назад к КП", href=f"/quotes/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1(f"Редактирование КП {quote.get('idn_quote', '')}",
               style="margin: 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            style=header_style
        ),

        Form(
            # Section 1: Client & Status
            Div(
                Div(icon("users", size=14), " Клиент и статус", style=section_header_style),
                Div(
                    Div(
                        Label("Клиент *", style=label_style),
                        Select(
                            *[Option(
                                f"{c['name']} ({c.get('inn', '')})",
                                value=c["id"],
                                selected=(c["id"] == quote.get("customer_id"))
                            ) for c in customers],
                            name="customer_id", required=True,
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    Div(
                        Label("Статус", style=label_style),
                        Select(
                            Option("Черновик", value="draft", selected=quote.get("status") == "draft"),
                            Option("Отправлено", value="sent", selected=quote.get("status") == "sent"),
                            Option("Одобрено", value="approved", selected=quote.get("status") == "approved"),
                            Option("Отклонено", value="rejected", selected=quote.get("status") == "rejected"),
                            name="status",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                Div(
                    Label("Компания-продавец *", style=label_style),
                    Select(
                        Option("Выберите компанию...", value=""),
                        *[Option(
                            format_seller_company_for_dropdown(sc),
                            value=sc.id,
                            selected=(str(sc.id) == str(selected_seller_id)) if selected_seller_id else False
                        ) for sc in seller_companies],
                        name="seller_company_id", required=True,
                        style=select_style
                    ),
                    Small("Наше юридическое лицо для продажи",
                          style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"),
                    style=form_group_style
                ),
                Div(
                    Label("Контактное лицо", style=label_style),
                    Select(
                        Option("— Не выбрано —", value=""),
                        *[Option(
                            f"{'⭐ ' if c.get('is_lpr') else ''}{c['name']}" + (f" ({c.get('position', '')})" if c.get('position') else ""),
                            value=c["id"],
                            selected=(c["id"] == quote.get("contact_person_id"))
                        ) for c in edit_contacts],
                        name="contact_person_id",
                        style=select_style
                    ),
                    Small("ЛПР или контакт клиента",
                          style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"),
                    style=form_group_style
                ),
                style=form_card_style
            ),

            # Section 2: Delivery
            Div(
                Div(icon("truck", size=14), " Доставка", style=section_header_style),
                Div(
                    Div(
                        Label("Город доставки", style=label_style),
                        Input(
                            name="delivery_city",
                            id="edit-delivery-city-input",
                            type="text",
                            value=quote.get("delivery_city", "") or "",
                            placeholder="Москва, Пекин и т.д.",
                            list="city-datalist",
                            style=input_style,
                            hx_get="/api/cities/search",
                            hx_trigger="input changed delay:300ms",
                            hx_target="#city-datalist",
                            hx_vals='js:{"q": document.getElementById("edit-delivery-city-input").value}',
                            hx_swap="innerHTML"
                        ),
                        Datalist(id="city-datalist"),
                        style=form_group_style
                    ),
                    Div(
                        Label("Страна доставки", style=label_style),
                        Input(
                            name="delivery_country",
                            type="text",
                            value=quote.get("delivery_country", "") or "",
                            placeholder="Россия, Китай и т.д.",
                            style=input_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                Div(
                    Div(
                        Label("Способ доставки", style=label_style),
                        Select(
                            Option("-- Выберите способ --", value="", selected=not quote.get("delivery_method")),
                            Option("Авиа", value="air", selected=quote.get("delivery_method") == "air"),
                            Option("Авто", value="auto", selected=quote.get("delivery_method") == "auto"),
                            Option("Море", value="sea", selected=quote.get("delivery_method") == "sea"),
                            Option("Мультимодально", value="multimodal", selected=quote.get("delivery_method") == "multimodal"),
                            name="delivery_method",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    Div(
                        Label("Условия поставки", style=label_style),
                        Select(
                            Option("EXW", value="EXW", selected=quote.get("delivery_terms") == "EXW"),
                            Option("FOB", value="FOB", selected=quote.get("delivery_terms") == "FOB"),
                            Option("CIF", value="CIF", selected=quote.get("delivery_terms") == "CIF"),
                            Option("DDP", value="DDP", selected=quote.get("delivery_terms") == "DDP"),
                            name="delivery_terms",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                Div(
                    Div(
                        Label("Приоритет доставки", style=label_style),
                        Select(
                            Option("-- Выберите приоритет --", value="", selected=not quote.get("delivery_priority")),
                            Option("Лучше быстро", value="fast", selected=quote.get("delivery_priority") == "fast"),
                            Option("Лучше дешево", value="cheap", selected=quote.get("delivery_priority") == "cheap"),
                            Option("Обычно", value="normal", selected=quote.get("delivery_priority") == "normal"),
                            name="delivery_priority",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                style=form_card_style
            ),

            # Section 3: Terms
            Div(
                Div(icon("file-text", size=14), " Условия оплаты и сроки", style=section_header_style),
                Div(
                    Div(
                        Label("Валюта", style=label_style),
                        Select(
                            Option("RUB", value="RUB", selected=quote.get("currency") == "RUB"),
                            Option("USD", value="USD", selected=quote.get("currency") == "USD"),
                            Option("EUR", value="EUR", selected=quote.get("currency") == "EUR"),
                            name="currency",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    Div(
                        Label("Отсрочка платежа (дней)", style=label_style),
                        Input(name="payment_terms", type="number", value=str(quote.get("payment_terms", 30)), min="0",
                              style=input_style),
                        style=form_group_style
                    ),
                    Div(
                        Label("Срок поставки (дней)", style=label_style),
                        Input(name="delivery_days", type="number", value=str(quote.get("delivery_days", 45)), min="0",
                              style=input_style),
                        style=form_group_style
                    ),
                    Div(
                        Label("Срок действия КП (дней)", style=label_style),
                        Input(name="validity_days", type="number", value=str(quote.get("validity_days", 30)), min="1",
                              style=input_style),
                        style=form_group_style
                    ),
                    style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 20px;"
                ),
                Div(
                    Label("Примечания", style=label_style),
                    Textarea(quote.get("notes", "") or "", name="notes", rows="3",
                             style=f"{input_style} resize: vertical; min-height: 80px;"),
                    style=form_group_style
                ),
                style=form_card_style
            ),

            # Action buttons
            Div(
                Button(icon("check", size=14), " Сохранить", type="submit",
                       style="padding: 10px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/quotes/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                Button(icon("trash-2", size=14), " Удалить КП", type="button",
                       hx_delete=f"/quotes/{quote_id}",
                       hx_confirm="Вы уверены, что хотите удалить это КП?",
                       style="padding: 10px 20px; background: #fee2e2; color: #dc2626; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px; margin-left: auto;"),
                style="display: flex; gap: 12px; padding: 20px 0;"
            ),
            method="post",
            action=f"/quotes/{quote_id}/edit"
        ),

        session=session
    )


# @rt("/quotes/{quote_id}/edit")
def post(quote_id: str, customer_id: str, status: str, currency: str, delivery_terms: str,
         payment_terms: int, delivery_days: int, notes: str,
         delivery_city: str = None, delivery_country: str = None, delivery_method: str = None,
         delivery_priority: str = None, seller_company_id: str = None,
         contact_person_id: str = None, validity_days: int = 30, session=None):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    try:
        update_data = {
            "customer_id": customer_id,
            "status": status,
            "currency": currency,
            "delivery_terms": delivery_terms,
            "payment_terms": payment_terms,
            "delivery_days": delivery_days,
            "validity_days": validity_days,
            "notes": notes or None,
            "updated_at": datetime.now().isoformat()
        }

        # Add delivery location if provided
        if delivery_city and delivery_city.strip():
            update_data["delivery_city"] = delivery_city.strip()
        else:
            update_data["delivery_city"] = None

        if delivery_country and delivery_country.strip():
            update_data["delivery_country"] = delivery_country.strip()
        else:
            update_data["delivery_country"] = None

        if delivery_method and delivery_method.strip():
            update_data["delivery_method"] = delivery_method.strip()
        else:
            update_data["delivery_method"] = None

        if delivery_priority and delivery_priority.strip():
            update_data["delivery_priority"] = delivery_priority.strip()
        else:
            update_data["delivery_priority"] = None

        # v3.0: seller_company_id at quote level
        # If provided and not empty, set it; otherwise keep existing or set to None
        if seller_company_id and seller_company_id.strip():
            update_data["seller_company_id"] = seller_company_id.strip()
        else:
            update_data["seller_company_id"] = None

        # Contact person (ЛПР)
        if contact_person_id and contact_person_id.strip():
            update_data["contact_person_id"] = contact_person_id.strip()
        else:
            update_data["contact_person_id"] = None

        supabase.table("quotes").update(update_data) \
            .eq("id", quote_id) \
            .eq("organization_id", user["org_id"]) \
            .execute()

        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    except Exception as e:
        return page_layout("Error",
            Div(f"Error: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}/edit"),
            session=session
        )


# @rt("/quotes/{quote_id}")
def delete(quote_id: str, session):
    redirect = require_login(session)
    if redirect:
        return ""

    user = session["user"]
    supabase = get_supabase()

    try:
        # Delete quote items first
        supabase.table("quote_items").delete().eq("quote_id", quote_id).execute()
        # Delete quote
        supabase.table("quotes").delete().eq("id", quote_id).eq("organization_id", user["org_id"]).execute()
        # Redirect to quotes list
        return RedirectResponse("/quotes", status_code=303)
    except Exception as e:
        return Div(f"Error: {str(e)}", cls="alert alert-error")


# ============================================================================
# CUSTOMER DETAIL/EDIT
# ============================================================================

# REMOVED: Old customer detail route - replaced by enhanced version at line ~15609
# This old route was causing routing conflicts preventing /customers/{customer_id}/contacts/new from working


    # REMOVED: GET/POST /customers/{customer_id}/edit routes
    # Customer detail page (/customers/{customer_id}) has inline editing for all fields.




# ============================================================================
# AREA 1 continued — /quotes preview/calculate/documents/versions/exports
# Extracted from main.py lines 9987-12316.
# Note: render_preview_panel (below) is an exclusive HTMX preview helper;
# all preceding calc helpers (build_calculation_inputs, resolve_vat_zone
# etc.) stay in main.py because api/quotes.py imports them.
# ============================================================================


def render_preview_panel(results: List, items: List[Dict], currency: str) -> str:
    """Render the preview panel HTML for HTMX."""
    if not results:
        return Div(P("Add products to preview calculation."), cls="alert alert-info", id="preview-panel")

    # Calculate totals
    total_purchase = sum(safe_decimal(r.purchase_price_total_quote_currency) for r in results)
    total_logistics = sum(safe_decimal(r.logistics_total) for r in results)
    total_cogs = sum(safe_decimal(r.cogs_per_product) for r in results)
    total_profit = sum(safe_decimal(r.profit) for r in results)
    total_no_vat = sum(safe_decimal(r.sales_price_total_no_vat) for r in results)
    total_with_vat = sum(safe_decimal(r.sales_price_total_with_vat) for r in results)

    avg_margin = (total_profit / total_cogs * 100) if total_cogs else Decimal("0")

    # Build product rows for preview
    product_rows = []
    for item, result in zip(items, results):
        product_rows.append(
            Tr(
                Td(item.get('product_name', 'Product')[:30]),
                Td(str(item.get('quantity', 1))),
                Td(format_money(result.sales_price_per_unit_no_vat, currency)),
                Td(format_money(result.sales_price_total_with_vat, currency)),
                Td(format_money(result.profit, currency)),
            )
        )

    return Div(
        H3("Preview (not saved)"),

        # Summary stats
        Div(
            Div(
                Div("Total (excl VAT)", style="font-size: 0.875rem; color: #666;"),
                Div(format_money(total_no_vat, currency), cls="stat-value", style="font-size: 1.5rem;"),
                cls="stat-card"
            ),
            Div(
                Div("Total (incl VAT)", style="font-size: 0.875rem; color: #666;"),
                Div(format_money(total_with_vat, currency), cls="stat-value", style="font-size: 1.5rem; color: #28a745;"),
                cls="stat-card"
            ),
            Div(
                Div("Profit", style="font-size: 0.875rem; color: #666;"),
                Div(format_money(total_profit, currency), cls="stat-value", style="font-size: 1.5rem;"),
                cls="stat-card"
            ),
            Div(
                Div("Avg Margin", style="font-size: 0.875rem; color: #666;"),
                Div(f"{avg_margin:.1f}%", cls="stat-value", style="font-size: 1.5rem;"),
                cls="stat-card"
            ),
            cls="stats-grid", style="margin-bottom: 1rem;"
        ),

        # Cost breakdown
        Table(
            Thead(Tr(Th("Product"), Th("Qty"), Th("Unit Price"), Th("Total"), Th("Profit"))),
            Tbody(*product_rows),
            Tfoot(
                Tr(
                    Td(Strong("TOTAL"), colspan="3"),
                    Td(Strong(format_money(total_with_vat, currency))),
                    Td(Strong(format_money(total_profit, currency))),
                )
            ),
            style="font-size: 0.875rem;"
        ),

        id="preview-panel",
        style="background: #f0fff0; border: 2px solid #28a745; padding: 1rem; border-radius: 8px;"
    )


# ============================================================================
# HTMX LIVE PREVIEW ROUTE
# ============================================================================

# @rt("/quotes/{quote_id}/preview")
def post(
    quote_id: str,
    session,
    # Company settings
    seller_company: str = "МАСТЕР БЭРИНГ ООО",
    offer_sale_type: str = "поставка",
    offer_incoterms: str = "DDP",
    # Pricing (note: 'currency' matches form field name)
    currency: str = "RUB",
    markup: str = "15",
    supplier_discount: str = "0",
    exchange_rate: str = "1.0",
    delivery_time: str = "30",
    # Logistics
    logistics_supplier_hub: str = "0",
    logistics_hub_customs: str = "0",
    logistics_customs_client: str = "0",
    # Brokerage (values and currencies)
    brokerage_hub: str = "0",
    brokerage_hub_currency: str = "RUB",
    brokerage_customs: str = "0",
    brokerage_customs_currency: str = "RUB",
    warehousing_at_customs: str = "0",
    warehousing_at_customs_currency: str = "RUB",
    customs_documentation: str = "0",
    customs_documentation_currency: str = "RUB",
    brokerage_extra: str = "0",
    brokerage_extra_currency: str = "RUB",
    # Payment terms
    advance_from_client: str = "100",
    advance_to_supplier: str = "100",
    time_to_advance: str = "0",
    time_to_advance_on_receiving: str = "0",
    # DM Fee
    dm_fee_type: str = "fixed",
    dm_fee_value: str = "0",
    dm_fee_currency: str = "USD",
):
    """HTMX endpoint - returns preview panel only (no DB save)."""
    redirect = require_login(session)
    if redirect:
        return HTMLResponse("Unauthorized", status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Get quote
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return Div("Quote not found", cls="alert alert-error", id="preview-panel")

    quote = quote_result.data[0]
    # Note: 'currency' comes from form parameter (user's selection)
    # Don't override with quote.get("currency")

    # Get items via composition_service (Phase 5b): overlays purchase price
    # fields from invoice_item_prices when the item has an active composition
    # pointer, otherwise returns the quote_items row unchanged. The dict shape
    # is identical to a plain quote_items SELECT, so build_calculation_inputs()
    # sees no difference.
    items = get_composed_items(quote_id, supabase)

    if not items:
        return Div("Add products to preview.", cls="alert alert-info", id="preview-panel")

    # Validate that all available items have prices before calculation
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
        missing_list = Ul(
            *[Li(name, style="margin-bottom: 4px;") for name in items_without_price],
            style="margin: 12px 0; padding-left: 20px;"
        )
        return Div(
            P(Strong("Не все позиции имеют цену."), style="margin-bottom: 8px;"),
            P("Заполните цены в разделе закупок перед расчётом."),
            P(f"Позиции без цены ({len(items_without_price)}):", style="margin-bottom: 4px; color: #64748b;"),
            missing_list,
            cls="alert alert-error", id="preview-panel"
        )

    try:
        # Aggregate delivery time from items (production_time_days) and invoices (logistics_total_days)
        max_production_days = max((item.get("production_time_days") or 0) for item in items) if items else 0

        invoices_days_result = supabase.table("invoices") \
            .select("logistics_total_days") \
            .eq("quote_id", quote_id) \
            .execute()
        max_logistics_days = max((inv.get("logistics_total_days") or 0) for inv in (invoices_days_result.data or [])) if invoices_days_result.data else 0

        aggregated_delivery_time = max_logistics_days + max_production_days
        form_delivery_time = safe_int(delivery_time)
        effective_delivery_time = max(aggregated_delivery_time, form_delivery_time)

        # ==========================================================================
        # STORE VALUES IN ORIGINAL CURRENCY (no conversion on save)
        # Conversion to USD happens only in build_calculation_inputs() before calculation
        # ==========================================================================

        # Build variables from form parameters
        variables = {
            'currency_of_quote': currency,
            'markup': safe_decimal(markup),
            'supplier_discount': safe_decimal(supplier_discount),
            'offer_incoterms': offer_incoterms,
            'delivery_time': effective_delivery_time,  # Uses MAX(logistics_days + production_days) if greater
            'seller_company': seller_company,
            'offer_sale_type': offer_sale_type,

            # Logistics (stored in USD - aggregated from invoices which are already converted)
            'logistics_supplier_hub': safe_decimal(logistics_supplier_hub),
            'logistics_hub_customs': safe_decimal(logistics_hub_customs),
            'logistics_customs_client': safe_decimal(logistics_customs_client),

            # Brokerage (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
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

            # Payment terms
            'advance_from_client': safe_decimal(advance_from_client),
            'advance_to_supplier': safe_decimal(advance_to_supplier),
            'time_to_advance': safe_int(time_to_advance),
            'time_to_advance_on_receiving': safe_int(time_to_advance_on_receiving),

            # DM Fee (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
            'dm_fee_type': dm_fee_type,
            'dm_fee_value': safe_decimal(dm_fee_value),
            'dm_fee_currency': dm_fee_currency,

            # Exchange rate
            'exchange_rate': safe_decimal(exchange_rate),
        }

        # Build calculation inputs
        calc_inputs = build_calculation_inputs(items, variables)

        # Run calculation (in memory, no save)
        results = calculate_multiproduct_quote(calc_inputs)

        # Return preview panel
        return render_preview_panel(results, items, currency)

    except Exception as e:
        return Div(f"Preview error: {str(e)}", cls="alert alert-error", id="preview-panel")


# ============================================================================
# CALCULATION PAGE (GET) - Enhanced with all variables
# ============================================================================

# @rt("/quotes/{quote_id}/calculate")
def get(quote_id: str, session):
    """Calculate quote using the 13-phase calculation engine with HTMX live preview."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote with customer (v3.0 - fetch seller company separately to avoid FK issues)
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = quote_result.data[0]
    currency = quote.get("currency", "USD")

    # Get seller company info separately using service function
    from services.seller_company_service import get_seller_company
    seller_company_info = None
    seller_company_display = "Не выбрана"
    seller_company_name = ""
    if quote.get("seller_company_id"):
        seller_company = get_seller_company(quote["seller_company_id"])
        if seller_company:
            seller_company_info = {"id": seller_company.id, "supplier_code": seller_company.supplier_code, "name": seller_company.name}
            seller_company_display = f"{seller_company.supplier_code} - {seller_company.name}"
            seller_company_name = seller_company.name

    # Get quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    if not items:
        return page_layout("Невозможно рассчитать",
            H1("Нет позиций"),
            P("Добавьте товары в КП перед расчётом."),
            A("Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Try to load existing calculation variables
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    saved_vars = vars_result.data[0]["variables"] if vars_result.data else {}

    # NOTE: Monetary values (brokerage, DM fee) are now stored in ORIGINAL currency
    # No back-conversion needed for display - values are shown as entered

    # ==========================================================================
    # AGGREGATE LOGISTICS FROM INVOICES (with multi-currency support)
    # Logistics costs are entered per-invoice by logistics department
    # Each segment may have different currency - convert all to QUOTE CURRENCY before summing
    # The calculation engine expects logistics values in quote currency, not USD
    # ==========================================================================
    invoices_result = supabase.table("invoices") \
        .select("logistics_supplier_to_hub, logistics_hub_to_customs, logistics_customs_to_customer, "
                "logistics_supplier_to_hub_currency, logistics_hub_to_customs_currency, logistics_customs_to_customer_currency") \
        .eq("quote_id", quote_id) \
        .execute()

    invoices_logistics = invoices_result.data or []

    # Sum logistics costs from all invoices, converting each to USD (standard storage currency)
    # Conversion to quote currency happens only at export time (single point of conversion)
    from services.currency_service import convert_amount
    total_logistics_supplier_hub = Decimal(0)
    total_logistics_hub_customs = Decimal(0)
    total_logistics_customs_client = Decimal(0)

    for inv in invoices_logistics:
        # Supplier → Hub - convert to USD
        s2h_amount = Decimal(str(inv.get("logistics_supplier_to_hub") or 0))
        s2h_currency = inv.get("logistics_supplier_to_hub_currency") or "USD"
        if s2h_amount > 0:
            total_logistics_supplier_hub += convert_amount(s2h_amount, s2h_currency, "USD")

        # Hub → Customs - convert to USD
        h2c_amount = Decimal(str(inv.get("logistics_hub_to_customs") or 0))
        h2c_currency = inv.get("logistics_hub_to_customs_currency") or "USD"
        if h2c_amount > 0:
            total_logistics_hub_customs += convert_amount(h2c_amount, h2c_currency, "USD")

        # Customs → Customer - convert to USD
        c2c_amount = Decimal(str(inv.get("logistics_customs_to_customer") or 0))
        c2c_currency = inv.get("logistics_customs_to_customer_currency") or "USD"
        if c2c_amount > 0:
            total_logistics_customs_client += convert_amount(c2c_amount, c2c_currency, "USD")

    # Convert to float for downstream compatibility
    total_logistics_supplier_hub = float(total_logistics_supplier_hub)
    total_logistics_hub_customs = float(total_logistics_hub_customs)
    total_logistics_customs_client = float(total_logistics_customs_client)

    # Use aggregated values from invoices as defaults
    # Override saved_vars if: aggregated > 0 AND (saved is missing or saved is 0)
    # This ensures invoice-level logistics data flows to calculation
    saved_supplier_hub = float(saved_vars.get("logistics_supplier_hub", 0) or 0)
    saved_hub_customs = float(saved_vars.get("logistics_hub_customs", 0) or 0)
    saved_customs_client = float(saved_vars.get("logistics_customs_client", 0) or 0)

    if total_logistics_supplier_hub > 0 and saved_supplier_hub == 0:
        saved_vars["logistics_supplier_hub"] = total_logistics_supplier_hub
    if total_logistics_hub_customs > 0 and saved_hub_customs == 0:
        saved_vars["logistics_hub_customs"] = total_logistics_hub_customs
    if total_logistics_customs_client > 0 and saved_customs_client == 0:
        saved_vars["logistics_customs_client"] = total_logistics_customs_client

    # Default values (with saved values taking precedence)
    def get_var(key, default):
        return saved_vars.get(key, default)

    # Check for partial recalculation
    partial_recalc = quote.get("partial_recalc")

    # Check existing versions and workflow status for version dialog
    existing_versions = list_quote_versions(quote_id, user["org_id"])
    workflow_status = quote.get("workflow_status", "draft")
    can_update, update_reason = can_update_version(quote_id, user["org_id"])
    current_version = get_current_quote_version(quote_id, user["org_id"]) if existing_versions else None
    current_version_num = current_version.get("version_number", 1) if current_version else 0

    # ==========================================================================
    # COMPACT CALCULATE PAGE STYLING (Logistics-inspired design)
    # ==========================================================================
    # Inline styles for compact logistics-style layout
    card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 16px;
        margin-bottom: 12px;
    """
    label_style = "font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;"
    input_row_style = "display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9;"
    input_row_last_style = "display: flex; align-items: center; padding: 8px 0;"
    input_style = "width: 100px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    input_wide_style = "width: 140px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    select_style = "width: 120px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    select_currency_style = "width: 70px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    section_title_style = "font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; display: flex; align-items: center; gap: 6px;"
    field_label_style = "font-size: 13px; color: #64748b; width: 140px; font-weight: 500;"
    value_style = "font-size: 14px; font-weight: 600; color: #1e40af;"

    # Build seller company display
    seller_company_hidden = Input(type="hidden", name="seller_company", value=seller_company_name if seller_company_info else "")
    if seller_company_info:
        seller_display = Span(seller_company_display, style="font-weight: 600; color: #1e40af;")
    else:
        seller_display = Span("Не выбрана", style="color: #d97706; font-weight: 500;")

    return page_layout(f"Calculate - {quote.get('idn_quote', '')}",
        # Compact header
        Div(
            Div(
                icon("calculator", size=20),
                Span(f"Расчёт {quote.get('idn_quote', '')}", style="font-size: 1.25rem; font-weight: 600; margin-left: 8px;"),
                style="display: flex; align-items: center;"
            ),
            Div(
                Span(quote.get('customers', {}).get('name', '—') if quote.get('customers') else '—', style="font-weight: 500;"),
                Span(" • ", style="color: #94a3b8;"),
                Span(f"{currency}", style="color: #3b82f6; font-weight: 600;"),
                Span(" • ", style="color: #94a3b8;"),
                Span(f"{len(items)} поз.", style="color: #64748b;"),
                style="font-size: 13px; margin-top: 4px;"
            ),
            style="margin-bottom: 16px;"
        ),

        # Partial recalculation banner
        Div(
            icon("refresh-cw", size=16),
            Span(" Частичный пересчёт: только наценка", style="font-weight: 600; margin-left: 6px;"),
            Span(" — данные закупки, логистики и таможни сохранены", style="font-size: 12px; color: #065f46; margin-left: 8px;"),
            style="background: linear-gradient(90deg, #dcfce7 0%, #f0fdf4 100%); border: 1px solid #86efac; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; display: flex; align-items: center; color: #166534;"
        ) if partial_recalc == "price" else None,

        # Main form with HTMX live preview
        Form(
            Div(
                # Left column: Compact form cards
                Div(
                    # === COMPANY & PRICING CARD (Combined) ===
                    Div(
                        # Section: Company
                        Div(
                            Span(icon("building-2", size=14), style="color: #64748b;"),
                            Span("Компания и условия", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        # Row: Seller Company
                        Div(
                            Span("Продавец", style=field_label_style),
                            seller_display,
                            A("изменить", href=f"/quotes/{quote_id}/edit", style="font-size: 11px; margin-left: 8px; color: #94a3b8;"),
                            seller_company_hidden,
                            style=input_row_style
                        ),
                        # Row: Sale Type + Incoterms
                        Div(
                            Span("Тип сделки", style=field_label_style),
                            Select(
                                Option("Поставка", value="поставка", selected=True),
                                Option("Транзит", value="транзит"),
                                name="offer_sale_type",
                                style=select_style
                            ),
                            Span("Incoterms", style=f"{field_label_style} margin-left: 20px; width: 80px;"),
                            Select(
                                Option("DDP", value="DDP", selected=get_var('offer_incoterms', 'DDP') == "DDP"),
                                Option("DAP", value="DAP", selected=get_var('offer_incoterms', '') == "DAP"),
                                Option("CIF", value="CIF", selected=get_var('offer_incoterms', '') == "CIF"),
                                Option("FOB", value="FOB", selected=get_var('offer_incoterms', '') == "FOB"),
                                Option("EXW", value="EXW", selected=get_var('offer_incoterms', '') == "EXW"),
                                name="offer_incoterms",
                                style="width: 80px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
                            ),
                            style=input_row_style
                        ),

                        # Divider
                        Div(style="height: 1px; background: #e2e8f0; margin: 12px 0;"),

                        # Section: Pricing
                        Div(
                            Span(icon("percent", size=14), style="color: #64748b;"),
                            Span("Цена и наценка", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        # Row: Currency + Markup
                        Div(
                            Span("Валюта КП", style=field_label_style),
                            Select(
                                Option("RUB", value="RUB", selected=currency == "RUB"),
                                Option("USD", value="USD", selected=currency == "USD"),
                                Option("EUR", value="EUR", selected=currency == "EUR"),
                                Option("CNY", value="CNY", selected=currency == "CNY"),
                                name="currency",
                                style=select_currency_style
                            ),
                            Span("Наценка", style=f"{field_label_style} margin-left: 20px; width: 80px;"),
                            Input(name="markup", type="number", value=str(get_var('markup', 15)), min="0", max="100", step="0.1",
                                  style="width: 70px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("%", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            style=input_row_last_style
                        ),

                        # Hidden fields
                        Input(type="hidden", name="supplier_discount", value=str(get_var('supplier_discount', 0))),
                        Input(type="hidden", name="exchange_rate", value=str(get_var('exchange_rate', 1.0))),
                        Input(type="hidden", name="delivery_time", value=str(get_var('delivery_time', 30))),
                        Input(type="hidden", name="logistics_supplier_hub", value=str(get_var('logistics_supplier_hub', 0))),
                        Input(type="hidden", name="logistics_hub_customs", value=str(get_var('logistics_hub_customs', 0))),
                        Input(type="hidden", name="logistics_customs_client", value=str(get_var('logistics_customs_client', 0))),
                        Input(type="hidden", name="brokerage_hub", value=str(get_var('brokerage_hub', 0))),
                        Input(type="hidden", name="brokerage_hub_currency", value=str(get_var('brokerage_hub_currency', 'RUB'))),
                        Input(type="hidden", name="brokerage_customs", value=str(get_var('brokerage_customs', 0))),
                        Input(type="hidden", name="brokerage_customs_currency", value=str(get_var('brokerage_customs_currency', 'RUB'))),
                        Input(type="hidden", name="warehousing_at_customs", value=str(get_var('warehousing_at_customs', 0))),
                        Input(type="hidden", name="warehousing_at_customs_currency", value=str(get_var('warehousing_at_customs_currency', 'RUB'))),
                        Input(type="hidden", name="customs_documentation", value=str(get_var('customs_documentation', 0))),
                        Input(type="hidden", name="customs_documentation_currency", value=str(get_var('customs_documentation_currency', 'RUB'))),
                        Input(type="hidden", name="brokerage_extra", value=str(get_var('brokerage_extra', 0))),
                        Input(type="hidden", name="brokerage_extra_currency", value=str(get_var('brokerage_extra_currency', 'RUB'))),
                        Input(type="hidden", name="advance_to_supplier", value=str(get_var('advance_to_supplier', 100))),

                        style=card_style
                    ),

                    # === PAYMENT TERMS CARD ===
                    Div(
                        Div(
                            Span(icon("credit-card", size=14), style="color: #64748b;"),
                            Span("Условия оплаты", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        # Row: All payment fields inline
                        Div(
                            Span("Аванс клиента", style=field_label_style),
                            Input(name="advance_from_client", type="number", value=str(get_var('advance_from_client', 100)), min="0", max="100", step="1",
                                  style="width: 60px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("%", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            style=input_row_style
                        ),
                        Div(
                            Span("До аванса", style=field_label_style),
                            Input(name="time_to_advance", type="number", value=str(get_var('time_to_advance', 0)), min="0",
                                  style="width: 60px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("дн.", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            Span("До расчёта", style=f"{field_label_style} margin-left: 20px; width: 80px;"),
                            Input(name="time_to_advance_on_receiving", type="number", value=str(get_var('time_to_advance_on_receiving', 0)), min="0",
                                  style="width: 60px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("дн.", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            style=input_row_last_style
                        ),
                        style=card_style
                    ),

                    # === DM FEE CARD ===
                    Div(
                        Div(
                            Span(icon("award", size=14), style="color: #64748b;"),
                            Span("Вознаграждение (LPR)", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        Div(
                            Span("Тип", style=field_label_style),
                            Select(
                                Option("Фикс.", value="fixed", selected=get_var('dm_fee_type', 'fixed') == "fixed"),
                                Option("%", value="percentage", selected=get_var('dm_fee_type', '') == "percentage"),
                                name="dm_fee_type",
                                style="width: 70px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
                            ),
                            Span("Сумма", style=f"{field_label_style} margin-left: 16px; width: 60px;"),
                            Input(name="dm_fee_value", type="number", value=str(get_var('dm_fee_value', 0)), min="0", step="0.01",
                                  style="width: 80px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Select(
                                Option("RUB", value="RUB", selected=get_var('dm_fee_currency', 'RUB') == "RUB"),
                                Option("USD", value="USD", selected=get_var('dm_fee_currency', '') == "USD"),
                                Option("EUR", value="EUR", selected=get_var('dm_fee_currency', '') == "EUR"),
                                name="dm_fee_currency",
                                style="width: 65px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; margin-left: 4px;"
                            ),
                            style=input_row_last_style
                        ),
                        Span("Для % — валюта = валюте КП", style="font-size: 11px; color: #94a3b8; margin-top: 4px; display: block;"),
                        style=card_style
                    ),

                    style="flex: 1; min-width: 380px; max-width: 550px;"
                ),

                # Right column: Preview
                Div(
                    Div(
                        Div(
                            Span(icon("eye", size=14), style="color: #64748b;"),
                            Span("Предпросмотр", style="font-size: 13px; font-weight: 600; color: #374151; margin-left: 6px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        Span("Автообновление при изменении полей", style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 12px;"),
                        Div(
                            P("Введите данные слева для расчёта", style="margin: 0; font-size: 13px;"),
                            style="background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%); padding: 12px; border-radius: 8px; color: #1e40af;",
                            id="preview-panel"
                        ),
                        btn("Обновить", variant="secondary", icon_name="refresh-cw", type="button", size="sm",
                            hx_post=f"/quotes/{quote_id}/preview",
                            hx_target="#preview-panel",
                            hx_include="closest form",
                            style="margin-top: 12px;"
                        ),
                        style=f"{card_style} position: sticky; top: 16px;"
                    ),
                    style="flex: 1; min-width: 320px;"
                ),

                style="display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start;"
            ),

            # Hidden fields for version handling
            Input(type="hidden", name="version_action", id="version_action", value="new" if existing_versions else "auto"),
            Input(type="hidden", name="change_reason", id="change_reason", value=""),

            # Version dialog (shown only if versions exist)
            Div(
                Div(
                    # Dialog header
                    Div(
                        icon("git-branch", size=20),
                        Span("Сохранение версии", style="font-size: 16px; font-weight: 600; margin-left: 8px;"),
                        style="display: flex; align-items: center; margin-bottom: 16px;"
                    ),
                    # Current version info
                    Div(
                        Span(f"Текущая версия: v{current_version_num}", style="font-weight: 500;"),
                        style="margin-bottom: 12px; color: #64748b;"
                    ) if current_version_num > 0 else None,
                    # Options
                    Div(
                        # Update option (only if allowed)
                        Div(
                            Input(type="radio", name="version_choice", value="update", id="version_update",
                                  disabled=not can_update,
                                  style="margin-right: 8px;"),
                            Label(
                                f"Обновить версию v{current_version_num}",
                                fr="version_update",
                                style="cursor: pointer;" if can_update else "cursor: not-allowed; color: #9ca3af;"
                            ),
                            Span(" (не создавать новую)", style="font-size: 12px; color: #64748b;"),
                            style="margin-bottom: 8px;"
                        ) if can_update else Div(
                            icon("lock", size=14),
                            Span(update_reason, style="font-size: 13px; color: #dc2626; margin-left: 6px;"),
                            style="display: flex; align-items: center; margin-bottom: 12px; padding: 8px 12px; background: #fef2f2; border-radius: 6px; border: 1px solid #fecaca;"
                        ),
                        # New version option
                        Div(
                            Input(type="radio", name="version_choice", value="new", id="version_new", checked=True,
                                  style="margin-right: 8px;"),
                            Label(
                                f"Создать версию v{current_version_num + 1}",
                                fr="version_new",
                                style="cursor: pointer; font-weight: 500;"
                            ),
                            style="margin-bottom: 12px;"
                        ),
                        style="margin-bottom: 16px;"
                    ),
                    # Change reason (optional)
                    Div(
                        Label("Причина изменения (опционально):", style="font-size: 13px; color: #64748b; display: block; margin-bottom: 6px;"),
                        Input(type="text", id="change_reason_input", placeholder="Скидка по запросу клиента",
                              style="width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;"),
                        style="margin-bottom: 20px;"
                    ),
                    # Dialog buttons
                    Div(
                        Button("Сохранить", type="button", id="version_dialog_save",
                               style="padding: 10px 24px; background: #10b981; color: white; border: none; border-radius: 6px; font-weight: 500; cursor: pointer;"),
                        Button("Отмена", type="button", id="version_dialog_cancel",
                               style="padding: 10px 24px; background: #f1f5f9; color: #374151; border: 1px solid #e2e8f0; border-radius: 6px; margin-left: 8px; cursor: pointer;"),
                        style="display: flex; justify-content: flex-end;"
                    ),
                    style="background: white; padding: 24px; border-radius: 12px; max-width: 420px; width: 90%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);"
                ),
                id="version_dialog",
                style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.5); z-index: 1000; justify-content: center; align-items: center;"
            ) if existing_versions else None,

            # Actions - compact
            Div(
                btn("Сохранить расчёт", variant="success", icon_name="check", type="button" if existing_versions else "submit",
                    id="save_calc_btn", onclick="showVersionDialog()" if existing_versions else None),
                btn_link("Отмена", href=f"/quotes/{quote_id}", variant="ghost"),
                style="display: flex; gap: 12px; margin-top: 16px; padding: 12px 16px; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 10px; border: 1px solid #e2e8f0;"
            ),

            # JavaScript for version dialog
            Script(f"""
                function showVersionDialog() {{
                    document.getElementById('version_dialog').style.display = 'flex';
                }}

                document.addEventListener('DOMContentLoaded', function() {{
                    var dialog = document.getElementById('version_dialog');
                    var saveBtn = document.getElementById('version_dialog_save');
                    var cancelBtn = document.getElementById('version_dialog_cancel');
                    var form = document.querySelector('form[action="/quotes/{quote_id}/calculate"]');

                    if (cancelBtn) {{
                        cancelBtn.addEventListener('click', function() {{
                            dialog.style.display = 'none';
                        }});
                    }}

                    if (saveBtn) {{
                        saveBtn.addEventListener('click', function() {{
                            // Get selected version action
                            var versionChoice = document.querySelector('input[name="version_choice"]:checked');
                            if (versionChoice) {{
                                document.getElementById('version_action').value = versionChoice.value;
                            }}
                            // Get change reason
                            var changeReason = document.getElementById('change_reason_input');
                            if (changeReason) {{
                                document.getElementById('change_reason').value = changeReason.value;
                            }}
                            // Submit the form
                            dialog.style.display = 'none';
                            form.submit();
                        }});
                    }}

                    // Close dialog on backdrop click
                    if (dialog) {{
                        dialog.addEventListener('click', function(e) {{
                            if (e.target === dialog) {{
                                dialog.style.display = 'none';
                            }}
                        }});
                    }}
                }});
            """) if existing_versions else None,

            method="post",
            action=f"/quotes/{quote_id}/calculate",
            hx_post=f"/quotes/{quote_id}/preview",
            hx_target="#preview-panel",
            hx_trigger="input changed delay:500ms from:find input, input changed delay:500ms from:find select"
        ),

        session=session
    )


# @rt("/quotes/{quote_id}/calculate")
def post(
    quote_id: str,
    session,
    # Company settings
    seller_company: str = "МАСТЕР БЭРИНГ ООО",
    offer_sale_type: str = "поставка",
    offer_incoterms: str = "DDP",
    # Pricing (note: 'currency' matches form field name)
    currency: str = "RUB",
    markup: str = "15",
    supplier_discount: str = "0",
    exchange_rate: str = "1.0",
    delivery_time: str = "30",
    # Version handling (new fields)
    version_action: str = "auto",  # "auto", "update", "new"
    change_reason: str = "",
    # Logistics
    logistics_supplier_hub: str = "0",
    logistics_hub_customs: str = "0",
    logistics_customs_client: str = "0",
    # Brokerage (values and currencies)
    brokerage_hub: str = "0",
    brokerage_hub_currency: str = "RUB",
    brokerage_customs: str = "0",
    brokerage_customs_currency: str = "RUB",
    warehousing_at_customs: str = "0",
    warehousing_at_customs_currency: str = "RUB",
    customs_documentation: str = "0",
    customs_documentation_currency: str = "RUB",
    brokerage_extra: str = "0",
    brokerage_extra_currency: str = "RUB",
    # Payment terms
    advance_from_client: str = "100",
    advance_to_supplier: str = "100",
    time_to_advance: str = "0",
    time_to_advance_on_receiving: str = "0",
    # DM Fee
    dm_fee_type: str = "fixed",
    dm_fee_value: str = "0",
    dm_fee_currency: str = "RUB",
):
    """Execute full 13-phase calculation engine and save results."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote with items
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Error", Div("Quote not found", cls="alert alert-error"), session=session)

    quote = quote_result.data[0]
    # Note: 'currency' comes from form parameter (user's selection on calculate page)
    # Don't override with quote.get("currency") - the form value is what user wants

    # Get items via composition_service (Phase 5b): overlays purchase price
    # fields from invoice_item_prices when the item has an active composition
    # pointer, otherwise returns the quote_items row unchanged. The dict shape
    # is identical to a plain quote_items SELECT, so build_calculation_inputs()
    # sees no difference.
    items = get_composed_items(quote_id, supabase)

    if not items:
        return page_layout("Error",
            Div("Cannot calculate - no products in quote", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Validate that all available items have prices before calculation
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
        missing_list = Ul(
            *[Li(name, style="margin-bottom: 4px;") for name in items_without_price],
            style="margin: 12px 0; padding-left: 20px;"
        )
        return page_layout("Ошибка расчёта",
            Div(
                P(Strong("Не все позиции имеют цену. Заполните цены в разделе закупок перед расчётом."),
                  style="margin-bottom: 8px;"),
                P(f"Позиции без цены ({len(items_without_price)}):", style="margin-bottom: 4px; color: #64748b;"),
                missing_list,
                cls="alert alert-error"
            ),
            A("← Назад к КП", href=f"/quotes/{quote_id}", style="display: inline-block; margin-top: 12px;"),
            session=session
        )

    try:
        # ==========================================================================
        # AGGREGATE LOGISTICS FROM INVOICES (if form values are 0)
        # This ensures invoice-level logistics data flows to calculation even if
        # form fields weren't properly populated
        # ==========================================================================
        form_logistics_supplier_hub = safe_decimal(logistics_supplier_hub)
        form_logistics_hub_customs = safe_decimal(logistics_hub_customs)
        form_logistics_customs_client = safe_decimal(logistics_customs_client)

        print(f"[calc-debug] Form logistics values: S2H={logistics_supplier_hub}, H2C={logistics_hub_customs}, C2C={logistics_customs_client}")
        print(f"[calc-debug] Parsed form values: S2H={form_logistics_supplier_hub}, H2C={form_logistics_hub_customs}, C2C={form_logistics_customs_client}")

        # ==========================================================================
        # AGGREGATE DELIVERY TIME from invoices (logistics_total_days) + items (production_time_days)
        # ==========================================================================
        max_logistics_days = 0
        max_production_days = 0

        # Get max production_time_days from quote_items
        for item in items:
            prod_days = item.get("production_time_days") or 0
            if prod_days > max_production_days:
                max_production_days = prod_days

        # Get max logistics_total_days from invoices
        invoices_days_result = supabase.table("invoices") \
            .select("logistics_total_days") \
            .eq("quote_id", quote_id) \
            .execute()

        for inv in (invoices_days_result.data or []):
            log_days = inv.get("logistics_total_days") or 0
            if log_days > max_logistics_days:
                max_logistics_days = log_days

        # Calculate total delivery time
        aggregated_delivery_time = max_logistics_days + max_production_days
        form_delivery_time = safe_int(delivery_time)

        # Use aggregated value if it's greater than form value
        if aggregated_delivery_time > form_delivery_time:
            effective_delivery_time = aggregated_delivery_time
        else:
            effective_delivery_time = form_delivery_time

        print(f"[calc-debug] Delivery time: max_logistics={max_logistics_days}, max_production={max_production_days}, form={form_delivery_time}, effective={effective_delivery_time}")

        # ALWAYS aggregate logistics from invoices - invoices are the source of truth
        # (form values may be stale from previous calculations with different currency logic)
        print("[calc-debug] Aggregating logistics from invoices...")
        invoices_result = supabase.table("invoices") \
            .select("logistics_supplier_to_hub, logistics_hub_to_customs, logistics_customs_to_customer, "
                    "logistics_supplier_to_hub_currency, logistics_hub_to_customs_currency, logistics_customs_to_customer_currency") \
            .eq("quote_id", quote_id) \
            .execute()

        invoices_logistics = invoices_result.data or []

        # Import convert_amount for use in logistics aggregation and exchange rate calculation
        from services.currency_service import convert_amount

        if invoices_logistics:
            total_logistics_supplier_hub = Decimal(0)
            total_logistics_hub_customs = Decimal(0)
            total_logistics_customs_client = Decimal(0)

            print(f"[calc-debug] Quote currency: {currency}")
            print(f"[calc-debug] Found {len(invoices_logistics)} invoices with logistics data")
            print(f"[calc-debug] Converting all logistics to USD (standard storage currency)")

            for inv in invoices_logistics:
                # Supplier → Hub - convert to USD (standard storage currency)
                s2h_amount = Decimal(str(inv.get("logistics_supplier_to_hub") or 0))
                s2h_currency = inv.get("logistics_supplier_to_hub_currency") or "USD"
                if s2h_amount > 0:
                    converted = convert_amount(s2h_amount, s2h_currency, "USD")
                    print(f"[calc-debug] S2H: {s2h_amount} {s2h_currency} → {converted} USD")
                    total_logistics_supplier_hub += converted

                # Hub → Customs - convert to USD
                h2c_amount = Decimal(str(inv.get("logistics_hub_to_customs") or 0))
                h2c_currency = inv.get("logistics_hub_to_customs_currency") or "USD"
                if h2c_amount > 0:
                    converted = convert_amount(h2c_amount, h2c_currency, "USD")
                    print(f"[calc-debug] H2C: {h2c_amount} {h2c_currency} → {converted} USD")
                    total_logistics_hub_customs += converted

                # Customs → Customer - convert to USD
                c2c_amount = Decimal(str(inv.get("logistics_customs_to_customer") or 0))
                c2c_currency = inv.get("logistics_customs_to_customer_currency") or "USD"
                if c2c_amount > 0:
                    converted = convert_amount(c2c_amount, c2c_currency, "USD")
                    print(f"[calc-debug] C2C: {c2c_amount} {c2c_currency} → {converted} USD")
                    total_logistics_customs_client += converted

            # Use aggregated values (always override form values for logistics)
            print(f"[calc-debug] Aggregated logistics: S2H={total_logistics_supplier_hub}, H2C={total_logistics_hub_customs}, C2C={total_logistics_customs_client}")
            form_logistics_supplier_hub = total_logistics_supplier_hub
            form_logistics_hub_customs = total_logistics_hub_customs
            form_logistics_customs_client = total_logistics_customs_client
            print(f"[calc-debug] Final logistics values: S2H={form_logistics_supplier_hub}, H2C={form_logistics_hub_customs}, C2C={form_logistics_customs_client}")

        # ==========================================================================
        # STORE VALUES IN ORIGINAL CURRENCY (no conversion here)
        # Conversion to USD happens in build_calculation_inputs() before calculation
        # ==========================================================================
        print(f"[calc-debug] Brokerage (original): hub={brokerage_hub} {brokerage_hub_currency}, customs={brokerage_customs} {brokerage_customs_currency}")

        # Build variables from form parameters (store in ORIGINAL currency)
        variables = {
            'currency_of_quote': currency,
            'markup': safe_decimal(markup),
            'supplier_discount': safe_decimal(supplier_discount),
            'offer_incoterms': offer_incoterms,
            'delivery_time': effective_delivery_time,  # Uses MAX(logistics_days + production_days) if greater than form value
            'seller_company': seller_company,
            'offer_sale_type': offer_sale_type,

            # Logistics (stored in USD - aggregated from invoices which are already converted)
            'logistics_supplier_hub': form_logistics_supplier_hub,
            'logistics_hub_customs': form_logistics_hub_customs,
            'logistics_customs_client': form_logistics_customs_client,

            # Brokerage (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
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

            # Payment terms
            'advance_from_client': safe_decimal(advance_from_client),
            'advance_to_supplier': safe_decimal(advance_to_supplier),
            'time_to_advance': safe_int(time_to_advance),
            'time_to_advance_on_receiving': safe_int(time_to_advance_on_receiving),

            # DM Fee (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
            'dm_fee_type': dm_fee_type,
            'dm_fee_value': safe_decimal(dm_fee_value),
            'dm_fee_currency': dm_fee_currency,

            # Exchange rate
            'exchange_rate': safe_decimal(exchange_rate),
        }

        # Build calculation inputs for all items
        calc_inputs = build_calculation_inputs(items, variables)

        print(f"[calc-debug] Variables passed to calc: logistics_supplier_hub={variables['logistics_supplier_hub']}, logistics_hub_customs={variables['logistics_hub_customs']}, logistics_customs_client={variables['logistics_customs_client']}")
        print(f"[calc-debug] Brokerage: hub={variables['brokerage_hub']}, customs={variables['brokerage_customs']}, warehousing={variables['warehousing_at_customs']}, docs={variables['customs_documentation']}, extra={variables['brokerage_extra']}")

        # Run full 13-phase calculation engine
        results = calculate_multiproduct_quote(calc_inputs)

        # Calculate totals from results
        total_purchase = sum(safe_decimal(r.purchase_price_total_quote_currency) for r in results)
        total_logistics = sum(safe_decimal(r.logistics_total) for r in results)
        print(f"[calc-debug] Calc results: total_purchase={total_purchase}, total_logistics={total_logistics}")
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

        # Calculate exchange rate from quote currency to USD for analytics
        if currency == 'USD':
            exchange_rate_to_usd = Decimal("1.0")
        else:
            exchange_rate_to_usd = safe_decimal(convert_amount(Decimal("1"), currency, 'USD'))
            if exchange_rate_to_usd == 0:
                exchange_rate_to_usd = Decimal("1.0")  # Fallback

        # Calculate USD equivalents for analytics
        subtotal_usd = total_purchase * exchange_rate_to_usd
        total_amount_usd = total_with_vat * exchange_rate_to_usd
        total_profit_usd = total_profit * exchange_rate_to_usd

        # Update quote totals (only use columns that exist in quotes table)
        supabase.table("quotes").update({
            "subtotal": float(total_purchase),
            "total_amount": float(total_with_vat),
            "total_profit_usd": float(total_profit_usd),
            # Quote-currency totals (for display on summary tab)
            "total_quote_currency": float(total_with_vat),
            "revenue_no_vat_quote_currency": float(total_no_vat),
            "profit_quote_currency": float(total_profit),
            "cogs_quote_currency": float(total_cogs),
            # USD analytics columns
            "exchange_rate_to_usd": float(exchange_rate_to_usd),
            "subtotal_usd": float(subtotal_usd),
            "total_amount_usd": float(total_amount_usd),
            "updated_at": datetime.now().isoformat()
        }).eq("id", quote_id).execute()

        # Convert Decimal values to float for JSON storage
        variables_for_storage = {
            k: float(v) if isinstance(v, Decimal) else v
            for k, v in variables.items()
        }

        # Store calculation variables
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

        # Store per-item calculation results (as JSONB)
        for item, result in zip(items, results):
            # Build phase_results JSONB with all calculation outputs
            phase_results = {
                # Purchase prices
                "N16": float(result.purchase_price_no_vat or 0),
                "P16": float(result.purchase_price_after_discount or 0),
                "R16": float(result.purchase_price_per_unit_quote_currency or 0),
                "S16": float(result.purchase_price_total_quote_currency or 0),
                # Logistics
                "T16": float(result.logistics_first_leg or 0),
                "U16": float(result.logistics_last_leg or 0),
                "V16": float(result.logistics_total or 0),
                # Customs and taxes
                "Y16": float(result.customs_fee or 0),
                "Z16": float(result.excise_tax_amount or 0),
                # COGS
                "AA16": float(result.cogs_per_unit or 0),
                "AB16": float(result.cogs_per_product or 0),
                # Sale prices (excl financial)
                "AD16": float(result.sale_price_per_unit_excl_financial or 0),
                "AE16": float(result.sale_price_total_excl_financial or 0),
                # Profit and fees
                "AF16": float(result.profit or 0),
                "AG16": float(result.dm_fee or 0),
                "AH16": float(result.forex_reserve or 0),
                "AI16": float(result.financial_agent_fee or 0),
                # Final sale prices
                "AJ16": float(result.sales_price_per_unit_no_vat or 0),
                "AK16": float(result.sales_price_total_no_vat or 0),
                "AL16": float(result.sales_price_total_with_vat or 0),
                "AM16": float(result.sales_price_per_unit_with_vat or 0),
                # VAT breakdown
                "AN16": float(result.vat_from_sales or 0),
                "AO16": float(result.vat_on_import or 0),
                "AP16": float(result.vat_net_payable or 0),
                # Special
                "AQ16": float(result.transit_commission or 0),
                # Internal pricing
                "AX16": float(result.internal_sale_price_per_unit or 0),
                "AY16": float(result.internal_sale_price_total or 0),
                # Financing
                "BA16": float(result.financing_cost_initial or 0),
                "BB16": float(result.financing_cost_credit or 0),
            }

            # Convert phase_results to USD for analytics
            rate = float(exchange_rate_to_usd)
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

        # Store calculation summary (with USD equivalents for analytics)
        rate = float(exchange_rate_to_usd)
        calc_summary = {
            "quote_id": quote_id,
            # Quote currency values
            "calc_s16_total_purchase_price": float(total_purchase),
            "calc_v16_total_logistics": float(total_logistics),
            "calc_y16_customs_duty": float(total_customs),
            "calc_total_brokerage": float(total_brokerage),
            "calc_ae16_sale_price_total": float(total_no_vat),
            "calc_al16_total_with_vat": float(total_with_vat),
            "calc_af16_profit_margin": float(avg_margin),
            # USD equivalents for analytics
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

        # Update quote currency if it changed
        if quote.get("currency") != currency:
            supabase.table("quotes") \
                .update({"currency": currency}) \
                .eq("id", quote_id) \
                .execute()

        # Handle partial recalculation for price-only changes
        partial_recalc = quote.get("partial_recalc")
        if partial_recalc == "price":
            # Clear partial_recalc flag
            supabase.table("quotes").update({
                "partial_recalc": None
            }).eq("id", quote_id).execute()

            # Transition back to client_negotiation
            user_roles = user.get("roles", [])
            transition_quote_status(
                quote_id=quote_id,
                to_status="client_negotiation",
                actor_id=user["id"],
                actor_roles=user_roles,
                comment="Partial recalculation: price updated, returning to client negotiation"
            )

        # Create or update quote version for audit trail
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
            # Check existing versions and decide action
            existing_versions = list_quote_versions(quote_id, user["org_id"])
            current_version = get_current_quote_version(quote_id, user["org_id"]) if existing_versions else None

            # Determine change reason text
            reason_text = change_reason if change_reason else "Calculation saved"

            if not existing_versions:
                # First version - always create (no dialog shown)
                # Phase 5d: items sourced from composition_service inside the
                # snapshot function — not passed as kwarg.
                version = create_quote_version(
                    quote_id=quote_id,
                    user_id=user["id"],
                    variables=variables,
                    results=all_results,
                    totals=version_totals,
                    change_reason=reason_text,
                    customer_id=quote.get("customer_id")
                )
                version_number = version.get("version") if version else 1

            elif version_action == "update" and current_version:
                # User chose to update existing version
                can_update_flag, _ = can_update_version(quote_id, user["org_id"])
                if can_update_flag:
                    version = update_quote_version(
                        version_id=current_version["id"],
                        quote_id=quote_id,
                        org_id=user["org_id"],
                        user_id=user["id"],
                        variables=variables,
                        results=all_results,
                        totals=version_totals,
                        change_reason=reason_text
                    )
                    version_number = current_version.get("version_number", 1)
                else:
                    # Can't update, create new instead
                    version = create_quote_version(
                        quote_id=quote_id,
                        user_id=user["id"],
                        variables=variables,
                        results=all_results,
                        totals=version_totals,
                        change_reason=reason_text,
                        customer_id=quote.get("customer_id")
                    )
                    version_number = version.get("version") if version else None

            else:
                # Create new version (default or user explicitly chose "new")
                version = create_quote_version(
                    quote_id=quote_id,
                    user_id=user["id"],
                    variables=variables,
                    results=all_results,
                    totals=version_totals,
                    change_reason=reason_text,
                    customer_id=quote.get("customer_id")
                )
                version_number = version.get("version") if version else None

        except Exception as ve:
            # Version creation is optional - don't fail calculation
            version_number = None
            print(f"Warning: Failed to create version: {ve}")

        # Build detailed results page
        product_rows = []
        for item, result in zip(items, results):
            product_rows.append(
                Tr(
                    Td(item.get('product_name', 'Product')[:40]),
                    Td(str(item.get('quantity', 1))),
                    Td(format_money(result.cogs_per_unit, currency)),
                    Td(format_money(result.sales_price_per_unit_no_vat, currency)),
                    Td(format_money(result.sales_price_total_with_vat, currency)),
                    Td(format_money(result.profit, currency)),
                )
            )

        return page_layout(f"Результат расчёта - {quote.get('idn_quote', '')}",
            Div("Расчёт выполнен и сохранён!", cls="alert alert-success"),

            H1(f"Результат: {quote.get('idn_quote', '')}"),

            # Summary stats
            Div(
                Div(
                    Div("Итого (без НДС)", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_no_vat, currency), cls="stat-value"),
                    cls="stat-card"
                ),
                Div(
                    Div("Итого (с НДС)", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_with_vat, currency), cls="stat-value", style="color: #28a745;"),
                    cls="stat-card"
                ),
                Div(
                    Div("Общий профит", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_profit, currency), cls="stat-value"),
                    cls="stat-card"
                ),
                Div(
                    Div("Наценка (профит ÷ себест.)", style="font-size: 0.875rem; color: #666;"),
                    Div(f"{avg_margin:.1f}%", cls="stat-value"),
                    cls="stat-card"
                ),
                cls="stats-grid"
            ),

            # Cost breakdown
            Div(
                H3("Структура затрат"),
                Table(
                    Tr(Td("Закупка товаров:"), Td(format_money(total_purchase, currency))),
                    Tr(Td("Логистика:"), Td(format_money(total_logistics, currency))),
                    Tr(Td("Брокерские услуги:"), Td(format_money(total_brokerage, currency))),
                    Tr(Td("Себестоимость:"), Td(format_money(total_cogs, currency))),
                    Tr(Td(Strong("НДС к уплате:")), Td(Strong(format_money(total_vat, currency)))),
                ),
                cls="card"
            ),

            # Product details
            Div(
                H3("Детализация по позициям"),
                Table(
                    Thead(
                        Tr(
                            Th("Товар"),
                            Th("Кол-во"),
                            Th("Себест./ед."),
                            Th("Цена/ед."),
                            Th("Итого"),
                            Th("Профит"),
                        )
                    ),
                    Tbody(*product_rows),
                    Tfoot(
                        Tr(
                            Td(Strong("ИТОГО"), colspan="4"),
                            Td(Strong(format_money(total_with_vat, currency))),
                            Td(Strong(format_money(total_profit, currency))),
                        )
                    ),
                ),
                cls="card"
            ),

            # Variables used
            Div(
                H3("Параметры расчёта"),
                Table(
                    Tr(Td("Наценка:"), Td(f"{variables['markup']}%")),
                    Tr(Td("Инкотермс:"), Td(variables['offer_incoterms'])),
                    Tr(Td("Срок поставки:"), Td(f"{variables['delivery_time']} дн.")),
                    Tr(Td("Аванс клиента:"), Td(f"{variables['advance_from_client']}%")),
                    Tr(Td("Курс:"), Td(str(variables['exchange_rate']))),
                ),
                cls="card"
            ),

            # Actions
            Div(
                btn_link("Назад к КП", href=f"/quotes/{quote_id}", variant="secondary", icon_name="arrow-left"),
                btn_link("Пересчитать", href=f"/quotes/{quote_id}/calculate", variant="primary", icon_name="calculator"),
                cls="form-actions"
            ),

            session=session
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return page_layout("Ошибка расчёта",
            Div(f"Ошибка: {str(e)}", cls="alert alert-error"),
            btn_link("Назад", href=f"/quotes/{quote_id}/calculate", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# NOTE: POST /api/quotes/{quote_id}/calculate — extracted in Phase 6B-6a to
# api/quotes.py::calculate_quote, registered via api/routers/quotes.py.


# ============================================================================
# QUOTE CANCEL API + WORKFLOW TRANSITION API
# ============================================================================
# Extracted to api/quotes.py::cancel_quote and api/quotes.py::transition_workflow
# in 6B-6b, registered via api/routers/quotes.py.


# ============================================================================
# QUOTE DOCUMENTS TAB
# ============================================================================

# @rt("/quotes/{quote_id}/documents")
def get(quote_id: str, session):
    """View documents tab for a quote with hierarchical binding support"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]
    user_roles = get_session_user_roles(session)

    supabase = get_supabase()

    # Get quote details
    quote_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, status, workflow_status, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            Div("Запрошенное КП не существует или у вас нет доступа.", cls="card"),
            A("← К списку КП", href="/quotes"),
            session=session
        )

    quote = quote_result.data[0]
    quote_number = quote.get("idn_quote") or quote_id[:8]
    workflow_status = quote.get("workflow_status") or quote.get("status", "draft")

    # Get customer name
    customer_name = (quote.get("customers") or {}).get("name", "—")
    if customer_name == "—" and quote.get("customer_id"):
        customer_result = supabase.table("customers") \
            .select("name") \
            .eq("id", quote["customer_id"]) \
            .execute()
        if customer_result.data:
            customer_name = customer_result.data[0].get("name", "—")

    # Get supplier invoices for this quote (for invoice binding dropdown)
    invoices = []
    try:
        # First get quote item IDs
        quote_items_result = supabase.table("quote_items") \
            .select("id") \
            .eq("quote_id", quote_id) \
            .execute()

        quote_item_ids = [item["id"] for item in (quote_items_result.data or [])]

        if quote_item_ids:
            # Get invoice items linked to this quote's items
            invoice_items_result = supabase.table("supplier_invoice_items") \
                .select("invoice_id") \
                .in_("quote_item_id", quote_item_ids) \
                .execute()

            if invoice_items_result.data:
                invoice_ids = list(set(item["invoice_id"] for item in invoice_items_result.data if item.get("invoice_id")))
                if invoice_ids:
                    invoices_result = supabase.table("supplier_invoices") \
                        .select("id, invoice_number, supplier_id") \
                        .in_("id", invoice_ids) \
                        .order("invoice_date", desc=True) \
                        .execute()

                    if invoices_result.data:
                        # Get supplier names
                        supplier_ids = list(set(inv["supplier_id"] for inv in invoices_result.data if inv.get("supplier_id")))
                        suppliers_map = {}
                        if supplier_ids:
                            suppliers_result = supabase.table("suppliers") \
                                .select("id, name") \
                                .in_("id", supplier_ids) \
                                .execute()
                            suppliers_map = {s["id"]: s["name"] for s in (suppliers_result.data or [])}

                        for inv in invoices_result.data:
                            invoices.append({
                                "id": inv["id"],
                                "invoice_number": inv.get("invoice_number", ""),
                                "supplier_name": suppliers_map.get(inv.get("supplier_id"), "")
                            })
    except Exception as e:
        print(f"Error fetching invoices for quote documents: {e}")

    # Get quote items (for certificate binding dropdown)
    items = []
    try:
        items_result = supabase.table("quote_items") \
            .select("id, product_name, product_code, brand") \
            .eq("quote_id", quote_id) \
            .order("position") \
            .execute()

        if items_result.data:
            for item in items_result.data:
                items.append({
                    "id": item["id"],
                    "name": item.get("product_name", "Товар"),
                    "sku": item.get("product_code", ""),
                    "brand": item.get("brand", "")
                })
    except Exception as e:
        print(f"Error fetching items for quote documents: {e}")

    # Determine permissions based on roles
    can_upload = user_has_any_role(session, ["admin", "sales", "sales_manager", "procurement", "quote_controller", "finance", "logistics", "customs"])
    can_delete = user_has_any_role(session, ["admin", "sales_manager", "quote_controller", "finance"])

    # Get total documents count (all related to this quote)
    doc_count = count_all_documents_for_quote(quote_id)

    return page_layout(
        f"Документы КП {quote_number}",

        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "documents", user_roles),

        # Info card with gradient styling
        Div(
            P(
                icon("info", size=16, color="#3b82f6"),
                " Здесь можно загружать и просматривать все документы по КП: документы самого КП, сканы инвойсов и сертификаты на товары.",
                style="display: flex; align-items: flex-start; gap: 0.5rem; margin: 0; color: #64748b; font-size: 0.875rem;"
            ),
            cls="card",
            style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-left: 4px solid #3b82f6; margin-bottom: 1.5rem; padding: 1rem; border-radius: 8px;"
        ),

        # Documents section with hierarchical binding
        _quote_documents_section(
            quote_id=quote_id,
            session=session,
            invoices=invoices,
            items=items,
            can_upload=can_upload,
            can_delete=can_delete
        ),

        # Document chain section (grouped by stage)
        _render_document_chain_section(quote_id),

        # Currency invoices section (verified/exported only, hidden if no deal)
        _render_currency_invoices_section(quote_id, supabase),

        # Back button
        Div(
            A(icon("arrow-left", size=16), " К обзору КП", href=f"/quotes/{quote_id}",
              style="display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text-secondary); text-decoration: none;"),
            style="margin-top: 2rem;"
        ),

        session=session
    )


# ============================================================================
# DOCUMENT CHAIN (P2.10)
# ============================================================================

def _build_document_chain(quote_id):
    """
    Build document chain structure for a quote.

    Groups all documents related to a quote into 5 stages:
    - quote: Documents directly attached to the quote (entity_type='quote')
    - specification: Documents attached to specifications (entity_type='specification')
    - supplier_invoice: Documents attached to supplier invoices (entity_type='supplier_invoice')
    - upd: Documents with document_type='upd' (from any entity)
    - customs_declaration: Documents with document_type='customs_declaration' (from any entity)

    Args:
        quote_id: Quote UUID

    Returns:
        Dict with 5 stage keys, each mapping to a list of documents
    """
    all_docs = get_all_documents_for_quote(quote_id)

    chain = {
        "quote": [],
        "specification": [],
        "supplier_invoice": [],
        "customs_declaration": [],
        "upd": [],
    }

    for doc in all_docs:
        # First check document_type for upd and customs_declaration
        if doc.document_type == "upd":
            chain["upd"].append(doc)
        elif doc.document_type == "customs_declaration":
            chain["customs_declaration"].append(doc)
        elif doc.entity_type == "quote":
            chain["quote"].append(doc)
        elif doc.entity_type == "specification":
            chain["specification"].append(doc)
        elif doc.entity_type == "supplier_invoice":
            chain["supplier_invoice"].append(doc)
        else:
            # Default: attach to quote stage
            chain["quote"].append(doc)

    return chain


def _render_document_chain_section(quote_id: str):
    """
    Render the document chain section showing documents grouped by stage.
    Used as a sub-section within the merged Documents tab.
    """
    chain = _build_document_chain(quote_id)

    # Define chain stages with Russian labels and icons
    chain_stages = [
        {"key": "quote", "label": "КП", "icon": "file-text", "color": "#3b82f6"},
        {"key": "specification", "label": "Спецификация", "icon": "clipboard-list", "color": "#8b5cf6"},
        {"key": "supplier_invoice", "label": "Инвойс", "icon": "receipt", "color": "#f59e0b"},
        {"key": "customs_declaration", "label": "ГТД", "icon": "shield", "color": "#ef4444"},
        {"key": "upd", "label": "УПД", "icon": "file-check", "color": "#22c55e"},
    ]

    # Build stage cards
    stage_cards = []
    for stage in chain_stages:
        docs = chain.get(stage["key"], [])
        doc_count = len(docs)

        # Build document list for this stage
        doc_items = []
        for doc in docs:
            doc_items.append(
                Div(
                    I(cls=f"fa-solid {get_file_icon(doc.mime_type)}", style=f"margin-right: 0.5rem; color: {stage['color']};"),
                    A(doc.original_filename,
                      href=f"/documents/{doc.id}/view",
                      target="_blank",
                      style="text-decoration: none; color: #1e293b; font-size: 13px;"),
                    Span(
                        get_document_type_label(doc.document_type),
                        style="margin-left: 8px; font-size: 11px; color: #64748b; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;"
                    ) if doc.document_type else "",
                    style="display: flex; align-items: center; padding: 6px 0; border-bottom: 1px solid #f1f5f9;"
                )
            )

        stage_cards.append(
            Div(
                # Stage header
                Div(
                    Div(
                        icon(stage["icon"], size=20, color=stage["color"]),
                        Span(stage["label"], style=f"font-size: 14px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    ),
                    Span(
                        str(doc_count),
                        style=f"background: {stage['color']}20; color: {stage['color']}; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 10px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid " + stage["color"] + ";"
                ),
                # Document list or empty state
                Div(*doc_items) if doc_items else Div(
                    Span("Нет документов", style="font-size: 13px; color: #94a3b8; font-style: italic;"),
                    style="padding: 12px 0; text-align: center;"
                ),
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            )
        )

    return Div(
        # Divider
        Hr(style="margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;"),

        # Section header
        H3(
            icon("link", size=20),
            " Цепочка документов по стадиям",
            style="display: flex; align-items: center; gap: 0.5rem; margin: 0 0 1rem; font-size: 1.1rem; color: #1e293b;"
        ),

        # Chain timeline grid
        Div(
            *stage_cards,
            style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px;"
        ),
    )


def _render_currency_invoices_section(quote_id: str, supabase):
    """
    Render 'Валютные инвойсы' section for quote documents tab.
    Only shows invoices with status 'verified' or 'exported'.
    Returns empty string if no deal exists for this quote.
    """
    # Check if a deal exists for this quote
    try:
        deal_resp = supabase.table("deals").select("id").eq("quote_id", quote_id).is_("deleted_at", None).execute()
        deals = deal_resp.data or []
    except Exception as e:
        print(f"Error checking deals for quote {quote_id}: {e}")
        return ""

    if not deals:
        return ""

    deal_ids = [d["id"] for d in deals]

    # Fetch approved currency invoices for these deals
    try:
        ci_resp = supabase.table("currency_invoices").select(
            "id, invoice_number, segment, total_amount, currency, status, generated_at"
        ).in_("deal_id", deal_ids).in_("status", ["verified", "exported"]).order("generated_at", desc=True).execute()
        approved_cis = ci_resp.data or []
    except Exception as e:
        print(f"Error fetching approved currency invoices for quote {quote_id}: {e}")
        approved_cis = []

    # Build cards
    if approved_cis:
        cards = []
        for ci in approved_cis:
            total = float(ci.get("total_amount", 0) or 0)
            cards.append(
                A(
                    Div(
                        Div(
                            _ci_segment_badge(ci.get("segment", "")),
                            _ci_status_badge(ci.get("status", "")),
                            style="display: flex; gap: 6px; align-items: center; margin-bottom: 8px;"
                        ),
                        Div(
                            ci.get("invoice_number", "—"),
                            style="font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 4px;"
                        ),
                        Div(
                            f"{total:,.2f} {ci.get('currency', '')}",
                            style="font-size: 13px; color: #64748b;"
                        ),
                    ),
                    href=f"/currency-invoices/{ci['id']}",
                    style="display: block; background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; text-decoration: none; transition: box-shadow 0.15s;",
                    onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'",
                    onmouseout="this.style.boxShadow='none'"
                )
            )
        content = Div(*cards, style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px;")
    else:
        content = Div(
            Span("Нет утверждённых валютных инвойсов",
                 style="font-size: 13px; color: #94a3b8; font-style: italic;"),
            style="padding: 16px 0;"
        )

    count_badge = Span(
        str(len(approved_cis)),
        style="background: #8b5cf620; color: #8b5cf6; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-left: 8px;"
    ) if approved_cis else ""

    return Div(
        Hr(style="margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;"),
        H3(
            icon("receipt", size=20),
            " Валютные инвойсы",
            count_badge,
            style="display: flex; align-items: center; gap: 0.5rem; margin: 0 0 1rem; font-size: 1.1rem; color: #1e293b;"
        ),
        content,
    )


# ============================================================================
# VERSION HISTORY ROUTES
# ============================================================================

# @rt("/quotes/{quote_id}/versions")
def get(quote_id: str, session):
    """View version history for a quote"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = quote_result.data[0]
    currency = quote.get("currency", "USD")

    # Get versions
    versions = list_quote_versions(quote_id, user["org_id"])

    # Build version rows
    version_rows = []
    for v in versions:
        version_rows.append(
            Tr(
                Td(f"v{v['version_number']}"),
                Td(v.get("status", "draft")),
                Td(format_money(v.get("total_quote_currency"), currency)),
                Td(v.get("change_reason", "-")),
                Td(v.get("created_at", "")[:16].replace("T", " ")),
                Td(
                    A("View", href=f"/quotes/{quote_id}/versions/{v['version_number']}", style="margin-right: 0.5rem;"),
                ),
            )
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

    table_style = """
        width: 100%;
        border-collapse: collapse;
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    """

    th_style = """
        padding: 14px 16px;
        text-align: left;
        background: #f8fafc;
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        border-bottom: 1px solid #e2e8f0;
    """

    td_style = "padding: 14px 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px; color: #334155;"

    return page_layout(f"История версий - {quote.get('idn_quote', '')}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), " Назад к КП", href=f"/quotes/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1(f"История версий",
               style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            Div(
                Span(icon("file-text", size=14), style="color: #64748b;"),
                Span(f"КП: {quote.get('idn_quote', '-')}", style="color: #475569; font-weight: 500;"),
                Span(" • ", style="color: #cbd5e1;"),
                Span(f"Клиент: {quote.get('customers', {}).get('name', '-')}", style="color: #64748b;"),
                style="display: flex; align-items: center; gap: 8px; font-size: 14px;"
            ),
            style=header_style
        ),

        # Versions table
        Table(
            Thead(
                Tr(
                    Th("Версия", style=th_style),
                    Th("Статус", style=th_style),
                    Th("Сумма", style=th_style),
                    Th("Причина изменения", style=th_style),
                    Th("Создана", style=th_style),
                    Th("", style=th_style),
                )
            ),
            Tbody(
                *[Tr(
                    Td(f"v{v['version_number']}", style=f"{td_style} font-weight: 600;"),
                    Td(
                        Span(v.get("status", "draft"),
                             style=f"padding: 4px 10px; border-radius: 12px; font-size: 12px; "
                                   f"background: {'#dcfce7' if v.get('status') == 'approved' else '#fef3c7' if v.get('status') == 'sent' else '#f1f5f9'}; "
                                   f"color: {'#166534' if v.get('status') == 'approved' else '#92400e' if v.get('status') == 'sent' else '#475569'};"),
                        style=td_style
                    ),
                    Td(format_money(v.get("total_quote_currency"), currency), style=f"{td_style} font-weight: 500;"),
                    Td(v.get("change_reason") or "-", style=f"{td_style} color: #64748b;"),
                    Td(v.get("created_at", "")[:16].replace("T", " "), style=f"{td_style} color: #64748b; font-size: 13px;"),
                    Td(
                        A(icon("eye", size=14), " Просмотр", href=f"/quotes/{quote_id}/versions/{v['version_number']}",
                          style="color: #3b82f6; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 4px;"),
                        style=td_style
                    ),
                ) for v in versions]
            ) if version_rows else Tbody(
                Tr(Td("Версий пока нет. Запустите расчёт для создания первой версии.",
                      colspan="6", style=f"{td_style} text-align: center; color: #94a3b8; padding: 40px;"))
            ),
            style=table_style
        ),

        # Action buttons
        Div(
            A(icon("arrow-left", size=14), " К КП", href=f"/quotes/{quote_id}",
              style="padding: 10px 16px; background: #f1f5f9; color: #475569; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
            A(icon("calculator", size=14), " Новый расчёт", href=f"/quotes/{quote_id}/calculate",
              style="padding: 10px 16px; background: #3b82f6; color: white; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
            style="margin-top: 20px; display: flex; gap: 12px;"
        ),

        session=session
    )


# @rt("/quotes/{quote_id}/versions/{version_num}")
def get(quote_id: str, version_num: int, session):
    """View specific version details"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    # Get version
    version = get_quote_version(quote_id, version_num, user["org_id"])

    if not version:
        return page_layout("Not Found", H1("Version not found"), session=session)

    # Get quote for context
    supabase = get_supabase()
    quote_result = supabase.table("quotes") \
        .select("idn_quote, currency") \
        .eq("id", quote_id) \
        .is_("deleted_at", None) \
        .execute()

    quote = quote_result.data[0] if quote_result.data else {}
    currency = quote.get("currency", "USD")

    # Build products from snapshot
    products = version.get("products_snapshot", [])
    results = version.get("calculation_results", [])

    product_rows = []
    for i, p in enumerate(products):
        r = results[i] if i < len(results) else {}
        product_rows.append(
            Tr(
                Td(p.get("product_name", "-")[:40]),
                Td(str(p.get("quantity", 1))),
                Td(format_money(r.get("AJ16"), currency)),
                Td(format_money(r.get("AL16"), currency)),
                Td(format_money(r.get("AF16"), currency)),
            )
        )

    # Get variables
    variables = version.get("quote_variables", {})

    return page_layout(f"Version {version_num} - {quote.get('idn_quote', '')}",
        # Gradient header card
        Div(
            Div(
                A(
                    icon("arrow-left", size=16, color="#64748b"),
                    Span("К истории версий", style="margin-left: 6px;"),
                    href=f"/quotes/{quote_id}/versions",
                    style="display: inline-flex; align-items: center; color: #64748b; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("history", size=24, color="#6366f1"),
                    Span(f"Версия {version_num}", style="font-size: 24px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    status_badge(version.get("status", "draft")),
                    style="display: flex; align-items: center; gap: 12px;"
                ),
                Div(
                    Span(f"КП: {quote.get('idn_quote', '-')}", style="color: #64748b; font-size: 14px;"),
                    style="margin-top: 4px;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Two column layout
        Div(
            # Left column - Version Info & Variables
            Div(
                # Version metadata card
                Div(
                    Div(
                        icon("info", size=16, color="#64748b"),
                        Span("ИНФОРМАЦИЯ О ВЕРСИИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        Div(
                            Span("Дата создания", style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;"),
                            Span(version.get("created_at", "")[:16].replace("T", " "), style="font-size: 14px; font-weight: 500; color: #1e293b;"),
                            style="margin-bottom: 16px;"
                        ),
                        Div(
                            Span("Причина изменения", style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;"),
                            Span(version.get("change_reason", "-") or "-", style="font-size: 14px; font-weight: 500; color: #1e293b;"),
                            style="margin-bottom: 16px;"
                        ),
                        Div(
                            Span("Итого по версии", style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;"),
                            Span(format_money(version.get("total_quote_currency"), currency), style="font-size: 18px; font-weight: 600; color: #059669;"),
                        ),
                    ),
                    style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),

                # Variables snapshot card
                Div(
                    Div(
                        icon("sliders", size=16, color="#64748b"),
                        Span("ПАРАМЕТРЫ РАСЧЁТА", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        *[
                            Div(
                                Span(label, style="font-size: 12px; color: #64748b;"),
                                Span(value, style="font-size: 14px; font-weight: 500; color: #1e293b;"),
                                style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9;"
                            )
                            for label, value in [
                                ("Наценка", f"{variables.get('markup', '-')}%"),
                                ("Инкотермс", variables.get('offer_incoterms', '-') or '-'),
                                ("Срок поставки", f"{variables.get('delivery_time', '-')} дн."),
                                ("Аванс от клиента", f"{variables.get('advance_from_client', '-')}%"),
                                ("Курс обмена", str(variables.get('exchange_rate', '-'))),
                            ]
                        ],
                    ),
                    style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),
                style="flex: 1; min-width: 280px;"
            ),

            # Right column - Products
            Div(
                Div(
                    Div(
                        icon("package", size=16, color="#64748b"),
                        Span("ТОВАРЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        Span(f"{len(products)}", style="background: #e0e7ff; color: #4f46e5; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-left: 8px;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Товар", style="text-align: left; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Кол-во", style="text-align: center; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Цена/ед.", style="text-align: right; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Итого", style="text-align: right; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Прибыль", style="text-align: right; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                )
                            ),
                            Tbody(
                                *[
                                    Tr(
                                        Td(p.get("product_name", "-")[:40], style="padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(str(p.get("quantity", 1)), style="text-align: center; padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(format_money((results[i] if i < len(results) else {}).get("AJ16"), currency), style="text-align: right; padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(format_money((results[i] if i < len(results) else {}).get("AL16"), currency), style="text-align: right; padding: 12px 16px; font-size: 14px; font-weight: 500; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(format_money((results[i] if i < len(results) else {}).get("AF16"), currency), style="text-align: right; padding: 12px 16px; font-size: 14px; font-weight: 500; color: #059669; border-bottom: 1px solid #f1f5f9;"),
                                    )
                                    for i, p in enumerate(products)
                                ] if products else [
                                    Tr(Td("Нет товаров", colspan="5", style="padding: 24px; text-align: center; color: #94a3b8;"))
                                ]
                            ),
                            style="width: 100%; border-collapse: collapse;"
                        ),
                        style="overflow-x: auto;"
                    ),
                    style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),
                style="flex: 2; min-width: 400px;"
            ),
            style="display: flex; gap: 24px; flex-wrap: wrap;"
        ),

        # Action buttons
        Div(
            btn_link("История версий", href=f"/quotes/{quote_id}/versions", variant="secondary", icon_name="history"),
            btn_link("К КП", href=f"/quotes/{quote_id}", variant="primary", icon_name="file-text"),
            style="margin-top: 24px; display: flex; gap: 12px;"
        ),

        session=session
    )


# ============================================================================
# EXPORT ROUTES
# ============================================================================

# @rt("/quotes/{quote_id}/export/specification")
def get(quote_id: str, session):
    """Export Specification PDF - uses contract-style template matching DOCX"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    try:
        # First, check if a specification exists for this quote
        from services.specification_service import get_specification_by_quote
        spec = get_specification_by_quote(quote_id, org_id)

        if spec:
            # Use new contract-style template (matches DOCX)
            from services.contract_spec_export import generate_contract_spec_pdf
            pdf_bytes, spec_number = generate_contract_spec_pdf(str(spec.id), org_id)
            safe_spec_number = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(spec_number))
            filename = f"Specification_{safe_spec_number}.pdf"
        else:
            # Fallback to old template if no specification exists yet
            data = fetch_export_data(quote_id, org_id)
            pdf_bytes = generate_specification_pdf(data)
            customer_name = data.customer.get('company_name') or data.customer.get('name') or ''
            filename = build_export_filename(
                doc_type="specification",
                customer_name=customer_name,
                quote_number=data.quote.get('quote_number', ''),
                ext="pdf"
            )

        # Return as file download
        from starlette.responses import Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate PDF: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )


# @rt("/quotes/{quote_id}/export/invoice")
def get(quote_id: str, session):
    """Export Invoice PDF (Счет на оплату)"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    try:
        # Fetch all export data
        data = fetch_export_data(quote_id, user["org_id"])

        # Generate PDF
        pdf_bytes = generate_invoice_pdf(data)

        # Return as file download
        from starlette.responses import Response
        customer_name = data.customer.get('company_name') or data.customer.get('name') or ''
        filename = build_export_filename(
            doc_type="invoice",
            customer_name=customer_name,
            quote_number=data.quote.get('quote_number', ''),
            ext="pdf"
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate PDF: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )


# @rt("/quotes/{quote_id}/export/validation")
def get(quote_id: str, session):
    """Export Validation Excel spreadsheet"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    try:
        # Fetch all export data
        data = fetch_export_data(quote_id, user["org_id"])

        # Generate Excel
        excel_bytes = create_validation_excel(data)

        # Return as file download (XLSM with macros)
        from starlette.responses import Response
        filename = f"validation_{data.quote.get('quote_number', quote_id)}.xlsm"
        return Response(
            content=excel_bytes,
            media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate Excel: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )



# ============================================================================
# AREA 2 — /procurement cluster (4 routes)
# ============================================================================
# Extracted from main.py lines 12967-13397.
# Includes _build_sales_checklist_card — was exclusive to the /procurement
# detail page which was archived in Phase 6C-1 (procurement_workspace.py);
# after that archive it had zero callers in main.py, so it moves here
# alongside the remaining /procurement registry + exports.
# ============================================================================

# ============================================================================
# USER PROFILE PAGE — [archived to legacy-fasthtml/settings_profile.py in Phase 6C-2B-4]
# Routes moved: /profile GET+POST, /profile/{user_id} POST (admin save).
# Superseded by Next.js /profile.
# ============================================================================

# @rt("/procurement")
def get(session, status_filter: str = None):
    """
    Redirect to unified dashboard procurement tab.
    Old URL preserved for backwards compatibility.
    """
    url = "/dashboard?tab=procurement"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


# ============================================================================
# SALES CHECKLIST DISPLAY HELPER
# ============================================================================

def _build_sales_checklist_card(sales_checklist):
    """Build a yellow info card displaying sales checklist answers for procurement."""
    if not sales_checklist:
        return None

    # Handle both dict and string (JSONB comes as dict from Supabase)
    if isinstance(sales_checklist, str):
        try:
            sales_checklist = json.loads(sales_checklist)
        except (json.JSONDecodeError, TypeError):
            return None

    def _yes_no(val):
        return "Да" if val else "Нет"

    def _check_icon(val):
        if val:
            return icon("check-circle", size=14, color="#059669")
        return icon("circle", size=14, color="#94a3b8")

    return Div(
        Div(
            icon("clipboard-list", size=18, color="#92400e"),
            Span(" Информация от отдела продаж", style="font-weight: 600; font-size: 1rem; margin-left: 6px; color: #92400e;"),
            style="display: flex; align-items: center; margin-bottom: 12px;"
        ),
        Div(
            Div(
                _check_icon(sales_checklist.get("is_estimate")),
                Span(f" Проценка: {_yes_no(sales_checklist.get('is_estimate'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            Div(
                _check_icon(sales_checklist.get("is_tender")),
                Span(f" Тендер: {_yes_no(sales_checklist.get('is_tender'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            Div(
                _check_icon(sales_checklist.get("direct_request")),
                Span(f" Прямой запрос от клиента: {_yes_no(sales_checklist.get('direct_request'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            Div(
                _check_icon(sales_checklist.get("trading_org_request")),
                Span(f" Запрос через торгующую организацию: {_yes_no(sales_checklist.get('trading_org_request'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            style="margin-bottom: 12px; font-size: 0.875rem; color: #374151;"
        ),
        Div(
            Span("Описание оборудования:", style="font-weight: 600; font-size: 0.875rem; color: #92400e; display: block; margin-bottom: 4px;"),
            P(sales_checklist.get("equipment_description", "---"),
              style="margin: 0; padding: 8px 12px; background: rgba(255,255,255,0.5); border-radius: 6px; font-size: 0.875rem; white-space: pre-wrap; line-height: 1.5;"),
        ),
        cls="card",
        style="background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-left: 4px solid #f59e0b; margin-bottom: 1rem; padding: 1rem; border-radius: 10px;"
    )




# ============================================================================
# DOCUMENT API ENDPOINTS
# ============================================================================
# Phase 6B-9: /api/documents/{document_id}/download (GET) and
# /api/documents/{document_id} (DELETE) moved to api/documents.py + routed via
# api/routers/documents.py on the FastAPI sub-app mounted at /api.






# ============================================================================
# PROCUREMENT - RETURN TO QUOTE CONTROL (Feature: multi-department return)
# ============================================================================

# @rt("/procurement/{quote_id}/return-to-control")
def get(quote_id: str, session):
    """
    Form for procurement to return a revised quote back to quote control.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
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
            P("КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data
    workflow_status = quote.get("workflow_status", "draft")
    revision_comment = quote.get("revision_comment", "")
    idn_quote = quote.get("idn_quote", f"#{quote_id[:8]}")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    # Can only return from pending_procurement status
    if workflow_status != "pending_procurement":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
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
                A(icon("arrow-left", size=16), f" Назад к закупкам", href=f"/quotes/{quote_id}",
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
                    placeholder="Исправлена цена на позицию X...\nОбновлены данные поставщика...\nИзменены сроки производства...",
                    required=True,
                    style=textarea_style
                ),
                style="margin-bottom: 24px;"
            ),
            Div(
                Button(icon("check", size=14), " Вернуть на проверку", type="submit",
                       style="padding: 10px 20px; background: #22c55e; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/quotes/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                style="display: flex; gap: 12px;"
            ),
            action=f"/procurement/{quote_id}/return-to-control",
            method="post",
            style=form_card_style
        ),
        session=session
    )


# @rt("/procurement/{quote_id}/return-to-control")
def post(quote_id: str, session, comment: str = ""):
    """
    Handle return to quote control from procurement.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий об исправлениях."),
            A("← Вернуться", href=f"/procurement/{quote_id}/return-to-control"),
            session=session
        )

    supabase = get_supabase()

    # Verify quote exists
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

    if current_status != "pending_procurement":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Perform workflow transition
    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_QUOTE_CONTROL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"Исправления от закупок: {comment.strip()}"
    )

    if result.success:
        # Clear revision fields after returning
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
            A("← Назад", href=f"/procurement/{quote_id}/return-to-control"),
            session=session
        )


# @rt("/procurement/{quote_id}/export")
def get(quote_id: str, session):
    """
    Export procurement items to Excel for sending to suppliers.

    Feature #36: Скачивание списка для оценки
    - Exports items belonging to user's assigned brands
    - Creates Excel file with columns for supplier to fill in
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has procurement role
    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    quote = quote_result.data
    if not quote:
        return RedirectResponse("/procurement", status_code=303)

    customer_name = (quote.get("customers") or {}).get("name", "")

    # Check if user is admin or head_of_procurement - bypass brand filtering
    is_admin = user_has_any_role(session, ["admin", "head_of_procurement"])

    # Get user's assigned brands (admin sees all)
    my_brands = get_assigned_brands(user_id, org_id) if not is_admin else []
    my_brands_lower = [b.lower() for b in my_brands]

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    all_items = items_result.data or []

    # Filter items for my brands (handle None brand values) - admin sees all
    if is_admin:
        my_items = all_items
    else:
        my_items = [item for item in all_items
                    if (item.get("brand") or "").lower() in my_brands_lower]

    if not my_items:
        # No items to export, redirect back with message
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    # Generate Excel
    excel_bytes = create_procurement_excel(
        quote=quote,
        items=my_items,
        brands=my_brands,
        customer_name=customer_name
    )

    # Return as file download
    from starlette.responses import Response
    filename = build_export_filename(
        doc_type="procurement",
        customer_name=customer_name,
        quote_number=quote.get("idn_quote", ''),
        ext="xlsx"
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )








# ============================================================================
# AREA 3 — /quotes chat + comments (2 routes)
# ============================================================================
# Extracted from main.py lines 17635-17904.
# ============================================================================

# ============================================================================
# QUOTE CHAT TAB (Comments)
# ============================================================================

def _render_comment_bubble(comment, current_user_id):
    """Render a single chat message bubble."""
    is_own = comment.get("user_id") == current_user_id
    author_name = comment.get("author_name", "Unknown")
    body_raw = comment.get("body", "")
    created_at = comment.get("created_at", "")

    # HTML-escape body BEFORE applying @mention highlighting
    body_escaped = html_mod.escape(body_raw)

    # Highlight @mentions in the escaped body
    import re
    body_html = re.sub(
        r'(@\w+)',
        r'<span style="color: #3b82f6; font-weight: 600;">\1</span>',
        body_escaped
    )

    # Format timestamp
    time_display = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            time_display = dt.strftime("%H:%M")
        except Exception:
            time_display = created_at[:16]

    # Bubble alignment and style
    if is_own:
        bubble_style = """
            background: #dbeafe; border-radius: 12px 12px 4px 12px;
            padding: 0.75rem 1rem; max-width: 75%; margin-left: auto;
            margin-bottom: 0.5rem;
        """
        name_style = "font-size: 0.75rem; font-weight: 600; color: #2563eb; margin-bottom: 0.25rem;"
    else:
        bubble_style = """
            background: #f3f4f6; border-radius: 12px 12px 12px 4px;
            padding: 0.75rem 1rem; max-width: 75%;
            margin-bottom: 0.5rem;
        """
        name_style = "font-size: 0.75rem; font-weight: 600; color: #6b7280; margin-bottom: 0.25rem;"

    return Div(
        Div(author_name, style=name_style),
        Div(NotStr(body_html), style="font-size: 0.9rem; line-height: 1.4; color: #1f2937;"),
        Div(time_display, style="font-size: 0.7rem; color: #9ca3af; text-align: right; margin-top: 0.25rem;"),
        style=bubble_style,
        cls="chat-bubble"
    )


def _render_chat_tab(quote_id, comments, org_users, current_user_id):
    """Render the full chat tab content with messages, input form, and @mention dropdown."""

    # Messages area
    message_elements = []
    for comment in comments:
        message_elements.append(_render_comment_bubble(comment, current_user_id))

    if not message_elements:
        message_elements.append(
            Div(
                icon("message-circle", size=48, color="#d1d5db"),
                P("Нет сообщений", style="color: #9ca3af; margin-top: 0.5rem;"),
                P("Напишите первое сообщение в чат КП", style="color: #d1d5db; font-size: 0.85rem;"),
                id="chat-empty-state",
                style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 3rem;"
            )
        )

    messages_area = Div(
        *message_elements,
        id="chat-messages",
        style="flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; min-height: 300px; max-height: 500px;"
    )

    # Input form
    input_form = Form(
        Div(
            Textarea(
                name="body",
                placeholder="Написать сообщение...",
                id="chat-input",
                rows="2",
                style="flex: 1; border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.75rem; font-size: 0.9rem; resize: none; outline: none;",
            ),
            Input(type="hidden", name="mentions_json", id="mentions-json-input", value=""),
            Button(
                icon("send", size=18),
                type="submit",
                style="background: #3b82f6; color: white; border: none; border-radius: 8px; padding: 0.5rem 1rem; cursor: pointer; display: flex; align-items: center; gap: 0.25rem;",
            ),
            style="display: flex; gap: 0.5rem; align-items: flex-end;"
        ),
        hx_post=f"/quotes/{quote_id}/comments",
        hx_target="#chat-messages",
        hx_swap="beforeend",
        hx_on__after_request="this.querySelector('#chat-input').value = ''; this.querySelector('#mentions-json-input').value = ''; document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;",
        style="padding: 1rem; border-top: 1px solid #e5e7eb;",
    )

    # Chat container
    return Div(
        Div(
            H3(
                icon("message-circle", size=20),
                " Чат по КП",
                style="display: flex; align-items: center; gap: 0.5rem; margin: 0; font-size: 1.1rem;"
            ),
            style="padding: 1rem; border-bottom: 1px solid #e5e7eb;"
        ),
        messages_area,
        input_form,
        Script(f"""
            // Auto-scroll to bottom on page load
            (function() {{
                var el = document.getElementById('chat-messages');
                if (el) el.scrollTop = el.scrollHeight;
            }})();
        """),
        cls="card",
        style="display: flex; flex-direction: column; border-radius: 12px; overflow: hidden; margin-bottom: 1.5rem;"
    )


# @rt("/quotes/{quote_id}/chat")
def get(quote_id: str, session):
    """View chat tab for a quote."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]
    user_id = user["id"]
    user_roles = get_session_user_roles(session)

    supabase = get_supabase()

    # Get quote details
    quote_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, status, workflow_status, customers!customer_id(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            Div("Запрошенное КП не существует или у вас нет доступа.", cls="card"),
            A("← К списку КП", href="/quotes"),
            session=session
        )

    quote = quote_result.data[0]
    quote_number = quote.get("idn_quote") or quote_id[:8]
    workflow_status = quote.get("workflow_status") or quote.get("status", "draft")

    # Get customer name
    customer_name = (quote.get("customers") or {}).get("name", "—")

    # Import and use comment service
    from services.comment_service import get_comments_for_quote, mark_as_read, get_org_users_for_mentions

    # Mark as read when user opens chat
    mark_as_read(quote_id=quote_id, user_id=user_id)

    # Fetch comments and org users
    comments = get_comments_for_quote(quote_id)
    org_users = get_org_users_for_mentions(org_id)

    return page_layout(
        f"Чат КП {quote_number}",

        # Persistent header
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs -- chat_unread=0 because we just marked as read
        quote_detail_tabs(quote_id, "chat", user_roles, chat_unread=0),

        # Chat content
        _render_chat_tab(quote_id, comments, org_users, user_id),

        # Back button
        Div(
            A(icon("arrow-left", size=16), " К обзору КП", href=f"/quotes/{quote_id}",
              style="display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text-secondary); text-decoration: none;"),
            style="margin-top: 2rem;"
        ),

        session=session
    )


# @rt("/quotes/{quote_id}/comments")
def post(session, quote_id: str, body: str = "", mentions_json: str = ""):
    """Post a new comment to a quote's chat."""
    redirect = require_login(session)
    if redirect:
        return Response("Unauthorized", status_code=401)

    user = session["user"]
    org_id = user["org_id"]
    user_id = user["id"]

    # Validate body not empty
    if not body or not body.strip():
        return Response(status_code=204)

    # Verify quote belongs to org
    supabase = get_supabase()
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return Response("Quote not found", status_code=404)

    # Parse mentions
    mentions = []
    if mentions_json:
        try:
            mentions = json.loads(mentions_json)
            if not isinstance(mentions, list):
                mentions = []
        except (json.JSONDecodeError, TypeError):
            mentions = []

    # Create comment
    from services.comment_service import create_comment
    created = create_comment(
        quote_id=quote_id,
        user_id=user_id,
        body=body.strip(),
        mentions=mentions,
    )

    if not created:
        return Response("Error creating comment", status_code=500)

    # Enrich the created comment for rendering
    try:
        profile_result = supabase.table("user_profiles") \
            .select("full_name") \
            .eq("user_id", user_id) \
            .execute()
        author_name = (profile_result.data[0].get("full_name") if profile_result.data else None) or user_id[:8]
    except Exception:
        author_name = user_id[:8]

    created["author_name"] = author_name
    created["user_id"] = user_id

    # Render the new bubble
    bubble = _render_comment_bubble(created, user_id)

    # OOB: remove empty state placeholder when first message is sent
    empty_state_remove = Div(id="chat-empty-state", hx_swap_oob="outerHTML", style="display:none;")

    return Div(bubble, empty_state_remove)

