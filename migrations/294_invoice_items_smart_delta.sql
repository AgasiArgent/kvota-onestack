-- Migration 294: Smart-delta trigger for invoice_items → invoice review flags.
-- Wave 2 Task 14/E of logistics-customs-redesign spec (design §3.8, §5.3).
--
-- Purpose:
--   Wave 1 added `invoices.{logistics,customs}_needs_review_since` columns and
--   an /api/logistics/acknowledge-review endpoint, but nothing set the flags.
--   This trigger closes the loop: when procurement edits an invoice_items row
--   after the invoice has been fully priced by logistics/customs, the flag is
--   raised so the assignee sees a badge and must acknowledge the change.
--
-- Matrix (which change flips which flag):
--   | Change                          | logistics | customs |
--   |---------------------------------|-----------|---------|
--   | quantity                        |     ✅    |    —    |
--   | weight_in_kg                    |     ✅    |    —    |
--   | supplier_country                |     ✅    |    ✅   |
--   | customs_code                    |      —    |    ✅   |
--   | INSERT row                      |     ✅    |    ✅   |
--   | DELETE row                      |     ✅    |    ✅   |
--   | any other column                |      —    |    —    |
--
-- Guard: flag is set ONLY if the corresponding `*_completed_at` is NOT NULL
-- (no point raising review for work that hasn't been done yet).
--
-- Naming: `trg_zz_invoice_items_smart_delta` — the `zz_` prefix ensures this
-- runs AFTER any alphabetically earlier triggers on the same table (spec §10).
-- Keeps interactions with procurement-branch triggers deterministic.

-- =============================================================================
-- Helper function: set the flag(s) on the parent invoice
-- =============================================================================

CREATE OR REPLACE FUNCTION kvota.tg_invoice_items_smart_delta()
RETURNS TRIGGER AS $$
DECLARE
    v_invoice_id UUID;
    v_affect_logistics BOOLEAN := FALSE;
    v_affect_customs BOOLEAN := FALSE;
BEGIN
    -- Determine which invoice is affected and which flags to raise.
    IF TG_OP = 'INSERT' THEN
        v_invoice_id := NEW.invoice_id;
        v_affect_logistics := TRUE;
        v_affect_customs := TRUE;

    ELSIF TG_OP = 'DELETE' THEN
        v_invoice_id := OLD.invoice_id;
        v_affect_logistics := TRUE;
        v_affect_customs := TRUE;

    ELSIF TG_OP = 'UPDATE' THEN
        v_invoice_id := NEW.invoice_id;
        -- Only the explicit matrix columns count. IS DISTINCT FROM handles NULLs.
        IF NEW.quantity IS DISTINCT FROM OLD.quantity THEN
            v_affect_logistics := TRUE;
        END IF;
        IF NEW.weight_in_kg IS DISTINCT FROM OLD.weight_in_kg THEN
            v_affect_logistics := TRUE;
        END IF;
        IF NEW.supplier_country IS DISTINCT FROM OLD.supplier_country THEN
            v_affect_logistics := TRUE;
            v_affect_customs := TRUE;
        END IF;
        IF NEW.customs_code IS DISTINCT FROM OLD.customs_code THEN
            v_affect_customs := TRUE;
        END IF;
        -- Invoice moved between invoices — treat as add+remove on both sides.
        IF NEW.invoice_id IS DISTINCT FROM OLD.invoice_id THEN
            v_affect_logistics := TRUE;
            v_affect_customs := TRUE;
            -- Flag the OLD invoice too
            UPDATE kvota.invoices
            SET logistics_needs_review_since = COALESCE(logistics_needs_review_since, now())
            WHERE id = OLD.invoice_id
                AND logistics_completed_at IS NOT NULL
                AND logistics_needs_review_since IS NULL;
            UPDATE kvota.invoices
            SET customs_needs_review_since = COALESCE(customs_needs_review_since, now())
            WHERE id = OLD.invoice_id
                AND customs_completed_at IS NOT NULL
                AND customs_needs_review_since IS NULL;
        END IF;
    END IF;

    IF v_invoice_id IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    -- Set logistics flag only on an already-completed invoice that isn't
    -- already pending review.
    IF v_affect_logistics THEN
        UPDATE kvota.invoices
        SET logistics_needs_review_since = now()
        WHERE id = v_invoice_id
            AND logistics_completed_at IS NOT NULL
            AND logistics_needs_review_since IS NULL;
    END IF;

    IF v_affect_customs THEN
        UPDATE kvota.invoices
        SET customs_needs_review_since = now()
        WHERE id = v_invoice_id
            AND customs_completed_at IS NOT NULL
            AND customs_needs_review_since IS NULL;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kvota.tg_invoice_items_smart_delta() IS
    'Smart-delta trigger for Wave 2 Task 14/E — raises '
    'invoices.{logistics,customs}_needs_review_since when procurement '
    'edits a priced invoice. See migration 294.';

-- =============================================================================
-- Trigger wiring
-- =============================================================================

DROP TRIGGER IF EXISTS trg_zz_invoice_items_smart_delta ON kvota.invoice_items;
CREATE TRIGGER trg_zz_invoice_items_smart_delta
    AFTER INSERT OR UPDATE OR DELETE ON kvota.invoice_items
    FOR EACH ROW
    EXECUTE FUNCTION kvota.tg_invoice_items_smart_delta();

-- =============================================================================
-- Sanity probe (non-destructive): verify trigger is attached.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_zz_invoice_items_smart_delta'
          AND tgrelid = 'kvota.invoice_items'::regclass
    ) THEN
        RAISE EXCEPTION 'smart-delta trigger failed to attach to kvota.invoice_items';
    END IF;
END;
$$;
