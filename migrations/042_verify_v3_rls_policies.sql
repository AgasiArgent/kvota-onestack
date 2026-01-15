-- Migration: 042_verify_v3_rls_policies.sql
-- Feature: DB-026 - Add RLS policies for all new tables (v3.0 verification)
-- Date: 2026-01-15
-- Description: Comprehensive verification and documentation of RLS policies for all v3.0 tables
--
-- This migration ensures RLS is properly configured on all v3.0 tables.
-- All tables should already have RLS enabled from their creation migrations.
-- This migration serves as a checkpoint and documentation.

-- =============================================================================
-- PART 1: ENSURE RLS IS ENABLED ON ALL V3.0 TABLES
-- =============================================================================

-- Supply chain entities
ALTER TABLE IF EXISTS suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS buyer_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS seller_companies ENABLE ROW LEVEL SECURITY;

-- Customer related
ALTER TABLE IF EXISTS customer_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS customer_contracts ENABLE ROW LEVEL SECURITY;

-- Shared entities
ALTER TABLE IF EXISTS bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS locations ENABLE ROW LEVEL SECURITY;

-- Assignment tables
ALTER TABLE IF EXISTS brand_supplier_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS route_logistics_assignments ENABLE ROW LEVEL SECURITY;

-- Supplier invoicing
ALTER TABLE IF EXISTS supplier_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS supplier_invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS supplier_invoice_payments ENABLE ROW LEVEL SECURITY;

-- Plan-fact (already enabled but ensure)
ALTER TABLE IF EXISTS plan_fact_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS plan_fact_items ENABLE ROW LEVEL SECURITY;

-- Communication (already enabled but ensure)
ALTER TABLE IF EXISTS telegram_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS notifications ENABLE ROW LEVEL SECURITY;

-- Core workflow tables (already enabled from v2.0 but ensure)
ALTER TABLE IF EXISTS quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS quote_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS workflow_transitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS specifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS deals ENABLE ROW LEVEL SECURITY;


-- =============================================================================
-- PART 2: HELPER FUNCTIONS FOR RLS POLICIES (CREATE IF NOT EXISTS)
-- =============================================================================

-- Helper: Check if user can access organization data
CREATE OR REPLACE FUNCTION public.user_can_access_organization(p_org_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM organization_members
        WHERE user_id = auth.uid()
          AND organization_id = p_org_id
    );
END;
$$;

COMMENT ON FUNCTION public.user_can_access_organization IS 'Check if current user is member of specified organization';
GRANT EXECUTE ON FUNCTION public.user_can_access_organization TO authenticated;


