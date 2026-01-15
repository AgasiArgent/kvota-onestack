-- Migration: 026_create_brand_procurement_view.sql
-- Feature DB-009: Create brand_procurement_assignments view
-- Description: Creates a view alias for brand_assignments table and adds helper functions
-- Note: brand_assignments table already exists (migration 003) and serves as brand→procurement manager assignments

-- Create view alias for consistency with spec naming
-- This allows code to use brand_procurement_assignments as table name
CREATE OR REPLACE VIEW brand_procurement_assignments AS
SELECT
    id,
    organization_id,
    brand,
    user_id,
    created_at,
    created_by
FROM brand_assignments;

-- Make the view updatable (insertable, updatable, deletable)
-- This allows using the view as if it were the original table
CREATE OR REPLACE RULE brand_procurement_assignments_insert AS
ON INSERT TO brand_procurement_assignments
DO INSTEAD
INSERT INTO brand_assignments (id, organization_id, brand, user_id, created_at, created_by)
VALUES (
    COALESCE(NEW.id, gen_random_uuid()),
    NEW.organization_id,
    NEW.brand,
    NEW.user_id,
    COALESCE(NEW.created_at, NOW()),
    NEW.created_by
)
RETURNING *;

CREATE OR REPLACE RULE brand_procurement_assignments_update AS
ON UPDATE TO brand_procurement_assignments
DO INSTEAD
UPDATE brand_assignments SET
    organization_id = NEW.organization_id,
    brand = NEW.brand,
    user_id = NEW.user_id,
    created_by = NEW.created_by
WHERE id = OLD.id;

CREATE OR REPLACE RULE brand_procurement_assignments_delete AS
ON DELETE TO brand_procurement_assignments
DO INSTEAD
DELETE FROM brand_assignments WHERE id = OLD.id;

-- Helper function: Get procurement manager for a brand
CREATE OR REPLACE FUNCTION get_procurement_manager_for_brand(
    p_organization_id UUID,
    p_brand VARCHAR(255)
)
RETURNS UUID AS $$
BEGIN
    RETURN (
        SELECT user_id
        FROM brand_assignments
        WHERE organization_id = p_organization_id
        AND brand = p_brand
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- Helper function: Get all brands assigned to a procurement manager
CREATE OR REPLACE FUNCTION get_brands_for_procurement_manager(
    p_user_id UUID
)
RETURNS TABLE (
    brand VARCHAR(255),
    organization_id UUID,
    assigned_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ba.brand,
        ba.organization_id,
        ba.created_at AS assigned_at
    FROM brand_assignments ba
    WHERE ba.user_id = p_user_id
    ORDER BY ba.brand;
END;
$$ LANGUAGE plpgsql STABLE;

-- Helper function: Get all procurement managers with their assigned brands (for admin view)
CREATE OR REPLACE FUNCTION get_procurement_assignments_summary(
    p_organization_id UUID
)
RETURNS TABLE (
    user_id UUID,
    brand_count BIGINT,
    brands TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ba.user_id,
        COUNT(*)::BIGINT AS brand_count,
        ARRAY_AGG(ba.brand ORDER BY ba.brand) AS brands
    FROM brand_assignments ba
    WHERE ba.organization_id = p_organization_id
    GROUP BY ba.user_id
    ORDER BY brand_count DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Comment on the view
COMMENT ON VIEW brand_procurement_assignments IS 'Alias view for brand_assignments table - assigns brands to procurement managers';
