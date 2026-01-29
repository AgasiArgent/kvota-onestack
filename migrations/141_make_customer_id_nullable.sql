-- Migration 141: Make customer_id nullable in quotes table
-- This allows creating draft quotes without selecting a customer first

ALTER TABLE kvota.quotes
ALTER COLUMN customer_id DROP NOT NULL;

-- Add comment explaining why it's nullable
COMMENT ON COLUMN kvota.quotes.customer_id IS 'Customer ID - nullable to allow creating empty draft quotes';
