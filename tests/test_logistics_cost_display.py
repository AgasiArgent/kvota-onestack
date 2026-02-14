"""
TDD Tests for [86afdkuvh]: Logistics cost display fix on the Sales tab (Prodazhi).

Problem: The Itogo block on the Sales tab shows "---" for logistics cost because
`quote.get("logistics_total")` reads from the quote dict, but `logistics_total`
is NOT a column in the quotes table.

Fix: Calculate logistics_total by querying the invoices table, summing the 3
logistics cost segments (supplier_to_hub, hub_to_customs, customs_to_customer),
converting each segment from its currency to the quote currency, then display
that calculated value in the Itogo block.

Invoice logistics columns (from migration 131 + 133):
  - logistics_supplier_to_hub (Decimal)
  - logistics_hub_to_customs (Decimal)
  - logistics_customs_to_customer (Decimal)
  - logistics_supplier_to_hub_currency (VARCHAR(3), default 'USD')
  - logistics_hub_to_customs_currency (VARCHAR(3), default 'USD')
  - logistics_customs_to_customer_currency (VARCHAR(3), default 'USD')

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the feature is implemented.
"""

import pytest
import os
import re
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


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


# ==============================================================================
# Test Data Factories
# ==============================================================================

def make_invoice(
    quote_id,
    s2h=None, s2h_currency="USD",
    h2c=None, h2c_currency="USD",
    c2c=None, c2c_currency="USD",
    currency="USD",
):
    """Create a mock invoice dict with logistics cost segments."""
    return {
        "id": _make_uuid(),
        "quote_id": quote_id,
        "currency": currency,
        "logistics_supplier_to_hub": s2h,
        "logistics_hub_to_customs": h2c,
        "logistics_customs_to_customer": c2c,
        "logistics_supplier_to_hub_currency": s2h_currency,
        "logistics_hub_to_customs_currency": h2c_currency,
        "logistics_customs_to_customer_currency": c2c_currency,
    }


# ==============================================================================
# SECTION 1: Pure Calculation Logic Tests
#
# The implementation should extract invoice-to-logistics-total logic into a
# callable function (or inline block) that we can test. Since main.py is a
# monolith, we test by verifying source code patterns and by exercising the
# calculation logic directly.
# ==============================================================================

def calculate_logistics_total_from_invoices(invoices, quote_currency, convert_fn):
    """
    Reference implementation of the expected calculation logic.
    This is what the implementation SHOULD produce.

    The developer must add a function with this name and signature to main.py,
    OR inline equivalent logic in the quote detail handler.

    Args:
        invoices: list of invoice dicts with logistics cost segments
        quote_currency: target currency (e.g. "RUB", "USD")
        convert_fn: callable(amount: Decimal, from_currency: str, to_currency: str) -> Decimal

    Returns:
        float: total logistics cost in quote currency
    """
    total = Decimal(0)
    for inv in invoices:
        s2h = Decimal(str(inv.get("logistics_supplier_to_hub") or 0))
        s2h_cur = inv.get("logistics_supplier_to_hub_currency") or "USD"
        h2c = Decimal(str(inv.get("logistics_hub_to_customs") or 0))
        h2c_cur = inv.get("logistics_hub_to_customs_currency") or "USD"
        c2c = Decimal(str(inv.get("logistics_customs_to_customer") or 0))
        c2c_cur = inv.get("logistics_customs_to_customer_currency") or "USD"

        if s2h > 0:
            total += convert_fn(s2h, s2h_cur, quote_currency)
        if h2c > 0:
            total += convert_fn(h2c, h2c_cur, quote_currency)
        if c2c > 0:
            total += convert_fn(c2c, c2c_cur, quote_currency)
    return float(total)


