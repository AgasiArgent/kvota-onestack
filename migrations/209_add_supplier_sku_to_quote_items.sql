-- Migration 209: Add supplier_sku to quote_items
-- Business case: Procurement tracks when a supplier offers a replacement SKU
-- idn_sku (immutable, auto-generated) = client's original request
-- supplier_sku (nullable, set by procurement) = what supplier actually offers

ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS supplier_sku TEXT;

COMMENT ON COLUMN kvota.quote_items.supplier_sku IS
  'Alternative SKU offered by supplier when original idn_sku is discontinued or unavailable. Set by procurement department.';
