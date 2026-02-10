"""
BUG-4: Customs Table Missing ARTIKUL Column + HS Code Validation

Two issues:
1. The customs Handsontable is missing the product_code/SKU column ('Артикул').
   It should appear after 'Бренд' as a readOnly column.
2. HS code (ТН ВЭД) must be mandatory before customs completion. Currently
   the completion handler does NOT validate that all items have hs_code filled.

These tests are written BEFORE the fix. All should FAIL on the current codebase.
"""

import pytest
import re
import os
import json

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
WORKFLOW_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "workflow_service.py")


def _read_source(path):
    """Read source file without importing (avoids sentry_sdk and other deps)."""
    with open(path) as f:
        return f.read()


def _read_main_source():
    return _read_source(MAIN_PY)


# ==============================================================================
# 1. colHeaders must include 'Артикул' after 'Бренд'
# ==============================================================================

class TestColHeadersIncludeArtikul:
    """The customs Handsontable colHeaders must include 'Артикул' column."""

    def _get_customs_colheaders(self):
        """Extract the colHeaders array from the customs Handsontable init."""
        source = _read_main_source()
        # Find the colHeaders line inside the customs Handsontable init
        # Pattern: colHeaders: ['...', '...', ...]
        match = re.search(
            r"customs-spreadsheet.*?colHeaders:\s*\[([^\]]+)\]",
            source,
            re.DOTALL,
        )
        assert match, "colHeaders array not found near customs-spreadsheet"
        return match.group(1)

    def test_colheaders_contains_artikul(self):
        """colHeaders must include 'Артикул' label."""
        headers_str = self._get_customs_colheaders()
        assert "Артикул" in headers_str, (
            "colHeaders is missing 'Артикул'. Current headers: "
            + headers_str[:200]
        )

    def test_artikul_appears_after_brand(self):
        """'Артикул' must appear after 'Бренд' in colHeaders."""
        headers_str = self._get_customs_colheaders()
        # Parse the individual header strings
        headers = re.findall(r"'([^']*)'", headers_str)

        assert "Артикул" in headers, (
            f"'Артикул' not found in colHeaders: {headers}"
        )
        assert "Бренд" in headers, (
            f"'Бренд' not found in colHeaders: {headers}"
        )

        brand_idx = headers.index("Бренд")
        artikul_idx = headers.index("Артикул")
        assert artikul_idx == brand_idx + 1, (
            f"'Артикул' (index {artikul_idx}) must be right after "
            f"'Бренд' (index {brand_idx}). Current order: {headers}"
        )

    def test_colheaders_count_increased(self):
        """Adding 'Артикул' should increase the total header count by 1."""
        headers_str = self._get_customs_colheaders()
        headers = re.findall(r"'([^']*)'", headers_str)
        # Currently 13 headers, should become 14 with Артикул
        assert len(headers) >= 14, (
            f"Expected at least 14 colHeaders (with Артикул), got {len(headers)}: {headers}"
        )


# ==============================================================================
# 2. columns config must include product_code field
# ==============================================================================

