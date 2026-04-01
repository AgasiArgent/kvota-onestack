# Procurement Distribution Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated procurement distribution page where head_of_procurement can assign unassigned quote items to procurement users, grouped by quote and brand, with workload visibility.

**Architecture:** New Next.js page at `/procurement/distribution` using FSD feature structure. Server component fetches data via admin Supabase client, client component handles assignment mutations. Sidebar gets a new menu item with badge counter. Migration clears existing brand_assignments data.

**Tech Stack:** Next.js 15 (App Router), Supabase (schema `kvota`), shadcn/ui, Tailwind CSS, TypeScript

**Spec:** `docs/superpowers/specs/2026-04-01-procurement-distribution-design.md`

---

### Task 1: Migration — Clear brand_assignments

**Files:**
- Create: `migrations/243_clear_brand_assignments.sql`

- [ ] **Step 1: Write migration**

```sql
-- Migration: 243_clear_brand_assignments.sql
-- Description: Clear all brand assignment rules to start fresh.
--   Table structure, RLS, and constraints are preserved.
--   Head of procurement will rebuild rules via "Pin brand" in distribution UI.

DELETE FROM kvota.brand_assignments;
```

- [ ] **Step 2: Apply migration**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"DELETE FROM kvota.brand_assignments;\""
```

Verify: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT COUNT(*) FROM kvota.brand_assignments;\""` — should return 0.

- [ ] **Step 3: Commit**

```bash
git add migrations/243_clear_brand_assignments.sql
git commit -m "feat: clear brand_assignments for fresh distribution start"
```

---

### Task 2: Feature types and server queries

**Files:**
- Create: `frontend/src/features/procurement-distribution/model/types.ts`
- Create: `frontend/src/features/procurement-distribution/api/server-queries.ts`

- [ ] **Step 1: Create types**

```typescript
// frontend/src/features/procurement-distribution/model/types.ts

/** A single unassigned quote item from the server */
export interface UnassignedItemRow {
  id: string;
  quote_id: string;
  brand: string | null;
  product_name: string;
  quantity: number;
  created_at: string | null;
}

/** Quote-level metadata for grouping */
export interface QuoteInfo {
  id: string;
  idn: string;
  customer_name: string | null;
  sales_manager_name: string | null;
  created_at: string | null;
}

/** A brand group within a quote — the unit of assignment */
export interface BrandGroup {
  brand: string | null;
  itemCount: number;
  itemIds: string[];
}

/** A quote with its unassigned brand groups */
export interface QuoteWithBrandGroups {
  quote: QuoteInfo;
  brandGroups: BrandGroup[];
}

/** Procurement user with current workload */
export interface ProcurementUserWorkload {
  user_id: string;
  full_name: string | null;
  active_items: number;
}
```

- [ ] **Step 2: Create server queries**

Read the existing pattern from `frontend/src/features/admin-routing/api/server-queries.ts` (uses `createAdminClient()`, batch profile fetching with Maps).

