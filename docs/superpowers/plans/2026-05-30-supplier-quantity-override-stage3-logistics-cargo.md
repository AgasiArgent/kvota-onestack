# Supplier-quantity override — Stage 3 (logistics cargo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** The logistics/customs cargo summary («Сводка по заказу» → per-invoice «Кол-во» and «Стоимость») reflects the **effective** (supplier-overridden) quantity, and the override rule helper is relocated to the `shared` layer so non-feature layers can use it.

**Architecture:** Helper-only (no DB column — decided 2026-05-30: no out-of-app SQL consumers). Two parts: (1) **relocate** `effectiveQuantity` from `features/quotes/ui/procurement-step/moq-warning.ts` to `shared/lib/effective-quantity.ts` (FSD: the `entities/quote/queries.ts` cargo rollup is in the *entities* layer and may not import from *features*); (2) the cargo rollup in `fetchQuoteInvoices` aggregates `effectiveQuantity(quantity, minimum_order_quantity)` instead of raw `quantity`, for both `total_quantity` and `total_amount_original`. The rollup loop is extracted into a pure, unit-testable helper.

**Tech Stack:** Next.js 15 (FSD), TypeScript, vitest. No `node_modules` locally → rely on CI; commands listed per step.

---

## File Structure

| File | Change |
|---|---|
| `frontend/src/shared/lib/effective-quantity.ts` | **Create** — move `effectiveQuantity` here (pure, dependency-free) |
| `frontend/src/shared/lib/__tests__/effective-quantity.test.ts` | **Create** — move the `effectiveQuantity` unit tests here |
| `frontend/src/features/quotes/ui/procurement-step/moq-warning.ts` | Remove `effectiveQuantity` (keep `isMoqViolation` + `MoqCheckable`) |
| `frontend/src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts` | Drop the `effectiveQuantity` import + describe block (keep `isMoqViolation`) |
| `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx` | Import `effectiveQuantity` from `@/shared/lib/effective-quantity` |
| `frontend/src/features/quotes/ui/calculation-step/calculation-results.tsx` | Import `effectiveQuantity` from `@/shared/lib/effective-quantity` |
| `frontend/src/entities/quote/queries.ts` | Extract rollup → `rollupInvoiceItemsByInvoice`; use effective qty; add `minimum_order_quantity` to the select |
| `frontend/src/entities/quote/__tests__/invoice-items-rollup.test.ts` | **Create** — unit-test the rollup (effective up/down/unset, amount) |

---

### Task 1: Relocate `effectiveQuantity` to the shared layer (pure refactor, no behavior change)

**Files:** create `shared/lib/effective-quantity.ts` + `shared/lib/__tests__/effective-quantity.test.ts`; edit `moq-warning.ts`, `moq-warning.test.ts`, `composition-picker.tsx`, `calc-results.tsx`.

- [ ] **Step 1: Create the shared helper** — `frontend/src/shared/lib/effective-quantity.ts`:

```ts
/**
 * Effective per-line quantity. When the supplier quantity is set (non-null,
 * > 0) it OVERRIDES the ordered quantity in both directions; otherwise the
 * ordered quantity stands (null → 0). Mirrors the backend
 * `effective_calc_quantity` helper (same `> 0` rule). Single in-app definition
 * of the supplier-quantity override rule (2026-05-29); lives in `shared` so
 * every FSD layer (entities, features) can import it.
 */
export function effectiveQuantity(
  ordered: number | null,
  supplierQty: number | null
): number {
  if (supplierQty != null && supplierQty > 0) return supplierQty;
  return ordered ?? 0;
}
```

- [ ] **Step 2: Create the shared test** — `frontend/src/shared/lib/__tests__/effective-quantity.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { effectiveQuantity } from "../effective-quantity";

describe("effectiveQuantity", () => {
  it("overrides up when supplier qty is higher", () => {
    expect(effectiveQuantity(5, 10)).toBe(10);
  });
  it("overrides DOWN when supplier qty is lower", () => {
    expect(effectiveQuantity(10, 5)).toBe(5);
  });
  it("equal", () => { expect(effectiveQuantity(10, 10)).toBe(10); });
  it("unset → ordered", () => { expect(effectiveQuantity(5, null)).toBe(5); });
  it("zero → ordered", () => { expect(effectiveQuantity(5, 0)).toBe(5); });
  it("negative → ordered", () => { expect(effectiveQuantity(5, -3)).toBe(5); });
  it("null ordered + set supplier qty → supplier qty", () => {
    expect(effectiveQuantity(null, 10)).toBe(10);
  });
});
```

