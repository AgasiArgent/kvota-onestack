-- Migration 279: Cascade soft-delete for Quote → Spec → Deal entity lifecycle
--
-- Standardizes soft-delete across the three entities that represent one business
-- object at different stages (per CLAUDE.md: "Quote → Specification → Deal = same
-- business entity at different stages"). Before this migration, only kvota.quotes
-- had deleted_at; specs and deals supported hard delete only, and the FKs
-- deals→quotes and deals→specifications are RESTRICT, leaving orphaned rows when
-- a quote was soft-deleted.
--
-- Design choice (Option C): deleted_at lives on the 3 lifecycle tables only.
-- Children (quote_items, plan_fact_items, logistics_stages, currency_invoices,
-- etc.) are hidden transitively via parent filter. See
-- .kiro/specs/soft-delete-entity-lifecycle/design.md for rationale vs. A/B.
--
-- Introduces two atomic entry points:
--   - kvota.soft_delete_quote(quote_id, actor_id) → cascades to spec + deal
--   - kvota.restore_quote(quote_id)              → reverses the cascade
-- Both SECURITY DEFINER so they run with owner privileges; callers are
-- authenticated via the API layer (JWT → user_id passed as actor_id).
--
-- Retention: 365 days. A separate cron (scripts/purge_old_deleted_quotes.py)
-- hard-deletes older rows, relying on existing FK CASCADEs for downstream cleanup.

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- 1. Columns
-- ─────────────────────────────────────────────────────────────

ALTER TABLE kvota.specifications
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES auth.users(id);

ALTER TABLE kvota.deals
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES auth.users(id);

ALTER TABLE kvota.quotes
  ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES auth.users(id);

COMMENT ON COLUMN kvota.specifications.deleted_at IS
  'Soft-delete timestamp. NULL = active. Set atomically with quote via soft_delete_quote().';
COMMENT ON COLUMN kvota.specifications.deleted_by IS
  'User who triggered the soft-delete (auth.users.id).';
COMMENT ON COLUMN kvota.deals.deleted_at IS
  'Soft-delete timestamp. NULL = active. Set atomically with quote+spec via soft_delete_quote().';
COMMENT ON COLUMN kvota.deals.deleted_by IS
  'User who triggered the soft-delete (auth.users.id).';
COMMENT ON COLUMN kvota.quotes.deleted_by IS
  'User who triggered the soft-delete (auth.users.id). Column deleted_at pre-existed.';

-- ─────────────────────────────────────────────────────────────
-- 2. Partial indexes — 95%+ of queries filter deleted_at IS NULL;
--    partial indexes are ~3x smaller and are auto-selected by the planner.
-- ─────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_quotes_active_customer
  ON kvota.quotes(customer_id) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_quotes_active_created
  ON kvota.quotes(created_at DESC) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_specs_active_quote
  ON kvota.specifications(quote_id) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_deals_active_spec
  ON kvota.deals(specification_id) WHERE deleted_at IS NULL;

-- ─────────────────────────────────────────────────────────────
-- 3. Atomic cascade soft-delete
-- ─────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION kvota.soft_delete_quote(
  p_quote_id uuid,
  p_actor_id uuid
)
RETURNS TABLE(quote_affected int, spec_affected int, deal_affected int)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = kvota, public
AS $$
DECLARE
  v_now timestamptz := now();
  v_quote int := 0;
  v_spec  int := 0;
  v_deal  int := 0;
BEGIN
  -- Anti-spoof guard: when called from an authenticated user session (JS/direct
  -- rpc), auth.uid() is the caller's uid and must match p_actor_id — otherwise
  -- an attacker could record someone else as the deleter in the audit trail.
  -- When called from the Python backend via service_role, auth.uid() is NULL
  -- and the guard passes unconditionally (backend is trusted to pass a correct
  -- actor_id it derived from its own JWT validation).
  IF auth.uid() IS NOT NULL AND p_actor_id IS DISTINCT FROM auth.uid() THEN
    RAISE EXCEPTION 'actor mismatch: p_actor_id (%) must equal auth.uid() (%) for non-service-role callers',
      p_actor_id, auth.uid();
  END IF;

  -- Order: deal → spec → quote. The retention cron (subtask 6) MUST mirror this
  -- order when hard-deleting, because the FK deals.specification_id is RESTRICT
  -- (delete of specs/quotes blocks while active deal exists); existing CASCADEs
  -- downstream of deal (plan_fact_items, logistics_stages, etc.) clean up
  -- children automatically once the deal row is gone.
  WITH updated AS (
    UPDATE kvota.deals d
       SET deleted_at = v_now, deleted_by = p_actor_id
      FROM kvota.specifications s
     WHERE s.id = d.specification_id
       AND s.quote_id = p_quote_id
       AND d.deleted_at IS NULL
     RETURNING d.id
  )
  SELECT count(*)::int INTO v_deal FROM updated;

  WITH updated AS (
    UPDATE kvota.specifications
       SET deleted_at = v_now, deleted_by = p_actor_id
     WHERE quote_id = p_quote_id AND deleted_at IS NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_spec FROM updated;

  WITH updated AS (
    UPDATE kvota.quotes
       SET deleted_at = v_now, deleted_by = p_actor_id
     WHERE id = p_quote_id AND deleted_at IS NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_quote FROM updated;

  RETURN QUERY SELECT v_quote, v_spec, v_deal;
END;
$$;

COMMENT ON FUNCTION kvota.soft_delete_quote(uuid, uuid) IS
  'Atomically soft-delete a quote and its linked spec + deal. Idempotent '
  '(no-op on already-deleted rows). Returns per-level affected counts. '
  'SECURITY DEFINER: callers must pass their authenticated user_id as p_actor_id.';

-- ─────────────────────────────────────────────────────────────
-- 4. Atomic cascade restore
-- ─────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION kvota.restore_quote(p_quote_id uuid)
RETURNS TABLE(quote_affected int, spec_affected int, deal_affected int)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = kvota, public
AS $$
DECLARE
  v_quote int := 0;
  v_spec  int := 0;
  v_deal  int := 0;
BEGIN
  -- No actor guard here: restore has no audit column to spoof (we clear
  -- deleted_by to NULL). Authorization happens at the API layer (role check).
  -- Reverse order: quote → spec → deal. No FK concern here since all columns
  -- are being set back to NULL; order is stylistic (mirror of delete path).
  WITH updated AS (
    UPDATE kvota.quotes
       SET deleted_at = NULL, deleted_by = NULL
     WHERE id = p_quote_id AND deleted_at IS NOT NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_quote FROM updated;

  WITH updated AS (
    UPDATE kvota.specifications
       SET deleted_at = NULL, deleted_by = NULL
     WHERE quote_id = p_quote_id AND deleted_at IS NOT NULL
     RETURNING id
  )
  SELECT count(*)::int INTO v_spec FROM updated;

  WITH updated AS (
    UPDATE kvota.deals d
       SET deleted_at = NULL, deleted_by = NULL
      FROM kvota.specifications s
     WHERE s.id = d.specification_id
       AND s.quote_id = p_quote_id
       AND d.deleted_at IS NOT NULL
     RETURNING d.id
  )
  SELECT count(*)::int INTO v_deal FROM updated;

  RETURN QUERY SELECT v_quote, v_spec, v_deal;
END;
$$;

COMMENT ON FUNCTION kvota.restore_quote(uuid) IS
  'Reverse a prior soft-delete: clear deleted_at / deleted_by on quote, spec, deal. '
  'Idempotent. Does not restore rows older than retention window — hard-purged '
  'rows are gone for good.';

-- ─────────────────────────────────────────────────────────────
-- 5. Grants — authenticated role only; anon cannot invoke.
-- ─────────────────────────────────────────────────────────────

GRANT EXECUTE ON FUNCTION kvota.soft_delete_quote(uuid, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION kvota.restore_quote(uuid) TO authenticated;

COMMIT;
