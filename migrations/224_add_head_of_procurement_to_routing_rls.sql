-- Migration: 224_add_head_of_procurement_to_routing_rls.sql
-- Description: Allow head_of_procurement role to manage brand_assignments and
--   route_procurement_group_assignments (INSERT, UPDATE, DELETE).
--   Also standardize brand_assignments policies to use r.slug (was r.code).

-- =============================================================================
-- brand_assignments: DROP old policies, CREATE new ones with r.slug
-- =============================================================================

-- INSERT
DROP POLICY IF EXISTS brand_assignments_insert_policy ON kvota.brand_assignments;
CREATE POLICY brand_assignments_insert_policy ON kvota.brand_assignments
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

-- UPDATE
DROP POLICY IF EXISTS brand_assignments_update_policy ON kvota.brand_assignments;
CREATE POLICY brand_assignments_update_policy ON kvota.brand_assignments
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

-- DELETE
DROP POLICY IF EXISTS brand_assignments_delete_policy ON kvota.brand_assignments;
CREATE POLICY brand_assignments_delete_policy ON kvota.brand_assignments
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
-- route_procurement_group_assignments: DROP old policies, CREATE new ones
-- =============================================================================

-- INSERT
DROP POLICY IF EXISTS route_procurement_group_insert_policy ON kvota.route_procurement_group_assignments;
CREATE POLICY route_procurement_group_insert_policy ON kvota.route_procurement_group_assignments
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

-- UPDATE
DROP POLICY IF EXISTS route_procurement_group_update_policy ON kvota.route_procurement_group_assignments;
CREATE POLICY route_procurement_group_update_policy ON kvota.route_procurement_group_assignments
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

-- DELETE
DROP POLICY IF EXISTS route_procurement_group_delete_policy ON kvota.route_procurement_group_assignments;
CREATE POLICY route_procurement_group_delete_policy ON kvota.route_procurement_group_assignments
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