- [ ] **Step 3: Remove `effectiveQuantity` from `moq-warning.ts`** — delete the function + its doc comment (the block starting `/** \n * Effective per-line quantity.` through the closing `}`). Keep `MoqCheckable` and `isMoqViolation` untouched.

- [ ] **Step 4: Update `moq-warning.test.ts`** — change line 2 to `import { isMoqViolation } from "../moq-warning";` and delete the entire `describe("effectiveQuantity", ...)` block (lines 42-56). Keep the `isMoqViolation` describe.

- [ ] **Step 5: Update the two importers** — in `composition-picker.tsx` and `calc-results.tsx`, replace:
  `import { effectiveQuantity } from "../procurement-step/moq-warning";`
  with:
  `import { effectiveQuantity } from "@/shared/lib/effective-quantity";`
  (composition-picker.tsx imports other things from moq-warning? No — only effectiveQuantity at line 42. calc-results.tsx imports only effectiveQuantity. Both become a single shared import.)

- [ ] **Step 6: Type-check + run moved tests**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/shared/lib/__tests__/effective-quantity.test.ts src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts`
Expected: PASS, no type errors (all importers resolve the new path).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/shared/lib/effective-quantity.ts \
        frontend/src/shared/lib/__tests__/effective-quantity.test.ts \
        frontend/src/features/quotes/ui/procurement-step/moq-warning.ts \
        frontend/src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts \
        frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx \
        frontend/src/features/quotes/ui/calculation-step/calculation-results.tsx
git commit -m "refactor(calc): move effectiveQuantity helper to shared layer (FSD)"
```

---

### Task 2: Cargo rollup aggregates the effective quantity

**Files:** `frontend/src/entities/quote/queries.ts`; create `frontend/src/entities/quote/__tests__/invoice-items-rollup.test.ts`.

- [ ] **Step 1: Write the failing rollup test** — `frontend/src/entities/quote/__tests__/invoice-items-rollup.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { rollupInvoiceItemsByInvoice } from "../queries";

function row(over: Partial<Parameters<typeof rollupInvoiceItemsByInvoice>[0][number]> = {}) {
  return {
    invoice_id: "inv-1",
    quantity: 10,
    minimum_order_quantity: null,
    purchase_price_original: 100,
    purchase_currency: "USD",
    invoice_item_coverage: [{ quote_items: { unit: "шт" } }],
    ...over,
  };
}

describe("rollupInvoiceItemsByInvoice — effective quantity", () => {
  it("sums effective qty (override UP) and price × effective", () => {
    // ordered 5, supplier 10 → effective 10; amount 100 × 10 = 1000
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: 5, minimum_order_quantity: 10 }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBe(10);
    expect(agg.total_amount_original).toBe(1000);
  });

  it("sums effective qty (override DOWN)", () => {
    // ordered 20, supplier 5 → effective 5; amount 100 × 5 = 500
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: 20, minimum_order_quantity: 5 }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBe(5);
    expect(agg.total_amount_original).toBe(500);
  });

  it("uses ordered qty when supplier qty unset", () => {
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: 7, minimum_order_quantity: null, purchase_price_original: 100 }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBe(7);
    expect(agg.total_amount_original).toBe(700);
  });

  it("aggregates units and keeps total null when no quantity contributes", () => {
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: null, purchase_price_original: null }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBeNull();
    expect(agg.units.has("шт")).toBe(true);
  });
});
```

- [ ] **Step 2: Run it — verify it fails**

Run: `cd frontend && npx vitest run src/entities/quote/__tests__/invoice-items-rollup.test.ts`
Expected: FAIL — `rollupInvoiceItemsByInvoice` is not exported.

- [ ] **Step 3: Add the shared import** — at the top of `queries.ts`, after the existing `@/shared/lib/*` imports:

```ts
import { effectiveQuantity } from "@/shared/lib/effective-quantity";
```

- [ ] **Step 4: Add `minimum_order_quantity` to the cargo select + inline row type** in `fetchQuoteInvoices`.

Change the select string (currently `"invoice_id, quantity, purchase_price_original, purchase_currency, invoice_item_coverage!inner(quote_items!inner(unit))"`) to add `minimum_order_quantity`:

```ts
        .select(
          "invoice_id, quantity, minimum_order_quantity, purchase_price_original, purchase_currency, invoice_item_coverage!inner(quote_items!inner(unit))"
        )
```

