-- Migration: 002_create_user_roles_table
-- Description: Create junction table linking users to roles per organization
-- Author: Claude (autonomous session)
-- Date: 2025-01-15
-- Depends on: 001_create_roles_table

-- Create user_roles table
-- This table links users to roles within specific organizations
-- A user can have multiple roles in the same organization
CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- Unique constraint: user can have each role only once per organization
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_roles_unique
    ON user_roles(user_id, organization_id, role_id);

-- Index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id
    ON user_roles(user_id);

-- Index for fast lookups by organization
CREATE INDEX IF NOT EXISTS idx_user_roles_organization_id
    ON user_roles(organization_id);

-- Index for fast lookups by role
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id
    ON user_roles(role_id);

-- Composite index for common query pattern: get user's roles in org
CREATE INDEX IF NOT EXISTS idx_user_roles_user_org
    ON user_roles(user_id, organization_id);

-- Enable Row Level Security
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

-- Policy: Users can see their own roles
CREATE POLICY "user_roles_select_own" ON user_roles
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

-- Policy: Users can see roles of other users in their organization
CREATE POLICY "user_roles_select_org" ON user_roles
    FOR SELECT
    TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM user_roles WHERE user_id = auth.uid()
        )
    );

-- Policy: Only admins can insert/update/delete roles
-- Check if the current user has admin role in the same organization
CREATE POLICY "user_roles_admin_insert" ON user_roles
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = organization_id
            AND r.code = 'admin'
        )
    );

CREATE POLICY "user_roles_admin_delete" ON user_roles
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = user_roles.organization_id
            AND r.code = 'admin'
        )
    );

-- Add comments to table and columns
COMMENT ON TABLE user_roles IS 'Junction table linking users to roles within organizations';
COMMENT ON COLUMN user_roles.user_id IS 'Reference to auth.users';
COMMENT ON COLUMN user_roles.organization_id IS 'Reference to organizations - roles are organization-specific';
COMMENT ON COLUMN user_roles.role_id IS 'Reference to roles table';
COMMENT ON COLUMN user_roles.created_by IS 'User who assigned this role (admin)';
