# Design Document — Phase 5d: Legacy Surface Refactor

**Depends on:** Phase 5c (13 local commits on branch, not pushed) ✅
**Locks:** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` (zero modifications — same as Phase 5c)
**Ship strategy:** all Phase 5c + 5d commits ship as single atomic push after migration 284 applies

---

## 1. Data-Access Contracts (the source of truth going forward)

Phase 5d establishes three canonical paths for reading item-level data. Every surface must use exactly one:

### 1.1 `composition_service.get_composed_items(quote_id, supabase) -> list[dict]`

**When to use:** you need "the final calc-ready shape" — what the engine would calculate with, what the client sees in their КП.

**Returns:** list of item dicts. For split, N dicts per quote_item. For merge, one dict per unique invoice_item (even if covering multiple quote_items). For 1:1, one dict per quote_item.

**Consumers:** calc engine entry points (already done in Phase 5c), workflow auto-transitions, PDF renders, XLS exports that represent "final customer quote".

### 1.2 `composition_service.is_procurement_complete(quote_id, supabase) -> bool` *(new helper)*

**When to use:** workflow gates, status transitions, readiness checks.

**Semantics:** True iff every non-N/A `quote_items` row is covered by at least one `invoice_items` row (in the currently-selected invoice via `composition_selected_invoice_id`) with `purchase_price_original IS NOT NULL`.

**Implementation:**
```python
def is_procurement_complete(quote_id: str, supabase) -> bool:
    qi_rows = supabase.table("quote_items").select(
        "id, is_unavailable, composition_selected_invoice_id"
    ).eq("quote_id", quote_id).execute().data or []

    required_qi = [qi for qi in qi_rows if not qi.get("is_unavailable")]
    if not required_qi:
        return False  # empty quote can't be "complete"

    # For each required quote_item, find coverage in the selected invoice
    qi_ids = [qi["id"] for qi in required_qi]
    coverage_rows = supabase.table("invoice_item_coverage").select(
        "quote_item_id, invoice_items!inner(invoice_id, purchase_price_original)"
    ).in_("quote_item_id", qi_ids).execute().data or []

    # Group by quote_item_id
    priced_qi_ids = set()
    for cov in coverage_rows:
        ii = cov["invoice_items"]
        qi = next(q for q in required_qi if q["id"] == cov["quote_item_id"])
        if ii["invoice_id"] == qi.get("composition_selected_invoice_id") \
                and ii.get("purchase_price_original") is not None:
            priced_qi_ids.add(cov["quote_item_id"])

    return len(priced_qi_ids) == len(required_qi)
```

**Consumers:** `workflow_service.check_all_procurement_complete` (wrap this helper), procurement-step's "can we complete?" button guard (already uses frontend-local logic but could switch).

### 1.3 Direct `invoice_items` query

**When to use:** per-invoice views — "positions of this specific supplier offer", independent of composition selection.

**Examples:** invoice-card items list (Phase 5c already does this), XLS export per invoice, logistics row per invoice.

**Pattern:**
```python
# Python
rows = supabase.table("invoice_items").select("*").eq("invoice_id", invoice_id).order("position").execute().data
```
```typescript
// TypeScript (frontend, Next.js)
const { data } = await supabase
  .from("invoice_items")
  .select("*, coverage:invoice_item_coverage(quote_item_id, ratio)")
  .eq("invoice_id", invoiceId)
  .order("position");
