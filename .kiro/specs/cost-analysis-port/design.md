# Cost Analysis Port — Design

## Scope

Migrate the `/quotes/{id}/cost-analysis` FastHTML page to Next.js + FastAPI.
Pure read-only viewer: no writes, no calculations beyond the existing
aggregation logic. FastHTML handler (`main.py` L5834-6140) stays in this PR
and will be archived in a follow-up.

## API Contract

`GET /api/quotes/{quote_id}/cost-analysis`

Auth: Bearer JWT only (handled by `ApiAuthMiddleware`).
Role gate: `finance`, `top_manager`, `admin`, `quote_controller`.
Response envelope follows the project standard (`success`/`data`/`error`).

Success shape (`data`):
```json
{
  "quote": {
    "id": "uuid", "idn_quote": "Q-...", "title": "...",
    "currency": "USD", "workflow_status": "approved",
    "customer_name": "ACME"
  },
  "has_calculation": true,
  "totals": {
    "revenue_no_vat": 0.0, "revenue_with_vat": 0.0,
    "purchase": 0.0, "logistics": 0.0, "customs": 0.0, "excise": 0.0,
    "dm_fee": 0.0, "forex": 0.0, "financial_agent_fee": 0.0, "financing": 0.0
  },
  "logistics_breakdown": {
    "W2_supplier_hub": 0.0, "W3_hub_customs": 0.0, "W4_customs_client": 0.0,
    "W5_brokerage_hub": 0.0, "W6_brokerage_customs": 0.0, "W7_warehousing": 0.0,
    "W8_documentation": 0.0, "W9_extra": 0.0, "W10_insurance": 0.0
  },
  "derived": {
    "direct_costs": 0.0, "gross_profit": 0.0,
    "financial_expenses": 0.0, "net_profit": 0.0,
    "markup_pct": 0.0, "sale_purchase_ratio": 0.0
  }
}
```

Errors:
- `401 UNAUTHORIZED` — no/invalid JWT
- `403 FORBIDDEN` — role gate or org mismatch
- `404 NOT_FOUND` — quote missing / soft-deleted

When `has_calculation == false`, totals/logistics_breakdown/derived are zero.
Clients render an empty state.

## Module Layout

Backend (Python):
- `api/cost_analysis.py` — handler `get_cost_analysis(request, quote_id)`
- `api/routers/cost_analysis.py` — APIRouter thin wrapper
- `api/app.py` — register router at `prefix="/quotes"` (endpoint lives at
  `/api/quotes/{id}/cost-analysis`)

Frontend (Next.js):
- `frontend/src/features/cost-analysis/api/queries.ts` — server-only fetcher
- `frontend/src/features/cost-analysis/types.ts` — response DTOs
- `frontend/src/features/cost-analysis/ui/cost-analysis-view.tsx` — server
  component rendering cards + waterfall table
- `frontend/src/features/cost-analysis/ui/summary-cards.tsx` — 4 metric cards
- `frontend/src/features/cost-analysis/ui/waterfall-table.tsx` — P&L table
- `frontend/src/features/cost-analysis/ui/not-calculated.tsx` — empty state
- `frontend/src/features/cost-analysis/index.ts` — slice public API
- `frontend/src/app/(app)/quotes/[id]/cost-analysis/page.tsx` — route entry

## Data Flow

1. Next.js page reads session via `getSessionUser()`; if no user → redirect
   `/login`.
2. Page calls `apiServerClient('/quotes/{id}/cost-analysis')` which forwards
   the Supabase JWT as Bearer.
3. FastAPI handler authenticates via `request.state.api_user` (JWT middleware),
   resolves `org_id` from `organization_members`, role slugs from `user_roles`.
4. Handler selects the quote (with `customers!customer_id(name)` join and
   `deleted_at IS NULL`), aggregates `quote_calculation_results.phase_results`,
   extracts variables, computes derived metrics, returns JSON envelope.
5. Page maps error codes: 403 → `redirect('/unauthorized')`, 404 → `notFound()`,
   other failures → error message placeholder.
6. For `has_calculation=false`, renders `<NotCalculated />`. Otherwise renders
   `<SummaryCards />` + `<WaterfallTable />`.

## Visual Design

- 4-card grid (shadcn Card component). Net Profit card uses green-600 for
  positive, red-600 for negative. Markup uses `text-foreground`.
- Waterfall table uses shadcn `<Table>`. Subtotal rows (`Revenue`,
  `Gross Profit`, `Net Profit`) have `bg-muted/50` + `font-semibold`.
  Indented W2-W10 rows use `pl-8 text-muted-foreground text-xs`.
- Page header: breadcrumb `Quotes / {idn_quote} / Кост-анализ` + workflow
  status badge. We do NOT reuse the full `QuoteStatusRail` for this PR (the
  rail is designed for in-workflow editing; cost-analysis is a standalone view).
  This keeps the port lightweight and matches the FastHTML screen which only
  had breadcrumb + header.

## Role Gate (Backend)

```python
ALLOWED_ROLES = {"finance", "top_manager", "admin", "quote_controller"}
if not role_slugs & ALLOWED_ROLES:
    return 403 FORBIDDEN
```

## Role Gate (Frontend)

The page checks the user's roles from `getSessionUser()`. If none match the
allowed set, redirect to `/unauthorized` before even calling the API.
This prevents a round-trip for known-unauthorized cases. The API still
enforces the gate as the source of truth.

## Out of Scope

- Removing the FastHTML handler (archival in follow-up PR per task scope).
- Changing any calculation logic.
- Adding new workflow status transitions.
- Integration with `QuoteStatusRail` (separate future task if desired).
