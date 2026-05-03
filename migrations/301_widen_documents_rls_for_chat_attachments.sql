-- Migration 301: Widen kvota.documents RLS to support chat attachments
--
-- Bug: РОП (head_of_sales) test 2026-05-03 RPQ11–RPQ17 reported "ошибка"
-- when attaching files in the quote chat. Root cause: documents_insert_policy
-- and documents_update_policy from migration 143 only allow:
--   admin, sales, sales_manager, procurement, quote_controller, finance,
--   logistics, customs
-- That allowlist predates the addition of head_of_*  / top_manager /
-- spec_controller / etc. (kvota.roles seed grew to 17 entries — see
-- migration 168 cleanup). Chat file uploads do TWO writes to documents:
--   1. INSERT a draft row (entity_type='quote', status='draft')
--   2. UPDATE comment_id when the message is sent (link step in mutations.ts)
-- Both were rejected for head_of_sales; UI fired toast.error("…") and the
-- file never reached the chat. Same applies to any other role that can read
-- a quote (organization-scoped) but isn't in the legacy allowlist.
--
-- Fix: replace the static role list with a single rule — any user that
-- belongs to the document's organization (i.e. has any role assignment in
-- that org via kvota.user_roles) can write/update its documents. This
-- matches the SELECT policy already in place (organization-scoped, no role
-- filter) and is consistent with how kvota.quote_comments handles inserts
-- (insert_own — any authenticated user that owns the row). Application-level
-- role gates remain in place for writes that require specific roles
-- (e.g. official document classification, deletion).
--
-- DELETE policy is left unchanged — deletion remains restricted to
-- admin / sales_manager / quote_controller / finance because it impacts
-- official documents, not just chat media.

BEGIN;

DROP POLICY IF EXISTS documents_insert_policy ON kvota.documents;
DROP POLICY IF EXISTS documents_update_policy ON kvota.documents;

-- INSERT: any user that has at least one role in the document's organization
-- can insert a document. Most write paths target their own quote / spec /
-- supplier scope; broader auditing remains organization-level.
CREATE POLICY documents_insert_policy ON kvota.documents
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id
            FROM kvota.user_roles
            WHERE user_id = auth.uid()
        )
    );

-- UPDATE: same scope — chat-attachment link step (UPDATE comment_id) and
-- description / type edits all happen at this layer. Application enforces
-- which fields a given role may touch.
CREATE POLICY documents_update_policy ON kvota.documents
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id
            FROM kvota.user_roles
            WHERE user_id = auth.uid()
        )
    );

COMMIT;
