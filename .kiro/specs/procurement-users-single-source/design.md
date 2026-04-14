# Design — Procurement Users Single Source of Truth

## Query Pattern

### Python (Supabase-py) — "quotes where user has item assignment"

```python
# BEFORE
quotes = supabase.table("quotes") \
    .select("...") \
    .eq("organization_id", org_id) \
    .contains("assigned_procurement_users", [user_id]) \
    .execute()

# AFTER
quotes = supabase.table("quotes") \
    .select("*, quote_items!inner(id)") \
    .eq("organization_id", org_id) \
    .eq("quote_items.assigned_procurement_user", user_id) \
    .execute()
# Result: quote rows where ≥1 item matches. PostgREST deduplicates quote rows
# because the embedded filter produces an INNER JOIN, but the SELECT projects
# the parent row only once per parent (if we don't select item fields in main list).
```

**Critical detail:** When using `!inner` filter, PostgREST returns ONE row per parent regardless of how many items match, because we're selecting parent fields. If we accidentally project item fields (e.g., `select("*, quote_items!inner(*)")`), we'd get one row per item. Verify projection carefully per call site.

### Python — "get distinct procurement users for a quote" (for timer, telegram)

```python
# BEFORE
quote = supabase.table("quotes").select("assigned_procurement_users").eq("id", quote_id).single().execute()
user_ids = quote.data.get("assigned_procurement_users") or []

# AFTER
items = supabase.table("quote_items") \
    .select("assigned_procurement_user") \
    .eq("quote_id", quote_id) \
    .not_.is_("assigned_procurement_user", "null") \
    .execute()
user_ids = list({i["assigned_procurement_user"] for i in (items.data or [])})
```

### Python — "is user assigned to this quote?" (permission check)

```python
# BEFORE
return user_id in (quote.get("assigned_procurement_users") or [])

# AFTER
result = supabase.table("quote_items") \
    .select("id") \
    .eq("quote_id", quote_id) \
    .eq("assigned_procurement_user", user_id) \
    .limit(1) \
    .execute()
return bool(result.data)
```

### TypeScript (Supabase-js) — frontend filter

```typescript
// BEFORE (messages/queries.ts:95)
.or(`assigned_procurement_users.cs.{${user.id}},assigned_logistics_user.eq.${user.id},assigned_customs_user.eq.${user.id}`)

// AFTER
// Need to split into two queries or use a DB RPC, because Supabase client can't
// combine .or() with embedded filter. Two-step:
// 1. Fetch quote_ids where user is assigned at item level
// 2. Add those quote_ids to the .or() chain
const { data: itemAssignedQuoteIds } = await supabase
  .from("quote_items")
  .select("quote_id")
  .eq("assigned_procurement_user", user.id);
const quoteIds = [...new Set((itemAssignedQuoteIds ?? []).map(r => r.quote_id))];
// then: .or(`id.in.(${quoteIds.join(",")}),assigned_logistics_user.eq.${user.id},...`)
```

For simple single-column filter (`customs-info-block.tsx`) use embedded filter directly:

```typescript
// BEFORE
.select("created_by, assigned_procurement_users, assigned_customs_user")
// then: const procurementUsers = quote.assigned_procurement_users as ...

// AFTER
.select("created_by, assigned_customs_user, quote_items(assigned_procurement_user)")
// then: const procurementUsers = [...new Set(quote.quote_items
//   .map(i => i.assigned_procurement_user).filter(Boolean))];
```

## Migration 276

```sql
BEGIN;

-- Drop index first to avoid orphan
DROP INDEX IF EXISTS kvota.idx_quotes_assigned_procurement_users;

-- Drop the column
ALTER TABLE kvota.quotes DROP COLUMN IF EXISTS assigned_procurement_users;

COMMIT;
```

Simple, reversible (re-adding the column with empty default would work, but data cannot be restored from the array since item-level is already the truth).

## Rollout Order (deploy-safe)

```
1. Code change (readers + writers removed) → push → GitHub Actions deploys to prod
2. Verify deploy completed: ssh beget-kvota "docker logs kvota-onestack --tail 20"
3. Apply migration 276 on prod
4. Regenerate types: cd frontend && npm run db:types → commit type changes
5. Browser-test on prod as procurement user
```

Why this order: if migration runs BEFORE code reaches prod, old code (still reading the column) hits "column does not exist" for the duration of deploy. Deploy → migrate is safer.

**Alternative:** migrate first with column rename to `_deprecated_assigned_procurement_users`, deploy code, then drop after verification. Rejected for complexity — the single-commit atomic approach is simpler and the deploy window is short.

## Test Strategy

1. **Unit/integration test** (`tests/test_quotes_access.py` — new file or extend existing):
   - Seed: create quote with no `assigned_procurement_users`, assign 1 item to `user_A`, verify `user_A` sees the quote in "my quotes" query.
   - Seed: create quote, assign items to `user_A` and `user_B`, verify both appear in procurement users list derived from items.
   - Seed: create quote with items, reassign an item from `user_A` to `user_B`, verify `user_A` no longer appears as assigned, `user_B` does.

2. **Prod browser-test** (after deploy):
   - Login as procurement user known to have item-level assignments (query DB to pick one)
   - Navigate to quotes list → verify their assigned quotes appear
   - Navigate to messages (if message filter depends on this) → verify filter works

## Concerns

- **Duplicate rows from !inner join:** Verify empirically per call site. If parent row comes back N times for N matching items, apply `SELECT DISTINCT` equivalent or dedupe in application.
- **Embedded filter + .or():** Supabase-js doesn't combine these well. `messages/queries.ts` needs two-step (fetch quote_ids, then use `.or().in()`).
- **Permission check in hot path:** `main.py:16990` is in a route handler. Adding a subquery per request is acceptable at current scale (~hundreds of requests/hour), but monitor if the endpoint becomes chattier.
