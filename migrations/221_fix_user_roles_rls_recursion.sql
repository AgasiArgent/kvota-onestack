-- Fix infinite recursion in user_roles RLS policy
-- The user_roles_select_org policy was querying user_roles itself, causing
-- infinite recursion when accessed via Supabase JS client (anon key + JWT).
-- Fix: use organization_members table instead of self-referencing user_roles.

DROP POLICY IF EXISTS user_roles_select_org ON kvota.user_roles;

CREATE POLICY user_roles_select_org ON kvota.user_roles
  FOR SELECT TO authenticated
  USING (
    organization_id IN (
      SELECT organization_id
      FROM kvota.organization_members
      WHERE user_id = auth.uid() AND status = 'active'
    )
  );