```typescript
// frontend/src/features/procurement-distribution/api/server-queries.ts
import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  QuoteWithBrandGroups,
  QuoteInfo,
  BrandGroup,
  ProcurementUserWorkload,
} from "../model/types";

export async function fetchDistributionData(
  orgId: string
): Promise<QuoteWithBrandGroups[]> {
  const supabase = createAdminClient();

  // 1. Get all quotes for this org (not deleted)
  const { data: quoteRows } = await supabase
    .from("quotes")
    .select("id, idn_quote, customer_id, created_by_user_id, created_at")
    .eq("organization_id", orgId)
    .is("deleted_at", null);

  if (!quoteRows || quoteRows.length === 0) return [];

  const quoteIds = quoteRows.map((q) => q.id);

  // 2. Get unassigned items across all quotes
  const { data: items } = await supabase
    .from("quote_items")
    .select("id, quote_id, brand, product_name, quantity, created_at")
    .in("quote_id", quoteIds)
    .is("assigned_procurement_user", null);

  if (!items || items.length === 0) return [];

  // 3. Find which quotes actually have unassigned items
  const quoteIdsWithItems = new Set(items.map((i) => i.quote_id));
  const relevantQuotes = quoteRows.filter((q) => quoteIdsWithItems.has(q.id));

  // 4. Batch-fetch customer names
  const customerIds = [
    ...new Set(
      relevantQuotes
        .map((q) => q.customer_id)
        .filter((id): id is string => id !== null)
    ),
  ];
  const customerMap = new Map<string, string>();
  if (customerIds.length > 0) {
    const { data: customers } = await supabase
      .from("customers")
      .select("id, name")
      .in("id", customerIds);
    for (const c of customers ?? []) {
      customerMap.set(c.id, c.name);
    }
  }

  // 5. Batch-fetch sales manager names
  const managerIds = [
    ...new Set(
      relevantQuotes
        .map((q) => q.created_by_user_id)
        .filter((id): id is string => id !== null)
    ),
  ];
  const managerMap = new Map<string, string | null>();
  if (managerIds.length > 0) {
    const { data: profiles } = await supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .eq("organization_id", orgId)
      .in("user_id", managerIds);
    for (const p of profiles ?? []) {
      managerMap.set(p.user_id, p.full_name);
    }
  }

  // 6. Group items by quote, then by brand
  const itemsByQuote = new Map<string, typeof items>();
  for (const item of items) {
    const list = itemsByQuote.get(item.quote_id) ?? [];
    list.push(item);
    itemsByQuote.set(item.quote_id, list);
  }

  // 7. Build result sorted by quote created_at ASC (oldest first)
  const sorted = relevantQuotes.sort(
    (a, b) =>
      new Date(a.created_at ?? 0).getTime() -
      new Date(b.created_at ?? 0).getTime()
  );

  return sorted.map((q) => {
    const quoteItems = itemsByQuote.get(q.id) ?? [];

    // Group by normalized brand
    const brandMap = new Map<string, { itemCount: number; itemIds: string[] }>();
    for (const item of quoteItems) {
      const key = item.brand ? item.brand.toLowerCase() : "__null__";
      const group = brandMap.get(key) ?? { itemCount: 0, itemIds: [] };
      group.itemCount++;
      group.itemIds.push(item.id);
      brandMap.set(key, group);
    }

    // Sort brand groups: alphabetical, null-brand last
    const brandGroups: BrandGroup[] = [...brandMap.entries()]
      .sort(([a], [b]) => {
        if (a === "__null__") return 1;
        if (b === "__null__") return -1;
        return a.localeCompare(b);
      })
      .map(([key, group]) => ({
        brand: key === "__null__" ? null : (quoteItems.find(
          (i) => i.brand && i.brand.toLowerCase() === key
        )?.brand ?? key),
        itemCount: group.itemCount,
        itemIds: group.itemIds,
      }));

    const quote: QuoteInfo = {
      id: q.id,
      idn: q.idn_quote ?? "",
      customer_name: q.customer_id
        ? (customerMap.get(q.customer_id) ?? null)
        : null,
      sales_manager_name: q.created_by_user_id
        ? (managerMap.get(q.created_by_user_id) ?? null)
        : null,
      created_at: q.created_at,
    };

    return { quote, brandGroups };
  });
}

export async function fetchProcurementWorkload(
  orgId: string
): Promise<ProcurementUserWorkload[]> {
  const supabase = createAdminClient();

  // 1. Find all procurement users
  const { data: roleRows } = await supabase
    .from("user_roles")
    .select("user_id, roles!inner(slug)")
    .eq("organization_id", orgId);

  const procUserIds = new Set<string>();
  for (const row of roleRows ?? []) {
    const role = row.roles as unknown as { slug: string } | null;
    const slug = role?.slug;
    if (slug === "procurement" || slug === "head_of_procurement") {
      procUserIds.add(row.user_id);
    }
  }

  if (procUserIds.size === 0) return [];

  const userIdArr = [...procUserIds];

  // 2. Fetch profiles
  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .eq("organization_id", orgId)
    .in("user_id", userIdArr);

  const profileMap = new Map<string, string | null>();
  for (const p of profiles ?? []) {
    profileMap.set(p.user_id, p.full_name);
  }

  // 3. Count active items per user
  const { data: countRows } = await supabase
    .from("quote_items")
    .select("assigned_procurement_user, quote_id")
    .in("assigned_procurement_user", userIdArr)
    .in("procurement_status", ["pending", "in_progress"]);

  // Filter to non-deleted quotes
  const activeQuoteIds = new Set<string>();
  if (countRows && countRows.length > 0) {
    const qIds = [...new Set(countRows.map((r) => r.quote_id))];
    const { data: activeQuotes } = await supabase
      .from("quotes")
      .select("id")
      .in("id", qIds)
      .is("deleted_at", null);
    for (const q of activeQuotes ?? []) {
      activeQuoteIds.add(q.id);
    }
  }

  const countMap = new Map<string, number>();
  for (const row of countRows ?? []) {
    if (!activeQuoteIds.has(row.quote_id)) continue;
    const uid = row.assigned_procurement_user;
    if (uid) {
      countMap.set(uid, (countMap.get(uid) ?? 0) + 1);
    }
  }

  return userIdArr.map((uid) => ({
    user_id: uid,
    full_name: profileMap.get(uid) ?? null,
    active_items: countMap.get(uid) ?? 0,
  }));
}

/** Lightweight count for sidebar badge */
export async function fetchUnassignedItemCount(orgId: string): Promise<number> {
  const supabase = createAdminClient();

  const { count, error } = await supabase
    .from("quote_items")
    .select("id, quotes!inner(organization_id, deleted_at)", {
      count: "exact",
      head: true,
    })
    .is("assigned_procurement_user", null)
    .eq("quotes.organization_id", orgId)
    .is("quotes.deleted_at", null);

  if (error) {
    console.error("Failed to fetch unassigned count:", error);
    return 0;
  }

  return count ?? 0;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/procurement-distribution/model/types.ts \
       frontend/src/features/procurement-distribution/api/server-queries.ts
git commit -m "feat: add types and server queries for procurement distribution"
```

