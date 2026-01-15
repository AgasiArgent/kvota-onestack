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
from services.specification_export import generate_specification_pdf
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
    transition_quote_status
)

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
# DASHBOARD
# ============================================================================

@rt("/dashboard")
def get(session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quotes stats
    quotes_result = supabase.table("quotes") \
        .select("id, status, total_amount") \
        .eq("organization_id", user["org_id"]) \
        .execute()

    quotes = quotes_result.data or []

    total_quotes = len(quotes)
    total_revenue = sum(
        Decimal(str(q.get("total_amount") or 0))
        for q in quotes if q.get("status") == "approved"
    )
    pending_quotes = len([q for q in quotes if q.get("status") in ["draft", "sent"]])

    # Get recent quotes
    recent_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, customers(name), status, total_amount, created_at") \
        .eq("organization_id", user["org_id"]) \
        .order("created_at", desc=True) \
        .limit(5) \
        .execute()

    recent_quotes = recent_result.data or []

    return page_layout("Dashboard",
        H1(f"Welcome back!"),
        P(f"Organization: {user.get('org_name', 'Unknown')}"),

        # Stats cards
        Div(
            Div(
                Div(str(total_quotes), cls="stat-value"),
                Div("Total Quotes"),
                cls="card stat-card"
            ),
            Div(
                Div(format_money(total_revenue), cls="stat-value"),
                Div("Revenue (Approved)"),
                cls="card stat-card"
            ),
            Div(
                Div(str(pending_quotes), cls="stat-value"),
                Div("Pending"),
                cls="card stat-card"
            ),
            cls="stats-grid"
        ),

        # Recent quotes
        H2("Recent Quotes"),
        Table(
            Thead(Tr(Th("Quote #"), Th("Customer"), Th("Status"), Th("Total"), Th("Actions"))),
            Tbody(
                *[Tr(
                    Td(q.get("idn_quote", f"#{q['id'][:8]}")),
                    Td(q.get("customers", {}).get("name", "—") if q.get("customers") else "—"),
                    Td(status_badge(q.get("status", "draft"))),
                    Td(format_money(q.get("total_amount"))),
                    Td(A("View", href=f"/quotes/{q['id']}"))
                ) for q in recent_quotes]
            ) if recent_quotes else Tbody(Tr(Td("No quotes yet", colspan="5", style="text-align: center;")))
        ),
        A("View All Quotes →", href="/quotes"),
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

        result = supabase.table("quotes").insert({
            "idn_quote": idn_quote,
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

    return page_layout(f"Quote {quote.get('idn_quote', '')}",
        Div(
            Div(
                H1(f"Quote {quote.get('idn_quote', '')}"),
                status_badge(quote.get("status", "draft")),
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
            .select("id, quote_id, brand, procurement_status, quantity, name") \
            .execute()

        # Filter items for my brands (case-insensitive)
        my_items = [item for item in (items_result.data or [])
                    if item.get("brand", "").lower() in my_brands_lower]

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

        session=session
    )


@rt("/procurement/{quote_id}")
def post(quote_id: str, session, action: str = "save", **kwargs):
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

    supabase = get_supabase()

    # Verify quote exists and is accessible
    quote_result = supabase.table("quotes") \
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
    item_count = int(kwargs.get("item_count", 0))

    # Process each item from the form
    updated_items = 0
    for idx in range(item_count):
        item_id = kwargs.get(f"item_id_{idx}")
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
        if not item or item.get("brand", "").lower() not in my_brands_lower:
            continue

        # Build update data
        update_data = {}

        # Get values from form (using item_id suffix)
        base_price = kwargs.get(f"base_price_vat_{item_id}")
        if base_price:
            update_data["base_price_vat"] = float(base_price)

        weight = kwargs.get(f"weight_in_kg_{item_id}")
        if weight:
            update_data["weight_in_kg"] = float(weight)

        supplier_country = kwargs.get(f"supplier_country_{item_id}")
        if supplier_country:
            update_data["supplier_country"] = supplier_country

        supplier_city = kwargs.get(f"supplier_city_{item_id}")
        update_data["supplier_city"] = supplier_city or None

        production_time = kwargs.get(f"production_time_days_{item_id}")
        if production_time:
            update_data["production_time_days"] = int(production_time)

        payer_company = kwargs.get(f"payer_company_{item_id}")
        update_data["payer_company"] = payer_company or None

        advance_percent = kwargs.get(f"advance_to_supplier_percent_{item_id}")
        if advance_percent:
            update_data["advance_to_supplier_percent"] = float(advance_percent)

        payment_terms = kwargs.get(f"supplier_payment_terms_{item_id}")
        update_data["supplier_payment_terms"] = payment_terms or None

        notes = kwargs.get(f"procurement_notes_{item_id}")
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
        .select("id, brand, article_number, name, quantity, unit, base_price, weight, supplier_country") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    # Check if logistics is editable
    editable_statuses = ["pending_logistics", "pending_customs", "draft", "pending_procurement"]
    is_editable = workflow_status in editable_statuses and quote.get("logistics_completed_at") is None
    logistics_done = quote.get("logistics_completed_at") is not None

    # Calculate summary stats
    total_items = len(items)
    total_weight = sum(float(item.get("weight", 0) or 0) for item in items)
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
                Td(item.get("article_number", "—")),
                Td(item.get("name", "—")[:40] + "..." if len(item.get("name", "")) > 40 else item.get("name", "—")),
                Td(str(item.get("quantity", 0))),
                Td(str(item.get("weight", "—"))),
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
                "organization_id": org_id,
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
        .select("id, brand, article_number, name, quantity, unit, base_price, weight, supplier_country, hs_code, customs_duty, customs_extra") \
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
                Div(item.get("article_number", ""), style="font-size: 0.75rem; color: #666;")
            ),
            Td(item.get("name", "—")[:40] + "..." if len(item.get("name", "")) > 40 else item.get("name", "—")),
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
def post(session, quote_id: str, action: str = "save", customs_notes: str = "", **kwargs):
    """
    Save customs data for all items and optionally mark customs as complete.

    Feature #44: Customs data entry form (POST handler)
    Feature #45: Complete customs button
    """
    redirect = require_login(session)
    if redirect:
        return redirect

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
        hs_code = kwargs.get(f"hs_code_{item_id}", "")
        customs_duty = kwargs.get(f"customs_duty_{item_id}", "0")
        customs_extra = kwargs.get(f"customs_extra_{item_id}", "0")

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
        .select("*, customers(name, idn_customer)") \
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
        .select("*, customers(name, idn_customer)") \
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
        .select("*, customers(name, idn_customer)") \
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
    Transitions the quote from PENDING_QUOTE_CONTROL to PENDING_APPROVAL.

    Feature #50: Кнопка отправки на согласование - POST handler
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
        return page_layout("Согласование невозможно",
            H1("Согласование невозможно"),
            P(f"КП находится в статусе '{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}' и не может быть отправлено на согласование."),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}"),
            session=session
        )

    # Perform the workflow transition to PENDING_APPROVAL
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_APPROVAL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=comment.strip()
    )

    if result.success:
        # Success - redirect to quote control list
        return page_layout("Успешно",
            H1("✓ КП отправлено на согласование"),
            P(f"КП {idn_quote} было успешно отправлено на согласование топ-менеджеру."),
            P(f"Комментарий: {comment.strip()}", style="color: #666; font-style: italic;"),
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
        .select("*, customers(name, idn_customer)") \
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
                # Callback query handling will be expanded in Features #60, #61
                # For now, just log it
                logger.info(f"Callback query: {result.callback_data.action} for {result.callback_data.quote_id}")

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
