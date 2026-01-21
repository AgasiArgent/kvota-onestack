-- Migration 121: Add purchase_currency column to quote_items
-- Feature: Procurement workflow improvements
-- Date: 2026-01-21
-- Description: Add currency field for purchase price (procurement enters price in supplier's currency)

-- =============================================================================
-- ADD PURCHASE_CURRENCY COLUMN TO QUOTE_ITEMS TABLE
-- =============================================================================

-- Purchase currency - currency in which supplier quotes price
-- Common values: USD, EUR, RUB, CNY, TRY
ALTER TABLE kvota.quote_items
ADD COLUMN IF NOT EXISTS purchase_currency VARCHAR(3) DEFAULT 'USD';

COMMENT ON COLUMN kvota.quote_items.purchase_currency IS 'Currency code for purchase_price_original (ISO 4217: USD, EUR, RUB, CNY, TRY, etc.)';

-- =============================================================================
-- ADD CHECK CONSTRAINT
-- =============================================================================

-- Currency code must be 3 uppercase letters (ISO 4217 standard)
ALTER TABLE kvota.quote_items
DROP CONSTRAINT IF EXISTS quote_items_purchase_currency_check;

ALTER TABLE kvota.quote_items
ADD CONSTRAINT quote_items_purchase_currency_check
CHECK (purchase_currency IS NULL OR purchase_currency ~ '^[A-Z]{3}$');

-- =============================================================================
-- CREATE INDEX FOR FILTERING BY CURRENCY
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_quote_items_purchase_currency
ON kvota.quote_items(purchase_currency)
WHERE purchase_currency IS NOT NULL;

-- =============================================================================
-- UPDATE TABLE COMMENT
-- =============================================================================

COMMENT ON TABLE kvota.quote_items IS 'Quote line items with v3.0 supply chain extensions. Includes purchase_price_original (price from supplier) and purchase_currency (currency of that price). Auto-conversion to quote currency will be implemented separately.';
