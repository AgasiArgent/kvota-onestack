"""
Tests for Invoice Architecture: Two-Table Design

Architecture (see BUSINESS_LOGIC.md):
  - `invoices` = procurement workflow groupings (quote-scoped)
  - `supplier_invoices` = finance payment registry (org-scoped)

These are SEPARATE tables serving DIFFERENT business purposes.
Procurement CRUD uses `invoices`. Finance tracking uses `supplier_invoices`.
"""

import pytest
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


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
# TEST CLASS: Procurement uses invoices table (workflow)
# ============================================================================

class TestProcurementUsesInvoicesTable:
    """
    Procurement CRUD must use the `invoices` table (workflow groupings),
    NOT `supplier_invoices` (finance registry).
    """

    def test_invoice_creation_uses_invoices_table(self):
        """api_create_invoice must insert into 'invoices' table."""
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None, "api_create_invoice function not found in main.py"

        has_invoices = re.search(r'\.table\("invoices"\)\.insert\(', func_body)
        has_supplier_invoices = re.search(r'\.table\("supplier_invoices"\)\.insert\(', func_body)

        assert has_invoices is not None, (
            "api_create_invoice must insert into 'invoices' table (procurement workflow)."
        )
        assert has_supplier_invoices is None, (
            "api_create_invoice must NOT insert into 'supplier_invoices' table. "
            "That table is for finance payment tracking, not procurement workflow."
        )

    def test_invoice_data_includes_quote_id(self):
        """invoices table requires quote_id (NOT NULL, FK to quotes)."""
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1, "invoice_data dict not found"
        data_section = func_body[data_start:data_start + 800]

        assert '"quote_id"' in data_section or "'quote_id'" in data_section, (
            "invoice_data must include 'quote_id'. "
            "The invoices table is quote-scoped (required FK)."
        )

    def test_invoice_data_does_not_include_organization_id(self):
        """invoices table has no organization_id column (that's supplier_invoices)."""
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1
        data_section = func_body[data_start:data_start + 800]

        assert '"organization_id"' not in data_section, (
            "invoice_data must NOT include 'organization_id'. "
            "That column belongs to supplier_invoices, not invoices."
        )

    def test_invoice_data_does_not_include_total_amount(self):
        """invoices table has no total_amount column (amounts are on quote_items)."""
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1
        data_section = func_body[data_start:data_start + 800]

        assert '"total_amount"' not in data_section, (
            "invoice_data must NOT include 'total_amount'. "
            "The invoices table calculates totals from quote_items."
        )

    def test_invoice_status_uses_workflow_values(self):
        """invoices use workflow statuses (pending_procurement), not payment statuses (pending)."""
        func_body = get_function_body("api_create_invoice")
        assert func_body is not None

        data_start = func_body.find("invoice_data = {")
        assert data_start != -1
        data_section = func_body[data_start:data_start + 800]

        assert '"pending_procurement"' in data_section or "'pending_procurement'" in data_section, (
            "invoice_data status must be 'pending_procurement' (workflow status), "
            "not 'pending' (payment status)."
        )


# ============================================================================
# TEST CLASS: Invoice completion uses workflow statuses
# ============================================================================

class TestInvoiceCompletionWorkflow:
    """Verify invoice completion sets workflow status, not payment status."""

    def test_complete_invoice_sets_workflow_status(self):
        """Completing an invoice should set pending_logistics, not partially_paid."""
        func_body = get_function_body("api_complete_invoice")
        assert func_body is not None, "api_complete_invoice not found"

        # Should NOT set payment status
        assert '"partially_paid"' not in func_body, (
            "Invoice completion must NOT set status to 'partially_paid'. "
            "That's a payment status for supplier_invoices. "
            "Use workflow status like 'pending_logistics'."
        )

    def test_complete_invoice_sets_procurement_completed_fields(self):
        """Completing should set procurement_completed_at and procurement_completed_by."""
        func_body = get_function_body("api_complete_invoice")
        assert func_body is not None

        assert "procurement_completed_at" in func_body, (
            "Invoice completion must set procurement_completed_at timestamp."
        )
        assert "procurement_completed_by" in func_body, (
            "Invoice completion must set procurement_completed_by user ID."
        )


# ============================================================================
# TEST CLASS: Finance registry uses supplier_invoices table
# ============================================================================

class TestFinanceRegistryUsesSupplierInvoices:
    """
    The supplier_invoice_service correctly reads from supplier_invoices.
    This is the finance side — separate from procurement.
    """

    def test_service_reads_from_supplier_invoices(self):
        """supplier_invoice_service must read from supplier_invoices table."""
        service_path = os.path.join(PROJECT_ROOT, "services", "supplier_invoice_service.py")
        with open(service_path, "r") as f:
            content = f.read()

        assert 'table("supplier_invoices")' in content, (
            "supplier_invoice_service must read from 'supplier_invoices' table"
        )

    def test_service_does_not_read_from_invoices(self):
        """supplier_invoice_service must NOT read from invoices table."""
        service_path = os.path.join(PROJECT_ROOT, "services", "supplier_invoice_service.py")
        with open(service_path, "r") as f:
            content = f.read()

        assert '.table("invoices")' not in content, (
            "supplier_invoice_service must NOT read from 'invoices' table. "
            "It should only use 'supplier_invoices'."
        )


# ============================================================================
# TEST CLASS: Finance invoices tab reads from invoices table
# ============================================================================

class TestFinanceInvoicesTab:
    """
    The /finance?tab=invoices page should read from the invoices table
    (showing procurement workflow invoices in the registry view).
    """

    def test_finance_invoices_tab_exists(self):
        """The finance page must have an invoices tab."""
        with open(MAIN_PY, "r") as f:
            content = f.read()

        assert "tab=invoices" in content or 'tab == "invoices"' in content, (
            "Finance page must have an invoices tab"
        )
