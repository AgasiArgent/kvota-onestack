"""
TDD Tests for Janna's Quote Control Checklist (7-item specification).

Task: [86af8hcmv] - Refactor existing 11-item checklist at /quote-control/{quote_id}
into Janna's exact 7-item specification with proper automation rules.

New functions to be implemented in main.py:
  - MIN_MARKUP_RULES constant (pmt_1=8%/0%, pmt_2=15%/8%, pmt_3=12.5%/5%)
  - VAT_SENSITIVE_COUNTRIES constant
  - calculate_forex_risk_auto(prepayment_percent)
  - check_markup_vs_payment_terms(deal_type, markup, payment_terms_code, prepayment_percent)
  - compare_quote_vs_invoice_prices(quote_id, items, supabase)
  - check_vat_sensitive_countries(items)
  - build_janna_checklist(quote, calc_vars, calc_summary, items)

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the feature is implemented.
"""

import pytest
import os
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock


# ============================================================================
# Path constants
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


# ============================================================================
# Import helpers -- these WILL fail until implementation exists (TDD)
# ============================================================================

def _import_from_main(name):
    """
    Import a name from main.py.
    Returns the object or raises ImportError/AttributeError (expected for TDD).
    """
    # Set test environment before importing
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_KEY", "test-key")
    os.environ.setdefault("APP_SECRET", "test-secret")
    import importlib
    main_mod = importlib.import_module("main")
    return getattr(main_mod, name)


