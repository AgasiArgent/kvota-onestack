# Requirements Document

## Introduction

A reusable DataTable component for the OneStack Next.js frontend that provides Excel-style column-level filtering, column visibility management, saved views, and URL-based state synchronization. The component will replace the current ad-hoc quotes-table implementation and serve as the foundation for all registry pages (customers, positions, suppliers, currency invoices, etc.) in kvotaflow. The component must be framework-consistent (shadcn/Base UI + Feature-Sliced Design), follow OneStack's access-control and database conventions, and be designed for extension to other registries with minimal per-registry code.

**Key principles:**
- **Declarative column configuration** — registries declare their columns, filters, and data sources; the DataTable renders the UI
- **URL as source of truth** — all filter, sort, and view state lives in URL query parameters for shareable links
- **Server-side filtering/pagination** — filters translate into Supabase query predicates, not client-side array operations
- **Saved views in DB** — user-specific named filter/sort/column presets stored in `kvota.user_table_views`, with a forward-compatible schema for organization-shared views
- **No editing** — the DataTable is read-only by design; editing happens on detail pages

**Out of scope (explicitly excluded):**
- Cell editing
- Pivot/grouping operations
- Client-side sorting of server-paginated data
- Shared views UI (schema supports it; UI is future work)
- Role-based column visibility enforcement (schema supports `allowedRoles`; enforcement is future work)

## Requirements

### Requirement 1: Declarative Column Configuration

**Objective:** As a frontend developer integrating a new registry, I want to declare columns as config objects, so that I can wire up a new filterable table in under an hour without reimplementing filter UI, sort logic, or URL handling.

#### Acceptance Criteria

1. The DataTable component shall accept a `columns` prop that is an array of column descriptors, where each descriptor specifies at minimum a unique `key`, a display `label`, and an `accessor` function that returns the cell content for a row.
2. Where a column descriptor declares a `filter` of kind `multi-select`, the DataTable shall render a filter popover on that column header with a searchable checkbox list of values.
3. Where a column descriptor declares a `filter` of kind `range`, the DataTable shall render a min/max numeric input popover on that column header.
4. Where a column descriptor declares `sortable: true`, the DataTable shall render a sort toggle on the column header that cycles through ascending, descending, and unsorted states.
5. Where a column descriptor declares an `allowedRoles` array, the DataTable shall store this metadata unchanged (enforcement is future work) and expose it via the public column type.
6. The DataTable shall accept a generic row type `T` via TypeScript generics, ensuring `accessor` functions are type-safe against the row shape.
7. The DataTable shall accept an `onRowClick` callback and invoke it with the row data when the user clicks on a row.

### Requirement 2: Multi-Select Column Filters with Search

**Objective:** As a procurement manager, I want to filter a column by selecting multiple specific values from a searchable checkbox list, so that I can quickly narrow the quotes table to exactly the brands, clients, or statuses I care about.

#### Acceptance Criteria

1. When the user clicks a column filter trigger, the DataTable shall open a popover containing a search input, a scrollable checkbox list of distinct values for that column, and apply/reset controls.
2. When the user types in the popover search input, the DataTable shall filter the checkbox list client-side by case-insensitive substring match on the value labels.
3. When the user toggles a checkbox, the DataTable shall update the local popover state without immediately applying the filter to the URL.
4. When the user clicks the apply control, the DataTable shall serialize the selected values into the URL query parameter for that column using a comma-separated format (e.g., `?status=draft,pending_procurement`) and trigger a re-fetch.
5. When the user clicks the reset control in the popover, the DataTable shall clear only that column's filter from the URL and trigger a re-fetch.
6. When the user clicks the "select all" control, the DataTable shall toggle between selecting all currently visible values (post-search) and clearing them.
7. While any column has one or more values selected, the DataTable shall render the filter trigger on that column in an active visual state (e.g., highlighted icon plus a count badge).
8. If a column's filter has no selected values, the DataTable shall treat the column as unfiltered and shall not include its parameter in the URL.
9. When the DataTable re-fetches data with active filters, it shall translate each multi-select filter into an `IN` predicate on the corresponding database column or foreign-key relationship.

