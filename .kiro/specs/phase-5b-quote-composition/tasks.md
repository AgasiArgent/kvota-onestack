# Implementation Tasks — Phase 5b Quote Composition Engine

> **For agentic workers:** Execute tasks sequentially. Each task is independently commitable. Each commit touches ONLY the files its task explicitly changes — use `git add <explicit-paths>`, never `git add .` or `-A` (parallel procurement work in the tree must not be swept in). All commits include `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>` footer.

**Check-in discipline:** The user has explicitly requested a pause after **Task 1 commit** before continuing to Task 2. Subsequent cadence to be agreed at that checkpoint.

**Spec references:**
- Requirements: `.kiro/specs/phase-5b-quote-composition/requirements.md`
- Design: `.kiro/specs/phase-5b-quote-composition/design.md`
- Research: `.kiro/specs/phase-5b-quote-composition/research.md`
- Scope doc: `docs/plans/2026-04-10-phase-5b-quote-composition-engine.md`

**Locked files (never modify):** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`

---

## Task 1: Migration 263 — `invoice_item_prices` junction table

**Requirements:** 1.1, 1.2, 1.5, 10.1, 10.2
**Dependencies:** none
**Check-in point:** STOP after commit and wait for user confirmation before Task 2.

**Files:**
- Create: `migrations/263_invoice_item_prices.sql`
- Create: `frontend/src/shared/types/database.types.ts` (regenerated, not hand-edited)

**Steps:**
- [ ] Write `migrations/263_invoice_item_prices.sql` with the full DDL from `design.md` § "Migration 263" — junction table (including `organization_id NOT NULL` column) + 4 indexes + 4 RLS policies (org + role pattern) + comments
- [ ] Dry-run locally: `cat migrations/263_invoice_item_prices.sql | grep -E "^(CREATE|ALTER|COMMENT|GRANT)"` and visually verify structure
- [ ] Apply via SSH: `cat migrations/263_invoice_item_prices.sql | ssh beget-kvota 'docker exec -i supabase-db psql -U postgres -d postgres -v ON_ERROR_STOP=1'`
- [ ] Verify table exists: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c '\\dt kvota.invoice_item_prices'"` — expect one row
- [ ] Verify columns: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c '\\d kvota.invoice_item_prices'"` — expect `invoice_id, quote_item_id, organization_id, purchase_price_original, purchase_currency, base_price_vat, price_includes_vat, version, frozen_at, frozen_by, created_at, updated_at, created_by`
- [ ] Verify RLS enabled and policy count: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT COUNT(*) FROM pg_policies WHERE schemaname='kvota' AND tablename='invoice_item_prices'\""` — expect 4
- [ ] Record in tracking table: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"INSERT INTO kvota.migrations (filename) VALUES ('263_invoice_item_prices.sql') ON CONFLICT DO NOTHING\""`
- [ ] Reload PostgREST schema cache: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"NOTIFY pgrst, 'reload schema'\""`
- [ ] Regenerate frontend types: `cd frontend && npm run db:types && cd ..`
- [ ] Verify type regen worked: `grep -q invoice_item_prices frontend/src/shared/types/database.types.ts && echo OK`
- [ ] Commit:
```bash
git add migrations/263_invoice_item_prices.sql frontend/src/shared/types/database.types.ts
git commit -m "$(cat <<'EOF'
feat(composition): migration 263 — invoice_item_prices junction

Junction table for Phase 5b multi-supplier quote composition.
Holds per-item prices from each supplier invoice with versioning
(version + frozen_at columns).

RLS uses the project-standard org + role pattern with an
explicit organization_id column. The original reference-predicate
approach was dropped after pre-check revealed kvota.invoices has
RLS disabled entirely — see .kiro/specs/phase-5b-quote-composition/
research.md § "Pre-check findings".

