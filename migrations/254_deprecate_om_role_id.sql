-- Migration: 254_deprecate_om_role_id
-- Description: Deprecate organization_members.role_id in favor of user_roles table.
--   Phase 1 (Expand): Create helper function, migrate RLS policies + DB functions
--   to read from user_roles, fix data mismatches, make role_id nullable.
-- Author: Claude
-- Date: 2026-04-09

-- ============================================================================
-- Step 1: Fix data mismatch — ensure ekaterina.pl has head_of_procurement in user_roles
-- ============================================================================

INSERT INTO kvota.user_roles (user_id, organization_id, role_id)
SELECT
  om.user_id,
  om.organization_id,
  om.role_id
FROM kvota.organization_members om
JOIN kvota.roles r ON r.id = om.role_id
JOIN auth.users u ON u.id = om.user_id  -- exclude orphaned records
WHERE NOT EXISTS (
  SELECT 1 FROM kvota.user_roles ur
  JOIN kvota.roles r2 ON r2.id = ur.role_id
  WHERE ur.user_id = om.user_id
    AND ur.organization_id = om.organization_id
    AND r2.slug = r.slug
)
AND om.status = 'active';

-- ============================================================================
-- Step 2: Create helper function for role checks via user_roles
-- ============================================================================

CREATE OR REPLACE FUNCTION kvota.has_role(p_user_id uuid, p_org_id uuid, p_role_slug text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM kvota.user_roles ur
    JOIN kvota.roles r ON r.id = ur.role_id
    WHERE ur.user_id = p_user_id
      AND ur.organization_id = p_org_id
      AND r.slug = p_role_slug
  );
$$;

