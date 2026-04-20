"""FastHTML /currency-invoices area — archived 2026-04-20 during Phase 6C-2B-8.

Superseded by Next.js currency-invoice management flows (registry, detail,
editing, verification, DOCX/PDF export, regeneration) — consumed via Next.js
against the live services layer through deal-level flows.

Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy these paths back to this Python container.

Contents (7 @rt routes + 5 exclusive helpers, ~1,070 LOC total):

Routes:
  - GET  /currency-invoices                        — Registry grouped by quote (IDN)
  - GET  /currency-invoices/{ci_id}                — Detail page with edit form
  - POST /currency-invoices/{ci_id}                — Save company selections + markup recalculation
  - POST /currency-invoices/{ci_id}/verify         — Verify (confirm) a currency invoice
  - GET  /currency-invoices/{ci_id}/download-docx  — DOCX export (uses services.currency_invoice_export)
  - GET  /currency-invoices/{ci_id}/download-pdf   — PDF export (DOCX → libreoffice conversion)
  - POST /currency-invoices/{ci_id}/regenerate     — Regenerate all CI for the deal from source data

Helpers exclusive to /currency-invoices (archived here):
  - _ci_get_company_options   — segment/role-scoped company dropdown options
  - _ci_current_entity_value  — format "{entity_type}:{entity_id}" for dropdown value
  - _fetch_ci_for_download    — fetch CI + items + seller/buyer for DOCX/PDF export
  - _resolve_company_details  — polymorphic FK → {name, address, tax_id} (used by download routes)
  - _convert_docx_to_pdf      — libreoffice headless DOCX → PDF conversion

Preserved in main.py (NOT archived here):
  - _ci_segment_badge           — still called by _render_currency_invoices_section (/quotes/documents)
  - _ci_status_badge            — still called by _render_currency_invoices_section + finance tab
  - _resolve_company_name       — shared by _finance_currency_invoices_tab_content
  - _fetch_items_with_buyer_companies  — used by finance / quote-control generate-CI flows
  - _fetch_enrichment_data      — used by finance / quote-control generate-CI flows
  - _render_currency_invoices_section  — /quotes/{quote_id}/documents section (live)
  - _finance_currency_invoices_tab_content  — /finance/{deal_id}?tab=currency_invoices (live)
  - services/currency_invoice_service.py, services/currency_invoice_export.py
    — service layers still alive, consumed by Next.js and the preserved helpers
  - sidebar/nav entry "Валютные инвойсы" → /currency-invoices (main.py ~line 2783)
    left intact, becomes a dead link post-archive, safe per Caddy cutover

NOT including (separate archive decisions):
  - /api/currency-invoices/* — no FastAPI sub-app exists yet (services consumed directly)
  - /finance/{deal_id}/generate-currency-invoices — part of /finance cluster, archived in 6C-2B-10
  - /quotes/{quote_id}/export/invoice — part of quote export cluster, separate area

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_any_role, get_supabase,
icon, _resolve_company_name, _ci_segment_badge, _ci_status_badge,
_fetch_items_with_buyer_companies, _fetch_enrichment_data, fasthtml
components, datetime, Decimal, services.currency_invoice_service,
services.currency_invoice_export), re-apply the @rt decorator, and regenerate
tests if needed. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime
from decimal import Decimal

from fasthtml.common import (
    A, Button, Div, Form, H1, H2, Input, Option, P, Select, Span,
    Table, Tbody, Td, Th, Thead, Titled, Tr,
)
from starlette.responses import RedirectResponse, Response


# ============================================================================
# COMPANY DROPDOWN OPTIONS HELPERS (used only by /currency-invoices/{ci_id} GET)
# ============================================================================

def _ci_get_company_options(supabase, segment, role):
    """Get company dropdown options filtered by segment and role (seller/buyer).

    Returns list of (value, label) tuples where value is 'entity_type:entity_id'.

    Segment filtering:
      EURTR seller: buyer_companies (EU suppliers)
      EURTR buyer: buyer_companies where country = 'TR'
      TRRU seller: buyer_companies where country = 'TR' + seller_companies
      TRRU buyer: seller_companies where country = 'RU'
    """
    options = []
    try:
        if segment == "EURTR" and role == "seller":
            # EU suppliers - all buyer_companies
            resp = supabase.table("buyer_companies").select("id, name, country").order("name").execute()
            for c in (resp.data or []):
                label = f"{c.get('name', '')} ({c.get('country', '')})"
                options.append((f"buyer_company:{c['id']}", label))

        elif segment == "EURTR" and role == "buyer":
            # Turkish intermediary - buyer_companies where region = TR
            resp = supabase.table("buyer_companies").select("id, name, country").eq("region", "TR").order("name").execute()
            for c in (resp.data or []):
                label = f"{c.get('name', '')} ({c.get('country', '')})"
                options.append((f"buyer_company:{c['id']}", label))

        elif segment == "TRRU" and role == "seller":
            # Turkish intermediary - buyer_companies TR + seller_companies
            resp_bc = supabase.table("buyer_companies").select("id, name, country").eq("region", "TR").order("name").execute()
            for c in (resp_bc.data or []):
                label = f"{c.get('name', '')} ({c.get('country', '')})"
                options.append((f"buyer_company:{c['id']}", label))
            resp_sc = supabase.table("seller_companies").select("id, name").order("name").execute()
            for c in (resp_sc.data or []):
                label = f"{c.get('name', '')} (ЮЛ-продажи)"
                options.append((f"seller_company:{c['id']}", label))

        elif segment == "TRRU" and role == "buyer":
            # Russian buyer - seller_companies where country = RU
            resp = supabase.table("seller_companies").select("id, name").order("name").execute()
            for c in (resp.data or []):
                label = f"{c.get('name', '')}"
                options.append((f"seller_company:{c['id']}", label))

    except Exception as e:
        print(f"Error fetching company options for {segment}/{role}: {e}")

    return options


def _ci_current_entity_value(entity_type, entity_id):
    """Build the dropdown value string from entity_type + entity_id."""
    if not entity_type or not entity_id:
        return ""
    return f"{entity_type}:{entity_id}"


# ============================================================================
# CURRENCY INVOICES REGISTRY (Task 6) - must be BEFORE {ci_id} routes
# ============================================================================

# @rt("/currency-invoices")  # decorator removed; file is archived and not mounted
def get(session):
    """Currency invoices registry — grouped by quote (IDN)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller", "finance"]):
        return page_layout("Доступ запрещён",
            Div(P("У вас нет прав для просмотра реестра валютных инвойсов."), style="padding: 40px; text-align: center; color: #64748b;"),
            session=session
        )

    supabase = get_supabase()
    user = session["user"]
    org_id = user.get("org_id", "")

    # Fetch all deals with quote info (to show quotes even with 0 invoices)
    try:
        deals_resp = supabase.table("deals").select(
            "id, deal_number, quote_id, "
            "quotes!deals_quote_id_fkey(id, idn_quote, customers(name))"
        ).eq("organization_id", org_id).is_("deleted_at", None).execute()
        all_deals = deals_resp.data or []
    except Exception as e:
        print(f"Error fetching deals for currency invoices registry: {e}")
        all_deals = []

    # Fetch all currency invoices
    try:
        ci_resp = supabase.table("currency_invoices").select(
            "*, deals!deal_id(deal_number)"
        ).eq("organization_id", org_id).order("generated_at", desc=True).execute()
        all_cis = ci_resp.data or []
    except Exception as e:
        print(f"Error fetching currency invoices: {e}")
        all_cis = []

    # Resolve company names
    for ci in all_cis:
        ci["seller_name"] = _resolve_company_name(supabase, ci.get("seller_entity_type"), ci.get("seller_entity_id"))
        ci["buyer_name"] = _resolve_company_name(supabase, ci.get("buyer_entity_type"), ci.get("buyer_entity_id"))

    # Build deal_map: deal_id → {quote_id, idn_quote, customer_name}
    deal_map = {}
    for deal in all_deals:
        q = (deal.get("quotes") or {})
        deal_map[deal["id"]] = {
            "quote_id": deal.get("quote_id", ""),
            "idn_quote": q.get("idn_quote") or f"#{str(deal.get('quote_id', ''))[:8]}",
            "customer_name": (q.get("customers") or {}).get("name", "—"),
        }

    # Group invoices by quote_id
    ci_by_quote = {}
    for ci in all_cis:
        deal_id = ci.get("deal_id", "")
        deal_info = deal_map.get(deal_id, {})
        quote_id = deal_info.get("quote_id", "")
        if quote_id:
            ci_by_quote.setdefault(quote_id, []).append(ci)

    # Build ordered list of quote groups (all quotes with deals)
    quote_groups = []
    seen_quote_ids = set()
    for deal in all_deals:
        q_id = deal.get("quote_id", "")
        if not q_id or q_id in seen_quote_ids:
            continue
        seen_quote_ids.add(q_id)
        info = deal_map.get(deal["id"], {})
        cis = ci_by_quote.get(q_id, [])
        latest_date = max((ci.get("generated_at") or "" for ci in cis), default="") if cis else ""
        quote_groups.append({
            "quote_id": q_id,
            "idn_quote": info.get("idn_quote", "—"),
            "customer_name": info.get("customer_name", "—"),
            "cis": cis,
            "latest_date": latest_date,
        })

    # Sort: groups with invoices first (latest date DESC), then groups without
    groups_with = sorted([g for g in quote_groups if g["latest_date"]], key=lambda g: g["latest_date"], reverse=True)
    groups_without = [g for g in quote_groups if not g["latest_date"]]
    quote_groups = groups_with + groups_without

    # Styles
    table_header_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    cell_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    if quote_groups:
        rows = []
        for group in quote_groups:
            cis = group["cis"]
            total_for_group = sum(float(ci.get("total_amount", 0) or 0) for ci in cis)
            ci_count = len(cis)

            # Quote group header row
            header_content = Div(
                A(group["idn_quote"],
                  href=f"/quotes/{group['quote_id']}",
                  style="color: #3b82f6; text-decoration: none; font-weight: 700; font-size: 14px;"),
                Span(f" — {group['customer_name']}", style="color: #475569; font-weight: 500; margin-left: 4px;"),
                Span(f" | {ci_count} инвойс(ов)", style="color: #64748b; margin-left: 8px; font-size: 13px;") if ci_count else "",
                Span(f" | {total_for_group:,.2f}", style="color: #475569; margin-left: 8px; font-size: 13px; font-weight: 600;") if ci_count else "",
                style="display: flex; align-items: center; flex-wrap: wrap;",
            )
            rows.append(
                Tr(
                    Td(header_content, colspan="8",
                       style="background: #f1f5f9; padding: 10px 16px;"),
                    cls="group-separator"
                )
            )

            if cis:
                # Sort within group: EURTR first, then TRRU
                segment_order = {"EURTR": 0, "TRRU": 1}
                cis_sorted = sorted(cis, key=lambda c: segment_order.get(c.get("segment", ""), 2))

                for ci in cis_sorted:
                    total_amount = float(ci.get("total_amount", 0) or 0)

                    # Format date
                    display_date = "—"
                    generated_at = ci.get("generated_at", "")
                    if generated_at:
                        try:
                            from datetime import datetime as dt_cls
                            if "T" in str(generated_at):
                                dt_obj = dt_cls.fromisoformat(str(generated_at).replace("Z", "+00:00"))
                                display_date = dt_obj.strftime("%d.%m.%Y")
                            else:
                                display_date = str(generated_at)[:10]
                        except Exception:
                            display_date = str(generated_at)[:10]

                    rows.append(Tr(
                        Td(display_date, style=f"{cell_style} color: #64748b; font-size: 13px;"),
                        Td(
                            A(ci.get("invoice_number", "—"),
                              href=f"/currency-invoices/{ci['id']}",
                              style="color: #3b82f6; text-decoration: none; font-weight: 500;"),
                            style=cell_style
                        ),
                        Td(_ci_segment_badge(ci.get("segment", "")), style=cell_style),
                        Td(ci.get("seller_name", "Не выбрана"), style=cell_style),
                        Td(ci.get("buyer_name", "Не выбрана"), style=cell_style),
                        Td(f"{total_amount:,.2f}", style=f"{cell_style} text-align: right; font-weight: 500;"),
                        Td(ci.get("currency", ""), style=cell_style),
                        Td(_ci_status_badge(ci.get("status", "draft")), style=cell_style),
                        style="transition: background-color 0.15s ease;",
                        onmouseover="this.style.backgroundColor='#f8fafc'",
                        onmouseout="this.style.backgroundColor='transparent'"
                    ))
            else:
                rows.append(
                    Tr(Td("Нет валютных инвойсов", colspan="8",
                           style="padding: 12px 16px; color: #94a3b8; font-size: 13px; font-style: italic; text-align: center;"))
                )

        invoices_table = Table(
            Thead(
                Tr(
                    Th("Дата", style=table_header_style),
                    Th("Номер инвойса", style=table_header_style),
                    Th("Сегмент", style=table_header_style),
                    Th("Продавец", style=table_header_style),
                    Th("Покупатель", style=table_header_style),
                    Th("Сумма", style=f"{table_header_style} text-align: right;"),
                    Th("Валюта", style=table_header_style),
                    Th("Статус", style=table_header_style),
                )
            ),
            Tbody(*rows),
            style="width: 100%; border-collapse: collapse;"
        )
    else:
        invoices_table = Div(
            Div(icon("file-text", size=40, color="#94a3b8"), style="margin-bottom: 12px;"),
            P("Валютные инвойсы ещё не созданы", style="color: #64748b; font-size: 14px; margin: 0;"),
            P("Инвойсы автоматически создаются при подписании сделки.", style="color: #94a3b8; font-size: 13px; margin-top: 8px;"),
            style="text-align: center; padding: 60px 20px;"
        )

    card_style = "background: white; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"

    return page_layout(
        "Валютные инвойсы",
        Div(
            H1("Валютные инвойсы", style="font-size: 22px; font-weight: 700; color: #1e293b; margin: 0 0 8px 0;"),
            P(f"КП со сделками: {len(quote_groups)}, инвойсов: {len(all_cis)}", style="color: #64748b; font-size: 14px; margin: 0;"),
            style="margin-bottom: 24px;"
        ),
        Div(
            Div(invoices_table, style="overflow-x: auto;"),
            style=card_style
        ),
        session=session,
        current_path="/currency-invoices"
    )


