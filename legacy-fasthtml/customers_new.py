"""Legacy FastHTML customer-creation routes — archived 2026-04-20 during Phase 6C-1.

These routes are broken post-migration-284 (Phase 5d exempt list).
Preserved for historical reference; NOT imported by main.py or api/app.py.
The user flow that formerly used these routes is served by Next.js
(customer creation via the inline dialog on /customers).

Contents:
  - GET/POST /customers/new — full page customer creation (with DaData INN lookup)
  - GET /api/customers/search — datalist typeahead
  - GET /api/customers/check-inn — global INN uniqueness check
  - GET /api/customers/{customer_id}/contacts — contact-person dropdown fragment
  - POST /api/customers/create-inline — inline creation from /quotes/new form
  - GET /api/suppliers/search — datalist typeahead for suppliers
  - GET /api/buyer-companies/search — datalist typeahead for buyer companies
  - GET /api/seller-companies/search — datalist typeahead for seller companies
  - GET /api/dadata/lookup-inn — DaData INN -> company info lookup
  - supplier_dropdown / buyer_company_dropdown / seller_company_dropdown helpers

To restore any route temporarily, copy the handler back to main.py and
import required helpers. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

import json as json_module
import uuid
from datetime import datetime

from fasthtml.common import (
    Button, Datalist, Div, Form, Group, Input, Label, Option, Script,
    Select, Small,
)
from starlette.responses import RedirectResponse, Response


# ============================================================================
# UI COMPONENTS — Reusable HTMX Dropdown Components (Feature UI-011)
# ============================================================================

def supplier_dropdown(
    name: str = "supplier_id",
    label: str = "Поставщик",
    selected_id: str = None,
    selected_label: str = None,
    required: bool = False,
    placeholder: str = "Начните печатать название...",
    help_text: str = None,
    cls: str = "",
    dropdown_id: str = None,
) -> Div:
    """
    Reusable HTMX-powered supplier dropdown component using datalist.

    Creates a searchable input with suggestions that fetches supplier options from
    /api/suppliers/search as user types. Uses HTML5 datalist for native autocomplete.

    Args:
        name: Form field name (default: "supplier_id")
        label: Label text displayed above the dropdown
        selected_id: Pre-selected supplier UUID (for edit forms)
        selected_label: Pre-selected supplier display text
        required: Whether field is required
        placeholder: Placeholder text for search input
        help_text: Optional help text below the dropdown
        cls: Additional CSS classes for the container
        dropdown_id: Custom ID for the dropdown

    Returns:
        Div: FastHTML element containing the complete dropdown component

    Usage:
        supplier_dropdown(
            name="supplier_id",
            label="Поставщик",
            required=True
        )
    """
    component_id = dropdown_id or f"sup-{uuid.uuid4().hex[:8]}"
    datalist_id = f"datalist-{component_id}"
    hidden_id = f"hidden-{component_id}"
    input_id = f"input-{component_id}"

    label_text = f"{label} *" if required else label
    help_element = Small(help_text, style="color: #666; display: block; margin-top: 0.25rem;") if help_text else None
    container_cls = f"supplier-dropdown {cls}".strip()

    # Inline script to sync datalist selection with hidden field and handle Enter key
    sync_script = Script(f"""
        (function() {{
            const input = document.getElementById('{input_id}');
            const datalist = document.getElementById('{datalist_id}');
            const hidden = document.getElementById('{hidden_id}');

            if (!input || !datalist || !hidden) return;

            function syncValue() {{
                const option = Array.from(datalist.options).find(opt => opt.value === input.value);
                hidden.value = option ? (option.getAttribute('data-id') || '') : '';
            }}

            input.addEventListener('input', syncValue);
            input.addEventListener('change', syncValue);

            input.addEventListener('keydown', function(e) {{
                if (e.key === 'Enter') {{
                    const options = Array.from(datalist.options);
                    if (options.length === 1) {{
                        input.value = options[0].value;
                        syncValue();
                        e.preventDefault();
                    }} else if (options.length > 1) {{
                        const exact = options.find(opt => opt.value === input.value);
                        if (exact) {{
                            syncValue();
                            e.preventDefault();
                        }} else {{
                            const partial = options.find(opt =>
                                opt.value.toLowerCase().includes(input.value.toLowerCase())
                            );
                            if (partial) {{
                                input.value = partial.value;
                                syncValue();
                                e.preventDefault();
                            }}
                        }}
                    }}
                }}
            }});
        }})();
    """)

    return Div(
        Label(
            label_text,
            Input(
                type="text",
                id=input_id,
                name="q",  # HTMX will send this value as query parameter
                list=datalist_id,
                value=selected_label or "",
                placeholder=placeholder,
                autocomplete="off",
                required=required,
                style="width: 100%;",
                **{
                    "hx-get": "/api/suppliers/search",
                    "hx-trigger": "input changed delay:300ms, focus",
                    "hx-target": f"#{datalist_id}",
                }
            ),
            Datalist(id=datalist_id),
            Input(type="hidden", name=name, id=hidden_id, value=selected_id or ""),
            help_element,
        ),
        sync_script,
        cls=container_cls,
        id=component_id,
    )


def buyer_company_dropdown(
    name: str = "buyer_company_id",
    label: str = "Компания-покупатель",
    selected_id: str = None,
    selected_label: str = None,
    required: bool = False,
    placeholder: str = "Начните печатать название...",
    help_text: str = None,
    cls: str = "",
    dropdown_id: str = None,
) -> Div:
    """
    Reusable HTMX-powered buyer company dropdown component using datalist.

    Creates a searchable input with suggestions for selecting our purchasing legal entities.
    Uses HTML5 datalist for native autocomplete without separate search field.

    Args:
        name: Form field name (default: "buyer_company_id")
        label: Label text
        selected_id: Pre-selected company UUID
        selected_label: Pre-selected company display text
        required: Whether field is required
        placeholder: Placeholder text
        help_text: Optional help text
        cls: Additional CSS classes
        dropdown_id: Custom ID

    Returns:
        Div: FastHTML element containing the input with datalist
    """
    component_id = dropdown_id or f"buy-{uuid.uuid4().hex[:8]}"
    datalist_id = f"datalist-{component_id}"
    hidden_id = f"hidden-{component_id}"
    input_id = f"input-{component_id}"

    label_text = f"{label} *" if required else label
    help_element = Small(help_text, style="color: #666; display: block; margin-top: 0.25rem;") if help_text else None
    container_cls = f"buyer-company-dropdown {cls}".strip()

    # Inline script to sync datalist selection with hidden field and handle Enter key
    sync_script = Script(f"""
        (function() {{
            const input = document.getElementById('{input_id}');
            const datalist = document.getElementById('{datalist_id}');
            const hidden = document.getElementById('{hidden_id}');

            if (!input || !datalist || !hidden) return;

            function syncValue() {{
                const option = Array.from(datalist.options).find(opt => opt.value === input.value);
                hidden.value = option ? (option.getAttribute('data-id') || '') : '';
            }}

            input.addEventListener('input', syncValue);
            input.addEventListener('change', syncValue);

            input.addEventListener('keydown', function(e) {{
                if (e.key === 'Enter') {{
                    const options = Array.from(datalist.options);
                    if (options.length === 1) {{
                        input.value = options[0].value;
                        syncValue();
                        e.preventDefault();
                    }} else if (options.length > 1) {{
                        const exact = options.find(opt => opt.value === input.value);
                        if (exact) {{
                            syncValue();
                            e.preventDefault();
                        }} else {{
                            const partial = options.find(opt =>
                                opt.value.toLowerCase().includes(input.value.toLowerCase())
                            );
                            if (partial) {{
                                input.value = partial.value;
                                syncValue();
                                e.preventDefault();
                            }}
                        }}
                    }}
                }}
            }});
        }})();
    """)

    return Div(
        Label(
            label_text,
            Input(
                type="text",
                id=input_id,
                name="q",  # HTMX will send this value as query parameter
                list=datalist_id,
                value=selected_label or "",
                placeholder=placeholder,
                autocomplete="off",
                required=required,
                style="width: 100%;",
                **{
                    "hx-get": "/api/buyer-companies/search",
                    "hx-trigger": "input changed delay:300ms, focus",
                    "hx-target": f"#{datalist_id}",
                }
            ),
            Datalist(id=datalist_id),
            Input(type="hidden", name=name, id=hidden_id, value=selected_id or ""),
            help_element,
        ),
        sync_script,
        cls=container_cls,
        id=component_id,
    )


def seller_company_dropdown(
    name: str = "seller_company_id",
    label: str = "Компания-продавец",
    selected_id: str = None,
    selected_label: str = None,
    required: bool = False,
    placeholder: str = "Начните печатать название...",
    help_text: str = None,
    cls: str = "",
    dropdown_id: str = None,
) -> Div:
    """
    Reusable HTMX-powered seller company dropdown component using datalist.

    Creates a searchable input with suggestions for selecting our selling legal entities
    at the quote level. Uses HTML5 datalist for native autocomplete.

    Args:
        name: Form field name (default: "seller_company_id")
        label: Label text
        selected_id: Pre-selected company UUID
        selected_label: Pre-selected company display text
        required: Whether field is required
        placeholder: Placeholder text
        help_text: Optional help text
        cls: Additional CSS classes
        dropdown_id: Custom ID

    Returns:
        Div: FastHTML element containing the input with datalist
    """
    component_id = dropdown_id or f"sel-{uuid.uuid4().hex[:8]}"
    datalist_id = f"datalist-{component_id}"
    hidden_id = f"hidden-{component_id}"
    input_id = f"input-{component_id}"

    label_text = f"{label} *" if required else label
    help_element = Small(help_text, style="color: #666; display: block; margin-top: 0.25rem;") if help_text else None
    container_cls = f"seller-company-dropdown {cls}".strip()

    # Inline script to sync datalist selection with hidden field and handle Enter key
    sync_script = Script(f"""
        (function() {{
            const input = document.getElementById('{input_id}');
            const datalist = document.getElementById('{datalist_id}');
            const hidden = document.getElementById('{hidden_id}');

            if (!input || !datalist || !hidden) return;

            function syncValue() {{
                const option = Array.from(datalist.options).find(opt => opt.value === input.value);
                hidden.value = option ? (option.getAttribute('data-id') || '') : '';
            }}

            input.addEventListener('input', syncValue);
            input.addEventListener('change', syncValue);

            input.addEventListener('keydown', function(e) {{
                if (e.key === 'Enter') {{
                    const options = Array.from(datalist.options);
                    if (options.length === 1) {{
                        input.value = options[0].value;
                        syncValue();
                        e.preventDefault();
                    }} else if (options.length > 1) {{
                        const exact = options.find(opt => opt.value === input.value);
                        if (exact) {{
                            syncValue();
                            e.preventDefault();
                        }} else {{
                            const partial = options.find(opt =>
                                opt.value.toLowerCase().includes(input.value.toLowerCase())
                            );
                            if (partial) {{
                                input.value = partial.value;
                                syncValue();
                                e.preventDefault();
                            }}
                        }}
                    }}
                }}
            }});
        }})();
    """)

    return Div(
        Label(
            label_text,
            Input(
                type="text",
                id=input_id,
                name="q",  # HTMX will send this value as query parameter
                list=datalist_id,
                value=selected_label or "",
                placeholder=placeholder,
                autocomplete="off",
                required=required,
                style="width: 100%;",
                **{
                    "hx-get": "/api/seller-companies/search",
                    "hx-trigger": "input changed delay:300ms, focus",
                    "hx-target": f"#{datalist_id}",
                }
            ),
            Datalist(id=datalist_id),
            Input(type="hidden", name=name, id=hidden_id, value=selected_id or ""),
            help_element,
        ),
        sync_script,
        cls=container_cls,
        id=component_id,
    )


# ============================================================================
# NEW CUSTOMER — full-page form (superseded by Next.js modal)
# ============================================================================

# @rt("/customers/new")  — decorator removed, file is archived and not mounted
def customers_new_get(session):
    """Redirect to /customers where the creation modal is."""
    return RedirectResponse("/customers", status_code=302)


# @rt("/customers/new")  — decorator removed, file is archived and not mounted
async def customers_new_post(inn: str = "", no_inn: str = "", session=None):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    customer_data = {
        "organization_id": user["org_id"],
        "manager_id": user["id"],
    }

    if no_inn or not inn.strip():
        # No-INN path: auto-generate name
        auto_name = f"Новый клиент {datetime.now().strftime('%Y%m%d-%H%M')}"
        customer_data["name"] = auto_name
    else:
        # INN path: call DaData for company info
        inn = inn.strip()
        customer_data["inn"] = inn
        try:
            from services.dadata_service import lookup_company_by_inn
            dadata_result = await lookup_company_by_inn(inn)
            if dadata_result:
                customer_data["name"] = dadata_result.get("name", f"Компания ИНН {inn}")
                customer_data["kpp"] = dadata_result.get("kpp")
                customer_data["ogrn"] = dadata_result.get("ogrn")
                customer_data["legal_address"] = dadata_result.get("address")
            else:
                customer_data["name"] = f"Компания ИНН {inn}"
        except Exception as e:
            print(f"DaData lookup failed for INN {inn}: {e}")
            customer_data["name"] = f"Компания ИНН {inn}"

    try:
        result = supabase.table("customers").insert(customer_data).execute()
        customer_id = result.data[0]["id"]
        return RedirectResponse(f"/customers/{customer_id}", status_code=303)

    except Exception as e:
        error_str = str(e)
        if "duplicate" in error_str.lower() or "уже существует" in error_str:
            error_msg = f"Клиент с ИНН '{inn}' уже существует в вашей организации."
        else:
            error_msg = f"Ошибка при создании клиента: {error_str}"

        return page_layout("Ошибка",
            Div(error_msg, style="background: #fee; border: 1px solid #c33; padding: 1rem; margin-bottom: 1rem; border-radius: 4px;"),
            Div(
                Form(
                    Div(
                        Label("ИНН", Input(name="inn", value=inn or "")),
                        style="margin-bottom: 16px;"
                    ),
                    Div(
                        btn("Создать", variant="primary", icon_name="check", type="submit"),
                        btn("Не знаю ИНН", variant="secondary", type="submit", name="no_inn", value="1"),
                        btn_link("Назад", href="/customers", variant="secondary"),
                        style="display: flex; gap: 8px;"
                    ),
                    method="post",
                    action="/customers/new"
                ),
                cls="card"
            ),
            session=session
        )


# ============================================================================
# API ENDPOINTS — Customer Search for HTMX Dropdown
# ============================================================================

# @rt("/api/customers/search")  — decorator removed, file is archived and not mounted
def customers_search(request, session, q: str = "", limit: int = 20):
    """Customer search for datalist typeahead on /quotes/new.
    Respects role-based visibility: sales-only users see only their customers."""
    # Dual auth: JWT (Next.js) or session (FastHTML HTMX)
    api_user = getattr(request.state, 'api_user', None)
    if api_user:
        user_meta = api_user.user_metadata or {}
        user = {
            "id": str(api_user.id),
            "email": api_user.email or "",
            "name": user_meta.get("name", api_user.email or ""),
            "org_id": user_meta.get("org_id"),
        }
    else:
        redirect = require_login(session)
        if redirect:
            return Option("Требуется авторизация", value="", disabled=True)
        user = session["user"]

    org_id = user.get("org_id")
    if not org_id:
        return Option("Организация не найдена", value="", disabled=True)

    from services.customer_service import search_customers, get_all_customers

    roles = get_user_role_codes(user["id"], org_id) if api_user else get_effective_roles(session)
    has_full_visibility = any(r in roles for r in ["admin", "top_manager", "head_of_sales"])
    is_sales_only = not has_full_visibility
    manager_id = user["id"] if is_sales_only else None

    try:
        if q and len(q.strip()) >= 1:
            customers = search_customers(
                organization_id=org_id,
                query=q.strip(),
                manager_id=manager_id,
                limit=min(limit, 50),
            )
        else:
            customers = get_all_customers(
                organization_id=org_id,
                manager_id=manager_id,
                limit=20,
            )

        options = []
        for c in customers:
            label = c.name
            if c.inn:
                label = f"{c.name} (ИНН {c.inn})"
            options.append(Option(
                label,
                value=label,
                **{"data-id": str(c.id)}
            ))

        if not options and q:
            options.append(Option(f"Клиенты не найдены: '{q}'", value="", disabled=True))

        return Group(*options)

    except Exception as e:
        print(f"Error in customer search API: {e}")
        return Option("Ошибка поиска", value="", disabled=True)


# IMPORTANT: check-inn must be defined BEFORE {customer_id}/contacts to avoid route conflict
# @rt("/api/customers/check-inn")  — decorator removed, file is archived and not mounted
def customers_check_inn(session, inn: str = ""):
    """Check if INN exists globally (across all orgs). Returns HTML fragment."""
    redirect = require_login(session)
    if redirect:
        return Div(Small("Требуется авторизация", style="color: #ef4444;"))

    inn = inn.strip() if inn else ""

    from services.dadata_service import validate_inn
    if not validate_inn(inn):
        return Div(Small("Неверный формат ИНН (нужно 10 или 12 цифр)", style="color: #ef4444;"),
                   style="padding: 8px;")

    from services.customer_service import customer_exists_globally
    if customer_exists_globally(inn):
        return Div(
            Div(
                f"Клиент с ИНН {inn} уже существует в системе.",
                style="font-weight: 600; color: #dc2626;"
            ),
            Div(
                "Обратитесь к руководителю для получения доступа.",
                style="color: #64748b; font-size: 13px; margin-top: 4px;"
            ),
            style="padding: 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; margin-top: 8px;"
        )

    # INN is free — signal to show the creation form fields and autofill name from DaData
    return Div(
        Small("ИНН свободен — можно создавать клиента", style="color: #22c55e;"),
        Script(f"""
            (function() {{
                // Clear the bridge input before DaData fills it
                var bridge = document.getElementById('dadata-name-bridge');
                if (bridge) bridge.value = '';
                // Look up company name from DaData and autofill
                htmx.ajax('GET', '/api/dadata/lookup-inn?inn={inn}', {{
                    target: '#inn-dadata-result',
                    swap: 'innerHTML'
                }});
                // Watch for DaData result to fill bridge input, then copy to visible name field
                var observer = new MutationObserver(function(mutations) {{
                    var bridgeInput = document.getElementById('dadata-name-bridge');
                    if (bridgeInput && bridgeInput.value) {{
                        var nameField = document.getElementById('new-customer-name');
                        if (nameField && !nameField.value) {{
                            nameField.value = bridgeInput.value;
                        }}
                        observer.disconnect();
                    }}
                }});
                var target = document.getElementById('inn-dadata-result');
                if (target) observer.observe(target, {{childList: true, subtree: true}});
                // Also poll briefly in case MutationObserver misses the event
                var attempts = 0;
                var poll = setInterval(function() {{
                    attempts++;
                    var bridgeInput = document.getElementById('dadata-name-bridge');
                    if (bridgeInput && bridgeInput.value) {{
                        var nameField = document.getElementById('new-customer-name');
                        if (nameField && !nameField.value) {{
                            nameField.value = bridgeInput.value;
                        }}
                        clearInterval(poll);
                        observer.disconnect();
                    }}
                    if (attempts > 20) clearInterval(poll);
                }}, 200);
            }})();
        """),
        style="padding: 8px;"
    )


# @rt("/api/customers/{customer_id}/contacts")  — decorator removed, file is archived and not mounted
def customers_contacts(session, customer_id: str):
    """Return contact person dropdown fragment for a customer. Used on /quotes/new."""
    redirect = require_login(session)
    if redirect:
        return ""

    supabase = get_supabase()
    try:
        result = supabase.table("customer_contacts") \
            .select("id, name, position, is_lpr") \
            .eq("customer_id", customer_id) \
            .order("is_lpr", desc=True) \
            .order("name") \
            .execute()
        contacts = result.data or []
    except Exception:
        contacts = []

    if not contacts:
        return ""

    return Div(
        Label("Контактное лицо", For="contact_person_id"),
        Select(
            Option("— Не выбрано —", value=""),
            *[Option(
                f"{c['name']}" + (f" ({c.get('position', '')})" if c.get('position') else ""),
                value=c["id"]
            ) for c in contacts],
            name="contact_person_id",
            id="contact_person_id",
            cls="form-input"
        ),
        cls="form-group",
        style="margin-top: 12px;"
    )


# @rt("/api/customers/create-inline")  — decorator removed, file is archived and not mounted
async def customers_create_inline(session, request):
    """Inline customer creation from /quotes/new form. Returns JSON."""
    redirect = require_login(session)
    if redirect:
        return Response(json_module.dumps({"error": "Требуется авторизация"}),
                        media_type="application/json", status_code=401)

    user = session["user"]
    try:
        body = await request.json()
    except Exception:
        return Response(json_module.dumps({"error": "Неверный формат запроса"}),
                        media_type="application/json", status_code=400)

    inn = (body.get("inn") or "").strip()
    name = (body.get("name") or "").strip()

    if not name:
        return Response(json_module.dumps({"error": "Укажите название клиента"}),
                        media_type="application/json", status_code=400)

    from services.customer_service import customer_exists_globally, create_customer
    from services.dadata_service import validate_inn

    if inn:
        if not validate_inn(inn):
            return Response(json_module.dumps({"error": f"Неверный формат ИНН: {inn}"}),
                            media_type="application/json", status_code=400)
        if customer_exists_globally(inn):
            return Response(json_module.dumps({
                "error": f"Клиент с ИНН {inn} уже существует в системе. Обратитесь к руководителю."
            }), media_type="application/json", status_code=409)

    try:
        customer = create_customer(
            organization_id=user["org_id"],
            name=name,
            inn=inn or None,
            manager_id=user["id"],
        )
        if customer is None:
            raise ValueError("create_customer returned None")

        return Response(
            json_module.dumps({"id": str(customer.id), "name": customer.name}),
            media_type="application/json"
        )
    except Exception as e:
        return Response(json_module.dumps({"error": f"Ошибка: {str(e)}"}),
                        media_type="application/json")


# ============================================================================
# API ENDPOINTS — Supplier Search for HTMX Dropdown (Feature UI-011)
# ============================================================================

# @rt("/api/suppliers/search")  — decorator removed, file is archived and not mounted
def suppliers_search(session, q: str = "", country: str = "", limit: int = 20):
    """
    Search suppliers for HTMX dropdown autocomplete.

    Query Parameters:
        q: Search query (matches name, supplier_code, or INN)
        country: Filter by country code
        limit: Maximum results (default 20, max 50)

    Returns:
        HTML fragment with <option> elements for dropdown
    """
    redirect = require_login(session)
    if redirect:
        return Option("Требуется авторизация", value="", disabled=True)

    user = session["user"]
    org_id = user.get("org_id")  # Fixed: session stores 'org_id' not 'organization_id'

    if not org_id:
        return Option("Организация не найдена", value="", disabled=True)

    try:
        from services.supplier_service import search_suppliers, get_all_suppliers, format_supplier_for_dropdown

        if q and len(q.strip()) > 0:
            suppliers = search_suppliers(
                organization_id=org_id,
                query=q.strip(),
                is_active=True,
                limit=min(limit, 50),
            )
        else:
            suppliers = get_all_suppliers(
                organization_id=org_id,
                is_active=True,
                limit=min(limit, 50),
            )

        options = []
        for sup in suppliers:
            label = format_supplier_for_dropdown(sup)
            # For datalist: value = display text, data-id = UUID
            options.append(Option(
                label.get("label", ""),
                value=label.get("label", ""),
                **{"data-id": label.get("value", "")}
            ))

        if len(suppliers) == 0 and q:
            options.append(Option(f"Ничего не найдено по запросу '{q}'", value="", disabled=True))

        return Group(*options)

    except Exception as e:
        print(f"Error in supplier search API: {e}")
        return Option(f"Ошибка: {str(e)}", value="", disabled=True)


# @rt("/api/buyer-companies/search")  — decorator removed, file is archived and not mounted
def buyer_companies_search(session, q: str = "", limit: int = 20):
    """
    Search buyer companies for HTMX dropdown autocomplete.

    Query Parameters:
        q: Search query (matches name, company_code, or INN)
        limit: Maximum results (default 20, max 50)

    Returns:
        HTML fragment with <option> elements for dropdown
    """
    redirect = require_login(session)
    if redirect:
        return Option("Требуется авторизация", value="", disabled=True)

    user = session["user"]
    org_id = user.get("org_id")

    if not org_id:
        return Option("Организация не найдена", value="", disabled=True)

    try:
        from services.buyer_company_service import search_buyer_companies, get_all_buyer_companies, format_buyer_company_for_dropdown

        if q and len(q.strip()) > 0:
            companies = search_buyer_companies(
                organization_id=org_id,
                query=q.strip(),
                is_active=True,
                limit=min(limit, 50),
            )
        else:
            companies = get_all_buyer_companies(
                organization_id=org_id,
                is_active=True,
                limit=min(limit, 50),
            )

        options = []
        for comp in companies:
            label = format_buyer_company_for_dropdown(comp)
            # For datalist: value = display text, data-id = UUID
            options.append(Option(
                label.get("label", ""),
                value=label.get("label", ""),
                **{"data-id": label.get("value", "")}
            ))

        if len(companies) == 0 and q:
            options.append(Option(f"Ничего не найдено по запросу '{q}'", value="", disabled=True))

        return Group(*options)

    except Exception as e:
        print(f"Error in buyer company search API: {e}")
        return Option(f"Ошибка: {str(e)}", value="", disabled=True)


# @rt("/api/seller-companies/search")  — decorator removed, file is archived and not mounted
def seller_companies_search(session, q: str = "", limit: int = 20):
    """
    Search seller companies for HTMX dropdown autocomplete.

    Query Parameters:
        q: Search query (matches name, supplier_code, or INN)
        limit: Maximum results (default 20, max 50)

    Returns:
        HTML fragment with <option> elements for dropdown
    """
    redirect = require_login(session)
    if redirect:
        return Option("Требуется авторизация", value="", disabled=True)

    user = session["user"]
    org_id = user.get("org_id")

    if not org_id:
        return Option("Организация не найдена", value="", disabled=True)

    try:
        from services.seller_company_service import search_seller_companies, get_all_seller_companies, format_seller_company_for_dropdown

        if q and len(q.strip()) > 0:
            companies = search_seller_companies(
                organization_id=org_id,
                query=q.strip(),
                is_active=True,
                limit=min(limit, 50),
            )
        else:
            companies = get_all_seller_companies(
                organization_id=org_id,
                is_active=True,
                limit=min(limit, 50),
            )

        options = []
        for comp in companies:
            label = format_seller_company_for_dropdown(comp)
            # For datalist: value = display text, data-id = UUID
            options.append(Option(
                label.get("label", ""),
                value=label.get("label", ""),
                **{"data-id": label.get("value", "")}
            ))

        if len(companies) == 0 and q:
            options.append(Option(f"Ничего не найдено по запросу '{q}'", value="", disabled=True))

        return Group(*options)

    except Exception as e:
        print(f"Error in seller company search API: {e}")
        return Option(f"Ошибка: {str(e)}", value="", disabled=True)


# ============================================================================
# DADATA INN LOOKUP API
# ============================================================================

# @rt("/api/dadata/lookup-inn")  — decorator removed, file is archived and not mounted
async def dadata_lookup_inn(inn: str, session):
    """Look up company info by INN via DaData API. Returns HTML fragment for HTMX."""
    redirect = require_login(session)
    if redirect:
        return Div(Small("Требуется авторизация", style="color: #ef4444;"))

    try:
        from services.dadata_service import validate_inn, lookup_company_by_inn  # normalize_dadata_result used internally

        inn = inn.strip() if inn else ""

        if not validate_inn(inn):
            return Div(Small("Неверный формат ИНН", style="color: #ef4444;"))

        result = await lookup_company_by_inn(inn)

        if result is None:
            return Div(Small(f"Компания с ИНН {inn} не найдена", style="color: #94a3b8;"))

        # Return HTML with company info + JS to auto-fill form fields
        name = result.get("name", "")
        address = result.get("address", "")
        director = result.get("director", "")
        status_text = "Действующая" if result.get("is_active") else "Ликвидирована"
        status_color = "#22c55e" if result.get("is_active") else "#ef4444"

        return Div(
            Div(
                Small(f"✓ {name}", style="color: #22c55e; font-weight: 600;"),
                Small(f" · {status_text}", style=f"color: {status_color}; font-size: 11px;"),
                style="margin-bottom: 4px;"
            ),
            Small(f"Юр. адрес: {address}", style="color: #64748b; font-size: 11px; display: block;") if address else "",
            Small(f"Руководитель: {director}", style="color: #64748b; font-size: 11px; display: block;") if director else "",
            Script(f"""
                (function() {{
                    var nameField = document.querySelector('input[name="name"]');
                    if (nameField && !nameField.value) {{ nameField.value = {repr(name)}; }}
                    var addrField = document.querySelector('textarea[name="legal_address"]');
                    if (addrField && !addrField.value) {{ addrField.value = {repr(address)}; }}
                }})();
            """),
            style="padding: 8px; background: #f0fdf4; border-radius: 6px; margin-top: 4px;"
        )
    except Exception as e:
        return Div(Small("Ошибка при поиске компании", style="color: #ef4444;"))