def _read_main_source():
    """Read main.py source without importing (avoids dependency issues)."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# Test data factories
# ============================================================================

def make_uuid():
    return str(uuid4())


ORG_ID = make_uuid()


def make_quote(
    quote_id=None,
    deal_type="supply",
    currency="USD",
    workflow_status="pending_quote_control",
    **kwargs,
):
    base = {
        "id": quote_id or make_uuid(),
        "organization_id": ORG_ID,
        "deal_type": deal_type,
        "currency": currency,
        "workflow_status": workflow_status,
        "total_amount": 100000,
        "customers": {"name": "Test Customer", "inn": "1234567890"},
    }
    base.update(kwargs)
    return base


def make_calc_vars(
    markup=15,
    prepayment_percent=100,
    payment_terms_code=None,
    forex_risk_percent=3,
    lpr_reward=0,
    **kwargs,
):
    base = {
        "markup": markup,
        "client_prepayment_percent": prepayment_percent,
        "payment_terms_code": payment_terms_code,
        "forex_risk_percent": forex_risk_percent,
        "lpr_reward": lpr_reward,
        "offer_sale_type": "supply",
        "offer_incoterms": "DDP",
        "exchange_rate": 90.5,
    }
    base.update(kwargs)
    return base


def make_calc_summary(
    total_purchase=50000,
    total_logistics=5000,
    total_amount_usd=100000,
    total_profit_usd=20000,
    **kwargs,
):
    base = {
        "calc_s16_total_purchase_price": total_purchase,
        "calc_v16_total_logistics": total_logistics,
        "total_amount_usd": total_amount_usd,
        "total_profit_usd": total_profit_usd,
    }
    base.update(kwargs)
    return base


def make_item(
    item_id=None,
    quote_id=None,
    product_name="Test Product",
    quantity=10,
    purchase_price_original=100,
    purchase_currency="USD",
    supplier_country="China",
    invoice_id=None,
    **kwargs,
):
    base = {
        "id": item_id or make_uuid(),
        "quote_id": quote_id or make_uuid(),
        "product_name": product_name,
        "quantity": quantity,
        "purchase_price_original": purchase_price_original,
        "purchase_currency": purchase_currency,
        "supplier_country": supplier_country,
        "invoice_id": invoice_id,
    }
    base.update(kwargs)
    return base


# ============================================================================
# Mock Supabase for compare_quote_vs_invoice_prices tests
# ============================================================================

class MockSupabaseResponse:
    def __init__(self, data=None):
        self.data = data or []


class MockQueryBuilder:
    def __init__(self, data=None):
        self._data = data or []
        self._filters = {}

    def select(self, cols="*"):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def in_(self, col, vals):
        return self

    def execute(self):
        return MockSupabaseResponse(self._data)


class MockSupabase:
    def __init__(self):
        self._tables = {}

    def set_table_data(self, name, data):
        self._tables[name] = data

    def table(self, name):
        return MockQueryBuilder(self._tables.get(name, []))


# ============================================================================
# 1. check_markup_vs_payment_terms() -- parametrized tests
# ============================================================================

class TestCheckMarkupVsPaymentTerms:
    """
    Tests for check_markup_vs_payment_terms(deal_type, markup, payment_terms_code, prepayment_percent).

    MIN_MARKUP_RULES:
        pmt_1 (100% prepay):   supply=8%, transit=0%
        pmt_2 (0% prepay):     supply=15%, transit=8%
        pmt_3 (partial prepay): supply=12.5%, transit=5%
    """

    @pytest.mark.parametrize(
        "deal_type, markup, payment_terms_code, prepayment_percent, expected_ok",
        [
            # --- pmt_1: 100% prepayment ---
            # supply: min 8%
            ("supply", 10.0, "pmt_1", 100, True),    # above min
            ("supply", 8.0, "pmt_1", 100, True),     # exactly min
            ("supply", 7.0, "pmt_1", 100, False),    # below min
            ("supply", 7.99, "pmt_1", 100, False),   # just below min
            # transit: min 0%
            ("transit", 0.0, "pmt_1", 100, True),    # exactly min
            ("transit", 5.0, "pmt_1", 100, True),    # above min
            # --- pmt_2: 0% prepayment (full deferred) ---
            # supply: min 15%
            ("supply", 15.0, "pmt_2", 0, True),      # exactly min
            ("supply", 20.0, "pmt_2", 0, True),      # above min
            ("supply", 14.0, "pmt_2", 0, False),     # below min
            ("supply", 14.99, "pmt_2", 0, False),    # just below min
            # transit: min 8%
            ("transit", 8.0, "pmt_2", 0, True),      # exactly min
            ("transit", 7.0, "pmt_2", 0, False),     # below min
            # --- pmt_3: partial prepayment ---
            # supply: min 12.5%
            ("supply", 12.5, "pmt_3", 50, True),     # exactly min
            ("supply", 15.0, "pmt_3", 50, True),     # above min
            ("supply", 12.4, "pmt_3", 50, False),    # below min
            ("supply", 12.0, "pmt_3", 50, False),    # below min
            # transit: min 5%
            ("transit", 5.0, "pmt_3", 50, True),     # exactly min
            ("transit", 4.9, "pmt_3", 50, False),    # below min
        ],
        ids=[
            "pmt1_supply_10pct_OK",
            "pmt1_supply_8pct_OK_exact",
            "pmt1_supply_7pct_ERROR",
            "pmt1_supply_7.99pct_ERROR",
            "pmt1_transit_0pct_OK",
            "pmt1_transit_5pct_OK",
            "pmt2_supply_15pct_OK_exact",
            "pmt2_supply_20pct_OK",
            "pmt2_supply_14pct_ERROR",
            "pmt2_supply_14.99pct_ERROR",
            "pmt2_transit_8pct_OK_exact",
            "pmt2_transit_7pct_ERROR",
            "pmt3_supply_12.5pct_OK_exact",
            "pmt3_supply_15pct_OK",
            "pmt3_supply_12.4pct_ERROR",
            "pmt3_supply_12pct_ERROR",
            "pmt3_transit_5pct_OK_exact",
            "pmt3_transit_4.9pct_ERROR",
        ],
    )
    def test_markup_check_with_explicit_payment_code(
        self, deal_type, markup, payment_terms_code, prepayment_percent, expected_ok
    ):
        """Check markup against MIN_MARKUP_RULES with explicit payment_terms_code."""
        check_markup_vs_payment_terms = _import_from_main("check_markup_vs_payment_terms")

        result = check_markup_vs_payment_terms(
            deal_type=deal_type,
            markup=markup,
            payment_terms_code=payment_terms_code,
            prepayment_percent=prepayment_percent,
        )

        # Result should be a dict with at least 'ok' (bool) and 'min_markup' (float)
        assert isinstance(result, dict), "Result must be a dict"
        assert "ok" in result, "Result must have 'ok' key"
        assert result["ok"] is expected_ok, (
            f"Expected ok={expected_ok} for deal_type={deal_type}, "
            f"markup={markup}%, pmt={payment_terms_code}: got {result}"
        )

    @pytest.mark.parametrize(
        "prepayment_percent, expected_inferred_code",
        [
            (100, "pmt_1"),   # 100% prepay -> pmt_1
            (0, "pmt_2"),     # 0% prepay -> pmt_2
            (50, "pmt_3"),    # partial -> pmt_3
            (30, "pmt_3"),    # partial -> pmt_3
            (70, "pmt_3"),    # partial -> pmt_3
            (99, "pmt_3"),    # not quite 100 -> pmt_3
            (1, "pmt_3"),     # not quite 0 -> pmt_3
        ],
        ids=[
            "fallback_100pct_infer_pmt1",
            "fallback_0pct_infer_pmt2",
            "fallback_50pct_infer_pmt3",
            "fallback_30pct_infer_pmt3",
            "fallback_70pct_infer_pmt3",
            "fallback_99pct_infer_pmt3",
            "fallback_1pct_infer_pmt3",
        ],
    )
    def test_markup_check_infers_payment_code_from_prepayment(
        self, prepayment_percent, expected_inferred_code
    ):
        """When payment_terms_code is None, infer from prepayment_percent."""
        check_markup_vs_payment_terms = _import_from_main("check_markup_vs_payment_terms")

        result = check_markup_vs_payment_terms(
            deal_type="supply",
            markup=20.0,  # well above any min, so ok=True regardless
            payment_terms_code=None,
            prepayment_percent=prepayment_percent,
        )

        assert isinstance(result, dict)
        assert "inferred_code" in result or "payment_terms_code" in result, (
            "Result should indicate which payment terms code was used/inferred"
        )
        actual_code = result.get("inferred_code") or result.get("payment_terms_code")
        assert actual_code == expected_inferred_code, (
            f"For prepayment={prepayment_percent}%, expected inferred "
            f"code={expected_inferred_code}, got {actual_code}"
        )

    def test_result_contains_min_markup(self):
        """Result dict should contain the applied min_markup value."""
        check_markup_vs_payment_terms = _import_from_main("check_markup_vs_payment_terms")

        result = check_markup_vs_payment_terms(
            deal_type="supply",
            markup=10.0,
            payment_terms_code="pmt_1",
            prepayment_percent=100,
        )

        assert "min_markup" in result, "Result must contain 'min_markup'"
        assert result["min_markup"] == 8.0, (
            f"For pmt_1/supply, min_markup should be 8.0, got {result['min_markup']}"
        )

    def test_result_contains_message_on_failure(self):
        """When markup is below min, result should have a descriptive message."""
        check_markup_vs_payment_terms = _import_from_main("check_markup_vs_payment_terms")

        result = check_markup_vs_payment_terms(
            deal_type="supply",
            markup=5.0,
            payment_terms_code="pmt_1",
            prepayment_percent=100,
        )

        assert result["ok"] is False
        assert "message" in result or "details" in result, (
            "Failed check should include a message or details string"
        )


# ============================================================================
# 2. calculate_forex_risk_auto() tests
# ============================================================================

class TestCalculateForexRiskAuto:
    """
    Tests for calculate_forex_risk_auto(prepayment_percent).

    Business rules:
        prepayment_percent == 100         -> 0.0%
        prepayment_percent in [45..55]    -> 1.5%
        prepayment_percent == 0           -> 3.0%
        any other value                   -> 3.0% (default/conservative)
    """

    @pytest.mark.parametrize(
        "prepayment_percent, expected_risk",
        [
            (100, 0.0),
            (50, 1.5),
            (0, 3.0),
            (75, 3.0),      # outside any special range -> default
            (45, 1.5),      # edge: bottom of 45-55 range
            (55, 1.5),      # edge: top of 45-55 range
            (44, 3.0),      # just outside range
            (56, 3.0),      # just outside range
            (25, 3.0),      # random value
        ],
        ids=[
            "100pct_zero_risk",
            "50pct_moderate_risk",
            "0pct_full_risk",
            "75pct_default_risk",
            "45pct_edge_moderate",
            "55pct_edge_moderate",
            "44pct_outside_range",
            "56pct_outside_range",
            "25pct_default_risk",
        ],
    )
    def test_forex_risk_calculation(self, prepayment_percent, expected_risk):
        """Forex risk is auto-calculated based on prepayment percentage."""
        calculate_forex_risk_auto = _import_from_main("calculate_forex_risk_auto")

        result = calculate_forex_risk_auto(prepayment_percent)

        assert isinstance(result, (int, float)), "Result must be numeric"
        assert result == expected_risk, (
            f"For prepayment={prepayment_percent}%, expected forex risk "
            f"{expected_risk}%, got {result}%"
        )

    def test_return_type_is_float(self):
        """Result should be a float for consistent handling."""
        calculate_forex_risk_auto = _import_from_main("calculate_forex_risk_auto")

        result = calculate_forex_risk_auto(100)
        assert isinstance(result, float), f"Expected float, got {type(result)}"

    def test_never_returns_negative(self):
        """Forex risk should never be negative."""
        calculate_forex_risk_auto = _import_from_main("calculate_forex_risk_auto")

        for pct in [0, 25, 50, 75, 100, -10, 150]:
            result = calculate_forex_risk_auto(pct)
            assert result >= 0.0, (
                f"Forex risk must be non-negative, got {result} for prepayment={pct}"
            )


# ============================================================================
# 3. check_vat_sensitive_countries() tests
# ============================================================================

class TestCheckVatSensitiveCountries:
    """
    Tests for check_vat_sensitive_countries(items).

    VAT_SENSITIVE_COUNTRIES = ['Turkey', 'Poland', 'Lithuania']
    Returns a dict with status + flagged items.
    """

    def test_turkey_flagged(self):
        """Items from Turkey should trigger a warning."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [make_item(supplier_country="Turkey", product_name="Bearing A")]
        result = check_vat_sensitive_countries(items)

        assert isinstance(result, dict)
        assert result.get("status") == "warning", (
            f"Turkey should trigger warning, got status={result.get('status')}"
        )
        assert len(result.get("flagged_items", [])) == 1

    def test_poland_flagged(self):
        """Items from Poland should trigger a warning."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [make_item(supplier_country="Poland", product_name="Motor B")]
        result = check_vat_sensitive_countries(items)

        assert result.get("status") == "warning"

    def test_lithuania_flagged(self):
        """Items from Lithuania should trigger a warning."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [make_item(supplier_country="Lithuania", product_name="Pump C")]
        result = check_vat_sensitive_countries(items)

        assert result.get("status") == "warning"

    def test_china_not_flagged(self):
        """Items from China should NOT trigger a warning (info status)."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [make_item(supplier_country="China", product_name="Widget D")]
        result = check_vat_sensitive_countries(items)

        assert result.get("status") in ("ok", "info"), (
            f"China should not be flagged, got status={result.get('status')}"
        )
        assert len(result.get("flagged_items", [])) == 0

    def test_germany_not_flagged(self):
        """Items from Germany should NOT trigger a warning."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [make_item(supplier_country="Germany")]
        result = check_vat_sensitive_countries(items)

        assert result.get("status") in ("ok", "info")
        assert len(result.get("flagged_items", [])) == 0

    def test_mixed_countries_flags_sensitive_only(self):
        """Mixed items: only sensitive countries are flagged."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [
            make_item(supplier_country="Turkey", product_name="Item from Turkey"),
            make_item(supplier_country="China", product_name="Item from China"),
            make_item(supplier_country="Germany", product_name="Item from Germany"),
        ]
        result = check_vat_sensitive_countries(items)

        assert result.get("status") == "warning"
        flagged = result.get("flagged_items", [])
        assert len(flagged) == 1, f"Only Turkey item should be flagged, got {len(flagged)}"

    def test_multiple_sensitive_countries(self):
        """Multiple items from different sensitive countries are all flagged."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [
            make_item(supplier_country="Turkey", product_name="From Turkey"),
            make_item(supplier_country="Poland", product_name="From Poland"),
            make_item(supplier_country="Lithuania", product_name="From Lithuania"),
        ]
        result = check_vat_sensitive_countries(items)

        assert result.get("status") == "warning"
        assert len(result.get("flagged_items", [])) == 3

    def test_empty_items_returns_info(self):
        """Empty items list should return info status."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        result = check_vat_sensitive_countries([])

        assert result.get("status") in ("ok", "info"), (
            f"Empty items should be info/ok, got status={result.get('status')}"
        )

    def test_item_with_no_country(self):
        """Items without supplier_country should not be flagged."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [make_item(supplier_country=None)]
        result = check_vat_sensitive_countries(items)

        assert len(result.get("flagged_items", [])) == 0


