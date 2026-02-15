"""CBR (Central Bank of Russia) exchange rates from JSON API."""
import httpx
from datetime import date
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