Part of Phase 5b — Quote Composition Engine.
See: docs/plans/2026-04-10-phase-5b-quote-composition-engine.md

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```
- [ ] **STOP — report completion to user and wait for "continue" before Task 2**

---

## Task 2: Migration 264 — Composition pointer + verification columns

**Requirements:** 2.4, 3.3, 5.1
**Dependencies:** Task 1

**Files:**
- Create: `migrations/264_composition_pointer_and_verification.sql`
- Modify: `frontend/src/shared/types/database.types.ts` (regenerated)

**Steps:**
- [ ] Write `migrations/264_composition_pointer_and_verification.sql` with DDL from `design.md` § "Migration 264" — ALTER TABLE quote_items ADD composition_selected_invoice_id + partial index; ALTER TABLE invoices ADD verified_at/verified_by + partial index; column comments
- [ ] Apply via SSH (same pattern as Task 1)
- [ ] Verify: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT column_name FROM information_schema.columns WHERE table_schema='kvota' AND table_name='quote_items' AND column_name='composition_selected_invoice_id'\""` — expect one row
- [ ] Verify invoices columns: similar query for `verified_at`, `verified_by`
- [ ] Record in `kvota.migrations` tracking table
- [ ] Reload PostgREST schema
- [ ] Regenerate frontend types: `cd frontend && npm run db:types`
- [ ] Commit:
```bash
git add migrations/264_composition_pointer_and_verification.sql frontend/src/shared/types/database.types.ts
git commit -m "$(cat <<'EOF'
feat(composition): migration 264 — composition pointer + verification

Adds quote_items.composition_selected_invoice_id (active invoice
per item) and invoices.verified_at/verified_by (locks direct edits
behind head_of_procurement approval, per Decision #5).

ON DELETE SET NULL on composition pointer — composition_service
falls back to legacy quote_items.invoice_id when pointer is cleared.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Migration 265 — Idempotent backfill

**Requirements:** 5.5, 9.1, 9.2, 9.3
**Dependencies:** Task 2

**Files:**
- Create: `migrations/265_backfill_composition.sql`

**Steps:**
- [ ] Write `migrations/265_backfill_composition.sql` with the 3 idempotent statements from `design.md` § "Migration 265": INSERT ... ON CONFLICT DO NOTHING into invoice_item_prices from `quote_items JOIN quotes` (JOIN resolves `organization_id` for each iip row); UPDATE quote_items SET composition_selected_invoice_id = invoice_id WHERE composition_selected_invoice_id IS NULL; UPDATE invoices SET verified_at WHERE status='completed' AND verified_at IS NULL
- [ ] Before applying: snapshot current state for regression: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT COUNT(*) FROM kvota.quote_items WHERE invoice_id IS NOT NULL\""` — remember this count for verification
- [ ] Apply via SSH
- [ ] Verify iip row count matches the quote_items count: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT COUNT(*) FROM kvota.invoice_item_prices WHERE version=1\""` — should equal the pre-apply count
- [ ] Verify organization_id populated on every iip row: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT COUNT(*) FROM kvota.invoice_item_prices WHERE organization_id IS NULL\""` — expect 0
- [ ] Verify composition pointer set: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT COUNT(*) FROM kvota.quote_items WHERE composition_selected_invoice_id IS NOT NULL\""` — should equal count from previous step
- [ ] Verify idempotency: re-apply the migration and expect ZERO new iip rows + ZERO new pointer updates + ZERO new verified stamps
- [ ] Record in `kvota.migrations` tracking table
- [ ] Reload PostgREST schema
- [ ] Commit:
```bash
git add migrations/265_backfill_composition.sql
git commit -m "$(cat <<'EOF'
feat(composition): migration 265 — idempotent backfill

Backfills invoice_item_prices from existing quote_items.invoice_id
pairs (ON CONFLICT DO NOTHING), sets composition_selected_invoice_id
= invoice_id for legacy items, marks status='completed' invoices as
verified (verified_at = updated_at).

Idempotent — running twice is a no-op.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `composition_service.py` — pure Python service

**Requirements:** 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 8.1, 8.2, 10.5
**Dependencies:** Task 3

**Files:**
- Create: `services/composition_service.py`
- Create: `tests/test_composition_service.py`

**Steps:**
- [ ] Create `services/composition_service.py` with function signatures from `design.md` § "Composition Service Interface": `get_composed_items`, `get_composition_view`, `apply_composition`, `validate_composition`, `freeze_composition`
- [ ] Implement `get_composed_items(quote_id, supabase_client) -> List[Dict]` with a single SELECT using PostgREST LEFT JOIN: `quote_items` with `invoice_item_prices!composition_selected_invoice_id(*)`. For each row, overlay `purchase_price_original`, `purchase_currency`, `base_price_vat`, `price_includes_vat` from the iip row when present; otherwise keep quote_items values. All other fields pass through unchanged.
- [ ] Implement `validate_composition(quote_id, selection_map, supabase_client) -> ValidationResult` — single SELECT checking every `(quote_item_id, invoice_id)` pair in selection_map exists in invoice_item_prices. Build error list per-item.
- [ ] Implement `apply_composition(quote_id, selection_map, supabase_client, user_id, quote_updated_at)` — call validate_composition; check quotes.updated_at matches quote_updated_at (raise ConcurrencyError on mismatch); UPDATE quote_items.composition_selected_invoice_id for all items in selection_map; UPDATE quotes.updated_at
- [ ] Implement `get_composition_view(quote_id, supabase_client, user_id) -> CompositionView` — single SELECT joining quote_items → invoice_item_prices → invoices → suppliers; group alternatives per quote_item; compute `composition_complete = all items have selection`
- [ ] Implement `freeze_composition(quote_id, user_id, supabase_client) -> int` — UPDATE invoice_item_prices SET frozen_at=now(), frozen_by=user_id WHERE (quote_item_id, invoice_id) matches current composition_selected_invoice_id AND frozen_at IS NULL; return rowcount
- [ ] Verify locked files: `grep -l "calculation_engine\|calculation_models\|calculation_mapper" services/composition_service.py` — expect ZERO matches
- [ ] Write `tests/test_composition_service.py` covering:
  - `test_get_composed_items_overlays_iip_price_when_pointer_set`
  - `test_get_composed_items_falls_back_to_legacy_when_pointer_null`
  - `test_get_composed_items_preserves_all_non_price_fields`
  - `test_get_composed_items_executes_single_query` (assert exactly 1 supabase select call via mock)
  - `test_validate_composition_happy_path`
  - `test_validate_composition_rejects_non_existent_iip`
  - `test_apply_composition_atomic_update`
  - `test_apply_composition_raises_concurrency_error_on_stale_updated_at`
  - `test_apply_composition_calls_validate_first`
  - `test_freeze_composition_stamps_frozen_at`
  - `test_freeze_composition_idempotent_skips_already_frozen`
  - `test_freeze_composition_only_affects_given_quote`
