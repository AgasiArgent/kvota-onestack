-- Migration 133: Add currency columns for logistics costs
-- Each logistics segment can have its own currency (USD, EUR, RUB, CNY, TRY)
-- Values will be converted to USD before calculation

ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_supplier_to_hub_currency VARCHAR(3) DEFAULT 'USD';
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_hub_to_customs_currency VARCHAR(3) DEFAULT 'USD';
ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS logistics_customs_to_customer_currency VARCHAR(3) DEFAULT 'USD';

-- Add comments
COMMENT ON COLUMN kvota.invoices.logistics_supplier_to_hub_currency IS 'Currency for supplier to hub logistics cost (USD, EUR, RUB, CNY, TRY)';
COMMENT ON COLUMN kvota.invoices.logistics_hub_to_customs_currency IS 'Currency for hub to customs logistics cost (USD, EUR, RUB, CNY, TRY)';
COMMENT ON COLUMN kvota.invoices.logistics_customs_to_customer_currency IS 'Currency for customs to customer logistics cost (USD, EUR, RUB, CNY, TRY)';
