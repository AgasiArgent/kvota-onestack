"""
TDD Tests for Invoice Scan Comparison on Quote Control Page.

Task: [86afb2hgf] - Invoice scan comparison feature
When the quote controller clicks checklist card #2 "Tseny KP <-> invojs zakupki",
it expands inline showing invoices. Clicking an invoice shows split-screen:
items data on left, PDF scan iframe on right.

New routes to be implemented in main.py:
  - GET /quote-control/{quote_id}/invoice-comparison
  - GET /quote-control/{quote_id}/invoice/{invoice_id}/detail

Modified:
  - Checklist card #2 becomes clickable with hx-get
  - JavaScript toggleInvoiceComparisonCard() function added

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the feature is implemented.
"""

import pytest
import os
import re
from uuid import uuid4
from unittest.mock import MagicMock, patch, AsyncMock


# ============================================================================
# Path constants
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


# ============================================================================
# Helpers
# ============================================================================

def _read_main_source():
    """Read main.py source without importing (avoids dependency issues)."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def make_uuid():
    return str(uuid4())


ORG_ID = make_uuid()
QUOTE_ID = make_uuid()
INVOICE_ID_1 = make_uuid()
INVOICE_ID_2 = make_uuid()
SUPPLIER_ID_1 = make_uuid()
SUPPLIER_ID_2 = make_uuid()
DOC_ID_1 = make_uuid()


# ============================================================================
# Mock Supabase (matches pattern from test_janna_checklist.py)
# ============================================================================

class MockSupabaseResponse:
    def __init__(self, data=None):
        self.data = data or []


class MockQueryBuilder:
    def __init__(self, data=None):
        self._data = data or []
        self._filters = {}

    def select(self, cols="*"):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def in_(self, col, vals):
        return self

    def is_(self, col, val):
        return self

    def order(self, col, **kwargs):
        return self

    def limit(self, count):
        return self

    @property
    def not_(self):
        return self

    def execute(self):
        result = self._data
        for col, val in self._filters.items():
            result = [r for r in result if r.get(col) == val]
        return MockSupabaseResponse(result)


class MockSupabase:
    def __init__(self):
        self._tables = {}

    def set_table_data(self, name, data):
        self._tables[name] = data

    def table(self, name):
        return MockQueryBuilder(self._tables.get(name, []))


# ============================================================================
# Test data factories
# ============================================================================

def make_invoice(invoice_id=None, quote_id=None, supplier_id=None,
                 invoice_number=None, currency="USD", **kwargs):
    """Create a mock invoice dict."""
    base = {
        "id": invoice_id or make_uuid(),
        "quote_id": quote_id or QUOTE_ID,
        "supplier_id": supplier_id or make_uuid(),
        "invoice_number": invoice_number or f"INV-{make_uuid()[:6]}",
        "currency": currency,
        "total_weight_kg": 100.0,
        "suppliers": {"name": "Test Supplier"},
    }
    base.update(kwargs)
    return base


def make_document(doc_id=None, entity_id=None, entity_type="supplier_invoice",
                  file_path="invoices/scan.pdf", **kwargs):
    """Create a mock document dict."""
    base = {
        "id": doc_id or make_uuid(),
        "entity_id": entity_id or make_uuid(),
        "entity_type": entity_type,
        "file_path": file_path,
        "file_name": "scan.pdf",
        "mime_type": "application/pdf",
    }
    base.update(kwargs)
    return base


def make_quote_item(item_id=None, quote_id=None, invoice_id=None,
                    product_name="Test Product", quantity=10,
                    purchase_price_original=100, purchase_currency="USD",
                    **kwargs):
    """Create a mock quote item dict."""
    base = {
        "id": item_id or make_uuid(),
        "quote_id": quote_id or QUOTE_ID,
        "invoice_id": invoice_id,
        "product_name": product_name,
        "quantity": quantity,
        "purchase_price_original": purchase_price_original,
        "purchase_currency": purchase_currency,
    }
    base.update(kwargs)
    return base


# ============================================================================
# 1. Route definition existence tests (source inspection)
# ============================================================================

class TestInvoiceComparisonRouteExists:
    """Verify that the invoice-comparison HTMX route is defined in main.py."""

    def test_invoice_comparison_route_defined(self):
        """GET /quote-control/{quote_id}/invoice-comparison route must exist."""
        source = _read_main_source()
        # Look for route decorator pattern
        assert re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\']',
            source,
        ), (
            "Route /quote-control/{quote_id}/invoice-comparison not found in main.py. "
            "This HTMX endpoint should return the list of invoices for inline expansion."
        )

    def test_invoice_comparison_is_get_handler(self):
        """The invoice-comparison route must be a GET handler (async or sync)."""
        source = _read_main_source()
        # After the @rt decorator, the next function def should be get or async get
        pattern = (
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\'].*?\)'
            r'\s+(?:async\s+)?def\s+get\s*\('
        )
        assert re.search(pattern, source, re.DOTALL), (
            "invoice-comparison route must be a GET handler (def get or async def get)"
        )


class TestInvoiceDetailRouteExists:
    """Verify that the invoice detail split-screen route is defined in main.py."""

    def test_invoice_detail_route_defined(self):
        """GET /quote-control/{quote_id}/invoice/{invoice_id}/detail route must exist."""
        source = _read_main_source()
        assert re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\']',
            source,
        ), (
            "Route /quote-control/{quote_id}/invoice/{invoice_id}/detail not found in main.py. "
            "This HTMX endpoint should return the split-screen view with items and scan."
        )

    def test_invoice_detail_is_get_handler(self):
        """The invoice detail route must be a GET handler."""
        source = _read_main_source()
        pattern = (
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\'].*?\)'
            r'\s+(?:async\s+)?def\s+get\s*\('
        )
        assert re.search(pattern, source, re.DOTALL), (
            "invoice detail route must be a GET handler"
        )


# ============================================================================
# 2. Checklist card #2 clickable with hx-get
# ============================================================================

class TestChecklistCard2Clickable:
    """
    Verify that checklist card #2 (Tseny KP <-> invojs) is rendered with
    hx-get pointing to the invoice-comparison route.
    """

    def test_checklist_rendering_has_hx_get_for_invoice_comparison(self):
        """
        The quote control page rendering must include hx-get or hx_get
        referencing invoice-comparison for checklist card #2.
        """
        source = _read_main_source()
        # Look for hx_get (Python FastHTML syntax) or hx-get with invoice-comparison
        has_htmx = (
            "invoice-comparison" in source
            and (
                "hx_get" in source
                or "hx-get" in source
            )
        )
        assert has_htmx, (
            "Checklist card #2 must have hx-get/hx_get attribute pointing to "
            "invoice-comparison route for HTMX inline expansion."
        )

    def test_checklist_card2_has_expansion_target(self):
        """
        There must be an expansion target div (e.g., id='invoice-comparison-details')
        where the HTMX response will be inserted.
        """
        source = _read_main_source()
        assert "invoice-comparison-details" in source, (
            "Must have a target div with id 'invoice-comparison-details' for HTMX "
            "swap of the invoice list."
        )

    def test_checklist_card2_has_cursor_pointer(self):
        """Card #2 should have cursor:pointer to indicate it is clickable."""
        source = _read_main_source()
        # Search in the area around checklist rendering for cursor pointer
        # on the invoice comparison card
        card2_area = re.search(
            r'invoice.comparison.*?cursor.*?pointer',
            source,
            re.DOTALL | re.IGNORECASE,
        )
        assert card2_area, (
            "Invoice comparison card should have cursor: pointer style "
            "to indicate it is clickable."
        )


