# Supplier-quantity override — Stage 2 (calc-results table) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The calc-results table on the calculation step shows the **effective** (supplier-overridden) per-line quantity and line total, matching the composition picker and the calc engine.

**Architecture:** Frontend-only. Extend the existing `invoice_item_coverage` join in `calculation-step.tsx` to also pull `minimum_order_quantity`; build a `supplierQtyByQi` map (same selected-invoice matching the existing `priceByQi` already uses); add `minimum_order_quantity` to the `CalculationResultsItem` prop shape; in `calculation-results.tsx` render `effectiveQuantity(ordered, supplierQty)` (the shared helper — single in-app rule) with the picker's exact «кол-во поставщика: N» hint, and compute the line total from the effective quantity. **No DB/migration change** — the generated `effective_quantity` column is deferred to Stage 3 (its first single-value reader: the exports).

**Why this fixes a live bug:** After Stage 1 (PR #288) the calc engine uses the effective quantity, so the summary cards (Сумма с НДС / Профит / Маржа — written by the Python calc API) already reflect it. But the per-item table still renders `quote_items.quantity` (ordered) and an ordered-based line total. The two halves of the same screen disagree. This stage aligns them.

**Tech Stack:** Next.js 15 (App Router, FSD), TypeScript, vitest (SSR `renderToString` `.test.tsx` + jsdom `.dom.test.tsx`), shared `effectiveQuantity` helper in `features/quotes/ui/procurement-step/moq-warning.ts`.

**Cannot run tests locally** (no `node_modules` in this env) — rely on CI. Each task still specifies the exact command + expected result so CI (and a local dev) can verify.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `frontend/src/features/quotes/ui/calculation-step/calculation-results.tsx` | Presentational calc-results table (summary cards + per-item rows) | Add `minimum_order_quantity` to `CalculationResultsItem`; render effective qty + hint + effective line total |
| `frontend/src/features/quotes/ui/calculation-step/calculation-step.tsx` | Data loader — builds `CalculationResultsItem[]` from a coverage join | Pull `minimum_order_quantity` in the select; build `supplierQtyByQi`; pass it through (real path + placeholder) |
| `frontend/src/features/quotes/ui/calculation-step/__tests__/calculation-results.test.tsx` | SSR render regression | Add override up/down/unset cases |
| `frontend/src/features/quotes/ui/calculation-step/__tests__/calculation-results.dom.test.tsx` | jsdom render regression | Add effective-qty + hint case |

The shared helper `effectiveQuantity(ordered, supplierQty)` already exists and is used by the picker — **do not duplicate it**.

---

### Task 1: calc-results table renders the effective quantity + hint + effective line total

**Files:**
- Modify: `frontend/src/features/quotes/ui/calculation-step/calculation-results.tsx`
- Test: `frontend/src/features/quotes/ui/calculation-step/__tests__/calculation-results.test.tsx` (SSR)
- Test: `frontend/src/features/quotes/ui/calculation-step/__tests__/calculation-results.dom.test.tsx` (jsdom)

- [ ] **Step 1: Write the failing SSR tests**

Append to `calculation-results.test.tsx`. First update the local `makeItem` factory to carry the new optional field (add the line `minimum_order_quantity: null,` to the returned object inside `makeItem`), then add this describe block at the end of the file:

```tsx
describe("CalculationResults — supplier-quantity override (Stage 2)", () => {
  it("renders the effective quantity (override UP) and price × effective line total", () => {
    const quote = makeQuote();
    // ordered 5, supplier 10 → effective 10; price 100 → line total 1000
    const items = [
      makeItem({
        id: "a",
        product_name: "Болт",
        base_price_vat: 100,
        quantity: 5,
        minimum_order_quantity: 10,
      }),
    ];

    const html = renderToString(
      <CalculationResults quote={quote} items={items} />
    );

    expect(html).toContain("Болт");
    // effective qty 10 shown, not ordered 5
    expect(html).toContain("кол-во поставщика: 10");
    expect(html).toContain("заказано 5");
    // line total = 100 × 10 = 1000 (ru-RU groups with U+00A0)
    expect(html).toMatch(/1\s000,00/);
  });

  it("renders the effective quantity (override DOWN) and reduced line total", () => {
    const quote = makeQuote();
    // ordered 20, supplier 5 → effective 5; price 100 → line total 500
    const items = [
      makeItem({
        id: "a",
        product_name: "Гайка",
        base_price_vat: 100,
        quantity: 20,
        minimum_order_quantity: 5,
      }),
    ];

    const html = renderToString(
      <CalculationResults quote={quote} items={items} />
    );

    expect(html).toContain("кол-во поставщика: 5");
    expect(html).toContain("заказано 20");
    // line total = 100 × 5 = 500
    expect(html).toContain("500,00");
  });

  it("shows no hint and uses ordered qty when supplier qty is unset", () => {
    const quote = makeQuote();
    const items = [
      makeItem({
        id: "a",
        product_name: "Шайба",
        base_price_vat: 100,
        quantity: 7,
        minimum_order_quantity: null,
      }),
    ];

    const html = renderToString(
      <CalculationResults quote={quote} items={items} />
    );

    expect(html).not.toContain("кол-во поставщика");
    // line total = 100 × 7 = 700
    expect(html).toContain("700,00");
  });
});
```

- [ ] **Step 2: Run the SSR tests — verify they fail**

Run: `cd frontend && npx vitest run src/features/quotes/ui/calculation-step/__tests__/calculation-results.test.tsx`
Expected: FAIL — `minimum_order_quantity` is not on `CalculationResultsItem` (tsc) and the hint text is not rendered.

- [ ] **Step 3: Implement — add the field + render the effective qty/hint/total**

In `calculation-results.tsx`:

3a. Add the import at the top (after the lucide-react import):

```tsx
import { effectiveQuantity } from "../procurement-step/moq-warning";
```

3b. Add the field to the `CalculationResultsItem` interface (after `quantity`):

```tsx
  quantity: number | null;
  /**
   * Supplier quantity («Кол-во поставщика», DB `minimum_order_quantity`).
   * When set (> 0) it overrides `quantity` in both directions via the shared
   * `effectiveQuantity` helper. Null/0 → use ordered `quantity`. Sourced by
   * calculation-step.tsx from the selected invoice_item.
   */
  minimum_order_quantity?: number | null;
  base_price_vat: number | null;
```

3c. Replace the per-row quantity + line-total computation. Find this block inside `items.map((item) => { ... })`:

```tsx
                const priceVat = excluded ? null : item.base_price_vat;
                const qty = item.quantity ?? 0;
                const lineTotal =
                  priceVat != null ? priceVat * qty : null;
```

Replace it with:

```tsx
                const priceVat = excluded ? null : item.base_price_vat;
                const ordered = item.quantity ?? 0;
                const supplierQty = item.minimum_order_quantity ?? null;
                const qty = effectiveQuantity(item.quantity, supplierQty);
                // Override is "adjusted" only when a positive supplier qty
                // actually changes the number — mirrors the picker's QuantityCell.
                const adjusted =
                  supplierQty != null && supplierQty > 0 && qty !== ordered;
                const lineTotal =
                  priceVat != null ? priceVat * qty : null;
```

3d. Replace the quantity `<TableCell>` (the one that renders `{qty}`):

```tsx
                    <TableCell className="text-sm text-right tabular-nums">
                      {qty}
                    </TableCell>
```

with (the hint is a single template-literal text node — avoids the SSR `<!-- -->` marker between adjacent text + `{expr}`):

```tsx
                    <TableCell className="text-sm text-right tabular-nums">
                      {qty}
                      {adjusted && (
                        <div
                          className="text-[11px] font-normal text-muted-foreground"
                          title={`Кол-во поставщика переопределяет заказанное (заказано ${ordered})`}
                        >
                          {`кол-во поставщика: ${supplierQty}`}
                        </div>
                      )}
                    </TableCell>
```

- [ ] **Step 4: Run the SSR tests — verify they pass**

Run: `cd frontend && npx vitest run src/features/quotes/ui/calculation-step/__tests__/calculation-results.test.tsx`
Expected: PASS (all cases, including the pre-existing ones).

- [ ] **Step 5: Add the jsdom render test**

Append to `calculation-results.dom.test.tsx`. First add `minimum_order_quantity: null,` to that file's local `makeItem` factory, then add:

```tsx
describe("CalculationResults — effective quantity (supplier override)", () => {
  it("renders effective qty + «кол-во поставщика» hint when supplier qty overrides", () => {
    const quote = makeQuote({ total_quote_currency: 1000 });
    const items = [
      makeItem({
        id: "a",
        product_name: "С поставщиком",
        base_price_vat: 100,
        quantity: 5,
        minimum_order_quantity: 10,
      }),
    ];

    render(<CalculationResults quote={quote} items={items} />);

    const row = screen.getByText("С поставщиком").closest("tr") as HTMLElement;
    // Effective qty (10) is shown.
    expect(within(row).getByText("10")).toBeTruthy();
    // Two-sided hint visible.
    expect(within(row).getByText(/кол-во поставщика: 10/)).toBeTruthy();
    expect(
      within(row).getByText(/кол-во поставщика: 10/).getAttribute("title"),
    ).toContain("заказано 5");
  });
});
```

- [ ] **Step 6: Run the jsdom test — verify it passes**

Run: `cd frontend && npx vitest run src/features/quotes/ui/calculation-step/__tests__/calculation-results.dom.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/quotes/ui/calculation-step/calculation-results.tsx \
        frontend/src/features/quotes/ui/calculation-step/__tests__/calculation-results.test.tsx \
        frontend/src/features/quotes/ui/calculation-step/__tests__/calculation-results.dom.test.tsx
git commit -m "feat(calc): calc-results table shows effective (supplier-override) qty"
```

---

### Task 2: wire the supplier quantity through the calc-results loader

**Files:**
- Modify: `frontend/src/features/quotes/ui/calculation-step/calculation-step.tsx`

This is the data-fetch wiring. The loader already joins `invoice_item_coverage → invoice_items` and matches the row to `composition_selected_invoice_id` to build `priceByQi`. We add the supplier qty to the same join and build a parallel map — no new query.

- [ ] **Step 1: Extend the coverage select to include `minimum_order_quantity`**

Find (inside the `Promise.all`, the coverage query):

```tsx
        supabase
          .from("invoice_item_coverage")
          .select(
            "quote_item_id, invoice_items!inner(invoice_id, base_price_vat)"
          )
          .in("quote_item_id", qiIds),
```

Replace the `.select(...)` string with:

```tsx
          .select(
            "quote_item_id, invoice_items!inner(invoice_id, base_price_vat, minimum_order_quantity)"
          )
```

- [ ] **Step 2: Widen the row type + build `supplierQtyByQi` alongside `priceByQi`**

Find:

```tsx
      const priceByQi = new Map<string, number | null>();
      for (const row of (cov ?? []) as unknown as Array<{
        quote_item_id: string;
        invoice_items: { invoice_id: string; base_price_vat: number | null };
      }>) {
        const qi = items.find((it) => it.id === row.quote_item_id);
        if (!qi) continue;
        const selected = qi.composition_selected_invoice_id ?? null;
        if (selected != null && row.invoice_items.invoice_id !== selected)
          continue;
        if (!priceByQi.has(row.quote_item_id)) {
          priceByQi.set(
            row.quote_item_id,
            row.invoice_items.base_price_vat ?? null
          );
        }
      }
```

Replace with (adds the `minimum_order_quantity` field to the row type and fills a parallel map under the **same** selected-invoice matching, so price and supplier qty always come from the same chosen invoice_item):

```tsx
      const priceByQi = new Map<string, number | null>();
      const supplierQtyByQi = new Map<string, number | null>();
      for (const row of (cov ?? []) as unknown as Array<{
        quote_item_id: string;
        invoice_items: {
          invoice_id: string;
          base_price_vat: number | null;
          minimum_order_quantity: number | null;
        };
      }>) {
        const qi = items.find((it) => it.id === row.quote_item_id);
        if (!qi) continue;
        const selected = qi.composition_selected_invoice_id ?? null;
        if (selected != null && row.invoice_items.invoice_id !== selected)
          continue;
        if (!priceByQi.has(row.quote_item_id)) {
          priceByQi.set(
            row.quote_item_id,
            row.invoice_items.base_price_vat ?? null
          );
          supplierQtyByQi.set(
            row.quote_item_id,
            row.invoice_items.minimum_order_quantity ?? null
          );
        }
      }
```

- [ ] **Step 3: Pass the supplier qty into the result items**

Find the `setResultsItems(items.map((it) => ({ ... })))` object and add the field after `quantity:`:

```tsx
          quantity: it.quantity ?? null,
          minimum_order_quantity: supplierQtyByQi.get(it.id) ?? null,
          base_price_vat: priceByQi.get(it.id) ?? null,
```

- [ ] **Step 4: Carry it through the placeholder**

In `toPlaceholderResultItem`, the supplier qty lives on the invoice_item, which is not loaded until the async coverage fetch lands — so it is `null` on first paint (same as `base_price_vat`). Add after `quantity:`:

```tsx
    quantity: item.quantity ?? null,
    minimum_order_quantity: null,
    base_price_vat: null,
```

- [ ] **Step 5: Type-check the frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no type errors).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/quotes/ui/calculation-step/calculation-step.tsx
git commit -m "feat(calc): load supplier qty into calc-results via existing coverage join"
```

---

## Self-Review

**1. Spec coverage** (spec §4 row "Calc-results table | join selected invoice_item → effective"): Task 2 adds `minimum_order_quantity` to the existing selected-invoice join; Task 1 computes the effective value via the shared helper and renders it. ✅ Covered. The spec's generated-column single-source (§3) is intentionally deferred to Stage 3 (its first single-value reader, the exports) — documented in the plan header and the memory file; end state unchanged.

**2. Placeholder scan:** No TBD/TODO/"handle edge cases". Every code step shows exact before/after. ✅

**3. Type consistency:** `effectiveQuantity(ordered: number | null, supplierQty: number | null): number` is used with `item.quantity` (number | null) and `supplierQty` (number | null) — matches the signature in `moq-warning.ts`. The new prop `minimum_order_quantity?: number | null` matches the map value type `Map<string, number | null>` and the `?? null` fallbacks. Hint copy (`кол-во поставщика: ${supplierQty}` / title `…(заказано ${ordered})`) is character-identical to the picker's `QuantityCell`. ✅

**Out of scope for this stage (Stage 3+):** generated column `invoice_items.effective_quantity` + apply-to-prod, exports (specification/contract/invoice), composition `effective_quantity` forwarding, logistics, customs, KP, procurement rename + tooltip + retire `isMoqViolation`.
