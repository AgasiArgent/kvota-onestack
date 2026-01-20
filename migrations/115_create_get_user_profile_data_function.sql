-- Migration: 115_create_get_user_profile_data_function
-- Description: Create RPC function to get user profile data with email and other info

CREATE OR REPLACE FUNCTION kvota.get_user_profile_data(
    p_user_id UUID,
    p_organization_id UUID
)
RETURNS TABLE (
    email TEXT,
    phone TEXT,
    created_at TIMESTAMPTZ,
    full_name TEXT,
    "position" TEXT,
    department_name TEXT,
    sales_group_name TEXT,
    manager_email TEXT,
    location TEXT,
    role_name TEXT,
    role_slug TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.email::TEXT,
        u.phone::TEXT,
        u.created_at,
        up.full_name::TEXT,
        up."position"::TEXT,
        d.name::TEXT AS department_name,
        sg.name::TEXT AS sales_group_name,
        manager.email::TEXT AS manager_email,
        up.location::TEXT,
        r.name::TEXT AS role_name,
        r.slug::TEXT AS role_slug
    FROM auth.users u
    INNER JOIN kvota.organization_members om ON om.user_id = u.id
        AND om.organization_id = p_organization_id
        AND om.status = 'active'
    LEFT JOIN kvota.user_profiles up ON up.user_id = u.id
        AND up.organization_id = p_organization_id
    LEFT JOIN kvota.departments d ON d.id = up.department_id
    LEFT JOIN kvota.sales_groups sg ON sg.id = up.sales_group_id
    LEFT JOIN auth.users manager ON manager.id = up.manager_id
    LEFT JOIN kvota.roles r ON r.id = om.role_id
    WHERE u.id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION kvota.get_user_profile_data(UUID, UUID) TO authenticated;

-- Add comment
COMMENT ON FUNCTION kvota.get_user_profile_data IS 'Get comprehensive user profile data including email, profile fields, and role information';
