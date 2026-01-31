-- Migration 145: Price Offers as JSONB field in quote_items
-- Single source of truth - no sync needed
--
-- Architecture: JSONB array in quote_items table

-- Add price_offers JSONB column to existing quote_items
ALTER TABLE kvota.quote_items
ADD COLUMN IF NOT EXISTS price_offers JSONB DEFAULT '[]'::jsonb;

-- Add index for JSONB queries (find items with selected offer from specific supplier)
CREATE INDEX IF NOT EXISTS idx_quote_items_price_offers
ON kvota.quote_items USING GIN (price_offers);

-- Comment explaining structure
COMMENT ON COLUMN kvota.quote_items.price_offers IS
'Array of price offers: [{"id": "uuid", "supplier_id": "uuid", "supplier_name": "...", "price": 1500.00, "currency": "USD", "production_days": 14, "is_selected": true, "created_at": "..."}]';

-- Stored procedure to select an offer (atomic operation)
-- Sets is_selected=true for target, false for others, updates main fields
CREATE OR REPLACE FUNCTION kvota.select_jsonb_offer(
    p_item_id UUID,
    p_offer_id TEXT  -- offer id within JSONB array
)
RETURNS VOID AS $$
DECLARE
    v_offers JSONB;
    v_selected JSONB;
    v_new_offers JSONB;
    i INTEGER;
BEGIN
    -- Get current offers
    SELECT price_offers INTO v_offers
    FROM kvota.quote_items
    WHERE id = p_item_id;

    IF v_offers IS NULL OR jsonb_array_length(v_offers) = 0 THEN
        RAISE EXCEPTION 'No offers found for item %', p_item_id;
    END IF;

    -- Build new array with updated is_selected flags
    v_new_offers := '[]'::jsonb;

    FOR i IN 0..jsonb_array_length(v_offers) - 1 LOOP
        IF (v_offers->i->>'id') = p_offer_id THEN
            -- This is the selected offer
            v_selected := v_offers->i;
            v_new_offers := v_new_offers || jsonb_set(v_offers->i, '{is_selected}', 'true'::jsonb);
        ELSE
            -- Deselect others
            v_new_offers := v_new_offers || jsonb_set(v_offers->i, '{is_selected}', 'false'::jsonb);
        END IF;
    END LOOP;

    IF v_selected IS NULL THEN
        RAISE EXCEPTION 'Offer % not found in item %', p_offer_id, p_item_id;
    END IF;

    -- Update item with new offers array AND sync main fields
    UPDATE kvota.quote_items
    SET
        price_offers = v_new_offers,
        supplier_id = (v_selected->>'supplier_id')::uuid,
        purchase_price_original = (v_selected->>'price')::decimal,
        purchase_currency = v_selected->>'currency',
        production_time_days = (v_selected->>'production_days')::integer,
        updated_at = NOW()
    WHERE id = p_item_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute
GRANT EXECUTE ON FUNCTION kvota.select_jsonb_offer(UUID, TEXT) TO authenticated;

-- Helper function to add an offer
CREATE OR REPLACE FUNCTION kvota.add_jsonb_offer(
    p_item_id UUID,
    p_supplier_id UUID,
    p_supplier_name TEXT,
    p_price DECIMAL,
    p_currency VARCHAR(3),
    p_production_days INTEGER DEFAULT 0
)
RETURNS TEXT AS $$  -- Returns the new offer's ID
DECLARE
    v_offer_id TEXT;
    v_new_offer JSONB;
    v_current_count INTEGER;
BEGIN
    -- Check max offers limit
    SELECT jsonb_array_length(COALESCE(price_offers, '[]'::jsonb))
    INTO v_current_count
    FROM kvota.quote_items
    WHERE id = p_item_id;

    IF v_current_count >= 5 THEN
        RAISE EXCEPTION 'Maximum 5 offers per item reached';
    END IF;

    -- Generate unique ID for this offer
    v_offer_id := gen_random_uuid()::text;

    -- Build offer object
    v_new_offer := jsonb_build_object(
        'id', v_offer_id,
        'supplier_id', p_supplier_id,
        'supplier_name', p_supplier_name,
        'price', p_price,
        'currency', p_currency,
        'production_days', p_production_days,
        'is_selected', false,
        'created_at', NOW()
    );

    -- Append to array
    UPDATE kvota.quote_items
    SET
        price_offers = COALESCE(price_offers, '[]'::jsonb) || v_new_offer,
        updated_at = NOW()
    WHERE id = p_item_id;

    RETURN v_offer_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION kvota.add_jsonb_offer(UUID, UUID, TEXT, DECIMAL, VARCHAR, INTEGER) TO authenticated;

-- Helper function to delete an offer
CREATE OR REPLACE FUNCTION kvota.delete_jsonb_offer(
    p_item_id UUID,
    p_offer_id TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_offers JSONB;
    v_new_offers JSONB;
    v_was_selected BOOLEAN := false;
    i INTEGER;
BEGIN
    SELECT price_offers INTO v_offers
    FROM kvota.quote_items
    WHERE id = p_item_id;

    v_new_offers := '[]'::jsonb;

    FOR i IN 0..jsonb_array_length(v_offers) - 1 LOOP
        IF (v_offers->i->>'id') = p_offer_id THEN
            -- Check if we're deleting the selected offer
            v_was_selected := (v_offers->i->>'is_selected')::boolean;
            -- Skip this one (delete it)
        ELSE
            v_new_offers := v_new_offers || (v_offers->i);
        END IF;
    END LOOP;

    -- Update with filtered array
    UPDATE kvota.quote_items
    SET
        price_offers = v_new_offers,
        -- Clear main fields if deleted offer was selected
        supplier_id = CASE WHEN v_was_selected THEN NULL ELSE supplier_id END,
        purchase_price_original = CASE WHEN v_was_selected THEN NULL ELSE purchase_price_original END,
        purchase_currency = CASE WHEN v_was_selected THEN NULL ELSE purchase_currency END,
        updated_at = NOW()
    WHERE id = p_item_id;

    RETURN v_was_selected;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION kvota.delete_jsonb_offer(UUID, TEXT) TO authenticated;

-- Track migration
INSERT INTO kvota.migrations (version, name, applied_at)
VALUES (145, 'item_price_offers_jsonb', NOW())
ON CONFLICT (version) DO NOTHING;
