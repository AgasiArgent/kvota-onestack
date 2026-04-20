"""FastHTML /settings + /profile areas — archived 2026-04-20 Phase 6C-2B-4.

Replaced by Next.js at https://app.kvotaflow.ru/settings + /profile.
Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy these paths back to this Python container.

Contents:
  - GET    /settings                                        — org + calc settings page (admin only)
  - POST   /settings                                        — save calc settings
  - GET    /settings/telegram                               — legacy 301 shim → /telegram
  - POST   /settings/telegram                               — legacy 301 shim → /telegram
  - GET    /profile                                         — own profile view + edit form
  - POST   /profile                                         — save own profile
  - POST   /profile/{user_id}                               — admin save other user's profile
  - GET    /profile/{user_id}                               — admin/self profile view with tabs (general/specifications/customers)
  - GET    /profile/{user_id}/edit-field/{field_name}       — inline-edit HTMX fragment
  - POST   /profile/{user_id}/update-field/{field_name}     — inline-edit save
  - GET    /profile/{user_id}/cancel-edit/{field_name}      — inline-edit cancel
  - helper: _render_profile_field_display

Preserved in main.py (NOT archived here):
  - /api/settings/*              — FastAPI sub-app, consumed by Next.js
  - /api/profile/*               — FastAPI sub-app, consumed by Next.js
  - /admin/*                     — separate admin cluster, archive decision pending (6C-2B-6+)
  - /telegram/*                  — separate telegram cluster, archive decision pending (6C-2B-6)
  - nav entries for /settings + /profile in FastHTML top-nav/sidebar (lines 2586, 2590, 2795, 2902)
    — these become dead links post-archive, safe per Caddy cutover (user confirmed).

The `/profile/{user_id}` GET + POST pair uses FastHTML's function-name method
inference: both routes share the same `@rt("/profile/{user_id}")` decorator,
but one function is named `get` and the other `post`. This is the standard
FastHTML idiom (same as `/quotes/{quote_id}/edit` GET+POST pair). Not dead
code, not a duplicate. Moved together in this archive.

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_any_role, get_supabase,
btn, btn_link, icon, stat_card, A, Button, Div, Form, H1, H2, H3, Input,
Label, Option, P, Script, Select, Small, Span, Strong, Style, Table, Tbody,
Td, Textarea, Th, Thead, Tr, RedirectResponse, datetime), re-apply the @rt
decorator, and regenerate tests if needed. Not recommended — rewrite via
Next.js instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime

from fasthtml.common import (
    A, Button, Div, Form, H1, H2, H3, Input, Label, Option, P, Script,
    Select, Small, Span, Strong, Style, Table, Tbody, Td, Textarea, Th,
    Thead, Tr,
)
from starlette.responses import RedirectResponse


# ============================================================================
# SETTINGS PAGE
# ============================================================================

# @rt("/settings")  # decorator removed; file is archived and not mounted
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    # Only admins can access settings
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Настройки доступны только администраторам. Используйте раздел 'Профиль' для управления своими данными."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            btn_link("Мой профиль", href="/profile", variant="primary", icon_name="user"),
            session=session
        )

    supabase = get_supabase()

    # Get organization settings
    org_result = supabase.table("organizations") \
        .select("*") \
        .eq("id", user["org_id"]) \
        .execute()

    org = org_result.data[0] if org_result.data else {}

    # Get calculation settings
    calc_result = supabase.table("calculation_settings") \
        .select("*") \
        .eq("organization_id", user["org_id"]) \
        .execute()

    calc_settings = calc_result.data[0] if calc_result.data else {}

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
        padding: 24px;
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

    label_style = "display: block; font-size: 13px; color: #475569; margin-bottom: 6px; font-weight: 500;"

    form_group_style = "margin-bottom: 16px;"

    grid_2col_style = "display: grid; grid-template-columns: 1fr 1fr; gap: 20px;"

    return page_layout("Настройки",
        # Header card
        Div(
            H1("Настройки организации",
               style="margin: 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            P(f"Организация: {org.get('name', '—')}",
              style="margin: 8px 0 0 0; font-size: 14px; color: #64748b;"),
            cls="card-elevated"
        ),

        # Organization info
        Div(
            Div(icon("building", size=14), " Информация об организации", style=section_header_style),
            Div(
                Label("Название организации", style=label_style),
                Input(name="name", value=org.get("name", ""), readonly=True,
                      style=f"{input_style} background: #f1f5f9; color: #64748b;"),
                Small("Для изменения реквизитов организации обратитесь к администратору",
                      style="color: #94a3b8; font-size: 12px; margin-top: 6px; display: block;"),
                style=form_group_style
            ),
            style=form_card_style
        ),

        # Calculation defaults
        Form(
            Div(
                Div(icon("calculator", size=14), " Настройки расчётов", style=section_header_style),
                Div(
                    Div(
                        Label("Риск курса валют (%)", style=label_style),
                        Input(name="rate_forex_risk", type="number", value=str(calc_settings.get("rate_forex_risk", 3)),
                              step="0.1", min="0", max="20", style=input_style),
                        style=form_group_style
                    ),
                    Div(
                        Label("Финансовая комиссия (%)", style=label_style),
                        Input(name="rate_fin_comm", type="number", value=str(calc_settings.get("rate_fin_comm", 2)),
                              step="0.1", min="0", max="20", style=input_style),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                Div(
                    Label("Ставка кредита (% в день)", style=label_style),
                    Input(name="rate_loan_interest_daily", type="number",
                          value=str(round(calc_settings.get("rate_loan_interest_daily", 0.05), 6)),
                          step="any", min="0", max="1", style=f"{input_style} max-width: 300px;"),
                    style=form_group_style
                ),
                Button(icon("check", size=14), " Сохранить настройки", type="submit",
                       style="padding: 10px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                style=form_card_style
            ),
            method="post",
            action="/settings"
        ),

        # Telegram settings link
        Div(
            Div(icon("message-circle", size=14), " Telegram", style=section_header_style),
            P("Привяжите Telegram для получения уведомлений о задачах и согласованиях.",
              style="color: #64748b; margin: 0 0 16px 0; font-size: 14px;"),
            A(icon("message-circle", size=14), " Настройки Telegram", href="/telegram",
              style="padding: 10px 20px; background: #3b82f6; color: white; border-radius: 6px; font-size: 14px; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;"),
            style=form_card_style
        ),

        session=session
    )


# @rt("/settings")  # decorator removed; file is archived and not mounted
def post(rate_forex_risk: float, rate_fin_comm: float, rate_loan_interest_daily: float, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    try:
        # Check if settings exist
        existing = supabase.table("calculation_settings") \
            .select("organization_id") \
            .eq("organization_id", user["org_id"]) \
            .execute()

        settings_data = {
            "organization_id": user["org_id"],
            "rate_forex_risk": rate_forex_risk,
            "rate_fin_comm": rate_fin_comm,
            "rate_loan_interest_daily": rate_loan_interest_daily,
            "updated_at": datetime.now().isoformat()
        }

        if existing.data:
            supabase.table("calculation_settings") \
                .update(settings_data) \
                .eq("organization_id", user["org_id"]) \
                .execute()
        else:
            supabase.table("calculation_settings") \
                .insert(settings_data) \
                .execute()

        return page_layout("Settings",
            Div("Settings saved successfully!", cls="alert alert-success"),
            Script("setTimeout(() => window.location.href = '/settings', 1500);"),
            session=session
        )

    except Exception as e:
        return page_layout("Settings Error",
            Div(f"Error: {str(e)}", cls="alert alert-error"),
            A("← Назад", href="/settings"),
            session=session
        )


# ============================================================================
# TELEGRAM SETTINGS PAGE — redirects to /telegram (consolidated)
# ============================================================================

# @rt("/settings/telegram")  # decorator removed; file is archived and not mounted
def get(session):
    """Redirect old settings/telegram URL to the canonical /telegram page."""
    return RedirectResponse("/telegram", status_code=301)

# @rt("/settings/telegram")  # decorator removed; file is archived and not mounted
def post(session):
    """Redirect old settings/telegram POST to the canonical /telegram page."""
    return RedirectResponse("/telegram", status_code=301)


# ============================================================================
# USER PROFILE PAGE
# ============================================================================

# @rt("/profile")  # decorator removed; file is archived and not mounted
def get(session):
    """User profile page - view and edit own profile."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    supabase = get_supabase()

    from services.user_profile_service import (
        get_departments, get_sales_groups, get_organization_users
    )

    # Get user profile
    profile_result = supabase.table("user_profiles").select(
        "*, departments(name), sales_groups(name)"
    ).eq("user_id", user_id).eq("organization_id", org_id).limit(1).execute()

    if profile_result.data:
        profile = profile_result.data[0]
    else:
        profile = {
            "full_name": "", "position": "", "phone": "",
            "date_of_birth": None, "hire_date": None, "location": "",
            "timezone": "Europe/Moscow", "bio": "",
            "department_id": None, "sales_group_id": None, "manager_id": None
        }

    # Get Telegram status
    tg_result = supabase.table("telegram_users").select(
        "telegram_id, telegram_username, verified_at"
    ).eq("user_id", user_id).limit(1).execute()

    tg_linked, tg_display = False, "—"
    if tg_result.data and tg_result.data[0].get("verified_at"):
        tg_linked = True
        tg_data = tg_result.data[0]
        tg_display = f"@{tg_data.get('telegram_username') or tg_data.get('telegram_id')}"

    departments = get_departments(org_id)
    sales_groups = get_sales_groups(org_id)
    users = get_organization_users(org_id)

    # Design system styles
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    section_card_style = """
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 24px;
        margin-bottom: 20px;
    """

    section_header_style = """
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #e2e8f0;
    """

    input_style = """
        width: 100%;
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
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

    return page_layout("Мой профиль",
        # Header card with gradient
        Div(
            Div(
                btn_link("", href="/dashboard", variant="secondary", icon_name="arrow-left",
                         style="padding: 8px 12px; margin-right: 12px;"),
                Div(
                    icon("user", size=24, color="#475569"),
                    Span(" Мой профиль", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                    style="display: flex; align-items: center;"
                ),
                style="display: flex; align-items: center;"
            ),
            style=header_card_style
        ),

        Form(
            # Section 1: Personal info
            Div(
                Div(
                    icon("user", size=16, color="#64748b"),
                    Span(" ЛИЧНАЯ ИНФОРМАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style=section_header_style
                ),
                Div(
                    Div(
                        Label("ФИО *", style=label_style),
                        Input(name="full_name", value=profile.get("full_name") or "", placeholder="Иванов Иван Иванович", required=True, style=input_style),
                        style="flex: 2;"
                    ),
                    Div(
                        Label("Email", style=label_style),
                        Input(value=user.get("email", "—"), readonly=True, disabled=True, style=f"{input_style} background: #f1f5f9; cursor: not-allowed;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Телефон", style=label_style),
                        Input(name="phone", type="tel", value=profile.get("phone") or "", placeholder="+7 (999) 123-45-67", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Дата рождения", style=label_style),
                        Input(name="date_of_birth", type="date", value=profile.get("date_of_birth") or "", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Label("Telegram", style=label_style),
                    Div(
                        Span(tg_display, style=f"color: {'#10b981' if tg_linked else '#9ca3af'}; font-weight: 500;"),
                        Small(" (привязан)" if tg_linked else " (не привязан)", style="color: #64748b; margin-left: 4px;"),
                        A(" → Настроить" if not tg_linked else " → Изменить", href="/telegram", style="margin-left: 8px; font-size: 13px; color: #3b82f6;"),
                        style="display: flex; align-items: center; padding: 10px 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;"
                    ),
                ),
                style=section_card_style
            ),

            # Section 2: Organization
            Div(
                Div(
                    icon("building", size=16, color="#64748b"),
                    Span(" ОРГАНИЗАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style=section_header_style
                ),
                Div(
                    Div(
                        Label("Должность", style=label_style),
                        Input(name="position", value=profile.get("position") or "", placeholder="Менеджер по продажам", style=input_style),
                        style="flex: 2;"
                    ),
                    Div(
                        Label("Дата приема", style=label_style),
                        Input(name="hire_date", type="date", value=profile.get("hire_date") or "", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Департамент", style=label_style),
                        Select(Option("— Не выбрано —", value="", selected=not profile.get("department_id")),
                            *[Option(dept["name"], value=dept["id"], selected=dept["id"] == profile.get("department_id")) for dept in departments],
                            name="department_id", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Группа продаж", style=label_style),
                        Select(Option("— Не выбрано —", value="", selected=not profile.get("sales_group_id")),
                            *[Option(sg["name"], value=sg["id"], selected=sg["id"] == profile.get("sales_group_id")) for sg in sales_groups],
                            name="sales_group_id", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px; margin-bottom: 16px;"
                ),
                Div(
                    Label("Руководитель", style=label_style),
                    Select(Option("— Не выбрано —", value="", selected=not profile.get("manager_id")),
                        *[Option(u["full_name"], value=u["id"], selected=u["id"] == profile.get("manager_id")) for u in users if u.get("full_name")],
                        name="manager_id", style=input_style),
                ),
                style=section_card_style
            ),

            # Section 3: Settings
            Div(
                Div(
                    icon("settings", size=16, color="#64748b"),
                    Span(" НАСТРОЙКИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style=section_header_style
                ),
                Div(
                    Div(
                        Label("Часовой пояс", style=label_style),
                        Select(
                            Option("Europe/Moscow (МСК, UTC+3)", value="Europe/Moscow", selected=profile.get("timezone") == "Europe/Moscow" or not profile.get("timezone")),
                            Option("Asia/Shanghai (CST, UTC+8)", value="Asia/Shanghai", selected=profile.get("timezone") == "Asia/Shanghai"),
                            Option("Asia/Hong_Kong (HKT, UTC+8)", value="Asia/Hong_Kong", selected=profile.get("timezone") == "Asia/Hong_Kong"),
                            Option("Asia/Dubai (GST, UTC+4)", value="Asia/Dubai", selected=profile.get("timezone") == "Asia/Dubai"),
                            Option("Europe/Istanbul (TRT, UTC+3)", value="Europe/Istanbul", selected=profile.get("timezone") == "Europe/Istanbul"),
                            name="timezone", style=input_style),
                        style="flex: 1;"
                    ),
                    Div(
                        Label("Офис/локация", style=label_style),
                        Input(name="location", value=profile.get("location") or "", placeholder="Москва, офис на Тверской", style=input_style),
                        style="flex: 1;"
                    ),
                    style="display: flex; gap: 16px;"
                ),
                style=section_card_style
            ),

            # Section 4: Bio
            Div(
                Div(
                    icon("file-text", size=16, color="#64748b"),
                    Span(" О СЕБЕ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style=section_header_style
                ),
                Label("Биография", style=label_style),
                Textarea(profile.get("bio") or "", name="bio", rows="4", placeholder="Расскажите немного о себе, своем опыте, интересах...",
                         style=f"{input_style} resize: vertical;"),
                style=section_card_style
            ),

            # Actions
            Div(
                btn("Сохранить изменения", variant="primary", icon_name="save", type="submit"),
                btn_link("Отмена", href="/dashboard", variant="secondary", icon_name="x"),
                style="display: flex; gap: 12px; justify-content: flex-end;"
            ),
            method="post", action="/profile"
        ),
        session=session)


# @rt("/profile")  # decorator removed; file is archived and not mounted
def post(session, full_name: str, phone: str = "", date_of_birth: str = "",
         position: str = "", hire_date: str = "", department_id: str = "",
         sales_group_id: str = "", manager_id: str = "", timezone: str = "Europe/Moscow",
         location: str = "", bio: str = ""):
    """Save user profile."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    from services.user_profile_service import update_user_profile

    update_data = {
        "full_name": full_name.strip() if full_name else None,
        "phone": phone.strip() if phone else None,
        "date_of_birth": date_of_birth if date_of_birth else None,
        "position": position.strip() if position else None,
        "hire_date": hire_date if hire_date else None,
        "department_id": department_id if department_id else None,
        "sales_group_id": sales_group_id if sales_group_id else None,
        "manager_id": manager_id if manager_id else None,
        "timezone": timezone,
        "location": location.strip() if location else None,
        "bio": bio.strip() if bio else None
    }

    success = update_user_profile(user["id"], user["org_id"], **update_data)

    if success:
        return page_layout("Профиль сохранен",
            Div(Div("Профиль успешно обновлен!", cls="alert alert-success"),
                Script("setTimeout(() => window.location.href = '/profile', 1500);")),
            session=session)
    else:
        return page_layout("Ошибка",
            Div(Div("Не удалось сохранить профиль. Попробуйте позже.", cls="alert alert-error"),
                btn_link("Назад к профилю", href="/profile", variant="secondary", icon_name="arrow-left")),
            session=session)