# ============================================================================
# 4. compare_quote_vs_invoice_prices() tests (mock supabase)
# ============================================================================

class TestCompareQuoteVsInvoicePrices:
    """
    Tests for compare_quote_vs_invoice_prices(quote_id, items, supabase).

    Compares purchase_price_original on quote_items vs prices on supplier invoices.
    Flags mismatches > 5%.
    """

    def test_all_prices_match(self):
        """When all invoice prices match quote prices, status is ok."""
        compare_quote_vs_invoice_prices = _import_from_main("compare_quote_vs_invoice_prices")

        quote_id = make_uuid()
        item_id_1 = make_uuid()
        item_id_2 = make_uuid()

        items = [
            make_item(item_id=item_id_1, quote_id=quote_id, purchase_price_original=100),
            make_item(item_id=item_id_2, quote_id=quote_id, purchase_price_original=200),
        ]

        mock_sb = MockSupabase()
        # Simulate supplier_invoice_items matching quote prices
        mock_sb.set_table_data("supplier_invoice_items", [
            {"quote_item_id": item_id_1, "unit_price": 100},
            {"quote_item_id": item_id_2, "unit_price": 200},
        ])

        result = compare_quote_vs_invoice_prices(quote_id, items, mock_sb)

        assert isinstance(result, dict)
        assert result.get("status") in ("ok", "info"), (
            f"All matching prices should be ok, got {result.get('status')}"
        )
        assert len(result.get("mismatches", [])) == 0

    def test_one_price_mismatch_above_threshold(self):
        """When one invoice price differs by >5%, status is warning."""
        compare_quote_vs_invoice_prices = _import_from_main("compare_quote_vs_invoice_prices")

        quote_id = make_uuid()
        item_id_1 = make_uuid()

        items = [
            make_item(
                item_id=item_id_1,
                quote_id=quote_id,
                purchase_price_original=100,
                product_name="Bearing SKF 6205",
            ),
        ]

        mock_sb = MockSupabase()
        # Invoice price differs by 10% (>5% threshold)
        mock_sb.set_table_data("supplier_invoice_items", [
            {"quote_item_id": item_id_1, "unit_price": 110},
        ])

        result = compare_quote_vs_invoice_prices(quote_id, items, mock_sb)

        assert result.get("status") == "warning"
        mismatches = result.get("mismatches", [])
        assert len(mismatches) == 1
        # Mismatch should include the product name
        assert "Bearing" in str(mismatches[0]) or "product_name" in mismatches[0]

    def test_price_mismatch_within_threshold(self):
        """Price difference within 5% should not be flagged."""
        compare_quote_vs_invoice_prices = _import_from_main("compare_quote_vs_invoice_prices")

        quote_id = make_uuid()
        item_id_1 = make_uuid()

        items = [
            make_item(item_id=item_id_1, quote_id=quote_id, purchase_price_original=100),
        ]

        mock_sb = MockSupabase()
        # 4% difference - within threshold
        mock_sb.set_table_data("supplier_invoice_items", [
            {"quote_item_id": item_id_1, "unit_price": 104},
        ])

        result = compare_quote_vs_invoice_prices(quote_id, items, mock_sb)

        assert result.get("status") in ("ok", "info")
        assert len(result.get("mismatches", [])) == 0

    def test_multiple_mismatches(self):
        """Multiple price mismatches are all reported."""
        compare_quote_vs_invoice_prices = _import_from_main("compare_quote_vs_invoice_prices")

        quote_id = make_uuid()
        id_1, id_2, id_3 = make_uuid(), make_uuid(), make_uuid()

        items = [
            make_item(item_id=id_1, quote_id=quote_id, purchase_price_original=100, product_name="Item A"),
            make_item(item_id=id_2, quote_id=quote_id, purchase_price_original=200, product_name="Item B"),
            make_item(item_id=id_3, quote_id=quote_id, purchase_price_original=300, product_name="Item C"),
        ]

        mock_sb = MockSupabase()
        mock_sb.set_table_data("supplier_invoice_items", [
            {"quote_item_id": id_1, "unit_price": 120},  # +20% mismatch
            {"quote_item_id": id_2, "unit_price": 202},  # +1% ok
            {"quote_item_id": id_3, "unit_price": 350},  # +16.7% mismatch
        ])

        result = compare_quote_vs_invoice_prices(quote_id, items, mock_sb)

        assert result.get("status") == "warning"
        mismatches = result.get("mismatches", [])
        assert len(mismatches) == 2, (
            f"Expected 2 mismatches (Item A +20%, Item C +16.7%), got {len(mismatches)}"
        )

    def test_no_invoices_found(self):
        """When no supplier invoices exist, return a specific warning."""
        compare_quote_vs_invoice_prices = _import_from_main("compare_quote_vs_invoice_prices")

        quote_id = make_uuid()
        items = [make_item(quote_id=quote_id)]

        mock_sb = MockSupabase()
        mock_sb.set_table_data("supplier_invoice_items", [])

        result = compare_quote_vs_invoice_prices(quote_id, items, mock_sb)

        assert result.get("status") in ("warning", "error")
        # Should indicate no invoices
        result_str = str(result).lower()
        assert "инвойс" in result_str or "invoice" in result_str or "no_invoices" in result_str, (
            "Result should mention missing invoices"
        )

    def test_empty_items_list(self):
        """Empty items list should return info."""
        compare_quote_vs_invoice_prices = _import_from_main("compare_quote_vs_invoice_prices")

        mock_sb = MockSupabase()
        result = compare_quote_vs_invoice_prices(make_uuid(), [], mock_sb)

        assert result.get("status") in ("ok", "info")


