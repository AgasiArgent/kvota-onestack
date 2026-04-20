# Tasks — Phase 5c: Invoice Items

**Workflow:** `/lean-tdd` — each task is one RED → GREEN → REFACTOR cycle.
**Check-in:** After tasks 1-4 (migrations) and task 15 (browser E2E) before continuing.
**Commit hygiene:** `git add <explicit paths>` — never `git add .`. `Co-Authored-By: Claude Opus 4.7`.

---

## Task 1 — Migration 281: invoice_items table + RLS

**Goal:** Create `kvota.invoice_items` table with full column set, indexes, and RLS policies mirroring Phase 5b's invoice_item_prices pattern.

**RED:**
- Write `tests/test_migration_281.py`: queries `information_schema.columns` for `kvota.invoice_items`, asserts 28 columns present with correct types. Asserts RLS enabled. Asserts 10 SELECT role policies + 4 INSERT + 4 UPDATE + 2 DELETE.

**GREEN:**
- Write `migrations/281_create_invoice_items.sql` per `design.md §1.1` — full CREATE TABLE + 3 indexes + 4 RLS policies.
- Apply via `scripts/apply-migrations.sh` to dev DB.
- Rerun tests — pass.

**REFACTOR:** n/a (DDL-only task).

**Commit:**
```
git add migrations/281_create_invoice_items.sql tests/test_migration_281.py
```

Message: `feat(phase-5c): migration 281 — invoice_items table`

**Acceptance:** `ls migrations/` shows 281 file; RLS tests pass; no errors in Supabase logs.

---

## Task 2 — Migration 282: invoice_item_coverage M:N junction + RLS

**Goal:** Create `kvota.invoice_item_coverage` table with M:N to invoice_items + quote_items, `ratio NUMERIC` column, RLS via invoice_items.

**RED:**
- Write `tests/test_migration_282.py`: asserts PK `(invoice_item_id, quote_item_id)`, CHECK `ratio > 0`, CASCADE on both FKs, RLS enabled with same 10/4/2 role count.

**GREEN:**
- Write `migrations/282_create_invoice_item_coverage.sql` per `design.md §1.1` — CREATE TABLE + 2 indexes + 4 RLS policies (org resolved via JOIN to invoice_items).
- Apply; rerun tests.

**Commit:**
```
git add migrations/282_create_invoice_item_coverage.sql tests/test_migration_282.py
```

Message: `feat(phase-5c): migration 282 — invoice_item_coverage M:N junction`

**Acceptance:** Inserting a coverage row with `ratio=0` fails CHECK; inserting valid rows succeeds; RLS blocks users from other orgs.

---

## Task 3 — Migration 283: Backfill + bit-identity test

**Goal:** Populate `invoice_items` + `invoice_item_coverage` from `invoice_item_prices` + `quote_items`. Produce bit-identical calc output for 5+ representative prod quotes.

**RED:**
- Write `tests/test_migration_283_bit_identity.py`: for 5 representative pre-Phase-5c quotes (fetched from prod snapshot), compute `calculate_multiproduct_quote(legacy_items)` BEFORE and `calculate_multiproduct_quote(composed_items_via_new_schema)` AFTER. Asserts every monetary field and item-level result is bit-identical (within 1e-10 tolerance).
- Initial run fails — backfill hasn't run yet.

**GREEN:**
- Write `migrations/283_backfill_invoice_items.sql`:
  - INSERT INTO invoice_items SELECT from iip JOIN qi, copying supplier-side fields from qi, overlay fields from iip
  - INSERT INTO invoice_item_coverage SELECT with ratio=1 (every backfilled row is 1:1)
  - position = ROW_NUMBER() OVER (PARTITION BY invoice_id ORDER BY iip.created_at)
  - ON CONFLICT DO NOTHING for idempotency
- Apply; rerun test — must pass.

**Commit:**
```
git add migrations/283_backfill_invoice_items.sql tests/test_migration_283_bit_identity.py
```

Message: `feat(phase-5c): migration 283 — backfill invoice_items from iip`

**Acceptance:** Row counts match: `count(invoice_items) == count(invoice_item_prices)`; every qi with `composition_selected_invoice_id NOT NULL` has a matching coverage row; bit-identity test passes.

---

## Task 4 — Migration 284: Drop legacy schema

