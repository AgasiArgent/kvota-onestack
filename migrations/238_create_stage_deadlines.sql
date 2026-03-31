-- Migration 238: Create stage_deadlines table + add timer columns to quotes
-- Per-org configurable deadline hours for each workflow stage.
-- Timer tracks how long a quote has been in its current stage.
-- Date: 2026-03-30

-- Table: stage_deadlines — configurable deadline per (org, stage)
CREATE TABLE IF NOT EXISTS kvota.stage_deadlines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    stage VARCHAR(50) NOT NULL,
    deadline_hours INT NOT NULL DEFAULT 48,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, stage)
);

CREATE INDEX IF NOT EXISTS idx_stage_deadlines_org
    ON kvota.stage_deadlines(organization_id);

-- RLS: org members can read, org members can write (admin check in app layer)
ALTER TABLE kvota.stage_deadlines ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "stage_deadlines_select" ON kvota.stage_deadlines;
CREATE POLICY "stage_deadlines_select" ON kvota.stage_deadlines FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM kvota.organization_members om
        WHERE om.organization_id = stage_deadlines.organization_id
          AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "stage_deadlines_insert" ON kvota.stage_deadlines;
CREATE POLICY "stage_deadlines_insert" ON kvota.stage_deadlines FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM kvota.organization_members om
        WHERE om.organization_id = stage_deadlines.organization_id
          AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "stage_deadlines_update" ON kvota.stage_deadlines;
CREATE POLICY "stage_deadlines_update" ON kvota.stage_deadlines FOR UPDATE
    USING (EXISTS (
        SELECT 1 FROM kvota.organization_members om
        WHERE om.organization_id = stage_deadlines.organization_id
          AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "stage_deadlines_delete" ON kvota.stage_deadlines;
CREATE POLICY "stage_deadlines_delete" ON kvota.stage_deadlines FOR DELETE
    USING (EXISTS (
        SELECT 1 FROM kvota.organization_members om
        WHERE om.organization_id = stage_deadlines.organization_id
          AND om.user_id = auth.uid()
    ));

-- Updated_at trigger
CREATE OR REPLACE FUNCTION kvota.update_stage_deadlines_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER stage_deadlines_updated_at_trigger
    BEFORE UPDATE ON kvota.stage_deadlines
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_stage_deadlines_timestamp();

-- Add timer columns to quotes
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS stage_entered_at TIMESTAMPTZ;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS stage_deadline_override_hours INT;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS overdue_notified_at TIMESTAMPTZ;
