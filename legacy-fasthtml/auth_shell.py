"""FastHTML auth shell — archived 2026-04-20 during Phase 6C-2B Mega-D.

Replaced by Next.js auth shell at https://app.kvotaflow.ru/ (Supabase Auth
session handshake + /login + /logout + /unauthorized views). Post-Caddy-cutover
`kvotaflow.ru` 301→`app.kvotaflow.ru`, which does not proxy these paths back
to this Python container — they become unreachable for end users.

Contents:
  - GET  /               — root redirect: /tasks if logged in, else /login
  - GET  /login          — login form page (email + password)
  - POST /login          — authenticate via Supabase anon client, set session,
                           redirect to /dashboard (or re-render with error)
  - GET  /logout         — clear session, redirect to /login
  - GET  /unauthorized   — 401/403 error page shown when a user lacks the
                           required role to access a given /admin/* area

Preserved in main.py (NOT archived here):
  - /admin/*                        — 25 routes, separate archive decision
    (may stay FastHTML-backed until post-cutover rewrite)
  - FastAPI sub-app mount at /api   — all API endpoints consumed by Next.js
  - Middleware stack (SessionMiddleware, ApiAuthMiddleware, Sentry)
  - require_login(session) helper   — used by /admin/* and other alive code
  - page_layout(), icon(), etc.     — shared UI helpers used by /admin/*
  - get_supabase(), get_user_role_codes, etc. — shared service helpers
  - RedirectResponse import         — still used in /admin/* + redirects

Service-import cleanup in main.py:
  - `get_anon_client` from `services.database` had a single caller (POST
    /login) which lives here now. Removed the `get_anon_client` symbol from
    the main.py import line; `get_supabase` stays (consumed everywhere).
    The service helper itself remains alive in `services/database.py` for
    potential future reuse.

Post-archive main.py footprint:
  - Imports + FastHTML app + middleware setup
  - 25 /admin/* @rt routes + their exclusive helpers
  - FastAPI sub-app mount at bottom

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, icon, RedirectResponse, get_anon_client,
get_supabase, get_user_role_codes, A, Button, Div, Form, H1, Input, Label,
P, Span), re-apply the @rt decorator. Not recommended — rewrite via
Next.js + Supabase Auth instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Button, Div, Form, H1, Input, Label, P, Span,
)
from starlette.responses import RedirectResponse


# ============================================================================
# AUTH ROUTES
# ============================================================================

# @rt("/")  # decorator removed; file is archived and not mounted
def get(session):
    if session.get("user"):
        return RedirectResponse("/tasks", status_code=303)  # New primary entry point
    return RedirectResponse("/login", status_code=303)


# @rt("/login")  # decorator removed; file is archived and not mounted
def get(session):
    if session.get("user"):
        return RedirectResponse("/dashboard", status_code=303)

    # Design system styles for login page
    login_card_style = """
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 24px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
        padding: 40px;
        max-width: 420px;
        margin: 0 auto;
    """

    logo_section_style = """
        text-align: center;
        margin-bottom: 32px;
    """

    logo_icon_style = """
        width: 56px;
        height: 56px;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        border-radius: 14px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    """

    title_style = """
        font-size: 24px;
        font-weight: 700;
        color: #1e293b;
        margin: 0 0 6px 0;
        letter-spacing: -0.02em;
    """

    subtitle_style = """
        font-size: 14px;
        color: #64748b;
        margin: 0;
    """

    label_style = """
        display: block;
        font-size: 11px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    """

    input_style = """
        width: 100%;
        padding: 12px 14px;
        font-size: 14px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: #f8fafc;
        color: #1e293b;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
        box-sizing: border-box;
    """

    input_group_style = "margin-bottom: 20px;"

    submit_btn_style = """
        width: 100%;
        padding: 14px 20px;
        font-size: 15px;
        font-weight: 600;
        color: white;
        background: #3b82f6;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        margin-top: 28px;
        transition: background-color 0.15s ease;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    """

    page_bg_style = """
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
    """

    return page_layout("Вход — OneStack",
        Div(
            Div(
                # Logo section
                Div(
                    Div(
                        icon("layers", size=28, style="color: white;"),
                        style=logo_icon_style
                    ),
                    H1("OneStack", style=title_style),
                    P("Система управления коммерческими предложениями", style=subtitle_style),
                    style=logo_section_style
                ),

                # Form
                Form(
                    # Email field
                    Div(
                        Label("Электронная почта", style=label_style, **{"for": "email"}),
                        Input(
                            name="email",
                            type="email",
                            id="email",
                            placeholder="your@email.com",
                            required=True,
                            style=input_style
                        ),
                        style=input_group_style
                    ),
                    # Password field
                    Div(
                        Label("Пароль", style=label_style, **{"for": "password"}),
                        Input(
                            name="password",
                            type="password",
                            id="password",
                            required=True,
                            style=input_style
                        ),
                        style=input_group_style
                    ),
                    # Submit button
                    Button(
                        icon("log-in", size=18),
                        Span("Войти в систему"),
                        type="submit",
                        style=submit_btn_style
                    ),
                    method="post",
                    action="/login"
                ),
                style=login_card_style
            ),
            style=page_bg_style
        ),
        session=session,
        hide_nav=True
    )


# @rt("/login")  # decorator removed; file is archived and not mounted
def post(email: str, password: str, session):
    """Authenticate with Supabase"""
    try:
        # Use anon client for auth
        client = get_anon_client()
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user:
            # Get user's organization
            supabase = get_supabase()
            org_result = supabase.table("organization_members") \
                .select("organization_id, organizations(id, name)") \
                .eq("user_id", response.user.id) \
                .eq("status", "active") \
                .limit(1) \
                .execute()

            org_data = org_result.data[0] if org_result.data else None
            org_id = org_data["organization_id"] if org_data else None

            # Get user's roles in the organization
            user_roles = []
            if org_id:
                user_roles = get_user_role_codes(response.user.id, org_id)

            # training_manager is a super-role for demos — grant all permissions
            if "training_manager" in user_roles:
                all_roles = ["admin", "sales", "procurement", "logistics", "customs",
                             "quote_controller", "spec_controller", "finance",
                             "top_manager", "head_of_sales", "head_of_procurement",
                             "head_of_logistics", "training_manager"]
                user_roles = list(set(user_roles + all_roles))

            session["user"] = {
                "id": response.user.id,
                "email": response.user.email,
                "org_id": org_id,
                "org_name": org_data["organizations"]["name"] if org_data else "No Organization",
                "roles": user_roles  # List of role codes: ['sales', 'admin', etc.]
            }
            session["access_token"] = response.session.access_token

            return RedirectResponse("/dashboard", status_code=303)

    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            error_msg = "Неверный email или пароль"

        # Design system styles for login page (same as GET)
        login_card_style = """
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
            padding: 40px;
            max-width: 420px;
            margin: 0 auto;
        """

        logo_section_style = """
            text-align: center;
            margin-bottom: 32px;
        """

        logo_icon_style = """
            width: 56px;
            height: 56px;
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            border-radius: 14px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        """

        title_style = """
            font-size: 24px;
            font-weight: 700;
            color: #1e293b;
            margin: 0 0 6px 0;
            letter-spacing: -0.02em;
        """

        subtitle_style = """
            font-size: 14px;
            color: #64748b;
            margin: 0;
        """

        label_style = """
            display: block;
            font-size: 11px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        """

        input_style = """
            width: 100%;
            padding: 12px 14px;
            font-size: 14px;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            background: #f8fafc;
            color: #1e293b;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
            box-sizing: border-box;
        """

        input_group_style = "margin-bottom: 20px;"

        submit_btn_style = """
            width: 100%;
            padding: 14px 20px;
            font-size: 15px;
            font-weight: 600;
            color: white;
            background: #3b82f6;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-top: 28px;
            transition: background-color 0.15s ease;
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        """

        page_bg_style = """
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
        """

        error_alert_style = """
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 14px 16px;
            background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
            border: 1px solid #fecaca;
            border-radius: 10px;
            color: #dc2626;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 24px;
        """

        return page_layout("Вход — OneStack",
            Div(
                Div(
                    # Logo section
                    Div(
                        Div(
                            icon("layers", size=28, style="color: white;"),
                            style=logo_icon_style
                        ),
                        H1("OneStack", style=title_style),
                        P("Система управления коммерческими предложениями", style=subtitle_style),
                        style=logo_section_style
                    ),

                    # Error alert
                    Div(
                        icon("alert-circle", size=18),
                        Span(error_msg),
                        style=error_alert_style
                    ),

                    # Form
                    Form(
                        # Email field
                        Div(
                            Label("Электронная почта", style=label_style, **{"for": "email"}),
                            Input(
                                name="email",
                                type="email",
                                id="email",
                                value=email,
                                required=True,
                                style=input_style
                            ),
                            style=input_group_style
                        ),
                        # Password field
                        Div(
                            Label("Пароль", style=label_style, **{"for": "password"}),
                            Input(
                                name="password",
                                type="password",
                                id="password",
                                required=True,
                                style=input_style
                            ),
                            style=input_group_style
                        ),
                        # Submit button
                        Button(
                            icon("log-in", size=18),
                            Span("Войти в систему"),
                            type="submit",
                            style=submit_btn_style
                        ),
                        method="post",
                        action="/login"
                    ),
                    style=login_card_style
                ),
                style=page_bg_style
            ),
            session=session,
            hide_nav=True
        )


# @rt("/logout")  # decorator removed; file is archived and not mounted
def get(session):
    session.clear()
    return RedirectResponse("/login", status_code=303)


# @rt("/unauthorized")  # decorator removed; file is archived and not mounted
def get(session):
    """Page shown when user doesn't have required role"""
    # Design system styles
    card_style = """
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        padding: 48px 40px;
        max-width: 480px;
        margin: 0 auto;
        text-align: center;
    """

    icon_container_style = """
        width: 72px;
        height: 72px;
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border-radius: 20px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 24px;
        border: 1px solid #fecaca;
    """

    title_style = """
        font-size: 22px;
        font-weight: 700;
        color: #1e293b;
        margin: 0 0 12px 0;
        letter-spacing: -0.02em;
    """

    text_style = """
        font-size: 14px;
        color: #64748b;
        margin: 0 0 8px 0;
        line-height: 1.6;
    """

    btn_style = """
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        font-size: 14px;
        font-weight: 600;
        color: #374151;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        text-decoration: none;
        margin-top: 24px;
        transition: background-color 0.15s ease, border-color 0.15s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    """

    page_bg_style = """
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
    """

    return page_layout("Доступ запрещён — OneStack",
        Div(
            Div(
                # Error icon
                Div(
                    icon("shield-x", size=36, style="color: #dc2626;"),
                    style=icon_container_style
                ),
                # Title
                H1("Доступ запрещён", style=title_style),
                # Description
                P("У вас нет прав для доступа к этой странице.", style=text_style),
                P("Обратитесь к администратору, если считаете это ошибкой.", style=text_style),
                # Back button
                A(
                    icon("arrow-left", size=16),
                    Span("Вернуться на главную"),
                    href="/tasks",
                    style=btn_style
                ),
                style=card_style
            ),
            style=page_bg_style
        ),
        session=session,
        hide_nav=True
    )
