"""FastHTML control-flow bundle (Mega-B: /quote-control cluster + /spec-control
cluster) — archived 2026-04-20 during Phase 6C-2B Mega-B.

These two approval/control workflow stages — quote-control (Жанна's
checklist-gated quote-controller review) and spec-control (specification
creation, PDF/DOCX export, signed-scan upload, signature confirmation →
deal creation) — are replaced by Next.js pages reading
`/api/quotes/*` and `/api/specifications/*` FastAPI routers. Routes
unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru, which
doesn't proxy these paths back to this Python container. Preserved here
for reference / future copy-back.

Bundle rationale (Mega-B):
    Both areas are approval/control workflow stages — /quote-control
    gates the pre-spec approval step, /spec-control handles the
    spec→signed-deal step. They share the underlying workflow
    (PENDING_QUOTE_CONTROL → PENDING_APPROVAL → APPROVED →
    spec creation → approved → signed → DEAL_SIGNED). A single Mega-B
    PR reduces archive review overhead versus 2 separate PRs (scope
    previously labeled 12a + 12b).

Contents (23 @rt routes + 5 exclusive helpers + 1 exclusive constant,
~4,256 LOC total):

Area 1 — /quote-control cluster (13 routes):
  - GET    /quote-control                                          — Redirect to /dashboard?tab=quote-control
  - GET    /quote-control/{quote_id}                               — Quote Control detail view with 7-item
                                                                     Janna checklist + per-item calculation
                                                                     table + supplier-invoice verification
  - GET    /quote-control/{quote_id}/invoice-comparison            — HTMX: inline list of invoices for
                                                                     checklist card #2 expansion
  - GET    /quote-control/{quote_id}/invoice/{invoice_id}/detail   — HTMX: split-screen items + PDF scan
                                                                     iframe for a specific invoice
  - GET    /quote-control/{quote_id}/columns                       — Custom column selector page
  - POST   /quote-control/{quote_id}/columns                       — Save custom column selection
  - GET    /quote-control/{quote_id}/columns/preset/{preset_name}  — Quick preset switch (basic/full)
  - GET    /quote-control/{quote_id}/return                        — Return-for-revision form
  - POST   /quote-control/{quote_id}/return                        — Submit return with department +
                                                                     comment; calls notify_creator_of_return
  - GET    /quote-control/{quote_id}/request-approval              — Request-top-manager-approval form
  - POST   /quote-control/{quote_id}/request-approval              — Submit request-approval (justification
                                                                     variant B: round-trip via sales)
  - GET    /quote-control/{quote_id}/approve                       — Approve-confirmation page
  - POST   /quote-control/{quote_id}/approve                       — Transition quote to APPROVED

Area 2 — /spec-control cluster (10 routes):
  - GET    /spec-control                                           — Redirect to /dashboard?tab=spec-control
  - GET    /spec-control/create/{quote_id}                         — Create specification form (v3.0 with
                                                                     contract dropdown + signatory +
                                                                     seller-company prefill)
  - POST   /spec-control/create/{quote_id}                         — Insert new specification +
                                                                     auto-numbering from contract
  - GET    /spec-control/{spec_id}                                 — View/edit specification with admin-
                                                                     panel status override
  - POST   /spec-control/{spec_id}                                 — Save + action=approve + admin
                                                                     admin_change_status (signed creates deal
                                                                     and generates currency invoices)
  - GET    /spec-control/{spec_id}/preview-pdf                     — PDF preview (inline)
  - GET    /spec-control/{spec_id}/export-pdf                      — PDF download
  - GET    /spec-control/{spec_id}/export-docx                     — DOCX download (beta)
  - POST   /spec-control/{spec_id}/upload-signed                   — Upload signed scan via document_service
  - POST   /spec-control/{spec_id}/confirm-signature               — Confirm signature → create deal +
                                                                     initialize logistics stages + generate
                                                                     currency invoices + transition to
                                                                     DEAL_SIGNED

Exclusive helpers archived with their callers (5 Janna checklist
helpers + 1 constant — all only called by the archived
/quote-control/{quote_id} detail route):
  - MIN_MARKUP_RULES — dict of minimum markup rules per payment-terms
                       code (pmt_1 100% предоплата, pmt_2 100% постоплата,
                       pmt_3 частичная оплата); only used by
                       check_markup_vs_payment_terms
  - calculate_forex_risk_auto — forex risk % from prepayment %
  - check_markup_vs_payment_terms — returns markup-threshold result dict
  - build_vat_zone_info — per-item VAT zone analysis (uses live
                          normalize_country_to_iso + resolve_vat_zone +
                          EU_COUNTRY_VAT_RATES which stay in main.py)
  - compare_quote_vs_invoice_prices — invoice-coverage + scan-presence +
                                      item-pricing analysis
  - build_janna_checklist — 7-item checklist aggregator (composes the 5
                            above)

Preserved in main.py (live, consumed by other alive surfaces):
  - normalize_country_to_iso, resolve_vat_zone, EU_COUNTRY_VAT_RATES,
    COUNTRY_NAME_MAP — also used by calculation path + other consumers
  - build_calc_table, CALC_COLUMNS, CALC_PRESET_BASIC, CALC_PRESET_FULL,
    get_user_calc_columns, save_user_calc_columns — used elsewhere
  - workflow_transition_history, workflow_progress_bar, workflow_status_badge,
    quote_header, quote_detail_tabs, STATUS_NAMES, WorkflowStatus — used by
    /quotes/{id} + finance helpers
  - _fetch_items_with_buyer_companies, _fetch_enrichment_data — used by
    currency-invoice generation paths in /quotes/{id} + preserved helpers

Preserved service layers (all alive):
  - services/approval_service.py — count_pending_approvals (sidebar)
    stays alive; request_approval + get_pending_approvals_for_user become
    unused after this archive (import trimmed)
  - services/specification_service.py — validate_quote_items_have_idn_sku
    becomes unused in main.py after this archive (import trimmed); service
    file stays covered by tests/test_idn_sku_validation.py
  - services/specification_export.py, services/contract_spec_export.py,
    services/contract_spec_docx.py — PDF/DOCX generators; no main.py
    callers after archive (import stays only through
    services.specification_export.generate_specification_pdf used by
    /quotes/{id}/export/specification which stays alive)
  - services/currency_invoice_service.py — generate_currency_invoices,
    save_currency_invoices still called by preserved finance-tab helpers
  - services/document_service.py — upload_document, get_download_url still
    called by other /quotes/{id} handlers
  - services/logistics_service.py.initialize_logistics_stages — now only
    called from archived code; service file alive, may be rewired via
    /api/deals post-cutover
  - services/telegram_service.py.notify_creator_of_return — only caller
    was /quote-control/{quote_id}/return POST; import removed from main.py,
    service file stays alive covered by tests + available for future
    consumers
  - services/quote_approval_service.py — * still used by /quotes/*
    submit-justification + manager-decision + approve-department handlers
    that are alive

NOT included (separate archive decisions):
  - /quotes/*, /procurement/* — Mega-C scope, not this PR
  - /admin/* — Mega-D scope, not this PR
  - /login, /logout, /, /unauthorized — Mega-D scope, not this PR
  - /quotes/{quote_id}/chat + /quotes/{quote_id}/comments — quote-detail
    cluster, Mega-C scope
  - Previously archived in prior Megas: customers, suppliers, companies,
    settings, profile, training, approvals, changelog, telegram,
    dashboard, tasks, currency-invoices, locations, calls, documents,
    customer-contracts, supplier-invoices, finance lifecycle, deals
    detail, finance HTMX tail, customs, logistics

Sidebar/nav entries for /spec-control (main.py sidebar "Спецификации" →
/spec-control) left intact post-archive — becomes dead link but safe per
the Caddy cutover plan (kvotaflow.ru → app.kvotaflow.ru).

This file is NOT imported by main.py or api/app.py. Effectively dead
code preserved for reference. To resurrect a handler: copy back to
main.py, restore imports (page_layout, require_login, user_has_any_role,
get_supabase, icon, btn, btn_link, format_money, cast, json, os, uuid,
Decimal, datetime/date, workflow_status_badge, workflow_progress_bar,
quote_header, quote_detail_tabs, workflow_transition_history,
STATUS_NAMES, WorkflowStatus, transition_quote_status, get_user_roles_from_session,
CALC_COLUMNS, CALC_PRESET_BASIC, CALC_PRESET_FULL, build_calc_table,
normalize_country_to_iso, resolve_vat_zone, EU_COUNTRY_VAT_RATES,
COUNTRY_NAME_MAP, _fetch_items_with_buyer_companies, _fetch_enrichment_data,
MIN_MARKUP_RULES + 5 Janna helpers listed above,
services.approval_service.request_approval,
services.specification_service.validate_quote_items_have_idn_sku,
services.specification_export.generate_spec_pdf_from_spec_id,
services.contract_spec_export.{generate_contract_spec_pdf, fetch_contract_spec_data},
services.contract_spec_docx.generate_contract_spec_docx,
services.currency_invoice_service.{generate_currency_invoices, save_currency_invoices},
services.document_service.{upload_document, get_download_url},
services.logistics_service.initialize_logistics_stages,
services.supplier_invoice_service.get_quote_invoicing_summary,
services.telegram_service.notify_creator_of_return,
fasthtml components, starlette RedirectResponse/Response/JSONResponse),
re-apply the @rt decorator, and regenerate tests if needed. Not
recommended — rewrite via Next.js + FastAPI instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime, date, timezone
from decimal import Decimal

from fasthtml.common import (
    A, Br, Button, Div, Form, H1, H3, H4, Hidden, I, Iframe, Input, Label,
    Li, Option, P, Script, Select, Small, Span, Strong, Style, Table, Tbody,
    Td, Textarea, Th, Thead, Tr, Ul,
)
from starlette.responses import RedirectResponse



# ============================================================================
# JANNA CHECKLIST CONSTANTS (Task 86af8hcmv)
# Only consumer: check_markup_vs_payment_terms (below)
# ============================================================================

# Minimum markup rules for Janna's checklist (item #1)
MIN_MARKUP_RULES = {
    'pmt_1': {'code': 'pmt_1', 'name': '100% предоплата', 'min_markup_supply': 8.0, 'min_markup_transit': 0.0},
    'pmt_2': {'code': 'pmt_2', 'name': '100% постоплата', 'min_markup_supply': 15.0, 'min_markup_transit': 8.0},
    'pmt_3': {'code': 'pmt_3', 'name': 'Частичная оплата', 'min_markup_supply': 12.5, 'min_markup_transit': 5.0},
}

# VAT_SENSITIVE_COUNTRIES removed — replaced by two-factor resolve_vat_zone() mapping


# ============================================================================
# QUOTE CONTROL WORKSPACE (Features #46-51)
# ============================================================================

# @rt("/quote-control")
def get(session, status_filter: str = None):
    """
    Redirect to unified dashboard quote-control tab.
    Old URL preserved for backwards compatibility.
    """
    url = "/dashboard?tab=quote-control"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


# ============================================================================
# JANNA CHECKLIST HELPER FUNCTIONS (Task 86af8hcmv)
# ============================================================================

def calculate_forex_risk_auto(prepayment_percent):
    """
    Auto-calculate forex risk based on prepayment percentage.

    Rules:
        100%    -> 0.0% risk (fully prepaid, no forex exposure)
        45-55%  -> 1.5% risk (balanced payment)
        other   -> 3.0% risk (conservative default)
    """
    if prepayment_percent is None:
        return 3.0
    if prepayment_percent == 100:
        return 0.0
    if 45 <= prepayment_percent <= 55:
        return 1.5
    return 3.0


def check_markup_vs_payment_terms(deal_type, markup, payment_terms_code=None, prepayment_percent=None):
    """
    Check if markup meets minimum threshold for the given payment terms and deal type.

    Returns dict with: ok (bool), min_markup (float), payment_terms_code or inferred_code, message/details.
    """
    inferred = False
    if not payment_terms_code:
        inferred = True
        if prepayment_percent is not None and prepayment_percent == 100:
            payment_terms_code = 'pmt_1'
        elif prepayment_percent is not None and prepayment_percent == 0:
            payment_terms_code = 'pmt_2'
        else:
            payment_terms_code = 'pmt_3'

    rule = MIN_MARKUP_RULES.get(payment_terms_code, MIN_MARKUP_RULES['pmt_3'])

    if deal_type == 'transit':
        min_markup = rule['min_markup_transit']
    else:
        min_markup = rule['min_markup_supply']

    ok = markup >= min_markup

    result = {
        'ok': ok,
        'min_markup': min_markup,
        'payment_terms_code': payment_terms_code,
    }

    if inferred:
        result['inferred_code'] = payment_terms_code

    if ok:
        result['message'] = f"Наценка {markup}% >= минимум {min_markup}% ({rule['name']})"
        result['details'] = f"Наценка {markup}% >= минимум {min_markup}% ({rule['name']})"
    else:
        result['message'] = f"Наценка {markup}% ниже минимума {min_markup}% для {rule['name']}"
        result['details'] = f"Наценка {markup}% ниже минимума {min_markup}% для {rule['name']}"

    return result


def build_vat_zone_info(items):
    """
    Analyze VAT zone mapping for all items using resolve_vat_zone().

    Returns dict with:
        status: 'ok' | 'warning' | 'error'
        value: summary text for checklist card
        details: detailed explanation
        items: per-item analysis list
    """
    if not items:
        return {
            'status': 'info',
            'value': 'Нет позиций для проверки',
            'details': None,
            'items': [],
        }

    analyzed_items = []
    has_error = False
    has_warning = False

    for item in items:
        country_raw = item.get('supplier_country', '')
        vat_flag = bool(item.get('price_includes_vat', False))
        result = resolve_vat_zone(country_raw, vat_flag)

        iso = normalize_country_to_iso(country_raw)
        eu_info = EU_COUNTRY_VAT_RATES.get(iso)
        vat_rate_str = f" ({eu_info['vat_rate']}%)" if eu_info and vat_flag else ""

        item_status = 'ok'
        if result["error"]:
            item_status = 'error'
            has_error = True
        elif result["warning"]:
            item_status = 'warning'
            has_warning = True

        analyzed_items.append({
            'product_name': item.get('product_name', '—'),
            'country': country_raw,
            'country_display': COUNTRY_NAME_MAP.get(iso, country_raw or '—'),
            'iso': iso,
            'price_includes_vat': vat_flag,
            'vat_zone': f"{result['zone']}{vat_rate_str}" if result['zone'] else '—',
            'reason': result['reason'],
            'warning': result.get('warning'),
            'error': result.get('error'),
            'status': item_status,
        })

    # Build summary
    total = len(analyzed_items)
    errors = sum(1 for i in analyzed_items if i['status'] == 'error')
    warnings = sum(1 for i in analyzed_items if i['status'] == 'warning')
    ok_count = total - errors - warnings

    if has_error:
        status = 'error'
        value = f"{errors} из {total} позиций — ошибка маппинга НДС"
    elif has_warning:
        status = 'warning'
        value = f"{total} позиций, {warnings} требуют проверки"
    else:
        status = 'ok'
        value = f"{total} позиций — все зоны определены"

    # Build details text
    zones_used = set()
    for ai in analyzed_items:
        if ai['status'] != 'error':
            zones_used.add(ai.get('vat_zone', ''))
    details = f"Зоны: {', '.join(sorted(zones_used))}" if zones_used else None

    return {
        'status': status,
        'value': value,
        'details': details,
        'items': analyzed_items,
    }


def compare_quote_vs_invoice_prices(quote_id, items, supabase):
    """
    Check invoice coverage for a quote: count invoices, scan attachments, and item pricing.
    Returns dict with: status, value, details, invoice_count, scans_ok, pricing_ok.
    """
    if not items:
        return {
            'status': 'info',
            'value': 'Нет позиций для сверки',
            'details': '',
            'mismatches': [],
        }

    try:
        # 1. Count procurement invoices for this quote
        invoices_resp = supabase.table("invoices") \
            .select("id") \
            .eq("quote_id", quote_id) \
            .execute()
        invoice_list = invoices_resp.data or []
        invoice_count = len(invoice_list)
    except Exception:
        invoice_list = []
        invoice_count = 0

    if invoice_count == 0:
        return {
            'status': 'warning',
            'value': 'Нет инвойсов поставщиков',
            'details': '',
            'mismatches': [],
            'no_invoices': True,
        }

    # 2. Check which invoices have scan attachments via documents table
    invoice_ids = [inv['id'] for inv in invoice_list]
    invoices_with_scans = 0
    try:
        if invoice_ids:
            docs_resp = supabase.table("documents") \
                .select("entity_id") \
                .eq("entity_type", "supplier_invoice") \
                .in_("entity_id", invoice_ids) \
                .execute()
            invoices_with_scans = len(set(d['entity_id'] for d in (docs_resp.data or [])))
    except Exception:
        invoices_with_scans = 0

    invoices_without_scans = invoice_count - invoices_with_scans

    # 3. Check item pricing completeness (items linked to invoices)
    try:
        items_resp = supabase.table("quote_items") \
            .select("id, purchase_price_original, invoice_id") \
            .eq("quote_id", quote_id) \
            .not_.is_("invoice_id", "null") \
            .execute()
        invoiced_items = items_resp.data or []
    except Exception:
        invoiced_items = []

    total_invoiced_items = len(invoiced_items)
    unpriced_items = sum(1 for i in invoiced_items if not float(i.get('purchase_price_original') or 0) > 0)

    # Build status and display text
    parts = [f"{invoice_count} инвойс" + ("а" if 2 <= invoice_count <= 4 else "ов" if invoice_count >= 5 else "")]

    if invoices_without_scans > 0:
        parts.append(f"{invoices_without_scans} без скана")
        status = 'warning'
    elif unpriced_items > 0:
        parts.append("все со сканами")
        parts.append(f"{unpriced_items}/{total_invoiced_items} без цены")
        status = 'warning'
    else:
        if invoices_with_scans == invoice_count:
            parts.append("все со сканами")
        if total_invoiced_items > 0:
            parts.append("все цены заполнены")
        status = 'ok'

    return {
        'status': status,
        'value': ', '.join(parts),
        'details': '',
        'mismatches': [],
    }


def build_janna_checklist(quote, calc_vars, calc_summary, items, supabase=None):
    """
    Build the 7-item Janna checklist for quote control.

    Items:
    1. Наценка vs условия оплаты (auto)
    2. Цены КП vs инвойс закупки (auto)
    3. Страна + НДС (auto_flag)
    4. Логистика (reference)
    5. Таможня (reference)
    6. Курсовая разница (auto)
    7. Откат / ЛПР (approval)
    """
    checklist = []

    deal_type = quote.get('deal_type') or calc_vars.get('offer_sale_type', 'supply')
    markup = float(calc_vars.get('markup', 0) or 0)
    payment_terms_code = calc_vars.get('payment_terms_code')
    prepayment_percent = calc_vars.get('advance_from_client')
    if prepayment_percent is not None:
        prepayment_percent = float(prepayment_percent)
    lpr_reward = float(calc_vars.get('lpr_reward', 0) or 0)

    # 1. Наценка vs условия оплаты
    markup_result = check_markup_vs_payment_terms(
        deal_type=deal_type,
        markup=markup,
        payment_terms_code=payment_terms_code,
        prepayment_percent=prepayment_percent,
    )
    checklist.append({
        'name': 'Наценка vs условия оплаты',
        'status': 'ok' if markup_result['ok'] else 'error',
        'value': f"{markup}% (мин. {markup_result['min_markup']}%)",
        'details': markup_result.get('details', ''),
        'type': 'auto',
    })

    # 2. Цены КП vs инвойс закупки
    invoice_result = compare_quote_vs_invoice_prices(
        quote_id=quote.get('id', ''),
        items=items,
        supabase=supabase,
    ) if supabase else {'status': 'info', 'value': 'Нет данных', 'details': [], 'mismatches': []}
    checklist.append({
        'name': 'Цены КП ↔ инвойс закупки',
        'status': invoice_result['status'],
        'value': invoice_result['value'],
        'details': str(invoice_result.get('details', '')),
        'type': 'auto',
    })

    # 3. Страна + НДС (two-factor mapping: country + price_includes_vat)
    vat_result = build_vat_zone_info(items)
    checklist.append({
        'name': 'Страна + НДС',
        'status': vat_result['status'],
        'value': vat_result['value'],
        'details': vat_result.get('details'),
        'type': 'auto_flag',
        'vat_items': vat_result.get('items', []),
    })

    # 4. Логистика
    total_logistics = float(calc_summary.get('calc_v16_total_logistics', 0) or 0)
    logistics_status = 'ok' if total_logistics > 0 else 'warning'
    checklist.append({
        'name': 'Логистика',
        'status': logistics_status,
        'value': f"{total_logistics:,.2f}" if total_logistics else 'Не рассчитана',
        'details': f"Итого логистика из расчёта",
        'type': 'reference',
    })

    # 5. Таможня
    customs_duty = float(calc_vars.get('customs_duty', 0) or calc_vars.get('customs_rate', 0) or 0)
    customs_status = 'ok' if customs_duty >= 0 else 'warning'
    checklist.append({
        'name': 'Таможня',
        'status': customs_status,
        'value': f"{customs_duty}%" if customs_duty else 'Не указана',
        'details': 'Ставка таможенной пошлины',
        'type': 'reference',
    })

    # 6. Курсовая разница
    auto_forex = calculate_forex_risk_auto(prepayment_percent)
    actual_forex = float(calc_vars.get('forex_risk_percent', auto_forex) or auto_forex)
    forex_status = 'ok' if actual_forex >= 0 else 'warning'
    checklist.append({
        'name': 'Курсовая разница',
        'status': forex_status,
        'value': f"{auto_forex}%",
        'details': f"Авто-расчёт по предоплате {prepayment_percent}%" if prepayment_percent is not None else "Предоплата не указана",
        'type': 'auto',
    })

    # 7. Откат / ЛПР
    lpr_status = 'warning' if lpr_reward > 0 else 'ok'
    checklist.append({
        'name': 'Откат / ЛПР',
        'status': lpr_status,
        'value': f"{lpr_reward}" if lpr_reward > 0 else 'Нет',
        'details': 'Требует согласования' if lpr_reward > 0 else None,
        'type': 'approval',
    })

    return checklist


# ============================================================================
# QUOTE CONTROL DETAIL VIEW (Feature #48)
# ============================================================================

# @rt("/quote-control/{quote_id}")
def get(session, quote_id: str, preset: str = None):
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

    Query params:
        preset: 'basic', 'full', or 'custom' - which column preset to display
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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
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

    # Get detailed calculation results from quote_calculation_results (all phases)
    calc_results_query = supabase.table("quote_calculation_results") \
        .select("quote_item_id, phase_results") \
        .eq("quote_id", quote_id) \
        .execute()

    # Get aggregated totals from quote_calculation_summaries
    calc_summary_result = supabase.table("quote_calculation_summaries") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()
    calc_summary = calc_summary_result.data[0] if calc_summary_result.data else {}

    # Build items data with phase_results joined
    items_by_id = {item["id"]: item for item in items}
    calc_items_data = []
    if calc_results_query.data:
        for cr in calc_results_query.data:
            item_id = cr.get("quote_item_id")
            item = items_by_id.get(item_id, {})
            calc_items_data.append({
                "id": item_id,
                "product_name": item.get("product_name", "—"),
                "quantity": item.get("quantity", 0),
                "phase_results": cr.get("phase_results", {})
            })

    # Fallback to quote_versions if no calculation results
    if not calc_items_data:
        version_result = supabase.table("quote_versions") \
            .select("input_variables") \
            .eq("quote_id", quote_id) \
            .order("version", desc=True) \
            .limit(1) \
            .execute()
        if version_result.data:
            input_vars = version_result.data[0].get("input_variables", {})
            for r in input_vars.get("results", []):
                item_id = r.get("item_id")
                item = items_by_id.get(item_id, {})
                calc_items_data.append({
                    "id": item_id,
                    "product_name": item.get("product_name", "—"),
                    "quantity": item.get("quantity", 0),
                    "phase_results": r  # Results are already phase data
                })
            # Also get variables from version if not from quote_calculation_variables
            if not calc_vars:
                calc_vars = input_vars.get("variables", {})

    # Get user's column preferences (URL param overrides saved setting)
    user_calc_preset = "basic"  # Default
    user_calc_columns = CALC_PRESET_BASIC
    user_custom_columns = None  # Saved custom columns if any

    # First load saved settings
    try:
        user_settings_result = supabase.table("user_settings") \
            .select("setting_value") \
            .eq("user_id", user_id) \
            .eq("setting_key", "quote_control_columns") \
            .execute()
        if user_settings_result.data:
            setting = user_settings_result.data[0].get("setting_value", {})
            user_custom_columns = setting.get("columns", CALC_PRESET_BASIC)
            if not preset:  # Only use saved preset if no URL param
                user_calc_preset = setting.get("preset", "basic")
    except Exception:
        pass

    # URL param overrides saved setting
    if preset in ("basic", "full", "custom"):
        user_calc_preset = preset

    # Set columns based on active preset
    if user_calc_preset == "full":
        user_calc_columns = CALC_PRESET_FULL
    elif user_calc_preset == "custom" and user_custom_columns:
        user_calc_columns = user_custom_columns
    else:
        user_calc_columns = CALC_PRESET_BASIC

    # Determine if editing is allowed
    can_edit = workflow_status in {"pending_quote_control", "pending_approval"}

    # Load organization's calculation settings for fallback values
    calc_settings_result = supabase.table("calculation_settings") \
        .select("*") \
        .eq("organization_id", org_id) \
        .execute()
    org_calc_settings = calc_settings_result.data[0] if calc_settings_result.data else {}

    # Extract values for checklist verification
    deal_type = quote.get("deal_type") or calc_vars.get("offer_sale_type", "")
    incoterms = calc_vars.get("offer_incoterms", "")
    currency = quote.get("currency", "USD")
    markup = float(calc_vars.get("markup", 0) or 0)
    supplier_advance = float(calc_vars.get("supplier_advance", 0) or 0)
    exchange_rate = float(calc_vars.get("exchange_rate", 1.0) or 1.0)
    # Forex risk: first from quote calculation, then from org settings, default 3%
    forex_risk = float(calc_vars.get("forex_risk_percent", 0) or org_calc_settings.get("rate_forex_risk", 3) or 0)
    lpr_reward = float(calc_vars.get("lpr_reward", 0) or calc_vars.get("decision_maker_reward", 0) or 0)

    # Payment terms
    payment_terms = calc_vars.get("client_payment_terms", "")
    prepayment = float(calc_vars.get("advance_from_client", 100) or 100)

    # Logistics costs - get from calculation results, not input variables
    # calc_summary has the aggregated total, phase_results has per-item breakdown
    total_logistics = float(calc_summary.get("calc_v16_total_logistics", 0) or 0)

    # Calculate leg breakdown from phase_results (T16 = first leg, U16 = last leg)
    # Note: V16 = T16 + U16 (total logistics per item)
    logistics_first_leg = sum(
        float((item.get("phase_results") or {}).get("T16", 0) or 0)
        for item in calc_items_data
    )
    logistics_last_leg = sum(
        float((item.get("phase_results") or {}).get("U16", 0) or 0)
        for item in calc_items_data
    )
    # For display: first leg = supplier to hub + hub to customs, last leg = customs to client
    # Simplified display as two legs since that's what calculation engine provides
    logistics_supplier_hub = logistics_first_leg
    logistics_hub_customs = 0  # Combined into first_leg in calculation
    logistics_customs_client = logistics_last_leg

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

    # Build checklist items with auto-detected status (modern card design)
    def checklist_item(name, description, value, status="info", details=None):
        """Create a modern checklist card with status indicator using Lucide icons."""
        status_config = {
            "ok": {
                "bg": "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
                "border": "#86efac",
                "text": "#166534",
                "icon_name": "check-circle",
                "icon_color": "#22c55e"
            },
            "warning": {
                "bg": "linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)",
                "border": "#fcd34d",
                "text": "#92400e",
                "icon_name": "alert-triangle",
                "icon_color": "#f59e0b"
            },
            "error": {
                "bg": "linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)",
                "border": "#fca5a5",
                "text": "#991b1b",
                "icon_name": "x-circle",
                "icon_color": "#ef4444"
            },
            "info": {
                "bg": "linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)",
                "border": "#93c5fd",
                "text": "#1e40af",
                "icon_name": "info",
                "icon_color": "#3b82f6"
            },
        }
        cfg = status_config.get(status, status_config["info"])

        # Extract item number from name (e.g., "1. Тип сделки" -> "1")
        item_name = name.split(". ", 1)[-1] if ". " in name else name

        return Div(
            # Header: status icon + name
            Div(
                icon(cfg["icon_name"], size=16, color=cfg["icon_color"]),
                Span(item_name, style=f"font-weight: 600; font-size: 0.8125rem; color: #374151; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 0.5rem;"
            ),
            # Value
            Div(
                Span(str(value) if value else "—", style=f"font-weight: 600; font-size: 0.875rem; color: {cfg['text']};"),
                style="margin-bottom: 0.25rem;"
            ),
            # Details (if present)
            Div(
                Span(details, style="color: #64748b; font-size: 0.75rem;"),
                style="margin-top: 0.25rem;"
            ) if details else None,
            title=description,  # Description as tooltip
            style=f"padding: 0.75rem; background: {cfg['bg']}; border: 1px solid {cfg['border']}; border-radius: 8px; cursor: help; box-shadow: 0 1px 3px rgba(0,0,0,0.04);"
        )

    # Generate Janna's 7-item checklist (Task 86af8hcmv)
    deal_type_display = "Поставка" if deal_type == "supply" else ("Транзит" if deal_type == "transit" else deal_type or "Не указан")
    janna_checklist_data = build_janna_checklist(quote, calc_vars, calc_summary, items, supabase)

    # Render checklist items as cards
    checklist_items = []
    for idx, cl_item in enumerate(janna_checklist_data):
        card = checklist_item(
            f"{idx + 1}. {cl_item['name']}",
            cl_item.get('details', '') or '',
            cl_item.get('value', '—'),
            cl_item.get('status', 'info'),
            cl_item.get('details'),
        )
        # Card #2 (idx=1): "Цены КП ↔ инвойс закупки" — make clickable with hx-get for invoice comparison
        if idx == 1:
            card = Div(
                card,
                hx_get=f"/quote-control/{quote_id}/invoice-comparison",
                hx_target="#invoice-comparison-details",
                hx_swap="innerHTML",
                onclick="toggleInvoiceComparisonCard(this)",
                style="cursor: pointer;",
            )
        # Card #3 (idx=2): "Страна + НДС" — expandable per-item VAT zone detail
        if idx == 2 and cl_item.get('vat_items'):
            vat_detail_rows = []
            for vi in cl_item['vat_items']:
                vat_flag_icon = "☑ НДС" if vi['price_includes_vat'] else "☐ без НДС"
                row_color = {"ok": "#166534", "warning": "#92400e", "error": "#991b1b"}.get(vi['status'], "#374151")
                status_prefix = {"warning": "⚠️ ", "error": "❌ "}.get(vi['status'], "")
                vat_detail_rows.append(
                    Div(
                        Div(
                            Span(f"{status_prefix}{vi['product_name'][:30]}", style=f"font-weight: 500; color: {row_color};"),
                            Span(f"{vi['country_display']} ({vi['iso']})" if vi['iso'] else vi['country_display'],
                                 style="color: #64748b; margin-left: 8px; font-size: 0.8125rem;"),
                            Span(vat_flag_icon, style="margin-left: 8px; font-size: 0.75rem; color: #64748b;"),
                            style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;"
                        ),
                        Div(
                            Span(f"→ {vi['reason']}", style="font-size: 0.75rem; color: #6b7280;"),
                            Span(vi['error'], style="font-size: 0.75rem; color: #ef4444; margin-left: 8px;") if vi.get('error') else None,
                            style="margin-top: 2px;"
                        ),
                        style="padding: 6px 0; border-bottom: 1px solid #f1f5f9;"
                    )
                )
            vat_detail_panel = Div(
                *vat_detail_rows,
                id="vat-zone-details",
                style="display: none; margin-top: 8px; padding: 8px; background: #f8fafc; border-radius: 6px; font-size: 0.8125rem;"
            )
            card = Div(
                card,
                vat_detail_panel,
                onclick="var d=this.querySelector('#vat-zone-details'); d.style.display=d.style.display==='none'?'block':'none';",
                style="cursor: pointer;",
            )
        checklist_items.append(card)

    # Load invoicing summary for detail section (using supplier_invoice_items for per-item breakdown)
    # This is separate from criterion 11 which checks internal invoices
    from services.supplier_invoice_service import get_quote_invoicing_summary
    invoicing_summary = get_quote_invoicing_summary(quote_id)

    # Summary info
    customer_name = (quote.get("customers") or {}).get("name", "—")
    quote_total = float(quote.get("total_amount", 0) or 0)

    # Status banner
    if workflow_status == "pending_quote_control":
        status_banner = Div(
            icon("clipboard-list", size=20), " Требуется проверка",
            style="background: #fef3c7; color: #92400e; padding: 1rem; border-radius: 8px; text-align: center; font-weight: 500; margin-bottom: 1rem; display: flex; justify-content: center; align-items: center; gap: 0.5rem;"
        )
    elif workflow_status == "pending_approval":
        status_banner = Div(
            icon("clock", size=20), " Ожидает согласования топ-менеджера",
            style="background: #dbeafe; color: #1e40af; padding: 1rem; border-radius: 8px; text-align: center; font-weight: 500; margin-bottom: 1rem; display: flex; justify-content: center; align-items: center; gap: 0.5rem;"
        )
    elif workflow_status == "approved":
        status_banner = Div(
            icon("check-circle", size=20), " КП одобрено",
            style="background: #dcfce7; color: #166534; padding: 1rem; border-radius: 8px; text-align: center; font-weight: 500; margin-bottom: 1rem; display: flex; justify-content: center; align-items: center; gap: 0.5rem;"
        )
    else:
        status_banner = Div(
            "Статус: ", workflow_status_badge(workflow_status),
            style="margin-bottom: 1rem;"
        )

    # Approval requirements banner
    approval_banner = None
    if needs_approval and workflow_status == "pending_quote_control":
        approval_banner = Div(
            H4(icon("alert-triangle", size=18), " Требуется согласование топ-менеджера", style="color: #b45309; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;"),
            Ul(*[Li(reason) for reason in needs_approval_reasons], style="margin: 0; padding-left: 1.5rem; color: #92400e;"),
            style="background: #fef3c7; border: 1px solid #f59e0b; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"
        )

    return page_layout(f"Проверка КП - {quote.get('idn_quote', '')}",
        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "control", user.get("roles", []), quote=quote, user_id=user_id),

        # Workflow progress bar (Feature #87)
        workflow_progress_bar(workflow_status),

        # Status banner
        status_banner,

        # Approval requirements banner
        approval_banner,

        # Quote summary card with gradient styling
        Div(
            # Section header
            Div(
                icon("file-text", size=16, color="#64748b"),
                Span(" СВОДКА ПО КП", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0;"
            ),
            # Summary grid with 5 columns
            Div(
                Div(
                    Span("ТИП СДЕЛКИ", style="font-size: 11px; color: #64748b; text-transform: uppercase; display: block; margin-bottom: 4px;"),
                    Span(deal_type_display, style="font-weight: 600; color: #1e40af;"),
                ),
                Div(
                    Span("INCOTERMS", style="font-size: 11px; color: #64748b; text-transform: uppercase; display: block; margin-bottom: 4px;"),
                    Span(incoterms or "—", style="font-weight: 600; color: #1e40af;"),
                ),
                Div(
                    Span("ВАЛЮТА", style="font-size: 11px; color: #64748b; text-transform: uppercase; display: block; margin-bottom: 4px;"),
                    Span(currency, style="font-weight: 600; color: #1e40af;"),
                ),
                Div(
                    Span("НАЦЕНКА", style="font-size: 11px; color: #64748b; text-transform: uppercase; display: block; margin-bottom: 4px;"),
                    Span(f"{markup}%", style="font-weight: 600; color: #1e40af;"),
                ),
                Div(
                    Span("ПОЗИЦИЙ", style="font-size: 11px; color: #64748b; text-transform: uppercase; display: block; margin-bottom: 4px;"),
                    Span(str(len(items)), style="font-weight: 600; color: #1e40af;"),
                ),
                style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem;"
            ),
            cls="card",
            style="margin-bottom: 1rem; padding: 1.25rem; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Checklist (modern 3-column grid)
        Div(
            # Section header
            Div(
                icon("check-square", size=16, color="#64748b"),
                Span(" ЧЕК-ЛИСТ ПРОВЕРКИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0;"
            ),
            P("Проверьте все пункты перед одобрением или возвратом КП", style="color: #64748b; margin-bottom: 1rem; font-size: 0.8125rem;"),
            Div(
                *checklist_items,
                style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem;"
            ),
            cls="card",
            style="padding: 1.25rem; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Invoice comparison expansion target (populated via HTMX from checklist card #2)
        Div(id="invoice-comparison-details"),

        # JavaScript toggle function for invoice comparison card expand/collapse
        Script("""
        function toggleInvoiceComparisonCard(el) {
            var details = document.getElementById('invoice-comparison-details');
            if (details && details.innerHTML.trim() !== '') {
                // Already expanded — collapse
                details.innerHTML = '';
                // Cancel the HTMX request since we are collapsing
                if (typeof htmx !== 'undefined') { htmx.trigger(el, 'htmx:abort'); }
                return false;
            }
            // Let HTMX handle the expansion
            return true;
        }
        """),

        # Detailed Calculation Results Table with Preset Selector
        Div(
            # Section header
            Div(
                icon("calculator", size=16, color="#64748b"),
                Span(" ДЕТАЛИ РАСЧЁТА ПО ПОЗИЦИЯМ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0;"
            ),
            P("Промежуточные значения расчёта для каждой позиции", style="color: #64748b; margin-bottom: 1rem; font-size: 0.8125rem;"),

            # Preset selector (links include #calc-table anchor to preserve scroll position)
            Div(
                Span("Показать:", style="margin-right: 0.5rem; font-weight: 500;"),
                A(
                    "Базовый",
                    href=f"/quote-control/{quote_id}?preset=basic#calc-table",
                    cls="btn btn-sm" + (" btn-primary" if user_calc_preset == "basic" else ""),
                    style="margin-right: 0.25rem;"
                ),
                A(
                    "Полный",
                    href=f"/quote-control/{quote_id}?preset=full#calc-table",
                    cls="btn btn-sm" + (" btn-primary" if user_calc_preset == "full" else ""),
                    style="margin-right: 0.25rem;"
                ),
                A(
                    "Настроить...",
                    href=f"/quote-control/{quote_id}/columns",
                    cls="btn btn-sm" + (" btn-primary" if user_calc_preset == "custom" else ""),
                ),
                style="display: flex; align-items: center; margin-bottom: 1rem;"
            ),

            # Summary totals from calc_summary
            Div(
                Div(
                    Strong("Итого закупка: "),
                    format_money(float(calc_summary.get('calc_s16_total_purchase_price', 0) or 0), currency),
                    style="margin-right: 2rem;"
                ),
                Div(
                    Strong("Себестоимость: "),
                    format_money(float(calc_summary.get('calc_ab16_cogs_total', 0) or 0), currency),
                    style="margin-right: 2rem;"
                ),
                Div(
                    Strong("Логистика: "),
                    format_money(float(calc_summary.get('calc_v16_total_logistics', 0) or 0), currency),
                    style="margin-right: 2rem;"
                ),
                Div(
                    Strong("Продажа с НДС: "),
                    format_money(float(calc_summary.get('calc_al16_total_with_vat', 0) or 0), currency),
                    style="margin-right: 2rem; color: #22c55e; font-weight: 500;"
                ),
                style="display: flex; flex-wrap: wrap; gap: 1rem; padding: 1rem; background: #f0fdf4; border-radius: 8px; margin-bottom: 1rem;"
            ) if calc_summary else None,

            # Per-item calculation table using build_calc_table
            Div(
                build_calc_table(calc_items_data, calc_summary, user_calc_columns, currency) if calc_items_data else
                    Div(
                        P("Нет данных расчёта. Выполните расчёт КП.", style="text-align: center; color: #666; padding: 2rem;")
                    ),
                style="overflow-x: auto;"
            ),

            # Column legend for current preset
            Div(
                P(
                    Strong("Отображаемые колонки: "),
                    ", ".join([CALC_COLUMNS.get(col, {}).get("name", col) for col in user_calc_columns]),
                    style="font-size: 0.75rem; color: #666;"
                ),
                style="margin-top: 0.5rem;"
            ),

            id="calc-table",
            cls="card",
            style="margin-top: 1rem; padding: 1.25rem; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if calc_items_data or calc_summary else None,

        # Invoice verification detail (v3.0 Feature UI-022)
        Div(
            # Section header
            Div(
                icon("receipt", size=16, color="#64748b"),
                Span(" ПРОВЕРКА ИНВОЙСОВ ПОСТАВЩИКОВ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0;"
            ),
            P("Сверка сумм и позиций с инвойсами в реестре", style="color: #64748b; margin-bottom: 1rem; font-size: 0.8125rem;"),
            # Summary stats
            Div(
                Div(
                    Span(f"{invoicing_summary.items_with_invoices}", style="font-size: 1.5rem; font-weight: bold;"),
                    Span(f" / {invoicing_summary.total_items} позиций с инвойсами",
                         style="color: #666;"),
                    style="text-align: center;"
                ),
                Div(
                    Span(f"{invoicing_summary.coverage_percent:.0f}%", style="font-size: 1.25rem; font-weight: bold; color: #22c55e;" if invoicing_summary.coverage_percent == 100 else "font-size: 1.25rem; font-weight: bold; color: #f59e0b;"),
                    Span(" покрытие", style="color: #666;"),
                    style="text-align: center;"
                ),
                style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 1rem; background: #f9fafb; border-radius: 8px; margin-bottom: 1rem;"
            ),
            # Items table
            Table(
                Thead(
                    Tr(
                        Th("Товар", style="text-align: left;"),
                        Th("Кол-во", style="text-align: right;"),
                        Th("Инвойс кол-во", style="text-align: right;"),
                        Th("Инвойс сумма", style="text-align: right;"),
                        Th("Статус", style="text-align: center;"),
                    )
                ),
                Tbody(
                    *[
                        Tr(
                            Td(item.product_name or "—", style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;"),
                            Td(f"{item.quote_quantity:.0f}", style="text-align: right;"),
                            Td(
                                f"{item.invoiced_quantity:.0f}" if item.invoice_count > 0 else "—",
                                style="text-align: right;"
                            ),
                            Td(
                                format_money(float(item.invoiced_amount)) if item.invoice_count > 0 else "—",
                                style="text-align: right;"
                            ),
                            Td(
                                Span("✓", style="color: #22c55e; font-weight: bold;") if item.is_fully_invoiced else (
                                    Span("◐", style="color: #f59e0b;", title="Частично") if item.invoice_count > 0 else Span("✗", style="color: #ef4444;", title="Нет инвойса")
                                ),
                                style="text-align: center;"
                            )
                        )
                        for item in invoicing_summary.items
                    ] if invoicing_summary.items else [
                        Tr(
                            Td("Нет позиций для проверки", colspan="5", style="text-align: center; color: #666; padding: 1rem;")
                        )
                    ]
                ),
                style="width: 100%;"
            ),
            # Link to supplier invoices registry
            Div(
                A(icon("clipboard-list", size=16), " Открыть реестр инвойсов поставщиков →", href="/supplier-invoices",
                  style="color: #3b82f6; text-decoration: none; font-size: 0.875rem;"),
                style="margin-top: 1rem; text-align: right;"
            ),
            cls="card",
            style="margin-top: 1rem; padding: 1.25rem; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if invoicing_summary.total_items > 0 else None,

        # Action buttons (only if can edit)
        Div(
            # Section header
            Div(
                icon("zap", size=16, color="#64748b"),
                Span(" ДЕЙСТВИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0;"
            ),
            Div(
                # Return for revision button
                A(
                    icon("rotate-ccw", size=16, color="white"),
                    Span(" Вернуть на доработку", style="margin-left: 6px;"),
                    href=f"/quote-control/{quote_id}/return",
                    role="button",
                    style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); border: none; border-radius: 8px; padding: 0.625rem 1rem; display: inline-flex; align-items: center; text-decoration: none; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                ),
                # Always allow direct approval
                A(
                    icon("check", size=16, color="white"),
                    Span(" Одобрить", style="margin-left: 6px;"),
                    href=f"/quote-control/{quote_id}/approve",
                    role="button",
                    style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); border: none; border-radius: 8px; padding: 0.625rem 1rem; display: inline-flex; align-items: center; text-decoration: none; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                ) if workflow_status in {"pending_quote_control", "pending_approval"} else None,
                # Optionally send for top-manager approval
                A(
                    icon("clock", size=16, color="white"),
                    Span(" Отправить на согласование", style="margin-left: 6px;"),
                    href=f"/quote-control/{quote_id}/request-approval",
                    role="button",
                    style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); border: none; border-radius: 8px; padding: 0.625rem 1rem; display: inline-flex; align-items: center; text-decoration: none; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                ) if workflow_status == "pending_quote_control" and needs_approval else None,
                style="display: flex; gap: 1rem; flex-wrap: wrap;"
            ),
            cls="card",
            style="margin-top: 1rem; padding: 1.25rem; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if can_edit else Div(
            P("Редактирование недоступно в текущем статусе", style="color: #64748b; text-align: center;"),
            cls="card",
            style="margin-top: 1rem; padding: 1.25rem; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Link to quote details
        Div(
            A(icon("file-text", size=16), " Открыть КП в редакторе", href=f"/quotes/{quote_id}", role="button",
              style="background: #6b7280; border-color: #6b7280;"),
            style="margin-top: 1rem; text-align: center;"
        ),

        # Transition history (Feature #88)
        workflow_transition_history(quote_id),

        session=session
    )


# ============================================================================
# QUOTE CONTROL - INVOICE COMPARISON (HTMX endpoints)
# ============================================================================

# @rt("/quote-control/{quote_id}/invoice-comparison")
def get(session, quote_id: str):
    """
    HTMX endpoint: returns the list of invoices for inline expansion
    under checklist card #2 (Цены КП ↔ инвойс закупки).
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return Div("Нет доступа", style="color: #ef4444; padding: 1rem;")

    supabase = get_supabase()

    # Fetch invoices for this quote with supplier names
    try:
        invoices_resp = supabase.table("invoices") \
            .select("id, invoice_number, currency, supplier_id, suppliers!supplier_id(name)") \
            .eq("quote_id", quote_id) \
            .execute()
        invoices = invoices_resp.data or []
    except Exception:
        invoices = []

    if not invoices:
        return Div(
            P("Нет инвойсов поставщиков", style="color: #64748b; text-align: center; padding: 1rem;"),
            style="margin-top: 0.75rem; padding: 1rem; background: #f9fafb; border-radius: 8px; border: 1px solid #e2e8f0;"
        )

    # Fetch documents (scans) for these invoices
    invoice_ids = [inv["id"] for inv in invoices]
    try:
        docs_resp = supabase.table("documents") \
            .select("id, entity_id, storage_path, original_filename") \
            .eq("entity_type", "supplier_invoice") \
            .in_("entity_id", invoice_ids) \
            .execute()
        docs = docs_resp.data or []
    except Exception:
        docs = []

    # Map invoice_id -> document existence
    docs_by_invoice = {}
    for doc in docs:
        docs_by_invoice[doc["entity_id"]] = doc

    # Count items per invoice
    try:
        items_resp = supabase.table("quote_items") \
            .select("id, invoice_id, purchase_price_original, quantity") \
            .eq("quote_id", quote_id) \
            .in_("invoice_id", invoice_ids) \
            .execute()
        items_data = items_resp.data or []
    except Exception:
        items_data = []

    items_by_invoice = {}
    for item in items_data:
        inv_id = item.get("invoice_id")
        if inv_id:
            items_by_invoice.setdefault(inv_id, []).append(item)

    # Render invoice rows
    rows = []
    for inv in invoices:
        inv_id = inv["id"]
        inv_number = inv.get("invoice_number", "—")
        supplier_name = (inv.get("suppliers") or {}).get("name", "—")
        currency = inv.get("currency", "USD")
        inv_items = items_by_invoice.get(inv_id, [])
        items_count = len(inv_items)
        total_amount = sum(
            float(it.get("purchase_price_original") or 0) * float(it.get("quantity") or 0)
            for it in inv_items
        )
        has_scan = inv_id in docs_by_invoice
        scan_label = "Скан загружен" if has_scan else "Нет скана"
        scan_color = "#22c55e" if has_scan else "#ef4444"

        rows.append(
            Div(
                Div(
                    Span(f"{inv_number}", style="font-weight: 600; color: #1e40af;"),
                    Span(f" | {supplier_name}", style="color: #64748b; font-size: 0.8125rem;"),
                    Span(f" | {items_count} поз.", style="color: #64748b; font-size: 0.8125rem;"),
                    Span(f" | {total_amount:,.2f} {currency}", style="color: #374151; font-size: 0.8125rem; font-weight: 500;"),
                    Span(f" | ", style="color: #d1d5db;"),
                    Span(scan_label, style=f"color: {scan_color}; font-size: 0.75rem; font-weight: 500;"),
                    style="display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap;"
                ),
                # Detail expansion target for this invoice
                Div(id=f"invoice-detail-{inv_id}"),
                hx_get=f"/quote-control/{quote_id}/invoice/{inv_id}/detail",
                hx_target=f"#invoice-detail-{inv_id}",
                hx_swap="innerHTML",
                style="padding: 0.75rem; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 0.5rem; cursor: pointer; background: white; transition: background 0.15s;",
            )
        )

    return Div(
        *rows,
        style="margin-top: 0.75rem;"
    )


