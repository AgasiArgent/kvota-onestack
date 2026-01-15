-- Migration: 039_create_plan_fact_items_table.sql
-- Description: Create plan_fact_items table for tracking planned vs actual payments
-- Feature DB-023 from features.json v3.0
-- Created: 2026-01-15

-- ============================================
-- TABLE: plan_fact_items
-- ============================================
-- Purpose: Track planned and actual payments for deals
-- Each record represents a payment line item (income or expense)
-- Variance is auto-calculated when actual_amount is set

CREATE TABLE IF NOT EXISTS public.plan_fact_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parent reference
    deal_id UUID NOT NULL REFERENCES public.deals(id) ON DELETE CASCADE,

    -- Category from plan_fact_categories
    category_id UUID NOT NULL REFERENCES public.plan_fact_categories(id) ON DELETE RESTRICT,

    -- Description for this specific item
    description VARCHAR(255),

    -- Planned values (set when deal is created)
    planned_amount DECIMAL(15, 2),
    planned_currency VARCHAR(3) DEFAULT 'RUB',
    planned_date DATE,

    -- Actual values (filled when payment is registered)
    actual_amount DECIMAL(15, 2),
    actual_currency VARCHAR(3),
    actual_date DATE,
    actual_exchange_rate DECIMAL(10, 4), -- Rate to convert actual to planned currency

    -- Calculated variance (actual - planned in RUB)
    variance_amount DECIMAL(15, 2),
    variance_percent DECIMAL(8, 2), -- Variance as percentage

    -- Payment documentation
    payment_document VARCHAR(100), -- Invoice/receipt number
    bank_account_id UUID REFERENCES public.bank_accounts(id), -- Which bank account

    -- Status tracking
    status VARCHAR(20) DEFAULT 'planned' CHECK (status IN ('planned', 'partial', 'completed', 'cancelled', 'overdue')),

    -- Notes
    notes TEXT,

    -- Audit
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancelled_by UUID REFERENCES auth.users(id),
    cancellation_reason TEXT
);

-- Add comment
COMMENT ON TABLE public.plan_fact_items IS 'Plan-fact items for deal payment tracking. Each item represents a planned or actual payment.';
COMMENT ON COLUMN public.plan_fact_items.variance_amount IS 'Difference between actual and planned amounts in base currency (RUB)';
COMMENT ON COLUMN public.plan_fact_items.variance_percent IS 'Variance as percentage of planned amount';
COMMENT ON COLUMN public.plan_fact_items.actual_exchange_rate IS 'Exchange rate used when actual currency differs from planned';

-- ============================================
-- INDEXES
-- ============================================

-- Fast lookup by deal
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_id ON public.plan_fact_items(deal_id);

-- Filter by category
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_category_id ON public.plan_fact_items(category_id);

-- Status filters
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_status ON public.plan_fact_items(status);

-- Date-based queries
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_planned_date ON public.plan_fact_items(planned_date);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_actual_date ON public.plan_fact_items(actual_date);

-- Overdue items (planned but not paid past date)
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_overdue
ON public.plan_fact_items(planned_date, status)
WHERE status = 'planned' AND planned_date < CURRENT_DATE;

-- ============================================
-- TRIGGER: Auto-update timestamps
-- ============================================

CREATE OR REPLACE FUNCTION public.plan_fact_items_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_plan_fact_items_update_timestamp ON public.plan_fact_items;
CREATE TRIGGER tr_plan_fact_items_update_timestamp
    BEFORE UPDATE ON public.plan_fact_items
    FOR EACH ROW EXECUTE FUNCTION public.plan_fact_items_update_timestamp();

-- ============================================
-- TRIGGER: Auto-calculate variance
-- ============================================

CREATE OR REPLACE FUNCTION public.plan_fact_items_calculate_variance()
RETURNS TRIGGER AS $$
DECLARE
    v_actual_in_rub DECIMAL(15, 2);
    v_planned_in_rub DECIMAL(15, 2);
