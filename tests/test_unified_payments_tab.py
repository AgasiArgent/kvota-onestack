"""
TDD Tests for Unified Payments Tab (P2.5) + Customer Grouping (P2.4) + Customer Debt Summary Card

Feature P2.5: Unified Payments Tab on /finance
- Replace non-functional "Calendar" tab with "Payments" tab
- Show ALL plan_fact_items across ALL deals in one table
- 9 columns: planned_date, deal_number, customer, category, description,
  planned_amount, actual_amount, actual_date, variance
- Filters: payment_type, payment_status, date_from, date_to, deal_filter
- Summary footer with income/expense totals and net balance
- Color coding: income green, expense red, overdue yellow
- Clickable rows -> navigate to deal detail

Feature P2.4 Addition 1: Group by Customer toggle
- Toggle "By records" (flat, default) / "By customers" (grouped)
- URL param: ?view=grouped
- Collapsible customer rows with subtotals
- render_payments_grouped() helper function

Feature P2.4 Addition 2: Customer Debt Summary Card
- get_customer_debt_summary(customer_id) in services/plan_fact_service.py
- Returns: total_debt, last_payment_date, last_payment_amount, overdue_count,
  overdue_amount, unpaid_count
- Card on /customers/{id} page
- Link to /finance?tab=payments&customer_filter={id}

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the features are implemented.
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
# PART 1: P2.5 — Unified Payments Tab on /finance
# ==============================================================================

class TestPaymentsTabExistsInFinanceRoute:
    """
    The /finance route must accept tab=payments and render a Payments tab
    instead of (or alongside) the old Calendar tab.
    """

    def test_finance_route_accepts_payments_tab(self):
        """The /finance GET handler must handle tab='payments'."""
        source = _read_main_source()
        # Find the finance route handler
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler not found"
        handler_body = match.group(0) + match.group(1)
        # Should reference tab == "payments" or tab='payments'
        has_payments_tab = (
            'tab == "payments"' in handler_body
            or "tab == 'payments'" in handler_body
            or 'tab=="payments"' in handler_body
        )
        assert has_payments_tab, (
            'GET /finance handler must handle tab="payments" (replace calendar tab)'
        )

    def test_finance_tab_navigation_shows_payments(self):
        """The finance page tab bar must show 'Платежи' instead of 'Календарь'."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler not found"
        handler_body = match.group(0) + match.group(1)
        has_payments_label = "Платежи" in handler_body
        assert has_payments_label, (
            'Finance tab bar must include "Платежи" tab label'
        )

    def test_finance_tab_link_uses_payments_param(self):
        """The Payments tab link must point to ?tab=payments."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler not found"
        handler_body = match.group(0) + match.group(1)
        assert "tab=payments" in handler_body, (
            'Finance tab bar must link to ?tab=payments'
        )


class TestFinancePaymentsTabFunction:
    """The finance_payments_tab function must exist and be called."""

    def test_finance_payments_tab_function_exists(self):
        """finance_payments_tab() function must be defined in main.py."""
        source = _read_main_source()
        assert "def finance_payments_tab(" in source, (
            "finance_payments_tab() function must be defined in main.py"
        )

    def test_finance_route_calls_payments_tab(self):
        """The /finance GET handler must call finance_payments_tab when tab=payments."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler not found"
        handler_body = match.group(0) + match.group(1)
        assert "finance_payments_tab" in handler_body, (
            'GET /finance must call finance_payments_tab() for tab="payments"'
        )


