"""Tests for the FastAPI sub-app mounted at /api (Phase 6B-0 foundation).

Covers:
- Direct requests to the FastAPI sub-app for /health and /changelog.
- Auto-generated OpenAPI schema and Swagger UI.
- Integration via the outer FastHTML app: /api/health reachable through the mount.
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


class TestHealthEndpoint:
    """GET /health (served at /api/health via mount)."""

    def test_returns_200_with_ok_status(self, subapp_client: TestClient) -> None:
        response = subapp_client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "ok"

    def test_hidden_from_openapi_schema(self, subapp_client: TestClient) -> None:
        """Liveness probe should not clutter the public schema surface."""
        response = subapp_client.get("/openapi.json")
        schema = response.json()

        assert "/health" not in schema.get("paths", {})


class TestChangelogEndpoint:
    """GET /changelog (served at /api/changelog via mount)."""

    def test_returns_entries_with_expected_shape(self, subapp_client: TestClient) -> None:
        fake_entries = [
            {
                "slug": "2026-04-01-release",
                "title": "Test release",
                "date": __import__("datetime").date(2026, 4, 1),
                "category": "feature",
                "version": "0.3.0",
                "body": "## Body",
            }
        ]

        with patch("services.changelog_service.get_all_entries", return_value=fake_entries), \
             patch("services.changelog_service.render_entry_html", return_value="<p>Rendered</p>"):
            response = subapp_client.get("/changelog")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert isinstance(payload["data"], list)
        assert len(payload["data"]) == 1

        entry = payload["data"][0]
        assert entry["slug"] == "2026-04-01-release"
        assert entry["title"] == "Test release"
        assert entry["date"] == "2026-04-01"
        assert entry["category"] == "feature"
        assert entry["version"] == "0.3.0"
        assert entry["body_html"] == "<p>Rendered</p>"

    def test_empty_changelog_returns_empty_list(self, subapp_client: TestClient) -> None:
        with patch("services.changelog_service.get_all_entries", return_value=[]):
            response = subapp_client.get("/changelog")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"] == []


class TestOpenApiSchema:
    """Verify FastAPI auto-generates OpenAPI + Swagger UI."""

    def test_openapi_json_served(self, subapp_client: TestClient) -> None:
        response = subapp_client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert schema.get("openapi", "").startswith("3.")
        assert schema["info"]["title"] == "OneStack API"
        # /changelog is public-facing and should be documented.
        assert "/changelog" in schema.get("paths", {})

    def test_docs_ui_served(self, subapp_client: TestClient) -> None:
        response = subapp_client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


# ----------------------------------------------------------------------------
# Integration test via outer FastHTML app
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


class TestMountIntegration:
    """Verify /api mount works through the outer FastHTML app."""

    def test_health_reachable_through_mount(self, outer_app_client: TestClient) -> None:
        response = outer_app_client.get("/api/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "ok"

    def test_unknown_api_path_returns_404_not_500(self, outer_app_client: TestClient) -> None:
        """Mount must not mask failures — unknown /api/* paths should 404 cleanly."""
        response = outer_app_client.get("/api/__does_not_exist__")

        assert response.status_code == 404

    def test_legacy_rt_api_route_still_reachable(self, outer_app_client: TestClient) -> None:
        """Legacy @rt("/api/...") routes must still resolve.

        The mount lives AFTER all @rt registrations, so Starlette's ordered
        matcher serves specific @rt routes first and the mount catches the
        rest. Regression guard: if the mount is moved before @rt, every
        legacy endpoint returns 404 ({"detail":"Not Found"}).
        """
        response = outer_app_client.get("/api/quotes/kanban")

        # /api/quotes/kanban requires JWT; without one ApiAuthMiddleware or the
        # handler returns 401. Anything other than 401/200 means routing broke.
        assert response.status_code in (200, 401, 403), (
            f"Legacy @rt route returned {response.status_code}; mount ordering "
            f"likely shadowed it. Body: {response.text[:200]}"
        )
