-- Migration 331: Widen buyer_companies RLS for procurement tier (Testing 2 row 82 follow-up)
-- ===========================================================================
-- Description: РОЗ (head_of_procurement) reported no Создать/Редактировать
-- buttons on /companies?tab=buyer. The page-level access set already grants
-- view to admin, finance, procurement, procurement_senior — but RLS only
-- allowed admin + finance to INSERT/UPDATE buyer_companies, so widening the
-- UI gate alone would still fail at the DB layer.
--
-- buyer_companies are operational counterparties consumed by the procurement
-- workflow («Наши юрлица-закупки»). The natural maintainers are admins,
-- finance, and the procurement tier itself.
--
-- This migration widens INSERT/UPDATE to match the page-level set:
--   admin, finance, procurement, procurement_senior, head_of_procurement.
-- DELETE remains admin-only.
-- ===========================================================================

BEGIN;

DROP POLICY IF EXISTS buyer_companies_insert_policy ON kvota.buyer_companies;
CREATE POLICY buyer_companies_insert_policy ON kvota.buyer_companies
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN (
                'admin',
                'finance',
                'procurement',
                'procurement_senior',
                'head_of_procurement'
            )
        )
    );

DROP POLICY IF EXISTS buyer_companies_update_policy ON kvota.buyer_companies;
CREATE POLICY buyer_companies_update_policy ON kvota.buyer_companies
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN (
                'admin',
                'finance',
                'procurement',
                'procurement_senior',
                'head_of_procurement'
            )
        )
    );

COMMIT;
