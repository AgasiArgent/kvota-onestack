-- Migration 280: active_* views + RLS defense-in-depth for soft-delete
-- Created: 2026-04-15
--
-- Part 3 of the soft-delete standardization initiative. Migration 279 added
-- deleted_at to kvota.quotes / specifications / deals. Migration 280:
--   1. Exposes three convenience views (active_quotes, active_specs,
--      active_deals) that filter deleted_at IS NULL for free.
--   2. Layers an additive SELECT RLS policy on each of the three tables that
--      hides soft-deleted rows from non-admin readers — defense-in-depth so
--      even a reader that forgets to add WHERE deleted_at IS NULL cannot leak
--      deleted rows across the role boundary. Admin bypass is explicit so the
--      forthcoming /quotes/trash page (subtask 5) can still enumerate them.
--
-- security_invoker=true on the views means the caller's RLS policies apply,
-- not the view-owner's — critical so existing org-scoped SELECT policies keep
-- working and the new hide-deleted policy is composed onto every read path.
--
-- REQ-005 in .kiro/specs/soft-delete-entity-lifecycle/requirements.md.

BEGIN;

-- ──────────────────────────────────────────────────────────────────────
-- Views
-- ──────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW kvota.active_quotes
  WITH (security_invoker = true) AS
  SELECT * FROM kvota.quotes WHERE deleted_at IS NULL;

CREATE OR REPLACE VIEW kvota.active_specs
  WITH (security_invoker = true) AS
  SELECT * FROM kvota.specifications WHERE deleted_at IS NULL;

CREATE OR REPLACE VIEW kvota.active_deals
  WITH (security_invoker = true) AS
  SELECT * FROM kvota.deals WHERE deleted_at IS NULL;

COMMENT ON VIEW kvota.active_quotes IS
  'Soft-delete-filtered view. Use this instead of kvota.quotes for NEW readers '
  'that never want soft-deleted rows. Existing direct reads must still add '
  '".is_(''deleted_at'', None)" until the read-audit converts them. '
  'security_invoker=true — caller RLS applies.';
COMMENT ON VIEW kvota.active_specs IS 'Same contract as active_quotes.';
COMMENT ON VIEW kvota.active_deals IS 'Same contract as active_quotes.';

GRANT SELECT ON kvota.active_quotes TO authenticated, service_role;
GRANT SELECT ON kvota.active_specs  TO authenticated, service_role;
GRANT SELECT ON kvota.active_deals  TO authenticated, service_role;

-- ──────────────────────────────────────────────────────────────────────
-- RLS defense-in-depth
-- ──────────────────────────────────────────────────────────────────────
-- Strategy: add a PERMISSIVE SELECT policy that adds an OR-branch —
-- "deleted_at IS NULL OR caller is admin". Because PERMISSIVE policies on
-- the same command are OR-combined, we can't just ADD "deleted_at IS NULL"
-- (that would widen, not narrow, access). Instead we need this to be a
-- RESTRICTIVE policy so it AND-combines with the existing org-scoping
-- policy: row is visible iff (it's in my org) AND (not deleted OR I'm admin).

DROP POLICY IF EXISTS quotes_hide_deleted_from_non_admin ON kvota.quotes;
CREATE POLICY quotes_hide_deleted_from_non_admin
  ON kvota.quotes
  AS RESTRICTIVE
  FOR SELECT
  TO authenticated
  USING (
    deleted_at IS NULL
    OR EXISTS (
      SELECT 1
        FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
       WHERE ur.user_id = auth.uid()
         AND r.slug = 'admin'
    )
  );

DROP POLICY IF EXISTS specs_hide_deleted_from_non_admin ON kvota.specifications;
CREATE POLICY specs_hide_deleted_from_non_admin
  ON kvota.specifications
  AS RESTRICTIVE
  FOR SELECT
  TO authenticated
  USING (
    deleted_at IS NULL
    OR EXISTS (
      SELECT 1
        FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
       WHERE ur.user_id = auth.uid()
         AND r.slug = 'admin'
    )
  );

DROP POLICY IF EXISTS deals_hide_deleted_from_non_admin ON kvota.deals;
CREATE POLICY deals_hide_deleted_from_non_admin
  ON kvota.deals
  AS RESTRICTIVE
  FOR SELECT
  TO authenticated
  USING (
    deleted_at IS NULL
    OR EXISTS (
      SELECT 1
        FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
       WHERE ur.user_id = auth.uid()
         AND r.slug = 'admin'
    )
  );

COMMENT ON POLICY quotes_hide_deleted_from_non_admin ON kvota.quotes IS
  'RESTRICTIVE: soft-deleted rows are hidden from everyone except admin. '
  'AND-composed with existing org-scoping policies. service_role bypasses RLS '
  'by default (Postgres built-in) — Python backend using service_role still '
  'sees soft-deleted rows, application code is responsible for filtering there.';
COMMENT ON POLICY specs_hide_deleted_from_non_admin ON kvota.specifications IS
  'Same contract as quotes_hide_deleted_from_non_admin.';
COMMENT ON POLICY deals_hide_deleted_from_non_admin ON kvota.deals IS
  'Same contract as quotes_hide_deleted_from_non_admin.';

COMMIT;
