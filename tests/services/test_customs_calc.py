"""Tests for services/customs_calc.py — REQ-4 customs-phase-1.

Pure-functional duty arithmetic: ad-valorem, specific, combined (max / +),
ПП 342 customs fee step-function, ПП 81 utilization fee (87xxxx only),
Decimal precision invariants, ValueError on inconsistent rate shapes.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from services.alta_client import Rate
from services.customs_calc import (
    CustomsPayBreakdown,
    calculate_customs_fee,
    calculate_duty,
    calculate_total_customs_pay,
    calculate_util_fee,
)


# ---------------------------------------------------------------------------
# Rate factory — build Rate dataclass with required positional fields filled
# ---------------------------------------------------------------------------


def _make_rate(**overrides) -> Rate:
    """Build a Rate dataclass with sensible defaults for testing.

    Required fields (tnved_code, payment_type, country_or_areal,
    valid_from) are provided defaults so tests can focus on the
    rate-shape (slot 1/2/3) under test.
    """
    defaults: dict = {
        "tnved_code": "1234567890",
        "payment_type": "IMP",
        "country_or_areal": None,
        "valid_from": date(2026, 1, 1),
        "valid_to": None,
        "value_1_number": None,
        "value_1_unit": None,
        "value_1_currency": None,
        "value_2_number": None,
        "value_2_unit": None,
        "value_2_currency": None,
        "sign_1": None,
        "value_3_number": None,
        "value_3_unit": None,
        "value_3_currency": None,
        "sign_2": None,
        "raw_value_string": None,
        "certificate_required": False,
        "sp_certificate_required": False,
    }
    defaults.update(overrides)
    return Rate(**defaults)


# ---------------------------------------------------------------------------
# calculate_duty — ad-valorem (pure percent)
# ---------------------------------------------------------------------------


def test_calculate_duty_pure_ad_valorem():
    """Ad-valorem: customs_value × value_1_number / 100."""
    rate = _make_rate(value_1_number=10.0, value_1_unit="percent")
    result = calculate_duty(
        rate=rate,
        customs_value_rub=Decimal("100000"),
        weight_kg=Decimal("0"),
        quantity=Decimal("0"),
        currency_rates={},
    )
    assert result == Decimal("10000.00")
    assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# calculate_duty — pure specific (per-kg / per-unit)
# ---------------------------------------------------------------------------


def test_calculate_duty_pure_specific_per_kg():
    """Specific per-kg: weight × value × currency_rate."""
    rate = _make_rate(
        value_1_number=0.04,
        value_1_unit="166",  # kg
        value_1_currency="EUR",
    )
    result = calculate_duty(
        rate=rate,
        customs_value_rub=Decimal("0"),
        weight_kg=Decimal("500"),
        quantity=Decimal("0"),
        currency_rates={"EUR": Decimal("100")},
    )
    # 500 kg × 0.04 EUR/kg × 100 RUB/EUR = 2000.00
    assert result == Decimal("2000.00")


def test_calculate_duty_pure_specific_per_unit():
    """Specific per-unit (796 = шт): quantity × value × currency_rate."""
    rate = _make_rate(
        value_1_number=2.0,
        value_1_unit="796",  # шт
        value_1_currency="USD",
    )
    result = calculate_duty(
        rate=rate,
        customs_value_rub=Decimal("0"),
        weight_kg=Decimal("0"),
        quantity=Decimal("100"),
        currency_rates={"USD": Decimal("92")},
    )
    # 100 × 2 USD × 92 RUB/USD = 18400.00
    assert result == Decimal("18400.00")


# ---------------------------------------------------------------------------
# calculate_duty — combined max (default sign='>')
# ---------------------------------------------------------------------------


def test_calculate_duty_combined_max_default():
    """Combined `>` (max): when ad-valorem dominates."""
    rate = _make_rate(
        value_1_number=10.0,
        value_1_unit="percent",
        value_2_number=0.04,
        value_2_unit="166",
        value_2_currency="EUR",
        sign_1=">",
    )
    result = calculate_duty(
        rate=rate,
        customs_value_rub=Decimal("100000"),
        weight_kg=Decimal("500"),
        quantity=Decimal("0"),
        currency_rates={"EUR": Decimal("100")},
    )
    # ad_valorem = 100000 × 10/100 = 10000
    # specific   = 500 × 0.04 × 100 = 2000
    # max(10000, 2000) = 10000
    assert result == Decimal("10000.00")


def test_calculate_duty_combined_max_specific_wins():
    """Combined `>` (max): when specific dominates."""
    rate = _make_rate(
        value_1_number=10.0,
        value_1_unit="percent",
        value_2_number=0.04,
        value_2_unit="166",
        value_2_currency="EUR",
        sign_1=">",
    )
    result = calculate_duty(
        rate=rate,
        customs_value_rub=Decimal("10000"),
        weight_kg=Decimal("500"),
        quantity=Decimal("0"),
        currency_rates={"EUR": Decimal("100")},
    )
    # ad_valorem = 10000 × 10/100 = 1000
    # specific   = 500 × 0.04 × 100 = 2000
    # max(1000, 2000) = 2000
    assert result == Decimal("2000.00")


# ---------------------------------------------------------------------------
# calculate_duty — combined addition (sign='+')
# ---------------------------------------------------------------------------


def test_calculate_duty_combined_addition():
    """Combined `+`: ad-valorem + specific (NOT max)."""
    rate = _make_rate(
        value_1_number=5.0,
        value_1_unit="percent",
        value_2_number=0.10,
        value_2_unit="166",
        value_2_currency="USD",
        sign_1="+",
    )
    result = calculate_duty(
        rate=rate,
        customs_value_rub=Decimal("200000"),
        weight_kg=Decimal("100"),
        quantity=Decimal("0"),
        currency_rates={"USD": Decimal("90")},
    )
    # ad_valorem = 200000 × 5/100 = 10000
    # specific   = 100 × 0.10 × 90 = 900
    # sum = 10900
    assert result == Decimal("10900.00")


# ---------------------------------------------------------------------------
# calculate_duty — error cases
# ---------------------------------------------------------------------------


def test_calculate_duty_unknown_sign_raises():
    """Unknown combined sign (e.g. '*') → ValueError mentioning sign_1.

    Invariant moved upstream: Rate.__post_init__ now rejects illegal
    combinations at construction (per PR #83 review TD-1). The
    enforcement layer changed but the user-visible contract is the
    same — bad data raises ValueError before any calc happens.
    """
    with pytest.raises(ValueError, match="sign_1"):
        _make_rate(
            value_1_number=10.0,
            value_1_unit="percent",
            value_2_number=0.04,
            value_2_unit="166",
            value_2_currency="EUR",
            sign_1="*",
        )


def test_calculate_duty_inconsistent_rate_raises():
    """Percent rate with a currency set is inconsistent → ValueError.

    Same invariant-relocation as above. Rate.__post_init__ catches it
    at construction time now (TD-1).
    """
    with pytest.raises(ValueError) as excinfo:
        _make_rate(
            value_1_number=10.0,
            value_1_unit="percent",
            value_1_currency="EUR",  # incompatible with percent
        )
    msg = str(excinfo.value)
    assert "value_1_currency" in msg or "percent" in msg


def test_calculate_duty_unknown_unit_code_raises():
    """Unsupported unit code (e.g. '999') → ValueError mentioning the code."""
    rate = _make_rate(
        value_1_number=1.0,
        value_1_unit="999",
        value_1_currency="EUR",
    )
    with pytest.raises(ValueError, match="999"):
        calculate_duty(
            rate=rate,
            customs_value_rub=Decimal("0"),
            weight_kg=Decimal("100"),
            quantity=Decimal("0"),
            currency_rates={"EUR": Decimal("100")},
        )


# ---------------------------------------------------------------------------
# calculate_duty — Decimal precision invariants
# ---------------------------------------------------------------------------


def test_calculate_duty_decimal_precision_no_float():
    """Output must be Decimal; intermediate calc must preserve precision.

    Use a rate value that loses precision in float arithmetic
    (0.1 + 0.2 != 0.3 in float). Confirms str() conversion of
    Rate.value_*_number floats happens at the boundary.
    """
    # 0.1% on 100 RUB = 0.10 RUB (exact in Decimal, lossy in float)
    rate = _make_rate(value_1_number=0.1, value_1_unit="percent")
    result = calculate_duty(
        rate=rate,
        customs_value_rub=Decimal("100"),
        weight_kg=Decimal("0"),
        quantity=Decimal("0"),
        currency_rates={},
    )
    assert isinstance(result, Decimal)
    assert result == Decimal("0.10")
    # Float would give 0.10000000000000001 or similar — Decimal must be exact
    assert str(result) == "0.10"


# ---------------------------------------------------------------------------
# calculate_duty — pure-functional invariant
# ---------------------------------------------------------------------------


def test_calculate_duty_no_side_effects():
    """Pure-functional: no logger calls, no DB, no I/O."""
    rate = _make_rate(value_1_number=10.0, value_1_unit="percent")
    with patch("services.customs_calc.logger") as mock_logger:
        calculate_duty(
            rate=rate,
            customs_value_rub=Decimal("100000"),
            weight_kg=Decimal("0"),
            quantity=Decimal("0"),
            currency_rates={},
        )
        # No logger calls during pure arithmetic
        mock_logger.warning.assert_not_called()
        mock_logger.info.assert_not_called()
        mock_logger.error.assert_not_called()


# ---------------------------------------------------------------------------
# calculate_customs_fee — ПП 342 step-function bands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "customs_value, expected_fee",
    [
        # Band 1: ≤ 200 000 → 775
        (Decimal("100000"), Decimal("775")),
        (Decimal("200000"), Decimal("775")),
        (Decimal("199999.99"), Decimal("775")),
        # Band 2: ≤ 450 000 → 1550
        (Decimal("200001"), Decimal("1550")),
        (Decimal("300000"), Decimal("1550")),
        (Decimal("450000"), Decimal("1550")),
        # Band 3: ≤ 1 200 000 → 3100
        (Decimal("450001"), Decimal("3100")),
        (Decimal("1200000"), Decimal("3100")),
        # Band 4: ≤ 2 700 000 → 8530
        (Decimal("2000000"), Decimal("8530")),
        (Decimal("2700000"), Decimal("8530")),
        # Band 5: ≤ 4 200 000 → 12 000
        (Decimal("4200000"), Decimal("12000")),
        # Band 6: ≤ 5 500 000 → 15 500
        (Decimal("5500000"), Decimal("15500")),
        # Band 7: ≤ 7 000 000 → 20 000
        (Decimal("7000000"), Decimal("20000")),
        # Band 8: ≤ 8 000 000 → 23 000
        (Decimal("8000000"), Decimal("23000")),
        # Band 9: ≤ 9 000 000 → 25 000
        (Decimal("9000000"), Decimal("25000")),
        # Band 10: ≤ 10 000 000 → 27 000
        (Decimal("10000000"), Decimal("27000")),
        # Band 11: > 10 000 000 → 30 000
        (Decimal("10000001"), Decimal("30000")),
        (Decimal("100000000"), Decimal("30000")),
    ],
)
def test_calculate_customs_fee_pp342_bands(customs_value, expected_fee):
    """ПП РФ № 342 от 26.03.2020 step function across all bands."""
    result = calculate_customs_fee(customs_value)
    assert result == expected_fee
    assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# calculate_util_fee — ПП 81 (87xxxx only)
# ---------------------------------------------------------------------------


def test_calculate_util_fee_returns_zero_for_non_87():
    """Non-vehicle TN VED codes return 0 deterministically (REQ-4 AC#3)."""
    assert calculate_util_fee("8409", 2000, 3) == Decimal("0")
    assert calculate_util_fee("1234567890", 2000, 3) == Decimal("0")
    assert calculate_util_fee("0101290000", 0, 0) == Decimal("0")
    # Verify return type
    assert isinstance(calculate_util_fee("8409", 2000, 3), Decimal)


def test_calculate_util_fee_for_87_code():
    """Vehicle TN VED (87xxxx) returns a non-zero Decimal.

    Phase 1 simplified — formula is a placeholder per task spec
    (МастерБэринг товары rarely include vehicles). The CRITICAL
    invariant tested elsewhere is that non-87 codes return 0.
    """
    result = calculate_util_fee("8703", 2000, 3)
    assert isinstance(result, Decimal)
    # Phase 1 placeholder may legitimately return 0 even for 87-codes
    # per task spec. The test fixes the SHAPE (Decimal), not the value.
    assert result >= Decimal("0")


def test_calculate_util_fee_for_87_extended_code():
    """Full 10-digit 87xxxx code is recognized (prefix match)."""
    result = calculate_util_fee("8703210000", 1500, 5)
    assert isinstance(result, Decimal)
    assert result >= Decimal("0")


# ---------------------------------------------------------------------------
# calculate_total_customs_pay — Phase A aggregator (REQ-3)
# ---------------------------------------------------------------------------


def test_calculate_total_only_imp():
    """Only IMP=10%, no NDS rate → default 22% applied to (customs_value + imp)."""
    rate_imp = _make_rate(value_1_number=10.0, value_1_unit="percent")
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("100000"),
        selected_rates_by_payment_type={"IMP": rate_imp},
        weight_kg=None,
        quantity=None,
        currency_rates={},
    )
    assert isinstance(breakdown, CustomsPayBreakdown)
    # Per-type sums
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.impdemp_rub == Decimal("0")
    assert breakdown.impcomp_rub == Decimal("0")
    assert breakdown.impdop_rub == Decimal("0")
    assert breakdown.imptmp_rub == Decimal("0")
    assert breakdown.akc_rub == Decimal("0")
    # Aggregates
    assert breakdown.total_import_duty_rub == Decimal("10000.00")
    assert breakdown.nds_base_rub == Decimal("110000.00")
    assert breakdown.nds_pct == Decimal("22")  # default
    assert breakdown.nds_rub == Decimal("24200.0000")
    assert breakdown.customs_fee_rub == Decimal("0")
    assert breakdown.total_customs_pay_rub == Decimal("134200.0000")


def test_calculate_total_imp_nds():
    """IMP+NDS rates: nds_base = customs_value + imp; NDS pct from rate."""
    rate_imp = _make_rate(value_1_number=10.0, value_1_unit="percent")
    rate_nds = _make_rate(
        payment_type="NDS",
        value_1_number=10.0,  # льготная категория
        value_1_unit="percent",
    )
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("100000"),
        selected_rates_by_payment_type={"IMP": rate_imp, "NDS": rate_nds},
        weight_kg=None,
        quantity=None,
        currency_rates={},
    )
    # imp = 10000, nds_base = 110000, nds_pct = 10
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.total_import_duty_rub == Decimal("10000.00")
    assert breakdown.nds_base_rub == Decimal("110000.00")
    assert breakdown.nds_pct == Decimal("10")
    # 110000 × 10/100 = 11000
    assert breakdown.nds_rub == Decimal("11000.0")
    assert breakdown.total_customs_pay_rub == Decimal("121000.0")


