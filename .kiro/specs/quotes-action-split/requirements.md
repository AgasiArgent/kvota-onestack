# Requirements Document

## Introduction
Add a visual split on the /quotes registry page: "Требует вашего действия" (requires your action) section at the top, followed by "Остальные КП" (other quotes). The split is based on the user's role and the quote's workflow_status, using the existing role-to-status mapping from the legacy /tasks page. This replaces the need for a separate /tasks page.

## Requirements

### Requirement 1: Role-Based Action Split
**Objective:** As a user, I want to immediately see which quotes need my attention, so that I can prioritize my work.

#### Acceptance Criteria
1. The Quotes Page shall split results into two sections: "Требует вашего действия" (top) and "Остальные КП" (bottom).
2. The "requires action" section shall filter quotes by the user's role using this mapping:
   - sales: `pending_sales_review`, `approved`
   - procurement: `pending_procurement`
   - logistics: `pending_logistics`, `pending_logistics_and_customs`
   - customs: `pending_customs`, `pending_logistics_and_customs`
   - quote_controller: `pending_quote_control`
   - spec_controller: `pending_spec_control`
   - top_manager/admin: quotes with `pending_approval`
3. When a user has multiple roles, the "requires action" section shall combine statuses from all their roles (union).
4. When the "requires action" section is empty, the Quotes Page shall hide it entirely (no empty section header).
5. The section header shall display the count of action items: "Требует вашего действия (N)".

### Requirement 2: Visual Separation
**Objective:** As a user, I want a clear visual distinction between action items and other quotes.

#### Acceptance Criteria
1. The "requires action" section shall have a distinct header with an accent indicator (icon or colored left border).
2. A visual divider shall separate the two sections.
3. The "Остальные КП" section shall have a muted header.
4. Both sections shall use the same table columns and formatting.

### Requirement 3: Filter Interaction
**Objective:** As a user, I want filters to work correctly with the split view.

#### Acceptance Criteria
1. When status group filters are active, the split shall still apply within the filtered results.
2. When customer or manager filters are active, both sections shall respect them.
3. The action section count in the header shall update to reflect filtered results.
