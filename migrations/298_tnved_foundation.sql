-- Migration 298: TN VED foundation — справочные таблицы для customs Phase 1.
-- customs-phase-1-rates-and-measures spec, Task 1.
--
-- Provisions infrastructure for Alta-Soft XML API integration:
--   - countries (ОКСМ + ISO + is_unfriendly per ПП 430-р)
--   - areals (EAEU, CIS, FTA-VN, FTA-IR, FTA-SRB, LRC, UNFRIENDLY)
--   - country_areals (M2M)
--   - tnved_codes (hierarchical 2→4→6→8→10-digit, populated organically from Alta)
--   - payment_types (8 types: IMP/EXP/NDS/AKC/IMPCOMP/IMPDEMP/IMPTMP/IMPDOP)
--   - tnved_rates (3-slot model: percent / per-unit / combined; supports
--                  ad-valorem + specific via value_1/value_2 + sign_1/sign_2)
--   - tnved_non_tariff_measures (certifications, bans, licenses)
--   - tnved_apu_cache (Alta АПУ classifier cache — Phase 2 surface)
--   - tnved_classification_log (audit trail)
--   - ALTER quote_items: country_of_origin_oksm, has_origin_certificate,
--                        has_fta_certificate
--
-- Customs rates SNAPSHOT for freeze: NOT a column on quote_items —
-- extends existing kvota.quote_versions.input_variables JSONB with
-- a `customs_rates` key (Q7 architectural simplification, see decisions.md).
-- Therefore migration does NOT add customs_rates_snapshot/customs_rates_snapshot_date.
--
-- Migration numbering: handoff doc said 296. 296 was taken by procurement-bugs-fix
-- (296_update_vat_rates_by_country). Bumped to 297, then to 298 because
-- 297_relax_cargo_places_constraints landed during spec authoring (verified
-- 2026-05-01 via git pull origin main on feature/customs-phase1 worktree).
--
-- Idempotency: re-running is safe (CREATE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS,
-- ON CONFLICT DO NOTHING for seeds).
--
-- Design references:
--   - .kiro/specs/customs-phase-1-rates-and-measures/design.md § "Data Model — Migration 298"
--   - .kiro/specs/customs-phase-1-rates-and-measures/decisions.md (Q3 last_used_at column, Q7 snapshot)
--   - docs/plans/2026-04-22-customs-ved-integration-handoff.md § "Target State"


-- =============================================================================
-- Part 1: countries — ОКСМ digital + ISO alpha-2/alpha-3 + name_ru/name_en
-- =============================================================================
-- ОКСМ — Общероссийский классификатор стран мира (Росстандарт). Numeric codes
-- are aligned with ISO 3166-1 numeric. Stored as SMALLINT (max code is ~896).
--
-- Seed covers МастерБэринг's primary trading partners (EU, EAEU, CIS, China,
-- Turkey, India, USA, и др. — ~70 most relevant). Additional countries are
-- added manually as they become needed. is_unfriendly flag manually maintained
-- per ПП РФ № 430-р (фиксация на дату миграции 2026-05-01).

