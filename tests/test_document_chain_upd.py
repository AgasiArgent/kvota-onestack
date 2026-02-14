"""
TDD Tests for Document Chain + UPD Support (P2.6 + P2.10)

These tests define expected behavior for:
- P2.10 Part 1: Adding 'upd' document type to document_service.py
- P2.6: Supplier invoice document count column + invoice detail documents section
- P2.10 Part 2: Document chain visualization on quote detail

Current state: Features NOT implemented yet.
These tests MUST FAIL until the features are implemented.

Tests cover:
1. 'upd' in VALID_DOCUMENT_TYPES
2. 'upd' label in DOCUMENT_TYPE_LABELS
3. Migration adds 'upd' to CHECK constraint
4. /supplier-invoices page renders document count column
5. /supplier-invoices/{id} detail route has documents section
6. count_documents_for_entity works for supplier_invoice entity type
7. _build_document_chain returns proper structure
8. Chain groups documents correctly by entity_type
9. Chain handles quote with no documents (empty chain)
10. /quotes/{quote_id}/document-chain route exists
11. Quote detail has "Цепочка документов" tab
"""

import pytest
import re
import os
import glob
import uuid
from datetime import datetime


# ==============================================================================
# Path Constants
# ==============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "migrations")
DOCUMENT_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "document_service.py")


# ==============================================================================
# Helpers
# ==============================================================================

