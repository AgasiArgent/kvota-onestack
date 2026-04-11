"""
HERE Geocoding API service for international city search.

Replaces DaData city search with HERE Geocode API for international coverage.
API docs: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/endpoint-geocode-brief.html

Phase 3 hardening (Procurement Phase 3, Section 2.1):
- Manual LRU cache on repeated typeahead queries to avoid hitting the HERE
  free-tier rate ceiling. The cache key is the normalized (stripped + lower)
  query so "Berlin"/"BERLIN"/"  berlin  " share one entry, but the RAW-cased
  query is passed to `_call_here_api` — HERE Geocode is case-insensitive so
  this only affects the mock-visible string in tests, but the legacy contract
  in `tests/test_city_autocomplete_here.py` asserts raw-case pass-through and
  Phase 3's R9 (non-regression) forbids changing that test.
- pycountry-backed ISO 3166-1 alpha-3 -> alpha-2 mapping (replaces the legacy
  28-country hardcoded dict), with graceful fallback when pycountry is absent.
"""

import os
from collections import OrderedDict
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
# Public search API with manual LRU cache
# ----------------------------------------------------------------------------
#
# We use OrderedDict instead of functools.lru_cache because lru_cache forces
# the cache key to equal the wrapped function's positional args — that coupling
# breaks the legacy contract: the caller sends "Moscow" but we want the cache
# key to be "moscow" (for hit-rate) while still passing "Moscow" to the HERE
# API (for the pre-existing test that asserts raw case reaches HERE). A manual
# OrderedDict decouples key from value cleanly with one source of truth.

_CACHE_MAX_SIZE = 256
_CACHE: "OrderedDict[tuple[str, int], tuple[dict, ...]]" = OrderedDict()


def _clear_cache() -> None:
    """Test helper — reset the city-search cache between tests."""
    _CACHE.clear()


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
        Process-local LRU cache (256 entries) keyed on `(normalized_query, count)`.
        The query is stripped + lowercased for the cache key so "Berlin",
        " BERLIN ", and "berlin" share one entry, but the RAW-cased query is
        passed to `_call_here_api` (HERE Geocode is case-insensitive so this
        only affects mock-visible call args; the legacy test in
        `tests/test_city_autocomplete_here.py` asserts raw-case pass-through).
    """
    if not query or not isinstance(query, str) or not query.strip():
        return []

    raw = query.strip()
    key = (raw.lower(), count)

    # Cache hit — promote to most-recently-used and return a fresh list copy
    # (tuples are immutable so the clone is cheap and safe for mutation).
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return list(cached)

    try:
        response_data = _call_here_api(raw, limit=count)
    except Exception as e:
        # Graceful degradation — do NOT cache failures.
        print(f"HERE city search failed for '{query}': {e}")
        return []

    items = response_data.get("items", [])
    city_items = [item for item in items if item.get("resultType") == "locality"]
    result: tuple[dict, ...] = (
        tuple(_normalize_item(item) for item in city_items) if city_items else tuple()
    )

    _CACHE[key] = result
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX_SIZE:
        _CACHE.popitem(last=False)

    return list(result)
