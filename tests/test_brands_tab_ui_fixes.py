"""
Tests for Supplier Brands Tab UI Fixes (Designer Review)

Verifies 5 design deviations found during review of the "Brands" tab
on supplier detail pages:

1. Duplicate tabs fix: HTMX requests should return only tab_content, not full page
2. Add-brand button uses btn() helper instead of inline #6366f1 style
3. Empty state uses table-row pattern (Td with colspan, centered text)
4. Row action buttons use btn() helper instead of inline styles
5. Code deduplication: shared helper function for brand row rendering

Tests use source code analysis (no HTTP imports needed).
"""

import pytest
import re
import os
import ast
import textwrap

# Path constants (relative to project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code."""
    with open(MAIN_PY) as f:
        return f.read()


def _extract_function_source(func_name: str, source: str = None) -> str:
    """Extract a top-level function's source code from main.py by name.

    Finds `def func_name(` at the start of a line and grabs everything
    until the next top-level definition or end of file.
    """
    if source is None:
        source = _read_main_source()
    pattern = re.compile(
        rf'^(def {re.escape(func_name)}\(.*?)(?=\n(?:def |@rt\(|class |# ===)|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(source)
    assert match, f"Function '{func_name}' not found in main.py"
    return match.group(1)


def _extract_supplier_detail_handler(source: str = None) -> str:
    """Extract the supplier detail GET handler (route + function body)."""
    if source is None:
        source = _read_main_source()
    # The handler is @rt("/suppliers/{supplier_id}") followed by def get(...)
    pattern = re.compile(
        r'(@rt\("/suppliers/\{supplier_id\}"\)\s*'
        r'def get\(supplier_id.*?)(?=\n@rt\(|\nclass |\n# ===|\Z)',
        re.DOTALL,
    )
    match = pattern.search(source)
    assert match, "Supplier detail GET handler not found in main.py"
    return match.group(1)


# ==============================================================================
# 1. Duplicate Tabs Fix -- HTMX partial response
# ==============================================================================

class TestSupplierDetailHtmxPartialResponse:
    """Supplier detail GET handler must return only tab_content for HTMX requests.

    The customer detail handler (around line 31111) already implements this:
        if request and request.headers.get("HX-Request"):
            return tab_content

    The supplier detail handler must follow the same pattern.
    """

    def test_supplier_detail_handler_has_request_parameter(self):
        """Handler signature must include `request` parameter (needed for HX-Request check)."""
        handler = _extract_supplier_detail_handler()
        # Find the def line
        def_match = re.search(r'def get\((.*?)\):', handler)
        assert def_match, "Could not parse handler signature"
        params = def_match.group(1)
        assert "request" in params, (
            "Supplier detail GET handler must accept `request` parameter "
            "(needed to check HX-Request header). "
            "Current signature: def get({})".format(params)
        )

    def test_supplier_detail_handler_checks_hx_request_header(self):
        """Handler must check request.headers.get('HX-Request') to detect tab switches."""
        handler = _extract_supplier_detail_handler()
        assert "HX-Request" in handler, (
            "Supplier detail handler must check HX-Request header to return "
            "partial content for HTMX tab switches. Without this check, "
            "HTMX responses contain the full page_layout(), causing tabs-inside-tabs."
        )

    def test_supplier_detail_handler_returns_tab_content_for_htmx(self):
        """When HX-Request is detected, handler must return tab_content (not page_layout)."""
        handler = _extract_supplier_detail_handler()
        # Look for the pattern: if ... HX-Request ... return tab_content
        hx_block = re.search(
            r'if\s+.*HX-Request.*?return\s+(\w+)',
            handler,
            re.DOTALL,
        )
        assert hx_block, (
            "Handler must have: if request.headers.get('HX-Request'): return tab_content"
        )
        returned_var = hx_block.group(1)
        assert returned_var == "tab_content", (
            f"HTMX branch should return 'tab_content', but returns '{returned_var}'"
        )

    def test_hx_request_check_is_before_page_layout(self):
        """The HX-Request check must come BEFORE the page_layout() call."""
        handler = _extract_supplier_detail_handler()
        hx_pos = handler.find("HX-Request")
        layout_pos = handler.find("page_layout")
        assert hx_pos != -1, "HX-Request check not found"
        assert layout_pos != -1, "page_layout call not found"
        assert hx_pos < layout_pos, (
            "HX-Request check must come BEFORE page_layout() call, "
            "otherwise HTMX requests still get the full page."
        )

    def test_customer_detail_has_hx_request_pattern_as_reference(self):
        """Verify the customer detail handler has the pattern we expect to replicate."""
        source = _read_main_source()
        # Customer handler pattern
        assert re.search(
            r'def get\(customer_id.*request.*\).*?'
            r'if request.*HX-Request.*return tab_content',
            source,
            re.DOTALL,
        ), (
            "Customer detail handler reference pattern not found. "
            "This test validates the reference implementation exists."
        )


# ==============================================================================
# 2. Add-Brand Button Uses btn() Helper
# ==============================================================================

class TestAddBrandButtonUsesBtnHelper:
    """The add-brand form button must use the project's btn() helper,
    not inline styles with hardcoded background: #6366f1."""

    def test_no_inline_6366f1_background_in_brands_tab(self):
        """_supplier_brands_tab must NOT have inline background: #6366f1 style."""
        func_src = _extract_function_source("_supplier_brands_tab")
        # Look for the specific inline style pattern on the add button
        assert "#6366f1" not in func_src, (
            "_supplier_brands_tab contains inline '#6366f1' background style. "
            "The add-brand button should use btn() helper instead of "
            "style='... background: #6366f1 ...'."
        )

    def test_no_inline_6366f1_background_in_brands_list_partial(self):
        """_supplier_brands_list_partial must NOT have inline background: #6366f1 style."""
        func_src = _extract_function_source("_supplier_brands_list_partial")
        assert "#6366f1" not in func_src, (
            "_supplier_brands_list_partial contains inline '#6366f1' background style. "
            "Buttons should use btn() helper."
        )

    def test_add_brand_button_uses_btn_call(self):
        """The add-brand form should use btn(...) instead of raw Button with inline style."""
        func_src = _extract_function_source("_supplier_brands_tab")
        # The form should call btn() for the submit button
        assert re.search(r'\bbtn\s*\(', func_src), (
            "_supplier_brands_tab must use btn() helper for the add-brand button. "
            "Found raw Button with inline styles instead."
        )

    def test_add_brand_button_has_correct_label(self):
        """The add-brand button must have the label text present."""
        func_src = _extract_function_source("_supplier_brands_tab")
        assert "Добавить бренд" in func_src, (
            "Add-brand button must have label 'Добавить бренд'"
        )


# ==============================================================================
# 3. Empty State Consistency -- Table Row Pattern
# ==============================================================================

class TestEmptyStateTableRowPattern:
    """Empty state must use Tr(Td(..., colspan=..., style='text-align: center; padding: 2rem; color: #666;'))
    pattern consistent with contacts, contracts, and other tabs in the project.
    It should NOT use a standalone Div with a floating tag icon."""

    def test_brands_tab_empty_state_uses_td_with_colspan(self):
        """Empty state in _supplier_brands_tab must use Td with colspan attribute."""
        func_src = _extract_function_source("_supplier_brands_tab")
        # Look for the empty state -- it should be Tr(Td(... colspan ...))
        # The current bug uses Div(icon("tag"), P(...))
        has_td_colspan = bool(re.search(r'Td\(.*colspan', func_src, re.DOTALL))
        assert has_td_colspan, (
            "Empty state in _supplier_brands_tab must use Td with colspan "
            "for consistency with other tabs (contacts, contracts). "
            "Current implementation uses a standalone Div with icon('tag')."
        )

    def test_brands_tab_empty_state_has_centered_text(self):
        """Empty state must have text-align: center styling."""
        func_src = _extract_function_source("_supplier_brands_tab")
        # Check for the standard style pattern in the empty-state section
        empty_section = func_src[func_src.find("else"):]  # After the 'if brand_rows:' block
        assert "text-align: center" in empty_section or "text-align:center" in empty_section, (
            "Empty state must use 'text-align: center' styling, "
            "matching the project pattern: Tr(Td('...', colspan='3', "
            "style='text-align: center; padding: 2rem; color: #666;'))"
        )

    def test_brands_tab_empty_state_no_standalone_icon(self):
        """Empty state must NOT use a standalone floating tag icon."""
        func_src = _extract_function_source("_supplier_brands_tab")
        # Find the else block (empty state)
        else_pos = func_src.rfind("else:")
        assert else_pos != -1, "Could not find else block in _supplier_brands_tab"
        empty_block = func_src[else_pos:]
        # Should not have icon("tag", size=32) as a standalone element
        has_floating_icon = bool(re.search(r'icon\("tag".*size=32', empty_block))
        assert not has_floating_icon, (
            "Empty state should NOT have a floating icon('tag', size=32). "
            "Use the standard table-row empty state pattern instead."
        )

    def test_brands_list_partial_empty_state_uses_td_with_colspan(self):
        """Empty state in _supplier_brands_list_partial must also use Td with colspan."""
        func_src = _extract_function_source("_supplier_brands_list_partial")
        has_td_colspan = bool(re.search(r'Td\(.*colspan', func_src, re.DOTALL))
        assert has_td_colspan, (
            "Empty state in _supplier_brands_list_partial must use Td with colspan, "
            "consistent with other tabs."
        )

    def test_empty_state_matches_project_pattern(self):
        """Verify the project-wide pattern exists for reference."""
        source = _read_main_source()
        # The standard pattern used in customer contracts, specs, etc.
        pattern_count = len(re.findall(
            r'Tr\(Td\(".*?не найден.*?colspan.*?text-align:\s*center.*?padding:\s*2rem.*?color:\s*#666',
            source,
            re.IGNORECASE,
        ))
        assert pattern_count >= 3, (
            f"Expected at least 3 instances of the standard empty-state pattern "
            f"in main.py (found {pattern_count}). This confirms the project convention."
        )


# ==============================================================================
# 4. Row Action Buttons Use btn() Helper
# ==============================================================================

class TestRowActionButtonsUseBtnHelper:
    """Row action buttons ('Сделать основным' / 'Убрать основной' and 'Удалить')
    must use the btn() helper function, not raw Button elements with inline styles."""

    def _get_brand_row_section(self, func_name: str) -> str:
        """Extract the brand row rendering section from a function."""
        func_src = _extract_function_source(func_name)
        # Get the for loop body that builds brand rows
        loop_match = re.search(r'for a in.*?(?=\n    if brand_rows|\n    else:)', func_src, re.DOTALL)
        assert loop_match, f"Could not find brand row loop in {func_name}"
        return loop_match.group(0)

    def test_toggle_button_uses_btn_in_brands_tab(self):
        """Toggle primary button in _supplier_brands_tab must use btn() helper."""
        func_src = _extract_function_source("_supplier_brands_tab")
        row_section = func_src
        # Check that btn() is used for toggle action
        has_btn_call = bool(re.search(r'\bbtn\s*\(.*(?:основн|toggle|primary)', row_section, re.IGNORECASE | re.DOTALL))
        # Also check there's no inline style on a Button for toggle
        has_inline_toggle = bool(re.search(
            r'Button\(.*?(?:основн|toggle).*?style\s*=\s*".*?background:\s*none',
            row_section,
            re.DOTALL | re.IGNORECASE,
        ))
        assert has_btn_call or not has_inline_toggle, (
            "Toggle primary button in _supplier_brands_tab uses inline styles. "
            "Should use btn() helper, e.g.: btn('Сделать основным', variant='ghost', ...)"
        )

    def test_delete_button_uses_btn_in_brands_tab(self):
        """Delete button in _supplier_brands_tab must use btn() helper."""
        func_src = _extract_function_source("_supplier_brands_tab")
        # Check no inline-style Button with #dc2626 color (delete button pattern)
        has_inline_delete = bool(re.search(
            r'Button\(.*?[Уу]далить.*?style\s*=\s*".*?#dc2626',
            func_src,
            re.DOTALL,
        ))
        assert not has_inline_delete, (
            "Delete button in _supplier_brands_tab uses inline style with #dc2626. "
            "Should use btn('Удалить', variant='danger', icon_name='trash-2', size='sm', ...)"
        )

    def test_toggle_button_uses_btn_in_list_partial(self):
        """Toggle primary button in _supplier_brands_list_partial must use btn() helper."""
        func_src = _extract_function_source("_supplier_brands_list_partial")
        has_inline_toggle = bool(re.search(
            r'Button\(.*?(?:основн|toggle).*?style\s*=\s*".*?background:\s*none',
            func_src,
            re.DOTALL | re.IGNORECASE,
        ))
        assert not has_inline_toggle, (
            "Toggle primary button in _supplier_brands_list_partial uses inline styles. "
            "Should use btn() helper."
        )

    def test_delete_button_uses_btn_in_list_partial(self):
        """Delete button in _supplier_brands_list_partial must use btn() helper."""
        func_src = _extract_function_source("_supplier_brands_list_partial")
        has_inline_delete = bool(re.search(
            r'Button\(.*?[Уу]далить.*?style\s*=\s*".*?#dc2626',
            func_src,
            re.DOTALL,
        ))
        assert not has_inline_delete, (
            "Delete button in _supplier_brands_list_partial uses inline style with #dc2626. "
            "Should use btn('Удалить', variant='danger', ...) helper."
        )

    def test_btn_helper_supports_required_variants(self):
        """Verify btn() helper supports 'ghost' and 'danger' variants needed for row actions."""
        source = _read_main_source()
        btn_func = _extract_function_source("btn", source)
        # Check that variant parameter exists and supports ghost/danger
        assert "variant" in btn_func, "btn() must have variant parameter"
        # Verify usage examples mention danger and ghost
        assert "danger" in btn_func, "btn() must support 'danger' variant"
        assert "ghost" in btn_func, "btn() must support 'ghost' variant"


# ==============================================================================
# 5. Code Deduplication -- Shared Row Rendering Helper
# ==============================================================================

class TestCodeDeduplication:
    """_supplier_brands_tab and _supplier_brands_list_partial should share
    brand row rendering logic via a helper function, not duplicate it."""

    def test_brand_row_helper_function_exists(self):
        """A shared helper function for rendering a brand row should exist."""
        source = _read_main_source()
        # Look for a helper function like _supplier_brand_row or _brand_row
        has_helper = bool(re.search(
            r'def _supplier_brand_row\(|def _brand_row\(|def _render_brand_row\(',
            source,
        ))
        assert has_helper, (
            "No shared brand row helper function found (expected _supplier_brand_row, "
            "_brand_row, or _render_brand_row). "
            "_supplier_brands_tab and _supplier_brands_list_partial currently duplicate "
            "~30 lines of identical row rendering code."
        )

    def test_brands_tab_calls_shared_helper(self):
        """_supplier_brands_tab should call the shared row rendering helper."""
        func_src = _extract_function_source("_supplier_brands_tab")
        calls_helper = bool(re.search(
            r'_supplier_brand_row\(|_brand_row\(|_render_brand_row\(',
            func_src,
        ))
        assert calls_helper, (
            "_supplier_brands_tab does not call a shared row helper. "
            "It should use a helper function instead of inline row building."
        )

    def test_brands_list_partial_calls_shared_helper(self):
        """_supplier_brands_list_partial should call the shared row rendering helper."""
        func_src = _extract_function_source("_supplier_brands_list_partial")
        calls_helper = bool(re.search(
            r'_supplier_brand_row\(|_brand_row\(|_render_brand_row\(',
            func_src,
        ))
        assert calls_helper, (
            "_supplier_brands_list_partial does not call a shared row helper. "
            "It should use the same helper function as _supplier_brands_tab."
        )

    def test_row_rendering_not_duplicated(self):
        """The two functions should NOT both contain full inline row-building code."""
        tab_src = _extract_function_source("_supplier_brands_tab")
        partial_src = _extract_function_source("_supplier_brands_list_partial")

        # Count how many times the toggle label pattern appears (indicator of row building)
        # Each function having its own toggle_label = "..." means duplication
        tab_has_toggle_label = "toggle_label" in tab_src or "Сделать основным" in tab_src
        partial_has_toggle_label = "toggle_label" in partial_src or "Сделать основным" in partial_src

        assert not (tab_has_toggle_label and partial_has_toggle_label), (
            "Both _supplier_brands_tab and _supplier_brands_list_partial contain "
            "inline row rendering code with toggle labels. This is duplicated code. "
            "Extract a shared _supplier_brand_row() helper to eliminate duplication."
        )


# ==============================================================================
# Meta: Verify test infrastructure
# ==============================================================================

class TestMetaInfrastructure:
    """Verify the test helper functions work correctly."""

    def test_main_py_exists(self):
        """main.py must exist at the expected project root path."""
        assert os.path.isfile(MAIN_PY), f"main.py not found at {MAIN_PY}"

    def test_can_read_main_source(self):
        """main.py must be readable."""
        source = _read_main_source()
        assert len(source) > 10000, "main.py seems too small, possible read error"

    def test_extract_function_finds_brands_tab(self):
        """Helper can extract _supplier_brands_tab function."""
        func = _extract_function_source("_supplier_brands_tab")
        assert "supplier_id" in func
        assert "brand" in func.lower()

    def test_extract_function_finds_brands_list_partial(self):
        """Helper can extract _supplier_brands_list_partial function."""
        func = _extract_function_source("_supplier_brands_list_partial")
        assert "supplier_id" in func
        assert "brand" in func.lower()

    def test_extract_supplier_detail_handler(self):
        """Helper can extract the supplier detail GET handler."""
        handler = _extract_supplier_detail_handler()
        assert "supplier_id" in handler
        assert "tab" in handler
        assert "page_layout" in handler


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
