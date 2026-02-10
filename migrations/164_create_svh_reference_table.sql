-- Migration 164: Create SVH (warehouse) reference table
-- P2.7: SVH reference for logistics hub/hub_hub stages

CREATE TABLE IF NOT EXISTS kvota.svh (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50),
    address TEXT,
    contact_info TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kvota.svh IS 'SVH (warehouse) reference table for logistics hub stages';

-- Add FK from logistics_stages to svh
ALTER TABLE kvota.logistics_stages
    ADD CONSTRAINT logistics_stages_svh_id_fkey
    FOREIGN KEY (svh_id) REFERENCES kvota.svh(id) ON DELETE SET NULL;
