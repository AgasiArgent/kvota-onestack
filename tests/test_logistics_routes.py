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
# PART 1: Deal Detail Route with Logistics Tab
# ==============================================================================

class TestDealDetailRouteExists:
    """The /deals/{deal_id} route must exist and support a logistics tab."""

    def test_deals_detail_route_exists(self):
        """GET /deals/{deal_id} route must be defined in main.py."""
        source = _read_main_source()
        has_route = (
            '@rt("/deals/{deal_id}")' in source
            or "@rt('/deals/{deal_id}')" in source
            or '@rt("/deals/{deal_id}"' in source
        )
        assert has_route, (
            'GET /deals/{deal_id} route must be defined in main.py'
        )

    def test_deals_detail_accepts_tab_param(self):
        """GET /deals/{deal_id} must accept a tab parameter."""
        source = _read_main_source()
        # Find the deals detail handler
        match = re.search(
            r'@rt\(\s*["\']\/deals\/\{deal_id\}["\']\s*\)\s*\ndef get\((.*?)\):',
            source,
            re.DOTALL,
        )
        assert match, "GET /deals/{deal_id} handler signature not found"
        params = match.group(1)
        assert "tab" in params, (
            'GET /deals/{deal_id} must accept tab parameter (for logistics tab)'
        )

    def test_deals_detail_handles_logistics_tab(self):
        """GET /deals/{deal_id} must handle tab='logistics'."""
        source = _read_main_source()
        # Find the handler body
        match = re.search(
            r'@rt\(\s*["\']\/deals\/\{deal_id\}["\']\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /deals/{deal_id} handler body not found"
        handler_body = match.group(1)
        has_logistics_tab = (
            'tab == "logistics"' in handler_body
            or "tab == 'logistics'" in handler_body
            or 'tab=="logistics"' in handler_body
            or '"logistics"' in handler_body
        )
        assert has_logistics_tab, (
            'GET /deals/{deal_id} must handle tab="logistics"'
        )


class TestDealDetailTabNavigation:
    """The deal detail page must show tab navigation including logistics."""

    def test_deal_detail_shows_logistics_tab_label(self):
        """Tab bar must include a Logistics label (Russian: Логистика)."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*["\']\/deals\/\{deal_id\}["\']\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /deals/{deal_id} handler not found"
        handler_body = match.group(1)
        has_label = (
            "Логистика" in handler_body
            or "logistics" in handler_body.lower()
        )
        assert has_label, (
            'Deal detail tab bar must show "Логистика" or logistics tab label'
        )


# ==============================================================================
# PART 2: Logistics Tab Content Route
# ==============================================================================

class TestLogisticsTabContentRoute:
    """GET /deals/{deal_id}/tab/logistics must return stages accordion."""

    def test_logistics_tab_route_exists(self):
        """GET /deals/{deal_id}/tab/logistics route must be defined."""
        source = _read_main_source()
        has_route = (
            '/deals/{deal_id}/tab/logistics' in source
        )
        assert has_route, (
            'GET /deals/{deal_id}/tab/logistics route must be defined in main.py'
        )

    def test_logistics_tab_calls_get_stages_for_deal(self):
        """Logistics tab handler must call get_stages_for_deal."""
        source = _read_main_source()
        # Find the logistics tab handler and check for stage query
        has_stages_call = (
            'get_stages_for_deal' in source
        )
        assert has_stages_call, (
            "Logistics tab handler must call get_stages_for_deal()"
        )

    def test_logistics_tab_renders_stages_ui(self):
        """Logistics tab must render stages UI with stage codes."""
        source = _read_main_source()
        # Find the logistics tab handler specifically
        idx = source.find('/deals/{deal_id}/tab/logistics')
        assert idx != -1, "Logistics tab route not found in main.py"
        # Check nearby code (within 3000 chars) for stage rendering
        nearby = source[idx:idx+3000]
        has_stage_rendering = (
            'first_mile' in nearby
            or 'FIRST MILE' in nearby
            or 'stage_code' in nearby
            or 'logistics_stages_accordion' in nearby.lower()
        )
        assert has_stage_rendering, (
            "Logistics tab handler must render individual stages "
            "(should reference stage codes or accordion helper)"
        )


# ==============================================================================
# PART 3: Add Expense Route
# ==============================================================================

class TestAddExpenseRoute:
    """POST /deals/{deal_id}/stages/{stage_id}/expenses must create expense."""

    def test_add_expense_route_exists(self):
        """POST /deals/{deal_id}/stages/{stage_id}/expenses route must exist."""
        source = _read_main_source()
        has_route = (
            '/deals/{deal_id}/stages/{stage_id}/expenses' in source
        )
        assert has_route, (
            'POST /deals/{deal_id}/stages/{stage_id}/expenses route must be defined'
        )

    def test_add_expense_route_is_post(self):
        """The expense creation route must be a POST handler."""
        source = _read_main_source()
        # Search for route decorator followed by 'def post'
        match = re.search(
            r'@rt\(\s*["\'].*?stages/\{stage_id\}/expenses["\']\s*\)\s*\ndef post\(',
            source,
            re.DOTALL,
        )
        # Alternative: route might use methods parameter
        alternative_match = re.search(
            r'/stages/\{stage_id\}/expenses.*?\bpost\b',
            source,
            re.DOTALL | re.IGNORECASE,
        )
        assert match or alternative_match, (
            "Expense route must be a POST handler"
        )

    def test_add_expense_requires_description(self):
        """POST expense handler must accept description parameter."""
        source = _read_main_source()
        # Find the handler signature
        match = re.search(
            r'/stages/\{stage_id\}/expenses["\']\s*\)\s*\ndef \w+\((.*?)\):',
            source,
            re.DOTALL,
        )
        if match:
            params = match.group(1)
            assert "description" in params, (
                "Expense creation route must accept description parameter"
            )
        else:
            # If we can't find the exact signature, just check it's mentioned near the route
            idx = source.find('/stages/{stage_id}/expenses')
            assert idx != -1, "Expense route not found"
            nearby = source[idx:idx+500]
            assert "description" in nearby, (
                "Expense creation handler must use description field"
            )

    def test_add_expense_requires_amount(self):
        """POST expense handler must accept amount parameter."""
        source = _read_main_source()
        idx = source.find('/stages/{stage_id}/expenses')
        assert idx != -1, "Expense route not found"
        nearby = source[idx:idx+500]
        assert "amount" in nearby, (
            "Expense creation handler must accept amount parameter"
        )

    def test_add_expense_requires_currency(self):
        """POST expense handler must accept currency parameter."""
        source = _read_main_source()
        idx = source.find('/stages/{stage_id}/expenses')
        assert idx != -1, "Expense route not found"
        nearby = source[idx:idx+500]
        assert "currency" in nearby, (
            "Expense creation handler must accept currency parameter"
        )

    def test_add_expense_requires_expense_date(self):
        """POST expense handler must accept expense_date parameter."""
        source = _read_main_source()
        idx = source.find('/stages/{stage_id}/expenses')
        assert idx != -1, "Expense route not found"
        nearby = source[idx:idx+800]
        has_date = (
            "expense_date" in nearby
            or "planned_date" in nearby
            or "date" in nearby.lower()
        )
        assert has_date, (
            "Expense creation handler must accept date parameter"
        )


class TestAddExpenseToGtdUploadRejected:
    """POST expense to gtd_upload stage must be rejected."""

    def test_gtd_upload_expense_rejection_in_route(self):
        """Route handler must check stage_code and reject gtd_upload expenses."""
        source = _read_main_source()
        # Look for gtd_upload check near the expense route
        idx = source.find('/stages/{stage_id}/expenses')
        if idx == -1:
            pytest.fail("Expense route not found in main.py")

        # Search in a wider context around the route
        nearby = source[max(0, idx-200):idx+2000]
        has_gtd_check = (
            'gtd_upload' in nearby
            or 'stage_allows_expenses' in nearby
            or 'no_expense' in nearby
            or 'cannot add expense' in nearby.lower()
        )
        assert has_gtd_check, (
            "Expense route must check and reject expenses on gtd_upload stage"
        )


# ==============================================================================
# PART 4: Update Stage Status Route
# ==============================================================================

class TestUpdateStageStatusRoute:
    """PATCH /deals/{deal_id}/stages/{stage_id}/status must update status."""

    def test_stage_status_route_exists(self):
        """PATCH route for stage status must be defined."""
        source = _read_main_source()
        has_route = (
            '/stages/{stage_id}/status' in source
        )
        assert has_route, (
            'PATCH /deals/{deal_id}/stages/{stage_id}/status route must be defined'
        )

    def test_stage_status_route_is_patch_or_post(self):
        """Stage status update must be PATCH or POST handler."""
        source = _read_main_source()
        match = re.search(
            r'/stages/\{stage_id\}/status["\']\s*\)\s*\ndef (patch|post)\(',
            source,
            re.DOTALL,
        )
        alternative = re.search(
            r'/stages/\{stage_id\}/status.*?(patch|put|post)',
            source,
            re.DOTALL | re.IGNORECASE,
        )
        assert match or alternative, (
            "Stage status route must be a PATCH or POST handler"
        )

    def test_stage_status_route_accepts_status_param(self):
        """Stage status handler must accept status parameter."""
        source = _read_main_source()
        idx = source.find('/stages/{stage_id}/status')
        assert idx != -1, "Stage status route not found"
        nearby = source[idx:idx+500]
        assert "status" in nearby, (
            "Stage status handler must accept status parameter"
        )

    def test_stage_status_route_calls_update_stage_status(self):
        """Handler must call update_stage_status from logistics_service."""
        source = _read_main_source()
        idx = source.find('/stages/{stage_id}/status')
        assert idx != -1, "Stage status route not found"
        nearby = source[idx:idx+1000]
        assert "update_stage_status" in nearby, (
            "Stage status handler must call update_stage_status()"
        )


# ==============================================================================
# PART 5: Authentication and Authorization
# ==============================================================================

class TestLogisticsRoutesRequireAuth:
    """All logistics routes must require authentication."""

    def test_logistics_tab_route_checks_session(self):
        """GET /deals/{deal_id}/tab/logistics must check session."""
        source = _read_main_source()
        # Find the logistics tab handler
        match = re.search(
            r'/deals/\{deal_id\}/tab/logistics["\']\s*\)\s*\ndef \w+\((.*?)\):',
            source,
            re.DOTALL,
        )
        if match:
            params = match.group(1)
            assert "session" in params or "sess" in params, (
                "Logistics tab handler must accept session parameter"
            )
        else:
            # If route not found, test fails anyway
            pytest.fail("Logistics tab route not found in main.py")

    def test_expense_route_checks_session(self):
        """POST expense route must check session."""
        source = _read_main_source()
        match = re.search(
            r'/stages/\{stage_id\}/expenses["\']\s*\)\s*\ndef \w+\((.*?)\):',
            source,
            re.DOTALL,
        )
        if match:
            params = match.group(1)
            assert "session" in params or "sess" in params, (
                "Expense creation handler must accept session parameter"
            )
        else:
            # Check if session is used near the route
            idx = source.find('/stages/{stage_id}/expenses')
            assert idx != -1, "Expense route not found"
            nearby = source[idx:idx+500]
            assert "session" in nearby, (
                "Expense creation handler must use session"
            )


class TestLogisticsRoutesRequireRole:
    """Logistics routes must require finance/admin/logistician role."""

    def test_logistics_routes_check_user_role(self):
        """Route handlers must verify user has appropriate role."""
        source = _read_main_source()
        # Look for role checks near logistics-related routes
        logistics_section_start = source.find('/deals/{deal_id}/tab/logistics')
        if logistics_section_start == -1:
            pytest.fail("Logistics routes not found in main.py")

        # Check within a reasonable range of the logistics routes
        logistics_section = source[logistics_section_start:logistics_section_start + 5000]
        has_role_check = (
            'user_has_role' in logistics_section
            or 'user_has_any_role' in logistics_section
            or 'require_role' in logistics_section
            or 'require_any_role' in logistics_section
            or 'has_role' in logistics_section
            or 'has_any_role' in logistics_section
            or "'finance'" in logistics_section
            or "'admin'" in logistics_section
            or "'logistician'" in logistics_section
            or "'logistics'" in logistics_section
        )
        assert has_role_check, (
            "Logistics route handlers must check user role "
            "(finance/admin/logistician)"
        )


class TestLogisticsRoutesOrgIsolation:
    """Logistics routes must enforce organization isolation."""

    def test_logistics_tab_checks_organization(self):
        """Logistics tab must verify deal belongs to user's org."""
        source = _read_main_source()
        logistics_section_start = source.find('/deals/{deal_id}/tab/logistics')
        if logistics_section_start == -1:
            pytest.fail("Logistics routes not found in main.py")

        logistics_section = source[logistics_section_start:logistics_section_start + 3000]
        has_org_check = (
            'organization_id' in logistics_section
            or 'org_id' in logistics_section
        )
        assert has_org_check, (
            "Logistics tab must check deal's organization_id matches user's org"
        )


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

    def test_main_imports_add_expense_to_stage(self):
        """main.py must import add_expense_to_stage."""
        source = _read_main_source()
        has_import = 'add_expense_to_stage' in source
        assert has_import, (
            "main.py must import add_expense_to_stage from logistics_service"
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


# ==============================================================================
# PART 12: Expense Form UI Elements
# ==============================================================================

class TestExpenseFormUI:
    """The expense form must have required input fields."""

    def test_expense_form_has_description_input(self):
        """Expense form for logistics must include a description input field."""
        source = _read_main_source()
        # The expense form must be near the logistics expense route
        idx = source.find('/stages/{stage_id}/expenses')
        assert idx != -1, "Expense route not found in main.py"
        # Search within 5000 chars of the route for the form field
        nearby = source[max(0, idx-6000):idx+3000]
        has_desc_input = (
            'name="description"' in nearby or "name='description'" in nearby
        )
        assert has_desc_input, (
            "Logistics expense form must include a description input field "
            "(near /stages/{stage_id}/expenses route)"
        )

    def test_expense_form_has_amount_input(self):
        """Expense form for logistics must include an amount input field."""
        source = _read_main_source()
        idx = source.find('/stages/{stage_id}/expenses')
        assert idx != -1, "Expense route not found in main.py"
        nearby = source[max(0, idx-6000):idx+3000]
        has_amount_input = (
            'name="amount"' in nearby or "name='amount'" in nearby
            or 'name="planned_amount"' in nearby
        )
        assert has_amount_input, (
            "Logistics expense form must include an amount input field "
            "(near /stages/{stage_id}/expenses route)"
        )

    def test_expense_form_has_currency_select(self):
        """Expense form for logistics must include a currency selector."""
        source = _read_main_source()
        idx = source.find('/stages/{stage_id}/expenses')
        assert idx != -1, "Expense route not found in main.py"
        nearby = source[max(0, idx-6000):idx+3000]
        has_currency = (
            'name="currency"' in nearby or "name='currency'" in nearby
            or 'name="planned_currency"' in nearby
        )
        assert has_currency, (
            "Logistics expense form must include a currency selector "
            "(near /stages/{stage_id}/expenses route)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
