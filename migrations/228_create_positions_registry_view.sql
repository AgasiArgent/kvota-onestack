-- Positions Registry View: aggregates quote_items by brand + SKU for procurement reference
-- Shows the latest pricing/availability per unique product across all quotes

CREATE OR REPLACE VIEW kvota.positions_registry_view AS
WITH base AS (
  SELECT
    qi.brand,
    COALESCE(qi.idn_sku, '') AS idn_sku,
    qi.product_name,
    qi.purchase_price_original,
    qi.purchase_currency,
    qi.is_unavailable,
    qi.updated_at,
    qi.assigned_procurement_user,
    qi.proforma_number,
    qi.quote_id,
    q.organization_id,
    q.idn AS quote_idn,
    up.full_name AS moz_name,
    ROW_NUMBER() OVER (
      PARTITION BY qi.brand, COALESCE(qi.idn_sku, '')
      ORDER BY qi.updated_at DESC
    ) AS rn,
    bool_or(NOT COALESCE(qi.is_unavailable, false)
            AND qi.purchase_price_original IS NOT NULL)
      OVER (PARTITION BY qi.brand, COALESCE(qi.idn_sku, '')) AS has_available,
    bool_or(COALESCE(qi.is_unavailable, false))
      OVER (PARTITION BY qi.brand, COALESCE(qi.idn_sku, '')) AS has_unavailable,
    COUNT(*) OVER (PARTITION BY qi.brand, COALESCE(qi.idn_sku, '')) AS entry_count
  FROM kvota.quote_items qi
  JOIN kvota.quotes q ON q.id = qi.quote_id
  LEFT JOIN kvota.user_profiles up ON up.user_id = qi.assigned_procurement_user
  WHERE qi.procurement_status = 'completed'
     OR COALESCE(qi.is_unavailable, false) = true
)
SELECT
  brand,
  idn_sku,
  product_name,
  purchase_price_original AS latest_price,
  purchase_currency AS latest_currency,
  moz_name AS last_moz_name,
  assigned_procurement_user AS last_moz_id,
  updated_at AS last_updated,
  entry_count,
  organization_id,
  CASE
    WHEN has_available AND has_unavailable THEN 'mixed'
    WHEN has_available THEN 'available'
    ELSE 'unavailable'
  END AS availability_status
FROM base
WHERE rn = 1;

-- Index to speed up the view's base query
CREATE INDEX IF NOT EXISTS idx_quote_items_brand_sku_updated
  ON kvota.quote_items (brand, COALESCE(idn_sku, ''), updated_at DESC)
  WHERE procurement_status = 'completed' OR is_unavailable = true;
