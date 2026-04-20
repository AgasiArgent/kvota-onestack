"""FastHTML companies area — archived 2026-04-20 during Phase 6C-2B-3.

Includes /companies + /buyer-companies + /seller-companies legacy split.
Replaced by Next.js at https://app.kvotaflow.ru/companies (and children).
Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy these paths back to this Python container.

Contents:
  - GET    /companies                                       — unified page with tabs (seller_companies | buyer_companies)
  - GET    /buyer-companies                                 — legacy shim, redirects to /companies?tab=buyer_companies
  - GET    /buyer-companies/new                             — create form
  - POST   /buyer-companies/new                             — create buyer company
  - GET    /buyer-companies/{company_id}                    — detail view
  - GET    /buyer-companies/{company_id}/edit               — edit form
  - POST   /buyer-companies/{company_id}/edit               — update buyer company
  - POST   /buyer-companies/{company_id}/delete             — deactivate buyer company
  - GET    /seller-companies                                — legacy shim, redirects to /companies?tab=seller_companies
  - GET    /seller-companies/new                            — create form
  - POST   /seller-companies/new                            — create seller company
  - GET    /seller-companies/{company_id}                   — detail view
  - GET    /seller-companies/{company_id}/edit              — edit form
  - POST   /seller-companies/{company_id}/edit              — update seller company
  - POST   /seller-companies/{company_id}/delete            — deactivate seller company
  - helpers: _buyer_company_form, _seller_company_form

Preserved in main.py (NOT archived here):
  - /api/buyer-companies/*   — FastAPI sub-app, consumed by Next.js
  - /api/seller-companies/*  — FastAPI sub-app, consumed by Next.js
  - /api/companies/*         — FastAPI sub-app, consumed by Next.js
  - /customer-contracts/*    — separate area, no Next.js equivalent yet
  - /quotes/.../companies/*  — part of quote detail area (if any)

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_role, get_supabase,
btn, btn_link, icon, SellerCompany model, services.buyer_company_service,
services.seller_company_service, A, Div, Form, H1, Input, Label, Option, P,
Select, Small, Span, Strong, Style, Table, Tbody, Td, Textarea, Th, Thead,
Tr, RedirectResponse), re-apply the @rt decorator, and regenerate tests if
needed. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Div, Form, H1, Input, Label, Option, P, Select, Small, Span, Strong,
    Style, Table, Tbody, Td, Textarea, Th, Thead, Tr,
)
from starlette.responses import RedirectResponse



# ============================================================================
# COMPANIES PAGE (Юрлица) - seller + buyer companies with tabs
# ============================================================================

# @rt("/companies")  # decorator removed; file is archived and not mounted
def get(session, tab: str = "seller_companies"):
    """Companies page with tabs for seller and buyer companies.

    Tabs:
    - seller_companies: Seller companies (юрлица-продажи) - default
    - buyer_companies: Buyer companies (юрлица-закупки)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Tab navigation
    tabs_nav = Div(
        A("Юрлица-продажи",
          href="/companies?tab=seller_companies",
          cls=f"tab-btn {'active' if tab == 'seller_companies' else ''}"),
        A("Юрлица-закупки",
          href="/companies?tab=buyer_companies",
          cls=f"tab-btn {'active' if tab == 'buyer_companies' else ''}"),
        cls="tabs-nav"
    )

    # Build tab content based on selected tab
    if tab == "seller_companies":
        # Get all seller companies
        companies = supabase.table("seller_companies").select("*")\
            .eq("organization_id", org_id)\
            .order("name")\
            .execute()

        companies_data = companies.data if companies.data else []

        company_rows = []
        for company in companies_data:
            status_badge = Span("Активна" if company.get("is_active") else "Неактивна",
                              cls=f"status-badge {'status-approved' if company.get('is_active') else 'status-rejected'}")

            company_rows.append(
                Tr(
                    Td(Strong(company.get("name", "—"))),
                    Td(company.get("supplier_code", "—")),
                    Td(company.get("inn", "—")),
                    Td(company.get("kpp", "—")),
                    Td(company.get("country", "—")),
                    Td(status_badge),
                    Td(
                        A(icon("edit", size=14), href=f"/seller-companies/{company['id']}/edit", title="Редактировать",
                          style="margin-right: 0.5rem;"),
                        A(icon("eye", size=14), href=f"/seller-companies/{company['id']}", title="Просмотр")
                    ),
                    cls="clickable-row",
                    onclick=f"window.location='/seller-companies/{company['id']}'"
                )
            )

        tab_content = Div(
            Div(
                icon("info", size=16), " Компании-продавцы — это наши юридические лица, через которые мы продаём товары клиентам. ",
                "Каждое КП привязывается к одной компании-продавцу.",
                cls="alert alert-info",
                style="margin-bottom: 1rem;"
            ),
            Div(
                btn_link("Добавить компанию-продавца", href="/seller-companies/new", variant="success", icon_name="plus"),
                style="margin-bottom: 1rem;"
            ),
            Table(
                Thead(
                    Tr(
                        Th("Название"),
                        Th("Код"),
                        Th("ИНН"),
                        Th("КПП"),
                        Th("Страна"),
                        Th("Статус"),
                        Th("Действия"),
                    )
                ),
                Tbody(*company_rows) if company_rows else Tbody(
                    Tr(Td("Компании-продавцы не найдены. ", A("Добавить первую компанию", href="/seller-companies/new"),
                           colspan="7", style="text-align: center; padding: 2rem;"))
                )
            ),
            id="tab-content"
        )

    elif tab == "buyer_companies":
        # Get all buyer companies
        companies = supabase.table("buyer_companies").select("*")\
            .eq("organization_id", org_id)\
            .order("name")\
            .execute()

        companies_data = companies.data if companies.data else []

        company_rows = []
        for company in companies_data:
            status_badge = Span("Активна" if company.get("is_active") else "Неактивна",
                              cls=f"status-badge {'status-approved' if company.get('is_active') else 'status-rejected'}")

            company_rows.append(
                Tr(
                    Td(Strong(company.get("name", "—"))),
                    Td(company.get("company_code", "—")),
                    Td(company.get("inn", "—")),
                    Td(company.get("kpp", "—")),
                    Td(company.get("country", "—")),
                    Td(status_badge),
                    Td(
                        A(icon("edit", size=14), href=f"/buyer-companies/{company['id']}/edit", title="Редактировать",
                          style="margin-right: 0.5rem;"),
                        A(icon("eye", size=14), href=f"/buyer-companies/{company['id']}", title="Просмотр")
                    ),
                    cls="clickable-row",
                    onclick=f"window.location='/buyer-companies/{company['id']}'"
                )
            )

        tab_content = Div(
            Div(
                icon("lightbulb", size=16), " Компании-покупатели — наши юрлица, через которые мы закупаем товар у поставщиков. ",
                "Указываются на уровне позиции КП.",
                cls="alert alert-info",
                style="margin-bottom: 1rem;"
            ),
            Div(
                btn_link("Добавить компанию-покупателя", href="/buyer-companies/new", variant="success", icon_name="plus"),
                style="margin-bottom: 1rem;"
            ),
            Table(
                Thead(
                    Tr(
                        Th("Название"),
                        Th("Код"),
                        Th("ИНН"),
                        Th("КПП"),
                        Th("Страна"),
                        Th("Статус"),
                        Th("Действия"),
                    )
                ),
                Tbody(*company_rows) if company_rows else Tbody(
                    Tr(Td("Компании-покупатели не найдены. ", A("Добавить первую компанию", href="/buyer-companies/new"),
                           colspan="7", style="text-align: center; padding: 2rem;"))
                )
            ),
            id="tab-content"
        )

    else:
        tab_content = Div("Неизвестная вкладка", id="tab-content")

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    return page_layout("Юрлица",
        # Header card with gradient
        Div(
            Div(
                icon("building", size=24, color="#475569"),
                Span(" Юрлица", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                style="display: flex; align-items: center;"
            ),
            P("Управление юридическими лицами для продаж и закупок",
              style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;"),
            style=header_card_style
        ),

        # Tabs navigation
        tabs_nav,

        # Tab content
        tab_content,

        # Tab styles (reuse admin tab styles)
        Style("""
            .tabs-nav {
                display: flex;
                gap: 4px;
                padding: 0 4px;
                margin-bottom: 20px;
                border-bottom: 1px solid #e2e8f0;
                background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
                padding: 12px 16px 0 16px;
                border-radius: 12px 12px 0 0;
            }

            .tab-btn {
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

            .tab-btn:hover {
                color: #1e293b;
                background: rgba(255,255,255,0.5);
            }

            .tab-btn.active {
                color: #1e293b;
                background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
                border-color: #e2e8f0;
                font-weight: 600;
                box-shadow: 0 -2px 8px rgba(0,0,0,0.04);
            }
        """),

        session=session
    )


# ============================================================================
# BUYER COMPANIES LIST - Redirect to /companies page
# ============================================================================

# @rt("/buyer-companies")  # decorator removed; file is archived and not mounted
def get(session):
    """Redirect standalone buyer companies list to unified /companies page."""
    return RedirectResponse("/companies?tab=buyer_companies", status_code=303)


# @rt("/buyer-companies/new")  # decorator removed; file is archived and not mounted
def get(session):
    """Show form to create a new buyer company."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания компаний-покупателей. Требуется роль: admin", cls="alert alert-error"),
            session=session
        )

    return _buyer_company_form(session=session)


# @rt("/buyer-companies/new")  # decorator removed; file is archived and not mounted
def post(
    company_code: str,
    name: str,
    country: str = "Россия",
    region: str = "",
    inn: str = "",
    kpp: str = "",
    ogrn: str = "",
    registration_address: str = "",
    general_director_position: str = "Генеральный директор",
    general_director_name: str = "",
    session=None
):
    """Handle buyer company creation form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания компаний-покупателей.", cls="alert alert-error"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")
    user_id = user.get("id")

    from services.buyer_company_service import (
        create_buyer_company, validate_company_code, validate_inn, validate_kpp, validate_ogrn
    )

    # Normalize company code to uppercase
    company_code = company_code.strip().upper() if company_code else ""

    # Validate company code format
    if not company_code or not validate_company_code(company_code):
        return _buyer_company_form(
            error="Код компании должен состоять из 3 заглавных латинских букв",
            session=session
        )

    # Validate INN (required for buyer companies)
    inn_clean = inn.strip() if inn else ""
    if not inn_clean:
        return _buyer_company_form(
            error="ИНН обязателен для компании-покупателя",
            session=session
        )
    if not validate_inn(inn_clean):
        return _buyer_company_form(
            error="ИНН должен состоять из 10 цифр (для юридического лица)",
            session=session
        )

    # Validate KPP (optional)
    kpp_clean = kpp.strip() if kpp else ""
    if kpp_clean and not validate_kpp(kpp_clean):
        return _buyer_company_form(
            error="КПП должен состоять из 9 цифр",
            session=session
        )

    # Validate OGRN (optional)
    ogrn_clean = ogrn.strip() if ogrn else ""
    if ogrn_clean and not validate_ogrn(ogrn_clean):
        return _buyer_company_form(
            error="ОГРН должен состоять из 13 цифр",
            session=session
        )

    try:
        company = create_buyer_company(
            organization_id=org_id,
            name=name.strip(),
            company_code=company_code,
            country=country.strip() or "Россия",
            region=region.strip() or None,
            inn=inn_clean,
            kpp=kpp_clean or None,
            ogrn=ogrn_clean or None,
            registration_address=registration_address.strip() or None,
            general_director_position=general_director_position.strip() or "Генеральный директор",
            general_director_name=general_director_name.strip() or None,
            is_active=True,
            created_by=user_id,
        )

        if company:
            return RedirectResponse(f"/buyer-companies/{company.id}", status_code=303)
        else:
            return _buyer_company_form(
                error="Компания с таким кодом или ИНН уже существует",
                session=session
            )

    except ValueError as e:
        return _buyer_company_form(error=str(e), session=session)
    except Exception as e:
        print(f"Error creating buyer company: {e}")
        return _buyer_company_form(error=f"Ошибка при создании: {e}", session=session)


# @rt("/buyer-companies/{company_id}")  # decorator removed; file is archived and not mounted
def get(company_id: str, session):
    """View single buyer company details."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра компаний-покупателей.", cls="alert alert-error"),
            session=session
        )

    from services.buyer_company_service import get_buyer_company

    company = get_buyer_company(company_id)

    if not company:
        return page_layout("Компания не найдена",
            Div(
                H1(icon("x-circle", size=28), " Компания не найдена", cls="page-header"),
                P("Запрашиваемая компания-покупатель не существует."),
                btn_link("К списку компаний", href="/companies?tab=buyer_companies", variant="secondary", icon_name="arrow-left"),
                cls="card"
            ),
            session=session
        )

    status_text = "Активна" if company.is_active else "Неактивна"

    return page_layout(f"Компания: {company.name}",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Компании-покупатели", href="/companies?tab=buyer_companies",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Div(
                        icon("building-2", size=24, color="#8b5cf6"),
                        H1(company.name, style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        Span(company.company_code, style="font-family: monospace; font-size: 14px; padding: 4px 10px; background: #f3e8ff; color: #7c3aed; border-radius: 6px; font-weight: 600;"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    Div(
                        Span(status_text, style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: {'#16a34a' if company.is_active else '#dc2626'}; background: {'#dcfce7' if company.is_active else '#fee2e2'};"),
                        btn_link("Редактировать", href=f"/buyer-companies/{company_id}/edit", variant="secondary", icon_name="edit", size="sm"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Main info cards grid
        Div(
            # Card 1: Company Info
            Div(
                Div(
                    icon("building", size=16, color="#64748b"),
                    Span("ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("Код компании", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.company_code, style="font-weight: 600; color: #7c3aed; font-family: monospace; font-size: 16px;"),
                    ),
                    Div(
                        Span("Название", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.name, style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("Страна", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.country or "Россия", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    style="display: grid; gap: 12px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            # Card 2: Director
            Div(
                Div(
                    icon("user", size=16, color="#64748b"),
                    Span("РУКОВОДСТВО", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("Должность", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.general_director_position or "Генеральный директор", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("ФИО", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.general_director_name or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    style="display: grid; gap: 12px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;"
        ),

        # Legal info
        Div(
            Div(
                icon("file-text", size=16, color="#64748b"),
                Span("ЮРИДИЧЕСКИЕ ДАННЫЕ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    Span("ИНН", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(company.inn or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                Div(
                    Span("КПП", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(company.kpp or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                Div(
                    Span("ОГРН", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(company.ogrn or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px;"
            ),
            style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Registration address
        Div(
            Div(
                icon("map-pin", size=16, color="#64748b"),
                Span("ЮРИДИЧЕСКИЙ АДРЕС", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;"
            ),
            P(company.registration_address or "Не указан", style="font-size: 14px; color: #1e293b; margin: 0;"),
            style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if company.registration_address else "",

        # Metadata
        Div(
            Div(
                Span("Создана", style="font-size: 11px; color: #94a3b8; text-transform: uppercase;"),
                Span(f"{company.created_at.strftime('%d.%m.%Y %H:%M') if company.created_at else '—'}", style="font-size: 13px; color: #64748b; margin-left: 8px;"),
                style="display: flex; align-items: center; gap: 4px;"
            ),
            Div(
                Span("Обновлена", style="font-size: 11px; color: #94a3b8; text-transform: uppercase;"),
                Span(f"{company.updated_at.strftime('%d.%m.%Y %H:%M') if company.updated_at else '—'}", style="font-size: 13px; color: #64748b; margin-left: 8px;"),
                style="display: flex; align-items: center; gap: 4px;"
            ),
            style="display: flex; gap: 24px; padding: 12px 0; border-top: 1px solid #e2e8f0;"
        ),

        session=session
    )


# ============================================================================
# BUYER COMPANY FORM (Feature UI-004)
# ============================================================================

def _buyer_company_form(company=None, error=None, session=None):
    """
    Render buyer company create/edit form.

    Args:
        company: Existing BuyerCompany object for edit mode, None for create mode
        error: Error message to display
        session: Session object for page layout
    """
    is_edit = company is not None
    title = "Редактирование компании-покупателя" if is_edit else "Новая компания-покупатель"
    action_url = f"/buyer-companies/{company.id}/edit" if is_edit else "/buyer-companies/new"

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
                    Span("Компании-покупатели", style="margin-left: 6px;"),
                    href="/companies?tab=buyer_companies",
                    style="display: inline-flex; align-items: center; color: #64748b; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("building-2" if not is_edit else "edit", size=24, color="#3b82f6"),
                    Span(title, style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    style="display: flex; align-items: center;"
                ),
            ),
            style=header_card_style
        ),

        # Info alert
        Div(
            icon("lightbulb", size=16, color="#0369a1"),
            Span(" Компания-покупатель — наше юридическое лицо, через которое мы закупаем товар у поставщиков. Привязывается к позиции КП.", style="margin-left: 8px;"),
            style="background: #f0f9ff; border: 1px solid #bae6fd; color: #0369a1; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center;"
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
                        Label("Код компании *", style=label_style),
                        Input(
                            name="company_code",
                            value=company.company_code if company else "",
                            placeholder="ZAK",
                            required=True,
                            maxlength="3",
                            pattern="[A-Z]{3}",
                            title="3 заглавные латинские буквы",
                            style=f"{input_style} text-transform: uppercase; font-family: monospace; font-weight: bold;"
                        ),
                        Small("3 заглавные латинские буквы (например: ZAK, CMT)", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Название компании *", style=label_style),
                        Input(name="name", value=company.name if company else "", placeholder='ООО "Закупки"', required=True, style=input_style),
                        style="flex: 2;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Страна", style=label_style),
                        Input(name="country", value=company.country if company else "Россия", placeholder="Россия", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Регион (для валютных инвойсов)", style=label_style),
                        Select(
                            Option("-- Не указан --", value="", selected=not (company and getattr(company, 'region', None))),
                            Option("EU", value="EU", selected=(getattr(company, 'region', None) == "EU") if company else False),
                            Option("TR", value="TR", selected=(getattr(company, 'region', None) == "TR") if company else False),
                            name="region",
                            style=input_style
                        ),
                        Small("EU = европейская компания, TR = турецкая компания", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
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
                        Label("ИНН *", style=label_style),
                        Input(name="inn", value=company.inn if company else "", placeholder="1234567890", pattern="\\d{10}", title="10 цифр для юридического лица", required=True, style=input_style),
                        Small("10 цифр (ИНН юридического лица)", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("КПП", style=label_style),
                        Input(name="kpp", value=company.kpp if company else "", placeholder="123456789", pattern="\\d{9}", title="9 цифр", style=input_style),
                        Small("9 цифр", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("ОГРН", style=label_style),
                        Input(name="ogrn", value=company.ogrn if company else "", placeholder="1234567890123", pattern="\\d{13}", title="13 цифр", style=input_style),
                        Small("13 цифр", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(style="flex: 1;"),  # Spacer
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
                ),

                # Section: Registration address
                Div(
                    icon("map-pin", size=16, color="#64748b"),
                    Span("ЮРИДИЧЕСКИЙ АДРЕС", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Label("Адрес регистрации", style=label_style),
                    Textarea(
                        company.registration_address if company else "",
                        name="registration_address",
                        placeholder="123456, г. Москва, ул. Примерная, д. 1",
                        rows="2",
                        style=f"{input_style} resize: vertical;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Section: Director info
                Div(
                    icon("user", size=16, color="#64748b"),
                    Span("РУКОВОДСТВО (ДЛЯ ДОКУМЕНТОВ)", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Div(
                        Label("Должность руководителя", style=label_style),
                        Input(name="general_director_position", value=company.general_director_position if company else "Генеральный директор", placeholder="Генеральный директор", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("ФИО руководителя", style=label_style),
                        Input(name="general_director_name", value=company.general_director_name if company else "", placeholder="Иванов Иван Иванович", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
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
                            checked=company.is_active if company else True,
                            value="true",
                            style="accent-color: #3b82f6; margin-right: 8px;"
                        ),
                        Span("Активная компания", style="font-size: 14px; color: #1e293b;"),
                        style="display: flex; align-items: center; cursor: pointer;"
                    ),
                    Small("Неактивные компании не отображаются в выпадающих списках", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 6px;"),
                ) if is_edit else "",

                # Form actions
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/companies?tab=buyer_companies" if not is_edit else f"/buyer-companies/{company.id}", variant="secondary", icon_name="x"),
                    style="display: flex; gap: 12px; justify-content: flex-end; padding-top: 20px; margin-top: 24px; border-top: 1px solid #e2e8f0;"
                ),

                method="post",
                action=action_url
            ),
            style=form_card_style
        ),
        session=session
    )


# @rt("/buyer-companies/{company_id}/edit")  # decorator removed; file is archived and not mounted
def get(company_id: str, session):
    """Show form to edit an existing buyer company."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования компаний-покупателей.", cls="alert alert-error"),
            session=session
        )

    from services.buyer_company_service import get_buyer_company

    company = get_buyer_company(company_id)

    if not company:
        return page_layout("Компания не найдена",
            Div("Запрашиваемая компания-покупатель не существует.", cls="alert alert-error"),
            btn_link("К списку компаний", href="/companies?tab=buyer_companies", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    return _buyer_company_form(company=company, session=session)


# @rt("/buyer-companies/{company_id}/edit")  # decorator removed; file is archived and not mounted
def post(
    company_id: str,
    company_code: str,
    name: str,
    country: str = "Россия",
    region: str = "",
    inn: str = "",
    kpp: str = "",
    ogrn: str = "",
    registration_address: str = "",
    general_director_position: str = "Генеральный директор",
    general_director_name: str = "",
    is_active: str = "",
    session=None
):
    """Handle buyer company edit form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования компаний-покупателей.", cls="alert alert-error"),
            session=session
        )

    from services.buyer_company_service import (
        get_buyer_company, update_buyer_company, validate_company_code,
        validate_inn, validate_kpp, validate_ogrn
    )

    company = get_buyer_company(company_id)
    if not company:
        return page_layout("Компания не найдена",
            Div("Запрашиваемая компания-покупатель не существует.", cls="alert alert-error"),
            btn_link("К списку компаний", href="/companies?tab=buyer_companies", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Normalize company code to uppercase
    company_code = company_code.strip().upper() if company_code else ""

    # Validate company code format
    if not company_code or not validate_company_code(company_code):
        return _buyer_company_form(
            company=company,
            error="Код компании должен состоять из 3 заглавных латинских букв",
            session=session
        )

    # Validate INN (required)
    inn_clean = inn.strip() if inn else ""
    if not inn_clean:
        return _buyer_company_form(
            company=company,
            error="ИНН обязателен для компании-покупателя",
            session=session
        )
    if not validate_inn(inn_clean):
        return _buyer_company_form(
            company=company,
            error="ИНН должен состоять из 10 цифр (для юридического лица)",
            session=session
        )

    # Validate KPP (optional)
    kpp_clean = kpp.strip() if kpp else ""
    if kpp_clean and not validate_kpp(kpp_clean):
        return _buyer_company_form(
            company=company,
            error="КПП должен состоять из 9 цифр",
            session=session
        )

    # Validate OGRN (optional)
    ogrn_clean = ogrn.strip() if ogrn else ""
    if ogrn_clean and not validate_ogrn(ogrn_clean):
        return _buyer_company_form(
            company=company,
            error="ОГРН должен состоять из 13 цифр",
            session=session
        )

    # Checkbox handling: is_active
    active = is_active == "true"

    try:
        updated = update_buyer_company(
            company_id=company_id,
            name=name.strip(),
            company_code=company_code,
            country=country.strip() or "Россия",
            region=region.strip() or None,
            inn=inn_clean,
            kpp=kpp_clean or None,
            ogrn=ogrn_clean or None,
            registration_address=registration_address.strip() or None,
            general_director_position=general_director_position.strip() or "Генеральный директор",
            general_director_name=general_director_name.strip() or None,
            is_active=active,
        )

        if updated:
            return RedirectResponse(f"/buyer-companies/{company_id}", status_code=303)
        else:
            return _buyer_company_form(
                company=company,
                error="Не удалось обновить компанию. Возможно, код или ИНН уже используются другой компанией.",
                session=session
            )

    except ValueError as e:
        return _buyer_company_form(company=company, error=str(e), session=session)
    except Exception as e:
        print(f"Error updating buyer company: {e}")
        return _buyer_company_form(company=company, error=f"Ошибка при обновлении: {e}", session=session)


# @rt("/buyer-companies/{company_id}/delete")  # decorator removed; file is archived and not mounted
def post(company_id: str, session):
    """Handle buyer company deletion (soft delete - deactivate)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("Только администратор может удалять компании-покупатели.", cls="alert alert-error"),
            session=session
        )

    from services.buyer_company_service import deactivate_buyer_company

    result = deactivate_buyer_company(company_id)

    if result:
        return RedirectResponse("/companies?tab=buyer_companies", status_code=303)
    else:
        return page_layout("Ошибка",
            Div("Не удалось деактивировать компанию.", cls="alert alert-error"),
            btn_link("К списку компаний", href="/companies?tab=buyer_companies", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# ============================================================================
# SELLER COMPANIES MANAGEMENT (UI-005, UI-006)
# ============================================================================

# @rt("/seller-companies")  # decorator removed; file is archived and not mounted
def get(session):
    """Redirect standalone seller companies list to unified /companies page."""
    return RedirectResponse("/companies?tab=seller_companies", status_code=303)


# @rt("/seller-companies/new")  # decorator removed; file is archived and not mounted
def get(session):
    """Show form to create a new seller company."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания компаний-продавцов. Требуется роль: admin", cls="alert alert-error"),
            session=session
        )

    return _seller_company_form(session=session)


# @rt("/seller-companies/new")  # decorator removed; file is archived and not mounted
def post(
    supplier_code: str,
    name: str,
    country: str = "Россия",
    inn: str = "",
    kpp: str = "",
    ogrn: str = "",
    registration_address: str = "",
    general_director_position: str = "Генеральный директор",
    general_director_name: str = "",
    session=None
):
    """Handle seller company creation form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания компаний-продавцов.", cls="alert alert-error"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")
    user_id = user.get("id")

    from services.seller_company_service import (
        create_seller_company, validate_supplier_code, validate_inn, validate_kpp, validate_ogrn
    )

    # Normalize supplier code to uppercase
    supplier_code = supplier_code.strip().upper() if supplier_code else ""

    # Validate supplier code format
    if not supplier_code or not validate_supplier_code(supplier_code):
        return _seller_company_form(
            error="Код компании должен состоять из 3 заглавных латинских букв (например, MBR, CMT, GES)",
            session=session
        )

    # Validate INN (optional but if provided must be valid)
    inn_clean = inn.strip() if inn else ""
    if inn_clean and not validate_inn(inn_clean):
        return _seller_company_form(
            error="ИНН должен состоять из 10 цифр (юрлицо) или 12 цифр (ИП)",
            session=session
        )

    # Validate KPP (optional)
    kpp_clean = kpp.strip() if kpp else ""
    if kpp_clean and not validate_kpp(kpp_clean):
        return _seller_company_form(
            error="КПП должен состоять из 9 цифр",
            session=session
        )

    # Validate OGRN (optional)
    ogrn_clean = ogrn.strip() if ogrn else ""
    if ogrn_clean and not validate_ogrn(ogrn_clean):
        return _seller_company_form(
            error="ОГРН должен состоять из 13 цифр (юрлицо) или 15 цифр (ИП)",
            session=session
        )

    try:
        company = create_seller_company(
            organization_id=org_id,
            name=name.strip(),
            supplier_code=supplier_code,
            country=country.strip() or "Россия",
            inn=inn_clean or None,
            kpp=kpp_clean or None,
            ogrn=ogrn_clean or None,
            registration_address=registration_address.strip() or None,
            general_director_position=general_director_position.strip() or "Генеральный директор",
            general_director_name=general_director_name.strip() or None,
            is_active=True,
            created_by=user_id,
        )

        if company:
            return RedirectResponse(f"/seller-companies/{company.id}", status_code=303)
        else:
            return _seller_company_form(
                error="Компания с таким кодом или ИНН уже существует",
                session=session
            )

    except ValueError as e:
        return _seller_company_form(error=str(e), session=session)
    except Exception as e:
        print(f"Error creating seller company: {e}")
        return _seller_company_form(error=f"Ошибка при создании: {e}", session=session)


# @rt("/seller-companies/{company_id}")  # decorator removed; file is archived and not mounted
def get(company_id: str, session):
    """Seller company detail view page."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра данной страницы.", cls="alert alert-error"),
            session=session
        )

    from services.seller_company_service import get_seller_company

    company = get_seller_company(company_id)
    if not company:
        return page_layout("Не найдено",
            Div("Компания-продавец не найдена.", cls="alert alert-error"),
            btn_link("К списку компаний", href="/companies?tab=seller_companies", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    status_text = "Активна" if company.is_active else "Неактивна"

    return page_layout(f"Компания: {company.name}",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Компании-продавцы", href="/companies?tab=seller_companies",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Div(
                        icon("building-2", size=24, color="#f97316"),
                        H1(company.name, style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        Span(company.supplier_code, style="font-family: monospace; font-size: 14px; padding: 4px 10px; background: #fff7ed; color: #ea580c; border-radius: 6px; font-weight: 600;"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    Div(
                        Span(status_text, style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: {'#16a34a' if company.is_active else '#dc2626'}; background: {'#dcfce7' if company.is_active else '#fee2e2'};"),
                        btn_link("Редактировать", href=f"/seller-companies/{company_id}/edit", variant="secondary", icon_name="edit", size="sm"),
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Main info cards grid
        Div(
            # Card 1: Company Info
            Div(
                Div(
                    icon("building", size=16, color="#64748b"),
                    Span("ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("Код компании", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.supplier_code, style="font-weight: 600; color: #ea580c; font-family: monospace; font-size: 16px;"),
                    ),
                    Div(
                        Span("Название", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.name, style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("Страна", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.country or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    style="display: grid; gap: 12px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            # Card 2: Director
            Div(
                Div(
                    icon("user", size=16, color="#64748b"),
                    Span("РУКОВОДИТЕЛЬ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("ФИО директора", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.general_director_name or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("Должность", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(company.general_director_position or "Генеральный директор", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    style="display: grid; gap: 12px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;"
        ),

        # Legal info
        Div(
            Div(
                icon("file-text", size=16, color="#64748b"),
                Span("ЮРИДИЧЕСКИЕ РЕКВИЗИТЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    Span("ИНН", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(company.inn or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                Div(
                    Span("КПП", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(company.kpp or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                Div(
                    Span("ОГРН", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(company.ogrn or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                ),
                style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; margin-bottom: 16px;"
            ),
            Div(
                Span("Юридический адрес", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                Div(company.registration_address or "—", style="font-weight: 500; color: #1e293b; font-size: 14px; margin-top: 4px;"),
            ),
            style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        session=session
    )


# -----------------------------------------------------------------------------
# UI-006: Seller Company Form (Create/Edit)
# -----------------------------------------------------------------------------

def _seller_company_form(
    company: "SellerCompany | None" = None,
    error: str = "",
    session=None
):
    """
    Render create/edit form for seller companies.

    Args:
        company: Existing company (for edit mode), None for create mode
        error: Error message to display
        session: User session

    Returns:
        Page layout with seller company form
    """
    is_edit = company is not None
    title = f"Редактировать: {company.name}" if is_edit else "Новая компания-продавец"
    action_url = f"/seller-companies/{company.id}/edit" if is_edit else "/seller-companies/new"

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        border-radius: 12px;
        border: 1px solid #fde68a;
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

        # Header card with gradient (orange theme for seller)
        Div(
            Div(
                A(
                    icon("arrow-left", size=16, color="#92400e"),
                    Span("Компании-продавцы", style="margin-left: 6px;"),
                    href="/companies?tab=seller_companies",
                    style="display: inline-flex; align-items: center; color: #92400e; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("store" if not is_edit else "edit", size=24, color="#d97706"),
                    Span(title, style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    style="display: flex; align-items: center;"
                ),
            ),
            style=header_card_style
        ),

        # Info alert
        Div(
            icon("lightbulb", size=16, color="#0369a1"),
            Span(" Компания-продавец — это наше юридическое лицо, от имени которого мы продаём товары клиентам. Код компании (3 буквы) используется для генерации IDN коммерческого предложения.", style="margin-left: 8px;"),
            style="background: #f0f9ff; border: 1px solid #bae6fd; color: #0369a1; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center;"
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
                        Label("Код компании *", style=label_style),
                        Input(
                            name="supplier_code",
                            value=company.supplier_code if company else "",
                            placeholder="MBR",
                            pattern="[A-Za-z]{3}",
                            maxlength="3",
                            required=True,
                            title="3 буквы латиницей (например, MBR, CMT, GES)",
                            style=f"{input_style} text-transform: uppercase; font-family: monospace; font-weight: bold;"
                        ),
                        Small("3 буквы латиницей (используется в IDN)", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Название компании *", style=label_style),
                        Input(name="name", value=company.name if company else "", placeholder="ООО «МАСТЕР БЭРИНГ»", required=True, style=input_style),
                        style="flex: 2;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Страна", style=label_style),
                        Input(name="country", value=company.country if company else "Россия", placeholder="Россия", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(style="flex: 1;"),  # Spacer
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
                ),

                # Section: Legal info
                Div(
                    icon("file-text", size=16, color="#64748b"),
                    Span("ЮРИДИЧЕСКИЕ РЕКВИЗИТЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                # Info note about legal IDs
                Div(
                    icon("info", size=14, color="#0369a1"),
                    Span(" ИНН: 10 цифр для юрлиц, 12 цифр для ИП. ОГРН: 13 цифр для юрлиц, 15 цифр для ИП.", style="margin-left: 6px;"),
                    style="background: #f0f9ff; color: #0369a1; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; display: flex; align-items: center;"
                ),
                Div(
                    Div(
                        Label("ИНН", style=label_style),
                        Input(name="inn", value=company.inn if company else "", placeholder="1234567890 или 123456789012", pattern="\\d{10}|\\d{12}", title="10 цифр для юрлица или 12 цифр для ИП", style=input_style),
                        Small("10 цифр (юрлицо) или 12 цифр (ИП)", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("КПП", style=label_style),
                        Input(name="kpp", value=company.kpp if company else "", placeholder="123456789", pattern="\\d{9}", title="9 цифр (только для юрлиц)", style=input_style),
                        Small("9 цифр (только для юрлиц)", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("ОГРН", style=label_style),
                        Input(name="ogrn", value=company.ogrn if company else "", placeholder="1234567890123 или 123456789012345", pattern="\\d{13}|\\d{15}", title="13 цифр для юрлица или 15 цифр для ИП", style=input_style),
                        Small("13 цифр (юрлицо) или 15 цифр (ИП)", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(style="flex: 1;"),  # Spacer
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
                ),

                # Section: Registration address
                Div(
                    icon("map-pin", size=16, color="#64748b"),
                    Span("ЮРИДИЧЕСКИЙ АДРЕС", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Label("Адрес регистрации", style=label_style),
                    Textarea(
                        company.registration_address if company else "",
                        name="registration_address",
                        placeholder="123456, г. Москва, ул. Примерная, д. 1, офис 100",
                        rows="2",
                        style=f"{input_style} resize: vertical;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Section: Director info
                Div(
                    icon("user", size=16, color="#64748b"),
                    Span("РУКОВОДСТВО (ДЛЯ ДОКУМЕНТОВ)", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Div(
                        Label("Должность руководителя", style=label_style),
                        Input(name="general_director_position", value=company.general_director_position if company else "Генеральный директор", placeholder="Генеральный директор", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("ФИО руководителя", style=label_style),
                        Input(name="general_director_name", value=company.general_director_name if company else "", placeholder="Иванов Иван Иванович", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 20px;"
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
                            checked=company.is_active if company else True,
                            value="true",
                            style="accent-color: #d97706; margin-right: 8px;"
                        ),
                        Span("Активная компания", style="font-size: 14px; color: #1e293b;"),
                        style="display: flex; align-items: center; cursor: pointer;"
                    ),
                    Small("Неактивные компании не отображаются в выпадающих списках при создании КП", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 6px;"),
                ) if is_edit else "",

                # Form actions
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/companies?tab=seller_companies" if not is_edit else f"/seller-companies/{company.id}", variant="secondary", icon_name="x"),
                    style="display: flex; gap: 12px; justify-content: flex-end; padding-top: 20px; margin-top: 24px; border-top: 1px solid #e2e8f0;"
                ),

                method="post",
                action=action_url
            ),
            cls="card"
        ),
        session=session
    )


# @rt("/seller-companies/{company_id}/edit")  # decorator removed; file is archived and not mounted
def get(company_id: str, session):
    """Show form to edit an existing seller company."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования компаний-продавцов.", cls="alert alert-error"),
            session=session
        )

    from services.seller_company_service import get_seller_company

    company = get_seller_company(company_id)

    if not company:
        return page_layout("Компания не найдена",
            Div("Запрашиваемая компания-продавец не существует.", cls="alert alert-error"),
            btn_link("К списку компаний", href="/companies?tab=seller_companies", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    return _seller_company_form(company=company, session=session)


# @rt("/seller-companies/{company_id}/edit")  # decorator removed; file is archived and not mounted
def post(
    company_id: str,
    supplier_code: str,
    name: str,
    country: str = "Россия",
    inn: str = "",
    kpp: str = "",
    ogrn: str = "",
    registration_address: str = "",
    general_director_position: str = "Генеральный директор",
    general_director_name: str = "",
    is_active: str = "",
    session=None
):
    """Handle seller company edit form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования компаний-продавцов.", cls="alert alert-error"),
            session=session
        )

    from services.seller_company_service import (
        get_seller_company, update_seller_company, validate_supplier_code,
        validate_inn, validate_kpp, validate_ogrn
    )

    company = get_seller_company(company_id)
    if not company:
        return page_layout("Компания не найдена",
            Div("Запрашиваемая компания-продавец не существует.", cls="alert alert-error"),
            btn_link("К списку компаний", href="/companies?tab=seller_companies", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Normalize supplier code to uppercase
    supplier_code = supplier_code.strip().upper() if supplier_code else ""

    # Validate supplier code format
    if not supplier_code or not validate_supplier_code(supplier_code):
        return _seller_company_form(
            company=company,
            error="Код компании должен состоять из 3 заглавных латинских букв (например, MBR, CMT, GES)",
            session=session
        )

    # Validate INN (optional)
    inn_clean = inn.strip() if inn else ""
    if inn_clean and not validate_inn(inn_clean):
        return _seller_company_form(
            company=company,
            error="ИНН должен состоять из 10 цифр (юрлицо) или 12 цифр (ИП)",
            session=session
        )

    # Validate KPP (optional)
    kpp_clean = kpp.strip() if kpp else ""
    if kpp_clean and not validate_kpp(kpp_clean):
        return _seller_company_form(
            company=company,
            error="КПП должен состоять из 9 цифр",
            session=session
        )

    # Validate OGRN (optional)
    ogrn_clean = ogrn.strip() if ogrn else ""
    if ogrn_clean and not validate_ogrn(ogrn_clean):
        return _seller_company_form(
            company=company,
            error="ОГРН должен состоять из 13 цифр (юрлицо) или 15 цифр (ИП)",
            session=session
        )

    # Checkbox handling: is_active
    active = is_active == "true"

    try:
        updated = update_seller_company(
            company_id=company_id,
            name=name.strip(),
            supplier_code=supplier_code,
            country=country.strip() or "Россия",
            inn=inn_clean or None,
            kpp=kpp_clean or None,
            ogrn=ogrn_clean or None,
            registration_address=registration_address.strip() or None,
            general_director_position=general_director_position.strip() or "Генеральный директор",
            general_director_name=general_director_name.strip() or None,
            is_active=active,
        )

        if updated:
            return RedirectResponse(f"/seller-companies/{company_id}", status_code=303)
        else:
            return _seller_company_form(
                company=company,
                error="Не удалось обновить компанию. Возможно, код или ИНН уже используются другой компанией.",
                session=session
            )

    except ValueError as e:
        return _seller_company_form(company=company, error=str(e), session=session)
    except Exception as e:
        print(f"Error updating seller company: {e}")
        return _seller_company_form(company=company, error=f"Ошибка при обновлении: {e}", session=session)


# @rt("/seller-companies/{company_id}/delete")  # decorator removed; file is archived and not mounted
def post(company_id: str, session):
    """Handle seller company deletion (soft delete - deactivate)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("Только администратор может удалять компании-продавцы.", cls="alert alert-error"),
            session=session
        )

    from services.seller_company_service import deactivate_seller_company

    result = deactivate_seller_company(company_id)

    if result:
        return RedirectResponse("/companies?tab=seller_companies", status_code=303)
    else:
        return page_layout("Ошибка",
            Div("Не удалось деактивировать компанию.", cls="alert alert-error"),
            btn_link("К списку компаний", href="/companies?tab=seller_companies", variant="secondary", icon_name="arrow-left"),
            session=session
        )

