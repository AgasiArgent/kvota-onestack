# Customers Page Migration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the customers list and detail pages from FastHTML to Next.js with UX improvements: 10 tabs → 4 tabs (Обзор, CRM, Документы, Позиции), compact KP/spec counters on overview, server-side pagination.

**Architecture:** Server components for data fetching (Supabase direct), client components only for interactive parts (tab switching, search, inline edit). FSD architecture: `entities/customer` for types+queries, `features/customers` for page-level UI.

**Tech Stack:** Next.js 15 App Router, Supabase JS (`schema: "kvota"`), shadcn/ui, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-13-customers-screen-audit.md`

---

## File Structure

```
frontend/src/
├── entities/customer/
│   ├── index.ts                    # Public API: types + queries
│   ├── types.ts                    # Customer, CustomerContact, CustomerStats types
│   └── queries.ts                  # Supabase queries (list, detail, stats, contacts)
├── features/customers/
│   ├── index.ts                    # Public API
│   └── ui/
│       ├── customers-table.tsx     # List page table (client — search, filter, paginate)
│       ├── customer-header.tsx     # Detail header: name, status, "Создать КП" button
│       ├── tab-overview.tsx        # Обзор: requisites + debt + KP/spec counters
│       ├── tab-crm.tsx             # CRM: sub-tabs (contacts, addresses, calls, meetings, notes)
│       ├── tab-documents.tsx       # Документы: sub-tabs (KP, specs, contracts)
│       ├── tab-positions.tsx       # Позиции: requested items table
│       └── customer-tabs.tsx       # Tab navigation controller (4 main tabs)
├── components/ui/
│   └── table.tsx                   # shadcn table (need to add)
├── app/(app)/
│   ├── customers/
│   │   ├── page.tsx                # List page (server component)
│   │   └── [id]/
│   │       └── page.tsx            # Detail page (server component, tab routing via searchParams)
```

---

## Chunk 1: Entity Layer + List Page

### Task 1: Customer Entity Types

**Files:**
- Create: `frontend/src/entities/customer/types.ts`
- Create: `frontend/src/entities/customer/index.ts`

- [ ] **Step 1: Create customer types**

```typescript
// types.ts
export interface Customer {
  id: string;
  name: string;
  inn: string | null;
  kpp: string | null;
  ogrn: string | null;
  legal_address: string | null;
  actual_address: string | null;
  postal_address: string | null;
  general_director_name: string | null;
  general_director_position: string | null;
  warehouse_addresses: { address: string; label?: string }[] | null;
  is_active: boolean;
  order_source: string | null;
  manager_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  // Joined fields
  manager?: { full_name: string } | null;
  quotes_count?: number;
  specs_count?: number;
}

