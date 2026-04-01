# Procurement Distribution — Implementation Tasks

## Task 1: Migration — clear brand_assignments (REQ-2)
- [ ] Create `migrations/243_clear_brand_assignments.sql` with `DELETE FROM kvota.brand_assignments`
- [ ] Apply migration on VPS
- [ ] Verify table is empty
**Files:** `migrations/243_clear_brand_assignments.sql`
**REQ:** REQ-2

## Task 2: Types and server queries (REQ-3, REQ-4, REQ-7)
- [ ] Create `frontend/src/features/procurement-distribution/model/types.ts` with types: `UnassignedItemRow`, `QuoteInfo`, `BrandGroup`, `QuoteWithBrandGroups`, `ProcurementUserWorkload`
- [ ] Create `frontend/src/features/procurement-distribution/api/server-queries.ts` with:
  - `fetchDistributionData(orgId)` — returns `QuoteWithBrandGroups[]` (REQ-4)
  - `fetchProcurementWorkload(orgId)` — returns `ProcurementUserWorkload[]` (REQ-3)
  - `fetchUnassignedItemCount(orgId)` — returns `number` for sidebar badge (REQ-7)
**Files:** `frontend/src/features/procurement-distribution/model/types.ts`, `frontend/src/features/procurement-distribution/api/server-queries.ts`
**REQ:** REQ-3, REQ-4, REQ-7

## Task 3: Server action for assignment (REQ-5, REQ-6)
- [ ] Create `frontend/src/features/procurement-distribution/api/mutations.ts` with `assignBrandGroup()` server action
  - Auth + role check before mutation
  - Bulk update `quote_items.assigned_procurement_user` for all items in the brand group
  - Optionally insert `brand_assignments` record (REQ-6)
  - Call `revalidatePath("/procurement/distribution")`
**Files:** `frontend/src/features/procurement-distribution/api/mutations.ts`
**REQ:** REQ-5, REQ-6

## Task 4: UI components (REQ-3, REQ-4, REQ-5, REQ-6, REQ-8)
- [ ] Create `frontend/src/features/procurement-distribution/ui/workload-cards.tsx` (REQ-3)
- [ ] Create `frontend/src/features/procurement-distribution/ui/quote-brand-card.tsx` (REQ-4, REQ-5, REQ-6)
- [ ] Create `frontend/src/features/procurement-distribution/ui/distribution-page.tsx` (REQ-8)
**Files:** `frontend/src/features/procurement-distribution/ui/`
**REQ:** REQ-3, REQ-4, REQ-5, REQ-6, REQ-8

## Task 5: Page route and barrel export (REQ-1)
- [ ] Create `frontend/src/features/procurement-distribution/index.ts` barrel export
- [ ] Create `frontend/src/app/(app)/procurement/distribution/page.tsx` — server component with auth check, parallel data fetch
**Files:** `frontend/src/features/procurement-distribution/index.ts`, `frontend/src/app/(app)/procurement/distribution/page.tsx`
**REQ:** REQ-1

## Task 6: Sidebar integration (REQ-7)
- [ ] Add `SplitSquareHorizontal` icon import and `unassignedDistributionCount` to `MenuConfig` in `sidebar-menu.ts`
- [ ] Add "Распределение" item to "Главное" section for `head_of_procurement` role
- [ ] Add `unassignedDistributionCount` prop to `SidebarProps` in `sidebar.tsx`
- [ ] Fetch `fetchUnassignedItemCount(orgId)` in `layout.tsx` and pass to `Sidebar`
**Files:** `frontend/src/widgets/sidebar/sidebar-menu.ts`, `frontend/src/widgets/sidebar/sidebar.tsx`, `frontend/src/app/(app)/layout.tsx`
**REQ:** REQ-7

## Task 7: Manual testing (ALL REQs)
- [ ] Push to main, wait for CI
- [ ] Test page access with head_of_procurement role (REQ-1)
- [ ] Test redirect for unauthorized users (REQ-1)
- [ ] Verify workload cards display (REQ-3)
- [ ] Verify quote grouping and brand grouping (REQ-4)
- [ ] Test assignment flow (REQ-5)
- [ ] Test "Закрепить" checkbox creates brand_assignments record (REQ-6)
- [ ] Verify sidebar badge appears and updates (REQ-7)
- [ ] Verify empty state when all distributed (REQ-8)
- [ ] Verify routing cascade is unchanged (REQ-9)
- [ ] Verify /admin/routing still works (REQ-10)
