# Implementation Tasks

Each task maps to one or more Requirements (REQ-N). Tasks sequenced for incremental verification: schema → backend → UI → integration → tests.

## Task 1: DB migration

**REQs:** REQ-1
**Files:**
- `migrations/3XX_add_payment_segments_to_specifications.sql` (NEW)

**Steps:**
1. Determine next migration number (verify current latest, likely 322 or 323 after batch 23A lands).
2. Write migration в shape из `design.md`:
   - 7 ADD COLUMN statements (3 pct, 3 days, 1 receiving days).
   - 8 CHECK constraints (3 pct ranges, 4 days ranges, 1 composite sum).
   - 7 COMMENT ON COLUMN statements.
   - Wrap в BEGIN/COMMIT.
3. **Backfill:** добавить в migration в той же транзакции:
   ```sql
   UPDATE kvota.specifications
   SET payment_on_receiving_days = COALESCE(client_payment_term_after_upd, 0)
   WHERE client_payment_term_after_upd IS NOT NULL;
   ```
4. Apply locally (либо через VPS workflow для prod):
   - `ssh beget-kvota → cd /root/onestack && git pull && bash scripts/apply-migrations.sh`
   - **NOT scp** — per memory `feedback_migrations_never_scp`.
5. Verify post-state via:
   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_schema='kvota' AND table_name='specifications'
     AND column_name LIKE 'payment_on_%';
   -- Expect 7 rows
   ```
6. Verify constraints:
   ```sql
   SELECT conname FROM pg_constraint
   WHERE conrelid='kvota.specifications'::regclass
     AND conname LIKE 'spec_payment_%';
   -- Expect 8 constraints
   ```

**Acceptance:** все verify queries возвращают expected counts; migration в git.

---

## Task 2: Backend mapping в build_calculation_inputs()

**REQs:** REQ-2
**Files:**
- `main.py` (или `api/calculation.py` — locate via grep "build_calculation_inputs")

**Steps:**
1. Locate `build_calculation_inputs(spec, ...)` function.
2. Add 8 new field mappings (anchors 2-4 pct/days + anchor 5 days source change):
   ```python
   'advance_on_loading': spec.get('payment_on_loading_pct') or 0,
   'time_to_advance_loading': spec.get('payment_on_loading_days') or 0,
   'advance_on_going_to_country_destination': spec.get('payment_on_country_arrival_pct') or 0,
   'time_to_advance_going_to_country_destination': spec.get('payment_on_country_arrival_days') or 0,
   'advance_on_customs_clearance': spec.get('payment_on_customs_clearance_pct') or 0,
   'time_to_advance_on_customs_clearance': spec.get('payment_on_customs_clearance_days') or 0,
   ```
3. Change `time_to_advance_on_receiving` source:
   ```python
   # Before
   'time_to_advance_on_receiving': spec.get('client_payment_term_after_upd', 0),
   # After
   'time_to_advance_on_receiving': spec.get('payment_on_receiving_days') or 0,
   ```
4. **DO NOT MODIFY** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`.

**Acceptance:** mapping function returns dict с 10 PaymentTerms fields; manual smoke test calc call.

---

## Task 3: Golden master verification

**REQs:** REQ-2
**Files:**
- `tests/test_calc_engine_golden_master.py` (existing — no changes expected)

**Steps:**
1. Run `pytest tests/test_calc_engine_golden_master.py -v`.
2. **All existing fixtures должны проходить** с теми же 3 ACCEPTED_DIFFERENCES — никаких новых diff'ов.
3. Если есть новые diff'ы → analyze: вероятно backfill `payment_on_receiving_days` не совпал с `client_payment_term_after_upd` для fixture spec. Fix migration backfill.

**Acceptance:** golden master pass без новых diff'ов.

---

## Task 4: Frontend type regen

**REQs:** REQ-5
**Files:**
- `frontend/src/shared/types/database.types.ts` (auto-regenerated)

**Steps:**
1. `cd frontend && npm run db:types`.
2. Verify `Specifications` row type включает 7 new fields.
3. Commit `database.types.ts` если изменения present.

**Acceptance:** TypeScript types отражают new schema; `npm run build` локально без errors.

---

## Task 5: `<PaymentSegmentsBlock>` component

**REQs:** REQ-3, REQ-5
**Files:**
- `frontend/src/features/quotes/ui/calculation-step/payment-segments-block.tsx` (NEW)
- `frontend/src/features/quotes/ui/calculation-step/payment-segments-block.test.tsx` (NEW)
- `frontend/src/features/quotes/ui/calculation-step/__tests__/` (если test со-located не предпочитается)

**Steps:**
1. Implement component per design.md spec.
2. Sub-components inline в file (или extract если разрастается):
   - `<PaymentRow>` — single anchor row.
   - `<QuickPresets>` — 5 preset buttons.
   - `<SumIndicator>` — badge с color по sumStatus.
3. State management via `useState` для controlled inputs.
4. Save handler:
   - Validate sum = 100% (refuse save если != 100).
   - Call server action `updateSpecificationPayment(specId, currentState)`.
   - Toast on success/failure.
   - Optimistic UI: button → "Сохранение…" → "Сохранено ✓" с auto-revert через 2s.
5. Empty state: `initial.advance_percent_from_client === 0` AND все остальные = 0 → render с anchor 1 default = 100 (UX hint).

