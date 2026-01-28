-- Migration 140: Add requisites and bank details to seller_companies
-- For proper Invoice PDF generation matching reference template
-- Date: 2026-01-28

-- Legal identifiers
ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS inn VARCHAR(12);

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS kpp VARCHAR(9);

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS ogrn VARCHAR(15);

-- Registration address
ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS registration_address TEXT;

-- Contact info
ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS phone VARCHAR(50);

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS email VARCHAR(100);

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS website VARCHAR(100);

-- Bank details (for invoice "Образец платежного поручения")
ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS bank_name VARCHAR(200);

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS bik VARCHAR(9);

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS correspondent_account VARCHAR(20);

ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS payment_account VARCHAR(20);

-- Invoice validity days default
ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS invoice_validity_days INTEGER DEFAULT 30;

-- Comments
COMMENT ON COLUMN kvota.seller_companies.inn IS 'ИНН - Tax ID (10 digits for legal entities, 12 for IE)';
COMMENT ON COLUMN kvota.seller_companies.kpp IS 'КПП - Tax registration code (9 digits)';
COMMENT ON COLUMN kvota.seller_companies.ogrn IS 'ОГРН - State registration number (13 or 15 digits)';
COMMENT ON COLUMN kvota.seller_companies.registration_address IS 'Legal registration address';
COMMENT ON COLUMN kvota.seller_companies.phone IS 'Contact phone number';
COMMENT ON COLUMN kvota.seller_companies.email IS 'Contact email';
COMMENT ON COLUMN kvota.seller_companies.website IS 'Company website';
COMMENT ON COLUMN kvota.seller_companies.bank_name IS 'Bank name for payment details';
COMMENT ON COLUMN kvota.seller_companies.bik IS 'БИК - Bank identification code';
COMMENT ON COLUMN kvota.seller_companies.correspondent_account IS 'К/сч - Correspondent account';
COMMENT ON COLUMN kvota.seller_companies.payment_account IS 'Р/сч - Payment account';
COMMENT ON COLUMN kvota.seller_companies.invoice_validity_days IS 'Default validity period for invoices';

-- Update Master Bearing with actual data from reference invoice
UPDATE kvota.seller_companies
SET
    inn = '0242013464',
    kpp = '772101001',
    registration_address = '109428, г. Москва, вн.тер.г. муниципальный округ Рязанский, пр-кт Рязанский, д. 22, к. 2, помещ. 1/1.',
    phone = '8 (800) 350-21-34',
    website = 'masterbearing.ru',
    bank_name = 'АО "Кредит Европа Банк (Россия)"',
    bik = '044525767',
    correspondent_account = '30101810945250000767',
    payment_account = '40702978700903800004',
    invoice_validity_days = 30
WHERE supplier_code = 'MBR' AND name ILIKE '%МАСТЕР БЭРИНГ%';
