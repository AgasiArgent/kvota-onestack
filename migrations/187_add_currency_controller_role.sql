-- Migration 187: Add currency_controller role
-- Role for verifying and exporting currency invoices between group companies

INSERT INTO kvota.roles (organization_id, slug, name, description, is_system_role)
SELECT o.id, 'currency_controller', 'Контролёр валютных документов',
       'Проверка и экспорт валютных инвойсов между компаниями группы', false
FROM kvota.organizations o
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.roles
    WHERE slug = 'currency_controller' AND organization_id = o.id
);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (187, '187_add_currency_controller_role.sql', now())
ON CONFLICT (id) DO NOTHING;
