-- Migration 198: Create currency_contracts table
-- Maps seller+buyer entity pairs to contract numbers for currency invoice auto-fill.
-- Uses the same polymorphic entity pattern as currency_invoices (seller_entity_type/id, buyer_entity_type/id).
-- One active contract per (org, seller, buyer, currency) enforced by partial unique index.

CREATE TABLE IF NOT EXISTS kvota.currency_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,

    -- Polymorphic seller reference (same pattern as currency_invoices)
    seller_entity_type TEXT CHECK (seller_entity_type IS NULL OR seller_entity_type IN ('buyer_company', 'seller_company')),
    seller_entity_id UUID,

    -- Polymorphic buyer reference
    buyer_entity_type TEXT CHECK (buyer_entity_type IS NULL OR buyer_entity_type IN ('buyer_company', 'seller_company')),
    buyer_entity_id UUID,

    -- Contract details
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    contract_number TEXT NOT NULL,
    contract_date DATE,

    -- Soft-delete
    is_active BOOLEAN DEFAULT true NOT NULL,

    -- Optional notes
    notes TEXT,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Only one active contract per (org, seller, buyer, currency) combination
CREATE UNIQUE INDEX IF NOT EXISTS idx_currency_contracts_active_unique
ON kvota.currency_contracts (
    organization_id,
    seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency
) WHERE is_active = true;

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_currency_contracts_org
ON kvota.currency_contracts(organization_id);

CREATE INDEX IF NOT EXISTS idx_currency_contracts_seller
ON kvota.currency_contracts(seller_entity_type, seller_entity_id)
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_currency_contracts_buyer
ON kvota.currency_contracts(buyer_entity_type, buyer_entity_id)
WHERE is_active = true;

-- RLS
ALTER TABLE kvota.currency_contracts ENABLE ROW LEVEL SECURITY;

CREATE POLICY currency_contracts_org_isolation ON kvota.currency_contracts
    USING (organization_id = current_setting('app.current_organization_id')::uuid);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION kvota.update_currency_contracts_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER currency_contracts_updated_at_trigger
    BEFORE UPDATE ON kvota.currency_contracts
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_currency_contracts_timestamp();

-- Comments
COMMENT ON TABLE kvota.currency_contracts IS 'Contract numbers mapped to seller/buyer entity pairs for currency invoice auto-fill';
COMMENT ON COLUMN kvota.currency_contracts.seller_entity_type IS 'Polymorphic type: buyer_company or seller_company';
COMMENT ON COLUMN kvota.currency_contracts.buyer_entity_type IS 'Polymorphic type: buyer_company or seller_company';
COMMENT ON COLUMN kvota.currency_contracts.contract_number IS 'Full contract number string, e.g. CONTRACT No 03-09/2024-1';
COMMENT ON COLUMN kvota.currency_contracts.contract_date IS 'Contract signing date';
COMMENT ON COLUMN kvota.currency_contracts.is_active IS 'Soft-delete flag. Partial unique index ensures one active contract per pair+currency.';

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (198, '198_create_currency_contracts.sql', now())
ON CONFLICT (id) DO NOTHING;
