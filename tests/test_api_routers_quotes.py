"""Tests for /api/quotes/* endpoints migrated to FastAPI quotes router (Phase 6B-2).

Covers:
- Direct sub-app: GET /quotes/search registered on api_app.
- OpenAPI schema includes the /quotes/search endpoint.
- Integration via outer FastHTML app: /api/quotes/search resolves through the mount.

This file grows in 6B-4 (procurement kanban) and 6B-6 (quote actions) as
additional /api/quotes/* endpoints migrate into api/routers/quotes.py.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Ensure project root importable for `api` and `services` modules.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_app  # noqa: E402


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_app)


class TestQuotesSearchRouteRegistered:
    """Assert the /quotes/search endpoint is wired to the FastAPI sub-app."""

    def test_get_search_registered(self, subapp_client: TestClient) -> None:
        """GET /quotes/search must exist (not 404)."""
        response = subapp_client.get("/quotes/search")
        assert response.status_code != 404, (
            f"Route not registered: GET /quotes/search returned 404. "
            f"Body: {response.text[:200]}"
        )


class TestQuotesOpenApiSchema:
    """Verify /quotes/search appears in the auto-generated OpenAPI schema."""

    def test_schema_includes_search_path(self, subapp_client: TestClient) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        assert "/quotes/search" in paths, (
            f"Missing /quotes/search path in OpenAPI. "
            f"Present: {sorted(paths.keys())}"
        )
        assert "get" in paths["/quotes/search"]


@pytest.fixture
def outer_app_client() -> TestClient:
    """TestClient wired to the FastHTML app — exercises the actual /api mount."""
    try:
        with patch("services.database.get_supabase") as mock_get_sb:
            mock_get_sb.return_value = MagicMock()
            from main import app as outer_app
    except Exception as exc:  # pragma: no cover — diagnostic only
        pytest.skip(f"Cannot import outer app: {exc}")

    return TestClient(outer_app)


class TestQuotesMountIntegration:
    """Verify /api/quotes/search reaches the FastAPI sub-app via the outer mount."""

    def test_get_search_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/quotes/search must resolve through the mount (not 404)."""
        response = outer_app_client.get("/api/quotes/search")
        # No JWT → auth middleware / handler returns 401. 404 would mean the
        # mount didn't route to the quotes router.
        assert response.status_code != 404, (
            f"Mount routing broken for GET /api/quotes/search. "
            f"Body: {response.text[:200]}"
        )
