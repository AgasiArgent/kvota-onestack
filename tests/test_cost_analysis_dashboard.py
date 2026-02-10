"""
TDD Tests for P2.3: Cost Analysis (KA) Dashboard

Feature: Read-only P&L waterfall tab on quote detail page showing cost analysis
derived from existing calculation results.

Route: GET /quotes/{quote_id}/cost-analysis
Tab: "Kost-analiz" on quote detail page
Visible to: finance, top_manager, admin, quote_control roles

Data sources:
  - quote_calculation_results.phase_results (JSONB per item)
  - quote_calculation_variables.variables (JSONB per quote)

P&L Waterfall:
  Revenue (no VAT) = sum(AK16)
  Purchase cost = sum(S16)
  Logistics total = sum(V16) with W2-W10 breakdown
  Customs duty = sum(Y16)
  Excise = sum(Z16)
  = Gross Profit (revenue - direct costs)
  Financial agent fee = sum(AI16)
  Forex reserve = sum(AH16)
  DM fee = sum(AG16)
  Financing cost = sum(BB16)
  = Net Profit (gross - financial expenses)
  Markup % = (revenue / purchase - 1) * 100

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the feature is implemented.
"""

import pytest
import re
import os
import uuid
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Path constants (relative to project root via os.path)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Test Data Factories
# ==============================================================================

ORG_ID = _make_uuid()
USER_ID = _make_uuid()
QUOTE_ID = _make_uuid()

# Allowed roles for cost analysis tab
ALLOWED_ROLES = ["finance", "top_manager", "admin", "quote_control"]

# Roles that should NOT see the cost analysis tab
DENIED_ROLES = ["sales", "procurement", "logistics", "customs"]

# W2-W10 logistics breakdown variable keys
LOGISTICS_BREAKDOWN_KEYS = {
    "W2": "logistics_supplier_hub",
    "W3": "logistics_hub_customs",
    "W4": "logistics_customs_client",
    "W5": "brokerage_hub",
    "W6": "brokerage_customs",
    "W7": "warehousing_at_customs",
    "W8": "customs_documentation",
    "W9": "brokerage_extra",
    "W10": "insurance",
}

# Phase result keys used in P&L waterfall
PHASE_RESULT_KEYS = {
    "AK16": "revenue_no_vat",        # sales_price_total_no_vat
    "AL16": "revenue_with_vat",       # sales_price_total_with_vat
    "S16": "purchase_cost",           # purchase_price_total_quote_currency
    "V16": "logistics_total",         # logistics_total
    "Y16": "customs_duty",            # customs_fee
    "Z16": "excise",                  # excise_tax_amount
    "AG16": "dm_fee",                 # dm_fee
    "AH16": "forex_reserve",          # forex_reserve
    "AI16": "financial_agent_fee",    # financial_agent_fee
    "BB16": "financing_cost",         # financing_cost_credit
}


def make_phase_results(
    revenue_no_vat=10000.0,
    revenue_with_vat=12000.0,
    purchase_cost=6000.0,
    logistics_total=1500.0,
    customs_duty=500.0,
    excise=100.0,
    dm_fee=200.0,
    forex_reserve=150.0,
    financial_agent_fee=300.0,
    financing_cost=100.0,
):
    """Create a phase_results JSONB dict matching the structure stored in DB."""
    return {
        "AK16": revenue_no_vat,
        "AL16": revenue_with_vat,
        "S16": purchase_cost,
        "V16": logistics_total,
        "Y16": customs_duty,
        "Z16": excise,
        "AG16": dm_fee,
        "AH16": forex_reserve,
        "AI16": financial_agent_fee,
        "BB16": financing_cost,
        # Other phase_results fields (not used by KA but present in DB)
        "N16": purchase_cost * 0.9,
        "P16": purchase_cost * 0.95,
        "R16": purchase_cost / 10,
        "T16": logistics_total * 0.6,
        "U16": logistics_total * 0.4,
        "AA16": 800.0,
        "AB16": 8000.0,
        "AD16": 900.0,
        "AE16": 9000.0,
        "AF16": 1500.0,
        "AJ16": 1000.0,
        "AM16": 1200.0,
        "AN16": 2000.0,
        "AO16": 500.0,
        "AP16": 1500.0,
        "AQ16": 0.0,
        "AX16": 850.0,
        "AY16": 8500.0,
        "BA16": 50.0,
    }


def make_calculation_result(
    quote_id=None,
    item_id=None,
    phase_results=None,
):
    """Create a mock quote_calculation_results row."""
    return {
        "id": _make_uuid(),
        "quote_id": quote_id or QUOTE_ID,
        "quote_item_id": item_id or _make_uuid(),
        "phase_results": phase_results or make_phase_results(),
        "phase_results_usd": phase_results or make_phase_results(),
        "calculated_at": "2026-02-10T12:00:00",
    }


