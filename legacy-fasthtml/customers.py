"""FastHTML /customers area — archived 2026-04-20 during Phase 6C-2B-1.

Replaced by Next.js at https://app.kvotaflow.ru/customers (and children).
Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy /customers/* back to this Python container.

Contents:
  - GET    /customers                                                   — registry list
  - GET    /customers/{customer_id}                                     — detail view with tabs (general, addresses, contacts, contracts, quotes, specifications, requested_items, additional, calls, meetings)
  - PUT    /customers/{customer_id}/manager                             — assign manager
  - GET    /customers/{customer_id}/calls/new-form                      — HTMX call form
  - POST   /customers/{customer_id}/calls                               — create call
  - GET    /customers/{customer_id}/calls/{call_id}/edit-form           — HTMX edit form
  - POST   /customers/{customer_id}/calls/{call_id}/edit                — update call
  - DELETE /customers/{customer_id}/calls/{call_id}                     — delete call
  - GET    /customers/{customer_id}/edit-field/{field_name}             — inline edit trigger
  - POST   /customers/{customer_id}/update-field/{field_name}           — inline edit save
  - GET    /customers/{customer_id}/cancel-edit/{field_name}            — inline edit cancel
  - GET    /customers/{customer_id}/edit-notes                          — notes inline edit
  - POST   /customers/{customer_id}/update-notes                        — notes inline save
  - GET    /customers/{customer_id}/cancel-edit-notes                   — notes inline cancel
  - GET    /customers/{customer_id}/contacts/{contact_id}/edit-field/{field_name}    — contact inline edit
  - POST   /customers/{customer_id}/contacts/{contact_id}/update-field/{field_name}  — contact inline save
  - GET    /customers/{customer_id}/contacts/{contact_id}/cancel-edit/{field_name}   — contact inline cancel
  - POST   /customers/{customer_id}/contacts/{contact_id}/toggle-signatory           — flag toggle
  - POST   /customers/{customer_id}/contacts/{contact_id}/toggle-primary             — flag toggle
  - POST   /customers/{customer_id}/contacts/{contact_id}/toggle-lpr                 — flag toggle
  - GET    /customers/{customer_id}/warehouses/add                       — warehouse add form
  - POST   /customers/{customer_id}/warehouses/add                       — create warehouse
  - GET    /customers/{customer_id}/warehouses/cancel-add                — cancel warehouse add
  - POST   /customers/{customer_id}/warehouses/delete/{index}            — delete warehouse
  - GET    /customers/{customer_id}/contacts/new                         — contact form page
  - POST   /customers/{customer_id}/contacts/new                         — create contact
  - helpers: _stat_card_simple, _render_calls_list, _render_field_display,
    _render_notes_display, _render_contact_field, _render_contact_name_cell,
    _render_contact_flags_cell, _render_contact_row, _render_warehouses_list
  - constants: ORDER_SOURCE_OPTIONS, ORDER_SOURCE_LABELS

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, tab_nav, require_login, user_has_any_role,
get_supabase, btn, btn_link, icon, format_money, Tr, Td, Th, Table,
Thead, Tbody, Div, Span, H1, H3, P, A, Button, Form, Input, Label, Select,
Option, Dialog, Textarea, Pre, etc.), re-apply the @rt decorator, and
regenerate tests if needed. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Button, Dialog, Div, Form, H1, H3, Input, Label, Option, P, Pre,
    Script, Select, Span, Table, Tbody, Td, Textarea, Th, Thead, Tr,
)
from starlette.responses import RedirectResponse


# ============================================================================
# CUSTOMERS MANAGEMENT (UI-007, UI-008) - Feature v3.0
# ============================================================================

# @rt("/customers")  # decorator removed; file is archived and not mounted
def get(session, q: str = "", status: str = ""):
    """
    Customers list page with search, filters, and contacts preview.

    Customers are external companies that buy from us (at quote level).
    Each customer can have multiple contacts (ЛПР - decision makers).
    The is_signatory contact is used for specification PDF generation.

    Query Parameters:
        q: Search query (matches name or INN)
        status: Filter by status ("active", "inactive", or "" for all)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - sales, admin, top_manager, or head_of_sales can view customers
    if not user_has_any_role(session, ["admin", "sales", "top_manager", "head_of_sales"]):
        return page_layout("Access Denied",
            Div(
                H1("⛔ Доступ запрещён"),
                P("У вас нет прав для просмотра справочника клиентов."),
                P("Требуется одна из ролей: admin, sales, top_manager, head_of_sales"),
                btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
                cls="card"
            ),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")
    user_id = user.get("id")

    # Import customer service functions
    from services.customer_service import (
        get_all_customers, search_customers, get_customer_stats
    )

    # Sales-only users see only their own customers; heads/admins see all
    is_sales_only = not user_has_any_role(session, ["admin", "top_manager", "head_of_sales"])
    manager_filter = user_id if is_sales_only else None

    # Get customers based on filters
    try:
        if q and q.strip():
            # Use search if query provided
            is_active_filter = None if status == "" else (status == "active")
            customers = search_customers(
                organization_id=org_id,
                query=q.strip(),
                is_active=is_active_filter,
                manager_id=manager_filter,
                limit=100
            )
        else:
            # Get all with filters
            is_active_filter = None if status == "" else (status == "active")
            customers = get_all_customers(
                organization_id=org_id,
                is_active=is_active_filter,
                manager_id=manager_filter,
                limit=100
            )

        # Get stats for summary (filtered by manager for sales-only users)
        stats = get_customer_stats(organization_id=org_id, manager_id=manager_filter)

    except Exception as e:
        print(f"Error loading customers: {e}")
        customers = []
        stats = {"total": 0, "active": 0, "inactive": 0, "with_contacts": 0, "with_signatory": 0}

    # Status options for filter
    status_options = [
        Option("Все статусы", value="", selected=(status == "")),
        Option("Активные", value="active", selected=(status == "active")),
        Option("Неактивные", value="inactive", selected=(status == "inactive")),
    ]

    # Resolve manager names from profiles
    manager_ids = list(set(c.manager_id for c in customers if c.manager_id))
    manager_names = {}
    if manager_ids:
        try:
            supabase = get_supabase()
            profiles_result = supabase.table("profiles") \
                .select("id, full_name") \
                .in_("id", manager_ids) \
                .execute()
            for p in (profiles_result.data or []):
                manager_names[p["id"]] = p.get("full_name", "—")
        except Exception:
            pass

    # Build customer rows — compact table: Name, INN, Manager, Status
    customer_rows = []
    for c in customers:
        status_class = "status-success" if c.is_active else "status-neutral"
        status_text = "Активен" if c.is_active else "Неактивен"
        manager_name = manager_names.get(c.manager_id, "—") if c.manager_id else "—"

        customer_rows.append(
            Tr(
                Td(A(c.name, href=f"/customers/{c.id}", style="color: var(--accent); text-decoration: none; font-weight: 500;")),
                Td(c.inn or "—", style="font-size: 13px; color: var(--text-secondary);"),
                Td(manager_name, style="font-size: 13px;"),
                Td(Span(status_text, cls=f"status-badge {status_class}")),
            )
        )

    return page_layout("Клиенты",
        # Unified Table with search in header
        Div(
            # Table header with search and filters
            Div(
                Div(
                    Form(
                        Input(type="text", name="q", value=q, placeholder="Поиск по названию или ИНН...", cls="table-search"),
                        Select(*status_options, name="status",
                               style="padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 6px; font-size: 13px; background: white;",
                               onchange="this.form.submit()"),
                        btn("Найти", variant="secondary", icon_name="search", type="submit", size="sm"),
                        method="get",
                        action="/customers",
                        style="display: flex; gap: 0.75rem; align-items: center;"
                    ),
                    cls="table-header-left"
                ),
                Div(
                    btn("Новый клиент", variant="primary", icon_name="plus",
                        onclick="document.getElementById('create-customer-modal').showModal()"),
                    cls="table-header-right"
                ),
                cls="table-header"
            ),
            # Compact stats summary
            Div(
                Span(f"Всего: {stats.get('total', 0)}", style="font-weight: 500;"),
                Span(f"Активных: {stats.get('active', 0)}"),
                Span(f"С контактами: {stats.get('with_contacts', 0)}"),
                style="display: flex; gap: 16px; padding: 6px 12px; font-size: 12px; color: var(--text-secondary);"
            ),
            # Table
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("НАИМЕНОВАНИЕ"),
                            Th("ИНН"),
                            Th("МЕНЕДЖЕР"),
                            Th("СТАТУС"),
                        )
                    ),
                    Tbody(*customer_rows) if customer_rows else Tbody(
                        Tr(Td("Клиенты не найдены", colspan="4", style="text-align: center; padding: 2rem; color: #666;"))
                    ),
                    cls="unified-table"
                ),
                cls="table-responsive"
            ),
            # Table footer
            Div(
                Span(f"Показано: {len(customers)}"),
                cls="table-footer"
            ),
            cls="table-container"
        ),

        # Modal dialog for creating a new customer
        Dialog(
            Div(
                H3("Новый клиент", style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600;"),
                Form(
                    Div(
                        Label("ИНН", style="font-size: 13px; font-weight: 500; color: #475569; display: block; margin-bottom: 4px;"),
                        Input(name="inn", placeholder="Введите ИНН компании", style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;"),
                        style="margin-bottom: 16px;"
                    ),
                    Div(
                        btn("Создать", variant="primary", icon_name="check", type="submit"),
                        btn("Не знаю ИНН", variant="secondary", icon_name="x",
                            type="submit", name="no_inn", value="1"),
                        Button("Отмена", type="button",
                               onclick="document.getElementById('create-customer-modal').close()",
                               style="padding: 8px 16px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; cursor: pointer;"),
                        style="display: flex; gap: 8px; justify-content: flex-end;"
                    ),
                    method="post",
                    action="/customers/new"
                ),
                style="padding: 24px; background: white; border-radius: 12px; min-width: 400px;"
            ),
            id="create-customer-modal",
            style="border: none; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.15); padding: 0;"
        ),

        session=session
    )


def _stat_card_simple(value: str, label: str, description: str = None):
    """Simple stat card without DaisyUI borders."""
    return Div(
        Div(label, style="color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;"),
        Div(value, style="font-size: 1.75rem; font-weight: 600; color: #e2e8f0;"),
        Div(description, style="color: #64748b; font-size: 0.75rem; margin-top: 0.25rem;") if description else None,
        style="background: linear-gradient(135deg, #2d2d44 0%, #1e1e2f 100%); border-radius: 0.75rem; padding: 1rem; text-align: center;"
    )


ORDER_SOURCE_OPTIONS = [
    ("cold_call", "Холодный звонок"),
    ("recommendation", "Рекомендация"),
    ("tender", "Тендер"),
    ("website", "Сайт"),
    ("exhibition", "Выставка"),
    ("social", "Соцсети"),
    ("repeat", "Повторный клиент"),
    ("other", "Другое"),
]

ORDER_SOURCE_LABELS = dict(ORDER_SOURCE_OPTIONS)


# @rt("/customers/{customer_id}")  # decorator removed; file is archived and not mounted
def get(customer_id: str, session, request, tab: str = "general"):
    """Customer detail view page with tabbed interface."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - sales, admin, top_manager, or head_of_sales can view customers
    if not user_has_any_role(session, ["admin", "sales", "top_manager", "head_of_sales"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра данной страницы.", cls="alert alert-error"),
            session=session
        )

    from services.customer_service import get_customer_with_contacts

    customer = get_customer_with_contacts(customer_id)
    if not customer:
        return page_layout("Не найдено",
            Div("Клиент не найден.", cls="alert alert-error"),
            btn_link("К списку клиентов", href="/customers", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Tab navigation using DaisyUI tabs (short labels to prevent wrapping)
    tabs_nav = tab_nav([
        {'id': 'general', 'label': 'Общая', 'url': f'/customers/{customer_id}?tab=general'},
        {'id': 'addresses', 'label': 'Адреса', 'url': f'/customers/{customer_id}?tab=addresses'},
        {'id': 'contacts', 'label': 'Контакты', 'url': f'/customers/{customer_id}?tab=contacts'},
        {'id': 'contracts', 'label': 'Договоры', 'url': f'/customers/{customer_id}?tab=contracts'},
        {'id': 'quotes', 'label': 'КП', 'url': f'/customers/{customer_id}?tab=quotes'},
        {'id': 'specifications', 'label': 'Спеки', 'url': f'/customers/{customer_id}?tab=specifications'},
        {'id': 'requested_items', 'label': 'Позиции', 'url': f'/customers/{customer_id}?tab=requested_items'},
        {'id': 'additional', 'label': 'Ещё', 'url': f'/customers/{customer_id}?tab=additional'},
        {'id': 'calls', 'label': 'Звонки', 'url': f'/customers/{customer_id}?tab=calls'},
        {'id': 'meetings', 'label': 'Встречи', 'url': f'/customers/{customer_id}?tab=meetings'},
    ], active_tab=tab, target_id="tab-content")

    # Build tab content based on selected tab
    if tab == "general":
        from services.customer_service import get_customer_statistics, get_customer_quotes, get_customer_specifications, get_customer_contracts
        from datetime import datetime

        # Get statistics
        stats = get_customer_statistics(customer_id)

        # Get raw customer data for manager_id
        supabase = get_supabase()
        raw_customer = supabase.table("customers").select("manager_id").eq("id", customer_id).limit(1).execute()
        current_manager_id = raw_customer.data[0].get("manager_id") if raw_customer.data else None

        # Look up manager name
        current_manager_name = "Не назначен"
        if current_manager_id:
            mgr_profile = supabase.table("user_profiles").select("full_name").eq("user_id", current_manager_id).limit(1).execute()
            if mgr_profile.data:
                current_manager_name = mgr_profile.data[0].get("full_name") or "—"

        # Get all org users for manager dropdown (for admin/top_manager/head_of_sales)
        user = session["user"]
        org_users = []
        can_change_manager = user_has_any_role(session, ["admin", "top_manager", "head_of_sales"])
        if can_change_manager:
            org_users_result = supabase.table("user_profiles").select("user_id, full_name").eq("organization_id", user["org_id"]).order("full_name").execute()
            org_users = org_users_result.data if org_users_result.data else []

        # Get latest quotes and specifications (for summary)
        all_quotes = get_customer_quotes(customer_id)
        all_specs = get_customer_specifications(customer_id)
        latest_quotes = all_quotes[:5] if all_quotes else []
        latest_specs = all_specs[:5] if all_specs else []

        # Get contracts for preview
        contracts = get_customer_contracts(customer_id)

        # Format dates
        created_at = ""
        if customer.created_at:
            created_at = customer.created_at.strftime("%d.%m.%Y %H:%M")

        updated_at = ""
        if customer.updated_at:
            updated_at = customer.updated_at.strftime("%d.%m.%Y %H:%M")

        # Helper to render workflow status badge
        def render_status_badge(status):
            status_map = {
                'draft': ('Черновик', 'status-draft'),
                'sent': ('Отправлено', 'status-sent'),
                'approved': ('Одобрено', 'status-approved'),
                'rejected': ('Отклонено', 'status-rejected'),
                'in_progress': ('В работе', 'status-progress'),
                'pending': ('На рассмотрении', 'status-pending'),
                'deal': ('Сделка', 'status-approved'),
            }
            label, cls = status_map.get(status, (status or '—', 'status-draft'))
            return Span(label, cls=f"status-badge {cls}", style="font-size: 0.75rem; padding: 0.25rem 0.5rem;")

        # Build contacts preview items
        contacts_preview_items = []
        for contact in customer.contacts[:5]:
            badges = []
            if contact.is_lpr:
                badges.append(Span("ЛПР", title="Лицо, принимающее решения", style="margin-left: 0.25rem; background: #dbeafe; color: #1d4ed8; padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.65rem; font-weight: 600;"))
            if contact.is_signatory:
                badges.append(Span(icon("pen-line", size=12), title="Подписант", style="margin-left: 0.25rem;"))
            if contact.is_primary:
                badges.append(Span("★", title="Основной", style="margin-left: 0.25rem; color: #f59e0b;"))
            contacts_preview_items.append(
                Div(
                    Div(
                        Span(contact.get_full_name(), style="font-weight: 500; color: #374151; font-size: 0.8rem;"),
                        *badges,
                        style="display: flex; align-items: center;"
                    ),
                    Div(contact.position or "—", style="font-size: 0.7rem; color: #6b7280;"),
                    style="padding: 0.35rem 0; border-bottom: 1px solid #e5e7eb;"
                )
            )

        # Build contracts preview items
        contracts_preview_items = []
        for contract in contracts[:5]:
            status = contract.get("status", "")
            status_color = "#10b981" if status == "active" else "#6b7280"
            status_text = "активен" if status == "active" else ("истёк" if status == "terminated" else status)
            contracts_preview_items.append(
                Div(
                    Div(
                        Span(f"№{contract.get('contract_number', '—')}", style="font-weight: 500; color: #374151; font-size: 0.8rem;"),
                        style="display: flex; align-items: center;"
                    ),
                    Div(status_text, style=f"font-size: 0.7rem; color: {status_color};"),
                    style="padding: 0.35rem 0; border-bottom: 1px solid #e5e7eb;"
                )
            )

        # Build latest quotes rows
        quotes_rows = []
        for q in latest_quotes:
            q_date = ""
            if q.get("created_at"):
                try:
                    q_date = datetime.fromisoformat(q["created_at"].replace("Z", "+00:00")).strftime("%d.%m.%Y")
                except:
                    q_date = "—"
            quotes_rows.append(
                Tr(
                    Td(A(q.get("idn_quote") or f"#{q['id'][:8]}", href=f"/quotes/{q['id']}", style="font-weight: 500; color: var(--accent);")),
                    Td(format_money(q.get('total_sum'), q.get('currency', 'RUB')), style="text-align: right;"),
                    Td(format_money(q.get('total_profit'), q.get('currency', 'RUB')), style="text-align: right; color: #10b981;"),
                    Td(q_date),
                    Td(render_status_badge(q.get("workflow_status"))),
                )
            )

        # Build latest specs rows
        specs_rows = []
        for s in latest_specs:
            s_date = ""
            if s.get("sign_date"):
                try:
                    s_date = datetime.fromisoformat(s["sign_date"].replace("Z", "+00:00")).strftime("%d.%m.%Y")
                except:
                    s_date = "—"
            elif s.get("created_at"):
                try:
                    s_date = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")).strftime("%d.%m.%Y")
                except:
                    s_date = "—"
            spec_idn = s.get("idn") or (s.get("quotes") or {}).get("idn_quote") or f"#{s['id'][:8]}"
            spec_currency = (s.get("quotes") or {}).get("currency", "RUB")
            specs_rows.append(
                Tr(
                    Td(A(spec_idn, href=f"/specifications/{s['id']}", style="font-weight: 500; color: var(--accent);")),
                    Td(format_money(s.get('total_sum'), spec_currency), style="text-align: right;"),
                    Td(format_money(s.get('total_profit'), spec_currency), style="text-align: right; color: #10b981;"),
                    Td(s_date),
                    Td(render_status_badge(s.get("status"))),
                )
            )

        # Get customer debt summary
        from services.plan_fact_service import get_customer_debt_summary
        debt_summary = get_customer_debt_summary(customer_id)
        total_debt = debt_summary.get("total_debt", 0)
        overdue_count = debt_summary.get("overdue_count", 0)
        overdue_amount = debt_summary.get("overdue_amount", 0)
        last_payment_date = debt_summary.get("last_payment_date")
        last_payment_amount = debt_summary.get("last_payment_amount")
        unpaid_count = debt_summary.get("unpaid_count", 0)

        # Build debt card
        overdue_badge = Span(f"{overdue_count} просрочено", style="background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;") if overdue_count > 0 else Span("Нет просрочек", style="background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;")

        last_payment_info = ""
        if last_payment_date and last_payment_amount:
            last_payment_info = f"Последний платёж: {last_payment_amount:,.0f} ₽ ({last_payment_date})"
        elif last_payment_date:
            last_payment_info = f"Последний платёж: {last_payment_date}"
        else:
            last_payment_info = "Последний платёж: нет данных"

        debt_card = Div(
            Div(
                Span(icon("wallet", size=14), " Задолженность", style="color: #374151; display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; font-weight: 500;"),
                A("Подробнее →", href=f"/finance?tab=payments&customer_filter={customer_id}",
                  style="font-size: 0.75rem; color: #3b82f6; text-decoration: none;"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;"
            ),
            Div(
                Div(
                    Div("Долг", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                    Div(f"{total_debt:,.0f} ₽", style=f"font-size: 1.25rem; font-weight: 700; color: {'#991b1b' if total_debt > 0 else '#166534'};"),
                    style="flex: 1;"
                ),
                Div(
                    Div("Неоплачено", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                    Div(f"{unpaid_count} позиций", style="font-size: 0.875rem; font-weight: 500; color: #374151;"),
                    style="flex: 1;"
                ),
                Div(
                    overdue_badge,
                    style="flex: 1; display: flex; align-items: center;"
                ),
                style="display: flex; gap: 1rem; margin-bottom: 0.5rem;"
            ),
            Div(last_payment_info, style="color: #6b7280; font-size: 0.8rem;"),
            cls="card",
            style="background: white; border-radius: 0.75rem; padding: 0.75rem; border: 1px solid #e5e7eb;"
        )

        tab_content = Div(
            # Row 1: Three cards side by side with equal height
            Div(
                # Card 1: Company info (narrow, 2 columns layout)
                Div(
                    # Company name (full width)
                    Div(
                        Div("Название", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                        _render_field_display(customer_id, "name", customer.name or ""),
                        style="margin-bottom: 0.5rem;"
                    ),
                    # 2-column grid for fields
                    Div(
                        Div(
                            Div("ИНН", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            _render_field_display(customer_id, "inn", customer.inn or ""),
                        ),
                        Div(
                            Div("КПП", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            _render_field_display(customer_id, "kpp", customer.kpp or ""),
                        ),
                        Div(
                            Div("ОГРН", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            _render_field_display(customer_id, "ogrn", customer.ogrn or ""),
                        ),
                        Div(
                            Div("Статус", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            Span("Активен" if customer.is_active else "Неактивен",
                                 cls=f"status-badge {'status-approved' if customer.is_active else 'status-rejected'}",
                                 style="margin-top: 0.25rem; display: inline-block;"),
                        ),
                        Div(
                            Div("Создан", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            Div(created_at or "—", style="color: #374151; font-size: 0.8rem; padding: 0.25rem 0;"),
                        ),
                        Div(
                            Div("Обновлён", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            Div(updated_at or "—", style="color: #374151; font-size: 0.8rem; padding: 0.25rem 0;"),
                        ),
                        Div(
                            Div("Источник", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            _render_field_display(customer_id, "order_source", customer.order_source or ""),
                        ),
                        Div(
                            Div("Менеджер", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"),
                            Div(
                                Select(
                                    Option("Не назначен", value=""),
                                    *[Option(u.get("full_name", "—"), value=u["user_id"], selected=(u["user_id"] == current_manager_id)) for u in org_users],
                                    name="manager_id",
                                    hx_put=f"/customers/{customer_id}/manager",
                                    hx_target=f"#manager-status-{customer_id}",
                                    hx_swap="innerHTML",
                                    style="font-size: 0.8rem; padding: 0.25rem 0.5rem; border: 1px solid #d1d5db; border-radius: 6px; background: white; width: 100%; max-width: 200px;"
                                ),
                                Span(id=f"manager-status-{customer_id}", style="margin-left: 0.5rem; font-size: 0.8rem;"),
                                style="display: flex; align-items: center; padding: 0.25rem 0;"
                            ) if can_change_manager else Div(
                                current_manager_name,
                                style="color: #374151; font-size: 0.8rem; padding: 0.25rem 0;"
                            ),
                        ),
                        style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;"
                    ),
                    cls="card",
                    style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb; flex: 1; min-width: 200px;"
                ),

                # Card 2: Contacts preview
                Div(
                    Div(
                        Span(icon("users", size=14), " Контакты", style="color: #374151; display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; font-weight: 500;"),
                        A("→", href=f"/customers/{customer_id}?tab=contacts",
                          hx_get=f"/customers/{customer_id}?tab=contacts",
                          hx_target="#tab-content",
                          hx_push_url="true",
                          style="font-size: 0.875rem; color: #3b82f6;"),
                        style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;"
                    ),
                    Div(
                        *contacts_preview_items if contacts_preview_items else [
                            Div("Нет контактов", style="color: #9ca3af; font-size: 0.8rem; text-align: center; padding: 1rem;")
                        ],
                        style="flex: 1; overflow-y: auto;"
                    ),
                    cls="card",
                    style="background: white; border-radius: 0.75rem; padding: 0.75rem; cursor: pointer; border: 1px solid #e5e7eb; flex: 1; display: flex; flex-direction: column;",
                    hx_get=f"/customers/{customer_id}?tab=contacts",
                    hx_target="#tab-content",
                    hx_push_url="true",
                ),

                # Card 3: Contracts preview
                Div(
                    Div(
                        Span(icon("file-text", size=14), " Договоры", style="color: #374151; display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; font-weight: 500;"),
                        A("→", href=f"/customers/{customer_id}?tab=contracts",
                          hx_get=f"/customers/{customer_id}?tab=contracts",
                          hx_target="#tab-content",
                          hx_push_url="true",
                          style="font-size: 0.875rem; color: #3b82f6;"),
                        style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;"
                    ),
                    Div(
                        *contracts_preview_items if contracts_preview_items else [
                            Div("Нет договоров", style="color: #9ca3af; font-size: 0.8rem; text-align: center; padding: 1rem;")
                        ],
                        style="flex: 1; overflow-y: auto;"
                    ),
                    cls="card",
                    style="background: white; border-radius: 0.75rem; padding: 0.75rem; cursor: pointer; border: 1px solid #e5e7eb; flex: 1; display: flex; flex-direction: column;",
                    hx_get=f"/customers/{customer_id}?tab=contracts",
                    hx_target="#tab-content",
                    hx_push_url="true",
                ),
                style="display: flex; gap: 1rem; margin-bottom: 1rem; align-items: stretch;"
            ),

            # Row 1.5: Debt summary card
            Div(
                debt_card,
                style="margin-bottom: 1rem;"
            ),

            # Row 2: Two tables side by side (Quotes + Specifications) with stats in headers
            Div(
                # Latest Quotes table
                Div(
                    Div(
                        Div(
                            H3(icon("file-text", size=18), " КП", style="margin: 0; color: #374151; display: flex; align-items: center; gap: 0.5rem; font-size: 1rem;"),
                            Span(f"Всего: {stats['quotes_count']}", style="color: #6b7280; font-size: 0.75rem;"),
                            style="display: flex; flex-direction: column; gap: 0.25rem;"
                        ),
                        A("Все →", href=f"/customers/{customer_id}?tab=quotes",
                          hx_get=f"/customers/{customer_id}?tab=quotes",
                          hx_target="#tab-content",
                          hx_push_url="true",
                          style="font-size: 0.75rem; color: #3b82f6;"),
                        style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;"
                    ),
                    Table(
                        Thead(
                            Tr(
                                Th("№", style="font-size: 0.7rem; color: #6b7280;"),
                                Th("Сумма", style="font-size: 0.7rem; text-align: right; color: #6b7280;"),
                                Th("Профит", style="font-size: 0.7rem; text-align: right; color: #6b7280;"),
                                Th("Дата", style="font-size: 0.7rem; color: #6b7280;"),
                                Th("Статус", style="font-size: 0.7rem; color: #6b7280;"),
                            )
                        ),
                        Tbody(*quotes_rows) if quotes_rows else Tbody(
                            Tr(Td("Нет КП", colspan="5", style="text-align: center; color: #9ca3af; padding: 1rem;"))
                        ),
                        cls="unified-table compact-table"
                    ),
                    cls="card",
                    style="background: white; border-radius: 0.75rem; padding: 0.75rem; flex: 1; border: 1px solid #e5e7eb;"
                ),

                # Latest Specifications table
                Div(
                    Div(
                        Div(
                            H3(icon("clipboard", size=18), " Спецификации", style="margin: 0; color: #374151; display: flex; align-items: center; gap: 0.5rem; font-size: 1rem;"),
                            Span(f"Всего: {stats['specifications_count']}" + (f" • Сумма: {stats['specifications_sum']:,.0f}" if stats['specifications_sum'] else ""), style="color: #6b7280; font-size: 0.75rem;"),
                            style="display: flex; flex-direction: column; gap: 0.25rem;"
                        ),
                        A("Все →", href=f"/customers/{customer_id}?tab=specifications",
                          hx_get=f"/customers/{customer_id}?tab=specifications",
                          hx_target="#tab-content",
                          hx_push_url="true",
                          style="font-size: 0.75rem; color: #3b82f6;"),
                        style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;"
                    ),
                    Table(
                        Thead(
                            Tr(
                                Th("№", style="font-size: 0.7rem; color: #6b7280;"),
                                Th("Сумма", style="font-size: 0.7rem; text-align: right; color: #6b7280;"),
                                Th("Профит", style="font-size: 0.7rem; text-align: right; color: #6b7280;"),
                                Th("Дата", style="font-size: 0.7rem; color: #6b7280;"),
                                Th("Статус", style="font-size: 0.7rem; color: #6b7280;"),
                            )
                        ),
                        Tbody(*specs_rows) if specs_rows else Tbody(
                            Tr(Td("Нет спецификаций", colspan="5", style="text-align: center; color: #9ca3af; padding: 1rem;"))
                        ),
                        cls="unified-table compact-table"
                    ),
                    cls="card",
                    style="background: white; border-radius: 0.75rem; padding: 0.75rem; flex: 1; border: 1px solid #e5e7eb;"
                ),
                style="display: flex; gap: 1.5rem;"
            )
        )

    elif tab == "addresses":
        # Show postal address only if it differs from actual_address
        show_postal = customer.postal_address and customer.postal_address != customer.actual_address

        _addr_label = "color: #6b7280; font-size: 0.8em; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 0.375rem;"
        _addr_block = "margin-bottom: 1rem;"

        # Block 1: Official addresses
        official_block = Div(
            Div(
                icon("building-2", size=16, color="#64748b"),
                Span(" Официальные адреса", style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
            ),
            Div(
                Div(Strong("Юридический"), style=_addr_label),
                _render_field_display(customer_id, "legal_address", customer.legal_address or ""),
                style=_addr_block
            ),
            Div(
                Div(Strong("Фактический"), style=_addr_label),
                _render_field_display(customer_id, "actual_address", customer.actual_address or ""),
                style=_addr_block
            ),
            Div(
                Div(Strong("Почтовый"), style=_addr_label),
                _render_field_display(customer_id, "postal_address", customer.postal_address or ""),
                style=_addr_block
            ) if show_postal else Div(
                Div(Strong("Почтовый"), style=_addr_label),
                Div("Совпадает с фактическим", style="color: #9ca3af; font-size: 13px; font-style: italic; padding: 0.25rem 0;"),
                style=_addr_block
            ),
            cls="card",
            style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb; margin-bottom: 1rem;"
        )

        # Block 2: Warehouse addresses
        warehouse_block = Div(
            Div(
                icon("warehouse", size=16, color="#64748b"),
                Span(" Склады", style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
            ),
            _render_warehouses_list(customer_id, customer.warehouse_addresses or []),
            btn("Добавить склад", variant="secondary", icon_name="plus", type="button",
                hx_get=f"/customers/{customer_id}/warehouses/add",
                hx_target="#add-warehouse-form",
                hx_swap="outerHTML",
                id="add-warehouse-form"),
            cls="card",
            style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb;"
        )

        tab_content = Div(official_block, warehouse_block)

    elif tab == "contacts":
        # Build contacts list with inline editing
        contacts_rows = []
        for contact in customer.contacts:
            contacts_rows.append(_render_contact_row(contact, customer_id))

        # Add button for table header
        add_btn = A(
            icon("plus", size=14), " Добавить",
            href=f"/customers/{customer_id}/contacts/new",
            style="background: var(--accent); color: white; padding: 0.4rem 0.75rem; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; font-weight: 500;"
        )

        tab_content = Div(
            Div(
                Div(
                    Table(
                        Thead(Tr(
                            Th("ФИО"),
                            Th("ДОЛЖНОСТЬ"),
                            Th("EMAIL"),
                            Th("ТЕЛЕФОН"),
                            Th("ЗАМЕТКИ"),
                            Th(add_btn, style="text-align: right;", cls="col-actions")
                        )),
                        Tbody(*contacts_rows, id="contacts-tbody") if contacts_rows else Tbody(
                            Tr(Td("Контакты не добавлены.", colspan="6", style="text-align: center; padding: 2rem; color: #666;")),
                            id="contacts-tbody"
                        ),
                        cls="unified-table compact-table"
                    ),
                    cls="table-responsive"
                ),
                Div(Span(f"Всего: {len(customer.contacts)} контактов"), cls="table-footer"),
                cls="table-container", style="margin: 0;"
            )
        )

    elif tab == "contracts":
        from services.customer_service import get_customer_contracts

        contracts = get_customer_contracts(customer_id)

        contracts_rows = []
        for contract in contracts:
            # Format date
            contract_date = contract.get("contract_date", "")
            if contract_date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(contract_date.replace("Z", "+00:00"))
                    contract_date = dt.strftime("%d.%m.%Y")
                except:
                    pass

            # Status badge
            status = contract.get("status", "")
            status_text = {
                "active": "Активен",
                "suspended": "Приостановлен",
                "terminated": "Расторгнут"
            }.get(status, status)

            status_class = {
                "active": "status-approved",
                "suspended": "status-pending",
                "terminated": "status-rejected"
            }.get(status, "")

            # Contract type badge
            c_type = contract.get("contract_type", "")
            c_type_names = {"one_time": "Единоразовый", "renewable": "Пролонгируемый"}
            c_type_colors = {"one_time": "#3b82f6", "renewable": "#10b981"}
            type_badge = Span(
                c_type_names.get(c_type, ""),
                style=f"display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; color: white; background: {c_type_colors.get(c_type, '#94a3b8')};"
            ) if c_type else Span("—", style="color: #94a3b8;")

            # End date
            c_end_date = contract.get("end_date", "")
            if c_end_date:
                try:
                    from datetime import datetime as dt_cls
                    ed = dt_cls.fromisoformat(c_end_date.replace("Z", "+00:00")) if isinstance(c_end_date, str) else c_end_date
                    c_end_date_str = ed.strftime("%d.%m.%Y") if hasattr(ed, 'strftime') else str(c_end_date)
                except Exception:
                    c_end_date_str = str(c_end_date)
            else:
                c_end_date_str = "—"

            contracts_rows.append(
                Tr(
                    Td(Strong(contract.get("contract_number", "—"))),
                    Td(contract_date or "—"),
                    Td(type_badge),
                    Td(c_end_date_str),
                    Td(Span(status_text, cls=f"status-badge {status_class}")),
                    Td(
                        A(icon("file-text", size=16), href=f"/customer-contracts/{contract['id']}", title="Просмотр") if contract.get("id") else "—"
                    )
                )
            )

        add_btn = A(
            icon("plus", size=14), " Добавить",
            href=f"/customer-contracts/new?customer_id={customer_id}",
            style="background: var(--accent); color: white; padding: 0.4rem 0.75rem; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; font-weight: 500;"
        )

        tab_content = Div(
            Div(
                Div(
                    Table(
                        Thead(Tr(
                            Th("НОМЕР"),
                            Th("ДАТА"),
                            Th("ТИП"),
                            Th("ОКОНЧАНИЕ"),
                            Th("СТАТУС"),
                            Th(add_btn, style="text-align: right;", cls="col-actions")
                        )),
                        Tbody(*contracts_rows) if contracts_rows else Tbody(
                            Tr(Td("Договоры не найдены.", colspan="6", style="text-align: center; padding: 2rem; color: #666;"))
                        ),
                        cls="unified-table"
                    ),
                    cls="table-responsive"
                ),
                Div(Span(f"Всего: {len(contracts)} договоров"), cls="table-footer"),
                cls="table-container", style="margin: 0;"
            )
        )

    elif tab == "quotes":
        from services.customer_service import get_customer_quotes

        quotes = get_customer_quotes(customer_id)

        quotes_rows = []
        for quote in quotes:
            # Format date
            created_at = quote.get("created_at", "")
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    created_at = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    pass

            # Status badge
            workflow_status = quote.get("workflow_status", "")
            status_text = {
                "draft": "Черновик",
                "pending_procurement": "Закупка",
                "pending_logistics": "Логистика",
                "pending_customs": "Таможня",
                "pending_quote_control": "Контроль КП",
                "pending_spec_control": "Контроль спец.",
                "pending_sales_review": "Ревизия",
                "pending_approval": "Согласование",
                "approved": "Одобрено",
                "sent_to_client": "Отправлено",
                "deal": "Сделка",
                "rejected": "Отклонено",
                "cancelled": "Отменено"
            }.get(workflow_status, workflow_status)

            # Format sum and profit
            total_sum = quote.get("total_sum", 0)
            total_profit = quote.get("total_profit", 0)

            q_currency = quote.get("currency", "RUB")

            status_cls_map = {
                "draft": "status-draft", "pending_procurement": "status-pending",
                "approved": "status-approved", "sent_to_client": "status-sent",
                "deal": "status-approved", "rejected": "status-rejected",
                "cancelled": "status-neutral"
            }
            s_cls = status_cls_map.get(workflow_status, "status-draft")

            quotes_rows.append(
                Tr(
                    Td(created_at or "—", style="white-space: nowrap;"),
                    Td(A(quote.get("idn_quote", "—"), href=f"/quotes/{quote['id']}", style="font-weight: 500; color: var(--accent);")),
                    Td(Span(status_text, cls=f"status-badge {s_cls}")),
                    Td(format_money(total_sum, q_currency) if total_sum else "—", style="text-align: right;"),
                    Td(format_money(total_profit, q_currency) if total_profit else "—", style="text-align: right; color: " + ("#16a34a" if total_profit > 0 else "#666")),
                )
            )

        add_btn = A(
            icon("plus", size=14), " Создать КП",
            href=f"/quotes/new?customer_id={customer_id}",
            style="background: var(--accent); color: white; padding: 0.4rem 0.75rem; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; font-weight: 500;"
        )

        tab_content = Div(
            Div(
                Div(
                    Table(
                        Thead(Tr(
                            Th("ДАТА"),
                            Th("IDN"),
                            Th("СТАТУС"),
                            Th("СУММА", cls="col-money"),
                            Th("ПРОФИТ", cls="col-money"),
                            Th(add_btn, style="text-align: right;")
                        )),
                        Tbody(*quotes_rows) if quotes_rows else Tbody(
                            Tr(Td("КП не найдены.", colspan="6", style="text-align: center; padding: 2rem; color: #666;"))
                        ),
                        cls="unified-table compact-table"
                    ),
                    cls="table-responsive"
                ),
                Div(Span(f"Всего: {len(quotes)} КП"), cls="table-footer"),
                cls="table-container", style="margin: 0;"
            )
        )

    elif tab == "specifications":
        from services.customer_service import get_customer_specifications

        specifications = get_customer_specifications(customer_id)

        specs_rows = []
        for spec in specifications:
            # Format date
            sign_date = spec.get("sign_date", "")
            if sign_date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(sign_date.replace("Z", "+00:00"))
                    sign_date = dt.strftime("%d.%m.%Y")
                except:
                    pass

            # Status badge
            status = spec.get("status", "")
            status_text = {
                "draft": "Черновик",
                "pending_review": "На проверке",
                "approved": "Согласовано",
                "signed": "Подписано"
            }.get(status, status)

            # Get quote IDN if available
            quote_idn = ""
            if spec.get("quotes"):
                quote_idn = (spec["quotes"] or {}).get("idn_quote", "")

            # Format sum and profit
            total_sum = spec.get("total_sum", 0)
            total_profit = spec.get("total_profit", 0)

            spec_currency = (spec.get("quotes") or {}).get("currency", "RUB")
            specs_rows.append(
                Tr(
                    Td(Strong(spec.get("specification_number", "—"))),
                    Td(A(quote_idn, href=f"/quotes/{spec.get('quote_id')}") if spec.get("quote_id") else "—"),
                    Td(format_money(total_sum, spec_currency) if total_sum else "—", style="text-align: right;"),
                    Td(format_money(total_profit, spec_currency) if total_profit else "—", style="text-align: right; color: " + ("#16a34a" if total_profit > 0 else "#666")),
                    Td(sign_date or "—", style="font-size: 0.9em;"),
                    Td(Span(status_text, cls="status-badge")),
                )
            )

        tab_content = Div(
            Div(
                Div(
                    Table(
                        Thead(Tr(
                            Th("НОМЕР"),
                            Th("IDN"),
                            Th("СУММА", cls="col-money"),
                            Th("ПРОФИТ", cls="col-money"),
                            Th("ДАТА"),
                            Th("СТАТУС")
                        )),
                        Tbody(*specs_rows) if specs_rows else Tbody(
                            Tr(Td("Спецификации не найдены.", colspan="6", style="text-align: center; padding: 2rem; color: #666;"))
                        ),
                        cls="unified-table"
                    ),
                    cls="table-responsive"
                ),
                Div(Span(f"Всего: {len(specifications)} спецификаций"), cls="table-footer"),
                cls="table-container", style="margin: 0;"
            )
        )

    elif tab == "requested_items":
        from services.customer_service import get_customer_requested_items

        items = get_customer_requested_items(customer_id)

        items_rows = []
        for item in items:
            product = item.get("product", {}) or {}

            # Format last requested date
            last_requested = item.get("last_requested_at", "")
            if last_requested:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(last_requested.replace("Z", "+00:00"))
                    last_requested = dt.strftime("%d.%m.%Y")
                except:
                    pass

            # Brands as comma-separated
            brands = ", ".join(item.get("brands", [])) if item.get("brands") else "—"

            # Quantity
            total_quantity = item.get("total_quantity", 0)

            # Price
            last_price = item.get("last_price")
            last_currency = item.get("last_currency", "RUB")
            price_display = format_money(last_price, last_currency) if last_price else "—"

            # Was sold status
            was_sold = item.get("was_sold", False)
            sold_badge = Span(icon("check-circle", size=14), " Продан", cls="status-badge status-approved", style="display: inline-flex; align-items: center; gap: 0.25rem;") if was_sold else Span("—", style="color: #999;")

            items_rows.append(
                Tr(
                    Td(Strong(product.get("name", "—"))),
                    Td(brands),
                    Td(product.get("sku", "—")),
                    Td(f"{total_quantity:,.0f}" if total_quantity else "—", style="text-align: right;"),
                    Td(price_display, style="text-align: right;"),
                    Td(last_requested or "—", style="font-size: 0.9em;"),
                    Td(sold_badge),
                )
            )

        tab_content = Div(
            Div(
                Div(
                    Table(
                        Thead(Tr(
                            Th("НАЗВАНИЕ"),
                            Th("БРЕНД"),
                            Th("АРТИКУЛ"),
                            Th("КОЛ-ВО", cls="col-number"),
                            Th("ЦЕНА", cls="col-money"),
                            Th("ДАТА"),
                            Th("СТАТУС")
                        )),
                        Tbody(*items_rows) if items_rows else Tbody(
                            Tr(Td("Позиции не найдены.", colspan="7", style="text-align: center; padding: 2rem; color: #666;"))
                        ),
                        cls="unified-table compact-table"
                    ),
                    cls="table-responsive"
                ),
                Div(Span(f"Всего: {len(items)} позиций"), cls="table-footer"),
                cls="table-container", style="margin: 0;"
            )
        )

    elif tab == "additional":
        # Additional tab - notes/remarks with inline editing
        tab_content = Div(
            Div(
                H3(icon("more-horizontal", size=20), " Дополнительная информация", style="margin-bottom: 1rem; color: #e2e8f0; display: flex; align-items: center; gap: 0.5rem;"),
                Div(
                    Div(
                        Div("Заметки / Примечания", style="color: #94a3b8; font-size: 0.8rem; margin-bottom: 0.5rem;"),
                        _render_notes_display(customer_id, customer.notes or ""),
                        style="margin-bottom: 1rem;"
                    ),
                    style="padding: 1rem;"
                ),
                cls="card",
                style="background: linear-gradient(135deg, #2d2d44 0%, #1e1e2f 100%); border-radius: 0.75rem; max-width: 800px;"
            )
        )

    elif tab == "calls":
        from services.call_service import get_calls_for_customer

        calls = get_calls_for_customer(customer_id)

        tab_content = Div(
            # Add call button + modal container
            Div(
                btn("Внести звонок", variant="primary", icon_name="phone",
                    hx_get=f"/customers/{customer_id}/calls/new-form",
                    hx_target="#call-modal-container",
                    hx_swap="innerHTML"),
                Div(id="call-modal-container"),
                style="margin-bottom:16px;"
            ),
            # Call history list - reuse shared renderer
            _render_calls_list(customer_id, calls),
            style="padding:16px 0;"
        )

    elif tab == "meetings":
        # Meetings tab - redirects to calls tab
        tab_content = Div(
            Div(
                icon("calendar", size=48),
                H3("Встречи", style="margin: 1rem 0 0.5rem; color: #e2e8f0;"),
                P("Запланированные звонки смотрите во вкладке Звонки", style="color: #64748b;"),
                cls="flex flex-col items-center justify-center",
                style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 4rem; text-align: center; color: #94a3b8;"
            ),
            cls="card",
            style="background: linear-gradient(135deg, #2d2d44 0%, #1e1e2f 100%); border-radius: 0.75rem;"
        )

    else:
        tab_content = Div("Неизвестная вкладка")

    # If this is an HTMX request (tab switch), return only the tab content
    if request and request.headers.get("HX-Request"):
        return tab_content

    return page_layout(f"Клиент: {customer.name}",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Клиенты", href="/customers",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Div(
                        icon("building", size=24, color="#10b981"),
                        H1(customer.name, style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    Div(
                        Span("Активен" if customer.is_active else "Неактивен",
                             style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: {'#16a34a' if customer.is_active else '#dc2626'}; background: {'#dcfce7' if customer.is_active else '#fee2e2'};"),
                        A(icon("file-plus", size=14), " Создать КП",
                          href=f"/quotes/new?customer_id={customer_id}",
                          cls="btn btn--primary",
                          style="font-size: 13px; padding: 6px 14px;"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Tabs navigation (DaisyUI)
        tabs_nav,

        # Tab content wrapper for HTMX targeting
        Div(tab_content, id="tab-content", style="min-height: 300px;"),

        session=session
    )


# ============================================================================
# CALLS JOURNAL — Customer-scoped HTMX endpoints
# ============================================================================

def _render_calls_list(customer_id: str, calls: list) -> object:
    """Render the #calls-list div fragment for HTMX swap."""
    from services.call_service import CALL_TYPE_LABELS, CALL_CATEGORY_LABELS

    rows = []
    for c in calls:
        type_label = CALL_TYPE_LABELS.get(c.call_type, c.call_type)
        cat_label = CALL_CATEGORY_LABELS.get(c.call_category or "", "")

        date_str = "—"
        if c.call_type == "scheduled" and c.scheduled_date:
            date_str = c.scheduled_date.strftime("%d.%m.%Y %H:%M")
        elif c.created_at:
            date_str = c.created_at.strftime("%d.%m.%Y %H:%M")

        type_color = "#2563eb" if c.call_type == "scheduled" else "#10b981"
        type_bg = "#bfdbfe" if c.call_type == "scheduled" else "#d1fae5"
        type_badge = Span(type_label, style=f"background:{type_bg};color:{type_color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;")

        cat_colors = {"cold": ("#6b7280", "#f1f5f9"), "warm": ("#f59e0b", "#fef3c7"), "incoming": ("#8b5cf6", "#ede9fe")}
        c_fg, c_bg = cat_colors.get(c.call_category or "", ("#6b7280", "#f1f5f9"))
        cat_badge = Span(cat_label, style=f"background:{c_bg};color:{c_fg};padding:2px 8px;border-radius:4px;font-size:11px;") if cat_label else ""

        rows.append(Div(
            Div(
                Div(type_badge, cat_badge, style="display:flex;gap:6px;align-items:center;"),
                Div(
                    Button(icon("edit-2", size=14),
                        hx_get=f"/customers/{customer_id}/calls/{c.id}/edit-form",
                        hx_target="#call-modal-container",
                        hx_swap="innerHTML",
                        style="background:none;border:none;cursor:pointer;color:#64748b;padding:4px;"),
                    Button(icon("trash-2", size=14),
                        hx_delete=f"/customers/{customer_id}/calls/{c.id}",
                        hx_target="#calls-list",
                        hx_swap="outerHTML",
                        hx_confirm="Удалить запись о звонке?",
                        style="background:none;border:none;cursor:pointer;color:#ef4444;padding:4px;"),
                    style="display:flex;gap:2px;"
                ),
                style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;"
            ),
            Div(
                Span(c.contact_name or "Не указан контакт", style="color:#64748b;font-size:12px;"),
                Span(" · ", style="color:#cbd5e1;"),
                Span(c.user_name or "—", style="color:#64748b;font-size:12px;"),
                Span(" · ", style="color:#cbd5e1;"),
                Span(date_str, style="color:#64748b;font-size:12px;"),
            ),
            P(c.comment or "Без комментария", style="margin:6px 0 0;font-size:13px;color:#374151;white-space:pre-wrap;"),
            Div(
                Div(
                    Span("Потребление / Зона: ", style="color:#64748b;font-size:12px;font-weight:500;"),
                    Span(c.customer_needs, style="font-size:13px;color:#374151;"),
                ) if c.customer_needs else None,
                Div(
                    Span("Назначение встречи: ", style="color:#64748b;font-size:12px;font-weight:500;"),
                    Span(c.meeting_notes, style="font-size:13px;color:#374151;"),
                ) if c.meeting_notes else None,
                style="margin-top:4px;display:flex;flex-direction:column;gap:2px;"
            ) if (c.customer_needs or c.meeting_notes) else None,
            style="padding:12px 0;border-bottom:1px solid #e2e8f0;"
        ))

    return Div(
        *rows if rows else [
            Div(icon("phone-off", size=32, color="#cbd5e1"),
                P("Звонков пока нет", style="color:#64748b;margin-top:8px;"),
                style="text-align:center;padding:2rem;")
        ],
        id="calls-list",
        style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:0 16px;"
    )


# @rt("/customers/{customer_id}/manager")  # decorator removed; file is archived and not mounted
def put(customer_id: str, session, manager_id: str = ""):
    """Update customer manager."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "top_manager", "head_of_sales"]):
        return Span("Нет прав", style="color: red;")

    user = session["user"]
    supabase = get_supabase()
    try:
        supabase.table("customers").update({"manager_id": manager_id or None}).eq("id", customer_id).eq("organization_id", user["org_id"]).execute()

        # Get updated manager name
        manager_name = "Не назначен"
        if manager_id:
            profile = supabase.table("user_profiles").select("full_name").eq("user_id", manager_id).limit(1).execute()
            if profile.data:
                manager_name = profile.data[0].get("full_name", "—")

        return Span(f"OK {manager_name}", style="color: #16a34a; font-weight: 500;")
    except Exception as e:
        print(f"Error updating customer manager: {e}")
        return Span("Ошибка сохранения", style="color: red;")


# @rt("/customers/{customer_id}/calls/new-form")  # decorator removed; file is archived and not mounted
def get(session, customer_id: str):
    """HTMX partial - 'Внести звонок' modal form."""
    redirect = require_login(session)
    if redirect:
        return redirect
    if not user_has_any_role(session, ["admin", "sales", "sales_manager", "top_manager"]):
        return Div(P("Доступ запрещён"), style="color:red;")

    supabase = get_supabase()
    # Fetch contacts for this customer
    try:
        contacts_resp = supabase.table("customer_contacts") \
            .select("id, name, position") \
            .eq("customer_id", customer_id) \
            .order("name") \
            .execute()
        contacts = contacts_resp.data or []
    except Exception:
        contacts = []

    contact_options = [Option("Не указан", value="")] + [
        Option(f"{c['name']}" + (f" ({c['position']})" if c.get('position') else ""), value=c['id'])
        for c in contacts
    ]

    input_style = "width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;"
    select_style = "width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;background:#fff;"

    form = Div(
        Div(
            Div(
                H3("Внести звонок", style="margin:0;font-size:16px;font-weight:600;"),
                Button("✕",
                    onclick="document.getElementById('call-modal-container').innerHTML=''",
                    style="background:none;border:none;font-size:1.2rem;cursor:pointer;padding:4px;"),
                style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;"
            ),
            Form(
                # Type selector
                Div(
                    Label("Тип *", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Select(
                        Option("Звонок", value="call", selected=True),
                        Option("Запланировать звонок", value="scheduled"),
                        name="call_type",
                        id="call-type-select",
                        style=select_style,
                        onchange="document.getElementById('scheduled-date-row').style.display = this.value==='scheduled' ? 'block' : 'none';"
                    ),
                    style="margin-bottom:12px;"
                ),
                # Scheduled date (hidden initially)
                Div(
                    Label("Дата и время звонка *", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Input(name="scheduled_date", type="datetime-local", style=input_style),
                    id="scheduled-date-row",
                    style="margin-bottom:12px;display:none;"
                ),
                # Contact person
                Div(
                    Label("Контактное лицо", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Select(*contact_options, name="contact_person_id", style=select_style),
                    Small(
                        A("+ Добавить контакт", href=f"/customers/{customer_id}/contacts/new",
                          style="color:#6366f1;font-size:12px;"),
                    ),
                    style="margin-bottom:12px;"
                ),
                # Category
                Div(
                    Label("Категория звонка", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Select(
                        Option("Не указана", value=""),
                        Option("Холодный", value="cold"),
                        Option("Тёплый", value="warm"),
                        Option("Входящий", value="incoming"),
                        name="call_category",
                        style=select_style,
                    ),
                    style="margin-bottom:12px;"
                ),
                # Comment
                Div(
                    Label("Комментарий / Суть звонка", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Textarea(name="comment", rows="3", placeholder="О чём был звонок...", style=f"{input_style} resize:vertical;"),
                    style="margin-bottom:12px;"
                ),
                # Customer needs
                Div(
                    Label("Потребление клиента / Зона ответственности контакта", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Textarea(name="customer_needs", rows="2", placeholder="Что интересует клиента...", style=f"{input_style} resize:vertical;"),
                    style="margin-bottom:12px;"
                ),
                # Meeting notes
                Div(
                    Label("Назначение встречи", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Textarea(name="meeting_notes", rows="2", placeholder="Договорённость о встрече...", style=f"{input_style} resize:vertical;"),
                    style="margin-bottom:16px;"
                ),
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn("Отмена", variant="ghost", type="button",
                        onclick="document.getElementById('call-modal-container').innerHTML=''"),
                    style="display:flex;gap:8px;"
                ),
                hx_post=f"/customers/{customer_id}/calls",
                hx_target="#calls-list",
                hx_swap="outerHTML",
            ),
            style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:24px;max-width:520px;width:90%;max-height:90vh;overflow-y:auto;"
        ),
        id="call-modal-overlay",
        style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;"
    )
    return form


# @rt("/customers/{customer_id}/calls")  # decorator removed; file is archived and not mounted
def post(session, customer_id: str,
         call_type: str = "call", call_category: str = "",
         scheduled_date: str = "", contact_person_id: str = "",
         comment: str = "", customer_needs: str = "", meeting_notes: str = ""):
    """Create a new call record for a customer, return updated calls list."""
    redirect = require_login(session)
    if redirect:
        return redirect
    if not user_has_any_role(session, ["admin", "sales", "sales_manager", "top_manager"]):
        return P("Доступ запрещён", style="color:red;")

    user = session["user"]
    user_id = user.get("id")
    org_id = user.get("org_id")

    from services.call_service import create_call, get_calls_for_customer

    result = create_call(
        organization_id=org_id,
        customer_id=customer_id,
        user_id=user_id,
        call_type=call_type,
        call_category=call_category or None,
        scheduled_date=scheduled_date or None,
        comment=comment or None,
        customer_needs=customer_needs or None,
        meeting_notes=meeting_notes or None,
        contact_person_id=contact_person_id or None,
    )

    if result is None:
        return P("Ошибка при сохранении звонка", style="color:red;")

    # Return fresh calls list + OOB swap to close modal
    calls = get_calls_for_customer(customer_id)
    return (_render_calls_list(customer_id, calls),
            Div(id="call-modal-container", hx_swap_oob="true"))


# @rt("/customers/{customer_id}/calls/{call_id}/edit-form")  # decorator removed; file is archived and not mounted
def get(session, customer_id: str, call_id: str):
    """HTMX partial - edit call form."""
    redirect = require_login(session)
    if redirect:
        return redirect
    if not user_has_any_role(session, ["admin", "sales", "sales_manager", "top_manager"]):
        return Div(P("Доступ запрещён"), style="color:red;")

    from services.call_service import get_call
    supabase = get_supabase()

    call = get_call(call_id)
    if not call:
        return Div(P("Запись не найдена"), style="color:red;")

    # Contacts
    try:
        contacts_resp = supabase.table("customer_contacts") \
            .select("id, name, position") \
            .eq("customer_id", customer_id) \
            .order("name") \
            .execute()
        contacts = contacts_resp.data or []
    except Exception:
        contacts = []

    contact_options = [Option("Не указан", value="")] + [
        Option(f"{c['name']}" + (f" ({c['position']})" if c.get('position') else ""),
               value=c['id'],
               selected=(c['id'] == call.contact_person_id))
        for c in contacts
    ]

    # Scheduled date formatted for datetime-local input
    scheduled_val = ""
    if call.scheduled_date:
        scheduled_val = call.scheduled_date.strftime("%Y-%m-%dT%H:%M")

    input_style = "width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;"
    select_style = "width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;background:#fff;"

    form = Div(
        Div(
            Div(
                H3("Редактировать звонок", style="margin:0;font-size:16px;font-weight:600;"),
                Button("✕",
                    onclick="document.getElementById('call-modal-container').innerHTML=''",
                    style="background:none;border:none;font-size:1.2rem;cursor:pointer;padding:4px;"),
                style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;"
            ),
            Form(
                Div(
                    Label("Тип *", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Select(
                        Option("Звонок", value="call", selected=(call.call_type == "call")),
                        Option("Запланировать звонок", value="scheduled", selected=(call.call_type == "scheduled")),
                        name="call_type",
                        style=select_style,
                        onchange="document.getElementById('edit-scheduled-date-row').style.display = this.value==='scheduled' ? 'block' : 'none';"
                    ),
                    style="margin-bottom:12px;"
                ),
                Div(
                    Label("Дата и время звонка *", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Input(name="scheduled_date", type="datetime-local", value=scheduled_val, style=input_style),
                    id="edit-scheduled-date-row",
                    style=f"margin-bottom:12px;display:{'block' if call.call_type == 'scheduled' else 'none'};"
                ),
                Div(
                    Label("Контактное лицо", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Select(*contact_options, name="contact_person_id", style=select_style),
                    style="margin-bottom:12px;"
                ),
                Div(
                    Label("Категория звонка", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Select(
                        Option("Не указана", value="", selected=(not call.call_category)),
                        Option("Холодный", value="cold", selected=(call.call_category == "cold")),
                        Option("Тёплый", value="warm", selected=(call.call_category == "warm")),
                        Option("Входящий", value="incoming", selected=(call.call_category == "incoming")),
                        name="call_category",
                        style=select_style,
                    ),
                    style="margin-bottom:12px;"
                ),
                Div(
                    Label("Комментарий / Суть звонка", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Textarea(call.comment or "", name="comment", rows="3", style=f"{input_style} resize:vertical;"),
                    style="margin-bottom:12px;"
                ),
                Div(
                    Label("Потребление клиента / Зона ответственности контакта", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Textarea(call.customer_needs or "", name="customer_needs", rows="2", style=f"{input_style} resize:vertical;"),
                    style="margin-bottom:12px;"
                ),
                Div(
                    Label("Назначение встречи", style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;"),
                    Textarea(call.meeting_notes or "", name="meeting_notes", rows="2", style=f"{input_style} resize:vertical;"),
                    style="margin-bottom:16px;"
                ),
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn("Отмена", variant="ghost", type="button",
                        onclick="document.getElementById('call-modal-container').innerHTML=''"),
                    style="display:flex;gap:8px;"
                ),
                hx_post=f"/customers/{customer_id}/calls/{call_id}/edit",
                hx_target="#calls-list",
                hx_swap="outerHTML",
            ),
            style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:24px;max-width:520px;width:90%;max-height:90vh;overflow-y:auto;"
        ),
        style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;"
    )
    return form


# @rt("/customers/{customer_id}/calls/{call_id}/edit")  # decorator removed; file is archived and not mounted
def post(session, customer_id: str, call_id: str,
         call_type: str = "call", call_category: str = "",
         scheduled_date: str = "", contact_person_id: str = "",
         comment: str = "", customer_needs: str = "", meeting_notes: str = ""):
    """Update a call record, return updated calls list."""
    redirect = require_login(session)
    if redirect:
        return redirect
    if not user_has_any_role(session, ["admin", "sales", "sales_manager", "top_manager"]):
        return P("Доступ запрещён", style="color:red;")

    user = session["user"]
    org_id = user.get("org_id")

    from services.call_service import get_call, update_call, get_calls_for_customer

    # Verify call belongs to user's organization (service uses service_role key, bypasses RLS)
    call = get_call(call_id)
    if not call or call.organization_id != org_id:
        return P("Запись не найдена", style="color:red;")

    update_call(
        call_id=call_id,
        call_type=call_type,
        call_category=call_category,
        scheduled_date=scheduled_date,
        comment=comment,
        customer_needs=customer_needs,
        meeting_notes=meeting_notes,
        contact_person_id=contact_person_id,
    )

    calls = get_calls_for_customer(customer_id)
    return (_render_calls_list(customer_id, calls),
            Div(id="call-modal-container", hx_swap_oob="true"))


# @rt("/customers/{customer_id}/calls/{call_id}")  # decorator removed; file is archived and not mounted
def delete(session, customer_id: str, call_id: str):
    """Delete a call record, return updated calls list."""
    redirect = require_login(session)
    if redirect:
        return redirect
    if not user_has_any_role(session, ["admin", "sales", "sales_manager", "top_manager"]):
        return P("Доступ запрещён", style="color:red;")

    user = session["user"]
    org_id = user.get("org_id")

    from services.call_service import get_call, delete_call, get_calls_for_customer

    # Verify call belongs to user's organization (service uses service_role key, bypasses RLS)
    call = get_call(call_id)
    if not call or call.organization_id != org_id:
        return P("Запись не найдена", style="color:red;")

    delete_call(call_id)
    calls = get_calls_for_customer(customer_id)
    return _render_calls_list(customer_id, calls)


# ============================================================================
# Customer Inline Editing
# ============================================================================

# @rt("/customers/{customer_id}/edit-field/{field_name}")  # decorator removed; file is archived and not mounted
def get(customer_id: str, field_name: str, session):
    """Return inline edit form for a specific field."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    # Map field names to labels and current values
    field_config = {
        "name": ("Название компании", customer.name, "text"),
        "inn": ("ИНН", customer.inn or "", "text"),
        "kpp": ("КПП", customer.kpp or "", "text"),
        "ogrn": ("ОГРН", customer.ogrn or "", "text"),
        "legal_address": ("Юридический адрес", customer.legal_address or "", "textarea"),
        "actual_address": ("Фактический адрес", customer.actual_address or "", "textarea"),
        "postal_address": ("Почтовый адрес", customer.postal_address or "", "textarea"),
        "order_source": ("Источник заказа", customer.order_source or "", "select"),
    }

    if field_name not in field_config:
        return Div("Неизвестное поле")

    label, value, input_type = field_config[field_name]

    # Style for modern inline editing
    input_style = "padding: 0.5rem 0.75rem; border: 2px solid #3b82f6; border-radius: 0.375rem; font-size: inherit; outline: none;"
    form_id = f"customer-field-form-{field_name}"

    # Key handlers: Enter to click hidden submit button, Escape to cancel
    esc_handler = "if(event.key === 'Escape') { event.preventDefault(); htmx.ajax('GET', '" + f"/customers/{customer_id}/cancel-edit/{field_name}" + "', {target: '#field-" + field_name + "', swap: 'outerHTML'}); }"
    key_handler = f"if(event.key === 'Enter' && !event.shiftKey) {{ event.preventDefault(); document.querySelector('#{form_id} button[type=submit]').click(); }} else " + esc_handler

    if input_type == "textarea":
        # Textarea: Escape cancels, Enter+Shift for newline, just Enter doesn't save (use button)
        input_elem = Textarea(
            value, name=field_name,
            autofocus=True,
            style=input_style + " width: 100%; min-height: 80px; font-family: inherit;",
            required=True if field_name == "name" else False,
            onkeydown=esc_handler
        )
    elif input_type == "select":
        # Select dropdown: auto-submit on change, Escape cancels
        select_options = [Option("— Не указан —", value="")]
        if field_name == "order_source":
            for opt_val, opt_label in ORDER_SOURCE_OPTIONS:
                select_options.append(Option(opt_label, value=opt_val, selected=(opt_val == value)))
        input_elem = Select(
            *select_options,
            name=field_name,
            autofocus=True,
            style=input_style + " flex: 1; cursor: pointer;",
            onchange=f"this.form.querySelector('button[type=submit]').click();",
            onkeydown=esc_handler,
        )
    else:
        # Input: Enter saves, Escape cancels
        input_elem = Input(
            value=value, name=field_name,
            autofocus=True,
            style=input_style + " flex: 1;",
            required=True if field_name == "name" else False,
            onkeydown=key_handler
        )

    return Form(
        Div(
            input_elem,
            Button(type="submit", style="position: absolute; left: -9999px; width: 1px; height: 1px;"),  # Offscreen submit button
            id=f"field-{field_name}"
        ),
        id=form_id,
        hx_post=f"/customers/{customer_id}/update-field/{field_name}",
        hx_target=f"#field-{field_name}",
        hx_swap="outerHTML"
    )


# @rt("/customers/{customer_id}/update-field/{field_name}")  # decorator removed; file is archived and not mounted
async def post(customer_id: str, field_name: str, session, request):
    """Update a specific field via inline editing."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    from services.customer_service import get_customer, update_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    # Verify customer belongs to user's organization
    if customer.organization_id != user["org_id"]:
        return Div("Клиент не найден", id=f"field-{field_name}")

    # Get form data
    form_data = await request.form()
    new_value = form_data.get(field_name, "")

    # For select fields, store None instead of empty string
    if new_value == "" and field_name == "order_source":
        new_value = None

    # Update customer
    if field_name == "order_source":
        # Direct update for nullable select fields (update_customer treats None as "don't change")
        try:
            supabase = get_supabase()
            supabase.table("customers").update({"order_source": new_value}).eq("id", customer_id).eq("organization_id", user["org_id"]).execute()
            success = True
        except Exception:
            success = False
    else:
        update_data = {field_name: new_value}
        success = update_customer(customer_id, **update_data)

    if not success:
        return Div("Ошибка обновления", id=f"field-{field_name}")

    # Return updated display
    return _render_field_display(customer_id, field_name, new_value or "")


# @rt("/customers/{customer_id}/cancel-edit/{field_name}")  # decorator removed; file is archived and not mounted
def get(customer_id: str, field_name: str, session):
    """Cancel inline editing and return to display mode."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    from services.customer_service import get_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    # Verify customer belongs to user's organization
    if customer.organization_id != user["org_id"]:
        return Div("Клиент не найден", id=f"field-{field_name}")

    # Get current value
    value = getattr(customer, field_name, "")

    return _render_field_display(customer_id, field_name, value)


def _render_field_display(customer_id: str, field_name: str, value: str):
    """Helper function to render field in display mode with modern inline edit."""
    # Translate select field values to human-readable labels
    if field_name == "order_source" and value:
        display_value = ORDER_SOURCE_LABELS.get(value, value)
    else:
        display_value = value if value else "Не указан"
    # Use consistent dark gray for filled values, lighter gray for empty
    display_color = "#6b7280" if not value else "#374151"

    # Special formatting for name field
    if field_name == "name":
        font_style = "font-size: 1.1em; font-weight: 500;"
    else:
        font_style = ""

    return Div(
        display_value,
        id=f"field-{field_name}",
        hx_get=f"/customers/{customer_id}/edit-field/{field_name}",
        hx_target=f"#field-{field_name}",
        hx_swap="outerHTML",
        style=f"cursor: pointer; padding: 0.5rem 0.75rem; border-radius: 0.375rem; transition: background 0.15s ease; color: {display_color}; {font_style}",
        onmouseover="this.style.background='#f3f4f6'",
        onmouseout="this.style.background='transparent'",
        title="Кликните для редактирования"
    )


def _render_notes_display(customer_id: str, value: str):
    """Helper function to render notes field in display mode with inline edit."""
    display_value = value if value else "Нажмите чтобы добавить заметки..."
    display_color = "#64748b" if not value else "#e2e8f0"

    return Div(
        Pre(display_value, style="white-space: pre-wrap; margin: 0; font-family: inherit;") if value else Span(display_value, style="font-style: italic;"),
        id="field-notes",
        hx_get=f"/customers/{customer_id}/edit-notes",
        hx_target="#field-notes",
        hx_swap="outerHTML",
        style=f"cursor: pointer; padding: 1rem; border-radius: 0.5rem; transition: background 0.15s ease; color: {display_color}; min-height: 100px; background: rgba(255,255,255,0.03);",
        onmouseover="this.style.background='rgba(255,255,255,0.08)'",
        onmouseout="this.style.background='rgba(255,255,255,0.03)'",
        title="Кликните для редактирования"
    )


# @rt("/customers/{customer_id}/edit-notes")  # decorator removed; file is archived and not mounted
def get(customer_id: str, session):
    """Return inline edit form for notes field."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    return Form(
        Div(
            Textarea(
                customer.notes or "",
                name="notes",
                autofocus=True,
                style="width: 100%; min-height: 150px; padding: 0.75rem; border: 2px solid #3b82f6; border-radius: 0.5rem; font-family: inherit; font-size: inherit; background: #1e1e2f; color: #e2e8f0; resize: vertical;",
                placeholder="Введите заметки о клиенте...",
                onkeydown="if(event.key === 'Escape') { event.target.form.querySelector('.cancel-btn').click(); }"
            ),
            Div(
                btn("Сохранить", variant="success", icon_name="check", type="submit", size="sm"),
                btn("Отмена", variant="danger", size="sm", type="button",
                    cls="cancel-btn",
                    hx_get=f"/customers/{customer_id}/cancel-edit-notes",
                    hx_target="#field-notes",
                    hx_swap="outerHTML"),
                style="display: flex; gap: 0.5rem; margin-top: 0.75rem;"
            ),
            id="field-notes"
        ),
        hx_post=f"/customers/{customer_id}/update-notes",
        hx_target="#field-notes",
        hx_swap="outerHTML"
    )


# @rt("/customers/{customer_id}/update-notes")  # decorator removed; file is archived and not mounted
async def post(customer_id: str, session, request):
    """Update notes field via inline editing."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_customer, update_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    # Get form data
    form_data = await request.form()
    new_value = form_data.get("notes", "")

    # Update customer
    success = update_customer(customer_id, notes=new_value)

    if not success:
        return Div("Ошибка обновления", id="field-notes")

    # Return updated display
    return _render_notes_display(customer_id, new_value)


# @rt("/customers/{customer_id}/cancel-edit-notes")  # decorator removed; file is archived and not mounted
def get(customer_id: str, session):
    """Cancel inline editing of notes and return to display mode."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    return _render_notes_display(customer_id, customer.notes or "")


# ============================================================================
# Contact Inline Editing
# ============================================================================

def _render_contact_field(contact_id: str, customer_id: str, field_name: str, value: str, is_link: bool = False):
    """Helper function to render a contact field with inline editing capability."""
    display_value = value if value else "—"

    # For email/phone links
    if is_link and value:
        if field_name == "email":
            content = A(value, href=f"mailto:{value}", style="color: #3b82f6; text-decoration: none;")
        elif field_name == "phone":
            content = A(value, href=f"tel:{value}", style="color: #3b82f6; text-decoration: none;")
        else:
            content = display_value
    else:
        content = display_value

    return Td(
        Div(
            content,
            id=f"contact-{contact_id}-{field_name}",
            hx_get=f"/customers/{customer_id}/contacts/{contact_id}/edit-field/{field_name}",
            hx_target=f"#contact-{contact_id}-{field_name}",
            hx_swap="outerHTML",
            style="cursor: pointer; padding: 0.25rem 0.5rem; border-radius: 0.25rem; transition: background 0.15s ease; min-width: 60px;",
            onmouseover="this.style.background='#f3f4f6'",
            onmouseout="this.style.background='transparent'",
            title="Кликните для редактирования"
        )
    )


def _render_contact_name_cell(contact, customer_id: str):
    """Render the name cell with full name (Фамилия Имя Отчество), ЛПР badge, and inline editing."""
    # Build full name: Фамилия Имя Отчество
    name_parts = []
    if contact.last_name:
        name_parts.append(contact.last_name)
    if contact.name:
        name_parts.append(contact.name)
    if contact.patronymic:
        name_parts.append(contact.patronymic)
    full_name = " ".join(name_parts) if name_parts else "—"

    # Build name content with optional ЛПР badge
    name_content = [Strong(full_name)]
    if contact.is_lpr:
        name_content.append(Span("ЛПР", style="margin-left: 0.5rem; background: #dbeafe; color: #1d4ed8; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600;"))

    return Td(
        Div(
            *name_content,
            id=f"contact-{contact.id}-name",
            hx_get=f"/customers/{customer_id}/contacts/{contact.id}/edit-field/name",
            hx_target=f"#contact-{contact.id}-name",
            hx_swap="outerHTML",
            style="cursor: pointer; padding: 0.25rem 0.5rem; border-radius: 0.25rem; transition: background 0.15s ease;",
            onmouseover="this.style.background='#f3f4f6'",
            onmouseout="this.style.background='transparent'",
            title="Кликните для редактирования"
        )
    )


def _render_contact_flags_cell(contact, customer_id: str):
    """Render the flags cell (signatory, primary, LPR) with minimal clickable icons."""
    # Colors: green for signatory, orange for primary, blue for LPR, darker gray for inactive
    signatory_color = "#10b981" if contact.is_signatory else "#6b7280"
    primary_color = "#f59e0b" if contact.is_primary else "#6b7280"
    lpr_color = "#3b82f6" if contact.is_lpr else "#6b7280"

    # Use Span with HTMX instead of Button to avoid global button styling
    return Td(
        Div(
            Span(
                icon("pen-tool", size=18),
                hx_post=f"/customers/{customer_id}/contacts/{contact.id}/toggle-signatory",
                hx_target="#contacts-tbody",
                hx_swap="innerHTML",
                style=f"color: {signatory_color}; cursor: pointer; padding: 6px; display: inline-flex; border-radius: 4px; transition: background 0.15s;",
                title="Подписант" if contact.is_signatory else "Сделать подписантом",
                onmouseover="this.style.background='#f3f4f6'",
                onmouseout="this.style.background='transparent'"
            ),
            Span(
                icon("star", size=18),
                hx_post=f"/customers/{customer_id}/contacts/{contact.id}/toggle-primary",
                hx_target="#contacts-tbody",
                hx_swap="innerHTML",
                style=f"color: {primary_color}; cursor: pointer; padding: 6px; display: inline-flex; border-radius: 4px; transition: background 0.15s;",
                title="Основной контакт" if contact.is_primary else "Сделать основным",
                onmouseover="this.style.background='#f3f4f6'",
                onmouseout="this.style.background='transparent'"
            ),
            Span(
                icon("user-check", size=18),
                hx_post=f"/customers/{customer_id}/contacts/{contact.id}/toggle-lpr",
                hx_target="#contacts-tbody",
                hx_swap="innerHTML",
                style=f"color: {lpr_color}; cursor: pointer; padding: 6px; display: inline-flex; border-radius: 4px; transition: background 0.15s;",
                title="ЛПР (лицо, принимающее решения)" if contact.is_lpr else "Сделать ЛПР",
                onmouseover="this.style.background='#f3f4f6'",
                onmouseout="this.style.background='transparent'"
            ),
            style="display: flex; align-items: center; gap: 8px;"
        ),
        cls="col-actions"
    )


def _render_contact_row(contact, customer_id: str):
    """Render a single contact row with inline editing."""
    return Tr(
        _render_contact_name_cell(contact, customer_id),
        _render_contact_field(contact.id, customer_id, "position", contact.position or ""),
        _render_contact_field(contact.id, customer_id, "email", contact.email or "", is_link=True),
        _render_contact_field(contact.id, customer_id, "phone", contact.phone or "", is_link=True),
        _render_contact_field(contact.id, customer_id, "notes", (contact.notes[:50] + "..." if contact.notes and len(contact.notes) > 50 else contact.notes) or ""),
        _render_contact_flags_cell(contact, customer_id),
        id=f"contact-row-{contact.id}"
    )


# @rt("/customers/{customer_id}/contacts/{contact_id}/edit-field/{field_name}")  # decorator removed; file is archived and not mounted
def get(customer_id: str, contact_id: str, field_name: str, session):
    """Return inline edit form for a contact field."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_contact

    contact = get_contact(contact_id)
    if not contact:
        return Div("Контакт не найден", id=f"contact-{contact_id}-{field_name}")

    # Blur handler for save on click outside
    blur_save = "setTimeout(() => { if(this.form && document.contains(this)) this.form.requestSubmit(); }, 150)"
    cancel_url = f"/customers/{customer_id}/contacts/{contact_id}/cancel-edit/{field_name}"

    # Get current value based on field
    if field_name == "name":
        # For name, we edit all three parts: last_name, name, patronymic
        # Key handlers: Enter to click hidden submit button, Escape to cancel
        form_id = f"contact-name-form-{contact_id}"
        key_handler = f"if(event.key === 'Enter') {{ event.preventDefault(); document.querySelector('#{form_id} button[type=submit]').click(); }} else if(event.key === 'Escape') {{ event.preventDefault(); htmx.ajax('GET', '{cancel_url}', {{target: '#contact-{contact_id}-{field_name}', swap: 'outerHTML'}}); }}"
        input_style = "padding: 0.35rem 0.5rem; border: 2px solid #3b82f6; border-radius: 0.25rem;"

        return Div(
            Form(
                Div(
                    Input(type="text", name="last_name", value=contact.last_name or "", placeholder="Фамилия",
                          style=input_style + " width: 90px; margin-right: 0.25rem;",
                          onkeydown=key_handler),
                    Input(type="text", name="name", value=contact.name or "", placeholder="Имя", required=True,
                          style=input_style + " width: 70px; margin-right: 0.25rem;", autofocus=True,
                          onkeydown=key_handler),
                    Input(type="text", name="patronymic", value=contact.patronymic or "", placeholder="Отчество",
                          style=input_style + " width: 90px;",
                          onkeydown=key_handler),
                    Button(type="submit", style="position: absolute; left: -9999px; width: 1px; height: 1px;"),  # Offscreen submit button
                    style="display: flex; align-items: center; gap: 0.25rem;"
                ),
                id=form_id,
                hx_post=f"/customers/{customer_id}/contacts/{contact_id}/update-field/{field_name}",
                hx_target=f"#contact-row-{contact_id}",
                hx_swap="outerHTML"
            ),
            id=f"contact-{contact_id}-{field_name}",
            style="padding: 0.25rem;"
        )
    else:
        current_value = getattr(contact, field_name, "") or ""

        # Determine input type
        if field_name == "email":
            input_type = "email"
            placeholder = "email@example.com"
        elif field_name == "phone":
            input_type = "tel"
            placeholder = "+7 (999) 123-45-67"
        elif field_name == "notes":
            input_type = "text"
            placeholder = "Заметки..."
        else:
            input_type = "text"
            placeholder = ""

        # Key handlers: Enter to click hidden submit button, Escape to cancel
        form_id = f"contact-field-form-{contact_id}-{field_name}"
        key_handler = f"if(event.key === 'Enter') {{ event.preventDefault(); document.querySelector('#{form_id} button[type=submit]').click(); }} else if(event.key === 'Escape') {{ event.preventDefault(); htmx.ajax('GET', '{cancel_url}', {{target: '#contact-{contact_id}-{field_name}', swap: 'outerHTML'}}); }}"

        return Div(
            Form(
                Input(type=input_type, name=field_name, value=current_value, placeholder=placeholder,
                      style="padding: 0.35rem 0.5rem; border: 2px solid #3b82f6; border-radius: 0.25rem; width: 150px;", autofocus=True,
                      onkeydown=key_handler),
                Button(type="submit", style="position: absolute; left: -9999px; width: 1px; height: 1px;"),  # Offscreen submit button
                id=form_id,
                hx_post=f"/customers/{customer_id}/contacts/{contact_id}/update-field/{field_name}",
                hx_target=f"#contact-{contact_id}-{field_name}",
                hx_swap="outerHTML"
            ),
            id=f"contact-{contact_id}-{field_name}",
            style="padding: 0.25rem;"
        )


# @rt("/customers/{customer_id}/contacts/{contact_id}/update-field/{field_name}")  # decorator removed; file is archived and not mounted
async def post(customer_id: str, contact_id: str, field_name: str, session, request):
    """Update a contact field via inline editing."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_contact, update_contact

    contact = get_contact(contact_id)
    if not contact:
        return Div("Контакт не найден", id=f"contact-{contact_id}-{field_name}")

    # Get form data
    form_data = await request.form()

    try:
        if field_name == "name":
            # Update all name parts
            last_name = form_data.get("last_name", "")
            name = form_data.get("name", "")
            patronymic = form_data.get("patronymic", "")

            updated_contact = update_contact(contact_id, name=name, last_name=last_name, patronymic=patronymic)
        else:
            new_value = form_data.get(field_name, "")
            kwargs = {field_name: new_value}
            updated_contact = update_contact(contact_id, **kwargs)

        if not updated_contact:
            return Div("Ошибка обновления", id=f"contact-{contact_id}-{field_name}")

        # For name field, return the full row
        if field_name == "name":
            return _render_contact_row(updated_contact, customer_id)

        # For other fields, return just the updated cell content
        is_link = field_name in ("email", "phone")
        value = getattr(updated_contact, field_name, "") or ""
        if field_name == "notes" and value and len(value) > 50:
            value = value[:50] + "..."

        display_value = value if value else "—"

        if is_link and value:
            if field_name == "email":
                content = A(value, href=f"mailto:{value}", style="color: #3b82f6; text-decoration: none;")
            elif field_name == "phone":
                content = A(value, href=f"tel:{value}", style="color: #3b82f6; text-decoration: none;")
            else:
                content = display_value
        else:
            content = display_value

        return Div(
            content,
            id=f"contact-{contact_id}-{field_name}",
            hx_get=f"/customers/{customer_id}/contacts/{contact_id}/edit-field/{field_name}",
            hx_target=f"#contact-{contact_id}-{field_name}",
            hx_swap="outerHTML",
            style="cursor: pointer; padding: 0.25rem 0.5rem; border-radius: 0.25rem; transition: background 0.15s ease; min-width: 60px;",
            onmouseover="this.style.background='#f3f4f6'",
            onmouseout="this.style.background='transparent'",
            title="Кликните для редактирования"
        )

    except ValueError as e:
        return Div(str(e), id=f"contact-{contact_id}-{field_name}", style="color: red; padding: 0.25rem 0.5rem;")


# @rt("/customers/{customer_id}/contacts/{contact_id}/cancel-edit/{field_name}")  # decorator removed; file is archived and not mounted
def get(customer_id: str, contact_id: str, field_name: str, session):
    """Cancel inline editing of a contact field."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_contact

    contact = get_contact(contact_id)
    if not contact:
        return Div("Контакт не найден", id=f"contact-{contact_id}-{field_name}")

    if field_name == "name":
        # Return the name cell with badges
        badges = []
        if contact.is_lpr:
            badges.append(Span("ЛПР", style="margin-left: 0.5rem; background: #dbeafe; color: #1d4ed8; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600;"))
        if contact.is_signatory:
            badges.append(Span(icon("pen-tool", size=12), " Подписант", cls="status-badge status-approved", style="margin-left: 0.5rem; display: inline-flex; align-items: center; gap: 0.25rem;"))
        if contact.is_primary:
            badges.append(Span("★ Основной", cls="status-badge status-pending", style="margin-left: 0.5rem;"))

        return Div(
            Div(
                Strong(contact.get_full_name()),
                *badges,
                style="display: flex; align-items: center; flex-wrap: wrap;"
            ),
            id=f"contact-{contact.id}-name",
            hx_get=f"/customers/{customer_id}/contacts/{contact.id}/edit-field/name",
            hx_target=f"#contact-{contact.id}-name",
            hx_swap="outerHTML",
            style="cursor: pointer; padding: 0.25rem 0.5rem; border-radius: 0.25rem; transition: background 0.15s ease;",
            onmouseover="this.style.background='#f3f4f6'",
            onmouseout="this.style.background='transparent'",
            title="Кликните для редактирования"
        )

    # For other fields
    is_link = field_name in ("email", "phone")
    value = getattr(contact, field_name, "") or ""
    if field_name == "notes" and value and len(value) > 50:
        value = value[:50] + "..."

    display_value = value if value else "—"

    if is_link and value:
        if field_name == "email":
            content = A(value, href=f"mailto:{value}", style="color: #3b82f6; text-decoration: none;")
        elif field_name == "phone":
            content = A(value, href=f"tel:{value}", style="color: #3b82f6; text-decoration: none;")
        else:
            content = display_value
    else:
        content = display_value

    return Div(
        content,
        id=f"contact-{contact_id}-{field_name}",
        hx_get=f"/customers/{customer_id}/contacts/{contact_id}/edit-field/{field_name}",
        hx_target=f"#contact-{contact_id}-{field_name}",
        hx_swap="outerHTML",
        style="cursor: pointer; padding: 0.25rem 0.5rem; border-radius: 0.25rem; transition: background 0.15s ease; min-width: 60px;",
        onmouseover="this.style.background='#f3f4f6'",
        onmouseout="this.style.background='transparent'",
        title="Кликните для редактирования"
    )


# @rt("/customers/{customer_id}/contacts/{contact_id}/toggle-signatory")  # decorator removed; file is archived and not mounted
def post(customer_id: str, contact_id: str, session):
    """Toggle signatory status for a contact. Returns all contacts to show unique signatory."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_contact, update_contact, get_customer_with_contacts

    contact = get_contact(contact_id)
    if not contact:
        return Tr(Td("Контакт не найден", colspan="6"))

    # Toggle signatory status (backend will unset other signatories if setting to true)
    new_status = not contact.is_signatory
    update_contact(contact_id, is_signatory=new_status)

    # Re-fetch all contacts to show updated state (including unset signatory on other contacts)
    customer = get_customer_with_contacts(customer_id)
    if customer and customer.contacts:
        return tuple(_render_contact_row(c, customer_id) for c in customer.contacts)
    return Tr(Td("Контакты не найдены", colspan="6"))


# @rt("/customers/{customer_id}/contacts/{contact_id}/toggle-primary")  # decorator removed; file is archived and not mounted
def post(customer_id: str, contact_id: str, session):
    """Toggle primary status for a contact. Returns all contacts to show unique primary."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_contact, update_contact, get_customer_with_contacts

    contact = get_contact(contact_id)
    if not contact:
        return Tr(Td("Контакт не найден", colspan="6"))

    # Toggle primary status (backend will unset other primaries if setting to true)
    new_status = not contact.is_primary
    update_contact(contact_id, is_primary=new_status)

    # Re-fetch all contacts to show updated state (including unset primary on other contacts)
    customer = get_customer_with_contacts(customer_id)
    if customer and customer.contacts:
        return tuple(_render_contact_row(c, customer_id) for c in customer.contacts)
    return Tr(Td("Контакты не найдены", colspan="6"))


# @rt("/customers/{customer_id}/contacts/{contact_id}/toggle-lpr")  # decorator removed; file is archived and not mounted
def post(customer_id: str, contact_id: str, session):
    """Toggle LPR (decision maker) status for a contact. Multiple contacts can be LPR."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_contact, update_contact, get_customer_with_contacts

    contact = get_contact(contact_id)
    if not contact:
        return Tr(Td("Контакт не найден", colspan="6"))

    # Toggle LPR status (multiple contacts can be LPR, no need to unset others)
    new_status = not contact.is_lpr
    update_contact(contact_id, is_lpr=new_status)

    # Re-fetch all contacts to show updated state
    customer = get_customer_with_contacts(customer_id)
    if customer and customer.contacts:
        return tuple(_render_contact_row(c, customer_id) for c in customer.contacts)
    return Tr(Td("Контакты не найдены", colspan="6"))


# ============================================================================
# Customer Warehouse Addresses Management
# ============================================================================

# @rt("/customers/{customer_id}/warehouses/add")  # decorator removed; file is archived and not mounted
def get(customer_id: str, session):
    """Return form to add new warehouse address."""
    redirect = require_login(session)
    if redirect:
        return redirect

    return Form(
        Input(type="text", name="warehouse_address", placeholder="Введите адрес склада",
              style="width: 100%; padding: 0.5rem; border: 2px solid #3b82f6; border-radius: 0.375rem;", required=True),
        Div(
            btn("Добавить", variant="success", icon_name="check", type="submit", size="sm"),
            btn("Отмена", variant="danger", size="sm", type="button",
                hx_get=f"/customers/{customer_id}/warehouses/cancel-add",
                hx_target="#add-warehouse-form",
                hx_swap="outerHTML"),
            style="display: flex; gap: 0.5rem; margin-top: 0.5rem;"
        ),
        hx_post=f"/customers/{customer_id}/warehouses/add",
        hx_target="#warehouses-list",
        hx_swap="outerHTML",
        id="add-warehouse-form",
        style="margin-bottom: 1rem;"
    )


# @rt("/customers/{customer_id}/warehouses/add")  # decorator removed; file is archived and not mounted
async def post(customer_id: str, session, request):
    """Add new warehouse address."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_customer, update_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    # Get form data
    form_data = await request.form()
    new_address = form_data.get("warehouse_address", "").strip()

    if not new_address:
        return _render_warehouses_list(customer_id, customer.warehouse_addresses or [])

    # Add to warehouse addresses
    warehouses = customer.warehouse_addresses or []
    warehouses.append(new_address)

    # Update customer
    update_customer(customer_id, warehouse_addresses=warehouses)

    return _render_warehouses_list(customer_id, warehouses)


# @rt("/customers/{customer_id}/warehouses/cancel-add")  # decorator removed; file is archived and not mounted
def get(customer_id: str, session):
    """Cancel adding warehouse address."""
    redirect = require_login(session)
    if redirect:
        return redirect

    return btn("Добавить адрес склада", variant="secondary", icon_name="plus", type="button",
               hx_get=f"/customers/{customer_id}/warehouses/add",
               hx_target="#add-warehouse-form",
               hx_swap="outerHTML",
               id="add-warehouse-form")


# @rt("/customers/{customer_id}/warehouses/delete/{index}")  # decorator removed; file is archived and not mounted
def post(customer_id: str, index: int, session):
    """Delete warehouse address by index."""
    redirect = require_login(session)
    if redirect:
        return redirect

    from services.customer_service import get_customer, update_customer

    customer = get_customer(customer_id)
    if not customer:
        return Div("Клиент не найден")

    warehouses = customer.warehouse_addresses or []
    if 0 <= index < len(warehouses):
        warehouses.pop(index)
        update_customer(customer_id, warehouse_addresses=warehouses)

    return _render_warehouses_list(customer_id, warehouses)


def _render_warehouses_list(customer_id: str, warehouses: list):
    """Helper function to render warehouses list."""
    warehouse_items = []
    for i, addr in enumerate(warehouses):
        warehouse_items.append(
            Li(
                Span(addr, style="flex: 1;"),
                btn("Удалить", variant="danger", icon_name="trash-2", size="sm", type="button",
                    hx_post=f"/customers/{customer_id}/warehouses/delete/{i}",
                    hx_target="#warehouses-list",
                    hx_swap="outerHTML",
                    hx_confirm="Удалить этот адрес склада?"),
                style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;"
            )
        )

    return Div(
        Ul(*warehouse_items, style="padding-left: 1.5rem; list-style: none;") if warehouse_items else Div("Нет адресов складов", style="color: #999; font-style: italic;"),
        id="warehouses-list"
    )


# ============================================================================
# Customer Contacts - New Contact
# ============================================================================

# @rt("/customers/{customer_id}/contacts/new")  # decorator removed; file is archived and not mounted
def get(session, customer_id: str):
    """Add new contact for a customer."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check if user has sales or admin role
    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()
    user = session["user"]

    # Get customer info
    customer_result = supabase.table("customers") \
        .select("id, name, inn") \
        .eq("id", customer_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not customer_result.data:
        return page_layout("Клиент не найден",
            H1("Клиент не найден"),
            P("Запрошенный клиент не найден или у вас нет доступа."),
            A("← Назад к клиентам", href="/customers"),
            session=session
        )

    customer = customer_result.data[0]

    return page_layout("Добавить контакт",
        H1(f"Добавить контакт для {customer['name']}"),
        Div(
            Form(
                Div(
                    Label("Фамилия *", Input(name="last_name", required=True, placeholder="Иванов")),
                    Label("Имя *", Input(name="name", required=True, placeholder="Иван")),
                    Label("Отчество", Input(name="patronymic", placeholder="Иванович")),
                    cls="form-row", style="grid-template-columns: repeat(3, 1fr);"
                ),
                Div(
                    Label("Должность", Input(name="position", placeholder="Директор")),
                    cls="form-row"
                ),
                Div(
                    Label("Email", Input(name="email", type="email", placeholder="ivanov@company.ru")),
                    Label("Телефон", Input(name="phone", placeholder="+7 999 123 4567")),
                    cls="form-row"
                ),
                Div(
                    Label(
                        Input(type="checkbox", name="is_primary", value="true"),
                        " ★ Основной контакт (для основной коммуникации)",
                        style="display: flex; align-items: center; gap: 0.5rem;"
                    ),
                    Label(
                        Input(type="checkbox", name="is_signatory", value="true"),
                        icon("pen-tool", size=12), " Подписант (имя будет в спецификациях PDF)",
                        style="display: flex; align-items: center; gap: 0.5rem;"
                    ),
                    Label(
                        Input(type="checkbox", name="is_lpr", value="true"),
                        icon("user-check", size=12), " ЛПР (лицо, принимающее решения)",
                        style="display: flex; align-items: center; gap: 0.5rem;"
                    ),
                    cls="form-row"
                ),
                Label("Заметки", Textarea(name="notes", placeholder="Дополнительная информация о контакте", rows="3")),
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href=f"/customers/{customer_id}", variant="secondary"),
                    cls="form-actions"
                ),
                method="post",
                action=f"/customers/{customer_id}/contacts/new"
            ),
            cls="card"
        ),
        session=session
    )


# @rt("/customers/{customer_id}/contacts/new")  # decorator removed; file is archived and not mounted
def post(session, customer_id: str, name: str, last_name: str = "", patronymic: str = "",
         position: str = "", email: str = "", phone: str = "",
         is_primary: str = "", is_signatory: str = "", is_lpr: str = "", notes: str = ""):
    """Create new contact for a customer."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check if user has sales or admin role
    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()
    user = session["user"]

    # Verify customer exists and user has access
    customer_result = supabase.table("customers") \
        .select("id, name") \
        .eq("id", customer_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not customer_result.data:
        return RedirectResponse("/customers", status_code=303)

    customer = customer_result.data[0]

    try:
        # Combine name parts into full name: "Surname Name Patronymic"
        # Form has: last_name (Фамилия), name (Имя), patronymic (Отчество)
        full_name_parts = [last_name, name, patronymic]
        full_name = " ".join(p.strip() for p in full_name_parts if p and p.strip())

        # Check for duplicate contact (same name for same customer)
        existing = supabase.table("customer_contacts") \
            .select("id, name") \
            .eq("customer_id", customer_id) \
            .eq("name", full_name) \
            .limit(1) \
            .execute()

        if existing.data:
            return page_layout("Добавить контакт",
                Div(f"Контакт «{full_name}» уже существует у данного клиента.",
                    style="background: #fef3c7; border: 1px solid #f59e0b; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; color: #92400e;"),
                H1(f"Добавить контакт для {customer['name']}"),
                Div(
                    btn_link("← Назад к клиенту", href=f"/customers/{customer_id}?tab=contacts", variant="secondary", icon_name="arrow-left"),
                    style="margin-top: 1rem;"
                ),
                session=session
            )

        # Insert new contact
        result = supabase.table("customer_contacts").insert({
            "customer_id": customer_id,
            "organization_id": user["org_id"],
            "name": full_name,  # Combined: "Рахал Мамут Иванович"
            "position": position or None,
            "email": email or None,
            "phone": phone or None,
            "is_primary": is_primary == "true",
            "is_signatory": is_signatory == "true",
            "is_lpr": is_lpr == "true",
            "notes": notes or None
        }).execute()

        return RedirectResponse(f"/customers/{customer_id}", status_code=303)

    except Exception as e:
        error_msg = f"Ошибка при создании контакта: {str(e)}"

        return page_layout("Добавить контакт",
            Div(error_msg, style="background: #fee; border: 1px solid #c33; padding: 1rem; margin-bottom: 1rem; border-radius: 4px;"),
            H1(f"Добавить контакт для {customer['name']}"),
            Div(
                Form(
                    Div(
                        Label("Фамилия *", Input(name="last_name", required=True, placeholder="Иванов", value=last_name)),
                        Label("Имя *", Input(name="name", required=True, placeholder="Иван", value=name)),
                        Label("Отчество", Input(name="patronymic", placeholder="Иванович", value=patronymic)),
                        cls="form-row", style="grid-template-columns: repeat(3, 1fr);"
                    ),
                    Div(
                        Label("Должность", Input(name="position", placeholder="Директор", value=position)),
                        cls="form-row"
                    ),
                    Div(
                        Label("Email", Input(name="email", type="email", placeholder="ivanov@company.ru", value=email)),
                        Label("Телефон", Input(name="phone", placeholder="+7 999 123 4567", value=phone)),
                        cls="form-row"
                    ),
                    Div(
                        Label(
                            Input(type="checkbox", name="is_primary", value="true", checked=is_primary=="true"),
                            " ★ Основной контакт (для основной коммуникации)",
                            style="display: flex; align-items: center; gap: 0.5rem;"
                        ),
                        Label(
                            Input(type="checkbox", name="is_signatory", value="true", checked=is_signatory=="true"),
                            icon("pen-tool", size=12), " Подписант (имя будет в спецификациях PDF)",
                            style="display: flex; align-items: center; gap: 0.5rem;"
                        ),
                        Label(
                            Input(type="checkbox", name="is_lpr", value="true", checked=is_lpr=="true"),
                            icon("user-check", size=12), " ЛПР (лицо, принимающее решения)",
                            style="display: flex; align-items: center; gap: 0.5rem;"
                        ),
                        cls="form-row"
                    ),
                    Label("Заметки", Textarea(name="notes", placeholder="Дополнительная информация о контакте", rows="3", value=notes)),
                    Div(
                        btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                        btn_link("Отмена", href=f"/customers/{customer_id}", variant="secondary"),
                        cls="form-actions"
                    ),
                    method="post",
                    action=f"/customers/{customer_id}/contacts/new"
                ),
                cls="card"
            ),
            session=session
        )
