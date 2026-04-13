-- Migration 272: Procurement sub-status state machine + status history audit
-- Phase 4c: adds an additive sub-status axis on top of the frozen workflow_status
-- enum using expand-contract discipline. procurement_substatus is NULL unless
-- workflow_status = 'pending_procurement'; the CHECK constraint enforces this
-- coupling so the sub-state cannot leak into other parent states. Same pattern
-- is intended for future departmental sub-states (logistics, customs).

BEGIN;

-- Sub-status column on quotes (additive — does not touch workflow_status enum)
ALTER TABLE kvota.quotes
  ADD COLUMN IF NOT EXISTS procurement_substatus VARCHAR(30);

-- Valid (workflow_status, substatus) pairs: sub-status is only meaningful when
-- the parent workflow_status is 'pending_procurement'. Any other combination
-- must keep procurement_substatus NULL.
ALTER TABLE kvota.quotes
  ADD CONSTRAINT chk_procurement_substatus CHECK (
    (procurement_substatus IS NULL) OR
    (workflow_status = 'pending_procurement' AND procurement_substatus IN (
      'distributing', 'searching_supplier', 'waiting_prices', 'prices_ready'
    ))
  );

COMMENT ON COLUMN kvota.quotes.procurement_substatus IS
  'Sub-state within pending_procurement: distributing → searching_supplier → waiting_prices → prices_ready. NULL when parent workflow_status != pending_procurement.';

-- Status history audit table: records every (status, substatus) transition so
-- we can reconstruct how a quote moved through the pipeline and who moved it.
CREATE TABLE kvota.status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
  from_status VARCHAR(50),
  from_substatus VARCHAR(30),
  to_status VARCHAR(50),
  to_substatus VARCHAR(30),
  transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  transitioned_by UUID NOT NULL REFERENCES auth.users(id),
  reason TEXT NOT NULL DEFAULT ''
);

COMMENT ON TABLE kvota.status_history IS
  'Append-only audit log of workflow_status / procurement_substatus transitions per quote.';

CREATE INDEX IF NOT EXISTS idx_status_history_quote
  ON kvota.status_history(quote_id);
CREATE INDEX IF NOT EXISTS idx_status_history_date
  ON kvota.status_history(transitioned_at DESC);

-- Backfill: every quote currently sitting in pending_procurement starts in the
-- 'distributing' sub-state. Safe to re-run: only fills rows where the sub-status
-- column is still NULL.
UPDATE kvota.quotes
  SET procurement_substatus = 'distributing'
  WHERE workflow_status = 'pending_procurement'
    AND procurement_substatus IS NULL;

COMMIT;
