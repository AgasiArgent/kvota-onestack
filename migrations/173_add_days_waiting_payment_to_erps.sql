-- Migration 173: Add days_waiting_payment column to erps_registry view
-- Purpose: Show how many days since payment was expected but not received.
-- Formula: (CURRENT_DATE - earliest overdue planned_date) for income items without actual payment.
-- Only counts overdue items (planned_date < CURRENT_DATE AND actual_amount IS NULL).
-- Returns NULL if no overdue payments exist.

-- Recreate the entire view with the new column
DROP VIEW IF EXISTS kvota.erps_registry;

CREATE VIEW kvota.erps_registry AS
SELECT
  s.id AS specification_id,
  s.organization_id,

  -- Deal ID (for navigation to deal detail page)
  d.id AS deal_id,

  -- Block "Specification" - Basic specification info
  s.specification_number AS idn,
  c.name AS client_name,
  c.id AS customer_id,
  s.sign_date,
  q.deal_type,
  s.client_payment_terms AS payment_terms,
  s.advance_percent_from_client AS advance_percent,
  s.payment_deferral_days,

  -- Spec sums (from quotes table - populated by calculation engine)
  COALESCE(q.total_amount_usd, 0) AS spec_sum_usd,
  COALESCE(q.total_profit_usd, 0) AS spec_profit_usd,

  -- Block "Auto" - Delivery deadlines (auto-calculated)
  CASE
    WHEN s.delivery_period_days IS NOT NULL THEN
      s.sign_date + (s.delivery_period_days || ' days')::INTERVAL
    ELSE NULL
  END AS delivery_deadline,

  CASE
    WHEN s.delivery_period_days IS NOT NULL AND s.days_from_delivery_to_advance IS NOT NULL THEN
      s.sign_date + ((s.delivery_period_days + s.days_from_delivery_to_advance) || ' days')::INTERVAL
    ELSE NULL
  END AS advance_payment_deadline,

  -- Days remaining until advance deadline
  CASE
    WHEN s.delivery_period_days IS NOT NULL AND s.days_from_delivery_to_advance IS NOT NULL THEN
      EXTRACT(DAY FROM (
        s.sign_date + ((s.delivery_period_days + s.days_from_delivery_to_advance) || ' days')::INTERVAL
      ) - CURRENT_DATE)::INT
    ELSE NULL
  END AS days_until_advance,

  -- Planned advance amount in USD
  CASE
    WHEN s.advance_percent_from_client IS NOT NULL AND q.total_amount_usd IS NOT NULL THEN
      q.total_amount_usd * (s.advance_percent_from_client / 100.0)
    ELSE 0
  END AS planned_advance_usd,

  -- Total paid by client (income from plan_fact_items via deal)
  COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ), 0) AS total_paid_usd,

  -- Remaining payment (USD)
  COALESCE(q.total_amount_usd, 0) - COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ), 0) AS remaining_payment_usd,

  -- Remaining payment %
  CASE
    WHEN COALESCE(q.total_amount_usd, 0) > 0 THEN
      100.0 * (1 - COALESCE((
        SELECT SUM(pfi.actual_amount)
        FROM kvota.plan_fact_items pfi
        JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
        WHERE pfi.deal_id = d.id
          AND pfc.is_income = true
          AND pfi.actual_amount IS NOT NULL
      ), 0) / q.total_amount_usd)
    ELSE 0
  END AS remaining_payment_percent,

  -- Delivery period (calendar days)
  s.delivery_period_days AS delivery_period_calendar_days,

  -- Delivery period (working days) - placeholder
  NULL::INT AS delivery_period_working_days,

  -- Days until next planned payment (from plan_fact_items)
  (
    SELECT (MIN(pfi.planned_date) - CURRENT_DATE)
    FROM kvota.plan_fact_items pfi
    WHERE pfi.deal_id = d.id
      AND pfi.actual_amount IS NULL
      AND pfi.planned_date >= CURRENT_DATE
  ) AS days_until_next_payment,

  -- NEW: Days waiting for payment (overdue counter)
  -- How many days since the earliest overdue planned income payment date.
  -- Only for items where planned_date has passed and no actual payment received.
  -- Returns NULL if no overdue income payments exist.
  (
    SELECT (CURRENT_DATE - MIN(pfi.planned_date))
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NULL
      AND pfi.planned_date < CURRENT_DATE
  ) AS days_waiting_payment,

  -- Block "Finance" - Finance info (from plan_fact_items via deal)
  (
    SELECT MAX(pfi.actual_date)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ) AS last_payment_date,

  (
    SELECT MIN(pfi.actual_date)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ) AS first_payment_date,

  -- Date when advance was paid (approximate - first payment)
  (
    SELECT MIN(pfi.actual_date)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ) AS advance_payment_date,

  -- Comment
  s.comment,

  -- Block "Procurement" - Procurement info (from plan_fact_items via deal)
  (
    SELECT MIN(pfi.actual_date)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = false
      AND pfi.actual_amount IS NOT NULL
  ) AS supplier_payment_date,

  -- Total spent (total expenses from plan_fact_items)
  COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = false
      AND pfi.actual_amount IS NOT NULL
  ), 0) AS total_spent_usd,

  -- Block "Logistics"
  CASE
    WHEN s.delivery_period_days IS NOT NULL THEN
      s.sign_date + (s.delivery_period_days || ' days')::INTERVAL
    ELSE NULL
  END AS planned_delivery_date,

  s.actual_delivery_date,
  s.planned_dovoz_date,

  -- Block "Management"
  s.priority_tag,

  -- Actual profit (income - expenses from plan_fact_items)
  COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ), 0) - COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = false
      AND pfi.actual_amount IS NOT NULL
  ), 0) AS actual_profit_usd,

  -- Metadata
  s.created_by,
  s.created_at,
  s.updated_at

FROM kvota.specifications s
LEFT JOIN kvota.customers c ON c.id = (
  SELECT customer_id FROM kvota.quotes WHERE id = s.quote_id LIMIT 1
)
LEFT JOIN kvota.quotes q ON q.id = s.quote_id
LEFT JOIN kvota.deals d ON d.specification_id = s.id
WHERE s.status = 'signed'  -- Only show signed specifications
ORDER BY s.sign_date DESC NULLS LAST;

-- Grant SELECT to authenticated users
GRANT SELECT ON kvota.erps_registry TO authenticated;

COMMENT ON VIEW kvota.erps_registry IS 'ERPS Registry (Контроль платежей) with days_waiting_payment counter. Reads from plan_fact_items via deal->spec join.';
