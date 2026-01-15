-- Migration: Create seller_companies table
-- Feature: DB-003
-- Description: Create seller_companies table for our legal entities used for selling
-- Part of v3.0: Supply chain entities (Supplier → Buyer Company → Seller Company → Customer)

-- ============================================
-- SELLER COMPANIES TABLE
-- ============================================
-- Our legal entities used for selling goods to customers
-- Level: QUOTE (one seller company per quote)
--
-- Examples:
-- - МАСТЕР БЭРИНГ ООО (MBR) - Россия
-- - РадРесурс ООО (RAR) - Россия
-- - ЦМТО1 ООО (CMT) - Россия
-- - GESTUS DIŞ TİCARET (GES) - Турция
-- - TEXCEL OTOMOTİV (TEX) - Турция

CREATE TABLE IF NOT EXISTS seller_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Company identification
    name VARCHAR(255) NOT NULL,
    supplier_code VARCHAR(3) NOT NULL,  -- 3-letter code (e.g., MBR, RAR, CMT, GES, TEX)

    -- Location
    country VARCHAR(100),

    -- Legal identifiers (Russian legal entity)
    inn VARCHAR(12),   -- ИНН (10 for legal entities, 12 for individual entrepreneurs)
    kpp VARCHAR(9),    -- КПП (9 digits)
    ogrn VARCHAR(15),  -- ОГРН (13 digits for legal entities, 15 for individual entrepreneurs)

    -- Registration address
    registration_address TEXT,

    -- Director information (for contracts/documents/specifications)
    general_director_name VARCHAR(255),
    general_director_position VARCHAR(100) DEFAULT 'Генеральный директор',

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),

    -- Constraints
    CONSTRAINT seller_companies_code_format CHECK (supplier_code ~ '^[A-Z]{3}$')
);

-- Unique constraint: one supplier code per organization
CREATE UNIQUE INDEX IF NOT EXISTS idx_seller_companies_org_code
ON seller_companies(organization_id, supplier_code);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_seller_companies_organization
ON seller_companies(organization_id);

CREATE INDEX IF NOT EXISTS idx_seller_companies_name
ON seller_companies(organization_id, name);

CREATE INDEX IF NOT EXISTS idx_seller_companies_active
ON seller_companies(organization_id, is_active) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_seller_companies_inn
ON seller_companies(organization_id, inn);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE seller_companies ENABLE ROW LEVEL SECURITY;

-- Users can view seller companies in their organization
CREATE POLICY seller_companies_select_policy ON seller_companies
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_roles WHERE user_id = auth.uid()
            UNION
            SELECT id FROM organizations WHERE id = auth.uid()
        )
    );

-- Users with appropriate roles can insert seller companies
CREATE POLICY seller_companies_insert_policy ON seller_companies
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code IN ('admin', 'finance')
        )
    );

-- Users with appropriate roles can update seller companies
CREATE POLICY seller_companies_update_policy ON seller_companies
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code IN ('admin', 'finance')
        )
    );

-- Only admins can delete seller companies
CREATE POLICY seller_companies_delete_policy ON seller_companies
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

CREATE OR REPLACE FUNCTION update_seller_companies_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS seller_companies_update_timestamp ON seller_companies;
CREATE TRIGGER seller_companies_update_timestamp
    BEFORE UPDATE ON seller_companies
    FOR EACH ROW
    EXECUTE FUNCTION update_seller_companies_timestamp();

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE seller_companies IS 'Our legal entities used for selling to customers (v3.0)';
COMMENT ON COLUMN seller_companies.supplier_code IS '3-letter unique code for the seller company within organization (used in IDN)';
COMMENT ON COLUMN seller_companies.inn IS 'Russian tax ID (ИНН) - 10 digits for legal entities, 12 for individual entrepreneurs';
COMMENT ON COLUMN seller_companies.kpp IS 'Russian tax registration code (КПП) - 9 digits';
COMMENT ON COLUMN seller_companies.ogrn IS 'Russian state registration number (ОГРН) - 13 digits for legal entities';
COMMENT ON COLUMN seller_companies.registration_address IS 'Legal registration address of the company';
COMMENT ON COLUMN seller_companies.general_director_name IS 'Name of the general director for document signing';
COMMENT ON COLUMN seller_companies.general_director_position IS 'Position title of the director (default: Генеральный директор)';
