-- Phase 3: Minimum order quantity on quote items.
-- Informational only — triggers a soft UX warning when quantity < min_order_quantity,
-- but does not block save, calculation, or approval.

ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS min_order_quantity NUMERIC;

COMMENT ON COLUMN kvota.quote_items.min_order_quantity IS
    'Supplier minimum order quantity. Informational only — triggers a soft UX warning when quantity < min_order_quantity, but does not block save, calculation, or approval.';
