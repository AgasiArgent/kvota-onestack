-- Migration: Add rejection tracking columns to quotes
-- Created: 2026-02-02
-- Purpose: Store rejection reason and details when client rejects a quote

SET search_path TO kvota;

-- Add rejection tracking columns
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(50),
ADD COLUMN IF NOT EXISTS rejection_comment TEXT,
ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES auth.users(id);

-- Add index for filtering rejected quotes by reason
CREATE INDEX IF NOT EXISTS idx_quotes_rejection_reason ON kvota.quotes(rejection_reason) WHERE rejection_reason IS NOT NULL;

COMMENT ON COLUMN kvota.quotes.rejection_reason IS 'Reason code for client rejection (price_too_high, delivery_time, competitor, etc.)';
COMMENT ON COLUMN kvota.quotes.rejection_comment IS 'Additional details about the rejection';
COMMENT ON COLUMN kvota.quotes.rejected_at IS 'Timestamp when quote was marked as rejected';
COMMENT ON COLUMN kvota.quotes.rejected_by IS 'User who recorded the rejection';
