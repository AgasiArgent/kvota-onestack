"""
TDD Tests for Spec Creation Bug Fix: contract_id, delivery_days, auto-number lost on save.

Root cause: migration 036 created contract_id in wrong schema (public instead of kvota).
Fix: migration 160 ensures columns exist in kvota.specifications (idempotent).

POST handler: main.py ~line 21797 (POST /spec-control/create/{quote_id})
  - spec_data dict building: ~lines 21894-21921
  - Auto-numbering logic: ~lines 21856-21877
  - delivery_days fallback: ~line 21880-21891
  - INSERT: ~line 21924

These tests are written BEFORE implementation (TDD).
Tests that check migration 160 should FAIL until the migration is created.
Tests that verify spec_data dict building should PASS (code already exists).
"""

import pytest
import re
import os
import glob as glob_module
import uuid

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "migrations")


def _read_main_source():
    """Read main.py source code (no import needed, avoids sentry_sdk dep)."""
    with open(MAIN_PY) as f:
        return f.read()


def _read_post_handler_source():
    """Extract POST /spec-control/create/{quote_id} handler source from main.py."""
    content = _read_main_source()
    # Find the POST handler for spec-control/create
    match = re.search(
        r'(@rt\("/spec-control/create/\{quote_id\}"\)\s*def post\(.*?)(?=\n@rt\(|$)',
        content,
        re.DOTALL
    )
    if not match:
        pytest.fail("Could not find POST /spec-control/create/{quote_id} handler in main.py")
    return match.group(0)


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def quote_id():
    return _make_uuid()


@pytest.fixture
def org_id():
    return _make_uuid()


@pytest.fixture
def user_id():
    return _make_uuid()


@pytest.fixture
def contract_id():
    return _make_uuid()


@pytest.fixture
def post_handler_source():
    """Read POST handler source once per test."""
    return _read_post_handler_source()


# ==============================================================================
# 1. spec_data dict building tests: verify all required keys present
# ==============================================================================

class TestSpecDataDictBuilding:
    """
    The POST handler builds a spec_data dict at ~lines 21894-21921 and INSERTs it.
    These tests verify that the dict includes the keys that were previously lost
    due to the schema mismatch bug.
    """

    def test_spec_data_includes_contract_id_key(self, post_handler_source):
        """
        spec_data dict MUST include 'contract_id' key.
        Without it, the contract linkage is lost when saving.
        """
        # Look for contract_id in the spec_data dict definition
        # Pattern: "contract_id": contract_id or "contract_id": ...
        has_contract_id_in_dict = re.search(
            r'spec_data\s*=\s*\{[^}]*["\']contract_id["\']',
            post_handler_source,
            re.DOTALL
        )
        assert has_contract_id_in_dict, (
            "spec_data dict must include 'contract_id' key. "
            "Without it, the contract linkage is lost on INSERT."
        )

    def test_spec_data_includes_delivery_days_key(self, post_handler_source):
        """
        spec_data dict MUST include 'delivery_days' key.
        This is the pre-filled value from calc_variables.delivery_time.
        """
        has_delivery_days_in_dict = re.search(
            r'spec_data\s*=\s*\{[^}]*["\']delivery_days["\']',
            post_handler_source,
            re.DOTALL
        )
        assert has_delivery_days_in_dict, (
            "spec_data dict must include 'delivery_days' key. "
            "Without it, delivery days are lost on INSERT."
        )

    def test_spec_data_includes_delivery_days_type_key(self, post_handler_source):
        """
        spec_data dict MUST include 'delivery_days_type' key.
        Default is 'working days' in Russian.
        """
        has_delivery_days_type = re.search(
            r'spec_data\s*=\s*\{[^}]*["\']delivery_days_type["\']',
            post_handler_source,
            re.DOTALL
        )
        assert has_delivery_days_type, (
            "spec_data dict must include 'delivery_days_type' key. "
            "Without it, the delivery days type is lost on INSERT."
        )

    def test_spec_data_includes_specification_number_key(self, post_handler_source):
        """
        spec_data dict MUST include 'specification_number' key.
        This is either auto-generated from contract or manually provided.
        """
        has_spec_number = re.search(
            r'spec_data\s*=\s*\{[^}]*["\']specification_number["\']',
            post_handler_source,
            re.DOTALL
        )
        assert has_spec_number, (
            "spec_data dict must include 'specification_number' key. "
            "Without it, the auto-generated number from contract is lost."
        )


