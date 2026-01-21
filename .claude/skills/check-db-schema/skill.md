# Check DB Schema Before Coding

**Purpose:** Always verify actual database column names before writing code that references them.

**Trigger phrases:**
- Before adding new database columns
- Before referencing table fields in queries
- When seeing "column does not exist" errors
- Before writing migrations

---

## 🔴 CRITICAL RULE

**NEVER assume field names exist.** Always check the actual schema first.

**Bad:**
```python
# ❌ Assuming field names
SELECT purchase_price_rub, weight_kg, customs_duty_percent
```

**Good:**
```python
# ✅ Check schema first, then use actual names
SELECT purchase_price_original, weight_in_kg, customs_duty
```

---

## Quick Schema Check Commands

### Check all columns in a table
```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='kvota' AND table_name='quote_items'
ORDER BY ordinal_position;
\""
```

### Search for columns by pattern
```bash
# Find all columns with 'price' in name
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='kvota' AND table_name='quote_items'
  AND column_name LIKE '%price%'
ORDER BY column_name;
\""
```

### Check specific column exists
```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
SELECT EXISTS (
  SELECT 1 FROM information_schema.columns
  WHERE table_schema='kvota'
    AND table_name='quote_items'
    AND column_name='customs_duty'
);
\""
```

---

## Naming Conventions (for NEW fields only)

**Existing fields keep their names.** Use these patterns for new fields:

### 1. Units of Measurement
Pattern: `fieldname_unit`

Examples:
- `weight_kg` or `weight_in_kg` (both acceptable)
- `volume_m3`
- `price_rub` (converted price in RUB)
- `time_days` or `production_time_days`
- `distance_km`

### 2. Prices and Currency
Pattern: `price_original` + `price_currency`

Examples:
- `purchase_price_original` + `purchase_currency` (actual supplier price + EUR/USD/CNY)
- `sale_price_original` + `sale_currency`
- `price_rub` (converted to RUB for calculations)

**Note:** Don't store prices in multiple currency columns. Store original + currency code, then convert via API on demand.

### 3. Workflow Status/Completion
Pattern: `stage_status`, `stage_completed_at`, `stage_completed_by`

Examples:
- `procurement_status` + `procurement_completed_at` + `procurement_completed_by`
- `logistics_completed_at`
- `customs_completed_at`

### 4. Foreign Keys
Pattern: `entity_id`

Examples:
- `quote_id`
- `supplier_id`
- `customer_id`
- `invoice_id`

### 5. Percentages
Pattern: `field` (NO _percent suffix)

Examples:
- `customs_duty` (not customs_duty_percent)
- `markup` (not markup_percent)
- `vat` (not vat_percent)

### 6. Extra Costs
Pattern: `field_extra` (NO _cost suffix)

Examples:
- `customs_extra` (not customs_extra_cost)
- `logistics_extra` (not logistics_extra_cost)

### 7. Boolean Flags
Pattern: `is_something` or `has_something`

Examples:
- `is_active`
- `is_completed`
- `has_documents`

---

## Workflow: Adding New Database Field

1. **Design the field name** using conventions above
2. **Check if similar fields exist:**
   ```bash
   ssh beget-kvota "docker exec supabase-db psql ... LIKE '%keyword%'"
   ```
3. **Create migration file** `migrations/XXX_description.sql`
4. **Apply migration** via `scripts/apply-migrations.sh`
5. **Verify column exists** before writing code
6. **Update code** to use new field

---

## Common Errors from Naming Mismatches

### Error: "column quote_items.customs_duty_percent does not exist"
**Cause:** Code used old/assumed name instead of checking schema

**Solution:**
1. Check actual schema: `SELECT column_name ... LIKE '%customs%'`
2. Found: `customs_duty`, `customs_extra`, `customs_code`
3. Update code: Replace all occurrences via `sed` or manual editing

### Error: "column quote_items.purchase_price_rub does not exist"
**Cause:** Refactoring changed field structure (split into price_original + currency)

**Solution:**
1. Check current schema
2. Update queries to use `purchase_price_original`, `purchase_currency`
3. Add conversion logic if RUB amount needed

---

## Schema Documentation Location

**Always up-to-date:** Query `information_schema.columns` directly

**Reference docs (may lag):**
- `DATABASE_TABLES.md` - Manual documentation (check date)
- `DATABASE_GUIDE.md` - Usage patterns
- `.claude/skills/db-kvota/skill.md` - Database operations

**Golden rule:** Trust the database, not the docs.

---

## Real-World Example: Customs Page Cascade

**Problem:** 4 sequential "column does not exist" errors

**Root cause:** Code used assumed field names without checking schema

**Errors fixed:**
1. `purchase_price_rub` → `purchase_price_original` + `purchase_currency`
2. `weight_kg` → `weight_in_kg`
3. Missing `volume_m3` → Added via migration 123
4. `customs_duty_percent`/`customs_extra_cost` → `customs_duty`/`customs_extra`

**Prevention:** Run schema check BEFORE writing SELECT queries

---

## When to Create Migration vs Fix Code

**Create migration IF:**
- Field makes logical sense and will be used in future
- User says "давай у них тоже будет поле" or "проще миграцию сделать"
- Removing field breaks existing functionality

**Fix code IF:**
- Field was a typo or wrong assumption
- Field duplicates existing data
- Field belongs at different table level (item vs invoice vs quote)

---

## Quick Reference Commands

```bash
# List all tables in kvota schema
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
SELECT table_name FROM information_schema.tables
WHERE table_schema='kvota' ORDER BY table_name;
\""

# Count columns in a table
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
SELECT COUNT(*) as column_count
FROM information_schema.columns
WHERE table_schema='kvota' AND table_name='quote_items';
\""

# Show all NOT NULL columns
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='kvota' AND table_name='quote_items'
  AND is_nullable='NO'
ORDER BY column_name;
\""
```

---

**Last updated:** 2026-01-21
**Schema:** kvota
**Container:** supabase-db (via beget-kvota host)
