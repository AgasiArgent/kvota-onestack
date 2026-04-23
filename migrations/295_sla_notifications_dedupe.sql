-- Migration 295: SLA notification dedupe table
-- Task 12 of logistics-customs-redesign spec.
--
-- Purpose:
--   /api/cron/sla-check runs every ~10 minutes and scans invoices with
--   logistics/customs deadlines. For each (invoice_id, kind) pair we must
--   send at most ONE Telegram notification. The UNIQUE constraint on
--   (invoice_id, kind) makes dedupe a natural side-effect of INSERT:
--   a duplicate INSERT raises unique_violation, the handler swallows it
--   and skips sending.
--
-- Kinds (stable strings — code matches on these literals):
--   - logistics_reminder : reminder at deadline - 24h (sent once)
--   - logistics_overdue  : head-of-logistics ping at/after deadline (sent once)
--   - customs_reminder   : symmetric for customs
--   - customs_overdue    : symmetric for customs
--
-- Requirements: R4.2 (reminder at deadline-24h), R4.3 (overdue notification).

CREATE TABLE IF NOT EXISTS kvota.invoice_sla_notifications_sent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN (
        'logistics_reminder',
        'logistics_overdue',
        'customs_reminder',
        'customs_overdue'
    )),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (invoice_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_invoice_sla_notif_invoice
    ON kvota.invoice_sla_notifications_sent(invoice_id);

COMMENT ON TABLE kvota.invoice_sla_notifications_sent IS
    'Dedupe ledger for /api/cron/sla-check. UNIQUE(invoice_id, kind) guarantees one notification per (invoice, kind). Rows are never updated; to resend, delete the row.';

-- Record migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (295, '295_sla_notifications_dedupe', now())
ON CONFLICT (id) DO NOTHING;
