# Phase 5b Research Summary

> Pre-gathered via Explore agent immediately before /code was invoked. Not re-running agents — findings are fresh.

## Codebase state (the "what exists now")

**Calculation pipeline (LOCKED):**
- `calculation_engine.py` / `calculation_models.py` / `calculation_mapper.py` — never modified.
- `main.py:12995-13159` = `build_calculation_inputs(items, variables)`. Pure function. Takes item dicts, returns `List[QuoteCalculationInput]`. **Not modified** — adapter hook is upstream.
- Items are read from `quote_items` at `main.py:13303-13306` then passed to the function. Three call sites feed it:
  - `main.py:13400` — POST `/quotes/{id}/preview` (HTMX live preview)
  - `main.py:14188` — POST `/quotes/{id}/calculate` (form submit)
  - `main.py:14846` — third entry point (needs verification during Task 5)
- **Insight:** Replacing the 3 item-reads with `composition_service.get_composed_items(quote_id)` is a smaller surface than touching the function itself.

**Data model:**
- `kvota.quote_items.invoice_id` = current 1:1 supplier assignment. Stays as legacy pointer (Decision #1).
- `kvota.quote_items.purchase_price_original` = primary cost field (see `.kiro/steering/database.md` confusable columns — 15+ amount/total variants).
- `kvota.invoices` = supplier KPs (recently renamed "КП поставщику" in UI). Status lifecycle: `pending_procurement` → `completed`. No existing "verified" state.
- HS codes live on `quote_items.customs_code` (Decision #3 — customs per-item).
- **No existing `invoice_items` / `invoice_positions` junction.** `supplier_invoice_items` (migration 107) exists but is unrelated finance — must not confuse.
- Migration tracking: `kvota.migrations(id, filename UNIQUE, applied_at, checksum)`.

**Invoice creation:** POST `/api/procurement/{quote_id}/invoices/create` at `main.py:18971-19094`. `pickup_country` now required (Phase 5a tightening). Role guard at `main.py:19110` checks `["procurement", "admin", "head_of_procurement"]`.

**Approval infrastructure (reusable):**
- `services/approval_service.py` with `request_approval()` function.
- `kvota.approvals` table (migrations 005, 035, 137, 20260119).
- `head_of_procurement` role is live (127+ references in main.py).
- Pattern: request → pending → review → approve/reject → state transition.
- **Decision #5 reuses this** for edit-verified-invoice flow — no new approval machinery.

**Frontend (Next.js 15 App Router):**
- Calculation step: `frontend/src/features/quotes/ui/calculation-step/calculation-step.tsx` (114 lines).
- Structure: `CalculationActionBar` (sticky, with Calculate button at `calculation-action-bar.tsx:90-102`) → grid of `CalculationForm` + `CalculationResults`.
- Composition picker insertion point (Decision #2): new card between `CalculationForm` and `CalculationResults`, NOT inside the sticky action bar.
- Entity queries: `frontend/src/entities/quote/queries.ts` (where `useQuoteComposition` will live).
- All existing procurement invoice UI is FastHTML (main.py templates) — composition will be **first Next.js-native step** in procurement.

## Architecture shape

**Data flow after Phase 5b:**
```
supplier KP submitted → INSERT invoice_item_prices (one row per item, unfrozen)
                     → UPDATE quote_items.invoice_id (legacy pointer, unchanged)

sales opens calc step → SELECT composition + alternatives (composition API)
                     → CompositionPicker renders radio per item

sales picks combo   → POST /api/quotes/{id}/composition
                     → UPDATE quote_items.composition_selected_invoice_id

Calculate button    → main.py reads items via composition_service.get_composed_items(quote_id)
                     → join quote_items + invoice_item_prices on (composition_selected_invoice_id)
                     → overlay price/currency/vat fields from iip onto quote_items shape
                     → feed to build_calculation_inputs() unchanged
                     → engine sees one chosen price per item, same as today
```

**Adapter principle:** `composition_service.get_composed_items()` produces the exact same Dict shape the current `quote_items` read produces. Engine contract unchanged.

## Risk map (from brief + codebase)

| Risk | Mitigation |
|---|---|
| Backfill race: existing quotes mid-procurement when migration 265 runs | Backfill is idempotent; `invoice_item_prices` insert uses `ON CONFLICT DO NOTHING` on `(invoice_id, quote_item_id, version=1)` |
| Concurrent composition edits (two users picking different suppliers at once) | Optimistic concurrency via `quote_items.updated_at` check on POST composition |
| Invoice deleted while composition references it | FK `ON DELETE CASCADE` on `invoice_item_prices.invoice_id`; service layer detects orphaned composition_selected and clears pointer + surfaces warning |
| Currency mismatch between supplier offers (USD vs EUR for same item) | Per-row `purchase_currency` on `invoice_item_prices`; calculation layer already handles per-item currency (see `main.py:13140-13150`) — no new logic needed |
| "Verified" semantics — does `completed` status == verified? | **Open decision.** Proposed: add explicit `verified_at`/`verified_by` columns rather than overloading status. Procurement clicks "Verify" → locks invoice from direct edits, requires approval to change |
| Migration 264 scope ambiguity | Flagged as the only OPEN DECISION requiring user confirmation before Task 1 |
| N+1 reads on composition page (one query per item for alternatives) | Single JOIN in composition API returns all items with their alternatives nested |

## Domain notes

- Multi-supplier composition is a standard procurement pattern (SAP Ariba, Coupa, Jaggaer). Key UX principle: **never hide the alternatives** — always show rejected supplier offers alongside the chosen one so sales can re-pick.
- Versioning on offer rows (not full-history tables) is the lightweight pattern: `version INT + frozen_at TIMESTAMPTZ`. Frozen rows become immutable; edits create a new version row.
- KP freeze-on-send (Decision #4) is deferred to a separate follow-up task — the send flow itself may need discovery work (Explore didn't map it).

## Non-goals for Phase 5b

- Automatic supplier selection (AI/scoring) — sales picks manually.
- Multi-currency conversion inside the picker — display per-offer in native currency, conversion happens at calculation.
- Bulk composition actions — pick per-item, no "select all from supplier X" shortcut (can add later).
- KP send flow changes beyond freeze (actual send email / file generation stays as-is).
