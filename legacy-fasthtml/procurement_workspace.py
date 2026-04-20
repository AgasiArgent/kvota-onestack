"""Legacy FastHTML /procurement/{quote_id} + 7 /api/procurement HTMX endpoints.

Archived 2026-04-20 during Phase 6C-1.

These routes are broken post-migration-284 (Phase 5d exempt list).
Preserved for historical reference; NOT imported by main.py or api/app.py.
The user flow that formerly used these routes is served by Next.js
(/procurement/kanban for invoice list, /quotes/[id] for the procurement
step, and inline item editing).

Contents:
  - GET /procurement/{quote_id} — invoice-first procurement workspace page
  - POST   /api/procurement/{quote_id}/invoices — create invoice
  - PATCH  /api/procurement/{quote_id}/invoices/update — update invoice
  - DELETE /api/procurement/{quote_id}/invoices/{invoice_id} — delete invoice
  - POST   /api/procurement/{quote_id}/invoices/{invoice_id}/complete
  - POST   /api/procurement/{quote_id}/invoices/{invoice_id}/reopen
  - POST   /api/procurement/{quote_id}/items/assign — bulk-assign items to invoice
  - POST   /api/procurement/{quote_id}/complete — complete procurement stage
  - render_invoices_list() helper — was used by legacy HTMX swaps

To restore any route temporarily, copy the handler back to main.py and
re-apply the @rt decorator. Imports (page_layout, quote_header,
workflow_progress_bar, quote_detail_tabs, icon, btn, btn_link, Tr, Td,
Table, Thead, Tbody, P, Span, H1, get_supabase, get_assigned_brands,
require_login, user_has_any_role, get_documents_for_entity, STATUS_NAMES,
WorkflowStatus, complete_procurement, is_procurement_complete,
check_edit_permission, maybe_advance_after_distribution,
send_procurement_invoice_complete_notification, _build_sales_checklist_card,
etc.) must be restored as well.

Not recommended — rewrite via Next.js + FastAPI instead.
"""
# flake8: noqa
# type: ignore

import json
import logging
from datetime import datetime

from fasthtml.common import (
    A, Button, Datalist, Div, Form, H1, H4, Input, Label, Option, P, Script,
    Select, Small, Span, Table, Tbody, Td, Th, Thead, Tr,
)
from starlette.responses import JSONResponse, RedirectResponse


