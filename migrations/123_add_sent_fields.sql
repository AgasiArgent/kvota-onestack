-- Migration 123: Add sent_at and sent_to_email fields to quotes
-- For tracking when KP was sent to client

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS sent_to_email VARCHAR(255);

-- Add comment for documentation
COMMENT ON COLUMN kvota.quotes.sent_at IS 'Timestamp when quote was sent to client';
COMMENT ON COLUMN kvota.quotes.sent_to_email IS 'Email address the quote was sent to';
