"""
Tests for GET /api/geo/cities/search — Procurement Phase 3, Section 2.2.

Contract:
    200 OK    — valid query → {"success": True, "data": [...]}
    200 OK    — HERE failure → {"success": True, "data": []} (graceful degradation)
    400       — missing or < 2-char q → {"success": False, "error": {"code": "INVALID_QUERY", ...}}
    401       — unauthenticated → {"success": False, "error": {"code": "UNAUTHENTICATED", ...}}

Auth: dual-auth (Supabase JWT via `request.state.api_user` OR legacy session).
Docstring: must include Path/Params/Returns/Roles sections per api-first.md.

The legacy HTMX endpoint `GET /api/cities/search` (FastHTML Option output) is
NOT touched — regression coverage lives in `tests/test_city_autocomplete_here.py`.
"""

import inspect
import json
import os
import re
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("HERE_API_KEY", "test-here-api-key")


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture
def mock_session_authenticated():
    """A session dict with a logged-in user (bypasses require_login)."""
    return {
        "user": {
            "id": "test-user-id",
            "email": "test@example.com",
            "org_id": "test-org-id",
            "roles": ["sales"],
        }
    }


@pytest.fixture
def mock_session_anonymous():
    """Empty session — should cause 401 unauthenticated."""
    return {}


@pytest.fixture
def mock_request_no_jwt():
    """Starlette request with no JWT (legacy session auth path)."""
    request = MagicMock()
    request.state = MagicMock()
    request.state.api_user = None
    return request


@pytest.fixture
def mock_request_with_jwt():
    """Starlette request with a JWT user (Next.js path)."""
    request = MagicMock()
    request.state = MagicMock()
    jwt_user = MagicMock()
    jwt_user.id = "jwt-user-id"
    jwt_user.email = "jwt@example.com"
    jwt_user.user_metadata = {}
    request.state.api_user = jwt_user
    return request


BERLIN_RESULT = [
    {
        "city": "Berlin",
        "region": "Berlin",
        "country": "Germany",
        "country_code": "DE",
        "display": "Berlin, Germany",
    }
]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _parse_json(response):
    """Extract JSON body from a Starlette Response returned by the handler."""
    body = response.body
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return json.loads(body)


def _get_handler():
    """Import the new endpoint handler from main.py.

    The endpoint is registered via `@rt("/api/geo/cities/search")` which
    wraps the inner function. We import the underlying callable by name
    (it is stored on the module as `get_api_geo_cities_search` per our
    implementation plan — see the handler's `__name__` or module attribute).
    """
    from main import get_api_geo_cities_search  # noqa: WPS433 — test imports

    return get_api_geo_cities_search


# ============================================================================
# Handler presence & docstring (REQ 3.8)
# ============================================================================


def test_handler_exists():
    """The GET /api/geo/cities/search handler must exist in main.py."""
    handler = _get_handler()
    assert callable(handler)


def test_handler_docstring_has_required_sections():
    """Per api-first.md, the docstring must include Path/Params/Returns/Roles."""
    handler = _get_handler()
    doc = inspect.getdoc(handler) or ""
    assert "Path:" in doc, "Handler docstring missing 'Path:' section"
    assert "Params:" in doc, "Handler docstring missing 'Params:' section"
    assert "Returns:" in doc, "Handler docstring missing 'Returns:' section"
    assert "Roles:" in doc, "Handler docstring missing 'Roles:' section"
    # Side Effects is REQ 3.8 per design §4
    assert "Side Effects" in doc, "Handler docstring missing 'Side Effects' section"


# ============================================================================
# 200 OK — valid query (REQ 3.1, 3.4)
# ============================================================================


def test_valid_query_returns_200_with_data(
    mock_session_authenticated, mock_request_no_jwt
):
    """Valid query (>= 2 chars) returns 200 + {success: true, data: [...]}."""
    handler = _get_handler()
    with patch("services.here_service.search_cities", return_value=BERLIN_RESULT):
        response = handler(
            session=mock_session_authenticated,
            request=mock_request_no_jwt,
            q="Berlin",
            limit=10,
        )

    assert response.status_code == 200
    body = _parse_json(response)
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 1
    entry = body["data"][0]
    assert entry["city"] == "Berlin"
    assert entry["country_code"] == "DE"
    # Bilingual country names per REQ 8.5
    assert "country_name_ru" in entry
    assert "country_name_en" in entry
    assert "display" in entry


