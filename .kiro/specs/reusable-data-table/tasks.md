# Implementation Plan — Reusable Data Table

Tasks grouped by architectural boundary to maximize parallel-capable work. Parallel-capable tasks are marked with `(P)`.

---

## 1. Foundations — Database, URL Helpers, Popover Primitive ✅ DONE

- [x] 1.1 (P) Create the `user_table_views` database migration
  - Migration 261 (was 259, bumped due to concurrent numbering)
  - Partial unique indexes for personal vs shared views
  - RLS policies: personal owner-only; shared forward-compatible
  - Default-view trigger, updated_at trigger
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [x] 1.2 (P) Add a Popover primitive wrapping Base UI
  - `frontend/src/components/ui/popover.tsx`
  - Follows `dialog.tsx` pattern: Popover, PopoverTrigger, PopoverPortal, PopoverContent, PopoverClose
  - _Requirements: enables 2.1, 3.1, 5.1, 6.1_

- [x] 1.3 Build URL state serialization utilities
  - `frontend/src/shared/lib/data-table/filter-serialize.ts`
  - Pure functions: parseFilterParams, serializeFilters, canonicalizeState, parseSortString, serializeSortString, cycleSortState
  - _Requirements: 8.1, 8.4, 8.5, 8.6, 8.8_

- [x] 1.4 Build the useTableState hook
  - `frontend/src/shared/lib/data-table/use-table-state.ts`
  - URL ↔ filter/sort/view/page/visibility state with localStorage fallback
  - Mutators reset page to 1 on filter change
  - serializeCurrent + isModifiedFromView helpers
  - _Requirements: 8.1, 8.2, 8.3, 8.7_

---

## 2. Filter and Visibility UI Primitives

- [ ] 2.1 (P) Build the multi-select column filter popover
  - `frontend/src/shared/ui/data-table/column-filter.tsx`
  - Search input + scrollable checkbox list + apply/reset
  - Select all toggles visible (post-search) options only
  - Count badge on trigger when filter is active
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8, 10.4_

- [ ] 2.2 (P) Build the numeric range filter popover
  - `frontend/src/shared/ui/data-table/range-filter.tsx`
  - Min/max numeric inputs with optional unit label
  - Partial ranges (either bound undefined)
  - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [ ] 2.3 (P) Build the column visibility popover
  - `frontend/src/shared/ui/data-table/column-visibility.tsx`
  - Checkbox per column (excluding `alwaysVisible`)
  - Immediate toggles, propagated via callback
  - _Requirements: 5.1, 5.2, 5.5, 5.6_

- [ ] 2.4 Build the column header component
  - `frontend/src/shared/ui/data-table/column-header.tsx`
  - Label + sort indicator + filter trigger
  - Sort tri-state (asc/desc/clear) via callback
  - Delegates to ColumnFilter or RangeFilter based on column config
  - _Requirements: 1.3, 1.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

---

## 3. Saved Views Entity and Selector

- [ ] 3.1 Build the table-view entity module
  - `frontend/src/entities/table-view/{types,queries,mutations,index}.ts`
  - TableView type matching migration schema
  - Fetch: listViews, fetchView
  - Mutations: createView, updateView, deleteView, setDefaultView (transactional)
  - _Requirements: 6.1, 6.3, 6.5, 6.6, 6.7, 6.9, 13.3, 13.6_

- [ ] 3.2 Build the save-view dialog
  - Modes: "save as new" + "rename existing"
  - Inline validation for duplicate names
  - _Requirements: 6.3, 6.7, 6.8_

- [ ] 3.3 Build the view selector dropdown
  - Lists personal views for current tableKey
  - Actions: Save as new, Update current (when modified), Delete, Set as default, Clear
  - On select, populates URL from view state via useTableState
  - Auto-loads default view on first mount when URL has no view id
  - _Requirements: 6.1, 6.2, 6.4, 6.9_

