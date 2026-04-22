-- Migration 292: Add head_of_customs role (symmetric to head_of_logistics).
-- Wave 1 Task 6.1 of logistics-customs-redesign spec (R14).
--
-- One user can have both head_of_logistics and head_of_customs — Andrey already
-- plays both roles in the current team (see session notes 2026-04-22).
--
-- Idempotent: re-run safe.

INSERT INTO kvota.roles (slug, name, description, is_system_role, organization_id)
SELECT 'head_of_customs',
       'Руководитель таможни',
       'Назначает таможенников, видит все заявки таможни, управляет правилами маршрутов таможенных пользователей',
       false,
       o.id
FROM kvota.organizations o
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.roles r
    WHERE r.slug = 'head_of_customs' AND r.organization_id = o.id
);

COMMENT ON TABLE kvota.roles IS
    'Role definitions per organization. Added head_of_customs in m292 for symmetry with head_of_logistics.';

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (292, '292_head_of_customs_role', now())
ON CONFLICT (id) DO NOTHING;
