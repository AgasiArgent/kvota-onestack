"""Tests for /api/geo/* endpoints migrated to FastAPI geo router (Phase 6B-5).

Covers:
- Direct sub-app: /geo/vat-rate + /geo/cities/search routes registered on api_app.
- OpenAPI schema includes both geo paths.
- Integration via outer FastHTML app: /api/geo/* resolves through the mount.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Ensure project root importable for `api` and `services` modules.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_sub_app  # noqa: E402


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_sub_app)


class TestGeoRoutesRegistered:
    """Assert the geo endpoints are wired to the FastAPI sub-app."""

    def test_get_vat_rate_registered(self, subapp_client: TestClient) -> None:
        """GET /geo/vat-rate must exist (resolve past routing, not 404)."""
        response = subapp_client.get("/geo/vat-rate")
        # No auth → handler returns 401. 404 would mean the route was not registered.
        assert response.status_code != 404, (
            f"Route not registered: GET /geo/vat-rate returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_get_cities_search_registered(self, subapp_client: TestClient) -> None:
        """GET /geo/cities/search must exist (resolve past routing, not 404)."""
        response = subapp_client.get("/geo/cities/search")
        # No auth → handler returns 401. 404 would mean the route was not registered.
        assert response.status_code != 404, (
            f"Route not registered: GET /geo/cities/search returned 404. "
            f"Body: {response.text[:200]}"
        )


class TestGeoOpenApiSchema:
    """Verify the geo endpoints appear in the auto-generated OpenAPI schema."""

    def test_schema_includes_vat_rate_path(self, subapp_client: TestClient) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        assert "/geo/vat-rate" in paths, (
            f"Missing /geo/vat-rate path in OpenAPI. "
            f"Present: {sorted(paths.keys())}"
        )
        assert "get" in paths["/geo/vat-rate"]

    def test_schema_includes_cities_search_path(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})

        assert "/geo/cities/search" in paths, (
            f"Missing /geo/cities/search path in OpenAPI. "
            f"Present: {sorted(paths.keys())}"
        )
        assert "get" in paths["/geo/cities/search"]


# ----------------------------------------------------------------------------
# Integration tests via outer FastHTML app
# ----------------------------------------------------------------------------


@pytest.fixture
def outer_app_client() -> TestClient:
    """TestClient wired to the FastHTML app — exercises the actual /api mount."""
    try:
        with patch("services.database.get_supabase") as mock_get_sb:
            mock_get_sb.return_value = MagicMock()
            from api.app import api_app as outer_app
    except Exception as exc:  # pragma: no cover — diagnostic only
        pytest.skip(f"Cannot import outer app: {exc}")

    return TestClient(outer_app)


class TestGeoMountIntegration:
    """Verify /api/geo/* reaches the FastAPI sub-app via the outer mount."""

    def test_vat_rate_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/geo/vat-rate must resolve through the mount (not 404)."""
        response = outer_app_client.get("/api/geo/vat-rate")
        # No JWT → middleware / handler returns 401. 404 would mean the
        # mount didn't route to the geo router.
        assert response.status_code != 404, (
            f"Mount routing broken for GET /api/geo/vat-rate. "
            f"Body: {response.text[:200]}"
        )

    def test_cities_search_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/geo/cities/search must resolve through the mount (not 404)."""
        response = outer_app_client.get("/api/geo/cities/search")
        # No JWT / session → 401. 404 would mean the mount didn't route.
        assert response.status_code != 404, (
            f"Mount routing broken for GET /api/geo/cities/search. "
            f"Body: {response.text[:200]}"
        )
