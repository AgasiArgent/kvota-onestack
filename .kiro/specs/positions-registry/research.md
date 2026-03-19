# Research Log — positions-registry

**Date:** 2026-03-19
**Discovery Type:** Light (extension of existing Next.js frontend patterns)

## Summary

The Positions Registry is a new page following established FSD + server-component patterns. No new technologies needed. Key challenge is the aggregation query — grouping quote_items by brand + idn_sku with window functions to derive latest price, availability status, and entry counts.

## Research Log

### Topic 1: Data Aggregation Strategy

**Question:** How to efficiently query unique products with their latest pricing from quote_items?

**Findings:**
- Supabase JS client does not support `GROUP BY`, `DISTINCT ON`, or window functions directly
- Two viable approaches:
  1. **Database view** — create a Postgres view with `DISTINCT ON (brand, idn_sku)` that pre-aggregates the data, then query the view from Supabase
  2. **RPC function** — Postgres function with grouping logic, called via `supabase.rpc()`
- View approach is simpler — it's queryable like a table, supports `.select()`, `.eq()`, `.range()` etc.
- RPC approach is more flexible but requires manual parameter handling

**Decision:** Use a **database view** (`kvota.positions_registry_view`) for the master-level query. The view handles:
- `DISTINCT ON (brand, idn_sku)` ordered by `updated_at DESC` for latest entry
- JOIN to `user_profiles` for МОЗ name
- Subquery for entry count and availability classification
- Filter base: `procurement_status = 'completed' OR is_unavailable = true`

For the detail-level expansion, use a direct `quote_items` query filtered by brand + idn_sku.

### Topic 2: Availability Status Derivation

**Question:** How to classify mixed availability (product available in some quotes, unavailable in others)?

**Approach:** The view computes three aggregates per product group:
- `has_available`: `bool_or(NOT is_unavailable AND purchase_price_original IS NOT NULL)`
- `has_unavailable`: `bool_or(is_unavailable)`
- Derived status: both true → "mixed", only available → "available", only unavailable → "unavailable"

### Topic 3: Existing Patterns Analyzed

**Files reviewed:**
- `entities/supplier/queries.ts` — `createAdminClient()`, `PAGE_SIZE = 50`, filter chaining, parallel counts
- `entities/supplier/types.ts` — explicit interface per view (list item vs detail)
- `features/suppliers/ui/suppliers-table.tsx` — `form method="GET"` for filters, URL-based state, shadcn Table
- `app/(app)/suppliers/page.tsx` — server component pattern: auth → role check → parse searchParams → fetch → render
- `widgets/sidebar/sidebar-menu.ts` — `buildMenuSections()`, role-gated menu items

**Patterns to follow:**
- Server component fetches data, client component handles interaction
- URL search params for all filter state (no React state for filters)
- `createAdminClient()` for all server-side queries (bypasses RLS)
- Form-based filter submission with native HTML
- Pagination via `.range()` with `count: "exact"`

### Topic 4: Migration Requirement

A new migration is needed to create the `positions_registry_view` database view. This keeps the aggregation logic in SQL (where it's most efficient) and presents a flat, queryable surface to the Supabase JS client.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data aggregation | Database view | Supabase JS can't GROUP BY; view is queryable like a table |
| Detail fetch | Direct query | Simple filter by brand + SKU, no aggregation needed |
| Filter state | URL search params | Matches existing pattern (suppliers, customers) |
| Expand/collapse | Client-side state | Only UI state, no server round-trip for toggle |
| Detail data fetch | On initial load | Fetch all items, group client-side; avoids expand-on-click latency |

## Risks

1. **View performance** — If quote_items grows to 100K+ rows, the view may be slow. Mitigation: add index on `(brand, idn_sku, updated_at DESC)`.
2. **Null SKU handling** — Some items may have null `idn_sku`. Decision: treat null SKU as a distinct group per brand (coalesce to empty string in view).
