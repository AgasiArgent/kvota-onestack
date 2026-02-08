"""
DaData API service for company lookup by INN and city autocomplete.

Provides:
- validate_inn(inn) -> bool
- lookup_company_by_inn(inn) -> dict | None  (async)
- normalize_dadata_result(suggestion) -> dict
- search_cities(query, count=10) -> list[dict]  (sync)

DaData APIs used:
- INN lookup: https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party
- City search: https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address
"""

import os
import httpx

DADATA_PARTY_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
DADATA_ADDRESS_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"


# ============================================================================
# INN VALIDATION
# ============================================================================

def validate_inn(inn) -> bool:
    """Validate INN format: must be 10 or 12 digits, not all zeros."""
    if inn is None:
        return False
    inn = str(inn).strip()
    if not inn.isdigit():
        return False
    if len(inn) not in (10, 12):
        return False
    if inn == "0" * len(inn):
        return False
    return True


# ============================================================================
# DADATA API CALLS (internal)
# ============================================================================

def _call_dadata_api(inn: str) -> dict:
    """Call DaData findById/party API for INN lookup."""
    api_key = os.environ.get("DADATA_API_KEY", "")
    if not api_key:
        raise ValueError("DADATA_API_KEY not configured")

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"query": inn}

    response = httpx.post(DADATA_PARTY_URL, json=payload, headers=headers, timeout=10.0)
    response.raise_for_status()
    return response.json()


def _call_dadata_address_api(query: str, count: int = 10) -> dict:
    """Call DaData address suggestions API for city search."""
    api_key = os.environ.get("DADATA_API_KEY", "")
    if not api_key:
        raise ValueError("DADATA_API_KEY not configured")

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "count": count,
        "from_bound": {"value": "city"},
        "to_bound": {"value": "city"},
    }

    response = httpx.post(DADATA_ADDRESS_URL, json=payload, headers=headers, timeout=10.0)
    response.raise_for_status()
    return response.json()


# ============================================================================
# RESULT NORMALIZATION (INN lookup)
# ============================================================================

def normalize_dadata_result(suggestion: dict) -> dict:
    """Normalize a DaData party suggestion into our schema."""
    data = suggestion.get("data", {})

    name_data = data.get("name", {})
    address_data = data.get("address", {})
    address_inner = address_data.get("data", {}) if address_data else {}
    management = data.get("management", {})
    state = data.get("state", {})
    opf = data.get("opf", {})

    return {
        "name": name_data.get("short_with_opf") or suggestion.get("value", ""),
        "full_name": name_data.get("full_with_opf") or name_data.get("short_with_opf") or suggestion.get("value", ""),
        "inn": data.get("inn"),
        "kpp": data.get("kpp") if data.get("type") == "LEGAL" else None,
        "ogrn": data.get("ogrn"),
        "address": address_data.get("value") if address_data else None,
        "postal_code": address_inner.get("postal_code") if address_inner else None,
        "city": address_inner.get("city") if address_inner else None,
        "director": management.get("name") if management else None,
        "director_title": management.get("post") if management else None,
        "opf": opf.get("short") if opf else None,
        "entity_type": data.get("type", "LEGAL"),
        "is_active": state.get("status") == "ACTIVE",
    }


# ============================================================================
# LOOKUP COMPANY BY INN (async)
# ============================================================================

async def lookup_company_by_inn(inn: str) -> dict | None:
    """Look up company info by INN via DaData API.

    Args:
        inn: Company INN (10 digits for legal entity, 12 for individual)

    Returns:
        Normalized company dict or None if not found / error

    Raises:
        ValueError: If INN format is invalid
    """
    if inn is not None:
        inn = str(inn).strip()

    if not validate_inn(inn):
        raise ValueError(f"Invalid INN format: {inn}")

    try:
        response_data = _call_dadata_api(inn)
        suggestions = response_data.get("suggestions", [])
        if not suggestions:
            return None
        return normalize_dadata_result(suggestions[0])
    except ValueError:
        raise
    except Exception:
        return None


# ============================================================================
# CITY SEARCH (sync)
# ============================================================================

def search_cities(query: str, count: int = 10) -> list[dict]:
    """Search cities using DaData address suggestions API.

    Args:
        query: City name to search (min 2 characters after stripping)
        count: Maximum number of results (default 10)

    Returns:
        List of city dicts with keys: city, region, country, display
        Returns [] on any error or for short/empty queries
    """
    if not query or len(query.strip()) < 2:
        return []

    query = query.strip()

    try:
        response_data = _call_dadata_address_api(query, count)
        suggestions = response_data.get("suggestions", [])

        results = []
        for suggestion in suggestions:
            data = suggestion.get("data", {})
            city = data.get("city", "")
            region = data.get("region_with_type", "")
            country = data.get("country", "")

            # Build display string: "City, Region" unless city is a federal city
            # (region = "г Москва" for city "Москва" means they're the same)
            city_is_region = (
                not region
                or region == city
                or region == f"г {city}"
            )
            if city and not city_is_region:
                display = f"{city}, {region}"
            else:
                display = city

            results.append({
                "city": city,
                "region": region,
                "country": country,
                "display": display,
            })

        return results

    except Exception:
        return []
