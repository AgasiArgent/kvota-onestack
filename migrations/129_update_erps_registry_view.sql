-- Migration 129: Update ERPS Registry View with delivery dates and comment
-- Purpose: Add planned_delivery_date, actual_delivery_date, planned_dovoz_date, comment, priority_tag

-- Drop and recreate view
DROP VIEW IF EXISTS kvota.erps_registry;

CREATE VIEW kvota.erps_registry AS
SELECT
  s.id AS specification_id,
  s.organization_id,

  -- Блок "Спецификация" - Basic specification info
  s.specification_number AS idn,
  c.name AS client_name,
  c.id AS customer_id,
  s.sign_date,
  q.deal_type,
  s.client_payment_terms AS payment_terms,
  s.advance_percent_from_client AS advance_percent,
  s.payment_deferral_days,

  -- Суммы спецификации (из calculation)
  COALESCE(qcs.calc_ak16_final_price_total, 0) AS spec_sum_usd,
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
    WHEN s.advance_percent_from_client IS NOT NULL AND qcs.calc_ak16_final_price_total IS NOT NULL THEN
      qcs.calc_ak16_final_price_total * (s.advance_percent_from_client / 100.0)
    ELSE 0
  END AS planned_advance_usd,

  -- Всего оплачено клиентом (income from specification_payments)
  COALESCE((
    SELECT SUM(amount)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'income'
  ), 0) AS total_paid_usd,

  -- Остаток к оплате (remaining payment in USD)
  COALESCE(qcs.calc_ak16_final_price_total, 0) - COALESCE((
    SELECT SUM(amount)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'income'
  ), 0) AS remaining_payment_usd,

  -- Остаток к оплате % (remaining payment percentage)
  CASE
    WHEN COALESCE(qcs.calc_ak16_final_price_total, 0) > 0 THEN
      100.0 * (1 - COALESCE((
        SELECT SUM(amount)
        FROM kvota.specification_payments sp
        WHERE sp.specification_id = s.id
          AND sp.category = 'income'
      ), 0) / qcs.calc_ak16_final_price_total)
    ELSE 0
  END AS remaining_payment_percent,

  -- Срок поставки (delivery period in days)
  s.delivery_period_days AS delivery_period_calendar_days,

  -- Срок поставки в рабочих днях (пока NULL, потом добавим функцию)
  NULL::INT AS delivery_period_working_days,

  -- Блок "Финансы" - Finance info
  (
    SELECT MAX(payment_date)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'income'
  ) AS last_payment_date,

  (
    SELECT MIN(payment_date)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'income'
  ) AS first_payment_date,

  -- Date when advance was paid (approximate - first payment)
  (
    SELECT MIN(payment_date)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'income'
  ) AS advance_payment_date,

  -- Комментарий
  s.comment,

  -- Блок "Закупки" - Procurement info
  (
    SELECT MIN(payment_date)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'expense'
  ) AS supplier_payment_date,

  -- Всего потрачено (total expenses)
  COALESCE((
    SELECT SUM(amount)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'expense'
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

  -- Фактический профит (actual profit = income - expenses)
  COALESCE((
    SELECT SUM(amount)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'income'
  ), 0) - COALESCE((
    SELECT SUM(amount)
    FROM kvota.specification_payments sp
    WHERE sp.specification_id = s.id
      AND sp.category = 'expense'
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
LEFT JOIN kvota.quote_calculation_summaries qcs ON qcs.quote_id = q.id
WHERE s.status = 'signed'  -- Only show signed specifications
ORDER BY s.sign_date DESC NULLS LAST;

-- Grant SELECT to authenticated users
GRANT SELECT ON kvota.erps_registry TO authenticated;

COMMENT ON VIEW kvota.erps_registry IS 'ERPS Registry - Единый реестр подписанных спецификаций with all fields including delivery dates and comments';
