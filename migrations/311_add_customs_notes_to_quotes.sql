-- Migration 311: add customs_notes column to kvota.quotes
--
-- Frontend (commit 474fb88a, "Customs step — Handsontable grid + expenses + notes")
-- ships customs-notes.tsx that writes to quotes.customs_notes via:
--     .update({ customs_notes: notes } as Record<string, unknown>)
-- The `as Record<string, unknown>` cast disabled the typed Update<T> contract,
-- masking the fact that the column was never added to the schema. Same root
-- cause as МОЗ-82 / migration 310 (vat_rate on invoices).
--
-- This migration ships the column so PostgREST stops returning 42703 on
-- customs-notes save. Type is TEXT, nullable (notes are optional). Once the
-- column exists, regenerated database.types.ts will include it and the cast
-- in customs-notes.tsx can be removed (compiler will then enforce the shape).

ALTER TABLE kvota.quotes
  ADD COLUMN IF NOT EXISTS customs_notes TEXT;

NOTIFY pgrst, 'reload schema';
