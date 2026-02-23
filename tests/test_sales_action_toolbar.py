"""
TDD Tests for Persistent Action Toolbar in the Sales tab.

TASK: Move action buttons (Рассчитать, История версий, Валидация Excel, Удалить КП)
from "Позиции" sub-tab only into a persistent toolbar visible on BOTH Обзор and
Позиции sub-tabs.

CURRENT STATE:
- Action buttons are inside a Div(...) if subtab == "products" else None block
  (lines ~9280-9307) -- only visible on "Позиции" sub-tab
- No _sales_action_toolbar helper function exists

DESIRED STATE:
- New helper function _sales_action_toolbar() defined in main.py
- Toolbar rendered unconditionally between overview_subtabs() and sub-tab content
- Old action card removed from the subtab == "products" conditional block
- Toolbar has correct buttons with size="sm"
- Visual style: background #f8fafc, border-top/bottom #e5e7eb
- No duplicate btn-delete-quote id

Tests use SOURCE CODE ANALYSIS pattern (read main.py as text, no imports).
All tests should FAIL until the feature is implemented.
"""

import pytest
import os
import re

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source without importing it."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _read_main_lines():
    """Read main.py as a list of lines."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.readlines()


def _extract_overview_tab_section(source=None):
    """Extract the overview tab section from the quote detail GET handler.

    The overview tab is the return page_layout(...) block that includes
    quote_detail_tabs(quote_id, "overview"...).
    """
    if source is None:
        source = _read_main_source()
    marker = 'quote_detail_tabs(quote_id, "overview"'
    start = source.find(marker)
    assert start != -1, "Overview tab section not found in main.py"
    return_start = source.rfind("return page_layout(", 0, start)
    assert return_start != -1, "Could not find return page_layout before overview tab"
    next_route = source.find("\n@rt(", start)
    if next_route == -1:
        next_route = len(source)
    return source[return_start:next_route]


def _extract_toolbar_function(source=None):
    """Extract the _sales_action_toolbar function body from main.py."""
    if source is None:
        source = _read_main_source()
    func_start = source.find("def _sales_action_toolbar(")
    assert func_start != -1, (
        "_sales_action_toolbar function not found in main.py. "
        "This helper must be created to render the persistent action toolbar."
    )
    # Find the next top-level def to delimit the function
    func_end = source.find("\ndef ", func_start + 10)
    if func_end == -1:
        func_end = len(source)
    return source[func_start:func_end]


# ==============================================================================
# A. _sales_action_toolbar function existence and signature
# ==============================================================================

class TestToolbarFunctionExists:
    """A helper function _sales_action_toolbar must exist in main.py."""

    def test_sales_action_toolbar_function_defined(self):
        """Function _sales_action_toolbar() must be defined in main.py."""
        source = _read_main_source()
        assert "def _sales_action_toolbar(" in source, (
            "Function _sales_action_toolbar() must exist in main.py "
            "to render the persistent action toolbar for the Sales tab."
        )

    def test_toolbar_function_accepts_required_params(self):
        """_sales_action_toolbar must accept quote_id, workflow_status params."""
        source = _read_main_source()
        func_match = re.search(r"def _sales_action_toolbar\(([^)]+)\)", source)
        assert func_match is not None, (
            "_sales_action_toolbar function definition not found"
        )
        params = func_match.group(1)
        assert "quote_id" in params, (
            "_sales_action_toolbar must accept quote_id parameter"
        )
        assert "workflow_status" in params, (
            "_sales_action_toolbar must accept workflow_status parameter"
        )

    def test_toolbar_function_returns_div(self):
        """_sales_action_toolbar must return a Div (contains 'return Div(' or 'Div(')."""
        func_body = _extract_toolbar_function()
        assert "Div(" in func_body, (
            "_sales_action_toolbar must build and return a Div element "
            "containing the toolbar buttons."
        )


# ==============================================================================
# B. Toolbar has correct buttons
# ==============================================================================

class TestToolbarButtons:
    """The persistent toolbar must contain the correct action buttons."""

    def test_toolbar_has_calculate_button(self):
        """Toolbar must have a Рассчитать button."""
        func_body = _extract_toolbar_function()
        assert "Рассчитать" in func_body or "calculate" in func_body, (
            "_sales_action_toolbar must contain a 'Рассчитать' button."
        )

    def test_toolbar_has_version_history_button(self):
        """Toolbar must have an 'История версий' button."""
        func_body = _extract_toolbar_function()
        assert "История версий" in func_body, (
            "_sales_action_toolbar must contain an 'История версий' button."
        )

    def test_toolbar_has_delete_button(self):
        """Toolbar must have an 'Удалить КП' danger button."""
        func_body = _extract_toolbar_function()
        assert "Удалить КП" in func_body, (
            "_sales_action_toolbar must contain an 'Удалить КП' danger button."
        )

    def test_toolbar_has_validation_excel_conditional(self):
        """Toolbar must have a 'Валидация Excel' button (conditional on workflow_status)."""
        func_body = _extract_toolbar_function()
        assert "Валидация Excel" in func_body, (
            "_sales_action_toolbar must contain a 'Валидация Excel' button "
            "(conditionally shown based on workflow_status)."
        )

    def test_toolbar_has_quote_pdf_conditional(self):
        """Toolbar must have a 'КП PDF' button (conditional on workflow_status)."""
        func_body = _extract_toolbar_function()
        assert "КП PDF" in func_body, (
            "_sales_action_toolbar must contain a 'КП PDF' export button."
        )

    def test_toolbar_has_invoice_pdf_conditional(self):
        """Toolbar must have a 'Счёт PDF' button (conditional on workflow_status)."""
        func_body = _extract_toolbar_function()
        assert "Счёт PDF" in func_body, (
            "_sales_action_toolbar must contain a 'Счёт PDF' export button."
        )


# ==============================================================================
# C. Toolbar uses size="sm" buttons (compact style)
# ==============================================================================

class TestToolbarCompactStyle:
    """Toolbar buttons must use size='sm' for compact presentation."""

    def test_toolbar_buttons_use_size_sm(self):
        """All buttons in the toolbar must use size='sm' for compact style."""
        func_body = _extract_toolbar_function()
        # Count btn_link and btn calls vs size="sm" occurrences
        btn_calls = len(re.findall(r'btn_link\(|btn\(', func_body))
        sm_calls = len(re.findall(r'size="sm"|size=\'sm\'', func_body))
        assert btn_calls > 0, (
            "Toolbar must contain btn_link() or btn() calls."
        )
        assert sm_calls >= btn_calls, (
            f"Found {btn_calls} button calls but only {sm_calls} with size='sm'. "
            "All toolbar buttons must use size='sm' for compact presentation."
        )


# ==============================================================================
# D. Toolbar visual style
# ==============================================================================

class TestToolbarVisualStyle:
    """Toolbar must have the correct visual styling to be distinct from tabs."""

    def test_toolbar_has_light_background(self):
        """Toolbar must have a light gray background (#f8fafc)."""
        func_body = _extract_toolbar_function()
        assert "#f8fafc" in func_body, (
            "Toolbar must use background: #f8fafc for visual distinction "
            "from tab navigation and white page content."
        )

    def test_toolbar_has_border_top(self):
        """Toolbar must have a top border to separate from sub-tab pills."""
        func_body = _extract_toolbar_function()
        assert "border-top" in func_body, (
            "Toolbar must have a border-top to visually separate it from "
            "the sub-tab navigation (Обзор | Позиции) above."
        )

    def test_toolbar_has_border_bottom(self):
        """Toolbar must have a bottom border to separate from content below."""
        func_body = _extract_toolbar_function()
        assert "border-bottom" in func_body, (
            "Toolbar must have a border-bottom to visually separate it from "
            "the sub-tab content below."
        )


# ==============================================================================
# E. Toolbar rendered unconditionally in page_layout (between subtabs and content)
# ==============================================================================

class TestToolbarPlacement:
    """The toolbar must be called unconditionally in the overview tab's page_layout,
    positioned between overview_subtabs() and the sub-tab content blocks."""

    def test_toolbar_called_in_overview_section(self):
        """_sales_action_toolbar must be called in the overview tab page_layout."""
        section = _extract_overview_tab_section()
        assert "_sales_action_toolbar(" in section, (
            "The overview tab page_layout must call _sales_action_toolbar() "
            "to render the persistent action toolbar."
        )

    def test_toolbar_called_after_overview_subtabs(self):
        """_sales_action_toolbar call must appear AFTER overview_subtabs call."""
        section = _extract_overview_tab_section()
        subtabs_pos = section.find("overview_subtabs(")
        toolbar_pos = section.find("_sales_action_toolbar(")
        assert subtabs_pos != -1, "overview_subtabs() call not found in overview section"
        assert toolbar_pos != -1, "_sales_action_toolbar() call not found in overview section"
        assert toolbar_pos > subtabs_pos, (
            f"_sales_action_toolbar() (pos {toolbar_pos}) must appear AFTER "
            f"overview_subtabs() (pos {subtabs_pos}) in the page_layout call. "
            "Toolbar goes between sub-tab pills and content."
        )

    def test_toolbar_called_before_subtab_content(self):
        """_sales_action_toolbar call must appear BEFORE the sub-tab content blocks."""
        section = _extract_overview_tab_section()
        toolbar_pos = section.find("_sales_action_toolbar(")
        # The info subtab content starts with ОСНОВНАЯ ИНФОРМАЦИЯ
        info_pos = section.find("ОСНОВНАЯ ИНФОРМАЦИЯ")
        assert toolbar_pos != -1, "_sales_action_toolbar() call not found"
        assert info_pos != -1, "ОСНОВНАЯ ИНФОРМАЦИЯ not found in overview section"
        assert toolbar_pos < info_pos, (
            f"_sales_action_toolbar() (pos {toolbar_pos}) must appear BEFORE "
            f"the sub-tab content (ОСНОВНАЯ ИНФОРМАЦИЯ at pos {info_pos}). "
            "Toolbar is positioned between sub-tab pills and content."
        )

    def test_toolbar_not_conditional_on_subtab(self):
        """_sales_action_toolbar call must NOT be wrapped in a subtab conditional.
        It must be visible on both Обзор and Позиции sub-tabs."""
        section = _extract_overview_tab_section()
        # Find the line containing _sales_action_toolbar call
        toolbar_pos = section.find("_sales_action_toolbar(")
        assert toolbar_pos != -1, "_sales_action_toolbar() call not found"
        # Get context around the toolbar call (100 chars after)
        toolbar_context = section[toolbar_pos:toolbar_pos + 300]
        # It should NOT have 'if subtab ==' after the call on the same expression
        assert 'if subtab ==' not in toolbar_context.split('\n')[0], (
            "_sales_action_toolbar() must be called unconditionally, "
            "not wrapped in 'if subtab ==' conditional. "
            "The toolbar must be visible on both Обзор and Позиции sub-tabs."
        )


# ==============================================================================
# F. Old action card removed from products-only block
# ==============================================================================

class TestOldActionCardRemoved:
    """The old unified action card that was inside 'if subtab == \"products\"'
    must be removed. Buttons are now in the persistent toolbar."""

    def test_no_action_buttons_in_products_only_block(self):
        """The old action card with Рассчитать/История версий/Удалить КП
        must NOT be inside a subtab == 'products' conditional anymore."""
        source = _read_main_source()
        section = _extract_overview_tab_section(source)

        # Look for the old pattern: action card block guarded by subtab == "products"
        # The old code had a Div(...) with Рассчитать + История версий wrapped in
        # ) if subtab == "products" else None,
        #
        # After the change, the section around 'Unified action card ABOVE items table'
        # should be gone from the overview section. The toolbar is rendered separately.
        #
        # Check: no block in the overview section contains BOTH "Рассчитать" and
        # 'if subtab == "products"' on the same block.
        lines = section.split('\n')
        found_old_pattern = False
        for i, line in enumerate(lines):
            if 'subtab == "products"' in line and i > 0:
                # Look in the preceding 30 lines for action button text
                block_above = '\n'.join(lines[max(0, i-30):i+1])
                if "Рассчитать" in block_above or "История версий" in block_above:
                    found_old_pattern = True
                    break

        assert not found_old_pattern, (
            "Found action buttons (Рассчитать/История версий) still inside a "
            "'subtab == \"products\"' conditional block in the overview section. "
            "These buttons must be moved to _sales_action_toolbar() which is "
            "rendered unconditionally."
        )

    def test_no_delete_button_in_products_only_block(self):
        """'Удалить КП' button must NOT be inside a subtab == 'products' conditional."""
        source = _read_main_source()
        section = _extract_overview_tab_section(source)

        lines = section.split('\n')
        found_old_pattern = False
        for i, line in enumerate(lines):
            if 'subtab == "products"' in line and i > 0:
                block_above = '\n'.join(lines[max(0, i-30):i+1])
                if "Удалить КП" in block_above or "btn-delete-quote" in block_above:
                    found_old_pattern = True
                    break

        assert not found_old_pattern, (
            "Found 'Удалить КП' button still inside a 'subtab == \"products\"' "
            "conditional block. It must be in _sales_action_toolbar() instead."
        )


# ==============================================================================
# G. No duplicate btn-delete-quote id
# ==============================================================================

class TestNoDuplicateDeleteButton:
    """Only ONE instance of id='btn-delete-quote' should exist in the
    overview tab section (inside the toolbar, not duplicated)."""

    def test_single_btn_delete_quote_id_in_overview(self):
        """btn-delete-quote id must appear exactly once in the overview tab area."""
        section = _extract_overview_tab_section()
        count = section.count('id="btn-delete-quote"')
        # The toolbar is a function call, so btn-delete-quote won't appear
        # literally in the section. But the old inline one should be gone.
        # Check the entire main.py for duplicates within route context
        source = _read_main_source()
        # Count all occurrences of btn-delete-quote in the GET /quotes/{quote_id} handler
        handler_start = source.find('@rt("/quotes/{quote_id}")')
        assert handler_start != -1, "GET /quotes/{quote_id} route not found"
        next_route = source.find("\n@rt(", handler_start + 10)
        if next_route == -1:
            next_route = len(source)
        handler_section = source[handler_start:next_route]

        # Count inline occurrences (excluding function definitions elsewhere)
        inline_count = handler_section.count('id="btn-delete-quote"')
        assert inline_count <= 1, (
            f"Found {inline_count} occurrences of id='btn-delete-quote' in the "
            "GET /quotes/{{quote_id}} handler section. There must be at most 1 "
            "(inside _sales_action_toolbar, not duplicated inline)."
        )

    def test_btn_delete_quote_only_in_toolbar_function(self):
        """btn-delete-quote must exist inside _sales_action_toolbar, not inline."""
        source = _read_main_source()
        func_body = _extract_toolbar_function(source)
        assert 'btn-delete-quote' in func_body, (
            "btn-delete-quote must be inside _sales_action_toolbar function."
        )

        # Also verify it's NOT inline in the overview section directly
        section = _extract_overview_tab_section(source)
        # The section should not contain btn-delete-quote as a literal
        # (it would be inside the _sales_action_toolbar function, called but not inline)
        inline_in_section = section.count('id="btn-delete-quote"')
        assert inline_in_section == 0, (
            f"Found {inline_in_section} inline 'btn-delete-quote' in the overview section. "
            "It should only exist inside the _sales_action_toolbar function, "
            "not as inline code in the page_layout return block."
        )


# ==============================================================================
# H. Toolbar positioned correctly relative to other elements
# ==============================================================================

class TestToolbarPositionRelativeToElements:
    """Toolbar must be correctly positioned in the page structure:
    after workflow_progress_bar, after overview_subtabs, before content blocks."""

    def test_toolbar_after_workflow_progress_bar(self):
        """Toolbar must appear after workflow_progress_bar in page_layout."""
        section = _extract_overview_tab_section()
        progress_pos = section.find("workflow_progress_bar(")
        toolbar_pos = section.find("_sales_action_toolbar(")
        assert progress_pos != -1, "workflow_progress_bar() not found"
        assert toolbar_pos != -1, "_sales_action_toolbar() not found"
        assert toolbar_pos > progress_pos, (
            "Toolbar must appear after workflow_progress_bar in the page layout."
        )

    def test_toolbar_before_items_spreadsheet(self):
        """Toolbar must appear before items-spreadsheet content in page_layout."""
        section = _extract_overview_tab_section()
        toolbar_pos = section.find("_sales_action_toolbar(")
        # The spreadsheet is conditionally rendered for products subtab
        spreadsheet_pos = section.find("items-spreadsheet")
        assert toolbar_pos != -1, "_sales_action_toolbar() not found"
        assert spreadsheet_pos != -1, "items-spreadsheet not found"
        assert toolbar_pos < spreadsheet_pos, (
            "Toolbar must appear before items-spreadsheet in the page layout."
        )