# @rt("/quote-control/{quote_id}/invoice/{invoice_id}/detail")
def get(session, quote_id: str, invoice_id: str):
    """
    HTMX endpoint: returns the split-screen detail view for a specific invoice.
    Left (40%): items table with product_name, quantity, purchase_price_original
    Right (60%): iframe with the scan PDF via signed URL, or placeholder if no scan.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return Div("Нет доступа", style="color: #ef4444; padding: 1rem;")

    supabase = get_supabase()

    # Fetch invoice items
    try:
        items_resp = supabase.table("quote_items") \
            .select("id, product_name, quantity, purchase_price_original, purchase_currency") \
            .eq("quote_id", quote_id) \
            .eq("invoice_id", invoice_id) \
            .execute()
        items = items_resp.data or []
    except Exception:
        items = []

    # Fetch scan document for this invoice
    signed_url = None
    try:
        docs_resp = supabase.table("documents") \
            .select("id, storage_path, original_filename, mime_type") \
            .eq("entity_type", "supplier_invoice") \
            .eq("entity_id", invoice_id) \
            .limit(1) \
            .execute()
        document = (docs_resp.data or [None])[0] if docs_resp.data else None
    except Exception:
        document = None

    if document:
        signed_url = get_download_url(document["id"])

    # Build items table (left side, 40%)
    item_rows = []
    for item in items:
        price = float(item.get("purchase_price_original") or 0)
        qty = float(item.get("quantity") or 0)
        currency = item.get("purchase_currency", "USD")
        item_rows.append(
            Tr(
                Td(item.get("product_name", "—"), style="padding: 0.5rem; border-bottom: 1px solid #e2e8f0;"),
                Td(f"{qty:g}", style="padding: 0.5rem; text-align: right; border-bottom: 1px solid #e2e8f0;"),
                Td(f"{price:,.2f} {currency}", style="padding: 0.5rem; text-align: right; border-bottom: 1px solid #e2e8f0;"),
            )
        )

    if not item_rows:
        item_rows.append(
            Tr(Td("Нет позиций", colspan="3", style="text-align: center; color: #64748b; padding: 1rem;"))
        )

    items_table = Table(
        Thead(
            Tr(
                Th("Товар", style="text-align: left; padding: 0.5rem; border-bottom: 2px solid #e2e8f0;"),
                Th("Кол-во", style="text-align: right; padding: 0.5rem; border-bottom: 2px solid #e2e8f0;"),
                Th("Цена закупки", style="text-align: right; padding: 0.5rem; border-bottom: 2px solid #e2e8f0;"),
            )
        ),
        Tbody(*item_rows),
        style="width: 100%; border-collapse: collapse; font-size: 0.8125rem;"
    )

    left_panel = Div(
        H4("Позиции инвойса", style="margin: 0 0 0.75rem 0; font-size: 0.875rem; color: #374151;"),
        items_table,
        style="width: 40%; padding-right: 1rem; overflow-y: auto; max-height: 500px;"
    )

    # Build scan viewer (right side, 60%)
    if signed_url:
        right_panel = Div(
            Iframe(
                src=signed_url,
                style="width: 100%; height: 500px; border: 1px solid #e2e8f0; border-radius: 4px;",
            ),
            style="width: 60%;"
        )
    else:
        right_panel = Div(
            Div(
                icon("file-x", size=48, color="#cbd5e1") if 'icon' in dir() else "",
                P("Скан не загружен", style="color: #94a3b8; font-size: 1rem; margin-top: 0.75rem;"),
                style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 300px; background: #f9fafb; border: 2px dashed #e2e8f0; border-radius: 8px;"
            ),
            style="width: 60%;"
        )

    return Div(
        Div(
            left_panel,
            right_panel,
            style="display: flex; gap: 1rem; margin-top: 0.75rem; padding: 1rem; background: #fafbfc; border-radius: 8px; border: 1px solid #e2e8f0;"
        ),
    )


# ============================================================================
# QUOTE CONTROL - CUSTOM COLUMN SELECTOR
# ============================================================================

# @rt("/quote-control/{quote_id}/columns")
def get(session, quote_id: str):
    """Custom column selector page for quote control calculations."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get current user settings
    current_columns = CALC_PRESET_BASIC
    try:
        result = supabase.table("user_settings") \
            .select("setting_value") \
            .eq("user_id", user_id) \
            .eq("setting_key", "quote_control_columns") \
            .execute()
        if result.data:
            current_columns = (result.data[0].get("setting_value") or {}).get("columns", CALC_PRESET_BASIC)
    except Exception:
        pass

    # Group columns by category
    column_groups = {}
    for col_code, col_info in CALC_COLUMNS.items():
        group = col_info.get("group", "Прочее")
        if group not in column_groups:
            column_groups[group] = []
        column_groups[group].append((col_code, col_info))

    # Build checkboxes grouped by category
    checkbox_groups = []
    for group_name, cols in column_groups.items():
        checkboxes = [
            Label(
                Input(
                    type="checkbox",
                    name="columns",
                    value=col_code,
                    checked=col_code in current_columns,
                    style="margin-right: 0.5rem;"
                ),
                col_info["name"],
                Span(f" ({col_code})", style="color: #666; font-size: 0.75rem;"),
                style="display: flex; align-items: center; margin-bottom: 0.5rem;"
            )
            for col_code, col_info in cols
        ]
        checkbox_groups.append(
            Div(
                H4(group_name, style="margin-bottom: 0.5rem; color: #374151;"),
                *checkboxes,
                style="padding: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 1rem;"
            )
        )

    return page_layout(
        "Настройка колонок расчёта",

        H1(icon("settings", size=28), " Настройка колонок", cls="page-header"),
        P("Выберите колонки для отображения в таблице расчётов", style="color: #666; margin-bottom: 1rem;"),

        # Quick preset buttons
        Div(
            btn_link("Базовый набор", href=f"/quote-control/{quote_id}/columns/preset/basic", variant="secondary", size="sm"),
            btn_link("Полный набор", href=f"/quote-control/{quote_id}/columns/preset/full", variant="secondary", size="sm"),
            style="margin-bottom: 1rem; display: flex; gap: 0.5rem;"
        ),

        Form(
            *checkbox_groups,

            Div(
                btn("Сохранить настройки", variant="primary", icon_name="check", type="submit"),
                btn_link("Отмена", href=f"/quote-control/{quote_id}", variant="ghost"),
                style="margin-top: 1rem; display: flex; gap: 0.5rem;"
            ),
            action=f"/quote-control/{quote_id}/columns",
            method="post"
        ),

        session=session
    )


