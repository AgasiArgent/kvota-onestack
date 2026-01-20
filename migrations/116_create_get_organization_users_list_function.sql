-- Migration: 116_create_get_organization_users_list_function
-- Description: Create RPC function to get list of users in organization with email

CREATE OR REPLACE FUNCTION kvota.get_organization_users_list(
    p_organization_id UUID
)
RETURNS TABLE (
    id UUID,
    email TEXT,
    full_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id,
        u.email::TEXT,
        COALESCE(up.full_name, u.email)::TEXT AS full_name
    FROM auth.users u
    INNER JOIN kvota.organization_members om ON om.user_id = u.id
        AND om.organization_id = p_organization_id
        AND om.status = 'active'
    LEFT JOIN kvota.user_profiles up ON up.user_id = u.id
        AND up.organization_id = p_organization_id
    ORDER BY COALESCE(up.full_name, u.email);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION kvota.get_organization_users_list(UUID) TO authenticated;

-- Add comment
COMMENT ON FUNCTION kvota.get_organization_users_list IS 'Get list of active users in organization with email and full name';