# @rt("/profile/{user_id}")  # decorator removed; file is archived and not mounted
def post(session, user_id: str, full_name: str, phone: str = "", date_of_birth: str = "",
         position: str = "", hire_date: str = "", department_id: str = "",
         sales_group_id: str = "", manager_id: str = "", timezone: str = "Europe/Moscow",
         location: str = "", bio: str = ""):
    """Admin save other user's profile."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user, roles = session["user"], session["user"].get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён", H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"), session=session)

    from services.user_profile_service import update_user_profile

    update_data = {
        "full_name": full_name.strip() if full_name else None,
        "phone": phone.strip() if phone else None,
        "date_of_birth": date_of_birth if date_of_birth else None,
        "position": position.strip() if position else None,
        "hire_date": hire_date if hire_date else None,
        "department_id": department_id if department_id else None,
        "sales_group_id": sales_group_id if sales_group_id else None,
        "manager_id": manager_id if manager_id else None,
        "timezone": timezone,
        "location": location.strip() if location else None,
        "bio": bio.strip() if bio else None
    }

    success = update_user_profile(user_id, user["org_id"], **update_data)

    if success:
        return page_layout("Профиль сохранен",
            Div(Div("Профиль успешно обновлен!", cls="alert alert-success"),
                Script(f"setTimeout(() => window.location.href = '/profile/{user_id}', 1500);")),
            session=session)
    else:
        return page_layout("Ошибка",
            Div(Div("Не удалось сохранить профиль. Попробуйте позже.", cls="alert alert-error"),
                btn_link("Назад к профилю", href=f"/profile/{user_id}", variant="secondary", icon_name="arrow-left")),
            session=session)


# ============================================================================
# User Profile (view + inline edit)
# ============================================================================

# @rt("/profile/{user_id}")  # decorator removed; file is archived and not mounted
def get(user_id: str, session, tab: str = "general"):
    """User profile view page with statistics, specifications, and customers."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user.get("org_id")

    # Check permissions - users can view their own profile, admins can view all profiles
    current_user_id = user.get("user_id")
    is_admin = user_has_any_role(session, ["admin", "top_manager"])

    if user_id != current_user_id and not is_admin:
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра данного профиля.", cls="alert alert-error"),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.user_profile_service import (
        get_user_profile,
        get_user_statistics,
        get_user_specifications,
        get_user_customers
    )

    # Get user profile
    profile = get_user_profile(user_id, org_id)
    if not profile:
        return page_layout("Не найдено",
            Div("Пользователь не найден.", cls="alert alert-error"),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Tab navigation
    tabs_nav = Div(
        A("Общая информация",
          href=f"/profile/{user_id}?tab=general",
          cls=f"tab-btn {'active' if tab == 'general' else ''}"),
        A("Спецификации",
          href=f"/profile/{user_id}?tab=specifications",
          cls=f"tab-btn {'active' if tab == 'specifications' else ''}"),
        A("Клиенты",
          href=f"/profile/{user_id}?tab=customers",
          cls=f"tab-btn {'active' if tab == 'customers' else ''}"),
        cls="tabs-nav"
    )

    # Build tab content based on selected tab
    if tab == "general":
        # Get statistics
        stats = get_user_statistics(user_id, org_id)

        # Build editable fields for admins
        if is_admin:
            full_name_display = _render_profile_field_display(user_id, "full_name", profile.get("full_name") or "")
            phone_display = _render_profile_field_display(user_id, "phone", profile.get("phone") or "")
            position_display = _render_profile_field_display(user_id, "position", profile.get("position") or "")
            department_display = _render_profile_field_display(user_id, "department_id", profile.get("department") or "")
            sales_group_display = _render_profile_field_display(user_id, "sales_group_id", profile.get("sales_group") or "")
            manager_display = _render_profile_field_display(user_id, "manager_id", profile.get("manager_email") or "")
            location_display = _render_profile_field_display(user_id, "location", profile.get("location") or "")
        else:
            full_name_display = Div(profile.get("full_name") or "—", style="padding: 0.5rem 0.75rem;")
            phone_display = Div(profile.get("phone") or "—", style="padding: 0.5rem 0.75rem;")
            position_display = Div(profile.get("position") or "—", style="padding: 0.5rem 0.75rem;")
            department_display = Div(profile.get("department") or "—", style="padding: 0.5rem 0.75rem;")
            sales_group_display = Div(profile.get("sales_group") or "—", style="padding: 0.5rem 0.75rem;")
            manager_display = Div(profile.get("manager_email") or "—", style="padding: 0.5rem 0.75rem;")
            location_display = Div(profile.get("location") or "—", style="padding: 0.5rem 0.75rem;")

        tab_content = Div(
            # Main info section
            Div(
                H3("Основная информация", style="margin-bottom: 1rem;"),
                Div(
                    Div(
                        Div(Strong("ФИО"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        full_name_display,
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Email"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        Div(profile.get("email") or "—", style="padding: 0.5rem 0.75rem;"),
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Телефон"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        phone_display,
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Должность"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        position_display,
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Департамент"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        department_display,
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Группа"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        sales_group_display,
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Руководитель"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        manager_display,
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Местонахождение"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        location_display,
                        cls="info-item"
                    ),
                    Div(
                        Div(Strong("Роль"), style="color: #666; font-size: 0.9em; margin-bottom: 0.5rem;"),
                        Div(profile.get("role_name") or "—", style="padding: 0.5rem 0.75rem;"),
                        cls="info-item"
                    ),
                    cls="info-grid",
                    style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1.5rem;"
                ),
            ),

            # Statistics section (DaisyUI stats)
            Div(
                H3("Статистика", style="margin: 2rem 0 1rem 0;"),
                Div(
                    stat_card(
                        value=str(stats["total_customers"]),
                        label="Клиенты",
                        description="клиентов"
                    ),
                    stat_card(
                        value=str(stats["total_quotes"]),
                        label="КП",
                        description="коммерческих предложений"
                    ),
                    stat_card(
                        value=f"${stats['total_quotes_sum_usd']:,.0f}",
                        label="Сумма КП",
                        description="общая сумма предложений"
                    ),
                    stat_card(
                        value=str(stats["total_specifications"]),
                        label="Спецификации",
                        description="спецификаций"
                    ),
                    stat_card(
                        value=f"${stats['total_specifications_sum_usd']:,.0f}",
                        label="Сумма спецификаций",
                        description="общая сумма сделок"
                    ),
                    stat_card(
                        value=f"${stats['total_profit_usd']:,.0f}",
                        label="Профит",
                        description="суммарный профит"
                    ),
                    cls="stats stats-vertical lg:stats-horizontal shadow",
                    style="background: var(--card-background-color); display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));"
                ),
            )
        )

    elif tab == "specifications":
        # Get specifications
        specifications = get_user_specifications(user_id, org_id)

        # Build specifications table
        spec_rows = []
        for spec in specifications:
            last_quote_date_str = ""
            if spec["last_quote_date"]:
                from datetime import datetime
                if isinstance(spec["last_quote_date"], str):
                    last_quote_date = datetime.fromisoformat(spec["last_quote_date"].replace("Z", "+00:00"))
                else:
                    last_quote_date = spec["last_quote_date"]
                last_quote_date_str = last_quote_date.strftime("%d.%m.%Y")

            updated_at_str = ""
            if spec["updated_at"]:
                from datetime import datetime
                if isinstance(spec["updated_at"], str):
                    updated_at = datetime.fromisoformat(spec["updated_at"].replace("Z", "+00:00"))
                else:
                    updated_at = spec["updated_at"]
                updated_at_str = updated_at.strftime("%d.%m.%Y %H:%M")

            spec_rows.append(
                Tr(
                    Td(spec["customer_name"]),
                    Td(spec["customer_inn"]),
                    Td(spec["customer_category"]),
                    Td(f"${spec['quote_sum']:,.0f}"),
                    Td(f"${spec['spec_sum']:,.0f}"),
                    Td(last_quote_date_str),
                    Td(updated_at_str),
                )
            )

        tab_content = Div(
            H3(f"Спецификации ({len(specifications)})", style="margin-bottom: 1rem;"),
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("Клиент"),
                            Th("ИНН"),
                            Th("Категория"),
                            Th("Сумма КП"),
                            Th("Сумма спецификации"),
                            Th("Дата последнего КП"),
                            Th("Дата обновления"),
                        )
                    ),
                    Tbody(*spec_rows) if spec_rows else Tbody(
                        Tr(Td("Нет спецификаций", colspan="7", style="text-align: center; color: #999;"))
                    ),
                    cls="table-auto"
                ),
                cls="table-container"
            ) if specifications else Div(
                P("Нет спецификаций", style="text-align: center; color: #999; padding: 2rem;")
            ),
            id="tab-content"
        )

    elif tab == "customers":
        # Get customers
        customers = get_user_customers(user_id, org_id)

        # Build customers table
        customer_rows = []
        for customer in customers:
            last_quote_date_str = ""
            if customer["last_quote_date"]:
                from datetime import datetime
                if isinstance(customer["last_quote_date"], str):
                    last_quote_date = datetime.fromisoformat(customer["last_quote_date"].replace("Z", "+00:00"))
                else:
                    last_quote_date = customer["last_quote_date"]
                last_quote_date_str = last_quote_date.strftime("%d.%m.%Y")

            updated_at_str = ""
            if customer["updated_at"]:
                from datetime import datetime
                if isinstance(customer["updated_at"], str):
                    updated_at = datetime.fromisoformat(customer["updated_at"].replace("Z", "+00:00"))
                else:
                    updated_at = customer["updated_at"]
                updated_at_str = updated_at.strftime("%d.%m.%Y %H:%M")

            customer_rows.append(
                Tr(
                    Td(A(customer["customer_name"], href=f"/customers/{customer['customer_id']}")),
                    Td(customer["customer_inn"]),
                    Td(customer["customer_category"]),
                    Td(f"${customer['quotes_sum']:,.0f}"),
                    Td(f"${customer['specs_sum']:,.0f}"),
                    Td(last_quote_date_str),
                    Td(updated_at_str),
                )
            )

        tab_content = Div(
            H3(f"Клиенты ({len(customers)})", style="margin-bottom: 1rem;"),
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("Наименование"),
                            Th("ИНН"),
                            Th("Категория"),
                            Th("Сумма КП"),
                            Th("Сумма спецификаций"),
                            Th("Дата последнего КП"),
                            Th("Дата обновления"),
                        )
                    ),
                    Tbody(*customer_rows) if customer_rows else Tbody(
                        Tr(Td("Нет клиентов", colspan="7", style="text-align: center; color: #999;"))
                    ),
                    cls="table-auto"
                ),
                cls="table-container"
            ) if customers else Div(
                P("Нет клиентов", style="text-align: center; color: #999; padding: 2rem;")
            ),
            id="tab-content"
        )

    # Page layout
    return page_layout(
        f"Профиль: {profile.get('full_name') or profile.get('email')}",
        Div(
            Div(
                H2(profile.get("full_name") or profile.get("email"), style="margin-bottom: 0.5rem;"),
                P(profile.get("position") or profile.get("role_name") or "—", style="color: #666;"),
                style="margin-bottom: 1.5rem;"
            ),
            tabs_nav,
            tab_content,
            cls="card"
        ),
        session=session
    )


