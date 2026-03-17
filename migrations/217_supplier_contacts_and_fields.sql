-- Migration: 217_supplier_contacts_and_fields
-- Description: Create supplier_contacts table, add registration_number, relax supplier_code constraint
-- Date: 2026-03-17

-- 1. Add registration_number to suppliers (generic VAT/tax ID for international suppliers)
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS registration_number VARCHAR(50);
COMMENT ON COLUMN suppliers.registration_number IS 'Generic registration/VAT/tax number for international suppliers';

-- 2. Relax supplier_code: make nullable and extend length
ALTER TABLE suppliers ALTER COLUMN supplier_code DROP NOT NULL;
ALTER TABLE suppliers ALTER COLUMN supplier_code TYPE VARCHAR(20);

-- 3. Create supplier_contacts table (mirrors customer_contacts pattern)
CREATE TABLE IF NOT EXISTS supplier_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    position VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

CREATE INDEX IF NOT EXISTS idx_supplier_contacts_supplier_id ON supplier_contacts(supplier_id);
CREATE INDEX IF NOT EXISTS idx_supplier_contacts_org_id ON supplier_contacts(organization_id);

-- 4. Migrate existing flat contact fields into supplier_contacts
-- Only migrate if contact_person is not null/empty
INSERT INTO supplier_contacts (supplier_id, organization_id, name, email, phone, is_primary, created_by)
SELECT
    s.id,
    s.organization_id,
    s.contact_person,
    NULLIF(s.contact_email, ''),
    NULLIF(s.contact_phone, ''),
    TRUE,
    s.created_by
FROM suppliers s
WHERE s.contact_person IS NOT NULL AND s.contact_person != ''
ON CONFLICT DO NOTHING;

-- 5. Enable RLS
ALTER TABLE supplier_contacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY supplier_contacts_select ON supplier_contacts
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM user_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY supplier_contacts_insert ON supplier_contacts
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM user_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY supplier_contacts_update ON supplier_contacts
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id FROM user_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY supplier_contacts_delete ON supplier_contacts
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id FROM user_profiles WHERE user_id = auth.uid()
        )
    );
