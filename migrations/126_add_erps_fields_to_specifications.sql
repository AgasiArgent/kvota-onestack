-- Migration 126: Add fields to specifications table for ERPS calculations
-- Purpose: Add fields needed for payment and delivery deadline calculations in ERPS registry

-- Add new fields to specifications table
ALTER TABLE kvota.specifications
  ADD COLUMN IF NOT EXISTS advance_percent_from_client DECIMAL(5,2) DEFAULT 100 CHECK (advance_percent_from_client >= 0 AND advance_percent_from_client <= 100),
  ADD COLUMN IF NOT EXISTS payment_deferral_days INT DEFAULT 0 CHECK (payment_deferral_days >= 0),
  ADD COLUMN IF NOT EXISTS delivery_period_days INT CHECK (delivery_period_days >= 0),
  ADD COLUMN IF NOT EXISTS days_from_delivery_to_advance INT DEFAULT 0 CHECK (days_from_delivery_to_advance >= 0);

-- Add indexes for query performance
CREATE INDEX IF NOT EXISTS idx_specifications_delivery_period ON kvota.specifications(delivery_period_days) WHERE delivery_period_days IS NOT NULL;

-- Comments for documentation
COMMENT ON COLUMN kvota.specifications.advance_percent_from_client IS 'Размер аванса от клиента (%). Используется для расчета планируемой суммы аванса';
COMMENT ON COLUMN kvota.specifications.payment_deferral_days IS 'Отсрочка платежа от клиента (дни). Используется для расчета крайнего срока оплаты';
COMMENT ON COLUMN kvota.specifications.delivery_period_days IS 'Срок поставки (дни). Используется для расчета: крайний срок поставки = sign_date + delivery_period_days';
COMMENT ON COLUMN kvota.specifications.days_from_delivery_to_advance IS 'Дней с момента доставки до оплаты аванса. Используется для расчета крайнего срока оплаты аванса';
