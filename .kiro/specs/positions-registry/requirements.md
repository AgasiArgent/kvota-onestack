# Requirements Document

## Introduction

The Positions Registry is a new standalone page (`/positions`) in the Next.js frontend that serves as a **product sourcing directory** — a centralized reference of all unique products that procurement managers have processed across all quotes, whether successfully priced or marked as unavailable. Products are identified by brand + manufacturer SKU and can be expanded to reveal full sourcing history (different quotes, suppliers, prices, dates, and availability). The feature addresses user feedback request FB-260316-111518.

**Out of scope:** The "Покупай" (buy) status concept belongs on the procurement manager's quotes list as a third grouping — tracked as a separate feature.

## Requirements

### Requirement 1: Page Access and Navigation
**Objective:** As a procurement manager or admin, I want to access the Positions Registry from the sidebar, so that I can quickly look up product pricing without searching through individual quotes.

#### Acceptance Criteria
1. The Positions Registry shall appear as a menu item labeled "Позиции" in the "Реестры" sidebar section, positioned after "Поставщики".
2. When a user with the `procurement` or `admin` role navigates to `/positions`, the Positions Registry page shall load and display the product table.
3. When a user without the `procurement` or `admin` role navigates to `/positions`, the page shall redirect them to `/`.
4. When an unauthenticated user navigates to `/positions`, the page shall redirect them to `/login`.

### Requirement 2: Product Table (Master Level)
**Objective:** As a procurement manager, I want to see a deduplicated list of all products that have been processed (priced or marked unavailable), showing the most recent sourcing info for each, so that I can quickly reference current prices and availability.

#### Acceptance Criteria
1. The Positions Registry page shall display a table where each row represents a unique product, identified by the combination of `brand` + `idn_sku`.
2. Each product row shall display the following columns: availability status, brand, manufacturer SKU (`idn_sku`), product name, latest price (`purchase_price_original`) with currency (`purchase_currency`), МОЗ (procurement manager who last processed it), last updated date, and number of sourcing entries.
3. The table shall include products where `procurement_status = 'completed'` OR `is_unavailable = true` — i.e., all products that procurement has finished processing.
4. The "availability status" column shall display a visual indicator:
   - A "Доступен" badge when the most recent entry has `is_unavailable = false` and a price set
   - A "Недоступен" badge when the most recent entry has `is_unavailable = true`
   - A "Смешанный" badge when the product has both available and unavailable entries across different quotes
5. The "latest price" shall show the most recent price from entries where `is_unavailable = false`. If all entries are unavailable, the price column shall display "—".
6. The "МОЗ" column shall display the full name of the procurement user who last processed this product, resolved via `assigned_procurement_user` joined to `user_profiles`.
7. The "sourcing entries" column shall display a count of how many times this product has been processed across different quotes.
8. When a product has more than one sourcing entry, the row shall display an expand/collapse chevron indicator.
9. The table shall be sorted by last updated date (most recent first) by default.

### Requirement 3: Sourcing History (Detail Level)
**Objective:** As a procurement manager, I want to expand a product row to see all its sourcing entries across different quotes, suppliers, and dates, so that I can compare historical prices, availability, and sourcing options.

#### Acceptance Criteria
1. When a user clicks the expand chevron on a product row, the page shall display a nested detail section below the row showing all sourcing entries for that product.
2. Each sourcing history entry shall display: date (`updated_at`), availability status (available/unavailable), price (`purchase_price_original` + `purchase_currency`), МОЗ (procurement manager name), invoice/offer number (`proforma_number`), and a link to the source quote.
3. When an entry has `is_unavailable = true`, the price shall display "Недоступен" instead of a price value, and the row shall be visually muted (e.g., reduced opacity or strikethrough).
4. When a user clicks the source quote link, the page shall navigate to `/quotes/{quote_id}` (the quote detail page for that entry's parent quote).
5. The sourcing history entries shall be sorted by date (most recent first).
6. When a user clicks the expand chevron again, the detail section shall collapse.

### Requirement 4: Filtering
**Objective:** As a procurement manager, I want to filter the product list by brand, procurement manager, and date range, so that I can find specific products or review a particular manager's work.

#### Acceptance Criteria
1. The Positions Registry page shall provide a filter bar above the table with controls for: availability status (dropdown), brand (dropdown), МОЗ (dropdown), and date period (from/to date inputs).
2. When a user selects an availability filter ("Все", "Доступен", "Недоступен"), the page shall reload showing only products matching that availability status based on their most recent entry.
3. When a user selects a brand filter, the page shall reload showing only products matching that brand.
4. When a user selects a МОЗ filter, the page shall reload showing only products that have at least one sourcing entry from that manager.
5. When a user sets a date range, the page shall reload showing only products that have at least one sourcing entry within the specified period.
6. The brand filter shall populate its options from distinct `brand` values present in processed items.
7. The МОЗ filter shall populate its options from distinct procurement users who have processed items.
8. When multiple filters are applied, the page shall show only products matching ALL filter criteria (AND logic).
9. The page shall persist filter state in URL search parameters for bookmarking and sharing.

### Requirement 5: Pagination
**Objective:** As a user, I want the product list to be paginated, so that the page loads quickly regardless of product count.

#### Acceptance Criteria
1. The Positions Registry page shall display a maximum of 50 unique products per page.
2. When more than 50 products match the current filters, the page shall display pagination controls (previous/next) below the table.
3. The page shall display "Страница X из Y" and the total count of matching products.
4. When navigating between pages, the page shall preserve all active filter selections.

### Requirement 6: Empty State
**Objective:** As a user, I want clear feedback when there are no results, so that I understand the system state.

#### Acceptance Criteria
1. When no products match the active filters, the table shall display a centered message: "Позиции не найдены".
2. If the database query fails, the page shall display an error state rather than an empty table.

### Requirement 7: Design System Compliance
**Objective:** As a user, I want the Positions Registry to look consistent with the rest of the application.

#### Acceptance Criteria
1. The Positions Registry page shall use design tokens from `design-system.md` (Plus Jakarta Sans font, copper accent color, spacing scale).
2. The page shall use shadcn/ui Table, Select, Input, Button, and Badge components consistent with other registry pages.
3. The expandable detail section shall use a subtle background differentiation (e.g., slightly darker or indented) to visually distinguish it from master rows.
4. The pricing entries count badge shall use a secondary variant to indicate expandability.

### Requirement 8: FSD Architecture Compliance
**Objective:** As a developer, I want the page to follow established FSD patterns for codebase consistency.

#### Acceptance Criteria
1. The Positions Registry feature code shall reside in `frontend/src/features/positions/` with a barrel export via `index.ts`.
2. Position entity types and Supabase query functions shall reside in `frontend/src/entities/position/`.
3. The page route shall be a server component at `frontend/src/app/(app)/positions/page.tsx` that fetches data and passes it to the feature's client component.
4. The feature shall import only from `entities/` and `shared/` layers — never from other `features/` or `widgets/`.
