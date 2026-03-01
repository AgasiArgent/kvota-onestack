-- Migration 193: Create PHMB (price-list based) tables
-- PHMB mode = simplified workflow with pre-loaded price list + markup formula

-- 1. Price list items (populated by admin later, not via CSV upload yet)
CREATE TABLE IF NOT EXISTS kvota.phmb_price_list (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cat_number TEXT NOT NULL,
    product_name TEXT NOT NULL,
    list_price_rmb NUMERIC(12,2) NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    product_classification TEXT NOT NULL DEFAULT '',
    vendor TEXT NOT NULL DEFAULT '',
    hs_code TEXT DEFAULT NULL,
    duty_pct NUMERIC(5,2) DEFAULT NULL,
    delivery_days INTEGER DEFAULT NULL,
    additional_fee_usd NUMERIC(10,2) DEFAULT 0,
    org_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(org_id, cat_number)
);

-- 2. Brand-type discounts (discount % per brand + product classification pair)
CREATE TABLE IF NOT EXISTS kvota.phmb_brand_type_discounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand TEXT NOT NULL,
    product_classification TEXT NOT NULL DEFAULT '',
    discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    org_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(org_id, brand, product_classification)
);

-- 3. PHMB overhead settings (one row per org)
CREATE TABLE IF NOT EXISTS kvota.phmb_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL UNIQUE,
    logistics_price_per_pallet NUMERIC(10,2) NOT NULL DEFAULT 1800,
    base_price_per_pallet NUMERIC(10,2) NOT NULL DEFAULT 50000,
    exchange_rate_insurance_pct NUMERIC(5,2) NOT NULL DEFAULT 3.0,
    financial_transit_pct NUMERIC(5,2) NOT NULL DEFAULT 2.0,
    customs_handling_cost NUMERIC(10,2) NOT NULL DEFAULT 800,
    customs_insurance_pct NUMERIC(5,2) NOT NULL DEFAULT 5.0,
    default_markup_pct NUMERIC(5,2) NOT NULL DEFAULT 10.0,
    default_advance_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    default_payment_days INTEGER NOT NULL DEFAULT 30,
    default_delivery_days INTEGER NOT NULL DEFAULT 90,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. PHMB quote items (separate from standard quote_items)
CREATE TABLE IF NOT EXISTS kvota.phmb_quote_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    phmb_price_list_id UUID REFERENCES kvota.phmb_price_list(id) ON DELETE SET NULL,
    cat_number TEXT NOT NULL,
    product_name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    product_classification TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL DEFAULT 1,
    list_price_rmb NUMERIC(12,2) NOT NULL,
    discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    exw_price_usd NUMERIC(12,2),
    cogs_usd NUMERIC(12,2),
    financial_cost_usd NUMERIC(12,2),
    total_price_usd NUMERIC(12,2),
    total_price_with_vat_usd NUMERIC(12,2),
    hs_code TEXT,
    duty_pct NUMERIC(5,2),
    delivery_days INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Extend quotes table for PHMB mode
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS is_phmb BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS phmb_advance_pct NUMERIC(5,2) DEFAULT 0;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS phmb_markup_pct NUMERIC(5,2) DEFAULT 10;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS phmb_payment_days INTEGER DEFAULT 30;

-- Indexes for FK lookups
CREATE INDEX IF NOT EXISTS idx_phmb_quote_items_quote_id ON kvota.phmb_quote_items(quote_id);
CREATE INDEX IF NOT EXISTS idx_phmb_price_list_org_id ON kvota.phmb_price_list(org_id);
CREATE INDEX IF NOT EXISTS idx_phmb_brand_type_discounts_org_id ON kvota.phmb_brand_type_discounts(org_id);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (193, '193_create_phmb_tables.sql', now())
ON CONFLICT (id) DO NOTHING;
