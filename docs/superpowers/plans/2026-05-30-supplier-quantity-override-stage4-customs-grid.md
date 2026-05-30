# Supplier-quantity override — Stage 4 (customs grid) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** The customs workspace grid («Кол-во» column) shows the **effective** (supplier-overridden) quantity, like the calc/picker/cargo surfaces.

**Architecture:** Helper-only (no DB column). The grid's `itemToRow` reads `quote_items.quantity` (ordered) + a `supplierByQuoteItemId` map (built in `customs-step.tsx` from the selected invoice_item via coverage). Thread `minimum_order_quantity` through that map and apply `effectiveQuantity(ordered, supplierQty)` in `itemToRow`. The inline map type `{ supplier_country; invoice_id }` is duplicated at 6 sites — extract a shared `SupplierByQuoteItem` type (in the leaf file `customs-handsontable.tsx`) and reuse it, adding the new field once.

**Tech Stack:** Next.js 15 (FSD), TypeScript, vitest. No `node_modules` locally → rely on CI.

---

## File Structure

| File | Change |
|---|---|
| `customs-step/customs-handsontable.tsx` | Export `SupplierByQuoteItem` (adds `minimum_order_quantity`); use it at 2 sites; export `itemToRow`; apply `effectiveQuantity` to the quantity cell; import the shared helper |
| `customs-step/customs-step.tsx` | Import + use `SupplierByQuoteItem` (3 sites); add `minimum_order_quantity` to the coverage select + map value |
| `customs-step/customs-items-editor.tsx` | Import + use `SupplierByQuoteItem` (1 site) |
| `customs-step/__tests__/customs-itemToRow-effective-qty.test.ts` | **Create** — unit-test `itemToRow` quantity = effective |

---

### Task 1: shared type + effective qty in the grid (customs-handsontable.tsx)

- [ ] **Step 1: Write the failing test** — `customs-step/__tests__/customs-itemToRow-effective-qty.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { itemToRow, type SupplierByQuoteItem } from "../customs-handsontable";
import type { QuoteItemRow } from "@/entities/quote/queries";

function item(over: Record<string, unknown> = {}): QuoteItemRow {
  return {
    id: "qi-1",
    position: 1,
    brand: "B",
    product_code: "PC",
    product_name: "P",
    quantity: 32,
    ...over,
  } as unknown as QuoteItemRow;
}

function supplierMap(
  entry: Partial<SupplierByQuoteItem> = {}
): Map<string, SupplierByQuoteItem> {
  return new Map([
    [
      "qi-1",
      {
        supplier_country: "CN",
        invoice_id: "inv-1",
        minimum_order_quantity: null,
        ...entry,
      },
    ],
  ]);
}

describe("itemToRow — effective quantity (supplier override)", () => {
  it("shows effective qty (override UP)", () => {
    const row = itemToRow(item({ quantity: 32 }), new Map(), supplierMap({ minimum_order_quantity: 738 }));
    expect(row.quantity).toBe(738);
  });
  it("shows effective qty (override DOWN)", () => {
    const row = itemToRow(item({ quantity: 20 }), new Map(), supplierMap({ minimum_order_quantity: 10 }));
    expect(row.quantity).toBe(10);
  });
  it("falls back to ordered when supplier qty unset", () => {
    const row = itemToRow(item({ quantity: 7 }), new Map(), supplierMap({ minimum_order_quantity: null }));
    expect(row.quantity).toBe(7);
  });
  it("falls back to ordered when no supplier map entry", () => {
    const row = itemToRow(item({ quantity: 5 }), new Map(), new Map());
    expect(row.quantity).toBe(5);
  });
});
```

- [ ] **Step 2: Run it — verify it fails** (`itemToRow`/`SupplierByQuoteItem` not exported).

Run: `cd frontend && npx vitest run src/features/quotes/ui/customs-step/__tests__/customs-itemToRow-effective-qty.test.ts`

- [ ] **Step 3: customs-handsontable.tsx edits.**

3a. Add the shared helper import (after the `@/shared/lib/hs-code` import):
```ts
import { effectiveQuantity } from "@/shared/lib/effective-quantity";
```

3b. Add the exported shared type (just before `function itemToRow(`):
```ts
/**
 * Per-quote_item supplier facts resolved from the selected invoice_item
 * (via composition coverage in customs-step.tsx). `minimum_order_quantity`
 * is the supplier-quantity override (effective qty when > 0).
 */
export interface SupplierByQuoteItem {
  supplier_country: string | null;
  invoice_id: string | null;
  minimum_order_quantity: number | null;
}
```

