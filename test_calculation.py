#!/usr/bin/env python3
"""
Calculation Engine Test Runner

Compares calculation engine output against Excel reference values.
Based on Test 1 from all_test_values_complete.txt:
- Baseline SUPPLY RU->Turkey DDP 50% advance (FIXED DM fee)

IMPORTANT: The calculation engine is currency-agnostic.
All input values must be in the same currency before calling the engine.

Usage:
    python test_calculation.py
"""

from decimal import Decimal
from datetime import date

# Import calculation engine and models
from calculation_engine import calculate_single_product_quote
from calculation_models import (
    QuoteCalculationInput,
    ProductInfo,
    FinancialParams,
    LogisticsParams,
    TaxesAndDuties,
    PaymentTerms,
    CustomsAndClearance,
    CompanySettings,
    SystemConfig,
    Currency,
    SupplierCountry,
    SellerCompany,
    OfferSaleType,
    Incoterms,
    DMFeeType
)


# ============================================================================
# TEST 1: Baseline SUPPLY RU->Turkey DDP 50% advance (FIXED DM fee)
# ============================================================================

def create_test1_input() -> QuoteCalculationInput:
    """
    Create input for Test 1 from Excel reference.

    Key inputs from test file:
    - base_price_VAT = 1200.00 (implies N16 = 1000.00 with 20% Turkish VAT)
    - quantity = 10
    - weight_in_kg = 25.0
    - currency_of_base_price = RUB (Q16 exchange rate = 0.0105 RUB->USD)
    - supplier_discount = 10%
    - markup = 15%
    - supplier_country = Турция
    - offer_incoterms = DDP
    - delivery_time = 30
    - advance_from_client = 50%
    """

    # Product info - base price in RUB with 20% VAT
    product = ProductInfo(
        base_price_VAT=Decimal("1200.00"),  # K16 - includes Turkish 20% VAT
        quantity=10,  # E16
        weight_in_kg=Decimal("25.0"),  # G16
        currency_of_base_price=Currency.RUB,  # J16
        customs_code="8708913509"  # W16
    )

    # Financial params
    # Q16 = 0.0105 is the exchange rate from RUB to USD
    # The engine expects divisor format for Phase 1: R16 = P16 / Q16
    financial = FinancialParams(
        currency_of_quote=Currency.USD,  # Internal calculation always in USD
        exchange_rate_base_price_to_quote=Decimal("0.0105"),  # Q16 - RUB to USD rate
        supplier_discount=Decimal("10"),  # O16 - 10%
        markup=Decimal("15"),  # AC16 - 15%
        rate_forex_risk=Decimal("3"),  # AH11 - 3% (admin setting)
        dm_fee_type=DMFeeType.FIXED,  # AG3
        dm_fee_value=Decimal("1000")  # AG7
    )

    # Logistics params - costs assumed in USD (quote currency)
    logistics = LogisticsParams(
        supplier_country=SupplierCountry.TURKEY,  # L16
        offer_incoterms=Incoterms.DDP,  # D7
        delivery_time=30,  # D9
        delivery_date=date.today(),
        logistics_supplier_hub=Decimal("1500.00"),  # W2 - already in USD
        logistics_hub_customs=Decimal("800.00"),  # W3 - already in USD
        logistics_customs_client=Decimal("500.00")  # W4 - already in USD
    )

    # Taxes and duties
    taxes = TaxesAndDuties(
        import_tariff=Decimal("5"),  # X16 - 5%
        excise_tax=Decimal("0"),  # Z16
        util_fee=Decimal("0")
    )

    # Payment terms
    payment = PaymentTerms(
        advance_from_client=Decimal("50"),  # J5 - 50%
        advance_to_supplier=Decimal("100"),  # D11 - 100%
        time_to_advance=7,  # K5
        advance_on_loading=Decimal("0"),
        time_to_advance_loading=0,
        advance_on_going_to_country_destination=Decimal("0"),
        time_to_advance_going_to_country_destination=0,
        advance_on_customs_clearance=Decimal("0"),
        time_to_advance_on_customs_clearance=0,
        time_to_advance_on_receiving=15  # K9
    )

    # Customs and clearance - costs in USD
    customs = CustomsAndClearance(
        brokerage_hub=Decimal("200.00"),  # W5
        brokerage_customs=Decimal("500.00"),  # W6
        warehousing_at_customs=Decimal("100.00"),  # W7
        customs_documentation=Decimal("200.00"),  # W8
        brokerage_extra=Decimal("50.00")  # W9
    )

    # Company settings
    company = CompanySettings(
        seller_company=SellerCompany.MASTER_BEARING_RU,  # D5
        offer_sale_type=OfferSaleType.SUPPLY  # D6
    )

    # System config (admin controlled)
    system = SystemConfig(
        rate_fin_comm=Decimal("2"),  # 2%
        rate_loan_interest_annual=Decimal("0.25"),  # 25% annual = 0.00069 daily
        rate_insurance=Decimal("0.00047"),
        customs_logistics_pmt_due=10
    )

    return QuoteCalculationInput(
        product=product,
        financial=financial,
        logistics=logistics,
        taxes=taxes,
        payment=payment,
        customs=customs,
        company=company,
        system=system
    )


