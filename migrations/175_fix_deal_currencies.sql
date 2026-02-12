-- Migration 175: Fix deal currencies to match their quote currencies
--
-- Problem: All 4 existing deals were created with currency='USD' regardless
-- of the actual quote currency. The deal creation code (deal_service.py:1044)
-- now correctly reads currency from the spec/quote, but existing data needs
-- a one-time fix.
--
-- Affected deals:
--   ad66b5c0: USD -> RUB (quote currency is RUB)
--   97ba3198: USD -> EUR (quote currency is EUR)
--   2f2286bb: USD -> RUB (quote currency is RUB)
--   0601783c: USD -> USD (already correct, no change)

UPDATE kvota.deals d
SET currency = q.currency
FROM kvota.specifications s
JOIN kvota.quotes q ON q.id = s.quote_id
WHERE d.specification_id = s.id
  AND d.currency != q.currency;

COMMENT ON TABLE kvota.deals IS 'Deal currency is inherited from quote.currency via specification at creation time. Migration 175 fixed historical data where all deals had USD regardless of quote currency.';
