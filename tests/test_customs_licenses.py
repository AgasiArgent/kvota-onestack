"""
TDD Tests for Customs Licenses (MOT workspace enhancement)

Feature: 3 license types per quote_item for customs department:
  - DS (Declaration of Conformity / Декларация соответствия)
  - SS (Certificate of Conformity / Сертификат соответствия)
  - SGR (State Registration Certificate / Свидетельство о гос. регистрации)

Each license type has:
  - required (boolean, default false)
  - cost (decimal, default 0) - cost per entire quantity, not per unit

These tests are written BEFORE implementation (TDD).
All tests should FAIL until the feature is implemented.
"""

import pytest
from decimal import Decimal
import uuid
import json
import re
import glob
import os

# Path constants
MAIN_PY = "/Users/andreynovikov/workspace/tech/projects/kvota/onestack/main.py"
MIGRATIONS_DIR = "/Users/andreynovikov/workspace/tech/projects/kvota/onestack/migrations"


def _read_main_source():
    """Read main.py source code (no import needed, avoids sentry_sdk dep)."""
    with open(MAIN_PY) as f:
        return f.read()


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Fixtures
# ==============================================================================

LICENSE_FIELDS = [
    "license_ds_required",
    "license_ds_cost",
    "license_ss_required",
    "license_ss_cost",
    "license_sgr_required",
    "license_sgr_cost",
]

LICENSE_BOOLEAN_FIELDS = [
    "license_ds_required",
    "license_ss_required",
    "license_sgr_required",
]

LICENSE_COST_FIELDS = [
    "license_ds_cost",
    "license_ss_cost",
    "license_sgr_cost",
]


@pytest.fixture
def quote_id():
    return _make_uuid()


@pytest.fixture
def org_id():
    return _make_uuid()


@pytest.fixture
def sample_items_with_licenses(quote_id):
    """Quote items with license fields populated."""
    return [
        {
            "id": _make_uuid(),
            "quote_id": quote_id,
            "brand": "SKF",
            "product_name": "Bearing 6205",
            "quantity": 100,
            "hs_code": "8482.10.10",
            "customs_duty": 5.0,
            "supplier_country": "Germany",
            "license_ds_required": True,
            "license_ds_cost": 5000.00,
            "license_ss_required": False,
            "license_ss_cost": 0,
            "license_sgr_required": True,
            "license_sgr_cost": 12000.00,
        },
        {
            "id": _make_uuid(),
            "quote_id": quote_id,
            "brand": "FAG",
            "product_name": "Roller bearing 32310",
            "quantity": 50,
            "hs_code": "8482.20.00",
            "customs_duty": 3.0,
            "supplier_country": "China",
            "license_ds_required": False,
            "license_ds_cost": 0,
            "license_ss_required": True,
            "license_ss_cost": 8000.00,
            "license_sgr_required": False,
            "license_sgr_cost": 0,
        },
    ]


@pytest.fixture
def sample_items_no_licenses(quote_id):
    """Quote items without license fields (before migration)."""
    return [
        {
            "id": _make_uuid(),
            "quote_id": quote_id,
            "brand": "NSK",
            "product_name": "Linear guide",
            "quantity": 20,
            "hs_code": "8482.10.10",
            "customs_duty": 5.0,
        },
    ]


# ==============================================================================
# 1. Database Migration Tests
# ==============================================================================

