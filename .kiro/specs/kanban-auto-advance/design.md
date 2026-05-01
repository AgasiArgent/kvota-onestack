# Design: Kanban auto-advance

## Overview

Три точки авто-продвижения brand-slice'ов на канбане, привязанные к существующим Server Actions / mutations. Один общий хелпер `maybeAdvanceBrandSlices` инкапсулирует SQL-логику; вызывается с массивом (quote_id, brand) пар и целевым substatus'ом. На каждой точке вызова — свой набор аргументов.

## Architecture pattern

```
frontend/src/entities/quote/kanban-auto-advance.ts (NEW)
└─ maybeAdvanceBrandSlices(args) → records advanced rows in status_history

Phase A: assignBrandGroup (server-action)
  └─ after items update: maybeAdvanceBrandSlices({
       trigger: "distribution",
       slices: [(quote_id, brand)],
     })

Phase B: invoice send mutation
  └─ after sent_at: maybeAdvanceBrandSlices({
       trigger: "send",
       slices: <derived from invoice_items by brand>,
     })

Phase C: completeInvoiceProcurement (mutation)
  └─ after procurement_completed_at: maybeAdvanceBrandSlices({
       trigger: "procurement_complete",
       slices: <derived from invoice_items by brand>,
     })
```

The helper takes the trigger type so it knows which transition to attempt and which gate to evaluate. Single helper, three callsites, three transition rules.

## Helper contract

```ts
// frontend/src/entities/quote/kanban-auto-advance.ts

export type AdvanceTrigger =
  | "distribution"        // distributing → searching_supplier
  | "send"                // searching_supplier → waiting_prices
  | "procurement_complete"; // waiting_prices → prices_ready

export interface AdvanceArgs {
  trigger: AdvanceTrigger;
  /** Affected (quote_id, brand) pairs to evaluate. Brand="" for unbranded items. */
  slices: Array<{ quote_id: string; brand: string }>;
  /** auth.uid() of the caller — recorded as transitioned_by. */
  userId: string;
}

export async function maybeAdvanceBrandSlices(
  args: AdvanceArgs
): Promise<{ advanced: Array<{ quote_id: string; brand: string; to: string }> }>;
```

Internally:
- Uses `createAdminClient()` (caller already validated auth)
- Per (quote, brand): fetch current substatus, evaluate gate based on trigger, advance if gate passes
- Errors logged but never thrown (Req 5.2)
- Idempotent (Req 5.3): condition gates on substatus, so second invocation is a no-op

### Gate logic per trigger

| Trigger | Required current substatus | Gate (must hold to advance) | Target substatus |
|---|---|---|---|
| `distribution` | `distributing` | All `quote_items` of (q, b): `assigned_procurement_user IS NOT NULL OR is_unavailable IS TRUE` | `searching_supplier` |
| `send` | `searching_supplier` | True (no extra check — sender is the trigger) | `waiting_prices` |
| `procurement_complete` | `waiting_prices` | All `quote_items` of (q, b) where `is_unavailable IS NOT TRUE` are covered by at least one `invoice_item` belonging to an invoice with `procurement_completed_at IS NOT NULL` | `prices_ready` |

## Per-callsite plumbing

### Phase A: `assignBrandGroup` server-action

```ts
// entities/quote/server-actions.ts (extend existing)

export async function assignBrandGroup(itemIds, userId, pinBrand, orgId, brand) {
  // ... existing auth + update + brand-pin logic ...

  // NEW: collect (quote_id, brand) pairs from the items we just updated
  const { data: items } = await supabase
    .from("quote_items")
    .select("quote_id, brand")
    .in("id", itemIds);
  const slices = uniqueBy(items, (i) => `${i.quote_id}|${i.brand ?? ""}`)
    .map((i) => ({ quote_id: i.quote_id, brand: i.brand ?? "" }));

  // Best-effort auto-advance — never throws
  void maybeAdvanceBrandSlices({
    trigger: "distribution",
    slices,
    userId: user.id,
  });

  revalidatePath(...);
  return { success: true };
}
```

### Phase B: invoice "send" mutation

Need to find the existing mutation that sets `invoices.sent_at`. After it succeeds:

```ts
// derive distinct brands from invoice_items of this invoice
const { data: items } = await supabase
  .from("invoice_items")
  .select("brand")
  .eq("invoice_id", invoiceId);
const brands = unique((items ?? []).map((i) => i.brand ?? ""));

void maybeAdvanceBrandSlices({
  trigger: "send",
  slices: brands.map((b) => ({ quote_id: invoice.quote_id, brand: b })),
  userId,
});
```

### Phase C: `completeInvoiceProcurement` (already exists)

