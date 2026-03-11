-- Add revenue_no_vat_quote_currency column to quotes table
-- Used for correct margin calculation: margin = profit / revenue_no_vat
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS revenue_no_vat_quote_currency NUMERIC;
