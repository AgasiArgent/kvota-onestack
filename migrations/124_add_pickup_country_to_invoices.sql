-- Migration 124: Add pickup_country to invoices table
-- This moves pickup_country from item-level to invoice-level

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS pickup_country VARCHAR(100);

-- Add comment
COMMENT ON COLUMN kvota.invoices.pickup_country IS 'Country where items are picked up (invoice-level)';
