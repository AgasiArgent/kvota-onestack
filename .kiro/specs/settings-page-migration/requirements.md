# Requirements Document

## Introduction
Migrate the FastHTML `/settings` and `/settings/phmb` pages into a single tabbed Next.js page at `/settings` with UX redesign. The new page consolidates organization-level settings (calculation rates, PHMB overhead costs, brand discounts) into three tabs with improved information hierarchy, live percentage calculations, and mobile-responsive layout. Admin role required.

## Requirements

### Requirement 1: Tabbed Settings Page Structure
**Objective:** As an admin user, I want a single `/settings` page with three tabs (Расчёты, Наценки PHMB, Скидки по брендам), so that all organization settings are accessible from one location without navigating between pages.

#### Acceptance Criteria
1. When an admin user navigates to `/settings`, the Settings Page shall display a tabbed interface with three tabs: "Расчёты", "Наценки PHMB", and "Скидки по брендам".
2. When a tab is selected, the Settings Page shall display the corresponding content without a full page reload.
3. The Settings Page shall display the organization name as read-only text in the page header.
4. The Settings Page shall persist the selected tab in the URL (e.g., `/settings?tab=phmb`) so that direct linking and browser back/forward work correctly.
5. When a non-admin user attempts to access `/settings`, the Settings Page shall redirect to the dashboard or display an unauthorized message.

### Requirement 2: Calculation Rates Tab (Расчёты)
**Objective:** As an admin user, I want to view and edit the three core calculation rate parameters, so that the quotation calculation engine uses the correct rates.

#### Acceptance Criteria
1. When the "Расчёты" tab is active, the Settings Page shall display three editable numeric fields: forex risk % (`rate_forex_risk`), financial commission % (`rate_fin_commission`), and daily loan interest % (`rate_loan_interest_daily`).
2. When the admin clicks "Сохранить", the Settings Page shall upsert the values to the `calculation_settings` table for the current organization.
3. If the save operation succeeds, the Settings Page shall display a success toast notification.
4. If the save operation fails, the Settings Page shall display an error toast with the failure reason.
5. While the save is in progress, the Settings Page shall disable the save button and show a loading indicator.

### Requirement 3: PHMB Overhead Costs Tab (Наценки PHMB)
**Objective:** As an admin user, I want to configure PHMB overhead costs and default values with live percentage preview, so that I can understand how absolute costs translate into calculation percentages.

#### Acceptance Criteria
1. When the "Наценки PHMB" tab is active, the Settings Page shall display the base pallet price (`base_price_per_pallet`) prominently at the top with an explanatory label: "Все накладные расходы делятся на эту сумму для получения процентных коэффициентов."
2. The Settings Page shall display overhead cost fields in a left column: logistics per pallet, customs handling, warehouse (SVH), bank expenses, insurance %, and other expenses.
3. When any overhead cost value or the base pallet price changes, the Settings Page shall recalculate and display the corresponding percentage next to each absolute cost field in real-time (e.g., "1800 USD → 3.6%").
4. The Settings Page shall display default value fields in a right column: markup %, advance %, payment days, and delivery days.
5. The Settings Page shall display a bidirectional markup ↔ margin calculator that updates in real-time when either value changes.
6. When the admin clicks "Сохранить", the Settings Page shall upsert all PHMB fields to the `phmb_settings` table for the current organization.
7. If the save operation succeeds, the Settings Page shall display a success toast notification.
8. If the save operation fails, the Settings Page shall display an error toast with the failure reason.

### Requirement 4: Brand Discounts Tab (Скидки по брендам)
**Objective:** As an admin user, I want to manage brand-type discount rules with search and inline editing, so that discount percentages for specific brand/classification combinations are maintained efficiently.

#### Acceptance Criteria
1. When the "Скидки по брендам" tab is active, the Settings Page shall display a searchable table of brand-type discounts with columns: brand, classification, and discount %.
2. When the admin types in the search field, the Settings Page shall filter the discount table rows by brand name in real-time.
3. When the admin clicks the edit icon on a discount row, the Settings Page shall enable inline editing of the discount percentage.
4. When the admin saves an inline edit, the Settings Page shall update the `phmb_brand_type_discounts` record in the database.
5. When the admin clicks the delete icon on a discount row, the Settings Page shall show a confirmation and then delete the record from the database.
6. The Settings Page shall display a "Добавить группу" button that opens a form to create a new brand group.
7. The Settings Page shall display existing brand groups below the discount table with a delete action per group.

### Requirement 5: Responsive Design
**Objective:** As an admin user, I want the settings page to work correctly on mobile devices, so that I can adjust settings from any device.

#### Acceptance Criteria
1. While the viewport width is below 768px, the Settings Page shall display tabs as a horizontally scrollable row.
2. While the viewport width is below 768px, the Settings Page shall stack form fields in a single column layout.
3. While the viewport width is below 768px, the Settings Page shall display the save button at full width.
4. The Settings Page shall follow the design system tokens from `design-system.md` (Slate & Copper palette, Plus Jakarta Sans font, constrained spacing scales).

### Requirement 6: Authentication and Authorization
**Objective:** As a system, I want to ensure only admin users can access and modify organization settings, so that sensitive configuration is protected.

#### Acceptance Criteria
1. The Settings Page shall require Supabase Auth authentication before rendering any content.
2. The Settings Page shall verify the user has the "admin" role before granting access.
3. If the user's session expires while on the page, the Settings Page shall redirect to the login page.
4. The Settings Page shall read organization context from the authenticated user's profile to scope all database operations.
