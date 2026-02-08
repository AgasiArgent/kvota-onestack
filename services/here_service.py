"""
HERE Geocoding API service for international city search.

Replaces DaData city search with HERE Geocode API for international coverage.
API docs: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/endpoint-geocode-brief.html
"""

import os
import httpx


HERE_API_KEY = os.getenv("HERE_API_KEY", "")
HERE_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"


def _call_here_api(query: str, limit: int = 10) -> dict:
    """Call HERE Geocode API and return raw JSON response.

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
        "limit": limit,
    }

    response = httpx.get(HERE_GEOCODE_URL, params=params, timeout=5.0)
    response.raise_for_status()
    return response.json()


def _normalize_item(item: dict) -> dict:
    """Normalize a single HERE API result item to our standard format.

    Handles both structured address fields (city, state, countryName)
    and label-only responses by parsing the label string.
    """
    address = item.get("address", {})

    # Try structured fields first, fall back to parsing label
    city = address.get("city", "")
    region = address.get("state", "")
    country = address.get("countryName", "")

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

    return {
        "city": city,
        "region": region,
        "country": country,
        "display": display,
    }


def search_cities(query: str, count: int = 10) -> list[dict]:
    """Search for cities using HERE Geocode API.

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
        # Filter to only locality/city resultType items
        city_items = [item for item in items if item.get("resultType") == "locality"]
        if not city_items:
            return []
        return [_normalize_item(item) for item in city_items]
    except Exception as e:
        print(f"HERE city search failed for '{query}': {e}")
        return []
