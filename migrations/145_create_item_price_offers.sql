-- Migration 145: Item Price Offers table
-- Multiple supplier offers per quote item with selection logic
-- Based on Gemini code with organization_id isolation added

-- Create table for price offers
CREATE TABLE IF NOT EXISTS kvota.item_price_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_item_id UUID NOT NULL REFERENCES kvota.quote_items(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES kvota.suppliers(id),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id),
    price DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    production_days INTEGER DEFAULT 0,
    is_selected BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Partial unique index: only one selected offer per item (radio-button logic)
CREATE UNIQUE INDEX IF NOT EXISTS one_selected_offer_per_item
ON kvota.item_price_offers (quote_item_id) WHERE is_selected = TRUE;

-- Index for fast lookup by quote_item_id
CREATE INDEX IF NOT EXISTS idx_item_price_offers_quote_item
ON kvota.item_price_offers (quote_item_id);

-- Index for supplier lookup
CREATE INDEX IF NOT EXISTS idx_item_price_offers_supplier
ON kvota.item_price_offers (supplier_id);

-- Index for organization lookup
CREATE INDEX IF NOT EXISTS idx_item_price_offers_organization
ON kvota.item_price_offers (organization_id);

-- RLS policies
ALTER TABLE kvota.item_price_offers ENABLE ROW LEVEL SECURITY;

-- Allow users with procurement, admin, finance, sales_manager roles to view (within their org)
CREATE POLICY "item_price_offers_select" ON kvota.item_price_offers
FOR SELECT
USING (
    organization_id IN (
        SELECT ur.organization_id FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE ur.user_id = auth.uid()
        AND r.slug IN ('admin', 'procurement', 'finance', 'sales_manager')
    )
);

-- Allow procurement and admin to insert (within their org)
CREATE POLICY "item_price_offers_insert" ON kvota.item_price_offers
FOR INSERT
WITH CHECK (
    organization_id IN (
        SELECT ur.organization_id FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE ur.user_id = auth.uid()
        AND r.slug IN ('admin', 'procurement')
    )
);

-- Allow procurement and admin to update (within their org)
CREATE POLICY "item_price_offers_update" ON kvota.item_price_offers
FOR UPDATE
USING (
    organization_id IN (
        SELECT ur.organization_id FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE ur.user_id = auth.uid()
        AND r.slug IN ('admin', 'procurement')
    )
);

-- Allow procurement and admin to delete (within their org)
CREATE POLICY "item_price_offers_delete" ON kvota.item_price_offers
FOR DELETE
USING (
    organization_id IN (
        SELECT ur.organization_id FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE ur.user_id = auth.uid()
        AND r.slug IN ('admin', 'procurement')
    )
);

-- Stored Procedure to atomically select an offer AND sync to quote_items
-- This prevents race conditions by doing everything in one transaction
CREATE OR REPLACE FUNCTION kvota.select_price_offer(p_offer_id UUID)
RETURNS VOID AS $$
DECLARE
    v_item_id UUID;
    v_supplier_id UUID;
    v_price DECIMAL;
    v_currency VARCHAR;
    v_days INTEGER;
    v_supplier_country VARCHAR;
BEGIN
    -- 1. Get offer details
    SELECT quote_item_id, supplier_id, price, currency, production_days
    INTO v_item_id, v_supplier_id, v_price, v_currency, v_days
    FROM kvota.item_price_offers
    WHERE id = p_offer_id;

    IF v_item_id IS NULL THEN
        RAISE EXCEPTION 'Offer not found';
    END IF;

    -- 2. Get supplier country (needed for quote_items sync)
    SELECT country INTO v_supplier_country
    FROM kvota.suppliers
    WHERE id = v_supplier_id;

    -- 3. Deselect any currently selected offer for this item
    UPDATE kvota.item_price_offers
    SET is_selected = FALSE, updated_at = NOW()
    WHERE quote_item_id = v_item_id AND is_selected = TRUE;

    -- 4. Mark target offer as selected
    UPDATE kvota.item_price_offers
    SET is_selected = TRUE, updated_at = NOW()
    WHERE id = p_offer_id;

    -- 5. Sync main quote_items table (atomic with selection)
    UPDATE kvota.quote_items
    SET
        supplier_id = v_supplier_id,
        purchase_price_original = v_price,
        purchase_currency = v_currency,
        production_time_days = v_days,
        supplier_country = COALESCE(v_supplier_country, supplier_country)
    WHERE id = v_item_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute on function (fixed: function takes 1 argument, not 2)
GRANT EXECUTE ON FUNCTION kvota.select_price_offer(UUID) TO authenticated;

-- Track migration
INSERT INTO kvota.migrations (version, name, applied_at)
VALUES (145, 'create_item_price_offers', NOW())
ON CONFLICT (version) DO NOTHING;
