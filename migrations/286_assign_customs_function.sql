-- Migration 286: RPC function for customs auto-assignment with advisory lock.
-- Part of Wave 1 Task 7.2 of logistics-customs-redesign spec.
--
-- Least-loaded strategy: pick the customs user with fewest open
-- (assigned_customs_user = user AND customs_completed_at IS NULL) invoices,
-- deterministic tiebreak on user_id.
--
-- Concurrency: pg_advisory_xact_lock per-org serialises customs assignment
-- calls within the same organisation (prevents two concurrent workflow
-- transitions from picking the same least-loaded user under READ COMMITTED).
-- Design §3.4.
--
-- Returns a result row per invoice: (invoice_id, assigned_user_id, matched)
-- Caller uses this to compute quote-level summary + notify.

CREATE OR REPLACE FUNCTION kvota.assign_customs_invoices_for_quote(
    p_quote_id UUID
)
RETURNS TABLE (
    invoice_id UUID,
    assigned_user_id UUID,
    matched BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_org_id UUID;
    v_lock_key BIGINT;
    v_invoice RECORD;
    v_user_id UUID;
    v_sla_hours INT;
    v_now TIMESTAMPTZ := now();
BEGIN
    -- Resolve org for the quote
    SELECT organization_id INTO v_org_id
    FROM kvota.quotes
    WHERE id = p_quote_id;

    IF v_org_id IS NULL THEN
        RAISE EXCEPTION 'Quote % not found', p_quote_id;
    END IF;

    -- Advisory lock on (customs_assign, org) — per-org serialisation.
    -- hashtext() returns int4; cast to int8 per pg_advisory_xact_lock signature.
    v_lock_key := hashtext('customs_assign:' || v_org_id::text)::BIGINT;
    PERFORM pg_advisory_xact_lock(v_lock_key);

    -- Iterate invoices needing customs assignment
    FOR v_invoice IN
        SELECT id, customs_sla_hours
        FROM kvota.invoices
        WHERE quote_id = p_quote_id
          AND customs_completed_at IS NULL
          AND assigned_customs_user IS NULL
    LOOP
        -- Least-loaded customs user in this org
        SELECT ur.user_id INTO v_user_id
        FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
        LEFT JOIN kvota.invoices i
            ON i.assigned_customs_user = ur.user_id
           AND i.customs_completed_at IS NULL
        WHERE r.slug = 'customs'
          AND ur.organization_id = v_org_id
        GROUP BY ur.user_id
        ORDER BY COUNT(i.id) ASC, ur.user_id ASC
        LIMIT 1;

        v_sla_hours := COALESCE(v_invoice.customs_sla_hours, 72);

        IF v_user_id IS NOT NULL THEN
            UPDATE kvota.invoices
               SET assigned_customs_user = v_user_id,
                   customs_assigned_at = v_now,
                   customs_deadline_at = v_now + (v_sla_hours || ' hours')::INTERVAL
             WHERE id = v_invoice.id;

            invoice_id := v_invoice.id;
            assigned_user_id := v_user_id;
            matched := true;
            RETURN NEXT;
        ELSE
            -- No customs user in org — leave unassigned, will appear in
            -- head_of_customs "Неназначенные" inbox
            invoice_id := v_invoice.id;
            assigned_user_id := NULL;
            matched := false;
            RETURN NEXT;
        END IF;
    END LOOP;

    RETURN;
END;
$$;

COMMENT ON FUNCTION kvota.assign_customs_invoices_for_quote IS
    'Auto-assign customs users to invoices of a quote using least-loaded strategy. Per-org advisory lock ensures concurrent workflow transitions serialise. Returns one row per invoice.';

-- Grant execute to authenticated (callers check role in application layer)
GRANT EXECUTE ON FUNCTION kvota.assign_customs_invoices_for_quote(UUID) TO authenticated;

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (286, '286_assign_customs_function', now())
ON CONFLICT (id) DO NOTHING;
