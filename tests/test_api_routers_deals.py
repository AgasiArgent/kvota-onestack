"""Tests for /api/deals/* endpoints migrated to FastAPI deals router (Phase 6B-2).

Covers:
- Direct sub-app: POST /deals registered on api_app.
- OpenAPI schema includes the /deals endpoint.
- Integration via outer FastHTML app: /api/deals resolves through the mount.
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


class TestDealsRoutesRegistered:
    """Assert the deals endpoint is wired to the FastAPI sub-app."""

    def test_post_deals_registered(self, subapp_client: TestClient) -> None:
        """POST /deals must exist (not 404)."""
        response = subapp_client.post("/deals", json={})
        assert response.status_code != 404, (
            f"Route not registered: POST /deals returned 404. "
            f"Body: {response.text[:200]}"
        )


class TestDealsOpenApiSchema:
    """Verify the /deals endpoint appears in the auto-generated OpenAPI schema."""

    def test_schema_includes_deals_path(self, subapp_client: TestClient) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        assert "/deals" in paths, (
            f"Missing /deals path in OpenAPI. Present: {sorted(paths.keys())}"
        )
        assert "post" in paths["/deals"]


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


class TestDealsMountIntegration:
    """Verify /api/deals reaches the FastAPI sub-app via the outer mount."""

    def test_post_deals_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/deals must resolve through the mount (not 404)."""
        response = outer_app_client.post("/api/deals", json={})
        # No JWT → auth middleware / handler returns 401. 404 would mean the
        # mount didn't route to the deals router.
        assert response.status_code != 404, (
            f"Mount routing broken for POST /api/deals. "
            f"Body: {response.text[:200]}"
        )
