-- Normalize quote_items.hs_code on write: strip every non-digit char.
-- ТН ВЭД codes are semantically 10 digits; separators are copy-paste noise.
BEGIN;

CREATE OR REPLACE FUNCTION kvota.normalize_hs_code()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.hs_code IS NOT NULL THEN
    NEW.hs_code := NULLIF(regexp_replace(NEW.hs_code, '\D', '', 'g'), '');
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_normalize_hs_code ON kvota.quote_items;
CREATE TRIGGER trg_normalize_hs_code
  BEFORE INSERT OR UPDATE OF hs_code ON kvota.quote_items
  FOR EACH ROW
  EXECUTE FUNCTION kvota.normalize_hs_code();

-- Backfill existing rows that have separators
UPDATE kvota.quote_items
SET hs_code = NULLIF(regexp_replace(hs_code, '\D', '', 'g'), '')
WHERE hs_code IS NOT NULL AND hs_code ~ '\D';

COMMIT;
