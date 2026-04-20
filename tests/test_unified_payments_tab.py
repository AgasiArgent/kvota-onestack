"""
TDD Tests for Customer Debt Summary Card (P2.4) + pure logic helpers.

Feature P2.4: Customer Debt Summary Card
- get_customer_debt_summary(customer_id) in services/plan_fact_service.py
- Returns: total_debt, last_payment_date, last_payment_amount, overdue_count,
  overdue_amount, unpaid_count
- Card on /customers/{id} page

Note: P2.5 Unified Payments Tab tests (TestPaymentsTabExistsInFinanceRoute,
TestFinancePaymentsTabFunction, TestPaymentsTabFilters,
TestPaymentsTabQueryAndJoins, TestPaymentsTabTableColumns,
TestPaymentsTabSummaryFooter, TestPaymentsTabClickableRows,
TestGroupByCustomerToggle, TestRenderPaymentsGroupedContent,
TestFinanceRouteAcceptsCustomerFilter) were removed during Phase 6C-2B-10c1
archive of /finance + /payments/calendar + /deals (2026-04-20). Their target
helpers (finance_payments_tab, render_payments_grouped, GET /finance handler)
now live in legacy-fasthtml/finance_lifecycle.py and are not imported.
"""

import pytest
import re
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Path constants (relative to project root via os.path)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
PLAN_FACT_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "plan_fact_service.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


def _read_plan_fact_service_source():
    """Read plan_fact_service.py source code without importing it."""
    with open(PLAN_FACT_SERVICE_PY) as f:
        return f.read()


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def org_id():
    return _make_uuid()


@pytest.fixture
def customer_id():
    return _make_uuid()


@pytest.fixture
def deal_id():
    return _make_uuid()


@pytest.fixture
def category_client_payment():
    """Income category."""
    return {
        "id": _make_uuid(),
        "code": "client_payment",
        "name": "Оплата от клиента",
        "is_income": True,
        "sort_order": 1,
    }


@pytest.fixture
def category_supplier_payment():
    """Expense category."""
    return {
        "id": _make_uuid(),
        "code": "supplier_payment",
        "name": "Оплата поставщику",
        "is_income": False,
        "sort_order": 2,
    }


@pytest.fixture
def sample_plan_fact_items_with_deals(deal_id, category_client_payment, category_supplier_payment):
    """Plan-fact items with deal/customer info for the payments tab table."""
    cust_id = _make_uuid()
    return [
        {
            "id": _make_uuid(),
            "deal_id": deal_id,
            "category_id": category_client_payment["id"],
            "description": "Аванс от клиента (50%)",
            "planned_amount": 500000.00,
            "planned_currency": "RUB",
            "planned_date": "2026-02-15",
            "actual_amount": 500000.00,
            "actual_currency": "RUB",
            "actual_date": "2026-02-14",
            "variance_amount": 0.0,
            "plan_fact_categories": category_client_payment,
            "deals": {
                "id": deal_id,
                "deal_number": "D-2026-0042",
                "specifications": {
                    "quotes": {
                        "customers": {
                            "id": cust_id,
                            "name": "Test Customer LLC",
                        }
                    }
                }
            },
        },
        {
            "id": _make_uuid(),
            "deal_id": deal_id,
            "category_id": category_supplier_payment["id"],
            "description": "Оплата поставщику (100%)",
            "planned_amount": 300000.00,
            "planned_currency": "RUB",
            "planned_date": "2026-02-10",
            "actual_amount": None,
            "actual_currency": None,
            "actual_date": None,
            "variance_amount": None,
            "plan_fact_categories": category_supplier_payment,
            "deals": {
                "id": deal_id,
                "deal_number": "D-2026-0042",
                "specifications": {
                    "quotes": {
                        "customers": {
                            "id": cust_id,
                            "name": "Test Customer LLC",
                        }
                    }
                }
            },
        },
    ]



# ==============================================================================
# PART 3: P2.4 — Customer Debt Summary Card
# ==============================================================================

