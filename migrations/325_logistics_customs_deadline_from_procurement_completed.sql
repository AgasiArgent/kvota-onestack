-- Migration 325: timer source = stage entry (procurement_completed_at)
--
-- Background (Testing 2 row 43):
--   Until now ``logistics_deadline_at`` / ``customs_deadline_at`` were stamped
--   only by the auto-assigners (assign_logistics_to_invoices /
--   assign_customs_invoices_for_quote — see m285/m286), computed as
--   ``assigned_at + sla_hours``. Auto-distribution was removed by the
--   logistics-customs-kanban redesign (REQ-3) — assignment is now manual via
--   the workspace kanban (`selfPullInvoice` / `reassignInvoice`). Those
--   server actions stamp only ``*_assigned_at`` and DO NOT touch
--   ``*_deadline_at`` — so newly completed procurement invoices have a NULL
--   deadline until someone happens to assign them, and the SLA timer never
--   fires for unassigned cards.
--
--   Product decision (docs/plans/2026-05-24-product-decisions.md, row 43):
--   the deadline must start counting from STAGE ENTRY (the moment procurement
--   completes and the invoice enters the logistics+customs queue), regardless
--   of whether anyone is assigned yet.
--
-- This migration:
--   Backfills existing rows whose procurement was completed but the deadline
--   was never stamped (or was stamped from the old assigned_at semantics).
--   New deadline = ``procurement_completed_at + sla_hours * INTERVAL '1 hour'``
--   per-row (sla_hours is a per-invoice column, default 72 — see m285).
--
-- Note on units:
--   SLA is measured in HOURS, not days (logistics_sla_hours / customs_sla_hours,
--   default 72h = 3 days; per-org configurable). The original task draft
--   guessed 30 days; the actual constants live in m285.
--
-- Idempotency:
--   The UPDATE recomputes the deadline for every row that has
--   ``procurement_completed_at`` set. Already-stamped invoices simply get
--   their deadline rewritten to the new (correct) value — no row stays in a
--   mixed/legacy state.

BEGIN;

UPDATE kvota.invoices
SET logistics_deadline_at = procurement_completed_at
                          + (COALESCE(logistics_sla_hours, 72) || ' hours')::INTERVAL
WHERE procurement_completed_at IS NOT NULL
  AND logistics_completed_at IS NULL;

UPDATE kvota.invoices
SET customs_deadline_at = procurement_completed_at
                        + (COALESCE(customs_sla_hours, 72) || ' hours')::INTERVAL
WHERE procurement_completed_at IS NOT NULL
  AND customs_completed_at IS NULL;

COMMENT ON COLUMN kvota.invoices.logistics_deadline_at IS
  'procurement_completed_at + logistics_sla_hours * INTERVAL ''1 hour''. '
  'Stamped when the invoice enters the logistics+customs stage (Testing 2 row 43). '
  'Independent of who is assigned — SLA runs even on unassigned invoices.';

COMMENT ON COLUMN kvota.invoices.customs_deadline_at IS
  'procurement_completed_at + customs_sla_hours * INTERVAL ''1 hour''. '
  'Symmetric to logistics_deadline_at.';

-- Note on kvota.assign_customs_invoices_for_quote (m286):
--   The function still stamps customs_deadline_at = assigned_at + sla_hours
--   when called, but it is no longer invoked by the normal workflow
--   (logistics-customs-kanban REQ-3 removed auto-distribution). It is
--   retained only for one-off backfill scripts. Live procurement
--   completions own the deadline via the application path
--   (workflow_service.complete_procurement / complete_procurement_for_invoice).

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (325, '325_logistics_customs_deadline_from_procurement_completed', now())
ON CONFLICT (id) DO NOTHING;

COMMIT;
