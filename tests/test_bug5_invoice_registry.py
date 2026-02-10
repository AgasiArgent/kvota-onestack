"""
Tests for BUG-5: Supplier Invoices Not Appearing in Registry

BUG: Procurement creates invoices in the `invoices` table (migration 123),
but the registry page at /supplier-invoices reads from `supplier_invoices`
table (migration 106) via supplier_invoice_service.py.

These are TWO DIFFERENT TABLES with incompatible schemas:

  invoices (procurement writes here):
    - quote_id, supplier_id, buyer_company_id, pickup_location_id
    - pickup_country, currency, total_weight_kg, total_volume_m3
    - status values: pending_procurement, pending_logistics, etc.

  supplier_invoices (registry reads here):
    - organization_id, supplier_id, invoice_number, invoice_date, due_date
    - total_amount, currency, status, notes, invoice_file_url, created_by
    - status values: pending, partially_paid, paid, overdue, cancelled

FIX REQUIRED: Procurement invoice creation (main.py:15586) must write to
`supplier_invoices` table, and the invoice data schema must be adapted
to match the `supplier_invoices` columns.

These tests are EXPECTED TO FAIL until the bug is fixed.
"""

import pytest
import os
import re
import ast

# Project root for reliable file access
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


# ============================================================================
# HELPER: Extract function body from main.py by function name
# ============================================================================

def get_function_body(func_name, max_chars=5000):
    """Extract a function body from main.py for inspection."""
    with open(MAIN_PY, "r") as f:
        content = f.read()
    marker = f"async def {func_name}" if f"async def {func_name}" in content else f"def {func_name}"
    start = content.find(marker)
    if start == -1:
        return None
    return content[start:start + max_chars]


# ============================================================================
# TEST CLASS: Invoice creation uses correct table
# ============================================================================

class TestProcurementInvoiceUsesCorrectTable:
    """
    Verify that procurement invoice creation writes to supplier_invoices,
    NOT to the invoices table.

    Currently FAILS because main.py:15586 uses supabase.table("invoices").
    """

    def test_invoice_creation_uses_supplier_invoices_table(self):
        """
        The api_create_invoice function must insert into 'supplier_invoices'
        table so that the registry at /supplier-invoices can find them.

        EXPECTED TO FAIL: Currently inserts into 'invoices' table.
        """
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found in main.py"

        # Find the insert statement within the function
        # The fix should change: supabase.table("invoices").insert(...)
        # to: supabase.table("supplier_invoices").insert(...)
        insert_pattern = r'\.table\("invoices"\)\.insert\('
        supplier_insert_pattern = r'\.table\("supplier_invoices"\)\.insert\('

        has_wrong_table = re.search(insert_pattern, func_body)
        has_correct_table = re.search(supplier_insert_pattern, func_body)

        assert has_correct_table is not None, (
            "api_create_invoice must insert into 'supplier_invoices' table, "
            "not 'invoices' table. The registry reads from supplier_invoices."
        )
        assert has_wrong_table is None, (
            "api_create_invoice still inserts into 'invoices' table. "
            "This causes invoices to not appear in the registry."
        )

    def test_invoice_count_query_uses_supplier_invoices_table(self):
        """
        The invoice count query (for generating invoice numbers) must also
        query from 'supplier_invoices' table for consistency.

        EXPECTED TO FAIL: Currently queries from 'invoices' table.
        """
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found in main.py"

        # The count query for invoice numbering should also use supplier_invoices
        count_pattern = r'\.table\("invoices"\)\.select\("id",\s*count="exact"\)'
        correct_count_pattern = r'\.table\("supplier_invoices"\)\.select\("id",\s*count="exact"\)'

        has_wrong_count = re.search(count_pattern, func_body)
        has_correct_count = re.search(correct_count_pattern, func_body)

        assert has_correct_count is not None, (
            "Invoice count query must use 'supplier_invoices' table "
            "to correctly count existing invoices in the registry."
        )
        assert has_wrong_count is None, (
            "Invoice count query still uses 'invoices' table. "
            "This counts from the wrong table."
        )


# ============================================================================
# TEST CLASS: Invoice data schema matches supplier_invoices table
# ============================================================================

