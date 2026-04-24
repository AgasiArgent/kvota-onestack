-- Migration 504: Storage bucket for nightly Playwright captures (Task 26)
-- Date: 2026-04-24
-- Spec: .kiro/specs/customer-journey-map/requirements.md §10.2, §10.5, §10.6
-- Reqs: 10.2, 10.5, 10.6
--
-- Scope:
--   - Private Supabase Storage bucket `journey-screenshots` backing the
--     `{role}/{node_id_safe}/{YYYY-MM-DD}.png` captures produced by
--     frontend/scripts/journey/capture-screenshots.ts.
--   - Storage RLS policies on storage.objects:
--       SELECT: any authenticated user who is an active organization member
--               (mirrors journey-verification-attachments — all journey data
--               is visible to app members, per Req 12.3).
--       INSERT/UPDATE/DELETE: service-role only. The nightly action uses the
--               Supabase service-role key, which bypasses RLS entirely, so we
--               explicitly deny all three ops for the `authenticated` role to
--               keep humans + anon agents out of the bucket's write path.
--
-- NOTES:
--   * Bucket size limit 5 MB per PNG (Req 10.2 compliance — captures at
--     1280×720 headless chromium average 80–200 KB, 5 MB is a generous
--     safety margin for debug full-page captures while still bounding cost).
--   * Retention (keep 2 newest per role/node) is enforced in the Node script
--     (_capture-helpers.ts::pruneRetainedFiles), not at the DB level.
--     Storage RLS cannot express "delete all but latest 2" predicates.
--   * DELETE/UPDATE policies are explicit DENY (`USING ... AND false`)
--     rather than omitted — matches the convention set by migration 503.

-- ---------------------------------------------------------------------------
-- Bucket: create or update constraints.
-- ---------------------------------------------------------------------------

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'journey-screenshots',
  'journey-screenshots',
  false,
  5242880,  -- 5 MB per PNG (see NOTES above)
  ARRAY['image/png']
)
ON CONFLICT (id) DO UPDATE SET
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types,
  public = EXCLUDED.public;

-- ---------------------------------------------------------------------------
-- RLS policies on storage.objects — gated by bucket_id.
-- ---------------------------------------------------------------------------

-- SELECT: any authenticated user who is an active organization member.
-- Required so the /journey page can resolve signed URLs for pin overlays.
DROP POLICY IF EXISTS "journey_screenshots_select_authenticated" ON storage.objects;
CREATE POLICY "journey_screenshots_select_authenticated"
ON storage.objects FOR SELECT
TO authenticated
USING (
  bucket_id = 'journey-screenshots'
  AND EXISTS (
    SELECT 1 FROM kvota.organization_members om
    WHERE om.user_id = auth.uid() AND om.status = 'active'
  )
);

-- INSERT: explicit deny for authenticated role. Only the service-role key
-- (used by the nightly Playwright action) may write to this bucket; service
-- role bypasses RLS so no policy is needed for it.
DROP POLICY IF EXISTS "journey_screenshots_no_insert" ON storage.objects;
CREATE POLICY "journey_screenshots_no_insert"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'journey-screenshots' AND false);

-- UPDATE: explicit deny — captures are immutable (a new YYYY-MM-DD.png is
-- written instead of rewriting yesterday's file).
DROP POLICY IF EXISTS "journey_screenshots_no_update" ON storage.objects;
CREATE POLICY "journey_screenshots_no_update"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'journey-screenshots' AND false);

-- DELETE: explicit deny for authenticated; service-role performs retention
-- pruning (Req 10.6).
DROP POLICY IF EXISTS "journey_screenshots_no_delete" ON storage.objects;
CREATE POLICY "journey_screenshots_no_delete"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'journey-screenshots' AND false);

-- ---------------------------------------------------------------------------
-- Register migration.
-- ---------------------------------------------------------------------------

INSERT INTO kvota.migrations (id, filename)
VALUES (504, '504_journey_screenshots_bucket.sql')
ON CONFLICT (id) DO NOTHING;
