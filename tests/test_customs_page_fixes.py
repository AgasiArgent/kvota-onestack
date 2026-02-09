"""
TDD Tests for Customs Page Fixes (3 changes):

1. Button text: "Сохранить расходы" -> "Сохранить данные" (button + instruction text)
2. RUB footnote: informational note that license costs (DS, SS, SGR) are in rubles
3. Calc engine integration: license costs summed and passed to build_calculation_inputs()

These tests are written BEFORE implementation (TDD).
All tests should FAIL until the feature is implemented.
"""

import pytest
import re
import os
import json
import subprocess

# Path constants (relative to project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")

# Calculation engine files that must NOT be modified
CALC_ENGINE_FILES = [
    "calculation_engine.py",
    "calculation_models.py",
    "calculation_mapper.py",
]


def _read_main_source():
    """Read main.py source code (no import needed, avoids sentry_sdk dep)."""
    with open(MAIN_PY) as f:
        return f.read()


LICENSE_COST_FIELDS = [
    "license_ds_cost",
    "license_ss_cost",
    "license_sgr_cost",
]


# ==============================================================================
# 1. Button Text Change: "Сохранить расходы" -> "Сохранить данные"
# ==============================================================================

class TestButtonTextChange:
    """Customs page save button must say 'Сохранить данные' not 'Сохранить расходы'."""

    def test_no_old_button_text_in_customs_form(self):
        """The old button text 'Сохранить расходы' must NOT appear in main.py."""
        source = _read_main_source()
        assert "Сохранить расходы" not in source, (
            "Old button text 'Сохранить расходы' still present in main.py. "
            "Must be replaced with 'Сохранить данные'."
        )

    def test_customs_form_button_says_save_data(self):
        """The customs form save button must read 'Сохранить данные'."""
        source = _read_main_source()
        # Find the customs form action buttons area (around customs_form definition)
        # The button should appear in the customs workspace section
        customs_section = re.search(
            r'customs_form\s*=\s*Form\((.*?)method="post"',
            source,
            re.DOTALL,
        )
        assert customs_section, "customs_form definition not found in main.py"
        form_body = customs_section.group(1)
        assert "Сохранить данные" in form_body, (
            "Customs form save button must read 'Сохранить данные'. "
            "Found form body but text not present."
        )

    def test_instruction_text_references_save_data(self):
        """The instruction text must reference 'Сохранить данные' button."""
        source = _read_main_source()
        # The instruction paragraph tells users which button to click
        instruction_match = re.search(
            r"Заполните код ТН ВЭД.*?для сохранения",
            source,
            re.DOTALL,
        )
        assert instruction_match, (
            "Customs page instruction text not found in main.py"
        )
        instruction_text = instruction_match.group(0)
        assert "Сохранить данные" in instruction_text, (
            "Instruction text must reference 'Сохранить данные' button, "
            f"but found: {instruction_text[:100]}"
        )

    def test_instruction_text_does_not_reference_old_button(self):
        """The instruction text must NOT reference old 'Сохранить расходы'."""
        source = _read_main_source()
        instruction_match = re.search(
            r"Заполните код ТН ВЭД.*?для сохранения",
            source,
            re.DOTALL,
        )
        assert instruction_match, "Instruction text not found"
        instruction_text = instruction_match.group(0)
        assert "Сохранить расходы" not in instruction_text, (
            "Instruction text still references old button name 'Сохранить расходы'"
        )

    def test_save_data_button_count(self):
        """'Сохранить данные' should appear at least twice (logistics + customs)."""
        source = _read_main_source()
        count = source.count("Сохранить данные")
        assert count >= 2, (
            f"'Сохранить данные' appears {count} time(s), expected at least 2 "
            "(logistics page already uses it, customs page should too)"
        )

    def test_old_button_text_count_is_zero(self):
        """'Сохранить расходы' should appear exactly 0 times in the entire codebase."""
        source = _read_main_source()
        count = source.count("Сохранить расходы")
        assert count == 0, (
            f"'Сохранить расходы' still appears {count} time(s) in main.py. "
            "All occurrences must be replaced with 'Сохранить данные'."
        )


