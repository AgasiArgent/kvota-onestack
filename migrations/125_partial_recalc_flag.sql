-- Migration 125: Add partial_recalc flag to quotes
-- For tracking partial recalculation requirements during change requests

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS partial_recalc VARCHAR(50);

-- Add check constraint for valid values
ALTER TABLE kvota.quotes
ADD CONSTRAINT chk_partial_recalc_values 
CHECK (partial_recalc IS NULL OR partial_recalc IN ('logistics', 'add_item', 'price', 'full'));

-- Add comment for documentation
COMMENT ON COLUMN kvota.quotes.partial_recalc IS 'Partial recalc flag: logistics, add_item, price, full, or NULL';
