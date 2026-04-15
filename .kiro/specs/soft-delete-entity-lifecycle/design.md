# Design: Cascade Soft-Delete for Quote → Spec → Deal

## Architecture Choice: Option C

**Soft-delete at entity-lifecycle level, not at every table.**

Three entities (`quotes`, `specifications`, `deals`) carry `deleted_at`. Children (`quote_items`, `plan_fact_items`, `logistics_stages`, `currency_invoices`, `quote_comments`, etc.) do not — they are hidden transitively via the parent filter.

### Why not the alternatives

| Option | Rejected because |
|--------|------------------|
| A — `deleted_at` on all 30+ tables | Schema bloat; 30+ places to forget filter; many children have zero independent lifecycle |
| B — only `quotes.deleted_at`, joins everywhere | Cross-layer joins in every query reading deals/specs; can't "cancel a deal without deleting quote"; hard to enforce via RLS |
| C — selected | Matches domain model ("entity at three stages"); minimum schema delta; natural fit for existing FK CASCADE on children during hard-purge |

## Data Model

### Migration 279 (schema)

```sql
BEGIN;

ALTER TABLE kvota.specifications
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES auth.users(id);

ALTER TABLE kvota.deals
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES auth.users(id);

ALTER TABLE kvota.quotes
  ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES auth.users(id);

-- Partial indexes: 95%+ queries filter deleted_at IS NULL; partial indexes are ~3x
-- smaller than full and auto-selected by planner when the filter is present.
CREATE INDEX IF NOT EXISTS idx_quotes_active_customer
  ON kvota.quotes(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_quotes_active_created
  ON kvota.quotes(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_specs_active_quote
  ON kvota.specifications(quote_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_deals_active_spec
  ON kvota.deals(specification_id) WHERE deleted_at IS NULL;

COMMIT;
```

### Migration 279 (functions)

```sql
-- Atomic cascade soft-delete. Caller: API endpoint passes authenticated user_id as p_actor_id.
CREATE OR REPLACE FUNCTION kvota.soft_delete_quote(p_quote_id uuid, p_actor_id uuid)
RETURNS TABLE(quote_affected int, spec_affected int, deal_affected int)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = kvota, public
AS $$
DECLARE
  v_now timestamptz := now();
  v_quote int := 0;
  v_spec int := 0;
  v_deal int := 0;
BEGIN
  -- Deal first (RESTRICT FK upstream would otherwise block hard-purge later)
  WITH updated AS (
    UPDATE kvota.deals d
       SET deleted_at = v_now, deleted_by = p_actor_id
      FROM kvota.specifications s
     WHERE s.id = d.specification_id
       AND s.quote_id = p_quote_id
       AND d.deleted_at IS NULL
     RETURNING d.id
  )
  SELECT count(*)::int INTO v_deal FROM updated;

  -- Then spec
  WITH updated AS (
    UPDATE kvota.specifications
       SET deleted_at = v_now, deleted_by = p_actor_id
     WHERE quote_id = p_quote_id AND deleted_at IS NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_spec FROM updated;

  -- Then quote itself
  WITH updated AS (
    UPDATE kvota.quotes
       SET deleted_at = v_now, deleted_by = p_actor_id
     WHERE id = p_quote_id AND deleted_at IS NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_quote FROM updated;

  RETURN QUERY SELECT v_quote, v_spec, v_deal;
END;
$$;

COMMENT ON FUNCTION kvota.soft_delete_quote IS
  'Atomically soft-delete a quote and its linked spec + deal. Idempotent. '
  'Returns counts of rows affected per level. Transaction boundary: caller''s txn.';

CREATE OR REPLACE FUNCTION kvota.restore_quote(p_quote_id uuid)
RETURNS TABLE(quote_affected int, spec_affected int, deal_affected int)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = kvota, public
AS $$
DECLARE
  v_quote int := 0;
  v_spec int := 0;
  v_deal int := 0;
BEGIN
  -- Reverse order: quote first (no FK check upstream now), then spec, then deal
  WITH updated AS (
    UPDATE kvota.quotes
       SET deleted_at = NULL, deleted_by = NULL
     WHERE id = p_quote_id AND deleted_at IS NOT NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_quote FROM updated;

  WITH updated AS (
    UPDATE kvota.specifications
       SET deleted_at = NULL, deleted_by = NULL
     WHERE quote_id = p_quote_id AND deleted_at IS NOT NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_spec FROM updated;

  WITH updated AS (
    UPDATE kvota.deals d
       SET deleted_at = NULL, deleted_by = NULL
      FROM kvota.specifications s
     WHERE s.id = d.specification_id
       AND s.quote_id = p_quote_id
       AND d.deleted_at IS NOT NULL
     RETURNING d.id
  )
  SELECT count(*)::int INTO v_deal FROM updated;

  RETURN QUERY SELECT v_quote, v_spec, v_deal;
END;
$$;

COMMENT ON FUNCTION kvota.restore_quote IS
  'Reverse a soft-delete: clear deleted_at/deleted_by on quote, spec, and deal. Idempotent.';

GRANT EXECUTE ON FUNCTION kvota.soft_delete_quote(uuid, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION kvota.restore_quote(uuid) TO authenticated;
```

