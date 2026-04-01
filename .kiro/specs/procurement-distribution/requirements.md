# Procurement Distribution — Requirements

## REQ-1: Page Access
When a user with role `head_of_procurement` or `admin` navigates to `/procurement/distribution`, the system shall display the distribution page.
Users without these roles shall be redirected to `/quotes`.

## REQ-2: Clear Brand Assignments
The system shall clear all existing records from the `brand_assignments` table via migration 243.
The table structure, RLS policies, and constraints shall remain intact.

## REQ-3: Workload Cards
The distribution page shall display workload cards at the top showing all procurement users (roles `procurement` and `head_of_procurement`).
Each card shall show: user's full name and count of active items (items with `procurement_status` in `pending` or `in_progress` from non-deleted quotes).

## REQ-4: Unassigned Items Grouped by Quote and Brand
The distribution page shall list all quotes that have items with `assigned_procurement_user IS NULL`.
Quotes shall be sorted by `created_at ASC` (oldest first).
Within each quote, items shall be grouped by brand (case-insensitive).
Items with `brand IS NULL` shall appear as a separate group labeled "Без бренда".
Each quote card shall show: quote IDN, customer name, sales manager name, creation date.
Each brand group shall show: brand name and item count.

## REQ-5: Assignment Action
Each brand group shall have:
- A dropdown to select a procurement user (showing all procurement users from REQ-3)
- A "Назначить" button that assigns all items in that brand group to the selected user
When "Назначить" is clicked, the system shall:
1. Update `assigned_procurement_user` on all items in the group
2. Refresh the page data (the assigned group disappears from the list)
3. Show a toast notification with the count of assigned items and the user's name

## REQ-6: Pin Brand Rule
Each brand group (except "Без бренда") shall have a checkbox "Закрепить".
When checked during assignment, the system shall create a record in `brand_assignments` mapping that brand to the selected procurement user.
If the brand already exists in `brand_assignments`, the system shall silently ignore the duplicate constraint error.

## REQ-7: Sidebar Integration
The sidebar shall show a "Распределение" item in the "Главное" section, visible only to `head_of_procurement` and `admin` roles.
The item shall display a red badge with the count of unassigned items (across all non-deleted quotes in the user's organization).
The badge shall not appear when the count is 0.

## REQ-8: Empty State
When there are no unassigned items, the page shall display an empty state with a green checkmark icon, text "Все заявки распределены", and subtitle "Новые нераспределённые позиции появятся здесь автоматически".

## REQ-9: Routing Cascade Unchanged
The existing routing cascade trigger (`assign_procurement_user_cascade`) shall NOT be modified.
The cascade order remains: Tender → Sales Group → Multi-brand skip → Brand → NULL.
The multi-brand skip step (items in quotes with multiple brands go to NULL) shall be preserved.

## REQ-10: Admin Routing Page Unchanged
The existing `/admin/routing` page with all 4 tabs (Brands, Groups, Tender, Unassigned) shall remain fully functional and unchanged.
