-- Migration 159: Add license fields (DS, SS, SGR) to quote_items for customs department
-- DS = Декларация соответствия (Declaration of Conformity)
-- SS = Сертификат соответствия (Certificate of Conformity)
-- SGR = Свидетельство о гос. регистрации (State Registration Certificate)

ALTER TABLE kvota.quote_items
ADD COLUMN IF NOT EXISTS license_ds_required BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS license_ds_cost DECIMAL(15,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS license_ss_required BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS license_ss_cost DECIMAL(15,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS license_sgr_required BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS license_sgr_cost DECIMAL(15,2) DEFAULT 0;

-- Check constraints: license costs must be >= 0
ALTER TABLE kvota.quote_items ADD CONSTRAINT check_license_ds_cost_non_negative CHECK (license_ds_cost >= 0);
ALTER TABLE kvota.quote_items ADD CONSTRAINT check_license_ss_cost_non_negative CHECK (license_ss_cost >= 0);
ALTER TABLE kvota.quote_items ADD CONSTRAINT check_license_sgr_cost_non_negative CHECK (license_sgr_cost >= 0);
