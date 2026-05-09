-- Migration 310: add vat_rate column to kvota.invoices
--
-- Frontend (PR #114, fix/autofill-НДС, commit 76c48aa7) writes to
-- invoices.vat_rate via invoice-card.tsx, but the column was never added
-- to the invoices table — only to quote_items (m229) and invoice_items (m281).
-- Result on prod: PostgREST returns 42703 "column does not exist" → silent
-- save failures across procurement-step UI (МОЗ-82, МОЗ-91, МОЗ-108, МОЗ-109..114
-- all surface this as "ничего не сохраняется" to testers).
--
-- Type matches invoice_items.vat_rate (NUMERIC(5,2)). Nullable; autofill
-- populates it on first invoice-card mount via vat_rates_by_country lookup.

ALTER TABLE kvota.invoices
  ADD COLUMN IF NOT EXISTS vat_rate NUMERIC(5,2);

-- Tell PostgREST to refresh its schema cache so the new column is queryable.
NOTIFY pgrst, 'reload schema';