# ============================================================================
# 5. build_janna_checklist() integration tests
# ============================================================================

class TestBuildJannaChecklist:
    """
    Tests for build_janna_checklist(quote, calc_vars, calc_summary, items).

    Must return exactly 7 checklist items in this order:
    1. Markup vs payment terms
    2. Purchase prices vs invoice prices
    3. VAT sensitive countries
    4. Logistics verification
    5. Customs / HS codes
    6. Forex risk
    7. Kickback (LPR reward)
    """

    def _get_checklist(self, **overrides):
        """Helper to build a checklist with reasonable defaults."""
        build_janna_checklist = _import_from_main("build_janna_checklist")

        quote = overrides.pop("quote", make_quote())
        calc_vars = overrides.pop("calc_vars", make_calc_vars())
        calc_summary = overrides.pop("calc_summary", make_calc_summary())
        items = overrides.pop("items", [make_item(), make_item()])

        return build_janna_checklist(quote, calc_vars, calc_summary, items)

    def test_returns_exactly_7_items(self):
        """Checklist must contain exactly 7 items (Janna's specification)."""
        checklist = self._get_checklist()

        assert isinstance(checklist, list), "Checklist must be a list"
        assert len(checklist) == 7, (
            f"Janna's checklist must have exactly 7 items, got {len(checklist)}"
        )

    def test_each_item_has_required_fields(self):
        """Each checklist item must have name, status, value, and details."""
        checklist = self._get_checklist()

        required_keys = {"name", "status", "value"}
        for i, item in enumerate(checklist):
            assert isinstance(item, dict), f"Item {i} must be a dict"
            missing = required_keys - set(item.keys())
            assert not missing, (
                f"Item {i} ({item.get('name', '?')}) missing keys: {missing}"
            )
            # Status must be one of known values
            assert item["status"] in ("ok", "warning", "error", "info"), (
                f"Item {i} status must be ok/warning/error/info, got {item['status']}"
            )

    def test_item_order_matches_spec(self):
        """Items must be in Janna's specified order."""
        checklist = self._get_checklist()

        # Expected item topics (substring matching for flexibility)
        expected_topics = [
            "наценк",     # 1. Markup
            "цен",        # 2. Prices (quote vs invoice)
            "НДС",        # 3. VAT
            "логистик",   # 4. Logistics
            "тамож",      # 5. Customs
            "курсов",     # 6. Forex
            "ЛПР",        # 7. Kickback / LPR reward
        ]

        for i, topic in enumerate(expected_topics):
            item_name = checklist[i].get("name", "").lower()
            assert topic.lower() in item_name, (
                f"Item {i+1} should be about '{topic}', "
                f"got name='{checklist[i].get('name')}'"
            )

    def test_markup_item_status_ok_when_above_min(self):
        """First item (markup) should be ok when markup exceeds minimum."""
        checklist = self._get_checklist(
            calc_vars=make_calc_vars(markup=20, payment_terms_code="pmt_1"),
        )

        markup_item = checklist[0]
        assert markup_item["status"] == "ok", (
            f"Markup 20% with pmt_1/supply (min 8%) should be ok, "
            f"got {markup_item['status']}"
        )

    def test_markup_item_status_error_when_below_min(self):
        """First item (markup) should be error when markup is below minimum."""
        checklist = self._get_checklist(
            calc_vars=make_calc_vars(markup=5, payment_terms_code="pmt_2"),
        )

        markup_item = checklist[0]
        assert markup_item["status"] == "error", (
            f"Markup 5% with pmt_2/supply (min 15%) should be error, "
            f"got {markup_item['status']}"
        )

    def test_vat_item_warning_for_turkey(self):
        """VAT item should be warning when items from Turkey."""
        items = [
            make_item(supplier_country="Turkey"),
            make_item(supplier_country="China"),
        ]
        checklist = self._get_checklist(items=items)

        vat_item = checklist[2]  # item index 2 = VAT
        assert vat_item["status"] == "warning", (
            f"VAT should warn for Turkey items, got {vat_item['status']}"
        )

    def test_forex_item_auto_calculated(self):
        """Forex item should use auto-calculated risk when available."""
        checklist = self._get_checklist(
            calc_vars=make_calc_vars(prepayment_percent=100),
        )

        forex_item = checklist[5]  # item index 5 = Forex
        # With 100% prepayment, auto-forex should be 0%
        assert "0" in str(forex_item.get("value", "")), (
            f"With 100% prepayment, forex risk should show 0%, "
            f"got value={forex_item.get('value')}"
        )

    def test_kickback_item_warning_when_present(self):
        """Kickback (LPR) item should be warning when reward > 0."""
        checklist = self._get_checklist(
            calc_vars=make_calc_vars(lpr_reward=5000),
        )

        kickback_item = checklist[6]  # item index 6 = Kickback
        assert kickback_item["status"] == "warning", (
            f"LPR reward > 0 should be warning, got {kickback_item['status']}"
        )

    def test_kickback_item_ok_when_zero(self):
        """Kickback (LPR) item should be ok when reward is 0."""
        checklist = self._get_checklist(
            calc_vars=make_calc_vars(lpr_reward=0),
        )

        kickback_item = checklist[6]
        assert kickback_item["status"] == "ok", (
            f"LPR reward 0 should be ok, got {kickback_item['status']}"
        )


