-- Migration 233: Create logistics additional expenses table
-- Tracks per-invoice additional costs: СВХ (warehouse), insurance, other.
-- Used by the logistics step on the quote detail page.

CREATE TABLE IF NOT EXISTS kvota.logistics_additional_expenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
  expense_type TEXT NOT NULL,  -- 'svh', 'insurance', 'other'
  description TEXT,
  amount DECIMAL(15,2) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_logistics_expenses_invoice
  ON kvota.logistics_additional_expenses(invoice_id);

-- RLS: org members can access expenses through invoice -> quote -> org chain
ALTER TABLE kvota.logistics_additional_expenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_members_all" ON kvota.logistics_additional_expenses
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM kvota.invoices i
      JOIN kvota.quotes q ON q.id = i.quote_id
      JOIN kvota.organization_members om ON om.organization_id = q.organization_id
      WHERE i.id = kvota.logistics_additional_expenses.invoice_id
        AND om.user_id = auth.uid()
    )
  );
