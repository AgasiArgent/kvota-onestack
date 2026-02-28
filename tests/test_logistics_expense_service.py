"""
Tests for Logistics Expense Service - CRUD for deal_logistics_expenses table.

Feature: [86aftzex6] Трекинг фактических расходов на логистику по сделкам

Tests cover:
- Module imports and constants (EXPENSE_SUBTYPE_LABELS, SUPPORTED_CURRENCIES)
- LogisticsExpense dataclass creation
- _parse_expense() with full data, missing FK joins, None values
- get_expenses_for_deal() — mock Supabase, verify query chain
- get_expenses_for_stage() — mock Supabase
- get_expense() — single record fetch
- create_expense() — verify insert data, return value
- delete_expense() — verify delete chain
- sync_plan_fact_for_stage() — verify plan-fact upsert logic
- get_deal_logistics_summary() — verify per-stage totals and grand total
- Edge cases: empty results, None returns, FK null safety pattern

TDD: These tests are written BEFORE implementation.
The logistics_expense_service.py module does not exist yet -- tests should fail with ImportError.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    """Organization ID for tests."""
    return str(uuid4())


@pytest.fixture
def deal_id():
    """Deal ID for tests."""
    return str(uuid4())


@pytest.fixture
def stage_id():
    """Logistics stage ID for tests."""
    return str(uuid4())


@pytest.fixture
def expense_id():
    """Expense record ID for tests."""
    return str(uuid4())


@pytest.fixture
def user_id():
    """User (financier) ID for tests."""
    return str(uuid4())


@pytest.fixture
def document_id():
    """Document attachment ID for tests."""
    return str(uuid4())


@pytest.fixture
def category_id():
    """Plan-fact category ID for tests."""
    return str(uuid4())


@pytest.fixture
def sample_expense_data(expense_id, deal_id, stage_id, org_id, user_id):
    """Sample expense database row with FK join to logistics_stages."""
    return {
        "id": expense_id,
        "deal_id": deal_id,
        "logistics_stage_id": stage_id,
        "expense_subtype": "transport",
        "amount": "1500.00",
        "currency": "USD",
        "expense_date": "2026-02-25",
        "description": "Truck from factory to port",
        "document_id": None,
        "created_by": user_id,
        "created_at": "2026-02-25T14:30:00Z",
        "organization_id": org_id,
        # FK join data (PostgREST explicit FK hint)
        "logistics_stages": {"stage_code": "first_mile"},
    }


@pytest.fixture
def sample_expense_data_with_doc(expense_id, deal_id, stage_id, org_id, user_id, document_id):
    """Sample expense with a document attachment."""
    return {
        "id": expense_id,
        "deal_id": deal_id,
        "logistics_stage_id": stage_id,
        "expense_subtype": "storage",
        "amount": "800.50",
        "currency": "EUR",
        "expense_date": "2026-02-20",
        "description": "Warehouse storage 5 days",
        "document_id": document_id,
        "created_by": user_id,
        "created_at": "2026-02-20T09:15:00Z",
        "organization_id": org_id,
        "logistics_stages": {"stage_code": "hub"},
    }


@pytest.fixture
def sample_expense_data_null_fks(expense_id, deal_id, stage_id, org_id):
    """Sample expense with null FK join (PostgREST null join pattern)."""
    return {
        "id": expense_id,
        "deal_id": deal_id,
        "logistics_stage_id": stage_id,
        "expense_subtype": "other",
        "amount": "250.00",
        "currency": "RUB",
        "expense_date": "2026-02-18",
        "description": None,
        "document_id": None,
        "created_by": None,
        "created_at": "2026-02-18T10:00:00Z",
        "organization_id": org_id,
        # PostgREST returns null when FK join has no match
        "logistics_stages": None,
    }


@pytest.fixture
def sample_expense_data_minimal(deal_id, stage_id, org_id):
    """Minimal expense data with only required fields."""
    return {
        "id": str(uuid4()),
        "deal_id": deal_id,
        "logistics_stage_id": stage_id,
        "expense_subtype": "transport",
        "amount": "100.00",
        "currency": "USD",
        "expense_date": "2026-02-28",
        "description": None,
        "document_id": None,
        "created_by": None,
        "created_at": None,
        "organization_id": org_id,
        "logistics_stages": {"stage_code": "last_mile"},
    }


@pytest.fixture
def sample_multiple_expenses(deal_id, org_id, user_id):
    """Multiple expenses across different stages for summary tests."""
    stage_first_mile = str(uuid4())
    stage_hub = str(uuid4())
    stage_transit = str(uuid4())

    return [
        {
            "id": str(uuid4()),
            "deal_id": deal_id,
            "logistics_stage_id": stage_first_mile,
            "expense_subtype": "transport",
            "amount": "1000.00",
            "currency": "USD",
            "expense_date": "2026-02-20",
            "description": "Truck delivery",
            "document_id": None,
            "created_by": user_id,
            "created_at": "2026-02-20T10:00:00Z",
            "organization_id": org_id,
            "logistics_stages": {"stage_code": "first_mile"},
        },
        {
            "id": str(uuid4()),
            "deal_id": deal_id,
            "logistics_stage_id": stage_first_mile,
            "expense_subtype": "handling",
            "amount": "200.00",
            "currency": "USD",
            "expense_date": "2026-02-21",
            "description": "Loading",
            "document_id": None,
            "created_by": user_id,
            "created_at": "2026-02-21T10:00:00Z",
            "organization_id": org_id,
            "logistics_stages": {"stage_code": "first_mile"},
        },
        {
            "id": str(uuid4()),
            "deal_id": deal_id,
            "logistics_stage_id": stage_hub,
            "expense_subtype": "storage",
            "amount": "500.00",
            "currency": "EUR",
            "expense_date": "2026-02-22",
            "description": "Hub storage",
            "document_id": None,
            "created_by": user_id,
            "created_at": "2026-02-22T10:00:00Z",
            "organization_id": org_id,
            "logistics_stages": {"stage_code": "hub"},
        },
        {
            "id": str(uuid4()),
            "deal_id": deal_id,
            "logistics_stage_id": stage_transit,
            "expense_subtype": "insurance",
            "amount": "300.00",
            "currency": "USD",
            "expense_date": "2026-02-23",
            "description": "Cargo insurance",
            "document_id": None,
            "created_by": user_id,
            "created_at": "2026-02-23T10:00:00Z",
            "organization_id": org_id,
            "logistics_stages": {"stage_code": "transit"},
        },
    ], {
        "first_mile": stage_first_mile,
        "hub": stage_hub,
        "transit": stage_transit,
    }


# =============================================================================
# IMPORT TESTS - verify module structure
# =============================================================================

class TestModuleImports:
    """Test that logistics_expense_service module exists and exports expected symbols."""

    def test_import_module(self):
        """logistics_expense_service module can be imported."""
        from services import logistics_expense_service
        assert logistics_expense_service is not None

    def test_import_logistics_expense_dataclass(self):
        """LogisticsExpense dataclass is importable."""
        from services.logistics_expense_service import LogisticsExpense
        assert LogisticsExpense is not None

    def test_import_expense_subtype_labels(self):
        """EXPENSE_SUBTYPE_LABELS constant is importable and is a dict."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert isinstance(EXPENSE_SUBTYPE_LABELS, dict)

    def test_import_supported_currencies(self):
        """SUPPORTED_CURRENCIES constant is importable and is a list."""
        from services.logistics_expense_service import SUPPORTED_CURRENCIES
        assert isinstance(SUPPORTED_CURRENCIES, list)

    def test_import_stage_to_plan_fact_category(self):
        """STAGE_TO_PLAN_FACT_CATEGORY constant is importable."""
        from services.logistics_expense_service import STAGE_TO_PLAN_FACT_CATEGORY
        assert isinstance(STAGE_TO_PLAN_FACT_CATEGORY, dict)

    def test_import_crud_functions(self):
        """All CRUD and query functions are importable."""
        from services.logistics_expense_service import (
            get_expenses_for_deal,
            get_expenses_for_stage,
            get_expense,
            create_expense,
            delete_expense,
            sync_plan_fact_for_stage,
            get_deal_logistics_summary,
            _parse_expense,
        )
        assert all([
            get_expenses_for_deal, get_expenses_for_stage, get_expense,
            create_expense, delete_expense, sync_plan_fact_for_stage,
            get_deal_logistics_summary, _parse_expense,
        ])


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