# @rt("/profile/{user_id}/edit-field/{field_name}")  # decorator removed; file is archived and not mounted
def get(user_id: str, field_name: str, session):
    """Return inline edit form for a specific profile field (admin only)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - only admins can edit profiles
    if not user_has_any_role(session, ["admin", "top_manager"]):
        return Div("У вас нет прав для редактирования профиля", id=f"field-{field_name}")

    user = session["user"]
    org_id = user.get("org_id")

    from services.user_profile_service import (
        get_user_profile,
        get_departments,
        get_sales_groups,
        get_organization_users
    )

    profile = get_user_profile(user_id, org_id)
    if not profile:
        return Div("Пользователь не найден")

    # Map field names to labels and current values
    field_config = {
        "full_name": ("ФИО", profile.get("full_name") or "", "text"),
        "phone": ("Телефон", profile.get("phone") or "", "text"),
        "position": ("Должность", profile.get("position") or "", "text"),
        "location": ("Местонахождение", profile.get("location") or "", "text"),
        "department_id": ("Департамент", None, "select"),
        "sales_group_id": ("Группа", None, "select"),
        "manager_id": ("Руководитель", None, "select"),
    }

    if field_name not in field_config:
        return Div("Неизвестное поле")

    label, value, input_type = field_config[field_name]

    # Style for modern inline editing
    input_style = "width: 100%; padding: 0.5rem 0.75rem; border: 2px solid #3b82f6; border-radius: 0.375rem; font-size: inherit; outline: none;"

    if input_type == "text":
        input_elem = Input(
            type="text", value=value, name=field_name,
            autofocus=True,
            style=input_style,
            onkeydown="if(event.key === 'Escape') { document.getElementById('cancel-btn-" + field_name + "').click(); } else if(event.key === 'Enter') { event.target.form.requestSubmit(); }"
        )
        # Simple input - no visible buttons
        action_buttons = Div(
            Button("✕", type="button", id=f"cancel-btn-{field_name}",
                  hx_get=f"/profile/{user_id}/cancel-edit/{field_name}",
                  hx_target=f"#field-{field_name}",
                  hx_swap="outerHTML",
                  style="position: absolute; right: 0.75rem; top: 50%; transform: translateY(-50%); background: transparent; border: none; color: #999; cursor: pointer; padding: 0.25rem 0.5rem; font-size: 1.2em;"),
            style="position: relative;"
        )
    elif input_type == "select":
        # Get options based on field
        if field_name == "department_id":
            departments = get_departments(org_id)
            current_value = None
            for dept in departments:
                if profile.get("department") == dept.get("name"):
                    current_value = dept.get("id")
                    break
            options = [Option("Не указан", value="", selected=(not current_value))]
            options.extend([
                Option(dept.get("name"), value=dept.get("id"), selected=(dept.get("id") == current_value))
                for dept in departments
            ])
        elif field_name == "sales_group_id":
            sales_groups = get_sales_groups(org_id)
            current_value = None
            for sg in sales_groups:
                if profile.get("sales_group") == sg.get("name"):
                    current_value = sg.get("id")
                    break
            options = [Option("Не указан", value="", selected=(not current_value))]
            options.extend([
                Option(sg.get("name"), value=sg.get("id"), selected=(sg.get("id") == current_value))
                for sg in sales_groups
            ])
        elif field_name == "manager_id":
            users = get_organization_users(org_id)
            current_value = None
            for u in users:
                if profile.get("manager_email") == u.get("email"):
                    current_value = u.get("id")
                    break
            options = [Option("Не указан", value="", selected=(not current_value))]
            options.extend([
                Option(u.get("full_name") or u.get("email"), value=u.get("id"), selected=(u.get("id") == current_value))
                for u in users
                if u.get("id") != user_id  # Don't allow selecting self as manager
            ])
        else:
            options = [Option("Не указан", value="")]

        input_elem = Select(
            *options,
            name=field_name,
            autofocus=True,
            style=input_style,
            onchange="this.form.requestSubmit();"
        )
        # Select dropdown - auto-submit on change
        action_buttons = Div(
            Button("✕", type="button", id=f"cancel-btn-{field_name}",
                  hx_get=f"/profile/{user_id}/cancel-edit/{field_name}",
                  hx_target=f"#field-{field_name}",
                  hx_swap="outerHTML",
                  style="position: absolute; right: 0.75rem; top: 50%; transform: translateY(-50%); background: transparent; border: none; color: #999; cursor: pointer; padding: 0.25rem 0.5rem; font-size: 1.2em;"),
            style="position: relative;"
        )

    return Form(
        Div(
            input_elem,
            action_buttons,
            style="position: relative;"
        ),
        id=f"field-{field_name}",
        hx_post=f"/profile/{user_id}/update-field/{field_name}",
        hx_target=f"#field-{field_name}",
        hx_swap="outerHTML",
        style="margin: 0;"
    )


# @rt("/profile/{user_id}/update-field/{field_name}")  # decorator removed; file is archived and not mounted
async def post(user_id: str, field_name: str, session, request):
    """Update a specific profile field via inline editing (admin only)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - only admins can edit profiles
    if not user_has_any_role(session, ["admin", "top_manager"]):
        return Div("У вас нет прав для редактирования профиля", id=f"field-{field_name}")

    user = session["user"]
    org_id = user.get("org_id")

    from services.user_profile_service import get_user_profile, update_user_profile

    profile = get_user_profile(user_id, org_id)
    if not profile:
        return Div("Пользователь не найден")

    # Get form data
    form_data = await request.form()
    new_value = form_data.get(field_name, "")

    # Update profile
    update_data = {field_name: new_value if new_value else None}
    success = update_user_profile(user_id, org_id, **update_data)

    if not success:
        return Div("Ошибка обновления", id=f"field-{field_name}")

    # Get updated profile to show new value
    updated_profile = get_user_profile(user_id, org_id)

    # Map field names to display values
    display_values = {
        "full_name": updated_profile.get("full_name") or "—",
        "phone": updated_profile.get("phone") or "—",
        "position": updated_profile.get("position") or "—",
        "location": updated_profile.get("location") or "—",
        "department_id": updated_profile.get("department") or "—",
        "sales_group_id": updated_profile.get("sales_group") or "—",
        "manager_id": updated_profile.get("manager_email") or "—",
    }

    # Return updated display
    return _render_profile_field_display(user_id, field_name, display_values.get(field_name, "—"))


