-- Migration 274: Per-(quote, brand) procurement sub-status
--
-- Shifts the kanban unit-of-work from "quote" to "(quote, brand)". Replaces the
-- quote-level procurement_substatus column (migration 272) with a dedicated
-- table keyed by (quote_id, brand). A quote with N distinct brands now owns N
-- rows — each brand flows through distributing → searching_supplier →
-- waiting_prices → prices_ready independently.
--
-- Empty string '' is used for items with NULL brand (unbranded), so the PK is
-- always well-defined. status_history gets a nullable `brand` column so a row
-- NULL means "quote-level transition", non-NULL means "per-brand transition".

BEGIN;

-- Per-(quote, brand) sub-status row. Unit of work on the kanban.
CREATE TABLE kvota.quote_brand_substates (
  quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
  brand TEXT NOT NULL,  -- '' (empty string) for unbranded items
  substatus VARCHAR(30) NOT NULL DEFAULT 'distributing',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_by UUID,  -- FK to auth.users(id) — nullable for backfill
  PRIMARY KEY (quote_id, brand),
  CONSTRAINT chk_qbs_substatus CHECK (
    substatus IN ('distributing','searching_supplier','waiting_prices','prices_ready')
  )
);

COMMENT ON TABLE kvota.quote_brand_substates IS
  'Per-(quote,brand) procurement sub-status. Unit of work for МОЗ on the kanban. '
  'Q-202604-0034 with 2 brands → 2 rows. NULL brand becomes empty string.';

CREATE INDEX idx_qbs_substatus ON kvota.quote_brand_substates(substatus);

-- Extend status_history with brand for per-brand transitions (NULL = quote-level).
ALTER TABLE kvota.status_history
  ADD COLUMN IF NOT EXISTS brand TEXT;

-- Backfill: for each pending_procurement quote, for each distinct brand in its
-- items, insert a row with substatus='distributing'. Everything starts fresh —
-- application-level auto-advance will move rows to 'searching_supplier' if all
-- items of that brand already have МОЗ assigned.
INSERT INTO kvota.quote_brand_substates (quote_id, brand, substatus)
SELECT DISTINCT
  qi.quote_id,
  COALESCE(qi.brand, '') AS brand,
  'distributing'
FROM kvota.quote_items qi
JOIN kvota.quotes q ON q.id = qi.quote_id
WHERE q.workflow_status = 'pending_procurement'
ON CONFLICT (quote_id, brand) DO NOTHING;

-- Drop the legacy quote-level substatus column (only the kanban read it —
-- verified: api/procurement.py + services/workflow_service.py are the only
-- non-test readers, and both are refactored in this change).
ALTER TABLE kvota.quotes DROP CONSTRAINT IF EXISTS chk_procurement_substatus;
ALTER TABLE kvota.quotes DROP COLUMN IF EXISTS procurement_substatus;

COMMIT;