# ============================================================================
# 3. JavaScript toggle function
# ============================================================================

class TestToggleJavaScriptFunction:
    """Verify the toggle JavaScript function exists in main.py source."""

    def test_toggle_function_defined(self):
        """toggleInvoiceComparisonCard JavaScript function must exist."""
        source = _read_main_source()
        assert "toggleInvoiceComparisonCard" in source, (
            "JavaScript function 'toggleInvoiceComparisonCard' not found in main.py. "
            "This function handles expand/collapse of the invoice comparison section."
        )

    def test_toggle_function_references_details_div(self):
        """Toggle function must reference the invoice-comparison-details div."""
        source = _read_main_source()
        # The JS function should manipulate the expansion div
        toggle_section = re.search(
            r'toggleInvoiceComparisonCard.*?invoice.comparison.details',
            source,
            re.DOTALL,
        )
        assert toggle_section, (
            "toggleInvoiceComparisonCard function must reference "
            "'invoice-comparison-details' div for expand/collapse."
        )


# ============================================================================
# 4. Invoice comparison route returns proper HTML with invoice data
# ============================================================================

class TestInvoiceComparisonRouteContent:
    """
    Test the invoice comparison route handler logic.
    Uses source inspection to verify the function queries the right tables
    and returns expected HTML structures.
    """

    def test_route_queries_invoices_table(self):
        """The invoice-comparison handler must query kvota.invoices."""
        source = _read_main_source()
        # Find the route handler section
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice-comparison route not found"
        handler_source = route_match.group(1)

        assert 'invoices' in handler_source, (
            "invoice-comparison handler must query the 'invoices' table"
        )

    def test_route_queries_documents_for_scan_status(self):
        """The handler must check documents table for scan attachments."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice-comparison route not found"
        handler_source = route_match.group(1)

        assert 'document' in handler_source.lower() or 'scan' in handler_source.lower(), (
            "invoice-comparison handler must check documents/scan status for each invoice"
        )

    def test_route_returns_invoice_number_in_html(self):
        """Handler must include invoice_number in the response HTML."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice-comparison route not found"
        handler_source = route_match.group(1)

        assert 'invoice_number' in handler_source, (
            "invoice-comparison handler must display invoice_number"
        )

    def test_route_shows_no_invoices_message(self):
        """When no invoices exist, handler should show a message."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice-comparison route not found"
        handler_source = route_match.group(1)

        # Should have a fallback message for empty invoice list
        has_empty_msg = (
            "Нет инвойсов" in handler_source
            or "нет инвойсов" in handler_source
            or "no invoices" in handler_source.lower()
            or "Инвойсы не найдены" in handler_source
        )
        assert has_empty_msg, (
            "Handler must show a message when no invoices found (e.g., 'Нет инвойсов поставщиков')"
        )

    def test_route_includes_hx_get_for_invoice_detail(self):
        """Each invoice row must have hx-get to load its detail view."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice-comparison route not found"
        handler_source = route_match.group(1)

        # Each invoice row should have hx_get or hx-get for the detail route
        has_detail_link = (
            "invoice" in handler_source
            and "detail" in handler_source
            and ("hx_get" in handler_source or "hx-get" in handler_source)
        )
        assert has_detail_link, (
            "Each invoice row in the comparison list must have hx-get "
            "pointing to the invoice detail route."
        )


