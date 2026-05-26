-- Migration 332: Add `included_in_calc` to quote_items for МОП-controlled КПП selection.
-- Testing 2 row 90: МОП can deselect individual quote_items so they are excluded
-- from the calculation engine while remaining visible in the composition picker.
--
-- Default TRUE → existing rows behave as before (included by default).
-- build_calculation_inputs() (services/calculation_helpers.py) filters out rows
-- with included_in_calc=FALSE before passing to the locked calculation engine.
--
-- BEGIN/COMMIT wrap per feedback_apply_migrations_silent_partial (м318 incident
-- 2026-05-21): scripts/apply-migrations.sh only checks the LAST statement's
-- result, so multi-statement migrations must be transactional to avoid silent
-- partial state on prod.

BEGIN;

ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS included_in_calc BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN kvota.quote_items.included_in_calc IS
    'МОП-controlled flag — when FALSE the item is skipped by build_calculation_inputs() '
    'and excluded from totals. TRUE by default. Persists across reloads. '
    'Distinct from is_unavailable (system-side N/A) and import_banned (customs auto-block).';

COMMIT;