# Expected values from Test 1
TEST1_EXPECTED = {
    "N16": Decimal("1000.00"),      # Purchase price without VAT
    "P16": Decimal("900.00"),       # After discount
    "R16": Decimal("85714.29"),     # Per unit in quote currency
    "S16": Decimal("857142.90"),    # Total purchase price
    "T16": Decimal("2800.00"),      # Logistics first leg
    "U16": Decimal("1243.20"),      # Logistics last leg
    "V16": Decimal("4043.20"),      # Total logistics
    "Y16": Decimal("47142.86"),     # Customs fee
    "AY16": Decimal("942857.20"),   # Internal sale price total
    "BH6": Decimal("1049142.91"),   # Supplier payment needed
    "BH4": Decimal("1051998.91"),   # Total before forwarding
    "BJ11": Decimal("12872.12"),    # Total financing cost
    "BL5": Decimal("6694.54"),      # Credit sales interest
    "BA16": Decimal("12872.12"),    # Initial financing per product
    "BB16": Decimal("6694.54"),     # Credit interest per product
    "AB16": Decimal("927895.62"),   # COGS per product
    "AA16": Decimal("92789.56"),    # COGS per unit
    "AF16": Decimal("139184.34"),   # Profit
    "AG16": Decimal("1000.00"),     # DM fee
    "AD16": Decimal("106708.00"),   # Sale price/unit (excl financial)
    "AJ16": Decimal("112348.75"),   # Sales price per unit (no VAT)
    "AK16": Decimal("1123487.50"),  # Sales price total (no VAT)
    "AL16": Decimal("1348185.00"),  # FINAL PRICE (with VAT)
    "AP16": Decimal("26697.49"),    # Net VAT payable
    "AQ16": Decimal("0.00"),        # Transit commission
}


def compare_values(actual: Decimal, expected: Decimal, name: str, tolerance: Decimal = Decimal("0.01")) -> bool:
    """Compare two values with tolerance and print result."""
    diff = abs(actual - expected)
    passed = diff <= tolerance

    status = "PASS" if passed else "FAIL"
    print(f"  {name:6s}: {actual:>15.2f} vs {expected:>15.2f}  [{status}]  (diff: {diff:.2f})")

    return passed


