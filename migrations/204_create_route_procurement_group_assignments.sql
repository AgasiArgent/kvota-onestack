-- Migration: 204_create_route_procurement_group_assignments.sql
-- Description: Map sales groups to procurement users for automatic routing.
-- When a sales manager belongs to a sales_group, quotes from that manager
-- are routed to the procurement user defined by this table.
-- This takes priority over brand-based routing (brand_assignments).

-- =============================================================================
-- TABLE: route_procurement_group_assignments
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.route_procurement_group_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,

    -- The sales group that triggers this routing rule
    sales_group_id UUID NOT NULL REFERENCES kvota.sales_groups(id) ON DELETE CASCADE,

    -- The procurement user to assign quotes to
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,

    -- One procurement user per sales group per organization
    CONSTRAINT route_procurement_group_unique
        UNIQUE (organization_id, sales_group_id)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_route_procurement_group_org
    ON kvota.route_procurement_group_assignments(organization_id);

CREATE INDEX IF NOT EXISTS idx_route_procurement_group_sales_group
    ON kvota.route_procurement_group_assignments(sales_group_id);

CREATE INDEX IF NOT EXISTS idx_route_procurement_group_user
    ON kvota.route_procurement_group_assignments(user_id);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE kvota.route_procurement_group_assignments ENABLE ROW LEVEL SECURITY;

-- Policy: All org members can read assignments (via user_roles, not organization_members)
CREATE POLICY route_procurement_group_select_policy
    ON kvota.route_procurement_group_assignments
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_roles WHERE user_id = auth.uid()
        )
    );

-- Policy: Only admins can insert assignments
CREATE POLICY route_procurement_group_insert_policy
    ON kvota.route_procurement_group_assignments
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin')
        )
    );

-- Policy: Only admins can update assignments
CREATE POLICY route_procurement_group_update_policy
    ON kvota.route_procurement_group_assignments
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin')
        )
    );

-- Policy: Only admins can delete assignments
CREATE POLICY route_procurement_group_delete_policy
    ON kvota.route_procurement_group_assignments
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin')
        )
    );

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE kvota.route_procurement_group_assignments IS
    'Maps sales groups to procurement users. When a sales manager belongs to a sales_group, all items in their quotes are routed to the mapped procurement user. Takes priority over brand-based routing.';

COMMENT ON COLUMN kvota.route_procurement_group_assignments.sales_group_id IS
    'The sales group (from kvota.sales_groups) that triggers this routing rule.';

COMMENT ON COLUMN kvota.route_procurement_group_assignments.user_id IS
    'The procurement user who will be assigned to all items in quotes from this sales group.';
