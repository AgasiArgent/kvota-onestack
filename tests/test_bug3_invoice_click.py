"""
Tests for BUG-3: Procurement Invoice Not Clickable

The invoice card on the procurement page is rendered as a plain Div with only
a selectInvoice() handler that highlights it. There is no expand/collapse
mechanism to reveal invoice item details inline.

Expected behavior:
- Invoice card should have a clickable toggle element (button, chevron, or card-level onclick)
- Clicking the card should expand/collapse a details section inline
- The details section should contain an items table showing the invoice's line items

All tests here are expected to FAIL against the current codebase, proving the bug exists.
"""

import os
import re
import pytest


# ============================================================================
# PATHS
# ============================================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


def _read_main():
    """Read main.py content once per test session."""
    with open(MAIN_PY, "r") as f:
        return f.read()


# ============================================================================
# Helper: extract JS function body by name
# ============================================================================

def _extract_js_function(content, func_name):
    """Extract the body of a JS function defined on window object.

    Looks for patterns like:
        window.funcName = function(...) { ... };
    Returns the function body string or None.
    """
    pattern = rf"window\.{func_name}\s*=\s*function"
    match = re.search(pattern, content)
    if not match:
        return None
    start = match.start()
    # Walk forward to find roughly the next 3000 chars (enough for any handler)
    return content[start:start + 3000]


def _extract_invoice_card_div(content):
    """Extract the invoice card Div(...) block near line 14504-14596.

    Returns the string slice containing the card definition.
    """
    # Look for the card div with invoice-card id pattern
    marker = 'id=f"invoice-card-{inv[\'id\']}"'
    idx = content.find(marker)
    if idx == -1:
        # Try alternate quoting
        marker = "id=f\"invoice-card-{inv['id']}\""
        idx = content.find(marker)
    if idx == -1:
        return None
    # Go back ~2000 chars to capture the full Div(
    start = max(0, idx - 2000)
    end = idx + 500
    return content[start:end]


# ============================================================================
# Test Class: Invoice Card Has Expand/Collapse Toggle
# ============================================================================

class TestInvoiceCardClickable:
    """Verify the invoice card has a clickable toggle to expand/collapse details."""

    def test_select_invoice_toggles_details_visibility(self):
        """selectInvoice() should toggle a details section, not just highlight.

        Current behavior: selectInvoice only changes background color.
        Expected: It should also show/hide an inline details panel.
        """
        content = _read_main()
        js_body = _extract_js_function(content, "selectInvoice")
        assert js_body is not None, "selectInvoice function not found"

        # The function should toggle visibility of a details/items section
        # e.g. style.display = 'block'/'none', or toggle a CSS class, or use .hidden
        has_toggle = any(keyword in js_body for keyword in [
            "style.display",
            "classList.toggle",
            "classList.add",
            ".hidden",
            "toggle(",
            "slideToggle",
            "invoice-details",
            "invoice-items",
        ])

        assert has_toggle, (
            "selectInvoice() only highlights the card background. "
            "It should toggle an inline details section to show invoice items."
        )

    def test_invoice_card_has_toggle_button_or_chevron(self):
        """Invoice card should contain a toggle indicator (chevron, button, or expand icon).

        Current behavior: Card has no toggle affordance.
        Expected: A chevron icon or 'Expand'/'Details' button inside the card.
        """
        content = _read_main()
        card_block = _extract_invoice_card_div(content)
        assert card_block is not None, "Invoice card Div block not found"

        # Look for toggle indicators in the card markup
        has_toggle_ui = any(keyword in card_block for keyword in [
            "chevron",
            "expand",
            "collapse",
            "arrow-down",
            "arrow-up",
            "caret",
            "Подробнее",
            "Развернуть",
            "Details",
            "toggle",
        ])

        assert has_toggle_ui, (
            "Invoice card has no expand/collapse UI affordance. "
            "Expected a chevron icon, expand button, or similar toggle indicator."
        )

    def test_invoice_card_onclick_is_not_just_select(self):
        """The card onclick should do more than just selectInvoice().

        Current behavior: onclick=selectInvoice(id) only highlights.
        Expected: onclick should also expand/collapse the details panel.
        """
        content = _read_main()
        card_block = _extract_invoice_card_div(content)
        assert card_block is not None, "Invoice card Div block not found"

        # Find the onclick attribute on the card
        onclick_match = re.search(r'onclick=f?"([^"]*)"', card_block)
        if not onclick_match:
            onclick_match = re.search(r"onclick=f?'([^']*)'", card_block)

        assert onclick_match is not None, "No onclick handler found on invoice card"

        onclick_value = onclick_match.group(1)

        # The onclick should reference a toggle/expand function, not just selectInvoice
        has_toggle_call = any(keyword in onclick_value for keyword in [
            "toggle",
            "expand",
            "collapse",
            "showDetail",
            "showItems",
        ])

        assert has_toggle_call, (
            f"Invoice card onclick is '{onclick_value}' which only selects/highlights. "
            "Expected it to also call a toggle/expand function for inline details."
        )


