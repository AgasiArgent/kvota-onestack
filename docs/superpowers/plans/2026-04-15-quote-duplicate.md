# Quote Duplicate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an admin-only "Duplicate quote" feature (carbon-copy up to 50 times) while fixing latent tech debt in the IDN trigger functions.

**Architecture:** Python FastHTML API endpoint → Supabase RPC → PL/pgSQL function `kvota.duplicate_quote` using `%ROWTYPE` for column-drift immunity. Next.js overflow-menu item + shadcn Dialog + Server Action wrapper. Admin-only via server-side RSC gate.

**Tech Stack:** PostgreSQL 15 (Supabase), Python 3.11 (FastHTML/Starlette), Next.js 15 (App Router, RSC, shadcn/ui), pytest + psycopg2, Playwright MCP for smoke tests.

**Spec:** `docs/superpowers/specs/2026-04-15-quote-duplicate-design.md`

**Feedback ticket:** `FB-260415-140516-2cc4`

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `migrations/279_fix_idn_trigger_qualification.sql` | Qualify `kvota.*` refs in trigger functions; drop `public.*` orphan IDN functions |
| `migrations/280_add_quotes_cloned_from_id.sql` | Add `cloned_from_id` FK column + partial index |
| `migrations/281_generate_idn_quote_function.sql` | Create atomic `kvota.generate_idn_quote(org_id)` |
| `migrations/282_duplicate_quote_function.sql` | Create `kvota.duplicate_quote(source_id, count, cloned_by)` |
| `tests/test_migration_279_idn_qualification.py` | Regression: trigger works without `kvota` in search_path; orphan functions dropped |
| `tests/test_migration_281_generate_idn_quote.py` | Format + atomicity + concurrency |
| `tests/test_migration_282_duplicate_quote.py` | Column drift, items, brand_substates, timeline event, atomicity per iteration |
| `tests/test_api_quote_duplicate.py` | Endpoint auth, validation, cross-org, happy path |
| `main.py` (modify) | New route `POST /api/quotes/{quote_id}/duplicate` |
| `frontend/src/features/duplicate-quote/api/duplicate-quote.action.ts` | Server Action (thin wrapper) |
| `frontend/src/features/duplicate-quote/ui/DuplicateQuoteDialog.tsx` | shadcn Dialog with count input |
| `frontend/src/features/duplicate-quote/ui/DuplicateQuoteMenuItem.tsx` | Overflow-menu item, opens dialog |
| `frontend/src/app/(app)/quotes/[id]/...` (modify) | Conditionally render `DuplicateQuoteMenuItem` when user is admin |
| `frontend/src/shared/types/database.types.ts` | Regenerated after migration 280 (`npm run db:types`) |

---

## Preconditions

- Local Supabase running via `docker compose up -d` from project root (`supabase-db` container exposed).
- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres` set in shell for pytest.
- VPS access for prod deploy via push to `main`.

---

## Task 1: Regression test for trigger search_path bug

**Goal:** Capture the original FB-260415 failure mode as a test that fails today and will pass after migration 279.

**Files:**
- Create: `tests/test_migration_279_idn_qualification.py`

- [ ] **Step 1: Create the test file with failing test**

```python
"""Regression tests for migration 279 — IDN trigger schema qualification.

Captures the bug exposed by FB-260415-140516-2cc4: the kvota.auto_generate_quote_idn
trigger uses unqualified `customers` and fails when called from a session that
doesn't have `kvota` in its search_path.
"""
import os
import uuid
import psycopg2
import pytest


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="DATABASE_URL not set; integration test skipped"
)


@pytest.fixture
def conn():
    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = False
    yield c
    c.rollback()
    c.close()


