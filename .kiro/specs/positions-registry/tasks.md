# Implementation Plan

- [x] 1. Create database view for product aggregation
- [x] 1.1 Create the positions registry view migration
  - Write a SQL migration that creates `kvota.positions_registry_view` aggregating quote items by brand + SKU
  - The view deduplicates products, shows the latest entry per group, computes availability status (available/unavailable/mixed), and counts sourcing entries
  - Include a partial index on `quote_items(brand, idn_sku, updated_at)` for view performance
  - Only include items where procurement has completed processing (priced or marked unavailable)
  - Handle null SKU values by coalescing to empty string for grouping
  - Apply the migration to the database via SSH
  - _Requirements: 2.1, 2.3, 2.4, 2.5, 2.7, 2.9_

- [x] 2. Build the position entity layer (types and queries)
- [x] 2.1 (P) Define position entity types
  - Create TypeScript types for the product list item (master level) and sourcing entry (detail level)
  - Include an availability status union type with three values
  - Create the entity barrel export
  - _Requirements: 2.2, 8.1, 8.2_

- [x] 2.2 (P) Implement the data fetch function for positions list
  - Query the database view for paginated, filtered master-level product rows
  - Query quote items directly for detail-level sourcing entries matching products on the current page
  - Fetch distinct brand values and procurement managers in parallel for filter dropdown options
  - Support filtering by availability status, brand, procurement manager, and date range
  - Return master rows, grouped detail entries, total count, and filter options in a single result
  - Join user profiles to resolve procurement manager names in detail entries
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.2, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 5.1_

- [x] 3. Build the positions feature UI components
- [x] 3.1 Create the positions table with filter bar and pagination
  - Render a filter bar with dropdowns for availability status, brand, and procurement manager, plus date range inputs
  - Use native HTML form submission for filters, persisting state in URL search parameters
  - Render the master product table with columns: availability badge, brand, SKU, product name, price with currency, МОЗ name, last updated date, and sourcing entry count
  - Display availability status as colored badges (three distinct variants)
  - Show expand/collapse chevrons for products with multiple sourcing entries
  - Track expanded product state client-side (no server round-trip on toggle)
  - Include pagination controls (previous/next links) preserving filter state
  - Display page info ("Страница X из Y") and total product count
  - Show empty state message when no products match filters
  - Use shadcn/ui Table, Select, Input, Button, and Badge components following design system tokens
  - _Requirements: 2.1, 2.2, 2.4, 2.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4, 6.1, 7.1, 7.2, 7.4_

- [x] 3.2 Create the position history detail component
  - Render an expandable detail section below the parent product row showing all sourcing entries
  - Display each entry with: date, availability indicator, price with currency, МОЗ name, proforma number, and a link to the source quote
  - Mute unavailable entries visually (reduced opacity) and show "Недоступен" instead of price
  - Sort entries by date descending (most recent first)
  - Use a subtly differentiated background to distinguish detail rows from master rows
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.3_

- [x] 3.3 Create the feature barrel export
  - Export the positions table component from the feature index
  - _Requirements: 8.1_

- [x] 4. Create the page route and integrate with sidebar
- [x] 4.1 Create the positions page server component
  - Authenticate the user and verify procurement or admin role access
  - Redirect unauthenticated users to login and unauthorized users to home
  - Parse URL search parameters for filters and pagination
  - Fetch position data using the entity query function
  - Render the page title and positions table component with fetched data
  - _Requirements: 1.2, 1.3, 1.4, 6.2, 8.3_

- [x] 4.2 (P) Add the positions link to the sidebar navigation
  - Add a "Позиции" menu item in the "Реестры" section, positioned after "Поставщики"
  - Gate visibility to procurement and admin roles (same as suppliers)
  - Use an appropriate Lucide icon for the menu item
  - _Requirements: 1.1_

- [x] 5. Error handling and design polish
- [x] 5.1 Handle database errors gracefully
  - Display an error state in the table area when the database query fails
  - Ensure the page remains usable (header, sidebar, filters still visible) even on error
  - _Requirements: 6.2_

- [x] 5.2 Verify design system compliance
  - Confirm all components use design-system.md tokens (font, colors, spacing)
  - Verify badge variants are visually distinct for all three availability statuses
  - Ensure the expandable detail section has proper visual differentiation
  - Confirm the page matches the visual style of other registry pages (suppliers, customers)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.4_