class TestColumnsConfigIncludeProductCode:
    """The customs Handsontable columns config must include a product_code column."""

    def _get_customs_columns_section(self):
        """Extract the columns config from the customs Handsontable init."""
        source = _read_main_source()
        # The columns array is right after colHeaders in the Handsontable init
        match = re.search(
            r"customs-spreadsheet.*?columns:\s*\[(.*?)\],\s*\n\s*rowHeaders",
            source,
            re.DOTALL,
        )
        assert match, "columns config not found near customs-spreadsheet"
        return match.group(1)

    def test_columns_config_has_product_code(self):
        """columns config must include a column with data: 'product_code'."""
        cols = self._get_customs_columns_section()
        assert "product_code" in cols, (
            "columns config is missing product_code column. "
            "Expected {{data: 'product_code', ...}} in columns array."
        )

    def test_product_code_column_is_readonly(self):
        """product_code column must be readOnly: true."""
        cols = self._get_customs_columns_section()
        # Find the product_code column definition
        pc_match = re.search(
            r"\{[^}]*data:\s*'product_code'[^}]*\}",
            cols,
            re.DOTALL,
        )
        assert pc_match, "product_code column definition not found"
        col_def = pc_match.group(0)
        assert "readOnly" in col_def and "true" in col_def, (
            f"product_code column must be readOnly: true. Found: {col_def}"
        )

    def test_product_code_column_type_is_text(self):
        """product_code column must be type: 'text'."""
        cols = self._get_customs_columns_section()
        pc_match = re.search(
            r"\{[^}]*data:\s*'product_code'[^}]*\}",
            cols,
            re.DOTALL,
        )
        assert pc_match, "product_code column definition not found"
        col_def = pc_match.group(0)
        assert "'text'" in col_def, (
            f"product_code column must have type: 'text'. Found: {col_def}"
        )

    def test_product_code_column_after_brand_column(self):
        """product_code column must appear after brand column in the config."""
        cols = self._get_customs_columns_section()
        brand_pos = cols.find("'brand'")
        pc_pos = cols.find("'product_code'")
        assert brand_pos != -1, "'brand' not found in columns config"
        assert pc_pos != -1, "'product_code' not found in columns config"
        assert pc_pos > brand_pos, (
            f"product_code (pos {pc_pos}) must come after brand (pos {brand_pos}) "
            "in the columns config"
        )


# ==============================================================================
# 3. _build_customs_item must include product_code
# ==============================================================================

class TestBuildCustomsItemIncludesProductCode:
    """The _build_customs_item helper must include product_code in the row dict."""

    def _get_build_customs_item_source(self):
        """Extract the _build_customs_item function source."""
        source = _read_main_source()
        match = re.search(
            r"(def _build_customs_item\(item,\s*idx\):.*?)(?=\n    items_for_handsontable)",
            source,
            re.DOTALL,
        )
        assert match, "_build_customs_item function not found in main.py"
        return match.group(1)

    def test_build_customs_item_includes_product_code(self):
        """_build_customs_item must set product_code in the row dict."""
        fn_source = self._get_build_customs_item_source()
        assert "product_code" in fn_source, (
            "_build_customs_item does not include product_code in the row dict. "
            "Expected: 'product_code': item.get('product_code', '')"
        )

    def test_product_code_has_default_empty_string(self):
        """product_code should default to empty string when missing."""
        fn_source = self._get_build_customs_item_source()
        # Check for a default value pattern
        has_default = (
            "product_code', ''" in fn_source
            or "product_code', \"\"" in fn_source
            or "product_code') or ''" in fn_source
        )
        assert has_default, (
            "product_code should have a default empty string when not present. "
            "Expected pattern like: item.get('product_code', '')"
        )


# ==============================================================================
# 4. saveCustomsItems JS must NOT send product_code (readOnly)
# ==============================================================================

class TestSaveDoesNotSendProductCode:
    """product_code is readOnly and should NOT be in the save payload.
    The JS saveCustomsItems function should not include it."""

    def _get_save_payload_fields(self):
        """Extract the fields sent in the saveCustomsItems PATCH payload.

        The JS is inside a Python f-string, so braces are doubled: {{ and }}.
        The return object looks like:
            return {{
                id: row.id,
                hs_code: row.hs_code || '',
                ...
            }};
        """
        source = _read_main_source()
        # Find the return block inside sourceData.map
        match = re.search(
            r"sourceData\.map\(function\(row\)\s*\{\{(.*?)\}\};\s*\n\s*\}\}\)",
            source,
            re.DOTALL,
        )
        assert match, "saveCustomsItems map return block not found"
        return match.group(1)

    def test_save_payload_does_not_include_product_code(self):
        """The PATCH payload should not include product_code (readOnly field)."""
        payload_body = self._get_save_payload_fields()
        assert "product_code" not in payload_body, (
            "product_code should NOT be in the save payload since it is readOnly. "
            f"Found in: {payload_body[:300]}"
        )


# ==============================================================================
# 5. HS code validation blocks customs completion when empty
# ==============================================================================

