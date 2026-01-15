-- Migration 036: Extend specifications table for v3.0
-- Created: 2026-01-15
-- Feature DB-020: Add missing columns for v3.0 supply chain integration
--
-- v3.0 additions:
-- - contract_id: Link to customer_contracts for specification numbering
-- - specification_date: Date of specification creation
-- - export_data: JSONB for storing exported data snapshot
-- - Updated status constraint to include 'cancelled'

-- =====================================================
-- ADD NEW COLUMNS
-- =====================================================

-- Add contract_id column (links to customer contract for sequential numbering)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'specifications' AND column_name = 'contract_id'
    ) THEN
        ALTER TABLE specifications
        ADD COLUMN contract_id UUID REFERENCES customer_contracts(id) ON DELETE SET NULL;
    END IF;
END
$$;

COMMENT ON COLUMN specifications.contract_id IS 'Customer contract for specification numbering sequence';

-- Add specification_date column (date when specification was created)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'specifications' AND column_name = 'specification_date'
    ) THEN
        ALTER TABLE specifications
        ADD COLUMN specification_date DATE DEFAULT CURRENT_DATE;
    END IF;
END
$$;

COMMENT ON COLUMN specifications.specification_date IS 'Date when specification was created';

-- Add export_data JSONB column for storing complete snapshot
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'specifications' AND column_name = 'export_data'
    ) THEN
        ALTER TABLE specifications
        ADD COLUMN export_data JSONB DEFAULT '{}';
    END IF;
END
$$;

COMMENT ON COLUMN specifications.export_data IS 'Complete data snapshot at time of specification creation (quote, items, pricing)';

-- =====================================================
-- UPDATE STATUS CONSTRAINT
-- =====================================================

-- Drop and recreate status check constraint to include 'cancelled'
ALTER TABLE specifications DROP CONSTRAINT IF EXISTS specifications_status_check;

ALTER TABLE specifications
ADD CONSTRAINT specifications_status_check
CHECK (status IN ('draft', 'pending_review', 'approved', 'signed', 'cancelled'));

COMMENT ON COLUMN specifications.status IS 'Specification status: draft, pending_review, approved, signed, cancelled';