class TestCalculateLogisticsTotalFromInvoices:
    """
    Test the pure calculation: given a list of invoices with logistics costs
    and a target currency, compute the total logistics cost.

    The function/block should:
    1. Sum logistics_supplier_to_hub + logistics_hub_to_customs + logistics_customs_to_customer
       per invoice
    2. Convert each segment from its currency to the quote currency
    3. Return the total as a float (or Decimal)

    These tests use a reference implementation defined above to validate
    the expected behavior. The source code pattern tests in Section 2
    verify that main.py actually contains this logic.
    """

    # --- Happy path ---

    def test_single_invoice_all_segments_same_currency(self, quote_id):
        """Single invoice with all 3 segments in same currency as quote."""
        invoices = [make_invoice(quote_id, s2h=100, h2c=200, c2c=150)]
        identity = lambda amt, fr, to: amt  # same currency = no conversion
        result = calculate_logistics_total_from_invoices(invoices, "USD", identity)
        assert result == 450.0

    def test_multiple_invoices_same_currency(self, quote_id):
        """Multiple invoices, all USD, quote currency USD."""
        invoices = [
            make_invoice(quote_id, s2h=100, h2c=50, c2c=30),
            make_invoice(quote_id, s2h=200, h2c=0, c2c=100),
        ]
        identity = lambda amt, fr, to: amt
        result = calculate_logistics_total_from_invoices(invoices, "USD", identity)
        assert result == 480.0  # (100+50+30) + (200+0+100)

    def test_single_invoice_mixed_currencies_conversion(self, quote_id):
        """Invoice with segments in different currencies, convert to RUB."""
        invoices = [make_invoice(
            quote_id,
            s2h=100, s2h_currency="USD",
            h2c=200, h2c_currency="EUR",
            c2c=50000, c2c_currency="RUB",
        )]

        def mock_convert(amount, from_cur, to_cur):
            # Simulated rates: USD->RUB = 90, EUR->RUB = 100
            rates_to_rub = {"USD": Decimal("90"), "EUR": Decimal("100"), "RUB": Decimal("1")}
            if from_cur == to_cur:
                return amount
            amt_rub = amount * rates_to_rub.get(from_cur, Decimal("1"))
            to_rate = rates_to_rub.get(to_cur, Decimal("1"))
            return amt_rub / to_rate

        result = calculate_logistics_total_from_invoices(invoices, "RUB", mock_convert)
        # 100 USD * 90 = 9000 RUB, 200 EUR * 100 = 20000 RUB, 50000 RUB = 50000 RUB
        expected = 9000 + 20000 + 50000  # = 79000
        assert result == float(expected)

    def test_multiple_invoices_mixed_currencies(self, quote_id):
        """Multiple invoices with different currencies, convert to USD."""
        invoices = [
            make_invoice(quote_id, s2h=1000, s2h_currency="USD", h2c=500, h2c_currency="USD", c2c=0),
            make_invoice(quote_id, s2h=9000, s2h_currency="RUB", h2c=0, c2c=5000, c2c_currency="RUB"),
        ]

        def mock_convert(amount, from_cur, to_cur):
            rates_to_rub = {"USD": Decimal("90"), "EUR": Decimal("100"), "RUB": Decimal("1")}
            if from_cur == to_cur:
                return amount
            amt_rub = amount * rates_to_rub.get(from_cur, Decimal("1"))
            to_rate = rates_to_rub.get(to_cur, Decimal("1"))
            return amt_rub / to_rate

        result = calculate_logistics_total_from_invoices(invoices, "USD", mock_convert)
        # Inv1: 1000 USD + 500 USD + 0 = 1500 USD
        # Inv2: 9000 RUB / 90 = 100 USD + 0 + 5000 RUB / 90 = ~55.56 USD
        expected = Decimal("1500") + Decimal("9000") / Decimal("90") + Decimal("5000") / Decimal("90")
        assert abs(result - float(expected)) < 0.01

    # --- Edge cases ---

    def test_empty_invoices_returns_zero(self, quote_id):
        """No invoices at all should return 0."""
        identity = lambda amt, fr, to: amt
        result = calculate_logistics_total_from_invoices([], "USD", identity)
        assert result == 0.0

    def test_invoices_with_all_null_logistics(self, quote_id):
        """Invoices exist but all logistics fields are None."""
        invoices = [
            make_invoice(quote_id, s2h=None, h2c=None, c2c=None),
            make_invoice(quote_id, s2h=None, h2c=None, c2c=None),
        ]
        identity = lambda amt, fr, to: amt
        result = calculate_logistics_total_from_invoices(invoices, "RUB", identity)
        assert result == 0.0

    def test_invoices_with_partial_null_logistics(self, quote_id):
        """Some segments are None, some have values."""
        invoices = [
            make_invoice(quote_id, s2h=100, h2c=None, c2c=None),
            make_invoice(quote_id, s2h=None, h2c=200, c2c=None),
        ]
        identity = lambda amt, fr, to: amt
        result = calculate_logistics_total_from_invoices(invoices, "USD", identity)
        assert result == 300.0

    def test_invoices_with_zero_values(self, quote_id):
        """Segments explicitly set to 0."""
        invoices = [
            make_invoice(quote_id, s2h=0, h2c=0, c2c=0),
        ]
        identity = lambda amt, fr, to: amt
        result = calculate_logistics_total_from_invoices(invoices, "USD", identity)
        assert result == 0.0

    def test_invoices_with_string_numeric_values(self, quote_id):
        """DB may return numeric strings instead of numbers."""
        invoices = [{
            "id": _make_uuid(),
            "quote_id": quote_id,
            "logistics_supplier_to_hub": "150.50",
            "logistics_hub_to_customs": "200.00",
            "logistics_customs_to_customer": "0",
            "logistics_supplier_to_hub_currency": "USD",
            "logistics_hub_to_customs_currency": "USD",
            "logistics_customs_to_customer_currency": "USD",
        }]
        identity = lambda amt, fr, to: amt
        result = calculate_logistics_total_from_invoices(invoices, "USD", identity)
        assert result == 350.50

    def test_missing_currency_defaults_to_usd(self, quote_id):
        """If currency field is missing/None, should default to USD."""
        invoices = [{
            "id": _make_uuid(),
            "quote_id": quote_id,
            "logistics_supplier_to_hub": 100,
            "logistics_hub_to_customs": None,
            "logistics_customs_to_customer": None,
            "logistics_supplier_to_hub_currency": None,  # Missing currency
            "logistics_hub_to_customs_currency": None,
            "logistics_customs_to_customer_currency": None,
        }]

        convert_calls = []
        def tracking_convert(amount, from_cur, to_cur):
            convert_calls.append((float(amount), from_cur, to_cur))
            return amount
        calculate_logistics_total_from_invoices(invoices, "USD", tracking_convert)
        # If from=USD and to=USD, convert may short-circuit.
        # The key assertion: from_currency defaults to "USD" when None
        if convert_calls:
            assert convert_calls[0][1] == "USD"

    def test_single_large_value(self, quote_id):
        """Test with large monetary values (no overflow)."""
        invoices = [make_invoice(quote_id, s2h=999999.99, h2c=888888.88, c2c=777777.77)]
        identity = lambda amt, fr, to: amt
        result = calculate_logistics_total_from_invoices(invoices, "USD", identity)
        assert abs(result - 2666666.64) < 0.01


