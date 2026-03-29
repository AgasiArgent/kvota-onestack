-- Migration 237: RPC function to create deal from specification in one call
-- Replaces 4 sequential Supabase queries with a single DB function
-- Date: 2026-03-29

CREATE OR REPLACE FUNCTION kvota.create_deal_from_specification(
  p_spec_id UUID,
  p_quote_id UUID,
  p_organization_id UUID
) RETURNS TABLE(deal_id UUID, deal_number TEXT) AS $$
DECLARE
  v_deal_id UUID;
  v_deal_number TEXT;
  v_year INT;
  v_seq INT;
  v_sign_date DATE;
  v_total_amount NUMERIC;
  v_currency VARCHAR;
BEGIN
  v_year := EXTRACT(YEAR FROM NOW());

  -- Get next deal sequence number
  SELECT COUNT(*) + 1 INTO v_seq
  FROM kvota.deals
  WHERE created_at >= make_date(v_year, 1, 1);

  v_deal_number := 'DEAL-' || v_year || '-' || LPAD(v_seq::TEXT, 4, '0');

  -- Get spec sign date
  SELECT sign_date INTO v_sign_date
  FROM kvota.specifications
  WHERE id = p_spec_id;

  -- Get quote financials
  SELECT total_amount, currency INTO v_total_amount, v_currency
  FROM kvota.quotes
  WHERE id = p_quote_id;

  -- Update specification status
  UPDATE kvota.specifications
  SET status = 'signed', updated_at = NOW()
  WHERE id = p_spec_id;

  -- Create deal
  INSERT INTO kvota.deals (
    specification_id, quote_id, organization_id,
    deal_number, signed_at, total_amount, currency, status
  ) VALUES (
    p_spec_id, p_quote_id, p_organization_id,
    v_deal_number, COALESCE(v_sign_date, CURRENT_DATE), COALESCE(v_total_amount, 0), COALESCE(v_currency, 'USD'), 'active'
  ) RETURNING id INTO v_deal_id;

  -- Update quote workflow
  UPDATE kvota.quotes
  SET workflow_status = 'spec_signed'
  WHERE id = p_quote_id;

  RETURN QUERY SELECT v_deal_id, v_deal_number;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