export interface CustomerContact {
  id: string;
  customer_id: string;
  name: string;
  last_name: string | null;
  patronymic: string | null;
  position: string | null;
  email: string | null;
  phone: string | null;
  is_signatory: boolean;
  is_primary: boolean;
  is_lpr: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerListItem {
  id: string;
  name: string;
  inn: string | null;
  is_active: boolean;
  manager: { full_name: string } | null;
  quotes_count: number;
  last_quote_date: string | null;
}

export interface CustomerStats {
  quotes_in_review: number;
  quotes_in_progress: number;
  quotes_total: number;
  specs_active: number;
  specs_signed: number;
  specs_total: number;
  total_debt: number;
  overdue_count: number;
  last_payment_date: string | null;
}
```

- [ ] **Step 2: Create barrel export**

```typescript
// index.ts
export type {
  Customer,
  CustomerContact,
  CustomerListItem,
  CustomerStats,
} from "./types";
export {
  fetchCustomersList,
  fetchCustomerDetail,
  fetchCustomerStats,
  fetchCustomerContacts,
} from "./queries";
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/entities/customer/
git commit -m "feat(customers): add customer entity types"
```

---

### Task 2: Customer Supabase Queries

**Files:**
- Create: `frontend/src/entities/customer/queries.ts`

- [ ] **Step 1: Create queries file with list query**

```typescript
// queries.ts
import { createClient } from "@/shared/lib/supabase/server";
import type { CustomerListItem, Customer, CustomerContact, CustomerStats } from "./types";

const PAGE_SIZE = 50;

export async function fetchCustomersList(params: {
  search?: string;
  status?: "active" | "inactive" | "";
  page?: number;
}): Promise<{ data: CustomerListItem[]; total: number }> {
  const supabase = await createClient();
  const { search = "", status = "", page = 1 } = params;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("customers")
    .select(
      "id, name, inn, is_active, manager:user_profiles!manager_id(full_name)",
      { count: "exact" }
    )
    .order("created_at", { ascending: false })
    .range(from, to);

  if (search) {
    query = query.or(`name.ilike.%${search}%,inn.ilike.%${search}%`);
  }
  if (status === "active") query = query.eq("is_active", true);
  if (status === "inactive") query = query.eq("is_active", false);

  const { data, count, error } = await query;
  if (error) throw error;

  // Fetch quotes count per customer in a separate query
  // (PostgREST can't do aggregated counts in the same select)
  const customerIds = (data ?? []).map((c) => c.id);
  const { data: quoteCounts } = await supabase
    .rpc("get_customers_quote_counts", { customer_ids: customerIds });

  const countsMap = new Map(
    (quoteCounts ?? []).map((r: { customer_id: string; cnt: number; last_date: string | null }) => [
      r.customer_id,
      { count: r.cnt, lastDate: r.last_date },
    ])
  );

  const items: CustomerListItem[] = (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
    inn: row.inn,
    is_active: row.is_active,
    manager: (row.manager as { full_name: string } | null) ?? null,
    quotes_count: countsMap.get(row.id)?.count ?? 0,
    last_quote_date: countsMap.get(row.id)?.lastDate ?? null,
  }));

  return { data: items, total: count ?? 0 };
}

export async function fetchCustomerDetail(id: string): Promise<Customer | null> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("customers")
    .select("*, manager:user_profiles!manager_id(full_name)")
    .eq("id", id)
    .single();

  if (error) return null;
  return data as Customer;
}

export async function fetchCustomerStats(customerId: string): Promise<CustomerStats> {
  const supabase = await createClient();

  // Quotes stats
  const { data: quotes } = await supabase
    .from("quotes")
    .select("id, status")
    .eq("customer_id", customerId);

  const quotesList = quotes ?? [];
  const inReview = quotesList.filter((q) => q.status === "in_review").length;
  const inProgress = quotesList.filter((q) =>
    ["draft", "calculating", "calculated"].includes(q.status)
  ).length;

  // Specs stats
  const { data: specs } = await supabase
    .from("specifications")
    .select("id, status")
    .eq("customer_id", customerId);

  const specsList = specs ?? [];
  const active = specsList.filter((s) => s.status !== "signed" && s.status !== "cancelled").length;
  const signed = specsList.filter((s) => s.status === "signed").length;

  return {
    quotes_in_review: inReview,
    quotes_in_progress: inProgress,
    quotes_total: quotesList.length,
    specs_active: active,
    specs_signed: signed,
    specs_total: specsList.length,
    total_debt: 0,      // TODO: implement from plan_fact_items
    overdue_count: 0,   // TODO: implement from plan_fact_items
    last_payment_date: null,
  };
}

