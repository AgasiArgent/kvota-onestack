-- ===========================================================================
-- Migration 109: Fix RLS policies - replace r.code with r.slug
-- ===========================================================================
-- Description: Drop and recreate RLS policies that were created with r.code
--              (which doesn't exist) and use r.slug instead
-- Prerequisites: Migrations 102, 103, 105, 106, 107, 108 must be applied
-- Created: 2026-01-20
-- ===========================================================================

-- ============================================
-- FIX: buyer_companies policies (Migration 102)
-- ============================================

DROP POLICY IF EXISTS buyer_companies_insert_policy ON kvota.buyer_companies;
DROP POLICY IF EXISTS buyer_companies_update_policy ON kvota.buyer_companies;
DROP POLICY IF EXISTS buyer_companies_delete_policy ON kvota.buyer_companies;

CREATE POLICY buyer_companies_insert_policy ON kvota.buyer_companies
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

CREATE POLICY buyer_companies_update_policy ON kvota.buyer_companies
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

CREATE POLICY buyer_companies_delete_policy ON kvota.buyer_companies
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- FIX: bank_accounts policies (Migration 103)
-- ============================================

DROP POLICY IF EXISTS bank_accounts_insert_policy ON kvota.bank_accounts;
DROP POLICY IF EXISTS bank_accounts_update_policy ON kvota.bank_accounts;
DROP POLICY IF EXISTS bank_accounts_delete_policy ON kvota.bank_accounts;

CREATE POLICY bank_accounts_insert_policy ON kvota.bank_accounts
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

CREATE POLICY bank_accounts_update_policy ON kvota.bank_accounts
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

CREATE POLICY bank_accounts_delete_policy ON kvota.bank_accounts
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- FIX: brand_supplier_assignments policies (Migration 105)
-- ============================================

DROP POLICY IF EXISTS brand_supplier_assignments_insert_policy ON kvota.brand_supplier_assignments;
DROP POLICY IF EXISTS brand_supplier_assignments_update_policy ON kvota.brand_supplier_assignments;
DROP POLICY IF EXISTS brand_supplier_assignments_delete_policy ON kvota.brand_supplier_assignments;

CREATE POLICY brand_supplier_assignments_insert_policy ON kvota.brand_supplier_assignments
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'procurement')
        )
    );

CREATE POLICY brand_supplier_assignments_update_policy ON kvota.brand_supplier_assignments
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'procurement')
        )
    );

CREATE POLICY brand_supplier_assignments_delete_policy ON kvota.brand_supplier_assignments
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- FIX: supplier_invoices policies (Migration 106)
-- ============================================

DROP POLICY IF EXISTS supplier_invoices_insert_policy ON kvota.supplier_invoices;
DROP POLICY IF EXISTS supplier_invoices_update_policy ON kvota.supplier_invoices;
DROP POLICY IF EXISTS supplier_invoices_delete_policy ON kvota.supplier_invoices;

CREATE POLICY supplier_invoices_insert_policy ON kvota.supplier_invoices
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
        )
    );

CREATE POLICY supplier_invoices_update_policy ON kvota.supplier_invoices
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
        )
    );

CREATE POLICY supplier_invoices_delete_policy ON kvota.supplier_invoices
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- FIX: supplier_invoice_items policies (Migration 107)
-- ============================================

DROP POLICY IF EXISTS supplier_invoice_items_insert_policy ON kvota.supplier_invoice_items;
DROP POLICY IF EXISTS supplier_invoice_items_update_policy ON kvota.supplier_invoice_items;
DROP POLICY IF EXISTS supplier_invoice_items_delete_policy ON kvota.supplier_invoice_items;

CREATE POLICY supplier_invoice_items_insert_policy ON kvota.supplier_invoice_items
    FOR INSERT
    WITH CHECK (
        invoice_id IN (
            SELECT si.id FROM kvota.supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
            )
        )
    );

CREATE POLICY supplier_invoice_items_update_policy ON kvota.supplier_invoice_items
    FOR UPDATE
    USING (
        invoice_id IN (
            SELECT si.id FROM kvota.supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
            )
        )
    );

CREATE POLICY supplier_invoice_items_delete_policy ON kvota.supplier_invoice_items
    FOR DELETE
    USING (
        invoice_id IN (
            SELECT si.id FROM kvota.supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.slug IN ('admin', 'procurement', 'quote_controller')
            )
        )
    );

-- ============================================
-- FIX: supplier_invoice_payments policies (Migration 108)
-- ============================================

DROP POLICY IF EXISTS "Authorized roles can insert payments" ON kvota.supplier_invoice_payments;
DROP POLICY IF EXISTS "Authorized roles can update payments" ON kvota.supplier_invoice_payments;
DROP POLICY IF EXISTS "Admins can delete payments" ON kvota.supplier_invoice_payments;

CREATE POLICY "Authorized roles can insert payments"
ON kvota.supplier_invoice_payments FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM kvota.supplier_invoices si
        JOIN kvota.user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = si.organization_id
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND r.slug IN ('procurement', 'finance', 'admin', 'head_of_procurement')
    )
);

CREATE POLICY "Authorized roles can update payments"
ON kvota.supplier_invoice_payments FOR UPDATE
USING (
    EXISTS (
        SELECT 1 FROM kvota.supplier_invoices si
        JOIN kvota.user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = si.organization_id
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND r.slug IN ('procurement', 'finance', 'admin', 'head_of_procurement')
    )
);

CREATE POLICY "Admins can delete payments"
ON kvota.supplier_invoice_payments FOR DELETE
USING (
    EXISTS (
        SELECT 1 FROM kvota.supplier_invoices si
        JOIN kvota.user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = si.organization_id
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND r.slug IN ('admin', 'finance')
    )
);

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Migration 109 completed successfully!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Fixed RLS policies for 6 tables:';
    RAISE NOTICE '  - buyer_companies (3 policies)';
    RAISE NOTICE '  - bank_accounts (3 policies)';
    RAISE NOTICE '  - brand_supplier_assignments (3 policies)';
    RAISE NOTICE '  - supplier_invoices (3 policies)';
    RAISE NOTICE '  - supplier_invoice_items (3 policies)';
    RAISE NOTICE '  - supplier_invoice_payments (3 policies)';
    RAISE NOTICE '';
    RAISE NOTICE 'All policies now use r.slug instead of r.code';
END $$;
