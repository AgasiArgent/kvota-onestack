-- Migration 142: Make base_price_vat nullable in quote_items
-- This allows sales to create items without knowing the price
-- Procurement will fill in the price later

ALTER TABLE kvota.quote_items
ALTER COLUMN base_price_vat DROP NOT NULL;

-- Set default to 0 for new items
ALTER TABLE kvota.quote_items
ALTER COLUMN base_price_vat SET DEFAULT 0;

COMMENT ON COLUMN kvota.quote_items.base_price_vat IS 'Base price with VAT - nullable for sales draft items, filled by procurement';
