-- Fix: telegram_users_telegram_id_key prevents multiple users from generating
-- verification codes simultaneously (all unverified rows have telegram_id=0).
-- Solution: Replace full unique constraint with partial unique index that only
-- enforces uniqueness for actual telegram IDs (non-zero).

-- Drop the problematic unique constraint
ALTER TABLE kvota.telegram_users DROP CONSTRAINT IF EXISTS telegram_users_telegram_id_key;

-- Add partial unique index: only enforces uniqueness for verified (non-zero) telegram IDs
CREATE UNIQUE INDEX IF NOT EXISTS telegram_users_telegram_id_verified_key
ON kvota.telegram_users (telegram_id) WHERE telegram_id != 0;
