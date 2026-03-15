# Requirements Document

## Introduction
PHMB quote workspace at `/phmb/[id]` — the main working screen for creating and managing PHMB quotations. Features a Handsontable spreadsheet for items, search from price list, auto-calculation, payment terms, versioning, partial quotes, and PDF export. Screen 2 of 3 in the PHMB standalone flow.

## Requirements

### Requirement 1: Quote Workspace Layout
**Objective:** As a sales manager, I want a dedicated workspace for each PHMB quote with all tools visible, so that I can efficiently build quotations.

#### Acceptance Criteria
1. When a user navigates to `/phmb/[id]`, the Workspace shall display a header with quote IDN, client name, and items progress counter (e.g., "3/5 позиций с ценой").
2. The Workspace shall display a search bar above the items table for finding products in the price list.
3. The Workspace shall display a Handsontable spreadsheet as the primary working area, at full page width.
4. The Workspace shall display a collapsible payment terms panel below the table, collapsed by default.
5. The Workspace shall require authentication and verify sales or admin role.

### Requirement 2: Item Search and Addition
**Objective:** As a sales manager, I want to search products by article or name and add them to the quote, so that I can build the quote from the price list.

#### Acceptance Criteria
1. When the user types in the search bar (min 2 chars), the Workspace shall search `phmb_price_list` by catalog number or product name and display results in a dropdown.
2. When the user selects a search result, the Workspace shall add a new row to the Handsontable with product data pre-filled.
3. If the selected product has a price in the price list, the Workspace shall populate the price and mark the item as "priced".
4. If the selected product has no price, the Workspace shall mark the item as "waiting" with an orange background and clock icon, and create an entry in `phmb_procurement_queue`.
5. The search shall apply the organization's brand-type discount to results automatically.

### Requirement 3: Handsontable Spreadsheet
**Objective:** As a sales manager, I want an Excel-like table to manage quote items with copy-paste, cell navigation, and inline editing.

#### Acceptance Criteria
1. The Handsontable shall display columns: article, product name, brand, quantity, unit, purchase price, currency, and calculated columns (EXW USD, COGS, total price, total with VAT).
2. The user shall be able to edit quantity and purchase price directly in cells.
3. The Handsontable shall support keyboard cell navigation (arrow keys, Tab, Enter).
4. The Handsontable shall support copy-paste of rows and cell values.
5. The user shall be able to add and delete rows.
6. The Handsontable shall visually distinguish priced items from items waiting for procurement (orange background + icon for waiting).
7. Calculated columns shall be read-only and update automatically when inputs change.

### Requirement 4: Auto-Calculation
**Objective:** As a sales manager, I want prices to calculate automatically based on settings and payment terms, so that I see final prices without manual steps.

#### Acceptance Criteria
1. When an item receives a price (from price list or procurement), the Workspace shall automatically calculate EXW price, COGS, financial cost, total price, and total with VAT using the organization's overhead settings from `phmb_settings`.
2. When payment terms change (advance %, deferral days, markup %), the Workspace shall recalculate all priced items in real-time.
3. The Workspace shall call the Python API endpoint for calculation (phmb_calculator.py logic).
4. The Workspace shall display a quote total row at the bottom of the table summing all calculated items.

### Requirement 5: Payment Terms Panel
**Objective:** As a sales manager, I want to adjust payment terms per-quote and see how they affect prices.

#### Acceptance Criteria
1. The payment terms panel shall display editable fields: advance %, deferral days, and markup %.
2. The panel shall be pre-populated with values from the quote (set during creation).
3. When the user changes a term and clicks save, the Workspace shall persist the values and recalculate all items.
4. The panel shall be collapsible and collapsed by default.

### Requirement 6: Versioning
**Objective:** As a sales manager, I want to create versions of the quote with different terms, so that I can offer the client multiple pricing options.

#### Acceptance Criteria
1. The Workspace shall display version pills in the header (e.g., "v1 Аванс 100%", "v2 Отсрочка 30д").
2. When the user clicks "Создать версию", the Workspace shall create a new version with copied items and the current payment terms.
3. When the user clicks a version pill, the Workspace shall switch to that version's data.
4. Each version shall have independent payment terms and calculated prices.

### Requirement 7: Partial Quotes
**Objective:** As a sales manager, I want to generate a quote from only the priced items when some items are still waiting for procurement.

#### Acceptance Criteria
1. When some items are waiting for procurement, the Workspace shall display a "Сформировать КП из готовых позиций" button.
2. When clicked, the Workspace shall generate the quote using only priced items, excluding waiting items.

### Requirement 8: PDF Export
**Objective:** As a sales manager, I want to download a PDF of the commercial offer to send to the client.

#### Acceptance Criteria
1. The Workspace shall display a PDF export button in the header.
2. When clicked, the Workspace shall call the Python API to generate a PDF with the current version's items and terms.
3. The generated PDF shall download to the user's device.

### Requirement 9: Responsive Design
**Objective:** As a user, I want the workspace to be usable on different screen sizes.

#### Acceptance Criteria
1. The Workspace shall follow design system tokens from `design-system.md`.
2. While viewport is below 768px, the Handsontable shall be horizontally scrollable.
3. While viewport is below 768px, the payment terms panel shall stack fields vertically.