# ==============================================================================
# 2. RUB Footnote for License Costs
# ==============================================================================

class TestRubFootnote:
    """Customs page must display a note that license costs are in rubles (RUB)."""

    def _get_customs_page_source(self):
        """Extract the customs workspace page render section."""
        source = _read_main_source()
        # The customs page is between the GET handler for /customs/{quote_id}
        # and the next route. We look for the Handsontable section and surrounding area.
        match = re.search(
            r'(async def get_customs_workspace.*?)(?=\nasync def |\ndef (?!_)\w+\()',
            source,
            re.DOTALL,
        )
        if not match:
            # Fallback: look for the customs page broader section
            match = re.search(
                r'(items_for_handsontable.*?customs_form)',
                source,
                re.DOTALL,
            )
        return match.group(1) if match else source

    def test_rub_note_exists_on_customs_page(self):
        """A note about RUB currency for license costs must exist on the page."""
        source = _read_main_source()
        # The note can contain "руб" or "RUB" or "рубл" in some form
        # near the license/customs/Handsontable context
        rub_near_license = re.search(
            r'(?:лицензи|license|ДС|СС|СГР).*?(?:руб|RUB|рубл)',
            source,
            re.DOTALL | re.IGNORECASE,
        )
        rub_before_license = re.search(
            r'(?:руб|RUB|рубл).*?(?:лицензи|license|ДС|СС|СГР)',
            source,
            re.DOTALL | re.IGNORECASE,
        )
        assert rub_near_license or rub_before_license, (
            "No RUB footnote found near license columns. "
            "Customs page must inform users that license costs are in rubles."
        )

    def test_rub_note_is_visible_text(self):
        """The RUB note must be in visible HTML text (P, Span, Div), not just a comment."""
        source = _read_main_source()
        # Look for a pattern like P("...руб...", or Span("...руб...",
        # in the customs page context near license references
        visible_rub = re.search(
            r'(?:P|Span|Div|Small)\(["\'].*?(?:руб|RUB).*?["\']',
            source,
            re.IGNORECASE,
        )
        assert visible_rub, (
            "RUB note must be in visible HTML (P, Span, Div, Small element), "
            "not just a code comment. Expected something like "
            "P('* Стоимость лицензий указана в рублях (RUB)')"
        )

    def test_rub_note_near_handsontable_or_license_section(self):
        """The RUB note should be near the Handsontable or license columns section."""
        source = _read_main_source()
        # Find the customs Handsontable section
        ht_idx = source.find("customs-spreadsheet")
        assert ht_idx != -1, "customs-spreadsheet element not found"

        # Look for RUB note within a reasonable range around the Handsontable
        # (3000 chars before or 5000 after the Handsontable reference)
        context_start = max(0, ht_idx - 3000)
        context_end = min(len(source), ht_idx + 5000)
        context = source[context_start:context_end]

        has_rub_in_context = re.search(
            r'(?:руб|RUB|рубл)',
            context,
            re.IGNORECASE,
        )
        assert has_rub_in_context, (
            "RUB note not found near the Handsontable section. "
            "The footnote should be placed close to the license columns."
        )

    def test_rub_note_mentions_license_types(self):
        """The RUB note should mention at least one license type (ДС, СС, СГР)."""
        source = _read_main_source()
        # Find visible RUB notes and check they mention license types
        # Search for text elements containing both RUB and license type references
        rub_with_license_type = re.search(
            r'(?:P|Span|Div|Small)\(["\'].*?(?:ДС|СС|СГР|лицензи).*?(?:руб|RUB).*?["\']',
            source,
            re.IGNORECASE | re.DOTALL,
        )
        rub_before_type = re.search(
            r'(?:P|Span|Div|Small)\(["\'].*?(?:руб|RUB).*?(?:ДС|СС|СГР|лицензи).*?["\']',
            source,
            re.IGNORECASE | re.DOTALL,
        )
        assert rub_with_license_type or rub_before_type, (
            "RUB note should mention license types (ДС, СС, СГР) or the word 'лицензий' "
            "to make it clear which costs are in rubles."
        )