class TestPaymentsTabFilters:
    """
    The /finance route must accept filter params for the payments tab:
    payment_type, payment_status, date_from, date_to, deal_filter.
    """

    def test_finance_route_accepts_payment_type_param(self):
        """The /finance GET must accept payment_type parameter."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\((.*?)\):',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler signature not found"
        params = match.group(1)
        assert "payment_type" in params, (
            'GET /finance must accept payment_type filter param'
        )

    def test_finance_route_accepts_payment_status_param(self):
        """The /finance GET must accept payment_status parameter."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\((.*?)\):',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler signature not found"
        params = match.group(1)
        assert "payment_status" in params, (
            'GET /finance must accept payment_status filter param'
        )

    def test_finance_route_accepts_date_from_param(self):
        """The /finance GET must accept date_from parameter."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\((.*?)\):',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler signature not found"
        params = match.group(1)
        assert "date_from" in params, (
            'GET /finance must accept date_from filter param'
        )

    def test_finance_route_accepts_date_to_param(self):
        """The /finance GET must accept date_to parameter."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\((.*?)\):',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler signature not found"
        params = match.group(1)
        assert "date_to" in params, (
            'GET /finance must accept date_to filter param'
        )

    def test_finance_route_accepts_deal_filter_param(self):
        """The /finance GET must accept deal_filter parameter."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\((.*?)\):',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler signature not found"
        params = match.group(1)
        assert "deal_filter" in params, (
            'GET /finance must accept deal_filter filter param'
        )


class TestPaymentsTabQueryAndJoins:
    """
    The finance_payments_tab must query plan_fact_items with
    category and deal joins across all deals for the org.
    """

    def test_payments_tab_queries_plan_fact_items(self):
        """finance_payments_tab must query plan_fact_items table."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        assert "plan_fact_items" in fn_body, (
            "finance_payments_tab must query plan_fact_items table"
        )

    def test_payments_tab_joins_categories(self):
        """finance_payments_tab must join plan_fact_categories."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        assert "plan_fact_categories" in fn_body, (
            "finance_payments_tab must join plan_fact_categories for category names"
        )

    def test_payments_tab_joins_deals(self):
        """finance_payments_tab must join deals for deal numbers."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        assert "deals" in fn_body, (
            "finance_payments_tab must join deals table for deal_number"
        )

    def test_payments_tab_filters_by_org(self):
        """Payments must be filtered by organization_id via deals."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_org_filter = (
            "organization_id" in fn_body
            or "org_id" in fn_body
        )
        assert has_org_filter, (
            "finance_payments_tab must filter by organization_id"
        )


class TestPaymentsTabTableColumns:
    """The payments table must have 9 columns as specified in the blueprint."""

    def test_payments_table_has_planned_date_column(self):
        """Table must include planned_date column."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_col = "planned_date" in fn_body or "Дата план" in fn_body or "План. дата" in fn_body
        assert has_col, (
            "Payments table must include planned_date column"
        )

    def test_payments_table_has_deal_number_column(self):
        """Table must include deal_number column."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_col = "deal_number" in fn_body or "Сделка" in fn_body
        assert has_col, (
            "Payments table must include deal number column"
        )

    def test_payments_table_has_customer_column(self):
        """Table must include customer name column."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_col = "customer" in fn_body.lower() or "Клиент" in fn_body
        assert has_col, (
            "Payments table must include customer name column"
        )

    def test_payments_table_has_variance_column(self):
        """Table must include variance column."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_col = "variance" in fn_body.lower() or "Отклонение" in fn_body or "Разница" in fn_body
        assert has_col, (
            "Payments table must include variance column"
        )


class TestPaymentsTabSummaryFooter:
    """
    The payments tab must show a summary footer with:
    - Total incoming planned/paid
    - Total outgoing planned/paid
    - Net balance
    """

    def test_payments_tab_calculates_income_totals(self):
        """finance_payments_tab must calculate total income (planned + actual)."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_income_total = (
            "income" in fn_body.lower()
            or "is_income" in fn_body
            or "Приход" in fn_body
            or "Поступления" in fn_body
        )
        assert has_income_total, (
            "finance_payments_tab must calculate income totals for summary"
        )

    def test_payments_tab_calculates_expense_totals(self):
        """finance_payments_tab must calculate total expenses."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_expense_total = (
            "expense" in fn_body.lower()
            or "Расход" in fn_body
            or "Выплаты" in fn_body
            or (not fn_body.startswith("pass"))  # Just needs to exist and have content
        )
        # More specific check: the function must separate income and expense
        has_separation = "is_income" in fn_body
        assert has_separation, (
            "finance_payments_tab must separate income/expense for summary totals"
        )

    def test_payments_tab_shows_summary_section(self):
        """The payments tab must render a summary/footer section."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_summary = (
            "Итого" in fn_body
            or "Баланс" in fn_body
            or "summary" in fn_body.lower()
            or "footer" in fn_body.lower()
        )
        assert has_summary, (
            "finance_payments_tab must show a summary/footer section with totals"
        )