**Goal:** DROP `invoice_item_prices` table + 16 legacy columns on `quote_items`. Prerequisite: all application code reads from new schema (tasks 5-14 merged and deployed to staging first).

**RED:**
- Write `tests/test_migration_284_no_legacy_refs.py`: grep codebase for removed column names (`quote_items.invoice_id`, `purchase_price_original` usage in quote_items SELECT, etc.); asserts zero matches in `main.py`, `services/`, `frontend/src/`, `tests/` (except the test file itself). This test pre-validates that drop is safe.

**GREEN:**
- Write `migrations/284_drop_legacy_schema.sql`:
  - DROP TABLE kvota.invoice_item_prices CASCADE;
  - ALTER TABLE kvota.quote_items DROP COLUMN invoice_id, DROP COLUMN purchase_price_original, ... (16 columns per design.md §1.2)
- Apply on dev after pre-check passes; run full test suite; staging.

**Commit:**
```
git add migrations/284_drop_legacy_schema.sql tests/test_migration_284_no_legacy_refs.py
```

Message: `feat(phase-5c): migration 284 — drop iip + legacy quote_items columns`

**Acceptance:** Pre-check test passes (zero legacy refs); migration applies cleanly; calc engine tests still pass.

---

## Task 5 — Rewrite composition_service.py

**Goal:** Update `services/composition_service.py` to use new `invoice_items` + `invoice_item_coverage` schema while preserving public API.

**RED:**
- Extend `tests/test_composition_service.py` with 20+ new cases:
  - 1:1 composition (legacy-equivalent): produces one calc item per quote_item
  - Split composition: 1 quote_item → 2 invoice_items → 2 calc items (with correct quantities via ratio)
  - Merge composition: 3 quote_items → 1 invoice_item → 1 calc item (emitted once)
  - No composition selected: falls back to emitting quote_items with null price fields
  - Quote_item not covered in selected invoice: skipped in output
  - N+1 guard: assert ≤3 SQL queries regardless of item count
- Run — fails (old code still uses iip).

**GREEN:**
- Rewrite `get_composed_items()` per `design.md §2.1`.
- Rewrite `get_composition_view()` per §2.2 (alternatives now grouped by invoice, not by invoice_item; coverage summary field added).
- Rewrite `apply_composition()` per §2.3 (merge case: picking one invoice sets composition_selected_invoice_id on N covered quote_items).
- Rewrite `freeze_composition()` per §2.4 (walks coverage → invoice_items).
- Rewrite `validate_composition()` per §2.5 (coverage existence check).
- Update constants: replace `_OVERLAY_FIELDS` (no longer overlay, items come from invoice_items directly).

**REFACTOR:**
- Extract `_build_calc_item(qi, ii, ratio)` helper (design.md §2.1 snippet).
- Ensure all queries use `.in_()` for batch semantics, no loops with per-row queries.

**Commit:**
```
git add services/composition_service.py tests/test_composition_service.py
```

Message: `feat(phase-5c): rewrite composition_service for invoice_items + coverage`

**Acceptance:** All new + existing tests pass; Bit-identity test from Task 3 still passes.

---

## Task 6 — Hook composition_service into 3 calc entry points (no signature change)

**Goal:** Verify `main.py:13463, 14252, 14910` still call `composition_service.get_composed_items(quote_id, supabase)` — no change expected since signature preserved.

**RED:**
- Write `tests/test_main_calc_entry_points.py`: for each of 3 call sites, instantiate with a test quote, assert `build_calculation_inputs()` receives a list where items have `purchase_price_original` from invoice_items (not quote_items).

