-- One-time retroactive auto-advance for brand slices whose items were
-- already fully distributed BEFORE migration 274 landed. Without this,
-- ~11 quote-brand pairs on prod would be stuck in 'distributing' forever
-- because auto-advance in application code only fires on item-assignment
-- events (assign/bulk endpoints), and nothing triggers it for pre-existing
-- state.
--
-- For each (quote, brand) in distributing where every item has either
-- assigned_procurement_user IS NOT NULL or is_unavailable = true:
--   1. Insert a status_history row (transitioned_by = admin@test.kvota.ru
--      as system-representative; application-level future advances attribute
--      to the acting user).
--   2. Update quote_brand_substates.substatus → 'searching_supplier'.

BEGIN;

WITH ready_slices AS (
    SELECT qbs.quote_id, qbs.brand
    FROM kvota.quote_brand_substates qbs
    JOIN kvota.quote_items qi
      ON qi.quote_id = qbs.quote_id
     AND COALESCE(qi.brand, '') = qbs.brand
    WHERE qbs.substatus = 'distributing'
    GROUP BY qbs.quote_id, qbs.brand
    HAVING COUNT(qi.id) FILTER (
               WHERE qi.assigned_procurement_user IS NULL
                 AND qi.is_unavailable IS NOT TRUE
           ) = 0
       AND COUNT(qi.id) > 0
)
INSERT INTO kvota.status_history (
    quote_id, from_status, from_substatus,
    to_status, to_substatus,
    transitioned_by, brand, reason
)
SELECT
    r.quote_id,
    'pending_procurement', 'distributing',
    'pending_procurement', 'searching_supplier',
    (SELECT id FROM auth.users WHERE email = 'admin@test.kvota.ru' LIMIT 1),
    r.brand,
    'Auto-advance: distribution already complete before migration 274'
FROM ready_slices r;

UPDATE kvota.quote_brand_substates qbs
SET substatus = 'searching_supplier',
    updated_at = NOW()
WHERE qbs.substatus = 'distributing'
  AND EXISTS (
      SELECT 1
      FROM kvota.quote_items qi
      WHERE qi.quote_id = qbs.quote_id
        AND COALESCE(qi.brand, '') = qbs.brand
      GROUP BY qi.quote_id
      HAVING COUNT(qi.id) FILTER (
                 WHERE qi.assigned_procurement_user IS NULL
                   AND qi.is_unavailable IS NOT TRUE
             ) = 0
         AND COUNT(qi.id) > 0
  );

COMMIT;