### Migration 280 (views) — follows in subtask 3

```sql
CREATE OR REPLACE VIEW kvota.active_quotes AS
  SELECT * FROM kvota.quotes WHERE deleted_at IS NULL;
CREATE OR REPLACE VIEW kvota.active_specs AS
  SELECT * FROM kvota.specifications WHERE deleted_at IS NULL;
CREATE OR REPLACE VIEW kvota.active_deals AS
  SELECT * FROM kvota.deals WHERE deleted_at IS NULL;
-- Add security_invoker = true so RLS policies on base tables apply
ALTER VIEW kvota.active_quotes SET (security_invoker = true);
ALTER VIEW kvota.active_specs SET (security_invoker = true);
ALTER VIEW kvota.active_deals SET (security_invoker = true);
```

## API Layer

```python
# api/soft_delete.py (new file)
from starlette.requests import Request
from fastapi import HTTPException
from services.database import get_supabase

async def soft_delete_quote_endpoint(request: Request):
    """Soft-delete a quote with its linked spec and deal.

    Path: POST /api/quotes/{quote_id}/soft-delete
    Params (path): quote_id: str (UUID)
    Returns:
        quote_affected: int — 0 if already deleted, 1 if newly deleted
        spec_affected: int — 0 if no spec or already deleted, 1 if newly
        deal_affected: int — same
    Side Effects:
        Sets deleted_at + deleted_by on affected rows.
        Reversible via /api/quotes/{id}/restore within 365 days.
    Roles: admin ONLY — not sales/head_of_sales/top_manager. Soft-delete
        is an administrative operation (affects cross-role reporting, can
        orphan in-progress procurement work) so the authority is centralized.
    Errors: 401 (no auth), 403 (not admin), 404 (quote not found)
    """
    quote_id = request.path_params["quote_id"]
    user = getattr(request.state, "api_user", None) or require_login(request.session)
    # role check + ownership check here
    sb = get_supabase()
    result = sb.rpc("soft_delete_quote", {
        "p_quote_id": quote_id,
        "p_actor_id": str(user.id),
    }).execute()
    return {"success": True, "data": result.data[0]}
```

Wired into FastHTML app via routing registered alongside existing `/api/*` handlers.

## Delete Flow (end-to-end)

