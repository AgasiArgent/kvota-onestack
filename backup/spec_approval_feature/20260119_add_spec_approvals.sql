-- Migration: Add multi-department approval tracking to specifications
-- Date: 2026-01-19
-- Feature: Bug #8 follow-up - Department-level approval workflow

-- Add approvals JSONB column to specifications table
ALTER TABLE specifications
ADD COLUMN IF NOT EXISTS approvals JSONB DEFAULT '{
  "procurement": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "logistics": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "customs": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "sales": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "control": {"approved": false, "approved_by": null, "approved_at": null, "comments": null}
}'::JSONB;

-- Initialize approvals for existing specifications that don't have it
UPDATE specifications
SET approvals = '{
  "procurement": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "logistics": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "customs": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "sales": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "control": {"approved": false, "approved_by": null, "approved_at": null, "comments": null}
}'::JSONB
WHERE approvals IS NULL;

-- For specifications already in "approved" or "signed" status,
-- mark all departments as approved with legacy flag
UPDATE specifications
SET approvals = '{
  "procurement": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval (migrated)"},
  "logistics": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval (migrated)"},
  "customs": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval (migrated)"},
  "sales": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval (migrated)"},
  "control": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval (migrated)"}
}'::JSONB
WHERE status IN ('approved', 'signed') AND approvals IS NOT NULL;

-- Create index for querying approval status
CREATE INDEX IF NOT EXISTS idx_specifications_approvals ON specifications USING GIN (approvals);

-- Add comment to column for documentation
COMMENT ON COLUMN specifications.approvals IS 'Multi-department approval tracking. Structure: {department: {approved: bool, approved_by: user_id, approved_at: timestamp, comments: str}}. Workflow: procurement → (logistics + customs parallel) → sales → control';
