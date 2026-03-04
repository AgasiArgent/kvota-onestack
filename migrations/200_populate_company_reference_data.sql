-- Migration 200: Populate company reference data for currency invoices
-- Data-only migration: creates new companies, enriches existing ones,
-- inserts contracts and bank accounts.
-- All operations are idempotent (ON CONFLICT / WHERE NOT EXISTS).

-- =============================================================
-- Helper: get organization_id (single-org system)
-- =============================================================
-- Used throughout via: (SELECT id FROM kvota.organizations LIMIT 1)

-- =============================================================
-- SECTION 1: Create new TR buyer_companies
-- =============================================================
-- Existing TR companies: GESTUS, TEXCEL (already in buyer_companies)
-- New TR companies: HORIZON, PEG, SOLO FRUIT, ATLANTIS, RAFOIL, NORTH WEST

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, tax_id, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'HORIZON GLOBAL',
    'HOR',
    'Turkey',
    'TR',
    'HORIZON GLOBAL MAKINA VE YEDEK PARCA TICARET LIMITED SIRKETI',
    'Atakoy 7-8-9-10. Kisim Mah. Cobancesme E-5 Yan Yol Cad. Atakoy Towers A Blok No 20/1 Ic Kapi No 70 Bakirkoy/Istanbul',
    '4631500728',
    'Ozgur Mahmut Komur',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%HORIZON%GLOBAL%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'PEG ENGINEERING',
    'PEG',
    'Turkey',
    'TR',
    'PEG ENGINEERING TRADE LIMITED COMPANY',
    'Zafer Dist. Chalishlar St. Hurshide Ehmed Bayramova, 6G Nakhchivan Azerbaijan',
    'BAHATTIN AKSU',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%PEG%ENGINEERING%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'SOLO FRUIT',
    'SOL',
    'Turkey',
    'TR',
    'SOLO FRUIT TARIM URUNLERI SANAYI TICARET LIMITED SIRKETI',
    'Istanbul, Turkey',
    'Parviz Bashir',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%SOLO%FRUIT%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, tax_id, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'ATLANTIS',
    'ATL',
    'Turkey',
    'TR',
    'ATLANTIS ITHALAT VE DIS TICARET ANONIM SIRKETI',
    'ZAFER MAH. CALISLAR SOK., Istanbul, Turkey',
    NULL,
    'ABDULAZIZ TUNCER',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%ATLANTIS%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'RAFOIL',
    'RAF',
    'Turkey',
    'TR',
    'RAFOIL GIDA PETROL SANAYI TICARET LIMITED SIRKETI',
    'Istanbul, Turkey',
    'ORUJZADE FAKHRI',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%RAFOIL%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'NORTH WEST',
    'NWE',
    'Turkey',
    'TR',
    'NORTH WEST DIS TICARET LIMITED SIRKETI',
    'YESILKOY MAH. ATATU..., Istanbul, Turkey',
    'Seyhun Khalilov',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%NORTH%WEST%'
);

-- =============================================================
-- SECTION 2: Create new EU buyer_companies
-- =============================================================

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, tax_id, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'Interfactum UAB',
    'IFT',
    'Lithuania',
    'EU',
    'Interfactum, UAB',
    'Konstitucijos pr. 7, LT-09308 Vilnius',
    'LT100016367414',
    'Kristina Kravtsova',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%Interfactum%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'Trading Industry Bulgaria',
    'TIB',
    'Bulgaria',
    'EU',
    'TRADING INDUSTRY BULGARIA LTD',
    'R. Sofia 1000, Bulgaria',
    'Katerina Maksimivna Krapivchenko',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%Trading%Industry%Bulgaria%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'MASTER INZYNIERIA',
    'MIZ',
    'Poland',
    'EU',
    'MASTER INZYNIERIA SPOLKA Z OGRANICZONA ODPOWIEDZIALNOSCIA',
    'ul. Juliana Smulikowskiego, Warsaw, Poland',
    'Ivars Cinitis',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%MASTER%INZYNIERIA%'
);