class TestPaymentsTabClickableRows:
    """Rows in the payments table must be clickable, navigating to deal detail."""

    def test_payments_rows_link_to_deal(self):
        """Each payment row must link to /finance/{deal_id}."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_deal_link = (
            "/finance/" in fn_body
            and ("deal_id" in fn_body or "deal" in fn_body)
            and ("href" in fn_body or "onclick" in fn_body or "hx-get" in fn_body
                 or "cursor" in fn_body or "clickable" in fn_body)
        )
        assert has_deal_link, (
            "Payment rows must be clickable and link to deal detail page"
        )


# ==============================================================================
# PART 2: P2.4 — Group by Customer Toggle
# ==============================================================================

class TestGroupByCustomerToggle:
    """
    The payments tab must have a toggle for flat vs grouped view.
    URL param: ?view=grouped
    """

    def test_finance_route_accepts_view_param_for_payments(self):
        """The /finance GET handler must pass view param to payments tab."""
        source = _read_main_source()
        # The route already has a view param, but it must be used for payments tab too
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler not found"
        handler_body = match.group(0) + match.group(1)
        # When tab == payments, view param must be passed to finance_payments_tab
        has_view_in_payments = (
            "finance_payments_tab" in handler_body
            and "view" in handler_body
        )
        assert has_view_in_payments, (
            "finance_payments_tab call must receive view parameter"
        )

    def test_render_payments_grouped_function_exists(self):
        """render_payments_grouped() function must be defined in main.py."""
        source = _read_main_source()
        assert "def render_payments_grouped(" in source, (
            "render_payments_grouped() function must be defined in main.py"
        )

    def test_payments_tab_has_toggle_buttons(self):
        """The payments tab filter bar must include view toggle buttons."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_flat_toggle = "По записям" in fn_body
        has_grouped_toggle = "По клиентам" in fn_body
        assert has_flat_toggle, (
            "Payments tab must have 'По записям' (flat view) toggle button"
        )
        assert has_grouped_toggle, (
            "Payments tab must have 'По клиентам' (grouped view) toggle button"
        )

    def test_payments_tab_checks_view_param(self):
        """finance_payments_tab must check view param and branch on 'grouped'."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        has_grouped_check = (
            '"grouped"' in fn_body
            or "'grouped'" in fn_body
            or "view == " in fn_body
        )
        assert has_grouped_check, (
            "finance_payments_tab must check for view='grouped' parameter"
        )

    def test_grouped_view_calls_render_payments_grouped(self):
        """When view=grouped, finance_payments_tab must call render_payments_grouped."""
        source = _read_main_source()
        match = re.search(
            r'def finance_payments_tab\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "finance_payments_tab function not found"
        fn_body = match.group(1)
        assert "render_payments_grouped" in fn_body, (
            "finance_payments_tab must call render_payments_grouped for grouped view"
        )


class TestRenderPaymentsGroupedContent:
    """render_payments_grouped must group items by customer with subtotals."""

    def test_grouped_view_groups_by_customer(self):
        """render_payments_grouped must organize items by customer name."""
        source = _read_main_source()
        match = re.search(
            r'def render_payments_grouped\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "render_payments_grouped function not found"
        fn_body = match.group(1)
        has_customer_grouping = (
            "customer" in fn_body.lower()
            and ("group" in fn_body.lower() or "dict" in fn_body.lower()
                 or "defaultdict" in fn_body.lower())
        )
        assert has_customer_grouping, (
            "render_payments_grouped must group items by customer"
        )

    def test_grouped_view_has_subtotals(self):
        """render_payments_grouped must show subtotals per customer."""
        source = _read_main_source()
        match = re.search(
            r'def render_payments_grouped\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "render_payments_grouped function not found"
        fn_body = match.group(1)
        has_subtotals = (
            "subtotal" in fn_body.lower()
            or "sum" in fn_body.lower()
            or "итого" in fn_body.lower()
        )
        assert has_subtotals, (
            "render_payments_grouped must calculate subtotals per customer group"
        )


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
# PART 4: Customer Detail Page — Debt Card
# ==============================================================================

class TestCustomerDetailDebtCard:
    """The customer detail page /customers/{id} must show a debt summary card."""

    def test_customer_detail_calls_debt_summary(self):
        """The /customers/{customer_id} GET handler must call get_customer_debt_summary."""
        source = _read_main_source()
        # Find the customer detail handler and check for debt summary
        match = re.search(
            r'@rt\(\s*"/customers/\{customer_id\}"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /customers/{customer_id} handler not found"
        handler_body = match.group(1)
        assert "get_customer_debt_summary" in handler_body, (
            "Customer detail page must call get_customer_debt_summary()"
        )

    def test_customer_detail_shows_debt_total(self):
        """The customer page must render total_debt from the debt summary."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/customers/\{customer_id\}"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /customers/{customer_id} handler not found"
        handler_body = match.group(1)
        has_debt_display = (
            "total_debt" in handler_body
            or "Задолженность" in handler_body
            or "Долг" in handler_body
        )
        assert has_debt_display, (
            "Customer detail page must display total_debt amount"
        )

    def test_customer_debt_card_links_to_finance_payments(self):
        """The debt card must link to /finance?tab=payments&customer_filter={id}."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/customers/\{customer_id\}"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /customers/{customer_id} handler not found"
        handler_body = match.group(1)
        has_finance_link = (
            "tab=payments" in handler_body
            and "customer_filter" in handler_body
        )
        assert has_finance_link, (
            "Debt card must link to /finance?tab=payments&customer_filter={customer_id}"
        )


class TestCustomerDebtCardContent:
    """Test the specific content elements of the debt summary card."""

    def test_debt_card_shows_overdue_count(self):
        """Debt card must display number of overdue items."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/customers/\{customer_id\}"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /customers/{customer_id} handler not found"
        handler_body = match.group(1)
        has_overdue = (
            "overdue_count" in handler_body
            or "overdue" in handler_body.lower()
            or "просроч" in handler_body.lower()
        )
        assert has_overdue, (
            "Debt card must show overdue item count"
        )

    def test_debt_card_shows_last_payment_info(self):
        """Debt card must display last payment date/amount."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/customers/\{customer_id\}"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /customers/{customer_id} handler not found"
        handler_body = match.group(1)
        has_last_payment = (
            "last_payment" in handler_body
            or "Последний платёж" in handler_body
            or "Последняя оплата" in handler_body
        )
        assert has_last_payment, (
            "Debt card must display last payment information"
        )


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


class TestFinanceRouteAcceptsCustomerFilter:
    """The /finance route must accept customer_filter for linking from debt card."""

    def test_finance_route_accepts_customer_filter_param(self):
        """The /finance GET must accept customer_filter parameter."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance"\s*\)\s*\ndef get\((.*?)\):',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance handler signature not found"
        params = match.group(1)
        assert "customer_filter" in params, (
            'GET /finance must accept customer_filter param '
            '(used by debt card link: /finance?tab=payments&customer_filter={id})'
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