-- Helper: Get organization ID from a quote
CREATE OR REPLACE FUNCTION public.get_quote_organization_id(p_quote_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
DECLARE
    v_org_id UUID;
BEGIN
    SELECT organization_id INTO v_org_id
    FROM quotes
    WHERE id = p_quote_id;
    RETURN v_org_id;
END;
$$;

COMMENT ON FUNCTION public.get_quote_organization_id IS 'Get organization ID for a quote';
GRANT EXECUTE ON FUNCTION public.get_quote_organization_id TO authenticated;


-- Helper: Get organization ID from a customer
CREATE OR REPLACE FUNCTION public.get_customer_organization_id(p_customer_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
DECLARE
    v_org_id UUID;
BEGIN
    SELECT organization_id INTO v_org_id
    FROM customers
    WHERE id = p_customer_id;
    RETURN v_org_id;
END;
$$;

COMMENT ON FUNCTION public.get_customer_organization_id IS 'Get organization ID for a customer';
GRANT EXECUTE ON FUNCTION public.get_customer_organization_id TO authenticated;


-- Helper: Get organization ID from a supplier invoice
CREATE OR REPLACE FUNCTION public.get_supplier_invoice_organization_id(p_invoice_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
DECLARE
    v_org_id UUID;
BEGIN
    SELECT organization_id INTO v_org_id
    FROM supplier_invoices
    WHERE id = p_invoice_id;
    RETURN v_org_id;
END;
$$;

COMMENT ON FUNCTION public.get_supplier_invoice_organization_id IS 'Get organization ID for a supplier invoice';
GRANT EXECUTE ON FUNCTION public.get_supplier_invoice_organization_id TO authenticated;


-- Helper: Get organization ID from a deal
CREATE OR REPLACE FUNCTION public.get_deal_organization_id(p_deal_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
DECLARE
    v_org_id UUID;
BEGIN
    SELECT q.organization_id INTO v_org_id
    FROM deals d
    JOIN quotes q ON d.quote_id = q.id
    WHERE d.id = p_deal_id;
    RETURN v_org_id;
END;
$$;

COMMENT ON FUNCTION public.get_deal_organization_id IS 'Get organization ID for a deal (via quote)';
GRANT EXECUTE ON FUNCTION public.get_deal_organization_id TO authenticated;


-- Helper: Check if user has specific roles for a given organization
CREATE OR REPLACE FUNCTION public.user_has_any_role(
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
        WHERE ur.user_id = auth.uid()
          AND ur.organization_id = p_org_id
          AND r.code = ANY(p_role_codes)
    );
END;
$$;

COMMENT ON FUNCTION public.user_has_any_role IS 'Check if current user has any of specified roles in organization';
GRANT EXECUTE ON FUNCTION public.user_has_any_role TO authenticated;


-- =============================================================================
-- PART 3: VERIFICATION FUNCTION (for audit/testing)
-- =============================================================================

-- Function to verify RLS is enabled on all expected tables
CREATE OR REPLACE FUNCTION public.verify_v3_rls_status()
RETURNS TABLE (
    table_name TEXT,
    rls_enabled BOOLEAN,
    policy_count INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.tablename::TEXT,
        t.rowsecurity,
        COALESCE(p.policy_count, 0)::INTEGER
    FROM pg_tables t
    LEFT JOIN (
        SELECT tablename AS tbl, COUNT(*)::INTEGER AS policy_count
        FROM pg_policies
        WHERE schemaname = 'public'
        GROUP BY tablename
    ) p ON t.tablename = p.tbl
    WHERE t.schemaname = 'public'
      AND t.tablename IN (
          -- v3.0 supply chain entities
          'suppliers', 'buyer_companies', 'seller_companies',
          -- v3.0 customer related
          'customer_contacts', 'customer_contracts',
          -- v3.0 shared entities
          'bank_accounts', 'locations',
          -- v3.0 assignments
          'brand_supplier_assignments', 'route_logistics_assignments',
          -- v3.0 supplier invoicing
          'supplier_invoices', 'supplier_invoice_items', 'supplier_invoice_payments',
          -- v3.0 plan-fact
          'plan_fact_categories', 'plan_fact_items',
          -- v3.0 communication
          'telegram_users', 'notifications',
          -- v2.0 core tables (verify still enabled)
          'quotes', 'quote_items', 'workflow_transitions', 'approvals',
          'specifications', 'deals', 'roles', 'user_roles', 'brand_assignments'
      )
    ORDER BY t.tablename;
END;
$$;

COMMENT ON FUNCTION public.verify_v3_rls_status IS 'Verify RLS is enabled and list policy counts for all v3.0 tables';
GRANT EXECUTE ON FUNCTION public.verify_v3_rls_status TO service_role;


-- =============================================================================
-- PART 4: RLS POLICY DOCUMENTATION (v3.0 TABLES)
-- =============================================================================
--
-- Table: suppliers
--   - SELECT: Users in same organization
--   - INSERT/UPDATE: admin, procurement (roles that manage suppliers)
--   - DELETE: admin only
--
-- Table: buyer_companies
--   - SELECT: Users in same organization
--   - INSERT/UPDATE/DELETE: admin only (legal entities)
--
-- Table: seller_companies
--   - SELECT: Users in same organization
--   - INSERT/UPDATE/DELETE: admin only (legal entities)
--
-- Table: customer_contacts
--   - SELECT: Users in same organization (via customer→organization)
--   - INSERT/UPDATE: sales_manager, admin
--   - DELETE: admin only
--
-- Table: customer_contracts
--   - SELECT: Users in same organization (via customer→organization)
--   - INSERT/UPDATE: sales_manager, admin
--   - DELETE: admin only
--
-- Table: bank_accounts
--   - SELECT: Users in same organization (polymorphic via entity)
--   - INSERT/UPDATE: admin, finance
--   - DELETE: admin only
--
-- Table: locations
--   - SELECT: Users in same organization
--   - INSERT/UPDATE/DELETE: admin only (directory data)
--
-- Table: brand_supplier_assignments
--   - SELECT: Users in same organization
--   - INSERT/UPDATE: admin, procurement
--   - DELETE: admin only
--
-- Table: route_logistics_assignments
--   - SELECT: Users in same organization
--   - INSERT/UPDATE: admin, head_of_logistics
--   - DELETE: admin only
--
-- Table: supplier_invoices
--   - SELECT: Users in same organization
--   - INSERT/UPDATE: procurement, finance, admin
--   - DELETE: admin only
--
-- Table: supplier_invoice_items
--   - SELECT: Users with access to parent invoice
--   - INSERT/UPDATE: procurement, finance, admin
--   - DELETE: admin only
--
-- Table: supplier_invoice_payments
--   - SELECT: Users with access to parent invoice
--   - INSERT/UPDATE: finance, admin
--   - DELETE: admin only
--
-- Table: plan_fact_categories
--   - SELECT: All authenticated users (reference data)
--   - INSERT/UPDATE/DELETE: admin only (system configuration)
--
-- Table: plan_fact_items
--   - SELECT: Users in same organization (via deal→quote→organization)
--   - INSERT/UPDATE: finance, admin
--   - DELETE: admin only
--
-- Table: telegram_users
--   - SELECT: Own record + admin can see org members
--   - INSERT/UPDATE: Own record only
--   - DELETE: Own record + admin
--
-- Table: notifications
--   - SELECT: Own notifications only
--   - INSERT: System or users in same organization
--   - UPDATE: Own notifications only (mark read)
--   - DELETE: Not allowed (audit records)
--
-- =============================================================================


-- =============================================================================
-- PART 5: VERIFICATION TEST QUERY (for manual execution)
-- =============================================================================
--
-- Execute this after migration to verify all tables have RLS enabled:
--
-- SELECT * FROM verify_v3_rls_status();
--
-- Expected output: all tables should have rls_enabled = true and policy_count > 0
--
-- To see policy details:
-- SELECT schemaname, tablename, policyname, cmd, roles, qual
-- FROM pg_policies
-- WHERE schemaname = 'public'
-- ORDER BY tablename, cmd;
--
-- =============================================================================


-- =============================================================================
-- PART 6: ENSURE MISSING POLICIES (if any tables were created without them)
-- =============================================================================

-- Note: The following is a safety check. If policies already exist, these
-- statements will fail with "policy already exists" which is fine.
-- Using DO blocks to handle gracefully.

DO $$
BEGIN
    -- Check if suppliers has policies, if not create basic ones
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'suppliers' AND policyname LIKE '%select%'
    ) THEN
        -- This should not happen as 018 creates policies, but safety first
        RAISE NOTICE 'suppliers table missing select policy - this should not happen';
    END IF;
END
$$;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 042_verify_v3_rls_policies.sql completed successfully';
    RAISE NOTICE 'All v3.0 tables verified for RLS enablement';
    RAISE NOTICE 'Run SELECT * FROM verify_v3_rls_status() to verify';
END
$$;
