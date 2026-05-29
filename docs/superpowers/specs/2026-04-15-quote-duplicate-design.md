# Quote Duplicate — admin feature + IDN tech debt fix

**Date:** 2026-04-15
**Status:** Approved for planning
**Originating feedback:** FB-260415-140516-2cc4 ("вот тут не подтянуло DDP")

## Context

Admin needs to create carbon-copies of a quote to test multiple workflow paths in parallel (e.g., take copy A through procurement path X, copy B through path Y, compare outcomes). The original ad-hoc SQL clone used an explicit column whitelist and silently dropped `incoterms` + `delivery_priority` — the feedback ticket exposed this. A proper feature must be immune to column drift.

Two unrelated issues with the IDN generation subsystem were discovered during the ad-hoc clone attempt:

1. `kvota.auto_generate_quote_idn` and `kvota.auto_generate_item_idn` use unqualified references (`customers`, `quotes`, `quote_items`, `generate_*_idn`), so they fail when called from a session without `kvota` in `search_path`. Latent hazard: works in normal app traffic (PostgREST sets search_path), fails in out-of-band contexts (direct psql, cron).
2. `public.auto_generate_quote_idn`, `public.generate_quote_idn`, `public.auto_generate_item_idn`, `public.generate_item_idn` are orphan duplicates of the `kvota.*` versions. The `public.generate_quote_idn` specifically is an **older, non-atomic** implementation (SELECT → UPDATE without row lock) — a hidden race-condition mine if search_path ever resolves to `public.*`.

These are fixed in the same PR as the duplicate feature since they touch the same trigger functions.

## Decisions (what we're building)

| # | Decision |
|---|---|
| 1 | Tech debt scope: qualify all `kvota.*` refs in the two trigger functions + drop all four `public.*` orphan IDN functions. `idn` vs `idn_quote` columns are **not** a tech debt — they are two semantically distinct identifiers (internal `Q-YYYYMM-NNNN` vs external `SELLER-INN-YEAR-SEQ`). |
| 2 | UI: single overflow-menu item "Duplicate" on quote detail page → modal with count input (1–50). |
| 3 | Access: **admin only**. Sales/procurement self-service duplicate is out of scope. |
| 4 | Data policy: **carbon-copy** — copy all source fields, reset only identity (`id`, `idn`, `idn_quote`, `item_idn`), timestamps, and title. Workflow state, procurement data, proforma, assigned users — all kept. Copy lands at the same workflow stage as source. |
| 5 | Child tables copied: `quote_items`, `quote_brand_substates`. Skipped: `quote_versions`, `quote_calculation_*` (5 derived tables), `quote_comments`, `quote_comment_reads`, `quote_timeline_events` (copy gets its own timeline), `quote_workflow_transitions`, `quote_approval_history`, `quote_change_requests`, `quote_export_settings`. |
| 6 | Lineage: `created_by` of copy = source's `created_by` (sales owner keeps ownership). New nullable column `quotes.cloned_from_id UUID` with FK + partial index. Timeline event `'cloned_from'` on each copy records admin actor. |
| 7 | Technical approach: **SQL function** (PL/pgSQL) using `%ROWTYPE` variables and `INSERT ... SELECT (v_row).*` — immune to future column additions. Python endpoint is a thin RPC wrapper. |
| 8 | Atomicity: per-copy SAVEPOINT inside the function. A failing copy rolls back only itself; earlier copies persist; function returns array of successfully-created IDs. |
| 9 | Post-action UX for count > 1: minimal — redirect to `/quotes` + toast. Filter `cloned_from_id` on quotes registry is deferred to a follow-up ticket. |
| 10 | Browser smoke tests are **mandatory** before merge. |

## Architecture

```
Next.js (RSC + Server Action)
    │
    ▼ thin wrapper: auth check → forward
Python API: POST /api/quotes/{id}/duplicate
    │
    ▼ supabase.rpc('duplicate_quote', ...)
SQL function: kvota.duplicate_quote(source_id, count, cloned_by)
    │
    ├─► INSERT kvota.quotes (v_row.*)          ← column-drift-immune via %ROWTYPE
    ├─► INSERT kvota.quote_items (v_item.*)    ← same pattern
    ├─► INSERT kvota.quote_brand_substates     ← same pattern
    └─► INSERT kvota.quote_timeline_events     ← 'cloned_from' event
```

**Why SQL function (not Python-side dup):**

- `%ROWTYPE` + `SELECT (v_row).*` is the only idiom that automatically picks up new columns without code changes. Python-side dict construction requires manual discipline that erodes over time.
- Atomicity per-copy via SAVEPOINT is native to PL/pgSQL.
- Triggers (`auto_generate_quote_idn`, `auto_generate_item_idn`) fire correctly on the INSERT path.
- Eliminates multiple round-trips that a Python loop would incur on `count=50`.

