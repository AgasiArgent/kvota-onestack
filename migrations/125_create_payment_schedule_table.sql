-- Migration 125: Create payment_schedule table (КАЛЕНДАРЬ - Payment Calendar)
-- Purpose: Finance team manually enters expected payment schedules from clients

-- Create payment_schedule table
CREATE TABLE IF NOT EXISTS kvota.payment_schedule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
  specification_id UUID NOT NULL REFERENCES kvota.specifications(id) ON DELETE CASCADE,

  -- Payment number (auto-incremented per specification)
  payment_number INT NOT NULL,

  -- MOP/FM Input - Planning fields
  days_term INT,  -- Days term for payment
  calculation_variant TEXT CHECK (calculation_variant IN (
    'from_order_date',      -- от даты заказа
    'from_agreement_date',  -- от даты согласования
    'from_shipment_date',   -- от даты отгрузки
    'until_shipment_date'   -- до даты отгрузки
  )),

  -- Dates
  expected_payment_date DATE,  -- Ожидаемая дата платежа
  actual_payment_date DATE,    -- Фактическая дата платежа

  -- Payment amounts
  payment_amount DECIMAL(15,2),
  payment_currency VARCHAR(3) DEFAULT 'USD',

  -- Payment purpose
  payment_purpose TEXT CHECK (payment_purpose IN (
    'advance',      -- Аванс
    'additional',   -- Доплата
    'final'         -- Закрывающий платеж
  )),

  -- Document
  payment_document_url TEXT,  -- URL uploaded payment document

  -- Comment
  comment TEXT,

  -- Metadata
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_payment_schedule_specification ON kvota.payment_schedule(specification_id);
CREATE INDEX idx_payment_schedule_expected_date ON kvota.payment_schedule(expected_payment_date);
CREATE INDEX idx_payment_schedule_actual_date ON kvota.payment_schedule(actual_payment_date);
CREATE INDEX idx_payment_schedule_org ON kvota.payment_schedule(organization_id);

-- Function to auto-set payment_number (per specification)
CREATE OR REPLACE FUNCTION kvota.set_payment_schedule_number()
RETURNS TRIGGER AS $$
BEGIN
  -- Get max payment_number for this specification
  SELECT COALESCE(MAX(payment_number), 0) + 1
  INTO NEW.payment_number
  FROM kvota.payment_schedule
  WHERE specification_id = NEW.specification_id;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-set payment_number on insert
CREATE TRIGGER trigger_set_payment_schedule_number
  BEFORE INSERT ON kvota.payment_schedule
  FOR EACH ROW
  EXECUTE FUNCTION kvota.set_payment_schedule_number();

-- Trigger for updated_at
CREATE TRIGGER update_payment_schedule_updated_at
  BEFORE UPDATE ON kvota.payment_schedule
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security
ALTER TABLE kvota.payment_schedule ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Only finance, admin, top_manager can access
CREATE POLICY "finance_admin_full_access_schedule" ON kvota.payment_schedule
  FOR ALL USING (
    auth.uid() IN (
      SELECT ur.user_id
      FROM kvota.user_roles ur
      JOIN kvota.roles r ON r.id = ur.role_id
      WHERE r.slug IN ('finance', 'admin', 'top_manager')
        AND ur.organization_id = payment_schedule.organization_id
    )
  );

-- Comments for documentation
COMMENT ON TABLE kvota.payment_schedule IS 'Payment calendar (КАЛЕНДАРЬ) - manually entered expected payment schedules from clients';
COMMENT ON COLUMN kvota.payment_schedule.payment_number IS 'Auto-incremented payment number per specification';
COMMENT ON COLUMN kvota.payment_schedule.calculation_variant IS 'How to calculate expected date based on days_term';
COMMENT ON COLUMN kvota.payment_schedule.payment_purpose IS 'advance=аванс, additional=доплата, final=закрывающий платеж';
