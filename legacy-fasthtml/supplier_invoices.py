"""FastHTML /supplier-invoices area — archived 2026-04-20 during Phase 6C-2B-10b.

Supplier-invoice management (registry, detail, payments) has no Next.js
replacement at the time of archival (per user directive 2026-04-20); routes
are archived rather than rewritten because the Caddy cutover already moves
kvotaflow.ru → app.kvotaflow.ru, which doesn't proxy these paths back to
this Python container. These handlers therefore become unreachable in
production. Preserved here for reference / future copy-back.

Contents (4 @rt routes + 2 exclusive helpers, ~1,446 LOC total):

Routes:
  - GET  /supplier-invoices                              — Registry with
         supplier/status filters, item counts + document counts per invoice
  - GET  /supplier-invoices/{invoice_id}                 — Detail page with
         info, financial summary, items, payments, documents section,
         actions
  - GET  /supplier-invoices/{invoice_id}/payments/new    — Payment form
         (create new payment for an invoice)
  - POST /supplier-invoices/{invoice_id}/payments/new    — Submit new
         payment (validates + calls register_payment service)

Helpers exclusive to /supplier-invoices (archived here):
  - _invoice_payment_form   — Payment create/edit form renderer, called
         only by GET+POST /supplier-invoices/{invoice_id}/payments/new
         (grep confirmed no external callers)
  - _documents_section      — Generic reusable documents section
         component. Called exclusively by /supplier-invoices/{invoice_id}
         GET as of 2026-04-20 (the /documents + /customer-contracts +
         /calls area was archived in Phase 6C-2B-10a, removing the
         previously-shared callers). /quotes/{id}/documents uses the
         separate _quote_documents_section helper (kept alive in main.py).
         Archived with this file since its only remaining caller moves
         here.

Preserved in main.py (NOT archived here):
  - _quote_documents_section — documents section for /quotes with
         hierarchical invoice/item binding; kept alive (live caller in
         /quotes/{id}/documents)
  - services/supplier_invoice_service.py, services/supplier_invoice_payment_service.py,
         services/buyer_company_service.py, services/document_service.py,
         services/database.py, services/user_service.py — all service
         layers still alive, consumed by FastAPI /api/* and Next.js
  - "Открыть реестр инвойсов поставщиков →" link in /finance page
         (main.py ~line 17885) left intact, becomes a dead link
         post-archive, safe per Caddy cutover

NOT including (separate archive decisions):
  - /api/supplier-invoices/* — no FastAPI sub-app exists yet
         (service layer consumed via services module directly; Next.js
         replacement pending)
  - /api/invoices/* (api/routers/invoices.py) — different area
         (procurement invoice download/letter/verify/unlock endpoints,
         alive)
  - /finance/*, /deals/*, /customer-contracts/* — separate areas
         (customer-contracts already archived in Phase 6C-2B-10a)

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_any_role, btn,
btn_link, icon, status_badge, fasthtml components, starlette
RedirectResponse, services.supplier_invoice_service,
services.supplier_invoice_payment_service, services.buyer_company_service,
services.document_service, services.database.get_supabase, date from
datetime), re-apply the @rt decorator, and regenerate tests if needed.
Not recommended — rewrite via Next.js + FastAPI instead.
"""
# flake8: noqa
# type: ignore

from datetime import date, datetime

from fasthtml.common import (
    A, Div, Form, H1, H3, H4, I, Input, Label, Option, P, Script,
    Select, Small, Span, Strong, Table, Tbody, Td, Textarea, Th, Thead, Tr,
)
from starlette.responses import RedirectResponse


# ============================================================================
# SUPPLIER INVOICES REGISTRY
# ============================================================================