-- =====================================================
-- CREATE INDEX FOR CONTRACT
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_specifications_contract_id
ON specifications(contract_id);

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function to get next specification number for a contract
CREATE OR REPLACE FUNCTION get_next_specification_number(p_contract_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_next_number INTEGER;
BEGIN
    -- Get and increment the next_specification_number from customer_contracts
    UPDATE customer_contracts
    SET next_specification_number = next_specification_number + 1
    WHERE id = p_contract_id
    RETURNING next_specification_number - 1 INTO v_next_number;

    -- Return the number (before increment)
    RETURN COALESCE(v_next_number, 1);
END;
$$;

COMMENT ON FUNCTION get_next_specification_number(UUID) IS 'Get and increment next specification number for a contract';

-- Function to generate specification number string
-- Format: CONTRACT_NUMBER-SPEC_NUMBER (e.g., "ДП-2025/001-3")
CREATE OR REPLACE FUNCTION generate_specification_number(
    p_contract_id UUID,
    p_spec_number INTEGER DEFAULT NULL
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_contract_number TEXT;
    v_spec_number INTEGER;
BEGIN
    -- Get contract number
    SELECT contract_number INTO v_contract_number
    FROM customer_contracts
    WHERE id = p_contract_id;

    IF v_contract_number IS NULL THEN
        RETURN NULL;
    END IF;

    -- Get specification number (either passed or generate new)
    IF p_spec_number IS NOT NULL THEN
        v_spec_number := p_spec_number;
    ELSE
        v_spec_number := get_next_specification_number(p_contract_id);
    END IF;

    -- Return formatted specification number
    RETURN v_contract_number || '-' || v_spec_number::TEXT;
END;
$$;

COMMENT ON FUNCTION generate_specification_number(UUID, INTEGER) IS 'Generate specification number as CONTRACT_NUMBER-SPEC_NUMBER';

-- Function to create a specification from a quote
CREATE OR REPLACE FUNCTION create_specification_from_quote(
    p_quote_id UUID,
    p_quote_version_id UUID DEFAULT NULL,
    p_contract_id UUID DEFAULT NULL,
    p_created_by UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_spec_id UUID;
    v_org_id UUID;
    v_quote_idn TEXT;
    v_seller_company_name TEXT;
    v_customer_name TEXT;
    v_spec_number INTEGER;
    v_export_data JSONB;
BEGIN
    -- Get quote details
    SELECT
        q.organization_id,
        q.idn,
        sc.name,
        c.name
    INTO v_org_id, v_quote_idn, v_seller_company_name, v_customer_name
    FROM quotes q
    LEFT JOIN seller_companies sc ON q.seller_company_id = sc.id
    LEFT JOIN customers c ON q.customer_id = c.id
    WHERE q.id = p_quote_id;

    IF v_org_id IS NULL THEN
        RAISE EXCEPTION 'Quote not found: %', p_quote_id;
    END IF;

    -- Get next specification number if contract provided
    IF p_contract_id IS NOT NULL THEN
        v_spec_number := get_next_specification_number(p_contract_id);
    END IF;

    -- Build export data snapshot (basic version, can be extended)
    SELECT jsonb_build_object(
        'quote_id', p_quote_id,
        'quote_version_id', p_quote_version_id,
        'quote_idn', v_quote_idn,
        'created_at', NOW(),
        'items', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id', qi.id,
                'item_idn', qi.item_idn,
                'product_name', qi.product_name,
                'quantity', qi.quantity,
                'unit_price', qi.unit_price,
                'total_price', qi.total_price
            ))
            FROM quote_items qi
            WHERE qi.quote_id = p_quote_id
        ), '[]'::jsonb)
    ) INTO v_export_data;

    -- Create specification
    INSERT INTO specifications (
        organization_id,
        quote_id,
        quote_version_id,
        contract_id,
        specification_number,
        specification_date,
        proposal_idn,
        our_legal_entity,
        client_legal_entity,
        export_data,
        status,
        created_by
    ) VALUES (
        v_org_id,
        p_quote_id,
        p_quote_version_id,
        p_contract_id,
        v_spec_number::TEXT, -- Store as string for compatibility
        CURRENT_DATE,
        v_quote_idn,
        v_seller_company_name,
        v_customer_name,
        v_export_data,
        'draft',
        COALESCE(p_created_by, auth.uid())
    )
    RETURNING id INTO v_spec_id;

    RETURN v_spec_id;
END;
$$;

COMMENT ON FUNCTION create_specification_from_quote(UUID, UUID, UUID, UUID) IS
'Create a new specification from a quote with export data snapshot';