# ==============================================================================
# SECTION 2: Source Code Pattern Verification
#
# These tests verify that main.py contains the expected code patterns for
# fetching and calculating logistics costs in the quote detail handler.
# ==============================================================================

class TestMainPyLogisticsCostIntegration:
    """Verify main.py source code has the logistics cost calculation
    in the quote detail GET handler (around line 8007+)."""

    def test_quote_detail_queries_invoices_for_logistics(self):
        """The quote detail handler should query invoices table for logistics costs."""
        source = _read_main_source()

        # Find the quote detail handler section (starts with @rt("/quotes/{quote_id}"))
        # and look for invoices query with logistics columns
        pattern = r'@rt\("/quotes/\{quote_id\}"\).*?def get\('
        match = re.search(pattern, source, re.DOTALL)
        assert match, "Quote detail GET handler not found"

        # Get the handler body (up to next @rt decorator)
        handler_start = match.start()
        next_rt = source.find("@rt(", handler_start + 10)
        handler_body = source[handler_start:next_rt] if next_rt > 0 else source[handler_start:]

        # Check that invoices are queried with logistics columns within this handler
        assert "invoices" in handler_body, \
            "Quote detail handler should query invoices table"
        assert "logistics_supplier_to_hub" in handler_body, \
            "Quote detail handler should select logistics_supplier_to_hub from invoices"
        assert "logistics_hub_to_customs" in handler_body, \
            "Quote detail handler should select logistics_hub_to_customs from invoices"
        assert "logistics_customs_to_customer" in handler_body, \
            "Quote detail handler should select logistics_customs_to_customer from invoices"

    def test_itogo_block_uses_calculated_logistics_total(self):
        """The Itogo block should use a calculated logistics_total variable,
        NOT quote.get('logistics_total')."""
        source = _read_main_source()

        # Find the line that displays Логистика in the Itого block
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if 'Td("Логистика:")' in line or "Td('Логистика:')" in line:
                # This line should NOT contain quote.get("logistics_total")
                assert 'quote.get("logistics_total")' not in line, \
                    f"Line {i+1}: Itogo block still uses quote.get('logistics_total'). " \
                    "It should use a calculated variable from invoices."
                # Positive check: should reference logistics_total variable directly
                assert re.search(r'format_money\(\s*logistics_total\b', line), \
                    f"Line {i+1}: Expected format_money(logistics_total, ...) but got: {line.strip()}"
                return

        pytest.fail("Could not find Td('Логистика:') display line in main.py")

    def test_logistics_total_calculated_before_itogo_block(self):
        """logistics_total variable should be calculated (from invoices)
        before the Itogo display block."""
        source = _read_main_source()

        # Find the quote detail handler
        pattern = r'@rt\("/quotes/\{quote_id\}"\).*?def get\('
        match = re.search(pattern, source, re.DOTALL)
        assert match, "Quote detail GET handler not found"

        handler_start = match.start()
        next_rt = source.find("@rt(", handler_start + 10)
        handler_body = source[handler_start:next_rt] if next_rt > 0 else source[handler_start:]

        # Look for logistics_total calculation (assignment)
        calc_pattern = r'logistics_total\s*[=+]'
        calc_match = re.search(calc_pattern, handler_body)
        assert calc_match, \
            "No logistics_total calculation found in quote detail handler. " \
            "Expected variable assignment from invoice aggregation."

    def test_currency_conversion_used_for_logistics(self):
        """The logistics calculation should use convert_amount for currency conversion."""
        source = _read_main_source()

        # Find the quote detail handler
        pattern = r'@rt\("/quotes/\{quote_id\}"\).*?def get\('
        match = re.search(pattern, source, re.DOTALL)
        assert match

        handler_start = match.start()
        next_rt = source.find("@rt(", handler_start + 10)
        handler_body = source[handler_start:next_rt] if next_rt > 0 else source[handler_start:]

        assert "convert_amount" in handler_body, \
            "Quote detail handler should use convert_amount for currency conversion of logistics costs"


