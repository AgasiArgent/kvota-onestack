# Tasks — Phase 5d: Legacy Surface Refactor

**Workflow:** `/lean-tdd` per task.
**Ship rule:** no push until entire Phase 5d complete. All commits accumulate on branch `feat/soft-delete-services-audit`.
**FastHTML:** exempt. Pattern E tasks omit refactor; migration 284 breaks them, accepted.

---

## Group 2 — Python Services

### Task 1 — New helper `composition_service.is_procurement_complete()`

**Goal:** Add the canonical procurement-readiness check.

**RED:**
- Extend `tests/test_composition_service.py` with `TestIsProcurementComplete`:
  - `test_all_items_priced_returns_true`
  - `test_one_item_uncovered_returns_false`
  - `test_covered_but_null_price_returns_false`
  - `test_na_item_is_excluded`
  - `test_empty_quote_returns_false`
  - `test_ignores_coverage_in_other_invoices` (coverage must be in the composition_selected_invoice_id invoice)

**GREEN:**
- Implement `is_procurement_complete(quote_id, supabase) -> bool` in `services/composition_service.py` per design.md §1.2.

**Commit:** `feat(phase-5d): add composition_service.is_procurement_complete helper`

### Task 2 — Refactor `workflow_service.check_all_procurement_complete`

**Dependency:** Task 1.

**RED:** Extend existing workflow_service test (or add new) asserting the function delegates to `is_procurement_complete`, returns identical bools on 5+ scenarios.

**GREEN:** Replace body of `check_all_procurement_complete(quote_id)` with `return composition_service.is_procurement_complete(quote_id, supabase)`. Remove the old `SELECT purchase_price_original FROM quote_items` query.

**Commit:** `refactor(phase-5d): workflow_service uses composition_service.is_procurement_complete`

### Task 3 — Refactor `services/xls_export_service`

**RED:** Extend `tests/test_xls_export_service.py`:
- Test XLS rows come from invoice_items, not quote_items
- Test split invoice_items appear as independent rows
- Test merge invoice_items appear once with "Покрывает: <qi names>" column populated
- Test 1:1 rows have empty "Покрывает" column

**GREEN:**
- Change `services/xls_export_service.py:109-111` from `table("quote_items").select("*").eq("invoice_id", ...)` to `table("invoice_items").select("*").eq("invoice_id", ...)`
- Extend select with `invoice_item_coverage(quote_item_id, quote_items(product_name, quantity))` JOIN for "Покрывает" column
- Rebuild XLS column mapping per design.md §2.1

**Commit:** `refactor(phase-5d): xls_export_service reads from invoice_items`

### Task 4 — Refactor `services/customer_service` (4 queries)

**RED:** Extend `tests/test_customer_service.py` with aggregation-correctness cases:
- Customer with one completed quote produces correct totals via new query
- Customer with multi-supplier quote aggregates from chosen composition only

**GREEN:**
- Refactor 4 queries at lines 1620-1621, 1699-1700, 1774, 1798 per design.md §2.1 Pattern C
- Coordinate with existing test fixtures — may need to add invoice_items + coverage seed data

**Commit:** `refactor(phase-5d): customer_service aggregates from invoice_items`

### Task 5 — Refactor `services/currency_invoice_service`

**RED:** Test that currency_invoice_service consumes items from composition_service.get_composed_items output (no raw quote_items read of legacy price columns).

**GREEN:** Update lines 174-176, 221 per design.md §2.1 Pattern A. If currently fetches items itself, refactor to accept items as argument OR delegate fetch to get_composed_items.

**Commit:** `refactor(phase-5d): currency_invoice_service consumes composed items`

### Task 6 — Refactor `services/export_validation_service`

**RED:** Test column mapping for export validation references invoice_items fields.

**GREEN:** Update lines 238, 240, 1309, 1311 column-name source to `invoice_items`.

**Commit:** `refactor(phase-5d): export_validation_service maps invoice_items columns`

### Task 7 — Refactor `services/quote_version_service` snapshots

**RED:** Test that snapshots (`quote_versions.input_variables` JSONB) contain composed-item shape, not raw legacy columns.

**GREEN:** Update lines 69, 380 to source items from `composition_service.get_composed_items()` at snapshot creation time.

**Commit:** `refactor(phase-5d): quote_version_service snapshots composed items`

---

## Group 3 — Python API

### Task 8 — Main.py ambiguous-sites classification audit

**Goal:** Resolve the 16 "ambiguous" lines in main.py flagged by Task 4 audit.

