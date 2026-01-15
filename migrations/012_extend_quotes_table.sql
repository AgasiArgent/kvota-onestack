-- Migration: Extend quotes table with workflow fields
-- Feature #12: Расширить таблицу quotes
-- Description: Add workflow_status, deal_type, assigned_*_users, *_completed_at fields
-- Created: 2025-01-15

-- =============================================================================
-- ADD NEW COLUMNS TO QUOTES TABLE
-- =============================================================================

-- Workflow status - tracks the current stage of the quote in the business process
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS workflow_status VARCHAR(50) DEFAULT 'draft';

COMMENT ON COLUMN quotes.workflow_status IS 'Current workflow status: draft, pending_procurement, pending_logistics, pending_customs, pending_sales_review, pending_quote_control, pending_approval, approved, sent_to_client, client_negotiation, pending_spec_control, pending_signature, deal, rejected, cancelled';

-- Deal type - differentiates between supply and transit deals (affects markup)
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS deal_type VARCHAR(20) DEFAULT NULL;

COMMENT ON COLUMN quotes.deal_type IS 'Type of deal: supply (поставка) or transit (транзит) - affects pricing markup';

-- Assigned procurement users - array of user IDs for procurement managers (one per brand)
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS assigned_procurement_users UUID[] DEFAULT '{}';

COMMENT ON COLUMN quotes.assigned_procurement_users IS 'Array of user IDs for procurement managers assigned to evaluate brands in this quote';

-- Assigned logistics user - single user responsible for logistics calculation
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS assigned_logistics_user UUID DEFAULT NULL;

COMMENT ON COLUMN quotes.assigned_logistics_user IS 'User ID of the logistics manager assigned to this quote';

-- Assigned customs user - single user responsible for customs data
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS assigned_customs_user UUID DEFAULT NULL;

COMMENT ON COLUMN quotes.assigned_customs_user IS 'User ID of the customs manager (Олег Князев) assigned to this quote';

-- Timestamps for tracking completion of parallel stages
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

COMMENT ON COLUMN quotes.procurement_completed_at IS 'Timestamp when all procurement evaluations were completed';

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS logistics_completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

COMMENT ON COLUMN quotes.logistics_completed_at IS 'Timestamp when logistics calculation was completed';

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS customs_completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

COMMENT ON COLUMN quotes.customs_completed_at IS 'Timestamp when customs data entry was completed';

-- Current version ID - the selected version for specification generation
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS current_version_id UUID DEFAULT NULL;

COMMENT ON COLUMN quotes.current_version_id IS 'ID of the quote version selected for specification generation (after client approval)';

-- =============================================================================
-- ADD CONSTRAINTS
-- =============================================================================

-- Workflow status constraint - only allow valid status values
ALTER TABLE quotes
DROP CONSTRAINT IF EXISTS quotes_workflow_status_check;

ALTER TABLE quotes
ADD CONSTRAINT quotes_workflow_status_check CHECK (
    workflow_status IS NULL OR
    workflow_status IN (
        'draft',
        'pending_procurement',
        'pending_logistics',
        'pending_customs',
        'pending_sales_review',
        'pending_quote_control',
        'pending_approval',
        'approved',
        'sent_to_client',
        'client_negotiation',
        'pending_spec_control',
        'pending_signature',
        'deal',
        'rejected',
        'cancelled'
    )
);

-- Deal type constraint - only allow valid values
ALTER TABLE quotes
DROP CONSTRAINT IF EXISTS quotes_deal_type_check;

ALTER TABLE quotes
ADD CONSTRAINT quotes_deal_type_check CHECK (
    deal_type IS NULL OR
    deal_type IN ('supply', 'transit')
);

-- Foreign key for current_version_id (if quote_versions table exists)
-- Note: Using DO block to check if the constraint already exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_current_version_id_fkey'
    ) THEN
        ALTER TABLE quotes
        ADD CONSTRAINT quotes_current_version_id_fkey
        FOREIGN KEY (current_version_id)
        REFERENCES quote_versions(id)
        ON DELETE SET NULL;
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        -- quote_versions table doesn't exist yet, skip FK constraint
        RAISE NOTICE 'quote_versions table not found, skipping FK constraint';
END $$;

-- Foreign key for assigned_logistics_user
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_assigned_logistics_user_fkey'
    ) THEN
        ALTER TABLE quotes
        ADD CONSTRAINT quotes_assigned_logistics_user_fkey
        FOREIGN KEY (assigned_logistics_user)
        REFERENCES auth.users(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- Foreign key for assigned_customs_user
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_assigned_customs_user_fkey'
    ) THEN
        ALTER TABLE quotes
        ADD CONSTRAINT quotes_assigned_customs_user_fkey
        FOREIGN KEY (assigned_customs_user)
        REFERENCES auth.users(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- =============================================================================
-- ADD INDEXES FOR QUERY PERFORMANCE
-- =============================================================================

-- Index on workflow_status for filtering quotes by status
CREATE INDEX IF NOT EXISTS idx_quotes_workflow_status
ON quotes(workflow_status);

-- Index on deal_type for filtering
CREATE INDEX IF NOT EXISTS idx_quotes_deal_type
ON quotes(deal_type);

-- Index on assigned_logistics_user for finding quotes assigned to a logistics user
CREATE INDEX IF NOT EXISTS idx_quotes_assigned_logistics_user
ON quotes(assigned_logistics_user)
WHERE assigned_logistics_user IS NOT NULL;

-- Index on assigned_customs_user for finding quotes assigned to a customs user
CREATE INDEX IF NOT EXISTS idx_quotes_assigned_customs_user
ON quotes(assigned_customs_user)
WHERE assigned_customs_user IS NOT NULL;

-- Composite index for finding quotes by organization and status
CREATE INDEX IF NOT EXISTS idx_quotes_organization_workflow_status
ON quotes(organization_id, workflow_status);

-- GIN index for array search on assigned_procurement_users
CREATE INDEX IF NOT EXISTS idx_quotes_assigned_procurement_users
ON quotes USING GIN(assigned_procurement_users);

-- =============================================================================
-- ADD COMMENT TO TABLE
-- =============================================================================

COMMENT ON TABLE quotes IS 'Commercial proposals (КП) with multi-role workflow support. Extended with workflow_status, deal_type, role assignments, and completion timestamps.';

-- =============================================================================
-- UPDATE EXISTING QUOTES TO HAVE DEFAULT STATUS
-- =============================================================================

-- Set workflow_status to 'draft' for any existing quotes that don't have it set
UPDATE quotes
SET workflow_status = 'draft'
WHERE workflow_status IS NULL;
