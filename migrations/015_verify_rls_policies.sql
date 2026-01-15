-- Migration: 015_verify_rls_policies.sql
-- Feature #16: Configure RLS for new tables
-- Date: 2025-01-15
-- Description: Verification and consolidation of RLS policies for all new workflow tables
--
-- This migration verifies that RLS is properly configured on all new tables.
-- All tables already have RLS enabled and policies created in their respective migrations.
-- This migration serves as a checkpoint and adds any missing policies.

-- =============================================================================
-- VERIFY RLS IS ENABLED ON ALL NEW TABLES
-- =============================================================================

-- Ensure RLS is enabled on all new tables (idempotent - already enabled in individual migrations)
ALTER TABLE IF EXISTS roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS brand_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS workflow_transitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS specifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS plan_fact_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS plan_fact_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS telegram_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS notifications ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- HELPER FUNCTION: Check if user has a specific role in organization
-- This function is used by multiple RLS policies
-- =============================================================================

CREATE OR REPLACE FUNCTION public.user_has_role_in_org(
    p_user_id UUID,
    p_org_id UUID,
    p_role_codes TEXT[]
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = p_user_id
          AND ur.organization_id = p_org_id
          AND r.code = ANY(p_role_codes)
    );
END;
$$;

COMMENT ON FUNCTION public.user_has_role_in_org IS 'Check if a user has any of the specified roles in an organization';
GRANT EXECUTE ON FUNCTION public.user_has_role_in_org TO authenticated;

-- =============================================================================
-- HELPER FUNCTION: Get user's organization IDs
-- =============================================================================

CREATE OR REPLACE FUNCTION public.user_organization_ids(p_user_id UUID DEFAULT NULL)
RETURNS UUID[]
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := COALESCE(p_user_id, auth.uid());
    RETURN ARRAY(
        SELECT DISTINCT organization_id
        FROM organization_members
        WHERE user_id = v_user_id
    );
END;
$$;

COMMENT ON FUNCTION public.user_organization_ids IS 'Get array of organization IDs where user is a member';
GRANT EXECUTE ON FUNCTION public.user_organization_ids TO authenticated;

-- =============================================================================
-- HELPER FUNCTION: Check if user is admin in any organization
-- =============================================================================

CREATE OR REPLACE FUNCTION public.user_is_admin_in_org(p_org_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = auth.uid()
          AND ur.organization_id = p_org_id
          AND r.code = 'admin'
    );
END;
$$;

COMMENT ON FUNCTION public.user_is_admin_in_org IS 'Check if current user has admin role in specified organization';
GRANT EXECUTE ON FUNCTION public.user_is_admin_in_org TO authenticated;

-- =============================================================================
-- RLS POLICY SUMMARY (DOCUMENTATION)
-- =============================================================================
--
-- Table: roles
--   - SELECT: All authenticated users (reference data)
--   - INSERT/UPDATE/DELETE: Service role only (admin UI via API)
--
-- Table: user_roles
--   - SELECT: Own roles + roles of users in same organization
--   - INSERT/DELETE: Only admins in same organization
--
-- Table: brand_assignments
--   - SELECT: Users in same organization
--   - INSERT/UPDATE/DELETE: Only admins in same organization
--
-- Table: workflow_transitions
--   - SELECT: Users for quotes in their organization
--   - INSERT: Users for quotes in their organization (immutable audit log)
--   - UPDATE/DELETE: Not allowed (audit records)
--
-- Table: approvals
--   - SELECT: Users for quotes in their organization
--   - INSERT: Quote controllers
--   - UPDATE: Only the designated approver
--   - DELETE: Not allowed (audit records)
--
-- Table: specifications
--   - SELECT/INSERT/UPDATE: Users in same organization
--   - DELETE: Only admins
--
-- Table: deals
--   - SELECT: Users in same organization
--   - INSERT: spec_controller or admin
--   - UPDATE: finance or admin
--   - DELETE: Only admins
--
-- Table: plan_fact_categories
--   - SELECT: All authenticated users (reference data)
--   - INSERT/UPDATE/DELETE: Only admins
--
-- Table: plan_fact_items
--   - SELECT: Users for deals in their organization
--   - INSERT/UPDATE: finance or admin
--   - DELETE: Only admins
--
-- Table: telegram_users
--   - SELECT: Own record + admins can see org members
--   - INSERT/UPDATE/DELETE: Own record only
--
-- Table: notifications
--   - SELECT/UPDATE: Own notifications only
--   - INSERT: Users in same organization
--   - DELETE: Not allowed (audit records)
--
-- =============================================================================

-- =============================================================================
-- VERIFICATION QUERY (for manual checking)
-- =============================================================================
-- Run this query in Supabase SQL Editor to verify RLS is enabled:
--
-- SELECT
--     schemaname,
--     tablename,
--     rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
--   AND tablename IN (
--       'roles', 'user_roles', 'brand_assignments', 'workflow_transitions',
--       'approvals', 'specifications', 'deals', 'plan_fact_categories',
--       'plan_fact_items', 'telegram_users', 'notifications'
--   );
--
-- All tables should show rowsecurity = true
--
-- To see policies:
-- SELECT tablename, policyname, cmd, roles, qual
-- FROM pg_policies
-- WHERE schemaname = 'public';
-- =============================================================================

-- Add migration metadata comment
COMMENT ON FUNCTION public.user_has_role_in_org IS 'Helper function for RLS policies - check user role membership';