class TestConstants:
    """Test label constants for expense subtypes and currencies."""

    def test_expense_subtype_labels_has_transport(self):
        """EXPENSE_SUBTYPE_LABELS contains 'transport' key."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert "transport" in EXPENSE_SUBTYPE_LABELS

    def test_expense_subtype_labels_has_storage(self):
        """EXPENSE_SUBTYPE_LABELS contains 'storage' key."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert "storage" in EXPENSE_SUBTYPE_LABELS

    def test_expense_subtype_labels_has_handling(self):
        """EXPENSE_SUBTYPE_LABELS contains 'handling' key."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert "handling" in EXPENSE_SUBTYPE_LABELS

    def test_expense_subtype_labels_has_customs_fee(self):
        """EXPENSE_SUBTYPE_LABELS contains 'customs_fee' key."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert "customs_fee" in EXPENSE_SUBTYPE_LABELS

    def test_expense_subtype_labels_has_insurance(self):
        """EXPENSE_SUBTYPE_LABELS contains 'insurance' key."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert "insurance" in EXPENSE_SUBTYPE_LABELS

    def test_expense_subtype_labels_has_other(self):
        """EXPENSE_SUBTYPE_LABELS contains 'other' key."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert "other" in EXPENSE_SUBTYPE_LABELS

    def test_expense_subtype_labels_count(self):
        """EXPENSE_SUBTYPE_LABELS has exactly 6 entries."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert len(EXPENSE_SUBTYPE_LABELS) == 6

    def test_expense_subtype_labels_russian_values(self):
        """EXPENSE_SUBTYPE_LABELS values are Russian labels."""
        from services.logistics_expense_service import EXPENSE_SUBTYPE_LABELS
        assert EXPENSE_SUBTYPE_LABELS["transport"] == "Перевозка"
        assert EXPENSE_SUBTYPE_LABELS["storage"] == "Хранение"
        assert EXPENSE_SUBTYPE_LABELS["handling"] == "Погрузка/разгрузка"
        assert EXPENSE_SUBTYPE_LABELS["customs_fee"] == "Таможенные сборы"
        assert EXPENSE_SUBTYPE_LABELS["insurance"] == "Страхование"
        assert EXPENSE_SUBTYPE_LABELS["other"] == "Прочее"

    def test_supported_currencies_contains_usd(self):
        """SUPPORTED_CURRENCIES contains USD."""
        from services.logistics_expense_service import SUPPORTED_CURRENCIES
        assert "USD" in SUPPORTED_CURRENCIES

    def test_supported_currencies_contains_eur(self):
        """SUPPORTED_CURRENCIES contains EUR."""
        from services.logistics_expense_service import SUPPORTED_CURRENCIES
        assert "EUR" in SUPPORTED_CURRENCIES

    def test_supported_currencies_contains_rub(self):
        """SUPPORTED_CURRENCIES contains RUB."""
        from services.logistics_expense_service import SUPPORTED_CURRENCIES
        assert "RUB" in SUPPORTED_CURRENCIES

    def test_supported_currencies_contains_cny(self):
        """SUPPORTED_CURRENCIES contains CNY."""
        from services.logistics_expense_service import SUPPORTED_CURRENCIES
        assert "CNY" in SUPPORTED_CURRENCIES

    def test_supported_currencies_contains_try(self):
        """SUPPORTED_CURRENCIES contains TRY."""
        from services.logistics_expense_service import SUPPORTED_CURRENCIES
        assert "TRY" in SUPPORTED_CURRENCIES

    def test_supported_currencies_count(self):
        """SUPPORTED_CURRENCIES has exactly 5 entries."""
        from services.logistics_expense_service import SUPPORTED_CURRENCIES
        assert len(SUPPORTED_CURRENCIES) == 5

    def test_stage_to_plan_fact_category_mapping(self):
        """STAGE_TO_PLAN_FACT_CATEGORY maps 6 stages (no gtd_upload)."""
        from services.logistics_expense_service import STAGE_TO_PLAN_FACT_CATEGORY
        assert "first_mile" in STAGE_TO_PLAN_FACT_CATEGORY
        assert "hub" in STAGE_TO_PLAN_FACT_CATEGORY
        assert "hub_hub" in STAGE_TO_PLAN_FACT_CATEGORY
        assert "transit" in STAGE_TO_PLAN_FACT_CATEGORY
        assert "post_transit" in STAGE_TO_PLAN_FACT_CATEGORY
        assert "last_mile" in STAGE_TO_PLAN_FACT_CATEGORY
        assert "gtd_upload" not in STAGE_TO_PLAN_FACT_CATEGORY
        assert len(STAGE_TO_PLAN_FACT_CATEGORY) == 6

    def test_stage_to_plan_fact_category_values(self):
        """STAGE_TO_PLAN_FACT_CATEGORY maps to correct category codes."""
        from services.logistics_expense_service import STAGE_TO_PLAN_FACT_CATEGORY
        assert STAGE_TO_PLAN_FACT_CATEGORY["first_mile"] == "logistics_first_mile"
        assert STAGE_TO_PLAN_FACT_CATEGORY["hub"] == "logistics_hub"
        assert STAGE_TO_PLAN_FACT_CATEGORY["hub_hub"] == "logistics_hub_hub"
        assert STAGE_TO_PLAN_FACT_CATEGORY["transit"] == "logistics_transit"
        assert STAGE_TO_PLAN_FACT_CATEGORY["post_transit"] == "logistics_post_transit"
        assert STAGE_TO_PLAN_FACT_CATEGORY["last_mile"] == "logistics_last_mile"


# =============================================================================
# DATACLASS TESTS
# =============================================================================

class TestLogisticsExpenseDataclass:
    """Test LogisticsExpense dataclass fields and defaults."""

    def test_create_with_all_fields(self):
        """LogisticsExpense can be created with all fields."""
        from services.logistics_expense_service import LogisticsExpense
        now = datetime.now()
        today = date.today()
        expense = LogisticsExpense(
            id="test-id",
            deal_id="deal-1",
            logistics_stage_id="stage-1",
            stage_code="first_mile",
            expense_subtype="transport",
            amount=Decimal("1500.00"),
            currency="USD",
            expense_date=today,
            description="Test expense",
            document_id="doc-1",
            created_by="user-1",
            created_at=now,
            organization_id="org-1",
        )
        assert expense.id == "test-id"
        assert expense.deal_id == "deal-1"
        assert expense.logistics_stage_id == "stage-1"
        assert expense.stage_code == "first_mile"
        assert expense.expense_subtype == "transport"
        assert expense.amount == Decimal("1500.00")
        assert expense.currency == "USD"
        assert expense.expense_date == today
        assert expense.description == "Test expense"
        assert expense.document_id == "doc-1"
        assert expense.created_by == "user-1"
        assert expense.created_at == now
        assert expense.organization_id == "org-1"

    def test_amount_is_decimal(self):
        """LogisticsExpense.amount is a Decimal."""
        from services.logistics_expense_service import LogisticsExpense
        expense = LogisticsExpense(
            id="test-id",
            deal_id="deal-1",
            logistics_stage_id="stage-1",
            stage_code="hub",
            expense_subtype="storage",
            amount=Decimal("999.99"),
            currency="EUR",
            expense_date=date.today(),
            description=None,
            document_id=None,
            created_by=None,
            created_at=datetime.now(),
            organization_id="org-1",
        )
        assert isinstance(expense.amount, Decimal)
        assert expense.amount == Decimal("999.99")

    def test_optional_fields_accept_none(self):
        """LogisticsExpense optional fields accept None."""
        from services.logistics_expense_service import LogisticsExpense
        expense = LogisticsExpense(
            id="test-id",
            deal_id="deal-1",
            logistics_stage_id="stage-1",
            stage_code="transit",
            expense_subtype="other",
            amount=Decimal("50.00"),
            currency="RUB",
            expense_date=date.today(),
            description=None,
            document_id=None,
            created_by=None,
            created_at=datetime.now(),
            organization_id="org-1",
        )
        assert expense.description is None
        assert expense.document_id is None
        assert expense.created_by is None

    def test_expense_date_is_date_type(self):
        """LogisticsExpense.expense_date is a date object."""
        from services.logistics_expense_service import LogisticsExpense
        today = date.today()
        expense = LogisticsExpense(
            id="test-id",
            deal_id="deal-1",
            logistics_stage_id="stage-1",
            stage_code="last_mile",
            expense_subtype="transport",
            amount=Decimal("100.00"),
            currency="USD",
            expense_date=today,
            description=None,
            document_id=None,
            created_by=None,
            created_at=datetime.now(),
            organization_id="org-1",
        )
        assert isinstance(expense.expense_date, date)
        assert expense.expense_date == today


# =============================================================================
# PARSE EXPENSE TESTS
# =============================================================================

class TestParseExpense:
    """Test _parse_expense() function for converting DB rows to LogisticsExpense."""

    def test_parse_expense_basic(self, sample_expense_data):
        """Parse a complete expense record from database row."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data)

        assert expense.id == sample_expense_data["id"]
        assert expense.deal_id == sample_expense_data["deal_id"]
        assert expense.logistics_stage_id == sample_expense_data["logistics_stage_id"]
        assert expense.expense_subtype == "transport"
        assert expense.amount == Decimal("1500.00")
        assert expense.currency == "USD"
        assert expense.description == "Truck from factory to port"
        assert expense.organization_id == sample_expense_data["organization_id"]

    def test_parse_expense_extracts_stage_code_from_fk(self, sample_expense_data):
        """Parse extracts stage_code from FK join with logistics_stages."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data)

        assert expense.stage_code == "first_mile"

    def test_parse_expense_date_is_date_object(self, sample_expense_data):
        """Parse converts expense_date string to date object."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data)

        assert isinstance(expense.expense_date, date)
        assert expense.expense_date == date(2026, 2, 25)

    def test_parse_expense_created_at_is_datetime(self, sample_expense_data):
        """Parse converts created_at string to datetime object."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data)

        assert isinstance(expense.created_at, datetime)

    def test_parse_expense_amount_is_decimal(self, sample_expense_data):
        """Parse converts amount string to Decimal."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data)

        assert isinstance(expense.amount, Decimal)
        assert expense.amount == Decimal("1500.00")

    def test_parse_expense_with_document(self, sample_expense_data_with_doc, document_id):
        """Parse expense with attached document."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data_with_doc)

        assert expense.document_id == document_id
        assert expense.expense_subtype == "storage"
        assert expense.currency == "EUR"
        assert expense.amount == Decimal("800.50")

    def test_parse_expense_null_fk_safety_logistics_stages(self, sample_expense_data_null_fks):
        """Parse handles null logistics_stages FK without crash.

        BUG PATTERN: data.get("logistics_stages", {}).get("stage_code") crashes when value is None.
        SAFE PATTERN: (data.get("logistics_stages") or {}).get("stage_code", "")
        """
        from services.logistics_expense_service import _parse_expense
        # Should NOT raise AttributeError
        expense = _parse_expense(sample_expense_data_null_fks)

        # stage_code should be empty string or default, not crash
        assert expense.stage_code == "" or expense.stage_code is not None

    def test_parse_expense_null_description(self, sample_expense_data_null_fks):
        """Parse handles None description without crash."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data_null_fks)

        assert expense.description is None

    def test_parse_expense_null_created_by(self, sample_expense_data_null_fks):
        """Parse handles None created_by without crash."""
        from services.logistics_expense_service import _parse_expense
        expense = _parse_expense(sample_expense_data_null_fks)

        assert expense.created_by is None

    def test_parse_expense_null_created_at(self, sample_expense_data_minimal):
        """Parse handles None created_at by using current time."""
        from services.logistics_expense_service import _parse_expense
        before = datetime.now()
        expense = _parse_expense(sample_expense_data_minimal)
        after = datetime.now()

        assert expense.created_at is not None
        # created_at should be roughly now if None was in the data
        assert isinstance(expense.created_at, datetime)

    def test_parse_expense_default_subtype(self):
        """Parse uses 'transport' as default expense_subtype if missing."""
        from services.logistics_expense_service import _parse_expense
        data = {
            "id": str(uuid4()),
            "deal_id": str(uuid4()),
            "logistics_stage_id": str(uuid4()),
            # No expense_subtype key
            "amount": "100.00",
            "currency": "USD",
            "expense_date": "2026-02-28",
            "description": None,
            "document_id": None,
            "created_by": None,
            "created_at": "2026-02-28T10:00:00Z",
            "organization_id": str(uuid4()),
            "logistics_stages": {"stage_code": "hub"},
        }
        expense = _parse_expense(data)
        assert expense.expense_subtype == "transport"

    def test_parse_expense_default_currency(self):
        """Parse uses 'USD' as default currency if missing."""
        from services.logistics_expense_service import _parse_expense
        data = {
            "id": str(uuid4()),
            "deal_id": str(uuid4()),
            "logistics_stage_id": str(uuid4()),
            "expense_subtype": "transport",
            "amount": "100.00",
            # No currency key
            "expense_date": "2026-02-28",
            "description": None,
            "document_id": None,
            "created_by": None,
            "created_at": "2026-02-28T10:00:00Z",
            "organization_id": str(uuid4()),
            "logistics_stages": {"stage_code": "hub"},
        }
        expense = _parse_expense(data)
        assert expense.currency == "USD"


