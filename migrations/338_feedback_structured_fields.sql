-- Migration 338: Structured feedback fields (Testing 2 row 49)
-- Date: 2026-06-01
--
-- The bug-report form ("Форма обратной связи") splits the single «Описание»
-- textarea into three labeled fields:
--   - steps_taken      «Что делал»            (required in UI)
--   - expected_result  «Что ожидал получить»  (optional in UI)
--   - actual_result    «Что получил»          (required in UI)
--
-- The legacy `description` column is KEPT for backward compatibility: the
-- submit handler composes a labeled human-readable summary into it so existing
-- read surfaces (admin feedback list/detail, ClickUp task body, Telegram admin
-- notification) keep working unchanged. New rows populate both the structured
-- columns and `description`; historical rows keep their original `description`.
--
-- Idempotent (IF NOT EXISTS) + transactional. Applied to prod via SSH
-- (scripts/apply-migrations.sh) — NOT auto-applied by deploy.

BEGIN;

ALTER TABLE kvota.user_feedback
    ADD COLUMN IF NOT EXISTS steps_taken TEXT;

ALTER TABLE kvota.user_feedback
    ADD COLUMN IF NOT EXISTS expected_result TEXT;

ALTER TABLE kvota.user_feedback
    ADD COLUMN IF NOT EXISTS actual_result TEXT;

COMMENT ON COLUMN kvota.user_feedback.steps_taken IS
    'Structured feedback: «Что делал» (what the user was doing). Composed into description for back-compat.';
COMMENT ON COLUMN kvota.user_feedback.expected_result IS
    'Structured feedback: «Что ожидал получить» (expected result). Optional.';
COMMENT ON COLUMN kvota.user_feedback.actual_result IS
    'Structured feedback: «Что получил» (actual result / what went wrong).';

COMMIT;