-- Convenience: check if current auth user has a role in a given org
CREATE OR REPLACE FUNCTION kvota.current_user_has_role(p_org_id uuid, p_role_slug text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT kvota.has_role(auth.uid(), p_org_id, p_role_slug);
$$;

-- Convenience: check if current user is admin or owner in a given org
CREATE OR REPLACE FUNCTION kvota.is_org_admin(p_org_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM kvota.organization_members om
    WHERE om.user_id = auth.uid()
      AND om.organization_id = p_org_id
      AND om.status = 'active'
      AND (
        om.is_owner = true
        OR kvota.has_role(auth.uid(), p_org_id, 'admin')
      )
  );
$$;

-- ============================================================================
-- Step 3: Rewrite DB functions to use user_roles
-- ============================================================================

DROP FUNCTION IF EXISTS kvota.get_user_organizations(uuid);
CREATE FUNCTION kvota.get_user_organizations(user_uuid uuid)
RETURNS TABLE (
  id uuid,
  name text,
  slug text,
  role_name text,
  is_owner boolean,
  joined_at timestamptz
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    o.id,
    o.name::text,
    o.slug::text,
    COALESCE(
      (SELECT string_agg(r.name::text, ', ' ORDER BY r.name)
       FROM kvota.user_roles ur
       JOIN kvota.roles r ON r.id = ur.role_id
       WHERE ur.user_id = om.user_id AND ur.organization_id = om.organization_id),
      'No role'
    ) AS role_name,
    om.is_owner,
    om.joined_at
  FROM kvota.organization_members om
  JOIN kvota.organizations o ON o.id = om.organization_id
  WHERE om.user_id = user_uuid
    AND om.status = 'active'
  ORDER BY om.is_owner DESC, om.joined_at DESC;
END;
$$;

CREATE OR REPLACE FUNCTION kvota.get_user_profile_data(p_user_id uuid, p_organization_id uuid)
RETURNS TABLE (
  email text,
  phone text,
  created_at timestamptz,
  full_name text,
  "position" text,
  department_name text,
  sales_group_name text,
  manager_email text,
  location text,
  role_name text,
  role_slug text
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    u.email::text,
    COALESCE(up.phone, u.phone)::text AS phone,
    u.created_at,
    up.full_name::text,
    up."position"::text,
    d.name::text AS department_name,
    sg.name::text AS sales_group_name,
    manager.email::text AS manager_email,
    up.location::text,
    COALESCE(
      (SELECT string_agg(r.name::text, ', ' ORDER BY r.name)
       FROM kvota.user_roles ur
       JOIN kvota.roles r ON r.id = ur.role_id
       WHERE ur.user_id = u.id AND ur.organization_id = p_organization_id),
      'No role'
    ) AS role_name,
    COALESCE(
      (SELECT string_agg(r.slug::text, ', ' ORDER BY r.slug)
       FROM kvota.user_roles ur
       JOIN kvota.roles r ON r.id = ur.role_id
       WHERE ur.user_id = u.id AND ur.organization_id = p_organization_id),
      ''
    ) AS role_slug
  FROM auth.users u
  INNER JOIN kvota.organization_members om ON om.user_id = u.id
    AND om.organization_id = p_organization_id
    AND om.status = 'active'
  LEFT JOIN kvota.user_profiles up ON up.user_id = u.id
    AND up.organization_id = p_organization_id
  LEFT JOIN kvota.departments d ON d.id = up.department_id
  LEFT JOIN kvota.sales_groups sg ON sg.id = up.sales_group_id
  LEFT JOIN auth.users manager ON manager.id = up.manager_id
  WHERE u.id = p_user_id;
END;
$$;

-- ============================================================================
-- Step 4: Rewrite RLS policies to use user_roles via helper functions
-- ============================================================================

-- --- kvota.roles ---
DROP POLICY IF EXISTS "Admins can create custom roles" ON kvota.roles;
CREATE POLICY "Admins can create custom roles" ON kvota.roles
  FOR INSERT TO authenticated
  WITH CHECK (kvota.is_org_admin(organization_id));

-- --- kvota.organizations ---
DROP POLICY IF EXISTS "Org admins can update organization" ON kvota.organizations;
CREATE POLICY "Org admins can update organization" ON kvota.organizations
  FOR UPDATE TO authenticated
  USING (kvota.is_org_admin(id));

-- --- kvota.organization_invitations ---
DROP POLICY IF EXISTS "Admins can create invitations" ON kvota.organization_invitations;
CREATE POLICY "Admins can create invitations" ON kvota.organization_invitations
  FOR INSERT TO authenticated
  WITH CHECK (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Admins can delete invitations" ON kvota.organization_invitations;
CREATE POLICY "Admins can delete invitations" ON kvota.organization_invitations
  FOR DELETE TO authenticated
  USING (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Admins can view invitations" ON kvota.organization_invitations;
CREATE POLICY "Admins can view invitations" ON kvota.organization_invitations
  FOR SELECT TO authenticated
  USING (kvota.is_org_admin(organization_id));

-- --- kvota.calculation_settings ---
DROP POLICY IF EXISTS "Only admins can create calculation settings" ON kvota.calculation_settings;
CREATE POLICY "Only admins can create calculation settings" ON kvota.calculation_settings
  FOR INSERT TO authenticated
  WITH CHECK (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Only admins can update calculation settings" ON kvota.calculation_settings;
CREATE POLICY "Only admins can update calculation settings" ON kvota.calculation_settings
  FOR UPDATE TO authenticated
  USING (kvota.is_org_admin(organization_id));

-- --- kvota.organization_exchange_rates ---
DROP POLICY IF EXISTS "admins_can_manage_rates" ON kvota.organization_exchange_rates;
CREATE POLICY "admins_can_manage_rates" ON kvota.organization_exchange_rates
  FOR ALL TO authenticated
  USING (kvota.is_org_admin(organization_id));

-- --- kvota.user_profiles ---
DROP POLICY IF EXISTS "Admins can update profiles in their organization" ON kvota.user_profiles;
CREATE POLICY "Admins can update profiles in their organization" ON kvota.user_profiles
  FOR UPDATE TO authenticated
  USING (kvota.current_user_has_role(organization_id, 'admin'));

-- --- kvota.seller_companies ---
DROP POLICY IF EXISTS "Admins can insert seller companies" ON kvota.seller_companies;
CREATE POLICY "Admins can insert seller companies" ON kvota.seller_companies
  FOR INSERT TO authenticated
  WITH CHECK (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Admins can update seller companies" ON kvota.seller_companies;
CREATE POLICY "Admins can update seller companies" ON kvota.seller_companies
  FOR UPDATE TO authenticated
  USING (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Admins can delete seller companies" ON kvota.seller_companies;
CREATE POLICY "Admins can delete seller companies" ON kvota.seller_companies
  FOR DELETE TO authenticated
  USING (kvota.is_org_admin(organization_id));

-- --- kvota.purchasing_companies ---
DROP POLICY IF EXISTS "Admins can insert purchasing companies" ON kvota.purchasing_companies;
CREATE POLICY "Admins can insert purchasing companies" ON kvota.purchasing_companies
  FOR INSERT TO authenticated
  WITH CHECK (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Admins can update purchasing companies" ON kvota.purchasing_companies;
CREATE POLICY "Admins can update purchasing companies" ON kvota.purchasing_companies
  FOR UPDATE TO authenticated
  USING (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Admins can delete purchasing companies" ON kvota.purchasing_companies;
CREATE POLICY "Admins can delete purchasing companies" ON kvota.purchasing_companies
  FOR DELETE TO authenticated
  USING (kvota.is_org_admin(organization_id));

-- --- kvota.quote_approval_history ---
DROP POLICY IF EXISTS "Managers can insert approval history" ON kvota.quote_approval_history;
CREATE POLICY "Managers can insert approval history" ON kvota.quote_approval_history
  FOR INSERT TO authenticated
  WITH CHECK (
    organization_id IN (
      SELECT om.organization_id
      FROM kvota.organization_members om
      WHERE om.user_id = auth.uid() AND om.status = 'active'
    )
  );

-- --- public.lead_stages ---
DROP POLICY IF EXISTS "Managers can create lead stages" ON public.lead_stages;
CREATE POLICY "Managers can create lead stages" ON public.lead_stages
  FOR INSERT TO authenticated
  WITH CHECK (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Managers can delete lead stages" ON public.lead_stages;
CREATE POLICY "Managers can delete lead stages" ON public.lead_stages
  FOR DELETE TO authenticated
  USING (kvota.is_org_admin(organization_id));

DROP POLICY IF EXISTS "Managers can update lead stages" ON public.lead_stages;
CREATE POLICY "Managers can update lead stages" ON public.lead_stages
  FOR UPDATE TO authenticated
  USING (kvota.is_org_admin(organization_id));

-- --- public.leads ---
DROP POLICY IF EXISTS "Managers can delete leads" ON public.leads;
CREATE POLICY "Managers can delete leads" ON public.leads
  FOR DELETE TO authenticated
  USING (kvota.is_org_admin(organization_id));

-- --- public.list_presets ---
DROP POLICY IF EXISTS "Users can create presets" ON public.list_presets;
CREATE POLICY "Users can create presets" ON public.list_presets
  FOR INSERT TO authenticated
  WITH CHECK (
    (preset_type = 'personal' AND created_by = auth.uid() AND organization_id IN (
      SELECT om.organization_id FROM kvota.organization_members om
      WHERE om.user_id = auth.uid() AND om.status = 'active'
    ))
    OR
    (preset_type = 'org' AND kvota.is_org_admin(organization_id))
  );

DROP POLICY IF EXISTS "Users can update own presets" ON public.list_presets;
CREATE POLICY "Users can update own presets" ON public.list_presets
  FOR UPDATE TO authenticated
  USING (
    (preset_type = 'personal' AND created_by = auth.uid())
    OR
    (preset_type = 'org' AND kvota.is_org_admin(organization_id))
  );

DROP POLICY IF EXISTS "Users can delete own presets" ON public.list_presets;
CREATE POLICY "Users can delete own presets" ON public.list_presets
  FOR DELETE TO authenticated
  USING (
    (preset_type = 'personal' AND created_by = auth.uid())
    OR
    (preset_type = 'org' AND kvota.is_org_admin(organization_id))
  );

-- ============================================================================
-- Step 5: Make role_id nullable (expand phase — column still exists but unused)
-- ============================================================================

ALTER TABLE kvota.organization_members ALTER COLUMN role_id DROP NOT NULL;

-- Add deprecation comment
COMMENT ON COLUMN kvota.organization_members.role_id IS
  'DEPRECATED (migration 254): Use kvota.user_roles table instead. Will be dropped in a future migration.';