class TestInvoiceDataMatchesSupplierInvoicesSchema:
    """
    Verify that the invoice_data dict constructed in api_create_invoice
    matches the supplier_invoices table schema (migration 106).

    supplier_invoices required columns:
      - organization_id (UUID, NOT NULL)
      - supplier_id (UUID, NOT NULL)
      - invoice_number (VARCHAR, NOT NULL)
      - invoice_date (DATE, NOT NULL)
      - total_amount (DECIMAL, NOT NULL)

    supplier_invoices optional columns:
      - due_date, currency, status, notes, invoice_file_url, created_by

    Currently FAILS because the invoice_data dict uses the invoices table
    schema (quote_id, buyer_company_id, pickup_location_id, etc.).
    """

    def test_invoice_data_includes_organization_id(self):
        """
        supplier_invoices requires organization_id (NOT NULL).
        The invoices table does NOT have this column.

        EXPECTED TO FAIL: Current invoice_data has no organization_id.
        """
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found"

        # Look for organization_id in the invoice_data dict construction
        # It should be between invoice_data = { and the closing }
        data_start = func_body.find("invoice_data = {")
        assert data_start != -1, "invoice_data dict not found in api_create_invoice"

        # Get the dict portion
        data_section = func_body[data_start:data_start + 800]

        assert '"organization_id"' in data_section or "'organization_id'" in data_section, (
            "invoice_data must include 'organization_id' field. "
            "The supplier_invoices table requires it (NOT NULL). "
            "Current code writes to invoices table which doesn't have this column."
        )

    def test_invoice_data_includes_invoice_date(self):
        """
        supplier_invoices requires invoice_date (DATE, NOT NULL).
        The invoices table does NOT have this column.

        EXPECTED TO FAIL: Current invoice_data has no invoice_date.
        """
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found"

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1, "invoice_data dict not found"

        data_section = func_body[data_start:data_start + 800]

        assert '"invoice_date"' in data_section or "'invoice_date'" in data_section, (
            "invoice_data must include 'invoice_date' field. "
            "The supplier_invoices table requires it (NOT NULL)."
        )

    def test_invoice_data_includes_total_amount(self):
        """
        supplier_invoices requires total_amount (DECIMAL, NOT NULL, > 0).
        The invoices table does NOT have this column (it tracks weight/volume instead).

        EXPECTED TO FAIL: Current invoice_data has no total_amount.
        """
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found"

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1, "invoice_data dict not found"

        data_section = func_body[data_start:data_start + 800]

        assert '"total_amount"' in data_section or "'total_amount'" in data_section, (
            "invoice_data must include 'total_amount' field. "
            "The supplier_invoices table requires it (NOT NULL, must be > 0)."
        )

    def test_invoice_data_includes_created_by(self):
        """
        supplier_invoices has created_by column to track who created the invoice.
        This is important for audit trail.

        EXPECTED TO FAIL: Current invoice_data has no created_by.
        """
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found"

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1, "invoice_data dict not found"

        data_section = func_body[data_start:data_start + 800]

        assert '"created_by"' in data_section or "'created_by'" in data_section, (
            "invoice_data must include 'created_by' field with the user ID. "
            "The supplier_invoices table has this column for audit purposes."
        )

    def test_invoice_data_does_not_include_invoices_only_columns(self):
        """
        After migration, invoice_data should NOT include columns that only
        exist in the invoices table (quote_id, buyer_company_id,
        pickup_location_id, total_weight_kg, total_volume_m3).

        These columns do not exist in supplier_invoices and would cause
        a database error.

        EXPECTED TO FAIL: Current invoice_data includes all of these columns.
        """
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found"

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1, "invoice_data dict not found"

        # Find the closing brace of the dict
        data_section = func_body[data_start:data_start + 800]

        # These columns exist in invoices but NOT in supplier_invoices
        invoices_only_columns = [
            "pickup_location_id",
            "pickup_country",
            "total_weight_kg",
            "total_volume_m3",
        ]

        found_wrong_columns = []
        for col in invoices_only_columns:
            if f'"{col}"' in data_section or f"'{col}'" in data_section:
                found_wrong_columns.append(col)

        assert len(found_wrong_columns) == 0, (
            f"invoice_data contains columns that don't exist in supplier_invoices table: "
            f"{found_wrong_columns}. These columns only exist in the invoices table. "
            f"Writing these to supplier_invoices would cause a database error."
        )


# ============================================================================
# TEST CLASS: Registry visibility after procurement creates invoice
# ============================================================================

