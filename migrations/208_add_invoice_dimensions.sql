-- Migration 208: Add invoice dimensions, package count, and procurement notes
-- Logistics needs granular shipping data from procurement

ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS height_m DECIMAL(6,3);
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS length_m DECIMAL(6,3);
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS width_m DECIMAL(6,3);
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS package_count INTEGER;
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS procurement_notes TEXT;
