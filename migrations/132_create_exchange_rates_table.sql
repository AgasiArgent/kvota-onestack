-- Migration 132: Create exchange_rates table for multi-currency support
-- Stores daily exchange rates from CBR (Central Bank of Russia)

CREATE TABLE IF NOT EXISTS kvota.exchange_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rate_date DATE NOT NULL,
    currency VARCHAR(3) NOT NULL,        -- USD, EUR, CNY, TRY
    rate_to_rub DECIMAL(18,8) NOT NULL,  -- Rate per 1 unit (e.g., 1 USD = 96.5 RUB)
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(rate_date, currency)
);

-- Index for efficient lookups by date
CREATE INDEX IF NOT EXISTS idx_exchange_rates_date ON kvota.exchange_rates(rate_date DESC);

-- Index for currency lookups
CREATE INDEX IF NOT EXISTS idx_exchange_rates_currency ON kvota.exchange_rates(currency);

COMMENT ON TABLE kvota.exchange_rates IS 'Daily exchange rates from CBR for multi-currency logistics calculations';
COMMENT ON COLUMN kvota.exchange_rates.rate_to_rub IS 'Rate per 1 unit of currency to RUB (e.g., 1 USD = 96.5 RUB)';
