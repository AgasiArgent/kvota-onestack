"""
PHMB Calculator Service

Pure calculation module for PHMB (price list-based) quotes.
Takes item data + settings + quote-level params, returns calculated prices.

No database access -- all inputs are passed in, all outputs are returned.
Does NOT import or depend on calculation_engine.py or calculation_models.py.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

# Constants
VAT_RATE = Decimal("1.20")  # 20% VAT
ANNUAL_FINANCING_RATE = Decimal("0.25")  # 25% annual rate
DAYS_IN_YEAR = 365


def _to_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _round2(value: Decimal) -> Decimal:
    """Round to 2 decimal places using ROUND_HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_phmb_item(
    item_data: dict,
    settings: dict,
    quote_params: dict,
) -> dict:
    """Calculate prices for a single PHMB quote item.

    Args:
        item_data: Dict with keys:
            - list_price_rmb: Decimal/float - price from price list in RMB/CNY
            - discount_pct: Decimal/float - discount percentage (0-100)
            - duty_pct: Decimal/float or None - customs duty percentage from HS code
            - delivery_days: int - delivery time in days
            - quantity: int - item quantity

        settings: Dict from phmb_settings table:
            - logistics_price_per_pallet: Decimal/float (USD)
            - base_price_per_pallet: Decimal/float (USD) - shared denominator
            - exchange_rate_insurance_pct: Decimal/float (default 3%)
            - financial_transit_pct: Decimal/float (default 2%)
            - customs_handling_cost: Decimal/float (USD)
            - customs_insurance_pct: Decimal/float (default 5%) - fallback when duty unknown

        quote_params: Dict with quote-level parameters:
            - advance_pct: Decimal/float (0-100)
            - markup_pct: Decimal/float
            - payment_days: int (not used in calculation directly, informational)
            - cny_to_usd_rate: Decimal/float - CNY/USD exchange rate

    Returns:
        Dict with calculated prices:
            - exw_price_usd: Decimal - EXW price in USD (after discount, converted)
            - cogs_usd: Decimal - cost of goods sold including overhead
            - financial_cost_usd: Decimal - financing cost for deferred payment
            - total_price_usd: Decimal - final price per unit (with markup, no VAT)
            - total_price_with_vat_usd: Decimal - final price per unit (with markup + VAT)
    """
    # Parse inputs
    list_price_rmb = _to_decimal(item_data.get("list_price_rmb"))
    discount_pct = _to_decimal(item_data.get("discount_pct"), Decimal("0"))
    duty_pct = item_data.get("duty_pct")  # Keep None check
    delivery_days = int(item_data.get("delivery_days", 0))

    logistics_price_per_pallet = _to_decimal(settings.get("logistics_price_per_pallet"))
    base_price_per_pallet = _to_decimal(settings.get("base_price_per_pallet"))
    exchange_rate_insurance_pct = _to_decimal(
        settings.get("exchange_rate_insurance_pct"), Decimal("3")
    )
    financial_transit_pct = _to_decimal(
        settings.get("financial_transit_pct"), Decimal("2")
    )
    customs_handling_cost = _to_decimal(settings.get("customs_handling_cost"))
    customs_insurance_pct = _to_decimal(
        settings.get("customs_insurance_pct"), Decimal("5")
    )

    advance_pct = _to_decimal(quote_params.get("advance_pct"), Decimal("0"))
    markup_pct = _to_decimal(quote_params.get("markup_pct"), Decimal("0"))
    cny_to_usd_rate = _to_decimal(quote_params.get("cny_to_usd_rate"))

    # Guard against division by zero
    if cny_to_usd_rate == 0:
        logger.error("cny_to_usd_rate is zero, cannot calculate prices")
        return {
            "exw_price_usd": Decimal("0"),
            "cogs_usd": Decimal("0"),
            "financial_cost_usd": Decimal("0"),
            "total_price_usd": Decimal("0"),
            "total_price_with_vat_usd": Decimal("0"),
        }

    if base_price_per_pallet == 0:
        logger.error("base_price_per_pallet is zero, cannot calculate overhead ratios")
        return {
            "exw_price_usd": Decimal("0"),
            "cogs_usd": Decimal("0"),
            "financial_cost_usd": Decimal("0"),
            "total_price_usd": Decimal("0"),
            "total_price_with_vat_usd": Decimal("0"),
        }

    # Step 1: Get EXW USD price
    if discount_pct > 0:
        discounted_rmb = list_price_rmb * (1 - discount_pct / 100)
    else:
        discounted_rmb = list_price_rmb
    exw_usd = discounted_rmb / cny_to_usd_rate

    # Step 2: Calculate overhead percentages
    logistics_pct = logistics_price_per_pallet / base_price_per_pallet
    customs_handling_pct = customs_handling_cost / base_price_per_pallet

    # Step 3: Determine duty/insurance percentage
    if duty_pct is not None:
        duty_or_insurance_pct = _to_decimal(duty_pct) / 100
    else:
        duty_or_insurance_pct = customs_insurance_pct / 100

    # Step 4: COGS
    overhead_multiplier = (
        1
        + logistics_pct
        + exchange_rate_insurance_pct / 100
        + financial_transit_pct / 100
        + customs_handling_pct
        + duty_or_insurance_pct
    )
    cogs_usd = exw_usd * overhead_multiplier

    # Step 5: Financial cost (simple interest on non-advanced portion)
    daily_rate = ANNUAL_FINANCING_RATE / DAYS_IN_YEAR
    non_advanced_share = 1 - advance_pct / 100
    financial_cost_usd = cogs_usd * non_advanced_share * daily_rate * delivery_days

    # Step 6: Total
    total_usd = (cogs_usd + financial_cost_usd) * (1 + markup_pct / 100)
    total_with_vat_usd = total_usd * VAT_RATE

    return {
        "exw_price_usd": _round2(exw_usd),
        "cogs_usd": _round2(cogs_usd),
        "financial_cost_usd": _round2(financial_cost_usd),
        "total_price_usd": _round2(total_usd),
        "total_price_with_vat_usd": _round2(total_with_vat_usd),
    }


