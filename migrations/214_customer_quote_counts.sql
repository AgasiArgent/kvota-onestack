-- Migration 214: Add RPC function for customer quote counts (used by Next.js frontend)
CREATE OR REPLACE FUNCTION kvota.get_customers_quote_counts(customer_ids uuid[])
RETURNS TABLE(customer_id uuid, cnt bigint, last_date timestamptz) AS $$
  SELECT
    q.customer_id,
    count(*)::bigint AS cnt,
    max(q.created_at) AS last_date
  FROM kvota.quotes q
  WHERE q.customer_id = ANY(customer_ids)
  GROUP BY q.customer_id;
$$ LANGUAGE sql STABLE;