## Database layer

Four migrations, in order (latest migration = 278 → start at 279):

### Migration 279 — tech debt fix

```sql
-- Qualify all refs in trigger functions
CREATE OR REPLACE FUNCTION kvota.auto_generate_quote_idn() RETURNS trigger AS $$
  -- Body: customers → kvota.customers, generate_quote_idn(...) → kvota.generate_quote_idn(...)
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION kvota.auto_generate_item_idn() RETURNS trigger AS $$
  -- Body: quotes → kvota.quotes, quote_items → kvota.quote_items,
  --       generate_item_idn(...) → kvota.generate_item_idn(...)
$$ LANGUAGE plpgsql;

-- Drop orphan public.* duplicates
DROP FUNCTION IF EXISTS public.auto_generate_quote_idn();
DROP FUNCTION IF EXISTS public.auto_generate_item_idn();
DROP FUNCTION IF EXISTS public.generate_quote_idn(uuid, varchar);
DROP FUNCTION IF EXISTS public.generate_item_idn(uuid, integer);
```

Downgrade: recreate `public.*` functions with their current bodies (captured in migration header comment for reference).

### Migration 280 — lineage column

```sql
ALTER TABLE kvota.quotes
  ADD COLUMN cloned_from_id UUID REFERENCES kvota.quotes(id) ON DELETE SET NULL;

CREATE INDEX ix_quotes_cloned_from_id
  ON kvota.quotes(cloned_from_id)
  WHERE cloned_from_id IS NOT NULL;
```

Partial index (most quotes are not clones).

### Migration 281 — atomic `kvota.generate_idn_quote(org_id)`

Atomic version of the per-month counter currently implemented in `main.py:8663` (Python loop with SELECT MAX + retry). Stores the counter in `organizations.idn_counters` JSONB under key `quote_month_YYYYMM`, using the same `UPDATE ... RETURNING` idiom already used by `kvota.generate_quote_idn`.

Format preserved: `Q-YYYYMM-NNNN`.

**Scope boundary:** `main.py`'s existing Python-side generation for fresh quotes is **not** refactored in this PR. The new SQL function is consumed only by `kvota.duplicate_quote`. Migrating `POST /quotes` to use the SQL generator is a separate follow-up (isolates risk, keeps this PR focused).

### Migration 282 — `kvota.duplicate_quote(...)`

```sql
CREATE OR REPLACE FUNCTION kvota.duplicate_quote(
  p_source_id UUID,
  p_count INTEGER,
  p_cloned_by UUID
) RETURNS UUID[] AS $$
DECLARE
  v_row_q kvota.quotes%ROWTYPE;
  v_row_i kvota.quote_items%ROWTYPE;
  v_row_bs kvota.quote_brand_substates%ROWTYPE;
  v_new_id UUID;
  v_new_ids UUID[] := ARRAY[]::UUID[];
  i INTEGER;
BEGIN
  FOR i IN 1..p_count LOOP
    BEGIN  -- implicit savepoint per iteration
      SELECT * INTO v_row_q FROM kvota.quotes WHERE id = p_source_id AND deleted_at IS NULL;
      IF NOT FOUND THEN RAISE EXCEPTION 'Source quote not found: %', p_source_id; END IF;

      v_row_q.id := gen_random_uuid();
      v_row_q.idn := NULL;  -- trigger regenerates
      v_row_q.idn_quote := kvota.generate_idn_quote(v_row_q.organization_id);
      v_row_q.title := 'COPY ' || lpad(i::text, 2, '0') || ' — ' || v_row_q.title;
      v_row_q.cloned_from_id := p_source_id;
      v_row_q.created_at := now();
      v_row_q.updated_at := now();

      INSERT INTO kvota.quotes SELECT (v_row_q).*;
      v_new_id := v_row_q.id;

      FOR v_row_i IN SELECT * FROM kvota.quote_items WHERE quote_id = p_source_id ORDER BY position LOOP
        v_row_i.id := gen_random_uuid();
        v_row_i.quote_id := v_new_id;
        v_row_i.item_idn := NULL;  -- trigger regenerates (globally unique)
        v_row_i.created_at := now();
        v_row_i.updated_at := now();
        INSERT INTO kvota.quote_items SELECT (v_row_i).*;
      END LOOP;

      FOR v_row_bs IN SELECT * FROM kvota.quote_brand_substates WHERE quote_id = p_source_id LOOP
        v_row_bs.id := gen_random_uuid();
        v_row_bs.quote_id := v_new_id;
        v_row_bs.created_at := now();
        v_row_bs.updated_at := now();
        INSERT INTO kvota.quote_brand_substates SELECT (v_row_bs).*;
      END LOOP;

      INSERT INTO kvota.quote_timeline_events (quote_id, event_type, metadata, actor_user_id, created_at)
      VALUES (v_new_id, 'cloned_from',
              jsonb_build_object('source_quote_id', p_source_id, 'admin_id', p_cloned_by),
              p_cloned_by, now());

      v_new_ids := array_append(v_new_ids, v_new_id);
    EXCEPTION WHEN OTHERS THEN
      -- one copy failed; rollback to savepoint, log, continue
      RAISE WARNING 'Duplicate iteration % failed: %', i, SQLERRM;
    END;
  END LOOP;
  RETURN v_new_ids;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER;
```

