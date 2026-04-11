"""
Tests for services.here_service hardening (Procurement Phase 3, Section 2.1).

Covers:
- LRU cache on search_cities de-duplicates repeated typeahead calls
- Query normalization (case/whitespace) shares cache entries
- pycountry-backed alpha-3 -> alpha-2 mapping for countries outside the legacy
  hardcoded 28-country dict
- Graceful fallback: unknown alpha-3 returns empty string, HERE errors return []

These tests MUST coexist with the existing tests/test_city_autocomplete_here.py
without regressing the legacy /api/cities/search contract.
"""

import os

# Test environment setup (matches conftest defaults, in case this file is
# executed standalone).
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("HERE_API_KEY", "test-here-api-key")

from unittest.mock import patch

import pytest

from services import here_service
from services.here_service import (
    _alpha3_to_alpha2,
    _clear_cache,
    search_cities,
)


# ----------------------------------------------------------------------------
# Sample responses (kept minimal and distinct per query so cache tests can
# assert that the right payload came back).
# ----------------------------------------------------------------------------

BERLIN_RESPONSE = {
    "items": [
        {
            "title": "Berlin, Germany",
            "resultType": "locality",
            "address": {
                "label": "Berlin, Germany",
                "city": "Berlin",
                "state": "Berlin",
                "countryName": "Germany",
                "countryCode": "DEU",
            },
        }
    ]
}


@pytest.fixture(autouse=True)
def _reset_cache():
    """Every test starts with a cold cache so call-count assertions are stable."""
    _clear_cache()
    yield
    _clear_cache()


# ============================================================================
# LRU CACHE — REQ 4.1, 4.2
# ============================================================================


def test_search_cities_caches_identical_queries():
    """Two identical calls result in exactly one HERE API call."""
    with patch.object(here_service, "_call_here_api", return_value=BERLIN_RESPONSE) as mock_api:
        first = search_cities("berlin", 10)
        second = search_cities("berlin", 10)

    assert mock_api.call_count == 1
    assert first == second
    assert first and first[0]["city"] == "Berlin"


def test_search_cities_normalizes_query_for_cache():
    """Whitespace and case differences share the same cache entry."""
    with patch.object(here_service, "_call_here_api", return_value=BERLIN_RESPONSE) as mock_api:
        r1 = search_cities("berlin", 10)
        r2 = search_cities("BERLIN", 10)
        r3 = search_cities("  Berlin  ", 10)

    assert mock_api.call_count == 1
    assert r1 == r2 == r3


def test_search_cities_different_limit_separate_cache_entries():
    """Different `count` arguments must NOT share a cache entry (REQ 4.1 keys on query+limit)."""
    with patch.object(here_service, "_call_here_api", return_value=BERLIN_RESPONSE) as mock_api:
        search_cities("berlin", 10)
        search_cities("berlin", 5)

    assert mock_api.call_count == 2


# ============================================================================
# GRACEFUL DEGRADATION — REQ 4.5, existing behavior
# ============================================================================


def test_search_cities_returns_empty_on_here_error():
    """HERE API failures return [] without crashing (graceful degradation)."""
    with patch.object(here_service, "_call_here_api", side_effect=RuntimeError("boom")):
        result = search_cities("berlin", 10)

    assert result == []


def test_search_cities_empty_query_returns_empty_list():
    """Input validation: empty/whitespace queries bypass the cache entirely."""
    with patch.object(here_service, "_call_here_api") as mock_api:
        assert search_cities("", 10) == []
        assert search_cities("   ", 10) == []
        assert search_cities(None, 10) == []  # type: ignore[arg-type]

    mock_api.assert_not_called()


# ============================================================================
# ALPHA-3 -> ALPHA-2 MAPPING — REQ 4.3, 4.4, 4.6
# ============================================================================


def test_alpha3_to_alpha2_covers_non_hardcoded_countries():
    """pycountry-backed lookup must handle countries outside the legacy 28-entry dict."""
    # These countries are all absent from the legacy alpha3_to_alpha2 dict in
    # the original here_service.py implementation.
    assert _alpha3_to_alpha2("BRA") == "BR"
    assert _alpha3_to_alpha2("EGY") == "EG"
    assert _alpha3_to_alpha2("NGA") == "NG"
    assert _alpha3_to_alpha2("PAK") == "PK"
    assert _alpha3_to_alpha2("ARG") == "AR"


def test_alpha3_to_alpha2_still_covers_legacy_hardcoded_countries():
    """Countries that WERE in the legacy dict still map correctly (non-regression)."""
    assert _alpha3_to_alpha2("DEU") == "DE"
    assert _alpha3_to_alpha2("CHN") == "CN"
    assert _alpha3_to_alpha2("TUR") == "TR"
    assert _alpha3_to_alpha2("USA") == "US"


def test_alpha3_to_alpha2_unknown_code_returns_empty():
    """Unknown codes return empty string, never raise, never return garbage."""
    assert _alpha3_to_alpha2("XXX") == ""
    assert _alpha3_to_alpha2("ZZZ") == ""


def test_alpha3_to_alpha2_empty_input_returns_empty():
    """Empty / None input returns empty string rather than raising."""
    assert _alpha3_to_alpha2("") == ""
    assert _alpha3_to_alpha2(None) == ""  # type: ignore[arg-type]


def test_alpha3_to_alpha2_is_case_insensitive():
    """Lowercase input should still resolve."""
    assert _alpha3_to_alpha2("deu") == "DE"
    assert _alpha3_to_alpha2("bra") == "BR"


# ============================================================================
# NORMALIZATION INTEGRATION — REQ 4.3, 4.5
# ============================================================================


def test_search_cities_normalizes_alpha3_country_codes_in_results():
    """Full pipeline: HERE returns DEU -> normalized result exposes DE."""
    with patch.object(here_service, "_call_here_api", return_value=BERLIN_RESPONSE):
        result = search_cities("berlin", 10)

    assert len(result) == 1
    assert result[0]["country_code"] == "DE"
    assert result[0]["city"] == "Berlin"
    assert result[0]["country"] == "Germany"


def test_search_cities_unknown_country_code_yields_empty_string():
    """A HERE response with an unknown alpha-3 yields country_code='' — no crash, no garbage."""
    unknown_response = {
        "items": [
            {
                "title": "Nowhere, Atlantis",
                "resultType": "locality",
                "address": {
                    "label": "Nowhere, Atlantis",
                    "city": "Nowhere",
                    "countryName": "Atlantis",
                    "countryCode": "XXX",
                },
            }
        ]
    }
    with patch.object(here_service, "_call_here_api", return_value=unknown_response):
        result = search_cities("nowhere", 10)

    assert len(result) == 1
    assert result[0]["country_code"] == ""
