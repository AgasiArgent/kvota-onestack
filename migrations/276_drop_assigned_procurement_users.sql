-- Migration 276: Drop legacy kvota.quotes.assigned_procurement_users column.
--
-- Single source of truth for "which procurement users are involved in a quote"
-- is now kvota.quote_items.assigned_procurement_user. The quote-level array had
-- drifted in production (18/44 quotes with empty array despite items assigned).
-- All readers have been rewritten to query quote_items directly; all writers
-- have been removed. This migration drops the now-unused column + its GIN index.
--
-- Rollback: re-add the column (data cannot be reconstructed from items in a
-- way that matches the historical array, but items ARE the truth, so this is
-- intentional — no data loss).

BEGIN;

-- Drop the GIN index first to avoid leaving an orphan.
DROP INDEX IF EXISTS kvota.idx_quotes_assigned_procurement_users;

-- Drop the legacy column.
ALTER TABLE kvota.quotes
    DROP COLUMN IF EXISTS assigned_procurement_users;

COMMIT;
