# Research Log — Phase 5b Quote Composition Engine

## Summary

**Discovery type:** Extension (integration-focused). Greenfield composition feature grafted onto an existing procurement workflow that already has supplier invoices, a locked calculation engine, and a reusable approval framework.

**Primary upstream research:** `.planning/research/SUMMARY.md` (codebase map gathered via Explore agent immediately before `/code` was invoked). This log captures only design-phase findings that go beyond that document.

## Codebase discovery (delta from SUMMARY.md)

### Calculation pipeline entry points

`build_calculation_inputs()` at `main.py:12995-13159` is called from three sites, each reading `quote_items` from the DB before passing them in:

| Site | Route | Purpose | Current read pattern |
|---|---|---|---|
| `main.py:13303` → call at `main.py:13400` | `POST /quotes/{id}/preview` | HTMX live preview | `supabase.from_("quote_items").select(...).eq("quote_id", ...)` |
| `main.py:14188` | `POST /quotes/{id}/calculate` | Form submit, full calculation | Same pattern |
| `main.py:14846` | Third entry point (verify during Task 5 implementation) | Needs grep confirmation | Same pattern |

**Design implication:** Replace each of these reads with `composition_service.get_composed_items(quote_id, supabase)` — the adapter surface is ~3 small diffs, not a refactor of `build_calculation_inputs()` itself. The locked function stays byte-identical.

### Existing approval infrastructure

`services/approval_service.py` exposes `request_approval()` which creates rows in `kvota.approvals`. Used today for "quote → top manager" approval flow (migrations 005, 035, 137, 20260119). The approval row shape supports a free-form `payload` JSONB column — this is where the edit-diff goes for Requirement 6.

**No new approval machinery needed.** The composition edit-verified flow is a thin wrapper: build a JSON diff, call `request_approval()`, store the diff in `payload`, wait for head_of_procurement to approve/reject, then apply or discard.

### Access control integration

`.kiro/steering/access-control.md` defines 8 visibility tiers. For composition:

- **CompositionPicker visible to:** `sales` (own quotes), `head_of_sales` (group quotes), `head_of_procurement` (all quotes), `admin`
- **Composition API read (GET):** Mirrors quote visibility — a user who can read a quote can read its composition
- **Composition API write (POST):** Same tiers as CompositionPicker visibility
- **Invoice-edit approval:** Only `head_of_procurement` and `admin` can approve/reject
- **Pattern:** `shared/lib/roles.ts` for role predicates, `entities/quote/queries.ts` for `canAccessQuote()` guard, 404-on-denial

### Two invoices tables — do not confuse

Per `.kiro/steering/database.md`:
- `kvota.invoices` = procurement workflow grouping (the one Phase 5b touches). Calc engine reads from this one.
- `kvota.supplier_invoices` = finance payment tracking. Unrelated to Phase 5b.

Migration 107 created `kvota.supplier_invoice_items` — finance, NOT procurement. Do not confuse with the new `kvota.invoice_item_prices`.

## Architecture pattern evaluation

### Pattern 1: Overlay prices via adapter (CHOSEN)

The `composition_service.get_composed_items()` function fetches quote_items and overlays price fields from `invoice_item_prices` via a JOIN on `composition_selected_invoice_id`. Returns dicts in the exact shape the current `quote_items` read returns.

- **Pro:** Zero changes to `build_calculation_inputs()` or the engine. Smallest possible surface.
- **Pro:** Backward compatible by construction — quotes without composition fall through to legacy `quote_items` values.
- **Pro:** Single SQL query, no N+1.
- **Con:** Requires the caller to use the service instead of direct DB reads. Three call sites to update — manageable.

### Pattern 2: Modify `build_calculation_inputs()` internally (REJECTED)

Have the function itself query `invoice_item_prices` and resolve composition.

- **Pro:** Only one place changes.
- **Con:** Function currently takes `items: List[Dict]` as a pure transform. Pulling DB access into it changes its signature and makes unit testing harder.
- **Con:** Doesn't save any lines — the 3 call sites still read `quote_items` as the fallback, and we'd still need a service to contain the JOIN logic.
- **Verdict:** No meaningful benefit over Pattern 1.

### Pattern 3: Denormalize prices back into `quote_items` on composition (REJECTED)

When the user picks a supplier, copy the selected price into `quote_items.purchase_price_original`. Then `build_calculation_inputs()` never needs to change.

- **Pro:** Absolute minimal code change.
- **Con:** Loses the provenance — once copied, you can't tell which invoice the price came from without a separate pointer.
- **Con:** History/freeze semantics become awkward — `quote_items` isn't versioned; `invoice_item_prices` can be.
- **Con:** Reversing a composition pick requires the caller to remember the old value.
- **Verdict:** Dirty data model; rejects too many of the feature's future extensibility points (versioning, freeze, multi-version history).

