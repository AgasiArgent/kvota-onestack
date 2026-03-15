-- Migration 215: Create phmb_versions table
-- Enables versioning for PHMB quotes — each version snapshots payment terms
-- and calculated totals independently from the master quote flow.

CREATE TABLE IF NOT EXISTS kvota.phmb_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    label TEXT NOT NULL DEFAULT '',
    phmb_advance_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    phmb_payment_days INTEGER NOT NULL DEFAULT 0,
    phmb_markup_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    total_amount_usd NUMERIC(15,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(quote_id, version_number)
);

-- Index for quick lookup by quote
CREATE INDEX IF NOT EXISTS idx_phmb_versions_quote_id
    ON kvota.phmb_versions(quote_id);

-- RLS policy (org-scoped, same pattern as quotes)
ALTER TABLE kvota.phmb_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "phmb_versions_select" ON kvota.phmb_versions;
CREATE POLICY "phmb_versions_select" ON kvota.phmb_versions FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM kvota.quotes q
        JOIN kvota.organization_members om ON q.organization_id = om.organization_id
        WHERE q.id = phmb_versions.quote_id AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "phmb_versions_insert" ON kvota.phmb_versions;
CREATE POLICY "phmb_versions_insert" ON kvota.phmb_versions FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM kvota.quotes q
        JOIN kvota.organization_members om ON q.organization_id = om.organization_id
        WHERE q.id = phmb_versions.quote_id AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "phmb_versions_update" ON kvota.phmb_versions;
CREATE POLICY "phmb_versions_update" ON kvota.phmb_versions FOR UPDATE
    USING (EXISTS (
        SELECT 1 FROM kvota.quotes q
        JOIN kvota.organization_members om ON q.organization_id = om.organization_id
        WHERE q.id = phmb_versions.quote_id AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "phmb_versions_delete" ON kvota.phmb_versions;
CREATE POLICY "phmb_versions_delete" ON kvota.phmb_versions FOR DELETE
    USING (EXISTS (
        SELECT 1 FROM kvota.quotes q
        JOIN kvota.organization_members om ON q.organization_id = om.organization_id
        WHERE q.id = phmb_versions.quote_id AND om.user_id = auth.uid()
    ));
