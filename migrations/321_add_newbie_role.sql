-- Migration: Add 'newbie' role for parking inactive/terminated users
-- Created: 2026-05-24
-- Context: Testing 2 row 38p2 — placeholder role assigned by admin/head_of_*
-- when a user is no longer assigned to any functional role but still has
-- an account. Newbie-only users see an empty dashboard and a placeholder
-- prompting them to contact their manager.

BEGIN;

INSERT INTO kvota.roles (slug, name, is_system_role)
VALUES ('newbie', 'Новичок', false)
ON CONFLICT (slug) DO NOTHING;

COMMIT;
