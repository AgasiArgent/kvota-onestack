-- Customer assignees: many-to-many link between customers and sales managers.
-- Per access-control steering: two sales managers can share a client (different
-- divisions of the same company) and both must see the customer AND each other's
-- quotes for that customer. A single manager_id column cannot express this.
--
-- customers.manager_id is NOT dropped — it becomes a display-only "lead manager"
-- for UI convenience (e.g. who to show in the customer list). Access logic uses
-- this junction table exclusively.

CREATE TABLE IF NOT EXISTS kvota.customer_assignees (
  customer_id UUID NOT NULL REFERENCES kvota.customers(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id)      ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by  UUID REFERENCES auth.users(id),
  PRIMARY KEY (customer_id, user_id)
);

-- Index for reverse lookup: "which customers is this user assigned to?"
-- Composite PK already covers (customer_id, user_id) lookups.
CREATE INDEX IF NOT EXISTS idx_customer_assignees_user_id
  ON kvota.customer_assignees(user_id);

COMMENT ON TABLE kvota.customer_assignees IS
  'Many-to-many: sales managers assigned to customers. All assignees are equal — no "primary" concept. See .kiro/steering/access-control.md.';

-- RLS: scoped through customer.organization_id via organization_members.
-- Application-level filters in queries.ts are the primary access control;
-- this RLS is a safety net against direct DB access from the frontend.
ALTER TABLE kvota.customer_assignees ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage customer assignees in their org"
  ON kvota.customer_assignees
  FOR ALL
  USING (
    customer_id IN (
      SELECT c.id
      FROM kvota.customers c
      JOIN kvota.organization_members om ON om.organization_id = c.organization_id
      WHERE om.user_id = auth.uid()
    )
  );

-- Backfill: copy every existing manager_id into customer_assignees.
-- Idempotent — re-running this migration is a no-op thanks to ON CONFLICT.
INSERT INTO kvota.customer_assignees (customer_id, user_id)
SELECT id, manager_id
FROM kvota.customers
WHERE manager_id IS NOT NULL
ON CONFLICT (customer_id, user_id) DO NOTHING;
