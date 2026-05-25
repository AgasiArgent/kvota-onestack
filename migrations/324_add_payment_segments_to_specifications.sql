-- Migration 324: Multi-segment client payment terms on specifications
-- Testing 2 row 46 (РОП + МОП): «На данный момент, мы предоставляем любые условия
-- оплаты - 30/70, 70/30, 50/50 и тд. Также есть комбинированные 20/30/50 и тд.
-- На каждый сегмент указать сроки оплаты в календарных днях. Важно выделить -
-- Срок оплаты Аванса Клиентом, Срок оплаты Клиентом после отгрузки Товара»
--
-- Spec: .kiro/specs/payment-segments-row-46/
--
-- Adds 7 new columns to kvota.specifications matching calc engine эталон
-- PaymentTerms (10 fields; anchor 1 reuses existing advance_percent_from_client
-- + payment_deferral_days, anchor 5 % auto-computed as 100 - sum(1..4)).
--
-- Anchor map:
--   1. Аванс клиента          — advance_percent_from_client + payment_deferral_days (EXISTING)
--   2. При погрузке           — payment_on_loading_pct + payment_on_loading_days (NEW)
--   3. При прибытии в страну  — payment_on_country_arrival_pct + payment_on_country_arrival_days (NEW)
--   4. При таможне            — payment_on_customs_clearance_pct + payment_on_customs_clearance_days (NEW)
--   5. После получения        — % derived; payment_on_receiving_days (NEW)
--
-- Backfill rationale (design.md Risk #1):
--   The existing `client_payment_term_after_upd` column was the legacy source
--   for `time_to_advance_on_receiving` engine input. Semantics differ (УПД ≠
--   приёмка), so it stays as-is for ERPS reports. The new
--   `payment_on_receiving_days` becomes the canonical engine source; existing
--   rows are backfilled from `client_payment_term_after_upd` so engine output
--   is byte-identical before/after migration (golden master backward-compat).
--
-- Atomicity: wrapped in BEGIN/COMMIT (memory notes: m309 + m318 incidents
-- documented partial-state hazards on multi-statement migrations).

BEGIN;

-- Anchor 2: При погрузке -----------------------------------------------------
ALTER TABLE kvota.specifications
    ADD COLUMN IF NOT EXISTS payment_on_loading_pct NUMERIC(5,2) NOT NULL DEFAULT 0;

ALTER TABLE kvota.specifications
    ADD COLUMN IF NOT EXISTS payment_on_loading_days INTEGER NOT NULL DEFAULT 0;

-- Anchor 3: При прибытии в страну --------------------------------------------
ALTER TABLE kvota.specifications
    ADD COLUMN IF NOT EXISTS payment_on_country_arrival_pct NUMERIC(5,2) NOT NULL DEFAULT 0;

ALTER TABLE kvota.specifications
    ADD COLUMN IF NOT EXISTS payment_on_country_arrival_days INTEGER NOT NULL DEFAULT 0;

-- Anchor 4: При таможне ------------------------------------------------------
ALTER TABLE kvota.specifications
    ADD COLUMN IF NOT EXISTS payment_on_customs_clearance_pct NUMERIC(5,2) NOT NULL DEFAULT 0;

ALTER TABLE kvota.specifications
    ADD COLUMN IF NOT EXISTS payment_on_customs_clearance_days INTEGER NOT NULL DEFAULT 0;

-- Anchor 5 days: После получения (% is derived as 100 - Σ(1..4)) -------------
ALTER TABLE kvota.specifications
    ADD COLUMN IF NOT EXISTS payment_on_receiving_days INTEGER NOT NULL DEFAULT 0;

-- CHECK constraints: pct ranges 0..100 ---------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_on_loading_pct_range'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_on_loading_pct_range
            CHECK (payment_on_loading_pct >= 0 AND payment_on_loading_pct <= 100);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_on_country_arrival_pct_range'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_on_country_arrival_pct_range
            CHECK (payment_on_country_arrival_pct >= 0 AND payment_on_country_arrival_pct <= 100);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_on_customs_clearance_pct_range'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_on_customs_clearance_pct_range
            CHECK (payment_on_customs_clearance_pct >= 0 AND payment_on_customs_clearance_pct <= 100);
    END IF;
END $$;

-- CHECK constraints: days >= 0 -----------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_on_loading_days_nonneg'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_on_loading_days_nonneg
            CHECK (payment_on_loading_days >= 0);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_on_country_arrival_days_nonneg'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_on_country_arrival_days_nonneg
            CHECK (payment_on_country_arrival_days >= 0);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_on_customs_clearance_days_nonneg'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_on_customs_clearance_days_nonneg
            CHECK (payment_on_customs_clearance_days >= 0);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_on_receiving_days_nonneg'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_on_receiving_days_nonneg
            CHECK (payment_on_receiving_days >= 0);
    END IF;
END $$;

-- Composite CHECK: sum of explicit anchor % must not exceed 100 --------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'kvota.specifications'::regclass
          AND conname = 'spec_payment_pct_sum_max'
    ) THEN
        ALTER TABLE kvota.specifications
            ADD CONSTRAINT spec_payment_pct_sum_max
            CHECK (
                COALESCE(advance_percent_from_client, 0)
                + payment_on_loading_pct
                + payment_on_country_arrival_pct
                + payment_on_customs_clearance_pct
                <= 100
            );
    END IF;
