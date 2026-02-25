-- Migration 185: Create currency_invoices table
-- Stores internal currency invoices between group companies (EURTR/TRRU segments)
-- Generated automatically when a deal is signed

CREATE TABLE IF NOT EXISTS kvota.currency_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES kvota.deals(id) ON DELETE CASCADE,
    segment TEXT NOT NULL CHECK (segment IN ('EURTR', 'TRRU')),
    invoice_number TEXT UNIQUE NOT NULL,
    seller_entity_type TEXT CHECK (seller_entity_type IS NULL OR seller_entity_type IN ('buyer_company', 'seller_company')),
    seller_entity_id UUID,
    buyer_entity_type TEXT CHECK (buyer_entity_type IS NULL OR buyer_entity_type IN ('buyer_company', 'seller_company')),
    buyer_entity_id UUID,
    markup_percent DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    total_amount DECIMAL(15,2),
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'verified', 'exported')),
    source_invoice_ids UUID[],
    generated_at TIMESTAMPTZ DEFAULT now(),
    verified_by UUID REFERENCES auth.users(id),
    verified_at TIMESTAMPTZ,
    organization_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_currency_invoices_deal ON kvota.currency_invoices(deal_id);
CREATE INDEX IF NOT EXISTS idx_currency_invoices_status ON kvota.currency_invoices(status);
CREATE INDEX IF NOT EXISTS idx_currency_invoices_org ON kvota.currency_invoices(organization_id);

-- RLS
ALTER TABLE kvota.currency_invoices ENABLE ROW LEVEL SECURITY;

CREATE POLICY currency_invoices_org_isolation ON kvota.currency_invoices
    USING (organization_id = current_setting('app.current_organization_id')::uuid);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (185, '185_create_currency_invoices.sql', now())
ON CONFLICT (id) DO NOTHING;
