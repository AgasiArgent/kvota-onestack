"""Tests for /api/cron/* endpoints migrated to FastAPI cron router (Phase 6B-5).

Covers:
- Direct sub-app: /cron/check-overdue route registered on api_app.
- OpenAPI schema includes the cron path.
- PUBLIC_API_PATHS entry — middleware passes without auth; handler enforces
  X-Cron-Secret separately.
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


class TestCronRoutesRegistered:
    """Assert the cron endpoint is wired to the FastAPI sub-app."""

    def test_get_check_overdue_registered(self, subapp_client: TestClient) -> None:
        """GET /cron/check-overdue must exist (resolve past routing, not 404)."""
        response = subapp_client.get("/cron/check-overdue")
        # Without X-Cron-Secret → handler returns 403 or 500 (if env missing).
        # 404 would mean the route was not registered.
        assert response.status_code != 404, (
            f"Route not registered: GET /cron/check-overdue returned 404. "
            f"Body: {response.text[:200]}"
        )


class TestCronOpenApiSchema:
    """Verify the cron endpoint appears in the auto-generated OpenAPI schema."""

    def test_schema_includes_check_overdue_path(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        assert "/cron/check-overdue" in paths, (
            f"Missing /cron/check-overdue path in OpenAPI. "
            f"Present: {sorted(paths.keys())}"
        )
        assert "get" in paths["/cron/check-overdue"]


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


class TestCronMountIntegration:
    """Verify /api/cron/* reaches the FastAPI sub-app via the outer mount.

    The cron route is in api.auth.PUBLIC_API_PATHS so JWT middleware must
    pass through without auth. The handler itself enforces X-Cron-Secret.
    """

    def test_check_overdue_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/cron/check-overdue must resolve through the mount."""
        response = outer_app_client.get("/api/cron/check-overdue")
        # Without X-Cron-Secret → handler returns 403 (or 500 if env missing).
        # 404 would mean the mount didn't route to the cron router.
        # 401 would mean middleware didn't recognize the public path.
        assert response.status_code != 404, (
            f"Mount routing broken for GET /api/cron/check-overdue. "
            f"Body: {response.text[:200]}"
        )
        assert response.status_code != 401, (
            "Middleware returned 401 — PUBLIC_API_PATHS not respected. "
            f"Body: {response.text[:200]}"
        )