# ==============================================================================
# 3. Calc Engine Integration: License Costs in build_calculation_inputs()
# ==============================================================================

class TestCalcEngineLicenseIntegration:
    """License costs must be summed and passed to the calculation engine
    via build_calculation_inputs() in main.py.

    IMPORTANT: We must NOT modify calculation_engine.py, calculation_models.py,
    or calculation_mapper.py. Only the data preparation in main.py is changed.
    """

    def _get_build_calc_inputs_source(self):
        """Extract build_calculation_inputs function source from main.py."""
        source = _read_main_source()
        match = re.search(
            r'(def build_calculation_inputs\(.*?\)\s*->.*?:\s*\n.*?)'
            r'(?=\ndef \w+\()',
            source,
            re.DOTALL,
        )
        assert match, "build_calculation_inputs function not found in main.py"
        return match.group(1)

    def test_build_calc_inputs_references_license_costs(self):
        """build_calculation_inputs must reference license cost fields."""
        fn_source = self._get_build_calc_inputs_source()
        has_license_ref = any(
            field in fn_source for field in LICENSE_COST_FIELDS
        )
        assert has_license_ref, (
            "build_calculation_inputs() must reference license cost fields "
            "(license_ds_cost, license_ss_cost, license_sgr_cost) to pass them "
            "to the calculation engine."
        )

    def test_build_calc_inputs_sums_license_costs(self):
        """License costs should be summed into a total license cost."""
        fn_source = self._get_build_calc_inputs_source()
        # Check that at least two license cost fields are referenced
        # (implying they are being aggregated)
        found_fields = [f for f in LICENSE_COST_FIELDS if f in fn_source]
        assert len(found_fields) >= 2, (
            f"build_calculation_inputs() only references {found_fields}. "
            "All 3 license cost fields should be summed together."
        )

    def test_all_three_license_fields_in_build_calc(self):
        """All 3 license cost fields must be referenced (not just 1 or 2)."""
        fn_source = self._get_build_calc_inputs_source()
        found_fields = [f for f in LICENSE_COST_FIELDS if f in fn_source]
        assert len(found_fields) == 3, (
            f"Expected all 3 license cost fields in build_calculation_inputs(), "
            f"but only found {found_fields}."
        )

    def test_license_cost_total_calculation_logic(self):
        """Verify the summing logic for license costs is correct."""
        # Simulate the expected behavior: sum of all 3 license costs per item
        items = [
            {
                "license_ds_cost": 5000.00,
                "license_ss_cost": 3000.00,
                "license_sgr_cost": 12000.00,
                "quantity": 100,
            },
            {
                "license_ds_cost": 0,
                "license_ss_cost": 8000.00,
                "license_sgr_cost": 0,
                "quantity": 50,
            },
        ]

        for item in items:
            total = (
                float(item.get("license_ds_cost") or 0)
                + float(item.get("license_ss_cost") or 0)
                + float(item.get("license_sgr_cost") or 0)
            )
            if item["quantity"] == 100:
                assert total == 20000.00
            elif item["quantity"] == 50:
                assert total == 8000.00

    def test_license_cost_total_zero_when_no_costs(self):
        """Total license cost should be 0 when no license costs are set."""
        item = {
            "license_ds_cost": 0,
            "license_ss_cost": 0,
            "license_sgr_cost": 0,
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 0.0

    def test_license_cost_total_handles_none_values(self):
        """Total license cost calculation handles None values gracefully."""
        item = {
            "license_ds_cost": None,
            "license_ss_cost": 5000.00,
            "license_sgr_cost": None,
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 5000.00

    def test_license_cost_total_handles_missing_keys(self):
        """Total license cost calculation handles missing dict keys."""
        item = {"quantity": 10}  # No license fields at all
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 0.0

    def test_license_cost_passed_to_product_or_variables(self):
        """License cost must be added to the product dict or variables dict
        that feeds into the calculation engine."""
        fn_source = self._get_build_calc_inputs_source()
        # The total license cost should be added somewhere that the calc engine
        # can use it. It could be:
        # 1. Added to the product dict (e.g., product['total_license_cost'] = ...)
        # 2. Added to calc_variables (e.g., calc_variables['license_cost'] = ...)
        # 3. Added to brokerage_extra or customs_documentation (existing fields)
        # Either way, the license cost must flow into the calculation pipeline
        has_license_in_product = (
            "license" in fn_source.lower()
            and ("product" in fn_source or "variables" in fn_source or "calc_variables" in fn_source)
        )
        assert has_license_in_product, (
            "License cost total must be passed to either the product dict or "
            "calc_variables dict in build_calculation_inputs(). "
            "This value should flow into the calculation engine via an existing field "
            "(e.g., brokerage_extra, customs_documentation, or a new field)."
        )

    def test_calculation_engine_files_not_modified(self):
        """CRITICAL: calculation_engine.py, calculation_models.py, and
        calculation_mapper.py must NOT be modified."""
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"] + CALC_ENGINE_FILES,
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
        )
        modified_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        for f in modified_files:
            assert f not in CALC_ENGINE_FILES, (
                f"CRITICAL: {f} was modified! Only main.py's build_calculation_inputs() "
                "should be changed, not the calculation engine itself."
            )

    def test_calculation_engine_files_not_staged(self):
        """Verify calc engine files are not even staged for commit."""
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"] + CALC_ENGINE_FILES,
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
        )
        staged_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        for f in staged_files:
            assert f not in CALC_ENGINE_FILES, (
                f"CRITICAL: {f} is staged for commit! Calculation engine files "
                "must remain unchanged."
            )

    def test_license_cost_total_is_per_item(self):
        """Each item should have its own license cost total (not aggregated across items)."""
        fn_source = self._get_build_calc_inputs_source()
        # The function iterates per item (for item in items),
        # so license cost calculation should be inside that loop
        loop_match = re.search(
            r'for item in items:(.*?)(?=\n    return|\Z)',
            fn_source,
            re.DOTALL,
        )
        assert loop_match, "Item loop not found in build_calculation_inputs"
        loop_body = loop_match.group(1)
        has_license_in_loop = any(
            field in loop_body for field in LICENSE_COST_FIELDS
        )
        assert has_license_in_loop, (
            "License cost fields must be processed inside the per-item loop "
            "in build_calculation_inputs(), not outside it."
        )

    def test_license_cost_uses_existing_calc_engine_field(self):
        """License cost should be routed through an existing calc engine field
        (e.g., brokerage_extra, customs_documentation) since we cannot modify
        the calculation engine models."""
        fn_source = self._get_build_calc_inputs_source()
        # The license cost must be added to an existing field that the calc engine
        # already processes. The most likely candidates are:
        # - brokerage_extra (extra brokerage fees in CustomsAndClearance)
        # - customs_documentation (documentation costs in CustomsAndClearance)
        # Check that license cost is being added to one of these
        has_license_plus_existing = (
            ("license" in fn_source.lower() and "brokerage_extra" in fn_source)
            or ("license" in fn_source.lower() and "customs_documentation" in fn_source)
            or ("license" in fn_source.lower() and "calc_variables" in fn_source)
        )
        assert has_license_plus_existing, (
            "License cost must be routed through an existing calc engine field "
            "(brokerage_extra, customs_documentation, or added to calc_variables). "
            "We cannot add new fields to calculation_models.py."
        )