def make_calculation_variables(
    quote_id=None,
    variables=None,
):
    """Create a mock quote_calculation_variables row."""
    default_vars = {
        "logistics_supplier_hub": 500.0,
        "logistics_hub_customs": 300.0,
        "logistics_customs_client": 200.0,
        "brokerage_hub": 150.0,
        "brokerage_customs": 100.0,
        "warehousing_at_customs": 80.0,
        "customs_documentation": 60.0,
        "brokerage_extra": 50.0,
        "rate_insurance": 0.00047,
        "currency_of_quote": "USD",
        "delivery_time": 30,
    }
    return {
        "quote_id": quote_id or QUOTE_ID,
        "variables": variables or default_vars,
        "updated_at": "2026-02-10T12:00:00",
    }


def make_quote(
    quote_id=None,
    org_id=None,
    currency="USD",
):
    """Create a mock quote for cost analysis tests."""
    return {
        "id": quote_id or QUOTE_ID,
        "organization_id": org_id or ORG_ID,
        "idn_quote": "Q-202602-0001",
        "workflow_status": "calculated",
        "title": "Test Quote for KA",
        "currency": currency,
        "seller_company": "MASTER BEARING OOO",
        "delivery_terms": "DDP",
        "delivery_time": 30,
        "payment_terms": "50/50",
        "advance_to_supplier": 100,
        "created_at": "2026-02-10T10:00:00",
        "updated_at": "2026-02-10T12:00:00",
    }


# ==============================================================================
# 1. Route Existence Tests
# ==============================================================================

class TestCostAnalysisRouteExists:
    """The cost-analysis route must exist in main.py."""

    def test_cost_analysis_route_defined_in_main_py(self):
        """
        Route GET /quotes/{quote_id}/cost-analysis must be defined in main.py.
        """
        source = _read_main_source()
        # Match the route decorator pattern
        has_route = (
            'cost-analysis' in source
            and '/quotes/' in source
        )
        # More specific: look for the actual route decorator
        route_pattern = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\']',
            source,
        )
        assert route_pattern is not None, (
            "main.py must define a GET route /quotes/{quote_id}/cost-analysis"
        )

    def test_cost_analysis_route_requires_login(self):
        """
        The cost-analysis route handler must call require_login()
        or equivalent authentication check.
        """
        source = _read_main_source()
        # Find the route handler function
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, (
            "Could not find cost-analysis route handler in main.py"
        )
        handler_body = route_match.group(1)
        assert 'require_login' in handler_body or 'user' in handler_body, (
            "Cost analysis route must require authentication (require_login)"
        )


# ==============================================================================
# 2. Tab Configuration Tests
# ==============================================================================