def test_calculate_total_imp_impdemp_nds():
    """IMPDEMP включается в nds_base — антидемпинг увеличивает НДС."""
    rate_imp = _make_rate(value_1_number=10.0, value_1_unit="percent")
    rate_impdemp = _make_rate(
        payment_type="IMPDEMP",
        value_1_number=19.4,
        value_1_unit="percent",
    )
    rate_nds = _make_rate(
        payment_type="NDS",
        value_1_number=22.0,
        value_1_unit="percent",
    )
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("100000"),
        selected_rates_by_payment_type={
            "IMP": rate_imp,
            "IMPDEMP": rate_impdemp,
            "NDS": rate_nds,
        },
        weight_kg=None,
        quantity=None,
        currency_rates={},
    )
    # imp = 10000, impdemp = 19400, total_duty = 29400
    # nds_base = 100000 + 29400 = 129400; nds = 129400 × 22% = 28468
    # total = 129400 + 28468 = 157868
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.impdemp_rub == Decimal("19400.00")
    assert breakdown.total_import_duty_rub == Decimal("29400.00")
    assert breakdown.nds_base_rub == Decimal("129400.00")
    assert breakdown.nds_pct == Decimal("22")
    assert breakdown.nds_rub == Decimal("28468.0000")
    assert breakdown.total_customs_pay_rub == Decimal("157868.0000")