# ============================================================================
# CURRENCY INVOICE DETAIL PAGE (Task 5)
# ============================================================================

# @rt("/currency-invoices/{ci_id}")  # decorator removed; file is archived and not mounted
def get(session, ci_id: str):
    """Currency invoice detail page with editing capabilities."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller", "finance"]):
        return page_layout("Доступ запрещён",
            Div(P("У вас нет прав для просмотра валютных инвойсов."), style="padding: 40px; text-align: center; color: #64748b;"),
            session=session
        )

    supabase = get_supabase()
    user = session["user"]

    # Fetch invoice
    try:
        ci_resp = supabase.table("currency_invoices").select("*").eq("id", ci_id).single().execute()
        ci = ci_resp.data
    except Exception as e:
        print(f"Error fetching currency invoice {ci_id}: {e}")
        ci = None

    if not ci or ci.get("organization_id") != user.get("org_id", ""):
        return page_layout("Инвойс не найден",
            Div(
                H2("Валютный инвойс не найден", style="color: #1e293b; margin-bottom: 8px;"),
                P("Запрашиваемый инвойс не существует или был удалён.", style="color: #64748b;"),
                style="padding: 40px; text-align: center;"
            ),
            session=session
        )

    # Fetch items
    try:
        items_resp = supabase.table("currency_invoice_items").select("*").eq("currency_invoice_id", ci_id).order("sort_order").execute()
        items = items_resp.data or []
    except Exception as e:
        print(f"Error fetching currency invoice items for {ci_id}: {e}")
        items = []

    # Fetch deal info for back link
    deal_id = ci.get("deal_id", "")
    deal_number = ""
    quote_id = ""
    try:
        deal_resp = supabase.table("deals").select(
            "deal_number, specification_id, specifications!specification_id(quote_id)"
        ).eq("id", deal_id).single().is_("deleted_at", None).execute()
        deal_data = deal_resp.data or {}
        deal_number = deal_data.get("deal_number", "")
        specs = deal_data.get("specifications") or {}
        quote_id = specs.get("quote_id", "")
    except Exception:
        pass

    segment = ci.get("segment", "")
    status = ci.get("status", "draft")
    invoice_number = ci.get("invoice_number", "—")
    currency = ci.get("currency", "EUR")
    markup_percent = float(ci.get("markup_percent", 2.0) or 2.0)
    total_amount = float(ci.get("total_amount", 0) or 0)
    generated_at = ci.get("generated_at", "")

    # Format date
    display_date = ""
    if generated_at:
        try:
            from datetime import datetime as dt_cls
            if "T" in str(generated_at):
                dt_obj = dt_cls.fromisoformat(str(generated_at).replace("Z", "+00:00"))
                display_date = dt_obj.strftime("%d.%m.%Y %H:%M")
            else:
                display_date = str(generated_at)[:10]
        except Exception:
            display_date = str(generated_at)[:19]

    # Resolve current company names
    seller_name = _resolve_company_name(supabase, ci.get("seller_entity_type"), ci.get("seller_entity_id"))
    buyer_name = _resolve_company_name(supabase, ci.get("buyer_entity_type"), ci.get("buyer_entity_id"))

    # Get company dropdown options
    seller_options = _ci_get_company_options(supabase, segment, "seller")
    buyer_options = _ci_get_company_options(supabase, segment, "buyer")
    current_seller_value = _ci_current_entity_value(ci.get("seller_entity_type"), ci.get("seller_entity_id"))
    current_buyer_value = _ci_current_entity_value(ci.get("buyer_entity_type"), ci.get("buyer_entity_id"))

    # --- Build page ---

    # Styles
    card_style = "background: white; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; margin-bottom: 20px;"
    section_label_style = "font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;"
    field_label_style = "font-size: 12px; color: #64748b; font-weight: 500; margin-bottom: 4px;"
    select_style = "width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; color: #1e293b; background: white;"
    input_style = "width: 120px; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; color: #1e293b;"
    table_header_style = "padding: 10px 14px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    cell_style = "padding: 10px 14px; font-size: 13px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    # Back link
    back_link_href = f"/quotes/{quote_id}?tab=currency_invoices" if quote_id else "/dashboard"
    back_link = A(
        icon("arrow-left", size=14, color="#64748b"),
        Span(f" Назад к сделке {deal_number}" if deal_number else " Назад", style="margin-left: 4px;"),
        href=back_link_href,
        style="display: inline-flex; align-items: center; color: #64748b; text-decoration: none; font-size: 13px; font-weight: 500; margin-bottom: 16px;"
    )

    # Header
    header = Div(
        Div(
            H1(invoice_number, style="font-size: 22px; font-weight: 700; color: #1e293b; margin: 0 12px 0 0;"),
            _ci_segment_badge(segment),
            _ci_status_badge(status),
            style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;"
        ),
        Div(
            Span(f"Дата создания: {display_date}" if display_date else "", style="font-size: 13px; color: #94a3b8;"),
            Span(f"  |  Валюта: {currency}", style="font-size: 13px; color: #94a3b8; margin-left: 12px;") if currency else "",
            style="margin-top: 6px;"
        ),
        style="margin-bottom: 24px;"
    )

    # Determine if editable (only draft status)
    is_editable = (status == "draft")

    # Companies section (form)
    seller_select = Select(
        Option("— Не выбрана —", value=""),
        *[Option(label, value=val, selected=(val == current_seller_value)) for val, label in seller_options],
        name="seller_entity",
        style=select_style,
        disabled=None if is_editable else "disabled"
    )

    buyer_select = Select(
        Option("— Не выбрана —", value=""),
        *[Option(label, value=val, selected=(val == current_buyer_value)) for val, label in buyer_options],
        name="buyer_entity",
        style=select_style,
        disabled=None if is_editable else "disabled"
    )

    companies_section = Div(
        Div(
            icon("building", size=14, color="#64748b"),
            Span("КОМПАНИИ", style="margin-left: 6px;"),
            style=section_label_style
        ),
        Div(
            Div(
                Div("Продавец", style=field_label_style),
                seller_select,
                Div(f"Текущий: {seller_name}", style="font-size: 11px; color: #94a3b8; margin-top: 4px;") if seller_name != "Не выбрана" else "",
            ),
            Div(
                Div("Покупатель", style=field_label_style),
                buyer_select,
                Div(f"Текущий: {buyer_name}", style="font-size: 11px; color: #94a3b8; margin-top: 4px;") if buyer_name != "Не выбрана" else "",
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;"
        ),
        style=card_style
    )

    # Markup section
    markup_section = Div(
        Div(
            icon("percent", size=14, color="#64748b"),
            Span("НАЦЕНКА НА СЕГМЕНТ", style="margin-left: 6px;"),
            style=section_label_style
        ),
        Div(
            Div("Наценка, %", style=field_label_style),
            Input(
                type="number",
                name="markup_percent",
                value=str(markup_percent),
                step="0.01",
                min="0",
                max="100",
                style=input_style,
                disabled=None if is_editable else "disabled"
            ),
            Div("При изменении наценки цены всех позиций будут пересчитаны",
                style="font-size: 11px; color: #94a3b8; margin-top: 4px;"),
        ),
        style=card_style
    )

    # Items table
    item_rows = []
    for idx, item in enumerate(items, 1):
        item_base_price = float(item.get("base_price", 0) or 0)
        item_price = float(item.get("price", 0) or 0)
        item_total = float(item.get("total", 0) or 0)
        item_qty = float(item.get("quantity", 0) or 0)

        item_rows.append(Tr(
            Td(str(idx), style=f"{cell_style} color: #94a3b8; width: 40px;"),
            Td(item.get("product_name", "—"), style=f"{cell_style} font-weight: 500;"),
            Td(item.get("sku", "—"), style=f"{cell_style} font-family: monospace; font-size: 12px;"),
            Td(item.get("idn_sku", "—"), style=f"{cell_style} font-family: monospace; font-size: 12px;"),
            Td(item.get("manufacturer", "—"), style=cell_style),
            Td(f"{item_qty:g}", style=f"{cell_style} text-align: right;"),
            Td(item.get("unit", "pcs"), style=f"{cell_style} text-align: center;"),
            Td(item.get("hs_code", "—"), style=f"{cell_style} font-family: monospace; font-size: 12px;"),
            Td(f"{item_base_price:,.4f}", style=f"{cell_style} text-align: right; color: #64748b;"),
            Td(f"{item_price:,.4f}", style=f"{cell_style} text-align: right; font-weight: 500;"),
            Td(f"{item_total:,.2f}", style=f"{cell_style} text-align: right; font-weight: 600;"),
        ))

    # Total row
    item_rows.append(Tr(
        Td("", colspan="9", style="padding: 12px 14px; border-top: 2px solid #e2e8f0;"),
        Td("ИТОГО:", style="padding: 12px 14px; text-align: right; font-weight: 700; font-size: 13px; color: #1e293b; border-top: 2px solid #e2e8f0;"),
        Td(f"{total_amount:,.2f} {currency}", style="padding: 12px 14px; text-align: right; font-weight: 700; font-size: 14px; color: #1e293b; border-top: 2px solid #e2e8f0;"),
    ))

    items_section = Div(
        Div(
            icon("list", size=14, color="#64748b"),
            Span("ПОЗИЦИИ", style="margin-left: 6px;"),
            style=section_label_style
        ),
        Div(
            Table(
                Thead(Tr(
                    Th("#", style=f"{table_header_style} width: 40px;"),
                    Th("Наименование", style=table_header_style),
                    Th("SKU", style=table_header_style),
                    Th("IDN-SKU", style=table_header_style),
                    Th("Производитель", style=table_header_style),
                    Th("Кол-во", style=f"{table_header_style} text-align: right;"),
                    Th("Ед.", style=f"{table_header_style} text-align: center;"),
                    Th("HS Code", style=table_header_style),
                    Th("Базовая цена", style=f"{table_header_style} text-align: right;"),
                    Th("Цена", style=f"{table_header_style} text-align: right;"),
                    Th("Итого", style=f"{table_header_style} text-align: right;"),
                )),
                Tbody(*item_rows),
                style="width: 100%; border-collapse: collapse;"
            ),
            style="overflow-x: auto;"
        ),
        style=card_style
    )

    # Success/error message from query params (via session flash)
    flash_msg = ""
    flash_type = session.get("_ci_flash_type", "")
    flash_text = session.get("_ci_flash_text", "")
    if flash_text:
        bg_color = "#dcfce7" if flash_type == "success" else "#fef2f2"
        text_color = "#166534" if flash_type == "success" else "#991b1b"
        flash_msg = Div(
            flash_text,
            style=f"background: {bg_color}; color: {text_color}; padding: 12px 16px; border-radius: 8px; font-size: 14px; margin-bottom: 16px;"
        )
        # Clear flash
        session.pop("_ci_flash_type", None)
        session.pop("_ci_flash_text", None)

    # Action buttons
    btn_base_style = "padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; display: inline-flex; align-items: center; gap: 6px; text-decoration: none; width: auto;"
    btn_primary_style = f"{btn_base_style} background: #3b82f6; color: white;"
    btn_success_style = f"{btn_base_style} background: #16a34a; color: white;"
    btn_secondary_style = f"{btn_base_style} background: #f1f5f9; color: #475569; border: 1px solid #d1d5db;"
    btn_disabled_style = f"{btn_base_style} background: #f1f5f9; color: #94a3b8; cursor: not-allowed;"

    action_buttons = []

    if is_editable:
        # Save button (submits the form)
        action_buttons.append(
            Button(
                icon("save", size=14, color="white"),
                " Сохранить",
                type="submit",
                style=btn_primary_style
            )
        )
        # Verify button
        action_buttons.append(
            Button(
                icon("check-circle", size=14, color="white"),
                " Подтвердить",
                hx_post=f"/currency-invoices/{ci_id}/verify",
                hx_confirm="Подтвердить инвойс? После подтверждения редактирование будет заблокировано.",
                style=btn_success_style
            )
        )
    else:
        action_buttons.append(
            Span(
                icon("check-circle", size=14, color="#16a34a"),
                " Инвойс подтверждён",
                style="color: #16a34a; font-weight: 600; font-size: 14px; display: inline-flex; align-items: center; gap: 6px;"
            )
        )

    # Regenerate button
    action_buttons.append(
        Button(
            icon("refresh-cw", size=14, color="#475569"),
            " Пересоздать из источника",
            onclick=f"if(confirm('Все ручные изменения будут потеряны. Пересоздать?')){{var f=document.createElement('form');f.method='POST';f.action='/currency-invoices/{ci_id}/regenerate';document.body.appendChild(f);f.submit();}}",
            type="button",
            style=btn_secondary_style
        )
    )

    # Export buttons (placeholders - Task 8)
    action_buttons.append(
        A(
            icon("file-text", size=14, color="#475569"),
            " Экспорт DOCX",
            href=f"/currency-invoices/{ci_id}/download-docx",
            style=btn_secondary_style
        )
    )
    action_buttons.append(
        A(
            icon("file", size=14, color="#475569"),
            " Экспорт PDF",
            href=f"/currency-invoices/{ci_id}/download-pdf",
            style=btn_secondary_style
        )
    )

    actions_section = Div(
        *action_buttons,
        style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;"
    )

    # Wrap editable sections in a form
    if is_editable:
        page_content = Form(
            flash_msg if flash_msg else "",
            companies_section,
            markup_section,
            items_section,
            Div(actions_section, style=card_style),
            method="post",
            action=f"/currency-invoices/{ci_id}",
        )
    else:
        page_content = Div(
            flash_msg if flash_msg else "",
            companies_section,
            markup_section,
            items_section,
            Div(actions_section, style=card_style),
        )

    return page_layout(
        f"Инвойс {invoice_number}",
        back_link,
        header,
        page_content,
        session=session,
        current_path=f"/currency-invoices/{ci_id}"
    )


# @rt("/currency-invoices/{ci_id}")  # decorator removed; file is archived and not mounted
def post(
    session,
    ci_id: str,
    seller_entity: str = "",
    buyer_entity: str = "",
    markup_percent: str = "2.0",
):
    """Save currency invoice changes: company selections and markup recalculation."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller", "finance"]):
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    supabase = get_supabase()
    user = session["user"]
    org_id = user.get("org_id", "")

    # Parse entity selections
    seller_entity_type = None
    seller_entity_id = None
    if seller_entity and ":" in seller_entity:
        parts = seller_entity.split(":", 1)
        seller_entity_type = parts[0]
        seller_entity_id = parts[1]

    buyer_entity_type = None
    buyer_entity_id = None
    if buyer_entity and ":" in buyer_entity:
        parts = buyer_entity.split(":", 1)
        buyer_entity_type = parts[0]
        buyer_entity_id = parts[1]

    # Parse markup
    try:
        new_markup = float(markup_percent.strip())
    except (ValueError, AttributeError):
        new_markup = 2.0

    # Fetch current invoice to check if markup changed
    try:
        ci_resp = supabase.table("currency_invoices").select("*").eq("id", ci_id).single().execute()
        ci = ci_resp.data
    except Exception as e:
        print(f"Error fetching currency invoice {ci_id} for update: {e}")
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Ошибка при загрузке инвойса"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    if not ci or ci.get("organization_id") != org_id:
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Инвойс не найден"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    if ci.get("status") != "draft":
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Нельзя редактировать подтверждённый инвойс"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    old_markup = float(ci.get("markup_percent", 2.0) or 2.0)
    segment = ci.get("segment", "")

    # Update invoice record
    update_data = {
        "markup_percent": new_markup,
        "updated_at": datetime.now().isoformat(),
    }
    if seller_entity_type:
        update_data["seller_entity_type"] = seller_entity_type
        update_data["seller_entity_id"] = seller_entity_id
    else:
        update_data["seller_entity_type"] = "buyer_company"
        update_data["seller_entity_id"] = None

    if buyer_entity_type:
        update_data["buyer_entity_type"] = buyer_entity_type
        update_data["buyer_entity_id"] = buyer_entity_id
    else:
        update_data["buyer_entity_type"] = "buyer_company"
        update_data["buyer_entity_id"] = None

    # Recalculate item prices if markup changed
    if abs(new_markup - old_markup) > 0.001:
        try:
            from decimal import Decimal
            from services.currency_invoice_service import calculate_segment_price

            items_resp = supabase.table("currency_invoice_items").select("*").eq("currency_invoice_id", ci_id).execute()
            items = items_resp.data or []

            new_total = Decimal("0")
            for item in items:
                base_price = Decimal(str(item.get("base_price", 0) or 0))
                quantity = Decimal(str(item.get("quantity", 0) or 0))

                # For simplicity: recalculate using base_price + new markup
                # base_price already accounts for prior segment markup for TRRU items from EU chain
                new_price = base_price * (1 + Decimal(str(new_markup)) / Decimal("100"))
                new_price = new_price.quantize(Decimal("0.0001"))
                item_total = (quantity * new_price).quantize(Decimal("0.01"))

                supabase.table("currency_invoice_items").update({
                    "price": float(new_price),
                    "total": float(item_total),
                }).eq("id", item["id"]).execute()

                new_total += item_total

            update_data["total_amount"] = float(new_total)
        except Exception as e:
            print(f"Error recalculating currency invoice items: {e}")
            session["_ci_flash_type"] = "error"
            session["_ci_flash_text"] = f"Ошибка при пересчёте цен: {e}"
            return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    try:
        supabase.table("currency_invoices").update(update_data).eq("id", ci_id).execute()
    except Exception as e:
        print(f"Error updating currency invoice {ci_id}: {e}")
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = f"Ошибка при сохранении: {e}"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    session["_ci_flash_type"] = "success"
    session["_ci_flash_text"] = "Инвойс сохранён"
    return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)


