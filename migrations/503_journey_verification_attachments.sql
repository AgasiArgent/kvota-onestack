-- Migration 503: Storage bucket for verification screenshots (Task 24)
-- Date: 2026-04-24
-- Spec: .kiro/specs/customer-journey-map/requirements.md §9.5–9.8, §14.6
-- Reqs: 9.5, 9.6, 9.7, 9.8, 14.6
--
-- Scope:
--   - Private Supabase Storage bucket `journey-verification-attachments`
--     backing the screenshot field of kvota.journey_verifications.
--   - Storage RLS policies on storage.objects:
--       SELECT: any authenticated user who is an active organization member
--       INSERT: admin, quote_controller, spec_controller (mirrors
--               canRecordVerification in frontend/src/entities/journey/access.ts
--               and RLS on kvota.journey_verifications)
--       UPDATE/DELETE: denied for every role (append-only per Req 9.2 + 9.6)
--
-- NOTES:
--   * The bucket size limit, MIME whitelist, and per-row count (3) are
--     enforced in THREE places for defence in depth:
--       1. This migration (DB-level size/mime)
--       2. frontend/src/features/journey/lib/attachment-upload.ts (UI gate)
--       3. .kiro/specs/customer-journey-map/requirements.md §9.8 (spec)
--     Keep all three in sync when limits change.
--
--   * kvota.user_has_role(p_slug text) is defined in migration 500 — we
--     depend on it here. Abort early if it's missing so the failure is
--     obvious instead of leaving half-wired policies.
--
--   * DELETE/UPDATE policies are explicit DENY (`USING ... AND false`)
--     rather than omitted. An absent policy also denies in PostgreSQL RLS,
--     but an explicit deny is easier to grep in audits and in policy dumps.

-- ---------------------------------------------------------------------------
-- Prerequisite check: kvota.user_has_role must exist (migration 500).
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'kvota' AND p.proname = 'user_has_role'
  ) THEN
    RAISE EXCEPTION 'kvota.user_has_role() missing — apply migration 500 first';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Bucket: create or update constraints.
-- ---------------------------------------------------------------------------

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'journey-verification-attachments',
  'journey-verification-attachments',
  false,
  2097152,  -- 2 MB (matches MAX_FILE_BYTES in attachment-upload.ts)
  ARRAY['image/png', 'image/jpeg', 'image/webp']
)
ON CONFLICT (id) DO UPDATE SET
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types,
  public = EXCLUDED.public;

-- ---------------------------------------------------------------------------
-- RLS policies on storage.objects — gated by bucket_id.
-- ---------------------------------------------------------------------------

-- SELECT: any authenticated user who is an active organization member.
-- Mirrors the "all authenticated users can read journey data" rule from
-- Req 12.3 while keeping objects invisible to service-role-less anon calls.
DROP POLICY IF EXISTS "journey_attachments_select_authenticated" ON storage.objects;
CREATE POLICY "journey_attachments_select_authenticated"
ON storage.objects FOR SELECT
TO authenticated
USING (
  bucket_id = 'journey-verification-attachments'
  AND EXISTS (
    SELECT 1 FROM kvota.organization_members om
    WHERE om.user_id = auth.uid() AND om.status = 'active'
  )
);

-- INSERT: admin / quote_controller / spec_controller only (Req 12.7 + 9.2).
DROP POLICY IF EXISTS "journey_attachments_insert_qa" ON storage.objects;
CREATE POLICY "journey_attachments_insert_qa"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'journey-verification-attachments'
  AND (
    kvota.user_has_role('admin')
    OR kvota.user_has_role('quote_controller')
    OR kvota.user_has_role('spec_controller')
  )
);

-- UPDATE: explicit deny (append-only — Req 9.2 + 9.6).
DROP POLICY IF EXISTS "journey_attachments_no_update" ON storage.objects;
CREATE POLICY "journey_attachments_no_update"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'journey-verification-attachments' AND false);

-- DELETE: explicit deny (append-only — Req 9.2 + 9.6).
DROP POLICY IF EXISTS "journey_attachments_no_delete" ON storage.objects;
CREATE POLICY "journey_attachments_no_delete"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'journey-verification-attachments' AND false);

-- ---------------------------------------------------------------------------
-- Register migration.
-- ---------------------------------------------------------------------------

INSERT INTO kvota.migrations (id, filename)
VALUES (503, '503_journey_verification_attachments.sql')
ON CONFLICT (id) DO NOTHING;
