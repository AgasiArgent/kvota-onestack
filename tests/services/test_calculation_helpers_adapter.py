"""Tests for build_calculation_inputs() customs adapter switch (REQ-4).

Covers the Q1 decision: when an item carries a `_resolved_customs_rate`
sourced from Alta (`alta-live` | `alta-revalidate`), the new
`services.customs_calc.calculate_duty()` must compute the duty in RUB
which is then converted to a percent for the calc engine's
`import_tariff` field. Otherwise the legacy `_calc_combined_duty()`
formula must be used unchanged.

Phase A (Req 3 customs-tariff-completeness): adapter migrated to call
`calculate_total_customs_pay()` aggregator instead of per-rate
`calculate_duty()`. The locked engine still receives a single
`import_tariff` percent — sourced from `total_import_duty_rub` rather
than a single Rate. Migration regression contract: each existing
fixture must produce identical numeric output (tolerance Decimal('0.01')
RUB) under old vs new path. New antidumping fixtures verify the
aggregator correctly raises the percent when IMPDEMP is added.

The locked files (calculation_engine.py, calculation_models.py,
calculation_mapper.py) are NOT touched by this adapter.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from services.alta_client import Rate
from services.calculation_helpers import _resolve_import_tariff_pct, build_calculation_inputs
from services.customs_calc import calculate_duty


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


# ---------------------------------------------------------------------------
# Phase A migration regression — old per-rate path vs new aggregator path
#
# Contract: для each existing single-rate fixture, the percent emitted
# by `_resolve_import_tariff_pct()` after migration must match what the
# pre-migration per-rate path would have produced (tolerance 0.01₽).
# The "old path" simulator below recomputes the percent the way the
# pre-migration code did:  duty_rub = calculate_duty(IMP_rate, ...);
# pct = duty_rub × 100 / customs_value_rub.
# ---------------------------------------------------------------------------


_REGRESSION_TOLERANCE_RUB = Decimal("0.01")


def _old_path_pct(
    rate: Rate,
    customs_value_rub: Decimal,
    weight_kg: Decimal,
    quantity: Decimal,
    currency_rates: dict,
) -> Decimal:
    """Replay the pre-migration per-rate calc — single Rate → percent.

    Mirrors the pre-Phase-A `_resolve_import_tariff_pct()` body: one
    `calculate_duty()` invocation, then RUB → percent conversion. Used
    by migration regression tests to assert numeric parity with the new
    aggregator path on every existing single-IMP fixture.
    """
    duty_rub = calculate_duty(
        rate=rate,
        customs_value_rub=customs_value_rub,
        weight_kg=weight_kg,
        quantity=quantity,
        currency_rates=currency_rates,
    )
    if customs_value_rub <= 0:
        return Decimal("0")
    return duty_rub * Decimal("100") / customs_value_rub


def test_migration_regression_simple_imp_rate_matches_old_path():
    """Single IMP ad-valorem 10% → percent identical under old vs new."""
    rate_imp = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal="C:643",
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        source="alta-live",
    )
    item = _make_minimal_item(
        _resolved_customs_rate=rate_imp,
        purchase_price_original=Decimal("1000"),
        purchase_currency="RUB",
        quantity=1,
        weight_in_kg=Decimal("10"),
    )
    customs_value = Decimal("1000")  # 1000 RUB × 1
    weight = Decimal("10")
    qty = Decimal("1")

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value={}):
            new_pct = Decimal(str(_resolve_import_tariff_pct(item, "RUB")))

    old_pct = _old_path_pct(rate_imp, customs_value, weight, qty, {})

    # Convert percents → absolute rub at this customs_value to compare in
    # the spec's 0.01₽ tolerance unit (rather than abstract percent diff).
    new_rub = new_pct * customs_value / Decimal("100")
    old_rub = old_pct * customs_value / Decimal("100")
    assert abs(new_rub - old_rub) <= _REGRESSION_TOLERANCE_RUB, (
        f"Migration regression: simple IMP — old={old_rub}, new={new_rub}"
    )
    # Sanity: 10% of 1000 = 100 RUB
    assert abs(new_rub - Decimal("100.00")) <= _REGRESSION_TOLERANCE_RUB


def test_migration_regression_specific_per_kg_rate_matches_old_path():
    """Specific per-kg rate → percent identical under old vs new."""
    rate_imp_specific = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal="C:643",
        valid_from=date(2026, 1, 1),
        value_1_number=0.04,
        value_1_unit="166",  # kg
        value_1_currency="EUR",
        source="alta-live",
    )
    item = _make_minimal_item(
        _resolved_customs_rate=rate_imp_specific,
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
        quantity=1,
        weight_in_kg=Decimal("500"),
    )
    customs_value = Decimal("100000")
    weight = Decimal("500")
    qty = Decimal("1")
    fx_rates = {"EUR": Decimal("100")}

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value=fx_rates):
            new_pct = Decimal(str(_resolve_import_tariff_pct(item, "RUB")))

    old_pct = _old_path_pct(rate_imp_specific, customs_value, weight, qty, fx_rates)

    new_rub = new_pct * customs_value / Decimal("100")
    old_rub = old_pct * customs_value / Decimal("100")
    assert abs(new_rub - old_rub) <= _REGRESSION_TOLERANCE_RUB
    # Sanity: 500 × 0.04 × 100 = 2000 RUB
    assert abs(new_rub - Decimal("2000.00")) <= _REGRESSION_TOLERANCE_RUB


def test_migration_regression_combined_rate_max_matches_old_path():
    """Combined rate with sign='>' → max(ad-valorem, specific) preserved."""
    rate_imp_combined = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal="C:643",
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        value_2_number=0.04,
        value_2_unit="166",
        value_2_currency="EUR",
        sign_1=">",
        source="alta-live",
    )
    item = _make_minimal_item(
        _resolved_customs_rate=rate_imp_combined,
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
        quantity=1,
        weight_in_kg=Decimal("500"),
    )
    customs_value = Decimal("100000")
    weight = Decimal("500")
    qty = Decimal("1")
    fx_rates = {"EUR": Decimal("100")}

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value=fx_rates):
            new_pct = Decimal(str(_resolve_import_tariff_pct(item, "RUB")))

    old_pct = _old_path_pct(rate_imp_combined, customs_value, weight, qty, fx_rates)

    new_rub = new_pct * customs_value / Decimal("100")
    old_rub = old_pct * customs_value / Decimal("100")
    assert abs(new_rub - old_rub) <= _REGRESSION_TOLERANCE_RUB
    # Sanity: max(100000×10%=10000, 500×0.04×100=2000) = 10000
    assert abs(new_rub - Decimal("10000.00")) <= _REGRESSION_TOLERANCE_RUB


def test_migration_regression_zero_customs_value_matches_old_path():
    """Zero base price → 0% under both paths (no division-by-zero)."""
    rate_imp = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal="C:643",
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        source="alta-live",
    )
    item = _make_minimal_item(
        _resolved_customs_rate=rate_imp,
        purchase_price_original=Decimal("0"),
    )

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value={}):
            new_pct = _resolve_import_tariff_pct(item, "RUB")

    assert new_pct == 0.0
    # Old path also returns 0% via the `customs_value_rub <= 0` guard
    old_pct = _old_path_pct(rate_imp, Decimal("0"), Decimal("0"), Decimal("0"), {})
    assert old_pct == Decimal("0")


def test_migration_regression_alta_revalidate_source_also_matches():
    """source='alta-revalidate' goes through the same aggregator branch."""
    rate_imp = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal="C:643",
        valid_from=date(2026, 1, 1),
        value_1_number=7.5,
        value_1_unit="percent",
        source="alta-revalidate",
    )
    item = _make_minimal_item(
        _resolved_customs_rate=rate_imp,
        purchase_price_original=Decimal("2000"),
        purchase_currency="RUB",
        quantity=1,
        weight_in_kg=Decimal("5"),
    )
    customs_value = Decimal("2000")

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value={}):
            new_pct = Decimal(str(_resolve_import_tariff_pct(item, "RUB")))

    old_pct = _old_path_pct(
        rate_imp, customs_value, Decimal("5"), Decimal("1"), {}
    )

    new_rub = new_pct * customs_value / Decimal("100")
    old_rub = old_pct * customs_value / Decimal("100")
    assert abs(new_rub - old_rub) <= _REGRESSION_TOLERANCE_RUB
    # Sanity: 7.5% of 2000 = 150
    assert abs(new_rub - Decimal("150.00")) <= _REGRESSION_TOLERANCE_RUB


# ---------------------------------------------------------------------------
# Phase A — antidumping (IMPDEMP) flows through the aggregator
#
# These two fixtures verify Req 3: antidumping correctly enters the
# total_import_duty (and therefore the engine's import_tariff percent),
# previously dropped under the per-rate IMP-only path.
# ---------------------------------------------------------------------------


def test_phase_a_antidumping_increases_total_vs_imp_only_baseline():
    """Adding IMPDEMP rate raises the percent above IMP-only baseline."""
    rate_imp = Rate(
        tnved_code="7304110008",
        payment_type="IMP",
        country_or_areal="C:804",  # Ukraine
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        source="alta-live",
    )
    rate_impdemp = Rate(
        tnved_code="7304110008",
        payment_type="IMPDEMP",
        country_or_areal="C:804",
        valid_from=date(2026, 1, 1),
        value_1_number=19.4,
        value_1_unit="percent",
        source="alta-live",
    )

    # Baseline — IMP only
    item_baseline = _make_minimal_item(
        _resolved_rates_by_payment_type={"IMP": rate_imp},
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
    )
    # With antidumping
    item_with_demp = _make_minimal_item(
        _resolved_rates_by_payment_type={"IMP": rate_imp, "IMPDEMP": rate_impdemp},
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
    )

    customs_value = Decimal("100000")

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value={}):
            pct_baseline = Decimal(str(_resolve_import_tariff_pct(item_baseline, "RUB")))
            pct_with_demp = Decimal(str(_resolve_import_tariff_pct(item_with_demp, "RUB")))

    rub_baseline = pct_baseline * customs_value / Decimal("100")
    rub_with_demp = pct_with_demp * customs_value / Decimal("100")

    # Baseline: 10% of 100000 = 10000
    assert abs(rub_baseline - Decimal("10000.00")) <= _REGRESSION_TOLERANCE_RUB
    # With antidumping: (10% + 19.4%) of 100000 = 29400
    assert abs(rub_with_demp - Decimal("29400.00")) <= _REGRESSION_TOLERANCE_RUB
    # Antidumping raised the duty by 19400 RUB (the impdemp portion)
    assert abs((rub_with_demp - rub_baseline) - Decimal("19400.00")) <= _REGRESSION_TOLERANCE_RUB


def test_phase_a_antidumping_via_legacy_single_rate_shape():
    """Backwards compat: single legacy IMPDEMP rate also flows through.

    Even when only the legacy single-rate `_resolved_customs_rate` shape
    is populated (no `_resolved_rates_by_payment_type`), an IMPDEMP rate
    must still be summed into the engine's import_tariff via the
    aggregator. The wrapper key is taken from `rate.payment_type`.
    """
    rate_impdemp = Rate(
        tnved_code="7304110008",
        payment_type="IMPDEMP",
        country_or_areal="C:804",
        valid_from=date(2026, 1, 1),
        value_1_number=19.4,
        value_1_unit="percent",
        source="alta-live",
    )
    item = _make_minimal_item(
        _resolved_customs_rate=rate_impdemp,
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
    )
    customs_value = Decimal("100000")

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value={}):
            new_pct = Decimal(str(_resolve_import_tariff_pct(item, "RUB")))

    new_rub = new_pct * customs_value / Decimal("100")
    # Single IMPDEMP rate → 19.4% of 100000 = 19400 RUB
    assert abs(new_rub - Decimal("19400.00")) <= _REGRESSION_TOLERANCE_RUB


# ---------------------------------------------------------------------------
# Phase A — multi-rate shape and edge cases
# ---------------------------------------------------------------------------


def test_phase_a_multi_rate_shape_drops_manual_rates():
    """Manual rates inside the multi-rate dict are filtered out.

    Only Alta-resolved rates (source ∈ {alta-live, alta-revalidate})
    contribute to the aggregator. Manual rates inside the same dict are
    ignored — they don't contaminate the engine's import_tariff.
    """
    rate_imp_alta = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal=None,
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        source="alta-live",
    )
    rate_impdemp_manual = Rate(
        tnved_code="1234567890",
        payment_type="IMPDEMP",
        country_or_areal=None,
        valid_from=date(2026, 1, 1),
        value_1_number=99.0,
        value_1_unit="percent",
        source="manual",  # NOT alta-resolved
    )
    item = _make_minimal_item(
        _resolved_rates_by_payment_type={
            "IMP": rate_imp_alta,
            "IMPDEMP": rate_impdemp_manual,
        },
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
    )
    customs_value = Decimal("100000")

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value={}):
            pct = Decimal(str(_resolve_import_tariff_pct(item, "RUB")))

    rub = pct * customs_value / Decimal("100")
    # Only the alta-live IMP (10%) counts → 10000 RUB; manual IMPDEMP dropped
    assert abs(rub - Decimal("10000.00")) <= _REGRESSION_TOLERANCE_RUB


def test_phase_a_no_weight_or_qty_combined_rate_uses_ad_valorem_only():
    """Per Task 3 contract: weight_kg=None / qty=None coerced to 0.

    Combined rate `>` returns max(ad_valorem, 0) = ad_valorem when
    weight is missing — no exception. Tested at the helpers boundary
    rather than directly on calculate_total_customs_pay (already
    covered in test_customs_calc.py) to verify the adapter passes None
    through correctly.
    """
    rate_imp_combined = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal=None,
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        value_2_number=0.04,
        value_2_unit="166",
        value_2_currency="EUR",
        sign_1=">",
        source="alta-live",
    )
    # weight_in_kg explicitly omitted → safe_decimal(None) = 0
    item = _make_minimal_item(
        _resolved_customs_rate=rate_imp_combined,
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
        weight_in_kg=None,
        quantity=None,
    )
    customs_value = Decimal("100000")
    fx_rates = {"EUR": Decimal("100")}

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.currency_service.get_latest_rates", return_value=fx_rates):
            pct = Decimal(str(_resolve_import_tariff_pct(item, "RUB")))

    rub = pct * customs_value / Decimal("100")
    # max(100000 × 10% = 10000, 0 × 0.04 × 100 = 0) = 10000
    assert abs(rub - Decimal("10000.00")) <= _REGRESSION_TOLERANCE_RUB


def test_phase_a_aggregator_invoked_once_per_item():
    """Single aggregator call per item — not per rate (perf invariant)."""
    rate_imp = Rate(
        tnved_code="1234567890",
        payment_type="IMP",
        country_or_areal=None,
        valid_from=date(2026, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
        source="alta-live",
    )
    rate_impdemp = Rate(
        tnved_code="1234567890",
        payment_type="IMPDEMP",
        country_or_areal=None,
        valid_from=date(2026, 1, 1),
        value_1_number=19.4,
        value_1_unit="percent",
        source="alta-live",
    )
    item = _make_minimal_item(
        _resolved_rates_by_payment_type={"IMP": rate_imp, "IMPDEMP": rate_impdemp},
        purchase_price_original=Decimal("100000"),
        purchase_currency="RUB",
    )
    variables = _make_minimal_variables()

    with patch("services.currency_service.convert_amount", return_value=Decimal("1")):
        with patch("services.customs_calc.calculate_total_customs_pay") as mock_agg:
            from services.customs_calc import CustomsPayBreakdown
            mock_agg.return_value = CustomsPayBreakdown(
                customs_value_rub=Decimal("100000"),
                imp_rub=Decimal("10000"),
                impdemp_rub=Decimal("19400"),
                impcomp_rub=Decimal("0"),
                impdop_rub=Decimal("0"),
                imptmp_rub=Decimal("0"),
                akc_rub=Decimal("0"),
                total_import_duty_rub=Decimal("29400"),
                nds_base_rub=Decimal("129400"),
                nds_pct=Decimal("22"),
                nds_rub=Decimal("28468"),
                customs_fee_rub=Decimal("0"),
                total_customs_pay_rub=Decimal("157868"),
            )
            build_calculation_inputs([item], variables)

    # Aggregator called exactly once for this item
    assert mock_agg.call_count == 1
    # Verify both Alta rates were passed to the aggregator
    call_kwargs = mock_agg.call_args.kwargs
    selected = call_kwargs["selected_rates_by_payment_type"]
    assert "IMP" in selected
    assert "IMPDEMP" in selected
    assert selected["IMP"] is rate_imp
    assert selected["IMPDEMP"] is rate_impdemp