# ==============================================================================
# 2. Auto-numbering logic tests
# ==============================================================================

class TestAutoNumbering:
    """
    Auto-numbering logic at main.py ~lines 21856-21877:
    - If contract_id is set and no manual specification_number provided,
      auto-generate as "{contract_number}-{next_spec_num}"
    - If contract_id is set and manual specification_number provided, use manual
    - If no contract_id, specification_number stays as provided (or None)
    """

    def test_auto_numbering_triggered_when_contract_and_no_manual_number(self, post_handler_source):
        """
        When contract_id is provided and specification_number is empty/None,
        the handler should auto-generate the specification number.
        Pattern: if contract_id and not specification_number
        """
        has_auto_numbering_condition = re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            post_handler_source
        )
        assert has_auto_numbering_condition, (
            "Auto-numbering must be triggered when contract_id is present "
            "and specification_number is not provided. "
            "Expected pattern: 'if contract_id and not specification_number'"
        )

    def test_auto_numbering_fetches_contract_info(self, post_handler_source):
        """
        Auto-numbering fetches contract_number and next_specification_number
        from customer_contracts table.
        """
        has_contract_fetch = (
            "customer_contracts" in post_handler_source
            and "contract_number" in post_handler_source
            and "next_specification_number" in post_handler_source
        )
        assert has_contract_fetch, (
            "Auto-numbering must fetch contract_number and next_specification_number "
            "from customer_contracts table."
        )

    def test_auto_numbering_format_is_contract_dash_number(self, post_handler_source):
        """
        Auto-generated spec number format: "{contract_number}-{next_spec_num}"
        e.g., "DP-001/2025-1"
        """
        # Look for string formatting pattern like f"{contract_num}-{next_spec_num}"
        has_format = re.search(
            r'f".*\{contract_num.*\}-\{next_spec_num.*\}"',
            post_handler_source
        )
        assert has_format, (
            "Auto-generated specification number must follow format "
            "'{contract_number}-{next_spec_num}'. "
            "Expected f-string pattern in source."
        )

    def test_auto_numbering_increments_counter(self, post_handler_source):
        """
        After generating the spec number, the handler must increment
        next_specification_number in the customer_contracts table.
        """
        has_increment = re.search(
            r'\.update\(\{.*next_specification_number.*next_spec_num\s*\+\s*1',
            post_handler_source,
            re.DOTALL
        )
        assert has_increment, (
            "Auto-numbering must increment next_specification_number in "
            "customer_contracts after generating the spec number."
        )

    def test_manual_number_used_when_provided_with_contract(self, post_handler_source):
        """
        When both contract_id and specification_number are provided,
        the manual number should be used (auto-numbering NOT triggered).
        The condition 'if contract_id and not specification_number' ensures this.
        """
        # The condition already handles this: auto-numbering only fires
        # when specification_number is empty/None
        has_correct_guard = re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            post_handler_source
        )
        assert has_correct_guard, (
            "Manual specification_number must be preserved when provided. "
            "The auto-numbering guard 'if contract_id and not specification_number' "
            "must be present to skip auto-generation when manual number exists."
        )

    def test_no_contract_leaves_spec_number_as_is(self, post_handler_source):
        """
        When no contract_id is provided, specification_number stays as-is
        (either from kwargs or None). No auto-numbering attempt.
        """
        # The contract_id guard ensures no auto-numbering without contract
        has_contract_guard = re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            post_handler_source
        )
        # Also verify contract_id is read from kwargs
        has_contract_from_kwargs = re.search(
            r'contract_id\s*=\s*kwargs\.get\(["\']contract_id["\']\)',
            post_handler_source
        )
        assert has_contract_guard and has_contract_from_kwargs, (
            "When no contract_id in kwargs, specification_number must remain as-is. "
            "contract_id must come from kwargs.get('contract_id')."
        )


# ==============================================================================
# 3. delivery_days fallback tests
# ==============================================================================