def run_test1():
    """Run Test 1 and compare results."""
    print("=" * 80)
    print("TEST 1: Baseline SUPPLY RU->Turkey DDP 50% advance (FIXED DM fee)")
    print("=" * 80)
    print()

    # Create input
    calc_input = create_test1_input()

    # Run calculation
    print("Running calculation...")
    try:
        result = calculate_single_product_quote(calc_input)
    except Exception as e:
        print(f"ERROR: Calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("Calculation complete!")
    print()

    # Compare key results
    print("Comparing results against Excel reference:")
    print("-" * 80)

    all_passed = True

    # Map result fields to Excel cell names
    comparisons = [
        ("N16", result.purchase_price_no_vat, TEST1_EXPECTED["N16"], "Purchase price without VAT"),
        ("P16", result.purchase_price_after_discount, TEST1_EXPECTED["P16"], "After discount"),
        ("R16", result.purchase_price_per_unit_quote_currency, TEST1_EXPECTED["R16"], "Per unit in quote currency"),
        ("S16", result.purchase_price_total_quote_currency, TEST1_EXPECTED["S16"], "Total purchase price"),
        ("T16", result.logistics_first_leg, TEST1_EXPECTED["T16"], "Logistics first leg"),
        ("U16", result.logistics_last_leg, TEST1_EXPECTED["U16"], "Logistics last leg"),
        ("V16", result.logistics_total, TEST1_EXPECTED["V16"], "Total logistics"),
        ("Y16", result.customs_fee, TEST1_EXPECTED["Y16"], "Customs fee"),
        ("AY16", result.internal_sale_price_total, TEST1_EXPECTED["AY16"], "Internal sale price total"),
        ("AB16", result.cogs_per_product, TEST1_EXPECTED["AB16"], "COGS per product"),
        ("AA16", result.cogs_per_unit, TEST1_EXPECTED["AA16"], "COGS per unit"),
        ("AF16", result.profit, TEST1_EXPECTED["AF16"], "Profit"),
        ("AG16", result.dm_fee, TEST1_EXPECTED["AG16"], "DM fee"),
        ("AD16", result.sale_price_per_unit_excl_financial, TEST1_EXPECTED["AD16"], "Sale price/unit (excl fin)"),
        ("AJ16", result.sales_price_per_unit_no_vat, TEST1_EXPECTED["AJ16"], "Sales price/unit (no VAT)"),
        ("AK16", result.sales_price_total_no_vat, TEST1_EXPECTED["AK16"], "Sales price total (no VAT)"),
        ("AL16", result.sales_price_total_with_vat, TEST1_EXPECTED["AL16"], "FINAL PRICE (with VAT)"),
        ("AP16", result.vat_net_payable, TEST1_EXPECTED["AP16"], "Net VAT payable"),
        ("AQ16", result.transit_commission, TEST1_EXPECTED["AQ16"], "Transit commission"),
        ("BH6", result.quote_level_supplier_payment, TEST1_EXPECTED["BH6"], "Supplier payment needed"),
        ("BJ11", result.quote_level_total_financing_cost, TEST1_EXPECTED["BJ11"], "Total financing cost"),
        ("BL5", result.quote_level_credit_sales_interest, TEST1_EXPECTED["BL5"], "Credit sales interest"),
        ("BA16", result.financing_cost_initial, TEST1_EXPECTED["BA16"], "Initial financing"),
        ("BB16", result.financing_cost_credit, TEST1_EXPECTED["BB16"], "Credit interest"),
    ]

    passed = 0
    failed = 0

    print(f"\n{'Cell':6s}  {'Actual':>15s}  {'Expected':>15s}  {'Diff':>10s}  {'%Diff':>8s}  {'Result':6s}  Description")
    print("-" * 95)

    for cell, actual, expected, desc in comparisons:
        if actual is None:
            actual = Decimal("0")
        diff = actual - expected
        pct_diff = (diff / expected * 100) if expected != 0 else Decimal("0")
        is_pass = abs(pct_diff) < Decimal("1.0")  # Within 1% tolerance

        status = "PASS" if is_pass else "FAIL"
        if is_pass:
            passed += 1
        else:
            failed += 1

        print(f"{cell:6s}  {float(actual):>15.2f}  {float(expected):>15.2f}  {float(diff):>10.2f}  {float(pct_diff):>7.2f}%  {status:6s}  {desc}")

    print("-" * 95)
    print(f"\nSummary: {passed} passed, {failed} failed out of {len(comparisons)} comparisons")
    print(f"Pass rate: {passed/len(comparisons)*100:.1f}%")

    return all_passed


def test_calculation_engine_import():
    """Test that we can import the calculation engine."""
    print("Testing calculation engine import...")
    try:
        from calculation_engine import calculate_single_product_quote
        print("  Import successful!")
        return True
    except ImportError as e:
        print(f"  ERROR: Import failed: {e}")
        return False


def test_models_import():
    """Test that we can import the models."""
    print("Testing models import...")
    try:
        from calculation_models import QuoteCalculationInput
        print("  Import successful!")
        return True
    except ImportError as e:
        print(f"  ERROR: Import failed: {e}")
        return False


def main():
    """Run all tests."""
    print()
    print("=" * 80)
    print("CALCULATION ENGINE TEST SUITE")
    print("=" * 80)
    print()

    # Test imports
    if not test_models_import():
        print("\nFATAL: Cannot import models. Aborting.")
        return 1

    if not test_calculation_engine_import():
        print("\nFATAL: Cannot import calculation engine. Aborting.")
        return 1

    print()

    # Run Test 1
    try:
        run_test1()
    except Exception as e:
        print(f"\nERROR: Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
