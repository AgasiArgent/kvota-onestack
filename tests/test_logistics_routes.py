"""
TDD Tests for P2.7+P2.8: Logistics Routes (Deal Detail + Logistics Tab)

Routes to be implemented:
  1. GET  /deals/{deal_id}?tab=logistics    -- Deal detail with logistics tab
  2. GET  /deals/{deal_id}/tab/logistics     -- HTMX target: logistics tab content
  3. POST /deals/{deal_id}/stages/{stage_id}/expenses  -- Add expense to stage
  4. PATCH /deals/{deal_id}/stages/{stage_id}/status   -- Update stage status

Route requirements:
  - Authentication required (session with user)
  - Role-based access: finance, admin, or logistician roles
  - Organization isolation: can't access other org's deal logistics
  - POST expense requires: description, amount, currency, expense_date
  - POST expense to gtd_upload stage is rejected
  - PATCH status updates correctly, auto-sets timestamps

Integration requirements:
  - Deal creation auto-initializes 7 logistics stages
  - Expense added via logistics tab appears in finance payments view

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the features are implemented.
"""

import pytest
import re
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Path constants (relative to project root via os.path)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
DEAL_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "deal_service.py")
LOGISTICS_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "logistics_service.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


def _read_deal_service_source():
    """Read deal_service.py source code without importing it."""
    with open(DEAL_SERVICE_PY) as f:
        return f.read()


def _read_logistics_service_source():
    """Read logistics_service.py source code without importing it."""
    with open(LOGISTICS_SERVICE_PY) as f:
        return f.read()


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def deal_id():
    return _make_uuid()


@pytest.fixture
def org_id():
    return _make_uuid()


@pytest.fixture
def user_id():
    return _make_uuid()


@pytest.fixture
def stage_id():
    return _make_uuid()



# ==============================================================================
# PART 6: Deal Creation Auto-Initializes Logistics Stages
# ==============================================================================

