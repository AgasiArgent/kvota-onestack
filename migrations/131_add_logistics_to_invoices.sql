-- Migration 131: Add logistics cost columns to invoices table
-- These columns store per-invoice logistics costs filled by logistics department
-- Then aggregated and passed to calculation engine

-- Add logistics cost columns
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_supplier_to_hub DECIMAL(15,2);
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_hub_to_customs DECIMAL(15,2);
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_customs_to_customer DECIMAL(15,2);
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_total_days INTEGER;
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_notes TEXT;
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_completed_at TIMESTAMPTZ;
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_completed_by UUID REFERENCES kvota.users(id);

-- Add comments
COMMENT ON COLUMN kvota.invoices.logistics_supplier_to_hub IS 'Cost of logistics from supplier to hub (in invoice currency)';
COMMENT ON COLUMN kvota.invoices.logistics_hub_to_customs IS 'Cost of logistics from hub to customs (in invoice currency)';
COMMENT ON COLUMN kvota.invoices.logistics_customs_to_customer IS 'Cost of logistics from customs to customer (in invoice currency)';
COMMENT ON COLUMN kvota.invoices.logistics_total_days IS 'Total transit time in days';
COMMENT ON COLUMN kvota.invoices.logistics_notes IS 'Logistics notes and comments';
COMMENT ON COLUMN kvota.invoices.logistics_completed_at IS 'When logistics was completed for this invoice';
COMMENT ON COLUMN kvota.invoices.logistics_completed_by IS 'User who completed logistics';

-- Create index for finding invoices needing logistics
CREATE INDEX IF NOT EXISTS idx_invoices_logistics_pending
ON kvota.invoices(quote_id)
WHERE logistics_supplier_to_hub IS NULL;
