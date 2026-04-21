"""Tests for /api/plan-fact/* endpoints migrated to FastAPI plan_fact router (Phase 6B-2).

Covers:
- Direct sub-app: routes registered on api_app under /plan-fact/*.
- OpenAPI schema includes the 5 plan-fact endpoints.
- Integration via outer FastHTML app: /api/plan-fact/* resolves through the mount.
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


# ----------------------------------------------------------------------------
# Direct sub-app tests (isolated from FastHTML)
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_sub_app)


class TestPlanFactRoutesRegistered:
    """Assert the 5 plan-fact endpoints are wired to the FastAPI sub-app."""

    def test_get_categories_registered(self, subapp_client: TestClient) -> None:
        """GET /plan-fact/categories must exist (not 404)."""
        response = subapp_client.get("/plan-fact/categories")
        assert response.status_code != 404, (
            f"Route not registered: GET /plan-fact/categories returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_get_items_registered(self, subapp_client: TestClient) -> None:
        """GET /plan-fact/{deal_id}/items must exist."""
        deal_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.get(f"/plan-fact/{deal_id}/items")
        assert response.status_code != 404

    def test_post_items_registered(self, subapp_client: TestClient) -> None:
        """POST /plan-fact/{deal_id}/items must exist."""
        deal_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.post(f"/plan-fact/{deal_id}/items", json={})
        assert response.status_code != 404

    def test_patch_item_registered(self, subapp_client: TestClient) -> None:
        """PATCH /plan-fact/{deal_id}/items/{id} must exist."""
        deal_id = "11111111-1111-1111-1111-111111111111"
        item_id = "22222222-2222-2222-2222-222222222222"
        response = subapp_client.patch(
            f"/plan-fact/{deal_id}/items/{item_id}", json={}
        )
        assert response.status_code != 404

    def test_delete_item_registered(self, subapp_client: TestClient) -> None:
        """DELETE /plan-fact/{deal_id}/items/{id} must exist."""
        deal_id = "11111111-1111-1111-1111-111111111111"
        item_id = "22222222-2222-2222-2222-222222222222"
        response = subapp_client.delete(f"/plan-fact/{deal_id}/items/{item_id}")
        assert response.status_code != 404


class TestPlanFactOpenApiSchema:
    """Verify the plan-fact endpoints appear in the auto-generated OpenAPI schema."""

    def test_schema_includes_all_plan_fact_paths(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        expected_paths = {
            "/plan-fact/categories",
            "/plan-fact/{deal_id}/items",
            "/plan-fact/{deal_id}/items/{id}",
        }
        assert expected_paths.issubset(set(paths.keys())), (
            f"Missing plan-fact paths in OpenAPI: "
            f"{expected_paths - set(paths.keys())}"
        )

    def test_schema_declares_correct_methods(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema["paths"]

        assert "get" in paths["/plan-fact/categories"]
        assert "get" in paths["/plan-fact/{deal_id}/items"]
        assert "post" in paths["/plan-fact/{deal_id}/items"]
        assert "patch" in paths["/plan-fact/{deal_id}/items/{id}"]
        assert "delete" in paths["/plan-fact/{deal_id}/items/{id}"]


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


class TestPlanFactMountIntegration:
    """Verify /api/plan-fact/* reaches the FastAPI sub-app via the outer mount."""

    def test_get_categories_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/plan-fact/categories must resolve through the mount (not 404)."""
        response = outer_app_client.get("/api/plan-fact/categories")
        # No JWT → ApiAuthMiddleware / handler returns 401. 404 would mean the
        # mount didn't route to the plan_fact router.
        assert response.status_code != 404, (
            f"Mount routing broken for GET /api/plan-fact/categories. "
            f"Body: {response.text[:200]}"
        )

    def test_post_items_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/plan-fact/{deal_id}/items must resolve through the mount."""
        deal_id = "11111111-1111-1111-1111-111111111111"
        response = outer_app_client.post(
            f"/api/plan-fact/{deal_id}/items", json={}
        )
        assert response.status_code != 404
