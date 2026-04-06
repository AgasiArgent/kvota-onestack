# Implementation Plan

- [x] 1. Set up TanStack React Table and scaffold the new feedback list
- [x] 1.1 Install TanStack React Table and define column configuration
  - Add `@tanstack/react-table` dependency to the frontend project
  - Define column definitions for the feedback table: checkbox, ID, type badge, description (truncated), user, status dropdown, ClickUp link, date
  - Configure the table instance with expand model (single-row mode) and row selection model
  - Preserve existing `FeedbackListProps` interface for backward compatibility with the page shell
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 3.1, 3.2, 5.1, 5.2, 5.3_

- [x] 1.2 Render the TanStack table using existing shadcn Table components
  - Replace the current plain `<Table>` rendering with TanStack-driven rows and cells
  - Map TanStack header groups to `<TableHeader>` / `<TableHead>` and rows to `<TableBody>` / `<TableRow>` / `<TableCell>`
  - Add click handler on rows to toggle expansion (skip clicks on interactive elements)
  - Add keyboard handler (Enter/Space) on focused rows to toggle expansion
  - Ensure the empty state ("Нет обращений" with filter reset link) still renders when no items exist
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 5.3_

- [x] 2. Build the expanded row detail panel
- [x] 2.1 (P) Create the expanded row component with feedback detail content
  - Build a component that renders inside a full-width table cell spanning all columns
  - Display: sender info (name + email), page URL as a link, full description text, screenshot with lightbox (reuse Dialog pattern), collapsible debug context, ClickUp external link
  - Fetch full detail data for the expanded row (the list query only returns summary fields — the expanded view needs `page_url`, `screenshot_url`, `debug_context`)
  - Do not include a status change card — status is handled inline in the table column
  - _Requirements: 1.1, 1.5_

- [x] 2.2 (P) Update entity query to support detail fetching for expanded rows
  - The list query returns `FeedbackItem` (summary fields). The expanded row needs `FeedbackDetail` fields (`page_url`, `screenshot_url`, `debug_context`)
  - Add a client-side query function to fetch a single feedback detail by `short_id` for use in the expanded row
  - Show a loading skeleton while the detail is being fetched
  - _Requirements: 1.1, 1.5_

- [x] 3. Implement inline status change with optimistic updates
- [x] 3.1 Replace the status badge with an inline dropdown in the status column
  - Render a Select component in the status column cell instead of a static badge
  - Stop event propagation on the Select to prevent triggering row expansion
  - Display status options: Новое, В работе, Решено, Закрыто
  - _Requirements: 2.1, 2.4_

- [x] 3.2 Add optimistic update logic for single status changes
  - On status selection, immediately update the displayed status in local state
  - Call the existing `updateFeedbackStatus` mutation in the background
  - On success, keep the new status and optionally show a subtle success indicator
  - On failure, revert to the previous status and show an error toast notification
  - _Requirements: 2.2, 2.3_

- [x] 4. Implement bulk status change with selection toolbar
- [x] 4.1 Wire up checkbox selection and render the bulk action toolbar
  - Enable the checkbox column with header-level select-all (current page only)
  - When one or more rows are selected, display a toolbar between the filter tabs and the table
  - Toolbar shows: selected count label, a status dropdown, an "Apply" button (disabled until a status is chosen), and a "Clear selection" text button
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4.2 Add the bulk status mutation and connect it to the toolbar
  - Create a new `bulkUpdateFeedbackStatus` function that updates multiple rows by `short_id` in a single Supabase call
  - On "Apply" click: call the bulk mutation with all selected `short_id` values and the chosen status
  - On success: clear selection, refresh page data, show success toast with count
  - On failure: show error toast, keep selection intact for retry
  - _Requirements: 3.5, 3.6, 3.7_

- [x] 5. Add configurable page size with URL persistence
- [x] 5.1 (P) Update the server query to accept a dynamic page size
  - Modify `fetchFeedbackList` to accept an optional `pageSize` parameter (default: 50)
  - Remove the hardcoded `FEEDBACK_PAGE_SIZE = 20` constant
  - Update the page shell to read `pageSize` from URL search params and pass it to the query
  - _Requirements: 4.2, 4.4_

- [x] 5.2 Add a page size selector next to pagination controls
  - Render a small Select component with options 25, 50, 100 near the existing pagination
  - On change: update the `pageSize` URL parameter via `useFilterNavigation`, which auto-resets to page 1
  - Clear any active row selection when page size changes
  - Validate the `pageSize` param — if invalid or missing, default to 50
  - _Requirements: 4.1, 4.3, 4.5_

- [x] 6. Integration verification and re-export
- [x] 6.1 Wire everything together and verify preserved functionality
  - Update the barrel export in `features/admin-feedback/index.ts` to include any new exports
  - Verify filter tabs, search input, ClickUp links, and pagination all work as before
  - Verify the standalone detail page at `/admin/feedback/[id]` is unaffected
  - Confirm that selecting rows, expanding a row, changing inline status, and bulk updating all work together without conflicts
  - _Requirements: 5.1, 5.2, 5.3, 5.4_