# @rt("/quote-control/{quote_id}/columns")
def post(session, quote_id: str, columns: list = None):
    """Save custom column selection."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]

    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Handle single column (not list) case from form submission
    if columns is None:
        columns = []
    elif isinstance(columns, str):
        columns = [columns]

    # Validate columns
    valid_columns = [c for c in columns if c in CALC_COLUMNS]
    if not valid_columns:
        valid_columns = CALC_PRESET_BASIC

    # Save to user_settings using upsert
    try:
        # First try to update
        update_result = supabase.table("user_settings") \
            .update({
                "setting_value": {"columns": valid_columns, "preset": "custom"},
                "updated_at": datetime.now().isoformat()
            }) \
            .eq("user_id", user_id) \
            .eq("setting_key", "quote_control_columns") \
            .execute()

        # If no rows updated, insert new
        if not update_result.data:
            supabase.table("user_settings").insert({
                "user_id": user_id,
                "setting_key": "quote_control_columns",
                "setting_value": {"columns": valid_columns, "preset": "custom"}
            }).execute()
    except Exception as e:
        print(f"Error saving user settings: {e}")

    return RedirectResponse(f"/quote-control/{quote_id}?preset=custom#calc-table", status_code=303)


# @rt("/quote-control/{quote_id}/columns/preset/{preset_name}")
def get(session, quote_id: str, preset_name: str):
    """Quick preset selection - sets preset and redirects."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]

    if not user_has_any_role(session, ["quote_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    if preset_name not in ("basic", "full"):
        preset_name = "basic"

    # Save preset to user settings
    columns = CALC_PRESET_FULL if preset_name == "full" else CALC_PRESET_BASIC
    try:
        update_result = supabase.table("user_settings") \
            .update({
                "setting_value": {"columns": columns, "preset": preset_name},
                "updated_at": datetime.now().isoformat()
            }) \
            .eq("user_id", user_id) \
            .eq("setting_key", "quote_control_columns") \
            .execute()

        if not update_result.data:
            supabase.table("user_settings").insert({
                "user_id": user_id,
                "setting_key": "quote_control_columns",
                "setting_value": {"columns": columns, "preset": preset_name}
            }).execute()
    except Exception as e:
        print(f"Error saving user settings: {e}")

    return RedirectResponse(f"/quote-control/{quote_id}?preset={preset_name}#calc-table", status_code=303)


# ============================================================================
# TOP MANAGER APPROVALS WORKSPACE — [archived to legacy-fasthtml/approvals_changelog_telegram.py in Phase 6C-2B-6]
# Route moved: /approvals GET. Superseded by Next.js /quotes?status=pending_approval + dashboard widget.
# ============================================================================


# ============================================================================
# QUOTE CONTROL - RETURN FOR REVISION FORM (Feature #49)
# ============================================================================

# @rt("/quote-control/{quote_id}/return")
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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
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

    customer_name = (quote.get("customers") or {}).get("name", "—")
    idn_quote = quote.get("idn_quote", "")

    # Department options for return
    department_options = [
        ("sales", "💼 Менеджер по продажам", "Вернуть для исправления данных о клиенте, наценке, условиях"),
        ("procurement", "📦 Закупки", "Вернуть для исправления цен, поставщиков, сроков производства"),
        ("logistics", "🚚 Логистика", "Вернуть для исправления расчёта доставки, маршрутов"),
        ("customs", "📋 Таможня", "Вернуть для исправления таможенных расчётов, HS-кодов"),
    ]

    return page_layout(f"Возврат на доработку - {idn_quote}",
        # Gradient header card
        Div(
            Div(
                A(
                    icon("arrow-left", size=16, color="#64748b"),
                    Span("Вернуться к проверке", style="margin-left: 6px;"),
                    href=f"/quote-control/{quote_id}",
                    style="display: inline-flex; align-items: center; color: #64748b; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("undo-2", size=24, color="#f59e0b"),
                    Span(f"Возврат КП {idn_quote} на доработку", style="font-size: 22px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    style="display: flex; align-items: center;"
                ),
                Div(
                    Span(f"Клиент: {customer_name}", style="color: #64748b; font-size: 14px;"),
                    style="margin-top: 4px;"
                ),
            ),
            style="background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border: 1px solid #fde68a; border-radius: 12px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Form
        Form(
            # Department selection card
            Div(
                Div(
                    icon("users", size=16, color="#64748b"),
                    Span("КОМУ ВЕРНУТЬ?", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;"
                ),
                P("Выберите отдел, который должен внести исправления:",
                  style="color: #64748b; font-size: 13px; margin-bottom: 16px;"),
                *[
                    Div(
                        Label(
                            Input(
                                type="radio",
                                name="department",
                                value=dept_code,
                                required=True,
                                checked=(dept_code == "sales"),
                                style="margin-right: 10px; accent-color: #f59e0b;"
                            ),
                            Span(dept_label, style="font-weight: 500; color: #1e293b;"),
                            Br(),
                            Span(dept_desc, style="color: #64748b; font-size: 13px; margin-left: 26px; display: block; margin-top: 2px;"),
                            style="cursor: pointer; display: block;"
                        ),
                        style="padding: 14px 16px; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 8px; background: #f8fafc;"
                    )
                    for dept_code, dept_label, dept_desc in department_options
                ],
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Comment section card
            Div(
                Div(
                    icon("message-square", size=16, color="#64748b"),
                    Span("ПРИЧИНА ВОЗВРАТА", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;"
                ),
                P("Укажите, что необходимо исправить в КП:",
                  style="color: #64748b; font-size: 13px; margin-bottom: 12px;"),
                Textarea(
                    name="comment",
                    id="comment",
                    placeholder="Опишите, какие именно данные требуют исправления:\n- Неверная наценка\n- Ошибки в логистике\n- Некорректные условия оплаты\n- и т.д.",
                    required=True,
                    style="width: 100%; min-height: 150px; padding: 12px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-family: inherit; resize: vertical; background: #f8fafc; font-size: 14px; color: #1e293b;"
                ),
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Info banner
            Div(
                icon("alert-triangle", size=18, color="#92400e"),
                Span("После исправлений выбранный отдел вернёт КП обратно на проверку.", style="margin-left: 10px;"),
                style="display: flex; align-items: center; background: #fef3c7; color: #92400e; padding: 14px 16px; border-radius: 10px; margin-bottom: 24px; font-size: 14px;"
            ),

            # Action buttons
            Div(
                btn("Вернуть на доработку", variant="secondary", icon_name="undo-2", type="submit"),
                btn_link("Отмена", href=f"/quote-control/{quote_id}", variant="ghost"),
                style="display: flex; align-items: center; gap: 12px;"
            ),

            action=f"/quote-control/{quote_id}/return",
            method="post"
        ),

        session=session
    )


# @rt("/quote-control/{quote_id}/return")
def post(session, quote_id: str, comment: str = "", department: str = "sales"):
    """
    Handle the return for revision form submission.
    Transitions the quote from PENDING_QUOTE_CONTROL to the selected department's status.

    Feature #49: Форма возврата на доработку - POST handler
    Feature: Multi-department return - can return to sales/procurement/logistics/customs
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

    # Map department to target status
    department_status_map = {
        "sales": WorkflowStatus.PENDING_SALES_REVIEW,
        "procurement": WorkflowStatus.PENDING_PROCUREMENT,
        "logistics": WorkflowStatus.PENDING_LOGISTICS,
        "customs": WorkflowStatus.PENDING_CUSTOMS,
    }

    department_names = {
        "sales": "менеджеру по продажам",
        "procurement": "в отдел закупок",
        "logistics": "в отдел логистики",
        "customs": "в таможенный отдел",
    }

    # Validate department
    if department not in department_status_map:
        return page_layout("Ошибка",
            H1("Ошибка возврата"),
            P("Выбран некорректный отдел для возврата."),
            A("← Вернуться к форме", href=f"/quote-control/{quote_id}/return"),
            session=session
        )

    target_status = department_status_map[department]
    department_name = department_names[department]

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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
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
        to_status=target_status,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=comment.strip()
    )

    if result.success:
        # Save revision tracking info to quote
        from datetime import datetime, timezone
        try:
            supabase.table("quotes").update({
                "revision_department": department,
                "revision_comment": comment.strip(),
                "revision_returned_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", quote_id).execute()
        except Exception as e:
            print(f"Warning: Failed to save revision info for quote {quote_id}: {e}")

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
            H1(icon("check", size=28), " КП возвращено на доработку", cls="page-header"),
            P(f"КП было успешно возвращено {department_name}."),
            P(f"Комментарий: {comment.strip()}", style="color: #666; font-style: italic;"),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
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

# @rt("/quote-control/{quote_id}/request-approval")
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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
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
    prepayment = float(calc_vars.get("advance_from_client", 100) or 100)
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

    customer_name = (quote.get("customers") or {}).get("name", "—")
    idn_quote = quote.get("idn_quote", "")

    # Pre-fill the reason with detected triggers
    default_reason = ""
    if approval_reasons:
        default_reason = "Требуется согласование по следующим причинам:\n" + "\n".join(f"• {r}" for r in approval_reasons)

    return page_layout(f"Запрос согласования - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(icon("clock", size=28), f" Запрос согласования КП {idn_quote}", cls="page-header"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Info banner
        Div(
            icon("info", size=16), " КП будет отправлено на согласование топ-менеджеру. После одобрения вы сможете отправить его клиенту.",
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
                btn("Отправить на согласование", variant="primary", icon_name="clock", type="submit"),
                btn_link("Отмена", href=f"/quote-control/{quote_id}", variant="ghost"),
                style="display: flex; align-items: center; gap: 1rem;"
            ),

            action=f"/quote-control/{quote_id}/request-approval",
            method="post",
            cls="card"
        ),

        session=session
    )


# @rt("/quote-control/{quote_id}/request-approval")
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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    idn_quote = quote.get("idn_quote", "")
    customer_name = (quote.get("customers") or {}).get("name", "")

    # Feature: Justification workflow (Variant B)
    # Instead of sending directly to pending_approval, we:
    # 1. Save the controller's approval_reason
    # 2. Set needs_justification=true
    # 3. Transition to pending_sales_review so sales manager can provide justification
    # 4. After sales provides justification, THEN it goes to pending_approval

    try:
        # Transition quote to pending_sales_review for justification
        result = transition_quote_status(
            quote_id=quote_id,
            to_status=WorkflowStatus.PENDING_SALES_REVIEW,
            actor_id=user_id,
            actor_roles=user_roles,
            comment=f"[Запрос согласования] {comment.strip()}"
        )

        if not result.success:
            return page_layout("Ошибка",
                H1("Ошибка отправки"),
                P(f"Не удалось отправить КП на согласование: {result.error_message}"),
                A("← Вернуться к форме", href=f"/quote-control/{quote_id}/request-approval"),
                session=session
            )

        # Save approval_reason, needs_justification flag, and quote controller tracking
        from datetime import timezone
        supabase.table("quotes").update({
            "approval_reason": comment.strip(),
            "needs_justification": True,
            "approval_justification": None,  # Clear any previous justification
            "quote_controller_id": user_id,
            "quote_control_completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", quote_id).eq("organization_id", org_id).execute()

        return page_layout("Успешно",
            H1(icon("check", size=28), " Отправлено менеджеру продаж", cls="page-header"),
            P(f"КП {idn_quote} отправлено менеджеру продаж для обоснования."),
            P(f"Причина согласования: {comment.strip()}", style="color: #666; font-style: italic;"),
            P("После того как менеджер продаж предоставит обоснование, КП будет отправлено на согласование топ-менеджеру.", style="color: #666;"),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    except Exception as e:
        return page_layout("Ошибка",
            H1("Ошибка отправки"),
            P(f"Произошла ошибка: {str(e)}"),
            A("← Вернуться к форме", href=f"/quote-control/{quote_id}/request-approval"),
            session=session
        )


# ============================================================================
# QUOTE CONTROL - APPROVE QUOTE (Feature #51)
# ============================================================================

# @rt("/quote-control/{quote_id}/approve")
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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Quote Not Found",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is in correct status (allow both pending_quote_control and pending_approval)
    APPROVABLE_STATUSES = {"pending_quote_control", "pending_approval"}
    if workflow_status not in APPROVABLE_STATUSES:
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
    prepayment = float(calc_vars.get("advance_from_client", 100) or 100)
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
    # Only check at pending_quote_control — pending_approval already passed this gate
    if approval_reasons and workflow_status == "pending_quote_control":
        return page_layout("Требуется согласование",
            H1(icon("alert-triangle", size=28), " Требуется согласование топ-менеджера", cls="page-header"),
            P("Это КП не может быть одобрено напрямую, так как имеются следующие причины для согласования:"),
            Ul(*[Li(reason) for reason in approval_reasons]),
            A(icon("clock", size=16), " Отправить на согласование", href=f"/quote-control/{quote_id}/request-approval", role="button"),
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}",
              style="margin-left: 1rem; color: #6b7280; text-decoration: none;"),
            session=session
        )

    customer_name = (quote.get("customers") or {}).get("name", "—")
    idn_quote = quote.get("idn_quote", "")
    total_amount = float(quote.get("total_amount", 0) or 0)
    quote_currency = quote.get("currency", "USD")

    return page_layout(f"Одобрение КП - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к проверке", href=f"/quote-control/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(icon("check", size=28), f" Одобрение КП {idn_quote}", cls="page-header"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Success banner
        Div(
            "КП прошло проверку и может быть одобрено",
            style="background: #dcfce7; color: #166534; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"
        ),

        # Quote summary card
        Div(
            H3("Сводка по КП"),
            Div(
                Div(Strong("Сумма: "), format_money(total_amount, quote_currency)),
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
                btn("Одобрить КП", variant="success", icon_name="check", type="submit"),
                btn_link("Отмена", href=f"/quote-control/{quote_id}", variant="ghost"),
                style="display: flex; align-items: center; gap: 1rem;"
            ),

            action=f"/quote-control/{quote_id}/approve",
            method="post",
            cls="card"
        ),

        session=session
    )


# @rt("/quote-control/{quote_id}/approve")
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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    current_status = quote.get("workflow_status", "draft")
    idn_quote = quote.get("idn_quote", "")

    # Check if quote is in correct status (allow both pending_quote_control and pending_approval)
    if current_status not in {"pending_quote_control", "pending_approval"}:
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
        # Record quote controller tracking data
        try:
            from datetime import timezone
            supabase.table("quotes").update({
                "quote_controller_id": user_id,
                "quote_control_completed_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", quote_id).eq("organization_id", org_id).execute()
        except Exception as e:
            print(f"Warning: Could not update quote control tracking: {e}")

        # Success - redirect to quote control list
        return page_layout("Успешно",
            H1(icon("check-circle", size=28), " КП одобрено", cls="page-header"),
            P(f"КП {idn_quote} было успешно одобрено."),
            P("Теперь менеджер по продажам может отправить его клиенту.", style="color: #666;"),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
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
# TELEGRAM BOT — service imports used by non-webhook handlers
# ============================================================================
# The /api/telegram/webhook endpoint was extracted to api/integrations.py in
# Phase 6B-8. FastHTML /telegram/* routes were archived in Phase 6C-2B-6
# (see legacy-fasthtml/approvals_changelog_telegram.py). Only
# notify_creator_of_return remains — called by /quote-control/{quote_id}/return-to-control.

from services.telegram_service import notify_creator_of_return


# ============================================================================
# SPEC CONTROL WORKSPACE (Features #67-72)
# ============================================================================

# @rt("/spec-control")
def get(session, status_filter: str = None):
    """
    Redirect to unified dashboard spec-control tab.
    Old URL preserved for backwards compatibility.
    """
    url = "/dashboard?tab=spec-control"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


# ============================================================================
# SPECIFICATION DATA ENTRY (Feature #69)
# ============================================================================

# @rt("/spec-control/create/{quote_id}")
def get(session, quote_id: str):
    """
    Create a new specification from a quote.

    Feature #69: Specification data entry form (create new)
    Feature UI-023: Enhanced v3.0 integration with seller company, customer contracts, signatory
    - Shows quote summary
    - Pre-fills some fields from quote data
    - v3.0: Auto-fetches seller company from quote's seller_company_id
    - v3.0: Customer contract dropdown for specification numbering
    - v3.0: Shows signatory from customer_contacts
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

    # Fetch quote with customer info (some columns may not exist in DB)
    quote_result = supabase.table("quotes") \
        .select("*, customers(id, name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
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
    customer_id = customer.get("id")
    customer_name = customer.get("name", "Unknown")
    customer_company = customer.get("company_name") or customer_name

    # v3.0: Get seller company from quote
    seller_company = quote.get("seller_companies", {}) or {}
    seller_company_name = seller_company.get("name", "")
    seller_company_id = quote.get("seller_company_id")

    # Check if specification already exists for this quote
    existing_spec = supabase.table("specifications") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .is_("deleted_at", None) \
        .execute()

    if existing_spec.data:
        # Redirect to edit existing specification
        return RedirectResponse(f"/spec-control/{existing_spec.data[0]['id']}", status_code=303)

    # Get quote versions for version selection (use * to avoid column mismatch)
    versions_result = supabase.table("quote_versions") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at", desc=True) \
        .execute()

    versions = versions_result.data or []

    # Get quote calculation variables for pre-filling some fields
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_vars = vars_result.data[0].get("variables", {}) if vars_result.data else {}

    # v3.0: Get customer contracts for dropdown
    customer_contracts = []
    if customer_id:
        contracts_result = supabase.table("customer_contracts") \
            .select("id, contract_number, contract_date, next_specification_number, status") \
            .eq("customer_id", customer_id) \
            .eq("status", "active") \
            .order("contract_date", desc=True) \
            .execute()
        customer_contracts = contracts_result.data or []

    # v3.0: Get customer signatory from customer_contacts
    signatory_info = None
    if customer_id:
        signatory_result = supabase.table("customer_contacts") \
            .select("name, position") \
            .eq("customer_id", customer_id) \
            .eq("is_signatory", True) \
            .limit(1) \
            .execute()
        if signatory_result.data:
            signatory_info = signatory_result.data[0]

    # Pre-fill values from quote
    prefill = {
        "proposal_idn": quote.get("idn_quote", ""),
        "specification_currency": quote.get("currency", "USD"),
        "client_legal_entity": customer_company,
        "delivery_city_russia": calc_vars.get("delivery_city", ""),
        "cargo_pickup_country": calc_vars.get("supplier_country", ""),
        # v3.0: Pre-fill our legal entity from seller company
        "our_legal_entity": seller_company_name,
    }

    # Form fields grouped by category
    return page_layout("Создание спецификации",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Назад", href="/dashboard?tab=spec-control",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    icon("file-plus", size=24, color="#6366f1"),
                    H1("Создание спецификации", style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    style="display: flex; align-items: center; gap: 12px;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Quote summary card
        Div(
            Div(
                Span("ИНФОРМАЦИЯ О КП", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            Div(
                Div(
                    Span("КП", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(f"{quote.get('idn_quote', '-')}", style="font-weight: 600; color: #1e293b; font-size: 15px;"),
                    style="flex: 1;"
                ),
                Div(
                    Span("Клиент", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(customer_name, style="font-weight: 600; color: #1e293b; font-size: 15px;"),
                    style="flex: 1;"
                ),
                Div(
                    Span("Сумма КП", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                    Div(f"{quote.get('total_amount', 0):,.2f} {quote.get('currency', 'RUB')}", style="font-weight: 600; color: #1e293b; font-size: 15px;"),
                    style="flex: 1;"
                ),
                style="display: flex; gap: 24px;"
            ),
            style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border: 1px solid #bfdbfe; border-radius: 12px; padding: 16px 20px; margin-bottom: 20px;"
        ),

        Form(
            # Hidden fields
            Input(type="hidden", name="quote_id", value=quote_id),
            Input(type="hidden", name="organization_id", value=org_id),

            # Section 1: Identification & Date
            Div(
                Div(
                    icon("file-text", size=16, color="#64748b"),
                    Span("ИДЕНТИФИКАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("№ Спецификации", For="specification_number", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Input(name="specification_number", id="specification_number",
                              placeholder="Авто при выборе договора",
                              style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"),
                        Small("Заполнится автоматически при выборе договора", style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Дата подписания", For="sign_date", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Input(name="sign_date", id="sign_date", type="date",
                              style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Версия КП", For="quote_version_id", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Select(
                            Option("-- Выберите версию --", value=""),
                            *[Option(
                                f"v{v.get('version_number', 0)} - {v.get('total_amount', 0):,.2f} {v.get('currency', '')} ({v.get('created_at', '')[:10]})",
                                value=v.get("id"),
                                selected=v.get("id") == quote.get("current_version_id")
                            ) for v in versions],
                            name="quote_version_id",
                            id="quote_version_id",
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(3, 1fr); gap: 1rem;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Section 2: Delivery Conditions
            Div(
                Div(
                    icon("truck", size=16, color="#64748b"),
                    Span("УСЛОВИЯ ПОСТАВКИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Срок поставки (дней)", For="delivery_days", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Input(name="delivery_days", id="delivery_days", type="number", min="1",
                              placeholder="Авто из расчёта",
                              style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"),
                        Small("Заполнится автоматически из расчёта КП", style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Тип дней", For="delivery_days_type", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Select(
                            Option("рабочих дней", value="рабочих дней", selected=True),
                            Option("календарных дней", value="календарных дней"),
                            name="delivery_days_type",
                            id="delivery_days_type",
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                P(
                    icon("info", size=14, color="#64748b"),
                    " Остальные условия (оплата, адрес, Incoterms) берутся из КП и данных клиента",
                    style="color: #64748b; font-size: 13px; margin-top: 12px; display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: #f1f5f9; border-radius: 6px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Section 3: Contract and Signatory
            Div(
                Div(
                    icon("file-signature", size=16, color="#64748b"),
                    Span("ДОГОВОР И ПОДПИСАНТ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Договор клиента", For="contract_id", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Select(
                            Option("-- Без привязки к договору --", value=""),
                            *[Option(
                                f"{c.get('contract_number', '-')} от {c.get('contract_date', '')[:10] if c.get('contract_date') else '-'} (след.спец: №{c.get('next_specification_number', 1)})",
                                value=c.get("id")
                            ) for c in customer_contracts],
                            name="contract_id",
                            id="contract_id",
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"
                        ),
                        Small(
                            "При выборе договора номер спецификации будет сгенерирован автоматически",
                            style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"
                        ),
                        cls="form-group"
                    ) if customer_contracts else Div(
                        Label("Договор клиента", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        P(icon("alert-triangle", size=14, color="#d97706"), " У клиента нет активных договоров", style="color: #d97706; margin: 0; display: flex; align-items: center; gap: 8px; font-size: 13px;"),
                        A("Создать договор →", href=f"/customer-contracts/new?customer_id={customer_id}" if customer_id else "#",
                          style="font-size: 13px; color: #6366f1; margin-top: 4px; display: inline-block;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Подписант со стороны клиента", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Div(
                            P(
                                Strong(signatory_info.get("name", ""), style="color: #1e293b;"),
                                Br() if signatory_info.get("position") else None,
                                Span(signatory_info.get("position", ""), style="color: #64748b; font-size: 13px;") if signatory_info.get("position") else None,
                                style="margin: 0; padding: 10px 14px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 6px; border-left: 3px solid #22c55e;"
                            ),
                            Small(icon("check", size=12, color="#16a34a"), " Подписант определён из контактов клиента", style="color: #16a34a; display: flex; align-items: center; gap: 4px; margin-top: 6px; font-size: 12px;"),
                        ) if signatory_info else Div(
                            P(icon("alert-triangle", size=14, color="#d97706"), " Подписант не указан в контактах клиента", style="color: #d97706; margin: 0; display: flex; align-items: center; gap: 8px; font-size: 13px;"),
                            A("Указать подписанта →", href=f"/customers/{customer_id}" if customer_id else "#",
                              style="font-size: 13px; color: #6366f1; margin-top: 4px; display: inline-block;"),
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                style="background: linear-gradient(135deg, #fefce8 0%, #fef9c3 100%); border: 1px solid #fde047; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Action buttons
            Div(
                btn("Создать спецификацию", variant="success", icon_name="save", type="submit", name="action", value="create"),
                btn_link("Отмена", href="/dashboard?tab=spec-control", variant="secondary"),
                style="margin-top: 8px; display: flex; gap: 12px;"
            ),

            action=f"/spec-control/create/{quote_id}",
            method="POST"
        ),

        session=session
    )


# @rt("/spec-control/create/{quote_id}")
def post(session, quote_id: str, action: str = "create",
         contract_id: str = "", specification_number: str = "",
         delivery_days: str = "", quote_version_id: str = "",
         proposal_idn: str = "", item_ind_sku: str = "",
         sign_date: str = "", validity_period: str = "",
         specification_currency: str = "", exchange_rate_to_ruble: str = "",
         client_payment_term_after_upd: str = "", client_payment_terms: str = "",
         cargo_pickup_country: str = "", readiness_period: str = "",
         goods_shipment_country: str = "", delivery_city_russia: str = "",
         cargo_type: str = "", logistics_period: str = "",
         delivery_days_type: str = "", our_legal_entity: str = "",
         client_legal_entity: str = "", supplier_payment_country: str = ""):
    """
    Create a new specification from form data.

    Feature #69: Specification data entry form (create POST handler)
    Feature UI-023: v3.0 enhanced with contract_id for auto-numbering
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
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return RedirectResponse("/spec-control", status_code=303)

    # Check if specification already exists
    existing_spec = supabase.table("specifications") \
        .select("id") \
        .eq("quote_id", quote_id) \
        .is_("deleted_at", None) \
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

    # v3.0: Handle contract_id for auto-numbering
    contract_id = contract_id or None
    specification_number = specification_number or None

    # Auto-generate specification number from contract if selected and no manual number provided
    if contract_id and not specification_number:
        try:
            # Get contract info for spec numbering
            contract_result = supabase.table("customer_contracts") \
                .select("contract_number, next_specification_number") \
                .eq("id", contract_id) \
                .execute()

            if contract_result.data:
                contract = contract_result.data[0]
                next_spec_num = contract.get("next_specification_number", 1)
                contract_num = contract.get("contract_number", "")
                # Format: CONTRACT_NUMBER-SPEC_NUMBER (e.g., ДП-001/2025-1)
                specification_number = f"{contract_num}-{next_spec_num}"

                # Increment next_specification_number in contract
                supabase.table("customer_contracts") \
                    .update({"next_specification_number": next_spec_num + 1}) \
                    .eq("id", contract_id) \
                    .execute()
        except Exception as e:
            print(f"Error auto-generating specification number: {e}")

    # Pre-fill delivery_days from calc_variables.delivery_time
    delivery_days_val = safe_int(delivery_days)
    if not delivery_days_val:
        try:
            calc_vars_result = supabase.table("quote_calculation_variables") \
                .select("variables") \
                .eq("quote_id", quote_id) \
                .execute()
            if calc_vars_result.data:
                variables = calc_vars_result.data[0].get("variables", {})
                delivery_days_val = safe_int(variables.get("delivery_time"))
        except Exception as e:
            print(f"Error fetching delivery_time from calc_variables: {e}")

    # Build specification data
    spec_data = {
        "quote_id": quote_id,
        "organization_id": org_id,
        "quote_version_id": quote_version_id or None,
        "specification_number": specification_number,
        "proposal_idn": proposal_idn or None,
        "item_ind_sku": item_ind_sku or None,
        "sign_date": sign_date or None,
        "validity_period": validity_period or None,
        "specification_currency": specification_currency or "USD",
        "exchange_rate_to_ruble": safe_decimal(exchange_rate_to_ruble),
        "client_payment_term_after_upd": safe_int(client_payment_term_after_upd),
        "client_payment_terms": client_payment_terms or None,
        "cargo_pickup_country": cargo_pickup_country or None,
        "readiness_period": readiness_period or None,
        "goods_shipment_country": goods_shipment_country or None,
        "delivery_city_russia": delivery_city_russia or None,
        "cargo_type": cargo_type or None,
        "logistics_period": logistics_period or None,
        "delivery_days": delivery_days_val,  # Pre-filled from calc_variables.delivery_time
        "delivery_days_type": delivery_days_type or "рабочих дней",
        "our_legal_entity": our_legal_entity or None,
        "client_legal_entity": client_legal_entity or None,
        "supplier_payment_country": supplier_payment_country or None,
        "contract_id": contract_id,  # v3.0: Link to customer contract
        "status": "draft",
        "created_by": user_id,
    }

    # Insert specification
    try:
        result = supabase.table("specifications").insert(spec_data).execute()
    except Exception as e:
        print(f"[ERROR] Specification INSERT failed. spec_data keys: {list(spec_data.keys())}")
        print(f"[ERROR] Exception: {e}")
        if sentry_dsn:
            sentry_sdk.capture_exception(e)
        return page_layout("Ошибка",
            H1("Ошибка создания спецификации"),
            P("Произошла ошибка при сохранении спецификации. Обратитесь к администратору."),
            A("← Назад", href=f"/spec-control/create/{quote_id}"),
            session=session
        )

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


# @rt("/spec-control/{spec_id}")
def get(session, spec_id: str):
    """
    View/edit an existing specification.

    Feature #69: Specification data entry form (edit existing)
    Feature UI-023: v3.0 enhanced with seller company, contracts, signatory
    - Shows all 18 specification fields
    - Editable when status is draft or pending_review
    - Shows quote summary and customer info
    - v3.0: Shows seller company from quote
    - v3.0: Shows linked contract info
    - v3.0: Shows signatory from customer_contacts
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
    # Note: contract_id FK not yet applied in production DB (migration 036 pending)
    # Contracts are fetched separately below (lines 9298-9306)
    try:
        spec_result = supabase.table("specifications") \
            .select("*, quotes(id, idn_quote, total_amount, currency, workflow_status, customers(id, name, inn))") \
            .eq("id", spec_id) \
            .eq("organization_id", org_id) \
            .is_("deleted_at", None) \
            .execute()
    except Exception as e:
        # Log detailed error to Sentry
        import traceback
        error_details = {
            "spec_id": spec_id,
            "org_id": org_id,
            "user_id": user_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

        # Log to Sentry if available
        if sentry_dsn:
            sentry_sdk.capture_exception(e)

        # Log to console for debugging
        print(f"[ERROR] Spec-control route failed for spec_id={spec_id}")
        print(f"Error: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")

        return page_layout("Ошибка",
            H1("Ошибка загрузки спецификации"),
            Div(
                P(f"Произошла ошибка при загрузке спецификации ID: {spec_id}"),
                P(f"Ошибка: {str(e)}", style="font-family: monospace; font-size: 0.9rem; background: #f5f5f5; padding: 0.5rem; border-radius: 4px;"),
                P("Ошибка отправлена в систему мониторинга.", style="font-size: 0.875rem; color: #666;"),
                style="background: #fee; border: 1px solid #c33; padding: 1rem; margin-bottom: 1rem; border-radius: 4px;"
            ),
            A("← Назад к спецификациям", href="/spec-control"),
            session=session
        )

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
    customer_id = customer.get("id")
    customer_name = customer.get("name", "Unknown")
    customer_company = customer_name  # Fixed: removed company_name reference
    quote_id = spec.get("quote_id")
    status = spec.get("status", "draft")
    quote_workflow_status = quote.get("workflow_status", "draft")

    # Bug C2: Check if a deal actually exists for this spec (for signed status label)
    has_deal = False
    if status == "signed":
        existing_deal = supabase.table("deals") \
            .select("id, deal_number") \
            .eq("specification_id", spec_id) \
            .is_("deleted_at", None) \
            .execute()
        has_deal = bool(existing_deal and existing_deal.data)

    # TODO: seller_companies relationship not yet implemented in database
    seller_company_name = ""
    seller_company_code = ""

    # v3.0: Get linked contract info (if contract_id exists)
    contract_id = spec.get("contract_id")
    linked_contract = {}
    if contract_id:
        try:
            linked_contract_result = supabase.table("customer_contracts") \
                .select("id, contract_number, contract_date") \
                .eq("id", contract_id) \
                .limit(1) \
                .execute()
            if linked_contract_result.data:
                linked_contract = linked_contract_result.data[0]
        except Exception as e:
            print(f"[WARNING] Could not fetch linked contract {contract_id}: {e}")
            linked_contract = {}

    # Check if editable
    is_editable = status in ["draft", "pending_review"]

    # Get quote versions for version selection (use * to avoid column mismatch)
    versions_result = supabase.table("quote_versions") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at", desc=True) \
        .execute()

    versions = versions_result.data or []

    # v3.0: Get customer contracts for dropdown
    customer_contracts = []
    if customer_id:
        contracts_result = supabase.table("customer_contracts") \
            .select("id, contract_number, contract_date, next_specification_number, status") \
            .eq("customer_id", customer_id) \
            .eq("status", "active") \
            .order("contract_date", desc=True) \
            .execute()
        customer_contracts = contracts_result.data or []

    # v3.0: Get customer signatory from customer_contacts
    signatory_info = None
    if customer_id:
        signatory_result = supabase.table("customer_contacts") \
            .select("name, position") \
            .eq("customer_id", customer_id) \
            .eq("is_signatory", True) \
            .limit(1) \
            .execute()
        if signatory_result.data:
            signatory_info = signatory_result.data[0]

    # Status badge helper with design system colors
    def spec_status_badge(status):
        status_map = {
            "draft": ("Черновик", "#64748b", "#f1f5f9"),
            "pending_review": ("На проверке", "#d97706", "#fef3c7"),
            "approved": ("Утверждена", "#2563eb", "#dbeafe"),
            "signed": ("Подписана", "#16a34a", "#dcfce7"),
        }
        label, color, bg = status_map.get(status, (status, "#64748b", "#f1f5f9"))
        return Span(label, style=f"display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: {color}; background: {bg};")

    # Safe workflow progress bar with error handling
    try:
        progress_bar = workflow_progress_bar(quote_workflow_status)
    except Exception as e:
        print(f"[WARNING] workflow_progress_bar failed for status={quote_workflow_status}: {e}")
        progress_bar = Div()  # Empty div if workflow bar fails

    return page_layout("Редактирование спецификации",
        # Header card with gradient
        Div(
            Div(
                Div(
                    A(icon("arrow-left", size=18), " Назад", href="/dashboard?tab=spec-control",
                      style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;"),
                    style="margin-bottom: 12px;"
                ),
                Div(
                    Div(
                        Div(
                            icon("file-text", size=24, color="#6366f1"),
                            H1(f"Спецификация: {spec.get('specification_number', '-') or 'Без номера'}", style="margin: 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                            style="display: flex; align-items: center; gap: 12px;"
                        ),
                        Div(spec_status_badge(status), style="margin-top: 8px;"),
                    ),
                    Div(
                        Div(
                            Span("КП", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                            Div(quote.get('idn_quote', '-'), style="font-weight: 600; color: #1e293b; font-size: 14px;"),
                        ),
                        Div(
                            Span("Клиент", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                            Div(customer_name, style="font-weight: 600; color: #1e293b; font-size: 14px;"),
                        ),
                        Div(
                            Span("Сумма КП", style="font-size: 11px; color: #64748b; text-transform: uppercase;"),
                            Div(f"{quote.get('total_amount', 0):,.2f} {quote.get('currency', 'RUB')}", style="font-weight: 600; color: #1e293b; font-size: 14px;"),
                        ),
                        style="display: flex; gap: 24px; text-align: left;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: flex-start;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Workflow progress bar (Feature #87)
        progress_bar,

        # Warning banner if not editable
        Div(
            icon("alert-triangle", size=16, color="#d97706"), " Спецификация утверждена/подписана и не может быть отредактирована.",
            style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 1px solid #fde047; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; font-size: 14px; color: #92400e;"
        ) if not is_editable else None,

        # Admin panel for status management (Bug #8: Allow admins to move specs between stages)
        Div(
            Div(
                icon("wrench", size=16, color="#dc2626"),
                Span("АДМИН-ПАНЕЛЬ УПРАВЛЕНИЯ СТАТУСОМ", style="font-size: 11px; font-weight: 600; color: #dc2626; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
            ),
            P("Текущий статус: ", spec_status_badge(status), style="margin-bottom: 12px; font-size: 14px;"),
            P("Изменить статус на:", style="margin-bottom: 8px; font-weight: 600; font-size: 13px; color: #374151;"),
            Div(
                # Simplified workflow: draft -> approved -> signed (no pending_review)
                Form(
                    Input(type="hidden", name="action", value="admin_change_status"),
                    Input(type="hidden", name="new_status", value="draft"),
                    btn("Черновик", variant="secondary", icon_name="file-edit", type="submit", size="sm",
                        disabled=(status == "draft")),
                    action=f"/spec-control/{spec_id}",
                    method="POST",
                    style="display: inline;"
                ),
                Form(
                    Input(type="hidden", name="action", value="admin_change_status"),
                    Input(type="hidden", name="new_status", value="approved"),
                    btn("Утверждена", variant="primary", icon_name="check", type="submit", size="sm",
                        disabled=(status == "approved")),
                    action=f"/spec-control/{spec_id}",
                    method="POST",
                    style="display: inline;"
                ),
                Form(
                    Input(type="hidden", name="action", value="admin_change_status"),
                    Input(type="hidden", name="new_status", value="signed"),
                    btn("Подписана", variant="success", icon_name="pen-tool", type="submit", size="sm",
                        disabled=(status == "signed")),
                    action=f"/spec-control/{spec_id}",
                    method="POST",
                    style="display: inline;"
                ),
                style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px;"
            ),
            P(icon("alert-triangle", size=14, color="#ef4444"), " Внимание: это админ-функция для тестирования и исправления ошибок. Используйте осторожно!",
              style="margin-top: 12px; font-size: 12px; color: #ef4444; display: flex; align-items: center; gap: 6px;"),
            style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); border: 1px solid #fca5a5; border-left: 4px solid #dc2626; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px;"
        ) if user_has_any_role(session, ["admin"]) else None,

        Form(
            # Hidden fields
            Input(type="hidden", name="spec_id", value=spec_id),

            # Section 1: Identification & Date
            Div(
                Div(
                    icon("file-text", size=16, color="#64748b"),
                    Span("ИДЕНТИФИКАЦИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("№ Спецификации", For="specification_number", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Input(name="specification_number", id="specification_number",
                              value=spec.get("specification_number", ""),
                              placeholder="Авто при выборе договора",
                              disabled=not is_editable,
                              style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Дата подписания", For="sign_date", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Input(name="sign_date", id="sign_date", type="date",
                              value=spec.get("sign_date", "") or "",
                              disabled=not is_editable,
                              style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Версия КП", For="quote_version_id", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
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
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(3, 1fr); gap: 1rem;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Section 2: Delivery Conditions
            Div(
                Div(
                    icon("truck", size=16, color="#64748b"),
                    Span("УСЛОВИЯ ПОСТАВКИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Срок поставки (дней)", For="delivery_days", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Input(name="delivery_days", id="delivery_days", type="number", min="1",
                              value=str(spec.get("delivery_days", "")) if spec.get("delivery_days") else "",
                              placeholder="Из расчёта КП",
                              disabled=not is_editable,
                              style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Тип дней", For="delivery_days_type", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Select(
                            Option("рабочих дней", value="рабочих дней",
                                   selected=spec.get("delivery_days_type", "рабочих дней") == "рабочих дней"),
                            Option("календарных дней", value="календарных дней",
                                   selected=spec.get("delivery_days_type") == "календарных дней"),
                            name="delivery_days_type",
                            id="delivery_days_type",
                            disabled=not is_editable,
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                P(
                    icon("info", size=14, color="#64748b"),
                    " Остальные условия (оплата, адрес, Incoterms) берутся из КП и данных клиента",
                    style="color: #64748b; font-size: 13px; margin-top: 12px; display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: #f1f5f9; border-radius: 6px;"
                ),
                style="background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Section 3: Contract and Signatory
            Div(
                Div(
                    icon("file-signature", size=16, color="#64748b"),
                    Span("ДОГОВОР И ПОДПИСАНТ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                    style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Label("Договор клиента", For="contract_id", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        # Show linked contract (read-only display) or dropdown to select
                        Div(
                            P(
                                Strong(f"{linked_contract.get('contract_number', '-')}", style="color: #1e293b;"),
                                f" от {linked_contract.get('contract_date', '')[:10] if linked_contract.get('contract_date') else '-'}",
                                style="margin: 0; padding: 10px 14px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 6px; border-left: 3px solid #3b82f6; font-size: 14px;"
                            ),
                            Small(icon("check", size=12, color="#1d4ed8"), " Спецификация привязана к договору", style="color: #1d4ed8; display: flex; align-items: center; gap: 4px; margin-top: 6px; font-size: 12px;"),
                            Input(type="hidden", name="contract_id", value=contract_id or ""),
                        ) if linked_contract.get("contract_number") else Select(
                            Option("-- Без привязки к договору --", value="", selected=not contract_id),
                            *[Option(
                                f"{c.get('contract_number', '-')} от {c.get('contract_date', '')[:10] if c.get('contract_date') else '-'}",
                                value=c.get("id"),
                                selected=c.get("id") == contract_id
                            ) for c in customer_contracts],
                            name="contract_id",
                            id="contract_id",
                            disabled=not is_editable,
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; font-size: 14px;"
                        ) if customer_contracts else Div(
                            P(icon("alert-triangle", size=14, color="#d97706"), " У клиента нет активных договоров", style="color: #d97706; margin: 0; display: flex; align-items: center; gap: 8px; font-size: 13px;"),
                            A("Создать договор →", href=f"/customer-contracts/new?customer_id={customer_id}" if customer_id else "#",
                              style="font-size: 13px; color: #6366f1; margin-top: 4px; display: inline-block;"),
                        ),
                        cls="form-group"
                    ),
                    Div(
                        Label("Подписант со стороны клиента", style="font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block;"),
                        Div(
                            P(
                                Strong(signatory_info.get("name", ""), style="color: #1e293b;"),
                                Br() if signatory_info.get("position") else None,
                                Span(signatory_info.get("position", ""), style="color: #64748b; font-size: 13px;") if signatory_info.get("position") else None,
                                style="margin: 0; padding: 10px 14px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 6px; border-left: 3px solid #22c55e;"
                            ),
                            Small(icon("check", size=12, color="#16a34a"), " Подписант определён из контактов клиента", style="color: #16a34a; display: flex; align-items: center; gap: 4px; margin-top: 6px; font-size: 12px;"),
                        ) if signatory_info else Div(
                            P(icon("alert-triangle", size=14, color="#d97706"), " Подписант не указан в контактах клиента", style="color: #d97706; margin: 0; display: flex; align-items: center; gap: 8px; font-size: 13px;"),
                            A("Указать подписанта →", href=f"/customers/{customer_id}" if customer_id else "#",
                              style="font-size: 13px; color: #6366f1; margin-top: 4px; display: inline-block;"),
                        ),
                        cls="form-group"
                    ),
                    cls="grid",
                    style="grid-template-columns: repeat(2, 1fr); gap: 1rem;"
                ),
                style="background: linear-gradient(135deg, #fefce8 0%, #fef9c3 100%); border: 1px solid #fde047; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            ),

            # Action buttons (simplified workflow: draft -> approved -> signed)
            Div(
                btn("Сохранить", variant="primary", icon_name="save", type="submit", name="action", value="save",
                    disabled=not is_editable) if is_editable else None,
                btn("Утвердить", variant="success", icon_name="check", type="submit", name="action", value="approve",
                    disabled=not is_editable) if is_editable and status == "draft" else None,
                # Feature #70: PDF Preview button (opens in new tab)
                btn_link("Предпросмотр PDF", href=f"/spec-control/{spec_id}/preview-pdf", variant="ghost", icon_name="file-text", target="_blank"),
                # Contract-style specification export (direct download - no modal)
                btn_link("Экспорт PDF", href=f"/spec-control/{spec_id}/export-pdf", variant="primary", icon_name="download"),
                btn_link("DOCX (Beta)", href=f"/spec-control/{spec_id}/export-docx", variant="secondary", icon_name="file-text"),
                btn_link("Назад", href="/dashboard?tab=spec-control", variant="ghost", icon_name="arrow-left"),
                style="margin-top: 8px; display: flex; gap: 12px; flex-wrap: wrap;"
            ),

            action=f"/spec-control/{spec_id}",
            method="POST"
        ),

        # Feature #71: Section 7 - Signed Scan Upload (OUTSIDE main form - HTML doesn't support nested forms)
        # Visible when status is approved or signed
        Div(
            Div(
                icon("pen-tool", size=16, color="#64748b"),
                Span("ПОДПИСАННЫЙ СКАН", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
            ),
            # Show current scan if exists
            Div(
                P(
                    icon("check-circle", size=14, color="#16a34a"), " Скан загружен: ",
                    # Strip query params (token) from display for security - only show filename
                    A(spec.get("signed_scan_url", "").split("/")[-1].split("?")[0] if spec.get("signed_scan_url") else "",
                      href=spec.get("signed_scan_url", "#"),
                      target="_blank",
                      style="color: #6366f1; font-weight: 500;"),
                    style="margin-bottom: 0; display: flex; align-items: center; gap: 6px; font-size: 14px;"
                ),
                style="background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); border: 1px solid #86efac; border-left: 4px solid #22c55e; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;"
            ) if spec.get("signed_scan_url") else None,
            # Upload form (standalone - not nested)
            P(
                "Загрузите скан подписанной спецификации (PDF, JPG, PNG, до 10 МБ).",
                style="margin-bottom: 12px; color: #64748b; font-size: 13px;"
            ) if not spec.get("signed_scan_url") else P(
                "Вы можете загрузить новый скан для замены текущего.",
                style="margin-bottom: 12px; color: #64748b; font-size: 13px;"
            ),
            Form(
                Input(type="file", name="signed_scan", id="signed_scan",
                      accept=".pdf,.jpg,.jpeg,.png",
                      style="margin-bottom: 12px; font-size: 14px;"),
                btn("Загрузить скан", variant="primary", icon_name="upload", type="submit"),
                action=f"/spec-control/{spec_id}/upload-signed",
                method="POST",
                enctype="multipart/form-data"
            ),
            # Feature #72: Confirm Signature button (visible when approved + has signed scan)
            Div(
                Div(style="height: 1px; background: #e2e8f0; margin: 16px 0;"),
                P(
                    icon("file-text", size=14, color="#16a34a"), " Скан загружен. Подтвердите подпись для создания сделки.",
                    style="margin-bottom: 12px; color: #16a34a; font-weight: 500; font-size: 14px; display: flex; align-items: center; gap: 8px;"
                ),
                Form(
                    btn("Подтвердить подпись и создать сделку", variant="success", icon_name="check", type="submit", full_width=True),
                    action=f"/spec-control/{spec_id}/confirm-signature",
                    method="POST"
                ),
                style="margin-top: 16px;"
            ) if status == "approved" and spec.get("signed_scan_url") else None,
            # Info for already signed specs - show deal status based on actual deal existence
            Div(
                Div(style="height: 1px; background: #e2e8f0; margin: 16px 0;"),
                P(
                    icon("check-circle", size=14, color="#16a34a"), " Спецификация подписана. Сделка создана.",
                    style="margin-bottom: 0; color: #16a34a; font-weight: 500; font-size: 14px; display: flex; align-items: center; gap: 8px;"
                ) if has_deal else P(
                    icon("alert-circle", size=14, color="#d97706"), " Спецификация подписана. Сделка не создана.",
                    style="margin-bottom: 0; color: #d97706; font-weight: 500; font-size: 14px; display: flex; align-items: center; gap: 8px;"
                ),
                style="margin-top: 16px;"
            ) if status == "signed" else None,
            style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ) if status in ["approved", "signed"] else None,

        # Transition history (Feature #88) - uses quote_id from the spec
        workflow_transition_history(quote_id) if quote_id else None,

        session=session
    )




# @rt("/spec-control/{spec_id}")
def post(session, spec_id: str, action: str = "save", new_status: str = "",
         contract_id: str = "", specification_number: str = "",
         delivery_days: str = "", quote_version_id: str = "",
         proposal_idn: str = "", item_ind_sku: str = "",
         sign_date: str = "", validity_period: str = "",
         specification_currency: str = "", exchange_rate_to_ruble: str = "",
         client_payment_term_after_upd: str = "", client_payment_terms: str = "",
         cargo_pickup_country: str = "", readiness_period: str = "",
         goods_shipment_country: str = "", delivery_city_russia: str = "",
         cargo_type: str = "", logistics_period: str = "",
         delivery_days_type: str = "", our_legal_entity: str = "",
         client_legal_entity: str = "", supplier_payment_country: str = ""):
    """
    Save specification changes or change status.

    Feature #69: Specification data entry form (save/update POST handler)
    Bug #8: Admin status override for testing and error correction

    Actions:
    - save: Save current data
    - approve: Save and change status to approved (direct from draft)
    - admin_change_status: Admin-only action to directly change status to any value
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
        .select("id, status, quote_id, contract_id, specification_currency, sign_date") \
        .eq("id", spec_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not spec_result.data:
        return RedirectResponse("/spec-control", status_code=303)

    spec = spec_result.data[0]
    current_status = spec.get("status", "draft")

    # Bug #8: Admin override - allow admins to change status directly
    if action == "admin_change_status":
        if not user_has_any_role(session, ["admin"]):
            return RedirectResponse("/unauthorized", status_code=303)

        new_status = new_status or current_status
        valid_statuses = ["draft", "pending_review", "approved", "signed"]

        if new_status not in valid_statuses:
            return RedirectResponse(f"/spec-control/{spec_id}", status_code=303)

        # Validate IDN-SKU before signing (Feature P2.2)
        if new_status == "signed":
            quote_id_for_validation = spec.get("quote_id")
            is_valid, idn_sku_error = validate_quote_items_have_idn_sku(quote_id_for_validation)
            if not is_valid:
                return page_layout("Ошибка валидации IDN-SKU",
                    H1("Не все позиции имеют IDN-SKU"),
                    Div(
                        idn_sku_error,
                        cls="card", style="background: #fee2e2; border-left: 4px solid #dc2626; white-space: pre-line;"
                    ),
                    A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                    session=session
                )

        # Update the status
        supabase.table("specifications") \
            .update({"status": new_status}) \
            .eq("id", spec_id) \
            .execute()

        # Bug C2: When admin sets status to "signed", also create a deal record
        if new_status == "signed":
            # Idempotency: check if a deal already exists for this spec
            existing_deal = supabase.table("deals") \
                .select("id, deal_number") \
                .eq("specification_id", spec_id) \
                .is_("deleted_at", None) \
                .execute()

            if not existing_deal.data:
                # Fetch quote data for total_amount and customer info
                quote_id_val = spec.get("quote_id")
                quote_result = supabase.table("quotes") \
                    .select("id, total_amount, customers(id, name)") \
                    .eq("id", quote_id_val) \
                    .is_("deleted_at", None) \
                    .execute()

                total_amount = (quote_result.data[0].get("total_amount") or 0) if quote_result.data else 0

                # Use specification_currency and sign_date from initial spec query
                spec_currency = spec.get("specification_currency") or "RUB"
                spec_sign_date = spec.get("sign_date")

                # Generate deal number
                try:
                    deal_number_result = supabase.rpc("generate_deal_number", {"org_id": org_id}).execute()
                    deal_number = deal_number_result.data if deal_number_result.data else None
                except Exception:
                    deal_number = None

                if not deal_number:
                    from datetime import datetime
                    year = datetime.now().year
                    count_result = supabase.table("deals") \
                        .select("id", count="exact") \
                        .eq("organization_id", org_id) \
                        .is_("deleted_at", None) \
                        .execute()
                    seq_num = (count_result.count or 0) + 1
                    deal_number = f"DEAL-{year}-{seq_num:04d}"

                from datetime import date
                deal_sign_date = spec_sign_date or date.today().isoformat()

                # Insert deal record
                deal_data = {
                    "specification_id": spec_id,
                    "quote_id": quote_id_val,
                    "organization_id": org_id,
                    "deal_number": deal_number,
                    "signed_at": deal_sign_date,
                    "total_amount": float(total_amount) if total_amount else 0.0,
                    "currency": spec_currency,
                    "status": "active",
                    "created_by": user_id,
                }
                deal_result = supabase.table("deals").insert(deal_data).execute()
                new_deal_id = (deal_result.data[0]["id"]) if deal_result.data else None

                # Initialize logistics stages for the new deal
                if new_deal_id:
                    try:
                        from services.logistics_service import initialize_logistics_stages
                        initialize_logistics_stages(new_deal_id, user_id)
                    except Exception as e:
                        print(f"Note: Could not initialize logistics stages (admin sign): {e}")

                # Generate currency invoices for the new deal
                if new_deal_id:
                    try:
                        from services.currency_invoice_service import generate_currency_invoices, save_currency_invoices

                        ci_items, bc_lookup = _fetch_items_with_buyer_companies(supabase, quote_id_val)

                        ci_quote_resp = supabase.table("quotes").select(
                            "idn_quote, seller_companies!seller_company_id(id, name)"
                        ).eq("id", quote_id_val).single().is_("deleted_at", None).execute()
                        ci_quote_data = ci_quote_resp.data or {}
                        sc = (ci_quote_data.get("seller_companies") or {})
                        ci_seller_company = {"id": sc.get("id"), "name": sc.get("name"), "entity_type": "seller_company"}
                        ci_quote_idn = ci_quote_data.get("idn_quote", "")

                        if bc_lookup and ci_seller_company.get("id"):
                            ci_contracts, ci_bank_accounts = _fetch_enrichment_data(supabase, org_id)
                            ci_invoices = generate_currency_invoices(
                                deal_id=str(new_deal_id),
                                quote_idn=ci_quote_idn,
                                items=ci_items,
                                buyer_companies=bc_lookup,
                                seller_company=ci_seller_company,
                                organization_id=org_id,
                                contracts=ci_contracts,
                                bank_accounts=ci_bank_accounts,
                            )
                            if ci_invoices:
                                save_currency_invoices(supabase, ci_invoices)
                                print(f"Currency invoices generated (admin sign): {len(ci_invoices)} for deal {new_deal_id}")
                            else:
                                print(f"No currency invoices generated (admin sign) for deal {new_deal_id}")
                        else:
                            print(f"Currency invoice generation skipped (admin sign): no buyer/seller company for deal {new_deal_id}")
                    except Exception as e:
                        print(f"Warning: currency invoice generation failed (admin sign): {e}")
                        # Non-blocking — deal creation still succeeds

                # Update quote workflow_status to deal_signed
                try:
                    from services import transition_quote_status, WorkflowStatus
                    transition_quote_status(
                        quote_id=quote_id_val,
                        to_status=WorkflowStatus.DEAL_SIGNED,
                        actor_id=user_id,
                        actor_roles=get_user_roles_from_session(session),
                        comment=f"Сделка {deal_number} создана (admin)",
                        supabase=supabase
                    )
                except Exception:
                    pass  # Workflow transition optional

        return RedirectResponse(f"/spec-control/{spec_id}", status_code=303)

    # Check if editable (for regular save/approve actions)
    if current_status not in ["draft"]:
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
    # Simplified workflow: draft -> approved (no pending_review step)
    resolved_status = current_status
    if action == "approve" and current_status == "draft":
        resolved_status = "approved"

    # Extract contract_id and specification_number for auto-numbering
    contract_id = contract_id or None
    specification_number = specification_number or None

    # Auto-number from contract if contract_id changed
    if contract_id and not specification_number:
        if contract_id != spec.get("contract_id"):
            try:
                contract_result = supabase.table("customer_contracts") \
                    .select("contract_number, next_specification_number") \
                    .eq("id", contract_id) \
                    .execute()

                if contract_result.data:
                    contract = contract_result.data[0]
                    next_spec_num = contract.get("next_specification_number", 1)
                    contract_num = contract.get("contract_number", "")
                    specification_number = f"{contract_num}-{next_spec_num}"

                    supabase.table("customer_contracts") \
                        .update({"next_specification_number": next_spec_num + 1}) \
                        .eq("id", contract_id) \
                        .execute()
            except Exception as e:
                print(f"Error auto-generating specification number on update: {e}")

    # Build update data
    update_data = {
        "quote_version_id": quote_version_id or None,
        "specification_number": specification_number,
        "proposal_idn": proposal_idn or None,
        "item_ind_sku": item_ind_sku or None,
        "sign_date": sign_date or None,
        "validity_period": validity_period or None,
        "specification_currency": specification_currency or "USD",
        "exchange_rate_to_ruble": safe_decimal(exchange_rate_to_ruble),
        "client_payment_term_after_upd": safe_int(client_payment_term_after_upd),
        "client_payment_terms": client_payment_terms or None,
        "cargo_pickup_country": cargo_pickup_country or None,
        "readiness_period": readiness_period or None,
        "goods_shipment_country": goods_shipment_country or None,
        "delivery_city_russia": delivery_city_russia or None,
        "cargo_type": cargo_type or None,
        "logistics_period": logistics_period or None,
        "delivery_days": safe_int(delivery_days),
        "delivery_days_type": delivery_days_type or "рабочих дней",
        "our_legal_entity": our_legal_entity or None,
        "client_legal_entity": client_legal_entity or None,
        "supplier_payment_country": supplier_payment_country or None,
        "contract_id": contract_id,
        "status": resolved_status,
    }

    # Update specification
    supabase.table("specifications") \
        .update(update_data) \
        .eq("id", spec_id) \
        .execute()

    # Record spec controller tracking data when approving
    if resolved_status == "approved" and current_status == "draft":
        try:
            from datetime import timezone
            quote_id_for_tracking = spec.get("quote_id")
            if quote_id_for_tracking:
                supabase.table("quotes").update({
                    "spec_controller_id": user_id,
                    "spec_control_completed_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", quote_id_for_tracking).eq("organization_id", org_id).execute()
        except Exception as e:
            print(f"Warning: Could not update spec control tracking: {e}")

    return RedirectResponse(f"/spec-control/{spec_id}", status_code=303)


# ============================================================================
# Feature #70: Specification PDF Preview
# ============================================================================

# @rt("/spec-control/{spec_id}/preview-pdf")
def get(session, spec_id: str):
    """
    Preview specification PDF in browser.

    Feature #70: Preview PDF спецификации

    Uses contract-style template with fixed delivery conditions.
    Opens PDF inline in browser for preview.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check role access
    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # UUID validation
    import uuid
    try:
        uuid.UUID(spec_id)
    except ValueError:
        return RedirectResponse("/spec-control", status_code=303)

    try:
        from services.contract_spec_export import generate_contract_spec_pdf

        # Generate PDF using contract-style template (no modal - uses fixed template)
        pdf_bytes, spec_number = generate_contract_spec_pdf(spec_id, org_id)

        # Clean filename for safe characters
        safe_spec_number = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(spec_number))

        # Return as inline view (opens in browser)
        from starlette.responses import Response
        filename = f"Specification_{safe_spec_number}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
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
        import traceback
        traceback.print_exc()
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
# Contract-style Specification Export (Direct Download - No Modal)
# ============================================================================

# @rt("/spec-control/{spec_id}/export-pdf")
def get(session, spec_id: str):
    """
    Download specification PDF.

    Uses contract-style template with fixed delivery conditions.
    All variable values are pulled from the database - no user input needed.
    Downloads PDF as attachment.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # UUID validation
    import uuid
    try:
        uuid.UUID(spec_id)
    except ValueError:
        return RedirectResponse("/spec-control", status_code=303)

    try:
        from services.contract_spec_export import generate_contract_spec_pdf

        # Generate PDF using contract-style template with fixed delivery conditions
        pdf_bytes, spec_number = generate_contract_spec_pdf(spec_id, org_id)

        safe_spec_number = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(spec_number))

        from starlette.responses import Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="Specification_{safe_spec_number}.pdf"'}
        )

    except Exception as e:
        print(f"Error generating contract specification PDF: {e}")
        import traceback
        traceback.print_exc()
        return page_layout("Ошибка",
            H1("Ошибка генерации PDF"),
            Div(f"Ошибка: {str(e)}", cls="card", style="background: #fee2e2; border-left: 4px solid #dc2626;"),
            A("← Назад", href=f"/spec-control/{spec_id}"),
            session=session
        )


# @rt("/spec-control/{spec_id}/export-docx")
def get(session, spec_id: str):
    """
    Download specification as DOCX (Beta).

    Uses same data as PDF export but generates editable Word document.
    Beta feature - allows users to edit the document if needed.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["spec_controller", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # UUID validation
    import uuid
    try:
        uuid.UUID(spec_id)
    except ValueError:
        return RedirectResponse("/spec-control", status_code=303)

    try:
        from services.contract_spec_docx import generate_contract_spec_docx
        from services.contract_spec_export import fetch_contract_spec_data

        # Generate DOCX
        docx_bytes = generate_contract_spec_docx(spec_id, org_id)

        # Get spec number for filename
        data = fetch_contract_spec_data(spec_id, org_id)
        spec_number = data["specification"].get("specification_number") or data["specification"].get("proposal_idn") or "spec"
        safe_spec_number = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(spec_number))

        from starlette.responses import Response
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="Specification_{safe_spec_number}.docx"'}
        )

    except Exception as e:
        print(f"Error generating contract specification DOCX: {e}")
        import traceback
        traceback.print_exc()
        return page_layout("Ошибка",
            H1("Ошибка генерации DOCX"),
            Div(f"Ошибка: {str(e)}", cls="card", style="background: #fee2e2; border-left: 4px solid #dc2626;"),
            A("← Назад", href=f"/spec-control/{spec_id}"),
            session=session
        )


# ============================================================================
# Feature #71: Upload signed specification scan (simplified with document_service)
# ============================================================================

# @rt("/spec-control/{spec_id}/upload-signed")
async def post(session, spec_id: str, request):
    """
    Upload signed specification scan using unified document_service.

    Feature #71: Загрузка подписанного скана
    Simplified: Uses document_service for unified document storage.

    Accepts PDF, JPG, PNG files up to 50MB (document_service limit).
    Stores in unified 'kvota-documents' bucket via document_service.
    Updates specifications.signed_scan_document_id with document reference.
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
        .is_("deleted_at", None) \
        .execute()

    if not spec_result.data:
        return RedirectResponse("/spec-control", status_code=303)

    spec = spec_result.data[0]
    status = spec.get("status", "draft")
    quote_id = spec.get("quote_id")

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

        # Read file content
        file_content = await signed_scan.read()
        filename = signed_scan.filename

        # Use document_service for upload (handles validation, storage, metadata)
        doc, error = upload_document(
            organization_id=org_id,
            entity_type="specification",
            entity_id=spec_id,
            file_content=file_content,
            filename=filename,
            document_type="specification_signed_scan",
            uploaded_by=user_id,
            parent_quote_id=quote_id,  # For hierarchical aggregation
        )

        if error:
            return page_layout("Ошибка загрузки",
                H1("Ошибка загрузки файла"),
                Div(error, cls="card", style="background: #fee2e2; border-left: 4px solid #dc2626;"),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Update specification with document reference
        # Keep signed_scan_url for backward compatibility (generate signed URL)
        signed_url = get_download_url(doc.id, expires_in=3600*24*365)  # 1 year expiry

        supabase.table("specifications") \
            .update({
                "signed_scan_document_id": doc.id,
                "signed_scan_url": signed_url,  # Backward compatibility
                "updated_at": datetime.now().isoformat()
            }) \
            .eq("id", spec_id) \
            .execute()

        print(f"Signed scan uploaded successfully via document_service: doc_id={doc.id}")

        # Redirect back to spec page with success
        return RedirectResponse(f"/spec-control/{spec_id}?upload_success=1", status_code=303)

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

# @rt("/spec-control/{spec_id}/confirm-signature")
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
            .is_("deleted_at", None) \
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

        # Validate all quote items have IDN-SKU (Feature P2.2)
        quote_id = spec.get("quote_id")
        is_valid, idn_sku_error = validate_quote_items_have_idn_sku(quote_id)
        if not is_valid:
            return page_layout("Ошибка валидации IDN-SKU",
                H1("Не все позиции имеют IDN-SKU"),
                Div(
                    idn_sku_error,
                    cls="card", style="background: #fee2e2; border-left: 4px solid #dc2626; white-space: pre-line;"
                ),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        # Check if deal already exists for this spec
        existing_deal = supabase.table("deals") \
            .select("id, deal_number") \
            .eq("specification_id", spec_id) \
            .is_("deleted_at", None) \
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
        quote_result = supabase.table("quotes") \
            .select("id, total_amount, customers(id, name)") \
            .eq("id", quote_id) \
            .is_("deleted_at", None) \
            .execute()

        if not quote_result.data:
            return page_layout("Ошибка",
                H1("КП не найдено"),
                Div("Связанное КП не найдено.", cls="card", style="background: #fee2e2;"),
                A("← Назад к спецификации", href=f"/spec-control/{spec_id}"),
                session=session
            )

        quote = quote_result.data[0]
        total_amount = quote.get("total_amount") or 0

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
                .is_("deleted_at", None) \
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

        # Step 2b: Auto-initialize 7 logistics stages for the new deal
        try:
            from services.logistics_service import initialize_logistics_stages
            initialize_logistics_stages(deal_id, user_id)
        except Exception as e:
            print(f"Note: Could not initialize logistics stages: {e}")

        # Step 2c: Generate currency invoices for the new deal
        try:
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
                ci_invoices = generate_currency_invoices(
                    deal_id=str(deal_id),
                    quote_idn=ci_quote_idn,
                    items=ci_items,
                    buyer_companies=bc_lookup,
                    seller_company=ci_seller_company,
                    organization_id=org_id,
                    contracts=ci_contracts,
                    bank_accounts=ci_bank_accounts,
                )
                if ci_invoices:
                    save_currency_invoices(supabase, ci_invoices)
                    print(f"Currency invoices generated: {len(ci_invoices)} invoice(s) for deal {deal_id}")
                else:
                    print(f"No currency invoices generated for deal {deal_id} (no eligible items)")
            else:
                print(f"Currency invoice generation skipped: no buyer companies or seller company for deal {deal_id}")
        except Exception as e:
            print(f"Warning: currency invoice generation failed: {e}")
            # Non-blocking — deal creation still succeeds

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
            H1(icon("check-circle", size=28), " Сделка успешно создана", cls="page-header"),
            Div(
                H3(f"Номер сделки: {deal_number}"),
                P(f"Клиент: {quote.get('customers', {}).get('name', 'N/A') if quote.get('customers') else 'N/A'}"),
                P(f"Сумма: {total_amount:,.2f} {currency}"),
                P(f"Дата подписания: {sign_date}"),
                cls="card",
                style="background: #d4edda; border-left: 4px solid #28a745; padding: 1rem;"
            ),
            Div(
                btn_link("К спецификации", href=f"/spec-control/{spec_id}", variant="primary", icon_name="arrow-right"),
                btn_link("Назад к списку", href="/spec-control", variant="secondary", icon_name="arrow-left"),
                style="margin-top: 1rem; display: flex; gap: 0.5rem;"
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

