-- Migration 306: quote_certificates + quote_certificate_items
-- Phase B (customs-shared-certificates) Req 1.
--
-- Atomic schema + RLS + indexes + CHECK constraint + backfill from
-- legacy customs_*_expenses tables.  All steps run in the SAME transaction
-- (psql autocommit-off via apply-migrations.sh hereDoc) — rollback-safe.
--
-- RLS rationale: This file uses the migration-293 multi-table JOIN pattern
-- (organization_members + user_roles + roles WHERE r.slug IN (...)) — NOT the
-- migration-304 single-line JWT-claim pattern. Reason: Phase B certificates
-- are a primary entity with role-based mutation rights (REQ-1 AC#6), not a
-- write-only audit log. Future migrations should NOT copy 304's JWT-claim
-- shortcut for similar entities.
--
-- Backfill rationale: customs_quote_expenses (per-quote расход) → 1 cert + N
-- attachments по всем позициям квоты (расход на КП распределяется на ВСЕ
-- позиции). customs_item_expenses (per-item расход) → group by (quote_id,
-- label) → 1 cert + multi-attach (одна label на нескольких позициях одной
-- квоты = один сертификат с несколькими привязками). Старые таблицы НЕ
-- дропаются (REQ-1 AC#8) — drop отложен до отдельной миграции после
-- production-верификации.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- CHECK constraint guarded via pg_constraint lookup, DROP POLICY IF EXISTS
-- + CREATE POLICY, backfill guarded WHERE NOT EXISTS.

SET search_path TO kvota;

BEGIN;

-- =============================================================================
-- Part 1: Schema — kvota.quote_certificates
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.quote_certificates (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id          UUID         NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    type              TEXT         NOT NULL,
    number            TEXT,
    issuer            TEXT,
    legal_doc         TEXT,
    issued_at         DATE,
    valid_until       DATE,
    cost_rub          NUMERIC(14, 2) NOT NULL DEFAULT 0,
    notes             TEXT,
    display_name      TEXT,                                 -- only for is_custom_expense=TRUE
    is_custom_expense BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_by        UUID         REFERENCES auth.users(id)
);

COMMENT ON TABLE kvota.quote_certificates IS
    'Phase B: shared compliance certificates (ДС ТР ТС, СС, СГР, ОТТС, EUR.1) '
    'and custom customs expenses (is_custom_expense=TRUE + display_name). '
    'Cost is proportionally distributed across attached quote_items via '
    'services/cost_split.py + frontend/src/shared/lib/cost-split.ts.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quote_certificates_cost_rub_nonneg'
    ) THEN
        ALTER TABLE kvota.quote_certificates
            ADD CONSTRAINT quote_certificates_cost_rub_nonneg CHECK (cost_rub >= 0);
    END IF;
END $$;

-- =============================================================================
-- Part 2: Schema — kvota.quote_certificate_items (M2M)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.quote_certificate_items (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    certificate_id UUID        NOT NULL REFERENCES kvota.quote_certificates(id) ON DELETE CASCADE,
    item_id        UUID        NOT NULL REFERENCES kvota.quote_items(id)        ON DELETE CASCADE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (certificate_id, item_id)
);

COMMENT ON TABLE kvota.quote_certificate_items IS
    'Phase B: M2M attachments — which quote_items each certificate covers. '
    'UNIQUE (certificate_id, item_id) prevents duplicate bindings.';

-- =============================================================================
-- Part 3: Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_quote_certificates_quote_id
    ON kvota.quote_certificates(quote_id);

CREATE INDEX IF NOT EXISTS idx_quote_certificate_items_cert
    ON kvota.quote_certificate_items(certificate_id);

CREATE INDEX IF NOT EXISTS idx_quote_certificate_items_item
    ON kvota.quote_certificate_items(item_id);

-- =============================================================================
-- Part 4: Row-level security — 293 pattern (organization_members + user_roles + roles)
-- =============================================================================

ALTER TABLE kvota.quote_certificates       ENABLE ROW LEVEL SECURITY;
ALTER TABLE kvota.quote_certificate_items  ENABLE ROW LEVEL SECURITY;

-- ----- quote_certificates: SELECT (extended read-role list) -------------------
DROP POLICY IF EXISTS quote_certificates_org_select ON kvota.quote_certificates;
CREATE POLICY quote_certificates_org_select
    ON kvota.quote_certificates
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE q.id = quote_certificates.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN (
                  'customs', 'admin', 'head_of_customs',
                  'sales', 'quote_controller', 'spec_controller',
                  'finance', 'top_manager'
              )
        )
    );

-- ----- quote_certificates: INSERT/UPDATE/DELETE (write-role list) -------------
DROP POLICY IF EXISTS quote_certificates_org_mutate ON kvota.quote_certificates;
CREATE POLICY quote_certificates_org_mutate
    ON kvota.quote_certificates
    FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE q.id = quote_certificates.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN ('customs', 'admin', 'head_of_customs')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE q.id = quote_certificates.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN ('customs', 'admin', 'head_of_customs')
        )
    );

