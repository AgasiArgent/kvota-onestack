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

# Import version service
from services.quote_version_service import create_quote_version, list_quote_versions, get_quote_version

# Import role service
from services.role_service import get_user_role_codes, get_session_user_roles, require_role, require_any_role

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
    """Navigation bar component"""
    user = session.get("user")
    if user:
        return Nav(
            Div(
                Ul(Li(Strong("Kvota OneStack"))),
                Ul(
                    Li(A("Dashboard", href="/dashboard")),
                    Li(A("Quotes", href="/quotes")),
                    Li(A("Customers", href="/customers")),
                    Li(A("New Quote", href="/quotes/new")),
                    Li(A("Settings", href="/settings")),
                    Li(A(f"Logout ({user.get('email', 'User')})", href="/logout")),
                ),
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
