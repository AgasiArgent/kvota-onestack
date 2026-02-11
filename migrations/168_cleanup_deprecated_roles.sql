-- Migration 168: Clean up deprecated and duplicate roles
-- Context: DB has 86 role rows for ~15 unique slugs.
-- Active roles (from kvota_roles_access.csv spec):
--   admin, sales, procurement, logistics, customs,
--   quote_controller, spec_controller, finance, top_manager
-- Deprecated roles to remove (with precise remappings):
--   sales_manager → sales, top_sales_manager → sales, marketing_director → sales,
--   customs_manager → customs, logistics_manager → logistics,
--   procurement_manager → procurement, financial_manager → finance,
--   financial_admin → admin, ceo → admin, cfo → admin
-- Also creates 3 missing roles from spec: head_of_sales, head_of_procurement, head_of_logistics

BEGIN;

-- 1. Precise remapping: organization_members.role_id from deprecated → active
-- sales_manager → sales
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'sales' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'sales_manager');

-- top_sales_manager → sales
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'sales' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'top_sales_manager');

-- marketing_director → sales
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'sales' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'marketing_director');

-- customs_manager → customs
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'customs' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'customs_manager');

-- logistics_manager → logistics
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'logistics' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'logistics_manager');

-- procurement_manager → procurement
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'procurement' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'procurement_manager');

-- financial_manager → finance
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'finance' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'financial_manager');

-- financial_admin → admin
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'admin' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'financial_admin');

-- ceo → admin
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'admin' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'ceo');

-- cfo → admin
UPDATE kvota.organization_members
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'admin' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'cfo');

-- 2. Also remap user_roles table (safety net — may have 0 rows but just in case)
UPDATE kvota.user_roles
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'sales' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug IN ('sales_manager', 'top_sales_manager', 'marketing_director'));

UPDATE kvota.user_roles
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'customs' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'customs_manager');

UPDATE kvota.user_roles
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'logistics' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'logistics_manager');

UPDATE kvota.user_roles
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'procurement' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'procurement_manager');

UPDATE kvota.user_roles
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'finance' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug = 'financial_manager');

UPDATE kvota.user_roles
SET role_id = (SELECT id FROM kvota.roles WHERE slug = 'admin' LIMIT 1)
WHERE role_id IN (SELECT id FROM kvota.roles WHERE slug IN ('financial_admin', 'ceo', 'cfo'));

-- 3. Delete all deprecated roles (now safe — no FK references remain)
DELETE FROM kvota.roles
WHERE slug IN (
    'ceo', 'cfo', 'customs_manager', 'financial_admin',
    'financial_manager', 'logistics_manager', 'marketing_director',
    'procurement_manager', 'sales_manager', 'top_sales_manager'
);

-- 4. Create missing roles from spec (head_of_* department leads)
INSERT INTO kvota.roles (slug, name, description, is_system_role, organization_id)
SELECT 'head_of_sales', 'Head of Sales', 'Руководитель отдела продаж', false, organization_id
FROM kvota.roles WHERE slug = 'sales' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO kvota.roles (slug, name, description, is_system_role, organization_id)
SELECT 'head_of_procurement', 'Head of Procurement', 'Руководитель отдела закупок', false, organization_id
FROM kvota.roles WHERE slug = 'procurement' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO kvota.roles (slug, name, description, is_system_role, organization_id)
SELECT 'head_of_logistics', 'Head of Logistics', 'Руководитель отдела логистики', false, organization_id
FROM kvota.roles WHERE slug = 'logistics' LIMIT 1
ON CONFLICT DO NOTHING;

COMMIT;
