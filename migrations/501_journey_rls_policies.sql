-- Migration 501: RLS policies for the 6 Customer Journey Map annotation tables.
-- Date: 2026-04-22
-- Spec: .kiro/specs/customer-journey-map/requirements.md Req 12, design.md §4.3/§6
-- Reqs: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9
--
-- Scope (Task 3, follow-up to migration 500):
--   - SELECT allowed to all authenticated users on every journey_* table.
--   - Writes per the matrix below. `top_manager` explicitly gets NO write
--     policy anywhere (read-only per access-control.md).
--   - journey_node_state: NO client INSERT/UPDATE/DELETE — writes only via
--     Python API running as service_role (which bypasses RLS).
--   - journey_node_state_history: SELECT only; INSERTs happen via the
--     SECURITY DEFINER trigger from migration 500.
--   - journey_verifications: INSERT for admin / quote_controller /
--     spec_controller; UPDATE and DELETE denied for everyone (append-only).
--   - journey_ghost_nodes: INSERT/UPDATE/DELETE for admin only.
--   - journey_pins: INSERT/UPDATE/DELETE for admin / quote_controller /
--     spec_controller.
--   - journey_flows: INSERT/UPDATE/DELETE for admin only (Req 18.2).
--
-- MATRIX (C = allowed, x = denied)
--   role              | n_state | n_hist | ghost | pins | verif | flows
--   ------------------+---------+--------+-------+------+-------+------
--   admin             |  S      |  S     |  CUD  | CUD  |  C    |  CUD
--   quote_controller  |  S      |  S     |  S    | CUD  |  C    |  S
--   spec_controller   |  S      |  S     |  S    | CUD  |  C    |  S
--   sales/proc/log/
--   customs/finance   |  S      |  S     |  S    |  S   |  S    |  S
--   top_manager       |  S      |  S     |  S    |  S   |  S    |  S  (explicitly read-only)
--
-- Notes:
--   * Policies use kvota.user_has_role('slug') which was created in migration 500.
--   * All statements are idempotent via DROP POLICY IF EXISTS + CREATE POLICY.
--   * RLS is already ENABLED on all six tables (migration 500); we only add policies.

SET search_path TO kvota, public;

-- ───────────────────────────────────────────────────────────────────────────
-- Table 1 — journey_node_state
-- SELECT: authenticated.  INSERT/UPDATE/DELETE: none (service_role only).
-- Per Req 12.4: "deny all client-direct INSERT / UPDATE / DELETE".
-- ───────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS journey_node_state_select ON kvota.journey_node_state;
CREATE POLICY journey_node_state_select
    ON kvota.journey_node_state
    FOR SELECT
    TO authenticated
    USING (true);

-- No INSERT/UPDATE/DELETE policies are defined intentionally.
-- With RLS enabled and no matching policy, those operations are rejected
-- for every non-bypassing role, including admin. Python API uses service_role.

-- ───────────────────────────────────────────────────────────────────────────
-- Table 2 — journey_node_state_history
-- SELECT: authenticated.  INSERT only via SECURITY DEFINER trigger
-- (migration 500); UPDATE/DELETE denied for every role (Req 12.8).
-- ───────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS journey_node_state_history_select ON kvota.journey_node_state_history;
CREATE POLICY journey_node_state_history_select
    ON kvota.journey_node_state_history
    FOR SELECT
    TO authenticated
    USING (true);

-- No INSERT policy: the SECURITY DEFINER trigger bypasses RLS when copying
-- BEFORE-images from journey_node_state, so client direct INSERT is denied.
-- No UPDATE / DELETE policies: append-only.

-- ───────────────────────────────────────────────────────────────────────────
-- Table 3 — journey_ghost_nodes
-- SELECT: authenticated.  INSERT/UPDATE/DELETE: admin only (Req 12.5).
-- top_manager explicitly NOT granted — Req 12.5 calls this out.
-- ───────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS journey_ghost_nodes_select ON kvota.journey_ghost_nodes;
CREATE POLICY journey_ghost_nodes_select
    ON kvota.journey_ghost_nodes
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS journey_ghost_nodes_insert_admin ON kvota.journey_ghost_nodes;
CREATE POLICY journey_ghost_nodes_insert_admin
    ON kvota.journey_ghost_nodes
    FOR INSERT
    TO authenticated
    WITH CHECK (kvota.user_has_role('admin'));

DROP POLICY IF EXISTS journey_ghost_nodes_update_admin ON kvota.journey_ghost_nodes;
CREATE POLICY journey_ghost_nodes_update_admin
    ON kvota.journey_ghost_nodes
    FOR UPDATE
    TO authenticated
    USING (kvota.user_has_role('admin'))
    WITH CHECK (kvota.user_has_role('admin'));

