-- Migration 295: Add country_code (ISO alpha-2) to suppliers and buyer_companies.
-- Procurement bugs fix spec (April 2026) — Requirement 1.
--
-- Purpose:
--   Country fields on suppliers and buyer_companies are currently free-text
--   VARCHAR(100) with inconsistent values ("Германия"/"Germany", "Türkiye"/
--   "Turkey", "USA"/"США", plus junk like "Test", "ААААА", empty strings).
--   This breaks buyer↔supplier matching, VAT resolution (Migration 296 / REQ-3),
--   and pickup-location logic.
--
-- What this migration does:
--   1. Adds country_code CHAR(2) NULL to both tables with a CHECK constraint
--      enforcing uppercase ISO alpha-2 (or NULL).
--   2. Backfills country_code via LOWER(TRIM(country)) matching against a
--      hardcoded name→code mapping covering every spelling observed in the
--      current DB plus expected variants (RU/EN, common misspellings).
--   3. Logs the count of unmatched rows per table via RAISE NOTICE so CI surfaces
--      the number for human triage (REQ-1 AC#3).
--
-- Expand-contract: old `country` column is NOT dropped. Both live during
-- transition; form writes both fields (REQ-1 AC#4/5).
--
-- Idempotency: re-running is a no-op.
--   - ADD COLUMN IF NOT EXISTS
--   - CHECK constraint added inside DO block that skips if already present
--   - Backfill only touches rows where country_code IS NULL
--
-- Design reference: .kiro/specs/procurement-bugs-fix/requirements.md REQ-1, REQ-9

-- =============================================================================
-- Part 1: ADD COLUMN country_code to kvota.suppliers
-- =============================================================================

ALTER TABLE kvota.suppliers
    ADD COLUMN IF NOT EXISTS country_code CHAR(2) NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'suppliers_country_code_format_check'
          AND conrelid = 'kvota.suppliers'::regclass
    ) THEN
        ALTER TABLE kvota.suppliers
            ADD CONSTRAINT suppliers_country_code_format_check
            CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$');
    END IF;
END $$;

COMMENT ON COLUMN kvota.suppliers.country_code IS
    'ISO 3166-1 alpha-2 country code (e.g., DE, TR, RU). Source of truth for '
    'buyer/supplier matching and VAT resolution. The free-text `country` column '
    'is kept in sync by the UI during transition (expand-contract).';

-- =============================================================================
-- Part 2: ADD COLUMN country_code to kvota.buyer_companies
-- =============================================================================

ALTER TABLE kvota.buyer_companies
    ADD COLUMN IF NOT EXISTS country_code CHAR(2) NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'buyer_companies_country_code_format_check'
          AND conrelid = 'kvota.buyer_companies'::regclass
    ) THEN
        ALTER TABLE kvota.buyer_companies
            ADD CONSTRAINT buyer_companies_country_code_format_check
            CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$');
    END IF;
END $$;

COMMENT ON COLUMN kvota.buyer_companies.country_code IS
    'ISO 3166-1 alpha-2 country code (e.g., DE, TR, RU). Source of truth for '
    'buyer/supplier matching and VAT resolution. The free-text `country` column '
    'is kept in sync by the UI during transition (expand-contract).';