class TestHsCodeValidationOnCompletion:
    """Customs completion must be blocked when any item has empty hs_code."""

    def _get_customs_completion_block(self):
        """Extract ONLY the customs completion block (not logistics).

        The customs POST handler ends with:
            if action == "complete":
                ...
                result = complete_customs(...)
            return RedirectResponse(f"/customs/{quote_id}")

        We find the complete_customs call and extract the surrounding if-block.
        """
        source = _read_main_source()
        # Find complete_customs call position first
        cc_pos = source.find("complete_customs(quote_id")
        assert cc_pos != -1, "complete_customs(quote_id...) call not found in main.py"

        # Extract context: from the nearest 'if action == "complete"' before it
        # to the nearest 'return RedirectResponse' after it
        before = source[:cc_pos]
        after = source[cc_pos:]

        # Find the if action == "complete" that precedes this call
        if_pos = before.rfind('if action == "complete"')
        assert if_pos != -1, 'if action == "complete" not found before complete_customs call'

        # Find the return redirect after the call
        redirect_match = re.search(
            r'return RedirectResponse\(f"/customs/',
            after,
        )
        assert redirect_match, "return RedirectResponse to /customs/ not found after complete_customs"

        block = source[if_pos : cc_pos + redirect_match.end()]
        return block

    def test_completion_validates_hs_codes(self):
        """The customs POST handler must check that all items have hs_code before completing."""
        block = self._get_customs_completion_block()
        has_hs_check = "hs_code" in block
        assert has_hs_check, (
            "Customs completion block must validate hs_code before calling "
            "complete_customs(). Currently the block is:\n" + block[:400]
        )

    def test_completion_fetches_items_for_hs_check(self):
        """Before completing customs, handler must fetch items to check their hs_code."""
        block = self._get_customs_completion_block()
        has_items_query = "quote_items" in block and "hs_code" in block
        assert has_items_query, (
            "Customs completion block must query quote_items and check hs_code "
            "before calling complete_customs(). Currently it does neither."
        )

    def test_completion_blocks_when_hs_code_missing(self):
        """Handler must prevent completion when any item is missing hs_code."""
        block = self._get_customs_completion_block()
        # The block must contain logic to check items AND prevent completion
        # It needs both: a check for hs_code AND a branch that avoids complete_customs
        has_validation_branch = (
            "hs_code" in block
            and (
                "all(" in block
                or "any(" in block
                or "missing" in block.lower()
                or "empty" in block.lower()
                or "without" in block.lower()
                or "not item" in block
            )
        )
        assert has_validation_branch, (
            "Customs completion must check if any items lack hs_code and "
            "prevent completion. Currently there is no validation logic."
        )

    def test_hs_code_check_appears_before_complete_customs_call(self):
        """hs_code validation must appear BEFORE the complete_customs() call."""
        block = self._get_customs_completion_block()
        hs_pos = block.find("hs_code")
        complete_pos = block.find("complete_customs")
        assert hs_pos != -1, (
            "No hs_code reference found in customs completion block. "
            "All items must have hs_code filled before customs can be completed."
        )
        assert complete_pos != -1, "complete_customs() call not found"
        assert hs_pos < complete_pos, (
            f"hs_code check (pos {hs_pos}) must come BEFORE "
            f"complete_customs() call (pos {complete_pos})"
        )


# ==============================================================================
# 6. HS code validation in complete_customs (workflow_service.py)
# ==============================================================================

class TestHsCodeValidationInWorkflowService:
    """Alternatively/additionally, the complete_customs function in
    workflow_service.py should validate hs_code for all items."""

    def _get_complete_customs_source(self):
        """Extract complete_customs function source from workflow_service.py."""
        source = _read_source(WORKFLOW_SERVICE_PY)
        match = re.search(
            r'(def complete_customs\(.*?\n(?:    .*\n)*)',
            source,
        )
        assert match, "complete_customs function not found in workflow_service.py"
        return match.group(1)

    def test_complete_customs_checks_hs_codes(self):
        """complete_customs should validate that all items have hs_code."""
        fn_source = self._get_complete_customs_source()
        # Either main.py or workflow_service.py should validate
        # But best practice: the service function validates
        has_hs_validation = "hs_code" in fn_source
        assert has_hs_validation, (
            "complete_customs() in workflow_service.py does NOT validate hs_code. "
            "Items with empty hs_code should prevent customs completion."
        )

    def test_complete_customs_queries_items(self):
        """complete_customs should query quote_items to check hs_code."""
        fn_source = self._get_complete_customs_source()
        has_items_query = "quote_items" in fn_source
        assert has_items_query, (
            "complete_customs() does not query quote_items. "
            "It should fetch items and verify all have hs_code before completing."
        )

    def test_complete_customs_returns_error_for_missing_hs(self):
        """complete_customs should return error when hs_code is missing."""
        fn_source = self._get_complete_customs_source()
        has_hs_error = (
            "hs_code" in fn_source
            and "error" in fn_source.lower()
        )
        assert has_hs_error, (
            "complete_customs() must return an error when items lack hs_code. "
            "Currently it completes regardless of hs_code presence."
        )