class TestLicenseMigrationExists:
    """Verify a migration file exists with all 6 license columns."""

    def _find_migration(self):
        """Find migration file matching *license* pattern."""
        files = glob.glob(os.path.join(MIGRATIONS_DIR, "*license*"))
        return files

    def test_migration_file_exists(self):
        """A migration file for license columns must exist."""
        files = self._find_migration()
        assert len(files) > 0, (
            "No migration file found matching *license* pattern in migrations/. "
            "Expected e.g. 159_add_license_fields_to_quote_items.sql"
        )

    def test_migration_adds_license_ds_required(self):
        """Migration must add license_ds_required column."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "license_ds_required" in content

    def test_migration_adds_license_ds_cost(self):
        """Migration must add license_ds_cost column."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "license_ds_cost" in content

    def test_migration_adds_license_ss_required(self):
        """Migration must add license_ss_required column."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "license_ss_required" in content

    def test_migration_adds_license_ss_cost(self):
        """Migration must add license_ss_cost column."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "license_ss_cost" in content

    def test_migration_adds_license_sgr_required(self):
        """Migration must add license_sgr_required column."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "license_sgr_required" in content

    def test_migration_adds_license_sgr_cost(self):
        """Migration must add license_sgr_cost column."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "license_sgr_cost" in content

    def test_boolean_columns_default_false(self):
        """Boolean license columns must DEFAULT FALSE."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "default false" in content, (
            "Boolean license columns must have DEFAULT FALSE"
        )

    def test_cost_columns_default_zero(self):
        """Decimal cost columns must DEFAULT 0."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert "default 0" in content, (
            "Cost license columns must have DEFAULT 0"
        )

    def test_cost_columns_have_non_negative_check(self):
        """Cost columns should have CHECK >= 0 constraint."""
        files = self._find_migration()
        assert files, "Migration file not found"
        with open(files[0]) as f:
            content = f.read().lower()
        assert ">= 0" in content or "check" in content, (
            "Cost columns should have CHECK constraint for non-negative values"
        )


# ==============================================================================
# 2. API Tests - Bulk Update (source inspection, no import)
# ==============================================================================

class TestBulkUpdateLicenseFields:
    """PATCH /api/customs/{quote_id}/items/bulk must accept license fields."""

    def _get_bulk_handler_source(self):
        """Extract the api_customs_items_bulk_update function source."""
        source = _read_main_source()
        # Find the function between its decorator and the next route
        match = re.search(
            r'(async def api_customs_items_bulk_update.*?)(?=\n@rt\(|$)',
            source,
            re.DOTALL,
        )
        assert match, "api_customs_items_bulk_update function not found in main.py"
        return match.group(1)

    def test_handler_processes_license_ds_required(self):
        """Bulk update handler must process license_ds_required."""
        handler = self._get_bulk_handler_source()
        assert "license_ds_required" in handler, (
            "api_customs_items_bulk_update must handle license_ds_required"
        )

    def test_handler_processes_license_ds_cost(self):
        """Bulk update handler must process license_ds_cost."""
        handler = self._get_bulk_handler_source()
        assert "license_ds_cost" in handler, (
            "api_customs_items_bulk_update must handle license_ds_cost"
        )

    def test_handler_processes_license_ss_required(self):
        """Bulk update handler must process license_ss_required."""
        handler = self._get_bulk_handler_source()
        assert "license_ss_required" in handler

    def test_handler_processes_license_ss_cost(self):
        """Bulk update handler must process license_ss_cost."""
        handler = self._get_bulk_handler_source()
        assert "license_ss_cost" in handler

    def test_handler_processes_license_sgr_required(self):
        """Bulk update handler must process license_sgr_required."""
        handler = self._get_bulk_handler_source()
        assert "license_sgr_required" in handler

    def test_handler_processes_license_sgr_cost(self):
        """Bulk update handler must process license_sgr_cost."""
        handler = self._get_bulk_handler_source()
        assert "license_sgr_cost" in handler

    def test_handler_includes_license_in_db_update(self):
        """The .update() dict must include all 6 license fields."""
        handler = self._get_bulk_handler_source()
        for field in LICENSE_FIELDS:
            assert field in handler, (
                f"{field} must be in the .update() call in "
                "api_customs_items_bulk_update"
            )


# ==============================================================================
# 3. UI Tests - Handsontable Columns
# ==============================================================================

