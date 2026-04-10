-- migrations/264_composition_pointer_and_verification.sql
-- Phase 5b Task 2: Composition pointer on quote_items + verification state on invoices.
--
-- This migration is additive-only — it adds 3 nullable columns across 2 tables,
-- 2 partial indexes, and 3 column comments. No existing data is modified and
-- no existing queries are affected. Backfill happens in migration 265.
--
-- Columns added:
--
--   kvota.quote_items.composition_selected_invoice_id (UUID, nullable)
--     The active composition pointer. NULL = fall back to legacy quote_items.invoice_id.
--     NOT NULL = use this invoice's row in invoice_item_prices for calculation.
--     ON DELETE SET NULL — if the referenced invoice is deleted, the pointer
--     clears and composition_service falls back to the legacy path.
--
--   kvota.invoices.verified_at (TIMESTAMPTZ, nullable)
--     When procurement marked this invoice as ready for composition. Locks
--     direct edits to price-carrying fields — subsequent edits require an
--     approved approval row via the edit-verified-invoice flow (see Task 7).
--
--   kvota.invoices.verified_by (UUID, nullable, FK auth.users)
--     Who verified this invoice.

SET search_path TO kvota, public;

-- 1) Composition pointer on quote_items
ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS composition_selected_invoice_id UUID NULL
        REFERENCES kvota.invoices(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_quote_items_composition_pointer
    ON kvota.quote_items(composition_selected_invoice_id)
    WHERE composition_selected_invoice_id IS NOT NULL;

COMMENT ON COLUMN kvota.quote_items.composition_selected_invoice_id IS
    'Phase 5b: Active composition — which invoice provides this item''s price. NULL = use legacy quote_items.invoice_id values (pre-composition quotes). Populated by migration 265 backfill for existing items, then by composition POST endpoint for new selections.';

-- 2) Verification state on invoices
ALTER TABLE kvota.invoices
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS verified_by UUID        NULL REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_invoices_verified
    ON kvota.invoices(verified_at)
    WHERE verified_at IS NOT NULL;

COMMENT ON COLUMN kvota.invoices.verified_at IS
    'Phase 5b: When procurement marked this invoice as ready for composition. NOT NULL state locks direct edits to price-carrying fields — subsequent edits require an approved approval_id via /api/invoices/{id}/edit-request flow. Backfilled in migration 265 for existing status=completed invoices.';

COMMENT ON COLUMN kvota.invoices.verified_by IS
    'Phase 5b: Who verified this invoice. FK to auth.users. NULL when verified_at is NULL.';
