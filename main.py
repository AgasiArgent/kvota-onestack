"""
Kvota OneStack - FastHTML + Supabase

A single-language (Python) quotation platform.
Run with: python main.py
"""

from fasthtml.common import *
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

from services.database import get_supabase, get_anon_client

# Import export services
from services.export_data_mapper import fetch_export_data
from services.specification_export import generate_specification_pdf, generate_spec_pdf_from_spec_id
from services.invoice_export import generate_invoice_pdf
from services.validation_export import create_validation_excel
from services.procurement_export import create_procurement_excel

# Import version service
from services.quote_version_service import create_quote_version, list_quote_versions, get_quote_version

# Import role service
from services.role_service import get_user_role_codes, get_session_user_roles, require_role, require_any_role

# Import brand service for procurement
from services.brand_service import get_assigned_brands

# Import workflow service for status display
from services.workflow_service import (
    WorkflowStatus, STATUS_NAMES, STATUS_NAMES_SHORT, STATUS_COLORS,
    check_all_procurement_complete, complete_procurement, complete_logistics, complete_customs,
    transition_quote_status, get_quote_transition_history, transition_to_pending_procurement
)

# Import approval service (Feature #65, #86)
from services.approval_service import request_approval, count_pending_approvals, get_pending_approvals_for_user, get_approvals_with_details

# Import deal service (Feature #86)
from services.deal_service import count_deals_by_status, get_deals_by_status

# Import specification service (Feature #86)
from services.specification_service import count_specifications_by_status

# Import calculation engine
from calculation_engine import calculate_multiproduct_quote
from calculation_mapper import map_variables_to_calculation_input, safe_decimal, safe_int
from calculation_models import (
    QuoteCalculationInput, Currency, SupplierCountry, SellerCompany,
    OfferSaleType, Incoterms, DMFeeType
)

# ============================================================================
# APP SETUP
# ============================================================================

app, rt = fast_app(
    secret_key=os.getenv("APP_SECRET", "dev-secret-change-in-production"),
    live=True,
)

# ============================================================================
# STYLES
# ============================================================================

APP_STYLES = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; background: #f5f5f5; color: #333; line-height: 1.6; }
nav { background: #1a1a2e; color: white; padding: 1rem 0; }
nav .nav-container { max-width: 1200px; margin: 0 auto; padding: 0 1rem; display: flex; justify-content: space-between; align-items: center; }
nav ul { list-style: none; margin: 0; padding: 0; display: flex; gap: 1.5rem; align-items: center; }
nav a { color: #a0a0ff; text-decoration: none; }
nav a:hover { color: white; }
nav strong { color: white; font-size: 1.2rem; }
h1, h2, h3 { color: #1a1a2e; margin-top: 0; }
a { color: #4a4aff; }
input, select, button, textarea { padding: 0.5rem; font-size: 1rem; border: 1px solid #ddd; border-radius: 4px; }
input:focus, select:focus, textarea:focus { outline: 2px solid #4a4aff; border-color: #4a4aff; }
button { background: #4a4aff; color: white; border: none; cursor: pointer; padding: 0.75rem 1.5rem; }
button:hover { background: #3a3adf; }
button.secondary { background: #6c757d; }
button.danger { background: #dc3545; }
table { width: 100%; border-collapse: collapse; background: white; margin-top: 1rem; }
th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; }
tr:hover { background: #f8f9fa; }
label { display: block; margin-bottom: 1rem; font-weight: 500; }
label input, label select, label textarea { margin-top: 0.25rem; width: 100%; }
.container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
.card { background: white; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
.stat-card { text-align: center; padding: 1rem; }
.stat-value { font-size: 2rem; font-weight: bold; color: #4a4aff; }
.alert { padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
.alert-success { background: #d4edda; color: #155724; }
.alert-error { background: #f8d7da; color: #721c24; }
.alert-info { background: #cce5ff; color: #004085; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.form-actions { display: flex; gap: 1rem; margin-top: 1rem; }
.status-badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.875rem; }
.status-draft { background: #ffc107; color: #000; }
.status-sent { background: #17a2b8; color: #fff; }
.status-approved { background: #28a745; color: #fff; }
.status-rejected { background: #dc3545; color: #fff; }
@media (max-width: 768px) { .form-row { grid-template-columns: 1fr; } }
"""

# ============================================================================
# LAYOUT HELPERS
# ============================================================================

def nav_bar(session):
    """Navigation bar component with role-based links"""
    user = session.get("user")
    if user:
        roles = user.get("roles", [])

        # Base navigation items
        nav_items = [
            Li(A("Dashboard", href="/dashboard")),
            Li(A("Quotes", href="/quotes")),
            Li(A("Customers", href="/customers")),
            Li(A("New Quote", href="/quotes/new")),
        ]

        # Role-specific navigation items
        if "procurement" in roles or "admin" in roles:
            nav_items.append(Li(A("Закупки", href="/procurement")))

        if "logistics" in roles or "admin" in roles:
            nav_items.append(Li(A("Логистика", href="/logistics")))

        if "customs" in roles or "admin" in roles:
            nav_items.append(Li(A("Таможня", href="/customs")))

        if "quote_controller" in roles or "admin" in roles:
            nav_items.append(Li(A("Контроль КП", href="/quote-control")))

        if "spec_controller" in roles or "admin" in roles:
            nav_items.append(Li(A("Спецификации", href="/spec-control")))

        if "finance" in roles or "admin" in roles:
            nav_items.append(Li(A("Финансы", href="/finance")))

        # Admin-only navigation
        if "admin" in roles:
            nav_items.append(Li(A("Админ", href="/admin/users")))

        # Add settings and logout at the end
        nav_items.extend([
            Li(A("Settings", href="/settings")),
            Li(A(f"Logout ({user.get('email', 'User')})", href="/logout")),
        ])

        return Nav(
            Div(
                Ul(Li(Strong("Kvota OneStack"))),
                Ul(*nav_items),
                cls="nav-container"
            )
        )
    return Nav(
        Div(
            Ul(Li(Strong("Kvota OneStack"))),
            Ul(Li(A("Login", href="/login"))),
            cls="nav-container"
        )
    )


def page_layout(title, *content, session=None):
    """Standard page layout wrapper"""
    return Html(
        Head(
            Title(f"{title} - Kvota"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(APP_STYLES),
            # HTMX
            Script(src="https://unpkg.com/htmx.org@1.9.10")
        ),
        Body(
            nav_bar(session or {}),
            Main(Div(*content, cls="container"))
        )
    )


def require_login(session):
    """Check if user is logged in"""
    if not session.get("user"):
        return RedirectResponse("/login", status_code=303)
    return None


def user_has_role(session, role_code: str) -> bool:
    """
    Check if logged-in user has a specific role (from session cache).

    This function checks the roles stored in the session at login time,
    avoiding database queries for role checks.

    Args:
        session: Session dict containing user info
        role_code: Role code to check for (e.g., 'admin', 'sales')

    Returns:
        True if user has the role, False otherwise

    Example:
        if user_has_role(session, 'admin'):
            # Show admin controls
            pass
    """
    user = session.get("user")
    if not user:
        return False
    roles = user.get("roles", [])
    return role_code in roles


def user_has_any_role(session, role_codes: list) -> bool:
    """
    Check if logged-in user has any of the specified roles (from session cache).

    Args:
        session: Session dict containing user info
        role_codes: List of role codes to check for

    Returns:
        True if user has at least one of the roles, False otherwise

    Example:
        if user_has_any_role(session, ['admin', 'finance']):
            # Show financial controls
            pass
    """
    user = session.get("user")
    if not user:
        return False
    roles = user.get("roles", [])
    return any(code in roles for code in role_codes)


def get_user_roles_from_session(session) -> list:
    """
    Get role codes for the logged-in user from session cache.

    Args:
        session: Session dict containing user info

    Returns:
        List of role codes, or empty list if not logged in
    """
    user = session.get("user")
    if not user:
        return []
    return user.get("roles", [])


def format_money(value, currency="RUB"):
    """Format money value"""
    if value is None:
        return "—"
    symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{value:,.0f}"


def status_badge(status):
    """Status badge component"""
    return Span(status.capitalize(), cls=f"status-badge status-{status}")


# ============================================================================
# AUTH ROUTES
# ============================================================================

@rt("/")
def get(session):
    if session.get("user"):
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse("/login", status_code=303)


@rt("/login")
def get(session):
    if session.get("user"):
        return RedirectResponse("/dashboard", status_code=303)

    return page_layout("Login",
        Div(
            H1("Login"),
            Form(
                Label("Email", Input(name="email", type="email", placeholder="your@email.com", required=True)),
                Label("Password", Input(name="password", type="password", required=True)),
                Button("Sign In", type="submit"),
                method="post",
                action="/login"
            ),
            cls="card", style="max-width: 400px; margin: 2rem auto;"
        ),
        session=session
    )


@rt("/login")
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
            error_msg = "Invalid email or password"

        return page_layout("Login",
            Div(
                Div(error_msg, cls="alert alert-error"),
                H1("Login"),
                Form(
                    Label("Email", Input(name="email", type="email", value=email, required=True)),
                    Label("Password", Input(name="password", type="password", required=True)),
                    Button("Sign In", type="submit"),
                    method="post",
                    action="/login"
                ),
                cls="card", style="max-width: 400px; margin: 2rem auto;"
            ),
            session=session
        )


@rt("/logout")
def get(session):
    session.clear()
    return RedirectResponse("/login", status_code=303)


@rt("/unauthorized")
def get(session):
    """Page shown when user doesn't have required role"""
    return page_layout("Access Denied",
        Div(
            H1("🚫 Access Denied"),
            P("You don't have permission to access this page."),
            P("Contact your administrator if you believe this is an error."),
            Div(
                A("← Back to Dashboard", href="/dashboard", cls="button"),
                style="margin-top: 1rem;"
            ),
            cls="card", style="max-width: 500px; margin: 2rem auto; text-align: center;"
        ),
        session=session
    )


# ============================================================================
# DASHBOARD (Feature #86: Role-based tasks)
# ============================================================================

def _get_role_tasks_sections(user_id: str, org_id: str, roles: list, supabase) -> list:
    """
    Build role-specific task sections for the dashboard.
    Returns a list of FastHTML elements showing tasks relevant to user's roles.
    """
    sections = []

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
                    Td(format_money(quote_info.get('total_amount'))),
                    Td(a.get('requested_at', '')[:10] if a.get('requested_at') else '—'),
                    Td(
                        A("Согласовать", href=f"/quotes/{a.get('quote_id')}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;")
                    )
                ))

            sections.append(
                Div(
                    H2(f"⏳ Ожидают согласования ({pending_count})", style="color: #b45309;"),
                    Table(
                        Thead(Tr(Th("КП #"), Th("Клиент"), Th("Сумма"), Th("Запрошено"), Th("Действие"))),
                        Tbody(*approval_rows) if approval_rows else Tbody(Tr(Td("Нет ожидающих", colspan="5", style="text-align: center;")))
                    ) if approvals else P("Загрузка..."),
                    A("Открыть все согласования →", href="/quotes?status=pending_approval"),
                    cls="card", style="border-left: 4px solid #f59e0b; margin-bottom: 1rem;"
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
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        proc_quotes = proc_result.data or []
        proc_count = len(proc_quotes)

        if proc_count > 0:
            proc_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(q.get("created_at", "")[:10] if q.get("created_at") else "—"),
                    Td(A("Оценить", href=f"/procurement", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in proc_quotes
            ]

            sections.append(
                Div(
                    H2(f"📦 Закупки: ожидают оценки ({proc_count})", style="color: #92400e;"),
                    Table(
                        Thead(Tr(Th("КП #"), Th("Клиент"), Th("Создано"), Th("Действие"))),
                        Tbody(*proc_rows)
                    ),
                    A("Открыть раздел Закупки →", href="/procurement"),
                    cls="card", style="border-left: 4px solid #fbbf24; margin-bottom: 1rem;"
                )
            )

    # -------------------------------------------------------------------------
    # LOGISTICS: Quotes needing logistics data
    # -------------------------------------------------------------------------
    if 'logistics' in roles:
        log_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, created_at") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_logistics") \
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        log_quotes = log_result.data or []
        log_count = len(log_quotes)

        if log_count > 0:
            log_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(q.get("created_at", "")[:10] if q.get("created_at") else "—"),
                    Td(A("Заполнить", href=f"/logistics", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in log_quotes
            ]

            sections.append(
                Div(
                    H2(f"🚚 Логистика: ожидают данных ({log_count})", style="color: #1e40af;"),
                    Table(
                        Thead(Tr(Th("КП #"), Th("Клиент"), Th("Создано"), Th("Действие"))),
                        Tbody(*log_rows)
                    ),
                    A("Открыть раздел Логистика →", href="/logistics"),
                    cls="card", style="border-left: 4px solid #3b82f6; margin-bottom: 1rem;"
                )
            )

    # -------------------------------------------------------------------------
    # CUSTOMS: Quotes needing customs data
    # -------------------------------------------------------------------------
    if 'customs' in roles:
        cust_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, created_at") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_customs") \
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        cust_quotes = cust_result.data or []
        cust_count = len(cust_quotes)

        if cust_count > 0:
            cust_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(q.get("created_at", "")[:10] if q.get("created_at") else "—"),
                    Td(A("Заполнить", href=f"/customs", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in cust_quotes
            ]

            sections.append(
                Div(
                    H2(f"🛃 Таможня: ожидают данных ({cust_count})", style="color: #6b21a8;"),
                    Table(
                        Thead(Tr(Th("КП #"), Th("Клиент"), Th("Создано"), Th("Действие"))),
                        Tbody(*cust_rows)
                    ),
                    A("Открыть раздел Таможня →", href="/customs"),
                    cls="card", style="border-left: 4px solid #8b5cf6; margin-bottom: 1rem;"
                )
            )

    # -------------------------------------------------------------------------
    # QUOTE_CONTROLLER: Quotes needing review
    # -------------------------------------------------------------------------
    if 'quote_controller' in roles or 'admin' in roles:
        qc_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, total_amount, created_at") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_quote_control") \
            .order("created_at", desc=False) \
            .limit(5) \
            .execute()

        qc_quotes = qc_result.data or []
        qc_count = len(qc_quotes)

        if qc_count > 0:
            qc_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(format_money(q.get("total_amount"))),
                    Td(A("Проверить", href=f"/quote-control/{q['id']}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in qc_quotes
            ]

            sections.append(
                Div(
                    H2(f"✅ Контроль КП: на проверке ({qc_count})", style="color: #9d174d;"),
                    Table(
                        Thead(Tr(Th("КП #"), Th("Клиент"), Th("Сумма"), Th("Действие"))),
                        Tbody(*qc_rows)
                    ),
                    A("Открыть раздел Контроль КП →", href="/quote-control"),
                    cls="card", style="border-left: 4px solid #ec4899; margin-bottom: 1rem;"
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
            .execute()
        pending_spec_quotes = spec_quotes_result.count or 0

        total_spec_work = pending_specs + pending_spec_quotes

        if total_spec_work > 0:
            sections.append(
                Div(
                    H2(f"📋 Спецификации: требуют внимания ({total_spec_work})", style="color: #4338ca;"),
                    Div(
                        Div(
                            Div(str(pending_spec_quotes), cls="stat-value", style="font-size: 1.5rem; color: #4338ca;"),
                            Div("КП для создания спец."),
                            cls="stat-card", style="padding: 0.5rem;"
                        ),
                        Div(
                            Div(str(spec_counts.get('draft', 0)), cls="stat-value", style="font-size: 1.5rem; color: #6366f1;"),
                            Div("Черновики"),
                            cls="stat-card", style="padding: 0.5rem;"
                        ),
                        Div(
                            Div(str(spec_counts.get('pending_review', 0)), cls="stat-value", style="font-size: 1.5rem; color: #818cf8;"),
                            Div("На проверке"),
                            cls="stat-card", style="padding: 0.5rem;"
                        ),
                        cls="stats-grid", style="grid-template-columns: repeat(3, 1fr);"
                    ),
                    A("Открыть раздел Спецификации →", href="/spec-control"),
                    cls="card", style="border-left: 4px solid #6366f1; margin-bottom: 1rem;"
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
                spec_info = d.get('specification', {})
                deal_rows.append(Tr(
                    Td(d.get('deal_number', '—')),
                    Td(spec_info.get('customer_name', '—') if spec_info else '—'),
                    Td(format_money(d.get('total_amount'), d.get('currency', 'RUB'))),
                    Td(A("Открыть", href=f"/finance/{d.get('id')}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ))

            sections.append(
                Div(
                    H2(f"💰 Финансы: активные сделки ({active_deals})", style="color: #059669;"),
                    Table(
                        Thead(Tr(Th("Сделка #"), Th("Клиент"), Th("Сумма"), Th("Действие"))),
                        Tbody(*deal_rows) if deal_rows else Tbody(Tr(Td("Нет данных", colspan="4", style="text-align: center;")))
                    ),
                    A("Открыть раздел Финансы →", href="/finance"),
                    cls="card", style="border-left: 4px solid #10b981; margin-bottom: 1rem;"
                )
            )

    # -------------------------------------------------------------------------
    # SALES: My quotes (pending sales review)
    # -------------------------------------------------------------------------
    if 'sales' in roles:
        sales_result = supabase.table("quotes") \
            .select("id, idn_quote, customers(name), workflow_status, total_amount") \
            .eq("organization_id", org_id) \
            .eq("workflow_status", "pending_sales_review") \
            .order("updated_at", desc=True) \
            .limit(5) \
            .execute()

        sales_quotes = sales_result.data or []
        sales_count = len(sales_quotes)

        if sales_count > 0:
            sales_rows = [
                Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(format_money(q.get("total_amount"))),
                    Td(A("Продолжить", href=f"/quotes/{q['id']}", cls="button", style="padding: 0.25rem 0.5rem; font-size: 0.875rem;"))
                ) for q in sales_quotes
            ]

            sections.append(
                Div(
                    H2(f"📝 Продажи: ожидают вашего решения ({sales_count})", style="color: #9a3412;"),
                    Table(
                        Thead(Tr(Th("КП #"), Th("Клиент"), Th("Сумма"), Th("Действие"))),
                        Tbody(*sales_rows)
                    ),
                    A("Все мои КП →", href="/quotes"),
                    cls="card", style="border-left: 4px solid #f97316; margin-bottom: 1rem;"
                )
            )

    return sections


@rt("/dashboard")
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user.get("id")
    org_id = user.get("org_id")
    supabase = get_supabase()

    # Get user roles
    roles = get_user_role_codes(user_id, org_id) if user_id and org_id else []

    # If no roles, show standard dashboard
    if not roles:
        roles = []

    # Get overall quotes stats
    quotes_result = supabase.table("quotes") \
        .select("id, status, workflow_status, total_amount") \
        .eq("organization_id", org_id) \
        .execute()

    quotes = quotes_result.data or []

    total_quotes = len(quotes)
    total_revenue = sum(
        Decimal(str(q.get("total_amount") or 0))
        for q in quotes if q.get("workflow_status") in ["approved", "deal"]
    )

    # Count quotes in active workflow stages
    active_workflow = len([q for q in quotes if q.get("workflow_status") not in
                          ["draft", "approved", "deal", "rejected", "cancelled", None]])

    # Get recent quotes
    recent_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), status, workflow_status, total_amount, created_at") \
        .eq("organization_id", org_id) \
        .order("created_at", desc=True) \
        .limit(5) \
        .execute()

    recent_quotes = recent_result.data or []

    # Build role-specific task sections
    task_sections = _get_role_tasks_sections(user_id, org_id, roles, supabase)

    # Role badges
    role_names = {
        'sales': ('Продажи', '#f97316'),
        'procurement': ('Закупки', '#fbbf24'),
        'logistics': ('Логистика', '#3b82f6'),
        'customs': ('Таможня', '#8b5cf6'),
        'quote_controller': ('Контроль КП', '#ec4899'),
        'spec_controller': ('Спецификации', '#6366f1'),
        'finance': ('Финансы', '#10b981'),
        'top_manager': ('Топ-менеджер', '#f59e0b'),
        'admin': ('Админ', '#ef4444'),
    }

    role_badges = [
        Span(role_names.get(r, (r, '#6b7280'))[0],
             style=f"display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-right: 0.25rem; background: {role_names.get(r, (r, '#6b7280'))[1]}20; color: {role_names.get(r, (r, '#6b7280'))[1]}; border: 1px solid {role_names.get(r, (r, '#6b7280'))[1]}40;")
        for r in roles
    ] if roles else [Span("Нет ролей", style="color: #9ca3af; font-size: 0.875rem;")]

    return page_layout("Dashboard",
        # Header with roles
        Div(
            H1(f"👋 Добро пожаловать!"),
            P(
                Strong("Организация: "), user.get('org_name', 'Неизвестно'), " | ",
                Strong("Ваши роли: "), *role_badges
            ),
            style="margin-bottom: 1rem;"
        ),

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
        H2("📋 Ваши задачи", style="margin-top: 1.5rem; margin-bottom: 1rem;") if task_sections else "",
        *task_sections,

        # If no tasks, show helpful message
        Div(
            P("✅ У вас нет активных задач! Все под контролем.", style="color: #059669; font-size: 1.1rem;"),
            cls="card", style="text-align: center; background: #ecfdf5;"
        ) if not task_sections else "",

        # Recent quotes
        H2("📊 Последние КП", style="margin-top: 1.5rem;"),
        Table(
            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Сумма"), Th("Действия"))),
            Tbody(
                *[Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(workflow_status_badge(q.get("workflow_status") or q.get("status", "draft"))),
                    Td(format_money(q.get("total_amount"))),
                    Td(A("Открыть", href=f"/quotes/{q['id']}"))
                ) for q in recent_quotes]
            ) if recent_quotes else Tbody(Tr(Td("Нет КП", colspan="5", style="text-align: center;")))
        ),
        A("Все КП →", href="/quotes"),
        session=session
    )


# ============================================================================
# QUOTES LIST
# ============================================================================

@rt("/quotes")
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), status, total_amount, created_at") \
        .eq("organization_id", user["org_id"]) \
        .order("created_at", desc=True) \
        .execute()

    quotes = result.data or []

    return page_layout("Quotes",
        Div(
            H1("Quotes"),
            A("+ New Quote", href="/quotes/new", role="button"),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        Table(
            Thead(Tr(Th("Quote #"), Th("Customer"), Th("Status"), Th("Total"), Th("Created"), Th("Actions"))),
            Tbody(
                *[Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(status_badge(q.get("status", "draft"))),
                    Td(format_money(q.get("total_amount"))),
                    Td(q.get("created_at", "")[:10]),
                    Td(
                        A("View", href=f"/quotes/{q['id']}", style="margin-right: 0.5rem;"),
                        A("Edit", href=f"/quotes/{q['id']}/edit")
                    )
                ) for q in quotes]
            ) if quotes else Tbody(Tr(Td("No quotes yet. Create your first quote!", colspan="6", style="text-align: center;")))
        ),
        session=session
    )


# ============================================================================
# CUSTOMERS LIST
# ============================================================================

@rt("/customers")
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    result = supabase.table("customers") \
        .select("id, name, email, phone, inn, created_at") \
        .eq("organization_id", user["org_id"]) \
        .order("name") \
        .execute()

    customers = result.data or []

    return page_layout("Customers",
        Div(
            H1("Customers"),
            A("+ Add Customer", href="/customers/new", role="button"),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        Table(
            Thead(Tr(Th("Name"), Th("INN"), Th("Email"), Th("Phone"), Th("Actions"))),
            Tbody(
                *[Tr(
                    Td(c.get("name", "—")),
                    Td(c.get("inn", "—")),
                    Td(c.get("email", "—")),
                    Td(c.get("phone", "—")),
                    Td(A("View", href=f"/customers/{c['id']}"))
                ) for c in customers]
            ) if customers else Tbody(Tr(Td("No customers yet. Add your first customer!", colspan="5", style="text-align: center;")))
        ),
        session=session
    )


# ============================================================================
# NEW CUSTOMER
# ============================================================================

@rt("/customers/new")
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    return page_layout("New Customer",
        H1("Add Customer"),
        Div(
            Form(
                Div(
                    Label("Company Name *", Input(name="name", required=True, placeholder="ООО Ромашка")),
                    Label("INN", Input(name="inn", placeholder="7701234567")),
                    cls="form-row"
                ),
                Div(
                    Label("Email", Input(name="email", type="email", placeholder="info@company.ru")),
                    Label("Phone", Input(name="phone", placeholder="+7 999 123 4567")),
                    cls="form-row"
                ),
                Label("Address", Textarea(name="address", placeholder="Delivery address", rows="3")),
                Div(
                    Button("Save Customer", type="submit"),
                    A("Cancel", href="/customers", role="button", cls="secondary"),
                    cls="form-actions"
                ),
                method="post",
                action="/customers/new"
            ),
            cls="card"
        ),
        session=session
    )


@rt("/customers/new")
def post(name: str, inn: str, email: str, phone: str, address: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    try:
        result = supabase.table("customers").insert({
            "name": name,
            "inn": inn or None,
            "email": email or None,
            "phone": phone or None,
            "address": address or None,
            "organization_id": user["org_id"]
        }).execute()

        return RedirectResponse("/customers", status_code=303)

    except Exception as e:
        return page_layout("New Customer",
            Div(str(e), cls="alert alert-error"),
            H1("Add Customer"),
            # ... form would be here
            session=session
        )


# ============================================================================
# NEW QUOTE
# ============================================================================

@rt("/quotes/new")
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get customers for dropdown
    customers_result = supabase.table("customers") \
        .select("id, name, inn") \
        .eq("organization_id", user["org_id"]) \
        .order("name") \
        .execute()

    customers = customers_result.data or []

    return page_layout("New Quote",
        H1("Create New Quote"),

        # Quote details form
        Div(
            H3("Quote Details"),
            Form(
                Div(
                    Label("Customer *",
                        Select(
                            Option("Select customer...", value="", disabled=True, selected=True),
                            *[Option(f"{c['name']} ({c.get('inn', '')})", value=c["id"]) for c in customers],
                            name="customer_id", required=True
                        )
                    ),
                    Label("Quote Currency",
                        Select(
                            Option("RUB - Russian Ruble", value="RUB", selected=True),
                            Option("USD - US Dollar", value="USD"),
                            Option("EUR - Euro", value="EUR"),
                            name="currency"
                        )
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Delivery Terms",
                        Select(
                            Option("EXW - Ex Works", value="EXW"),
                            Option("FOB - Free on Board", value="FOB"),
                            Option("CIF - Cost, Insurance, Freight", value="CIF"),
                            Option("DDP - Delivered Duty Paid", value="DDP", selected=True),
                            name="delivery_terms"
                        )
                    ),
                    Label("Payment Terms (days)",
                        Input(name="payment_terms", type="number", value="30", min="0")
                    ),
                    cls="form-row"
                ),
                Label("Notes", Textarea(name="notes", placeholder="Additional notes...", rows="3")),
                Div(
                    Button("Create Quote", type="submit"),
                    A("Cancel", href="/quotes", role="button", cls="secondary"),
                    cls="form-actions"
                ),
                method="post",
                action="/quotes/new"
            ),
            cls="card"
        ),

        Div(
            P("After creating the quote, you'll be able to add products."),
            cls="alert alert-info"
        ) if customers else Div(
            P("You need to ", A("add a customer", href="/customers/new"), " first before creating a quote."),
            cls="alert alert-error"
        ),

        session=session
    )


@rt("/quotes/new")
def post(customer_id: str, currency: str, delivery_terms: str, payment_terms: int, notes: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    try:
        # Generate quote number
        count_result = supabase.table("quotes") \
            .select("id", count="exact") \
            .eq("organization_id", user["org_id"]) \
            .execute()

        quote_num = (count_result.count or 0) + 1
        idn_quote = f"Q-{datetime.now().strftime('%Y%m')}-{quote_num:04d}"

        # Get customer name for title
        customer_result = supabase.table("customers") \
            .select("name") \
            .eq("id", customer_id) \
            .single() \
            .execute()
        customer_name = customer_result.data.get("name", "Unknown") if customer_result.data else "Unknown"
        title = f"Quote for {customer_name}"

        result = supabase.table("quotes").insert({
            "idn_quote": idn_quote,
            "title": title,
            "customer_id": customer_id,
            "organization_id": user["org_id"],
            "currency": currency,
            "delivery_terms": delivery_terms,
            "payment_terms": payment_terms,
            "notes": notes or None,
            "status": "draft",
            "created_by": user["id"]
        }).execute()

        new_quote = result.data[0]
        return RedirectResponse(f"/quotes/{new_quote['id']}", status_code=303)

    except Exception as e:
        return page_layout("Error",
            Div(f"Error creating quote: {str(e)}", cls="alert alert-error"),
            A("← Back to Quotes", href="/quotes"),
            session=session
        )


# ============================================================================
# QUOTE DETAIL
# ============================================================================

@rt("/quotes/{quote_id}")
def get(quote_id: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote with customer
    result = supabase.table("quotes") \
        .select("*, customers(name, inn, email)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not result.data:
        return page_layout("Not Found",
            H1("Quote not found"),
            A("← Back to Quotes", href="/quotes"),
            session=session
        )

    quote = result.data[0]
    customer = quote.get("customers", {})

    # Get quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    items = items_result.data or []

    workflow_status = quote.get("workflow_status") or quote.get("status", "draft")

    return page_layout(f"Quote {quote.get('idn_quote', '')}",
        Div(
            Div(
                H1(f"Quote {quote.get('idn_quote', '')}"),
                workflow_status_badge(workflow_status),
                style="display: flex; align-items: center; gap: 1rem;"
            ),
            Div(
                A("Edit", href=f"/quotes/{quote_id}/edit", role="button", cls="secondary", style="margin-right: 0.5rem;"),
                A("Add Products", href=f"/quotes/{quote_id}/products", role="button"),
            ),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        # Customer info
        Div(
            H3("Customer"),
            P(Strong(customer.get("name", "—"))),
            P(f"INN: {customer.get('inn', '')}") if customer.get("inn") else None,
            P(customer.get("email", "")) if customer.get("email") else None,
            cls="card"
        ),

        # Quote details
        Div(
            H3("Details"),
            Table(
                Tr(Td("Currency:"), Td(quote.get("currency", "RUB"))),
                Tr(Td("Delivery Terms:"), Td(quote.get("delivery_terms", "—"))),
                Tr(Td("Payment Terms:"), Td(f"{quote.get('payment_terms', 0)} days")),
                Tr(Td("Created:"), Td(quote.get("created_at", "")[:10])),
            ),
            cls="card"
        ),

        # Products
        Div(
            H3(f"Products ({len(items)})"),
            Table(
                Thead(Tr(Th("Product"), Th("SKU"), Th("Qty"), Th("Unit Price"), Th("Total"))),
                Tbody(
                    *[Tr(
                        Td(item.get("product_name", "—")),
                        Td(item.get("product_code", "—")),
                        Td(str(item.get("quantity", 0))),
                        Td(format_money(item.get("base_price_vat"), quote.get("currency", "RUB"))),
                        Td(format_money(
                            (item.get("quantity", 0) * Decimal(str(item.get("base_price_vat", 0)))) if item.get("base_price_vat") else None,
                            quote.get("currency", "RUB")
                        ))
                    ) for item in items]
                ) if items else Tbody(Tr(Td("No products yet", colspan="5", style="text-align: center;")))
            ),
            A("+ Add Products", href=f"/quotes/{quote_id}/products") if not items else None,
            cls="card"
        ),

        # Totals
        Div(
            H3("Totals"),
            Table(
                Tr(Td("Products Subtotal:"), Td(format_money(quote.get("subtotal"), quote.get("currency", "RUB")))),
                Tr(Td("Logistics:"), Td(format_money(quote.get("logistics_total"), quote.get("currency", "RUB")))),
                Tr(Td(Strong("Total:")), Td(Strong(format_money(quote.get("total_amount"), quote.get("currency", "RUB"))))),
            ),
            cls="card"
        ) if quote.get("total_amount") else None,

        # Workflow Actions (for draft quotes with items)
        Div(
            H3("Workflow"),
            Form(
                Button("📤 Submit for Procurement", type="submit",
                       style="background: #16a34a; color: white; font-size: 1rem; padding: 0.75rem 1.5rem;"),
                P("Send quote to procurement for supplier pricing.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
                method="post",
                action=f"/quotes/{quote_id}/submit-procurement"
            ),
            cls="card", style="border-left: 4px solid #16a34a;"
        ) if workflow_status == "draft" and items else None,

        # Workflow Actions (for pending_sales_review - submit for Quote Control)
        Div(
            H3("Workflow"),
            Form(
                Button("📋 Submit for Quote Control", type="submit",
                       style="background: #ec4899; color: white; font-size: 1rem; padding: 0.75rem 1.5rem;"),
                P("Send calculated quote to Zhanna for validation review.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
                method="post",
                action=f"/quotes/{quote_id}/submit-quote-control"
            ),
            cls="card", style="border-left: 4px solid #ec4899;"
        ) if workflow_status == "pending_sales_review" else None,

        # Workflow Actions (for pending_approval - Top Manager approval)
        Div(
            H3("⏳ Согласование"),
            P("Этот КП требует вашего одобрения.", style="margin-bottom: 1rem;"),
            Form(
                Div(
                    Label("Комментарий (необязательно):", for_="approval_comment"),
                    Input(type="text", name="comment", id="approval_comment",
                          placeholder="Ваш комментарий...", style="width: 100%; margin-bottom: 1rem;"),
                ),
                Div(
                    Button("✅ Одобрить", type="submit", name="action", value="approve",
                           style="background: #16a34a; color: white; margin-right: 1rem;"),
                    Button("❌ Отклонить", type="submit", name="action", value="reject",
                           style="background: #dc2626; color: white;"),
                ),
                method="post",
                action=f"/quotes/{quote_id}/manager-decision"
            ),
            cls="card", style="border-left: 4px solid #f59e0b;"
        ) if workflow_status == "pending_approval" and user_has_any_role(session, ["top_manager", "admin"]) else None,

        # Workflow Actions (for approved quotes - Send to Client)
        Div(
            H3("Workflow"),
            Form(
                Button("📧 Send to Client", type="submit",
                       style="background: #0891b2; color: white; font-size: 1rem; padding: 0.75rem 1.5rem;"),
                P("Send approved quote to the client.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
                method="post",
                action=f"/quotes/{quote_id}/send-to-client"
            ),
            cls="card", style="border-left: 4px solid #0891b2;"
        ) if workflow_status == "approved" and user_has_any_role(session, ["sales", "admin"]) else None,

        # Workflow Actions (for sent_to_client - Start Negotiation or Accept)
        Div(
            H3("Workflow"),
            P("Client has received the quote. What's next?", style="margin-bottom: 1rem;"),
            Div(
                Form(
                    Button("🤝 Start Negotiation", type="submit",
                           style="background: #14b8a6; color: white; margin-right: 1rem;"),
                    method="post",
                    action=f"/quotes/{quote_id}/start-negotiation",
                    style="display: inline;"
                ),
                Form(
                    Button("✅ Client Accepted - Submit for Spec", type="submit",
                           style="background: #16a34a; color: white;"),
                    method="post",
                    action=f"/quotes/{quote_id}/submit-spec-control",
                    style="display: inline;"
                ),
            ),
            cls="card", style="border-left: 4px solid #14b8a6;"
        ) if workflow_status == "sent_to_client" and user_has_any_role(session, ["sales", "admin"]) else None,

        # Workflow Actions (for client_negotiation - Accept Version)
        Div(
            H3("Workflow"),
            P("Negotiation in progress. When client accepts a version:", style="margin-bottom: 1rem;"),
            Form(
                Button("✅ Client Accepted Version - Submit for Spec", type="submit",
                       style="background: #16a34a; color: white; font-size: 1rem; padding: 0.75rem 1.5rem;"),
                P("Proceed to specification preparation.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
                method="post",
                action=f"/quotes/{quote_id}/submit-spec-control"
            ),
            cls="card", style="border-left: 4px solid #16a34a;"
        ) if workflow_status == "client_negotiation" and user_has_any_role(session, ["sales", "admin"]) else None,

        # Actions section
        Div(
            H3("Actions"),
            Div(
                A("Calculate", href=f"/quotes/{quote_id}/calculate", role="button"),
                A("Version History", href=f"/quotes/{quote_id}/versions", role="button", cls="secondary", style="margin-left: 0.5rem;"),
            ),
            H4("Export", style="margin-top: 1rem;"),
            Div(
                A("Specification PDF", href=f"/quotes/{quote_id}/export/specification", role="button", cls="secondary"),
                A("Invoice PDF", href=f"/quotes/{quote_id}/export/invoice", role="button", cls="secondary", style="margin-left: 0.5rem;"),
                A("Validation Excel", href=f"/quotes/{quote_id}/export/validation", role="button", cls="secondary", style="margin-left: 0.5rem;"),
            ),
            cls="card"
        ),

        A("← Back to Quotes", href="/quotes", style="display: inline-block; margin-top: 1rem;"),
        session=session
    )


# ============================================================================
# SUBMIT QUOTE FOR PROCUREMENT
# ============================================================================

@rt("/quotes/{quote_id}/submit-procurement")
def post(quote_id: str, session):
    """Submit a draft quote for procurement evaluation."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    # Use the workflow service to transition to pending_procurement
    result = transition_to_pending_procurement(
        quote_id=quote_id,
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Submitted by sales for procurement evaluation"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error submitting quote: {result.error_message}", cls="alert alert-error"),
            A("← Back to Quote", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SUBMIT QUOTE FOR QUOTE CONTROL
# ============================================================================

@rt("/quotes/{quote_id}/submit-quote-control")
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
            A("← Back to Quote", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# MANAGER APPROVAL/REJECTION
# ============================================================================

@rt("/quotes/{quote_id}/manager-decision")
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
                A("← Back to Quote", href=f"/quotes/{quote_id}"),
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
            A("← Back to Quote", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SEND TO CLIENT
# ============================================================================

@rt("/quotes/{quote_id}/send-to-client")
def post(quote_id: str, session):
    """Send approved quote to client."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="sent_to_client",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Quote sent to client"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Back to Quote", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# START NEGOTIATION
# ============================================================================

@rt("/quotes/{quote_id}/start-negotiation")
def post(quote_id: str, session):
    """Start client negotiation."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="client_negotiation",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Client negotiation started"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Back to Quote", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SUBMIT FOR SPEC CONTROL
# ============================================================================

@rt("/quotes/{quote_id}/submit-spec-control")
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
            A("← Back to Quote", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# QUOTE PRODUCTS
# ============================================================================

@rt("/quotes/{quote_id}/products")
def get(quote_id: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote
    quote_result = supabase.table("quotes") \
        .select("id, idn_quote, currency, organization_id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not quote_result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = quote_result.data[0]

    # Get existing products
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    items = items_result.data or []

    return page_layout(f"Products - {quote.get('idn_quote', '')}",
        H1(f"Add Products to {quote.get('idn_quote', '')}"),

        # Existing products table
        Div(
            H3(f"Products ({len(items)})"),
            Div(id="products-list",
                *[product_row(item, quote["currency"]) for item in items]
            ) if items else Div(P("No products yet. Add your first product below."), id="products-list"),
            cls="card"
        ),

        # Add product form
        Div(
            H3("Add Product"),
            Form(
                Div(
                    Label("Product Name *", Input(name="product_name", required=True, placeholder="Bearing SKF 6205")),
                    Label("Product Code (SKU)", Input(name="product_code", placeholder="SKF-6205-2RS")),
                    cls="form-row"
                ),
                Div(
                    Label("Brand", Input(name="brand", placeholder="SKF")),
                    Label("Quantity *", Input(name="quantity", type="number", value="1", min="1", required=True)),
                    cls="form-row"
                ),
                Div(
                    Label("Unit Price (with VAT) *",
                        Input(name="base_price_vat", type="number", step="0.01", min="0", required=True, placeholder="1500.00")
                    ),
                    Label("Weight per unit (kg)",
                        Input(name="weight_in_kg", type="number", step="0.001", min="0", placeholder="0.5")
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Supplier Country",
                        Select(
                            Option("Select country...", value=""),
                            Option("Turkey", value="TR"),
                            Option("China", value="CN"),
                            Option("Germany", value="DE"),
                            Option("Italy", value="IT"),
                            Option("USA", value="US"),
                            Option("Russia", value="RU"),
                            name="supplier_country"
                        )
                    ),
                    Label("HS Code (Customs)",
                        Input(name="customs_code", placeholder="8482109000")
                    ),
                    cls="form-row"
                ),
                Input(type="hidden", name="quote_id", value=quote_id),
                Div(
                    Button("Add Product", type="submit"),
                    cls="form-actions"
                ),
                method="post",
                action=f"/quotes/{quote_id}/products",
                hx_post=f"/quotes/{quote_id}/products",
                hx_target="#products-list",
                hx_swap="beforeend"
            ),
            cls="card"
        ),

        # Actions
        Div(
            A("← Back to Quote", href=f"/quotes/{quote_id}", role="button", cls="secondary"),
            A("Calculate Quote", href=f"/quotes/{quote_id}/calculate", role="button", style="margin-left: 1rem;") if items else None,
            cls="form-actions", style="margin-top: 1rem;"
        ),

        session=session
    )


def product_row(item, currency="RUB"):
    """Render a single product row"""
    total = (item.get("quantity", 0) * Decimal(str(item.get("base_price_vat", 0)))) if item.get("base_price_vat") else Decimal(0)
    return Div(
        Div(
            Strong(item.get("product_name", "—")),
            Small(f" ({item.get('product_code', 'No SKU')})", style="color: #666;"),
            style="flex: 2;"
        ),
        Div(f"Qty: {item.get('quantity', 0)}", style="flex: 1;"),
        Div(format_money(item.get("base_price_vat"), currency), style="flex: 1;"),
        Div(format_money(total, currency), style="flex: 1; font-weight: bold;"),
        Div(
            Button("×",
                hx_delete=f"/quotes/{item['quote_id']}/products/{item['id']}",
                hx_target=f"#product-{item['id']}",
                hx_swap="outerHTML",
                cls="danger",
                style="padding: 0.25rem 0.5rem; font-size: 1rem;"
            ),
            style="flex: 0;"
        ),
        id=f"product-{item['id']}",
        style="display: flex; align-items: center; gap: 1rem; padding: 0.75rem; border-bottom: 1px solid #eee;"
    )


@rt("/quotes/{quote_id}/products")
def post(quote_id: str, product_name: str, product_code: str, brand: str, quantity: int,
         base_price_vat: float, weight_in_kg: float, supplier_country: str, customs_code: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id, currency") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not quote_result.data:
        return Div("Quote not found", cls="alert alert-error")

    quote = quote_result.data[0]

    try:
        result = supabase.table("quote_items").insert({
            "quote_id": quote_id,
            "product_name": product_name,
            "product_code": product_code or None,
            "brand": brand or None,
            "quantity": quantity,
            "base_price_vat": base_price_vat,
            "weight_in_kg": weight_in_kg or None,
            "supplier_country": supplier_country or None,
            "customs_code": customs_code or None,
        }).execute()

        new_item = result.data[0]
        # Return just the new row for HTMX to append
        return product_row(new_item, quote["currency"])

    except Exception as e:
        return Div(f"Error: {str(e)}", cls="alert alert-error")


@rt("/quotes/{quote_id}/products/{item_id}")
def delete(quote_id: str, item_id: str, session):
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
        .execute()

    if not quote_result.data:
        return ""

    try:
        supabase.table("quote_items") \
            .delete() \
            .eq("id", item_id) \
            .eq("quote_id", quote_id) \
            .execute()
        # Return empty string to remove the element
        return ""
    except Exception as e:
        return Div(f"Error: {str(e)}", cls="alert alert-error")


# ============================================================================
# QUOTE EDIT
# ============================================================================

@rt("/quotes/{quote_id}/edit")
def get(quote_id: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote
    result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
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

    return page_layout(f"Edit {quote.get('idn_quote', '')}",
        H1(f"Edit Quote {quote.get('idn_quote', '')}"),

        Div(
            Form(
                Div(
                    Label("Customer *",
                        Select(
                            *[Option(
                                f"{c['name']} ({c.get('inn', '')})",
                                value=c["id"],
                                selected=(c["id"] == quote.get("customer_id"))
                            ) for c in customers],
                            name="customer_id", required=True
                        )
                    ),
                    Label("Status",
                        Select(
                            Option("Draft", value="draft", selected=quote.get("status") == "draft"),
                            Option("Sent", value="sent", selected=quote.get("status") == "sent"),
                            Option("Approved", value="approved", selected=quote.get("status") == "approved"),
                            Option("Rejected", value="rejected", selected=quote.get("status") == "rejected"),
                            name="status"
                        )
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Currency",
                        Select(
                            Option("RUB", value="RUB", selected=quote.get("currency") == "RUB"),
                            Option("USD", value="USD", selected=quote.get("currency") == "USD"),
                            Option("EUR", value="EUR", selected=quote.get("currency") == "EUR"),
                            name="currency"
                        )
                    ),
                    Label("Delivery Terms",
                        Select(
                            Option("EXW", value="EXW", selected=quote.get("delivery_terms") == "EXW"),
                            Option("FOB", value="FOB", selected=quote.get("delivery_terms") == "FOB"),
                            Option("CIF", value="CIF", selected=quote.get("delivery_terms") == "CIF"),
                            Option("DDP", value="DDP", selected=quote.get("delivery_terms") == "DDP"),
                            name="delivery_terms"
                        )
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Payment Terms (days)",
                        Input(name="payment_terms", type="number", value=str(quote.get("payment_terms", 30)), min="0")
                    ),
                    Label("Delivery Days",
                        Input(name="delivery_days", type="number", value=str(quote.get("delivery_days", 45)), min="0")
                    ),
                    cls="form-row"
                ),
                Label("Notes", Textarea(quote.get("notes", "") or "", name="notes", rows="3")),
                Div(
                    Button("Save Changes", type="submit"),
                    A("Cancel", href=f"/quotes/{quote_id}", role="button", cls="secondary"),
                    Button("Delete Quote", type="button", cls="danger",
                        hx_delete=f"/quotes/{quote_id}",
                        hx_confirm="Are you sure you want to delete this quote?"),
                    cls="form-actions"
                ),
                method="post",
                action=f"/quotes/{quote_id}/edit"
            ),
            cls="card"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/edit")
def post(quote_id: str, customer_id: str, status: str, currency: str, delivery_terms: str,
         payment_terms: int, delivery_days: int, notes: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    try:
        supabase.table("quotes").update({
            "customer_id": customer_id,
            "status": status,
            "currency": currency,
            "delivery_terms": delivery_terms,
            "payment_terms": payment_terms,
            "delivery_days": delivery_days,
            "notes": notes or None,
            "updated_at": datetime.now().isoformat()
        }).eq("id", quote_id).eq("organization_id", user["org_id"]).execute()

        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    except Exception as e:
        return page_layout("Error",
            Div(f"Error: {str(e)}", cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}/edit"),
            session=session
        )


@rt("/quotes/{quote_id}")
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

@rt("/customers/{customer_id}")
def get(customer_id: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    result = supabase.table("customers") \
        .select("*") \
        .eq("id", customer_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not result.data:
        return page_layout("Not Found", H1("Customer not found"), session=session)

    customer = result.data[0]

    # Get customer's quotes
    quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, status, total_amount, created_at") \
        .eq("customer_id", customer_id) \
        .order("created_at", desc=True) \
        .limit(10) \
        .execute()

    quotes = quotes_result.data or []

    return page_layout(customer.get("name", "Customer"),
        Div(
            H1(customer.get("name", "—")),
            A("Edit", href=f"/customers/{customer_id}/edit", role="button", cls="secondary"),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        Div(
            H3("Contact Information"),
            Table(
                Tr(Td("INN:"), Td(customer.get("inn") or "—")),
                Tr(Td("Email:"), Td(customer.get("email") or "—")),
                Tr(Td("Phone:"), Td(customer.get("phone") or "—")),
                Tr(Td("Address:"), Td(customer.get("address") or "—")),
            ),
            cls="card"
        ),

        Div(
            H3(f"Quotes ({len(quotes)})"),
            Table(
                Thead(Tr(Th("Quote #"), Th("Status"), Th("Total"), Th("Date"))),
                Tbody(
                    *[Tr(
                        Td(A(q.get("idn_quote", "—"), href=f"/quotes/{q['id']}")),
                        Td(status_badge(q.get("status", "draft"))),
                        Td(format_money(q.get("total_amount"))),
                        Td(q.get("created_at", "")[:10])
                    ) for q in quotes]
                ) if quotes else Tbody(Tr(Td("No quotes yet", colspan="4")))
            ),
            cls="card"
        ),

        A("← Back to Customers", href="/customers"),
        session=session
    )


@rt("/customers/{customer_id}/edit")
def get(customer_id: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    result = supabase.table("customers") \
        .select("*") \
        .eq("id", customer_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not result.data:
        return page_layout("Not Found", H1("Customer not found"), session=session)

    customer = result.data[0]

    return page_layout(f"Edit {customer.get('name', 'Customer')}",
        H1(f"Edit Customer"),

        Div(
            Form(
                Div(
                    Label("Company Name *", Input(name="name", value=customer.get("name", ""), required=True)),
                    Label("INN", Input(name="inn", value=customer.get("inn", "") or "")),
                    cls="form-row"
                ),
                Div(
                    Label("Email", Input(name="email", type="email", value=customer.get("email", "") or "")),
                    Label("Phone", Input(name="phone", value=customer.get("phone", "") or "")),
                    cls="form-row"
                ),
                Label("Address", Textarea(customer.get("address", "") or "", name="address", rows="3")),
                Div(
                    Button("Save Changes", type="submit"),
                    A("Cancel", href=f"/customers/{customer_id}", role="button", cls="secondary"),
                    cls="form-actions"
                ),
                method="post",
                action=f"/customers/{customer_id}/edit"
            ),
            cls="card"
        ),

        session=session
    )


@rt("/customers/{customer_id}/edit")
def post(customer_id: str, name: str, inn: str, email: str, phone: str, address: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    try:
        supabase.table("customers").update({
            "name": name,
            "inn": inn or None,
            "email": email or None,
            "phone": phone or None,
            "address": address or None,
            "updated_at": datetime.now().isoformat()
        }).eq("id", customer_id).eq("organization_id", user["org_id"]).execute()

        return RedirectResponse(f"/customers/{customer_id}", status_code=303)

    except Exception as e:
        return page_layout("Error",
            Div(f"Error: {str(e)}", cls="alert alert-error"),
            session=session
        )


# ============================================================================
# QUOTE CALCULATION (calls existing backend API)
# ============================================================================

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ============================================================================
# CALCULATION HELPERS
# ============================================================================

def build_calculation_inputs(items: List[Dict], variables: Dict[str, Any]) -> List[QuoteCalculationInput]:
    """Build calculation inputs for all quote items."""
    calc_inputs = []
    for item in items:
        # Product fields
        product = {
            'base_price_vat': safe_decimal(item.get('base_price_vat')),
            'quantity': item.get('quantity', 1),
            'weight_in_kg': safe_decimal(item.get('weight_in_kg')),
            'customs_code': item.get('customs_code', '0000000000'),
            'supplier_country': item.get('supplier_country', variables.get('supplier_country', 'Турция')),
            'currency_of_base_price': item.get('currency_of_base_price', variables.get('currency_of_base_price', 'USD')),
            'import_tariff': item.get('import_tariff'),
            'markup': item.get('markup'),
            'supplier_discount': item.get('supplier_discount'),
        }

        # Get exchange rate (default to 1.0 if same currency)
        exchange_rate = safe_decimal(variables.get('exchange_rate', '1.0'))

        calc_input = map_variables_to_calculation_input(
            product=product,
            variables=variables,
            exchange_rate=exchange_rate
        )
        calc_inputs.append(calc_input)

    return calc_inputs


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

@rt("/quotes/{quote_id}/preview")
def post(
    quote_id: str,
    session,
    # Company settings
    seller_company: str = "МАСТЕР БЭРИНГ ООО",
    offer_sale_type: str = "поставка",
    offer_incoterms: str = "DDP",
    # Pricing
    markup: str = "15",
    supplier_discount: str = "0",
    exchange_rate: str = "1.0",
    delivery_time: str = "30",
    # Logistics
    logistics_supplier_hub: str = "0",
    logistics_hub_customs: str = "0",
    logistics_customs_client: str = "0",
    # Brokerage
    brokerage_hub: str = "0",
    brokerage_customs: str = "0",
    warehousing_at_customs: str = "0",
    customs_documentation: str = "0",
    brokerage_extra: str = "0",
    # Payment terms
    advance_from_client: str = "100",
    advance_to_supplier: str = "100",
    time_to_advance: str = "0",
    time_to_advance_on_receiving: str = "0",
    # DM Fee
    dm_fee_type: str = "fixed",
    dm_fee_value: str = "0",
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
        .execute()

    if not quote_result.data:
        return Div("Quote not found", cls="alert alert-error", id="preview-panel")

    quote = quote_result.data[0]
    currency = quote.get("currency", "USD")

    # Get items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    if not items:
        return Div("Add products to preview.", cls="alert alert-info", id="preview-panel")

    try:
        # Build variables from form parameters
        variables = {
            'currency_of_quote': currency,
            'markup': safe_decimal(markup),
            'supplier_discount': safe_decimal(supplier_discount),
            'offer_incoterms': offer_incoterms,
            'delivery_time': safe_int(delivery_time),
            'seller_company': seller_company,
            'offer_sale_type': offer_sale_type,

            # Logistics
            'logistics_supplier_hub': safe_decimal(logistics_supplier_hub),
            'logistics_hub_customs': safe_decimal(logistics_hub_customs),
            'logistics_customs_client': safe_decimal(logistics_customs_client),

            # Brokerage
            'brokerage_hub': safe_decimal(brokerage_hub),
            'brokerage_customs': safe_decimal(brokerage_customs),
            'warehousing_at_customs': safe_decimal(warehousing_at_customs),
            'customs_documentation': safe_decimal(customs_documentation),
            'brokerage_extra': safe_decimal(brokerage_extra),

            # Payment terms
            'advance_from_client': safe_decimal(advance_from_client),
            'advance_to_supplier': safe_decimal(advance_to_supplier),
            'time_to_advance': safe_int(time_to_advance),
            'time_to_advance_on_receiving': safe_int(time_to_advance_on_receiving),

            # DM Fee
            'dm_fee_type': dm_fee_type,
            'dm_fee_value': safe_decimal(dm_fee_value),

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

@rt("/quotes/{quote_id}/calculate")
def get(quote_id: str, session):
    """Calculate quote using the 13-phase calculation engine with HTMX live preview."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote with items
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .execute()

    if not quote_result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = quote_result.data[0]
    currency = quote.get("currency", "USD")

    # Get quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    if not items:
        return page_layout("Cannot Calculate",
            H1("No Products"),
            P("Add products to the quote before calculating."),
            A("Back to Quote", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Try to load existing calculation variables
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    saved_vars = vars_result.data[0]["variables"] if vars_result.data else {}

    # Default values (with saved values taking precedence)
    def get_var(key, default):
        return saved_vars.get(key, default)

    return page_layout(f"Calculate - {quote.get('idn_quote', '')}",
        H1(f"Calculate {quote.get('idn_quote', '')}"),
        P(f"Customer: {quote.get('customers', {}).get('name', '-')} | Currency: {currency} | {len(items)} products",
          style="color: #666;"),

        # Main form with HTMX live preview
        Form(
            Div(
                # Left column: Variables
                Div(
                    # Company & Deal Type
                    Div(
                        H3("Company Settings"),
                        Label("Seller Company",
                            Select(
                                Option("МАСТЕР БЭРИНГ ООО", value="МАСТЕР БЭРИНГ ООО", selected=get_var('seller_company', '') == "МАСТЕР БЭРИНГ ООО"),
                                Option("TEXCEL OTOMOTIV", value="TEXCEL OTOMOTİV TİCARET LİMİTED ŞİRKETİ"),
                                Option("GESTUS OTOMOTIV", value="GESTUS OTOMOTİV TİCARET LİMİTED ŞİRKETİ"),
                                name="seller_company"
                            )
                        ),
                        Div(
                            Label("Sale Type",
                                Select(
                                    Option("Поставка", value="поставка", selected=True),
                                    Option("Транзит", value="транзит"),
                                    name="offer_sale_type"
                                )
                            ),
                            Label("Incoterms",
                                Select(
                                    Option("DDP", value="DDP", selected=get_var('offer_incoterms', 'DDP') == "DDP"),
                                    Option("DAP", value="DAP", selected=get_var('offer_incoterms', '') == "DAP"),
                                    Option("CIF", value="CIF", selected=get_var('offer_incoterms', '') == "CIF"),
                                    Option("FOB", value="FOB", selected=get_var('offer_incoterms', '') == "FOB"),
                                    Option("EXW", value="EXW", selected=get_var('offer_incoterms', '') == "EXW"),
                                    name="offer_incoterms"
                                )
                            ),
                            cls="form-row"
                        ),
                        cls="card"
                    ),

                    # Pricing
                    Div(
                        H3("Pricing"),
                        Div(
                            Label("Markup %",
                                Input(name="markup", type="number", value=str(get_var('markup', 15)), min="0", max="100", step="0.1")
                            ),
                            Label("Supplier Discount %",
                                Input(name="supplier_discount", type="number", value=str(get_var('supplier_discount', 0)), min="0", max="100", step="0.1")
                            ),
                            cls="form-row"
                        ),
                        Div(
                            Label("Exchange Rate (to quote currency)",
                                Input(name="exchange_rate", type="number", value=str(get_var('exchange_rate', 1.0)), min="0.0001", step="0.0001")
                            ),
                            Label("Delivery Time (days)",
                                Input(name="delivery_time", type="number", value=str(get_var('delivery_time', 30)), min="1", max="365")
                            ),
                            cls="form-row"
                        ),
                        cls="card"
                    ),

                    # Logistics
                    Div(
                        H3("Logistics Costs"),
                        Div(
                            Label("Supplier → Hub",
                                Input(name="logistics_supplier_hub", type="number", value=str(get_var('logistics_supplier_hub', 0)), min="0", step="0.01")
                            ),
                            Label("Hub → Customs",
                                Input(name="logistics_hub_customs", type="number", value=str(get_var('logistics_hub_customs', 0)), min="0", step="0.01")
                            ),
                            Label("Customs → Client",
                                Input(name="logistics_customs_client", type="number", value=str(get_var('logistics_customs_client', 0)), min="0", step="0.01")
                            ),
                            cls="form-row", style="grid-template-columns: 1fr 1fr 1fr;"
                        ),
                        cls="card"
                    ),

                    # Brokerage
                    Div(
                        H3("Brokerage Costs"),
                        Div(
                            Label("Hub Brokerage",
                                Input(name="brokerage_hub", type="number", value=str(get_var('brokerage_hub', 0)), min="0", step="0.01")
                            ),
                            Label("Customs Brokerage",
                                Input(name="brokerage_customs", type="number", value=str(get_var('brokerage_customs', 0)), min="0", step="0.01")
                            ),
                            cls="form-row"
                        ),
                        Div(
                            Label("Warehousing",
                                Input(name="warehousing_at_customs", type="number", value=str(get_var('warehousing_at_customs', 0)), min="0", step="0.01")
                            ),
                            Label("Documentation",
                                Input(name="customs_documentation", type="number", value=str(get_var('customs_documentation', 0)), min="0", step="0.01")
                            ),
                            Label("Extra",
                                Input(name="brokerage_extra", type="number", value=str(get_var('brokerage_extra', 0)), min="0", step="0.01")
                            ),
                            cls="form-row", style="grid-template-columns: 1fr 1fr 1fr;"
                        ),
                        cls="card"
                    ),

                    # Payment Terms
                    Div(
                        H3("Payment Terms"),
                        Div(
                            Label("Client Advance %",
                                Input(name="advance_from_client", type="number", value=str(get_var('advance_from_client', 100)), min="0", max="100", step="1")
                            ),
                            Label("Supplier Advance %",
                                Input(name="advance_to_supplier", type="number", value=str(get_var('advance_to_supplier', 100)), min="0", max="100", step="1")
                            ),
                            cls="form-row"
                        ),
                        Div(
                            Label("Days to Advance",
                                Input(name="time_to_advance", type="number", value=str(get_var('time_to_advance', 0)), min="0")
                            ),
                            Label("Days to Final Payment",
                                Input(name="time_to_advance_on_receiving", type="number", value=str(get_var('time_to_advance_on_receiving', 0)), min="0")
                            ),
                            cls="form-row"
                        ),
                        cls="card"
                    ),

                    # DM Fee
                    Div(
                        H3("DM Fee"),
                        Div(
                            Label("Fee Type",
                                Select(
                                    Option("Fixed", value="fixed", selected=get_var('dm_fee_type', 'fixed') == "fixed"),
                                    Option("Percentage", value="percentage", selected=get_var('dm_fee_type', '') == "percentage"),
                                    name="dm_fee_type"
                                )
                            ),
                            Label("Fee Value",
                                Input(name="dm_fee_value", type="number", value=str(get_var('dm_fee_value', 0)), min="0", step="0.01")
                            ),
                            cls="form-row"
                        ),
                        cls="card"
                    ),

                    style="flex: 1;"
                ),

                # Right column: Preview
                Div(
                    Div(
                        H3("Live Preview"),
                        P("Adjust values on the left. Preview updates automatically.", style="color: #666; font-size: 0.875rem;"),
                        Div(
                            P("Enter values and click below to preview, or wait for auto-update."),
                            cls="alert alert-info",
                            id="preview-panel"
                        ),
                        Button("Update Preview", type="button",
                            hx_post=f"/quotes/{quote_id}/preview",
                            hx_target="#preview-panel",
                            hx_include="closest form",
                            style="margin-bottom: 1rem;"
                        ),
                        cls="card", style="position: sticky; top: 1rem;"
                    ),
                    style="flex: 1; min-width: 400px;"
                ),

                style="display: flex; gap: 1rem; flex-wrap: wrap;"
            ),

            # Actions
            Div(
                Button("Save Calculation", type="submit", style="font-size: 1.1rem; padding: 1rem 2rem;"),
                A("Cancel", href=f"/quotes/{quote_id}", role="button", cls="secondary", style="margin-left: 1rem;"),
                cls="form-actions", style="margin-top: 1rem; padding: 1rem; background: white; border-radius: 8px;"
            ),

            method="post",
            action=f"/quotes/{quote_id}/calculate",
            hx_post=f"/quotes/{quote_id}/preview",
            hx_target="#preview-panel",
            hx_trigger="input changed delay:500ms from:find input, input changed delay:500ms from:find select"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/calculate")
def post(
    quote_id: str,
    session,
    # Company settings
    seller_company: str = "МАСТЕР БЭРИНГ ООО",
    offer_sale_type: str = "поставка",
    offer_incoterms: str = "DDP",
    # Pricing
    markup: str = "15",
    supplier_discount: str = "0",
    exchange_rate: str = "1.0",
    delivery_time: str = "30",
    # Logistics
    logistics_supplier_hub: str = "0",
    logistics_hub_customs: str = "0",
    logistics_customs_client: str = "0",
    # Brokerage
    brokerage_hub: str = "0",
    brokerage_customs: str = "0",
    warehousing_at_customs: str = "0",
    customs_documentation: str = "0",
    brokerage_extra: str = "0",
    # Payment terms
    advance_from_client: str = "100",
    advance_to_supplier: str = "100",
    time_to_advance: str = "0",
    time_to_advance_on_receiving: str = "0",
    # DM Fee
    dm_fee_type: str = "fixed",
    dm_fee_value: str = "0",
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
        .execute()

    if not quote_result.data:
        return page_layout("Error", Div("Quote not found", cls="alert alert-error"), session=session)

    quote = quote_result.data[0]
    currency = quote.get("currency", "USD")

    # Get items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    if not items:
        return page_layout("Error",
            Div("Cannot calculate - no products in quote", cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}"),
            session=session
        )

    try:
        # Build variables from form parameters
        variables = {
            'currency_of_quote': currency,
            'markup': safe_decimal(markup),
            'supplier_discount': safe_decimal(supplier_discount),
            'offer_incoterms': offer_incoterms,
            'delivery_time': safe_int(delivery_time),
            'seller_company': seller_company,
            'offer_sale_type': offer_sale_type,

            # Logistics
            'logistics_supplier_hub': safe_decimal(logistics_supplier_hub),
            'logistics_hub_customs': safe_decimal(logistics_hub_customs),
            'logistics_customs_client': safe_decimal(logistics_customs_client),

            # Brokerage
            'brokerage_hub': safe_decimal(brokerage_hub),
            'brokerage_customs': safe_decimal(brokerage_customs),
            'warehousing_at_customs': safe_decimal(warehousing_at_customs),
            'customs_documentation': safe_decimal(customs_documentation),
            'brokerage_extra': safe_decimal(brokerage_extra),

            # Payment terms
            'advance_from_client': safe_decimal(advance_from_client),
            'advance_to_supplier': safe_decimal(advance_to_supplier),
            'time_to_advance': safe_int(time_to_advance),
            'time_to_advance_on_receiving': safe_int(time_to_advance_on_receiving),

            # DM Fee
            'dm_fee_type': dm_fee_type,
            'dm_fee_value': safe_decimal(dm_fee_value),

            # Exchange rate
            'exchange_rate': safe_decimal(exchange_rate),
        }

        # Build calculation inputs for all items
        calc_inputs = build_calculation_inputs(items, variables)

        # Run full 13-phase calculation engine
        results = calculate_multiproduct_quote(calc_inputs)

        # Calculate totals from results
        total_purchase = sum(safe_decimal(r.purchase_price_total_quote_currency) for r in results)
        total_logistics = sum(safe_decimal(r.logistics_total) for r in results)
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

        avg_margin = (total_profit / total_cogs * 100) if total_cogs else Decimal("0")

        # Update quote totals (only use columns that exist in quotes table)
        supabase.table("quotes").update({
            "subtotal": float(total_purchase),
            "total_amount": float(total_with_vat),
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
                "N16": float(result.purchase_price_no_vat or 0),
                "P16": float(result.purchase_price_after_discount or 0),
                "R16": float(result.purchase_price_per_unit_quote_currency or 0),
                "S16": float(result.purchase_price_total_quote_currency or 0),
                "T16": float(result.logistics_first_leg or 0),
                "U16": float(result.logistics_last_leg or 0),
                "V16": float(result.logistics_total or 0),
                "Y16": float(result.customs_fee or 0),
                "AA16": float(result.cogs_per_unit or 0),
                "AB16": float(result.cogs_per_product or 0),
                "AF16": float(result.profit or 0),
                "AG16": float(result.dm_fee or 0),
                "AD16": float(result.sale_price_per_unit_excl_financial or 0),
                "AJ16": float(result.sales_price_per_unit_no_vat or 0),
                "AK16": float(result.sales_price_total_no_vat or 0),
                "AL16": float(result.sales_price_total_with_vat or 0),
                "AP16": float(result.vat_net_payable or 0),
                "BA16": float(result.financing_cost_initial or 0),
                "BB16": float(result.financing_cost_credit or 0),
            }

            item_result = {
                "quote_id": quote_id,
                "quote_item_id": item["id"],
                "phase_results": phase_results,
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

        # Store calculation summary
        calc_summary = {
            "quote_id": quote_id,
            "calc_s16_total_purchase_price": float(total_purchase),
            "calc_v16_total_logistics": float(total_logistics),
            "calc_total_brokerage": float(total_brokerage),
            "calc_ae16_sale_price_total": float(total_no_vat),
            "calc_al16_total_with_vat": float(total_with_vat),
            "calc_af16_profit_margin": float(avg_margin),
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

        # Create immutable quote version for audit trail
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
            version = create_quote_version(
                quote_id=quote_id,
                user_id=user["id"],
                variables=variables,
                items=items,
                results=all_results,
                totals=version_totals,
                change_reason="Calculation saved",
                customer_id=quote.get("customer_id")
            )
            version_number = version.get("version_number") if version else None
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

        return page_layout(f"Calculation Results - {quote.get('idn_quote', '')}",
            Div("Calculation completed and saved!", cls="alert alert-success"),

            H1(f"Results for {quote.get('idn_quote', '')}"),

            # Summary stats
            Div(
                Div(
                    Div("Total (excl VAT)", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_no_vat, currency), cls="stat-value"),
                    cls="stat-card"
                ),
                Div(
                    Div("Total (incl VAT)", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_with_vat, currency), cls="stat-value", style="color: #28a745;"),
                    cls="stat-card"
                ),
                Div(
                    Div("Total Profit", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_profit, currency), cls="stat-value"),
                    cls="stat-card"
                ),
                Div(
                    Div("Avg Margin", style="font-size: 0.875rem; color: #666;"),
                    Div(f"{avg_margin:.1f}%", cls="stat-value"),
                    cls="stat-card"
                ),
                cls="stats-grid"
            ),

            # Cost breakdown
            Div(
                H3("Cost Breakdown"),
                Table(
                    Tr(Td("Products Purchase Total:"), Td(format_money(total_purchase, currency))),
                    Tr(Td("Logistics Total:"), Td(format_money(total_logistics, currency))),
                    Tr(Td("Brokerage Total:"), Td(format_money(total_brokerage, currency))),
                    Tr(Td("Total COGS:"), Td(format_money(total_cogs, currency))),
                    Tr(Td(Strong("VAT Payable:")), Td(Strong(format_money(total_vat, currency)))),
                ),
                cls="card"
            ),

            # Product details
            Div(
                H3("Product Details"),
                Table(
                    Thead(
                        Tr(
                            Th("Product"),
                            Th("Qty"),
                            Th("COGS/unit"),
                            Th("Price/unit"),
                            Th("Total"),
                            Th("Profit"),
                        )
                    ),
                    Tbody(*product_rows),
                    Tfoot(
                        Tr(
                            Td(Strong("TOTAL"), colspan="4"),
                            Td(Strong(format_money(total_with_vat, currency))),
                            Td(Strong(format_money(total_profit, currency))),
                        )
                    ),
                ),
                cls="card"
            ),

            # Variables used
            Div(
                H3("Calculation Variables"),
                Table(
                    Tr(Td("Markup:"), Td(f"{variables['markup']}%")),
                    Tr(Td("Incoterms:"), Td(variables['offer_incoterms'])),
                    Tr(Td("Delivery Time:"), Td(f"{variables['delivery_time']} days")),
                    Tr(Td("Client Advance:"), Td(f"{variables['advance_from_client']}%")),
                    Tr(Td("Exchange Rate:"), Td(str(variables['exchange_rate']))),
                ),
                cls="card"
            ),

            # Actions
            Div(
                A("← Back to Quote", href=f"/quotes/{quote_id}", role="button"),
                A("Recalculate", href=f"/quotes/{quote_id}/calculate", role="button", cls="secondary", style="margin-left: 1rem;"),
                cls="form-actions"
            ),

            session=session
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return page_layout("Calculation Error",
            Div(f"Error: {str(e)}", cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}/calculate"),
            session=session
        )


# ============================================================================
# VERSION HISTORY ROUTES
# ============================================================================

@rt("/quotes/{quote_id}/versions")
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

    return page_layout(f"Version History - {quote.get('idn_quote', '')}",
        H1(f"Version History - {quote.get('idn_quote', '')}"),
        P(f"Customer: {quote.get('customers', {}).get('name', '-')}"),

        Table(
            Thead(
                Tr(
                    Th("Version"),
                    Th("Status"),
                    Th("Total"),
                    Th("Change Reason"),
                    Th("Created"),
                    Th("Actions"),
                )
            ),
            Tbody(*version_rows) if version_rows else Tbody(
                Tr(Td("No versions yet. Run calculation to create first version.", colspan="6", style="text-align: center;"))
            ),
        ),

        Div(
            A("← Back to Quote", href=f"/quotes/{quote_id}", role="button"),
            A("Calculate New Version", href=f"/quotes/{quote_id}/calculate", role="button", cls="secondary", style="margin-left: 0.5rem;"),
            style="margin-top: 1rem;"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/versions/{version_num}")
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
        Div(
            H1(f"Version {version_num}"),
            status_badge(version.get("status", "draft")),
            style="display: flex; align-items: center; gap: 1rem;"
        ),

        # Version metadata
        Div(
            H3("Version Info"),
            Table(
                Tr(Td("Created:"), Td(version.get("created_at", "")[:16].replace("T", " "))),
                Tr(Td("Change Reason:"), Td(version.get("change_reason", "-"))),
                Tr(Td("Status:"), Td(version.get("status", "draft"))),
                Tr(Td("Total:"), Td(Strong(format_money(version.get("total_quote_currency"), currency)))),
            ),
            cls="card"
        ),

        # Variables snapshot
        Div(
            H3("Calculation Variables"),
            Table(
                Tr(Td("Markup:"), Td(f"{variables.get('markup', '-')}%")),
                Tr(Td("Incoterms:"), Td(variables.get('offer_incoterms', '-'))),
                Tr(Td("Delivery Time:"), Td(f"{variables.get('delivery_time', '-')} days")),
                Tr(Td("Client Advance:"), Td(f"{variables.get('advance_from_client', '-')}%")),
                Tr(Td("Exchange Rate:"), Td(str(variables.get('exchange_rate', '-')))),
            ),
            cls="card"
        ),

        # Products snapshot
        Div(
            H3("Products"),
            Table(
                Thead(Tr(Th("Product"), Th("Qty"), Th("Price/Unit"), Th("Total"), Th("Profit"))),
                Tbody(*product_rows) if product_rows else Tbody(Tr(Td("No products", colspan="5"))),
            ),
            cls="card"
        ),

        Div(
            A("← Version History", href=f"/quotes/{quote_id}/versions", role="button"),
            A("Back to Quote", href=f"/quotes/{quote_id}", role="button", cls="secondary", style="margin-left: 0.5rem;"),
            style="margin-top: 1rem;"
        ),

        session=session
    )


# ============================================================================
# EXPORT ROUTES
# ============================================================================

@rt("/quotes/{quote_id}/export/specification")
def get(quote_id: str, session):
    """Export Specification PDF"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    try:
        # Fetch all export data
        data = fetch_export_data(quote_id, user["org_id"])

        # Generate PDF
        pdf_bytes = generate_specification_pdf(data)

        # Return as file download
        from starlette.responses import Response
        filename = f"specification_{data.quote.get('quote_number', quote_id)}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate PDF: {str(e)}", cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}"),
            session=session
        )


@rt("/quotes/{quote_id}/export/invoice")
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
        filename = f"invoice_{data.quote.get('quote_number', quote_id)}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate PDF: {str(e)}", cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}"),
            session=session
        )


@rt("/quotes/{quote_id}/export/validation")
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

        # Return as file download
        from starlette.responses import Response
        filename = f"validation_{data.quote.get('quote_number', quote_id)}.xlsx"
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate Excel: {str(e)}", cls="alert alert-error"),
            A("← Back", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SETTINGS PAGE
# ============================================================================

@rt("/settings")
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
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

    return page_layout("Settings",
        H1("Organization Settings"),

        # Organization info
        Div(
            H3("Organization Details"),
            Form(
                Label("Organization Name",
                    Input(name="name", value=org.get("name", ""), readonly=True)
                ),
                P("Contact your administrator to change organization details.", style="color: #666; font-size: 0.875rem;"),
                cls="card"
            )
        ),

        # Calculation defaults
        Div(
            H3("Calculation Defaults"),
            Form(
                Div(
                    Label("Default Forex Risk %",
                        Input(name="rate_forex_risk", type="number", value=str(calc_settings.get("rate_forex_risk", 3)), step="0.1", min="0", max="20")
                    ),
                    Label("Default Financial Commission %",
                        Input(name="rate_fin_comm", type="number", value=str(calc_settings.get("rate_fin_comm", 2)), step="0.1", min="0", max="20")
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Daily Loan Interest Rate %",
                        Input(name="rate_loan_interest_daily", type="number", value=str(round(calc_settings.get("rate_loan_interest_daily", 0.05), 6)), step="any", min="0", max="1")
                    ),
                    cls="form-row"
                ),
                Div(
                    Button("Save Settings", type="submit"),
                    cls="form-actions"
                ),
                method="post",
                action="/settings"
            ),
            cls="card"
        ),

        # User info
        Div(
            H3("Your Account"),
            Table(
                Tr(Td("Email:"), Td(user.get("email", "—"))),
                Tr(Td("User ID:"), Td(Code(user.get("id", "—")[:8] + "..."))),
            ),
            cls="card"
        ),

        # Telegram settings link
        Div(
            H3("📱 Telegram"),
            P("Привяжите Telegram для получения уведомлений о задачах и согласованиях.",
              style="color: #666; margin-bottom: 1rem;"),
            A("Настройки Telegram →", href="/settings/telegram",
              style="display: inline-block; background: #3b82f6; color: white; padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none;"),
            cls="card"
        ),

        session=session
    )


@rt("/settings")
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
            A("← Back", href="/settings"),
            session=session
        )


# ============================================================================
# TELEGRAM SETTINGS PAGE (Feature #56)
# ============================================================================

@rt("/settings/telegram")
def get(session):
    """Telegram settings page for account linking.

    Feature #56: UI генерации кода верификации

    This page allows users to:
    - See their current Telegram connection status
    - Generate a verification code to link their Telegram account
    - Unlink their Telegram account
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    # Get current Telegram status
    status = get_user_telegram_status(user["id"])

    # Build status display
    if status.is_verified:
        # Account is linked and verified
        status_card = Div(
            Div(
                Span("✅", style="font-size: 2rem;"),
                H3("Telegram привязан", style="margin: 0.5rem 0;"),
                cls="text-center"
            ),
            Table(
                Tr(
                    Td("Аккаунт:", style="font-weight: 500; padding: 0.5rem;"),
                    Td(f"@{status.telegram_username}" if status.telegram_username else "—",
                       style="padding: 0.5rem;")
                ),
                Tr(
                    Td("Telegram ID:", style="font-weight: 500; padding: 0.5rem;"),
                    Td(Code(str(status.telegram_id)) if status.telegram_id else "—",
                       style="padding: 0.5rem;")
                ),
                Tr(
                    Td("Привязан:", style="font-weight: 500; padding: 0.5rem;"),
                    Td(status.verified_at[:10] if status.verified_at else "—",
                       style="padding: 0.5rem;")
                ),
                style="width: 100%; margin: 1rem 0;"
            ),
            P("🔔 Вы будете получать уведомления о задачах и согласованиях в Telegram.",
              style="color: #166534; background: #dcfce7; padding: 0.75rem; border-radius: 8px; margin-top: 1rem;"),
            Form(
                Button("🔓 Отвязать Telegram", type="submit", name="action", value="unlink",
                       style="background: #dc2626; color: white; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer;"),
                P("Внимание: после отвязки вы перестанете получать уведомления.",
                  style="color: #666; font-size: 0.875rem; margin-top: 0.5rem;"),
                method="post",
                action="/settings/telegram",
                style="margin-top: 1.5rem; text-align: center;"
            ),
            cls="card",
            style="padding: 1.5rem; max-width: 400px; margin: 0 auto;"
        )
    elif status.verification_code:
        # Has pending verification code
        status_card = Div(
            Div(
                Span("⏳", style="font-size: 2rem;"),
                H3("Ожидание верификации", style="margin: 0.5rem 0;"),
                cls="text-center"
            ),
            Div(
                P("Ваш код верификации:", style="margin-bottom: 0.5rem; color: #666;"),
                Div(
                    Code(status.verification_code,
                         style="font-size: 2rem; letter-spacing: 0.3rem; padding: 0.75rem 1.5rem; background: #f3f4f6; border-radius: 8px; display: inline-block;"),
                    style="text-align: center; margin: 1rem 0;"
                ),
                P(f"Код действителен до: {status.code_expires_at[:16].replace('T', ' ')}" if status.code_expires_at else "",
                  style="color: #666; font-size: 0.875rem; text-align: center;"),
                style="margin: 1rem 0;"
            ),
            Div(
                H4("📱 Как привязать:", style="margin-bottom: 0.5rem;"),
                Ol(
                    Li("Откройте Telegram и найдите бота"),
                    Li("Отправьте боту команду /start"),
                    Li(f"Введите код: {status.verification_code}"),
                    style="padding-left: 1.25rem; line-height: 1.8;"
                ),
                style="background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-top: 1rem;"
            ),
            Form(
                Button("🔄 Получить новый код", type="submit", name="action", value="new_code",
                       style="background: #3b82f6; color: white; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer;"),
                method="post",
                action="/settings/telegram",
                style="margin-top: 1rem; text-align: center;"
            ),
            cls="card",
            style="padding: 1.5rem; max-width: 400px; margin: 0 auto;"
        )
    else:
        # Not linked, show button to get code
        status_card = Div(
            Div(
                Span("📱", style="font-size: 2rem;"),
                H3("Telegram не привязан", style="margin: 0.5rem 0;"),
                cls="text-center"
            ),
            P("Привяжите Telegram-аккаунт, чтобы получать уведомления о:",
              style="margin: 1rem 0;"),
            Ul(
                Li("🔔 Новых задачах на проверку"),
                Li("✅ Согласованиях коммерческих предложений"),
                Li("📋 Изменениях статуса заявок"),
                Li("⚠️ Возвратах на доработку"),
                style="list-style: none; padding: 0; line-height: 1.8;"
            ),
            Form(
                Button("📲 Получить код привязки", type="submit", name="action", value="new_code",
                       style="background: #3b82f6; color: white; padding: 0.75rem 1.5rem; border-radius: 6px; cursor: pointer; font-size: 1rem;"),
                method="post",
                action="/settings/telegram",
                style="margin-top: 1.5rem; text-align: center;"
            ),
            cls="card",
            style="padding: 1.5rem; max-width: 400px; margin: 0 auto;"
        )

    return page_layout("Настройки Telegram",
        Div(
            A("← Настройки", href="/settings", style="color: #3b82f6;"),
            H1("🔗 Привязка Telegram", style="margin: 1rem 0;"),
            P("Получайте уведомления и согласовывайте КП прямо в Telegram",
              style="color: #666; margin-bottom: 2rem;"),
            status_card,
            style="max-width: 600px; margin: 0 auto;"
        ),
        session=session
    )


@rt("/settings/telegram")
def post(action: str, session):
    """Handle Telegram settings form submissions.

    Actions:
    - new_code: Generate a new verification code
    - unlink: Remove the Telegram link
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    if action == "new_code":
        # Request a new verification code
        code = request_verification_code(user["id"])
        if code:
            return page_layout("Код создан",
                Div(
                    Div(
                        Span("✅", style="font-size: 3rem;"),
                        H2("Код верификации создан!", style="margin: 1rem 0;"),
                        cls="text-center"
                    ),
                    Div(
                        Code(code,
                             style="font-size: 2.5rem; letter-spacing: 0.4rem; padding: 1rem 2rem; background: #dcfce7; border-radius: 8px; display: inline-block; color: #166534;"),
                        style="text-align: center; margin: 1.5rem 0;"
                    ),
                    P("Код действителен 30 минут.",
                      style="color: #666; text-align: center;"),
                    Div(
                        H4("📱 Следующие шаги:", style="margin-bottom: 0.5rem;"),
                        Ol(
                            Li("Откройте Telegram"),
                            Li("Найдите нашего бота"),
                            Li(f"Отправьте команду: /start {code}"),
                            Li("Готово! Аккаунт будет привязан автоматически."),
                            style="padding-left: 1.25rem; line-height: 1.8;"
                        ),
                        style="background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-top: 1.5rem;"
                    ),
                    A("← Назад к настройкам Telegram", href="/settings/telegram",
                      style="display: block; text-align: center; margin-top: 1.5rem; color: #3b82f6;"),
                    cls="card",
                    style="padding: 2rem; max-width: 450px; margin: 0 auto;"
                ),
                session=session
            )
        else:
            # Already verified or error
            status = get_user_telegram_status(user["id"])
            if status.is_verified:
                return page_layout("Уже привязан",
                    Div(
                        Span("ℹ️", style="font-size: 2rem;"),
                        H2("Telegram уже привязан", style="margin: 0.5rem 0;"),
                        P("Ваш аккаунт уже связан с Telegram. Если хотите привязать другой аккаунт, сначала отвяжите текущий.",
                          style="color: #666;"),
                        A("← Назад к настройкам Telegram", href="/settings/telegram",
                          style="display: inline-block; margin-top: 1rem; color: #3b82f6;"),
                        cls="card text-center",
                        style="padding: 2rem; max-width: 400px; margin: 0 auto;"
                    ),
                    session=session
                )
            else:
                return page_layout("Ошибка",
                    Div(
                        Div("❌ Не удалось создать код верификации. Попробуйте позже.",
                            cls="alert alert-error"),
                        A("← Назад", href="/settings/telegram",
                          style="display: inline-block; margin-top: 1rem; color: #3b82f6;"),
                    ),
                    session=session
                )

    elif action == "unlink":
        # Unlink Telegram account
        success = unlink_telegram_account(user["id"])
        if success:
            return page_layout("Telegram отвязан",
                Div(
                    Div(
                        Span("✅", style="font-size: 2rem;"),
                        H2("Telegram успешно отвязан", style="margin: 0.5rem 0;"),
                        P("Вы больше не будете получать уведомления в Telegram. Вы можете привязать аккаунт снова в любое время.",
                          style="color: #666;"),
                        A("← Назад к настройкам Telegram", href="/settings/telegram",
                          style="display: inline-block; margin-top: 1rem; color: #3b82f6;"),
                        cls="card text-center",
                        style="padding: 2rem; max-width: 400px; margin: 0 auto;"
                    ),
                ),
                session=session
            )
        else:
            return page_layout("Ошибка",
                Div(
                    Div("❌ Не удалось отвязать Telegram. Попробуйте позже.",
                        cls="alert alert-error"),
                    A("← Назад", href="/settings/telegram",
                      style="display: inline-block; margin-top: 1rem; color: #3b82f6;"),
                ),
                session=session
            )

    # Unknown action - redirect back
    return RedirectResponse("/settings/telegram", status_code=303)


# ============================================================================
# PROCUREMENT WORKSPACE (Feature #33)
# ============================================================================

def workflow_status_badge(status_str: str):
    """
    Create a styled badge for workflow status.
    Uses workflow service colors and names.
    """
    try:
        status = WorkflowStatus(status_str) if status_str else None
    except ValueError:
        status = None

    if status:
        name = STATUS_NAMES_SHORT.get(status, status_str)
        # Convert Tailwind classes to inline styles for non-Tailwind environment
        color_map = {
            WorkflowStatus.DRAFT: ("#f3f4f6", "#1f2937"),
            WorkflowStatus.PENDING_PROCUREMENT: ("#fef3c7", "#92400e"),
            WorkflowStatus.PENDING_LOGISTICS: ("#dbeafe", "#1e40af"),
            WorkflowStatus.PENDING_CUSTOMS: ("#e9d5ff", "#6b21a8"),
            WorkflowStatus.PENDING_SALES_REVIEW: ("#ffedd5", "#9a3412"),
            WorkflowStatus.PENDING_QUOTE_CONTROL: ("#fce7f3", "#9d174d"),
            WorkflowStatus.PENDING_APPROVAL: ("#fef3c7", "#b45309"),
            WorkflowStatus.APPROVED: ("#dcfce7", "#166534"),
            WorkflowStatus.SENT_TO_CLIENT: ("#cffafe", "#0e7490"),
            WorkflowStatus.CLIENT_NEGOTIATION: ("#ccfbf1", "#115e59"),
            WorkflowStatus.PENDING_SPEC_CONTROL: ("#e0e7ff", "#3730a3"),
            WorkflowStatus.PENDING_SIGNATURE: ("#ede9fe", "#5b21b6"),
            WorkflowStatus.DEAL: ("#d1fae5", "#065f46"),
            WorkflowStatus.REJECTED: ("#fee2e2", "#991b1b"),
            WorkflowStatus.CANCELLED: ("#f5f5f4", "#57534e"),
        }
        bg, text = color_map.get(status, ("#f3f4f6", "#1f2937"))
        return Span(name, style=f"display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.875rem; background: {bg}; color: {text};")

    return Span(status_str or "—", cls="status-badge")


def workflow_progress_bar(status_str: str):
    """
    Create a visual workflow progress bar showing the current stage of a quote.

    Feature #87: Прогресс-бар workflow на КП

    Shows workflow stages as a horizontal bar with steps:
    1. Черновик (draft)
    2. Закупки (procurement)
    3. Лог + Там (logistics + customs parallel)
    4. Продажи (sales review)
    5. Контроль (quote control)
    6. Согласование (approval)
    7. Клиент (sent/negotiation)
    8. Спецификация (spec control)
    9. Сделка (deal)

    For rejected/cancelled shows a different indicator.
    """
    try:
        status = WorkflowStatus(status_str) if status_str else None
    except ValueError:
        status = None

    if not status:
        return Div()

    # Handle final negative states separately
    if status == WorkflowStatus.REJECTED:
        return Div(
            Span("❌ Отклонено", style="color: #dc2626; font-weight: 600;"),
            style="padding: 0.75rem 1rem; background: #fef2f2; border-radius: 8px; border-left: 4px solid #dc2626; margin: 0.5rem 0;"
        )
    if status == WorkflowStatus.CANCELLED:
        return Div(
            Span("⊘ Отменено", style="color: #57534e; font-weight: 600;"),
            style="padding: 0.75rem 1rem; background: #f5f5f4; border-radius: 8px; border-left: 4px solid #78716c; margin: 0.5rem 0;"
        )

    # Define workflow stages in order (main path)
    # Some stages are parallel (logistics + customs) - we show them as one combined step
    stages = [
        ("draft", "Черновик", [WorkflowStatus.DRAFT]),
        ("procurement", "Закупки", [WorkflowStatus.PENDING_PROCUREMENT]),
        ("logistics_customs", "Лог+Там", [WorkflowStatus.PENDING_LOGISTICS, WorkflowStatus.PENDING_CUSTOMS]),
        ("sales", "Продажи", [WorkflowStatus.PENDING_SALES_REVIEW]),
        ("control", "Контроль", [WorkflowStatus.PENDING_QUOTE_CONTROL]),
        ("approval", "Согласование", [WorkflowStatus.PENDING_APPROVAL, WorkflowStatus.APPROVED]),
        ("client", "Клиент", [WorkflowStatus.SENT_TO_CLIENT, WorkflowStatus.CLIENT_NEGOTIATION]),
        ("spec", "Спец-я", [WorkflowStatus.PENDING_SPEC_CONTROL, WorkflowStatus.PENDING_SIGNATURE]),
        ("deal", "Сделка", [WorkflowStatus.DEAL]),
    ]

    # Find current stage index
    current_stage_idx = -1
    for idx, (stage_id, name, statuses) in enumerate(stages):
        if status in statuses:
            current_stage_idx = idx
            break

    # Build progress bar
    steps = []
    for idx, (stage_id, name, statuses) in enumerate(stages):
        is_current = status in statuses
        is_completed = idx < current_stage_idx
        is_future = idx > current_stage_idx

        # Determine step styling
        if is_completed:
            # Completed step - green
            circle_style = "background: #22c55e; color: white; border: 2px solid #22c55e;"
            text_style = "color: #22c55e; font-weight: 500;"
            icon = "✓"
        elif is_current:
            # Current step - blue with pulse animation
            circle_style = "background: #3b82f6; color: white; border: 2px solid #3b82f6; animation: pulse 2s infinite;"
            text_style = "color: #3b82f6; font-weight: 600;"
            icon = str(idx + 1)
        else:
            # Future step - gray
            circle_style = "background: #e5e7eb; color: #9ca3af; border: 2px solid #e5e7eb;"
            text_style = "color: #9ca3af;"
            icon = str(idx + 1)

        # Connector line (not for first step)
        connector = None
        if idx > 0:
            line_color = "#22c55e" if is_completed or is_current else "#e5e7eb"
            connector = Div(
                style=f"flex: 1; height: 2px; background: {line_color}; margin: 0 -2px;"
            )

        step = Div(
            # Circle with number or checkmark
            Div(
                icon,
                style=f"width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; {circle_style}"
            ),
            # Label
            Div(name, style=f"font-size: 11px; margin-top: 4px; text-align: center; white-space: nowrap; {text_style}"),
            style="display: flex; flex-direction: column; align-items: center; min-width: 50px;"
        )

        if connector:
            steps.append(Div(connector, style="display: flex; align-items: center; flex: 1; padding-bottom: 20px;"))
        steps.append(step)

    # CSS for pulse animation
    pulse_animation = Style("""
        @keyframes pulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
            50% { transform: scale(1.05); box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
        }
    """)

    return Div(
        pulse_animation,
        Div(
            *steps,
            style="display: flex; align-items: flex-start; justify-content: space-between; width: 100%; padding: 0.5rem 0;"
        ),
        style="background: #f9fafb; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; overflow-x: auto;"
    )


def workflow_transition_history(quote_id: str, limit: int = 20, collapsed: bool = True):
    """
    Create a UI component showing the workflow transition history for a quote.

    Feature #88: Просмотр истории переходов

    Shows an audit log of all status changes with:
    - From/to status (with colored badges)
    - Who made the transition (actor)
    - When it happened
    - Any comments/reasons

    Args:
        quote_id: UUID of the quote
        limit: Max number of transitions to show (default 20)
        collapsed: If True, history is collapsed by default with toggle button

    Returns:
        FastHTML Div component with transition history
    """
    from datetime import datetime

    # Get transition history
    history = get_quote_transition_history(quote_id, limit=limit)

    if not history:
        if collapsed:
            return Div()  # Don't show anything if no history and collapsed mode
        return Div(
            H4("📋 История переходов", style="margin: 0 0 0.5rem;"),
            P("История переходов пуста", style="color: #666; font-size: 0.875rem;"),
            cls="card",
            style="background: #f9fafb;"
        )

    # Format timestamp
    def format_date(date_str):
        if not date_str:
            return "—"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return date_str[:16] if date_str else "—"

    # Build transition rows
    def transition_row(record, is_first=False):
        from_status = record.get("from_status", "—")
        to_status = record.get("to_status", "—")
        from_name = record.get("from_status_name", from_status)
        to_name = record.get("to_status_name", to_status)
        comment = record.get("comment", "")
        actor_role = record.get("actor_role", "")
        created_at = format_date(record.get("created_at"))

        # Get colors for status badges
        def get_badge_colors(status_str):
            try:
                status = WorkflowStatus(status_str) if status_str else None
            except ValueError:
                status = None

            color_map = {
                WorkflowStatus.DRAFT: ("#f3f4f6", "#1f2937"),
                WorkflowStatus.PENDING_PROCUREMENT: ("#fef3c7", "#92400e"),
                WorkflowStatus.PENDING_LOGISTICS: ("#dbeafe", "#1e40af"),
                WorkflowStatus.PENDING_CUSTOMS: ("#e9d5ff", "#6b21a8"),
                WorkflowStatus.PENDING_SALES_REVIEW: ("#ffedd5", "#9a3412"),
                WorkflowStatus.PENDING_QUOTE_CONTROL: ("#fce7f3", "#9d174d"),
                WorkflowStatus.PENDING_APPROVAL: ("#fef3c7", "#b45309"),
                WorkflowStatus.APPROVED: ("#dcfce7", "#166534"),
                WorkflowStatus.SENT_TO_CLIENT: ("#cffafe", "#0e7490"),
                WorkflowStatus.CLIENT_NEGOTIATION: ("#ccfbf1", "#115e59"),
                WorkflowStatus.PENDING_SPEC_CONTROL: ("#e0e7ff", "#3730a3"),
                WorkflowStatus.PENDING_SIGNATURE: ("#ede9fe", "#5b21b6"),
                WorkflowStatus.DEAL: ("#d1fae5", "#065f46"),
                WorkflowStatus.REJECTED: ("#fee2e2", "#991b1b"),
                WorkflowStatus.CANCELLED: ("#f5f5f4", "#57534e"),
            }
            if status:
                return color_map.get(status, ("#f3f4f6", "#1f2937"))
            return ("#f3f4f6", "#1f2937")

        from_bg, from_text = get_badge_colors(from_status)
        to_bg, to_text = get_badge_colors(to_status)

        # Role name translation
        role_names = {
            "sales": "Продажи",
            "procurement": "Закупки",
            "logistics": "Логистика",
            "customs": "Таможня",
            "quote_controller": "Контролёр КП",
            "spec_controller": "Контролёр спец.",
            "finance": "Финансы",
            "top_manager": "Руководство",
            "admin": "Админ",
            "system": "Система",
        }
        role_display = role_names.get(actor_role, actor_role) if actor_role else "—"

        return Div(
            # Timeline dot and line
            Div(
                # Dot
                Div(
                    style=f"width: 10px; height: 10px; border-radius: 50%; background: {'#3b82f6' if is_first else '#cbd5e1'}; margin-top: 5px;"
                ),
                # Line (except for last item)
                Div(style="width: 2px; flex: 1; background: #e5e7eb; margin-left: 4px;"),
                style="display: flex; flex-direction: column; align-items: center; margin-right: 12px;"
            ),
            # Content
            Div(
                # Header: timestamp and role
                Div(
                    Span(created_at, style="font-size: 0.75rem; color: #666;"),
                    Span(f" • {role_display}", style="font-size: 0.75rem; color: #9ca3af;") if role_display != "—" else None,
                    style="margin-bottom: 4px;"
                ),
                # Status transition
                Div(
                    Span(from_name, style=f"display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: {from_bg}; color: {from_text};"),
                    Span(" → ", style="margin: 0 6px; color: #9ca3af;"),
                    Span(to_name, style=f"display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: {to_bg}; color: {to_text};"),
                    style="margin-bottom: 4px;"
                ),
                # Comment if exists
                Div(
                    Span(f"💬 {comment}", style="font-size: 0.8rem; color: #4b5563; font-style: italic;"),
                    style="margin-top: 4px;"
                ) if comment else None,
                style="flex: 1; padding-bottom: 12px;"
            ),
            style="display: flex; align-items: stretch;"
        )

    # Build history list
    history_items = [transition_row(record, idx == 0) for idx, record in enumerate(history)]

    # Container ID for toggle functionality
    container_id = f"transition-history-{quote_id[:8]}"

    if collapsed:
        # Collapsible version with toggle button
        return Div(
            # Toggle button
            Div(
                Button(
                    f"📋 История переходов ({len(history)})",
                    type="button",
                    cls="secondary",
                    style="font-size: 0.875rem; padding: 0.5rem 1rem;",
                    onclick=f"document.getElementById('{container_id}').classList.toggle('hidden');"
                ),
                style="margin-bottom: 0.5rem;"
            ),
            # Hidden history container
            Div(
                *history_items,
                id=container_id,
                cls="hidden",  # Hidden by default
                style="padding: 0.75rem; background: #fafafa; border-radius: 8px; border: 1px solid #e5e7eb;"
            ),
            # CSS for hidden class
            Style("""
                .hidden { display: none; }
            """),
            style="margin: 0.5rem 0;"
        )
    else:
        # Always visible version
        return Div(
            H4("📋 История переходов", style="margin: 0 0 0.75rem;"),
            Div(
                *history_items,
                style="padding: 0.75rem; background: #fafafa; border-radius: 8px; border: 1px solid #e5e7eb;"
            ),
            cls="card",
            style="background: #f9fafb;"
        )


@rt("/procurement")
def get(session, status_filter: str = None):
    """
    Procurement workspace - shows quotes with items having brands assigned to current user.

    Feature #33: Basic procurement page structure
    Feature #34: Filtered list with my brands, status filter, and item details
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has procurement role
    if not user_has_any_role(session, ["procurement", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get brands assigned to this user
    my_brands = get_assigned_brands(user_id, org_id)
    my_brands_lower = [b.lower() for b in my_brands]  # For case-insensitive matching

    # Get quotes that have items with brands assigned to this user
    # Enhanced: Also get item details for each quote

    quotes_with_details = []

    if my_brands:
        # Query quote_items with my brands - get more details
        items_result = supabase.table("quote_items") \
            .select("id, quote_id, brand, procurement_status, quantity, product_name") \
            .execute()

        # Filter items for my brands (case-insensitive)
        my_items = [item for item in (items_result.data or [])
                    if (item.get("brand") or "").lower() in my_brands_lower]

        # Group items by quote_id
        items_by_quote = {}
        for item in my_items:
            qid = item["quote_id"]
            if qid not in items_by_quote:
                items_by_quote[qid] = []
            items_by_quote[qid].append(item)

        quote_ids_with_my_brands = list(items_by_quote.keys())

        if quote_ids_with_my_brands:
            # Get full quote data for those quotes
            quotes_result = supabase.table("quotes") \
                .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at") \
                .eq("organization_id", org_id) \
                .in_("id", quote_ids_with_my_brands) \
                .order("created_at", desc=True) \
                .execute()

            # Enrich quotes with item details
            for q in (quotes_result.data or []):
                q_items = items_by_quote.get(q["id"], [])
                # Calculate item stats
                total_items = len(q_items)
                completed_items = len([i for i in q_items if i.get("procurement_status") == "completed"])
                pending_items = total_items - completed_items
                # Get unique brands in this quote from my assignments
                brands_in_quote = list(set([i.get("brand", "") for i in q_items]))

                quotes_with_details.append({
                    **q,
                    "my_items": q_items,
                    "my_items_total": total_items,
                    "my_items_completed": completed_items,
                    "my_items_pending": pending_items,
                    "my_brands_in_quote": brands_in_quote
                })

    # Apply status filter if provided
    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    # Separate quotes by workflow status for default view
    pending_quotes = [q for q in quotes_with_details
                      if q.get("workflow_status") == "pending_procurement"]
    other_quotes = [q for q in quotes_with_details
                    if q.get("workflow_status") != "pending_procurement"]

    # Count stats
    all_quotes_count = len(quotes_with_details)
    pending_count = len(pending_quotes)
    in_progress_count = len([q for q in quotes_with_details
                             if q.get("workflow_status") in ["pending_logistics", "pending_customs", "pending_sales_review"]])
    completed_count = len([q for q in quotes_with_details
                           if q.get("workflow_status") in ["approved", "deal", "sent_to_client"]])

    # Build the table rows with enhanced item details
    def quote_row(q, show_work_button=True):
        customer_name = "—"
        if q.get("customers"):
            customer_name = q["customers"].get("name", "—")

        workflow_status = q.get("workflow_status") or q.get("status", "draft")

        # Item progress display
        my_total = q.get("my_items_total", 0)
        my_completed = q.get("my_items_completed", 0)
        brands_list = q.get("my_brands_in_quote", [])

        # Progress bar for items
        progress_pct = int((my_completed / my_total * 100) if my_total > 0 else 0)
        progress_bar = Div(
            Div(style=f"width: {progress_pct}%; height: 100%; background: #22c55e;"),
            style="width: 60px; height: 8px; background: #e5e7eb; border-radius: 4px; display: inline-block; margin-right: 0.5rem; overflow: hidden;",
            title=f"{my_completed}/{my_total} позиций оценено"
        )

        items_info = Span(
            progress_bar,
            f"{my_completed}/{my_total}",
            style="font-size: 0.875rem; color: #666;"
        )

        # Brands display (truncate if many)
        brands_display = ", ".join(brands_list[:3])
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
            Td(q.get("created_at", "")[:10] if q.get("created_at") else "—"),
            Td(
                A("Открыть", href=f"/procurement/{q['id']}", role="button",
                  style="font-size: 0.875rem; padding: 0.25rem 0.75rem;")
                if show_work_button and workflow_status == "pending_procurement" else
                A("Просмотр", href=f"/quotes/{q['id']}", style="font-size: 0.875rem;")
            )
        )

    # Status filter options for procurement perspective
    status_options = [
        ("all", "Все статусы"),
        ("pending_procurement", "🔶 Ожидают оценки"),
        ("pending_logistics", "📦 На логистике"),
        ("pending_customs", "🛃 На таможне"),
        ("pending_sales_review", "👤 У менеджера продаж"),
        ("pending_quote_control", "✓ На проверке"),
        ("approved", "✅ Одобрено"),
        ("deal", "💼 Сделка"),
    ]

    # Status filter form
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
        method="get",
        action="/procurement",
        style="margin-bottom: 1rem;"
    )

    return page_layout("Procurement Workspace",
        # Header
        Div(
            H1("Закупки"),
            P(f"Рабочая зона менеджера по закупкам"),
            style="margin-bottom: 1rem;"
        ),

        # My assigned brands
        Div(
            H3("Мои бренды"),
            P(", ".join(my_brands) if my_brands else "Нет назначенных брендов. Обратитесь к администратору."),
            cls="card"
        ) if True else None,

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
                Div("В работе"),
                cls="card stat-card"
            ),
            Div(
                Div(str(len(my_brands)), cls="stat-value"),
                Div("Моих брендов"),
                cls="card stat-card"
            ),
            Div(
                Div(str(all_quotes_count), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Status filter
        Div(filter_form, cls="card") if not status_filter or status_filter == "all" else filter_form,

        # Show filtered view if filter is active
        Div(
            H2(f"КП: {dict(status_options).get(status_filter, status_filter)}"),
            P(f"Найдено: {len(quotes_with_details)} КП", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП # / Бренды"), Th("Клиент"), Th("Статус"), Th("Мои позиции"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q, show_work_button=True) for q in quotes_with_details]
                ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="7", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if status_filter and status_filter != "all" else None,

        # Default view: Pending quotes (requiring my attention) - only when no filter
        Div(
            H2("🔶 Ожидают оценки"),
            P("КП на этапе закупок с моими брендами — требуется моя работа", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП # / Бренды"), Th("Клиент"), Th("Статус"), Th("Мои позиции"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q) for q in pending_quotes]
                ) if pending_quotes else Tbody(Tr(Td("Нет КП на оценке", colspan="7", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if not status_filter or status_filter == "all" else None,

        # Other quotes with my brands - only when no filter
        Div(
            H2("📋 Другие КП с моими брендами"),
            P("КП на других этапах workflow", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП # / Бренды"), Th("Клиент"), Th("Статус"), Th("Мои позиции"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q, show_work_button=False) for q in other_quotes]
                ) if other_quotes else Tbody(Tr(Td("Нет других КП", colspan="7", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if (not status_filter or status_filter == "all") and other_quotes else None,

        session=session
    )


# ============================================================================
# PROCUREMENT DETAIL PAGE (Feature #35)
# ============================================================================

@rt("/procurement/{quote_id}")
def get(quote_id: str, session):
    """
    Procurement detail page - form for entering procurement data for items.

    Feature #35: Форма ввода закупочных данных
    - Shows items belonging to user's assigned brands
    - Allows editing: price, supplier country/city, weight, production time,
      payer company, advance %, payment terms
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has procurement role
    if not user_has_any_role(session, ["procurement", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .execute()

    quote = quote_result.data
    if not quote:
        return page_layout("Not Found",
            Div(
                H1("КП не найдено"),
                P("КП не существует или у вас нет доступа."),
                A("Назад к списку", href="/procurement", role="button"),
                cls="card"
            ),
            session=session
        )

    # Get user's assigned brands
    my_brands = get_assigned_brands(user_id, org_id)
    my_brands_lower = [b.lower() for b in my_brands]

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    all_items = items_result.data or []

    # Filter items for my brands
    my_items = [item for item in all_items
                if item.get("brand", "").lower() in my_brands_lower]

    # Calculate progress for MY items
    total_items = len(my_items)
    completed_items = len([i for i in my_items if i.get("procurement_status") == "completed"])
    my_items_complete = (completed_items == total_items) and total_items > 0

    # Calculate progress for ALL items (Feature #37: overall procurement status)
    overall_total = len(all_items)
    overall_completed = len([i for i in all_items if i.get("procurement_status") == "completed"])
    all_procurement_complete = (overall_completed == overall_total) and overall_total > 0

    customer_name = quote.get("customers", {}).get("name", "—") if quote.get("customers") else "—"
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is in the right status for editing
    can_edit = workflow_status in ["pending_procurement", "draft"]

    # Build item rows for the form
    def item_row(item, index):
        item_id = item["id"]
        brand = item.get("brand", "—")
        name = item.get("name", "")
        product_code = item.get("product_code", "")
        quantity = item.get("quantity", 1)
        is_completed = item.get("procurement_status") == "completed"

        # Current values
        base_price = item.get("base_price_vat", "")
        weight = item.get("weight_in_kg", "")
        supplier_country = item.get("supplier_country", "")
        supplier_city = item.get("supplier_city", "")
        production_time = item.get("production_time_days", "")
        payer_company = item.get("payer_company", "")
        advance_percent = item.get("advance_to_supplier_percent", 100)
        payment_terms = item.get("supplier_payment_terms", "")
        notes = item.get("procurement_notes", "")

        # Status badge
        status_style = "background: #dcfce7; color: #166534;" if is_completed else "background: #fef3c7; color: #92400e;"
        status_text = "✓ Оценено" if is_completed else "⏳ Ожидает"

        return Div(
            # Item header with status
            Div(
                Div(
                    Span(brand, style="font-weight: 600; font-size: 1.1rem;"),
                    Span(f" / {product_code}" if product_code else "", style="color: #666;"),
                    style="flex: 1;"
                ),
                Span(status_text, style=f"display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; {status_style}"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;"
            ),

            # Product info (read-only)
            Div(
                Div(f"Наименование: {name}", style="flex: 1;") if name else None,
                Div(f"Количество: {quantity} шт.", style="font-weight: 500;"),
                style="display: flex; gap: 1rem; margin-bottom: 1rem; font-size: 0.875rem; color: #666;"
            ) if name else None,

            # Editable fields in grid
            Div(
                # Row 1: Price, Weight, Country, City
                Label("Цена за ед. (с НДС) *",
                    Input(name=f"base_price_vat_{item_id}", type="number", step="0.01", min="0",
                          value=str(base_price) if base_price else "",
                          placeholder="1500.00", required=True if can_edit else False,
                          disabled=not can_edit),
                    style="flex: 1;"
                ),
                Label("Вес, кг",
                    Input(name=f"weight_in_kg_{item_id}", type="number", step="0.001", min="0",
                          value=str(weight) if weight else "",
                          placeholder="0.5",
                          disabled=not can_edit),
                    style="flex: 1;"
                ),
                Label("Страна поставщика",
                    Select(
                        Option("— Выберите —", value=""),
                        Option("Китай", value="Китай", selected=(supplier_country == "Китай")),
                        Option("Турция", value="Турция", selected=(supplier_country == "Турция")),
                        Option("Россия", value="Россия", selected=(supplier_country == "Россия")),
                        Option("Германия", value="Германия", selected=(supplier_country == "Германия")),
                        Option("Италия", value="Италия", selected=(supplier_country == "Италия")),
                        Option("Корея", value="Корея", selected=(supplier_country == "Корея")),
                        Option("Тайвань", value="Тайвань", selected=(supplier_country == "Тайвань")),
                        Option("Индия", value="Индия", selected=(supplier_country == "Индия")),
                        Option("США", value="США", selected=(supplier_country == "США")),
                        Option("Другое", value="other", selected=(supplier_country and supplier_country not in ["Китай", "Турция", "Россия", "Германия", "Италия", "Корея", "Тайвань", "Индия", "США"])),
                        name=f"supplier_country_{item_id}",
                        disabled=not can_edit
                    ),
                    style="flex: 1;"
                ),
                Label("Город поставщика",
                    Input(name=f"supplier_city_{item_id}", type="text",
                          value=supplier_city or "",
                          placeholder="Шанхай",
                          disabled=not can_edit),
                    style="flex: 1;"
                ),
                style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1rem;"
            ),

            # Row 2: Production time, Payer company, Advance %, Payment terms
            Div(
                Label("Срок пр-ва, дней",
                    Input(name=f"production_time_days_{item_id}", type="number", min="0",
                          value=str(production_time) if production_time else "",
                          placeholder="30",
                          disabled=not can_edit),
                    style="flex: 1;"
                ),
                Label("Компания-плательщик",
                    Select(
                        Option("— Выберите —", value=""),
                        Option("ООО Квота", value="ООО Квота", selected=(payer_company == "ООО Квота")),
                        Option("ООО Квота Групп", value="ООО Квота Групп", selected=(payer_company == "ООО Квота Групп")),
                        Option("ИП Иванов", value="ИП Иванов", selected=(payer_company == "ИП Иванов")),
                        name=f"payer_company_{item_id}",
                        disabled=not can_edit
                    ),
                    style="flex: 1;"
                ),
                Label("Аванс поставщику, %",
                    Input(name=f"advance_to_supplier_percent_{item_id}", type="number", min="0", max="100",
                          value=str(advance_percent) if advance_percent is not None else "100",
                          placeholder="100",
                          disabled=not can_edit),
                    style="flex: 1;"
                ),
                Label("Условия оплаты поставщику",
                    Input(name=f"supplier_payment_terms_{item_id}", type="text",
                          value=payment_terms or "",
                          placeholder="30% аванс, 70% до отгрузки",
                          disabled=not can_edit),
                    style="flex: 1;"
                ),
                style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1rem;"
            ),

            # Notes field
            Label("Примечания",
                Textarea(notes or "", name=f"procurement_notes_{item_id}",
                         placeholder="Дополнительная информация о позиции...",
                         style="width: 100%; min-height: 60px;",
                         disabled=not can_edit)
            ),

            # Hidden field for item ID
            Input(type="hidden", name=f"item_id_{index}", value=item_id),

            cls="card",
            style=f"border-left: 4px solid {'#22c55e' if is_completed else '#f59e0b'}; margin-bottom: 1rem;",
            id=f"item-{item_id}"
        )

    # Build the page
    return page_layout(f"Закупки — {quote.get('idn_quote', 'КП')}",
        # Breadcrumbs
        Div(
            A("← Назад к списку", href="/procurement"),
            style="margin-bottom: 1rem;"
        ),

        # Header
        Div(
            H1(f"Оценка КП: {quote.get('idn_quote', f'#{quote_id[:8]}')}"),
            Div(
                Span(f"Клиент: {customer_name}", style="margin-right: 1.5rem;"),
                workflow_status_badge(workflow_status),
            ),
            style="margin-bottom: 1rem;"
        ),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(workflow_status),

        # Progress card with export button
        Div(
            Div(
                H3("Мой прогресс", style="margin: 0;"),
                A("📥 Скачать Excel", href=f"/procurement/{quote_id}/export", role="button",
                  cls="secondary", style="font-size: 0.875rem;") if total_items > 0 else None,
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;"
            ),
            Div(
                Div(f"{completed_items}/{total_items} позиций", style="margin-bottom: 0.5rem;"),
                Div(
                    Div(style=f"width: {(completed_items/total_items*100) if total_items > 0 else 0}%; height: 100%; background: #22c55e;"),
                    style="width: 100%; height: 12px; background: #e5e7eb; border-radius: 9999px; overflow: hidden;"
                ),
            ),
            # Show success when all MY items are complete
            Div(
                P("✅ Вы завершили оценку своих позиций!", style="color: #166534; margin: 0.5rem 0 0;"),
                style="padding: 0.5rem; background: #dcfce7; border-radius: 0.5rem; margin-top: 0.75rem;"
            ) if my_items_complete else None,
            cls="card"
        ),

        # Overall procurement status (Feature #37)
        Div(
            H4("Общий статус закупок", style="margin: 0 0 0.5rem;"),
            Div(
                Div(f"{overall_completed}/{overall_total} позиций оценено всеми менеджерами", style="margin-bottom: 0.5rem; font-size: 0.875rem;"),
                Div(
                    Div(style=f"width: {(overall_completed/overall_total*100) if overall_total > 0 else 0}%; height: 8px; background: #3b82f6;"),
                    style="width: 100%; height: 8px; background: #e5e7eb; border-radius: 9999px; overflow: hidden;"
                ),
            ),
            # Show status message
            Div(
                P("✅ Все закупки оценены! КП перешло на следующий этап.", style="color: #166534; margin: 0;") if all_procurement_complete and workflow_status != "pending_procurement" else
                P("⏳ Ожидается оценка от других менеджеров по закупкам.", style="color: #92400e; margin: 0;") if my_items_complete and not all_procurement_complete else None,
                style=f"padding: 0.5rem; background: {'#dcfce7' if all_procurement_complete and workflow_status != 'pending_procurement' else '#fef3c7'}; border-radius: 0.5rem; margin-top: 0.5rem;"
            ) if (my_items_complete and not all_procurement_complete) or (all_procurement_complete and workflow_status != "pending_procurement") else None,
            cls="card",
            style="background: #f8fafc; border: 1px dashed #cbd5e1;"
        ) if overall_total > total_items else None,  # Only show if there are other brands

        # Warning if not in correct status
        Div(
            P(f"⚠️ КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}». "
              "Редактирование недоступно.", style="color: #b45309; margin: 0;"),
            cls="card",
            style="background: #fffbeb;"
        ) if not can_edit else None,

        # Form with items
        Form(
            # Hidden field with quote_id
            Input(type="hidden", name="quote_id", value=quote_id),
            Input(type="hidden", name="item_count", value=str(len(my_items))),

            # Items section
            Div(
                H2(f"Мои позиции ({len(my_items)})"),
                P("Заполните данные для каждой позиции:", style="color: #666; margin-bottom: 1rem;") if can_edit else None,
                *[item_row(item, idx) for idx, item in enumerate(my_items)],
            ) if my_items else Div(
                P("Нет позиций с вашими брендами в этом КП.", style="color: #666;"),
                cls="card"
            ),

            # Action buttons (Feature #37: Smart completion button)
            Div(
                Button("💾 Сохранить данные", type="submit", name="action", value="save",
                       style="margin-right: 1rem;") if can_edit and not my_items_complete else None,
                Button("✓ Завершить оценку", type="submit", name="action", value="complete",
                       style="background: #16a34a;") if can_edit and total_items > 0 and not my_items_complete else None,
                # Show a disabled "already complete" button when user's items are done
                Button("✓ Моя оценка завершена", disabled=True,
                       style="background: #6b7280; cursor: default;") if can_edit and my_items_complete else None,
                A("← Назад к списку", href="/procurement", role="button", cls="secondary",
                  style="margin-left: auto;"),
                style="display: flex; align-items: center; margin-top: 1rem;"
            ),

            method="post",
            action=f"/procurement/{quote_id}"
        ),

        # Transition history (Feature #88)
        workflow_transition_history(quote_id),

        session=session
    )


@rt("/procurement/{quote_id}")
async def post(quote_id: str, session, request):
    """
    Save procurement data for quote items.

    Feature #35: Handler for saving procurement form data
    - Saves all procurement fields for each item
    - Can mark items as complete
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has procurement role
    if not user_has_any_role(session, ["procurement", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Get form data
    form_data = await request.form()
    action = form_data.get("action", "save")

    supabase = get_supabase()

    # Verify quote exists and is accessible
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .execute()

    quote = quote_result.data
    if not quote:
        return RedirectResponse("/procurement", status_code=303)

    # Check workflow status allows editing
    workflow_status = quote.get("workflow_status", "draft")
    if workflow_status not in ["pending_procurement", "draft"]:
        return RedirectResponse(f"/procurement/{quote_id}", status_code=303)

    # Get user's assigned brands to filter items
    my_brands = get_assigned_brands(user_id, org_id)
    my_brands_lower = [b.lower() for b in my_brands]

    # Get items count from form
    item_count = int(form_data.get("item_count", 0))

    # Process each item from the form
    updated_items = 0
    for idx in range(item_count):
        item_id = form_data.get(f"item_id_{idx}")
        if not item_id:
            continue

        # Verify this item belongs to user's brands
        item_result = supabase.table("quote_items") \
            .select("id, brand") \
            .eq("id", item_id) \
            .eq("quote_id", quote_id) \
            .single() \
            .execute()

        item = item_result.data
        if not item or (item.get("brand") or "").lower() not in my_brands_lower:
            continue

        # Build update data
        update_data = {}

        # Get values from form (using item_id suffix)
        base_price = form_data.get(f"base_price_vat_{item_id}")
        if base_price:
            update_data["base_price_vat"] = float(base_price)

        weight = form_data.get(f"weight_in_kg_{item_id}")
        if weight:
            update_data["weight_in_kg"] = float(weight)

        supplier_country = form_data.get(f"supplier_country_{item_id}")
        if supplier_country:
            update_data["supplier_country"] = supplier_country

        supplier_city = form_data.get(f"supplier_city_{item_id}")
        update_data["supplier_city"] = supplier_city or None

        production_time = form_data.get(f"production_time_days_{item_id}")
        if production_time:
            update_data["production_time_days"] = int(production_time)

        payer_company = form_data.get(f"payer_company_{item_id}")
        update_data["payer_company"] = payer_company or None

        advance_percent = form_data.get(f"advance_to_supplier_percent_{item_id}")
        if advance_percent:
            update_data["advance_to_supplier_percent"] = float(advance_percent)

        payment_terms = form_data.get(f"supplier_payment_terms_{item_id}")
        update_data["supplier_payment_terms"] = payment_terms or None

        notes = form_data.get(f"procurement_notes_{item_id}")
        update_data["procurement_notes"] = notes or None

        # If completing, mark procurement status
        if action == "complete":
            update_data["procurement_status"] = "completed"
            update_data["procurement_completed_at"] = datetime.utcnow().isoformat()
            update_data["procurement_completed_by"] = user_id

        # Update the item
        if update_data:
            supabase.table("quote_items") \
                .update(update_data) \
                .eq("id", item_id) \
                .execute()
            updated_items += 1

    # Feature #37: If completing, check if ALL procurement is done and trigger workflow transition
    if action == "complete" and updated_items > 0:
        # Get user's roles for the workflow transition
        user_roles = get_user_roles_from_session(session)

        # Try to complete procurement and transition to next status
        completion_result = complete_procurement(
            quote_id=quote_id,
            actor_id=user_id,
            actor_roles=user_roles
        )

        # Note: Even if not all items are complete (other users' brands still pending),
        # the user's items are saved. The workflow transition only happens when ALL
        # items across ALL brands are complete.

        # If transition was successful, show success message (via redirect)
        # If not (other items still pending), user sees updated progress on the page

    # Redirect back to the procurement detail page
    return RedirectResponse(f"/procurement/{quote_id}", status_code=303)


# ============================================================================
# PROCUREMENT EXCEL EXPORT (Feature #36)
# ============================================================================

@rt("/procurement/{quote_id}/export")
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
    if not user_has_any_role(session, ["procurement", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .execute()

    quote = quote_result.data
    if not quote:
        return RedirectResponse("/procurement", status_code=303)

    customer_name = quote.get("customers", {}).get("name", "") if quote.get("customers") else ""

    # Get user's assigned brands
    my_brands = get_assigned_brands(user_id, org_id)
    my_brands_lower = [b.lower() for b in my_brands]

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    all_items = items_result.data or []

    # Filter items for my brands
    my_items = [item for item in all_items
                if item.get("brand", "").lower() in my_brands_lower]

    if not my_items:
        # No items to export, redirect back with message
        return RedirectResponse(f"/procurement/{quote_id}", status_code=303)

    # Generate Excel
    excel_bytes = create_procurement_excel(
        quote=quote,
        items=my_items,
        brands=my_brands,
        customer_name=customer_name
    )

    # Return as file download
    from starlette.responses import Response
    quote_number = quote.get("idn_quote", quote_id[:8])
    filename = f"procurement_request_{quote_number}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================================
# LOGISTICS WORKSPACE (Feature #38)
# ============================================================================

@rt("/logistics")
def get(session, status_filter: str = None):
    """
    Logistics workspace - shows quotes in logistics stage for logist role.

    Feature #38: Basic logistics page structure
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has logistics role
    if not user_has_any_role(session, ["logistics", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get quotes for this organization
    # Logistics sees quotes in pending_logistics or pending_customs (parallel) or pending_sales_review (after)
    quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at, logistics_completed_at, customs_completed_at, assigned_logistics_user") \
        .eq("organization_id", org_id) \
        .order("created_at", desc=True) \
        .execute()

    all_quotes = quotes_result.data or []

    # Filter to quotes that are relevant to logistics
    logistics_statuses = [
        "pending_logistics",
        "pending_customs",  # Can work in parallel
        "pending_sales_review",  # Already done, for reference
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

    # Apply status filter if provided
    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    # Separate quotes by status
    pending_quotes = [q for q in quotes_with_details
                      if q.get("workflow_status") in ["pending_logistics", "pending_customs"]
                      and not q.get("logistics_done")]
    completed_quotes = [q for q in quotes_with_details
                        if q.get("logistics_done")]

    # Count stats
    all_count = len(quotes_with_details)
    pending_count = len(pending_quotes)
    completed_count = len(completed_quotes)

    # Build the table rows
    def quote_row(q, show_work_button=True):
        customer_name = "—"
        if q.get("customers"):
            customer_name = q["customers"].get("name", "—")

        workflow_status = q.get("workflow_status") or q.get("status", "draft")
        logistics_done = q.get("logistics_done", False)
        customs_done = q.get("customs_done", False)

        # Parallel stage progress indicator
        stages_status = []
        if logistics_done:
            stages_status.append(Span("✅ Логистика", style="color: #22c55e; margin-right: 0.5rem;"))
        else:
            stages_status.append(Span("⏳ Логистика", style="color: #f59e0b; margin-right: 0.5rem;"))

        if customs_done:
            stages_status.append(Span("✅ Таможня", style="color: #22c55e;"))
        else:
            stages_status.append(Span("⏳ Таможня", style="color: #f59e0b;"))

        return Tr(
            Td(
                A(q.get("idn_quote", f"#{q['id'][:8]}"), href=f"/quotes/{q['id']}", style="font-weight: 500;"),
            ),
            Td(customer_name),
            Td(workflow_status_badge(workflow_status)),
            Td(*stages_status),
            Td(format_money(q.get("total_amount"))),
            Td(q.get("created_at", "")[:10] if q.get("created_at") else "—"),
            Td(
                A("Работать", href=f"/logistics/{q['id']}", role="button",
                  style="font-size: 0.875rem; padding: 0.25rem 0.75rem;")
                if show_work_button and not logistics_done and workflow_status in ["pending_logistics", "pending_customs"] else
                A("Просмотр", href=f"/logistics/{q['id']}", style="font-size: 0.875rem;")
            )
        )

    # Status filter options
    status_options = [
        ("all", "Все статусы"),
        ("pending_logistics", "📦 На логистике"),
        ("pending_customs", "🛃 На таможне (параллельно)"),
        ("pending_sales_review", "👤 У менеджера продаж"),
    ]

    # Status filter form
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
        method="get",
        action="/logistics",
        style="margin-bottom: 1rem;"
    )

    return page_layout("Logistics Workspace",
        # Header
        Div(
            H1("Логистика"),
            P(f"Рабочая зона логиста"),
            style="margin-bottom: 1rem;"
        ),

        # Stats
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
                Div(str(all_count), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Status filter
        Div(filter_form, cls="card") if not status_filter or status_filter == "all" else filter_form,

        # Show filtered view if filter is active
        Div(
            H2(f"КП: {dict(status_options).get(status_filter, status_filter)}"),
            P(f"Найдено: {len(quotes_with_details)} КП", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Параллельные этапы"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q) for q in quotes_with_details]
                ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="7", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if status_filter and status_filter != "all" else None,

        # Default view: Pending quotes
        Div(
            H2("📦 Ожидают логистики"),
            P("КП требующие расчёта логистики", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Параллельные этапы"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q) for q in pending_quotes]
                ) if pending_quotes else Tbody(Tr(Td("Нет КП на логистике", colspan="7", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if not status_filter or status_filter == "all" else None,

        # Completed quotes
        Div(
            H2("✅ Завершённые"),
            P("КП с завершённой логистикой", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Параллельные этапы"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q, show_work_button=False) for q in completed_quotes[:10]]
                ) if completed_quotes else Tbody(Tr(Td("Нет завершённых КП", colspan="7", style="text-align: center; color: #666;")))
            ),
            P(f"Показано 10 из {len(completed_quotes)}", style="color: #888; font-size: 0.875rem; margin-top: 0.5rem;") if len(completed_quotes) > 10 else None,
            cls="card"
        ) if not status_filter or status_filter == "all" else None,

        session=session
    )


# ============================================================================
# LOGISTICS DETAIL PAGE
# ============================================================================

@rt("/logistics/{quote_id}")
def get(session, quote_id: str):
    """
    Logistics detail page - view and edit logistics data for a quote.

    Feature #40: Logistics data entry form
    - Shows quote summary and items
    - Editable fields for logistics costs and delivery time
    - Only editable when quote is in pending_logistics or pending_customs status
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has logistics role
    if not user_has_any_role(session, ["logistics", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("Quote Not Found"),
            P("The requested quote was not found or you don't have access."),
            A("← Back to Logistics", href="/logistics"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    customer_name = quote.get("customers", {}).get("name", "Unknown")

    # Load existing calculation variables (where logistics data is stored)
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    saved_vars = vars_result.data[0]["variables"] if vars_result.data else {}

    def get_var(key, default):
        return saved_vars.get(key, default)

    # Fetch quote items for summary
    items_result = supabase.table("quote_items") \
        .select("id, brand, product_code, product_name, quantity, unit, base_price_vat, weight_in_kg, supplier_country") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    # Check if logistics is editable
    editable_statuses = ["pending_logistics", "pending_customs", "draft", "pending_procurement"]
    is_editable = workflow_status in editable_statuses and quote.get("logistics_completed_at") is None
    logistics_done = quote.get("logistics_completed_at") is not None

    # Calculate summary stats
    total_items = len(items)
    total_weight = sum(float(item.get("weight_in_kg", 0) or 0) for item in items)
    unique_countries = set(item.get("supplier_country", "Unknown") for item in items)

    # Build items summary table
    items_summary = Table(
        Thead(Tr(
            Th("Бренд"),
            Th("Артикул"),
            Th("Наименование"),
            Th("Кол-во"),
            Th("Вес (кг)"),
            Th("Страна")
        )),
        Tbody(
            *[Tr(
                Td(item.get("brand", "—")),
                Td(item.get("product_code", "—")),
                Td(item.get("product_name", "—")[:40] + "..." if len(item.get("product_name", "") or "") > 40 else item.get("product_name", "—")),
                Td(str(item.get("quantity", 0))),
                Td(str(item.get("weight_in_kg", "—"))),
                Td(item.get("supplier_country", "—"))
            ) for item in items[:20]]  # Show first 20 items
        ),
        style="width: 100%; font-size: 0.875rem;"
    )

    # Form for logistics data
    logistics_form = Form(
        # Logistics cost fields
        Div(
            H3("📦 Стоимость логистики"),
            P("Введите стоимость доставки по сегментам (в валюте КП)", style="color: #666; margin-bottom: 1rem;"),
            Div(
                Div(
                    Label("От поставщика до хаба",
                        Input(
                            name="logistics_supplier_hub",
                            type="number",
                            value=str(get_var('logistics_supplier_hub', 0)),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style="width: 100%;"
                        ),
                        style="display: block;"
                    ),
                    style="flex: 1;"
                ),
                Div(
                    Label("От хаба до таможни",
                        Input(
                            name="logistics_hub_customs",
                            type="number",
                            value=str(get_var('logistics_hub_customs', 0)),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style="width: 100%;"
                        ),
                        style="display: block;"
                    ),
                    style="flex: 1;"
                ),
                Div(
                    Label("От таможни до клиента",
                        Input(
                            name="logistics_customs_client",
                            type="number",
                            value=str(get_var('logistics_customs_client', 0)),
                            min="0",
                            step="0.01",
                            disabled=not is_editable,
                            style="width: 100%;"
                        ),
                        style="display: block;"
                    ),
                    style="flex: 1;"
                ),
                style="display: flex; gap: 1rem;"
            ),
            cls="card"
        ),

        # Delivery time
        Div(
            H3("📅 Сроки доставки"),
            Div(
                Div(
                    Label("Срок доставки (дней)",
                        Input(
                            name="delivery_time",
                            type="number",
                            value=str(get_var('delivery_time', 30)),
                            min="1",
                            max="365",
                            disabled=not is_editable,
                            style="width: 100%;"
                        ),
                        style="display: block;"
                    ),
                    style="flex: 1; max-width: 200px;"
                ),
                Div(
                    Label("Примечания логиста",
                        Textarea(
                            str(get_var('logistics_notes', '')),
                            name="logistics_notes",
                            rows="3",
                            disabled=not is_editable,
                            style="width: 100%;"
                        ),
                        style="display: block;"
                    ),
                    style="flex: 2;"
                ),
                style="display: flex; gap: 1rem; align-items: start;"
            ),
            cls="card"
        ),

        # Action buttons
        Div(
            Button("💾 Сохранить данные", type="submit", name="action", value="save",
                   style="margin-right: 0.5rem;") if is_editable else None,
            Button("✅ Завершить логистику", type="submit", name="action", value="complete",
                   cls="btn-success", style="background-color: #22c55e;") if is_editable else None,
            Span("✅ Логистика завершена", style="color: #22c55e; font-weight: bold;") if logistics_done else None,
            style="margin-top: 1rem;"
        ) if is_editable or logistics_done else None,

        method="post",
        action=f"/logistics/{quote_id}"
    )

    # Status banner
    status_banner = Div(
        P(f"⚠️ Данный КП в статусе '{STATUS_NAMES.get(workflow_status, workflow_status)}' — редактирование логистики недоступно.",
          style="margin: 0;"),
        style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if not is_editable and not logistics_done else None

    success_banner = Div(
        P(f"✅ Логистика по данному КП завершена.",
          style="margin: 0;"),
        style="background-color: #dcfce7; border: 1px solid #22c55e; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if logistics_done else None

    return page_layout(f"Logistics - {quote.get('idn_quote', '')}",
        # Header
        Div(
            A("← К списку", href="/logistics", style="color: #666; font-size: 0.875rem;"),
            H1(f"Логистика: {quote.get('idn_quote', '')}"),
            Div(
                Span(f"Клиент: {customer_name}", style="margin-right: 1rem;"),
                workflow_status_badge(workflow_status),
                style="display: flex; align-items: center; gap: 0.5rem;"
            ),
            style="margin-bottom: 1rem;"
        ),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(workflow_status),

        # Status banners
        success_banner,
        status_banner,

        # Quote summary
        Div(
            H3("📋 Сводка по КП"),
            Div(
                Div(
                    Div(str(total_items), cls="stat-value"),
                    Div("Позиций"),
                    cls="stat-card-mini"
                ),
                Div(
                    Div(f"{total_weight:.1f}", cls="stat-value"),
                    Div("Общий вес (кг)"),
                    cls="stat-card-mini"
                ),
                Div(
                    Div(str(len(unique_countries)), cls="stat-value"),
                    Div("Стран отправки"),
                    cls="stat-card-mini"
                ),
                style="display: flex; gap: 1rem; margin-bottom: 1rem;"
            ),
            Details(
                Summary("Показать позиции", style="cursor: pointer; color: #3b82f6;"),
                items_summary,
                style="margin-top: 0.5rem;"
            ) if items else P("Нет позиций в КП", style="color: #666;"),
            cls="card"
        ),

        # Logistics form
        logistics_form,

        # Additional styles
        Style("""
            .stat-card-mini {
                background: #f9fafb;
                padding: 0.75rem 1rem;
                border-radius: 4px;
                text-align: center;
            }
            .stat-card-mini .stat-value {
                font-size: 1.5rem;
                font-weight: bold;
                color: #1f2937;
            }
        """),

        # Transition history (Feature #88)
        workflow_transition_history(quote_id),

        session=session
    )


@rt("/logistics/{quote_id}")
def post(session, quote_id: str,
         logistics_supplier_hub: str = "0",
         logistics_hub_customs: str = "0",
         logistics_customs_client: str = "0",
         delivery_time: str = "30",
         logistics_notes: str = "",
         action: str = "save"):
    """
    Save logistics data and optionally mark logistics as complete.

    Feature #40: Logistics data entry form (POST handler)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role
    if not user_has_any_role(session, ["logistics", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify quote exists and belongs to org
    quote_result = supabase.table("quotes") \
        .select("id, workflow_status, logistics_completed_at") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return RedirectResponse("/logistics", status_code=303)

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if editable
    editable_statuses = ["pending_logistics", "pending_customs", "draft", "pending_procurement"]
    if workflow_status not in editable_statuses or quote.get("logistics_completed_at"):
        return RedirectResponse(f"/logistics/{quote_id}", status_code=303)

    # Load existing variables
    vars_result = supabase.table("quote_calculation_variables") \
        .select("id, variables") \
        .eq("quote_id", quote_id) \
        .execute()

    existing_vars = vars_result.data[0]["variables"] if vars_result.data else {}
    vars_id = vars_result.data[0]["id"] if vars_result.data else None

    # Helper function
    def safe_decimal(val, default="0"):
        try:
            return float(val) if val else float(default)
        except:
            return float(default)

    def safe_int(val, default=30):
        try:
            return int(val) if val else default
        except:
            return default

    # Update logistics fields in variables
    updated_vars = {
        **existing_vars,
        'logistics_supplier_hub': safe_decimal(logistics_supplier_hub),
        'logistics_hub_customs': safe_decimal(logistics_hub_customs),
        'logistics_customs_client': safe_decimal(logistics_customs_client),
        'delivery_time': safe_int(delivery_time),
        'logistics_notes': logistics_notes
    }

    # Upsert variables
    if vars_id:
        supabase.table("quote_calculation_variables") \
            .update({"variables": updated_vars}) \
            .eq("id", vars_id) \
            .execute()
    else:
        supabase.table("quote_calculation_variables") \
            .insert({
                "quote_id": quote_id,
                "variables": updated_vars
            }) \
            .execute()

    # If action is complete, mark logistics as done
    if action == "complete":
        user_roles = get_user_roles_from_session(session)
        result = complete_logistics(quote_id, user_id, user_roles)

        if not result.success:
            # Log error but still redirect
            print(f"Error completing logistics: {result.error}")

    return RedirectResponse(f"/logistics/{quote_id}", status_code=303)


# ============================================================================
# CUSTOMS WORKSPACE (Feature #42)
# ============================================================================

@rt("/customs")
def get(session, status_filter: str = None):
    """
    Customs workspace - shows quotes in customs stage for customs role.

    Feature #42: Basic customs page structure
    Feature #43: List quotes at customs stage (included)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has customs role
    if not user_has_any_role(session, ["customs", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get quotes for this organization
    # Customs sees quotes in pending_customs or pending_logistics (parallel) or pending_sales_review (after)
    quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at, logistics_completed_at, customs_completed_at, assigned_customs_user") \
        .eq("organization_id", org_id) \
        .order("created_at", desc=True) \
        .execute()

    all_quotes = quotes_result.data or []

    # Filter to quotes that are relevant to customs
    customs_statuses = [
        "pending_customs",
        "pending_logistics",  # Can work in parallel
        "pending_sales_review",  # Already done, for reference
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

    # Apply status filter if provided
    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    # Separate quotes by status
    pending_quotes = [q for q in quotes_with_details
                      if q.get("workflow_status") in ["pending_customs", "pending_logistics"]
                      and not q.get("customs_done")]
    completed_quotes = [q for q in quotes_with_details
                        if q.get("customs_done")]

    # Count stats
    all_count = len(quotes_with_details)
    pending_count = len(pending_quotes)
    completed_count = len(completed_quotes)

    # Build the table rows
    def quote_row(q, show_work_button=True):
        customer_name = "—"
        if q.get("customers"):
            customer_name = q["customers"].get("name", "—")

        workflow_status = q.get("workflow_status") or q.get("status", "draft")
        logistics_done = q.get("logistics_done", False)
        customs_done = q.get("customs_done", False)

        # Parallel stage progress indicator
        stages_status = []
        if logistics_done:
            stages_status.append(Span("✅ Логистика", style="color: #22c55e; margin-right: 0.5rem;"))
        else:
            stages_status.append(Span("⏳ Логистика", style="color: #f59e0b; margin-right: 0.5rem;"))

        if customs_done:
            stages_status.append(Span("✅ Таможня", style="color: #22c55e;"))
        else:
            stages_status.append(Span("⏳ Таможня", style="color: #f59e0b;"))

        return Tr(
            Td(
                A(q.get("idn_quote", f"#{q['id'][:8]}"), href=f"/quotes/{q['id']}", style="font-weight: 500;"),
            ),
            Td(customer_name),
            Td(workflow_status_badge(workflow_status)),
            Td(*stages_status),
            Td(format_money(q.get("total_amount"))),
            Td(q.get("created_at", "")[:10] if q.get("created_at") else "—"),
            Td(
                A("Работать", href=f"/customs/{q['id']}", role="button",
                  style="font-size: 0.875rem; padding: 0.25rem 0.75rem;")
                if show_work_button and not customs_done and workflow_status in ["pending_customs", "pending_logistics"] else
                A("Просмотр", href=f"/customs/{q['id']}", style="font-size: 0.875rem;")
            )
        )

    # Status filter options
    status_options = [
        ("all", "Все статусы"),
        ("pending_customs", "🛃 На таможне"),
        ("pending_logistics", "📦 На логистике (параллельно)"),
        ("pending_sales_review", "👤 У менеджера продаж"),
    ]

    # Status filter form
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
        method="get",
        action="/customs",
        style="margin-bottom: 1rem;"
    )

    return page_layout("Customs Workspace",
        # Header
        Div(
            H1("🛃 Таможня"),
            P(f"Рабочая зона менеджера ТО (Олег Князев)"),
            style="margin-bottom: 1rem;"
        ),

        # Stats
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
                Div(str(all_count), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Status filter
        Div(filter_form, cls="card") if not status_filter or status_filter == "all" else filter_form,

        # Show filtered view if filter is active
        Div(
            H2(f"КП: {dict(status_options).get(status_filter, status_filter)}"),
            P(f"Найдено: {len(quotes_with_details)} КП", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Параллельные этапы"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q) for q in quotes_with_details]
                ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="7", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if status_filter and status_filter != "all" else None,

        # Default view: Pending quotes
        Div(
            H2("🛃 Ожидают таможни"),
            P("КП требующие таможенного оформления", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Параллельные этапы"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q) for q in pending_quotes]
                ) if pending_quotes else Tbody(Tr(Td("Нет КП на таможне", colspan="7", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if not status_filter or status_filter == "all" else None,

        # Completed quotes
        Div(
            H2("✅ Завершённые"),
            P("КП с завершённой таможней", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Параллельные этапы"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q, show_work_button=False) for q in completed_quotes[:10]]
                ) if completed_quotes else Tbody(Tr(Td("Нет завершённых КП", colspan="7", style="text-align: center; color: #666;")))
            ),
            P(f"Показано 10 из {len(completed_quotes)}", style="color: #888; font-size: 0.875rem; margin-top: 0.5rem;") if len(completed_quotes) > 10 else None,
            cls="card"
        ) if not status_filter or status_filter == "all" else None,

        session=session
    )


# ============================================================================
# CUSTOMS DETAIL PAGE (Feature #44, #45)
# ============================================================================

@rt("/customs/{quote_id}")
def get(session, quote_id: str):
    """
    Customs detail page - view and edit customs data for each item in a quote.

    Feature #44: Customs data entry form
    - Shows quote summary and all items
    - Editable fields for HS codes (ТН ВЭД), duty, and extra charges
    - Only editable when quote is in pending_customs or pending_logistics status
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has customs role
    if not user_has_any_role(session, ["customs", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("Quote Not Found"),
            P("The requested quote was not found or you don't have access."),
            A("← Back to Customs", href="/customs"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    customer_name = quote.get("customers", {}).get("name", "Unknown")

    # Fetch quote items
    items_result = supabase.table("quote_items") \
        .select("id, brand, product_code, product_name, quantity, unit, base_price_vat, weight_in_kg, supplier_country, hs_code, customs_duty, customs_extra") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    items = items_result.data or []

    # Check if customs is editable
    editable_statuses = ["pending_customs", "pending_logistics", "draft", "pending_procurement"]
    is_editable = workflow_status in editable_statuses and quote.get("customs_completed_at") is None
    customs_done = quote.get("customs_completed_at") is not None

    # Calculate summary stats
    total_items = len(items)
    items_with_hs = sum(1 for item in items if item.get("hs_code"))
    total_duty = sum(float(item.get("customs_duty", 0) or 0) for item in items)
    total_extra = sum(float(item.get("customs_extra", 0) or 0) for item in items)

    # Build items form - each item has fields for HS code, duty, extra
    def item_row(item, index):
        item_id = item.get("id")
        return Tr(
            Td(str(index + 1)),
            Td(
                Div(item.get("brand", "—"), style="font-weight: 500;"),
                Div(item.get("product_code", ""), style="font-size: 0.75rem; color: #666;")
            ),
            Td((item.get("product_name", "") or "—")[:40] + "..." if len(item.get("product_name", "") or "") > 40 else (item.get("product_name", "") or "—")),
            Td(f"{item.get('quantity', 0)} {item.get('unit', 'шт')}"),
            Td(item.get("supplier_country", "—")),
            Td(
                Input(
                    name=f"hs_code_{item_id}",
                    type="text",
                    value=item.get("hs_code", ""),
                    placeholder="0000000000",
                    maxlength="20",
                    disabled=not is_editable,
                    style="width: 120px; font-size: 0.875rem;"
                )
            ),
            Td(
                Input(
                    name=f"customs_duty_{item_id}",
                    type="number",
                    value=str(item.get("customs_duty", 0) or 0),
                    min="0",
                    step="0.01",
                    disabled=not is_editable,
                    style="width: 80px; font-size: 0.875rem;"
                )
            ),
            Td(
                Input(
                    name=f"customs_extra_{item_id}",
                    type="number",
                    value=str(item.get("customs_extra", 0) or 0),
                    min="0",
                    step="0.01",
                    disabled=not is_editable,
                    style="width: 80px; font-size: 0.875rem;"
                )
            )
        )

    # Items table in a form
    items_form = Form(
        Table(
            Thead(Tr(
                Th("#"),
                Th("Бренд/Артикул"),
                Th("Наименование"),
                Th("Кол-во"),
                Th("Страна"),
                Th("Код ТН ВЭД"),
                Th("Пошлина %"),
                Th("Доп. расходы")
            )),
            Tbody(
                *[item_row(item, i) for i, item in enumerate(items)]
            ) if items else Tbody(Tr(Td("Нет позиций в КП", colspan="8", style="text-align: center; color: #666;"))),
            style="width: 100%; font-size: 0.875rem;"
        ),

        # Notes field
        Div(
            Label("Примечания таможенника",
                Textarea(
                    quote.get("customs_notes", ""),
                    name="customs_notes",
                    rows="3",
                    disabled=not is_editable,
                    style="width: 100%;"
                ),
                style="display: block; margin-top: 1rem;"
            ),
        ) if is_editable else None,

        # Action buttons
        Div(
            Button("💾 Сохранить данные", type="submit", name="action", value="save",
                   style="margin-right: 0.5rem;") if is_editable else None,
            Button("✅ Завершить таможню", type="submit", name="action", value="complete",
                   cls="btn-success", style="background-color: #22c55e;") if is_editable else None,
            Span("✅ Таможня завершена", style="color: #22c55e; font-weight: bold;") if customs_done else None,
            style="margin-top: 1rem;"
        ) if is_editable or customs_done else None,

        method="post",
        action=f"/customs/{quote_id}"
    )

    # Status banner
    status_banner = Div(
        P(f"⚠️ Данный КП в статусе '{STATUS_NAMES.get(workflow_status, workflow_status)}' — редактирование таможни недоступно.",
          style="margin: 0;"),
        style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if not is_editable and not customs_done else None

    success_banner = Div(
        P(f"✅ Таможня по данному КП завершена.",
          style="margin: 0;"),
        style="background-color: #dcfce7; border: 1px solid #22c55e; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem;"
    ) if customs_done else None

    # Progress indicator
    progress_percent = int(items_with_hs / total_items * 100) if total_items > 0 else 0

    return page_layout(f"Customs - {quote.get('idn_quote', '')}",
        # Header
        Div(
            A("← К списку", href="/customs", style="color: #666; font-size: 0.875rem;"),
            H1(f"🛃 Таможня: {quote.get('idn_quote', '')}"),
            Div(
                Span(f"Клиент: {customer_name}", style="margin-right: 1rem;"),
                workflow_status_badge(workflow_status),
                style="display: flex; align-items: center; gap: 0.5rem;"
            ),
            style="margin-bottom: 1rem;"
        ),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(workflow_status),

        # Status banners
        success_banner,
        status_banner,

        # Quote summary with customs stats
        Div(
            H3("📋 Сводка по КП"),
            Div(
                Div(
                    Div(str(total_items), cls="stat-value"),
                    Div("Позиций"),
                    cls="stat-card-mini"
                ),
                Div(
                    Div(f"{items_with_hs}/{total_items}", cls="stat-value"),
                    Div("Заполнено ТН ВЭД"),
                    cls="stat-card-mini"
                ),
                Div(
                    Div(f"{total_duty:.2f}%", cls="stat-value"),
                    Div("Сумма пошлин"),
                    cls="stat-card-mini"
                ),
                Div(
                    Div(format_money(total_extra) if total_extra else "0", cls="stat-value"),
                    Div("Доп. расходы"),
                    cls="stat-card-mini"
                ),
                style="display: flex; gap: 1rem; margin-bottom: 1rem;"
            ),
            # Progress bar
            Div(
                Div(
                    Div(style=f"width: {progress_percent}%; height: 100%; background-color: {'#22c55e' if progress_percent == 100 else '#3b82f6'};"),
                    style="background-color: #e5e7eb; height: 8px; border-radius: 4px; overflow: hidden;"
                ),
                P(f"Прогресс: {progress_percent}% ({items_with_hs} из {total_items} позиций)", style="margin-top: 0.25rem; font-size: 0.875rem; color: #666;"),
                style="margin-top: 0.5rem;"
            ),
            cls="card"
        ),

        # Instructions
        Div(
            H3("📝 Инструкция"),
            P("Заполните коды ТН ВЭД для каждой позиции, укажите процент пошлины и дополнительные расходы.", style="margin-bottom: 0;"),
            cls="card",
            style="background-color: #f0f9ff; border-left: 4px solid #3b82f6;"
        ) if is_editable else None,

        # Items form
        Div(
            H3("📦 Позиции"),
            items_form,
            cls="card"
        ),

        # Transition history (Feature #88)
        workflow_transition_history(quote_id),

        # Additional styles
        Style("""
            .stat-card-mini {
                background: #f9fafb;
                padding: 0.75rem 1rem;
                border-radius: 4px;
                text-align: center;
            }
            .stat-card-mini .stat-value {
                font-size: 1.5rem;
                font-weight: bold;
                color: #1f2937;
            }
        """),

        session=session
    )


@rt("/customs/{quote_id}")
async def post(session, quote_id: str, request):
    """
    Save customs data for all items and optionally mark customs as complete.

    Feature #44: Customs data entry form (POST handler)
    Feature #45: Complete customs button
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Get form data
    form_data = await request.form()
    action = form_data.get("action", "save")
    customs_notes = form_data.get("customs_notes", "")

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role
    if not user_has_any_role(session, ["customs", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify quote exists and belongs to org
    quote_result = supabase.table("quotes") \
        .select("id, workflow_status, customs_completed_at") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return RedirectResponse("/customs", status_code=303)

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if editable
    editable_statuses = ["pending_customs", "pending_logistics", "draft", "pending_procurement"]
    if workflow_status not in editable_statuses or quote.get("customs_completed_at"):
        return RedirectResponse(f"/customs/{quote_id}", status_code=303)

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    # Helper function for safe decimal conversion
    def safe_decimal(val, default=0):
        try:
            return float(val) if val else default
        except:
            return default

    # Update customs data for each item
    for item in items:
        item_id = item["id"]
        hs_code = form_data.get(f"hs_code_{item_id}", "")
        customs_duty = form_data.get(f"customs_duty_{item_id}", "0")
        customs_extra = form_data.get(f"customs_extra_{item_id}", "0")

        # Update item
        supabase.table("quote_items") \
            .update({
                "hs_code": hs_code if hs_code else None,
                "customs_duty": safe_decimal(customs_duty),
                "customs_extra": safe_decimal(customs_extra)
            }) \
            .eq("id", item_id) \
            .execute()

    # If action is complete, mark customs as done
    if action == "complete":
        user_roles = get_user_roles_from_session(session)
        result = complete_customs(quote_id, user_id, user_roles)

        if not result.success:
            # Log error but still redirect
            print(f"Error completing customs: {result.error}")

    return RedirectResponse(f"/customs/{quote_id}", status_code=303)


# ============================================================================
# QUOTE CONTROL WORKSPACE (Features #46-51)
# ============================================================================

@rt("/quote-control")
def get(session, status_filter: str = None):
    """
    Quote Control workspace - shows quotes pending review for quote_controller role (Жанна).

    Feature #46: Basic quote control page structure
    Feature #47: List quotes at pending_quote_control status (included)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get quotes for this organization
    # Quote controller sees quotes at pending_quote_control stage and can view history
    quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, created_at, deal_type, current_version_id") \
        .eq("organization_id", org_id) \
        .order("created_at", desc=True) \
        .execute()

    all_quotes = quotes_result.data or []

    # Statuses relevant to quote control
    control_statuses = [
        "pending_quote_control",  # Main work status
        "pending_approval",  # Sent for top manager approval
        "approved",  # Approved by controller or top manager
        "sent_to_client",  # Sent to client
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

    # Apply status filter if provided
    if status_filter and status_filter != "all":
        quotes_with_details = [q for q in quotes_with_details
                               if q.get("workflow_status") == status_filter]

    # Separate quotes by review status
    pending_quotes = [q for q in quotes_with_details
                      if q.get("needs_review")]
    awaiting_approval_quotes = [q for q in quotes_with_details
                                 if q.get("pending_approval")]
    approved_quotes = [q for q in quotes_with_details
                       if q.get("is_approved") or q.get("sent_to_client")]

    # Count stats
    all_count = len(quotes_with_details)
    pending_count = len(pending_quotes)
    awaiting_count = len(awaiting_approval_quotes)
    approved_count = len(approved_quotes)

    # Build the table rows
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
            Td(q.get("created_at", "")[:10] if q.get("created_at") else "—"),
            Td(
                A("Проверить", href=f"/quote-control/{q['id']}", role="button",
                  style="font-size: 0.875rem; padding: 0.25rem 0.75rem;")
                if show_work_button and q.get("needs_review") else
                A("Просмотр", href=f"/quote-control/{q['id']}", style="font-size: 0.875rem;")
            )
        )

    # Status filter options
    status_options = [
        ("all", "Все статусы"),
        ("pending_quote_control", "📋 На проверке"),
        ("pending_approval", "⏳ Ожидает согласования"),
        ("approved", "✅ Одобрено"),
        ("sent_to_client", "📤 Отправлено клиенту"),
    ]

    # Status filter form
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
        method="get",
        action="/quote-control",
        style="margin-bottom: 1rem;"
    )

    return page_layout("Quote Control Workspace",
        # Header
        Div(
            H1("📋 Контроль КП"),
            P("Рабочая зона контроллера КП (Жанна)"),
            style="margin-bottom: 1rem;"
        ),

        # Stats
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
                Div(str(all_count), cls="stat-value"),
                Div("Всего КП"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Status filter
        Div(filter_form, cls="card") if not status_filter or status_filter == "all" else filter_form,

        # Show filtered view if filter is active
        Div(
            H2(f"КП: {dict(status_options).get(status_filter, status_filter)}"),
            P(f"Найдено: {len(quotes_with_details)} КП", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q) for q in quotes_with_details]
                ) if quotes_with_details else Tbody(Tr(Td("Нет КП с этим статусом", colspan="6", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if status_filter and status_filter != "all" else None,

        # Default view: Pending review quotes
        Div(
            H2("📋 Ожидают проверки"),
            P("КП требующие проверки контроллера", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q) for q in pending_quotes]
                ) if pending_quotes else Tbody(Tr(Td("Нет КП на проверке", colspan="6", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if not status_filter or status_filter == "all" else None,

        # Awaiting approval quotes
        Div(
            H2("⏳ Ожидают согласования"),
            P("КП отправленные на согласование топ-менеджеру", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q, show_work_button=False) for q in awaiting_approval_quotes]
                ) if awaiting_approval_quotes else Tbody(Tr(Td("Нет КП на согласовании", colspan="6", style="text-align: center; color: #666;")))
            ),
            cls="card"
        ) if not status_filter or status_filter == "all" else None,

        # Approved/sent quotes
        Div(
            H2("✅ Одобренные"),
            P("КП одобренные и отправленные клиенту", style="color: #666; margin-bottom: 1rem;"),
            Table(
                Thead(Tr(Th("КП #"), Th("Клиент"), Th("Статус"), Th("Сумма"), Th("Создан"), Th("Действия"))),
                Tbody(
                    *[quote_row(q, show_work_button=False) for q in approved_quotes[:10]]
                ) if approved_quotes else Tbody(Tr(Td("Нет одобренных КП", colspan="6", style="text-align: center; color: #666;")))
            ),
            cls="card",
            style="margin-bottom: 2rem;"
        ) if not status_filter or status_filter == "all" else None,

        session=session
    )


# ============================================================================
# QUOTE CONTROL DETAIL VIEW (Feature #48)
# ============================================================================

@rt("/quote-control/{quote_id}")
def get(session, quote_id: str):
    """
    Quote Control detail view - shows checklist for reviewing a specific quote.

    Feature #48: Checklist for quote_controller (Жанна) to verify all aspects of the quote.

    Checklist items from spec:
    1. Тип сделки (поставка/транзит) - разная наценка
    2. Базис поставки (чаще DDP)
    3. Валюта КП, корректность конвертации
    4. Условия расчётов с клиентом
    5. Размер аванса поставщику
    6. Корректность закупочных цен, НДС
    7. Корректность логистики (не из головы)
    8. Минимальные наценки
    9. Вознаграждения ЛПРа
    10. % курсовой разницы
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← Вернуться к списку", href="/quote-control"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Get quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()
    items = items_result.data or []

    # Get calculation variables
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()
    calc_vars = vars_result.data[0]["variables"] if vars_result.data else {}

    # Get calculation summary
    summary_result = supabase.table("quote_calculation_summaries") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()
    summary = summary_result.data[0] if summary_result.data else {}

    # Determine if editing is allowed
    can_edit = workflow_status == "pending_quote_control"

    # Extract values for checklist verification
    deal_type = quote.get("deal_type") or calc_vars.get("offer_sale_type", "")
    incoterms = calc_vars.get("offer_incoterms", "")
    currency = quote.get("currency", "USD")
    markup = float(calc_vars.get("markup", 0) or 0)
    supplier_advance = float(calc_vars.get("supplier_advance", 0) or 0)
    exchange_rate = float(calc_vars.get("exchange_rate", 1.0) or 1.0)
    forex_risk = float(calc_vars.get("forex_risk_percent", 0) or 0)
    lpr_reward = float(calc_vars.get("lpr_reward", 0) or calc_vars.get("decision_maker_reward", 0) or 0)

    # Payment terms
    payment_terms = calc_vars.get("client_payment_terms", "")
    prepayment = float(calc_vars.get("client_prepayment_percent", 100) or 100)

    # Logistics costs
    logistics_supplier_hub = float(calc_vars.get("logistics_supplier_hub", 0) or 0)
    logistics_hub_customs = float(calc_vars.get("logistics_hub_customs", 0) or 0)
    logistics_customs_client = float(calc_vars.get("logistics_customs_client", 0) or 0)
    total_logistics = logistics_supplier_hub + logistics_hub_customs + logistics_customs_client

    # Min markup thresholds (these would typically come from settings)
    min_markup_supply = 12  # %
    min_markup_transit = 8   # %

    # Approval triggers (from spec):
    # - Валюта КП = рубли
    # - Условия не 100% предоплата
    # - Наценка ниже минимума
    # - Есть вознаграждение ЛПРа
    needs_approval_reasons = []
    if currency == "RUB":
        needs_approval_reasons.append("Валюта КП = рубли")
    if prepayment < 100:
        needs_approval_reasons.append(f"Не 100% предоплата ({prepayment}%)")
    if deal_type == "supply" and markup < min_markup_supply:
        needs_approval_reasons.append(f"Наценка ({markup}%) ниже минимума для поставки ({min_markup_supply}%)")
    elif deal_type == "transit" and markup < min_markup_transit:
        needs_approval_reasons.append(f"Наценка ({markup}%) ниже минимума для транзита ({min_markup_transit}%)")
    if lpr_reward > 0:
        needs_approval_reasons.append(f"Есть вознаграждение ЛПРа ({lpr_reward})")

    needs_approval = len(needs_approval_reasons) > 0

    # Build checklist items with auto-detected status
    def checklist_item(name, description, value, status="info", details=None):
        """Create a checklist item with status indicator."""
        status_colors = {
            "ok": ("#dcfce7", "#166534", "✓"),
            "warning": ("#fef3c7", "#92400e", "⚠"),
            "error": ("#fee2e2", "#991b1b", "✗"),
            "info": ("#dbeafe", "#1e40af", "ℹ"),
        }
        bg, text_color, icon = status_colors.get(status, status_colors["info"])

        return Div(
            Div(
                Span(icon, style=f"color: {text_color}; font-weight: bold; margin-right: 0.5rem;"),
                Strong(name),
                style="display: flex; align-items: center;"
            ),
            P(description, style="color: #666; font-size: 0.875rem; margin: 0.25rem 0;"),
            Div(
                Strong(str(value) if value else "—"),
                style=f"padding: 0.5rem; background: {bg}; border-radius: 4px; margin-top: 0.25rem;"
            ),
            P(details, style="color: #666; font-size: 0.75rem; margin-top: 0.25rem;") if details else None,
            style="padding: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 0.75rem;"
        )

    # Generate checklist
    checklist_items = []

    # 1. Deal type
    deal_type_display = "Поставка" if deal_type == "supply" else ("Транзит" if deal_type == "transit" else deal_type or "Не указан")
    deal_status = "ok" if deal_type else "warning"
    checklist_items.append(checklist_item(
        "1. Тип сделки",
        "Поставка или транзит - влияет на минимальную наценку",
        deal_type_display,
        deal_status,
        f"Мин. наценка: {min_markup_supply}% (поставка) / {min_markup_transit}% (транзит)"
    ))

    # 2. Incoterms
    incoterms_status = "ok" if incoterms else "warning"
    checklist_items.append(checklist_item(
        "2. Базис поставки (Incoterms)",
        "Обычно DDP. Влияет на распределение расходов и рисков",
        incoterms or "Не указан",
        incoterms_status,
        "DDP = все расходы до клиента включены в цену"
    ))

    # 3. Currency
    currency_status = "warning" if currency == "RUB" else "ok"
    checklist_items.append(checklist_item(
        "3. Валюта КП",
        "Проверить корректность конвертации. Рубли требуют согласования",
        currency,
        currency_status,
        f"Курс: {exchange_rate}" if exchange_rate != 1.0 else None
    ))

    # 4. Payment terms
    payment_display = f"{prepayment}% предоплата"
    if payment_terms:
        payment_display += f" ({payment_terms})"
    payment_status = "ok" if prepayment == 100 else "warning"
    checklist_items.append(checklist_item(
        "4. Условия расчётов с клиентом",
        "Не 100% предоплата требует согласования",
        payment_display,
        payment_status,
        "100% предоплата = минимальный риск" if prepayment == 100 else "Отсрочка = требует согласования"
    ))

    # 5. Supplier advance
    supplier_advance_display = f"{supplier_advance}%"
    advance_status = "ok" if supplier_advance <= 50 else "warning"
    checklist_items.append(checklist_item(
        "5. Размер аванса поставщику",
        "Проверить соответствие договорённостям с поставщиком",
        supplier_advance_display,
        advance_status,
        "Стандарт: 30-50% аванс"
    ))

    # 6. Purchase prices
    total_purchase = sum(float(item.get("purchase_price", 0) or 0) * int(item.get("quantity", 1) or 1) for item in items)
    vat_rate = float(calc_vars.get("vat_rate", 20) or 20)
    checklist_items.append(checklist_item(
        "6. Закупочные цены и НДС",
        "Проверить корректность закупочных цен",
        f"Итого закупка: {format_money(total_purchase)} | НДС: {vat_rate}%",
        "info",
        f"Позиций с ценами: {len([i for i in items if i.get('purchase_price')])}/{len(items)}"
    ))

    # 7. Logistics
    logistics_status = "ok" if total_logistics > 0 else "warning"
    checklist_items.append(checklist_item(
        "7. Корректность логистики",
        "Стоимость должна быть рассчитана, не 'из головы'",
        f"Поставщик→Хаб: {format_money(logistics_supplier_hub)} | Хаб→Таможня: {format_money(logistics_hub_customs)} | Таможня→Клиент: {format_money(logistics_customs_client)}",
        logistics_status,
        f"Итого логистика: {format_money(total_logistics)}"
    ))

    # 8. Minimum markup
    min_markup = min_markup_supply if deal_type == "supply" else min_markup_transit
    markup_status = "ok" if markup >= min_markup else "error"
    checklist_items.append(checklist_item(
        "8. Минимальные наценки",
        f"Минимум: {min_markup}% для {'поставки' if deal_type == 'supply' else 'транзита'}",
        f"{markup}%",
        markup_status,
        "Наценка в норме" if markup >= min_markup else f"⚠ Ниже минимума на {min_markup - markup}%"
    ))

    # 9. LPR reward
    lpr_status = "warning" if lpr_reward > 0 else "ok"
    checklist_items.append(checklist_item(
        "9. Вознаграждение ЛПРа",
        "Наличие вознаграждения требует согласования",
        f"{lpr_reward}" if lpr_reward else "Нет",
        lpr_status,
        "Требует согласования топ-менеджера" if lpr_reward > 0 else None
    ))

    # 10. Forex risk
    forex_status = "ok" if forex_risk > 0 else "info"
    checklist_items.append(checklist_item(
        "10. % курсовой разницы",
        "Заложен ли риск изменения курса валют",
        f"{forex_risk}%" if forex_risk else "Не учтён",
        forex_status,
        "Рекомендуется 2-5% при длительных сроках поставки"
    ))

    # Summary info
    customer_name = quote.get("customers", {}).get("name", "—")
    quote_total = float(quote.get("total_amount", 0) or 0)

    # Status banner
    if workflow_status == "pending_quote_control":
        status_banner = Div(
            "📋 Требуется проверка",
            style="background: #fef3c7; color: #92400e; padding: 1rem; border-radius: 8px; text-align: center; font-weight: 500; margin-bottom: 1rem;"
        )
    elif workflow_status == "pending_approval":
        status_banner = Div(
            "⏳ Ожидает согласования топ-менеджера",
            style="background: #dbeafe; color: #1e40af; padding: 1rem; border-radius: 8px; text-align: center; font-weight: 500; margin-bottom: 1rem;"
        )
    elif workflow_status == "approved":
        status_banner = Div(
            "✅ КП одобрено",
            style="background: #dcfce7; color: #166534; padding: 1rem; border-radius: 8px; text-align: center; font-weight: 500; margin-bottom: 1rem;"
        )
    else:
        status_banner = Div(
            f"Статус: {workflow_status_badge(workflow_status)}",
            style="margin-bottom: 1rem;"
        )

    # Approval requirements banner
    approval_banner = None
    if needs_approval and workflow_status == "pending_quote_control":
        approval_banner = Div(
            H4("⚠ Требуется согласование топ-менеджера", style="color: #b45309; margin-bottom: 0.5rem;"),
            Ul(*[Li(reason) for reason in needs_approval_reasons], style="margin: 0; padding-left: 1.5rem; color: #92400e;"),
            style="background: #fef3c7; border: 1px solid #f59e0b; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"
        )

    return page_layout(f"Проверка КП - {quote.get('idn_quote', '')}",
        # Header
        Div(
            A("← Вернуться к списку", href="/quote-control", style="color: #3b82f6; text-decoration: none;"),
            H1(f"📋 Проверка КП {quote.get('idn_quote', '')}"),
            P(f"Клиент: {customer_name} | Сумма: {format_money(quote_total)} {currency}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(workflow_status),

        # Status banner
        status_banner,

        # Approval requirements banner
        approval_banner,

        # Quote summary card
        Div(
            H3("Сводка по КП"),
            Div(
                Div(
                    Strong("Тип сделки: "), deal_type_display,
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Incoterms: "), incoterms or "—",
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Валюта: "), currency,
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Наценка: "), f"{markup}%",
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Позиций: "), str(len(items)),
                    style="margin-bottom: 0.5rem;"
                ),
                style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem;"
            ),
            cls="card",
            style="margin-bottom: 1rem;"
        ),

        # Checklist
        Div(
            H3("✓ Чек-лист проверки"),
            P("Проверьте все пункты перед одобрением или возвратом КП", style="color: #666; margin-bottom: 1rem;"),
            *checklist_items,
            cls="card"
        ),

        # Action buttons (only if can edit)
        Div(
            H3("Действия"),
            Div(
                # Return for revision button
                A("↩ Вернуть на доработку", href=f"/quote-control/{quote_id}/return",
                  role="button", style="background: #f59e0b; border-color: #f59e0b;"),
                # Approve or send for approval
                A("✓ Одобрить" if not needs_approval else "⏳ Отправить на согласование",
                  href=f"/quote-control/{quote_id}/approve" if not needs_approval else f"/quote-control/{quote_id}/request-approval",
                  role="button", style="background: #22c55e; border-color: #22c55e;") if workflow_status == "pending_quote_control" else None,
                style="display: flex; gap: 1rem; flex-wrap: wrap;"
            ),
            cls="card",
            style="margin-top: 1rem;"
        ) if can_edit else Div(
            P("Редактирование недоступно в текущем статусе", style="color: #666; text-align: center;"),
            cls="card",
            style="margin-top: 1rem;"
        ),

        # Link to quote details
        Div(
            A("📄 Открыть КП в редакторе", href=f"/quotes/{quote_id}", role="button",
              style="background: #6b7280; border-color: #6b7280;"),
            style="margin-top: 1rem; text-align: center;"
        ),

        # Transition history (Feature #88)
        workflow_transition_history(quote_id),

        session=session
    )


# ============================================================================
# QUOTE CONTROL - RETURN FOR REVISION FORM (Feature #49)
# ============================================================================

@rt("/quote-control/{quote_id}/return")
def get(session, quote_id: str):
    """
    Return for Revision form - shows a form for quote_controller to return a quote
    back to sales manager with a comment explaining what needs to be fixed.

    Feature #49: Форма возврата на доработку
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← Вернуться к списку", href="/quote-control"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is in correct status
    if workflow_status != "pending_quote_control":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе '{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}' и не может быть возвращено на доработку."),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}"),
            session=session
        )

    customer_name = quote.get("customers", {}).get("name", "—")
    idn_quote = quote.get("idn_quote", "")

    return page_layout(f"Возврат на доработку - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(f"↩ Возврат КП {idn_quote} на доработку"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Info banner
        Div(
            "⚠ Внимание: КП будет возвращено менеджеру по продажам для внесения исправлений.",
            style="background: #fef3c7; color: #92400e; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"
        ),

        # Form
        Form(
            Div(
                H3("Причина возврата", style="margin-bottom: 0.5rem;"),
                P("Укажите, что необходимо исправить в КП. Это сообщение увидит менеджер по продажам.",
                  style="color: #666; font-size: 0.875rem; margin-bottom: 1rem;"),
                Textarea(
                    name="comment",
                    id="comment",
                    placeholder="Опишите, какие именно данные требуют исправления:\n- Неверная наценка\n- Ошибки в логистике\n- Некорректные условия оплаты\n- и т.д.",
                    required=True,
                    style="width: 100%; min-height: 150px; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; resize: vertical;"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Action buttons
            Div(
                Button(
                    "↩ Вернуть на доработку",
                    type="submit",
                    style="background: #f59e0b; border-color: #f59e0b; color: white; padding: 0.75rem 1.5rem; border-radius: 6px; cursor: pointer; font-weight: 500;"
                ),
                A("Отмена", href=f"/quote-control/{quote_id}",
                  style="margin-left: 1rem; color: #6b7280; text-decoration: none;"),
                style="display: flex; align-items: center;"
            ),

            action=f"/quote-control/{quote_id}/return",
            method="post",
            cls="card"
        ),

        session=session
    )


@rt("/quote-control/{quote_id}/return")
def post(session, quote_id: str, comment: str = ""):
    """
    Handle the return for revision form submission.
    Transitions the quote from PENDING_QUOTE_CONTROL to PENDING_SALES_REVIEW.

    Feature #49: Форма возврата на доработку - POST handler
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Get user's role codes for the transition
    user_roles = get_user_roles_from_session(session)

    # Validate comment is provided
    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка возврата"),
            P("Необходимо указать причину возврата КП на доработку."),
            A("← Вернуться к форме", href=f"/quote-control/{quote_id}/return"),
            session=session
        )

    supabase = get_supabase()

    # Verify quote exists and belongs to this org
    quote_result = supabase.table("quotes") \
        .select("workflow_status") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← Вернуться к списку", href="/quote-control"),
            session=session
        )

    current_status = quote_result.data[0].get("workflow_status", "draft")

    # Check if quote is in correct status
    if current_status != "pending_quote_control":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе '{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}' и не может быть возвращено на доработку."),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}"),
            session=session
        )

    # Perform the workflow transition
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_SALES_REVIEW,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=comment.strip()
    )

    if result.success:
        # Feature #63: Send notification to quote creator about the return
        # Import asyncio locally if not already imported at module level
        import asyncio
        try:
            asyncio.get_event_loop().run_until_complete(
                notify_creator_of_return(
                    quote_id=quote_id,
                    actor_id=user_id,
                    comment=comment.strip()
                )
            )
        except Exception as e:
            # Log error but don't fail the request - notification is best effort
            print(f"Error sending return notification for quote {quote_id}: {e}")

        # Redirect to quote control list with success message
        return page_layout("Успешно",
            H1("✓ КП возвращено на доработку"),
            P(f"КП было успешно возвращено менеджеру по продажам."),
            P(f"Комментарий: {comment.strip()}", style="color: #666; font-style: italic;"),
            A("← Вернуться к списку КП", href="/quote-control", role="button"),
            session=session
        )
    else:
        # Show error
        return page_layout("Ошибка",
            H1("Ошибка возврата"),
            P(f"Не удалось вернуть КП на доработку: {result.error_message}"),
            A("← Вернуться к форме", href=f"/quote-control/{quote_id}/return"),
            session=session
        )


# ============================================================================
# QUOTE CONTROL - REQUEST APPROVAL FORM (Feature #50)
# ============================================================================

@rt("/quote-control/{quote_id}/request-approval")
def get(session, quote_id: str):
    """
    Request Approval form - shows a form for quote_controller to request
    top manager approval when the quote meets certain criteria.

    Feature #50: Кнопка отправки на согласование

    Approval is required when:
    - Currency is RUB
    - Prepayment is less than 100%
    - Markup is below minimum threshold
    - There is an LPR reward
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← Вернуться к списку", href="/quote-control"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is in correct status
    if workflow_status != "pending_quote_control":
        return page_layout("Согласование невозможно",
            H1("Согласование невозможно"),
            P(f"КП находится в статусе '{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}' и не может быть отправлено на согласование."),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}"),
            session=session
        )

    # Get calculation variables to show reasons
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()
    calc_vars = vars_result.data[0]["variables"] if vars_result.data else {}

    # Calculate approval reasons (same logic as in quote-control detail page)
    deal_type = quote.get("deal_type") or calc_vars.get("offer_sale_type", "")
    currency = quote.get("currency", "USD")
    markup = float(calc_vars.get("markup", 0) or 0)
    prepayment = float(calc_vars.get("client_prepayment_percent", 100) or 100)
    lpr_reward = float(calc_vars.get("lpr_reward", 0) or calc_vars.get("decision_maker_reward", 0) or 0)

    min_markup_supply = 12
    min_markup_transit = 8

    approval_reasons = []
    if currency == "RUB":
        approval_reasons.append("Валюта КП = рубли")
    if prepayment < 100:
        approval_reasons.append(f"Не 100% предоплата ({prepayment}%)")
    if deal_type == "supply" and markup < min_markup_supply:
        approval_reasons.append(f"Наценка ({markup}%) ниже минимума для поставки ({min_markup_supply}%)")
    elif deal_type == "transit" and markup < min_markup_transit:
        approval_reasons.append(f"Наценка ({markup}%) ниже минимума для транзита ({min_markup_transit}%)")
    if lpr_reward > 0:
        approval_reasons.append(f"Есть вознаграждение ЛПРа ({lpr_reward})")

    customer_name = quote.get("customers", {}).get("name", "—")
    idn_quote = quote.get("idn_quote", "")

    # Pre-fill the reason with detected triggers
    default_reason = ""
    if approval_reasons:
        default_reason = "Требуется согласование по следующим причинам:\n" + "\n".join(f"• {r}" for r in approval_reasons)

    return page_layout(f"Запрос согласования - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(f"⏳ Запрос согласования КП {idn_quote}"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Info banner
        Div(
            "ℹ КП будет отправлено на согласование топ-менеджеру. После одобрения вы сможете отправить его клиенту.",
            style="background: #dbeafe; color: #1e40af; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"
        ),

        # Detected reasons card
        Div(
            H3("Причины для согласования"),
            Ul(*[Li(reason) for reason in approval_reasons], style="margin: 0; padding-left: 1.5rem;") if approval_reasons else P("Причины не обнаружены автоматически", style="color: #666;"),
            cls="card",
            style="margin-bottom: 1rem; background: #fef3c7;"
        ) if approval_reasons else None,

        # Form
        Form(
            Div(
                H3("Комментарий для топ-менеджера", style="margin-bottom: 0.5rem;"),
                P("Опишите причину запроса согласования и любую дополнительную информацию.",
                  style="color: #666; font-size: 0.875rem; margin-bottom: 1rem;"),
                Textarea(
                    default_reason,
                    name="comment",
                    id="comment",
                    placeholder="Укажите причину запроса согласования...",
                    required=True,
                    style="width: 100%; min-height: 150px; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; resize: vertical;"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Action buttons
            Div(
                Button(
                    "⏳ Отправить на согласование",
                    type="submit",
                    style="background: #3b82f6; border-color: #3b82f6; color: white; padding: 0.75rem 1.5rem; border-radius: 6px; cursor: pointer; font-weight: 500;"
                ),
                A("Отмена", href=f"/quote-control/{quote_id}",
                  style="margin-left: 1rem; color: #6b7280; text-decoration: none;"),
                style="display: flex; align-items: center;"
            ),

            action=f"/quote-control/{quote_id}/request-approval",
            method="post",
            cls="card"
        ),

        session=session
    )


@rt("/quote-control/{quote_id}/request-approval")
def post(session, quote_id: str, comment: str = ""):
    """
    Handle the request approval form submission.
    Uses request_approval() to:
    1. Transition quote from PENDING_QUOTE_CONTROL to PENDING_APPROVAL
    2. Create approval records for all top_manager/admin users
    3. Send Telegram notifications to approvers

    Feature #50: Кнопка отправки на согласование - POST handler
    Feature #65: Uses request_approval function for complete workflow
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Get user's role codes for the transition
    user_roles = get_user_roles_from_session(session)

    # Validate comment is provided
    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка отправки"),
            P("Необходимо указать причину запроса согласования."),
            A("← Вернуться к форме", href=f"/quote-control/{quote_id}/request-approval"),
            session=session
        )

    supabase = get_supabase()

    # Verify quote exists and belongs to this org
    quote_result = supabase.table("quotes") \
        .select("workflow_status, idn_quote, total_amount, currency, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← Вернуться к списку", href="/quote-control"),
            session=session
        )

    quote = quote_result.data[0]
    idn_quote = quote.get("idn_quote", "")
    customer_name = quote.get("customers", {}).get("name", "") if quote.get("customers") else ""
    total_amount = quote.get("total_amount")

    # Use the new request_approval function (Feature #65)
    # This handles:
    # - Status validation
    # - Workflow transition
    # - Creating approval records for top_manager/admin users
    # - Sending Telegram notifications
    result = request_approval(
        quote_id=quote_id,
        requested_by=user_id,
        reason=comment.strip(),
        organization_id=org_id,
        actor_roles=user_roles,
        quote_idn=idn_quote,
        customer_name=customer_name,
        total_amount=float(total_amount) if total_amount else None,
        send_notifications=True
    )

    if result.success:
        # Success - show details about what was created
        details = []
        if result.approvals_created > 0:
            details.append(P(f"Создано запросов на согласование: {result.approvals_created}"))
        if result.notifications_sent > 0:
            details.append(P(f"Отправлено уведомлений в Telegram: {result.notifications_sent}"))

        return page_layout("Успешно",
            H1("✓ КП отправлено на согласование"),
            P(f"КП {idn_quote} было успешно отправлено на согласование топ-менеджеру."),
            P(f"Комментарий: {comment.strip()}", style="color: #666; font-style: italic;"),
            *details,
            P("Вы получите уведомление о решении.", style="color: #666;"),
            A("← Вернуться к списку КП", href="/quote-control", role="button"),
            session=session
        )
    else:
        # Show error
        return page_layout("Ошибка",
            H1("Ошибка отправки"),
            P(f"Не удалось отправить КП на согласование: {result.error_message}"),
            A("← Вернуться к форме", href=f"/quote-control/{quote_id}/request-approval"),
            session=session
        )


# ============================================================================
# QUOTE CONTROL - APPROVE QUOTE (Feature #51)
# ============================================================================

@rt("/quote-control/{quote_id}/approve")
def get(session, quote_id: str):
    """
    Approve Quote confirmation page - shows a confirmation before approving.

    Feature #51: Кнопка одобрения КП

    This is used when the quote does NOT require top manager approval.
    For quotes that need approval, use /request-approval instead.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← Вернуться к списку", href="/quote-control"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is in correct status
    if workflow_status != "pending_quote_control":
        return page_layout("Одобрение невозможно",
            H1("Одобрение невозможно"),
            P(f"КП находится в статусе '{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}' и не может быть одобрено."),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}"),
            session=session
        )

    # Get calculation variables to check if approval is needed
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()
    calc_vars = vars_result.data[0]["variables"] if vars_result.data else {}

    # Check if approval is required (same logic as in quote-control detail page)
    deal_type = quote.get("deal_type") or calc_vars.get("offer_sale_type", "")
    currency = quote.get("currency", "USD")
    markup = float(calc_vars.get("markup", 0) or 0)
    prepayment = float(calc_vars.get("client_prepayment_percent", 100) or 100)
    lpr_reward = float(calc_vars.get("lpr_reward", 0) or calc_vars.get("decision_maker_reward", 0) or 0)

    min_markup_supply = 12
    min_markup_transit = 8

    approval_reasons = []
    if currency == "RUB":
        approval_reasons.append("Валюта КП = рубли")
    if prepayment < 100:
        approval_reasons.append(f"Не 100% предоплата ({prepayment}%)")
    if deal_type == "supply" and markup < min_markup_supply:
        approval_reasons.append(f"Наценка ниже минимума для поставки")
    elif deal_type == "transit" and markup < min_markup_transit:
        approval_reasons.append(f"Наценка ниже минимума для транзита")
    if lpr_reward > 0:
        approval_reasons.append(f"Есть вознаграждение ЛПРа")

    # If approval is required, redirect to request-approval
    if approval_reasons:
        return page_layout("Требуется согласование",
            H1("⚠ Требуется согласование топ-менеджера"),
            P("Это КП не может быть одобрено напрямую, так как имеются следующие причины для согласования:"),
            Ul(*[Li(reason) for reason in approval_reasons]),
            A("⏳ Отправить на согласование", href=f"/quote-control/{quote_id}/request-approval", role="button"),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}",
              style="margin-left: 1rem; color: #6b7280; text-decoration: none;"),
            session=session
        )

    customer_name = quote.get("customers", {}).get("name", "—")
    idn_quote = quote.get("idn_quote", "")
    total_amount = float(quote.get("total_amount", 0) or 0)
    quote_currency = quote.get("currency", "USD")

    return page_layout(f"Одобрение КП - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(f"✓ Одобрение КП {idn_quote}"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Success banner
        Div(
            "✓ КП прошло проверку и может быть одобрено",
            style="background: #dcfce7; color: #166534; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"
        ),

        # Quote summary card
        Div(
            H3("Сводка по КП"),
            Div(
                Div(Strong("Сумма: "), f"{format_money(total_amount)} {quote_currency}"),
                Div(Strong("Наценка: "), f"{markup}%"),
                Div(Strong("Предоплата: "), f"{prepayment}%"),
                style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem;"
            ),
            cls="card",
            style="margin-bottom: 1rem;"
        ),

        # Confirmation form
        Form(
            P("После одобрения КП станет доступно для отправки клиенту.", style="color: #666; margin-bottom: 1rem;"),

            # Optional comment
            Div(
                Label("Комментарий (необязательно)", for_="comment", style="font-weight: 500; margin-bottom: 0.25rem; display: block;"),
                Textarea(
                    name="comment",
                    id="comment",
                    placeholder="Дополнительные комментарии...",
                    style="width: 100%; min-height: 80px; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; resize: vertical;"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Action buttons
            Div(
                Button(
                    "✓ Одобрить КП",
                    type="submit",
                    style="background: #22c55e; border-color: #22c55e; color: white; padding: 0.75rem 1.5rem; border-radius: 6px; cursor: pointer; font-weight: 500;"
                ),
                A("Отмена", href=f"/quote-control/{quote_id}",
                  style="margin-left: 1rem; color: #6b7280; text-decoration: none;"),
                style="display: flex; align-items: center;"
            ),

            action=f"/quote-control/{quote_id}/approve",
            method="post",
            cls="card"
        ),

        session=session
    )


@rt("/quote-control/{quote_id}/approve")
def post(session, quote_id: str, comment: str = ""):
    """
    Handle the approve quote form submission.
    Transitions the quote from PENDING_QUOTE_CONTROL to APPROVED.

    Feature #51: Кнопка одобрения КП - POST handler
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has quote_controller role
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Get user's role codes for the transition
    user_roles = get_user_roles_from_session(session)

    supabase = get_supabase()

    # Verify quote exists and belongs to this org
    quote_result = supabase.table("quotes") \
        .select("workflow_status, idn_quote") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← Вернуться к списку", href="/quote-control"),
            session=session
        )

    quote = quote_result.data[0]
    current_status = quote.get("workflow_status", "draft")
    idn_quote = quote.get("idn_quote", "")

    # Check if quote is in correct status
    if current_status != "pending_quote_control":
        return page_layout("Одобрение невозможно",
            H1("Одобрение невозможно"),
            P(f"КП находится в статусе '{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}' и не может быть одобрено."),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}"),
            session=session
        )

    # Perform the workflow transition to APPROVED
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.APPROVED,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=comment.strip() if comment else "Одобрено контроллером КП"
    )

    if result.success:
        # Success - redirect to quote control list
        return page_layout("Успешно",
            H1("✓ КП одобрено"),
            P(f"КП {idn_quote} было успешно одобрено."),
            P("Теперь менеджер по продажам может отправить его клиенту.", style="color: #666;"),
            A("← Вернуться к списку КП", href="/quote-control", role="button"),
            session=session
        )
    else:
        # Show error
        return page_layout("Ошибка",
            H1("Ошибка одобрения"),
            P(f"Не удалось одобрить КП: {result.error_message}"),
            A("← Вернуться к форме", href=f"/quote-control/{quote_id}/approve"),
            session=session
        )


# ============================================================================
# TELEGRAM BOT WEBHOOK (Feature #53)
# ============================================================================

# Import asyncio for running async webhook handler
import asyncio

# Import telegram service functions
from services.telegram_service import (
    is_bot_configured,
    process_webhook_update,
    respond_to_command,
    WebhookResult,
    # Feature #56 imports
    get_user_telegram_status,
    request_verification_code,
    unlink_telegram_account,
    # Feature #60 imports
    handle_approve_callback,
    send_callback_response,
    # Feature #61 imports
    handle_reject_callback,
    # Feature #63 imports
    notify_creator_of_return,
)


@rt("/api/telegram/webhook")
async def telegram_webhook(request):
    """Handle incoming Telegram webhook updates.

    This endpoint receives updates from Telegram when:
    - Users send messages to the bot (/start, /status, /help)
    - Users press inline buttons (approve, reject, details)

    Returns:
        JSON response with status

    Note:
        - This endpoint must be publicly accessible (HTTPS in production)
        - Webhook URL must be registered with Telegram via set_webhook()
        - Always return 200 OK quickly to prevent Telegram from retrying
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    # Check if bot is configured
    if not is_bot_configured():
        logger.warning("Telegram webhook received but bot is not configured")
        return {"ok": True, "message": "Bot not configured"}

    # Get the request body
    try:
        # FastHTML provides the body through request
        body = await request.body()
        json_data = json.loads(body)
    except Exception as e:
        logger.error(f"Failed to parse webhook request: {e}")
        return {"ok": False, "error": "Invalid request body"}

    # Log the incoming update (for debugging)
    logger.info(f"Telegram webhook received update: {json_data.get('update_id', 'unknown')}")

    # Process the update asynchronously
    try:
        result: WebhookResult = await process_webhook_update(json_data)

        if result.success:
            # Handle different update types
            if result.update_type == "command" and result.telegram_id and result.text:
                # Respond to commands, passing any arguments (e.g., /start ABC123)
                # Also pass telegram_username for verification (Feature #55)
                await respond_to_command(result.telegram_id, result.text, result.args, result.telegram_username)

            elif result.update_type == "callback_query" and result.callback_data:
                # Handle callback queries (inline button presses)
                callback_data = result.callback_data
                logger.info(f"Callback query: {callback_data.action} for {callback_data.quote_id}")

                # Feature #60: Handle approve callback
                if callback_data.action == "approve":
                    approve_result = await handle_approve_callback(
                        telegram_id=result.telegram_id,
                        quote_id=callback_data.quote_id
                    )
                    logger.info(f"Approve callback result: success={approve_result.success}, quote={approve_result.quote_idn}")

                    # Get message_id from the original update to edit the message
                    message_id = json_data.get("callback_query", {}).get("message", {}).get("message_id")
                    if message_id and result.telegram_id:
                        await send_callback_response(result.telegram_id, message_id, approve_result)

                # Feature #61: Handle reject callback
                elif callback_data.action == "reject":
                    reject_result = await handle_reject_callback(
                        telegram_id=result.telegram_id,
                        quote_id=callback_data.quote_id
                    )
                    logger.info(f"Reject callback result: success={reject_result.success}, quote={reject_result.quote_idn}")

                    # Get message_id from the original update to edit the message
                    message_id = json_data.get("callback_query", {}).get("message", {}).get("message_id")
                    if message_id and result.telegram_id:
                        await send_callback_response(result.telegram_id, message_id, reject_result)

                # Handle details callback - just log for now
                elif callback_data.action == "details":
                    logger.info(f"Details callback for quote {callback_data.quote_id}")

            elif result.update_type == "message":
                # Regular text message (not a command)
                logger.info(f"Text message from {result.telegram_id}: {result.text}")

            logger.info(f"Webhook processed: {result.message}")
        else:
            logger.warning(f"Webhook processing failed: {result.error}")

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Still return 200 to prevent Telegram from retrying
        return {"ok": True, "error": str(e)}

    # Always return 200 OK to Telegram
    return {"ok": True}


# ============================================================================
# SPEC CONTROL WORKSPACE (Features #67-72)
# ============================================================================

@rt("/spec-control")
def get(session, status_filter: str = None):
    """
    Spec Control workspace - shows quotes pending specification and existing specifications
    for spec_controller role.

    Feature #67: Basic spec control page structure
    Feature #68: List specifications at pending_review status (included)

    This page shows:
    1. Quotes awaiting specification creation (workflow_status = pending_spec_control)
    2. Existing specifications with their review status (draft, pending_review, approved, signed)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has spec_controller role
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get quotes awaiting specification creation (pending_spec_control status)
    quotes_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), workflow_status, status, total_amount, currency, created_at, deal_type, current_version_id") \
        .eq("organization_id", org_id) \
        .eq("workflow_status", "pending_spec_control") \
        .order("created_at", desc=True) \
        .execute()

    pending_quotes = quotes_result.data or []

    # Get all specifications for this organization
    specs_result = supabase.table("specifications") \
        .select("id, quote_id, specification_number, proposal_idn, status, sign_date, specification_currency, created_at, updated_at, quotes(idn_quote, customers(name))") \
        .eq("organization_id", org_id) \
        .order("created_at", desc=True) \
        .execute()

    all_specs = specs_result.data or []

    # Filter specifications by status if filter is applied
    if status_filter and status_filter != "all":
        if status_filter == "pending_quotes":
            # Show only the pending quotes section (handled separately)
            filtered_specs = []
        else:
            filtered_specs = [s for s in all_specs if s.get("status") == status_filter]
    else:
        filtered_specs = all_specs

    # Group specifications by status
    draft_specs = [s for s in all_specs if s.get("status") == "draft"]
    pending_review_specs = [s for s in all_specs if s.get("status") == "pending_review"]
    approved_specs = [s for s in all_specs if s.get("status") == "approved"]
    signed_specs = [s for s in all_specs if s.get("status") == "signed"]

    # Stats
    stats = {
        "pending_quotes": len(pending_quotes),
        "draft_specs": len(draft_specs),
        "pending_review": len(pending_review_specs),
        "approved": len(approved_specs),
        "signed": len(signed_specs),
        "total_specs": len(all_specs),
    }

    # Spec status badge helper
    def spec_status_badge(status):
        status_map = {
            "draft": ("Черновик", "bg-gray-200 text-gray-800"),
            "pending_review": ("На проверке", "bg-yellow-200 text-yellow-800"),
            "approved": ("Утверждена", "bg-blue-200 text-blue-800"),
            "signed": ("Подписана", "bg-green-200 text-green-800"),
        }
        label, classes = status_map.get(status, (status, "bg-gray-200 text-gray-800"))
        return Span(label, cls=f"px-2 py-1 rounded text-sm {classes}")

    # Deal type badge helper
    def deal_type_badge(deal_type):
        if deal_type == "supply":
            return Span("Поставка", cls="px-2 py-1 rounded text-sm bg-blue-100 text-blue-800")
        elif deal_type == "transit":
            return Span("Транзит", cls="px-2 py-1 rounded text-sm bg-yellow-100 text-yellow-800")
        return None

    # Quote row for pending quotes section
    def pending_quote_row(quote):
        customer_name = quote.get("customers", {}).get("name", "Unknown") if quote.get("customers") else "Unknown"
        return Tr(
            Td(A(quote.get("idn_quote", "-"), href=f"/quotes/{quote['id']}")),
            Td(customer_name),
            Td(deal_type_badge(quote.get("deal_type")) or "-"),
            Td(f"{quote.get('total_amount', 0):,.2f} {quote.get('currency', 'RUB')}"),
            Td(quote.get("created_at", "")[:10] if quote.get("created_at") else "-"),
            Td(
                A("Создать спецификацию", href=f"/spec-control/create/{quote['id']}", role="button",
                  style="background: #28a745; border-color: #28a745; font-size: 0.875rem; padding: 0.25rem 0.5rem;"),
            ),
        )

    # Spec row for specifications section
    def spec_row(spec, show_work_button=True):
        quote = spec.get("quotes", {}) or {}
        customer = quote.get("customers", {}) or {}
        quote_idn = quote.get("idn_quote", "-")
        customer_name = customer.get("name", "Unknown")

        return Tr(
            Td(spec.get("specification_number", "-") or A(quote_idn, href=f"/quotes/{spec.get('quote_id')}")),
            Td(customer_name),
            Td(spec_status_badge(spec.get("status", "draft"))),
            Td(spec.get("specification_currency", "-")),
            Td(spec.get("created_at", "")[:10] if spec.get("created_at") else "-"),
            Td(
                A("Редактировать", href=f"/spec-control/{spec['id']}", role="button",
                  style="background: #007bff; border-color: #007bff; font-size: 0.875rem; padding: 0.25rem 0.5rem;") if show_work_button and spec.get("status") in ["draft", "pending_review"] else
                A("Просмотр", href=f"/spec-control/{spec['id']}", style="color: #666; font-size: 0.875rem;"),
            ),
        )

    return page_layout("Контроль спецификаций",
        H1("Контроль спецификаций"),

        # Stats cards
        Div(
            Div(
                Div(str(stats["pending_quotes"]), cls="stat-value", style="color: #f59e0b;"),
                Div("Ожидают спецификации", style="font-size: 0.875rem;"),
                cls="stat-card",
                style="border-left: 4px solid #f59e0b;" if stats["pending_quotes"] > 0 else ""
            ),
            Div(
                Div(str(stats["pending_review"]), cls="stat-value", style="color: #3b82f6;"),
                Div("На проверке", style="font-size: 0.875rem;"),
                cls="stat-card"
            ),
            Div(
                Div(str(stats["approved"]), cls="stat-value", style="color: #22c55e;"),
                Div("Утверждены", style="font-size: 0.875rem;"),
                cls="stat-card"
            ),
            Div(
                Div(str(stats["signed"]), cls="stat-value", style="color: #10b981;"),
                Div("Подписаны", style="font-size: 0.875rem;"),
                cls="stat-card"
            ),
            cls="grid",
            style="grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;"
        ),

        # Status filter
        Div(
            Label("Фильтр: ", For="status_filter"),
            Select(
                Option("Все", value="all", selected=not status_filter or status_filter == "all"),
                Option(f"Ожидают спецификации ({stats['pending_quotes']})", value="pending_quotes", selected=status_filter == "pending_quotes"),
                Option(f"Черновики ({stats['draft_specs']})", value="draft", selected=status_filter == "draft"),
                Option(f"На проверке ({stats['pending_review']})", value="pending_review", selected=status_filter == "pending_review"),
                Option(f"Утверждены ({stats['approved']})", value="approved", selected=status_filter == "approved"),
                Option(f"Подписаны ({stats['signed']})", value="signed", selected=status_filter == "signed"),
                id="status_filter",
                onchange="window.location.href='/spec-control?status_filter=' + this.value"
            ),
            style="margin-bottom: 1.5rem;"
        ),

        # Pending quotes section (quotes waiting for spec creation)
        Div(
            H2(f"КП ожидающие спецификации ({stats['pending_quotes']})"),
            Table(
                Thead(
                    Tr(
                        Th("№ КП"),
                        Th("Клиент"),
                        Th("Тип сделки"),
                        Th("Сумма"),
                        Th("Дата"),
                        Th("Действие"),
                    )
                ),
                Tbody(
                    *[pending_quote_row(q) for q in pending_quotes]
                ) if pending_quotes else Tbody(Tr(Td("Нет КП, ожидающих спецификации", colspan="6", style="text-align: center; color: #666;"))),
            ),
            cls="card",
            style="margin-bottom: 2rem;"
        ) if not status_filter or status_filter in ["all", "pending_quotes"] else None,

        # Specifications on review section
        Div(
            H2(f"Спецификации на проверке ({stats['pending_review']})"),
            Table(
                Thead(
                    Tr(
                        Th("№ Спецификации"),
                        Th("Клиент"),
                        Th("Статус"),
                        Th("Валюта"),
                        Th("Дата"),
                        Th("Действие"),
                    )
                ),
                Tbody(
                    *[spec_row(s, show_work_button=True) for s in pending_review_specs]
                ) if pending_review_specs else Tbody(Tr(Td("Нет спецификаций на проверке", colspan="6", style="text-align: center; color: #666;"))),
            ),
            cls="card",
            style="margin-bottom: 2rem;"
        ) if not status_filter or status_filter in ["all", "pending_review"] else None,

        # Draft specifications section
        Div(
            H2(f"Черновики ({stats['draft_specs']})"),
            Table(
                Thead(
                    Tr(
                        Th("№ Спецификации / КП"),
                        Th("Клиент"),
                        Th("Статус"),
                        Th("Валюта"),
                        Th("Дата"),
                        Th("Действие"),
                    )
                ),
                Tbody(
                    *[spec_row(s, show_work_button=True) for s in draft_specs[:10]]
                ) if draft_specs else Tbody(Tr(Td("Нет черновиков", colspan="6", style="text-align: center; color: #666;"))),
            ),
            cls="card",
            style="margin-bottom: 2rem;"
        ) if not status_filter or status_filter in ["all", "draft"] else None,

        # Approved/Signed specifications section
        Div(
            H2(f"Утверждённые и подписанные ({stats['approved'] + stats['signed']})"),
            Table(
                Thead(
                    Tr(
                        Th("№ Спецификации"),
                        Th("Клиент"),
                        Th("Статус"),
                        Th("Валюта"),
                        Th("Дата"),
                        Th("Действие"),
                    )
                ),
                Tbody(
                    *[spec_row(s, show_work_button=False) for s in (approved_specs + signed_specs)[:10]]
                ) if (approved_specs + signed_specs) else Tbody(Tr(Td("Нет утверждённых спецификаций", colspan="6", style="text-align: center; color: #666;"))),
            ),
            cls="card",
            style="margin-bottom: 2rem;"
        ) if not status_filter or status_filter in ["all", "approved", "signed"] else None,

        session=session
    )


# ============================================================================
# SPECIFICATION DATA ENTRY (Feature #69)
# ============================================================================

@rt("/spec-control/create/{quote_id}")
def get(session, quote_id: str):
    """
    Create a new specification from a quote.

    Feature #69: Specification data entry form (create new)
    - Shows quote summary
    - Pre-fills some fields from quote data
    - Form for all 18 specification fields
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has spec_controller role
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не найдено или у вас нет доступа."),
            A("← Назад к спецификациям", href="/spec-control"),
            session=session
        )

    quote = quote_result.data[0]
    customer = quote.get("customers", {}) or {}
    customer_name = customer.get("name", "Unknown")

    # Check if specification already exists for this quote
    existing_spec = supabase.table("specifications") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .execute()

    if existing_spec.data:
        # Redirect to edit existing specification
        return RedirectResponse(f"/spec-control/{existing_spec.data[0]['id']}", status_code=303)

    # Get quote versions for version selection
    versions_result = supabase.table("quote_versions") \
        .select("id, version_number, comment, created_at, total_amount, currency") \
        .eq("quote_id", quote_id) \
        .order("version_number", desc=True) \
        .execute()

    versions = versions_result.data or []

    # Get quote calculation variables for pre-filling some fields
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_vars = vars_result.data[0].get("variables", {}) if vars_result.data else {}

    # Pre-fill values from quote
    prefill = {
        "proposal_idn": quote.get("idn_quote", ""),
        "specification_currency": quote.get("currency", "USD"),
        "client_legal_entity": customer_name,
        "delivery_city_russia": calc_vars.get("delivery_city", ""),
        "cargo_pickup_country": calc_vars.get("supplier_country", ""),
    }

    # Form fields grouped by category
    return page_layout("Создание спецификации",
        H1("Создание спецификации"),

        # Quote summary
        Div(
            H3(f"КП: {quote.get('idn_quote', '-')}"),
            P(f"Клиент: {customer_name}"),
            P(f"Сумма: {quote.get('total_amount', 0):,.2f} {quote.get('currency', 'RUB')}"),
            cls="card",
            style="margin-bottom: 1.5rem; background: #f0f9ff;"
        ),

        Form(
            # Hidden fields
            Input(type="hidden", name="quote_id", value=quote_id),
            Input(type="hidden", name="organization_id", value=org_id),

            # Section 1: Identification
            Div(
                H3("📋 Идентификация"),
                Div(
                    Div(
                        Label("№ Спецификации", For="specification_number"),
                        Input(name="specification_number", id="specification_number",
                              placeholder="SPEC-2025-0001",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("IDN КП", For="proposal_idn"),
                        Input(name="proposal_idn", id="proposal_idn",
                              value=prefill.get("proposal_idn", ""),
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("IDN-SKU", For="item_ind_sku"),
                        Input(name="item_ind_sku", id="item_ind_sku",
                              placeholder="IDN-SKU identifier",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Версия КП", For="quote_version_id"),
                        Select(
                            Option("-- Выберите версию --", value=""),
                            *[Option(
                                f"v{v.get('version_number', 0)} - {v.get('total_amount', 0):,.2f} {v.get('currency', '')} ({v.get('created_at', '')[:10]})",
                                value=v.get("id"),
                                selected=v.get("id") == quote.get("current_version_id")
                            ) for v in versions],
                            name="quote_version_id",
                            id="quote_version_id",
                            style="width: 100%;"
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 2: Dates and Validity
            Div(
                H3("📅 Даты и сроки"),
                Div(
                    Div(
                        Label("Дата подписания", For="sign_date"),
                        Input(name="sign_date", id="sign_date", type="date",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок действия", For="validity_period"),
                        Input(name="validity_period", id="validity_period",
                              placeholder="90 дней",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок готовности", For="readiness_period"),
                        Input(name="readiness_period", id="readiness_period",
                              placeholder="30-45 дней",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок на логистику", For="logistics_period"),
                        Input(name="logistics_period", id="logistics_period",
                              placeholder="14-21 дней",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 3: Currency and Payment
            Div(
                H3("💰 Валюта и оплата"),
                Div(
                    Div(
                        Label("Валюта спецификации", For="specification_currency"),
                        Select(
                            Option("USD", value="USD", selected=prefill.get("specification_currency") == "USD"),
                            Option("EUR", value="EUR", selected=prefill.get("specification_currency") == "EUR"),
                            Option("RUB", value="RUB", selected=prefill.get("specification_currency") == "RUB"),
                            Option("CNY", value="CNY", selected=prefill.get("specification_currency") == "CNY"),
                            name="specification_currency",
                            id="specification_currency",
                            style="width: 100%;"
                        ),
                        cls="form-group"
                    ),
                    Div(
                        Label("Курс к рублю", For="exchange_rate_to_ruble"),
                        Input(name="exchange_rate_to_ruble", id="exchange_rate_to_ruble",
                              type="number", step="0.0001",
                              placeholder="91.5000",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок оплаты после УПД (дней)", For="client_payment_term_after_upd"),
                        Input(name="client_payment_term_after_upd", id="client_payment_term_after_upd",
                              type="number", min="0",
                              placeholder="0",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Условия оплаты клиента", For="client_payment_terms"),
                        Input(name="client_payment_terms", id="client_payment_terms",
                              placeholder="100% предоплата",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 4: Origin and Shipping
            Div(
                H3("🚚 Отгрузка и доставка"),
                Div(
                    Div(
                        Label("Страна забора груза", For="cargo_pickup_country"),
                        Input(name="cargo_pickup_country", id="cargo_pickup_country",
                              value=prefill.get("cargo_pickup_country", ""),
                              placeholder="Китай",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Страна товара к отгрузке", For="goods_shipment_country"),
                        Input(name="goods_shipment_country", id="goods_shipment_country",
                              placeholder="Китай",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Город доставки в РФ", For="delivery_city_russia"),
                        Input(name="delivery_city_russia", id="delivery_city_russia",
                              value=prefill.get("delivery_city_russia", ""),
                              placeholder="Москва",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Тип груза", For="cargo_type"),
                        Input(name="cargo_type", id="cargo_type",
                              placeholder="Генеральный",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Страна оплаты поставщику", For="supplier_payment_country"),
                        Input(name="supplier_payment_country", id="supplier_payment_country",
                              placeholder="Китай",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 5: Legal Entities
            Div(
                H3("🏢 Юридические лица"),
                Div(
                    Div(
                        Label("Наше юридическое лицо", For="our_legal_entity"),
                        Input(name="our_legal_entity", id="our_legal_entity",
                              placeholder="ООО \"Наша компания\"",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Юридическое лицо клиента", For="client_legal_entity"),
                        Input(name="client_legal_entity", id="client_legal_entity",
                              value=prefill.get("client_legal_entity", ""),
                              placeholder="ООО \"Клиент\"",
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Action buttons
            Div(
                Button("💾 Создать спецификацию", type="submit", name="action", value="create",
                       style="background: #28a745; border-color: #28a745;"),
                A("Отмена", href="/spec-control", role="button",
                  style="background: #6c757d; border-color: #6c757d; margin-left: 1rem;"),
                style="margin-top: 1rem;"
            ),

            action=f"/spec-control/create/{quote_id}",
            method="POST"
        ),

        session=session
    )


@rt("/spec-control/create/{quote_id}")
def post(session, quote_id: str, action: str = "create", **kwargs):
    """
    Create a new specification from form data.

    Feature #69: Specification data entry form (create POST handler)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify quote exists and belongs to org
    quote_result = supabase.table("quotes") \
        .select("id, organization_id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        return RedirectResponse("/spec-control", status_code=303)

    # Check if specification already exists
    existing_spec = supabase.table("specifications") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .execute()

    if existing_spec.data:
        return RedirectResponse(f"/spec-control/{existing_spec.data[0]['id']}", status_code=303)

    # Helper for safe numeric conversion
    def safe_decimal(val, default=None):
        try:
            return float(val) if val else default
        except:
            return default

    def safe_int(val, default=None):
        try:
            return int(val) if val else default
        except:
            return default

    # Build specification data
    spec_data = {
        "quote_id": quote_id,
        "organization_id": org_id,
        "quote_version_id": kwargs.get("quote_version_id") or None,
        "specification_number": kwargs.get("specification_number") or None,
        "proposal_idn": kwargs.get("proposal_idn") or None,
        "item_ind_sku": kwargs.get("item_ind_sku") or None,
        "sign_date": kwargs.get("sign_date") or None,
        "validity_period": kwargs.get("validity_period") or None,
        "specification_currency": kwargs.get("specification_currency") or "USD",
        "exchange_rate_to_ruble": safe_decimal(kwargs.get("exchange_rate_to_ruble")),
        "client_payment_term_after_upd": safe_int(kwargs.get("client_payment_term_after_upd")),
        "client_payment_terms": kwargs.get("client_payment_terms") or None,
        "cargo_pickup_country": kwargs.get("cargo_pickup_country") or None,
        "readiness_period": kwargs.get("readiness_period") or None,
        "goods_shipment_country": kwargs.get("goods_shipment_country") or None,
        "delivery_city_russia": kwargs.get("delivery_city_russia") or None,
        "cargo_type": kwargs.get("cargo_type") or None,
        "logistics_period": kwargs.get("logistics_period") or None,
        "our_legal_entity": kwargs.get("our_legal_entity") or None,
        "client_legal_entity": kwargs.get("client_legal_entity") or None,
        "supplier_payment_country": kwargs.get("supplier_payment_country") or None,
        "status": "draft",
        "created_by": user_id,
    }

    # Insert specification
    result = supabase.table("specifications").insert(spec_data).execute()

    if result.data:
        spec_id = result.data[0]["id"]
        return RedirectResponse(f"/spec-control/{spec_id}", status_code=303)
    else:
        return page_layout("Ошибка",
            H1("Ошибка создания спецификации"),
            P("Не удалось создать спецификацию. Попробуйте еще раз."),
            A("← Назад", href=f"/spec-control/create/{quote_id}"),
            session=session
        )


@rt("/spec-control/{spec_id}")
def get(session, spec_id: str):
    """
    View/edit an existing specification.

    Feature #69: Specification data entry form (edit existing)
    - Shows all 18 specification fields
    - Editable when status is draft or pending_review
    - Shows quote summary and customer info
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has spec_controller role
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch specification with quote and customer info
    spec_result = supabase.table("specifications") \
        .select("*, quotes(id, idn_quote, total_amount, currency, workflow_status, customers(name, inn))") \
        .eq("id", spec_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not spec_result.data:
        return page_layout("Спецификация не найдена",
            H1("Спецификация не найдена"),
            P("Запрошенная спецификация не найдена или у вас нет доступа."),
            A("← Назад к спецификациям", href="/spec-control"),
            session=session
        )

    spec = spec_result.data[0]
    quote = spec.get("quotes", {}) or {}
    customer = quote.get("customers", {}) or {}
    customer_name = customer.get("name", "Unknown")
    quote_id = spec.get("quote_id")
    status = spec.get("status", "draft")
    quote_workflow_status = quote.get("workflow_status", "draft")

    # Check if editable
    is_editable = status in ["draft", "pending_review"]

    # Get quote versions for version selection
    versions_result = supabase.table("quote_versions") \
        .select("id, version_number, comment, created_at, total_amount, currency") \
        .eq("quote_id", quote_id) \
        .order("version_number", desc=True) \
        .execute()

    versions = versions_result.data or []

    # Status badge helper
    def spec_status_badge(status):
        status_map = {
            "draft": ("Черновик", "bg-gray-200 text-gray-800"),
            "pending_review": ("На проверке", "bg-yellow-200 text-yellow-800"),
            "approved": ("Утверждена", "bg-blue-200 text-blue-800"),
            "signed": ("Подписана", "bg-green-200 text-green-800"),
        }
        label, classes = status_map.get(status, (status, "bg-gray-200 text-gray-800"))
        return Span(label, cls=f"px-2 py-1 rounded text-sm {classes}")

    return page_layout("Редактирование спецификации",
        H1("Редактирование спецификации"),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(quote_workflow_status),

        # Status and info banner
        Div(
            Div(
                H3(f"Спецификация: {spec.get('specification_number', '-') or 'Без номера'}"),
                P(
                    "Статус: ", spec_status_badge(status),
                    style="margin-top: 0.5rem;"
                ),
            ),
            Div(
                P(f"КП: {quote.get('idn_quote', '-')}"),
                P(f"Клиент: {customer_name}"),
                P(f"Сумма КП: {quote.get('total_amount', 0):,.2f} {quote.get('currency', 'RUB')}"),
                style="text-align: right;"
            ),
            cls="card",
            style="margin-bottom: 1.5rem; background: #f0f9ff; display: flex; justify-content: space-between; align-items: start;"
        ),

        # Warning banner if not editable
        Div(
            "⚠️ Спецификация утверждена/подписана и не может быть отредактирована.",
            cls="card",
            style="background: #fef3c7; border-left: 4px solid #f59e0b; margin-bottom: 1.5rem;"
        ) if not is_editable else None,

        Form(
            # Hidden fields
            Input(type="hidden", name="spec_id", value=spec_id),

            # Section 1: Identification
            Div(
                H3("📋 Идентификация"),
                Div(
                    Div(
                        Label("№ Спецификации", For="specification_number"),
                        Input(name="specification_number", id="specification_number",
                              value=spec.get("specification_number", ""),
                              placeholder="SPEC-2025-0001",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("IDN КП", For="proposal_idn"),
                        Input(name="proposal_idn", id="proposal_idn",
                              value=spec.get("proposal_idn", ""),
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("IDN-SKU", For="item_ind_sku"),
                        Input(name="item_ind_sku", id="item_ind_sku",
                              value=spec.get("item_ind_sku", ""),
                              placeholder="IDN-SKU identifier",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Версия КП", For="quote_version_id"),
                        Select(
                            Option("-- Выберите версию --", value=""),
                            *[Option(
                                f"v{v.get('version_number', 0)} - {v.get('total_amount', 0):,.2f} {v.get('currency', '')} ({v.get('created_at', '')[:10]})",
                                value=v.get("id"),
                                selected=v.get("id") == spec.get("quote_version_id")
                            ) for v in versions],
                            name="quote_version_id",
                            id="quote_version_id",
                            disabled=not is_editable,
                            style="width: 100%;"
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 2: Dates and Validity
            Div(
                H3("📅 Даты и сроки"),
                Div(
                    Div(
                        Label("Дата подписания", For="sign_date"),
                        Input(name="sign_date", id="sign_date", type="date",
                              value=spec.get("sign_date", "") or "",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок действия", For="validity_period"),
                        Input(name="validity_period", id="validity_period",
                              value=spec.get("validity_period", ""),
                              placeholder="90 дней",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок готовности", For="readiness_period"),
                        Input(name="readiness_period", id="readiness_period",
                              value=spec.get("readiness_period", ""),
                              placeholder="30-45 дней",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок на логистику", For="logistics_period"),
                        Input(name="logistics_period", id="logistics_period",
                              value=spec.get("logistics_period", ""),
                              placeholder="14-21 дней",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 3: Currency and Payment
            Div(
                H3("💰 Валюта и оплата"),
                Div(
                    Div(
                        Label("Валюта спецификации", For="specification_currency"),
                        Select(
                            Option("USD", value="USD", selected=spec.get("specification_currency") == "USD"),
                            Option("EUR", value="EUR", selected=spec.get("specification_currency") == "EUR"),
                            Option("RUB", value="RUB", selected=spec.get("specification_currency") == "RUB"),
                            Option("CNY", value="CNY", selected=spec.get("specification_currency") == "CNY"),
                            name="specification_currency",
                            id="specification_currency",
                            disabled=not is_editable,
                            style="width: 100%;"
                        ),
                        cls="form-group"
                    ),
                    Div(
                        Label("Курс к рублю", For="exchange_rate_to_ruble"),
                        Input(name="exchange_rate_to_ruble", id="exchange_rate_to_ruble",
                              type="number", step="0.0001",
                              value=str(spec.get("exchange_rate_to_ruble", "")) if spec.get("exchange_rate_to_ruble") else "",
                              placeholder="91.5000",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Срок оплаты после УПД (дней)", For="client_payment_term_after_upd"),
                        Input(name="client_payment_term_after_upd", id="client_payment_term_after_upd",
                              type="number", min="0",
                              value=str(spec.get("client_payment_term_after_upd", "")) if spec.get("client_payment_term_after_upd") is not None else "",
                              placeholder="0",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Условия оплаты клиента", For="client_payment_terms"),
                        Input(name="client_payment_terms", id="client_payment_terms",
                              value=spec.get("client_payment_terms", ""),
                              placeholder="100% предоплата",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 4: Origin and Shipping
            Div(
                H3("🚚 Отгрузка и доставка"),
                Div(
                    Div(
                        Label("Страна забора груза", For="cargo_pickup_country"),
                        Input(name="cargo_pickup_country", id="cargo_pickup_country",
                              value=spec.get("cargo_pickup_country", ""),
                              placeholder="Китай",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Страна товара к отгрузке", For="goods_shipment_country"),
                        Input(name="goods_shipment_country", id="goods_shipment_country",
                              value=spec.get("goods_shipment_country", ""),
                              placeholder="Китай",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Город доставки в РФ", For="delivery_city_russia"),
                        Input(name="delivery_city_russia", id="delivery_city_russia",
                              value=spec.get("delivery_city_russia", ""),
                              placeholder="Москва",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Тип груза", For="cargo_type"),
                        Input(name="cargo_type", id="cargo_type",
                              value=spec.get("cargo_type", ""),
                              placeholder="Генеральный",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Страна оплаты поставщику", For="supplier_payment_country"),
                        Input(name="supplier_payment_country", id="supplier_payment_country",
                              value=spec.get("supplier_payment_country", ""),
                              placeholder="Китай",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Section 5: Legal Entities
            Div(
                H3("🏢 Юридические лица"),
                Div(
                    Div(
                        Label("Наше юридическое лицо", For="our_legal_entity"),
                        Input(name="our_legal_entity", id="our_legal_entity",
                              value=spec.get("our_legal_entity", ""),
                              placeholder="ООО \"Наша компания\"",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Юридическое лицо клиента", For="client_legal_entity"),
                        Input(name="client_legal_entity", id="client_legal_entity",
                              value=spec.get("client_legal_entity", ""),
                              placeholder="ООО \"Клиент\"",
                              disabled=not is_editable,
                              style="width: 100%;"),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="margin-bottom: 1.5rem;"
            ),

            # Feature #71: Section 6 - Signed Scan Upload (visible when status is approved or signed)
            Div(
                H3("✍️ Подписанный скан"),
                # Show current scan if exists
                Div(
                    P(
                        "✅ Скан загружен: ",
                        A(spec.get("signed_scan_url", "").split("/")[-1] if spec.get("signed_scan_url") else "",
                          href=spec.get("signed_scan_url", "#"),
                          target="_blank",
                          style="color: #007bff;"),
                        style="margin-bottom: 0.5rem;"
                    ),
                    cls="card",
                    style="background: #d4edda; border-left: 4px solid #28a745; padding: 0.75rem; margin-bottom: 1rem;"
                ) if spec.get("signed_scan_url") else None,
                # Upload form (separate form from main form due to enctype)
                P(
                    "Загрузите скан подписанной спецификации (PDF, JPG, PNG, до 10 МБ).",
                    style="margin-bottom: 0.75rem; color: #666;"
                ) if not spec.get("signed_scan_url") else P(
                    "Вы можете загрузить новый скан для замены текущего.",
                    style="margin-bottom: 0.75rem; color: #666;"
                ),
                Form(
                    Input(type="file", name="signed_scan", id="signed_scan",
                          accept=".pdf,.jpg,.jpeg,.png",
                          style="margin-bottom: 0.75rem;"),
                    Button("📤 Загрузить скан", type="submit",
                           style="background: #6f42c1; border-color: #6f42c1;"),
                    action=f"/spec-control/{spec_id}/upload-signed",
                    method="POST",
                    enctype="multipart/form-data"
                ),
                # Feature #72: Confirm Signature button (visible when approved + has signed scan)
                Div(
                    Hr(style="margin: 1rem 0;"),
                    P(
                        "📋 Скан загружен. Подтвердите подпись для создания сделки.",
                        style="margin-bottom: 0.75rem; color: #155724; font-weight: 500;"
                    ),
                    Form(
                        Button("✅ Подтвердить подпись и создать сделку", type="submit",
                               style="background: #28a745; border-color: #28a745; width: 100%;"),
                        action=f"/spec-control/{spec_id}/confirm-signature",
                        method="POST"
                    ),
                    style="margin-top: 1rem;"
                ) if status == "approved" and spec.get("signed_scan_url") else None,
                # Info for already signed specs
                Div(
                    Hr(style="margin: 1rem 0;"),
                    P(
                        "✅ Спецификация подписана. Сделка создана.",
                        style="margin-bottom: 0; color: #155724; font-weight: 500;"
                    ),
                    style="margin-top: 1rem;"
                ) if status == "signed" else None,
                cls="card",
                style="margin-bottom: 1.5rem; background: #f8f9fa;"
            ) if status in ["approved", "signed"] else None,

            # Action buttons
            Div(
                Button("💾 Сохранить", type="submit", name="action", value="save",
                       style="background: #28a745; border-color: #28a745;",
                       disabled=not is_editable) if is_editable else None,
                Button("📤 Отправить на проверку", type="submit", name="action", value="submit_review",
                       style="background: #007bff; border-color: #007bff; margin-left: 1rem;",
                       disabled=not is_editable) if is_editable and status == "draft" else None,
                Button("✅ Утвердить", type="submit", name="action", value="approve",
                       style="background: #28a745; border-color: #28a745; margin-left: 1rem;",
                       disabled=not is_editable) if is_editable and status == "pending_review" else None,
                # Feature #70: PDF Preview button
                A("📄 Предпросмотр PDF", href=f"/spec-control/{spec_id}/preview-pdf",
                  target="_blank", role="button",
                  style="background: #17a2b8; border-color: #17a2b8; margin-left: 1rem; text-decoration: none;"),
                A("← Назад к спецификациям", href="/spec-control", role="button",
                  style="background: #6c757d; border-color: #6c757d; margin-left: 1rem;"),
                style="margin-top: 1rem;"
            ),

            action=f"/spec-control/{spec_id}",
            method="POST"
        ),

        # Transition history (Feature #88) - uses quote_id from the spec
        workflow_transition_history(quote_id) if quote_id else None,

        session=session
    )


@rt("/spec-control/{spec_id}")
def post(session, spec_id: str, action: str = "save", **kwargs):
    """
    Save specification changes or change status.

    Feature #69: Specification data entry form (save/update POST handler)

    Actions:
    - save: Save current data
    - submit_review: Save and change status to pending_review
    - approve: Save and change status to approved
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify spec exists and belongs to org
    spec_result = supabase.table("specifications") \
        .select("id, status, quote_id") \
        .eq("id", spec_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not spec_result.data:
        return RedirectResponse("/spec-control", status_code=303)

    spec = spec_result.data[0]
    current_status = spec.get("status", "draft")

    # Check if editable
    if current_status not in ["draft", "pending_review"]:
        return RedirectResponse(f"/spec-control/{spec_id}", status_code=303)

    # Helper for safe numeric conversion
    def safe_decimal(val, default=None):
        try:
            return float(val) if val else default
        except:
            return default

    def safe_int(val, default=None):
        try:
            return int(val) if val else default
        except:
            return default

    # Determine new status based on action
    new_status = current_status
    if action == "submit_review" and current_status == "draft":
        new_status = "pending_review"
    elif action == "approve" and current_status == "pending_review":
        new_status = "approved"

    # Build update data
    update_data = {
        "quote_version_id": kwargs.get("quote_version_id") or None,
        "specification_number": kwargs.get("specification_number") or None,
        "proposal_idn": kwargs.get("proposal_idn") or None,
        "item_ind_sku": kwargs.get("item_ind_sku") or None,
        "sign_date": kwargs.get("sign_date") or None,
        "validity_period": kwargs.get("validity_period") or None,
        "specification_currency": kwargs.get("specification_currency") or "USD",
        "exchange_rate_to_ruble": safe_decimal(kwargs.get("exchange_rate_to_ruble")),
        "client_payment_term_after_upd": safe_int(kwargs.get("client_payment_term_after_upd")),
        "client_payment_terms": kwargs.get("client_payment_terms") or None,
        "cargo_pickup_country": kwargs.get("cargo_pickup_country") or None,
        "readiness_period": kwargs.get("readiness_period") or None,
        "goods_shipment_country": kwargs.get("goods_shipment_country") or None,
        "delivery_city_russia": kwargs.get("delivery_city_russia") or None,
        "cargo_type": kwargs.get("cargo_type") or None,
        "logistics_period": kwargs.get("logistics_period") or None,
        "our_legal_entity": kwargs.get("our_legal_entity") or None,
        "client_legal_entity": kwargs.get("client_legal_entity") or None,
        "supplier_payment_country": kwargs.get("supplier_payment_country") or None,
        "status": new_status,
    }

    # Update specification
    supabase.table("specifications") \
        .update(update_data) \
        .eq("id", spec_id) \
        .execute()

    return RedirectResponse(f"/spec-control/{spec_id}", status_code=303)


# ============================================================================
# Feature #70: Specification PDF Preview
# ============================================================================

@rt("/spec-control/{spec_id}/preview-pdf")
def get(session, spec_id: str):
    """
    Preview/download specification PDF.

    Feature #70: Preview PDF спецификации

    Generates PDF using all 18 specification fields from the specifications table.
    Returns PDF for download or viewing in browser.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check role access
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    try:
        # Generate PDF using enhanced specification export function
        pdf_bytes = generate_spec_pdf_from_spec_id(spec_id, org_id)

        # Get spec number for filename
        supabase = get_supabase()
        spec_result = supabase.table("specifications") \
            .select("specification_number, proposal_idn") \
            .eq("id", spec_id) \
            .eq("organization_id", org_id) \
            .execute()

        spec_number = "spec"
        if spec_result.data:
            spec_number = spec_result.data[0].get("specification_number") or spec_result.data[0].get("proposal_idn") or "spec"

        # Clean filename for safe characters
        safe_spec_number = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(spec_number))

        # Return as file download (or inline view)
        from starlette.responses import Response
        filename = f"specification_{safe_spec_number}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                # Use "inline" for browser preview, "attachment" for download
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )

    except ValueError as e:
        return page_layout("Ошибка",
            H1("Ошибка генерации PDF"),
            Div(
                f"Не удалось сгенерировать PDF: {str(e)}",
                cls="card",
                style="background: #fee2e2; border-left: 4px solid #dc2626;"
            ),
            A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
            session=session
        )

    except Exception as e:
        print(f"Error generating specification PDF: {e}")
        return page_layout("Ошибка",
            H1("Ошибка генерации PDF"),
            Div(
                f"Произошла ошибка при генерации PDF. Пожалуйста, попробуйте позже.",
                cls="card",
                style="background: #fee2e2; border-left: 4px solid #dc2626;"
            ),
            P(f"Техническая информация: {str(e)}", style="font-size: 0.8rem; color: #666;"),
            A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
            session=session
        )


# ============================================================================
# Feature #71: Upload signed specification scan
# ============================================================================

@rt("/spec-control/{spec_id}/upload-signed")
async def post(session, spec_id: str, request):
    """
    Upload signed specification scan.

    Feature #71: Загрузка подписанного скана

    Accepts PDF, JPG, PNG files up to 10MB.
    Stores in Supabase Storage bucket 'specifications'.
    Updates specifications.signed_scan_url with public URL.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Verify specification exists and belongs to org
    spec_result = supabase.table("specifications") \
        .select("id, status, specification_number, quote_id") \
        .eq("id", spec_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not spec_result.data:
        return RedirectResponse("/spec-control", status_code=303)

    spec = spec_result.data[0]
    status = spec.get("status", "draft")

    # Only allow upload for approved specifications
    if status not in ["approved", "signed"]:
        return page_layout("Ошибка загрузки",
            H1("Ошибка загрузки"),
            Div(
                "Загрузка скана доступна только для утверждённых спецификаций.",
                cls="card",
                style="background: #fee2e2; border-left: 4px solid #dc2626;"
            ),
            A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
            session=session
        )

    try:
        # Get the uploaded file from form data
        form = await request.form()
        signed_scan = form.get("signed_scan")

        if not signed_scan or not signed_scan.filename:
            return page_layout("Ошибка загрузки",
                H1("Файл не выбран"),
                Div(
                    "Пожалуйста, выберите файл для загрузки.",
                    cls="card",
                    style="background: #fee2e2; border-left: 4px solid #dc2626;"
                ),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Validate file type
        filename = signed_scan.filename
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        file_ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if file_ext not in allowed_extensions:
            return page_layout("Ошибка загрузки",
                H1("Неподдерживаемый формат"),
                Div(
                    f"Поддерживаемые форматы: PDF, JPG, PNG. Вы загрузили: {file_ext}",
                    cls="card",
                    style="background: #fee2e2; border-left: 4px solid #dc2626;"
                ),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Read file content
        file_content = await signed_scan.read()

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_content) > max_size:
            return page_layout("Ошибка загрузки",
                H1("Файл слишком большой"),
                Div(
                    f"Максимальный размер файла: 10 МБ. Ваш файл: {len(file_content) / 1024 / 1024:.1f} МБ",
                    cls="card",
                    style="background: #fee2e2; border-left: 4px solid #dc2626;"
                ),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Determine content type
        content_type_map = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }
        content_type = content_type_map.get(file_ext, 'application/octet-stream')

        # Generate storage path: org_id/spec_id/signed_scan_timestamp.ext
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        spec_number = spec.get("specification_number") or spec_id[:8]
        safe_spec_number = "".join(c for c in spec_number if c.isalnum() or c in "-_")
        storage_path = f"{org_id}/{spec_id}/signed_{safe_spec_number}_{timestamp}{file_ext}"

        # Upload to Supabase Storage (bucket: specifications)
        # Note: Bucket must be created manually in Supabase dashboard first
        bucket_name = "specifications"

        try:
            # Upload the file
            upload_result = supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": content_type, "upsert": "true"}
            )

            # Get public URL
            public_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)

            # Update specification with signed_scan_url
            supabase.table("specifications") \
                .update({"signed_scan_url": public_url, "updated_at": datetime.now().isoformat()}) \
                .eq("id", spec_id) \
                .execute()

            print(f"Signed scan uploaded successfully: {public_url}")

            # Redirect back to spec page with success
            return RedirectResponse(f"/spec-control/{spec_id}?upload_success=1", status_code=303)

        except Exception as storage_error:
            print(f"Storage upload error: {storage_error}")

            # If bucket doesn't exist, provide helpful message
            error_msg = str(storage_error)
            if "Bucket not found" in error_msg or "bucket" in error_msg.lower():
                return page_layout("Ошибка хранилища",
                    H1("Хранилище не настроено"),
                    Div(
                        "Хранилище для спецификаций не настроено. ",
                        "Необходимо создать bucket 'specifications' в Supabase Storage.",
                        cls="card",
                        style="background: #fef3c7; border-left: 4px solid #f59e0b;"
                    ),
                    P("Инструкция: Supabase Dashboard → Storage → New Bucket → Name: specifications, Public: Yes",
                      style="font-size: 0.9rem; color: #666; margin-top: 1rem;"),
                    A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                    session=session
                )

            raise storage_error

    except Exception as e:
        print(f"Error uploading signed scan: {e}")
        import traceback
        traceback.print_exc()

        return page_layout("Ошибка загрузки",
            H1("Ошибка загрузки файла"),
            Div(
                "Произошла ошибка при загрузке файла. Пожалуйста, попробуйте позже.",
                cls="card",
                style="background: #fee2e2; border-left: 4px solid #dc2626;"
            ),
            P(f"Техническая информация: {str(e)}", style="font-size: 0.8rem; color: #666;"),
            A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
            session=session
        )


# ============================================================================
# Feature #72: Confirm Signature and Create Deal
# ============================================================================

@rt("/spec-control/{spec_id}/confirm-signature")
def post(session, spec_id: str):
    """
    Confirm signature on specification and create a deal.

    Feature #72: Кнопка подтверждения подписи

    This endpoint:
    1. Validates spec is in 'approved' status and has signed_scan_url
    2. Updates specification status to 'signed'
    3. Creates a new deal record from the specification data
    4. Updates quote workflow status to 'deal_signed'
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check role (spec_controller or admin)
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    try:
        # Fetch specification with all needed data
        spec_result = supabase.table("specifications") \
            .select("id, quote_id, organization_id, status, signed_scan_url, specification_number, sign_date, specification_currency, exchange_rate_to_ruble") \
            .eq("id", spec_id) \
            .eq("organization_id", org_id) \
            .execute()

        if not spec_result.data:
            return page_layout("Ошибка",
                H1("Спецификация не найдена"),
                Div("Спецификация не найдена или у вас нет доступа.", cls="card", style="background: #fee2e2;"),
                A("← Назад к спецификациям", href="/spec-control"),
                session=session
            )

        spec = spec_result.data[0]
        current_status = spec.get("status", "")
        signed_scan_url = spec.get("signed_scan_url", "")

        # Validate status is 'approved'
        if current_status != "approved":
            return page_layout("Ошибка статуса",
                H1("Неверный статус"),
                Div(
                    f"Подтверждение подписи возможно только для спецификаций в статусе 'Утверждена'. Текущий статус: {current_status}",
                    cls="card", style="background: #fee2e2; border-left: 4px solid #dc2626;"
                ),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Validate signed scan exists
        if not signed_scan_url:
            return page_layout("Ошибка",
                H1("Скан не загружен"),
                Div(
                    "Для подтверждения подписи необходимо сначала загрузить скан подписанной спецификации.",
                    cls="card", style="background: #fef3c7; border-left: 4px solid #f59e0b;"
                ),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Check if deal already exists for this spec
        existing_deal = supabase.table("deals") \
            .select("id, deal_number") \
            .eq("specification_id", spec_id) \
            .execute()

        if existing_deal.data:
            return page_layout("Сделка уже существует",
                H1("Сделка уже создана"),
                Div(
                    f"Для этой спецификации уже создана сделка: {existing_deal.data[0].get('deal_number', 'N/A')}",
                    cls="card", style="background: #d4edda; border-left: 4px solid #28a745;"
                ),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Get quote data for total amount calculation
        quote_id = spec.get("quote_id")
        quote_result = supabase.table("quotes") \
            .select("id, client_name, calculated_total_client_price") \
            .eq("id", quote_id) \
            .execute()

        if not quote_result.data:
            return page_layout("Ошибка",
                H1("КП не найдено"),
                Div("Связанное КП не найдено.", cls="card", style="background: #fee2e2;"),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        quote = quote_result.data[0]
        total_amount = quote.get("calculated_total_client_price") or 0

        # Generate deal number using SQL function if available, otherwise generate manually
        try:
            deal_number_result = supabase.rpc("generate_deal_number", {"org_id": org_id}).execute()
            deal_number = deal_number_result.data if deal_number_result.data else None
        except Exception:
            deal_number = None

        # Fallback: generate deal number manually
        if not deal_number:
            from datetime import datetime
            year = datetime.now().year

            # Count existing deals for this org in current year
            count_result = supabase.table("deals") \
                .select("id", count="exact") \
                .eq("organization_id", org_id) \
                .execute()

            seq_num = (count_result.count or 0) + 1
            deal_number = f"DEAL-{year}-{seq_num:04d}"

        # Get sign date (from spec or use today)
        from datetime import date
        sign_date = spec.get("sign_date") or date.today().isoformat()
        currency = spec.get("specification_currency") or "RUB"

        # Step 1: Update specification status to 'signed'
        supabase.table("specifications") \
            .update({"status": "signed"}) \
            .eq("id", spec_id) \
            .execute()

        # Step 2: Create deal record
        deal_data = {
            "specification_id": spec_id,
            "quote_id": quote_id,
            "organization_id": org_id,
            "deal_number": deal_number,
            "signed_at": sign_date,
            "total_amount": float(total_amount) if total_amount else 0.0,
            "currency": currency,
            "status": "active",
            "created_by": user_id,
        }

        deal_result = supabase.table("deals") \
            .insert(deal_data) \
            .execute()

        if not deal_result.data:
            # Rollback spec status
            supabase.table("specifications") \
                .update({"status": "approved"}) \
                .eq("id", spec_id) \
                .execute()
            raise Exception("Failed to create deal record")

        deal_id = deal_result.data[0]["id"]

        # Step 3: Update quote workflow status to deal_signed (if workflow service available)
        try:
            from services import transition_quote_status, WorkflowStatus
            # Try to transition quote to deal_signed status
            transition_result = transition_quote_status(
                quote_id=quote_id,
                to_status=WorkflowStatus.DEAL_SIGNED,
                actor_id=user_id,
                actor_roles=get_user_roles_from_session(session),
                comment=f"Сделка {deal_number} создана из спецификации",
                supabase=supabase
            )
            print(f"Quote workflow transition result: {transition_result}")
        except Exception as e:
            # Workflow transition is optional - log but don't fail
            print(f"Note: Could not transition quote workflow: {e}")

        print(f"Deal created successfully: {deal_number} (ID: {deal_id})")

        # Show success page
        return page_layout("Сделка создана",
            H1("✅ Сделка успешно создана"),
            Div(
                H3(f"Номер сделки: {deal_number}"),
                P(f"Клиент: {quote.get('client_name', 'N/A')}"),
                P(f"Сумма: {total_amount:,.2f} {currency}"),
                P(f"Дата подписания: {sign_date}"),
                cls="card",
                style="background: #d4edda; border-left: 4px solid #28a745; padding: 1rem;"
            ),
            Div(
                A("→ К спецификации", href=f"/spec-control/{spec_id}", role="button",
                  style="background: #007bff; border-color: #007bff; margin-right: 1rem;"),
                A("← Назад к списку", href="/spec-control", role="button",
                  style="background: #6c757d; border-color: #6c757d;"),
                style="margin-top: 1rem;"
            ),
            session=session
        )

    except Exception as e:
        print(f"Error confirming signature: {e}")
        import traceback
        traceback.print_exc()

        return page_layout("Ошибка",
            H1("Ошибка создания сделки"),
            Div(
                "Произошла ошибка при создании сделки. Пожалуйста, попробуйте позже.",
                cls="card", style="background: #fee2e2; border-left: 4px solid #dc2626;"
            ),
            P(f"Техническая информация: {str(e)}", style="font-size: 0.8rem; color: #666;"),
            A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
            session=session
        )


# ============================================================================
# FINANCE WORKSPACE (Features #77-80)
# ============================================================================

@rt("/finance")
def get(session, status_filter: str = None):
    """
    Finance workspace - shows active deals and plan-fact management
    for finance role.

    Feature #77: Basic finance page structure
    Feature #78: List of active deals (included)

    This page shows:
    1. Deal statistics (active, completed, total amounts)
    2. Active deals list with navigation to deal details
    3. Quick summary of amounts
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
                .execute()
            stats[status] = count_result.count or 0

        stats["total"] = stats["active"] + stats["completed"] + stats["cancelled"]

        # Sum amounts for active deals
        active_result = supabase.table("deals").select("total_amount") \
            .eq("organization_id", org_id) \
            .eq("status", "active") \
            .execute()
        if active_result.data:
            stats["active_amount"] = sum(float(d.get("total_amount", 0) or 0) for d in active_result.data)

        # Sum amounts for completed deals
        completed_result = supabase.table("deals").select("total_amount") \
            .eq("organization_id", org_id) \
            .eq("status", "completed") \
            .execute()
        if completed_result.data:
            stats["completed_amount"] = sum(float(d.get("total_amount", 0) or 0) for d in completed_result.data)

    except Exception as e:
        print(f"Error getting deal stats: {e}")

    # Get deals with details based on filter
    target_status = status_filter if status_filter and status_filter != "all" else None

    try:
        query = supabase.table("deals").select(
            "id, deal_number, signed_at, total_amount, currency, status, created_at, "
            "specifications(id, specification_number, proposal_idn), "
            "quotes(id, idn_quote, customer_name, customers(name, company_name))"
        ).eq("organization_id", org_id)

        if target_status:
            query = query.eq("status", target_status)

        deals_result = query.order("signed_at", desc=True).limit(100).execute()
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
            "active": ("В работе", "bg-green-200 text-green-800"),
            "completed": ("Завершена", "bg-blue-200 text-blue-800"),
            "cancelled": ("Отменена", "bg-red-200 text-red-800"),
        }
        label, classes = status_map.get(status, (status, "bg-gray-200 text-gray-800"))
        return Span(label, cls=f"px-2 py-1 rounded text-sm {classes}")

    # Deal row helper
    def deal_row(deal):
        spec = deal.get("specifications", {}) or {}
        quote = deal.get("quotes", {}) or {}
        customer = quote.get("customers", {}) or {}
        customer_name = customer.get("company_name") or customer.get("name") or quote.get("customer_name", "Неизвестно")

        # Format amount
        amount = float(deal.get("total_amount", 0) or 0)
        currency = deal.get("currency", "RUB")
        amount_str = f"{amount:,.2f} {currency}"

        # Format date
        signed_at = deal.get("signed_at", "")[:10] if deal.get("signed_at") else "-"

        return Tr(
            Td(A(deal.get("deal_number", "-"), href=f"/finance/{deal['id']}")),
            Td(spec.get("specification_number", "-") or spec.get("proposal_idn", "-")),
            Td(customer_name),
            Td(amount_str, style="text-align: right; font-weight: 500;"),
            Td(signed_at),
            Td(deal_status_badge(deal.get("status", "active"))),
            Td(
                A("Подробнее", href=f"/finance/{deal['id']}", role="button",
                  style="background: #3b82f6; border-color: #3b82f6; font-size: 0.875rem; padding: 0.25rem 0.5rem;"),
            ),
        )

    # Build deals table
    def deals_table(deals_list, title, status_color):
        if not deals_list:
            return Div(
                H3(f"{title} (0)", style=f"color: {status_color};"),
                P("Нет сделок", style="color: #666; font-style: italic;"),
                style="margin-bottom: 2rem;"
            )

        return Div(
            H3(f"{title} ({len(deals_list)})", style=f"color: {status_color};"),
            Table(
                Thead(
                    Tr(
                        Th("№ Сделки"),
                        Th("№ Спецификации"),
                        Th("Клиент"),
                        Th("Сумма", style="text-align: right;"),
                        Th("Дата подписания"),
                        Th("Статус"),
                        Th("Действия"),
                    )
                ),
                Tbody(*[deal_row(d) for d in deals_list]),
                cls="striped"
            ),
            style="margin-bottom: 2rem;"
        )

    # Build filter buttons
    filter_buttons = Div(
        A("Все", href="/finance", role="button",
          cls="secondary" if status_filter and status_filter != "all" else "",
          style="margin-right: 0.5rem;"),
        A("В работе", href="/finance?status_filter=active", role="button",
          cls="secondary" if status_filter != "active" else "",
          style="margin-right: 0.5rem; background: #10b981;" if status_filter == "active" else "margin-right: 0.5rem;"),
        A("Завершённые", href="/finance?status_filter=completed", role="button",
          cls="secondary" if status_filter != "completed" else "",
          style="margin-right: 0.5rem; background: #3b82f6;" if status_filter == "completed" else "margin-right: 0.5rem;"),
        A("Отменённые", href="/finance?status_filter=cancelled", role="button",
          cls="secondary" if status_filter != "cancelled" else "",
          style="background: #ef4444;" if status_filter == "cancelled" else ""),
        style="margin-bottom: 1.5rem;"
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

    return page_layout("Финансы",
        H1("Финансовый менеджер"),

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
        deals_section,

        session=session
    )


# ============================================================================
# FINANCE DEAL DETAIL PAGE (Feature #79)
# ============================================================================

@rt("/finance/{deal_id}")
def get(session, deal_id: str):
    """
    Finance deal detail page - shows deal info and plan-fact table.

    Feature #79: Таблица план-факт по сделке

    This page shows:
    1. Deal information (number, customer, specification, dates)
    2. Plan-fact table with all payment items
    3. Summary of planned vs actual amounts
    4. Variance tracking
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

    # Fetch deal with related data
    try:
        deal_result = supabase.table("deals").select(
            "id, deal_number, signed_at, total_amount, currency, status, created_at, "
            "specifications(id, specification_number, proposal_idn, sign_date, validity_period, "
            "  specification_currency, exchange_rate_to_ruble, client_payment_terms, "
            "  our_legal_entity, client_legal_entity), "
            "quotes(id, idn_quote, customer_name, customers(name, company_name))"
        ).eq("id", deal_id).eq("organization_id", org_id).single().execute()

        deal = deal_result.data
        if not deal:
            return page_layout("Ошибка",
                H1("Сделка не найдена"),
                P(f"Сделка с ID {deal_id} не найдена или у вас нет доступа."),
                A("← Назад к списку сделок", href="/finance", role="button"),
                session=session
            )
    except Exception as e:
        print(f"Error fetching deal: {e}")
        return page_layout("Ошибка",
            H1("Ошибка загрузки"),
            P(f"Не удалось загрузить сделку: {str(e)}"),
            A("← Назад к списку сделок", href="/finance", role="button"),
            session=session
        )

    # Fetch plan_fact_items for this deal
    try:
        plan_fact_result = supabase.table("plan_fact_items").select(
            "id, description, planned_amount, planned_currency, planned_date, "
            "actual_amount, actual_currency, actual_date, actual_exchange_rate, "
            "variance_amount, payment_document, notes, created_at, "
            "plan_fact_categories(id, code, name, is_income, sort_order)"
        ).eq("deal_id", deal_id).order("planned_date").execute()

        plan_fact_items = plan_fact_result.data or []
    except Exception as e:
        print(f"Error fetching plan_fact_items: {e}")
        plan_fact_items = []

    # Fetch all categories for reference
    try:
        categories_result = supabase.table("plan_fact_categories").select(
            "id, code, name, is_income, sort_order"
        ).order("sort_order").execute()
        categories = categories_result.data or []
    except Exception as e:
        print(f"Error fetching categories: {e}")
        categories = []

    # Extract deal info
    spec = deal.get("specifications", {}) or {}
    quote = deal.get("quotes", {}) or {}
    customer = quote.get("customers", {}) or {}
    customer_name = customer.get("company_name") or customer.get("name") or quote.get("customer_name", "Неизвестно")

    deal_number = deal.get("deal_number", "-")
    spec_number = spec.get("specification_number", "-") or spec.get("proposal_idn", "-")
    deal_amount = float(deal.get("total_amount", 0) or 0)
    deal_currency = deal.get("currency", "RUB")
    signed_at = deal.get("signed_at", "")[:10] if deal.get("signed_at") else "-"

    # Status badge
    status_map = {
        "active": ("В работе", "bg-green-200 text-green-800", "#10b981"),
        "completed": ("Завершена", "bg-blue-200 text-blue-800", "#3b82f6"),
        "cancelled": ("Отменена", "bg-red-200 text-red-800", "#ef4444"),
    }
    status = deal.get("status", "active")
    status_label, status_class, status_color = status_map.get(status, (status, "bg-gray-200 text-gray-800", "#6b7280"))
    status_badge = Span(status_label, cls=f"px-2 py-1 rounded text-sm {status_class}")

    # Calculate plan-fact summary
    total_planned_income = sum(
        float(item.get("planned_amount", 0) or 0)
        for item in plan_fact_items
        if item.get("plan_fact_categories", {}).get("is_income", False)
    )
    total_planned_expense = sum(
        float(item.get("planned_amount", 0) or 0)
        for item in plan_fact_items
        if not item.get("plan_fact_categories", {}).get("is_income", True)
    )
    total_actual_income = sum(
        float(item.get("actual_amount", 0) or 0)
        for item in plan_fact_items
        if item.get("plan_fact_categories", {}).get("is_income", False) and item.get("actual_amount") is not None
    )
    total_actual_expense = sum(
        float(item.get("actual_amount", 0) or 0)
        for item in plan_fact_items
        if not item.get("plan_fact_categories", {}).get("is_income", True) and item.get("actual_amount") is not None
    )
    total_variance = sum(
        float(item.get("variance_amount", 0) or 0)
        for item in plan_fact_items
        if item.get("variance_amount") is not None
    )

    # Count paid vs unpaid items
    paid_count = sum(1 for item in plan_fact_items if item.get("actual_amount") is not None)
    unpaid_count = len(plan_fact_items) - paid_count

    # Build plan-fact table row
    def plan_fact_row(item):
        category = item.get("plan_fact_categories", {}) or {}
        is_income = category.get("is_income", False)
        category_name = category.get("name", "Прочее")

        # Format amounts
        planned_amount = float(item.get("planned_amount", 0) or 0)
        planned_currency = item.get("planned_currency", "RUB")
        planned_str = f"{planned_amount:,.2f} {planned_currency}"

        actual_amount = item.get("actual_amount")
        actual_currency = item.get("actual_currency", "RUB")
        if actual_amount is not None:
            actual_str = f"{float(actual_amount):,.2f} {actual_currency}"
        else:
            actual_str = "—"

        variance = item.get("variance_amount")
        if variance is not None:
            variance_val = float(variance)
            if variance_val > 0:
                variance_str = f"+{variance_val:,.2f}"
                variance_color = "#ef4444" if not is_income else "#10b981"  # Red for overspend, green for extra income
            elif variance_val < 0:
                variance_str = f"{variance_val:,.2f}"
                variance_color = "#10b981" if not is_income else "#ef4444"  # Green for underspend, red for less income
            else:
                variance_str = "0.00"
                variance_color = "#6b7280"
        else:
            variance_str = "—"
            variance_color = "#6b7280"

        # Format dates
        planned_date = item.get("planned_date", "")[:10] if item.get("planned_date") else "-"
        actual_date = item.get("actual_date", "")[:10] if item.get("actual_date") else "-"

        # Payment status
        if actual_amount is not None:
            payment_status = Span("✓ Оплачено", style="color: #10b981; font-weight: 500;")
        else:
            payment_status = Span("○ Ожидает", style="color: #f59e0b;")

        # Category badge color
        category_color = "#10b981" if is_income else "#6366f1"

        return Tr(
            Td(
                Span(category_name, style=f"color: {category_color}; font-weight: 500;"),
                Br(),
                Small(item.get("description", "-") or "-", style="color: #666;")
            ),
            Td(planned_date),
            Td(planned_str, style="text-align: right; font-weight: 500;"),
            Td(actual_date if actual_amount is not None else "-"),
            Td(actual_str, style="text-align: right;"),
            Td(variance_str, style=f"text-align: right; color: {variance_color}; font-weight: 500;"),
            Td(payment_status),
            Td(
                A("Редакт.", href=f"/finance/{deal_id}/plan-fact/{item['id']}", role="button",
                  style="font-size: 0.75rem; padding: 0.2rem 0.5rem; background: #6b7280;") if actual_amount is None else "",
            ),
        )

    # Build plan-fact table
    if plan_fact_items:
        plan_fact_table = Table(
            Thead(
                Tr(
                    Th("Категория / Описание"),
                    Th("План. дата"),
                    Th("План. сумма", style="text-align: right;"),
                    Th("Факт. дата"),
                    Th("Факт. сумма", style="text-align: right;"),
                    Th("Отклонение", style="text-align: right;"),
                    Th("Статус"),
                    Th(""),
                )
            ),
            Tbody(*[plan_fact_row(item) for item in plan_fact_items]),
            cls="striped"
        )
    else:
        plan_fact_table = Div(
            P("Плановые платежи ещё не созданы.", style="color: #666; font-style: italic; margin-bottom: 1rem;"),
            Div(
                A("🔄 Сгенерировать из КП", href=f"/finance/{deal_id}/generate-plan-fact", role="button",
                  style="background: #3b82f6; margin-right: 0.5rem;"),
                A("+ Добавить вручную", href=f"/finance/{deal_id}/plan-fact/new", role="button",
                  style="background: #10b981;"),
            ),
            style="text-align: center; padding: 2rem; background: #f9fafb; border-radius: 8px;"
        )

    return page_layout(f"Сделка {deal_number}",
        # Header with back button
        Div(
            A("← Назад к списку сделок", href="/finance", style="color: #6b7280; text-decoration: none;"),
            style="margin-bottom: 1rem;"
        ),

        # Deal header
        Div(
            H1(f"Сделка {deal_number}", style="margin-bottom: 0.5rem;"),
            Div(status_badge, style="margin-bottom: 1rem;"),
            style="margin-bottom: 1.5rem;"
        ),

        # Deal info cards
        Div(
            # Left column - Deal info
            Div(
                H3("Информация о сделке", style="margin-top: 0;"),
                Table(
                    Tr(Td(Strong("Номер сделки:"), style="width: 180px;"), Td(deal_number)),
                    Tr(Td(Strong("Спецификация:")), Td(spec_number)),
                    Tr(Td(Strong("Клиент:")), Td(customer_name)),
                    Tr(Td(Strong("Сумма сделки:")), Td(f"{deal_amount:,.2f} {deal_currency}", style="font-weight: 600;")),
                    Tr(Td(Strong("Дата подписания:")), Td(signed_at)),
                    Tr(Td(Strong("Условия оплаты:")), Td(spec.get("client_payment_terms", "-") or "-")),
                    Tr(Td(Strong("Наше юр. лицо:")), Td(spec.get("our_legal_entity", "-") or "-")),
                    Tr(Td(Strong("Юр. лицо клиента:")), Td(spec.get("client_legal_entity", "-") or "-")),
                ),
                style="flex: 1; padding: 1rem; background: #f9fafb; border-radius: 8px; margin-right: 1rem;"
            ),
            # Right column - Plan-fact summary
            Div(
                H3("Сводка план-факт", style="margin-top: 0;"),
                Table(
                    Tr(
                        Td(Strong("Плановые поступления:"), style="width: 180px;"),
                        Td(f"{total_planned_income:,.2f} ₽", style="color: #10b981; font-weight: 500; text-align: right;")
                    ),
                    Tr(
                        Td(Strong("Фактические поступления:")),
                        Td(f"{total_actual_income:,.2f} ₽", style="text-align: right;")
                    ),
                    Tr(
                        Td(Strong("Плановые расходы:")),
                        Td(f"{total_planned_expense:,.2f} ₽", style="color: #6366f1; font-weight: 500; text-align: right;")
                    ),
                    Tr(
                        Td(Strong("Фактические расходы:")),
                        Td(f"{total_actual_expense:,.2f} ₽", style="text-align: right;")
                    ),
                    Tr(
                        Td(Strong("Плановая маржа:")),
                        Td(f"{total_planned_income - total_planned_expense:,.2f} ₽", style="font-weight: 600; text-align: right;")
                    ),
                    Tr(
                        Td(Strong("Общее отклонение:")),
                        Td(f"{total_variance:+,.2f} ₽" if total_variance != 0 else "0.00 ₽",
                           style=f"font-weight: 600; text-align: right; color: {'#ef4444' if total_variance > 0 else '#10b981' if total_variance < 0 else '#6b7280'};")
                    ),
                ),
                Div(
                    Span(f"Оплачено: {paid_count}", style="color: #10b981; margin-right: 1rem;"),
                    Span(f"Ожидает: {unpaid_count}", style="color: #f59e0b;"),
                    style="margin-top: 1rem; font-size: 0.875rem;"
                ),
                style="flex: 1; padding: 1rem; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0;"
            ),
            style="display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 2rem;"
        ),

        # Plan-fact table section
        Div(
            Div(
                H2("План-факт платежей", style="display: inline-block; margin-right: 1rem;"),
                Div(
                    A("+ Добавить платёж", href=f"/finance/{deal_id}/plan-fact/new", role="button",
                      style="background: #10b981; font-size: 0.875rem; margin-right: 0.5rem;"),
                    A("🔄 Перегенерировать", href=f"/finance/{deal_id}/generate-plan-fact", role="button",
                      style="background: #6b7280; font-size: 0.875rem;"),
                ) if plan_fact_items else "",
                style="display: flex; align-items: center; margin-bottom: 1rem;"
            ),
            plan_fact_table,
        ),

        # Transition history (Feature #88) - uses quote_id from the deal
        workflow_transition_history(quote.get("id")) if quote.get("id") else None,

        session=session
    )


# ============================================================================
# AUTO-GENERATE PLAN-FACT ITEMS (Feature #82)
# ============================================================================

@rt("/finance/{deal_id}/generate-plan-fact")
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
            A("← Назад к сделке", href=f"/finance/{deal_id}", role="button"),
            session=session
        )

    deal_info = preview.get('deal_info', {})
    planned_items = preview.get('planned_items', [])
    totals = preview.get('totals', {})
    existing_items = preview.get('existing_items', 0)

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
            Strong("⚠️ Внимание: "),
            f"Для этой сделки уже существуют {existing_items} плановых платежей. ",
            "Генерация заменит все существующие записи.",
            style="background: #fef3c7; border: 1px solid #f59e0b; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; color: #92400e;"
        )

    return page_layout(f"Генерация план-факта",
        # Header with back button
        Div(
            A(f"← Назад к сделке {deal_info.get('deal_number', '')}", href=f"/finance/{deal_id}", style="color: #6b7280; text-decoration: none;"),
            style="margin-bottom: 1rem;"
        ),

        H1("Автогенерация плановых платежей"),
        P("На основе условий сделки будут созданы следующие плановые платежи:"),

        existing_warning,

        # Source data info
        Div(
            H3("Исходные данные", style="margin-top: 0;"),
            Table(
                Tr(Td(Strong("Сумма сделки:"), style="width: 200px;"), Td(f"{deal_info.get('total_amount', 0):,.2f} {deal_info.get('currency', 'RUB')}")),
                Tr(Td(Strong("Дата подписания:")), Td(deal_info.get('signed_at', '-'))),
                Tr(Td(Strong("Закупка (из КП):")), Td(f"{totals.get('total_purchase', 0):,.2f}")),
                Tr(Td(Strong("Логистика (из КП):")), Td(f"{totals.get('total_logistics', 0):,.2f}")),
                Tr(Td(Strong("Таможня (из КП):")), Td(f"{totals.get('total_customs', 0):,.2f}")),
            ),
            style="background: #f9fafb; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;"
        ),

        # Preview table
        H3("Планируемые платежи"),
        Table(
            Thead(
                Tr(
                    Th("Категория"),
                    Th("Описание"),
                    Th("Сумма", style="text-align: right;"),
                    Th("План. дата"),
                    Th("Тип"),
                )
            ),
            Tbody(*preview_rows),
            Tfoot(
                Tr(
                    Td(Strong("Итого поступлений:"), colspan="2"),
                    Td(Strong(f"{total_income:,.2f}"), style="text-align: right; color: #10b981;"),
                    Td(),
                    Td(),
                ),
                Tr(
                    Td(Strong("Итого расходов:"), colspan="2"),
                    Td(Strong(f"{total_expense:,.2f}"), style="text-align: right; color: #6366f1;"),
                    Td(),
                    Td(),
                ),
                Tr(
                    Td(Strong("Плановая маржа:"), colspan="2"),
                    Td(Strong(f"{planned_margin:,.2f}"), style=f"text-align: right; color: {'#10b981' if planned_margin >= 0 else '#ef4444'};"),
                    Td(),
                    Td(),
                ),
            ),
            cls="striped"
        ) if preview_rows else P("Нет данных для генерации платежей.", style="color: #666; font-style: italic;"),

        # Action buttons
        Div(
            Form(
                Button("✓ Сгенерировать платежи", type="submit", style="background: #10b981; margin-right: 1rem;") if preview_rows else "",
                A("Отмена", href=f"/finance/{deal_id}", role="button", style="background: #6b7280;"),
                method="POST",
                action=f"/finance/{deal_id}/generate-plan-fact",
            ),
            style="margin-top: 1.5rem;"
        ),

        session=session
    )


@rt("/finance/{deal_id}/generate-plan-fact")
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
            A("← Назад к сделке", href=f"/finance/{deal_id}", role="button"),
            session=session
        )


# ============================================================================
# PAYMENT REGISTRATION FORM (Feature #80)
# ============================================================================

@rt("/finance/{deal_id}/plan-fact/{item_id}")
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
                A("← Назад к сделке", href=f"/finance/{deal_id}", role="button"),
                session=session
            )
    except Exception as e:
        print(f"Error fetching plan_fact_item: {e}")
        return page_layout("Ошибка",
            H1("Ошибка загрузки"),
            P(f"Не удалось загрузить запись: {str(e)}"),
            A("← Назад к сделке", href=f"/finance/{deal_id}", role="button"),
            session=session
        )

    # Verify item belongs to the deal
    if str(item.get("deal_id")) != str(deal_id):
        return page_layout("Ошибка",
            H1("Неверный запрос"),
            P("Запись план-факта не относится к указанной сделке."),
            A("← Назад к сделке", href=f"/finance/{deal_id}", role="button"),
            session=session
        )

    # Fetch deal info for header
    try:
        deal_result = supabase.table("deals").select(
            "id, deal_number, organization_id"
        ).eq("id", deal_id).single().execute()

        deal = deal_result.data
        if not deal or str(deal.get("organization_id")) != str(org_id):
            return page_layout("Ошибка",
                H1("Сделка не найдена"),
                P("Сделка не найдена или у вас нет доступа."),
                A("← Назад к финансам", href="/finance", role="button"),
                session=session
            )
    except Exception as e:
        print(f"Error fetching deal: {e}")
        return page_layout("Ошибка",
            H1("Ошибка загрузки"),
            P(f"Не удалось загрузить сделку: {str(e)}"),
            A("← Назад к финансам", href="/finance", role="button"),
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
    status_label = "✓ Оплачено" if is_paid else "○ Ожидает оплаты"
    status_color = "#10b981" if is_paid else "#f59e0b"

    # Category badge
    category_color = "#10b981" if is_income else "#6366f1"
    category_type = "Доход" if is_income else "Расход"

    return page_layout(f"Регистрация платежа — {deal_number}",
        # Header with back button
        Div(
            A(f"← Назад к сделке {deal_number}", href=f"/finance/{deal_id}",
              style="color: #6b7280; text-decoration: none;"),
            style="margin-bottom: 1rem;"
        ),

        # Page header
        H1("Регистрация платежа", style="margin-bottom: 1rem;"),

        # Planned payment info card
        Div(
            H3("Плановые данные", style="margin-top: 0;"),
            Table(
                Tr(
                    Td(Strong("Категория:"), style="width: 180px;"),
                    Td(
                        Span(category_name, style=f"color: {category_color}; font-weight: 600;"),
                        Span(f" ({category_type})", style="color: #666; font-size: 0.875rem;")
                    )
                ),
                Tr(Td(Strong("Описание:")), Td(description or "-")),
                Tr(
                    Td(Strong("Плановая сумма:")),
                    Td(f"{planned_amount:,.2f} {planned_currency}", style="font-weight: 600;")
                ),
                Tr(Td(Strong("Плановая дата:")), Td(planned_date or "-")),
                Tr(
                    Td(Strong("Статус:")),
                    Td(Span(status_label, style=f"color: {status_color}; font-weight: 500;"))
                ),
            ),
            style="padding: 1rem; background: #f9fafb; border-radius: 8px; margin-bottom: 1.5rem;"
        ),

        # Actual payment form
        Form(
            H3("Фактические данные", style="margin-top: 0;"),

            # Hidden fields
            Input(type="hidden", name="deal_id", value=deal_id),
            Input(type="hidden", name="item_id", value=item_id),

            # Actual amount
            Div(
                Label("Фактическая сумма *", fr="actual_amount"),
                Input(
                    type="number",
                    name="actual_amount",
                    id="actual_amount",
                    value=str(actual_amount) if actual_amount is not None else "",
                    step="0.01",
                    min="0",
                    required=True,
                    placeholder=f"Плановая: {planned_amount:,.2f}"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Actual currency and exchange rate (side by side)
            Div(
                Div(
                    Label("Валюта", fr="actual_currency"),
                    Select(
                        Option("RUB - Рубли", value="RUB", selected=(actual_currency == "RUB")),
                        Option("USD - Доллары США", value="USD", selected=(actual_currency == "USD")),
                        Option("EUR - Евро", value="EUR", selected=(actual_currency == "EUR")),
                        Option("CNY - Юани", value="CNY", selected=(actual_currency == "CNY")),
                        name="actual_currency",
                        id="actual_currency"
                    ),
                    style="flex: 1; margin-right: 1rem;"
                ),
                Div(
                    Label("Курс к рублю", fr="actual_exchange_rate"),
                    Input(
                        type="number",
                        name="actual_exchange_rate",
                        id="actual_exchange_rate",
                        value=str(actual_exchange_rate) if actual_exchange_rate else "",
                        step="0.0001",
                        min="0",
                        placeholder="Для валюты, отличной от RUB"
                    ),
                    Small("Оставьте пустым для RUB. Для валют введите курс на дату платежа.",
                          style="display: block; color: #666; margin-top: 0.25rem;"),
                    style="flex: 1;"
                ),
                style="display: flex; flex-wrap: wrap; margin-bottom: 1rem;"
            ),

            # Actual date
            Div(
                Label("Дата платежа *", fr="actual_date"),
                Input(
                    type="date",
                    name="actual_date",
                    id="actual_date",
                    value=actual_date or "",
                    required=True
                ),
                style="margin-bottom: 1rem;"
            ),

            # Payment document
            Div(
                Label("Номер платёжного документа", fr="payment_document"),
                Input(
                    type="text",
                    name="payment_document",
                    id="payment_document",
                    value=payment_document,
                    placeholder="№ п/п, номер счёта и т.д."
                ),
                style="margin-bottom: 1rem;"
            ),

            # Notes
            Div(
                Label("Примечания", fr="notes"),
                Textarea(
                    notes,
                    name="notes",
                    id="notes",
                    rows="3",
                    placeholder="Дополнительная информация о платеже..."
                ),
                style="margin-bottom: 1.5rem;"
            ),

            # Submit buttons
            Div(
                Button("Сохранить платёж", type="submit",
                       style="background: #10b981; margin-right: 0.5rem;"),
                A("Отмена", href=f"/finance/{deal_id}", role="button",
                  style="background: #6b7280;"),
                style="display: flex; gap: 0.5rem;"
            ),

            action=f"/finance/{deal_id}/plan-fact/{item_id}",
            method="POST",
            style="padding: 1rem; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0;"
        ),

        # Help text
        Div(
            H4("Подсказка", style="margin-top: 1.5rem; margin-bottom: 0.5rem;"),
            P("При сохранении система автоматически рассчитает отклонение от плана.",
              style="color: #666; font-size: 0.875rem; margin: 0;"),
            P("Отклонение = Фактическая сумма (в рублях) - Плановая сумма.",
              style="color: #666; font-size: 0.875rem; margin: 0;"),
            style="padding: 0.75rem; background: #fef3c7; border-radius: 6px; border: 1px solid #fcd34d;"
        ),

        session=session
    )


@rt("/finance/{deal_id}/plan-fact/{item_id}")
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
            A("← Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", role="button"),
            session=session
        )

    # Validate the item exists and belongs to the deal in user's org
    try:
        # First verify the deal belongs to user's org
        deal_result = supabase.table("deals").select(
            "id, deal_number, organization_id"
        ).eq("id", deal_id).eq("organization_id", org_id).single().execute()

        if not deal_result.data:
            return page_layout("Ошибка",
                H1("Доступ запрещён"),
                P("Сделка не найдена или у вас нет доступа."),
                A("← Назад к финансам", href="/finance", role="button"),
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
                A("← Назад к сделке", href=f"/finance/{deal_id}", role="button"),
                session=session
            )
    except Exception as e:
        print(f"Error validating item: {e}")
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось проверить запись: {str(e)}"),
            A("← Назад к сделке", href=f"/finance/{deal_id}", role="button"),
            session=session
        )

    # Prepare update data
    try:
        actual_amount_val = float(actual_amount)
    except ValueError:
        return page_layout("Ошибка",
            H1("Ошибка валидации"),
            P("Некорректное значение суммы."),
            A("← Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", role="button"),
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
                A("← Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", role="button"),
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
            A("← Назад к форме", href=f"/finance/{deal_id}/plan-fact/{item_id}", role="button"),
            session=session
        )


# ============================================================================
# ADMIN: USER MANAGEMENT
# Feature #84: Страница /admin/users
# ============================================================================

@rt("/admin/users")
def get(session):
    """Admin page for user and role management.

    Feature #84: Страница /admin/users

    This page allows admins to:
    - View all users in the organization
    - See assigned roles for each user
    - Add/remove roles
    - See Telegram connection status
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
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get all organization members with their roles and Telegram status
    members_result = supabase.table("organization_members").select(
        "user_id, status, created_at"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    members = members_result.data if members_result.data else []

    # Get all available roles
    from services.role_service import get_all_roles
    all_roles = get_all_roles()

    # Build user data with roles
    users_data = []
    for member in members:
        member_user_id = member["user_id"]

        # Get user roles
        user_roles_result = supabase.table("user_roles").select(
            "id, role_id, roles(code, name)"
        ).eq("user_id", member_user_id).eq("organization_id", org_id).execute()

        member_roles = user_roles_result.data if user_roles_result.data else []
        role_codes = [r.get("roles", {}).get("code", "") for r in member_roles if r.get("roles")]
        role_names = [r.get("roles", {}).get("name", "") for r in member_roles if r.get("roles")]

        # Get Telegram status
        tg_result = supabase.table("telegram_users").select(
            "telegram_id, username, verified_at"
        ).eq("user_id", member_user_id).limit(1).execute()

        tg_data = tg_result.data[0] if tg_result.data else None

        # Try to get email from auth.users via profiles or organization_invites
        # Since we can't directly query auth.users, use the invite email if available
        # Or show user_id shortened
        email_display = member_user_id[:8] + "..."  # Default fallback

        users_data.append({
            "user_id": member_user_id,
            "email": email_display,
            "roles": role_codes,
            "role_names": role_names,
            "telegram": tg_data,
            "joined_at": member["created_at"][:10] if member.get("created_at") else "-"
        })

    # Build users table rows
    user_rows = []
    for u in users_data:
        # Roles badges
        role_badges = []
        for i, code in enumerate(u["roles"]):
            name = u["role_names"][i] if i < len(u["role_names"]) else code
            color = {
                "admin": "#ef4444",
                "sales": "#3b82f6",
                "procurement": "#10b981",
                "logistics": "#f59e0b",
                "customs": "#8b5cf6",
                "quote_controller": "#ec4899",
                "spec_controller": "#06b6d4",
                "finance": "#84cc16",
                "top_manager": "#f97316"
            }.get(code, "#6b7280")
            role_badges.append(
                Span(name, style=f"background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-right: 4px;")
            )

        # Telegram status
        if u["telegram"] and u["telegram"].get("verified_at"):
            tg_status = Span("✓ @" + (u["telegram"].get("username") or str(u["telegram"]["telegram_id"])),
                style="color: #10b981; font-size: 0.875rem;")
        else:
            tg_status = Span("—", style="color: #9ca3af;")

        user_rows.append(Tr(
            Td(u["email"]),
            Td(*role_badges if role_badges else [Span("—", style="color: #9ca3af;")]),
            Td(tg_status),
            Td(u["joined_at"]),
            Td(
                A("Роли", href=f"/admin/users/{u['user_id']}/roles", role="button",
                  style="font-size: 0.75rem; padding: 4px 12px;")
            )
        ))

    # Role legend
    role_legend = Div(
        H4("Доступные роли:", style="margin-bottom: 8px;"),
        Div(
            *[
                Div(
                    Span(r.code, style=f"background: #6b7280; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-right: 8px;"),
                    Span(r.name + (f" - {r.description}" if r.description else ""), style="font-size: 0.875rem;")
                , style="margin-bottom: 4px;")
                for r in all_roles
            ],
            style="display: grid; gap: 4px;"
        ),
        style="background: #f9fafb; padding: 16px; border-radius: 8px; margin-bottom: 24px;"
    )

    return page_layout("Управление пользователями",
        H1("Управление пользователями"),

        # Stats
        Div(
            Div(
                Div(str(len(users_data)), cls="stat-value", style="color: #3b82f6;"),
                Div("Всего пользователей", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(sum(1 for u in users_data if u["telegram"])), cls="stat-value", style="color: #10b981;"),
                Div("С Telegram", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(len(all_roles)), cls="stat-value", style="color: #8b5cf6;"),
                Div("Доступных ролей", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Role legend
        role_legend,

        # Users table
        Div(
            H3("Пользователи организации"),
            Table(
                Thead(Tr(
                    Th("ID пользователя"),
                    Th("Роли"),
                    Th("Telegram"),
                    Th("Дата вступления"),
                    Th("Действия")
                )),
                Tbody(*user_rows) if user_rows else Tbody(Tr(Td("Нет пользователей", colspan="5", style="text-align: center; color: #9ca3af;"))),
                cls="striped"
            ),
            cls="card"
        ),

        # Navigation
        Div(
            A("← На главную", href="/dashboard", role="button", cls="secondary"),
            A("Назначение брендов →", href="/admin/brands", role="button"),
            style="margin-top: 24px; display: flex; gap: 12px;"
        ),

        session=session
    )


@rt("/admin/users/{user_id}/roles")
def get(user_id: str, session):
    """Page to manage roles for a specific user.

    Shows all available roles and allows admin to toggle them on/off.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    supabase = get_supabase()
    org_id = admin_user["org_id"]

    # Get all available roles
    from services.role_service import get_all_roles, get_user_role_codes
    all_roles = get_all_roles()

    # Get current user roles
    current_roles = get_user_role_codes(user_id, org_id)

    # Build role checkboxes
    role_inputs = []
    for r in all_roles:
        checked = r.code in current_roles
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316"
        }.get(r.code, "#6b7280")

        role_inputs.append(
            Label(
                Input(type="checkbox", name="roles", value=r.code, checked=checked),
                Span(r.name, style=f"color: {color}; font-weight: 600; margin-left: 8px;"),
                Span(f" ({r.code})", style="color: #6b7280; font-size: 0.875rem;"),
                Br(),
                Span(r.description or "", style="color: #9ca3af; font-size: 0.875rem; margin-left: 28px;") if r.description else None,
                style="display: block; margin-bottom: 12px; cursor: pointer;"
            )
        )

    return page_layout(f"Управление ролями",
        H1("Управление ролями пользователя"),
        P(f"ID: {user_id[:8]}...", style="color: #6b7280;"),

        # Current roles display
        Div(
            H4("Текущие роли:", style="margin-bottom: 8px;"),
            Div(
                *[Span(code, style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.875rem; margin-right: 4px;") for code in current_roles]
                if current_roles else [Span("Нет ролей", style="color: #9ca3af;")]
            ),
            style="background: #f0fdf4; padding: 12px; border-radius: 8px; margin-bottom: 24px;"
        ),

        # Role management form
        Form(
            H3("Выберите роли:"),
            Div(
                *role_inputs,
                style="margin-bottom: 16px;"
            ),
            Input(type="hidden", name="user_id", value=user_id),
            Button("Сохранить роли", type="submit"),
            method="POST",
            action=f"/admin/users/{user_id}/roles"
        ),

        # Navigation
        Div(
            A("← Назад к списку", href="/admin/users", role="button", cls="secondary"),
            style="margin-top: 24px;"
        ),

        session=session
    )


@rt("/admin/users/{user_id}/roles")
def post(user_id: str, session, roles: list = None):
    """Handle role updates for a user.

    Compares submitted roles with current roles and adds/removes as needed.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    admin_roles = admin_user.get("roles", [])

    # Only admins can access this page
    if "admin" not in admin_roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    # Handle empty roles list (none selected)
    if roles is None:
        roles = []
    elif isinstance(roles, str):
        roles = [roles]

    # Get current user roles
    from services.role_service import get_user_role_codes, assign_role, remove_role
    current_roles = get_user_role_codes(user_id, org_id)

    submitted_roles = set(roles)
    current_roles_set = set(current_roles)

    # Roles to add
    to_add = submitted_roles - current_roles_set
    for role_code in to_add:
        result = assign_role(user_id, org_id, role_code, admin_id)
        if result:
            print(f"Added role {role_code} to user {user_id}")

    # Roles to remove
    to_remove = current_roles_set - submitted_roles
    for role_code in to_remove:
        result = remove_role(user_id, org_id, role_code)
        if result:
            print(f"Removed role {role_code} from user {user_id}")

    # Success message
    return page_layout("Роли обновлены",
        H1("✓ Роли обновлены"),
        P(f"Пользователь: {user_id[:8]}..."),
        P(f"Добавлено ролей: {len(to_add)}" if to_add else ""),
        P(f"Удалено ролей: {len(to_remove)}" if to_remove else ""),
        Div(
            H4("Текущие роли:", style="margin-bottom: 8px;"),
            Div(
                *[Span(code, style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.875rem; margin-right: 4px;") for code in sorted(submitted_roles)]
                if submitted_roles else [Span("Нет ролей", style="color: #9ca3af;")]
            ),
            style="background: #f0fdf4; padding: 12px; border-radius: 8px; margin-top: 16px;"
        ),
        Div(
            A("← Назад к списку", href="/admin/users", role="button"),
            style="margin-top: 24px;"
        ),
        session=session
    )


# ============================================================================
# ADMIN: BRAND MANAGEMENT
# Feature #85: Страница /admin/brands
# ============================================================================

@rt("/admin/brands")
def get(session):
    """Admin page for brand assignments.

    Feature #85: Страница /admin/brands

    This page allows admins to:
    - View all brand assignments (brand → procurement manager)
    - Import new brands from existing quotes
    - Assign/reassign brands to procurement managers
    - Delete brand assignments
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
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Import brand service functions
    from services.brand_service import (
        get_all_brand_assignments,
        get_unique_brands_in_org,
        count_assignments_by_user
    )

    # Get all current brand assignments
    assignments = get_all_brand_assignments(org_id)

    # Get unique brands from quote_items in this organization
    # This is for "import from quotes" functionality
    quote_items_result = supabase.table("quote_items").select(
        "brand, quotes!inner(organization_id)"
    ).eq("quotes.organization_id", org_id).execute()

    all_quote_brands = set()
    for item in (quote_items_result.data or []):
        if item.get("brand"):
            all_quote_brands.add(item["brand"])

    # Get already assigned brands
    assigned_brands = set(a.brand.lower() for a in assignments)

    # Find unassigned brands
    unassigned_brands = [b for b in sorted(all_quote_brands) if b.lower() not in assigned_brands]

    # Get procurement users for assignments
    proc_users_result = supabase.table("organization_members").select(
        "user_id, user_roles(role_id, roles(code))"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    # Filter to only procurement users
    procurement_users = []
    for member in (proc_users_result.data or []):
        user_roles = member.get("user_roles", [])
        has_procurement = any(
            ur.get("roles", {}).get("code") == "procurement"
            for ur in user_roles if ur.get("roles")
        )
        if has_procurement:
            procurement_users.append(member["user_id"])

    # Get assignment counts per user
    assignment_counts = count_assignments_by_user(org_id)

    # Build assignment table rows
    assignment_rows = []
    for a in assignments:
        # Get user display (shortened ID)
        user_display = a.user_id[:8] + "..."
        brand_count = assignment_counts.get(a.user_id, 0)

        assignment_rows.append(Tr(
            Td(Span(a.brand, style="font-weight: 600;")),
            Td(user_display),
            Td(str(brand_count)),
            Td(a.created_at.strftime("%Y-%m-%d") if a.created_at else "-"),
            Td(
                Div(
                    A("Изменить", href=f"/admin/brands/{a.id}/edit", role="button",
                      style="font-size: 0.75rem; padding: 4px 10px; margin-right: 8px;"),
                    Form(
                        Button("Удалить", type="submit", cls="secondary",
                               style="font-size: 0.75rem; padding: 4px 10px;"),
                        method="POST",
                        action=f"/admin/brands/{a.id}/delete",
                        style="display: inline;"
                    ),
                    style="display: flex; align-items: center;"
                )
            )
        ))

    # Build unassigned brands list
    unassigned_items = []
    for brand in unassigned_brands:
        unassigned_items.append(
            Div(
                Span(brand, style="font-weight: 500; margin-right: 12px;"),
                A("Назначить", href=f"/admin/brands/new?brand={brand}", role="button",
                  style="font-size: 0.75rem; padding: 2px 8px;"),
                style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f3f4f6;"
            )
        )

    return page_layout("Управление брендами",
        H1("Управление брендами"),
        P("Назначение брендов менеджерам по закупкам", style="color: #6b7280;"),

        # Stats
        Div(
            Div(
                Div(str(len(assignments)), cls="stat-value", style="color: #10b981;"),
                Div("Назначено брендов", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(len(unassigned_brands)), cls="stat-value", style="color: #f59e0b;"),
                Div("Без назначения", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(len(procurement_users)), cls="stat-value", style="color: #3b82f6;"),
                Div("Менеджеров закупок", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(len(all_quote_brands)), cls="stat-value", style="color: #8b5cf6;"),
                Div("Всего брендов в КП", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Unassigned brands section
        Div(
            H3("Бренды без назначения", style="margin-bottom: 12px;"),
            Div(
                *unassigned_items if unassigned_items else [
                    P("Все бренды из КП назначены менеджерам ✓", style="color: #10b981;")
                ],
                style="max-height: 200px; overflow-y: auto;"
            ),
            cls="card", style="margin-bottom: 24px; border-left: 4px solid #f59e0b;" if unassigned_items else "margin-bottom: 24px;"
        ) if all_quote_brands else None,

        # Add new assignment button
        Div(
            A("+ Добавить назначение", href="/admin/brands/new", role="button"),
            style="margin-bottom: 24px;"
        ),

        # Current assignments table
        Div(
            H3("Текущие назначения"),
            Table(
                Thead(Tr(
                    Th("Бренд"),
                    Th("Менеджер"),
                    Th("Всего брендов"),
                    Th("Дата назначения"),
                    Th("Действия")
                )),
                Tbody(*assignment_rows) if assignment_rows else Tbody(
                    Tr(Td("Нет назначений", colspan="5", style="text-align: center; color: #9ca3af;"))
                ),
                cls="striped"
            ),
            cls="card"
        ),

        # Navigation
        Div(
            A("← Управление пользователями", href="/admin/users", role="button", cls="secondary"),
            A("На главную", href="/dashboard", role="button", cls="secondary"),
            style="margin-top: 24px; display: flex; gap: 12px;"
        ),

        session=session
    )


@rt("/admin/brands/new")
def get(session, brand: str = None):
    """Form to create new brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get procurement users
    proc_users_result = supabase.table("organization_members").select(
        "user_id, user_roles(role_id, roles(code))"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    procurement_users = []
    for member in (proc_users_result.data or []):
        user_roles = member.get("user_roles", [])
        has_procurement = any(
            ur.get("roles", {}).get("code") == "procurement"
            for ur in user_roles if ur.get("roles")
        )
        if has_procurement:
            procurement_users.append({
                "user_id": member["user_id"],
                "display": member["user_id"][:8] + "..."
            })

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"])
        for u in procurement_users
    ]

    return page_layout("Новое назначение бренда",
        H1("Новое назначение бренда"),

        Form(
            Label(
                "Название бренда",
                Input(type="text", name="brand", value=brand or "", required=True,
                      placeholder="Например: BOSCH"),
            ),
            Label(
                "Менеджер по закупкам",
                Select(
                    Option("— Выберите менеджера —", value="", disabled=True, selected=True),
                    *user_options,
                    name="user_id",
                    required=True
                ) if user_options else Div(
                    P("Нет пользователей с ролью 'procurement'", style="color: #ef4444;"),
                    P("Сначала назначьте роль менеджера по закупкам на ",
                      A("странице пользователей", href="/admin/users"), ".")
                )
            ),
            Button("Создать назначение", type="submit") if user_options else None,
            method="POST",
            action="/admin/brands/new"
        ),

        Div(
            A("← Назад к списку", href="/admin/brands", role="button", cls="secondary"),
            style="margin-top: 24px;"
        ),

        session=session
    )


@rt("/admin/brands/new")
def post(session, brand: str, user_id: str):
    """Create new brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    from services.brand_service import create_brand_assignment, get_brand_assignment_by_brand

    # Check if brand is already assigned
    existing = get_brand_assignment_by_brand(org_id, brand)
    if existing:
        return page_layout("Ошибка",
            H1("⚠️ Бренд уже назначен"),
            P(f"Бренд '{brand}' уже назначен другому менеджеру."),
            P("Используйте функцию редактирования для изменения назначения."),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )

    # Create the assignment
    result = create_brand_assignment(
        organization_id=org_id,
        brand=brand.strip(),
        user_id=user_id,
        created_by=admin_id
    )

    if result:
        return page_layout("Назначение создано",
            H1("✓ Назначение создано"),
            P(f"Бренд '{brand}' успешно назначен менеджеру."),
            Div(
                Span(brand, style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;"),
                Span(" → ", style="margin: 0 8px;"),
                Span(user_id[:8] + "...", style="color: #6b7280;"),
                style="margin: 16px 0;"
            ),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("❌ Ошибка создания"),
            P("Не удалось создать назначение. Попробуйте ещё раз."),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )


@rt("/admin/brands/{assignment_id}/edit")
def get(assignment_id: str, session):
    """Edit form for brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    from services.brand_service import get_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    if not assignment:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get procurement users
    proc_users_result = supabase.table("organization_members").select(
        "user_id, user_roles(role_id, roles(code))"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    procurement_users = []
    for member in (proc_users_result.data or []):
        user_roles = member.get("user_roles", [])
        has_procurement = any(
            ur.get("roles", {}).get("code") == "procurement"
            for ur in user_roles if ur.get("roles")
        )
        if has_procurement:
            procurement_users.append({
                "user_id": member["user_id"],
                "display": member["user_id"][:8] + "..."
            })

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"], selected=(u["user_id"] == assignment.user_id))
        for u in procurement_users
    ]

    return page_layout("Редактирование назначения",
        H1("Редактирование назначения"),

        Div(
            H3(f"Бренд: {assignment.brand}", style="color: #10b981;"),
            style="margin-bottom: 16px;"
        ),

        Form(
            Input(type="hidden", name="brand", value=assignment.brand),
            Label(
                "Менеджер по закупкам",
                Select(
                    *user_options,
                    name="user_id",
                    required=True
                ) if user_options else P("Нет менеджеров", style="color: #ef4444;")
            ),
            Button("Сохранить изменения", type="submit") if user_options else None,
            method="POST",
            action=f"/admin/brands/{assignment_id}/edit"
        ),

        Div(
            A("← Назад к списку", href="/admin/brands", role="button", cls="secondary"),
            style="margin-top: 24px;"
        ),

        session=session
    )


@rt("/admin/brands/{assignment_id}/edit")
def post(assignment_id: str, session, user_id: str, brand: str = None):
    """Update brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    from services.brand_service import update_brand_assignment, get_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    if not assignment:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )

    # Update the assignment
    result = update_brand_assignment(assignment_id, user_id)

    if result:
        return page_layout("Назначение обновлено",
            H1("✓ Назначение обновлено"),
            P(f"Бренд '{assignment.brand}' переназначен новому менеджеру."),
            Div(
                Span(assignment.brand, style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;"),
                Span(" → ", style="margin: 0 8px;"),
                Span(user_id[:8] + "...", style="color: #6b7280;"),
                style="margin: 16px 0;"
            ),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("❌ Ошибка обновления"),
            P("Не удалось обновить назначение. Попробуйте ещё раз."),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )


@rt("/admin/brands/{assignment_id}/delete")
def post(assignment_id: str, session):
    """Delete brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            A("← На главную", href="/dashboard", role="button"),
            session=session
        )

    from services.brand_service import get_brand_assignment, delete_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    brand_name = assignment.brand if assignment else "Unknown"

    result = delete_brand_assignment(assignment_id)

    if result:
        return page_layout("Назначение удалено",
            H1("✓ Назначение удалено"),
            P(f"Бренд '{brand_name}' больше не назначен менеджеру."),
            P("Бренд вернулся в список неназначенных.", style="color: #6b7280;"),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("❌ Ошибка удаления"),
            P("Не удалось удалить назначение. Попробуйте ещё раз."),
            A("← Назад к списку", href="/admin/brands", role="button"),
            session=session
        )


# ============================================================================
# API ENDPOINTS - HTMX Search Endpoints
# ============================================================================

# Import location service for API endpoint
from services.location_service import get_locations_for_dropdown, search_locations, format_location_for_dropdown


@rt("/api/locations/search")
def get(session, q: str = "", hub_only: str = "", customs_only: str = "", limit: int = 20):
    """
    Search locations for HTMX dropdown autocomplete.

    This endpoint provides location search functionality for HTMX-powered
    dropdown components used in quote item forms (pickup_location_id).

    Query Parameters:
        q: Search query (matches code, city, country, address)
        hub_only: If "true", return only logistics hub locations
        customs_only: If "true", return only customs point locations
        limit: Maximum number of results (default 20)

    Returns:
        HTML fragment with <option> elements for dropdown

    Usage in HTMX:
        <input type="text"
               hx-get="/api/locations/search"
               hx-trigger="input changed delay:300ms"
               hx-target="#location-options"
               name="q">
        <select id="location-options">
            <!-- Options populated by HTMX -->
        </select>

    Example Response (HTML):
        <option value="">Выберите локацию...</option>
        <option value="uuid-1">MSK - Москва, Россия [хаб]</option>
        <option value="uuid-2">SPB - Санкт-Петербург, Россия [хаб]</option>
    """
    # Check authentication
    redirect = require_login(session)
    if redirect:
        # Return empty for HTMX partial
        return Option("Требуется авторизация", value="", disabled=True)

    user = session["user"]
    org_id = user.get("organization_id")

    if not org_id:
        return Option("Организация не найдена", value="", disabled=True)

    # Parse boolean flags
    is_hub_only = hub_only.lower() == "true"
    is_customs_only = customs_only.lower() == "true"

    # Search locations using location service
    try:
        if q and len(q.strip()) > 0:
            # Search with query
            from services.location_service import search_locations
            locations = search_locations(
                organization_id=org_id,
                query=q.strip(),
                is_hub_only=is_hub_only,
                is_customs_only=is_customs_only,
                limit=min(limit, 50),  # Cap at 50 for safety
            )
            dropdown_items = [format_location_for_dropdown(loc) for loc in locations]
        else:
            # Get all locations (limited) when no query
            dropdown_items = get_locations_for_dropdown(
                organization_id=org_id,
                query=None,
                is_hub_only=is_hub_only,
                is_customs_only=is_customs_only,
                limit=min(limit, 50),
            )

        # Build HTML options
        options = [Option("Выберите локацию...", value="")]
        for item in dropdown_items:
            options.append(Option(item["label"], value=item["value"]))

        # If no results found
        if len(dropdown_items) == 0 and q:
            options.append(Option(f"Ничего не найдено по запросу '{q}'", value="", disabled=True))

        return Group(*options)

    except Exception as e:
        print(f"Error in location search API: {e}")
        return Option(f"Ошибка поиска: {str(e)}", value="", disabled=True)


@rt("/api/locations/search/json")
def get(session, q: str = "", hub_only: str = "", customs_only: str = "", limit: int = 20):
    """
    Search locations for HTMX dropdown - JSON response format.

    Same as /api/locations/search but returns JSON instead of HTML.
    Useful for custom dropdown implementations.

    Returns:
        JSON array of {value, label} objects
    """
    # Check authentication
    redirect = require_login(session)
    if redirect:
        return {"error": "Unauthorized", "items": []}

    user = session["user"]
    org_id = user.get("organization_id")

    if not org_id:
        return {"error": "Organization not found", "items": []}

    # Parse boolean flags
    is_hub_only = hub_only.lower() == "true"
    is_customs_only = customs_only.lower() == "true"

    # Search locations
    try:
        if q and len(q.strip()) > 0:
            from services.location_service import search_locations
            locations = search_locations(
                organization_id=org_id,
                query=q.strip(),
                is_hub_only=is_hub_only,
                is_customs_only=is_customs_only,
                limit=min(limit, 50),
            )
            items = [format_location_for_dropdown(loc) for loc in locations]
        else:
            items = get_locations_for_dropdown(
                organization_id=org_id,
                query=None,
                is_hub_only=is_hub_only,
                is_customs_only=is_customs_only,
                limit=min(limit, 50),
            )

        return {"items": items, "count": len(items), "query": q}

    except Exception as e:
        print(f"Error in location search JSON API: {e}")
        return {"error": str(e), "items": []}


# ============================================================================
# SUPPLIERS LIST (Feature UI-001)
# ============================================================================

@rt("/suppliers")
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
                A("← На главную", href="/dashboard", role="button"),
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
            active_only = None if status == "" else (status == "active")
            suppliers = get_all_suppliers(
                organization_id=org_id,
                country=country if country else None,
                active_only=active_only,
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

    # Build country options for filter
    country_options = [Option("Все страны", value="")] + [
        Option(c, value=c, selected=(c == country)) for c in countries
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
        status_class = "status-approved" if s.is_active else "status-rejected"
        status_text = "Активен" if s.is_active else "Неактивен"

        supplier_rows.append(
            Tr(
                Td(
                    Strong(s.supplier_code),
                    style="font-family: monospace; color: #4a4aff;"
                ),
                Td(s.name),
                Td(f"{s.country or '—'}, {s.city or '—'}" if s.country else "—"),
                Td(s.inn or "—"),
                Td(s.contact_person or "—"),
                Td(s.contact_email or "—"),
                Td(Span(status_text, cls=f"status-badge {status_class}")),
                Td(
                    A("✏️", href=f"/suppliers/{s.id}/edit", title="Редактировать", style="margin-right: 0.5rem;"),
                    A("👁️", href=f"/suppliers/{s.id}", title="Просмотр"),
                )
            )
        )

    return page_layout("Поставщики",
        # Header
        Div(
            H1("📦 Поставщики"),
            A("+ Добавить поставщика", href="/suppliers/new", role="button"),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        # Stats cards
        Div(
            Div(
                Div(str(stats.get("total", 0)), cls="stat-value"),
                Div("Всего"),
                cls="card stat-card"
            ),
            Div(
                Div(str(stats.get("active", 0)), cls="stat-value", style="color: #28a745;"),
                Div("Активных"),
                cls="card stat-card"
            ),
            Div(
                Div(str(stats.get("inactive", 0)), cls="stat-value", style="color: #dc3545;"),
                Div("Неактивных"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Filters
        Div(
            Form(
                Div(
                    Input(name="q", value=q, placeholder="Поиск по названию или коду...", style="flex: 2;"),
                    Select(*country_options, name="country", style="flex: 1;"),
                    Select(*status_options, name="status", style="flex: 1;"),
                    Button("🔍 Поиск", type="submit"),
                    A("Сбросить", href="/suppliers", role="button", cls="secondary"),
                    style="display: flex; gap: 0.5rem; align-items: center;"
                ),
                method="get",
                action="/suppliers"
            ),
            cls="card", style="margin-bottom: 1rem;"
        ),

        # Table
        Table(
            Thead(
                Tr(
                    Th("Код"),
                    Th("Название"),
                    Th("Локация"),
                    Th("ИНН"),
                    Th("Контакт"),
                    Th("Email"),
                    Th("Статус"),
                    Th("Действия")
                )
            ),
            Tbody(*supplier_rows) if supplier_rows else Tbody(
                Tr(Td(
                    "Поставщики не найдены. ",
                    A("Добавить первого поставщика", href="/suppliers/new"),
                    colspan="8", style="text-align: center; padding: 2rem;"
                ))
            )
        ),

        # Results count
        P(f"Показано записей: {len(suppliers)}", style="color: #666; margin-top: 0.5rem;"),

        session=session
    )


@rt("/suppliers/{supplier_id}")
def get(supplier_id: str, session):
    """View single supplier details."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "procurement"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра поставщиков.", cls="alert alert-error"),
            session=session
        )

    from services.supplier_service import get_supplier

    supplier = get_supplier(supplier_id)

    if not supplier:
        return page_layout("Поставщик не найден",
            Div(
                H1("❌ Поставщик не найден"),
                P("Запрашиваемый поставщик не существует."),
                A("← К списку поставщиков", href="/suppliers", role="button"),
                cls="card"
            ),
            session=session
        )

    status_class = "status-approved" if supplier.is_active else "status-rejected"
    status_text = "Активен" if supplier.is_active else "Неактивен"

    return page_layout(f"Поставщик: {supplier.name}",
        # Header with actions
        Div(
            H1(f"📦 {supplier.name}"),
            Div(
                A("✏️ Редактировать", href=f"/suppliers/{supplier_id}/edit", role="button"),
                A("← К списку", href="/suppliers", role="button", cls="secondary"),
                style="display: flex; gap: 0.5rem;"
            ),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        # Main info card
        Div(
            Div(
                H3("Основная информация"),
                Table(
                    Tr(Th("Код поставщика:"), Td(
                        Strong(supplier.supplier_code, style="font-family: monospace; font-size: 1.25rem; color: #4a4aff;")
                    )),
                    Tr(Th("Название:"), Td(supplier.name)),
                    Tr(Th("Статус:"), Td(Span(status_text, cls=f"status-badge {status_class}"))),
                    style="width: auto;"
                ),
                style="flex: 1;"
            ),
            Div(
                H3("Локация"),
                Table(
                    Tr(Th("Страна:"), Td(supplier.country or "—")),
                    Tr(Th("Город:"), Td(supplier.city or "—")),
                    style="width: auto;"
                ),
                style="flex: 1;"
            ),
            cls="card", style="display: flex; gap: 2rem;"
        ),

        # Legal info (if Russian supplier)
        Div(
            H3("Юридические данные"),
            Table(
                Tr(Th("ИНН:"), Td(supplier.inn or "—")),
                Tr(Th("КПП:"), Td(supplier.kpp or "—")),
            ),
            cls="card"
        ) if supplier.inn or supplier.kpp else "",

        # Contact info
        Div(
            H3("Контактная информация"),
            Table(
                Tr(Th("Контактное лицо:"), Td(supplier.contact_person or "—")),
                Tr(Th("Email:"), Td(
                    A(supplier.contact_email, href=f"mailto:{supplier.contact_email}")
                    if supplier.contact_email else "—"
                )),
                Tr(Th("Телефон:"), Td(
                    A(supplier.contact_phone, href=f"tel:{supplier.contact_phone}")
                    if supplier.contact_phone else "—"
                )),
            ),
            cls="card"
        ),

        # Payment terms
        Div(
            H3("Условия оплаты"),
            P(supplier.default_payment_terms or "Не указаны"),
            cls="card"
        ) if supplier.default_payment_terms else "",

        # Metadata
        Div(
            P(f"Создан: {supplier.created_at.strftime('%d.%m.%Y %H:%M') if supplier.created_at else '—'}"),
            P(f"Обновлён: {supplier.updated_at.strftime('%d.%m.%Y %H:%M') if supplier.updated_at else '—'}"),
            style="color: #666; font-size: 0.875rem;"
        ),

        session=session
    )


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

    return page_layout(title,
        # Error alert
        Div(error, cls="alert alert-error") if error else "",

        H1(f"{'✏️' if is_edit else '➕'} {title}"),

        Div(
            Form(
                # Main info section
                H3("Основная информация"),
                Div(
                    Label("Код поставщика *",
                        Input(
                            name="supplier_code",
                            value=supplier.supplier_code if supplier else "",
                            placeholder="ABC",
                            required=True,
                            maxlength="3",
                            pattern="[A-Z]{3}",
                            title="3 заглавные латинские буквы",
                            style="text-transform: uppercase; font-family: monospace; font-weight: bold;"
                        ),
                        Small("3 заглавные латинские буквы (например: CMT, RAR)", style="color: #666; display: block;")
                    ),
                    Label("Название компании *",
                        Input(
                            name="name",
                            value=supplier.name if supplier else "",
                            placeholder="China Manufacturing Ltd",
                            required=True
                        )
                    ),
                    cls="form-row"
                ),

                # Location section
                H3("Локация", style="margin-top: 1.5rem;"),
                Div(
                    Label("Страна",
                        Input(
                            name="country",
                            value=supplier.country if supplier else "",
                            placeholder="Китай"
                        )
                    ),
                    Label("Город",
                        Input(
                            name="city",
                            value=supplier.city if supplier else "",
                            placeholder="Гуанчжоу"
                        )
                    ),
                    cls="form-row"
                ),

                # Legal info (Russian suppliers)
                H3("Юридические данные (для российских поставщиков)", style="margin-top: 1.5rem;"),
                Div(
                    Label("ИНН",
                        Input(
                            name="inn",
                            value=supplier.inn if supplier else "",
                            placeholder="1234567890",
                            pattern="\\d{10}(\\d{2})?",
                            title="10 или 12 цифр"
                        ),
                        Small("10 цифр для юрлиц, 12 для ИП", style="color: #666; display: block;")
                    ),
                    Label("КПП",
                        Input(
                            name="kpp",
                            value=supplier.kpp if supplier else "",
                            placeholder="123456789",
                            pattern="\\d{9}",
                            title="9 цифр"
                        ),
                        Small("9 цифр", style="color: #666; display: block;")
                    ),
                    cls="form-row"
                ),

                # Contact info section
                H3("Контактная информация", style="margin-top: 1.5rem;"),
                Div(
                    Label("Контактное лицо",
                        Input(
                            name="contact_person",
                            value=supplier.contact_person if supplier else "",
                            placeholder="Иван Иванов"
                        )
                    ),
                    Label("Email",
                        Input(
                            name="contact_email",
                            type="email",
                            value=supplier.contact_email if supplier else "",
                            placeholder="contact@supplier.com"
                        )
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Телефон",
                        Input(
                            name="contact_phone",
                            value=supplier.contact_phone if supplier else "",
                            placeholder="+7 999 123 4567"
                        )
                    ),
                    Div(cls="form-placeholder"),  # Empty placeholder for alignment
                    cls="form-row"
                ),

                # Payment terms section
                H3("Условия работы", style="margin-top: 1.5rem;"),
                Label("Условия оплаты по умолчанию",
                    Textarea(
                        supplier.default_payment_terms if supplier else "",
                        name="default_payment_terms",
                        placeholder="50% предоплата, 50% по готовности",
                        rows="3"
                    )
                ),

                # Status (for edit mode)
                Div(
                    H3("Статус", style="margin-top: 1.5rem;"),
                    Label(
                        Input(
                            type="checkbox",
                            name="is_active",
                            checked=supplier.is_active if supplier else True,
                            value="true"
                        ),
                        " Активный поставщик",
                        style="display: flex; align-items: center; gap: 0.5rem;"
                    ),
                    Small("Неактивные поставщики не отображаются в выпадающих списках", style="color: #666;"),
                ) if is_edit else "",

                # Form actions
                Div(
                    Button("💾 Сохранить", type="submit"),
                    A("Отмена", href="/suppliers" if not is_edit else f"/suppliers/{supplier.id}", role="button", cls="secondary"),
                    cls="form-actions", style="margin-top: 1.5rem;"
                ),

                method="post",
                action=action_url
            ),
            cls="card"
        ),
        session=session
    )


@rt("/suppliers/new")
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


@rt("/suppliers/new")
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


@rt("/suppliers/{supplier_id}/edit")
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
            A("← К списку поставщиков", href="/suppliers", role="button"),
            session=session
        )

    return _supplier_form(supplier=supplier, session=session)


@rt("/suppliers/{supplier_id}/edit")
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


@rt("/suppliers/{supplier_id}/delete")
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
            A("← К списку поставщиков", href="/suppliers", role="button"),
            session=session
        )


# ============================================================================
# BUYER COMPANIES LIST (Feature UI-003)
# ============================================================================

@rt("/buyer-companies")
def get(session, q: str = "", status: str = ""):
    """
    Buyer companies list page with search and filters.

    Buyer companies are OUR legal entities used for purchasing from suppliers.
    Each quote_item can have its own buyer_company_id.

    Query Parameters:
        q: Search query (matches name or company_code)
        status: Filter by status ("active", "inactive", or "" for all)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only can manage buyer companies
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div(
                H1("⛔ Доступ запрещён"),
                P("У вас нет прав для просмотра справочника компаний-покупателей."),
                P("Требуется роль: admin"),
                A("← На главную", href="/dashboard", role="button"),
                cls="card"
            ),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    # Import buyer company service
    from services.buyer_company_service import (
        get_all_buyer_companies, search_buyer_companies, get_buyer_company_stats
    )

    # Get buyer companies based on filters
    try:
        if q and q.strip():
            # Use search if query provided
            companies = search_buyer_companies(
                organization_id=org_id,
                query=q.strip(),
                active_only=(status == "active"),
                limit=100
            )
        else:
            # Get all with filters
            active_only = None if status == "" else (status == "active")
            companies = get_all_buyer_companies(
                organization_id=org_id,
                active_only=active_only,
                limit=100
            )

        # Get stats for summary
        stats = get_buyer_company_stats(organization_id=org_id)

    except Exception as e:
        print(f"Error loading buyer companies: {e}")
        companies = []
        stats = {"total": 0, "active": 0, "inactive": 0}

    # Status options for filter
    status_options = [
        Option("Все статусы", value="", selected=(status == "")),
        Option("Активные", value="active", selected=(status == "active")),
        Option("Неактивные", value="inactive", selected=(status == "inactive")),
    ]

    # Build company rows
    company_rows = []
    for c in companies:
        status_class = "status-approved" if c.is_active else "status-rejected"
        status_text = "Активна" if c.is_active else "Неактивна"

        company_rows.append(
            Tr(
                Td(
                    Strong(c.company_code),
                    style="font-family: monospace; color: #4a4aff;"
                ),
                Td(c.name),
                Td(c.inn or "—"),
                Td(c.kpp or "—"),
                Td(c.ogrn or "—"),
                Td(c.general_director_name or "—"),
                Td(Span(status_text, cls=f"status-badge {status_class}")),
                Td(
                    A("✏️", href=f"/buyer-companies/{c.id}/edit", title="Редактировать", style="margin-right: 0.5rem;"),
                    A("👁️", href=f"/buyer-companies/{c.id}", title="Просмотр"),
                )
            )
        )

    return page_layout("Компании-покупатели",
        # Header
        Div(
            H1("🏢 Компании-покупатели (закупки)"),
            A("+ Добавить компанию", href="/buyer-companies/new", role="button"),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        # Info alert explaining what this is
        Div(
            "💡 Компании-покупатели — наши юрлица, через которые мы закупаем товар у поставщиков. "
            "Указываются на уровне позиции КП (quote_item.buyer_company_id).",
            cls="alert alert-info"
        ),

        # Stats cards
        Div(
            Div(
                Div(str(stats.get("total", 0)), cls="stat-value"),
                Div("Всего"),
                cls="card stat-card"
            ),
            Div(
                Div(str(stats.get("active", 0)), cls="stat-value", style="color: #28a745;"),
                Div("Активных"),
                cls="card stat-card"
            ),
            Div(
                Div(str(stats.get("inactive", 0)), cls="stat-value", style="color: #dc3545;"),
                Div("Неактивных"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Filters
        Div(
            Form(
                Div(
                    Input(name="q", value=q, placeholder="Поиск по названию или коду...", style="flex: 2;"),
                    Select(*status_options, name="status", style="flex: 1;"),
                    Button("🔍 Поиск", type="submit"),
                    A("Сбросить", href="/buyer-companies", role="button", cls="secondary"),
                    style="display: flex; gap: 0.5rem; align-items: center;"
                ),
                method="get",
                action="/buyer-companies"
            ),
            cls="card", style="margin-bottom: 1rem;"
        ),

        # Table
        Table(
            Thead(
                Tr(
                    Th("Код"),
                    Th("Название"),
                    Th("ИНН"),
                    Th("КПП"),
                    Th("ОГРН"),
                    Th("Директор"),
                    Th("Статус"),
                    Th("Действия")
                )
            ),
            Tbody(*company_rows) if company_rows else Tbody(
                Tr(Td(
                    "Компании не найдены. ",
                    A("Добавить первую компанию", href="/buyer-companies/new"),
                    colspan="8", style="text-align: center; padding: 2rem;"
                ))
            )
        ),

        # Results count
        P(f"Показано записей: {len(companies)}", style="color: #666; margin-top: 0.5rem;"),

        session=session
    )


@rt("/buyer-companies/{company_id}")
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
                H1("❌ Компания не найдена"),
                P("Запрашиваемая компания-покупатель не существует."),
                A("← К списку компаний", href="/buyer-companies", role="button"),
                cls="card"
            ),
            session=session
        )

    status_class = "status-approved" if company.is_active else "status-rejected"
    status_text = "Активна" if company.is_active else "Неактивна"

    return page_layout(f"Компания: {company.name}",
        # Header with actions
        Div(
            H1(f"🏢 {company.name}"),
            Div(
                A("✏️ Редактировать", href=f"/buyer-companies/{company_id}/edit", role="button"),
                A("← К списку", href="/buyer-companies", role="button", cls="secondary"),
                style="display: flex; gap: 0.5rem;"
            ),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        # Main info card
        Div(
            Div(
                H3("Основная информация"),
                Table(
                    Tr(Th("Код компании:"), Td(
                        Strong(company.company_code, style="font-family: monospace; font-size: 1.25rem; color: #4a4aff;")
                    )),
                    Tr(Th("Название:"), Td(company.name)),
                    Tr(Th("Страна:"), Td(company.country or "Россия")),
                    Tr(Th("Статус:"), Td(Span(status_text, cls=f"status-badge {status_class}"))),
                    style="width: auto;"
                ),
                style="flex: 1;"
            ),
            Div(
                H3("Руководство"),
                Table(
                    Tr(Th("Должность:"), Td(company.general_director_position or "Генеральный директор")),
                    Tr(Th("ФИО:"), Td(company.general_director_name or "—")),
                    style="width: auto;"
                ),
                style="flex: 1;"
            ),
            cls="card", style="display: flex; gap: 2rem;"
        ),

        # Legal info
        Div(
            H3("Юридические данные"),
            Table(
                Tr(Th("ИНН:"), Td(company.inn or "—")),
                Tr(Th("КПП:"), Td(company.kpp or "—")),
                Tr(Th("ОГРН:"), Td(company.ogrn or "—")),
            ),
            cls="card"
        ),

        # Registration address
        Div(
            H3("Юридический адрес"),
            P(company.registration_address or "Не указан"),
            cls="card"
        ) if company.registration_address else "",

        # Metadata
        Div(
            P(f"Создана: {company.created_at.strftime('%d.%m.%Y %H:%M') if company.created_at else '—'}"),
            P(f"Обновлена: {company.updated_at.strftime('%d.%m.%Y %H:%M') if company.updated_at else '—'}"),
            style="color: #666; font-size: 0.875rem;"
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

    return page_layout(title,
        # Error alert
        Div(error, cls="alert alert-error") if error else "",

        H1(f"{'✏️' if is_edit else '➕'} {title}"),

        # Info alert
        Div(
            "💡 Компания-покупатель — наше юридическое лицо, через которое мы закупаем товар у поставщиков. "
            "Привязывается к позиции КП (quote_item).",
            cls="alert alert-info"
        ),

        Div(
            Form(
                # Main info section
                H3("Основная информация"),
                Div(
                    Label("Код компании *",
                        Input(
                            name="company_code",
                            value=company.company_code if company else "",
                            placeholder="ZAK",
                            required=True,
                            maxlength="3",
                            pattern="[A-Z]{3}",
                            title="3 заглавные латинские буквы",
                            style="text-transform: uppercase; font-family: monospace; font-weight: bold;"
                        ),
                        Small("3 заглавные латинские буквы (например: ZAK, CMT)", style="color: #666; display: block;")
                    ),
                    Label("Название компании *",
                        Input(
                            name="name",
                            value=company.name if company else "",
                            placeholder='ООО "Закупки"',
                            required=True
                        )
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Страна",
                        Input(
                            name="country",
                            value=company.country if company else "Россия",
                            placeholder="Россия"
                        )
                    ),
                    Div(cls="form-placeholder"),  # Empty placeholder for alignment
                    cls="form-row"
                ),

                # Legal info section (required for Russian legal entity)
                H3("Юридические данные", style="margin-top: 1.5rem;"),
                Div(
                    Label("ИНН *",
                        Input(
                            name="inn",
                            value=company.inn if company else "",
                            placeholder="1234567890",
                            pattern="\\d{10}",
                            title="10 цифр для юридического лица",
                            required=True
                        ),
                        Small("10 цифр (ИНН юридического лица)", style="color: #666; display: block;")
                    ),
                    Label("КПП",
                        Input(
                            name="kpp",
                            value=company.kpp if company else "",
                            placeholder="123456789",
                            pattern="\\d{9}",
                            title="9 цифр"
                        ),
                        Small("9 цифр", style="color: #666; display: block;")
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("ОГРН",
                        Input(
                            name="ogrn",
                            value=company.ogrn if company else "",
                            placeholder="1234567890123",
                            pattern="\\d{13}",
                            title="13 цифр"
                        ),
                        Small("13 цифр", style="color: #666; display: block;")
                    ),
                    Div(cls="form-placeholder"),
                    cls="form-row"
                ),

                # Registration address
                H3("Юридический адрес", style="margin-top: 1.5rem;"),
                Label("Адрес регистрации",
                    Textarea(
                        company.registration_address if company else "",
                        name="registration_address",
                        placeholder="123456, г. Москва, ул. Примерная, д. 1",
                        rows="2"
                    )
                ),

                # Director information
                H3("Руководство (для документов)", style="margin-top: 1.5rem;"),
                Div(
                    Label("Должность руководителя",
                        Input(
                            name="general_director_position",
                            value=company.general_director_position if company else "Генеральный директор",
                            placeholder="Генеральный директор"
                        )
                    ),
                    Label("ФИО руководителя",
                        Input(
                            name="general_director_name",
                            value=company.general_director_name if company else "",
                            placeholder="Иванов Иван Иванович"
                        )
                    ),
                    cls="form-row"
                ),

                # Status (for edit mode)
                Div(
                    H3("Статус", style="margin-top: 1.5rem;"),
                    Label(
                        Input(
                            type="checkbox",
                            name="is_active",
                            checked=company.is_active if company else True,
                            value="true"
                        ),
                        " Активная компания",
                        style="display: flex; align-items: center; gap: 0.5rem;"
                    ),
                    Small("Неактивные компании не отображаются в выпадающих списках", style="color: #666;"),
                ) if is_edit else "",

                # Form actions
                Div(
                    Button("💾 Сохранить", type="submit"),
                    A("Отмена", href="/buyer-companies" if not is_edit else f"/buyer-companies/{company.id}", role="button", cls="secondary"),
                    cls="form-actions", style="margin-top: 1.5rem;"
                ),

                method="post",
                action=action_url
            ),
            cls="card"
        ),
        session=session
    )


@rt("/buyer-companies/new")
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


@rt("/buyer-companies/new")
def post(
    company_code: str,
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


@rt("/buyer-companies/{company_id}/edit")
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
            A("← К списку компаний", href="/buyer-companies", role="button"),
            session=session
        )

    return _buyer_company_form(company=company, session=session)


@rt("/buyer-companies/{company_id}/edit")
def post(
    company_id: str,
    company_code: str,
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
            A("← К списку компаний", href="/buyer-companies", role="button"),
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


@rt("/buyer-companies/{company_id}/delete")
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
        return RedirectResponse("/buyer-companies", status_code=303)
    else:
        return page_layout("Ошибка",
            Div("Не удалось деактивировать компанию.", cls="alert alert-error"),
            A("← К списку компаний", href="/buyer-companies", role="button"),
            session=session
        )


# ============================================================================
# SELLER COMPANIES MANAGEMENT (UI-005, UI-006)
# ============================================================================

@rt("/seller-companies")
def get(session, q: str = "", status: str = ""):
    """
    Seller companies list page with search and filters.

    Seller companies are OUR legal entities used for selling to customers.
    Each quote has one seller_company_id (at quote level).

    Query Parameters:
        q: Search query (matches name, supplier_code, INN)
        status: Filter by status ("active", "inactive", or "" for all)
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin only can manage seller companies
    if not user_has_role(session, "admin"):
        return page_layout("Access Denied",
            Div(
                H1("⛔ Доступ запрещён"),
                P("У вас нет прав для просмотра справочника компаний-продавцов."),
                P("Требуется роль: admin"),
                A("← На главную", href="/dashboard", role="button"),
                cls="card"
            ),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    # Import seller company service
    from services.seller_company_service import (
        get_all_seller_companies, search_seller_companies, get_seller_company_stats
    )

    # Get seller companies based on filters
    try:
        if q and q.strip():
            # Use search if query provided
            is_active_filter = None if status == "" else (status == "active")
            companies = search_seller_companies(
                organization_id=org_id,
                query=q.strip(),
                is_active=is_active_filter,
                limit=100
            )
        else:
            # Get all with filters
            is_active_filter = None if status == "" else (status == "active")
            companies = get_all_seller_companies(
                organization_id=org_id,
                is_active=is_active_filter,
                limit=100
            )

        # Get stats for summary
        stats = get_seller_company_stats(organization_id=org_id)

    except Exception as e:
        print(f"Error loading seller companies: {e}")
        companies = []
        stats = {"total": 0, "active": 0, "inactive": 0}

    # Status options for filter
    status_options = [
        Option("Все статусы", value="", selected=(status == "")),
        Option("Активные", value="active", selected=(status == "active")),
        Option("Неактивные", value="inactive", selected=(status == "inactive")),
    ]

    # Build company rows
    company_rows = []
    for c in companies:
        status_class = "status-approved" if c.is_active else "status-rejected"
        status_text = "Активна" if c.is_active else "Неактивна"

        company_rows.append(
            Tr(
                Td(
                    Strong(c.supplier_code),
                    style="font-family: monospace; color: #4a4aff;"
                ),
                Td(c.name),
                Td(c.country or "—"),
                Td(c.inn or "—"),
                Td(c.kpp or "—"),
                Td(c.general_director_name or "—"),
                Td(Span(status_text, cls=f"status-badge {status_class}")),
                Td(
                    A("✏️", href=f"/seller-companies/{c.id}/edit", title="Редактировать", style="margin-right: 0.5rem;"),
                    A("👁️", href=f"/seller-companies/{c.id}", title="Просмотр"),
                )
            )
        )

    return page_layout("Компании-продавцы",
        # Header
        Div(
            H1("🏭 Компании-продавцы (наши юрлица)"),
            A("+ Добавить компанию", href="/seller-companies/new", role="button"),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),

        # Info alert
        Div(
            "ℹ️ Компании-продавцы — это наши юридические лица, через которые мы продаём товары клиентам. ",
            "Каждое КП (quote) привязывается к одной компании-продавцу. ",
            "Примеры: MBR (МАСТЕР БЭРИНГ), RAR (РадРесурс), CMT (ЦМТО1), GES (GESTUS), TEX (TEXCEL).",
            cls="alert alert-info"
        ),

        # Stats cards
        Div(
            Div(
                Div(str(stats.get("total", 0)), cls="stat-value"),
                Div("Всего"),
                cls="stat-card card"
            ),
            Div(
                Div(str(stats.get("active", 0)), cls="stat-value"),
                Div("Активных"),
                cls="stat-card card"
            ),
            Div(
                Div(str(stats.get("inactive", 0)), cls="stat-value"),
                Div("Неактивных"),
                cls="stat-card card"
            ),
            cls="stats-grid"
        ),

        # Filter form
        Div(
            Form(
                Div(
                    Label(
                        "Поиск по названию, коду или ИНН:",
                        Input(type="text", name="q", value=q, placeholder="Например: МАСТЕР или MBR"),
                    ),
                    Label(
                        "Статус:",
                        Select(*status_options, name="status"),
                    ),
                    Button("Найти", type="submit"),
                    style="display: flex; gap: 1rem; align-items: flex-end;"
                ),
                method="get",
                action="/seller-companies"
            ),
            cls="card"
        ),

        # Companies table
        Div(
            Table(
                Thead(
                    Tr(
                        Th("Код"),
                        Th("Название"),
                        Th("Страна"),
                        Th("ИНН"),
                        Th("КПП"),
                        Th("Директор"),
                        Th("Статус"),
                        Th("Действия"),
                    )
                ),
                Tbody(*company_rows) if company_rows else Tbody(
                    Tr(Td("Компании-продавцы не найдены", colspan="8", style="text-align: center; color: #666;"))
                )
            ),
            cls="card"
        ),

        session=session
    )


@rt("/seller-companies/{company_id}")
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
            A("← К списку компаний", href="/seller-companies", role="button"),
            session=session
        )

    status_class = "status-approved" if company.is_active else "status-rejected"
    status_text = "Активна" if company.is_active else "Неактивна"

    return page_layout(f"Компания: {company.name}",
        Div(
            # Header with actions
            Div(
                H1(f"🏭 {company.supplier_code} - {company.name}"),
                Div(
                    A("✏️ Редактировать", href=f"/seller-companies/{company_id}/edit", role="button"),
                    " ",
                    A("← К списку", href="/seller-companies", role="button", cls="secondary"),
                    style="display: flex; gap: 0.5rem;"
                ),
                style="display: flex; justify-content: space-between; align-items: center;"
            ),
            cls="card"
        ),

        # Company details
        Div(
            H2("Основная информация"),
            Div(
                Div(
                    Strong("Код компании: "), Span(company.supplier_code, style="font-family: monospace;"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Название: "), Span(company.name),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Страна: "), Span(company.country or "—"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Статус: "), Span(status_text, cls=f"status-badge {status_class}"),
                    style="margin-bottom: 0.5rem;"
                ),
            ),

            H2("Юридические реквизиты", style="margin-top: 1.5rem;"),
            Div(
                Div(
                    Strong("ИНН: "), Span(company.inn or "—"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("КПП: "), Span(company.kpp or "—"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("ОГРН: "), Span(company.ogrn or "—"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Юридический адрес: "), Span(company.registration_address or "—"),
                    style="margin-bottom: 0.5rem;"
                ),
            ),

            H2("Руководитель", style="margin-top: 1.5rem;"),
            Div(
                Div(
                    Strong("ФИО директора: "), Span(company.general_director_name or "—"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Strong("Должность: "), Span(company.general_director_position or "Генеральный директор"),
                    style="margin-bottom: 0.5rem;"
                ),
            ),

            cls="card"
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

    return page_layout(title,
        # Header
        Div(
            H1(f"🏭 {title}"),
            cls="card"
        ),

        # Info alert
        Div(
            "ℹ️ Компания-продавец — это наше юридическое лицо, от имени которого мы продаём товары клиентам. ",
            "Код компании (3 буквы) используется для генерации IDN коммерческого предложения.",
            cls="alert alert-info"
        ),

        # Error message
        Div(f"❌ {error}", cls="alert alert-error") if error else "",

        # Form
        Div(
            Form(
                # Basic information
                H3("Основная информация"),
                Div(
                    Label("Код компании *",
                        Input(
                            name="supplier_code",
                            value=company.supplier_code if company else "",
                            placeholder="MBR",
                            pattern="[A-Za-z]{3}",
                            maxlength="3",
                            required=True,
                            title="3 буквы латиницей (например, MBR, CMT, GES)",
                            style="text-transform: uppercase;"
                        ),
                        Small("3 буквы латиницей (используется в IDN)", style="color: #666; display: block;")
                    ),
                    Label("Название компании *",
                        Input(
                            name="name",
                            value=company.name if company else "",
                            placeholder="ООО «МАСТЕР БЭРИНГ»",
                            required=True
                        )
                    ),
                    cls="form-row"
                ),

                # Country
                Div(
                    Label("Страна",
                        Input(
                            name="country",
                            value=company.country if company else "Россия",
                            placeholder="Россия"
                        )
                    ),
                    Div(cls="form-placeholder"),
                    cls="form-row"
                ),

                # Legal identifiers
                H3("Юридические реквизиты", style="margin-top: 1.5rem;"),
                Div(
                    "ℹ️ ИНН: 10 цифр для юрлиц, 12 цифр для ИП. ОГРН: 13 цифр для юрлиц, 15 цифр для ИП.",
                    cls="alert alert-info", style="margin-bottom: 1rem;"
                ),
                Div(
                    Label("ИНН",
                        Input(
                            name="inn",
                            value=company.inn if company else "",
                            placeholder="1234567890 или 123456789012",
                            pattern="\\d{10}|\\d{12}",
                            title="10 цифр для юрлица или 12 цифр для ИП"
                        ),
                        Small("10 цифр (юрлицо) или 12 цифр (ИП)", style="color: #666; display: block;")
                    ),
                    Label("КПП",
                        Input(
                            name="kpp",
                            value=company.kpp if company else "",
                            placeholder="123456789",
                            pattern="\\d{9}",
                            title="9 цифр (только для юрлиц)"
                        ),
                        Small("9 цифр (только для юрлиц)", style="color: #666; display: block;")
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("ОГРН",
                        Input(
                            name="ogrn",
                            value=company.ogrn if company else "",
                            placeholder="1234567890123 или 123456789012345",
                            pattern="\\d{13}|\\d{15}",
                            title="13 цифр для юрлица или 15 цифр для ИП"
                        ),
                        Small("13 цифр (юрлицо) или 15 цифр (ИП)", style="color: #666; display: block;")
                    ),
                    Div(cls="form-placeholder"),
                    cls="form-row"
                ),

                # Registration address
                H3("Юридический адрес", style="margin-top: 1.5rem;"),
                Label("Адрес регистрации",
                    Textarea(
                        company.registration_address if company else "",
                        name="registration_address",
                        placeholder="123456, г. Москва, ул. Примерная, д. 1, офис 100",
                        rows="2"
                    )
                ),

                # Director information
                H3("Руководство (для документов)", style="margin-top: 1.5rem;"),
                Div(
                    Label("Должность руководителя",
                        Input(
                            name="general_director_position",
                            value=company.general_director_position if company else "Генеральный директор",
                            placeholder="Генеральный директор"
                        )
                    ),
                    Label("ФИО руководителя",
                        Input(
                            name="general_director_name",
                            value=company.general_director_name if company else "",
                            placeholder="Иванов Иван Иванович"
                        )
                    ),
                    cls="form-row"
                ),

                # Status (for edit mode)
                Div(
                    H3("Статус", style="margin-top: 1.5rem;"),
                    Label(
                        Input(
                            type="checkbox",
                            name="is_active",
                            checked=company.is_active if company else True,
                            value="true"
                        ),
                        " Активная компания",
                        style="display: flex; align-items: center; gap: 0.5rem;"
                    ),
                    Small("Неактивные компании не отображаются в выпадающих списках при создании КП", style="color: #666;"),
                ) if is_edit else "",

                # Form actions
                Div(
                    Button("💾 Сохранить", type="submit"),
                    A("Отмена", href="/seller-companies" if not is_edit else f"/seller-companies/{company.id}", role="button", cls="secondary"),
                    cls="form-actions", style="margin-top: 1.5rem;"
                ),

                method="post",
                action=action_url
            ),
            cls="card"
        ),
        session=session
    )


@rt("/seller-companies/new")
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


@rt("/seller-companies/new")
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


@rt("/seller-companies/{company_id}/edit")
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
            A("← К списку компаний", href="/seller-companies", role="button"),
            session=session
        )

    return _seller_company_form(company=company, session=session)


@rt("/seller-companies/{company_id}/edit")
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
            A("← К списку компаний", href="/seller-companies", role="button"),
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


@rt("/seller-companies/{company_id}/delete")
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
        return RedirectResponse("/seller-companies", status_code=303)
    else:
        return page_layout("Ошибка",
            Div("Не удалось деактивировать компанию.", cls="alert alert-error"),
            A("← К списку компаний", href="/seller-companies", role="button"),
            session=session
        )


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Kvota OneStack - FastHTML + Supabase")
    print("="*50)
    print("  URL: http://localhost:5001")
    print("  Using real Supabase database")
    print("="*50 + "\n")

    serve(port=5001)
