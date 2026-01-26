"""
Currency Service - Exchange rates from CBR (Central Bank of Russia)
Provides multi-currency support for logistics calculations
"""

import os
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Optional
import httpx
from supabase import create_client, Client
from supabase.client import ClientOptions
from dotenv import load_dotenv

load_dotenv()

# Supported currencies
SUPPORTED_CURRENCIES = ['USD', 'EUR', 'RUB', 'CNY', 'TRY']

# CBR currency codes mapping (CBR uses different codes)
CBR_CURRENCY_CODES = {
    'USD': 'R01235',  # US Dollar
    'EUR': 'R01239',  # Euro
    'CNY': 'R01375',  # Chinese Yuan
    'TRY': 'R01700J', # Turkish Lira
}

# CBR XML currency char codes
CBR_CHAR_CODES = {
    'USD': 'USD',
    'EUR': 'EUR',
    'CNY': 'CNY',
    'TRY': 'TRY',
}


def _get_supabase() -> Client:
    """Get Supabase client configured for kvota schema"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key, options=ClientOptions(schema="kvota"))


def fetch_cbr_rates(rate_date: Optional[date] = None) -> dict[str, Decimal]:
    """
    Fetch exchange rates from CBR API (XML format)
    Returns dict: {currency: rate_to_rub}

    CBR API: https://www.cbr.ru/scripts/XML_daily.asp?date_req=DD/MM/YYYY
    """
    if rate_date is None:
        rate_date = date.today()

    # Format date for CBR API (DD/MM/YYYY)
    date_str = rate_date.strftime("%d/%m/%Y")
    url = f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={date_str}"

    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()

        # Parse XML (encoding is windows-1251)
        root = ET.fromstring(response.content)

        rates = {}
        for valute in root.findall('Valute'):
            char_code = valute.find('CharCode').text
            if char_code in CBR_CHAR_CODES.values():
                # CBR uses comma as decimal separator
                value_str = valute.find('Value').text.replace(',', '.')
                nominal_str = valute.find('Nominal').text

                # Rate is Value / Nominal (e.g., 100 CNY = 1300 RUB means 1 CNY = 13 RUB)
                value = Decimal(value_str)
                nominal = Decimal(nominal_str)
                rate_per_unit = value / nominal

                # Map back to our currency code
                for our_code, cbr_code in CBR_CHAR_CODES.items():
                    if cbr_code == char_code:
                        rates[our_code] = rate_per_unit
                        break

        return rates

    except Exception as e:
        print(f"[currency_service] Error fetching CBR rates: {e}")
        return {}


def save_rates_to_db(rate_date: date, rates: dict[str, Decimal]) -> bool:
    """Save exchange rates to database.

    Table schema: from_currency, to_currency, rate, fetched_at
    All CBR rates are X -> RUB (e.g., 1 USD = 78.53 RUB)
    """
    if not rates:
        return False

    try:
        supabase = _get_supabase()
        now = datetime.now().isoformat()

        for currency, rate in rates.items():
            # CBR rates are currency -> RUB
            supabase.table("exchange_rates").insert({
                "from_currency": currency,
                "to_currency": "RUB",
                "rate": float(rate),
                "fetched_at": now
            }).execute()

        print(f"[currency_service] Saved {len(rates)} rates for {rate_date}")
        return True

    except Exception as e:
        print(f"[currency_service] Error saving rates: {e}")
        return False


def get_rates_from_db(rate_date: date) -> dict[str, Decimal]:
    """Get exchange rates from database for today (latest fetched).

    Returns dict: {currency: rate_to_rub}
    Specifically fetches USD, EUR, CNY, TRY rates.
    """
    try:
        supabase = _get_supabase()

        # Get latest rates for required currencies -> RUB
        required_currencies = ['USD', 'EUR', 'CNY', 'TRY']
        result = supabase.table("exchange_rates")\
            .select("from_currency, rate")\
            .eq("to_currency", "RUB")\
            .in_("from_currency", required_currencies)\
            .order("fetched_at", desc=True)\
            .limit(20)\
            .execute()

        rates = {}
        for row in result.data:
            currency = row["from_currency"]
            # Only take first (latest) rate for each currency
            if currency not in rates:
                rates[currency] = Decimal(str(row["rate"]))

        print(f"[currency_service] Loaded rates from DB: {rates}")
        return rates

    except Exception as e:
        print(f"[currency_service] Error getting rates from DB: {e}")
        return {}


def ensure_rates_available(rate_date: Optional[date] = None) -> dict[str, Decimal]:
    """
    Ensure exchange rates are available for the given date.
    Fetches from CBR and caches in DB if not already present.
    Returns the rates dict.
    """
    if rate_date is None:
        rate_date = date.today()

    # First try to get from database
    rates = get_rates_from_db(rate_date)

    if rates and len(rates) >= 4:  # We expect USD, EUR, CNY, TRY
        return rates

    # If weekend or holiday, CBR might not have rates - try previous days
    original_date = rate_date
    attempts = 0
    max_attempts = 7  # Try up to 7 days back

    while attempts < max_attempts:
        # Fetch from CBR
        rates = fetch_cbr_rates(rate_date)

        if rates and len(rates) >= 4:
            # Save to DB with original requested date for convenience
            save_rates_to_db(original_date, rates)
            return rates

        # Try previous day
        rate_date = rate_date - timedelta(days=1)
        attempts += 1

    print(f"[currency_service] Could not fetch rates after {max_attempts} attempts")
    return {}


def get_latest_rates() -> dict[str, Decimal]:
    """
    Get the latest available exchange rates.
    Tries today, then looks back up to 7 days.
    """
    return ensure_rates_available(date.today())


def convert_to_usd(amount: Decimal, from_currency: str, rate_date: Optional[date] = None) -> Decimal:
    """
    Convert amount from any currency to USD.
    Uses RUB as intermediate (CBR only provides RUB rates).

    Conversion: from_currency -> RUB -> USD
    Formula: amount_usd = amount * (from_currency_to_rub / usd_to_rub)
    """
    if amount == 0:
        return Decimal(0)

    from_currency = from_currency.upper()

    # If already USD, no conversion needed
    if from_currency == 'USD':
        return amount

    # If RUB, convert directly to USD
    rates = ensure_rates_available(rate_date)

    if not rates:
        print(f"[currency_service] No rates available, returning original amount")
        return amount

    usd_to_rub = rates.get('USD')
    if not usd_to_rub:
        print(f"[currency_service] No USD rate, returning original amount")
        return amount

    # RUB -> USD
    if from_currency == 'RUB':
        return amount / usd_to_rub

    # Other currency -> RUB -> USD
    from_currency_to_rub = rates.get(from_currency)
    if not from_currency_to_rub:
        print(f"[currency_service] No rate for {from_currency}, returning original amount")
        return amount

    # Cross-rate conversion
    amount_in_rub = amount * from_currency_to_rub
    amount_in_usd = amount_in_rub / usd_to_rub

    return amount_in_usd


def convert_amount(amount: Decimal, from_currency: str, to_currency: str, rate_date: Optional[date] = None) -> Decimal:
    """
    Convert amount between any two supported currencies.
    Uses RUB as intermediate.
    """
    if amount == 0:
        return Decimal(0)

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return amount

    rates = ensure_rates_available(rate_date)
    print(f"[currency_service] convert_amount({amount}, {from_currency}, {to_currency}): rates={rates}")

    if not rates:
        print(f"[currency_service] NO RATES AVAILABLE, returning original amount")
        return amount

    # Convert to RUB first
    if from_currency == 'RUB':
        amount_in_rub = amount
    else:
        from_rate = rates.get(from_currency)
        if not from_rate:
            return amount
        amount_in_rub = amount * from_rate

    # Convert from RUB to target
    if to_currency == 'RUB':
        return amount_in_rub
    else:
        to_rate = rates.get(to_currency)
        if not to_rate:
            return amount_in_rub
        return amount_in_rub / to_rate


def format_rates_for_display(rates: Optional[dict[str, Decimal]] = None) -> list[dict]:
    """
    Format rates for display in UI.
    Returns list of {currency, rate_to_rub, rate_to_usd}
    """
    if rates is None:
        rates = get_latest_rates()

    if not rates:
        return []

    usd_rate = rates.get('USD', Decimal(1))

    result = []
    for currency in ['USD', 'EUR', 'CNY', 'TRY']:
        if currency in rates:
            rate_to_rub = rates[currency]
            rate_to_usd = rate_to_rub / usd_rate if usd_rate else Decimal(1)
            result.append({
                'currency': currency,
                'rate_to_rub': float(rate_to_rub),
                'rate_to_usd': float(rate_to_usd)
            })

    # Add RUB
    result.append({
        'currency': 'RUB',
        'rate_to_rub': 1.0,
        'rate_to_usd': float(Decimal(1) / usd_rate) if usd_rate else 0
    })

    return result