def _read_main_source():
    """Read main.py source code without importing (avoids heavy app deps)."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _read_document_service_source():
    """Read document_service.py source code."""
    with open(DOCUMENT_SERVICE_PY, "r", encoding="utf-8") as f:
        return f.read()


def _read_function_source(full_source, func_name):
    """
    Extract a top-level function body from source code.

    Returns the full function text from 'def func_name(' until the next
    top-level 'def ' or end of file.
    """
    pattern = rf'^def {func_name}\(.*?\n(.*?)(?=\ndef |\Z)'
    match = re.search(pattern, full_source, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    return match.group(0)


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# P2.10 Part 1: UPD Document Type
# ==============================================================================

class TestUPDDocumentType:
    """
    The 'upd' (Universal Transfer Document / Универсальный передаточный документ)
    must be added as a valid document type in document_service.py.
    """

    def test_upd_in_valid_document_types(self):
        """'upd' must be present in VALID_DOCUMENT_TYPES set."""
        # We import directly to verify the runtime set value
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        from services.document_service import VALID_DOCUMENT_TYPES

        assert "upd" in VALID_DOCUMENT_TYPES, (
            "VALID_DOCUMENT_TYPES must include 'upd' for Universal Transfer Document"
        )

    def test_upd_has_label_in_document_type_labels(self):
        """'upd' must have a Russian label in DOCUMENT_TYPE_LABELS."""
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        from services.document_service import DOCUMENT_TYPE_LABELS

        assert "upd" in DOCUMENT_TYPE_LABELS, (
            "DOCUMENT_TYPE_LABELS must include 'upd' with a Russian label"
        )
        label = DOCUMENT_TYPE_LABELS["upd"]
        assert label and len(label) > 0, "UPD label must not be empty"
        # Should contain 'УПД' in the label
        assert "УПД" in label, (
            f"UPD label should contain 'УПД', got: '{label}'"
        )

    def test_upd_validates_as_valid_document_type(self):
        """validate_document_type('upd') must return True."""
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        from services.document_service import validate_document_type

        assert validate_document_type("upd") is True, (
            "validate_document_type('upd') must return True"
        )

    def test_upd_label_via_get_document_type_label(self):
        """get_document_type_label('upd') must return a non-empty label containing 'УПД'."""
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        from services.document_service import get_document_type_label

        label = get_document_type_label("upd")
        # Without proper label, it falls back to the key itself: "upd"
        assert "УПД" in label, (
            f"get_document_type_label('upd') should return label with 'УПД', got: '{label}'"
        )


# ==============================================================================
# P2.10 Part 1: Migration for UPD CHECK constraint
# ==============================================================================

class TestUPDMigration:
    """
    A migration must update the document_type CHECK constraint in kvota.documents
    to include 'upd'.
    """

    def test_migration_file_exists_for_upd(self):
        """A migration file for adding 'upd' document type must exist in migrations/."""
        migration_files = glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))

        upd_migrations = [
            f for f in migration_files
            if "upd_document" in os.path.basename(f).lower()
            or "_add_upd" in os.path.basename(f).lower()
            or "_upd_type" in os.path.basename(f).lower()
        ]
        assert len(upd_migrations) > 0, (
            "A migration file for adding 'upd' document type must exist in migrations/ "
            "(e.g., 162_add_upd_document_type.sql)"
        )

    def test_migration_alters_document_type_check_constraint(self):
        """The UPD migration must alter the document_type CHECK constraint."""
        migration_files = glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))

        upd_migrations = [
            f for f in migration_files
            if "upd_document" in os.path.basename(f).lower()
            or "_add_upd" in os.path.basename(f).lower()
            or "_upd_type" in os.path.basename(f).lower()
        ]
        assert len(upd_migrations) > 0, "UPD migration file not found"

        # Read the migration file
        migration_content = ""
        for mf in upd_migrations:
            with open(mf, "r", encoding="utf-8") as f:
                migration_content += f.read()

        # Must contain DROP/ALTER for the CHECK constraint and add 'upd'
        assert "'upd'" in migration_content, (
            "UPD migration must include 'upd' value in CHECK constraint update"
        )
        assert "documents_document_type_check" in migration_content.lower() or "document_type" in migration_content.lower(), (
            "UPD migration must reference the document_type CHECK constraint"
        )


# ==============================================================================
# P2.6: Supplier Invoice Documents Column on List Page
# ==============================================================================

class TestSupplierInvoiceDocumentCount:
    """
    The /supplier-invoices list page table must include a document count column
    showing how many documents are attached to each invoice.
    """

    def _get_supplier_invoices_list_source(self):
        """Extract the supplier invoices list route handler source."""
        source = _read_main_source()
        # Find the GET /supplier-invoices handler
        match = re.search(
            r'@rt\("/supplier-invoices"\)\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL
        )
        if not match:
            pytest.fail("Could not find GET /supplier-invoices route in main.py")
        return match.group(0)

    def test_supplier_invoices_table_has_documents_header(self):
        """
        The supplier invoices table Thead must include a 'Документы' or 'Док.' column.
        """
        source = self._get_supplier_invoices_list_source()

        has_docs_header = (
            '"Документы"' in source
            or '"Док."' in source
            or '"Док"' in source
            or '"Файлы"' in source
        )
        assert has_docs_header, (
            "Supplier invoices table must have a 'Документы' (or similar) column header "
            "for document count display"
        )

    def test_supplier_invoices_imports_count_documents(self):
        """
        The supplier invoices list route must import or use
        count_documents_for_entity to count documents per invoice.
        """
        source = self._get_supplier_invoices_list_source()

        has_count_fn = (
            "count_documents_for_entity" in source
            or "document_count" in source
            or "doc_count" in source
        )
        assert has_count_fn, (
            "Supplier invoices list must use count_documents_for_entity or equivalent "
            "to show document count per invoice"
        )


# ==============================================================================
# P2.6: Supplier Invoice Detail Page Documents Section
# ==============================================================================

class TestSupplierInvoiceDetailDocuments:
    """
    The /supplier-invoices/{invoice_id} detail page must include a
    documents section using the existing _documents_section() pattern.
    """

    def _get_supplier_invoice_detail_source(self):
        """Extract the supplier invoice detail route handler source."""
        source = _read_main_source()
        match = re.search(
            r'@rt\("/supplier-invoices/\{invoice_id\}"\)\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL
        )
        if not match:
            pytest.fail("Could not find GET /supplier-invoices/{invoice_id} route in main.py")
        return match.group(0)

    def test_invoice_detail_has_documents_section(self):
        """
        The invoice detail page must call _documents_section() to render
        an attached documents section.
        """
        source = self._get_supplier_invoice_detail_source()

        has_docs = (
            "_documents_section(" in source
            or "documents_section(" in source
        )
        assert has_docs, (
            "Supplier invoice detail page must include _documents_section() "
            "for viewing and uploading invoice documents"
        )

    def test_invoice_detail_passes_supplier_invoice_entity_type(self):
        """
        The _documents_section must be called with entity_type='supplier_invoice'.
        """
        source = self._get_supplier_invoice_detail_source()

        has_entity_type = (
            '"supplier_invoice"' in source
            and "_documents_section(" in source
        )
        assert has_entity_type, (
            "Invoice detail documents section must pass entity_type='supplier_invoice'"
        )


# ==============================================================================
# P2.10 Part 2: _build_document_chain Helper
# ==============================================================================

class TestBuildDocumentChain:
    """
    The _build_document_chain(quote_id) helper function must:
    - Group documents from get_all_documents_for_quote() by stage
    - Return a dict with keys: quote, specification, supplier_invoice, upd, customs_declaration
    - Each key maps to a list of documents for that stage
    """

    def test_build_document_chain_function_exists(self):
        """_build_document_chain must be defined in main.py."""
        source = _read_main_source()

        assert "def _build_document_chain(" in source, (
            "_build_document_chain function must exist in main.py"
        )

    def test_build_document_chain_has_correct_stages(self):
        """
        _build_document_chain must reference all 5 chain stages:
        quote, specification, supplier_invoice, upd, customs_declaration
        """
        source = _read_main_source()
        func_source = _read_function_source(source, "_build_document_chain")

        assert func_source is not None, "_build_document_chain function not found"

        # Must reference all chain stage keys
        required_stages = ["quote", "specification", "supplier_invoice", "upd", "customs_declaration"]
        for stage in required_stages:
            assert f'"{stage}"' in func_source or f"'{stage}'" in func_source, (
                f"_build_document_chain must include stage key '{stage}'"
            )

    def test_build_document_chain_uses_get_all_documents_for_quote(self):
        """
        _build_document_chain must call get_all_documents_for_quote()
        to fetch all documents hierarchically via parent_quote_id.
        """
        source = _read_main_source()
        func_source = _read_function_source(source, "_build_document_chain")

        assert func_source is not None, "_build_document_chain function not found"
        assert "get_all_documents_for_quote" in func_source, (
            "_build_document_chain must use get_all_documents_for_quote() to fetch documents"
        )

    def test_build_document_chain_returns_dict_structure(self):
        """
        _build_document_chain must return a dict (not a list or tuple).
        Check that the function has return statement with dict-like structure.
        """
        source = _read_main_source()
        func_source = _read_function_source(source, "_build_document_chain")

        assert func_source is not None, "_build_document_chain function not found"

        # Should have a return with dict construction
        has_dict_return = (
            "return {" in func_source
            or "return chain" in func_source
            or "return result" in func_source
            or "return stages" in func_source
        )
        assert has_dict_return, (
            "_build_document_chain must return a dict mapping stages to document lists"
        )

    def test_build_document_chain_groups_upd_documents(self):
        """
        Documents with document_type='upd' must be grouped under the 'upd' stage.
        The function must check document_type for upd classification.
        """
        source = _read_main_source()
        func_source = _read_function_source(source, "_build_document_chain")

        assert func_source is not None, "_build_document_chain function not found"

        # Must reference 'upd' for grouping
        assert '"upd"' in func_source or "'upd'" in func_source, (
            "_build_document_chain must handle 'upd' document type for chain grouping"
        )


# ==============================================================================
# P2.10 Part 2: Document Chain Route
# ==============================================================================

class TestDocumentChainRoute:
    """
    Document chain content is now merged into the Documents tab.
    These tests verify the merged behavior.
    """

    def test_document_chain_rendered_in_documents_route(self):
        """
        The documents route must include document chain rendering.
        """
        source = _read_main_source()

        assert "_render_document_chain_section" in source or "_build_document_chain" in source, (
            "Documents route must render document chain content"
        )

    def test_document_chain_stages_exist_in_codebase(self):
        """
        The document chain must render all 5 chain stages: КП, Спецификация, Инвойс, УПД, ГТД
        """
        source = _read_main_source()

        stage_labels = ["КП", "Спецификация", "Инвойс", "УПД", "ГТД"]
        for label in stage_labels:
            assert label in source, (
                f"Document chain must display stage label '{label}'"
            )

    def test_no_separate_document_chain_route(self):
        """
        The standalone /document-chain route should NOT exist (merged into documents tab).
        """
        source = _read_main_source()

        assert '@rt("/quotes/{quote_id}/document-chain")' not in source, (
            "Standalone /document-chain route should be removed (merged into documents tab)"
        )


# ==============================================================================
# P2.10 Part 2: Quote Detail Tabs - Document Chain Tab
# ==============================================================================

class TestQuoteDetailDocumentChainTab:
    """
    Document chain is now merged into the Documents tab (no separate tab).
    Verify the merged behavior.
    """

    def _get_quote_detail_tabs_source(self):
        """Extract quote_detail_tabs function source."""
        source = _read_main_source()
        func_source = _read_function_source(source, "quote_detail_tabs")
        if not func_source:
            pytest.fail("Could not find quote_detail_tabs function in main.py")
        return func_source

    def test_quote_detail_tabs_has_documents_tab(self):
        """
        The tabs_config must include a 'documents' tab (merged with chain).
        """
        source = self._get_quote_detail_tabs_source()

        assert '"documents"' in source, (
            "quote_detail_tabs must include a 'documents' tab in tabs_config"
        )

    def test_quote_detail_tabs_no_separate_chain_tab(self):
        """
        No separate document_chain tab should exist (merged into documents).
        """
        source = self._get_quote_detail_tabs_source()

        assert '"document_chain"' not in source, (
            "Separate document_chain tab should be removed (merged into documents)"
        )

    def test_quote_detail_tabs_documents_label(self):
        """
        The documents tab should have label "Документы".
        """
        source = self._get_quote_detail_tabs_source()

        assert "Документы" in source, (
            'Documents tab must have label "Документы"'
        )


# ==============================================================================
# Edge Cases
# ==============================================================================

class TestDocumentChainEdgeCases:
    """Edge cases for document chain functionality."""

    def test_upd_in_allowed_types_for_supplier_invoice(self):
        """
        The get_allowed_document_types_for_entity('supplier_invoice')
        should include 'upd' in the list of allowed types.
        """
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        from services.document_service import get_allowed_document_types_for_entity

        allowed = get_allowed_document_types_for_entity("supplier_invoice")
        values = [t["value"] for t in allowed]

        assert "upd" in values, (
            "supplier_invoice entity should allow 'upd' document type "
            "since UPD is commonly attached to invoices"
        )

    def test_upd_in_allowed_types_for_quote(self):
        """
        The get_allowed_document_types_for_entity('quote')
        should include 'upd' since quotes aggregate all document types.
        """
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        from services.document_service import get_allowed_document_types_for_entity

        allowed = get_allowed_document_types_for_entity("quote")
        values = [t["value"] for t in allowed]

        assert "upd" in values, (
            "quote entity should allow 'upd' document type "
            "since quote aggregates all documents including UPDs"
        )

    def test_specification_signed_scan_still_valid(self):
        """
        Adding 'upd' must not break existing document types.
        'specification_signed_scan' must still be valid.
        """
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        from services.document_service import VALID_DOCUMENT_TYPES

        assert "specification_signed_scan" in VALID_DOCUMENT_TYPES, (
            "Existing 'specification_signed_scan' type must not be removed when adding 'upd'"
        )

    def test_build_document_chain_handles_empty_documents(self):
        """
        _build_document_chain must handle a quote with zero documents
        by returning a dict with empty lists for all stages.
        """
        source = _read_main_source()
        func_source = _read_function_source(source, "_build_document_chain")

        assert func_source is not None, (
            "_build_document_chain function must exist to handle empty documents case"
        )

        # The function must initialize all stage keys (even if empty)
        # This is verified by checking that default/initial values are set
        # Look for patterns like: {"quote": [], "specification": [], ...}
        # or chain = {"quote": [], ...} or stage initialization
        has_initialization = (
            '": []' in func_source
            or "= []" in func_source
            or "defaultdict" in func_source
            or ".get(" in func_source
            or ".setdefault(" in func_source
        )
        assert has_initialization, (
            "_build_document_chain must initialize all stage keys with empty lists "
            "to handle quotes with no documents"
        )

    def test_document_chain_supplier_invoice_column_includes_count(self):
        """
        The supplier invoices list page must show actual document count
        (not just a boolean/icon), i.e., it must render a number.
        """
        source = _read_main_source()

        # Find the supplier invoices list route
        match = re.search(
            r'@rt\("/supplier-invoices"\)\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL
        )
        assert match is not None, "Could not find GET /supplier-invoices route"

        handler_source = match.group(0)

        # Should call count_documents_for_entity for each invoice
        has_count = (
            "count_documents_for_entity" in handler_source
            or "doc_count" in handler_source
            or "document_count" in handler_source
        )
        assert has_count, (
            "Supplier invoices list must count documents per invoice for display"
        )
