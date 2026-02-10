-- Migration 160: Fix specifications schema - ensure columns exist in kvota schema
-- Created: 2026-02-10
--
-- Root cause: Migration 036 created contract_id, delivery_days, delivery_days_type
-- in the wrong schema (public schema instead of kvota.specifications).
-- The information_schema.columns check in 036 did not filter by table_schema = 'kvota',
-- so columns were created in public schema by default.
-- PostgREST silently drops unknown columns on INSERT, causing data loss.
--
-- This migration idempotently ensures all affected columns exist in kvota.specifications.

-- =====================================================
-- WARN IF COLUMNS EXIST IN WRONG SCHEMA (public)
-- =====================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'specifications'
          AND column_name = 'contract_id'
    ) THEN
        RAISE WARNING 'contract_id found in public schema specifications table (wrong schema) -- migration 036 bug confirmed';
    END IF;
END
$$;

-- =====================================================
-- ENSURE contract_id IN kvota.specifications
-- =====================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota'
          AND table_name = 'specifications'
          AND column_name = 'contract_id'
    ) THEN
        ALTER TABLE kvota.specifications
        ADD COLUMN contract_id UUID REFERENCES kvota.customer_contracts(id) ON DELETE SET NULL;
    END IF;
END
$$;

COMMENT ON COLUMN kvota.specifications.contract_id IS 'Customer contract for specification numbering sequence (fixed by migration 160)';

-- =====================================================
-- ENSURE delivery_days IN kvota.specifications
-- =====================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota'
          AND table_name = 'specifications'
          AND column_name = 'delivery_days'
    ) THEN
        ALTER TABLE kvota.specifications
        ADD COLUMN delivery_days INTEGER;
    END IF;
END
$$;

COMMENT ON COLUMN kvota.specifications.delivery_days IS 'Delivery days for specification (pre-filled from calc_variables.delivery_time)';

-- =====================================================
-- ENSURE delivery_days_type IN kvota.specifications
-- =====================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota'
          AND table_name = 'specifications'
          AND column_name = 'delivery_days_type'
    ) THEN
        ALTER TABLE kvota.specifications
        ADD COLUMN delivery_days_type VARCHAR(50) DEFAULT 'рабочих дней';
    END IF;
END
$$;

COMMENT ON COLUMN kvota.specifications.delivery_days_type IS 'Type of delivery days: working days or calendar days';

-- =====================================================
-- INDEX ON contract_id (idempotent)
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_kvota_specifications_contract_id
ON kvota.specifications(contract_id);