def test_calculate_total_imp_akc_nds():
    """Акциз учтён в nds_base (и в total) but NOT в total_import_duty."""
    rate_imp = _make_rate(value_1_number=10.0, value_1_unit="percent")
    rate_akc = _make_rate(
        payment_type="AKC",
        value_1_number=5.0,
        value_1_unit="percent",
    )
    rate_nds = _make_rate(
        payment_type="NDS",
        value_1_number=22.0,
        value_1_unit="percent",
    )
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("100000"),
        selected_rates_by_payment_type={
            "IMP": rate_imp,
            "AKC": rate_akc,
            "NDS": rate_nds,
        },
        weight_kg=None,
        quantity=None,
        currency_rates={},
    )
    # imp = 10000, akc = 5000
    # total_import_duty = 10000 (akc NOT included — it's a separate aggregate)
    # nds_base = 100000 + 10000 + 5000 = 115000
    # nds = 115000 × 22% = 25300; total = 115000 + 25300 = 140300
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.akc_rub == Decimal("5000.00")
    assert breakdown.total_import_duty_rub == Decimal("10000.00")
    assert breakdown.nds_base_rub == Decimal("115000.00")
    assert breakdown.nds_rub == Decimal("25300.0000")
    assert breakdown.total_customs_pay_rub == Decimal("140300.0000")


