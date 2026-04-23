-- Migration 500: Customer Journey Map — 6 annotation tables + helper + history trigger
-- Date: 2026-04-22
-- Spec: .kiro/specs/customer-journey-map/design.md §3, §4.3
-- Reqs: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 11.1, 18.1
--
-- Scope of this migration (Task 1):
--   - 6 tables in kvota schema backing every mutable journey annotation
--   - kvota.user_has_role(slug text) helper (create only if absent)
--   - AFTER UPDATE trigger that copies journey_node_state → ..._history
--   - ADD COLUMN kvota.user_feedback.node_id + index
--   - ENABLE RLS on all 6 tables (POLICIES come in Task 3)
--
-- NOTES:
--   * The spec text says "kvota.feedback" but the actual feedback table in
--     this codebase is kvota.user_feedback (migration 144). We target that.
--   * kvota.user_has_role(p_slug text) already exists (defined pre-journey),
--     so we add it only if missing to avoid breaking other RLS policies.
--   * Every CREATE uses IF NOT EXISTS so the migration is idempotent for
--     environments where these objects were provisioned out-of-band.

SET search_path TO kvota, public;

-- ---------------------------------------------------------------------------
-- Table 1 — journey_node_state: one row per real or ghost node.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kvota.journey_node_state (
    node_id         text PRIMARY KEY,
    impl_status     text CHECK (impl_status IN ('done', 'partial', 'missing')),
    qa_status       text CHECK (qa_status   IN ('verified', 'broken', 'untested')),
    notes           text,
    version         integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    last_tested_at  timestamptz,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    updated_by      uuid REFERENCES auth.users(id)
);

CREATE INDEX IF NOT EXISTS idx_journey_node_state_updated_by
    ON kvota.journey_node_state(updated_by);

COMMENT ON TABLE  kvota.journey_node_state IS 'Mutable impl/qa status per journey node. Writes go through Python API only (RLS denies direct INSERT/UPDATE).';
COMMENT ON COLUMN kvota.journey_node_state.version IS 'Optimistic concurrency guard; Python API PATCH enforces If-Match semantics.';