INSERT INTO kvota.buyer_companies (
    organization_id, name, company_code, country, region,
    legal_name, address, general_director_name, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'MILLENIUM VISION',
    'MLV',
    'Bulgaria',
    'EU',
    'MILLENIUM VISION LTD',
    'Burgas 8000, Odrin 15, fl. 10, Bulgaria',
    'Mandiev Sergey Dimitrov',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.buyer_companies WHERE name ILIKE '%MILLENIUM%VISION%'
);

-- =============================================================
-- SECTION 3: Enrich existing TR buyer_companies
-- =============================================================

-- GESTUS: update legal_name, address, tax_id, director
UPDATE kvota.buyer_companies
SET legal_name = 'GESTUS DIS TICARET LIMITED SIRKETI',
    address = COALESCE(address, 'Istanbul, Turkey'),
    general_director_name = COALESCE(general_director_name, 'Director'),
    region = 'TR'
WHERE name ILIKE '%GESTUS%'
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

-- TEXCEL: update legal_name, address, director
UPDATE kvota.buyer_companies
SET legal_name = 'TEXCEL OTOMOTIV TICARET LIMITED SIRKETI',
    address = COALESCE(address, 'Istanbul, Turkey'),
    general_director_name = COALESCE(general_director_name, 'Director'),
    region = 'TR'
WHERE name ILIKE '%TEXCEL%'
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

-- =============================================================
-- SECTION 4: Create RU seller_companies that don't exist yet
-- =============================================================
-- Existing seller_companies: GESTUS Trading Ltd, KVOTA EUROPE GmbH, Test 2
-- Need to create: Промкомплект, Петрокем, Промрешения

INSERT INTO kvota.seller_companies (
    organization_id, name, supplier_code, country, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'Промкомплект',
    'PMK',
    'Russia',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.seller_companies WHERE name ILIKE '%Промкомплект%'
);

INSERT INTO kvota.seller_companies (
    organization_id, name, supplier_code, country, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'Петрокем',
    'PTK',
    'Russia',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.seller_companies WHERE name ILIKE '%Петрокем%'
);

INSERT INTO kvota.seller_companies (
    organization_id, name, supplier_code, country, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'Промрешения',
    'PMR',
    'Russia',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.seller_companies WHERE name ILIKE '%Промрешения%'
);

-- =============================================================
-- SECTION 5: Set region on existing RU buyer_companies
-- =============================================================
-- These are RU companies currently misplaced in buyer_companies.
-- Cannot move them to seller_companies due to FK references.
-- Setting region = 'RU' for routing purposes.
-- NOTE: The CHECK constraint on region only allows ('EU', 'TR').
-- Must drop and recreate to allow 'RU'.

ALTER TABLE kvota.buyer_companies DROP CONSTRAINT IF EXISTS chk_buyer_companies_region;
ALTER TABLE kvota.buyer_companies
ADD CONSTRAINT chk_buyer_companies_region CHECK (region IS NULL OR region IN ('EU', 'TR', 'RU'));

UPDATE kvota.buyer_companies SET region = 'RU'
WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%')
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

UPDATE kvota.buyer_companies SET region = 'RU'
WHERE (name ILIKE '%РадРесурс%' OR name ILIKE '%Рад Ресурс%')
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

UPDATE kvota.buyer_companies SET region = 'RU'
WHERE name ILIKE '%ЦМТО%'
  AND organization_id = (SELECT id FROM kvota.organizations LIMIT 1);

-- =============================================================
-- SECTION 6: Insert bank accounts for TR companies
-- =============================================================
-- Note: account_number is NOT NULL in bank_accounts table.
-- For international accounts without a specific account number,
-- we use the IBAN or SWIFT as the account_number placeholder.

-- TEXCEL: Is Bankasi (EUR and USD accounts, SWIFT only - no IBAN known)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Is Bankasi',
    'ISBKTRISXXX',
    'ISBKTRISXXX',
    'EUR',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%TEXCEL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'EUR'
  );

INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Is Bankasi',
    'ISBKTRISXXX',
    'ISBKTRISXXX',
    'USD',
    false,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%TEXCEL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'USD'
  );

-- HORIZON: Emlak Katilim Bankasi (EUR and USD accounts with IBANs)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, iban, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Emlak Katilim Bankasi',
    'EMLATRIS',
    'TR700021100000788194001002',
    'TR700021100000788194001002',
    'EUR',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%HORIZON%GLOBAL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'EUR'
  );

INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, iban, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Emlak Katilim Bankasi',
    'EMLATRIS',
    'TR970021100000788194001001',
    'TR970021100000788194001001',
    'USD',
    false,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%HORIZON%GLOBAL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'USD'
  );

-- HORIZON: also has Ziraat Bankasi account (TRY, SWIFT only)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Ziraat Bankasi',
    'TCZBTR2A',
    'TCZBTR2A',
    'TRY',
    false,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%HORIZON%GLOBAL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.swift = 'TCZBTR2A'
  );

-- GESTUS: Vakif Katilim (SWIFT only)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Vakif Katilim Bankasi',
    'VAKFTRISXXX',
    'VAKFTRISXXX',
    'EUR',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%GESTUS%'
  AND bc.region = 'TR'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'EUR'
  );

-- ATLANTIS: Garanti Bankasi (SWIFT only)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Garanti Bankasi',
    'TGBATRIS',
    'TGBATRIS',
    'EUR',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%ATLANTIS%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'EUR'
  );

-- PEG: Emlak Katilim Bankasi (SWIFT only)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, account_number, currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Emlak Katilim Bankasi',
    'EMLATRIS',
    'EMLATRIS',
    'EUR',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%PEG%ENGINEERING%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'EUR'
  );

-- RAFOIL: Credit Europa Bank (Russia) - uses Russian bank format (BIK, not SWIFT/IBAN)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, account_number, bik, correspondent_account,
    currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'JSC Credit Europa Bank (Russia)',
    '40807810075600040509',
    '044525770',
    '30101810900000000770',
    'RUB',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%RAFOIL%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.account_number = '40807810075600040509'
  );

-- SOLO FRUIT: Credit Europe Bank (Russia) - Russian bank format
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, account_number, bik, correspondent_account,
    currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Credit Europe Bank (Russia)',
    '40807810475600029874',
    '044525770',
    '30101810900000000770',
    'RUB',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%SOLO%FRUIT%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.account_number = '40807810475600029874'
  );

-- =============================================================
-- SECTION 7: Insert bank accounts for EU companies
-- =============================================================

-- Interfactum: Paysera LT (SWIFT + IBAN)
INSERT INTO kvota.bank_accounts (
    organization_id, entity_type, entity_id,
    bank_name, swift, iban, account_number,
    currency, is_default, is_active
)
SELECT
    bc.organization_id,
    'buyer_company',
    bc.id,
    'Paysera LT',
    'EVIULT2VXXX',
    'LT163500010016350841',
    'LT163500010016350841',
    'EUR',
    true,
    true
FROM kvota.buyer_companies bc
WHERE bc.name ILIKE '%Interfactum%'
  AND NOT EXISTS (
    SELECT 1 FROM kvota.bank_accounts ba
    WHERE ba.entity_type = 'buyer_company'
      AND ba.entity_id = bc.id
      AND ba.currency = 'EUR'
  );

-- =============================================================
-- SECTION 8: Insert currency contracts (22 contracts)
-- =============================================================
-- Convention: TR company is the SELLER, RU company is the BUYER
-- TR companies are in buyer_companies (entity_type = 'buyer_company')
-- RU companies: some in buyer_companies, some in seller_companies

-- Contract 1: TEXCEL -> MB, USD
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%TEXCEL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%') AND region = 'RU' LIMIT 1),
    'USD',
    'CONTRACT No 03-09/2024-1 dated August 03, 2024',
    '2024-08-03',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'CONTRACT No 03-09/2024-1 dated August 03, 2024'
      AND seller_entity_id = (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%TEXCEL%' LIMIT 1)
);