And add `minimum_order_quantity: number | null;` to the inline `data: Array<{ ... }>` row type (right after `quantity: number | null;`).

- [ ] **Step 5: Extract the rollup loop into a pure exported helper.** Replace the inline `const aggregatesByInvoice = new Map...` loop (the `for (const row of invoiceItemsRes.data ?? [])` block) with a call:

```ts
  const aggregatesByInvoice = rollupInvoiceItemsByInvoice(invoiceItemsRes.data ?? []);
```

and add this exported helper near `InvoiceItemsAggregate` (after the `interface InvoiceItemsAggregate` block):

```ts
/** Input row shape for {@link rollupInvoiceItemsByInvoice}. */
export interface InvoiceItemAggRow {
  invoice_id: string;
  quantity: number | null;
  minimum_order_quantity: number | null;
  purchase_price_original: number | null;
  purchase_currency: string | null;
  invoice_item_coverage: Array<{ quote_items: { unit: string | null } | null }>;
}

/**
 * Roll up invoice_items into a per-invoice aggregate for the cargo summary.
 * `total_quantity` / `total_amount_original` use the EFFECTIVE quantity
 * (supplier override), so a supplier minimum/short stock is reflected in the
 * cargo «Кол-во» and «Стоимость». Nulls are preserved (no contributing row →
 * total stays null) so the UI shows «—» vs «0».
 */
export function rollupInvoiceItemsByInvoice(
  rows: InvoiceItemAggRow[]
): Map<string, InvoiceItemsAggregate> {
  const aggregatesByInvoice = new Map<string, InvoiceItemsAggregate>();
  for (const row of rows) {
    const prev = aggregatesByInvoice.get(row.invoice_id) ?? {
      total_quantity: null,
      total_amount_original: null,
      currency: null,
      units: new Set<string>(),
    };
    if (row.quantity != null) {
      const eff = effectiveQuantity(row.quantity, row.minimum_order_quantity);
      prev.total_quantity = (prev.total_quantity ?? 0) + eff;
      if (row.purchase_price_original != null) {
        prev.total_amount_original =
          (prev.total_amount_original ?? 0) + row.purchase_price_original * eff;
      }
    }
    if (!prev.currency && row.purchase_currency) {
      prev.currency = row.purchase_currency;
    }
    for (const cov of row.invoice_item_coverage ?? []) {
      const unit = cov.quote_items?.unit?.trim();
      if (unit) prev.units.add(unit);
    }
    aggregatesByInvoice.set(row.invoice_id, prev);
  }
  return aggregatesByInvoice;
}
```

(Note: the original had two separate `if` guards — `if (row.quantity != null)` for total_quantity and `if (purchase_price_original != null && row.quantity != null)` for amount. The refactor nests the amount under the quantity guard since both require `quantity != null` — behaviorally identical, and `eff` is computed once.)

- [ ] **Step 6: Run the rollup test — verify it passes**

Run: `cd frontend && npx vitest run src/entities/quote/__tests__/invoice-items-rollup.test.ts`
Expected: PASS.

- [ ] **Step 7: Type-check the frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/entities/quote/queries.ts \
        frontend/src/entities/quote/__tests__/invoice-items-rollup.test.ts
git commit -m "feat(logistics): cargo summary reflects effective (supplier-override) qty"
```

---

## Self-Review

**1. Spec coverage** (spec §4 "Logistics | invoice-cargo-summary.tsx | show effective"): the cargo `total_quantity`/`total_amount_original` now aggregate the effective qty. `InvoiceCargoSummary` reads `aggregate.total_quantity` verbatim → no component change needed. ✅

**2. Placeholder scan:** every step has exact code/commands. ✅

**3. Type consistency:** `rollupInvoiceItemsByInvoice(rows: InvoiceItemAggRow[]): Map<string, InvoiceItemsAggregate>`; the inline select row type and `InvoiceItemAggRow` both add `minimum_order_quantity: number | null`; `effectiveQuantity(number|null, number|null): number` matches. The relocated helper keeps the exact signature, so `composition-picker`/`calc-results` callers are unchanged except the import path. ✅

**4. FSD:** helper now in `shared/lib` → `entities/quote/queries.ts` import is legal (entities → shared). ✅

**Out of scope (later stages):** customs grid (Stage 4), customer exports + KP (Stage 5), procurement rename + retire `isMoqViolation` (Stage 6).
