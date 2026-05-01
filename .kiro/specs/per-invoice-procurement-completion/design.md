# Design: Per-invoice procurement completion

## Overview

Перенос флага `procurement_completed_at` с уровня квоты на уровень инвойса. Все consumer queries (logistics, customs, dashboards) и UI-locks перерабатываются под новый scope. Quote-level флаг остаётся в БД (deprecated), но новой логикой не пишется и не читается.

## Architecture pattern & boundary map

| Слой | Файл | Что делает |
|---|---|---|
| **DB schema** | новая миграция (next free seq) | Add invoices.procurement_completed_at + _by |
| **Mutations** | entities/quote/mutations.ts | New: completeInvoiceProcurement, reopenInvoiceProcurement |
| **Lock state** | invoice-card.tsx | isLocked reads invoice prop, not quote prop |
| **Per-КП кнопка** | invoice-card.tsx header | New «Завершить закупку по КП» button |
| **Per-КП badge** | invoice-card.tsx header | New lifecycle badge (4 states) |
| **Customs queries** | (where they live) | Filter by invoice flag, regroup per-invoice |
| **Logistics queries** | (where they live) | Filter by invoice flag (semantics same) |
| **Quote progress badge** | quotes-list / dashboards | Derived "N/M КП" |
| **Quote-step header** | procurement-step.tsx | Remove top-level «Завершить закупку» |

## Technology stack & alignment

- React 19 + Next.js 15 — same as remaining frontend.
- Migration via existing `scripts/apply-migrations.sh` flow.
- Supabase JS direct — same client pattern as existing per-invoice mutations (e.g. `updateInvoice`, `addCargoPlace`).
- No new dependencies.

## DB migration

```sql
-- migrations/NNN_per_invoice_procurement_completion.sql
SET search_path TO kvota, public;

ALTER TABLE kvota.invoices
  ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS procurement_completed_by UUID REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_invoices_procurement_completed_at
  ON kvota.invoices(procurement_completed_at)
  WHERE procurement_completed_at IS NOT NULL;

COMMENT ON COLUMN kvota.invoices.procurement_completed_at IS
  'Per-invoice procurement completion timestamp. Replaces the legacy
   quotes.procurement_completed_at flag — each КП now finishes
   procurement independently.';
COMMENT ON COLUMN kvota.invoices.procurement_completed_by IS
  'Auth user who marked this invoice procurement complete.';
```

Quote-level `quotes.procurement_completed_at` остаётся в схеме до отдельной миграции-cleanup. Application-уровень его не пишет и не читает после этого PR.

## Mutations (additions)

```ts
// entities/quote/mutations.ts (additions)
export async function completeInvoiceProcurement(invoiceId: string): Promise<void> {
  const supabase = createClient();
  const { data: auth } = await supabase.auth.getUser();
  const userId = auth.user?.id ?? null;
  const { error } = await supabase
    .from("invoices")
    .update({
      procurement_completed_at: new Date().toISOString(),
      procurement_completed_by: userId,
    })
    .eq("id", invoiceId);
  if (error) throw error;
}

export async function reopenInvoiceProcurement(invoiceId: string): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase
    .from("invoices")
    .update({
      procurement_completed_at: null,
      procurement_completed_by: null,
    })
    .eq("id", invoiceId);
  if (error) throw error;
}
```

## InvoiceCard changes

### Lock derivation

```ts
// before
const procurementCompleted = quote.procurement_completed_at != null;
// after
const procurementCompleted =
  (invoice as { procurement_completed_at?: string | null }).procurement_completed_at != null;
```

The rest of the lock-check chain (`isLocked`, lock-respecting branches in render) doesn't change — same flag name, different source.

### Per-КП completion button

Inserted in the header action bar, next to the supplier name, gated on:
- `!procurementCompleted` (not already completed)
- `invoiceItems.length > 0` (have items to complete)

```tsx
{!procurementCompleted && invoiceItems.length > 0 && (
  <Button
    variant="ghost"
    size="sm"
    className="text-xs"
    onClick={async () => {
      try {
        await completeInvoiceProcurement(invoice.id);
        toast.success("Закупка по КП завершена");
        router.refresh();
        setRefreshKey((k) => k + 1);
      } catch (err) {
        toast.error(extractErrorMessage(err) ?? "Не удалось завершить");
      }
    }}
  >
    <CheckCircle2 size={14} className="mr-1" />
    Завершить закупку по КП
  </Button>
)}
```

`router.refresh()` обновляет server-rendered prop `invoice`; локальный `refreshKey++` пересчитывает eligibility maps.

### Lifecycle badge (4 states)

