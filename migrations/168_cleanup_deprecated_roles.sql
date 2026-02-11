-- Migration 168: Clean up deprecated and duplicate roles
-- Context: DB had 86 role rows for ~15 unique slugs.
-- Deprecated English-named roles had 0 user assignments.
-- sales_manager had 10 duplicate rows.

BEGIN;

-- 1. Delete deprecated roles (confirmed 0 user assignments on all)
DELETE FROM kvota.roles
WHERE slug IN (
    'ceo', 'cfo', 'customs_manager', 'financial_admin',
    'financial_manager', 'logistics_manager', 'marketing_director',
    'procurement_manager', 'top_sales_manager'
);

-- 2. Deduplicate sales_manager: keep oldest row, delete copies
DELETE FROM kvota.roles
WHERE slug = 'sales_manager'
AND id NOT IN (
    SELECT id FROM kvota.roles
    WHERE slug = 'sales_manager'
    ORDER BY created_at ASC
    LIMIT 1
);

COMMIT;
