-- Migration 261: Create user_table_views for saved filter/sort/column presets per registry.
--
-- Supports personal views now. Schema is forward-compatible with organization-shared views
-- (is_shared + organization_id columns with separate partial unique indexes and RLS policies).
-- Only one default view per (user, table_key) — enforced by trigger.

SET search_path = kvota, public;

-- Shared updated_at helper (create only if not already present in this schema).
CREATE OR REPLACE FUNCTION kvota.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS kvota.user_table_views (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    table_key VARCHAR(50) NOT NULL,
    name TEXT NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    sort VARCHAR(50),
    visible_columns TEXT[] NOT NULL DEFAULT '{}',
    is_shared BOOLEAN NOT NULL DEFAULT false,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Shared views must have an organization; personal views must not
    CONSTRAINT chk_shared_has_org
        CHECK ((is_shared = false) OR (organization_id IS NOT NULL)),
    CONSTRAINT chk_personal_no_org
        CHECK ((is_shared = true) OR (organization_id IS NULL))
);

-- Partial unique indexes: name uniqueness scoped differently for personal vs shared views
CREATE UNIQUE INDEX IF NOT EXISTS uq_table_views_personal
    ON kvota.user_table_views (user_id, table_key, name)
    WHERE is_shared = false;

CREATE UNIQUE INDEX IF NOT EXISTS uq_table_views_shared
    ON kvota.user_table_views (organization_id, table_key, name)
    WHERE is_shared = true;

-- Fast lookup for the common case: "list my views for table X"
CREATE INDEX IF NOT EXISTS idx_table_views_user_table
    ON kvota.user_table_views (user_id, table_key)
    WHERE is_shared = false;

-- Enforce "at most one default view per (user, table_key)" by resetting others on insert/update
CREATE OR REPLACE FUNCTION kvota.enforce_single_default_view()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_default = true THEN
        UPDATE kvota.user_table_views
        SET is_default = false
        WHERE user_id = NEW.user_id
          AND table_key = NEW.table_key
          AND id IS DISTINCT FROM NEW.id
          AND is_default = true;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_single_default ON kvota.user_table_views;
CREATE TRIGGER trg_enforce_single_default
    BEFORE INSERT OR UPDATE ON kvota.user_table_views
    FOR EACH ROW
    WHEN (NEW.is_default = true)
    EXECUTE FUNCTION kvota.enforce_single_default_view();

DROP TRIGGER IF EXISTS trg_user_table_views_updated_at ON kvota.user_table_views;
CREATE TRIGGER trg_user_table_views_updated_at
    BEFORE UPDATE ON kvota.user_table_views
    FOR EACH ROW
    EXECUTE FUNCTION kvota.set_updated_at();

-- Row-level security
ALTER TABLE kvota.user_table_views ENABLE ROW LEVEL SECURITY;

-- Personal views: only owner can SELECT/INSERT/UPDATE/DELETE
DROP POLICY IF EXISTS personal_views_owner_all ON kvota.user_table_views;
CREATE POLICY personal_views_owner_all
    ON kvota.user_table_views
    FOR ALL
    USING (is_shared = false AND user_id = auth.uid())
    WITH CHECK (is_shared = false AND user_id = auth.uid());

-- Shared views (not used in this release; schema + policies prepared for future):
-- Any organization member can SELECT; only the original owner can UPDATE/DELETE.
DROP POLICY IF EXISTS shared_views_org_read ON kvota.user_table_views;
CREATE POLICY shared_views_org_read
    ON kvota.user_table_views
    FOR SELECT
    USING (
        is_shared = true
        AND organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS shared_views_owner_update ON kvota.user_table_views;
CREATE POLICY shared_views_owner_update
    ON kvota.user_table_views
    FOR UPDATE
    USING (is_shared = true AND user_id = auth.uid())
    WITH CHECK (is_shared = true AND user_id = auth.uid());

DROP POLICY IF EXISTS shared_views_owner_delete ON kvota.user_table_views;
CREATE POLICY shared_views_owner_delete
    ON kvota.user_table_views
    FOR DELETE
    USING (is_shared = true AND user_id = auth.uid());

DROP POLICY IF EXISTS shared_views_owner_insert ON kvota.user_table_views;
CREATE POLICY shared_views_owner_insert
    ON kvota.user_table_views
    FOR INSERT
    WITH CHECK (is_shared = true AND user_id = auth.uid());

COMMENT ON TABLE kvota.user_table_views IS 'Saved filter/sort/column presets per user per registry table. Supports personal views; schema allows future org-shared views.';
COMMENT ON COLUMN kvota.user_table_views.table_key IS 'Identifier for the registry this view applies to (e.g., quotes, customers, positions).';
COMMENT ON COLUMN kvota.user_table_views.filters IS 'JSONB object keyed by column name; values are FilterValue discriminated union ({kind, values|min|max}).';
COMMENT ON COLUMN kvota.user_table_views.sort IS 'URL-format sort string (e.g., "-amount" for desc, "created_at" for asc).';
COMMENT ON COLUMN kvota.user_table_views.is_shared IS 'Reserved for future organization-wide views. Always false in initial release.';
