"""Calculation helpers — inputs builder and VAT/country resolution.

Relocated from main.py in Phase 6C-3 (2026-04-21) when the FastHTML shell was
retired. These helpers feed the calculation engine (calculation_engine.py),
which remains locked per CLAUDE.md.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List

from calculation_mapper import map_variables_to_calculation_input, safe_decimal
from calculation_models import QuoteCalculationInput


# Shared mapping from ISO country codes to Russian names for UI display.
# Used by supplier list, customs workspace, logistics, and other pages.
COUNTRY_NAME_MAP = {
    "RU": "Россия",
    "CN": "Китай",
    "TR": "Турция",
    "DE": "Германия",
    "US": "США",
    "KR": "Корея",
    "JP": "Япония",
    "IT": "Италия",
    "FR": "Франция",
    "PL": "Польша",
    "LT": "Литва",
    "LV": "Латвия",
    "BG": "Болгария",
    "KZ": "Казахстан",
    "BY": "Беларусь",
    "UZ": "Узбекистан",
    "AE": "ОАЭ",
    "IN": "Индия",
    "GB": "Великобритания",
    "ES": "Испания",
    "CZ": "Чехия",
    "NL": "Нидерланды",
    "BE": "Бельгия",
    "AT": "Австрия",
    "CH": "Швейцария",
    "SE": "Швеция",
    "FI": "Финляндия",
    "DK": "Дания",
    "TW": "Тайвань",
    "VN": "Вьетнам",
    "TH": "Таиланд",
    "MY": "Малайзия",
    "SG": "Сингапур",
    "SA": "Саудовская Аравия",
}

# ============================================================================
# VAT ZONE MAPPING (Two-factor: country + price_includes_vat → SupplierCountry)
# ============================================================================

# EU countries: ISO code → {name_ru, vat_rate, zone (SupplierCountry enum value or None)}
# zone=None means the VAT rate has no matching SupplierCountry zone → error when price_includes_vat=True
EU_COUNTRY_VAT_RATES = {
    # 21% → maps to LITHUANIA zone
    "BE": {"name_ru": "Бельгия", "vat_rate": 21, "zone": "Литва"},
    "NL": {"name_ru": "Нидерланды", "vat_rate": 21, "zone": "Литва"},
    "CZ": {"name_ru": "Чехия", "vat_rate": 21, "zone": "Литва"},
    "ES": {"name_ru": "Испания", "vat_rate": 21, "zone": "Литва"},
    "LT": {"name_ru": "Литва", "vat_rate": 21, "zone": "Литва"},
    "LV": {"name_ru": "Латвия", "vat_rate": 21, "zone": "Латвия"},
    # 20% → maps to BULGARIA zone
    "BG": {"name_ru": "Болгария", "vat_rate": 20, "zone": "Болгария"},
    "FR": {"name_ru": "Франция", "vat_rate": 20, "zone": "Болгария"},
    "AT": {"name_ru": "Австрия", "vat_rate": 20, "zone": "Болгария"},
    "SK": {"name_ru": "Словакия", "vat_rate": 20, "zone": "Болгария"},
    # 23% → maps to POLAND zone
    "PL": {"name_ru": "Польша", "vat_rate": 23, "zone": "Польша"},
    "PT": {"name_ru": "Португалия", "vat_rate": 23, "zone": "Польша"},
    "IE": {"name_ru": "Ирландия", "vat_rate": 23, "zone": "Польша"},
    # Unsupported rates → zone=None → ERROR when price_includes_vat=True
    "DE": {"name_ru": "Германия", "vat_rate": 19, "zone": None},
    "IT": {"name_ru": "Италия", "vat_rate": 22, "zone": None},
    "SE": {"name_ru": "Швеция", "vat_rate": 25, "zone": None},
    "DK": {"name_ru": "Дания", "vat_rate": 25, "zone": None},
    "FI": {"name_ru": "Финляндия", "vat_rate": 25.5, "zone": None},
    "HU": {"name_ru": "Венгрия", "vat_rate": 27, "zone": None},
    "RO": {"name_ru": "Румыния", "vat_rate": 19, "zone": None},
    "HR": {"name_ru": "Хорватия", "vat_rate": 25, "zone": None},
    "SI": {"name_ru": "Словения", "vat_rate": 22, "zone": None},
    "EE": {"name_ru": "Эстония", "vat_rate": 22, "zone": None},
    "GR": {"name_ru": "Греция", "vat_rate": 24, "zone": None},
}

EU_ISO_CODES = set(EU_COUNTRY_VAT_RATES.keys())

# Direct country matches: ISO code → SupplierCountry enum value
# These countries have dedicated zones in the calculation engine
DIRECT_COUNTRY_ZONES = {
    "TR": "Турция",
    "RU": "Россия",
    "CN": "Китай",
    "AE": "ОАЭ",
}

# Reverse lookup: Russian name → ISO code
_RUSSIAN_TO_ISO = {}
for _iso, _name_ru in COUNTRY_NAME_MAP.items():
    _RUSSIAN_TO_ISO[_name_ru] = _iso
# Add EU countries not in COUNTRY_NAME_MAP
for _iso, _info in EU_COUNTRY_VAT_RATES.items():
    _RUSSIAN_TO_ISO[_info["name_ru"]] = _iso

# English name → ISO code (for common names)
_ENGLISH_TO_ISO = {
    "Turkey": "TR", "Russia": "RU", "China": "CN", "Lithuania": "LT",
    "Latvia": "LV", "Bulgaria": "BG", "Poland": "PL", "UAE": "AE",
    "Germany": "DE", "Italy": "IT", "France": "FR", "Japan": "JP",
    "South Korea": "KR", "Korea": "KR", "India": "IN", "Belgium": "BE",
    "Netherlands": "NL", "Spain": "ES", "Czech Republic": "CZ",
    "Austria": "AT", "Switzerland": "CH", "Sweden": "SE", "Finland": "FI",
    "Denmark": "DK", "Portugal": "PT", "Ireland": "IE", "Greece": "GR",
    "Hungary": "HU", "Romania": "RO", "Croatia": "HR", "Slovenia": "SI",
    "Estonia": "EE", "Slovakia": "SK",
}

# SupplierCountry enum value → ISO code (for values already mapped to zones)
_ENUM_TO_ISO = {
    "Турция": "TR", "Россия": "RU", "Китай": "CN", "Литва": "LT",
    "Латвия": "LV", "Болгария": "BG", "Польша": "PL", "ОАЭ": "AE",
}


def normalize_country_to_iso(value: str) -> str:
    """Normalize any country representation to ISO 2-letter code.

    Handles: ISO codes ("BE"), Russian names ("Бельгия"), English names ("Belgium"),
    SupplierCountry enum values ("Литва").

    Returns empty string if not recognized.
    """
    if not value:
        return ""
    v = value.strip()
    upper = v.upper()

    # Already an ISO code?
    if len(v) == 2 and upper.isalpha():
        return upper

    # Russian name?
    if v in _RUSSIAN_TO_ISO:
        return _RUSSIAN_TO_ISO[v]

    # English name?
    if v in _ENGLISH_TO_ISO:
        return _ENGLISH_TO_ISO[v]

    # SupplierCountry enum value?
    if v in _ENUM_TO_ISO:
        return _ENUM_TO_ISO[v]

    # Case-insensitive fallbacks
    v_lower = v.lower()
    for eng, iso in _ENGLISH_TO_ISO.items():
        if eng.lower() == v_lower:
            return iso

    return ""


def resolve_vat_zone(country_raw: str, price_includes_vat: bool) -> dict:
    """Map (country, price_includes_vat) → SupplierCountry enum value with reason.

    Returns dict:
        zone: str or None — SupplierCountry enum value for calculation engine
        reason: str — human-readable explanation for quote control page
        warning: str or None — warning message (needs manual check)
        error: str or None — error message (cannot calculate)
    """
    iso = normalize_country_to_iso(country_raw)
    name_ru = COUNTRY_NAME_MAP.get(iso, "") or EU_COUNTRY_VAT_RATES.get(iso, {}).get("name_ru", country_raw or "неизвестная")

    # 1. Empty/unknown country → Прочие with warning
    if not iso:
        return {
            "zone": "Прочие",
            "reason": f"Страна не определена ({country_raw or '—'}) → Прочие",
            "warning": "Страна поставщика не указана — проверьте",
            "error": None,
        }

    # 2. China — always "Китай" regardless of VAT flag
    # Engine already handles China as VAT-free (line 200: if supplier_country == CHINA: N16 = base_price_VAT)
    if iso == "CN":
        return {
            "zone": "Китай",
            "reason": f"{name_ru} → Китай (НДС не применяется)",
            "warning": None,
            "error": None,
        }

    # 3. Direct match countries (TR, RU, AE) — have their own zones
    if iso in DIRECT_COUNTRY_ZONES:
        zone = DIRECT_COUNTRY_ZONES[iso]
        if price_includes_vat:
            return {
                "zone": zone,
                "reason": f"{name_ru} с НДС → {zone}",
                "warning": None,
                "error": None,
            }
        else:
            # Price without VAT → engine shouldn't strip VAT → use Прочие (0%)
            return {
                "zone": "Прочие",
                "reason": f"{name_ru}, цена без НДС → Прочие (0%)",
                "warning": f"Цена без НДС для {name_ru} — проверьте корректность",
                "error": None,
            }

    # 4. EU countries
    if iso in EU_ISO_CODES:
        eu_info = EU_COUNTRY_VAT_RATES[iso]
        vat_rate = eu_info["vat_rate"]

        if not price_includes_vat:
            # EU without VAT → cross-border (0% VAT, 4% EU route markup)
            return {
                "zone": "ЕС (между странами ЕС)",
                "reason": f"{name_ru}, цена без НДС → ЕС cross-border (0% НДС, 4% наценка)",
                "warning": f"Цена без НДС для ЕС ({name_ru}) — проверьте",
                "error": None,
            }
        else:
            # EU with VAT — need matching zone
            zone = eu_info["zone"]
            if zone:
                return {
                    "zone": zone,
                    "reason": f"{name_ru} с НДС {vat_rate}% → зона {zone} (очистка {vat_rate}%)",
                    "warning": None,
                    "error": None,
                }
            else:
                return {
                    "zone": None,
                    "reason": f"НДС {name_ru} ({vat_rate}%) не поддерживается расчётной моделью",
                    "warning": None,
                    "error": f"НДС {name_ru} ({vat_rate}%) не поддерживается. Поддерживаемые ставки: 20% (Болгария), 21% (Литва), 23% (Польша)",
                }

    # 5. Non-EU, non-direct country → Прочие
    if price_includes_vat:
        return {
            "zone": "Прочие",
            "reason": f"{name_ru} → Прочие",
            "warning": f"Цена с НДС для {name_ru} — НДС не будет очищен",
            "error": None,
        }
    return {
        "zone": "Прочие",
        "reason": f"{name_ru} → Прочие",
        "warning": None,
        "error": None,
    }


def _calc_combined_duty(item: Dict) -> float:
    """REQ-004: Compute combined import tariff from percent + per-kg duty.

    Formula: customs_duty + (customs_duty_per_kg * weight_in_kg / base_price * 100)
    Falls back to customs_duty only when weight or price is missing/zero.
    Falls back to legacy import_tariff field when customs_duty is absent.
    """
    duty_pct = float(safe_decimal(item.get('customs_duty')))
    duty_per_kg = float(safe_decimal(item.get('customs_duty_per_kg')))

    # If neither column is populated, fall back to legacy field
    if duty_pct == 0 and duty_per_kg == 0:
        legacy = item.get('import_tariff')
        return float(safe_decimal(legacy))

    if duty_per_kg > 0:
        weight = float(safe_decimal(item.get('weight_in_kg')))
        price = float(safe_decimal(item.get('purchase_price_original') or item.get('base_price_vat')))
        if weight > 0 and price > 0:
            kg_as_pct = (duty_per_kg * weight) / price * 100
            return duty_pct + kg_as_pct
        else:
            logging.getLogger(__name__).warning(
                "Item %s: customs_duty_per_kg=%.4f but weight=%.2f, price=%.2f — using duty_pct only",
                item.get('id'), duty_per_kg, weight, price,
            )
            return duty_pct

    return duty_pct


def build_calculation_inputs(items: List[Dict], variables: Dict[str, Any]) -> List[QuoteCalculationInput]:
    """Build calculation inputs for all quote items.

    Note: Uses purchase_price_original as base_price_vat for calculation engine.
    Calculation engine is NOT modified - we adapt data to match its expectations.

    2026-01-26: Added per-item exchange rate calculation. Each item may have a different
    purchase_currency, so we calculate individual exchange rates to quote_currency.

    2026-01-28: Monetary values (brokerage, DM fee) are now stored in ORIGINAL currency.
    Conversion to USD happens here, just before passing to calculation engine.
    """
    from services.currency_service import convert_amount

    # Get quote currency (target currency for all conversions)
    quote_currency = variables.get('currency_of_quote') or variables.get('currency', 'USD')

    # ==========================================================================
    # CONVERT MONETARY VALUES TO QUOTE CURRENCY FOR CALCULATION ENGINE
    #
    # IMPORTANT: The calculation engine uses exchange_rate to convert purchase
    # prices to quote currency (R16 = P16 / exchange_rate). This means S16, AY16
    # are in quote currency. For Y16 = tariff * (AY16 + T16) to be correct,
    # T16 (logistics) must also be in quote currency.
    #
    # Values are stored in various currencies (logistics in USD, brokerage in
    # original currency). We convert ALL to quote currency here.
    #
    # 2026-01-28: Fixed currency mixing bug - was converting to USD but engine
    # outputs S16/AY16 in quote currency, causing Y16 calculation error.
    # ==========================================================================

    # Helper to convert value from source_currency to quote_currency
    def to_quote(value, from_currency):
        if not value:
            return safe_decimal(value)
        if from_currency == quote_currency:
            return safe_decimal(value)
        val = safe_decimal(value)
        if val > 0:
            return safe_decimal(convert_amount(val, from_currency, quote_currency))
        return val

    # Convert brokerage fields from their currencies to quote currency
    brokerage_hub_qc = to_quote(
        variables.get('brokerage_hub'),
        variables.get('brokerage_hub_currency', 'USD')
    )
    brokerage_customs_qc = to_quote(
        variables.get('brokerage_customs'),
        variables.get('brokerage_customs_currency', 'USD')
    )
    warehousing_at_customs_qc = to_quote(
        variables.get('warehousing_at_customs'),
        variables.get('warehousing_at_customs_currency', 'USD')
    )
    customs_documentation_qc = to_quote(
        variables.get('customs_documentation'),
        variables.get('customs_documentation_currency', 'USD')
    )
    brokerage_extra_qc = to_quote(
        variables.get('brokerage_extra'),
        variables.get('brokerage_extra_currency', 'USD')
    )

    # Convert logistics fields from USD to quote currency
    # Logistics costs are aggregated and stored in USD
    logistics_supplier_hub_qc = to_quote(
        variables.get('logistics_supplier_hub'), 'USD'
    )
    logistics_hub_customs_qc = to_quote(
        variables.get('logistics_hub_customs'), 'USD'
    )
    logistics_customs_client_qc = to_quote(
        variables.get('logistics_customs_client'), 'USD'
    )

    # Convert DM Fee from its currency to quote currency (only for fixed type)
    dm_fee_type = variables.get('dm_fee_type', 'fixed')
    dm_fee_currency = variables.get('dm_fee_currency', 'USD')
    if dm_fee_type == 'fixed':
        dm_fee_value_qc = to_quote(variables.get('dm_fee_value'), dm_fee_currency)
    else:
        # Percentage - no conversion needed
        dm_fee_value_qc = safe_decimal(variables.get('dm_fee_value'))

    # Create a copy of variables with quote-currency-converted values
    calc_variables = dict(variables)
    calc_variables['brokerage_hub'] = brokerage_hub_qc
    calc_variables['brokerage_customs'] = brokerage_customs_qc
    calc_variables['warehousing_at_customs'] = warehousing_at_customs_qc
    calc_variables['customs_documentation'] = customs_documentation_qc
    calc_variables['brokerage_extra'] = brokerage_extra_qc
    calc_variables['logistics_supplier_hub'] = logistics_supplier_hub_qc
    calc_variables['logistics_hub_customs'] = logistics_hub_customs_qc
    calc_variables['logistics_customs_client'] = logistics_customs_client_qc
    calc_variables['dm_fee_value'] = dm_fee_value_qc

    # seller_company name comes directly from DB (already matches SellerCompany enum)
    # No normalization needed -- DB names were updated to match enum values exactly

    calc_inputs = []
    for item in items:
        # Skip unavailable items - they shouldn't be included in calculation
        if item.get('is_unavailable'):
            continue

        # REQ-009: Skip import-banned items from calculation entirely
        if item.get('import_banned'):
            continue

        # Get item's purchase currency
        item_currency = item.get('purchase_currency') or item.get('currency_of_base_price', 'USD')

        # Product fields (adapt new schema to calculation engine expectations)
        product = {
            'base_price_vat': safe_decimal(item.get('purchase_price_original') or item.get('base_price_vat')),
            'quantity': item.get('quantity', 1),
            'weight_in_kg': safe_decimal(item.get('weight_in_kg')),
            'customs_code': item.get('customs_code', '0000000000'),
            'supplier_country': resolve_vat_zone(
                item.get('supplier_country') or variables.get('supplier_country', ''),
                bool(item.get('price_includes_vat', False))
            )["zone"] or "Прочие",
            'currency_of_base_price': item_currency,
            'import_tariff': _calc_combined_duty(item),
            'markup': item.get('markup'),
            'supplier_discount': item.get('supplier_discount'),
        }

        # Sum per-item license costs (ДС, СС, СГР) stored in RUB
        # license_ds_cost (numeric), license_ss_cost (numeric), license_sgr_cost (numeric)
        total_license_cost = (
            float(item.get('license_ds_cost') or 0)
            + float(item.get('license_ss_cost') or 0)
            + float(item.get('license_sgr_cost') or 0)
        )

        # Create per-item calc_variables copy and add license cost to brokerage_extra
        # License costs are in RUB, convert to quote currency and add to brokerage_extra
        item_calc_variables = dict(calc_variables)
        if total_license_cost > 0:
            license_cost_qc = to_quote(total_license_cost, 'RUB')
            item_calc_variables['brokerage_extra'] = safe_decimal(calc_variables.get('brokerage_extra', 0)) + safe_decimal(license_cost_qc)

        # Calculate per-item exchange rate (2026-01-26)
        # Formula: exchange_rate = "how many units of source currency per 1 unit of quote currency"
        # Example: if quote is EUR and item is USD, and 1 EUR = 1.08 USD, then exchange_rate = 1.08
        # Calculation: P16 (in USD) / 1.08 = R16 (in EUR)
        if item_currency == quote_currency:
            exchange_rate = Decimal("1.0")
        else:
            # convert_amount(1, quote_currency, item_currency) gives how many item_currency = 1 quote_currency
            exchange_rate = safe_decimal(convert_amount(Decimal("1"), quote_currency, item_currency))
            if exchange_rate == 0:
                exchange_rate = Decimal("1.0")  # Fallback if rate not found

        calc_input = map_variables_to_calculation_input(
            product=product,
            variables=item_calc_variables,  # Per-item variables with license costs in brokerage_extra
            exchange_rate=exchange_rate
        )
        calc_inputs.append(calc_input)

    return calc_inputs