class TestDeliveryDaysFallback:
    """
    delivery_days fallback logic at main.py ~line 21880:
    - If delivery_days is provided in form, use it
    - If delivery_days is empty/None, fallback to calc_variables.delivery_time
    """

    def test_delivery_days_read_from_kwargs(self, post_handler_source):
        """
        delivery_days is first read from kwargs (form submission).
        """
        has_kwargs_read = re.search(
            r'delivery_days\s*=\s*safe_int\(kwargs\.get\(["\']delivery_days["\']\)\)',
            post_handler_source
        )
        assert has_kwargs_read, (
            "delivery_days must first be read from kwargs via safe_int(). "
            "Expected: delivery_days = safe_int(kwargs.get('delivery_days'))"
        )

    def test_delivery_days_fallback_to_calc_variables(self, post_handler_source):
        """
        When delivery_days is empty, the handler falls back to
        calc_variables.delivery_time from quote_calculation_variables table.
        """
        has_fallback = (
            "quote_calculation_variables" in post_handler_source
            and "delivery_time" in post_handler_source
        )
        assert has_fallback, (
            "When delivery_days is empty, must fallback to "
            "calc_variables.delivery_time from quote_calculation_variables table."
        )

    def test_delivery_days_fallback_condition(self, post_handler_source):
        """
        Fallback is triggered by 'if not delivery_days' condition.
        """
        has_condition = re.search(
            r'if\s+not\s+delivery_days',
            post_handler_source
        )
        assert has_condition, (
            "Fallback must be triggered by 'if not delivery_days' condition. "
            "This covers both None and 0 (empty form field)."
        )

    def test_delivery_days_fallback_extracts_from_variables_json(self, post_handler_source):
        """
        The fallback reads the 'variables' JSONB column from
        quote_calculation_variables and extracts 'delivery_time' from it.
        """
        has_json_extract = re.search(
            r'variables\.get\(["\']delivery_time["\']\)',
            post_handler_source
        )
        assert has_json_extract, (
            "Fallback must extract delivery_time from the variables JSONB: "
            "variables.get('delivery_time')"
        )


# ==============================================================================
# 4. Source code verification: POST handler references correct keys
# ==============================================================================

class TestSourceCodeVerification:
    """
    Verify the POST handler source code references all required fields
    in the spec_data dict building section.
    """

    def test_post_handler_references_contract_id_in_spec_data(self):
        """POST handler must reference 'contract_id' when building spec_data."""
        source = _read_main_source()
        # Find the spec_data assignment block
        spec_data_match = re.search(
            r'spec_data\s*=\s*\{(.*?)\}',
            source,
            re.DOTALL
        )
        assert spec_data_match, "Could not find spec_data dict in main.py"
        spec_data_block = spec_data_match.group(1)
        assert "contract_id" in spec_data_block, (
            "spec_data dict must contain 'contract_id' key. "
            "This is the fix for the contract linkage being lost."
        )

    def test_post_handler_references_delivery_days_in_spec_data(self):
        """POST handler must reference 'delivery_days' when building spec_data."""
        source = _read_main_source()
        spec_data_match = re.search(
            r'spec_data\s*=\s*\{(.*?)\}',
            source,
            re.DOTALL
        )
        assert spec_data_match, "Could not find spec_data dict in main.py"
        spec_data_block = spec_data_match.group(1)
        assert "delivery_days" in spec_data_block, (
            "spec_data dict must contain 'delivery_days' key. "
            "This is the fix for delivery days being lost on save."
        )

    def test_post_handler_references_specification_number_in_spec_data(self):
        """POST handler must reference 'specification_number' when building spec_data."""
        source = _read_main_source()
        spec_data_match = re.search(
            r'spec_data\s*=\s*\{(.*?)\}',
            source,
            re.DOTALL
        )
        assert spec_data_match, "Could not find spec_data dict in main.py"
        spec_data_block = spec_data_match.group(1)
        assert "specification_number" in spec_data_block, (
            "spec_data dict must contain 'specification_number' key. "
            "This is the fix for auto-numbered spec numbers being lost."
        )

    def test_post_handler_delivery_days_type_default_value(self):
        """delivery_days_type should have a default value of 'working days' in Russian."""
        source = _read_post_handler_source()
        # The default should be set inline in the spec_data dict
        has_default = re.search(
            r'["\']delivery_days_type["\'].*["\'].*\u0440\u0430\u0431\u043e\u0447\u0438\u0445\s+\u0434\u043d\u0435\u0439["\']',
            source
        )
        assert has_default, (
            "delivery_days_type must have a default value of "
            "'рабочих дней' (working days) in the spec_data dict."
        )


