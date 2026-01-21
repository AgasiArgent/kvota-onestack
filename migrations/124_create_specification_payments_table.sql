-- Migration 124: Create specification_payments table for tracking income/expense by specification
-- Purpose: Finance team tracks all payments (from client and to suppliers) per specification

-- Create specification_payments table
CREATE TABLE IF NOT EXISTS kvota.specification_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
  specification_id UUID NOT NULL REFERENCES kvota.specifications(id) ON DELETE CASCADE,

  -- Payment details
  payment_date DATE NOT NULL,
  amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),
  currency VARCHAR(3) NOT NULL DEFAULT 'USD',

  -- Category: income (from client) or expense (to suppliers/logistics/etc)
  category TEXT NOT NULL CHECK (category IN ('income', 'expense')),
  payment_number INT NOT NULL,  -- Auto-incremented separately for income/expense per specification

  -- Additional info
  comment TEXT,

  -- Metadata
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_spec_payments_specification ON kvota.specification_payments(specification_id);
CREATE INDEX idx_spec_payments_category ON kvota.specification_payments(category);
CREATE INDEX idx_spec_payments_date ON kvota.specification_payments(payment_date);
CREATE INDEX idx_spec_payments_org_category ON kvota.specification_payments(organization_id, category);

-- Function to auto-set payment_number (separate counter per specification + category)
CREATE OR REPLACE FUNCTION kvota.set_spec_payment_number()
RETURNS TRIGGER AS $$
BEGIN
  -- Get max payment_number for this specification + category combination
  SELECT COALESCE(MAX(payment_number), 0) + 1
  INTO NEW.payment_number
  FROM kvota.specification_payments
  WHERE specification_id = NEW.specification_id
    AND category = NEW.category;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-set payment_number on insert
CREATE TRIGGER trigger_set_spec_payment_number
  BEFORE INSERT ON kvota.specification_payments
  FOR EACH ROW
  EXECUTE FUNCTION kvota.set_spec_payment_number();

-- Trigger for updated_at
CREATE TRIGGER update_spec_payments_updated_at
  BEFORE UPDATE ON kvota.specification_payments
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security
ALTER TABLE kvota.specification_payments ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Only finance, admin, top_manager can access
CREATE POLICY "finance_admin_full_access" ON kvota.specification_payments
  FOR ALL USING (
    auth.uid() IN (
      SELECT ur.user_id
      FROM kvota.user_roles ur
      JOIN kvota.roles r ON r.id = ur.role_id
      WHERE r.slug IN ('finance', 'admin', 'top_manager')
        AND ur.organization_id = specification_payments.organization_id
    )
  );

-- Comments for documentation
COMMENT ON TABLE kvota.specification_payments IS 'Tracks all payments (income from client, expenses to suppliers) per specification';
COMMENT ON COLUMN kvota.specification_payments.category IS 'income = payment from client, expense = payment to supplier/logistics/customs';
COMMENT ON COLUMN kvota.specification_payments.payment_number IS 'Auto-incremented counter (separate for income and expense per specification)';