def test_limit_is_clamped_to_upper_bound(
    mock_session_authenticated, mock_request_no_jwt
):
    """limit > 25 is silently clamped to 25 (REQ 3.3)."""
    handler = _get_handler()
    with patch(
        "services.here_service.search_cities", return_value=[]
    ) as mock_search:
        handler(
            session=mock_session_authenticated,
            request=mock_request_no_jwt,
            q="Berlin",
            limit=500,
        )
    # The service should have been called with count <= 25
    call = mock_search.call_args
    # Accept either positional or keyword argument forms
    passed_count = (
        call.kwargs.get("count")
        if "count" in call.kwargs
        else (call.args[1] if len(call.args) > 1 else None)
    )
    assert passed_count == 25


def test_limit_is_clamped_to_lower_bound(
    mock_session_authenticated, mock_request_no_jwt
):
    """limit < 1 is silently clamped to 1 (REQ 3.3)."""
    handler = _get_handler()
    with patch(
        "services.here_service.search_cities", return_value=[]
    ) as mock_search:
        handler(
            session=mock_session_authenticated,
            request=mock_request_no_jwt,
            q="Berlin",
            limit=0,
        )
    call = mock_search.call_args
    passed_count = (
        call.kwargs.get("count")
        if "count" in call.kwargs
        else (call.args[1] if len(call.args) > 1 else None)
    )
    assert passed_count == 1


# ============================================================================
# 400 — invalid query (REQ 3.2)
# ============================================================================


def test_missing_query_returns_400(
    mock_session_authenticated, mock_request_no_jwt
):
    """Missing q (empty string) returns 400 with INVALID_QUERY code."""
    handler = _get_handler()
    response = handler(
        session=mock_session_authenticated,
        request=mock_request_no_jwt,
        q="",
        limit=10,
    )
    assert response.status_code == 400
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_QUERY"


def test_short_query_returns_400(
    mock_session_authenticated, mock_request_no_jwt
):
    """Single-char query returns 400 with INVALID_QUERY code."""
    handler = _get_handler()
    response = handler(
        session=mock_session_authenticated,
        request=mock_request_no_jwt,
        q="B",
        limit=10,
    )
    assert response.status_code == 400
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_QUERY"


def test_whitespace_only_query_returns_400(
    mock_session_authenticated, mock_request_no_jwt
):
    """Whitespace-only query returns 400 (the TRIMMED length is what counts)."""
    handler = _get_handler()
    response = handler(
        session=mock_session_authenticated,
        request=mock_request_no_jwt,
        q="   ",
        limit=10,
    )
    assert response.status_code == 400
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_QUERY"


# ============================================================================
# 401 — unauthenticated (REQ 3.7)
# ============================================================================


def test_unauthenticated_returns_401(
    mock_session_anonymous, mock_request_no_jwt
):
    """No session cookie and no JWT -> 401 with structured error."""
    handler = _get_handler()
    response = handler(
        session=mock_session_anonymous,
        request=mock_request_no_jwt,
        q="Berlin",
        limit=10,
    )
    assert response.status_code == 401
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_jwt_auth_bypasses_session_check(
    mock_session_anonymous, mock_request_with_jwt
):
    """A JWT user is allowed through even when the session dict is empty."""
    handler = _get_handler()
    with patch("services.here_service.search_cities", return_value=BERLIN_RESULT):
        response = handler(
            session=mock_session_anonymous,
            request=mock_request_with_jwt,
            q="Berlin",
            limit=10,
        )
    assert response.status_code == 200
    body = _parse_json(response)
    assert body["success"] is True


# ============================================================================
# 200 OK — HERE failure returns empty array (REQ 3.5, 3.6)
# ============================================================================


def test_here_failure_returns_200_empty_data(
    mock_session_authenticated, mock_request_no_jwt
):
    """When HERE raises, the endpoint returns 200 + [] (graceful degradation)."""
    handler = _get_handler()
    # search_cities already handles exceptions internally — we simulate the
    # downstream graceful-degradation by having it return []. The endpoint
    # must pass that through as a 200 OK empty data array, NOT as a 500.
    with patch("services.here_service.search_cities", return_value=[]):
        response = handler(
            session=mock_session_authenticated,
            request=mock_request_no_jwt,
            q="Berlin",
            limit=10,
        )
    assert response.status_code == 200
    body = _parse_json(response)
    assert body["success"] is True
    assert body["data"] == []


# ============================================================================
# Legacy endpoint preservation (REQ 3.9, 9.5)
# ============================================================================


def test_legacy_cities_search_endpoint_still_exists():
    """The legacy `/api/cities/search` route must remain in main.py."""
    with open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"),
        "r",
    ) as f:
        source = f.read()
    assert '@rt("/api/cities/search")' in source, (
        "Legacy /api/cities/search HTMX endpoint must not be removed"
    )
    # And the new one exists too (registered via @app.get for discoverable name)
    assert '"/api/geo/cities/search"' in source, (
        "New /api/geo/cities/search JSON endpoint must be registered"
    )