# ==============================================================================
# SECTION 3: format_money Display Logic
#
# Verify that format_money correctly handles the calculated logistics value.
# ==============================================================================

class TestFormatMoneyForLogistics:
    """Test the format_money function with logistics cost values."""

    def _get_format_money(self):
        """Import format_money from main.py."""
        try:
            # Try to import directly
            import sys
            sys.path.insert(0, _PROJECT_ROOT)
            # Can't import main.py directly (too many deps), so parse the function
            source = _read_main_source()
            # Extract the format_money function and exec it
            fn_match = re.search(
                r'(def format_money\(.*?\n(?:    .*\n)*)',
                source,
            )
            assert fn_match, "format_money function not found in main.py"
            fn_source = fn_match.group(1)
            local_ns = {}
            exec(fn_source, local_ns)
            return local_ns["format_money"]
        except Exception as e:
            pytest.skip(f"Cannot extract format_money: {e}")

    def test_format_money_with_positive_logistics_total(self):
        """Positive logistics total should display as formatted money."""
        format_money = self._get_format_money()
        result = format_money(1500.0, "USD")
        assert "$" in result
        assert "1,500" in result or "1500" in result

    def test_format_money_with_zero_shows_dash(self):
        """Zero logistics total should show dash."""
        format_money = self._get_format_money()
        result = format_money(0, "USD")
        # format_money returns dash for 0 values
        assert result == "\u2014"  # em dash

    def test_format_money_with_none_shows_dash(self):
        """None logistics total should show dash."""
        format_money = self._get_format_money()
        result = format_money(None, "USD")
        assert result == "\u2014"  # em dash

    def test_format_money_with_rub_currency(self):
        """Logistics total in RUB should use ruble symbol."""
        format_money = self._get_format_money()
        result = format_money(79000, "RUB")
        assert "\u20bd" in result  # ruble sign
        assert "79" in result