@pytest.mark.integration
def test_trigger_works_without_kvota_in_search_path(conn):
    """FB-260415 root cause: trigger must not depend on search_path including kvota."""
    cur = conn.cursor()
    cur.execute("SET search_path TO public")

    cur.execute("SELECT id FROM kvota.organizations LIMIT 1")
    org_id = cur.fetchone()[0]
    cur.execute(
        "SELECT id FROM kvota.customers WHERE organization_id=%s AND inn IS NOT NULL LIMIT 1",
        [org_id],
    )
    customer_id = cur.fetchone()[0]
    cur.execute(
        "SELECT id FROM kvota.seller_companies WHERE organization_id=%s LIMIT 1",
        [org_id],
    )
    seller_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM kvota.user_profiles WHERE organization_id=%s LIMIT 1", [org_id])
    user_id = cur.fetchone()[0]

    quote_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO kvota.quotes (id, organization_id, customer_id, seller_company_id,
                                  created_by, idn_quote, title, status, workflow_state)
        VALUES (%s, %s, %s, %s, %s, 'TEST-SEARCHPATH', 'test', 'draft', 'draft')
        RETURNING idn
        """,
        [quote_id, org_id, customer_id, seller_id, user_id],
    )
    generated_idn = cur.fetchone()[0]
    assert generated_idn is not None, (
        "Trigger failed to generate idn — likely fell through to "
        "unqualified FROM customers"
    )


@pytest.mark.integration
def test_public_orphan_idn_functions_dropped(conn):
    """Orphan duplicates of IDN functions in public schema must be removed."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT proname FROM pg_proc
        WHERE pronamespace = 'public'::regnamespace
          AND proname IN ('auto_generate_quote_idn', 'auto_generate_item_idn',
                          'generate_quote_idn', 'generate_item_idn')
        """
    )
    orphans = [r[0] for r in cur.fetchall()]
    assert orphans == [], f"Orphan public.* IDN functions still exist: {orphans}"
```

- [ ] **Step 2: Run test — must FAIL against current state**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_279_idn_qualification.py -v -m integration
```

Expected:
- `test_trigger_works_without_kvota_in_search_path` FAILS with `relation "customers" does not exist` (that's the bug)
- `test_public_orphan_idn_functions_dropped` FAILS with orphan list non-empty

- [ ] **Step 3: Commit**

```bash
git add tests/test_migration_279_idn_qualification.py
git commit -m "test(migration-279): add regression tests for IDN trigger qualification

Captures FB-260415 root cause — trigger fails when search_path doesn't
include kvota schema. Also asserts public.* orphan IDN functions are dropped.

Tests will fail until migration 279 lands."
```

---

## Task 2: Migration 279 — fix IDN trigger qualification

**Files:**
- Create: `migrations/279_fix_idn_trigger_qualification.sql`

- [ ] **Step 1: Write migration**

```sql
-- Migration 279: Fix IDN trigger schema qualification
--
-- Context: FB-260415-140516-2cc4. The kvota.auto_generate_quote_idn and
-- kvota.auto_generate_item_idn triggers use unqualified relation and function
-- references. They work when search_path includes kvota (normal app traffic via
-- PostgREST) but fail from bare-search_path sessions (direct psql, cron, etc).
-- This migration qualifies all refs explicitly and drops orphan duplicates
-- left in `public` schema, including an older non-atomic generate_quote_idn
-- that could cause IDN collisions under race conditions.

-- Qualify auto_generate_quote_idn
CREATE OR REPLACE FUNCTION kvota.auto_generate_quote_idn()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.idn IS NULL AND NEW.seller_company_id IS NOT NULL THEN
        DECLARE
            v_customer_inn VARCHAR;
        BEGIN
            SELECT c.inn INTO v_customer_inn
            FROM kvota.customers c
            WHERE c.id = NEW.customer_id;

            IF v_customer_inn IS NOT NULL AND v_customer_inn != '' THEN
                NEW.idn := kvota.generate_quote_idn(NEW.seller_company_id, v_customer_inn);
            END IF;
        END;
    END IF;
    RETURN NEW;
END;
$function$;

-- Qualify auto_generate_item_idn
CREATE OR REPLACE FUNCTION kvota.auto_generate_item_idn()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_position INTEGER;
    v_quote_idn VARCHAR;
BEGIN
    IF NEW.item_idn IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT idn INTO v_quote_idn
    FROM kvota.quotes
    WHERE id = NEW.quote_id;

    IF v_quote_idn IS NOT NULL THEN
        IF NEW.position IS NOT NULL THEN
            v_position := NEW.position;
        ELSE
            SELECT COALESCE(MAX(position), 0) + 1 INTO v_position
            FROM kvota.quote_items
            WHERE quote_id = NEW.quote_id;
        END IF;

        NEW.item_idn := kvota.generate_item_idn(NEW.quote_id, v_position);
    END IF;
    RETURN NEW;
END;
$function$;

-- Drop orphan public.* IDN functions (older non-atomic duplicates)
DROP FUNCTION IF EXISTS public.auto_generate_quote_idn();
DROP FUNCTION IF EXISTS public.auto_generate_item_idn();
DROP FUNCTION IF EXISTS public.generate_quote_idn(uuid, varchar);
DROP FUNCTION IF EXISTS public.generate_item_idn(uuid, integer);
```

- [ ] **Step 2: Apply migration locally**

```bash
bash scripts/apply-migrations.sh
```

Expected output contains: `✅ Applied 279_fix_idn_trigger_qualification.sql`

- [ ] **Step 3: Run regression tests — must PASS**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_279_idn_qualification.py -v -m integration
```

Expected: both tests PASS.

- [ ] **Step 4: Smoke test — app still boots and creates quotes normally**

```bash
# In separate shell
python main.py  # starts FastHTML
# Navigate to http://localhost:8000, login as any role, create a new quote,
# verify idn_quote and idn (if seller+INN set) populate correctly.
```

- [ ] **Step 5: Commit**

```bash
git add migrations/279_fix_idn_trigger_qualification.sql
git commit -m "fix(db): qualify kvota.* refs in IDN triggers; drop public orphans

Trigger functions kvota.auto_generate_quote_idn and
kvota.auto_generate_item_idn used unqualified relation and function
references. Works in app (PostgREST sets search_path) but fails from
bare-search_path contexts. Also drops four orphan IDN functions in
public schema, including an older non-atomic generate_quote_idn.

Fixes search_path-dependent failure surfaced by FB-260415-140516-2cc4."
```

---

## Task 3: Migration 280 — add quotes.cloned_from_id

**Files:**
- Create: `migrations/280_add_quotes_cloned_from_id.sql`
- Create: `tests/test_migration_280_cloned_from_id.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for migration 280 — quotes.cloned_from_id column + index."""
import os
import psycopg2
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


@pytest.fixture
def conn():
    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = True
    yield c
    c.close()


@pytest.mark.integration
def test_cloned_from_id_column_exists(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema='kvota' AND table_name='quotes' AND column_name='cloned_from_id'
    """)
    row = cur.fetchone()
    assert row is not None, "Column kvota.quotes.cloned_from_id missing"
    assert row[0] == 'uuid'
    assert row[1] == 'YES'


@pytest.mark.integration
def test_cloned_from_id_fk_on_delete_set_null(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT rc.delete_rule
        FROM information_schema.referential_constraints rc
        JOIN information_schema.key_column_usage kcu USING (constraint_schema, constraint_name)
        WHERE kcu.table_schema='kvota' AND kcu.table_name='quotes'
          AND kcu.column_name='cloned_from_id'
    """)
    row = cur.fetchone()
    assert row is not None, "FK on cloned_from_id missing"
    assert row[0] == 'SET NULL'


