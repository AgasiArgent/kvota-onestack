-- Migration 013: Extend quote_items table with workflow fields
-- Feature #13: Расширить таблицу quote_items
-- Date: 2025-01-15
-- Description: Add procurement tracking, customs data, and assignment fields

-- =============================================================================
-- ADD NEW COLUMNS TO QUOTE_ITEMS TABLE
-- =============================================================================

-- Procurement assignment - which procurement manager handles this item
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS assigned_procurement_user UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- Procurement status - tracks whether this item's procurement is complete
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_status VARCHAR(20) DEFAULT 'pending';

-- Procurement completion tracking
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_completed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- Customs data - HS code (ТН ВЭД)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS hs_code VARCHAR(20);

-- Customs duty percentage or fixed amount
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS customs_duty DECIMAL(15, 4) DEFAULT 0;

-- Customs extra charges
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS customs_extra DECIMAL(15, 2) DEFAULT 0;

-- =============================================================================
-- ADD CONSTRAINTS
-- =============================================================================

-- Check constraint for procurement_status
ALTER TABLE quote_items
ADD CONSTRAINT quote_items_procurement_status_check
CHECK (procurement_status IN ('pending', 'in_progress', 'completed'));

-- =============================================================================
-- CREATE INDEXES
-- =============================================================================

-- Index for finding items by assigned procurement user
CREATE INDEX IF NOT EXISTS idx_quote_items_assigned_procurement_user
ON quote_items(assigned_procurement_user)
WHERE assigned_procurement_user IS NOT NULL;

-- Index for filtering by procurement status
CREATE INDEX IF NOT EXISTS idx_quote_items_procurement_status
ON quote_items(procurement_status);

-- Composite index for procurement dashboard queries
CREATE INDEX IF NOT EXISTS idx_quote_items_procurement_user_status
ON quote_items(assigned_procurement_user, procurement_status)
WHERE assigned_procurement_user IS NOT NULL;

-- Index for quote + procurement status (finding incomplete items for a quote)
CREATE INDEX IF NOT EXISTS idx_quote_items_quote_procurement_status
ON quote_items(quote_id, procurement_status);

-- =============================================================================
-- ADD COLUMN COMMENTS
-- =============================================================================

COMMENT ON COLUMN quote_items.assigned_procurement_user IS 'Procurement manager assigned to this item (based on brand)';
COMMENT ON COLUMN quote_items.procurement_status IS 'Procurement evaluation status: pending, in_progress, completed';
COMMENT ON COLUMN quote_items.procurement_completed_at IS 'When procurement evaluation was completed';
COMMENT ON COLUMN quote_items.procurement_completed_by IS 'User who completed the procurement evaluation';
COMMENT ON COLUMN quote_items.hs_code IS 'Customs HS code (ТН ВЭД) for this product';
COMMENT ON COLUMN quote_items.customs_duty IS 'Customs duty percentage or amount';
COMMENT ON COLUMN quote_items.customs_extra IS 'Additional customs-related charges';

-- =============================================================================
-- FUNCTION: Auto-assign procurement user based on brand
-- =============================================================================

CREATE OR REPLACE FUNCTION assign_procurement_user_by_brand()
RETURNS TRIGGER AS $$
DECLARE
    v_org_id UUID;
    v_assigned_user UUID;
BEGIN
    -- Get organization_id from the parent quote
    SELECT organization_id INTO v_org_id
    FROM quotes
    WHERE id = NEW.quote_id;

    -- Look up the procurement manager for this brand
    IF NEW.brand IS NOT NULL AND v_org_id IS NOT NULL THEN
        SELECT user_id INTO v_assigned_user
        FROM brand_assignments
        WHERE organization_id = v_org_id
          AND LOWER(brand) = LOWER(NEW.brand);

        IF v_assigned_user IS NOT NULL THEN
            NEW.assigned_procurement_user := v_assigned_user;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to auto-assign on insert or brand change
DROP TRIGGER IF EXISTS trigger_assign_procurement_user ON quote_items;
CREATE TRIGGER trigger_assign_procurement_user
    BEFORE INSERT OR UPDATE OF brand ON quote_items
    FOR EACH ROW
    WHEN (NEW.brand IS NOT NULL)
    EXECUTE FUNCTION assign_procurement_user_by_brand();

-- =============================================================================
-- FUNCTION: Mark item procurement as complete
-- =============================================================================

CREATE OR REPLACE FUNCTION complete_item_procurement(
    p_item_id UUID,
    p_user_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE quote_items
    SET procurement_status = 'completed',
        procurement_completed_at = NOW(),
        procurement_completed_by = p_user_id
    WHERE id = p_item_id
      AND assigned_procurement_user = p_user_id
      AND procurement_status != 'completed';

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- FUNCTION: Check if all items for a quote have completed procurement
-- =============================================================================

CREATE OR REPLACE FUNCTION check_quote_procurement_complete(p_quote_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_pending_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_pending_count
    FROM quote_items
    WHERE quote_id = p_quote_id
      AND procurement_status != 'completed';

    RETURN v_pending_count = 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION assign_procurement_user_by_brand() TO authenticated;
GRANT EXECUTE ON FUNCTION complete_item_procurement(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION check_quote_procurement_complete(UUID) TO authenticated;