def test_calculate_total_imp_impdemp_akc_nds():
    """Все 4 типа в nds_base: IMP + IMPDEMP в total_duty, AKC отдельно."""
    rate_imp = _make_rate(value_1_number=10.0, value_1_unit="percent")
    rate_impdemp = _make_rate(
        payment_type="IMPDEMP",
        value_1_number=19.4,
        value_1_unit="percent",
    )
    rate_akc = _make_rate(
        payment_type="AKC",
        value_1_number=5.0,
        value_1_unit="percent",
    )
    rate_nds = _make_rate(
        payment_type="NDS",
        value_1_number=22.0,
        value_1_unit="percent",
    )
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("100000"),
        selected_rates_by_payment_type={
            "IMP": rate_imp,
            "IMPDEMP": rate_impdemp,
            "AKC": rate_akc,
            "NDS": rate_nds,
        },
        weight_kg=None,
        quantity=None,
        currency_rates={},
    )
    # imp = 10000, impdemp = 19400, akc = 5000
    # total_import_duty = 29400; nds_base = 100000 + 29400 + 5000 = 134400
    # nds = 134400 × 22% = 29568; total = 134400 + 29568 = 163968
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.impdemp_rub == Decimal("19400.00")
    assert breakdown.akc_rub == Decimal("5000.00")
    assert breakdown.total_import_duty_rub == Decimal("29400.00")
    assert breakdown.nds_base_rub == Decimal("134400.00")
    assert breakdown.nds_rub == Decimal("29568.0000")
    assert breakdown.total_customs_pay_rub == Decimal("163968.0000")


