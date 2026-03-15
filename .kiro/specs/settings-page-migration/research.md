# Research & Design Decisions

## Summary
- **Feature**: `settings-page-migration`
- **Discovery Scope**: Extension (migrating existing pages to new framework with UX redesign)
- **Key Findings**:
  - Existing FSD patterns provide clear blueprint: entities (types + queries + mutations), features (UI + hooks), pages (thin shells)
  - All DB tables already exist — no migrations needed, pure frontend work
  - Supabase client pattern well-established: server-side queries in entities, client-side mutations in features

## Research Log

### Existing FSD Architecture Patterns
- **Context**: Need to follow established patterns for consistency
- **Sources**: `frontend/src/entities/customer/`, `frontend/src/features/customers/`, `frontend/src/app/(app)/profile/page.tsx`
- **Findings**:
  - Entity layer: `types.ts` (interfaces), `queries.ts` (server-side Supabase), `mutations.ts` (client-side Supabase), `index.ts` (barrel)
  - Feature layer: `ui/` directory with components, `index.ts` barrel
  - Page layer: thin async server components that fetch data and pass to feature components
  - Supabase server client: `createClient()` from `@/shared/lib/supabase/server` — used in queries
  - Supabase browser client: `createClient()` from `@/shared/lib/supabase/client` — used in mutations
  - Types are hand-written interfaces (not generated from DB types), though `database.types.ts` exists for build-time safety
- **Implications**: Settings entity follows same pattern. Queries fetch org settings server-side, mutations upsert client-side.

### Tab Implementation Options
- **Context**: Need URL-synced tabs for 3 settings sections
- **Alternatives**:
  1. shadcn/ui `Tabs` + `useSearchParams` — client component, URL sync via router
  2. Next.js parallel routes — server-side, but overkill for simple tabs
  3. shadcn/ui `Tabs` + `defaultValue` from searchParams prop — hybrid
- **Selected**: Option 3 — page passes `searchParams.tab` to client component. Matches existing customer detail tab pattern.
- **Implications**: Page remains a server component (fetches all tab data), tabs component is client-side

### Inline Editing Pattern
- **Context**: Brand discount table needs inline editing (req 4.3, 4.4)
- **Findings**:
  - No existing inline editing pattern in the codebase — this is new
  - shadcn/ui provides `Table` + `Input` components sufficient for inline editing
  - Pattern: row state toggles between display and edit mode, escape cancels, enter/blur saves
  - Optimistic updates via local state, revert on error
- **Implications**: New pattern to establish. Keep simple — no data grid library needed for ~20-50 rows.

## Design Decisions

### Decision: Single Data Fetch vs Per-Tab Lazy Loading
- **Context**: 3 tabs with different data sources — fetch all at once or lazy-load per tab?
- **Alternatives**:
  1. Fetch all in server component (simple, consistent with existing pages)
  2. Lazy-load per tab (reduced initial payload)
- **Selected**: Option 1 — fetch all in server component
- **Rationale**: Settings data is small (3 rows max from 3 tables). No performance benefit from lazy loading. Simpler implementation. Matches profile page pattern.
- **Trade-offs**: Slightly more data on initial load (~1KB extra), but eliminates loading spinners per tab.

### Decision: Client-side Percentage Calculation
- **Context**: PHMB tab needs live percentage preview (req 3.3)
- **Selected**: Pure client-side calculation in the React component
- **Rationale**: Formula is trivial (`cost / base_price * 100`). No need for server round-trip. Instant feedback.
- **Trade-offs**: Calculation logic duplicated between frontend and `phmb_calculator.py`. Acceptable because it's a simple division.

## Risks & Mitigations
- **Risk 1**: Brand discount table might have 100+ rows → Mitigation: client-side search filter + paginate if >50 rows
- **Risk 2**: Race condition on concurrent admin saves → Mitigation: last-write-wins is acceptable for settings (single admin)
- **Risk 3**: Inline edit UX could be confusing → Mitigation: clear edit/save/cancel affordances, optimistic UI with error rollback
