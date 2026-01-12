"""
B2B Quotation Platform - Calculation Engine
Implements 13-phase calculation logic matching Excel formulas.

CURRENCY HANDLING (verified 2025-12-13):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALL CALCULATIONS HAPPEN IN QUOTE CURRENCY, NOT USD!

Flow:
1. Excel upload: Products have various currencies (EUR, USD, TRY, CNY, RUB)
2. Exchange rates: Fetched from CBR API, cross-rates calculated via RUB
3. Conversion: All values converted to quote_currency BEFORE calculation
4. Calculation: All 13 phases compute in quote_currency
5. Storage: DUAL - both quote_currency (primary) and USD (for analytics)
6. Export: Uses quote_currency for client-facing documents

Key variable: currency_of_quote (e.g., "USD", "EUR", "RUB")
Key function: phase1_purchase_price() converts base_price to quote_currency

See: .claude/skills/calculation-engine-guidelines/resources/currency-handling.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional
from datetime import date
import math

from calculation_models import (
    QuoteCalculationInput,
    ProductCalculationResult,
    QuoteCalculationResult,
    SupplierCountry,
    SellerCompany,
    OfferSaleType,
    Incoterms,
    DMFeeType
)


# ============================================================================
# DERIVED VARIABLE MAPPINGS
# ============================================================================

# Seller company → Seller region mapping
SELLER_REGION_MAP = {
    SellerCompany.MASTER_BEARING_RU: "RU",
    SellerCompany.CMTO1_RU: "RU",
    SellerCompany.RAD_RESURS_RU: "RU",
    SellerCompany.TEXCEL_TR: "TR",
    SellerCompany.GESTUS_TR: "TR",
    SellerCompany.UPDOOR_CN: "CN"
}

# Supplier country → VAT rate mapping (M16)
VAT_SELLER_COUNTRY_MAP = {
    SupplierCountry.TURKEY: Decimal("0.20"),
    SupplierCountry.TURKEY_TRANSIT: Decimal("0.00"),
    SupplierCountry.RUSSIA: Decimal("0.22"),  # Updated 2025: Russia VAT increased to 22%
    SupplierCountry.CHINA: Decimal("0.13"),
    SupplierCountry.LITHUANIA: Decimal("0.21"),
    SupplierCountry.LATVIA: Decimal("0.21"),
    SupplierCountry.BULGARIA: Decimal("0.20"),
    SupplierCountry.POLAND: Decimal("0.23"),
    SupplierCountry.EU_CROSS_BORDER: Decimal("0.00"),
    SupplierCountry.UAE: Decimal("0.05"),
    SupplierCountry.OTHER: Decimal("0.00")
}

# (Supplier country, Seller region) → Internal markup mapping (AW16)
# Updated 2025-11-09: New markup percentages based on trade routes
INTERNAL_MARKUP_MAP = {
    (SupplierCountry.TURKEY, "RU"): Decimal("0.02"),  # 2%
    (SupplierCountry.TURKEY, "TR"): Decimal("0.00"),
    (SupplierCountry.TURKEY_TRANSIT, "RU"): Decimal("0.02"),  # 2%
    (SupplierCountry.TURKEY_TRANSIT, "TR"): Decimal("0.00"),
    (SupplierCountry.RUSSIA, "RU"): Decimal("0.00"),
    (SupplierCountry.RUSSIA, "TR"): Decimal("0.00"),
    (SupplierCountry.CHINA, "RU"): Decimal("0.02"),  # 2%
    (SupplierCountry.CHINA, "TR"): Decimal("0.00"),
    (SupplierCountry.LITHUANIA, "RU"): Decimal("0.04"),  # 4%
    (SupplierCountry.LITHUANIA, "TR"): Decimal("0.02"),  # 2%
    (SupplierCountry.LATVIA, "RU"): Decimal("0.04"),  # 4%
    (SupplierCountry.LATVIA, "TR"): Decimal("0.02"),  # 2%
    (SupplierCountry.BULGARIA, "RU"): Decimal("0.04"),  # 4%
    (SupplierCountry.BULGARIA, "TR"): Decimal("0.02"),  # 2%
    (SupplierCountry.POLAND, "RU"): Decimal("0.04"),  # 4%
    (SupplierCountry.POLAND, "TR"): Decimal("0.02"),  # 2%
    (SupplierCountry.EU_CROSS_BORDER, "RU"): Decimal("0.04"),  # 4%
    (SupplierCountry.EU_CROSS_BORDER, "TR"): Decimal("0.02"),  # 2%
    (SupplierCountry.UAE, "RU"): Decimal("0.03"),  # 3%
    (SupplierCountry.UAE, "TR"): Decimal("0.01"),  # 1%
    (SupplierCountry.OTHER, "RU"): Decimal("0.02"),  # 2%
    (SupplierCountry.OTHER, "TR"): Decimal("0.00")
}

# Seller region → Russian VAT rate
RATE_VAT_BY_SELLER_REGION = {
    "RU": Decimal("0.20"),  # 20%
    "TR": Decimal("0.00"),  # Not implemented
    "CN": Decimal("0.00")   # Not implemented
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def round_decimal(value: Decimal, decimal_places: int = 4) -> Decimal:
    """Round decimal to specified places using ROUND_HALF_UP.

    Default is 4 decimal places to match Excel precision (validated 2025-11-28).
    """
    if decimal_places == 4:
        return value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    elif decimal_places == 2:
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    elif decimal_places == 0:
        return value.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    else:
        quantizer = Decimal(10) ** -decimal_places
        return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def get_seller_region(seller_company: SellerCompany) -> str:
    """Derive seller_region from seller_company"""
    return SELLER_REGION_MAP[seller_company]


def get_vat_seller_country(supplier_country: SupplierCountry) -> Decimal:
    """Get VAT rate for supplier country (M16)"""
    return VAT_SELLER_COUNTRY_MAP[supplier_country]


def get_internal_markup(supplier_country: SupplierCountry, seller_region: str) -> Decimal:
    """Get internal markup based on supplier country and seller region (AW16)"""
    return INTERNAL_MARKUP_MAP[(supplier_country, seller_region)]


def get_rate_vat_ru(seller_region: str, delivery_date: Optional[date] = None) -> Decimal:
    """Get Russian VAT rate based on seller region and delivery date.

    VAT Rate Timeline:
    - Before 2026: 20%
    - 2026 onwards: 22% (government mandate effective Jan 1, 2026)

    Args:
        seller_region: Seller region code (RU, TR, CN)
        delivery_date: Expected delivery date (optional for backward compat)

    Returns:
        Decimal: VAT rate (0.20, 0.22 for RU; 0.00 for TR/CN)
    """
    base_rate = RATE_VAT_BY_SELLER_REGION[seller_region]

    # Only adjust Russian VAT (Turkish/Chinese stay at 0%)
    if seller_region == "RU" and delivery_date and delivery_date.year >= 2026:
        return Decimal("0.22")  # 22% for 2026+

    return base_rate  # 20% for <2026 or non-Russian


def calculate_future_value(
    principal: Decimal,
    rate: Decimal,
    periods: int
) -> Decimal:
    """
    Calculate future value with compound interest
    Matches Excel's FV function: FV(rate, nper, , -pv)
    """
    if periods <= 0 or principal <= 0:
        return principal
    
    # FV = PV * (1 + rate)^periods
    multiplier = (Decimal("1") + rate) ** periods
    return round_decimal(principal * multiplier)


# ============================================================================
# PHASE 1: PURCHASE PRICE CALCULATIONS
# ============================================================================

def phase1_purchase_price(
    base_price_VAT: Decimal,
    quantity: int,
    supplier_discount: Decimal,
    exchange_rate: Decimal,
    vat_seller_country: Decimal,
    supplier_country: SupplierCountry
) -> Dict[str, Decimal]:
    """
    Calculate purchase price in quote currency

    Steps: Final-34, Final-35, Final-36, Final-9
    Returns: N16, P16, R16, S16
    """
    # Final-34: N16 = K16 / (1 + M16) - Remove VAT
    # Special case: China prices are already VAT-free
    if supplier_country == SupplierCountry.CHINA:
        N16 = base_price_VAT  # Already VAT-free
    else:
        N16 = round_decimal(base_price_VAT / (Decimal("1") + vat_seller_country))

    # Final-35: P16 = N16 * (1 - O16) - Apply discount
    discount_multiplier = Decimal("1") - (supplier_discount / Decimal("100"))
    P16 = round_decimal(N16 * discount_multiplier)

    # Final-36: R16 = P16 / Q16 - Convert to quote currency per unit
    R16 = round_decimal(P16 / exchange_rate)

    # Final-9: S16 = E16 * R16 - Total purchase price
    S16 = round_decimal(Decimal(quantity) * R16)
    
    return {
        "N16": N16,  # Purchase price no VAT
        "P16": P16,  # After discount
        "R16": R16,  # Per unit in quote currency
        "S16": S16   # Total purchase price
    }


# ============================================================================
# PHASE 2: DISTRIBUTION BASE SETUP
# ============================================================================

def phase2_distribution_base(
    products_S16: List[Decimal]
) -> Tuple[Decimal, List[Decimal]]:
    """
    Calculate distribution base for each product
    
    Steps: Final-33, Final-32
    Returns: S13 (total), List of BD16 (distribution base per product)
    """
    # Final-33: S13 = SUM(S16:S2015)
    S13 = sum(products_S16)
    
    # Final-32: BD16 = S16 / S13 for each product
    BD16_list = [round_decimal(S16 / S13, 6) if S13 > 0 else Decimal("0") for S16 in products_S16]
    
    return S13, BD16_list


# ============================================================================
# PHASE 2.5: INTERNAL PRICING (for insurance calculation)
# ============================================================================

def phase2_5_internal_pricing(
    S16: Decimal,
    quantity: int,
    internal_markup: Decimal
) -> Dict[str, Decimal]:
    """
    Calculate internal sale price (without duties)

    This phase calculates AY16 early so it can be used for insurance calculation
    before Phase 3 (logistics distribution).

    Steps: Final-46, Final-45
    Returns: AX16, AY16

    Created: 2025-11-09 (to resolve Phase 3 → Phase 4 circular dependency)
    """
    # Final-46: AX16 = S16 * (1 + AW16) / E16
    if quantity > 0:
        AX16 = round_decimal(S16 * (Decimal("1") + internal_markup) / Decimal(quantity))
    else:
        AX16 = Decimal("0")

    # Final-45: AY16 = E16 * AX16
    AY16 = round_decimal(Decimal(quantity) * AX16)

    return {
        "AX16": AX16,  # Internal sale price per unit
        "AY16": AY16   # Internal sale price total
    }


# ============================================================================
# PHASE 3: LOGISTICS DISTRIBUTION
# ============================================================================

def phase3_logistics_distribution(
    BD16: Decimal,
    logistics_supplier_hub: Decimal,
    logistics_hub_customs: Decimal,
    logistics_customs_client: Decimal,
    brokerage_hub: Decimal,
    brokerage_customs: Decimal,
    warehousing_at_customs: Decimal,
    customs_documentation: Decimal,
    brokerage_extra: Decimal,
    insurance_per_product: Decimal
) -> Dict[str, Decimal]:
    """
    Distribute logistics and brokerage costs to product

    Steps: Final-10
    Excel formulas (verified 2025-11-28 against test_raschet_multi_currency_correct_rate_2711.xlsm):
    - T13 = W2 + W3 + W5 + W8 (first leg total)
    - U13 = W4 + W6 + W7 + W9 (second leg total)
    - T16 = T13 * BD16 + insurance_per_product
    - U16 = U13 * BD16

    Where:
    - W2 = logistics_supplier_hub (Istanbul → hub)
    - W3 = logistics_hub_customs (hub → RU border)
    - W4 = logistics_customs_client (border → client)
    - W5 = brokerage_hub
    - W6 = brokerage_customs
    - W7 = warehousing_at_customs
    - W8 = customs_documentation
    - W9 = brokerage_extra

    Returns: T16, U16, V16

    Note: insurance_per_product should be pre-calculated as:
          insurance_total = ROUNDUP(AY13_total * rate_insurance, 1)
          insurance_per_product = insurance_total * BD16 (already distributed)
    """
    # T13 = W2 + W3 + W5 + W8 (logistics first leg + brokerage hub + docs)
    T13 = logistics_supplier_hub + logistics_hub_customs + brokerage_hub + customs_documentation

    # U13 = W4 + W6 + W7 + W9 (logistics last leg + brokerage customs + warehousing + extra)
    U13 = logistics_customs_client + brokerage_customs + warehousing_at_customs + brokerage_extra

    # T16 = T13 * BD16 + insurance_per_product
    T16 = round_decimal(T13 * BD16 + insurance_per_product)

    # U16 = U13 * BD16
    U16 = round_decimal(U13 * BD16)

    # V16 = T16 + U16 (total logistics + brokerage)
    V16 = round_decimal(T16 + U16)

    return {
        "T16": T16,  # First leg (logistics + brokerage + insurance)
        "U16": U16,  # Second leg (logistics + brokerage)
        "V16": V16   # Total logistics + brokerage
    }


# ============================================================================
# PHASE 4: DUTIES & VAT RESTORATION
# ============================================================================

def phase4_duties(
    AY16: Decimal,
    T16: Decimal,
    S16: Decimal,
    quantity: int,
    import_tariff: Decimal,
    excise_tax: Decimal,
    weight_in_kg: Decimal,
    vat_seller_country: Decimal,
    offer_incoterms: Incoterms,
    insurance_per_product: Decimal = Decimal("0")
) -> Dict[str, Decimal]:
    """
    Calculate customs duties and VAT restoration

    This phase is called AFTER Phase 3 (logistics) so T16 is available.
    AX16 and AY16 are calculated in Phase 2.5.

    Steps: Final-11, excise calculation, Final-8
    Returns: Y16, Z16, AZ16

    Updated 2025-11-09: Y16 formula changed to import_tariff × (AY16 + T16)
    Updated 2025-11-12: Y16 now includes insurance: import_tariff × (AY16 + T16 + insurance)
    Updated 2025-11-28: BUGFIX - Removed double insurance. T16 already includes insurance from Phase 3.
                        Y16 = import_tariff × (AY16 + T16) where T16 = T13×BD16 + insurance
    """
    # Final-11: Y16 = customs fee
    # BUGFIX 2025-11-28: Insurance is already in T16 (added in Phase 3), don't add again!
    # Y16 = import_tariff × (AY16 + T16) where T16 already contains insurance_per_product
    if offer_incoterms == Incoterms.DDP:
        Y16 = round_decimal((import_tariff / Decimal("100")) * (AY16 + T16))
    else:
        Y16 = Decimal("0")

    # Excise tax: Z16 = excise_tax * weight_in_kg * quantity
    Z16 = round_decimal(excise_tax * weight_in_kg * Decimal(quantity))

    # Final-8: AZ16 = S16 * (1 + M16) - Purchase with supplier VAT
    AZ16 = round_decimal(S16 * (Decimal("1") + vat_seller_country))

    return {
        "Y16": Y16,    # Customs fee (includes logistics T16)
        "Z16": Z16,    # Excise tax
        "AZ16": AZ16   # Purchase with VAT
    }


# ============================================================================
# PHASE 5: SUPPLIER PAYMENT CALCULATION
# ============================================================================

def phase5_supplier_payment(
    AZ13: Decimal,
    T13: Decimal,
    Y13: Decimal,
    Z13: Decimal,
    AO13: Decimal,
    advance_to_supplier: Decimal,
    rate_fin_comm: Decimal
) -> Dict[str, Decimal]:
    """
    Calculate supplier payment amounts

    Steps: Final-23, Final-27
    Excel formulas:
    - BH6 = AZ13 * D11 * (1 + rate_fin_comm)
    - BH4 = SUM(AZ13, T13) * (1 + rate_fin_comm) + Y13 + Z13 + AO13

    Updated 2025-11-09: BH4 now includes customs duties, excise tax, and import VAT

    Returns: BH6, BH4
    """
    # Final-23: BH6 = AZ13 * D11 * (1 + rate_fin_comm)
    advance_multiplier = advance_to_supplier / Decimal("100")
    fin_multiplier = Decimal("1") + (rate_fin_comm / Decimal("100"))
    BH6 = round_decimal(AZ13 * advance_multiplier * fin_multiplier)

    # Final-27: BH4 = SUM(AZ13, T13) * (1 + rate_fin_comm) + Y13 + Z13 + AO13
    # Updated 2025-11-09: Added customs duties (Y13), excise tax (Z13), and import VAT (AO13)
    BH4 = round_decimal((AZ13 + T13) * fin_multiplier + Y13 + Z13 + AO13)

    return {
        "BH6": BH6,  # Supplier payment
        "BH4": BH4   # Total before forwarding (includes duties and VAT)
    }


# ============================================================================
# PHASE 6: REVENUE ESTIMATION (WITHOUT FINANCING)
# ============================================================================

def phase6_revenue_estimation(
    products_AB16_est: List[Decimal],
    markup: Decimal,
    rate_forex_risk: Decimal,
    dm_fee_type: DMFeeType,
    dm_fee_value: Decimal,
    seller_region: str,
    rate_vat_ru: Decimal
) -> Dict[str, Decimal]:
    """
    Estimate revenue WITHOUT financing costs (breaks circular dependency)
    
    Steps: Final-1 (est), Final-20, Indirect COGS, Final-19 (est), Final-18
    Returns: AB13_est, BJ2, BJ3, AC12, BH2
    """
    # Final-1: AB13_est = SUM(AB16_est)
    AB13_est = sum(products_AB16_est)
    
    # Final-20: BJ2 = AB13_est (Direct COGS)
    BJ2 = AB13_est
    
    # Indirect COGS: BJ3
    forex_cost = BJ2 * (rate_forex_risk / Decimal("100"))
    if dm_fee_type == DMFeeType.FIXED:
        dm_cost = dm_fee_value
    else:  # Percentage
        dm_cost = BJ2 * (dm_fee_value / Decimal("100"))
    BJ3 = round_decimal(forex_cost + dm_cost)
    
    # Final-19: AC12 = markup (for now, use input markup)
    AC12 = markup / Decimal("100")  # Convert to decimal
    
    # Final-18: BH2 = (BJ2 * (1 + AC12) + BJ3) * (1 + VAT if RU)
    base_revenue = BJ2 * (Decimal("1") + AC12) + BJ3
    if seller_region == "RU":
        vat_multiplier = Decimal("1") + rate_vat_ru
    else:
        vat_multiplier = Decimal("1")
    BH2 = round_decimal(base_revenue * vat_multiplier)
    
    return {
        "AB13_est": AB13_est,
        "BJ2": BJ2,
        "BJ3": BJ3,
        "AC12": AC12,
        "BH2": BH2
    }


# ============================================================================
# PHASE 7: FINANCING NEEDS & COSTS
# ============================================================================

def phase7_financing_costs(
    BH2: Decimal,
    BH6: Decimal,
    BH4: Decimal,
    advance_from_client: Decimal,
    delivery_time: int,
    customs_logistics_pmt_due: int,
    rate_loan_interest_daily: Decimal,
    additional_payment_milestones: Decimal = Decimal("0")
) -> Dict[str, Decimal]:
    """
    Calculate financing needs and costs

    Steps: Final-17, Final-16, Final-22, Final-24, Final-21,
           Final-15, Final-14 (BJ7), Final-25, Final-14 (BJ10), Final-13
    Returns: BH3, BH7, BH9, BH8, BH10, BI7, BJ7, BI10, BJ10, BJ11

    Updated 2025-11-27:
    - BI7 = BH7 × (1 + rate_loan_interest_daily × D9) (simple interest, delivery time)
    - BH9: Excel formula depends on payment terms type (pmt_1, pmt_2, pmt_3)
      For pmt_3 (most common): BH9 = SUM(J6:J8) * BH2 where J6:J8 are additional milestones
      Default to 0 when no additional milestones specified

    Updated 2025-12-05:
    - BI10 = BH10 × (1 + rate_loan_interest_daily × customs_logistics_pmt_due)
      Uses customs_logistics_pmt_due (helpsheet E27, fixed 10 days) NOT offer_post_pmt_due (K9)
      Excel formula: =BH10+BH10*rate_loan_interest_daily*customs_logistics_pmt_due
    """
    # Final-17: BH3 = BH2 * (J5 / 100)
    BH3 = round_decimal(BH2 * (advance_from_client / Decimal("100")))

    # Final-16: BH7 = IF(BH3>0, IF(BH3>=BH6, 0, BH6-BH3), BH6)
    if BH3 > 0:
        if BH3 >= BH6:
            BH7 = Decimal("0")
        else:
            BH7 = round_decimal(BH6 - BH3)
    else:
        BH7 = BH6

    # Final-22: BH9 = additional payment milestones * BH2
    # Excel: =IFS(pmt_1,0,pmt_2,0,pmt_3,SUM(J6:J8))*BH2
    # For pmt_3 with no additional milestones, this equals 0
    BH9 = round_decimal(additional_payment_milestones * BH2)

    # Final-24: BH8 = BH4 - BH6
    BH8 = round_decimal(BH4 - BH6)

    # Final-21: BH10 = IF((BH9 + IF(BH3>BH6, BH3-BH6, 0)) > BH8, 0, BH8 - (BH9 + IF(BH3>BH6, BH3-BH6, 0)))
    excess_advance = BH3 - BH6 if BH3 > BH6 else Decimal("0")
    remaining_after_advance = BH9 + excess_advance
    if remaining_after_advance > BH8:
        BH10 = Decimal("0")
    else:
        BH10 = round_decimal(BH8 - remaining_after_advance)

    # Final-15: BI7 = BH7 × (1 + rate_loan_interest_daily × D9)
    # Updated 2025-11-09: Simplified to simple interest, only D9 (no K9)
    D9 = delivery_time
    BI7 = round_decimal(BH7 * (Decimal("1") + rate_loan_interest_daily * Decimal(D9)))

    # Final-14: BJ7 = BI7 - BH7
    BJ7 = round_decimal(BI7 - BH7)

    # Final-25: BI10 = BH10 × (1 + rate_loan_interest_daily × customs_logistics_pmt_due)
    # Updated 2025-12-05: Uses customs_logistics_pmt_due (helpsheet E27, fixed ~10 days)
    # NOT offer_post_pmt_due (K9) - Excel formula: =BH10+BH10*rate_loan_interest_daily*customs_logistics_pmt_due
    BI10 = round_decimal(BH10 * (Decimal("1") + rate_loan_interest_daily * Decimal(customs_logistics_pmt_due)))

    # Final-14: BJ10 = BI10 - BH10
    BJ10 = round_decimal(BI10 - BH10)

    # Final-13: BJ11 = BJ7 + BJ10
    BJ11 = round_decimal(BJ7 + BJ10)

    return {
        "BH3": BH3,    # Client advance
        "BH7": BH7,    # Supplier financing need
        "BH9": BH9,    # Remaining % after advance
        "BH8": BH8,    # Amount payable after supplier payment
        "BH10": BH10,  # Operational financing need
        "BI7": BI7,    # FV of supplier financing (simple interest)
        "BJ7": BJ7,    # Supplier financing COST
        "BI10": BI10,  # FV of operational financing (simple interest)
        "BJ10": BJ10,  # Operational financing COST
        "BJ11": BJ11   # TOTAL financing cost
    }


# ============================================================================
# PHASE 8: CREDIT SALES INTEREST
# ============================================================================

def phase8_credit_sales_interest(
    BH4: Decimal,
    BH3: Decimal,
    time_to_advance_on_receiving: int,
    rate_loan_interest_daily: Decimal
) -> Dict[str, Decimal]:
    """
    Calculate interest on delayed payment from client

    Steps: Final-28, Final-29, Final-30
    Returns: BL3, BL4, BL5

    Updated 2025-11-27: BL3 = BH4 - BH3 (not BH2 - BH3)
    Updated 2025-11-27: BL4 uses SIMPLE interest (not compound FV)
                        Excel formula: BL4 = BL3 + BL3 * rate * days
    """
    # Final-28: BL3 = BH4 - BH3 (total before forwarding minus client advance)
    BL3 = round_decimal(BH4 - BH3)

    # Final-29: BL4 = BL3 + BL3 * rate_loan_interest_daily * K9 (SIMPLE interest)
    # Excel: =BL3+BL3*rate_loan_interest_daily*offer_post_pmt_due
    K9 = time_to_advance_on_receiving
    BL4 = round_decimal(BL3 * (Decimal("1") + rate_loan_interest_daily * Decimal(K9)))

    # Final-30: BL5 = BL4 - BL3
    BL5 = round_decimal(BL4 - BL3)
    
    return {
        "BL3": BL3,  # Amount financed
        "BL4": BL4,  # FV with interest
        "BL5": BL5   # Credit interest COST
    }


# ============================================================================
# PHASE 9: DISTRIBUTE FINANCING TO PRODUCTS
# ============================================================================

def phase9_distribute_financing(
    BJ11: Decimal,
    BL5: Decimal,
    BD16: Decimal
) -> Dict[str, Decimal]:
    """
    Allocate financing costs to product
    
    Steps: Final-12, Final-31
    Returns: BA16, BB16
    """
    # Final-12: BA16 = BJ11 * BD16
    BA16 = round_decimal(BJ11 * BD16)
    
    # Final-31: BB16 = BL5 * BD16
    BB16 = round_decimal(BL5 * BD16)
    
    return {
        "BA16": BA16,  # Initial financing per product
        "BB16": BB16   # Credit interest per product
    }


# ============================================================================
# PHASE 10: FINAL COGS (WITH FINANCING)
# ============================================================================

def phase10_final_cogs(
    S16: Decimal,
    V16: Decimal,
    Y16: Decimal,
    Z16: Decimal,
    BA16: Decimal,
    BB16: Decimal,
    quantity: int
) -> Dict[str, Decimal]:
    """
    Calculate complete COGS with financing
    
    Steps: Final-3, Final-37
    Returns: AB16, AA16
    """
    # Final-3: AB16 = ROUND(SUM(S16, V16, Y16, Z16, BA16, BB16), 2)
    AB16 = round_decimal(S16 + V16 + Y16 + Z16 + BA16 + BB16)
    
    # Final-37: AA16 = IFERROR(AB16 / E16, 0)
    if quantity > 0:
        AA16 = round_decimal(AB16 / Decimal(quantity))
    else:
        AA16 = Decimal("0")
    
    return {
        "AB16": AB16,  # COGS per product
        "AA16": AA16   # COGS per unit
    }


# ============================================================================
# PHASE 11: PROFIT & SALES PRICE CALCULATION
# ============================================================================

def phase11_sales_price(
    AB16: Decimal,
    S16: Decimal,
    V16: Decimal,
    quantity: int,
    markup: Decimal,
    BD16: Decimal,
    rate_forex_risk: Decimal,
    dm_fee_type: DMFeeType,
    dm_fee_value: Decimal,
    rate_fin_comm: Decimal,
    AZ16: Decimal,
    internal_markup: Decimal,
    T16: Decimal,
    offer_sale_type: OfferSaleType,
    seller_region: str
) -> Dict[str, Decimal]:
    """
    Calculate profit and final sales price
    
    Steps: Final-4, Final-5, Final-38, Final-6, Final-7, Final-2
    Returns: AF16, AG16, AD16, AE16, AH16, AI16, AJ16, AK16
    """
    # Convert markup to decimal
    AC16 = markup / Decimal("100")
    
    # Final-4: AF16 = Profit
    # IFERROR(ROUND(IFS(offer_sale_type="поставка", AB16, offer_sale_type="транзит", S16) * AC16, 2), 0)
    if offer_sale_type == OfferSaleType.SUPPLY:
        profit_base = AB16
    else:  # транзит
        profit_base = S16
    AF16 = round_decimal(profit_base * AC16)
    
    # Final-5: AG16 = DM fee
    # BD16 * VLOOKUP(AG3, AF4:AG7, 2, FALSE)
    if dm_fee_type == DMFeeType.FIXED:
        AG16 = round_decimal(BD16 * dm_fee_value)
    else:  # Percentage
        # For percentage DM fee, it's based on some base amount
        # Assuming it's based on AB16 (COGS) - verify with Excel
        AG16 = round_decimal(BD16 * AB16 * (dm_fee_value / Decimal("100")))
    
    # Final-38: AD16 = Sale price per unit (excl. financial expenses)
    # Excel formula: IFERROR(ROUND((IFS(offer_sale_type="поставка", AB16, offer_sale_type="транзит", S16) * (1+AC16)) / E16, 2), 0)
    if offer_sale_type == OfferSaleType.SUPPLY:
        price_base = AB16
    else:  # транзит
        price_base = S16  # Excel uses S16 only for transit, NOT S16+V16
    if quantity > 0:
        AD16 = round_decimal((price_base * (Decimal("1") + AC16)) / Decimal(quantity))
    else:
        AD16 = Decimal("0")
    
    # Final-38: AE16 = AD16 * E16
    AE16 = round_decimal(AD16 * Decimal(quantity))
    
    # Final-7: AI16 = Financial agent fee
    # IF(OR(seller_region="TR", offer_sale_type="экспорт"), 0, rate_fin_comm) * SUM(AZ16, AZ16*AW16, T16)
    if seller_region == "TR" or offer_sale_type == OfferSaleType.EXPORT:
        AI16 = Decimal("0")
    else:
        fin_comm_rate = rate_fin_comm / Decimal("100")
        AI16 = round_decimal(fin_comm_rate * (AZ16 + AZ16 * internal_markup + T16))
    
    # Final-6: AH16 = Forex risk reserve
    # SUM(AE16, AG16, AI16) * rate_forex_risk
    forex_rate = rate_forex_risk / Decimal("100")
    AH16 = round_decimal((AE16 + AG16 + AI16) * forex_rate)
    
    # Final-2: AJ16 = FINAL sales price per unit
    # IFERROR(ROUND(SUM(AB16, AF16:AI16) / E16, 2), 0)
    if quantity > 0:
        AJ16 = round_decimal((AB16 + AF16 + AG16 + AH16 + AI16) / Decimal(quantity))
    else:
        AJ16 = Decimal("0")
    
    # Final-1: AK16 = AJ16 * E16
    AK16 = round_decimal(AJ16 * Decimal(quantity))
    
    return {
        "AF16": AF16,  # Profit
        "AG16": AG16,  # DM fee
        "AD16": AD16,  # Sale price per unit (excl financial)
        "AE16": AE16,  # Sale price total (excl financial)
        "AH16": AH16,  # Forex reserve
        "AI16": AI16,  # Financial agent fee
        "AJ16": AJ16,  # FINAL sales price per unit (no VAT)
        "AK16": AK16   # FINAL sales price total (no VAT)
    }


# ============================================================================
# PHASE 12: VAT CALCULATIONS
# ============================================================================

def phase12_vat_calculations(
    AJ16: Decimal,
    quantity: int,
    AY16: Decimal,
    Y16: Decimal,
    Z16: Decimal,
    T16: Decimal,
    offer_incoterms: Incoterms,
    offer_sale_type: OfferSaleType,
    rate_vat_ru: Decimal
) -> Dict[str, Decimal]:
    """
    Calculate VAT for sales and import

    Steps: Final-39, Final-40, Final-41, Final-42, Final-43
    Returns: AM16, AL16, AN16, AO16, AP16

    Updated 2025-11-09: AO16 formula now includes T16 (first-leg logistics)
    """
    # Final-39: AM16 = AJ16 * (1 + IF(offer_incoterms="DDP", rate_vatRu, 0))
    if offer_incoterms == Incoterms.DDP:
        vat_multiplier = Decimal("1") + rate_vat_ru
    else:
        vat_multiplier = Decimal("1")
    AM16 = round_decimal(AJ16 * vat_multiplier)

    # Final-40: AL16 = IFERROR(AM16 * E16, 0)
    AL16 = round_decimal(AM16 * Decimal(quantity))

    # Final-41: AN16 = AL16 - AK16
    AK16 = AJ16 * Decimal(quantity)  # Sales price total no VAT
    AN16 = round_decimal(AL16 - AK16)

    # Final-42: AO16 = SUM(AY16, Y16, Z16, T16) * IF(AND(DDP, not export), rate_vatRu, 0)
    # Updated 2025-11-09: Now includes T16 in the sum
    if offer_incoterms == Incoterms.DDP and offer_sale_type != OfferSaleType.EXPORT:
        import_vat_rate = rate_vat_ru
    else:
        import_vat_rate = Decimal("0")
    AO16 = round_decimal((AY16 + Y16 + Z16 + T16) * import_vat_rate)

    # Final-43: AP16 = AN16 - AO16
    AP16 = round_decimal(AN16 - AO16)

    return {
        "AM16": AM16,  # Sales price per unit with VAT
        "AL16": AL16,  # Sales price total with VAT
        "AN16": AN16,  # VAT from sales
        "AO16": AO16,  # VAT on import (includes T16)
        "AP16": AP16   # Net VAT payable
    }


# ============================================================================
# PHASE 13: TRANSIT COMMISSION
# ============================================================================

def phase13_transit_commission(
    AF16: Decimal,
    AG16: Decimal,
    AH16: Decimal,
    AI16: Decimal,
    BA16: Decimal,
    BB16: Decimal,
    offer_sale_type: OfferSaleType
) -> Decimal:
    """
    Calculate transit commission if applicable
    
    Steps: Final-44
    Returns: AQ16
    """
    # Final-44: AQ16 = IF(offer_sale_type="транзит", SUM(AF16:AI16, BA16, BB16), 0)
    if offer_sale_type == OfferSaleType.TRANSIT:
        AQ16 = round_decimal(AF16 + AG16 + AH16 + AI16 + BA16 + BB16)
    else:
        AQ16 = Decimal("0")
    
    return AQ16


# ============================================================================
# MAIN CALCULATION ORCHESTRATOR
# ============================================================================

def calculate_multiproduct_quote(products: List[QuoteCalculationInput]) -> List[ProductCalculationResult]:
    """
    Calculate complete quote for multiple products
    Handles proper distribution of quote-level costs across all products

    Key differences from single product:
    - Calculate S13 as sum of all S16 values
    - Calculate BD16 for each product as S16/S13
    - Calculate quote-level logistics (T13, U13) ONCE
    - Calculate quote-level financing (BH*, BJ*, BL*) ONCE
    - Distribute costs to products using BD16
    """
    if not products:
        return []

    if len(products) == 1:
        # Single product - use simpler function
        return [calculate_single_product_quote(products[0])]

    # Use first product's shared parameters (logistics, financial, company, etc.)
    shared = products[0]

    # Extract derived variables (same for all products)
    seller_region = get_seller_region(shared.company.seller_company)
    delivery_date = shared.logistics.delivery_date  # For VAT rate calculation
    rate_vat_ru = get_rate_vat_ru(seller_region, delivery_date)

    # STEP 1: Calculate Phase 1 for all products (each product has its own VAT rate)
    phase1_results_list = []
    vat_seller_country_list = []  # Store per-product VAT rates
    for product_input in products:
        # Calculate VAT rate for THIS product's supplier country
        vat_seller_country = get_vat_seller_country(product_input.logistics.supplier_country)
        vat_seller_country_list.append(vat_seller_country)

        phase1 = phase1_purchase_price(
            product_input.product.base_price_VAT,
            product_input.product.quantity,
            product_input.financial.supplier_discount,
            product_input.financial.exchange_rate_base_price_to_quote,
            vat_seller_country,
            product_input.logistics.supplier_country
        )
        phase1_results_list.append(phase1)

    # STEP 2: Calculate S13 and BD16 for each product
    S13 = sum(p["S16"] for p in phase1_results_list)
    BD16_list = [p["S16"] / S13 for p in phase1_results_list]

    # STEP 2.5: Calculate internal pricing (AY16) for insurance calculation
    phase2_5_results_list = []
    internal_markup_list = []  # Store per-product internal markup
    for i, product_input in enumerate(products):
        # Calculate internal markup for THIS product's supplier country
        internal_markup = get_internal_markup(product_input.logistics.supplier_country, seller_region)
        internal_markup_list.append(internal_markup)

        phase2_5 = phase2_5_internal_pricing(
            phase1_results_list[i]["S16"],
            product_input.product.quantity,
            internal_markup
        )
        phase2_5_results_list.append(phase2_5)

    # STEP 2.6: Calculate quote-level insurance using AY16
    # AY13_total = sum of all AY16 (internal sale price total for all products)
    AY13_total = sum(phase2_5["AY16"] for phase2_5 in phase2_5_results_list)

    # Insurance cost (ROUNDUP in Excel is ceiling to 1 decimal place)
    from decimal import ROUND_CEILING
    insurance_total = (AY13_total * shared.system.rate_insurance * Decimal("10")).quantize(Decimal("1"), rounding=ROUND_CEILING) / Decimal("10")

    # STEP 3: Process each product to calculate Phase 3 and Phase 4
    # We need to do this BEFORE aggregating for Phase 5-8
    phase3_results_list = []
    phase4_results_list = []

    for i, product_input in enumerate(products):
        BD16 = BD16_list[i]

        # Calculate insurance for this product (distributed by value proportion BD16)
        insurance_per_product = insurance_total * BD16

        # PHASE 3: Distribute logistics costs
        phase3 = phase3_logistics_distribution(
            BD16,
            shared.logistics.logistics_supplier_hub,
            shared.logistics.logistics_hub_customs,
            shared.logistics.logistics_customs_client,
            shared.customs.brokerage_hub,
            shared.customs.brokerage_customs,
            shared.customs.warehousing_at_customs,
            shared.customs.customs_documentation,
            shared.customs.brokerage_extra,
            insurance_per_product
        )
        phase3_results_list.append(phase3)

        # PHASE 4: Calculate duties (Y16, Z16, AZ16) using T16 from Phase 3
        phase4 = phase4_duties(
            phase2_5_results_list[i]["AY16"],  # From Phase 2.5
            phase3["T16"],  # From Phase 3 just calculated
            phase1_results_list[i]["S16"],  # From Phase 1
            product_input.product.quantity,
            product_input.taxes.import_tariff,
            product_input.taxes.excise_tax,
            product_input.product.weight_in_kg,
            vat_seller_country_list[i],
            product_input.logistics.offer_incoterms,  # FIX: logistics not company
            insurance_per_product  # Add insurance to Y16 calculation
        )
        phase4_results_list.append(phase4)

        # Calculate AO16 (deductible VAT) right after Phase 4
        # New formula (2025-11-09): AO16 = (AY16 + Y16 + Z16 + T16) × rate_vat_ru
        if (product_input.logistics.offer_incoterms == Incoterms.DDP and
            product_input.company.offer_sale_type != OfferSaleType.EXPORT):
            AO16 = round_decimal((phase2_5_results_list[i]["AY16"] + phase4["Y16"] + phase4["Z16"] + phase3["T16"]) * rate_vat_ru)
        else:
            AO16 = Decimal("0")

        # Store AO16 temporarily for aggregation
        phase4["AO16_temp"] = AO16

    # STEP 4: Aggregate for Phase 5 (supplier payment)
    T13 = sum(phase3["T16"] for phase3 in phase3_results_list)
    U13 = sum(phase3["U16"] for phase3 in phase3_results_list)
    AZ13 = sum(phase4["AZ16"] for phase4 in phase4_results_list)
    Y13 = sum(phase4["Y16"] for phase4 in phase4_results_list)
    Z13 = sum(phase4["Z16"] for phase4 in phase4_results_list)
    AO13 = sum(phase4["AO16_temp"] for phase4 in phase4_results_list)

    # STEP 5: Calculate quote-level supplier payment ONCE
    phase5_results = phase5_supplier_payment(
        AZ13,
        T13,
        Y13,
        Z13,
        AO13,
        shared.payment.advance_to_supplier,
        shared.system.rate_fin_comm
    )

    # STEP 6: Calculate estimated COGS for each product (for revenue estimation)
    AB16_est_list = []
    for i in range(len(products)):
        AB16_est = round_decimal(
            phase1_results_list[i]["S16"] +
            phase3_results_list[i]["V16"] +
            phase4_results_list[i]["Y16"] +
            phase4_results_list[i]["Z16"]
        )
        AB16_est_list.append(AB16_est)

    # STEP 7: Calculate quote-level revenue estimation ONCE
    phase6_results = phase6_revenue_estimation(
        AB16_est_list,
        shared.financial.markup,
        shared.financial.rate_forex_risk,
        shared.financial.dm_fee_type,
        shared.financial.dm_fee_value,
        seller_region,
        rate_vat_ru
    )

    # STEP 8: Calculate quote-level financing costs ONCE
    phase7_results = phase7_financing_costs(
        phase6_results["BH2"],
        phase5_results["BH6"],
        phase5_results["BH4"],
        shared.payment.advance_from_client,
        shared.logistics.delivery_time,
        shared.system.customs_logistics_pmt_due,  # helpsheet E27: fixed ~10 days
        shared.system.rate_loan_interest_daily
    )

    # STEP 9: Calculate quote-level credit sales interest ONCE
    phase8_results = phase8_credit_sales_interest(
        phase5_results["BH4"],  # Total before forwarding (not BH2 revenue)
        phase7_results["BH3"],
        shared.payment.time_to_advance_on_receiving,
        shared.system.rate_loan_interest_daily
    )

    # STEP 10: Now finalize each product with financing and sales pricing
    results = []
    for i, product_input in enumerate(products):
        BD16 = BD16_list[i]
        phase1 = phase1_results_list[i]
        phase2_5 = phase2_5_results_list[i]
        phase3 = phase3_results_list[i]
        phase4 = phase4_results_list[i]

        # PHASE 9: Distribute financing costs
        phase9_results = phase9_distribute_financing(
            phase7_results["BJ11"],
            phase8_results["BL5"],
            BD16
        )

        # PHASE 10: Final COGS
        phase10_results = phase10_final_cogs(
            phase1["S16"],
            phase3["V16"],
            phase4["Y16"],
            phase4["Z16"],
            phase9_results["BA16"],
            phase9_results["BB16"],
            product_input.product.quantity
        )

        # PHASE 11: Sales Price
        phase11_results = phase11_sales_price(
            phase10_results["AB16"],
            phase1["S16"],
            phase3["V16"],
            product_input.product.quantity,
            product_input.financial.markup,
            BD16,
            product_input.financial.rate_forex_risk,
            product_input.financial.dm_fee_type,
            product_input.financial.dm_fee_value,
            product_input.system.rate_fin_comm,
            phase4["AZ16"],
            internal_markup_list[i],  # Use per-product internal markup
            phase3["T16"],
            product_input.company.offer_sale_type,
            seller_region
        )

        # PHASE 12: VAT
        phase12_results = phase12_vat_calculations(
            phase11_results["AJ16"],
            product_input.product.quantity,
            phase2_5["AY16"],
            phase4["Y16"],
            phase4["Z16"],
            phase3["T16"],  # Added T16 for new AO16 formula
            product_input.logistics.offer_incoterms,  # FIX: logistics not company
            product_input.company.offer_sale_type,
            rate_vat_ru
        )

        # PHASE 13: Transit Commission
        AQ16 = phase13_transit_commission(
            phase11_results["AF16"],
            phase11_results["AG16"],
            phase11_results["AH16"],
            phase11_results["AI16"],
            phase9_results["BA16"],
            phase9_results["BB16"],
            product_input.company.offer_sale_type
        )

        # Assemble product result
        result = ProductCalculationResult(
            # Phase 1
            purchase_price_no_vat=phase1["N16"],
            purchase_price_after_discount=phase1["P16"],
            purchase_price_per_unit_quote_currency=phase1["R16"],
            purchase_price_total_quote_currency=phase1["S16"],
            # Phase 2
            distribution_base=BD16,
            # Phase 2.5
            internal_sale_price_per_unit=phase2_5["AX16"],
            internal_sale_price_total=phase2_5["AY16"],
            # Phase 3
            logistics_first_leg=phase3["T16"],
            logistics_last_leg=phase3["U16"],
            logistics_total=phase3["V16"],
            # Phase 4
            customs_fee=phase4["Y16"],
            excise_tax_amount=phase4["Z16"],
            # Phase 9
            financing_cost_initial=phase9_results["BA16"],
            financing_cost_credit=phase9_results["BB16"],
            # Phase 10
            cogs_per_unit=phase10_results["AA16"],
            cogs_per_product=phase10_results["AB16"],
            # Phase 11
            profit=phase11_results["AF16"],
            dm_fee=phase11_results["AG16"],
            forex_reserve=phase11_results["AH16"],
            financial_agent_fee=phase11_results["AI16"],
            sale_price_per_unit_excl_financial=phase11_results["AD16"],
            sale_price_total_excl_financial=phase11_results["AE16"],
            sales_price_per_unit_no_vat=phase11_results["AJ16"],
            sales_price_total_no_vat=phase11_results["AK16"],
            # Phase 12
            sales_price_per_unit_with_vat=phase12_results["AM16"],
            sales_price_total_with_vat=phase12_results["AL16"],
            vat_from_sales=phase12_results["AN16"],
            vat_on_import=phase12_results["AO16"],
            vat_net_payable=phase12_results["AP16"],
            # Phase 13
            transit_commission=AQ16,
            # Quote-level values (same for all products in multi-product quote)
            quote_level_supplier_payment=phase5_results["BH6"],
            quote_level_total_before_forwarding=phase5_results["BH4"],
            quote_level_evaluated_revenue=phase6_results["BH2"],
            quote_level_client_advance=phase7_results["BH3"],
            quote_level_supplier_financing_need=phase7_results["BH7"],
            quote_level_supplier_financing_fv=phase7_results["BI7"],
            quote_level_supplier_financing_cost=phase7_results["BJ7"],
            quote_level_operational_financing_need=phase7_results["BH10"],
            quote_level_operational_financing_fv=phase7_results["BI10"],
            quote_level_operational_financing_cost=phase7_results["BJ10"],
            quote_level_total_financing_cost=phase7_results["BJ11"],
            quote_level_credit_sales_amount=phase8_results["BL3"],
            quote_level_credit_sales_fv=phase8_results["BL4"],
            quote_level_credit_sales_interest=phase8_results["BL5"]
        )
        results.append(result)

    return results


def calculate_single_product_quote(inputs: QuoteCalculationInput) -> ProductCalculationResult:
    """
    Calculate complete quote for a single product
    Orchestrates all 13 phases in correct order
    """
    # Extract derived variables
    seller_region = get_seller_region(inputs.company.seller_company)
    vat_seller_country = get_vat_seller_country(inputs.logistics.supplier_country)
    internal_markup = get_internal_markup(inputs.logistics.supplier_country, seller_region)
    delivery_date = inputs.logistics.delivery_date  # For VAT rate calculation
    rate_vat_ru = get_rate_vat_ru(seller_region, delivery_date)
    
    # PHASE 1: Purchase Price
    phase1_results = phase1_purchase_price(
        inputs.product.base_price_VAT,
        inputs.product.quantity,
        inputs.financial.supplier_discount,
        inputs.financial.exchange_rate_base_price_to_quote,
        vat_seller_country,
        inputs.logistics.supplier_country
    )
    
    # For single product, distribution base is 1.0
    BD16 = Decimal("1.0")
    S13 = phase1_results["S16"]

    # PHASE 2.5: Internal Pricing (for insurance calculation)
    phase2_5_results = phase2_5_internal_pricing(
        phase1_results["S16"],
        inputs.product.quantity,
        internal_markup
    )

    # Calculate insurance for single product
    AY13_for_insurance = phase2_5_results["AY16"]  # For single product, AY13 = AY16
    from decimal import ROUND_CEILING
    insurance_total = (AY13_for_insurance * inputs.system.rate_insurance * Decimal("10")).quantize(Decimal("1"), rounding=ROUND_CEILING) / Decimal("10")

    # PHASE 3: Logistics (single product gets all logistics costs)
    phase3_results = phase3_logistics_distribution(
        BD16,
        inputs.logistics.logistics_supplier_hub,
        inputs.logistics.logistics_hub_customs,
        inputs.logistics.logistics_customs_client,
        inputs.customs.brokerage_hub,
        inputs.customs.brokerage_customs,
        inputs.customs.warehousing_at_customs,
        inputs.customs.customs_documentation,
        inputs.customs.brokerage_extra,
        insurance_total  # For single product, no distribution needed
    )

    # PHASE 4: Duties (calculate after Phase 3 so T16 is available)
    phase4_results = phase4_duties(
        phase2_5_results["AY16"],  # From Phase 2.5
        phase3_results["T16"],  # From Phase 3
        phase1_results["S16"],
        inputs.product.quantity,
        inputs.taxes.import_tariff,
        inputs.taxes.excise_tax,
        inputs.product.weight_in_kg,
        vat_seller_country,
        inputs.logistics.offer_incoterms,  # FIX: logistics not company
        insurance_total  # For single product, insurance_per_product = insurance_total
    )

    # Calculate AO16 (deductible VAT) right after Phase 4
    # New formula (2025-11-09): AO16 = (AY16 + Y16 + Z16 + T16) × rate_vat_ru
    if (inputs.logistics.offer_incoterms == Incoterms.DDP and
        inputs.company.offer_sale_type != OfferSaleType.EXPORT):
        AO16 = round_decimal((phase2_5_results["AY16"] + phase4_results["Y16"] +
                              phase4_results["Z16"] + phase3_results["T16"]) * rate_vat_ru)
    else:
        AO16 = Decimal("0")

    # Estimated COGS (without financing)
    AB16_est = round_decimal(
        phase1_results["S16"] +
        phase3_results["V16"] +
        phase4_results["Y16"] +
        phase4_results["Z16"]
    )

    # PHASE 5: Supplier Payment
    AZ13 = phase4_results["AZ16"]  # For single product
    T13 = phase3_results["T16"]  # For single product, T13 = T16
    Y13 = phase4_results["Y16"]  # For single product, Y13 = Y16
    Z13 = phase4_results["Z16"]  # For single product, Z13 = Z16
    AO13 = AO16  # For single product, AO13 = AO16

    phase5_results = phase5_supplier_payment(
        AZ13,
        T13,
        Y13,
        Z13,
        AO13,
        inputs.payment.advance_to_supplier,
        inputs.system.rate_fin_comm
    )
    
    # PHASE 6: Revenue Estimation
    phase6_results = phase6_revenue_estimation(
        [AB16_est],
        inputs.financial.markup,
        inputs.financial.rate_forex_risk,
        inputs.financial.dm_fee_type,
        inputs.financial.dm_fee_value,
        seller_region,
        rate_vat_ru
    )
    
    # PHASE 7: Financing Costs
    phase7_results = phase7_financing_costs(
        phase6_results["BH2"],
        phase5_results["BH6"],
        phase5_results["BH4"],
        inputs.payment.advance_from_client,
        inputs.logistics.delivery_time,
        inputs.system.customs_logistics_pmt_due,  # helpsheet E27: fixed ~10 days
        inputs.system.rate_loan_interest_daily
    )
    
    # PHASE 8: Credit Sales Interest
    phase8_results = phase8_credit_sales_interest(
        phase5_results["BH4"],  # Total before forwarding (not BH2 revenue)
        phase7_results["BH3"],
        inputs.payment.time_to_advance_on_receiving,
        inputs.system.rate_loan_interest_daily
    )
    
    # PHASE 9: Distribute Financing
    phase9_results = phase9_distribute_financing(
        phase7_results["BJ11"],
        phase8_results["BL5"],
        BD16
    )
    
    # PHASE 10: Final COGS
    phase10_results = phase10_final_cogs(
        phase1_results["S16"],
        phase3_results["V16"],
        phase4_results["Y16"],
        phase4_results["Z16"],
        phase9_results["BA16"],
        phase9_results["BB16"],
        inputs.product.quantity
    )
    
    # PHASE 11: Sales Price
    phase11_results = phase11_sales_price(
        phase10_results["AB16"],
        phase1_results["S16"],
        phase3_results["V16"],
        inputs.product.quantity,
        inputs.financial.markup,
        BD16,
        inputs.financial.rate_forex_risk,
        inputs.financial.dm_fee_type,
        inputs.financial.dm_fee_value,
        inputs.system.rate_fin_comm,
        phase4_results["AZ16"],
        internal_markup,
        phase3_results["T16"],
        inputs.company.offer_sale_type,
        seller_region
    )
    
    # PHASE 12: VAT
    phase12_results = phase12_vat_calculations(
        phase11_results["AJ16"],
        inputs.product.quantity,
        phase2_5_results["AY16"],  # From Phase 2.5
        phase4_results["Y16"],
        phase4_results["Z16"],
        phase3_results["T16"],  # Added T16 for new AO16 formula
        inputs.logistics.offer_incoterms,  # FIX: logistics not company
        inputs.company.offer_sale_type,
        rate_vat_ru
    )
    
    # PHASE 13: Transit Commission
    AQ16 = phase13_transit_commission(
        phase11_results["AF16"],
        phase11_results["AG16"],
        phase11_results["AH16"],
        phase11_results["AI16"],
        phase9_results["BA16"],
        phase9_results["BB16"],
        inputs.company.offer_sale_type
    )
    
    # Assemble results
    return ProductCalculationResult(
        purchase_price_no_vat=phase1_results["N16"],
        purchase_price_after_discount=phase1_results["P16"],
        purchase_price_per_unit_quote_currency=phase1_results["R16"],
        purchase_price_total_quote_currency=phase1_results["S16"],
        distribution_base=BD16,
        internal_sale_price_per_unit=phase2_5_results["AX16"],
        internal_sale_price_total=phase2_5_results["AY16"],
        logistics_first_leg=phase3_results["T16"],
        logistics_last_leg=phase3_results["U16"],
        logistics_total=phase3_results["V16"],
        customs_fee=phase4_results["Y16"],
        excise_tax_amount=phase4_results["Z16"],
        financing_cost_initial=phase9_results["BA16"],
        financing_cost_credit=phase9_results["BB16"],
        cogs_per_product=phase10_results["AB16"],
        cogs_per_unit=phase10_results["AA16"],
        profit=phase11_results["AF16"],
        dm_fee=phase11_results["AG16"],
        sale_price_per_unit_excl_financial=phase11_results["AD16"],
        sale_price_total_excl_financial=phase11_results["AE16"],
        forex_reserve=phase11_results["AH16"],
        financial_agent_fee=phase11_results["AI16"],
        sales_price_per_unit_no_vat=phase11_results["AJ16"],
        sales_price_total_no_vat=phase11_results["AK16"],
        sales_price_per_unit_with_vat=phase12_results["AM16"],
        sales_price_total_with_vat=phase12_results["AL16"],
        vat_from_sales=phase12_results["AN16"],
        vat_on_import=phase12_results["AO16"],
        vat_net_payable=phase12_results["AP16"],
        transit_commission=AQ16,
        # Quote-level financing values
        quote_level_supplier_payment=phase5_results["BH6"],
        quote_level_total_before_forwarding=phase5_results["BH4"],
        quote_level_evaluated_revenue=phase6_results["BH2"],
        quote_level_client_advance=phase7_results["BH3"],
        quote_level_supplier_financing_need=phase7_results["BH7"],
        quote_level_supplier_financing_fv=phase7_results["BI7"],
        quote_level_supplier_financing_cost=phase7_results["BJ7"],
        quote_level_operational_financing_need=phase7_results["BH10"],
        quote_level_operational_financing_fv=phase7_results["BI10"],
        quote_level_operational_financing_cost=phase7_results["BJ10"],
        quote_level_total_financing_cost=phase7_results["BJ11"],
        quote_level_credit_sales_amount=phase8_results["BL3"],
        quote_level_credit_sales_fv=phase8_results["BL4"],
        quote_level_credit_sales_interest=phase8_results["BL5"]
    )


# ============================================================================
# EXPORT FOR USE IN API
# ============================================================================

__all__ = [
    'calculate_single_product_quote',
    'get_seller_region',
    'get_vat_seller_country',
    'get_internal_markup',
    'get_rate_vat_ru'
]