def calculate_phmb_quote(
    items: list[dict],
    settings: dict,
    quote_params: dict,
) -> dict:
    """Calculate prices for all items in a PHMB quote and compute totals.

    Args:
        items: List of item dicts (see calculate_phmb_item for keys).
            Each item must also have a 'quantity' field.
        settings: Settings dict (see calculate_phmb_item).
        quote_params: Quote-level params (see calculate_phmb_item).

    Returns:
        Dict with:
            - items: list of dicts, each containing the original item data
              merged with calculated prices and line_total fields
            - totals: dict with aggregated totals across all items:
                - total_exw_usd
                - total_cogs_usd
                - total_financial_cost_usd
                - total_price_usd
                - total_price_with_vat_usd
                - total_quantity
    """
    calculated_items = []
    total_exw = Decimal("0")
    total_cogs = Decimal("0")
    total_financial = Decimal("0")
    total_price = Decimal("0")
    total_price_vat = Decimal("0")
    total_quantity = 0

    for item in items:
        quantity = int(item.get("quantity", 1))
        total_quantity += quantity

        calc = calculate_phmb_item(item, settings, quote_params)

        # Line totals = unit price * quantity
        line_exw = _round2(calc["exw_price_usd"] * quantity)
        line_cogs = _round2(calc["cogs_usd"] * quantity)
        line_financial = _round2(calc["financial_cost_usd"] * quantity)
        line_total = _round2(calc["total_price_usd"] * quantity)
        line_total_vat = _round2(calc["total_price_with_vat_usd"] * quantity)

        calculated_item = {
            **item,
            **calc,
            "quantity": quantity,
            "line_total_exw_usd": line_exw,
            "line_total_cogs_usd": line_cogs,
            "line_total_financial_cost_usd": line_financial,
            "line_total_usd": line_total,
            "line_total_with_vat_usd": line_total_vat,
        }
        calculated_items.append(calculated_item)

        total_exw += line_exw
        total_cogs += line_cogs
        total_financial += line_financial
        total_price += line_total
        total_price_vat += line_total_vat

    return {
        "items": calculated_items,
        "totals": {
            "total_exw_usd": _round2(total_exw),
            "total_cogs_usd": _round2(total_cogs),
            "total_financial_cost_usd": _round2(total_financial),
            "total_price_usd": _round2(total_price),
            "total_price_with_vat_usd": _round2(total_price_vat),
            "total_quantity": total_quantity,
        },
    }
