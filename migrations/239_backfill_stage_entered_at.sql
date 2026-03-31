-- Migration 239: Backfill stage_entered_at from workflow_transitions
-- For each quote, set stage_entered_at to the most recent transition timestamp.
-- Quotes with no transitions fall back to quotes.created_at.
-- Date: 2026-03-30

UPDATE kvota.quotes q
SET stage_entered_at = COALESCE(
    (SELECT MAX(wt.created_at)
     FROM kvota.workflow_transitions wt
     WHERE wt.quote_id = q.id),
    q.created_at
)
WHERE q.stage_entered_at IS NULL;
