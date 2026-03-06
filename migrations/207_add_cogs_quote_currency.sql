-- Add COGS (cost of goods sold) in quote currency to quotes table
-- Used to display both Маржа (profit/revenue) and Наценка (profit/COGS)
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS cogs_quote_currency DECIMAL(15, 2);