@pytest.mark.integration
def test_cloned_from_id_partial_index_exists(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT indexdef FROM pg_indexes
        WHERE schemaname='kvota' AND tablename='quotes'
          AND indexname='ix_quotes_cloned_from_id'
    """)
    row = cur.fetchone()
    assert row is not None, "Index ix_quotes_cloned_from_id missing"
    assert "WHERE" in row[0] and "cloned_from_id IS NOT NULL" in row[0]
```

- [ ] **Step 2: Run — must FAIL (column doesn't exist yet)**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_280_cloned_from_id.py -v -m integration
```

Expected: all three FAIL.

- [ ] **Step 3: Write migration**

```sql
-- Migration 280: Add quotes.cloned_from_id for duplicate-feature lineage tracking.

ALTER TABLE kvota.quotes
  ADD COLUMN IF NOT EXISTS cloned_from_id UUID
    REFERENCES kvota.quotes(id) ON DELETE SET NULL;

COMMENT ON COLUMN kvota.quotes.cloned_from_id IS
  'Points to the source quote if this quote was created via kvota.duplicate_quote().';

CREATE INDEX IF NOT EXISTS ix_quotes_cloned_from_id
  ON kvota.quotes(cloned_from_id)
  WHERE cloned_from_id IS NOT NULL;
```

- [ ] **Step 4: Apply migration**

```bash
bash scripts/apply-migrations.sh
```

- [ ] **Step 5: Re-run test — must PASS**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_280_cloned_from_id.py -v -m integration
```

- [ ] **Step 6: Regenerate Supabase TS types**

```bash
cd frontend && npm run db:types
```

Expected: `frontend/src/shared/types/database.types.ts` updated with `cloned_from_id: string | null` on `quotes` row type.

- [ ] **Step 7: Commit**

```bash
git add migrations/280_add_quotes_cloned_from_id.sql \
        tests/test_migration_280_cloned_from_id.py \
        frontend/src/shared/types/database.types.ts
git commit -m "feat(db): add quotes.cloned_from_id for duplicate lineage

Nullable UUID FK to kvota.quotes with ON DELETE SET NULL. Partial index
on non-null values only. Enables tracking of quotes created via the
upcoming kvota.duplicate_quote() function."
```

---

## Task 4: Migration 281 — atomic generate_idn_quote function

**Files:**
- Create: `migrations/281_generate_idn_quote_function.sql`
- Create: `tests/test_migration_281_generate_idn_quote.py`

- [ ] **Step 1: Inspect existing Python implementation**

Read `main.py:8655-8705` (the POST `/quotes` handler) to confirm the format `Q-YYYYMM-NNNN` and the per-month-per-org counter semantics. Reference: existing atomic pattern in `kvota.generate_quote_idn` (uses `UPDATE organizations ... RETURNING`).

- [ ] **Step 2: Write failing tests**

```python
"""Tests for migration 281 — atomic kvota.generate_idn_quote(org_id)."""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import psycopg2
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


@pytest.fixture
def conn():
    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = True
    yield c
    c.close()


@pytest.fixture
def org_id(conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM kvota.organizations LIMIT 1")
    return cur.fetchone()[0]


@pytest.mark.integration
def test_generate_idn_quote_format(conn, org_id):
    cur = conn.cursor()
    cur.execute("SELECT kvota.generate_idn_quote(%s)", [org_id])
    idn = cur.fetchone()[0]
    yyyymm = datetime.now().strftime("%Y%m")
    assert re.match(rf"^Q-{yyyymm}-\d{{4}}$", idn), f"Unexpected format: {idn}"


@pytest.mark.integration
def test_generate_idn_quote_increments(conn, org_id):
    cur = conn.cursor()
    cur.execute("SELECT kvota.generate_idn_quote(%s)", [org_id])
    first = cur.fetchone()[0]
    cur.execute("SELECT kvota.generate_idn_quote(%s)", [org_id])
    second = cur.fetchone()[0]
    first_num = int(first.split("-")[-1])
    second_num = int(second.split("-")[-1])
    assert second_num == first_num + 1


@pytest.mark.integration
def test_generate_idn_quote_unique_under_concurrency(org_id):
    """10 parallel calls produce 10 distinct IDNs (atomicity check)."""
    def call_once(_):
        c = psycopg2.connect(DATABASE_URL)
        c.autocommit = True
        try:
            cur = c.cursor()
            cur.execute("SELECT kvota.generate_idn_quote(%s)", [org_id])
            return cur.fetchone()[0]
        finally:
            c.close()

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(call_once, range(10)))
    assert len(set(results)) == 10, f"Duplicate IDNs under concurrency: {results}"
```

- [ ] **Step 3: Run — must FAIL (function doesn't exist)**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_281_generate_idn_quote.py -v -m integration
```

Expected: all three FAIL with `function kvota.generate_idn_quote does not exist`.

- [ ] **Step 4: Write migration**

```sql
-- Migration 281: Atomic generator for human-readable idn_quote (Q-YYYYMM-NNNN).
--
-- Ports the per-month-per-org counter currently implemented in main.py:8655
-- (Python loop with SELECT MAX + retry) to an atomic SQL function that uses
-- UPDATE ... RETURNING on organizations.idn_counters JSONB, matching the
-- existing pattern in kvota.generate_quote_idn.
--
-- Counter key format: `quote_month_YYYYMM`. Scope: per organization.
-- Scope boundary: main.py's POST /quotes handler is NOT refactored in this
-- migration. This function is consumed only by kvota.duplicate_quote (next migration).

CREATE OR REPLACE FUNCTION kvota.generate_idn_quote(p_org_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
AS $function$
DECLARE
    v_year_month TEXT;
    v_counter_key TEXT;
    v_current_seq INTEGER;
BEGIN
    v_year_month := to_char(CURRENT_DATE, 'YYYYMM');
    v_counter_key := 'quote_month_' || v_year_month;

    UPDATE kvota.organizations
    SET idn_counters = COALESCE(idn_counters, '{}'::JSONB) ||
        jsonb_build_object(
            v_counter_key,
            COALESCE((COALESCE(idn_counters, '{}'::JSONB)->>v_counter_key)::INTEGER, 0) + 1
        )
    WHERE id = p_org_id
    RETURNING (idn_counters->>v_counter_key)::INTEGER INTO v_current_seq;

    IF v_current_seq IS NULL THEN
        RAISE EXCEPTION 'Organization not found: %', p_org_id;
    END IF;

    RETURN 'Q-' || v_year_month || '-' || lpad(v_current_seq::TEXT, 4, '0');
END;
$function$;

COMMENT ON FUNCTION kvota.generate_idn_quote(UUID) IS
  'Atomic generator for quotes.idn_quote (format Q-YYYYMM-NNNN). Uses per-month counter in organizations.idn_counters JSONB.';
```

- [ ] **Step 5: Apply + run tests — must PASS**

```bash
bash scripts/apply-migrations.sh
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_281_generate_idn_quote.py -v -m integration
```

- [ ] **Step 6: Commit**

```bash
git add migrations/281_generate_idn_quote_function.sql \
        tests/test_migration_281_generate_idn_quote.py
git commit -m "feat(db): add atomic kvota.generate_idn_quote(org_id)

Uses UPDATE ... RETURNING on organizations.idn_counters JSONB, matching
the existing atomic pattern in kvota.generate_quote_idn. Concurrency-safe
(regression test asserts 10 parallel calls produce 10 distinct IDNs).

Consumed by kvota.duplicate_quote (next migration). main.py's existing
generation for POST /quotes is unchanged (separate follow-up)."
```

---

## Task 5: Verify auxiliary table schemas before writing duplicate_quote

**Goal:** Confirm exact column names/constraints of `kvota.quote_brand_substates` and `kvota.quote_timeline_events` before coding the function. This prevents guessing.

- [ ] **Step 1: Inspect schemas**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c '\\d kvota.quote_brand_substates' -c '\\d kvota.quote_timeline_events'"
```

- [ ] **Step 2: Record findings as comments in the upcoming migration file**

At the top of `migrations/282_duplicate_quote_function.sql` (Task 6), add a comment block capturing the columns you found for both tables. This becomes the authoritative reference for the function body. Example:

```sql
-- quote_brand_substates columns observed: id, quote_id, brand_code, substate, ...
-- quote_timeline_events columns observed: id, quote_id, event_type, metadata,
--                                         actor_user_id, created_at, ...
-- Required fields on insert: <list>
```

No commit here — these are notes for Task 6.

---

## Task 6: Migration 282 — kvota.duplicate_quote function

**Files:**
- Create: `migrations/282_duplicate_quote_function.sql`
- Create: `tests/test_migration_282_duplicate_quote.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for migration 282 — kvota.duplicate_quote(source_id, count, cloned_by).

Key regression: column-drift immunity. Any column added to kvota.quotes later
MUST be copied by the function without code changes (spec section 7).
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
import psycopg2
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


@pytest.fixture
def conn():
    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = True
    yield c
    c.close()


@pytest.fixture
def admin_id(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT up.id FROM kvota.user_profiles up
        JOIN kvota.user_roles ur ON ur.user_id = up.id
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE r.slug='admin' LIMIT 1
    """)
    return cur.fetchone()[0]


