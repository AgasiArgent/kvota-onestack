-- Migration 304: tnved_user_choices — audit log для повторного использования
-- тарифных выборов customs-специалистов (Phase A Req 10, Req 11).
--
-- Mirror of kvota.tnved_classification_log pattern (migration 298).
-- При сохранении позиции сохраняется выбор customs (IMP/IMPDEMP/NDS variant
-- + manual rate payload). При открытии новой позиции с теми же
-- (tnved_code, country) система предлагает применить prev choice.
--
-- Срок действия (`valid_until`) — для тарифных выборов НЕ хранится:
-- Alta является source-of-truth для актуальности ставок (resolver всегда
-- отдаёт current data). Cost-aware expiry logic — Phase B (для сертификатов).
--
-- Idempotent: CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- DROP POLICY IF EXISTS + CREATE POLICY.

SET search_path TO kvota;

-- =============================================================================
-- Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.tnved_user_choices (
    id                       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id          UUID         NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    user_id                  UUID         NOT NULL REFERENCES auth.users(id),

    -- Match key
    tnved_code               VARCHAR(10)  NOT NULL,
    country_oksm             SMALLINT     NOT NULL REFERENCES kvota.countries(oksm_digital),

    -- Snapshots of chosen variants (JSONB clone of Rate fields)
    chosen_imp_variant       JSONB,           -- IMP (basic)
    chosen_impdemp_variant   JSONB,           -- IMPDEMP (антидемпинг) — NULL if not applicable
    chosen_impcomp_variant   JSONB,           -- IMPCOMP
    chosen_impdop_variant    JSONB,           -- IMPDOP
    chosen_imptmp_variant    JSONB,           -- IMPTMP
    chosen_nds_variant       JSONB,           -- NDS — selected льготная или default

    -- Manual override
    manual_override          BOOLEAN      NOT NULL DEFAULT FALSE,
    manual_rate_payload      JSONB,           -- when manual_override=true

    created_at               TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- =============================================================================
-- Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_user_choices_lookup
    ON kvota.tnved_user_choices(organization_id, tnved_code, country_oksm, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_choices_user
    ON kvota.tnved_user_choices(user_id, created_at DESC);

-- =============================================================================
-- RLS — org isolation via JWT app_metadata.organization_id
-- =============================================================================

ALTER TABLE kvota.tnved_user_choices ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tnved_user_choices_org_isolation ON kvota.tnved_user_choices;

CREATE POLICY tnved_user_choices_org_isolation
    ON kvota.tnved_user_choices
    FOR ALL
    TO authenticated
    USING (organization_id = (auth.jwt() -> 'app_metadata' ->> 'organization_id')::uuid);

-- =============================================================================
-- Documentation
-- =============================================================================

COMMENT ON TABLE kvota.tnved_user_choices IS
    'Phase A audit log: customs-specialist tariff choices, used to suggest '
    'autofill on repeating (tnved_code, country) pairs. Does NOT store '
    'valid_until — Alta is source-of-truth for tariff freshness. Cost-aware '
    'expiry (for certificates) is Phase B scope.';