---

### Task 3: Client mutations

**Files:**
- Create: `frontend/src/features/procurement-distribution/api/mutations.ts`

- [ ] **Step 1: Write mutation for assigning a brand group**

```typescript
// frontend/src/features/procurement-distribution/api/mutations.ts
"use server";

import { createAdminClient } from "@/shared/lib/supabase/server";
import { getSessionUser } from "@/entities/user";
import { revalidatePath } from "next/cache";

export async function assignBrandGroup(
  itemIds: string[],
  userId: string,
  pinBrand: boolean,
  orgId: string,
  brand: string | null
): Promise<{ success: boolean; error?: string }> {
  const user = await getSessionUser();
  if (!user?.orgId) return { success: false, error: "Not authenticated" };

  const isAllowed =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement");
  if (!isAllowed) return { success: false, error: "Not authorized" };

  const supabase = createAdminClient();

  // 1. Assign all items in the group
  const { error: updateError } = await supabase
    .from("quote_items")
    .update({ assigned_procurement_user: userId })
    .in("id", itemIds);

  if (updateError) {
    return { success: false, error: updateError.message };
  }

  // 2. Optionally pin the brand rule
  if (pinBrand && brand) {
    const { error: brandError } = await supabase
      .from("brand_assignments")
      .insert({
        organization_id: orgId,
        brand,
        user_id: userId,
        created_by: user.id,
      });

    // Ignore unique constraint — brand may already be pinned
    if (
      brandError &&
      !brandError.message.includes("unique_brand_per_org") &&
      !brandError.message.includes("duplicate key")
    ) {
      console.error("Failed to pin brand:", brandError);
    }
  }

  revalidatePath("/procurement/distribution");
  return { success: true };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/procurement-distribution/api/mutations.ts
git commit -m "feat: add server action for assigning brand groups"
```

---

### Task 4: UI components

**Files:**
- Create: `frontend/src/features/procurement-distribution/ui/workload-cards.tsx`
- Create: `frontend/src/features/procurement-distribution/ui/quote-brand-card.tsx`
- Create: `frontend/src/features/procurement-distribution/ui/distribution-page.tsx`

- [ ] **Step 1: Write workload cards component**

```typescript
// frontend/src/features/procurement-distribution/ui/workload-cards.tsx
import type { ProcurementUserWorkload } from "../model/types";

interface Props {
  users: ProcurementUserWorkload[];
}

export function WorkloadCards({ users }: Props) {
  if (users.length === 0) return null;

  return (
    <div>
      <h3 className="text-sm font-medium text-text-muted mb-3">
        Загрузка закупщиков
      </h3>
      <div className="flex flex-wrap gap-3">
        {users.map((u) => (
          <div
            key={u.user_id}
            className="px-4 py-3 rounded-lg border border-border-light bg-surface text-center min-w-[120px]"
          >
            <p className="text-sm font-medium text-text truncate">
              {u.full_name ?? "—"}
            </p>
            <p className="text-2xl font-bold text-accent mt-1">
              {u.active_items}
            </p>
            <p className="text-xs text-text-muted">позиций</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write quote brand card component**

This is the main interactive component — one card per quote, with brand groups inside.

```typescript
// frontend/src/features/procurement-distribution/ui/quote-brand-card.tsx
"use client";

