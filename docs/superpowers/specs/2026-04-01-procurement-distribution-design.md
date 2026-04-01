# Procurement Distribution Page

**Date:** 2026-04-01
**Status:** Approved
**Scope:** New distribution page for head_of_procurement + cleanup of brand_assignments

---

## Problem

Procurement assignment has 3 stages: group-based routing, brand-based routing, and manual distribution. Currently, manual distribution lives in an admin tab (`/admin/routing?tab=unassigned`) that shows a flat list of individual items — no grouping by quote or brand. Head of procurement needs a dedicated, daily-use workspace for distributing unassigned items, with the ability to assign different procurement users to different brands within a single quote.

## Decision Record

- **Routing cascade:** Unchanged. Tender → Sales Group → Multi-brand skip → Brand → NULL.
- **Multi-brand skip:** Kept. Multi-brand quotes require elevated attention and manual review.
- **`brand_assignments` table:** Cleared (all rows deleted). Rules will be rebuilt organically as head_of_procurement uses "Pin brand" during manual distribution.
- **`/admin/routing`:** Stays as-is with all 4 tabs (Brands, Groups, Tender, Unassigned) for rule configuration.
- **New page:** `/procurement/distribution` — daily-use distribution workspace, separate from admin.
- **Backfill:** None. New logic applies only to future assignments.

---

## Changes

### 1. Migration: Clear `brand_assignments`

```sql
DELETE FROM kvota.brand_assignments;
```

Table structure, RLS, and constraints remain. Data is wiped to start fresh.

### 2. New Page: `/procurement/distribution`

**Access:** `head_of_procurement`, `admin` roles only.

**Sidebar placement:** Section "Главное", item "Распределение" with a red badge showing unassigned item count.

#### Page Layout

```
┌─────────────────────────────────────────────────────┐
│  Распределение заявок                  [12 позиций] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Загрузка закупщиков:                               │
│  ┌──────────┬──────────┬──────────┐                 │
│  │ Петров   │ Сидоров  │ Козлов   │                 │
│  │ 12 поз.  │ 5 поз.   │ 8 поз.   │                 │
│  └──────────┴──────────┴──────────┘                 │
│                                                     │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  КП Q-202604-0015 | ООО "Альфа" | Иванов | 28.03   │
│  ┌─────────────────────────────────────────────┐    │
│  │ Bosch (3 поз.)                              │    │
│  │ [Выбрать закупщика ▼] [☐ Закрепить] [Назн.] │    │
│  ├─────────────────────────────────────────────┤    │
│  │ Siemens (2 поз.)                            │    │
│  │ [Выбрать закупщика ▼] [☐ Закрепить] [Назн.] │    │
│  ├─────────────────────────────────────────────┤    │
│  │ Без бренда (1 поз.)                         │    │
│  │ [Выбрать закупщика ▼]               [Назн.] │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  КП Q-202604-0012 | ИП Бетов | Петрова | 25.03     │
│  ┌─────────────────────────────────────────────┐    │
│  │ ABB (5 поз.)                                │    │
│  │ [Выбрать закупщика ▼] [☐ Закрепить] [Назн.] │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### Data Queries

**Unassigned items (server query):**
```sql
SELECT
  qi.id,
  qi.quote_id,
  qi.brand,
  qi.product_name,
  qi.quantity,
  qi.created_at,
  q.idn AS quote_idn,
  q.created_at AS quote_created_at,
  c.name AS customer_name,
  up.full_name AS sales_manager_name
FROM kvota.quote_items qi
JOIN kvota.quotes q ON q.id = qi.quote_id
LEFT JOIN kvota.customers c ON c.id = q.customer_id
LEFT JOIN kvota.user_profiles up ON up.user_id = q.created_by_user_id
  AND up.organization_id = q.organization_id
WHERE qi.assigned_procurement_user IS NULL
  AND q.deleted_at IS NULL
  AND q.organization_id = :org_id
ORDER BY q.created_at ASC, qi.brand ASC NULLS LAST
```

**Procurement user workload (server query):**
```sql
SELECT
  qi.assigned_procurement_user AS user_id,
  up.full_name,
  COUNT(*) AS active_items
FROM kvota.quote_items qi
JOIN kvota.quotes q ON q.id = qi.quote_id
JOIN kvota.user_profiles up ON up.user_id = qi.assigned_procurement_user
  AND up.organization_id = q.organization_id
WHERE qi.assigned_procurement_user IS NOT NULL
  AND qi.procurement_status IN ('pending', 'in_progress')
  AND q.deleted_at IS NULL
  AND q.organization_id = :org_id
GROUP BY qi.assigned_procurement_user, up.full_name
```

**All procurement users (for dropdown):**
Reuse existing `fetchProcurementUsers()` from `features/admin-routing/api/routing-api.ts`.

#### Grouping Logic (client-side)

1. Group items by `quote_id`
2. Within each quote, group by `LOWER(brand)` (null brand = separate group "Без бренда")
3. Sort quotes by `quote_created_at ASC` (oldest first)
4. Sort brand groups alphabetically within each quote, null-brand last

#### Assignment Action

When user clicks "Назначить" on a brand group:

1. **Update items:** `UPDATE quote_items SET assigned_procurement_user = :user_id WHERE quote_id = :quote_id AND LOWER(brand) = LOWER(:brand) AND assigned_procurement_user IS NULL`
   - For null-brand group: `... AND brand IS NULL AND assigned_procurement_user IS NULL`
2. **Pin brand (if checked):** `INSERT INTO brand_assignments (organization_id, brand, user_id, created_by) VALUES (:org_id, :brand, :user_id, :current_user_id)` — skip if brand is null, ignore unique constraint violation (brand already pinned)
3. **Refresh:** Re-fetch data, update workload cards
4. **Toast:** "3 позиции назначены на Петрова"

#### Empty State

When no unassigned items exist:
- Icon: CheckCircle2 (green)
- Title: "Все заявки распределены"
- Subtitle: "Новые нераспределённые позиции появятся здесь автоматически"

### 3. Sidebar Badge

In the sidebar configuration, add "Распределение" item visible to `head_of_procurement` and `admin`. Badge shows count of unassigned items (`quote_items WHERE assigned_procurement_user IS NULL AND quote.deleted_at IS NULL`).

### 4. `/admin/routing` — No Changes

All 4 tabs remain: Brands (for managing pinned brand rules), Groups, Tender, Unassigned (existing flat list). The Unassigned tab continues to work as a secondary interface. No redirect, no removal.

---

## File Changes Summary

| What | Where | Type |
|------|-------|------|
| Migration: clear brand_assignments | `migrations/XXX_clear_brand_assignments.sql` | New |
| Distribution page (Next.js) | `frontend/src/app/(app)/procurement/distribution/page.tsx` | New |
| Distribution server queries | `frontend/src/features/procurement-distribution/api/server-queries.ts` | New |
| Distribution client mutations | `frontend/src/features/procurement-distribution/api/mutations.ts` | New |
| Distribution types | `frontend/src/features/procurement-distribution/model/types.ts` | New |
| Distribution UI components | `frontend/src/features/procurement-distribution/ui/` | New |
| Sidebar config | `frontend/src/widgets/sidebar/` or equivalent | Edit |

---

## Out of Scope

- Filtering/sorting controls (just oldest-first for now)
- Backfilling existing assignments
- Changes to the routing cascade trigger
- Changes to `/admin/routing`
