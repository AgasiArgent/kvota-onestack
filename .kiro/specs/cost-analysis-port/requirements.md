# Cost Analysis Port — Requirements

Port the read-only P&L waterfall viewer for `/quotes/{id}/cost-analysis` from
FastHTML (`main.py` L5834-6140) to Next.js + FastAPI, without changing the
business calculation. The FastAPI endpoint is JSON-only; the Next.js page is a
server component that consumes it.

## Functional Requirements

**REQ-001 Role gate.** WHEN a user without `finance`, `top_manager`, `admin`, or
`quote_controller` role requests `GET /api/quotes/{id}/cost-analysis`, THEN the
endpoint SHALL respond `403 FORBIDDEN`. WHEN the same user navigates to the
Next.js page `/quotes/{id}/cost-analysis`, THE page SHALL redirect to
`/unauthorized`.

**REQ-002 Authentication.** WHEN no Bearer JWT is present on the API request,
THE endpoint SHALL respond `401 UNAUTHORIZED`.

**REQ-003 Org isolation.** WHEN the quote's `organization_id` does not match
the caller's active `organization_id`, THE endpoint SHALL respond `403 FORBIDDEN`.

**REQ-004 Not-found.** WHEN the quote does not exist (or is soft-deleted via
`deleted_at IS NOT NULL`), THE endpoint SHALL respond `404 NOT_FOUND` and the
Next.js page SHALL render `notFound()`.

**REQ-005 Aggregation.** WHEN calculation results exist, THE endpoint SHALL
aggregate `phase_results` SUMs across all quote items for these keys:
AK16 (revenue_no_vat), AL16 (revenue_with_vat), S16 (purchase), V16 (logistics),
Y16 (customs), Z16 (excise), AG16 (dm_fee), AH16 (forex), AI16 (financial_agent_fee),
BB16 (financing). Missing keys SHALL be treated as 0.

**REQ-006 Logistics breakdown.** WHEN `quote_calculation_variables.variables`
is present, THE endpoint SHALL expose a `logistics_breakdown` object with keys
W2..W10 mapped from `logistics_supplier_hub`, `logistics_hub_customs`,
`logistics_customs_client`, `brokerage_hub`, `brokerage_customs`,
`warehousing_at_customs`, `customs_documentation`, `brokerage_extra`,
`rate_insurance`. Missing variables SHALL default to 0.

**REQ-007 Derived metrics.** THE endpoint SHALL compute and expose:
- `direct_costs = purchase + logistics + customs + excise`
- `gross_profit = revenue_no_vat - direct_costs`
- `financial_expenses = dm_fee + forex + financial_agent_fee + financing`
- `net_profit = gross_profit - financial_expenses`
- `markup_pct = (revenue_no_vat / purchase - 1) * 100` when purchase > 0, else 0
- `sale_purchase_ratio = revenue_no_vat / purchase` when purchase > 0, else 0

**REQ-008 Has-calculation flag.** IF no `quote_calculation_results` rows exist
for the quote, THE endpoint SHALL return `has_calculation=false` with zero totals/
breakdown/derived. THE Next.js page SHALL render an empty-state message
instructing the user to return to Calculation and press "Рассчитать".

**REQ-009 Number formatting.** THE Next.js page SHALL format all numeric values
with RU locale (`toLocaleString('ru-RU', {minimumFractionDigits:2, maximumFractionDigits:2})`)
and display the quote `currency` next to monetary values.

**REQ-010 Visual hierarchy.** THE page SHALL render:
- 4-card summary row: Revenue (no VAT), Revenue (with VAT), Net Profit, Markup %
- P&L waterfall table with waterfall rows in the exact same order as the
  FastHTML source, including 9 indented W2-W10 sub-rows under Logistics total.
- Gross Profit and Net Profit subtotals coloured green when ≥0 and red when <0.