-- Contract 2: TEXCEL -> Промкомплект, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%TEXCEL%' LIMIT 1),
    'seller_company',
    (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промкомплект%' LIMIT 1),
    'EUR',
    'CONTRACT No 27-10/2025-EUR dated October 27, 2025',
    '2025-10-27',
    true
WHERE (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промкомплект%' LIMIT 1) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'CONTRACT No 27-10/2025-EUR dated October 27, 2025'
);

-- Contract 3: TEXCEL -> Петрокем, USD
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%TEXCEL%' LIMIT 1),
    'seller_company',
    (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Петрокем%' LIMIT 1),
    'USD',
    'CONTRACT No 12/01-26-USD-TS dated January 12, 2026',
    '2026-01-12',
    true
WHERE (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Петрокем%' LIMIT 1) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'CONTRACT No 12/01-26-USD-TS dated January 12, 2026'
);

-- Contract 4: TEXCEL -> ЦМТО1, USD
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%TEXCEL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1),
    'USD',
    'Contract No. 03-09/2024-1 dated August 03, 2024',
    '2024-08-03',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 03-09/2024-1 dated August 03, 2024'
      AND buyer_entity_id = (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1)
);

-- Contract 5: TEXCEL -> РадРесурс, USD
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%TEXCEL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%РадРесурс%' OR name ILIKE '%Рад Ресурс%' LIMIT 1),
    'USD',
    'Contract No. 18/04-25-USD-TS dated April 18, 2025',
    '2025-04-18',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 18/04-25-USD-TS dated April 18, 2025'
);

-- Contract 6: HORIZON -> МБ, USD
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%HORIZON%GLOBAL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%') AND region = 'RU' LIMIT 1),
    'USD',
    'Contract No. 18/02-25-USD dated February 18, 2025',
    '2025-02-18',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 18/02-25-USD dated February 18, 2025'
);

-- Contract 7: HORIZON -> МБ, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%HORIZON%GLOBAL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%') AND region = 'RU' LIMIT 1),
    'EUR',
    'Contract No. 22/04-25-EUR dated April 22, 2025',
    '2025-04-22',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 22/04-25-EUR dated April 22, 2025'
);

-- Contract 8: HORIZON -> Промкомплект, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%HORIZON%GLOBAL%' LIMIT 1),
    'seller_company',
    (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промкомплект%' LIMIT 1),
    'EUR',
    'Contract No 30/12-25-EUR dated December 30, 2025',
    '2025-12-30',
    true
WHERE (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промкомплект%' LIMIT 1) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No 30/12-25-EUR dated December 30, 2025'
      AND seller_entity_id = (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%HORIZON%GLOBAL%' LIMIT 1)
);

-- Contract 9: HORIZON -> ЦМТО1, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%HORIZON%GLOBAL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1),
    'EUR',
    'CONTRACT No 14-01/2025-2-TL dated January 14, 2025',
    '2025-01-14',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'CONTRACT No 14-01/2025-2-TL dated January 14, 2025'
);

-- Contract 10: HORIZON -> РадРесурс, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%HORIZON%GLOBAL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%РадРесурс%' OR name ILIKE '%Рад Ресурс%' LIMIT 1),
    'EUR',
    'Contract No. 18/04-25-EUR-HR dated April 18, 2025',
    '2025-04-18',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 18/04-25-EUR-HR dated April 18, 2025'
);

-- Contract 11: GESTUS -> МБ, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%GESTUS%' AND region = 'TR' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%') AND region = 'RU' LIMIT 1),
    'EUR',
    'Contract No. 28/07-23-EUR dated July 28, 2023',
    '2023-07-28',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 28/07-23-EUR dated July 28, 2023'
      AND buyer_entity_id = (SELECT id FROM kvota.buyer_companies WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%') AND region = 'RU' LIMIT 1)
);

-- Contract 12: GESTUS -> РадРесурс, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%GESTUS%' AND region = 'TR' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%РадРесурс%' OR name ILIKE '%Рад Ресурс%' LIMIT 1),
    'EUR',
    'CONTRACT No 18/04-25-EUR-GS dated April 18, 2023',
    '2023-04-18',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'CONTRACT No 18/04-25-EUR-GS dated April 18, 2023'
);

