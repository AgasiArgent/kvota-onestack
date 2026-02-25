-- Migration 186: Create currency_invoice_items table
-- Line items for currency invoices, snapshot of quote_items with markup-adjusted prices

CREATE TABLE IF NOT EXISTS kvota.currency_invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    currency_invoice_id UUID NOT NULL REFERENCES kvota.currency_invoices(id) ON DELETE CASCADE,
    source_item_id UUID REFERENCES kvota.quote_items(id),
    product_name TEXT NOT NULL,
    sku TEXT,
    idn_sku TEXT,
    manufacturer TEXT,
    quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    unit TEXT DEFAULT 'pcs',
    hs_code TEXT,
    base_price DECIMAL(15,4) NOT NULL DEFAULT 0,
    price DECIMAL(15,4) NOT NULL DEFAULT 0,
    total DECIMAL(15,2) NOT NULL DEFAULT 0,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_currency_invoice_items_invoice ON kvota.currency_invoice_items(currency_invoice_id);
CREATE INDEX IF NOT EXISTS idx_currency_invoice_items_source ON kvota.currency_invoice_items(source_item_id);

-- RLS via parent join
ALTER TABLE kvota.currency_invoice_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY currency_invoice_items_via_parent ON kvota.currency_invoice_items
    USING (currency_invoice_id IN (
        SELECT id FROM kvota.currency_invoices
        WHERE organization_id = current_setting('app.current_organization_id')::uuid
    ));

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (186, '186_create_currency_invoice_items.sql', now())
ON CONFLICT (id) DO NOTHING;