```ts
// entities/quote/mutations.ts — extend completeInvoiceProcurement

export async function completeInvoiceProcurement(invoiceId: string) {
  // ... existing update ...

  // NEW: derive (quote_id, brand) pairs and try to advance
  const { data: invoice } = await supabase
    .from("invoices")
    .select("quote_id")
    .eq("id", invoiceId)
    .single();
  const { data: items } = await supabase
    .from("invoice_items")
    .select("brand")
    .eq("invoice_id", invoiceId);
  const brands = unique((items ?? []).map((i) => i.brand ?? ""));

  void maybeAdvanceBrandSlices({
    trigger: "procurement_complete",
    slices: brands.map((b) => ({ quote_id: invoice.quote_id, brand: b })),
    userId: <auth uid>,
  });
}
```

## SQL strategy

### Phase A gate

```sql
SELECT bool_and(
  (qi.assigned_procurement_user IS NOT NULL OR qi.is_unavailable IS TRUE)
) AS all_routed
FROM kvota.quote_items qi
WHERE qi.quote_id = $1
  AND COALESCE(qi.brand, '') = $2;
```

### Phase B gate
No SQL gate — sender is the trigger. Just check current substatus = `searching_supplier`.

### Phase C gate

```sql
WITH brand_items AS (
  SELECT id FROM kvota.quote_items
  WHERE quote_id = $1 AND COALESCE(brand, '') = $2
    AND is_unavailable IS NOT TRUE
)
SELECT
  COUNT(bi.id) AS total,
  COUNT(DISTINCT cov.quote_item_id) FILTER (
    WHERE inv.procurement_completed_at IS NOT NULL
  ) AS covered
FROM brand_items bi
LEFT JOIN kvota.invoice_item_coverage cov
  ON cov.quote_item_id = bi.id
LEFT JOIN kvota.invoice_items ii ON ii.id = cov.invoice_item_id
LEFT JOIN kvota.invoices inv ON inv.id = ii.invoice_id;
```

Advance if `total > 0 AND total = covered`.

## Trade-offs and risks

1. **Best-effort vs blocking.** Auto-advance is fire-and-forget — failures don't roll back the originating action. Trade-off: kanban может пойти из синка с реальным состоянием. Альтернатива (block on failure) опаснее — пользователь не сможет назначить МОЗ если случайно пропала связь до DB. Идём с best-effort + логи в console.error.
2. **Idempotency without lock.** Без транзакции/локов два одновременных назначения МОЗ для одной квоты могут попытаться продвинуть одну и ту же brand-slice одновременно. UPDATE WHERE substatus = 'distributing' гарантирует, что только один действительно сработает (второй обновит 0 строк). status_history тогда получит одну запись от первого. Acceptable.
3. **Manual drag back.** Если МОЗ вручную перетащил карточку из `searching_supplier` обратно в `distributing` (откатил), и потом снова назначил МОЗ — auto-advance снова сработает. Это правильное поведение.
4. **Phase B: «send» механика.** Реальная mutation сейчас может быть Python endpoint или прямой Supabase update. Если Python — нужно либо вызвать TS-helper из frontend после успешного API-запроса, либо реплицировать логику в Python. Предпочтительно frontend-side — single source of auto-advance logic.
5. **Phase C dependency on per-invoice completion.** Phase C предполагает, что миграция 298 (`invoices.procurement_completed_at`) уже на месте — она там, applied. Если quote_items имеет позицию без coverage row (legacy data), gate вернёт `covered < total` и не продвинет. Это правильное поведение — manual drag решит.

## Test strategy

```
__tests__/kanban-auto-advance.test.ts (NEW):
  - distribution trigger:
      * full route → advance
      * partial route → no advance
      * already searching_supplier → no advance (idempotent)
      * is_unavailable items count as routed
  - send trigger:
      * searching_supplier → advance
      * waiting_prices (already advanced) → no advance
      * distributing → no advance (wrong starting state)
  - procurement_complete trigger:
      * all items covered by completed invoices → advance
      * one item uncovered → no advance
      * is_unavailable items skipped from coverage
      * already prices_ready → no advance
  - error handling: DB failure swallowed, no throw
```

Existing tests for `assignBrandGroup`, `completeInvoiceProcurement` continue to pass — auto-advance is a side-effect that the tests can stub out (vi.mock).

## Phasing

- **Phase A** — helper + Phase A wiring + tests. Ship as one PR.
- **Phase B** — locate send mutation, wire helper, add tests. Separate PR.
- **Phase C** — extend `completeInvoiceProcurement`, wire helper with `procurement_complete` trigger, add tests. Separate PR.

User's preference: ship Phase A first, get visual feedback, then B, then C.

## Requirement traceability

| Req | Where addressed |
|---|---|
| 1.1-1.6 | Phase A: helper + assignBrandGroup wiring |
| 2.1-2.5 | Phase B: helper + send mutation wiring |
| 3.1-3.6 | Phase C: helper + completeInvoiceProcurement wiring |
| 4.1-4.3 | Helper only advances forward; gates on current substatus |
| 5.1-5.4 | Helper uses admin client, swallows errors, idempotent UPDATE |
| 6.1-6.3 | Unit tests + suite green |
