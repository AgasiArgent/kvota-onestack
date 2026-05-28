# Phase B Hotfix Plan — Max Effort

**Date:** 2026-05-04
**Author:** lean-tdd coordinator (Claude Opus 4.7)
**Status:** APPROVED PENDING USER (`Let's go with option 1 and plan fix with max effort` — 2026-05-04 ~20:30 UTC)
**Reverted to:** `5ed6a488` on origin/main (Phase B in original-3-bugs broken state)
**Research basis:** [tmp/research/phase-b-hotfix-research.md](../../tmp/research/phase-b-hotfix-research.md)
**Re-test report being addressed:** [tmp/test-reports/report-20260504-2006-retest.md](../../tmp/test-reports/report-20260504-2006-retest.md)

## Why we're here

Phase B (`customs-shared-certificates`) shipped 14 commits to main, deployed to prod, then was found broken on every cert/expense API call (`currency_of_quote` column doesn't exist). A hotfix attempt fixed 1 of 3 bugs cleanly but introduced 2 new regressions of equivalent severity. Reverted both hotfix commits. Now planning a max-effort retry with structural test-substrate upgrades that prevent this class of bug going forward.

The test architecture that allowed the bugs through is the actual problem:
- **Backend tests** mock the Supabase client wholesale via `_Stub` — `.select(...)` literals are accepted as opaque strings, never validated against a real schema. PostgREST 42703 errors are invisible.
- **Frontend tests** are SSR `renderToString` only — zero jsdom anywhere in `frontend/src/`, zero `@testing-library/*`. Component clicks, focus management, portal mounts, controlled/uncontrolled prop violations: all invisible to CI.

Both gaps must close before Phase B can be declared shipped. The fixes themselves are 30 minutes of work. The substrate is 90 minutes of one-time investment that pays back across every future feature.

## Scope (8 schema-drift sites — not 3)

The research agent enumerated every `.select(...)` call in `api/customs.py` and cross-referenced against `frontend/src/database.types.ts`. Originally we knew about 3 bugs from the browser test. Research found **8 broken column refs** plus the wrong-table bug:

| # | File:line | Helper | Bad column ref(s) | Class |
|---|-----------|--------|-------------------|-------|
| 1 | `api/customs.py:1756` | `_verify_quote_in_org` | `currency_of_quote` from `quotes` | wrong-column (lives on `quote_versions`) |
| 2 | `api/customs.py:1837` | `_compute_attached_items_payload` | `currency_of_quote` (re-selected) | wrong-column (same root cause as #1) |
| 3 | `api/customs.py:1849` | `_compute_attached_items_payload` | `purchase_price_original`, `purchase_currency`, `currency_of_base_price`, `base_price_vat` from `quote_items` | **WRONG-TABLE** (Phase 5d migration moved these to `invoice_items`) |
| 4 | `api/customs.py:438` | autofill | `license_ds_cost`, `license_ss_cost`, `license_sgr_cost` from `quote_items` | wrong-table (also moved to `invoice_items` in Phase 5d). Currently masked by `try/except` so not user-visible — but cleanup-grade tech debt. |

Plus 2 frontend bugs from the original report:

| # | File:line | Bug | Class |
|---|-----------|-----|-------|
| 5 | `customs-step.tsx:164` | `<TableViewsDropdown>` Base UI #31 fatal crash on click | controlled-vs-uncontrolled prop violation OR missing portal root introduced by the new `systemViews?` prop in the (now-reverted) hotfix. **Real DOM render needed to reproduce.** |
| 6 | `customs-item-dialog.tsx:1218-1249` | empty-state has only 1 of 2 mandated buttons; copy drifts from spec | spec violation REQ-8 AC#3 |

And the still-needed dropdown wiring:

| # | File:line | Bug | Class |
|---|-----------|-----|-------|
| 7 | `customs-step.tsx:164` | `CUSTOMS_SYSTEM_VIEWS` not spread into dropdown's `views` array | integration miss (URL persistence works; dropdown UI doesn't show 4 system views) |

## Architecture decisions

### AD-1: Replace `_compute_attached_items_payload` direct SELECT with 2-query JOIN through `invoice_item_coverage`

The research agent confirmed: price columns moved off `quote_items` in Phase 5d. Real recipe (per `services/composition_service.py:371-381` reference pattern):

```
For each attached_item_id:
    1. SELECT id, composition_selected_invoice_id FROM kvota.quote_items WHERE id IN (...)
    2. JOIN kvota.invoice_item_coverage ON quote_item_id IN (...)
       JOIN kvota.invoice_items ON invoice_item_coverage.invoice_item_id = invoice_items.id
       SELECT invoice_item_id, quote_item_id, ratio,
              invoice_items.purchase_price_original, invoice_items.purchase_currency,
              invoice_items.quantity
    3. Sum (purchase_price_original × invoice_items.quantity × coverage.ratio) per quote_item
    4. Convert to RUB once via services.calculation_helpers.convert_amount
    5. Feed list of Decimals into services.cost_split.split_cost_batch(bases, cert_cost) — unchanged
```

Two queries, no N+1, single conversion call. Decision: **do not** call `customs_value_rub_for_item` per LD-15's API surface — it expects a single `invoice_item` payload, but the helper here needs a batch. Use the underlying `_customs_value_in_rub` indirectly via a thin batch wrapper, or inline the formula since it's ~5 lines.

### AD-2: jsdom opt-in via per-file docblock; SSR remains the default

Research: zero existing DOM tests in `frontend/src/`, no jsdom installed. Adding global jsdom would risk regressing 1085 existing SSR tests. Per-file opt-in:

```typescript
// @vitest-environment jsdom
// then write the test as usual
```

Per-file docblock means **no `vitest.config.ts` change required**, no SSR-test breakage. Vitest natively supports the directive.

Setup file: `frontend/test-setup-jsdom.ts` polyfills `ResizeObserver`, `matchMedia`, and (if Base UI's Floating-UI chokes) `IntersectionObserver`. Wired in via vitest's `setupFiles` config — applied per-environment.

Stack: `jsdom@latest`, `@testing-library/react@latest`, `@testing-library/user-event@latest`, `@testing-library/jest-dom@latest`. All four go in `devDependencies`.

### AD-3: Backend schema-drift guard via static lint, not live postgrest

Research: backend tests have **zero** real-postgrest fixtures. Standing up postgrest in CI is days of work + flake risk + slow. Static lint is a 60-line script:

```python
# tools/check_select_columns.py
# 1. Walk Python AST of api/*.py
# 2. Find every `.select("col1, col2, ...")` literal call on a Supabase chain
# 3. Find the `.table("X")` or `.from_("X")` call in the same chain (typically 1-3 lines above)
# 4. Look up valid columns for kvota.X by parsing frontend/src/database.types.ts
#    (TypeScript type alias `Database['kvota']['Tables']['X']['Row']`)
# 5. Diff. Print violations as `file:line: column 'X' not in kvota.Y`
# 6. Exit 1 if any violations
```

Wire into `pytest` as a session fixture, OR run as a pre-commit / pre-push hook, OR add as CI step. Decision: **CI step only initially** (via `.github/workflows/lint.yml` addition) — surfaces violations without blocking local dev, but blocks the merge. Keep the script standalone so it can be promoted to pre-commit later.

Drift handling: if `database.types.ts` is stale, the lint will false-positive on real columns. Mitigation: run `npm run db:types` as part of the lint step (cheap, 2-3 sec).

### AD-4: Test the dropdown crash before fixing it (Phase 1 step 4)

Tradition says write the test, watch it FAIL, then fix. With jsdom newly installed and Base UI #31 being elusive, we need empirical proof that jsdom can reproduce the crash before we trust it as a regression guard. So:

1. Install substrate.
2. Write **one** jsdom test that renders `<TableViewsDropdown>` with the (still-broken from hotfix) `systemViews?` prop and clicks the trigger.
3. Run it. Confirm Base UI #31 reproduces in jsdom (not just real browser).
4. **Only then** proceed to fix the dropdown.
5. The same test that reproduced becomes the regression guard.

If jsdom does NOT reproduce: fall back to manual browser test for the dropdown click flow + document gap. We still get value from jsdom for everything else.

## Phased execution

### Phase 0 — Re-deploy revert + establish baseline (5 min)
- Confirm revert deploy completed (Deploy workflow on `5ed6a488` should be green per CI history check).
- Confirm prod is back to "original 3 bugs" state. Acceptance: `curl https://app.kvotaflow.ru/api/customs/certificates?quote_id=…` returns 500 with `currency_of_quote` error in container logs (sanity — we expect the original P0 to be live again).

### Phase 1 — Test substrate (90 min)

**Phase 1a — Frontend jsdom (60 min)**
1. `cd frontend && npm install --save-dev jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom`
2. Create `frontend/test-setup-jsdom.ts` with ResizeObserver / matchMedia polyfills + `@testing-library/jest-dom/vitest` import.
3. Update `vitest.config.ts` to add `setupFiles: { jsdom: ['./test-setup-jsdom.ts'] }` (or equivalent — verify the exact API; some vitest versions use `environmentMatchGlobs` for this).
4. Verify: `npm test` — all 1085 existing SSR tests still pass.
5. Write proof-of-concept test: `frontend/src/features/table-views/__tests__/dropdown-jsdom.dom.test.tsx` (note `.dom.test.tsx` naming convention so future tests follow it). Imports `<TableViewsDropdown>`, mounts with the broken `systemViews?` prop pattern from de3fd4d0 (look at the revert commit's diff to recreate it), clicks trigger.
6. Run. **MUST FAIL with Base UI #31 or equivalent error.** If it passes, stop — jsdom doesn't reproduce, fall back plan.
7. Once confirmed reproducing, leave the test as-is for Phase 3.

**Phase 1b — Backend schema-drift lint (30 min)**
1. Write `tools/check_select_columns.py` per AD-3. Use Python's `ast` module + a small regex/parser for `database.types.ts` (it's machine-generated, format is stable).
2. Add unit tests for the lint itself (e.g., feed a fake `customs.py` with a known bad column, assert it's flagged).
3. Run lint against current `api/customs.py` — should report **all 8 violations** above. Use this as acceptance for Phase 1b.
4. Add `.github/workflows/lint.yml` step that runs `npm run db:types --prefix frontend` then `python tools/check_select_columns.py`. Wire into existing CI gate.

### Phase 2 — Fix backend schema-drift (60 min)

**Phase 2a — Trivial drops (15 min)**
- `customs.py:1756`: drop `currency_of_quote` from `_verify_quote_in_org`'s select.
- `customs.py:1837`: drop `currency_of_quote` from `_compute_attached_items_payload`'s first select.
- `customs.py:1844`: drop the dead `or quote_row.get("currency_of_quote")` chain.
- `customs.py:438`: drop `license_ds_cost`, `license_ss_cost`, `license_sgr_cost` from autofill SELECT (they're masked by try/except today; clean drop, no replacement). Verify no consumer code reads them.

**Phase 2b — `_compute_attached_items_payload` rewrite (45 min)**
- Per AD-1: replace the body's direct `quote_items` SELECT with 2-query JOIN via `invoice_item_coverage` → `invoice_items`.
- Reference: `services/composition_service.py:371-381` for the JOIN syntax (PostgREST `select=...` with embedded `!inner`).
- Add 4 new backend tests covering the new computation:
  1. Single attached item → matches manual computation
  2. Multiple attached items, same supplier → shares sum to cert_cost
  3. Multiple attached items, mixed currencies → conversion happens once per RUB basis
  4. Empty `attached_item_ids` → returns empty list (no DB call) — confirms early-return preserved
- Run the schema-drift lint after the fix — it should now report **zero** violations.

### Phase 3 — Fix dropdown (45 min)
1. Read the reverted hotfix's diff (`git show de3fd4d0 -- frontend/src/features/table-views/`) to see what the new `systemViews?` prop looked like.
2. Diagnose the Base UI #31 root cause using the proof-of-concept jsdom test from Phase 1a step 5. Likely candidates:
   - Missing `Menu.Portal` wrapper → DOM tree has no portal root
   - Mixing controlled (`open`) and uncontrolled (`defaultOpen`) Menu state across the new prop
   - Re-render loop from prop change
3. Re-design the prop to avoid the violation. Options:
   - Pass `systemViews` as part of the existing `views` prop (single list with `is_system: true` flag), not as a separate prop. The dropdown internally splits into «Системные» group above «Личные»/«Общие». Lower change-surface.
   - Or: keep separate `systemViews?` prop but make the Menu state fully controlled with explicit portal mount.
4. Wire the chosen recipe into `customs-step.tsx`. Spread `[...CUSTOMS_SYSTEM_VIEWS, ...tableViews]` into a single `views` prop.
5. The proof-of-concept jsdom test now becomes the regression guard. Add 2 more jsdom tests: «4 system views appear in dropdown», «Click selects system view + URL updates with `?customs_view=system:tariffs-nds`».

### Phase 4 — Fix empty-state (15 min)
1. Add «Создать новый» button to `customs-item-dialog.tsx:1218-1249` empty-state container with default variant.
2. Wire to existing `setCertModalPreset(null)` / `setCreateCertModalOpen(true)` (same handler the popover-internal variant uses, already exists from commit 9a9fb90e).
3. Update copy to spec («Сертификат соответствия не оформлен»).
4. Add jsdom test: empty-state has 2 buttons; clicking «Создать новый» opens modal with current item pre-ticked.

### Phase 5 — Verification (30 min)

1. **Backend:** `pytest -x` + new schema-drift lint must PASS. Confirm `pytest tests/api/test_customs_certificates*.py -v` shows N+4 tests passing.
2. **Frontend:** existing 1085 SSR tests still pass + new jsdom tests pass (~6 expected).
3. **CI:** push to a branch first (NOT direct main); confirm green; merge.
4. **Browser test on prod:** wait for Deploy green, then re-run the manifest from `tmp/test-reports/manifest-20260504-1802.md` against `https://app.kvotaflow.ru` (with TEST-3 manifest correction noted). Acceptance: all 5 tests PASS, zero new console errors, zero orphan DB rows.
5. **Post-test cleanup:** delete any test certs/expenses created during the browser test.

## Time budget

| Phase | Time |
|-------|------|
| 0 — Baseline | 5 min |
| 1a — jsdom substrate | 60 min |
| 1b — Schema-drift lint | 30 min |
| 2a — Trivial column drops | 15 min |
| 2b — `_compute_attached_items_payload` rewrite | 45 min |
| 3 — Dropdown fix | 45 min |
| 4 — Empty-state fix | 15 min |
| 5 — Verification | 30 min |
| **Total** | **~4 hours** |

## Risks + mitigations

1. **jsdom doesn't reproduce Base UI #31.** Mitigation: fall back to manual prod browser test for click verification. We still get jsdom for everything else (empty-state click test in Phase 4 still works since modals are simpler than Base UI Menu).
2. **`_compute_attached_items_payload` rewrite has subtle math drift vs original Phase B fixture (`tests/fixtures/cost_split_fixtures.json`).** Mitigation: the JSON fixture asserts kopek-exact shares from Decimal arithmetic, not from any specific source-table SELECT. As long as the rewrite still outputs the correct list of Decimals from `split_cost_batch`, fixtures remain authoritative. Add a per-test parity check.
3. **Phase 5d migration broke other Phase A code paths we haven't audited.** Mitigation: the schema-drift lint catches any other `.select()` that references the dropped columns project-wide (run lint against ALL `api/*.py`, not just `customs.py`). Add this as the first run of the lint.
4. **`database.types.ts` stale at lint time** → false positives. Mitigation: lint always runs `npm run db:types` first.
5. **Branch + PR workflow drift.** Phase B was committed direct-to-main (per recent git history). For this hotfix, use a branch (`fix/customs-phase-b-schema-drift`) + PR + the CI lint gate as enforcement. Direct-to-main is the pattern that let the original bugs through.

## Authorization checkpoints

The user has authorized "Option 1 max effort" — that covers the whole plan. Stop and re-confirm only if:
- Phase 1a jsdom doesn't reproduce Base UI #31 → fall-back decision needed
- Phase 1b lint reports MORE than 8 violations across the project (not just `customs.py`) → scope-creep decision
- Phase 2b rewrite breaks existing cost-split fixture parity → design-level decision

Otherwise execute end-to-end.

## Out of scope (deferred)

- The text/plain "Internal Server Error" body that breaks frontend JSON parse — stack-wide FastAPI exception handler concern, separate fix.
- Migrating other Phase A `customs_*_expenses` references (already fully removed in Phase B Wave 4 Task 9).
- General test-substrate rollout to non-customs features — earned right by this PR; future work.
- Promoting the schema-drift lint to pre-commit hook — keep CI-only initially per AD-3.
