-- Migration 125: Add invoice status tracking for per-invoice workflow
-- Each invoice flows independently: pending_procurement → pending_logistics → pending_customs → completed

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'pending_procurement';

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMPTZ;

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS procurement_completed_by UUID;

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS logistics_completed_at TIMESTAMPTZ;

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS logistics_completed_by UUID;

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS customs_completed_at TIMESTAMPTZ;

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS customs_completed_by UUID;

-- Add comments
COMMENT ON COLUMN kvota.invoices.status IS 'Invoice workflow status: pending_procurement, pending_logistics, pending_customs, completed';
COMMENT ON COLUMN kvota.invoices.procurement_completed_at IS 'When procurement marked this invoice complete';
COMMENT ON COLUMN kvota.invoices.procurement_completed_by IS 'User who completed procurement for this invoice';

-- Create index for status queries
CREATE INDEX IF NOT EXISTS idx_invoices_status ON kvota.invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_quote_status ON kvota.invoices(quote_id, status);
