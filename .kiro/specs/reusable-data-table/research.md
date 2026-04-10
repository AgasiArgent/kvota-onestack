# Research & Design Decisions — Reusable Data Table

## Summary

- **Feature**: `reusable-data-table`
- **Discovery Scope**: Complex Integration (new reusable component + DB schema + migration of existing registry)
- **Key Findings**:
  - Project uses Base UI (`@base-ui/react@^1.3.0`) for primitives — Dialog already exists, Popover must be added as new primitive.
  - No existing `shared/ui/` components beyond `scrollable-table.tsx` and `pagination.tsx`. The data-table needs to live in `shared/ui/data-table/` per FSD conventions.
  - Current `quotes-table.tsx` is feature-local (`features/quotes/ui/`) and tightly coupled to `QuoteListItem`. Full rewrite is justified.
  - `kvota.user_table_views` does not yet exist; migration **261** (bumped from 259 due to concurrent migration numbering from `259_allow_empty_comment_body.sql` and `260_backfill_logistics_assignment.sql`).

## Research Log

### Topic: Column filter popover — library choice

- **Context**: Requirements R2 and R3 describe multi-select and range filter popovers on column headers.
- **Findings**:
  - Base UI provides `Popover` primitive with the same API style as Dialog. Zero additional dependencies.
  - Existing shadcn-style wrappers in `components/ui/` demonstrate the pattern: thin composition over Base UI.
  - No need for headless table libraries — current table renders via `<Table>` from shadcn.
- **Implications**: Add `components/ui/popover.tsx` wrapper. All filter popovers use this primitive.

### Topic: URL state serialization format

- **Context**: Requirement R8 mandates URL as source of truth.
- **Findings**:
  - Single-value params already used for customer, manager, status.
  - Multi-value needs comma-separated convention.
  - Range filters need distinct naming to avoid collision with multi-value.
  - Sort convention `?sort=-amount` exists and should be preserved.
- **Implications**:
  - Multi-value: `?<column>=v1,v2,v3`
  - Range: `?<column>__min=100&<column>__max=5000`
  - Sort: `?sort=-<column>` or `?sort=<column>`
  - View: `?view=<uuid>` (populates other params on first load)

### Topic: Supabase filter translation — multi-value and range

- **Context**: Translate URL filter state into Supabase query predicates without losing type safety.
- **Findings**:
  - `.in("column", [values])` maps to multi-select IN predicate.
  - `.gte()` / `.lte()` map to range bounds.
  - FK filters (procurement manager on `quote_items`) need pre-query to resolve quote IDs, then `.in("id", quoteIds)` on main query.
- **Implications**: DataTable is data-source agnostic — provides filter state to consumer; consumer translates to Supabase predicates.

### Topic: Saved views schema — personal vs shared

- **Context**: R6 (personal views) + R7 (forward-compatible shared views).
- **Findings**:
  - Partial unique indexes work in Postgres (`WHERE is_shared = false`).
  - RLS policies can be layered: personal match on `user_id`, shared match on `organization_id` membership.
- **Implications**:
  - Single table with `is_shared` flag.
  - Two partial unique indexes.
  - RLS with personal-owner-all policy + shared-org-read + shared-owner-write policies.

### Topic: Column visibility storage — localStorage vs saved view

- **Context**: R5 dual-source model (localStorage + view override).
- **Findings**:
  - localStorage is origin-scoped, acceptable for low-stakes UI preference.
  - Storage key must include `tableKey` to avoid collision across registries.
- **Implications**: Two-tier system: active view > localStorage > config defaults. Stale keys filtered silently (R5.6).

### Topic: Quotes table integration — migration safety

- **Context**: R12 requires no regression in quotes registry.
- **Findings**:
  - `fetchQuotesList` has role-based access control — must stay in query layer.
  - "Requires your action" grouping computed via `getActionStatusesForUser(user.roles)` — passed to DataTable as grouping predicate.
- **Implications**: DataTable is controlled; access control stays in query. Consumer orchestrates.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Decision |
|--------|-------------|-----------|---------------------|----------|
| Custom on shadcn Table | Build filter popovers + view system on existing shadcn primitives | Full control, consistent styling, small bundle | More code upfront | **Selected** |
| TanStack Table v8 | Headless table library | Battle-tested, feature-rich | Still need UI on top; client-side filtering by default | Rejected |
| ag-grid Community | Commercial grade table | Many features | Multi-value filter (Set Filter) is Enterprise only; large bundle; visual mismatch | Rejected |

## Design Decisions

### Decision: Base UI Popover as filter shell

- **Selected Approach**: Add `components/ui/popover.tsx` wrapping `@base-ui/react/popover`.
- **Rationale**: Zero new dependencies; project already committed to Base UI family.

### Decision: DataTable is data-source agnostic

- **Selected Approach**: DataTable receives `{ rows, total, page, pageSize }` and emits state changes. Consumer owns query + access control.
- **Rationale**: Keeps access control in query layer; allows any data source.

### Decision: URL is single source of truth; views populate URL on load

- **Selected Approach**: Selecting a view dispatches URL navigation. Drift detected by canonicalized JSON compare.
- **Rationale**: Preserves URL shareability; avoids double source of truth.

### Decision: Migration 261 for user_table_views

- **Context**: Migration 259 and 260 were taken by other concurrent work.
- **Selected**: `migrations/261_create_user_table_views.sql`.

### Decision: Remove status group-key concept

- **Selected Approach**: Filter popover renders individual statuses only; group concept survives as UI helper (e.g., "Select all in-progress" button), never propagates to URL.
- **Rationale**: Eliminates dual-parsing logic; URL semantics become consistent.

## Risks & Mitigations

- **Popover wrapper conflict with future shadcn**: Follow exact `dialog.tsx` pattern — same naming, same exports.
- **Shared views RLS bugs**: Write policies defensively with explicit `auth.uid()` + `organization_id` matches.
- **URL parameter bloat**: Use short param names; compress only if bookmarking becomes a practical problem.
- **Breaking quotes registry during migration**: Build DataTable in parallel, swap quotes-table last, browser tests before merge.
- **localStorage bloat**: Storage key includes `tableKey`; bounded by number of tables × column list size.
- **Views modified-state false positives**: Canonicalize filter serialization (sort keys, sort values) before comparing.

## References

- Base UI documentation — Popover primitive
- Supabase RLS guide — RLS policy design
- Feature-Sliced Design — layer rules for R13 component placement
- `.kiro/steering/access-control.md` — visibility tiers
- `.kiro/steering/tech.md` — technology stack constraints
- `.kiro/steering/structure.md` — FSD layer rules