# =============================================================================
# GET EXPENSES FOR DEAL TESTS
# =============================================================================

class TestGetExpensesForDeal:
    """Test get_expenses_for_deal() function."""

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_returns_list(
        self, mock_get_supabase, sample_expense_data, deal_id
    ):
        """Get expenses for deal returns list of LogisticsExpense objects."""
        from services.logistics_expense_service import get_expenses_for_deal

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[sample_expense_data]
        )

        results = get_expenses_for_deal(deal_id)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].deal_id == deal_id

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_queries_correct_table(
        self, mock_get_supabase, deal_id
    ):
        """Get expenses queries deal_logistics_expenses table."""
        from services.logistics_expense_service import get_expenses_for_deal

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        get_expenses_for_deal(deal_id)

        mock_client.table.assert_called_with("deal_logistics_expenses")

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_includes_stage_join(
        self, mock_get_supabase, deal_id
    ):
        """Get expenses includes FK join with logistics_stages for stage_code."""
        from services.logistics_expense_service import get_expenses_for_deal

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        get_expenses_for_deal(deal_id)

        # Verify select includes the FK join
        select_call = mock_client.table.return_value.select.call_args
        select_str = select_call[0][0]
        assert "logistics_stages" in select_str

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_filters_by_deal_id(
        self, mock_get_supabase, deal_id
    ):
        """Get expenses filters by deal_id."""
        from services.logistics_expense_service import get_expenses_for_deal

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        get_expenses_for_deal(deal_id)

        mock_client.table.return_value.select.return_value.eq.assert_called_with("deal_id", deal_id)

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_empty_result(self, mock_get_supabase, deal_id):
        """Get expenses for deal with no expenses returns empty list."""
        from services.logistics_expense_service import get_expenses_for_deal

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        results = get_expenses_for_deal(deal_id)

        assert results == []

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_db_error_returns_empty(self, mock_get_supabase, deal_id):
        """Get expenses returns empty list on database error."""
        from services.logistics_expense_service import get_expenses_for_deal

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.side_effect = Exception("DB error")

        results = get_expenses_for_deal(deal_id)

        assert results == []

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_none_data_returns_empty(self, mock_get_supabase, deal_id):
        """Get expenses returns empty list when response.data is None."""
        from services.logistics_expense_service import get_expenses_for_deal

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=None
        )

        results = get_expenses_for_deal(deal_id)

        assert results == []

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_deal_multiple_results(
        self, mock_get_supabase, sample_multiple_expenses, deal_id
    ):
        """Get expenses returns all expense records for a deal."""
        from services.logistics_expense_service import get_expenses_for_deal

        expenses_data, _ = sample_multiple_expenses
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=expenses_data
        )

        results = get_expenses_for_deal(deal_id)

        assert len(results) == 4


