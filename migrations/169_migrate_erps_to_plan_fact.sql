-- Migration 169: Migrate ERPS Registry view from specification_payments to plan_fact_items
-- Purpose: The erps_registry view currently reads from the DEPRECATED specification_payments table.
--          Nothing writes to specification_payments anymore - all payments go through plan_fact_items.
--          This migration updates the view to read from plan_fact_items via the deal->spec join.
-- Join chain: specifications -> deals (deals.specification_id) -> plan_fact_items (plan_fact_items.deal_id)
-- Also adds: deal_id column, days_until_next_payment column

-- Drop and recreate view
DROP VIEW IF EXISTS kvota.erps_registry;

CREATE VIEW kvota.erps_registry AS
SELECT
  s.id AS specification_id,
  s.organization_id,

  -- Deal ID (for navigation to deal detail page)
  d.id AS deal_id,

  -- Блок "Спецификация" - Basic specification info
  s.specification_number AS idn,
  c.name AS client_name,
  c.id AS customer_id,
  s.sign_date,
  q.deal_type,
  s.client_payment_terms AS payment_terms,
  s.advance_percent_from_client AS advance_percent,
  s.payment_deferral_days,

  -- Суммы спецификации (из quotes table - populated by calculation engine)
  COALESCE(q.total_amount_usd, 0) AS spec_sum_usd,
  COALESCE(q.total_profit_usd, 0) AS spec_profit_usd,

  -- Блок "Авто" - Сроки поставки (auto-calculated deadlines)
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

  -- Остаток времени на аванс (дни) - days remaining until advance deadline
  CASE
    WHEN s.delivery_period_days IS NOT NULL AND s.days_from_delivery_to_advance IS NOT NULL THEN
      EXTRACT(DAY FROM (
        s.sign_date + ((s.delivery_period_days + s.days_from_delivery_to_advance) || ' days')::INTERVAL
      ) - CURRENT_DATE)::INT
    ELSE NULL
  END AS days_until_advance,

  -- Планируемая сумма аванса в USD (calculated advance amount)
  CASE
    WHEN s.advance_percent_from_client IS NOT NULL AND q.total_amount_usd IS NOT NULL THEN
      q.total_amount_usd * (s.advance_percent_from_client / 100.0)
    ELSE 0
  END AS planned_advance_usd,

  -- Всего оплачено клиентом (income from plan_fact_items via deal)
  COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ), 0) AS total_paid_usd,

  -- Остаток к оплате (remaining payment in USD)
  COALESCE(q.total_amount_usd, 0) - COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = true
      AND pfi.actual_amount IS NOT NULL
  ), 0) AS remaining_payment_usd,

  -- Остаток к оплате % (remaining payment percentage)
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

  -- Срок поставки (delivery period in days)
  s.delivery_period_days AS delivery_period_calendar_days,

  -- Срок поставки в рабочих днях (пока NULL, потом добавим функцию)
  NULL::INT AS delivery_period_working_days,

  -- Дней до следующего планового платежа (from plan_fact_items)
  (
    SELECT (MIN(pfi.planned_date) - CURRENT_DATE)
    FROM kvota.plan_fact_items pfi
    WHERE pfi.deal_id = d.id
      AND pfi.actual_amount IS NULL
      AND pfi.planned_date >= CURRENT_DATE
  ) AS days_until_next_payment,

  -- Блок "Финансы" - Finance info (from plan_fact_items via deal)
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

  -- Комментарий
  s.comment,

  -- Блок "Закупки" - Procurement info (from plan_fact_items via deal)
  (
    SELECT MIN(pfi.actual_date)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = false
      AND pfi.actual_amount IS NOT NULL
  ) AS supplier_payment_date,

  -- Всего потрачено (total expenses from plan_fact_items)
  COALESCE((
    SELECT SUM(pfi.actual_amount)
    FROM kvota.plan_fact_items pfi
    JOIN kvota.plan_fact_categories pfc ON pfc.id = pfi.category_id
    WHERE pfi.deal_id = d.id
      AND pfc.is_income = false
      AND pfi.actual_amount IS NOT NULL
  ), 0) AS total_spent_usd,

  -- Блок "Логистика"
  -- Планируемая дата доставки = sign_date + delivery_period_days
  CASE
    WHEN s.delivery_period_days IS NOT NULL THEN
      s.sign_date + (s.delivery_period_days || ' days')::INTERVAL
    ELSE NULL
  END AS planned_delivery_date,

  -- Фактическая дата доставки
  s.actual_delivery_date,

  -- Планируемая дата довоза
  s.planned_dovoz_date,

  -- Блок "Финансы/Руководство"
  s.priority_tag,

  -- Фактический профит (actual profit = income - expenses from plan_fact_items)
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

  -- Метаданные
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

COMMENT ON VIEW kvota.erps_registry IS 'ERPS Registry (Контроль платежей) - migrated from specification_payments to plan_fact_items. Includes deal_id for navigation and days_until_next_payment counter.';
