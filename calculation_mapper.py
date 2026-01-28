"""
Quote Calculation Mapping Module - Simplified for OneStack

This module handles:
- Two-tier variable resolution (product override > quote default > fallback)
- Mapping flat variables dict to nested QuoteCalculationInput

IMPORTANT: This is a simplified version for standalone testing.
The calculation engine is CURRENCY-AGNOSTIC - all input values must be
pre-converted to the same currency before passing to the mapper.

Adapted from backend/routes/quotes_mapping.py
"""

from typing import Dict, Any, Optional, List
from datetime import date, timedelta
from decimal import Decimal
import logging

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

# Setup logger
logger = logging.getLogger(__name__)


# ============================================================================
# SAFE CONVERSION UTILITIES
# ============================================================================

def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert value to Decimal"""
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, Exception):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string"""
    if value is None or value == "":
        return default
    return str(value)


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int"""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ============================================================================
# SUPPLIER COUNTRY NORMALIZATION
# ============================================================================

# Map database values to enum values (handles variations in country names)
SUPPLIER_COUNTRY_MAPPING = {
    # EU variations
    "ЕС (закупка между странами ЕС)": "ЕС (между странами ЕС)",
    "ЕС (закупки между странами ЕС)": "ЕС (между странами ЕС)",
    "EC (между странами ЕС)": "ЕС (между странами ЕС)",  # Latin EC
    "EU (between EU countries)": "ЕС (между странами ЕС)",

    # Turkey variations
    "Turkey": "Турция",
    "Турция транзит": "Турция (транзитная зона)",

    # Other common variations
    "Russia": "Россия",
    "China": "Китай",
    "Lithuania": "Литва",
    "Latvia": "Латвия",
    "Bulgaria": "Болгария",
    "Poland": "Польша",
    "UAE": "ОАЭ",
    "Other": "Прочие",

    # Additional EU countries (map to EU cross-border)
    "Германия": "ЕС (между странами ЕС)",
    "Germany": "ЕС (между странами ЕС)",
    "DE": "ЕС (между странами ЕС)",  # Germany ISO code
    "FR": "ЕС (между странами ЕС)",  # France
    "IT": "ЕС (между странами ЕС)",  # Italy
    "ES": "ЕС (между странами ЕС)",  # Spain
    "NL": "ЕС (между странами ЕС)",  # Netherlands
    "AT": "ЕС (между странами ЕС)",  # Austria
    "BE": "ЕС (между странами ЕС)",  # Belgium
    "SE": "ЕС (между странами ЕС)",  # Sweden
    "CZ": "ЕС (между странами ЕС)",  # Czech Republic
    "SK": "ЕС (между странами ЕС)",  # Slovakia
    "HU": "ЕС (между странами ЕС)",  # Hungary
    "RO": "ЕС (между странами ЕС)",  # Romania
    "FI": "ЕС (между странами ЕС)",  # Finland
    "DK": "ЕС (между странами ЕС)",  # Denmark
    "PT": "ЕС (между странами ЕС)",  # Portugal
    "IE": "ЕС (между странами ЕС)",  # Ireland
    "GR": "ЕС (между странами ЕС)",  # Greece
    "HR": "ЕС (между странами ЕС)",  # Croatia
    "SI": "ЕС (между странами ЕС)",  # Slovenia
    "EE": "ЕС (между странами ЕС)",  # Estonia

    # ISO codes for existing countries
    "TR": "Турция",  # Turkey
    "RU": "Россия",  # Russia
    "CN": "Китай",  # China
    "LT": "Литва",  # Lithuania
    "LV": "Латвия",  # Latvia
    "BG": "Болгария",  # Bulgaria
    "PL": "Польша",  # Poland
    "AE": "ОАЭ",  # UAE

    # Non-EU countries (map to Other)
    "США": "Прочие",
    "USA": "Прочие",
    "US": "Прочие",  # USA ISO code
}


def normalize_supplier_country(value: str) -> str:
    """
    Normalize supplier country value to match SupplierCountry enum.

    Args:
        value: Raw supplier country value from database

    Returns:
        Normalized value matching enum
    """
    if not value:
        return "Турция"  # Default

    # Check if it's already a valid enum value
    valid_values = [
        "Турция", "Турция (транзитная зона)", "Россия", "Китай",
        "Литва", "Латвия", "Болгария", "Польша",
        "ЕС (между странами ЕС)", "ОАЭ", "Прочие"
    ]
    if value in valid_values:
        return value

    # Try to map from known variations
    if value in SUPPLIER_COUNTRY_MAPPING:
        return SUPPLIER_COUNTRY_MAPPING[value]

    # Fallback: return as-is and let it fail with clear error
    return value


# ============================================================================
# TWO-TIER VARIABLE RESOLUTION
# ============================================================================

def get_value(field_name: str, product: Any, variables: Dict[str, Any], default: Any = None) -> Any:
    """
    Get value using two-tier logic: product override > quote default > fallback default

    Args:
        field_name: Name of the field to retrieve
        product: Product object with potential overrides
        variables: Quote-level default variables dict
        default: Fallback default if not found anywhere

    Returns:
        Value from product override, quote default, or fallback (in that order)
    """
    # Check product override first (as dict or object)
    if isinstance(product, dict):
        product_value = product.get(field_name)
    else:
        product_value = getattr(product, field_name, None)

    if product_value is not None and product_value != "":
        return product_value

    # Check quote-level default
    quote_value = variables.get(field_name)
    if quote_value is not None and quote_value != "":
        return quote_value

    # Return fallback default
    return default


# ============================================================================
# ADMIN SETTINGS (DEFAULTS FOR STANDALONE TESTING)
# ============================================================================

def get_default_admin_settings() -> Dict[str, Decimal]:
    """
    Get default admin calculation settings.

    In production, these come from the database.
    For standalone testing, use hardcoded defaults.

    Returns:
        Dict with rate_forex_risk, rate_fin_comm, rate_loan_interest_annual
    """
    return {
        'rate_forex_risk': Decimal("3"),            # 3% (engine divides by 100)
        'rate_fin_comm': Decimal("2"),              # 2% (engine divides by 100)
        'rate_loan_interest_annual': Decimal("0.25"), # 25% annual rate
        'customs_logistics_pmt_due': 10             # 10 days
    }


# ============================================================================
# SIMPLE PRODUCT CLASS FOR TESTING
# ============================================================================

class SimpleProduct:
    """Simple product class for testing without database"""
    def __init__(
        self,
        product_name: str = "",
        product_code: str = "",
        base_price_vat: Decimal = Decimal("0"),
        quantity: int = 1,
        weight_in_kg: Decimal = Decimal("0"),
        customs_code: str = "0000000000",
        **kwargs  # Allow additional fields as overrides
    ):
        self.product_name = product_name
        self.product_code = product_code
        self.base_price_vat = safe_decimal(base_price_vat)
        self.quantity = quantity
        self.weight_in_kg = safe_decimal(weight_in_kg)
        self.customs_code = customs_code

        # Store any additional fields as overrides
        for key, value in kwargs.items():
            setattr(self, key, value)


# ============================================================================
# MAIN MAPPING FUNCTION
# ============================================================================

def map_variables_to_calculation_input(
    product: Any,
    variables: Dict[str, Any],
    admin_settings: Optional[Dict[str, Decimal]] = None,
    quote_date: Optional[date] = None,
    exchange_rate: Optional[Decimal] = None
) -> QuoteCalculationInput:
    """
    Transform flat variables dict + product into nested QuoteCalculationInput.

    IMPORTANT: All monetary values must be PRE-CONVERTED to the same currency
    before calling this function. The calculation engine is currency-agnostic.

    Implements two-tier variable system:
    - Product-level values override quote-level defaults
    - Quote-level defaults override hardcoded fallbacks

    Args:
        product: Product with fields (dict or object)
        variables: Quote-level default variables (flat dict)
        admin_settings: Admin settings (defaults used if None)
        quote_date: Quote creation date (defaults to today)
        exchange_rate: Exchange rate for Phase 1 (defaults to 1.0 for same-currency)

    Returns:
        QuoteCalculationInput with all nested models populated

    Raises:
        ValueError: If required fields are missing
    """
    # Use defaults if not provided
    if admin_settings is None:
        admin_settings = get_default_admin_settings()

    if quote_date is None:
        quote_date = date.today()

    if exchange_rate is None:
        exchange_rate = Decimal("1.0")  # Assume same currency

    # Get product fields (support both dict and object)
    if isinstance(product, dict):
        base_price_vat = safe_decimal(product.get('base_price_vat'))
        quantity = product.get('quantity', 1)
        weight_in_kg = safe_decimal(product.get('weight_in_kg'), Decimal("0"))
        customs_code = safe_str(product.get('customs_code'), '0000000000')
    else:
        base_price_vat = safe_decimal(getattr(product, 'base_price_vat', 0))
        quantity = getattr(product, 'quantity', 1)
        weight_in_kg = safe_decimal(getattr(product, 'weight_in_kg', Decimal("0")))
        customs_code = safe_str(getattr(product, 'customs_code', '0000000000'))

    # ========== ProductInfo (5 fields) ==========
    product_info = ProductInfo(
        base_price_VAT=base_price_vat,
        quantity=quantity,
        weight_in_kg=weight_in_kg,
        currency_of_base_price=Currency(get_value('currency_of_base_price', product, variables, 'USD')),
        customs_code=customs_code
    )

    # ========== FinancialParams (7 fields) ==========
    financial = FinancialParams(
        currency_of_quote=Currency("USD"),  # Always USD for internal calculation
        exchange_rate_base_price_to_quote=exchange_rate,
        supplier_discount=safe_decimal(
            get_value('supplier_discount', product, variables),
            Decimal("0")
        ),
        markup=safe_decimal(
            get_value('markup', product, variables),
            Decimal("15")
        ),
        rate_forex_risk=admin_settings.get('rate_forex_risk', Decimal("3")),
        dm_fee_type=DMFeeType(variables.get('dm_fee_type', 'fixed')),
        dm_fee_value=safe_decimal(variables.get('dm_fee_value'), Decimal("0"))
    )

    # ========== LogisticsParams (7 fields) ==========
    delivery_time_days = safe_int(variables.get('delivery_time'), 60)
    delivery_date = quote_date + timedelta(days=delivery_time_days)

    # Allow override if delivery_date explicitly provided
    if 'delivery_date' in variables:
        delivery_date_val = variables['delivery_date']
        if isinstance(delivery_date_val, str):
            from datetime import datetime
            delivery_date = datetime.strptime(delivery_date_val, "%Y-%m-%d").date()
        elif isinstance(delivery_date_val, date):
            delivery_date = delivery_date_val

    # Normalize supplier country to handle variations
    raw_country = get_value('supplier_country', product, variables, 'Турция')
    normalized_country = normalize_supplier_country(raw_country)

    logistics = LogisticsParams(
        supplier_country=SupplierCountry(normalized_country),
        offer_incoterms=Incoterms(variables.get('offer_incoterms', 'DDP')),
        delivery_time=delivery_time_days,
        delivery_date=delivery_date,
        logistics_supplier_hub=safe_decimal(variables.get('logistics_supplier_hub'), Decimal("0")),
        logistics_hub_customs=safe_decimal(variables.get('logistics_hub_customs'), Decimal("0")),
        logistics_customs_client=safe_decimal(variables.get('logistics_customs_client'), Decimal("0"))
    )

    # ========== TaxesAndDuties (3 fields) ==========
    taxes = TaxesAndDuties(
        import_tariff=safe_decimal(get_value('import_tariff', product, variables), Decimal("0")),
        excise_tax=safe_decimal(get_value('excise_tax', product, variables), Decimal("0")),
        util_fee=safe_decimal(get_value('util_fee', product, variables), Decimal("0"))
    )

    # ========== PaymentTerms (10 fields) ==========
    payment = PaymentTerms(
        advance_from_client=safe_decimal(variables.get('advance_from_client'), Decimal("1")),
        advance_to_supplier=safe_decimal(variables.get('advance_to_supplier'), Decimal("1")),
        time_to_advance=safe_int(variables.get('time_to_advance'), 0),
        advance_on_loading=safe_decimal(variables.get('advance_on_loading'), Decimal("0")),
        time_to_advance_loading=safe_int(variables.get('time_to_advance_loading'), 0),
        advance_on_going_to_country_destination=safe_decimal(
            variables.get('advance_on_going_to_country_destination'), Decimal("0")
        ),
        time_to_advance_going_to_country_destination=safe_int(
            variables.get('time_to_advance_going_to_country_destination'), 0
        ),
        advance_on_customs_clearance=safe_decimal(variables.get('advance_on_customs_clearance'), Decimal("0")),
        time_to_advance_on_customs_clearance=safe_int(variables.get('time_to_advance_on_customs_clearance'), 0),
        time_to_advance_on_receiving=safe_int(variables.get('time_to_advance_on_receiving'), 0)
    )

    # ========== CustomsAndClearance (5 fields) ==========
    customs = CustomsAndClearance(
        brokerage_hub=safe_decimal(variables.get('brokerage_hub'), Decimal("0")),
        brokerage_customs=safe_decimal(variables.get('brokerage_customs'), Decimal("0")),
        warehousing_at_customs=safe_decimal(variables.get('warehousing_at_customs'), Decimal("0")),
        customs_documentation=safe_decimal(variables.get('customs_documentation'), Decimal("0")),
        brokerage_extra=safe_decimal(variables.get('brokerage_extra'), Decimal("0"))
    )

    # ========== CompanySettings (2 fields) ==========
    # Handle empty seller_company - use default if empty or falsy
    seller_company_value = variables.get('seller_company') or 'МАСТЕР БЭРИНГ ООО'
    company = CompanySettings(
        seller_company=SellerCompany(seller_company_value),
        offer_sale_type=OfferSaleType(variables.get('offer_sale_type', 'поставка'))
    )

    # ========== SystemConfig (4 fields from admin) ==========
    system = SystemConfig(
        rate_fin_comm=admin_settings.get('rate_fin_comm', Decimal("0.02")),
        rate_loan_interest_annual=admin_settings.get('rate_loan_interest_annual', Decimal("0.25")),
        rate_insurance=safe_decimal(variables.get('rate_insurance'), Decimal("0.00047")),
        customs_logistics_pmt_due=admin_settings.get('customs_logistics_pmt_due', 10)
    )

    # ========== Construct final input ==========
    return QuoteCalculationInput(
        product=product_info,
        financial=financial,
        logistics=logistics,
        taxes=taxes,
        payment=payment,
        customs=customs,
        company=company,
        system=system
    )


# ============================================================================
# VALIDATION FUNCTION
# ============================================================================

def validate_calculation_input(
    product: Any,
    variables: Dict[str, Any]
) -> List[str]:
    """
    Validate calculation input before processing.
    Returns list of all validation errors (empty list if valid).

    Business rules:
    - If incoterms != EXW, at least one logistics field must be > 0
    - Required fields must be present
    - Markup must be provided and >= 0

    Args:
        product: Product (dict or object)
        variables: Quote-level variables dict

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Get product identifier for error messages
    if isinstance(product, dict):
        product_name = product.get('product_name', 'Unknown')
        product_code = product.get('product_code', '')
        base_price_vat = product.get('base_price_vat')
        quantity = product.get('quantity')
    else:
        product_name = getattr(product, 'product_name', 'Unknown')
        product_code = getattr(product, 'product_code', '')
        base_price_vat = getattr(product, 'base_price_vat', None)
        quantity = getattr(product, 'quantity', None)

    product_id = product_name
    if product_code:
        product_id = f"{product_code} ({product_name})"

    # Required fields validation
    if not base_price_vat or safe_decimal(base_price_vat) <= 0:
        errors.append(
            f"Товар '{product_id}': отсутствует цена закупки (base_price_vat). "
            "Укажите цену в файле или в таблице."
        )

    if not quantity or quantity <= 0:
        errors.append(
            f"Товар '{product_id}': отсутствует количество (quantity). "
            "Укажите количество в файле или в таблице."
        )

    # Quote-level required fields
    if not variables.get('seller_company'):
        errors.append(
            "Отсутствует 'Компания-продавец' (seller_company). "
            "Укажите значение в карточке 'Настройки компании'."
        )

    if not variables.get('offer_incoterms'):
        errors.append(
            "Отсутствует 'Базис поставки' (offer_incoterms). "
            "Укажите значение в карточке 'Настройки компании'."
        )

    # Markup validation
    markup = get_value('markup', product, variables, None)
    if markup is None:
        errors.append(
            f"Товар '{product_id}': отсутствует 'Наценка (%)' (markup). "
            "Укажите значение."
        )
    elif safe_decimal(markup) < 0:
        errors.append(
            f"Товар '{product_id}': 'Наценка (%)' не может быть отрицательной."
        )

    # Business rule: If incoterms != EXW, at least one logistics field must be > 0
    incoterms = variables.get('offer_incoterms')
    if incoterms and incoterms != 'EXW':
        logistics_supplier_hub = safe_decimal(variables.get('logistics_supplier_hub'), Decimal("0"))
        logistics_hub_customs = safe_decimal(variables.get('logistics_hub_customs'), Decimal("0"))
        logistics_customs_client = safe_decimal(variables.get('logistics_customs_client'), Decimal("0"))

        if logistics_supplier_hub == 0 and logistics_hub_customs == 0 and logistics_customs_client == 0:
            errors.append(
                f"Для базиса поставки '{incoterms}' должна быть указана хотя бы одна логистическая стоимость."
            )

    return errors