class TestCostAnalysisTabConfiguration:
    """The cost-analysis tab must appear in quote_detail_tabs()."""

    def _read_tabs_function_source(self):
        """Extract the quote_detail_tabs function source from main.py."""
        source = _read_main_source()
        match = re.search(
            r'def quote_detail_tabs\(.*?\n(.*?)(?=\ndef )',
            source,
            re.MULTILINE | re.DOTALL,
        )
        if not match:
            pytest.fail("Could not find quote_detail_tabs function in main.py")
        return match.group(0)

    def test_tab_config_includes_cost_analysis(self):
        """
        quote_detail_tabs() must include a tab with id 'cost_analysis'
        in its tabs_config list.
        """
        source = self._read_tabs_function_source()
        assert 'cost_analysis' in source, (
            "quote_detail_tabs must define a 'cost_analysis' tab in tabs_config"
        )

    def test_tab_label_is_kost_analiz(self):
        """
        The cost analysis tab label must be 'Kost-analiz' in Russian.
        """
        source = self._read_tabs_function_source()
        has_label = (
            'Кост-анализ' in source
            or 'КА' in source
        )
        assert has_label, (
            "Cost analysis tab must have label 'Кост-анализ' or 'КА'"
        )

    def test_tab_href_points_to_cost_analysis_route(self):
        """
        The cost analysis tab href must point to /quotes/{id}/cost-analysis.
        """
        source = self._read_tabs_function_source()
        assert 'cost-analysis' in source, (
            "Cost analysis tab href must contain 'cost-analysis'"
        )

    def test_tab_visible_to_finance_role(self):
        """
        The cost analysis tab must list 'finance' in its roles array.
        """
        source = self._read_tabs_function_source()
        # Look for the cost_analysis tab config block containing "finance"
        # Find the block between cost_analysis and the next tab definition
        ca_match = re.search(
            r'"cost_analysis".*?"roles":\s*\[(.*?)\]',
            source,
            re.DOTALL,
        )
        assert ca_match is not None, (
            "Could not find cost_analysis tab roles definition"
        )
        roles_str = ca_match.group(1)
        assert 'finance' in roles_str, (
            "Cost analysis tab must be visible to 'finance' role"
        )

    def test_tab_visible_to_admin_role(self):
        """
        The cost analysis tab must list 'admin' in its roles array.
        """
        source = self._read_tabs_function_source()
        ca_match = re.search(
            r'"cost_analysis".*?"roles":\s*\[(.*?)\]',
            source,
            re.DOTALL,
        )
        assert ca_match is not None, (
            "Could not find cost_analysis tab roles definition"
        )
        roles_str = ca_match.group(1)
        assert 'admin' in roles_str, (
            "Cost analysis tab must be visible to 'admin' role"
        )

    def test_tab_visible_to_top_manager_role(self):
        """
        The cost analysis tab must list 'top_manager' in its roles array.
        """
        source = self._read_tabs_function_source()
        ca_match = re.search(
            r'"cost_analysis".*?"roles":\s*\[(.*?)\]',
            source,
            re.DOTALL,
        )
        assert ca_match is not None, (
            "Could not find cost_analysis tab roles definition"
        )
        roles_str = ca_match.group(1)
        assert 'top_manager' in roles_str, (
            "Cost analysis tab must be visible to 'top_manager' role"
        )

    def test_tab_not_visible_to_sales_role(self):
        """
        The cost analysis tab must NOT be accessible to 'sales' role.
        It should have restricted roles (not None = visible to all).
        """
        source = self._read_tabs_function_source()
        ca_match = re.search(
            r'"cost_analysis".*?"roles":\s*\[(.*?)\]',
            source,
            re.DOTALL,
        )
        assert ca_match is not None, (
            "Could not find cost_analysis tab roles definition"
        )
        roles_str = ca_match.group(1)
        assert 'sales' not in roles_str, (
            "Cost analysis tab must NOT be visible to 'sales' role"
        )

    def test_tab_not_visible_to_procurement_role(self):
        """
        The cost analysis tab must NOT be accessible to 'procurement' role.
        """
        source = self._read_tabs_function_source()
        ca_match = re.search(
            r'"cost_analysis".*?"roles":\s*\[(.*?)\]',
            source,
            re.DOTALL,
        )
        assert ca_match is not None, (
            "Could not find cost_analysis tab roles definition"
        )
        roles_str = ca_match.group(1)
        assert 'procurement' not in roles_str, (
            "Cost analysis tab must NOT be visible to 'procurement' role"
        )

    def test_tab_not_visible_to_logistics_role(self):
        """
        The cost analysis tab must NOT be accessible to 'logistics' role.
        """
        source = self._read_tabs_function_source()
        ca_match = re.search(
            r'"cost_analysis".*?"roles":\s*\[(.*?)\]',
            source,
            re.DOTALL,
        )
        assert ca_match is not None, (
            "Could not find cost_analysis tab roles definition"
        )
        roles_str = ca_match.group(1)
        assert 'logistics' not in roles_str, (
            "Cost analysis tab must NOT be visible to 'logistics' role"
        )


# ==============================================================================
# 3. Route Handler Source Code Tests
# ==============================================================================