# ==============================================================================
# 7. Edge cases for product_code display
# ==============================================================================

class TestProductCodeEdgeCases:
    """Edge cases for the product_code/Артикул column in customs table."""

    def test_product_code_flows_from_select_to_handsontable(self):
        """product_code is already in the SELECT query -- verify it flows to the table.

        The database query at line ~17764 already includes product_code.
        The bug is that _build_customs_item does NOT include it in the row dict,
        so it never reaches the Handsontable. This test verifies the full flow.
        """
        source = _read_main_source()
        # The _build_customs_item function must map product_code into the row
        build_fn = re.search(
            r"def _build_customs_item\(item,\s*idx\):(.*?)return row",
            source,
            re.DOTALL,
        )
        assert build_fn, "_build_customs_item not found"
        fn_body = build_fn.group(1)
        assert "product_code" in fn_body, (
            "product_code is fetched from DB but _build_customs_item does not "
            "include it in the row dict. It is lost before reaching Handsontable."
        )


# ==============================================================================
# 8. Integration: product_code data flows end-to-end
# ==============================================================================

class TestProductCodeDataFlow:
    """product_code must flow from DB -> Python -> JSON -> Handsontable."""

    def test_product_code_in_json_data(self):
        """The items_json sent to Handsontable must contain product_code."""
        source = _read_main_source()
        # _build_customs_item builds the dict that becomes items_json
        build_fn = re.search(
            r"def _build_customs_item\(item,\s*idx\):(.*?)return row",
            source,
            re.DOTALL,
        )
        assert build_fn, "_build_customs_item not found"
        fn_body = build_fn.group(1)
        assert "product_code" in fn_body, (
            "_build_customs_item must include 'product_code' in the row dict "
            "so it appears in the Handsontable JSON data. Currently missing."
        )

    def test_colheaders_has_14_entries_with_artikul(self):
        """After adding Артикул, colHeaders should have 14 entries (was 13)."""
        source = _read_main_source()

        headers_match = re.search(
            r"customs-spreadsheet.*?colHeaders:\s*\[([^\]]+)\]",
            source,
            re.DOTALL,
        )
        assert headers_match, "colHeaders not found"
        headers = re.findall(r"'([^']*)'", headers_match.group(1))

        assert len(headers) == 14, (
            f"Expected 14 colHeaders (including Артикул), got {len(headers)}: {headers}"
        )

    def test_columns_count_matches_colheaders_count(self):
        """Number of columns configs must match number of colHeaders (both should be 14)."""
        source = _read_main_source()

        # Extract colHeaders
        headers_match = re.search(
            r"customs-spreadsheet.*?colHeaders:\s*\[([^\]]+)\]",
            source,
            re.DOTALL,
        )
        assert headers_match, "colHeaders not found"
        headers = re.findall(r"'([^']*)'", headers_match.group(1))

        # Extract columns
        cols_match = re.search(
            r"customs-spreadsheet.*?columns:\s*\[(.*?)\],\s*\n\s*rowHeaders",
            source,
            re.DOTALL,
        )
        assert cols_match, "columns config not found"
        col_count = len(re.findall(r"\bdata:", cols_match.group(1)))

        assert col_count == 14 and len(headers) == 14, (
            f"Both colHeaders ({len(headers)}) and columns ({col_count}) must be 14 "
            f"(including product_code/Артикул). Headers: {headers}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
