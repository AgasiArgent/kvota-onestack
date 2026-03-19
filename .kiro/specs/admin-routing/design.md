# Admin Routing — Technical Design

## Architecture Overview

```
frontend/src/
├── app/(app)/admin/routing/
│   └── page.tsx                    # Server component — data fetching + auth check
├── features/admin-routing/
│   ├── index.ts                    # Public API barrel
│   ├── ui/
│   │   ├── routing-page.tsx        # Client shell — tabs + content switching
│   │   ├── routing-tabs.tsx        # Tab navigation (URL-driven, ?tab= pattern)
│   │   ├── brands-tab.tsx          # REQ-3: Brand assignments CRUD
│   │   ├── groups-tab.tsx          # REQ-4: Sales group assignments CRUD
│   │   ├── tender-tab.tsx          # REQ-5: Tender chain configuration
│   │   ├── unassigned-tab.tsx      # REQ-6: Dispatcher queue
│   │   ├── assignment-dialog.tsx   # Shared dialog for add/edit assignment
│   │   └── user-select.tsx         # Procurement user dropdown (reusable)
│   ├── api/
│   │   └── routing-api.ts          # Supabase queries for all 4 tabs
│   └── model/
│       └── types.ts                # TypeScript types
```

## Data Flow

### Page Load (Server Component)
```
page.tsx (RSC)
  → auth check (redirect if not admin/head_of_procurement)
  → fetch initial data for active tab via Supabase server client
  → pass data as props to RoutingPage (client component)
```

### Tab Switching (Client)
```
RoutingTabs → Link with ?tab=X → page re-renders (Next.js handles via searchParams)
Each tab component receives its data as props from page.tsx
```

### Mutations (Client → Server)
```
Tab action (assign/edit/delete)
  → Supabase client.from('table').upsert/delete(...)
  → router.refresh() to re-fetch from server
  → Toast notification
```

## Component Details

### page.tsx (Server Component)
- Reads `searchParams.tab` (default: "brands")
- Auth: get user roles from Supabase, redirect if unauthorized
- Fetches ONLY the active tab's data (not all 4 tabs)
- Tab-specific queries:
  - brands: `brand_assignments` + unassigned brands (distinct from quote_items)
  - groups: `route_procurement_group_assignments` joined with `sales_groups`
  - tender: `tender_routing_chain` ordered by step_order
  - unassigned: quote_items where no routing rule matched + is_multibrand

### routing-tabs.tsx
Follow existing pattern from customer-tabs.tsx:
```tsx
const TABS = [
  { key: "brands", label: "По брендам" },
  { key: "groups", label: "По группам" },
  { key: "tender", label: "Тендерные" },
  { key: "unassigned", label: "Нераспределённые" },
] as const;
```
URL-driven via `<Link href="/admin/routing?tab=${key}">`.

### brands-tab.tsx
- Table: brand | assigned_to (user name) | created_at | actions
- "Назначить бренд" button → opens assignment-dialog
- "Неназначенные бренды" section: brands from quote_items not in brand_assignments
  - Each has "Назначить" action
- Inline user reassignment via select dropdown

### groups-tab.tsx
- Table: sales_group name | assigned_to | created_at | actions
- "Добавить правило" button → opens assignment-dialog (select group + user)
- Similar CRUD to brands tab

### tender-tab.tsx
- Ordered list of chain steps: step_order | role_label | user_name | actions
- Drag-to-reorder or up/down arrows
- "Добавить шаг" button
- For MVP: simple ordered list without drag (use up/down buttons)

### unassigned-tab.tsx
- Table of pending items: quote IDN | brand | customer | sales manager | date
- Per-item: "Назначить МОЗ" dropdown + "Закрепить бренд" checkbox
- "Назначить" button triggers:
  1. Update quote_item.assigned_procurement_user
  2. If checkbox checked: INSERT into brand_assignments
  3. Remove from queue (item now has assignment)

### assignment-dialog.tsx
Shared dialog for add/edit brand/group assignments:
- Props: mode ("brand" | "group"), current assignment (for edit), onSave callback
- Brand mode: brand name input (or select from unassigned) + user select
- Group mode: sales group select + user select
- Uses shadcn Dialog

### user-select.tsx
Reusable procurement user dropdown:
- Fetches users with `procurement` or `head_of_procurement` role
- Shows: full name (email fallback)
- Used across all 4 tabs

## Database Changes

### Migration 188: Update RLS policies
```sql
-- Add head_of_procurement to brand_assignments CRUD policies
-- Add head_of_procurement to route_procurement_group_assignments CRUD policies
```

### Migration 189: Create tender_routing_chain table
```sql
CREATE TABLE kvota.tender_routing_chain (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_label VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    CONSTRAINT tender_chain_unique_order UNIQUE (organization_id, step_order)
);
-- RLS: read by org members, write by admin + head_of_procurement
-- Indexes: organization_id, user_id
```

## Type Definitions

```typescript
interface BrandAssignment {
  id: string;
  brand: string;
  user_id: string;
  user: { full_name: string; email: string } | null;
  created_at: string;
}

interface GroupAssignment {
  id: string;
  sales_group_id: string;
  sales_group: { name: string } | null;
  user_id: string;
  user: { full_name: string; email: string } | null;
  created_at: string;
}

interface TenderChainStep {
  id: string;
  step_order: number;
  user_id: string;
  role_label: string;
  user: { full_name: string; email: string } | null;
}

interface UnassignedItem {
  quote_id: string;
  quote_idn: string;
  brand: string;
  customer_name: string;
  sales_manager_name: string;
  created_at: string;
  is_multibrand: boolean;
}

type RoutingTab = "brands" | "groups" | "tender" | "unassigned";
```

## Existing Code Reuse

- Tab pattern: copy from `customer-tabs.tsx` / `supplier-tabs.tsx`
- Table styling: use existing `@/components/ui/table`
- Dialog: use existing `@/components/ui/dialog`
- Toast: `sonner` (already installed, used in settings-tabs)
- Auth pattern: copy from other `page.tsx` files (supabase server client + role check)
- Supabase queries: follow pattern from `frontend/src/features/suppliers/api/`
