-- ===========================================================================
-- Migration 105: Create brand_supplier_assignments table in kvota schema
-- ===========================================================================
-- Description: Links brands to suppliers (which supplier provides which brand)
-- This is different from brand_assignments which links brands to procurement users
-- Prerequisites: Migration 101 must be applied (tables moved to kvota schema)
-- Created: 2026-01-20
-- ===========================================================================

-- Create brand_supplier_assignments table
CREATE TABLE IF NOT EXISTS kvota.brand_supplier_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    brand VARCHAR(255) NOT NULL,
    supplier_id UUID NOT NULL REFERENCES kvota.suppliers(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,  -- Primary supplier for this brand
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,

    -- One supplier can provide multiple brands, and one brand can have multiple suppliers
    -- The is_primary flag indicates the preferred/main supplier for the brand
    CONSTRAINT unique_brand_supplier_per_org UNIQUE (organization_id, brand, supplier_id)
);

-- Index for fast lookup by brand
CREATE INDEX idx_brand_supplier_assignments_brand ON kvota.brand_supplier_assignments(organization_id, brand);

-- Index for fast lookup by supplier
CREATE INDEX idx_brand_supplier_assignments_supplier ON kvota.brand_supplier_assignments(supplier_id);

-- Index for finding primary supplier for a brand
CREATE INDEX idx_brand_supplier_assignments_primary ON kvota.brand_supplier_assignments(organization_id, brand)
    WHERE is_primary = TRUE;

-- Enable Row Level Security
ALTER TABLE kvota.brand_supplier_assignments ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can view brand-supplier assignments in their organization
CREATE POLICY brand_supplier_assignments_select_policy ON kvota.brand_supplier_assignments
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid()
        )
    );

-- RLS Policy: Admin and procurement can insert assignments
CREATE POLICY brand_supplier_assignments_insert_policy ON kvota.brand_supplier_assignments
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_supplier_assignments.organization_id
            AND r.slug IN ('admin', 'procurement')
        )
    );

-- RLS Policy: Admin and procurement can update assignments
CREATE POLICY brand_supplier_assignments_update_policy ON kvota.brand_supplier_assignments
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_supplier_assignments.organization_id
            AND r.slug IN ('admin', 'procurement')
        )
    );

-- RLS Policy: Only admins can delete assignments
CREATE POLICY brand_supplier_assignments_delete_policy ON kvota.brand_supplier_assignments
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_supplier_assignments.organization_id
            AND r.slug = 'admin'
        )
    );

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION kvota.update_brand_supplier_assignments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER brand_supplier_assignments_updated_at_trigger
    BEFORE UPDATE ON kvota.brand_supplier_assignments
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_brand_supplier_assignments_updated_at();

-- Ensure only one primary supplier per brand per organization
CREATE OR REPLACE FUNCTION kvota.ensure_single_primary_brand_supplier()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_primary = TRUE THEN
        -- Remove primary flag from other suppliers for this brand
        UPDATE kvota.brand_supplier_assignments
        SET is_primary = FALSE
        WHERE organization_id = NEW.organization_id
          AND brand = NEW.brand
          AND id != NEW.id
          AND is_primary = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ensure_single_primary_brand_supplier_trigger
    AFTER INSERT OR UPDATE ON kvota.brand_supplier_assignments
    FOR EACH ROW
    WHEN (NEW.is_primary = TRUE)
    EXECUTE FUNCTION kvota.ensure_single_primary_brand_supplier();

-- Helper function: Get primary supplier for a brand
CREATE OR REPLACE FUNCTION kvota.get_primary_supplier_for_brand(
    p_organization_id UUID,
    p_brand VARCHAR
)
RETURNS UUID AS $$
    SELECT supplier_id
    FROM kvota.brand_supplier_assignments
    WHERE organization_id = p_organization_id
      AND brand = p_brand
      AND is_primary = TRUE
    LIMIT 1;
$$ LANGUAGE sql STABLE;

-- Helper function: Get all suppliers for a brand
CREATE OR REPLACE FUNCTION kvota.get_suppliers_for_brand(
    p_organization_id UUID,
    p_brand VARCHAR
)
RETURNS TABLE (
    supplier_id UUID,
    supplier_name VARCHAR,
    supplier_code VARCHAR,
    is_primary BOOLEAN
) AS $$
    SELECT
        bsa.supplier_id,
        s.name,
        s.supplier_code,
        bsa.is_primary
    FROM kvota.brand_supplier_assignments bsa
    JOIN kvota.suppliers s ON bsa.supplier_id = s.id
    WHERE bsa.organization_id = p_organization_id
      AND bsa.brand = p_brand
    ORDER BY bsa.is_primary DESC, s.name;
$$ LANGUAGE sql STABLE;

-- Helper function: Get all brands for a supplier
CREATE OR REPLACE FUNCTION kvota.get_brands_for_supplier(
    p_supplier_id UUID
)
RETURNS TABLE (
    brand VARCHAR,
    is_primary BOOLEAN
) AS $$
    SELECT
        bsa.brand,
        bsa.is_primary
    FROM kvota.brand_supplier_assignments bsa
    WHERE bsa.supplier_id = p_supplier_id
    ORDER BY bsa.is_primary DESC, bsa.brand;
$$ LANGUAGE sql STABLE;

-- Comments
COMMENT ON TABLE kvota.brand_supplier_assignments IS 'Links brands to suppliers - which supplier provides which brand';
COMMENT ON COLUMN kvota.brand_supplier_assignments.brand IS 'Brand name (matches brand field in products/quote_items)';
COMMENT ON COLUMN kvota.brand_supplier_assignments.supplier_id IS 'External supplier company that provides this brand';
COMMENT ON COLUMN kvota.brand_supplier_assignments.is_primary IS 'Whether this is the primary/preferred supplier for the brand';
COMMENT ON FUNCTION kvota.get_primary_supplier_for_brand IS 'Returns the primary supplier ID for a given brand in an organization';
COMMENT ON FUNCTION kvota.get_suppliers_for_brand IS 'Returns all suppliers for a brand with their details';
COMMENT ON FUNCTION kvota.get_brands_for_supplier IS 'Returns all brands provided by a supplier';

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 105: brand_supplier_assignments table created successfully in kvota schema';
    RAISE NOTICE 'Created 5 functions: updated_at trigger, ensure_single_primary, get_primary_supplier_for_brand, get_suppliers_for_brand, get_brands_for_supplier';
END $$;