# ============================================================================
# 6. Constants existence tests (source inspection)
# ============================================================================

class TestConstantsExistInSource:
    """Verify that required constants are defined in main.py."""

    def test_min_markup_rules_constant_exists(self):
        """MIN_MARKUP_RULES constant must be defined in main.py."""
        source = _read_main_source()
        assert "MIN_MARKUP_RULES" in source, (
            "MIN_MARKUP_RULES constant not found in main.py"
        )

    def test_min_markup_rules_has_pmt_1(self):
        """MIN_MARKUP_RULES must include pmt_1 entry."""
        source = _read_main_source()
        assert "pmt_1" in source, "MIN_MARKUP_RULES must include pmt_1"

    def test_min_markup_rules_has_pmt_2(self):
        """MIN_MARKUP_RULES must include pmt_2 entry."""
        source = _read_main_source()
        assert "pmt_2" in source, "MIN_MARKUP_RULES must include pmt_2"

    def test_min_markup_rules_has_pmt_3(self):
        """MIN_MARKUP_RULES must include pmt_3 entry."""
        source = _read_main_source()
        assert "pmt_3" in source, "MIN_MARKUP_RULES must include pmt_3"

    def test_vat_sensitive_countries_constant_exists(self):
        """VAT_SENSITIVE_COUNTRIES constant must be defined in main.py."""
        source = _read_main_source()
        assert "VAT_SENSITIVE_COUNTRIES" in source, (
            "VAT_SENSITIVE_COUNTRIES constant not found in main.py"
        )

    def test_vat_sensitive_countries_includes_turkey(self):
        """VAT_SENSITIVE_COUNTRIES must include Turkey."""
        source = _read_main_source()
        assert "Turkey" in source, "VAT_SENSITIVE_COUNTRIES must include Turkey"

    def test_vat_sensitive_countries_includes_poland(self):
        """VAT_SENSITIVE_COUNTRIES must include Poland."""
        source = _read_main_source()
        assert "Poland" in source, "VAT_SENSITIVE_COUNTRIES must include Poland"

    def test_vat_sensitive_countries_includes_lithuania(self):
        """VAT_SENSITIVE_COUNTRIES must include Lithuania."""
        source = _read_main_source()
        assert "Lithuania" in source, "VAT_SENSITIVE_COUNTRIES must include Lithuania"


