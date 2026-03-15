# Implementation Plan

- [x] 1. PHMB quote entity layer
- [x] 1.1 Define TypeScript interfaces for PHMB quote data models
  - Create interfaces: PhmbQuoteListItem (with computed status), CreatePhmbQuoteInput (6 fields), PhmbDefaults, SellerCompany, CustomerSearchResult, PhmbQuoteStatus union type
  - Export from barrel file
  - _Requirements: 1.1, 1.4, 3.2, 3.5_

- [x] 1.2 (P) Implement server-side query for PHMB quotes list with computed status
  - Fetch quotes where is_phmb=true for the organization, with customer name join
  - Compute status per quote via subquery: count total phmb_quote_items vs priced items (where purchase_price is not null)
  - Support search (client name or IDN ilike), status filter, and pagination (20 per page)
  - Return total count for pagination
  - Also implement fetchPhmbDefaults (from phmb_settings) and fetchSellerCompanies queries
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 3.3_

- [x] 1.3 (P) Implement client-side mutations for quote creation and customer search
  - createPhmbQuote: insert into quotes with is_phmb=true and payment terms, return new quote ID
  - searchCustomers: debounce-ready query searching customers by name ilike, returning id + name + inn, limited to 10 results
  - _Requirements: 3.4, 3.5_

- [x] 2. PHMB registry page and components
- [x] 2.1 Create the PHMB page server component with role-based access
  - Auth check: require login, verify sales or admin role, redirect unauthorized to dashboard
  - Read search/status/page from URL searchParams
  - Fetch quotes list, defaults, and seller companies in parallel
  - Pass all data to PhmbRegistry client component
  - _Requirements: 5.3, 5.4, 5.5_

- [x] 2.2 Build the registry table with search, status filter, and pagination
  - Render table with 6 columns: date, IDN, client, items progress (X/Y format), amount, status
  - Status badges: draft (gray), waiting_prices (amber), ready (green)
  - Search input that filters by client name or IDN
  - Status filter dropdown (all, draft, waiting, ready)
  - Pagination controls at bottom
  - Sync search/status/page with URL query params
  - Empty state with icon, text, and CTA button when no quotes exist
  - Row click navigates to /phmb/[id]
  - On mobile: hide amount column, condensed layout
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 6.1, 6.2_

- [x] 2.3 Build the create PHMB quote dialog with customer typeahead
  - Dialog with 6 fields: customer (typeahead), currency (select), seller company (select), advance %, deferral days, markup %
  - Customer typeahead: debounced input (300ms, min 2 chars) with dropdown showing name + INN
  - Pre-populate advance %, deferral days, markup % from organization phmb_settings defaults
  - On submit: create quote, redirect to /phmb/[id]
  - Loading state on submit button, error toast on failure
  - On mobile: render as full-screen sheet instead of centered dialog
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 6.3_

- [x] 3. Sidebar integration
- [x] 3.1 Add PHMB link to sidebar navigation
  - Add "PHMB" link in the Реестры section of the sidebar
  - Visible only for users with sales or admin roles
  - Use appropriate icon from Lucide
  - _Requirements: 5.1, 5.2_
