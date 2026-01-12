"""
B2B Quotation Platform - Calculation Models
Pydantic models for quote calculation inputs with Russian business validation

Copied from backend/calculation_models.py for OneStack standalone testing.
"""

from decimal import Decimal
from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================================================
# ENUMS - Dropdown/Select Values
# ============================================================================

class Currency(str, Enum):
    """Supported currencies"""
    USD = "USD"
    EUR = "EUR"
    CNY = "CNY"
    RUB = "RUB"
    AED = "AED"
    TRY = "TRY"  # Turkish Lira


class SupplierCountry(str, Enum):
    """Supplier countries with specific VAT/markup rules"""
    TURKEY = "Турция"
    TURKEY_TRANSIT = "Турция (транзитная зона)"
    RUSSIA = "Россия"
    CHINA = "Китай"
    LITHUANIA = "Литва"
    LATVIA = "Латвия"
    BULGARIA = "Болгария"
    POLAND = "Польша"
    EU_CROSS_BORDER = "ЕС (между странами ЕС)"
    UAE = "ОАЭ"
    OTHER = "Прочие"


class SellerCompany(str, Enum):
    """Seller company names (auto-derives seller_region)"""
    MASTER_BEARING_RU = "МАСТЕР БЭРИНГ ООО"
    CMTO1_RU = "ЦМТО1 ООО"
    RAD_RESURS_RU = "РАД РЕСУРС ООО"
    TEXCEL_TR = "TEXCEL OTOMOTİV TİCARET LİMİTED ŞİRKETİ"
    GESTUS_TR = "GESTUS DIŞ TİCARET LİMİTED ŞİRKETİ"
    UPDOOR_CN = "UPDOOR Limited"


class OfferSaleType(str, Enum):
    """Deal type for quotation"""
    SUPPLY = "поставка"       # Direct supply/delivery
    TRANSIT = "транзит"        # Transit through Russia
    FIN_TRANSIT = "финтранзит" # Financial transit
    EXPORT = "экспорт"         # Export from Russia


class Incoterms(str, Enum):
    """INCOTERMS options"""
    DDP = "DDP"  # Delivered Duty Paid
    DAP = "DAP"  # Delivered At Place
    CIF = "CIF"  # Cost, Insurance, Freight
    FOB = "FOB"  # Free On Board
    EXW = "EXW"  # Ex Works


class DMFeeType(str, Enum):
    """Decision Maker fee type"""
    FIXED = "fixed"
    PERCENTAGE = "%"


# ============================================================================
# CATEGORY-BASED INPUT MODELS
# ============================================================================

class ProductInfo(BaseModel):
    """Product information inputs"""
    base_price_VAT: Decimal = Field(..., gt=0, description="Product base price including VAT")
    quantity: int = Field(..., gt=0, description="Number of units")
    weight_in_kg: Decimal = Field(default=Decimal("0"), ge=0, description="Product weight in kg")
    currency_of_base_price: Currency = Field(..., description="Currency of base price")
    customs_code: str = Field(..., min_length=10, max_length=10, description="10-digit customs code")

    @validator('customs_code')
    def validate_customs_code(cls, v):
        """Validate customs code is 10 digits"""
        if not v.isdigit():
            raise ValueError("Customs code must contain only digits")
        if len(v) != 10:
            raise ValueError("Customs code must be exactly 10 digits")
        return v


class FinancialParams(BaseModel):
    """Financial calculation parameters"""
    currency_of_quote: Currency = Field(default=Currency.USD, description="Quote currency")
    exchange_rate_base_price_to_quote: Decimal = Field(..., gt=0, description="Exchange rate to quote currency")
    supplier_discount: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Supplier discount %")
    markup: Decimal = Field(..., gt=0, le=500, description="Markup on COGS %")
    rate_forex_risk: Decimal = Field(default=Decimal("3"), ge=0, le=100, description="Currency exchange risk %")
    dm_fee_type: DMFeeType = Field(default=DMFeeType.FIXED, description="DM fee calculation type")
    dm_fee_value: Decimal = Field(default=Decimal("0"), ge=0, description="DM fee value (amount or %)")


