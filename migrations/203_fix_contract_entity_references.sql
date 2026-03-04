-- Migration 203: Fix contract entity references
-- Migration 200 assumed TEXCEL and RU companies were in buyer_companies,
-- but they're actually in seller_companies.
-- Fixes: seller_entity for TEXCEL contracts, buyer_entity for МБ/РадРесурс/ЦМТО contracts.
-- Also creates TEXCEL bank accounts on seller_company entity.

-- =============================================================
-- FIX 1: TEXCEL as seller → seller_company in seller_companies
-- =============================================================

UPDATE kvota.currency_contracts
SET seller_entity_type = 'seller_company',
    seller_entity_id = (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%TEXCEL%' LIMIT 1)
WHERE seller_entity_id IS NULL
  AND seller_entity_type = 'buyer_company'
  AND contract_number ILIKE ANY(ARRAY[
    '%03-09/2024%',       -- TEXCEL → МБ (USD)
    '%27-10/2025-EUR%',   -- TEXCEL → Промкомплект (EUR)
    '%12/01-26-USD%',     -- TEXCEL → Петрокем (USD)
    '%18/04-25-USD-TS%'   -- TEXCEL → РадРесурс (USD)
  ]);

-- =============================================================
-- FIX 2: МБ as buyer → seller_company in seller_companies
-- =============================================================

UPDATE kvota.currency_contracts
SET buyer_entity_type = 'seller_company',
    buyer_entity_id = (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%МАСТЕР БЭРИНГ%' LIMIT 1)
WHERE buyer_entity_id IS NULL
  AND contract_number IN (
    'CONTRACT No 03-09/2024-1 dated August 03, 2024',       -- TEXCEL → МБ
    'Contract No. 18/02-25-USD dated February 18, 2025',     -- HORIZON → МБ
    'Contract No. 22/04-25-EUR dated April 22, 2025',        -- HORIZON → МБ
    -- NOTE: 'Contract No. 28/07-23-EUR' excluded — duplicate number shared with ЦМТО, handled below
    'Contract No. 23/10-25-EUR dated October 23, 2025',      -- RAFOIL → МБ
    'Contract No. 03/04-23-EUR dated April 03, 2023'         -- PEG → МБ
  );

-- Handle 1 of 2 duplicate "28/07-23-EUR" contracts: GESTUS → МБ
-- Both rows have same seller (GESTUS) and same contract_number, buyer is NULL
-- Use ctid to update only one row, leave the other for ЦМТО
UPDATE kvota.currency_contracts
SET buyer_entity_type = 'seller_company',
    buyer_entity_id = (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%МАСТЕР БЭРИНГ%' LIMIT 1)
WHERE id = (
    SELECT id FROM kvota.currency_contracts
    WHERE buyer_entity_id IS NULL
      AND contract_number = 'Contract No. 28/07-23-EUR dated July 28, 2023'
    LIMIT 1
);

-- =============================================================
-- FIX 3: РадРесурс as buyer → seller_company in seller_companies
-- =============================================================

UPDATE kvota.currency_contracts
SET buyer_entity_type = 'seller_company',
    buyer_entity_id = (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%РАД РЕСУРС%' LIMIT 1)
WHERE buyer_entity_id IS NULL
  AND contract_number IN (
    'Contract No. 18/04-25-USD-TS dated April 18, 2025',     -- TEXCEL → РадРесурс
    'Contract No. 18/04-25-EUR-HR dated April 18, 2025',     -- HORIZON → РадРесурс
    'CONTRACT No 18/04-25-EUR-GS dated April 18, 2023',      -- GESTUS → РадРесурс
    'Contract No. 07/11-25-EUR dated November 07, 2025'      -- RAFOIL → РадРесурс
  );

-- =============================================================
-- FIX 4: ЦМТО as buyer → seller_company in seller_companies
-- =============================================================

UPDATE kvota.currency_contracts
SET buyer_entity_type = 'seller_company',
    buyer_entity_id = (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1)
WHERE buyer_entity_id IS NULL
  AND contract_number IN (
    'Contract No. 03-09/2024-1 dated August 03, 2024',       -- TEXCEL → ЦМТО
    'CONTRACT No 14-01/2025-2-TL dated January 14, 2025',    -- HORIZON → ЦМТО
    'CONTRACT No 23/10-24-EUR dated October 23, 2024',        -- SOLO FRUIT → ЦМТО
    'Contract No. 01-10/25 dated January 10, 2025',           -- NORTH WEST → ЦМТО
    'Contract No. 03/04-23-USD dated April 03, 2023'          -- PEG → ЦМТО
  );

-- Handle duplicate contract number for GESTUS → ЦМТО (same number as GESTUS → МБ)
-- Contract No. 28/07-23-EUR appears twice: once for МБ (fixed above), once for ЦМТО
UPDATE kvota.currency_contracts
SET buyer_entity_type = 'seller_company',
    buyer_entity_id = (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1)
WHERE buyer_entity_id IS NULL
  AND contract_number = 'Contract No. 28/07-23-EUR dated July 28, 2023'
  AND seller_entity_id = (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%GESTUS%' AND region = 'TR' LIMIT 1);

-- =============================================================
-- FIX 5: TEXCEL bank accounts → link to seller_company entity
-- =============================================================

-- TEXCEL EUR account (Is Bankasi)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    sc.organization_id,
    'seller_company',
    sc.id,
    'Is Bankasi',
    'ISBKTRISXXX',
    'ISBKTRISXXX',
    'EUR',
    true,
    true
FROM kvota.seller_companies sc
WHERE sc.name ILIKE '%TEXCEL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'seller_company'
      AND ba.entity_id = sc.id
      AND ba.currency = 'EUR'
  );

-- TEXCEL USD account (Is Bankasi)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    sc.organization_id,
    'seller_company',
    sc.id,
    'Is Bankasi',
    'ISBKTRISXXX',
    'ISBKTRISXXX',
    'USD',
    false,
    true
FROM kvota.seller_companies sc
WHERE sc.name ILIKE '%TEXCEL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'seller_company'
      AND ba.entity_id = sc.id
      AND ba.currency = 'USD'
  );

-- =============================================================
-- FIX 6: Set region on TEXCEL in seller_companies
-- =============================================================

UPDATE kvota.seller_companies SET region = 'TR'
WHERE name ILIKE '%TEXCEL%' AND region IS NULL;

-- =============================================================
-- VERIFY: All contracts should now have non-NULL entity IDs
-- =============================================================
-- Run after migration:
-- SELECT contract_number, seller_entity_id IS NOT NULL, buyer_entity_id IS NOT NULL
-- FROM kvota.currency_contracts WHERE is_active = true;

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (203, '203_fix_contract_entity_references.sql', now())
ON CONFLICT (id) DO NOTHING;
