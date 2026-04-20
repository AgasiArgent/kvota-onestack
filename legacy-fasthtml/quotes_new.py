"""Legacy FastHTML /quotes/new — archived 2026-04-20 during Phase 6C-1.

These routes are broken post-migration-284 (Phase 5d exempt list).
Preserved for historical reference; NOT imported by main.py or api/app.py.
The user flow that formerly used these routes is served by Next.js
(quote creation via create-quote-dialog.tsx).

To restore any route temporarily, copy the handler back to main.py and
import required helpers. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime

from fasthtml.common import (
    A, Button, Datalist, Div, Form, H1, H4, Input, Label, Option, Script,
    Select, Small,
)
from starlette.responses import RedirectResponse

# The following helpers live in main.py and are imported when this file
# is revived. They are NOT imported here because this module is archived
# and not executed.
#   - page_layout, icon, btn_link, require_login, get_supabase
#   - customer_search_dropdown (defined below in this file)


def customer_search_dropdown(
    selected_id: str = None,
    selected_label: str = None,
) -> Div:
    """
    Searchable customer selector for /quotes/new form.
    Uses datalist typeahead searching /api/customers/search.
    Includes inline customer creation panel with INN check + DaData autofill.
    Contact person dropdown loaded via HTMX after customer selection.
    """
    input_id = "input-cust-search"
    datalist_id = "datalist-cust-search"
    hidden_id = "hidden-cust-search"

    sync_and_contacts_script = Script("""
        (function() {
            const input = document.getElementById('input-cust-search');
            const datalist = document.getElementById('datalist-cust-search');
            const hidden = document.getElementById('hidden-cust-search');
            const contactsSection = document.getElementById('contact-person-section');

            if (!input || !datalist || !hidden) return;

            // Track last confirmed selection to survive datalist refreshes
            var selectedId = hidden.value || '';
            var selectedLabel = input.value || '';

            function getBtn() { return document.getElementById('btn-create-quote'); }

            function syncValue() {
                const btn = getBtn();
                const option = Array.from(datalist.options).find(opt => opt.value === input.value);
                const newId = option ? (option.getAttribute('data-id') || '') : '';

                // If input text matches our last confirmed selection, keep it
                // (HTMX may have refreshed the datalist with non-matching results)
                if (!newId && selectedId && input.value === selectedLabel) {
                    if (btn) btn.disabled = false;
                    return;
                }

                const changed = hidden.value !== newId;
                hidden.value = newId;
                if (btn) btn.disabled = !newId;

                if (newId) {
                    selectedId = newId;
                    selectedLabel = input.value;
                } else {
                    selectedId = '';
                    selectedLabel = '';
                }

                if (newId && changed) {
                    htmx.ajax('GET', '/api/customers/' + newId + '/contacts', {
                        target: '#contact-person-section',
                        swap: 'innerHTML'
                    });
                }
                if (!newId && contactsSection) {
                    contactsSection.innerHTML = '';
                }
                var createBtn = document.getElementById('btn-show-create-customer');
                if (createBtn) {
                    createBtn.style.display = (!newId && input.value.length > 0) ? 'inline-block' : 'none';
                }
            }

            input.addEventListener('input', syncValue);
            input.addEventListener('change', syncValue);
            // Pre-selected: defer init until full DOM is rendered (btn doesn't exist yet)
            if (selectedId) {
                document.addEventListener('DOMContentLoaded', function() {
                    var b = getBtn();
                    if (b) b.disabled = false;
                    if (selectedId) {
                        htmx.ajax('GET', '/api/customers/' + selectedId + '/contacts', {
                            target: '#contact-person-section',
                            swap: 'innerHTML'
                        });
                    }
                });
            }
        })();
    """)

    create_panel_script = Script("""
        function showCreateCustomerPanel() {
            document.getElementById('create-customer-panel').style.display = 'block';
            document.getElementById('btn-show-create-customer').style.display = 'none';
        }
        function checkInnAndShow() {
            var inn = document.getElementById('new-customer-inn').value.trim();
            if (!inn) return;
            htmx.ajax('GET', '/api/customers/check-inn?inn=' + encodeURIComponent(inn), {
                target: '#inn-check-result',
                swap: 'innerHTML'
            });
        }
        function submitNewCustomer() {
            var inn = document.getElementById('new-customer-inn').value.trim();
            var nameField = document.getElementById('new-customer-name');
            var name = nameField ? nameField.value.trim() : '';
            if (!name) { alert('Укажите название клиента'); return; }
            fetch('/api/customers/create-inline', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({inn: inn, name: name})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.error) { alert(data.error); return; }
                document.getElementById('input-cust-search').value = data.name;
                document.getElementById('hidden-cust-search').value = data.id;
                var btn = document.getElementById('btn-create-quote');
                if (btn) btn.disabled = false;
                document.getElementById('create-customer-panel').style.display = 'none';
                htmx.ajax('GET', '/api/customers/' + data.id + '/contacts', {
                    target: '#contact-person-section',
                    swap: 'innerHTML'
                });
            })
            .catch(function(e) { alert('Ошибка создания клиента'); });
        }
    """)

    return Div(
        # Label + search input
        Div(
            Label("Клиент *", For=input_id),
            Input(
                type="text",
                id=input_id,
                name="q",
                list=datalist_id,
                value=selected_label or "",
                placeholder="Начните вводить название или ИНН...",
                autocomplete="off",
                required=False,
                cls="form-input",
                **{
                    "hx-get": "/api/customers/search",
                    "hx-trigger": "input changed delay:300ms, focus",
                    "hx-target": f"#{datalist_id}",
                }
            ),
            Datalist(id=datalist_id),
            Input(type="hidden", name="customer_id", id=hidden_id, value=selected_id or ""),
            cls="form-group"
        ),
        # "Создать нового клиента" button (shown when text entered but no match)
        Button(
            "+ Создать нового клиента",
            type="button",
            id="btn-show-create-customer",
            onclick="showCreateCustomerPanel()",
            cls="btn btn--link",
            style="display: none; font-size: 13px; margin-top: 4px;"
        ),
        # Inline creation panel (hidden by default)
        Div(
            H4("Новый клиент", style="margin: 0 0 12px 0; font-size: 15px;"),
            Div(
                Label("ИНН", For="new-customer-inn"),
                Div(
                    Input(
                        type="text",
                        id="new-customer-inn",
                        name="_new_customer_inn",
                        placeholder="ИНН компании (10 или 12 цифр)",
                        cls="form-input",
                        style="flex: 1;",
                    ),
                    Button("Проверить", type="button", onclick="checkInnAndShow()",
                           cls="btn btn--secondary", style="white-space: nowrap;"),
                    style="display: flex; gap: 8px;"
                ),
                cls="form-group"
            ),
            Div(id="inn-check-result"),
            Div(id="inn-dadata-result"),
            # Hidden input for DaData auto-fill (DaData JS targets input[name="name"])
            Input(type="hidden", name="name", id="dadata-name-bridge"),
            Div(
                Label("Название *", For="new-customer-name"),
                Input(type="text", id="new-customer-name", name="_new_customer_name",
                      placeholder="Автозаполнится из ИНН или введите вручную", cls="form-input"),
                cls="form-group"
            ),
            Div(
                Button("Создать клиента", type="button",
                       id="btn-create-customer-inline",
                       onclick="submitNewCustomer()",
                       cls="btn btn--primary"),
                Button("Отмена", type="button",
                       onclick="document.getElementById('create-customer-panel').style.display='none'; document.getElementById('btn-show-create-customer').style.display='inline-block';",
                       cls="btn btn--secondary"),
                cls="form-actions"
            ),
            id="create-customer-panel",
            style="display: none; padding: 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 8px;"
        ),
        # Contact person (loaded after customer selected)
        Div(id="contact-person-section"),
        sync_and_contacts_script,
        create_panel_script,
        id="cust-search",
    )


# @rt("/quotes/new")  — decorator removed, file is archived and not mounted
def get(session, customer_id: str = ""):
    """Show quote creation form with searchable customer selector."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    from services.seller_company_service import get_all_seller_companies

    seller_companies = get_all_seller_companies(organization_id=user["org_id"], is_active=True)

    # If customer_id is pre-provided (e.g. from customer detail page), look up name
    selected_label = None
    if customer_id:
        from services.customer_service import get_customer
        cust = get_customer(customer_id)
        if cust:
            selected_label = cust.name
            if cust.inn:
                selected_label = f"{cust.name} (ИНН {cust.inn})"

    _section_hdr = "font-size: 0.8rem; font-weight: 600; color: #374151; margin: 0 0 0.75rem 0; display: flex; align-items: center; gap: 0.5rem;"
    _section_card = "background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb; margin-bottom: 1rem;"

    return page_layout("Новый КП",
        H1(icon("file-plus", size=28), " Новый КП", cls="page-header"),
        Form(
            # Section 1: Customer + Contact
            Div(
                Div(icon("building-2", size=16), "Клиент и контакт", style=_section_hdr),
                customer_search_dropdown(
                    selected_id=customer_id if customer_id else None,
                    selected_label=selected_label,
                ),
                # Seller company (optional)
                Div(
                    Label("Наше юрлицо", For="seller_company_id"),
                    Select(
                        Option("-- Не указано --", value=""),
                        *[Option(sc.name, value=str(sc.id)) for sc in seller_companies],
                        name="seller_company_id", id="seller_company_id", cls="form-input"
                    ),
                    cls="form-group"
                ),
                cls="card", style=_section_card
            ),
            # Section 2: Delivery details
            Div(
                Div(icon("truck", size=16), "Доставка", style=_section_hdr),
                # Delivery city + country in one row
                Div(
                    Div(
                        Label("Страна", For="delivery_country"),
                        Input(name="delivery_country", id="delivery_country", type="text",
                              placeholder="Россия", cls="form-input"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Город", For="delivery_city"),
                        Input(name="delivery_city", id="delivery_city", type="text",
                              placeholder="Москва", cls="form-input"),
                        cls="form-group"
                    ),
                    cls="form-row"
                ),
                # Delivery method
                Div(
                    Label("Способ доставки", For="delivery_method"),
                    Select(
                        Option("-- Не указан --", value=""),
                        Option("Авиа", value="air"),
                        Option("Авто", value="auto"),
                        Option("Море", value="sea"),
                        Option("Мультимодально", value="multimodal"),
                        name="delivery_method", id="delivery_method", cls="form-input"
                    ),
                    cls="form-group"
                ),
                cls="card", style=_section_card
            ),
            # Actions
            Div(
                Button("Создать КП", type="submit", id="btn-create-quote", cls="btn btn--primary", disabled=True),
                A("Отмена", href="/quotes", cls="btn btn--secondary"),
                cls="form-actions"
            ),
            method="post", action="/quotes/new",
            style="max-width: 640px;"
        ),
        session=session
    )


# @rt("/quotes/new")  — decorator removed, file is archived and not mounted
def post(session,
         customer_id: str = "",
         contact_person_id: str = "",
         seller_company_id: str = "",
         delivery_city: str = "",
         delivery_country: str = "",
         delivery_method: str = ""):
    """Create a new draft quote from form submission."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not customer_id:
        return RedirectResponse("/quotes/new", status_code=303)

    user = session["user"]
    supabase = get_supabase()

    try:
        # Generate IDN and insert with retry for concurrent creation
        max_retries = 3
        for attempt in range(max_retries):
            # Find max IDN for current month, increment
            month_prefix = f"Q-{datetime.now().strftime('%Y%m')}-"
            existing_result = supabase.table("quotes") \
                .select("idn_quote") \
                .eq("organization_id", user["org_id"]) \
                .like("idn_quote", f"{month_prefix}%") \
                .order("idn_quote", desc=True) \
                .limit(1) \
                .is_("deleted_at", None) \
                .execute()

            if existing_result.data and existing_result.data[0].get("idn_quote"):
                last_idn = existing_result.data[0]["idn_quote"]
                try:
                    last_num = int(last_idn.split("-")[-1])
                except (ValueError, IndexError):
                    last_num = 0
                quote_num = last_num + 1
            else:
                quote_num = 1

            idn_quote = f"{month_prefix}{quote_num:04d}"

            insert_data = {
                "idn_quote": idn_quote,
                "title": "Новый КП",
                "customer_id": customer_id,
                "organization_id": user["org_id"],
                "currency": "RUB",
                "delivery_terms": "DDP",
                "status": "draft",
                "created_by": user["id"],
                "seller_company_id": seller_company_id if seller_company_id else None,
                "contact_person_id": contact_person_id if contact_person_id else None,
                "delivery_city": delivery_city.strip() if delivery_city else None,
                "delivery_country": delivery_country.strip() if delivery_country else None,
                "delivery_method": delivery_method if delivery_method else None,
            }

            try:
                result = supabase.table("quotes").insert(insert_data).execute()
                new_quote = result.data[0]
                return RedirectResponse(f"/quotes/{new_quote['id']}", status_code=303)
            except Exception as insert_err:
                if "23505" in str(insert_err) and attempt < max_retries - 1:
                    # Duplicate key — retry with next number
                    continue
                raise

    except Exception as e:
        return page_layout("Ошибка",
            Div(f"Ошибка создания КП: {str(e)}", cls="alert alert-error"),
            btn_link("Назад", href="/quotes/new", variant="secondary", icon_name="arrow-left"),
            session=session
        )
