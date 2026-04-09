-- Migration 256: Create update_user_roles function
-- Description: Atomic role update with last-admin guard, empty-roles check, and invalid-slug validation

CREATE OR REPLACE FUNCTION kvota.update_user_roles(
  p_user_id UUID,
  p_org_id UUID,
  p_role_slugs TEXT[]
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_admin_count INTEGER;
  v_has_admin BOOLEAN;
  v_will_have_admin BOOLEAN;
  v_invalid_slugs TEXT[];
BEGIN
  -- Validate: role slugs must not be empty
  IF p_role_slugs IS NULL OR array_length(p_role_slugs, 1) IS NULL THEN
    RAISE EXCEPTION 'Role slugs array must not be empty';
  END IF;

  -- Validate: all slugs must exist in kvota.roles
  SELECT array_agg(s)
  INTO v_invalid_slugs
  FROM unnest(p_role_slugs) AS s
  WHERE s NOT IN (SELECT slug FROM kvota.roles);

  IF v_invalid_slugs IS NOT NULL THEN
    RAISE EXCEPTION 'Invalid role slugs: %', array_to_string(v_invalid_slugs, ', ');
  END IF;

  -- Check if user currently has admin role
  SELECT EXISTS(
    SELECT 1 FROM kvota.user_roles ur
    JOIN kvota.roles r ON r.id = ur.role_id
    WHERE ur.user_id = p_user_id AND ur.organization_id = p_org_id AND r.slug = 'admin'
  ) INTO v_has_admin;

  -- Check if new roles include admin
  v_will_have_admin := 'admin' = ANY(p_role_slugs);

  -- If removing admin, check last admin guard
  IF v_has_admin AND NOT v_will_have_admin THEN
    SELECT COUNT(*) INTO v_admin_count
    FROM kvota.user_roles ur
    JOIN kvota.roles r ON r.id = ur.role_id
    WHERE ur.organization_id = p_org_id AND r.slug = 'admin' AND ur.user_id != p_user_id;

    IF v_admin_count = 0 THEN
      RAISE EXCEPTION 'Cannot remove admin role from the last administrator';
    END IF;
  END IF;

  -- Atomic swap: delete old roles, insert new ones
  DELETE FROM kvota.user_roles WHERE user_id = p_user_id AND organization_id = p_org_id;

  INSERT INTO kvota.user_roles (user_id, organization_id, role_id)
  SELECT p_user_id, p_org_id, r.id
  FROM kvota.roles r
  WHERE r.slug = ANY(p_role_slugs);
END;
$$;

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (256, '256_create_update_user_roles_function.sql', now())
ON CONFLICT (id) DO NOTHING;

-- Down migration (as comment):
-- DROP FUNCTION IF EXISTS kvota.update_user_roles(UUID, UUID, TEXT[]);
-- DELETE FROM kvota.migrations WHERE id = 256;
