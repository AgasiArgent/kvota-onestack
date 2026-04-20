"""FastHTML /calls + /documents + /customer-contracts areas — archived 2026-04-20 during Phase 6C-2B-10a.

Three independent areas combined in one archive file because none had a Next.js
replacement at the time of archival (per user directive 2026-04-20) and each
area is small enough to co-locate without ambiguity. Routes unreachable
post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru, which doesn't proxy
these paths back to this Python container.

Contents (10 @rt routes, NO exclusive helpers):

AREA 1: /customer-contracts (4 @rt)
  - GET  /customer-contracts                       — Registry with search + filters
  - GET  /customer-contracts/new                   — Create form
  - POST /customer-contracts/new                   — Create submit
  - GET  /customer-contracts/{contract_id}         — Detail view

AREA 2: /documents (5 @rt)
  - POST   /documents/upload/{entity_type}/{entity_id}  — Upload + hierarchical binding
  - GET    /documents/{document_id}/download           — 302 to signed storage URL
  - GET    /documents/{document_id}/view               — 302 to signed storage URL (inline)
  - DELETE /documents/{document_id}                    — HTMX delete
  - GET    /documents/{entity_type}/{entity_id}        — HTMX partial for docs list

AREA 3: /calls (1 @rt)
  - GET /calls                                     — Calls journal registry

No helpers exclusive to these three areas live in this file:
  - AREA 1 inlines all contract rendering (no _contract_* helpers exist).
  - AREA 2's `_documents_section` is SHARED with /supplier-invoices (27966) —
    left alive in main.py. Same for `_quote_documents_section` (used by
    /quotes/{quote_id}/documents). All `upload_document`, `get_document`,
    `delete_document`, `get_download_url`, `INVOICE_DOCUMENT_TYPES`,
    `ITEM_DOCUMENT_TYPES`, `get_file_icon`, `format_file_size`,
    `get_document_type_label`, `get_documents_for_entity`,
    `get_allowed_document_types_for_entity` come from `services.document_service`
    (service layer still alive, consumed by supplier-invoices, quote-documents,
    spec-control, logistics-expenses, and `api/documents.py` FastAPI).
  - AREA 3 inlines all call rendering (no _call_* helpers exist).
    `CALL_TYPE_LABELS`, `CALL_CATEGORY_LABELS`, `get_calls_registry` come from
    `services.call_service` (service layer still alive, consumed by
    `/customers/{id}/calls` detail subtab + future FastAPI).

Preserved in main.py / services/ (NOT archived here):
  - services/customer_contract_service.py — create_contract, get_all_contracts,
    get_contracts_for_customer, get_contracts_with_customer_names,
    search_contracts, get_contract_stats, get_contract_with_customer,
    CONTRACT_STATUS_NAMES, CONTRACT_STATUS_COLORS, CONTRACT_TYPE_NAMES,
    CONTRACT_TYPE_COLORS — still alive, consumed by /spec-control handlers
    (lines 19500, 20097 link to /customer-contracts/new but those
    links become dead, safe per Caddy cutover) and by
    tests/test_customer_contract_service.py.
  - services/document_service.py — full service layer, consumed by many
    live surfaces (supplier-invoices, quote-documents, spec-control upload,
    logistics-expenses, api/documents.py FastAPI).
  - services/call_service.py — still alive, consumed by
    /customers/{id}/calls detail subtab.
  - FastAPI /api/documents/* (api/documents.py) — signed-URL download + delete
    for Next.js consumers, fully alive and separately covered by
    tests/test_api_documents.py.
  - _documents_section helper + _quote_documents_section helper —
    live in main.py, called by /supplier-invoices/{id} and
    /quotes/{id}/documents respectively.
  - sidebar/nav entry "Журнал звонков" → /calls (main.py line 2766)
    left intact, becomes dead link post-archive, safe per Caddy cutover.

NOT including (separate archive decisions):
  - /supplier-invoices/* (Phase 6C-2B-10b, not yet archived)
  - /finance/*, /deals/*, /admin/* (separate decisions)
  - /quotes/{quote_id}/chat, /quotes/{quote_id}/comments (Phase 6C-2B-13,
    part of quote-detail cluster)
  - /api/* (FastAPI, fully alive)

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_any_role, btn, btn_link,
icon, fasthtml components, starlette RedirectResponse/JSONResponse,
service-layer functions listed in the docstring above), re-apply the @rt
decorator, and regenerate tests if needed. Not recommended — rewrite via
Next.js + FastAPI instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Button, Details, Div, Form, H1, I, Input, Label, Option, P, Script,
    Select, Small, Span, Strong, Summary, Table, Tbody, Td, Textarea, Th,
    Thead, Tr,
)
from starlette.responses import JSONResponse, RedirectResponse


# ============================================================================
# AREA 1: CUSTOMER CONTRACTS
# ============================================================================
# 4 routes — registry, create form, create submit, detail.
# Framework contracts managing specification numbering counter
# (next_specification_number) for linked quotes/specs.


# ============================================================================
# UI-009: Customer Contracts List
# ============================================================================

# @rt("/customer-contracts")  # decorator removed; file is archived and not mounted
def get(session, q: str = "", status: str = "", customer_id: str = ""):
    """
    Customer contracts list page with search and filters.

    Contracts track supply agreements with customers and manage
    specification numbering (next_specification_number counter).

    Query Parameters:
        q: Search query (matches contract_number or customer name)
        status: Filter by status ("active", "suspended", "terminated", or "" for all)
        customer_id: Filter by specific customer
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin, sales, or top_manager can view contracts
    if not user_has_any_role(session, ["admin", "sales", "top_manager"]):
        return page_layout("Access Denied",
            Div(
                H1("⛔ Доступ запрещён"),
                P("У вас нет прав для просмотра договоров."),
                P("Требуется одна из ролей: admin, sales, top_manager"),
                btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
                cls="card"
            ),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    # Import contract service functions
    from services.customer_contract_service import (
        get_all_contracts, get_contracts_for_customer, get_contracts_with_customer_names,
        search_contracts, get_contract_stats,
        CONTRACT_STATUS_NAMES, CONTRACT_STATUS_COLORS
    )
    from services.customer_service import get_all_customers, get_customer

    # Get contracts based on filters
    try:
        if q and q.strip():
            # Use search if query provided
            status_filter = None if status == "" else status
            contracts = search_contracts(
                organization_id=org_id,
                query=q.strip(),
                status=status_filter,
                limit=100
            )
        elif customer_id:
            # Filter by customer
            status_filter = None if status == "" else status
            contracts = get_contracts_for_customer(
                customer_id=customer_id,
                status=status_filter,
                limit=100
            )
        else:
            # Get all with filters
            status_filter = status if status else None
            contracts = get_contracts_with_customer_names(
                organization_id=org_id,
                status=status_filter,
                limit=100
            )

        # Get stats for summary
        stats = get_contract_stats(organization_id=org_id)

        # Get customers for filter dropdown
        customers = get_all_customers(organization_id=org_id, is_active=True, limit=200)

        # If filtering by customer, get customer name for display
        filter_customer = None
        if customer_id:
            filter_customer = get_customer(customer_id)

    except Exception as e:
        print(f"Error loading contracts: {e}")
        contracts = []
        stats = {"total": 0, "active": 0, "suspended": 0, "terminated": 0}
        customers = []
        filter_customer = None

    # Status options for filter
    status_options = [
        Option("Все статусы", value="", selected=(status == "")),
        Option("Действующие", value="active", selected=(status == "active")),
        Option("Приостановленные", value="suspended", selected=(status == "suspended")),
        Option("Расторгнутые", value="terminated", selected=(status == "terminated")),
    ]

    # Customer options for filter
    customer_options = [Option("Все клиенты", value="", selected=(customer_id == ""))]
    for c in customers:
        customer_options.append(Option(
            c.name[:40] + "..." if len(c.name) > 40 else c.name,
            value=c.id,
            selected=(customer_id == c.id)
        ))

    # Build contract rows
    from services.customer_contract_service import CONTRACT_TYPE_NAMES, CONTRACT_TYPE_COLORS
    contract_rows = []
    for c in contracts:
        status_class = {
            "active": "status-approved",
            "suspended": "status-pending",
            "terminated": "status-rejected"
        }.get(c.status, "")
        status_text = CONTRACT_STATUS_NAMES.get(c.status, c.status)

        # Type badge
        type_badge = Span(
            CONTRACT_TYPE_NAMES.get(c.contract_type, ""),
            style=f"display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; color: white; background: {CONTRACT_TYPE_COLORS.get(c.contract_type, '#94a3b8')};"
        ) if c.contract_type else Span("—", style="color: #94a3b8;")

        contract_rows.append(
            Tr(
                Td(
                    Strong(c.contract_number),
                    style="font-family: monospace;"
                ),
                Td(c.customer_name or "—"),
                Td(c.contract_date.strftime("%d.%m.%Y") if c.contract_date else "—"),
                Td(type_badge),
                Td(c.end_date.strftime("%d.%m.%Y") if c.end_date else "—"),
                Td(str(c.next_specification_number - 1 if c.next_specification_number > 1 else 0)),
                Td(Span(status_text, cls=f"status-badge {status_class}")),
                Td(
                    A(icon("eye", size=14), href=f"/customer-contracts/{c.id}", title="Просмотр"),
                ),
                cls="clickable-row",
                onclick=f"window.location='/customer-contracts/{c.id}'"
            )
        )

    # Build page title with filter info
    page_title = "Договоры с клиентами"
    if filter_customer:
        page_title = f"Договоры: {filter_customer.name}"

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    stat_card_style = """
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    """

    filter_card_style = """
        background: #ffffff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        padding: 16px 20px;
        margin-bottom: 16px;
    """

    select_style = """
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
        width: 180px;
    """

    input_style = """
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
        width: 220px;
    """

    table_card_style = """
        background: #ffffff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
    """

    return page_layout(page_title,
        # Header card with gradient
        Div(
            Div(
                # Title row
                Div(
                    icon("file-signature", size=24, color="#475569"),
                    Span(f" {page_title}", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                    Span(f" ({stats.get('total', 0)})", style="font-size: 16px; color: #64748b; margin-left: 4px;"),
                    style="display: flex; align-items: center;"
                ),
                # Subtitle
                P("Рамочные соглашения на поставку с клиентами",
                  style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;"),
                style="flex: 1;"
            ),
            btn_link("Добавить договор", href="/customer-contracts/new", variant="success", icon_name="plus"),
            style=f"{header_card_style} display: flex; justify-content: space-between; align-items: center;"
        ),

        # Stats cards row (4 columns)
        Div(
            Div(
                Div(str(stats.get("total", 0)), style="font-size: 28px; font-weight: 700; color: #1e293b;"),
                Div("Всего", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=stat_card_style
            ),
            Div(
                Div(str(stats.get("active", 0)), style="font-size: 28px; font-weight: 700; color: #10b981;"),
                Div("Действующих", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=stat_card_style
            ),
            Div(
                Div(str(stats.get("suspended", 0)), style="font-size: 28px; font-weight: 700; color: #f59e0b;"),
                Div("Приостановлено", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=stat_card_style
            ),
            Div(
                Div(str(stats.get("terminated", 0)), style="font-size: 28px; font-weight: 700; color: #ef4444;"),
                Div("Расторгнуто", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=stat_card_style
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px;"
        ),

        # Filters card
        Div(
            Form(
                Div(
                    # Search input
                    Input(type="text", name="q", value=q, placeholder="Номер договора...",
                          style=f"{input_style} margin-right: 12px;"),
                    # Filters
                    Select(*customer_options, name="customer_id", style=f"{select_style} margin-right: 8px;"),
                    Select(*status_options, name="status", style=f"{select_style} margin-right: 12px;"),
                    # Buttons
                    Button(icon("search", size=14), " Поиск", type="submit",
                           style="padding: 10px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; margin-right: 8px;"),
                    A(icon("x", size=14), " Сбросить", href="/customer-contracts",
                      style="padding: 10px 16px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none;"),
                    style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px 0;"
                ),
                method="get",
                action="/customer-contracts"
            ),
            style=filter_card_style
        ),

        # Contracts table with styled container
        Div(
            Table(
                Thead(
                    Tr(
                        Th("Номер договора"),
                        Th("Клиент"),
                        Th("Дата"),
                        Th("Тип"),
                        Th("Окончание"),
                        Th("Спецификаций"),
                        Th("Статус"),
                        Th("Действия"),
                    )
                ),
                Tbody(*contract_rows) if contract_rows else Tbody(
                    Tr(Td("Договоры не найдены. ", A("Добавить первый договор", href="/customer-contracts/new"),
                          colspan="8", style="text-align: center; padding: 2rem; color: #64748b;"))
                )
            ),
            style=table_card_style
        ),

        session=session
    )


# ============================================================================
# UI-009b: Create Customer Contract
# ============================================================================

# @rt("/customer-contracts/new")  # decorator removed; file is archived and not mounted
def get(session, customer_id: str = ""):
    """Form for creating a new customer contract."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "sales", "top_manager"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания договоров.", cls="alert alert-error"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    from services.customer_service import get_all_customers, get_customer

    # Pre-select customer if provided
    selected_customer = None
    if customer_id:
        selected_customer = get_customer(customer_id)

    # Get customers for dropdown (only if no customer pre-selected)
    customers = []
    if not selected_customer:
        customers = get_all_customers(organization_id=org_id, limit=200)

    # Generate suggested contract number
    from datetime import date
    today = date.today()
    suggested_number = f"ДП-{today.strftime('%Y%m%d')}"

    return page_layout("Новый договор",
        H1(icon("file-plus", size=28), " Новый договор", cls="page-header"),

        Div(
            Form(
                # Customer - show as read-only if pre-selected, otherwise dropdown
                Div(
                    Label("Клиент *", For="customer_id"),
                    # If customer is pre-selected, show as read-only with hidden input
                    Div(
                        Input(type="hidden", name="customer_id", value=customer_id),
                        Div(
                            selected_customer.name if selected_customer else "",
                            style="padding: 0.5rem 0.75rem; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; color: #374151;"
                        ),
                        style="width: 100%;"
                    ) if selected_customer else
                    # Otherwise show dropdown
                    Select(
                        Option("-- Выберите клиента --", value="", disabled=True, selected=True),
                        *[Option(c.name, value=c.id) for c in customers],
                        name="customer_id",
                        id="customer_id",
                        required=True,
                        cls="form-input"
                    ),
                    cls="form-group"
                ),

                # Contract number
                Div(
                    Label("Номер договора *", For="contract_number"),
                    Input(
                        name="contract_number",
                        id="contract_number",
                        type="text",
                        value=suggested_number,
                        required=True,
                        placeholder="Например: ДП-001/2025",
                        cls="form-input"
                    ),
                    cls="form-group"
                ),

                # Contract date
                Div(
                    Label("Дата договора *", For="contract_date"),
                    Input(
                        name="contract_date",
                        id="contract_date",
                        type="date",
                        value=today.isoformat(),
                        required=True,
                        cls="form-input"
                    ),
                    cls="form-group"
                ),

                # Status
                Div(
                    Label("Статус", For="status"),
                    Select(
                        Option("Действующий", value="active", selected=True),
                        Option("Приостановлен", value="suspended"),
                        Option("Расторгнут", value="terminated"),
                        name="status",
                        id="status",
                        cls="form-input"
                    ),
                    cls="form-group"
                ),

                # Contract type
                Div(
                    Label("Тип договора", For="contract_type"),
                    Select(
                        Option("-- Не указан --", value=""),
                        Option("Единоразовый", value="one_time"),
                        Option("Пролонгируемый", value="renewable"),
                        name="contract_type",
                        id="contract_type",
                        cls="form-input"
                    ),
                    cls="form-group"
                ),

                # End date
                Div(
                    Label("Дата окончания", For="end_date"),
                    Input(
                        name="end_date",
                        id="end_date",
                        type="date",
                        cls="form-input"
                    ),
                    Small("Необязательно", style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"),
                    cls="form-group"
                ),

                # Notes
                Div(
                    Label("Примечания", For="notes"),
                    Textarea(
                        name="notes",
                        id="notes",
                        rows="3",
                        placeholder="Дополнительная информация о договоре...",
                        cls="form-input"
                    ),
                    cls="form-group"
                ),

                # Buttons
                Div(
                    btn("Создать договор", variant="success", icon_name="save", type="submit"),
                    btn_link("Отмена", href="/customer-contracts", variant="secondary", icon_name="x"),
                    style="display: flex; gap: 0.5rem; margin-top: 1rem;"
                ),

                method="post",
                action="/customer-contracts/new"
            ),
            cls="card"
        ),

        session=session
    )


# @rt("/customer-contracts/new")  # decorator removed; file is archived and not mounted
def post(session, customer_id: str, contract_number: str, contract_date: str, status: str = "active", contract_type: str = "", end_date: str = "", notes: str = ""):
    """Handle new contract creation."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "sales", "top_manager"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания договоров.", cls="alert alert-error"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    from services.customer_contract_service import create_contract
    from datetime import date

    try:
        # Parse dates
        contract_date_obj = date.fromisoformat(contract_date) if contract_date else date.today()
        end_date_obj = date.fromisoformat(end_date) if end_date and end_date.strip() else None

        # Create contract
        contract = create_contract(
            organization_id=org_id,
            customer_id=customer_id,
            contract_number=contract_number.strip(),
            contract_date=contract_date_obj,
            status=status,
            contract_type=contract_type if contract_type else None,
            end_date=end_date_obj,
            notes=notes.strip() if notes else None
        )

        if contract:
            # Success - redirect to contract detail
            return RedirectResponse(f"/customer-contracts/{contract.id}", status_code=303)
        else:
            return page_layout("Ошибка",
                Div("Не удалось создать договор.", cls="alert alert-error"),
                btn_link("Назад", href="/customer-contracts/new", variant="secondary"),
                session=session
            )

    except ValueError as e:
        return page_layout("Ошибка",
            Div(f"Ошибка: {str(e)}", cls="alert alert-error"),
            btn_link("Назад", href=f"/customer-contracts/new?customer_id={customer_id}", variant="secondary"),
            session=session
        )
    except Exception as e:
        print(f"Error creating contract: {e}")
        return page_layout("Ошибка",
            Div(f"Ошибка создания договора: {str(e)}", cls="alert alert-error"),
            btn_link("Назад", href="/customer-contracts/new", variant="secondary"),
            session=session
        )


# @rt("/customer-contracts/{contract_id}")  # decorator removed; file is archived and not mounted
def get(contract_id: str, session):
    """Customer contract detail view page."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "sales", "top_manager"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра данной страницы.", cls="alert alert-error"),
            session=session
        )

    from services.customer_contract_service import (
        get_contract_with_customer, CONTRACT_STATUS_NAMES, CONTRACT_STATUS_COLORS,
        CONTRACT_TYPE_NAMES, CONTRACT_TYPE_COLORS
    )

    contract = get_contract_with_customer(contract_id)
    if not contract:
        return page_layout("Не найдено",
            Div("Договор не найден.", cls="alert alert-error"),
            btn_link("К списку договоров", href="/customer-contracts", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    status_text = CONTRACT_STATUS_NAMES.get(contract.status, contract.status)
    status_colors = {
        "active": ("#16a34a", "#dcfce7"),
        "suspended": ("#d97706", "#fef3c7"),
        "terminated": ("#dc2626", "#fee2e2"),
    }
    status_color, status_bg = status_colors.get(contract.status, ("#64748b", "#f1f5f9"))

    specs_count = contract.next_specification_number - 1 if contract.next_specification_number > 1 else 0

    # Contract type badge for header
    type_badge_el = ""
    if contract.contract_type:
        type_name = CONTRACT_TYPE_NAMES.get(contract.contract_type, contract.contract_type)
        type_color = CONTRACT_TYPE_COLORS.get(contract.contract_type, "#94a3b8")
        type_badge_el = Span(type_name, style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: white; background: {type_color}; margin-left: 8px;")

    return page_layout(f"Договор: {contract.contract_number}",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Договоры", href="/customer-contracts",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Div(
                        icon("file-text", size=24, color="#0ea5e9"),
                        H1(f"Договор {contract.contract_number}", style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        type_badge_el,
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    Div(
                        Span(status_text, style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: {status_color}; background: {status_bg};"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Main info card
        Div(
            Div(
                icon("clipboard-list", size=16, color="#64748b"),
                Span("ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    Span("Номер договора", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(contract.contract_number, style="font-weight: 600; color: #0284c7; font-family: monospace; font-size: 16px;"),
                ),
                Div(
                    Span("Клиент", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(
                        A(contract.customer_name, href=f"/customers/{contract.customer_id}", style="color: #6366f1; font-weight: 500;") if contract.customer_name else "—",
                        style="font-size: 14px;"
                    ),
                ),
                Div(
                    Span("Дата договора", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(contract.contract_date.strftime("%d.%m.%Y") if contract.contract_date else "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                Div(
                    Span("Дата окончания", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(contract.end_date.strftime("%d.%m.%Y") if contract.end_date else "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                Div(
                    Span("Тип договора", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(
                        Span(CONTRACT_TYPE_NAMES.get(contract.contract_type, ""), style=f"display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; color: white; background: {CONTRACT_TYPE_COLORS.get(contract.contract_type, '#94a3b8')};") if contract.contract_type else Span("Не указан", style="color: #94a3b8;"),
                        style="margin-top: 2px;"
                    ),
                ),
                Div(
                    Span("Спецификаций создано", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(str(specs_count), style="font-weight: 600; color: #1e293b; font-size: 16px;"),
                ),
                style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;"
            ),
            style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Notes card (if has notes)
        Div(
            Div(
                icon("message-square", size=16, color="#64748b"),
                Span("ПРИМЕЧАНИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;"
            ),
            P(contract.notes or "Нет примечаний", style="font-size: 14px; color: #1e293b; margin: 0;"),
            style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if contract.notes else "",

        # Specifications info
        Div(
            Div(
                icon("file-stack", size=16, color="#64748b"),
                Span("СПЕЦИФИКАЦИИ ПО ДОГОВОРУ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;"
            ),
            P(f"По данному договору создано {specs_count} спецификаций.", style="font-size: 14px; color: #1e293b; margin: 0 0 8px 0;") if specs_count > 0 else
            P("По данному договору ещё нет спецификаций.", style="font-size: 14px; color: #64748b; margin: 0 0 8px 0;"),
            P(Span("Следующий номер спецификации: ", style="color: #64748b;"), Strong(f"№{contract.next_specification_number}", style="color: #1e293b;"), style="font-size: 14px; margin: 0 0 16px 0;"),
            btn_link("К контролю спецификаций", href="/dashboard?tab=spec-control", variant="secondary", icon_name="arrow-right"),
            style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        session=session
    )


# ============================================================================
# AREA 2: DOCUMENTS
# ============================================================================
# 5 routes — upload + download + view + delete + HTMX list partial.
# All service-layer calls (upload_document, get_document, delete_document,
# get_download_url, INVOICE_DOCUMENT_TYPES, ITEM_DOCUMENT_TYPES) come from
# services.document_service (alive). `_documents_section` is a SHARED helper
# in main.py, also used by /supplier-invoices — left alive there.


# @rt("/documents/upload/{entity_type}/{entity_id}")  # decorator removed; file is archived and not mounted
async def post(session, entity_type: str, entity_id: str, request):
    """
    Upload a document for an entity.

    POST /documents/upload/{entity_type}/{entity_id}
    Form data: file, document_type (optional), description (optional),
               sub_entity_invoice (optional), sub_entity_item (optional),
               parent_quote_id (optional)

    Hierarchical binding:
    - For invoice docs (invoice_scan, proforma_scan, payment_order): binds to supplier_invoice
    - For certificates: binds to quote_item
    - parent_quote_id tracks the parent quote for aggregated document views
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Validate entity type
    valid_entity_types = {"quote", "specification", "supplier_invoice", "quote_item", "supplier", "customer", "seller_company", "buyer_company"}
    if entity_type not in valid_entity_types:
        return JSONResponse({"error": f"Invalid entity type: {entity_type}"}, status_code=400)

    try:
        # Get the uploaded file from form data
        form = await request.form()
        uploaded_file = form.get("file")
        document_type = form.get("document_type") or None
        description = form.get("description") or None

        # Hierarchical binding fields
        sub_entity_invoice = form.get("sub_entity_invoice") or None
        sub_entity_item = form.get("sub_entity_item") or None
        parent_quote_id = form.get("parent_quote_id") or None

        if not uploaded_file or not uploaded_file.filename:
            # Redirect back with error
            return page_layout("Ошибка загрузки",
                H1("Файл не выбран"),
                Div(
                    "Пожалуйста, выберите файл для загрузки.",
                    cls="card",
                    style="background: #fee2e2; border-left: 4px solid #dc2626;"
                ),
                btn("Назад", variant="secondary", icon_name="arrow-left", type="button", onclick="history.back()"),
                session=session
            )

        # Read file content
        file_content = await uploaded_file.read()
        filename = uploaded_file.filename

        # Determine actual entity binding based on document type
        actual_entity_type = entity_type
        actual_entity_id = entity_id

        if document_type:
            if document_type in INVOICE_DOCUMENT_TYPES and sub_entity_invoice:
                # Bind to supplier invoice
                actual_entity_type = "supplier_invoice"
                actual_entity_id = sub_entity_invoice
            elif document_type in ITEM_DOCUMENT_TYPES and sub_entity_item:
                # Bind to quote item
                actual_entity_type = "quote_item"
                actual_entity_id = sub_entity_item

        # Upload document using service
        doc, error = upload_document(
            organization_id=org_id,
            entity_type=actual_entity_type,
            entity_id=actual_entity_id,
            file_content=file_content,
            filename=filename,
            document_type=document_type,
            description=description,
            uploaded_by=user_id,
            parent_quote_id=parent_quote_id
        )

        if error:
            return page_layout("Ошибка загрузки",
                H1("Ошибка загрузки файла"),
                Div(
                    error,
                    cls="card",
                    style="background: #fee2e2; border-left: 4px solid #dc2626;"
                ),
                btn("Назад", variant="secondary", icon_name="arrow-left", type="button", onclick="history.back()"),
                session=session
            )

        # Determine redirect URL based on entity type
        # Use parent_quote_id if available for sub-entity documents
        if parent_quote_id and actual_entity_type in ("supplier_invoice", "quote_item"):
            redirect_url = f"/quotes/{parent_quote_id}?tab=documents"
        else:
            redirect_urls = {
                "quote": f"/quotes/{entity_id}?tab=documents",
                "specification": f"/spec-control/{entity_id}",
                "supplier_invoice": f"/supplier-invoices/{entity_id}",
                "supplier": f"/suppliers/{entity_id}",
                "customer": f"/customers/{entity_id}?tab=documents",
                "seller_company": f"/companies?tab=seller_companies",
                "buyer_company": f"/companies?tab=buyer_companies",
                "quote_item": f"/quotes/{entity_id}",
            }
            redirect_url = redirect_urls.get(entity_type, "/")

        return RedirectResponse(redirect_url, status_code=303)

    except Exception as e:
        print(f"Error uploading document: {e}")
        import traceback
        traceback.print_exc()

        return page_layout("Ошибка загрузки",
            H1("Ошибка загрузки файла"),
            Div(
                f"Произошла ошибка: {str(e)}",
                cls="card",
                style="background: #fee2e2; border-left: 4px solid #dc2626;"
            ),
            btn("Назад", variant="secondary", icon_name="arrow-left", type="button", onclick="history.back()"),
            session=session
        )


# @rt("/documents/{document_id}/download")  # decorator removed; file is archived and not mounted
async def get(session, document_id: str):
    """
    Download a document (redirect to signed URL).

    GET /documents/{document_id}/download
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Get document
    doc = get_document(document_id)
    if not doc:
        return page_layout("Документ не найден",
            H1("Документ не найден"),
            Div("Запрошенный документ не существует или был удалён.", cls="card"),
            session=session
        )

    # Verify organization access
    if doc.organization_id != org_id:
        return RedirectResponse("/unauthorized", status_code=303)

    # Get signed download URL with force_download to trigger browser download
    download_url = get_download_url(document_id, expires_in=3600, force_download=True)

    if not download_url:
        return page_layout("Ошибка загрузки",
            H1("Не удалось получить ссылку"),
            Div("Не удалось сгенерировать ссылку для скачивания. Попробуйте позже.", cls="card"),
            session=session
        )

    # Redirect to signed URL
    return RedirectResponse(download_url, status_code=302)


# @rt("/documents/{document_id}/view")  # decorator removed; file is archived and not mounted
async def get(session, document_id: str):
    """
    View a document in browser (redirect to signed URL without download header).

    GET /documents/{document_id}/view
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Get document
    doc = get_document(document_id)
    if not doc:
        return page_layout("Документ не найден",
            H1("Документ не найден"),
            Div("Запрошенный документ не существует или был удалён.", cls="card"),
            session=session
        )

    # Verify organization access
    if doc.organization_id != org_id:
        return RedirectResponse("/unauthorized", status_code=303)

    # Get signed URL without force_download (for viewing in browser)
    view_url = get_download_url(document_id, expires_in=3600, force_download=False)

    if not view_url:
        return page_layout("Ошибка просмотра",
            H1("Не удалось получить ссылку"),
            Div("Не удалось сгенерировать ссылку для просмотра. Попробуйте позже.", cls="card"),
            session=session
        )

    # Redirect to signed URL (will display in browser)
    return RedirectResponse(view_url, status_code=302)


# @rt("/documents/{document_id}")  # decorator removed; file is archived and not mounted
async def delete(session, document_id: str):
    """
    Delete a document (HTMX DELETE).

    DELETE /documents/{document_id}
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Get document to verify ownership
    doc = get_document(document_id)
    if not doc:
        return ""  # Already deleted

    # Verify organization access
    if doc.organization_id != org_id:
        return ""

    # Check role permissions for delete
    if not user_has_any_role(session, ["admin", "sales_manager", "quote_controller", "finance"]):
        return Div("Недостаточно прав для удаления", style="color: #dc3545;")

    # Delete document
    success, error = delete_document(document_id)

    if not success:
        return Div(f"Ошибка: {error}", style="color: #dc3545;")

    # Return empty to remove row
    return ""


# @rt("/documents/{entity_type}/{entity_id}")  # decorator removed; file is archived and not mounted
async def get(session, entity_type: str, entity_id: str):
    """
    Get documents list for an entity (HTMX partial).

    GET /documents/{entity_type}/{entity_id}
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    # Determine permissions based on roles
    can_upload = user_has_any_role(session, ["admin", "sales", "sales_manager", "procurement", "quote_controller", "finance", "logistics", "customs"])
    can_delete = user_has_any_role(session, ["admin", "sales_manager", "quote_controller", "finance"])

    return _documents_section(entity_type, entity_id, session, can_upload=can_upload, can_delete=can_delete)


# ============================================================================
# AREA 3: CALLS REGISTRY
# ============================================================================
# 1 route — calls journal, one big handler that inlines all row rendering.
# CALL_TYPE_LABELS, CALL_CATEGORY_LABELS, get_calls_registry come from
# services.call_service (alive, also consumed by /customers/{id}/calls tab).


# @rt("/calls")  # decorator removed; file is archived and not mounted
def get(session, q: str = "", call_type: str = "", user_filter: str = ""):
    """Calls journal registry page."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "sales", "sales_manager", "top_manager"]):
        return page_layout("Access Denied",
            Div(H1("Доступ запрещён"), P("Требуется роль: admin, sales или top_manager"), cls="card"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")
    user_id = user.get("id")
    roles = user.get("roles", [])
    is_admin_or_top = any(r in roles for r in ["admin", "top_manager"])

    from services.call_service import get_calls_registry, CALL_TYPE_LABELS, CALL_CATEGORY_LABELS

    # Sales-only see only their own calls
    effective_user_filter = user_filter if is_admin_or_top else user_id

    calls = get_calls_registry(
        org_id=org_id,
        q=q,
        user_id=effective_user_filter,
        call_type=call_type,
        limit=300,
    )

    th_style = "text-align:left;padding:12px 16px;background:#f8fafc;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #e2e8f0;"
    td_style = "padding:12px 16px;font-size:14px;color:#1e293b;border-bottom:1px solid #f1f5f9;vertical-align:top;"

    rows = []
    for c in calls:
        type_label = CALL_TYPE_LABELS.get(c.call_type, c.call_type)
        cat_label = CALL_CATEGORY_LABELS.get(c.call_category or "", "—")

        type_color = "#2563eb" if c.call_type == "scheduled" else "#10b981"
        type_bg = "#bfdbfe" if c.call_type == "scheduled" else "#d1fae5"
        type_badge = Span(type_label, style=f"background:{type_bg};color:{type_color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;")

        date_str = "—"
        if c.call_type == "scheduled" and c.scheduled_date:
            date_str = c.scheduled_date.strftime("%d.%m.%Y %H:%M")
        elif c.created_at:
            date_str = c.created_at.strftime("%d.%m.%Y")

        comment_text = c.comment or ""
        _extra_fields = []
        if c.customer_needs:
            _extra_fields.append(Div(Span("Потребление / Зона: ", style="font-weight:500;color:#64748b;"), c.customer_needs, style="font-size:12px;color:#374151;margin-top:4px;"))
        if c.meeting_notes:
            _extra_fields.append(Div(Span("Назначение встречи: ", style="font-weight:500;color:#64748b;"), c.meeting_notes, style="font-size:12px;color:#374151;margin-top:2px;"))

        if len(comment_text) > 80 or _extra_fields:
            summary_text = comment_text[:80] + ("…" if len(comment_text) > 80 else "")
            comment_cell = Details(
                Summary(summary_text or "—", style="cursor:pointer;color:#64748b;list-style:revert;"),
                P(comment_text, style="margin:6px 0 0;color:#374151;white-space:pre-wrap;") if len(comment_text) > 80 else None,
                *_extra_fields,
                style="max-width:320px;"
            )
        else:
            comment_cell = Span(comment_text or "—", style="color:#64748b;")

        rows.append(Tr(
            Td(type_badge, style=td_style),
            Td(date_str, style=td_style),
            Td(c.user_name or "—", style=td_style),
            Td(
                A(c.customer_name or "—",
                  href=f"/customers/{c.customer_id}?tab=calls",
                  style="color:#4a4aff;text-decoration:none;")
                if c.customer_id else Span("—"),
                style=td_style
            ),
            Td(c.contact_name or "—", style=td_style),
            Td(cat_label, style=td_style),
            Td(comment_cell, style=f"{td_style} max-width:280px;"),
        ))

    input_style = "padding:10px 14px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;background:#f8fafc;"
    select_style = "padding:10px 14px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;background:#f8fafc;"

    type_options = [
        Option("Все типы", value="", selected=(call_type == "")),
        Option("Звонки", value="call", selected=(call_type == "call")),
        Option("Запланированные", value="scheduled", selected=(call_type == "scheduled")),
    ]

    scheduled_count = sum(1 for c in calls if c.call_type == "scheduled")
    call_count = sum(1 for c in calls if c.call_type == "call")

    return page_layout("Журнал звонков",
        Div(
            Div(
                icon("phone", size=24, color="#6366f1"),
                Span("Журнал звонков", style="font-size:22px;font-weight:600;color:#1e293b;margin-left:10px;"),
                Span(f"{len(calls)}", style="background:#e0e7ff;color:#4f46e5;font-size:12px;font-weight:600;padding:4px 10px;border-radius:12px;margin-left:12px;"),
                style="display:flex;align-items:center;"
            ),
            style="background:linear-gradient(135deg,#fafbfc 0%,#f4f5f7 100%);border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.04);"
        ),
        # Stats
        Div(
            Div(Div(icon("phone", size=20, color="#10b981"), style="margin-bottom:8px;"),
                Div(str(call_count), style="font-size:28px;font-weight:700;color:#1e293b;"),
                Div("Звонков", style="font-size:12px;color:#64748b;text-transform:uppercase;"),
                style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:20px;text-align:center;"),
            Div(Div(icon("calendar", size=20, color="#6366f1"), style="margin-bottom:8px;"),
                Div(str(scheduled_count), style="font-size:28px;font-weight:700;color:#6366f1;"),
                Div("Запланировано", style="font-size:12px;color:#64748b;text-transform:uppercase;"),
                style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:20px;text-align:center;"),
            style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-bottom:20px;"
        ),
        # Filters
        Div(
            Form(
                Div(icon("search", size=16, color="#64748b"),
                    Span("ФИЛЬТРЫ", style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;margin-left:8px;"),
                    style="display:flex;align-items:center;margin-bottom:12px;"),
                Div(
                    Input(name="q", value=q, placeholder="Поиск по клиенту, контакту, комментарию...", style=f"{input_style} flex:3;"),
                    Select(*type_options, name="call_type", style=f"{select_style} flex:1;"),
                    btn("Поиск", variant="primary", icon_name="search", type="submit"),
                    btn_link("Сбросить", href="/calls", variant="secondary", icon_name="x"),
                    style="display:flex;gap:12px;align-items:center;"
                ),
                method="get", action="/calls"
            ),
            style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;margin-bottom:20px;"
        ),
        # Table
        Div(
            Div(
                Table(
                    Thead(Tr(
                        Th("Тип", style=th_style),
                        Th("Дата", style=th_style),
                        Th("МОП", style=th_style),
                        Th("Клиент", style=th_style),
                        Th("Контакт", style=th_style),
                        Th("Категория", style=th_style),
                        Th("Комментарий", style=th_style),
                    )),
                    Tbody(*rows) if rows else Tbody(Tr(Td(
                        Div(icon("inbox", size=40, color="#cbd5e1"),
                            Div("Звонков не найдено", style="font-size:16px;font-weight:500;color:#64748b;margin-top:12px;"),
                            style="text-align:center;padding:40px 20px;"),
                        colspan="7"
                    ))),
                    style="width:100%;border-collapse:collapse;"
                ),
                style="overflow-x:auto;"
            ),
            style="background:white;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.04);overflow:hidden;"
        ),
        session=session
    )
