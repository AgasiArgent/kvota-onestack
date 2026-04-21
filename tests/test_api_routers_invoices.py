"""Tests for /api/invoices/* endpoints on the FastAPI invoices router.

Covers (after Phase 6B-3 + 6B-4):
- Direct sub-app: 7 original (6B-3) routes + 3 new 6B-4 routes registered
  on api_app under /invoices/*.
- OpenAPI schema includes all 10 invoice endpoint paths.
- Integration via outer FastHTML app: /api/invoices/* resolves through the mount.
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


class TestInvoiceRoutesRegistered:
    """Assert the 7 invoice endpoints are wired to the FastAPI sub-app."""

    def test_post_download_xls_registered(self, subapp_client: TestClient) -> None:
        """POST /invoices/{invoice_id}/download-xls must exist (not 404)."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.post(f"/invoices/{invoice_id}/download-xls")
        # No auth → 401. 404 would mean the route was not registered.
        assert response.status_code != 404, (
            f"Route not registered: POST /invoices/{{id}}/download-xls "
            f"returned 404. Body: {response.text[:200]}"
        )

    def test_get_letter_draft_registered(self, subapp_client: TestClient) -> None:
        """GET /invoices/{invoice_id}/letter-draft must exist."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.get(f"/invoices/{invoice_id}/letter-draft")
        assert response.status_code != 404

    def test_post_letter_draft_registered(self, subapp_client: TestClient) -> None:
        """POST /invoices/{invoice_id}/letter-draft must exist."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.post(
            f"/invoices/{invoice_id}/letter-draft", json={}
        )
        assert response.status_code != 404

    def test_post_letter_draft_send_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /invoices/{invoice_id}/letter-draft/send must exist."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.post(
            f"/invoices/{invoice_id}/letter-draft/send", json={}
        )
        assert response.status_code != 404

    def test_delete_letter_draft_registered(
        self, subapp_client: TestClient
    ) -> None:
        """DELETE /invoices/{invoice_id}/letter-draft/{draft_id} must exist."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        draft_id = "22222222-2222-2222-2222-222222222222"
        response = subapp_client.delete(
            f"/invoices/{invoice_id}/letter-draft/{draft_id}"
        )
        assert response.status_code != 404

    def test_get_drafts_history_registered(
        self, subapp_client: TestClient
    ) -> None:
        """GET /invoices/{invoice_id}/letter-drafts/history must exist."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.get(
            f"/invoices/{invoice_id}/letter-drafts/history"
        )
        assert response.status_code != 404

    def test_post_procurement_unlock_request_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /invoices/{invoice_id}/procurement-unlock-request must exist."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.post(
            f"/invoices/{invoice_id}/procurement-unlock-request", json={}
        )
        assert response.status_code != 404

    # --- 6B-4 additions: verify + approve/reject procurement-unlock ---

    def test_post_verify_registered(self, subapp_client: TestClient) -> None:
        """POST /invoices/{invoice_id}/verify must exist (not 404)."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = subapp_client.post(f"/invoices/{invoice_id}/verify", json={})
        assert response.status_code != 404, (
            f"Route not registered: POST /invoices/{{id}}/verify returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_post_procurement_unlock_approve_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /invoices/{id}/procurement-unlock-approval/{approval_id}/approve."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        approval_id = "22222222-2222-2222-2222-222222222222"
        response = subapp_client.post(
            f"/invoices/{invoice_id}"
            f"/procurement-unlock-approval/{approval_id}/approve",
            json={},
        )
        assert response.status_code != 404

    def test_post_procurement_unlock_reject_registered(
        self, subapp_client: TestClient
    ) -> None:
        """POST /invoices/{id}/procurement-unlock-approval/{approval_id}/reject."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        approval_id = "22222222-2222-2222-2222-222222222222"
        response = subapp_client.post(
            f"/invoices/{invoice_id}"
            f"/procurement-unlock-approval/{approval_id}/reject",
            json={},
        )
        assert response.status_code != 404


