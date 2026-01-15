-- Migration: 027_create_route_logistics_assignments_table.sql
-- Feature: DB-010
-- Description: Assign routes to logistics managers with pattern matching
-- Pattern examples: "Китай-*", "Турция-Москва", "*-Москва", etc.

-- =============================================================================
-- TABLE: route_logistics_assignments
-- =============================================================================

CREATE TABLE IF NOT EXISTS route_logistics_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Route pattern for matching (uses LIKE or regex)
    -- Examples: "Китай-*", "Турция-Москва", "*-Россия"
    route_pattern VARCHAR(255) NOT NULL,

    -- Assigned logistics manager
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,

    -- Ensure unique route patterns per organization
    CONSTRAINT route_logistics_assignments_unique_pattern
        UNIQUE (organization_id, route_pattern)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for finding assignments by organization
CREATE INDEX IF NOT EXISTS idx_route_logistics_assignments_org
    ON route_logistics_assignments(organization_id);

-- Index for finding assignments by user
CREATE INDEX IF NOT EXISTS idx_route_logistics_assignments_user
    ON route_logistics_assignments(user_id);

-- Index for pattern matching (trigram for partial matches)
CREATE INDEX IF NOT EXISTS idx_route_logistics_assignments_pattern
    ON route_logistics_assignments USING gin (route_pattern gin_trgm_ops);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to match a route against patterns and find the responsible logistics manager
-- Route format: "origin_country-destination_city" e.g., "Китай-Москва", "Турция-Санкт-Петербург"
CREATE OR REPLACE FUNCTION match_route_to_logistics_manager(
    p_organization_id UUID,
    p_route TEXT
) RETURNS UUID AS $$
DECLARE
    v_user_id UUID;
BEGIN
    -- Try to find exact match first
    SELECT user_id INTO v_user_id
    FROM route_logistics_assignments
    WHERE organization_id = p_organization_id
      AND route_pattern = p_route
    LIMIT 1;

    IF v_user_id IS NOT NULL THEN
        RETURN v_user_id;
    END IF;

    -- Try to match with wildcards (convert * to SQL LIKE pattern)
    -- Priority: more specific patterns first (fewer wildcards)
    SELECT user_id INTO v_user_id
    FROM route_logistics_assignments
    WHERE organization_id = p_organization_id
      AND p_route LIKE replace(replace(route_pattern, '*', '%'), '?', '_')
    ORDER BY
        -- Prefer patterns with fewer wildcards (more specific)
        (length(route_pattern) - length(replace(route_pattern, '*', ''))) ASC,
        -- Then prefer longer patterns
        length(route_pattern) DESC
    LIMIT 1;

    RETURN v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get all routes assigned to a logistics manager
CREATE OR REPLACE FUNCTION get_routes_for_logistics_manager(
    p_organization_id UUID,
    p_user_id UUID
) RETURNS TABLE (
    assignment_id UUID,
    route_pattern VARCHAR(255),
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        rla.id,
        rla.route_pattern,
        rla.created_at
    FROM route_logistics_assignments rla
    WHERE rla.organization_id = p_organization_id
      AND rla.user_id = p_user_id
    ORDER BY rla.route_pattern;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get logistics manager for a specific origin-destination pair
-- Builds the route string from origin and destination locations
CREATE OR REPLACE FUNCTION get_logistics_manager_for_locations(
    p_organization_id UUID,
    p_origin_country TEXT,
    p_destination_city TEXT
) RETURNS UUID AS $$
DECLARE
    v_route TEXT;
BEGIN
    -- Build route string
    v_route := COALESCE(p_origin_country, '*') || '-' || COALESCE(p_destination_city, '*');

    -- Use the pattern matching function
    RETURN match_route_to_logistics_manager(p_organization_id, v_route);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get summary of route assignments
CREATE OR REPLACE FUNCTION get_route_assignments_summary(
    p_organization_id UUID
) RETURNS TABLE (
    user_id UUID,
    user_email TEXT,
    routes_count BIGINT,
    patterns TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        rla.user_id,
        au.email,
        COUNT(*)::BIGINT AS routes_count,
        array_agg(rla.route_pattern ORDER BY rla.route_pattern) AS patterns
    FROM route_logistics_assignments rla
    JOIN auth.users au ON au.id = rla.user_id
    WHERE rla.organization_id = p_organization_id
    GROUP BY rla.user_id, au.email
    ORDER BY routes_count DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to test if a route pattern is valid
CREATE OR REPLACE FUNCTION is_valid_route_pattern(p_pattern TEXT) RETURNS BOOLEAN AS $$
BEGIN
    -- Pattern should contain a hyphen (origin-destination separator)
    IF position('-' IN p_pattern) = 0 THEN
        RETURN FALSE;
    END IF;

    -- Pattern should not be empty
    IF length(trim(p_pattern)) = 0 THEN
        RETURN FALSE;
    END IF;

    -- Pattern should contain at least one non-wildcard character
    IF replace(replace(p_pattern, '*', ''), '-', '') = '' THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Add check constraint for valid route patterns
ALTER TABLE route_logistics_assignments
    ADD CONSTRAINT route_logistics_assignments_valid_pattern
    CHECK (is_valid_route_pattern(route_pattern));

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE route_logistics_assignments ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view assignments in their organization
CREATE POLICY route_logistics_assignments_select_policy ON route_logistics_assignments
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_roles WHERE user_id = auth.uid()
        )
    );

-- Policy: Only admins can insert assignments
CREATE POLICY route_logistics_assignments_insert_policy ON route_logistics_assignments
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.code IN ('admin', 'head_of_logistics')
        )
    );

-- Policy: Only admins can update assignments
CREATE POLICY route_logistics_assignments_update_policy ON route_logistics_assignments
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.code IN ('admin', 'head_of_logistics')
        )
    );

-- Policy: Only admins can delete assignments
CREATE POLICY route_logistics_assignments_delete_policy ON route_logistics_assignments
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.code IN ('admin', 'head_of_logistics')
        )
    );

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE route_logistics_assignments IS
    'Assigns routes to logistics managers using pattern matching. Routes are specified as "origin-destination" patterns with optional wildcards (*).';

COMMENT ON COLUMN route_logistics_assignments.route_pattern IS
    'Route pattern in format "origin-destination". Supports wildcards (*). Examples: "Китай-*" (all from China), "Турция-Москва" (specific route), "*-Санкт-Петербург" (all to St. Petersburg)';

COMMENT ON FUNCTION match_route_to_logistics_manager IS
    'Matches a route string (e.g., "Китай-Москва") against patterns to find the responsible logistics manager. Returns NULL if no match found.';

COMMENT ON FUNCTION get_logistics_manager_for_locations IS
    'Finds logistics manager for a route given origin country and destination city. Builds the route string and matches against patterns.';
