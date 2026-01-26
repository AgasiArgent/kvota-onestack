-- Migration 136: Add revision tracking fields to quotes table
-- Feature: Multi-department return for revision
--
-- This migration adds fields to track when a quote is returned for revision:
-- - revision_department: which department it was returned to (sales/procurement/logistics/customs)
-- - revision_comment: the comment from quote_controller explaining what needs to be fixed
-- - revision_returned_at: timestamp when the return happened
--
-- When a department finishes fixing and returns to quote_control, these fields are cleared.

-- Add revision tracking fields to quotes table
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS revision_department VARCHAR(50),
ADD COLUMN IF NOT EXISTS revision_comment TEXT,
ADD COLUMN IF NOT EXISTS revision_returned_at TIMESTAMPTZ;

-- Add comment for documentation
COMMENT ON COLUMN kvota.quotes.revision_department IS 'Department the quote was returned to for revision (sales/procurement/logistics/customs). Cleared when returned to quote_control.';
COMMENT ON COLUMN kvota.quotes.revision_comment IS 'Comment from quote_controller explaining what needs to be fixed. Cleared when returned to quote_control.';
COMMENT ON COLUMN kvota.quotes.revision_returned_at IS 'Timestamp when the quote was returned for revision. Cleared when returned to quote_control.';

-- Create index for filtering quotes that are returned for revision
CREATE INDEX IF NOT EXISTS idx_quotes_revision_department
ON kvota.quotes(revision_department)
WHERE revision_department IS NOT NULL;
