-- Migration 270: Invoice Send Infrastructure
-- Adds sent_at to invoices + invoice_letter_drafts audit table
-- Phase 4a: Send Flow Backend (REQ 4, 5, 6)

-- Denormalized "last sent" timestamp for fast filtering
ALTER TABLE kvota.invoices
  ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;

-- Letter drafts table: 1:N audit trail per invoice
CREATE TABLE kvota.invoice_letter_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
  created_by UUID NOT NULL REFERENCES auth.users(id),
  language CHAR(2) NOT NULL DEFAULT 'ru' CHECK (language IN ('ru', 'en')),
  method VARCHAR(20) NOT NULL CHECK (method IN ('xls_download', 'letter_draft')),
  recipient_email TEXT,
  subject TEXT,
  body_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMPTZ NULL
);

-- At most one unsent draft per invoice
CREATE UNIQUE INDEX idx_invoice_letter_drafts_one_active
  ON kvota.invoice_letter_drafts(invoice_id) WHERE sent_at IS NULL;

-- Fast lookups by invoice
CREATE INDEX idx_invoice_letter_drafts_invoice
  ON kvota.invoice_letter_drafts(invoice_id);