```
┌─────────────────────────────────────────────────────────────────┐
│ User clicks "Удалить" on /quotes/{id}                           │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────┐
│ <Dialog> confirms: "Удалить квоту + спец + дил"│
└────────────────────────────┬───────────────────┘
                             ▼
     fetch POST /api/quotes/{id}/soft-delete + JWT
                             ▼
┌─────────────────────────────────────────────────┐
│ Python: auth → rpc("soft_delete_quote", ids)    │
└────────────────────────────┬────────────────────┘
                             ▼
      PL/pgSQL atomic UPDATE on deal → spec → quote
                             ▼
           200 + {quote_affected, spec_affected, deal_affected}
                             ▼
┌─────────────────────────────────────────────────┐
│ Next.js: toast + revalidate /quotes             │
│ List hides the row (filter: deleted_at IS NULL) │
└─────────────────────────────────────────────────┘
```

## Read-side Invariant

After subtask 3 lands, the following grep SHOULD return zero matches in application code:

```bash
rg 'FROM kvota\.(quotes|specifications|deals)' --type py --type ts \
   | grep -v 'deleted_at IS NULL' \
   | grep -v 'active_(quotes|specs|deals)' \
   | grep -v 'trash'   # explicit trash readers are allowed
```

Any exception must be justified in a comment above the query.

## Retention + Hard-Purge (subtask 6)

```python
# scripts/purge_old_deleted_quotes.py
#
# Runs daily on beget-kvota. Hard-deletes quotes soft-deleted >365 days ago.
# Downstream CASCADEs clean up quote_items, specifications (CASCADE), deals
# (CASCADE from spec), plan_fact_items (CASCADE from deal), logistics_stages,
# currency_invoices, etc.
#
# Usage:
#   python scripts/purge_old_deleted_quotes.py          # real run
#   python scripts/purge_old_deleted_quotes.py --dry-run
```

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Readers still leak soft-deleted rows after migration lands | Subtask 3 is a hard gate — grep audit must be clean before closing |
| RLS on view breaks existing Next.js queries | `security_invoker = true` means base-table RLS applies; existing policies continue to work |
| `SECURITY DEFINER` function bypasses RLS intent | Add explicit role check inside function using `auth.role()` or `auth.uid()`; reject if caller has no grant |
| Hard-purge race: user restores at T-365d while cron fires at T | Cron adds 1-day buffer (`< now() - interval '366 days'`) OR uses `FOR UPDATE SKIP LOCKED` to avoid purging a row being restored |
| Migration number collision | Confirmed latest = 278 today; claim 279 immediately, block further migrations during today's session |
| FK null-safety regression (session 9 incident) | Any new PostgREST FK joins use `table!fk_name(...)` explicit form; regression tests from `tests/test_fk_null_safety.py` still run in CI |

## Test Strategy

**Unit (DB functions):** `tests/test_soft_delete_db.py`
- Empty quote (no spec, no deal) → (1, 0, 0)
- Quote with spec, no deal → (1, 1, 0)
- Full lifecycle quote → (1, 1, 1)
- Double soft-delete → (0, 0, 0) on second call
- Restore after soft-delete → (1, 1, 1)
- Restore on never-deleted → (0, 0, 0)
- Restore on partially-deleted (deleted quote but not spec) → (1, 0, 0)

**API (integration):** `tests/test_soft_delete_api.py`
- Happy path: POST → 200 + correct counts
- Missing JWT → 401
- Wrong role → 403
- Non-existent quote → 404
- Deleted then restored → row back in active list
- Double-POST soft-delete → both return 200, second has zero counts

**View + RLS:** `tests/test_active_views.py`
- Select from `active_quotes` after soft-delete → row invisible
- Direct `FROM kvota.quotes` with RLS filter → row invisible
- Admin's RLS bypass still shows deleted rows for Trash page

**UI (browser):** covered in Phase 5e manifests per subtask (4, 5)

## Acceptance

- Existing 33 ВАЛЕНТА ФАРМ soft-deleted quotes invisible in Next.js list after subtask 3
- New quote + deal → Delete button → disappears → Trash → Restore → reappears
- CI green (pytest + vitest + CI on PR)
- Production smoke (Phase 7b) passes
