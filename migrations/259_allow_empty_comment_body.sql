-- Migration 259: Allow empty comment body for attachment-only messages
-- Part of Phase 5a (document system)
--
-- The original constraint required body length > 0, but the new chat
-- attachments feature legitimately supports messages that contain only
-- file attachments (no text). The frontend prevents the fully-empty
-- case (no text AND no attachments) via UI state, so the DB only needs
-- to enforce the upper bound.

BEGIN;

ALTER TABLE kvota.quote_comments
    DROP CONSTRAINT IF EXISTS quote_comments_body_check;

ALTER TABLE kvota.quote_comments
    ADD CONSTRAINT quote_comments_body_check
    CHECK (char_length(body) <= 4000);

COMMIT;
