# Implementation Plan

- [ ] 1. Quote entity data layer
- [ ] 1.1 Define quote list types and status group configuration
  - Create the QuoteListItem, QuotesFilterParams, and QuotesListResult types for the quotes registry
  - Define the STATUS_GROUPS constant mapping all 14 workflow statuses into 5 categories (Draft, In Progress, Approval, Deal, Closed) with Russian labels and Tailwind color classes
  - Include a helper to resolve a status group key into its constituent workflow_status values
  - Ensure all 14 statuses are covered with no gaps or duplicates
  - _Requirements: 1.1, 2.1_

- [ ] 1.2 Implement quotes list fetch function with role-based visibility
  - Build a server-side function that queries kvota.quotes with FK joins to customers and profiles
  - For sales/sales_manager roles: filter to quotes where user is creator OR customer's manager_id matches user
  - For admin/top_manager/head_of_sales and all other roles: return all organization quotes
  - Apply optional filters: status group (expand to individual statuses via config), customer UUID, manager UUID
  - Support pagination with configurable page size (default 20) and return total count
  - Include quote version count via quote_versions join
  - _Requirements: 1.1, 1.6, 4.1, 4.2, 4.3_
  - _Contracts: fetchQuotesList Service Interface_

- [ ] 2. Status group filter component
- [ ] 2.1 (P) Build status group pill filter with optional detail expansion
  - Render 5 clickable pill buttons, one per status group, using colors from the config
  - Highlight the active group; clicking the same group again deselects it (shows all)
  - When a group is active, show an expand chevron that reveals individual status sub-pills for granular filtering
  - Selecting an individual status adds it as a separate URL param
  - Include a "Reset" action that clears both group and individual status selections
  - Works as form inputs (hidden fields) compatible with the form method="GET" pattern
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 3. Quotes registry table component
- [ ] 3.1 Build the quotes table with all 8 columns and row interactions
  - Render a table with columns: created date, IDN (quote number), customer name, manager name, status badge, version indicator, total amount, profit USD
  - Format dates in locale-appropriate short form, money with Intl.NumberFormat and currency, profit colored green/red/muted by sign
  - Status badge uses color from STATUS_GROUPS config matching the quote's workflow_status
  - Version indicator: plain "v{N}" for single version, styled pill "v{N} ({total})" for multiple
  - Clicking a row navigates to the quote detail page
  - Clicking the customer name cell navigates to the customer detail page without triggering row navigation
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 3.2 Add customer and manager filter dropdowns
  - Add a customer dropdown filter populated from the unique customers in the current result set
  - Add a manager dropdown filter populated from active managers — visible only to admin, top_manager, and head_of_sales roles
  - Hide the manager filter for sales and sales_manager users
  - All filters (status group, customer, manager) combine as AND conditions
  - Filters submit via form method="GET" so values persist in URL query params
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.1_

- [ ] 3.3 Add pagination controls
  - Display page navigation below the table when total exceeds page size
  - Pagination links preserve current filter params in the URL
  - Default page size of 20 results
  - Show empty state message "Нет коммерческих предложений" when no quotes match filters, with a suggestion to reset filters
  - _Requirements: 1.6, 7.1_

- [ ] 4. Quotes page server component and assembly
- [ ] 4.1 Build the quotes page server component with data loading
  - Create the /quotes page as a server component that reads searchParams for filters and pagination
  - Authenticate user via getSessionUser(), extract roles and org_id
  - Call fetchQuotesList with parsed filter params and user context
  - Fetch distinct customer and manager lists for filter dropdowns
  - Pass all data to the QuotesTable client component
  - Render page header with title "Коммерческие предложения"
  - _Requirements: 1.1, 4.1, 4.2, 4.3, 7.2, 7.3_

- [ ] 4.2 Wire the create quote dialog into the page
  - Show "Новый КП" button in the page header for users with sales, sales_manager, or admin role
  - Clicking the button opens the existing CreateQuoteDialog component
  - On successful creation, navigate to the new quote's detail page
  - Hide the button entirely for users without the required roles
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 5. (P) Routing and navigation changes
- [ ] 5.1 (P) Update redirects to make /quotes the landing page
  - Change root page redirect from /dashboard to /quotes
  - Replace dashboard page content with a redirect to /quotes
  - Verify the post-login auth callback redirects to /quotes
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 5.2 (P) Verify sidebar highlights correctly for /quotes
  - Confirm "Коммерческие предложения" item in the sidebar menu has href="/quotes"
  - Verify the active state detection highlights it when the user is on /quotes
  - Ensure the sidebar "Новый КП" link still works alongside the page-level create button
  - _Requirements: 6.4_
