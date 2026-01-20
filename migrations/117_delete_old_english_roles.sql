-- Delete old English-named roles that are no longer needed
-- Migration: 117_delete_old_english_roles.sql
--
-- Context: After migrating from old Kvota system, we have duplicate roles:
-- - Old roles with English names (ceo, cfo, customs_manager, etc.)
-- - New roles with Russian names (customs, finance, logistics, etc.)
--
-- This migration removes the old English-named roles since they are not used
-- and the new Russian-named roles are the current standard.
--
-- Safety check: None of these roles are assigned to users (verified on 2026-01-20)
-- They exist across multiple organizations (9-10 copies each) but are all unused.

-- First, verify no users have these roles (safety check)
DO $$
DECLARE
    user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO user_count
    FROM kvota.user_roles ur
    JOIN kvota.roles r ON r.id = ur.role_id
    WHERE r.slug IN (
        'ceo', 'cfo', 'customs_manager', 'financial_manager',
        'logistics_manager', 'procurement_manager', 'sales_manager', 'top_sales_manager'
    );

    IF user_count > 0 THEN
        RAISE EXCEPTION 'Cannot delete roles: % users are still assigned to old English-named roles', user_count;
    END IF;

    RAISE NOTICE 'Safety check passed: No users assigned to old roles';
END $$;

-- Delete old English-named roles (across all organizations)
DELETE FROM kvota.roles
WHERE slug IN (
    'ceo',                    -- Replaced by role-based approvals
    'cfo',                    -- Replaced by role-based approvals
    'customs_manager',        -- Replaced by 'customs' (Russian name)
    'financial_manager',      -- Replaced by 'finance' (Russian name)
    'logistics_manager',      -- Replaced by 'logistics' (Russian name)
    'procurement_manager',    -- Replaced by 'procurement' (Russian name)
    'sales_manager',          -- Replaced by 'sales' (Russian name)
    'top_sales_manager'       -- Replaced by 'top_manager' (Russian name)
);

-- Log the result
DO $$
DECLARE
    remaining_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_count
    FROM kvota.roles
    WHERE organization_id = '463060ad-4cfb-4ee5-b90c-f32b153c007a'
    OR is_system_role = true;

    RAISE NOTICE 'Old roles deleted. Remaining roles for main organization: %', remaining_count;
END $$;