class TestInvoiceOpenApiSchema:
    """Verify the invoice endpoints appear in the auto-generated OpenAPI schema."""

    def test_schema_includes_all_invoice_paths(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        expected_paths = {
            "/invoices/{invoice_id}/download-xls",
            "/invoices/{invoice_id}/letter-draft",
            "/invoices/{invoice_id}/letter-draft/send",
            "/invoices/{invoice_id}/letter-draft/{draft_id}",
            "/invoices/{invoice_id}/letter-drafts/history",
            "/invoices/{invoice_id}/procurement-unlock-request",
            # 6B-4 additions
            "/invoices/{invoice_id}/verify",
            "/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/approve",
            "/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/reject",
        }
        assert expected_paths.issubset(set(paths.keys())), (
            f"Missing invoice paths in OpenAPI: "
            f"{expected_paths - set(paths.keys())}"
        )

    def test_schema_declares_correct_methods(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        schema = response.json()
        paths = schema["paths"]

        assert "post" in paths["/invoices/{invoice_id}/download-xls"]
        assert "get" in paths["/invoices/{invoice_id}/letter-draft"]
        assert "post" in paths["/invoices/{invoice_id}/letter-draft"]
        assert "post" in paths["/invoices/{invoice_id}/letter-draft/send"]
        assert "delete" in paths["/invoices/{invoice_id}/letter-draft/{draft_id}"]
        assert "get" in paths["/invoices/{invoice_id}/letter-drafts/history"]
        assert "post" in paths["/invoices/{invoice_id}/procurement-unlock-request"]
        # 6B-4
        assert "post" in paths["/invoices/{invoice_id}/verify"]
        assert "post" in paths[
            "/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/approve"
        ]
        assert "post" in paths[
            "/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/reject"
        ]


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


class TestInvoiceMountIntegration:
    """Verify /api/invoices/* reaches the FastAPI sub-app via the outer mount."""

    def test_post_download_xls_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/invoices/{id}/download-xls must resolve through the mount."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = outer_app_client.post(
            f"/api/invoices/{invoice_id}/download-xls"
        )
        # No JWT → ApiAuthMiddleware / handler returns 401. 404 would mean the
        # mount didn't route to the invoices router.
        assert response.status_code != 404, (
            f"Mount routing broken for POST /api/invoices/{{id}}/download-xls. "
            f"Body: {response.text[:200]}"
        )

    def test_delete_letter_draft_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """DELETE /api/invoices/{id}/letter-draft/{draft_id} must resolve through mount."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        draft_id = "22222222-2222-2222-2222-222222222222"
        response = outer_app_client.delete(
            f"/api/invoices/{invoice_id}/letter-draft/{draft_id}"
        )
        assert response.status_code != 404

    def test_get_drafts_history_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """GET /api/invoices/{id}/letter-drafts/history must resolve through mount."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = outer_app_client.get(
            f"/api/invoices/{invoice_id}/letter-drafts/history"
        )
        assert response.status_code != 404

    def test_post_verify_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST /api/invoices/{id}/verify must resolve through the mount."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        response = outer_app_client.post(
            f"/api/invoices/{invoice_id}/verify", json={}
        )
        assert response.status_code != 404, (
            f"Mount routing broken for POST /api/invoices/{{id}}/verify. "
            f"Body: {response.text[:200]}"
        )

    def test_post_procurement_unlock_approve_reachable_through_mount(
        self, outer_app_client: TestClient
    ) -> None:
        """POST .../procurement-unlock-approval/{id}/approve must resolve through mount."""
        invoice_id = "11111111-1111-1111-1111-111111111111"
        approval_id = "22222222-2222-2222-2222-222222222222"
        response = outer_app_client.post(
            f"/api/invoices/{invoice_id}"
            f"/procurement-unlock-approval/{approval_id}/approve",
            json={},
        )
        assert response.status_code != 404
