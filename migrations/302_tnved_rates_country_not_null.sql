-- Migration 302: Make country_or_areal NOT NULL with sentinel to fix UNIQUE.
--
-- Discovered during prod verification of migration 301: 84 cache rows for
-- HS=7326909807 × Китай when the parser emits 14. Root cause — Postgres
-- UNIQUE treats NULLs as DISTINCT, so the migration-301 constraint
--   (tnved_code, payment_type, country_or_areal, valid_from, ..., category_code)
-- never matched on the base-rate path (country_or_areal IS NULL). Each
-- resolve_rate_variants call (one per payment_type) re-INSERTed instead
-- of UPDATEing, accumulating dupes proportional to the call count.
--
-- This bug was latent in migration 298 too — Phase 1 just never made
-- enough calls per (code, country) pair to surface it.
--
-- Fix: replace NULL with sentinel '__base__'. CHECK constraint extended
-- to allow this token. Existing rows TRUNCATEd (already stale because
-- of the duplicates).

-- =============================================================================
-- Part 1: clear stale duplicate rows
-- =============================================================================

TRUNCATE TABLE kvota.tnved_rates CASCADE;

-- =============================================================================
-- Part 2: drop CHECK that blocks the sentinel
-- =============================================================================

ALTER TABLE kvota.tnved_rates
    DROP CONSTRAINT IF EXISTS tnved_rates_country_or_areal_format_check;

-- =============================================================================
-- Part 3: NOT NULL + DEFAULT
-- =============================================================================

ALTER TABLE kvota.tnved_rates
    ALTER COLUMN country_or_areal SET DEFAULT '__base__';

-- After cache is empty (TRUNCATE above) we can safely flip NOT NULL.
ALTER TABLE kvota.tnved_rates
    ALTER COLUMN country_or_areal SET NOT NULL;

-- =============================================================================
-- Part 4: re-add the CHECK that now also accepts the sentinel
-- =============================================================================

ALTER TABLE kvota.tnved_rates
    ADD CONSTRAINT tnved_rates_country_or_areal_format_check
        CHECK (
            country_or_areal = '__base__'
            OR country_or_areal LIKE 'C:%'
            OR country_or_areal LIKE 'A:%'
        );

COMMENT ON COLUMN kvota.tnved_rates.country_or_areal IS
    'Lookup priority key (NOT NULL since migration 302 — __base__ is the '
    'sentinel for "applies to all countries", replacing previous NULL which '
    'broke uq_tnved_rates_v2 due to Postgres NULLS DISTINCT semantics).';
