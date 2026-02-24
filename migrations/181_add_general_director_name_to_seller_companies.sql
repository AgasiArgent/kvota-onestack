-- Migration 181: Add general_director_name column to seller_companies
-- Bug fix: code references general_director_name but DB only has split name columns
-- (general_director_last_name, general_director_first_name, general_director_patronymic)
-- The form uses a single "ФИО руководителя" field, so we need the unified column.

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS general_director_name VARCHAR(255);

COMMENT ON COLUMN kvota.seller_companies.general_director_name IS 'Full name of general director (ФИО) for document signing';

-- Populate from existing split columns where available
UPDATE kvota.seller_companies
SET general_director_name = TRIM(
    COALESCE(general_director_last_name, '') || ' ' ||
    COALESCE(general_director_first_name, '') || ' ' ||
    COALESCE(general_director_patronymic, '')
)
WHERE general_director_name IS NULL
  AND (general_director_last_name IS NOT NULL
       OR general_director_first_name IS NOT NULL
       OR general_director_patronymic IS NOT NULL);
