"""
Design Audit Tests: L4, L5, M13 -- Country code display issues

Tests for three country-code display bugs found during UI audit:

L4: Suppliers country filter dropdown (~main.py:29681-29683)
    - get_unique_countries() returns raw ISO codes like "CN", "DE", "TR"
    - The dropdown Option(c, value=c) renders "CN" instead of "Китай"
    - Fix: translate country codes to Russian names before building options

L5: Suppliers table location column (~main.py:29704)
    - Shows "DE, —" / "CN, —" — raw ISO codes + dangling dash when city is empty
    - Fix: translate codes and hide ", —" when city is absent

M13: Customs Handsontable raw country codes (~main.py:18019-18034)
    - _build_customs_item passes item.get('supplier_country', '') verbatim
    - Handsontable "Страна закупки" column shows "CN" instead of "Китай"
    - Fix: apply country name translation in _build_customs_item

All tests are expected to FAIL until the display issues are fixed.
"""

import pytest
import re
import os


# ============================================================================
# Path constants and helpers (same pattern as test_design_c1_c2_c3.py)
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code (no import needed, avoids sentry_sdk dep)."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _extract_function_source(func_name, source=None):
    """Extract a top-level function body from main.py by name."""
    if source is None:
        source = _read_main_source()
    pattern = re.compile(
        rf'^(def {re.escape(func_name)}\(.*?)(?=\ndef |\n@rt\(|\nclass |\n# ===|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(source)
    assert match, f"Function '{func_name}' not found in main.py"
    return match.group(1)


def _find_lines_containing(source, needle):
    """Return list of (line_number, line_text) for lines containing needle."""
    results = []
    for i, line in enumerate(source.splitlines(), 1):
        if needle in line:
            results.append((i, line))
    return results


def _extract_block_around(source, anchor, before=20, after=40):
    """Extract a block of lines around the first occurrence of anchor text."""
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if anchor in line:
            start = max(0, i - before)
            end = min(len(lines), i + after)
            return "\n".join(lines[start:end])
    return ""


# ============================================================================
# Shared: Verify a global COUNTRY_NAME_MAP exists for UI display
# ============================================================================

class TestCountryNameMapExists:
    """
    A global/shared COUNTRY_NAME_MAP (or equivalent) dictionary should exist
    at module level in main.py to translate ISO country codes to Russian names
    for UI display.

    The existing SUPPLIER_COUNTRY_MAPPING (~line 10500) maps codes to
    calculation-engine enum values (e.g. CN -> "Китай"), which is close but
    intended for the calculation engine, not for UI display. There should be
    a dedicated UI-display mapping that covers all countries (including DE,
    IT, FR, etc.) that are stored in the database.

    Note: A local `country_names` dict exists inside one function (~line 17004)
    but it is NOT accessible to the supplier list or customs code.
    """

    def test_global_country_name_map_defined(self):
        """A module-level COUNTRY_NAME_MAP dict should exist for UI translation."""
        source = _read_main_source()
        # Look for a module-level definition (not inside a function)
        # Should be something like: COUNTRY_NAME_MAP = { ... }
        # Must NOT be inside a def block — look for it at column 0
        pattern = re.compile(r'^COUNTRY_NAME_MAP\s*=\s*\{', re.MULTILINE)
        match = pattern.search(source)
        assert match, (
            "No module-level COUNTRY_NAME_MAP dictionary found in main.py. "
            "A shared mapping from ISO codes (CN, DE, TR, IT, etc.) to Russian "
            "names (Китай, Германия, Турция, Италия) is needed for consistent "
            "country display across suppliers list, customs workspace, and other pages. "
            "Currently country_names exists only as a local variable inside one function (~line 17004)."
        )

    def test_country_name_map_has_common_codes(self):
        """COUNTRY_NAME_MAP should include at least CN, DE, TR, IT, RU."""
        source = _read_main_source()
        pattern = re.compile(r'^COUNTRY_NAME_MAP\s*=\s*\{', re.MULTILINE)
        match = pattern.search(source)
        if not match:
            pytest.fail(
                "COUNTRY_NAME_MAP not found — see test_global_country_name_map_defined"
            )
        # Extract the dict body (find matching closing brace)
        start = match.start()
        # Read up to 2000 chars to capture the full dict
        dict_text = source[start:start + 2000]
        required_codes = {
            '"CN"': "Китай",
            '"DE"': "Германия",
            '"TR"': "Турция",
            '"IT"': "Италия",
            '"RU"': "Россия",
        }
        missing = []
        for code, name in required_codes.items():
            if code not in dict_text:
                missing.append(f"{code} -> {name}")
        assert not missing, (
            f"COUNTRY_NAME_MAP is missing entries: {', '.join(missing)}. "
            f"The map must translate all common ISO codes to Russian names."
        )


# ============================================================================
# L4: Suppliers country filter dropdown shows raw codes
# ============================================================================

class TestL4_SupplierCountryFilterDropdown:
    """
    The supplier list page (~main.py:29681-29683) builds the country filter
    dropdown directly from get_unique_countries() results:

        country_options = [Option("Все страны", value="")] + [
            Option(c, value=c, selected=(c == country)) for c in countries
        ]

    Since get_unique_countries() returns raw DB values (ISO codes like "CN",
    "DE", "TR"), the dropdown displays "CN" instead of "Китай".

    Fix: Apply COUNTRY_NAME_MAP translation to the Option label while
    keeping the raw code as the value for filtering.
    """

    def test_country_filter_options_use_translated_names(self):
        """Supplier country dropdown labels should show Russian names, not codes."""
        source = _read_main_source()
        # Find the country_options line in the suppliers section
        # Current code: Option(c, value=c, ...)
        # Fixed code should be something like:
        #   Option(COUNTRY_NAME_MAP.get(c, c), value=c, ...)
        #   or Option(translate_country(c), value=c, ...)

        # Find the block that builds country_options for suppliers
        block = _extract_block_around(source, "country_options = [Option", before=2, after=5)
        assert block, "Could not find country_options construction in main.py"

        # The Option label (first arg) must NOT be the raw variable `c` alone
        # It should reference a translation map or function
        has_translation = (
            "COUNTRY_NAME_MAP" in block
            or "country_name_map" in block
            or "country_names" in block
            or "translate_country" in block
            or "map_country" in block
            or "get_country_name" in block
        )
        assert has_translation, (
            f"Supplier country filter dropdown builds Option labels from raw DB values:\n"
            f"  Option(c, value=c, ...) for c in countries\n"
            f"This shows ISO codes ('CN', 'DE') instead of Russian names ('Китай', 'Германия').\n"
            f"The Option label should use a country name translation, e.g.:\n"
            f"  Option(COUNTRY_NAME_MAP.get(c, c), value=c, ...)\n"
            f"Relevant code:\n{block}"
        )

    def test_country_filter_preserves_raw_value_for_filtering(self):
        """Country filter value= should keep the raw code for DB-level filtering."""
        source = _read_main_source()
        block = _extract_block_around(source, "country_options = [Option", before=2, after=5)
        assert block, "Could not find country_options construction in main.py"
        # The value= parameter should still be the raw code `c` (or equivalent)
        # so that the filter query works against the database.
        # This test verifies the label is translated while value stays raw.
        # Look for pattern where label != value (translation applied)
        has_different_label_and_value = (
            re.search(r'Option\(\s*COUNTRY_NAME_MAP', block)
            or re.search(r'Option\(\s*translate_country', block)
            or re.search(r'Option\(\s*get_country_name', block)
            or re.search(r'Option\(\s*country_names', block)
        )
        assert has_different_label_and_value, (
            "Country filter Option() uses the same raw value for both label and value. "
            "The label should be translated to Russian while value= keeps the raw code "
            "for filtering: Option(COUNTRY_NAME_MAP.get(c, c), value=c, ...)"
        )


# ============================================================================
# L5: Suppliers table location column shows raw codes + dangling dash
# ============================================================================

class TestL5_SupplierTableLocationColumn:
    """
    The supplier table location column (~main.py:29704) renders:

        Td(f"{s.country or '—'}, {s.city or '—'}" if s.country else "—")

    Issues:
    1. s.country is a raw ISO code (e.g. "DE") — should be translated to Russian
    2. When city is empty, shows "DE, —" — the dangling ", —" is ugly
       Expected: just "Германия" when city is absent

    Fix: translate s.country via COUNTRY_NAME_MAP, and conditionally omit
    the city part when it's empty.
    """

    def test_location_column_translates_country_code(self):
        """Supplier location Td() should use translated country name, not raw code."""
        source = _read_main_source()
        # Find the specific line that builds the location Td
        # Current: Td(f"{s.country or '—'}, {s.city or '—'}" ...)
        location_hits = _find_lines_containing(source, 's.country or')
        # Filter to only Td() context in supplier rows
        td_location_hits = [
            (ln, txt) for ln, txt in location_hits
            if "Td(" in txt or "s.city" in txt
        ]
        assert td_location_hits, "Could not find supplier location Td() in main.py"

        for ln, txt in td_location_hits:
            has_translation = (
                "COUNTRY_NAME_MAP" in txt
                or "country_name_map" in txt
                or "country_names" in txt
                or "translate_country" in txt
                or "map_country" in txt
                or "get_country_name" in txt
            )
            assert has_translation, (
                f"Line {ln}: Supplier location column uses raw s.country code:\n"
                f"  {txt.strip()}\n"
                f"Raw ISO codes ('DE', 'CN') are displayed instead of Russian names "
                f"('Германия', 'Китай'). Apply COUNTRY_NAME_MAP.get(s.country, s.country)."
            )

    def test_location_column_hides_dash_when_city_empty(self):
        """When city is empty, location should show just country name, not 'Country, —'."""
        source = _read_main_source()
        # The current pattern: f"{s.country or '—'}, {s.city or '—'}"
        # This always appends ", —" when city is None/empty
        # Better pattern: show just country when city is absent
        location_hits = _find_lines_containing(source, 's.country or')
        td_location_hits = [
            (ln, txt) for ln, txt in location_hits
            if "Td(" in txt or "s.city" in txt
        ]
        assert td_location_hits, "Could not find supplier location Td() in main.py"

        for ln, txt in td_location_hits:
            # Check for the problematic pattern that always shows ", —"
            has_dangling_dash = (
                "s.city or '—'" in txt
                or 's.city or "—"' in txt
                or "s.city or '\\u2014'" in txt
            )
            if has_dangling_dash:
                # Verify there's conditional logic to omit city when empty
                has_conditional_city = (
                    "if s.city" in txt
                    or "s.city and" in txt
                    # Or the format string only includes city conditionally
                    or re.search(r'f".*\{.*s\.city.*\}.*".*if.*s\.city', txt)
                )
                assert has_conditional_city, (
                    f"Line {ln}: Location column always appends ', —' when city is empty:\n"
                    f"  {txt.strip()}\n"
                    f"Shows 'DE, —' instead of just 'Германия'. "
                    f"City part should be omitted when s.city is empty/None."
                )


# ============================================================================
# M13: Customs Handsontable _build_customs_item raw country codes
# ============================================================================

class TestM13_CustomsItemCountryTranslation:
    """
    The _build_customs_item function (~main.py:18019-18034) builds data for
    the Handsontable grid on the customs workspace page. The supplier_country
    field is passed through verbatim:

        'supplier_country': item.get('supplier_country', '')

    Since the database stores ISO codes (e.g. "CN", "DE"), the Handsontable
    "Страна закупки" column displays "CN" instead of "Китай".

    Fix: Apply country name translation, e.g.:
        'supplier_country': COUNTRY_NAME_MAP.get(item.get('supplier_country', ''),
                                                  item.get('supplier_country', ''))
    or use map_supplier_country() which already maps CN -> Китай.
    """

    def test_customs_item_translates_supplier_country(self):
        """_build_customs_item should translate supplier_country codes to Russian names."""
        source = _read_main_source()
        # Find the _build_customs_item function
        # Look for the supplier_country assignment line inside _build_customs_item
        block = _extract_block_around(source, "def _build_customs_item", before=0, after=20)
        assert block, "Could not find _build_customs_item function in main.py"

        # Find the specific supplier_country line
        sc_hits = _find_lines_containing(block, "'supplier_country'")
        assert sc_hits, "Could not find supplier_country assignment in _build_customs_item"

        for ln, txt in sc_hits:
            # Check that it's not just a raw passthrough
            is_raw_passthrough = (
                "item.get('supplier_country'" in txt
                or 'item.get("supplier_country"' in txt
            )
            has_translation = (
                "COUNTRY_NAME_MAP" in txt
                or "country_name_map" in txt
                or "country_names" in txt
                or "map_supplier_country" in txt
                or "translate_country" in txt
                or "get_country_name" in txt
            )
            if is_raw_passthrough:
                assert has_translation, (
                    f"_build_customs_item passes supplier_country verbatim:\n"
                    f"  {txt.strip()}\n"
                    f"ISO codes ('CN') are shown in Handsontable instead of Russian "
                    f"names ('Китай'). Apply COUNTRY_NAME_MAP or map_supplier_country() "
                    f"to translate the value before sending to the UI."
                )

    def test_customs_item_uses_consistent_translation_with_logistics(self):
        """Customs and logistics should use the same country translation approach.

        The logistics section (~line 17004) has a local country_names dict.
        The customs section should use the same (or a shared) mapping, not
        its own ad-hoc translation.
        """
        source = _read_main_source()
        block = _extract_block_around(source, "def _build_customs_item", before=0, after=20)
        assert block, "Could not find _build_customs_item function in main.py"

        # The function should reference a shared mapping, not have its own
        # local dict or skip translation entirely
        uses_shared_map = (
            "COUNTRY_NAME_MAP" in block
            or "map_supplier_country" in block
            or "SUPPLIER_COUNTRY_MAPPING" in block
        )
        assert uses_shared_map, (
            "_build_customs_item does not use any shared country translation mapping. "
            "It should use COUNTRY_NAME_MAP (or map_supplier_country) to translate "
            "ISO codes consistently with other parts of the application."
        )

    def test_map_supplier_country_covers_common_iso_codes(self):
        """map_supplier_country() or SUPPLIER_COUNTRY_MAPPING covers DE, IT, FR etc.

        The existing SUPPLIER_COUNTRY_MAPPING (~line 10500) maps CN, TR, RU, etc.
        but may be missing codes like DE (Germany), IT (Italy), FR (France) that
        appear in the suppliers database. If this mapping is used for UI display,
        it needs broader coverage.
        """
        source = _read_main_source()
        # Find the SUPPLIER_COUNTRY_MAPPING dict
        pattern = re.compile(
            r'SUPPLIER_COUNTRY_MAPPING\s*=\s*\{(.*?)\}',
            re.DOTALL,
        )
        match = pattern.search(source)
        assert match, "SUPPLIER_COUNTRY_MAPPING not found in main.py"
        mapping_text = match.group(1)

        # These codes appear in supplier data but may be missing from the mapping
        codes_needed_for_ui = {
            '"DE"': "Германия (Germany)",
            '"IT"': "Италия (Italy)",
            '"FR"': "Франция (France)",
            '"JP"': "Япония (Japan)",
            '"KR"': "Корея (Korea)",
            '"IN"': "Индия (India)",
        }
        missing = []
        for code, desc in codes_needed_for_ui.items():
            if code not in mapping_text:
                missing.append(f"{code} ({desc})")

        assert not missing, (
            f"SUPPLIER_COUNTRY_MAPPING is missing ISO codes commonly found in "
            f"supplier data: {', '.join(missing)}. "
            f"These codes need Russian name translations for UI display in "
            f"supplier lists and customs workspace."
        )


# ============================================================================
# Integration: supplier list and customs use the same country translation
# ============================================================================

class TestCountryTranslationConsistency:
    """
    Verify that all three areas (supplier filter, supplier table, customs item)
    use the same country translation mechanism rather than ad-hoc local dicts.
    """

    def test_supplier_list_page_references_shared_country_map(self):
        """The supplier list page block should reference a shared country map."""
        source = _read_main_source()
        # Find the block around the supplier page rendering (country_options area)
        block = _extract_block_around(source, "# Build country options for filter", before=0, after=30)
        if not block:
            block = _extract_block_around(source, "country_options = [Option", before=5, after=30)
        assert block, "Could not find supplier country options block in main.py"

        has_shared_map = (
            "COUNTRY_NAME_MAP" in block
            or "map_supplier_country" in block
            or "translate_country" in block
            or "get_country_name" in block
        )
        assert has_shared_map, (
            "Supplier list page does not reference any shared country translation map. "
            "Both the filter dropdown labels and the table location column should use "
            "COUNTRY_NAME_MAP or equivalent to translate ISO codes to Russian names."
        )

    def test_no_duplicate_country_dicts_in_main(self):
        """There should be at most one country name translation dict at module level.

        Currently country_names is defined locally inside a function (~line 17004).
        It should be promoted to a module-level COUNTRY_NAME_MAP and reused everywhere,
        avoiding scattered duplicate definitions.
        """
        source = _read_main_source()
        # Count local country_names = { definitions inside functions
        local_dicts = re.findall(
            r'^\s+country_names\s*=\s*\{',
            source,
            re.MULTILINE,
        )
        # If there are local dicts, there should also be a module-level shared one
        if local_dicts:
            has_module_level = bool(
                re.search(r'^COUNTRY_NAME_MAP\s*=\s*\{', source, re.MULTILINE)
            )
            assert has_module_level, (
                f"Found {len(local_dicts)} local country_names dict(s) inside functions, "
                f"but no module-level COUNTRY_NAME_MAP. The local dict(s) should be "
                f"refactored into a shared module-level constant for reuse across "
                f"supplier list, customs workspace, and logistics sections."
            )
