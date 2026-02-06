-- Migration 154: Add delivery_priority to quotes
-- Options: fast (Лучше быстро), cheap (Лучше дешево), normal (Обычно)

ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS delivery_priority TEXT;
