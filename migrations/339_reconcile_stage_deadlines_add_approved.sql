-- Migration 339: Reconcile stage_deadlines seed with the canonical system stages
-- Testing 2 row 55 — Настройки › «Дедлайны стадий» must reflect the actual
-- workflow stages the system tracks.
--
-- The original seed (migration 240) covered 11 stages but omitted `approved`,
-- which IS a deadline-tracked stage: services/stage_timer_service.py only skips
-- TERMINAL_STATUSES (draft, deal, rejected, cancelled), so a quote sitting in
-- `approved` is timed — yet no org had a configurable deadline row for it, so it
-- silently fell through to "no_deadline".
--
-- This migration backfills the missing `approved` row for every organization.
-- It is idempotent: ON CONFLICT DO NOTHING leaves any existing rows (and their
-- configured deadline_hours) untouched — only the SET of stages is reconciled,
-- not the values.
--
-- Date: 2026-06-01

BEGIN;

INSERT INTO kvota.stage_deadlines (organization_id, stage, deadline_hours)
SELECT o.id, 'approved', 48
FROM kvota.organizations o
ON CONFLICT (organization_id, stage) DO NOTHING;

COMMIT;
