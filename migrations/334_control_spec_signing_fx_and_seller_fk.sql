-- 334_control_spec_signing_fx_and_seller_fk.sql
-- Feature: control-spec-workspace (PR1 foundation).
--
-- Additive (expand phase) migration on kvota.specifications:
--   1. signing_fx_mode  — at-signing FX provenance: 'cbr_on_payment_day' (default in
--      UI, usual case) | 'fixed' (rare, a locked rate). NULL until a controller chooses
--      (fail-loud, no silent DB default).
--   2. signing_fx_rate  — the locked rate when mode = 'fixed'; NULL otherwise.
--      DECIMAL(15,6) mirrors kvota.specifications.exchange_rate_to_ruble.
--   3. seller_company_id — FK to the canonical "our legal entity" registry. The
--      existing our_legal_entity VARCHAR is kept as a dual-written name snapshot for
--      export compatibility (contract_spec_docx.py); this FK is the selection source.
--
-- Safety:
--   * All columns nullable, no backfill required.
--   * The calculation engine does NOT read these columns (verified: matches only in
--     specification_service.py + contract_spec_docx.py) — calc-engine LOCKED honoured.
--   * Idempotent (ADD COLUMN IF NOT EXISTS); wrapped in a transaction.
BEGIN;

ALTER TABLE kvota.specifications
  ADD COLUMN IF NOT EXISTS signing_fx_mode VARCHAR(32)
    CHECK (signing_fx_mode IS NULL OR signing_fx_mode IN ('cbr_on_payment_day', 'fixed')),
  ADD COLUMN IF NOT EXISTS signing_fx_rate DECIMAL(15, 6),
  ADD COLUMN IF NOT EXISTS seller_company_id UUID
    REFERENCES kvota.seller_companies(id) ON DELETE SET NULL;

COMMENT ON COLUMN kvota.specifications.signing_fx_mode IS
  'At-signing FX provenance: cbr_on_payment_day (default) | fixed. NULL until chosen.';
COMMENT ON COLUMN kvota.specifications.signing_fx_rate IS
  'Locked at-signing rate when signing_fx_mode = fixed; NULL for cbr_on_payment_day.';
COMMENT ON COLUMN kvota.specifications.seller_company_id IS
  'FK to kvota.seller_companies — canonical "our legal entity". our_legal_entity VARCHAR kept as export name snapshot.';

COMMIT;