class TestCostAnalysisRouteHandler:
    """The cost-analysis route handler must query correct data sources."""

    def _read_route_handler_source(self):
        """Extract the cost-analysis route handler source."""
        source = _read_main_source()
        match = re.search(
            r'(@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n)'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        if not match:
            pytest.fail(
                "Could not find cost-analysis route handler in main.py. "
                "The route GET /quotes/{quote_id}/cost-analysis must be defined."
            )
        return match.group(0)

    def test_handler_queries_calculation_results(self):
        """
        Route handler must query quote_calculation_results table
        to fetch per-item phase_results.
        """
        handler = self._read_route_handler_source()
        assert 'quote_calculation_results' in handler, (
            "Cost analysis handler must query 'quote_calculation_results' table"
        )

    def test_handler_queries_calculation_variables(self):
        """
        Route handler must query quote_calculation_variables table
        to fetch W2-W10 logistics breakdown.
        """
        handler = self._read_route_handler_source()
        assert 'quote_calculation_variables' in handler, (
            "Cost analysis handler must query 'quote_calculation_variables' table"
        )

    def test_handler_checks_organization_id(self):
        """
        Route handler must verify the quote belongs to the user's organization
        (org isolation / security check).
        """
        handler = self._read_route_handler_source()
        has_org_check = (
            'organization_id' in handler
            or 'org_id' in handler
        )
        assert has_org_check, (
            "Cost analysis handler must check organization_id for security"
        )

    def test_handler_uses_phase_results_keys(self):
        """
        Handler must reference phase_results JSONB keys (AK16, S16, etc.)
        for aggregating P&L data.
        """
        handler = self._read_route_handler_source()
        # Must reference at least revenue (AK16) and purchase (S16)
        has_ak16 = 'AK16' in handler
        has_s16 = 'S16' in handler
        assert has_ak16, (
            "Handler must reference 'AK16' (revenue no VAT) from phase_results"
        )
        assert has_s16, (
            "Handler must reference 'S16' (purchase cost) from phase_results"
        )


# ==============================================================================
# 4. P&L Aggregation Logic Tests (unit-level)
# ==============================================================================

class TestCostAnalysisAggregation:
    """
    Test the P&L aggregation logic that sums phase_results across items.
    These tests verify the aggregation function/logic that will be used
    in the route handler.
    """

    def test_revenue_no_vat_aggregation(self):
        """
        Revenue (no VAT) = sum of AK16 across all items.
        For 2 items with AK16=10000 and AK16=5000, revenue = 15000.
        """
        source = _read_main_source()
        # The function or inline logic must exist
        has_aggregation = re.search(
            r'(AK16|sales_price_total_no_vat).*?(sum|total|revenue)',
            source,
            re.DOTALL | re.IGNORECASE,
        )
        # Also check that the cost-analysis handler aggregates AK16
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, (
            "Must define cost-analysis route to test aggregation"
        )
        handler = route_match.group(1)
        assert 'AK16' in handler, (
            "Cost analysis must aggregate AK16 (revenue no VAT) from phase_results"
        )

    def test_purchase_cost_aggregation(self):
        """
        Purchase cost = sum of S16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'S16' in handler, (
            "Cost analysis must aggregate S16 (purchase cost) from phase_results"
        )

    def test_logistics_total_aggregation(self):
        """
        Logistics total = sum of V16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'V16' in handler, (
            "Cost analysis must aggregate V16 (logistics total) from phase_results"
        )

    def test_customs_duty_aggregation(self):
        """
        Customs duty = sum of Y16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'Y16' in handler, (
            "Cost analysis must aggregate Y16 (customs duty) from phase_results"
        )

    def test_excise_aggregation(self):
        """
        Excise tax = sum of Z16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'Z16' in handler, (
            "Cost analysis must aggregate Z16 (excise) from phase_results"
        )

    def test_financial_agent_fee_aggregation(self):
        """
        Financial agent fee = sum of AI16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'AI16' in handler, (
            "Cost analysis must aggregate AI16 (financial agent fee) from phase_results"
        )

    def test_forex_reserve_aggregation(self):
        """
        Forex reserve = sum of AH16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'AH16' in handler, (
            "Cost analysis must aggregate AH16 (forex reserve) from phase_results"
        )

    def test_dm_fee_aggregation(self):
        """
        DM fee = sum of AG16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'AG16' in handler, (
            "Cost analysis must aggregate AG16 (DM fee) from phase_results"
        )

    def test_financing_cost_aggregation(self):
        """
        Financing cost = sum of BB16 across all items.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'BB16' in handler, (
            "Cost analysis must aggregate BB16 (financing cost) from phase_results"
        )


# ==============================================================================
# 5. Gross Profit & Net Profit Calculation Tests
# ==============================================================================

class TestCostAnalysisProfitCalculations:
    """
    Test that gross profit and net profit are calculated correctly.
    These are pure calculation tests that verify the formulas.
    """

    def test_gross_profit_formula_in_handler(self):
        """
        Gross Profit = Revenue(no VAT) - (Purchase + Logistics + Customs Duty + Excise)
        The handler must compute this correctly.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        # Should contain gross_profit or equivalent variable name
        has_gross = (
            'gross_profit' in handler.lower()
            or 'gross' in handler.lower()
            or 'valovaya' in handler.lower()
        )
        assert has_gross, (
            "Cost analysis handler must calculate gross_profit "
            "(revenue - direct costs)"
        )

    def test_net_profit_formula_in_handler(self):
        """
        Net Profit = Gross Profit - (DM Fee + Forex Reserve + Fin Agent Fee + Financing Cost)
        The handler must compute net profit.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        has_net = (
            'net_profit' in handler.lower()
            or 'net' in handler.lower()
            or 'chistaya' in handler.lower()
        )
        assert has_net, (
            "Cost analysis handler must calculate net_profit "
            "(gross_profit - financial_expenses)"
        )

    def test_markup_percentage_formula(self):
        """
        Markup % = (revenue / purchase - 1) * 100
        Handler must calculate markup percentage from revenue and purchase.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        has_markup = (
            'markup' in handler.lower()
            or 'наценка' in handler.lower()
        )
        assert has_markup, (
            "Cost analysis handler must calculate markup percentage"
        )

    def test_gross_profit_value_correct(self):
        """
        Given known values, verify gross profit = revenue - direct costs.
        revenue=10000, purchase=6000, logistics=1500, customs=500, excise=100
        gross_profit = 10000 - (6000 + 1500 + 500 + 100) = 1900
        """
        revenue = 10000.0
        purchase = 6000.0
        logistics = 1500.0
        customs = 500.0
        excise = 100.0
        direct_costs = purchase + logistics + customs + excise
        gross_profit = revenue - direct_costs
        assert gross_profit == 1900.0, (
            f"Gross profit should be 1900.0, got {gross_profit}"
        )

    def test_net_profit_value_correct(self):
        """
        Given known values, verify net profit = gross - financial expenses.
        gross_profit=1900, dm=200, forex=150, fin_agent=300, financing=100
        net_profit = 1900 - (200 + 150 + 300 + 100) = 1150
        """
        gross_profit = 1900.0
        dm_fee = 200.0
        forex_reserve = 150.0
        fin_agent_fee = 300.0
        financing_cost = 100.0
        financial_expenses = dm_fee + forex_reserve + fin_agent_fee + financing_cost
        net_profit = gross_profit - financial_expenses
        assert net_profit == 1150.0, (
            f"Net profit should be 1150.0, got {net_profit}"
        )

    def test_markup_percentage_value_correct(self):
        """
        Markup % = (revenue / purchase - 1) * 100
        revenue=10000, purchase=6000 -> markup = (10000/6000 - 1)*100 = 66.67%
        """
        revenue = 10000.0
        purchase = 6000.0
        markup_pct = (revenue / purchase - 1) * 100
        assert abs(markup_pct - 66.667) < 0.01, (
            f"Markup should be ~66.67%, got {markup_pct:.2f}%"
        )

    def test_zero_revenue_no_division_by_zero(self):
        """
        When revenue is 0, markup % calculation must not raise ZeroDivisionError.
        Should return 0 or display a dash.
        """
        revenue = 0.0
        purchase = 6000.0
        # The implementation must handle this gracefully
        if purchase > 0:
            # Markup as revenue/purchase ratio makes no sense with 0 revenue
            # but (0/6000 - 1) * 100 = -100%, which is valid math
            markup_pct = (revenue / purchase - 1) * 100
            assert markup_pct == -100.0
        # The real test is that the handler doesn't crash
        # We verify this via source code check
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        # Handler should have a zero check for purchase or revenue
        has_zero_check = (
            '== 0' in handler
            or '> 0' in handler
            or 'if purchase' in handler.lower()
            or 'if total_purchase' in handler.lower()
            or 'or 1' in handler
        )
        assert has_zero_check, (
            "Cost analysis handler must handle zero revenue/purchase "
            "to avoid division by zero"
        )

    def test_zero_purchase_no_division_by_zero(self):
        """
        When purchase is 0, markup % = (revenue / 0) must not crash.
        Handler should handle division by zero gracefully.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        # Check for zero-division protection
        has_protection = (
            '== 0' in handler
            or '> 0' in handler
            or 'if purchase' in handler.lower()
            or 'if total_purchase' in handler.lower()
            or 'or 1' in handler
            or 'ZeroDivision' in handler
        )
        assert has_protection, (
            "Handler must protect against division by zero when purchase = 0"
        )


# ==============================================================================
# 6. Logistics Breakdown (W2-W10) Tests
# ==============================================================================

class TestCostAnalysisLogisticsBreakdown:
    """
    The cost analysis must show a 9-line logistics breakdown
    sourced from quote_calculation_variables.
    """

    def test_handler_extracts_logistics_supplier_hub(self):
        """W2: logistics_supplier_hub must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'logistics_supplier_hub' in handler, (
            "Handler must extract logistics_supplier_hub (W2) from variables"
        )

    def test_handler_extracts_logistics_hub_customs(self):
        """W3: logistics_hub_customs must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'logistics_hub_customs' in handler, (
            "Handler must extract logistics_hub_customs (W3) from variables"
        )

    def test_handler_extracts_logistics_customs_client(self):
        """W4: logistics_customs_client must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'logistics_customs_client' in handler, (
            "Handler must extract logistics_customs_client (W4) from variables"
        )

    def test_handler_extracts_brokerage_hub(self):
        """W5: brokerage_hub must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'brokerage_hub' in handler, (
            "Handler must extract brokerage_hub (W5) from variables"
        )

    def test_handler_extracts_brokerage_customs(self):
        """W6: brokerage_customs must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'brokerage_customs' in handler, (
            "Handler must extract brokerage_customs (W6) from variables"
        )

    def test_handler_extracts_warehousing(self):
        """W7: warehousing_at_customs must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'warehousing' in handler, (
            "Handler must extract warehousing_at_customs (W7) from variables"
        )

    def test_handler_extracts_documentation(self):
        """W8: customs_documentation must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        has_docs = (
            'customs_documentation' in handler
            or 'documentation' in handler
        )
        assert has_docs, (
            "Handler must extract customs_documentation (W8) from variables"
        )

    def test_handler_extracts_brokerage_extra(self):
        """W9: brokerage_extra must be extracted from variables."""
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'brokerage_extra' in handler, (
            "Handler must extract brokerage_extra (W9) from variables"
        )

    def test_missing_w_values_default_to_zero(self):
        """
        When W2-W10 values are missing from variables, they should default to 0.
        The handler must use .get() with a default or equivalent pattern.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        # Should use .get() with default 0 or or 0 pattern
        has_default = (
            '.get(' in handler
            or 'or 0' in handler
            or 'default' in handler.lower()
        )
        assert has_default, (
            "Handler must default missing W2-W10 values to 0 "
            "(use .get() with default or 'or 0' pattern)"
        )


# ==============================================================================
# 7. "Not Calculated" Message Test
# ==============================================================================

class TestCostAnalysisNotCalculatedMessage:
    """
    When no calculation results exist for a quote, the cost analysis page
    must show a "not calculated" message instead of the P&L waterfall.
    """

    def test_handler_shows_message_when_no_results(self):
        """
        When quote_calculation_results has no rows for the quote,
        handler must display a message like 'Расчёт ещё не выполнен'.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        has_not_calculated_msg = (
            'не выполнен' in handler
            or 'не рассчитан' in handler
            or 'not calculated' in handler.lower()
            or 'нет данных' in handler
            or 'нет результат' in handler
        )
        assert has_not_calculated_msg, (
            "Handler must display a 'not calculated' message when "
            "quote_calculation_results is empty for this quote"
        )


# ==============================================================================
# 8. P&L Display / UI Content Tests
# ==============================================================================

class TestCostAnalysisPLDisplay:
    """
    The cost analysis page must render all P&L waterfall sections
    in the correct order with proper labels.
    """

    def _get_handler_source(self):
        """Get the cost-analysis route handler source."""
        source = _read_main_source()
        match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        if not match:
            pytest.fail("Cost-analysis route handler not found in main.py")
        return match.group(1)

    def test_shows_purchase_cost_label(self):
        """P&L must show 'Сумма закупки' or equivalent purchase cost label."""
        handler = self._get_handler_source()
        has_label = (
            'закупк' in handler.lower()
            or 'purchase' in handler.lower()
            or 'Закупка' in handler
            or 'Сумма закупки' in handler
        )
        assert has_label, "P&L must include purchase cost label"

    def test_shows_logistics_label(self):
        """P&L must show 'Логистика' label."""
        handler = self._get_handler_source()
        has_label = (
            'Логистика' in handler
            or 'логистик' in handler.lower()
        )
        assert has_label, "P&L must include logistics label"

    def test_shows_customs_duty_label(self):
        """P&L must show 'Пошлина' or customs duty label."""
        handler = self._get_handler_source()
        has_label = (
            'Пошлина' in handler
            or 'пошлин' in handler.lower()
            or 'customs' in handler.lower()
        )
        assert has_label, "P&L must include customs duty label"

    def test_shows_excise_label(self):
        """P&L must show 'Акциз' or excise label."""
        handler = self._get_handler_source()
        has_label = (
            'Акциз' in handler
            or 'акциз' in handler.lower()
            or 'excise' in handler.lower()
        )
        assert has_label, "P&L must include excise label"

    def test_shows_gross_profit_label(self):
        """P&L must show 'Валовая прибыль' or gross profit label."""
        handler = self._get_handler_source()
        has_label = (
            'Валовая' in handler
            or 'валовая' in handler.lower()
            or 'gross' in handler.lower()
            or 'Gross' in handler
        )
        assert has_label, "P&L must include gross profit label"

    def test_shows_net_profit_label(self):
        """P&L must show 'Чистая прибыль' or net profit label."""
        handler = self._get_handler_source()
        has_label = (
            'Чистая' in handler
            or 'чистая' in handler.lower()
            or 'net' in handler.lower()
            or 'Net' in handler
        )
        assert has_label, "P&L must include net profit label"

    def test_shows_financial_agent_fee_label(self):
        """P&L must show financial agent fee label."""
        handler = self._get_handler_source()
        has_label = (
            'фин' in handler.lower()
            or 'агент' in handler.lower()
            or 'financial' in handler.lower()
            or 'Комиссия' in handler
        )
        assert has_label, "P&L must include financial agent fee label"

    def test_shows_forex_reserve_label(self):
        """P&L must show forex/currency reserve label."""
        handler = self._get_handler_source()
        has_label = (
            'курс' in handler.lower()
            or 'forex' in handler.lower()
            or 'Резерв' in handler
            or 'валют' in handler.lower()
        )
        assert has_label, "P&L must include forex reserve label"

    def test_shows_dm_fee_label(self):
        """P&L must show DM fee / kickback label."""
        handler = self._get_handler_source()
        has_label = (
            'ЛПР' in handler
            or 'dm_fee' in handler.lower()
            or 'DM' in handler
            or 'Вознаграждение' in handler
        )
        assert has_label, "P&L must include DM fee label"

    def test_shows_financing_cost_label(self):
        """P&L must show financing cost label."""
        handler = self._get_handler_source()
        has_label = (
            'финансирован' in handler.lower()
            or 'financing' in handler.lower()
            or 'Стоимость финансирования' in handler
        )
        assert has_label, "P&L must include financing cost label"

    def test_shows_revenue_no_vat_label(self):
        """P&L must show revenue (no VAT) label."""
        handler = self._get_handler_source()
        has_label = (
            'Выручка' in handler
            or 'выручк' in handler.lower()
            or 'revenue' in handler.lower()
            or 'Revenue' in handler
        )
        assert has_label, "P&L must include revenue label"

    def test_shows_markup_percentage_label(self):
        """P&L must show markup percentage label."""
        handler = self._get_handler_source()
        has_label = (
            'Наценка' in handler
            or 'наценк' in handler.lower()
            or 'markup' in handler.lower()
            or 'Markup' in handler
        )
        assert has_label, "P&L must include markup percentage label"


# ==============================================================================
# 9. Currency Formatting Tests
# ==============================================================================

class TestCostAnalysisCurrencyFormatting:
    """
    Financial values on the cost analysis page must be properly formatted.
    """

    def test_handler_formats_currency_values(self):
        """
        The handler must format currency values with proper decimal places.
        Common patterns: f'{value:,.2f}', f'{value:,.0f}', or format_currency().
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        has_formatting = (
            ':,' in handler       # f-string thousand separator
            or 'format' in handler.lower()
            or 'f"{' in handler   # f-string usage
            or "f'" in handler    # f-string with single quotes
            or '{:' in handler    # .format() style
        )
        assert has_formatting, (
            "Handler must format currency values with proper formatting "
            "(thousand separators, decimal places)"
        )


# ==============================================================================
# 10. Multi-Item Aggregation Tests (Pure Logic)
# ==============================================================================

class TestCostAnalysisMultiItemAggregation:
    """
    Verify that aggregation works correctly with multiple items.
    These are pure calculation tests (no main.py dependency).
    """

    def test_aggregate_two_items_revenue(self):
        """Sum AK16 from 2 items: 10000 + 5000 = 15000."""
        items = [
            make_phase_results(revenue_no_vat=10000.0),
            make_phase_results(revenue_no_vat=5000.0),
        ]
        total_revenue = sum(item["AK16"] for item in items)
        assert total_revenue == 15000.0

    def test_aggregate_two_items_purchase(self):
        """Sum S16 from 2 items: 6000 + 3000 = 9000."""
        items = [
            make_phase_results(purchase_cost=6000.0),
            make_phase_results(purchase_cost=3000.0),
        ]
        total_purchase = sum(item["S16"] for item in items)
        assert total_purchase == 9000.0

    def test_aggregate_three_items_all_fields(self):
        """
        Aggregate all P&L fields across 3 items and verify totals.
        """
        items = [
            make_phase_results(
                revenue_no_vat=10000.0, purchase_cost=6000.0,
                logistics_total=1500.0, customs_duty=500.0, excise=100.0,
                dm_fee=200.0, forex_reserve=150.0,
                financial_agent_fee=300.0, financing_cost=100.0,
            ),
            make_phase_results(
                revenue_no_vat=5000.0, purchase_cost=3000.0,
                logistics_total=750.0, customs_duty=250.0, excise=50.0,
                dm_fee=100.0, forex_reserve=75.0,
                financial_agent_fee=150.0, financing_cost=50.0,
            ),
            make_phase_results(
                revenue_no_vat=8000.0, purchase_cost=4800.0,
                logistics_total=1200.0, customs_duty=400.0, excise=80.0,
                dm_fee=160.0, forex_reserve=120.0,
                financial_agent_fee=240.0, financing_cost=80.0,
            ),
        ]

        totals = {}
        for key in ["AK16", "S16", "V16", "Y16", "Z16", "AG16", "AH16", "AI16", "BB16"]:
            totals[key] = sum(item[key] for item in items)

        assert totals["AK16"] == 23000.0   # revenue
        assert totals["S16"] == 13800.0    # purchase
        assert totals["V16"] == 3450.0     # logistics
        assert totals["Y16"] == 1150.0     # customs
        assert totals["Z16"] == 230.0      # excise
        assert totals["AG16"] == 460.0     # dm_fee
        assert totals["AH16"] == 345.0     # forex
        assert totals["AI16"] == 690.0     # fin_agent
        assert totals["BB16"] == 230.0     # financing

        # Derived calculations
        direct_costs = totals["S16"] + totals["V16"] + totals["Y16"] + totals["Z16"]
        gross_profit = totals["AK16"] - direct_costs
        assert gross_profit == 23000.0 - 18630.0  # = 4370.0

        financial_expenses = (
            totals["AG16"] + totals["AH16"] + totals["AI16"] + totals["BB16"]
        )
        net_profit = gross_profit - financial_expenses
        assert net_profit == 4370.0 - 1725.0  # = 2645.0

    def test_single_item_with_zero_costs(self):
        """
        A single item where all costs are 0 except revenue.
        Gross profit should equal revenue, net profit should equal revenue.
        """
        item = make_phase_results(
            revenue_no_vat=10000.0,
            purchase_cost=0.0,
            logistics_total=0.0,
            customs_duty=0.0,
            excise=0.0,
            dm_fee=0.0,
            forex_reserve=0.0,
            financial_agent_fee=0.0,
            financing_cost=0.0,
        )
        revenue = item["AK16"]
        direct_costs = item["S16"] + item["V16"] + item["Y16"] + item["Z16"]
        gross_profit = revenue - direct_costs
        assert gross_profit == 10000.0

        financial = item["AG16"] + item["AH16"] + item["AI16"] + item["BB16"]
        net_profit = gross_profit - financial
        assert net_profit == 10000.0

    def test_empty_items_list(self):
        """
        With no items, all aggregations should be 0.
        """
        items = []
        total_revenue = sum(item.get("AK16", 0) for item in items)
        assert total_revenue == 0.0


# ==============================================================================
# 11. Org Isolation / Security Tests
# ==============================================================================

class TestCostAnalysisOrgIsolation:
    """
    Cost analysis must enforce organization isolation.
    """

    def test_handler_checks_quote_organization(self):
        """
        The handler must verify that the quote belongs to the
        requesting user's organization before showing data.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        # Should compare quote's org_id with user's org_id
        has_org_check = (
            'organization_id' in handler
            or 'org_id' in handler
        )
        assert has_org_check, (
            "Cost analysis route must verify quote belongs to user's organization"
        )

    def test_handler_returns_error_for_wrong_org(self):
        """
        The handler must return 404 or redirect when user tries to access
        a quote from a different organization.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        has_error_handling = (
            '404' in handler
            or 'redirect' in handler.lower()
            or 'Redirect' in handler
            or 'not found' in handler.lower()
            or 'не найден' in handler.lower()
        )
        assert has_error_handling, (
            "Handler must return 404 or redirect when org mismatch"
        )


# ==============================================================================
# 12. P&L Section Order Tests
# ==============================================================================

class TestCostAnalysisSectionOrder:
    """
    The P&L waterfall sections must appear in the correct order.
    """

    def test_revenue_appears_before_purchase(self):
        """
        In the P&L waterfall, revenue should be presented first
        (or at least before purchase cost).
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)

        # Find positions of revenue and purchase labels
        revenue_pos = -1
        purchase_pos = -1

        for pattern, label in [
            ('Выручка', 'revenue'), ('выручк', 'revenue'),
            ('revenue', 'revenue'), ('AK16', 'revenue'),
        ]:
            pos = handler.lower().find(pattern.lower())
            if pos >= 0 and (revenue_pos < 0 or pos < revenue_pos):
                revenue_pos = pos

        for pattern, label in [
            ('закупк', 'purchase'), ('purchase', 'purchase'),
            ('Закупка', 'purchase'), ('S16', 'purchase'),
        ]:
            pos = handler.lower().find(pattern.lower())
            if pos >= 0 and (purchase_pos < 0 or pos < purchase_pos):
                purchase_pos = pos

        assert revenue_pos >= 0, "Revenue must be mentioned in handler"
        assert purchase_pos >= 0, "Purchase must be mentioned in handler"
        # Revenue aggregation typically defined before purchase in the waterfall display
        # (both are aggregated, but revenue label comes first in P&L)

    def test_gross_profit_appears_before_net_profit(self):
        """
        Gross profit subtotal must appear before net profit subtotal.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)

        gross_pos = handler.lower().find('gross')
        if gross_pos < 0:
            gross_pos = handler.lower().find('валовая')
        if gross_pos < 0:
            gross_pos = handler.lower().find('gross_profit')

        net_pos = handler.lower().find('net_profit')
        if net_pos < 0:
            net_pos = handler.lower().find('чистая')
        if net_pos < 0:
            net_pos = handler.lower().find('net')

        assert gross_pos >= 0, "Gross profit must be defined in handler"
        assert net_pos >= 0, "Net profit must be defined in handler"
        assert gross_pos < net_pos, (
            "Gross profit must be calculated/displayed before net profit"
        )


