-- Migration 281: kvota.hard_purge_quote(uuid) — transactional cascade hard-delete
--
-- Purpose: the retention cron (scripts/purge_old_deleted_quotes.py) previously
-- issued three separate DELETE statements via PostgREST for each expired quote
-- (deals → specs → quote). If the network dropped between them, the DB ended
-- up in a partial-purge state until the next cron run. This migration wraps
-- the three deletes in a single PL/pgSQL function so every purge is one atomic
-- transaction — all three rows gone or none.
--
-- The order (deals → specs → quote) is required because both deals.quote_id
-- and deals.specification_id are RESTRICT FKs. Keying all three deletes on
-- quote_id covers every deal that belongs to the quote, regardless of whether
-- a spec intermediates it.
--
-- Downstream tables (quote_items, plan_fact_items, logistics_stages,
-- currency_invoices, deal_logistics_expenses, etc.) are cleaned up by existing
-- FK CASCADEs from the three parent deletes.
--
-- Callable by the service_role key only (the purge cron runs with that key).
-- Authenticated users do not get EXECUTE — admins delete via the soft-delete
-- function; hard-purge is operational, not user-facing.

BEGIN;

CREATE OR REPLACE FUNCTION kvota.hard_purge_quote(p_quote_id uuid)
RETURNS TABLE(deals_deleted int, specs_deleted int, quotes_deleted int)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = kvota, public
AS $$
DECLARE
  v_deals int := 0;
  v_specs int := 0;
  v_quote int := 0;
BEGIN
  -- Order matters: deals first (both FK deals.quote_id and
  -- deals.specification_id are RESTRICT), then specs, then the quote.
  WITH deleted AS (
    DELETE FROM kvota.deals WHERE quote_id = p_quote_id RETURNING id
  )
  SELECT count(*)::int INTO v_deals FROM deleted;

  WITH deleted AS (
    DELETE FROM kvota.specifications WHERE quote_id = p_quote_id RETURNING id
  )
  SELECT count(*)::int INTO v_specs FROM deleted;

  WITH deleted AS (
    DELETE FROM kvota.quotes WHERE id = p_quote_id RETURNING id
  )
  SELECT count(*)::int INTO v_quote FROM deleted;

  RETURN QUERY SELECT v_deals, v_specs, v_quote;
END;
$$;

COMMENT ON FUNCTION kvota.hard_purge_quote(uuid) IS
  'Atomically hard-delete a quote and its spec/deal subtree. Intended for the '
  '365-day retention cron. Returns per-level deleted row counts. Downstream '
  'children (quote_items, plan_fact_items, logistics_stages, currency_invoices, '
  'etc.) are cleaned up by existing FK CASCADEs from the 3 parent deletes.';

-- service_role only — cron runs with service key. Authenticated users must not
-- be able to bypass soft-delete and directly hard-purge.
REVOKE ALL ON FUNCTION kvota.hard_purge_quote(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION kvota.hard_purge_quote(uuid) FROM authenticated;
GRANT EXECUTE ON FUNCTION kvota.hard_purge_quote(uuid) TO service_role;

COMMIT;
