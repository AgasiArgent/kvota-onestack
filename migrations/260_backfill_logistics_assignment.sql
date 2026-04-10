-- Migration: 260_backfill_logistics_assignment
-- Description: Backfill invoices.pickup_country for quotes stuck in
--   pending_logistics_and_customs after reaching the stage via the Next.js
--   procurement flow that bypassed the FastHTML validation at main.py:19327-19329.
--   Without pickup_country, services/workflow_service.py::assign_logistics_to_invoices
--   silently skips the invoice (line 2360-2362), leaving the quote with no
--   assigned_logistics_user and therefore invisible to the logistics tier.
--
-- Source: derive the country from quote_items.supplier_id → suppliers.country,
--   picking the MODE (most frequent supplier country) per quote via a CTE with
--   ROW_NUMBER() OVER (PARTITION BY quote_id ORDER BY count DESC).
--
-- Idempotent: only updates invoices where pickup_country IS NULL; safe to re-run.
--
-- Related bugs: FB-260410-110450-4b85 (customs/Oleg), FB-260410-123751-4b94 (logistics/Aleyna)
-- ClickUp: 86agtxp84
-- Author: Claude
-- Date: 2026-04-10
--
-- Rollback note: This migration is data-only and idempotent; rerunning is safe.
--   After this migration runs, logistics assignment MUST be re-triggered via
--   `scripts/backfill_logistics_assignment.py`, which calls the Python helper
--   `assign_logistics_to_invoices(quote_id)` for every still-unassigned quote.
--   SQL alone cannot set quotes.assigned_logistics_user — that requires the
--   RPC-driven routing logic in Python.

-- =============================================================================
-- STEP 1: Compute mode supplier country per stuck quote, then backfill invoices
-- =============================================================================

WITH stuck_quotes AS (
    SELECT q.id AS quote_id
    FROM kvota.quotes q
    WHERE q.workflow_status = 'pending_logistics_and_customs'
      AND q.deleted_at IS NULL
),
supplier_country_counts AS (
    -- Count items per (quote_id, supplier country), skipping items with no
    -- resolvable supplier country.
    SELECT
        qi.quote_id,
        s.country,
        COUNT(*) AS item_count
    FROM kvota.quote_items qi
    JOIN stuck_quotes sq ON sq.quote_id = qi.quote_id
    JOIN kvota.suppliers s ON s.id = qi.supplier_id
    WHERE s.country IS NOT NULL
      AND LENGTH(TRIM(s.country)) > 0
    GROUP BY qi.quote_id, s.country
),
mode_country_per_quote AS (
    -- Pick the most common supplier country per quote. Ties are broken
    -- alphabetically on country (deterministic across re-runs).
    SELECT quote_id, country
    FROM (
        SELECT
            quote_id,
            country,
            ROW_NUMBER() OVER (
                PARTITION BY quote_id
                ORDER BY item_count DESC, country ASC
            ) AS rn
        FROM supplier_country_counts
    ) ranked
    WHERE rn = 1
)
UPDATE kvota.invoices i
SET pickup_country = mcpq.country,
    updated_at = NOW()
FROM mode_country_per_quote mcpq
WHERE i.quote_id = mcpq.quote_id
  AND i.pickup_country IS NULL;

-- =============================================================================
-- STEP 2: Log any stuck quotes we could not backfill (missing supplier country)
-- =============================================================================

DO $$
DECLARE
    r RECORD;
    unresolved_count INT := 0;
BEGIN
    FOR r IN
        SELECT DISTINCT q.id, q.idn_quote
        FROM kvota.quotes q
        JOIN kvota.invoices i ON i.quote_id = q.id
        WHERE q.workflow_status = 'pending_logistics_and_customs'
          AND q.deleted_at IS NULL
          AND i.pickup_country IS NULL
    LOOP
        RAISE NOTICE 'Quote % (%) has invoices with NULL pickup_country and no supplier country to backfill from — needs manual investigation',
            r.idn_quote, r.id;
        unresolved_count := unresolved_count + 1;
    END LOOP;

    IF unresolved_count = 0 THEN
        RAISE NOTICE 'All stuck quotes backfilled successfully';
    END IF;
END $$;

-- =============================================================================
-- STEP 3: Verification — count invoices still missing pickup_country
-- =============================================================================

DO $$
DECLARE
    remaining INT;
BEGIN
    SELECT COUNT(*) INTO remaining
    FROM kvota.invoices i
    JOIN kvota.quotes q ON q.id = i.quote_id
    WHERE q.workflow_status = 'pending_logistics_and_customs'
      AND q.deleted_at IS NULL
      AND i.pickup_country IS NULL;

    RAISE NOTICE 'Invoices still missing pickup_country for pending_logistics_and_customs quotes: %', remaining;
END $$;