# ============================================================================
# 5. Invoice detail route returns split-screen with iframe when scan exists
# ============================================================================

class TestInvoiceDetailRouteContent:
    """
    Test the invoice detail route handler returns split-screen layout.
    """

    def test_route_has_split_layout(self):
        """Invoice detail route must render a split-screen layout."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice detail route not found"
        handler_source = route_match.group(1)

        # Should use flex or grid for split layout (40% left, 60% right)
        has_split = (
            "40%" in handler_source
            or "60%" in handler_source
            or "grid-template-columns" in handler_source
            or ("flex" in handler_source and "width" in handler_source)
        )
        assert has_split, (
            "Invoice detail must have split-screen layout (40% items / 60% scan)"
        )

    def test_route_has_iframe_for_scan(self):
        """Invoice detail route must include an iframe element for displaying scan PDF."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice detail route not found"
        handler_source = route_match.group(1)

        # Should contain Iframe or iframe element
        has_iframe = (
            "Iframe" in handler_source
            or "iframe" in handler_source
            or "<iframe" in handler_source
        )
        assert has_iframe, (
            "Invoice detail must include an iframe for displaying the scan PDF/image"
        )

    def test_route_uses_signed_url_for_scan(self):
        """The handler must use signed URL from document_service for the scan."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice detail route not found"
        handler_source = route_match.group(1)

        has_signed_url = (
            "signed_url" in handler_source
            or "get_download_url" in handler_source
            or "create_signed_url" in handler_source
        )
        assert has_signed_url, (
            "Invoice detail must use signed URL from document_service "
            "(get_download_url or create_signed_url) for secure scan access"
        )

    def test_route_has_items_table(self):
        """The left side must contain an items table with product_name, quantity, price."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice detail route not found"
        handler_source = route_match.group(1)

        has_items_data = (
            "product_name" in handler_source
            and "quantity" in handler_source
            and ("purchase_price" in handler_source or "price" in handler_source)
        )
        assert has_items_data, (
            "Invoice detail left side must show items table with "
            "product_name, quantity, and purchase_price_original"
        )