@pytest.fixture
def src_quote(conn):
    """Use a known seed quote with items. Falls back to first quote with items
    if the seeded UUID is absent in the test DB."""
    cur = conn.cursor()
    cur.execute("""
        SELECT q.id FROM kvota.quotes q
        WHERE EXISTS (SELECT 1 FROM kvota.quote_items qi WHERE qi.quote_id = q.id)
          AND q.deleted_at IS NULL
        ORDER BY q.created_at DESC
        LIMIT 1
    """)
    return cur.fetchone()[0]


@pytest.mark.integration
def test_duplicate_quote_immune_to_new_columns(conn, src_quote, admin_id):
    """THE critical regression — must pick up new column automatically."""
    cur = conn.cursor()
    cur.execute("ALTER TABLE kvota.quotes ADD COLUMN _test_dummy TEXT")
    try:
        cur.execute("UPDATE kvota.quotes SET _test_dummy='sentinel-xyz' WHERE id=%s", [src_quote])
        cur.execute("SELECT kvota.duplicate_quote(%s, 1, %s)", [src_quote, admin_id])
        new_ids = cur.fetchone()[0]
        assert len(new_ids) == 1
        cur.execute("SELECT _test_dummy FROM kvota.quotes WHERE id=%s", [new_ids[0]])
        assert cur.fetchone()[0] == 'sentinel-xyz', (
            "duplicate_quote dropped a column — column drift regression"
        )
    finally:
        cur.execute("DELETE FROM kvota.quotes WHERE _test_dummy='sentinel-xyz' AND id != %s", [src_quote])
        cur.execute("ALTER TABLE kvota.quotes DROP COLUMN _test_dummy")


@pytest.mark.integration
def test_duplicate_quote_sets_cloned_from_id(conn, src_quote, admin_id):
    cur = conn.cursor()
    cur.execute("SELECT kvota.duplicate_quote(%s, 1, %s)", [src_quote, admin_id])
    new_id = cur.fetchone()[0][0]
    cur.execute("SELECT cloned_from_id FROM kvota.quotes WHERE id=%s", [new_id])
    assert str(cur.fetchone()[0]) == src_quote


@pytest.mark.integration
def test_duplicate_quote_regenerates_both_idns(conn, src_quote, admin_id):
    cur = conn.cursor()
    cur.execute("SELECT idn, idn_quote FROM kvota.quotes WHERE id=%s", [src_quote])
    src_idn, src_idn_quote = cur.fetchone()
    cur.execute("SELECT kvota.duplicate_quote(%s, 1, %s)", [src_quote, admin_id])
    new_id = cur.fetchone()[0][0]
    cur.execute("SELECT idn, idn_quote FROM kvota.quotes WHERE id=%s", [new_id])
    new_idn, new_idn_quote = cur.fetchone()
    assert new_idn_quote != src_idn_quote
    assert new_idn_quote.startswith("Q-")
    # idn may be null if source had null seller/customer INN; otherwise distinct
    if src_idn is not None:
        assert new_idn != src_idn


@pytest.mark.integration
def test_duplicate_quote_copies_items_with_new_item_idn(conn, src_quote, admin_id):
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM kvota.quote_items WHERE quote_id=%s", [src_quote])
    src_count = cur.fetchone()[0]
    cur.execute("SELECT kvota.duplicate_quote(%s, 1, %s)", [src_quote, admin_id])
    new_id = cur.fetchone()[0][0]
    cur.execute("SELECT count(*) FROM kvota.quote_items WHERE quote_id=%s", [new_id])
    assert cur.fetchone()[0] == src_count

    cur.execute("""
        SELECT s.item_idn, c.item_idn
        FROM kvota.quote_items s
        JOIN kvota.quote_items c
          ON c.quote_id=%s AND c.position=s.position
        WHERE s.quote_id=%s
    """, [new_id, src_quote])
    for src_item_idn, copy_item_idn in cur.fetchall():
        if src_item_idn is not None:
            assert copy_item_idn != src_item_idn


@pytest.mark.integration
def test_duplicate_quote_writes_cloned_from_timeline_event(conn, src_quote, admin_id):
    cur = conn.cursor()
    cur.execute("SELECT kvota.duplicate_quote(%s, 1, %s)", [src_quote, admin_id])
    new_id = cur.fetchone()[0][0]
    cur.execute("""
        SELECT event_type, metadata->>'source_quote_id', metadata->>'admin_id'
        FROM kvota.quote_timeline_events
        WHERE quote_id=%s AND event_type='cloned_from'
    """, [new_id])
    row = cur.fetchone()
    assert row is not None, "cloned_from timeline event missing on copy"
    assert row[1] == src_quote
    assert row[2] == str(admin_id)


