"""CBR (Central Bank of Russia) exchange rates from JSON API."""
import httpx
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=100)
def get_usd_rub_rate(target_date: date) -> Optional[Decimal]:
    """Fetch USD/RUB rate from CBR JSON API for given date.

    Uses the cbr-xml-daily.ru archive endpoint which provides
    rates for specific dates in JSON format.
    Falls back to None on any error (network, parsing, missing data).
    """
    url = (
        f"https://www.cbr-xml-daily.ru/archive/"
        f"{target_date.year}/{target_date.month:02d}/{target_date.day:02d}/daily_json.js"
    )
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        usd_data = data.get("Valute", {}).get("USD")
        if not usd_data:
            return None
        value = usd_data.get("Value")
        if value is None:
            return None
        return Decimal(str(value))
    except Exception as e:
        print(f"[cbr_rates] Error fetching rate for {target_date}: {e}")
        return None


@lru_cache(maxsize=100)
def get_cny_rub_rate(target_date: date) -> Optional[Decimal]:
    """Fetch CNY/RUB rate from CBR JSON API for given date.

    CBR returns CNY rate with Nominal=1, so Value is the rate per 1 CNY.
    Falls back to None on any error (network, parsing, missing data).
    """
    url = (
        f"https://www.cbr-xml-daily.ru/archive/"
        f"{target_date.year}/{target_date.month:02d}/{target_date.day:02d}/daily_json.js"
    )
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        cny_data = data.get("Valute", {}).get("CNY")
        if not cny_data:
            return None
        value = cny_data.get("Value")
        if value is None:
            return None
        return Decimal(str(value))
    except Exception as e:
        print(f"[cbr_rates] Error fetching CNY rate for {target_date}: {e}")
        return None


@lru_cache(maxsize=100)
def get_cny_usd_rate(target_date: date) -> Optional[Decimal]:
    """Derive CNY/USD cross-rate for given date: how many CNY per 1 USD.

    Formula: cny_usd = usd_rub / cny_rub
    To convert CNY to USD: amount_cny / cny_usd_rate
    Returns None if either underlying rate is unavailable.
    """
    try:
        usd_rub = get_usd_rub_rate(target_date)
        cny_rub = get_cny_rub_rate(target_date)
        if usd_rub is None or cny_rub is None or cny_rub == 0:
            return None
        return usd_rub / cny_rub
    except Exception as e:
        print(f"[cbr_rates] Error computing CNY/USD rate for {target_date}: {e}")
        return None


def get_today_cny_usd_rate() -> Optional[Decimal]:
    """Get CNY/USD cross-rate for today, with fallback to recent days.

    If today's rate is not available (weekend/holiday), tries yesterday,
    then the day before, up to 5 days back.
    """
    today = date.today()
    for days_back in range(6):
        target = today - timedelta(days=days_back)
        rate = get_cny_usd_rate(target)
        if rate is not None:
            return rate
    return None
