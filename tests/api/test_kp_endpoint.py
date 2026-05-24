"""Integration tests for ``POST /api/kp/render-pdf``.

Covers:
- 401 when no JWT (and no session) is attached to the request
- 400 when the JSON body is malformed
- 200 with ``Content-Type: application/pdf`` and the dated
  ``Content-Disposition`` filename when a valid body is posted
- 500 ``RENDER_ERROR`` with a request_id when the renderer raises

The renderer is a slow call, so for the happy path the test monkey-patches
``render_proposal_pdf_async`` to return a tiny stub body — the goal is to
exercise the handler wiring (auth, body parsing, response shape), not the
Playwright pipeline itself (the real renderer is covered by
``tests/services/test_kp_export_render.py``).
"""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.kp import render_pdf


def _make_request(
    *, api_user_id: str | None = "u-1", json_body: object = None, raw_body: bytes | None = None
) -> MagicMock:
    """Build a minimal Starlette-style request stub.

    - ``api_user_id=None`` → request.state.api_user is None (unauthenticated).
    - ``json_body`` → coroutine .json() returns this object.
    - ``raw_body`` → coroutine .json() raises ValueError (malformed JSON).
    """
    req = MagicMock()

    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        user_metadata = {"org_id": "org-42", "name": "Tester"}
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email="tester@example.com",
                user_metadata=user_metadata,
            )
        )

    if raw_body is not None:
        async def _bad_json() -> None:
            raise ValueError("malformed")
        req.json = _bad_json
    else:
        async def _good_json() -> object:
            return json_body if json_body is not None else {}
        req.json = _good_json

    req.headers = {}
    return req


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuth:
    def test_missing_jwt_returns_401_unauthorized(self) -> None:
        req = _make_request(api_user_id=None)
        resp = _run(render_pdf(req))
        assert resp.status_code == 401
        # Body is JSON envelope per .kiro/steering/api-first.md.
        body = bytes(resp.body)
        assert b"UNAUTHORIZED" in body
        assert b"success" in body
        assert b"false" in body


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestValidation:
    def test_malformed_json_returns_400_validation_error(self) -> None:
        req = _make_request(raw_body=b"{not-json")
        resp = _run(render_pdf(req))
        assert resp.status_code == 400
        assert b"VALIDATION_ERROR" in bytes(resp.body)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHappyPath:
    def test_valid_body_returns_200_pdf(self) -> None:
        fake_pdf = b"%PDF-1.4 fake-pdf-bytes\n%%EOF"
        with patch("api.kp.render_proposal_pdf_async", new=AsyncMock(return_value=fake_pdf)):
            req = _make_request(json_body={"supplier": "ACME"})
            resp = _run(render_pdf(req))

        assert resp.status_code == 200
        assert resp.media_type == "application/pdf"
        assert resp.body == fake_pdf

    def test_valid_body_attaches_dated_filename(self) -> None:
        fake_pdf = b"%PDF-1.4 fake"
        with patch("api.kp.render_proposal_pdf_async", new=AsyncMock(return_value=fake_pdf)):
            req = _make_request(json_body={"supplier": "ACME"})
            resp = _run(render_pdf(req))

        today = date.today().isoformat()
        cd = resp.headers["content-disposition"]
        assert cd == f'attachment; filename="kp-{today}.pdf"'

    def test_minimal_body_renders_proposal(self) -> None:
        fake_pdf = b"%PDF-1.4 ok"
        mock_render = AsyncMock(return_value=fake_pdf)
        with patch("api.kp.render_proposal_pdf_async", new=mock_render):
            req = _make_request(json_body={"supplier": "ACME"})
            resp = _run(render_pdf(req))

        assert resp.status_code == 200
        # Renderer was called with a KpProposal (defaults all over).
        assert mock_render.call_count == 1

    def test_empty_body_returns_400_validation_error(self) -> None:
        """An empty body would otherwise render a blank Master Bearing
        template — almost never what the caller meant. Reject with 400."""
        req = _make_request(json_body={})
        resp = _run(render_pdf(req))

        assert resp.status_code == 400
        body = bytes(resp.body)
        assert b"VALIDATION_ERROR" in body
        assert b"Empty request body" in body


# ---------------------------------------------------------------------------
# Render failure
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRenderFailure:
    def test_render_exception_returns_500_render_error(self) -> None:
        with patch(
            "api.kp.render_proposal_pdf_async",
            new=AsyncMock(side_effect=RuntimeError("chromium blew up")),
        ):
            req = _make_request(json_body={"supplier": "ACME"})
            resp = _run(render_pdf(req))

        assert resp.status_code == 500
        body = bytes(resp.body)
        assert b"RENDER_ERROR" in body
        # The internal exception message must NOT leak to the client.
        assert b"chromium blew up" not in body

    def test_render_error_response_includes_request_id(self) -> None:
        with patch(
            "api.kp.render_proposal_pdf_async",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            req = _make_request(json_body={"supplier": "X"})
            resp = _run(render_pdf(req))

        # request_id is surfaced to support log-correlation per REQ-19.3.
        body = bytes(resp.body)
        assert b"request_id" in body
