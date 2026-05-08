-- Migration 309: Segment editor features (РОЛ Тест 07 #3.4, #3.5, #3.7).
--
-- Three independent additive changes that improve the per-invoice route
-- segment editor:
--
--   3.4 — МОЗ pickup addresses surfaced as first-class kvota.locations rows.
--         Trigger find-or-creates a location whenever an invoice's
--         pickup_country + pickup_city are set, then caches the FK on
--         invoices.pickup_location_id (column already exists since m123).
--         Backfill runs once for existing invoices.
--
--   3.5 — Hybrid templates: logistics_route_template_segments gains
--         nullable from_location_id / to_location_id FKs alongside the
--         existing *_location_type columns. apply_template prefers the
--         concrete FK when set; falls back to type-based selection.
--
--   3.7 — Per-segment currency: logistics_route_segments.main_cost_rub and
--         logistics_segment_expenses.cost_rub are now interpreted in the
--         segment's own currency_code (default 'RUB'). The column NAMES are
--         retained for backwards compatibility — frontend converts to the
--         quote currency at display time using kvota.quotes.exchange_rate_to_usd
--         + kvota.quotes.usd_to_quote_rate. Schema-drift follow-up: rename
--         main_cost_rub → main_cost in a later migration once all callers
--         pass currency_code explicitly.

-- =============================================================================
-- 3.4 — Pickup-address sync to kvota.locations
-- =============================================================================

-- Trigger function: when invoice.pickup_country + pickup_city are populated,
-- find-or-create a kvota.locations row in the same org and stash the id on
-- invoices.pickup_location_id. Case-insensitive city/country match.
--
-- SECURITY DEFINER so triggers fire under the table owner's privileges and
-- bypass locations RLS — the invoice itself is already org-scoped via RLS,
-- so the user can only INSERT/UPDATE invoices in their own org, and the
-- trigger creates the location in that same org.
--
-- Skipped silently when:
--   - pickup_country or pickup_city is NULL/blank (no usable address)
--   - the invoice has no parent quote (defensive — should never happen)
--   - the invoice's organisation cannot be resolved (defensive)

CREATE OR REPLACE FUNCTION kvota.sync_invoice_pickup_location()
RETURNS TRIGGER AS $$
DECLARE
    v_org_id    UUID;
    v_country   TEXT;
    v_city      TEXT;
    v_loc_id    UUID;
BEGIN
    -- Normalise inputs
    v_country := NULLIF(BTRIM(NEW.pickup_country), '');
    v_city    := NULLIF(BTRIM(NEW.pickup_city), '');

    -- Nothing usable → leave pickup_location_id alone
    IF v_country IS NULL OR v_city IS NULL THEN
        RETURN NEW;
    END IF;

    -- Resolve org via parent quote (invoices.quote_id NOT NULL by table def)
    SELECT q.organization_id
      INTO v_org_id
      FROM kvota.quotes q
     WHERE q.id = NEW.quote_id;

    IF v_org_id IS NULL THEN
        -- Defensive: invoice without a quote shouldn't exist; let the row
        -- save anyway so the original mutation doesn't fail because of us.
        RETURN NEW;
    END IF;

    -- Look for an existing location with matching country + city in the
    -- same org (case-insensitive). Prefer active rows.
    SELECT l.id
      INTO v_loc_id
      FROM kvota.locations l
     WHERE l.organization_id = v_org_id
       AND LOWER(BTRIM(l.country)) = LOWER(v_country)
       AND l.city IS NOT NULL
       AND LOWER(BTRIM(l.city)) = LOWER(v_city)
     ORDER BY l.is_active DESC, l.created_at ASC
     LIMIT 1;

    -- Not found? Create one. Defaults: type='supplier' (МОЗ pickup is the
    -- supplier side of the journey), is_active=true, code NULL.
    IF v_loc_id IS NULL THEN
        INSERT INTO kvota.locations (
            organization_id,
            country,
            city,
            location_type,
            is_active
        ) VALUES (
            v_org_id,
            v_country,
            v_city,
            'supplier',
            TRUE
        )
        RETURNING id INTO v_loc_id;
    END IF;

    NEW.pickup_location_id := v_loc_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = kvota, public;

COMMENT ON FUNCTION kvota.sync_invoice_pickup_location() IS
    'BEFORE INSERT/UPDATE trigger on invoices: find-or-create kvota.locations row matching pickup_country+pickup_city, cache id on pickup_location_id. РОЛ Тест 07 #3.4.';

-- Replace any previous trigger with the new one. We fire on INSERT and on
-- UPDATE OF (pickup_country, pickup_city, quote_id) — the OF list keeps
-- unrelated invoice updates from re-running the function unnecessarily.
DROP TRIGGER IF EXISTS trg_invoices_sync_pickup_location ON kvota.invoices;
CREATE TRIGGER trg_invoices_sync_pickup_location
    BEFORE INSERT OR UPDATE OF pickup_country, pickup_city, quote_id
    ON kvota.invoices
    FOR EACH ROW
    EXECUTE FUNCTION kvota.sync_invoice_pickup_location();

-- One-shot backfill: existing invoices that have a pickup_country+city but
-- no pickup_location_id get the same find-or-create treatment. We loop in
-- PL/pgSQL because the trigger only fires on writes, and we want per-row
-- deterministic ordering (oldest first → matching locations come from the
-- earliest invoice).
DO $$
DECLARE
    inv         RECORD;
    v_org_id    UUID;
    v_country   TEXT;
    v_city      TEXT;
    v_loc_id    UUID;
    v_created   INT := 0;
    v_linked    INT := 0;
BEGIN
    FOR inv IN
        SELECT i.id, i.quote_id, i.pickup_country, i.pickup_city
          FROM kvota.invoices i
         WHERE i.pickup_country IS NOT NULL
           AND i.pickup_city IS NOT NULL
           AND BTRIM(i.pickup_country) <> ''
           AND BTRIM(i.pickup_city) <> ''
           AND i.pickup_location_id IS NULL
         ORDER BY i.created_at NULLS FIRST, i.id
    LOOP
        v_country := BTRIM(inv.pickup_country);
        v_city    := BTRIM(inv.pickup_city);

        SELECT q.organization_id INTO v_org_id
          FROM kvota.quotes q WHERE q.id = inv.quote_id;
        IF v_org_id IS NULL THEN
            CONTINUE;
        END IF;

        SELECT l.id INTO v_loc_id
          FROM kvota.locations l
         WHERE l.organization_id = v_org_id
           AND LOWER(BTRIM(l.country)) = LOWER(v_country)
           AND l.city IS NOT NULL
           AND LOWER(BTRIM(l.city)) = LOWER(v_city)
         ORDER BY l.is_active DESC, l.created_at ASC
         LIMIT 1;

        IF v_loc_id IS NULL THEN
            INSERT INTO kvota.locations (
                organization_id, country, city,
                location_type, is_active
            ) VALUES (
                v_org_id, v_country, v_city,
                'supplier', TRUE
            )
            RETURNING id INTO v_loc_id;
            v_created := v_created + 1;
        END IF;

        UPDATE kvota.invoices
           SET pickup_location_id = v_loc_id
         WHERE id = inv.id;
        v_linked := v_linked + 1;
    END LOOP;

    RAISE NOTICE 'm309 pickup-location backfill: linked=% created=%', v_linked, v_created;
END $$;

-- =============================================================================
-- 3.5 — Hybrid templates: optional concrete location FKs alongside types
-- =============================================================================

ALTER TABLE kvota.logistics_route_template_segments
    ADD COLUMN IF NOT EXISTS from_location_id UUID
        REFERENCES kvota.locations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS to_location_id UUID
        REFERENCES kvota.locations(id) ON DELETE SET NULL;

COMMENT ON COLUMN kvota.logistics_route_template_segments.from_location_id IS
    'Optional concrete location for the from side. When set, apply_template uses this id; when NULL, falls back to from_location_type-based selection. РОЛ Тест 07 #3.5.';
COMMENT ON COLUMN kvota.logistics_route_template_segments.to_location_id IS
    'Optional concrete location for the to side. When set, apply_template uses this id; when NULL, falls back to to_location_type-based selection. РОЛ Тест 07 #3.5.';

CREATE INDEX IF NOT EXISTS idx_logistics_template_segments_from_loc
    ON kvota.logistics_route_template_segments(from_location_id)
    WHERE from_location_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_logistics_template_segments_to_loc
    ON kvota.logistics_route_template_segments(to_location_id)
    WHERE to_location_id IS NOT NULL;

-- =============================================================================
-- 3.7 — Per-segment currency
-- =============================================================================
--
-- main_cost_rub / cost_rub columns are kept (column-rename deferred to a
-- follow-up so we don't have to touch all calc-engine + view callers in the
-- same change). Default 'RUB' so existing rows keep their meaning.

ALTER TABLE kvota.logistics_route_segments
    ADD COLUMN IF NOT EXISTS currency_code TEXT NOT NULL DEFAULT 'RUB';

ALTER TABLE kvota.logistics_route_segments
    DROP CONSTRAINT IF EXISTS logistics_route_segments_currency_check;
ALTER TABLE kvota.logistics_route_segments
    ADD CONSTRAINT logistics_route_segments_currency_check
    CHECK (currency_code IN ('RUB', 'USD', 'EUR', 'CNY'));

COMMENT ON COLUMN kvota.logistics_route_segments.currency_code IS
    'Currency the main_cost_rub value is denominated in. Default RUB. Frontend converts to quote currency for display. РОЛ Тест 07 #3.7.';

ALTER TABLE kvota.logistics_segment_expenses
    ADD COLUMN IF NOT EXISTS currency_code TEXT NOT NULL DEFAULT 'RUB';

ALTER TABLE kvota.logistics_segment_expenses
    DROP CONSTRAINT IF EXISTS logistics_segment_expenses_currency_check;
ALTER TABLE kvota.logistics_segment_expenses
    ADD CONSTRAINT logistics_segment_expenses_currency_check
    CHECK (currency_code IN ('RUB', 'USD', 'EUR', 'CNY'));

COMMENT ON COLUMN kvota.logistics_segment_expenses.currency_code IS
    'Currency the cost_rub value is denominated in. Default RUB. Frontend converts to quote currency for display. РОЛ Тест 07 #3.7.';

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (309, '309_segment_features', now())
ON CONFLICT (id) DO NOTHING;
