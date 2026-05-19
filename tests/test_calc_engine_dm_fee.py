"""Эталон-independent regression for the AG16 percentage-DM-fee formula.

Phase 2 of the Calculation Engine verification fixed a real engine bug in
``calculation_engine.py`` phase11 (the per-product sales-price phase). For a
**percentage** DM fee the engine used to compute

    AG16 = BD16 · AB16 · pct          # OLD, BUGGY

— the percentage applied to the *per-product* COGS ``AB16``. The эталон
Excel form ("комиссия %" — ``VLOOKUP(AG3, AF4:AG7, 2)``) instead applies the
percentage to the **quote-level** COGS total ``AB13 = Σ AB16`` and only then
distributes it to the product by ``BD16``:

    AG16 = BD16 · pct · AB13          # FIXED, matches the эталон

For a single-product quote the two formulas coincide (``AB13 == AB16``), so
the bug was invisible there. It only shows on a **multi-product** quote whose
products have **different** per-product COGS — then ``Σ(BD16·AB16) ≠ AB13``
and the old formula is wrong per-product.

The only multi-product эталон coverage of this fix was ``forma_nds22_18`` —
now an ``ACCEPTED_DIFFERENCES`` entry in the golden-master suite because its
эталон .xlsm has a blank seller company (its BH2 omits RU VAT), so it can no
longer hard-assert the AG16 value. This test is therefore the **эталон-
independent** guard: it builds a synthetic multi-product quote from scratch,
runs the production engine, and asserts the engine's ``dm_fee`` equals the
FIXED эталон formula — and would FAIL if the engine reverted to the old bug.

Input construction is cribbed from ``test_calculation.py`` (the engine's own
single-product test) — same model objects, same field meanings.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from calculation_engine import calculate_multiproduct_quote
from calculation_models import (
    CompanySettings,
    Currency,
    CustomsAndClearance,
    DMFeeType,
    FinancialParams,
    Incoterms,
    LogisticsParams,
    OfferSaleType,
    PaymentTerms,
    ProductInfo,
    QuoteCalculationInput,
    SellerCompany,
    SupplierCountry,
    SystemConfig,
    TaxesAndDuties,
)

# The percentage DM fee under test — 10%, expressed as the engine wants it
# (a whole-number percent; the engine divides by 100 internally).
DM_FEE_PERCENT = Decimal("10")
DM_FEE_FRACTION = DM_FEE_PERCENT / Decimal("100")

# The engine rounds AG16 with ``round_decimal`` (4 decimal places). The
# reference formula below is evaluated in full Decimal precision, so the
# comparison only needs to absorb that ≤5e-5 rounding step — 1e-3 is a tight
# tolerance that still leaves a several-hundred-unit margin against the old
# buggy formula (proven by ``test_fixed_formula_differs_from_old_bug``).
ROUNDING_TOL = Decimal("1e-3")


def _make_product(
    base_price_vat: str,
    quantity: int,
    weight: str,
    customs_code: str,
    markup: str,
) -> QuoteCalculationInput:
    """Build one synthetic product input — cribbed from ``test_calculation.py``.

    Every quote-level setting is identical across the products of one test
    quote (same FinancialParams/PaymentTerms/etc. shape as Test 1 in
    ``test_calculation.py``); only the per-product price, quantity, weight,
    customs code and markup vary, which is enough to give the products
    DIFFERENT per-product COGS ``AB16`` — the condition under which the AG16
    bug shows.

    The DM fee is a **percentage** fee (``DMFeeType.PERCENTAGE``) — the
    branch this regression guards. Currencies are uniform USD so the engine
    runs currency-agnostically (see ``test_calculation.py`` header).
    """
    product = ProductInfo(
        base_price_VAT=Decimal(base_price_vat),
        quantity=quantity,
        weight_in_kg=Decimal(weight),
        currency_of_base_price=Currency.USD,
        customs_code=customs_code,
    )
    financial = FinancialParams(
        currency_of_quote=Currency.USD,
        exchange_rate_base_price_to_quote=Decimal("1"),
        supplier_discount=Decimal("0"),
        markup=Decimal(markup),
        rate_forex_risk=Decimal("3"),
        dm_fee_type=DMFeeType.PERCENTAGE,
        dm_fee_value=DM_FEE_PERCENT,
    )
    logistics = LogisticsParams(
        supplier_country=SupplierCountry.CHINA,
        offer_incoterms=Incoterms.DDP,
        delivery_time=30,
        delivery_date=date.today(),
        logistics_supplier_hub=Decimal("100.00"),
        logistics_hub_customs=Decimal("0.00"),
        logistics_customs_client=Decimal("0.00"),
    )
    taxes = TaxesAndDuties(
        import_tariff=Decimal("0"),
        excise_tax=Decimal("0"),
        util_fee=Decimal("0"),
    )
    payment = PaymentTerms(
        advance_from_client=Decimal("100"),
        advance_to_supplier=Decimal("100"),
        time_to_advance=0,
        advance_on_loading=Decimal("0"),
        time_to_advance_loading=0,
        advance_on_going_to_country_destination=Decimal("0"),
        time_to_advance_going_to_country_destination=0,
        advance_on_customs_clearance=Decimal("0"),
        time_to_advance_on_customs_clearance=0,
        time_to_advance_on_receiving=0,
    )
    customs = CustomsAndClearance(
        brokerage_hub=Decimal("0.00"),
        brokerage_customs=Decimal("0.00"),
        warehousing_at_customs=Decimal("0.00"),
        customs_documentation=Decimal("0.00"),
        brokerage_extra=Decimal("0.00"),
    )
    company = CompanySettings(
        seller_company=SellerCompany.MASTER_BEARING_RU,
        offer_sale_type=OfferSaleType.SUPPLY,
    )
    system = SystemConfig(
        rate_fin_comm=Decimal("2"),
        rate_loan_interest_annual=Decimal("0.25"),
        rate_insurance=Decimal("0.00047"),
        customs_logistics_pmt_due=10,
    )
    return QuoteCalculationInput(
        product=product,
        financial=financial,
        logistics=logistics,
        taxes=taxes,
        payment=payment,
        customs=customs,
        company=company,
        system=system,
    )


def _multiproduct_quote() -> list[QuoteCalculationInput]:
    """A 2-product synthetic quote whose products have DIFFERENT COGS.

    Product 1 is small (cheap, light); product 2 is large (5x the price, 4x
    the weight) — so their per-product COGS ``AB16`` differ substantially
    and ``Σ(BD16·AB16) ≠ AB13``. Both carry the same 10% percentage DM fee.
    """
    return [
        _make_product("1000.00", 10, "5.0", "8708913509", "15"),
        _make_product("5000.00", 4, "20.0", "8482101900", "20"),
    ]


def test_percentage_dm_fee_matches_etalon_formula():
    """Engine ``dm_fee`` (AG16) == the эталон formula ``BD16 · pct · AB13``.

    The эталон "комиссия %" formula applies the percentage to the
    quote-level COGS total ``AB13 = Σ AB16`` and distributes it by ``BD16``.
    For each product the engine's ``dm_fee`` must reproduce that, within the
    4dp ``round_decimal`` rounding tolerance.
    """
    products = _multiproduct_quote()
    results = calculate_multiproduct_quote(products)

    assert len(results) == 2, "synthetic quote must yield two product results"

    # AB13 — the quote-level COGS total, summed from the engine's own
    # per-product COGS (this is what the эталон applies the percentage to).
    ab13 = sum((r.cogs_per_product for r in results), Decimal("0"))
    assert ab13 > 0, "quote-level COGS total must be positive"

    for idx, result in enumerate(results, start=1):
        bd16 = result.distribution_base  # S16 / S13
        # FIXED эталон formula — percentage on the quote-level COGS total.
        expected_ag16 = bd16 * DM_FEE_FRACTION * ab13
        actual_ag16 = result.dm_fee

        assert abs(actual_ag16 - expected_ag16) <= ROUNDING_TOL, (
            f"product {idx}: engine dm_fee (AG16) = {actual_ag16} does not "
            f"match the эталон formula BD16·pct·AB13 = {expected_ag16} "
            f"(BD16={bd16}, pct={DM_FEE_FRACTION}, AB13={ab13})"
        )


def test_dm_fee_does_not_match_old_buggy_formula():
    """Engine ``dm_fee`` (AG16) must NOT equal the OLD buggy formula.

    The pre-Phase-2 bug computed ``AG16 = BD16 · AB16 · pct`` — the
    percentage on the *per-product* COGS ``AB16`` instead of the quote-level
    total ``AB13``. This test fails loudly if the engine ever reverts to
    that: for this synthetic multi-product quote the buggy result is several
    hundred currency units away from the correct one (per product), so the
    gap dwarfs the 4dp rounding tolerance.
    """
    products = _multiproduct_quote()
    results = calculate_multiproduct_quote(products)

    for idx, result in enumerate(results, start=1):
        bd16 = result.distribution_base
        ab16 = result.cogs_per_product  # per-product COGS — the OLD base
        buggy_ag16 = bd16 * ab16 * DM_FEE_FRACTION
        actual_ag16 = result.dm_fee

        assert abs(actual_ag16 - buggy_ag16) > ROUNDING_TOL, (
            f"product {idx}: engine dm_fee (AG16) = {actual_ag16} matches "
            f"the OLD buggy formula BD16·AB16·pct = {buggy_ag16} — the "
            f"phase11 percentage-DM-fee fix has regressed"
        )


def test_fixed_formula_differs_from_old_bug():
    """Numeric proof: the FIXED and OLD formulas DIVERGE for this input.

    This is the test's keystone — it confirms the synthetic multi-product
    quote actually distinguishes the two formulas. If this assertion ever
    held only by accident (``Σ(BD16·AB16) == AB13``), the two tests above
    would be vacuous. Here the products have deliberately different COGS, so
    ``BD16·pct·AB13`` and ``BD16·AB16·pct`` differ by hundreds of units —
    far more than the 4dp rounding tolerance — for every product.
    """
    products = _multiproduct_quote()
    results = calculate_multiproduct_quote(products)

    ab13 = sum((r.cogs_per_product for r in results), Decimal("0"))

    # The products must NOT all share the same per-product COGS — otherwise
    # the two formulas would coincide and the regression test is vacuous.
    distinct_cogs = {r.cogs_per_product for r in results}
    assert len(distinct_cogs) > 1, (
        "synthetic products must have DIFFERENT per-product COGS for the "
        "AG16 bug to be observable"
    )

    for idx, result in enumerate(results, start=1):
        bd16 = result.distribution_base
        ab16 = result.cogs_per_product
        fixed_ag16 = bd16 * DM_FEE_FRACTION * ab13
        buggy_ag16 = bd16 * ab16 * DM_FEE_FRACTION

        assert abs(fixed_ag16 - buggy_ag16) > ROUNDING_TOL, (
            f"product {idx}: the FIXED formula ({fixed_ag16}) and the OLD "
            f"buggy formula ({buggy_ag16}) do not differ — this input does "
            f"not distinguish the fix from the bug, the regression test "
            f"would be meaningless"
        )
