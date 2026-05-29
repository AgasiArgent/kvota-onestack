-- Migration 333: Codify the live (lisa-era) exchange_rates schema under
--                onestack source control.
--
-- The live kvota.exchange_rates table was created and maintained by the
-- DECOMMISSIONED legacy "lisa" backend, NOT by onestack migrations. The
-- onestack migration that referenced this table (132_create_exchange_rates_
-- table.sql) describes a DIFFERENT, stale/defunct shape (rate_date / currency
-- / rate_to_rub) that does NOT match production. Migration 132 is left
-- untouched for history; this migration is the canonical definition.
--
-- Do NOT delete or modify migration 132.
--
-- Idempotent + ordering-safe:
--   * LIVE DB  — table already has this (lisa-era) shape incl. `from_currency`,
--                so the reconciliation DROP below is a NO-OP and CREATE TABLE
--                IF NOT EXISTS is a NO-OP. Nothing is touched, no data lost.
--   * FRESH DB rebuilt from migrations — migration 132 runs first (numeric
--                order) and creates the defunct shape as an EMPTY table. The
--                reconciliation DROP removes that empty legacy table so the
--                correct shape can be created. Without this, 132 would win the
--                CREATE race and the FX writer (which has no rate_date) could
--                not insert.

-- Reconcile a legacy migration-132 shaped table (identified by the ABSENCE of
-- the `from_currency` column). Safe: never matches the live table (which has
-- from_currency); only ever drops the empty legacy table on a fresh rebuild.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kvota' AND table_name = 'exchange_rates'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota' AND table_name = 'exchange_rates'
          AND column_name = 'from_currency'
    ) THEN
        DROP TABLE kvota.exchange_rates;
    END IF;
END $$;

-- Canonical shape — created only if absent (live DB already has it).
CREATE TABLE IF NOT EXISTS kvota.exchange_rates (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency VARCHAR(3)    NOT NULL,
    to_currency   VARCHAR(3)    NOT NULL,
    rate          NUMERIC(10,6) NOT NULL CONSTRAINT exchange_rates_rate_positive CHECK (rate > 0),
    source        VARCHAR(50)   DEFAULT 'cbr',
    fetched_at    TIMESTAMP     NOT NULL,
    created_at    TIMESTAMP     DEFAULT now()
);

-- UNIQUE constraint backing the cron upsert's ON CONFLICT target.
CREATE UNIQUE INDEX IF NOT EXISTS idx_exchange_rates_unique
    ON kvota.exchange_rates (from_currency, to_currency, fetched_at);

-- Lookup index: latest rate for a currency pair.
CREATE INDEX IF NOT EXISTS idx_exchange_rates_lookup
    ON kvota.exchange_rates (from_currency, to_currency, fetched_at DESC);

-- Cleanup index: prune old rows by fetched_at.
CREATE INDEX IF NOT EXISTS idx_exchange_rates_cleanup
    ON kvota.exchange_rates (fetched_at);

-- created_at index.
CREATE INDEX IF NOT EXISTS idx_exchange_rates_created_at
    ON kvota.exchange_rates (created_at);

COMMENT ON TABLE kvota.exchange_rates IS
    'FX rates (X->RUB, source cbr). Codified from the live lisa-era schema in migration 333; supersedes the stale/defunct migration 132. Written by POST /api/cron/refresh-exchange-rates.';
