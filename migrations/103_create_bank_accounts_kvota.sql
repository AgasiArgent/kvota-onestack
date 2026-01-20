-- ===========================================================================
-- Migration 103: Create bank_accounts table in kvota schema
-- ===========================================================================
-- Description: Polymorphic bank accounts for all entity types
-- Entity types: supplier, buyer_company, seller_company, customer
-- Prerequisites: Migration 101 must be applied (tables moved to kvota schema)
-- Created: 2026-01-20
-- ===========================================================================

-- ============================================
-- Table: bank_accounts
-- Polymorphic table for bank details across all company types
-- Uses entity_type + entity_id pattern for flexibility
-- ============================================

CREATE TABLE IF NOT EXISTS kvota.bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,

    -- Polymorphic reference
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,

    -- Bank details (Russian format)
    bank_name VARCHAR(255) NOT NULL,
    account_number VARCHAR(50) NOT NULL,  -- Расчётный счёт
    bik VARCHAR(9),                         -- БИК (9 digits for Russian banks)
    correspondent_account VARCHAR(20),      -- Корреспондентский счёт (20 digits)

    -- International format
    swift VARCHAR(11),                      -- SWIFT/BIC code (8 or 11 characters)
    iban VARCHAR(34),                       -- IBAN (up to 34 characters)

    -- Currency and flags
    currency VARCHAR(3) DEFAULT 'RUB' NOT NULL,
    is_default BOOLEAN DEFAULT false NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Ensure valid entity type
    CONSTRAINT bank_accounts_entity_type_check
        CHECK (entity_type IN ('supplier', 'buyer_company', 'seller_company', 'customer'))
);

-- Comments
COMMENT ON TABLE kvota.bank_accounts IS 'Банковские реквизиты для всех типов компаний (полиморфная таблица)';
COMMENT ON COLUMN kvota.bank_accounts.entity_type IS 'Тип сущности: supplier, buyer_company, seller_company, customer';
COMMENT ON COLUMN kvota.bank_accounts.entity_id IS 'ID сущности в соответствующей таблице';
COMMENT ON COLUMN kvota.bank_accounts.bank_name IS 'Наименование банка';
COMMENT ON COLUMN kvota.bank_accounts.account_number IS 'Расчётный счёт';
COMMENT ON COLUMN kvota.bank_accounts.bik IS 'БИК банка (9 цифр, только для РФ)';
COMMENT ON COLUMN kvota.bank_accounts.correspondent_account IS 'Корреспондентский счёт (20 цифр)';
COMMENT ON COLUMN kvota.bank_accounts.swift IS 'SWIFT/BIC код для международных переводов';
COMMENT ON COLUMN kvota.bank_accounts.iban IS 'IBAN для международных переводов';
COMMENT ON COLUMN kvota.bank_accounts.currency IS 'Валюта счёта: RUB, USD, EUR, TRY, CNY, etc.';
COMMENT ON COLUMN kvota.bank_accounts.is_default IS 'Основной счёт по умолчанию для данной сущности';
COMMENT ON COLUMN kvota.bank_accounts.is_active IS 'Активный/архивный статус';

-- ============================================
-- Indexes
-- ============================================

-- Primary lookup by entity
CREATE INDEX idx_bank_accounts_entity
    ON kvota.bank_accounts(entity_type, entity_id);

-- Organization scope
CREATE INDEX idx_bank_accounts_organization
    ON kvota.bank_accounts(organization_id);

-- Find default account for entity
CREATE INDEX idx_bank_accounts_default
    ON kvota.bank_accounts(entity_type, entity_id, is_default)
    WHERE is_default = true AND is_active = true;

-- Search by currency
CREATE INDEX idx_bank_accounts_currency
    ON kvota.bank_accounts(organization_id, currency)
    WHERE is_active = true;

-- ============================================
-- RLS Policies
-- ============================================

ALTER TABLE kvota.bank_accounts ENABLE ROW LEVEL SECURITY;

-- Read policy: users can see bank accounts for their organization
CREATE POLICY bank_accounts_select_policy ON kvota.bank_accounts
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_roles
            WHERE user_id = auth.uid()
        )
    );

-- Insert policy: admins and finance can create bank accounts
CREATE POLICY bank_accounts_insert_policy ON kvota.bank_accounts
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

-- Update policy: admins and finance can modify bank accounts
CREATE POLICY bank_accounts_update_policy ON kvota.bank_accounts
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'finance')
        )
    );

-- Delete policy: only admins can delete (soft delete via is_active preferred)
CREATE POLICY bank_accounts_delete_policy ON kvota.bank_accounts
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- Auto-update trigger for updated_at
-- ============================================

