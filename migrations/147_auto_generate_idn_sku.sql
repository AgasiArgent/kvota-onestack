-- Migration: Auto-generate idn_sku for quote_items
-- Created: 2026-02-01
-- Problem: idn_sku is empty for most items, causing blank values in specification exports
-- Solution: Add trigger to generate idn_sku on INSERT, backfill existing items

SET search_path TO kvota;

-- Function to generate idn_sku
CREATE OR REPLACE FUNCTION kvota.generate_idn_sku()
RETURNS TRIGGER AS $$
DECLARE
    quote_idn TEXT;
    item_position INTEGER;
BEGIN
    -- Get quote IDN
    SELECT idn_quote INTO quote_idn
    FROM kvota.quotes
    WHERE id = NEW.quote_id;

    -- Get next position for this quote (count existing items + 1)
    SELECT COALESCE(MAX(position), 0) + 1 INTO item_position
    FROM kvota.quote_items
    WHERE quote_id = NEW.quote_id AND id != NEW.id;

    -- Set position if not already set
    IF NEW.position IS NULL OR NEW.position = 0 THEN
        NEW.position := item_position;
    END IF;

    -- Generate idn_sku if not already set
    IF NEW.idn_sku IS NULL OR NEW.idn_sku = '' THEN
        NEW.idn_sku := COALESCE(quote_idn, 'Q') || '-' || LPAD(COALESCE(NEW.position, item_position)::TEXT, 3, '0');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for new items
DROP TRIGGER IF EXISTS trigger_generate_idn_sku ON kvota.quote_items;
CREATE TRIGGER trigger_generate_idn_sku
    BEFORE INSERT ON kvota.quote_items
    FOR EACH ROW
    EXECUTE FUNCTION kvota.generate_idn_sku();

-- Backfill existing items that don't have idn_sku
UPDATE kvota.quote_items qi
SET idn_sku = COALESCE(q.idn_quote, 'Q') || '-' || LPAD(qi.position::TEXT, 3, '0')
FROM kvota.quotes q
WHERE qi.quote_id = q.id
  AND (qi.idn_sku IS NULL OR qi.idn_sku = '')
  AND qi.position > 0;

-- For items with position = 0, assign positions first
WITH numbered AS (
    SELECT id, quote_id, ROW_NUMBER() OVER (PARTITION BY quote_id ORDER BY created_at) as new_pos
    FROM kvota.quote_items
    WHERE position = 0 OR position IS NULL
)
UPDATE kvota.quote_items qi
SET position = n.new_pos
FROM numbered n
WHERE qi.id = n.id;

-- Then generate idn_sku for remaining items
UPDATE kvota.quote_items qi
SET idn_sku = COALESCE(q.idn_quote, 'Q') || '-' || LPAD(qi.position::TEXT, 3, '0')
FROM kvota.quotes q
WHERE qi.quote_id = q.id
  AND (qi.idn_sku IS NULL OR qi.idn_sku = '');
