-- Migration 327: procurement_pause_log activity table
-- Testing 2 row 74 — mandatory pause reason + activity log.
--
-- Each row records a single pause/unpause cycle. While `unpaused_at IS NULL`
-- the (quote_id, …) is the currently active pause for that quote. Unpause
-- closes the row by setting unpaused_at + unpaused_by; subsequent pauses
-- create new rows. Reason is required (non-empty CHECK).
--
-- RLS pattern follows migration 306 (multi-table JOIN via organization_members
-- + user_roles + roles WHERE r.slug IN (...)). Read + write open to ALL
-- procurement roles per the product decision (Q6 row 74).
--
-- Idempotent: CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- DROP POLICY IF EXISTS guards on policies.

BEGIN;

SET search_path TO kvota;

-- =============================================================================
-- Part 1: Schema
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.procurement_pause_log (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id      UUID         NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    paused_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    paused_by     UUID         NOT NULL REFERENCES auth.users(id),
    reason        TEXT         NOT NULL,
    unpaused_at   TIMESTAMPTZ,
    unpaused_by   UUID         REFERENCES auth.users(id),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE kvota.procurement_pause_log IS
    'Testing 2 row 74: mandatory pause reason + activity log for procurement '
    'kanban «На паузе» column. One row per pause/unpause cycle. While '
    'unpaused_at IS NULL the row is the currently active pause for that quote.';

-- Non-empty reason guard
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'procurement_pause_log_reason_nonempty'
    ) THEN
        ALTER TABLE kvota.procurement_pause_log
            ADD CONSTRAINT procurement_pause_log_reason_nonempty
            CHECK (length(reason) > 0);
    END IF;
END $$;

-- =============================================================================
-- Part 2: Indexes
-- =============================================================================

-- Newest-first lookup per quote — drives both the inline "latest reason"
-- card display and the full history drawer.
CREATE INDEX IF NOT EXISTS idx_procurement_pause_log_quote
    ON kvota.procurement_pause_log (quote_id, paused_at DESC);

-- Open-pause lookup: closing an unpause needs the latest row with
-- unpaused_at IS NULL. Partial index keeps it small.
CREATE INDEX IF NOT EXISTS idx_procurement_pause_log_open
    ON kvota.procurement_pause_log (quote_id, paused_at DESC)
    WHERE unpaused_at IS NULL;

-- =============================================================================
-- Part 3: Row-level security
-- =============================================================================

ALTER TABLE kvota.procurement_pause_log ENABLE ROW LEVEL SECURITY;

-- ----- SELECT: all procurement roles, scoped to the user's organization -----
DROP POLICY IF EXISTS procurement_pause_log_select ON kvota.procurement_pause_log;
CREATE POLICY procurement_pause_log_select
    ON kvota.procurement_pause_log
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE q.id = procurement_pause_log.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN (
                  'admin', 'procurement', 'procurement_senior', 'head_of_procurement'
              )
        )
    );

-- ----- INSERT/UPDATE: same role list (Q6 — ALL procurement) ------------------
DROP POLICY IF EXISTS procurement_pause_log_insert ON kvota.procurement_pause_log;
CREATE POLICY procurement_pause_log_insert
    ON kvota.procurement_pause_log
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE q.id = procurement_pause_log.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN (
                  'admin', 'procurement', 'procurement_senior', 'head_of_procurement'
              )
        )
    );

DROP POLICY IF EXISTS procurement_pause_log_update ON kvota.procurement_pause_log;
CREATE POLICY procurement_pause_log_update
    ON kvota.procurement_pause_log
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE q.id = procurement_pause_log.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN (
                  'admin', 'procurement', 'procurement_senior', 'head_of_procurement'
              )
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            JOIN kvota.user_roles ur            ON ur.user_id = om.user_id
            JOIN kvota.roles r                  ON r.id = ur.role_id
            WHERE q.id = procurement_pause_log.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
              AND r.slug IN (
                  'admin', 'procurement', 'procurement_senior', 'head_of_procurement'
              )
        )
    );

COMMIT;