import { useState } from "react";
import { Loader2, Pin } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { assignBrandGroup } from "../api/mutations";
import type {
  QuoteWithBrandGroups,
  BrandGroup,
  ProcurementUserWorkload,
} from "../model/types";

interface Props {
  data: QuoteWithBrandGroups;
  users: ProcurementUserWorkload[];
  orgId: string;
}

interface GroupState {
  userId: string;
  pinBrand: boolean;
}

export function QuoteBrandCard({ data, users, orgId }: Props) {
  const { quote, brandGroups } = data;
  const router = useRouter();
  const [groupStates, setGroupStates] = useState<Record<string, GroupState>>(
    {}
  );
  const [assigningKey, setAssigningKey] = useState<string | null>(null);

  function getKey(bg: BrandGroup): string {
    return bg.brand ?? "__null__";
  }

  function getState(bg: BrandGroup): GroupState {
    return groupStates[getKey(bg)] ?? { userId: "", pinBrand: false };
  }

  function updateState(bg: BrandGroup, partial: Partial<GroupState>) {
    const key = getKey(bg);
    setGroupStates((prev) => ({
      ...prev,
      [key]: { ...getState(bg), ...partial },
    }));
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
    });
  }

  async function handleAssign(bg: BrandGroup) {
    const state = getState(bg);
    if (!state.userId) return;

    const key = getKey(bg);
    setAssigningKey(key);

    const result = await assignBrandGroup(
      bg.itemIds,
      state.userId,
      state.pinBrand,
      orgId,
      bg.brand
    );

    if (result.success) {
      const userName =
        users.find((u) => u.user_id === state.userId)?.full_name ?? "закупщика";
      toast.success(
        `${bg.itemCount} поз. назначено на ${userName}`
      );
      router.refresh();
    } else {
      toast.error(result.error ?? "Ошибка назначения");
    }

    setAssigningKey(null);
  }

  return (
    <div className="rounded-lg border border-border-light bg-surface">
      {/* Quote header */}
      <div className="px-4 py-3 border-b border-border-light bg-background rounded-t-lg">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-semibold text-text">{quote.idn}</span>
          <span className="text-text-muted">{quote.customer_name ?? "—"}</span>
          <span className="text-text-subtle">{quote.sales_manager_name}</span>
          <span className="text-text-subtle ml-auto">
            {formatDate(quote.created_at)}
          </span>
        </div>
      </div>

      {/* Brand groups */}
      <div className="divide-y divide-border-light">
        {brandGroups.map((bg) => {
          const key = getKey(bg);
          const state = getState(bg);
          const isAssigning = assigningKey === key;

          return (
            <div
              key={key}
              className="px-4 py-3 flex items-center gap-4 flex-wrap"
            >
              {/* Brand + count */}
              <div className="min-w-[140px]">
                <span className="font-medium text-text">
                  {bg.brand ?? "Без бренда"}
                </span>
                <span className="text-text-muted text-sm ml-2">
                  ({bg.itemCount} поз.)
                </span>
              </div>

              {/* User select */}
              <div className="w-[200px]">
                <Select
                  value={state.userId}
                  onValueChange={(val) =>
                    updateState(bg, { userId: val ?? "" })
                  }
                  disabled={isAssigning}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Выберите закупщика" />
                  </SelectTrigger>
                  <SelectContent>
                    {users.map((u) => (
                      <SelectItem key={u.user_id} value={u.user_id}>
                        {u.full_name ?? u.user_id}
                        <span className="text-text-subtle ml-1">
                          ({u.active_items})
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Pin brand checkbox */}
              {bg.brand && (
                <label className="flex items-center gap-1.5 text-xs cursor-pointer whitespace-nowrap">
                  <Checkbox
                    checked={state.pinBrand}
                    onCheckedChange={(checked) =>
                      updateState(bg, { pinBrand: checked === true })
                    }
                    disabled={isAssigning}
                    className="size-3.5"
                  />
                  <Pin size={12} className="text-text-muted" />
                  <span className="text-text-muted">Закрепить</span>
                </label>
              )}

              {/* Assign button */}
              <Button
                size="sm"
                onClick={() => handleAssign(bg)}
                disabled={!state.userId || isAssigning}
                className="bg-accent text-white hover:bg-accent-hover"
              >
                {isAssigning ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : null}
                Назначить
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write main distribution page component**

```typescript
// frontend/src/features/procurement-distribution/ui/distribution-page.tsx
"use client";

import { CheckCircle2 } from "lucide-react";
import { Toaster } from "sonner";
import { WorkloadCards } from "./workload-cards";
import { QuoteBrandCard } from "./quote-brand-card";
import type {
  QuoteWithBrandGroups,
  ProcurementUserWorkload,
} from "../model/types";

interface Props {
  quotes: QuoteWithBrandGroups[];
  workload: ProcurementUserWorkload[];
  orgId: string;
}

export function DistributionPage({ quotes, workload, orgId }: Props) {
  const totalItems = quotes.reduce(
    (sum, q) => sum + q.brandGroups.reduce((s, bg) => s + bg.itemCount, 0),
    0
  );

  return (
    <>
      <div className="space-y-6 max-w-4xl">
        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold text-text">
            Распределение заявок
          </h1>
          {totalItems > 0 && (
            <p className="text-sm text-text-muted mt-1">
              {totalItems} {totalItems === 1 ? "позиция требует" : "позиций требуют"}{" "}
              назначения
            </p>
          )}
        </div>

        {/* Workload cards */}
        <WorkloadCards users={workload} />

        {/* Quote list or empty state */}
        {quotes.length === 0 ? (
          <div className="py-16 text-center">
            <CheckCircle2
              size={40}
              className="mx-auto text-success mb-3"
            />
            <p className="text-text-muted mb-1">Все заявки распределены</p>
            <p className="text-xs text-text-subtle">
              Новые нераспределённые позиции появятся здесь автоматически
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {quotes.map((q) => (
              <QuoteBrandCard
                key={q.quote.id}
                data={q}
                users={workload}
                orgId={orgId}
              />
            ))}
          </div>
        )}
      </div>
      <Toaster position="top-right" richColors />
    </>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/procurement-distribution/ui/
git commit -m "feat: add UI components for procurement distribution"
```

---

### Task 5: Feature barrel export and server page

**Files:**
- Create: `frontend/src/features/procurement-distribution/index.ts`
- Create: `frontend/src/app/(app)/procurement/distribution/page.tsx`

- [ ] **Step 1: Create barrel export**

```typescript
// frontend/src/features/procurement-distribution/index.ts
export { DistributionPage } from "./ui/distribution-page";
```

- [ ] **Step 2: Create server page component**

Follow the pattern from `frontend/src/app/(app)/admin/routing/page.tsx`: async server component, auth check, data fetch, pass to client component.

```typescript
// frontend/src/app/(app)/procurement/distribution/page.tsx
import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { DistributionPage } from "@/features/procurement-distribution";
import {
  fetchDistributionData,
  fetchProcurementWorkload,
} from "@/features/procurement-distribution/api/server-queries";

export default async function ProcurementDistributionPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement");
  if (!isAllowed) redirect("/quotes");

  const orgId = user.orgId;

  const [quotes, workload] = await Promise.all([
    fetchDistributionData(orgId),
    fetchProcurementWorkload(orgId),
  ]);

  return (
    <DistributionPage quotes={quotes} workload={workload} orgId={orgId} />
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/procurement-distribution/index.ts \
       frontend/src/app/\(app\)/procurement/distribution/page.tsx
git commit -m "feat: add procurement distribution page route"
```

---

### Task 6: Sidebar integration

**Files:**
- Modify: `frontend/src/widgets/sidebar/sidebar-menu.ts` — add "Распределение" item
- Modify: `frontend/src/widgets/sidebar/sidebar-menu.ts` — add `unassignedDistributionCount` to MenuConfig
- Modify: `frontend/src/widgets/sidebar/sidebar.tsx` — pass new count prop
- Modify: `frontend/src/app/(app)/layout.tsx` — fetch and pass unassigned count

- [ ] **Step 1: Add `unassignedDistributionCount` to MenuConfig and sidebar menu**

In `frontend/src/widgets/sidebar/sidebar-menu.ts`:

Add import for the new icon at the top:

```typescript
// Add to the import from "lucide-react":
import {
  PlayCircle,
  Newspaper,
  PlusCircle,
  BarChart3,
  Clock,
  Users,
  FileText,
  Building2,
  ClipboardList,
  Building,
  MapPin,
  Calendar,
  User,
  MessageSquare,
  MessageCircle,
  GitBranch,
  Settings,
  SplitSquareHorizontal,  // <-- ADD THIS
} from "lucide-react";
```

Add `unassignedDistributionCount` to `MenuConfig`:

```typescript
interface MenuConfig {
  roles: string[];
  isAdmin: boolean;
  pendingApprovalsCount?: number;
  changelogUnreadCount?: number;
  unassignedDistributionCount?: number;  // <-- ADD THIS
}
```

Destructure the new field in `buildMenuSections`:

```typescript
export function buildMenuSections(config: MenuConfig): MenuSection[] {
  const {
    roles,
    isAdmin,
    pendingApprovalsCount = 0,
    changelogUnreadCount = 0,
    unassignedDistributionCount = 0,  // <-- ADD THIS
  } = config;
```

Add the "Распределение" item in the "Главное" section, right after the "Обзор" item (after line 91, before the `Согласования` block):

```typescript
  if (hasRole("head_of_procurement")) {
    mainItems.push({
      icon: SplitSquareHorizontal,
      label: "Распределение",
      href: "/procurement/distribution",
      ...(unassignedDistributionCount > 0
        ? { badge: unassignedDistributionCount }
        : {}),
    });
  }
```

- [ ] **Step 2: Update sidebar props**

In `frontend/src/widgets/sidebar/sidebar.tsx`, add the new prop to `SidebarProps`:

```typescript
interface SidebarProps {
  user: SessionUser;
  pendingApprovalsCount?: number;
  changelogUnreadCount?: number;
  unassignedDistributionCount?: number;  // <-- ADD
  appContext?: AppContext;
}
```

Destructure and pass it to `menuBuilder`:

```typescript
export function Sidebar({
  user,
  pendingApprovalsCount = 0,
  changelogUnreadCount = 0,
  unassignedDistributionCount = 0,  // <-- ADD
  appContext = "main",
}: SidebarProps) {
  // ...
  const sections = menuBuilder({
    roles: user.roles,
    isAdmin,
    pendingApprovalsCount,
    changelogUnreadCount,
    unassignedDistributionCount,  // <-- ADD
  });
```

- [ ] **Step 3: Fetch count in layout and pass to sidebar**

In `frontend/src/app/(app)/layout.tsx`:

```typescript
import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { getAppContext } from "@/shared/lib/app-context";
import { Sidebar } from "@/widgets/sidebar";
import { FeedbackButton } from "@/features/feedback";
import { fetchUnassignedItemCount } from "@/features/procurement-distribution/api/server-queries";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const appContext = await getAppContext();

  // Fetch unassigned count only for users who can see it
  const canSeeDistribution =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement");
  const unassignedDistributionCount =
    canSeeDistribution && user.orgId
      ? await fetchUnassignedItemCount(user.orgId)
      : 0;

  return (
    <div className="flex min-h-screen">
      <Sidebar
        user={user}
        appContext={appContext}
        unassignedDistributionCount={unassignedDistributionCount}
      />
      <main className="flex-1 sidebar-margin p-6">
        {children}
      </main>
      <FeedbackButton />
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/widgets/sidebar/sidebar-menu.ts \
       frontend/src/widgets/sidebar/sidebar.tsx \
       frontend/src/app/\(app\)/layout.tsx
git commit -m "feat: add distribution item with badge to sidebar"
```

---

### Task 7: Manual testing and deployment

- [ ] **Step 1: Push to main and wait for CI**

```bash
git push origin main
```

Wait for GitHub Actions to pass.

- [ ] **Step 2: Test in browser**

Open `https://app.kvotaflow.ru/procurement/distribution` logged in as head_of_procurement or admin.

Verify:
1. Page loads without errors
2. Sidebar shows "Распределение" with badge count
3. Workload cards show procurement users with active item counts
4. Unassigned quotes are listed, grouped by brand
5. Selecting a user and clicking "Назначить" assigns items and refreshes the page
6. "Закрепить" checkbox creates a brand_assignments rule
7. Empty state shows when all items are distributed
8. Page is not visible to users without head_of_procurement/admin roles

- [ ] **Step 3: Verify brand_assignments is empty**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c 'SELECT COUNT(*) FROM kvota.brand_assignments;'"
```

Expected: 0

- [ ] **Step 4: Test pin brand flow**

1. Assign a brand group with "Закрепить" checked
2. Verify brand_assignments has a new row:
```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c 'SELECT brand, user_id FROM kvota.brand_assignments;'"
```
3. Create a new quote with the same brand — it should auto-assign to the pinned user