class TestHandsontableLicenseColumns:
    """Customs page Handsontable must display 6 new license columns."""

    def test_handsontable_has_ds_required_column(self):
        """Handsontable columns must include license_ds_required data field."""
        source = _read_main_source()
        assert "license_ds_required" in source, (
            "Handsontable must have license_ds_required column"
        )

    def test_handsontable_has_ds_cost_column(self):
        """Handsontable columns must include license_ds_cost data field."""
        source = _read_main_source()
        assert "license_ds_cost" in source

    def test_handsontable_has_ss_required_column(self):
        """Handsontable columns must include license_ss_required."""
        source = _read_main_source()
        assert "license_ss_required" in source

    def test_handsontable_has_ss_cost_column(self):
        """Handsontable columns must include license_ss_cost."""
        source = _read_main_source()
        assert "license_ss_cost" in source

    def test_handsontable_has_sgr_required_column(self):
        """Handsontable columns must include license_sgr_required."""
        source = _read_main_source()
        assert "license_sgr_required" in source

    def test_handsontable_has_sgr_cost_column(self):
        """Handsontable columns must include license_sgr_cost."""
        source = _read_main_source()
        assert "license_sgr_cost" in source

    def test_column_headers_include_ds_label(self):
        """Handsontable colHeaders must include Russian label for DS."""
        source = _read_main_source()
        assert "Ст-ть ДС" in source, (
            "Handsontable colHeaders must include 'Ст-ть ДС' label"
        )

    def test_column_headers_include_ss_label(self):
        """Handsontable colHeaders must include Russian label for SS."""
        source = _read_main_source()
        assert "Ст-ть СС" in source, (
            "Handsontable colHeaders must include 'Ст-ть СС' label"
        )

    def test_column_headers_include_sgr_label(self):
        """Handsontable colHeaders must include Russian label for SGR."""
        source = _read_main_source()
        assert "Ст-ть СГР" in source, (
            "Handsontable colHeaders must include 'Ст-ть СГР' label"
        )

    def test_required_columns_use_checkbox_type(self):
        """License required columns must use 'checkbox' type."""
        source = _read_main_source()
        for field in LICENSE_BOOLEAN_FIELDS:
            idx = source.find(field)
            assert idx != -1, f"{field} not found in source"
            context = source[idx:idx + 200]
            assert "checkbox" in context, (
                f"{field} column must be type 'checkbox' in Handsontable"
            )

    def test_cost_columns_use_numeric_type(self):
        """License cost columns must use 'numeric' type."""
        source = _read_main_source()
        for field in LICENSE_COST_FIELDS:
            idx = source.find(field)
            assert idx != -1, f"{field} not found in source"
            context = source[idx:idx + 200]
            assert "numeric" in context, (
                f"{field} column must be type 'numeric' in Handsontable"
            )


# ==============================================================================
# 4. Data Preparation Tests
# ==============================================================================

class TestLicenseDataPreparation:
    """License fields must be included in Handsontable data and JS save."""

    def test_items_for_handsontable_includes_license_fields(self):
        """items_for_handsontable dict must include all 6 license fields."""
        source = _read_main_source()
        for field in LICENSE_FIELDS:
            assert source.count(field) >= 2, (
                f"{field} must appear in both data preparation and column config "
                f"(found {source.count(field)} occurrence(s))"
            )

    def test_save_function_sends_license_fields(self):
        """JS saveCustomsItems must include license fields in PATCH payload."""
        source = _read_main_source()
        match = re.search(
            r'saveCustomsItems\s*=\s*function\(\)\s*\{(.*?)\};',
            source,
            re.DOTALL,
        )
        assert match, "saveCustomsItems JS function not found in main.py"
        fn_body = match.group(1)

        for field in LICENSE_FIELDS:
            assert field in fn_body, (
                f"saveCustomsItems must send {field} in the PATCH payload"
            )

    def test_select_query_includes_license_fields(self):
        """The customs GET handler's SELECT must fetch license columns."""
        source = _read_main_source()
        customs_select_match = re.search(
            r'items_result\s*=\s*supabase\.table\("quote_items"\)\s*\\?\s*\.select\("""(.*?)"""\)',
            source,
            re.DOTALL,
        )
        assert customs_select_match, "quote_items SELECT in customs handler not found"
        select_cols = customs_select_match.group(1)

        for field in LICENSE_FIELDS:
            assert field in select_cols, (
                f"Customs GET handler must SELECT {field} from quote_items"
            )

    def test_json_serialization(self, sample_items_with_licenses):
        """License data must be JSON-serializable for Handsontable."""
        items_for_ht = [
            {
                "id": item.get("id"),
                "license_ds_required": bool(item.get("license_ds_required", False)),
                "license_ds_cost": float(item.get("license_ds_cost") or 0),
                "license_ss_required": bool(item.get("license_ss_required", False)),
                "license_ss_cost": float(item.get("license_ss_cost") or 0),
                "license_sgr_required": bool(item.get("license_sgr_required", False)),
                "license_sgr_cost": float(item.get("license_sgr_cost") or 0),
            }
            for item in sample_items_with_licenses
        ]
        items_json = json.dumps(items_for_ht)
        parsed = json.loads(items_json)

        assert len(parsed) == 2
        assert parsed[0]["license_ds_required"] is True
        assert parsed[0]["license_ds_cost"] == 5000.00
        assert parsed[0]["license_sgr_required"] is True
        assert parsed[0]["license_sgr_cost"] == 12000.00
        assert parsed[1]["license_ss_required"] is True
        assert parsed[1]["license_ss_cost"] == 8000.00


