"""FastHTML /dashboard + /tasks areas — archived 2026-04-20 during Phase 6C-2B-7.

Replaced by Next.js:
  - /tasks      — https://app.kvotaflow.ru/tasks (unified task inbox, queries FastAPI /api/tasks/*)
  - /dashboard  — https://app.kvotaflow.ru/dashboard (role-based dashboard with tabs)

Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy these paths back to this Python container.

Contents (2 @rt routes + 18 exclusive helpers/constants, ~2,970 LOC total):

Routes:
  - GET /tasks       — Unified Task Inbox (hub for all role-based pending tasks)
  - GET /dashboard   — Role-based dashboard with tabs: overview, sales, procurement,
                       logistics, customs, quote-control, spec-control, finance
                       (supports HTMX partial responses for spec-control + overview tabs)

Tab configuration + routing helpers:
  - DASHBOARD_TABS           — tab config constant (labels, icons, roles, priority)
  - get_dashboard_tabs       — filter visible tabs by user roles
  - get_default_dashboard_tab — pick default tab based on roles
  - should_show_dashboard_tabs — decide tabs visibility for single vs multi-role users
  - _build_dashboard_tabs_nav — render tab navigation Div

Task/content builders (each scoped exclusively to /dashboard or /tasks):
  - _get_role_tasks_sections      — build role-specific task cards (shared by /tasks and /dashboard overview)
  - _get_sales_summary_blocks     — 3 sales-manager summary cards with date filter (overview tab)
  - _dashboard_overview_content   — overview tab content (admin/top_manager/sales)
  - _dashboard_procurement_content + _inner — procurement tab content with error boundary
  - _dashboard_logistics_content  — logistics tab content
  - _dashboard_customs_content    — customs tab content
  - _dashboard_quote_control_content — quote control tab content
  - _dashboard_spec_control_content — spec control tab with search + filter chips
  - _dashboard_finance_content    — finance tab (thin link-out to /finance)
  - _dashboard_sales_content      — sales tab (active specs + quotes + profile card)
  - _count_user_tasks             — aggregate pending-task counter for /tasks header badge

Date helpers (used only by _dashboard_sales_content):
  - _calculate_days_remaining     — "осталось N дн." / "просрочено" formatter
  - _format_deadline_display      — "DD.MM.YYYY (осталось N дн.)" formatter

All 18 helpers have ZERO callers outside /tasks and /dashboard (confirmed via grep trace):
  - 2 are shared between the two routes (_get_role_tasks_sections, DASHBOARD_TABS-cluster)
  - The remaining 16 are exclusive to /dashboard
  - Pure dead code after archive — safe single-file extraction.

Preserved in main.py / services/ (NOT archived here):
  - services.approval_service.count_pending_approvals, get_approvals_with_details
  - services.specification_service.count_specifications_by_status
  - services.deal_service.count_deals_by_status, get_deals_by_status
  - services.user_profile_service.get_user_profile, get_user_statistics
    (all still consumed by FastAPI routers + Next.js via /api/*)
  - sidebar/nav entries for /tasks and /dashboard (main.py nav markup)
    left intact, become dead links post-archive, safe per Caddy cutover

No /api/tasks/* or /api/dashboard/* FastAPI sub-apps are touched by this archive —
Next.js consumes its own FastAPI endpoints (/api/quotes, /api/specifications, etc.).

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_any_role, get_supabase,
icon, btn_link, format_money, format_date_russian, workflow_status_badge,
count_pending_approvals, get_approvals_with_details,
count_specifications_by_status, count_deals_by_status, get_deals_by_status,
get_effective_roles, services.user_profile_service.{get_user_profile,
get_user_statistics}), re-apply the @rt decorator, and regenerate tests if
needed. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime, date, timedelta
from decimal import Decimal

from fasthtml.common import (
    A, Div, Form, H1, H2, H3, Hidden, Input, Label, Option, P, Script,
    Select, Span, Strong, Table, Tbody, Td, Th, Thead, Title, Tr,
)


# ============================================================================
# DASHBOARD (Feature #86: Role-based tasks)
# ============================================================================

# Dashboard tab configuration
DASHBOARD_TABS = [
    {
        "id": "overview",
        "icon": "bar-chart-3",
        "label": "Обзор",
        "roles": ["admin", "top_manager", "sales", "sales_manager", "head_of_sales", "procurement", "head_of_procurement", "logistics", "head_of_logistics", "customs", "head_of_customs", "quote_controller", "spec_controller", "finance"],
        "priority": 0,
    },
    {
        "id": "sales",
        "icon": "user-circle",
        "label": "Продажи",
        "roles": ["sales", "sales_manager"],
        "priority": 1,
    },
    {
        "id": "procurement",
        "icon": "shopping-cart",
        "label": "Закупки",
        "roles": ["procurement", "head_of_procurement", "admin"],
        "priority": 2,
    },
    {
        "id": "logistics",
        "icon": "truck",
        "label": "Логистика",
        "roles": ["logistics", "head_of_logistics", "admin"],
        "priority": 3,
    },
    {
        "id": "customs",
        "icon": "shield-check",
        "label": "Таможня",
        "roles": ["customs", "head_of_customs", "admin"],
        "priority": 4,
    },
    {
        "id": "quote-control",
        "icon": "check-circle",
        "label": "Контроль КП",
        "roles": ["quote_controller", "admin"],
        "priority": 5,
    },
    {
        "id": "spec-control",
        "icon": "file-text",
        "label": "Спецификации",
        "roles": ["spec_controller", "admin"],
        "priority": 6,
    },
    {
        "id": "finance",
        "icon": "wallet",
        "label": "Финансы",
        "roles": ["finance", "top_manager", "admin"],
        "priority": 7,
    },
]


def get_dashboard_tabs(roles: list) -> list:
    """
    Get visible dashboard tabs based on user roles.

    Returns list of tab dicts the user can see, sorted by priority.
    """
    visible_tabs = []
    for tab in DASHBOARD_TABS:
        if any(role in roles for role in tab["roles"]):
            visible_tabs.append(tab)

    # Sort by priority
    visible_tabs.sort(key=lambda t: t["priority"])
    return visible_tabs


def get_default_dashboard_tab(roles: list) -> str:
    """
    Get default tab for user based on roles.

    Priority:
    1. overview (if admin/top_manager)
    2. First workspace tab by priority
    """
    visible_tabs = get_dashboard_tabs(roles)
    if not visible_tabs:
        return "overview"  # Fallback

    return visible_tabs[0]["id"]


def should_show_dashboard_tabs(roles: list) -> bool:
    """
    Determine if dashboard tabs should be shown.

    Key UX principle: if user has only ONE workspace role (excluding overview),
    show workspace directly without tabs.

    Returns True if tabs should be shown, False otherwise.
    """
    visible_tabs = get_dashboard_tabs(roles)

    # Separate overview from workspace tabs
    workspace_tabs = [t for t in visible_tabs if t["id"] != "overview"]
    has_overview = any(t["id"] == "overview" for t in visible_tabs)

    # Show tabs if:
    # - User has access to overview (admin/top_manager)
    # - User has multiple workspace tabs
    return has_overview or len(workspace_tabs) > 1


def _get_role_tasks_sections(user_id: str, org_id: str, roles: list, supabase) -> list:
    """
    Build role-specific task sections for the dashboard.
    Returns a list of FastHTML elements showing tasks relevant to user's roles.
    """
    sections = []

    # For sales users, get their assigned customer IDs for filtering
    # Filter applies when user has sales role but NOT admin/top_manager/head_of_sales (full visibility)
    has_sales_role = any(r in roles for r in ["sales", "sales_manager"])
    has_full_visibility = any(r in roles for r in ["admin", "top_manager", "head_of_sales"])
    needs_sales_filter = has_sales_role and not has_full_visibility
    my_customer_ids = None
    if needs_sales_filter:
        my_customers = supabase.table("customers").select("id") \
            .eq("organization_id", org_id).eq("manager_id", user_id).execute()
        my_customer_ids = [c["id"] for c in (my_customers.data or [])]

    # -------------------------------------------------------------------------
    # TOP MANAGER / ADMIN: Pending Approvals
    # -------------------------------------------------------------------------
    if 'top_manager' in roles or 'admin' in roles:
        pending_count = count_pending_approvals(user_id)
        if pending_count > 0:
            # Get approval details - only pending ones
            approvals = get_approvals_with_details(user_id, status='pending', limit=5)

            approval_rows = []
            for a in approvals:
                quote_info = a.get('quotes', {}) or {}
                # Handle both 'idn' and 'idn_quote' field names
                quote_idn = quote_info.get('idn_quote') or quote_info.get('idn') or f"#{a.get('quote_id', '')[:8]}"
                # Get customer name from nested customers relationship
                customer_name = quote_info.get('customers', {}).get('name', '—') if quote_info.get('customers') else '—'
                approval_rows.append(Tr(
                    Td(quote_idn),
                    Td(customer_name),
                    Td(format_money(quote_info.get('total_amount'), quote_info.get('currency', 'RUB'))),
                    Td(format_date_russian(a.get('requested_at')) if a.get('requested_at') else '—'),
                    Td(
                        A("Согласовать", href=f"/quotes/{a.get('quote_id')}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;")
                    )
                ))

            sections.append(
                Div(
                    H2(icon("clock", size=20), f" Ожидают согласования ({pending_count})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Сумма"), Th("Запрошено"), Th("Действие"))),
                            Tbody(*approval_rows) if approval_rows else Tbody(Tr(Td("Нет ожидающих", colspan="5", style="text-align: center;")))
                        , cls="table-enhanced") if approvals else P("Загрузка..."),
                        cls="table-enhanced-container"
                    ),
                    A("Открыть все согласования →", href="/quotes?status=pending_approval", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #f59e0b; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #f59e0b; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # PROCUREMENT: Quotes needing procurement evaluation
    # -------------------------------------------------------------------------
    if 'procurement' in roles:
        # Get quotes in pending_procurement status
        proc_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, created_at") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_procurement") \
            .is_("deleted_at", None) \
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        proc_quotes = proc_result.data or []
        proc_count = len(proc_quotes)

        if proc_count > 0:
            # Fetch buyer company names for these quotes via quote_items
            proc_quote_ids = [q["id"] for q in proc_quotes]
            buyer_names_by_quote = {}
            if proc_quote_ids:
                buyer_items_result = supabase.table("quote_items") \
                    .select("quote_id, purchasing_companies!purchasing_company_id(name)") \
                    .in_("quote_id", proc_quote_ids) \
                    .not_.is_("purchasing_company_id", "null") \
                    .execute()
                for bi in (buyer_items_result.data or []):
                    qid = bi.get("quote_id")
                    bc_name = (bi.get("purchasing_companies") or {}).get("name", "")
                    if bc_name:
                        buyer_names_by_quote.setdefault(qid, set()).add(bc_name)

            proc_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td((q.get("customers") or {}).get("name", "—")),
                    Td(", ".join(sorted(buyer_names_by_quote.get(q["id"], set()))) or "—"),
                    Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
                    Td(A("Оценить", href=f"/procurement", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in proc_quotes
            ]

            sections.append(
                Div(
                    H2(icon("package", size=20), f" Закупки: ожидают оценки ({proc_count})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Юрлицо-закупки"), Th("Создано"), Th("Действие"))),
                            Tbody(*proc_rows),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Открыть раздел Закупки →", href="/procurement", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #fbbf24; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #fbbf24; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # LOGISTICS: Quotes needing logistics data
    # -------------------------------------------------------------------------
    if 'logistics' in roles:
        log_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, created_at") \
            .eq("organization_id", org_id) \
            .in_("workflow_status", ["pending_logistics", "pending_logistics_and_customs"]) \
            .is_("deleted_at", None) \
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        log_quotes = log_result.data or []
        log_count = len(log_quotes)

        if log_count > 0:
            log_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td((q.get("customers") or {}).get("name", "—")),
                    Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
                    Td(A("Заполнить", href=f"/logistics", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in log_quotes
            ]

            sections.append(
                Div(
                    H2(icon("truck", size=20), f" Логистика: ожидают данных ({log_count})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Создано"), Th("Действие"))),
                            Tbody(*log_rows),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Открыть раздел Логистика →", href="/logistics", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #3b82f6; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #3b82f6; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # CUSTOMS: Quotes needing customs data
    # -------------------------------------------------------------------------
    if 'customs' in roles:
        cust_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, created_at") \
            .eq("organization_id", org_id) \
            .in_("workflow_status", ["pending_customs", "pending_logistics_and_customs"]) \
            .is_("deleted_at", None) \
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        cust_quotes = cust_result.data or []
        cust_count = len(cust_quotes)

        if cust_count > 0:
            cust_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td((q.get("customers") or {}).get("name", "—")),
                    Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
                    Td(A("Заполнить", href=f"/customs", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in cust_quotes
            ]

            sections.append(
                Div(
                    H2(icon("shield-check", size=20), f" Таможня: ожидают данных ({cust_count})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Создано"), Th("Действие"))),
                            Tbody(*cust_rows),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Открыть раздел Таможня →", href="/customs", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #8b5cf6; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #8b5cf6; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # QUOTE_CONTROLLER: Quotes needing review
    # -------------------------------------------------------------------------
    if 'quote_controller' in roles or 'admin' in roles:
        qc_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, total_amount, currency, created_at") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_quote_control") \
            .is_("deleted_at", None) \
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        qc_quotes = qc_result.data or []
        qc_count = len(qc_quotes)

        if qc_count > 0:
            qc_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td((q.get("customers") or {}).get("name", "—")),
                    Td(format_money(q.get("total_amount"), q.get("currency", "RUB"))),
                    Td(A("Проверить", href=f"/quote-control/{q['id']}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in qc_quotes
            ]

            sections.append(
                Div(
                    H2(icon("check-circle", size=20), f" Контроль КП: на проверке ({qc_count})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Сумма"), Th("Действие"))),
                            Tbody(*qc_rows),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Открыть раздел Контроль КП →", href="/quote-control", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #ec4899; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #ec4899; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # SPEC_CONTROLLER: Specifications needing work
    # -------------------------------------------------------------------------
    if 'spec_controller' in roles or 'admin' in roles:
        spec_counts = count_specifications_by_status(org_id)
        pending_specs = spec_counts.get('pending_review', 0) + spec_counts.get('draft', 0)

        # Also check quotes pending spec control
        spec_quotes_result = supabase.table("quotes") \
            .select("id", count="exact") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_spec_control") \
            .is_("deleted_at", None) \
            .execute()
        pending_spec_quotes = spec_quotes_result.count or 0

        total_spec_work = pending_specs + pending_spec_quotes

        if total_spec_work > 0:
            # Fetch specifications needing attention (draft + pending_review)
            spec_items_result = supabase.table("specifications") \
                .select("id, specification_number, status, created_at, quotes(id, idn_quote, customers(name))") \
                .eq("organization_id", org_id) \
                .in_("status", ["draft", "pending_review"]) \
                .is_("deleted_at", None) \
                .order("created_at", desc=True) \
                .limit(5) \
                .execute()
            spec_items = spec_items_result.data or []

            # Also fetch quotes pending spec control
            spec_ctrl_quotes_result = supabase.table("quotes") \
                .select("id, idn_quote, customers(name), created_at") \
                .eq("organization_id", org_id) \
                .eq("workflow_status", "pending_spec_control") \
                .is_("deleted_at", None) \
                .order("created_at", desc=True) \
                .limit(5) \
                .execute()
            spec_ctrl_quotes = spec_ctrl_quotes_result.data or []

            # Build table rows from specs needing attention
            spec_table_rows = []
            for s in spec_items:
                sq = s.get("quotes") or {}
                sc = sq.get("customers") or {}
                spec_status = s.get("status", "draft")
                status_label = {"draft": "Черновик", "pending_review": "На проверке"}.get(spec_status, spec_status)
                spec_table_rows.append(Tr(
                    Td(s.get("specification_number") or "—", style="font-weight: 500;"),
                    Td(sc.get("name", "—")),
                    Td(Span(status_label, style=f"display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; background: {'#f3f4f6' if spec_status == 'draft' else '#fef3c7'}; color: {'#6b7280' if spec_status == 'draft' else '#d97706'}; font-weight: 500;")),
                    Td(format_date_russian(s.get("created_at")) if s.get("created_at") else "—"),
                    Td(A("Открыть", href=f"/specifications/{s['id']}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ))
            # Add rows for quotes pending spec control
            for q in spec_ctrl_quotes:
                qc = q.get("customers") or {}
                spec_table_rows.append(Tr(
                    Td(q.get("idn_quote") or "—", style="font-weight: 500;"),
                    Td(qc.get("name", "—")),
                    Td(Span("Ожидает спец.", style="display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; background: #ede9fe; color: #4338ca; font-weight: 500;")),
                    Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
                    Td(A("Создать", href=f"/spec-control", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ))

            sections.append(
                Div(
                    H2(icon("file-text", size=20), f" Спецификации: требуют внимания ({total_spec_work})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("ИНД"), Th("Клиент"), Th("Статус"), Th("Создано"), Th("Действие"))),
                            Tbody(*spec_table_rows) if spec_table_rows else Tbody(Tr(Td("Нет данных", colspan="5", style="text-align: center;"))),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Открыть раздел Спецификации →", href="/spec-control", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #6366f1; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #6366f1; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # FINANCE: Active deals
    # -------------------------------------------------------------------------
    if 'finance' in roles or 'admin' in roles:
        deal_counts = count_deals_by_status(org_id)
        active_deals = deal_counts.get('active', 0)

        if active_deals > 0:
            # Get a few active deals
            active_deals_list = get_deals_by_status(org_id, 'active', limit=5)

            deal_rows = []
            for d in active_deals_list:
                # Deal is a dataclass, use attribute access not .get()
                deal_rows.append(Tr(
                    Td(d.deal_number or '—'),
                    Td(format_money(d.total_amount, d.currency or 'RUB')),
                    Td(A("Открыть", href=f"/finance/{d.id}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ))

            sections.append(
                Div(
                    H2(icon("wallet", size=20), f" Финансы: активные сделки ({active_deals})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("Сделка #"), Th("Сумма"), Th("Действие"))),
                            Tbody(*deal_rows) if deal_rows else Tbody(Tr(Td("Нет данных", colspan="3", style="text-align: center;"))),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Открыть раздел Финансы →", href="/finance", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #10b981; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #10b981; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # CURRENCY_CONTROLLER: Draft currency invoices needing review
    # -------------------------------------------------------------------------
    if 'currency_controller' in roles or 'admin' in roles:
        try:
            draft_ci_resp = supabase.table("currency_invoices").select(
                "id, deal_id, invoice_number, segment, status, deals!deal_id(deal_number)"
            ).eq("status", "draft").eq("organization_id", org_id).order("created_at", desc=False).limit(10).execute()
            draft_cis = draft_ci_resp.data or []

            if draft_cis:
                ci_rows = []
                for ci in draft_cis:
                    deal_info = (ci.get("deals") or {})
                    ci_rows.append(Tr(
                        Td(ci.get("invoice_number", "—"), style="font-weight: 500;"),
                        Td(
                            Span(ci.get("segment", ""),
                                 style="background: #f3f4f6; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;"),
                        ),
                        Td(deal_info.get("deal_number", "—")),
                        Td(A("Проверить", href=f"/currency-invoices/{ci['id']}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                    ))

                sections.append(
                    Div(
                        H2(icon("file-text", size=20), f" Валютные инвойсы: на проверке ({len(draft_cis)})",
                           style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                        Div(
                            Table(
                                Thead(Tr(Th("Номер инвойса"), Th("Сегмент"), Th("Сделка"), Th("Действие"))),
                                Tbody(*ci_rows),
                                cls="table-enhanced"
                            ),
                            cls="table-enhanced-container"
                        ),
                        A("Открыть реестр Валютных инвойсов →", href="/currency-invoices", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #8b5cf6; font-weight: 500;"),
                        cls="card-elevated", style="border-left: 4px solid #8b5cf6; padding: 16px;"
                    )
                )
        except Exception as e:
            print(f"Warning: failed to load currency invoice tasks: {e}")

    # -------------------------------------------------------------------------
    # SALES: My quotes (pending sales review)
    # -------------------------------------------------------------------------
    if 'sales' in roles:
        sales_query = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, total_amount, currency") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_sales_review") \
            .is_("deleted_at", None)
        if my_customer_ids is not None:
            sales_query = sales_query.in_("customer_id", my_customer_ids) if my_customer_ids else None
        if sales_query:
            sales_result = sales_query.order("updated_at", desc=True).limit(5).execute()
            sales_quotes = sales_result.data or []
        else:
            sales_quotes = []
        sales_count = len(sales_quotes)

        if sales_count > 0:
            sales_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td((q.get("customers") or {}).get("name", "—")),
                    Td(format_money(q.get("total_amount"), q.get("currency", "RUB"))),
                    Td(A("Продолжить", href=f"/quotes/{q['id']}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in sales_quotes
            ]

            sections.append(
                Div(
                    H2(icon("edit-3", size=20), f" Продажи: ожидают вашего решения ({sales_count})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Сумма"), Th("Действие"))),
                            Tbody(*sales_rows),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Все мои КП →", href="/quotes", style="display: inline-block; margin-top: 12px; font-size: 13px; color: #f97316; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #f97316; padding: 16px;"
                )
            )

    # -------------------------------------------------------------------------
    # SALES: Approved quotes - awaiting client response
    # -------------------------------------------------------------------------
    if 'sales' in roles:
        approved_query = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), total_amount, currency") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "approved") \
            .is_("deleted_at", None)
        if my_customer_ids is not None:
            approved_query = approved_query.in_("customer_id", my_customer_ids) if my_customer_ids else None
        if approved_query:
            approved_result = approved_query.order("updated_at", desc=True).limit(5).execute()
            approved_quotes = approved_result.data or []
        else:
            approved_quotes = []
        approved_count = len(approved_quotes)

        if approved_count > 0:
            approved_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td((q.get("customers") or {}).get("name", "—")),
                    Td(format_money(q.get("total_amount"), q.get("currency", "RUB"))),
                    Td(A("Открыть КП", href=f"/quotes/{q['id']}", cls="button",
                         style="padding: 0.25rem 0.5rem; font-size: 0.875rem; background: #0891b2; color: white; border-color: #0891b2;"))
                ) for q in approved_quotes
            ]

            sections.append(
                Div(
                    H2(icon("check-circle", size=20), f" Одобрено: ожидает ответа клиента ({approved_count})",
                       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
                    Div(
                        Table(
                            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Сумма"), Th("Действие"))),
                            Tbody(*approved_rows),
                            cls="table-enhanced"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("Все мои КП →", href="/quotes?status=approved",
                      style="display: inline-block; margin-top: 12px; font-size: 13px; color: #0891b2; font-weight: 500;"),
                    cls="card-elevated", style="border-left: 4px solid #0891b2; padding: 16px;"
                )
            )

    return sections


def _get_sales_summary_blocks(user_id: str, org_id: str, date_from: str, date_to: str, supabase) -> list:
    """
    Sales manager summary blocks: my requests (pending), my specs, my quotes.
    Returns list of FastHTML elements (date filter + 3 summary cards).
    """
    # Default date range: last 30 days
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")

    date_to_end = date_to + "T23:59:59"

    # Q1: All my quotes (single query — pending is derived below)
    all_quotes_result = supabase.table("quotes") \
        .select("id, total_amount, workflow_status") \
        .eq("organization_id", org_id) \
        .eq("created_by", user_id) \
        .is_("deleted_at", None) \
        .gte("created_at", date_from) \
        .lte("created_at", date_to_end) \
        .execute()

    all_quotes = all_quotes_result.data or []
    all_count = len(all_quotes)
    all_sum = sum(
        Decimal(str(q.get("total_amount") or 0))
        for q in all_quotes
    )

    # Derive pending_procurement subset from all_quotes (saves 1 DB round-trip)
    pending_quotes = [q for q in all_quotes if q.get("workflow_status") == "pending_procurement"]
    pending_count = len(pending_quotes)
    pending_sum = sum(
        Decimal(str(q.get("total_amount") or 0))
        for q in pending_quotes
    )

    # Q2: My specifications (via parent quote created_by)
    specs_result = supabase.table("specifications") \
        .select("id, created_at, quotes!inner(created_by, total_amount)") \
        .eq("organization_id", org_id) \
        .eq("quotes.created_by", user_id) \
        .is_("deleted_at", None) \
        .gte("created_at", date_from) \
        .lte("created_at", date_to_end) \
        .execute()

    specs = specs_result.data or []
    specs_count = len(specs)
    specs_sum = sum(
        Decimal(str((s.get("quotes") or {}).get("total_amount") or 0))
        for s in specs
    )

    card_style = "background: white; border-radius: 0.75rem; padding: 1.25rem; border: 1px solid #e5e7eb; display: flex; flex-direction: column;"
    label_style = "color: #6b7280; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem;"
    count_style_tpl = "font-size: 2rem; font-weight: 700; margin-bottom: 0.25rem; color: {};"
    sum_style = "font-size: 0.95rem; color: #374151; margin-bottom: 0.75rem;"
    link_style = "color: #3b82f6; font-size: 0.875rem; text-decoration: none; margin-top: auto; display: flex; align-items: center; gap: 0.25rem;"

    return [
        # Date range filter
        Div(
            Form(
                Div(
                    Div(
                        Span(icon("calendar", size=16), " Период:", style="font-weight: 500; color: #374151; margin-right: 0.75rem; display: flex; align-items: center; gap: 0.25rem;"),
                        Label("С ", Input(type="date", name="date_from", value=date_from, style="padding: 0.375rem 0.5rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.875rem;"), style="display: flex; align-items: center; gap: 0.25rem;"),
                        Label("По ", Input(type="date", name="date_to", value=date_to, style="padding: 0.375rem 0.5rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.875rem;"), style="display: flex; align-items: center; gap: 0.25rem;"),
                        style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;"
                    ),
                    style="display: flex; align-items: center;"
                ),
                Hidden(name="tab", value="overview"),
                hx_get="/dashboard",
                hx_target="#tab-content",
                hx_trigger="change delay:300ms",
            ),
            style="margin-bottom: 1.25rem;"
        ),

        # Section header
        H2(icon("briefcase", size=22), " Мои показатели", style="margin-bottom: 0.75rem; font-size: 1.25rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem;"),

        # 3-column grid of summary cards
        Div(
            # Block 1: My requests (pending procurement)
            Div(
                Div("Мои запросы (в работе)", style=label_style),
                Div(str(pending_count), style=count_style_tpl.format("#3b82f6")),
                Div(format_money(pending_sum), style=sum_style),
                A("Посмотреть все ", icon("arrow-right", size=14), href="/quotes?status=pending_procurement", style=link_style),
                style=card_style,
            ),

            # Block 2: My specifications
            Div(
                Div("Мои СП", style=label_style),
                Div(str(specs_count), style=count_style_tpl.format("#10b981")),
                Div(format_money(specs_sum), style=sum_style),
                A("Посмотреть все ", icon("arrow-right", size=14), href="/dashboard?tab=spec-control", style=link_style),
                style=card_style,
            ),

            # Block 3: My quotes (all)
            Div(
                Div("Мои КП", style=label_style),
                Div(str(all_count), style=count_style_tpl.format("#f59e0b")),
                Div(format_money(all_sum), style=sum_style),
                A("Посмотреть все ", icon("arrow-right", size=14), href="/quotes", style=link_style),
                style=card_style,
            ),

            style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 2rem;"
        ),
    ]


def _dashboard_overview_content(user_id: str, org_id: str, roles: list, user: dict, supabase, date_from: str = None, date_to: str = None) -> list:
    """
    Overview tab content - overall stats and role-specific task summaries.
    Used for admin and top_manager roles.
    """
    # Get overall quotes stats
    # Department heads see all quotes in the overview (they manage their teams)
    is_admin = any(r in roles for r in ["admin", "top_manager", "head_of_sales", "head_of_procurement", "head_of_logistics", "head_of_customs"])

    if is_admin:
        quotes_query = supabase.table("quotes") \
            .select("id, status, workflow_status, total_amount") \
            .eq("organization_id", org_id) \
            .is_("deleted_at", None)
        quotes_result = quotes_query.execute()
        quotes = quotes_result.data or []
    else:
        # Multi-query: find quotes for user's assigned customers OR assigned in any department
        _qs = "id, status, workflow_status, total_amount"
        # Get quotes for customers assigned to this user (sales managers)
        my_customers = supabase.table("customers").select("id") \
            .eq("organization_id", org_id).eq("manager_id", user_id).execute()
        my_customer_ids = [c["id"] for c in (my_customers.data or [])]
        q1_data = []
        if my_customer_ids:
            q1 = supabase.table("quotes").select(_qs) \
                .eq("organization_id", org_id).in_("customer_id", my_customer_ids) \
                .is_("deleted_at", None).execute()
            q1_data = q1.data or []
        # Also find quotes where user is assigned in any department.
        # Procurement assignment lives on quote_items now (single source of truth) —
        # use an inner join so the parent row comes back when ≥1 item matches.
        q2 = supabase.table("quotes").select(f"{_qs}, quote_items!inner(id)") \
            .eq("organization_id", org_id).eq("quote_items.assigned_procurement_user", user_id) \
            .is_("deleted_at", None).execute()
        q3 = supabase.table("quotes").select(_qs) \
            .eq("organization_id", org_id).eq("assigned_logistics_user", user_id) \
            .is_("deleted_at", None).execute()
        q4 = supabase.table("quotes").select(_qs) \
            .eq("organization_id", org_id).eq("assigned_customs_user", user_id) \
            .is_("deleted_at", None).execute()
        # Merge and deduplicate by quote ID
        seen_ids = set()
        quotes = []
        for data in [q1_data, q2.data or [], q3.data or [], q4.data or []]:
            for q in data:
                if q["id"] not in seen_ids:
                    seen_ids.add(q["id"])
                    quotes.append(q)

    total_quotes = len(quotes)
    total_revenue = sum(
        Decimal(str(q.get("total_amount") or 0))
        for q in quotes if q.get("workflow_status") in ["approved", "deal"]
    )

    # Count quotes in active workflow stages
    active_workflow = len([q for q in quotes if q.get("workflow_status") not in
                          ["draft", "approved", "deal", "rejected", "cancelled", None]])

    # Get recent quotes
    if is_admin:
        recent_query = supabase.table("quotes") \
            .select("id, idn_quote, customer_id, customers(name), status, workflow_status, total_amount, created_at") \
            .eq("organization_id", org_id) \
            .is_("deleted_at", None) \
            .order("created_at", desc=True) \
            .limit(5)
        recent_result = recent_query.execute()
        recent_quotes = recent_result.data or []
    else:
        # Multi-query for recent quotes: customer-manager + department assignment
        _rselect = "id, idn_quote, customer_id, customers(name), status, workflow_status, total_amount, created_at"
        # Reuse my_customer_ids from stats query above
        rq1_data = []
        if my_customer_ids:
            rq1 = supabase.table("quotes").select(_rselect) \
                .eq("organization_id", org_id).in_("customer_id", my_customer_ids) \
                .is_("deleted_at", None) \
                .order("created_at", desc=True).limit(10).execute()
            rq1_data = rq1.data or []
        # Procurement assignment is item-level — inner-join filters to quotes
        # where ≥1 non-deleted item is assigned to this user.
        rq2 = supabase.table("quotes").select(f"{_rselect}, quote_items!inner(id)") \
            .eq("organization_id", org_id).eq("quote_items.assigned_procurement_user", user_id) \
            .is_("deleted_at", None) \
            .order("created_at", desc=True).limit(10).execute()
        rq3 = supabase.table("quotes").select(_rselect) \
            .eq("organization_id", org_id).eq("assigned_logistics_user", user_id) \
            .is_("deleted_at", None) \
            .order("created_at", desc=True).limit(10).execute()
        rq4 = supabase.table("quotes").select(_rselect) \
            .eq("organization_id", org_id).eq("assigned_customs_user", user_id) \
            .is_("deleted_at", None) \
            .order("created_at", desc=True).limit(10).execute()
        # Merge, deduplicate, sort by created_at, take top 5
        seen_ids = set()
        all_recent = []
        for data in [rq1_data, rq2.data or [], rq3.data or [], rq4.data or []]:
            for q in data:
                if q["id"] not in seen_ids:
                    seen_ids.add(q["id"])
                    all_recent.append(q)
        all_recent.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        recent_quotes = all_recent[:5]

    # Build role-specific task sections
    task_sections = _get_role_tasks_sections(user_id, org_id, roles, supabase)

    # Role badges
    role_names = {
        'sales': ('Продажи', '#f97316'),
        'sales_manager': ('Менеджер продаж', '#ea580c'),
        'procurement': ('Закупки', '#fbbf24'),
        'logistics': ('Логистика', '#3b82f6'),
        'customs': ('Таможня', '#8b5cf6'),
        'quote_controller': ('Контроль КП', '#ec4899'),
        'spec_controller': ('Контроль спецификаций', '#6366f1'),
        'finance': ('Финансы', '#10b981'),
        'top_manager': ('Топ-менеджер', '#f59e0b'),
        'head_of_sales': ('Начальник отдела продаж', '#d97706'),
        'head_of_procurement': ('Начальник отдела закупок', '#ca8a04'),
        'head_of_logistics': ('Начальник отдела логистики', '#2563eb'),
        'admin': ('Админ', '#ef4444'),
    }

    role_badges = [
        Span(role_names.get(r, (r, '#6b7280'))[0],
             style=f"display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-right: 0.25rem; background: {role_names.get(r, (r, '#6b7280'))[1]}20; color: {role_names.get(r, (r, '#6b7280'))[1]}; border: 1px solid {role_names.get(r, (r, '#6b7280'))[1]}40;")
        for r in roles
    ] if roles else [Span("Нет ролей", style="color: #9ca3af; font-size: 0.875rem;")]

    # Sales manager summary blocks (only for sales roles)
    is_sales = any(r in roles for r in ["sales", "sales_manager", "head_of_sales", "admin", "top_manager"])
    sales_blocks = _get_sales_summary_blocks(user_id, org_id, date_from, date_to, supabase) if is_sales else []

    return [
        # Header with roles
        Div(
            H1("Добро пожаловать!"),
            P(
                Strong("Организация: "), user.get('org_name', 'Неизвестно'), " | ",
                Strong("Ваши роли: "), *role_badges
            ),
            style="margin-bottom: 1rem;"
        ),

        # Sales manager summary blocks (date filter + 3 cards)
        *sales_blocks,

        # Overall stats cards
        Div(
            Div(
                Div(str(total_quotes), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            Div(
                Div(format_money(total_revenue), cls="stat-value"),
                Div("Выручка (одобренные)"),
                cls="card stat-card"
            ),
            Div(
                Div(str(active_workflow), cls="stat-value"),
                Div("В работе"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Role-specific task sections
        H2(icon("list-todo", size=22), " Задачи по отделам", cls="section-header") if task_sections else "",
        *task_sections,

        # If no tasks, show helpful message
        Div(
            P(icon("check-circle", size=18), " Нет активных задач! Все под контролем.", style="color: #059669; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;"),
            cls="card", style="text-align: center; background: #ecfdf5;"
        ) if not task_sections else "",

        # Recent quotes
        H2(icon("file-text", size=22), " Последние КП", cls="section-header"),
        Div(
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Сумма"), Th("Действия"))),
                Tbody(
                    *[Tr(
                        Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                        Td((q.get("customers") or {}).get("name", "—")),
                        Td(workflow_status_badge(q.get("workflow_status") or q.get("status", "draft"))),
                        Td(format_money(q.get("total_amount"))),
                        Td(A("Открыть", href=f"/quotes/{q['id']}"))
                    ) for q in recent_quotes]
                ) if recent_quotes else Tbody(Tr(Td("Нет КП", colspan="5", style="text-align: center;")))
            , cls="table-enhanced"),
            cls="table-enhanced-container"
        ),
        A("Все КП →", href="/quotes"),
    ]


def _dashboard_procurement_content(user_id: str, org_id: str, supabase, status_filter: str = None, roles: list = None) -> list:
    """
    Procurement workspace tab content.
    Shows quotes with items having brands assigned to current user.
    Admin users see ALL items regardless of brand assignment.
    """
    try:
        return _dashboard_procurement_content_inner(user_id, org_id, supabase, status_filter, roles)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return [
            Div(
                H3("Ошибка загрузки данных закупок"),
                P(f"Не удалось загрузить данные закупок. Попробуйте обновить страницу."),
                P(f"Техническая информация: {str(e)}", style="font-size: 0.75rem; color: #9ca3af;"),
                cls="card",
                style="border-left: 4px solid #ef4444; padding: 1.5rem;"
            )
        ]


def _dashboard_procurement_content_inner(user_id: str, org_id: str, supabase, status_filter: str = None, roles: list = None) -> list:
    """Inner implementation of procurement content (extracted for error handling).

    Visibility logic (routing cascade):
    1. Admin users see ALL quotes
    2. Regular procurement users see quotes where:
       a) They are assigned to ≥1 quote_item (item-level assignment, single source of truth), OR
       b) Quote items match their brand assignments (brand routing fallback)
    """
    # Check if user is admin - bypass brand filtering
    is_admin = roles and ("admin" in roles or "head_of_procurement" in roles)

    # Get brands assigned to this user (empty for admin = see all)
    my_brands = get_assigned_brands(user_id, org_id) if not is_admin else []
    my_brands_lower = [b.lower() for b in my_brands]

    quotes_with_details = []

    # Step 1: For non-admin users, get quote IDs where user is assigned at item level.
    # Source of truth is quote_items.assigned_procurement_user.
    assigned_quote_ids = set()
    if not is_admin:
        try:
            assigned_result = supabase.table("quote_items") \
                .select("quote_id") \
                .eq("assigned_procurement_user", user_id) \
                .execute()
            assigned_quote_ids = set(
                row["quote_id"] for row in (assigned_result.data or []) if row.get("quote_id")
            )
        except Exception as e:
            print(f"Warning: Could not query item-level procurement assignments: {e}")

    # Step 2: Brand-based filtering (existing logic) + admin bypass
    if is_admin or my_brands or assigned_quote_ids:
        # Query quote_items with my brands
        items_result = supabase.table("quote_items") \
            .select("id, quote_id, brand, procurement_status, quantity, product_name") \
            .execute()

        # Filter items for my brands (case-insensitive) - admins see all
        if is_admin:
            my_items = items_result.data or []
        else:
            # Include items from brand-matched quotes AND from assigned quotes
            my_items = [item for item in (items_result.data or [])
                        if (item.get("brand") or "").lower() in my_brands_lower
                        or item.get("quote_id") in assigned_quote_ids]

        # Group items by quote_id
        items_by_quote = {}
        for item in my_items:
            qid = item["quote_id"]
            if qid not in items_by_quote:
                items_by_quote[qid] = []
            items_by_quote[qid].append(item)

        # Union: brand-matched quote IDs + assigned quote IDs
        all_visible_quote_ids = list(set(items_by_quote.keys()) | assigned_quote_ids)

        if all_visible_quote_ids:
            # Get full quote data for those quotes
            quotes_query = supabase.table("quotes") \
                .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at") \
                .eq("organization_id", org_id) \
                .in_("id", all_visible_quote_ids) \
                .is_("deleted_at", None) \
                .order("created_at", desc=True)

            quotes_result = quotes_query.execute()

            # Enrich quotes with item details
            for q in (quotes_result.data or []):
                q_items = items_by_quote.get(q["id"], [])
                total_items = len(q_items)
                completed_items = len([i for i in q_items if i.get("procurement_status") == "completed"])
                brands_in_quote = list(set([(i.get("brand") or "") for i in q_items if i.get("brand")]))

                quotes_with_details.append({
                    **q,
                    "my_items": q_items,
                    "my_items_total": total_items,
                    "my_items_completed": completed_items,
                    "my_items_pending": total_items - completed_items,
                    "my_brands_in_quote": brands_in_quote
                })

    # Apply status filter if provided
    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    # Separate quotes by workflow status
    pending_quotes = [q for q in quotes_with_details
                      if q.get("workflow_status") == "pending_procurement"]
    other_quotes = [q for q in quotes_with_details
                    if q.get("workflow_status") != "pending_procurement"]

    # Count stats
    pending_count = len(pending_quotes)
    in_progress_count = len([q for q in quotes_with_details
                             if q.get("workflow_status") in ["pending_logistics", "pending_customs", "pending_logistics_and_customs", "pending_sales_review"]])
    completed_count = len([q for q in quotes_with_details
                           if q.get("workflow_status") in ["approved", "deal", "sent_to_client"]])

    # Build the table rows
    def quote_row(q, show_work_button=True):
        customer_name = "—"
        if q.get("customers"):
            customer_name = q["customers"].get("name", "—")

        workflow_status = q.get("workflow_status") or q.get("status", "draft")

        my_total = q.get("my_items_total", 0)
        my_completed = q.get("my_items_completed", 0)
        brands_list = q.get("my_brands_in_quote", [])

        progress_pct = int((my_completed / my_total * 100) if my_total > 0 else 0)
        progress_bar = Div(
            Div(style=f"width: {progress_pct}%; height: 100%; background: #22c55e;"),
            style="width: 60px; height: 8px; background: #e5e7eb; border-radius: 4px; display: inline-block; margin-right: 0.5rem; overflow: hidden;",
            title=f"{my_completed}/{my_total} позиций оценено"
        )

        items_info = Span(progress_bar, f"{my_completed}/{my_total}", style="font-size: 0.875rem; color: #666;")

        brands_display = ", ".join([b for b in brands_list[:3] if b])
        if len(brands_list) > 3:
            brands_display += f" +{len(brands_list) - 3}"

        return Tr(
            Td(
                A(q.get("idn_quote", f"#{q['id'][:8]}"), href=f"/quotes/{q['id']}", style="font-weight: 500;"),
                Div(brands_display, style="font-size: 0.75rem; color: #888; margin-top: 2px;")
            ),
            Td(customer_name),
            Td(workflow_status_badge(workflow_status)),
            Td(items_info),
            Td(format_money(q.get("total_amount"))),
            Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
            Td(
                btn_link("Открыть", href=f"/quotes/{q['id']}", variant="primary", size="sm")
                if show_work_button and workflow_status == "pending_procurement" else
                btn_link("Просмотр", href=f"/quotes/{q['id']}", variant="ghost", size="sm")
            )
        )

    # Status filter options
    status_options = [
        ("all", "Все статусы"),
        ("pending_procurement", "Ожидают оценки"),
        ("pending_logistics", "На логистике"),
        ("pending_customs", "На таможне"),
        ("pending_sales_review", "У менеджера продаж"),
        ("pending_quote_control", "На проверке"),
        ("approved", "Одобрено"),
        ("deal", "Сделка"),
    ]

    filter_form = Form(
        Label("Фильтр по статусу: ", For="status_filter", style="margin-right: 0.5rem;"),
        Select(
            *[Option(label, value=value, selected=(value == (status_filter or "all")))
              for value, label in status_options],
            name="status_filter",
            id="status_filter",
            onchange="this.form.submit()",
            style="padding: 0.375rem 0.75rem; border-radius: 4px; border: 1px solid #d1d5db;"
        ),
        Hidden(name="tab", value="procurement"),
        method="get",
        action="/dashboard",
        style="margin-bottom: 1rem;"
    )

    return [
        # Header
        Div(
            H1(icon("shopping-cart", size=28), " Закупки", cls="page-header"),
            P("Рабочая зона менеджера по закупкам"),
            style="margin-bottom: 1rem;"
        ),

        # My assigned brands (admin sees all)
        Div(
            H3("Мои бренды"),
            P("Все бренды (администратор)" if is_admin else (", ".join([b for b in my_brands if b]) if my_brands else "Нет назначенных брендов. Обратитесь к администратору.")),
            cls="card"
        ),

        # Stats
        Div(
            Div(
                Div(str(pending_count), cls="stat-value"),
                Div("Ожидает оценки"),
                cls="card stat-card",
                style="border-left: 4px solid #f59e0b;" if pending_count > 0 else ""
            ),
            Div(
                Div(str(in_progress_count), cls="stat-value"),
                Div("В процессе"),
                cls="card stat-card"
            ),
            Div(
                Div(str(completed_count), cls="stat-value"),
                Div("Завершено"),
                cls="card stat-card"
            ),
            Div(
                Div(str(len(quotes_with_details)), cls="stat-value"),
                Div("Всего моих КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Filter
        filter_form,

        # Pending quotes section
        Div(
            Div(
                Div(
                    H3(icon("alert-circle", size=20), " Ожидают оценки", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ПРОГРЕСС"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in pending_quotes]
                        ) if pending_quotes else Tbody(Tr(Td("Нет КП на оценке", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {pending_count}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if not status_filter or status_filter == "all" else None,

        # Filtered view
        Div(
            Div(
                Div(
                    H3(f"КП: {dict(status_options).get(status_filter, status_filter)}", style="margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ПРОГРЕСС"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in quotes_with_details]
                        ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(quotes_with_details)}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if status_filter and status_filter != "all" else None,

        # Other quotes
        Div(
            Div(
                Div(
                    H3(icon("file-text", size=20), " Остальные КП", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ПРОГРЕСС"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q, show_work_button=False) for q in other_quotes]
                        ) if other_quotes else Tbody(Tr(Td("Нет других КП", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(other_quotes)}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if (not status_filter or status_filter == "all") and other_quotes else None,
    ]


def _dashboard_logistics_content(user_id: str, org_id: str, supabase, status_filter: str = None, roles: list = None) -> list:
    """
    Logistics workspace tab content.
    Shows quotes in logistics stage.
    """
    # Get quotes for this organization
    is_admin = roles and ("admin" in roles or "head_of_logistics" in roles)
    quotes_query = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at, logistics_completed_at, customs_completed_at, assigned_logistics_user") \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None)
    if not is_admin:
        quotes_query = quotes_query.eq("assigned_logistics_user", user_id)
    quotes_result = quotes_query.order("created_at", desc=True).execute()

    all_quotes = quotes_result.data or []

    logistics_statuses = [
        "pending_logistics",
        "pending_customs",
        "pending_logistics_and_customs",
        "pending_sales_review",
    ]

    quotes_with_details = []
    for q in all_quotes:
        ws = q.get("workflow_status")
        if ws in logistics_statuses or status_filter:
            logistics_done = q.get("logistics_completed_at") is not None
            customs_done = q.get("customs_completed_at") is not None
            quotes_with_details.append({
                **q,
                "logistics_done": logistics_done,
                "customs_done": customs_done,
                "assigned_to_me": q.get("assigned_logistics_user") == user_id
            })

    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    pending_quotes = [q for q in quotes_with_details
                      if q.get("workflow_status") in ["pending_logistics", "pending_customs", "pending_logistics_and_customs"]
                      and not q.get("logistics_done")]
    completed_quotes = [q for q in quotes_with_details
                        if q.get("logistics_done")]

    pending_count = len(pending_quotes)
    completed_count = len(completed_quotes)

    def quote_row(q, show_work_button=True):
        customer_name = "—"
        if q.get("customers"):
            customer_name = q["customers"].get("name", "—")

        workflow_status = q.get("workflow_status") or q.get("status", "draft")
        logistics_done = q.get("logistics_done", False)
        customs_done = q.get("customs_done", False)

        stages_status = []
        if logistics_done:
            stages_status.append(Span(icon("check-circle", size=14), " Логистика", style="color: #22c55e; margin-right: 0.5rem; display: inline-flex; align-items: center; gap: 0.25rem;"))
        else:
            stages_status.append(Span(icon("clock", size=14), " Логистика", style="color: #f59e0b; margin-right: 0.5rem; display: inline-flex; align-items: center; gap: 0.25rem;"))

        if customs_done:
            stages_status.append(Span(icon("check-circle", size=14), " Таможня", style="color: #22c55e; display: inline-flex; align-items: center; gap: 0.25rem;"))
        else:
            stages_status.append(Span(icon("clock", size=14), " Таможня", style="color: #f59e0b; display: inline-flex; align-items: center; gap: 0.25rem;"))

        return Tr(
            Td(A(q.get("idn_quote", f"#{q['id'][:8]}"), href=f"/quotes/{q['id']}", style="font-weight: 500;")),
            Td(customer_name),
            Td(workflow_status_badge(workflow_status)),
            Td(*stages_status),
            Td(format_money(q.get("total_amount"))),
            Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
            Td(
                btn_link("Работать", href=f"/logistics/{q['id']}", variant="primary", size="sm")
                if show_work_button and not logistics_done and workflow_status in ["pending_logistics", "pending_customs", "pending_logistics_and_customs"] else
                btn_link("Просмотр", href=f"/logistics/{q['id']}", variant="ghost", size="sm")
            )
        )

    status_options = [
        ("all", "Все статусы"),
        ("pending_logistics", "На логистике"),
        ("pending_customs", "На таможне (параллельно)"),
        ("pending_sales_review", "У менеджера продаж"),
    ]

    filter_form = Form(
        Label("Фильтр по статусу: ", For="status_filter", style="margin-right: 0.5rem;"),
        Select(
            *[Option(label, value=value, selected=(value == (status_filter or "all")))
              for value, label in status_options],
            name="status_filter",
            id="status_filter",
            onchange="this.form.submit()",
            style="padding: 0.375rem 0.75rem; border-radius: 4px; border: 1px solid #d1d5db;"
        ),
        Hidden(name="tab", value="logistics"),
        method="get",
        action="/dashboard",
        style="margin-bottom: 1rem;"
    )

    return [
        Div(
            H1(icon("truck", size=28), " Логистика", cls="page-header"),
            P("Рабочая зона логиста"),
            style="margin-bottom: 1rem;"
        ),

        Div(
            Div(
                Div(str(pending_count), cls="stat-value"),
                Div("Ожидает логистики"),
                cls="card stat-card",
                style="border-left: 4px solid #f59e0b;" if pending_count > 0 else ""
            ),
            Div(
                Div(str(completed_count), cls="stat-value"),
                Div("Завершено"),
                cls="card stat-card"
            ),
            Div(
                Div(str(len(quotes_with_details)), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        filter_form,

        Div(
            Div(
                Div(
                    H3(icon("package", size=20), " Ожидают логистики", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ЭТАПЫ"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in pending_quotes]
                        ) if pending_quotes else Tbody(Tr(Td("Нет КП на логистике", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {pending_count}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if not status_filter or status_filter == "all" else None,

        Div(
            Div(
                Div(
                    H3(f"КП: {dict(status_options).get(status_filter, status_filter)}", style="margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ЭТАПЫ"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in quotes_with_details]
                        ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(quotes_with_details)}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if status_filter and status_filter != "all" else None,

        Div(
            Div(
                Div(
                    H3(icon("check-circle", size=20), " Завершено", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ЭТАПЫ"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q, show_work_button=False) for q in completed_quotes]
                        ) if completed_quotes else Tbody(Tr(Td("Нет завершённых КП", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(completed_quotes)}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if (not status_filter or status_filter == "all") and completed_quotes else None,
    ]


def _dashboard_customs_content(user_id: str, org_id: str, supabase, status_filter: str = None, roles: list = None) -> list:
    """
    Customs workspace tab content.
    Shows quotes in customs stage.
    """
    is_admin = roles and ("admin" in roles or "head_of_customs" in roles)
    quotes_query = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at, logistics_completed_at, customs_completed_at, assigned_customs_user") \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None)
    if not is_admin:
        quotes_query = quotes_query.eq("assigned_customs_user", user_id)
    quotes_result = quotes_query.order("created_at", desc=True).execute()

    all_quotes = quotes_result.data or []

    customs_statuses = [
        "pending_customs",
        "pending_logistics",
        "pending_logistics_and_customs",
        "pending_sales_review",
    ]

    quotes_with_details = []
    for q in all_quotes:
        ws = q.get("workflow_status")
        if ws in customs_statuses or status_filter:
            logistics_done = q.get("logistics_completed_at") is not None
            customs_done = q.get("customs_completed_at") is not None
            quotes_with_details.append({
                **q,
                "logistics_done": logistics_done,
                "customs_done": customs_done,
                "assigned_to_me": q.get("assigned_customs_user") == user_id
            })

    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    pending_quotes = [q for q in quotes_with_details
                      if q.get("workflow_status") in ["pending_customs", "pending_logistics", "pending_logistics_and_customs"]
                      and not q.get("customs_done")]
    completed_quotes = [q for q in quotes_with_details
                        if q.get("customs_done")]

    pending_count = len(pending_quotes)
    completed_count = len(completed_quotes)

    def quote_row(q, show_work_button=True):
        customer_name = "—"
        if q.get("customers"):
            customer_name = q["customers"].get("name", "—")

        workflow_status = q.get("workflow_status") or q.get("status", "draft")
        logistics_done = q.get("logistics_done", False)
        customs_done = q.get("customs_done", False)

        stages_status = []
        if logistics_done:
            stages_status.append(Span(icon("check-circle", size=14), " Логистика", style="color: #22c55e; margin-right: 0.5rem; display: inline-flex; align-items: center; gap: 0.25rem;"))
        else:
            stages_status.append(Span(icon("clock", size=14), " Логистика", style="color: #f59e0b; margin-right: 0.5rem; display: inline-flex; align-items: center; gap: 0.25rem;"))

        if customs_done:
            stages_status.append(Span(icon("check-circle", size=14), " Таможня", style="color: #22c55e; display: inline-flex; align-items: center; gap: 0.25rem;"))
        else:
            stages_status.append(Span(icon("clock", size=14), " Таможня", style="color: #f59e0b; display: inline-flex; align-items: center; gap: 0.25rem;"))

        return Tr(
            Td(A(q.get("idn_quote", f"#{q['id'][:8]}"), href=f"/quotes/{q['id']}", style="font-weight: 500;")),
            Td(customer_name),
            Td(workflow_status_badge(workflow_status)),
            Td(*stages_status),
            Td(format_money(q.get("total_amount"))),
            Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
            Td(
                btn_link("Работать", href=f"/customs/{q['id']}", variant="primary", size="sm")
                if show_work_button and not customs_done and workflow_status in ["pending_customs", "pending_logistics", "pending_logistics_and_customs"] else
                btn_link("Просмотр", href=f"/customs/{q['id']}", variant="ghost", size="sm")
            )
        )

    status_options = [
        ("all", "Все статусы"),
        ("pending_customs", "На таможне"),
        ("pending_logistics", "На логистике (параллельно)"),
        ("pending_sales_review", "У менеджера продаж"),
    ]

    filter_form = Form(
        Label("Фильтр по статусу: ", For="status_filter", style="margin-right: 0.5rem;"),
        Select(
            *[Option(label, value=value, selected=(value == (status_filter or "all")))
              for value, label in status_options],
            name="status_filter",
            id="status_filter",
            onchange="this.form.submit()",
            style="padding: 0.375rem 0.75rem; border-radius: 4px; border: 1px solid #d1d5db;"
        ),
        Hidden(name="tab", value="customs"),
        method="get",
        action="/dashboard",
        style="margin-bottom: 1rem;"
    )

    return [
        Div(
            H1(icon("shield-check", size=28), " Таможня", cls="page-header"),
            P("Рабочая зона таможенного отдела"),
            style="margin-bottom: 1rem;"
        ),

        Div(
            Div(
                Div(str(pending_count), cls="stat-value"),
                Div("Ожидает таможни"),
                cls="card stat-card",
                style="border-left: 4px solid #f59e0b;" if pending_count > 0 else ""
            ),
            Div(
                Div(str(completed_count), cls="stat-value"),
                Div("Завершено"),
                cls="card stat-card"
            ),
            Div(
                Div(str(len(quotes_with_details)), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        filter_form,

        Div(
            Div(
                Div(
                    H3(icon("shield-check", size=20), " Ожидают таможни", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ЭТАПЫ"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in pending_quotes]
                        ) if pending_quotes else Tbody(Tr(Td("Нет КП на таможне", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {pending_count}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if not status_filter or status_filter == "all" else None,

        Div(
            Div(
                Div(
                    H3(f"КП: {dict(status_options).get(status_filter, status_filter)}", style="margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ЭТАПЫ"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in quotes_with_details]
                        ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(quotes_with_details)}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if status_filter and status_filter != "all" else None,

        Div(
            Div(
                Div(
                    H3(icon("check-circle", size=20), " Завершено", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("ЭТАПЫ"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q, show_work_button=False) for q in completed_quotes]
                        ) if completed_quotes else Tbody(Tr(Td("Нет завершённых КП", colspan="7", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(completed_quotes)}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if (not status_filter or status_filter == "all") and completed_quotes else None,
    ]


def _dashboard_quote_control_content(user_id: str, org_id: str, supabase, status_filter: str = None) -> list:
    """
    Quote Control workspace tab content.
    Shows quotes pending review for quote_controller role.
    """
    quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at, deal_type, current_version_id") \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .order("created_at", desc=True) \
        .execute()

    all_quotes = quotes_result.data or []

    control_statuses = [
        "pending_quote_control",
        "pending_approval",
        "approved",
        "sent_to_client",
    ]

    quotes_with_details = []
    for q in all_quotes:
        ws = q.get("workflow_status")
        if ws in control_statuses or status_filter:
            quotes_with_details.append({
                **q,
                "needs_review": ws == "pending_quote_control",
                "pending_approval": ws == "pending_approval",
                "is_approved": ws == "approved",
                "sent_to_client": ws == "sent_to_client",
            })

    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    pending_quotes = [q for q in quotes_with_details if q.get("needs_review")]
    awaiting_approval_quotes = [q for q in quotes_with_details if q.get("pending_approval")]
    approved_quotes = [q for q in quotes_with_details if q.get("is_approved") or q.get("sent_to_client")]

    pending_count = len(pending_quotes)
    awaiting_count = len(awaiting_approval_quotes)
    approved_count = len(approved_quotes)

    def quote_row(q, show_work_button=True):
        customer_name = "—"
        if q.get("customers"):
            customer_name = q["customers"].get("name", "—")

        workflow_status = q.get("workflow_status") or q.get("status", "draft")
        deal_type = q.get("deal_type")
        deal_type_badge = ""
        if deal_type == "supply":
            deal_type_badge = Span("Поставка", style="background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;")
        elif deal_type == "transit":
            deal_type_badge = Span("Транзит", style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;")

        return Tr(
            Td(
                A(q.get("idn_quote", f"#{q['id'][:8]}"), href=f"/quotes/{q['id']}", style="font-weight: 500;"),
                deal_type_badge if deal_type else "",
            ),
            Td(customer_name),
            Td(workflow_status_badge(workflow_status)),
            Td(format_money(q.get("total_amount"))),
            Td(format_date_russian(q.get("created_at")) if q.get("created_at") else "—"),
            Td(
                btn_link("Проверить", href=f"/quote-control/{q['id']}", variant="primary", size="sm")
                if show_work_button and q.get("needs_review") else
                btn_link("Просмотр", href=f"/quote-control/{q['id']}", variant="ghost", size="sm")
            )
        )

    status_options = [
        ("all", "Все статусы"),
        ("pending_quote_control", "На проверке"),
        ("pending_approval", "Ожидает согласования"),
        ("approved", "Одобрено"),
        ("sent_to_client", "Отправлено клиенту"),
    ]

    filter_form = Form(
        Label("Фильтр по статусу: ", For="status_filter", style="margin-right: 0.5rem;"),
        Select(
            *[Option(label, value=value, selected=(value == (status_filter or "all")))
              for value, label in status_options],
            name="status_filter",
            id="status_filter",
            onchange="this.form.submit()",
            style="padding: 0.375rem 0.75rem; border-radius: 4px; border: 1px solid #d1d5db;"
        ),
        Hidden(name="tab", value="quote-control"),
        method="get",
        action="/dashboard",
        style="margin-bottom: 1rem;"
    )

    return [
        Div(
            H1(icon("check-circle", size=28), " Контроль КП", cls="page-header"),
            P("Рабочая зона контроллера КП"),
            style="margin-bottom: 1rem;"
        ),

        Div(
            Div(
                Div(str(pending_count), cls="stat-value"),
                Div("На проверке"),
                cls="card stat-card",
                style="border-left: 4px solid #f59e0b;" if pending_count > 0 else ""
            ),
            Div(
                Div(str(awaiting_count), cls="stat-value"),
                Div("Ожидает согласования"),
                cls="card stat-card",
                style="border-left: 4px solid #3b82f6;" if awaiting_count > 0 else ""
            ),
            Div(
                Div(str(approved_count), cls="stat-value"),
                Div("Одобрено/Отправлено"),
                cls="card stat-card"
            ),
            Div(
                Div(str(len(quotes_with_details)), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        Div(filter_form, cls="card") if not status_filter or status_filter == "all" else filter_form,

        Div(
            Div(
                Div(
                    H3(f"КП: {dict(status_options).get(status_filter, status_filter)}", style="margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in quotes_with_details]
                        ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="6", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(quotes_with_details)}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if status_filter and status_filter != "all" else None,

        Div(
            Div(
                Div(
                    H3(icon("file-text", size=20), " Ожидают проверки", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    Span("КП требующие проверки контроллера", style="color: #666; font-size: 0.875rem; font-weight: normal;"),
                    cls="table-header", style="flex-direction: column; align-items: flex-start; gap: 0.25rem;"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q) for q in pending_quotes]
                        ) if pending_quotes else Tbody(Tr(Td("Нет КП на проверке", colspan="6", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {pending_count}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if not status_filter or status_filter == "all" else None,

        Div(
            Div(
                Div(
                    H3(icon("clock", size=20), " Ожидают согласования", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    Span("КП отправленные на согласование топ-менеджеру", style="color: #666; font-size: 0.875rem; font-weight: normal;"),
                    cls="table-header", style="flex-direction: column; align-items: flex-start; gap: 0.25rem;"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q, show_work_button=False) for q in awaiting_approval_quotes]
                        ) if awaiting_approval_quotes else Tbody(Tr(Td("Нет КП на согласовании", colspan="6", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {awaiting_count}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if (not status_filter or status_filter == "all") and awaiting_approval_quotes else None,

        Div(
            Div(
                Div(
                    H3(icon("check-circle", size=20), " Одобренные КП", style="display: flex; align-items: center; gap: 0.5rem; margin: 0;"),
                    cls="table-header"
                ),
                Div(
                    Table(
                        Thead(Tr(Th("КП #"), Th("КЛИЕНТ"), Th("СТАТУС"), Th("СУММА", cls="col-money"), Th("СОЗДАН"), Th("", cls="col-actions"))),
                        Tbody(
                            *[quote_row(q, show_work_button=False) for q in approved_quotes]
                        ) if approved_quotes else Tbody(Tr(Td("Нет одобренных КП", colspan="6", style="text-align: center; color: #666;"))),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {approved_count}"),
                    cls="table-footer"
                ),
                cls="table-container", style="margin: 0;"
            )
        ) if (not status_filter or status_filter == "all") and approved_quotes else None,
    ]


def _dashboard_spec_control_content(user_id: str, org_id: str, supabase, status_filter: str = None, q: str = None, partial: bool = False) -> list:
    """
    Spec Control workspace tab content.
    Unified table with search, filter chips, status badges, and group separators.
    When partial=True, returns only table rows for HTMX partial updates.
    """
    # Get quotes awaiting specification creation
    quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, currency, created_at, deal_type, current_version_id") \
        .eq("organization_id", org_id) \
        .eq("workflow_status", "pending_spec_control") \
        .is_("deleted_at", None) \
        .order("created_at", desc=True) \
        .execute()

    pending_quotes = quotes_result.data or []

    # Get all specifications
    specs_result = supabase.table("specifications") \
        .select("id, quote_id, specification_number, proposal_idn, status, sign_date, specification_currency, created_at, updated_at, quotes(idn_quote, total_amount_usd, total_profit_usd, customers(name))") \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .order("created_at", desc=True) \
        .execute()

    all_specs = specs_result.data or []

    # Filter out pending quotes that already have a specification (prevent duplicates)
    spec_quote_ids = {s.get("quote_id") for s in all_specs if s.get("quote_id")}
    pending_quotes = [q for q in pending_quotes if q["id"] not in spec_quote_ids]

    # Status badge mapping (unified for all item types)
    # Badge colors: pending=orange, draft=gray, pending_review=blue, approved/signed=green
    def spec_status_badge(status):
        status_map = {
            "pending_spec_control": ("Ожидает", "bg-orange-200 text-orange-800"),
            "draft": ("Черновик", "bg-gray-200 text-gray-800"),
            "pending_review": ("На проверке", "bg-blue-200 text-blue-800"),
            "approved": ("Утверждена", "bg-green-200 text-green-800"),
            "signed": ("Подписана", "bg-green-200 text-green-800"),
        }
        label, classes = status_map.get(status, (status, "bg-gray-200 text-gray-800"))
        return Span(label, cls=f"px-2 py-1 rounded text-sm {classes}")

    # Count specs by status
    draft_specs = [s for s in all_specs if s.get("status") == "draft"]
    review_specs = [s for s in all_specs if s.get("status") == "pending_review"]
    approved_specs = [s for s in all_specs if s.get("status") == "approved"]
    signed_specs = [s for s in all_specs if s.get("status") == "signed"]

    # Calculate financial totals across all specs
    specs_total_amount = sum(
        float((s.get("quotes") or {}).get("total_amount_usd") or 0)
        for s in all_specs
    )
    specs_total_profit = sum(
        float((s.get("quotes") or {}).get("total_profit_usd") or 0)
        for s in all_specs
    )

    stats = {
        "pending_quotes": len(pending_quotes),
        "draft_specs": len(draft_specs),
        "pending_review": len(review_specs),
        "approved": len(approved_specs),
        "signed": len(signed_specs),
        "total_specs": len(all_specs),
    }

    # --- Build combined_items list merging pending quotes and specs ---
    status_order = {
        "pending_spec_control": 0,
        "draft": 1,
        "pending_review": 2,
        "approved": 3,
        "signed": 4,
    }

    combined_items = []

    # Add pending quotes with type marker
    for pq in pending_quotes:
        customer_name = (pq.get("customers") or {}).get("name", "Unknown")
        combined_items.append({
            "type": "quote",
            "id": pq.get("id"),
            "number": pq.get("idn_quote", "-"),
            "customer_name": customer_name,
            "status": "pending_spec_control",
            "currency": pq.get("currency", "RUB"),
            "amount": float(pq.get("total_amount") or 0),
            "profit": None,
            "created_at": pq.get("created_at", ""),
            "quote_id": pq.get("id"),
            "spec_id": None,
        })

    # Add specs with type marker
    for spec in all_specs:
        quote = spec.get("quotes", {}) or {}
        customer = quote.get("customers", {}) or {}
        combined_items.append({
            "type": "spec",
            "id": spec.get("id"),
            "number": spec.get("specification_number") or quote.get("idn_quote", "-"),
            "customer_name": customer.get("name", "Unknown"),
            "status": spec.get("status", "draft"),
            "currency": spec.get("specification_currency", "-"),
            "amount": float(quote.get("total_amount_usd") or 0),
            "profit": float(quote.get("total_profit_usd") or 0),
            "created_at": spec.get("created_at", ""),
            "quote_id": spec.get("quote_id"),
            "spec_id": spec.get("id"),
        })

    # Sort by status priority, then by date desc
    def _safe_ts(val):
        if not val:
            return 0
        try:
            return datetime.fromisoformat(val).timestamp()
        except (ValueError, TypeError):
            return 0
    combined_items = sorted(combined_items, key=lambda x: (status_order.get(x["status"], 99), -_safe_ts(x["created_at"])))

    # Apply status filter
    if status_filter and status_filter != "all":
        if status_filter == "pending_quotes":
            combined_items = [item for item in combined_items if item["type"] == "quote"]
        else:
            combined_items = [item for item in combined_items if item["status"] == status_filter]

    # Apply search filter (q parameter)
    if q and q.strip():
        search_term = q.lower().strip()
        combined_items = [
            item for item in combined_items
            if search_term in (item.get("number") or "").lower()
            or search_term in (item.get("customer_name") or "").lower()
        ]

    # --- Build unified table rows with group separators ---
    def build_unified_row(item, row_num):
        """Unified row builder for both pending quotes and specifications."""
        number_cell = A(item["number"], href=f"/quotes/{item['quote_id']}") if item["type"] == "quote" else (item["number"] or "-")
        amount_display = f"${item['amount']:,.0f}" if item["amount"] is not None else "-"
        profit_display = f"${item['profit']:,.0f}" if item.get("profit") is not None else "-"
        date_display = item["created_at"][:10] if item.get("created_at") else "-"

        # Unified action column based on type/status
        if item["type"] == "quote":
            action = btn_link("Создать спецификацию", href=f"/spec-control/create/{item['quote_id']}", variant="success", size="sm")
        elif item["status"] in ["draft", "pending_review"]:
            action = btn_link("Редактировать", href=f"/spec-control/{item['spec_id']}", variant="primary", size="sm")
        else:
            action = btn_link("Просмотр", href=f"/spec-control/{item['spec_id']}", variant="ghost", size="sm")

        return Tr(
            Td(str(row_num)),
            Td(number_cell),
            Td(item["customer_name"]),
            Td(spec_status_badge(item["status"])),
            Td(item["currency"]),
            Td(amount_display),
            Td(profit_display),
            Td(date_display),
            Td(action),
        )

    # Group separator labels
    group_labels = {
        "pending_spec_control": "Ожидают спецификации",
        "draft": "Черновики",
        "pending_review": "На проверке",
        "approved": "Утверждены",
        "signed": "Подписаны",
    }

    table_rows = []
    current_status_group = None
    row_num = 0

    for item in combined_items:
        if item["status"] != current_status_group:
            current_status_group = item["status"]
            group_label = group_labels.get(current_status_group, current_status_group)
            table_rows.append(
                Tr(
                    Td(Div(group_label, cls="group-separator-label",
                       style="font-weight: 600; text-align: center; color: #475569;"), colspan="9",
                       style="background: #f1f5f9; padding: 0.5rem;"),
                    cls="group-separator"
                )
            )
        row_num += 1
        table_rows.append(build_unified_row(item, row_num))

    # Empty state for unified table
    if not table_rows:
        table_rows.append(
            Tr(Td("Ничего не найдено", colspan="9", style="text-align: center; color: #666; padding: 2rem;"))
        )

    # For HTMX partial requests (HX-Request header), return table rows only
    # Note: Can't mix Span OOB with Tr elements — HTMX wraps response in <table><tbody>
    # for parsing, and non-table elements get stripped by browser HTML parser.
    # Counter update is done client-side via htmx:afterSwap event.
    if partial:
        return tuple(table_rows)

    # Filter URL base; chips and cards append status=all or status=... for filtering
    filter_base_url = "/dashboard?tab=spec-control"

    return [
        H1(icon("files", size=28), " Контроль спецификаций", cls="page-header"),

        # Clickable status cards with hx_get
        Div(
            Div(
                Div(str(stats["pending_quotes"]), cls="stat-value", style="color: #f59e0b;"),
                Div("Ожидают спецификации", style="font-size: 0.875rem;"),
                cls="stat-card",
                style=("border-left: 4px solid #f59e0b; cursor: pointer;" if stats["pending_quotes"] > 0 else "cursor: pointer;"),
                hx_get=f"{filter_base_url}&status_filter=pending_quotes",
                hx_target="#spec-table-body",
                hx_swap="innerHTML",
            ),
            Div(
                Div(str(stats["pending_review"]), cls="stat-value", style="color: #3b82f6;"),
                Div("На проверке", style="font-size: 0.875rem;"),
                cls="stat-card",
                style="cursor: pointer;",
                hx_get=f"{filter_base_url}&status_filter=pending_review",
                hx_target="#spec-table-body",
                hx_swap="innerHTML",
            ),
            Div(
                Div(str(stats["approved"]), cls="stat-value", style="color: #22c55e;"),
                Div("Утверждены", style="font-size: 0.875rem;"),
                cls="stat-card",
                style="cursor: pointer;",
                hx_get=f"{filter_base_url}&status_filter=approved",
                hx_target="#spec-table-body",
                hx_swap="innerHTML",
            ),
            Div(
                Div(str(stats["signed"]), cls="stat-value", style="color: #10b981;"),
                Div("Подписаны", style="font-size: 0.875rem;"),
                cls="stat-card",
                style="cursor: pointer;",
                hx_get=f"{filter_base_url}&status_filter=signed",
                hx_target="#spec-table-body",
                hx_swap="innerHTML",
            ),
            cls="grid",
            style="grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;"
        ),

        # Itogo summary
        Div(
            Span(f"Итого: ${specs_total_amount:,.0f} | Профит: ${specs_total_profit:,.0f}",
                 style="font-size: 1rem; font-weight: 600;"),
            style="margin-bottom: 1.5rem; padding: 0.75rem 1rem; background: #f8fafc; border-radius: 0.5rem;"
        ),

        # Search input + status chip buttons
        Div(
            Input(
                type="text",
                name="q",
                placeholder="Поиск по номеру или клиенту...",
                cls="border rounded px-3 py-1.5 w-64",
                hx_get=f"{filter_base_url}",
                hx_trigger="input delay:300ms",
                hx_target="#spec-table-body",
                hx_swap="innerHTML",
            ),
            A(f"Все ({stats['pending_quotes'] + stats['total_specs']})",
              cls="px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-700",
              hx_get=f"{filter_base_url}&status_filter=all",
              hx_target="#spec-table-body",
              hx_swap="innerHTML",
              style="cursor: pointer; text-decoration: none; margin-left: 0.5rem;"),
            A(f"Ожидают ({stats['pending_quotes']})",
              cls="px-3 py-1 rounded-full text-sm bg-orange-100 text-orange-700",
              hx_get=f"{filter_base_url}&status_filter=pending_quotes",
              hx_target="#spec-table-body",
              hx_swap="innerHTML",
              style="cursor: pointer; text-decoration: none; margin-left: 0.25rem;"),
            A(f"Черновики ({stats['draft_specs']})",
              cls="px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-700",
              hx_get=f"{filter_base_url}&status_filter=draft",
              hx_target="#spec-table-body",
              hx_swap="innerHTML",
              style="cursor: pointer; text-decoration: none; margin-left: 0.25rem;"),
            A(f"Проверка ({stats['pending_review']})",
              cls="px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-700",
              hx_get=f"{filter_base_url}&status_filter=pending_review",
              hx_target="#spec-table-body",
              hx_swap="innerHTML",
              style="cursor: pointer; text-decoration: none; margin-left: 0.25rem;"),
            A(f"Подписаны ({stats['signed']})",
              cls="px-3 py-1 rounded-full text-sm bg-green-100 text-green-700",
              hx_get=f"{filter_base_url}&status_filter=signed",
              hx_target="#spec-table-body",
              hx_swap="innerHTML",
              style="cursor: pointer; text-decoration: none; margin-left: 0.25rem;"),
            cls="flex items-center gap-2",
            style="margin-bottom: 1.5rem; flex-wrap: wrap;"
        ),

        # Unified table
        Div(
            Div(
                Div(
                    Table(
                        Thead(Tr(
                            Th("#"),
                            Th("НОМЕР"),
                            Th("КЛИЕНТ"),
                            Th("СТАТУС"),
                            Th("ВАЛЮТА"),
                            Th("СУММА"),
                            Th("ПРОФИТ"),
                            Th("ДАТА"),
                            Th("", cls="col-actions"),
                        )),
                        Tbody(
                            *table_rows,
                            id="spec-table-body",
                        ),
                    cls="unified-table"),
                    cls="table-responsive"
                ),
                Div(
                    Span(f"Записей: {len(combined_items)}", id="spec-record-count"),
                    cls="table-footer"
                ),
                # Client-side counter update after HTMX swaps table rows
                Script("""
                    document.body.addEventListener('htmx:afterSwap', function(evt) {
                        if (evt.detail.target.id === 'spec-table-body') {
                            var rows = evt.detail.target.querySelectorAll('tr');
                            var count = 0;
                            rows.forEach(function(r) { if (r.querySelector('td[colspan]') === null) count++; });
                            var el = document.getElementById('spec-record-count');
                            if (el) el.textContent = 'Записей: ' + count;
                        }
                    });
                """),
                cls="table-container", style="margin: 0; margin-bottom: 2rem;"
            )
        ),
    ]


def _dashboard_finance_content(user_id: str, org_id: str, supabase) -> list:
    """
    Finance workspace tab content.
    Redirects to the existing /finance page which already has tabs.
    """
    # For finance, we show a simple redirect message or embed the finance content
    # For now, return a link to the full finance page
    return [
        H1(icon("wallet", size=28), " Финансы", cls="page-header"),
        P("Финансовый раздел имеет собственные табы для детальной работы."),
        Div(
            btn_link("Открыть полный раздел Финансы →", href="/finance", variant="primary", icon_name="arrow-right", icon_right=True),
            style="margin-top: 1rem;"
        ),
    ]


def _calculate_days_remaining(deadline_date) -> str:
    """
    Calculate days remaining until deadline.
    Returns formatted string like 'осталось 5 дн.' or 'просрочено на 3 дн.'
    """
    if not deadline_date:
        return "—"

    try:
        if isinstance(deadline_date, str):
            deadline = datetime.strptime(deadline_date[:10], "%Y-%m-%d").date()
        else:
            deadline = deadline_date

        today = date.today()
        delta = (deadline - today).days

        if delta > 0:
            return f"осталось {delta} дн."
        elif delta == 0:
            return "сегодня"
        else:
            return f"просрочено на {abs(delta)} дн."
    except (ValueError, TypeError):
        return "—"


def _format_deadline_display(deadline_date) -> str:
    """
    Format deadline date with days remaining.
    Returns formatted string like '22.06.2026 (осталось 90 дн.)'
    """
    if not deadline_date:
        return "—"

    try:
        if isinstance(deadline_date, str):
            deadline = datetime.strptime(deadline_date[:10], "%Y-%m-%d").date()
        else:
            deadline = deadline_date

        formatted_date = deadline.strftime("%d.%m.%Y")
        days_remaining = _calculate_days_remaining(deadline_date)

        return f"{formatted_date} ({days_remaining})"
    except (ValueError, TypeError):
        return "—"


def _dashboard_sales_content(user_id: str, org_id: str, user: dict, supabase) -> list:
    """
    Sales Manager Dashboard tab content.
    Shows personal statistics, active specifications, active quotes, and profile card.
    """
    from services.user_profile_service import get_user_profile, get_user_statistics

    # Get user profile and statistics
    profile = get_user_profile(user_id, org_id)
    stats = get_user_statistics(user_id, org_id)

    # Get organization name
    org_result = supabase.table("organizations").select("name").eq("id", org_id).execute()
    org_name = org_result.data[0].get("name", "—") if org_result.data else "—"

    # Get current month sales (deals) and profit
    now = datetime.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Query deals closed this month by this user
    month_deals_result = supabase.table("quotes") \
        .select("id, total_amount_usd, total_profit_usd") \
        .eq("organization_id", org_id) \
        .eq("created_by", user_id) \
        .eq("workflow_status", "deal") \
        .is_("deleted_at", None) \
        .gte("updated_at", first_day_of_month.isoformat()) \
        .execute()

    month_deals = month_deals_result.data or []
    month_sales = sum(float(d.get("total_amount_usd") or 0) for d in month_deals)
    month_profit = sum(float(d.get("total_profit_usd") or 0) for d in month_deals)

    # Get active specifications (status != 'signed') for this user
    active_specs_result = supabase.table("specifications") \
        .select("""
            id,
            specification_number,
            status,
            actual_delivery_date,
            created_at,
            quotes(
                id,
                idn_quote,
                total_amount_usd,
                total_profit_usd,
                customers(name)
            )
        """) \
        .eq("organization_id", org_id) \
        .eq("created_by", user_id) \
        .neq("status", "signed") \
        .is_("deleted_at", None) \
        .order("created_at", desc=True) \
        .limit(10) \
        .execute()

    active_specs = active_specs_result.data or []

    # Calculate totals for active specs
    specs_total_amount = sum(
        float((s.get("quotes") or {}).get("total_amount_usd") or 0)
        for s in active_specs
    )
    specs_total_profit = sum(
        float((s.get("quotes") or {}).get("total_profit_usd") or 0)
        for s in active_specs
    )

    # Get active quotes (not deal/rejected/cancelled) for this user
    active_quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, workflow_status, total_amount_usd, total_profit_usd, customers(name)") \
        .eq("organization_id", org_id) \
        .eq("created_by", user_id) \
        .not_.in_("workflow_status", ["deal", "rejected", "cancelled"]) \
        .is_("deleted_at", None) \
        .order("created_at", desc=True) \
        .limit(10) \
        .execute()

    active_quotes = active_quotes_result.data or []

    # Spec status badge helper
    def spec_status_badge(status):
        status_map = {
            "draft": ("Черновик", "#6b7280", "#f3f4f6"),
            "pending_review": ("На проверке", "#d97706", "#fef3c7"),
            "approved": ("Одобрена", "#059669", "#d1fae5"),
            "signed": ("Подписана", "#2563eb", "#dbeafe"),
        }
        label, color, bg = status_map.get(status, (status or "—", "#6b7280", "#f3f4f6"))
        return Span(label, style=f"display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; background: {bg}; color: {color}; font-weight: 500;")

    # Build spec rows
    def build_spec_row(spec):
        quote = spec.get("quotes") or {}
        customer = quote.get("customers") or {}
        spec_number = spec.get("specification_number") or "—"
        customer_name = customer.get("name") or "—"
        status = spec.get("status") or "draft"
        amount = float(quote.get("total_amount_usd") or 0)
        profit = float(quote.get("total_profit_usd") or 0)
        deadline = spec.get("actual_delivery_date")

        return Tr(
            Td(spec_number, style="font-weight: 500;"),
            Td(customer_name[:25] + "..." if len(customer_name) > 25 else customer_name),
            Td(spec_status_badge(status)),
            Td(f"${amount:,.0f}", style="text-align: right;"),
            Td(f"${profit:,.0f}", style="text-align: right; color: #059669;"),
            Td(_format_deadline_display(deadline), style="font-size: 0.875rem;"),
            cls="clickable-row",
            style="cursor: pointer;",
            onclick=f"window.location='/specifications/{spec['id']}'"
        )

    # Build quote rows
    def build_quote_row(quote):
        customer = quote.get("customers") or {}
        idn = quote.get("idn_quote") or "—"
        customer_name = customer.get("name") or "—"
        status = quote.get("workflow_status") or "draft"
        amount = float(quote.get("total_amount_usd") or 0)
        profit = float(quote.get("total_profit_usd") or 0)

        return Tr(
            Td(idn, style="font-weight: 500;"),
            Td(customer_name[:25] + "..." if len(customer_name) > 25 else customer_name),
            Td(workflow_status_badge(status)),
            Td(f"${amount:,.0f}", style="text-align: right;"),
            Td(f"${profit:,.0f}", style="text-align: right; color: #059669;"),
            cls="clickable-row",
            style="cursor: pointer;",
            onclick=f"window.location='/quotes/{quote['id']}'"
        )

    return [
        # Statistics cards row
        Div(
            Div(
                Div(str(stats.get("total_customers", 0)), cls="stat-value", style="font-size: 1.75rem; font-weight: 700; color: #1f2937;"),
                Div("Клиенты", style="font-size: 0.875rem; color: #6b7280;"),
                cls="card stat-card", style="text-align: center; padding: 1rem;"
            ),
            Div(
                Div(str(stats.get("total_quotes", 0)), cls="stat-value", style="font-size: 1.75rem; font-weight: 700; color: #1f2937;"),
                Div("Ваши КП", style="font-size: 0.875rem; color: #6b7280;"),
                cls="card stat-card", style="text-align: center; padding: 1rem;"
            ),
            Div(
                Div(str(stats.get("total_specifications", 0)), cls="stat-value", style="font-size: 1.75rem; font-weight: 700; color: #1f2937;"),
                Div("Ваши СП", style="font-size: 0.875rem; color: #6b7280;"),
                cls="card stat-card", style="text-align: center; padding: 1rem;"
            ),
            Div(
                Div(f"${month_sales:,.0f}", cls="stat-value", style="font-size: 1.75rem; font-weight: 700; color: #059669;"),
                Div("Продажи (месяц)", style="font-size: 0.875rem; color: #6b7280;"),
                cls="card stat-card", style="text-align: center; padding: 1rem;"
            ),
            Div(
                Div(f"${month_profit:,.0f}", cls="stat-value", style="font-size: 1.75rem; font-weight: 700; color: #10b981;"),
                Div("Профит (месяц)", style="font-size: 0.875rem; color: #6b7280;"),
                cls="card stat-card", style="text-align: center; padding: 1rem;"
            ),
            cls="grid",
            style="grid-template-columns: repeat(5, 1fr); gap: 1rem; margin-bottom: 1.5rem;"
        ),

        # Main content: two columns (tables + profile card)
        Div(
            # Left column: Tables
            Div(
                # Active Specifications section
                Div(
                    Div(
                        H3("Активные спецификации", style="margin: 0; display: inline;"),
                        Span(f"Итого: ${specs_total_amount:,.0f} | Профит: ${specs_total_profit:,.0f}",
                             style="float: right; color: #6b7280; font-size: 0.875rem; font-weight: normal;"),
                        style="margin-bottom: 1rem;"
                    ),
                    Div(
                        Table(
                            Thead(Tr(
                                Th("ИНД"),
                                Th("Клиент"),
                                Th("Статус"),
                                Th("Сумма", style="text-align: right;"),
                                Th("Профит", style="text-align: right;"),
                                Th("Дедлайн"),
                            )),
                            Tbody(
                                *[build_spec_row(s) for s in active_specs]
                            ) if active_specs else Tbody(
                                Tr(Td("Нет активных спецификаций", colspan="6", style="text-align: center; color: #9ca3af; padding: 2rem;"))
                            ),
                            cls="table-enhanced", style="width: 100%;"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("→ изменить", href="/spec-control", style="display: block; margin-top: 0.75rem; color: #3b82f6; font-size: 0.875rem;"),
                    cls="card",
                    style="margin-bottom: 1.5rem;"
                ),

                # Active Quotes section
                Div(
                    H3("Активные КП", style="margin-bottom: 1rem;"),
                    Div(
                        Table(
                            Thead(Tr(
                                Th("ИНД"),
                                Th("Клиент"),
                                Th("Статус"),
                                Th("Сумма USD", style="text-align: right;"),
                                Th("Профит USD", style="text-align: right;"),
                            )),
                            Tbody(
                                *[build_quote_row(q) for q in active_quotes]
                            ) if active_quotes else Tbody(
                                Tr(Td("Нет активных КП", colspan="5", style="text-align: center; color: #9ca3af; padding: 2rem;"))
                            ),
                            cls="table-enhanced", style="width: 100%;"
                        ),
                        cls="table-enhanced-container"
                    ),
                    A("→ изменить", href="/quotes", style="display: block; margin-top: 0.75rem; color: #3b82f6; font-size: 0.875rem;"),
                    cls="card",
                ),
                style="flex: 1;"
            ),

            # Right column: Profile card
            Div(
                Div(
                    # Avatar placeholder
                    Div(
                        Span(icon("user", size=48), style="color: #9ca3af;"),
                        style="width: 80px; height: 80px; background: #f3f4f6; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem auto;"
                    ),
                    # Name
                    H3(
                        profile.get("full_name") or user.get("email", "—"),
                        style="text-align: center; margin: 0 0 0.25rem 0; font-size: 1.125rem;"
                    ),
                    # Position
                    P(
                        profile.get("position") or "Менеджер по продажам",
                        style="text-align: center; color: #6b7280; margin: 0 0 0.75rem 0; font-size: 0.875rem;"
                    ),
                    # Phone
                    P(
                        Span(icon("phone", size=14), style="margin-right: 0.375rem;"),
                        profile.get("phone") or "—",
                        style="text-align: center; color: #374151; margin: 0 0 0.5rem 0; font-size: 0.875rem; display: flex; align-items: center; justify-content: center;"
                    ) if profile and profile.get("phone") else None,
                    # Organization
                    P(
                        Span(icon("building-2", size=14), style="margin-right: 0.375rem;"),
                        org_name,
                        style="text-align: center; color: #374151; margin: 0; font-size: 0.875rem; display: flex; align-items: center; justify-content: center;"
                    ),
                    cls="card",
                    style="padding: 1.5rem; text-align: center;"
                ),
                style="width: 260px; flex-shrink: 0;"
            ),

            style="display: flex; gap: 1.5rem; align-items: flex-start;"
        ),
    ]


def _build_dashboard_tabs_nav(tabs: list, active_tab: str) -> Div:
    """
    Build the dashboard tab navigation with design system styling.
    """
    # Tab styles following design system
    tab_base_style = """
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
    """

    tab_inactive_style = f"{tab_base_style} color: #64748b; background: transparent;"
    tab_active_style = f"""
        {tab_base_style}
        color: #1e293b;
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-color: #e2e8f0;
        font-weight: 600;
        box-shadow: 0 -2px 8px rgba(0,0,0,0.04);
    """

    tab_links = []
    for tab in tabs:
        is_active = tab["id"] == active_tab
        tab_links.append(
            A(
                icon(tab.get("icon", "circle"), size=16, color="#3b82f6" if is_active else "#94a3b8"),
                Span(tab["label"]),
                href=f"/dashboard?tab={tab['id']}",
                style=tab_active_style if is_active else tab_inactive_style
            )
        )

    container_style = """
        display: flex;
        gap: 4px;
        padding: 0 4px;
        margin-bottom: 20px;
        border-bottom: 1px solid #e2e8f0;
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        padding: 12px 16px 0 16px;
        border-radius: 12px 12px 0 0;
    """

    return Div(
        *tab_links,
        role="tablist",
        style=container_style
    )


# ============================================================================
# TASKS - Unified Task Inbox (Hub)
# ============================================================================

def _count_user_tasks(user_id: str, org_id: str, roles: list, supabase) -> int:
    """Count total pending tasks for user across all roles."""
    total = 0

    # Approvals for top_manager/admin
    if 'top_manager' in roles or 'admin' in roles:
        total += count_pending_approvals(user_id)

    # Procurement tasks
    if 'procurement' in roles:
        result = supabase.table("quotes").select("id", count="exact") \
            .eq("organization_id", org_id).eq("workflow_status", "pending_procurement") \
            .is_("deleted_at", None).execute()
        total += result.count or 0

    # Logistics tasks (pending_logistics + pending_logistics_and_customs)
    if 'logistics' in roles:
        result = supabase.table("quotes").select("id", count="exact") \
            .eq("organization_id", org_id).in_("workflow_status", ["pending_logistics", "pending_logistics_and_customs"]) \
            .is_("deleted_at", None).execute()
        total += result.count or 0

    # Customs tasks (pending_customs + pending_logistics_and_customs)
    if 'customs' in roles:
        result = supabase.table("quotes").select("id", count="exact") \
            .eq("organization_id", org_id).in_("workflow_status", ["pending_customs", "pending_logistics_and_customs"]) \
            .is_("deleted_at", None).execute()
        total += result.count or 0

    # Quote controller tasks
    if 'quote_controller' in roles or 'admin' in roles:
        result = supabase.table("quotes").select("id", count="exact") \
            .eq("organization_id", org_id).eq("workflow_status", "pending_quote_control") \
            .is_("deleted_at", None).execute()
        total += result.count or 0

    # Spec controller tasks
    if 'spec_controller' in roles or 'admin' in roles:
        spec_counts = count_specifications_by_status(org_id)
        total += spec_counts.get('pending_review', 0) + spec_counts.get('draft', 0)
        result = supabase.table("quotes").select("id", count="exact") \
            .eq("organization_id", org_id).eq("workflow_status", "pending_spec_control") \
            .is_("deleted_at", None).execute()
        total += result.count or 0

    # Finance tasks
    if 'finance' in roles or 'admin' in roles:
        deal_counts = count_deals_by_status(org_id)
        total += deal_counts.get('active', 0)

    # Sales tasks
    if 'sales' in roles:
        result = supabase.table("quotes").select("id", count="exact") \
            .eq("organization_id", org_id).eq("workflow_status", "pending_sales_review").is_("deleted_at", None).execute()
        total += result.count or 0

    return total


# @rt("/tasks")  # decorator removed; file is archived and not mounted
def get(session):
    """
    Unified Task Inbox - shows all pending tasks for the user.
    This is the main entry point instead of dashboard tabs.

    Design System V2: Matches calculate page patterns with gradient cards,
    section headers with icons, and refined spacing.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user.get("id")
    org_id = user.get("org_id")
    supabase = get_supabase()

    # Get user roles (respects admin impersonation)
    roles = get_effective_roles(session)

    # Count total tasks
    total_tasks = _count_user_tasks(user_id, org_id, roles, supabase)

    # Get task sections for all roles
    task_sections = _get_role_tasks_sections(user_id, org_id, roles, supabase)

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    page_title_style = """
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0;
        font-size: 22px;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: -0.02em;
    """

    task_count_badge_style = f"""
        display: inline-flex;
        align-items: center;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 13px;
        font-weight: 600;
        background: {'linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)' if total_tasks > 0 else 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)'};
        color: {'#dc2626' if total_tasks > 0 else '#059669'};
        border: 1px solid {'#fecaca' if total_tasks > 0 else '#a7f3d0'};
    """

    roles_label_style = """
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        font-weight: 600;
        margin-right: 10px;
    """

    # Role badges with refined styling
    role_names = {
        'sales': ('Продажи', '#f97316'),
        'sales_manager': ('Менеджер продаж', '#ea580c'),
        'procurement': ('Закупки', '#eab308'),
        'logistics': ('Логистика', '#3b82f6'),
        'customs': ('Таможня', '#8b5cf6'),
        'quote_controller': ('Контроль КП', '#ec4899'),
        'spec_controller': ('Контроль спецификаций', '#6366f1'),
        'finance': ('Финансы', '#10b981'),
        'top_manager': ('Топ-менеджер', '#f59e0b'),
        'head_of_sales': ('Начальник отдела продаж', '#d97706'),
        'head_of_procurement': ('Начальник отдела закупок', '#ca8a04'),
        'head_of_logistics': ('Начальник отдела логистики', '#2563eb'),
        'admin': ('Админ', '#ef4444'),
    }

    role_badges = [
        Span(role_names.get(r, (r, '#6b7280'))[0],
             style=f"""
                display: inline-block;
                padding: 5px 12px;
                border-radius: 8px;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                font-weight: 600;
                margin-right: 8px;
                margin-bottom: 4px;
                background: {role_names.get(r, (r, '#6b7280'))[1]}12;
                color: {role_names.get(r, (r, '#6b7280'))[1]};
                border: 1px solid {role_names.get(r, (r, '#6b7280'))[1]}25;
             """)
        for r in roles
    ] if roles else [Span("Нет ролей", style="color: #9ca3af; font-size: 13px;")]

    # Empty state card style
    empty_state_style = """
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border-radius: 12px;
        border: 1px solid #a7f3d0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        text-align: center;
        padding: 40px 32px;
    """

    # Build content
    content = [
        # Header card with gradient background
        Div(
            Div(
                # Title row with icon and count
                Div(
                    icon("inbox", size=26, style="color: #3b82f6;"),
                    H1("Мои задачи", style=page_title_style),
                    Span(
                        f"{total_tasks} " + ("задач" if total_tasks == 0 or total_tasks >= 5 else "задачи" if total_tasks >= 2 else "задача"),
                        style=task_count_badge_style
                    ),
                    style="display: flex; align-items: center; gap: 14px;"
                ),
                # Roles row
                Div(
                    Span("Роли:", style=roles_label_style),
                    *role_badges,
                    style="display: flex; align-items: center; flex-wrap: wrap; margin-top: 12px;"
                ),
            ),
            style=header_card_style
        ),
    ]

    # Add task sections or empty state
    if task_sections:
        content.extend(task_sections)
    else:
        content.append(
            Div(
                icon("check-circle", size=48, style="color: #22c55e; margin-bottom: 16px;"),
                H3("Отлично! Нет задач.", style="margin: 0 0 10px 0; font-size: 18px; font-weight: 600; color: #059669;"),
                P("Все задачи выполнены. Новые задачи появятся здесь автоматически.", style="margin: 0; color: #64748b; font-size: 14px; line-height: 1.5;"),
                style=empty_state_style
            )
        )

    return page_layout("Мои задачи",
        *content,
        session=session,
        current_path="/tasks"
    )


