-- Migration 297: Backfill kvota.user_feedback.node_id for existing rows
-- Date: 2026-04-22
-- Spec:   .kiro/specs/customer-journey-map/requirements.md Req 11.1
-- Task:   30 (Feedback integration)
-- Depends on: migration 295 (adds kvota.user_feedback.node_id column + index).
--
-- Goal
-- ----
-- Populate node_id for rows that already have a usable page_url, using a
-- pattern-based mapping. This is the (a) half of Req 11.1; the (b) half
-- (new-feedback creation logic passing the current route) is implemented
-- in application code (api/feedback.py + frontend submitFeedback).
--
-- Mapping strategy (pattern-based, no manifest lookup)
-- ----------------------------------------------------
-- The frontend manifest (frontend/public/journey-manifest.json) is not
-- available to SQL; it is also built concurrently by Task 7 and may not yet
-- exist when this migration is applied. A pure-SQL transformation of the
-- page_url is used instead:
--
--   1. Strip the scheme + host:         https://app.kvotaflow.ru/quotes/abc -> /quotes/abc
--   2. Strip query string + fragment:   /quotes/abc?step=procurement      -> /quotes/abc
--   3. Replace UUID segments with [id]: /quotes/abc-def-...-123            -> /quotes/[id]
--   4. Prefix with 'app:':              /quotes/[id]                       -> app:/quotes/[id]
--
-- The resulting value is the same shape a Next.js route would produce
-- (entities/journey/types.ts: JourneyNodeId = `app:${string}`). Rows whose
-- page_url does not yield a path starting with '/' (e.g. empty, null,
-- malformed) are left with node_id NULL.
--
-- Idempotency
-- -----------
-- Only rows where node_id IS NULL are touched, so re-running the migration
-- is a no-op for rows already mapped (by backfill or new-feedback logic).
-- The row count is reported via RAISE NOTICE for operator visibility.

SET search_path TO kvota, public;

DO $$
DECLARE
    v_updated integer;
BEGIN
    WITH candidates AS (
        SELECT
            id,
            -- 1+2: strip scheme/host and query/fragment
            regexp_replace(
                split_part(split_part(page_url, '?', 1), '#', 1),
                '^https?://[^/]+',
                ''
            ) AS clean_path
        FROM kvota.user_feedback
        WHERE node_id IS NULL
          AND page_url IS NOT NULL
          AND page_url <> ''
    ),
    mapped AS (
        SELECT
            id,
            clean_path,
            -- 3: UUID -> [id]
            regexp_replace(
                clean_path,
                '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                '/[id]',
                'g'
            ) AS parametrised_path
        FROM candidates
        WHERE clean_path LIKE '/%'  -- only accept real paths
    )
    UPDATE kvota.user_feedback uf
       SET node_id = 'app:' || m.parametrised_path
      FROM mapped m
     WHERE uf.id = m.id
       AND uf.node_id IS NULL;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RAISE NOTICE 'migration 297: backfilled node_id on % user_feedback rows', v_updated;
END $$;
