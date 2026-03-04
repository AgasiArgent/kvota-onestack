-- Migration 202: Extend currency_invoices for contract/bank/terms enrichment
-- Adds snapshot fields for bank account, contract, payment terms, and delivery terms.
-- These are auto-filled at generation time and overridable by controller.

-- =============================================================
-- Add new columns to currency_invoices
-- =============================================================

-- Bank account used for this invoice (auto-picked by currency, overridable)
ALTER TABLE kvota.currency_invoices
ADD COLUMN IF NOT EXISTS seller_bank_account_id UUID REFERENCES kvota.bank_accounts(id);

-- Contract snapshot (copied from currency_contracts at generation/save time, overridable)
ALTER TABLE kvota.currency_invoices
ADD COLUMN IF NOT EXISTS contract_number TEXT;

ALTER TABLE kvota.currency_invoices
ADD COLUMN IF NOT EXISTS contract_date DATE;

-- Payment terms text (template constant, overridable per invoice)
ALTER TABLE kvota.currency_invoices
ADD COLUMN IF NOT EXISTS payment_terms TEXT;

-- Delivery terms text (TRRU only, NULL for EURTR)
ALTER TABLE kvota.currency_invoices
ADD COLUMN IF NOT EXISTS delivery_terms TEXT;

-- =============================================================
-- Indexes
-- =============================================================

CREATE INDEX IF NOT EXISTS idx_currency_invoices_bank_account
ON kvota.currency_invoices(seller_bank_account_id)
WHERE seller_bank_account_id IS NOT NULL;

-- =============================================================
-- Comments
-- =============================================================

COMMENT ON COLUMN kvota.currency_invoices.seller_bank_account_id IS 'Bank account for DOCX export. Auto-picked by currency, overridable by controller.';
COMMENT ON COLUMN kvota.currency_invoices.contract_number IS 'Snapshot of contract number from currency_contracts. Overridable by controller.';
COMMENT ON COLUMN kvota.currency_invoices.contract_date IS 'Snapshot of contract date. Overridable by controller.';
COMMENT ON COLUMN kvota.currency_invoices.payment_terms IS 'Payment terms text for DOCX export. Template constant, overridable per invoice.';
COMMENT ON COLUMN kvota.currency_invoices.delivery_terms IS 'Delivery terms text for DOCX export. TRRU only (NULL for EURTR). Overridable.';

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (202, '202_extend_currency_invoices_for_enrichment.sql', now())
ON CONFLICT (id) DO NOTHING;