# =============================================================================
# GET EXPENSES FOR STAGE TESTS
# =============================================================================

class TestGetExpensesForStage:
    """Test get_expenses_for_stage() function."""

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_stage_returns_list(
        self, mock_get_supabase, sample_expense_data, stage_id
    ):
        """Get expenses for stage returns list of LogisticsExpense objects."""
        from services.logistics_expense_service import get_expenses_for_stage

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[sample_expense_data]
        )

        results = get_expenses_for_stage(stage_id)

        assert isinstance(results, list)
        assert len(results) == 1

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_stage_filters_by_stage_id(
        self, mock_get_supabase, stage_id
    ):
        """Get expenses filters by logistics_stage_id."""
        from services.logistics_expense_service import get_expenses_for_stage

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        get_expenses_for_stage(stage_id)

        mock_client.table.return_value.select.return_value.eq.assert_called_with("logistics_stage_id", stage_id)

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_stage_empty(self, mock_get_supabase, stage_id):
        """Get expenses for stage with no expenses returns empty list."""
        from services.logistics_expense_service import get_expenses_for_stage

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        results = get_expenses_for_stage(stage_id)

        assert results == []

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expenses_for_stage_db_error_returns_empty(self, mock_get_supabase, stage_id):
        """Get expenses returns empty list on database error."""
        from services.logistics_expense_service import get_expenses_for_stage

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.side_effect = Exception("DB error")

        results = get_expenses_for_stage(stage_id)

        assert results == []


# =============================================================================
# GET SINGLE EXPENSE TESTS
# =============================================================================

