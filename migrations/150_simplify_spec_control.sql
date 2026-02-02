-- Migration 150: Simplify spec-control workflow
-- Removes 5-department approval system (overkill)
-- Adds signed_scan_document_id for unified document storage
-- Migrates pending_review specs to draft status

-- Step 1: Add signed_scan_document_id column to specifications
ALTER TABLE kvota.specifications
ADD COLUMN IF NOT EXISTS signed_scan_document_id UUID REFERENCES kvota.documents(id);

-- Step 2: Create index for the new column
CREATE INDEX IF NOT EXISTS idx_specifications_signed_scan_document_id
ON kvota.specifications(signed_scan_document_id)
WHERE signed_scan_document_id IS NOT NULL;

-- Step 3: Migrate pending_review specifications to draft status
-- (pending_review is no longer needed without department approvals)
UPDATE kvota.specifications
SET status = 'draft'
WHERE status = 'pending_review';

-- Step 4: Add comment explaining the simplified workflow
COMMENT ON COLUMN kvota.specifications.signed_scan_document_id IS
'Reference to signed specification scan in documents table. Simplified workflow: draft -> approved -> signed';
