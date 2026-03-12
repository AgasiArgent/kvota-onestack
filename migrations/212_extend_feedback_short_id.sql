-- Extend short_id column to accommodate new format: FB-YYMMDD-HHMMSS-xxxx (22 chars)
ALTER TABLE kvota.user_feedback ALTER COLUMN short_id TYPE VARCHAR(30);