3c. Make `itemToRow` exported and use the shared type for `supplierByQi`:
```ts
export function itemToRow(
  item: QuoteItemRow,
  invoiceCountryMap: Map<string, string>,
  supplierByQi: Map<string, SupplierByQuoteItem>,
): RowData {
```

3d. Apply the override to the quantity cell. Change `quantity: item.quantity,` (in the returned object) to:
```ts
    quantity: effectiveQuantity(
      item.quantity,
      supplier?.minimum_order_quantity ?? null
    ),
```
(`supplier` is already `supplierByQi.get(item.id) ?? null` at the top of the function.)

3e. Update the component prop type — replace the inline map type in `CustomsHandsontableProps`:
```ts
  supplierByQuoteItemId: Map<string, SupplierByQuoteItem>;
```

- [ ] **Step 4: Run the test — verify it passes.** Same command as Step 2 → PASS.

---

### Task 2: thread `minimum_order_quantity` through the customs-step hook

- [ ] **Step 1: Import the shared type** in `customs-step.tsx` (with the other `./customs-handsontable`/sibling imports — add):
```ts
import type { SupplierByQuoteItem } from "./customs-handsontable";
```

- [ ] **Step 2: Replace the 3 inline map types** in `useSupplierByQuoteItemId` (the return type, the `useState` generic, and the `result` Map) — each currently `Map<string, { supplier_country: string | null; invoice_id: string | null }>` → `Map<string, SupplierByQuoteItem>`.

- [ ] **Step 3: Add `minimum_order_quantity` to the coverage select** (currently `"quote_item_id, invoice_items!inner(invoice_id, supplier_country)"`):
```ts
        .select(
          "quote_item_id, invoice_items!inner(invoice_id, supplier_country, minimum_order_quantity)"
        )
```

- [ ] **Step 4: Add it to the row type + the rowsByQi value type + the result map value.**

The cast row type (`for (const row of (data ?? []) as unknown as Array<{ quote_item_id; invoice_items: { invoice_id; supplier_country } }>`) → add `minimum_order_quantity: number | null;` to `invoice_items`.

The `rowsByQi` value type (`Array<{ invoice_id; supplier_country }>`) → add `minimum_order_quantity: number | null;`.

In the result-building loop, the `result.set(qi.id, { supplier_country: ..., invoice_id: ... })` gains:
```ts
        result.set(qi.id, {
          supplier_country: match?.supplier_country ?? null,
          invoice_id: match?.invoice_id ?? null,
          minimum_order_quantity: match?.minimum_order_quantity ?? null,
        });
```

- [ ] **Step 5: customs-items-editor.tsx** — import `SupplierByQuoteItem` from `./customs-handsontable` and replace its 1 inline map-type occurrence with `Map<string, SupplierByQuoteItem>`.

- [ ] **Step 6: Type-check.** Run: `cd frontend && npx tsc --noEmit` → PASS (all 6 former inline sites now reference the shared type).

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx \
        frontend/src/features/quotes/ui/customs-step/customs-step.tsx \
        frontend/src/features/quotes/ui/customs-step/customs-items-editor.tsx \
        frontend/src/features/quotes/ui/customs-step/__tests__/customs-itemToRow-effective-qty.test.ts \
        docs/superpowers/plans/2026-05-30-supplier-quantity-override-stage4-customs-grid.md
git commit -m "feat(customs): grid Кол-во column shows effective supplier-override qty"
```

---

## Self-Review

**1. Spec coverage** (spec §4 "Customs | customs-handsontable | show effective"): `itemToRow` quantity = `effectiveQuantity(...)`. ✅

**2. Placeholders:** none — exact code per step. ✅

**3. Type consistency:** `SupplierByQuoteItem` defined once in the leaf `customs-handsontable.tsx`, imported by `customs-step.tsx` + `customs-items-editor.tsx` (no cycle — the leaf imports neither). The hook's select, row cast, `rowsByQi`, and result map all carry `minimum_order_quantity: number | null`, matching the type. ✅

**Out of scope (later):** customer exports + KP (Stage 5), procurement rename + retire `isMoqViolation` (Stage 6). The customs grid quantity is a read-only display column — no hint/tooltip added (a handsontable cell renderer change is out of scope; the effective number is the requirement).