```tsx
function getInvoiceLifecycleStatus(
  invoice: InvoiceRow,
  hasLogisticsRoutes: boolean,
  hasCustomsRows: boolean,
): "in-work" | "procurement-done" | "logistics" | "customs" {
  const completed = invoice.procurement_completed_at != null;
  if (!completed) return "in-work";
  if (hasCustomsRows) return "customs";
  if (hasLogisticsRoutes) return "logistics";
  return "procurement-done";
}
```

`hasLogisticsRoutes` / `hasCustomsRows` — приходят как props или дополнительные fetched state. Для MVP — один extra query за все routes/customs, агрегированный per-invoice.

Badge label & colour:
- `in-work` → «В работе» / outline
- `procurement-done` → «Закупка завершена» / secondary
- `logistics` → «В логистике» / blue
- `customs` → «На таможне» / green

Plus completion date inline next to the badge: «Завершено 30.04».

### Re-open

`ProcurementUnlockButton` уже принимает `invoiceId`. Меняется его mutation: вместо clearing `quote.procurement_completed_at` — `invoice.procurement_completed_at`. Точечная правка внутри компонента.

## Customs query change

Locate the customs workspace queries. Two patterns to update:

1. **Items list** — currently joins quotes filtered by `procurement_completed_at IS NOT NULL`. Switch the filter to `invoice_items.invoice_id IN (SELECT id FROM invoices WHERE procurement_completed_at IS NOT NULL)`.
2. **Grouping** — surface invoice as a group key when displaying items, so the customs UI naturally clusters items by КП.

This is the largest unknown until I open the customs files. Worst case: one query helper to refactor + one list view to regroup.

## Logistics query change

Probable smaller change — verify the existing logistics workspace already filters per-invoice. If it filters by quote-level flag → swap to invoice-level. If already invoice-level → no change.

## Quote-level progress badge

Wherever the quote list/dashboards render the «закупка завершена» indicator, replace with derived value computed from invoice rows:

```ts
function getProcurementProgress(invoices: InvoiceRow[]): {
  completed: number;
  total: number;
  label: string;
} {
  const nonEmpty = invoices.filter((i) => i.items_count > 0); // or via a JOIN
  const total = nonEmpty.length;
  const completed = nonEmpty.filter((i) => i.procurement_completed_at != null).length;
  if (total === 0) return { completed: 0, total: 0, label: "" };
  if (completed === total) return { completed, total, label: "Закупка завершена" };
  return { completed, total, label: `${completed}/${total} КП завершено` };
}
```

## Removed surface

| Symbol | Where | Action |
|---|---|---|
| Top-level «Завершить закупку» button | procurement-step.tsx (or quote header) | Delete. Logic moves per-invoice. |
| Quote-level mutation that wrote `quotes.procurement_completed_at` | wherever it lives | Delete. |
| `quote.procurement_completed_at` reads | scattered | Replaced with per-invoice reads or derived progress. |

## Trade-offs and risks

1. **Quote-level legacy column.** Kept in DB to avoid touching exports/calc engine that may still inspect it. Application code stops writing/reading. A follow-up cleanup PR can drop the column once we've audited downstream consumers.
2. **Customs visibility partial.** When some КП are done and some aren't, customs sees a partial picture of the quote — that's intentional per Req 5.4. Customs should be able to start work on a 1-of-3 КП without waiting for the rest.
3. **Logistics pre-existing per-invoice handling.** If logistics already filters per-invoice (per user's hint), this is a no-op for them. If not, parity rolls in with this change.
4. **Lifecycle badge requires extra fetches** for hasLogisticsRoutes/hasCustomsRows. Trade-off: accuracy vs. extra round-trips. MVP — one batch query per page that returns counts per invoice. Cached for the page session.
5. **Re-open scope unchanged.** If a re-opened invoice has items already pulled into logistics/customs, the re-open doesn't auto-recall them. Out of scope; existing behaviour preserved.

## Test strategy

- Unit (Vitest) for the two new mutations: happy + error propagation. New file `procurement-completion.test.ts`.
- SSR sanity for InvoiceCard with new button + badge.
- Manual on localhost: create quote → 2 КП → complete one → verify lock + badge → second remains editable. Customs workspace shows only completed-КП items.

## Requirement traceability

| Req | Where addressed |
|---|---|
| 1.1-1.4 | Migration NNN |
| 2.1-2.5 | InvoiceCard header button + procurement-step.tsx removal |
| 3.1-3.5 | InvoiceCard isLocked source + ProcurementUnlockButton scope |
| 4.1-4.3 | InvoiceCard lifecycle badge component |
| 5.1-5.4 | Customs query refactor |
| 6.1-6.3 | Logistics query verification / refactor |
| 7.1-7.3 | Quote progress badge in lists/dashboards; legacy column deprecated |
| 8.1-8.4 | ProcurementUnlockButton scoped per-invoice |
| 9.1-9.5 | New mutations + tests + tsc/vitest |
