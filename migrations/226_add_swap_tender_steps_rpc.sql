-- Migration: 226_add_swap_tender_steps_rpc.sql
-- Description: Atomic swap of two tender routing chain steps within a single transaction.

CREATE OR REPLACE FUNCTION kvota.swap_tender_steps(
    p_step_a UUID,
    p_step_b UUID
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_order_a INTEGER;
    v_order_b INTEGER;
    v_org_a UUID;
    v_org_b UUID;
BEGIN
    -- Get current orders and org IDs
    SELECT step_order, organization_id INTO v_order_a, v_org_a
    FROM kvota.tender_routing_chain WHERE id = p_step_a;

    SELECT step_order, organization_id INTO v_order_b, v_org_b
    FROM kvota.tender_routing_chain WHERE id = p_step_b;

    IF v_order_a IS NULL OR v_order_b IS NULL THEN
        RAISE EXCEPTION 'One or both steps not found';
    END IF;

    IF v_org_a != v_org_b THEN
        RAISE EXCEPTION 'Steps belong to different organizations';
    END IF;

    -- Temporarily set one to a negative value to avoid unique constraint violation
    UPDATE kvota.tender_routing_chain SET step_order = -1 WHERE id = p_step_a;
    UPDATE kvota.tender_routing_chain SET step_order = v_order_a WHERE id = p_step_b;
    UPDATE kvota.tender_routing_chain SET step_order = v_order_b WHERE id = p_step_a;
END;
$$;

-- Grant execute to authenticated users (RLS on the table still applies for reads)
GRANT EXECUTE ON FUNCTION kvota.swap_tender_steps(UUID, UUID) TO authenticated;

COMMENT ON FUNCTION kvota.swap_tender_steps IS
    'Atomically swap step_order of two tender routing chain entries. Runs in a single transaction to prevent partial failures.';
