"""
Tests for services/currency_service.py — Phase 3 expansion to 10 currencies.

Covers:
- SUPPORTED_CURRENCIES length and membership (USD, EUR, RUB, CNY, TRY,
  AED, KZT, JPY, GBP, CHF)
- CBR_CURRENCY_CODES / CBR_CHAR_CODES completeness for all non-RUB entries
- convert_to_usd: plausible range for AED, JPY (nominal-100 quirk), unknown codes
"""

from decimal import Decimal
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Constants — SUPPORTED_CURRENCIES and CBR mappings
# ---------------------------------------------------------------------------


class TestSupportedCurrenciesConstant:
    """SUPPORTED_CURRENCIES must have exactly 10 entries matching the frontend."""

    def test_supported_currencies_length_is_ten(self):
        from services.currency_service import SUPPORTED_CURRENCIES
        assert len(SUPPORTED_CURRENCIES) == 10

    def test_supported_currencies_contains_all_expected_codes(self):
        from services.currency_service import SUPPORTED_CURRENCIES
        expected = {
            "USD", "EUR", "RUB", "CNY", "TRY",
            "AED", "KZT", "JPY", "GBP", "CHF",
        }
        assert set(SUPPORTED_CURRENCIES) == expected

    def test_supported_currencies_order_matches_frontend(self):
        """Order must match frontend/src/shared/lib/currencies.ts exactly.

        This keeps dropdown ordering consistent across stack and is required
        by the docstring of `currencies.ts`.
        """
        from services.currency_service import SUPPORTED_CURRENCIES
        expected_order = [
            "USD", "EUR", "RUB", "CNY", "TRY",
            "AED", "KZT", "JPY", "GBP", "CHF",
        ]
        assert list(SUPPORTED_CURRENCIES) == expected_order


class TestCbrMappingsComplete:
    """Every non-RUB currency in SUPPORTED_CURRENCIES must have CBR code + char code."""

    def test_cbr_currency_codes_covers_all_non_rub(self):
        from services.currency_service import (
            SUPPORTED_CURRENCIES,
            CBR_CURRENCY_CODES,
        )
        non_rub = [c for c in SUPPORTED_CURRENCIES if c != "RUB"]
        missing = [c for c in non_rub if c not in CBR_CURRENCY_CODES]
        assert missing == [], (
            f"Non-RUB currencies missing CBR codes: {missing}. "
            "Every entry in SUPPORTED_CURRENCIES except RUB must have a "
            "corresponding CBR_CURRENCY_CODES mapping."
        )

    def test_cbr_char_codes_covers_all_non_rub(self):
        from services.currency_service import (
            SUPPORTED_CURRENCIES,
            CBR_CHAR_CODES,
        )
        non_rub = [c for c in SUPPORTED_CURRENCIES if c != "RUB"]
        missing = [c for c in non_rub if c not in CBR_CHAR_CODES]
        assert missing == [], (
            f"Non-RUB currencies missing CBR char codes: {missing}"
        )

    def test_cbr_char_codes_are_iso_uppercase(self):
        """Char codes should equal the ISO 4217 code for every entry."""
        from services.currency_service import CBR_CHAR_CODES
        for code, char in CBR_CHAR_CODES.items():
            assert char == code, (
                f"CBR_CHAR_CODES[{code!r}] should be {code!r}, got {char!r}"
            )


# ---------------------------------------------------------------------------
# convert_to_usd — plausible range tests with mocked rates
# ---------------------------------------------------------------------------


@pytest.fixture
def plausible_rates():
    """Plausible CBR rates (currency -> RUB) for conversion tests.

    Values are for illustration only — tests assert plausible ranges, not
    exact math. JPY here is already per-unit (post-Nominal=100 division) as
    that matches how `fetch_cbr_rates` normalizes rates before storage.
    """
    return {
        "USD": Decimal("85.0"),     # 1 USD = 85 RUB
        "EUR": Decimal("93.0"),     # 1 EUR = 93 RUB
        "CNY": Decimal("11.5"),     # 1 CNY = 11.5 RUB
        "TRY": Decimal("2.5"),      # 1 TRY = 2.5 RUB
        "AED": Decimal("23.0"),     # 1 AED = 23 RUB
        "KZT": Decimal("0.18"),     # 1 KZT = 0.18 RUB
        "JPY": Decimal("0.57"),     # 1 JPY = 0.57 RUB (post-Nominal division)
        "GBP": Decimal("108.0"),    # 1 GBP = 108 RUB
        "CHF": Decimal("95.0"),     # 1 CHF = 95 RUB
    }


