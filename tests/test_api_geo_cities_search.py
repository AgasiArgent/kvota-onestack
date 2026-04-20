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

Phase 6B-5 note: the handler was extracted from main.py into api/geo.py as
`async def get_cities_search(request)`. Query params now parsed from
`request.query_params` instead of kwargs, and session access uses
`request.session` (SessionMiddleware is installed on the outer app).
"""

import asyncio
import inspect
import json
import os
from types import SimpleNamespace
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


def _run(coro):
    """Execute an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_request(
    *,
    api_user=None,
    session: dict | None = None,
    q: str = "",
    limit: str | int = "10",
):
    """Build a mock Starlette-style request.

    - api_user: attached to request.state.api_user (JWT path)
    - session: backing dict for request.session (FastHTML path)
    - q, limit: query params returned by request.query_params.get(...)
    """
    request = MagicMock()
    request.state = SimpleNamespace(api_user=api_user)

    if session is None:
        # Accessing request.session must raise so the handler treats it as "no session".
        type(request).session = property(
            lambda _self: (_ for _ in ()).throw(
                AssertionError("SessionMiddleware not installed")
            )
        )
    else:
        # Plain attribute on the instance (SimpleNamespace-style).
        request.session = session

    query_map = {"q": q, "limit": str(limit)}

    qp = MagicMock()
    qp.get = lambda key, default=None: query_map.get(key, default)
    request.query_params = qp

    return request


@pytest.fixture
def request_authenticated_session():
    """Request authenticated via a FastHTML-style session dict."""
    return _make_request(
        api_user=None,
        session={
            "user": {
                "id": "test-user-id",
                "email": "test@example.com",
                "org_id": "test-org-id",
                "roles": ["sales"],
            }
        },
        q="Berlin",
        limit="10",
    )


@pytest.fixture
def request_authenticated_jwt():
    """Request authenticated via a Supabase JWT user."""
    jwt_user = MagicMock()
    jwt_user.id = "jwt-user-id"
    jwt_user.email = "jwt@example.com"
    jwt_user.user_metadata = {}
    return _make_request(
        api_user=jwt_user,
        session=None,
        q="Berlin",
        limit="10",
    )


@pytest.fixture
def request_anonymous():
    """Request with neither JWT nor session — should 401."""
    return _make_request(
        api_user=None,
        session=None,  # request.session raises → treated as missing
        q="Berlin",
        limit="10",
    )


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
    """Extract JSON body from a Starlette Response."""
    body = response.body
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return json.loads(body)


def _get_handler():
    """Import the extracted endpoint handler from api.geo."""
    from api.geo import get_cities_search

    return get_cities_search


# ============================================================================
# Handler presence & docstring (REQ 3.8)
# ============================================================================


def test_handler_exists():
    """The get_cities_search handler must exist in api.geo."""
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
    assert "Side Effects" in doc, "Handler docstring missing 'Side Effects' section"


# ============================================================================
# 200 OK — valid query (REQ 3.1, 3.4)
# ============================================================================


def test_valid_query_returns_200_with_data(request_authenticated_session):
    """Valid query (>= 2 chars) returns 200 + {success: true, data: [...]}."""
    handler = _get_handler()
    with patch("services.here_service.search_cities", return_value=BERLIN_RESULT):
        response = _run(handler(request_authenticated_session))

    assert response.status_code == 200
    body = _parse_json(response)
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 1
    entry = body["data"][0]
    assert entry["city"] == "Berlin"
    assert entry["country_code"] == "DE"
    assert "country_name_ru" in entry
    assert "country_name_en" in entry
    assert "display" in entry


