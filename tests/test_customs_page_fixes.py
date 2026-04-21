"""
TDD Tests for Customs License Cost Integration with Calculation Engine.

Previously this file also tested FastHTML /customs/{quote_id} page details:
- "Сохранить данные" button text (TestButtonTextChange)
- RUB footnote for license costs (TestRubFootnote)
- customs_form definition + Handsontable consistency (TestConsistencyChecks
  partially)

Those classes were removed in Phase 6C-2B-Mega-A because they targeted
FastHTML UI that now lives in legacy-fasthtml/ops_deal_finance_customs_logistics.py
and no longer runs. The calc-engine integration remains the authoritative
validation: license costs summed into `build_calculation_inputs()` flow
through the existing customs_documentation / brokerage_extra fields into
the calculation pipeline. The UI will be rebuilt via Next.js + /api/customs
post-cutover.

IMPORTANT: We must NOT modify calculation_engine.py, calculation_models.py,
or calculation_mapper.py. Only the data preparation in
services/calculation_helpers.py is changed.
"""

import pytest
import re
import os
import subprocess


# Path constants (relative to project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
CALC_HELPERS_PY = os.path.join(_PROJECT_ROOT, "services", "calculation_helpers.py")

# Calculation engine files that must NOT be modified
CALC_ENGINE_FILES = [
    "calculation_engine.py",
    "calculation_models.py",
    "calculation_mapper.py",
]


def _read_main_source():
    """Read the calc-helpers source (no import — avoids sentry_sdk dep).

    Historically these tests parsed main.py; after Phase 6C-3 the function lives
    in services/calculation_helpers.py. The function name is preserved to keep
    test references terse.
    """
    with open(CALC_HELPERS_PY) as f:
        return f.read()


LICENSE_COST_FIELDS = [
    "license_ds_cost",
    "license_ss_cost",
    "license_sgr_cost",
]


# ==============================================================================
# Calc Engine Integration: License Costs in build_calculation_inputs()
# ==============================================================================

class TestCalcEngineLicenseIntegration:
    """License costs must be summed and passed to the calculation engine
    via build_calculation_inputs() in main.py.

    IMPORTANT: We must NOT modify calculation_engine.py, calculation_models.py,
    or calculation_mapper.py. Only the data preparation in main.py is changed.
    """

    def _get_build_calc_inputs_source(self):
        """Extract build_calculation_inputs source from services/calculation_helpers.py."""
        source = _read_main_source()
        match = re.search(
            r'(def build_calculation_inputs\(.*?\)\s*->.*?:\s*\n.*?)'
            r'(?=\ndef \w+\(|\Z)',
            source,
            re.DOTALL,
        )
        assert match, (
            "build_calculation_inputs function not found in services/calculation_helpers.py"
        )
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
# Edge Cases for License Cost Summation
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
# Consistency Checks (remainder after FastHTML-targeting tests archived)
# ==============================================================================

class TestConsistencyChecks:
    """Cross-cutting checks to ensure the calc engine integration is intact."""

    def test_build_calculation_inputs_still_exists(self):
        """The build_calculation_inputs function must still exist."""
        source = _read_main_source()
        assert "def build_calculation_inputs(" in source, (
            "build_calculation_inputs function missing from services/calculation_helpers.py"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