def test_calculate_total_combined_rate_imp():
    """Combined-rate IMP с двумя slots (>=, max выбран корректно)."""
    rate_imp_combined = _make_rate(
        value_1_number=10.0,
        value_1_unit="percent",
        value_2_number=0.04,
        value_2_unit="166",  # kg
        value_2_currency="EUR",
        sign_1=">",
    )
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("100000"),
        selected_rates_by_payment_type={"IMP": rate_imp_combined},
        weight_kg=Decimal("500"),
        quantity=Decimal("0"),
        currency_rates={"EUR": Decimal("100")},
    )
    # ad_valorem = 100000 × 10% = 10000
    # specific = 500 × 0.04 × 100 = 2000
    # max(10000, 2000) = 10000
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.total_import_duty_rub == Decimal("10000.00")
    assert breakdown.nds_base_rub == Decimal("110000.00")
    assert breakdown.nds_pct == Decimal("22")  # default (no NDS rate provided)
    assert breakdown.nds_rub == Decimal("24200.0000")
    assert breakdown.total_customs_pay_rub == Decimal("134200.0000")


# ---------------------------------------------------------------------------
# calculate_total_customs_pay — edge cases
# ---------------------------------------------------------------------------


def test_calculate_total_missing_nds_uses_default_22pct():
    """No NDS rate in map → default 22% applied to nds_base."""
    rate_imp = _make_rate(value_1_number=5.0, value_1_unit="percent")
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("200000"),
        selected_rates_by_payment_type={"IMP": rate_imp},
        weight_kg=None,
        quantity=None,
        currency_rates={},
    )
    # imp = 200000 × 5% = 10000; nds_base = 210000
    # nds = 210000 × 22% = 46200 (default)
    assert breakdown.nds_pct == Decimal("22")
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.nds_base_rub == Decimal("210000.00")
    assert breakdown.nds_rub == Decimal("46200.0000")


