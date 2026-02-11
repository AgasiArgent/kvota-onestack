-- Migration 168: Clean up deprecated and duplicate roles
-- Context: DB had 86 role rows for ~15 unique slugs.
-- Deprecated English-named roles had 0 user_roles assignments,
-- but organization_members.role_id still references some of them.
-- Step 1: Remap org_members to active equivalents
-- Step 2: Delete deprecated roles
-- Step 3: Deduplicate sales_manager (10 rows → 1)

BEGIN;

-- 1. Remap organization_members.role_id from deprecated → active roles
-- sales_manager (12 members) → sales
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'sales' AND is_system_role = true LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'sales_manager');

-- financial_manager (1 member) → finance
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'finance' AND is_system_role = true LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'financial_manager');

-- marketing_director (3 members) → sales (closest match)
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'sales' AND is_system_role = true LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'marketing_director');

-- 2. Remap any remaining org_members pointing to other deprecated roles (safety net)
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'admin' AND is_system_role = true LIMIT 1)
WHERE role_id IN (
    SELECT id FROM kvota.roles
    WHERE slug IN ('ceo', 'cfo', 'customs_manager', 'financial_admin',
                   'logistics_manager', 'procurement_manager', 'top_sales_manager')
);

-- 3. Delete deprecated roles (now safe — no FK references remain)
DELETE FROM kvota.roles
WHERE slug IN (
    'ceo', 'cfo', 'customs_manager', 'financial_admin',
    'financial_manager', 'logistics_manager', 'marketing_director',
    'procurement_manager', 'top_sales_manager'
);

-- 4. Deduplicate sales_manager: keep oldest row, delete copies
-- First remap any org_members pointing to duplicate IDs
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'sales_manager' ORDER BY created_at ASC LIMIT 1)
WHERE role_id IN (
    SELECT id FROM kvota.roles WHERE slug = 'sales_manager'
    AND id != (SELECT id FROM kvota.roles WHERE slug = 'sales_manager' ORDER BY created_at ASC LIMIT 1)
);

DELETE FROM kvota.roles
WHERE slug = 'sales_manager'
AND id != (SELECT id FROM kvota.roles WHERE slug = 'sales_manager' ORDER BY created_at ASC LIMIT 1);

COMMIT;