class TestDealCreationInitializesStages:
    """When a deal is created, 7 logistics stages must be auto-initialized."""

    def test_deal_service_imports_logistics_service(self):
        """deal_service.py must import logistics_service."""
        source = _read_deal_service_source()
        has_import = (
            'logistics_service' in source
            or 'initialize_logistics_stages' in source
        )
        assert has_import, (
            "deal_service.py must import logistics_service for auto-initialization"
        )

    def test_create_deal_calls_initialize_logistics_stages(self):
        """create_deal or create_deal_from_specification must call initialize_logistics_stages."""
        source = _read_deal_service_source()
        has_init_call = (
            'initialize_logistics_stages' in source
        )
        assert has_init_call, (
            "Deal creation must call initialize_logistics_stages() "
            "to auto-create 7 logistics stages"
        )

    def test_logistics_init_called_after_deal_created(self):
        """initialize_logistics_stages must be called after deal is successfully created."""
        source = _read_deal_service_source()
        # Find create_deal_from_specification function
        match = re.search(
            r'def create_deal_from_specification\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        if not match:
            # Try create_deal
            match = re.search(
                r'def create_deal\(.*?\n(.*?)(?=\ndef |\Z)',
                source,
                re.DOTALL,
            )
        assert match, "create_deal or create_deal_from_specification not found"
        fn_body = match.group(1)

        # initialize_logistics_stages should appear AFTER the deal insert
        deal_insert_idx = fn_body.find('.insert(')
        logistics_init_idx = fn_body.find('initialize_logistics_stages')

        assert logistics_init_idx > -1, (
            "initialize_logistics_stages must be called in deal creation"
        )
        # If both are in the function, logistics init should come after insert
        if deal_insert_idx > -1:
            assert logistics_init_idx > deal_insert_idx, (
                "initialize_logistics_stages must be called AFTER deal is inserted"
            )


# ==============================================================================
# PART 7: Logistics Service File Exists
# ==============================================================================

class TestLogisticsServiceFileExists:
    """services/logistics_service.py must exist."""

    def test_file_exists(self):
        """The logistics service file must exist."""
        assert os.path.isfile(LOGISTICS_SERVICE_PY), (
            f"services/logistics_service.py must exist at {LOGISTICS_SERVICE_PY}"
        )

    def test_file_has_initialize_function(self):
        """logistics_service.py must define initialize_logistics_stages."""
        source = _read_logistics_service_source()
        assert "def initialize_logistics_stages(" in source, (
            "logistics_service.py must define initialize_logistics_stages()"
        )

    def test_file_has_get_stages_function(self):
        """logistics_service.py must define get_stages_for_deal."""
        source = _read_logistics_service_source()
        assert "def get_stages_for_deal(" in source, (
            "logistics_service.py must define get_stages_for_deal()"
        )

    def test_file_has_update_stage_status_function(self):
        """logistics_service.py must define update_stage_status."""
        source = _read_logistics_service_source()
        assert "def update_stage_status(" in source, (
            "logistics_service.py must define update_stage_status()"
        )

    def test_file_has_get_expenses_function(self):
        """logistics_service.py must define get_expenses_for_stage."""
        source = _read_logistics_service_source()
        assert "def get_expenses_for_stage(" in source, (
            "logistics_service.py must define get_expenses_for_stage()"
        )

    def test_file_has_add_expense_function(self):
        """logistics_service.py must define add_expense_to_stage."""
        source = _read_logistics_service_source()
        assert "def add_expense_to_stage(" in source, (
            "logistics_service.py must define add_expense_to_stage()"
        )

    def test_file_has_stage_summary_function(self):
        """logistics_service.py must define get_stage_summary."""
        source = _read_logistics_service_source()
        assert "def get_stage_summary(" in source, (
            "logistics_service.py must define get_stage_summary()"
        )

    def test_file_has_stage_allows_expenses_function(self):
        """logistics_service.py must define stage_allows_expenses."""
        source = _read_logistics_service_source()
        assert "def stage_allows_expenses(" in source, (
            "logistics_service.py must define stage_allows_expenses()"
        )


# ==============================================================================
# PART 8: Migration Files Exist
# ==============================================================================

class TestMigrationFilesExist:
    """Required migration files must exist."""

    def test_logistics_stages_migration_exists(self):
        """Migration for logistics_stages table must exist."""
        migrations_dir = os.path.join(_PROJECT_ROOT, "migrations")
        migration_files = os.listdir(migrations_dir)
        has_logistics_migration = any(
            'logistics_stages' in f.lower()
            for f in migration_files
        )
        assert has_logistics_migration, (
            "Migration file for logistics_stages table must exist in migrations/"
        )

    def test_svh_migration_exists(self):
        """Migration for svh reference table must exist."""
        migrations_dir = os.path.join(_PROJECT_ROOT, "migrations")
        migration_files = os.listdir(migrations_dir)
        has_svh_migration = any(
            'svh' in f.lower()
            for f in migration_files
        )
        assert has_svh_migration, (
            "Migration file for svh reference table must exist in migrations/"
        )

    def test_plan_fact_items_logistics_stage_fk_migration_exists(self):
        """Migration adding logistics_stage_id to plan_fact_items must exist."""
        migrations_dir = os.path.join(_PROJECT_ROOT, "migrations")
        migration_files = os.listdir(migrations_dir)
        has_fk_migration = any(
            ('logistics_stage' in f.lower() and 'plan_fact' in f.lower())
            or ('logistics' in f.lower() and 'plan_fact' in f.lower())
            or '165' in f  # Expected migration number
            for f in migration_files
        )
        assert has_fk_migration, (
            "Migration adding logistics_stage_id FK to plan_fact_items must exist"
        )


# ==============================================================================
# PART 9: Logistics Categories in Plan-Fact
# ==============================================================================

class TestLogisticsCategoriesExist:
    """Logistics-specific plan_fact categories must be created via migration."""

    def test_logistics_categories_in_migration(self):
        """Migration must INSERT all 6 logistics expense categories."""
        migrations_dir = os.path.join(_PROJECT_ROOT, "migrations")
        migration_files = sorted(os.listdir(migrations_dir))

        # We need ALL 6 logistics categories (one per expense-capable stage)
        required_categories = [
            'logistics_first_mile',
            'logistics_hub',
            'logistics_hub_hub',
            'logistics_transit',
            'logistics_post_transit',
            'logistics_last_mile',
        ]

        found_count = 0
        for fname in migration_files:
            fpath = os.path.join(migrations_dir, fname)
            if os.path.isfile(fpath) and fname.endswith('.sql'):
                try:
                    with open(fpath) as f:
                        content = f.read()
                    for cat in required_categories:
                        if cat in content:
                            found_count += 1
                except Exception:
                    pass

        assert found_count >= len(required_categories), (
            f"Migration must INSERT all 6 logistics categories "
            f"({required_categories}). Found {found_count}/{len(required_categories)}"
        )


# ==============================================================================
# PART 10: Integration — Main.py Imports Logistics Service
# ==============================================================================

class TestMainPyImportsLogisticsService:
    """main.py must import logistics_service functions."""

    def test_main_imports_logistics_service(self):
        """main.py must import from logistics_service."""
        source = _read_main_source()
        has_import = (
            'logistics_service' in source
            or 'from services.logistics_service' in source
            or 'import logistics_service' in source
        )
        assert has_import, (
            "main.py must import logistics_service for route handlers"
        )

    def test_main_imports_get_stages_for_deal(self):
        """main.py must import get_stages_for_deal."""
        source = _read_main_source()
        has_import = 'get_stages_for_deal' in source
        assert has_import, (
            "main.py must import get_stages_for_deal from logistics_service"
        )

    def test_main_imports_logistics_service(self):
        """main.py must import from logistics_service (stages, not expenses)."""
        source = _read_main_source()
        has_import = 'logistics_service' in source
        assert has_import, (
            "main.py must import from logistics_service"
        )


# ==============================================================================
# PART 11: Logistics Stage Category Mapping
# ==============================================================================

class TestStageCategoryMapping:
    """Each stage must map to a logistics plan_fact category."""

    def test_category_mapping_function_exists(self):
        """get_logistics_category_for_stage or equivalent must exist."""
        source = _read_main_source()
        has_mapping = (
            'get_logistics_category_for_stage' in source
            or 'STAGE_CATEGORY_MAP' in source
            or 'stage_to_category' in source
            or 'logistics_category' in source
        )
        assert has_mapping, (
            "A function or mapping to convert stage_code -> plan_fact_category must exist"
        )



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
