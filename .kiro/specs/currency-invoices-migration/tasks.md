# Implementation Plan

- [ ] 1. Currency invoice entity layer
- [ ] 1.1 Define types and fetch functions
  - CurrencyInvoice, CurrencyInvoiceItem, CurrencyInvoiceDetail interfaces
  - fetchCurrencyInvoices(orgId, filters) — flat list with FK joins to deals→specs→quotes for IDN/customer
  - fetchCurrencyInvoiceDetail(id, orgId) — single invoice with items and company options
  - fetchCompanyOptions(orgId) — seller and buyer company lists for dropdowns
  - _Requirements: 1.1, 1.6, 2.1, 2.4_

- [ ] 1.2 Define mutation functions
  - saveCurrencyInvoice(id, orgId, data) — update seller/buyer/markup, recalculate item prices
  - verifyCurrencyInvoice(id, orgId) — transition to verified status
  - regenerateCurrencyInvoice(id, orgId) — delete and recreate from source items (calls Python API)
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 2. Registry page
- [ ] 2.1 Build /currency-invoices list page
  - Server component with auth + role check (admin, currency_controller, finance)
  - Redirect to /quotes if unauthorized
  - Flat table with segment/status filters via form method="GET"
  - Segment badges (EURTR blue, TRRU purple), status badges (draft/verified/exported)
  - Quote IDN + customer name from deal chain
  - Pagination
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 4.1, 4.2_

- [ ] 3. Detail page
- [ ] 3.1 Build /currency-invoices/[id] detail page
  - Server component fetching invoice detail + company options
  - Header: invoice number, segment badge, status badge, date, currency, back-link to deal
  - Company selectors (seller/buyer dropdowns) — no "Текущий:" labels
  - Editable markup % with recalculation note
  - Positions table with all columns including totals
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 3.2 (P) Add action buttons with proper hierarchy
  - Primary: "Сохранить" button
  - Secondary: "Подтвердить" button (disabled if no seller/buyer)
  - Dropdown menu: "Пересоздать из источника" (admin/currency_controller only), "Экспорт DOCX", "Экспорт PDF"
  - Disable editing when status is verified/exported
  - Export calls Python API endpoints (existing /currency-invoices/{id}/download-docx and download-pdf)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
