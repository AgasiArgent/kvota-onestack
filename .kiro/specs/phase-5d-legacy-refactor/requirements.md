# Requirements Document — Phase 5d: Legacy Surface Refactor

## Introduction

Phase 5c (13 local commits on branch `feat/soft-delete-services-audit`) migrated the core composition layer to a new schema (`invoice_items` + `invoice_item_coverage`), rewrote `composition_service`, moved the invoice edit-gate from `sent_at` to `procurement_completed_at`, and delivered non-destructive Split/Merge UI. Migration 284 (drop legacy schema) was planned for Phase 5c completion but was BLOCKED by a grep audit that discovered 27+ production-code locations still reading/writing 16 legacy columns on `quote_items` + the `invoice_item_prices` table.

Phase 5d completes the data-model migration by refactoring every **active** non-FastHTML consumer to read from the new schema. When all consumers land, migration 284 applies, and the Phase 5c + 5d work ships as one atomic deploy — no intermediate prod state is permitted.

FastHTML code is explicitly **out of scope**. Migration 284 will break FastHTML-rendered pages after it lands — this is acceptable per business stance ("we effectively don't use FastHTML anymore"). A separate Phase 6 initiative will: (1) audit Next.js → FastHTML residual dependencies, (2) migrate them to FastAPI, (3) archive all FastHTML code to `legacy-fasthtml/` folder for historical reference.

**Reference documents:**
- Predecessor: `.kiro/specs/phase-5c-invoice-items/{requirements,design,tasks}.md`
- Task 4 audit report: full inventory of 27+ surfaces (see memory `project_phase_5c_invoice_items.md` + design.md §7.4 of Phase 5c)
- Architecture: memory `project_phase_5c_invoice_items.md` + `feedback_oneshot_migrations_when_engine_locked.md`

**Migration strategy:** all Phase 5c (13) + Phase 5d commits ship as a single atomic push after migration 284 applies clean. Local branch accumulates until complete. No incremental prod deploy.

## Terminology

