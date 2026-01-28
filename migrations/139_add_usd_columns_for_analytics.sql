-- Migration 139: Add USD columns for analytics reporting
-- Internal company currency is USD, so we store USD equivalents alongside quote currency values
-- This enables fast analytics queries without on-the-fly currency conversion

-- ============================================================================
-- 1. QUOTES TABLE - Add USD totals and exchange rate
-- ============================================================================

-- Exchange rate used at calculation time (quote_currency → USD)
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS exchange_rate_to_usd DECIMAL(12,6);

-- USD equivalents of totals (total_profit_usd already exists)
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS subtotal_usd DECIMAL(15,2);

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS total_amount_usd DECIMAL(15,2);

COMMENT ON COLUMN kvota.quotes.exchange_rate_to_usd IS 'Exchange rate from quote currency to USD at calculation time';
COMMENT ON COLUMN kvota.quotes.subtotal_usd IS 'Total purchase price (S16 sum) in USD';
COMMENT ON COLUMN kvota.quotes.total_amount_usd IS 'Total with VAT (AL16 sum) in USD';

-- ============================================================================
-- 2. QUOTE_CALCULATION_RESULTS TABLE - Add phase_results_usd
-- ============================================================================

ALTER TABLE kvota.quote_calculation_results
ADD COLUMN IF NOT EXISTS phase_results_usd JSONB;

COMMENT ON COLUMN kvota.quote_calculation_results.phase_results_usd IS 'All phase results converted to USD for analytics';

-- ============================================================================
-- 3. QUOTE_CALCULATION_SUMMARIES TABLE - Add USD columns
-- ============================================================================

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS exchange_rate_to_usd DECIMAL(12,6);

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS calc_s16_total_purchase_price_usd DECIMAL(15,2);

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS calc_v16_total_logistics_usd DECIMAL(15,2);

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS calc_y16_customs_duty_usd DECIMAL(15,2);

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS calc_total_brokerage_usd DECIMAL(15,2);

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS calc_ae16_sale_price_total_usd DECIMAL(15,2);

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS calc_al16_total_with_vat_usd DECIMAL(15,2);

ALTER TABLE kvota.quote_calculation_summaries
ADD COLUMN IF NOT EXISTS calc_af16_total_profit_usd DECIMAL(15,2);

COMMENT ON COLUMN kvota.quote_calculation_summaries.exchange_rate_to_usd IS 'Exchange rate from quote currency to USD at calculation time';

-- ============================================================================
-- 4. INDEX for analytics queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_quotes_total_amount_usd
ON kvota.quotes(total_amount_usd)
WHERE total_amount_usd IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quotes_subtotal_usd
ON kvota.quotes(subtotal_usd)
WHERE subtotal_usd IS NOT NULL;