**Tests (vitest):**
- Default render с initial = `{advance: 100, ...0}` → anchor 1 shows 100, anchor 5 shows 0, sum = 100% badge green.
- Change anchor 1 pct from 100 → 30 → anchor 5 pct shows 70.
- Sum > 100 → warning badge + save button disabled.
- Preset «30/70» click → anchor 1 pct = 30, anchor 5 days = 30 (preset days).
- Preset «Сброс» click → all zeroes, anchor 1 = 100.

**Acceptance:** component renders, presets work, validation works, tests pass.

---

## Task 6: Server action `updateSpecificationPayment`

**REQs:** REQ-4
**Files:**
- `frontend/src/entities/specification/server-actions.ts` (existing or NEW)

**Steps:**
1. Add `"use server"` async function per design.md.
2. Zod schema validation (включая refine для sum check).
3. Use existing admin client / RLS-aware client (verify project convention).
4. PATCH specifications с new fields.
5. revalidatePath для quote/spec route.
6. Return `{ success: true }` on success; throw with descriptive message on failure.

**Test:**
- Invalid sum → Zod throws.
- Valid input → mock supabase, assert correct payload.
- DB error → action throws + logs.

**Acceptance:** server action functional + unit tested.

---

## Task 7: Integration в calculation-form.tsx

**REQs:** REQ-3, REQ-4
**Files:**
- `frontend/src/features/quotes/ui/calculation-step/calculation-form.tsx`

**Steps:**
1. Remove 3 FormRows: «Аванс клиента» (~143), «До аванса» (~160), «До расчёта» (~175).
2. Insert `<PaymentSegmentsBlock>` в that position.
3. Pass `specId` + `initial` props (map из `spec` row).
4. Add `onSaved={() => router.refresh()}` to refetch calc inputs after save.
5. Verify visually что блок rendered correctly + остальные FormRows (Тип сделки, Инкотермс, Валюта КП, Наценка %) outsider blocked.

**Acceptance:** calc-step renders с новым блоком; saving works end-to-end.

---

## Task 8: Build + lint validation

**REQs:** REQ-5
**Files:** N/A

**Steps:**
1. `cd frontend && npm run lint` — fix any new warnings.
2. `npm run build` — no TS errors.
3. `pytest` — backend tests pass (especially golden master).

**Acceptance:** all gates green.

---

## Task 9: Manual browser smoke test on localhost

**REQs:** all
**Files:** N/A

**Steps:**
1. Start dev server `cd frontend && npm run dev`.
2. Open `localhost:3000/quotes/{id}?step=calculation` для test quote.
3. Verify `<PaymentSegmentsBlock>` rendered.
4. Apply «30/70» preset → check anchor 1 = 30, anchor 5 = 70, sum = 100% ✓.
5. Save → toast «Сохранено» → refresh page → verify values persisted.
6. Try invalid input (sum = 120) → save disabled + warning badge red.
7. Check calc-result section — verify cash-flow calculation reacts к new payment terms (если visible).

**Acceptance:** end-to-end UX works on localhost.

---

## Task 10: Documentation update

**REQs:** все
**Files:**
- `docs/plans/2026-05-24-product-decisions.md` — update Batch 23C-2 status to "shipped".
- `MEMORY.md` (если specific learnings).

**Steps:**
1. Update product-decisions doc: Row 46 status → "shipped via PR #XXX".
2. Add learning memory если migration backfill оказался tricky.

**Acceptance:** docs current.

---

## Task 11: Commit + PR

**REQs:** все
**Files:** N/A

**Steps:**
1. Single PR с миграцией + backend + UI changes:
   ```
   git checkout -b feat/testing2-row-46-payment-segments origin/main
   git add migrations/3XX_*.sql main.py frontend/src/...
   git commit -m "feat(calc): multi-segment client payment terms (Testing 2 row 46)

   Adds 5-anchor payment segments matching calc engine эталон. Replaces
   3-field UI with single block + presets. Backward-compat via backfill
   of payment_on_receiving_days from client_payment_term_after_upd.

   - Migration: 7 new columns + 8 CHECK constraints on specifications
   - Backend: build_calculation_inputs maps all 10 PaymentTerms fields
   - UI: <PaymentSegmentsBlock> with live sum validation + quick presets
   - Golden master verified pass (no new ACCEPTED_DIFFERENCES)

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
   git push -u origin feat/testing2-row-46-payment-segments
   gh pr create --head feat/testing2-row-46-payment-segments --base main \
     --title "feat(calc): multi-segment client payment terms (Testing 2 row 46)" \
     --body "..."
   ```
2. Monitor CI checks.
3. Squash-merge с `--delete-branch`.
4. Wait 90s before next merge (memory: feedback_parallel_deploys_container_conflict).
5. Verify prod deployment.

**Acceptance:** PR merged + prod has new feature.

---

## Constraints reminder (для имплементации)

- **NEVER** modify `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`.
- DB schema: всегда `kvota.` prefix.
- Migration via VPS git pull → `scripts/apply-migrations.sh`. **NOT scp**.
- Multi-statement migrations wrapped в BEGIN/COMMIT.
- After `scripts/apply-migrations.sh`: verify schema через `information_schema.columns`.
- `gh pr create` ALWAYS с `--head <branch> --base main`.
- All dropdown/select components MUST be searchable (project-wide standard).
- Co-author: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
