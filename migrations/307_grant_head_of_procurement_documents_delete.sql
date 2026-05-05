-- Migration 307: Grant head_of_procurement DELETE on kvota.documents (РОЗ-83)
--
-- Bug: head_of_procurement (chislova.e@masterbearing.ru, РОЗ tester 2026-05-05)
-- got "мало прав" when deleting a КП-document attachment from a quote.
--
-- Root cause: documents_delete_policy from migration 143 hardcoded a role
-- allowlist that pre-dates the head_of_* role family:
--   ('admin', 'sales_manager', 'quote_controller', 'finance')
-- The API layer (api/documents.py:131) already accepts head_of_procurement —
-- so the request reaches Supabase and is silently dropped by RLS at the DB
-- level, surfacing as a generic "permissions" error in the UI.
--
-- Migration 301 widened INSERT/UPDATE for chat attachments to org-scope but
-- explicitly left DELETE alone because deletion impacts official documents,
-- not just chat media. We keep that role-gated stance here — DELETE is
-- destructive — and only add head_of_procurement to the existing allowlist.
-- head_of_sales / head_of_logistics are NOT added; they can be considered
-- separately if testing shows the same gap.

BEGIN;

DROP POLICY IF EXISTS documents_delete_policy ON kvota.documents;

CREATE POLICY documents_delete_policy ON kvota.documents
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN (
                'admin',
                'sales_manager',
                'quote_controller',
                'finance',
                'head_of_procurement'
            )
        )
    );

COMMIT;
