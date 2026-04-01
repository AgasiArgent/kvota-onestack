# Procurement Distribution — Technical Design

## Architecture

New FSD feature `procurement-distribution` with a dedicated Next.js page at `/procurement/distribution`.
Server component handles auth and data fetching; client components handle interactive assignment.

## File Structure

```
frontend/src/
├── features/procurement-distribution/
│   ├── model/types.ts          — TypeScript types
│   ├── api/server-queries.ts   — Server-side Supabase queries (createAdminClient)
│   ├── api/mutations.ts        — Server action for assigning brand groups
│   ├── ui/distribution-page.tsx — Main client component
│   ├── ui/workload-cards.tsx    — Procurement user workload cards
│   ├── ui/quote-brand-card.tsx  — Single quote card with brand groups
│   └── index.ts                — Barrel export
├── app/(app)/procurement/distribution/
│   └── page.tsx                — Server component (auth + data fetch)
└── widgets/sidebar/
    ├── sidebar-menu.ts         — Add "Распределение" menu item (MODIFY)
    └── sidebar.tsx             — Pass unassignedDistributionCount prop (MODIFY)
```

Also:
- `frontend/src/app/(app)/layout.tsx` — fetch and pass unassigned count (MODIFY)
- `migrations/243_clear_brand_assignments.sql` — clear brand_assignments data (NEW)

## Data Flow

1. **Layout** (`layout.tsx`): Fetches `fetchUnassignedItemCount(orgId)` → passes to `Sidebar` as `unassignedDistributionCount`
2. **Page** (`page.tsx`): Auth check → parallel fetch of `fetchDistributionData(orgId)` and `fetchProcurementWorkload(orgId)` → passes to `DistributionPage`
3. **DistributionPage**: Renders `WorkloadCards` + list of `QuoteBrandCard`
4. **QuoteBrandCard**: User selects procurement user, optionally checks "Закрепить", clicks "Назначить"
5. **Server Action** (`assignBrandGroup`): Updates `quote_items.assigned_procurement_user`, optionally inserts `brand_assignments`, calls `revalidatePath`

## Grouping Algorithm

Server query fetches all unassigned items, then groups client-side:
1. Group items by `quote_id`
2. Within each quote, group by `LOWER(brand)` (null brand = separate group)
3. Sort quotes by `created_at ASC`
4. Sort brand groups alphabetically, null-brand last

## Security

- Page: server-side role check (`head_of_procurement` or `admin`), redirect if unauthorized
- Server action: re-validates session and role before mutation
- Data queries use `createAdminClient()` (service_role) after auth check — bypasses RLS for cross-table joins
