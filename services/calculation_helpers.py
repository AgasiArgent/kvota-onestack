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

# EU cross-border zone — the supplier-country value used when goods are
# bought between EU member states (0% VAT at purchase, 4% EU-route internal
# markup). This is NOT a country with an ISO code; it is a SupplierCountry
# *zone* in its own right (SupplierCountry.EU_CROSS_BORDER). The procurement
# form / templates store it as one of these string variants, so resolve_vat_zone
# must recognise them directly rather than route them through ISO resolution
# (which would fail and fall back to the "Прочие" zone — wrong internal markup).
_EU_CROSS_BORDER_ZONE = "ЕС (между странами ЕС)"
_EU_CROSS_BORDER_VARIANTS = frozenset(
    {
        "ЕС (между странами ЕС)",
        "ЕС (закупка между странами ЕС)",
    }
)


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

    # 0. EU cross-border zone — the supplier-country value is already a
    # SupplierCountry zone (goods bought between EU member states), not a
    # country with an ISO code. Recognise it directly: 0% VAT at purchase,
    # 4% EU-route internal markup. Without this it would fall through to the
    # "Прочие" zone (2% internal markup) — a wrong-zone calculation bug.
    if country_raw and str(country_raw).strip() in _EU_CROSS_BORDER_VARIANTS:
        return {
            "zone": _EU_CROSS_BORDER_ZONE,
            "reason": "ЕС (закупка между странами ЕС) → ЕС cross-border (0% НДС, 4% наценка)",
            "warning": None,
            "error": None,
        }

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

    NOTE: This is the legacy combined-rate formula. Per Q1 (decisions.md),
    it is wrapped by ``_resolve_import_tariff_pct`` which switches to the
    new ``services.customs_calc`` path when the item carries a Rate
    sourced from Alta. Sunset planned when all quote_items migrated to
    Alta-resolved rates (Phase 5+).
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


# ============================================================================
# REQ-4 customs_calc adapter switch (decisions.md Q1, Option B)
# Phase A migration (Req 3 customs-tariff-completeness): use the new
# `calculate_total_customs_pay()` aggregator instead of per-rate
# `calculate_duty()`. The aggregator sums all import-duty payment types
# (IMP + IMPDEMP + IMPCOMP + IMPDOP + IMPTMP) so antidumping (and other
# special duties) correctly raise the engine's `import_tariff` percent
# rather than being silently dropped.
#
# Item input shape:
#   * Legacy:  item['_resolved_customs_rate']           — single Rate
#              (Phase 1 — typically IMP only). Wrapped to
#              {rate.payment_type: rate} for the aggregator.
#   * Phase A: item['_resolved_rates_by_payment_type']  — dict[str, Rate]
#              with one entry per applicable payment_type (set by future
#              UI/API caller once multi-rate selection is wired through).
#
# Both shapes flow through the same single `calculate_total_customs_pay()`
# call. For backwards compat, when only the legacy single-rate shape is
# present, the aggregator output's `total_import_duty_rub` equals
# `calculate_duty(rate)` — so the resulting percent is identical to what
# the per-rate path produced before this migration (regression contract:
# tolerance Decimal('0.01₽')). Otherwise, fall through to the legacy
# combined-rate formula `_calc_combined_duty()` above.
#
# The locked engine itself (calculation_engine.py / calculation_models.py
# / calculation_mapper.py) is NEVER modified — this adapter is the
# integration seam. The locked engine still receives a single
# `import_tariff` percent; the aggregator just sources it from a complete
# breakdown rather than a single Rate.
#
# Sunset: legacy combined-rate formula path stays until all quote_items
# have been migrated to Alta-resolved rates (Phase 5+).
# ============================================================================


_ALTA_RESOLVED_SOURCES: frozenset[str] = frozenset({"alta-live", "alta-revalidate"})


def _collect_alta_resolved_rates(item: Dict) -> Dict[str, Any]:
    """Collect Alta-resolved rates from item, keyed by payment_type.

    Supports both the legacy single-rate shape (`_resolved_customs_rate`)
    and the Phase A multi-rate shape (`_resolved_rates_by_payment_type`).
    Only rates with `source` ∈ ALTA_RESOLVED_SOURCES are kept — manual
    or unresolved rates are dropped so the legacy fallback is taken
    upstream.

    Returns an empty dict when no Alta-resolved rate is present, so the
    caller can route to the legacy combined-rate formula.
    """
    rates: Dict[str, Any] = {}

    multi = item.get("_resolved_rates_by_payment_type")
    if isinstance(multi, dict):
        for payment_type, rate in multi.items():
            if rate is None:
                continue
            if getattr(rate, "source", None) in _ALTA_RESOLVED_SOURCES:
                rates[payment_type] = rate

    single = item.get("_resolved_customs_rate")
    if (
        single is not None
        and getattr(single, "source", None) in _ALTA_RESOLVED_SOURCES
    ):
        # Don't overwrite an entry already provided by the multi-rate
        # shape (it carries the same payment_type and is more complete).
        pt = getattr(single, "payment_type", None) or "IMP"
        rates.setdefault(pt, single)

    return rates