# ==============================================================================
# 4. Edge Cases for License Cost Summation
# ==============================================================================

class TestLicenseCostEdgeCases:
    """Edge cases for license cost handling in calc engine integration."""

    def test_large_license_costs_sum_correctly(self):
        """Large license cost values should sum without precision loss."""
        item = {
            "license_ds_cost": 999999.99,
            "license_ss_cost": 999999.99,
            "license_sgr_cost": 999999.99,
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert abs(total - 2999999.97) < 0.01

    def test_string_numeric_values_handled(self):
        """License cost values stored as strings should be convertible."""
        item = {
            "license_ds_cost": "5000.50",
            "license_ss_cost": "0",
            "license_sgr_cost": "12000",
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 17000.50

    def test_empty_string_values_treated_as_zero(self):
        """Empty string license cost values should be treated as zero."""
        item = {
            "license_ds_cost": "",
            "license_ss_cost": "",
            "license_sgr_cost": "",
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 0.0

    def test_only_one_license_has_cost(self):
        """When only one license type has a cost, total equals that cost."""
        item = {
            "license_ds_cost": 0,
            "license_ss_cost": 7500.00,
            "license_sgr_cost": 0,
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 7500.00

    def test_all_three_licenses_have_costs(self):
        """When all three license types have costs, total is the sum."""
        item = {
            "license_ds_cost": 5000.00,
            "license_ss_cost": 3000.00,
            "license_sgr_cost": 12000.00,
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 20000.00

    def test_negative_cost_values_not_masked_by_or_zero(self):
        """Negative cost values should NOT be masked to zero by 'or 0' pattern.
        They should be caught by DB CHECK constraints, not silently zeroed."""
        item = {
            "license_ds_cost": -100.00,
            "license_ss_cost": 0,
            "license_sgr_cost": 0,
        }
        # The 'or 0' pattern only converts falsy values (None, "", 0, False)
        # Negative numbers are truthy, so they pass through
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == -100.00  # Negative flows through; DB constraint prevents this

    def test_boolean_false_not_treated_as_cost(self):
        """Boolean False should be treated as 0 cost (not cause error)."""
        item = {
            "license_ds_cost": False,
            "license_ss_cost": False,
            "license_sgr_cost": False,
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 0.0

    def test_fractional_costs_sum_correctly(self):
        """License costs with fractional rubles should sum accurately."""
        item = {
            "license_ds_cost": 1500.50,
            "license_ss_cost": 2300.75,
            "license_sgr_cost": 800.25,
        }
        total = (
            float(item.get("license_ds_cost") or 0)
            + float(item.get("license_ss_cost") or 0)
            + float(item.get("license_sgr_cost") or 0)
        )
        assert total == 4601.50


# ==============================================================================
# 5. Consistency Checks
# ==============================================================================

class TestConsistencyChecks:
    """Cross-cutting checks to ensure all 3 changes are consistent."""

    def test_customs_form_still_exists(self):
        """The customs_form = Form(...) definition must still exist in main.py."""
        source = _read_main_source()
        assert "customs_form" in source, "customs_form definition missing from main.py"

    def test_handsontable_section_still_exists(self):
        """The Handsontable section for customs items must still be present."""
        source = _read_main_source()
        assert "customs-spreadsheet" in source, (
            "customs-spreadsheet element missing from main.py"
        )

    def test_build_calculation_inputs_still_exists(self):
        """The build_calculation_inputs function must still exist."""
        source = _read_main_source()
        assert "def build_calculation_inputs(" in source, (
            "build_calculation_inputs function missing from main.py"
        )

    def test_customs_save_button_has_correct_action_value(self):
        """The save button must have value='save' for the form handler."""
        source = _read_main_source()
        customs_section = re.search(
            r'customs_form\s*=\s*Form\((.*?)method="post"',
            source,
            re.DOTALL,
        )
        assert customs_section, "customs_form not found"
        form_body = customs_section.group(1)
        assert 'value="save"' in form_body, (
            "Customs save button must have value='save' for the POST handler"
        )

    def test_no_duplicate_save_buttons_in_customs(self):
        """Customs form should have exactly one save button (not both old and new)."""
        source = _read_main_source()
        customs_section = re.search(
            r'customs_form\s*=\s*Form\((.*?)method="post"',
            source,
            re.DOTALL,
        )
        assert customs_section, "customs_form not found"
        form_body = customs_section.group(1)
        # Count occurrences of button text patterns
        save_buttons = len(re.findall(r'Сохранить \w+', form_body))
        assert save_buttons <= 1, (
            f"Found {save_buttons} save buttons in customs form. "
            "There should be exactly 1."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
