-- Migration 299: Add UNIQUE constraint on tnved_non_tariff_measures
-- to prevent duplicate accumulation on repeated /api/customs/non-tariff-measures
-- calls. Customs Phase 1 review fix M3.
--
-- Background: api/customs.py:non_tariff_measures_handler used to .insert()
-- the freshly-fetched Alta measures every call, so the same (tnved_code,
-- country_or_areal, measure_type, name, valid_from) row would accumulate
-- across UI clicks. Migration 298 created the table without a UNIQUE
-- constraint, so the upsert had no on_conflict target. This migration
-- (a) dedupes whatever has already piled up, then (b) adds the constraint
-- so future upserts target it.
--
-- NULL handling: country_or_areal and valid_from are nullable. Postgres 15+
-- supports `UNIQUE NULLS NOT DISTINCT` which treats NULLs as equal — this
-- is the correct semantic here (two measures that both omit valid_from
-- should still be considered the same row). Verify the deployed Postgres
-- version supports it before applying:
--     SHOW server_version;
-- If < 15, this migration will need to be reworked to use a partial unique
-- index per nullable-column combination instead.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_tnved_non_tariff_measures'
          AND conrelid = 'kvota.tnved_non_tariff_measures'::regclass
    ) THEN
        -- Dedupe existing rows before adding the constraint. We keep the
        -- most-recent (highest id, which for gen_random_uuid() is *not*
        -- monotonic — but the dedupe is one-off and any survivor is fine
        -- since the rows are identical on the natural key).
        DELETE FROM kvota.tnved_non_tariff_measures a
        USING kvota.tnved_non_tariff_measures b
        WHERE a.id < b.id
          AND a.tnved_code IS NOT DISTINCT FROM b.tnved_code
          AND a.country_or_areal IS NOT DISTINCT FROM b.country_or_areal
          AND a.measure_type IS NOT DISTINCT FROM b.measure_type
          AND a.name IS NOT DISTINCT FROM b.name
          AND a.valid_from IS NOT DISTINCT FROM b.valid_from;

        ALTER TABLE kvota.tnved_non_tariff_measures
            ADD CONSTRAINT uq_tnved_non_tariff_measures
            UNIQUE NULLS NOT DISTINCT
                (tnved_code, country_or_areal, measure_type, name, valid_from);
    END IF;
END $$;

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (299, '299_tnved_measures_unique', now())
ON CONFLICT (id) DO NOTHING;