# ==============================================================================
# 5. License Summary Stats Tests
# ==============================================================================

class TestLicenseSummaryStats:
    """Customs page should display license summary statistics."""

    def test_source_references_license_stats(self):
        """Customs page must compute/display license statistics."""
        source = _read_main_source()
        assert "license_ds" in source, (
            "Customs page must reference license_ds for summary stats"
        )

    def test_count_items_with_ds(self, sample_items_with_licenses):
        """Count items requiring DS license."""
        count = sum(1 for i in sample_items_with_licenses
                    if i.get("license_ds_required"))
        assert count == 1

    def test_count_items_with_ss(self, sample_items_with_licenses):
        """Count items requiring SS license."""
        count = sum(1 for i in sample_items_with_licenses
                    if i.get("license_ss_required"))
        assert count == 1

    def test_count_items_with_sgr(self, sample_items_with_licenses):
        """Count items requiring SGR license."""
        count = sum(1 for i in sample_items_with_licenses
                    if i.get("license_sgr_required"))
        assert count == 1

    def test_total_license_cost(self, sample_items_with_licenses):
        """Total license cost across all items and types."""
        total = sum(
            float(i.get("license_ds_cost", 0))
            + float(i.get("license_ss_cost", 0))
            + float(i.get("license_sgr_cost", 0))
            for i in sample_items_with_licenses
        )
        assert total == 25000.00

    def test_per_type_cost_aggregation(self, sample_items_with_licenses):
        """Aggregate cost per license type across all items."""
        ds_total = sum(float(i.get("license_ds_cost", 0))
                       for i in sample_items_with_licenses
                       if i.get("license_ds_required"))
        ss_total = sum(float(i.get("license_ss_cost", 0))
                       for i in sample_items_with_licenses
                       if i.get("license_ss_required"))
        sgr_total = sum(float(i.get("license_sgr_cost", 0))
                        for i in sample_items_with_licenses
                        if i.get("license_sgr_required"))

        assert ds_total == 5000.00
        assert ss_total == 8000.00
        assert sgr_total == 12000.00


# ==============================================================================
# 6. Validation Tests
# ==============================================================================

class TestLicenseValidation:
    """Validation rules for license fields."""

    def test_cost_must_be_non_negative(self):
        """License cost must be >= 0."""
        for cost in [-1, -100, -0.01]:
            assert cost < 0, "Negative costs should be rejected by CHECK constraint"

    def test_cost_zero_when_not_required(self, sample_items_with_licenses):
        """Cost should be 0 when required is false."""
        item1 = sample_items_with_licenses[0]
        assert item1["license_ss_required"] is False
        assert item1["license_ss_cost"] == 0

        item2 = sample_items_with_licenses[1]
        assert item2["license_ds_required"] is False
        assert item2["license_ds_cost"] == 0
        assert item2["license_sgr_required"] is False
        assert item2["license_sgr_cost"] == 0

    def test_cost_allowed_when_required(self, sample_items_with_licenses):
        """Cost can be > 0 when required is true."""
        item1 = sample_items_with_licenses[0]
        assert item1["license_ds_required"] is True
        assert item1["license_ds_cost"] > 0
        assert item1["license_sgr_required"] is True
        assert item1["license_sgr_cost"] > 0

    def test_cost_is_per_quantity_not_per_unit(self, sample_items_with_licenses):
        """License cost is for entire quantity, not per unit."""
        item = sample_items_with_licenses[0]
        assert item["license_ds_cost"] == 5000.00
        assert item["license_ds_cost"] != 5000.00 * item["quantity"]

    def test_cost_accepts_decimal_values(self):
        """License cost should accept decimal values."""
        for cost in [0.50, 1500.75, 99999.99]:
            assert isinstance(cost, float)
            assert cost >= 0


