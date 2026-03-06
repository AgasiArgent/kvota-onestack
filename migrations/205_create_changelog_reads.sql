-- Migration 205: Create changelog_reads table for tracking user read status
-- Feature: [86afz31pe] Create changelog page with sidebar link

CREATE TABLE IF NOT EXISTS kvota.changelog_reads (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    last_read_date DATE NOT NULL DEFAULT CURRENT_DATE,
    last_read_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE kvota.changelog_reads IS 'Tracks when each user last read the changelog';

-- Enable RLS (mandatory for all user-data tables)
ALTER TABLE kvota.changelog_reads ENABLE ROW LEVEL SECURITY;

CREATE POLICY changelog_reads_select_policy
    ON kvota.changelog_reads FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY changelog_reads_insert_policy
    ON kvota.changelog_reads FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY changelog_reads_update_policy
    ON kvota.changelog_reads FOR UPDATE
    USING (user_id = auth.uid());

-- Track migration
INSERT INTO kvota.migrations (id, name, applied_at)
VALUES (205, '205_create_changelog_reads', now())
ON CONFLICT (id) DO NOTHING;
