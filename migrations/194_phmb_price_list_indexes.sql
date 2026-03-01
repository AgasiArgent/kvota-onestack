-- Migration 194: Trigram indexes for fast ILIKE search on PHMB price list
-- Requires pg_trgm extension (usually pre-installed in Supabase)

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_phmb_price_list_cat_number_trgm
ON kvota.phmb_price_list USING gin (cat_number gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_phmb_price_list_product_name_trgm
ON kvota.phmb_price_list USING gin (product_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_phmb_price_list_brand
ON kvota.phmb_price_list(brand);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (194, '194_phmb_price_list_indexes.sql', now())
ON CONFLICT (id) DO NOTHING;
