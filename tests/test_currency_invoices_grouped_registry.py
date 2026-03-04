"""
Tests for Currency Invoices Grouped Registry and
Quote Documents Currency Invoices Section.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


def _read_source():
    with open(MAIN_PY) as f:
        return f.read()


class TestGroupedRegistryStructure:
    """Registry groups CI by quote, not flat list."""

    def test_registry_fetches_all_deals(self):
        """Registry must fetch deals table to include 0-invoice quotes."""
        src = _read_source()
        marker = 'def get(session):\n    """Currency invoices registry'
        idx = src.find(marker)
        assert idx != -1
        body = src[idx:idx + 4000]
        assert '.table("deals")' in body, (
            "Registry handler must fetch deals table to include quotes with 0 invoices"
        )

    def test_registry_uses_group_separator_class(self):
        """Registry must use group-separator Tr rows for quote headers."""
        src = _read_source()
        marker = 'def get(session):\n    """Currency invoices registry'
        idx = src.find(marker)
        body = src[idx:idx + 8000]
        assert "group-separator" in body, "Registry must use group-separator CSS class"

    def test_registry_shows_quote_idn_in_header(self):
        """Quote group header must include idn_quote."""
        src = _read_source()
        marker = 'def get(session):\n    """Currency invoices registry'
        idx = src.find(marker)
        body = src[idx:idx + 8000]
        assert "idn_quote" in body, "Registry must reference idn_quote for quote header"

    def test_registry_handles_zero_invoice_quote(self):
        """Registry must emit placeholder for quotes with no invoices."""
        src = _read_source()
        assert "Нет валютных инвойсов" in src, (
            "Registry must include 'Нет валютных инвойсов' placeholder for empty quote groups"
        )

    def test_registry_colspan_matches_column_count(self):
        """Group-separator row colspan must match table column count (8)."""
        src = _read_source()
        marker = 'def get(session):\n    """Currency invoices registry'
        idx = src.find(marker)
        body = src[idx:idx + 8000]
        assert 'colspan="8"' in body, (
            "Group separator row must have colspan matching 8 table columns"
        )

    def test_registry_sorts_within_group_by_segment(self):
        """Invoices within each group should be sorted by segment (EURTR first)."""
        src = _read_source()
        marker = 'def get(session):\n    """Currency invoices registry'
        idx = src.find(marker)
        body = src[idx:idx + 8000]
        assert "EURTR" in body and "TRRU" in body, (
            "Registry must define segment sort order (EURTR first, TRRU second)"
        )

    def test_registry_dropped_deal_column(self):
        """Grouped registry should not have a 'Сделка' column header."""
        src = _read_source()
        marker = 'def get(session):\n    """Currency invoices registry'
        idx = src.find(marker)
        body = src[idx:idx + 8000]
        # The table headers should NOT contain "Сделка" since deal# is redundant when grouped
        thead_start = body.find("Thead(")
        if thead_start != -1:
            thead_block = body[thead_start:thead_start + 600]
            assert "Сделка" not in thead_block, (
                "Grouped registry should not have 'Сделка' column — redundant when grouped by quote"
            )


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
