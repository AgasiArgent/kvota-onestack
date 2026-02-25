-- Migration 184: Add training_manager role
-- training_manager: read-only viewer with impersonation for training/demos
-- Can view all interfaces and switch between roles, but cannot modify data

-- 1. Insert role (organization-scoped, not system role)
-- Check constraint: is_system_role = (organization_id IS NULL), so non-system roles need org_id
INSERT INTO kvota.roles (organization_id, slug, name, description, is_system_role)
SELECT o.id, 'training_manager', 'Менеджер обучения', 'Просмотр всех разделов и демонстрация ролей для обучения', false
FROM kvota.organizations o
WHERE NOT EXISTS (SELECT 1 FROM kvota.roles WHERE slug = 'training_manager' AND organization_id = o.id);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (184, '184_add_training_manager_role.sql', now())
ON CONFLICT (id) DO NOTHING;
