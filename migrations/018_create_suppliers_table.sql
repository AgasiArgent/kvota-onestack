-- Migration: Create suppliers table
-- Feature: DB-001
-- Description: Create suppliers table for external supplier companies in supply chain
-- Part of v3.0: Supply chain entities (Supplier → Buyer Company → Seller Company → Customer)

-- ============================================
-- SUPPLIERS TABLE
-- ============================================
-- External companies from which we purchase goods
-- Level: ITEM (each quote_item can have its own supplier)

CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Company identification
    name VARCHAR(255) NOT NULL,
    supplier_code VARCHAR(3) NOT NULL,  -- 3-letter code (e.g., CMT, RAR)

    -- Location
    country VARCHAR(100),
    city VARCHAR(100),

    -- Legal identifiers (for Russian suppliers)
    inn VARCHAR(12),  -- ИНН (10 for legal entities, 12 for individuals)
    kpp VARCHAR(9),   -- КПП

    -- Contact information
    contact_person VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),

    -- Payment terms
    default_payment_terms TEXT,

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),

    -- Constraints
    CONSTRAINT suppliers_code_format CHECK (supplier_code ~ '^[A-Z]{3}$')
);

-- Unique constraint: one supplier code per organization
CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_org_code
ON suppliers(organization_id, supplier_code);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_suppliers_organization
ON suppliers(organization_id);

CREATE INDEX IF NOT EXISTS idx_suppliers_name
ON suppliers(organization_id, name);

CREATE INDEX IF NOT EXISTS idx_suppliers_active
ON suppliers(organization_id, is_active) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_suppliers_country
ON suppliers(organization_id, country);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;

-- Users can view suppliers in their organization
CREATE POLICY suppliers_select_policy ON suppliers
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_roles WHERE user_id = auth.uid()
            UNION
            SELECT id FROM organizations WHERE id = auth.uid()
        )
    );

-- Users with appropriate roles can insert suppliers
CREATE POLICY suppliers_insert_policy ON suppliers
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code IN ('admin', 'procurement', 'sales')
        )
    );

-- Users with appropriate roles can update suppliers
CREATE POLICY suppliers_update_policy ON suppliers
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code IN ('admin', 'procurement')
        )
    );

-- Only admins can delete suppliers
CREATE POLICY suppliers_delete_policy ON suppliers
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code = 'admin'
        )
    );

-- ============================================
-- TRIGGER FOR updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_suppliers_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS suppliers_update_timestamp ON suppliers;
CREATE TRIGGER suppliers_update_timestamp
    BEFORE UPDATE ON suppliers
    FOR EACH ROW
    EXECUTE FUNCTION update_suppliers_timestamp();

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE suppliers IS 'External supplier companies in the supply chain (v3.0)';
COMMENT ON COLUMN suppliers.supplier_code IS '3-letter unique code for the supplier within organization (e.g., CMT, RAR)';
COMMENT ON COLUMN suppliers.inn IS 'Russian tax ID (ИНН) - 10 digits for legal entities, 12 for individuals';
COMMENT ON COLUMN suppliers.kpp IS 'Russian tax registration code (КПП) - 9 digits';
COMMENT ON COLUMN suppliers.default_payment_terms IS 'Default payment terms text for contracts with this supplier';
