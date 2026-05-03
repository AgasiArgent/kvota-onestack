-- Migration 302: add kvota.documents to supabase_realtime publication.
--
-- Required by the receiver-side fix in useRealtimeComments — listen to
-- UPDATE on documents to catch the comment_id NULL → value transition that
-- happens AFTER the quote_comments INSERT broadcast (post-PR #88 reverse
-- order). Without this publication entry, postgres_changes filtered by
-- table='documents' silently never fires, leaving receivers without a
-- realtime path for fresh attachments.
--
-- Closes
-- ------
-- - МОП Тест 2026-05-03 fail M9–M13 (final follow-up — receiver autorefresh)
--
-- Idempotent: ALTER PUBLICATION ADD TABLE errors only if the table is
-- already a member; we guard with a DO block + IF NOT EXISTS check via
-- pg_publication_tables.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'kvota'
      AND tablename = 'documents'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE kvota.documents;
  END IF;
END
$$;
