-- Migration 172: Add profit and total in quote currency columns
-- These store the calculated values in the quote's own currency (RUB/USD/EUR)
-- Previously only total_profit_usd was stored; total_amount already held quote-currency value

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS profit_quote_currency DECIMAL(15,2);

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS total_quote_currency DECIMAL(15,2);
