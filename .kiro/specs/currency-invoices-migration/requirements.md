# Requirements Document

## Introduction
Migrate /currency-invoices (list + detail) from FastHTML to Next.js. Currency invoices are internal invoices between group companies in multi-segment supply chains (EURTR: EU→Turkey, TRRU: Turkey→Russia). Auto-generated when deals are signed. UX improvements: flat list with filters (no empty group noise), streamlined action buttons on detail page.

## Requirements

### Requirement 1: Currency Invoice Registry
**Objective:** As a finance user, I want a flat list of all currency invoices with filters, so that I can find and manage invoices efficiently.

#### Acceptance Criteria
1. The CI Page shall display a flat table with columns: date, invoice number (link), segment badge (EURTR/TRRU), seller company, buyer company, amount, currency, status badge.
2. The CI Page shall provide filters: status (draft/verified/exported), segment (EURTR/TRRU).
3. When filters are active, the CI Page shall filter the table accordingly and persist filters in URL params.
4. When a user clicks an invoice row, the CI Page shall navigate to the detail page.
5. The CI Page shall paginate with default page size of 20.
6. The CI Page shall show the related quote IDN and customer name in each row (from the deal→spec→quote chain).

### Requirement 2: Currency Invoice Detail
**Objective:** As a finance user, I want to view and edit invoice details including company assignments and markup.

#### Acceptance Criteria
1. The Detail Page shall display: invoice number, segment badge, status badge, creation date, currency, link back to deal.
2. The Detail Page shall show seller and buyer company selectors (dropdowns) without redundant "Текущий:" labels.
3. The Detail Page shall show an editable markup percentage field with a note that changing it recalculates all item prices.
4. The Detail Page shall display a positions table with columns: #, product name, SKU, IDN-SKU, manufacturer, quantity, unit, HS code, base price, price (with markup), total.
5. The Detail Page shall show the invoice total (sum of all line items).

### Requirement 3: Invoice Actions
**Objective:** As a finance user, I want to save changes, verify invoices, and export documents.

#### Acceptance Criteria
1. The Detail Page shall display a primary "Сохранить" button for saving company selections and markup changes.
2. The Detail Page shall display a "Подтвердить" button that transitions status to verified (requires seller and buyer set).
3. Where the user has admin or currency_controller role, the Detail Page shall show a "Пересоздать из источника" option in a dropdown menu.
4. The Detail Page shall provide export options (DOCX, PDF) in a dropdown menu, not as separate buttons.
5. While the invoice status is verified or exported, the Detail Page shall disable editing of company selectors and markup.

### Requirement 4: Access Control
**Objective:** As a system, I want to restrict access to authorized roles only.

#### Acceptance Criteria
1. The CI Page shall be accessible only to users with admin, currency_controller, or finance role.
2. While the user lacks these roles, navigation to /currency-invoices shall redirect to /quotes.