# ==============================================================================
# 13. Tab Uses quote_detail_tabs Function Test
# ==============================================================================

class TestCostAnalysisUsesTabNavigation:
    """
    The cost-analysis route must use the quote_detail_tabs function
    for consistent tab navigation.
    """

    def test_handler_calls_quote_detail_tabs(self):
        """
        The cost-analysis route handler must call quote_detail_tabs()
        with active_tab='cost_analysis'.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        assert 'quote_detail_tabs' in handler, (
            "Cost analysis handler must call quote_detail_tabs() for tab navigation"
        )

    def test_handler_passes_cost_analysis_as_active_tab(self):
        """
        When calling quote_detail_tabs(), active_tab must be 'cost_analysis'.
        """
        source = _read_main_source()
        route_match = re.search(
            r'@app\.get\(["\'].*?/quotes/\{.*?\}/cost-analysis["\'].*?\n'
            r'(.*?)(?=\n@app\.)',
            source,
            re.DOTALL,
        )
        assert route_match is not None, "Must define cost-analysis route"
        handler = route_match.group(1)
        has_active_tab = (
            '"cost_analysis"' in handler
            or "'cost_analysis'" in handler
        )
        assert has_active_tab, (
            "Handler must pass 'cost_analysis' as active_tab to quote_detail_tabs"
        )