# ============================================================================
# 6. Invoice detail shows placeholder when no scan uploaded
# ============================================================================

class TestInvoiceDetailNoScanPlaceholder:
    """
    When no scan document is uploaded for an invoice, the right side
    must show a placeholder message instead of an iframe.
    """

    def test_no_scan_placeholder_text_exists(self):
        """Handler must contain the 'Scan ne zagruzhen' placeholder text."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice detail route not found"
        handler_source = route_match.group(1)

        has_placeholder = (
            "Скан не загружен" in handler_source
            or "скан не загружен" in handler_source
        )
        assert has_placeholder, (
            "Invoice detail route must show 'Скан не загружен' placeholder "
            "when no scan document is uploaded for the invoice."
        )

    def test_conditional_scan_rendering(self):
        """Handler must conditionally render iframe vs placeholder based on scan existence."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice/\{invoice_id\}/detail["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice detail route not found"
        handler_source = route_match.group(1)

        # Must have conditional logic: if scan exists -> iframe, else -> placeholder
        has_conditional = (
            ("if" in handler_source and "scan" in handler_source.lower())
            or ("if" in handler_source and "document" in handler_source.lower())
            or ("if" in handler_source and "signed_url" in handler_source)
        )
        assert has_conditional, (
            "Handler must have conditional logic to show iframe when scan exists "
            "and placeholder 'Скан не загружен' when it does not."
        )


# ============================================================================
# 7. Scan status indicator in invoice list
# ============================================================================

class TestInvoiceListScanStatus:
    """
    Each invoice row in the comparison list should show scan status
    (whether a scan document has been uploaded).
    """

    def test_scan_status_indicator_in_source(self):
        """Invoice list rendering must include scan status per invoice."""
        source = _read_main_source()
        route_match = re.search(
            r'@rt\(["\']/?quote-control/\{quote_id\}/invoice-comparison["\'].*?\)'
            r'(.*?)(?=\n@rt\(|\nclass\s|\Z)',
            source,
            re.DOTALL,
        )
        assert route_match, "invoice-comparison route not found"
        handler_source = route_match.group(1)

        # Should have visual indicator for scan presence
        has_scan_indicator = (
            "скан" in handler_source.lower()
            or "scan" in handler_source.lower()
            or "document" in handler_source.lower()
        )
        assert has_scan_indicator, (
            "Invoice comparison list must show scan status for each invoice "
            "(e.g., 'Скан загружен' / 'Нет скана')."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
