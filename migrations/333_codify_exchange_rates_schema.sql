-- Migration 333: Codify the live (lisa-era) exchange_rates schema under
--                onestack source control.
--
-- The live kvota.exchange_rates table was created and maintained by the
-- DECOMMISSIONED legacy "lisa" backend, NOT by onestack migrations. The
-- onestack migration that referenced this table (132_create_exchange_rates_
-- table.sql) describes a DIFFERENT, stale/defunct shape (rate_date / currency
-- / rate_to_rub) that does NOT match what is actually in production. That
-- migration is left untouched for history — this migration supersedes it as
-- the canonical definition of the table's real shape.
--
-- Do NOT delete or modify migration 132.
--
-- This migration is EXPAND-ONLY and FULLY IDEMPOTENT: when applied to the
-- live DB (where the table already exists) it is a no-op. It never DROPs or
-- recreates anything. The FX cron writer (POST /api/cron/refresh-exchange-
-- rates) and the on-demand fallback (services.currency_service) both rely on
-- exactly this shape.

-- Table — created only if absent (live DB already has it).
CREATE TABLE IF NOT EXISTS kvota.exchange_rates (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency VARCHAR(3)    NOT NULL,
    to_currency   VARCHAR(3)    NOT NULL,
    rate          NUMERIC(10,6) NOT NULL CHECK (rate > 0),
    source        VARCHAR(50)   DEFAULT 'cbr',
    fetched_at    TIMESTAMP     NOT NULL,
    created_at    TIMESTAMP     DEFAULT now()
);

-- Columns — guarded ADDs so a partially-migrated DB converges to the live
-- shape without error. No-op when the column already exists.
ALTER TABLE kvota.exchange_rates ADD COLUMN IF NOT EXISTS from_currency VARCHAR(3)    NOT NULL;
ALTER TABLE kvota.exchange_rates ADD COLUMN IF NOT EXISTS to_currency   VARCHAR(3)    NOT NULL;
ALTER TABLE kvota.exchange_rates ADD COLUMN IF NOT EXISTS rate          NUMERIC(10,6) NOT NULL;
ALTER TABLE kvota.exchange_rates ADD COLUMN IF NOT EXISTS source        VARCHAR(50)   DEFAULT 'cbr';
ALTER TABLE kvota.exchange_rates ADD COLUMN IF NOT EXISTS fetched_at    TIMESTAMP     NOT NULL;
ALTER TABLE kvota.exchange_rates ADD COLUMN IF NOT EXISTS created_at    TIMESTAMP     DEFAULT now();

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
