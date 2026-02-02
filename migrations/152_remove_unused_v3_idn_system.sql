-- Migration: Remove unused v3.0 IDN system
-- Description: Cleans up the duplicate IDN system that was never used.
--              The active IDN system uses idn_quote column (Q-YYYYMM-NNNN format).
--              The v3.0 system (idn column, SELLER-INN-YEAR-SEQ format) was never connected.
-- Created: 2026-02-02

-- =============================================================================
-- DROP TRIGGER (must be dropped before function)
-- =============================================================================

DROP TRIGGER IF EXISTS trg_auto_generate_quote_idn ON kvota.quotes;

-- =============================================================================
-- DROP FUNCTIONS
-- =============================================================================

DROP FUNCTION IF EXISTS kvota.auto_generate_quote_idn();
DROP FUNCTION IF EXISTS kvota.generate_quote_idn(UUID, VARCHAR);

-- Also check public schema (migration might have created there)
DROP FUNCTION IF EXISTS public.auto_generate_quote_idn();
DROP FUNCTION IF EXISTS public.generate_quote_idn(UUID, VARCHAR);

-- =============================================================================
-- DROP COLUMNS
-- =============================================================================

-- Drop idn column from quotes (always empty, never used)
ALTER TABLE kvota.quotes DROP COLUMN IF EXISTS idn;

-- Drop idn_counters from organizations (always empty, never used)
ALTER TABLE kvota.organizations DROP COLUMN IF EXISTS idn_counters;

-- =============================================================================
-- CLEANUP INDEXES (if any were created)
-- =============================================================================

DROP INDEX IF EXISTS kvota.idx_quotes_idn;
DROP INDEX IF EXISTS kvota.idx_quotes_idn_unique;

-- =============================================================================
-- NOTE: Keeping these columns/tables as they ARE used:
-- - quotes.idn_quote (active IDN system, Q-YYYYMM-NNNN format)
-- - quote_items.idn_sku (active item IDN, КП25-XXXX-NNN format)
-- =============================================================================
