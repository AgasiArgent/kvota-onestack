-- Migration 216: Fix department duplicates and prevent recurrence
--
-- Root cause: migration 178 is not tracked in kvota.migrations,
-- so it re-runs on every deploy, inserting duplicate "Контроль" rows.
-- Result: 196 duplicate "Контроль" rows (should be 1).

-- Step 1: Delete duplicate departments, keep the oldest one per name
DELETE FROM kvota.departments
WHERE id NOT IN (
    SELECT DISTINCT ON (name) id
    FROM kvota.departments
    ORDER BY name, created_at ASC
);

-- Step 2: Add UNIQUE constraint to prevent future duplicates
ALTER TABLE kvota.departments
ADD CONSTRAINT departments_name_unique UNIQUE (name);

-- Step 3: Register migration 178 so it doesn't re-run on next deploy
INSERT INTO kvota.migrations (filename)
VALUES ('178_beta_test_prep.sql')
ON CONFLICT (filename) DO NOTHING;
