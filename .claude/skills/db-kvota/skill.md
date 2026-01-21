# Skill: db-kvota

Database helper for OneStack - ensures correct schema usage and provides quick diagnostics.

## Activation

**Trigger keywords:**
- "база данных", "БД", "database"
- "supabase", "postgres", "postgresql"
- "migration", "миграция"
- "schema", "схема"
- "таблица", "table"
- "RLS", "policy", "политика"
- "ошибка БД", "database error"
- "SQL", "запрос", "query"

**Auto-activate when:**
- User mentions database operations
- Database errors occur
- Working with migrations
- Querying or modifying tables
- Debugging RLS policies

## Critical Information

### ⚠️ ALWAYS use kvota schema

```sql
-- ❌ WRONG
SELECT * FROM quotes;

-- ✅ CORRECT
SELECT * FROM kvota.quotes;
```

**Why kvota?**
- `public` schema: 130+ tables (n8n, CRM, OAuth, other projects)
- `kvota` schema: 51 tables (OneStack only)
- Clean isolation

### ⚠️ Use r.slug, NOT r.code

```sql
-- ❌ WRONG (column doesn't exist)
WHERE r.code = 'admin'

-- ✅ CORRECT
WHERE r.slug = 'admin'
```

**Available role slugs:**
- `admin`, `finance`, `procurement`, `quote_controller`
- `logistics`, `sales`, `spec_controller`
- `ceo`, `cfo`, `top_manager`, `head_of_procurement`

## Quick Commands

### Connect to database

```bash
# Connect via Docker (easiest)
ssh beget-kvota
docker exec -it supabase-db psql -U postgres -d postgres

# Set schema
SET search_path TO kvota;
```

### Check table exists

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT schemaname FROM pg_tables WHERE tablename = 'TABLE_NAME';\""
```

### List tables in kvota

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT tablename FROM pg_tables WHERE schemaname = 'kvota' ORDER BY tablename;\""
```

### Check RLS policies

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT * FROM pg_policies WHERE schemaname = 'kvota' AND tablename = 'TABLE_NAME';\""
```

### Describe table structure

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"\\d kvota.TABLE_NAME\""
```

## Common Errors & Solutions

### Error: "relation does not exist"

**Cause:** Table not in kvota schema or wrong schema prefix

**Solution:**
```bash
# Check which schema contains the table
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT schemaname FROM pg_tables WHERE tablename = 'your_table';\""

# Always prefix with kvota
SELECT * FROM kvota.your_table;
```

### Error: "column r.code does not exist"

**Cause:** Using r.code instead of r.slug in RLS policies

**Solution:**
```sql
-- Fix the policy - replace r.code with r.slug
WHERE r.slug IN ('admin', 'finance')
```

### Error: RLS policy blocks access

**Cause:** User doesn't have required role or organization access

**Solution:**
```bash
# Check user roles
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT ur.user_id, r.slug, ur.organization_id
      FROM kvota.user_roles ur
      JOIN kvota.roles r ON r.id = ur.role_id
      WHERE ur.user_id = 'USER_UUID';\""
```

### Error: Function not found

**Cause:** Function not in kvota schema

**Solution:**
```bash
# Find the function
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT routine_schema, routine_name
      FROM information_schema.routines
      WHERE routine_name LIKE '%function_name%';\""

# Call with schema prefix
SELECT kvota.function_name();
```

## Applying Migrations (AUTOMATED)

### Quick Command (Use This!)

```bash
# Apply all pending migrations
ssh beget-kvota "cd /root/onestack && bash scripts/migrate.sh"
```

This will:
- ✅ Create `kvota.migrations` table if needed
- ✅ Check which migrations are already applied
- ✅ Apply only pending migrations
- ✅ Track applied migrations automatically
- ✅ Stop on error and rollback

### Other Commands

```bash
# Check migration status
ssh beget-kvota "cd /root/onestack && bash scripts/migrate.sh status"

# List all migrations
ssh beget-kvota "cd /root/onestack && bash scripts/migrate.sh list"
```

### How It Works

**Files:**
- `scripts/migrate.py` - Python migration runner
- `scripts/migrate.sh` - Bash wrapper (auto-installs dependencies)
- `migrations/*.sql` - Migration files (numbered: `120_name.sql`)
- `kvota.migrations` table - Tracks applied migrations

**Migration Naming:**
- Format: `{number}_{description}.sql`
- Example: `120_add_delivery_method_to_quotes.sql`
- Numbering: Sequential (001, 002, ..., 120, 121, ...)