-- Function to get specification with all details
CREATE OR REPLACE FUNCTION get_specification_details(p_specification_id UUID)
RETURNS TABLE (
    id UUID,
    organization_id UUID,
    quote_id UUID,
    quote_idn TEXT,
    quote_version_id UUID,
    contract_id UUID,
    contract_number TEXT,
    specification_number TEXT,
    specification_date DATE,
    sign_date DATE,
    validity_period TEXT,
    specification_currency TEXT,
    exchange_rate_to_ruble DECIMAL,
    client_payment_term_after_upd INTEGER,
    client_payment_terms TEXT,
    delivery_city_russia TEXT,
    our_legal_entity TEXT,
    client_legal_entity TEXT,
    signed_scan_url TEXT,
    status TEXT,
    export_data JSONB,
    created_by UUID,
    created_by_email TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
LANGUAGE SQL
SECURITY DEFINER
STABLE
AS $$
    SELECT
        s.id,
        s.organization_id,
        s.quote_id,
        q.idn AS quote_idn,
        s.quote_version_id,
        s.contract_id,
        cc.contract_number,
        s.specification_number,
        s.specification_date,
        s.sign_date,
        s.validity_period,
        s.specification_currency,
        s.exchange_rate_to_ruble,
        s.client_payment_term_after_upd,
        s.client_payment_terms,
        s.delivery_city_russia,
        s.our_legal_entity,
        s.client_legal_entity,
        s.signed_scan_url,
        s.status,
        s.export_data,
        s.created_by,
        u.email AS created_by_email,
        s.created_at,
        s.updated_at
    FROM specifications s
    LEFT JOIN quotes q ON s.quote_id = q.id
    LEFT JOIN customer_contracts cc ON s.contract_id = cc.id
    LEFT JOIN auth.users u ON s.created_by = u.id
    WHERE s.id = p_specification_id;
$$;

COMMENT ON FUNCTION get_specification_details(UUID) IS 'Get specification with all related details';

-- Function to get specifications summary for organization
CREATE OR REPLACE FUNCTION get_specifications_summary(
    p_organization_id UUID,
    p_status TEXT DEFAULT NULL,
    p_from_date DATE DEFAULT NULL,
    p_to_date DATE DEFAULT NULL
)
RETURNS TABLE (
    status TEXT,
    count BIGINT,
    latest_date DATE
)
LANGUAGE SQL
SECURITY DEFINER
STABLE
AS $$
    SELECT
        s.status,
        COUNT(*) AS count,
        MAX(s.specification_date) AS latest_date
    FROM specifications s
    WHERE s.organization_id = p_organization_id
    AND (p_status IS NULL OR s.status = p_status)
    AND (p_from_date IS NULL OR s.specification_date >= p_from_date)
    AND (p_to_date IS NULL OR s.specification_date <= p_to_date)
    GROUP BY s.status
    ORDER BY count DESC;
$$;

COMMENT ON FUNCTION get_specifications_summary(UUID, TEXT, DATE, DATE) IS
'Get specifications count grouped by status for dashboard';

-- =====================================================
-- VIEW FOR SPECIFICATIONS LIST
-- =====================================================

CREATE OR REPLACE VIEW v_specifications_list AS
SELECT
    s.id,
    s.organization_id,
    s.quote_id,
    q.idn AS quote_idn,
    q.title AS quote_title,
    s.contract_id,
    cc.contract_number,
    cust.name AS customer_name,
    s.specification_number,
    s.specification_date,
    s.sign_date,
    s.specification_currency,
    s.our_legal_entity,
    s.client_legal_entity,
    s.status,
    s.signed_scan_url IS NOT NULL AS has_signed_scan,
    s.created_by,
    u.email AS created_by_email,
    s.created_at,
    s.updated_at
FROM specifications s
LEFT JOIN quotes q ON s.quote_id = q.id
LEFT JOIN customer_contracts cc ON s.contract_id = cc.id
LEFT JOIN customers cust ON cc.customer_id = cust.id
LEFT JOIN auth.users u ON s.created_by = u.id;

COMMENT ON VIEW v_specifications_list IS 'Specifications list view with related entity details';

-- =====================================================
-- CUSTOMER SIGNATORY INTEGRATION
-- =====================================================

-- Function to get signatory for specification
-- Uses customer_contacts.is_signatory from the customer linked through contract
CREATE OR REPLACE FUNCTION get_specification_signatory(p_specification_id UUID)
RETURNS TABLE (
    signatory_name TEXT,
    signatory_position TEXT,
    signatory_email TEXT,
    signatory_phone TEXT
)
LANGUAGE SQL
SECURITY DEFINER
STABLE
AS $$
    SELECT
        cc.name AS signatory_name,
        cc.position AS signatory_position,
        cc.email AS signatory_email,
        cc.phone AS signatory_phone
    FROM specifications s
    JOIN customer_contracts ct ON s.contract_id = ct.id
    JOIN customers cust ON ct.customer_id = cust.id
    JOIN customer_contacts cc ON cc.customer_id = cust.id
    WHERE s.id = p_specification_id
    AND cc.is_signatory = true
    LIMIT 1;
$$;

COMMENT ON FUNCTION get_specification_signatory(UUID) IS
'Get signatory contact for specification PDF generation (from customer_contacts.is_signatory)';