-- ----- quote_certificate_items: SELECT (read via cert → quote) ----------------
DROP POLICY IF EXISTS quote_certificate_items_org_select ON kvota.quote_certificate_items;
CREATE POLICY quote_certificate_items_org_select
    ON kvota.quote_certificate_items
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quote_certificates qc
            JOIN kvota.quotes q                 ON q.id = qc.quote_id
            JOIN kvota.organization_members om  ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE qc.id = quote_certificate_items.certificate_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN (
                  'customs', 'admin', 'head_of_customs',
                  'sales', 'quote_controller', 'spec_controller',
                  'finance', 'top_manager'
              )
        )
    );

-- ----- quote_certificate_items: INSERT/UPDATE/DELETE (write via cert → quote)
DROP POLICY IF EXISTS quote_certificate_items_org_mutate ON kvota.quote_certificate_items;
CREATE POLICY quote_certificate_items_org_mutate
    ON kvota.quote_certificate_items
    FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quote_certificates qc
            JOIN kvota.quotes q                 ON q.id = qc.quote_id
            JOIN kvota.organization_members om  ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE qc.id = quote_certificate_items.certificate_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN ('customs', 'admin', 'head_of_customs')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM kvota.quote_certificates qc
            JOIN kvota.quotes q                 ON q.id = qc.quote_id
            JOIN kvota.organization_members om  ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE qc.id = quote_certificate_items.certificate_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN ('customs', 'admin', 'head_of_customs')
        )
    );

-- =============================================================================
-- Part 5: Atomic backfill from legacy customs_*_expenses
--
-- Idempotency: backfill skipped entirely if any quote_certificates rows already
-- exist with is_custom_expense=TRUE — re-applying migration is a no-op.
-- (Migration is normally applied exactly once via apply-migrations.sh; this
--  guard protects against manual re-runs / partial failures.)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM kvota.quote_certificates WHERE is_custom_expense = TRUE
    ) THEN
        RAISE NOTICE 'Migration 306 backfill skipped — quote_certificates already populated';
        RETURN;
    END IF;

    -- Step 1: customs_quote_expenses → 1 cert + N attachments per quote_item.
    -- Per-quote расход распределяется на ВСЕ позиции квоты (REQ-1 AC#7 first bullet).
    WITH ins AS (
        INSERT INTO kvota.quote_certificates
            (quote_id, type, display_name, cost_rub, notes,
             is_custom_expense, created_by, created_at)
        SELECT cqe.quote_id,
               'custom_expense',
               cqe.label,
               cqe.amount_rub,
               cqe.notes,
               TRUE,
               cqe.created_by,
               cqe.created_at
        FROM kvota.customs_quote_expenses cqe
        RETURNING id, quote_id
    )
    INSERT INTO kvota.quote_certificate_items (certificate_id, item_id)
    SELECT ins.id, qi.id
    FROM ins
    JOIN kvota.quote_items qi ON qi.quote_id = ins.quote_id;

    -- Step 2: customs_item_expenses → multi-attach grouping by (quote_id, label).
    -- Same label across multiple items in same quote = ONE cert + N attachments
    -- (REQ-1 AC#7 second bullet — multi-attach rule).
    -- Note: PostgreSQL has no MIN(uuid)/MIN(text) for some types — pick the first
    -- non-null value via (array_agg(...) FILTER (...))[1].
    WITH grouped AS (
        SELECT qi.quote_id,
               cie.label,
               AVG(cie.amount_rub)::NUMERIC(14, 2) AS amount_rub,
               (ARRAY_AGG(cie.notes)      FILTER (WHERE cie.notes IS NOT NULL))[1]      AS notes,
               (ARRAY_AGG(cie.created_by) FILTER (WHERE cie.created_by IS NOT NULL))[1] AS created_by,
               MIN(cie.created_at) AS created_at,
               ARRAY_AGG(cie.quote_item_id) AS item_ids
        FROM kvota.customs_item_expenses cie
        JOIN kvota.quote_items qi ON qi.id = cie.quote_item_id
        GROUP BY qi.quote_id, cie.label
    ),
    ins AS (
        INSERT INTO kvota.quote_certificates
            (quote_id, type, display_name, cost_rub, notes,
             is_custom_expense, created_by, created_at)
        SELECT g.quote_id,
               'custom_expense',
               g.label,
               g.amount_rub,
               g.notes,
               TRUE,
               g.created_by,
               g.created_at
        FROM grouped g
        RETURNING id, quote_id, display_name
    )
    INSERT INTO kvota.quote_certificate_items (certificate_id, item_id)
    SELECT ins.id, UNNEST(g.item_ids)
    FROM ins
    JOIN grouped g
      ON g.quote_id = ins.quote_id
     AND g.label    = ins.display_name;
END $$;

-- =============================================================================
-- NOTE: customs_item_expenses + customs_quote_expenses tables NOT dropped here
-- (REQ-1 AC#8). Drop migration deferred to a separate release after production
-- verification. Source rows remain intact = rollback-safe.
-- =============================================================================

COMMIT;
