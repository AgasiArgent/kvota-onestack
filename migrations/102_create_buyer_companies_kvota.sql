-- ===========================================================================
-- Migration 102: Create buyer_companies table in kvota schema
-- ===========================================================================
-- Description: Create buyer_companies table for our legal entities used for purchasing
-- Part of v3.0: Supply chain entities (Supplier → Buyer Company → Seller Company → Customer)
-- Prerequisites: Migration 101 must be applied (tables moved to kvota schema)
-- Created: 2026-01-20
-- ===========================================================================

-- ============================================
-- BUYER COMPANIES TABLE
-- ============================================
-- Our legal entities used for purchasing goods from suppliers
-- Level: ITEM (each quote_item can have its own buyer company)

CREATE TABLE IF NOT EXISTS kvota.buyer_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,

    -- Company identification
    name VARCHAR(255) NOT NULL,
    company_code VARCHAR(3) NOT NULL,  -- 3-letter code (e.g., CMT, ZAK)

    -- Location
    country VARCHAR(100),

    -- Legal identifiers (Russian legal entity)
    inn VARCHAR(12),   -- ИНН (10 for legal entities)
    kpp VARCHAR(9),    -- КПП (9 digits)
    ogrn VARCHAR(15),  -- ОГРН (13 digits for legal entities, 15 for individual entrepreneurs)

    -- Registration address
    registration_address TEXT,

    -- Director information (for contracts/documents)
    general_director_name VARCHAR(255),
    general_director_position VARCHAR(100) DEFAULT 'Генеральный директор',

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),

    -- Constraints
    CONSTRAINT buyer_companies_code_format CHECK (company_code ~ '^[A-Z]{3}$')
);

-- Unique constraint: one company code per organization
CREATE UNIQUE INDEX IF NOT EXISTS idx_buyer_companies_org_code
ON kvota.buyer_companies(organization_id, company_code);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_buyer_companies_organization
ON kvota.buyer_companies(organization_id);

CREATE INDEX IF NOT EXISTS idx_buyer_companies_name
ON kvota.buyer_companies(organization_id, name);

CREATE INDEX IF NOT EXISTS idx_buyer_companies_active
ON kvota.buyer_companies(organization_id, is_active) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_buyer_companies_inn
ON kvota.buyer_companies(organization_id, inn);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE kvota.buyer_companies ENABLE ROW LEVEL SECURITY;

-- Users can view buyer companies in their organization
CREATE POLICY buyer_companies_select_policy ON kvota.buyer_companies
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_roles WHERE user_id = auth.uid()
            UNION
            SELECT id FROM kvota.organizations WHERE id = auth.uid()
        )
    );

-- Users with appropriate roles can insert buyer companies
CREATE POLICY buyer_companies_insert_policy ON kvota.buyer_companies
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

-- Users with appropriate roles can update buyer companies
CREATE POLICY buyer_companies_update_policy ON kvota.buyer_companies
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

-- Only admins can delete buyer companies
CREATE POLICY buyer_companies_delete_policy ON kvota.buyer_companies
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- TRIGGER FOR updated_at
-- ============================================

CREATE OR REPLACE FUNCTION kvota.update_buyer_companies_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS buyer_companies_update_timestamp ON kvota.buyer_companies;
CREATE TRIGGER buyer_companies_update_timestamp
    BEFORE UPDATE ON kvota.buyer_companies
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_buyer_companies_timestamp();

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE kvota.buyer_companies IS 'Our legal entities used for purchasing from suppliers (v3.0)';
COMMENT ON COLUMN kvota.buyer_companies.company_code IS '3-letter unique code for the buyer company within organization';
COMMENT ON COLUMN kvota.buyer_companies.inn IS 'Russian tax ID (ИНН) - 10 digits for legal entities';
COMMENT ON COLUMN kvota.buyer_companies.kpp IS 'Russian tax registration code (КПП) - 9 digits';
COMMENT ON COLUMN kvota.buyer_companies.ogrn IS 'Russian state registration number (ОГРН) - 13 digits';
COMMENT ON COLUMN kvota.buyer_companies.registration_address IS 'Legal registration address of the company';
COMMENT ON COLUMN kvota.buyer_companies.general_director_name IS 'Name of the general director for document signing';
COMMENT ON COLUMN kvota.buyer_companies.general_director_position IS 'Position title of the director (default: Генеральный директор)';

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 102: buyer_companies table created successfully in kvota schema';
END $$;