# @rt("/supplier-invoices")  # decorator removed; file is archived and not mounted
def get(session, q: str = "", supplier_id: str = "", status: str = ""):
    """
    Supplier invoices registry page - queries the invoices table directly.

    Query Parameters:
        q: Search query (matches invoice number)
        supplier_id: Filter by supplier
        status: Filter - "" for all, "deals_only" for invoices linked to deals
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions - admin, procurement, finance roles
    if not user_has_any_role(session, ["admin", "procurement", "finance"]):
        return page_layout("Access Denied",
            Div(
                H1("⛔ Доступ запрещён"),
                P("У вас нет прав для просмотра реестра инвойсов поставщиков."),
                P("Требуется роль: admin, procurement или finance"),
                btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
                cls="card"
            ),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    # Query invoices table directly via Supabase client
    from services.database import get_supabase
    supabase = get_supabase()

    try:
        # Get invoices with supplier info
        query = supabase.table("invoices") \
            .select("id, invoice_number, currency, total_weight_kg, total_volume_m3, created_at, quote_id, supplier_id, suppliers!invoices_supplier_id_fkey(name, supplier_code), quotes!invoices_quote_id_fkey(idn_quote, customer_id, customers!quotes_customer_id_fkey(name))")

        if supplier_id:
            query = query.eq("supplier_id", supplier_id)
        if q and q.strip():
            query = query.ilike("invoice_number", f"%{q.strip()}%")

        # Filter: deals_only
        if status == "deals_only":
            # Get quote_ids that have deals
            deals_resp = supabase.table("deals") \
                .select("specifications!inner(quote_id)") \
                .is_("deleted_at", None) \
                .execute()
            deal_quote_ids = list(set(
                (d.get("specifications") or {}).get("quote_id")
                for d in (deals_resp.data or [])
                if (d.get("specifications") or {}).get("quote_id")
            ))
            if deal_quote_ids:
                query = query.in_("quote_id", deal_quote_ids)
            else:
                query = query.eq("quote_id", "00000000-0000-0000-0000-000000000000")  # no results

        invoices_resp = query.order("created_at", desc=True).limit(200).execute()
        invoices = invoices_resp.data or []

        # Get item counts and totals per invoice
        invoice_ids = [inv['id'] for inv in invoices]
        items_by_invoice = {}
        if invoice_ids:
            items_resp = supabase.table("quote_items") \
                .select("invoice_id, purchase_price_original") \
                .in_("invoice_id", invoice_ids) \
                .execute()
            for item in (items_resp.data or []):
                iid = item.get('invoice_id')
                if iid:
                    if iid not in items_by_invoice:
                        items_by_invoice[iid] = {'count': 0, 'total': 0}
                    items_by_invoice[iid]['count'] += 1
                    items_by_invoice[iid]['total'] += float(item.get('purchase_price_original') or 0)

        # Check document attachments — batch version of count_documents_for_entity
        doc_count_by_invoice = {}
        if invoice_ids:
            docs_resp = supabase.table("documents") \
                .select("entity_id") \
                .eq("entity_type", "supplier_invoice") \
                .in_("entity_id", invoice_ids) \
                .execute()
            for d in (docs_resp.data or []):
                eid = d.get('entity_id')
                if eid:
                    doc_count_by_invoice[eid] = doc_count_by_invoice.get(eid, 0) + 1

        # Get suppliers for filter dropdown
        suppliers_resp = supabase.table("suppliers") \
            .select("id, name, supplier_code") \
            .order("name") \
            .limit(200) \
            .execute()
        suppliers_list = suppliers_resp.data or []

    except Exception as e:
        print(f"Error loading invoices registry: {e}")
        import traceback
        traceback.print_exc()
        invoices = []
        items_by_invoice = {}
        doc_count_by_invoice = {}
        suppliers_list = []

    # Build supplier filter options
    supplier_options = [Option("Все поставщики", value="")] + [
        Option(f"{s.get('supplier_code', '')} - {s.get('name', '')}", value=str(s['id']), selected=(str(s['id']) == supplier_id))
        for s in suppliers_list
    ]

    # Status filter: All / Deals only
    status_options = [
        Option("Все инвойсы", value="", selected=(status == "")),
        Option("Только сделки", value="deals_only", selected=(status == "deals_only")),
    ]

    # Calculate summary totals
    total_amount_sum = sum(inv_data['total'] for inv_data in items_by_invoice.values())

    # Build invoice rows
    invoice_rows = []
    for inv in invoices:
        supplier = (inv.get('suppliers') or {})
        quote = (inv.get('quotes') or {})
        customer = ((quote.get('customers') or {}).get('name', '—'))
        idn = quote.get('idn_quote', '—')

        inv_items = items_by_invoice.get(inv['id'], {'count': 0, 'total': 0})
        doc_count = doc_count_by_invoice.get(inv['id'], 0)

        created_str = ""
        if inv.get('created_at'):
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(inv['created_at'].replace('Z', '+00:00'))
                created_str = dt.strftime("%d.%m.%Y")
            except Exception:
                created_str = str(inv['created_at'])[:10]

        doc_badge = Span(
            icon("paperclip", size=14, color="#64748b"),
            f" {doc_count}",
            style="display: inline-flex; align-items: center; gap: 4px; font-size: 13px; color: #64748b;"
        ) if doc_count > 0 else Span("—", style="color: #cbd5e1;")

        invoice_rows.append(
            Tr(
                Td(Strong(inv.get('invoice_number', '—')), style="font-family: monospace;"),
                Td(f"{supplier.get('supplier_code', '')} {supplier.get('name', '—')}".strip()),
                Td(A(idn, href=f"/quotes/{inv.get('quote_id', '')}", style="color: #4a4aff; text-decoration: none;") if inv.get('quote_id') else Span("—", style="color: #cbd5e1;")),
                Td(customer),
                Td(str(inv_items['count']), style="text-align: center;"),
                Td(f"{inv_items['total']:,.2f} {inv.get('currency', 'USD')}", style="text-align: right;"),
                Td(f"{float(inv.get('total_weight_kg') or 0):,.1f} кг", style="text-align: right;"),
                Td(doc_badge, style="text-align: center;"),
                Td(created_str),
            )
        )

    # Design system styles
    input_style = "width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"
    select_style = "padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; min-width: 150px;"
    th_style = "text-align: left; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"
    td_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    return page_layout("Инвойсы поставщиков",
        # Header card with gradient
        Div(
            Div(
                Div(
                    icon("receipt", size=24, color="#6366f1"),
                    Span("Реестр инвойсов поставщиков", style="font-size: 22px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    Span(f"{len(invoices)}", style="background: #e0e7ff; color: #4f46e5; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 12px; margin-left: 12px;"),
                    style="display: flex; align-items: center;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Stats cards
        Div(
            # Total invoices
            Div(
                Div(
                    icon("file-text", size=20, color="#64748b"),
                    style="margin-bottom: 8px;"
                ),
                Div(str(len(invoices)), style="font-size: 28px; font-weight: 700; color: #1e293b;"),
                Div("Всего инвойсов", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            # Total amount
            Div(
                Div(
                    icon("wallet", size=20, color="#22c55e"),
                    style="margin-bottom: 8px;"
                ),
                Div(f"{total_amount_sum:,.0f}", style="font-size: 28px; font-weight: 700; color: #22c55e;"),
                Div("Сумма позиций", style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 20px;"
        ),

        # Filters card
        Div(
            Form(
                Div(
                    icon("search", size=16, color="#64748b"),
                    Span("ФИЛЬТРЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 8px;"),
                    style="display: flex; align-items: center; margin-bottom: 12px;"
                ),
                Div(
                    Input(name="q", value=q, placeholder="Поиск по номеру инвойса...", style=f"{input_style} flex: 2;"),
                    Select(*supplier_options, name="supplier_id", style=f"{select_style} flex: 2;"),
                    Select(*status_options, name="status", style=f"{select_style} flex: 1;"),
                    btn("Поиск", variant="primary", icon_name="search", type="submit"),
                    btn_link("Сбросить", href="/supplier-invoices", variant="secondary", icon_name="x"),
                    style="display: flex; gap: 12px; align-items: center;"
                ),
                method="get",
                action="/supplier-invoices"
            ),
            style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Table card
        Div(
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("№ Инвойса", style=th_style),
                            Th("Поставщик", style=th_style),
                            Th("КП", style=th_style),
                            Th("Клиент", style=th_style),
                            Th("Позиций", style=f"{th_style} text-align: center;"),
                            Th("Сумма", style=f"{th_style} text-align: right;"),
                            Th("Вес", style=f"{th_style} text-align: right;"),
                            Th("Документы", style=f"{th_style} text-align: center;"),
                            Th("Дата", style=th_style),
                        )
                    ),
                    Tbody(*invoice_rows) if invoice_rows else Tbody(
                        Tr(Td(
                            Div(
                                icon("inbox", size=40, color="#cbd5e1"),
                                Div("Инвойсы не найдены", style="font-size: 16px; font-weight: 500; color: #64748b; margin-top: 12px;"),
                                style="text-align: center; padding: 40px 20px;"
                            ),
                            colspan="9"
                        ))
                    ),
                    style="width: 100%; border-collapse: collapse;"
                ),
                style="overflow-x: auto;"
            ),
            style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); overflow: hidden;"
        ),

        session=session
    )


# ============================================================================
# SUPPLIER INVOICE DETAIL
# ============================================================================

# @rt("/supplier-invoices/{invoice_id}")  # decorator removed; file is archived and not mounted
def get(invoice_id: str, session):
    """View single supplier invoice details with items and payments."""
    redirect = require_login(session)
    if redirect:
        return redirect

    # Check permissions
    if not user_has_any_role(session, ["admin", "procurement", "finance"]):
        return page_layout("Access Denied",
            Div("У вас нет прав для просмотра инвойсов.", cls="alert alert-error"),
            session=session
        )

    user = session["user"]
    org_id = user.get("org_id")

    from services.supplier_invoice_service import (
        get_invoice_with_details, get_invoice_status_name, get_invoice_status_color
    )
    from services.supplier_invoice_payment_service import get_payments_for_invoice

    try:
        invoice = get_invoice_with_details(invoice_id)
        if not invoice:
            return page_layout("Не найдено",
                Div("Инвойс не найден.", cls="alert alert-error"),
                btn_link("К реестру инвойсов", href="/supplier-invoices", variant="secondary", icon_name="arrow-left"),
                session=session
            )

        # Verify organization access
        if str(invoice.organization_id) != str(org_id):
            return page_layout("Access Denied",
                Div("У вас нет доступа к этому инвойсу.", cls="alert alert-error"),
                session=session
            )

        # Get payments for this invoice
        payments = get_payments_for_invoice(invoice_id)

    except Exception as e:
        print(f"Error loading invoice: {e}")
        return page_layout("Ошибка",
            Div(f"Ошибка при загрузке инвойса: {e}", cls="alert alert-error"),
            btn_link("К реестру инвойсов", href="/supplier-invoices", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Status styling
    status_color_classes = {
        "pending": "status-pending",
        "partially_paid": "status-in-progress",
        "paid": "status-approved",
        "overdue": "status-rejected",
        "cancelled": "status-cancelled",
    }
    status_cls = status_color_classes.get(invoice.status, "status-pending")
    status_text = get_invoice_status_name(invoice.status)

    # Calculate amounts
    total_amount = invoice.total_amount or 0
    paid_amount = invoice.paid_amount or 0
    remaining = total_amount - paid_amount

    # Format dates
    invoice_date_str = invoice.invoice_date.strftime("%d.%m.%Y") if invoice.invoice_date else "—"
    due_date_str = invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "—"

    # Build items table (if items exist)
    items_section = []
    if hasattr(invoice, 'items') and invoice.items:
        item_rows = []
        for item in invoice.items:
            item_total = (item.quantity or 0) * (item.unit_price or 0)
            item_rows.append(
                Tr(
                    Td(item.description or "—"),
                    Td(str(item.quantity or 0)),
                    Td(f"{item.unit_price or 0:,.2f}"),
                    Td(f"{item_total:,.2f}", style="text-align: right;"),
                )
            )
        items_section = [
            H3(icon("package", size=20), " Позиции инвойса", cls="card-header"),
            Table(
                Thead(Tr(
                    Th("Описание"),
                    Th("Кол-во"),
                    Th("Цена за ед."),
                    Th("Сумма", style="text-align: right;"),
                )),
                Tbody(*item_rows),
                cls="table"
            ),
        ]

    # Build payments table
    payment_rows = []
    from services.supplier_invoice_payment_service import get_payment_type_name
    for p in payments:
        payment_date_str = p.payment_date.strftime("%d.%m.%Y") if p.payment_date else "—"
        payment_type_text = get_payment_type_name(p.payment_type)
        payment_rows.append(
            Tr(
                Td(payment_date_str),
                Td(payment_type_text),
                Td(f"{p.amount:,.2f} {p.currency}", style="text-align: right;"),
                Td(p.buyer_company_name or "—"),
                Td(p.payment_document or "—"),
                Td(p.notes or "—"),
            )
        )

    payments_section = [
        Div(
            H3(icon("credit-card", size=20), " Платежи", style="display: inline-flex; align-items: center; gap: 0.5rem;"),
            btn_link("Добавить платёж", href=f"/supplier-invoices/{invoice_id}/payments/new", variant="success", size="sm", icon_name="plus"),
            style="margin-bottom: 1rem;"
        ),
    ]

    if payment_rows:
        payments_section.append(
            Table(
                Thead(Tr(
                    Th("Дата"),
                    Th("Тип"),
                    Th("Сумма", style="text-align: right;"),
                    Th("Плательщик"),
                    Th("Документ"),
                    Th("Примечание"),
                )),
                Tbody(*payment_rows),
                cls="table"
            )
        )
    else:
        payments_section.append(
            Div("Платежи ещё не зарегистрированы.", cls="alert alert-warning")
        )

    # Design system styles
    section_header_style = "display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;"
    label_style = "font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 4px;"
    value_style = "font-size: 14px; font-weight: 500; color: #1e293b;"
    th_style = "text-align: left; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"
    td_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    return page_layout(f"Инвойс {invoice.invoice_number}",
        # Header card with gradient
        Div(
            Div(
                A(
                    icon("arrow-left", size=16, color="#64748b"),
                    Span("К реестру инвойсов", style="margin-left: 6px;"),
                    href="/supplier-invoices",
                    style="display: inline-flex; align-items: center; color: #64748b; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("receipt", size=24, color="#6366f1"),
                    Span(f"Инвойс {invoice.invoice_number}", style="font-size: 22px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    status_badge(invoice.status),
                    style="display: flex; align-items: center; gap: 12px;"
                ),
                Div(
                    Span(f"Поставщик: {invoice.supplier_code or ''} - {invoice.supplier_name or '—'}", style="color: #64748b; font-size: 14px;"),
                    style="margin-top: 4px;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Two column layout for main info
        Div(
            # Left column - Invoice info
            Div(
                Div(
                    icon("info", size=16, color="#64748b"),
                    Span("ИНФОРМАЦИЯ ОБ ИНВОЙСЕ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=section_header_style
                ),
                Div(
                    Div(
                        Span("Номер инвойса", style=label_style),
                        Span(invoice.invoice_number, style=f"{value_style} font-family: monospace;"),
                        style="margin-bottom: 16px;"
                    ),
                    Div(
                        Span("Поставщик", style=label_style),
                        Span(f"{invoice.supplier_code or ''} - {invoice.supplier_name or '—'}", style=value_style),
                        style="margin-bottom: 16px;"
                    ),
                    Div(
                        Span("Дата инвойса", style=label_style),
                        Span(invoice_date_str, style=value_style),
                        style="margin-bottom: 16px;"
                    ),
                    Div(
                        Span("Срок оплаты", style=label_style),
                        Span(due_date_str, style=value_style),
                        Span(
                            icon("alert-triangle", size=14, color="#ef4444"),
                            " Просрочено!",
                            style="color: #ef4444; font-size: 12px; font-weight: 600; margin-left: 8px;"
                        ) if invoice.is_overdue else "",
                    ),
                ),
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            # Right column - Financial info
            Div(
                Div(
                    icon("wallet", size=16, color="#64748b"),
                    Span("ФИНАНСЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style=section_header_style
                ),
                Div(
                    Div(
                        Span("Сумма", style=label_style),
                        Span(f"{total_amount:,.2f} {invoice.currency}", style="font-size: 20px; font-weight: 600; color: #1e293b;"),
                        style="margin-bottom: 16px;"
                    ),
                    Div(
                        Span("Оплачено", style=label_style),
                        Span(f"{paid_amount:,.2f} {invoice.currency}", style="font-size: 18px; font-weight: 600; color: #22c55e;"),
                        style="margin-bottom: 16px;"
                    ),
                    Div(
                        Span("Остаток", style=label_style),
                        Span(f"{remaining:,.2f} {invoice.currency}", style=f"font-size: 18px; font-weight: 600; color: {'#ef4444' if remaining > 0 else '#22c55e'};"),
                    ),
                ),
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;"
        ),

        # Items section (if any)
        Div(
            Div(
                icon("package", size=16, color="#64748b"),
                Span("ПОЗИЦИИ ИНВОЙСА", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                Span(f"{len(invoice.items)}", style="background: #e0e7ff; color: #4f46e5; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-left: 8px;"),
                style=section_header_style
            ),
            Table(
                Thead(Tr(
                    Th("Описание", style=th_style),
                    Th("Кол-во", style=f"{th_style} text-align: center;"),
                    Th("Цена за ед.", style=f"{th_style} text-align: right;"),
                    Th("Сумма", style=f"{th_style} text-align: right;"),
                )),
                Tbody(*[
                    Tr(
                        Td(item.description or "—", style=td_style),
                        Td(str(item.quantity or 0), style=f"{td_style} text-align: center;"),
                        Td(f"{item.unit_price or 0:,.2f}", style=f"{td_style} text-align: right;"),
                        Td(f"{(item.quantity or 0) * (item.unit_price or 0):,.2f}", style=f"{td_style} text-align: right; font-weight: 500;"),
                    )
                    for item in invoice.items
                ]),
                style="width: 100%; border-collapse: collapse;"
            ),
            style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if hasattr(invoice, 'items') and invoice.items else "",

        # Payments section
        Div(
            Div(
                Div(
                    icon("credit-card", size=16, color="#64748b"),
                    Span("ПЛАТЕЖИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    Span(f"{len(payments)}", style="background: #dcfce7; color: #16a34a; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-left: 8px;"),
                    style="display: flex; align-items: center; gap: 8px;"
                ),
                btn_link("Добавить платёж", href=f"/supplier-invoices/{invoice_id}/payments/new", variant="primary", size="sm", icon_name="plus"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;"
            ),
            Table(
                Thead(Tr(
                    Th("Дата", style=th_style),
                    Th("Тип", style=th_style),
                    Th("Сумма", style=f"{th_style} text-align: right;"),
                    Th("Плательщик", style=th_style),
                    Th("Документ", style=th_style),
                    Th("Примечание", style=th_style),
                )),
                Tbody(*[
                    Tr(
                        Td(p.payment_date.strftime("%d.%m.%Y") if p.payment_date else "—", style=td_style),
                        Td(get_payment_type_name(p.payment_type), style=td_style),
                        Td(f"{p.amount:,.2f} {p.currency}", style=f"{td_style} text-align: right; font-weight: 500; color: #22c55e;"),
                        Td(p.buyer_company_name or "—", style=td_style),
                        Td(p.payment_document or "—", style=f"{td_style} font-family: monospace; font-size: 13px;"),
                        Td(p.notes or "—", style=f"{td_style} color: #64748b;"),
                    )
                    for p in payments
                ]),
                style="width: 100%; border-collapse: collapse;"
            ) if payment_rows else Div(
                icon("inbox", size=32, color="#cbd5e1"),
                Div("Платежи ещё не зарегистрированы", style="font-size: 14px; color: #64748b; margin-top: 8px;"),
                style="text-align: center; padding: 32px 20px; color: #94a3b8;"
            ),
            style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Notes section
        Div(
            Div(
                icon("message-square", size=16, color="#64748b"),
                Span("ПРИМЕЧАНИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style=section_header_style
            ),
            P(invoice.notes or "Нет примечаний", style="color: #64748b; font-size: 14px; line-height: 1.6;"),
            style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if invoice.notes else "",

        # Documents section
        _documents_section("supplier_invoice", invoice_id, session, can_upload=True, can_delete=user_has_any_role(session, ["admin", "finance"])),

        # Actions
        Div(
            btn_link("Добавить платёж", href=f"/supplier-invoices/{invoice_id}/payments/new", variant="primary", icon_name="credit-card"),
            style="display: flex; gap: 12px;"
        ),

        session=session
    )


# ============================================================================
# UI-014: INVOICE PAYMENT FORM (helper exclusive to /supplier-invoices)
# ============================================================================

def _invoice_payment_form(invoice, payment=None, error=None, session=None):
    """
    Render invoice payment create/edit form.

    Args:
        invoice: SupplierInvoice object (required for context)
        payment: Existing SupplierInvoicePayment object for edit mode, None for create mode
        error: Error message to display
        session: Session object for page layout
    """
    from services.supplier_invoice_payment_service import (
        PAYMENT_TYPES, PAYMENT_TYPE_NAMES, DEFAULT_CURRENCY, SUPPORTED_CURRENCIES,
        get_remaining_amount
    )
    from services.buyer_company_service import get_all_buyer_companies

    is_edit = payment is not None
    title = "Редактирование платежа" if is_edit else "Регистрация платежа"
    action_url = f"/supplier-invoices/{invoice.id}/payments/{payment.id}/edit" if is_edit else f"/supplier-invoices/{invoice.id}/payments/new"

    # Calculate remaining amount
    remaining = get_remaining_amount(invoice.id)

    # Get buyer companies for dropdown
    buyer_companies = get_all_buyer_companies(invoice.organization_id) if invoice.organization_id else []

    # Format invoice dates
    invoice_date_str = invoice.invoice_date.strftime("%d.%m.%Y") if invoice.invoice_date else "—"
    due_date_str = invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "—"

    # Pre-fill values
    today_str = date.today().isoformat()
    default_amount = str(remaining) if remaining > 0 else ""
    default_currency = invoice.currency or DEFAULT_CURRENCY

    # Build payment type options
    payment_type_options = []
    for pt in PAYMENT_TYPES:
        attrs = {"value": pt}
        if payment and payment.payment_type == pt:
            attrs["selected"] = True
        elif not payment and pt == "advance":  # Default to advance for new payments
            attrs["selected"] = True
        payment_type_options.append(Option(PAYMENT_TYPE_NAMES.get(pt, pt), **attrs))

    # Build currency options
    currency_options = []
    for curr in SUPPORTED_CURRENCIES:
        attrs = {"value": curr}
        if payment and payment.currency == curr:
            attrs["selected"] = True
        elif not payment and curr == default_currency:
            attrs["selected"] = True
        currency_options.append(Option(curr, **attrs))

    # Build buyer company options
    buyer_company_options = [Option("— Не указан —", value="")]
    for bc in buyer_companies:
        if bc.is_active:
            attrs = {"value": bc.id}
            if payment and payment.buyer_company_id == bc.id:
                attrs["selected"] = True
            label = f"{bc.company_code} - {bc.name}"
            buyer_company_options.append(Option(label, **attrs))

    return page_layout(title,
        # Error alert
        Div(error, cls="alert alert-error") if error else "",

        Div(
            icon("edit", size=28) if is_edit else icon("credit-card", size=28),
            H1(f" {title}", style="display: inline; margin-left: 0.5rem;"),
            style="display: flex; align-items: center;"
        ),

        # Invoice context card
        Div(
            H3(icon("clipboard-list", size=20), f" Инвойс {invoice.invoice_number}", cls="card-header"),
            Div(
                Div(
                    Table(
                        Tr(Td(Strong("Поставщик:")), Td(f"{invoice.supplier_code or ''} - {invoice.supplier_name or '—'}")),
                        Tr(Td(Strong("Дата инвойса:")), Td(invoice_date_str)),
                        Tr(Td(Strong("Срок оплаты:")), Td(due_date_str)),
                        style="border: none;"
                    ),
                    cls="col"
                ),
                Div(
                    Table(
                        Tr(Td(Strong("Сумма:")), Td(f"{invoice.total_amount:,.2f} {invoice.currency}", style="font-size: 1.1rem;")),
                        Tr(Td(Strong("Оплачено:")), Td(f"{invoice.total_paid:,.2f} {invoice.currency}", style="color: #28a745;")),
                        Tr(Td(Strong("Остаток:")), Td(f"{remaining:,.2f} {invoice.currency}", style="color: #dc3545; font-weight: bold;" if remaining > 0 else "color: #28a745; font-weight: bold;")),
                        style="border: none;"
                    ),
                    cls="col"
                ),
                cls="grid"
            ),
            cls="card", style="margin-bottom: 1.5rem; background: #f8f9fa;"
        ),

        Div(
            Form(
                # Payment details section
                H3("Данные платежа"),
                Div(
                    Label("Дата платежа *",
                        Input(
                            name="payment_date",
                            type="date",
                            value=payment.payment_date.isoformat() if payment and payment.payment_date else today_str,
                            required=True
                        )
                    ),
                    Label("Тип платежа *",
                        Select(
                            *payment_type_options,
                            name="payment_type",
                            required=True
                        ),
                        Small("Аванс — первый платёж, Финальный — полное закрытие", style="color: #666; display: block;")
                    ),
                    cls="form-row"
                ),
                Div(
                    Label("Сумма *",
                        Input(
                            name="amount",
                            type="number",
                            step="0.01",
                            min="0.01",
                            value=str(payment.amount) if payment else default_amount,
                            placeholder="1000.00",
                            required=True
                        ),
                        Small(f"Остаток к оплате: {remaining:,.2f} {invoice.currency}", style="color: #666; display: block;") if remaining > 0 else ""
                    ),
                    Label("Валюта *",
                        Select(
                            *currency_options,
                            name="currency",
                            required=True
                        )
                    ),
                    cls="form-row"
                ),

                # Payer section
                H3("Плательщик", style="margin-top: 1.5rem;"),
                Div(
                    Label("Компания-плательщик",
                        Select(
                            *buyer_company_options,
                            name="buyer_company_id"
                        ),
                        Small("Наше юрлицо, с которого производится оплата", style="color: #666; display: block;")
                    ),
                    Label("Курс к RUB",
                        Input(
                            name="exchange_rate",
                            type="number",
                            step="0.0001",
                            min="0",
                            value=str(payment.exchange_rate) if payment and payment.exchange_rate else "",
                            placeholder="90.5"
                        ),
                        Small("Для конвертации в рубли (опционально)", style="color: #666; display: block;")
                    ),
                    cls="form-row"
                ),

                # Document reference
                H3("Документ", style="margin-top: 1.5rem;"),
                Div(
                    Label("Номер платёжного документа",
                        Input(
                            name="payment_document",
                            value=payment.payment_document if payment else "",
                            placeholder="ПП-123, PAY-2025-001"
                        ),
                        Small("Номер платёжки или банковской операции", style="color: #666; display: block;")
                    ),
                    Div(cls="form-placeholder"),
                    cls="form-row"
                ),

                # Notes
                Label("Примечания",
                    Textarea(
                        payment.notes if payment else "",
                        name="notes",
                        rows=3,
                        placeholder="Дополнительная информация о платеже..."
                    )
                ),

                # Buttons
                Div(
                    btn("Сохранить", variant="primary", icon_name="save", type="submit"),
                    btn_link("Отмена", href=f"/supplier-invoices/{invoice.id}", variant="secondary", icon_name="x"),
                    style="display: flex; gap: 0.5rem; margin-top: 1.5rem;"
                ),

                method="POST",
                action=action_url
            ),
            cls="card"
        ),

        session=session
    )


# ============================================================================
# SUPPLIER INVOICE PAYMENT — GET form
# ============================================================================

# @rt("/supplier-invoices/{invoice_id}/payments/new")  # decorator removed; file is archived and not mounted
def get_new_invoice_payment(session, invoice_id: str):
    """Display form to register new payment for supplier invoice."""
    # Check authentication
    user = session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Check roles (admin, procurement, or finance can register payments)
    org_id = session.get("organization_id")
    if org_id:
        from services.user_service import get_user_roles_in_organization
        user_roles = get_user_roles_in_organization(user["id"], org_id)
        role_codes = [r.get("role_code") for r in user_roles]
        if not any(r in role_codes for r in ["admin", "procurement", "finance"]):
            return page_layout("Доступ запрещён",
                Div("У вас нет прав для регистрации платежей.", cls="alert alert-error"),
                session=session
            )

    # Get invoice with details
    from services.supplier_invoice_service import get_invoice_with_details
    invoice = get_invoice_with_details(invoice_id)

    if not invoice:
        return page_layout("Инвойс не найден",
            Div("Инвойс не найден или был удалён.", cls="alert alert-error"),
            A("← К реестру инвойсов", href="/supplier-invoices"),
            session=session
        )

    # Check organization access
    if invoice.organization_id and invoice.organization_id != org_id:
        return page_layout("Доступ запрещён",
            Div("У вас нет доступа к этому инвойсу.", cls="alert alert-error"),
            session=session
        )

    return _invoice_payment_form(invoice, session=session)


# ============================================================================
# SUPPLIER INVOICE PAYMENT — POST submit
# ============================================================================

# @rt("/supplier-invoices/{invoice_id}/payments/new")  # decorator removed; file is archived and not mounted
def post_new_invoice_payment(session, invoice_id: str, payment_date: str, payment_type: str, amount: str, currency: str, buyer_company_id: str = None, exchange_rate: str = None, payment_document: str = None, notes: str = None):
    """Handle new payment form submission."""
    # Check authentication
    user = session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Check roles
    org_id = session.get("organization_id")
    if org_id:
        from services.user_service import get_user_roles_in_organization
        user_roles = get_user_roles_in_organization(user["id"], org_id)
        role_codes = [r.get("role_code") for r in user_roles]
        if not any(r in role_codes for r in ["admin", "procurement", "finance"]):
            return page_layout("Доступ запрещён",
                Div("У вас нет прав для регистрации платежей.", cls="alert alert-error"),
                session=session
            )

    # Get invoice
    from services.supplier_invoice_service import get_invoice_with_details
    invoice = get_invoice_with_details(invoice_id)

    if not invoice:
        return page_layout("Инвойс не найден",
            Div("Инвойс не найден или был удалён.", cls="alert alert-error"),
            session=session
        )

    # Check organization access
    if invoice.organization_id and invoice.organization_id != org_id:
        return page_layout("Доступ запрещён",
            Div("У вас нет доступа к этому инвойсу.", cls="alert alert-error"),
            session=session
        )

    # Parse and validate input
    from decimal import Decimal, InvalidOperation
    from datetime import date as dt_date

    try:
        payment_date_parsed = dt_date.fromisoformat(payment_date)
    except (ValueError, TypeError):
        return _invoice_payment_form(invoice, error="Некорректная дата платежа", session=session)

    try:
        amount_decimal = Decimal(amount.strip())
        if amount_decimal <= 0:
            return _invoice_payment_form(invoice, error="Сумма должна быть больше нуля", session=session)
    except (InvalidOperation, ValueError, AttributeError):
        return _invoice_payment_form(invoice, error="Некорректная сумма платежа", session=session)

    exchange_rate_decimal = None
    if exchange_rate and exchange_rate.strip():
        try:
            exchange_rate_decimal = Decimal(exchange_rate.strip())
            if exchange_rate_decimal <= 0:
                return _invoice_payment_form(invoice, error="Курс должен быть больше нуля", session=session)
        except (InvalidOperation, ValueError):
            return _invoice_payment_form(invoice, error="Некорректный курс валюты", session=session)

    # Clean up optional fields
    buyer_company_id_clean = buyer_company_id.strip() if buyer_company_id and buyer_company_id.strip() else None
    payment_document_clean = payment_document.strip() if payment_document and payment_document.strip() else None
    notes_clean = notes.strip() if notes and notes.strip() else None

    # Register payment
    from services.supplier_invoice_payment_service import register_payment

    try:
        payment = register_payment(
            invoice_id=invoice_id,
            payment_date=payment_date_parsed,
            amount=amount_decimal,
            currency=currency,
            exchange_rate=exchange_rate_decimal,
            payment_type=payment_type,
            buyer_company_id=buyer_company_id_clean,
            payment_document=payment_document_clean,
            notes=notes_clean,
            created_by=user["id"]
        )

        if payment:
            # Success - redirect to invoice detail
            return RedirectResponse(f"/supplier-invoices/{invoice_id}", status_code=303)
        else:
            return _invoice_payment_form(invoice, error="Не удалось зарегистрировать платёж", session=session)

    except ValueError as e:
        return _invoice_payment_form(invoice, error=str(e), session=session)
    except Exception as e:
        return _invoice_payment_form(invoice, error=f"Ошибка при сохранении: {str(e)}", session=session)


# ============================================================================
# DOCUMENTS SECTION HELPER (exclusive to /supplier-invoices as of Phase 6C-2B-10b)
# ============================================================================
# Previously shared: before Phase 6C-2B-10a (which archived /documents +
# /customer-contracts + /calls), _documents_section was called from
# multiple surfaces. After 10a, the only remaining caller was
# /supplier-invoices/{invoice_id} GET, which archives here in 10b. Moved
# alongside its caller. /quotes/{id}/documents uses the separate
# _quote_documents_section helper, kept alive in main.py.


def _documents_section(entity_type: str, entity_id: str, session: dict, can_upload: bool = True, can_delete: bool = True):
    """
    Reusable documents section component.

    Args:
        entity_type: Type of parent entity (quote, supplier_invoice, etc.)
        entity_id: UUID of parent entity
        session: User session
        can_upload: Whether user can upload new documents
        can_delete: Whether user can delete documents

    Returns:
        HTML component for documents section
    """
    documents = get_documents_for_entity(entity_type, entity_id)
    doc_types = get_allowed_document_types_for_entity(entity_type)

    # Document list
    doc_rows = []
    for doc in documents:
        doc_rows.append(
            Tr(
                # File icon + name
                Td(
                    I(cls=f"fa-solid {get_file_icon(doc.mime_type)}", style="margin-right: 0.5rem; color: var(--accent);"),
                    A(doc.original_filename,
                      href=f"/documents/{doc.id}/view",
                      target="_blank",
                      title="Открыть для просмотра",
                      style="text-decoration: none; color: var(--text-primary);"),
                    style="display: flex; align-items: center;"
                ),
                # Document type
                Td(
                    Span(get_document_type_label(doc.document_type),
                         cls="badge",
                         style="background: var(--accent-light); color: var(--accent); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.8rem;")
                    if doc.document_type else "-"
                ),
                # File size
                Td(format_file_size(doc.file_size_bytes) or "-", style="color: var(--text-secondary);"),
                # Upload date
                Td(doc.created_at.strftime("%d.%m.%Y %H:%M") if doc.created_at else "-", style="color: var(--text-secondary);"),
                # Description
                Td(doc.description or "-", style="color: var(--text-secondary); max-width: 200px; overflow: hidden; text-overflow: ellipsis;"),
                # Actions - small square icon buttons (using Lucide icons)
                Td(
                    A(
                      icon("eye", size=16),
                      href=f"/documents/{doc.id}/view",
                      target="_blank",
                      title="Просмотр",
                      style="display: inline-flex !important; align-items: center !important; justify-content: center !important; width: 32px !important; height: 32px !important; background: #f3f4f6 !important; border: 1px solid #d1d5db !important; border-radius: 6px !important; color: #374151 !important; text-decoration: none !important;"),
                    A(
                      icon("download", size=16),
                      href=f"/documents/{doc.id}/download",
                      title="Скачать",
                      style="display: inline-flex !important; align-items: center !important; justify-content: center !important; width: 32px !important; height: 32px !important; background: #f3f4f6 !important; border: 1px solid #d1d5db !important; border-radius: 6px !important; color: #374151 !important; text-decoration: none !important;"),
                    A(
                      icon("trash-2", size=16),
                      href="#",
                      hx_delete=f"/documents/{doc.id}",
                      hx_confirm="Удалить документ?",
                      hx_target=f"#doc-row-{doc.id}",
                      hx_swap="outerHTML",
                      title="Удалить",
                      style="display: inline-flex !important; align-items: center !important; justify-content: center !important; width: 32px !important; height: 32px !important; background: #f3f4f6 !important; border: 1px solid #d1d5db !important; border-radius: 6px !important; color: #374151 !important; text-decoration: none !important;") if can_delete else None,
                    style="white-space: nowrap; display: flex; gap: 0.5rem;"
                ),
                id=f"doc-row-{doc.id}"
            )
        )

    # Empty state
    if not doc_rows:
        doc_rows.append(
            Tr(
                Td("Документы не загружены", colspan="6", style="text-align: center; color: var(--text-muted); padding: 2rem;")
            )
        )

    # JavaScript for drag-and-drop
    drag_drop_js = Script("""
    document.addEventListener('DOMContentLoaded', function() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('doc_file');
        const fileNameSpan = document.getElementById('file-name');

        if (!dropZone || !fileInput) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#6366f1';
                dropZone.style.background = '#eef2ff';
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#d1d5db';
                dropZone.style.background = '#fafafa';
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
                if (fileNameSpan) {
                    fileNameSpan.textContent = files[0].name;
                    fileNameSpan.style.color = '#111827';
                }
            }
        }, false);

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length && fileNameSpan) {
                fileNameSpan.textContent = fileInput.files[0].name;
                fileNameSpan.style.color = '#111827';
            }
        });

        dropZone.addEventListener('click', () => fileInput.click());

        // Handle document type select color
        const docTypeSelect = document.getElementById('doc_type');
        if (docTypeSelect) {
            docTypeSelect.addEventListener('change', function() {
                if (this.value && this.value !== '') {
                    this.style.color = '#111827';
                } else {
                    this.style.color = '#9ca3af';
                }
            });
        }
    });
    """)

    return Div(
        drag_drop_js,

        # Compact upload form
        Div(
            Form(
                Div(
                    # Left side: Drop zone (wider)
                    Div(
                        Div(
                            I(cls="fa-solid fa-cloud-arrow-up", style="font-size: 1.5rem; color: #9ca3af; margin-bottom: 0.5rem;"),
                            Div(
                                Span("Перетащите файл или ", style="color: #6b7280;"),
                                Span("выберите", style="color: #6366f1; cursor: pointer;"),
                                style="font-size: 0.875rem;"
                            ),
                            Span("", id="file-name", style="font-size: 0.75rem; color: #9ca3af; margin-top: 0.25rem;"),
                            style="display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer;"
                        ),
                        Input(type="file", name="file", id="doc_file", required=True,
                              accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.zip,.rar,.7z,.txt,.csv",
                              style="display: none;"),
                        id="drop-zone",
                        style="border: 2px dashed #d1d5db; border-radius: 8px; padding: 1rem; background: #fafafa; flex: 1; display: flex; align-items: center; justify-content: center; transition: border-color 0.15s ease, background-color 0.15s ease;"
                    ),
                    style="flex: 1; display: flex;"
                ),

                # Right side: Type, description, save
                Div(
                    # Document type with custom styled select
                    Div(
                        Select(
                            Option("Тип документа", value="", disabled=True, selected=True, style="color: #9ca3af;"),
                            *[Option(dt["label"], value=dt["value"]) for dt in doc_types],
                            name="document_type",
                            id="doc_type",
                            style="width: 100%; padding: 0.5rem 2rem 0.5rem 0.5rem; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 0.875rem; background: white; color: #9ca3af; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E\"); background-repeat: no-repeat; background-position: right 0.5rem center; cursor: pointer;"
                        ),
                        style="margin-bottom: 0.5rem; position: relative;"
                    ),

                    # Description
                    Div(
                        Input(type="text", name="description", id="doc_desc",
                              placeholder="Описание (опционально)",
                              style="width: 100%; padding: 0.5rem; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 0.875rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),

                    # Save button
                    btn("Сохранить", variant="primary", icon_name="check", type="submit", full_width=True),

                    style="flex: 1; min-width: 180px;"
                ),

                action=f"/documents/upload/{entity_type}/{entity_id}",
                method="POST",
                enctype="multipart/form-data",
                id="doc-upload-form",
                style="display: flex; gap: 0.75rem; align-items: stretch;"
            ),
            style="margin-bottom: 1rem; padding: 1rem; background: white; border: 1px solid #e5e7eb; border-radius: 8px;"
        ) if can_upload else None,

        # Documents table
        Div(
            H4(I(cls="fa-solid fa-folder-open", style="margin-right: 0.5rem;"), f"Документы ({len(documents)})"),
            Table(
                Thead(
                    Tr(
                        Th("Файл", style="width: 30%;"),
                        Th("Тип", style="width: 15%;"),
                        Th("Размер", style="width: 10%;"),
                        Th("Дата", style="width: 15%;"),
                        Th("Описание", style="width: 20%;"),
                        Th("", style="width: 10%;"),
                    )
                ),
                Tbody(*doc_rows, id="documents-tbody"),
                cls="table",
                style="width: 100%;"
            ),
            style="overflow-x: auto;"
        ),

        cls="documents-section",
        id="documents-section"
    )
