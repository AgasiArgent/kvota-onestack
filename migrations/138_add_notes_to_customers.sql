-- Migration 138: Add notes field to customers table for free-form notes/remarks
-- This field will be shown in a new "Дополнительно" tab on customer detail page

ALTER TABLE kvota.customers
ADD COLUMN IF NOT EXISTS notes TEXT;

COMMENT ON COLUMN kvota.customers.notes IS 'Free-form notes and remarks about the customer';
