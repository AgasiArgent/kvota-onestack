"""FastHTML cost-analysis dashboard — archived 2026-04-20 during Phase 6C-2B Mega-F.

This was the read-only P&L waterfall dashboard mounted at
GET /quotes/{quote_id}/cost-analysis, showing aggregated cost breakdown per
quote (revenue, purchase, logistics W2-W10 breakdown, customs, excise,
gross/net profit, markup %, sale/purchase ratio). Visible to finance,
top_manager, admin, quote_controller roles.

Replaced in PR #50 by:
  - FastAPI endpoint GET /api/quotes/{quote_id}/cost-analysis
    (api/cost_analysis.py + api/routers/cost_analysis.py — ALIVE)
  - Next.js page frontend/src/app/(app)/quotes/[id]/cost-analysis/page.tsx
    (ALIVE — consumes the FastAPI endpoint)

Post-Caddy-cutover kvotaflow.ru 301→app.kvotaflow.ru does not proxy
/quotes/{id}/cost-analysis back to this Python container, so the route is
unreachable for end users. Preserved here for reference / future copy-back.

Contents (2 @app.get routes in the original — but only 1 preserved here):

  - GET /quotes/{quote_id}/cost-analysis
      Full P&L waterfall handler (~300 LOC). Queries
      quote_calculation_results.phase_results (per-item JSONB) and
      quote_calculation_variables.variables (quote-level W2-W10 breakdown),
      aggregates across items, renders page_layout with quote_header +
      quote_detail_tabs + cards + P&L table.

  - GET /quotes/{quote_id}/cost-analysis-json
      501 Not Implemented stub — NOT preserved here. Was a placeholder
      JSON endpoint that never got built; the real JSON API is the
      FastAPI handler at GET /api/quotes/{quote_id}/cost-analysis.
      Deleted entirely from main.py during this archive (no recovery
      value — stub had no functionality).

NOTE: These were `@app.get(...)` decorators (direct FastHTML app routing),
NOT `@rt(...)` — a different pattern than prior archives where @rt was the
norm. Mirroring the prior archive convention, the decorator is commented as
`# @app.get(...)` below.

Preserved in main.py (consumed by other alive surfaces):
  - require_login, user_has_any_role
  - get_supabase
  - quote_detail_tabs, quote_header, page_layout
  - FastHTML component imports (A, Div, H1, H2, H3, P, Table, Tbody,
    Thead, Tfoot, Tr, Td, Th, Strong)
  - RedirectResponse, JSONResponse

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect the handler: copy it back to main.py,
restore any missing imports, re-apply the @app.get decorator. Not
recommended — use the FastAPI + Next.js replacement instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Div, H1, H2, H3, P, Table, Tbody, Tfoot, Thead, Tr, Td, Th, Strong,
)
from starlette.responses import RedirectResponse


# ============================================================================
# COST ANALYSIS (КА) DASHBOARD — P&L Waterfall View
# ============================================================================

# @app.get("/quotes/{quote_id}/cost-analysis")  # decorator removed; file is archived and not mounted
def get_cost_analysis(session, quote_id: str):
    """
    Cost Analysis (КА) Dashboard — read-only P&L waterfall for a quote.

    Shows aggregated cost breakdown from existing calculation results:
    - Revenue (no VAT / with VAT)
    - Purchase cost, Logistics (with W2-W10 breakdown), Customs, Excise
    - Gross Profit = Revenue - Direct Costs
    - Financial expenses: DM fee, Forex reserve, Fin agent fee, Financing
    - Net Profit = Gross Profit - Financial Expenses
    - Markup % and Sale/Purchase ratio

    Visible to: finance, top_manager, admin, quote_controller roles.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]
    user_roles = user.get("roles", [])

    # Role check: only finance, top_manager, admin, quote_controller
    allowed_roles = ["finance", "top_manager", "admin", "quote_controller"]
    if not user_has_any_role(session, allowed_roles):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch quote with org isolation check (organization_id must match)
    quote_result = supabase.table("quotes") \
        .select("id, organization_id, idn_quote, title, currency, seller_company_id, delivery_terms, delivery_days, payment_terms, workflow_status, total_amount, customers(name)") \
        .eq("id", quote_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует."),
            A("← Назад", href="/quotes"),
            session=session
        )

    quote = quote_result.data[0]
    customer_name = (quote.get("customers") or {}).get("name", "—")

    # Org isolation: check organization_id matches user's org_id
    if quote.get("organization_id") != org_id:
        return Redirect("/quotes", status_code=303)

    # Build tab navigation with cost_analysis as active tab
    tabs = quote_detail_tabs(quote_id, "cost_analysis", user_roles, quote=quote, user_id=user_id)

    # Fetch calculation results (phase_results per item)
    calc_results_resp = supabase.table("quote_calculation_results") \
        .select("quote_item_id, phase_results") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_results = calc_results_resp.data if calc_results_resp.data else []

    # Fetch calculation variables (W2-W10 logistics breakdown)
    calc_vars_resp = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_vars = calc_vars_resp.data[0]["variables"] if calc_vars_resp.data else {}

    # If no calculation results exist, show "not calculated" message
    if not calc_results:
        return page_layout(
            f"Кост-анализ — {quote.get('idn_quote', '')}",
            quote_header(quote, quote.get("workflow_status", "draft"), customer_name),
            tabs,
            Div(
                Div(
                    H2("Кост-анализ", style="margin: 0 0 0.5rem 0; font-size: 1.25rem;"),
                    P("Расчёт ещё не выполнен. Вернитесь на вкладку Продажи и нажмите «Рассчитать».",
                      style="color: #6b7280; margin: 0;"),
                    style="padding: 2rem; text-align: center; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb;"
                ),
                style="padding: 1.5rem;"
            ),
            session=session
        )

    # ── Aggregate phase_results across all items ──
    # Keys: AK16=revenue_no_vat, AL16=revenue_with_vat, S16=purchase,
    #        V16=logistics, Y16=customs, Z16=excise,
    #        AG16=dm_fee, AH16=forex_reserve, AI16=financial_agent_fee, BB16=financing
    aggregate_keys = ["AK16", "AL16", "S16", "V16", "Y16", "Z16", "AG16", "AH16", "AI16", "BB16"]
    totals = {k: 0.0 for k in aggregate_keys}

    for result in calc_results:
        pr = result.get("phase_results", {})
        for key in aggregate_keys:
            totals[key] += float(pr.get(key, 0) or 0)

    revenue_no_vat = totals["AK16"]
    revenue_with_vat = totals["AL16"]
    total_purchase = totals["S16"]
    total_logistics = totals["V16"]
    total_customs = totals["Y16"]
    total_excise = totals["Z16"]
    total_dm_fee = totals["AG16"]
    total_forex = totals["AH16"]
    total_fin_agent = totals["AI16"]
    total_financing = totals["BB16"]

    # ── Derived P&L calculations ──
    direct_costs = total_purchase + total_logistics + total_customs + total_excise
    gross_profit = revenue_no_vat - direct_costs

    financial_expenses = total_dm_fee + total_forex + total_fin_agent + total_financing
    net_profit = gross_profit - financial_expenses

    # Markup % = (revenue / purchase - 1) * 100, with zero-division protection
    if total_purchase > 0:
        markup_pct = (revenue_no_vat / total_purchase - 1) * 100
        sale_purchase_ratio = revenue_no_vat / total_purchase
    else:
        markup_pct = 0.0
        sale_purchase_ratio = 0.0

    # Revenue percentage helper (avoid division by zero)
    def pct_of_revenue(value):
        if revenue_no_vat > 0:
            return (value / revenue_no_vat) * 100
        return 0.0

    # ── Extract W2-W10 logistics breakdown from variables ──
    logistics_supplier_hub = float(calc_vars.get("logistics_supplier_hub", 0) or 0)
    logistics_hub_customs = float(calc_vars.get("logistics_hub_customs", 0) or 0)
    logistics_customs_client = float(calc_vars.get("logistics_customs_client", 0) or 0)
    brokerage_hub = float(calc_vars.get("brokerage_hub", 0) or 0)
    brokerage_customs = float(calc_vars.get("brokerage_customs", 0) or 0)
    warehousing_at_customs = float(calc_vars.get("warehousing_at_customs", 0) or 0)
    customs_documentation = float(calc_vars.get("customs_documentation", 0) or 0)
    brokerage_extra = float(calc_vars.get("brokerage_extra", 0) or 0)
    insurance = float(calc_vars.get("rate_insurance", 0) or 0)

    # ── Format helper ──
    def fmt(value):
        return f"{value:,.2f}"

    # ── Card styles ──
    card_style = "background: white; border-radius: 8px; padding: 1rem 1.25rem; border: 1px solid #e5e7eb; text-align: center;"
    card_label_style = "font-size: 0.8rem; color: #6b7280; margin: 0 0 0.25rem 0;"
    card_value_style = "font-size: 1.25rem; font-weight: 700; margin: 0; color: #111827;"

    # ── Build P&L waterfall table ──
    row_style = "border-bottom: 1px solid #f3f4f6;"
    subtotal_style = "border-bottom: 2px solid #e5e7eb; background: #f9fafb; font-weight: 600;"
    indent_style = "padding-left: 2rem; color: #6b7280; font-size: 0.85rem;"

    waterfall_rows = [
        # Revenue section
        Tr(
            Td(Strong("Выручка (без НДС)"), style="padding: 0.5rem 0.75rem;"),
            Td(Strong(fmt(revenue_no_vat)), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td("100.0%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=subtotal_style
        ),
        # Purchase cost
        Tr(
            Td("Сумма закупки", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_purchase), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_purchase):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # Logistics total with breakdown
        Tr(
            Td("Логистика (итого)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_logistics), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_logistics):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # W2-W10 breakdown sub-rows
        Tr(Td("Логистика до СВХ (W2)", style=indent_style), Td(fmt(logistics_supplier_hub), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("ТР — РФ (W3)", style=indent_style), Td(fmt(logistics_hub_customs), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("РФ — КУДА (W4)", style=indent_style), Td(fmt(logistics_customs_client), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Брокерские до РФ (W5)", style=indent_style), Td(fmt(brokerage_hub), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Брокерские в РФ (W6)", style=indent_style), Td(fmt(brokerage_customs), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Порт и СВХ в РФ (W7)", style=indent_style), Td(fmt(warehousing_at_customs), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Сертификация (W8)", style=indent_style), Td(fmt(customs_documentation), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Доп. расход (W9)", style=indent_style), Td(fmt(brokerage_extra), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Страховка (W10)", style=indent_style), Td(fmt(insurance), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        # Customs duty
        Tr(
            Td("Пошлина", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_customs), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_customs):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # Excise
        Tr(
            Td("Акциз", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_excise), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_excise):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # === Gross Profit subtotal ===
        Tr(
            Td(Strong("= Валовая прибыль (Gross Profit)"), style="padding: 0.5rem 0.75rem;"),
            Td(Strong(fmt(gross_profit)), style=f"text-align: right; padding: 0.5rem 0.75rem; color: {'#16a34a' if gross_profit >= 0 else '#dc2626'};"),
            Td(Strong(f"{pct_of_revenue(gross_profit):.1f}%"), style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=subtotal_style
        ),
        # Financial expenses section
        Tr(
            Td("Вознаграждение ЛПР (DM fee)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_dm_fee), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_dm_fee):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        Tr(
            Td("Резерв курсовой разницы (Forex)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_forex), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_forex):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        Tr(
            Td("Комиссия фин. агента (Financial agent fee)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_fin_agent), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_fin_agent):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        Tr(
            Td("Стоимость финансирования (Financing)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_financing), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_financing):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # === Net Profit subtotal ===
        Tr(
            Td(Strong("= Чистая прибыль (Net Profit)"), style="padding: 0.5rem 0.75rem;"),
            Td(Strong(fmt(net_profit)), style=f"text-align: right; padding: 0.5rem 0.75rem; color: {'#16a34a' if net_profit >= 0 else '#dc2626'};"),
            Td(Strong(f"{pct_of_revenue(net_profit):.1f}%"), style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=subtotal_style
        ),
        # Markup
        Tr(
            Td("Наценка (Markup %)", style="padding: 0.5rem 0.75rem;"),
            Td(f"{markup_pct:.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; font-weight: 600;"),
            Td("", style="padding: 0.5rem;"),
            style=row_style
        ),
    ]

    # ── Assemble page ──
    currency = quote.get("currency", "USD")

    content = Div(
        # Top-line metric cards
        Div(
            Div(
                P("Выручка (без НДС)", style=card_label_style),
                P(f"{fmt(revenue_no_vat)} {currency}", style=card_value_style),
                style=card_style
            ),
            Div(
                P("Выручка (с НДС)", style=card_label_style),
                P(f"{fmt(revenue_with_vat)} {currency}", style=card_value_style),
                style=card_style
            ),
            Div(
                P("Чистая прибыль", style=card_label_style),
                P(f"{fmt(net_profit)} {currency}", style=f"{card_value_style} color: {'#16a34a' if net_profit >= 0 else '#dc2626'};"),
                style=card_style
            ),
            Div(
                P("Наценка (выр. ÷ закуп − 1)", style=card_label_style),
                P(f"{markup_pct:.1f}%", style=card_value_style),
                style=card_style
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;"
        ),
        # P&L Waterfall table
        Div(
            H3("P&L Waterfall — Кост-анализ", style="margin: 0 0 1rem 0; font-size: 1.1rem; color: #374151;"),
            Table(
                Thead(
                    Tr(
                        Th("Статья", style="text-align: left; padding: 0.5rem 0.75rem; background: #f9fafb; border-bottom: 2px solid #e5e7eb;"),
                        Th(f"Сумма ({currency})", style="text-align: right; padding: 0.5rem 0.75rem; background: #f9fafb; border-bottom: 2px solid #e5e7eb;"),
                        Th("% от выручки", style="text-align: right; padding: 0.5rem 0.75rem; background: #f9fafb; border-bottom: 2px solid #e5e7eb;"),
                    )
                ),
                Tbody(*waterfall_rows),
                style="width: 100%; border-collapse: collapse; font-size: 0.875rem;"
            ),
            style="background: white; border-radius: 8px; padding: 1.25rem; border: 1px solid #e5e7eb;"
        ),
        style="padding: 1.5rem;"
    )

    return page_layout(
        f"Кост-анализ — {quote.get('idn_quote', '')}",
        quote_header(quote, quote.get("workflow_status", "draft"), customer_name),
        tabs,
        content,
        session=session
    )
