-- Migration 296: Replace VAT-rates seed with domestic-rate semantics.
-- Procurement bugs fix spec (April 2026) — Requirement 4.
--
-- Purpose:
--   Migration 269 seeded kvota.vat_rates_by_country with 15 countries at 20%
--   each, conflating "Russian import VAT" with "country domestic VAT". That
--   seed was incorrect for the new VAT-resolver rule (REQ-3):
--
--     rate = vat_rates_by_country[country_code].rate
--            when buyer_company.country_code === supplier.country_code
--          = 0 (export zero-rated) otherwise.
--
--   Under this rule the table must store the *domestic* VAT rate for each
--   country (e.g., DE=19%, RU=22%, CH=7.7%). This migration overwrites the
--   Migration 269 seed with correct values and expands coverage to the full
--   set Kvota trades with.
--
-- Seed source: spec Requirement 4 AC#1, with correction RU=22% (current 2026
-- rate, user-confirmed 2026-04-24). Full breakdown:
--   EAEU:            RU=22, KZ=12, BY=20, AM=20, KG=12
--   EU-27:           DE=19, FR=20, IT=22, ES=21, NL=21, BE=21, CZ=21, PL=23,
--                    AT=20, PT=23, GR=24, SE=25, DK=25, FI=24, IE=23, LU=17,
--                    RO=19, BG=20, HU=27, HR=25, SI=22, SK=23, LT=21, LV=21,
--                    EE=22, MT=18, CY=19
--   UK + EEA:        GB=20, NO=25, IS=24, CH=7.7, LI=7.7
--   Asia:            CN=13, TR=20, JP=10, KR=10, IN=18, VN=10, TH=7, ID=11,
--                    MY=10, SG=9, PH=12, HK=0, TW=5
--   Middle East / Africa: AE=5, SA=15, IL=17, EG=14, ZA=15
--   Americas:        US=0, CA=5, MX=16, BR=17, AR=21, CL=19
--   Oceania:         AU=10, NZ=15
--
-- Idempotency: ON CONFLICT (country_code) DO UPDATE SET rate=..., notes=...,
-- updated_at=NOW(). Safe to re-run.
--
-- Design reference: .kiro/specs/procurement-bugs-fix/requirements.md REQ-4, REQ-9

-- =============================================================================
-- Seed / upsert the full country set
-- =============================================================================

