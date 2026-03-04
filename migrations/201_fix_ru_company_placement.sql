-- Migration 201: Fix RU company placement and add region to seller_companies
-- Adds 'region' column to seller_companies (mirroring buyer_companies from migration 188).
-- Sets region='RU' for Russian seller companies.
-- Documents the misplacement of MБ/РадРесурс/ЦМТО1 in buyer_companies and marks them
-- with region='RU' for routing purposes. They cannot be moved due to FK references.

-- =============================================================
-- Add region column to seller_companies
-- =============================================================

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS region VARCHAR(5);

-- Add check constraint allowing NULL or known region codes
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_seller_companies_region'
          AND table_schema = 'kvota'
    ) THEN
        ALTER TABLE kvota.seller_companies
        ADD CONSTRAINT chk_seller_companies_region
            CHECK (region IS NULL OR region IN ('RU', 'EU', 'TR'));
    END IF;
END $$;

COMMENT ON COLUMN kvota.seller_companies.region IS 'Region code for currency invoice routing: RU (Russian), EU (European), TR (Turkish)';

-- =============================================================
-- Set region on existing seller_companies
-- =============================================================

-- Russian seller companies
UPDATE kvota.seller_companies SET region = 'RU'
WHERE (country ILIKE '%Russia%' OR country ILIKE '%Россия%' OR country = 'RU')
  AND region IS NULL;

-- Промкомплект, Петрокем, Промрешения (created in migration 200)
UPDATE kvota.seller_companies SET region = 'RU'
WHERE name ILIKE ANY(ARRAY['%Промкомплект%', '%Петрокем%', '%Промрешения%'])
  AND region IS NULL;

-- GESTUS Trading Ltd in seller_companies is TR
UPDATE kvota.seller_companies SET region = 'TR'
WHERE name ILIKE '%GESTUS%'
  AND region IS NULL;

-- KVOTA EUROPE GmbH is EU
UPDATE kvota.seller_companies SET region = 'EU'
WHERE name ILIKE '%KVOTA%EUROPE%'
  AND region IS NULL;

-- =============================================================
-- Document misplaced RU companies in buyer_companies
-- =============================================================
-- МБ/Мастер Бэринг, РадРесурс, ЦМТО1 are Russian companies
-- currently in buyer_companies but conceptually should be in seller_companies.
-- They CANNOT be moved because of FK references from:
--   - quote_items.buyer_company_id
--   - currency_invoices.buyer_entity_id (where entity_type='buyer_company')
--   - invoices.buyer_company_id
-- The region='RU' flag (set in migration 200 Section 5) allows the code
-- to correctly route them as Russian buyer entities in TRRU invoices.
-- TODO: Future migration should consolidate these into seller_companies
-- after updating all FK references.

-- Ensure the region was set (idempotent repeat from migration 200)
UPDATE kvota.buyer_companies SET region = 'RU'
WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%')
  AND region IS DISTINCT FROM 'RU'
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

UPDATE kvota.buyer_companies SET region = 'RU'
WHERE (name ILIKE '%РадРесурс%' OR name ILIKE '%Рад Ресурс%')
  AND region IS DISTINCT FROM 'RU'
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

UPDATE kvota.buyer_companies SET region = 'RU'
WHERE name ILIKE '%ЦМТО%'
  AND region IS NULL
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (201, '201_fix_ru_company_placement.sql', now())
ON CONFLICT (id) DO NOTHING;
