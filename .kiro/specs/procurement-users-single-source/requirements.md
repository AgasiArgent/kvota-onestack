# Requirements — Procurement Users Single Source of Truth

**Created:** 2026-04-14
**Type:** BUGFIX + refactor
**Priority:** High (production drift affecting access control)

## Problem

The table `kvota.quotes` has a legacy `assigned_procurement_users UUID[]` column that duplicates information also stored per-item in `kvota.quote_items.assigned_procurement_user`. The new distribution flow (Phase 4 kanban: `api/procurement.py` items/assign, items/bulk) writes only to the item-level column. The quote-level array is stale.

**Impact on production (measured 2026-04-14):** 18 of 44 quotes have drift — items carry МОЗ assignments but the quote-level array is empty. Procurement users assigned via the new flow do not appear in:

- "My quotes" list filters (`main.py:5794`, `:5838`, `:6000`)
- Permission check for quote-level procurement access (`main.py:16990`)
- Stage timer MOЗ resolution (`services/stage_timer_service.py:165`)
- Telegram notification routing (`services/telegram_service.py:3252`)
- Customs step UI (`frontend/.../customs-info-block.tsx:88`)
- Messages filter (`frontend/.../messages/queries.ts:95`)

## Goal

Make `quote_items.assigned_procurement_user` the single source of truth for "which procurement users are involved with this quote". Remove the materialized array, rewrite all readers to query items directly. No application-level sync, no DB trigger.

## Requirements

### REQ-1 — Reader migration: quote list filters
All "my quotes" list queries MUST return a quote if ANY of its non-deleted items have `assigned_procurement_user = current_user_id`.

**Before:** `.contains("assigned_procurement_users", [user_id])`
**After:** PostgREST inner join `quote_items!inner(assigned_procurement_user)` with `.eq("quote_items.assigned_procurement_user", user_id)` producing SELECT DISTINCT at the query layer (or equivalent Python subquery).

Affected sites: `main.py:5794`, `:5838`, `:6000`.

### REQ-2 — Reader migration: permission check
Quote-level procurement permission check (`main.py:16990`) MUST return True if current user is assigned to any item of the quote.

### REQ-3 — Reader migration: stage timer
`services/stage_timer_service.py` stage-timing resolution MUST derive procurement user list from items, not the legacy array.

### REQ-4 — Reader migration: Telegram notifications
`services/telegram_service.py` MUST route notifications to all procurement users derived from items.

### REQ-5 — Reader migration: frontend
Frontend readers (customs-info-block.tsx, messages/queries.ts) MUST use Supabase embedded filter on `quote_items` instead of array containment.

### REQ-6 — Writer removal
`services/workflow_service.py` MUST NOT write to `quotes.assigned_procurement_users` (lines ~2190, ~2249). Reads of the column (lines ~2609, ~2656) MUST be replaced with item-derived queries or removed if no longer needed.

### REQ-7 — Schema migration
Migration 276 MUST drop:
1. Column `kvota.quotes.assigned_procurement_users`
2. Index `idx_quotes_assigned_procurement_users` (GIN on the array)

Migration MUST run AFTER all readers have been updated in the same commit to avoid runtime "column does not exist" errors.

### REQ-8 — Regression test
A new test MUST verify: a procurement user whose user_id appears in `quote_items.assigned_procurement_user` (but NOT previously in `quotes.assigned_procurement_users`) is returned by the "my quotes" query.

### REQ-9 — Type regeneration
After migration: `cd frontend && npm run db:types`. TypeScript compilation MUST pass — no `assigned_procurement_users` references remaining in type-checked code.

### REQ-10 — Docs
`DATABASE_TABLES.md:96` (line referencing the legacy column) MUST be removed.

## Non-Requirements (explicit out of scope)

- Performance benchmarking of subquery vs GIN — scale (few thousand quotes max) makes JOIN-based filter acceptable. Revisit only if p95 latency regresses.
- DB view/materialized view as a compat shim — single-commit atomic migration with all readers updated.
- Changing the distribution flow's item-level writes — those already work correctly; this refactor only fixes the read side.

## Rollout Order (single commit, tested before push)

1. Update all readers (main.py, services, frontend) → query items instead of array.
2. Remove writers in workflow_service.py.
3. Write migration 276 (drop column + index).
4. Run migration on prod via db-kvota skill.
5. Regenerate frontend types.
6. Run full test suite + prod browser-test (login as procurement user, verify /quotes visibility).
7. Commit single atomic change.

Rollback plan: migration is non-destructive for data (we're dropping metadata that was drifted anyway). If post-deploy smoke fails, the fix is forward (patch reader query), not backward (column cannot be resurrected from item data without backfill logic, but item data IS the truth so it doesn't need to).

## Risks

| Risk | Mitigation |
|------|------------|
| Reader regression: user loses visibility of their quotes | Comprehensive pre-commit test + prod browser-test as procurement user |
| PostgREST embedded filter returns duplicates (one row per matching item) | Use `.select` with distinct behavior or post-process in application |
| Supabase-js vs Supabase-py syntax divergence | Verify each call site individually, don't copy-paste across stacks |
| Migration runs before deploy finishes → runtime error | Apply migration AFTER the code deploy reaches prod, not before |