CREATE OR REPLACE FUNCTION kvota.update_bank_accounts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bank_accounts_updated_at_trigger
    BEFORE UPDATE ON kvota.bank_accounts
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_bank_accounts_updated_at();

-- ============================================
-- Helper Functions
-- ============================================

-- Get default bank account for an entity
CREATE OR REPLACE FUNCTION kvota.get_default_bank_account(
    p_entity_type VARCHAR,
    p_entity_id UUID
)
RETURNS TABLE (
    id UUID,
    bank_name VARCHAR,
    account_number VARCHAR,
    bik VARCHAR,
    correspondent_account VARCHAR,
    swift VARCHAR,
    iban VARCHAR,
    currency VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ba.id,
        ba.bank_name,
        ba.account_number,
        ba.bik,
        ba.correspondent_account,
        ba.swift,
        ba.iban,
        ba.currency
    FROM kvota.bank_accounts ba
    WHERE ba.entity_type = p_entity_type
    AND ba.entity_id = p_entity_id
    AND ba.is_active = true
    AND ba.is_default = true
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kvota.get_default_bank_account IS 'Получить основной банковский счёт для сущности';

-- Get all bank accounts for an entity
CREATE OR REPLACE FUNCTION kvota.get_entity_bank_accounts(
    p_entity_type VARCHAR,
    p_entity_id UUID
)
RETURNS TABLE (
    id UUID,
    bank_name VARCHAR,
    account_number VARCHAR,
    bik VARCHAR,
    correspondent_account VARCHAR,
    swift VARCHAR,
    iban VARCHAR,
    currency VARCHAR,
    is_default BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ba.id,
        ba.bank_name,
        ba.account_number,
        ba.bik,
        ba.correspondent_account,
        ba.swift,
        ba.iban,
        ba.currency,
        ba.is_default
    FROM kvota.bank_accounts ba
    WHERE ba.entity_type = p_entity_type
    AND ba.entity_id = p_entity_id
    AND ba.is_active = true
    ORDER BY ba.is_default DESC, ba.created_at ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kvota.get_entity_bank_accounts IS 'Получить все банковские счета для сущности';

-- ============================================
-- Trigger: Ensure only one default per entity
-- ============================================

CREATE OR REPLACE FUNCTION kvota.ensure_single_default_bank_account()
RETURNS TRIGGER AS $$
BEGIN
    -- If setting this account as default, unset others
    IF NEW.is_default = true THEN
        UPDATE kvota.bank_accounts
        SET is_default = false
        WHERE entity_type = NEW.entity_type
        AND entity_id = NEW.entity_id
        AND id != NEW.id
        AND is_default = true;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bank_accounts_single_default_trigger
    BEFORE INSERT OR UPDATE OF is_default ON kvota.bank_accounts
    FOR EACH ROW
    WHEN (NEW.is_default = true)
    EXECUTE FUNCTION kvota.ensure_single_default_bank_account();

-- ============================================
-- Validation Constraints
-- ============================================

-- BIK must be 9 digits if provided
ALTER TABLE kvota.bank_accounts
    ADD CONSTRAINT bank_accounts_bik_format
    CHECK (bik IS NULL OR bik ~ '^\d{9}$');

-- Correspondent account must be 20 digits if provided
ALTER TABLE kvota.bank_accounts
    ADD CONSTRAINT bank_accounts_corr_account_format
    CHECK (correspondent_account IS NULL OR correspondent_account ~ '^\d{20}$');

-- SWIFT must be 8 or 11 alphanumeric characters
ALTER TABLE kvota.bank_accounts
    ADD CONSTRAINT bank_accounts_swift_format
    CHECK (swift IS NULL OR swift ~ '^[A-Z0-9]{8}([A-Z0-9]{3})?$');

-- IBAN basic format validation
ALTER TABLE kvota.bank_accounts
    ADD CONSTRAINT bank_accounts_iban_format
    CHECK (iban IS NULL OR iban ~ '^[A-Z]{2}[0-9]{2}[A-Z0-9]{4,30}$');

-- Currency must be 3 uppercase letters (ISO 4217)
ALTER TABLE kvota.bank_accounts
    ADD CONSTRAINT bank_accounts_currency_format
    CHECK (currency ~ '^[A-Z]{3}$');

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 103: bank_accounts table created successfully in kvota schema';
    RAISE NOTICE 'Created 3 functions: update_bank_accounts_updated_at, get_default_bank_account, get_entity_bank_accounts, ensure_single_default_bank_account';
END $$;