# @rt("/procurement/{quote_id}")  # decorator removed; file is archived and not mounted
def get(quote_id: str, session):
    """
    Procurement workspace - single-page invoice-first design.

    Layout:
    - Left panel: Invoice list with create/edit functionality
    - Right panel: Items table (Handsontable) with price entry

    Workflow:
    1. Create invoice (supplier, buyer, currency)
    2. Assign items to invoice
    3. Enter prices (copy-paste from Excel supported)
    4. Set invoice weight/volume
    5. Complete procurement
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has procurement role
    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    quote = quote_result.data
    if not quote:
        return page_layout("Not Found",
            Div(
                H1("КП не найдено"),
                P("КП не существует или у вас нет доступа."),
                btn_link("Назад к задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
                cls="card"
            ),
            session=session
        )

    # Check if user is admin or head_of_procurement - bypass brand filtering
    is_admin = user_has_any_role(session, ["admin", "head_of_procurement"])

    # Get user's assigned brands (admin sees all)
    my_brands = get_assigned_brands(user_id, org_id) if not is_admin else []
    my_brands_lower = [b.lower() for b in my_brands]

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    all_items = items_result.data or []

    # Filter items for my brands (handle None brand values) - admin sees all
    if is_admin:
        my_items = all_items
    else:
        my_items = [item for item in all_items
                    if (item.get("brand") or "").lower() in my_brands_lower]

    # Get existing invoices for this quote
    invoices_result = supabase.table("invoices") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    invoices = invoices_result.data or []

    # Build invoice map for quick lookup
    invoice_map = {inv["id"]: inv for inv in invoices}

    # Get supplier names
    supplier_ids = list(set(inv.get("supplier_id") for inv in invoices if inv.get("supplier_id")))
    suppliers = {}
    if supplier_ids:
        suppliers_result = supabase.table("suppliers").select("id, name").in_("id", supplier_ids).execute()
        suppliers = {s["id"]: s["name"] for s in suppliers_result.data or []}

    # Get buyer company names
    buyer_company_ids = list(set(inv.get("buyer_company_id") for inv in invoices if inv.get("buyer_company_id")))
    buyer_companies = {}
    if buyer_company_ids:
        buyers_result = supabase.table("buyer_companies").select("id, name, company_code").in_("id", buyer_company_ids).execute()
        buyer_companies = {b["id"]: {"name": b["name"], "code": b.get("company_code", "")} for b in buyers_result.data or []}

    # Calculate progress
    total_items = len(my_items)
    priced_items = len([i for i in my_items if i.get("purchase_price_original")])
    assigned_items = len([i for i in my_items if i.get("invoice_id")])
    completed_items = len([i for i in my_items if i.get("procurement_status") == "completed"])

    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"
    workflow_status = quote.get("workflow_status", "draft")
    quote_idn = quote.get("idn_quote", f"#{quote_id[:8]}")

    # Check for revision status
    revision_department = quote.get("revision_department")
    revision_comment = quote.get("revision_comment")
    is_revision = revision_department == "procurement" and workflow_status == "pending_procurement"

    # Check if quote is in the right status for editing
    can_edit = workflow_status in ["pending_procurement", "draft"]

    # Currency symbols for display
    currency_symbols = {"USD": "$", "EUR": "€", "RUB": "₽", "CNY": "¥", "TRY": "₺"}

    # Get IDs of invoices still in procurement (not completed)
    pending_invoice_ids = set(
        inv["id"] for inv in invoices
        if inv.get("status") == "pending_procurement"
    )

    # Filter items: show only items that need work
    # Hide: items in completed invoices (already processed)
    # Hide: items marked unavailable (no action needed)
    items_to_show = [
        item for item in my_items
        if (not item.get("invoice_id") and not item.get("is_unavailable", False))
        or item.get("invoice_id") in pending_invoice_ids
    ]

    # Prepare items data for Handsontable
    items_for_handsontable = []
    for idx, item in enumerate(items_to_show):
        inv = invoice_map.get(item.get("invoice_id"))
        items_for_handsontable.append({
            'id': item.get('id'),
            'brand': item.get('brand', ''),
            'product_name': item.get('product_name', ''),
            'product_code': item.get('product_code', ''),
            'idn_sku': item.get('idn_sku', ''),
            'supplier_sku': item.get('supplier_sku', ''),
            'quantity': item.get('quantity', 1),
            'price': item.get('purchase_price_original') if item.get('purchase_price_original') is not None else '',
            'production_time': item.get('production_time_days') if item.get('production_time_days') is not None else '',
            'weight_kg': item.get('weight_in_kg') if item.get('weight_in_kg') is not None else '',
            'volume_m3': item.get('volume_m3') if item.get('volume_m3') is not None else '',
            'price_includes_vat': item.get('price_includes_vat', False),
            'is_unavailable': item.get('is_unavailable', False),
            'invoice_id': item.get('invoice_id') or '',
            'invoice_label': f"#{invoices.index(inv)+1}" if inv else '',
        })

    items_json = json.dumps(items_for_handsontable)

    # Fetch documents for all invoices (supplier_invoice entity type)
    invoice_documents = {}
    for inv in invoices:
        docs = get_documents_for_entity("supplier_invoice", inv["id"])
        if docs:
            invoice_documents[inv["id"]] = docs[0]  # Take first (most recent) document

    # Prepare invoices data for JavaScript
    invoices_for_js = []
    for idx, inv in enumerate(invoices, 1):
        supp = suppliers.get(inv.get("supplier_id"), "—")
        buyer = buyer_companies.get(inv.get("buyer_company_id"), {})
        doc = invoice_documents.get(inv['id'])
        invoices_for_js.append({
            'id': inv['id'],
            'number': idx,
            'invoice_number': inv.get('invoice_number', ''),
            'supplier_id': inv.get('supplier_id'),
            'supplier_name': supp,
            'buyer_company_id': inv.get('buyer_company_id'),
            'buyer_name': buyer.get('name', '—'),
            'buyer_code': buyer.get('code', ''),
            'currency': inv.get('currency', 'USD'),
            'currency_symbol': currency_symbols.get(inv.get('currency', 'USD'), inv.get('currency', '')),
            'total_weight_kg': inv.get('total_weight_kg'),
            'total_volume_m3': inv.get('total_volume_m3'),
            'height_m': inv.get('height_m'),
            'length_m': inv.get('length_m'),
            'width_m': inv.get('width_m'),
            'package_count': inv.get('package_count'),
            'procurement_notes': inv.get('procurement_notes', ''),
            'pickup_location_id': inv.get('pickup_location_id'),
            'has_document': doc is not None,
            'document_id': doc.id if doc else None,
            'document_filename': doc.original_filename if doc else None,
        })

    invoices_json = json.dumps(invoices_for_js)

    # Count unassigned items
    unassigned_count = len([i for i in my_items if not i.get("invoice_id")])

    # Build invoice cards for left panel
    def invoice_card(inv, idx):
        supp = suppliers.get(inv.get("supplier_id"), "Поставщик не указан")
        buyer = buyer_companies.get(inv.get("buyer_company_id"), {})
        buyer_name = buyer.get("name", "Компания не указана")
        currency = inv.get("currency", "USD")
        currency_sym = currency_symbols.get(currency, currency)
        weight = inv.get("total_weight_kg")
        volume = inv.get("total_volume_m3")
        status = inv.get("status", "pending_procurement")
        is_completed = status != "pending_procurement"
        has_document = inv["id"] in invoice_documents

        # Count items in this invoice
        items_in_invoice = len([i for i in my_items if i.get("invoice_id") == inv["id"]])

        # Calculate total for this invoice
        total_sum = sum(
            (item.get("purchase_price_original", 0) or 0) * (item.get("quantity", 0) or 0)
            for item in my_items if item.get("invoice_id") == inv["id"]
        )

        # Status indicator and styling
        status_labels = {
            "pending_procurement": None,
            "pending_logistics": "→ Логистика",
            "pending_customs": "→ Таможня",
            "completed": "Завершён"
        }
        status_label = status_labels.get(status)

        # Gradient card styling based on status
        if is_completed:
            card_bg = "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)"
            border_color = "#10b981"
            header_icon = icon("check-circle", size=16, color="#10b981")
        else:
            card_bg = "linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%)"
            border_color = "#3b82f6"
            header_icon = icon("package", size=16, color="#3b82f6")

        # Collect items belonging to this invoice for the details table
        invoice_items_list = [item for item in my_items if item.get("invoice_id") == inv["id"]]

        # Build invoice_items_table rows for the details section
        invoice_items_table = []
        for item in invoice_items_list:
            item_name = item.get("product_name") or "—"
            item_qty = item.get("quantity", 0) or 0
            item_price = item.get("purchase_price_original", 0) or 0
            item_sku = item.get("product_code") or ""
            item_supplier_sku = item.get("supplier_sku") or ""
            item_idn_sku = item.get("idn_sku") or ""
            # Show SKU replacement badge when supplier_sku differs from idn_sku
            sku_cell_content = []
            if item_sku:
                sku_cell_content.append(Span(item_sku, style="font-family: monospace;"))
            if item_supplier_sku and item_supplier_sku != item_idn_sku:
                sku_cell_content.append(
                    Span(f" → {item_supplier_sku}",
                         style="font-family: monospace; color: #b45309; background: #fffbeb; padding: 0 4px; border-radius: 3px; font-weight: 600; font-size: 0.7rem;")
                )
            invoice_items_table.append(
                Tr(
                    Td(*sku_cell_content if sku_cell_content else ["—"], style="padding: 0.25rem 0.5rem; font-size: 0.8rem; border-bottom: 1px solid #f1f5f9;"),
                    Td(item_name, style="padding: 0.25rem 0.5rem; font-size: 0.8rem; border-bottom: 1px solid #f1f5f9;"),
                    Td(str(item_qty), style="padding: 0.25rem 0.5rem; font-size: 0.8rem; text-align: center; border-bottom: 1px solid #f1f5f9;"),
                    Td(f"{item_price:,.2f} {currency_sym}", style="padding: 0.25rem 0.5rem; font-size: 0.8rem; text-align: right; border-bottom: 1px solid #f1f5f9;"),
                )
            )

        return Div(
            # Invoice header with chevron toggle
            Div(
                Div(
                    header_icon,
                    Span(f" Инвойс #{idx}", style="font-weight: 600; font-size: 1rem; margin-left: 6px;"),
                    style="display: flex; align-items: center;"
                ),
                Div(
                    Span(f"{items_in_invoice} поз.", style="font-size: 0.75rem; color: #64748b; background: #e2e8f0; padding: 0.125rem 0.5rem; border-radius: 999px; margin-right: 0.5rem;"),
                    Span(icon("chevron-down", size=14, color="#64748b"),
                         id=f"invoice-chevron-{inv['id']}",
                         style="transition: transform 0.2s; display: inline-flex; align-items: center;"),
                    style="display: flex; align-items: center;"
                ),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;"
            ),

            # Supplier → Buyer
            Div(
                Span(supp, style="font-size: 0.875rem; color: #374151;"),
                Span(" → ", style="color: #94a3b8;"),
                Span(buyer_name, style="font-size: 0.875rem; color: #374151;"),
                style="margin-bottom: 0.5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
            ),

            # Status label for completed invoices
            Div(
                icon("check", size=12, color="#059669"),
                Span(f" {status_label}", style="font-size: 0.75rem; color: #059669; font-weight: 500;"),
                style="margin-bottom: 0.5rem; display: flex; align-items: center;"
            ) if status_label else None,

            # Currency, weight, document indicator
            Div(
                Span(currency, style="font-weight: 500; color: #059669; margin-right: 0.75rem;"),
                Div(
                    icon("scale", size=12, color="#64748b"),
                    Span(f" {weight or '—'} кг", style="color: #64748b; margin-left: 2px;"),
                    style="display: inline-flex; align-items: center; margin-right: 0.75rem;"
                ) if weight else Div(
                    icon("alert-triangle", size=12, color="#f59e0b"),
                    Span(" вес", style="color: #f59e0b; margin-left: 2px;"),
                    style="display: inline-flex; align-items: center; margin-right: 0.75rem;"
                ),
                # Document indicator
                Div(
                    icon("file-text", size=12, color="#10b981"),
                    Span(" скан", style="color: #10b981; margin-left: 2px;"),
                    style="display: inline-flex; align-items: center; margin-right: 0.75rem;"
                ) if has_document else Div(
                    icon("file-x", size=12, color="#94a3b8"),
                    Span(" нет скана", style="color: #94a3b8; margin-left: 2px;"),
                    style="display: inline-flex; align-items: center; margin-right: 0.75rem;"
                ),
                Span(f"Σ {total_sum:,.2f} {currency_sym}", style="font-weight: 500; color: #1e40af;") if total_sum > 0 else None,
                style="font-size: 0.75rem; display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem;"
            ),

            # Dimensions and package count
            Div(
                Span(f"{inv.get('height_m')} \u00d7 {inv.get('length_m')} \u00d7 {inv.get('width_m')} м",
                     style="color: #64748b; font-size: 0.75rem;") if (inv.get('height_m') and inv.get('length_m') and inv.get('width_m')) else None,
                Span(f"  \u2022  {inv.get('package_count')} мест", style="color: #64748b; font-size: 0.75rem;") if inv.get('package_count') else None,
                style="display: flex; align-items: center; gap: 4px; margin-top: 0.25rem;"
            ) if (inv.get('height_m') or inv.get('package_count')) else None,

            # Collapsible invoice details section (hidden by default)
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("Артикул", style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #64748b; text-align: left; border-bottom: 2px solid #e2e8f0;"),
                            Th("Наименование", style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #64748b; text-align: left; border-bottom: 2px solid #e2e8f0;"),
                            Th("Кол-во", style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #64748b; text-align: center; border-bottom: 2px solid #e2e8f0;"),
                            Th("Цена", style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #64748b; text-align: right; border-bottom: 2px solid #e2e8f0;"),
                        )
                    ),
                    Tbody(*invoice_items_table) if invoice_items_table else Tbody(Tr(Td("Нет позиций", colspan="4", style="padding: 0.5rem; text-align: center; color: #94a3b8; font-size: 0.8rem;"))),
                    style="width: 100%; border-collapse: collapse;"
                ),
                id=f"invoice-details-{inv['id']}",
                style="display: none; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #e2e8f0;"
            ),

            # Action buttons for pending invoices
            Div(
                A("Редактировать", href="#", cls="text-blue-600 text-sm",
                  style="font-size: 0.75rem; color: #3b82f6; margin-right: 0.75rem;",
                  **{"onclick": f"openEditInvoiceModal('{inv['id']}'); return false;"}),
                A("Назначить ↓", href="#", cls="text-green-600 text-sm",
                  style="font-size: 0.75rem; color: #059669;",
                  **{"onclick": f"assignSelectedToInvoice('{inv['id']}'); return false;"}),
                style="margin-top: 0.5rem;"
            ) if can_edit and not is_completed else None,

            # Complete button for pending invoices
            Div(
                A(
                    Span(icon("check", size=14, color="white"), style="margin-right: 4px; display: inline-flex; vertical-align: middle;"),
                    Span("Завершить инвойс"),
                    href="#",
                    style="font-size: 0.75rem; color: white; background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 0.375rem 0.75rem; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);",
                    **{"onclick": f"completeInvoice('{inv['id']}'); return false;"}
                ),
                style="margin-top: 0.75rem;"
            ) if can_edit and not is_completed else None,

            # Reopen button for completed invoices
            Div(
                A(
                    icon("lock-open", size=12, color="#64748b"),
                    Span(" Вернуть в работу", style="margin-left: 4px;"),
                    href="#",
                    style="font-size: 0.75rem; color: #64748b; text-decoration: underline; display: inline-flex; align-items: center;",
                    **{"onclick": f"reopenInvoice('{inv['id']}'); return false;"}
                ),
                style="margin-top: 0.5rem;"
            ) if can_edit and is_completed else None,

            cls="card",
            style=f"padding: 0.75rem; margin-bottom: 0.5rem; border-left: 3px solid {border_color}; cursor: pointer; background: {card_bg}; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.04);" + (" opacity: 0.9;" if is_completed else ""),
            id=f"invoice-card-{inv['id']}",
            onclick=f"toggleInvoiceDetails('{inv['id']}'); selectInvoice('{inv['id']}')"
        )

    return page_layout(f"Закупки — {quote_idn}",
        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "procurement", user.get("roles", []), quote=quote, user_id=user_id),

        # Workflow progress bar
        workflow_progress_bar(workflow_status),

        # Revision banner with icon
        Div(
            Div(
                icon("rotate-ccw", size=18, color="#92400e"),
                Span(" Возвращено на доработку", style="font-weight: 600; font-size: 1.1rem; margin-left: 6px;"),
                style="margin-bottom: 0.5rem; display: flex; align-items: center;"
            ),
            Div(
                Span("Комментарий:", style="font-weight: 500;"),
                P(revision_comment, style="margin: 0.25rem 0 0; font-style: italic;"),
            ) if revision_comment else None,
            cls="card",
            style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 2px solid #f59e0b; margin-bottom: 1rem; border-radius: 10px;"
        ) if is_revision else None,

        # Sales checklist info card (shows answers from sales team)
        _build_sales_checklist_card(quote.get("sales_checklist")),

        # Sales notes (free-text comment from sales manager)
        Div(
            Div(
                icon("message-square", size=16, color="#64748b"),
                Span(" Примечания от продажника", style="font-weight: 600; font-size: 0.875rem; margin-left: 6px; color: #475569;"),
                style="display: flex; align-items: center; margin-bottom: 8px;"
            ),
            P(quote.get("notes"), style="margin: 0; padding: 8px 12px; background: rgba(255,255,255,0.5); border-radius: 6px; font-size: 0.875rem; white-space: pre-wrap; line-height: 1.5; color: #374151;"),
            cls="card",
            style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-left: 4px solid #94a3b8; margin-bottom: 1rem; padding: 1rem; border-radius: 10px;"
        ) if quote.get("notes") else None,

        # Progress bar with gradient card
        Div(
            Div(
                icon("trending-up", size=16, color="#64748b"),
                Span(f" Прогресс: ", style="font-weight: 500; margin-left: 6px;"),
                Span(f"{priced_items}/{total_items}", style="font-weight: 600; color: #1e40af;"),
                Span(" оценено", style="color: #64748b;"),
                Span(f" | {assigned_items} назначено", style="color: #64748b;"),
                style="margin-bottom: 0.5rem; display: flex; align-items: center;"
            ),
            Div(
                Div(style=f"width: {(priced_items/total_items*100) if total_items > 0 else 0}%; height: 8px; background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%); border-radius: 999px;"),
                style="width: 100%; height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden;"
            ),
            cls="card", style="padding: 1rem; margin-bottom: 1rem; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 10px;"
        ),

        # Warning if not in correct status
        Div(
            P(icon("alert-triangle", size=16), f" КП в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}». Редактирование недоступно.",
              style="color: #b45309; margin: 0; display: flex; align-items: center; gap: 0.5rem;"),
            cls="card", style="background: #fffbeb; margin-bottom: 1rem;"
        ) if not can_edit else None,

        # Invoices section (full-width above items)
        Div(
            # Section header with icon
            Div(
                icon("file-text", size=16, color="#64748b"),
                Span(" ИНВОЙСЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                A(icon("plus", size=14), " Новый",
                  href="#", onclick="openCreateInvoiceModal(); return false;",
                  style="font-size: 0.75rem; color: #3b82f6; display: flex; align-items: center; gap: 0.25rem; margin-left: auto;"
                ) if can_edit else None,
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e2e8f0;"
            ),

            # Invoice cards grid (always has id for HTMX target)
            Div(
                *[invoice_card(inv, idx) for idx, inv in enumerate(invoices, 1)],
                id="invoices-list",
                style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.75rem;"
            ) if invoices else Div(
                icon("inbox", size=24, color="#94a3b8"),
                P("Нет инвойсов", style="color: #64748b; text-align: center; margin: 0.5rem 0 0;"),
                P("Создайте инвойс, чтобы начать", style="color: #94a3b8; text-align: center; font-size: 0.875rem; margin: 0.25rem 0 0;"),
                style="padding: 2rem 0; text-align: center;",
                id="invoices-list"
            ),

            # Unassigned items count with icon
            Div(
                Div(
                    icon("alert-triangle", size=14, color="#92400e"),
                    Span(f" Без инвойса: {unassigned_count}", style="font-weight: 500; color: #92400e; margin-left: 4px;"),
                    style="padding: 0.5rem 0.75rem; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 6px; text-align: center; display: flex; align-items: center; justify-content: center;"
                ),
                style="margin-top: 1rem;"
            ) if unassigned_count > 0 else None,

            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); padding: 1.25rem; margin-bottom: 1rem;",
            cls="card",
            id="invoices-panel"
        ),

        # Items table section (full-width below invoices)
        Div(
            # Section header with icon
            Div(
                Div(
                    icon("package", size=16, color="#64748b"),
                    Span(f" ПОЗИЦИИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    Span(f" ({total_items})", style="font-size: 11px; color: #94a3b8;"),
                    style="display: flex; align-items: center;"
                ),
                Div(
                    Span(id="selection-count", style="margin-right: 1rem; color: #64748b;"),
                    A(icon("download", size=14), " Excel",
                      href=f"/procurement/{quote_id}/export",
                      style="font-size: 0.75rem; color: #3b82f6; display: flex; align-items: center; gap: 0.25rem;"
                    ),
                    style="display: flex; align-items: center;"
                ),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e2e8f0;"
            ),

            # Copy-paste hint with better styling
            Div(
                icon("clipboard", size=14, color="#64748b"),
                Span(" Ctrl+V для вставки цен из Excel", style="margin-left: 0.5rem;"),
                style="font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; display: flex; align-items: center;"
            ) if can_edit else None,

            # Handsontable container with enhanced styling
            Div(
                Div(id="items-spreadsheet", style="width: 100%; height: 500px; overflow: hidden;"),
                cls="handsontable-container"
            ),

            # Footer with actions
            Div(
                btn("Сохранить", variant="secondary", icon_name="save", id="btn-save", onclick="saveAllChanges()") if can_edit else None,
                btn("Завершить закупку", variant="success", icon_name="check", id="btn-complete", onclick="completeProcurement()") if can_edit else None,
                btn_link("Вернуть на проверку", href=f"/procurement/{quote_id}/return-to-control", variant="primary", icon_name="arrow-up") if is_revision else None,
                style="display: flex; gap: 0.75rem; margin-top: 1rem;"
            ),

            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); padding: 1.25rem;",
            cls="card",
            id="items-panel"
        ),

        # Create Invoice Modal (with all fields including pickup_country, weight, volume)
        Div(
            # Backdrop (click to close)
            Div(
                id="create-invoice-backdrop",
                onclick="closeCreateInvoiceModal()",
                cls="fixed inset-0 bg-black/50 z-[999]",
                style="display: none;"
            ),
            # Modal box with gradient styling
            Div(
                Div(
                    Div(
                        icon("file-plus", size=18, color="#3b82f6"),
                        Span(" Новый инвойс", style="font-weight: 600; font-size: 1.125rem; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    ),
                    A("×", href="#", onclick="closeCreateInvoiceModal(); return false;",
                      cls="text-2xl text-gray-500 hover:text-gray-700 no-underline"),
                    cls="flex justify-between items-center mb-4"
                ),

                # Selected items indicator with icon
                Div(
                    icon("package", size=16, color="#3b82f6"),
                    Span(" Выбрано позиций: ", style="color: #64748b; margin-left: 6px;"),
                    Span("0", id="modal-selected-count", style="font-weight: 600; color: #1e40af;"),
                    style="margin-bottom: 1rem; padding: 0.75rem; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 8px; font-size: 0.875rem; display: flex; align-items: center;"
                ),

                Form(
                    # Hidden field for selected item IDs
                    Input(type="hidden", name="item_ids", id="modal-item-ids"),

                    # Supplier dropdown
                    supplier_dropdown(
                        name="supplier_id",
                        label="Поставщик *",
                        required=True,
                        placeholder="Поиск поставщика...",
                        dropdown_id="modal-supplier"
                    ),

                    # Buyer company dropdown
                    buyer_company_dropdown(
                        name="buyer_company_id",
                        label="Компания-покупатель *",
                        required=True,
                        placeholder="Поиск компании...",
                        dropdown_id="modal-buyer"
                    ),

                    # City autocomplete (HERE Geocode API) - pure JS fetch, no HTMX (modal compatibility)
                    Div(
                        Label("Город отгрузки *", cls="block mb-2 font-medium"),
                        Div(
                            Input(type="text", id="city-search-input", name="pickup_city",
                                  placeholder="Введите город (рус/eng)...", required=True,
                                  autocomplete="off",
                                  cls="w-full p-2 border border-gray-300 rounded-md"),
                            Div(id="city-dropdown",
                                style="display:none; position:absolute; left:0; right:0; top:100%; background:#fff; border:1px solid #e2e8f0; border-top:none; border-radius:0 0 8px 8px; box-shadow:0 4px 12px rgba(0,0,0,0.1); z-index:50; max-height:200px; overflow-y:auto;"),
                            style="position: relative;"
                        ),
                        Input(type="hidden", name="pickup_country", id="city-country-code"),
                        Div(
                            Span("🌍", style="margin-right: 4px;"),
                            Span("Страна определится из города", id="city-country-hint",
                                 style="color: #94a3b8;"),
                            id="city-country-badge",
                            style="margin-top: 6px; font-size: 0.8125rem; display: flex; align-items: center;"
                        ),
                        cls="mb-4"
                    ),

                    # Currency
                    Div(
                        Label("Валюта *", cls="block mb-2 font-medium"),
                        Select(
                            Option("USD", value="USD", selected=True),
                            Option("EUR", value="EUR"),
                            Option("RUB", value="RUB"),
                            Option("CNY", value="CNY"),
                            Option("TRY", value="TRY"),
                            name="currency",
                            required=True,
                            cls="w-full p-2 border border-gray-300 rounded-md"
                        ),
                        cls="mb-4"
                    ),

                    # Weight and Volume in a row
                    Div(
                        Div(
                            Label("Общий вес, кг *", cls="block mb-2 font-medium"),
                            Input(type="number", name="total_weight_kg", step="0.001", min="0.001", required=True,
                                  placeholder="125.5", cls="w-full p-2 border border-gray-300 rounded-md"),
                            cls="flex-1"
                        ),
                        Div(
                            Label("Габариты, м³", cls="block mb-2 font-medium"),
                            Input(type="number", name="total_volume_m3", step="0.0001", min="0",
                                  placeholder="2.5", cls="w-full p-2 border border-gray-300 rounded-md"),
                            cls="flex-1"
                        ),
                        cls="flex gap-4 mb-4"
                    ),

                    # Invoice file upload
                    Div(
                        Label("Скан инвойса от поставщика", cls="block mb-2 font-medium"),
                        Div(
                            icon("upload", size=20, color="#64748b"),
                            Span(" Выберите файл или перетащите", style="margin-left: 8px; color: #64748b;"),
                            Input(type="file", name="invoice_file", id="create-invoice-file",
                                  accept=".pdf,.jpg,.jpeg,.png,.webp",
                                  style="position: absolute; inset: 0; opacity: 0; cursor: pointer;"),
                            style="position: relative; display: flex; align-items: center; justify-content: center; padding: 1rem; border: 2px dashed #e2e8f0; border-radius: 8px; background: #f8fafc; cursor: pointer;"
                        ),
                        Div(id="create-invoice-filename", style="margin-top: 0.5rem; font-size: 0.875rem; color: #059669;"),
                        cls="mb-4"
                    ),

                    # Error message container
                    Div(id="create-invoice-error", cls="text-red-500 text-sm mt-2 hidden"),

                    # Action buttons - use flex-none to prevent button stretching
                    Div(
                        Button(
                            icon("check", size=16),
                            "Создать",
                            type="button",
                            onclick="submitCreateInvoiceForm()",
                            cls="flex-none btn btn--primary"
                        ),
                        Button(
                            "Отмена",
                            type="button",
                            onclick="closeCreateInvoiceModal()",
                            cls="flex-none btn btn--ghost"
                        ),
                        cls="flex gap-3 justify-end mt-6"
                    ),

                    id="create-invoice-form"
                ),

                id="create-invoice-modal-box",
                cls="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl p-6 z-[1000] w-[90%] max-w-lg max-h-[90vh] overflow-y-auto",
                style="display: none;"
            ),
            id="create-invoice-modal"
        ),

        # Edit Invoice Modal (exact feedback modal pattern with Tailwind)
        Div(
            # Backdrop (click to close)
            Div(
                id="edit-invoice-backdrop",
                onclick="closeEditInvoiceModal()",
                cls="fixed inset-0 bg-black/50 z-[999]",
                style="display: none;"
            ),
            # Modal box with gradient styling
            Div(
                Div(
                    Div(
                        icon("edit", size=18, color="#3b82f6"),
                        Span(" Редактировать инвойс", style="font-weight: 600; font-size: 1.125rem; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    ),
                    A("×", href="#", onclick="closeEditInvoiceModal(); return false;",
                      cls="text-2xl text-gray-500 hover:text-gray-700 no-underline"),
                    cls="flex justify-between items-center mb-4"
                ),

                Form(
                    Input(type="hidden", name="invoice_id", id="edit-invoice-id"),

                    # Invoice number
                    Div(
                        Label("Номер инвойса *", cls="block mb-2 font-medium"),
                        Input(type="text", name="invoice_number", id="edit-invoice-number", required=True,
                              cls="w-full p-2 border border-gray-300 rounded-md"),
                        cls="mb-4"
                    ),

                    # Currency
                    Div(
                        Label("Валюта *", cls="block mb-2 font-medium"),
                        Select(
                            Option("USD", value="USD"),
                            Option("EUR", value="EUR"),
                            Option("RUB", value="RUB"),
                            Option("CNY", value="CNY"),
                            Option("TRY", value="TRY"),
                            name="currency",
                            id="edit-invoice-currency",
                            required=True,
                            cls="w-full p-2 border border-gray-300 rounded-md"
                        ),
                        cls="mb-4"
                    ),

                    # Weight
                    Div(
                        Label("Общий вес, кг *", cls="block mb-2 font-medium"),
                        Input(type="number", name="total_weight_kg", id="edit-invoice-weight", step="0.001", min="0", required=True,
                              placeholder="125.5",
                              cls="w-full p-2 border border-gray-300 rounded-md"),
                        cls="mb-4"
                    ),

                    # Dimensions - H x L x W
                    Div(
                        Label("Габариты (м): высота \u00d7 длина \u00d7 ширина", cls="block mb-2 font-medium"),
                        Div(
                            Input(type="number", name="height_m", id="edit-invoice-height", step="0.01", min="0",
                                  placeholder="В", cls="w-full p-2 border border-gray-300 rounded-md",
                                  oninput="updateVolumeCalc()"),
                            Span("\u00d7", style="padding: 0 4px; color: #94a3b8;"),
                            Input(type="number", name="length_m", id="edit-invoice-length", step="0.01", min="0",
                                  placeholder="Д", cls="w-full p-2 border border-gray-300 rounded-md",
                                  oninput="updateVolumeCalc()"),
                            Span("\u00d7", style="padding: 0 4px; color: #94a3b8;"),
                            Input(type="number", name="width_m", id="edit-invoice-width", step="0.01", min="0",
                                  placeholder="Ш", cls="w-full p-2 border border-gray-300 rounded-md",
                                  oninput="updateVolumeCalc()"),
                            cls="flex items-center gap-1"
                        ),
                        Div(id="edit-invoice-volume-calc", style="font-size: 12px; color: #64748b; margin-top: 4px;"),
                        cls="mb-4"
                    ),

                    # Package count
                    Div(
                        Label("Количество мест", cls="block mb-2 font-medium"),
                        Input(type="number", name="package_count", id="edit-invoice-packages", step="1", min="0",
                              placeholder="кол-во коробок/паллет",
                              cls="w-full p-2 border border-gray-300 rounded-md"),
                        cls="mb-4"
                    ),

                    # Procurement notes
                    Div(
                        Label("Комментарий для логистики/таможни", cls="block mb-2 font-medium"),
                        Textarea(name="procurement_notes", id="edit-invoice-notes",
                                 placeholder="Хрупкий груз, особые условия хранения...",
                                 rows="3",
                                 cls="w-full p-2 border border-gray-300 rounded-md",
                                 style="resize: vertical;"),
                        cls="mb-4"
                    ),

                    # Invoice file section
                    Div(
                        Label("Скан инвойса от поставщика", cls="block mb-2 font-medium"),
                        # Current file display (hidden by default, shown via JS)
                        Div(
                            icon("file-text", size=16, color="#10b981"),
                            Span(id="edit-invoice-doc-filename", style="margin-left: 6px; color: #374151;"),
                            A("Скачать", href="#", id="edit-invoice-doc-download", target="_blank",
                              style="margin-left: 0.75rem; color: #3b82f6; font-size: 0.875rem;"),
                            A("Удалить", href="#", onclick="deleteInvoiceDocument(); return false;",
                              style="margin-left: 0.75rem; color: #ef4444; font-size: 0.875rem;"),
                            id="edit-invoice-doc-current",
                            style="display: none; align-items: center; padding: 0.75rem; background: #f0fdf4; border-radius: 8px; margin-bottom: 0.5rem;"
                        ),
                        # Upload new file
                        Div(
                            icon("upload", size=20, color="#64748b"),
                            Span(" Заменить файл", id="edit-upload-label", style="margin-left: 8px; color: #64748b;"),
                            Input(type="file", name="invoice_file", id="edit-invoice-file",
                                  accept=".pdf,.jpg,.jpeg,.png,.webp",
                                  style="position: absolute; inset: 0; opacity: 0; cursor: pointer;"),
                            style="position: relative; display: flex; align-items: center; justify-content: center; padding: 0.75rem; border: 2px dashed #e2e8f0; border-radius: 8px; background: #f8fafc; cursor: pointer;"
                        ),
                        Div(id="edit-invoice-filename", style="margin-top: 0.5rem; font-size: 0.875rem; color: #059669;"),
                        cls="mb-4"
                    ),

                    # Delete button
                    Div(
                        A("🗑 Удалить инвойс", href="#", onclick="deleteInvoice(); return false;",
                          cls="text-red-600 text-sm"),
                        cls="mb-4"
                    ),

                    # Action buttons
                    Div(
                        btn("Сохранить", variant="primary", type="button", icon_name="check", onclick="submitEditInvoiceForm()"),
                        btn("Отмена", variant="ghost", type="button", onclick="closeEditInvoiceModal()"),
                        cls="flex gap-3 justify-end mt-6"
                    ),

                    id="edit-invoice-form",
                    enctype="multipart/form-data"
                ),

                id="edit-invoice-modal-box",
                cls="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl p-6 z-[1000] w-[90%] max-w-lg",
                style="display: none;"
            ),
            id="edit-invoice-modal"
        ),

        # Transition history
        workflow_transition_history(quote_id),

        # JavaScript for procurement workspace
        Script(f"""
        (function() {{
            var quoteId = '{quote_id}';
            var canEdit = {'true' if can_edit else 'false'};
            var invoicesData = {invoices_json};
            var itemsData = {items_json};
            var hot = null;
            var selectedInvoiceId = null;

            // Modal functions (sibling pattern - backdrop + modal-box)
            window.openCreateInvoiceModal = function() {{
                // Save Handsontable data before opening modal (prevents data loss on page reload)
                saveAllChanges(false);

                // Collect selected item IDs
                if (!hot) {{
                    alert('Таблица не инициализирована');
                    return;
                }}
                var sourceData = hot.getSourceData();
                var selectedIds = [];
                for (var i = 0; i < sourceData.length; i++) {{
                    if (hot.getDataAtCell(i, 0) === true) {{
                        selectedIds.push(sourceData[i].id);
                    }}
                }}
                if (selectedIds.length === 0) {{
                    alert('Сначала выберите позиции для добавления в инвойс');
                    return;
                }}
                // Set hidden field with item IDs
                document.getElementById('modal-item-ids').value = JSON.stringify(selectedIds);
                // Update selected count display
                document.getElementById('modal-selected-count').textContent = selectedIds.length;
                // Show modal
                document.getElementById('create-invoice-backdrop').style.display = 'block';
                document.getElementById('create-invoice-modal-box').style.display = 'block';
            }};

            window.closeCreateInvoiceModal = function() {{
                document.getElementById('create-invoice-backdrop').style.display = 'none';
                document.getElementById('create-invoice-modal-box').style.display = 'none';
                document.getElementById('create-invoice-form').reset();
                document.getElementById('modal-item-ids').value = '';
                document.getElementById('modal-selected-count').textContent = '0';
                document.getElementById('create-invoice-error').classList.add('hidden');
                document.getElementById('create-invoice-filename').textContent = '';
            }};

            // File input change handlers
            document.getElementById('create-invoice-file').addEventListener('change', function(e) {{
                var filename = e.target.files[0] ? e.target.files[0].name : '';
                document.getElementById('create-invoice-filename').textContent = filename ? '📎 ' + filename : '';
            }});

            document.getElementById('edit-invoice-file').addEventListener('change', function(e) {{
                var filename = e.target.files[0] ? e.target.files[0].name : '';
                document.getElementById('edit-invoice-filename').textContent = filename ? '📎 Новый файл: ' + filename : '';
            }});

            // City autocomplete: fetch-based (no HTMX - works in modals)
            var cityInput = document.getElementById('city-search-input');
            var cityDropdown = document.getElementById('city-dropdown');
            var _cityTimer = null;
            if (cityInput && cityDropdown) {{
                cityInput.addEventListener('input', function() {{
                    var q = this.value.trim();
                    clearTimeout(_cityTimer);
                    if (q.length < 2) {{ cityDropdown.style.display = 'none'; return; }}
                    _cityTimer = setTimeout(function() {{
                        fetch('/api/cities/search?q=' + encodeURIComponent(q))
                            .then(function(r) {{ return r.text(); }})
                            .then(function(html) {{
                                if (!html || html.trim() === '') {{ cityDropdown.style.display = 'none'; return; }}
                                // Parse options from HTML response
                                var parser = new DOMParser();
                                var doc = parser.parseFromString('<select>' + html + '</select>', 'text/html');
                                var opts = doc.querySelectorAll('option');
                                if (opts.length === 0) {{ cityDropdown.style.display = 'none'; return; }}
                                cityDropdown.innerHTML = '';
                                opts.forEach(function(opt) {{
                                    if (opt.disabled) return;
                                    var item = document.createElement('div');
                                    item.textContent = opt.value;
                                    item.style.cssText = 'padding:8px 12px; cursor:pointer; font-size:0.875rem; border-bottom:1px solid #f1f5f9;';
                                    item.addEventListener('mouseenter', function() {{ this.style.background = '#f0f9ff'; }});
                                    item.addEventListener('mouseleave', function() {{ this.style.background = '#fff'; }});
                                    item.addEventListener('click', function() {{
                                        var city = opt.getAttribute('data-city') || opt.value;
                                        var code = opt.getAttribute('data-country-code') || '';
                                        var countryName = opt.value.split(', ').slice(1).join(', ');
                                        cityInput.value = city;
                                        document.getElementById('city-country-code').value = code;
                                        // Update badge
                                        var hint = document.getElementById('city-country-hint');
                                        var badge = document.getElementById('city-country-badge');
                                        if (hint && code) {{
                                            hint.textContent = countryName + ' (' + code + ')';
                                            hint.style.color = '#059669';
                                            hint.style.fontWeight = '600';
                                        }}
                                        if (badge && code) {{
                                            badge.style.background = '#ecfdf5';
                                            badge.style.padding = '6px 10px';
                                            badge.style.borderRadius = '6px';
                                            badge.style.border = '1px solid #a7f3d0';
                                        }}
                                        cityDropdown.style.display = 'none';
                                    }});
                                    cityDropdown.appendChild(item);
                                }});
                                cityDropdown.style.display = 'block';
                            }});
                    }}, 300);
                }});
                // Hide dropdown on outside click
                document.addEventListener('click', function(e) {{
                    if (!cityInput.contains(e.target) && !cityDropdown.contains(e.target)) {{
                        cityDropdown.style.display = 'none';
                    }}
                }});
            }}

            window.submitCreateInvoiceForm = function() {{
                var form = document.getElementById('create-invoice-form');
                var errEl = document.getElementById('create-invoice-error');
                errEl.classList.add('hidden');

                var formData = new FormData(form);

                fetch('/api/procurement/{quote_id}/invoices', {{
                    method: 'POST',
                    body: formData
                }})
                .then(function(response) {{
                    return response.json();
                }})
                .then(function(data) {{
                    if (data.success) {{
                        closeCreateInvoiceModal();
                        location.reload();
                    }} else {{
                        errEl.textContent = data.error || 'Ошибка создания инвойса';
                        errEl.classList.remove('hidden');
                    }}
                }})
                .catch(function(err) {{
                    errEl.textContent = 'Ошибка сети: ' + err.message;
                    errEl.classList.remove('hidden');
                }});
            }};

            window.openEditInvoiceModal = function(invoiceId) {{
                // Save Handsontable data before opening modal (prevents data loss)
                saveAllChanges(false);

                var inv = invoicesData.find(function(i) {{ return i.id === invoiceId; }});
                if (!inv) return;

                document.getElementById('edit-invoice-id').value = inv.id;
                document.getElementById('edit-invoice-number').value = inv.invoice_number || '';
                document.getElementById('edit-invoice-currency').value = inv.currency || 'USD';
                document.getElementById('edit-invoice-weight').value = inv.total_weight_kg || '';
                document.getElementById('edit-invoice-height').value = inv.height_m || '';
                document.getElementById('edit-invoice-length').value = inv.length_m || '';
                document.getElementById('edit-invoice-width').value = inv.width_m || '';
                document.getElementById('edit-invoice-packages').value = inv.package_count || '';
                document.getElementById('edit-invoice-notes').value = inv.procurement_notes || '';
                // Auto-calc volume display
                updateVolumeCalc();

                // Show/hide current document info
                var docCurrentEl = document.getElementById('edit-invoice-doc-current');
                var uploadLabel = document.getElementById('edit-upload-label');
                if (inv.has_document && inv.document_filename) {{
                    docCurrentEl.style.display = 'flex';
                    document.getElementById('edit-invoice-doc-filename').textContent = inv.document_filename;
                    document.getElementById('edit-invoice-doc-download').href = '/api/documents/' + inv.document_id + '/download';
                    uploadLabel.textContent = ' Заменить файл';
                }} else {{
                    docCurrentEl.style.display = 'none';
                    uploadLabel.textContent = ' Загрузить файл';
                }}
                document.getElementById('edit-invoice-filename').textContent = '';
                document.getElementById('edit-invoice-file').value = '';

                selectedInvoiceId = invoiceId;
                document.getElementById('edit-invoice-backdrop').style.display = 'block';
                document.getElementById('edit-invoice-modal-box').style.display = 'block';
            }};

            window.updateVolumeCalc = function() {{
                var h = parseFloat(document.getElementById('edit-invoice-height').value) || 0;
                var l = parseFloat(document.getElementById('edit-invoice-length').value) || 0;
                var w = parseFloat(document.getElementById('edit-invoice-width').value) || 0;
                var el = document.getElementById('edit-invoice-volume-calc');
                if (h > 0 && l > 0 && w > 0) {{
                    el.textContent = 'Объём: ' + (h * l * w).toFixed(4) + ' м³';
                }} else {{
                    el.textContent = '';
                }}
            }};

            window.closeEditInvoiceModal = function() {{
                document.getElementById('edit-invoice-backdrop').style.display = 'none';
                document.getElementById('edit-invoice-modal-box').style.display = 'none';
                document.getElementById('edit-invoice-filename').textContent = '';
                selectedInvoiceId = null;
            }};

            window.submitEditInvoiceForm = function() {{
                var form = document.getElementById('edit-invoice-form');
                var formData = new FormData(form);

                fetch('/api/procurement/{quote_id}/invoices/update', {{
                    method: 'PATCH',
                    body: formData
                }})
                .then(function(response) {{
                    if (response.ok) {{
                        closeEditInvoiceModal();
                        location.reload();
                    }} else {{
                        return response.json().then(function(data) {{
                            alert(data.error || 'Ошибка сохранения');
                        }});
                    }}
                }})
                .catch(function(err) {{
                    alert('Ошибка сети: ' + err.message);
                }});
            }};

            window.deleteInvoiceDocument = function() {{
                if (!selectedInvoiceId) return;
                var inv = invoicesData.find(function(i) {{ return i.id === selectedInvoiceId; }});
                if (!inv || !inv.document_id) return;

                if (!confirm('Удалить скан инвойса?')) return;

                fetch('/api/documents/' + inv.document_id, {{
                    method: 'DELETE'
                }})
                .then(function(response) {{ return response.json(); }})
                .then(function(data) {{
                    if (data.success) {{
                        // Update local data and UI
                        inv.has_document = false;
                        inv.document_id = null;
                        inv.document_filename = null;
                        document.getElementById('edit-invoice-doc-current').style.display = 'none';
                        document.getElementById('edit-upload-label').textContent = ' Загрузить файл';
                        location.reload();
                    }} else {{
                        alert(data.error || 'Ошибка удаления');
                    }}
                }})
                .catch(function(err) {{ alert('Ошибка: ' + err.message); }});
            }};

            // Invoice selection — also toggles invoice-details section
            window.selectInvoice = function(invoiceId) {{
                document.querySelectorAll('[id^="invoice-card-"]').forEach(function(el) {{
                    el.style.background = 'white';
                }});
                var card = document.getElementById('invoice-card-' + invoiceId);
                if (card) card.style.background = '#eff6ff';
                selectedInvoiceId = invoiceId;
            }};

            // Toggle invoice details expand/collapse
            window.toggleInvoiceDetails = function(invoiceId) {{
                var details = document.getElementById('invoice-details-' + invoiceId);
                if (!details) return;
                var chevron = document.getElementById('invoice-chevron-' + invoiceId);
                if (details.style.display === 'none' || details.style.display === '') {{
                    details.style.display = 'block';
                    if (chevron) chevron.style.transform = 'rotate(180deg)';
                }} else {{
                    details.style.display = 'none';
                    if (chevron) chevron.style.transform = 'rotate(0deg)';
                }}
            }};

            // Assign selected items to invoice
            window.assignSelectedToInvoice = function(invoiceId) {{
                if (!hot) return;
                var selectedRows = [];
                var sourceData = hot.getSourceData();

                for (var i = 0; i < sourceData.length; i++) {{
                    var cellMeta = hot.getCellMeta(i, 0);
                    if (cellMeta && hot.getDataAtCell(i, 0) === true) {{
                        selectedRows.push(sourceData[i].id);
                    }}
                }}

                if (selectedRows.length === 0) {{
                    alert('Выберите позиции для назначения');
                    return;
                }}

                fetch('/api/procurement/' + quoteId + '/items/assign', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        item_ids: selectedRows,
                        invoice_id: invoiceId
                    }})
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (data.success) {{
                        // Update table data
                        var inv = invoicesData.find(function(i) {{ return i.id === invoiceId; }});
                        var invLabel = inv ? '#' + inv.number : '';

                        for (var i = 0; i < sourceData.length; i++) {{
                            if (selectedRows.indexOf(sourceData[i].id) >= 0) {{
                                sourceData[i].invoice_id = invoiceId;
                                sourceData[i].invoice_label = invLabel;
                                hot.setDataAtCell(i, 0, false);  // Uncheck
                            }}
                        }}
                        hot.render();
                        location.reload();  // Refresh to update counts
                    }} else {{
                        alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                    }}
                }});
            }};

            // Save all changes - returns Promise for chaining
            window.saveAllChanges = function(showAlert) {{
                if (!hot) return Promise.resolve({{ success: true }});
                // IMPORTANT: Finish any active cell edit before reading data
                // Without this, typing a value and clicking Save/Complete won't include the current edit
                hot.deselectCell();
                var sourceData = hot.getSourceData();
                var updates = [];

                for (var i = 0; i < sourceData.length; i++) {{
                    var row = sourceData[i];
                    if (row.id) {{
                        updates.push({{
                            id: row.id,
                            purchase_price_original: row.price !== '' && row.price != null ? parseFloat(row.price) : null,
                            production_time_days: row.production_time !== '' && row.production_time != null ? parseInt(row.production_time) : null,
                            weight_kg: row.weight_kg !== '' && row.weight_kg != null ? parseFloat(row.weight_kg) : null,
                            volume_m3: row.volume_m3 !== '' && row.volume_m3 != null ? parseFloat(row.volume_m3) : null,
                            price_includes_vat: row.price_includes_vat || false,
                            is_unavailable: row.is_unavailable || false,
                            supplier_sku: row.supplier_sku || null
                        }});
                    }}
                }}

                return fetch('/api/procurement/' + quoteId + '/items/bulk', {{
                    method: 'PATCH',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ items: updates }})
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (showAlert !== false) {{
                        if (data.success) {{
                            alert('Сохранено успешно');
                        }} else {{
                            alert('Ошибка сохранения: ' + (data.error || 'Неизвестная ошибка'));
                        }}
                    }}
                    return data;
                }});
            }};

            // Complete procurement - properly awaits save before completing
            window.completeProcurement = function() {{
                if (!confirm('Завершить закупку? Все позиции будут отмечены как оценённые.')) return;

                // First save all changes, then complete (no race condition)
                window.saveAllChanges(false)
                    .then(function(saveResult) {{
                        if (!saveResult.success) {{
                            alert('Ошибка сохранения: ' + (saveResult.error || 'Неизвестная ошибка'));
                            return;
                        }}
                        return fetch('/api/procurement/' + quoteId + '/complete', {{
                            method: 'POST'
                        }});
                    }})
                    .then(function(r) {{ if (r) return r.json(); }})
                    .then(function(data) {{
                        if (!data) return;
                        if (data.success) {{
                            var msg = 'Закупка завершена!';
                            if (data.warning) {{
                                msg += '\\n\\n⚠️ ' + data.warning;
                            }}
                            alert(msg);
                            location.href = '/tasks';
                        }} else {{
                            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                        }}
                    }})
                    .catch(function(err) {{
                        alert('Ошибка сети: ' + err.message);
                    }});
            }};

            // Delete invoice
            window.deleteInvoice = function() {{
                if (!selectedInvoiceId) return;
                if (!confirm('Удалить инвойс? Товары будут откреплены.')) return;

                fetch('/api/procurement/' + quoteId + '/invoices/' + selectedInvoiceId, {{
                    method: 'DELETE'
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (data.success) {{
                        closeEditInvoiceModal();
                        location.reload();
                    }} else {{
                        alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                    }}
                }});
            }};

            // Complete invoice - moves to logistics/customs
            window.completeInvoice = function(invoiceId) {{
                if (!confirm('Завершить инвойс и передать в логистику/таможню?')) return;

                // First save all changes
                window.saveAllChanges(false)
                    .then(function(saveResult) {{
                        if (!saveResult.success) {{
                            alert('Ошибка сохранения: ' + (saveResult.error || 'Неизвестная ошибка'));
                            return;
                        }}
                        // Then complete the invoice
                        return fetch('/api/procurement/' + quoteId + '/invoices/' + invoiceId + '/complete', {{
                            method: 'POST'
                        }});
                    }})
                    .then(function(r) {{
                        if (!r) return;
                        return r.json();
                    }})
                    .then(function(data) {{
                        if (!data) return;
                        if (data.success) {{
                            var msg = 'Инвойс завершён и передан в логистику/таможню!';
                            if (data.warning) {{
                                msg += '\\n\\n⚠️ ' + data.warning;
                            }}
                            alert(msg);
                            location.reload();
                        }} else {{
                            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                        }}
                    }})
                    .catch(function(err) {{
                        alert('Ошибка сети: ' + err.message);
                    }});
            }};

            // Reopen invoice - returns to procurement
            window.reopenInvoice = function(invoiceId) {{
                if (!confirm('Вернуть инвойс в работу?')) return;

                fetch('/api/procurement/' + quoteId + '/invoices/' + invoiceId + '/reopen', {{
                    method: 'POST'
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (data.success) {{
                        location.reload();
                    }} else {{
                        alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                    }}
                }})
                .catch(function(err) {{
                    alert('Ошибка сети: ' + err.message);
                }});
            }};

            // Update selection count
            function updateSelectionCount() {{
                if (!hot) return;
                var count = 0;
                for (var i = 0; i < hot.countRows(); i++) {{
                    if (hot.getDataAtCell(i, 0) === true) count++;
                }}
                var el = document.getElementById('selection-count');
                if (el) el.textContent = count > 0 ? count + ' выбрано' : '';
            }}

            // Initialize Handsontable
            function initTable() {{
                var container = document.getElementById('items-spreadsheet');
                if (!container || typeof Handsontable === 'undefined') return;

                var columns = [
                    {{data: 'selected', type: 'checkbox', width: 40, readOnly: !canEdit}},
                    {{data: 'brand', type: 'text', readOnly: true, width: 100}},
                    {{data: 'product_code', type: 'text', readOnly: true, width: 100}},
                    {{data: 'idn_sku', type: 'text', readOnly: true, width: 100,
                      renderer: function(instance, td, row, col, prop, value) {{
                          Handsontable.renderers.TextRenderer.apply(this, arguments);
                          td.style.fontFamily = 'monospace';
                          td.style.fontSize = '0.8rem';
                          td.style.color = '#6b7280';
                          td.style.backgroundColor = '#f9fafb';
                          return td;
                      }}
                    }},
                    {{data: 'supplier_sku', type: 'text', width: 120, readOnly: !canEdit,
                      renderer: function(instance, td, row, col, prop, value) {{
                          Handsontable.renderers.TextRenderer.apply(this, arguments);
                          td.style.fontFamily = 'monospace';
                          td.style.fontSize = '0.8rem';
                          var idnSku = instance.getDataAtRowProp(row, 'idn_sku');
                          if (value && value !== '' && value !== idnSku) {{
                              td.style.backgroundColor = '#fffbeb';
                              td.style.color = '#b45309';
                              td.style.fontWeight = '600';
                          }}
                          return td;
                      }}
                    }},
                    {{data: 'product_name', type: 'text', readOnly: true, width: 200}},
                    {{data: 'quantity', type: 'numeric', readOnly: true, width: 50}},
                    {{data: 'price', type: 'numeric', width: 80, readOnly: !canEdit, numericFormat: {{pattern: '0.00'}}}},
                    {{data: 'production_time', type: 'numeric', width: 90, readOnly: !canEdit}},
                    {{data: 'weight_kg', type: 'numeric', width: 70, readOnly: !canEdit, numericFormat: {{pattern: '0.000'}}}},
                    {{data: 'volume_m3', type: 'numeric', width: 70, readOnly: !canEdit, numericFormat: {{pattern: '0.0000'}}}},
                    {{data: 'price_includes_vat', type: 'checkbox', width: 50, readOnly: !canEdit}},
                    {{data: 'is_unavailable', type: 'checkbox', width: 50, readOnly: !canEdit,
                      renderer: function(instance, td, row, col, prop, value) {{
                          Handsontable.renderers.CheckboxRenderer.apply(this, arguments);
                          td.style.textAlign = 'center';
                          if (value) {{
                              td.parentNode.style.backgroundColor = '#fef2f2';
                          }}
                          return td;
                      }}
                    }},
                    {{data: 'invoice_label', type: 'text', readOnly: true, width: 70,
                      renderer: function(instance, td, row, col, prop, value) {{
                          td.innerHTML = value || '<span style="color:#f59e0b">—</span>';
                          td.style.textAlign = 'center';
                          if (value) td.style.color = '#3b82f6';
                          return td;
                      }}
                    }}
                ];

                // Add 'selected' field to each item
                itemsData.forEach(function(item) {{
                    item.selected = false;
                }});

                hot = new Handsontable(container, {{
                    licenseKey: 'non-commercial-and-evaluation',
                    data: itemsData,
                    colHeaders: ['☐', 'Бренд', 'Артикул', 'IDN-SKU', 'Артикул поставщика', 'Наименование', 'Кол-во', 'Цена', 'Готовность к отгрузке, дней', 'Вес кг', 'Объём м³', 'НДС', 'Н/Д', 'Инвойс'],
                    columns: columns,
                    rowHeaders: true,
                    stretchH: 'all',
                    autoWrapRow: true,
                    contextMenu: false,
                    manualColumnResize: true,
                    afterChange: function(changes, source) {{
                        if (source === 'loadData') return;
                        updateSelectionCount();
                    }},
                    cells: function(row, col) {{
                        var cellProperties = {{}};
                        if (col === 0) {{
                            cellProperties.className = 'htCenter';
                        }}
                        return cellProperties;
                    }}
                }});

                window.hot = hot;
            }}

            // Initialize on DOM ready
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initTable);
            }} else {{
                initTable();
            }}
        }})();
        """),

        session=session
    )



# ============================================================================
# PROCUREMENT API ENDPOINTS
# ============================================================================

# @rt("/api/procurement/{quote_id}/invoices", methods=["POST"])  # decorator removed; file is archived and not mounted
async def api_create_invoice(quote_id: str, session, request):
    """Create a new invoice for procurement with selected items."""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

    supabase = get_supabase()

    # Verify quote exists
    quote_result = supabase.table("quotes") \
        .select("id, idn_quote") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    quote = quote_result.data

    # Parse form data
    form = await request.form()

    supplier_id = form.get("supplier_id")
    buyer_company_id = form.get("buyer_company_id")
    pickup_location_id = form.get("pickup_location_id") or None
    pickup_country = form.get("pickup_country", "").strip()
    pickup_city = form.get("pickup_city", "").strip()
    currency = form.get("currency", "USD")
    total_weight_kg = form.get("total_weight_kg")
    total_volume_m3 = form.get("total_volume_m3") or None
    item_ids_json = form.get("item_ids", "[]")

    # Parse item IDs
    try:
        item_ids = json.loads(item_ids_json) if item_ids_json else []
    except json.JSONDecodeError:
        item_ids = []

    if not supplier_id or not buyer_company_id:
        return JSONResponse({"success": False, "error": "Укажите поставщика и компанию-покупателя"}, status_code=400)

    if not pickup_country:
        return JSONResponse({"success": False, "error": "Укажите страну отгрузки для инвойса"}, status_code=400)

    if not total_weight_kg:
        return JSONResponse({"success": False, "error": "Total weight is required"}, status_code=400)

    if not item_ids:
        return JSONResponse({"success": False, "error": "No items selected"}, status_code=400)

    # Generate invoice number
    count_result = supabase.table("invoices").select("id", count="exact").eq("quote_id", quote_id).eq("supplier_id", supplier_id).execute()
    idx = (count_result.count or 0) + 1
    invoice_number = f"INV-{idx:02d}-{quote.get('idn_quote', quote_id[:8])}"

    try:
        # Create invoice in invoices table (procurement workflow)
        invoice_data = {
            "quote_id": quote_id,
            "supplier_id": supplier_id,
            "buyer_company_id": buyer_company_id,
            "invoice_number": invoice_number,
            "currency": currency,
            "pickup_country": pickup_country or None,
            "total_weight_kg": float(total_weight_kg) if total_weight_kg else None,
            "total_volume_m3": float(total_volume_m3) if total_volume_m3 else None,
            "status": "pending_procurement",
        }
        if pickup_city:
            invoice_data["pickup_city"] = pickup_city
        if pickup_location_id:
            invoice_data["pickup_location_id"] = pickup_location_id

        result = supabase.table("invoices").insert(invoice_data).execute()

        if not result.data:
            return JSONResponse({"success": False, "error": "Failed to create invoice"}, status_code=500)

        invoice_id = result.data[0]["id"]

        # Assign selected items to this invoice and set supplier_country
        supabase.table("quote_items") \
            .update({
                "invoice_id": invoice_id,
                "purchase_currency": currency,
                "supplier_country": pickup_country,
            }) \
            .in_("id", item_ids) \
            .eq("quote_id", quote_id) \
            .execute()

        # Handle file upload if provided
        invoice_file = form.get("invoice_file")
        if invoice_file and hasattr(invoice_file, 'filename') and invoice_file.filename:
            file_content = await invoice_file.read()
            if file_content:
                doc, error = upload_document(
                    organization_id=org_id,
                    entity_type="supplier_invoice",
                    entity_id=invoice_id,
                    file_content=file_content,
                    filename=invoice_file.filename,
                    document_type="invoice_scan",
                    uploaded_by=user["id"],
                    parent_quote_id=quote_id,
                )
                if error:
                    print(f"Warning: Failed to upload invoice document: {error}")
                    # Invoice was created but file upload failed — inform the user
                    return JSONResponse({
                        "success": False,
                        "error": "Инвойс создан, но не удалось загрузить файл. Проверьте формат (PDF, JPG, PNG, WebP) и размер (до 50 МБ). Вы можете загрузить файл позже через редактирование инвойса."
                    }, status_code=400)

        # Return success JSON
        return JSONResponse({"success": True, "invoice_id": invoice_id})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/api/procurement/{quote_id}/invoices/update", methods=["PATCH"])  # decorator removed; file is archived and not mounted
async def api_update_invoice(quote_id: str, session, request):
    """Update an existing invoice."""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

    form = await request.form()
    invoice_id = form.get("invoice_id")

    if not invoice_id:
        return JSONResponse({"success": False, "error": "Invoice ID required"}, status_code=400)

    # Procurement-lock guard: block edits once the quote's procurement stage completes
    from services.invoice_send_service import check_edit_permission
    user_roles = user.get("roles", [])
    if not check_edit_permission(invoice_id, user_roles):
        return JSONResponse(
            {"success": False, "error": {"code": "PROCUREMENT_LOCKED", "message": "Procurement for this quote has completed. Request unlock approval to edit."}},
            status_code=403,
        )

    supabase = get_supabase()

    # Build update data for invoices table (procurement workflow)
    update_data = {}

    invoice_number = form.get("invoice_number")
    if invoice_number:
        update_data["invoice_number"] = invoice_number.strip()

    currency = form.get("currency")
    if currency:
        update_data["currency"] = currency

    # Pickup/weight/volume fields
    pickup_location_id = form.get("pickup_location_id")
    if pickup_location_id is not None:
        update_data["pickup_location_id"] = pickup_location_id or None

    pickup_country = form.get("pickup_country")
    if pickup_country is not None:
        update_data["pickup_country"] = pickup_country.strip() or None

    total_weight_kg = form.get("total_weight_kg")
    if total_weight_kg is not None:
        update_data["total_weight_kg"] = float(total_weight_kg) if total_weight_kg else None

    total_volume_m3 = form.get("total_volume_m3")
    if total_volume_m3 is not None:
        update_data["total_volume_m3"] = float(total_volume_m3) if total_volume_m3 else None

    # Dimensions
    height_m = form.get("height_m")
    if height_m is not None:
        update_data["height_m"] = float(height_m) if height_m else None

    length_m = form.get("length_m")
    if length_m is not None:
        update_data["length_m"] = float(length_m) if length_m else None

    width_m = form.get("width_m")
    if width_m is not None:
        update_data["width_m"] = float(width_m) if width_m else None

    # Auto-calculate volume from dimensions (reuse already-converted values)
    h = update_data.get("height_m")
    l = update_data.get("length_m")
    w = update_data.get("width_m")
    if h and l and w:
        update_data["total_volume_m3"] = h * l * w

    # Package count
    package_count = form.get("package_count")
    if package_count is not None:
        update_data["package_count"] = int(package_count) if package_count else None

    # Procurement notes
    procurement_notes = form.get("procurement_notes")
    if procurement_notes is not None:
        update_data["procurement_notes"] = procurement_notes.strip() or None

    # Handle file upload if provided
    invoice_file = form.get("invoice_file")
    has_file_upload = invoice_file and hasattr(invoice_file, 'filename') and invoice_file.filename

    if not update_data and not has_file_upload:
        return JSONResponse({"success": False, "error": "No fields to update"}, status_code=400)

    try:
        if update_data:
            supabase.table("invoices").update(update_data).eq("id", invoice_id).eq("quote_id", quote_id).execute()

            # Also update currency on linked items
            if currency:
                supabase.table("quote_items") \
                    .update({"purchase_currency": currency}) \
                    .eq("invoice_id", invoice_id) \
                    .execute()

        # Handle file upload
        if has_file_upload:
            file_content = await invoice_file.read()
            if file_content:
                # Delete existing document first
                existing_docs = get_documents_for_entity("supplier_invoice", invoice_id)
                for doc in existing_docs:
                    delete_document(doc.id)

                # Upload new document
                doc, error = upload_document(
                    organization_id=org_id,
                    entity_type="supplier_invoice",
                    entity_id=invoice_id,
                    file_content=file_content,
                    filename=invoice_file.filename,
                    document_type="invoice_scan",
                    uploaded_by=user["id"],
                    parent_quote_id=quote_id,
                )
                if error:
                    print(f"Warning: Failed to upload invoice document: {error}")
                    return JSONResponse({
                        "success": False,
                        "error": "Данные инвойса сохранены, но не удалось загрузить файл. Проверьте формат (PDF, JPG, PNG, WebP) и размер (до 50 МБ)."
                    }, status_code=400)

        return JSONResponse({"success": True})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/api/procurement/{quote_id}/invoices/{invoice_id}", methods=["DELETE"])  # decorator removed; file is archived and not mounted
async def api_delete_invoice(quote_id: str, invoice_id: str, session):
    """Delete an invoice and unlink items."""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

    supabase = get_supabase()

    # Verify quote belongs to user's organization
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    try:
        # Unlink items first (scoped to quote_id for safety)
        supabase.table("quote_items") \
            .update({"invoice_id": None}) \
            .eq("invoice_id", invoice_id) \
            .eq("quote_id", quote_id) \
            .execute()

        # Delete invoice from invoices (scoped to quote_id for safety)
        supabase.table("invoices") \
            .delete() \
            .eq("id", invoice_id) \
            .eq("quote_id", quote_id) \
            .execute()

        return JSONResponse({"success": True})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/api/procurement/{quote_id}/invoices/{invoice_id}/complete", methods=["POST"])  # decorator removed; file is archived and not mounted
async def api_complete_invoice(quote_id: str, invoice_id: str, session):
    """Complete an invoice - moves it to logistics/customs stage."""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

    supabase = get_supabase()

    # Verify quote belongs to user's organization
    quote_result = supabase.table("quotes") \
        .select("id, idn_quote, created_by, customers!customer_id(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    # Extract quote details for notification
    quote_data = quote_result.data
    quote_idn = quote_data.get("idn_quote", "N/A")
    quote_creator_id = quote_data.get("created_by")
    customer_name = (quote_data.get("customers") or {}).get("name", "N/A")

    # Get invoice from invoices (procurement workflow)
    invoice_result = supabase.table("invoices") \
        .select("*") \
        .eq("id", invoice_id) \
        .eq("quote_id", quote_id) \
        .single() \
        .execute()

    if not invoice_result.data:
        return JSONResponse({"success": False, "error": "Invoice not found"}, status_code=404)

    invoice = invoice_result.data

    # Check invoice is in pending_procurement status
    if invoice.get("status") != "pending_procurement":
        return JSONResponse({"success": False, "error": "Invoice is not in procurement stage"}, status_code=400)

    # Validate pickup_country on the invoice before completing
    invoice_pickup_country = (invoice.get("pickup_country") or "").strip()
    if not invoice_pickup_country:
        return JSONResponse({
            "success": False,
            "error": "Укажите страну отгрузки для инвойса перед завершением. Без страны отгрузки невозможно назначить логиста."
        }, status_code=400)

    # Phase 5d Task 10b (Q2): readiness via canonical helper.
    # Quote is procurement-complete iff every non-N/A quote_item is covered
    # by an invoice_item (in its selected invoice) with a non-null price.
    # See composition_service.is_procurement_complete for the full contract.
    if not is_procurement_complete(quote_id, supabase):
        return JSONResponse({
            "success": False,
            "error": "Не все позиции заполнены. Проверьте, что для каждой позиции выбран инвойс с ценой и сроком производства."
        }, status_code=400)

    try:
        # Update invoice status in invoices (procurement workflow)
        supabase.table("invoices") \
            .update({
                "status": "pending_logistics",
                "procurement_completed_at": datetime.utcnow().isoformat(),
                "procurement_completed_by": user_id,
            }) \
            .eq("id", invoice_id) \
            .eq("quote_id", quote_id) \
            .execute()

        # Mark all items in this invoice as procurement completed
        # This is required for quote workflow transition check
        supabase.table("quote_items") \
            .update({"procurement_status": "completed"}) \
            .eq("invoice_id", invoice_id) \
            .execute()

        # Check if ALL items in quote are now in completed invoices
        # If yes, auto-transition the quote workflow
        all_invoices = supabase.table("invoices") \
            .select("id, status") \
            .eq("quote_id", quote_id) \
            .execute()

        all_items = supabase.table("quote_items") \
            .select("id, invoice_id, is_unavailable") \
            .eq("quote_id", quote_id) \
            .execute()

        invoices_data = all_invoices.data or []
        items_data = all_items.data or []

        # Get IDs of completed invoices (not pending_procurement)
        completed_invoice_ids = set(
            inv["id"] for inv in invoices_data
            if inv.get("status") != "pending_procurement"
        )

        # Check: all items must either:
        # 1. Be in a completed invoice (which validated price + production_time), OR
        # 2. Be marked as unavailable (can skip invoice entirely)
        all_items_ready = all(
            (item.get("invoice_id") and item.get("invoice_id") in completed_invoice_ids)
            or item.get("is_unavailable", False)
            for item in items_data
        ) if items_data else False

        workflow_transitioned = False
        logistics_warning = None
        if all_items_ready:
            # All items are in completed invoices - transition quote workflow
            try:
                user_roles = user.get("roles", [])
                result = complete_procurement(quote_id, user_id, user_roles)
                workflow_transitioned = result.success if result else False
                # Surface logistics assignment warnings (even on success)
                if result and result.error_message:
                    logistics_warning = result.error_message
            except Exception as workflow_err:
                # Log but don't fail - invoice was completed successfully
                print(f"Auto-transition failed: {workflow_err}")
                logistics_warning = f"Не удалось перевести КП на следующий этап: {workflow_err}"

        # Send Telegram notification to quote creator
        try:
            if quote_creator_id and quote_creator_id != user_id:
                # Compute item counts for the notification
                total_invoice_count = len(invoices_data)
                completed_invoice_count = len(completed_invoice_ids)
                unavailable_count = sum(
                    1 for item in items_data if item.get("is_unavailable", False)
                )
                # Get actor name
                actor_name = "Закупщик"
                try:
                    actor_resp = supabase.table("organization_members") \
                        .select("full_name") \
                        .eq("user_id", user_id) \
                        .execute()
                    if actor_resp.data and actor_resp.data[0].get("full_name"):
                        actor_name = actor_resp.data[0]["full_name"]
                except Exception:
                    pass
                invoice_number = invoice.get("invoice_number", "N/A")
                await send_procurement_invoice_complete_notification(
                    user_id=quote_creator_id,
                    quote_id=quote_id,
                    quote_idn=quote_idn,
                    customer_name=customer_name,
                    invoice_number=invoice_number,
                    completed_count=completed_invoice_count,
                    total_count=total_invoice_count,
                    unavailable_count=unavailable_count,
                    actor_name=actor_name,
                )
        except Exception as notif_err:
            # Log but don't fail - invoice was completed successfully
            print(f"Notification failed: {notif_err}")

        response_data = {
            "success": True,
            "new_status": "pending_logistics",
            "workflow_transitioned": workflow_transitioned,
        }
        if logistics_warning:
            response_data["warning"] = logistics_warning

        return JSONResponse(response_data)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/api/procurement/{quote_id}/invoices/{invoice_id}/reopen", methods=["POST"])  # decorator removed; file is archived and not mounted
async def api_reopen_invoice(quote_id: str, invoice_id: str, session):
    """Reopen an invoice - returns it to procurement stage."""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

    supabase = get_supabase()

    # Verify quote belongs to user's organization
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    # Get invoice
    invoice_result = supabase.table("invoices") \
        .select("*") \
        .eq("id", invoice_id) \
        .eq("quote_id", quote_id) \
        .single() \
        .execute()

    if not invoice_result.data:
        return JSONResponse({"success": False, "error": "Invoice not found"}, status_code=404)

    invoice = invoice_result.data

    # Only allow reopening if not yet fully completed (customs done)
    if invoice.get("status") == "completed":
        return JSONResponse({"success": False, "error": "Cannot reopen fully completed invoice"}, status_code=400)

    try:
        # Update invoice status back to procurement
        supabase.table("invoices") \
            .update({
                "status": "pending_procurement",
                "procurement_completed_at": None,
                "procurement_completed_by": None
            }) \
            .eq("id", invoice_id) \
            .execute()

        return JSONResponse({"success": True, "new_status": "pending_procurement"})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/api/procurement/{quote_id}/items/assign", methods=["POST"])  # decorator removed; file is archived and not mounted
async def api_assign_items_to_invoice(quote_id: str, session, request):
    """Bulk assign items to an invoice."""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

    body = await request.body()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    item_ids = data.get("item_ids", [])
    invoice_id = data.get("invoice_id")

    if not item_ids or not invoice_id:
        return JSONResponse({"success": False, "error": "item_ids and invoice_id required"}, status_code=400)

    # Procurement-lock guard: block item assignment changes once procurement completes
    from services.invoice_send_service import check_edit_permission
    user_roles = user.get("roles", [])
    if not check_edit_permission(invoice_id, user_roles):
        return JSONResponse(
            {"success": False, "error": {"code": "PROCUREMENT_LOCKED", "message": "Procurement for this quote has completed. Request unlock approval to edit."}},
            status_code=403,
        )

    supabase = get_supabase()

    # Verify quote belongs to user's organization
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    try:
        # Get invoice currency (verify invoice belongs to this quote)
        invoice_result = supabase.table("invoices") \
            .select("currency") \
            .eq("id", invoice_id) \
            .eq("quote_id", quote_id) \
            .single() \
            .execute()

        if not invoice_result.data:
            return JSONResponse({"success": False, "error": "Invoice not found"}, status_code=404)

        currency = invoice_result.data.get("currency", "USD")

        # Update items
        supabase.table("quote_items") \
            .update({
                "invoice_id": invoice_id,
                "purchase_currency": currency
            }) \
            .in_("id", item_ids) \
            .eq("quote_id", quote_id) \
            .execute()

        # Auto-advance (quote, brand) substates out of 'distributing' when the
        # brand is fully routed. Safe/idempotent — silent on failure.
        import logging as _logging
        _log = _logging.getLogger(__name__)
        try:
            brand_rows = supabase.table("quote_items") \
                .select("brand") \
                .in_("id", item_ids) \
                .execute()
            from services.workflow_service import maybe_advance_after_distribution
            brands_affected = {(it.get("brand") or "") for it in (brand_rows.data or [])}
            for b in brands_affected:
                try:
                    maybe_advance_after_distribution(quote_id, b, user["id"])
                except Exception as e:
                    _log.warning(f"auto-advance failed for {quote_id}/{b!r}: {e}")
        except Exception as e:
            _log.warning(f"auto-advance brand fetch failed for {quote_id}: {e}")

        return JSONResponse({"success": True, "updated": len(item_ids)})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# @rt("/api/procurement/{quote_id}/complete", methods=["POST"])  # decorator removed; file is archived and not mounted
async def api_complete_procurement(quote_id: str, session):
    """Complete procurement for all user's items."""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

    try:
        # Check if user is admin or head_of_procurement - bypass brand filtering
        is_admin = user_has_any_role(session, ["admin", "head_of_procurement"])

        supabase = get_supabase()

        # Get user's assigned brands (admin sees all)
        my_brands = get_assigned_brands(user_id, org_id) if not is_admin else []
        my_brands_lower = [b.lower() for b in my_brands]

        # Get all items for this quote
        items_result = supabase.table("quote_items") \
            .select("id, brand") \
            .eq("quote_id", quote_id) \
            .execute()

        all_items = items_result.data or []

        # Filter items for my brands - admin can complete all
        if is_admin:
            my_item_ids = [item["id"] for item in all_items]
        else:
            my_item_ids = [item["id"] for item in all_items
                           if (item.get("brand") or "").lower() in my_brands_lower]

        if my_item_ids:
            # Mark items as completed
            supabase.table("quote_items") \
                .update({
                    "procurement_status": "completed",
                    "procurement_completed_at": datetime.utcnow().isoformat(),
                    "procurement_completed_by": user_id
                }) \
                .in_("id", my_item_ids) \
                .execute()

        # Get invoices linked to this quote's items for status tracking
        invoice_ids_result = supabase.table("quote_items") \
            .select("invoice_id") \
            .eq("quote_id", quote_id) \
            .not_.is_("invoice_id", "null") \
            .execute()

        linked_invoice_ids = list(set(
            item["invoice_id"] for item in (invoice_ids_result.data or [])
            if item.get("invoice_id")
        ))

        if linked_invoice_ids:
            # Update invoices status to reflect procurement completion
            supabase.table("invoices") \
                .update({
                    "status": "pending_logistics",
                    "procurement_completed_at": datetime.utcnow().isoformat(),
                    "procurement_completed_by": user_id,
                }) \
                .in_("id", linked_invoice_ids) \
                .eq("quote_id", quote_id) \
                .execute()

        # Check if ALL items are complete and trigger workflow transition
        user_roles = get_user_roles_from_session(session)
        completion_result = complete_procurement(
            quote_id=quote_id,
            actor_id=user_id,
            actor_roles=user_roles
        )

        response_data = {
            "success": True,
            "completed_items": len(my_item_ids),
            "workflow_transitioned": completion_result.success if completion_result else False
        }
        # Surface logistics assignment warnings to the user
        if completion_result and completion_result.error_message:
            response_data["warning"] = completion_result.error_message

        return JSONResponse(response_data)

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error completing procurement for {quote_id}: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def render_invoices_list(quote_id: str, org_id: str, session):
    """Helper to render the invoices list HTML for HTMX updates."""
    supabase = get_supabase()
    user = session["user"]
    user_id = user["id"]

    # Check if user is admin or head_of_procurement - bypass brand filtering
    is_admin = user_has_any_role(session, ["admin", "head_of_procurement"])

    # Get user's assigned brands (admin sees all)
    my_brands = get_assigned_brands(user_id, org_id) if not is_admin else []
    my_brands_lower = [b.lower() for b in my_brands]

    # Get items first to find linked invoice IDs
    items_result = supabase.table("quote_items") \
        .select("id, product_name, brand, invoice_id, purchase_price_original, quantity") \
        .eq("quote_id", quote_id) \
        .execute()

    all_items = items_result.data or []

    # Get invoices from invoices table via linked item invoice_ids
    linked_inv_ids = list(set(
        item["invoice_id"] for item in all_items
        if item.get("invoice_id")
    ))

    if linked_inv_ids:
        invoices_result = supabase.table("invoices") \
            .select("*") \
            .in_("id", linked_inv_ids) \
            .order("created_at") \
            .execute()
        invoices = invoices_result.data or []
    else:
        invoices = []
    if is_admin:
        my_items = all_items
    else:
        my_items = [item for item in all_items
                    if (item.get("brand") or "").lower() in my_brands_lower]

    # Get supplier and buyer names
    supplier_ids = list(set(inv.get("supplier_id") for inv in invoices if inv.get("supplier_id")))
    suppliers = {}
    if supplier_ids:
        suppliers_result = supabase.table("suppliers").select("id, name").in_("id", supplier_ids).execute()
        suppliers = {s["id"]: s["name"] for s in suppliers_result.data or []}

    buyer_company_ids = list(set(inv.get("buyer_company_id") for inv in invoices if inv.get("buyer_company_id")))
    buyer_companies = {}
    if buyer_company_ids:
        buyers_result = supabase.table("buyer_companies").select("id, name").in_("id", buyer_company_ids).execute()
        buyer_companies = {b["id"]: b["name"] for b in buyers_result.data or []}

    currency_symbols = {"USD": "$", "EUR": "€", "RUB": "₽", "CNY": "¥", "TRY": "₺"}

    # Build invoice cards
    cards = []
    for idx, inv in enumerate(invoices, 1):
        supp = suppliers.get(inv.get("supplier_id"), "—")
        buyer = buyer_companies.get(inv.get("buyer_company_id"), "—")
        currency = inv.get("currency", "USD")
        currency_sym = currency_symbols.get(currency, currency)
        weight = inv.get("total_weight_kg")

        items_in_invoice = len([i for i in my_items if i.get("invoice_id") == inv["id"]])
        total_sum = sum(
            (item.get("purchase_price_original", 0) or 0) * (item.get("quantity", 0) or 0)
            for item in my_items if item.get("invoice_id") == inv["id"]
        )

        # Collect items for this invoice_items_table details
        invoice_items_list = [item for item in my_items if item.get("invoice_id") == inv["id"]]
        invoice_items_table = []
        for item in invoice_items_list:
            item_name = item.get("product_name") or "—"
            item_qty = item.get("quantity", 0) or 0
            item_price = item.get("purchase_price_original", 0) or 0
            invoice_items_table.append(
                Tr(
                    Td(item_name, style="padding: 0.25rem 0.5rem; font-size: 0.8rem; border-bottom: 1px solid #f1f5f9;"),
                    Td(str(item_qty), style="padding: 0.25rem 0.5rem; font-size: 0.8rem; text-align: center; border-bottom: 1px solid #f1f5f9;"),
                    Td(f"{item_price:,.2f} {currency_sym}", style="padding: 0.25rem 0.5rem; font-size: 0.8rem; text-align: right; border-bottom: 1px solid #f1f5f9;"),
                )
            )

        cards.append(
            Div(
                Div(
                    Span(f"📦 Инвойс #{idx}", style="font-weight: 600;"),
                    Div(
                        Span(f"{items_in_invoice} поз.", style="font-size: 0.75rem; color: #666; background: #f3f4f6; padding: 0.125rem 0.5rem; border-radius: 999px; margin-right: 0.5rem;"),
                        Span(icon("chevron-down", size=14, color="#64748b"),
                             id=f"invoice-chevron-{inv['id']}",
                             style="transition: transform 0.2s; display: inline-flex; align-items: center;"),
                        style="display: flex; align-items: center;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;"
                ),
                Div(
                    Span(supp, style="font-size: 0.875rem;"),
                    Span(" → ", style="color: #9ca3af;"),
                    Span(buyer, style="font-size: 0.875rem;"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Span(currency, style="font-weight: 500; color: #059669; margin-right: 0.75rem;"),
                    Span(f"{weight or '—'} кг", style="color: #666; margin-right: 0.75rem;") if weight else Span("⚠ вес", style="color: #f59e0b; margin-right: 0.75rem;"),
                    Span(f"Σ {total_sum:,.2f} {currency_sym}", style="font-weight: 500;") if total_sum > 0 else None,
                    style="font-size: 0.75rem;"
                ),
                # Collapsible invoice details section (hidden by default)
                Div(
                    Table(
                        Thead(
                            Tr(
                                Th("Наименование", style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #64748b; text-align: left; border-bottom: 2px solid #e2e8f0;"),
                                Th("Кол-во", style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #64748b; text-align: center; border-bottom: 2px solid #e2e8f0;"),
                                Th("Цена", style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #64748b; text-align: right; border-bottom: 2px solid #e2e8f0;"),
                            )
                        ),
                        Tbody(*invoice_items_table) if invoice_items_table else Tbody(Tr(Td("Нет позиций", colspan="3", style="padding: 0.5rem; text-align: center; color: #94a3b8; font-size: 0.8rem;"))),
                        style="width: 100%; border-collapse: collapse;"
                    ),
                    id=f"invoice-details-{inv['id']}",
                    style="display: none; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #e2e8f0;"
                ),
                Div(
                    A("Редактировать", href="#", onclick=f"openEditInvoiceModal('{inv['id']}'); return false;",
                      style="font-size: 0.75rem; color: #3b82f6; margin-right: 0.75rem;"),
                    A("Назначить ↓", href="#", onclick=f"assignSelectedToInvoice('{inv['id']}'); return false;",
                      style="font-size: 0.75rem; color: #059669;"),
                    style="margin-top: 0.5rem;"
                ),
                cls="card",
                style="padding: 0.75rem; margin-bottom: 0.5rem; border-left: 3px solid #3b82f6;",
                id=f"invoice-card-{inv['id']}",
                onclick=f"toggleInvoiceDetails('{inv['id']}'); selectInvoice('{inv['id']}')"
            )
        )

    if not cards:
        return Div(
            P("Нет инвойсов", style="color: #666; text-align: center;"),
            P("Создайте инвойс, чтобы начать", style="color: #9ca3af; text-align: center; font-size: 0.875rem;"),
            style="padding: 2rem 0;"
        )

    return Div(*cards)