# ==============================================================================
# 5. Migration 160 tests: ensures columns exist in kvota schema
# ==============================================================================

class TestMigration160:
    """
    Migration 160 fixes the schema issue from migration 036.
    036 checked information_schema.columns without table_schema='kvota',
    so contract_id may have been created in public.specifications instead of
    kvota.specifications.

    Migration 160 must:
    - Exist as a migration file
    - Target kvota schema specifically
    - Use IF NOT EXISTS or equivalent for idempotency
    - Ensure contract_id column exists in kvota.specifications
    """

    def test_migration_160_file_exists(self):
        """
        Migration 160 file must exist in the migrations directory.
        This is the fix migration that ensures columns are in kvota schema.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file must exist in migrations/ directory. "
            "This migration fixes the schema issue from migration 036 "
            "where contract_id was created in public instead of kvota."
        )

    def test_migration_160_targets_kvota_schema(self):
        """
        Migration 160 must explicitly reference kvota schema (not public).
        The original bug was that 036 didn't specify kvota schema.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check schema targeting."
        )

        migration_content = open(migration_files[0]).read()
        has_kvota_schema = (
            "kvota.specifications" in migration_content
            or "table_schema = 'kvota'" in migration_content
            or "table_schema='kvota'" in migration_content
        )
        assert has_kvota_schema, (
            "Migration 160 must explicitly target kvota schema. "
            "Expected: 'kvota.specifications' or table_schema = 'kvota'. "
            "The original bug in 036 was missing this schema qualifier."
        )

    def test_migration_160_is_idempotent(self):
        """
        Migration 160 must use IF NOT EXISTS or equivalent for idempotency.
        Running it multiple times should not fail.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check idempotency."
        )

        migration_content = open(migration_files[0]).read().lower()
        has_idempotent = (
            "if not exists" in migration_content
            or "do $$" in migration_content  # PL/pgSQL conditional block
        )
        assert has_idempotent, (
            "Migration 160 must be idempotent (safe to run multiple times). "
            "Expected: IF NOT EXISTS or DO $$ conditional block."
        )

    def test_migration_160_ensures_contract_id_column(self):
        """
        Migration 160 must ensure contract_id column exists in kvota.specifications.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check contract_id column."
        )

        migration_content = open(migration_files[0]).read()
        has_contract_id = "contract_id" in migration_content
        assert has_contract_id, (
            "Migration 160 must ensure contract_id column exists in kvota.specifications. "
            "This is the primary column that was lost due to the schema bug."
        )

    def test_migration_160_does_not_use_public_schema(self):
        """
        Migration 160 must NOT reference public schema for specifications table.
        The whole point of this fix is to avoid the public schema mistake.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check for public schema references."
        )

        migration_content = open(migration_files[0]).read()
        has_public_specs = "public.specifications" in migration_content
        assert not has_public_specs, (
            "Migration 160 must NOT reference public.specifications. "
            "The fix specifically targets kvota schema."
        )


# ==============================================================================
# 6. Migration 036 bug verification: confirms the root cause
# ==============================================================================

class TestMigration036Bug:
    """
    Verify that migration 036 has the bug (no kvota schema qualifier).
    This confirms the root cause and justifies migration 160.
    """

    def test_migration_036_exists(self):
        """Migration 036 should exist."""
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "036*"))
        assert len(migration_files) > 0, (
            "Migration 036 file should exist in migrations/ directory."
        )

    def test_migration_036_missing_kvota_schema_in_information_schema_check(self):
        """
        Migration 036 checks information_schema.columns for column existence,
        but does NOT filter by table_schema = 'kvota'. This means it checks
        the public schema by default, creating columns there instead of in kvota.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "036*"))
        assert len(migration_files) > 0, "Migration 036 not found"

        migration_content = open(migration_files[0]).read()

        # Confirm it uses information_schema.columns
        uses_info_schema = "information_schema.columns" in migration_content
        assert uses_info_schema, (
            "Migration 036 should use information_schema.columns check"
        )

        # Confirm it does NOT have table_schema = 'kvota'
        has_kvota_filter = (
            "table_schema = 'kvota'" in migration_content
            or "table_schema='kvota'" in migration_content
        )
        assert not has_kvota_filter, (
            "Migration 036 is missing table_schema = 'kvota' filter in "
            "information_schema.columns check. This is the root cause: "
            "columns were created in public schema instead of kvota."
        )

    def test_migration_036_uses_plain_table_name(self):
        """
        Migration 036 uses 'ALTER TABLE specifications' without kvota prefix.
        This means the ALTER TABLE targets the search_path default (likely public).
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "036*"))
        assert len(migration_files) > 0, "Migration 036 not found"

        migration_content = open(migration_files[0]).read()

        # Check for ALTER TABLE without kvota prefix
        has_plain_alter = "ALTER TABLE specifications" in migration_content
        has_kvota_alter = "ALTER TABLE kvota.specifications" in migration_content

        assert has_plain_alter and not has_kvota_alter, (
            "Migration 036 uses 'ALTER TABLE specifications' without kvota prefix. "
            "This confirms the table targeted is in the default schema (public), "
            "not kvota. Migration 160 must fix this."
        )


# ==============================================================================
# 7. End-to-end data flow: spec_data keys match expected DB columns
# ==============================================================================

class TestSpecDataColumnAlignment:
    """
    Verify that the spec_data dict keys in the POST handler align with
    the expected database columns in kvota.specifications.
    """

    def test_spec_data_has_all_critical_columns(self, post_handler_source):
        """
        The spec_data dict must include ALL critical columns that were
        affected by the migration 036 schema bug.
        """
        critical_columns = [
            "contract_id",
            "delivery_days",
            "delivery_days_type",
            "specification_number",
        ]

        spec_data_match = re.search(
            r'spec_data\s*=\s*\{(.*?)\}',
            post_handler_source,
            re.DOTALL
        )
        assert spec_data_match, "Could not find spec_data dict in POST handler"
        spec_data_block = spec_data_match.group(1)

        missing = [col for col in critical_columns if col not in spec_data_block]
        assert not missing, (
            f"spec_data dict is missing critical columns: {missing}. "
            "These columns are needed for the specification to save correctly."
        )

    def test_spec_data_has_standard_columns(self, post_handler_source):
        """
        The spec_data dict must include standard specification columns
        that were already working before the bug.
        """
        standard_columns = [
            "quote_id",
            "organization_id",
            "status",
            "created_by",
            "specification_currency",
        ]

        spec_data_match = re.search(
            r'spec_data\s*=\s*\{(.*?)\}',
            post_handler_source,
            re.DOTALL
        )
        assert spec_data_match, "Could not find spec_data dict in POST handler"
        spec_data_block = spec_data_match.group(1)

        missing = [col for col in standard_columns if col not in spec_data_block]
        assert not missing, (
            f"spec_data dict is missing standard columns: {missing}. "
            "These should always be present in the specification INSERT."
        )

    def test_contract_id_value_comes_from_variable(self, post_handler_source):
        """
        contract_id in spec_data must reference the contract_id variable
        (which was read from kwargs and processed for auto-numbering).
        Not a raw kwargs.get() -- it should use the processed variable.
        """
        # The handler sets contract_id = kwargs.get("contract_id") or None
        # Then uses it in auto-numbering
        # Then puts the same variable in spec_data
        has_variable_reference = re.search(
            r'"contract_id":\s*contract_id',
            post_handler_source
        )
        assert has_variable_reference, (
            "spec_data['contract_id'] must reference the processed contract_id variable, "
            "not a raw kwargs.get(). The variable is set earlier and used for auto-numbering."
        )

    def test_delivery_days_value_comes_from_variable(self, post_handler_source):
        """
        delivery_days in spec_data must reference the delivery_days variable
        (which includes the fallback from calc_variables.delivery_time).
        """
        has_variable_reference = re.search(
            r'"delivery_days":\s*delivery_days',
            post_handler_source
        )
        assert has_variable_reference, (
            "spec_data['delivery_days'] must reference the processed delivery_days variable "
            "(which includes fallback from calc_variables.delivery_time), "
            "not a raw kwargs.get()."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