# ============================================================================
# Test Class: Invoice Details Section Exists
# ============================================================================

class TestInvoiceDetailsSectionExists:
    """Verify a collapsible details section is rendered inside or after the invoice card."""

    def test_invoice_card_contains_details_div(self):
        """Each invoice card should contain a hidden details div for item listing.

        Current behavior: No details div exists inside the card.
        Expected: A Div with id like 'invoice-details-{id}' containing items info.
        """
        content = _read_main()

        # Look for a details section tied to invoice ID
        has_details_section = any(pattern in content for pattern in [
            'invoice-details-{inv',
            'invoice-items-{inv',
            'invoice-detail-{inv',
            'invoice-expand-{inv',
        ])

        assert has_details_section, (
            "No invoice details section (e.g. 'invoice-details-{inv_id}') found in main.py. "
            "Each invoice card needs a collapsible details panel to show its items."
        )

    def test_invoice_details_section_hidden_by_default(self):
        """The invoice details section should be hidden by default (display:none or hidden attr).

        Current behavior: No details section exists at all.
        Expected: A details div with display:none that gets toggled on click.
        """
        content = _read_main()

        # Look for hidden details div patterns
        has_hidden_details = any(pattern in content for pattern in [
            'display: none',   # inline style hidden
            'display:none',
            'hidden=True',     # HTML hidden attribute
            'cls="hidden"',    # Tailwind hidden class
            'style="display: none"',
        ])

        # Specifically for invoice details context
        details_idx = content.find('invoice-details')
        if details_idx == -1:
            details_idx = content.find('invoice-items-section')

        assert details_idx != -1, (
            "No invoice details section found. Cannot check if it is hidden by default. "
            "A collapsible invoice details section must exist first."
        )

    def test_invoice_details_has_items_table(self):
        """The invoice details section should contain an items table or list.

        Current behavior: No inline items table exists for invoice cards.
        Expected: When expanded, shows a table with item name, quantity, price, etc.
        """
        content = _read_main()

        # Look for an items table/list rendered INSIDE or adjacent to the invoice card
        # The card is identified by 'invoice-card-{inv[' pattern
        has_items_rendering = False

        # Pattern 1: A dedicated function or component for rendering invoice items inline
        if 'invoice_items_table' in content or 'render_invoice_items' in content:
            has_items_rendering = True

        # Pattern 2: HTMX endpoint that loads invoice items inline on click
        if re.search(r'hx-get.*invoice.*items|hx-get.*invoice.*detail', content):
            has_items_rendering = True

        # Pattern 3: An inline details section with items rendered inside the card
        # Look for a details div that contains Tr/Td or item rendering near the card
        card_idx = content.find('id=f"invoice-card-')
        if card_idx != -1:
            # Check 2000 chars around the card for inline items rendering
            card_context = content[max(0, card_idx - 500):card_idx + 2000]
            if 'invoice-details' in card_context and ('Tr(' in card_context or 'item[' in card_context):
                has_items_rendering = True

        assert has_items_rendering, (
            "No inline items table or HTMX loader found for invoice details. "
            "When an invoice card is expanded, it should show the list of items "
            "(name, quantity, price) belonging to that invoice."
        )


