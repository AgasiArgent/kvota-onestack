-- Migration 190: Deal logistics expenses tracking
-- Feature [86aftzex6]: Трекинг фактических расходов на логистику по сделкам

CREATE TABLE IF NOT EXISTS kvota.deal_logistics_expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parent references
    deal_id UUID NOT NULL REFERENCES kvota.deals(id) ON DELETE CASCADE,
    logistics_stage_id UUID NOT NULL REFERENCES kvota.logistics_stages(id) ON DELETE CASCADE,

    -- Expense classification
    -- Subtypes: transport, storage, handling, customs_fee, insurance, other
    expense_subtype VARCHAR(30) NOT NULL DEFAULT 'transport'
        CHECK (expense_subtype IN ('transport', 'storage', 'handling', 'customs_fee', 'insurance', 'other')),

    -- Amount
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD'
        CHECK (currency IN ('USD', 'EUR', 'RUB', 'CNY', 'TRY')),

    -- Dates
    expense_date DATE NOT NULL,           -- actual expense date (user-entered)
    created_at TIMESTAMPTZ DEFAULT NOW(), -- system entry date

    -- Description / reference
    description VARCHAR(500),

    -- File attachment (optional, links to kvota.documents)
    document_id UUID REFERENCES kvota.documents(id) ON DELETE SET NULL,

    -- Audit
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_deal_logistics_expenses_deal_id
    ON kvota.deal_logistics_expenses(deal_id);
CREATE INDEX IF NOT EXISTS idx_deal_logistics_expenses_stage_id
    ON kvota.deal_logistics_expenses(logistics_stage_id);
CREATE INDEX IF NOT EXISTS idx_deal_logistics_expenses_expense_date
    ON kvota.deal_logistics_expenses(expense_date DESC);

-- RLS
ALTER TABLE kvota.deal_logistics_expenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "deal_logistics_expenses_select" ON kvota.deal_logistics_expenses
    FOR SELECT TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

CREATE POLICY "deal_logistics_expenses_insert" ON kvota.deal_logistics_expenses
    FOR INSERT TO authenticated
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

CREATE POLICY "deal_logistics_expenses_delete" ON kvota.deal_logistics_expenses
    FOR DELETE TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

COMMENT ON TABLE kvota.deal_logistics_expenses IS
    'Actual logistics expense records per deal per stage. Filled by financier after deal creation. Sum feeds into plan_fact_items for logistics categories.';
