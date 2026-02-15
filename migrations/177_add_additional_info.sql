-- Migration 177: Add additional_info field to quotes table
-- For the Prodazhi tab redesign — stores free-text notes in Block I col 2

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS additional_info TEXT;