class TestGetExpense:
    """Test get_expense() function."""

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expense_found(self, mock_get_supabase, sample_expense_data, expense_id):
        """Get existing expense by ID."""
        from services.logistics_expense_service import get_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_expense_data]
        )

        result = get_expense(expense_id)

        assert result is not None
        assert result.id == expense_id

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expense_not_found(self, mock_get_supabase):
        """Get non-existing expense returns None."""
        from services.logistics_expense_service import get_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_expense("nonexistent-id")

        assert result is None

    @patch('services.logistics_expense_service._get_supabase')
    def test_get_expense_db_error_returns_none(self, mock_get_supabase, expense_id):
        """Get expense returns None on database error."""
        from services.logistics_expense_service import get_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = get_expense(expense_id)

        assert result is None


# =============================================================================
# CREATE EXPENSE TESTS
# =============================================================================

class TestCreateExpense:
    """Test create_expense() function."""

    @patch('services.logistics_expense_service.get_expense')
    @patch('services.logistics_expense_service._get_supabase')
    def test_create_expense_basic(
        self, mock_get_supabase, mock_get_expense,
        sample_expense_data, deal_id, stage_id, org_id, user_id
    ):
        """Create a basic expense record with required fields."""
        from services.logistics_expense_service import create_expense, LogisticsExpense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        new_id = str(uuid4())
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": new_id}]
        )
        # Mock the re-fetch after insert
        mock_get_expense.return_value = LogisticsExpense(
            id=new_id,
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            stage_code="first_mile",
            expense_subtype="transport",
            amount=Decimal("1500.00"),
            currency="USD",
            expense_date=date(2026, 2, 25),
            description="Test",
            document_id=None,
            created_by=user_id,
            created_at=datetime.now(),
            organization_id=org_id,
        )

        result = create_expense(
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            organization_id=org_id,
            expense_subtype="transport",
            amount=Decimal("1500.00"),
            currency="USD",
            expense_date=date(2026, 2, 25),
            description="Test",
            created_by=user_id,
        )

        assert result is not None
        assert result.deal_id == deal_id
        mock_client.table.assert_called_with("deal_logistics_expenses")

    @patch('services.logistics_expense_service.get_expense')
    @patch('services.logistics_expense_service._get_supabase')
    def test_create_expense_inserts_correct_data(
        self, mock_get_supabase, mock_get_expense,
        deal_id, stage_id, org_id, user_id
    ):
        """Create expense inserts correct data into the table."""
        from services.logistics_expense_service import create_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4())}]
        )
        mock_get_expense.return_value = MagicMock()

        create_expense(
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            organization_id=org_id,
            expense_subtype="storage",
            amount=Decimal("800.50"),
            currency="EUR",
            expense_date=date(2026, 2, 20),
            description="Warehouse storage",
            created_by=user_id,
        )

        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["deal_id"] == deal_id
        assert insert_data["logistics_stage_id"] == stage_id
        assert insert_data["organization_id"] == org_id
        assert insert_data["expense_subtype"] == "storage"
        assert insert_data["amount"] == 800.50  # float(Decimal)
        assert insert_data["currency"] == "EUR"
        assert insert_data["expense_date"] == "2026-02-20"

    @patch('services.logistics_expense_service.get_expense')
    @patch('services.logistics_expense_service._get_supabase')
    def test_create_expense_with_document(
        self, mock_get_supabase, mock_get_expense,
        deal_id, stage_id, org_id, user_id, document_id
    ):
        """Create expense with a document attachment."""
        from services.logistics_expense_service import create_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4())}]
        )
        mock_get_expense.return_value = MagicMock()

        create_expense(
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            organization_id=org_id,
            expense_subtype="transport",
            amount=Decimal("500.00"),
            currency="USD",
            expense_date=date(2026, 2, 25),
            document_id=document_id,
            created_by=user_id,
        )

        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data.get("document_id") == document_id

    @patch('services.logistics_expense_service._get_supabase')
    def test_create_expense_optional_fields_omitted_when_none(
        self, mock_get_supabase, deal_id, stage_id, org_id
    ):
        """Create expense omits optional fields when not provided."""
        from services.logistics_expense_service import create_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4())}]
        )

        create_expense(
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            organization_id=org_id,
            expense_subtype="transport",
            amount=Decimal("100.00"),
            currency="USD",
            expense_date=date(2026, 2, 28),
            # No description, created_by, document_id
        )

        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        # Optional fields should not be in insert data when None
        assert "description" not in insert_data or insert_data.get("description") is None
        assert "created_by" not in insert_data or insert_data.get("created_by") is None
        assert "document_id" not in insert_data or insert_data.get("document_id") is None

    @patch('services.logistics_expense_service._get_supabase')
    def test_create_expense_db_error_returns_none(
        self, mock_get_supabase, deal_id, stage_id, org_id
    ):
        """Create expense returns None when database error occurs."""
        from services.logistics_expense_service import create_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.side_effect = Exception("DB error")

        result = create_expense(
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            organization_id=org_id,
            expense_subtype="transport",
            amount=Decimal("100.00"),
            currency="USD",
            expense_date=date(2026, 2, 28),
        )

        assert result is None

    @patch('services.logistics_expense_service._get_supabase')
    def test_create_expense_empty_response_returns_none(
        self, mock_get_supabase, deal_id, stage_id, org_id
    ):
        """Create expense returns None when DB returns empty data."""
        from services.logistics_expense_service import create_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

        result = create_expense(
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            organization_id=org_id,
            expense_subtype="transport",
            amount=Decimal("100.00"),
            currency="USD",
            expense_date=date(2026, 2, 28),
        )

        assert result is None

    @patch('services.logistics_expense_service.get_expense')
    @patch('services.logistics_expense_service._get_supabase')
    def test_create_expense_refetches_with_join(
        self, mock_get_supabase, mock_get_expense,
        deal_id, stage_id, org_id
    ):
        """Create expense re-fetches the record with FK join for stage_code."""
        from services.logistics_expense_service import create_expense

        new_id = str(uuid4())
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": new_id}]
        )
        mock_get_expense.return_value = MagicMock()

        create_expense(
            deal_id=deal_id,
            logistics_stage_id=stage_id,
            organization_id=org_id,
            expense_subtype="transport",
            amount=Decimal("100.00"),
            currency="USD",
            expense_date=date(2026, 2, 28),
        )

        # Verify get_expense was called to re-fetch with stage_code join
        mock_get_expense.assert_called_once_with(new_id)


# =============================================================================
# DELETE EXPENSE TESTS
# =============================================================================