```

---

## 2. Surface-by-Surface Refactor Strategy

Each of the 27+ surfaces is classified by Pattern A (use get_composed_items) / Pattern B (direct invoice_items) / Pattern C (aggregate via coverage) / Pattern D (is_procurement_complete helper) / Pattern E (dormant, leave alone).

### 2.1 Python Services (Group 2)

| # | File:line | Current behavior | Pattern | New behavior |
|---|-----------|-----------------|---------|--------------|
| 2.1.1 | `services/workflow_service.py:2714-2731` `check_all_procurement_complete` | Reads `quote_items.purchase_price_original` | D | Delegate to `composition_service.is_procurement_complete(quote_id, supabase)` |
| 2.1.2 | `services/xls_export_service.py:109-111` | `SELECT * FROM quote_items WHERE invoice_id=X` | B | `SELECT * FROM invoice_items WHERE invoice_id=X`. Extend with coverage JOIN for "Покрывает" column |
| 2.1.3 | `services/customer_service.py:1620-1621` | Aggregates `quote_items.base_price_vat` across customer | C | Aggregate from `invoice_items` via coverage → quote_items → quotes → customer_id filter |
| 2.1.4 | `services/customer_service.py:1699-1700, 1774, 1798` | Same pattern | C | Same pattern |
| 2.1.5 | `services/currency_invoice_service.py:174-176, 221` | Reads item dicts with `purchase_price_original` | A | Verify caller passes `composition_service.get_composed_items()` output; if not, refactor caller |
| 2.1.6 | `services/export_validation_service.py:238, 240, 1309, 1311` | Column mapping for export | B | Rename mapped column source from `quote_items.X` → `invoice_items.X` |
| 2.1.7 | `services/quote_version_service.py:69, 380` | Snapshot writes item shape to `quote_versions.input_variables JSONB` | A | Source items from `get_composed_items()` at snapshot creation time |

### 2.2 Python API (Group 3)

| # | File:line | Classification needed | Pattern |
|---|-----------|----------------------|---------|
| 2.2.1 | `api/procurement.py:240-245` | BLOCKER (kanban JSON for Next.js) | B — read `invoice_items` for the invoice filter |
| 2.2.2 | `main.py:19438-19442` invoice completion validation | Likely BLOCKER (called from completeProcurement mutation) | D — use `is_procurement_complete` |
| 2.2.3 | `main.py:19828-19844` bulk update writing legacy columns | Verify: FastHTML-only? If yes → E. If called from Next.js → must change to write invoice_items | E or B |
| 2.2.4 | `main.py:19292, 19359, 19495` UPDATE `quote_items WHERE invoice_id` | Likely FastHTML-only → E | E |
| 2.2.5 | `main.py:20041-20042, 20607-20608, 20474, 25286-25288, 30475-30477, 43302-43303, 25209-25210, 24314-24315` (8 read locations) | Per-site classification needed | Mix of A/B/E depending on caller context |
| 2.2.6 | `main.py:22131-22144` customs workspace | Likely BLOCKER (Next.js /api/customs/*) | A |
| 2.2.7 | `main.py:17594-18800` `/procurement/{quote_id}` FastHTML page + its POST handlers (19292-19900 subset) | DORMANT — FastHTML HTML route | E |
| 2.2.8 | `main.py:13044, 13174, 13381, 14076, 14799, 17814, 17845, 20095, 20105, 20932-20935, 22240, 22293, 25234, 25314, 30482, 43312` (16 ambiguous reads) | Per-site classification — "items came from composition_service" = FALSE POSITIVE, "items came from raw quote_items query" = BLOCKER | TBD |

**Group 3 precondition:** per-site classification pass before any refactor. First TDD task in Group 3 is an agent that walks these 16 ambiguous sites + produces a classified list.

### 2.3 Frontend Entity Queries (Group 4)

| # | File:line | Current | Pattern | New |
|---|-----------|---------|---------|-----|
| 2.3.1 | `frontend/src/entities/customer/queries.ts:405, 418` | `SELECT purchase_price_original, purchase_currency FROM quote_items` | C | JOIN invoice_item_coverage → invoice_items filtered by composition_selected_invoice_id |
| 2.3.2 | `frontend/src/entities/supplier/queries.ts:262, 276` | Same | C | Same |
| 2.3.3 | `frontend/src/entities/position/queries.ts:145-209` | Same (with additional fields) | C | Same |
| 2.3.4 | `frontend/src/app/(app)/export/specification/[id]/route.tsx:60` | `SELECT brand, product_code, product_name, unit, quantity, base_price_vat FROM quote_items` | B | Switch source to `invoice_items` for the spec's associated invoice |

**Pattern C implementation example:**
```typescript
// entities/customer/queries.ts — new pattern
const { data } = await supabase
  .from("quotes")
  .select(`
    id,
    quote_items!inner(
      id,
      composition_selected_invoice_id,
      coverage:invoice_item_coverage!quote_item_id(
        invoice_items!inner(purchase_price_original, purchase_currency)
      )
    )
  `)
  .eq("customer_id", customerId);
