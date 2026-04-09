-- Migration: 255_drop_om_role_id
-- Description: Phase 2 (Contract) — drop deprecated organization_members.role_id column.
--   All code, RLS policies, and DB functions were migrated to user_roles in migration 254.
-- Author: Claude
-- Date: 2026-04-09
-- Depends on: 254_deprecate_om_role_id

-- Safety check: verify no policies still reference om.role_id
-- (If this fails, migration 254 was not fully applied)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_policies
    WHERE (qual LIKE '%om.role_id%' OR with_check LIKE '%om.role_id%')
      AND schemaname = 'kvota'
  ) THEN
    RAISE EXCEPTION 'RLS policies still reference om.role_id — run migration 254 first';
  END IF;
END $$;

-- Drop the FK constraint first (explicit for clarity)
ALTER TABLE kvota.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_id_fkey;

-- Drop the column
ALTER TABLE kvota.organization_members
  DROP COLUMN IF EXISTS role_id;