# @rt("/dashboard")  # decorator removed; file is archived and not mounted
def get(session, request, tab: str = None, status_filter: str = None, q: str = None, date_from: str = None, date_to: str = None):
    """
    Unified Dashboard with role-based tabs.

    - Admin/top_manager see all tabs including overview
    - Sales managers see overview with personal summary blocks
    - Single-role users see their workspace directly without tabs
    - Multi-role users see relevant tabs
    - HTMX requests for spec-control/overview return partial HTML
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user.get("id")
    org_id = user.get("org_id")
    supabase = get_supabase()

    # Get user roles (respects admin impersonation)
    roles = get_effective_roles(session)

    # HTMX partial responses
    is_htmx = request.headers.get("hx-request") == "true"
    if is_htmx and tab == "spec-control":
        return _dashboard_spec_control_content(user_id, org_id, supabase, status_filter, q, partial=True)
    if is_htmx and tab == "overview":
        return _dashboard_overview_content(user_id, org_id, roles, user, supabase, date_from, date_to)

    # Get visible tabs for this user
    visible_tabs = get_dashboard_tabs(roles)
    show_tabs = should_show_dashboard_tabs(roles)

    # Determine active tab
    if not tab:
        tab = get_default_dashboard_tab(roles)

    # Validate that user has access to requested tab
    valid_tab_ids = [t["id"] for t in visible_tabs]
    if tab not in valid_tab_ids:
        # Fallback to default if invalid tab
        tab = get_default_dashboard_tab(roles)

    # Get tab title for page
    tab_titles = {
        "overview": "Обзор",
        "procurement": "Закупки",
        "logistics": "Логистика",
        "customs": "Таможня",
        "quote-control": "Контроль КП",
        "spec-control": "Спецификации",
        "finance": "Финансы",
        "sales": "Продажи",
    }
    page_title = f"Dashboard - {tab_titles.get(tab, tab)}"

    # Build tab content based on active tab
    if tab == "overview":
        content = _dashboard_overview_content(user_id, org_id, roles, user, supabase, date_from, date_to)
    elif tab == "procurement":
        content = _dashboard_procurement_content(user_id, org_id, supabase, status_filter, roles)
    elif tab == "logistics":
        content = _dashboard_logistics_content(user_id, org_id, supabase, status_filter, roles)
    elif tab == "customs":
        content = _dashboard_customs_content(user_id, org_id, supabase, status_filter, roles)
    elif tab == "quote-control":
        content = _dashboard_quote_control_content(user_id, org_id, supabase, status_filter)
    elif tab == "spec-control":
        content = _dashboard_spec_control_content(user_id, org_id, supabase, status_filter, q)
    elif tab == "finance":
        content = _dashboard_finance_content(user_id, org_id, supabase)
    elif tab == "sales":
        content = _dashboard_sales_content(user_id, org_id, user, supabase)
    else:
        content = _dashboard_overview_content(user_id, org_id, roles, user, supabase, date_from, date_to)

    # Build page with or without tabs
    if show_tabs:
        return page_layout(page_title,
            _build_dashboard_tabs_nav(visible_tabs, tab),
            Div(*content, id="tab-content"),
            session=session,
            current_path="/dashboard"
        )
    else:
        # Single workspace user - show content directly without tabs
        return page_layout(page_title,
            *content,
            session=session,
            current_path="/dashboard"
        )
