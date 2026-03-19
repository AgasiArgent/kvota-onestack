# Requirements Document

## Introduction
Migrate /finance page from FastHTML to Next.js. Consolidate 4 tabs into 3: merge Workspace + ERPS into a unified deals view with togglable detail columns, keep Payments tab with fixed labels, keep Supplier Invoices tab. Deal detail is NOT in scope (part of future /quotes/{id} migration).

## Requirements

### Requirement 1: Deals Registry (merged Workspace + ERPS)
**Objective:** As a finance user, I want a unified deals list with togglable payment detail columns, so that I don't switch between two tabs showing the same data.

#### Acceptance Criteria
1. The Finance Page shall display a "Сделки" tab as the default, showing deals in a table.
2. The table shall have base columns: № сделки, № спецификации, клиент, сумма (USD), дата подписания, статус.
3. The Finance Page shall provide a view toggle (Компактный / Расширенный) above the table.
4. When "Расширенный" is selected, the table shall show additional ERPS columns: аванс %, условия оплаты, сумма спец USD, профит USD, оплачено USD, остаток USD, крайний срок.
5. The Finance Page shall provide status filter pills: Все, В работе, Завершённые, Отменённые.
6. The Finance Page shall show summary cards above the table: count and total amount per status.
7. When a user clicks a deal row, the Finance Page shall navigate to the deal detail on the legacy app (kvotaflow.ru).
8. The Finance Page shall provide an "Выгрузить данные" (Export) button linking to the legacy export endpoint.

### Requirement 2: Payments Tab
**Objective:** As a finance user, I want to see all plan-fact payment records with proper Russian labels.

#### Acceptance Criteria
1. The Payments tab shall display a table with columns: плановая дата, сделка, клиент, категория, описание, сумма план, сумма факт, дата факт.
2. The Payments tab shall provide filters: grouping (По записям / По клиентам), type (Все / Приход / Расход), status (Все / План / Оплачено / Просрочено), date range.
3. The Payments tab shall display human-readable Russian labels for logistics stage keys (first_mile → "Первая миля", hub → "Хаб", last_mile → "Последняя миля", etc.).
4. The Payments tab shall show a footer with totals: planned income, actual income, planned expenses, actual expenses, balance.
5. The Payments tab shall paginate results.

### Requirement 3: Supplier Invoices Tab
**Objective:** As a finance user, I want to see all supplier invoices for payment tracking.

#### Acceptance Criteria
1. The Supplier Invoices tab shall display a table with columns: №, номер инвойса, поставщик, дата, сумма, валюта, статус.
2. The Supplier Invoices tab shall show totals by currency in the footer.
3. The Supplier Invoices tab shall paginate results.
4. When a user clicks a row, it shall navigate to the supplier invoice detail (legacy app for now).

### Requirement 4: Access Control
**Objective:** Restrict access to authorized roles.

#### Acceptance Criteria
1. The Finance Page shall be accessible only to users with admin, finance, or top_manager role.
2. While the user lacks these roles, navigation to /finance shall redirect to /quotes.