**Action (no commit, produces a report):**
Explore agent walks these 16 lines:
```
main.py:13044, 13174, 13381, 14076, 14799, 17814, 17845, 20095, 20105, 20932-20935,
22240, 22293, 25234, 25314, 30482, 43312
```

For each, read surrounding context (±20 lines), determine:
- What function/handler contains this line
- Does items-dict come from `composition_service.get_composed_items()` output? → FALSE POSITIVE
- Does items-dict come from raw `quote_items` query in the same handler? → BLOCKER
- Is the handler a FastHTML HTML route? → DORMANT

**Output:** markdown report saved to `.kiro/specs/phase-5d-legacy-refactor/main-py-classification.md`. Coordinator reads and decides per-site action.

**Deferred:** per-site fix tasks spawned based on classification results.

### Task 9 — Refactor `api/procurement.py:240` kanban aggregate

**RED:** `tests/test_api_procurement_kanban.py` test asserts kanban aggregate reads invoice_items, not iip.

**GREEN:** Swap query from `invoice_item_prices` to `invoice_items`.

**Commit:** `refactor(phase-5d): api/procurement.py kanban reads invoice_items`

### Task 10 — Refactor main.py non-FastHTML /api/* sites (driven by Task 8 output)

**RED:** Per-site test asserts behavior unchanged (regression guard).

**GREEN:** Per-site refactor per classification. BLOCKERS move to composition_service / invoice_items. DORMANTs left alone.

**Commit:** one commit per site or bundle of related sites (coordinator judgment).

---

## Group 4 — Frontend Entity Queries

### Task 11 — Refactor entity queries (customer, supplier, position, spec export)

**RED:** Extend `__tests__/queries.test.ts` for each entity:
- Customer query returns composed price data sourced via coverage
- Supplier query returns same
- Position query returns same
- Spec export route yields invoice_items-sourced rows

**GREEN:**
- `frontend/src/entities/customer/queries.ts:405, 418` — JOIN per design.md §2.3 pattern
- `frontend/src/entities/supplier/queries.ts:262, 276` — same
- `frontend/src/entities/position/queries.ts:145-209` — same
- `frontend/src/app/(app)/export/specification/[id]/route.tsx:60` — switch to invoice_items

**Commit:** `refactor(phase-5d): entity queries read via invoice_item_coverage`

---

## Group 5 — Frontend Components (3 parallel agents)

### Task 12 — Agent A: Sales + Calculation components

**Files:** sales-items-table.tsx, calculation-results.tsx, invoice-comparison-panel.tsx

**RED:** Extend existing component tests to assert data source is composed items (or flag as already-correct if upstream entity query change from Task 11 flows through).

**GREEN:** For each file, verify data flow. If component uses its own Supabase call reading `quote_items.base_price_vat` or `purchase_price_original` — refactor. If it reads from props populated by entity query (already refactored in Task 11) — just update field names if they shifted.

**Commit:** `refactor(phase-5d): sales + calculation components read composed data`

### Task 13 — Agent B: PDF exports

**Files:** kp-document.tsx, spec-document.tsx

**RED:** PDF snapshot tests (if exist) — verify rendered composed prices correct on split/merge cases.

**GREEN:** Update data sourcing in the two PDF components. Likely consume composed items prop — just verify upstream passes the right shape.

**Commit:** `refactor(phase-5d): PDF exports consume composed items`

### Task 14 — Agent C: Procurement + Logistics components

**Files:** procurement-handsontable.tsx, procurement-step.tsx, procurement-action-bar.tsx, logistics-invoice-row.tsx, products-subtable.tsx

**RED:** Tests for each:
- procurement-handsontable COLUMN_KEYS bind to invoice_items fields (test by asserting column defs reference correct keys)
- procurement-step null-check logic uses composed data
- procurement-action-bar counter uses composed data
- logistics-invoice-row reads invoice_items.weight_in_kg
- products-subtable same

**GREEN:** Refactor per component. COLUMN_KEYS for handsontable is a data-binding change — shift the source query up in the parent (invoice-card already reads invoice_items in Phase 5c, so handsontable gets invoice_item rows, just rebind column keys).

**Commit:** `refactor(phase-5d): procurement + logistics components bind to invoice_items`

---

## Group 6 — Migration 284 + Types Regen

### Task 15 — Pre-drop audit + migration 284 application

**Prerequisite:** Groups 2-5 all complete and tested.

**Action (coordinator-managed, not agent-scripted):**

