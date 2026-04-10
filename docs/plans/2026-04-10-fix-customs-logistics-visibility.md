# Fix — customs/logistics visibility on /quotes (root-cause)

**Date:** 2026-04-10
**Bugs:** FB-260410-110450-4b85 (customs/Oleg), FB-260410-123751-4b94 (logistics/Aleyna)
**ClickUp:** 86agtxp84
**Related commit:** `9b7fb20` (2026-04-08) — introduced ASSIGNED_ITEMS filter; preserve procurement/procurement_senior tiers
**Scope:** single commit, full root-cause, no hotfix

---

## Problem

After commit `9b7fb20` added `ASSIGNED_ITEMS` filtering, all users with roles `customs` or `logistics` see an empty `/quotes` list. Two bug reports confirm the symptom across both roles.

## Verified root causes (investigation complete)

1. **Customs assignment column `quotes.assigned_customs_user` is never written** anywhere in the codebase. Filter requires it → empty result for every customs user. Global count: **0 records**.

2. **Logistics assignment exists via `services/workflow_service.py::assign_logistics_to_invoices()`** (line 2288, called from `complete_procurement()` at line 2900). Logic routes by `invoice.pickup_country → delivery_city` via RPC `get_logistics_manager_for_locations()`. Silently skips invoices with empty pickup_country (line 2360-2362).

3. **All 8 active quotes in `pending_logistics_and_customs` have NULL `invoice.pickup_country`**. They bypassed the FastHTML validation (`main.py:19327-19329`). Global count of active logistics assignments: **0**.

## Goal

One commit that fixes all three layers:
- **Part 1** — Customs visibility: show all customs-stage quotes to all customs users (no assignment mechanism exists yet; will be added later)
- **Part 2** — Logistics data pipeline: ensure `invoices.pickup_country` is populated in the Next.js procurement flow so `assign_logistics_to_invoices` works end-to-end
- **Part 3** — Backfill: for the 8 stuck quotes, populate pickup_country on invoices + trigger `assign_logistics_to_invoices`, via idempotent migration

---

## Part 1 — Customs visibility (frontend-only)

**Decision rationale:** User said: *"По customs - можно сделать видимыми для всех сотрудников отдела сейчас. потом разберемся, их там всего двое или трое."* No assignment mechanism exists — treat customs as an all-stage-visible tier until such a mechanism is added in a follow-up.

### Changes

#### `frontend/src/shared/lib/roles.ts`
- Add new helper: `isCustomsOnly(roles: string[]): boolean` — returns `true` iff the user has `customs` role and none of the full-visibility roles (`admin`, `top_manager`).
- Keep existing `isAssignedItemsOnly` for logistics/procurement.

#### `frontend/src/shared/lib/access.ts`
- Modify `getAssignedQuoteIds()`: remove the `customs` branch (lines 120-132). Customs no longer goes through ASSIGNED_ITEMS. Only logistics + procurement remain.
- No other changes in this file.

#### `frontend/src/entities/quote/queries.ts`

**`fetchQuotesList()`** — add a new branch for customs BEFORE the `isAssignedItemsOnly` check:
```ts
if (isCustomsOnly(user.roles)) {
  // CUSTOMS tier: see all quotes in customs workflow stages
  query = query.in("workflow_status", ["pending_customs", "pending_logistics_and_customs"]);
} else if (isAssignedItemsOnly(user.roles)) {
  // unchanged — logistics + procurement via assignment
  ...
}
```

**`canAccessQuote()`** — mirror the same logic:
```ts
if (isCustomsOnly(user.roles)) {
  const { data } = await supabase
    .from("quotes")
    .select("workflow_status")
    .eq("id", quoteId)
    .eq("organization_id", user.orgId)
    .maybeSingle();
  return data?.workflow_status === "pending_customs" 
      || data?.workflow_status === "pending_logistics_and_customs";
}
```

**`fetchFilterOptions()`** (around line 514) — apply the same workflow_status filter for customs.

#### `frontend/src/shared/lib/__tests__/roles.test.ts`
- Add tests for `isCustomsOnly`:
  - Returns `true` for `["customs"]`
  - Returns `false` for `["customs", "admin"]`
  - Returns `false` for `["logistics"]`
  - Returns `false` for `[]`

#### Access tests (extend existing `__tests__/` in `entities/quote/` or create if needed)
- Mock test: customs user → `fetchQuotesList` query has `.in("workflow_status", ["pending_customs", "pending_logistics_and_customs"])` applied
- Mock test: logistics user → still uses ASSIGNED_ITEMS path (unchanged behavior)
- Mock test: procurement user → still uses ASSIGNED_ITEMS path (unchanged behavior)

### Acceptance criteria (Part 1)

