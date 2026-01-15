-- Migration 006: Create specifications table
-- Created: 2025-01-15
-- Feature #6: Specifications table for storing specification data from spec_controller

-- The specifications table stores all data needed for generating and managing
-- commercial specifications. This is created when a quote is ready to be sent
-- to a client as a formal specification document.

-- Create specifications table
CREATE TABLE IF NOT EXISTS specifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Linked quote and version
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    quote_version_id UUID REFERENCES quote_versions(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Specification identification
    specification_number VARCHAR(100),
    proposal_idn VARCHAR(100),
    item_ind_sku VARCHAR(100),

    -- Dates and validity
    sign_date DATE,
    validity_period VARCHAR(100),

    -- Currency and rates
    specification_currency VARCHAR(10),
    exchange_rate_to_ruble DECIMAL(15, 6),

    -- Client payment terms
    client_payment_term_after_upd INTEGER,
    client_payment_terms TEXT,

    -- Origin and shipping
    cargo_pickup_country VARCHAR(100),
    readiness_period VARCHAR(100),
    goods_shipment_country VARCHAR(100),
    delivery_city_russia VARCHAR(255),

    -- Cargo details
    cargo_type VARCHAR(100),
    logistics_period VARCHAR(100),

    -- Legal entities
    our_legal_entity VARCHAR(255),
    client_legal_entity VARCHAR(255),

    -- Supplier payment
    supplier_payment_country VARCHAR(100),

    -- Signed document
    signed_scan_url TEXT,

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'pending_review', 'approved', 'signed')),

    -- Audit fields
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add comments for documentation
COMMENT ON TABLE specifications IS 'Specification data for quotes ready to be sent to clients';
COMMENT ON COLUMN specifications.quote_id IS 'Reference to the source quote';
COMMENT ON COLUMN specifications.quote_version_id IS 'Specific version of the quote used for this specification';
COMMENT ON COLUMN specifications.organization_id IS 'Organization that owns this specification';
COMMENT ON COLUMN specifications.specification_number IS 'Unique specification number for the document';
COMMENT ON COLUMN specifications.proposal_idn IS 'IDN of the proposal (КП)';
COMMENT ON COLUMN specifications.item_ind_sku IS 'IDN-SKU identifier';
COMMENT ON COLUMN specifications.sign_date IS 'Date when specification was signed';
COMMENT ON COLUMN specifications.validity_period IS 'Period during which specification is valid';
COMMENT ON COLUMN specifications.specification_currency IS 'Currency used in the specification';
COMMENT ON COLUMN specifications.exchange_rate_to_ruble IS 'Exchange rate to Russian Ruble';
COMMENT ON COLUMN specifications.client_payment_term_after_upd IS 'Payment term in days after UPD';
COMMENT ON COLUMN specifications.client_payment_terms IS 'Client payment terms description';
COMMENT ON COLUMN specifications.cargo_pickup_country IS 'Country where cargo is picked up';
COMMENT ON COLUMN specifications.readiness_period IS 'Period for cargo readiness';
COMMENT ON COLUMN specifications.goods_shipment_country IS 'Country from which goods are shipped';
COMMENT ON COLUMN specifications.delivery_city_russia IS 'Delivery city in Russia';
COMMENT ON COLUMN specifications.cargo_type IS 'Type of cargo';
COMMENT ON COLUMN specifications.logistics_period IS 'Logistics delivery period';
COMMENT ON COLUMN specifications.our_legal_entity IS 'Our legal entity for the contract';
COMMENT ON COLUMN specifications.client_legal_entity IS 'Client legal entity';
COMMENT ON COLUMN specifications.supplier_payment_country IS 'Country for supplier payment';
COMMENT ON COLUMN specifications.signed_scan_url IS 'URL to the signed scan of specification';
COMMENT ON COLUMN specifications.status IS 'Specification status: draft, pending_review, approved, signed';

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_specifications_quote_id ON specifications(quote_id);
CREATE INDEX IF NOT EXISTS idx_specifications_organization_id ON specifications(organization_id);
CREATE INDEX IF NOT EXISTS idx_specifications_status ON specifications(status);
CREATE INDEX IF NOT EXISTS idx_specifications_created_at ON specifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_specifications_specification_number ON specifications(specification_number);
CREATE INDEX IF NOT EXISTS idx_specifications_org_status ON specifications(organization_id, status);

-- Enable Row Level Security
ALTER TABLE specifications ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can view specifications in their organization
CREATE POLICY "Users can view specifications in their organization"
    ON specifications
    FOR SELECT
    USING (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    );

-- RLS Policy: Users can insert specifications in their organization
CREATE POLICY "Users can insert specifications in their organization"
    ON specifications
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    );

-- RLS Policy: Users can update specifications in their organization
-- Only spec_controllers and admins should update, but RLS handles org-level access
-- Application logic will enforce role-based permissions
CREATE POLICY "Users can update specifications in their organization"
    ON specifications
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    );

-- RLS Policy: Only admins can delete specifications
-- In practice, specifications should not be deleted, only cancelled
CREATE POLICY "Admins can delete specifications"
    ON specifications
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = specifications.organization_id
            AND r.code = 'admin'
        )
    );

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_specifications_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_specifications_updated_at
    BEFORE UPDATE ON specifications
    FOR EACH ROW
    EXECUTE FUNCTION update_specifications_updated_at();
