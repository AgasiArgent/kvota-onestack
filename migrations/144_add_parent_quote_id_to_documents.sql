-- ===========================================================================
-- Migration 144: Add parent_quote_id to documents table
-- ===========================================================================
-- Description: Enables hierarchical document binding - all documents related
--              to a quote (including invoice docs, item certificates) can be
--              queried by parent_quote_id for unified view
-- Created: 2026-01-30
-- ===========================================================================

-- Add parent_quote_id column
ALTER TABLE kvota.documents
ADD COLUMN IF NOT EXISTS parent_quote_id UUID REFERENCES kvota.quotes(id) ON DELETE SET NULL;

-- Add index for fast lookup of all documents by quote
CREATE INDEX IF NOT EXISTS idx_documents_parent_quote
ON kvota.documents(parent_quote_id)
WHERE parent_quote_id IS NOT NULL;

-- Add comment
COMMENT ON COLUMN kvota.documents.parent_quote_id IS
'Parent quote ID for hierarchical binding. Allows fetching all documents related to a quote (direct + invoice docs + item certificates) in one query';

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 144: parent_quote_id column added to documents table';
END $$;
