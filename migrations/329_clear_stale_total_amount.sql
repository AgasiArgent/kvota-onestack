-- Migration 329: clear stale `kvota.quotes.total_amount` after calc deletion.
--
-- Background:
--   `quote_calculation_results` is CASCADE-deleted when `quote_items` change,
--   but `quotes.total_amount` is denormalized on `kvota.quotes` and lingers
--   from older successful calculations. Symptom: the «Validation Excel»
--   download produced a 1.6 MB workbook full of zeros — testers reported
--   it as "пустой".
--
--   PR #235 (2026-05-25) added a defensive gate in api/quotes.py
--   (`/api/quotes/{id}/export/validation`) that checks for calc data on the
--   items themselves, NOT the stale `total_amount` aggregate. That fixed the
--   symptom. This migration fixes the root cause:
--
--     1. ONE-TIME cleanup: NULL out `total_amount` on quotes whose calc
--        results no longer exist (~4 rows on prod as of 2026-05-25).
--
--     2. ON-GOING trigger: when the LAST `quote_calculation_results` row
--        for a quote is deleted, NULL its `total_amount` automatically.
--
-- Prerequisite:
--   The legacy `NOT NULL` constraint on `total_amount` (default 0) cannot
--   carry the "no calc present" semantic. We drop the constraint here so
--   NULL means "no calculation" and any positive number means "calc done".
--   No existing reader assumes non-null:
--     - frontend approvals/finance/customers use `quote.total_amount ?? 0`
--     - api/deals.py uses `float(total_amount) if total_amount else 0.0`
--     - api/quotes.py only WRITES total_amount on successful calc
--   The defensive gate in PR #235 (row-count based) is unaffected; this is
--   belt-and-suspenders.
--
-- Safety:
--   - Wrapped in BEGIN/COMMIT so partial application can't leave a half-state
--   - Idempotent: DROP TRIGGER IF EXISTS + CREATE OR REPLACE FUNCTION
--   - Post-condition assertion at the end fails the migration if cleanup
--     left any stale rows behind (a future schema drift could otherwise
--     silently bypass `apply-migrations.sh` per the m318 lesson).

BEGIN;

-- 1. Drop the NOT NULL constraint so NULL can carry "no calc present".
ALTER TABLE kvota.quotes ALTER COLUMN total_amount DROP NOT NULL;

-- Also drop the now-misleading default of 0 (a fresh row with no calc
-- should be NULL, not 0).
ALTER TABLE kvota.quotes ALTER COLUMN total_amount DROP DEFAULT;

-- 2. One-time cleanup: NULL out stale total_amount for quotes without
--    any calc result row.
UPDATE kvota.quotes q
SET total_amount = NULL
WHERE total_amount IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM kvota.quote_calculation_results qcr
    WHERE qcr.quote_id = q.id
  );

-- 3. Trigger: AFTER DELETE on quote_calculation_results, if no remaining
--    rows for that quote, NULL the quote's total_amount.
CREATE OR REPLACE FUNCTION kvota.clear_quote_total_amount_when_no_calc()
RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM kvota.quote_calculation_results
    WHERE quote_id = OLD.quote_id
  ) THEN
    UPDATE kvota.quotes
    SET total_amount = NULL
    WHERE id = OLD.quote_id
      AND total_amount IS NOT NULL;
  END IF;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS clear_quote_total_amount_trg
  ON kvota.quote_calculation_results;

CREATE TRIGGER clear_quote_total_amount_trg
AFTER DELETE ON kvota.quote_calculation_results
FOR EACH ROW
EXECUTE FUNCTION kvota.clear_quote_total_amount_when_no_calc();

COMMENT ON FUNCTION kvota.clear_quote_total_amount_when_no_calc() IS
  'Belt-and-suspenders for PR #235: NULL out quotes.total_amount when its '
  'last quote_calculation_results row is deleted, so the denormalised total '
  'never lingers as a stale aggregate.';

-- 4. Post-condition: cleanup must have left zero stale rows.
DO $$
DECLARE
  stale_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO stale_count
  FROM kvota.quotes q
  WHERE q.total_amount IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM kvota.quote_calculation_results qcr
      WHERE qcr.quote_id = q.id
    );

  IF stale_count > 0 THEN
    RAISE EXCEPTION
      'Migration 329 post-condition failed: % quotes still have stale total_amount',
      stale_count;
  END IF;
END $$;

COMMIT;