**GREEN:**
- Verify no code change needed in main.py (signature preserved). If any call site still passes legacy items (shouldn't, but double-check), fix it.

**REFACTOR:** n/a.

**Commit:** Only if main.py edits occur — otherwise just the test.
```
git add tests/test_main_calc_entry_points.py [main.py if changed]
```

Message: `test(phase-5c): verify calc entry points use rewritten composition_service`

**Acceptance:** Tests pass; all 3 call sites observed to feed invoice_items-derived data through the calc path.

---

## Task 7 — Edit-gate refactor: services/invoice_send_service.py

**Goal:** Replace `is_invoice_sent(invoice_id)` gate with `is_quote_procurement_locked(invoice_id)` (looks up invoice → quote → procurement_completed_at).

**RED:**
- Write `tests/test_edit_gate_procurement_lock.py`:
  - Invoice with quote.procurement_completed_at = NULL → `check_edit_permission` returns True for regular procurement user
  - Invoice with quote.procurement_completed_at = NOW() → returns False for procurement user, True for admin/head_of_procurement
  - Invoice whose quote is missing → returns True (fail-open for missing quote)
- Also write: `tests/test_sent_at_has_no_gate_effect.py` — invoice with sent_at != null AND procurement_completed_at IS NULL → editable by everyone.

**GREEN:**
- Rewrite `services/invoice_send_service.py:is_invoice_sent` → `is_quote_procurement_locked` per design.md §3.1.
- Update `check_edit_permission` to call new function.
- Update 3 call sites in main.py (19210, 19683, 19803) — error code string `EDIT_REQUIRES_APPROVAL` → `PROCUREMENT_LOCKED`.

**REFACTOR:**
- Remove old `is_invoice_sent` function if no longer used anywhere (grep to confirm).

**Commit:**
```
git add services/invoice_send_service.py main.py tests/test_edit_gate_procurement_lock.py tests/test_sent_at_has_no_gate_effect.py
```

Message: `feat(phase-5c): move edit-gate from sent_at to procurement_completed_at`

**Acceptance:** All new tests pass; existing `test_invoice_send_service.py` tests updated to new semantics pass; sending an invoice followed by editing is no longer blocked.

---

## Task 8 — API rename: request_edit_approval → request_procurement_unlock

**Goal:** Rename endpoint + approval_type for clarity + alignment with new gate semantics.

**RED:**
- Write `tests/test_api_procurement_unlock.py`:
  - POST /api/invoices/{id}/procurement-unlock-request creates approval with approval_type="edit_completed_procurement"
  - Old endpoint path `/api/invoices/{id}/edit-request` returns 404 (fully removed)
  - Approval approve/reject endpoints use new paths too

**GREEN:**
- Rename endpoint path in `api/invoices.py:430`: `/edit-request` → `/procurement-unlock-request`
- Rename function `request_edit_approval` → `request_procurement_unlock`
- Change approval_type literal `"edit_sent_invoice"` → `"edit_completed_procurement"` at line 457
- Rename approve/reject endpoints similarly at line 430-500 range
- Update frontend mutation caller (`frontend/src/entities/invoice/mutations.ts` — grep for `edit-request`) to new path

**Commit:**
```
git add api/invoices.py frontend/src/entities/invoice/mutations.ts tests/test_api_procurement_unlock.py
```

Message: `refactor(phase-5c): rename edit-approval API to procurement-unlock`

**Acceptance:** Old path returns 404; new path works; frontend mutations use new path.

---

## Task 9 — Frontend: quote-positions-list (rename + un-filter + "В КП" badge)

**Goal:** Replace `unassigned-items.tsx` with non-destructive `quote-positions-list.tsx` that shows all quote_items with coverage chips.

**RED:**
- Write `frontend/src/features/quotes/ui/procurement-step/__tests__/quote-positions-list.test.tsx`:
  - Renders all quote_items regardless of coverage status
  - Shows "В КП" chip list with invoice_numbers
  - Selecting items + clicking "Назначить в КП" dropdown shows all invoices + "➕ Создать новый КП"
  - Assigning items that are already in another invoice does NOT remove them from that invoice (non-destructive)

**GREEN:**
- Rename `unassigned-items.tsx` → `quote-positions-list.tsx`, rename component `UnassignedItems` → `QuotePositionsList`
- Remove filter `items.filter(i => i.invoice_id == null)` — render all `items`
- Add fetch of coverage data: query `invoice_item_coverage` JOIN `invoice_items` WHERE `coverage.quote_item_id IN (...)` on mount
- Add "В КП" column with chip list; chip click scrolls to invoice-card with `data-invoice-id={id}`
- Update dropdown to list ALL `invoices` prop (parent already has them)
- Update header: "Нераспределённые позиции (N)" → "Позиции заявки (N)"
- Update parent `procurement-step.tsx` import + component name

**REFACTOR:**
- Extract `CoverageChips` sub-component if complexity grows.

**Commit:**
```
git add frontend/src/features/quotes/ui/procurement-step/quote-positions-list.tsx \
        frontend/src/features/quotes/ui/procurement-step/procurement-step.tsx \
        frontend/src/features/quotes/ui/procurement-step/__tests__/quote-positions-list.test.tsx
git rm frontend/src/features/quotes/ui/procurement-step/unassigned-items.tsx
```

Message: `feat(phase-5c): non-destructive quote-positions-list with coverage chips`

**Acceptance:** Vitest passes; manual browser-smoke: items visible after assignment, new "В КП" badge shows invoice numbers.

---

## Task 10 — Frontend: rewrite assignItemsToInvoice mutation

**Goal:** `entities/quote/mutations.ts:assignItemsToInvoice` no longer UPDATEs `quote_items.invoice_id`; instead INSERTs invoice_items + invoice_item_coverage rows.

**RED:**
- Write `frontend/src/entities/quote/__tests__/mutations-assign.test.ts`:
  - Assigning items inserts one invoice_items row per quote_item (with defaults from quote_items)
  - Assigning inserts one coverage row per assignment with ratio=1
  - Re-assigning same (invoice, quote_item) is a no-op (ON CONFLICT DO NOTHING)
  - quote_items.composition_selected_invoice_id is set (for the newly-assigned invoice)

**GREEN:**
- Rewrite `assignItemsToInvoice(itemIds: string[], invoiceId: string)` per design.md §4.1:
  - SELECT quote_items rows for defaults (product_name, brand, quantity, idn_sku, supplier_sku for seeding invoice_items)
  - SELECT invoice.organization_id for RLS
  - INSERT invoice_items rows (position = (max position in invoice) + 1 + i)
  - INSERT invoice_item_coverage with ratio=1 (ON CONFLICT DO NOTHING)
  - UPDATE quote_items.composition_selected_invoice_id = invoiceId
- Remove old `invoice_item_prices` upsert code (was in Phase 5b mutations.ts:294-299)

**Commit:**
```
git add frontend/src/entities/quote/mutations.ts frontend/src/entities/quote/__tests__/mutations-assign.test.ts
```

Message: `feat(phase-5c): rewrite assignItemsToInvoice to use invoice_items + coverage`

**Acceptance:** Tests pass; manual smoke: assigning items creates invoice_items rows (verify via SQL).

---

## Task 11 — Frontend: invoice-card items from invoice_items; rename locks

**Goal:** `invoice-card.tsx` items list queries invoice_items (not quote_items.invoice_id). Rename `isSent` → `isLocked` based on `quote.procurement_completed_at`. Rename `EditApprovalButton` → `ProcurementUnlockButton`.

**RED:**
- Extend `frontend/src/features/quotes/ui/procurement-step/__tests__/invoice-card.test.tsx`:
  - Items list rendered from invoice_items source, not legacy FK
  - Merged invoice_item shows "покрывает: болт, гайка, шайба" coverage summary
  - Split invoice_item shows ratio in coverage sub-text
  - `ProcurementUnlockButton` renders when `quote.procurement_completed_at != null`
  - "Отправлено" badge renders when `invoice.sent_at != null` (informational, always)

**GREEN:**
- In `invoice-card.tsx`:
  - Change items source: query `invoice_items` + JOIN `invoice_item_coverage` WHERE `invoice_id = invoice.id`
  - Replace `isSent` variable at line 68 with `isLocked = quote.procurement_completed_at != null`
  - At lines 254-256: render `ProcurementUnlockButton` when `isLocked`
  - Keep green "Отправлено" badge at lines 243-246 unchanged (pure metadata)
- Rename file + component: `edit-approval-button.tsx` → `procurement-unlock-button.tsx`, `EditApprovalButton` → `ProcurementUnlockButton`
- Update mutation calls to new API path (from Task 8)
- Pass `quote` prop down from `procurement-step.tsx` (only `procurement_completed_at` needed, or full quote)

**Commit:**
```
git add frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx \
        frontend/src/features/quotes/ui/procurement-step/procurement-unlock-button.tsx \
        frontend/src/features/quotes/ui/procurement-step/procurement-step.tsx \
        frontend/src/features/quotes/ui/procurement-step/__tests__/invoice-card.test.tsx
git rm frontend/src/features/quotes/ui/procurement-step/edit-approval-button.tsx
```

Message: `feat(phase-5c): invoice-card reads invoice_items; rename edit-approval to procurement-unlock`

**Acceptance:** Tests pass; browser smoke: unlocked invoice is editable even after send; lock visible after "Завершить закупку".

---

## Task 12 — Frontend: SplitModal component + mutation

**Goal:** New modal triggered from invoice-card "⚡ Разделить позицию" button. Creates N invoice_items from 1 quote_item.

**RED:**
- Write `frontend/src/features/quotes/ui/procurement-step/__tests__/split-modal.test.tsx`:
  - Picks source quote_item from invoice's 1:1 coverage
  - Adds 2 child rows with (name, quantity_ratio, price)
  - Submit calls backend transaction: DELETE source invoice_item + coverage, INSERT N new invoice_items + coverage
  - Validation: each child's quantity_ratio > 0
  - Validation: can only split 1:1-covered quote_items (block if already split/merged)

**GREEN:**
- Create `frontend/src/features/quotes/ui/procurement-step/split-modal.tsx` per design.md §4.4.
- Create `splitInvoiceItem(invoiceId, sourceQuoteItemId, children)` mutation in `entities/quote/mutations.ts` — wraps a Python API call (or direct Supabase transaction via RPC if needed).
- Add "⚡ Разделить позицию" button to invoice-card header.

**REFACTOR:**
- Extract form-row sub-component if child definitions grow complex.

**Commit:**
```
git add frontend/src/features/quotes/ui/procurement-step/split-modal.tsx \
        frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx \
        frontend/src/entities/quote/mutations.ts \
        frontend/src/features/quotes/ui/procurement-step/__tests__/split-modal.test.tsx
```

Message: `feat(phase-5c): SplitModal for per-invoice quote_item decomposition`

**Acceptance:** Modal opens, form validates, submit creates expected rows; browser smoke: split a test quote_item into 2 invoice_items, verify calc still produces sensible output.

---

## Task 13 — Frontend: MergeModal component + mutation

**Goal:** New modal triggered from invoice-card "⚡ Объединить позиции". Creates 1 invoice_item from N quote_items.

**RED:**
- Write `__tests__/merge-modal.test.tsx`:
  - Multi-select N ≥ 2 quote_items (each must be 1:1 covered in this invoice)
  - Defines merged row with defaults (max quantity, empty name, etc.)
  - Submit: DELETE N source invoice_items + coverage, INSERT 1 merged invoice_item + N coverage rows (ratio=1)
  - Blocks if any selected quote_item is already part of split/merge

**GREEN:**
- Create `merge-modal.tsx` per design.md §4.5.
- Create `mergeInvoiceItems(invoiceId, sourceQuoteItemIds, merged)` mutation.
- Add "⚡ Объединить позиции" button to invoice-card.

**Commit:**
```
git add frontend/src/features/quotes/ui/procurement-step/merge-modal.tsx \
        frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx \
        frontend/src/entities/quote/mutations.ts \
        frontend/src/features/quotes/ui/procurement-step/__tests__/merge-modal.test.tsx
```

Message: `feat(phase-5c): MergeModal for per-invoice quote_items consolidation`

**Acceptance:** Modal opens, validation blocks chain-merge, submit creates merged invoice_item covering 3 quote_items; calc engine produces 1 line not 3.

---

## Task 14 — Frontend: composition-picker coverage summary

**Goal:** Sales-side picker shows coverage summary text under each alternative when supplier's invoice has split/merge structure.

**RED:**
- Extend `__tests__/composition-picker.test.tsx`:
  - Split alternative shows "→ болт ×1 + шайба ×2" label
  - Merge alternative shows "← болт, гайка, шайба объединены" label
  - 1:1 alternative shows no label (default)
- Also test: picking a merged alternative triggers backend to set composition_selected_invoice_id on all N covered quote_items.

**GREEN:**
- Extend `composition-picker.tsx`:
  - Group by invoice_id at render time (alternatives currently per-invoice_item — change to per-invoice with coverage list)
  - Render coverage summary string from alternative's coverage metadata (returned by `get_composition_view` in task 5)
- Update backend `get_composition_view` response shape to include `coverage_summary` field per alternative (if not already in task 5).

**Commit:**
```
git add frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx \
        frontend/src/entities/quote/types.ts \
        services/composition_service.py \
        frontend/src/features/quotes/ui/calculation-step/__tests__/composition-picker.test.tsx
```

Message: `feat(phase-5c): composition-picker coverage summary for split/merge`

**Acceptance:** Picker shows clear split/merge indicators; sales user sees what structural choice a supplier is offering.

---

## Task 15 — QA: bit-identity regression + RLS + browser E2E

**Goal:** Final verification on staging before prod deploy.

**Checks:**

1. **Bit-identity regression** (Python): run `pytest tests/test_migration_283_bit_identity.py -v` against staging DB. Must pass for all 5+ representative quotes.
2. **RLS smoke test** (Python): for each of 10 SELECT roles, authenticate as a user with that role in a different org, attempt SELECT on invoice_items → expect zero rows. Same for invoice_item_coverage.
3. **Browser E2E on staging:**
   - Create quote with 3 items via sales flow
   - Procurement: create invoice A (supplier S1), assign all 3 items → calc runs
   - Procurement: create invoice B (supplier S2), via non-destructive "Назначить в КП" add 2 of the items → both invoices now cover those 2
   - Split 1 quote_item in invoice A into 2 invoice_items
   - Merge 2 quote_items in invoice B into 1 invoice_item
   - Sales: composition picker shows both invoices as alternatives with coverage summaries; pick A for item 1, B for item 2
   - Calculate → check calc output matches hand-calculation
   - Complete procurement → edit-gate activates, ProcurementUnlockButton appears
   - Unlock approval flow → edit invoice → re-send

**Commit:** No code change — update `CHANGELOG.md` with verification results.

```
git add changelog/2026-04-XX.md
```

**Acceptance:** All 3 check categories pass. Staging DB state matches expected. User (Daisy/business owner) signs off on E2E flow.

---

## Task 16 — Changelog + production deploy

**Goal:** Ship to prod. Follow standard OneStack deploy: push to main → GitHub Actions → beget-kvota.

**Steps:**

1. Write `changelog/YYYY-MM-DD.md` with v0.7.0 entry summarizing all Phase 5c changes.
2. Merge PR to main.
3. Monitor CI deploy.
4. On prod DB, apply migrations 281-284 in order via `scripts/apply-migrations.sh`.
5. SSH to beget-kvota, `docker logs kvota-onestack --tail 100` — verify no crashes.
6. Run bit-identity test on prod DB (Python script, read-only): `python tests/test_migration_283_bit_identity.py --prod-snapshot`.
7. Browser smoke on prod (app.kvotaflow.ru): create a test quote, go through procurement flow, verify new UI works.
8. Monitor for 24h; revert if regression detected.

**Commit:**
```
git add changelog/YYYY-MM-DD.md
```

Message: `docs(changelog): v0.7.0 — Phase 5c Invoice Items`

**Acceptance:** Prod has migrations 281-284 applied; test quote passes full procurement flow; no errors in container logs; no user-reported regressions within 24h.

---

## Dependencies and critical path

```
281 → 282 → 5 (composition rewrite)
                 ↓
             6 (calc entries verify)
                 ↓
       9, 10, 11 (frontend) ← 7 (edit-gate) ← 8 (API rename)
                 ↓
             12, 13 (split/merge modals)
                 ↓
             14 (composition picker)
                 ↓
             15 (QA)
                 ↓
     283 (backfill) → 284 (drop) → 16 (deploy)
```

Tasks 7 + 8 can run in parallel with 9-14 (independent surfaces). Tasks 12 + 13 can run in parallel after task 11 merges (both depend on invoice-card data source change, neither depends on the other).

Migrations 283 + 284 apply AFTER all code tasks 5-14 merge to main, to avoid breaking the running system. In practice: CI deploys code + migration 281 + 282 together; after deploy-and-verify, operator manually applies 283 + 284 via SSH.

---

## Rollback plan

- **Schema:** revert commit + DROP new tables (no `down` migration; `DROP TABLE kvota.invoice_items CASCADE; DROP TABLE kvota.invoice_item_coverage CASCADE;` — iip and qi columns cannot be easily restored, so rollback after migration 284 requires restoring quote_items columns from backup).
- **Application:** standard `git revert` + redeploy.
- **Commitment:** migrations 281-283 are safely revertable (iip still exists); migration 284 is the point-of-no-return. Gate deploy on 24h of staging observation post-283.
