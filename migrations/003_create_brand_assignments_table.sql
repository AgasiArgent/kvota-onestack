-- Migration: 003_create_brand_assignments_table.sql
-- Feature #3: Create brand_assignments table
-- Description: Stores assignments of brands to procurement managers
-- Each brand in an organization can only be assigned to one procurement manager

-- Create brand_assignments table
CREATE TABLE IF NOT EXISTS brand_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    brand VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,

    -- Each brand can only be assigned to one user per organization
    CONSTRAINT unique_brand_per_org UNIQUE (organization_id, brand)
);

-- Index for fast lookup by user (which brands does this user manage)
CREATE INDEX IF NOT EXISTS idx_brand_assignments_user_id ON brand_assignments(user_id);

-- Index for fast lookup by organization
CREATE INDEX IF NOT EXISTS idx_brand_assignments_org_id ON brand_assignments(organization_id);

-- Composite index for finding brand manager in an organization
CREATE INDEX IF NOT EXISTS idx_brand_assignments_org_brand ON brand_assignments(organization_id, brand);

-- Enable Row Level Security
ALTER TABLE brand_assignments ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can view brand assignments in their organization
CREATE POLICY brand_assignments_select_policy ON brand_assignments
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
        )
    );

-- RLS Policy: Only admins can insert brand assignments
CREATE POLICY brand_assignments_insert_policy ON brand_assignments
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_assignments.organization_id
            AND r.code = 'admin'
        )
    );

-- RLS Policy: Only admins can update brand assignments
CREATE POLICY brand_assignments_update_policy ON brand_assignments
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_assignments.organization_id
            AND r.code = 'admin'
        )
    );

-- RLS Policy: Only admins can delete brand assignments
CREATE POLICY brand_assignments_delete_policy ON brand_assignments
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_assignments.organization_id
            AND r.code = 'admin'
        )
    );

-- Comment on table and columns
COMMENT ON TABLE brand_assignments IS 'Assigns brands to procurement managers - each brand can have only one manager per organization';
COMMENT ON COLUMN brand_assignments.id IS 'Unique identifier for the assignment';
COMMENT ON COLUMN brand_assignments.organization_id IS 'The organization this assignment belongs to';
COMMENT ON COLUMN brand_assignments.brand IS 'Brand name (matches brand field in quote_items)';
COMMENT ON COLUMN brand_assignments.user_id IS 'Procurement manager assigned to this brand';
COMMENT ON COLUMN brand_assignments.created_at IS 'When the assignment was created';
COMMENT ON COLUMN brand_assignments.created_by IS 'Admin who created this assignment';