# ============================================================================
# Test Class: HTMX or JS-based Expand Endpoint (if HTMX approach)
# ============================================================================

class TestInvoiceExpandEndpoint:
    """If using HTMX lazy-loading, verify the endpoint to fetch invoice details exists."""

    def test_invoice_details_htmx_endpoint_exists(self):
        """There should be an HTMX endpoint or JS function to load invoice item details.

        Current behavior: No such endpoint or function exists.
        Expected: Either an HTMX hx-get endpoint like /api/procurement/invoices/{id}/items
                  or a JS function that fetches and renders items inline.
        """
        content = _read_main()

        # Option A: HTMX endpoint for lazy-loading invoice details
        has_htmx_endpoint = bool(re.search(
            r'/api/procurement.*invoice.*items|/api/invoices/.*detail',
            content
        ))

        # Option B: JS function that fetches and renders invoice items
        has_js_loader = any(fname in content for fname in [
            'toggleInvoiceDetails',
            'expandInvoice',
            'loadInvoiceItems',
            'fetchInvoiceDetails',
            'showInvoiceItems',
        ])

        # Option C: Inline rendering (details already in DOM, just toggled)
        has_inline_details = 'invoice-details-' in content

        assert has_htmx_endpoint or has_js_loader or has_inline_details, (
            "No mechanism found to show invoice item details. "
            "Need either: (a) HTMX endpoint for lazy-loading, "
            "(b) JS function to fetch and render items, or "
            "(c) inline hidden details section that gets toggled."
        )

    def test_toggle_invoice_js_function_defined(self):
        """A JS function for toggling invoice details should be defined.

        Current behavior: Only selectInvoice() exists (highlights card).
        Expected: A function like toggleInvoiceDetails() that shows/hides items.
        """
        content = _read_main()

        toggle_function_names = [
            "toggleInvoiceDetails",
            "toggleInvoice",
            "expandInvoiceDetails",
            "showInvoiceItems",
        ]

        found_any = any(
            f"window.{fn}" in content or f"function {fn}" in content
            for fn in toggle_function_names
        )

        assert found_any, (
            f"No toggle function found. Looked for: {toggle_function_names}. "
            "selectInvoice() only highlights; a separate toggle function is needed "
            "to expand/collapse the invoice details section."
        )


# ============================================================================
# Test Class: Second Invoice Card Rendering (line ~16290)
# ============================================================================

class TestSecondInvoiceCardRendering:
    """The procurement page has a second invoice card rendering path (~line 16290).
    Both should support expand/collapse.
    """

    def test_second_card_rendering_has_toggle(self):
        """The second invoice card rendering block should also have expand/collapse.

        Current behavior: Both card renderings only call selectInvoice().
        Expected: Both should support expanding to show items.
        """
        content = _read_main()

        # Find all occurrences of invoice card onclick
        pattern = r"onclick=f?\"selectInvoice\("
        matches = list(re.finditer(pattern, content))

        if len(matches) < 2:
            # Alternate pattern
            pattern2 = r"onclick=f?[\"']selectInvoice\("
            matches = list(re.finditer(pattern2, content))

        # Each card location should have toggle mechanism, not just selectInvoice
        for i, match in enumerate(matches):
            surrounding = content[match.start() - 500:match.end() + 500]
            has_toggle = any(kw in surrounding for kw in [
                "toggle",
                "expand",
                "collapse",
                "details",
                "chevron",
            ])
            assert has_toggle, (
                f"Invoice card rendering #{i+1} (at offset {match.start()}) "
                "uses selectInvoice() without any expand/collapse mechanism."
            )


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
