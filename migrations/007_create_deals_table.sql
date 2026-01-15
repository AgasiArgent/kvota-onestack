-- Migration: 007_create_deals_table.sql
-- Description: Create deals table for tracking signed specifications
-- Feature #7 from features.json
-- Created: 2025-01-15

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create deals table
-- Deals are created when a specification is signed by the client
CREATE TABLE IF NOT EXISTS public.deals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign key references
    specification_id UUID NOT NULL REFERENCES public.specifications(id) ON DELETE RESTRICT,
    quote_id UUID NOT NULL REFERENCES public.quotes(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,

    -- Deal identification
    deal_number VARCHAR(100) NOT NULL,

    -- Signing info
    signed_at DATE NOT NULL,

    -- Financial details
    total_amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',

    -- Status tracking
    -- active: deal is in progress, payments being tracked
    -- completed: all payments made, deal closed successfully
    -- cancelled: deal was cancelled (rare case)
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),

    -- Audit fields
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add comments
COMMENT ON TABLE public.deals IS 'Сделки - подписанные спецификации с финансовым учётом';
COMMENT ON COLUMN public.deals.specification_id IS 'Ссылка на спецификацию, из которой создана сделка';
COMMENT ON COLUMN public.deals.quote_id IS 'Ссылка на оригинальное КП';
COMMENT ON COLUMN public.deals.organization_id IS 'Организация, которой принадлежит сделка';
COMMENT ON COLUMN public.deals.deal_number IS 'Номер сделки (human-readable идентификатор)';
COMMENT ON COLUMN public.deals.signed_at IS 'Дата подписания спецификации клиентом';
COMMENT ON COLUMN public.deals.total_amount IS 'Общая сумма сделки в валюте сделки';
COMMENT ON COLUMN public.deals.currency IS 'Валюта сделки (RUB, USD, EUR, CNY)';
COMMENT ON COLUMN public.deals.status IS 'Статус: active=в работе, completed=завершена, cancelled=отменена';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_deals_specification_id ON public.deals(specification_id);
CREATE INDEX IF NOT EXISTS idx_deals_quote_id ON public.deals(quote_id);
CREATE INDEX IF NOT EXISTS idx_deals_organization_id ON public.deals(organization_id);
CREATE INDEX IF NOT EXISTS idx_deals_status ON public.deals(status);
CREATE INDEX IF NOT EXISTS idx_deals_signed_at ON public.deals(signed_at DESC);
CREATE INDEX IF NOT EXISTS idx_deals_deal_number ON public.deals(deal_number);
CREATE INDEX IF NOT EXISTS idx_deals_created_at ON public.deals(created_at DESC);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_deals_org_status ON public.deals(organization_id, status);

-- Unique constraint: one deal per specification
CREATE UNIQUE INDEX IF NOT EXISTS idx_deals_unique_specification ON public.deals(specification_id);

-- Enable Row Level Security
ALTER TABLE public.deals ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Users can view deals in their organization
CREATE POLICY "Users can view deals in their organization"
    ON public.deals
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM public.organization_members
            WHERE user_id = auth.uid()
        )
    );

-- Users can create deals in their organization (spec_controller or admin role)
CREATE POLICY "Authorized users can create deals"
    ON public.deals
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.organization_members
            WHERE user_id = auth.uid()
        )
        AND (
            -- User must have spec_controller or admin role
            EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = public.deals.organization_id
                AND r.code IN ('spec_controller', 'admin')
            )
        )
    );

-- Finance users and admins can update deals
CREATE POLICY "Finance users can update deals"
    ON public.deals
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.organization_members
            WHERE user_id = auth.uid()
        )
        AND (
            EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = public.deals.organization_id
                AND r.code IN ('finance', 'admin')
            )
        )
    );

-- Only admins can delete deals (should be rare)
CREATE POLICY "Only admins can delete deals"
    ON public.deals
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM public.user_roles ur
            JOIN public.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = public.deals.organization_id
            AND r.code = 'admin'
        )
    );

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_deals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_deals_updated_at
    BEFORE UPDATE ON public.deals
    FOR EACH ROW
    EXECUTE FUNCTION public.update_deals_updated_at();

-- Function to generate deal number (e.g., DEAL-2025-001)
CREATE OR REPLACE FUNCTION public.generate_deal_number(org_id UUID)
RETURNS TEXT AS $$
DECLARE
    year_prefix TEXT;
    seq_num INT;
    deal_num TEXT;
BEGIN
    year_prefix := TO_CHAR(CURRENT_DATE, 'YYYY');

    -- Count existing deals for this org in current year
    SELECT COUNT(*) + 1 INTO seq_num
    FROM public.deals
    WHERE organization_id = org_id
    AND EXTRACT(YEAR FROM signed_at) = EXTRACT(YEAR FROM CURRENT_DATE);

    deal_num := 'DEAL-' || year_prefix || '-' || LPAD(seq_num::TEXT, 4, '0');

    RETURN deal_num;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.generate_deal_number IS 'Генерирует номер сделки в формате DEAL-YYYY-NNNN';
