"""
HERE Geocoding Autosuggest API service for international city search.

Replaces DaData city search with HERE API for international coverage.
API docs: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/endpoint-autosuggest-brief.html
"""

import os
import httpx


HERE_API_KEY = os.getenv("HERE_API_KEY", "")
HERE_AUTOSUGGEST_URL = "https://autosuggest.search.hereapi.com/v1/autosuggest"


def _call_here_api(query: str, limit: int = 10) -> dict:
    """Call HERE Autosuggest API and return raw JSON response.

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        Raw API response dict

    Raises:
        Various exceptions on network/HTTP errors
    """
    if not HERE_API_KEY:
        raise ValueError("HERE_API_KEY is not configured")

    params = {
        "q": query,
        "apiKey": HERE_API_KEY,
        "resultTypes": "city",
        "limit": limit,
    }

    response = httpx.get(HERE_AUTOSUGGEST_URL, params=params, timeout=5.0)
    response.raise_for_status()
    return response.json()


def _normalize_item(item: dict) -> dict:
    """Normalize a single HERE API result item to our standard format."""
    address = item.get("address", {})
    city = address.get("city", "")
    region = address.get("state", "")
    country = address.get("countryName", "")

    # Build display string with disambiguation
    parts = [city]
    if region and region != city:
        parts.append(region)
    if country:
        parts.append(country)
    display = ", ".join(parts)

    return {
        "city": city,
        "region": region,
        "country": country,
        "display": display,
    }


def search_cities(query: str, count: int = 10) -> list[dict]:
    """Search for cities using HERE Autosuggest API.

    Args:
        query: City name query (min 2 chars)
        count: Maximum number of results (default 10)

    Returns:
        List of dicts with keys: city, region, country, display.
        Returns empty list on errors or invalid input.
    """
    if not query or not isinstance(query, str) or not query.strip():
        return []

    try:
        response_data = _call_here_api(query.strip(), limit=count)
        items = response_data.get("items", [])
        if not items:
            return []
        return [_normalize_item(item) for item in items]
    except Exception as e:
        print(f"HERE city search failed for '{query}': {e}")
        return []
