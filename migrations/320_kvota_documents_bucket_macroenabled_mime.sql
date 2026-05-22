-- Migration: 320_kvota_documents_bucket_macroenabled_mime.sql
-- Description: Add macroenabled Office mime types to kvota-documents bucket
--              allowed_mime_types. The chat-attachments hook removed its
--              own allowlist (PR #178) so any file is accepted at the
--              frontend boundary, but Supabase Storage still rejects at
--              the bucket level for any mime not in this list.
--              Testing 2 row 32: tester uploaded "Форма_расчета_КП_НДС22…xlsm"
--              and saw "mime type application/vnd.ms-excel.sheet.macroenabled.12
--              is not supported" — the bucket allowed plain .xlsx/.xls but not
--              the macroenabled variants.
--
-- Approach: keep the explicit allowlist (so a malicious upload of e.g.
-- .exe still rejects at the storage layer) but extend it with the
-- macroenabled Office formats teams routinely exchange.

BEGIN;

UPDATE storage.buckets
   SET allowed_mime_types = (
       SELECT ARRAY(
         SELECT DISTINCT unnest(
           COALESCE(allowed_mime_types, ARRAY[]::text[]) || ARRAY[
             'application/vnd.ms-excel.sheet.macroenabled.12',         -- .xlsm
             'application/vnd.ms-excel.sheet.binary.macroenabled.12',  -- .xlsb
             'application/vnd.ms-excel.template.macroenabled.12',      -- .xltm
             'application/vnd.ms-word.document.macroenabled.12',       -- .docm
             'application/vnd.ms-word.template.macroenabled.12',       -- .dotm
             'application/vnd.ms-powerpoint.presentation.macroenabled.12',  -- .pptm
             'application/vnd.openxmlformats-officedocument.presentationml.presentation',  -- .pptx
             'application/vnd.oasis.opendocument.spreadsheet',         -- .ods
             'application/vnd.oasis.opendocument.text'                 -- .odt
           ]
         )
       )
   )
 WHERE id = 'kvota-documents';

-- Post-condition: the macroenabled Excel mime must now be in the allowlist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM storage.buckets
         WHERE id = 'kvota-documents'
           AND 'application/vnd.ms-excel.sheet.macroenabled.12'
               = ANY(allowed_mime_types)
    ) THEN
        RAISE EXCEPTION 'm320: kvota-documents bucket allowed_mime_types still missing macroenabled excel';
    END IF;
END $$;

COMMIT;
