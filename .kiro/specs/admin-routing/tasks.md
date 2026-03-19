# Admin Routing — Implementation Tasks

## Task 1: Database migrations (REQ-8, REQ-9)
- [ ] Migration 188: Update RLS policies on `brand_assignments` and `route_procurement_group_assignments` to allow `head_of_procurement` CRUD
- [ ] Migration 189: Create `tender_routing_chain` table with RLS
- [ ] Run migrations via `scripts/apply-migrations.sh`
- [ ] Regenerate frontend types: `cd frontend && npm run db:types`
**Files:** `migrations/188_*.sql`, `migrations/189_*.sql`, `frontend/src/shared/lib/supabase/database.types.ts`
**REQ:** REQ-8, REQ-9

## Task 2: Feature scaffold — types + API layer (REQ-3, REQ-4, REQ-5, REQ-6)
- [ ] Create `frontend/src/features/admin-routing/model/types.ts` with all TypeScript types
- [ ] Create `frontend/src/features/admin-routing/api/routing-api.ts` with Supabase queries:
  - `fetchBrandAssignments(orgId)` + `fetchUnassignedBrands(orgId)`
  - `fetchGroupAssignments(orgId)`
  - `fetchTenderChain(orgId)`
  - `fetchUnassignedItems(orgId)`
  - CRUD functions for each entity
- [ ] Create `frontend/src/features/admin-routing/index.ts` barrel export
**Files:** `frontend/src/features/admin-routing/**`
**REQ:** REQ-3, REQ-4, REQ-5, REQ-6

## Task 3: Page + tabs shell (REQ-1, REQ-2)
- [ ] Create `frontend/src/app/(app)/admin/routing/page.tsx` — server component with auth check
- [ ] Create `frontend/src/features/admin-routing/ui/routing-page.tsx` — client component shell
- [ ] Create `frontend/src/features/admin-routing/ui/routing-tabs.tsx` — URL-driven tab navigation
- [ ] Create `frontend/src/features/admin-routing/ui/user-select.tsx` — procurement user dropdown
- [ ] Verify sidebar link works (already configured in sidebar-menu.ts)
**Files:** `frontend/src/app/(app)/admin/routing/page.tsx`, `frontend/src/features/admin-routing/ui/*`
**REQ:** REQ-1, REQ-2

## Task 4: Brands tab (REQ-3)
- [ ] Create `frontend/src/features/admin-routing/ui/brands-tab.tsx`
- [ ] Brand assignments table with edit/delete actions
- [ ] Unassigned brands section (brands from quote_items not in brand_assignments)
- [ ] Assignment dialog for add/edit brand assignment
- [ ] Create shared `frontend/src/features/admin-routing/ui/assignment-dialog.tsx`
**Files:** `frontend/src/features/admin-routing/ui/brands-tab.tsx`, `assignment-dialog.tsx`
**REQ:** REQ-3

## Task 5: Groups tab (REQ-4)
- [ ] Create `frontend/src/features/admin-routing/ui/groups-tab.tsx`
- [ ] Group assignments table with CRUD
- [ ] Reuse assignment-dialog with mode="group"
**Files:** `frontend/src/features/admin-routing/ui/groups-tab.tsx`
**REQ:** REQ-4

## Task 6: Tender tab (REQ-5)
- [ ] Create `frontend/src/features/admin-routing/ui/tender-tab.tsx`
- [ ] Ordered chain steps list with up/down reorder buttons
- [ ] Add/remove step functionality
- [ ] Chain step form (role_label + user selection)
**Files:** `frontend/src/features/admin-routing/ui/tender-tab.tsx`
**REQ:** REQ-5

## Task 7: Unassigned tab (REQ-6, REQ-7)
- [ ] Create `frontend/src/features/admin-routing/ui/unassigned-tab.tsx`
- [ ] Queue of unmatched items with routing cascade context
- [ ] Assign action with procurement user dropdown
- [ ] "Закрепить бренд" checkbox that creates brand_assignment on assign
- [ ] Implement priority cascade query logic (REQ-7)
**Files:** `frontend/src/features/admin-routing/ui/unassigned-tab.tsx`, `routing-api.ts`
**REQ:** REQ-6, REQ-7
