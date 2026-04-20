"""
Tests for Quote Documents Currency Invoices Section helper
(_render_currency_invoices_section). The /currency-invoices/* route area
was archived to legacy-fasthtml/currency_invoices.py during Phase 6C-2B-8
(2026-04-20), so the old TestGroupedRegistryStructure class was removed.
The section helper itself remains live in main.py.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


def _read_source():
    with open(MAIN_PY) as f:
        return f.read()


class TestCurrencyInvoicesSectionExists:
    """_render_currency_invoices_section helper exists and is called."""

    def test_helper_function_exists(self):
        """_render_currency_invoices_section must exist in main.py."""
        src = _read_source()
        assert "def _render_currency_invoices_section" in src, (
            "Helper function _render_currency_invoices_section must exist in main.py"
        )

    def test_helper_called_in_documents_route(self):
        """Documents GET handler must call _render_currency_invoices_section."""
        src = _read_source()
        marker = '@rt("/quotes/{quote_id}/documents")'
        idx = src.find(marker)
        assert idx != -1
        body = src[idx:idx + 8000]
        assert "_render_currency_invoices_section" in body, (
            "Documents GET handler must call _render_currency_invoices_section"
        )

    def test_helper_filters_verified_exported_only(self):
        """Section must only show status 'verified' or 'exported'."""
        src = _read_source()
        marker = "def _render_currency_invoices_section"
        idx = src.find(marker)
        assert idx != -1
        body = src[idx:idx + 3000]
        assert "verified" in body and "exported" in body, (
            "_render_currency_invoices_section must filter by status verified/exported"
        )

    def test_helper_hides_section_when_no_deal(self):
        """Section must return empty when no deal exists for quote."""
        src = _read_source()
        marker = "def _render_currency_invoices_section"
        idx = src.find(marker)
        assert idx != -1
        body = src[idx:idx + 3000]
        assert 'return ""' in body, (
            "_render_currency_invoices_section must return empty string when no deal"
        )

    def test_section_shows_empty_state_text(self):
        """When deal exists but no approved invoices, show muted text."""
        src = _read_source()
        assert "Нет утверждённых валютных инвойсов" in src, (
            "Section must show 'Нет утверждённых валютных инвойсов' empty state"
        )

    def test_invoice_cards_link_to_detail(self):
        """Approved invoice cards must link to /currency-invoices/{ci_id}."""
        src = _read_source()
        marker = "def _render_currency_invoices_section"
        idx = src.find(marker)
        body = src[idx:idx + 3000]
        assert "/currency-invoices/" in body, (
            "Invoice cards in section must link to /currency-invoices/{ci_id}"
        )