# ============================================================================
# 7. Function definitions in source (source inspection)
# ============================================================================

class TestFunctionDefinitionsExist:
    """Verify that all new functions are defined in main.py."""

    def test_calculate_forex_risk_auto_defined(self):
        """calculate_forex_risk_auto function must exist in main.py."""
        source = _read_main_source()
        assert "def calculate_forex_risk_auto(" in source, (
            "calculate_forex_risk_auto function not found in main.py"
        )

    def test_check_markup_vs_payment_terms_defined(self):
        """check_markup_vs_payment_terms function must exist in main.py."""
        source = _read_main_source()
        assert "def check_markup_vs_payment_terms(" in source, (
            "check_markup_vs_payment_terms function not found in main.py"
        )

    def test_compare_quote_vs_invoice_prices_defined(self):
        """compare_quote_vs_invoice_prices function must exist in main.py."""
        source = _read_main_source()
        assert "def compare_quote_vs_invoice_prices(" in source, (
            "compare_quote_vs_invoice_prices function not found in main.py"
        )

    def test_check_vat_sensitive_countries_defined(self):
        """check_vat_sensitive_countries function must exist in main.py."""
        source = _read_main_source()
        assert "def check_vat_sensitive_countries(" in source, (
            "check_vat_sensitive_countries function not found in main.py"
        )

    def test_build_janna_checklist_defined(self):
        """build_janna_checklist function must exist in main.py."""
        source = _read_main_source()
        assert "def build_janna_checklist(" in source, (
            "build_janna_checklist function not found in main.py"
        )


