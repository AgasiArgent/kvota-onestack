-- Migration: 009_create_plan_fact_items_table.sql
-- Description: Create plan_fact_items table for tracking planned vs actual payments
-- Feature #9 from features.json
-- Created: 2025-01-15

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create plan_fact_items table
-- Stores both planned and actual payment records for financial tracking
CREATE TABLE IF NOT EXISTS public.plan_fact_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign key references
    deal_id UUID NOT NULL REFERENCES public.deals(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES public.plan_fact_categories(id) ON DELETE RESTRICT,

    -- Description of the payment
    description TEXT,

    -- Planned payment info
    planned_amount DECIMAL(15, 2) NOT NULL,
    planned_currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    planned_date DATE NOT NULL,

    -- Actual payment info (null if not yet paid)
    actual_amount DECIMAL(15, 2),
    actual_currency VARCHAR(10),
    actual_date DATE,
    actual_exchange_rate DECIMAL(15, 6),  -- Exchange rate to RUB at payment date

    -- Variance tracking (calculated: actual_amount_in_rub - planned_amount_in_rub)
    variance_amount DECIMAL(15, 2),

    -- Payment documentation
    payment_document VARCHAR(255),  -- Payment document number/reference
    notes TEXT,

    -- Audit fields
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add comments
COMMENT ON TABLE public.plan_fact_items IS 'Записи план-факта - плановые и фактические платежи по сделкам';
COMMENT ON COLUMN public.plan_fact_items.deal_id IS 'Ссылка на сделку';
COMMENT ON COLUMN public.plan_fact_items.category_id IS 'Категория платежа (оплата от клиента, поставщику, логистика и т.д.)';
COMMENT ON COLUMN public.plan_fact_items.description IS 'Описание платежа';
COMMENT ON COLUMN public.plan_fact_items.planned_amount IS 'Плановая сумма платежа';
COMMENT ON COLUMN public.plan_fact_items.planned_currency IS 'Валюта планового платежа';
COMMENT ON COLUMN public.plan_fact_items.planned_date IS 'Плановая дата платежа';
COMMENT ON COLUMN public.plan_fact_items.actual_amount IS 'Фактическая сумма платежа (NULL если не оплачено)';
COMMENT ON COLUMN public.plan_fact_items.actual_currency IS 'Валюта фактического платежа';
COMMENT ON COLUMN public.plan_fact_items.actual_date IS 'Фактическая дата платежа';
COMMENT ON COLUMN public.plan_fact_items.actual_exchange_rate IS 'Курс валюты к рублю на дату платежа';
COMMENT ON COLUMN public.plan_fact_items.variance_amount IS 'Отклонение в рублях (факт - план)';
COMMENT ON COLUMN public.plan_fact_items.payment_document IS 'Номер платёжного документа';
COMMENT ON COLUMN public.plan_fact_items.notes IS 'Дополнительные заметки';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_id ON public.plan_fact_items(deal_id);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_category_id ON public.plan_fact_items(category_id);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_planned_date ON public.plan_fact_items(planned_date);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_actual_date ON public.plan_fact_items(actual_date);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_created_at ON public.plan_fact_items(created_at DESC);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_category ON public.plan_fact_items(deal_id, category_id);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_planned_date ON public.plan_fact_items(deal_id, planned_date);

-- Index for finding unpaid items (actual_amount IS NULL)
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_unpaid ON public.plan_fact_items(deal_id) WHERE actual_amount IS NULL;

-- Enable Row Level Security
ALTER TABLE public.plan_fact_items ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Users can view plan_fact_items for deals in their organization
CREATE POLICY "Users can view plan_fact_items in their organization"
    ON public.plan_fact_items
    FOR SELECT
    USING (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE d.organization_id IN (
                SELECT organization_id FROM public.organization_members
                WHERE user_id = auth.uid()
            )
        )
    );

-- Finance users and admins can create plan_fact_items
CREATE POLICY "Finance users can create plan_fact_items"
    ON public.plan_fact_items
    FOR INSERT
    WITH CHECK (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE d.organization_id IN (
                SELECT om.organization_id FROM public.organization_members om
                WHERE om.user_id = auth.uid()
            )
            AND EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = d.organization_id
                AND r.code IN ('finance', 'admin')
            )
        )
    );

-- Finance users and admins can update plan_fact_items
CREATE POLICY "Finance users can update plan_fact_items"
    ON public.plan_fact_items
    FOR UPDATE
    USING (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE d.organization_id IN (
                SELECT om.organization_id FROM public.organization_members om
                WHERE om.user_id = auth.uid()
            )
            AND EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = d.organization_id
                AND r.code IN ('finance', 'admin')
            )
        )
    );

-- Only admins can delete plan_fact_items
CREATE POLICY "Only admins can delete plan_fact_items"
    ON public.plan_fact_items
    FOR DELETE
    USING (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = d.organization_id
                AND r.code = 'admin'
            )
        )
    );

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_plan_fact_items_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_plan_fact_items_updated_at
    BEFORE UPDATE ON public.plan_fact_items
    FOR EACH ROW
    EXECUTE FUNCTION public.update_plan_fact_items_updated_at();

-- Function to calculate variance when actual payment is recorded
-- Variance = (actual_amount * actual_exchange_rate) - (planned_amount * planned_exchange_rate)
-- Assumes planned amounts are already in RUB or have implicit exchange rate of 1
CREATE OR REPLACE FUNCTION public.calculate_plan_fact_variance()
RETURNS TRIGGER AS $$
BEGIN
    -- Only calculate when actual payment is being recorded
    IF NEW.actual_amount IS NOT NULL AND NEW.actual_date IS NOT NULL THEN
        -- If actual currency is RUB, no conversion needed
        IF NEW.actual_currency = 'RUB' OR NEW.actual_currency IS NULL THEN
            NEW.variance_amount := NEW.actual_amount - NEW.planned_amount;
        ELSE
            -- Convert actual to RUB using exchange rate, compare to planned
            IF NEW.actual_exchange_rate IS NOT NULL AND NEW.actual_exchange_rate > 0 THEN
                NEW.variance_amount := (NEW.actual_amount * NEW.actual_exchange_rate) - NEW.planned_amount;
            ELSE
                -- No exchange rate provided, assume same currency
                NEW.variance_amount := NEW.actual_amount - NEW.planned_amount;
            END IF;
        END IF;
    ELSE
        NEW.variance_amount := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_calculate_variance
    BEFORE INSERT OR UPDATE ON public.plan_fact_items
    FOR EACH ROW
    EXECUTE FUNCTION public.calculate_plan_fact_variance();

COMMENT ON FUNCTION public.calculate_plan_fact_variance IS 'Автоматически вычисляет отклонение при регистрации фактического платежа';
