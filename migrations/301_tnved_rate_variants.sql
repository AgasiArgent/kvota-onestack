-- Migration 301: Rate variants — capture Alta Такса XML metadata that
-- distinguishes льготные ставки from стандартные.
--
-- Background: migration 298's `tnved_rates` schema only kept value + raw
-- string. Production probe of HS=7326909807 × Китай returned 8 NDS rows
-- (0%, 10%, 22%) and 5 IMP rows (Беспошлинно, 7.5%) — each with rich
-- metadata that the parser threw away:
--   - <Directory><RuName/EnName>  — category (e.g., "nds_med", "nds_inv")
--   - <Condition>                 — when this rate applies (e.g., "- Прочие")
--   - <MainCondition>             — main scope statement
--   - <Document> / <Link>         — legal basis (Постановление 1042 etc.)
--   - <Prim> / <OrderCond>        — IMP comment + condition text
--   - <Order>                     — decision number reference
--
-- The resolver was returning the FIRST match per payment_type, hitting the
-- льготная (0%/Беспошлинно) — which was wrong for normal goods like
-- shaybas. UI showed «НДС 0%» as if applicable. This migration adds the
-- columns the parser will populate, so the API + UI can present every
-- variant with full context — and customs-specialist picks the right one.
--
-- Idempotency: ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT IF EXISTS.
-- The cache is truncated because existing rows have no metadata to
-- preserve — they'll repopulate organically on next resolve.

-- =============================================================================
-- Part 1: ALTER tnved_rates — add metadata columns
-- =============================================================================

ALTER TABLE kvota.tnved_rates
    ADD COLUMN IF NOT EXISTS description     TEXT,
    ADD COLUMN IF NOT EXISTS category_code   VARCHAR(50)  NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS category_ru     TEXT,
    ADD COLUMN IF NOT EXISTS condition_text  TEXT,
    ADD COLUMN IF NOT EXISTS legal_document  TEXT,
    ADD COLUMN IF NOT EXISTS legal_link      TEXT,
    ADD COLUMN IF NOT EXISTS order_ref       VARCHAR(50),
    ADD COLUMN IF NOT EXISTS is_default      BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN kvota.tnved_rates.description IS
    'Free-text description distinguishing this variant. For IMP: <Prim> '
    '(e.g., "- зажимное устройство"). For NDS/AKC: <Condition> '
    '(e.g., "- Медизделия (Регистрационное удостоверение)").';

COMMENT ON COLUMN kvota.tnved_rates.category_code IS
    'Stable identifier of the rate category. For NDS: <Directory><EnName> '
    '(e.g., "nds_med", "nds_inv", "nds_lecr"). For IMP: derived from '
    '<Order> (e.g., "09b00130"). NULL for "base" rate without category. '
    'Part of the unique key — multiple variants per (code, payment_type) '
    'distinguished by this column.';

COMMENT ON COLUMN kvota.tnved_rates.category_ru IS
    'Human-readable category name. For NDS: <Directory><RuName> '
    '(e.g., "Жизненно необходимая медтехника", "Технические средства для '
    'инвалидов"). NULL when category_code is NULL.';

COMMENT ON COLUMN kvota.tnved_rates.condition_text IS
    'Main condition statement. For NDS: <MainCondition> (e.g., "Изделия '
    'прочие из черных металлов (НДС Медизделия):"). For IMP: <OrderCond> '
    '(e.g., "Льгота по уплате... предоставляется", "НЕТ льготы").';

COMMENT ON COLUMN kvota.tnved_rates.legal_document IS
    'Legal basis. <Document> from Alta. E.g., "Постановление 1042 от '
    '30.09.2015 Правительства РФ".';

COMMENT ON COLUMN kvota.tnved_rates.legal_link IS
    'URL to legal text on alta.ru (e.g., '
    '"https://www.alta.ru/tamdoc/15ps1042/").';

COMMENT ON COLUMN kvota.tnved_rates.order_ref IS
    'Decision/order number reference. For IMP: <Order> (e.g., "реш.80", '
    '"09b00130"). NULL for NDS/AKC.';

COMMENT ON COLUMN kvota.tnved_rates.is_default IS
    'TRUE when this is the "default" rate that applies absent any лгота '
    'classification. Computed at parse time: for IMP — Prim contains '
    '"прочее" or is empty; for NDS — Condition contains "Прочие". UI uses '
    'this as the pre-selected option in the rate breakdown.';

-- =============================================================================
-- Part 2: Drop old unique constraint, replace with category-aware index
-- =============================================================================
-- The old uq_tnved_rates blocked льготные variants from coexisting with the
-- стандартная rate. New unique index uses COALESCE so NULL category_code
-- (base/non-categorized rate) still gets uniqueness, while distinct
-- categories live side by side.

ALTER TABLE kvota.tnved_rates
    DROP CONSTRAINT IF EXISTS uq_tnved_rates;

ALTER TABLE kvota.tnved_rates
    DROP CONSTRAINT IF EXISTS uq_tnved_rates_v2;

ALTER TABLE kvota.tnved_rates
    ADD CONSTRAINT uq_tnved_rates_v2 UNIQUE (
        tnved_code,
        payment_type,
        country_or_areal,
        valid_from,
        certificate_required,
        sp_certificate_required,
        category_code
    );

COMMENT ON CONSTRAINT uq_tnved_rates_v2 ON kvota.tnved_rates IS
    'Replaces uq_tnved_rates from migration 298. Adds category_code to the '
    'natural key so льготные variants (e.g., NDS 10% медтехника) coexist '
    'with the стандартная rate (e.g., NDS 22% Прочие). category_code is '
    'NOT NULL with empty-string default — Supabase upsert(on_conflict=...) '
    'requires plain column unique constraints (no expression indexes).';

-- =============================================================================
-- Part 3: Truncate stale cache
-- =============================================================================
-- Existing rows lack metadata — resolver would still hit them and return
-- empty descriptions. Faster to wipe and let the next resolve repopulate
-- (single Alta packet) than backfill from scratch. Safe because:
--   - tnved_rates is a derived cache, not source-of-truth
--   - Frozen quotes saved their snapshot to quote_versions.input_variables
--     (Q7 design), so live cache is repopulation-only.

TRUNCATE TABLE kvota.tnved_rates CASCADE;
