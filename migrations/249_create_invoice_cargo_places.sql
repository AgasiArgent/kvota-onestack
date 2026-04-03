-- Invoice cargo places (грузовые места)
-- Each invoice has 1+ boxes with weight and dimensions

CREATE TABLE IF NOT EXISTS kvota.invoice_cargo_places (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
  position INT NOT NULL DEFAULT 1,
  weight_kg DECIMAL(10,3) NOT NULL CHECK (weight_kg > 0),
  length_mm INT NOT NULL CHECK (length_mm > 0),
  width_mm INT NOT NULL CHECK (width_mm > 0),
  height_mm INT NOT NULL CHECK (height_mm > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(invoice_id, position)
);

-- RLS: same access as quote_invoices (through quote → org)
ALTER TABLE kvota.invoice_cargo_places ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage cargo places for their org invoices"
  ON kvota.invoice_cargo_places
  FOR ALL
  USING (
    invoice_id IN (
      SELECT qi.id FROM kvota.invoices qi
      JOIN kvota.quotes q ON q.id = qi.quote_id
      JOIN kvota.organization_members om ON om.organization_id = q.organization_id
      WHERE om.user_id = auth.uid()
    )
  );
