-- Migration 300: Add poison-pill counter to tnved_rates so cron_revalidate_rates
-- can back off chronically-failing (tnved_code, country) pairs instead of
-- retrying them every week forever (PR #83 review fix M9).
--
-- Verify next free migration number before applying:
--   ls migrations/29[0-9]*.sql migrations/30*.sql
-- (Expected: 299 is the most recent customs-phase-1 migration; 300 should be free.)
--
-- Idempotent: re-applying is a no-op (ADD COLUMN IF NOT EXISTS,
-- CREATE INDEX IF NOT EXISTS, ON CONFLICT DO NOTHING).

ALTER TABLE kvota.tnved_rates
    ADD COLUMN IF NOT EXISTS revalidate_failure_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS revalidate_failed_at TIMESTAMPTZ;

COMMENT ON COLUMN kvota.tnved_rates.revalidate_failure_count IS
    'Count of consecutive cron revalidation failures. Reset to 0 on success. '
    'Cron skips pairs where this is >= 3 AND revalidate_failed_at is within '
    'the last 7 days (poison-pill backoff).';

COMMENT ON COLUMN kvota.tnved_rates.revalidate_failed_at IS
    'Timestamp of last cron revalidation failure. NULL when never failed or '
    'after a successful revalidation reset.';

-- Partial index for fast poison-pill query during cron run setup.
CREATE INDEX IF NOT EXISTS idx_rates_poison_pill
    ON kvota.tnved_rates(revalidate_failure_count DESC, revalidate_failed_at DESC)
    WHERE revalidate_failure_count >= 3;

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (300, '300_tnved_rates_revalidate_failure', now())
ON CONFLICT (id) DO NOTHING;
