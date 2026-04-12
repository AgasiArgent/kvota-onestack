-- Migration 269: VAT Rates by Country
-- Phase 4a Task 1.1: Lookup table for VAT rates by country of origin
--
-- EAEU countries (RU, KZ, BY, AM, KG) are seeded at 0% because VAT for
-- intra-EAEU trade is collected via tax declaration, not customs.
-- Major import origin countries are seeded at the standard 20% Russian
-- import VAT rate for admin visibility.

CREATE TABLE kvota.vat_rates_by_country (
  country_code CHAR(2) PRIMARY KEY,
  rate NUMERIC(5,2) NOT NULL DEFAULT 20.00,
  notes TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_by UUID REFERENCES auth.users(id)
);

-- Seed EAEU countries at 0% (VAT collected via tax declaration, not customs)
INSERT INTO kvota.vat_rates_by_country (country_code, rate, notes) VALUES
  ('RU', 0, 'Россия — внутренний рынок'),
  ('KZ', 0, 'ЕАЭС — косвенный НДС через декларацию'),
  ('BY', 0, 'ЕАЭС — косвенный НДС через декларацию'),
  ('AM', 0, 'ЕАЭС — косвенный НДС через декларацию'),
  ('KG', 0, 'ЕАЭС — косвенный НДС через декларацию');

-- Major import origin countries at standard 20% (pre-seeded for admin visibility)
INSERT INTO kvota.vat_rates_by_country (country_code, rate, notes) VALUES
  ('CN', 20, 'Китай — стандартная ставка'),
  ('TR', 20, 'Турция — стандартная ставка'),
  ('DE', 20, 'Германия — стандартная ставка'),
  ('IT', 20, 'Италия — стандартная ставка'),
  ('AE', 20, 'ОАЭ — стандартная ставка'),
  ('JP', 20, 'Япония — стандартная ставка'),
  ('KR', 20, 'Южная Корея — стандартная ставка'),
  ('IN', 20, 'Индия — стандартная ставка'),
  ('US', 20, 'США — стандартная ставка'),
  ('GB', 20, 'Великобритания — стандартная ставка');