# ============================================================================
# 8. Route integration tests (source inspection)
# ============================================================================

class TestRouteUsesJannaChecklist:
    """
    Verify that GET /quote-control/{quote_id} uses the new build_janna_checklist
    and renders 7 checklist items.
    """

    def _get_route_source(self):
        """Extract the quote-control detail route source."""
        import re
        source = _read_main_source()
        match = re.search(
            r'@rt\("/quote-control/\{quote_id\}"\)\s*\ndef get\(.*?\n'
            r'(.*?)(?=\n@rt\(|$)',
            source,
            re.DOTALL,
        )
        assert match, "GET /quote-control/{quote_id} route not found in main.py"
        return match.group(0)

    def test_route_calls_build_janna_checklist(self):
        """Route handler must call build_janna_checklist."""
        route_source = self._get_route_source()
        assert "build_janna_checklist" in route_source, (
            "GET /quote-control/{quote_id} must call build_janna_checklist()"
        )

    def test_route_contains_checklist_title(self):
        """Route must render the checklist with a proper title."""
        route_source = self._get_route_source()
        has_title = (
            "ЧЕК-ЛИСТ ПРОВЕРКИ" in route_source
            or "Чек-лист проверки" in route_source
            or "чек-лист" in route_source.lower()
        )
        assert has_title, (
            "Route must contain checklist title text (e.g., 'ЧЕК-ЛИСТ ПРОВЕРКИ')"
        )

    def test_route_has_approve_action(self):
        """Route must have an approve action button."""
        route_source = self._get_route_source()
        has_approve = "approve" in route_source.lower() or "одобрить" in route_source.lower()
        assert has_approve, "Route must have an approve action"

    def test_route_has_return_action(self):
        """Route must have a return-to-revision action button."""
        route_source = self._get_route_source()
        has_return = (
            "return" in route_source.lower()
            or "вернуть" in route_source.lower()
            or "revision" in route_source.lower()
            or "доработк" in route_source.lower()
        )
        assert has_return, "Route must have a return/revision action"

    def test_route_has_request_approval_action(self):
        """Route must have a request-approval action for escalation."""
        route_source = self._get_route_source()
        has_request = (
            "request-approval" in route_source
            or "request_approval" in route_source
            or "согласовани" in route_source.lower()
        )
        assert has_request, "Route must have a request-approval action"