**Column-drift immunity via `INSERT INTO kvota.quotes SELECT (v_row_q).*`:** the row variable expands to all columns of `kvota.quotes` at runtime. Adding a column tomorrow automatically includes it in duplication with zero code change.

The schemas of `quote_brand_substates` and `quote_timeline_events` need to be checked during plan phase (column names, required fields, constraints) and the function body adjusted accordingly.

## Python API layer

### Contract

`POST /api/quotes/{quote_id}/duplicate`

Request body:
```json
{ "count": 20, "user_id": "<uuid>" }
```

Response 201:
```json
{
  "success": true,
  "data": {
    "created_ids": ["<uuid>", ...],
    "created_count": 20,
    "source_idn_quote": "Q-202604-0047"
  }
}
```

Error responses follow project envelope `{ "success": false, "error": { "code", "message" } }`.

### Error codes

| Code | HTTP | Trigger |
|------|------|---------|
| `UNAUTHORIZED` | 401 | No auth |
| `NOT_ADMIN` | 403 | User is not `admin` |
| `QUOTE_NOT_FOUND` | 404 | Source UUID doesn't exist or is soft-deleted |
| `QUOTE_NOT_IN_USER_ORG` | 403 | Source belongs to a different org |
| `INVALID_COUNT` | 400 | `count` not an int or out of [1, 50] |
| `DUPLICATE_FAILED` | 500 | SQL function raised |

### Handler responsibilities

1. Dual auth: accept JWT (`request.state.api_user`) OR session cookie (see `memory/feedback_dual_auth_api.md`).
2. Role check: `admin` in `user.roles`.
3. Body validation: `count` is int, `1 ≤ count ≤ 50`.
4. Source lookup: fetch `id, idn_quote, organization_id, deleted_at`. 404 if missing/deleted, 403 if cross-org.
5. Call `supabase.rpc('duplicate_quote', ...)`.
6. Log at INFO: `quote_id, count, user_id, created_count`. Errors → Sentry with `quote_id, user_id` tags.
7. Return 201 with `{ created_ids, created_count, source_idn_quote }`.

### Structured docstring

Every `/api/*` handler must carry the docstring format from `.claude/rules/api-first.md` (Path, Params, Returns, Side Effects, Roles) — this feeds future OpenAPI/MCP generation.

## Frontend layer

### File structure (FSD)

```
frontend/src/features/duplicate-quote/
├── api/
│   └── duplicate-quote.action.ts      Server Action (thin wrapper)
└── ui/
    ├── DuplicateQuoteDialog.tsx       shadcn Dialog
    └── DuplicateQuoteMenuItem.tsx     overflow-menu item (admin-only render)
```

### Visibility gate

`DuplicateQuoteMenuItem` rendered **conditionally on the server** by parent RSC:
```tsx
{user.roles.includes('admin') && <DuplicateQuoteMenuItem quoteId={quote.id} />}
```

Not `hidden`, not `disabled` — the component simply doesn't exist in the DOM for non-admins.

### Modal contents

- Header: "Duplicate quote"
- Body: source IDN + workflow-stage note ("Carbon-copy будет создан на том же этапе: `pending_procurement`")
- Input: `<Input type="number" min=1 max=50 defaultValue=1 />`
- CTA `[Cancel] [Duplicate]`
- Loading state: CTA disabled + "Creating N copies…" + spinner
- Error state: inline `<Alert variant="destructive">` inside modal (modal does not close on error)

### Post-action navigation

| count | Behavior |
|-------|----------|
| 1 | Toast "Copy created: `Q-202604-XXXX`" → router.push(`/quotes/${newId}`) |
| N > 1 | Toast "Created N copies" → router.push(`/quotes`) |

### Server Action contract