## Technology alignment

| Concern | Decision | Rationale |
|---|---|---|
| Python module layout | `services/composition_service.py` alongside existing `services/approval_service.py`, `services/logistics_service.py`, etc. | Matches existing service pattern per `tech.md` |
| API endpoint style | New module `api/composition.py` per `api-first.md` pattern (like `api/deals.py`) | Keeps `main.py` clean of new business logic |
| API docstrings | Structured format per `api-first.md` — `Path/Params/Returns/Side Effects/Roles` | Feeds future OpenAPI + MCP generation |
| Server Actions | Thin wrappers in `frontend/src/features/quotes/ui/calculation-step/mutations.ts` that call `apiServerClient("/composition/...", ...)` | Matches `api-first.md` rule |
| Entity query | `useQuoteComposition(quoteId)` in `frontend/src/entities/quote/queries.ts` — uses Supabase direct for read (no business logic) | Per `api-first.md`: reads without business logic can go direct |
| Component placement | `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx` | Same directory as `calculation-step.tsx` — co-located with its consumer per FSD |
| Transaction isolation | PostgreSQL default (READ COMMITTED) for composition POST, with `updated_at` optimistic concurrency check | Sufficient for this workload; no need for SERIALIZABLE |
| Migration tool | `scripts/apply-migrations.sh` (SSH to VPS) | Standard project pattern |

## Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Third calc entry point at `main.py:14846` may be a false positive | Low | Task 5 starts with a grep for `build_calculation_inputs(` to enumerate all actual call sites; update the list if wrong |
| KP-send flow may not exist, making R8 "freeze on send" unimplementable as-stated | Medium | R8 AC5 explicitly allows scope adjustment at implementation time — if no send flow exists, freeze becomes an admin action button |
| Backfill race with in-flight procurement work during migration 265 | Medium | Migration 265 is idempotent (`ON CONFLICT DO NOTHING`); run during low-traffic window; inserts don't lock existing rows |
| `quote_items.composition_selected_invoice_id` gets orphaned if an invoice is deleted | Medium | `ON DELETE SET NULL` FK rule; composition_service treats NULL pointer as "fall back to legacy `quote_items.invoice_id`" |
| Currency mismatch between competing supplier offers | Low | Already handled — per-item currency exists today at `main.py:13140-13150`; no new logic needed |
| Row-level freeze check enforcement | Medium | Use service-layer guard (Python) rather than DB trigger — easier to test, easier to bypass in repair scripts, consistent with project's "business logic in services, not DB" pattern |
| Concurrent composition edits from two tabs | Low | Optimistic concurrency check on `quotes.updated_at` at POST time; reject with 409 if stale |
| RLS policy drift (invoice vs iip) | Medium | Write iip RLS as a thin reference to the invoices RLS predicate, not a copy — avoid drift over time |

## Deferred questions (not blocking implementation)

- **KP version UI:** Requirement 8 introduces versioning on `invoice_item_prices` rows but doesn't define a "view version history" UI. Deferred — can be added later without data model changes.
- **Partial composition (some items picked, others legacy):** Supported by the data model (composition pointer is per-item), but UX is unclear. MVP assumes users either pick-all or pick-none; mixed state works but isn't highlighted in the UI. Can iterate based on feedback.
- **Bulk "select all from supplier X" action:** Explicitly out of scope per the scope doc. Can add in a later phase.

## Design-phase decisions auto-resolved (no STOP)

| Question | Decision | Rationale |
|---|---|---|
| Transaction isolation level for POST /composition | READ COMMITTED + optimistic concurrency | Matches project default; stronger isolation would add contention |
| FK rule for `composition_selected_invoice_id` | `ON DELETE SET NULL` | Allows graceful fallback to legacy pointer; doesn't cascade-delete items |
| FK rule for `invoice_item_prices.invoice_id` | `ON DELETE CASCADE` | When the invoice is deleted, its price rows have no meaning |
| FK rule for `invoice_item_prices.quote_item_id` | `ON DELETE CASCADE` | Same |
| Row freeze enforcement | Service-layer guard in Python, not DB trigger | Matches project pattern; easier to bypass in repair scripts |
| JSON diff format for edit-request payload | `{ "fields": {old: ..., new: ...}, "reason": "..." }` per field | Machine-readable for approval UI, human-readable for audit log |
| Composition picker update cadence | On radio click → immediate POST (optimistic UI) | Avoids "save button" friction; aligns with typical shadcn/ui forms |
| What to show when only one supplier covers an item | Disable the radio, show "only supplier" label | Clarifies that no choice exists, doesn't hide the picker structure |
