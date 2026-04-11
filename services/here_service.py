"""
HERE Geocoding API service for international city search.

Replaces DaData city search with HERE Geocode API for international coverage.
API docs: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/endpoint-geocode-brief.html

Phase 3 hardening (Procurement Phase 3, Section 2.1):
- LRU cache on repeated typeahead queries to avoid hitting the HERE free-tier
  rate ceiling.
- pycountry-backed ISO 3166-1 alpha-3 -> alpha-2 mapping (replaces the legacy
  28-country hardcoded dict), with graceful fallback when pycountry is absent.
"""

import os
from functools import lru_cache
from typing import Optional

import httpx


HERE_API_KEY = os.getenv("HERE_API_KEY", "")
HERE_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"


# ----------------------------------------------------------------------------
# Alpha-3 -> Alpha-2 resolution
# ----------------------------------------------------------------------------
#
# We try pycountry first (complete ISO 3166-1 coverage, ~250 countries). If the
# import fails at runtime (e.g. the dependency was removed from requirements
# without redeploying), we fall back to the legacy 28-country hardcoded dict so
# the service continues to work for the most common cases instead of silently
# dropping every country code.

_LEGACY_ALPHA3_TO_ALPHA2 = {
    "BEL": "BE", "NLD": "NL", "DEU": "DE", "FRA": "FR", "GBR": "GB",
    "ESP": "ES", "ITA": "IT", "POL": "PL", "CZE": "CZ", "AUT": "AT",
    "SWE": "SE", "CHE": "CH", "FIN": "FI", "DNK": "DK", "USA": "US",
    "CHN": "CN", "JPN": "JP", "KOR": "KR", "IND": "IN", "TWN": "TW",
    "TUR": "TR", "RUS": "RU", "VNM": "VN", "THA": "TH", "MYS": "MY",
    "SGP": "SG", "ARE": "AE", "SAU": "SA",
}

try:
    import pycountry  # type: ignore[import-not-found]

    def _alpha3_to_alpha2(code: Optional[str]) -> str:
        """Resolve ISO 3166-1 alpha-3 -> alpha-2 via pycountry.

        Returns an empty string for None, empty input, or unknown codes.
        `pycountry.countries.get` returns None (never raises) for unknown
        keys, so no exception handling is needed.
        """
        if not code:
            return ""
        country = pycountry.countries.get(alpha_3=code.upper())
        if country is None:
            return ""
        return getattr(country, "alpha_2", "") or ""

except ImportError:  # pragma: no cover — exercised only when pycountry absent

    def _alpha3_to_alpha2(code: Optional[str]) -> str:
        """Fallback alpha-3 -> alpha-2 resolver using the legacy 28-entry dict."""
        if not code:
            return ""
        return _LEGACY_ALPHA3_TO_ALPHA2.get(code.upper(), "")


def _call_here_api(query: str, limit: int = 10) -> dict:
    """Call HERE Geocode API and return the raw JSON response.

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        Raw API response dict

    Raises:
        Various exceptions on network/HTTP errors.
    """
    if not HERE_API_KEY:
        raise ValueError("HERE_API_KEY is not configured")

    params = {
        "q": query,
        "apiKey": HERE_API_KEY,
        "limit": limit,
    }

    response = httpx.get(HERE_GEOCODE_URL, params=params, timeout=5.0)
    response.raise_for_status()
    return response.json()


def _normalize_item(item: dict) -> dict:
    """Normalize a single HERE API result item to our standard format.

    Handles both structured address fields (city, state, countryName) and
    label-only responses by parsing the label string.
    """
    address = item.get("address", {})

    city = address.get("city", "")
    region = address.get("state", "")
    country = address.get("countryName", "")
    country_code = address.get("countryCode", "")

    # Fall back to parsing label if structured fields are missing
    if not city or not country:
        label = address.get("label", item.get("title", ""))
        if label:
            parts = [p.strip() for p in label.split(",")]
            if not city and len(parts) >= 1:
                city = parts[0]
            if not country and len(parts) >= 2:
                country = parts[-1]
            if not region and len(parts) >= 3:
                region = parts[1]

    # Build display string with disambiguation
    display_parts = [city]
    if region and region != city:
        display_parts.append(region)
    if country:
        display_parts.append(country)
    display = ", ".join(display_parts)

    country_code_2 = _alpha3_to_alpha2(country_code)

    return {
        "city": city,
        "region": region,
        "country": country,
        "country_code": country_code_2,
        "display": display,
    }


# ----------------------------------------------------------------------------
# Public search API with LRU cache
# ----------------------------------------------------------------------------


@lru_cache(maxsize=256)
def _search_cities_cached(query_normalized: str, count: int) -> tuple:
    """Inner cached HERE search, keyed on (normalized query, count).

    The query is normalized (stripped + lowercased) before it reaches this
    function, so "Berlin", " BERLIN ", and "berlin" all share a single cache
    entry. HERE Geocode is case-insensitive for city names, so sending the
    normalized form does not change result quality.

    Returns a tuple of dicts — tuples are hashable (required by lru_cache);
    the outer `search_cities` wrapper converts back to a list for backward-
    compatible consumer code.
    """
    response_data = _call_here_api(query_normalized, limit=count)
    items = response_data.get("items", [])
    if not items:
        return tuple()
    city_items = [item for item in items if item.get("resultType") == "locality"]
    if not city_items:
        return tuple()
    return tuple(_normalize_item(item) for item in city_items)


def search_cities(query: str, count: int = 10) -> list[dict]:
    """Search for cities using HERE Geocode API.

    Args:
        query: City name query (min 2 chars after trim)
        count: Maximum number of results (default 10)

    Returns:
        List of dicts with keys: city, region, country, country_code, display.
        Returns an empty list on invalid input or HERE API errors (graceful
        degradation — the caller sees no cities, not a broken endpoint).

    Caching:
        Results are cached per (normalized query, count) for the process
        lifetime via a 256-entry LRU cache on `_search_cities_cached`. The
        query is normalized (stripped + lowercased) before the cache lookup,
        so "Berlin", " BERLIN ", and "berlin" share one entry.
    """
    if not query or not isinstance(query, str) or not query.strip():
        return []

    normalized = query.strip().lower()

    try:
        cached = _search_cities_cached(normalized, count)
    except Exception as e:
        # Graceful degradation — do NOT cache failures. The @lru_cache
        # decorator only caches successful returns, so nothing to clear here.
        print(f"HERE city search failed for '{query}': {e}")
        return []

    return list(cached)
