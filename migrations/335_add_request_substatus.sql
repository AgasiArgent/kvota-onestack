-- Migration 335: Add 'request' procurement substatus («Заявка»)
-- Created: 2026-06-01
-- Testing 2 row 95a — inserts a new kanban stage «Заявка» between
-- «Распределение» (distributing) and «Поиск поставщика» (searching_supplier).
--
-- The procurement_substatus column on kvota.quote_brand_substates is a TEXT
-- with a CHECK constraint (chk_qbs_substatus, see migrations 274 + 326), not a
-- Postgres enum, so we drop+recreate the constraint to include the new value.
-- Wrapped in BEGIN/COMMIT so a partial failure rolls back (no constraint-less
-- window in prod).

BEGIN;

SET search_path TO kvota;

ALTER TABLE kvota.quote_brand_substates
    DROP CONSTRAINT IF EXISTS chk_qbs_substatus;

ALTER TABLE kvota.quote_brand_substates
    ADD CONSTRAINT chk_qbs_substatus CHECK (
        (substatus)::text = ANY ((ARRAY[
            'distributing'::character varying,
            'request'::character varying,
            'searching_supplier'::character varying,
            'waiting_prices'::character varying,
            'prices_ready'::character varying,
            'paused'::character varying
        ])::text[])
    );

COMMIT;