class LogisticsParams(BaseModel):
    """Logistics and shipping parameters"""
    supplier_country: SupplierCountry = Field(..., description="Supplier country")
    offer_incoterms: Incoterms = Field(default=Incoterms.DDP, description="INCOTERMS")
    delivery_time: int = Field(..., gt=0, description="Delivery time in days")
    delivery_date: Optional[date] = Field(default=None, description="Expected delivery date (for VAT calculation)")

    # Logistics costs (for entire shipment, will be distributed)
    logistics_supplier_hub: Decimal = Field(..., ge=0, description="Cost from supplier to hub")
    logistics_hub_customs: Decimal = Field(default=Decimal("0"), ge=0, description="Cost from hub to customs")
    logistics_customs_client: Decimal = Field(default=Decimal("0"), ge=0, description="Cost from customs to client")


class TaxesAndDuties(BaseModel):
    """Tax and duty parameters"""
    import_tariff: Decimal = Field(..., ge=0, le=100, description="Import tariff %")
    excise_tax: Decimal = Field(default=Decimal("0"), ge=0, description="Excise tax per kg")
    util_fee: Decimal = Field(default=Decimal("0"), ge=0, description="Utilization fee (not subject to VAT)")


class PaymentTerms(BaseModel):
    """Payment timeline parameters"""
    advance_from_client: Decimal = Field(default=Decimal("100"), ge=0, le=100, description="Client upfront payment %")
    advance_to_supplier: Decimal = Field(default=Decimal("100"), ge=0, le=100, description="Supplier upfront payment %")

    time_to_advance: int = Field(default=0, ge=0, description="Days until client pays advance")

    advance_on_loading: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Payment at loading %")
    time_to_advance_loading: int = Field(default=0, ge=0, description="Days to loading payment")

    advance_on_going_to_country_destination: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Payment at country arrival %")
    time_to_advance_going_to_country_destination: int = Field(default=0, ge=0, description="Days to country arrival")

    advance_on_customs_clearance: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Payment at customs %")
    time_to_advance_on_customs_clearance: int = Field(default=0, ge=0, description="Days to customs clearance")

    time_to_advance_on_receiving: int = Field(default=0, ge=0, description="Days to final payment after receiving")

    @validator('advance_from_client', 'advance_to_supplier')
    def validate_advance_percentage(cls, v):
        """Ensure advance percentages are reasonable"""
        if v > 100:
            raise ValueError("Advance percentage cannot exceed 100%")
        return v


class CustomsAndClearance(BaseModel):
    """Customs clearance and brokerage costs"""
    brokerage_hub: Decimal = Field(default=Decimal("0"), ge=0, description="Hub brokerage cost")
    brokerage_customs: Decimal = Field(default=Decimal("0"), ge=0, description="Customs brokerage cost")
    warehousing_at_customs: Decimal = Field(default=Decimal("0"), ge=0, description="Warehousing cost")
    customs_documentation: Decimal = Field(default=Decimal("0"), ge=0, description="Documentation cost")
    brokerage_extra: Decimal = Field(default=Decimal("0"), ge=0, description="Extra brokerage fees")


class CompanySettings(BaseModel):
    """Company and deal type settings"""
    seller_company: SellerCompany = Field(default=SellerCompany.MASTER_BEARING_RU, description="Seller company")
    offer_sale_type: OfferSaleType = Field(default=OfferSaleType.SUPPLY, description="Deal type")


class SystemConfig(BaseModel):
    """System-wide configuration (admin controlled)"""
    rate_fin_comm: Decimal = Field(default=Decimal("2"), ge=0, le=100, description="Financial agent fee %")
    rate_loan_interest_annual: Decimal = Field(default=Decimal("0.25"), ge=0, le=1, description="Annual loan interest rate (e.g., 0.25 = 25%)")
    rate_insurance: Decimal = Field(default=Decimal("0.00047"), ge=0, le=1, description="Insurance rate (default 0.047%)")
    customs_logistics_pmt_due: int = Field(default=10, ge=0, le=365, description="Payment term for customs/logistics costs (days)")

    @property
    def rate_loan_interest_daily(self) -> Decimal:
        """Calculate daily rate from annual rate: annual / 365"""
        return self.rate_loan_interest_annual / Decimal("365")


# ============================================================================
# MAIN CALCULATION INPUT MODEL
# ============================================================================

