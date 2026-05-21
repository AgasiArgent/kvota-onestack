-- Migration 319: recover from partial application of migration 318.
--
-- Background:
--   m318 tried to drop `kvota.quotes.total_amount_quote` and
--   `kvota.quote_items.supplier_advance_percent` (both orphan duplicates).
--   On prod, the second succeeded but the first was rejected:
--     ERROR: cannot drop column total_amount_quote of table kvota.quotes
--     DETAIL: view kvota.active_quotes depends on column total_amount_quote
--   psql's per-statement implicit transactions + no ON_ERROR_STOP meant the
--   second statement still ran and the script reported "✅ Success".
--
-- Fix:
--   active_quotes was created in m280 as `SELECT *` but Postgres froze the
--   column list at definition time, so CREATE OR REPLACE cannot shrink it.
--   We DROP the view, drop the column, and recreate the view from
--   the current column set. All wrapped in a single transaction.
--
-- Safety:
--   - active_quotes is referenced only by tests (test_soft_delete_read_audit,
--     test_migration_280) — production code reads kvota.quotes directly.
--   - The view definition + grants + comment mirror m280 exactly so the
--     contract for those tests is preserved.
--
-- Defensive: assert the column is gone after the operation, so a future
-- partial failure cannot quietly slip past the apply-migrations script.

BEGIN;

DROP VIEW IF EXISTS kvota.active_quotes;

ALTER TABLE kvota.quotes DROP COLUMN IF EXISTS total_amount_quote;

CREATE VIEW kvota.active_quotes
  WITH (security_invoker = true) AS
  SELECT * FROM kvota.quotes WHERE deleted_at IS NULL;

COMMENT ON VIEW kvota.active_quotes IS
  'Soft-delete-filtered view. Use this instead of kvota.quotes for NEW readers '
  'that never want soft-deleted rows. Existing direct reads must still add '
  '".is_(''deleted_at'', None)" until the read-audit converts them. '
  'security_invoker=true — caller RLS applies.';

GRANT SELECT ON kvota.active_quotes TO authenticated, service_role;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'kvota'
      AND table_name   = 'quotes'
      AND column_name  = 'total_amount_quote'
  ) THEN
    RAISE EXCEPTION
      'Migration 319 post-condition failed: kvota.quotes.total_amount_quote still exists';
  END IF;
END $$;

COMMIT;