DROP POLICY IF EXISTS journey_ghost_nodes_delete_admin ON kvota.journey_ghost_nodes;
CREATE POLICY journey_ghost_nodes_delete_admin
    ON kvota.journey_ghost_nodes
    FOR DELETE
    TO authenticated
    USING (kvota.user_has_role('admin'));

-- ───────────────────────────────────────────────────────────────────────────
-- Table 4 — journey_pins
-- SELECT: authenticated.  INSERT/UPDATE/DELETE: admin, quote_controller,
-- spec_controller (Req 12.6).
-- ───────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS journey_pins_select ON kvota.journey_pins;
CREATE POLICY journey_pins_select
    ON kvota.journey_pins
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS journey_pins_insert_qa ON kvota.journey_pins;
CREATE POLICY journey_pins_insert_qa
    ON kvota.journey_pins
    FOR INSERT
    TO authenticated
    WITH CHECK (
        kvota.user_has_role('admin')
        OR kvota.user_has_role('quote_controller')
        OR kvota.user_has_role('spec_controller')
    );

DROP POLICY IF EXISTS journey_pins_update_qa ON kvota.journey_pins;
CREATE POLICY journey_pins_update_qa
    ON kvota.journey_pins
    FOR UPDATE
    TO authenticated
    USING (
        kvota.user_has_role('admin')
        OR kvota.user_has_role('quote_controller')
        OR kvota.user_has_role('spec_controller')
    )
    WITH CHECK (
        kvota.user_has_role('admin')
        OR kvota.user_has_role('quote_controller')
        OR kvota.user_has_role('spec_controller')
    );

DROP POLICY IF EXISTS journey_pins_delete_qa ON kvota.journey_pins;
CREATE POLICY journey_pins_delete_qa
    ON kvota.journey_pins
    FOR DELETE
    TO authenticated
    USING (
        kvota.user_has_role('admin')
        OR kvota.user_has_role('quote_controller')
        OR kvota.user_has_role('spec_controller')
    );

-- ───────────────────────────────────────────────────────────────────────────
-- Table 5 — journey_verifications
-- SELECT: authenticated.  INSERT: admin/quote_controller/spec_controller.
-- UPDATE/DELETE: denied for everyone (append-only per Req 12.7).
-- ───────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS journey_verifications_select ON kvota.journey_verifications;
CREATE POLICY journey_verifications_select
    ON kvota.journey_verifications
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS journey_verifications_insert_qa ON kvota.journey_verifications;
CREATE POLICY journey_verifications_insert_qa
    ON kvota.journey_verifications
    FOR INSERT
    TO authenticated
    WITH CHECK (
        kvota.user_has_role('admin')
        OR kvota.user_has_role('quote_controller')
        OR kvota.user_has_role('spec_controller')
    );

-- No UPDATE / DELETE policies: append-only, denied for every role.

-- ───────────────────────────────────────────────────────────────────────────
-- Table 6 — journey_flows
-- SELECT: authenticated.  INSERT/UPDATE/DELETE: admin only (Req 18.2).
-- ───────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS journey_flows_select ON kvota.journey_flows;
CREATE POLICY journey_flows_select
    ON kvota.journey_flows
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS journey_flows_insert_admin ON kvota.journey_flows;
CREATE POLICY journey_flows_insert_admin
    ON kvota.journey_flows
    FOR INSERT
    TO authenticated
    WITH CHECK (kvota.user_has_role('admin'));

DROP POLICY IF EXISTS journey_flows_update_admin ON kvota.journey_flows;
CREATE POLICY journey_flows_update_admin
    ON kvota.journey_flows
    FOR UPDATE
    TO authenticated
    USING (kvota.user_has_role('admin'))
    WITH CHECK (kvota.user_has_role('admin'));

DROP POLICY IF EXISTS journey_flows_delete_admin ON kvota.journey_flows;
CREATE POLICY journey_flows_delete_admin
    ON kvota.journey_flows
    FOR DELETE
    TO authenticated
    USING (kvota.user_has_role('admin'));

-- ───────────────────────────────────────────────────────────────────────────
-- GRANTs — authenticated role must have base table privileges for RLS to let
-- matching policies through.  Without GRANT SELECT, RLS never gets consulted
-- and the operation is denied at the permission layer.
-- ───────────────────────────────────────────────────────────────────────────
GRANT SELECT                          ON kvota.journey_node_state         TO authenticated;
GRANT SELECT                          ON kvota.journey_node_state_history TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE  ON kvota.journey_ghost_nodes        TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE  ON kvota.journey_pins               TO authenticated;
GRANT SELECT, INSERT                  ON kvota.journey_verifications      TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE  ON kvota.journey_flows              TO authenticated;
