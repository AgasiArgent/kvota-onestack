-- Migration 126: Add unavailable flag to quote items
-- Allows marking items that supplier cannot provide (discontinued, out of stock, etc.)
-- These items are excluded from pricing calculations

ALTER TABLE kvota.quote_items
ADD COLUMN IF NOT EXISTS is_unavailable BOOLEAN DEFAULT FALSE;

-- Add comment
COMMENT ON COLUMN kvota.quote_items.is_unavailable IS 'Item not available from supplier (excluded from calculations)';

-- Create index for filtering available items
CREATE INDEX IF NOT EXISTS idx_quote_items_unavailable ON kvota.quote_items(quote_id, is_unavailable) WHERE is_unavailable = TRUE;