class TestGetCustomerDebtSummaryExists:
    """get_customer_debt_summary must exist in plan_fact_service.py."""

    def test_function_exists_in_service(self):
        """get_customer_debt_summary() must be defined in plan_fact_service.py."""
        source = _read_plan_fact_service_source()
        assert "def get_customer_debt_summary(" in source, (
            "get_customer_debt_summary() must be defined in services/plan_fact_service.py"
        )

    def test_function_importable(self):
        """get_customer_debt_summary must be importable from plan_fact_service."""
        from services.plan_fact_service import get_customer_debt_summary
        assert callable(get_customer_debt_summary)

    def test_function_accepts_customer_id(self):
        """get_customer_debt_summary must accept customer_id as first parameter."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\((.*?)\)',
            source,
        )
        assert match, "get_customer_debt_summary function signature not found"
        params = match.group(1)
        assert "customer_id" in params, (
            "get_customer_debt_summary must accept customer_id parameter"
        )


class TestGetCustomerDebtSummaryReturnStructure:
    """
    get_customer_debt_summary must return a dict with the specified keys:
    total_debt, last_payment_date, last_payment_amount, overdue_count,
    overdue_amount, unpaid_count
    """

    def test_return_has_total_debt_key(self):
        """Return dict must include total_debt."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        assert match, "get_customer_debt_summary function not found"
        fn_body = match.group(1)
        assert "total_debt" in fn_body, (
            "get_customer_debt_summary must return total_debt in result dict"
        )

    def test_return_has_last_payment_date_key(self):
        """Return dict must include last_payment_date."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        assert match, "get_customer_debt_summary function not found"
        fn_body = match.group(1)
        assert "last_payment_date" in fn_body, (
            "get_customer_debt_summary must return last_payment_date in result dict"
        )

    def test_return_has_last_payment_amount_key(self):
        """Return dict must include last_payment_amount."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        assert match, "get_customer_debt_summary function not found"
        fn_body = match.group(1)
        assert "last_payment_amount" in fn_body, (
            "get_customer_debt_summary must return last_payment_amount in result dict"
        )

    def test_return_has_overdue_count_key(self):
        """Return dict must include overdue_count."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        assert match, "get_customer_debt_summary function not found"
        fn_body = match.group(1)
        assert "overdue_count" in fn_body, (
            "get_customer_debt_summary must return overdue_count in result dict"
        )

    def test_return_has_overdue_amount_key(self):
        """Return dict must include overdue_amount."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        assert match, "get_customer_debt_summary function not found"
        fn_body = match.group(1)
        assert "overdue_amount" in fn_body, (
            "get_customer_debt_summary must return overdue_amount in result dict"
        )

    def test_return_has_unpaid_count_key(self):
        """Return dict must include unpaid_count."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        assert match, "get_customer_debt_summary function not found"
        fn_body = match.group(1)
        assert "unpaid_count" in fn_body, (
            "get_customer_debt_summary must return unpaid_count in result dict"
        )


class TestGetCustomerDebtSummaryBehavior:
    """
    Test the business logic of get_customer_debt_summary with mocked DB.
    """

    def test_customer_with_no_deals_returns_zeroes(self):
        """Customer with no deals should return all-zero summary."""
        # Mock the supabase to return empty data
        with patch('services.plan_fact_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # Simulate empty query results (no deals for customer)
            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.is_.return_value = mock_query
            mock_query.lt.return_value = mock_query
            mock_query.not_.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[], count=0)

            from services.plan_fact_service import get_customer_debt_summary
            result = get_customer_debt_summary(_make_uuid())

            assert isinstance(result, dict), "Result must be a dict"
            assert result.get('total_debt', -1) == 0 or result.get('total_debt') == Decimal('0'), (
                "Customer with no deals must have total_debt = 0"
            )
            assert result.get('overdue_count', -1) == 0, (
                "Customer with no deals must have overdue_count = 0"
            )
            assert result.get('unpaid_count', -1) == 0, (
                "Customer with no deals must have unpaid_count = 0"
            )
            assert result.get('overdue_amount', -1) == 0 or result.get('overdue_amount') == Decimal('0'), (
                "Customer with no deals must have overdue_amount = 0"
            )

    def test_customer_all_paid_returns_zero_debt(self):
        """Customer where all items are paid should have total_debt=0."""
        with patch('services.plan_fact_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # All items paid: actual_amount IS NOT NULL for every item
            paid_items = [
                {
                    "id": _make_uuid(),
                    "deal_id": _make_uuid(),
                    "planned_amount": 100000,
                    "actual_amount": 100000,
                    "actual_date": "2026-01-15",
                    "planned_date": "2026-01-15",
                    "plan_fact_categories": {"is_income": True},
                },
            ]

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.is_.return_value = mock_query
            mock_query.lt.return_value = mock_query
            mock_query.not_.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.limit.return_value = mock_query
            # Return empty for unpaid queries (all paid)
            mock_query.execute.return_value = MagicMock(data=[], count=0)

            from services.plan_fact_service import get_customer_debt_summary
            result = get_customer_debt_summary(_make_uuid())

            assert isinstance(result, dict), "Result must be a dict"
            debt = result.get('total_debt', -1)
            assert debt == 0 or debt == Decimal('0'), (
                "Customer with all items paid must have total_debt = 0"
            )

    def test_overdue_items_counted_correctly(self):
        """Overdue = unpaid + planned_date < today. Must count them."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        customer_id = _make_uuid()
        deal_id_1 = _make_uuid()
        deal_id_2 = _make_uuid()

        with patch('services.plan_fact_service.get_supabase') as mock_sb:
            mock_client = MagicMock()
            mock_sb.return_value = mock_client

            # First query: deals with customer chain
            deals_data = [
                {
                    "id": deal_id_1,
                    "specifications": {"quotes": {"customer_id": customer_id}},
                },
                {
                    "id": deal_id_2,
                    "specifications": {"quotes": {"customer_id": customer_id}},
                },
            ]

            # Second query: unpaid plan_fact_items
            overdue_items = [
                {
                    "id": _make_uuid(),
                    "deal_id": deal_id_1,
                    "planned_amount": 50000,
                    "actual_amount": None,
                    "planned_date": yesterday.isoformat(),
                    "plan_fact_categories": {"is_income": True},
                },
                {
                    "id": _make_uuid(),
                    "deal_id": deal_id_2,
                    "planned_amount": 30000,
                    "actual_amount": None,
                    "planned_date": (today - timedelta(days=10)).isoformat(),
                    "plan_fact_categories": {"is_income": True},
                },
            ]

            # Third query: paid items (last payment) - empty
            paid_items = []

            mock_query = MagicMock()
            mock_client.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.is_.return_value = mock_query
            mock_query.lt.return_value = mock_query
            mock_query.not_.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.limit.return_value = mock_query
            # Return different data for each .execute() call
            mock_query.execute.side_effect = [
                MagicMock(data=deals_data, count=2),
                MagicMock(data=overdue_items, count=2),
                MagicMock(data=paid_items, count=0),
            ]

            from services.plan_fact_service import get_customer_debt_summary
            result = get_customer_debt_summary(customer_id)

            assert isinstance(result, dict), "Result must be a dict"
            # Should detect the 2 overdue items
            overdue_count = result.get('overdue_count', 0)
            assert overdue_count >= 2, (
                f"Expected at least 2 overdue items, got {overdue_count}. "
                "Overdue = unpaid with planned_date < today"
            )