def _resolve_import_tariff_pct(
    item: Dict,
    quote_currency: str,
) -> float:
    """Resolve the import-tariff percent for one item.

    Switch by Alta-resolved rates on the item:
        * Any rate with source ∈ {'alta-live', 'alta-revalidate'}
          → aggregator path (calculate_total_customs_pay)
        * Otherwise (None, 'manual', missing keys)
          → legacy combined-rate formula (_calc_combined_duty)

    The aggregator path sums every applicable import-duty payment type
    (IMP + IMPDEMP + IMPCOMP + IMPDOP + IMPTMP) into a single
    `total_import_duty_rub`, then converts to a percent-of-customs-value
    so the calc engine's `import_tariff × (AY16 + T16)` semantics still
    apply. customs_value is taken from the item's purchase price
    (consistent with the legacy formula's `base_price` denominator on
    line 285 above).
    """
    selected_rates = _collect_alta_resolved_rates(item)
    if not selected_rates:
        # legacy combined-rate, sunset при переводе всех quote_items
        # на Alta-resolved (Phase 5+)
        return _calc_combined_duty(item)

    # --- Alta-resolved path (Phase A aggregator) ----------------------
    from services.currency_service import convert_amount, get_latest_rates
    from services.customs_calc import calculate_total_customs_pay

    customs_value_rub = _customs_value_in_rub(item, quote_currency, convert_amount)
    weight_kg = safe_decimal(item.get("weight_in_kg"))
    quantity = safe_decimal(item.get("quantity"))
    currency_rates = get_latest_rates() if customs_value_rub > 0 else {}

    breakdown = calculate_total_customs_pay(
        customs_value_rub=customs_value_rub,
        selected_rates_by_payment_type=selected_rates,
        weight_kg=weight_kg,
        quantity=quantity,
        currency_rates=currency_rates,
    )

    # Convert total RUB import duty → percent of customs value so the
    # calc engine's `import_tariff × (AY16 + T16)` semantics still
    # apply. When customs value is zero (insufficient pricing data) we
    # cannot derive a percent — fall back to 0% rather than dividing
    # by zero. The 0% result is identical to what the legacy formula
    # would emit for a zero-priced item, so behaviour is consistent
    # across both paths.
    if customs_value_rub <= 0:
        return 0.0
    pct = breakdown.total_import_duty_rub * Decimal("100") / customs_value_rub
    return float(pct)


def _customs_value_in_rub(
    item: Dict,
    quote_currency: str,
    convert_amount,
) -> Decimal:
    """Estimate customs value (purchase price × quantity) in rubles.

    Uses the item's purchase_price_original and purchase_currency, then
    converts to RUB via the existing currency service. Returns 0 if
    pricing data is missing — caller treats that as "cannot derive a
    percent" and falls back to 0%.
    """
    base_price = safe_decimal(
        item.get("purchase_price_original") or item.get("base_price_vat")
    )
    if base_price <= 0:
        return Decimal("0")
    quantity = safe_decimal(item.get("quantity") or 1)
    src_currency = (
        item.get("purchase_currency")
        or item.get("currency_of_base_price")
        or quote_currency
    )
    total = base_price * quantity
    if src_currency == "RUB":
        return total
    converted = convert_amount(total, src_currency, "RUB")
    return safe_decimal(converted)


def effective_calc_quantity(ordered, moq):
    """Round the per-line calc quantity up to the supplier minimum order quantity.

    Returns ``moq`` when it is a positive number strictly greater than
    ``ordered``; otherwise returns ``ordered`` unchanged — i.e. ``max(ordered,
    moq)`` with a positive MOQ. A MOQ of None / 0 / negative (or otherwise
    non-numeric) is treated as "no floor" and leaves the ordered quantity
    untouched.

    Pure: no mutation, no shared state. The calc engine consumes the result as
    ``product['quantity']`` (an ``int``, ``gt=0``), so a binding MOQ scales the
    line value, customs duty and logistics for the whole line. The customs duty
    *percent* is quantity-invariant for ad-valorem and '796' (per-unit) rates —
    numerator and denominator both scale with quantity — so flooring only the
    engine quantity keeps customs consistent without recomputing the percent
    (Testing 2 row 85).
    """
    moq_dec = safe_decimal(moq)
    if moq_dec > 0 and moq_dec > safe_decimal(ordered):
        # Return a clean int — the engine model requires ``quantity: int, gt=0``.
        # The live MOQ column is INTEGER, but coercing the validated Decimal
        # guarantees the contract even if a caller ever passes a Decimal/float.
        return int(moq_dec)
    return ordered


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

        # Testing 2 row 90: МОП-controlled exclusion (included_in_calc=False).
        # Default True so legacy items still flow through. Distinct from
        # is_unavailable (system N/A) and import_banned (customs auto-block):
        # this one is set explicitly by МОП on the calc step.
        # NOTE: Row 87 (parallel) adds auto-exclusion for rejected/customs-
        # disallowed items — that filter sits in this same loop. When both
        # branches merge, keep both filters; the UI distinguishes them via
        # separate flags exposed by the composition view.
        if item.get('included_in_calc') is False:
            continue

        # Get item's purchase currency
        item_currency = item.get('purchase_currency') or item.get('currency_of_base_price', 'USD')

        # Product fields (adapt new schema to calculation engine expectations)
        product = {
            'base_price_vat': safe_decimal(item.get('purchase_price_original') or item.get('base_price_vat')),
            # Testing 2 row 85: round the calc quantity up to the supplier's
            # minimum order quantity. This is THE single seam — the locked
            # engine reads only product['quantity'], so flooring here scales
            # line value, customs and logistics for the whole line.
            'quantity': effective_calc_quantity(
                item.get('quantity', 1), item.get('minimum_order_quantity')
            ),
            'weight_in_kg': safe_decimal(item.get('weight_in_kg')),
            'customs_code': item.get('customs_code', '0000000000'),
            'supplier_country': resolve_vat_zone(
                item.get('supplier_country') or variables.get('supplier_country', ''),
                bool(item.get('price_includes_vat', False))
            )["zone"] or "Прочие",
            'currency_of_base_price': item_currency,
            'import_tariff': _resolve_import_tariff_pct(item, quote_currency),
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