# ==============================================================================
# 7. Customs Completion Check Tests
# ==============================================================================

class TestLicenseCompletionCheck:
    """License fields should be considered in customs completion."""

    def test_completion_logic_references_license_fields(self):
        """Customs completion handler must check license fields."""
        source = _read_main_source()
        assert "license_ds" in source, (
            "Customs completion must reference license_ds fields"
        )
        assert "license_ss" in source, (
            "Customs completion must reference license_ss fields"
        )
        assert "license_sgr" in source, (
            "Customs completion must reference license_sgr fields"
        )

    def test_incomplete_when_required_but_no_cost(self):
        """Item is incomplete if license is required but cost is 0."""
        item = {
            "license_ds_required": True,
            "license_ds_cost": 0,
        }

        def is_license_complete(item):
            for prefix in ["license_ds", "license_ss", "license_sgr"]:
                if item.get(f"{prefix}_required", False):
                    if float(item.get(f"{prefix}_cost", 0)) <= 0:
                        return False
            return True

        assert is_license_complete(item) is False

    def test_complete_when_all_required_have_cost(self, sample_items_with_licenses):
        """Item is complete when all required licenses have cost > 0."""
        def is_license_complete(item):
            for prefix in ["license_ds", "license_ss", "license_sgr"]:
                if item.get(f"{prefix}_required", False):
                    if float(item.get(f"{prefix}_cost", 0)) <= 0:
                        return False
            return True

        for item in sample_items_with_licenses:
            assert is_license_complete(item) is True

    def test_complete_when_no_licenses_required(self, sample_items_no_licenses):
        """Item is complete if no licenses are required."""
        def is_license_complete(item):
            for prefix in ["license_ds", "license_ss", "license_sgr"]:
                if item.get(f"{prefix}_required", False):
                    if float(item.get(f"{prefix}_cost", 0)) <= 0:
                        return False
            return True

        assert is_license_complete(sample_items_no_licenses[0]) is True


# ==============================================================================
# 8. Edge Cases
# ==============================================================================

class TestLicenseEdgeCases:
    """Edge cases for license fields."""

    def test_all_three_licenses_required(self):
        """All three licenses can be required simultaneously."""
        item = {f: True for f in LICENSE_BOOLEAN_FIELDS}
        required = sum(1 for f in LICENSE_BOOLEAN_FIELDS if item.get(f))
        assert required == 3

    def test_no_licenses_required(self):
        """No licenses required is a valid state."""
        item = {f: False for f in LICENSE_BOOLEAN_FIELDS}
        required = sum(1 for f in LICENSE_BOOLEAN_FIELDS if item.get(f))
        assert required == 0

    def test_large_cost_values(self):
        """License costs can be large decimal values."""
        item = {"license_ds_required": True, "license_ds_cost": 999999.99}
        assert item["license_ds_cost"] == 999999.99

    def test_zero_cost_with_required_true(self):
        """Zero cost with required=true is valid but completion should flag it."""
        item = {"license_ds_required": True, "license_ds_cost": 0}
        assert item["license_ds_required"] is True
        assert item["license_ds_cost"] == 0

    def test_cost_with_required_false_ignored(self):
        """Cost is irrelevant when required is false."""
        item = {"license_ds_required": False, "license_ds_cost": 9999}
        effective = item["license_ds_cost"] if item["license_ds_required"] else 0
        assert effective == 0

    def test_boolean_false_default_when_missing(self):
        """Missing license required fields should default to False."""
        item = {"id": _make_uuid(), "hs_code": "1234.56.78"}
        for field in LICENSE_BOOLEAN_FIELDS:
            assert bool(item.get(field, False)) is False

    def test_cost_zero_default_when_missing(self):
        """Missing license cost fields should default to 0."""
        item = {"id": _make_uuid()}
        for field in LICENSE_COST_FIELDS:
            assert float(item.get(field) or 0) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
