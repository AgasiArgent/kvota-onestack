-- Migration 180: Create training_videos table
-- Training videos knowledge base with YouTube embeds and category filtering

CREATE TABLE IF NOT EXISTS kvota.training_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    youtube_id VARCHAR(20) NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'Общее',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for efficient querying by org, category, and sort order
CREATE INDEX IF NOT EXISTS idx_training_videos_org_category_sort
    ON kvota.training_videos (organization_id, category, sort_order);

-- Index for active videos lookup
CREATE INDEX IF NOT EXISTS idx_training_videos_org_active
    ON kvota.training_videos (organization_id, is_active);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION kvota.update_training_videos_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_training_videos_updated_at ON kvota.training_videos;
CREATE TRIGGER trigger_training_videos_updated_at
    BEFORE UPDATE ON kvota.training_videos
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_training_videos_updated_at();

-- RLS policies
ALTER TABLE kvota.training_videos ENABLE ROW LEVEL SECURITY;

-- All org members can read active training videos
CREATE POLICY training_videos_select_policy ON kvota.training_videos
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_organizations
            WHERE user_id = auth.uid()
        )
    );

-- Only admins can insert training videos
CREATE POLICY training_videos_insert_policy ON kvota.training_videos
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT uo.organization_id FROM kvota.user_organizations uo
            JOIN kvota.user_roles ur ON ur.user_id = uo.user_id AND ur.organization_id = uo.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE uo.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

-- Only admins can update training videos
CREATE POLICY training_videos_update_policy ON kvota.training_videos
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT uo.organization_id FROM kvota.user_organizations uo
            JOIN kvota.user_roles ur ON ur.user_id = uo.user_id AND ur.organization_id = uo.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE uo.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

-- Only admins can delete training videos
CREATE POLICY training_videos_delete_policy ON kvota.training_videos
    FOR DELETE
    USING (
        organization_id IN (
            SELECT uo.organization_id FROM kvota.user_organizations uo
            JOIN kvota.user_roles ur ON ur.user_id = uo.user_id AND ur.organization_id = uo.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE uo.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

-- Track migration
INSERT INTO kvota.migrations (id, name, applied_at)
VALUES (180, '180_create_training_videos', now())
ON CONFLICT (id) DO NOTHING;