class QuoteCalculationInput(BaseModel):
    """
    Complete input for single product line in quote calculation
    Combines all category models
    """
    # Product information
    product: ProductInfo

    # Financial parameters
    financial: FinancialParams

    # Logistics parameters
    logistics: LogisticsParams

    # Taxes and duties
    taxes: TaxesAndDuties

    # Payment terms
    payment: PaymentTerms

    # Customs and clearance
    customs: CustomsAndClearance

    # Company settings
    company: CompanySettings

    # System configuration
    system: SystemConfig = Field(default_factory=SystemConfig)

    class Config:
        json_schema_extra = {
            "example": {
                "product": {
                    "base_price_VAT": "1200.00",
                    "quantity": 10,
                    "weight_in_kg": "25.5",
                    "currency_of_base_price": "USD",
                    "customs_code": "8708913509"
                },
                "financial": {
                    "currency_of_quote": "RUB",
                    "exchange_rate_base_price_to_quote": "95.6",
                    "supplier_discount": "10",
                    "markup": "15",
                    "rate_forex_risk": "3",
                    "dm_fee_type": "fixed",
                    "dm_fee_value": "1000"
                },
                "logistics": {
                    "supplier_country": "Турция",
                    "offer_incoterms": "DDP",
                    "delivery_time": 30,
                    "logistics_supplier_hub": "1500.00",
                    "logistics_hub_customs": "800.00",
                    "logistics_customs_client": "500.00"
                },
                "taxes": {
                    "import_tariff": "5",
                    "excise_tax": "0",
                    "util_fee": "0"
                },
                "payment": {
                    "advance_from_client": "50",
                    "advance_to_supplier": "100",
                    "time_to_advance": 7,
                    "time_to_advance_on_receiving": 15
                },
                "customs": {
                    "brokerage_customs": "500.00",
                    "customs_documentation": "200.00"
                },
                "company": {
                    "seller_company": "МАСТЕР БЭРИНГ ООО",
                    "offer_sale_type": "поставка"
                }
            }
        }


# ============================================================================
# CALCULATION OUTPUT MODEL
# ============================================================================

class ProductCalculationResult(BaseModel):
    """Results for a single product line"""
    # Purchase price breakdown
    purchase_price_no_vat: Decimal = Field(..., description="N16 - Purchase price without VAT")
    purchase_price_after_discount: Decimal = Field(..., description="P16 - After discount")
    purchase_price_per_unit_quote_currency: Decimal = Field(..., description="R16 - Per unit in quote currency")
    purchase_price_total_quote_currency: Decimal = Field(..., description="S16 - Total purchase price")

    # Distribution base
    distribution_base: Decimal = Field(..., description="BD16 - Share of total purchase")

    # Logistics
    logistics_first_leg: Decimal = Field(..., description="T16 - Supplier to customs")
    logistics_last_leg: Decimal = Field(..., description="U16 - Customs to client")
    logistics_total: Decimal = Field(..., description="V16 - Total logistics")

    # Duties and taxes
    customs_fee: Decimal = Field(..., description="Y16 - Import tariff amount")
    excise_tax_amount: Decimal = Field(..., description="Z16 - Excise tax amount")

    # Internal pricing
    internal_sale_price_per_unit: Decimal = Field(..., description="AX16 - Internal sale price per unit")
    internal_sale_price_total: Decimal = Field(..., description="AY16 - Internal sale price total")

    # Financing costs
    financing_cost_initial: Decimal = Field(..., description="BA16 - Initial financing per product")
    financing_cost_credit: Decimal = Field(..., description="BB16 - Credit interest per product")

    # COGS
    cogs_per_product: Decimal = Field(..., description="AB16 - Cost of goods sold per product")
    cogs_per_unit: Decimal = Field(..., description="AA16 - COGS per unit")

    # Profit and fees
    profit: Decimal = Field(..., description="AF16 - Profit per product")
    dm_fee: Decimal = Field(..., description="AG16 - Decision maker fee")

    # Sales price (excluding financial expenses)
    sale_price_per_unit_excl_financial: Decimal = Field(..., description="AD16 - Sale price per unit (excl financial)")
    sale_price_total_excl_financial: Decimal = Field(..., description="AE16 - Sale price total (excl financial)")

    forex_reserve: Decimal = Field(..., description="AH16 - Forex risk reserve")
    financial_agent_fee: Decimal = Field(..., description="AI16 - Financial agent fee")

    # Sales price
    sales_price_per_unit_no_vat: Decimal = Field(..., description="AJ16 - Sales price per unit (no VAT)")
    sales_price_total_no_vat: Decimal = Field(..., description="AK16 - Sales price total (no VAT)")
    sales_price_per_unit_with_vat: Decimal = Field(..., description="AM16 - Sales price per unit (with VAT)")
    sales_price_total_with_vat: Decimal = Field(..., description="AL16 - Sales price total (with VAT)")

    # VAT breakdown
    vat_from_sales: Decimal = Field(..., description="AN16 - VAT from sales")
    vat_on_import: Decimal = Field(..., description="AO16 - VAT on import")
    vat_net_payable: Decimal = Field(..., description="AP16 - Net VAT payable")

    # Special cases
    transit_commission: Decimal = Field(..., description="AQ16 - Transit commission (if applicable)")

    # Quote-level financing values (optional, populated for single-product or at quote level)
    quote_level_supplier_payment: Optional[Decimal] = Field(None, description="BH6 - Supplier payment needed")
    quote_level_total_before_forwarding: Optional[Decimal] = Field(None, description="BH4 - Total before forwarding")
    quote_level_evaluated_revenue: Optional[Decimal] = Field(None, description="BH2 - Evaluated revenue")
    quote_level_client_advance: Optional[Decimal] = Field(None, description="BH3 - Client advance payment")
    quote_level_supplier_financing_need: Optional[Decimal] = Field(None, description="BH7 - Supplier financing need")
    quote_level_supplier_financing_fv: Optional[Decimal] = Field(None, description="BI7 - FV of supplier financing")
    quote_level_supplier_financing_cost: Optional[Decimal] = Field(None, description="BJ7 - Supplier financing cost")
    quote_level_operational_financing_need: Optional[Decimal] = Field(None, description="BH10 - Operational financing need")
    quote_level_operational_financing_fv: Optional[Decimal] = Field(None, description="BI10 - FV of operational financing")
    quote_level_operational_financing_cost: Optional[Decimal] = Field(None, description="BJ10 - Operational financing cost")
    quote_level_total_financing_cost: Optional[Decimal] = Field(None, description="BJ11 - Total financing cost")
    quote_level_credit_sales_amount: Optional[Decimal] = Field(None, description="BL3 - Amount client owes")
    quote_level_credit_sales_fv: Optional[Decimal] = Field(None, description="BL4 - FV with interest")
    quote_level_credit_sales_interest: Optional[Decimal] = Field(None, description="BL5 - Credit sales interest")


