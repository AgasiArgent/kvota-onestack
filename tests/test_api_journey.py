"""Tests for the /api/journey/* scaffold (Task 9).

Covers:
- Router is mounted under /api/journey on the outer FastAPI app.
- Every endpoint returns the standard envelope `{success, data?, error?}`.
- Error envelope shape matches the spec (success=false + error.code/message).

The Wave 4 tasks (10, 11, 12, 13) will extend this with concrete endpoints;
this file locks in only the scaffold contracts (mount point + envelope).
"""

from __future__ import annotations

import os
import sys

import pytest
from starlette.testclient import TestClient

# Ensure project root importable for `api` and `services` modules.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import api_app  # noqa: E402


@pytest.fixture
def api_client() -> TestClient:
    """TestClient bound to the OUTER api_app — same surface Docker serves."""
    return TestClient(api_app)


class TestJourneyRouterMount:
    """The router must be mounted at /api/journey/* via the sub-app include."""

    def test_router_mounted_under_api_journey(self, api_client: TestClient) -> None:
        """GET /api/journey/ping must not 404 (i.e. the router is wired).

        A 404 here means the router was never mounted. Anything else (200, 500,
        422) proves the path is being routed to the journey module.
        """
        response = api_client.get("/api/journey/ping")

        assert response.status_code != 404, (
            "Route /api/journey/ping returned 404 — router not mounted in "
            "api/app.py. Expected any other status (200 for success)."
        )

    def test_openapi_includes_journey_paths(self, api_client: TestClient) -> None:
        """Sub-app OpenAPI schema must list at least one /journey/* path."""
        response = api_client.get("/api/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})
        journey_paths = [p for p in paths if p.startswith("/journey")]
        assert journey_paths, (
            f"No /journey/* paths in OpenAPI. Got: {list(paths)[:10]}"
        )


class TestJourneyEnvelopeShape:
    """Every journey endpoint must return the standard envelope (Req 16.4)."""

    def test_envelope_shape(self, api_client: TestClient) -> None:
        """Happy path: {success: true, data: ...} with no `error` key."""
        response = api_client.get("/api/journey/ping")

        assert response.status_code == 200
        body = response.json()
        assert body.get("success") is True, f"Expected success=true, got: {body}"
        assert "data" in body, f"Missing `data` key in envelope: {body}"
        # Error key must be absent (or explicitly null) on success envelopes.
        assert body.get("error") in (None, {}) or "error" not in body

    def test_envelope_error_shape(self, api_client: TestClient) -> None:
        """Error path: {success: false, error: {code, message}}.

        Hits a deliberately-failing stub endpoint so we can lock in the error
        envelope shape without depending on any real business logic.
        """
        response = api_client.get("/api/journey/_error-probe")

        # Any 4xx/5xx is acceptable — we only validate envelope shape.
        assert response.status_code >= 400, (
            f"Error probe should return >=400, got {response.status_code}"
        )
        body = response.json()
        assert body.get("success") is False, (
            f"Expected success=false on error envelope, got: {body}"
        )
        error = body.get("error")
        assert isinstance(error, dict), f"Expected error dict, got: {error!r}"
        assert isinstance(error.get("code"), str) and error["code"], (
            f"error.code must be a non-empty string, got: {error}"
        )
        assert isinstance(error.get("message"), str) and error["message"], (
            f"error.message must be a non-empty string, got: {error}"
        )
