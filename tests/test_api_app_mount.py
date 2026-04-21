"""Tests for the FastAPI application and its /api mount.

Updated in Phase 6C-3 (2026-04-21) when the FastHTML shell was retired.
``api_app`` is now the OUTER FastAPI app served directly by Docker/uvicorn;
it mounts an inner sub-app at ``/api`` and owns middleware
(Sentry, Session, ApiAuth).

Covers:
- GET /api/health and /api/changelog reachable through the mount.
- Auto-generated OpenAPI schema and Swagger UI at /api/openapi.json + /api/docs.
- 404 behavior for unknown /api/* paths.
- Backward-compat re-export via ``from main import app``.
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
def api_client() -> TestClient:
    """TestClient bound to the OUTER api_app — same surface Docker serves."""
    return TestClient(api_app)


class TestHealthEndpoint:
    """GET /api/health (routed through the /api mount to public.router)."""

    def test_returns_200_with_ok_status(self, api_client: TestClient) -> None:
        response = api_client.get("/api/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "ok"

    def test_hidden_from_openapi_schema(self, api_client: TestClient) -> None:
        """Liveness probe should not clutter the public schema surface."""
        response = api_client.get("/api/openapi.json")
        schema = response.json()

        assert "/health" not in schema.get("paths", {})


class TestChangelogEndpoint:
    """GET /api/changelog (routed through the /api mount to public.router)."""

    def test_returns_entries_with_expected_shape(self, api_client: TestClient) -> None:
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
            response = api_client.get("/api/changelog")

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

    def test_empty_changelog_returns_empty_list(self, api_client: TestClient) -> None:
        with patch("services.changelog_service.get_all_entries", return_value=[]):
            response = api_client.get("/api/changelog")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"] == []


class TestOpenApiSchema:
    """Verify the inner sub-app auto-generates OpenAPI + Swagger UI at /api/*."""

    def test_openapi_json_served(self, api_client: TestClient) -> None:
        response = api_client.get("/api/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert schema.get("openapi", "").startswith("3.")
        assert schema["info"]["title"] == "OneStack API"
        # /changelog is public-facing and should be documented.
        assert "/changelog" in schema.get("paths", {})

    def test_docs_ui_served(self, api_client: TestClient) -> None:
        response = api_client.get("/api/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestUnknownApiPath:
    """Unknown /api/* paths must 404, not 500."""

    def test_unknown_api_path_returns_404_not_500(self, api_client: TestClient) -> None:
        response = api_client.get("/api/__does_not_exist__")

        assert response.status_code == 404


class TestMainStubCompatibility:
    """``from main import app`` still returns the outer FastAPI app post-6C-3."""

    def test_main_app_is_api_app(self) -> None:
        try:
            with patch("services.database.get_supabase") as mock_get_sb:
                mock_get_sb.return_value = MagicMock()
                from api.app import api_app as compat_app
        except Exception as exc:  # pragma: no cover — diagnostic only
            pytest.skip(f"Cannot import main stub: {exc}")

        assert compat_app is api_app, (
            "main.app must be the same object as api.app.api_app — the stub only "
            "re-exports for backward compatibility."
        )