### Requirement 3: Numeric Range Column Filters

**Objective:** As a sales manager, I want to filter the amount column by a min/max range, so that I can find quotes within a specific monetary bracket.

#### Acceptance Criteria

1. When the user clicks the filter trigger on a range-filtered column, the DataTable shall open a popover containing two numeric inputs labeled for minimum and maximum values.
2. When the user enters values and clicks apply, the DataTable shall serialize both values into the URL using a suffixed parameter format (e.g., `?amount__min=1000&amount__max=50000`).
3. If only one of the two range bounds is provided, the DataTable shall apply an open-ended range (e.g., "greater than or equal to min" with no upper bound).
4. When the DataTable re-fetches data with a range filter active, it shall translate it into `gte` and/or `lte` predicates on the target database column.
5. When the user clicks reset on a range filter, the DataTable shall remove both the min and max parameters from the URL.

### Requirement 4: Column Sorting

**Objective:** As any user, I want to sort the table by clicking a column header, so that I can order results by date, amount, or any other sortable field in ascending or descending order.

#### Acceptance Criteria

1. When the user clicks a sortable column header for the first time, the DataTable shall apply ascending sort on that column and update the URL with `?sort=<column_key>`.
2. When the user clicks the same sortable column header a second time, the DataTable shall switch to descending sort and update the URL to `?sort=-<column_key>`.
3. When the user clicks the same sortable column header a third time, the DataTable shall remove the sort parameter from the URL and return to the default sort order.
4. While a column is the active sort column, the DataTable shall render an appropriate ascending or descending arrow icon on that column header.
5. While no column is the active sort column, the DataTable shall render an idle sort icon (bidirectional arrow, visually dimmed) on every sortable column header.
6. When sorting is applied to a column whose `sortKey` differs from its `key`, the DataTable shall use the `sortKey` value as the database column name in the order-by clause.
7. The DataTable shall support only one active sort column at a time; clicking a new column shall replace the previous sort, not stack sorts.

### Requirement 5: Column Visibility Management

**Objective:** As a user on a narrow screen or with a role-specific workflow, I want to hide columns I do not need, so that the table remains readable and focused on my task.

#### Acceptance Criteria

1. The DataTable shall render a column-visibility control in its top bar that, when clicked, opens a popover listing all columns defined in the column config.
2. When the user toggles a column's visibility checkbox in the popover, the DataTable shall immediately hide or show that column without reloading data.
3. While no saved view is active, the DataTable shall persist the user's column-visibility choices to browser local storage under a key that includes the `tableKey` prop.
4. While a saved view is active, the DataTable shall read column visibility from the view's `visible_columns` field and shall not write to local storage.
5. When the user loads the page for the first time with no saved preferences, the DataTable shall show every column marked as `defaultVisible: true` in the column config (or all columns if `defaultVisible` is not specified).
6. If the column config changes between sessions and a stored visibility preference references a removed column, the DataTable shall silently ignore the stale entry and continue with the remaining valid columns.

### Requirement 6: Saved Views — Personal CRUD

**Objective:** As a user who works with the same filter combination repeatedly, I want to save, load, rename, and delete named filter/sort/column presets, so that I can switch between my working contexts in one click.

#### Acceptance Criteria

1. The DataTable shall render a view-selector dropdown in its top bar that lists a default "All" view plus all personal views owned by the current user for the current `tableKey`.
2. When the user selects a view from the dropdown, the DataTable shall populate the URL query parameters from the view's `filters`, `sort`, and `visible_columns` fields and trigger a re-fetch.
3. When the user clicks "Save as new view" from the dropdown, the DataTable shall prompt for a name and shall create a new row in `kvota.user_table_views` with the current URL state, associated to the current user and `tableKey`.
4. When a view is already active and the user has modified filters such that the URL state diverges from the view's stored state, the DataTable shall render both "Save as new" and "Update current" actions in the view menu.
5. When the user selects "Update current", the DataTable shall overwrite the active view's `filters`, `sort`, and `visible_columns` with the current URL state.
6. When the user deletes a view from the view management dialog, the DataTable shall remove the corresponding row from `kvota.user_table_views` and, if the deleted view was active, shall reset the URL to an unfiltered default.
7. The DataTable shall allow the user to rename a personal view via the view management dialog, updating the `name` field in the database.
8. If the user attempts to save or rename a view using a name that already exists for the same user and `tableKey`, the DataTable shall display an inline validation error and shall not submit.
9. While a view is marked as the user's default (`is_default: true`), the DataTable shall load that view automatically on first page mount when no `?view=` parameter is in the URL.

