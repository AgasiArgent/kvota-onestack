-- Migration 258: Add chat attachment + status support to documents
-- Part of Phase 5a (quote composition design doc, Feature 2)
--
-- Extends kvota.documents to support:
--   1. Chat attachments: documents can be linked to a quote_comments row
--      via the new comment_id FK. NULL means a direct upload (not from chat).
--   2. Draft/final status: chat uploads start as 'draft' and can be promoted
--      to 'final' by adding a document_type classification.

BEGIN;

ALTER TABLE kvota.documents
    ADD COLUMN IF NOT EXISTS comment_id UUID REFERENCES kvota.quote_comments(id) ON DELETE SET NULL;

ALTER TABLE kvota.documents
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'final'));

-- Indexes for the two documents-tab queries:
--   - Chat media: entity_type='quote' AND entity_id=$1 AND comment_id IS NOT NULL
--   - Official:   entity_type='quote' AND entity_id=$1 AND status='final'
CREATE INDEX IF NOT EXISTS idx_documents_quote_comment
    ON kvota.documents(entity_id, comment_id)
    WHERE entity_type = 'quote';

CREATE INDEX IF NOT EXISTS idx_documents_quote_status
    ON kvota.documents(entity_id, status)
    WHERE entity_type = 'quote';

COMMENT ON COLUMN kvota.documents.comment_id IS
    'If set, this document was uploaded as an attachment to a chat comment. NULL for direct uploads.';
COMMENT ON COLUMN kvota.documents.status IS
    'draft = work-in-progress or chat media, final = official document other departments rely on.';

COMMIT;