class TestInvoiceRegistryVisibility:
    """
    End-to-end test: after procurement creates an invoice, it must be
    visible in the supplier invoices registry.

    The registry page calls supplier_invoice_service.get_all_invoices()
    which queries the supplier_invoices table. If procurement writes to
    the invoices table instead, the registry will show zero results.
    """

    def test_registry_reads_from_supplier_invoices_table(self):
        """
        Verify the supplier_invoice_service reads from supplier_invoices table.
        This is the read side of the bug -- it's already correct.
        """
        service_path = os.path.join(PROJECT_ROOT, "services", "supplier_invoice_service.py")
        with open(service_path, "r") as f:
            content = f.read()

        # The service correctly queries supplier_invoices
        assert 'table("supplier_invoices")' in content, (
            "supplier_invoice_service must read from 'supplier_invoices' table"
        )

    def test_procurement_and_registry_use_same_table(self):
        """
        The table that procurement writes to must be the same table
        that the registry reads from. Otherwise invoices disappear.

        EXPECTED TO FAIL: procurement writes to 'invoices',
        registry reads from 'supplier_invoices'.
        """
        # Check what table procurement writes to
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found"

        # Extract the table name from the insert statement
        insert_match = re.search(r'\.table\("(\w+)"\)\.insert\(', func_body)
        assert insert_match is not None, "No insert statement found in api_create_invoice"
        write_table = insert_match.group(1)

        # Check what table the registry reads from
        service_path = os.path.join(PROJECT_ROOT, "services", "supplier_invoice_service.py")
        with open(service_path, "r") as f:
            service_content = f.read()

        # The get_all_invoices function reads from supplier_invoices
        assert 'table("supplier_invoices")' in service_content, (
            "Registry service must read from supplier_invoices"
        )

        # The write table and read table MUST match
        assert write_table == "supplier_invoices", (
            f"TABLE MISMATCH: Procurement writes to '{write_table}' but "
            f"registry reads from 'supplier_invoices'. "
            f"Invoices created in procurement will never appear in the registry. "
            f"Fix: Change api_create_invoice to write to 'supplier_invoices'."
        )


# ============================================================================
# TEST CLASS: Invoice update handler uses correct table
# ============================================================================

class TestInvoiceUpdateUsesCorrectTable:
    """
    Verify that invoice update (PATCH) also uses supplier_invoices table.
    """

    def test_invoice_update_uses_supplier_invoices_table(self):
        """
        The api_update_invoice function must update in 'supplier_invoices'
        table, not 'invoices' table.

        EXPECTED TO FAIL: Currently updates 'invoices' table.
        """
        func_body = get_function_body("api_update_invoice")
        assert func_body is not None, "api_update_invoice function not found in main.py"

        # Look for the update statement
        wrong_update = re.search(r'\.table\("invoices"\)\.update\(', func_body)
        correct_update = re.search(r'\.table\("supplier_invoices"\)\.update\(', func_body)

        assert correct_update is not None, (
            "api_update_invoice must update 'supplier_invoices' table. "
            "Currently updates 'invoices' which the registry never reads."
        )
        assert wrong_update is None, (
            "api_update_invoice still updates 'invoices' table."
        )


# ============================================================================
# TEST CLASS: Invoice delete handler uses correct table
# ============================================================================

class TestInvoiceDeleteUsesCorrectTable:
    """
    Verify that invoice delete also uses supplier_invoices table.
    """

    def test_invoice_delete_uses_supplier_invoices_table(self):
        """
        The api_delete_invoice function must delete from 'supplier_invoices'
        table, not 'invoices' table.

        EXPECTED TO FAIL: Currently deletes from 'invoices' table.
        """
        func_body = get_function_body("api_delete_invoice")
        if func_body is None:
            pytest.skip("api_delete_invoice function not found")

        # Look for delete and related query patterns
        wrong_table_refs = re.findall(r'\.table\("invoices"\)', func_body)
        correct_table_refs = re.findall(r'\.table\("supplier_invoices"\)', func_body)

        assert len(correct_table_refs) > 0, (
            "api_delete_invoice must reference 'supplier_invoices' table. "
            "Currently references 'invoices' which is the wrong table."
        )
        assert len(wrong_table_refs) == 0, (
            f"api_delete_invoice still has {len(wrong_table_refs)} references to 'invoices' table."
        )


# ============================================================================
# TEST CLASS: Complete procurement handler uses correct table
# ============================================================================

class TestCompleteProcurementUsesCorrectTable:
    """
    Verify that complete procurement also uses supplier_invoices table.
    """

    def test_complete_procurement_queries_supplier_invoices(self):
        """
        The api_complete_procurement function queries invoices for the quote.
        It must query from 'supplier_invoices' table.

        EXPECTED TO FAIL: Currently queries 'invoices' table.
        """
        func_body = get_function_body("api_complete_procurement")
        if func_body is None:
            pytest.skip("api_complete_procurement function not found")

        # Look for table references
        wrong_refs = re.findall(r'\.table\("invoices"\)', func_body)
        correct_refs = re.findall(r'\.table\("supplier_invoices"\)', func_body)

        assert len(correct_refs) > 0, (
            "api_complete_procurement must reference 'supplier_invoices' table."
        )
        # Allow that some refs may be to other tables like quote_items
        # But the direct invoices queries should use supplier_invoices
        if wrong_refs:
            assert len(wrong_refs) == 0, (
                f"api_complete_procurement still has {len(wrong_refs)} references "
                f"to 'invoices' table. Should use 'supplier_invoices'."
            )


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