class TestDeleteExpense:
    """Test delete_expense() function."""

    @patch('services.logistics_expense_service._get_supabase')
    def test_delete_expense_success(self, mock_get_supabase, expense_id):
        """Delete expense returns True on success."""
        from services.logistics_expense_service import delete_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        result = delete_expense(expense_id)

        assert result is True

    @patch('services.logistics_expense_service._get_supabase')
    def test_delete_expense_queries_correct_table(self, mock_get_supabase, expense_id):
        """Delete expense queries deal_logistics_expenses table."""
        from services.logistics_expense_service import delete_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        delete_expense(expense_id)

        mock_client.table.assert_called_with("deal_logistics_expenses")

    @patch('services.logistics_expense_service._get_supabase')
    def test_delete_expense_filters_by_id(self, mock_get_supabase, expense_id):
        """Delete expense filters by expense_id."""
        from services.logistics_expense_service import delete_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        delete_expense(expense_id)

        mock_client.table.return_value.delete.return_value.eq.assert_called_with("id", expense_id)

    @patch('services.logistics_expense_service._get_supabase')
    def test_delete_expense_db_error_returns_false(self, mock_get_supabase, expense_id):
        """Delete expense returns False on database error."""
        from services.logistics_expense_service import delete_expense

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = delete_expense(expense_id)

        assert result is False


# =============================================================================
# SYNC PLAN FACT FOR STAGE TESTS
# =============================================================================

class TestSyncPlanFactForStage:
    """Test sync_plan_fact_for_stage() function.

    This function:
    1. Gets all expenses for a stage
    2. Converts each to USD
    3. Upserts a plan_fact_items row with the total
    """

    @patch('services.logistics_expense_service.get_expenses_for_stage')
    @patch('services.logistics_expense_service._get_supabase')
    def test_sync_plan_fact_gtd_upload_skips(
        self, mock_get_supabase, mock_get_expenses, deal_id, stage_id, org_id
    ):
        """sync_plan_fact_for_stage returns True and skips for gtd_upload stage."""
        from services.logistics_expense_service import sync_plan_fact_for_stage

        result = sync_plan_fact_for_stage(deal_id, stage_id, "gtd_upload", org_id)

        assert result is True
        # Should not query expenses or supabase at all
        mock_get_expenses.assert_not_called()

    @patch('services.currency_service.convert_to_usd')
    @patch('services.logistics_expense_service.get_expenses_for_stage')
    @patch('services.logistics_expense_service._get_supabase')
    def test_sync_plan_fact_with_expenses_upserts(
        self, mock_get_supabase, mock_get_expenses, mock_convert,
        deal_id, stage_id, org_id, category_id
    ):
        """sync_plan_fact_for_stage upserts plan_fact_items with total USD amount."""
        from services.logistics_expense_service import sync_plan_fact_for_stage, LogisticsExpense

        # Mock expenses
        exp1 = LogisticsExpense(
            id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_id,
            stage_code="first_mile", expense_subtype="transport",
            amount=Decimal("1000.00"), currency="USD",
            expense_date=date(2026, 2, 20), description="Truck",
            document_id=None, created_by=None, created_at=datetime.now(),
            organization_id=org_id,
        )
        exp2 = LogisticsExpense(
            id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_id,
            stage_code="first_mile", expense_subtype="handling",
            amount=Decimal("200.00"), currency="USD",
            expense_date=date(2026, 2, 21), description="Loading",
            document_id=None, created_by=None, created_at=datetime.now(),
            organization_id=org_id,
        )
        mock_get_expenses.return_value = [exp1, exp2]

        # Mock convert_to_usd to return amount as-is (both are USD)
        mock_convert.side_effect = lambda amount, currency, rate_date: amount

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock category lookup
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": category_id}]
        )

        # Mock existing plan_fact_items check (no existing row)
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        # Mock insert
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

        result = sync_plan_fact_for_stage(deal_id, stage_id, "first_mile", org_id)

        assert result is True

    @patch('services.logistics_expense_service.get_expenses_for_stage')
    @patch('services.logistics_expense_service._get_supabase')
    def test_sync_plan_fact_no_expenses_nulls_out(
        self, mock_get_supabase, mock_get_expenses,
        deal_id, stage_id, org_id, category_id
    ):
        """sync_plan_fact_for_stage nulls actual_amount when no expenses exist."""
        from services.logistics_expense_service import sync_plan_fact_for_stage

        mock_get_expenses.return_value = []

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock category lookup
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": category_id}]
        )

        # Mock update call
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

        result = sync_plan_fact_for_stage(deal_id, stage_id, "first_mile", org_id)

        assert result is True
        # Verify update was called to null out amounts
        update_call = mock_client.table.return_value.update.call_args
        if update_call:
            update_data = update_call[0][0]
            assert update_data["actual_amount"] is None

    @patch('services.logistics_expense_service.get_expenses_for_stage')
    @patch('services.logistics_expense_service._get_supabase')
    def test_sync_plan_fact_missing_category_returns_false(
        self, mock_get_supabase, mock_get_expenses,
        deal_id, stage_id, org_id
    ):
        """sync_plan_fact_for_stage returns False when category not found."""
        from services.logistics_expense_service import sync_plan_fact_for_stage

        mock_get_expenses.return_value = []

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock category lookup - NOT FOUND
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = sync_plan_fact_for_stage(deal_id, stage_id, "first_mile", org_id)

        assert result is False

    @patch('services.currency_service.convert_to_usd')
    @patch('services.logistics_expense_service.get_expenses_for_stage')
    @patch('services.logistics_expense_service._get_supabase')
    def test_sync_plan_fact_updates_existing_row(
        self, mock_get_supabase, mock_get_expenses, mock_convert,
        deal_id, stage_id, org_id, category_id
    ):
        """sync_plan_fact_for_stage updates existing plan_fact_items row."""
        from services.logistics_expense_service import sync_plan_fact_for_stage, LogisticsExpense

        exp = LogisticsExpense(
            id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_id,
            stage_code="hub", expense_subtype="storage",
            amount=Decimal("500.00"), currency="EUR",
            expense_date=date(2026, 2, 22), description="Hub storage",
            document_id=None, created_by=None, created_at=datetime.now(),
            organization_id=org_id,
        )
        mock_get_expenses.return_value = [exp]

        mock_convert.return_value = Decimal("550.00")  # EUR->USD conversion

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock category lookup
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": category_id}]
        )

        existing_pfi_id = str(uuid4())
        # Mock existing plan_fact_items check (existing row found)
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": existing_pfi_id}]
        )

        # Mock update
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = sync_plan_fact_for_stage(deal_id, stage_id, "hub", org_id)

        assert result is True

    @patch('services.currency_service.convert_to_usd')
    @patch('services.logistics_expense_service.get_expenses_for_stage')
    @patch('services.logistics_expense_service._get_supabase')
    def test_sync_plan_fact_converts_currencies_to_usd(
        self, mock_get_supabase, mock_get_expenses, mock_convert,
        deal_id, stage_id, org_id, category_id
    ):
        """sync_plan_fact_for_stage calls convert_to_usd for each expense."""
        from services.logistics_expense_service import sync_plan_fact_for_stage, LogisticsExpense

        exp_eur = LogisticsExpense(
            id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_id,
            stage_code="transit", expense_subtype="transport",
            amount=Decimal("500.00"), currency="EUR",
            expense_date=date(2026, 2, 22), description="Transport",
            document_id=None, created_by=None, created_at=datetime.now(),
            organization_id=org_id,
        )
        exp_rub = LogisticsExpense(
            id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_id,
            stage_code="transit", expense_subtype="customs_fee",
            amount=Decimal("50000.00"), currency="RUB",
            expense_date=date(2026, 2, 23), description="Fee",
            document_id=None, created_by=None, created_at=datetime.now(),
            organization_id=org_id,
        )
        mock_get_expenses.return_value = [exp_eur, exp_rub]

        # Mock conversions
        mock_convert.side_effect = [Decimal("550.00"), Decimal("555.56")]

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock category lookup
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": category_id}]
        )

        # Mock existing plan_fact_items check (no existing row)
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        # Mock insert
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

        sync_plan_fact_for_stage(deal_id, stage_id, "transit", org_id)

        # Verify convert_to_usd was called for each expense
        assert mock_convert.call_count == 2
        mock_convert.assert_any_call(Decimal("500.00"), "EUR", date(2026, 2, 22))
        mock_convert.assert_any_call(Decimal("50000.00"), "RUB", date(2026, 2, 23))

    @patch('services.logistics_expense_service.get_expenses_for_stage')
    @patch('services.logistics_expense_service._get_supabase')
    def test_sync_plan_fact_db_error_returns_false(
        self, mock_get_supabase, mock_get_expenses,
        deal_id, stage_id, org_id
    ):
        """sync_plan_fact_for_stage returns False on database error."""
        from services.logistics_expense_service import sync_plan_fact_for_stage

        mock_get_expenses.return_value = []

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock category lookup - error
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = sync_plan_fact_for_stage(deal_id, stage_id, "first_mile", org_id)

        assert result is False


