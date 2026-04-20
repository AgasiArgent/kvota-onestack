"""Tests for /api/admin/* endpoints migrated to FastAPI admin router (Phase 6B-1).

Covers:
- Direct sub-app: routes registered on api_app under /admin/*.
- OpenAPI schema includes the 4 admin endpoints.
- Integration via outer FastHTML app: /api/admin/* resolves through the mount.
- Regression: /api/geo/vat-rate still served by legacy @rt handler.
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


# ----------------------------------------------------------------------------
# Direct sub-app tests (isolated from FastHTML)
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_app)


class TestAdminRoutesRegistered:
    """Assert the 4 admin endpoints are wired to the FastAPI sub-app."""

    def test_post_users_registered(self, subapp_client: TestClient) -> None:
        """POST /admin/users must exist (resolve past routing, not 404)."""
        response = subapp_client.post("/admin/users", json={})
        # No auth attached → 401 from the handler. 404 would mean the route
        # was not registered.
        assert response.status_code != 404, (
            f"Route not registered: POST /admin/users returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_patch_user_status_registered(self, subapp_client: TestClient) -> None:
        """PATCH /admin/users/{user_id} must exist."""
        response = subapp_client.patch(
            "/admin/users/11111111-1111-1111-1111-111111111111", json={}
        )
        assert response.status_code != 404

    def test_patch_user_roles_registered(self, subapp_client: TestClient) -> None:
        """PATCH /admin/users/{user_id}/roles must exist."""
        response = subapp_client.patch(
            "/admin/users/11111111-1111-1111-1111-111111111111/roles", json={}
        )
        assert response.status_code != 404

    def test_put_vat_rates_registered(self, subapp_client: TestClient) -> None:
        """PUT /admin/vat-rates must exist."""
        response = subapp_client.put("/admin/vat-rates", json={})
        assert response.status_code != 404


class TestAdminOpenApiSchema:
    """Verify the admin endpoints appear in the auto-generated OpenAPI schema."""

    def test_schema_includes_all_four_admin_paths(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        expected_paths = {
            "/admin/users",
            "/admin/users/{user_id}",
            "/admin/users/{user_id}/roles",
            "/admin/vat-rates",
        }
        assert expected_paths.issubset(set(paths.keys())), (
            f"Missing admin paths in OpenAPI: "
            f"{expected_paths - set(paths.keys())}"
        )

    def test_schema_declares_correct_methods(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema["paths"]

        assert "post" in paths["/admin/users"]
        assert "patch" in paths["/admin/users/{user_id}"]
        assert "patch" in paths["/admin/users/{user_id}/roles"]
        assert "put" in paths["/admin/vat-rates"]


# ----------------------------------------------------------------------------
# Integration tests via outer FastHTML app
# ----------------------------------------------------------------------------


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


class TestAdminMountIntegration:
    """Verify /api/admin/* reaches the FastAPI sub-app via the outer mount."""

    def test_post_admin_users_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/admin/users must resolve through the mount (not 404)."""
        response = outer_app_client.post("/api/admin/users", json={})
        # No JWT → ApiAuthMiddleware / handler returns 401. 404 would mean the
        # mount didn't route to the admin router.
        assert response.status_code != 404, (
            f"Mount routing broken for POST /api/admin/users. "
            f"Body: {response.text[:200]}"
        )

    def test_put_admin_vat_rates_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """PUT /api/admin/vat-rates must resolve through the mount."""
        response = outer_app_client.put("/api/admin/vat-rates", json={})
        assert response.status_code != 404


class TestGeoVatRateLegacyRegression:
    """GET /api/geo/vat-rate is still served by @rt in main.py (migrates in 6B-5)."""

    def test_legacy_geo_vat_rate_still_reachable(
        self, outer_app_client: TestClient
    ) -> None:
        """The GET endpoint must continue working via the @rt wrapper."""
        response = outer_app_client.get("/api/geo/vat-rate")
        # Without auth or country_code, handler returns 401 or 400. 404 would
        # mean the @rt registration was accidentally removed.
        assert response.status_code != 404, (
            f"Legacy @rt('/api/geo/vat-rate') was removed. "
            f"Body: {response.text[:200]}"
        )
