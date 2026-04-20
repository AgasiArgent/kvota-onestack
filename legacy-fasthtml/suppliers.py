"""FastHTML /suppliers area — archived 2026-04-20 during Phase 6C-2B-2.

Replaced by Next.js at https://app.kvotaflow.ru/suppliers (and children).
Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy /suppliers/* back to this Python container.

Contents:
  - GET    /suppliers                                     — registry list with filters
  - GET    /suppliers/new                                 — create form
  - POST   /suppliers/new                                 — create supplier
  - GET    /suppliers/{supplier_id}                       — detail view (general, brands tabs)
  - POST   /suppliers/{supplier_id}/brands                — add brand to supplier
  - DELETE /suppliers/{supplier_id}/brands/{assignment_id} — remove brand
  - PATCH  /suppliers/{supplier_id}/brands/{assignment_id} — toggle primary brand
  - GET    /suppliers/{supplier_id}/edit                   — edit form
  - POST   /suppliers/{supplier_id}/edit                   — update supplier
  - POST   /suppliers/{supplier_id}/delete                 — deactivate supplier (admin only)
  - helpers: _supplier_brand_row, _supplier_brands_tab,
    _supplier_brands_list_partial, _supplier_form

Preserved in main.py (NOT archived here):
  - /supplier-invoices/*          — no Next.js equivalent yet, separate archive decision
  - /api/suppliers/*              — FastAPI sub-app, consumed by Next.js
  - /quotes/.../suppliers/* (if any) — part of quote detail area

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, tab_nav, require_login, user_has_any_role,
user_has_role, get_supabase, btn, btn_link, icon, COUNTRY_NAME_MAP, json,
Tr, Td, Th, Table, Thead, Tbody, Div, Span, H1, P, A, Form, Input, Label,
Select, Option, Textarea, Small, Strong, etc.), re-apply the @rt decorator,
and regenerate tests if needed. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Div, Form, H1, Input, Label, Option, P, Select, Small, Span, Strong,
    Table, Tbody, Td, Textarea, Th, Thead, Tr,
)
from starlette.responses import RedirectResponse


# ============================================================================
# SUPPLIERS LIST (Feature UI-001)
# ============================================================================

# @rt("/suppliers")  # decorator removed; file is archived and not mounted
def get(session, q: str = "", country: str = "", status: str = ""):
    """
    Suppliers list page with search and filters.

    Query Parameters:
        q: Search query (matches name or supplier_code)
        country: Filter by country
        status: Filter by status ("active", "inactive", or "" for all)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin or procurement role required
    if not user_has_any_role(session, ["admin", "procurement"]):
        return page_layout("Access Denied",
            Div(
                H1("⛔ Доступ запрещён"),
                P("У вас нет прав для просмотра справочника поставщиков."),
                P("Требуется роль: admin или procurement"),
                btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
                cls="card"
            ),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    # Import supplier service
    from services.supplier_service import (
        get_all_suppliers, search_suppliers, get_unique_countries, get_supplier_stats
    )

    # Get suppliers based on filters
    try:
        if q and q.strip():
            # Use search if query provided
            suppliers = search_suppliers(
                organization_id=org_id,
                query=q.strip(),
                country=country if country else None,
                active_only=(status == "active"),
                limit=100
            )
        else:
            # Get all with filters
            is_active = None if status == "" else (status == "active")
            if country:
                # Use country-specific function
                from services.supplier_service import get_suppliers_by_country
                suppliers = get_suppliers_by_country(
                    organization_id=org_id,
                    country=country,
                    is_active=is_active
                )
            else:
                suppliers = get_all_suppliers(
                    organization_id=org_id,
                    is_active=is_active,
                    limit=100
                )

        # Get countries for filter dropdown
        countries = get_unique_countries(organization_id=org_id)

        # Get stats for summary
        stats = get_supplier_stats(organization_id=org_id)

    except Exception as e:
        print(f"Error loading suppliers: {e}")
        suppliers = []
        countries = []
        stats = {"total": 0, "active": 0, "inactive": 0}

    # Build country options for filter (deduplicate by display name)
    seen_labels = {}
    for c in countries:
        label = COUNTRY_NAME_MAP.get(c, c)
        if label not in seen_labels:
            seen_labels[label] = c
    country_options = [Option("Все страны", value="")] + [
        Option(label, value=raw_val, selected=(raw_val == country)) for label, raw_val in sorted(seen_labels.items())
    ]

    # Status options
    status_options = [
        Option("Все статусы", value="", selected=(status == "")),
        Option("Активные", value="active", selected=(status == "active")),
        Option("Неактивные", value="inactive", selected=(status == "inactive")),
    ]

    # Build supplier rows
    supplier_rows = []
    for s in suppliers:
        status_text = "Активен" if s.is_active else "Неактивен"
        status_class = "status-success" if s.is_active else "status-neutral"

        supplier_rows.append(
            Tr(
                Td(
                    A(Strong(s.supplier_code), href=f"/suppliers/{s.id}", style="font-family: monospace; color: var(--accent);")
                ),
                Td(s.name),
                Td(f"{COUNTRY_NAME_MAP.get(s.country or '', s.country or '—')}, {s.city}" if s.country and s.city else COUNTRY_NAME_MAP.get(s.country or '', s.country or '—') if s.country else "—"),
                Td(s.inn or "—"),
                Td(s.contact_person or "—"),
                Td(s.contact_email or "—"),
                Td(Span(status_text, cls=f"status-badge {status_class}")),
                Td(
                    A(icon("eye", size=16), href=f"/suppliers/{s.id}", title="Просмотр", cls="table-action-btn"),
                    A(icon("edit", size=16), href=f"/suppliers/{s.id}/edit", title="Редактировать", cls="table-action-btn"),
                    cls="col-actions"
                ),
                cls="clickable-row",
                onclick=f"window.location='/suppliers/{s.id}'"
            )
        )

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
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

    new_btn_style = """
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 18px;
        font-size: 14px;
        font-weight: 600;
        color: white;
        background: #3b82f6;
        border: none;
        border-radius: 8px;
        text-decoration: none;
        transition: background-color 0.15s ease;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.25);
    """

    stat_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        padding: 16px 20px;
        text-align: center;
        min-width: 120px;
    """

    filter_input_style = """
        padding: 8px 12px;
        font-size: 13px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        background: #f8fafc;
        color: #1e293b;
        max-width: 200px;
    """

    return page_layout("Поставщики",
        # Header card with title and actions
        Div(
            Div(
                icon("package", size=26, style="color: #f59e0b;"),
                H1("Поставщики", style=page_title_style),
                style="display: flex; align-items: center; gap: 14px;"
            ),
            Div(
                A(
                    icon("plus", size=16),
                    Span("Добавить"),
                    href="/suppliers/new",
                    style=new_btn_style
                ),
            ),
            style=header_card_style
        ),

        # Stats cards row
        Div(
            Div(
                Div(str(stats.get("total", 0)), style="font-size: 24px; font-weight: 700; color: #1e293b;"),
                Div("Всего", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px;"),
                style=stat_card_style
            ),
            Div(
                Div(str(stats.get("active", 0)), style="font-size: 24px; font-weight: 700; color: #059669;"),
                Div("Активных", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px;"),
                style=stat_card_style
            ),
            Div(
                Div(str(stats.get("inactive", 0)), style="font-size: 24px; font-weight: 700; color: #dc2626;"),
                Div("Неактивных", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px;"),
                style=stat_card_style
            ),
            style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;"
        ),

        # Table Container
        Div(
            # Table header with filters
            Div(
                Div(
                    Form(
                        Input(name="q", value=q, placeholder="Поиск по названию или коду...", style=filter_input_style + "min-width: 220px;"),
                        Select(*country_options, name="country", style=filter_input_style),
                        Select(*status_options, name="status", style=filter_input_style),
                        btn("Поиск", variant="secondary", icon_name="search", type="submit", size="sm"),
                        method="get",
                        action="/suppliers",
                        style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;"
                    ),
                    cls="table-header-left"
                ),
                cls="table-header"
            ),
            # Table
            Div(
                Div(
                    Table(
                        Thead(
                            Tr(
                                Th("КОД"),
                                Th("НАЗВАНИЕ"),
                                Th("ЛОКАЦИЯ"),
                                Th("ИНН"),
                                Th("КОНТАКТ"),
                                Th("EMAIL"),
                                Th("СТАТУС"),
                                Th("", cls="col-actions")
                            )
                        ),
                        Tbody(*supplier_rows) if supplier_rows else Tbody(
                            Tr(Td(
                                Div(
                                    icon("package", size=32, style="color: #94a3b8; margin-bottom: 12px;"),
                                    Div("Поставщики не найдены", style="font-size: 15px; font-weight: 500; color: #64748b; margin-bottom: 8px;"),
                                    A(
                                        icon("plus", size=14),
                                        Span("Добавить поставщика"),
                                        href="/suppliers/new",
                                        style="display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; font-size: 13px; font-weight: 600; color: #3b82f6; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; text-decoration: none;"
                                    ),
                                    style="text-align: center; padding: 40px 24px;"
                                ),
                                colspan="8"
                            ))
                        ),
                        cls="table-enhanced"
                    ),
                    cls="table-enhanced-container"
                ),
                cls="table-responsive"
            ),
            # Table footer
            Div(
                Span(f"Всего: {len(suppliers)} поставщиков", style="font-size: 13px; color: #64748b;"),
                cls="table-footer"
            ),
            cls="table-container"
        ),

        session=session,
        current_path="/suppliers"
    )


# @rt("/suppliers/new")  # decorator removed; file is archived and not mounted
def get(session):
    """Show form to create a new supplier."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "procurement"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания поставщиков.", cls="alert alert-error"),
            session=session
        )

    return _supplier_form(session=session)