- [ ] Customs user logs in → `/quotes` shows quotes in `pending_customs` + `pending_logistics_and_customs` stages for their org
- [ ] Customs user cannot access (via direct URL) a quote in `draft` / `pending_sales_review` / `approved` stages → `notFound()`
- [ ] Logistics user behavior unchanged (still uses ASSIGNED_ITEMS)
- [ ] Sales / admin / procurement users unchanged
- [ ] All existing tests in `roles.test.ts` still pass

---

## Part 2 — Fix Next.js procurement pipeline for `pickup_country`

**STATUS: pending Explore agent results** — exact files and fix approach to be filled in when `/tmp/.../tasks/a81d0264b6841e531.output` reports.

### Expected shape of the fix (to be confirmed by exploration)

1. **UI gap fix** — wherever the Next.js procurement step creates/edits invoices, ensure `pickup_country` is captured (user input, supplier-derived, or HERE Geocode autocomplete).
2. **API validation** — the Python endpoint `/api/quotes/{id}/submit-procurement` (main.py:10818+) must validate that all invoices for the quote have `pickup_country != NULL` before calling `complete_procurement()`. Return 422 with a clear field-level error if missing.
3. **Consistency** — both the FastHTML path and Next.js path must share the same validation. Best: extract validation to a helper in `services/` and call it from both paths.

### Acceptance criteria (Part 2)

- [ ] Submitting procurement through Next.js UI with an invoice missing `pickup_country` → clear validation error, no state change
- [ ] Submitting procurement with all invoices having `pickup_country` → success, `complete_procurement` runs, `assign_logistics_to_invoices` is triggered
- [ ] FastHTML path behavior unchanged
- [ ] New integration test: POST `/api/quotes/{id}/submit-procurement` without pickup_country → 422 error

---

## Part 3 — Backfill the 8 stuck quotes

**Approach:** write migration `260_backfill_logistics_assignment.sql` that is idempotent and safe to re-run.

### Migration strategy

Migrations in this repo are SQL files applied via `scripts/apply-migrations.sh`. But triggering `assign_logistics_to_invoices` is Python logic — can't do it from SQL alone. Two options:

**Option A — Pure SQL migration + Python follow-up script:**
1. SQL: backfill `invoices.pickup_country` from supplier country or other deterministic source
2. Python script (`scripts/backfill_logistics_assignment.py`): for each affected quote, call `assign_logistics_to_invoices(quote_id)`. Run manually once, output results.

**Option B — Python-only backfill script:**
- Skip migration, use a one-off Python script that does both UPDATE and calls `assign_logistics_to_invoices`
- Runs on VPS via `ssh beget-kvota 'docker exec kvota-onestack python scripts/backfill_logistics_assignment.py'`