- **Composed Items** — output of `composition_service.get_composed_items(quote_id)` — items shaped for calc engine, sourced from invoice_items via coverage rows and the quote's selected invoice pointer
- **Surface** — any code location that reads or writes legacy `quote_items` columns or `invoice_item_prices` table
- **Active Surface** — surface called by Next.js, production workflow, /api/* JSON endpoints, or server-side services — **must be refactored**
- **Dormant Surface** — FastHTML HTML-rendering routes (`/procurement/{quote_id}`, its related FastHTML POST handlers) — **exempt**; will break post-migration-284; user-accepted trade-off
- **Pattern A/B/C/D/E** — refactor strategy per surface (see design.md §2)

---

## Requirements

### Requirement 1: Python Service Layer Refactor

**Objective:** All active Python service functions read composed or invoice_item-derived data, not legacy `quote_items` columns or `invoice_item_prices`.

#### Acceptance Criteria

1. `services/workflow_service.check_all_procurement_complete(quote_id)` shall return True iff every non-N/A quote_item of the quote has at least one covering invoice_item in the selected invoice with a non-null `purchase_price_original`. Implementation shall delegate to new helper `composition_service.is_procurement_complete(quote_id, supabase)`.

2. `services/xls_export_service.py` XLS generation shall read `kvota.invoice_items WHERE invoice_id = :id ORDER BY position`. Coverage rows are used to populate a "Покрывает" column listing source quote_items for merged invoice_items (or NULL/empty for 1:1). Split rows appear as independent invoice_items with their own weights/prices.

3. `services/customer_service.py` four queries at lines 1620-1621, 1699-1700, 1774, 1798 reading `base_price_vat`/`purchase_price_original` from `quote_items` shall be refactored to aggregate from `invoice_items` joined through `invoice_item_coverage` → `quote_items` (filtered by customer + status via the invoice's parent quote).

4. `services/currency_invoice_service.py` lines 174-176, 221 shall accept already-composed items from caller (if not already). If it reads raw `quote_items` directly, refactor to read `invoice_items` for the relevant invoice context.

5. `services/export_validation_service.py` column mapping at lines 238-240, 1309-1311 shall reference `invoice_items.weight_in_kg` / `invoice_items.base_price_vat` instead of `quote_items`.

6. `services/quote_version_service.py` snapshot serialization at lines 69, 380 shall write composed items shape (sourced from `composition_service.get_composed_items(quote_id)` at snapshot time), not raw `quote_items` legacy columns.

7. New helper `composition_service.is_procurement_complete(quote_id: str, supabase) -> bool` is added with unit tests covering: (a) quote where every qi is covered with non-null price → True, (b) quote where one qi is uncovered → False, (c) quote where one qi has coverage but price is NULL → False, (d) qi marked `is_unavailable=True` is excluded from the check, (e) quote with zero qi → False (empty quote can't be complete).

### Requirement 2: Python API Layer Refactor

**Objective:** All non-FastHTML API endpoints read from the new schema.

#### Acceptance Criteria

1. `api/procurement.py:240-245` kanban invoice aggregation shall query `invoice_items` directly instead of `invoice_item_prices`.

2. All 16+ ambiguous `main.py` call sites listed in Task 4 audit (lines 13044, 13174, 13381, 14076, 14799, 17814, 17845, 20095, 20105, 20932-20935, 22240, 22293, 25234, 25314, 30482, 43312) shall be classified during Group 3 as:
   - **BLOCKER** — production code reading legacy → refactor to composition_service/invoice_items
   - **FALSE POSITIVE** — reads composed items (from composition_service output) — no change needed
   - **DORMANT** — FastHTML HTML path → exempt, accept migration 284 breakage

3. FastHTML HTML routes at `main.py:17594-18800` (`/procurement/{quote_id}` page) and related FastHTML HTMX POST handlers at `main.py:19292, 19359, 19420-19900` (if FastHTML-only) shall NOT be refactored. They remain in main.py; migration 284 will break them at runtime, which is acceptable.

4. Non-FastHTML `/api/*` routes reading `quote_items.invoice_id` filter (main.py:19292-19495 subset, 19828-19844 bulk update — verify which are still called from Next.js) shall be refactored if Next.js or external API agents call them.

### Requirement 3: Frontend Entity Query Refactor

**Objective:** Next.js entity-layer queries read composed data via Supabase joins on new schema.

#### Acceptance Criteria

1. `frontend/src/entities/customer/queries.ts:405, 418` shall read `purchase_price_original` via JOIN `invoice_item_coverage` → `invoice_items` filtered by active composition pointer (`quote_items.composition_selected_invoice_id`).

2. `frontend/src/entities/supplier/queries.ts:262, 276` shall follow the same pattern.

3. `frontend/src/entities/position/queries.ts:145-209` supplier position page query shall read composed item shape.

4. `frontend/src/app/(app)/export/specification/[id]/route.tsx:60` spec XLS export shall select from `invoice_items` (filter by the spec's associated invoice) with `base_price_vat` field.

### Requirement 4: Frontend Component Refactor

**Objective:** All UI components reading legacy columns are refactored to consume composed/invoice_item data.

#### Acceptance Criteria

1. `features/quotes/ui/sales-step/sales-items-table.tsx:39, 82, 103-104` renders `base_price_vat` from composed items (source changes upstream in entity query or via passed-in prop).

2. `features/quotes/ui/pdf/kp-document.tsx:327` and `features/quotes/ui/pdf/spec-document.tsx:149-240` PDF exports render composed item data (same data as Next.js composition view).

3. `features/quotes/ui/calculation-step/calculation-results.tsx:117` reads `base_price_vat` from composed items returned by calc API.

4. `features/quotes/ui/control-step/invoice-comparison-panel.tsx:43, 229-233` reads `purchase_price_original` from invoice_items (it's a per-invoice comparison view, directly appropriate).

5. `features/quotes/ui/logistics-step/logistics-invoice-row.tsx:57` + `products-subtable.tsx:77-78` source `weight_in_kg` from invoice_items (per-invoice logistics data).

6. `features/quotes/ui/procurement-step/procurement-handsontable.tsx:41-416` COLUMN_KEYS bindings are re-pointed at invoice_items fields. Underlying query in invoice-card or parent shifts to invoice_items.

7. `features/quotes/ui/procurement-step/procurement-step.tsx:94` and `procurement-action-bar.tsx:19, 49` null-check logic uses composed items or invoice_items coverage status instead of `quote_items.purchase_price_original`.

### Requirement 5: Migration 284 Application

#### Acceptance Criteria

1. `tests/test_migration_284_no_legacy_refs.py` (pre-drop audit test, written in Phase 5c Task 4 spec) passes: zero grep matches for any of the 16 legacy columns or `invoice_item_prices` table name in production code (excluding `tests/`, `migrations/`, `docs/`, `.kiro/`, `changelog/`, `legacy-fasthtml/` if created by Phase 6, and `main.py:17594-18800` FastHTML region if tooling allows regional exclusion).

2. `migrations/284_drop_legacy_schema.sql` is written (content per Phase 5c spec Task 4) and applies cleanly on VPS dev DB.

3. `cd frontend && npm run db:types` regenerates `database.types.ts` without the 16 legacy columns on `quote_items` and without the `invoice_item_prices` table.

4. All `as any` casts introduced in Phase 5c (in `frontend/src/entities/quote/mutations.ts`, `quote-positions-list.tsx`, `invoice-card.tsx`, `split-modal.tsx`, `merge-modal.tsx`) are removed once regenerated types reflect the new schema.

### Requirement 6: Extended Bit-Identity Regression

**Objective:** Extend Phase 5c Task 3's regression to cover the post-Phase-5d state.

#### Acceptance Criteria

1. `tests/test_migration_283_bit_identity.py` (from Phase 5c) shall be extended to cover at least 10 representative production quotes — up from 5 — with a mix of: single-supplier quotes, multi-supplier composition quotes, quotes with completed procurement, and quotes with N/A items.

2. The regression shall pass in two modes:
   - Mode A (post-Phase-5c, pre-Phase-5d): runs against current schema state on VPS dev (backfill applied, legacy columns intact). Baseline.
   - Mode B (post-migration-284): runs against schema after 284 applies. Calc output must match Mode A bit-identically for every monetary field.

3. A new regression `tests/test_workflow_transitions_post_5d.py` asserts that `is_procurement_complete(quote_id)` returns True for quotes that would have returned True under legacy `check_all_procurement_complete`, and False for quotes that would have returned False. Tested on same 10 sample quotes.

### Requirement 7: Atomic Deploy Readiness

**Objective:** The combined Phase 5c + 5d ship as one atomic prod push.

#### Acceptance Criteria

1. Full Python test suite passes (including pre-existing test_deal_service et al. failures being no worse than pre-Phase-5c baseline).

2. Frontend test suite passes (317+ tests from Phase 5c baseline, plus new Phase 5d tests).

3. Browser E2E on staging (run once, post-5d-complete) covers end-to-end flow:
   - Create quote via sales flow
   - Procurement multi-supplier: create invoice A + invoice B with overlapping items
   - SplitModal + MergeModal demonstrations
   - Composition picker selection
   - Calculation with composed prices
   - XLS export (RU + EN per Phase 4b)
   - PDF KP document export
   - Click "Завершить закупку" — procurement completes (workflow transitions)
   - Logistics tab populates with correct data from invoice_items
   - Customs tab shows correct customs codes per invoice_item

4. Staging DB snapshot taken BEFORE migration 284 applies to prod — rollback safety net.

5. Prod deploy sequence:
   - `git push` all commits from branch to main
   - GitHub Actions builds + deploys code to beget-kvota
   - Coordinator SSH-applies migrations 281-284 in order via `scripts/apply-migrations.sh`
   - Post-deploy smoke on prod: verify 1-2 test quotes calc correctly + UI works

6. If any smoke fails: `git revert` the deploy commit + restore DB from snapshot taken pre-284.

---

## Non-Goals

- **FastHTML porting:** separate Phase 6 initiative. Migration 284 breaks FastHTML — accepted.
- **New features:** Phase 5d is pure refactor. No business-logic changes.
- **Performance optimization:** composition_service.get_composed_items query count stays at ≤3. Surfaces that were N+1 before remain N+1 unless fix is trivial alongside refactor. Dedicated perf pass is out of scope.
- **Multi-tenant access control:** existing RLS patterns preserved. No new policies.

## Out-of-Scope Risks (documented, accepted)

1. **FastHTML breakage** post-migration-284: acceptable. Users moved to Next.js. If any stakeholder attempts to visit `/procurement/{quote_id}` FastHTML page after deploy, they'll see errors or blank rows. Product team informed.

2. **Customer data model coupling:** customer_service aggregates cross-quote data. If the business wants "show customer's all-time purchase price trends", aggregating over `invoice_items` (which may have split/merged structure) could change results. Current implementation will produce values consistent with what was computed pre-Phase-5c for existing data (because backfill preserved 1:1 semantics for existing iip). For new quotes using Split/Merge, new semantics apply.

3. **Historical Phase 4a `approval_type="edit_sent_invoice"` rows:** Phase 5c API rename was not accompanied by data migration. Any in-flight Phase 4a approvals from before the Phase 5c push must be manually processed by admin or flagged as "expired".
