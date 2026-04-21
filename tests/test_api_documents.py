"""Tests for api/documents.py — Phase 6B-9 extraction of
/api/documents/{document_id}/download (GET, 302) and
/api/documents/{document_id} (DELETE).

Covers each handler in isolation (direct call) plus route registration on
the FastAPI sub-app. Supabase / storage side effects are mocked — we only
verify the handler's request/response envelope and auth/role branches.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_sub_app  # noqa: E402
from api.documents import (  # noqa: E402
    delete_document_api,
    download_document,
)


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    user_metadata: dict | None = None,
    session_user: dict | None = None,
):
    """Build a minimal Starlette-style request with optional JWT + session.

    When ``api_user_id`` is a string, JWT auth is populated; session raises.
    When ``session_user`` is a dict, SessionMiddleware-style session is used.
    When both are None, auth fails (no JWT, no session).
    """
    req = MagicMock()
    if api_user_id is not None:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email="u@x.com",
                user_metadata=user_metadata or {},
            )
        )
    else:
        req.state = SimpleNamespace(api_user=None)

    if session_user is not None:
        session = {"user": session_user}
        type(req).session = property(lambda self: session)
    else:
        # Mimic Starlette: session raises AssertionError when SessionMiddleware absent.
        type(req).session = property(
            lambda self: (_ for _ in ()).throw(AssertionError("no session"))
        )
    req.headers = {}
    return req


def _run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


# ----------------------------------------------------------------------------
# Handler unit tests
# ----------------------------------------------------------------------------


class TestDownloadDocument:
    """GET /api/documents/{document_id}/download handler behaviour."""

    def test_unauthenticated_redirects_to_login(self):
        """No JWT + no session → 303 redirect to /login (legacy behaviour)."""
        req = _make_request(api_user_id=None)
        resp = _run(download_document(req, "doc-1"))
        # RedirectResponse has status_code attribute
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    @patch("api.documents.get_user_role_codes")
    @patch("api.documents.get_download_url")
    def test_missing_document_returns_404(self, mock_get_url, mock_roles):
        """JWT user + unknown document → 404 JSON."""
        mock_roles.return_value = []
        mock_get_url.return_value = None
        req = _make_request(api_user_id="user-1", user_metadata={"org_id": "o-1"})
        resp = _run(download_document(req, "doc-missing"))
        assert resp.status_code == 404
        assert _body(resp) == {
            "success": False,
            "error": "Document not found",
        }

    @patch("api.documents.get_user_role_codes")
    @patch("api.documents.get_download_url")
    def test_happy_path_returns_302(self, mock_get_url, mock_roles):
        """Valid JWT + document found → 302 RedirectResponse to signed URL."""
        mock_roles.return_value = []
        mock_get_url.return_value = "https://storage.example/signed?token=x"
        req = _make_request(api_user_id="user-1", user_metadata={"org_id": "o-1"})
        resp = _run(download_document(req, "doc-1"))
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://storage.example/signed?token=x"
        mock_get_url.assert_called_once_with(
            "doc-1", expires_in=3600, force_download=True
        )


class TestDeleteDocument:
    """DELETE /api/documents/{document_id} handler behaviour."""

    def test_unauthenticated_returns_401(self):
        """No JWT + no session → 401 with success=False envelope."""
        req = _make_request(api_user_id=None)
        resp = _run(delete_document_api(req, "doc-1"))
        assert resp.status_code == 401
        assert _body(resp) == {"success": False, "error": "Unauthorized"}

    @patch("api.documents.get_user_role_codes")
    def test_missing_role_returns_403(self, mock_roles):
        """Authenticated but not in procurement/admin set → 403 Forbidden."""
        mock_roles.return_value = ["sales"]  # Not in allowlist
        req = _make_request(api_user_id="user-1", user_metadata={"org_id": "o-1"})
        resp = _run(delete_document_api(req, "doc-1"))
        assert resp.status_code == 403
        assert _body(resp) == {"success": False, "error": "Forbidden"}

    @patch("api.documents.delete_document")
    @patch("api.documents.get_user_role_codes")
    def test_happy_path_returns_success(self, mock_roles, mock_delete):
        """Admin + delete succeeds → 200 with success=True."""
        mock_roles.return_value = ["admin"]
        mock_delete.return_value = (True, None)
        req = _make_request(api_user_id="user-1", user_metadata={"org_id": "o-1"})
        resp = _run(delete_document_api(req, "doc-1"))
        assert resp.status_code == 200
        assert _body(resp) == {"success": True}
        mock_delete.assert_called_once_with("doc-1")

    @patch("api.documents.delete_document")
    @patch("api.documents.get_user_role_codes")
    def test_delete_failure_returns_500(self, mock_roles, mock_delete):
        """Procurement user + delete error → 500 with error detail."""
        mock_roles.return_value = ["procurement"]
        mock_delete.return_value = (False, "Storage error")
        req = _make_request(api_user_id="user-1", user_metadata={"org_id": "o-1"})
        resp = _run(delete_document_api(req, "doc-1"))
        assert resp.status_code == 500
        assert _body(resp) == {
            "success": False,
            "error": "Storage error",
        }

    @patch("api.documents.delete_document")
    def test_session_auth_with_admin_role(self, mock_delete):
        """Legacy session with admin role → delete succeeds."""
        mock_delete.return_value = (True, None)
        req = _make_request(
            api_user_id=None,
            session_user={
                "id": "user-1",
                "org_id": "o-1",
                "roles": ["admin"],
            },
        )
        resp = _run(delete_document_api(req, "doc-1"))
        assert resp.status_code == 200
        assert _body(resp) == {"success": True}


# ----------------------------------------------------------------------------
# Route registration (sub-app)
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    """TestClient wired directly to the FastAPI sub-app (no /api prefix)."""
    return TestClient(api_sub_app)


class TestDocumentRoutesRegistered:
    """Assert the documents endpoints are wired on the FastAPI sub-app."""

    def test_get_download_registered(self, subapp_client: TestClient) -> None:
        """GET /documents/{document_id}/download must exist (not 404)."""
        response = subapp_client.get(
            "/documents/doc-1/download", follow_redirects=False
        )
        # No auth attached → 303 redirect to /login. 404 means route missing.
        assert response.status_code != 404, (
            f"Route not registered: GET /documents/.../download returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_delete_document_registered(self, subapp_client: TestClient) -> None:
        """DELETE /documents/{document_id} must exist (not 404)."""
        response = subapp_client.delete("/documents/doc-1")
        assert response.status_code != 404, (
            f"Route not registered: DELETE /documents/... returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_openapi_schema_includes_download(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/documents/{document_id}/download" in paths
        assert "get" in paths["/documents/{document_id}/download"]

    def test_openapi_schema_includes_delete(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/documents/{document_id}" in paths
        assert "delete" in paths["/documents/{document_id}"]