# @rt("/suppliers/new")  # decorator removed; file is archived and not mounted
def post(
    supplier_code: str,
    name: str,
    country: str = "",
    city: str = "",
    inn: str = "",
    kpp: str = "",
    contact_person: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    default_payment_terms: str = "",
    session=None
):
    """Handle supplier creation form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "procurement"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания поставщиков.", cls="alert alert-error"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")
    user_id = user.get("id")

    from services.supplier_service import create_supplier, validate_supplier_code

    # Normalize supplier code to uppercase
    supplier_code = supplier_code.strip().upper() if supplier_code else ""

    # Validate supplier code format
    if not supplier_code or not validate_supplier_code(supplier_code):
        return _supplier_form(
            error="Код поставщика должен состоять из 3 заглавных латинских букв",
            session=session
        )

    try:
        supplier = create_supplier(
            organization_id=org_id,
            name=name.strip(),
            supplier_code=supplier_code,
            country=country.strip() or None,
            city=city.strip() or None,
            inn=inn.strip() or None,
            kpp=kpp.strip() or None,
            contact_person=contact_person.strip() or None,
            contact_email=contact_email.strip() or None,
            contact_phone=contact_phone.strip() or None,
            default_payment_terms=default_payment_terms.strip() or None,
            is_active=True,
            created_by=user_id,
        )

        if supplier:
            return RedirectResponse(f"/suppliers/{supplier.id}", status_code=303)
        else:
            return _supplier_form(
                error="Поставщик с таким кодом уже существует",
                session=session
            )

    except ValueError as e:
        return _supplier_form(error=str(e), session=session)
    except Exception as e:
        print(f"Error creating supplier: {e}")
        return _supplier_form(error=f"Ошибка при создании: {e}", session=session)


def _supplier_brand_row(a, supplier_id):
    """Render a single brand row for the supplier brands table."""
    primary_badge = Span(
        icon("star", size=14, color="#f59e0b"),
        " Основной",
        style="display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; background: #fef3c7; color: #92400e; border-radius: 6px; font-size: 12px; font-weight: 600;"
    ) if a.is_primary else Span("—", style="color: #94a3b8; font-size: 13px;")

    toggle_label = "Убрать основной" if a.is_primary else "Сделать основным"
    toggle_value = "false" if a.is_primary else "true"

    return Tr(
        Td(Span(a.brand, style="font-weight: 600; color: #1e293b; font-size: 14px;"), style="padding: 12px 16px;"),
        Td(primary_badge, style="padding: 12px 16px;"),
        Td(
            Div(
                btn(toggle_label, variant="ghost", size="sm", icon_name="star",
                    hx_patch=f"/suppliers/{supplier_id}/brands/{a.id}",
                    hx_vals=json.dumps({"is_primary": toggle_value}),
                    hx_target="#brands-list",
                    hx_swap="innerHTML"),
                btn("Удалить", variant="danger", size="sm", icon_name="trash-2",
                    onclick=f"let b=this; b.innerText='Точно?'; b.style.background='#dc2626'; b.onclick=function(){{ htmx.ajax('DELETE', '/suppliers/{supplier_id}/brands/{a.id}', {{target:'#brands-list', swap:'innerHTML'}}); }}"),
                style="display: flex; gap: 8px;"
            ),
            style="padding: 12px 16px;"
        ),
        style="border-bottom: 1px solid #f1f5f9;"
    )


def _supplier_brands_tab(supplier_id, session):
    """Render the brands tab content for a supplier detail page."""
    from services.brand_supplier_assignment_service import get_assignments_for_supplier

    assignments = get_assignments_for_supplier(supplier_id)

    # Build brand rows using shared helper
    brand_rows = [_supplier_brand_row(a, supplier_id) for a in sorted(assignments, key=lambda x: x.brand)]

    if brand_rows:
        brands_table = Table(
            Thead(
                Tr(
                    Th("Бренд", style="padding: 10px 16px; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;"),
                    Th("Статус", style="padding: 10px 16px; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;"),
                    Th("Действия", style="padding: 10px 16px; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;"),
                ),
                style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
            ),
            Tbody(*brand_rows),
            style="width: 100%; border-collapse: collapse;"
        )
    else:
        brands_table = Table(
            Tbody(
                Tr(Td("Бренды не привязаны к этому поставщику.", colspan="3", style="text-align: center; padding: 2rem; color: #666;"))
            ),
            style="width: 100%; border-collapse: collapse;"
        )

    # Add brand form
    add_form = Form(
        Div(
            Input(name="brand", placeholder="Название бренда", required=True,
                  style="padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; flex: 1; background: #f8fafc;"),
            Label(
                Input(type="checkbox", name="is_primary", value="true", style="margin-right: 6px;"),
                "Основной",
                style="display: flex; align-items: center; font-size: 13px; color: #64748b; white-space: nowrap;"
            ),
            btn("Добавить бренд", variant="success", size="sm", icon_name="plus", type="submit"),
            style="display: flex; gap: 12px; align-items: center;"
        ),
        hx_post=f"/suppliers/{supplier_id}/brands",
        hx_target="#brands-list",
        hx_swap="innerHTML",
        style="margin-bottom: 16px;"
    )

    return Div(add_form, Div(brands_table, id="brands-list"))


def _supplier_brands_list_partial(supplier_id):
    """Render just the brands list (for HTMX partial updates)."""
    from services.brand_supplier_assignment_service import get_assignments_for_supplier

    assignments = get_assignments_for_supplier(supplier_id)

    # Build brand rows using shared helper
    brand_rows = [_supplier_brand_row(a, supplier_id) for a in sorted(assignments, key=lambda x: x.brand)]

    if brand_rows:
        return Table(
            Thead(
                Tr(
                    Th("Бренд", style="padding: 10px 16px; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;"),
                    Th("Статус", style="padding: 10px 16px; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;"),
                    Th("Действия", style="padding: 10px 16px; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;"),
                ),
                style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
            ),
            Tbody(*brand_rows),
            style="width: 100%; border-collapse: collapse;"
        )
    else:
        return Table(
            Tbody(
                Tr(Td("Бренды не привязаны к этому поставщику.", colspan="3", style="text-align: center; padding: 2rem; color: #666;"))
            ),
            style="width: 100%; border-collapse: collapse;"
        )


# @rt("/suppliers/{supplier_id}")  # decorator removed; file is archived and not mounted
def get(supplier_id: str, session, request, tab: str = "general"):
    """View single supplier details with tabbed interface."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "procurement"]):
        return Div("У вас нет прав для просмотра поставщиков.", cls="alert alert-error")

    from services.supplier_service import get_supplier

    supplier = get_supplier(supplier_id)

    if not supplier:
        return Div(
            H1(icon("x-circle", size=28), " Поставщик не найден", cls="page-header"),
            P("Запрашиваемый поставщик не существует."),
            btn_link("К списку поставщиков", href="/suppliers", variant="secondary", icon_name="arrow-left"),
            cls="card"
        )

    status_text = "Активен" if supplier.is_active else "Неактивен"

    # Tab navigation
    tabs_nav = tab_nav([
        {'id': 'general', 'label': 'Общая', 'url': f'/suppliers/{supplier_id}?tab=general'},
        {'id': 'brands', 'label': 'Бренды', 'url': f'/suppliers/{supplier_id}?tab=brands'},
    ], active_tab=tab, target_id="tab-content")

    # Build tab content
    if tab == "brands":
        tab_content = _supplier_brands_tab(supplier_id, session)
    else:
        tab_content = Div(
            Div(
                Div(
                    Div(
                        icon("building", size=16, color="#64748b"),
                        Span("ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        Div(
                            Span("Код поставщика", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                            Div(supplier.supplier_code, style="font-weight: 600; color: #3b82f6; font-family: monospace; font-size: 16px;"),
                        ),
                        Div(
                            Span("Название", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                            Div(supplier.name, style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                        ),
                        style="display: grid; gap: 12px;"
                    ),
                    style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),
                Div(
                    Div(
                        icon("map-pin", size=16, color="#64748b"),
                        Span("ЛОКАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        Div(
                            Span("Страна", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                            Div(supplier.country or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                        ),
                        Div(
                            Span("Город", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                            Div(supplier.city or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                        ),
                        style="display: grid; gap: 12px;"
                    ),
                    style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),
                style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    icon("file-text", size=16, color="#64748b"),
                    Span("ЮРИДИЧЕСКИЕ ДАННЫЕ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("ИНН", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(supplier.inn or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("КПП", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(supplier.kpp or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ) if supplier.inn or supplier.kpp else "",
            Div(
                Div(
                    icon("user", size=16, color="#64748b"),
                    Span("КОНТАКТНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("Контактное лицо", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(supplier.contact_person or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("Email", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(
                            A(supplier.contact_email, href=f"mailto:{supplier.contact_email}", style="color: #6366f1;")
                            if supplier.contact_email else "—",
                            style="font-weight: 500; color: #1e293b; font-size: 14px;"
                        ),
                    ),
                    Div(
                        Span("Телефон", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(
                            A(supplier.contact_phone, href=f"tel:{supplier.contact_phone}", style="color: #6366f1;")
                            if supplier.contact_phone else "—",
                            style="font-weight: 500; color: #1e293b; font-size: 14px;"
                        ),
                    ),
                    style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            Div(
                Div(
                    icon("credit-card", size=16, color="#64748b"),
                    Span("УСЛОВИЯ ОПЛАТЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;"
                ),
                P(supplier.default_payment_terms or "Не указаны", style="font-size: 14px; color: #1e293b;"),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ) if supplier.default_payment_terms else "",
            Div(
                Div(
                    Span("Создан", style="font-size: 11px; color: #94a3b8; text-transform: uppercase;"),
                    Span(f"{supplier.created_at.strftime('%d.%m.%Y %H:%M') if supplier.created_at else '—'}", style="font-size: 13px; color: #64748b; margin-left: 8px;"),
                    style="display: flex; align-items: center; gap: 4px;"
                ),
                Div(
                    Span("Обновлён", style="font-size: 11px; color: #94a3b8; text-transform: uppercase;"),
                    Span(f"{supplier.updated_at.strftime('%d.%m.%Y %H:%M') if supplier.updated_at else '—'}", style="font-size: 13px; color: #64748b; margin-left: 8px;"),
                    style="display: flex; align-items: center; gap: 4px;"
                ),
                style="display: flex; gap: 24px; padding: 12px 0; border-top: 1px solid #e2e8f0;"
            ),
        )

    # If this is an HTMX request (tab switch), return only the tab content
    if request and request.headers.get("HX-Request"):
        return tab_content

    return page_layout(f"Поставщик: {supplier.name}",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Поставщики", href="/suppliers",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Div(
                        icon("package", size=24, color="#6366f1"),
                        H1(supplier.name, style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        Span(supplier.supplier_code, style="font-family: monospace; font-size: 14px; padding: 4px 10px; background: #eff6ff; color: #3b82f6; border-radius: 6px; font-weight: 600;"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    Div(
                        Span(status_text, style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: {'#16a34a' if supplier.is_active else '#dc2626'}; background: {'#dcfce7' if supplier.is_active else '#fee2e2'};"),
                        btn_link("Редактировать", href=f"/suppliers/{supplier_id}/edit", variant="secondary", icon_name="edit", size="sm"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Tab navigation
        tabs_nav,

        # Tab content
        Div(tab_content, id="tab-content", style="margin-top: 16px;"),

        session=session
    )


# ============================================================================
# SUPPLIER BRAND MANAGEMENT ROUTES (Feature UI-BSA)
# ============================================================================

# @rt("/suppliers/{supplier_id}/brands")  # decorator removed; file is archived and not mounted
def post(supplier_id: str, session, brand: str = "", is_primary: str = ""):
    """Add a brand to a supplier."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "procurement"]):
        return Div("Нет прав", style="color: #dc2626;")

    brand = brand.strip().upper()
    if not brand:
        return Div(
            Span("Ошибка: название бренда обязательно", style="color: #dc2626; font-size: 13px;"),
            _supplier_brands_list_partial(supplier_id),
        )

    user = session.get("user") or {}
    org_id = user.get("org_id", "")
    user_id = user.get("id")
    primary = is_primary in ("true", "on", "True")

    from services.brand_supplier_assignment_service import create_brand_supplier_assignment
    try:
        create_brand_supplier_assignment(
            organization_id=org_id,
            brand=brand,
            supplier_id=supplier_id,
            is_primary=primary,
            created_by=user_id,
        )
    except Exception as e:
        print(f"Error creating brand assignment: {e}")

    return _supplier_brands_list_partial(supplier_id)


# @rt("/suppliers/{supplier_id}/brands/{assignment_id}")  # decorator removed; file is archived and not mounted
def delete(supplier_id: str, assignment_id: str, session):
    """Remove a brand-supplier assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "procurement"]):
        return Div("Нет прав", style="color: #dc2626;")

    from services.brand_supplier_assignment_service import delete_brand_supplier_assignment
    try:
        delete_brand_supplier_assignment(assignment_id)
    except Exception as e:
        print(f"Error deleting brand assignment: {e}")

    return _supplier_brands_list_partial(supplier_id)


# @rt("/suppliers/{supplier_id}/brands/{assignment_id}")  # decorator removed; file is archived and not mounted
def patch(supplier_id: str, assignment_id: str, session, is_primary: str = ""):
    """Toggle primary status on a brand-supplier assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "procurement"]):
        return Div("Нет прав", style="color: #dc2626;")

    primary = is_primary in ("true", "on", "True")

    from services.brand_supplier_assignment_service import update_brand_supplier_assignment
    try:
        update_brand_supplier_assignment(assignment_id, is_primary=primary)
    except Exception as e:
        print(f"Error updating brand assignment: {e}")

    return _supplier_brands_list_partial(supplier_id)


# ============================================================================
# SUPPLIER FORM - CREATE/EDIT (Feature UI-002)
# ============================================================================

def _supplier_form(supplier=None, error=None, session=None):
    """
    Render supplier create/edit form.

    Args:
        supplier: Existing Supplier object for edit mode, None for create mode
        error: Error message to display
        session: Session object for page layout
    """
    is_edit = supplier is not None
    title = "Редактирование поставщика" if is_edit else "Новый поставщик"
    action_url = f"/suppliers/{supplier.id}/edit" if is_edit else "/suppliers/new"

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    form_card_style = """
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 24px;
    """

    input_style = """
        width: 100%;
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    """

    label_style = """
        font-size: 12px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
        display: block;
    """

    section_header_style = """
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #e2e8f0;
    """

    return page_layout(title,
        # Error alert
        Div(
            icon("alert-circle", size=16, color="#dc2626"),
            Span(error, style="margin-left: 8px;"),
            style="background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center;"
        ) if error else "",

        # Header card with gradient
        Div(
            Div(
                A(
                    icon("arrow-left", size=16, color="#64748b"),
                    Span("Поставщики", style="margin-left: 6px;"),
                    href="/suppliers",
                    style="display: inline-flex; align-items: center; color: #64748b; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("truck" if not is_edit else "edit", size=24, color="#6366f1"),
                    Span(title, style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    style="display: flex; align-items: center;"
                ),
            ),
            style=header_card_style
        ),

        # Form card
        Div(
            Form(
                # Section: Main info
                Div(
                    icon("building", size=16, color="#64748b"),
                    Span("ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=section_header_style
                ),
                Div(
                    Div(
                        Label("Код поставщика *", style=label_style),
                        Input(
                            name="supplier_code",
                            value=supplier.supplier_code if supplier else "",
                            placeholder="ABC",
                            required=True,
                            maxlength="3",
                            pattern="[A-Z]{3}",
                            title="3 заглавные латинские буквы",
                            style=f"{input_style} text-transform: uppercase; font-family: monospace; font-weight: bold;"
                        ),
                        Small("3 заглавные латинские буквы (например: CMT, RAR)", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Название компании *", style=label_style),
                        Input(
                            name="name",
                            value=supplier.name if supplier else "",
                            placeholder="China Manufacturing Ltd",
                            required=True,
                            style=input_style
                        ),
                        style="flex: 2;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
                ),

                # Section: Location
                Div(
                    icon("map-pin", size=16, color="#64748b"),
                    Span("ЛОКАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Div(
                        Label("Страна", style=label_style),
                        Input(name="country", value=supplier.country if supplier else "", placeholder="Китай", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Город", style=label_style),
                        Input(name="city", value=supplier.city if supplier else "", placeholder="Гуанчжоу", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
                ),

                # Section: Legal info
                Div(
                    icon("file-text", size=16, color="#64748b"),
                    Span("ЮРИДИЧЕСКИЕ ДАННЫЕ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Div(
                        Label("ИНН", style=label_style),
                        Input(name="inn", value=supplier.inn if supplier else "", placeholder="1234567890", pattern="\\d{10}(\\d{2})?", title="10 или 12 цифр", style=input_style),
                        Small("10 цифр для юрлиц, 12 для ИП", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("КПП", style=label_style),
                        Input(name="kpp", value=supplier.kpp if supplier else "", placeholder="123456789", pattern="\\d{9}", title="9 цифр", style=input_style),
                        Small("9 цифр", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
                ),

                # Section: Contact info
                Div(
                    icon("phone", size=16, color="#64748b"),
                    Span("КОНТАКТНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Div(
                        Label("Контактное лицо", style=label_style),
                        Input(name="contact_person", value=supplier.contact_person if supplier else "", placeholder="Иван Иванов", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Email", style=label_style),
                        Input(name="contact_email", type="email", value=supplier.contact_email if supplier else "", placeholder="contact@supplier.com", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Телефон", style=label_style),
                        Input(name="contact_phone", value=supplier.contact_phone if supplier else "", placeholder="+7 999 123 4567", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(style="flex: 1;"),  # Spacer for alignment
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
                ),

                # Section: Payment terms
                Div(
                    icon("credit-card", size=16, color="#64748b"),
                    Span("УСЛОВИЯ РАБОТЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Label("Условия оплаты по умолчанию", style=label_style),
                    Textarea(
                        supplier.default_payment_terms if supplier else "",
                        name="default_payment_terms",
                        placeholder="50% предоплата, 50% по готовности",
                        rows="3",
                        style=f"{input_style} resize: vertical;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Status (for edit mode)
                Div(
                    Div(
                        icon("toggle-left", size=16, color="#64748b"),
                        Span("СТАТУС", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        style=f"{section_header_style} margin-top: 24px;"
                    ),
                    Label(
                        Input(
                            type="checkbox",
                            name="is_active",
                            checked=supplier.is_active if supplier else True,
                            value="true",
                            style="accent-color: #6366f1; margin-right: 8px;"
                        ),
                        Span("Активный поставщик", style="font-size: 14px; color: #1e293b;"),
                        style="display: flex; align-items: center; cursor: pointer;"
                    ),
                    Small("Неактивные поставщики не отображаются в выпадающих списках", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 6px;"),
                ) if is_edit else "",

                # Form actions
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/suppliers" if not is_edit else f"/suppliers/{supplier.id}", variant="secondary", icon_name="x"),
                    style="display: flex; gap: 12px; justify-content: flex-end; padding-top: 20px; margin-top: 24px; border-top: 1px solid #e2e8f0;"
                ),

                method="post",
                action=action_url
            ),
            style=form_card_style
        ),
        session=session
    )


# @rt("/suppliers/{supplier_id}/edit")  # decorator removed; file is archived and not mounted
def get(supplier_id: str, session):
    """Show form to edit an existing supplier."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "procurement"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования поставщиков.", cls="alert alert-error"),
            session=session
        )

    from services.supplier_service import get_supplier

    supplier = get_supplier(supplier_id)

    if not supplier:
        return page_layout("Поставщик не найден",
            Div("Запрашиваемый поставщик не существует.", cls="alert alert-error"),
            btn_link("К списку поставщиков", href="/suppliers", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    return _supplier_form(supplier=supplier, session=session)


# @rt("/suppliers/{supplier_id}/edit")  # decorator removed; file is archived and not mounted
def post(
    supplier_id: str,
    supplier_code: str,
    name: str,
    country: str = "",
    city: str = "",
    inn: str = "",
    kpp: str = "",
    contact_person: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    default_payment_terms: str = "",
    is_active: str = "",
    session=None
):
    """Handle supplier edit form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "procurement"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования поставщиков.", cls="alert alert-error"),
            session=session
        )

    from services.supplier_service import get_supplier, update_supplier, validate_supplier_code

    # Get current supplier for error display
    supplier = get_supplier(supplier_id)
    if not supplier:
        return page_layout("Поставщик не найден",
            Div("Запрашиваемый поставщик не существует.", cls="alert alert-error"),
            session=session
        )

    # Normalize supplier code to uppercase
    supplier_code = supplier_code.strip().upper() if supplier_code else ""

    # Validate supplier code format
    if not supplier_code or not validate_supplier_code(supplier_code):
        return _supplier_form(
            supplier=supplier,
            error="Код поставщика должен состоять из 3 заглавных латинских букв",
            session=session
        )

    try:
        # is_active is "true" if checkbox is checked, "" if not
        is_active_bool = is_active == "true"

        updated_supplier = update_supplier(
            supplier_id=supplier_id,
            name=name.strip(),
            supplier_code=supplier_code,
            country=country.strip() or None,
            city=city.strip() or None,
            inn=inn.strip() or None,
            kpp=kpp.strip() or None,
            contact_person=contact_person.strip() or None,
            contact_email=contact_email.strip() or None,
            contact_phone=contact_phone.strip() or None,
            default_payment_terms=default_payment_terms.strip() or None,
            is_active=is_active_bool,
        )

        if updated_supplier:
            return RedirectResponse(f"/suppliers/{supplier_id}", status_code=303)
        else:
            return _supplier_form(
                supplier=supplier,
                error="Ошибка при обновлении поставщика",
                session=session
            )

    except ValueError as e:
        return _supplier_form(supplier=supplier, error=str(e), session=session)
    except Exception as e:
        print(f"Error updating supplier: {e}")
        return _supplier_form(supplier=supplier, error=f"Ошибка при обновлении: {e}", session=session)


# @rt("/suppliers/{supplier_id}/delete")  # decorator removed; file is archived and not mounted
def post(supplier_id: str, session):
    """Handle supplier deletion (deactivation)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - only admin can delete
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("Только администратор может удалять поставщиков.", cls="alert alert-error"),
            session=session
        )

    from services.supplier_service import deactivate_supplier

    result = deactivate_supplier(supplier_id)

    if result:
        return RedirectResponse("/suppliers", status_code=303)
    else:
        return page_layout("Ошибка",
            Div("Не удалось деактивировать поставщика.", cls="alert alert-error"),
            btn_link("К списку поставщиков", href="/suppliers", variant="secondary", icon_name="arrow-left"),
            session=session
        )

