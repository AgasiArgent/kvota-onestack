-- Migration 189: Create calls table (Журнал звонков)

CREATE TABLE IF NOT EXISTS kvota.calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES kvota.customers(id) ON DELETE CASCADE,
    contact_person_id UUID REFERENCES kvota.customer_contacts(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,  -- МОП

    -- Call type & category
    call_type VARCHAR(20) NOT NULL DEFAULT 'call'
        CHECK (call_type IN ('call', 'scheduled')),
    call_category VARCHAR(20)
        CHECK (call_category IN ('cold', 'warm', 'incoming')),

    -- Scheduling
    scheduled_date TIMESTAMP WITH TIME ZONE,

    -- Content fields
    comment TEXT,           -- Общий комментарий / Суть звонка
    customer_needs TEXT,    -- Потребление клиента / Зона ответственности контакта
    meeting_notes TEXT,     -- Назначение встречи

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION kvota.update_calls_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calls_updated_at_trigger
    BEFORE UPDATE ON kvota.calls
    FOR EACH ROW EXECUTE FUNCTION kvota.update_calls_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_calls_customer_id ON kvota.calls(customer_id);
CREATE INDEX IF NOT EXISTS idx_calls_user_id ON kvota.calls(user_id);
CREATE INDEX IF NOT EXISTS idx_calls_organization_id ON kvota.calls(organization_id);
CREATE INDEX IF NOT EXISTS idx_calls_call_type ON kvota.calls(call_type);
CREATE INDEX IF NOT EXISTS idx_calls_scheduled_date ON kvota.calls(scheduled_date)
    WHERE call_type = 'scheduled';
CREATE INDEX IF NOT EXISTS idx_calls_created_at ON kvota.calls(created_at DESC);

-- RLS
ALTER TABLE kvota.calls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "calls_select_policy" ON kvota.calls
    FOR SELECT TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

CREATE POLICY "calls_insert_policy" ON kvota.calls
    FOR INSERT TO authenticated
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

CREATE POLICY "calls_update_policy" ON kvota.calls
    FOR UPDATE TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

CREATE POLICY "calls_delete_policy" ON kvota.calls
    FOR DELETE TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

COMMENT ON TABLE kvota.calls IS 'Calls journal - phone calls and scheduled meetings with customer contacts';
