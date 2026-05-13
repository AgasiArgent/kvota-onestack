-- Migration 313: backfill quote_brand_substates for stuck procurement quotes
--
-- Migration 274 (2026-04-13) initialized quote_brand_substates from existing
-- pending_procurement quotes, but the transition path
-- transition_to_pending_procurement() in services/workflow_service.py kept
-- updating quotes.workflow_status without creating qbs rows. Quotes entering
-- pending_procurement between 2026-04-13 and 2026-05-13 (PR #142, commit
-- dc611b86) thus had no qbs rows. Since api/procurement.py::get_kanban
-- inner-joins quote_brand_substates against quotes, those stuck quotes are
-- invisible on the kanban.
--
-- PR #142 fixed the forward path via _ensure_quote_brand_substates() in the
-- transition. This migration re-applies m274's backfill (idempotent) plus
-- advances rows to 'searching_supplier' where every item of (quote, brand)
-- is already routed (МОЗ assigned or marked unavailable) — matching the
-- post-distributing auto-advance logic in maybe_advance_after_distribution().

BEGIN;

-- Step 1: insert missing qbs rows for every (quote, brand) where the quote
-- sits in pending_procurement. Idempotent via composite PK conflict.
INSERT INTO kvota.quote_brand_substates (quote_id, brand, substatus)
SELECT DISTINCT
  qi.quote_id,
  COALESCE(qi.brand, '') AS brand,
  'distributing'
FROM kvota.quote_items qi
JOIN kvota.quotes q ON q.id = qi.quote_id
WHERE q.workflow_status = 'pending_procurement'
ON CONFLICT (quote_id, brand) DO NOTHING;

-- Step 2: auto-advance freshly-created rows whose items are already routed.
-- Without this, a quote whose МОЗ was assigned before this migration would
-- still show in the (hidden-from-regular-МОЗ) «Распределение» column instead
-- of «Поиск поставщика». Mirrors the condition in
-- maybe_advance_after_distribution(): EVERY item of (quote, brand) must have
-- either assigned_procurement_user IS NOT NULL OR is_unavailable = true.
UPDATE kvota.quote_brand_substates qbs
SET
  substatus = 'searching_supplier',
  updated_at = NOW()
WHERE qbs.substatus = 'distributing'
  AND EXISTS (
    SELECT 1
    FROM kvota.quote_items qi
    JOIN kvota.quotes q ON q.id = qi.quote_id
    WHERE qi.quote_id = qbs.quote_id
      AND COALESCE(qi.brand, '') = qbs.brand
      AND q.workflow_status = 'pending_procurement'
  )
  AND NOT EXISTS (
    SELECT 1
    FROM kvota.quote_items qi
    WHERE qi.quote_id = qbs.quote_id
      AND COALESCE(qi.brand, '') = qbs.brand
      AND qi.assigned_procurement_user IS NULL
      AND (qi.is_unavailable IS NULL OR qi.is_unavailable = FALSE)
  );

COMMIT;
