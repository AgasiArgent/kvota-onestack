-- Add phones JSONB column to customer_contacts and migrate existing phone data
ALTER TABLE kvota.customer_contacts ADD COLUMN IF NOT EXISTS phones JSONB DEFAULT '[]';

UPDATE kvota.customer_contacts
SET phones = jsonb_build_array(
  jsonb_build_object('number', phone, 'ext', null, 'label', 'основной')
)
WHERE phone IS NOT NULL AND phone != '' AND (phones IS NULL OR phones = '[]'::jsonb);