-- =============================================================================
-- Part 3: Country name → ISO alpha-2 mapping (RU + EN spellings)
--
-- Keys are pre-normalized: LOWER(TRIM(name)). Matching uses the same transform
-- on the row's free-text `country` value so trailing whitespace and case never
-- cause misses.
--
-- Coverage: every spelling present in the DB on 2026-04-24 plus expected
-- English/Russian variants for countries Kvota is likely to trade with.
-- Junk values ("Test", "ААААА", empty, NULL) intentionally have no entry and
-- stay as country_code = NULL (REQ-1 AC#2).
-- =============================================================================

-- Use a CTE-as-values pattern so both UPDATE statements share one mapping.
-- We materialize the mapping inside each UPDATE to keep the migration a single
-- set of statements (no temp tables, no cleanup).

UPDATE kvota.suppliers s
SET country_code = m.code
FROM (
    VALUES
        -- EAEU / CIS
        ('россия',              'RU'),
        ('russia',              'RU'),
        ('рф',                  'RU'),
        ('российская федерация','RU'),
        ('russian federation',  'RU'),
        ('казахстан',           'KZ'),
        ('kazakhstan',          'KZ'),
        ('беларусь',            'BY'),
        ('belarus',             'BY'),
        ('армения',             'AM'),
        ('armenia',             'AM'),
        ('киргизия',            'KG'),
        ('кыргызстан',          'KG'),
        ('kyrgyzstan',          'KG'),
        -- EU-27
        ('германия',            'DE'),
        ('germany',             'DE'),
        ('франция',             'FR'),
        ('france',              'FR'),
        ('италия',              'IT'),
        ('italy',               'IT'),
        ('italia',              'IT'),
        ('испания',             'ES'),
        ('spain',               'ES'),
        ('нидерланды',          'NL'),
        ('netherlands',         'NL'),
        ('голландия',           'NL'),
        ('holland',             'NL'),
        ('бельгия',             'BE'),
        ('belgium',             'BE'),
        ('чехия',               'CZ'),
        ('czechia',             'CZ'),
        ('czech republic',      'CZ'),
        ('польша',              'PL'),
        ('poland',              'PL'),
        ('австрия',             'AT'),
        ('austria',             'AT'),
        ('португалия',          'PT'),
        ('portugal',            'PT'),
        ('греция',              'GR'),
        ('greece',              'GR'),
        ('швеция',              'SE'),
        ('sweden',              'SE'),
        ('дания',               'DK'),
        ('denmark',             'DK'),
        ('финляндия',           'FI'),
        ('finland',             'FI'),
        ('ирландия',            'IE'),
        ('ireland',             'IE'),
        ('люксембург',          'LU'),
        ('luxembourg',          'LU'),
        ('румыния',             'RO'),
        ('romania',             'RO'),
        ('болгария',            'BG'),
        ('bulgaria',            'BG'),
        ('венгрия',             'HU'),
        ('hungary',             'HU'),
        ('хорватия',            'HR'),
        ('croatia',             'HR'),
        ('словения',            'SI'),
        ('slovenia',            'SI'),
        ('словакия',            'SK'),
        ('slovakia',            'SK'),
        ('литва',               'LT'),
        ('lithuania',           'LT'),
        ('латвия',               'LV'),
        ('latvia',              'LV'),
        ('эстония',             'EE'),
        ('estonia',             'EE'),
        ('мальта',              'MT'),
        ('malta',               'MT'),
        ('кипр',                'CY'),
        ('cyprus',              'CY'),
        -- UK + EEA (non-EU)
        ('великобритания',      'GB'),
        ('англия',              'GB'),
        ('united kingdom',      'GB'),
        ('uk',                  'GB'),
        ('england',             'GB'),
        ('норвегия',            'NO'),
        ('norway',              'NO'),
        ('исландия',            'IS'),
        ('iceland',             'IS'),
        ('швейцария',           'CH'),
        ('switzerland',         'CH'),
        ('лихтенштейн',         'LI'),
        ('liechtenstein',       'LI'),
        -- Asia
        ('китай',               'CN'),
        ('china',               'CN'),
        ('турция',              'TR'),
        ('turkey',              'TR'),
        ('türkiye',             'TR'),
        ('turkiye',             'TR'),
        ('япония',              'JP'),
        ('japan',               'JP'),
        ('корея',               'KR'),
        ('южная корея',         'KR'),
        ('korea',               'KR'),
        ('south korea',         'KR'),
        ('индия',               'IN'),
        ('india',               'IN'),
        ('вьетнам',             'VN'),
        ('vietnam',             'VN'),
        ('таиланд',             'TH'),
        ('thailand',            'TH'),
        ('индонезия',           'ID'),
        ('indonesia',           'ID'),
        ('малайзия',            'MY'),
        ('malaysia',            'MY'),
        ('сингапур',            'SG'),
        ('singapore',           'SG'),
        ('филиппины',           'PH'),
        ('philippines',         'PH'),
        ('гонконг',             'HK'),
        ('hong kong',           'HK'),
        ('тайвань',             'TW'),
        ('taiwan',              'TW'),
        -- Middle East / Africa
        ('оаэ',                 'AE'),
        ('uae',                 'AE'),
        ('объединённые арабские эмираты', 'AE'),
        ('объединенные арабские эмираты', 'AE'),
        ('united arab emirates','AE'),
        ('саудовская аравия',   'SA'),
        ('saudi arabia',        'SA'),
        ('израиль',             'IL'),
        ('israel',              'IL'),
        ('египет',              'EG'),
        ('egypt',               'EG'),
        ('юар',                 'ZA'),
        ('южная африка',        'ZA'),
        ('south africa',        'ZA'),
        -- Americas
        ('сша',                 'US'),
        ('usa',                 'US'),
        ('us',                  'US'),
        ('united states',       'US'),
        ('америка',             'US'),
        ('канада',              'CA'),
        ('canada',              'CA'),
        ('мексика',             'MX'),
        ('mexico',              'MX'),
        ('бразилия',            'BR'),
        ('brazil',              'BR'),
        ('аргентина',           'AR'),
        ('argentina',           'AR'),
        ('чили',                'CL'),
        ('chile',               'CL'),
        -- Oceania
        ('австралия',           'AU'),
        ('australia',           'AU'),
        ('новая зеландия',      'NZ'),
        ('new zealand',         'NZ')
) AS m(name_lower, code)
WHERE s.country_code IS NULL
  AND s.country IS NOT NULL
  AND LOWER(TRIM(s.country)) = m.name_lower;

UPDATE kvota.buyer_companies bc
SET country_code = m.code
FROM (
    VALUES
        -- EAEU / CIS
        ('россия',              'RU'),
        ('russia',              'RU'),
        ('рф',                  'RU'),
        ('российская федерация','RU'),
        ('russian federation',  'RU'),
        ('казахстан',           'KZ'),
        ('kazakhstan',          'KZ'),
        ('беларусь',            'BY'),
        ('belarus',             'BY'),
        ('армения',             'AM'),
        ('armenia',             'AM'),
        ('киргизия',            'KG'),
        ('кыргызстан',          'KG'),
        ('kyrgyzstan',          'KG'),
        -- EU-27
        ('германия',            'DE'),
        ('germany',             'DE'),
        ('франция',             'FR'),
        ('france',              'FR'),
        ('италия',              'IT'),
        ('italy',               'IT'),
        ('italia',              'IT'),
        ('испания',             'ES'),
        ('spain',               'ES'),
        ('нидерланды',          'NL'),
        ('netherlands',         'NL'),
        ('голландия',           'NL'),
        ('holland',             'NL'),
        ('бельгия',             'BE'),
        ('belgium',             'BE'),
        ('чехия',               'CZ'),
        ('czechia',             'CZ'),
        ('czech republic',      'CZ'),
        ('польша',              'PL'),
        ('poland',              'PL'),
        ('австрия',             'AT'),
        ('austria',             'AT'),
        ('португалия',          'PT'),
        ('portugal',            'PT'),
        ('греция',              'GR'),
        ('greece',              'GR'),
        ('швеция',              'SE'),
        ('sweden',              'SE'),
        ('дания',               'DK'),
        ('denmark',             'DK'),
        ('финляндия',           'FI'),
        ('finland',             'FI'),
        ('ирландия',            'IE'),
        ('ireland',             'IE'),
        ('люксембург',          'LU'),
        ('luxembourg',          'LU'),
        ('румыния',             'RO'),
        ('romania',             'RO'),
        ('болгария',            'BG'),
        ('bulgaria',            'BG'),
        ('венгрия',             'HU'),
        ('hungary',             'HU'),
        ('хорватия',            'HR'),
        ('croatia',             'HR'),
        ('словения',            'SI'),
        ('slovenia',            'SI'),
        ('словакия',            'SK'),
        ('slovakia',            'SK'),
        ('литва',               'LT'),
        ('lithuania',           'LT'),
        ('латвия',               'LV'),
        ('latvia',              'LV'),
        ('эстония',             'EE'),
        ('estonia',             'EE'),
        ('мальта',              'MT'),
        ('malta',               'MT'),
        ('кипр',                'CY'),
        ('cyprus',              'CY'),
        -- UK + EEA (non-EU)
        ('великобритания',      'GB'),
        ('англия',              'GB'),
        ('united kingdom',      'GB'),
        ('uk',                  'GB'),
        ('england',             'GB'),
        ('норвегия',            'NO'),
        ('norway',              'NO'),
        ('исландия',            'IS'),
        ('iceland',             'IS'),
        ('швейцария',           'CH'),
        ('switzerland',         'CH'),
        ('лихтенштейн',         'LI'),
        ('liechtenstein',       'LI'),
        -- Asia
        ('китай',               'CN'),
        ('china',               'CN'),
        ('турция',              'TR'),
        ('turkey',              'TR'),
        ('türkiye',             'TR'),
        ('turkiye',             'TR'),
        ('япония',              'JP'),
        ('japan',               'JP'),
        ('корея',               'KR'),
        ('южная корея',         'KR'),
        ('korea',               'KR'),
        ('south korea',         'KR'),
        ('индия',               'IN'),
        ('india',               'IN'),
        ('вьетнам',             'VN'),
        ('vietnam',             'VN'),
        ('таиланд',             'TH'),
        ('thailand',            'TH'),
        ('индонезия',           'ID'),
        ('indonesia',           'ID'),
        ('малайзия',            'MY'),
        ('malaysia',            'MY'),
        ('сингапур',            'SG'),
        ('singapore',           'SG'),
        ('филиппины',           'PH'),
        ('philippines',         'PH'),
        ('гонконг',             'HK'),
        ('hong kong',           'HK'),
        ('тайвань',             'TW'),
        ('taiwan',              'TW'),
        -- Middle East / Africa
        ('оаэ',                 'AE'),
        ('uae',                 'AE'),
        ('объединённые арабские эмираты', 'AE'),
        ('объединенные арабские эмираты', 'AE'),
        ('united arab emirates','AE'),
        ('саудовская аравия',   'SA'),
        ('saudi arabia',        'SA'),
        ('израиль',             'IL'),
        ('israel',              'IL'),
        ('египет',              'EG'),
        ('egypt',               'EG'),
        ('юар',                 'ZA'),
        ('южная африка',        'ZA'),
        ('south africa',        'ZA'),
        -- Americas
        ('сша',                 'US'),
        ('usa',                 'US'),
        ('us',                  'US'),
        ('united states',       'US'),
        ('америка',             'US'),
        ('канада',              'CA'),
        ('canada',              'CA'),
        ('мексика',             'MX'),
        ('mexico',              'MX'),
        ('бразилия',            'BR'),
        ('brazil',              'BR'),
        ('аргентина',           'AR'),
        ('argentina',           'AR'),
        ('чили',                'CL'),
        ('chile',               'CL'),
        -- Oceania
        ('австралия',           'AU'),
        ('australia',           'AU'),
        ('новая зеландия',      'NZ'),
        ('new zealand',         'NZ')
) AS m(name_lower, code)
WHERE bc.country_code IS NULL
  AND bc.country IS NOT NULL
  AND LOWER(TRIM(bc.country)) = m.name_lower;

-- =============================================================================
-- Part 4: Unmatched-rows diagnostic (REQ-1 AC#3)
--
-- Count rows that still have country_code IS NULL but had a non-empty `country`
-- value — i.e., values we couldn't map (junk, typos, missing from dictionary).
-- Emitted as NOTICE so CI logs carry the number for human triage without
-- failing the migration.
-- =============================================================================

DO $$
DECLARE
    v_suppliers_unmatched INT;
    v_buyer_companies_unmatched INT;
BEGIN
    SELECT COUNT(*) INTO v_suppliers_unmatched
    FROM kvota.suppliers
    WHERE country_code IS NULL
      AND country IS NOT NULL
      AND TRIM(country) <> '';

    SELECT COUNT(*) INTO v_buyer_companies_unmatched
    FROM kvota.buyer_companies
    WHERE country_code IS NULL
      AND country IS NOT NULL
      AND TRIM(country) <> '';

    RAISE NOTICE '[m295] Suppliers with unmatched country (country_code=NULL, country non-empty): %',
        v_suppliers_unmatched;
    RAISE NOTICE '[m295] Buyer companies with unmatched country (country_code=NULL, country non-empty): %',
        v_buyer_companies_unmatched;
END $$;

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (295, '295_add_country_code_to_suppliers_and_buyers', now())
ON CONFLICT (id) DO NOTHING;