### Requirement 7: Saved Views — Shared Views Schema Support

**Objective:** As a system architect planning future organization-wide shared views, I want the database schema to support shared views from day one, so that adding shared-views UI later does not require another migration.

#### Acceptance Criteria

1. The `kvota.user_table_views` table shall include an `is_shared BOOLEAN` column defaulting to `false`.
2. The `kvota.user_table_views` table shall include an `organization_id UUID` column that is nullable for personal views and populated for shared views.
3. The database shall enforce uniqueness of `(user_id, table_key, name)` for personal views and `(organization_id, table_key, name)` for shared views via separate partial unique indexes.
4. The DataTable shall fetch personal views for the current user and shall not fetch shared views in this release.
5. The DataTable view-selector shall expose the data model such that adding shared-views support later requires only a fetch-query change and optional UI grouping, not a schema migration.
6. While a view has `is_shared: true`, the database row-level security policies shall allow SELECT for any user in the same `organization_id` and shall restrict UPDATE/DELETE to the original `user_id`.
7. The `kvota.user_table_views` table shall enable row-level security, with personal views accessible only by their `user_id` owner.

### Requirement 8: URL State Synchronization

**Objective:** As a user sharing a filtered view with a colleague, I want the full filter state captured in the URL, so that pasting the URL into another user's browser reproduces the same filtered table.

#### Acceptance Criteria

1. The DataTable shall read initial filter, sort, and view-id state from the URL query parameters on mount.
2. When a filter, sort, column-visibility, or view selection changes, the DataTable shall update the URL without a full page reload.
3. When the user navigates via browser back/forward buttons, the DataTable shall re-render with the state corresponding to the target URL.
4. The DataTable shall use comma-separated values for multi-select filters (e.g., `status=a,b,c`).
5. The DataTable shall use double-underscore suffixes for range filters (e.g., `amount__min=100&amount__max=5000`).
6. The DataTable shall use a leading minus sign to indicate descending sort (e.g., `sort=-amount` vs `sort=amount`).
7. When the URL contains a `?view=<uuid>` parameter on first load, the DataTable shall load that view and populate the remaining URL parameters from the view's stored state.
8. If a URL parameter references a filter column that does not exist in the current column config, the DataTable shall silently ignore it without throwing an error.

### Requirement 9: Search Input and Action Row Grouping

**Objective:** As a user scanning a list of quotes, I want a global search across key fields and a visually distinct section highlighting quotes that need my attention, so that I see my priority work first and can quickly find specific entities.

#### Acceptance Criteria

1. The DataTable shall accept an optional `searchConfig` prop describing which fields to search and an optional `searchPlaceholder` string.
2. When the user types in the search input, the DataTable shall debounce input by approximately 300 milliseconds before updating the URL with `?search=<term>`.
3. When a search term is set, the DataTable shall translate it into multi-field search predicates on the database query according to the consumer's configuration (e.g., for quotes: KP number, customer name, brand).
4. The DataTable shall accept an optional `rowGrouping` prop specifying a predicate function and a group label.
5. Where a row grouping is provided, the DataTable shall render matching rows above a "remaining rows" section with a visually distinct header for the action group.
6. When no rows match the grouping predicate, the DataTable shall render all rows in a single ungrouped list without the action header.

### Requirement 10: Filter Options Data Source

**Objective:** As a developer integrating a new registry, I want to declare how filter options (the list of distinct values for multi-select filters) are fetched, so that my registry can load the correct options without hardcoding queries in the DataTable.