class TestDebtSummaryQueryChain:
    """
    get_customer_debt_summary must query through the chain:
    customer -> quotes -> specifications -> deals -> plan_fact_items
    """

    def test_function_queries_deals_via_customer_chain(self):
        """The function must traverse customer->quote->spec->deal chain."""
        source = _read_plan_fact_service_source()
        match = re.search(
            r'def get_customer_debt_summary\(.*?\n(.*?)(?=\ndef |\Z)',
            source,
            re.DOTALL,
        )
        assert match, "get_customer_debt_summary function not found"
        fn_body = match.group(1)
        # Must reference at least deals and plan_fact_items
        has_deals = "deals" in fn_body
        has_items = "plan_fact_items" in fn_body or "items" in fn_body
        assert has_deals and has_items, (
            "get_customer_debt_summary must query deals and plan_fact_items "
            "via the customer->quote->spec->deal chain"
        )


# ==============================================================================
# PART 4: Customer Detail Page — Debt Card — REMOVED
# ==============================================================================
# TestCustomerDetailDebtCard (3 tests) and TestCustomerDebtCardContent (2 tests)
# inspected the FastHTML @rt("/customers/{customer_id}") handler for the debt
# card integration. That handler was archived to legacy-fasthtml/customers.py
# in Phase 6C-2B-1 (2026-04-20). The Next.js /customers/[id] page now owns
# the debt card UI; the get_customer_debt_summary service remains unchanged
# and is exercised by services/plan_fact_service tests.


# ==============================================================================
# PART 5: Calculation Logic Tests (pure Python, no source inspection)
# ==============================================================================

