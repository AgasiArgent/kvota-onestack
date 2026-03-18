-- RPC function: aggregate financial data per customer for expanded view
-- Returns: quotes count, last quote date, specs count, revenue USD, profit USD

CREATE OR REPLACE FUNCTION kvota.get_customer_financials(p_org_id UUID)
RETURNS TABLE (
  customer_id UUID,
  quotes_count BIGINT,
  last_quote_date TIMESTAMPTZ,
  specs_count BIGINT,
  revenue_usd NUMERIC,
  profit_usd NUMERIC
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT
    q.customer_id,
    COUNT(DISTINCT q.id) AS quotes_count,
    MAX(q.created_at) AS last_quote_date,
    COUNT(DISTINCT s.id) AS specs_count,
    COALESCE(SUM(q.total_amount_usd), 0) AS revenue_usd,
    COALESCE(SUM(q.total_profit_usd), 0) AS profit_usd
  FROM kvota.quotes q
  LEFT JOIN kvota.specifications s ON s.quote_id = q.id
  WHERE q.organization_id = p_org_id
    AND q.deleted_at IS NULL
  GROUP BY q.customer_id;
$$;

-- Performance index for the RPC
CREATE INDEX IF NOT EXISTS idx_quotes_customer_org_status
  ON kvota.quotes(customer_id, organization_id, status)
  WHERE deleted_at IS NULL;
