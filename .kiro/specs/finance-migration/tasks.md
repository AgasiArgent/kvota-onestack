# Implementation Plan

- [ ] 1. Finance entity layer
- [ ] 1.1 Define types and queries for deals, payments, supplier invoices
  - DealListItem, PaymentRecord, SupplierInvoiceListItem interfaces
  - fetchDeals(orgId, filters) — deals with spec/quote/customer joins + ERPS payment aggregates
  - fetchPayments(orgId, filters) — plan_fact_items with deal/customer joins, Russian stage labels
  - fetchSupplierInvoices(orgId, filters) — supplier_invoices with pagination
  - Stage key label map: first_mile→Первая миля, hub→Хаб, last_mile→Последняя миля, etc.
  - _Requirements: 1.1, 1.2, 2.1, 2.3, 3.1_

- [ ] 2. Deals tab (merged Workspace + ERPS)
- [ ] 2.1 Build deals table with view toggle
  - Summary cards (count + total per status)
  - Status filter pills (Все/В работе/Завершённые/Отменённые)
  - Table with base columns + togglable ERPS columns (Компактный/Расширенный)
  - Row click → legacy app deal detail
  - Export button → legacy endpoint
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [ ] 3. Payments tab
- [ ] 3.1 Build payments table with filters
  - Grouping toggle (По записям/По клиентам)
  - Type pills (Все/Приход/Расход), Status pills (Все/План/Оплачено/Просрочено)
  - Date range inputs
  - Table with human-readable labels (no raw DB keys)
  - Footer with totals
  - Pagination
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 4. Supplier Invoices tab
- [ ] 4.1 (P) Build supplier invoices table
  - Table with №, номер, поставщик, дата, сумма, валюта, статус
  - Footer with currency totals
  - Pagination
  - Row click → legacy app
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 5. Page shell and routing
- [ ] 5.1 Build /finance page with 3 tabs
  - Server component with auth + role check
  - 3 tabs: Сделки (default), Платежи, Инвойсы поставщиков
  - Tab state in URL params (?tab=deals|payments|invoices)
  - Redirect unauthorized users to /quotes
  - _Requirements: 4.1, 4.2_