1. Run `pytest tests/test_migration_284_no_legacy_refs.py -v` — must PASS (zero legacy refs in production code, FastHTML exempt region noted).
2. Manually SSH-apply migration 284 on VPS dev:
   ```bash
   scp migrations/284_drop_legacy_schema.sql beget-kvota:/tmp/
   ssh beget-kvota "docker exec -i supabase-db psql -U postgres -d postgres < /tmp/284_drop_legacy_schema.sql"
   ```
3. Verify columns dropped via `information_schema.columns` query.
4. `cd frontend && npm run db:types` — regenerate TypeScript types.
5. Commit regenerated `database.types.ts` + any frontend file where `as any` cast is now unnecessary (grep for `as any` in recent commits, remove where possible).

**Commit:** `feat(phase-5d): apply migration 284 + regenerate TypeScript types`

### Task 16 — Remove `as any` casts introduced in Phase 5c

**Dependency:** Task 15 (types regenerated).

**RED:** Existing tests should still pass after cast removal (compilation check).

**GREEN:** Grep `as any` in `frontend/src/entities/quote/mutations.ts`, `quote-positions-list.tsx`, `invoice-card.tsx`, `split-modal.tsx`, `merge-modal.tsx`. Remove each cast. `tsc --noEmit` should pass.

**Commit:** `refactor(phase-5d): drop as-any casts now that types reflect schema`

---

## Group 7 — QA + Atomic Deploy

### Task 17 — Extended bit-identity regression

**RED:** Extend `tests/test_migration_283_bit_identity.py`:
- Sample expanded to 10+ representative production quotes
- Two-mode run: Mode A (pre-migration-284 baseline from VPS snapshot) + Mode B (post-migration-284 live)
- Both modes must produce bit-identical calc outputs for every monetary field

**GREEN:** If any quote diverges, investigate root cause. Likely causes: floating-point ordering changes, uncovered edge case in composition_service, markup/supplier_discount handling (per design.md §7.1 open item).

**Commit:** `test(phase-5d): extended bit-identity regression on 10 prod quotes`

### Task 18 — Workflow transition regression

**RED:** `tests/test_workflow_transitions_post_5d.py` — assert `is_procurement_complete` matches legacy `check_all_procurement_complete` expectation for the 10 sample quotes.

**GREEN:** If any mismatch, fix implementation of `is_procurement_complete` to match legacy behavior exactly.

**Commit:** `test(phase-5d): workflow transition regression`

### Task 19 — Browser E2E on staging

**Not a code task — browser-test skill invocation.**

Run Playwright MCP against localhost:3000 + prod Supabase (via `frontend/.env.local`). Manifest per design.md §5 spec §7.3.

Record pass/fail. If fail: create fix tasks, loop back to appropriate Group.

### Task 20 — Push, PR, CI, deploy

**Coordinator-managed:**

1. Final sanity: `git log --oneline main..HEAD` — verify ~30 commits
2. `git push origin feat/soft-delete-services-audit`
3. `gh pr create` — title "Phase 5c + 5d: invoice_items composition engine + legacy refactor"
4. `/code-review` runs on PR
5. Address findings (if any) via Ralph Loop
6. Merge PR
7. GitHub Actions deploys code
8. SSH-apply migrations 281, 282, 283, 284 in order on prod DB
9. Post-deploy smoke: 1 test quote full procurement flow on prod
10. Update changelog, close ClickUp tasks, finalize session

**Commit:** `docs(changelog): v0.7.0 — Phase 5c invoice_items + Phase 5d legacy refactor`

---

## Critical Path

```
Task 1 (is_procurement_complete) → Task 2 (workflow_service refactor)
                                                ↓
Tasks 3-7 (services: xls, customer, currency, export_validation, quote_version) ← can run in parallel
                                                ↓
Task 8 (main.py classification audit) → Tasks 9-10 (api refactor)
                                                ↓
Task 11 (frontend entity queries)
                                                ↓
Tasks 12-14 (3 parallel agents for components)
                                                ↓
Task 15 (migration 284 apply) → Task 16 (cast removal)
                                                ↓
Task 17 (bit-identity) + Task 18 (workflow regression)
                                                ↓
Task 19 (browser E2E)
                                                ↓
Task 20 (push + deploy)
```

Estimated total: **4-5 working days** with good agent parallelism.

---

## Rollback

- Pre-migration-284: branch is the only state. Reset branch pointer to drop Phase 5d commits. Phase 5c commits remain for follow-up attempt.
- Post-migration-284 applied on dev but not yet prod: revert migration via manual DDL (restore columns from dev snapshot backup). Group 5d commits stay or roll back per coordinator decision.
- Post-prod deploy: `git revert` merge commit + DB restore from snapshot taken before 284 applied on prod. Full prod rollback is possible but expensive — aim to avoid via staging verification.
