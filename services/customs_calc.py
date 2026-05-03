"""Customs duty arithmetic — REQ-4 customs-phase-1.

Pure-functional module: no DB queries, no network calls, no file I/O.
Inputs are explicit; output is `Decimal` rounded to 2 places.

Three rate types supported (per Alta Такса 3-slot model):

  * Ad-valorem  — `value_1_unit == 'percent'`
                  duty = customs_value × value_1_number / 100

  * Specific    — `value_1_unit ∈ unit-codes`
                  duty = unit_quantity × value_1_number × currency_rate
                  where unit_quantity comes from weight_kg or quantity
                  depending on the OKEI unit code.

  * Combined    — slot 1 (ad-valorem) + slot 2 (specific):
                  sign_1 == '>'  →  max(ad_valorem, specific)  (default)
                  sign_1 == '+'  →  ad_valorem + specific

Decimal precision (REQ-4 AC#5): All arithmetic uses Decimal. Floats from
`Rate.value_*_number` are converted via `Decimal(str(...))` at the
boundary to avoid binary float artifacts. Final result is quantized to
2 places using ROUND_HALF_UP.

The calc engine (`calculation_engine.py`, `calculation_models.py`,
`calculation_mapper.py`) is NEVER touched. Integration into the engine
flows through `services/calculation_helpers.py:build_calculation_inputs()`
adapter — this module only computes; the adapter wires the result.

Reference: `.kiro/specs/customs-phase-1-rates-and-measures/{requirements,design,decisions}.md`
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from services.alta_client import Rate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TWO_PLACES = Decimal("0.01")
_HUNDRED = Decimal("100")
_ZERO = Decimal("0")

# OKEI unit code whitelist — REQ-4 AC#6 (Phase 1 scope: МастерБэринг товары
# are mostly bearings, sold per kg or per piece). Liquid-volume codes are
# omitted intentionally — adding them later requires careful caller
# contract review (caller must pass `quantity` in the unit the rate
# expects, or the helper must perform the conversion).
_UNIT_KG = "166"          # килограмм
_UNIT_PIECE = "796"       # штука

_SUPPORTED_UNIT_CODES = frozenset({_UNIT_KG, _UNIT_PIECE})

# ПП РФ № 342 от 26.03.2020 — таможенные сборы за совершение таможенных
# операций. Step function: each (threshold, fee) means "if customs_value
# is ≤ threshold, the fee is `fee` rubles". Last band catches values
# above 10 000 000.
#
# verified 2026-05-01, проверять раз в год — источник: pravo.gov.ru
# (постановление № 342 в редакции на дату миграции 298).
_PP342_BANDS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("200000"),    Decimal("775")),
    (Decimal("450000"),    Decimal("1550")),
    (Decimal("1200000"),   Decimal("3100")),
    (Decimal("2700000"),   Decimal("8530")),
    (Decimal("4200000"),   Decimal("12000")),
    (Decimal("5500000"),   Decimal("15500")),
    (Decimal("7000000"),   Decimal("20000")),
    (Decimal("8000000"),   Decimal("23000")),
    (Decimal("9000000"),   Decimal("25000")),
    (Decimal("10000000"),  Decimal("27000")),
)
_PP342_TOP_FEE = Decimal("30000")

# ПП РФ № 81 — утилизационный сбор. Phase 1 scope: only TN VED 87xxxx
# (vehicles). MasterBearing товары are почти никогда транспортные средства
# — Phase 1 ставит deterministic Decimal('0') invariant для всех остальных
# кодов и оставляет placeholder для 87xxxx. Реальная формула будет
# доделана в follow-up задаче, когда появится конкретный пример utilization
# fee на бирках MasterBearing.
_UTIL_FEE_VEHICLE_PREFIX = "87"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: float | int | Decimal | None) -> Decimal:
    """Convert a numeric value to Decimal preserving the input string form.

    `Decimal(str(float_value))` is the standard way to avoid binary float
    artifacts when promoting `Rate.value_*_number: float` to Decimal —
    `Decimal(0.1)` = 0.1000000000000000055..., `Decimal(str(0.1))` = 0.1.
    """
    if value is None:
        return _ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    """Round to 2 decimal places using HALF_UP."""
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _resolve_unit_quantity(
    unit_code: str,
    weight_kg: Decimal,
    quantity: Decimal,
) -> Decimal:
    """Map an OKEI unit code to the quantity to multiply against.

    Whitelist for Phase 1:
        '166' (kg) → weight_kg
        '796' (шт) → quantity

    Liquid-volume codes (111 = л, 112 = 1000 л) are intentionally
    excluded — adding them requires the caller to pass `quantity` in
    the unit the rate expects, or this helper to perform a conversion.
    Phase 1 scope (МастерБэринг — bearings) does not need them.

    Raises `ValueError` for any other code so unsupported rates fail
    loudly rather than silently miscalculating.
    """
    if unit_code == _UNIT_KG:
        return weight_kg
    if unit_code == _UNIT_PIECE:
        return quantity
    raise ValueError(
        f"Unsupported unit code: {unit_code!r}. "
        f"Phase 1 supports only {sorted(_SUPPORTED_UNIT_CODES)} "
        f"(166=kg, 796=шт). Liquid-volume codes (111, 112) and others "
        f"are out of scope for МастерБэринг товары."
    )


def _validate_slot_consistency(
    slot_label: str,
    unit: str | None,
    currency: str | None,
) -> None:
    """Catch obviously inconsistent rate shapes early (REQ-4 AC#4).

    Examples of inconsistency:
        - percent rate has a currency set (currency only applies to
          specific rates measured in foreign units)
        - specific rate has no currency
    """
    if unit == "percent" and currency is not None:
        raise ValueError(
            f"{slot_label}: percent rate must not carry "
            f"{slot_label}_currency (got {currency!r})"
        )
    if unit is not None and unit != "percent" and currency is None:
        raise ValueError(
            f"{slot_label}: specific rate (unit={unit!r}) requires "
            f"{slot_label}_currency to be set"
        )


def _ad_valorem_amount(
    value_number: float | None,
    customs_value_rub: Decimal,
) -> Decimal:
    """Compute ad-valorem duty = customs_value × percent / 100."""
    pct = _to_decimal(value_number)
    return customs_value_rub * pct / _HUNDRED


def _specific_amount(
    value_number: float | None,
    unit: str,
    currency: str,
    weight_kg: Decimal,
    quantity: Decimal,
    currency_rates: dict[str, Decimal],
) -> Decimal:
    """Compute specific duty = unit_quantity × value × currency_rate."""
    unit_quantity = _resolve_unit_quantity(unit, weight_kg, quantity)
    if currency not in currency_rates:
        raise ValueError(
            f"Currency {currency!r} not present in currency_rates "
            f"(available: {sorted(currency_rates)})"
        )
    fx = _to_decimal(currency_rates[currency])
    val = _to_decimal(value_number)
    return unit_quantity * val * fx


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_duty(
    rate: Rate,
    customs_value_rub: Decimal,
    weight_kg: Decimal,
    quantity: Decimal,
    currency_rates: dict[str, Decimal],
) -> Decimal:
    """Compute duty amount in RUB for a single Rate.

    Supports three rate shapes:
      * Ad-valorem (slot 1 only, unit='percent')
      * Specific  (slot 1 only, unit=OKEI code with currency)
      * Combined  (slot 1 ad-valorem + slot 2 specific, sign_1='>' or '+')

    Combined `>` is the default per gotcha #3 — `max(ad_valorem, specific)`
    is the prevailing semantic in the actual Alta dataset.

    Args:
        rate: Alta-resolved Rate dataclass (3-slot model).
        customs_value_rub: Таможенная стоимость в рублях.
        weight_kg: Масса нетто в килограммах (used for unit '166').
        quantity: Количество единиц (used for unit '796').
        currency_rates: Map of ISO currency code → RUB rate.
                        Example: {'EUR': Decimal('100.5'), 'USD': Decimal('92.1')}

    Returns:
        Duty amount in RUB, quantized to 2 decimal places.

    Raises:
        ValueError: on unsupported rate shape (unknown sign, inconsistent
            slot/currency, unsupported OKEI unit code, missing currency
            in `currency_rates`).
    """
    _validate_slot_consistency("value_1", rate.value_1_unit, rate.value_1_currency)

    has_slot_2 = rate.value_2_number is not None
    if has_slot_2:
        _validate_slot_consistency(
            "value_2", rate.value_2_unit, rate.value_2_currency,
        )

    # --- Pure ad-valorem ----------------------------------------------
    if rate.value_1_unit == "percent" and not has_slot_2:
        amount = _ad_valorem_amount(rate.value_1_number, customs_value_rub)
        return _quantize(amount)

    # --- Pure specific ------------------------------------------------
    if rate.value_1_unit != "percent" and not has_slot_2:
        if rate.value_1_unit is None or rate.value_1_currency is None:
            raise ValueError(
                f"Pure-specific rate requires both value_1_unit and "
                f"value_1_currency (got unit={rate.value_1_unit!r}, "
                f"currency={rate.value_1_currency!r})"
            )
        amount = _specific_amount(
            rate.value_1_number,
            rate.value_1_unit,
            rate.value_1_currency,
            weight_kg,
            quantity,
            currency_rates,
        )
        return _quantize(amount)

    # --- Combined (slot 1 ad-valorem + slot 2 specific) ---------------
    if rate.value_1_unit == "percent" and has_slot_2:
        if rate.value_2_unit is None or rate.value_2_currency is None:
            raise ValueError(
                f"Combined rate slot 2 requires both unit and currency "
                f"(got unit={rate.value_2_unit!r}, "
                f"currency={rate.value_2_currency!r})"
            )

        ad_valorem = _ad_valorem_amount(rate.value_1_number, customs_value_rub)
        specific = _specific_amount(
            rate.value_2_number,
            rate.value_2_unit,
            rate.value_2_currency,
            weight_kg,
            quantity,
            currency_rates,
        )

        if rate.sign_1 == ">":
            return _quantize(max(ad_valorem, specific))
        if rate.sign_1 == "+":
            return _quantize(ad_valorem + specific)
        raise ValueError(
            f"Unknown sign_1 in combined rate: {rate.sign_1!r}. "
            f"Supported signs: '>' (max) and '+' (sum)."
        )

    # --- Unsupported shape --------------------------------------------
    raise ValueError(
        f"Unsupported rate shape: value_1_unit={rate.value_1_unit!r}, "
        f"has_slot_2={has_slot_2}"
    )


def calculate_customs_fee(customs_value_rub: Decimal) -> Decimal:
    """Customs processing fee per ПП РФ № 342 от 26.03.2020.

    Step function over customs value in rubles. Bands verified
    2026-05-01 against pravo.gov.ru — re-check annually:

        ≤    200 000 →    775
        ≤    450 000 →   1550
        ≤  1 200 000 →   3100
        ≤  2 700 000 →   8530
        ≤  4 200 000 →  12 000
        ≤  5 500 000 →  15 500
        ≤  7 000 000 →  20 000
        ≤  8 000 000 →  23 000
        ≤  9 000 000 →  25 000
        ≤ 10 000 000 →  27 000
        > 10 000 000 →  30 000

    Args:
        customs_value_rub: Таможенная стоимость в рублях (Decimal).

    Returns:
        Customs fee in RUB (Decimal).
    """
    for threshold, fee in _PP342_BANDS:
        if customs_value_rub <= threshold:
            return fee
    return _PP342_TOP_FEE


def calculate_util_fee(
    tnved_code: str,
    engine_volume_cc: int,
    vehicle_age_years: int,
) -> Decimal:
    """Utilization fee per ПП РФ № 81.

    REQ-4 AC#3: applies ONLY when `tnved_code` starts with '87'
    (vehicles). For every other TN VED group returns Decimal('0')
    deterministically.

    Phase 1 scope note: МастерБэринг товары are bearings — vehicles
    are exceedingly rare. The 87xxxx branch is intentionally a
    placeholder returning Decimal('0') until a real example surfaces;
    the precise ПП 81 formula (depends on vehicle category, engine
    size, age, weight class) will be filled in then.

    The CRITICAL invariant tested in tests/test_customs_calc.py is:
        non-87 codes → Decimal('0')

    Args:
        tnved_code: 10-digit ТН ВЭД code (string).
        engine_volume_cc: Объём двигателя в см³ (placeholder param).
        vehicle_age_years: Возраст ТС в годах (placeholder param).

    Returns:
        Utilization fee in RUB (Decimal). Zero for non-vehicle codes.
    """
    if not tnved_code.startswith(_UTIL_FEE_VEHICLE_PREFIX):
        return _ZERO

    # Phase 1 placeholder — see module docstring. Returning 0 keeps
    # downstream calculation correct for the common case (no util fee
    # billed) until the real ПП 81 formula is wired in. Caller-side
    # contracts (tests, calc engine) accept any non-negative Decimal.
    return _ZERO