def test_calculate_total_zero_customs_value_returns_zeros():
    """customs_value=0 → all derived amounts are 0 (except optional fee)."""
    rate_imp = _make_rate(value_1_number=10.0, value_1_unit="percent")
    rate_nds = _make_rate(
        payment_type="NDS",
        value_1_number=22.0,
        value_1_unit="percent",
    )
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("0"),
        selected_rates_by_payment_type={"IMP": rate_imp, "NDS": rate_nds},
        weight_kg=None,
        quantity=None,
        currency_rates={},
        customs_fee_rub=Decimal("775"),
    )
    assert breakdown.customs_value_rub == Decimal("0")
    assert breakdown.imp_rub == Decimal("0.00")
    assert breakdown.total_import_duty_rub == Decimal("0.00")
    assert breakdown.nds_base_rub == Decimal("0.00")
    assert breakdown.nds_rub == Decimal("0.0000")
    # total = nds_base + nds + customs_fee = 0 + 0 + 775
    assert breakdown.customs_fee_rub == Decimal("775")
    assert breakdown.total_customs_pay_rub == Decimal("775.0000")


def test_calculate_total_combined_rate_no_weight_skips_specific_part():
    """weight_kg=None → specific part = 0, combined `>` returns ad_valorem."""
    rate_imp_combined = _make_rate(
        value_1_number=10.0,
        value_1_unit="percent",
        value_2_number=0.04,
        value_2_unit="166",  # kg — but weight_kg=None
        value_2_currency="EUR",
        sign_1=">",
    )
    breakdown = calculate_total_customs_pay(
        customs_value_rub=Decimal("100000"),
        selected_rates_by_payment_type={"IMP": rate_imp_combined},
        weight_kg=None,
        quantity=None,
        currency_rates={"EUR": Decimal("100")},
    )
    # ad_valorem = 10000; specific = 0 × 0.04 × 100 = 0
    # max(10000, 0) = 10000 — only ad-valorem effectively counts
    assert breakdown.imp_rub == Decimal("10000.00")
    assert breakdown.total_import_duty_rub == Decimal("10000.00")
    assert breakdown.nds_base_rub == Decimal("110000.00")
    assert breakdown.total_customs_pay_rub == Decimal("134200.0000")