# @rt("/currency-invoices/{ci_id}/verify")  # decorator removed; file is archived and not mounted
def post(session, ci_id: str):
    """Verify (confirm) a currency invoice. Requires seller and buyer to be set."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller", "finance"]):
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Нет прав для подтверждения инвойса"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    supabase = get_supabase()
    user = session["user"]
    org_id = user.get("org_id", "")

    # Fetch invoice
    try:
        ci_resp = supabase.table("currency_invoices").select("*").eq("id", ci_id).single().execute()
        ci = ci_resp.data
    except Exception as e:
        print(f"Error fetching currency invoice {ci_id} for verification: {e}")
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Ошибка при загрузке инвойса"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    if not ci or ci.get("organization_id") != org_id:
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Инвойс не найден"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    if ci.get("status") != "draft":
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Инвойс уже подтверждён"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    # Validate: both companies must be selected
    if not ci.get("seller_entity_id") or not ci.get("buyer_entity_id"):
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Выберите компании продавца и покупателя"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    # Update status to verified
    try:
        supabase.table("currency_invoices").update({
            "status": "verified",
            "verified_by": user["id"],
            "verified_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }).eq("id", ci_id).execute()
    except Exception as e:
        print(f"Error verifying currency invoice {ci_id}: {e}")
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = f"Ошибка при подтверждении: {e}"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    session["_ci_flash_type"] = "success"
    session["_ci_flash_text"] = "Инвойс подтверждён"
    return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)


# ============================================================================
# CURRENCY INVOICE DOWNLOAD ROUTES (Task 8)
# ============================================================================

def _fetch_ci_for_download(supabase, ci_id, org_id):
    """Fetch currency invoice with items and company details for download.

    Returns (ci, items, seller, buyer) or (None, None, None, None) if not found
    or org_id doesn't match.
    """
    try:
        ci_resp = supabase.table("currency_invoices").select("*").eq("id", ci_id).single().execute()
        ci = ci_resp.data
    except Exception as e:
        print(f"Error fetching currency invoice {ci_id} for download: {e}")
        return None, None, None, None

    if not ci or ci.get("organization_id") != org_id:
        return None, None, None, None

    # Fetch items
    try:
        items_resp = supabase.table("currency_invoice_items").select("*").eq("currency_invoice_id", ci_id).order("sort_order").execute()
        items = items_resp.data or []
    except Exception as e:
        print(f"Error fetching currency invoice items for download: {e}")
        items = []

    # Resolve seller and buyer company details
    seller = _resolve_company_details(supabase, ci.get("seller_entity_type"), ci.get("seller_entity_id"))
    buyer = _resolve_company_details(supabase, ci.get("buyer_entity_type"), ci.get("buyer_entity_id"))

    return ci, items, seller, buyer


# @rt("/currency-invoices/{ci_id}/download-docx")  # decorator removed; file is archived and not mounted
def get(session, ci_id: str):
    """Download currency invoice as DOCX file."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller", "finance"]):
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    supabase = get_supabase()
    user = session["user"]
    org_id = user.get("org_id", "")

    ci, items, seller, buyer = _fetch_ci_for_download(supabase, ci_id, org_id)
    if not ci:
        return Titled("Ошибка", P("Доступ запрещён"))

    # Generate DOCX
    try:
        from services.currency_invoice_export import generate_currency_invoice_docx
        docx_bytes = generate_currency_invoice_docx(ci, seller, buyer, items)
    except Exception as e:
        print(f"Error generating currency invoice DOCX: {e}")
        import traceback
        traceback.print_exc()
        return page_layout("Ошибка",
            H1("Ошибка генерации DOCX"),
            Div(f"Ошибка: {str(e)}", style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 16px; border-radius: 8px;"),
            A("Назад", href=f"/currency-invoices/{ci_id}"),
            session=session
        )

    # Build filename
    invoice_number = ci.get("invoice_number", "currency-invoice")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(invoice_number))

    from starlette.responses import Response
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.docx"'}
    )


