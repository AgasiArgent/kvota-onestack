-- Migration 191: Create customs declarations tables
-- Feature: [86aftzmne] Загрузка таможенных деклараций (ДТ) из XML + учёт пошлин в план-факте

-- ============================================================================
-- Table: kvota.customs_declarations (header-level data from AltaGTD XML)
-- ============================================================================

CREATE TABLE IF NOT EXISTS kvota.customs_declarations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    regnum TEXT NOT NULL,                           -- REGNUM: e.g. "10009100/261125/5177437"
    declaration_date DATE,                          -- REG_DATE
    currency VARCHAR(3),                            -- G_22_3: EUR, USD, etc.
    exchange_rate DECIMAL(12,4),                    -- G_23_1: exchange rate to RUB
    sender_name TEXT,                               -- G_2_NAM
    sender_country VARCHAR(2),                      -- G_2_7: ISO country code
    receiver_name TEXT,                             -- G_8_NAM
    receiver_inn TEXT,                              -- G_8_6
    internal_ref TEXT,                              -- Comment attribute on AltaGTD root
    total_customs_value_rub DECIMAL(15,2),          -- G_12_0
    total_fee_rub DECIMAL(15,2) DEFAULT 0,          -- B_1 (1010)
    total_duty_rub DECIMAL(15,2) DEFAULT 0,         -- B_2 (2010)
    total_vat_rub DECIMAL(15,2) DEFAULT 0,          -- B_3 (5010)
    raw_xml TEXT,                                   -- Original XML content for audit
    created_by UUID REFERENCES auth.users(id),      -- User who uploaded (was: uploaded_by)
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(regnum, organization_id)                 -- Per-org uniqueness for multi-tenancy
);

CREATE INDEX IF NOT EXISTS idx_customs_declarations_organization_id
    ON kvota.customs_declarations(organization_id);
CREATE INDEX IF NOT EXISTS idx_customs_declarations_regnum
    ON kvota.customs_declarations(regnum);
CREATE INDEX IF NOT EXISTS idx_customs_declarations_declaration_date
    ON kvota.customs_declarations(declaration_date);

-- ============================================================================
-- Table: kvota.customs_declaration_items (per-TOVG item data)
-- ============================================================================

CREATE TABLE IF NOT EXISTS kvota.customs_declaration_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    declaration_id UUID NOT NULL REFERENCES kvota.customs_declarations(id) ON DELETE CASCADE,
    block_number INTEGER DEFAULT 1,                 -- Block index within declaration
    item_number INTEGER DEFAULT 1,                  -- Item index within declaration
    sku TEXT,                                       -- G31_15
    description TEXT,                               -- G31_1
    manufacturer TEXT,                              -- G31_11
    brand TEXT,                                     -- G31_14
    quantity INTEGER DEFAULT 0,                     -- KOLVO
    unit TEXT,                                      -- NAME_EDI
    gross_weight_kg DECIMAL(12,3) DEFAULT 0,        -- G31_35 (was: gross_weight)
    net_weight_kg DECIMAL(12,3) DEFAULT 0,          -- G31_38 (was: net_weight)
    invoice_cost DECIMAL(15,2) DEFAULT 0,           -- INVOICCOST (in header currency)
    invoice_currency VARCHAR(3),                    -- Currency from declaration header
    hs_code TEXT,                                   -- G_33_1 (from BLOCK)
    customs_value_rub DECIMAL(15,2) DEFAULT 0,      -- G_45_0 (from BLOCK, proportionally distributed)
    fee_amount_rub DECIMAL(15,2) DEFAULT 0,         -- Distributed 1010 payment (was: fee_rub)
    duty_amount_rub DECIMAL(15,2) DEFAULT 0,        -- Distributed 2010 payment (was: duty_rub)
    vat_amount_rub DECIMAL(15,2) DEFAULT 0,         -- Distributed 5010 payment (was: vat_rub)
    deal_id UUID REFERENCES kvota.deals(id),        -- Optional: linked deal
    matched_at TIMESTAMPTZ,                         -- When deal was matched
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customs_declaration_items_declaration_id
    ON kvota.customs_declaration_items(declaration_id);
CREATE INDEX IF NOT EXISTS idx_customs_declaration_items_organization_id
    ON kvota.customs_declaration_items(organization_id);
CREATE INDEX IF NOT EXISTS idx_customs_declaration_items_deal_id
    ON kvota.customs_declaration_items(deal_id);
CREATE INDEX IF NOT EXISTS idx_customs_declaration_items_sku
    ON kvota.customs_declaration_items(sku);

-- ============================================================================
-- RLS Policies
-- ============================================================================

ALTER TABLE kvota.customs_declarations ENABLE ROW LEVEL SECURITY;
ALTER TABLE kvota.customs_declaration_items ENABLE ROW LEVEL SECURITY;

-- customs_declarations: select
CREATE POLICY customs_declarations_select ON kvota.customs_declarations
    FOR SELECT USING (
        organization_id IN (
            SELECT om.organization_id FROM kvota.organization_members om
            WHERE om.user_id = auth.uid() AND om.status = 'active'
        )
    );

-- customs_declarations: insert
CREATE POLICY customs_declarations_insert ON kvota.customs_declarations
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT om.organization_id FROM kvota.organization_members om
            WHERE om.user_id = auth.uid() AND om.status = 'active'
        )
    );

-- customs_declarations: delete
CREATE POLICY customs_declarations_delete ON kvota.customs_declarations
    FOR DELETE USING (
        organization_id IN (
            SELECT om.organization_id FROM kvota.organization_members om
            WHERE om.user_id = auth.uid() AND om.status = 'active'
        )
    );

-- customs_declaration_items: select
CREATE POLICY customs_declaration_items_select ON kvota.customs_declaration_items
    FOR SELECT USING (
        organization_id IN (
            SELECT om.organization_id FROM kvota.organization_members om
            WHERE om.user_id = auth.uid() AND om.status = 'active'
        )
    );

-- customs_declaration_items: insert
CREATE POLICY customs_declaration_items_insert ON kvota.customs_declaration_items
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT om.organization_id FROM kvota.organization_members om
            WHERE om.user_id = auth.uid() AND om.status = 'active'
        )
    );

-- customs_declaration_items: delete
CREATE POLICY customs_declaration_items_delete ON kvota.customs_declaration_items
    FOR DELETE USING (
        organization_id IN (
            SELECT om.organization_id FROM kvota.organization_members om
            WHERE om.user_id = auth.uid() AND om.status = 'active'
        )
    );
