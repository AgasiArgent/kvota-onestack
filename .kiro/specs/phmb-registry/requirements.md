# Requirements Document

## Introduction
Standalone PHMB registry page at `/phmb` — the entry point for the PHMB (price-list mode) quotation flow. Displays a list of PHMB quotes with creation dialog. Screen 1 of 3 in the PHMB standalone flow. Accessible to sales managers and admins.

## Requirements

### Requirement 1: PHMB Quote Registry Table
**Objective:** As a sales manager, I want to see all my PHMB quotes in one place with key metrics at a glance, so that I can track progress and find quotes quickly.

#### Acceptance Criteria
1. When a user navigates to `/phmb`, the PHMB Registry shall display a table with columns: date, IDN, client name, items progress (priced/total), amount (USD), and status.
2. The PHMB Registry shall display only quotes where `is_phmb = true` for the user's organization.
3. The PHMB Registry shall show items progress as "X/Y" where X is the count of priced items and Y is the total count of items from `phmb_quote_items`.
4. The PHMB Registry shall display status as one of three values: "Черновик" (draft), "Ожидает цен" (has unpriced items), "Готов" (all items priced and calculated).
5. The PHMB Registry shall sort quotes by creation date descending (newest first) by default.
6. The PHMB Registry shall paginate results with 20 quotes per page.

### Requirement 2: Search and Filtering
**Objective:** As a sales manager, I want to search and filter PHMB quotes, so that I can find specific quotes without scrolling through the full list.

#### Acceptance Criteria
1. When the user types in the search field, the PHMB Registry shall filter quotes by client name or IDN in real-time.
2. When the user selects a status filter, the PHMB Registry shall show only quotes matching that status.
3. When both search and status filter are active, the PHMB Registry shall apply both conditions simultaneously.
4. The PHMB Registry shall display the total count of matching quotes.

### Requirement 3: Create PHMB Quote Dialog
**Objective:** As a sales manager, I want to create a new PHMB quote with payment terms pre-configured, so that the quote is ready for item entry with correct calculation parameters.

#### Acceptance Criteria
1. When the user clicks "Создать КП", the PHMB Registry shall open a dialog (not a separate page).
2. The dialog shall display fields: client (typeahead search), currency (USD/EUR/CNY/RUB), our legal entity (select from seller companies), advance % , deferral days, and markup %.
3. When the dialog opens, the PHMB Registry shall pre-populate advance %, deferral days, and markup % with default values from the organization's `phmb_settings`.
4. When the user types in the client field, the dialog shall search customers by name with typeahead suggestions.
5. When the user submits the form with all required fields filled, the PHMB Registry shall create a new quote with `is_phmb = true` and the specified payment terms.
6. If the quote creation succeeds, the PHMB Registry shall redirect the user to `/phmb/{id}` (the quote workspace).
7. If the quote creation fails, the dialog shall display an error message without closing.
8. While the creation is in progress, the dialog shall disable the submit button and show a loading indicator.

### Requirement 4: Empty State
**Objective:** As a first-time user, I want clear guidance when no PHMB quotes exist, so that I understand how to get started.

#### Acceptance Criteria
1. When no PHMB quotes exist for the organization, the PHMB Registry shall display an empty state with an icon, explanatory text, and a "Создать первое КП" button.
2. When the user clicks the empty state CTA button, the PHMB Registry shall open the create dialog.

### Requirement 5: Navigation and Access Control
**Objective:** As a system, I want to ensure PHMB registry is accessible from the sidebar and restricted to authorized roles.

#### Acceptance Criteria
1. The sidebar shall display a "PHMB" link in the Реестры section, visible only for users with sales or admin roles.
2. When the user clicks the "PHMB" sidebar link, the application shall navigate to `/phmb`.
3. The PHMB Registry shall require Supabase Auth authentication before rendering any content.
4. The PHMB Registry shall verify the user has a sales or admin role before granting access.
5. When an unauthorized user attempts to access `/phmb`, the PHMB Registry shall redirect to the dashboard.

### Requirement 6: Responsive Design
**Objective:** As a user, I want the registry page to work on different screen sizes.

#### Acceptance Criteria
1. While the viewport width is below 768px, the PHMB Registry shall hide the amount column and show a condensed layout.
2. The PHMB Registry shall follow the design system tokens from `design-system.md` (Slate & Copper palette, Plus Jakarta Sans font, constrained spacing scales).
3. While the viewport width is below 768px, the create dialog shall display as a full-screen sheet instead of a centered dialog.
