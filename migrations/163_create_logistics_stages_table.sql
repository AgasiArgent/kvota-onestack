-- Migration 163: Create logistics_stages table + drop old plan_fact_logistics_stages
-- P2.7: Logistics Stages Model - 7 predefined stages per deal
-- Decision: DROP old plan_fact_logistics_stages (0 rows, no code refs, old 3-segment model)

-- Step 1: Drop the old table (old 3-segment model linked to quote_id)
DROP TABLE IF EXISTS kvota.plan_fact_logistics_stages CASCADE;

-- Step 2: Create new logistics_stages table (7-stage model linked to deal_id)
CREATE TABLE IF NOT EXISTS kvota.logistics_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to deal (not quote)
    deal_id UUID NOT NULL REFERENCES kvota.deals(id) ON DELETE CASCADE,

    -- Stage identification
    stage_code VARCHAR(30) NOT NULL CHECK (stage_code IN (
        'first_mile', 'hub', 'hub_hub', 'transit',
        'post_transit', 'gtd_upload', 'last_mile'
    )),

    -- Status lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'in_progress', 'completed'
    )),

    -- Timestamps for status transitions
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Assignment
    responsible_person VARCHAR(255),

    -- Notes
    notes TEXT,

    -- SVH reference (for hub/hub_hub stages)
    svh_id UUID,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint: one stage per code per deal
    UNIQUE(deal_id, stage_code)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_logistics_stages_deal_id ON kvota.logistics_stages(deal_id);
CREATE INDEX IF NOT EXISTS idx_logistics_stages_status ON kvota.logistics_stages(status);

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION kvota.logistics_stages_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_logistics_stages_update_timestamp ON kvota.logistics_stages;
CREATE TRIGGER tr_logistics_stages_update_timestamp
    BEFORE UPDATE ON kvota.logistics_stages
    FOR EACH ROW EXECUTE FUNCTION kvota.logistics_stages_update_timestamp();

COMMENT ON TABLE kvota.logistics_stages IS '7 predefined logistics stages per deal: first_mile, hub, hub_hub, transit, post_transit, gtd_upload, last_mile';
