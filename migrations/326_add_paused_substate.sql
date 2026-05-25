-- Migration 326: Add 'paused' procurement substatus
-- Created: 2026-05-24
-- Testing 2 row 74 — adds a 5th kanban column «Пауза» for procurement.
-- The procurement_substatus column on kvota.quote_brand_substates is a TEXT
-- with a CHECK constraint (not a Postgres enum), so we drop+recreate the
-- constraint to include the new value.

BEGIN;

SET search_path TO kvota;

ALTER TABLE kvota.quote_brand_substates
    DROP CONSTRAINT IF EXISTS chk_qbs_substatus;

ALTER TABLE kvota.quote_brand_substates
    ADD CONSTRAINT chk_qbs_substatus CHECK (
        (substatus)::text = ANY ((ARRAY[
            'distributing'::character varying,
            'searching_supplier'::character varying,
            'waiting_prices'::character varying,
            'prices_ready'::character varying,
            'paused'::character varying
        ])::text[])
    );

COMMIT;
