-- Migration 297: Allow nullable / zero values on invoice_cargo_places
-- Why: post-creation editor lets procurement add empty cargo place rows
-- and fill them piecemeal as the supplier replies. Original constraints
-- (NOT NULL + CHECK > 0) reject inserts of partially-known places.
-- Same pattern as migration 235 for invoices.total_weight_kg.
-- Date: 2026-04-29

SET search_path TO kvota, public;

-- Drop the existing CHECK constraints (their auto-generated names follow
-- the pg_dump pattern <table>_<column>_check).
ALTER TABLE kvota.invoice_cargo_places
  DROP CONSTRAINT IF EXISTS invoice_cargo_places_weight_kg_check;
ALTER TABLE kvota.invoice_cargo_places
  DROP CONSTRAINT IF EXISTS invoice_cargo_places_length_mm_check;
ALTER TABLE kvota.invoice_cargo_places
  DROP CONSTRAINT IF EXISTS invoice_cargo_places_width_mm_check;
ALTER TABLE kvota.invoice_cargo_places
  DROP CONSTRAINT IF EXISTS invoice_cargo_places_height_mm_check;

-- Make the four dimension columns nullable.
ALTER TABLE kvota.invoice_cargo_places
  ALTER COLUMN weight_kg DROP NOT NULL,
  ALTER COLUMN length_mm DROP NOT NULL,
  ALTER COLUMN width_mm DROP NOT NULL,
  ALTER COLUMN height_mm DROP NOT NULL;

-- Re-add CHECK as IS NULL OR > 0 — partial values are fine, garbage is not.
ALTER TABLE kvota.invoice_cargo_places
  ADD CONSTRAINT invoice_cargo_places_weight_kg_check
    CHECK (weight_kg IS NULL OR weight_kg > 0),
  ADD CONSTRAINT invoice_cargo_places_length_mm_check
    CHECK (length_mm IS NULL OR length_mm > 0),
  ADD CONSTRAINT invoice_cargo_places_width_mm_check
    CHECK (width_mm IS NULL OR width_mm > 0),
  ADD CONSTRAINT invoice_cargo_places_height_mm_check
    CHECK (height_mm IS NULL OR height_mm > 0);

COMMENT ON COLUMN kvota.invoice_cargo_places.weight_kg IS
  'Weight in kg. NULL = unknown at creation, will be filled by procurement.';
COMMENT ON COLUMN kvota.invoice_cargo_places.length_mm IS
  'Length in mm. NULL = unknown at creation.';
COMMENT ON COLUMN kvota.invoice_cargo_places.width_mm IS
  'Width in mm. NULL = unknown at creation.';
COMMENT ON COLUMN kvota.invoice_cargo_places.height_mm IS
  'Height in mm. NULL = unknown at creation.';