class QuoteCalculationResult(BaseModel):
    """Complete quote calculation results"""
    # Individual product results
    products: List[ProductCalculationResult]

    # Quote-level totals
    total_purchase_price: Decimal = Field(..., description="S13 - Total purchase price all products")
    total_cogs: Decimal = Field(..., description="AB13 - Total COGS")
    total_financing_cost: Decimal = Field(..., description="BJ11 - Total financing cost")
    total_credit_interest: Decimal = Field(..., description="BL5 - Total credit sales interest")
    evaluated_revenue: Decimal = Field(..., description="BH2 - Total evaluated revenue")
    client_advance: Decimal = Field(..., description="BH3 - Client advance payment")
    supplier_payment: Decimal = Field(..., description="BH6 - Supplier payment needed")
    average_markup: Decimal = Field(..., description="AC12 - Average markup %")

    # Derived variables used
    seller_region: str = Field(..., description="Derived from seller_company")
    vat_seller_country: Decimal = Field(..., description="M16 - VAT in supplier country")
    internal_markup: Decimal = Field(..., description="AW16 - Internal markup %")
    rate_vat_ru: Decimal = Field(..., description="Russian VAT rate")


# ============================================================================
# HELPER MODELS FOR MULTI-PRODUCT QUOTES
# ============================================================================

class MultiProductQuoteInput(BaseModel):
    """Input for quote with multiple product lines"""
    products: List[QuoteCalculationInput] = Field(..., min_items=1, description="List of products in quote")

    # Shared parameters (same for all products in quote)
    quote_currency: Currency = Field(..., description="Quote currency")
    seller_company: SellerCompany = Field(..., description="Seller company")
    offer_sale_type: OfferSaleType = Field(..., description="Deal type")
    offer_incoterms: Incoterms = Field(..., description="INCOTERMS")

    # Shared payment terms
    advance_from_client: Decimal = Field(..., ge=0, le=100, description="Client advance %")
    delivery_time: int = Field(..., gt=0, description="Delivery time in days")
    time_to_advance: int = Field(default=0, ge=0, description="Days to advance")
    time_to_advance_on_receiving: int = Field(default=0, ge=0, description="Days to final payment")

    # Shared logistics costs
    logistics_supplier_hub: Decimal = Field(..., ge=0, description="Supplier to hub cost")
    logistics_hub_customs: Decimal = Field(default=Decimal("0"), ge=0, description="Hub to customs cost")
    logistics_customs_client: Decimal = Field(default=Decimal("0"), ge=0, description="Customs to client cost")

    # System config
    system_config: SystemConfig = Field(default_factory=SystemConfig)
