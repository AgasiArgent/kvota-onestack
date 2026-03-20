-- Migration 230: Unify weight columns on quote_items
-- Both weight_in_kg and weight_kg exist. weight_in_kg is the canonical column
-- used by the calculation engine. weight_kg was added later and is used by the
-- Handsontable JS frontend, with main.py mapping it back to weight_in_kg on save.
-- This migration merges any data from weight_kg into weight_in_kg and drops weight_kg.

-- Step 1: Copy weight_kg data into weight_in_kg where weight_in_kg is empty
UPDATE kvota.quote_items
SET weight_in_kg = weight_kg
WHERE weight_in_kg IS NULL AND weight_kg IS NOT NULL;

-- Step 2: Drop the duplicate column
ALTER TABLE kvota.quote_items DROP COLUMN IF EXISTS weight_kg;
