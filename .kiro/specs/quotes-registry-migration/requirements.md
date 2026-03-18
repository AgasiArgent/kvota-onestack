# Requirements Document

## Introduction
Migrate the /quotes registry page from FastHTML to Next.js and make it the primary landing page after login, replacing the current /dashboard placeholder. The page should be a clean, minimal registry with smart filtering — no summary cards or aggregation widgets. Statuses should be grouped into human-readable categories. Role-based visibility ensures sales users see only relevant quotes.

## Requirements

### Requirement 1: Quotes Registry Table
**Objective:** As a user, I want a clean table of quotes with essential columns, so that I can quickly find and navigate to the quote I need.

#### Acceptance Criteria
1. The Quotes Page shall display a table with columns: created date, IDN (quote number), customer name, manager name, workflow status badge, version indicator, total amount, and profit in USD.
2. When a user clicks a quote row, the Quotes Page shall navigate to `/quotes/{id}` detail page.
3. When a user clicks the customer name cell, the Quotes Page shall navigate to `/customers/{id}` (without triggering row navigation).
4. The Quotes Page shall render workflow status as a colored badge using the project design system tokens.
5. When a quote has multiple versions, the Quotes Page shall display a version indicator showing current version and total count.
6. The Quotes Page shall paginate results with a default page size of 20 and support loading more.

### Requirement 2: Status Group Filtering
**Objective:** As a user, I want statuses grouped into understandable categories, so that I can filter by business stage without memorizing 14 internal statuses.

#### Acceptance Criteria
1. The Quotes Page shall group the 14 workflow statuses into 5 categories: Draft (draft), In Progress (pending_procurement, logistics, pending_customs), Approval (pending_quote_control, pending_spec_control, pending_sales_review, pending_approval), Deal (approved, sent_to_client, deal), and Closed (rejected, cancelled).
2. When a user selects a status group filter, the Quotes Page shall filter the table to show only quotes matching any status within that group.
3. Where the user needs detailed filtering, the Quotes Page shall provide an option to expand and select individual statuses within a group.
4. When no filter is active, the Quotes Page shall show all quotes.
5. When a user clicks reset, the Quotes Page shall clear all active filters.

### Requirement 3: Customer and Manager Filters
**Objective:** As an admin or manager, I want to filter quotes by customer and responsible manager, so that I can review workload distribution and specific client pipelines.

#### Acceptance Criteria
1. The Quotes Page shall provide a customer filter dropdown populated with customers from the visible quotes.
2. Where the user has role admin, top_manager, or head_of_sales, the Quotes Page shall display a manager filter dropdown populated with active managers.
3. While the user has role sales or sales_manager, the Quotes Page shall hide the manager filter (they only see their own quotes).
4. When a user selects a customer filter, the Quotes Page shall filter the table to show only quotes for that customer.
5. When a user selects a manager filter, the Quotes Page shall filter the table to show only quotes created by that manager.
6. The Quotes Page shall support combining status, customer, and manager filters simultaneously.

### Requirement 4: Role-Based Quote Visibility
**Objective:** As a sales manager, I want to see only quotes relevant to me, so that I'm not overwhelmed by the full pipeline.

#### Acceptance Criteria
1. While the user has role sales or sales_manager, the Quotes Page shall display only quotes where the user is the creator OR where the quote's customer has the user assigned as manager (`customers.manager_id`).
2. While the user has role admin, top_manager, or head_of_sales, the Quotes Page shall display all organization quotes.
3. While the user has any other role (procurement, logistics, customs, finance), the Quotes Page shall display all organization quotes (they may need to find any quote for their workflow tasks).

### Requirement 5: Create Quote Action
**Objective:** As a sales user, I want to create a new quote directly from the registry, so that I don't need to navigate elsewhere.

#### Acceptance Criteria
1. Where the user has role sales, sales_manager, or admin, the Quotes Page shall display a "Новый КП" (New Quote) button in the page header.
2. When the user clicks "Новый КП", the Quotes Page shall open the existing create-quote dialog component (already built in Next.js).
3. When a new quote is successfully created via the dialog, the Quotes Page shall navigate to the new quote's detail page.
4. While the user lacks sales, sales_manager, or admin role, the Quotes Page shall not display the create button.

### Requirement 6: Landing Page Redirect
**Objective:** As any user, I want to land on the quotes registry after login, so that I immediately see my work.

#### Acceptance Criteria
1. When a user completes login, the Auth Flow shall redirect to `/quotes` instead of `/dashboard`.
2. When a user navigates to `/dashboard`, the App shall redirect to `/quotes`.
3. When a user navigates to `/` (root), the App shall redirect to `/quotes` for authenticated users.
4. The Sidebar shall highlight "Коммерческие предложения" as the active item when on `/quotes`.

### Requirement 7: URL State Persistence
**Objective:** As a user, I want my filter selections preserved in the URL, so that I can share filtered views and use browser back/forward.

#### Acceptance Criteria
1. When a user applies filters, the Quotes Page shall update the URL query parameters (e.g., `?status=in_progress&customer=uuid`).
2. When a user navigates to a URL with filter query parameters, the Quotes Page shall apply those filters on load.
3. When a user uses browser back/forward, the Quotes Page shall restore the filter state from the URL.
