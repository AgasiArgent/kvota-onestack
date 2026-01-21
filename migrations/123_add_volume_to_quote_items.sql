-- Migration 123: Add volume_m3 to quote_items
-- Date: 2026-01-21
-- Description: Add volume per item (optional, for future use)

ALTER TABLE kvota.quote_items
ADD COLUMN IF NOT EXISTS volume_m3 DECIMAL(10,4);

COMMENT ON COLUMN kvota.quote_items.volume_m3 IS 'Item volume in cubic meters (optional, for future customs calculations)';