INSERT INTO kvota.vat_rates_by_country (country_code, rate, notes) VALUES
    -- EAEU (rate applies only when buyer AND supplier are both in that country)
    ('RU', 22,   'Россия — стандартная ставка 22% (текущая ставка 2026)'),
    ('KZ', 12,   'Казахстан — стандартная ставка 12%'),
    ('BY', 20,   'Беларусь — стандартная ставка 20%'),
    ('AM', 20,   'Армения — стандартная ставка 20%'),
    ('KG', 12,   'Киргизия — стандартная ставка 12%'),

    -- EU-27
    ('DE', 19,   'Германия — стандартная ставка 19%'),
    ('FR', 20,   'Франция — стандартная ставка 20%'),
    ('IT', 22,   'Италия — стандартная ставка 22%'),
    ('ES', 21,   'Испания — стандартная ставка 21%'),
    ('NL', 21,   'Нидерланды — стандартная ставка 21%'),
    ('BE', 21,   'Бельгия — стандартная ставка 21%'),
    ('CZ', 21,   'Чехия — стандартная ставка 21%'),
    ('PL', 23,   'Польша — стандартная ставка 23%'),
    ('AT', 20,   'Австрия — стандартная ставка 20%'),
    ('PT', 23,   'Португалия — стандартная ставка 23%'),
    ('GR', 24,   'Греция — стандартная ставка 24%'),
    ('SE', 25,   'Швеция — стандартная ставка 25%'),
    ('DK', 25,   'Дания — стандартная ставка 25%'),
    ('FI', 24,   'Финляндия — стандартная ставка 24%'),
    ('IE', 23,   'Ирландия — стандартная ставка 23%'),
    ('LU', 17,   'Люксембург — стандартная ставка 17%'),
    ('RO', 19,   'Румыния — стандартная ставка 19%'),
    ('BG', 20,   'Болгария — стандартная ставка 20%'),
    ('HU', 27,   'Венгрия — стандартная ставка 27%'),
    ('HR', 25,   'Хорватия — стандартная ставка 25%'),
    ('SI', 22,   'Словения — стандартная ставка 22%'),
    ('SK', 23,   'Словакия — стандартная ставка 23%'),
    ('LT', 21,   'Литва — стандартная ставка 21%'),
    ('LV', 21,   'Латвия — стандартная ставка 21%'),
    ('EE', 22,   'Эстония — стандартная ставка 22%'),
    ('MT', 18,   'Мальта — стандартная ставка 18%'),
    ('CY', 19,   'Кипр — стандартная ставка 19%'),

    -- UK + EEA (non-EU)
    ('GB', 20,   'Великобритания — стандартная ставка 20%'),
    ('NO', 25,   'Норвегия — стандартная ставка 25%'),
    ('IS', 24,   'Исландия — стандартная ставка 24%'),
    ('CH', 7.7,  'Швейцария — стандартная ставка 7.7%'),
    ('LI', 7.7,  'Лихтенштейн — стандартная ставка 7.7%'),

    -- Asia
    ('CN', 13,   'Китай — стандартная ставка 13%'),
    ('TR', 20,   'Турция — стандартная ставка 20%'),
    ('JP', 10,   'Япония — стандартная ставка 10%'),
    ('KR', 10,   'Южная Корея — стандартная ставка 10%'),
    ('IN', 18,   'Индия — стандартная ставка GST 18%'),
    ('VN', 10,   'Вьетнам — стандартная ставка 10%'),
    ('TH', 7,    'Таиланд — стандартная ставка 7%'),
    ('ID', 11,   'Индонезия — стандартная ставка 11%'),
    ('MY', 10,   'Малайзия — стандартная ставка SST 10%'),
    ('SG', 9,    'Сингапур — стандартная ставка GST 9%'),
    ('PH', 12,   'Филиппины — стандартная ставка 12%'),
    ('HK', 0,    'Гонконг — НДС не применяется (0%)'),
    ('TW', 5,    'Тайвань — стандартная ставка 5%'),

    -- Middle East / Africa
    ('AE', 5,    'ОАЭ — стандартная ставка 5%'),
    ('SA', 15,   'Саудовская Аравия — стандартная ставка 15%'),
    ('IL', 17,   'Израиль — стандартная ставка 17%'),
    ('EG', 14,   'Египет — стандартная ставка 14%'),
    ('ZA', 15,   'ЮАР — стандартная ставка 15%'),

    -- Americas
    ('US', 0,    'США — нет федерального НДС (sales tax на уровне штата)'),
    ('CA', 5,    'Канада — федеральный GST 5%'),
    ('MX', 16,   'Мексика — стандартная ставка 16%'),
    ('BR', 17,   'Бразилия — стандартная ставка ICMS 17%'),
    ('AR', 21,   'Аргентина — стандартная ставка 21%'),
    ('CL', 19,   'Чили — стандартная ставка 19%'),

    -- Oceania
    ('AU', 10,   'Австралия — стандартная ставка GST 10%'),
    ('NZ', 15,   'Новая Зеландия — стандартная ставка GST 15%')
ON CONFLICT (country_code) DO UPDATE SET
    rate       = EXCLUDED.rate,
    notes      = EXCLUDED.notes,
    updated_at = NOW();

-- =============================================================================
-- Updated documentation on table and rate column
-- =============================================================================

COMMENT ON TABLE kvota.vat_rates_by_country IS
    'Domestic VAT rates per country. Applied only when buyer_company.country_code '
    'matches supplier.country_code. Otherwise export zero-rated (0%).';

COMMENT ON COLUMN kvota.vat_rates_by_country.rate IS
    'Domestic VAT rate in percent (e.g., 19.00 = 19%). Applied by VAT resolver '
    'only when buyer and supplier countries match.';

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (296, '296_update_vat_rates_by_country', now())
ON CONFLICT (id) DO NOTHING;
