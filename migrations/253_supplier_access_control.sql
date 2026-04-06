-- ===========================================================================
-- Migration 253: Supplier access control overhaul
-- ===========================================================================
-- Creates supplier_assignees (many-to-many) for procurement manager assignment.
-- Fixes broken RLS on suppliers (r.code→r.slug) and brand_supplier_assignments
-- (adds missing procurement_senior, head_of_procurement roles).
--
-- Bugs resolved:
--   FB-260406-120133-2185 — supplier creation fails (r.code doesn't exist)
--   FB-260406-111712-0936 — brand addition fails (missing roles in RLS)
--
-- Pattern: mirrors customer_assignees (migration 252)
-- ===========================================================================

-- ============================================
-- 1. Create supplier_assignees table
-- ============================================

CREATE TABLE IF NOT EXISTS kvota.supplier_assignees (
  supplier_id UUID NOT NULL REFERENCES kvota.suppliers(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id)      ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by  UUID REFERENCES auth.users(id),
  PRIMARY KEY (supplier_id, user_id)
);

-- Index for reverse lookup: "which suppliers is this user assigned to?"
CREATE INDEX IF NOT EXISTS idx_supplier_assignees_user_id
  ON kvota.supplier_assignees(user_id);

COMMENT ON TABLE kvota.supplier_assignees IS
  'Many-to-many: procurement managers assigned to suppliers. Mirrors customer_assignees. See .kiro/steering/access-control.md.';

ALTER TABLE kvota.supplier_assignees ENABLE ROW LEVEL SECURITY;

CREATE POLICY supplier_assignees_select ON kvota.supplier_assignees
  FOR SELECT
  USING (
    supplier_id IN (
      SELECT s.id
      FROM kvota.suppliers s
      JOIN kvota.organization_members om ON om.organization_id = s.organization_id
      WHERE om.user_id = auth.uid()
    )
  );

CREATE POLICY supplier_assignees_insert ON kvota.supplier_assignees
  FOR INSERT
  WITH CHECK (
    supplier_id IN (
      SELECT s.id
      FROM kvota.suppliers s
      WHERE EXISTS (
        SELECT 1 FROM kvota.user_roles ur
        JOIN kvota.roles r ON ur.role_id = r.id
        WHERE ur.user_id = auth.uid()
        AND ur.organization_id = s.organization_id
        AND r.slug IN ('admin', 'head_of_procurement')
      )
    )
    -- Allow procurement users to self-assign (auto-assign on supplier creation)
    OR (
      user_id = auth.uid()
      AND supplier_id IN (
        SELECT s.id
        FROM kvota.suppliers s
        WHERE EXISTS (
          SELECT 1 FROM kvota.user_roles ur
          JOIN kvota.roles r ON ur.role_id = r.id
          WHERE ur.user_id = auth.uid()
          AND ur.organization_id = s.organization_id
          AND r.slug IN ('procurement', 'procurement_senior')
        )
      )
    )
  );

CREATE POLICY supplier_assignees_delete ON kvota.supplier_assignees
  FOR DELETE
  USING (
    supplier_id IN (
      SELECT s.id
      FROM kvota.suppliers s
      WHERE EXISTS (
        SELECT 1 FROM kvota.user_roles ur
        JOIN kvota.roles r ON ur.role_id = r.id
        WHERE ur.user_id = auth.uid()
        AND ur.organization_id = s.organization_id
        AND r.slug IN ('admin', 'head_of_procurement')
      )
    )
  );

-- ============================================
-- 2. Fix suppliers table RLS policies
-- ============================================
-- Original policies (migration 018) used r.code which doesn't exist.
-- Migration 109 fixed other tables but missed suppliers.

DROP POLICY IF EXISTS suppliers_select_policy ON kvota.suppliers;
DROP POLICY IF EXISTS suppliers_insert_policy ON kvota.suppliers;
DROP POLICY IF EXISTS suppliers_update_policy ON kvota.suppliers;
DROP POLICY IF EXISTS suppliers_delete_policy ON kvota.suppliers;

-- SELECT: any org member
CREATE POLICY suppliers_select_policy ON kvota.suppliers
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid()
        )
    );

-- INSERT: admin + all procurement roles
CREATE POLICY suppliers_insert_policy ON kvota.suppliers
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = suppliers.organization_id
            AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
        )
    );

-- UPDATE: admin + all procurement roles
CREATE POLICY suppliers_update_policy ON kvota.suppliers
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = suppliers.organization_id
            AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
        )
    );

-- DELETE: admin only
CREATE POLICY suppliers_delete_policy ON kvota.suppliers
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = suppliers.organization_id
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- 3. Fix brand_supplier_assignments RLS policies
-- ============================================
-- Original (migration 105) only allowed admin + procurement.
-- Missing: procurement_senior, head_of_procurement.

DROP POLICY IF EXISTS brand_supplier_assignments_insert_policy ON kvota.brand_supplier_assignments;
DROP POLICY IF EXISTS brand_supplier_assignments_update_policy ON kvota.brand_supplier_assignments;
DROP POLICY IF EXISTS brand_supplier_assignments_delete_policy ON kvota.brand_supplier_assignments;

CREATE POLICY brand_supplier_assignments_insert_policy ON kvota.brand_supplier_assignments
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_supplier_assignments.organization_id
            AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
        )
    );

CREATE POLICY brand_supplier_assignments_update_policy ON kvota.brand_supplier_assignments
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_supplier_assignments.organization_id
            AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
        )
    );

CREATE POLICY brand_supplier_assignments_delete_policy ON kvota.brand_supplier_assignments
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_supplier_assignments.organization_id
            AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
        )
    );