# @rt("/profile/{user_id}/cancel-edit/{field_name}")  # decorator removed; file is archived and not mounted
def get(user_id: str, field_name: str, session):
    """Cancel inline editing and return to display mode."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user.get("org_id")

    from services.user_profile_service import get_user_profile

    profile = get_user_profile(user_id, org_id)
    if not profile:
        return Div("Пользователь не найден")

    # Map field names to display values
    display_values = {
        "full_name": profile.get("full_name") or "—",
        "phone": profile.get("phone") or "—",
        "position": profile.get("position") or "—",
        "location": profile.get("location") or "—",
        "department_id": profile.get("department") or "—",
        "sales_group_id": profile.get("sales_group") or "—",
        "manager_id": profile.get("manager_email") or "—",
    }

    return _render_profile_field_display(user_id, field_name, display_values.get(field_name, "—"))


def _render_profile_field_display(user_id: str, field_name: str, value: str):
    """Helper function to render profile field in display mode with modern inline edit."""
    display_value = value if value and value != "—" else "Не указан"
    display_color = "#999" if not value or value == "—" else "#000"

    return Div(
        display_value,
        id=f"field-{field_name}",
        hx_get=f"/profile/{user_id}/edit-field/{field_name}",
        hx_target=f"#field-{field_name}",
        hx_swap="outerHTML",
        style=f"cursor: pointer; padding: 0.5rem 0.75rem; border-radius: 0.375rem; transition: background 0.15s ease; color: {display_color};",
        onmouseover="this.style.background='#f3f4f6'",
        onmouseout="this.style.background='transparent'",
        title="Кликните для редактирования"
    )
