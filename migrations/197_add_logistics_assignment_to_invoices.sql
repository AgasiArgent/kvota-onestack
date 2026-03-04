-- Migration 197: Add assigned_logistics_user to invoices table
-- Enables per-invoice logistics manager auto-assignment based on pickup_country
-- when procurement completes. Quote-level assigned_logistics_user becomes a summary.

ALTER TABLE kvota.invoices
ADD COLUMN IF NOT EXISTS assigned_logistics_user UUID REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_invoices_assigned_logistics_user
ON kvota.invoices(assigned_logistics_user)
WHERE assigned_logistics_user IS NOT NULL;

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (197, '197_add_logistics_assignment_to_invoices', now())
ON CONFLICT (id) DO NOTHING;
