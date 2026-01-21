-- Migration 122: Add procurement total weight and volume to quotes
-- Feature: Procurement workflow improvements
-- Date: 2026-01-21
-- Description: Add fields for total weight and volume of priced items (procurement enters aggregated values)

-- =============================================================================
-- ADD PROCUREMENT TOTALS COLUMNS TO QUOTES TABLE
-- =============================================================================

-- Total weight in kg for all priced items in this quote
-- Procurement manager enters this after pricing items (may not know weight per item, but knows total)
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS procurement_total_weight_kg DECIMAL(10,3);

COMMENT ON COLUMN kvota.quotes.procurement_total_weight_kg IS 'Total weight in kilograms for all priced items (entered by procurement, precision to grams)';

-- Total volume in m3 for all priced items in this quote (optional)
-- Procurement manager enters this if known (not always available)
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS procurement_total_volume_m3 DECIMAL(10,4);

COMMENT ON COLUMN kvota.quotes.procurement_total_volume_m3 IS 'Total volume in cubic meters for all priced items (entered by procurement, optional, precision to 0.0001 m³)';

-- =============================================================================
-- ADD CHECK CONSTRAINTS
-- =============================================================================

-- Total weight must be positive
ALTER TABLE kvota.quotes
DROP CONSTRAINT IF EXISTS quotes_procurement_total_weight_check;

ALTER TABLE kvota.quotes
ADD CONSTRAINT quotes_procurement_total_weight_check
CHECK (procurement_total_weight_kg IS NULL OR procurement_total_weight_kg > 0);

-- Total volume must be positive
ALTER TABLE kvota.quotes
DROP CONSTRAINT IF EXISTS quotes_procurement_total_volume_check;

ALTER TABLE kvota.quotes
ADD CONSTRAINT quotes_procurement_total_volume_check
CHECK (procurement_total_volume_m3 IS NULL OR procurement_total_volume_m3 > 0);

-- =============================================================================
-- CREATE INDEXES FOR QUERIES
-- =============================================================================

-- Index for filtering quotes with weight data
CREATE INDEX IF NOT EXISTS idx_quotes_procurement_weight
ON kvota.quotes(procurement_total_weight_kg)
WHERE procurement_total_weight_kg IS NOT NULL;

-- Index for filtering quotes with volume data
CREATE INDEX IF NOT EXISTS idx_quotes_procurement_volume
ON kvota.quotes(procurement_total_volume_m3)
WHERE procurement_total_volume_m3 IS NOT NULL;
