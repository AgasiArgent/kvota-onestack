-- Add incoterms column to quotes table
-- Used by sales managers when creating a quote; copied to calc_variables.offer_incoterms at calculation time
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS incoterms VARCHAR(10) DEFAULT NULL;

COMMENT ON COLUMN kvota.quotes.incoterms IS 'Incoterms delivery terms set by sales at quote creation (DDP, DAP, CIF, FOB, EXW)';