**Decision:** Option A. Reasons:
- Migration number is trackable in migration history
- SQL backfill is auditable + idempotent
- The logistics assignment call can be re-run anytime (it's idempotent — overwrites the existing assignment)

### Migration 260: `260_backfill_logistics_assignment.sql`

```sql
-- Backfill pickup_country on invoices for quotes stuck in pending_logistics_and_customs
-- Source: linked supplier country via quote_items (majority vote per invoice)
-- Idempotent: only updates rows where pickup_country IS NULL

UPDATE kvota.invoices i
SET pickup_country = sub.country
FROM (
  SELECT DISTINCT ON (i2.id)
    i2.id AS invoice_id,
    s.country
  FROM kvota.invoices i2
  JOIN kvota.quotes q ON q.id = i2.quote_id
  JOIN kvota.quote_items qi ON qi.quote_id = q.id
  LEFT JOIN kvota.suppliers s ON s.id = qi.supplier_id
  WHERE q.workflow_status = 'pending_logistics_and_customs'
    AND q.deleted_at IS NULL
    AND i2.pickup_country IS NULL
    AND s.country IS NOT NULL
  ORDER BY i2.id, qi.created_at ASC
) sub
WHERE i.id = sub.invoice_id
  AND i.pickup_country IS NULL;

-- Verify outcome
DO $$
DECLARE
  remaining INT;
BEGIN
  SELECT COUNT(*) INTO remaining
  FROM kvota.invoices i
  JOIN kvota.quotes q ON q.id = i.quote_id
  WHERE q.workflow_status = 'pending_logistics_and_customs'
    AND q.deleted_at IS NULL
    AND i.pickup_country IS NULL;
  RAISE NOTICE 'Invoices still missing pickup_country: %', remaining;
END $$;
```

**Fallback:** if a quote's items have no supplier_id or the supplier has no country — log the quote_id via RAISE NOTICE. Those will need manual investigation outside this migration.

### Python script: `scripts/backfill_logistics_assignment.py`

```python
#!/usr/bin/env python3
"""One-off: re-run assign_logistics_to_invoices for quotes stuck after migration 260."""
from services.database import get_supabase
from services.workflow_service import assign_logistics_to_invoices

def main():
    supabase = get_supabase()
    stuck = supabase.table("quotes") \
        .select("id, idn_quote") \
        .eq("workflow_status", "pending_logistics_and_customs") \
        .is_("deleted_at", None) \
        .is_("assigned_logistics_user", None) \
        .execute()
    
    print(f"Found {len(stuck.data or [])} quotes needing logistics assignment")
    for q in (stuck.data or []):
        result = assign_logistics_to_invoices(q["id"])
        status = "OK" if result.get("success") else "FAIL"
        user = result.get("quote_level_user_id") or "unmatched"
        print(f"  {q['idn_quote']}: {status} → {user}")

if __name__ == "__main__":
    main()
```

### Acceptance criteria (Part 3)

- [ ] Migration 260 runs cleanly on production DB (via `scripts/apply-migrations.sh 260`)
- [ ] After migration: the 8 quotes have non-NULL `invoices.pickup_country`
- [ ] After running the Python script: `quotes.assigned_logistics_user` is populated for 8 of 8 quotes (or: for the subset where supplier countries match logistics routes — log the mismatches)
- [ ] Test: at least 1 logistics user (e.g., Aleyna or another logistics manager) sees the correct subset on `/quotes`

---

## Test strategy

### Unit tests (Phase 3)

- `frontend/src/shared/lib/__tests__/roles.test.ts` — new `isCustomsOnly` tests
- Quote-query access tests: customs → workflow-stage filter, logistics → assignment filter, procurement → item-level filter, sales → unchanged, admin → unchanged

### Integration test (Part 2 — Python)

- `tests/test_submit_procurement_validation.py` — new: mock supabase client, assert that submitting a quote with missing pickup_country returns 422

### Browser test on localhost:3000 (Phase 5e)

1. Start Next.js dev server: `cd frontend && npm run dev` (port 3000, proxies Supabase via `.env.local`)
2. Login as customs user — use existing account if possible (e.g., Oleg `oleg.k@masterbearing.ru`) OR create a test customs user
3. Navigate to `/quotes` — assert list is NOT empty (shows customs-stage quotes for the org)
4. Login as logistics user (Aleyna) — navigate to `/quotes`, assert list matches their assignments (after backfill runs) OR shows at least some quotes
5. Login as sales user — regression check: same list as before
6. Login as admin — regression check: all quotes visible
7. Capture screenshot for each role via Playwright MCP

### Manual backfill verification

Before committing, I run the backfill migration + script against production DB (with user approval):
```bash
# Apply migration
./scripts/apply-migrations.sh 260
# Verify no NULL pickup_country remain
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT count(*) FROM kvota.invoices i JOIN kvota.quotes q ON q.id=i.quote_id WHERE q.workflow_status='pending_logistics_and_customs' AND q.deleted_at IS NULL AND i.pickup_country IS NULL;\""
# Run the assignment script
ssh beget-kvota "docker exec kvota-onestack python scripts/backfill_logistics_assignment.py"
# Verify assignments now exist
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"SELECT idn_quote, assigned_logistics_user IS NOT NULL AS has_assignment FROM kvota.quotes WHERE workflow_status='pending_logistics_and_customs' AND deleted_at IS NULL;\""
```

---

## Files to modify (summary)

| File | Change | Part |
|---|---|---|
| `frontend/src/shared/lib/roles.ts` | + `isCustomsOnly` helper | 1 |
| `frontend/src/shared/lib/access.ts` | Remove customs branch from `getAssignedQuoteIds` | 1 |
| `frontend/src/entities/quote/queries.ts` | Add customs branch to `fetchQuotesList`, `canAccessQuote`, `fetchFilterOptions` | 1 |
| `frontend/src/shared/lib/__tests__/roles.test.ts` | Tests for `isCustomsOnly` | 1 |
| TBD Next.js procurement UI | Capture pickup_country | 2 |
| TBD Python submit-procurement endpoint | Enforce validation | 2 |
| `tests/test_submit_procurement_validation.py` | New: 422 on missing pickup_country | 2 |
| `migrations/260_backfill_logistics_assignment.sql` | Backfill pickup_country from supplier | 3 |
| `scripts/backfill_logistics_assignment.py` | Trigger assign_logistics_to_invoices for stuck quotes | 3 |

## Rollout

1. Local implementation via parallel developer agents (Part 1 + Part 3 in parallel, Part 2 sequential after Explore)
2. Simplify + review loop
3. Local browser test via Playwright MCP on localhost:3000
4. Commit locally (reference both FB IDs + ClickUp 86agtxp84)
5. **STOP — wait for user verification/approval**
6. On approval: apply migration 260 on prod (`apply-migrations.sh`) + run backfill script + verify
7. Push → GitHub Actions → verify on prod
8. Mark both FB IDs `resolved` via internal API

## Non-goals (explicit)

- Building a customs assignment mechanism (will be a separate task when the team wants item/route-level customs routing)
- Reverting commit 9b7fb20 (it correctly handles procurement and procurement_senior — keep those branches)
- Modifying `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`
- Touching `services/workflow_service.py` (logic is correct, only data was missing)
