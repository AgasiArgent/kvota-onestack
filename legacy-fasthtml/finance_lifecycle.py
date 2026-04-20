"""FastHTML /deals + /payments/calendar + /finance main cluster — archived 2026-04-20 during Phase 6C-2B-10c1.

Finance lifecycle pages (deals list redirect, payments calendar, finance
workspace with ERPS/payments/invoices/calendar tabs, deal detail
redirect, plan-fact payment CRUD) are replaced by Next.js `/deals` +
`/finance` pages reading `/api/finance/*` + `/api/deals/*` FastAPI
routers. Routes unreachable post-Caddy-cutover: kvotaflow.ru
301→app.kvotaflow.ru, which doesn't proxy these paths back to this
Python container. Preserved here for reference / future copy-back.

Cluster-split rationale (10c1 vs 10c2):
    The /finance area originally spanned two contiguous blocks separated
    by the /admin area. This file (10c1) archives the FIRST block
    (lines 21144-24225 pre-archive, 11 @rt routes + 9 exclusive helpers
    + 3 ERPS constants + 3 ERPS formatters). A later archive (10c2) will
    handle the SECOND block (/deals/{deal_id} detail at line 27121+,
    /finance/{deal_id}/stages/*, /finance/{deal_id}/logistics-expenses/*,
    /finance/{deal_id}/generate-currency-invoices, /finance HTMX tail at
    27914-28255, plus the helper functions _finance_fetch_deal_data,
    _finance_main_tab_content, _finance_plan_fact_tab_content,
    _finance_logistics_tab_content, _finance_currency_invoices_tab_content,
    _logistics_expenses_total_el, _finance_logistics_expenses_tab_content,
    _finance_payment_modal, _deals_logistics_tab,
    _finance_logistics_expenses_stage_section).

Contents (11 @rt routes + 9 exclusive helpers + 3 constants, ~3,088 LOC total):

Routes archived in 10c1:
  - GET  /deals                                              — Redirect to /finance (301)
  - GET  /payments/calendar                                  — Payment calendar page
                                                               (wraps finance_calendar_tab)
  - GET  /finance                                            — Finance workspace with
                                                               tabs: workspace, erps,
                                                               payments, invoices, calendar
  - GET  /finance/{deal_id}                                  — Redirect to
                                                               /quotes/{quote_id}?tab=finance_main
                                                               (backward compat for ERPS
                                                               bookmarks)
  - GET  /finance/{deal_id}/payments/new                     — Payment registration form
  - POST /finance/{deal_id}/payments                         — Register new payment
                                                               (create plan_fact_item)
  - DELETE /finance/{deal_id}/payments/{item_id}             — Clear actual payment
  - GET  /finance/{deal_id}/generate-plan-fact               — Plan-fact preview page
  - POST /finance/{deal_id}/generate-plan-fact               — Generate plan-fact items
                                                               from deal
  - GET  /finance/{deal_id}/plan-fact/{item_id}              — Payment registration form
                                                               for a specific plan-fact item
  - POST /finance/{deal_id}/plan-fact/{item_id}              — Submit payment data
                                                               for plan-fact item

Tab-renderer helpers exclusive to /finance (archived here):
  - finance_workspace_tab       — "Рабочая зона" tab (active deals +
                                  plan-fact management); only caller
                                  was GET /finance
  - finance_erps_tab            — "Контроль платежей" (ERPS — Единый
                                  реестр подписанных спецификаций);
                                  supports views: full/compact/finance/
                                  logistics/procurement/custom; only
                                  caller was GET /finance
  - finance_payments_tab        — "Платежи" unified payments tab with
                                  filters (payment_type/status/date/
                                  deal/customer) and flat vs grouped
                                  view; only caller was GET /finance
  - finance_invoices_tab        — "Инвойсы" procurement invoices tab;
                                  only caller was GET /finance
  - finance_calendar_tab        — "Календарь платежей" monthly calendar
                                  with planned/actual markers; called
                                  by GET /finance (tab=calendar) and
                                  GET /payments/calendar

ERPS constants/formatters exclusive to ERPS tab (archived here):
  - ERPS_COLUMN_GROUPS          — config of column groups for ERPS
                                  table (spec/auto/finance/logistics/
                                  procurement/management)
  - ERPS_VIEWS                  — preset view → groups mapping
  - ERPS_COMPACT_COLUMNS        — compact-view column whitelist
  - fmt_days_until_payment      — color-coded badge (green/yellow/red/
                                  gray) for days-until-advance column
  - fmt_remaining_payment_with_percent — remaining payment + percent
                                  badge with threshold coloring (red>50%,
                                  amber 20-50%, green≤0%)
  - render_payments_grouped     — group items by customer name with
                                  subtotals (used by finance_payments_tab
                                  when view=grouped)

Payment-form helper exclusive to /finance/{deal_id}/payments/new
  (archived here):
  - _payment_registration_form  — Payment create/edit form renderer;
                                  only callers were GET/POST
                                  /finance/{deal_id}/payments/new

Preserved in main.py (NOT archived in 10c1; will be archived in 10c2 OR
stay alive):
  - _finance_fetch_deal_data, _finance_main_tab_content,
    _finance_plan_fact_tab_content, _finance_logistics_tab_content,
    _finance_currency_invoices_tab_content, _logistics_expenses_total_el,
    _finance_logistics_expenses_tab_content, _finance_payment_modal,
    _deals_logistics_tab, _finance_logistics_expenses_stage_section
    — all consumed by /deals/{deal_id} detail (line 27121) which
    archives in 10c2
  - _resolve_company_name, _ci_status_badge, _ci_segment_badge,
    _fetch_items_with_buyer_companies, _fetch_enrichment_data,
    _render_currency_invoices_section — still alive, consumed by
    /quotes/{id}/documents and other live surfaces

Preserved service layers (all alive):
  - services/plan_fact_service.py   — get_plan_fact_items_for_deal,
    generate_plan_fact_from_deal, clear_actual_payment, register_payment,
    get_categories_for_role, get_all_categories, get_unpaid_items_for_deal,
    get_paid_items_for_deal, get_customer_debt_summary, etc. —
    consumed by FastAPI /api/plan-fact/* and Next.js
  - services/deal_service.py        — count_deals_by_status,
    get_deals_by_status, etc. — consumed by FastAPI /api/deals/* and
    Next.js
  - services/erps_service.py        — consumed by FastAPI and 10c2
  - services/finance_service.py     — consumed by FastAPI /api/finance/*

NOT included in 10c1 (separate archive decisions):
  - /admin/* (lines 24232+) — separate archive decision
  - /deals/{deal_id} (line 27121+) — 10c2 archive
  - /finance/{deal_id}/stages/*, /finance/{deal_id}/logistics-expenses/*,
    /finance/{deal_id}/generate-currency-invoices (27914-28255) — 10c2
  - /api/finance/*, /api/deals/*, /api/plan-fact/* — FastAPI, alive
  - calculation_engine.py, calculation_models.py, calculation_mapper.py
    — locked, never touched

Sidebar/nav entries for /deals, /finance, /payments/calendar in main.py
left intact post-archive — they become dead links but are safe per the
Caddy cutover plan.

This file is NOT imported by main.py or api/app.py. Effectively dead
code preserved for reference. To resurrect a handler: copy back to
main.py, restore imports (page_layout, require_login, user_has_any_role,
get_supabase, icon, btn, btn_link, format_money, format_date_russian,
status_badge, workflow_status_badge, fasthtml components, starlette
RedirectResponse, services.plan_fact_service.*, services.deal_service.*,
services.erps_service.*, datetime/date/timedelta/Decimal), re-apply the
@rt decorator, and regenerate tests if needed. Not recommended —
rewrite via Next.js + FastAPI instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime, date, timedelta
from decimal import Decimal

from fasthtml.common import (
    A, Button, Div, Form, H1, H2, H3, H4, Hidden, I, Input, Label, Option, P,
    Script, Select, Small, Span, Strong, Style, Table, Tbody, Td, Textarea,
    Th, Thead, Tr,
)
from starlette.responses import RedirectResponse



# ============================================================================
# DEALS (Object-oriented finance - Сделки)
# ============================================================================

# @rt("/deals")
def get(session, status_filter: str = None):
    """Redirect /deals to /finance — deals list is now accessed via finance page."""
    if status_filter:
        return RedirectResponse(f"/finance?tab=workspace&status_filter={status_filter}", status_code=301)
    return RedirectResponse("/finance", status_code=301)


# ============================================================================
# PAYMENTS CALENDAR (Object-oriented finance - Календарь платежей)
# ============================================================================

# @rt("/payments/calendar")
def get(session):
    """Payment calendar page."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["finance", "admin", "top_manager"]):
        return RedirectResponse("/unauthorized", status_code=303)

    content = finance_calendar_tab(session, user, org_id)

    # Design system header
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    return page_layout("Календарь платежей",
        # Header card with gradient
        Div(
            Div(
                icon("calendar", size=24, color="#475569"),
                Span(" Календарь платежей", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                style="display: flex; align-items: center;"
            ),
            P("Планируемые и выполненные платежи",
              style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;"),
            style=header_card_style
        ),
        content,
        session=session,
        current_path="/payments/calendar"
    )

# ============================================================================
# FINANCE WORKSPACE (Features #77-80)
# ============================================================================

# @rt("/finance")
def get(session, tab: str = "workspace", status_filter: str = None, view: str = "full", groups: str = None, payment_type: str = "all", payment_status: str = "all", date_from: str = "", date_to: str = "", deal_filter: str = "", customer_filter: str = ""):
    """
    Finance page with tabs: Workspace, ERPS, Payments

    Tabs:
    - workspace: Shows active deals and plan-fact management
    - erps: Единый реестр подписанных спецификаций (with configurable views)
    - payments: Unified payments tab across all deals

    ERPS Views:
    - full: All 30 columns
    - compact: Key columns only (8)
    - finance: Spec + Finance + Management blocks
    - logistics: Key + Logistics + Delivery periods
    - procurement: Key + Procurement + Auto-calculated payments
    - custom: User-selected column groups
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has finance role
    if not user_has_any_role(session, ["finance", "admin", "top_manager"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Tab navigation with design system styling
    tabs_style = """
        .finance-tabs {
            display: flex;
            gap: 4px;
            padding: 12px 16px 0 16px;
            margin-bottom: 20px;
            border-bottom: 1px solid #e2e8f0;
            background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
            border-radius: 12px 12px 0 0;
        }
        .finance-tab {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 18px;
            font-size: 13px;
            font-weight: 500;
            text-decoration: none;
            border-radius: 8px 8px 0 0;
            transition: background-color 0.15s ease, color 0.15s ease;
            border: 1px solid transparent;
            border-bottom: none;
            margin-bottom: -1px;
            color: #64748b;
            background: transparent;
        }
        .finance-tab:hover {
            color: #1e293b;
            background: rgba(255,255,255,0.5);
        }
        .finance-tab.active {
            color: #1e293b;
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border-color: #e2e8f0;
            font-weight: 600;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.04);
        }
    """

    tabs = Div(
        Style(tabs_style),
        Div(
            A(icon("briefcase", size=16), " Рабочая зона",
              href="/finance?tab=workspace",
              cls="finance-tab" + (" active" if tab == "workspace" else "")),
            A(icon("table", size=16), " Контроль платежей",
              href="/finance?tab=erps",
              cls="finance-tab" + (" active" if tab == "erps" else "")),
            A(icon("credit-card", size=16), " Платежи",
              href='/finance?tab=payments',
              cls="finance-tab" + (" active" if tab == 'payments' else "")),
            A(icon("file-text", size=16), " Инвойсы",
              href="/finance?tab=invoices",
              cls="finance-tab" + (" active" if tab == "invoices" else "")),
            cls="finance-tabs"
        )
    )

    # Render selected tab
    if tab == "erps":
        content = finance_erps_tab(session, user, org_id, view=view, custom_groups=groups)
    elif tab == 'payments':
        content = finance_payments_tab(session, user, org_id, payment_type=payment_type, payment_status=payment_status, date_from=date_from, date_to=date_to, deal_filter=deal_filter, customer_filter=customer_filter, view=view)
    elif tab == "calendar":
        content = finance_calendar_tab(session, user, org_id)
    elif tab == "invoices":
        content = finance_invoices_tab(session, user, org_id)
    else:
        content = finance_workspace_tab(session, user, org_id, status_filter)

    # Design system header
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    return page_layout("Финансы",
        # Header card with gradient
        Div(
            Div(
                icon("wallet", size=24, color="#475569"),
                Span(" Финансы", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                style="display: flex; align-items: center;"
            ),
            P("Сделки, Контроль платежей и календарь платежей",
              style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;"),
            style=header_card_style
        ),
        tabs,
        content,
        session=session
    )


def finance_workspace_tab(session, user, org_id, status_filter=None):
    """Finance workspace tab - shows active deals"""
    supabase = get_supabase()

    # Get deal statistics
    stats = {
        "active": 0,
        "completed": 0,
        "cancelled": 0,
        "total": 0,
        "active_amount": 0.0,
        "completed_amount": 0.0,
    }

    try:
        # Count deals by status
        for status in ["active", "completed", "cancelled"]:
            count_result = supabase.table("deals").select("id", count="exact") \
                .eq("organization_id", org_id) \
                .eq("status", status) \
                .is_("deleted_at", None) \
                .execute()
            stats[status] = count_result.count or 0

        stats["total"] = stats["active"] + stats["completed"] + stats["cancelled"]

        # Sum amounts for active deals
        active_result = supabase.table("deals").select("total_amount") \
            .eq("organization_id", org_id) \
            .eq("status", "active") \
            .is_("deleted_at", None) \
            .execute()
        if active_result.data:
            stats["active_amount"] = sum(float(d.get("total_amount", 0) or 0) for d in active_result.data)

        # Sum amounts for completed deals
        completed_result = supabase.table("deals").select("total_amount") \
            .eq("organization_id", org_id) \
            .eq("status", "completed") \
            .is_("deleted_at", None) \
            .execute()
        if completed_result.data:
            stats["completed_amount"] = sum(float(d.get("total_amount", 0) or 0) for d in completed_result.data)

    except Exception as e:
        print(f"Error getting deal stats: {e}")

    # Get deals with details based on filter
    target_status = status_filter if status_filter and status_filter != "all" else None

    try:
        query = supabase.table("deals").select(
            # FK hints resolve ambiguity: !specifications(deals_specification_id_fkey), !quotes(deals_quote_id_fkey)
            "id, deal_number, signed_at, total_amount, currency, status, created_at, "
            "specifications!deals_specification_id_fkey(id, specification_number, proposal_idn), "
            "quotes!deals_quote_id_fkey(id, idn_quote, customers(name))"
        ).eq("organization_id", org_id)

        if target_status:
            query = query.eq("status", target_status)

        deals_result = query.order("signed_at", desc=True).limit(100).is_("deleted_at", None).execute()
        deals = deals_result.data or []
    except Exception as e:
        print(f"Error getting deals: {e}")
        deals = []

    # Separate deals by status for display
    active_deals = [d for d in deals if d.get("status") == "active"]
    completed_deals = [d for d in deals if d.get("status") == "completed"]
    cancelled_deals = [d for d in deals if d.get("status") == "cancelled"]

    # Status badge helper
    def deal_status_badge(status):
        status_map = {
            "active": ("В работе", "status-success"),
            "completed": ("Завершена", "status-info"),
            "cancelled": ("Отменена", "status-error"),
        }
        label, cls_name = status_map.get(status, (status, "status-neutral"))
        return Span(label, cls=f"status-badge {cls_name}")

    # Deal row helper
    def deal_row(deal):
        spec = deal.get("specifications", {}) or {}
        quote = deal.get("quotes", {}) or {}
        customer = quote.get("customers", {}) or {}
        customer_name = customer.get("name", "Неизвестно")

        # Format amount
        amount = float(deal.get("total_amount", 0) or 0)
        currency = deal.get("currency", "RUB")
        amount_str = f"{amount:,.2f} {currency}"

        # Format date
        signed_at = format_date_russian(deal.get("signed_at")) if deal.get("signed_at") else "-"

        return Tr(
            Td(A(deal.get("deal_number", "-"), href=f"/finance/{deal['id']}", style="color: var(--accent); font-weight: 500;")),
            Td(spec.get("specification_number", "-") or spec.get("proposal_idn", "-")),
            Td(customer_name),
            Td(amount_str, cls="col-money"),
            Td(signed_at),
            Td(deal_status_badge(deal.get("status", "active"))),
            Td(
                A(icon("eye", size=16), href=f"/finance/{deal['id']}", title="Подробнее", cls="table-action-btn"),
                cls="col-actions"
            ),
            cls="clickable-row",
            onclick=f"window.location='/finance/{deal['id']}'"
        )

    # Build deals table
    def deals_table(deals_list, title, status_color):
        if not deals_list:
            return Div(
                H4(f"{title} (0)", style=f"color: {status_color}; margin-bottom: 0.5rem;"),
                P("Нет сделок", style="color: #666; font-style: italic;"),
                style="margin-bottom: 1.5rem;"
            )

        return Div(
            H4(f"{title} ({len(deals_list)})", style=f"color: {status_color}; margin-bottom: 0.75rem;"),
            Div(
                Div(
                    Table(
                        Thead(
                            Tr(
                                Th("№ СДЕЛКИ"),
                                Th("№ СПЕЦИФИКАЦИИ"),
                                Th("КЛИЕНТ"),
                                Th("СУММА", cls="col-money"),
                                Th("ДАТА"),
                                Th("СТАТУС"),
                                Th("", cls="col-actions"),
                            )
                        ),
                        Tbody(*[deal_row(d) for d in deals_list]),
                        cls="unified-table"
                    ),
                    cls="table-responsive"
                ),
                cls="table-container", style="margin: 0; margin-bottom: 1.5rem;"
            )
        )

    # Build filter buttons
    filter_buttons = Div(
        btn_link("Все", href="/finance", variant="primary" if not status_filter or status_filter == "all" else "secondary"),
        btn_link("В работе", href="/finance?status_filter=active", variant="success" if status_filter == "active" else "secondary"),
        btn_link("Завершённые", href="/finance?status_filter=completed", variant="primary" if status_filter == "completed" else "secondary"),
        btn_link("Отменённые", href="/finance?status_filter=cancelled", variant="danger" if status_filter == "cancelled" else "secondary"),
        style="margin-bottom: 1.5rem; display: flex; gap: 0.5rem;"
    )

    # Show appropriate table based on filter
    if status_filter == "active":
        deals_section = deals_table(active_deals, "Сделки в работе", "#10b981")
    elif status_filter == "completed":
        deals_section = deals_table(completed_deals, "Завершённые сделки", "#3b82f6")
    elif status_filter == "cancelled":
        deals_section = deals_table(cancelled_deals, "Отменённые сделки", "#ef4444")
    else:
        # Show all (active first, then completed, then cancelled)
        deals_section = Div(
            deals_table(active_deals, "Сделки в работе", "#10b981") if active_deals else "",
            deals_table(completed_deals, "Завершённые сделки", "#3b82f6") if completed_deals else "",
            deals_table(cancelled_deals, "Отменённые сделки", "#ef4444") if cancelled_deals else "",
        )

    return Div(
        # Stats cards
        Div(
            Div(
                Div(str(stats["active"]), cls="stat-value", style="color: #10b981;"),
                Div("В работе", style="font-size: 0.875rem;"),
                Div(f"{stats['active_amount']:,.0f} ₽", style="font-size: 0.75rem; color: #666;"),
                cls="stat-card",
                style="border-left: 4px solid #10b981;" if stats["active"] > 0 else ""
            ),
            Div(
                Div(str(stats["completed"]), cls="stat-value", style="color: #3b82f6;"),
                Div("Завершено", style="font-size: 0.875rem;"),
                Div(f"{stats['completed_amount']:,.0f} ₽", style="font-size: 0.75rem; color: #666;"),
                cls="stat-card"
            ),
            Div(
                Div(str(stats["cancelled"]), cls="stat-value", style="color: #ef4444;"),
                Div("Отменено", style="font-size: 0.875rem;"),
                cls="stat-card"
            ),
            Div(
                Div(str(stats["total"]), cls="stat-value", style="color: #6b7280;"),
                Div("Всего сделок", style="font-size: 0.875rem;"),
                Div(f"{stats['active_amount'] + stats['completed_amount']:,.0f} ₽", style="font-size: 0.75rem; color: #666;"),
                cls="stat-card"
            ),
            cls="stats-grid",
            style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem;"
        ),

        # Filter buttons
        filter_buttons,

        # Deals section
        deals_section
    )


# ERPS Column definitions by group
ERPS_COLUMN_GROUPS = {
    'spec': {
        'label': 'Спецификация',
        'color': '#fef3c7',
        'columns': [
            # IDN and Client are sticky - always visible, handled separately
            ('sign_date', 'Дата подписания', 'date', None),
            ('deal_type', 'Тип сделки', 'text', None),
            ('payment_terms', 'Условия оплаты', 'text', None),
            ('advance_percent', 'Аванс %', 'percent', None),
            ('payment_deferral_days', 'Отсрочка, дни', 'text', None),
            ('spec_sum_usd', 'Сумма спец. USD', 'money', 'text-align: right; font-weight: 500;'),
            ('spec_profit_usd', 'Профит USD', 'money', 'text-align: right;'),
            ('delivery_deadline', 'Крайний срок поставки', 'date', None),
            ('advance_payment_deadline', 'Крайний срок оплаты аванса', 'date', None),
        ]
    },
    'auto': {
        'label': 'Авто-расчетные',
        'color': '#e9d5ff',
        'columns': [
            ('days_until_advance', 'Остаток дней до аванса', 'number', 'text-align: right;'),
            ('days_until_next_payment', 'Дней до след. платежа', 'number', 'text-align: right;'),
            ('planned_advance_usd', 'Планируемая сумма аванса USD', 'money', 'text-align: right;'),
            ('total_paid_usd', 'Всего оплачено USD', 'money', 'text-align: right;'),
            ('remaining_payment_usd', 'Остаток к оплате USD', 'money', 'text-align: right; color: #dc2626;'),
            ('remaining_payment_percent', 'Остаток %', 'percent', 'text-align: right;'),
            ('days_waiting_payment', 'Дней ожидания оплаты', 'days_waiting', 'text-align: right;'),
            ('delivery_period_calendar_days', 'Срок поставки, к.д.', 'number', 'text-align: right;'),
            ('delivery_period_working_days', 'Срок поставки, р.д.', 'number', 'text-align: right;'),
        ]
    },
    'finance': {
        'label': 'Финансы',
        'color': '#fecdd3',
        'columns': [
            ('advance_payment_date', 'Дата оплаты аванса', 'date', None),
            ('last_payment_date', 'Дата последней оплаты', 'date', None),
            ('comment', 'Комментарий', 'text', 'max-width: 200px; overflow: hidden; text-overflow: ellipsis;'),
        ]
    },
    'procurement': {
        'label': 'Закупки',
        'color': '#bfdbfe',
        'columns': [
            ('supplier_payment_date', 'Дата оплаты поставщику', 'date', None),
            ('total_spent_usd', 'Всего потрачено USD', 'money', 'text-align: right;'),
        ]
    },
    'logistics': {
        'label': 'Логистика',
        'color': '#ddd6fe',
        'columns': [
            ('planned_delivery_date', 'Планируемая дата доставки', 'date', None),
            ('actual_delivery_date', 'Фактическая дата доставки', 'date', None),
            ('planned_dovoz_date', 'Планируемая дата довоза', 'date', None),
        ]
    },
    'management': {
        'label': 'Руководство',
        'color': '#fecdd3',
        'columns': [
            ('priority_tag', 'Тег приоритетности', 'priority', None),
            ('actual_profit_usd', 'Фактический профит USD', 'money', 'text-align: right;'),
        ]
    },
    'system': {
        'label': 'Системные',
        'color': '#e5e7eb',
        'columns': [
            ('created_at', 'Дата создания', 'date', None),
            ('updated_at', 'Дата изменения', 'date', None),
        ]
    },
}

# Predefined views with groups to show
ERPS_VIEWS = {
    'full': ['spec', 'auto', 'finance', 'procurement', 'logistics', 'management', 'system'],
    'compact': ['spec'],  # Will be further filtered to key columns only
    'finance': ['spec', 'auto', 'finance', 'management'],
    'logistics': ['spec', 'auto', 'logistics'],
    'procurement': ['spec', 'auto', 'procurement'],
}

# Compact view shows only these specific columns from spec group
ERPS_COMPACT_COLUMNS = ['sign_date', 'spec_sum_usd', 'spec_profit_usd', 'total_paid_usd', 'remaining_payment_usd', 'days_waiting_payment', 'days_until_next_payment', 'priority_tag']


def fmt_days_until_payment(days):
    """Color-coded badge for days until advance payment deadline.

    - days > 7: green badge (safe zone)
    - 1 <= days <= 7: yellow/amber badge (urgent zone)
    - days <= 0: red badge with 'ПРОСРОЧЕНО' and abs(days)
    - days is None: gray '-'
    """
    if days is None:
        return Span("-", style="color: #9ca3af;")
    days_int = int(days)
    if days_int > 7:
        return Span(
            f"{days_int} дн.",
            style="display: inline-block; padding: 2px 8px; border-radius: 12px; "
                  "background: #d1fae5; color: #059669; font-weight: 600; font-size: 0.7rem;"
        )
    elif days_int > 0:
        return Span(
            f"{days_int} дн.",
            style="display: inline-block; padding: 2px 8px; border-radius: 12px; "
                  "background: #fef3c7; color: #d97706; font-weight: 600; font-size: 0.7rem;"
        )
    else:
        overdue_days = abs(days_int)
        return Span(
            f"ПРОСРОЧЕНО {overdue_days} дн.",
            style="display: inline-block; padding: 2px 8px; border-radius: 12px; "
                  "background: #fee2e2; color: #dc2626; font-weight: 600; font-size: 0.7rem;"
        )


def fmt_remaining_payment_with_percent(remaining_usd, total_usd):
    """Format remaining payment as '$X,XXX.XX (XX.X%)' with color coding.

    Color thresholds based on remaining/total ratio:
    - > 50%: red (high debt)
    - 20-50%: amber/yellow (medium debt)
    - <= 20%: green (mostly paid)
    - None/zero total: gray '-'
    """
    if remaining_usd is None or total_usd is None or total_usd == 0:
        return Span("-", style="color: #9ca3af;")
    remaining_val = float(remaining_usd)
    total_val = float(total_usd)
    if total_val <= 0:
        return Span("-", style="color: #9ca3af;")
    pct = (remaining_val / total_val) * 100
    text = f"${remaining_val:,.2f} ({pct:.1f}%)"
    if pct > 50:
        color = "#dc2626"
    elif pct > 20:
        color = "#d97706"
    else:
        color = "#059669"
    return Span(text, style=f"color: {color}; font-weight: 500; font-size: 0.7rem;")


def fmt_days_waiting_payment(days, remaining_usd):
    """Color-coded badge for days waiting for payment.

    Shows how many days since an expected payment was not received.
    - days is None and remaining <= 0: "Оплачено" green badge
    - days is None and remaining > 0: "-" (no overdue items yet)
    - days < 30: green badge (recently overdue)
    - 30 <= days < 60: yellow/amber badge (moderately overdue)
    - days >= 60: red badge (critically overdue)
    """
    # If fully paid (no remaining balance), show "Оплачено"
    remaining_val = float(remaining_usd) if remaining_usd is not None else 0
    if remaining_val <= 0:
        return Span(
            "Оплачено",
            style="display: inline-block; padding: 2px 8px; border-radius: 12px; "
                  "background: #d1fae5; color: #059669; font-weight: 600; font-size: 0.65rem;"
        )
    # No overdue payments yet (but still has remaining balance)
    if days is None:
        return Span("—", style="color: #9ca3af;")
    days_int = int(days)
    if days_int < 30:
        return Span(
            f"{days_int} дн.",
            style="display: inline-block; padding: 2px 8px; border-radius: 12px; "
                  "background: #d1fae5; color: #059669; font-weight: 600; font-size: 0.7rem;"
        )
    elif days_int < 60:
        return Span(
            f"{days_int} дн.",
            style="display: inline-block; padding: 2px 8px; border-radius: 12px; "
                  "background: #fef3c7; color: #d97706; font-weight: 600; font-size: 0.7rem;"
        )
    else:
        return Span(
            f"{days_int} дн.",
            style="display: inline-block; padding: 2px 8px; border-radius: 12px; "
                  "background: #fee2e2; color: #dc2626; font-weight: 600; font-size: 0.7rem;"
        )


def finance_erps_tab(session, user, org_id, view: str = "full", custom_groups: str = None):
    """ERPS tab - Единый реестр подписанных спецификаций with configurable views"""
    supabase = get_supabase()

    # Fetch data from erps_registry view
    try:
        result = supabase.from_("erps_registry").select("*").execute()
        specs = result.data or []
    except Exception as e:
        print(f"Error fetching ERPS data: {e}")
        specs = []

    # Helper formatters
    def fmt_money(value):
        if value is None or value == 0:
            return "—"
        return f"${value:,.2f}"

    def fmt_date(value):
        if not value:
            return "-"
        return format_date_russian(value)

    def fmt_percent(value):
        if value is None:
            return "-"
        return f"{value:.1f}%"

    def fmt_priority(value):
        if not value:
            return "-"
        labels = {'important': 'Важно', 'normal': 'Обычно', 'problem': 'Проблема'}
        return labels.get(value, value)

    def format_value(value, fmt_type):
        if fmt_type == 'money':
            return fmt_money(value)
        elif fmt_type == 'date':
            return fmt_date(value)
        elif fmt_type == 'percent':
            return fmt_percent(value)
        elif fmt_type == 'priority':
            return fmt_priority(value)
        elif fmt_type == 'number':
            return str(value) if value is not None else '-'
        else:
            return str(value) if value else '-'

    # Determine which groups to show
    if view == 'custom' and custom_groups:
        import json
        try:
            visible_groups = json.loads(custom_groups)
            active_groups = [g for g, enabled in visible_groups.items() if enabled]
        except:
            active_groups = list(ERPS_COLUMN_GROUPS.keys())
    elif view == 'compact':
        # Compact view iterates ALL groups but filters to specific columns
        active_groups = list(ERPS_COLUMN_GROUPS.keys())
    elif view in ERPS_VIEWS:
        active_groups = ERPS_VIEWS[view]
    else:
        active_groups = ERPS_VIEWS['full']

    # Build column list based on view
    columns = []
    for group_key in active_groups:
        if group_key not in ERPS_COLUMN_GROUPS:
            continue
        group = ERPS_COLUMN_GROUPS[group_key]
        group_color = group['color']
        group_columns_filtered = []
        for col_key, col_label, col_type, col_style in group['columns']:
            # For compact view, only show specific columns
            if view == 'compact' and col_key not in ERPS_COMPACT_COLUMNS:
                continue
            group_columns_filtered.append({
                'key': col_key,
                'label': col_label,
                'type': col_type,
                'style': col_style,
                'color': group_color,
                'group': group_key,
                'is_last_in_group': False
            })
        # Mark the last column of this group
        if group_columns_filtered:
            group_columns_filtered[-1]['is_last_in_group'] = True
            columns.extend(group_columns_filtered)

    # CSS for sticky columns and view selector
    erps_css = """
        .erps-table-container {
            overflow-x: auto;
            max-width: 100%;
            position: relative;
        }
        .erps-table {
            border-collapse: separate;
            border-spacing: 0;
            font-size: 0.72rem;
        }
        /* All columns fixed width */
        .erps-table th, .erps-table td {
            padding: 0.3rem 0.4rem;
            border-bottom: 1px solid #e5e7eb;
            border-right: 1px solid #f0f0f0;
            text-align: center;
            width: 75px;
            min-width: 75px;
            max-width: 75px;
            box-sizing: border-box;
        }
        /* Vertical headers */
        .erps-table th {
            font-weight: 600;
            height: 130px;
            vertical-align: bottom;
            padding-bottom: 8px;
            position: relative;
        }
        .erps-table th .th-text {
            writing-mode: vertical-lr;
            transform: rotate(180deg);
            display: inline-block;
            white-space: nowrap;
            font-size: 0.68rem;
            letter-spacing: -0.02em;
            max-height: 120px;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        /* Data cells styling */
        .erps-table td {
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        /* Money columns - right align, bold */
        .erps-table td.col-money {
            text-align: right;
            font-weight: 500;
        }
        /* Percent columns */
        .erps-table td.col-percent {
            text-align: right;
        }
        /* Date columns - smaller font */
        .erps-table td.col-date {
            font-size: 0.65rem;
        }
        /* Number columns */
        .erps-table td.col-number {
            text-align: right;
        }
        /* Row hover */
        .erps-table tbody tr:hover td {
            background-color: #f0f9ff !important;
        }
        /* Sticky columns: IDN */
        .erps-table th.sticky-idn,
        .erps-table td.sticky-idn {
            position: sticky !important;
            left: 0 !important;
            z-index: 20 !important;
            background: #fef3c7 !important;
            width: 85px;
            min-width: 85px;
            max-width: 85px;
            text-align: left;
            font-weight: 600;
            box-shadow: 2px 0 4px -2px rgba(0,0,0,0.15);
        }
        .erps-table th.sticky-idn {
            vertical-align: middle;
            height: auto;
            padding: 0.5rem;
        }
        .erps-table th.sticky-idn .th-text {
            writing-mode: horizontal-tb;
            transform: none;
        }
        /* Sticky columns: Client */
        .erps-table th.sticky-client,
        .erps-table td.sticky-client {
            position: sticky !important;
            left: 85px !important;
            z-index: 20 !important;
            background: #fffbeb !important;
            width: 110px;
            min-width: 110px;
            max-width: 110px;
            text-align: left;
        }
        .erps-table th.sticky-client {
            vertical-align: middle;
            height: auto;
            padding: 0.5rem;
        }
        .erps-table th.sticky-client .th-text {
            writing-mode: horizontal-tb;
            transform: none;
        }
        /* Sticky columns: Action (+ button) */
        .erps-table th.sticky-action,
        .erps-table td.sticky-action {
            position: sticky !important;
            left: 195px !important;
            z-index: 20 !important;
            background: #f0fdf4 !important;
            width: 40px;
            min-width: 40px;
            max-width: 40px;
            text-align: center;
            border-right: 2px solid #d97706;
            box-shadow: 4px 0 6px -2px rgba(0,0,0,0.2);
        }
        .erps-table th.sticky-action {
            vertical-align: middle;
            height: auto;
            padding: 0.5rem;
        }
        .erps-table th.sticky-idn,
        .erps-table th.sticky-client,
        .erps-table th.sticky-action {
            z-index: 25 !important;
        }
        /* View selector styles */
        .view-selector {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .view-btn {
            padding: 0.4rem 0.8rem;
            border: 1px solid #d1d5db;
            border-radius: 0.375rem;
            text-decoration: none;
            color: #374151;
            font-size: 0.875rem;
            background: white;
            transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
        }
        .view-btn:hover {
            background: #f3f4f6;
            border-color: #9ca3af;
        }
        .view-btn.active {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }
        .group-toggles {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem;
            background: #f9fafb;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .group-toggle {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
            cursor: pointer;
        }
        .group-toggle input {
            margin: 0;
        }
        /* Block dividers - thick border at end of each column group */
        .erps-table th.block-end,
        .erps-table td.block-end {
            border-right: 2px solid #9ca3af !important;
        }
    """

    # View selector buttons
    view_labels = [
        ('full', 'Полный'),
        ('compact', 'Компактный'),
        ('finance', 'Финансы'),
        ('logistics', 'Логистика'),
        ('procurement', 'Закупки'),
        ('custom', 'Кастомный'),
    ]

    view_buttons = [
        A(label,
          href=f"/finance?tab=erps&view={key}",
          cls="view-btn" + (" active" if view == key else ""))
        for key, label in view_labels
    ]

    # Group toggles for custom view (shown only when custom is selected)
    group_toggles = None
    if view == 'custom':
        # Parse current custom groups or default to all enabled
        import json
        try:
            current_groups = json.loads(custom_groups) if custom_groups else {}
        except:
            current_groups = {}

        # Default all groups to enabled if not specified
        for gk in ERPS_COLUMN_GROUPS.keys():
            if gk not in current_groups:
                current_groups[gk] = True

        toggle_items = []
        for group_key, group_data in ERPS_COLUMN_GROUPS.items():
            is_checked = current_groups.get(group_key, True)
            toggle_items.append(
                Label(
                    Input(
                        type="checkbox",
                        checked=is_checked,
                        data_group=group_key,
                        cls="group-checkbox"
                    ),
                    f" {group_data['label']}",
                    cls="group-toggle",
                    style=f"background: {group_data['color']};"
                )
            )

        group_toggles = Div(
            Span("Показать блоки:", style="font-weight: 500; margin-right: 0.5rem;"),
            *toggle_items,
            cls="group-toggles",
            id="group-toggles"
        )

    # JavaScript for custom view toggling
    custom_js = Script("""
        document.addEventListener('DOMContentLoaded', function() {
            // Handle group checkbox changes
            document.querySelectorAll('.group-checkbox').forEach(function(checkbox) {
                checkbox.addEventListener('change', function() {
                    updateCustomView();
                });
            });
        });

        function updateCustomView() {
            const groups = {};
            document.querySelectorAll('.group-checkbox').forEach(function(checkbox) {
                groups[checkbox.dataset.group] = checkbox.checked;
            });
            // Save to localStorage
            localStorage.setItem('erps_custom_groups', JSON.stringify(groups));
            // Reload with new groups
            window.location.href = '/finance?tab=erps&view=custom&groups=' + encodeURIComponent(JSON.stringify(groups));
        }

        // On page load, check if we should apply saved custom groups
        (function() {
            const urlParams = new URLSearchParams(window.location.search);
            const view = urlParams.get('view');
            if (view === 'custom' && !urlParams.has('groups')) {
                const savedGroups = localStorage.getItem('erps_custom_groups');
                if (savedGroups) {
                    window.location.href = '/finance?tab=erps&view=custom&groups=' + encodeURIComponent(savedGroups);
                }
            }
        })();
    """)

    # Build table headers with vertical text - add action column
    header_cells = [
        Th(Span("IDN", cls="th-text"), cls="sticky-idn", style="background: #fef3c7;"),
        Th(Span("Клиент", cls="th-text"), cls="sticky-client"),
        # Action column header (sticky, right after IDN and Client)
        Th(Span("+", cls="th-text"), cls="sticky-action"),
    ]
    for col in columns:
        cell_style = f"background: {col['color']};"
        cell_cls = "block-end" if col.get('is_last_in_group') else ""
        # Wrap label in span for vertical text
        header_cells.append(Th(Span(col['label'], cls="th-text"), style=cell_style, cls=cell_cls))

    # Map column types to CSS classes
    type_to_class = {
        'money': 'col-money',
        'percent': 'col-percent',
        'date': 'col-date',
        'number': 'col-number',
    }

    # Build table rows - clickable rows with action button
    rows = []
    for spec in specs:
        deal_id = spec.get('deal_id', '')
        row_click_url = f"/finance/{deal_id}?tab=plan-fact" if deal_id else ""
        # Action cell - "Add payment" button (sticky, right after IDN and Client)
        if deal_id:
            erps_pay_path = "new?source=erps"
            erps_pay_url = f"/finance/{deal_id}/payments/{erps_pay_path}"
            action_btn = Button(
                icon("plus", size=12),
                hx_get=erps_pay_url,
                hx_target="#erps-payment-modal-body",
                hx_swap="innerHTML",
                onclick="event.stopPropagation(); document.getElementById('erps-payment-modal').style.display='flex';",
                title="Добавить платёж",
                style="background: #10b981; color: white; border: none; border-radius: 4px; padding: 2px 6px; cursor: pointer; font-size: 11px; line-height: 1;"
            )
        else:
            action_btn = ""

        row_cells = [
            Td(spec.get('idn', '-'), cls="sticky-idn"),
            Td(spec.get('client_name', '-'), cls="sticky-client"),
            Td(action_btn, cls="sticky-action"),
        ]
        # Columns that represent profit and should use conditional coloring
        profit_columns = {'spec_profit_usd', 'actual_profit_usd'}
        for col in columns:
            col_key = col['key']
            value = spec.get(col_key)
            if col_key == 'days_until_advance':
                formatted = fmt_days_until_payment(value)
            elif col_key == 'days_until_next_payment':
                formatted = fmt_days_until_payment(value)
            elif col_key == 'days_waiting_payment':
                formatted = fmt_days_waiting_payment(value, spec.get('remaining_payment_usd'))
            elif col_key == 'remaining_payment_usd':
                formatted = fmt_remaining_payment_with_percent(value, spec.get('spec_sum_usd'))
            else:
                formatted = format_value(value, col['type'])
            cell_style = f"background: {col['color']};"
            # Apply profit coloring for profit columns
            if col_key in profit_columns:
                cell_style += f" color: {profit_color(value)}; font-weight: 500;"
            cell_cls = type_to_class.get(col['type'], '')
            if col.get('is_last_in_group'):
                cell_cls = f"{cell_cls} block-end" if cell_cls else "block-end"
            row_cells.append(Td(formatted, style=cell_style, cls=cell_cls))

        row_style = f"cursor: pointer;" if deal_id else ""
        row_onclick = f"window.location.href='{row_click_url}';" if deal_id else ""
        rows.append(Tr(*row_cells, style=row_style, onclick=row_onclick))

    # Calculate summary footer totals
    total_outstanding = sum(
        float(s.get('remaining_payment_usd') or 0) for s in specs
    )
    overdue_count = len([
        s for s in specs
        if s.get('days_until_advance') is not None
        and s['days_until_advance'] <= 0
    ])
    urgent_count = len([
        s for s in specs
        if s.get('days_until_advance') is not None
        and 1 <= s['days_until_advance'] <= 7
    ])

    # Include action column in colspan
    colspan_total = str(3 + len(columns))
    tfoot_style = "padding: 0.5rem 0.6rem; font-size: 0.75rem; border-top: 2px solid #e5e7eb;"
    summary_footer = Tfoot(
        Tr(
            Td(
                Strong("ИТОГО К ПОЛУЧЕНИЮ:"),
                style=f"{tfoot_style} text-align: left;"
            ),
            Td(
                Strong(f"${total_outstanding:,.2f}"),
                colspan=str(int(colspan_total) - 1),
                style=f"{tfoot_style} text-align: left; color: #dc2626;"
            ),
        ),
        Tr(
            Td(
                Strong("ПРОСРОЧЕНО:"),
                style=f"{tfoot_style} text-align: left;"
            ),
            Td(
                Strong(str(overdue_count)),
                colspan=str(int(colspan_total) - 1),
                style=f"{tfoot_style} text-align: left; color: #dc2626;"
            ),
        ),
        Tr(
            Td(
                Strong("СРОЧНО (1-7 дней):"),
                style=f"{tfoot_style} text-align: left;"
            ),
            Td(
                Strong(str(urgent_count)),
                colspan=str(int(colspan_total) - 1),
                style=f"{tfoot_style} text-align: left; color: #d97706;"
            ),
        ),
    )

    # Build table
    if specs:
        table = Table(
            Thead(Tr(*header_cells)),
            Tbody(*rows),
            summary_footer,
            cls="erps-table"
        )
    else:
        colspan = 3 + len(columns)
        table = Table(
            Thead(Tr(*header_cells)),
            Tbody(Tr(Td("Нет данных", colspan=str(colspan), style="text-align: center; padding: 2rem; color: #666;"))),
            cls="erps-table"
        )

    # Modal CSS for payment form
    modal_css = """
        #erps-payment-modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        #erps-payment-modal .modal-content {
            background: white;
            border-radius: 12px;
            padding: 24px;
            max-width: 520px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .erps-action-cell {
            position: relative;
            z-index: 5;
        }
    """

    # Payment modal overlay (hidden by default, populated via HTMX)
    payment_modal = Div(
        Div(
            Div(
                Div(
                    H3("Добавить платёж", style="margin: 0; font-size: 16px; font-weight: 600; color: #1e293b;"),
                    Button(
                        icon("x", size=16),
                        onclick="document.getElementById('erps-payment-modal').style.display='none';",
                        style="background: none; border: none; cursor: pointer; color: #64748b; padding: 4px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;"
                ),
                Div(id="erps-payment-modal-body"),
                cls="modal-content"
            ),
            onclick="if(event.target===this) this.style.display='none';",
            style="display: flex; justify-content: center; align-items: center; width: 100%; height: 100%;"
        ),
        id="erps-payment-modal",
    )

    # Export placeholder button
    export_btn = Button(
        icon("download", size=14),
        " Выгрузить данные",
        disabled=True,
        title="В разработке",
        style="background: white; color: #94a3b8; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 14px; font-size: 13px; cursor: not-allowed; display: inline-flex; align-items: center; gap: 6px;"
    )

    # Build complete UI
    return Div(
        Style(erps_css),
        Style(modal_css),
        custom_js,
        Div(
            H2("Контроль платежей", style="margin-bottom: 0;"),
            export_btn,
            style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"
        ),

        # View selector
        Div(
            Span("Вид:", style="font-weight: 500; margin-right: 0.5rem;"),
            *view_buttons,
            cls="view-selector"
        ),

        # Group toggles (only for custom view)
        group_toggles if group_toggles else "",

        # Stats
        P(f"Всего спецификаций: {len(specs)} | Колонок: {2 + len(columns)}", style="margin-bottom: 1rem; color: #666; font-size: 0.875rem;"),

        # Table
        Div(table, cls="erps-table-container"),

        # Payment modal
        payment_modal,
    )


def render_payments_grouped(items):
    """Render payments grouped by customer with subtotals per customer group."""
    from collections import defaultdict

    # Group items by customer name from deal chain
    customer_groups = defaultdict(list)
    for item in items:
        deals = item.get("deals") or {}
        specs = deals.get("specifications") or {}
        quotes = specs.get("quotes") or {}
        customers = quotes.get("customers") or {}
        customer_name = customers.get("name", "Неизвестно")
        customer_groups[customer_name].append(item)

    rows = []
    for customer_name, group_items in sorted(customer_groups.items()):
        # Calculate subtotals for this customer
        subtotal_planned = sum(float(i.get("planned_amount") or 0) for i in group_items)
        subtotal_actual = sum(float(i.get("actual_amount") or 0) for i in group_items if i.get("actual_amount") is not None)

        # Customer header row (collapsed summary)
        rows.append(
            Tr(
                Td(Strong(customer_name), colspan="4", style="background: #f8fafc; font-weight: 600; color: #1e293b;"),
                Td(Span(f"{len(group_items)} записей", style="font-size: 0.8rem; color: #64748b;"), style="background: #f8fafc;"),
                Td(f"{subtotal_planned:,.0f} ₽", style="background: #f8fafc; text-align: right; font-weight: 600;"),
                Td(f"{subtotal_actual:,.0f} ₽", style="background: #f8fafc; text-align: right; font-weight: 600;"),
                Td("", style="background: #f8fafc;"),
                Td("", style="background: #f8fafc;"),
                style="border-top: 2px solid #e2e8f0;"
            )
        )

        # Individual items in this group
        for item in group_items:
            cat = item.get("plan_fact_categories") or {}
            is_income = cat.get("is_income", False)
            deals_data = item.get("deals") or {}
            deal_id = deals_data.get("id", "")
            deal_number = deals_data.get("deal_number", "—")

            planned_amt = float(item.get("planned_amount") or 0)
            actual_amt = item.get("actual_amount")
            actual_amt_str = f"{float(actual_amt):,.0f} ₽" if actual_amt is not None else "—"
            variance = item.get("variance_amount")
            variance_str = f"{float(variance):,.0f} ₽" if variance is not None else "—"

            badge_style = "background: #dcfce7; color: #166534;" if is_income else "background: #fee2e2; color: #991b1b;"
            type_label = "Приход" if is_income else "Расход"

            row_style = "cursor: pointer;"
            # Check overdue: unpaid and planned_date < today
            planned_date_str = item.get("planned_date") or ""
            if planned_date_str and actual_amt is None:
                try:
                    pd = datetime.strptime(planned_date_str[:10], "%Y-%m-%d").date()
                    if pd < date.today():
                        row_style += " background: #fefce8;"
                except Exception:
                    pass

            rows.append(
                Tr(
                    Td(format_date_russian(planned_date_str) if planned_date_str else "—", style="white-space: nowrap;"),
                    Td(A(deal_number, href=f"/finance/{deal_id}") if deal_id else deal_number,
                       style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"),
                    Td(""),  # customer already shown in header
                    Td(Span(type_label, style=f"padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; {badge_style}"), " ", cat.get("name", "—"),
                       style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"),
                    Td(item.get("description") or "—",
                       style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;",
                       title=item.get("description") or ""),
                    Td(f"{planned_amt:,.0f} ₽", style="text-align: right; white-space: nowrap;"),
                    Td(actual_amt_str, style="text-align: right; white-space: nowrap;"),
                    Td(item.get("actual_date", "—") if item.get("actual_date") else "—", style="white-space: nowrap;"),
                    Td(variance_str, style="text-align: right; white-space: nowrap;"),
                    style=row_style,
                    onclick=f"window.location='/finance/{deal_id}'" if deal_id else "",
                )
            )

    return rows


def finance_payments_tab(session, user, org_id, payment_type="all", payment_status="all", date_from="", date_to="", deal_filter="", customer_filter="", view="flat"):
    """Unified payments tab - shows ALL plan_fact_items across ALL deals for the organization."""
    supabase = get_supabase()

    # Query plan_fact_items with JOINs: plan_fact_categories, deals, specifications, quotes, customers
    # Filter by organization_id via deals.organization_id
    try:
        query = supabase.table("plan_fact_items").select(
            "*, plan_fact_categories(id, code, name, is_income, sort_order), "
            "deals!plan_fact_items_deal_id_fkey(id, deal_number, organization_id, "
            "specifications(quotes(customers(id, name))))"
        ).order("planned_date", desc=True)

        result = query.execute()
        all_items = result.data or []
    except Exception as e:
        print(f"Error fetching plan_fact_items for payments tab: {e}")
        all_items = []

    # Filter by org_id via deals.organization_id
    items = []
    for item in all_items:
        deals = item.get("deals") or {}
        if deals.get("organization_id") == org_id:
            items.append(item)

    # Apply filters
    filtered_items = []
    for item in items:
        cat = item.get("plan_fact_categories") or {}
        is_income = cat.get("is_income", False)

        # Filter by payment_type
        if payment_type == "income" and not is_income:
            continue
        if payment_type == "expense" and is_income:
            continue

        # Filter by payment_status
        if payment_status == "planned" and item.get("actual_amount") is not None:
            continue
        if payment_status == "paid" and item.get("actual_amount") is None:
            continue
        if payment_status == "overdue":
            planned_date_str = item.get("planned_date") or ""
            if item.get("actual_amount") is not None:
                continue
            if planned_date_str:
                try:
                    pd = datetime.strptime(planned_date_str[:10], "%Y-%m-%d").date()
                    if pd >= date.today():
                        continue
                except Exception:
                    continue
            else:
                continue

        # Filter by date_from
        if date_from:
            planned_date_str = item.get("planned_date") or ""
            if planned_date_str and planned_date_str[:10] < date_from:
                continue

        # Filter by date_to
        if date_to:
            planned_date_str = item.get("planned_date") or ""
            if planned_date_str and planned_date_str[:10] > date_to:
                continue

        # Filter by deal_filter
        if deal_filter:
            deals_data = item.get("deals") or {}
            if deal_filter not in (deals_data.get("deal_number") or "") and deal_filter != deals_data.get("id", ""):
                continue

        # Filter by customer_filter
        if customer_filter:
            deals_data = item.get("deals") or {}
            specs = deals_data.get("specifications") or {}
            quotes = specs.get("quotes") or {}
            customers = quotes.get("customers") or {}
            cust_id = customers.get("id", "")
            cust_name = customers.get("name", "")
            if customer_filter != cust_id and customer_filter.lower() not in cust_name.lower():
                continue

        filtered_items.append(item)

    # Calculate summary totals (income/expense, is_income based)
    income_planned = 0.0
    income_actual = 0.0
    expense_planned = 0.0
    expense_actual = 0.0

    for item in filtered_items:
        cat = item.get("plan_fact_categories") or {}
        is_income = cat.get("is_income", False)
        planned_amt = float(item.get("planned_amount") or 0)
        actual_amt = float(item.get("actual_amount") or 0) if item.get("actual_amount") is not None else 0.0

        if is_income:
            income_planned += planned_amt
            if item.get("actual_amount") is not None:
                income_actual += actual_amt
        else:
            expense_planned += planned_amt
            if item.get("actual_amount") is not None:
                expense_actual += actual_amt

    net_balance = income_actual - expense_actual

    # Filter bar with dropdowns and date inputs
    filter_bar = Div(
        # View toggle: По записям / По клиентам
        Div(
            A("По записям", href=f"/finance?tab=payments&view=flat&payment_type={payment_type}&payment_status={payment_status}&date_from={date_from}&date_to={date_to}&deal_filter={deal_filter}&customer_filter={customer_filter}",
              style=f"padding: 6px 14px; border-radius: 6px; font-size: 0.8rem; text-decoration: none; font-weight: 500; {'background: #1e293b; color: white;' if view != 'grouped' else 'background: #f1f5f9; color: #64748b;'}"),
            A("По клиентам", href=f"/finance?tab=payments&view=grouped&payment_type={payment_type}&payment_status={payment_status}&date_from={date_from}&date_to={date_to}&deal_filter={deal_filter}&customer_filter={customer_filter}",
              style=f"padding: 6px 14px; border-radius: 6px; font-size: 0.8rem; text-decoration: none; font-weight: 500; {'background: #1e293b; color: white;' if view == 'grouped' else 'background: #f1f5f9; color: #64748b;'}"),
            style="display: flex; gap: 4px; align-items: center;"
        ),
        # Payment type filter
        Div(
            Label("Тип:", style="font-size: 0.8rem; color: #64748b; margin-right: 4px;"),
            A("Все", href=f"/finance?tab=payments&payment_type=all&payment_status={payment_status}&date_from={date_from}&date_to={date_to}&view={view}&customer_filter={customer_filter}",
              style=f"padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; text-decoration: none; {'background: #1e293b; color: white;' if payment_type == 'all' else 'background: #f1f5f9; color: #64748b;'}"),
            A("Приход", href=f"/finance?tab=payments&payment_type=income&payment_status={payment_status}&date_from={date_from}&date_to={date_to}&view={view}&customer_filter={customer_filter}",
              style=f"padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; text-decoration: none; {'background: #16a34a; color: white;' if payment_type == 'income' else 'background: #f1f5f9; color: #64748b;'}"),
            A("Расход", href=f"/finance?tab=payments&payment_type=expense&payment_status={payment_status}&date_from={date_from}&date_to={date_to}&view={view}&customer_filter={customer_filter}",
              style=f"padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; text-decoration: none; {'background: #dc2626; color: white;' if payment_type == 'expense' else 'background: #f1f5f9; color: #64748b;'}"),
            style="display: flex; gap: 4px; align-items: center;"
        ),
        # Payment status filter
        Div(
            Label("Статус:", style="font-size: 0.8rem; color: #64748b; margin-right: 4px;"),
            A("Все", href=f"/finance?tab=payments&payment_type={payment_type}&payment_status=all&date_from={date_from}&date_to={date_to}&view={view}&customer_filter={customer_filter}",
              style=f"padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; text-decoration: none; {'background: #1e293b; color: white;' if payment_status == 'all' else 'background: #f1f5f9; color: #64748b;'}"),
            A("План", href=f"/finance?tab=payments&payment_type={payment_type}&payment_status=planned&date_from={date_from}&date_to={date_to}&view={view}&customer_filter={customer_filter}",
              style=f"padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; text-decoration: none; {'background: #1e293b; color: white;' if payment_status == 'planned' else 'background: #f1f5f9; color: #64748b;'}"),
            A("Оплачено", href=f"/finance?tab=payments&payment_type={payment_type}&payment_status=paid&date_from={date_from}&date_to={date_to}&view={view}&customer_filter={customer_filter}",
              style=f"padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; text-decoration: none; {'background: #1e293b; color: white;' if payment_status == 'paid' else 'background: #f1f5f9; color: #64748b;'}"),
            A("Просрочено", href=f"/finance?tab=payments&payment_type={payment_type}&payment_status=overdue&date_from={date_from}&date_to={date_to}&view={view}&customer_filter={customer_filter}",
              style=f"padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; text-decoration: none; {'background: #eab308; color: white;' if payment_status == 'overdue' else 'background: #f1f5f9; color: #64748b;'}"),
            style="display: flex; gap: 4px; align-items: center;"
        ),
        # Date range
        Div(
            Label("С:", style="font-size: 0.8rem; color: #64748b;"),
            Input(type="date", name="date_from", value=date_from, style="font-size: 0.8rem; padding: 4px; border: 1px solid #e2e8f0; border-radius: 4px;",
                  onchange=f"window.location='/finance?tab=payments&payment_type={payment_type}&payment_status={payment_status}&date_from='+this.value+'&date_to={date_to}&view={view}&customer_filter={customer_filter}'"),
            Label("По:", style="font-size: 0.8rem; color: #64748b;"),
            Input(type="date", name="date_to", value=date_to, style="font-size: 0.8rem; padding: 4px; border: 1px solid #e2e8f0; border-radius: 4px;",
                  onchange=f"window.location='/finance?tab=payments&payment_type={payment_type}&payment_status={payment_status}&date_from={date_from}&date_to='+this.value+'&view={view}&customer_filter={customer_filter}'"),
            style="display: flex; gap: 6px; align-items: center;"
        ),
        style="display: flex; flex-wrap: wrap; gap: 12px; padding: 12px 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 16px; align-items: center;"
    )

    # Build table rows (flat or grouped view)
    if view == "grouped":
        table_rows = render_payments_grouped(filtered_items)
    else:
        table_rows = []
        for item in filtered_items:
            cat = item.get("plan_fact_categories") or {}
            is_income = cat.get("is_income", False)
            deals_data = item.get("deals") or {}
            deal_id = deals_data.get("id", "")
            deal_number = deals_data.get("deal_number", "—")
            specs = deals_data.get("specifications") or {}
            quotes = specs.get("quotes") or {}
            customers = quotes.get("customers") or {}
            customer_name = customers.get("name", "—")

            planned_amt = float(item.get("planned_amount") or 0)
            actual_amt = item.get("actual_amount")
            actual_amt_str = f"{float(actual_amt):,.0f} ₽" if actual_amt is not None else "—"
            variance = item.get("variance_amount")
            variance_str = f"{float(variance):,.0f} ₽" if variance is not None else "—"

            badge_style = "background: #dcfce7; color: #166534;" if is_income else "background: #fee2e2; color: #991b1b;"
            type_label = "Приход" if is_income else "Расход"

            row_style = "cursor: pointer;"
            # Check overdue: unpaid and planned_date < today
            planned_date_str = item.get("planned_date") or ""
            if planned_date_str and actual_amt is None:
                try:
                    pd = datetime.strptime(planned_date_str[:10], "%Y-%m-%d").date()
                    if pd < date.today():
                        row_style += " background: #fefce8;"
                except Exception:
                    pass

            table_rows.append(
                Tr(
                    Td(format_date_russian(planned_date_str) if planned_date_str else "—", style="white-space: nowrap;"),
                    Td(A(deal_number, href=f"/finance/{deal_id}") if deal_id else deal_number,
                       style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"),
                    Td(customer_name, style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;", title=customer_name),
                    Td(Span(type_label, style=f"padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; {badge_style}"), " ", cat.get("name", "—"),
                       style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"),
                    Td(item.get("description") or "—",
                       style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;",
                       title=item.get("description") or ""),
                    Td(f"{planned_amt:,.0f} ₽", style="text-align: right; white-space: nowrap;"),
                    Td(actual_amt_str, style="text-align: right; white-space: nowrap;"),
                    Td(item.get("actual_date", "—") if item.get("actual_date") else "—", style="white-space: nowrap;"),
                    Td(variance_str, style="text-align: right; white-space: nowrap;"),
                    style=row_style,
                    onclick=f"window.location='/finance/{deal_id}'" if deal_id else "",
                )
            )

    # Payments table with 9 columns
    table = Table(
        Thead(
            Tr(
                Th("План. дата", style="width: 90px;"),
                Th("Сделка", style="width: 130px;"),
                Th("Клиент", style="width: 130px;"),
                Th("Категория", style="width: 180px;"),
                Th("Описание"),
                Th("Сумма план", style="text-align: right; width: 110px;"),
                Th("Сумма факт", style="text-align: right; width: 110px;"),
                Th("Дата факт", style="width: 90px;"),
                Th("Отклонение", style="text-align: right; width: 110px;"),
            )
        ),
        Tbody(*table_rows) if table_rows else Tbody(
            Tr(Td("Нет данных", colspan="9", style="text-align: center; padding: 2rem; color: #666;"))
        ),
        cls="unified-table",
        style="min-width: 1100px; table-layout: fixed;"
    )

    # Summary footer with Итого
    summary_footer = Div(
        Div(
            Div(
                Span("Поступления (план):", style="color: #64748b; font-size: 0.85rem;"),
                Span(f" {income_planned:,.0f} ₽", style="font-weight: 600; color: #166534; font-size: 0.85rem;"),
                style="margin-right: 20px;"
            ),
            Div(
                Span("Поступления (факт):", style="color: #64748b; font-size: 0.85rem;"),
                Span(f" {income_actual:,.0f} ₽", style="font-weight: 600; color: #166534; font-size: 0.85rem;"),
                style="margin-right: 20px;"
            ),
            Div(
                Span("Выплаты (план):", style="color: #64748b; font-size: 0.85rem;"),
                Span(f" {expense_planned:,.0f} ₽", style="font-weight: 600; color: #991b1b; font-size: 0.85rem;"),
                style="margin-right: 20px;"
            ),
            Div(
                Span("Выплаты (факт):", style="color: #64748b; font-size: 0.85rem;"),
                Span(f" {expense_actual:,.0f} ₽", style="font-weight: 600; color: #991b1b; font-size: 0.85rem;"),
                style="margin-right: 20px;"
            ),
            Div(
                Span("Баланс:", style="color: #64748b; font-size: 0.85rem;"),
                Span(f" {net_balance:,.0f} ₽", style=f"font-weight: 700; font-size: 0.95rem; color: {'#166534' if net_balance >= 0 else '#991b1b'};"),
            ),
            style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;"
        ),
        style="padding: 12px 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 12px;"
    )

    return Div(
        Div(
            Div(
                H3("Платежи", style="margin: 0;"),
                Span(f"Итого записей: {len(filtered_items)}", style="color: #64748b; font-size: 0.85rem;"),
                style="display: flex; align-items: center; gap: 12px;",
                cls="table-header"
            ),
            filter_bar,
            Div(table, cls="table-responsive"),
            summary_footer,
            cls="table-container"
        )
    )


def finance_invoices_tab(session, user, org_id):
    """Invoices tab - Procurement invoices registry for the finance section."""
    supabase = get_supabase()

    # Query invoices table, filtering by org through quotes
    try:
        # Get quote IDs for this organization
        quotes_result = supabase.table("quotes") \
            .select("id") \
            .eq("organization_id", org_id) \
            .is_("deleted_at", None) \
            .execute()
        org_quote_ids = [q["id"] for q in (quotes_result.data or [])]

        if org_quote_ids:
            result = supabase.table("invoices") \
                .select("id, quote_id, invoice_number, supplier_id, currency, status, created_at") \
                .in_("quote_id", org_quote_ids) \
                .order("created_at", desc=True) \
                .limit(200) \
                .execute()
            invoices = result.data or []
        else:
            invoices = []

        # Get supplier names
        supplier_ids = list(set(inv.get("supplier_id") for inv in invoices if inv.get("supplier_id")))
        suppliers_map = {}
        if supplier_ids:
            suppliers_result = supabase.table("suppliers").select("id, name").in_("id", supplier_ids).execute()
            suppliers_map = {s["id"]: s["name"] for s in (suppliers_result.data or [])}

        # Calculate totals from quote_items for each invoice
        invoice_ids = [inv["id"] for inv in invoices]
        invoice_totals = {}
        if invoice_ids:
            items_result = supabase.table("quote_items") \
                .select("invoice_id, purchase_price_original, quantity") \
                .in_("invoice_id", invoice_ids) \
                .execute()
            for item in (items_result.data or []):
                inv_id = item.get("invoice_id")
                if inv_id:
                    price = float(item.get("purchase_price_original", 0) or 0)
                    qty = float(item.get("quantity", 1) or 1)
                    invoice_totals[inv_id] = invoice_totals.get(inv_id, 0.0) + (price * qty)

    except Exception as e:
        print(f"Error fetching invoices for finance tab: {e}")
        invoices = []
        suppliers_map = {}
        invoice_totals = {}

    # Status label and style helper
    def invoice_status_display(status):
        status_map = {
            "pending_procurement": ("Закупка", "background: #fef3c7; color: #92400e;"),
            "pending_logistics": ("Логистика", "background: #dbeafe; color: #1e40af;"),
            "pending_customs": ("Таможня", "background: #e0e7ff; color: #3730a3;"),
            "completed": ("Завершён", "background: #dcfce7; color: #166534;"),
        }
        label, style = status_map.get(status, (status or "—", "background: #f1f5f9; color: #64748b;"))
        return Span(label, style=f"padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; {style}")

    # Calculate summary totals by currency
    totals_by_currency = {}
    count_by_status = {}
    for inv in invoices:
        cur = inv.get("currency", "USD")
        amt = invoice_totals.get(inv["id"], 0.0)
        if cur not in totals_by_currency:
            totals_by_currency[cur] = 0.0
        totals_by_currency[cur] += amt
        st = inv.get("status", "pending_procurement")
        count_by_status[st] = count_by_status.get(st, 0) + 1

    # Build table rows
    table_rows = []
    for idx, inv in enumerate(invoices, 1):
        supplier_name = suppliers_map.get(inv.get("supplier_id"), "—")
        invoice_number = inv.get("invoice_number", "—")
        total_amount = invoice_totals.get(inv["id"], 0.0)
        currency = inv.get("currency", "USD")
        status = inv.get("status", "pending_procurement")
        created_at = inv.get("created_at", "")

        # Format date
        date_display = format_date_russian(created_at[:10]) if created_at else "—"

        table_rows.append(
            Tr(
                Td(str(idx), style="color: #94a3b8; font-size: 0.85rem;"),
                Td(invoice_number, style="font-weight: 500;"),
                Td(supplier_name),
                Td(date_display),
                Td(f"{total_amount:,.2f} {currency}", style="text-align: right; font-weight: 500;"),
                Td(invoice_status_display(status)),
                style="cursor: default;",
            )
        )

    # Build table
    table = Table(
        Thead(
            Tr(
                Th("№", style="width: 40px;"),
                Th("НОМЕР ИНВОЙСА"),
                Th("ПОСТАВЩИК"),
                Th("ДАТА"),
                Th("СУММА", style="text-align: right;"),
                Th("СТАТУС"),
            )
        ),
        Tbody(*table_rows) if table_rows else Tbody(
            Tr(Td("Нет инвойсов от поставщиков", colspan="6", style="text-align: center; padding: 2rem; color: #666;"))
        ),
        cls="unified-table"
    )

    # Summary totals
    total_parts = []
    for cur, amt in sorted(totals_by_currency.items()):
        total_parts.append(
            Div(
                Span(f"Итого ({cur}):", style="color: #64748b; font-size: 0.85rem;"),
                Span(f" {amt:,.2f} {cur}", style="font-weight: 600; color: #1e293b; font-size: 0.85rem;"),
                style="margin-right: 20px;"
            )
        )

    # Status counts
    status_parts = []
    status_labels = {
        "pending_procurement": "Закупка",
        "pending_logistics": "Логистика",
        "pending_customs": "Таможня",
        "completed": "Завершён",
    }
    for st, label in status_labels.items():
        cnt = count_by_status.get(st, 0)
        if cnt > 0:
            status_parts.append(
                Span(f"{label}: {cnt}", style="color: #64748b; font-size: 0.8rem; margin-right: 12px;")
            )

    summary_footer = Div(
        Div(
            *total_parts,
            *status_parts,
            style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;"
        ),
        style="padding: 12px 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 12px;"
    ) if invoices else Div()

    return Div(
        Div(
            Div(
                H3("Инвойсы от поставщиков", style="margin: 0;"),
                Span(f"Итого записей: {len(invoices)}", style="color: #64748b; font-size: 0.85rem;"),
                style="display: flex; align-items: center; gap: 12px;",
                cls="table-header"
            ),
            Div(table, cls="table-responsive"),
            summary_footer,
            cls="table-container"
        )
    )


def finance_calendar_tab(session, user, org_id):
    """Calendar tab - Календарь платежей"""
    supabase = get_supabase()

    # Fetch payment schedule
    try:
        result = supabase.table("payment_schedule") \
            .select("*, specifications(specification_number)") \
            .order("expected_payment_date") \
            .execute()
        payments = result.data or []
    except Exception as e:
        print(f"Error fetching payment schedule: {e}")
        payments = []

    # Helper to format date
    def fmt_date(value):
        if not value:
            return "-"
        return format_date_russian(value)

    # Helper to format money
    def fmt_money(value, currency="USD"):
        if value is None:
            return "-"
        return f"{value:,.2f} {currency}"

    # Translation maps
    variant_map = {
        "from_order_date": "от даты заказа",
        "from_agreement_date": "от даты согласования",
        "from_shipment_date": "от даты отгрузки",
        "until_shipment_date": "до даты отгрузки"
    }

    purpose_map = {
        "advance": "Аванс",
        "additional": "Доплата",
        "final": "Закрывающий"
    }

    # Build table
    table = Table(
        Thead(
            Tr(
                Th("IDN"),
                Th("№ ПЛАТЕЖА"),
                Th("СРОК ДНЕЙ", cls="col-number"),
                Th("ВАРИАНТ РАСЧЕТА"),
                Th("ОЖИДАЕМАЯ ДАТА"),
                Th("ФАКТИЧЕСКАЯ ДАТА"),
                Th("СУММА", cls="col-money"),
                Th("НАЗНАЧЕНИЕ"),
                Th("КОММЕНТАРИЙ"),
            )
        ),
        Tbody(
            *[Tr(
                Td(p.get('specifications', {}).get('specification_number', '-') if p.get('specifications') else '-'),
                Td(str(p.get('payment_number', '-'))),
                Td(str(p.get('days_term', '-')), cls="col-number"),
                Td(variant_map.get(p.get('calculation_variant', ''), p.get('calculation_variant', '-'))),
                Td(fmt_date(p.get('expected_payment_date'))),
                Td(fmt_date(p.get('actual_payment_date'))),
                Td(fmt_money(p.get('payment_amount'), p.get('payment_currency', 'USD')), cls="col-money"),
                Td(purpose_map.get(p.get('payment_purpose', ''), p.get('payment_purpose', '-'))),
                Td(p.get('comment', '-'), style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;"),
            ) for p in payments]
        ) if payments else Tbody(
            Tr(Td("Нет данных", colspan="9", style="text-align: center; padding: 2rem; color: #666;"))
        ),
        cls="table-enhanced"
    )

    return Div(
        Div(
            Div(
                H3("Календарь платежей", style="margin: 0;"),
                cls="table-header"
            ),
            Div(table, cls="table-responsive"),
            Div(
                Span(f"Всего записей: {len(payments)}"),
                cls="table-footer"
            ),
            cls="table-enhanced-container"
        )
    )


# ============================================================================
# FINANCE DEAL DETAIL PAGE (Feature #79)
# ============================================================================

# @rt("/finance/{deal_id}")
def get(session, deal_id: str, tab: str = "main", generated: str = "", payment_registered: str = ""):
    """
    Redirect /finance/{deal_id} to /quotes/{quote_id}?tab=finance_main.

    Preserves backward compatibility for bookmarks and ERPS links.
    Maps old tab names to new quote detail tab names.

    Original Feature #79: Таблица план-факт по сделке
    Now consolidated into quote detail page.

    Tabs:
    - main: Deal info card + plan-fact summary card
    - plan-fact: Plan-fact table with payment registration modal
    - logistics: 7-stage accordion with per-stage expense buttons
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has finance, admin, or logistics role
    if not user_has_any_role(session, ["finance", "admin", "logistics", "top_manager"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Look up quote_id via deal -> specification -> quote chain
    try:
        deal_result = supabase.table("deals").select(
            "id, specifications!deals_specification_id_fkey(quote_id)"
        ).eq("id", deal_id).eq("organization_id", org_id).single().is_("deleted_at", None).execute()

        deal = deal_result.data
        if not deal:
            return page_layout("Ошибка",
                H1("Сделка не найдена"),
                P(f"Сделка с ID {deal_id} не найдена или у вас нет доступа."),
                btn_link("Назад к финансам", href="/finance", variant="secondary", icon_name="arrow-left"),
                session=session
            )

        spec = (deal.get("specifications") or {})
        quote_id = spec.get("quote_id")
        if not quote_id:
            return page_layout("Ошибка",
                H1("КП не найдено"),
                P("Не удалось определить КП для этой сделки."),
                btn_link("Назад к финансам", href="/finance", variant="secondary", icon_name="arrow-left"),
                session=session
            )
    except Exception as e:
        print(f"Error looking up quote for deal {deal_id}: {e}")
        return page_layout("Ошибка",
            H1("Ошибка загрузки"),
            P(f"Не удалось загрузить сделку: {str(e)}"),
            btn_link("Назад к финансам", href="/finance", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Map old finance tab names to new quote detail tab names
    tab_map = {"main": "finance_main", "plan-fact": "plan_fact", "logistics": "logistics_stages"}
    new_tab = tab_map.get(tab, "finance_main")

    return RedirectResponse(f"/quotes/{quote_id}?tab={new_tab}", status_code=301)


def _payment_registration_form(deal_id, unpaid_items, categories, source: str = "", preselect_category_id: str = "", source_tab: str = ""):
    """
    Render the payment registration form with two modes:
    - mode='plan': select an existing unpaid plan-fact item to register against
    - mode='new': create an ad-hoc payment (new plan-fact item + immediate actual)

    Args:
        deal_id: UUID of the deal
        unpaid_items: List of unpaid plan-fact item dicts (actual_amount is NULL)
        categories: List of category dicts for ad-hoc mode
        source: If 'erps', redirects back to ERPS tab after save
        preselect_category_id: If set, pre-selects category and defaults to 'new' mode
        source_tab: If set, redirects back to this tab after save (e.g. 'logistics')
    """
    from datetime import date as date_type

    today = date_type.today().isoformat()

    # If preselect_category_id is set, default to 'new' mode
    default_mode = "new" if preselect_category_id else "plan"

    # Build unpaid items options for plan mode
    if unpaid_items and len(unpaid_items) > 0:
        unpaid_options = [
            Option(
                f"{item.get('description', 'Без описания')} - {float(item.get('planned_amount', 0)):,.2f} {item.get('planned_currency', 'RUB')}",
                value=item["id"]
            )
            for item in unpaid_items
        ]
        plan_mode_section = Div(
            Label("Плановый платёж", fr="item_id", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
            Select(
                Option("-- Выберите плановый платёж --", value=""),
                *unpaid_options,
                name="item_id",
                id="item_id",
                style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px;"
            ),
            style="margin-bottom: 12px;"
        )
    else:
        plan_mode_section = Div(
            P("Нет неоплаченных плановых позиций", style="color: #64748b; font-size: 13px; font-style: italic;"),
            style="margin-bottom: 12px;"
        )

    # Category options for new (ad-hoc) mode
    category_options = [
        Option(
            cat.get("name", cat.get("code", "")),
            value=cat["id"],
            selected=(cat["id"] == preselect_category_id) if preselect_category_id else False,
        )
        for cat in categories
    ]

    return Div(
        Form(
            # Hidden fields for redirect control
            Input(type="hidden", name="source", value=source),
            Input(type="hidden", name="source_tab", value=source_tab),
            # Mode selector
            Div(
                Label("Режим", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
                Select(
                    Option("По плану (существующая позиция)", value="plan", selected=(default_mode == "plan")),
                    Option("Новый (внеплановый платёж)", value="new", selected=(default_mode == "new")),
                    name="mode",
                    id="payment_mode",
                    style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px;",
                    onchange="document.getElementById('plan_mode_fields').style.display = this.value === 'plan' ? 'block' : 'none'; document.getElementById('new_mode_fields').style.display = this.value === 'new' ? 'block' : 'none';"
                ),
                style="margin-bottom: 12px;"
            ),

            # Plan mode fields
            Div(
                plan_mode_section,
                id="plan_mode_fields",
                style=f"display: {'block' if default_mode == 'plan' else 'none'};"
            ),

            # New (ad-hoc) mode fields
            Div(
                Div(
                    Label("Категория", fr="category_id", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
                    Select(
                        Option("-- Выберите категорию --", value=""),
                        *category_options,
                        name="category_id",
                        id="category_id",
                        style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px;"
                    ),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Label("Описание", fr="description", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
                    Input(
                        type="text",
                        name="description",
                        id="description",
                        placeholder="Описание платежа",
                        style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; box-sizing: border-box;"
                    ),
                    style="margin-bottom: 12px;"
                ),
                id="new_mode_fields",
                style=f"display: {'block' if default_mode == 'new' else 'none'};"
            ),

            # Common fields for both modes
            Div(
                Div(
                    Label("Сумма *", fr="actual_amount", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
                    Input(
                        type="number",
                        name="actual_amount",
                        id="actual_amount",
                        step="0.01",
                        min="0.01",
                        required=True,
                        placeholder="0.00",
                        style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; box-sizing: border-box;"
                    ),
                    style="flex: 1;"
                ),
                Div(
                    Label("Валюта", fr="actual_currency", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
                    Select(
                        Option("RUB", value="RUB", selected=True),
                        Option("USD", value="USD"),
                        Option("EUR", value="EUR"),
                        Option("CNY", value="CNY"),
                        Option("TRY", value="TRY"),
                        name="actual_currency",
                        id="actual_currency",
                        style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px;"
                    ),
                    style="width: 120px;"
                ),
                style="display: flex; gap: 12px; margin-bottom: 12px;"
            ),
            Div(
                Div(
                    Label("Дата оплаты *", fr="actual_date", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
                    Input(
                        type="date",
                        name="actual_date",
                        id="actual_date",
                        value=today,
                        required=True,
                        style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; box-sizing: border-box;"
                    ),
                    style="flex: 1;"
                ),
                Div(
                    Label("Документ оплаты", fr="payment_document", style="font-size: 13px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;"),
                    Input(
                        type="text",
                        name="payment_document",
                        id="payment_document",
                        placeholder="PP-2026-001",
                        style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; box-sizing: border-box;"
                    ),
                    style="flex: 1;"
                ),
                style="display: flex; gap: 12px; margin-bottom: 12px;"
            ),

            # File upload (optional)
            Div(
                Label("Прикрепить документ", fr="payment_file", style="font-size: 12px; font-weight: 500; color: #64748b; display: block; margin-bottom: 4px;"),
                Input(
                    type="file",
                    name="payment_file",
                    id="payment_file",
                    accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx",
                    style="width: 100%; padding: 6px 10px; border: 1px dashed #d1d5db; border-radius: 8px; font-size: 12px; box-sizing: border-box; background: #f9fafb; color: #64748b; cursor: pointer;"
                ),
                style="margin-bottom: 16px;"
            ),

            # Submit buttons
            Div(
                Button(
                    "Зарегистрировать",
                    type="submit",
                    style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; border: none; border-radius: 8px; padding: 8px 20px; cursor: pointer; font-size: 14px; font-weight: 500;"
                ),
                Button(
                    "Отмена",
                    type="button",
                    onclick="var m=document.getElementById('deal-payment-modal'); if(m) m.style.display='none'; var e=document.getElementById('erps-payment-modal'); if(e) e.style.display='none'; var c=document.getElementById('payment-form-container'); if(c) c.innerHTML='';",
                    style="background: white; color: #64748b; border: 1px solid #d1d5db; border-radius: 8px; padding: 8px 20px; cursor: pointer; font-size: 14px;"
                ),
                style="display: flex; gap: 8px;"
            ),
            method="POST",
            action=f"/finance/{deal_id}/payments",
            enctype="multipart/form-data",
        ),
        style="background: #fafbfc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px;"
    )


# ============================================================================
# DEAL PAYMENT ROUTES (Feature 86af6ykhh)
# ============================================================================

# @rt("/finance/{deal_id}/payments/new")
def get(session, deal_id: str, source: str = "", stage_id: str = ""):
    """
    GET /finance/{deal_id}/payments/new - Returns the payment registration form.
    Supports two modes: plan (existing item) and new (ad-hoc).
    source param: if 'erps', form redirects back to ERPS tab after save.
    stage_id param: if set, looks up the logistics stage category to pre-select.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["finance", "admin", "logistics", "top_manager"]):
        return RedirectResponse("/unauthorized", status_code=303)

    user = session["user"]
    org_id = user["org_id"]
    user_roles = user.get("roles", [])

    supabase = get_supabase()

    # Verify deal belongs to user's organization
    deal_check = supabase.table("deals").select("id").eq("id", deal_id).eq("organization_id", org_id).is_("deleted_at", None).execute()
    if not deal_check.data:
        return P("Ошибка: сделка не найдена", style="color: #ef4444; font-size: 14px; padding: 12px;")

    # Fetch unpaid plan-fact items for this deal (actual_amount IS NULL)
    try:
        unpaid_result = supabase.table("plan_fact_items").select(
            "id, description, planned_amount, planned_currency, planned_date, actual_amount, "
            "plan_fact_categories(id, code, name, is_income)"
        ).eq("deal_id", deal_id).is_("actual_amount", "null").order("planned_date").execute()
        unpaid_items = unpaid_result.data or []
    except Exception as e:
        print(f"Error fetching unpaid items: {e}")
        unpaid_items = []

    # Fetch categories filtered by user role
    categories = get_categories_for_role(user_roles)

    # Resolve preselect_category_id from stage_id if provided
    preselect_category_id = ""
    if stage_id:
        try:
            stage_result = supabase.table("logistics_stages").select("stage_code").eq("id", stage_id).execute()
            if stage_result.data:
                stage_code = stage_result.data[0].get("stage_code", "")
                cat_code = STAGE_CATEGORY_MAP.get(stage_code, "")
                if cat_code:
                    cat_result = supabase.table("plan_fact_categories").select("id").eq("code", cat_code).execute()
                    if cat_result.data:
                        preselect_category_id = cat_result.data[0]["id"]
        except Exception as e:
            print(f"Warning: could not resolve stage category: {e}")

    # Form fields rendered by _payment_registration_form:
    # actual_amount, actual_currency, actual_date, payment_document
    # Form method=POST action=/finance/{deal_id}/payments
    # If opened from a logistics stage, redirect back to logistics tab after save
    source_tab = "logistics" if stage_id else ""
    return _payment_registration_form(deal_id, unpaid_items, categories, source=source, preselect_category_id=preselect_category_id, source_tab=source_tab)


# @rt("/finance/{deal_id}/payments")
async def post(session, request, deal_id: str, mode: str = "plan", item_id: str = "",
         actual_amount: str = "", actual_currency: str = "RUB",
         actual_date: str = "", payment_document: str = "",
         category_id: str = "", description: str = "", source: str = "",
         source_tab: str = ""):
    """
    POST /finance/{deal_id}/payments - Register a payment.
    Two modes:
      - mode='plan': records actual payment on an existing plan-fact item
      - mode='new': creates a new plan-fact item with actual data (ad-hoc)
    Supports optional file upload (payment_file) via multipart/form-data.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["finance", "admin", "logistics", "top_manager"]):
        return RedirectResponse("/unauthorized", status_code=303)

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Verify deal belongs to user's organization
    supabase = get_supabase()
    deal_check = supabase.table("deals").select("id").eq("id", deal_id).eq("organization_id", org_id).is_("deleted_at", None).execute()
    if not deal_check.data:
        return P("Ошибка: сделка не найдена", style="color: #ef4444; font-size: 14px; padding: 12px;")

    from datetime import date as date_type
    from services.plan_fact_service import (
        register_payment_for_item,
        create_plan_fact_item,
        record_actual_payment,
    )

    # Validate actual_amount
    try:
        amount_val = float(actual_amount)
    except (ValueError, TypeError):
        amount_val = None

    if not actual_amount or amount_val is None:
        return P("Ошибка: сумма обязательна", style="color: #ef4444; font-size: 14px; padding: 12px;")

    if amount_val <= 0:
        return P("Ошибка: сумма должна быть больше нуля", style="color: #ef4444; font-size: 14px; padding: 12px;")

    # Parse actual_date
    try:
        parsed_date = date_type.fromisoformat(actual_date) if actual_date else date_type.today()
    except ValueError:
        parsed_date = date_type.today()

    if mode == "plan" and item_id:
        # Mode plan: register payment for existing plan-fact item
        result = register_payment_for_item(
            item_id=item_id,
            actual_amount=amount_val,
            actual_date=parsed_date,
            actual_currency=actual_currency,
            payment_document=payment_document or None,
        )
        if not result.success:
            # Check if item is already paid
            error_msg = result.error or "Ошибка регистрации платежа"
            return P(f"Ошибка: {error_msg}", style="color: #ef4444; font-size: 14px; padding: 12px;")

    elif mode == "new":
        # Mode new: create ad-hoc plan-fact item then register payment
        if not category_id:
            return P("Ошибка: выберите категорию для нового платежа", style="color: #ef4444; font-size: 14px; padding: 12px;")

        new_item = create_plan_fact_item(
            deal_id=deal_id,
            category_id=category_id,
            planned_amount=amount_val,
            planned_date=parsed_date,
            planned_currency=actual_currency,
            description=description or "Внеплановый платёж",
            created_by=user_id,
        )
        if not new_item:
            return P("Ошибка: не удалось создать позицию", style="color: #ef4444; font-size: 14px; padding: 12px;")

        # Auto-link logistics_stage_id if the category is a logistics category.
        # This keeps stage summaries working on the logistics tab.
        try:
            cat_row = supabase.table("plan_fact_categories").select("code").eq("id", category_id).execute()
            cat_code = cat_row.data[0]["code"] if cat_row.data else ""
            if cat_code.startswith("logistics_"):
                # Reverse lookup: category_code -> stage_code via STAGE_CATEGORY_MAP
                stage_code = None
                for sc, cc in STAGE_CATEGORY_MAP.items():
                    if cc == cat_code:
                        stage_code = sc
                        break
                if stage_code:
                    stage_row = supabase.table("logistics_stages").select("id").eq("deal_id", deal_id).eq("stage_code", stage_code).execute()
                    if stage_row.data:
                        supabase.table("plan_fact_items").update(
                            {"logistics_stage_id": stage_row.data[0]["id"]}
                        ).eq("id", new_item.id).execute()
        except Exception as e:
            print(f"Warning: could not auto-link logistics_stage_id: {e}")

        # Now register actual payment on the newly created item
        result = record_actual_payment(
            item_id=new_item.id,
            actual_amount=amount_val,
            actual_date=parsed_date,
            actual_currency=actual_currency,
            payment_document=payment_document or None,
        )
        if not result:
            return P("Ошибка: позиция создана, но не удалось записать платёж", style="color: #ef4444; font-size: 14px; padding: 12px;")
    else:
        return P("Ошибка: выберите плановый платёж или режим 'Новый'", style="color: #ef4444; font-size: 14px; padding: 12px;")

    # Handle optional file upload after successful payment
    try:
        form = await request.form()
        payment_file = form.get("payment_file")
        if payment_file and hasattr(payment_file, 'filename') and payment_file.filename:
            file_content = await payment_file.read()
            if file_content:
                doc_description = payment_document if payment_document else f"Платёж {amount_val:,.2f} {actual_currency}"
                doc, error = upload_document(
                    organization_id=org_id,
                    entity_type="deal",
                    entity_id=deal_id,
                    file_content=file_content,
                    filename=payment_file.filename,
                    document_type="payment_order",
                    description=doc_description,
                    uploaded_by=user_id,
                )
                if error:
                    print(f"Warning: Failed to upload payment document: {error}")
    except Exception as e:
        print(f"Warning: Error uploading payment file: {e}")

    # Redirect based on source/source_tab
    if source == "erps":
        return RedirectResponse("/finance?tab=erps", status_code=303)
    if source_tab and source_tab in ("main", "plan-fact", "logistics"):
        return RedirectResponse(f"/finance/{deal_id}?tab={source_tab}", status_code=303)
    return RedirectResponse(f"/finance/{deal_id}?tab=plan-fact", status_code=303)


# @rt("/finance/{deal_id}/payments/{item_id}")
def delete(session, deal_id: str, item_id: str):
    """
    DELETE /finance/{deal_id}/payments/{item_id} - Clear the actual payment
    from a plan-fact item (sets actual fields to NULL).
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["finance", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Verify deal belongs to user's organization
    user = session["user"]
    org_id = user["org_id"]
    supabase = get_supabase()
    deal_check = supabase.table("deals").select("id").eq("id", deal_id).eq("organization_id", org_id).is_("deleted_at", None).execute()
    if not deal_check.data:
        return P("Ошибка: сделка не найдена", style="color: #ef4444; font-size: 14px; padding: 12px;")

    from services.plan_fact_service import clear_actual_payment, get_plan_fact_item

    # Validate item exists and belongs to this deal
    existing_item = get_plan_fact_item(item_id)
    if not existing_item:
        return P("Ошибка: платёж не найден (404)", style="color: #ef4444; font-size: 14px; padding: 12px;")
    if existing_item.deal_id != deal_id:
        return P("Ошибка: платёж не принадлежит этой сделке", style="color: #ef4444; font-size: 14px; padding: 12px;")

    # Clear actual payment fields
    clear_actual_payment(item_id)

    # Redirect back to deal page plan-fact tab to refresh all sections
    return RedirectResponse(f"/finance/{deal_id}?tab=plan-fact", status_code=303)


# ============================================================================
# AUTO-GENERATE PLAN-FACT ITEMS (Feature #82)
# ============================================================================

# @rt("/finance/{deal_id}/generate-plan-fact")
def get(session, deal_id: str):
    """
    Preview and confirm auto-generation of plan-fact items.

    Feature #82: Автогенерация плановых платежей

    Shows a preview of what plan-fact items will be generated from deal conditions.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has finance role
    if not user_has_any_role(session, ["finance", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    from services import get_plan_fact_generation_preview

    # Get preview of what will be generated
    preview = get_plan_fact_generation_preview(deal_id)

    if preview.get('error'):
        return page_layout("Ошибка",
            H1("Ошибка генерации"),
            P(f"Не удалось подготовить предпросмотр: {preview.get('error')}"),
            btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    deal_info = preview.get('deal_info', {})
    planned_items = preview.get('planned_items', [])
    totals = preview.get('totals', {})
    existing_items = preview.get('existing_items', 0)
    _currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥", "TRY": "₺"}
    deal_info_currency = deal_info.get('currency', 'RUB')
    deal_info_currency_sym = _currency_symbols.get(deal_info_currency, deal_info_currency)

    # Build preview table
    preview_rows = []
    for item in planned_items:
        is_income = item.get('is_income', False)
        amount = float(item.get('amount', 0))
        category_color = "#10b981" if is_income else "#6366f1"

        preview_rows.append(Tr(
            Td(Span(item.get('category_name', '-'), style=f"color: {category_color}; font-weight: 500;")),
            Td(item.get('description', '-')),
            Td(f"{amount:,.2f} {item.get('currency', 'RUB')}", style="text-align: right; font-weight: 500;"),
            Td(item.get('date', '-')),
            Td(
                Span("Доход", style="color: #10b981;") if is_income else Span("Расход", style="color: #6366f1;")
            ),
        ))

    # Calculate totals
    total_income = sum(item.get('amount', 0) for item in planned_items if item.get('is_income'))
    total_expense = sum(item.get('amount', 0) for item in planned_items if not item.get('is_income'))
    planned_margin = total_income - total_expense

    # Warning if items exist
    existing_warning = None
    if existing_items > 0:
        existing_warning = Div(
            Strong(icon("alert-triangle", size=14), " Внимание: "),
            f"Для этой сделки уже существуют {existing_items} плановых платежей. ",
            "Генерация заменит все существующие записи.",
            style="background: #fef3c7; border: 1px solid #f59e0b; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; color: #92400e;"
        )

    # Define consistent table styles
    th_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    td_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"
    tfoot_style = "padding: 12px 16px; font-size: 14px; background: #f8fafc; border-top: 2px solid #e2e8f0;"

    return page_layout(f"Генерация план-факта",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                f"К сделке {deal_info.get('deal_number', '')}",
                href=f"/finance/{deal_id}",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("refresh-cw", size=28, color="#6366f1"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Автогенерация плановых платежей", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    P("На основе условий сделки будут созданы плановые платежи", style="margin: 0; color: #64748b; font-size: 14px;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Warning banner if items exist
        Div(
            Div(
                icon("alert-triangle", size=18, color="#d97706"),
                style="margin-right: 12px;"
            ),
            Div(
                Strong(f"Внимание: для этой сделки уже существуют {existing_items} плановых платежей. ", style="display: block; margin-bottom: 2px;"),
                Span("Генерация заменит все существующие записи.", style="color: #92400e; font-size: 13px;"),
            ),
            style="display: flex; align-items: flex-start; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 1px solid #f59e0b; padding: 16px 20px; border-radius: 12px; margin-bottom: 20px; color: #92400e;"
        ) if existing_items > 0 else "",

        # Source data card
        Div(
            Div(
                icon("database", size=14, color="#64748b"),
                Span("ИСХОДНЫЕ ДАННЫЕ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
            ),
            Div(
                *[Div(
                    Span(label, style="font-size: 12px; color: #64748b; display: block; margin-bottom: 2px;"),
                    Span(str(value), style="font-size: 14px; color: #1e293b; font-weight: 500;"),
                    style="padding: 10px 16px; background: #f8fafc; border-radius: 8px;"
                ) for label, value in [
                    ("Сумма сделки", f"{deal_info.get('total_amount', 0):,.2f} {deal_info_currency_sym}"),
                    ("Дата подписания", format_date_russian(deal_info.get('signed_at')) if deal_info.get('signed_at') else '-'),
                    ("Закупка (из КП)", f"{totals.get('total_purchase', 0):,.2f}"),
                    ("Логистика (из КП)", f"{totals.get('total_logistics', 0):,.2f}"),
                    ("Таможня (из КП)", f"{totals.get('total_customs', 0):,.2f}"),
                ]],
                style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;"
            ),
            style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; margin-bottom: 24px;"
        ),

        # Preview table section
        Div(
            Div(
                icon("list", size=14, color="#64748b"),
                Span("ПЛАНИРУЕМЫЕ ПЛАТЕЖИ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
            ),
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("Категория", style=th_style),
                            Th("Описание", style=th_style),
                            Th("Сумма", style=f"{th_style} text-align: right;"),
                            Th("План. дата", style=th_style),
                            Th("Тип", style=th_style),
                        )
                    ),
                    Tbody(*[Tr(
                        Td(Span(item.get('category_name', '-'), style=f"color: {'#10b981' if item.get('is_income') else '#6366f1'}; font-weight: 600;"), style=td_style),
                        Td(item.get('description', '-'), style=td_style),
                        Td(f"{float(item.get('amount', 0)):,.2f} {item.get('currency', 'RUB')}", style=f"{td_style} text-align: right; font-weight: 500;"),
                        Td(item.get('date', '-'), style=td_style),
                        Td(
                            Span("Доход", style="padding: 3px 10px; background: #f0fdf4; border-radius: 12px; color: #10b981; font-size: 12px; font-weight: 500;") if item.get('is_income') else
                            Span("Расход", style="padding: 3px 10px; background: #eef2ff; border-radius: 12px; color: #6366f1; font-size: 12px; font-weight: 500;"),
                            style=td_style
                        ),
                    ) for item in planned_items]),
                    Tfoot(
                        Tr(
                            Td(Strong("Итого поступлений:"), colspan="2", style=tfoot_style),
                            Td(Strong(f"{total_income:,.2f}"), style=f"{tfoot_style} text-align: right; color: #10b981;"),
                            Td("", style=tfoot_style),
                            Td("", style=tfoot_style),
                        ),
                        Tr(
                            Td(Strong("Итого расходов:"), colspan="2", style=tfoot_style),
                            Td(Strong(f"{total_expense:,.2f}"), style=f"{tfoot_style} text-align: right; color: #6366f1;"),
                            Td("", style=tfoot_style),
                            Td("", style=tfoot_style),
                        ),
                        Tr(
                            Td(Strong("Плановая маржа:"), colspan="2", style=f"{tfoot_style} font-weight: 700;"),
                            Td(Strong(f"{planned_margin:,.2f}"), style=f"{tfoot_style} text-align: right; font-weight: 700; color: {'#10b981' if planned_margin >= 0 else '#ef4444'};"),
                            Td("", style=tfoot_style),
                            Td("", style=tfoot_style),
                        ),
                    ),
                    style="width: 100%; border-collapse: collapse;"
                ) if preview_rows else Div(
                    icon("file-x", size=40, color="#94a3b8"),
                    P("Нет данных для генерации платежей", style="color: #64748b; font-size: 14px; margin: 12px 0 0 0;"),
                    style="text-align: center; padding: 40px 20px;"
                ),
                style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="margin-bottom: 24px;"
        ),

        # Action buttons
        Form(
            Div(
                btn("Сгенерировать платежи", variant="success", icon_name="check", type="submit") if preview_rows else "",
                btn_link("Отмена", href=f"/finance/{deal_id}", variant="secondary"),
                style="display: flex; gap: 12px;"
            ),
            method="POST",
            action=f"/finance/{deal_id}/generate-plan-fact",
        ),

        session=session
    )


# @rt("/finance/{deal_id}/generate-plan-fact")
def post(session, deal_id: str):
    """
    Execute auto-generation of plan-fact items.

    Feature #82: Автогенерация плановых платежей

    Creates plan_fact_items based on deal conditions (payment terms, amounts, etc.)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has finance role
    if not user_has_any_role(session, ["finance", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    from services import generate_plan_fact_from_deal, count_items_for_deal

    # Check if items already exist and replace them
    existing_count = count_items_for_deal(deal_id).get('total', 0)
    replace_existing = existing_count > 0

    # Generate plan-fact items
    result = generate_plan_fact_from_deal(
        deal_id=deal_id,
        created_by=user_id,
        replace_existing=replace_existing
    )

    if result.success:
        # Redirect back to deal page with success message
        return RedirectResponse(f"/finance/{deal_id}?generated={result.items_count}", status_code=303)
    else:
        # Show error
        return page_layout("Ошибка генерации",
            H1("Ошибка"),
            P(f"Не удалось сгенерировать плановые платежи: {result.error}"),
            btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# ============================================================================
# PAYMENT REGISTRATION FORM (Feature #80)
# ============================================================================

# @rt("/finance/{deal_id}/plan-fact/{item_id}")
def get(session, deal_id: str, item_id: str):
    """
    Payment registration form - allows registering actual payment for a plan_fact_item.

    Feature #80: Форма регистрации платежа

    This form allows finance users to:
    1. View planned payment details
    2. Enter actual payment information (amount, date, currency, exchange rate)
    3. Add payment document reference and notes
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Validate item_id is a valid UUID to prevent DB errors
    import uuid as uuid_mod
    try:
        uuid_mod.UUID(item_id)
    except (ValueError, AttributeError):
        return page_layout("Ошибка",
            H1("Некорректный ID"),
            P(f"Идентификатор записи '{item_id}' не является допустимым UUID."),
            btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has finance role
    if not user_has_any_role(session, ["finance", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch the plan_fact_item with category info
    try:
        item_result = supabase.table("plan_fact_items").select(
            "id, deal_id, category_id, description, "
            "planned_amount, planned_currency, planned_date, "
            "actual_amount, actual_currency, actual_date, actual_exchange_rate, "
            "variance_amount, payment_document, notes, created_at, "
            "plan_fact_categories(id, code, name, is_income)"
        ).eq("id", item_id).single().execute()

        item = item_result.data
        if not item:
            return page_layout("Ошибка",
                H1("Платёж не найден"),
                P(f"Запись план-факта с ID {item_id} не найдена."),
                btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
                session=session
            )
    except Exception as e:
        print(f"Error fetching plan_fact_item: {e}")
        return page_layout("Ошибка",
            H1("Ошибка загрузки"),
            P(f"Не удалось загрузить запись: {str(e)}"),
            btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Verify item belongs to the deal
    if str(item.get("deal_id")) != str(deal_id):
        return page_layout("Ошибка",
            H1("Неверный запрос"),
            P("Запись план-факта не относится к указанной сделке."),
            btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Fetch deal info for header
    try:
        deal_result = supabase.table("deals").select(
            "id, deal_number, organization_id"
        ).eq("id", deal_id).single().is_("deleted_at", None).execute()

        deal = deal_result.data
        if not deal or str(deal.get("organization_id")) != str(org_id):
            return page_layout("Ошибка",
                H1("Сделка не найдена"),
                P("Сделка не найдена или у вас нет доступа."),
                btn_link("Назад к финансам", href="/finance", variant="secondary", icon_name="arrow-left"),
                session=session
            )
    except Exception as e:
        print(f"Error fetching deal: {e}")
        return page_layout("Ошибка",
            H1("Ошибка загрузки"),
            P(f"Не удалось загрузить сделку: {str(e)}"),
            btn_link("Назад к финансам", href="/finance", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    deal_number = deal.get("deal_number", "-")

    # Extract item info
    category = item.get("plan_fact_categories", {}) or {}
    category_name = category.get("name", "Прочее")
    is_income = category.get("is_income", False)
    description = item.get("description", "") or ""

    planned_amount = float(item.get("planned_amount", 0) or 0)
    planned_currency = item.get("planned_currency", "RUB")
    planned_date = item.get("planned_date", "")[:10] if item.get("planned_date") else ""

    # Existing actual values (for editing)
    actual_amount = item.get("actual_amount")
    actual_currency = item.get("actual_currency") or planned_currency
    actual_date = item.get("actual_date", "")[:10] if item.get("actual_date") else ""
    actual_exchange_rate = item.get("actual_exchange_rate") or ""
    payment_document = item.get("payment_document", "") or ""
    notes = item.get("notes", "") or ""

    # Status indicator
    is_paid = actual_amount is not None
    status_label = "Оплачено" if is_paid else "Ожидает оплаты"
    status_color = "#10b981" if is_paid else "#f59e0b"

    # Category badge
    category_color = "#10b981" if is_income else "#6366f1"
    category_type = "Доход" if is_income else "Расход"

    # Modern form input styles
    input_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; transition: border-color 0.15s ease, box-shadow 0.15s ease;"
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"

    return page_layout(f"Регистрация платежа — {deal_number}",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                f"К сделке {deal_number}",
                href=f"/finance/{deal_id}",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("credit-card", size=28, color="#10b981"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Регистрация платежа", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    Div(
                        Span(category_name, style=f"color: {category_color}; font-weight: 500; margin-right: 8px;"),
                        Span(f"({category_type})", style="color: #64748b; font-size: 13px; margin-right: 12px;"),
                        Span(
                            status_label,
                            style=f"display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; background: {status_color}20; color: {status_color};"
                        ),
                        style="display: flex; align-items: center; flex-wrap: wrap;"
                    ),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Two-column layout
        Div(
            # Left column - Planned payment info card
            Div(
                Div(
                    icon("file-text", size=14, color="#64748b"),
                    Span("ПЛАНОВЫЕ ДАННЫЕ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                ),
                Div(
                    *[Div(
                        Span(label, style="font-size: 12px; color: #64748b; display: block; margin-bottom: 2px;"),
                        Span(value, style="font-size: 14px; color: #1e293b; font-weight: 500;"),
                        style="margin-bottom: 12px;"
                    ) for label, value in [
                        ("Категория", f"{category_name} ({category_type})"),
                        ("Описание", description or "-"),
                        ("Плановая сумма", f"{planned_amount:,.2f} {planned_currency}"),
                        ("Плановая дата", planned_date or "-"),
                    ]],
                ),
                # Help box
                Div(
                    Div(
                        icon("info", size=16, color="#d97706"),
                        style="margin-right: 10px; flex-shrink: 0;"
                    ),
                    Div(
                        Strong("Подсказка", style="display: block; font-size: 13px; margin-bottom: 4px;"),
                        Span("При сохранении система автоматически рассчитает отклонение: Факт - План", style="font-size: 12px; color: #92400e;"),
                    ),
                    style="display: flex; align-items: flex-start; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 1px solid #fcd34d; padding: 12px 14px; border-radius: 8px; margin-top: 16px;"
                ),
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            # Right column - Actual payment form
            Div(
                Form(
                    Div(
                        icon("check-circle", size=14, color="#64748b"),
                        Span("ФАКТИЧЕСКИЕ ДАННЫЕ", style="margin-left: 6px;"),
                        style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                    ),

                    # Hidden fields
                    Input(type="hidden", name="deal_id", value=deal_id),
                    Input(type="hidden", name="item_id", value=item_id),

                    # Actual amount
                    Div(
                        Label("Фактическая сумма *", fr="actual_amount", style=label_style),
                        Input(
                            type="number",
                            name="actual_amount",
                            id="actual_amount",
                            value=str(actual_amount) if actual_amount is not None else "",
                            step="0.01",
                            min="0",
                            required=True,
                            placeholder=f"Плановая: {planned_amount:,.2f}",
                            style=input_style
                        ),
                        style="margin-bottom: 16px;"
                    ),

                    # Currency and exchange rate row
                    Div(
                        Div(
                            Label("Валюта", fr="actual_currency", style=label_style),
                            Select(
                                Option("RUB - Рубли", value="RUB", selected=(actual_currency == "RUB")),
                                Option("USD - Доллары США", value="USD", selected=(actual_currency == "USD")),
                                Option("EUR - Евро", value="EUR", selected=(actual_currency == "EUR")),
                                Option("CNY - Юани", value="CNY", selected=(actual_currency == "CNY")),
                                name="actual_currency",
                                id="actual_currency",
                                style=select_style
                            ),
                            style="flex: 1;"
                        ),
                        Div(
                            Label("Курс к рублю", fr="actual_exchange_rate", style=label_style),
                            Input(
                                type="number",
                                name="actual_exchange_rate",
                                id="actual_exchange_rate",
                                value=str(actual_exchange_rate) if actual_exchange_rate else "",
                                step="0.0001",
                                min="0",
                                placeholder="Для валюты ≠ RUB",
                                style=input_style
                            ),
                            style="flex: 1;"
                        ),
                        style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;"
                    ),

                    # Actual date
                    Div(
                        Label("Дата платежа *", fr="actual_date", style=label_style),
                        Input(
                            type="date",
                            name="actual_date",
                            id="actual_date",
                            value=actual_date or "",
                            required=True,
                            style=input_style
                        ),
                        style="margin-bottom: 16px;"
                    ),

                    # Payment document
                    Div(
                        Label("Номер платёжного документа", fr="payment_document", style=label_style),
                        Input(
                            type="text",
                            name="payment_document",
                            id="payment_document",
                            value=payment_document,
                            placeholder="№ п/п, номер счёта и т.д.",
                            style=input_style
                        ),
                        style="margin-bottom: 16px;"
                    ),

                    # Notes
                    Div(
                        Label("Примечания", fr="notes", style=label_style),
                        Textarea(
                            notes,
                            name="notes",
                            id="notes",
                            rows="3",
                            placeholder="Дополнительная информация о платеже...",
                            style=f"{input_style} resize: vertical; min-height: 80px;"
                        ),
                        style="margin-bottom: 20px;"
                    ),

                    # Submit buttons
                    Div(
                        btn("Сохранить платёж", variant="success", icon_name="check", type="submit"),
                        btn_link("Отмена", href=f"/finance/{deal_id}", variant="secondary"),
                        style="display: flex; gap: 12px;"
                    ),

                    action=f"/finance/{deal_id}/plan-fact/{item_id}",
                    method="POST",
                ),
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: 1fr 1.5fr; gap: 20px;"
        ),

        session=session
    )


# @rt("/finance/{deal_id}/plan-fact/{item_id}")
def post(session, deal_id: str, item_id: str,
         actual_amount: str = None,
         actual_currency: str = "RUB",
         actual_exchange_rate: str = None,
         actual_date: str = None,
         payment_document: str = None,
         notes: str = None):
    """
    Handle payment registration form submission.

    Feature #80: Форма регистрации платежа (POST handler)

    Updates the plan_fact_item with actual payment data.
    The database trigger automatically calculates variance.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has finance role
    if not user_has_any_role(session, ["finance", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Validate required fields
    if not actual_amount or not actual_date:
        return page_layout("Ошибка",
            H1("Ошибка валидации"),
            P("Сумма и дата платежа обязательны для заполнения."),
            btn_link("Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Validate the item exists and belongs to the deal in user's org
    try:
        # First verify the deal belongs to user's org
        deal_result = supabase.table("deals").select(
            "id, deal_number, organization_id"
        ).eq("id", deal_id).eq("organization_id", org_id).single().is_("deleted_at", None).execute()

        if not deal_result.data:
            return page_layout("Ошибка",
                H1("Доступ запрещён"),
                P("Сделка не найдена или у вас нет доступа."),
                btn_link("Назад к финансам", href="/finance", variant="secondary", icon_name="arrow-left"),
                session=session
            )

        # Verify item belongs to the deal
        item_result = supabase.table("plan_fact_items").select(
            "id, deal_id"
        ).eq("id", item_id).eq("deal_id", deal_id).single().execute()

        if not item_result.data:
            return page_layout("Ошибка",
                H1("Запись не найдена"),
                P("Запись план-факта не найдена или не относится к указанной сделке."),
                btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
                session=session
            )
    except Exception as e:
        print(f"Error validating item: {e}")
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось проверить запись: {str(e)}"),
            btn_link("Назад к сделке", href=f"/finance/{deal_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Prepare update data
    try:
        actual_amount_val = float(actual_amount)
    except ValueError:
        return page_layout("Ошибка",
            H1("Ошибка валидации"),
            P("Некорректное значение суммы."),
            btn_link("Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    update_data = {
        "actual_amount": actual_amount_val,
        "actual_currency": actual_currency,
        "actual_date": actual_date,
        "payment_document": payment_document.strip() if payment_document else None,
        "notes": notes.strip() if notes else None,
    }

    # Handle exchange rate
    if actual_exchange_rate and actual_exchange_rate.strip():
        try:
            update_data["actual_exchange_rate"] = float(actual_exchange_rate)
        except ValueError:
            return page_layout("Ошибка",
                H1("Ошибка валидации"),
                P("Некорректное значение курса валюты."),
                btn_link("Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", variant="secondary", icon_name="arrow-left"),
                session=session
            )
    else:
        # For RUB, set exchange rate to 1
        if actual_currency == "RUB":
            update_data["actual_exchange_rate"] = 1.0
        else:
            update_data["actual_exchange_rate"] = None

    # Update the plan_fact_item
    try:
        result = supabase.table("plan_fact_items").update(update_data).eq("id", item_id).execute()

        if not result.data:
            raise Exception("No data returned from update")

        # Redirect back to deal page with success
        return RedirectResponse(f"/finance/{deal_id}?payment_registered=1", status_code=303)

    except Exception as e:
        print(f"Error updating plan_fact_item: {e}")
        return page_layout("Ошибка",
            H1("Ошибка сохранения"),
            P(f"Не удалось сохранить платёж: {str(e)}"),
            btn_link("Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", variant="secondary", icon_name="arrow-left"),
            session=session
        )