class TestConvertToUsdPlausibleRange:
    """convert_to_usd returns plausible values for the new currencies."""

    @patch("services.currency_service.ensure_rates_available")
    def test_convert_aed_to_usd_plausible_range(self, mock_rates, plausible_rates):
        """1000 AED should convert to roughly 100-500 USD at plausible rates.

        Math: 1000 AED * 23 RUB/AED / 85 RUB/USD = ~270 USD.
        """
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        result = convert_to_usd(Decimal("1000"), "AED")

        assert Decimal("100") < result < Decimal("500"), (
            f"Expected ~100-500 USD, got {result}"
        )

    @patch("services.currency_service.ensure_rates_available")
    def test_convert_jpy_respects_nominal_per_unit_rate(
        self, mock_rates, plausible_rates
    ):
        """1000 JPY should convert to roughly 6-10 USD.

        Math: 1000 JPY * 0.57 RUB/JPY / 85 RUB/USD = ~6.7 USD.
        This verifies that JPY rates are stored per-unit (already divided
        by CBR's Nominal=100 in fetch_cbr_rates).
        """
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        result = convert_to_usd(Decimal("1000"), "JPY")

        assert Decimal("5") < result < Decimal("12"), (
            f"Expected ~5-12 USD for 1000 JPY, got {result}. "
            "If this fails, check that fetch_cbr_rates correctly divides "
            "Value by Nominal (CBR publishes JPY per 100 units)."
        )

    @patch("services.currency_service.ensure_rates_available")
    def test_convert_gbp_to_usd_plausible_range(self, mock_rates, plausible_rates):
        """1000 GBP should convert to roughly 1000-1500 USD."""
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        result = convert_to_usd(Decimal("1000"), "GBP")

        assert Decimal("1000") < result < Decimal("1500"), (
            f"Expected ~1000-1500 USD, got {result}"
        )

    @patch("services.currency_service.ensure_rates_available")
    def test_convert_chf_to_usd_plausible_range(self, mock_rates, plausible_rates):
        """1000 CHF should convert to roughly 1000-1300 USD."""
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        result = convert_to_usd(Decimal("1000"), "CHF")

        assert Decimal("1000") < result < Decimal("1300"), (
            f"Expected ~1000-1300 USD, got {result}"
        )

    @patch("services.currency_service.ensure_rates_available")
    def test_convert_kzt_to_usd_plausible_range(self, mock_rates, plausible_rates):
        """100000 KZT should convert to roughly 150-300 USD."""
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        result = convert_to_usd(Decimal("100000"), "KZT")

        assert Decimal("150") < result < Decimal("300"), (
            f"Expected ~150-300 USD for 100000 KZT, got {result}"
        )


class TestConvertToUsdEdgeCases:
    """Unknown currencies and boundary conditions."""

    @patch("services.currency_service.ensure_rates_available")
    def test_unknown_currency_returns_amount_unchanged(
        self, mock_rates, plausible_rates
    ):
        """Unknown currency falls back to returning the input amount.

        This matches the existing behavior of convert_to_usd: when a rate
        is missing, the function logs and returns the amount as-is rather
        than raising or returning zero. Tests the contract, does not
        change it.
        """
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        amount = Decimal("100")
        result = convert_to_usd(amount, "XXX")

        assert result == amount

    @patch("services.currency_service.ensure_rates_available")
    def test_zero_amount_returns_zero(self, mock_rates, plausible_rates):
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        assert convert_to_usd(Decimal("0"), "AED") == Decimal("0")

    @patch("services.currency_service.ensure_rates_available")
    def test_usd_to_usd_is_identity(self, mock_rates, plausible_rates):
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        assert convert_to_usd(Decimal("123.45"), "USD") == Decimal("123.45")

    @patch("services.currency_service.ensure_rates_available")
    def test_lowercase_currency_normalized(self, mock_rates, plausible_rates):
        """convert_to_usd should accept lowercase currency codes and normalize."""
        from services.currency_service import convert_to_usd
        mock_rates.return_value = plausible_rates

        result_upper = convert_to_usd(Decimal("1000"), "AED")
        result_lower = convert_to_usd(Decimal("1000"), "aed")
        assert result_upper == result_lower
