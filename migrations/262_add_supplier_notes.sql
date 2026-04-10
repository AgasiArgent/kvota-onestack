-- Add notes/comments field to suppliers table
ALTER TABLE kvota.suppliers ADD COLUMN IF NOT EXISTS notes TEXT;

COMMENT ON COLUMN kvota.suppliers.notes IS 'Free-text comments about this supplier';
