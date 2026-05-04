-- Migration 305: per-item Manual duty-rate override (Phase A Req 4, Task 10).
--
-- Adds two columns to kvota.quote_items so the customs-item dialog's Manual
-- mode can round-trip — a UI-level boolean flag plus a JSONB payload
-- compatible with `services.alta_client.Rate` (3-slot model). Reading from
-- these columns is preferred over re-deriving from `customs_duty` /
-- `customs_duty_per_kg` because they preserve sign + currency info that
-- the legacy two-column representation cannot carry.
--
-- Columns are NULLable — Auto mode and unedited rows carry NULL. The
-- calc-engine adapter still reads `customs_duty` / `customs_duty_per_kg`
-- as before; the new payload is informational/UI-only until Phase B.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS.
SET search_path TO kvota;

ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS customs_manual_override BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS customs_manual_rate_payload JSONB;

COMMENT ON COLUMN kvota.quote_items.customs_manual_override IS
    'Phase A Req 4: TRUE when customs-specialist toggled Manual mode in the '
    'per-item dialog. Drives UI re-hydration; calc-engine continues to read '
    'customs_duty / customs_duty_per_kg.';

COMMENT ON COLUMN kvota.quote_items.customs_manual_rate_payload IS
    'Phase A Req 4: JSONB clone of Alta Rate dataclass (3-slot model) — '
    'stored when customs-specialist enters a combined / specific rate that '
    'the legacy customs_duty + customs_duty_per_kg pair cannot represent. '
    'Shape: {duty_rate_type, value_1_number, value_1_unit, value_1_currency, '
    'value_2_number, value_2_unit, value_2_currency, sign_1}.';
