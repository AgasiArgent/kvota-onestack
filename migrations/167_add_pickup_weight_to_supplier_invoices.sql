-- Migration 167: Add pickup/weight/volume columns to supplier_invoices
-- BUG-5 follow-up: These fields are per-invoice (different invoices can have
-- different pickup locations and weights), so they belong on supplier_invoices.

ALTER TABLE kvota.supplier_invoices
  ADD COLUMN IF NOT EXISTS pickup_location_id UUID REFERENCES kvota.locations(id),
  ADD COLUMN IF NOT EXISTS pickup_country VARCHAR(100),
  ADD COLUMN IF NOT EXISTS total_weight_kg DECIMAL(10,3),
  ADD COLUMN IF NOT EXISTS total_volume_m3 DECIMAL(10,4);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_pickup_location
  ON kvota.supplier_invoices(pickup_location_id);

COMMENT ON COLUMN kvota.supplier_invoices.pickup_location_id IS 'Pickup location for this invoice (different invoices may have different pickup points)';
COMMENT ON COLUMN kvota.supplier_invoices.pickup_country IS 'Country of pickup/origin for this invoice';
COMMENT ON COLUMN kvota.supplier_invoices.total_weight_kg IS 'Total weight in kg for items in this invoice';
COMMENT ON COLUMN kvota.supplier_invoices.total_volume_m3 IS 'Total volume in m3 for items in this invoice';