- [ ] Run tests: `pytest tests/test_composition_service.py -v` — expect all green
- [ ] Commit:
```bash
git add services/composition_service.py tests/test_composition_service.py
git commit -m "$(cat <<'EOF'
feat(composition): add composition_service with unit tests

Pure Python service that adapts invoice_item_prices composition
into the List[Dict] shape build_calculation_inputs() expects.
Single SQL query per get_composed_items call (no N+1).

Does NOT import calculation_engine / calculation_models /
calculation_mapper — the locked files stay byte-identical.

12 unit tests cover overlay logic, validation, atomic apply,
optimistic concurrency, freeze idempotency.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Hook `composition_service` into the 3 calc entry points + regression test

**Requirements:** 3.5, 4.1, 4.2, 4.3, 4.4, 9.4, 9.5
**Dependencies:** Task 4

**Files:**
- Modify: `main.py` (~3 small diffs at the quote_items read sites)
- Create: `tests/test_calc_regression_phase_5b.py`

**Steps:**
- [ ] Enumerate actual call sites: `grep -n "build_calculation_inputs(" main.py` — record every line number. The scope doc expects 13303, 14188, 14846 but verify and adjust if drifted.
- [ ] For each call site, find the preceding `quote_items` read (typically 10-15 lines above the call) and replace with `from services.composition_service import get_composed_items; items = get_composed_items(quote_id, supabase)`
- [ ] Verify locked files untouched: `git diff calculation_engine.py calculation_models.py calculation_mapper.py` — expect EMPTY output
- [ ] Before any code change, capture pre-change calculation snapshots for 5 representative existing quotes (pick 5 quote IDs from prod via SSH): `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT id, total_amount_quote, total_with_vat_quote, cogs_quote_currency FROM kvota.quotes WHERE status='calculated' ORDER BY updated_at DESC LIMIT 5\""` — save this output to `tests/fixtures/phase_5b_regression_snapshot.json`
- [ ] Write `tests/test_calc_regression_phase_5b.py`:
  - `test_calculation_bit_identical_on_representative_quotes` — for each of the 5 quote IDs, call the calculation path (same entry points that use composition_service now) and assert every monetary field in the output matches the snapshot to 4 decimal places
  - `test_composition_service_hooked_at_all_call_sites` — grep-based test that asserts no remaining `quote_items.select("*").eq("quote_id"` patterns exist in main.py near `build_calculation_inputs(` calls
- [ ] Run tests: `pytest tests/test_composition_service.py tests/test_calc_regression_phase_5b.py -v` — expect all green
- [ ] Run the full main.py calculation path manually for one of the 5 quotes via the preview endpoint (local): `python main.py &` then `curl -X POST http://localhost:5001/quotes/{quote_id}/preview ...` and diff the response against the snapshot
- [ ] Commit:
```bash
git add main.py tests/test_calc_regression_phase_5b.py tests/fixtures/phase_5b_regression_snapshot.json
git commit -m "$(cat <<'EOF'
feat(composition): hook composition_service into 3 calc entry points

Replaces the three quote_items reads that feed build_calculation_inputs()
with composition_service.get_composed_items(quote_id, supabase) calls.
build_calculation_inputs() signature and body unchanged.

Regression test asserts bit-identical calculation output on 5 existing
quotes (pre-snapshot in tests/fixtures/phase_5b_regression_snapshot.json).

Verified: calculation_engine.py, calculation_models.py, and
calculation_mapper.py show zero modifications.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `api/composition.py` — GET + POST `/api/quotes/{id}/composition`

**Requirements:** 2.1, 2.2, 2.5, 2.6, 2.7, 10.3, 10.4, 10.5
**Dependencies:** Task 4

**Files:**
- Create: `api/composition.py`
- Create: `tests/test_composition_api.py`
- Modify: `main.py` (route registration only — 2 lines)

**Steps:**
- [ ] Create `api/composition.py` with two handlers: `get_composition(request)` and `apply_composition(request)`. Both follow `api-first.md` structured docstring format (Path/Params/Returns/Side Effects/Roles).
- [ ] `get_composition` reads quote_id from path, auth via `request.state.api_user` (dual auth pattern), checks quote visibility via existing helper (same pattern as `api/deals.py`); calls `composition_service.get_composition_view(...)`; returns `{success: True, data: {...}}`; returns 404 on visibility denial
- [ ] `apply_composition` reads quote_id from path + selection + quote_updated_at from body; auth check; calls `composition_service.apply_composition(...)`; returns 400 on ValidationError, 409 on ConcurrencyError, 200 on success
- [ ] Register routes in main.py (2 new lines):
  ```python
  from api.composition import get_composition, apply_composition
  @rt("/api/quotes/{quote_id}/composition", methods=["GET"])
  async def http_get_composition(request): return await get_composition(request)
  @rt("/api/quotes/{quote_id}/composition", methods=["POST"])
  async def http_apply_composition(request): return await apply_composition(request)
  ```
- [ ] Write `tests/test_composition_api.py`:
  - `test_get_composition_returns_alternatives_for_each_item`
  - `test_get_composition_404_when_quote_not_visible_to_user`
  - `test_post_composition_happy_path_updates_pointer`
  - `test_post_composition_400_on_invalid_selection`
  - `test_post_composition_409_on_stale_updated_at`
  - `test_post_composition_404_when_quote_not_visible`
  - `test_post_composition_403_when_user_cannot_edit_composition`
- [ ] Run tests: `pytest tests/test_composition_api.py -v` — expect all green
- [ ] Commit:
```bash
git add api/composition.py tests/test_composition_api.py main.py
git commit -m "$(cat <<'EOF'
feat(composition): add GET+POST /api/quotes/{id}/composition endpoints

GET returns current composition with all supplier alternatives
per item, for the CompositionPicker UI.

POST validates and applies the user's selection atomically, with
optimistic concurrency check on quotes.updated_at.

Follows api-first.md docstring standard. Returns 404 on visibility
denial (per access-control.md "404 on denial" rule).

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Invoice verify + edit-request + approve/reject endpoints

**Requirements:** 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.7
**Dependencies:** Task 3

**Files:**
- Modify: `api/composition.py` (add 4 more handlers to existing module)
- Modify: `tests/test_composition_api.py` (add test cases)
- Modify: `main.py` (register 4 more routes)

**Steps:**
- [ ] Add `verify_invoice(request)` handler to `api/composition.py`: reads invoice_id from path; auth; role check (procurement, procurement_senior, head_of_procurement, admin); UPDATE invoices SET verified_at=now(), verified_by=user_id WHERE id=invoice_id; return {verified_at, verified_by}
- [ ] Add `request_invoice_edit(request)` handler: reads invoice_id, proposed_changes (dict), reason from body; constructs payload dict per `design.md` § "JSON diff format"; calls `approval_service.request_approval(target_role='head_of_procurement', payload=payload, reason=reason)`; returns `{approval_id, status: 'pending'}`
- [ ] Add `approve_invoice_edit(request)` handler: reads invoice_id + approval_id from path; auth + role check (head_of_procurement, admin only); fetch approval row; ensure status is 'pending'; read diff from payload; apply diff to invoices + invoice_item_prices atomically in a transaction; UPDATE approval row status='approved', approver_id=user_id; return {applied_changes}
- [ ] Add `reject_invoice_edit(request)` handler: symmetric; UPDATE approval row status='rejected' with optional reason; no changes to invoice
- [ ] Modify the existing invoice update endpoint at `main.py:19100` to reject direct updates to price-carrying fields when `invoices.verified_at IS NOT NULL` unless the request carries an `approval_id` for an approved approval; return HTTP 409 `INVOICE_VERIFIED`
- [ ] Register 4 new routes in main.py:
  - `POST /api/invoices/{invoice_id}/verify`
  - `POST /api/invoices/{invoice_id}/edit-request`
  - `POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/approve`
  - `POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/reject`
- [ ] Add tests to `tests/test_composition_api.py`:
  - `test_verify_invoice_stamps_verified_at`
  - `test_verify_invoice_403_for_non_procurement_role`
  - `test_direct_edit_of_verified_invoice_returns_409`
  - `test_edit_request_creates_approval_row_with_diff_payload`
  - `test_approve_invoice_edit_applies_diff_atomically`
  - `test_approve_invoice_edit_403_for_non_head_role`
  - `test_reject_invoice_edit_marks_rejected_no_changes`
- [ ] Run tests: `pytest tests/test_composition_api.py -v`
- [ ] Commit:
```bash
git add api/composition.py tests/test_composition_api.py main.py
git commit -m "$(cat <<'EOF'
feat(composition): verify + edit-approval endpoints for invoices

Adds 4 endpoints reusing the existing approval_service:
  POST /api/invoices/{id}/verify
  POST /api/invoices/{id}/edit-request
  POST /api/invoices/{id}/edit-approval/{approval_id}/approve
  POST /api/invoices/{id}/edit-approval/{approval_id}/reject

Verified invoices can only be edited via an approval flow
gated by head_of_procurement (Decision #5 — included from day 1,
not deferred).

Direct edit attempts on verified invoices return HTTP 409
INVOICE_VERIFIED unless the request carries an approved
approval_id.

JSON diff payload format: { fields: {old, new}, reason }.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Next.js `useQuoteComposition` entity query + access guard

**Requirements:** 2.1, 2.3, 10.3, 10.6
**Dependencies:** Task 6

**Files:**
- Modify: `frontend/src/entities/quote/queries.ts` — add `useQuoteComposition` hook + `fetchQuoteComposition` server function + `canAccessQuoteComposition` guard
- Modify: `frontend/src/shared/lib/roles.ts` — add `canEditComposition()` helper if not present

**Steps:**
- [ ] Read current `frontend/src/entities/quote/queries.ts` to match existing hook conventions (TanStack Query patterns, error handling, typed returns)
- [ ] Add `useQuoteComposition(quoteId: string)` hook using TanStack Query with `queryKey: ['quote', quoteId, 'composition']`, `staleTime: 30_000`
- [ ] Add `fetchQuoteComposition(quoteId)` server-side function that uses Supabase direct to LEFT JOIN quote_items → invoice_item_prices → invoices → suppliers, grouping alternatives per quote_item. Return shape: `{ items: [...], can_edit, composition_complete }`
- [ ] Add `canAccessQuoteComposition(quoteId, user)` — delegates to existing `canAccessQuote()` for visibility + checks `canEditComposition(user)` for edit permission
- [ ] Add `canEditComposition(user)` in `shared/lib/roles.ts`: returns true for `sales`, `head_of_sales`, `head_of_procurement`, `admin`
- [ ] Write Vitest unit tests (separate file if entities/quote has test colocations, else skip — check convention):
  - `canEditComposition returns true for sales`
  - `canEditComposition returns false for logistics`
  - `canEditComposition returns true for admin`
- [ ] Run lint + type check: `cd frontend && npm run lint && npx tsc --noEmit`
- [ ] Commit:
```bash
git add frontend/src/entities/quote/queries.ts frontend/src/shared/lib/roles.ts
git commit -m "$(cat <<'EOF'
feat(composition): add useQuoteComposition entity query + role helper

New TanStack Query hook fetches composition state (items with
supplier alternatives) for the CompositionPicker UI via Supabase
direct LEFT JOIN — simple read, no business logic, per api-first.md.

canEditComposition() role helper returns true for sales,
head_of_sales, head_of_procurement, admin.

Access guard delegates to canAccessQuote() for visibility.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `CompositionPicker` component

**Requirements:** 2.3, 2.4, 2.5
**Dependencies:** Task 8

**Files:**
- Create: `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx`
- Create: `frontend/src/features/quotes/ui/calculation-step/composition-picker.test.tsx` (colocated Vitest)
- Create: `frontend/src/features/quotes/ui/calculation-step/mutations.ts` — `applyComposition` Server Action

**Steps:**
- [ ] Create `mutations.ts` with `applyComposition` Server Action per `design.md` § "applyComposition Server Action" — thin wrapper calling `apiServerClient("/quotes/${quoteId}/composition", {method: POST, body})`, then `revalidatePath(...)`
- [ ] Create `composition-picker.tsx` as a client component:
  - Props: `quoteId: string`, `quoteUpdatedAt: string`
  - Uses `useQuoteComposition(quoteId)` hook
  - Renders a shadcn/ui `<Card>` with title "Выбор поставщиков"
  - Inside: a table with one row per quote_item showing: item name, quantity, one radio per alternative invoice (radio label includes supplier name + price + currency)
  - When only one alternative exists, the radio is disabled and shows "Единственное КП"
  - onChange handler: updates local selection state, calls `applyComposition(quoteId, selection, quoteUpdatedAt)`, handles 409 error by prompting reload
  - Shows empty state "Нет КП для композиции" when no items have invoice_item_prices rows
- [ ] Write `composition-picker.test.tsx` Vitest unit tests (mock `useQuoteComposition`):
  - `renders a row per quote_item`
  - `renders one radio per alternative invoice`
  - `disables radio when only one alternative exists`
  - `calls applyComposition on selection change`
  - `shows empty state when no items have iip rows`
  - `highlights current selection from composition_selected_invoice_id`
  - `falls back to legacy invoice_id when composition pointer is null`
- [ ] Run tests: `cd frontend && npm run test -- composition-picker.test.tsx`
- [ ] Run lint + type check: `cd frontend && npm run lint && npx tsc --noEmit`
- [ ] Commit:
```bash
git add frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx frontend/src/features/quotes/ui/calculation-step/composition-picker.test.tsx frontend/src/features/quotes/ui/calculation-step/mutations.ts
git commit -m "$(cat <<'EOF'
feat(composition): CompositionPicker component

Client component rendering per-item supplier selection table.
Uses useQuoteComposition hook + applyComposition Server Action
(thin wrapper over POST /api/quotes/{id}/composition).

- One row per quote_item with radios for each alternative invoice
- Optimistic UI: radio click triggers immediate POST
- 409 handling: stale quote triggers reload prompt
- Disabled radio + "Единственное КП" label when only one supplier
- Empty state when no composition data exists yet

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Integrate `CompositionPicker` into `CalculationStep` + browser test

**Requirements:** 2.8
**Dependencies:** Task 9

**Files:**
- Modify: `frontend/src/features/quotes/ui/calculation-step/calculation-step.tsx` (single import + single JSX insertion)

**Steps:**
- [ ] Read current `calculation-step.tsx` (~114 lines) to find the JSX structure. The picker goes between `<CalculationForm />` and `<CalculationResults />`, inside the `<div className="p-6 space-y-6">` block below `<CalculationActionBar />`.
- [ ] Import: `import { CompositionPicker } from "./composition-picker";`
- [ ] Insert: `<CompositionPicker quoteId={quote.id} quoteUpdatedAt={quote.updated_at} />` between the Form and Results components
- [ ] Run lint + type check
- [ ] **Browser test on localhost:3000 with prod Supabase:**
  - Start dev server: `cd frontend && npm run dev` (background)
  - Use Playwright MCP to navigate to a quote detail page with multi-supplier composition data (use one of the 5 regression-test quotes from Task 5, or create a test quote with 2 supplier invoices via procurement UI)
  - Take `browser_snapshot()` and verify CompositionPicker renders with a row per quote_item and visible radios
  - Click a different radio, `browser_wait_for()` the optimistic update, take another snapshot to verify selection persisted
  - Verify console has no errors
  - Screenshot to `.claude/test-ui-reports/phase-5b-composition-picker-test-{YYYYMMDD-HHMM}.png`
- [ ] Commit:
```bash
git add frontend/src/features/quotes/ui/calculation-step/calculation-step.tsx
git commit -m "$(cat <<'EOF'
feat(composition): integrate CompositionPicker into CalculationStep

Renders as a new card between CalculationForm and CalculationResults,
above the Calculate button (per Decision #2).

Verified on localhost:3000 with prod Supabase via Playwright:
picker renders all quote_items, radios select alternatives,
optimistic update persists via POST /api/quotes/{id}/composition.
Zero console errors.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Same-supplier / new-supplier bypass logic in invoice creation

**Requirements:** 1.3, 7.1, 7.2, 7.3, 7.4, 7.5
**Dependencies:** Task 3 (schema must be in place; actual bypass detection is schema-independent but we want iip rows to also be inserted from this flow)

**Files:**
- Modify: `main.py` (around lines 18971-19094 — invoice creation POST handler)
- Modify: `frontend/src/features/quotes/ui/procurement-step/...` or wherever the invoice creation form lives — add `bypass_reason` banner
- Create: `tests/test_invoice_creation_bypass.py`

**Steps:**
- [ ] Read `main.py:18971-19094` to understand the current invoice creation flow and identify where `pickup_country` is resolved
- [ ] Before the pre-fill block, add same-supplier detection: `existing = supabase.from_("invoices").select("id").eq("quote_id", quote_id).eq("supplier_id", supplier_id).limit(1).execute()`
- [ ] If `existing.data`: set `bypass_reason = "same_supplier"`, skip ALL pre-fill (pickup_country, pickup_location_id, total_weight_kg, total_volume_m3, customs fields). User-provided values from form are still used if present.
- [ ] Else: set `bypass_reason = "new_supplier"`, keep existing Phase 5a logistics pre-fill (`pickup_country = form or suppliers.country`), skip customs fields only.
- [ ] After creating the invoice, ALSO insert invoice_item_prices rows for each quote_item the invoice covers (call composition_service or inline the INSERT) — this satisfies Requirement 1.2
- [ ] Include `bypass_reason` in the response body: `{success: True, data: {invoice_id: ..., bypass_reason: "same_supplier" | "new_supplier"}}`
- [ ] Find the frontend invoice creation form: `grep -rn "createInvoice\|invoice-create" frontend/src/features/procurement*` — add conditional banner rendering based on `bypass_reason`
- [ ] Banner text when `bypass_reason === "same_supplier"`: "ℹ Уже есть КП от этого поставщика — поля не предзаполнены"
- [ ] Write `tests/test_invoice_creation_bypass.py`:
  - `test_same_supplier_bypass_skips_pickup_country_prefill`
  - `test_same_supplier_bypass_skips_customs_prefill`
  - `test_new_supplier_bypass_prefills_pickup_country_from_suppliers`
  - `test_new_supplier_bypass_skips_customs`
  - `test_invoice_creation_inserts_iip_rows_for_covered_items`
  - `test_bypass_reason_in_response_body`
- [ ] Run tests: `pytest tests/test_invoice_creation_bypass.py -v`
- [ ] **Browser test on localhost:3000**: create invoice A from supplier X (verify pre-fill), create invoice B from supplier X (verify no pre-fill + banner shown), create invoice C from supplier Y (verify pre-fill returns). Screenshot to `.claude/test-ui-reports/phase-5b-bypass-test-{YYYYMMDD-HHMM}.png`
- [ ] Commit:
```bash
git add main.py tests/test_invoice_creation_bypass.py frontend/src/features/procurement-distribution/...
# Note: adjust frontend path to whatever grep finds
git commit -m "$(cat <<'EOF'
feat(composition): bypass logic for same/new supplier invoice creation

When procurement creates a second invoice from the same supplier on
a quote, the creation flow now skips ALL pre-fills (logistics +
customs) — those fields were already filled on the first invoice.

New-supplier invoices keep the Phase 5a pickup_country auto-derive
from suppliers.country, but skip customs pre-fills.

Invoice creation now also inserts invoice_item_prices rows for
every quote_item the new invoice covers (Requirement 1.2).

Response includes bypass_reason: same_supplier | new_supplier | null.
Frontend shows an info banner when same_supplier bypass applies.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Edit-verified-invoice approval request modal

**Requirements:** 6.6
**Dependencies:** Task 7

**Files:**
- Create: `frontend/src/features/quotes/ui/calculation-step/edit-verified-request-modal.tsx`
- Modify: existing invoice edit UI (wherever the "edit invoice" button lives in Next.js — grep needed)
- Create: colocated Vitest test

**Steps:**
- [ ] Find the current invoice edit UI: `grep -rn "editInvoice\|invoice-edit" frontend/src/features/`
- [ ] Create `edit-verified-request-modal.tsx` using shadcn/ui Dialog:
  - Props: `invoice: Invoice`, `proposedChanges: Record<string, {old, new}>`, `onClose: () => void`
  - Shows a table of the proposed changes (one row per field: field name, old value, new value)
  - Reason textarea (required, min 10 chars)
  - Submit button calls new Server Action `requestInvoiceEdit(invoiceId, proposedChanges, reason)` which wraps `POST /api/invoices/{id}/edit-request`
  - On success: shows "Заявка отправлена head_of_procurement" toast, closes modal
  - On error: shows error toast
- [ ] Modify the invoice edit flow: when saving a verified invoice (verified_at IS NOT NULL) and the current user is not head_of_procurement, intercept the save action and open this modal instead of submitting directly
- [ ] Write Vitest tests:
  - `renders proposed changes table`
  - `requires reason with min 10 chars`
  - `calls requestInvoiceEdit Server Action on submit`
  - `shows success toast and closes on success`
- [ ] **Browser test on localhost:3000**: open a verified invoice → try to edit → modal appears → submit with reason → verify approval row created in DB via SSH query
- [ ] Commit:
```bash
git add frontend/src/features/quotes/ui/calculation-step/edit-verified-request-modal.tsx ...
git commit -m "$(cat <<'EOF'
feat(composition): edit-verified-invoice approval request modal

When a procurement user attempts to edit a verified invoice,
this modal intercepts the save and opens an approval request flow.

Shows the proposed changes as a diff table, collects a reason
(min 10 chars), and calls POST /api/invoices/{id}/edit-request.

After submission, head_of_procurement can approve or reject via
the existing approval flow — the diff is applied atomically on
approval.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: E2E verification + KP freeze hook + changelog + deploy

**Requirements:** 4.4 (regression pass), 8.1, 8.2, 8.3, 8.4, 8.5, 9.4
**Dependencies:** Tasks 1-12

**Files:**
- Create: `tests/e2e/phase-5b-composition.spec.ts` (or equivalent — Playwright test location)
- Modify: `services/composition_service.py` — wire `freeze_composition` into the KP send flow if present (otherwise add an admin action UI element — scope call at implementation time per R8 AC5)
- Modify: `changelog/2026-04-10.md` (or next day's file)
- Optional create: an admin "Freeze composition" action somewhere visible to head_of_procurement (only if no KP send flow exists to hook into)

**Steps:**
- [ ] Write `tests/e2e/phase-5b-composition.spec.ts` Playwright test covering the full happy path:
  1. Login as admin
  2. Navigate to a test quote with 2+ supplier invoices
  3. Open calculation step
  4. Verify CompositionPicker renders with multiple alternatives per item
  5. Pick item 1 from supplier A, item 2 from supplier B
  6. Click Calculate
  7. Verify total equals hand-computed sum from the selected prices
  8. Screenshot each step to `.claude/test-ui-reports/phase-5b-e2e-{YYYYMMDD-HHMM}/`
- [ ] Run the regression test suite: `pytest tests/test_calc_regression_phase_5b.py -v` — expect all 5 representative quotes to still compute bit-identically (proves Task 5 held up through all subsequent changes)
- [ ] Determine freeze hook location: `grep -rn "send.*kp\|send_kp\|kp.*send\|отправ.*КП" main.py frontend/src/ | head -20`
  - If a send flow exists: wire `composition_service.freeze_composition(quote_id, user_id, supabase)` into it as a side effect
  - If no send flow exists: add a "Заморозить композицию" button on the quote detail page visible only to `head_of_procurement` and `admin`, calling a new endpoint `POST /api/quotes/{id}/freeze-composition` that calls `composition_service.freeze_composition`. Document the decision in the commit message.
- [ ] Write 2-3 unit tests for the freeze hook integration (extending test_composition_service.py or a new integration test file)
- [ ] Update `changelog/2026-04-10.md` (or next day's file based on actual ship date) with Phase 5b summary: 13 migrations/files/commits, features added, migration numbers, regression-test verification
- [ ] Final verification: all tests green (`pytest && cd frontend && npm run test`), lint clean, type check clean
- [ ] Push to main (triggers GitHub Actions auto-deploy): `git push origin main`
- [ ] After deploy, verify on prod: `ssh beget-kvota "docker logs kvota-onestack --tail 50"` — expect no errors
- [ ] Prod smoke test: navigate to one of the 5 regression quotes on https://app.kvotaflow.ru, open calculation step, verify CompositionPicker renders correctly, Calculate returns the expected total
- [ ] Commit (final):
```bash
git add tests/e2e/phase-5b-composition.spec.ts services/composition_service.py changelog/2026-04-10.md ...
git commit -m "$(cat <<'EOF'
feat(composition): Phase 5b complete — E2E + freeze hook + changelog

Ships Phase 5b Quote Composition Engine end-to-end.

E2E Playwright test covers the full composition happy path from
quote detail through calculation with per-item supplier selection.

Freeze hook wired into [send flow / admin action — decided based
on codebase state per R8 AC5].

Regression test suite (5 representative existing quotes) still
passes — calculation outputs bit-identical to pre-migration
snapshot. Engine files show zero modifications.

Closes Phase 5b.

Part of Phase 5b — Quote Composition Engine.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Coverage check

| Requirement | Task(s) |
|---|---|
| 1.1, 1.2, 1.5 | Task 1, Task 11 |
| 1.3 | Task 11 (preserves legacy pointer) |
| 1.4 | Task 1 (created_by column), Task 11 (sets created_by on insert) |
| 2.1, 2.2 | Task 6 |
| 2.3, 2.4 | Task 8, Task 9 |
| 2.5, 2.6, 2.7 | Task 6, Task 9 |
| 2.8 | Task 10 |
| 3.1, 3.2, 3.3, 3.4 | Task 4 |
| 3.5 | Task 5 |
| 3.6 | Task 4 (single-query assertion) |
| 3.7 | Task 4 (no locked file imports) |
| 4.1, 4.2, 4.3 | Task 5 (verify locked files untouched) |
| 4.4 | Task 5 (regression test) |
| 5.1 | Task 2 |
| 5.2, 5.3, 5.4 | Task 7 |
| 5.5 | Task 3 (backfill verified_at for completed invoices) |
| 6.1, 6.2, 6.3, 6.4, 6.5, 6.7 | Task 7 |
| 6.6 | Task 12 |
| 7.1, 7.2, 7.3, 7.4, 7.5 | Task 11 |
| 8.1, 8.2 | Task 4 (freeze_composition implementation) |
| 8.3, 8.4 | Task 4 (service-layer guard in composition_service) |
| 8.5 | Task 13 (freeze hook or admin action) |
| 9.1, 9.2, 9.3 | Task 3 |
| 9.4 | Task 5 (regression test) + Task 13 (rerun at end) |
| 9.5 | Task 4 (fallback logic in get_composed_items) |
| 10.1, 10.2 | Task 1 (RLS policies) |
| 10.3, 10.4 | Task 6 (API 404 on denial) |
| 10.5 | Task 4 (org_id in all queries) |
| 10.6 | Task 8 (canEditComposition in roles.ts) |

All 10 requirements fully covered across 13 tasks.

## Execution notes

- **Sequential only** — not running in parallel mode. Each task blocks the next.
- **Check-in after Task 1** — user explicitly requested this.
- **Browser tests on localhost:3000** for Tasks 10, 11, 12 — use Playwright MCP with prod Supabase via `frontend/.env.local`.
- **Commit hygiene** — `git add <explicit-paths>` only. Parallel procurement work in the tree must not be swept in.
- **Never modify** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` — verified at Task 5 via explicit `git diff` assertion.
