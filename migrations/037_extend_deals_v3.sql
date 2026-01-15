-- Migration: 037_extend_deals_v3.sql
-- Description: Verify deals table and add v3.0 helper functions
-- Feature DB-021 from features.json v3.0
-- Created: 2026-01-15

-- ============================================
-- VERIFICATION: Table exists from migration 007
-- ============================================

-- Verify deals table structure
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'deals' AND table_schema = 'public') THEN
        RAISE EXCEPTION 'deals table does not exist - run migration 007 first';
    END IF;

    -- Verify essential columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'deals' AND column_name = 'specification_id') THEN
        RAISE EXCEPTION 'deals.specification_id column missing';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'deals' AND column_name = 'quote_id') THEN
        RAISE EXCEPTION 'deals.quote_id column missing';
    END IF;

    RAISE NOTICE 'deals table verified - all required columns present';
END $$;

-- ============================================
-- V3.0 HELPER FUNCTIONS
-- ============================================

-- Create deal from specification with full context
CREATE OR REPLACE FUNCTION public.create_deal_from_specification(
    p_specification_id UUID,
    p_signed_at DATE DEFAULT CURRENT_DATE,
    p_created_by UUID DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_spec RECORD;
    v_deal_id UUID;
    v_deal_number TEXT;
BEGIN
    -- Get specification details
    SELECT s.*, q.organization_id, q.customer_id
    INTO v_spec
    FROM public.specifications s
    JOIN public.quotes q ON s.quote_id = q.id
    WHERE s.id = p_specification_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Specification % not found', p_specification_id;
    END IF;

    -- Check specification status
    IF v_spec.status != 'signed' THEN
        RAISE EXCEPTION 'Cannot create deal from specification with status %', v_spec.status;
    END IF;

    -- Check if deal already exists
    IF EXISTS (SELECT 1 FROM public.deals WHERE specification_id = p_specification_id) THEN
        RAISE EXCEPTION 'Deal already exists for specification %', p_specification_id;
    END IF;

    -- Generate deal number
    v_deal_number := public.generate_deal_number(v_spec.organization_id);

    -- Create deal
    INSERT INTO public.deals (
        id,
        organization_id,
        specification_id,
        quote_id,
        deal_number,
        signed_at,
        total_amount,
        currency,
        status,
        created_by
    ) VALUES (
        gen_random_uuid(),
        v_spec.organization_id,
        p_specification_id,
        v_spec.quote_id,
        v_deal_number,
        p_signed_at,
        v_spec.total_amount,
        COALESCE(v_spec.currency, 'RUB'),
        'active',
        p_created_by
    )
    RETURNING id INTO v_deal_id;

    -- Update specification status to indicate deal created
    UPDATE public.specifications
    SET status = 'signed',  -- Keep signed status
        updated_at = NOW()
    WHERE id = p_specification_id;

    -- Update quote workflow status to 'deal'
    UPDATE public.quotes
    SET workflow_status = 'deal',
        updated_at = NOW()
    WHERE id = v_spec.quote_id;

    RETURN v_deal_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.create_deal_from_specification IS 'Creates a deal from a signed specification, updating workflow status';

-- Get deal details with related info
CREATE OR REPLACE FUNCTION public.get_deal_details(p_deal_id UUID)
RETURNS TABLE (
    deal_id UUID,
    deal_number VARCHAR,
    signed_at DATE,
    total_amount DECIMAL,
    currency VARCHAR,
    deal_status VARCHAR,
    deal_created_at TIMESTAMPTZ,
    specification_id UUID,
    specification_number VARCHAR,
    specification_date DATE,
    quote_id UUID,
    quote_number VARCHAR,
    customer_id UUID,
    customer_name VARCHAR,
    seller_company_id UUID,
    seller_company_name VARCHAR,
    items_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id AS deal_id,
        d.deal_number::VARCHAR,
        d.signed_at,
        d.total_amount,
        d.currency::VARCHAR,
        d.status::VARCHAR AS deal_status,
        d.created_at AS deal_created_at,
        s.id AS specification_id,
        s.specification_number::VARCHAR,
        s.specification_date,
        q.id AS quote_id,
        q.quote_number::VARCHAR,
        c.id AS customer_id,
        c.name::VARCHAR AS customer_name,
        sc.id AS seller_company_id,
        sc.name::VARCHAR AS seller_company_name,
        (SELECT COUNT(*) FROM public.quote_items qi WHERE qi.quote_id = q.id)::BIGINT AS items_count
    FROM public.deals d
    JOIN public.specifications s ON d.specification_id = s.id
    JOIN public.quotes q ON d.quote_id = q.id
    LEFT JOIN public.customers c ON q.customer_id = c.id
    LEFT JOIN public.seller_companies sc ON q.seller_company_id = sc.id
    WHERE d.id = p_deal_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION public.get_deal_details IS 'Returns comprehensive deal information with related entities';

-- Get deals summary for organization
CREATE OR REPLACE FUNCTION public.get_deals_summary(p_organization_id UUID)
RETURNS TABLE (
    total_deals BIGINT,
    active_deals BIGINT,
    completed_deals BIGINT,
    cancelled_deals BIGINT,
    total_amount_rub DECIMAL,
    total_amount_usd DECIMAL,
    total_amount_eur DECIMAL,
    total_amount_cny DECIMAL,
    this_year_deals BIGINT,
    this_month_deals BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT AS total_deals,
        COUNT(*) FILTER (WHERE d.status = 'active')::BIGINT AS active_deals,
        COUNT(*) FILTER (WHERE d.status = 'completed')::BIGINT AS completed_deals,
        COUNT(*) FILTER (WHERE d.status = 'cancelled')::BIGINT AS cancelled_deals,
        COALESCE(SUM(d.total_amount) FILTER (WHERE d.currency = 'RUB'), 0) AS total_amount_rub,
        COALESCE(SUM(d.total_amount) FILTER (WHERE d.currency = 'USD'), 0) AS total_amount_usd,
        COALESCE(SUM(d.total_amount) FILTER (WHERE d.currency = 'EUR'), 0) AS total_amount_eur,
        COALESCE(SUM(d.total_amount) FILTER (WHERE d.currency = 'CNY'), 0) AS total_amount_cny,
        COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM d.signed_at) = EXTRACT(YEAR FROM CURRENT_DATE))::BIGINT AS this_year_deals,
        COUNT(*) FILTER (WHERE d.signed_at >= DATE_TRUNC('month', CURRENT_DATE))::BIGINT AS this_month_deals
    FROM public.deals d
    WHERE d.organization_id = p_organization_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION public.get_deals_summary IS 'Returns deal statistics for an organization';

-- Get deals list with filtering
CREATE OR REPLACE FUNCTION public.get_deals_list(
    p_organization_id UUID,
    p_status VARCHAR DEFAULT NULL,
    p_customer_id UUID DEFAULT NULL,
    p_from_date DATE DEFAULT NULL,
    p_to_date DATE DEFAULT NULL,
    p_limit INT DEFAULT 50,
    p_offset INT DEFAULT 0
)
RETURNS TABLE (
    deal_id UUID,
    deal_number VARCHAR,
    signed_at DATE,
    total_amount DECIMAL,
    currency VARCHAR,
    status VARCHAR,
    customer_name VARCHAR,
    specification_number VARCHAR,
    quote_number VARCHAR,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id AS deal_id,
        d.deal_number::VARCHAR,
        d.signed_at,
        d.total_amount,
        d.currency::VARCHAR,
        d.status::VARCHAR,
        c.name::VARCHAR AS customer_name,
        s.specification_number::VARCHAR,
        q.quote_number::VARCHAR,
        d.created_at
    FROM public.deals d
    JOIN public.specifications s ON d.specification_id = s.id
    JOIN public.quotes q ON d.quote_id = q.id
    LEFT JOIN public.customers c ON q.customer_id = c.id
    WHERE d.organization_id = p_organization_id
    AND (p_status IS NULL OR d.status = p_status)
    AND (p_customer_id IS NULL OR q.customer_id = p_customer_id)
    AND (p_from_date IS NULL OR d.signed_at >= p_from_date)
    AND (p_to_date IS NULL OR d.signed_at <= p_to_date)
    ORDER BY d.signed_at DESC, d.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION public.get_deals_list IS 'Returns filtered list of deals for an organization';

-- Complete deal
CREATE OR REPLACE FUNCTION public.complete_deal(
    p_deal_id UUID,
    p_completed_by UUID DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_deal RECORD;
BEGIN
    -- Get deal
    SELECT * INTO v_deal FROM public.deals WHERE id = p_deal_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Deal % not found', p_deal_id;
    END IF;

    IF v_deal.status != 'active' THEN
        RAISE EXCEPTION 'Cannot complete deal with status %', v_deal.status;
    END IF;

    -- Update deal status
    UPDATE public.deals
    SET status = 'completed',
        updated_at = NOW()
    WHERE id = p_deal_id;

    -- Update quote workflow status to completed
    UPDATE public.quotes
    SET workflow_status = 'completed',
        updated_at = NOW()
    WHERE id = v_deal.quote_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.complete_deal IS 'Marks a deal as completed, updating quote workflow status';

-- Cancel deal
CREATE OR REPLACE FUNCTION public.cancel_deal(
    p_deal_id UUID,
    p_reason TEXT DEFAULT NULL,
    p_cancelled_by UUID DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_deal RECORD;
BEGIN
    -- Get deal
    SELECT * INTO v_deal FROM public.deals WHERE id = p_deal_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Deal % not found', p_deal_id;
    END IF;

    IF v_deal.status = 'cancelled' THEN
        RAISE NOTICE 'Deal % is already cancelled', p_deal_id;
        RETURN FALSE;
    END IF;

    IF v_deal.status = 'completed' THEN
        RAISE EXCEPTION 'Cannot cancel a completed deal';
    END IF;

    -- Update deal status
    UPDATE public.deals
    SET status = 'cancelled',
        updated_at = NOW()
    WHERE id = p_deal_id;

    -- Update quote workflow status to cancelled
    UPDATE public.quotes
    SET workflow_status = 'cancelled',
        updated_at = NOW()
    WHERE id = v_deal.quote_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.cancel_deal IS 'Cancels a deal, updating quote workflow status';

-- ============================================
-- VIEW: Deals with full context
-- ============================================

CREATE OR REPLACE VIEW public.v_deals_list AS
SELECT
    d.id AS deal_id,
    d.organization_id,
    d.deal_number,
    d.signed_at,
    d.total_amount,
    d.currency,
    d.status,
    d.created_at,
    d.updated_at,
    s.id AS specification_id,
    s.specification_number,
    s.specification_date,
    q.id AS quote_id,
    q.quote_number,
    q.idn AS quote_idn,
    c.id AS customer_id,
    c.name AS customer_name,
    c.inn AS customer_inn,
    sc.id AS seller_company_id,
    sc.name AS seller_company_name,
    sc.supplier_code AS seller_code,
    (SELECT COUNT(*) FROM public.quote_items qi WHERE qi.quote_id = q.id) AS items_count,
    -- Plan-fact summary (to be used after plan_fact tables are ready)
    COALESCE(
        (SELECT SUM(pfi.actual_amount) FROM public.plan_fact_items pfi WHERE pfi.deal_id = d.id AND pfi.actual_amount IS NOT NULL),
        0
    ) AS total_actual_payments
FROM public.deals d
JOIN public.specifications s ON d.specification_id = s.id
JOIN public.quotes q ON d.quote_id = q.id
LEFT JOIN public.customers c ON q.customer_id = c.id
LEFT JOIN public.seller_companies sc ON q.seller_company_id = sc.id;

COMMENT ON VIEW public.v_deals_list IS 'Comprehensive view of deals with related entities';

-- ============================================
-- GRANT PERMISSIONS
-- ============================================

GRANT EXECUTE ON FUNCTION public.create_deal_from_specification TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_deal_details TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_deals_summary TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_deals_list TO authenticated;
GRANT EXECUTE ON FUNCTION public.complete_deal TO authenticated;
GRANT EXECUTE ON FUNCTION public.cancel_deal TO authenticated;
GRANT SELECT ON public.v_deals_list TO authenticated;