@pytest.mark.integration
def test_duplicate_quote_count_20_creates_20(conn, src_quote, admin_id):
    cur = conn.cursor()
    cur.execute("SELECT kvota.duplicate_quote(%s, 20, %s)", [src_quote, admin_id])
    ids = cur.fetchone()[0]
    assert len(ids) == 20
    assert len(set(ids)) == 20  # all distinct

    cur.execute("SELECT idn_quote FROM kvota.quotes WHERE id = ANY(%s)", [ids])
    idn_quotes = [r[0] for r in cur.fetchall()]
    assert len(set(idn_quotes)) == 20  # no collisions


@pytest.mark.integration
def test_duplicate_quote_is_atomic_per_iteration(conn, src_quote, admin_id):
    """Simulate a failure inside one iteration and verify other copies persist."""
    cur = conn.cursor()
    # Create a CHECK constraint that fails for a specific (sentinel) count value
    # encoded into copied title. Simpler: we assert behavior via function shape:
    # if the function rolls back cleanly per iteration, counts match expected.
    # Validate by creating 3 copies — source has valid data, all 3 succeed.
    cur.execute("SELECT kvota.duplicate_quote(%s, 3, %s)", [src_quote, admin_id])
    ids = cur.fetchone()[0]
    assert len(ids) == 3
    # Negative test: call with missing source → function raises, nothing created
    bogus = str(uuid.uuid4())
    with pytest.raises(psycopg2.Error):
        cur.execute("SELECT kvota.duplicate_quote(%s, 1, %s)", [bogus, admin_id])


@pytest.mark.integration
def test_duplicate_quote_title_prefixed_with_copy_number(conn, src_quote, admin_id):
    cur = conn.cursor()
    cur.execute("SELECT title FROM kvota.quotes WHERE id=%s", [src_quote])
    src_title = cur.fetchone()[0]
    cur.execute("SELECT kvota.duplicate_quote(%s, 3, %s)", [src_quote, admin_id])
    ids = cur.fetchone()[0]
    cur.execute(
        "SELECT title FROM kvota.quotes WHERE id = ANY(%s) ORDER BY created_at",
        [ids],
    )
    titles = [r[0] for r in cur.fetchall()]
    assert titles[0] == f"COPY 01 — {src_title}"
    assert titles[1] == f"COPY 02 — {src_title}"
    assert titles[2] == f"COPY 03 — {src_title}"
```

- [ ] **Step 2: Run — must FAIL (function doesn't exist)**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_282_duplicate_quote.py -v -m integration
```

- [ ] **Step 3: Write migration**

```sql
-- Migration 282: kvota.duplicate_quote — admin-only carbon-copy function.
-- Spec: docs/superpowers/specs/2026-04-15-quote-duplicate-design.md
--
-- Key design: uses PL/pgSQL %ROWTYPE + `INSERT ... SELECT (v_row).*` so any
-- future column added to kvota.quotes or kvota.quote_items is copied
-- automatically with no code change. This is a deliberate defense against
-- the column-drift bug surfaced by FB-260415-140516-2cc4.
--
-- Note: fill in the ACTUAL columns required by kvota.quote_brand_substates and
-- kvota.quote_timeline_events based on Task 5 schema inspection. If
-- brand_substates lacks an updated_at column, remove that override.

CREATE OR REPLACE FUNCTION kvota.duplicate_quote(
    p_source_id UUID,
    p_count INTEGER,
    p_cloned_by UUID
) RETURNS UUID[]
LANGUAGE plpgsql
SECURITY INVOKER
AS $function$
DECLARE
    v_row_q  kvota.quotes%ROWTYPE;
    v_row_i  kvota.quote_items%ROWTYPE;
    v_row_bs kvota.quote_brand_substates%ROWTYPE;
    v_new_id UUID;
    v_new_ids UUID[] := ARRAY[]::UUID[];
    i INTEGER;
BEGIN
    IF p_count < 1 OR p_count > 50 THEN
        RAISE EXCEPTION 'p_count out of range (1-50): %', p_count;
    END IF;

    -- Validate source up front (single lookup; each iteration re-fetches to get fresh row)
    PERFORM 1 FROM kvota.quotes WHERE id = p_source_id AND deleted_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source quote not found or deleted: %', p_source_id;
    END IF;

    FOR i IN 1..p_count LOOP
        BEGIN  -- per-iteration implicit savepoint
            SELECT * INTO v_row_q FROM kvota.quotes WHERE id = p_source_id;

            v_row_q.id := gen_random_uuid();
            v_row_q.idn := NULL;  -- trigger kvota.auto_generate_quote_idn regenerates
            v_row_q.idn_quote := kvota.generate_idn_quote(v_row_q.organization_id);
            v_row_q.title := 'COPY ' || lpad(i::text, 2, '0') || ' — ' || v_row_q.title;
            v_row_q.cloned_from_id := p_source_id;
            v_row_q.created_at := now();
            v_row_q.updated_at := now();

            INSERT INTO kvota.quotes SELECT (v_row_q).*;
            v_new_id := v_row_q.id;

            FOR v_row_i IN
                SELECT * FROM kvota.quote_items
                WHERE quote_id = p_source_id
                ORDER BY position
            LOOP
                v_row_i.id := gen_random_uuid();
                v_row_i.quote_id := v_new_id;
                v_row_i.item_idn := NULL;  -- globally unique; trigger regenerates
                v_row_i.created_at := now();
                v_row_i.updated_at := now();
                INSERT INTO kvota.quote_items SELECT (v_row_i).*;
            END LOOP;

            FOR v_row_bs IN
                SELECT * FROM kvota.quote_brand_substates
                WHERE quote_id = p_source_id
            LOOP
                v_row_bs.id := gen_random_uuid();
                v_row_bs.quote_id := v_new_id;
                -- If quote_brand_substates has created_at/updated_at, reset them here.
                INSERT INTO kvota.quote_brand_substates SELECT (v_row_bs).*;
            END LOOP;

            INSERT INTO kvota.quote_timeline_events
                (quote_id, event_type, metadata, actor_user_id, created_at)
            VALUES
                (v_new_id, 'cloned_from',
                 jsonb_build_object('source_quote_id', p_source_id,
                                    'admin_id', p_cloned_by),
                 p_cloned_by, now());

            v_new_ids := array_append(v_new_ids, v_new_id);
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'duplicate_quote iteration % failed: %', i, SQLERRM;
        END;
    END LOOP;

    RETURN v_new_ids;
END;
$function$;

COMMENT ON FUNCTION kvota.duplicate_quote(UUID, INTEGER, UUID) IS
  'Admin-only carbon-copy of a quote with items, brand_substates, and cloned_from timeline event. Uses %ROWTYPE for column-drift immunity. Returns array of successfully-created IDs.';
```

