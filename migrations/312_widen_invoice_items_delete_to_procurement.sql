-- Migration 312: widen invoice_items DELETE RLS to include procurement roles
--
-- Background: MOZ-108. The X cross on invoice_items rows in
-- procurement-handsontable calls unassignInvoiceItem() which DELETEs from
-- kvota.invoice_items. Existing RLS allowed only `admin` and
-- `head_of_procurement` to delete — regular `procurement` users got 0 rows
-- affected with no PostgREST error (200 OK, empty body), so the frontend
-- silently showed a success toast while the row remained in the DB.
--
-- INSERT and UPDATE on the same table are already open to `procurement` and
-- `procurement_senior`, so DELETE was the only inconsistent gate. Org scope
-- (`organization_id IN (...)`) is preserved — no cross-org widening.

DROP POLICY IF EXISTS invoice_items_delete ON kvota.invoice_items;

CREATE POLICY invoice_items_delete ON kvota.invoice_items
  FOR DELETE
  USING (
    organization_id IN (
      SELECT ur.organization_id
      FROM kvota.user_roles ur
      JOIN kvota.roles r ON r.id = ur.role_id
      WHERE ur.user_id = auth.uid()
        AND r.slug IN (
          'admin',
          'procurement',
          'procurement_senior',
          'head_of_procurement'
        )
    )
  );

NOTIFY pgrst, 'reload schema';
