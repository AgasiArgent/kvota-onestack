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
# TEST CLASSES REMOVED (Phase 6C-1, 2026-04-20):
#   - TestProcurementUsesInvoicesTable
#   - TestInvoiceCompletionWorkflow
# These verified api_create_invoice / api_complete_invoice FastHTML handlers
# in main.py. Both handlers were archived to legacy-fasthtml/procurement_workspace.py
# as part of the FastHTML cleanup.
# ============================================================================


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
# TEST CLASS REMOVED (Phase 6C-2B-10c1, 2026-04-20):
#   - TestFinanceInvoicesTab
# This verified the /finance?tab=invoices page (finance_invoices_tab helper)
# in main.py. The helper was archived to legacy-fasthtml/finance_lifecycle.py
# along with the parent GET /finance handler.
# ============================================================================