-- Contract 13: GESTUS -> ЦМТО1, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%GESTUS%' AND region = 'TR' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1),
    'EUR',
    'Contract No. 28/07-23-EUR dated July 28, 2023',
    '2023-07-28',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 28/07-23-EUR dated July 28, 2023'
      AND buyer_entity_id = (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1)
);

-- Contract 14: GESTUS -> Промкомплект, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%GESTUS%' AND region = 'TR' LIMIT 1),
    'seller_company',
    (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промкомплект%' LIMIT 1),
    'EUR',
    'Contract No 30/12-25-EUR dated December 30, 2025',
    '2025-12-30',
    true
WHERE (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промкомплект%' LIMIT 1) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No 30/12-25-EUR dated December 30, 2025'
      AND seller_entity_id = (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%GESTUS%' AND region = 'TR' LIMIT 1)
);

-- Contract 15: SOLO FRUIT -> ЦМТО1, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%SOLO%FRUIT%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1),
    'EUR',
    'CONTRACT No 23/10-24-EUR dated October 23, 2024',
    '2024-10-23',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'CONTRACT No 23/10-24-EUR dated October 23, 2024'
);

-- Contract 16: ATLANTIS -> Промрешения, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ATLANTIS%' LIMIT 1),
    'seller_company',
    (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промрешения%' LIMIT 1),
    'EUR',
    'CONTRACT No 13/01-26-EUR dated January 13, 2026',
    '2026-01-13',
    true
WHERE (SELECT id FROM kvota.seller_companies WHERE name ILIKE '%Промрешения%' LIMIT 1) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'CONTRACT No 13/01-26-EUR dated January 13, 2026'
);

-- Contract 17: RAFOIL -> МБ, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%RAFOIL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%') AND region = 'RU' LIMIT 1),
    'EUR',
    'Contract No. 23/10-25-EUR dated October 23, 2025',
    '2025-10-23',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 23/10-25-EUR dated October 23, 2025'
);

-- Contract 18: RAFOIL -> РадРесурс, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%RAFOIL%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%РадРесурс%' OR name ILIKE '%Рад Ресурс%' LIMIT 1),
    'EUR',
    'Contract No. 07/11-25-EUR dated November 07, 2025',
    '2025-11-07',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 07/11-25-EUR dated November 07, 2025'
);

-- Contract 19: NORTH WEST -> ЦМТО1, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%NORTH%WEST%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1),
    'EUR',
    'Contract No. 01-10/25 dated January 10, 2025',
    '2025-01-10',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 01-10/25 dated January 10, 2025'
);

-- Contract 20: PEG -> МБ, EUR
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%PEG%ENGINEERING%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE (name ILIKE '%МБ%' OR name ILIKE '%Мастер Бэринг%' OR name ILIKE '%Master Bearing%') AND region = 'RU' LIMIT 1),
    'EUR',
    'Contract No. 03/04-23-EUR dated April 03, 2023',
    '2023-04-03',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 03/04-23-EUR dated April 03, 2023'
);

-- Contract 21: PEG -> ЦМТО1, USD
INSERT INTO kvota.currency_contracts (
    organization_id, seller_entity_type, seller_entity_id,
    buyer_entity_type, buyer_entity_id,
    currency, contract_number, contract_date, is_active
)
SELECT
    (SELECT id FROM kvota.organizations LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%PEG%ENGINEERING%' LIMIT 1),
    'buyer_company',
    (SELECT id FROM kvota.buyer_companies WHERE name ILIKE '%ЦМТО%' LIMIT 1),
    'USD',
    'Contract No. 03/04-23-USD dated April 03, 2023',
    '2023-04-03',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.currency_contracts
    WHERE contract_number = 'Contract No. 03/04-23-USD dated April 03, 2023'
);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (200, '200_populate_company_reference_data.sql', now())
ON CONFLICT (id) DO NOTHING;