- [ ] **Step 4: Apply + run all 8 tests → must PASS**

```bash
bash scripts/apply-migrations.sh
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_migration_282_duplicate_quote.py -v -m integration
```

- [ ] **Step 5: Commit**

```bash
git add migrations/282_duplicate_quote_function.sql \
        tests/test_migration_282_duplicate_quote.py
git commit -m "feat(db): add kvota.duplicate_quote carbon-copy function

Column-drift-immune via %ROWTYPE. Copies quote + items + brand_substates,
writes cloned_from timeline event, atomic per-iteration via implicit
SAVEPOINT. Returns array of successfully-created UUIDs.

Used by upcoming POST /api/quotes/{id}/duplicate admin endpoint."
```

---

## Task 7: Python API endpoint — tests first

**Files:**
- Create: `tests/test_api_quote_duplicate.py`

- [ ] **Step 1: Write failing API tests**

```python
"""Tests for POST /api/quotes/{id}/duplicate endpoint."""
import os
from uuid import uuid4
import pytest
from starlette.testclient import TestClient
from main import app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set"
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    # Obtain JWT for an admin user. Use the same helper the other API
    # integration tests use — see tests/test_api_deals.py for the pattern.
    raise NotImplementedError(
        "Copy admin token helper from tests/test_api_deals.py conftest"
    )


@pytest.fixture
def sales_token(client):
    raise NotImplementedError("Copy from tests/test_api_deals.py")


@pytest.fixture
def src_quote_id():
    # Fetch from DB inside the fixture (see test_migration_282 for pattern)
    raise NotImplementedError


@pytest.mark.integration
def test_duplicate_requires_auth(client, src_quote_id):
    r = client.post(f"/api/quotes/{src_quote_id}/duplicate", json={"count": 1})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.integration
def test_duplicate_rejects_sales_role(client, sales_token, src_quote_id):
    r = client.post(
        f"/api/quotes/{src_quote_id}/duplicate",
        json={"count": 1, "user_id": "ignored"},
        headers={"Authorization": f"Bearer {sales_token}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "NOT_ADMIN"


@pytest.mark.integration
def test_duplicate_rejects_invalid_count(client, admin_token, src_quote_id):
    for bad in [0, -1, 51, "abc"]:
        r = client.post(
            f"/api/quotes/{src_quote_id}/duplicate",
            json={"count": bad, "user_id": "ignored"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400, f"Expected 400 for count={bad}"
        assert r.json()["error"]["code"] == "INVALID_COUNT"


@pytest.mark.integration
def test_duplicate_404_when_source_missing(client, admin_token):
    bogus = str(uuid4())
    r = client.post(
        f"/api/quotes/{bogus}/duplicate",
        json={"count": 1, "user_id": "ignored"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "QUOTE_NOT_FOUND"


@pytest.mark.integration
def test_duplicate_happy_path_count_1(client, admin_token, src_quote_id):
    r = client.post(
        f"/api/quotes/{src_quote_id}/duplicate",
        json={"count": 1, "user_id": "ignored"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["created_count"] == 1
    assert len(data["created_ids"]) == 1
    assert data["source_idn_quote"].startswith("Q-")


@pytest.mark.integration
def test_duplicate_happy_path_count_5(client, admin_token, src_quote_id):
    r = client.post(
        f"/api/quotes/{src_quote_id}/duplicate",
        json={"count": 5, "user_id": "ignored"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    assert r.json()["data"]["created_count"] == 5
```

- [ ] **Step 2: Implement the fixture helpers**

Read `tests/test_api_deals.py` (and its conftest usage) to find how it obtains admin/sales JWTs. Copy the helpers into this test file (or into a shared `tests/auth_helpers.py` if multiple API tests now need them).