// Flatten coverage → pick the row matching composition_selected_invoice_id
```

### 2.4 Frontend Components (Group 5, split into 3-4 parallel agents)

Grouping by visual area to allow parallel agents without file conflicts:

**Agent A — Sales + Calculation:**
- `features/quotes/ui/sales-step/sales-items-table.tsx`
- `features/quotes/ui/calculation-step/calculation-results.tsx`
- `features/quotes/ui/control-step/invoice-comparison-panel.tsx`

**Agent B — PDF exports:**
- `features/quotes/ui/pdf/kp-document.tsx`
- `features/quotes/ui/pdf/spec-document.tsx`

**Agent C — Procurement + Logistics:**
- `features/quotes/ui/procurement-step/procurement-handsontable.tsx` (COLUMN_KEYS rebinding)
- `features/quotes/ui/procurement-step/procurement-step.tsx` (null-check logic)
- `features/quotes/ui/procurement-step/procurement-action-bar.tsx` (null-check logic)
- `features/quotes/ui/logistics-step/logistics-invoice-row.tsx`
- `features/quotes/ui/logistics-step/products-subtable.tsx`

Pattern for each: trace the data source. If it comes via entity query (refactored in Group 4), no component change needed — just verify. If the component reads raw `quote_items` directly via its own Supabase call, refactor to invoice_items (Pattern B) or composed (Pattern A) based on semantics.

### 2.5 Dormant (Pattern E, no action)

- `main.py:17594-18800` `/procurement/{quote_id}` FastHTML page (entire workspace)
- `main.py:19292, 19359, 19420-19900` FastHTML POST handlers (subset — exact lines determined in Group 3 classification)

---

## 3. Migration 284 (Group 6)

### 3.1 Pre-apply checklist

1. All Groups 2-5 tasks merged locally. Phase 5d commits on branch.
2. Run `tests/test_migration_284_no_legacy_refs.py` — expect PASS.
3. Run full Python + frontend test suite — expect baseline PASS (no regressions from Phase 5c).

### 3.2 Apply sequence

Coordinator executes manually (not in agent scope):

```bash
ssh beget-kvota "docker exec -i supabase-db psql -U postgres -d postgres" < migrations/284_drop_legacy_schema.sql
# verify
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c 'SELECT column_name FROM information_schema.columns WHERE table_schema=\"kvota\" AND table_name=\"quote_items\"'"
# expect: id, quote_id, idn_sku, product_name, brand, quantity,
#         composition_selected_invoice_id, is_unavailable, import_banned,
#         vat_rate, supplier_sku, supplier_sku_note, manufacturer_product_name,
#         name_en, position, created_at, updated_at
```

### 3.3 Post-apply steps

1. `cd frontend && npm run db:types` — regenerate `database.types.ts`
2. Remove `as any` casts introduced in Phase 5c (find via grep `as any` in recent commits)
3. Commit type regen + cast removal
4. Run full test suite again

### 3.4 Rollback plan

If migration 284 fails or smoke test reveals issue:
1. Restore DB from snapshot taken pre-284
2. `git revert` the deploy commit (or, if on branch pre-push, just reset the branch pointer)
3. Investigate + re-plan

---

## 4. Ship Sequence (Group 7)

```
Phase 5c local commits: 13 (already exist on branch)
Phase 5d local commits:
  Group 2 — Python services:        6-7 commits
  Group 3 — Python API:             3-4 commits (including classification audit task)
  Group 4 — Frontend entities:      1-2 commits (batched)
  Group 5 — Frontend components:    3 commits (3 parallel agents)
  Group 6 — Migration 284 + types:  2 commits (apply + regen)
  Group 7 — QA + deploy:            1 commit (changelog)

Total: ~30+ commits

git push origin feat/soft-delete-services-audit
# open PR to main
# /code-review runs (5 agents)
# CI passes
# merge
# GitHub Actions deploys code to beget-kvota
# coordinator applies 281→282→283→284 on prod via scripts/apply-migrations.sh
# post-deploy smoke: test quote calc correctly + UI works
```

Phase 5d-specific browser E2E happens before git push (on staging-like localhost:3000 + prod Supabase combo per `reference_localhost_browser_test.md`).

---

## 5. Open Questions (resolve during Group 3 classification)

1. **Main.py bulk-update handler (19828-19844):** Is this called by Next.js procurement-handsontable save or is it purely FastHTML? Grep for `/api/procurement/.*/items/bulk` or similar from `frontend/src/`.
2. **Main.py invoice completion validation (19438-19442):** Called by `completeProcurement` mutation in `entities/quote/mutations.ts`? Trace the API path.
3. **Main.py customs workspace (22131-22144):** Called by Next.js customs tab? Check `frontend/src/features/quotes/ui/customs-step/`.
4. **Quote_version_service snapshot:** Does it currently snapshot from composition_service output, or raw quote_items? Read the function signature.

Each of these answers determines Pattern E vs Pattern A/B for the specific lines.

---

## 6. Success Criteria

1. `test_migration_284_no_legacy_refs.py` passes with zero production-code references to 16 legacy columns + `invoice_item_prices` table (excluding explicitly-exempted FastHTML region).
2. Full Python test suite passes (no worse than pre-Phase-5c baseline — pre-existing failures are acceptable).
3. Full frontend test suite passes (317+ Phase 5c + new Phase 5d tests).
4. Extended bit-identity regression (10+ quotes, Mode A + Mode B) passes.
5. Workflow transition regression passes: `is_procurement_complete` equivalent to `check_all_procurement_complete` on all 10 sample quotes.
6. Browser E2E flow end-to-end on staging passes.
7. Migration 284 applies cleanly on prod after deploy. Post-deploy smoke on 1-2 test quotes confirms calc + UI work.
8. `as any` cast count in frontend repo decreases to pre-Phase-5c levels (or lower).
