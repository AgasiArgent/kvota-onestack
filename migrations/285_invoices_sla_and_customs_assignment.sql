-- Migration 285: SLA timers + customs assignment on invoices
-- Part of Wave 1 Task 7.1 of logistics-customs-redesign spec.
--
-- Adds:
--   - assigned_customs_user UUID — who handles customs for this invoice (parallel to assigned_logistics_user from m197)
--   - logistics_assigned_at / _deadline_at / _completed_at / _sla_hours — SLA timer fields
--   - customs_assigned_at / _deadline_at / _completed_at / _sla_hours — symmetric
--   - logistics_needs_review_since / customs_needs_review_since — smart-delta review flags (m296 trigger populates)
--
-- Design references:
--   - .kiro/specs/logistics-customs-redesign/design.md §3.6 SLA timers (single-phase, no "Начать работу")
--   - .kiro/specs/logistics-customs-redesign/design.md §5.2 ALTER invoices spec
--   - .kiro/specs/logistics-customs-redesign/requirements.md R3, R4, R12
--
-- Backfill strategy: existing invoices get NULL in all new fields. `assign_customs_to_invoices`
-- will populate them when future workflow transitions fire; existing in-progress deals do not
-- retroactively acquire SLA timers (hybrid policy — see design §9.5 Option A).

ALTER TABLE kvota.invoices
    ADD COLUMN IF NOT EXISTS assigned_customs_user UUID REFERENCES auth.users(id),

    ADD COLUMN IF NOT EXISTS logistics_assigned_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS logistics_deadline_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS logistics_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS logistics_sla_hours    INT DEFAULT 72,

    ADD COLUMN IF NOT EXISTS customs_assigned_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS customs_deadline_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS customs_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS customs_sla_hours    INT DEFAULT 72,

    ADD COLUMN IF NOT EXISTS logistics_needs_review_since TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS customs_needs_review_since   TIMESTAMPTZ;

-- Comments
COMMENT ON COLUMN kvota.invoices.assigned_customs_user IS 'User (role: customs) responsible for this invoice''s customs pricing. Set by assign_customs_to_invoices() least-loaded strategy.';
COMMENT ON COLUMN kvota.invoices.logistics_assigned_at IS 'When logistics assignee was picked. Starts SLA timer.';
COMMENT ON COLUMN kvota.invoices.logistics_deadline_at IS 'logistics_assigned_at + logistics_sla_hours * interval ''1 hour''.';
COMMENT ON COLUMN kvota.invoices.logistics_completed_at IS 'When logistics pricing finished. NULL = still in work.';
COMMENT ON COLUMN kvota.invoices.logistics_sla_hours IS 'SLA target in hours. Default 72 (3 days). Per-org configurable.';
COMMENT ON COLUMN kvota.invoices.customs_assigned_at IS 'Symmetric to logistics_assigned_at for customs.';
COMMENT ON COLUMN kvota.invoices.customs_deadline_at IS 'Symmetric to logistics_deadline_at for customs.';
COMMENT ON COLUMN kvota.invoices.customs_completed_at IS 'Symmetric to logistics_completed_at for customs.';
COMMENT ON COLUMN kvota.invoices.customs_sla_hours IS 'Symmetric to logistics_sla_hours for customs.';
COMMENT ON COLUMN kvota.invoices.logistics_needs_review_since IS 'Smart-delta flag: procurement changed items after logistics pricing complete. Populated by trg_zz_invoice_items_smart_delta (m296).';
COMMENT ON COLUMN kvota.invoices.customs_needs_review_since IS 'Smart-delta flag: procurement changed items after customs pricing complete. Populated by trg_zz_invoice_items_smart_delta (m296).';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_invoices_assigned_customs_user
    ON kvota.invoices(assigned_customs_user)
    WHERE assigned_customs_user IS NOT NULL;

-- Partial indexes for workspace queries (active invoices = not completed)
CREATE INDEX IF NOT EXISTS idx_invoices_logistics_active
    ON kvota.invoices(assigned_logistics_user, logistics_deadline_at)
    WHERE logistics_completed_at IS NULL AND assigned_logistics_user IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_invoices_customs_active
    ON kvota.invoices(assigned_customs_user, customs_deadline_at)
    WHERE customs_completed_at IS NULL AND assigned_customs_user IS NOT NULL;

-- Review flag indexes (small tables — partial)
CREATE INDEX IF NOT EXISTS idx_invoices_logistics_needs_review
    ON kvota.invoices(logistics_needs_review_since)
    WHERE logistics_needs_review_since IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_invoices_customs_needs_review
    ON kvota.invoices(customs_needs_review_since)
    WHERE customs_needs_review_since IS NOT NULL;

-- Record migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (285, '285_invoices_sla_and_customs_assignment', now())
ON CONFLICT (id) DO NOTHING;
