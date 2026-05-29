# Supplier-quantity Override — Stage 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `invoice_items.minimum_order_quantity` (UI: «Кол-во поставщика») *override* the ordered quantity in both directions across the live calc path (engine + composition picker), backed by a single-source DB generated column.

**Architecture:** Add a STORED generated column `invoice_items.effective_quantity = COALESCE(NULLIF(minimum_order_quantity,0), quantity)`. The composition layer carries it; `build_calculation_inputs` feeds it to the locked engine. The shared helpers (`effective_calc_quantity` Python / `effectiveQuantity` TS) flip from `max()` to override, and the picker hint copy stops saying "minimum". This **supersedes the Row 85 `max()` floor** (PR #285/#287).

**Tech Stack:** PostgreSQL (Supabase, schema `kvota`), FastAPI/Python, Next.js/TypeScript (vitest), pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-supplier-quantity-override-design.md`

**Branch:** `feat/supplier-quantity-override` (from `origin/main`).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `migrations/334_invoice_items_effective_quantity.sql` | DB single source of the effective value | Create |
| `services/calculation_helpers.py` | `effective_calc_quantity` helper + `build_calculation_inputs` seam | Modify |
| `services/composition_service.py` | `_build_calc_item` / `_legacy_shape` carry `effective_quantity` | Modify |
| `tests/services/test_moq_roundup.py` | helper + build-inputs override regression | Modify (rewrite max→override) |
| `frontend/src/features/quotes/ui/procurement-step/moq-warning.ts` | `effectiveQuantity` helper | Modify |
| `frontend/src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts` | helper override tests | Modify |
| `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx` | `QuantityCell` + `SumCell` hint copy | Modify |
| `frontend/src/features/quotes/ui/calculation-step/__tests__/composition-picker-coverage.test.tsx` | picker override + hint tests | Modify |
| `frontend/src/shared/types/database.types.ts` | typed `effective_quantity` column | Regenerate |

---

### Task 1: Migration 334 — `effective_quantity` generated column

**Files:**
- Create: `migrations/334_invoice_items_effective_quantity.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 334_invoice_items_effective_quantity.sql
-- Supplier-quantity override (2026-05-29): single source of the effective
-- per-line quantity. When minimum_order_quantity (UI «Кол-во поставщика») is
-- set (non-null, non-zero) it OVERRIDES the ordered quantity in both
-- directions; otherwise the ordered quantity stands. NUMERIC to match
-- invoice_items.quantity (minimum_order_quantity is INTEGER → promoted).
BEGIN;

ALTER TABLE kvota.invoice_items
  ADD COLUMN IF NOT EXISTS effective_quantity NUMERIC
  GENERATED ALWAYS AS (COALESCE(NULLIF(minimum_order_quantity, 0), quantity)) STORED;

COMMENT ON COLUMN kvota.invoice_items.effective_quantity IS
  'Effective per-line quantity used by calc/display: COALESCE(NULLIF(minimum_order_quantity,0), quantity). Supplier qty overrides the order both ways. Read-only (generated).';

COMMIT;
```

- [ ] **Step 2: Apply to prod BEFORE merging** (expand-contract — the column must exist in prod before any code that selects it deploys; see `reference_expand_contract_migration_workflow`)

Run (from repo root on the deploy host path, or via SSH per project workflow):
```bash
scripts/apply-migrations.sh 334_invoice_items_effective_quantity.sql
```
Expected: `✅ Success`. (Multi-statement is wrapped in BEGIN/COMMIT so a partial apply rolls back — see `feedback_apply_migrations_silent_partial`.)

- [ ] **Step 3: Verify the column computes correctly in prod**

Run (psql / Supabase SQL):
```sql
SELECT
  count(*) FILTER (WHERE effective_quantity = COALESCE(NULLIF(minimum_order_quantity,0), quantity)) AS ok,
  count(*) AS total
FROM kvota.invoice_items;
```
Expected: `ok == total`. Spot-check an up-flip, a down-flip, a null, and a zero row.

- [ ] **Step 4: Commit the migration file**

```bash
git add migrations/334_invoice_items_effective_quantity.sql
git commit -m "feat(db): m334 invoice_items.effective_quantity generated column (supplier-qty override)"
```

---

### Task 2: Flip the Python helper `max()` → override

**Files:**
- Modify: `services/calculation_helpers.py` (`effective_calc_quantity`)
- Test: `tests/services/test_moq_roundup.py` (`TestEffectiveCalcQuantity`)

- [ ] **Step 1: Rewrite the helper unit tests for override semantics (RED)**

Replace the body of `class TestEffectiveCalcQuantity` in `tests/services/test_moq_roundup.py` with:
```python
class TestEffectiveCalcQuantity:
    @pytest.mark.parametrize(
        "ordered, supplier_qty, expected",
        [
            (5, 10, 10),      # supplier higher → override up
            (10, 5, 5),       # supplier lower → override DOWN (new behaviour)
            (10, 10, 10),     # equal
            (5, None, 5),     # unset → ordered
            (5, 0, 5),        # zero treated as unset → ordered
            (5, -3, 5),       # negative treated as unset → ordered
            (10, None, 10),
        ],
    )
    def test_supplier_qty_overrides_when_set(self, ordered, supplier_qty, expected):
        assert effective_calc_quantity(ordered, supplier_qty) == expected

    def test_returns_int_when_overridden(self):
        result = effective_calc_quantity(5, 10)
        assert result == 10 and isinstance(result, int)

    def test_decimal_supplier_qty_coerced_to_int(self):
        result = effective_calc_quantity(5, Decimal("10"))
        assert result == 10 and isinstance(result, int)

    def test_unset_returns_ordered_verbatim(self):
        assert effective_calc_quantity(7, None) == 7
```

- [ ] **Step 2: Run to verify failure** (CI; pytest unavailable locally — rely on CI)

Run: `pytest tests/services/test_moq_roundup.py::TestEffectiveCalcQuantity -v`
Expected: FAIL — e.g. `effective_calc_quantity(10, 5)` returns `10` (old max), test wants `5`.

- [ ] **Step 3: Rewrite the helper to override**

In `services/calculation_helpers.py`, replace `effective_calc_quantity`:
```python
def effective_calc_quantity(ordered, supplier_qty):
    """Resolve the effective per-line quantity.

    When ``supplier_qty`` is set (non-null, non-zero, numeric) it OVERRIDES the
    ordered quantity in BOTH directions — the supplier ships exactly that many
    (more when his minimum exceeds the order, fewer when he is short). A
    null / 0 / negative / non-numeric supplier quantity falls back to the
    ordered quantity. Returns a clean int when overriding (engine model
    requires ``quantity: int, gt=0``).

    Mirrors the DB column invoice_items.effective_quantity =
    COALESCE(NULLIF(minimum_order_quantity, 0), quantity). Supersedes the Row 85
    max() floor (2026-05-29 supplier-quantity override).
    """
    sq = safe_decimal(supplier_qty)
    if sq > 0:
        return int(sq)
    return ordered
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/services/test_moq_roundup.py::TestEffectiveCalcQuantity -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/calculation_helpers.py tests/services/test_moq_roundup.py
git commit -m "feat(calc): supplier qty overrides ordered both ways (was max floor)"
```

---

### Task 3: Composition carries `effective_quantity`; engine reads it

**Files:**
- Modify: `services/composition_service.py` (`_build_calc_item` ~line 173, `_legacy_shape` ~line 126)
- Modify: `services/calculation_helpers.py` (`build_calculation_inputs` product seam ~line 619)
- Test: `tests/services/test_moq_roundup.py` (`TestBuildCalculationInputsMoqRoundup` → rename + override cases)

- [ ] **Step 1: Update the build-inputs regression tests for override (RED)**

Replace `class TestBuildCalculationInputsMoqRoundup` in `tests/services/test_moq_roundup.py` with cases that pass `effective_quantity` on the item (the composed shape), plus the override-down case:
```python
class TestBuildCalculationInputsOverride:
    def _qty(self, calc_inputs):
        assert len(calc_inputs) == 1
        return calc_inputs[0].product.quantity

    def test_uses_effective_quantity_when_present(self):
        item = _make_item(quantity=5, minimum_order_quantity=10, effective_quantity=10)
        with patch("services.currency_service.convert_amount", side_effect=lambda v, f, t: v):
            ci = build_calculation_inputs([item], _make_minimal_variables())
        assert self._qty(ci) == 10

    def test_override_down(self):
        item = _make_item(quantity=10, minimum_order_quantity=5, effective_quantity=5)
        with patch("services.currency_service.convert_amount", side_effect=lambda v, f, t: v):
            ci = build_calculation_inputs([item], _make_minimal_variables())
        assert self._qty(ci) == 5

    def test_falls_back_to_helper_when_no_effective_key(self):
        # Legacy callers that don't supply effective_quantity still resolve via the helper.
        item = _make_item(quantity=5, minimum_order_quantity=10)
        item.pop("effective_quantity", None)
        with patch("services.currency_service.convert_amount", side_effect=lambda v, f, t: v):
            ci = build_calculation_inputs([item], _make_minimal_variables())
        assert self._qty(ci) == 10

    def test_unset_uses_ordered(self):
        item = _make_item(quantity=5, minimum_order_quantity=None, effective_quantity=5)
        with patch("services.currency_service.convert_amount", side_effect=lambda v, f, t: v):
            ci = build_calculation_inputs([item], _make_minimal_variables())
        assert self._qty(ci) == 5
```
Also update `_make_item` in that file to accept/emit `effective_quantity` (default `None`) alongside the existing keys.

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/services/test_moq_roundup.py::TestBuildCalculationInputsOverride -v`
Expected: FAIL (`effective_quantity` not yet read by the seam).

- [ ] **Step 3: Carry `effective_quantity` through composition**

In `services/composition_service.py`:
- `_build_calc_item` (the returned dict): add
```python
        # Supplier-quantity override (2026-05-29): DB generated column
        # COALESCE(NULLIF(minimum_order_quantity,0), quantity). Single source.
        "effective_quantity": ii.get("effective_quantity"),
```
  (next to the existing `"minimum_order_quantity": ii.get("minimum_order_quantity"),`)
- `_legacy_shape` (the returned dict): add — no invoice line, so effective == ordered
```python
        "effective_quantity": qi.get("quantity"),
```
  (next to the existing `"minimum_order_quantity": qi.get("minimum_order_quantity"),`)

- [ ] **Step 4: Read `effective_quantity` at the seam**

In `services/calculation_helpers.py` `build_calculation_inputs`, replace the `'quantity'` line in the `product` dict with:
```python
            # Supplier-quantity override (2026-05-29): prefer the DB-computed
            # effective_quantity carried by composition_service; fall back to
            # the in-app helper for legacy callers that don't supply it.
            'quantity': (
                int(safe_decimal(item['effective_quantity']))
                if item.get('effective_quantity') not in (None, "")
                else effective_calc_quantity(
                    item.get('quantity', 1), item.get('minimum_order_quantity')
                )
            ),
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/services/test_moq_roundup.py -v`
Expected: PASS (all classes).

- [ ] **Step 6: Update the engine-equivalence test for override**

In `TestMoqRoundupScalesTotals` (same file), change the helper `_run_engine` items to include `effective_quantity`, and keep the two assertions but with override semantics:
- `effective_quantity=10` (ordered 5) `==` `effective_quantity=10` (ordered 10) — engine identical.
- `effective_quantity=10` (ordered 5) `!=` `effective_quantity=5` (ordered 5, unset) — floor changes totals.

- [ ] **Step 7: Commit**

```bash
git add services/composition_service.py services/calculation_helpers.py tests/services/test_moq_roundup.py
git commit -m "feat(calc): composition carries DB effective_quantity; engine reads it"
```

---

### Task 4: Flip the TS helper + picker hint; regenerate types

**Files:**
- Modify: `frontend/src/features/quotes/ui/procurement-step/moq-warning.ts`
- Test: `frontend/src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts`
- Modify: `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx` (`QuantityCell`, `SumCell`)
- Test: `frontend/src/features/quotes/ui/calculation-step/__tests__/composition-picker-coverage.test.tsx`
- Regenerate: `frontend/src/shared/types/database.types.ts`

- [ ] **Step 1: Regenerate DB types (picks up `effective_quantity`)**

Run:
```bash
cd frontend && npm run db:types
```
Expected: `invoice_items` Row type gains `effective_quantity: number | null`. Commit separately if large.

- [ ] **Step 2: Rewrite the TS helper tests for override (RED)**

Replace the `describe("effectiveQuantity", ...)` block in `moq-warning.test.ts`:
```ts
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

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npx vitest run src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts`
Expected: FAIL on `effectiveQuantity(10, 5)` (old max returns 10, want 5).

- [ ] **Step 4: Rewrite the TS helper to override**

In `moq-warning.ts`, replace `effectiveQuantity`:
```ts
/**
 * Effective per-line quantity. When the supplier quantity is set (non-null,
 * > 0) it OVERRIDES the ordered quantity in both directions; otherwise the
 * ordered quantity stands (null → 0). Mirrors the backend effective_calc_quantity
 * and the DB column COALESCE(NULLIF(minimum_order_quantity,0), quantity).
 * (Supplier-quantity override, 2026-05-29 — supersedes the Row 85 max floor.)
 */
export function effectiveQuantity(
  ordered: number | null,
  supplierQty: number | null
): number {
  if (supplierQty != null && supplierQty > 0) return supplierQty;
  return ordered ?? 0;
}
```

- [ ] **Step 5: Update the picker hint copy + SumCell (two-sided, no "minimum")**

In `composition-picker.tsx` `QuantityCell`, replace the `floored` branch hint so it shows whenever supplier qty differs from ordered (either direction) and renders a SINGLE text node (avoid the SSR `<!-- -->` marker):
```tsx
  const ordered = quantity ?? 1;
  const supplierQty = alt?.minimum_order_quantity ?? null;
  const effective = effectiveQuantity(ordered, supplierQty);
  const adjusted = supplierQty != null && supplierQty > 0 && effective !== ordered;

  if (!adjusted) {
    return <td className="py-3 px-2 tabular-nums">{ordered}</td>;
  }
  return (
    <td className="py-3 px-2 tabular-nums">
      <span className="flex flex-col leading-tight">
        <span>{effective}</span>
        <span
          className="text-[10px] text-amber-600 dark:text-amber-400"
          title={`Кол-во поставщика переопределяет заказанное (заказано ${ordered})`}
        >
          {`кол-во поставщика: ${supplierQty}`}
        </span>
      </span>
    </td>
  );
```
`SumCell` already uses `effectiveQuantity(quantity ?? 1, alt.minimum_order_quantity ?? null)` (from #287) — no change; it now follows the override automatically.

- [ ] **Step 6: Update the picker tests for override + new copy (RED→GREEN)**

In `composition-picker-coverage.test.tsx`, in the "Кол-во MOQ round-up" describe block: rename to "supplier-qty override", change the up-case assertions to the new copy (`кол-во поставщика: 123`, `заказано 10`, Сумма `15 129,00 USD`), and add a down-case: `minimum_order_quantity: 5`, `quantity: 10`, price `10` → cell shows `5`, hint `кол-во поставщика: 5`, Сумма `50,00 USD`.

- [ ] **Step 7: Run picker + helper tests**

Run: `cd frontend && npx vitest run src/features/quotes/ui/calculation-step/__tests__/composition-picker-coverage.test.tsx src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/quotes/ui/procurement-step/moq-warning.ts \
        frontend/src/features/quotes/ui/procurement-step/__tests__/moq-warning.test.ts \
        frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx \
        frontend/src/features/quotes/ui/calculation-step/__tests__/composition-picker-coverage.test.tsx \
        frontend/src/shared/types/database.types.ts
git commit -m "feat(calc): picker shows supplier-qty override (both ways); types regen"
```

---

### Task 5: Full-suite + golden master verification, then PR

**Files:** none (verification + PR)

- [ ] **Step 1: Schema-drift lint** (new column must resolve)

Run: `python3 tools/check_select_columns.py`
Expected: `OK: ... no schema-drift violations`.

- [ ] **Step 2: Golden master stays green** (no golden fixture sets the field → override is a no-op there)

Run: `pytest tests/test_calc_engine_golden_master.py tests/test_calc_comparison.py -q`
Expected: PASS (unchanged).

- [ ] **Step 3: Composition snapshot** (adds `effective_quantity` key — regenerate if the snapshot is keyed on the composed shape)

Run: `pytest tests/test_composition_snapshot.py -q`
Expected: PASS. If it fails on a new key, regenerate the committed fixture via `tests/test_refresh_golden.py`'s documented refresh (or the snapshot's regen path) and re-run — only the additive `effective_quantity` key should differ.

- [ ] **Step 4: Push + open PR**

```bash
git push -u origin feat/supplier-quantity-override
gh pr create --head feat/supplier-quantity-override --base main \
  --title "feat(calc): supplier-quantity override foundation (Stage 1)" \
  --body "$(cat <<'BODY'
Stage 1 of the supplier-quantity-override spec (docs/superpowers/specs/2026-05-29-supplier-quantity-override-design.md).

invoice_items.minimum_order_quantity (UI «Кол-во поставщика») now OVERRIDES the
ordered quantity in both directions when set (up = supplier minimum, down =
limited stock), via the DB generated column m334 invoice_items.effective_quantity
= COALESCE(NULLIF(minimum_order_quantity,0), quantity). Composition carries it;
the locked engine reads it; the shared helpers flip max()→override; the picker
hint drops the "minimum" wording.

Supersedes the Row 85 max() floor (#285/#287). Calc totals shift on quotes where
supplier qty != ordered (both directions, intended — confirmed with PO). Golden
master unaffected (no fixture sets the field). m334 applied to prod pre-merge.

Stages 2-5 (calc-results, logistics, customs, KP/exports, procurement rename)
follow as separate PRs.
BODY
)"
```

- [ ] **Step 5: Adversarial review → CI green → squash-merge → deploy → browser smoke**

Re-run the same funnel as the original Row 85: silent-failure + correctness review (PASS required), CI (build/test/schema-drift), squash-merge, wait for Deploy, then browser-smoke on a down-flip quote (e.g. one of the 19) and an up-flip quote (Q-202604-0055) confirming the picker + calc reflect the override.

---

## Subsequent stages (separate plans, written when reached)

Each depends on Stage 1 landing and gets its own bite-sized plan after reading the surface's code:
- **Stage 2** — calc-results table (`calculation-results.tsx` + the `calculation-step.tsx` builder: join selected invoice_item → `effective_quantity`).
- **Stage 3** — logistics cargo (`invoice-cargo-summary.tsx`) + customs grid (`customs-*`).
- **Stage 4** — KP PDF (Python `kp_export.py` + React `widgets/kp-preview/*`, one PR) + specification / contract / invoice / currency-invoice exports + XLS.
- **Stage 5** — procurement UI: rename column → «Кол-во поставщика» + explainer tooltip; retire `isMoqViolation`.