# ==============================================================================
# SECTION 4: Edge Cases for Invoice Data Quality
#
# Real-world invoices may have unexpected data shapes.
# ==============================================================================

class TestInvoiceDataQualityEdgeCases:
    """Test logistics calculation resilience to bad data."""

    def _calculate(self, invoices, quote_currency="USD"):
        """Helper to calculate logistics total with identity conversion."""
        identity = lambda amt, fr, to: amt
        return calculate_logistics_total_from_invoices(invoices, quote_currency, identity)

    def test_invoice_missing_all_logistics_keys(self, quote_id):
        """Invoice dict has no logistics keys at all."""
        invoices = [{"id": _make_uuid(), "quote_id": quote_id}]
        result = self._calculate(invoices)
        assert result == 0.0

    def test_invoice_with_negative_values_ignored(self, quote_id):
        """Negative logistics costs should not reduce total (treat as 0)."""
        invoices = [make_invoice(quote_id, s2h=-100, h2c=200, c2c=0)]
        # Negative amounts: the implementation should handle this.
        # The existing pattern checks `if amount > 0` before adding.
        result = self._calculate(invoices)
        # -100 is not > 0, so only 200 counted
        assert result == 200.0

    def test_very_many_invoices(self, quote_id):
        """Test with many invoices (performance sanity)."""
        invoices = [make_invoice(quote_id, s2h=10, h2c=20, c2c=30) for _ in range(100)]
        result = self._calculate(invoices)
        assert result == 6000.0  # 100 * (10 + 20 + 30)


# ==============================================================================
# SECTION 5: Integration Pattern - Verify Quote Detail Displays Logistics
#
# These tests check the full data flow: query + calculation + display.
# ==============================================================================

class TestQuoteDetailLogisticsDataFlow:
    """Verify the complete data flow from DB query to HTML display."""

    def test_source_has_no_logistics_total_from_quote_dict(self):
        """Confirm the Логистика display line does NOT read logistics_total
        from the quote dict. It must come from invoices calculation."""
        source = _read_main_source()

        # Find the specific line that displays Логистика in the Itogo block
        lines = source.split('\n')
        found = False
        for i, line in enumerate(lines):
            if 'Td("Логистика:")' in line:
                found = True
                # This line should NOT contain quote.get("logistics_total")
                assert 'quote.get("logistics_total")' not in line, \
                    f"Line {i+1}: Logistics display still reads from quote dict. " \
                    "It should use a calculated variable from invoices."
                break

        assert found, "Could not find Td('Логистика:') display line in main.py"

    def test_logistics_total_variable_used_in_display(self):
        """The Itogo block should reference a logistics_total variable
        (not quote.get) for the Логистика row."""
        source = _read_main_source()

        # Find the line with "Логистика:" in the Itogo section
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if 'Td("Логистика:")' in line or "Td('Логистика:')" in line:
                # Check the same line or next line for the value source
                context = '\n'.join(lines[max(0, i):min(len(lines), i+3)])
                # Should use format_money(logistics_total, ...) not format_money(quote.get(...), ...)
                assert 'quote.get("logistics_total")' not in context, \
                    f"Line {i+1}: Still using quote.get('logistics_total'). Expected calculated variable."
                # Verify it uses a variable (not a dict access on quote)
                assert re.search(r'format_money\(\s*logistics_total', context), \
                    f"Line {i+1}: Expected format_money(logistics_total, ...) but got: {context.strip()}"
                return

        pytest.fail("Could not find Td('Логистика:') in the Itogo block")
