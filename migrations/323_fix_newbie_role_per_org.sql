-- Migration: Fix newbie role insert — kvota.roles has UNIQUE(organization_id, slug)
-- Created: 2026-05-24
-- Context: m321 failed on prod because it used ON CONFLICT (slug) but the only
-- unique constraint is (organization_id, slug). Roles in this project are
-- per-organization (is_system_role=false), only `admin` is system-wide.
-- This migration inserts `newbie` for ALL existing organizations.

BEGIN;

INSERT INTO kvota.roles (slug, name, is_system_role, organization_id)
SELECT 'newbie', 'Новичок', false, o.id
FROM kvota.organizations o
WHERE NOT EXISTS (
  SELECT 1 FROM kvota.roles r
  WHERE r.organization_id = o.id AND r.slug = 'newbie'
);

COMMIT;
