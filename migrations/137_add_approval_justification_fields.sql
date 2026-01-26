-- Migration 137: Add approval justification fields to quotes table
-- Feature: Approval workflow with justification from sales manager
--
-- Fields:
-- - approval_reason: Comment from quote_controller explaining why approval is needed
-- - approval_justification: Justification from sales manager explaining the business case
-- - needs_justification: Flag indicating that sales manager needs to provide justification

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS approval_reason TEXT,
ADD COLUMN IF NOT EXISTS approval_justification TEXT,
ADD COLUMN IF NOT EXISTS needs_justification BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN kvota.quotes.approval_reason IS 'Comment from quote_controller explaining why top manager approval is needed (low margin, special terms, etc.)';
COMMENT ON COLUMN kvota.quotes.approval_justification IS 'Justification from sales manager explaining the business case for approval';
COMMENT ON COLUMN kvota.quotes.needs_justification IS 'Flag indicating that sales manager needs to provide justification before sending to approval';
