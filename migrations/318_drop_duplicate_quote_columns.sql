-- Drop dupe orphan columns confirmed unused in code + prod:
--   quotes.total_amount_quote        — never written; total_quote_currency is canonical
--   quote_items.supplier_advance_percent — never read/written; advance_to_supplier_percent is canonical

ALTER TABLE kvota.quotes DROP COLUMN IF EXISTS total_amount_quote;
ALTER TABLE kvota.quote_items DROP COLUMN IF EXISTS supplier_advance_percent;
