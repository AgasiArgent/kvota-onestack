-- Fix race condition in generate_quote_idn: make counter increment atomic
-- Previously: SELECT counter → compute +1 → UPDATE (two statements, not atomic)
-- Now: single UPDATE...RETURNING (row-level lock prevents concurrent reads)

CREATE OR REPLACE FUNCTION kvota.generate_quote_idn(p_seller_company_id UUID, p_customer_inn VARCHAR)
RETURNS VARCHAR
LANGUAGE plpgsql
AS $$
DECLARE
    v_seller_code VARCHAR(10);
    v_year INTEGER;
    v_counter_key TEXT;
    v_current_seq INTEGER;
    v_org_id UUID;
BEGIN
    SELECT supplier_code, organization_id INTO v_seller_code, v_org_id
    FROM kvota.seller_companies
    WHERE id = p_seller_company_id;

    IF v_seller_code IS NULL THEN
        RAISE EXCEPTION 'Seller company not found: %', p_seller_company_id;
    END IF;

    v_year := EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER;
    v_counter_key := v_year::TEXT || '-' || p_customer_inn;

    -- Atomic increment: UPDATE locks the row, preventing concurrent reads
    UPDATE kvota.organizations
    SET idn_counters = COALESCE(idn_counters, '{}'::JSONB) ||
        jsonb_build_object(
            v_counter_key,
            COALESCE((COALESCE(idn_counters, '{}'::JSONB)->>v_counter_key)::INTEGER, 0) + 1
        )
    WHERE id = v_org_id
    RETURNING (idn_counters->>v_counter_key)::INTEGER INTO v_current_seq;

    RETURN v_seller_code || '-' || p_customer_inn || '-' || v_year::TEXT || '-' || v_current_seq::TEXT;
END;
$$;
