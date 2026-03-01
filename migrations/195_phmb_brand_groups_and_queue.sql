-- Migration 195: PHMB Brand Groups and Procurement Queue
-- Creates tables for brand group management and procurement queue workflow.
-- Also makes list_price_rmb nullable on phmb_quote_items for custom unpriced items.

-- =============================================================================
-- 1. Brand Groups table
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.phmb_brand_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    name TEXT NOT NULL,
    brand_patterns TEXT[] NOT NULL DEFAULT '{}',
    is_catchall BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(org_id, name)
);

CREATE INDEX IF NOT EXISTS idx_phmb_brand_groups_org_id
    ON kvota.phmb_brand_groups(org_id);

-- =============================================================================
-- 2. Procurement Queue table
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.phmb_procurement_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    quote_item_id UUID NOT NULL REFERENCES kvota.phmb_quote_items(id) ON DELETE CASCADE,
    quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    brand TEXT NOT NULL DEFAULT '',
    brand_group_id UUID REFERENCES kvota.phmb_brand_groups(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'new',
    priced_rmb NUMERIC(12,2),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_queue_status CHECK (status IN ('new', 'requested', 'priced')),
    UNIQUE(quote_item_id)
);

CREATE INDEX IF NOT EXISTS idx_phmb_procurement_queue_org_id
    ON kvota.phmb_procurement_queue(org_id);

CREATE INDEX IF NOT EXISTS idx_phmb_procurement_queue_status
    ON kvota.phmb_procurement_queue(status);

CREATE INDEX IF NOT EXISTS idx_phmb_procurement_queue_brand_group_id
    ON kvota.phmb_procurement_queue(brand_group_id);

CREATE INDEX IF NOT EXISTS idx_phmb_procurement_queue_quote_id
    ON kvota.phmb_procurement_queue(quote_id);

-- =============================================================================
-- 3. Make list_price_rmb nullable for custom unpriced items
-- =============================================================================

ALTER TABLE kvota.phmb_quote_items ALTER COLUMN list_price_rmb DROP NOT NULL;

-- =============================================================================
-- 4. Track migration
-- =============================================================================

INSERT INTO kvota.migrations (id, name, applied_at)
VALUES (195, '195_phmb_brand_groups_and_queue', now())
ON CONFLICT (id) DO NOTHING;