BEGIN
    -- Only calculate if both planned and actual are set
    IF NEW.actual_amount IS NOT NULL AND NEW.planned_amount IS NOT NULL THEN
        -- Convert actual to RUB if exchange rate provided
        IF NEW.actual_exchange_rate IS NOT NULL AND NEW.actual_exchange_rate > 0 THEN
            v_actual_in_rub := NEW.actual_amount * NEW.actual_exchange_rate;
        ELSE
            v_actual_in_rub := NEW.actual_amount;
        END IF;

        -- Planned is assumed to be in RUB or converted
        v_planned_in_rub := NEW.planned_amount;

        -- Calculate variance (positive = overpaid/over-received, negative = underpaid/under-received)
        NEW.variance_amount := v_actual_in_rub - v_planned_in_rub;

        -- Calculate variance percentage
        IF v_planned_in_rub > 0 THEN
            NEW.variance_percent := ((v_actual_in_rub - v_planned_in_rub) / v_planned_in_rub) * 100;
        ELSE
            NEW.variance_percent := NULL;
        END IF;

        -- Auto-update status to completed if actual date is set
        IF NEW.actual_date IS NOT NULL AND NEW.status = 'planned' THEN
            NEW.status := 'completed';
            NEW.completed_at := NOW();
        END IF;
    ELSE
        NEW.variance_amount := NULL;
        NEW.variance_percent := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_plan_fact_items_calculate_variance ON public.plan_fact_items;
CREATE TRIGGER tr_plan_fact_items_calculate_variance
    BEFORE INSERT OR UPDATE ON public.plan_fact_items
    FOR EACH ROW EXECUTE FUNCTION public.plan_fact_items_calculate_variance();

-- ============================================
-- TRIGGER: Auto-mark overdue items
-- ============================================

CREATE OR REPLACE FUNCTION public.plan_fact_items_check_overdue()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark as overdue if planned date passed and still in planned status
    IF NEW.status = 'planned' AND NEW.planned_date < CURRENT_DATE AND NEW.actual_amount IS NULL THEN
        NEW.status := 'overdue';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_plan_fact_items_check_overdue ON public.plan_fact_items;
CREATE TRIGGER tr_plan_fact_items_check_overdue
    BEFORE UPDATE ON public.plan_fact_items
    FOR EACH ROW EXECUTE FUNCTION public.plan_fact_items_check_overdue();

-- ============================================
-- RLS POLICIES
-- ============================================

ALTER TABLE public.plan_fact_items ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view items for deals in their organization
CREATE POLICY plan_fact_items_select_policy ON public.plan_fact_items
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.deals d
            JOIN public.quotes q ON d.quote_id = q.id
            WHERE d.id = plan_fact_items.deal_id
            AND q.organization_id = (auth.jwt() -> 'app_metadata' ->> 'organization_id')::UUID
        )
    );

-- Policy: Users can insert items for deals in their organization
CREATE POLICY plan_fact_items_insert_policy ON public.plan_fact_items
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.deals d
            JOIN public.quotes q ON d.quote_id = q.id
            WHERE d.id = plan_fact_items.deal_id
            AND q.organization_id = (auth.jwt() -> 'app_metadata' ->> 'organization_id')::UUID
        )
    );

-- Policy: Users can update items for deals in their organization
CREATE POLICY plan_fact_items_update_policy ON public.plan_fact_items
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.deals d
            JOIN public.quotes q ON d.quote_id = q.id
            WHERE d.id = plan_fact_items.deal_id
            AND q.organization_id = (auth.jwt() -> 'app_metadata' ->> 'organization_id')::UUID
        )
    );

