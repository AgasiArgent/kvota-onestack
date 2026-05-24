-- Migration 322: Add per-row currency to certificates + expenses
-- Testing 2 row 73 — tester request: «Дать возможность изменения валюты и в
-- сертификации, и в расходах»
--
-- Current state:
--   kvota.quote_certificates.cost_rub — NUMERIC(14, 2) NOT NULL DEFAULT 0
--   (stores both cert and expense rows via is_custom_expense discriminator;
--    migration 306).
--
-- Change:
--   1. Rename cost_rub → cost_original (the numeric amount in whatever
--      currency the user picked). Backfill is automatic: existing rows keep
--      their value verbatim.
--   2. Add cost_currency text NOT NULL DEFAULT 'RUB'. Existing rows backfill
--      to 'RUB' (matches the pre-migration semantics that the stored amount
--      was always RUB).
--
-- Idempotency: guarded via information_schema lookups so re-running the
-- migration after partial application is a no-op.
--
-- Atomicity: wrapped in BEGIN/COMMIT (memory notes: m309 + m318 incidents
-- documented partial-state hazards on multi-statement migrations).

BEGIN;

-- Rename cost_rub → cost_original on quote_certificates ----------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota'
          AND table_name = 'quote_certificates'
          AND column_name = 'cost_rub'
    ) THEN
        ALTER TABLE kvota.quote_certificates
            RENAME COLUMN cost_rub TO cost_original;
    END IF;
END $$;

-- Rename the CHECK constraint to match the new column name -------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'quote_certificates_cost_rub_nonneg'
    ) THEN
        ALTER TABLE kvota.quote_certificates
            RENAME CONSTRAINT quote_certificates_cost_rub_nonneg
            TO quote_certificates_cost_original_nonneg;
    END IF;
END $$;

-- Add cost_currency on quote_certificates ------------------------------------
ALTER TABLE kvota.quote_certificates
    ADD COLUMN IF NOT EXISTS cost_currency TEXT NOT NULL DEFAULT 'RUB';

COMMENT ON COLUMN kvota.quote_certificates.cost_original IS
    'Certificate / custom-expense cost in the currency specified by cost_currency. '
    'Renamed from cost_rub in migration 322 (Testing 2 row 73). Calc engine '
    'converts to RUB via services.currency_service.convert_amount when consuming.';

COMMENT ON COLUMN kvota.quote_certificates.cost_currency IS
    'ISO 4217 code (RUB/USD/EUR/CNY/...) for cost_original. Defaults to RUB so '
    'pre-migration rows retain their semantics. Frontend defaults new rows to '
    'the parent quote currency.';

COMMIT;