### Creating New Migrations

1. **Create file:**
   ```bash
   # Find next number
   ls migrations/*.sql | tail -1  # See last number

   # Create new migration
   touch migrations/121_your_description.sql
   ```

2. **Write SQL (ALWAYS use kvota schema):**
   ```sql
   -- Migration: Description
   -- Created: YYYY-MM-DD

   SET search_path TO kvota;

   ALTER TABLE kvota.your_table ADD COLUMN your_column TEXT;
   ```

3. **Apply migration:**
   ```bash
   ssh beget-kvota "cd /root/onestack && bash scripts/migrate.sh"
   ```

### Before Every Migration

**Checklist:**
1. ✅ Create backup (optional but recommended)
2. ✅ Use `kvota` schema prefix in SQL
3. ✅ Use `r.slug` not `r.code` in RLS
4. ✅ Check foreign keys reference `kvota.table`
5. ✅ Test SQL syntax if complex

**Create backup (optional):**
```bash
ssh beget-kvota "cd /root/onestack && \
  docker exec supabase-db pg_dump -U postgres -d postgres \
  > backup_$(date +%Y%m%d_%H%M%S).sql"
```

## Code Configuration

### Backend (FastAPI)

**File:** `services/database.py`

```python
from supabase import create_client

supabase = create_client(
    url=os.getenv("SUPABASE_URL"),
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    options={"schema": "kvota"}  # ⚠️ REQUIRED
)
```

### Frontend (Next.js)

**File:** `lib/supabase.ts` or similar

```typescript
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  {
    db: { schema: 'kvota' }  // ⚠️ REQUIRED
  }
)
```

## Table Categories (51 tables total)

**Organizations** (6): organizations, organization_members, organization_invitations, etc.
**Quotes** (11): quotes, quote_items, quote_versions, quote_calculation_*, etc.
**Procurement** (12): suppliers, supplier_invoices, buyer_companies, bank_accounts, etc.
**Customers** (4): customers, customer_contacts, customer_contracts, etc.
**Plan-Fact** (7): plan_fact_items, plan_fact_products, etc.
**Specifications** (2): specifications, specification_exports
**Other** (9): roles, user_roles, approvals, deals, notifications, etc.

**Full list:** `DATABASE_TABLES.md`

## Files to Check

When troubleshooting database issues, read these files:

- **`DATABASE_GUIDE.md`** - Detailed guide (for humans)
- **`DATABASE_TABLES.md`** - All table schemas
- **`PRODUCTION_TABLES.md`** - Production state
- **`migrations/`** - Migration files
- **`MIGRATION_GUIDE.md`** - Migration instructions

## Proactive Checks

When you work with database:

1. **Always verify schema:**
   - Check if using `kvota.` prefix
   - Warn if missing schema prefix

2. **Check RLS policies:**
   - Verify using `r.slug` not `r.code`
   - Confirm role slugs are valid

3. **Validate migrations:**
   - Ensure kvota schema prefix
   - Check foreign key references

4. **Before queries:**
   - Confirm table exists in kvota
   - Check RLS policies won't block

## Example: Safe Query Pattern

```python
# Bad - might query wrong schema
result = supabase.table("quotes").select("*").execute()

# Good - explicit check first
# 1. Verify client configured for kvota schema
# 2. Then query
result = supabase.table("quotes").select("*").execute()

# Better - in SQL, always prefix
result = supabase.rpc("kvota.my_function", {})
```

## Monitoring & Diagnostics

### Check schema distribution

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT schemaname, COUNT(*) FROM pg_tables
      WHERE schemaname IN ('kvota', 'public')
      GROUP BY schemaname;\""
```

### Check active connections

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c \"SELECT count(*), state FROM pg_stat_activity GROUP BY state;\""
```

### Check logs

```bash
ssh beget-kvota "docker logs kvota-onestack --tail 50"
```

## Success Criteria

You're doing it right when:

- ✅ All queries use `kvota.table_name` format
- ✅ All RLS policies use `r.slug` not `r.code`
- ✅ Migrations include schema prefix
- ✅ Client configured with `schema: "kvota"`
- ✅ No "relation does not exist" errors
- ✅ No "column r.code does not exist" errors

---

**Last updated:** 2026-01-20
**Schema:** kvota (51 tables)
**Location:** Supabase PostgreSQL on VPS (supabase-db container)