CREATE TABLE IF NOT EXISTS kvota.countries (
    oksm_digital  SMALLINT      PRIMARY KEY,
    iso_alpha2    CHAR(2)       NOT NULL UNIQUE,
    iso_alpha3    CHAR(3)       NOT NULL UNIQUE,
    name_ru       VARCHAR(200)  NOT NULL,
    name_en       VARCHAR(200)  NOT NULL,
    is_unfriendly BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

COMMENT ON TABLE kvota.countries IS
    'ОКСМ countries (Росстандарт), aligned with ISO 3166-1 numeric. is_unfriendly '
    'is UI-only flag per ПП 430-р; rate_resolver does NOT use it (Alta encodes '
    'effects in rate response automatically — see gotcha #11).';

COMMENT ON COLUMN kvota.countries.is_unfriendly IS
    'Per ПП РФ № 430-р. Manual seed at migration date 2026-05-01. Updates require '
    'manual UPDATE statement when ПП is amended.';

-- Seed: ~70 primary trading countries. Expandable.
INSERT INTO kvota.countries (oksm_digital, iso_alpha2, iso_alpha3, name_ru, name_en) VALUES
    -- Russia + EAEU + CIS
    (643, 'RU', 'RUS', 'Россия',                 'Russia'),
    (398, 'KZ', 'KAZ', 'Казахстан',              'Kazakhstan'),
    (112, 'BY', 'BLR', 'Беларусь',               'Belarus'),
    (51,  'AM', 'ARM', 'Армения',                'Armenia'),
    (417, 'KG', 'KGZ', 'Киргизия',               'Kyrgyzstan'),
    (762, 'TJ', 'TJK', 'Таджикистан',            'Tajikistan'),
    (860, 'UZ', 'UZB', 'Узбекистан',             'Uzbekistan'),
    (795, 'TM', 'TKM', 'Туркменистан',           'Turkmenistan'),
    (31,  'AZ', 'AZE', 'Азербайджан',            'Azerbaijan'),
    (268, 'GE', 'GEO', 'Грузия',                 'Georgia'),
    (498, 'MD', 'MDA', 'Молдова',                'Moldova'),
    (804, 'UA', 'UKR', 'Украина',                'Ukraine'),
    -- EU-27
    (276, 'DE', 'DEU', 'Германия',               'Germany'),
    (250, 'FR', 'FRA', 'Франция',                'France'),
    (380, 'IT', 'ITA', 'Италия',                 'Italy'),
    (724, 'ES', 'ESP', 'Испания',                'Spain'),
    (528, 'NL', 'NLD', 'Нидерланды',             'Netherlands'),
    (56,  'BE', 'BEL', 'Бельгия',                'Belgium'),
    (203, 'CZ', 'CZE', 'Чехия',                  'Czechia'),
    (616, 'PL', 'POL', 'Польша',                 'Poland'),
    (40,  'AT', 'AUT', 'Австрия',                'Austria'),
    (620, 'PT', 'PRT', 'Португалия',             'Portugal'),
    (300, 'GR', 'GRC', 'Греция',                 'Greece'),
    (752, 'SE', 'SWE', 'Швеция',                 'Sweden'),
    (208, 'DK', 'DNK', 'Дания',                  'Denmark'),
    (246, 'FI', 'FIN', 'Финляндия',              'Finland'),
    (372, 'IE', 'IRL', 'Ирландия',               'Ireland'),
    (442, 'LU', 'LUX', 'Люксембург',             'Luxembourg'),
    (642, 'RO', 'ROU', 'Румыния',                'Romania'),
    (100, 'BG', 'BGR', 'Болгария',               'Bulgaria'),
    (348, 'HU', 'HUN', 'Венгрия',                'Hungary'),
    (191, 'HR', 'HRV', 'Хорватия',               'Croatia'),
    (705, 'SI', 'SVN', 'Словения',               'Slovenia'),
    (703, 'SK', 'SVK', 'Словакия',               'Slovakia'),
    (440, 'LT', 'LTU', 'Литва',                  'Lithuania'),
    (428, 'LV', 'LVA', 'Латвия',                 'Latvia'),
    (233, 'EE', 'EST', 'Эстония',                'Estonia'),
    (470, 'MT', 'MLT', 'Мальта',                 'Malta'),
    (196, 'CY', 'CYP', 'Кипр',                   'Cyprus'),
    -- UK + EFTA
    (826, 'GB', 'GBR', 'Великобритания',         'United Kingdom'),
    (578, 'NO', 'NOR', 'Норвегия',               'Norway'),
    (756, 'CH', 'CHE', 'Швейцария',              'Switzerland'),
    (352, 'IS', 'ISL', 'Исландия',               'Iceland'),
    (438, 'LI', 'LIE', 'Лихтенштейн',            'Liechtenstein'),
    -- Other Europe
    (792, 'TR', 'TUR', 'Турция',                 'Turkey'),
    (688, 'RS', 'SRB', 'Сербия',                 'Serbia'),
    (807, 'MK', 'MKD', 'Северная Македония',     'North Macedonia'),
    (8,   'AL', 'ALB', 'Албания',                'Albania'),
    -- Asia
    (156, 'CN', 'CHN', 'Китай',                  'China'),
    (344, 'HK', 'HKG', 'Гонконг',                'Hong Kong'),
    (158, 'TW', 'TWN', 'Тайвань',                'Taiwan'),
    (392, 'JP', 'JPN', 'Япония',                 'Japan'),
    (410, 'KR', 'KOR', 'Республика Корея',       'South Korea'),
    (704, 'VN', 'VNM', 'Вьетнам',                'Vietnam'),
    (764, 'TH', 'THA', 'Таиланд',                'Thailand'),
    (458, 'MY', 'MYS', 'Малайзия',               'Malaysia'),
    (360, 'ID', 'IDN', 'Индонезия',              'Indonesia'),
    (608, 'PH', 'PHL', 'Филиппины',              'Philippines'),
    (702, 'SG', 'SGP', 'Сингапур',               'Singapore'),
    (356, 'IN', 'IND', 'Индия',                  'India'),
    (586, 'PK', 'PAK', 'Пакистан',               'Pakistan'),
    (50,  'BD', 'BGD', 'Бангладеш',              'Bangladesh'),
    (524, 'NP', 'NPL', 'Непал',                  'Nepal'),
    (144, 'LK', 'LKA', 'Шри-Ланка',              'Sri Lanka'),
    -- Middle East
    (364, 'IR', 'IRN', 'Иран',                   'Iran'),
    (368, 'IQ', 'IRQ', 'Ирак',                   'Iraq'),
    (682, 'SA', 'SAU', 'Саудовская Аравия',      'Saudi Arabia'),
    (784, 'AE', 'ARE', 'ОАЭ',                    'United Arab Emirates'),
    (376, 'IL', 'ISR', 'Израиль',                'Israel'),
    (400, 'JO', 'JOR', 'Иордания',               'Jordan'),
    (760, 'SY', 'SYR', 'Сирия',                  'Syria'),
    (422, 'LB', 'LBN', 'Ливан',                  'Lebanon'),
    -- Africa
    (818, 'EG', 'EGY', 'Египет',                 'Egypt'),
    (504, 'MA', 'MAR', 'Марокко',                'Morocco'),
    (788, 'TN', 'TUN', 'Тунис',                  'Tunisia'),
    (12,  'DZ', 'DZA', 'Алжир',                  'Algeria'),
    (710, 'ZA', 'ZAF', 'ЮАР',                    'South Africa'),
    (566, 'NG', 'NGA', 'Нигерия',                'Nigeria'),
    -- Americas
    (840, 'US', 'USA', 'США',                    'United States'),
    (124, 'CA', 'CAN', 'Канада',                 'Canada'),
    (484, 'MX', 'MEX', 'Мексика',                'Mexico'),
    (76,  'BR', 'BRA', 'Бразилия',               'Brazil'),
    (32,  'AR', 'ARG', 'Аргентина',              'Argentina'),
    (152, 'CL', 'CHL', 'Чили',                   'Chile'),
    (170, 'CO', 'COL', 'Колумбия',               'Colombia'),
    (604, 'PE', 'PER', 'Перу',                   'Peru'),
    -- Oceania
    (36,  'AU', 'AUS', 'Австралия',              'Australia'),
    (554, 'NZ', 'NZL', 'Новая Зеландия',         'New Zealand')
ON CONFLICT (oksm_digital) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_countries_iso_alpha2
    ON kvota.countries(iso_alpha2);


-- =============================================================================
-- Part 2: is_unfriendly UPDATE per ПП РФ № 430-р
-- =============================================================================
-- Дата фиксации: 2026-05-01. Источник: pravo.gov.ru (ПП 430-р).
-- Обновлять вручную при поправках к постановлению.

UPDATE kvota.countries SET is_unfriendly = TRUE WHERE iso_alpha2 IN (
    -- North America
    'US','CA',
    -- UK + EFTA
    'GB','NO','CH','IS','LI',
    -- EU-27 (все государства-члены)
    'DE','FR','IT','ES','NL','BE','CZ','PL','AT','PT','GR','SE','DK','FI','IE',
    'LU','RO','BG','HU','HR','SI','SK','LT','LV','EE','MT','CY',
    -- Asia-Pacific aligned
    'AU','NZ','JP','KR','SG','TW',
    -- Eastern Europe + Balkans
    'UA','AL','MK'
    -- Note: ПП 430-р also includes Andorra, Monaco, San Marino, Micronesia,
    -- Bahamas, Montenegro and others not currently in the countries seed.
    -- Add them here if/when they're inserted into kvota.countries.
);


-- =============================================================================
-- Part 3: areals — economic zones (EAEU, CIS, FTA, etc.)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.areals (
    code        VARCHAR(20)  PRIMARY KEY,
    name_ru     VARCHAR(200) NOT NULL,
    description TEXT
);

COMMENT ON TABLE kvota.areals IS
    'Экономические зоны/преференциальные ареалы. Используются как ключ '
    'tnved_rates.country_or_areal с префиксом A: (e.g., A:EAEU). Lookup '
    'в rate_resolver: Tier 1 exact country (C:643) → Tier 2 areal (A:EAEU) → '
    'Tier 3 base (NULL).';

INSERT INTO kvota.areals (code, name_ru, description) VALUES
    ('EAEU',      'ЕАЭС',                      'Евразийский экономический союз: РФ, Беларусь, Казахстан, Армения, Киргизия'),
    ('CIS',       'СНГ',                       'Содружество Независимых Государств'),
    ('FTA-VN',    'ЗСТ Вьетнам',               'Соглашение о свободной торговле ЕАЭС–Вьетнам'),
    ('FTA-IR',    'ЗСТ Иран',                  'Соглашение о свободной торговле ЕАЭС–Иран'),
    ('FTA-SRB',   'ЗСТ Сербия',                'Соглашение о свободной торговле ЕАЭС–Сербия'),
    ('LRC',       'Наименее развитые страны',  'Least Developed Countries — преференциальный режим'),
    ('UNFRIENDLY','Недружественные страны',    'Список недружественных государств per ПП 430-р')
ON CONFLICT (code) DO NOTHING;


-- =============================================================================
-- Part 4: country_areals — M2M mapping
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.country_areals (
    country_oksm SMALLINT     NOT NULL REFERENCES kvota.countries(oksm_digital) ON DELETE CASCADE,
    areal_code   VARCHAR(20)  NOT NULL REFERENCES kvota.areals(code) ON DELETE CASCADE,
    PRIMARY KEY (country_oksm, areal_code)
);

COMMENT ON TABLE kvota.country_areals IS
    'M2M mapping: country → economic areal. Один country может попадать в '
    'несколько ареалов (e.g., Россия в EAEU и CIS).';

CREATE INDEX IF NOT EXISTS idx_country_areals_areal
    ON kvota.country_areals(areal_code);

-- EAEU members
INSERT INTO kvota.country_areals (country_oksm, areal_code)
SELECT oksm_digital, 'EAEU' FROM kvota.countries
WHERE iso_alpha2 IN ('RU','KZ','BY','AM','KG')
ON CONFLICT DO NOTHING;

-- CIS members (broader than EAEU; includes EAEU + others)
INSERT INTO kvota.country_areals (country_oksm, areal_code)
SELECT oksm_digital, 'CIS' FROM kvota.countries
WHERE iso_alpha2 IN ('RU','KZ','BY','AM','KG','TJ','UZ','MD','AZ','TM')
ON CONFLICT DO NOTHING;

-- FTA-VN (Vietnam)
INSERT INTO kvota.country_areals (country_oksm, areal_code)
SELECT oksm_digital, 'FTA-VN' FROM kvota.countries WHERE iso_alpha2 = 'VN'
ON CONFLICT DO NOTHING;

-- FTA-IR (Iran)
INSERT INTO kvota.country_areals (country_oksm, areal_code)
SELECT oksm_digital, 'FTA-IR' FROM kvota.countries WHERE iso_alpha2 = 'IR'
ON CONFLICT DO NOTHING;

-- FTA-SRB (Serbia)
INSERT INTO kvota.country_areals (country_oksm, areal_code)
SELECT oksm_digital, 'FTA-SRB' FROM kvota.countries WHERE iso_alpha2 = 'RS'
ON CONFLICT DO NOTHING;

-- UNFRIENDLY mirror of countries.is_unfriendly
INSERT INTO kvota.country_areals (country_oksm, areal_code)
SELECT oksm_digital, 'UNFRIENDLY' FROM kvota.countries WHERE is_unfriendly = TRUE
ON CONFLICT DO NOTHING;


-- =============================================================================
-- Part 5: tnved_codes — hierarchical 2/4/6/8/10-digit codes
-- =============================================================================
-- Self-FK on parent_code uses DEFERRABLE INITIALLY DEFERRED to allow batch
-- inserts in any order within a transaction. Phase 1 seeds only the 99
-- two-digit chapter roots; deeper codes accrete organically from Alta Такса.

CREATE TABLE IF NOT EXISTS kvota.tnved_codes (
    code         VARCHAR(10) PRIMARY KEY,
    parent_code  VARCHAR(10) REFERENCES kvota.tnved_codes(code) DEFERRABLE INITIALLY DEFERRED,
    description  TEXT        NOT NULL,
    prim         VARCHAR(10),
    fetched_from VARCHAR(20) NOT NULL DEFAULT 'alta',
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tnved_codes_fetched_from_check
        CHECK (fetched_from IN ('alta', 'manual'))
);

COMMENT ON TABLE kvota.tnved_codes IS
    'Hierarchical ТН ВЭД codes (2/4/6/8/10-digit). Roots (2-digit chapters) '
    'seeded inline. Deeper codes accrete from Alta Такса response on first '
    'resolve. parent_code self-FK is DEFERRABLE so batch inserts can land '
    'in any order within a transaction.';

COMMENT ON COLUMN kvota.tnved_codes.prim IS
    'Primary unit code per Alta Такса: 166=kg, 111=l, 796=шт. Used by '
    'customs_calc.calculate_duty() to resolve unit_quantity for specific rates.';

-- Seed: 99 two-digit chapter roots (00..99). Description placeholder; real
-- chapter names land via Alta on first lookup that returns hierarchy.
DO $$
DECLARE
    chapter_code TEXT;
BEGIN
    FOR i IN 0..99 LOOP
        chapter_code := lpad(i::TEXT, 2, '0');
        INSERT INTO kvota.tnved_codes (code, description, fetched_from)
        VALUES (chapter_code, 'Группа ' || chapter_code || ' (loaded on demand from Alta)', 'manual')
        ON CONFLICT (code) DO NOTHING;
    END LOOP;
END $$;


-- =============================================================================
-- Part 6: payment_types — 8 строгих типов
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.payment_types (
    code                   VARCHAR(20)  PRIMARY KEY,
    name_ru                VARCHAR(200) NOT NULL,
    depends_on_country     BOOLEAN NOT NULL DEFAULT FALSE,
    depends_on_certificate BOOLEAN NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE kvota.payment_types IS
    '8 фиксированных типов customs payments. depends_on_country=TRUE — ставка '
    'варьируется по стране (импортная пошлина, comp/demp/tmp). depends_on_certificate=TRUE — '
    'ставка может меняться при наличии сертификата происхождения / FTA.';

INSERT INTO kvota.payment_types (code, name_ru, depends_on_country, depends_on_certificate) VALUES
    ('IMP',     'Импортная пошлина',                          TRUE,  TRUE),
    ('EXP',     'Экспортная пошлина',                         FALSE, FALSE),
    ('NDS',     'НДС при импорте',                            FALSE, FALSE),
    ('AKC',     'Акциз',                                      FALSE, FALSE),
    ('IMPCOMP', 'Компенсационная пошлина',                    TRUE,  FALSE),
    ('IMPDEMP', 'Антидемпинговая пошлина',                    TRUE,  FALSE),
    ('IMPTMP',  'Временная (специальная) пошлина',            TRUE,  FALSE),
    ('IMPDOP',  'Дополнительная импортная пошлина',           TRUE,  FALSE)
ON CONFLICT (code) DO NOTHING;


-- =============================================================================
-- Part 7: tnved_rates — 3-slot rate model
-- =============================================================================
-- Supports: ad-valorem (slot 1 = percent), specific (slot 1 = unit + currency),
-- combined (slot 1 + slot 2 + sign_1 ∈ {'>', '+'}), three-component (slots 1+2+3).
--
-- country_or_areal encoding:
--   'C:643'   — exact country (OKSM digital)
--   'A:EAEU'  — areal code
--   NULL      — base rate (applies to any country not matched above)
--
-- source values:
--   'alta-live'        — fetched on demand via rate_resolver lazy-fetch
--   'alta-revalidate'  — fetched by weekly cron
--   'manual'           — entered by hand (legacy / fixup)
-- last_used_at — Q3 decision: column on row, updated on each successful
-- resolve. Cron uses ORDER BY last_used_at DESC to revalidate top-1000.

CREATE TABLE IF NOT EXISTS kvota.tnved_rates (
    id                      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tnved_code              VARCHAR(10)  NOT NULL REFERENCES kvota.tnved_codes(code),
    payment_type            VARCHAR(20)  NOT NULL REFERENCES kvota.payment_types(code),
    country_or_areal        VARCHAR(30),

    valid_from              DATE         NOT NULL,
    valid_to                DATE,

    -- Slot 1 (always present)
    value_1_number          DECIMAL(20, 6),
    value_1_unit            VARCHAR(20),
    value_1_currency        VARCHAR(3),

    -- Slot 2 (combined rates)
    value_2_number          DECIMAL(20, 6),
    value_2_unit            VARCHAR(20),
    value_2_currency        VARCHAR(3),
    sign_1                  VARCHAR(2),

    -- Slot 3 (three-component, rare)
    value_3_number          DECIMAL(20, 6),
    value_3_unit            VARCHAR(20),
    value_3_currency        VARCHAR(3),
    sign_2                  VARCHAR(2),

    raw_value_string        TEXT,

    certificate_required    BOOLEAN      NOT NULL DEFAULT FALSE,
    sp_certificate_required BOOLEAN      NOT NULL DEFAULT FALSE,

    source                  VARCHAR(20)  NOT NULL,
    source_fetched_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_used_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),

    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT tnved_rates_country_or_areal_format_check
        CHECK (country_or_areal IS NULL
               OR country_or_areal LIKE 'C:%'
               OR country_or_areal LIKE 'A:%'),
    CONSTRAINT tnved_rates_source_check
        CHECK (source IN ('alta-live', 'alta-revalidate', 'manual')),
    CONSTRAINT tnved_rates_sign_1_check
        CHECK (sign_1 IS NULL OR sign_1 IN ('+', '>')),
    CONSTRAINT uq_tnved_rates UNIQUE (
        tnved_code, payment_type, country_or_areal, valid_from,
        certificate_required, sp_certificate_required
    )
);

COMMENT ON TABLE kvota.tnved_rates IS
    'Customs duty rates per (ТН ВЭД code, payment_type, country/areal, valid period). '
    '3-slot model supports ad-valorem, specific, and combined rates. '
    'See services/customs_calc.py:calculate_duty() for evaluation logic.';

COMMENT ON COLUMN kvota.tnved_rates.country_or_areal IS
    'Lookup priority key: C:{oksm} (exact country) | A:{areal_code} (zone) | NULL (base). '
    'Resolved by services/rate_resolver.py three-tier lookup.';

COMMENT ON COLUMN kvota.tnved_rates.last_used_at IS
    'Updated on each successful resolve (fire-and-forget, не блокирует response). '
    'Используется api/cron.py:cron_revalidate_rates для выбора top-1000.';

CREATE INDEX IF NOT EXISTS idx_rates_lookup
    ON kvota.tnved_rates(tnved_code, payment_type, valid_from DESC);

CREATE INDEX IF NOT EXISTS idx_rates_country
    ON kvota.tnved_rates(country_or_areal)
    WHERE country_or_areal IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rates_last_used
    ON kvota.tnved_rates(last_used_at DESC);

CREATE INDEX IF NOT EXISTS idx_rates_source_fetched_at
    ON kvota.tnved_rates(source_fetched_at)
    WHERE source_fetched_at IS NOT NULL;


-- =============================================================================
-- Part 8: tnved_non_tariff_measures — certifications, bans, licenses
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.tnved_non_tariff_measures (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tnved_code        VARCHAR(10)  NOT NULL REFERENCES kvota.tnved_codes(code),
    country_or_areal  VARCHAR(30),
    measure_type      VARCHAR(50)  NOT NULL,
    name              VARCHAR(500) NOT NULL,
    description       TEXT,
    document_basis    TEXT,
    document_link     TEXT,
    valid_from        DATE,
    valid_to          DATE,
    source            VARCHAR(20)  NOT NULL,
    source_fetched_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT tnved_measures_country_or_areal_format_check
        CHECK (country_or_areal IS NULL
               OR country_or_areal LIKE 'C:%'
               OR country_or_areal LIKE 'A:%'),
    CONSTRAINT tnved_measures_source_check
        CHECK (source IN ('alta-live', 'alta-revalidate', 'manual'))
);

COMMENT ON TABLE kvota.tnved_non_tariff_measures IS
    'Меры нетарифного регулирования (сертификации, запреты, лицензии). '
    'Fetched on explicit UI request only — отдельная тарификация ~3₽/call '
    '(gotcha #5).';

CREATE INDEX IF NOT EXISTS idx_measures_lookup
    ON kvota.tnved_non_tariff_measures(tnved_code, country_or_areal);


-- =============================================================================
-- Part 9: tnved_apu_cache — Alta АПУ classifier cache (Phase 2 surface)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.tnved_apu_cache (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text    TEXT         NOT NULL,
    payload_id    VARCHAR(100),
    response_json JSONB        NOT NULL,
    last_used_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE kvota.tnved_apu_cache IS
    'Alta АПУ classifier (interactive picker) response cache. Phase 2 surface — '
    'клиент существует с Phase 1, UI deferred. last_used_at — для LRU eviction.';

CREATE INDEX IF NOT EXISTS idx_apu_cache_query_text
    ON kvota.tnved_apu_cache USING gin (to_tsvector('russian', query_text));

CREATE INDEX IF NOT EXISTS idx_apu_cache_last_used
    ON kvota.tnved_apu_cache(last_used_at DESC);


-- =============================================================================
-- Part 10: tnved_classification_log — audit trail of Express/АПУ calls
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.tnved_classification_log (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_item_id   UUID         REFERENCES kvota.quote_items(id) ON DELETE SET NULL,
    method          VARCHAR(20)  NOT NULL,
    input_text      TEXT         NOT NULL,
    suggested_codes JSONB        NOT NULL,
    chosen_code     VARCHAR(10),
    user_id         UUID         REFERENCES auth.users(id),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT tnved_class_log_method_check
        CHECK (method IN ('express', 'apu', 'manual', 'history'))
);

COMMENT ON TABLE kvota.tnved_classification_log IS
    'Audit trail классификаций (Alta Express batch, АПУ interactive, manual, '
    'history-based autofill). Для cost-tracking + accuracy eval Phase 3.';

CREATE INDEX IF NOT EXISTS idx_class_log_quote_item
    ON kvota.tnved_classification_log(quote_item_id)
    WHERE quote_item_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_class_log_created_at
    ON kvota.tnved_classification_log(created_at DESC);


-- =============================================================================
-- Part 11: ALTER kvota.quote_items — 3 new columns
-- =============================================================================
-- DROPPED from REQ-1 per Q7 architectural simplification:
--   - customs_rates_snapshot JSONB
--   - customs_rates_snapshot_date DATE
-- Snapshot lives in kvota.quote_versions.input_variables JSONB
-- under 'customs_rates' key (see services/customs_freeze_service.py).

ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS country_of_origin_oksm SMALLINT
        REFERENCES kvota.countries(oksm_digital),
    ADD COLUMN IF NOT EXISTS has_origin_certificate BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS has_fta_certificate    BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN kvota.quote_items.country_of_origin_oksm IS
    'ОКСМ digital code страны происхождения товара. NB: distinct from '
    'kvota.suppliers.country_code (ISO alpha-2 — для контрагентов). Origin '
    'country отражает фактическое происхождение для customs lookup.';

COMMENT ON COLUMN kvota.quote_items.has_origin_certificate IS
    'Наличие сертификата происхождения. Влияет на rate_resolver выбор ставки '
    'когда payment_type.depends_on_certificate = TRUE.';

COMMENT ON COLUMN kvota.quote_items.has_fta_certificate IS
    'Наличие сертификата FTA (зона свободной торговли). Используется для '
    'преференциальных режимов EAEU FTA-VN/FTA-IR/FTA-SRB.';

CREATE INDEX IF NOT EXISTS idx_quote_items_country_of_origin
    ON kvota.quote_items(country_of_origin_oksm)
    WHERE country_of_origin_oksm IS NOT NULL;


-- =============================================================================
-- Part 12: RLS — reference tables readable by all authenticated, mutation
--               restricted to service_role (which bypasses RLS).
-- =============================================================================
-- Reference data (countries, areals, tnved_*) is shared across organizations.
-- Service-role API is the only writer; direct frontend Supabase JS reads
-- countries dropdown (REQ-7 AC#10).

DO $$
DECLARE
    tbl TEXT;
    tables TEXT[] := ARRAY[
        'countries', 'areals', 'country_areals',
        'tnved_codes', 'payment_types',
        'tnved_rates', 'tnved_non_tariff_measures',
        'tnved_apu_cache', 'tnved_classification_log'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE kvota.%I ENABLE ROW LEVEL SECURITY', tbl);
        -- SELECT for all authenticated users (reference data is org-shared)
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'kvota' AND tablename = tbl
              AND policyname = format('%s_authenticated_select', tbl)
        ) THEN
            EXECUTE format(
                'CREATE POLICY %I ON kvota.%I FOR SELECT TO authenticated USING (true)',
                tbl || '_authenticated_select', tbl
            );
        END IF;
    END LOOP;
END $$;


-- =============================================================================
-- Part 13: Migration tracking + observability NOTICEs
-- =============================================================================

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (298, '298_tnved_foundation', now())
ON CONFLICT (id) DO NOTHING;

DO $$
DECLARE
    n_countries        INT;
    n_unfriendly       INT;
    n_areals           INT;
    n_country_areals   INT;
    n_tnved_codes      INT;
    n_payment_types    INT;
BEGIN
    SELECT COUNT(*) INTO n_countries        FROM kvota.countries;
    SELECT COUNT(*) INTO n_unfriendly       FROM kvota.countries WHERE is_unfriendly = TRUE;
    SELECT COUNT(*) INTO n_areals           FROM kvota.areals;
    SELECT COUNT(*) INTO n_country_areals   FROM kvota.country_areals;
    SELECT COUNT(*) INTO n_tnved_codes      FROM kvota.tnved_codes;
    SELECT COUNT(*) INTO n_payment_types    FROM kvota.payment_types;

    RAISE NOTICE 'Migration 298 seed counts: countries=%, unfriendly=%, areals=%, country_areals=%, tnved_codes(roots)=%, payment_types=%',
        n_countries, n_unfriendly, n_areals, n_country_areals, n_tnved_codes, n_payment_types;
END $$;
