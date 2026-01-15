-- Migration 017: Setup Supabase Storage for Specifications
-- Feature #71: Загрузка подписанного скана
--
-- This migration documents the manual setup required in Supabase Dashboard.
-- Storage buckets cannot be created via SQL, they must be created in the Dashboard.
--
-- MANUAL STEPS REQUIRED:
-- 1. Go to Supabase Dashboard → Storage
-- 2. Click "New bucket"
-- 3. Create bucket with these settings:
--    - Name: specifications
--    - Public bucket: Yes (for easy access to signed scans)
--    - File size limit: 10MB (10485760 bytes)
--    - Allowed MIME types: application/pdf, image/jpeg, image/png
--
-- 4. Set up RLS policies for the bucket:

-- Enable RLS on the storage.objects table if not already enabled
-- (This is usually already enabled by default)

-- Policy: Allow authenticated users to read files in their organization's folder
-- Note: The path structure is: org_id/spec_id/filename
-- Since we use service role key, we can skip this for server-side uploads

-- Policy: Allow public read access to specifications bucket
-- This allows anyone with the URL to view signed scans
INSERT INTO storage.policies (bucket_id, name, definition, check, using)
SELECT
    'specifications',
    'Public Read Access',
    'SELECT',
    NULL,
    'true'
WHERE NOT EXISTS (
    SELECT 1 FROM storage.policies
    WHERE bucket_id = 'specifications' AND name = 'Public Read Access'
);

-- Policy: Allow service role to upload files
-- Service role key bypasses RLS, so no specific policy needed for uploads
-- However, if using anon key in the future, add this policy:
-- INSERT INTO storage.policies (bucket_id, name, definition, check, using)
-- SELECT
--     'specifications',
--     'Authenticated Upload',
--     'INSERT',
--     'bucket_id = ''specifications''',
--     'auth.role() = ''authenticated'''
-- WHERE NOT EXISTS (
--     SELECT 1 FROM storage.policies
--     WHERE bucket_id = 'specifications' AND name = 'Authenticated Upload'
-- );

-- ALTERNATIVE: If policies table doesn't exist or fails, create bucket manually:
-- Go to Dashboard → Storage → specifications bucket → Policies tab → Add policy
--
-- For SELECT (read):
--   - Policy name: Public Read Access
--   - Check: true (allows all reads)
--
-- For INSERT (upload):
--   - Policy name: Authenticated Upload
--   - Check: bucket_id = 'specifications' AND auth.role() = 'authenticated'

-- Note: This migration may fail if storage.policies table doesn't exist
-- or has different structure. In that case, configure policies manually
-- in the Supabase Dashboard.

-- Verify bucket exists (this will fail if bucket doesn't exist - that's OK)
-- SELECT * FROM storage.buckets WHERE id = 'specifications';

DO $$
BEGIN
    RAISE NOTICE 'Migration 017: Specifications storage setup';
    RAISE NOTICE 'Please create the "specifications" bucket manually in Supabase Dashboard → Storage';
    RAISE NOTICE 'Settings: Public=Yes, Size limit=10MB, Types: PDF, JPEG, PNG';
END $$;
