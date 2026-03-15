# Implementation Plan

- [x] 1. Settings entity layer (types, queries, mutations)
- [x] 1.1 Define TypeScript interfaces for all settings data models
  - Create interfaces for organization info, calculation settings, PHMB settings, brand discounts, brand groups, and the composite page data object
  - Include all fields matching the existing database columns
  - Export all types from the entity barrel file
  - _Requirements: 1.3, 2.1, 3.1, 4.1_

- [x] 1.2 (P) Implement server-side query to fetch all settings data
  - Create a single function that fetches organization name, calculation settings, PHMB settings, brand discounts, and brand groups in parallel
  - Use the server-side Supabase client with kvota schema
  - Return null for settings that don't exist yet (first-time setup)
  - Scope all queries by organization ID
  - _Requirements: 1.3, 2.1, 3.1, 4.1, 6.4_

- [x] 1.3 (P) Implement client-side mutations for all settings operations
  - Upsert calculation settings (3 rate fields) for the organization
  - Upsert PHMB settings (all overhead + default fields) for the organization
  - Update a single brand discount percentage by ID
  - Delete a brand discount by ID
  - Create a new brand group with a name for the organization
  - Delete a brand group by ID
  - Use the browser-side Supabase client with kvota schema
  - _Requirements: 2.2, 3.6, 4.4, 4.5, 4.6, 4.7_

- [x] 2. Settings page shell with authentication and tab navigation
- [x] 2.1 Create the settings page server component with admin-only access
  - Verify authentication via session user; redirect to login if not authenticated
  - Check the user has "admin" role; redirect to dashboard if unauthorized
  - Read the organization ID from the user's profile
  - Fetch all settings data using the entity query
  - Pass data and the selected tab (from URL search params, default "calc") to the client component
  - _Requirements: 1.4, 1.5, 6.1, 6.2, 6.3, 6.4_

- [x] 2.2 Build the tabbed container component with URL-synced navigation
  - Render three tabs: "Расчёты", "Наценки PHMB", "Скидки по брендам"
  - Display the organization name as read-only text in the page header
  - Switch tab content without full page reload using client-side state
  - Persist the selected tab in the URL query parameter (e.g., ?tab=phmb) so direct links and browser navigation work
  - On mobile (below 768px), render tabs as a horizontally scrollable row
  - Follow design system tokens (Slate & Copper palette, Plus Jakarta Sans font)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.4_

- [x] 3. Calculation rates tab (Расчёты)
- [x] 3.1 Build the calculation rates form with save functionality
  - Display three editable numeric fields: forex risk %, financial commission %, and daily loan interest rate %
  - Pre-populate fields from existing settings or show empty for first-time setup
  - On save: disable the button, show loading state, call the upsert mutation, then show a success or error toast
  - On mobile, stack fields in a single column with full-width save button
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.2, 5.3_

- [x] 4. PHMB overhead costs tab (Наценки PHMB)
- [x] 4.1 Build the PHMB form with live percentage preview and markup calculator
  - Display the base pallet price prominently at the top with explanatory label about its role as the common denominator
  - Show overhead cost fields in a left column: logistics per pallet, customs handling, warehouse (SVH), bank expenses, insurance %, and other expenses
  - Next to each absolute cost field, display the live-calculated percentage (cost / base price * 100), updating in real-time as values change
  - Show default value fields in a right column: markup %, advance %, payment days, and delivery days
  - Include a bidirectional markup ↔ margin calculator that recalculates when either value changes
  - On save: upsert all PHMB fields with loading state and toast feedback
  - Two-column layout on desktop, single-column on mobile with full-width save button
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 5.2, 5.3_

- [x] 5. Brand discounts tab (Скидки по брендам)
- [x] 5.1 Build the brand discount table with search and inline editing
  - Display a table with columns: brand, classification, and discount %
  - Add a search input that filters rows by brand name in real-time (client-side)
  - On edit icon click, switch the discount % cell to an editable input field
  - Save inline edits on Enter or blur; cancel on Escape
  - Optimistically update local state on save; revert if the mutation fails
  - On delete icon click, show a confirmation dialog then remove the record
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 5.2 Build the brand groups management section
  - Display existing brand groups below the discount table with group name, brand count, and a delete action per group
  - Provide an "Добавить группу" button that opens an inline form to create a new brand group
  - On delete, show confirmation then remove the group
  - _Requirements: 4.6, 4.7_

- [x] 6. Integration and sidebar navigation
- [x] 6.1 Wire the settings page into the application sidebar and verify end-to-end flow
  - Add "Настройки" link to the sidebar under the Администрирование section, visible only for admin role
  - Verify the complete flow: login as admin → sidebar → settings → switch tabs → edit → save → toast confirmation
  - Verify non-admin users cannot access the page (redirect to dashboard)
  - Verify mobile responsive behavior across all three tabs
  - _Requirements: 1.1, 1.5, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2_