-- ---------------------------------------------------------------------------
-- Table 2 — journey_node_state_history: append-only audit log.
-- AFTER UPDATE trigger on journey_node_state copies OLD row here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kvota.journey_node_state_history (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id      text NOT NULL,
    impl_status  text,
    qa_status    text,
    notes        text,
    version      integer NOT NULL,
    changed_by   uuid REFERENCES auth.users(id),
    changed_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_journey_node_state_history_node_id_changed_at
    ON kvota.journey_node_state_history(node_id, changed_at DESC);

COMMENT ON TABLE kvota.journey_node_state_history IS 'Append-only audit of journey_node_state changes. Populated by trg_journey_node_state_history trigger.';

-- ---------------------------------------------------------------------------
-- Table 3 — journey_ghost_nodes: proposed routes not yet in code.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kvota.journey_ghost_nodes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         text UNIQUE NOT NULL CHECK (node_id LIKE 'ghost:%'),
    proposed_route  text,
    title           text NOT NULL,
    planned_in      text,
    assignee        uuid REFERENCES auth.users(id),
    parent_node_id  text,
    cluster         text,
    status          text NOT NULL DEFAULT 'proposed'
                         CHECK (status IN ('proposed', 'approved', 'in_progress', 'shipped')),
    created_by      uuid REFERENCES auth.users(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_journey_ghost_nodes_status
    ON kvota.journey_ghost_nodes(status);
CREATE INDEX IF NOT EXISTS idx_journey_ghost_nodes_cluster
    ON kvota.journey_ghost_nodes(cluster);
CREATE INDEX IF NOT EXISTS idx_journey_ghost_nodes_assignee
    ON kvota.journey_ghost_nodes(assignee);

-- ---------------------------------------------------------------------------
-- Table 4 — journey_pins: dual-mode (qa / training) annotations.
-- Relative coordinates (0.0–1.0) refreshed nightly by Playwright webhook.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kvota.journey_pins (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id               text NOT NULL,
    selector              text NOT NULL,
    expected_behavior     text NOT NULL,
    mode                  text NOT NULL CHECK (mode IN ('qa', 'training')),
    training_step_order   integer,
    linked_story_ref      text,
    -- Relative position cache (fractions of screenshot dimensions).
    last_rel_x            numeric(6, 4) CHECK (last_rel_x      IS NULL OR (last_rel_x      >= 0 AND last_rel_x      <= 1)),
    last_rel_y            numeric(6, 4) CHECK (last_rel_y      IS NULL OR (last_rel_y      >= 0 AND last_rel_y      <= 1)),
    last_rel_width        numeric(6, 4) CHECK (last_rel_width  IS NULL OR (last_rel_width  >= 0 AND last_rel_width  <= 1)),
    last_rel_height       numeric(6, 4) CHECK (last_rel_height IS NULL OR (last_rel_height >= 0 AND last_rel_height <= 1)),
    last_position_update  timestamptz,
    selector_broken       boolean NOT NULL DEFAULT false,
    created_by            uuid REFERENCES auth.users(id),
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_journey_pins_node_id
    ON kvota.journey_pins(node_id);
CREATE INDEX IF NOT EXISTS idx_journey_pins_mode
    ON kvota.journey_pins(mode);
CREATE INDEX IF NOT EXISTS idx_journey_pins_selector_broken
    ON kvota.journey_pins(selector_broken)
    WHERE selector_broken = true;
CREATE INDEX IF NOT EXISTS idx_journey_pins_created_by
    ON kvota.journey_pins(created_by);

COMMENT ON COLUMN kvota.journey_pins.last_rel_x IS 'Relative x position (0.0–1.0 fraction of screenshot width). Survives viewport/DPR changes.';

-- ---------------------------------------------------------------------------
-- Table 5 — journey_verifications: append-only QA events.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kvota.journey_verifications (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pin_id           uuid NOT NULL REFERENCES kvota.journey_pins(id) ON DELETE CASCADE,
    node_id          text NOT NULL,              -- denormalised for read-path
    result           text NOT NULL CHECK (result IN ('verified', 'broken', 'skip')),
    note             text,
    attachment_urls  text[],                     -- Supabase Storage object keys
    tested_by        uuid REFERENCES auth.users(id),
    tested_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_journey_verifications_node_id_tested_at
    ON kvota.journey_verifications(node_id, tested_at DESC);
CREATE INDEX IF NOT EXISTS idx_journey_verifications_pin_id_tested_at
    ON kvota.journey_verifications(pin_id, tested_at DESC);
CREATE INDEX IF NOT EXISTS idx_journey_verifications_tested_by
    ON kvota.journey_verifications(tested_by);

COMMENT ON TABLE kvota.journey_verifications IS 'Append-only QA verification events. RLS will deny UPDATE and DELETE for every role (Task 3).';

-- ---------------------------------------------------------------------------
-- Table 6 — journey_flows: curated persona walkthroughs (Req 18).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kvota.journey_flows (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           text UNIQUE NOT NULL,
    title          text NOT NULL,
    role           text NOT NULL,             -- RoleSlug (not FK: roles table stores many legacy rows)
    persona        text NOT NULL,
    description    text,
    est_minutes    integer,
    steps          jsonb NOT NULL DEFAULT '[]'::jsonb,
    is_archived    boolean NOT NULL DEFAULT false,
    display_order  integer NOT NULL DEFAULT 0,
    created_by     uuid REFERENCES auth.users(id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_journey_flows_role
    ON kvota.journey_flows(role);
CREATE INDEX IF NOT EXISTS idx_journey_flows_is_archived
    ON kvota.journey_flows(is_archived);
CREATE INDEX IF NOT EXISTS idx_journey_flows_display_order
    ON kvota.journey_flows(display_order);

-- ---------------------------------------------------------------------------
-- Feedback integration: link feedback rows to a journey node.
-- (Spec §4.3 says kvota.feedback; actual table is kvota.user_feedback.)
-- ---------------------------------------------------------------------------
ALTER TABLE kvota.user_feedback
    ADD COLUMN IF NOT EXISTS node_id text;

CREATE INDEX IF NOT EXISTS idx_user_feedback_node_id
    ON kvota.user_feedback(node_id);

-- ---------------------------------------------------------------------------
-- Helper: kvota.user_has_role(slug) — created only if absent.
-- A function with this signature was introduced by earlier migrations; we
-- define it here only as a safety net for fresh environments.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'kvota'
          AND p.proname = 'user_has_role'
          AND pg_get_function_arguments(p.oid) = 'p_slug text'
    ) THEN
        EXECUTE $fn$
            CREATE FUNCTION kvota.user_has_role(p_slug text)
            RETURNS boolean
            LANGUAGE sql
            STABLE
            SECURITY DEFINER
            SET search_path TO 'kvota', 'public'
            AS $body$
                SELECT EXISTS (
                    SELECT 1
                    FROM kvota.user_roles ur
                    JOIN kvota.roles r ON r.id = ur.role_id
                    WHERE ur.user_id = auth.uid()
                      AND r.slug = p_slug
                );
            $body$;
        $fn$;
        EXECUTE 'GRANT EXECUTE ON FUNCTION kvota.user_has_role(text) TO authenticated';
    END IF;
END$$;

-- ---------------------------------------------------------------------------
-- Trigger: copy journey_node_state BEFORE-image into history on UPDATE.
-- SECURITY DEFINER so the insert succeeds regardless of caller RLS.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION kvota.copy_journey_node_state_to_history()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'kvota', 'public'
AS $$
BEGIN
    INSERT INTO kvota.journey_node_state_history
        (node_id, impl_status, qa_status, notes, version, changed_by, changed_at)
    VALUES
        (OLD.node_id, OLD.impl_status, OLD.qa_status, OLD.notes,
         OLD.version, OLD.updated_by, OLD.updated_at);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_journey_node_state_history ON kvota.journey_node_state;
CREATE TRIGGER trg_journey_node_state_history
    AFTER UPDATE ON kvota.journey_node_state
    FOR EACH ROW
    EXECUTE FUNCTION kvota.copy_journey_node_state_to_history();

-- ---------------------------------------------------------------------------
-- RLS — enable on all 6 tables. Policies are defined in Task 3.
-- With RLS enabled and no policies, authenticated clients see nothing; this
-- is intentional until Task 3 lands. The Python API uses the service role
-- (bypasses RLS) so server-side flows continue to work.
-- ---------------------------------------------------------------------------
ALTER TABLE kvota.journey_node_state          ENABLE ROW LEVEL SECURITY;
ALTER TABLE kvota.journey_node_state_history  ENABLE ROW LEVEL SECURITY;
ALTER TABLE kvota.journey_ghost_nodes         ENABLE ROW LEVEL SECURITY;
ALTER TABLE kvota.journey_pins                ENABLE ROW LEVEL SECURITY;
ALTER TABLE kvota.journey_verifications       ENABLE ROW LEVEL SECURITY;
ALTER TABLE kvota.journey_flows               ENABLE ROW LEVEL SECURITY;