-- Policy: Users can delete items for deals in their organization
CREATE POLICY plan_fact_items_delete_policy ON public.plan_fact_items
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM public.deals d
            JOIN public.quotes q ON d.quote_id = q.id
            WHERE d.id = plan_fact_items.deal_id
            AND q.organization_id = (auth.jwt() -> 'app_metadata' ->> 'organization_id')::UUID
        )
    );

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Create planned item from deal terms
CREATE OR REPLACE FUNCTION public.create_plan_fact_item(
    p_deal_id UUID,
    p_category_code VARCHAR(50),
    p_description VARCHAR(255),
    p_planned_amount DECIMAL(15, 2),
    p_planned_currency VARCHAR(3) DEFAULT 'RUB',
    p_planned_date DATE DEFAULT NULL,
    p_created_by UUID DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_category_id UUID;
    v_item_id UUID;
BEGIN
    -- Get category ID
    SELECT id INTO v_category_id
    FROM public.plan_fact_categories
    WHERE code = p_category_code AND is_active = TRUE;

    IF v_category_id IS NULL THEN
        RAISE EXCEPTION 'Invalid plan_fact category code: %', p_category_code;
    END IF;

    -- Create the item
    INSERT INTO public.plan_fact_items (
        deal_id,
        category_id,
        description,
        planned_amount,
        planned_currency,
        planned_date,
        created_by
    )
    VALUES (
        p_deal_id,
        v_category_id,
        p_description,
        p_planned_amount,
        p_planned_currency,
        p_planned_date,
        p_created_by
    )
    RETURNING id INTO v_item_id;

    RETURN v_item_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Register actual payment
CREATE OR REPLACE FUNCTION public.register_plan_fact_payment(
    p_item_id UUID,
    p_actual_amount DECIMAL(15, 2),
    p_actual_currency VARCHAR(3) DEFAULT 'RUB',
    p_actual_date DATE DEFAULT CURRENT_DATE,
    p_exchange_rate DECIMAL(10, 4) DEFAULT NULL,
    p_payment_document VARCHAR(100) DEFAULT NULL,
    p_bank_account_id UUID DEFAULT NULL,
    p_notes TEXT DEFAULT NULL,
    p_updated_by UUID DEFAULT NULL
)
RETURNS public.plan_fact_items AS $$
DECLARE
    v_result public.plan_fact_items;
BEGIN
    UPDATE public.plan_fact_items
    SET
        actual_amount = p_actual_amount,
        actual_currency = p_actual_currency,
        actual_date = p_actual_date,
        actual_exchange_rate = p_exchange_rate,
        payment_document = p_payment_document,
        bank_account_id = p_bank_account_id,
        notes = COALESCE(p_notes, notes),
        status = 'completed',
        completed_at = NOW()
    WHERE id = p_item_id
    RETURNING * INTO v_result;

    IF v_result IS NULL THEN
        RAISE EXCEPTION 'Plan-fact item not found: %', p_item_id;
    END IF;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Cancel plan-fact item
CREATE OR REPLACE FUNCTION public.cancel_plan_fact_item(
    p_item_id UUID,
    p_reason TEXT DEFAULT NULL,
    p_cancelled_by UUID DEFAULT NULL
)
RETURNS public.plan_fact_items AS $$
DECLARE
    v_result public.plan_fact_items;
BEGIN
    UPDATE public.plan_fact_items
    SET
        status = 'cancelled',
        cancelled_at = NOW(),
        cancelled_by = p_cancelled_by,
        cancellation_reason = p_reason
    WHERE id = p_item_id
    RETURNING * INTO v_result;

    IF v_result IS NULL THEN
        RAISE EXCEPTION 'Plan-fact item not found: %', p_item_id;
    END IF;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get deal plan-fact summary
CREATE OR REPLACE FUNCTION public.get_deal_plan_fact_summary(p_deal_id UUID)
RETURNS TABLE (
    total_planned_income DECIMAL(15, 2),
    total_actual_income DECIMAL(15, 2),
    total_planned_expenses DECIMAL(15, 2),
    total_actual_expenses DECIMAL(15, 2),
    planned_profit DECIMAL(15, 2),
    actual_profit DECIMAL(15, 2),
    total_variance DECIMAL(15, 2),
    items_count INTEGER,
    completed_count INTEGER,
    overdue_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(CASE WHEN c.is_income = TRUE THEN pfi.planned_amount END), 0) AS total_planned_income,
        COALESCE(SUM(CASE WHEN c.is_income = TRUE THEN pfi.actual_amount END), 0) AS total_actual_income,
        COALESCE(SUM(CASE WHEN c.is_income = FALSE THEN pfi.planned_amount END), 0) AS total_planned_expenses,
        COALESCE(SUM(CASE WHEN c.is_income = FALSE THEN pfi.actual_amount END), 0) AS total_actual_expenses,
        COALESCE(SUM(CASE WHEN c.is_income = TRUE THEN pfi.planned_amount ELSE -pfi.planned_amount END), 0) AS planned_profit,
        COALESCE(SUM(CASE WHEN c.is_income = TRUE THEN pfi.actual_amount ELSE -pfi.actual_amount END), 0) AS actual_profit,
        COALESCE(SUM(pfi.variance_amount), 0) AS total_variance,
        COUNT(*)::INTEGER AS items_count,
        COUNT(*) FILTER (WHERE pfi.status = 'completed')::INTEGER AS completed_count,
        COUNT(*) FILTER (WHERE pfi.status = 'overdue')::INTEGER AS overdue_count
    FROM public.plan_fact_items pfi
    JOIN public.plan_fact_categories c ON pfi.category_id = c.id
    WHERE pfi.deal_id = p_deal_id
    AND pfi.status != 'cancelled';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get plan-fact items with details
CREATE OR REPLACE FUNCTION public.get_plan_fact_items(
    p_deal_id UUID,
    p_status VARCHAR(20) DEFAULT NULL,
    p_category_code VARCHAR(50) DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    deal_id UUID,
    category_id UUID,
    category_code VARCHAR(50),
    category_name VARCHAR(100),
    category_name_ru VARCHAR(100),
    is_income BOOLEAN,
    description VARCHAR(255),
    planned_amount DECIMAL(15, 2),
    planned_currency VARCHAR(3),
    planned_date DATE,
    actual_amount DECIMAL(15, 2),
    actual_currency VARCHAR(3),
    actual_date DATE,
    actual_exchange_rate DECIMAL(10, 4),
    variance_amount DECIMAL(15, 2),
    variance_percent DECIMAL(8, 2),
    payment_document VARCHAR(100),
    status VARCHAR(20),
    notes TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pfi.id,
        pfi.deal_id,
        pfi.category_id,
        c.code AS category_code,
        c.name AS category_name,
        c.name_ru AS category_name_ru,
        c.is_income,
        pfi.description,
        pfi.planned_amount,
        pfi.planned_currency,
        pfi.planned_date,
        pfi.actual_amount,
        pfi.actual_currency,
        pfi.actual_date,
        pfi.actual_exchange_rate,
        pfi.variance_amount,
        pfi.variance_percent,
        pfi.payment_document,
        pfi.status,
        pfi.notes,
        pfi.created_at
    FROM public.plan_fact_items pfi
    JOIN public.plan_fact_categories c ON pfi.category_id = c.id
    WHERE pfi.deal_id = p_deal_id
    AND (p_status IS NULL OR pfi.status = p_status)
    AND (p_category_code IS NULL OR c.code = p_category_code)
    ORDER BY c.display_order, pfi.planned_date NULLS LAST, pfi.created_at;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Auto-generate plan-fact items from deal
CREATE OR REPLACE FUNCTION public.generate_plan_fact_from_deal(
    p_deal_id UUID,
    p_created_by UUID DEFAULT NULL
)
RETURNS INTEGER AS $$
DECLARE
    v_deal RECORD;
    v_quote RECORD;
    v_count INTEGER := 0;
BEGIN
    -- Get deal details
    SELECT d.*, s.total_amount, s.currency
    INTO v_deal
    FROM public.deals d
    LEFT JOIN public.specifications s ON d.specification_id = s.id
    WHERE d.id = p_deal_id;

    IF v_deal IS NULL THEN
        RAISE EXCEPTION 'Deal not found: %', p_deal_id;
    END IF;

    -- Get quote details for calculation
    SELECT q.*
    INTO v_quote
    FROM public.quotes q
    WHERE q.id = v_deal.quote_id;

    -- Create client payment item (income)
    IF v_deal.total_amount IS NOT NULL AND v_deal.total_amount > 0 THEN
        PERFORM public.create_plan_fact_item(
            p_deal_id,
            'client_payment',
            'Full payment from client',
            v_deal.total_amount,
            COALESCE(v_deal.currency, 'RUB'),
            NULL,
            p_created_by
        );
        v_count := v_count + 1;
    END IF;

    -- TODO: Add more items based on quote breakdown when calculation_engine fields are available:
    -- - supplier_payment (from quote_items.fob_price * quantity)
    -- - logistics_cost (from quote_items.logistics_* fields)
    -- - customs_cost (from quote_items.customs_* fields)

    RETURN v_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Mark overdue items batch (for scheduled job)
CREATE OR REPLACE FUNCTION public.mark_plan_fact_items_overdue()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE public.plan_fact_items
    SET status = 'overdue'
    WHERE status = 'planned'
    AND planned_date < CURRENT_DATE
    AND actual_amount IS NULL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- VIEW: Plan-fact items with full context
-- ============================================

CREATE OR REPLACE VIEW public.v_plan_fact_items_full AS
SELECT
    pfi.*,
    c.code AS category_code,
    c.name AS category_name,
    c.name_ru AS category_name_ru,
    c.is_income,
    d.deal_number,
    d.status AS deal_status,
    q.name AS quote_name,
    q.idn AS quote_idn,
    cust.name AS customer_name
FROM public.plan_fact_items pfi
JOIN public.plan_fact_categories c ON pfi.category_id = c.id
JOIN public.deals d ON pfi.deal_id = d.id
JOIN public.quotes q ON d.quote_id = q.id
LEFT JOIN public.customers cust ON q.customer_id = cust.id
ORDER BY d.deal_number, c.display_order, pfi.planned_date NULLS LAST;

COMMENT ON VIEW public.v_plan_fact_items_full IS 'Plan-fact items with category, deal, quote, and customer context';

-- Grant permissions
GRANT SELECT ON public.v_plan_fact_items_full TO authenticated;

-- ============================================
-- SUMMARY
-- ============================================

-- This migration creates:
-- 1. plan_fact_items table with:
--    - deal_id and category_id foreign keys
--    - Planned values (amount, currency, date)
--    - Actual values (amount, currency, date, exchange_rate)
--    - Auto-calculated variance (amount and percent)
--    - Status tracking (planned/partial/completed/cancelled/overdue)
--    - Payment documentation fields
--
-- 2. Triggers:
--    - Auto-update timestamp
--    - Auto-calculate variance when actual is set
--    - Auto-check overdue status
--
-- 3. RLS policies for organization isolation
--
-- 4. Helper functions:
--    - create_plan_fact_item() - Create new planned item
--    - register_plan_fact_payment() - Register actual payment
--    - cancel_plan_fact_item() - Cancel an item
--    - get_deal_plan_fact_summary() - Dashboard summary for deal
--    - get_plan_fact_items() - List items with filters
--    - generate_plan_fact_from_deal() - Auto-generate items from deal
--    - mark_plan_fact_items_overdue() - Batch mark overdue items
--
-- 5. View: v_plan_fact_items_full with full context