# ============================================================================
# 9. Edge cases and boundary values
# ============================================================================

class TestEdgeCases:
    """Additional edge case tests across all functions."""

    def test_markup_check_zero_markup_transit_pmt1_is_ok(self):
        """Zero markup for transit with pmt_1 is valid (min is 0%)."""
        check_markup_vs_payment_terms = _import_from_main("check_markup_vs_payment_terms")

        result = check_markup_vs_payment_terms(
            deal_type="transit",
            markup=0.0,
            payment_terms_code="pmt_1",
            prepayment_percent=100,
        )
        assert result["ok"] is True

    def test_markup_check_negative_markup_always_fails(self):
        """Negative markup should always fail."""
        check_markup_vs_payment_terms = _import_from_main("check_markup_vs_payment_terms")

        result = check_markup_vs_payment_terms(
            deal_type="supply",
            markup=-5.0,
            payment_terms_code="pmt_1",
            prepayment_percent=100,
        )
        assert result["ok"] is False

    def test_forex_risk_with_none_prepayment(self):
        """None prepayment should be handled gracefully (default to 3%)."""
        calculate_forex_risk_auto = _import_from_main("calculate_forex_risk_auto")

        # Should not raise, should return default
        result = calculate_forex_risk_auto(None)
        assert result == 3.0, (
            f"None prepayment should default to 3.0%, got {result}"
        )

    def test_vat_check_case_insensitive_country(self):
        """Country matching should work regardless of case."""
        check_vat_sensitive_countries = _import_from_main("check_vat_sensitive_countries")

        items = [make_item(supplier_country="turkey")]  # lowercase
        result = check_vat_sensitive_countries(items)

        # Should still flag Turkey regardless of case
        assert result.get("status") == "warning", (
            "Country check should be case-insensitive"
        )

    def test_build_checklist_with_empty_items(self):
        """Checklist should handle empty items list gracefully."""
        build_janna_checklist = _import_from_main("build_janna_checklist")

        result = build_janna_checklist(
            make_quote(),
            make_calc_vars(),
            make_calc_summary(),
            [],
        )

        assert isinstance(result, list)
        assert len(result) == 7, "Even with empty items, 7 checklist items returned"

    def test_build_checklist_with_missing_calc_vars(self):
        """Checklist should handle missing/empty calc_vars gracefully."""
        build_janna_checklist = _import_from_main("build_janna_checklist")

        result = build_janna_checklist(
            make_quote(),
            {},  # empty calc_vars
            make_calc_summary(),
            [make_item()],
        )

        assert isinstance(result, list)
        assert len(result) == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
