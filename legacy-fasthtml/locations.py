"""FastHTML /locations area — archived 2026-04-20 during Phase 6C-2B-9.

Superseded by Next.js locations management flow. Routes unreachable
post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru, which doesn't proxy
/locations/* back to this Python container.

Contents (7 @rt routes + 1 exclusive helper, ~888 LOC):

Routes archived:
  - GET  /locations                           — Registry with search + filters
  - GET  /locations/new                       — Create form
  - POST /locations/new                       — Create submit
  - GET  /locations/{location_id}             — Detail view
  - GET  /locations/{location_id}/edit        — Edit form
  - POST /locations/{location_id}/edit        — Edit submit
  - POST /locations/{location_id}/delete      — Soft-delete (deactivate)

Helper exclusive to /locations (archived here):
  - _location_form   — shared create/edit form renderer (called only by the
                       archived GET/POST handlers)

DELETED SEPARATELY (not archived here, per user directive 2026-04-20):
  - GET /locations/seed                       — bootstrap endpoint that seeded
    default locations via services.location_service.seed_default_locations.
    Only useful in fresh-install scenarios — not production. User confirmed
    "удаляем" over archive. The handler + decorator were deleted entirely
    from main.py in the same PR. The underlying service function
    `seed_default_locations` in services/location_service.py is PRESERVED
    (still covered by tests/test_location_service.py and may be called from
    admin tooling / future FastAPI endpoints).

Preserved in main.py (NOT archived):
  - services/location_service.py — full service layer (get_all_locations,
    get_location, create_location, update_location, deactivate_location,
    validate_location_code, validate_country, seed_default_locations,
    get_unique_countries, get_location_stats, search_locations) still alive,
    consumed by supplier/seller-company services, tests, and future FastAPI.

NOT including (separate archive decisions):
  - /supplier-invoices/* — separate area, not yet archived
  - services/location_service.py — service layer still live

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_any_role, user_has_role,
btn, btn_link, icon, fasthtml components, starlette RedirectResponse,
services.location_service.*), re-apply the @rt decorator, and regenerate
tests if needed. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Br, Button, Div, Form, H1, Input, Label, Option, P, Select, Small,
    Span, Strong, Table, Tbody, Td, Textarea, Th, Thead, Tr,
)
from starlette.responses import RedirectResponse


# ============================================================================
# UI-010: Locations Directory Page
# ============================================================================

@rt("/locations")
def get(session, q: str = "", country: str = "", type_filter: str = "", status: str = ""):
    """
    Locations directory page with search and filters.

    Locations are pickup/delivery points used in quote_items (pickup_location_id).
    Includes hubs (logistics centers) and customs clearance points.

    Query Parameters:
        q: Search query (matches code, city, country)
        country: Filter by country
        type_filter: Filter by type ("hub", "customs", or "" for all)
        status: Filter by status ("active", "inactive", or "" for all)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin, logistics, customs, procurement can view locations
    if not user_has_any_role(session, ["admin", "logistics", "customs", "procurement"]):
        return page_layout("Access Denied",
            Div(
                H1("⛔ Доступ запрещён"),
                P("У вас нет прав для просмотра справочника локаций."),
                P("Требуется одна из ролей: admin, logistics, customs, procurement"),
                btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
                cls="card"
            ),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    # Import location service functions
    from services.location_service import (
        get_all_locations, search_locations, get_unique_countries, get_location_stats
    )

    # Get locations based on filters
    try:
        # Determine hub/customs filters
        is_hub = True if type_filter == "hub" else None
        is_customs = True if type_filter == "customs" else None
        is_active = None
        if status == "active":
            is_active = True
        elif status == "inactive":
            is_active = False

        if q and q.strip():
            # Use search if query provided
            locations = search_locations(
                organization_id=org_id,
                query=q.strip(),
                is_hub_only=(type_filter == "hub"),
                is_customs_only=(type_filter == "customs"),
                limit=100
            )
            # Filter by country and status after search if needed
            if country:
                locations = [loc for loc in locations if loc.country == country]
            if is_active is not None:
                locations = [loc for loc in locations if loc.is_active == is_active]
        else:
            # Get all with filters
            locations = get_all_locations(
                organization_id=org_id,
                is_active=is_active,
                is_hub=is_hub,
                is_customs_point=is_customs,
                limit=100
            )
            # Filter by country if specified
            if country:
                locations = [loc for loc in locations if loc.country == country]

        # Get stats for summary
        stats = get_location_stats(organization_id=org_id)

        # Get unique countries for filter dropdown
        countries = get_unique_countries(organization_id=org_id)

    except Exception as e:
        print(f"Error loading locations: {e}")
        locations = []
        stats = {"total": 0, "active": 0, "inactive": 0, "hubs": 0, "customs_points": 0}
        countries = []

    # Status options for filter
    status_options = [
        Option("Все", value="", selected=(status == "")),
        Option("Активные", value="active", selected=(status == "active")),
        Option("Неактивные", value="inactive", selected=(status == "inactive")),
    ]

    # Type options for filter
    type_options = [
        Option("Все типы", value="", selected=(type_filter == "")),
        Option("Хабы", value="hub", selected=(type_filter == "hub")),
        Option("Таможенные пункты", value="customs", selected=(type_filter == "customs")),
    ]

    # Country options for filter
    country_options = [Option("Все страны", value="", selected=(country == ""))]
    for c in countries:
        country_options.append(Option(c, value=c, selected=(country == c)))

    # Build location rows
    location_rows = []
    for loc in locations:
        status_class = "status-approved" if loc.is_active else "status-rejected"
        status_text = "Активна" if loc.is_active else "Неактивна"

        # Type badges
        type_badges = []
        if loc.is_hub:
            type_badges.append(Span(icon("building-2", size=12), " Хаб", cls="badge badge-primary", style="margin-right: 0.25rem; display: inline-flex; align-items: center; gap: 0.25rem;"))
        if loc.is_customs_point:
            type_badges.append(Span(icon("shield-check", size=12), " Таможня", cls="badge badge-info", style="margin-right: 0.25rem; display: inline-flex; align-items: center; gap: 0.25rem;"))

        location_rows.append(
            Tr(
                Td(
                    Strong(loc.code) if loc.code else "—",
                    style="font-family: monospace;"
                ),
                Td(loc.city or "—"),
                Td(loc.country),
                Td(*type_badges if type_badges else ["—"]),
                Td(loc.address[:50] + "..." if loc.address and len(loc.address) > 50 else (loc.address or "—")),
                Td(Span(status_text, cls=f"status-badge {status_class}")),
                Td(
                    A(icon("edit", size=14), href=f"/locations/{loc.id}/edit", title="Редактировать", style="margin-right: 0.5rem;"),
                    A(icon("eye", size=14), href=f"/locations/{loc.id}", title="Просмотр"),
                )
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
        width: 140px;
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

    return page_layout("Справочник локаций",
        # Header card with gradient
        Div(
            Div(
                # Title row
                Div(
                    icon("map-pin", size=24, color="#475569"),
                    Span(" Локации", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                    Span(f" ({stats.get('total', 0)})", style="font-size: 16px; color: #64748b; margin-left: 4px;"),
                    style="display: flex; align-items: center;"
                ),
                # Subtitle
                P("Точки получения и доставки товаров",
                  style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;"),
                style="flex: 1;"
            ),
            btn_link("Добавить локацию", href="/locations/new", variant="success", icon_name="plus"),
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
                Div("Активных", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=stat_card_style
            ),
            Div(
                Div(str(stats.get("hubs", 0)), style="font-size: 28px; font-weight: 700; color: #3b82f6;"),
                Div("Хабов", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=stat_card_style
            ),
            Div(
                Div(str(stats.get("customs_points", 0)), style="font-size: 28px; font-weight: 700; color: #f59e0b;"),
                Div("Таможенных", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=stat_card_style
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px;"
        ),

        # Filters card
        Div(
            Form(
                Div(
                    # Search input
                    Input(type="text", name="q", value=q, placeholder="Код, город или страна...",
                          style=f"{input_style} margin-right: 12px;"),
                    # Filters
                    Select(*country_options, name="country", style=f"{select_style} margin-right: 8px;"),
                    Select(*type_options, name="type_filter", style=f"{select_style} margin-right: 8px;"),
                    Select(*status_options, name="status", style=f"{select_style} margin-right: 12px;"),
                    # Buttons
                    Button(icon("search", size=14), " Поиск", type="submit",
                           style="padding: 10px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; margin-right: 8px;"),
                    A(icon("x", size=14), " Сбросить", href="/locations",
                      style="padding: 10px 16px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none;"),
                    style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px 0;"
                ),
                method="get",
                action="/locations"
            ),
            style=filter_card_style
        ),

        # Locations table with styled container
        Div(
            Table(
                Thead(
                    Tr(
                        Th("Код"),
                        Th("Город"),
                        Th("Страна"),
                        Th("Тип"),
                        Th("Адрес"),
                        Th("Статус"),
                        Th("Действия"),
                    )
                ),
                Tbody(*location_rows) if location_rows else Tbody(
                    Tr(Td("Локации не найдены. ", A("Добавьте первую локацию", href="/locations/new"), " или ", A("загрузите стандартные", href="/locations/seed"), ".",
                          colspan="7", style="text-align: center; padding: 2rem; color: #64748b;"))
                )
            ),
            style=table_card_style
        ),

        session=session
    )


# NOTE: /locations/new routes MUST be defined BEFORE /locations/{location_id}
# to prevent "new" from being matched as a location_id parameter
@rt("/locations/new")
def get_new_location(session):
    """Show form to create a new location."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin or logistics can create locations
    if not user_has_any_role(session, ["admin", "logistics"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания локаций. Требуется роль: admin или logistics", cls="alert alert-error"),
            session=session
        )

    return _location_form(session=session)


@rt("/locations/new")
def post_new_location(
    country: str,
    code: str = "",
    city: str = "",
    address: str = "",
    is_hub: str = "",
    is_customs_point: str = "",
    notes: str = "",
    session=None
):
    """Handle location creation form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "logistics"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для создания локаций.", cls="alert alert-error"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")
    user_id = user.get("id")

    from services.location_service import create_location, validate_location_code, validate_country

    # Normalize code to uppercase
    code = code.strip().upper() if code else ""

    # Validate country
    if not validate_country(country):
        return _location_form(error="Страна обязательна для заполнения", session=session)

    # Validate code format if provided
    if code and not validate_location_code(code):
        return _location_form(
            error="Код локации должен состоять из 2-5 заглавных латинских букв (например, MSK, SPB, SH)",
            session=session
        )

    try:
        location = create_location(
            organization_id=org_id,
            country=country.strip(),
            city=city.strip() if city else None,
            code=code if code else None,
            address=address.strip() if address else None,
            is_hub=bool(is_hub),
            is_customs_point=bool(is_customs_point),
            is_active=True,
            notes=notes.strip() if notes else None,
            created_by=user_id,
        )

        if location:
            return RedirectResponse(f"/locations/{location.id}", status_code=303)
        else:
            return _location_form(
                error="Локация с таким кодом уже существует или произошла ошибка",
                session=session
            )

    except ValueError as e:
        return _location_form(error=str(e), session=session)
    except Exception as e:
        print(f"Error creating location: {e}")
        return _location_form(error=f"Ошибка при создании: {e}", session=session)


@rt("/locations/{location_id}")
def get(location_id: str, session):
    """Location detail view page."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "logistics", "customs", "procurement"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра данной страницы.", cls="alert alert-error"),
            session=session
        )

    from services.location_service import get_location

    location = get_location(location_id)
    if not location:
        return page_layout("Не найдено",
            Div("Локация не найдена.", cls="alert alert-error"),
            btn_link("К списку локаций", href="/locations", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    status_text = "Активна" if location.is_active else "Неактивна"
    display_name = location.display_name or f"{location.code or ''} - {location.city or ''}, {location.country}".strip(" -,")

    return page_layout(f"Локация: {display_name}",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Локации", href="/locations",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Div(
                        icon("map-pin", size=24, color="#0ea5e9"),
                        H1(display_name, style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        Span(location.code, style="font-family: monospace; font-size: 14px; padding: 4px 10px; background: #e0f2fe; color: #0284c7; border-radius: 6px; font-weight: 600;") if location.code else "",
                        style="display: flex; align-items: center; gap: 12px;"
                    ),
                    Div(
                        Span(status_text, style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: {'#16a34a' if location.is_active else '#dc2626'}; background: {'#dcfce7' if location.is_active else '#fee2e2'};"),
                        Span(icon("building-2", size=12), " Хаб", style="display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: #7c3aed; background: #f3e8ff;") if location.is_hub else "",
                        Span(icon("shield-check", size=12), " Таможня", style="display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: #0284c7; background: #e0f2fe;") if location.is_customs_point else "",
                        btn_link("Редактировать", href=f"/locations/{location_id}/edit", variant="secondary", icon_name="edit", size="sm"),
                        style="display: flex; align-items: center; gap: 8px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Main info cards grid
        Div(
            # Card 1: Location Info
            Div(
                Div(
                    icon("clipboard-list", size=16, color="#64748b"),
                    Span("ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("Код", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(location.code or "—", style="font-weight: 600; color: #0284c7; font-family: monospace; font-size: 16px;"),
                    ),
                    Div(
                        Span("Город", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(location.city or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("Страна", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(location.country, style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    Div(
                        Span("Адрес", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(location.address or "—", style="font-weight: 500; color: #1e293b; font-size: 14px;"),
                    ),
                    style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            # Card 2: Classification
            Div(
                Div(
                    icon("tag", size=16, color="#64748b"),
                    Span("КЛАССИФИКАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("Логистический хаб", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(
                            Span(icon("check-circle", size=14, color="#16a34a"), " Да", style="display: inline-flex; align-items: center; gap: 4px; color: #16a34a; font-weight: 500;") if location.is_hub else
                            Span(icon("x-circle", size=14, color="#94a3b8"), " Нет", style="display: inline-flex; align-items: center; gap: 4px; color: #64748b;"),
                            style="font-size: 14px; margin-top: 4px;"
                        ),
                    ),
                    Div(
                        Span("Таможенный пункт", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                        Div(
                            Span(icon("check-circle", size=14, color="#16a34a"), " Да", style="display: inline-flex; align-items: center; gap: 4px; color: #16a34a; font-weight: 500;") if location.is_customs_point else
                            Span(icon("x-circle", size=14, color="#94a3b8"), " Нет", style="display: inline-flex; align-items: center; gap: 4px; color: #64748b;"),
                            style="font-size: 14px; margin-top: 4px;"
                        ),
                    ),
                    style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;"
        ),

        # Notes card (if has notes)
        Div(
            Div(
                icon("message-square", size=16, color="#64748b"),
                Span("ПРИМЕЧАНИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;"
            ),
            P(location.notes or "Нет примечаний", style="font-size: 14px; color: #1e293b; margin: 0;"),
            style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if location.notes else "",

        session=session
    )


def _location_form(location=None, error=None, session=None):
    """Helper function to render location create/edit form."""
    is_edit = location is not None
    title = f"Редактирование: {location.display_name or location.city or location.country}" if is_edit else "Новая локация"
    action_url = f"/locations/{location.id}/edit" if is_edit else "/locations/new"

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border-radius: 12px;
        border: 1px solid #a7f3d0;
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

    checkbox_card_style = """
        padding: 14px 16px;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #f8fafc;
        margin-bottom: 12px;
        cursor: pointer;
    """

    return page_layout(title,
        # Error alert
        Div(
            icon("alert-circle", size=16, color="#dc2626"),
            Span(error, style="margin-left: 8px;"),
            style="background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center;"
        ) if error else "",

        # Header card with gradient (green theme for locations)
        Div(
            Div(
                A(
                    icon("arrow-left", size=16, color="#047857"),
                    Span("Локации", style="margin-left: 6px;"),
                    href="/locations",
                    style="display: inline-flex; align-items: center; color: #047857; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("map-pin" if not is_edit else "edit", size=24, color="#059669"),
                    Span(title, style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    style="display: flex; align-items: center;"
                ),
            ),
            style=header_card_style
        ),

        # Info alert
        Div(
            icon("lightbulb", size=16, color="#0369a1"),
            Span(" Локация — это точка получения или доставки товаров. Код (2-5 букв) используется для быстрого поиска. Отметьте как хаб или таможенный пункт при необходимости.", style="margin-left: 8px;"),
            style="background: #f0f9ff; border: 1px solid #bae6fd; color: #0369a1; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center;"
        ),

        # Form card
        Div(
            Form(
                # Section: Main info
                Div(
                    icon("map", size=16, color="#64748b"),
                    Span("ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=section_header_style
                ),
                Div(
                    Div(
                        Label("Код (2-5 букв)", style=label_style),
                        Input(
                            name="code",
                            value=location.code if location else "",
                            placeholder="MSK",
                            pattern="[A-Za-z]{2,5}",
                            title="2-5 латинских букв",
                            maxlength="5",
                            style=f"{input_style} text-transform: uppercase; font-family: monospace; font-weight: bold;"
                        ),
                        Small("Необязательно. Например: MSK, SPB, SH, GZ", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 4px;"),
                        style="flex: 1;"
                    ),
                    Div(style="flex: 2;"),  # Spacer
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Страна *", style=label_style),
                        Input(name="country", value=location.country if location else "Россия", placeholder="Россия", required=True, style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Город", style=label_style),
                        Input(name="city", value=location.city if location else "", placeholder="Москва", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Label("Адрес (полный)", style=label_style),
                    Textarea(
                        location.address if location else "",
                        name="address",
                        placeholder="ул. Примерная, д. 1, склад №5",
                        rows="2",
                        style=f"{input_style} resize: vertical;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Section: Classification
                Div(
                    icon("tag", size=16, color="#64748b"),
                    Span("КЛАССИФИКАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Label(
                        Input(
                            type="checkbox",
                            name="is_hub",
                            value="1",
                            checked=location.is_hub if location else False,
                            style="accent-color: #059669; margin-right: 10px;"
                        ),
                        icon("building-2", size=16, color="#64748b"),
                        Span(" Логистический хаб", style="font-weight: 500; color: #1e293b; margin-left: 4px;"),
                        Br(),
                        Small("Центр консолидации и отправки грузов", style="color: #94a3b8; font-size: 12px; margin-left: 30px; display: block; margin-top: 2px;"),
                        style="cursor: pointer; display: block;"
                    ),
                    style=checkbox_card_style
                ),
                Div(
                    Label(
                        Input(
                            type="checkbox",
                            name="is_customs_point",
                            value="1",
                            checked=location.is_customs_point if location else False,
                            style="accent-color: #059669; margin-right: 10px;"
                        ),
                        icon("shield-check", size=16, color="#64748b"),
                        Span(" Таможенный пункт", style="font-weight: 500; color: #1e293b; margin-left: 4px;"),
                        Br(),
                        Small("Пункт таможенного оформления", style="color: #94a3b8; font-size: 12px; margin-left: 30px; display: block; margin-top: 2px;"),
                        style="cursor: pointer; display: block;"
                    ),
                    style=checkbox_card_style
                ),

                # Section: Notes
                Div(
                    icon("file-text", size=16, color="#64748b"),
                    Span("ПРИМЕЧАНИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=f"{section_header_style} margin-top: 24px;"
                ),
                Div(
                    Label("Заметки", style=label_style),
                    Textarea(
                        location.notes if location else "",
                        name="notes",
                        placeholder="Дополнительная информация о локации...",
                        rows="3",
                        style=f"{input_style} resize: vertical;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Status (edit only)
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
                            value="1",
                            checked=location.is_active if location else True,
                            style="accent-color: #059669; margin-right: 8px;"
                        ),
                        Span("Активная локация", style="font-size: 14px; color: #1e293b;"),
                        style="display: flex; align-items: center; cursor: pointer;"
                    ),
                    Small("Неактивные локации не отображаются в выпадающих списках", style="color: #94a3b8; font-size: 12px; display: block; margin-top: 6px;"),
                ) if is_edit else "",

                # Form actions
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/locations" if not is_edit else f"/locations/{location.id}", variant="secondary", icon_name="x"),
                    style="display: flex; gap: 12px; justify-content: flex-end; padding-top: 20px; margin-top: 24px; border-top: 1px solid #e2e8f0;"
                ),

                method="post",
                action=action_url
            ),
            style=form_card_style
        ),
        session=session
    )


@rt("/locations/{location_id}/edit")
def get(location_id: str, session):
    """Show form to edit an existing location."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin or logistics can edit locations
    if not user_has_any_role(session, ["admin", "logistics"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования локаций.", cls="alert alert-error"),
            session=session
        )

    from services.location_service import get_location

    location = get_location(location_id)

    if not location:
        return page_layout("Локация не найдена",
            Div("Запрашиваемая локация не существует.", cls="alert alert-error"),
            btn_link("К списку локаций", href="/locations", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    return _location_form(location=location, session=session)


@rt("/locations/{location_id}/edit")
def post(
    location_id: str,
    country: str,
    code: str = "",
    city: str = "",
    address: str = "",
    is_hub: str = "",
    is_customs_point: str = "",
    notes: str = "",
    is_active: str = "",
    session=None
):
    """Handle location edit form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "logistics"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для редактирования локаций.", cls="alert alert-error"),
            session=session
        )

    from services.location_service import (
        get_location, update_location, validate_location_code, validate_country
    )

    location = get_location(location_id)
    if not location:
        return page_layout("Локация не найдена",
            Div("Запрашиваемая локация не существует.", cls="alert alert-error"),
            btn_link("К списку локаций", href="/locations", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Normalize code to uppercase
    code = code.strip().upper() if code else ""

    # Validate country
    if not validate_country(country):
        return _location_form(location=location, error="Страна обязательна для заполнения", session=session)

    # Validate code format if provided
    if code and not validate_location_code(code):
        return _location_form(
            location=location,
            error="Код локации должен состоять из 2-5 заглавных латинских букв (например, MSK, SPB, SH)",
            session=session
        )

    try:
        updated = update_location(
            location_id=location_id,
            country=country.strip(),
            city=city.strip() if city else None,
            code=code if code else None,
            address=address.strip() if address else None,
            is_hub=bool(is_hub),
            is_customs_point=bool(is_customs_point),
            is_active=bool(is_active),
            notes=notes.strip() if notes else None,
        )

        if updated:
            return RedirectResponse(f"/locations/{location_id}", status_code=303)
        else:
            return _location_form(
                location=location,
                error="Не удалось обновить локацию. Возможно, код уже используется другой локацией.",
                session=session
            )

    except ValueError as e:
        return _location_form(location=location, error=str(e), session=session)
    except Exception as e:
        print(f"Error updating location: {e}")
        return _location_form(location=location, error=f"Ошибка при обновлении: {e}", session=session)


@rt("/locations/{location_id}/delete")
def post(location_id: str, session):
    """Handle location deletion (soft delete - deactivate)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only can delete
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div("Только администратор может удалять локации.", cls="alert alert-error"),
            session=session
        )

    from services.location_service import deactivate_location

    result = deactivate_location(location_id)

    if result:
        return RedirectResponse("/locations", status_code=303)
    else:
        return page_layout("Ошибка",
            Div("Не удалось деактивировать локацию.", cls="alert alert-error"),
            btn_link("К списку локаций", href="/locations", variant="secondary", icon_name="arrow-left"),
            session=session
        )