class TestPaymentsSummaryCalculation:
    """Test the summary calculation logic for the payments tab."""

    def test_income_total_from_items(self):
        """Income totals: sum of planned_amount where category.is_income=True."""
        items = [
            {"planned_amount": 500000, "actual_amount": 500000, "plan_fact_categories": {"is_income": True}},
            {"planned_amount": 300000, "actual_amount": 300000, "plan_fact_categories": {"is_income": True}},
            {"planned_amount": 200000, "actual_amount": None, "plan_fact_categories": {"is_income": False}},
        ]
        income_planned = sum(
            float(i["planned_amount"] or 0)
            for i in items
            if (i.get("plan_fact_categories") or {}).get("is_income")
        )
        income_actual = sum(
            float(i["actual_amount"] or 0)
            for i in items
            if (i.get("plan_fact_categories") or {}).get("is_income") and i.get("actual_amount")
        )
        assert income_planned == 800000.0
        assert income_actual == 800000.0

    def test_expense_total_from_items(self):
        """Expense totals: sum of planned_amount where category.is_income=False."""
        items = [
            {"planned_amount": 500000, "actual_amount": 500000, "plan_fact_categories": {"is_income": True}},
            {"planned_amount": 200000, "actual_amount": 190000, "plan_fact_categories": {"is_income": False}},
            {"planned_amount": 100000, "actual_amount": None, "plan_fact_categories": {"is_income": False}},
        ]
        expense_planned = sum(
            float(i["planned_amount"] or 0)
            for i in items
            if not (i.get("plan_fact_categories") or {}).get("is_income")
        )
        expense_actual = sum(
            float(i["actual_amount"] or 0)
            for i in items
            if not (i.get("plan_fact_categories") or {}).get("is_income") and i.get("actual_amount")
        )
        assert expense_planned == 300000.0
        assert expense_actual == 190000.0

    def test_net_balance_calculation(self):
        """Net balance = income_actual - expense_actual."""
        income_actual = 500000.0
        expense_actual = 200000.0
        net = income_actual - expense_actual
        assert net == 300000.0

    def test_summary_with_no_items(self):
        """Summary with empty list should return all zeroes."""
        items = []
        income_planned = sum(
            float(i["planned_amount"] or 0)
            for i in items
            if (i.get("plan_fact_categories") or {}).get("is_income")
        )
        assert income_planned == 0.0

    def test_summary_with_none_amounts(self):
        """Items with None amounts should be treated as 0."""
        items = [
            {"planned_amount": None, "actual_amount": None, "plan_fact_categories": {"is_income": True}},
        ]
        total = sum(
            float(i["planned_amount"] or 0)
            for i in items
        )
        assert total == 0.0


class TestOverdueDetectionLogic:
    """Test the logic for detecting overdue payments."""

    def test_unpaid_past_date_is_overdue(self):
        """Item with actual_amount=None and planned_date < today is overdue."""
        today = date.today()
        item = {
            "actual_amount": None,
            "planned_date": (today - timedelta(days=5)).isoformat(),
        }
        planned = datetime.strptime(item["planned_date"], "%Y-%m-%d").date()
        is_overdue = item["actual_amount"] is None and planned < today
        assert is_overdue is True

    def test_paid_item_is_not_overdue(self):
        """Item with actual_amount set is NOT overdue, even if late."""
        today = date.today()
        item = {
            "actual_amount": 100000,
            "planned_date": (today - timedelta(days=5)).isoformat(),
        }
        planned = datetime.strptime(item["planned_date"], "%Y-%m-%d").date()
        is_overdue = item["actual_amount"] is None and planned < today
        assert is_overdue is False

    def test_future_unpaid_is_not_overdue(self):
        """Item with planned_date in the future is NOT overdue."""
        today = date.today()
        item = {
            "actual_amount": None,
            "planned_date": (today + timedelta(days=10)).isoformat(),
        }
        planned = datetime.strptime(item["planned_date"], "%Y-%m-%d").date()
        is_overdue = item["actual_amount"] is None and planned < today
        assert is_overdue is False

    def test_today_planned_unpaid_is_not_overdue(self):
        """Item planned for today but not yet paid is NOT overdue (< not <=)."""
        today = date.today()
        item = {
            "actual_amount": None,
            "planned_date": today.isoformat(),
        }
        planned = datetime.strptime(item["planned_date"], "%Y-%m-%d").date()
        is_overdue = item["actual_amount"] is None and planned < today
        assert is_overdue is False


class TestCustomerGroupingLogic:
    """Test the logic for grouping payments by customer."""

    def test_group_items_by_customer_name(self):
        """Items should be grouped by customer name from deal chain."""
        items = [
            {"id": "1", "deals": {"specifications": {"quotes": {"customers": {"name": "Alpha LLC"}}}}},
            {"id": "2", "deals": {"specifications": {"quotes": {"customers": {"name": "Beta Corp"}}}}},
            {"id": "3", "deals": {"specifications": {"quotes": {"customers": {"name": "Alpha LLC"}}}}},
        ]
        grouped = {}
        for item in items:
            cust_name = (
                (item.get("deals") or {})
                .get("specifications", {})
                .get("quotes", {})
                .get("customers", {})
                .get("name", "Unknown")
            )
            grouped.setdefault(cust_name, []).append(item)

        assert len(grouped) == 2
        assert len(grouped["Alpha LLC"]) == 2
        assert len(grouped["Beta Corp"]) == 1

    def test_group_items_missing_customer_uses_unknown(self):
        """Items without customer info should be grouped under 'Unknown'."""
        items = [
            {"id": "1", "deals": None},
            {"id": "2", "deals": {"specifications": None}},
        ]
        grouped = {}
        for item in items:
            deals = item.get("deals") or {}
            specs = deals.get("specifications") or {}
            quotes = specs.get("quotes") or {}
            customers = quotes.get("customers") or {}
            cust_name = customers.get("name", "Unknown")
            grouped.setdefault(cust_name, []).append(item)

        assert "Unknown" in grouped
        assert len(grouped["Unknown"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
