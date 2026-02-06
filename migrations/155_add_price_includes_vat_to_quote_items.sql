-- Migration 155: Add price_includes_vat flag to quote_items
-- Indicates whether the purchase price includes VAT

ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS price_includes_vat BOOLEAN DEFAULT false;