- [ ] 3.4 Build the manage-views dialog
  - Rename + delete per view
  - Delete confirmation inline
  - _Requirements: 6.6, 6.7_

---

## 4. DataTable Shell and Integration

- [ ] 4.1 Build the DataTable shell component
  - `frontend/src/shared/ui/data-table/data-table.tsx`
  - Generic `<DataTable<T>>` with rows, columns, pagination, grouping
  - Top bar: search + view selector + column visibility + custom actions slot
  - Row grouping section rendering
  - Row click handler
  - Search debounce 300ms
  - _Requirements: 1.1, 1.2, 1.6, 1.7, 5.3, 5.4, 9.1, 9.2, 9.4, 9.5, 9.6, 10.1, 10.2, 10.3, 10.5_

- [ ] 4.2 Expose the public API of the data-table shared module
  - Barrel `shared/ui/data-table/index.ts` exporting DataTable + types
  - Barrel `shared/lib/data-table/index.ts` exporting hook + helpers
  - Verify no imports from features/ or entities/quote
  - _Requirements: 13.1, 13.2, 13.4, 13.5_

- [ ] 4.3 Extend the quotes query for multi-value filters and range
  - Update `QuotesFilterParams`: status/customer/brand/manager/procurement_manager as arrays, amount __min/__max, sort
  - Multi-value → IN predicates
  - Range → gte/lte predicates
  - Brand/procurement filter → pre-query on quote_items
  - Remove status-group-key expansion
  - _Requirements: 11.3, 12.5, 12.6_

- [ ] 4.4 Extend fetchFilterOptions to include additional lookup values
  - Distinct brands from quote_items
  - All workflow statuses with labels
  - Procurement managers (from quote_items.assigned_procurement_user)
  - Preserve customer + sales manager lookups
  - _Requirements: 10.3_

- [ ] 4.5 Replace the quotes page and quotes-table implementation
  - Quotes page renders DataTable with declared column config
  - "Requires your action" row grouping via predicate
  - Row click → `/quotes/{id}`
  - New KP button in top bar actions slot
  - Remove status pills, legacy dropdowns, status-group helpers
  - Default filter: `status NOT IN (cancelled)`
  - Delete obsolete `quotes-table.tsx`
  - _Requirements: 11.1, 11.2, 11.4, 11.5, 11.6, 12.1, 12.2, 12.3, 12.4, 12.7, 12.8_

---

## 5. Verification

- [ ] 5.1 Write unit tests for the serialization utilities
  - Round-trip parse + serialize for all filter types
  - Canonicalize order-independence
  - Unknown keys silently dropped
  - _Requirements: 8.4, 8.5, 8.6, 8.8_

- [ ] 5.2 Write unit tests for the useTableState hook
  - Page resets on filter change
  - Clear filters preserves sort and visibility
  - isModifiedFromView returns correct boolean
  - _Requirements: 8.2, 6.4_

- [ ] 5.3 Write integration tests for the table-view entity
  - CRUD round-trip
  - Default view enforcement (only one per user+table)
  - Duplicate name rejection
  - RLS isolation between users
  - _Requirements: 6.3, 6.5, 6.8, 6.9, 7.1, 7.7_

- [ ] 5.4 Write browser tests for the quotes registry integration
  - Status pills gone, legacy dropdowns gone
  - Multi-select status filter works
  - Range amount filter works
  - Sort toggles work
  - Save view → load view → modify detection
  - Column visibility persists via localStorage
  - Search debounce + multi-field
  - "Requires your action" grouping preserved
  - Row click navigation
  - _Requirements: 11.1, 11.2, 2.4, 3.2, 4.1, 4.2, 4.3, 6.3, 6.4, 5.2, 5.3, 5.4, 9.2, 9.3, 9.5, 12.2_

- [ ]* 5.5 Write component tests for filter popovers
  - Multi-select search substring match
  - Select all (post-search) behavior
  - Range filter reset on empty inputs
  - _Requirements: 2.2, 2.6, 3.3_