# @rt("/currency-invoices/{ci_id}/download-pdf")  # decorator removed; file is archived and not mounted
def get(session, ci_id: str):
    """Download currency invoice as PDF file (requires libreoffice on server)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller", "finance"]):
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    supabase = get_supabase()
    user = session["user"]
    org_id = user.get("org_id", "")

    ci, items, seller, buyer = _fetch_ci_for_download(supabase, ci_id, org_id)
    if not ci:
        return Titled("Ошибка", P("Доступ запрещён"))

    # Generate DOCX first, then convert to PDF
    try:
        from services.currency_invoice_export import generate_currency_invoice_docx
        docx_bytes = generate_currency_invoice_docx(ci, seller, buyer, items)
    except Exception as e:
        print(f"Error generating currency invoice DOCX for PDF conversion: {e}")
        import traceback
        traceback.print_exc()
        return page_layout("Ошибка",
            H1("Ошибка генерации PDF"),
            Div(f"Ошибка: {str(e)}", style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 16px; border-radius: 8px;"),
            A("Назад", href=f"/currency-invoices/{ci_id}"),
            session=session
        )

    # Convert DOCX to PDF using libreoffice
    pdf_bytes = _convert_docx_to_pdf(docx_bytes)
    if pdf_bytes is None:
        # Fallback: libreoffice not available
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "PDF конвертация доступна только на сервере. Используйте DOCX экспорт."
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    # Build filename
    invoice_number = ci.get("invoice_number", "currency-invoice")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(invoice_number))

    from starlette.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'}
    )


def _resolve_company_details(supabase, entity_type, entity_id):
    """Resolve full company details (name, address, tax_id) from polymorphic FK."""
    if not entity_type or not entity_id:
        return {"name": "Не выбрана", "address": "", "tax_id": ""}
    table = "buyer_companies" if entity_type == "buyer_company" else "seller_companies"
    try:
        resp = supabase.table(table).select("name, address, tax_id").eq("id", entity_id).single().execute()
        data = resp.data or {}
        return {
            "name": data.get("name", "Неизвестно"),
            "address": data.get("address", ""),
            "tax_id": data.get("tax_id", ""),
        }
    except Exception:
        return {"name": "Неизвестно", "address": "", "tax_id": ""}


def _convert_docx_to_pdf(docx_bytes):
    """Convert DOCX bytes to PDF using libreoffice headless. Returns None if unavailable."""
    import subprocess
    import tempfile
    import os

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "invoice.docx")
            with open(docx_path, "wb") as f:
                f.write(docx_bytes)
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, docx_path],
                capture_output=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"libreoffice conversion failed: {result.stderr.decode('utf-8', errors='replace')}")
                return None
            pdf_path = os.path.join(tmpdir, "invoice.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()
    except FileNotFoundError:
        print("libreoffice not found - PDF conversion unavailable locally")
        return None
    except subprocess.TimeoutExpired:
        print("libreoffice conversion timed out")
        return None
    except Exception as e:
        print(f"PDF conversion error: {e}")
        return None
    return None


# ============================================================================
# CURRENCY INVOICE REGENERATION (Task 10)
# ============================================================================

# @rt("/currency-invoices/{ci_id}/regenerate")  # decorator removed; file is archived and not mounted
def post(session, ci_id: str):
    """Regenerate all currency invoices for the deal from source data.

    Deletes ALL existing currency invoices for the deal and re-generates
    from current quote_items data. All manual edits will be lost.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin", "currency_controller"]):
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Нет прав для пересоздания инвойсов"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    supabase = get_supabase()
    user = session["user"]
    org_id = user.get("org_id", "")

    # Fetch the currency invoice to get deal_id
    try:
        ci_resp = supabase.table("currency_invoices").select("deal_id, organization_id").eq("id", ci_id).single().execute()
        ci = ci_resp.data
    except Exception as e:
        print(f"Error fetching currency invoice {ci_id} for regeneration: {e}")
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = f"Ошибка при загрузке инвойса: {e}"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    if not ci:
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Инвойс не найден"
        return RedirectResponse("/currency-invoices", status_code=303)

    # IDOR check: verify invoice belongs to user's organization
    if not org_id or ci.get("organization_id") != org_id:
        return Titled("Ошибка", P("Доступ запрещён"))

    deal_id = ci.get("deal_id")

    if not deal_id:
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "Сделка не найдена для этого инвойса"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    # Fetch deal to get quote_id
    try:
        deal_resp = supabase.table("deals").select(
            "id, specification_id, specifications!specification_id(quote_id)"
        ).eq("id", deal_id).single().is_("deleted_at", None).execute()
        deal_data = deal_resp.data or {}
        specs = deal_data.get("specifications") or {}
        quote_id = specs.get("quote_id", "")
    except Exception as e:
        print(f"Error fetching deal {deal_id} for regeneration: {e}")
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = f"Ошибка при загрузке сделки: {e}"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    if not quote_id:
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = "КП для сделки не найдено"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    try:
        # Step 1: Delete all existing currency_invoice_items for this deal's invoices
        existing_ci_resp = supabase.table("currency_invoices").select("id").eq("deal_id", deal_id).execute()
        existing_ci_ids = [r["id"] for r in (existing_ci_resp.data or [])]
        for existing_id in existing_ci_ids:
            supabase.table("currency_invoice_items").delete().eq("currency_invoice_id", existing_id).execute()

        # Step 2: Delete all currency_invoices for this deal
        supabase.table("currency_invoices").delete().eq("deal_id", deal_id).execute()

        # Step 3: Re-fetch source data and regenerate
        from services.currency_invoice_service import generate_currency_invoices, save_currency_invoices

        ci_items, bc_lookup = _fetch_items_with_buyer_companies(supabase, quote_id)

        # Get seller_company and quote IDN
        ci_quote_resp = supabase.table("quotes").select(
            "idn_quote, seller_companies!seller_company_id(id, name)"
        ).eq("id", quote_id).single().is_("deleted_at", None).execute()
        ci_quote_data = ci_quote_resp.data or {}
        sc = (ci_quote_data.get("seller_companies") or {})
        ci_seller_company = {"id": sc.get("id"), "name": sc.get("name"), "entity_type": "seller_company"}
        ci_quote_idn = ci_quote_data.get("idn_quote", "")

        if bc_lookup and ci_seller_company.get("id"):
            ci_contracts, ci_bank_accounts = _fetch_enrichment_data(supabase, org_id)
            new_invoices = generate_currency_invoices(
                deal_id=str(deal_id),
                quote_idn=ci_quote_idn,
                items=ci_items,
                buyer_companies=bc_lookup,
                seller_company=ci_seller_company,
                organization_id=org_id,
                contracts=ci_contracts,
                bank_accounts=ci_bank_accounts,
            )
            if new_invoices:
                saved = save_currency_invoices(supabase, new_invoices)
                print(f"Currency invoices regenerated: {len(saved)} invoice(s) for deal {deal_id}")

                # Redirect to the first new invoice
                if saved and saved[0].get("id"):
                    session["_ci_flash_type"] = "success"
                    session["_ci_flash_text"] = f"Инвойсы пересозданы: {len(saved)} шт."
                    return RedirectResponse(f"/currency-invoices/{saved[0]['id']}", status_code=303)
            else:
                session["_ci_flash_type"] = "error"
                session["_ci_flash_text"] = "Не удалось сгенерировать инвойсы (нет подходящих позиций)"
                return RedirectResponse("/currency-invoices", status_code=303)
        else:
            session["_ci_flash_type"] = "error"
            session["_ci_flash_text"] = "Не найдены компании для генерации инвойсов"
            return RedirectResponse("/currency-invoices", status_code=303)

    except Exception as e:
        print(f"Error regenerating currency invoices for deal {deal_id}: {e}")
        import traceback
        traceback.print_exc()
        session["_ci_flash_type"] = "error"
        session["_ci_flash_text"] = f"Ошибка при пересоздании: {e}"
        return RedirectResponse(f"/currency-invoices/{ci_id}", status_code=303)

    # Fallback redirect
    session["_ci_flash_type"] = "success"
    session["_ci_flash_text"] = "Инвойсы пересозданы"
    return RedirectResponse("/currency-invoices", status_code=303)