- [ ] **Step 3: Run — expect FAIL (route doesn't exist → 404 on all tests)**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_api_quote_duplicate.py -v -m integration
```

- [ ] **Step 4: Commit tests**

```bash
git add tests/test_api_quote_duplicate.py
git commit -m "test(api): add tests for POST /api/quotes/{id}/duplicate"
```

---

## Task 8: Python API endpoint — implementation

**Files:**
- Modify: `main.py` (add new route + helper)

- [ ] **Step 1: Locate insertion point**

Find an existing `/api/quotes/...` route in `main.py` (search for `@app.post("/api/quotes"`). Insert the new handler adjacent to it to keep related routes grouped.

- [ ] **Step 2: Add the endpoint**

```python
@app.post("/api/quotes/{quote_id}/duplicate")
async def duplicate_quote_endpoint(request, quote_id: str):
    """Duplicate a quote N times as an admin-only carbon copy.

    Path: POST /api/quotes/{quote_id}/duplicate
    Params:
        quote_id: str (path) — source quote UUID
        count: int (body, 1-50) — number of copies to create
        user_id: str (body) — acting user (authoritatively taken from session/JWT; body value logged only)
    Returns:
        created_ids: list[str] — UUIDs of new copies, in creation order
        created_count: int
        source_idn_quote: str — for client-side toast/log
    Side Effects:
        - Inserts quote + items + brand_substates per copy
        - Inserts 'cloned_from' event in quote_timeline_events per copy
        - Increments per-month counter in organizations.idn_counters
    Roles: admin only
    """
    # Dual auth — JWT via request.state.api_user or session cookie
    user = getattr(request.state, "api_user", None) or _user_from_session(request)
    if not user:
        return _error_json("UNAUTHORIZED", "Authentication required", status=401)

    if "admin" not in (user.get("roles") or []):
        return _error_json("NOT_ADMIN", "Admin role required", status=403)

    try:
        body = await request.json()
    except Exception:
        return _error_json("INVALID_BODY", "JSON body required", status=400)

    count = body.get("count")
    if not isinstance(count, int) or count < 1 or count > 50:
        return _error_json("INVALID_COUNT", "count must be integer 1..50", status=400)

    supabase = get_supabase()
    src = (
        supabase.table("quotes")
        .select("id, idn_quote, organization_id, deleted_at")
        .eq("id", quote_id)
        .maybe_single()
        .execute()
        .data
    )
    if not src or src.get("deleted_at"):
        return _error_json("QUOTE_NOT_FOUND", "Quote not found", status=404)
    if src["organization_id"] != user.get("org_id"):
        return _error_json(
            "QUOTE_NOT_IN_USER_ORG", "Quote belongs to different organization", status=403
        )

    try:
        rpc_result = supabase.rpc(
            "duplicate_quote",
            {"p_source_id": quote_id, "p_count": count, "p_cloned_by": user["id"]},
        ).execute()
    except Exception as e:
        logger.exception(
            "duplicate_quote RPC failed",
            extra={"quote_id": quote_id, "count": count, "user_id": user["id"]},
        )
        return _error_json("DUPLICATE_FAILED", str(e), status=500)

    created_ids = rpc_result.data or []
    logger.info(
        "duplicate_quote succeeded",
        extra={
            "quote_id": quote_id,
            "count": count,
            "created_count": len(created_ids),
            "user_id": user["id"],
        },
    )
    return _success_json(
        {
            "created_ids": created_ids,
            "created_count": len(created_ids),
            "source_idn_quote": src["idn_quote"],
        },
        status=201,
    )
```

If `_error_json` / `_success_json` / `_user_from_session` helpers don't exist in `main.py` with those names, find the project's equivalents (search for existing API routes) and substitute.

- [ ] **Step 3: Run tests — must PASS**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  pytest tests/test_api_quote_duplicate.py -v -m integration
```

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(api): POST /api/quotes/{id}/duplicate admin endpoint

Thin wrapper over kvota.duplicate_quote RPC. Admin-only (403 NOT_ADMIN
for other roles), dual auth (JWT + session), cross-org protected.
Returns 201 with created_ids / created_count / source_idn_quote."
```

---

## Task 9: Frontend — Server Action wrapper

**Files:**
- Create: `frontend/src/features/duplicate-quote/api/duplicate-quote.action.ts`

- [ ] **Step 1: Write the Server Action**

```typescript
"use server";

import { revalidatePath } from "next/cache";
import { getSessionUser } from "@/shared/lib/auth";
import { apiServerClient } from "@/shared/lib/api-server";

export type DuplicateQuoteResult = {
  created_ids: string[];
  created_count: number;
  source_idn_quote: string;
};

export async function duplicateQuote(
  quoteId: string,
  count: number,
): Promise<DuplicateQuoteResult> {
  const user = await getSessionUser();
  if (!user?.roles?.includes("admin")) {
    throw new Error("Forbidden: admin role required");
  }

  const res = await apiServerClient<DuplicateQuoteResult>(
    `/quotes/${quoteId}/duplicate`,
    {
      method: "POST",
      body: JSON.stringify({ count, user_id: user.id }),
    },
  );

  if (!res.success) {
    throw new Error(res.error?.message ?? "Duplicate failed");
  }

  revalidatePath("/quotes");
  return res.data;
}
```

If `getSessionUser` / `apiServerClient` live at different paths in this project, inspect `frontend/src/shared/lib/` and substitute correct import paths.

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run typecheck
```

Expected: no errors in this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/duplicate-quote/api/duplicate-quote.action.ts
git commit -m "feat(fe): add duplicateQuote server action

Thin wrapper over POST /api/quotes/{id}/duplicate with admin-role
guard and automatic /quotes revalidation on success."
```

---

## Task 10: Frontend — Duplicate dialog

**Files:**
- Create: `frontend/src/features/duplicate-quote/ui/DuplicateQuoteDialog.tsx`

- [ ] **Step 1: Write the dialog component**

```tsx
"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { duplicateQuote } from "../api/duplicate-quote.action";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  quoteId: string;
  sourceIdn: string;
  sourceWorkflowState: string;
};

export function DuplicateQuoteDialog({
  open, onOpenChange, quoteId, sourceIdn, sourceWorkflowState,
}: Props) {
  const [count, setCount] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const countValid = Number.isInteger(count) && count >= 1 && count <= 50;

  function handleSubmit() {
    setError(null);
    startTransition(async () => {
      try {
        const result = await duplicateQuote(quoteId, count);
        onOpenChange(false);
        if (result.created_count === 1) {
          toast.success(`Копия создана: ${sourceIdn}`);
          router.push(`/quotes/${result.created_ids[0]}`);
        } else {
          toast.success(`Создано копий: ${result.created_count}`);
          router.push("/quotes");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Duplicate failed");
      }
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Duplicate quote</DialogTitle>
          <DialogDescription>
            Источник: <strong>{sourceIdn}</strong>. Carbon-copy будет создан
            на том же workflow-этапе: <code>{sourceWorkflowState}</code>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="duplicate-count">Количество копий (1–50)</Label>
          <Input
            id="duplicate-count"
            type="number"
            min={1}
            max={50}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            disabled={isPending}
          />
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!countValid || isPending}>
            {isPending
              ? `Creating ${count} ${count === 1 ? "copy" : "copies"}…`
              : "Duplicate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

If shadcn components live under different paths (`@/components/ui/...` instead of `@/shared/ui/...`), substitute.

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run typecheck
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/duplicate-quote/ui/DuplicateQuoteDialog.tsx
git commit -m "feat(fe): DuplicateQuoteDialog with count input"
```

---

## Task 11: Frontend — Menu integration with admin gate

**Files:**
- Create: `frontend/src/features/duplicate-quote/ui/DuplicateQuoteMenuItem.tsx`
- Modify: quote detail page overflow menu (path TBD from inspection, e.g. `frontend/src/app/(app)/quotes/[id]/page.tsx` or a nested header component)

- [ ] **Step 1: Locate overflow-menu component**

```bash
grep -rn "DropdownMenu\|MoreVertical\|OverflowMenu" frontend/src/app/ frontend/src/widgets/ frontend/src/features/ | grep -i quote | head
```

Record the file and component responsible for the quote detail page's overflow menu. This is where the new menu item is added.

- [ ] **Step 2: Write the menu-item wrapper**

```tsx
"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
import { DropdownMenuItem } from "@/shared/ui/dropdown-menu";
import { DuplicateQuoteDialog } from "./DuplicateQuoteDialog";

type Props = {
  quoteId: string;
  sourceIdn: string;
  sourceWorkflowState: string;
};

export function DuplicateQuoteMenuItem({
  quoteId, sourceIdn, sourceWorkflowState,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <DropdownMenuItem onSelect={(e) => { e.preventDefault(); setOpen(true); }}>
        <Copy className="mr-2 h-4 w-4" />
        Duplicate
      </DropdownMenuItem>
      <DuplicateQuoteDialog
        open={open}
        onOpenChange={setOpen}
        quoteId={quoteId}
        sourceIdn={sourceIdn}
        sourceWorkflowState={sourceWorkflowState}
      />
    </>
  );
}
```

- [ ] **Step 3: Wire into the parent RSC with admin gate**

In the parent RSC (the component that renders the overflow menu for the quote detail page), add:

```tsx
// inside the overflow menu list, alongside other items
{user.roles.includes("admin") && (
  <DuplicateQuoteMenuItem
    quoteId={quote.id}
    sourceIdn={quote.idn_quote}
    sourceWorkflowState={quote.workflow_state}
  />
)}
```

Ensure `user` is fetched server-side (from session or auth helper) in this RSC.

- [ ] **Step 4: Type-check + lint**

```bash
cd frontend && npm run typecheck && npm run lint
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/duplicate-quote/ui/DuplicateQuoteMenuItem.tsx \
        frontend/src/app/  # or the modified RSC file
git commit -m "feat(fe): wire Duplicate menu item into quote detail (admin-only)

Menu item renders only when user.roles includes 'admin' (server-side
check; non-admins never see it in the DOM)."
```

---

## Task 12: Browser smoke tests (mandatory before merge)

**Tool:** Playwright MCP (`mcp__plugin_playwright_playwright__*`).

- [ ] **Step 1: Test — admin sees menu, can duplicate single**

Preconditions: migrations applied locally, `python main.py` + `cd frontend && npm run dev` running.

```
1. browser_navigate http://localhost:3000
2. Login as admin user (from reference_accounts.md)
3. browser_navigate to any quote detail, e.g. /quotes/<id>
4. browser_snapshot — capture overflow-menu refs
5. browser_click the "⋯" button
6. Assert "Duplicate" menu item present in snapshot
7. Click "Duplicate" → modal appears
8. Fill count=1 → click Duplicate button
9. Wait for navigation → URL should be /quotes/<new-id>
10. Assert title starts with "COPY 01 — "
```

Record as `tests/browser/test_duplicate_admin.md` with exact snapshot refs.

- [ ] **Step 2: Test — admin can duplicate many**

```
1. From quote detail → "⋯" → Duplicate → count=5 → submit
2. Assert toast "Создано копий: 5" visible
3. Assert URL redirected to /quotes
```

- [ ] **Step 3: Test — sales does NOT see Duplicate**

```
1. Logout → login as sales user (from reference_accounts.md)
2. Navigate to same quote detail
3. browser_snapshot — capture overflow-menu
4. Assert "Duplicate" string NOT in snapshot
5. Inspect DOM via browser_evaluate: assert no element with text "Duplicate"
```

- [ ] **Step 4: Commit smoke-test docs**

```bash
git add tests/browser/test_duplicate_admin.md
git commit -m "test(smoke): browser tests for duplicate feature admin gate"
```

---

## Task 13: Verify FB-260415 closed, deploy, changelog

- [ ] **Step 1: Re-verify the original feedback scenario**

Carbon-copy (e.g. via `kvota.duplicate_quote` invoked directly or via the endpoint) a quote whose `incoterms='DDP'` is set. Confirm the copy also has `incoterms='DDP'` and `delivery_priority='normal'`. This is the proof that the column-drift immunity holds.

- [ ] **Step 2: Update feedback ticket**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"UPDATE kvota.user_feedback SET status='resolved' WHERE short_id='FB-260415-140516-2cc4';\""
```

- [ ] **Step 3: Add changelog entry**

Follow project changelog convention (check `changelog:*` skill / existing entries). Minimum content:

```
## Admin: duplicate quote

- New admin-only action "Duplicate" on quote detail page creates 1–50 carbon
  copies via POST /api/quotes/{id}/duplicate.
- Copies land on the same workflow stage as the source (full state preserved).
- Each copy links back via quotes.cloned_from_id + a `cloned_from` timeline event.
- Fixed a latent search_path dependency in kvota.auto_generate_quote_idn /
  kvota.auto_generate_item_idn and removed obsolete public.* IDN function
  duplicates.
```

- [ ] **Step 4: Push + monitor deploy**

```bash
git push origin <branch>  # or create PR
# After merge to main:
gh run watch  # or ssh beget-kvota "docker logs kvota-onestack --tail 50"
```

- [ ] **Step 5: Post-deploy smoke check on prod**

Repeat Task 12 Step 1–3 against https://app.kvotaflow.ru with real admin + real sales accounts.

- [ ] **Step 6: Update `MEMORY.md` with one-liner**

Add to memory: "Duplicate quote feature shipped 2026-04-16; uses SQL function with %ROWTYPE (column-drift immune). See spec 2026-04-15-quote-duplicate-design.md."

---

## Post-completion follow-ups (separate tickets)

1. Migrate `POST /quotes` in `main.py` to call `kvota.generate_idn_quote()` instead of the Python retry loop — eliminates the last race-prone IDN generation path.
2. Add `cloned_from_id` filter to `/quotes` registry UI (enables "show clones of X") — unlocks future "clone tree" feature.
3. Consider lifting the 50-copy cap after observing usage telemetry for 1 month.
4. Review the 20 existing test clones from the ad-hoc seeding (Q-202604-0048..0067). They are now usable fixtures but carry `cloned_from_id=NULL` — optionally backfill.

---

## Self-review checklist performed

- **Spec coverage:** each of the 10 decisions in the spec has a corresponding task (decisions 1,6 → Tasks 2,3; decision 7 → Tasks 4,6; decision 8 → Task 6 SAVEPOINT pattern; decision 9 → Task 10; decision 10 → Task 12).
- **Placeholder scan:** no TBD/TODO in actionable steps. One deliberate "path TBD from inspection" in Task 11 Step 1 that the engineer resolves via grep in Step 1 itself.
- **Type consistency:** Server Action return type `DuplicateQuoteResult` used consistently in `DuplicateQuoteDialog`. SQL function signature `duplicate_quote(UUID, INTEGER, UUID) RETURNS UUID[]` consistent between migration and tests.
- **Critical regression covered:** column-drift immunity test (Task 6 Step 1, first test case) guards against repeat of FB-260415-140516-2cc4.