#### Acceptance Criteria

1. The DataTable shall accept a `filterOptions` prop that is an object mapping column keys to arrays of `{ value, label }` pairs.
2. Where a column's filter type is `multi-select`, the DataTable shall read that column's options from the `filterOptions` prop and render them in the filter popover.
3. The consuming page shall be responsible for fetching filter options server-side and passing them to the DataTable as props.
4. When `filterOptions` does not contain an entry for a multi-select column, the DataTable shall render an empty filter popover with a message indicating no options are available.
5. The DataTable shall not refetch filter options when the user applies a filter; filter options are considered a static lookup for the lifetime of the page.

### Requirement 11: Remove Status Pills and Group-Key Concept

**Objective:** As a user of the quotes registry, I want a single consistent filter surface on column headers, so that I do not see duplicate filter controls for status and can use the same pattern across all columns.

#### Acceptance Criteria

1. The quotes registry page shall not render the current status-group pill row above the table.
2. The quotes registry page shall not render the legacy "Все клиенты / Все менеджеры / Все МОЗ" top-bar dropdowns; filtering for these columns shall happen exclusively through the column-header filter popovers.
3. The `fetchQuotesList` query shall no longer interpret `?status=<group_key>` as a group expansion; the status parameter shall accept only literal workflow status values (optionally comma-separated).
4. The quotes registry page shall retain a general search input in the top bar above the table.
5. The quotes registry page shall retain the "Новый КП" action button in the top bar.
6. When a user lands on `/quotes` without any filters, the DataTable shall apply a default filter excluding the `cancelled` status and shall show all other quotes.

### Requirement 12: Integration with Existing Quotes Registry

**Objective:** As the maintainer of the quotes registry, I want the new DataTable to replace the current quotes-table.tsx with no loss of existing functionality, so that users experience only improvements with no regressions.

#### Acceptance Criteria

1. The quotes registry page shall render a DataTable instance wired to the existing `fetchQuotesList` query function with columns for Date, KP Number, Client, Brands, Sales Manager (МОП), Status, Procurement Manager (МОЗ), Version, Amount, and Profit.
2. When the user clicks a quote row, the DataTable shall navigate to `/quotes/{id}` using the Next.js router.
3. The quotes registry shall continue to respect existing access control rules (`fetchQuotesList` role-based filtering) without modification to access logic.
4. The quotes registry shall preserve the existing "Requires your action" row grouping for statuses that match the current user's role.
5. When the user selects a value in the Client filter, the DataTable shall include only quotes whose `customer_id` is in the selected list, matching the behavior of the current client dropdown filter.
6. When the user selects a value in the Procurement Manager filter, the DataTable shall include only quotes that have at least one item with `quote_items.assigned_procurement_user` matching the selected user, consistent with the current MOZ filter semantics.
7. The quotes registry page's pagination controls shall continue to function unchanged, with the current page count and total count rendered above the table.
8. The quotes registry's filter state shall be reflected in the URL with parameter names consistent with the new DataTable conventions (multi-value comma-separated, range suffixed).

### Requirement 13: Component Placement and Public API

**Objective:** As a developer maintaining the shared UI library, I want the DataTable to live in the shared layer with a clear public API, so that any feature can import it without creating cross-feature dependencies.

#### Acceptance Criteria

1. The DataTable component and its subcomponents shall be located in `frontend/src/shared/ui/data-table/`.
2. The DataTable's supporting hooks and utilities shall be located in `frontend/src/shared/lib/data-table/`.
3. The saved views entity (types, queries, mutations) shall be located in `frontend/src/entities/table-view/`.
4. The shared DataTable directory shall export only its intended public API (`DataTable`, column type helpers, hook utilities) through an `index.ts` barrel file.
5. The DataTable shall not import from any `features/` or `entities/quote/` modules to preserve Feature-Sliced Design layer boundaries.
6. The entities/table-view module shall expose CRUD functions as its public API and shall not leak internal Supabase query details.
