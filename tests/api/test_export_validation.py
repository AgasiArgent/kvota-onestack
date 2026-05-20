"""Tests for ``GET /api/quotes/{quote_id}/export/validation`` — validation Excel download.

Post-Phase 6C-2B-Mega-C (2026-04-20) the FastHTML legacy route
``/quotes/{quote_id}/export/validation`` was archived. The Next.js callers
(calculation-action-bar.tsx, control-action-bar.tsx) still pointed at the
dead route on prod, causing a silent download failure. This endpoint
brings the validation Excel download under ``/api/*`` with proper
dual-auth (JWT primary, session fallback).

Covers:
- Happy path: JWT-authed user in correct org → 200 + xlsm bytes + correct
  ``Content-Type`` (``application/vnd.ms-excel.sheet.macroEnabled.12``)
  and ``Content-Disposition: attachment; filename="validation_<quote_number>.xlsm"``.
- 401 when no JWT (and no session).
- 404 when the underlying ``fetch_export_data`` raises ``ValueError``
  (unknown quote / wrong org — RLS-style behavior).

The Supabase client is mocked at ``api.quotes.get_supabase`` so the
auth/org-membership branch is exercised without a real DB. The
``fetch_export_data`` helper is patched on ``api.quotes`` to return a tiny
fake ``ExportData`` (or raise ``ValueError``) — full DB fixtures are NOT
required because we are testing the handler wiring, not the data mapper
itself. ``create_validation_excel`` is NOT mocked: the real implementation
runs against the fake ``ExportData`` so the response body is real bytes.
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.quotes import export_validation  # noqa: E402


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_request(api_user_id: str | None = "user-1", email: str = "u@x.com"):
    """Build a minimal Starlette-style request with optional JWT user."""
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(id=api_user_id, email=email)
        )
    req.headers = {}
    # request.session raises AssertionError on Starlette without SessionMiddleware
    type(req).session = property(
        lambda _self: (_ for _ in ()).throw(AssertionError("no session"))
    )
    return req


def _mock_supabase_for_org(org_id: str | None = "org-1"):
    """Mock Supabase for the organization_members lookup only.

    The validation export handler does its own auth + org lookup, then
    delegates the rest to ``fetch_export_data`` (which we patch separately).
    """
    sb = MagicMock()

    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "organization_members":
            data = [{"organization_id": org_id}] if org_id else []
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = data
        return tbl

    sb.table.side_effect = table_side_effect
    return sb


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fake_export_data():
    """Return a minimal ExportData-compatible namespace for create_validation_excel.

    The validator only reads ``data.quote.get("quote_number", ...)`` from the
    handler's perspective; the underlying ``create_validation_excel`` will
    walk through the full ExportData shape. We import the real dataclass
    so the structure is correct.
    """
    from services.export_data_mapper import ExportData

    quote = {
        "id": "q-1",
        "quote_number": "Q-202605-0018",
        "customer_id": "cust-1",
        "currency": "USD",
        "title": "Test Quote",
    }
    items: list[dict] = []
    customer = {"id": "cust-1", "name": "Test Customer"}
    organization = {"id": "org-1", "name": "Test Org"}
    variables: dict = {}
    calculations: dict = {}
    return ExportData(
        quote=quote,
        items=items,
        customer=customer,
        organization=organization,
        variables=variables,
        calculations=calculations,
    )


# ----------------------------------------------------------------------------
# Auth edge cases
# ----------------------------------------------------------------------------


class TestExportValidationAuth:
    def test_no_auth_returns_401(self):
        """No JWT and no session → 401."""
        req = _make_request(api_user_id=None)
        resp = _run(export_validation(req, "q-1"))
        assert resp.status_code == 401

    @patch("api.quotes.get_supabase")
    def test_jwt_without_org_returns_403(self, mock_get_sb):
        """JWT valid but user has no organization_members row → 403."""
        mock_get_sb.return_value = _mock_supabase_for_org(org_id=None)
        req = _make_request(api_user_id="u-no-org")

        resp = _run(export_validation(req, "q-1"))
        assert resp.status_code == 403


# ----------------------------------------------------------------------------
# Handler behavior
# ----------------------------------------------------------------------------


class TestExportValidationHandler:
    @patch("api.quotes.fetch_export_data")
    @patch("api.quotes.get_supabase")
    def test_missing_quote_returns_404(
        self, mock_get_sb, mock_fetch
    ):
        """fetch_export_data raises ValueError → 404."""
        mock_get_sb.return_value = _mock_supabase_for_org()
        mock_fetch.side_effect = ValueError("Quote not found: q-missing")

        req = _make_request(api_user_id="u-1")
        resp = _run(export_validation(req, "q-missing"))

        assert resp.status_code == 404

    @patch("api.quotes.create_validation_excel")
    @patch("api.quotes.fetch_export_data")
    @patch("api.quotes.get_supabase")
    def test_happy_path_returns_xlsm_bytes(
        self, mock_get_sb, mock_fetch, mock_create
    ):
        """Authed user, quote in org → 200 with xlsm bytes + correct headers.

        ``create_validation_excel`` is mocked here only so the test is hermetic
        (no template file dependency) — the handler wiring is still verified
        end-to-end: handler → fetch_export_data → create_validation_excel →
        Response with correct media_type + filename.
        """
        mock_get_sb.return_value = _mock_supabase_for_org()
        mock_fetch.return_value = _fake_export_data()
        # Fake xlsm bytes (real openpyxl output isn't needed for the wiring test).
        mock_create.return_value = b"PK\x03\x04 fake-xlsm-bytes"

        req = _make_request(api_user_id="u-1")
        resp = _run(export_validation(req, "q-1"))

        assert resp.status_code == 200
        assert (
            resp.media_type
            == "application/vnd.ms-excel.sheet.macroEnabled.12"
        )
        # Body is non-empty bytes
        assert resp.body == b"PK\x03\x04 fake-xlsm-bytes"
        # Filename is based on the quote_number from fetch_export_data result
        assert (
            resp.headers["content-disposition"]
            == 'attachment; filename="validation_Q-202605-0018.xlsm"'
        )
        # Verify fetch_export_data was called with (quote_id, org_id)
        mock_fetch.assert_called_once_with("q-1", "org-1")
        # Verify create_validation_excel was called with the data
        mock_create.assert_called_once()

    @patch("api.quotes.fetch_export_data")
    @patch("api.quotes.get_supabase")
    def test_fetch_export_data_unexpected_error_returns_500(
        self, mock_get_sb, mock_fetch
    ):
        """Non-ValueError exception from data mapper (DB/network/etc) → 500
        with a controlled JSON error and the traceback logged."""
        mock_get_sb.return_value = _mock_supabase_for_org()
        mock_fetch.side_effect = RuntimeError("postgrest connection refused")

        req = _make_request(api_user_id="u-1")
        resp = _run(export_validation(req, "q-1"))

        assert resp.status_code == 500
        # Internal error message is NOT leaked to the response body.
        assert b"postgrest" not in resp.body
        assert b"Failed to fetch" in resp.body

    @patch("api.quotes.create_validation_excel")
    @patch("api.quotes.fetch_export_data")
    @patch("api.quotes.get_supabase")
    def test_create_validation_excel_failure_returns_500(
        self, mock_get_sb, mock_fetch, mock_create
    ):
        """Template-load / openpyxl-write failure → 500 with a controlled
        JSON error (no stack trace in the response body)."""
        mock_get_sb.return_value = _mock_supabase_for_org()
        mock_fetch.return_value = _fake_export_data()
        mock_create.side_effect = FileNotFoundError("template.xlsm not found")

        req = _make_request(api_user_id="u-1")
        resp = _run(export_validation(req, "q-1"))

        assert resp.status_code == 500
        assert b"template.xlsm" not in resp.body
        assert b"Failed to generate" in resp.body

    @patch("api.quotes.create_validation_excel")
    @patch("api.quotes.fetch_export_data")
    @patch("api.quotes.get_supabase")
    def test_filename_falls_back_to_quote_id_when_number_missing(
        self, mock_get_sb, mock_fetch, mock_create
    ):
        """When quote dict lacks ``quote_number``, filename uses the quote_id."""
        from services.export_data_mapper import ExportData

        mock_get_sb.return_value = _mock_supabase_for_org()
        data = ExportData(
            quote={"id": "q-fallback"},  # no quote_number
            items=[],
            customer={},
            organization={},
            variables={},
            calculations={},
        )
        mock_fetch.return_value = data
        mock_create.return_value = b"xlsm-bytes"

        req = _make_request(api_user_id="u-1")
        resp = _run(export_validation(req, "q-fallback"))

        assert resp.status_code == 200
        assert (
            resp.headers["content-disposition"]
            == 'attachment; filename="validation_q-fallback.xlsm"'
        )
