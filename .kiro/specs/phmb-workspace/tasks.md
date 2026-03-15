# Implementation Plan

- [x] 1. Install Handsontable and extend phmb-quote entity
- [x] 1.1 Install Handsontable React package
  - Run npm install handsontable @handsontable/react in frontend/
  - Verify installation compiles
  - _Requirements: 3.1_

- [x] 1.2 Add workspace types to phmb-quote entity
  - Add interfaces: PhmbQuoteDetail, PhmbQuoteItem, PhmbVersion, PriceListSearchResult, CalcResult
  - Add status union type: "priced" | "waiting"
  - Note: PhmbVersion type skipped — existing quote_versions table lacks PHMB columns. Versioning UI is a placeholder until migration.
  - Note: DB column is `cat_number` (not `catalog_number`), no `unit` column exists in phmb_quote_items or phmb_price_list.
  - _Requirements: 1.1, 3.6_

- [x] 1.3 (P) Add server-side queries for quote detail, items, and versions
  - fetchPhmbQuoteDetail: fetch single quote with customer name join
  - fetchPhmbQuoteItems: fetch all phmb_quote_items for quote, compute status (priced vs waiting based on price fields)
  - fetchPhmbVersions: skipped — quote_versions table lacks PHMB payment term columns
  - _Requirements: 1.1, 6.1_

- [x] 1.4 (P) Add client-side mutations for items, terms, versions, search, calc, and PDF
  - addItemToQuote: insert phmb_quote_item from price list selection
  - updateItemQuantity, updateItemPrice, deleteItem: item CRUD
  - savePaymentTerms: update quote payment terms
  - createVersion: skipped — no PHMB-specific version table. TODO after DB migration.
  - searchPriceList: search phmb_price_list by catalog number or product name (debounce-ready, limit 10)
  - calculateQuote: POST to /api/phmb/calculate, return CalcResult
  - exportPdf: POST to /api/phmb/export-pdf, return Blob for download
  - _Requirements: 2.2, 3.2, 3.5, 5.3, 6.2, 4.3, 8.2_

- [x] 2. Quote workspace page and core components
- [x] 2.1 Create the workspace page server component
  - Auth check (sales/admin), fetch quote detail + items + versions in parallel
  - Redirect to /phmb if quote not found or not is_phmb
  - Pass data to QuoteWorkspace client component
  - _Requirements: 1.5_

- [x] 2.2 Build QuoteWorkspace orchestrator component
  - Header: quote IDN, client name, progress counter "X/Y позиций с ценой"
  - PDF export button in header
  - Renders: VersionPills, ItemSearch, ItemsTable, PaymentTermsPanel
  - Manages state: current items, active version, terms, calc results
  - Coordinates auto-calculation: when items or terms change, call calculateQuote API
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.2, 4.4, 8.1_

- [x] 2.3 Build ItemSearch component
  - Search input with 300ms debounce, min 2 chars
  - Dropdown with search results (catalog number, product name, brand, price if available)
  - On select: call addItemToQuote → add row to table → trigger auto-calc if priced
  - If item has no price: create phmb_procurement_queue entry, mark row as "waiting"
  - Apply brand-type discount from org settings automatically
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2.4 Build ItemsTable with Handsontable
  - Configure Handsontable with columns: article, product name, brand, qty, price RMB, discount, EXW USD, COGS, total price, total with VAT, status
  - Editable: quantity, price RMB
  - Read-only: article, name, brand, discount, all calculated columns
  - Orange background for "waiting" rows (via cells callback + custom CSS)
  - Support: keyboard cell navigation, copy-paste, context menu delete
  - Quote total row at bottom
  - afterChange hook: detect qty/price changes → call updateItemQuantity/Price → trigger auto-calc
  - Style Handsontable to match Slate & Copper design system (custom CSS overrides)
  - Note: `unit` and `purchase_currency` columns don't exist in DB — omitted from table
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.4, 9.2_

- [x] 3. Payment terms, versioning, and export
- [x] 3.1 Build PaymentTermsPanel
  - Collapsible panel (collapsed by default) with 3 fields: advance %, deferral days, markup %
  - Pre-populated from quote values
  - On save: call savePaymentTerms → trigger recalculation of all items
  - Mobile: stack fields vertically (grid-cols-1 sm:grid-cols-3)
  - Uses @base-ui/react Collapsible (not Radix — no asChild)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.3_

- [x] 3.2 Build VersionPills component
  - Placeholder implementation — shows "v1" pill + disabled "+" button
  - TODO: Requires DB migration to add PHMB columns to quote_versions or create phmb_versions table
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 3.3 Implement partial quote and PDF export
  - When items are mixed (priced + waiting): show "КП из N готовых" button
  - PDF button: calls exportPdf → downloads blob as file
  - Both buttons in QuoteWorkspace header
  - _Requirements: 7.1, 7.2, 8.1, 8.2, 8.3_

- [ ] 4. Python API endpoints
- [ ] 4.1 Create POST /api/phmb/calculate endpoint
  - Read quote items and phmb_settings
  - Call phmb_calculator.py calculation logic
  - Update phmb_quote_items with calculated values
  - Return CalcResult JSON
  - Protect with ApiAuthMiddleware (JWT)
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 4.2 (P) Create POST /api/phmb/export-pdf endpoint
  - Read quote detail, items, calculated values
  - Generate PDF using existing PDF generation patterns
  - Return PDF binary
  - Protect with ApiAuthMiddleware (JWT)
  - _Requirements: 8.2, 8.3_