export async function fetchCustomerContacts(customerId: string): Promise<CustomerContact[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("customer_contacts")
    .select("*")
    .eq("customer_id", customerId)
    .order("is_primary", { ascending: false })
    .order("name");

  if (error) throw error;
  return (data ?? []) as CustomerContact[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/entities/customer/
git commit -m "feat(customers): add Supabase queries for list and detail"
```

---

### Task 3: DB function for quote counts

**Files:**
- Create: `migrations/188_customer_quote_counts.sql`

- [ ] **Step 1: Create migration**

```sql
-- Migration 188: Add RPC function for customer quote counts (used by Next.js frontend)
CREATE OR REPLACE FUNCTION kvota.get_customers_quote_counts(customer_ids uuid[])
RETURNS TABLE(customer_id uuid, cnt bigint, last_date timestamptz) AS $$
  SELECT
    q.customer_id,
    count(*)::bigint AS cnt,
    max(q.created_at) AS last_date
  FROM kvota.quotes q
  WHERE q.customer_id = ANY(customer_ids)
  GROUP BY q.customer_id;
$$ LANGUAGE sql STABLE;
```

- [ ] **Step 2: Apply migration**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -f -" < migrations/188_customer_quote_counts.sql
```

- [ ] **Step 3: Commit**

```bash
git add migrations/188_customer_quote_counts.sql
git commit -m "feat(db): add get_customers_quote_counts RPC for customer list"
```

---

### Task 4: Add shadcn Table component

**Files:**
- Create: `frontend/src/components/ui/table.tsx`

- [ ] **Step 1: Add table component via shadcn CLI**

```bash
cd frontend && npx shadcn@latest add table
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ui/table.tsx
git commit -m "feat(ui): add shadcn table component"
```

---

### Task 5: Customers List Page

**Files:**
- Create: `frontend/src/features/customers/ui/customers-table.tsx`
- Create: `frontend/src/features/customers/index.ts`
- Create: `frontend/src/app/(app)/customers/page.tsx`

- [ ] **Step 1: Create the customer table (client component)**

This is where meaningful UX decisions happen. The table needs:
- Search input with debounce
- Status filter dropdown
- Pagination controls
- Columns: Наименование (truncated 50ch), ИНН, Менеджер, КП (count), Посл. КП (date), Статус

```typescript
// features/customers/ui/customers-table.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CustomerListItem } from "@/entities/customer";

interface Props {
  initialData: CustomerListItem[];
  initialTotal: number;
  initialSearch?: string;
  initialStatus?: string;
  initialPage?: number;
}

const PAGE_SIZE = 50;

export function CustomersTable({
  initialData,
  initialTotal,
  initialSearch = "",
  initialStatus = "",
  initialPage = 1,
}: Props) {
  // Server-driven: use URL params for search/filter/page
  // This component renders the initial server data
  // and handles client-side navigation for filter changes

  const totalPages = Math.ceil(initialTotal / PAGE_SIZE);

  function formatDate(dateStr: string | null) {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  function truncate(str: string, max: number) {
    return str.length > max ? str.slice(0, max) + "..." : str;
  }

  return (
    <div className="space-y-4">
      {/* Search + Filter bar */}
      <form className="flex items-center gap-3" method="GET">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input
            name="q"
            defaultValue={initialSearch}
            placeholder="Поиск по названию или ИНН..."
            className="pl-9"
          />
        </div>
        <Select name="status" defaultValue={initialStatus || "all"}>
          <SelectTrigger className="w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все статусы</SelectItem>
            <SelectItem value="active">Активные</SelectItem>
            <SelectItem value="inactive">Неактивные</SelectItem>
          </SelectContent>
        </Select>
        <Button type="submit" size="sm">
          <Search size={16} />
          Найти
        </Button>
        <Button asChild variant="default" size="sm" className="ml-auto">
          <Link href="/customers/new">
            <Plus size={16} />
            Новый клиент
          </Link>
        </Button>
      </form>

      {/* Stats row */}
      <div className="flex gap-4 text-sm text-slate-500">
        <span>Всего: {initialTotal}</span>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40%]">Наименование</TableHead>
            <TableHead>ИНН</TableHead>
            <TableHead>Менеджер</TableHead>
            <TableHead className="text-center">КП</TableHead>
            <TableHead>Посл. КП</TableHead>
            <TableHead>Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {initialData.map((customer) => (
            <TableRow key={customer.id}>
              <TableCell>
                <Link
                  href={`/customers/${customer.id}`}
                  className="text-blue-600 hover:underline font-medium"
                >
                  {truncate(customer.name, 50)}
                </Link>
              </TableCell>
              <TableCell className="text-slate-500 tabular-nums">
                {customer.inn ?? "—"}
              </TableCell>
              <TableCell className="text-slate-500">
                {customer.manager?.full_name ?? "—"}
              </TableCell>
              <TableCell className="text-center tabular-nums">
                {customer.quotes_count || "—"}
              </TableCell>
              <TableCell className="text-slate-500">
                {formatDate(customer.last_quote_date)}
              </TableCell>
              <TableCell>
                <Badge variant={customer.is_active ? "default" : "secondary"}>
                  {customer.is_active ? "Активен" : "Неактивен"}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
          {initialData.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-slate-400">
                Клиенты не найдены
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">
            Страница {initialPage} из {totalPages}
          </span>
          <div className="flex gap-2">
            {initialPage > 1 && (
              <Button asChild variant="outline" size="sm">
                <Link
                  href={`/customers?page=${initialPage - 1}&q=${initialSearch}&status=${initialStatus}`}
                >
                  Назад
                </Link>
              </Button>
            )}
            {initialPage < totalPages && (
              <Button asChild variant="outline" size="sm">
                <Link
                  href={`/customers?page=${initialPage + 1}&q=${initialSearch}&status=${initialStatus}`}
                >
                  Вперёд
                </Link>
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create barrel export**

```typescript
// features/customers/index.ts
export { CustomersTable } from "./ui/customers-table";
```

- [ ] **Step 3: Create list page (server component)**

```typescript
// app/(app)/customers/page.tsx
import { fetchCustomersList } from "@/entities/customer";
import { CustomersTable } from "@/features/customers";

interface Props {
  searchParams: Promise<{ q?: string; status?: string; page?: string }>;
}

export default async function CustomersPage({ searchParams }: Props) {
  const params = await searchParams;
  const search = params.q ?? "";
  const status = (params.status ?? "") as "active" | "inactive" | "";
  const page = parseInt(params.page ?? "1", 10);

  const { data, total } = await fetchCustomersList({ search, status, page });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Клиенты</h1>
      <CustomersTable
        initialData={data}
        initialTotal={total}
        initialSearch={search}
        initialStatus={status}
        initialPage={page}
      />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/customers/ frontend/src/app/\(app\)/customers/
git commit -m "feat(customers): add customers list page with search and pagination"
```

---

## Chunk 2: Customer Detail — Overview Tab

### Task 6: Customer Header Component

**Files:**
- Create: `frontend/src/features/customers/ui/customer-header.tsx`

- [ ] **Step 1: Create header component**

Back link + customer name + status badge + "Создать КП" button.

```typescript
// features/customers/ui/customer-header.tsx
import Link from "next/link";
import { ArrowLeft, Plus, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Customer } from "@/entities/customer";

interface Props {
  customer: Customer;
}

export function CustomerHeader({ customer }: Props) {
  return (
    <div className="mb-6">
      <Link
        href="/customers"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-3"
      >
        <ArrowLeft size={16} />
        Клиенты
      </Link>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 size={24} className="text-slate-400" />
          <h1 className="text-2xl font-bold">{customer.name}</h1>
          <Badge variant={customer.is_active ? "default" : "secondary"}>
            {customer.is_active ? "Активен" : "Неактивен"}
          </Badge>
        </div>
        <Button asChild>
          <Link href={`/quotes/new?customer_id=${customer.id}`}>
            <Plus size={16} />
            Создать КП
          </Link>
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/customers/ui/customer-header.tsx
git commit -m "feat(customers): add customer detail header component"
```

---

### Task 7: Tab Navigation Component

**Files:**
- Create: `frontend/src/features/customers/ui/customer-tabs.tsx`

- [ ] **Step 1: Create tab component**

4 tabs: Обзор, CRM, Документы, Позиции. Uses URL searchParams for tab state (server-friendly).

```typescript
// features/customers/ui/customer-tabs.tsx
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

interface Props {
  customerId: string;
  children: React.ReactNode;
}

const TABS = [
  { key: "overview", label: "Обзор" },
  { key: "crm", label: "CRM" },
  { key: "documents", label: "Документы" },
  { key: "positions", label: "Позиции" },
] as const;

export type TabKey = (typeof TABS)[number]["key"];

export function CustomerTabs({ customerId, children }: Props) {
  const searchParams = useSearchParams();
  const activeTab = (searchParams.get("tab") ?? "overview") as TabKey;

  return (
    <div>
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {TABS.map((tab) => (
          <Link
            key={tab.key}
            href={`/customers/${customerId}?tab=${tab.key}`}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === tab.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
            )}
          >
            {tab.label}
          </Link>
        ))}
      </div>
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/customers/ui/customer-tabs.tsx
git commit -m "feat(customers): add tab navigation component"
```

---

### Task 8: Overview Tab

**Files:**
- Create: `frontend/src/features/customers/ui/tab-overview.tsx`

- [ ] **Step 1: Create overview tab**

Layout: Requisites card + Debt card (side by side), then KP/Specs counters below.

```typescript
// features/customers/ui/tab-overview.tsx
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Customer, CustomerStats } from "@/entities/customer";

interface Props {
  customer: Customer;
  stats: CustomerStats;
}

export function TabOverview({ customer, stats }: Props) {
  return (
    <div className="space-y-6">
      {/* Row 1: Requisites + Debt */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Requisites */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Реквизиты</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="ИНН" value={customer.inn} />
            <Row label="КПП" value={customer.kpp} />
            <Row label="ОГРН" value={customer.ogrn} />
            <Row label="Источник" value={customer.order_source} />
            <Row label="Менеджер" value={customer.manager?.full_name} />
          </CardContent>
        </Card>

        {/* Debt */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Задолженность</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Долг" value={`${stats.total_debt.toLocaleString("ru-RU")} ₽`} />
            <Row label="Просрочено" value={`${stats.overdue_count} позиций`} />
            <Row
              label="Последний платёж"
              value={
                stats.last_payment_date
                  ? new Date(stats.last_payment_date).toLocaleDateString("ru-RU")
                  : "нет данных"
              }
            />
          </CardContent>
        </Card>
      </div>

      {/* Row 2: KP + Specs counters */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">Коммерческие предложения</CardTitle>
            <Link
              href={`?tab=documents&subtab=quotes`}
              className="text-sm text-blue-600 hover:underline"
            >
              Все →
            </Link>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <CounterBlock label="На рассмотрении" value={stats.quotes_in_review} />
              <CounterBlock label="В подготовке" value={stats.quotes_in_progress} />
              <CounterBlock label="Всего" value={stats.quotes_total} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">Спецификации</CardTitle>
            <Link
              href={`?tab=documents&subtab=specs`}
              className="text-sm text-blue-600 hover:underline"
            >
              Все →
            </Link>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <CounterBlock label="Активных" value={stats.specs_active} />
              <CounterBlock label="Подписанных" value={stats.specs_signed} />
              <CounterBlock label="Всего" value={stats.specs_total} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium">{value ?? "—"}</span>
    </div>
  );
}

function CounterBlock({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/customers/ui/tab-overview.tsx
git commit -m "feat(customers): add overview tab with requisites, debt, KP/spec counters"
```

---

### Task 9: Detail Page (server component)

**Files:**
- Create: `frontend/src/app/(app)/customers/[id]/page.tsx`
- Modify: `frontend/src/features/customers/index.ts`

- [ ] **Step 1: Create detail page**

```typescript
// app/(app)/customers/[id]/page.tsx
import { notFound } from "next/navigation";
import {
  fetchCustomerDetail,
  fetchCustomerStats,
  fetchCustomerContacts,
} from "@/entities/customer";
import { CustomerHeader } from "@/features/customers/ui/customer-header";
import { CustomerTabs } from "@/features/customers/ui/customer-tabs";
import { TabOverview } from "@/features/customers/ui/tab-overview";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string; subtab?: string }>;
}

export default async function CustomerDetailPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { tab = "overview" } = await searchParams;

  const customer = await fetchCustomerDetail(id);
  if (!customer) notFound();

  return (
    <div>
      <CustomerHeader customer={customer} />
      <CustomerTabs customerId={id}>
        {tab === "overview" && <OverviewContent customerId={id} customer={customer} />}
        {tab === "crm" && <PlaceholderTab name="CRM" />}
        {tab === "documents" && <PlaceholderTab name="Документы" />}
        {tab === "positions" && <PlaceholderTab name="Позиции" />}
      </CustomerTabs>
    </div>
  );
}

async function OverviewContent({
  customerId,
  customer,
}: {
  customerId: string;
  customer: Awaited<ReturnType<typeof fetchCustomerDetail>> & {};
}) {
  const stats = await fetchCustomerStats(customerId);
  return <TabOverview customer={customer} stats={stats} />;
}

function PlaceholderTab({ name }: { name: string }) {
  return (
    <div className="py-12 text-center text-slate-400">
      Таб «{name}» — в разработке
    </div>
  );
}
```

- [ ] **Step 2: Update barrel export**

```typescript
// features/customers/index.ts
export { CustomersTable } from "./ui/customers-table";
export { CustomerHeader } from "./ui/customer-header";
export { CustomerTabs } from "./ui/customer-tabs";
export { TabOverview } from "./ui/tab-overview";
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(app\)/customers/ frontend/src/features/customers/
git commit -m "feat(customers): add customer detail page with overview tab"
```

---

## Chunk 3: CRM Tab (contacts, addresses, calls, meetings, notes)

### Task 10: CRM Tab with Sub-tabs

**Files:**
- Create: `frontend/src/features/customers/ui/tab-crm.tsx`

- [ ] **Step 1: Create CRM tab**

Sub-tab navigation (pills) + content sections. Contacts is a table, Addresses is cards, Calls/Meetings are chronological lists, Notes is a textarea.

```typescript
// features/customers/ui/tab-crm.tsx
"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Customer, CustomerContact } from "@/entities/customer";

interface Props {
  customer: Customer;
  contacts: CustomerContact[];
}

type SubTab = "contacts" | "addresses" | "calls" | "meetings" | "notes";

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "contacts", label: "Контакты" },
  { key: "addresses", label: "Адреса" },
  { key: "calls", label: "Звонки" },
  { key: "meetings", label: "Встречи" },
  { key: "notes", label: "Заметки" },
];

export function TabCRM({ customer, contacts }: Props) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("contacts");

  return (
    <div>
      {/* Sub-tab pills */}
      <div className="flex gap-2 mb-6">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSubTab(tab.key)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              activeSubTab === tab.key
                ? "bg-blue-100 text-blue-700 font-medium"
                : "text-slate-500 hover:bg-slate-100"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeSubTab === "contacts" && <ContactsSection contacts={contacts} />}
      {activeSubTab === "addresses" && <AddressesSection customer={customer} />}
      {activeSubTab === "calls" && <PlaceholderSection name="Звонки" />}
      {activeSubTab === "meetings" && <PlaceholderSection name="Встречи" />}
      {activeSubTab === "notes" && <NotesSection notes={customer.notes} />}
    </div>
  );
}

function ContactsSection({ contacts }: { contacts: CustomerContact[] }) {
  if (contacts.length === 0) {
    return <p className="text-slate-400 py-8 text-center">Нет контактов</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ФИО</TableHead>
          <TableHead>Должность</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Телефон</TableHead>
          <TableHead>Заметки</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {contacts.map((c) => (
          <TableRow key={c.id}>
            <TableCell className="font-medium">
              {c.name}
              {c.is_primary && <span className="ml-1 text-yellow-500" title="Основной">★</span>}
              {c.is_lpr && <span className="ml-1 text-blue-500 text-xs">ЛПР</span>}
            </TableCell>
            <TableCell className="text-slate-500">{c.position ?? "—"}</TableCell>
            <TableCell>
              {c.email ? (
                <a href={`mailto:${c.email}`} className="text-blue-600 hover:underline">
                  {c.email}
                </a>
              ) : "—"}
            </TableCell>
            <TableCell>
              {c.phone ? (
                <a href={`tel:${c.phone}`} className="text-blue-600 hover:underline">
                  {c.phone}
                </a>
              ) : "—"}
            </TableCell>
            <TableCell className="text-slate-500 max-w-[200px] truncate">
              {c.notes ?? "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function AddressesSection({ customer }: { customer: Customer }) {
  const addresses = [
    { label: "Юридический", value: customer.legal_address },
    { label: "Фактический", value: customer.actual_address },
    { label: "Почтовый", value: customer.postal_address },
  ];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Официальные адреса</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {addresses.map((addr) => (
            <div key={addr.label}>
              <div className="text-xs font-semibold text-slate-400 uppercase">{addr.label}</div>
              <div className="text-sm">{addr.value || "Не указан"}</div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Склады</CardTitle>
        </CardHeader>
        <CardContent>
          {customer.warehouse_addresses && customer.warehouse_addresses.length > 0 ? (
            <div className="space-y-2">
              {customer.warehouse_addresses.map((wh, i) => (
                <div key={i} className="text-sm">
                  {wh.label && <span className="font-medium">{wh.label}: </span>}
                  {wh.address}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400 text-sm">Нет адресов складов</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function NotesSection({ notes }: { notes: string | null }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Заметки / Примечания</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm whitespace-pre-wrap">
          {notes || "Нет заметок"}
        </p>
      </CardContent>
    </Card>
  );
}

function PlaceholderSection({ name }: { name: string }) {
  return (
    <div className="py-8 text-center text-slate-400">
      {name} — в разработке
    </div>
  );
}
```

- [ ] **Step 2: Wire CRM tab into detail page**

In `app/(app)/customers/[id]/page.tsx`, replace the CRM placeholder:

```typescript
// Replace: {tab === "crm" && <PlaceholderTab name="CRM" />}
// With:
{tab === "crm" && <CRMContent customerId={id} customer={customer} />}

// Add async component:
async function CRMContent({
  customerId,
  customer,
}: {
  customerId: string;
  customer: Customer;
}) {
  const contacts = await fetchCustomerContacts(customerId);
  return <TabCRM customer={customer} contacts={contacts} />;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/customers/
git commit -m "feat(customers): add CRM tab with contacts, addresses, notes"
```

---

## Chunk 4: Documents Tab + Positions Tab + Final Wiring

### Task 11: Documents Tab

**Files:**
- Create: `frontend/src/features/customers/ui/tab-documents.tsx`

- [ ] **Step 1: Create documents tab**

Sub-tabs: КП, Спецификации, Договоры — each shows a table.

```typescript
// features/customers/ui/tab-documents.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";

interface Quote {
  id: string;
  idn: string;
  total_amount: number | null;
  profit_amount: number | null;
  created_at: string;
  status: string;
}

interface Spec {
  id: string;
  idn: string;
  total_amount: number | null;
  profit_amount: number | null;
  created_at: string;
  status: string;
}

interface Props {
  quotes: Quote[];
  specs: Spec[];
  initialSubTab?: string;
}

type SubTab = "quotes" | "specs" | "contracts";

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "quotes", label: "КП" },
  { key: "specs", label: "Спецификации" },
  { key: "contracts", label: "Договоры" },
];

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  calculating: "Расчёт",
  calculated: "Рассчитан",
  in_review: "На проверке",
  approved: "Одобрен",
  rejected: "Отклонён",
  cancelled: "Отменён",
  signed: "Подписана",
  active: "Активна",
  completed: "Завершена",
};

export function TabDocuments({ quotes, specs, initialSubTab }: Props) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>(
    (initialSubTab as SubTab) ?? "quotes"
  );

  function formatDate(d: string) {
    return new Date(d).toLocaleDateString("ru-RU");
  }

  function formatAmount(n: number | null) {
    if (n == null) return "—";
    return `$${n.toLocaleString("ru-RU")}`;
  }

  return (
    <div>
      <div className="flex gap-2 mb-6">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSubTab(tab.key)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              activeSubTab === tab.key
                ? "bg-blue-100 text-blue-700 font-medium"
                : "text-slate-500 hover:bg-slate-100"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeSubTab === "quotes" && (
        <DocumentTable
          items={quotes}
          emptyText="Нет КП"
          linkPrefix="/quotes"
          formatDate={formatDate}
          formatAmount={formatAmount}
        />
      )}
      {activeSubTab === "specs" && (
        <DocumentTable
          items={specs}
          emptyText="Нет спецификаций"
          linkPrefix="/specifications"
          formatDate={formatDate}
          formatAmount={formatAmount}
        />
      )}
      {activeSubTab === "contracts" && (
        <div className="py-8 text-center text-slate-400">
          Договоры — в разработке
        </div>
      )}
    </div>
  );
}

function DocumentTable({
  items,
  emptyText,
  linkPrefix,
  formatDate,
  formatAmount,
}: {
  items: { id: string; idn: string; total_amount: number | null; profit_amount: number | null; created_at: string; status: string }[];
  emptyText: string;
  linkPrefix: string;
  formatDate: (d: string) => string;
  formatAmount: (n: number | null) => string;
}) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-slate-400">{emptyText}</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>№</TableHead>
          <TableHead>Сумма</TableHead>
          <TableHead>Профит</TableHead>
          <TableHead>Дата</TableHead>
          <TableHead>Статус</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell>
              <Link
                href={`${linkPrefix}/${item.id}`}
                className="text-blue-600 hover:underline font-medium"
              >
                {item.idn}
              </Link>
            </TableCell>
            <TableCell className="tabular-nums">{formatAmount(item.total_amount)}</TableCell>
            <TableCell className="tabular-nums">{formatAmount(item.profit_amount)}</TableCell>
            <TableCell className="text-slate-500">{formatDate(item.created_at)}</TableCell>
            <TableCell>
              <Badge variant="secondary">{STATUS_LABELS[item.status] ?? item.status}</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Add quotes/specs queries to entity**

Add to `entities/customer/queries.ts`:

```typescript
export async function fetchCustomerQuotes(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("quotes")
    .select("id, idn, total_amount, profit_amount, created_at, status")
    .eq("customer_id", customerId)
    .order("created_at", { ascending: false });
  return data ?? [];
}

export async function fetchCustomerSpecs(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("specifications")
    .select("id, idn, total_amount, profit_amount, created_at, status")
    .eq("customer_id", customerId)
    .order("created_at", { ascending: false });
  return data ?? [];
}
```

- [ ] **Step 3: Wire into detail page**

Replace Documents placeholder in `customers/[id]/page.tsx`:

```typescript
{tab === "documents" && <DocumentsContent customerId={id} subtab={subtab} />}

async function DocumentsContent({ customerId, subtab }: { customerId: string; subtab?: string }) {
  const [quotes, specs] = await Promise.all([
    fetchCustomerQuotes(customerId),
    fetchCustomerSpecs(customerId),
  ]);
  return <TabDocuments quotes={quotes} specs={specs} initialSubTab={subtab} />;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/customers/ frontend/src/entities/customer/
git commit -m "feat(customers): add documents tab with KP and specs tables"
```

---

### Task 12: Positions Tab (stub)

**Files:**
- Create: `frontend/src/features/customers/ui/tab-positions.tsx`

- [ ] **Step 1: Create positions tab stub**

Positions are complex (requested_items across quotes). Ship as read-only table.

```typescript
// features/customers/ui/tab-positions.tsx
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";

interface Position {
  id: string;
  product_name: string;
  brand: string | null;
  sku: string | null;
  quantity: number | null;
  quote_idn: string;
}

interface Props {
  positions: Position[];
}

export function TabPositions({ positions }: Props) {
  if (positions.length === 0) {
    return <p className="py-8 text-center text-slate-400">Нет запрошенных позиций</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Наименование</TableHead>
          <TableHead>Бренд</TableHead>
          <TableHead>Артикул</TableHead>
          <TableHead className="text-right">Кол-во</TableHead>
          <TableHead>КП</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {positions.map((p) => (
          <TableRow key={p.id}>
            <TableCell className="font-medium">{p.product_name}</TableCell>
            <TableCell className="text-slate-500">{p.brand ?? "—"}</TableCell>
            <TableCell className="text-slate-500">{p.sku ?? "—"}</TableCell>
            <TableCell className="text-right tabular-nums">{p.quantity ?? "—"}</TableCell>
            <TableCell className="text-blue-600">{p.quote_idn}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Add query and wire into detail page**

Add to `entities/customer/queries.ts`:

```typescript
export async function fetchCustomerPositions(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("quote_items")
    .select("id, product_name, brand, sku, quantity, quotes!inner(idn, customer_id)")
    .eq("quotes.customer_id", customerId)
    .order("created_at", { ascending: false })
    .limit(100);

  return (data ?? []).map((row: any) => ({
    id: row.id,
    product_name: row.product_name,
    brand: row.brand,
    sku: row.sku,
    quantity: row.quantity,
    quote_idn: row.quotes?.idn ?? "—",
  }));
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/customers/ frontend/src/entities/customer/
git commit -m "feat(customers): add positions tab with quote items table"
```

---

### Task 13: Final Integration + Deploy

- [ ] **Step 1: Update barrel exports**

Ensure `features/customers/index.ts` exports all components.

- [ ] **Step 2: Build check**

```bash
cd frontend && npm run build
```

Fix any TypeScript errors.

- [ ] **Step 3: Commit and push**

```bash
git add -A
git commit -m "feat(customers): complete customers page migration (list + detail 4-tab layout)"
git push origin main
```

- [ ] **Step 4: Apply migration on VPS**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -f -" < migrations/188_customer_quote_counts.sql
```

- [ ] **Step 5: Wait for deploy, then browser-test**

Test checklist:
- `/customers` — list loads with search, pagination, columns
- `/customers/{id}` — overview tab shows requisites + counters
- `/customers/{id}?tab=crm` — contacts table, addresses cards, notes
- `/customers/{id}?tab=documents` — KP and specs tables
- `/customers/{id}?tab=positions` — positions table
