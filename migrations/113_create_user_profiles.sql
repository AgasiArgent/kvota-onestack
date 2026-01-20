-- Migration: 113_create_user_profiles
-- Description: Create user_profiles table for extended user information

-- Create user_profiles table
CREATE TABLE IF NOT EXISTS kvota.user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,

    -- Basic information
    full_name VARCHAR(255),
    position VARCHAR(100),

    -- Department and group
    department_id UUID REFERENCES kvota.departments(id) ON DELETE SET NULL,
    sales_group_id UUID REFERENCES kvota.sales_groups(id) ON DELETE SET NULL,

    -- Manager
    manager_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,

    -- Contact info (phone is already in auth.users, but can be duplicated here)
    phone VARCHAR(50),

    -- Location
    location VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),

    -- Constraint: one profile per user per organization
    CONSTRAINT user_profiles_user_org_unique UNIQUE (user_id, organization_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON kvota.user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_organization_id ON kvota.user_profiles(organization_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_department_id ON kvota.user_profiles(department_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_sales_group_id ON kvota.user_profiles(sales_group_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_manager_id ON kvota.user_profiles(manager_id);

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION kvota.update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_user_profiles_updated_at
    BEFORE UPDATE ON kvota.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_user_profiles_updated_at();

-- RLS policies
ALTER TABLE kvota.user_profiles ENABLE ROW LEVEL SECURITY;

-- Users can view profiles in their organization
CREATE POLICY "Users can view profiles in their organization"
    ON kvota.user_profiles FOR SELECT
    TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id
            FROM kvota.organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
        )
    );

-- Users can update their own profile
CREATE POLICY "Users can update their own profile"
    ON kvota.user_profiles FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Users can insert their own profile
CREATE POLICY "Users can insert their own profile"
    ON kvota.user_profiles FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

-- Admins can update any profile in their organization
CREATE POLICY "Admins can update profiles in their organization"
    ON kvota.user_profiles FOR UPDATE
    TO authenticated
    USING (
        organization_id IN (
            SELECT om.organization_id
            FROM kvota.organization_members om
            JOIN kvota.roles r ON r.id = om.role_id
            WHERE om.user_id = auth.uid()
            AND om.status = 'active'
            AND r.slug = 'admin'
        )
    );
