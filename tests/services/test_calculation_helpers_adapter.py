"""Tests for build_calculation_inputs() customs adapter switch (REQ-4).

Covers the Q1 decision: when an item carries a `_resolved_customs_rate`
sourced from Alta (`alta-live` | `alta-revalidate`), the new
`services.customs_calc.calculate_duty()` must compute the duty in RUB
which is then converted to a percent for the calc engine's
`import_tariff` field. Otherwise the legacy `_calc_combined_duty()`
formula must be used unchanged.

The locked files (calculation_engine.py, calculation_models.py,
calculation_mapper.py) are NOT touched by this adapter.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from services.alta_client import Rate
from services.calculation_helpers import build_calculation_inputs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_minimal_variables() -> dict:
    """Minimum keys required by build_calculation_inputs."""
    return {
        "currency_of_quote": "RUB",
        "markup": Decimal("15"),
        "supplier_discount": Decimal("0"),
        "offer_incoterms": "DDP",
        "delivery_time": 30,
        "seller_company": "МАСТЕР БЭРИНГ ООО",
        "offer_sale_type": "поставка",
        "logistics_supplier_hub": Decimal("0"),
        "logistics_hub_customs": Decimal("0"),
        "logistics_customs_client": Decimal("0"),
        "brokerage_hub": Decimal("0"),
        "brokerage_hub_currency": "RUB",
        "brokerage_customs": Decimal("0"),
        "brokerage_customs_currency": "RUB",
        "warehousing_at_customs": Decimal("0"),
        "warehousing_at_customs_currency": "RUB",
        "customs_documentation": Decimal("0"),
        "customs_documentation_currency": "RUB",
        "brokerage_extra": Decimal("0"),
        "brokerage_extra_currency": "RUB",
        "advance_from_client": Decimal("100"),
        "advance_to_supplier": Decimal("100"),
        "time_to_advance": 0,
        "time_to_advance_on_receiving": 0,
        "dm_fee_type": "fixed",
        "dm_fee_value": Decimal("0"),
        "dm_fee_currency": "RUB",
        "exchange_rate": Decimal("1.0"),
    }


def _make_minimal_item(**overrides) -> dict:
    """Build an item dict with sane defaults for the adapter tests."""
    item = {
        "id": "item-1",
        "purchase_price_original": Decimal("1000"),
        "purchase_currency": "RUB",
        "quantity": 1,
        "weight_in_kg": Decimal("10"),
        "customs_code": "1234567890",
        "customs_duty": Decimal("5"),       # legacy: 5 percent
        "customs_duty_per_kg": Decimal("0"),
        "supplier_country": "RU",
        "price_includes_vat": False,
        "markup": Decimal("15"),
        "supplier_discount": Decimal("0"),
    }
    item.update(overrides)
    return item


def _make_alta_rate(source: str = "alta-live") -> Rate:
    """Build a Rate dataclass with alta-resolved provenance."""
    return Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal="C:643",
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        source=source,
    )


# ---------------------------------------------------------------------------
# Adapter switch — alta-resolved path
# ---------------------------------------------------------------------------


def test_build_calculation_inputs_uses_customs_calc_when_alta_resolved():
    """When item carries a Rate with source='alta-live', the new
    customs_calc.calculate_duty() must drive the import_tariff value
    (NOT the legacy _calc_combined_duty formula).
    """
    item = _make_minimal_item(_resolved_customs_rate=_make_alta_rate("alta-live"))
    variables = _make_minimal_variables()

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.customs_calc.calculate_duty") as mock_calc:
            mock_calc.return_value = Decimal("100.00")  # arbitrary RUB duty
            result = build_calculation_inputs([item], variables)

    # customs_calc.calculate_duty MUST have been invoked
    assert mock_calc.called, (
        "Adapter must call customs_calc.calculate_duty() when item carries "
        "a Rate with source in {'alta-live','alta-revalidate'}"
    )
    # Single calc input produced
    assert len(result) == 1


def test_build_calculation_inputs_alta_revalidate_also_routes_to_customs_calc():
    """source='alta-revalidate' must trigger the same adapter branch."""
    item = _make_minimal_item(_resolved_customs_rate=_make_alta_rate("alta-revalidate"))
    variables = _make_minimal_variables()

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.customs_calc.calculate_duty") as mock_calc:
            mock_calc.return_value = Decimal("50.00")
            build_calculation_inputs([item], variables)

    assert mock_calc.called


# ---------------------------------------------------------------------------
# Adapter switch — legacy fallback paths
# ---------------------------------------------------------------------------


def test_build_calculation_inputs_falls_back_to_legacy_when_no_resolved_rate():
    """Item without `_resolved_customs_rate` key → legacy formula."""
    item = _make_minimal_item()  # no _resolved_customs_rate
    variables = _make_minimal_variables()

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.customs_calc.calculate_duty") as mock_calc:
            result = build_calculation_inputs([item], variables)

    assert not mock_calc.called, (
        "Items without _resolved_customs_rate must use the legacy formula "
        "(_calc_combined_duty), not customs_calc"
    )
    assert len(result) == 1


def test_build_calculation_inputs_falls_back_to_legacy_for_manual_rate():
    """Rate with source='manual' must NOT trigger customs_calc — only
    'alta-live' / 'alta-revalidate' do (Q1 decision).
    """
    manual_rate = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal=None,
        valid_from=date(2026, 1, 1),
        value_1_number=5.0,
        value_1_unit="percent",
        source="manual",
    )
    item = _make_minimal_item(_resolved_customs_rate=manual_rate)
    variables = _make_minimal_variables()

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.customs_calc.calculate_duty") as mock_calc:
            build_calculation_inputs([item], variables)

    assert not mock_calc.called, (
        "Rates with source='manual' must use the legacy formula — only "
        "Alta-resolved rates ('alta-live', 'alta-revalidate') trigger "
        "customs_calc"
    )


def test_build_calculation_inputs_falls_back_to_legacy_for_none_source():
    """Rate without `source` (None default) must NOT trigger customs_calc."""
    rate_no_source = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal=None,
        valid_from=date(2026, 1, 1),
        value_1_number=5.0,
        value_1_unit="percent",
        # source defaults to None
    )
    item = _make_minimal_item(_resolved_customs_rate=rate_no_source)
    variables = _make_minimal_variables()

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.customs_calc.calculate_duty") as mock_calc:
            build_calculation_inputs([item], variables)

    assert not mock_calc.called
