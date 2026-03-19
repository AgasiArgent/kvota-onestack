# Admin Routing — Requirements

## REQ-1: Page Structure
When the user navigates to `/admin/routing`, the system shall display a page with 4 tabs: "По брендам", "По группам", "Тендерные", "Нераспределённые".
The active tab shall be controlled by `?tab=` query parameter (default: `brands`).

## REQ-2: Access Control
The page shall be accessible only to users with roles `admin` or `head_of_procurement`.
If a user without these roles navigates to the page, the system shall redirect to `/quotes`.

## REQ-3: Tab — По брендам (brands)
When the "По брендам" tab is active, the system shall display:
- A table of existing brand → procurement manager assignments (from `brand_assignments` table)
- Columns: Brand, Procurement Manager, Assigned Date, Actions (edit/delete)
- A button to add a new brand assignment (select brand + select procurement user)
- A section showing unassigned brands (brands from `quote_items` with no assignment)
- Inline editing of assignments (reassign to different user)

## REQ-4: Tab — По группам (groups)
When the "По группам" tab is active, the system shall display:
- A table of existing sales group → procurement manager assignments (from `route_procurement_group_assignments`)
- Columns: Sales Group, Procurement Manager, Assigned Date, Actions (edit/delete)
- A button to add a new group assignment (select sales group + select procurement user)
- Inline editing of assignments

## REQ-5: Tab — Тендерные (tender)
When the "Тендерные" tab is active, the system shall display:
- A configurable chain of responsible users for tender deals
- The chain defines the sequence: заявка → тендерный отдел → руководитель → распределённый МОЗ
- CRUD for chain steps (add/remove/reorder users in the chain)
- One chain per organization

## REQ-6: Tab — Нераспределённые (unassigned)
When the "Нераспределённые" tab is active, the system shall display:
- A queue of quote items that did not match any routing rule
- Multi-brand quotes automatically appear here
- Each item shows: Quote IDN, Brand, Customer, Sales Manager, Created Date
- Action: Assign to a specific procurement manager (select from dropdown)
- Checkbox: "Закрепить бренд за этим МОЗ" — when checked, creates a `brand_assignments` record

## REQ-7: Priority Cascade (DEFERRED — future task)
The routing engine shall evaluate rules in this order (first match wins):
1. Is the deal a tender? → tender chain
2. Is the sales manager in a mapped sales group? → group-based procurement user
3. Is the quote multi-brand? → unassigned queue (manual)
4. Is the brand assigned? → brand-based procurement user
5. No match → unassigned queue (manual)

> NOTE: The cascade ENGINE is a separate concern. This page only DISPLAYS config and unassigned items.
> The auto-routing trigger `assign_procurement_user_by_brand()` already exists for brand-based routing.
> Group-based and tender routing triggers are deferred to a follow-up task.

## REQ-8: RLS Policy Update
RLS policies on `brand_assignments` and `route_procurement_group_assignments` shall allow `head_of_procurement` role to INSERT, UPDATE, DELETE (currently admin-only).

## REQ-9: New DB Table — Tender Routing Chain
A new table `tender_routing_chain` shall store ordered chain steps:
- `id`, `organization_id`, `step_order`, `user_id`, `role_label` (e.g., "Тендерный отдел"), `created_at`
- Unique constraint on (organization_id, step_order)