END $$;

-- Backfill payment_on_receiving_days from legacy client_payment_term_after_upd
-- so existing specs preserve their effective time_to_advance_on_receiving
-- engine input (golden-master backward compatibility, see design.md Risk #1).
UPDATE kvota.specifications
SET payment_on_receiving_days = COALESCE(client_payment_term_after_upd, 0)
WHERE client_payment_term_after_upd IS NOT NULL
  AND payment_on_receiving_days = 0;

-- Column comments ------------------------------------------------------------
COMMENT ON COLUMN kvota.specifications.payment_on_loading_pct IS
    'Multi-segment payment %: anchor 2 (При погрузке). 0-100. Combined with '
    'advance_percent_from_client + payment_on_country_arrival_pct + '
    'payment_on_customs_clearance_pct must be <= 100 (composite CHECK). '
    'Maps to calc engine PaymentTerms.advance_on_loading. Migration 324.';

COMMENT ON COLUMN kvota.specifications.payment_on_loading_days IS
    'Days to settle the «При погрузке» segment after загрузка event. '
    'Maps to calc engine PaymentTerms.time_to_advance_loading. Migration 324.';

COMMENT ON COLUMN kvota.specifications.payment_on_country_arrival_pct IS
    'Multi-segment payment %: anchor 3 (При прибытии в страну). 0-100. '
    'Subject to composite sum constraint. Maps to calc engine '
    'PaymentTerms.advance_on_going_to_country_destination. Migration 324.';

COMMENT ON COLUMN kvota.specifications.payment_on_country_arrival_days IS
    'Days to settle the «При прибытии в страну» segment. Maps to calc engine '
    'PaymentTerms.time_to_advance_going_to_country_destination. Migration 324.';

COMMENT ON COLUMN kvota.specifications.payment_on_customs_clearance_pct IS
    'Multi-segment payment %: anchor 4 (При таможне). 0-100. Subject to '
    'composite sum constraint. Maps to calc engine '
    'PaymentTerms.advance_on_customs_clearance. Migration 324.';

COMMENT ON COLUMN kvota.specifications.payment_on_customs_clearance_days IS
    'Days to settle the «При таможне» segment. Maps to calc engine '
    'PaymentTerms.time_to_advance_on_customs_clearance. Migration 324.';

COMMENT ON COLUMN kvota.specifications.payment_on_receiving_days IS
    'Days to settle the «После получения» (final) segment. Maps to calc engine '
    'PaymentTerms.time_to_advance_on_receiving. NOTE: semantically distinct '
    'from client_payment_term_after_upd (УПД signing) — the legacy column '
    'stays for ERPS reports. Backfilled from client_payment_term_after_upd on '
    'migration 324; new specs initialise to 0.';

COMMIT;