def test_limit_is_clamped_to_upper_bound(request_authenticated_session):
    """limit > 25 is silently clamped to 25 (REQ 3.3)."""
    handler = _get_handler()
    request_authenticated_session.query_params.get = lambda key, default=None: {
        "q": "Berlin",
        "limit": "500",
    }.get(key, default)

    with patch(
        "services.here_service.search_cities", return_value=[]
    ) as mock_search:
        _run(handler(request_authenticated_session))

    call = mock_search.call_args
    passed_count = (
        call.kwargs.get("count")
        if "count" in call.kwargs
        else (call.args[1] if len(call.args) > 1 else None)
    )
    assert passed_count == 25


def test_limit_is_clamped_to_lower_bound(request_authenticated_session):
    """limit < 1 is silently clamped to 1 (REQ 3.3)."""
    handler = _get_handler()
    request_authenticated_session.query_params.get = lambda key, default=None: {
        "q": "Berlin",
        "limit": "0",
    }.get(key, default)

    with patch(
        "services.here_service.search_cities", return_value=[]
    ) as mock_search:
        _run(handler(request_authenticated_session))

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


def test_missing_query_returns_400(request_authenticated_session):
    """Missing q (empty string) returns 400 with INVALID_QUERY code."""
    handler = _get_handler()
    request_authenticated_session.query_params.get = lambda key, default=None: {
        "q": "",
        "limit": "10",
    }.get(key, default)

    response = _run(handler(request_authenticated_session))
    assert response.status_code == 400
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_QUERY"


def test_short_query_returns_400(request_authenticated_session):
    """Single-char query returns 400 with INVALID_QUERY code."""
    handler = _get_handler()
    request_authenticated_session.query_params.get = lambda key, default=None: {
        "q": "B",
        "limit": "10",
    }.get(key, default)

    response = _run(handler(request_authenticated_session))
    assert response.status_code == 400
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_QUERY"


def test_whitespace_only_query_returns_400(request_authenticated_session):
    """Whitespace-only query returns 400 (the TRIMMED length is what counts)."""
    handler = _get_handler()
    request_authenticated_session.query_params.get = lambda key, default=None: {
        "q": "   ",
        "limit": "10",
    }.get(key, default)

    response = _run(handler(request_authenticated_session))
    assert response.status_code == 400
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_QUERY"


# ============================================================================
# 401 — unauthenticated (REQ 3.7)
# ============================================================================


def test_unauthenticated_returns_401(request_anonymous):
    """No session cookie and no JWT -> 401 with structured error."""
    handler = _get_handler()
    response = _run(handler(request_anonymous))
    assert response.status_code == 401
    body = _parse_json(response)
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_jwt_auth_bypasses_session_check(request_authenticated_jwt):
    """A JWT user is allowed through even when the session dict is empty."""
    handler = _get_handler()
    with patch("services.here_service.search_cities", return_value=BERLIN_RESULT):
        response = _run(handler(request_authenticated_jwt))
    assert response.status_code == 200
    body = _parse_json(response)
    assert body["success"] is True


# ============================================================================
# 200 OK — HERE failure returns empty array (REQ 3.5, 3.6)
# ============================================================================


def test_here_failure_returns_200_empty_data(request_authenticated_session):
    """When HERE returns [], the endpoint returns 200 + [] (graceful degradation)."""
    handler = _get_handler()
    # search_cities already handles exceptions internally — we simulate the
    # downstream graceful-degradation by having it return []. The endpoint
    # must pass that through as a 200 OK empty data array, NOT as a 500.
    with patch("services.here_service.search_cities", return_value=[]):
        response = _run(handler(request_authenticated_session))
    assert response.status_code == 200
    body = _parse_json(response)
    assert body["success"] is True
    assert body["data"] == []


# ============================================================================
# Legacy HTMX endpoint preservation — REMOVED (Phase 6C-1, 2026-04-20)
# ============================================================================
# The legacy `@rt("/api/cities/search")` HTMX handler was archived to
# legacy-fasthtml/cities_search.py. `GET /api/geo/cities/search` (above) is
# now the sole live endpoint for city autocomplete.
# ============================================================================