# =============================================================================
# GET DEAL LOGISTICS SUMMARY TESTS
# =============================================================================

class TestGetDealLogisticsSummary:
    """Test get_deal_logistics_summary() function.

    Returns per-stage totals and a grand total in USD.
    """

    @patch('services.currency_service.convert_to_usd')
    @patch('services.logistics_expense_service.get_expenses_for_deal')
    def test_summary_with_expenses(
        self, mock_get_expenses, mock_convert, deal_id, org_id
    ):
        """Summary returns per-stage totals and grand total."""
        from services.logistics_expense_service import get_deal_logistics_summary, LogisticsExpense

        stage_fm = str(uuid4())
        stage_hub = str(uuid4())

        expenses = [
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_fm,
                stage_code="first_mile", expense_subtype="transport",
                amount=Decimal("1000.00"), currency="USD",
                expense_date=date(2026, 2, 20), description="Truck",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_fm,
                stage_code="first_mile", expense_subtype="handling",
                amount=Decimal("200.00"), currency="USD",
                expense_date=date(2026, 2, 21), description="Loading",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_hub,
                stage_code="hub", expense_subtype="storage",
                amount=Decimal("500.00"), currency="EUR",
                expense_date=date(2026, 2, 22), description="Hub",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
        ]
        mock_get_expenses.return_value = expenses

        # USD stays as-is, EUR converts
        mock_convert.side_effect = [Decimal("1000.00"), Decimal("200.00"), Decimal("550.00")]

        summary = get_deal_logistics_summary(deal_id)

        assert "first_mile" in summary
        assert "hub" in summary
        assert "grand_total_usd" in summary
        assert summary["first_mile"]["total_usd"] == Decimal("1200.00")
        assert summary["first_mile"]["expense_count"] == 2
        assert summary["hub"]["total_usd"] == Decimal("550.00")
        assert summary["hub"]["expense_count"] == 1
        assert summary["grand_total_usd"] == Decimal("1750.00")

    @patch('services.logistics_expense_service.get_expenses_for_deal')
    def test_summary_empty_deal(self, mock_get_expenses, deal_id):
        """Summary for deal with no expenses returns empty with grand_total_usd=0."""
        from services.logistics_expense_service import get_deal_logistics_summary

        mock_get_expenses.return_value = []

        summary = get_deal_logistics_summary(deal_id)

        assert "grand_total_usd" in summary
        assert summary["grand_total_usd"] == Decimal("0") or summary["grand_total_usd"] == 0

    @patch('services.currency_service.convert_to_usd')
    @patch('services.logistics_expense_service.get_expenses_for_deal')
    def test_summary_single_stage(
        self, mock_get_expenses, mock_convert, deal_id, org_id
    ):
        """Summary for single stage shows correct total."""
        from services.logistics_expense_service import get_deal_logistics_summary, LogisticsExpense

        expenses = [
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=str(uuid4()),
                stage_code="transit", expense_subtype="insurance",
                amount=Decimal("300.00"), currency="USD",
                expense_date=date(2026, 2, 23), description="Insurance",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
        ]
        mock_get_expenses.return_value = expenses
        mock_convert.return_value = Decimal("300.00")

        summary = get_deal_logistics_summary(deal_id)

        assert summary["transit"]["total_usd"] == Decimal("300.00")
        assert summary["transit"]["expense_count"] == 1
        assert summary["grand_total_usd"] == Decimal("300.00")

    @patch('services.currency_service.convert_to_usd')
    @patch('services.logistics_expense_service.get_expenses_for_deal')
    def test_summary_multiple_currencies(
        self, mock_get_expenses, mock_convert, deal_id, org_id
    ):
        """Summary correctly sums expenses in different currencies via USD conversion."""
        from services.logistics_expense_service import get_deal_logistics_summary, LogisticsExpense

        stage_id = str(uuid4())
        expenses = [
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_id,
                stage_code="last_mile", expense_subtype="transport",
                amount=Decimal("100.00"), currency="USD",
                expense_date=date(2026, 2, 25), description="Transport",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=stage_id,
                stage_code="last_mile", expense_subtype="handling",
                amount=Decimal("50.00"), currency="EUR",
                expense_date=date(2026, 2, 25), description="Unloading",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
        ]
        mock_get_expenses.return_value = expenses

        # 100 USD = 100 USD, 50 EUR = 55 USD
        mock_convert.side_effect = [Decimal("100.00"), Decimal("55.00")]

        summary = get_deal_logistics_summary(deal_id)

        assert summary["last_mile"]["total_usd"] == Decimal("155.00")
        assert summary["grand_total_usd"] == Decimal("155.00")

    @patch('services.currency_service.convert_to_usd')
    @patch('services.logistics_expense_service.get_expenses_for_deal')
    def test_summary_calls_convert_to_usd_with_expense_date(
        self, mock_get_expenses, mock_convert, deal_id, org_id
    ):
        """Summary uses expense_date for each convert_to_usd call."""
        from services.logistics_expense_service import get_deal_logistics_summary, LogisticsExpense

        exp_date = date(2026, 2, 22)
        expenses = [
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=str(uuid4()),
                stage_code="hub_hub", expense_subtype="transport",
                amount=Decimal("7500.00"), currency="CNY",
                expense_date=exp_date, description="China shipping",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
        ]
        mock_get_expenses.return_value = expenses
        mock_convert.return_value = Decimal("1050.00")

        get_deal_logistics_summary(deal_id)

        mock_convert.assert_called_once_with(Decimal("7500.00"), "CNY", exp_date)


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_parse_expense_zero_amount(self):
        """Parse handles zero amount (though DB constraint should prevent it)."""
        from services.logistics_expense_service import _parse_expense
        data = {
            "id": str(uuid4()),
            "deal_id": str(uuid4()),
            "logistics_stage_id": str(uuid4()),
            "expense_subtype": "other",
            "amount": "0",
            "currency": "USD",
            "expense_date": "2026-02-28",
            "description": None,
            "document_id": None,
            "created_by": None,
            "created_at": "2026-02-28T10:00:00Z",
            "organization_id": str(uuid4()),
            "logistics_stages": {"stage_code": "hub"},
        }
        expense = _parse_expense(data)
        assert expense.amount == Decimal("0")

    def test_parse_expense_large_amount(self):
        """Parse handles large amounts without overflow."""
        from services.logistics_expense_service import _parse_expense
        data = {
            "id": str(uuid4()),
            "deal_id": str(uuid4()),
            "logistics_stage_id": str(uuid4()),
            "expense_subtype": "transport",
            "amount": "9999999999999.99",
            "currency": "RUB",
            "expense_date": "2026-02-28",
            "description": None,
            "document_id": None,
            "created_by": None,
            "created_at": "2026-02-28T10:00:00Z",
            "organization_id": str(uuid4()),
            "logistics_stages": {"stage_code": "transit"},
        }
        expense = _parse_expense(data)
        assert expense.amount == Decimal("9999999999999.99")

    def test_parse_expense_all_currencies(self):
        """Parse handles all supported currencies."""
        from services.logistics_expense_service import _parse_expense, SUPPORTED_CURRENCIES
        for curr in SUPPORTED_CURRENCIES:
            data = {
                "id": str(uuid4()),
                "deal_id": str(uuid4()),
                "logistics_stage_id": str(uuid4()),
                "expense_subtype": "transport",
                "amount": "100.00",
                "currency": curr,
                "expense_date": "2026-02-28",
                "description": None,
                "document_id": None,
                "created_by": None,
                "created_at": "2026-02-28T10:00:00Z",
                "organization_id": str(uuid4()),
                "logistics_stages": {"stage_code": "hub"},
            }
            expense = _parse_expense(data)
            assert expense.currency == curr

    def test_parse_expense_all_subtypes(self):
        """Parse handles all expense subtypes."""
        from services.logistics_expense_service import _parse_expense, EXPENSE_SUBTYPE_LABELS
        for subtype in EXPENSE_SUBTYPE_LABELS.keys():
            data = {
                "id": str(uuid4()),
                "deal_id": str(uuid4()),
                "logistics_stage_id": str(uuid4()),
                "expense_subtype": subtype,
                "amount": "100.00",
                "currency": "USD",
                "expense_date": "2026-02-28",
                "description": None,
                "document_id": None,
                "created_by": None,
                "created_at": "2026-02-28T10:00:00Z",
                "organization_id": str(uuid4()),
                "logistics_stages": {"stage_code": "hub"},
            }
            expense = _parse_expense(data)
            assert expense.expense_subtype == subtype

    @patch('services.logistics_expense_service.get_expenses_for_deal')
    def test_summary_with_no_stage_code(self, mock_get_expenses, deal_id, org_id):
        """Summary handles expense with empty stage_code gracefully."""
        from services.logistics_expense_service import get_deal_logistics_summary, LogisticsExpense

        expenses = [
            LogisticsExpense(
                id=str(uuid4()), deal_id=deal_id, logistics_stage_id=str(uuid4()),
                stage_code="", expense_subtype="transport",
                amount=Decimal("100.00"), currency="USD",
                expense_date=date(2026, 2, 25), description="Test",
                document_id=None, created_by=None, created_at=datetime.now(),
                organization_id=org_id,
            ),
        ]
        mock_get_expenses.return_value = expenses

        with patch('services.currency_service.convert_to_usd', return_value=Decimal("100.00")):
            summary = get_deal_logistics_summary(deal_id)

        # Should not crash -- the empty key should still work in the dict
        assert "grand_total_usd" in summary

    def test_parse_expense_iso_date_with_time(self):
        """Parse handles expense_date that includes time component."""
        from services.logistics_expense_service import _parse_expense
        data = {
            "id": str(uuid4()),
            "deal_id": str(uuid4()),
            "logistics_stage_id": str(uuid4()),
            "expense_subtype": "transport",
            "amount": "100.00",
            "currency": "USD",
            "expense_date": "2026-02-28T14:30:00+03:00",
            "description": None,
            "document_id": None,
            "created_by": None,
            "created_at": "2026-02-28T10:00:00Z",
            "organization_id": str(uuid4()),
            "logistics_stages": {"stage_code": "first_mile"},
        }
        expense = _parse_expense(data)
        # Should extract just the date part
        assert isinstance(expense.expense_date, date)
        assert expense.expense_date == date(2026, 2, 28)

    def test_parse_expense_created_at_with_z_suffix(self):
        """Parse handles created_at timestamp with Z suffix."""
        from services.logistics_expense_service import _parse_expense
        data = {
            "id": str(uuid4()),
            "deal_id": str(uuid4()),
            "logistics_stage_id": str(uuid4()),
            "expense_subtype": "transport",
            "amount": "100.00",
            "currency": "USD",
            "expense_date": "2026-02-28",
            "description": None,
            "document_id": None,
            "created_by": None,
            "created_at": "2026-02-28T10:00:00Z",
            "organization_id": str(uuid4()),
            "logistics_stages": {"stage_code": "first_mile"},
        }
        expense = _parse_expense(data)
        assert isinstance(expense.created_at, datetime)