```typescript
"use server";
export async function duplicateQuote(quoteId: string, count: number): Promise<{
  created_ids: string[];
  created_count: number;
  source_idn_quote: string;
}> {
  const user = await getSessionUser();
  if (!user?.roles?.includes("admin")) throw new Error("Forbidden");
  const res = await apiServerClient(`/quotes/${quoteId}/duplicate`, {
    method: "POST",
    body: JSON.stringify({ count, user_id: user.id }),
  });
  if (!res.success) throw new Error(res.error?.message ?? "Duplicate failed");
  revalidatePath("/quotes");
  return res.data;
}
```

Zero business logic — pure forwarding.

### Integration point

Existing overflow menu on the quote detail page — exact component path to be determined in plan phase by inspecting `frontend/src/app/(app)/quotes/[id]/...`.

## Testing strategy

Pyramid: many DB-level unit-ish tests, several integration/API tests, minimal E2E.

### A. DB-level (`pytest.mark.integration`, local Supabase with transactional fixture)

**Critical regression — column drift:**
```python
def test_duplicate_quote_immune_to_new_columns(db, admin_user, src_quote):
    db.execute("ALTER TABLE kvota.quotes ADD COLUMN _test_dummy TEXT")
    try:
        db.execute("UPDATE kvota.quotes SET _test_dummy='xyz' WHERE id=%s", [src_quote.id])
        ids = db.execute("SELECT kvota.duplicate_quote(%s, 1, %s)",
                         [src_quote.id, admin_user.id]).scalar()
        val = db.execute("SELECT _test_dummy FROM kvota.quotes WHERE id=%s", [ids[0]]).scalar()
        assert val == 'xyz'
    finally:
        db.execute("ALTER TABLE kvota.quotes DROP COLUMN _test_dummy")
```

**Other DB tests:**
- `test_duplicate_sets_cloned_from_id`
- `test_duplicate_regenerates_idn_and_idn_quote`
- `test_duplicate_copies_items_resets_item_idn`
- `test_duplicate_copies_brand_substates`
- `test_duplicate_writes_cloned_from_timeline_event`
- `test_duplicate_count_20_produces_20_copies`
- `test_duplicate_copy_is_atomic_per_iteration` — inject a failure mid-batch, assert earlier copies persist
- `test_duplicate_idn_quote_unique_across_concurrent_calls` — 10 parallel threads, all IDN_quotes unique
- `test_duplicate_source_not_found_raises`
- `test_duplicate_soft_deleted_source_raises`

**Tech debt regression:**
- `test_auto_generate_quote_idn_works_without_kvota_in_search_path` — the original FB-260415 root cause
- `test_public_orphan_functions_dropped`

### B. Python API (`pytest + httpx`)

- `test_duplicate_endpoint_requires_auth` → 401
- `test_duplicate_endpoint_requires_admin` → 403 `NOT_ADMIN`
- `test_duplicate_endpoint_admin_ok` → 201
- `test_duplicate_endpoint_rejects_cross_org` → 403 `QUOTE_NOT_IN_USER_ORG`
- `test_duplicate_endpoint_validates_count` (0, 51, non-int) → 400
- `test_duplicate_endpoint_quote_not_found` → 404
- `test_duplicate_endpoint_count_1_returns_201`
- `test_duplicate_endpoint_count_20_returns_201`

### C. Browser smoke (Playwright MCP, mandatory before merge)

1. Login as admin → quote detail → overflow menu → "Duplicate" present → click → modal appears → count=1 submit → redirect to new quote, title starts with `COPY 01 — `.
2. Same admin → submit count=5 → toast "Created 5 copies" → redirect to /quotes.
3. Login as sales → quote detail → overflow menu → "Duplicate" **not present in DOM**.

### D. Fixtures

- `admin_user` (org A), `sales_user` (org A), `admin_org_b` (org B) — for cross-org test
- `src_quote_full` — quote with 6 items that have procurement data populated (proforma, supplier_id, hs_code) — simulates a realistic `pending_procurement` quote
- `src_quote_minimal` — draft quote with no items — edge case

## Out of scope (deliberately deferred)

- Refactor `POST /quotes` in `main.py` to use new `kvota.generate_idn_quote` SQL function
- Collapse `idn` and `idn_quote` columns into one canonical identifier
- `cloned_from_id` filter on quotes registry (enables "show all clones of X")
- Self-service duplicate for sales/procurement roles
- Bulk duplicate from quotes registry (select multiple, duplicate each)
- Toggle "reset procurement data" in modal (for when carbon-copy is not desired)
- Copy `quote_versions` (functional equivalence acceptable for test-seeding use case)

## Open follow-ups

After this PR lands:
- Track usage (log `created_count` distribution) to validate the 50-copy cap.
- Review the `main.py` `idn_quote` generation race condition — may be low-impact today but should ride on top of the SQL generator.
- Consider a generic `kvota.duplicate_row(table_name, id)` helper for future "duplicate X" admin features (YAGNI for now — one use case does not justify a generic).
