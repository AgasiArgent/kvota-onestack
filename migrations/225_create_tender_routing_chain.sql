-- Migration: 225_create_tender_routing_chain.sql
-- Description: Create tender_routing_chain table for defining the approval chain
--   that tender quotes pass through. Each step has a user and role label.

-- =============================================================================
-- TABLE: tender_routing_chain
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.tender_routing_chain (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_label VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,

    -- Each step_order is unique per organization
    CONSTRAINT tender_chain_unique_order UNIQUE (organization_id, step_order)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX idx_tender_routing_chain_org ON kvota.tender_routing_chain(organization_id);
CREATE INDEX idx_tender_routing_chain_user ON kvota.tender_routing_chain(user_id);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE kvota.tender_routing_chain ENABLE ROW LEVEL SECURITY;

-- SELECT: all org members can read the chain
CREATE POLICY tender_chain_select ON kvota.tender_routing_chain
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_roles WHERE user_id = auth.uid()
        )
    );

-- INSERT: admin + head_of_procurement
CREATE POLICY tender_chain_insert ON kvota.tender_routing_chain
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin', 'head_of_procurement')
        )
    );

-- UPDATE: admin + head_of_procurement
CREATE POLICY tender_chain_update ON kvota.tender_routing_chain
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin', 'head_of_procurement')
        )
    );

-- DELETE: admin + head_of_procurement
CREATE POLICY tender_chain_delete ON kvota.tender_routing_chain
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin', 'head_of_procurement')
        )
    );

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE kvota.tender_routing_chain IS
    'Defines the sequential approval chain for tender quotes. Each step assigns a user with a role label (e.g. "Руководитель закупок", "Финансовый контролёр").';

COMMENT ON COLUMN kvota.tender_routing_chain.step_order IS
    'Position in the chain (1-based). Unique per organization — determines the sequence of approvals.';

COMMENT ON COLUMN kvota.tender_routing_chain.user_id IS
    'The user responsible for this step in the tender routing chain.';

COMMENT ON COLUMN kvota.tender_routing_chain.role_label IS
    'Human-readable label for this step (e.g. "Руководитель закупок"). Not tied to kvota.roles — purely descriptive.';

COMMENT ON COLUMN kvota.tender_routing_chain.created_by IS
    'The admin or head_of_procurement who created this chain step.';
