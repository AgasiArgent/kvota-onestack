"""Tests for /api/quotes/* endpoints migrated to FastAPI quotes router.

Covers (after Phase 6B-2 + 6B-4):
- Direct sub-app: GET /quotes/search, /quotes/kanban, plus composition +
  substatus + status-history routes registered on api_app.
- OpenAPI schema includes all expected endpoints.
- Integration via outer FastHTML app: /api/quotes/* resolves through the mount.
- Route ordering: /kanban is NOT shadowed by /{quote_id}/status-history.

This file grows in 6B-6 (quote actions) as additional /api/quotes/*
endpoints migrate into api/routers/quotes.py.
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


class TestQuotesSearchRouteRegistered:
    """Assert the /quotes/search endpoint is wired to the FastAPI sub-app."""

    def test_get_search_registered(self, subapp_client: TestClient) -> None:
        """GET /quotes/search must exist (not 404)."""
        response = subapp_client.get("/quotes/search")
        assert response.status_code != 404, (
            f"Route not registered: GET /quotes/search returned 404. "
            f"Body: {response.text[:200]}"
        )


class TestQuotesKanbanAndWorkflowRoutes:
    """6B-4: kanban + substatus + status-history + composition endpoints."""

    _QUOTE_ID = "11111111-1111-1111-1111-111111111111"

    def test_get_kanban_registered(self, subapp_client: TestClient) -> None:
        """GET /quotes/kanban must exist (not 404)."""
        response = subapp_client.get("/quotes/kanban")
        assert response.status_code != 404, (
            "GET /quotes/kanban not registered. "
            f"Body: {response.text[:200]}"
        )

    def test_kanban_not_shadowed_by_quote_id_routes(
        self, subapp_client: TestClient
    ) -> None:
        """/kanban must NOT be captured by /{quote_id}/status-history.

        If route ordering were wrong, /kanban would match {quote_id}=kanban
        and hit status-history — a GET that handler may accept. The strongest
        routing signal is that OpenAPI lists /quotes/kanban as its own path.
        """
        response = subapp_client.get("/openapi.json")
        paths = response.json().get("paths", {})
        assert "/quotes/kanban" in paths, (
            "/quotes/kanban is not its own path; route ordering likely "
            f"shadowed by /{{quote_id}}/*. Present: {sorted(paths.keys())}"
        )

    def test_post_substatus_registered(self, subapp_client: TestClient) -> None:
        """POST /quotes/{quote_id}/substatus must exist."""
        response = subapp_client.post(
            f"/quotes/{self._QUOTE_ID}/substatus", json={}
        )
        assert response.status_code != 404

    def test_get_status_history_registered(
        self, subapp_client: TestClient
    ) -> None:
        """GET /quotes/{quote_id}/status-history must exist."""
        response = subapp_client.get(
            f"/quotes/{self._QUOTE_ID}/status-history"
        )
        assert response.status_code != 404

    def test_get_composition_registered(self, subapp_client: TestClient) -> None:
        """GET /quotes/{quote_id}/composition must exist."""
        response = subapp_client.get(
            f"/quotes/{self._QUOTE_ID}/composition"
        )
        assert response.status_code != 404

    def test_post_composition_registered(self, subapp_client: TestClient) -> None:
        """POST /quotes/{quote_id}/composition must exist."""
        response = subapp_client.post(
            f"/quotes/{self._QUOTE_ID}/composition", json={}
        )
        assert response.status_code != 404


class TestQuotesSoftDeleteRoutes:
    """6B-5: admin-only soft-delete + restore endpoints."""

    _QUOTE_ID = "11111111-1111-1111-1111-111111111111"

    def test_post_soft_delete_registered(self, subapp_client: TestClient) -> None:
        """POST /quotes/{quote_id}/soft-delete must exist."""
        response = subapp_client.post(f"/quotes/{self._QUOTE_ID}/soft-delete")
        # No auth → 401. 404 would mean the route was not registered.
        assert response.status_code != 404, (
            f"Route not registered: POST /quotes/{{id}}/soft-delete returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_post_restore_registered(self, subapp_client: TestClient) -> None:
        """POST /quotes/{quote_id}/restore must exist."""
        response = subapp_client.post(f"/quotes/{self._QUOTE_ID}/restore")
        assert response.status_code != 404, (
            f"Route not registered: POST /quotes/{{id}}/restore returned 404. "
            f"Body: {response.text[:200]}"
        )


class TestQuotesCalculateRoute:
    """6B-6a: POST /{quote_id}/calculate extracted from main.py."""

    _QUOTE_ID = "11111111-1111-1111-1111-111111111111"

    def test_post_calculate_registered(self, subapp_client: TestClient) -> None:
        """POST /quotes/{quote_id}/calculate must exist on the sub-app."""
        response = subapp_client.post(f"/quotes/{self._QUOTE_ID}/calculate")
        # No auth → 401. 404 would mean the route was not registered.
        assert response.status_code != 404, (
            "Route not registered: POST /quotes/{id}/calculate returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_schema_includes_calculate_path(self, subapp_client: TestClient) -> None:
        """The /calculate endpoint must appear in the OpenAPI schema."""
        response = subapp_client.get("/openapi.json")
        paths = response.json().get("paths", {})
        assert "/quotes/{quote_id}/calculate" in paths, (
            f"Missing /quotes/{{quote_id}}/calculate in OpenAPI. "
            f"Present: {sorted(paths.keys())}"
        )
        assert "post" in paths["/quotes/{quote_id}/calculate"]


class TestQuotesActionRoutes:
    """6B-6b: submit-procurement + cancel + workflow/transition."""

    _QUOTE_ID = "11111111-1111-1111-1111-111111111111"

    def test_post_submit_procurement_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /quotes/{quote_id}/submit-procurement must exist."""
        response = subapp_client.post(
            f"/quotes/{self._QUOTE_ID}/submit-procurement"
        )
        # No auth → 401. 404 would mean the route was not registered.
        assert response.status_code != 404, (
            "Route not registered: POST /quotes/{id}/submit-procurement "
            f"returned 404. Body: {response.text[:200]}"
        )

    def test_post_cancel_registered(self, subapp_client: TestClient) -> None:
        """POST /quotes/{quote_id}/cancel must exist."""
        response = subapp_client.post(f"/quotes/{self._QUOTE_ID}/cancel")
        assert response.status_code != 404, (
            "Route not registered: POST /quotes/{id}/cancel returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_post_workflow_transition_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /quotes/{quote_id}/workflow/transition must exist."""
        response = subapp_client.post(
            f"/quotes/{self._QUOTE_ID}/workflow/transition"
        )
        assert response.status_code != 404, (
            "Route not registered: POST /quotes/{id}/workflow/transition "
            f"returned 404. Body: {response.text[:200]}"
        )

    def test_schema_includes_6b6b_action_paths(
        self, subapp_client: TestClient
    ) -> None:
        """All 6B-6b quotes action endpoints must appear in the OpenAPI schema."""
        response = subapp_client.get("/openapi.json")
        paths = response.json().get("paths", {})
        expected = {
            "/quotes/{quote_id}/submit-procurement",
            "/quotes/{quote_id}/cancel",
            "/quotes/{quote_id}/workflow/transition",
        }
        missing = expected - set(paths.keys())
        assert not missing, (
            f"Missing 6B-6b action paths in OpenAPI: {missing}. "
            f"Present: {sorted(paths.keys())}"
        )
        for path in expected:
            assert "post" in paths[path], (
                f"Path {path} has no POST method entry"
            )


class TestQuotesOpenApiSchema:
    """Verify the quotes router endpoints appear in the OpenAPI schema."""

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

    def test_schema_includes_all_6b4_paths(
        self, subapp_client: TestClient
    ) -> None:
        """All 6B-4 quotes endpoints must appear in the OpenAPI schema."""
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema["paths"]

        expected = {
            "/quotes/kanban",
            "/quotes/{quote_id}/substatus",
            "/quotes/{quote_id}/status-history",
            "/quotes/{quote_id}/composition",
        }
        missing = expected - set(paths.keys())
        assert not missing, f"Missing OpenAPI paths: {missing}"

        assert "get" in paths["/quotes/kanban"]
        assert "post" in paths["/quotes/{quote_id}/substatus"]
        assert "get" in paths["/quotes/{quote_id}/status-history"]
        # /composition serves both GET and POST on the same path
        assert "get" in paths["/quotes/{quote_id}/composition"]
        assert "post" in paths["/quotes/{quote_id}/composition"]

    def test_schema_includes_6b5_soft_delete_paths(
        self, subapp_client: TestClient
    ) -> None:
        """Soft-delete + restore (6B-5) must appear in the OpenAPI schema."""
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema["paths"]

        expected = {
            "/quotes/{quote_id}/soft-delete",
            "/quotes/{quote_id}/restore",
        }
        missing = expected - set(paths.keys())
        assert not missing, f"Missing OpenAPI paths: {missing}"

        assert "post" in paths["/quotes/{quote_id}/soft-delete"]
        assert "post" in paths["/quotes/{quote_id}/restore"]


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


class TestQuotesMountIntegration:
    """Verify /api/quotes/* reaches the FastAPI sub-app via the outer mount."""

    _QUOTE_ID = "11111111-1111-1111-1111-111111111111"

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

    def test_get_kanban_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/quotes/kanban must resolve through the mount (not 404)."""
        response = outer_app_client.get("/api/quotes/kanban")
        assert response.status_code != 404, (
            f"Mount routing broken for GET /api/quotes/kanban. "
            f"Body: {response.text[:200]}"
        )

    def test_get_composition_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/quotes/{id}/composition must resolve through the mount."""
        response = outer_app_client.get(
            f"/api/quotes/{self._QUOTE_ID}/composition"
        )
        assert response.status_code != 404, (
            "Mount routing broken for GET /api/quotes/{id}/composition. "
            f"Body: {response.text[:200]}"
        )

    def test_soft_delete_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/quotes/{id}/soft-delete must resolve through the mount."""
        response = outer_app_client.post(
            f"/api/quotes/{self._QUOTE_ID}/soft-delete"
        )
        # No JWT → 401 from handler. 404 would mean the mount didn't route.
        assert response.status_code != 404, (
            "Mount routing broken for POST /api/quotes/{id}/soft-delete. "
            f"Body: {response.text[:200]}"
        )

    def test_restore_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/quotes/{id}/restore must resolve through the mount."""
        response = outer_app_client.post(
            f"/api/quotes/{self._QUOTE_ID}/restore"
        )
        assert response.status_code != 404, (
            "Mount routing broken for POST /api/quotes/{id}/restore. "
            f"Body: {response.text[:200]}"
        )

    def test_calculate_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/quotes/{id}/calculate must resolve through the mount.

        Pre-6B-6a this was served by a FastHTML ``@rt`` decorator directly
        on the outer app. After extraction the FastAPI sub-app at /api
        takes over — this test ensures the mount is correctly serving
        the new wrapper.
        """
        response = outer_app_client.post(
            f"/api/quotes/{self._QUOTE_ID}/calculate"
        )
        # No JWT → 401 from handler. 404 would mean the mount didn't route.
        assert response.status_code != 404, (
            "Mount routing broken for POST /api/quotes/{id}/calculate. "
            f"Body: {response.text[:200]}"
        )
