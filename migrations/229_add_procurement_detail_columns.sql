-- Migration 229: Add procurement detail columns to quote_items
-- Adds VAT rate, supplier SKU mismatch note, dimensions, and manufacturer product name
-- for the procurement 12-column table in the quote detail migration.

ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS supplier_sku_note TEXT;
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS manufacturer_product_name TEXT;
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS dimension_height_mm INTEGER;
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS dimension_width_mm INTEGER;
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS dimension_length_mm INTEGER;
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS vat_rate DECIMAL(5,2);
