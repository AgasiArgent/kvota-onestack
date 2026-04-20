"""
Phase 5c Task 8 — API rename tests.

Verifies that the Phase 4a/5b "edit approval" flow has been renamed to
"procurement unlock" throughout the API surface:

- POST /api/invoices/{id}/procurement-unlock-request  (new)
- POST /api/invoices/{id}/procurement-unlock-approval/{aid}/approve  (new)
- POST /api/invoices/{id}/procurement-unlock-approval/{aid}/reject   (new)
- approval_type literal: "edit_sent_invoice" → "edit_completed_procurement"
- function: request_edit_approval → request_procurement_unlock

Old endpoint paths (/edit-request, /edit-approval/.../approve|reject,
/edit-request-approval) must be fully removed (no aliases).
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_uuid() -> str:
    return str(uuid4())


def _mock_api_user(user_id: str) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.email = "test@example.com"
    u.user_metadata = {"org_id": "org-x"}
    return u


def _mock_request(body: dict | None = None, api_user: MagicMock | None = None):
    request = MagicMock()
    if body is None:
        request.json = AsyncMock(side_effect=Exception("no body"))
    else:
        request.json = AsyncMock(return_value=body)
    request.state = MagicMock()
    request.state.api_user = api_user
    return request


def _chain_mock():
    m = MagicMock()
    m.select.return_value = m
    m.insert.return_value = m
    m.update.return_value = m
    m.eq.return_value = m
    m.in_.return_value = m
    m.order.return_value = m
    m.limit.return_value = m
    m.single.return_value = m
    m.is_.return_value = m
    return m


def _make_org_roles_mocks(sb, user_id, org_id, role_slugs):
    """Shared helper: mock organization_members + user_roles lookups."""
    org_mock = _chain_mock()
    org_mock.execute.return_value = MagicMock(
        data=[{"organization_id": org_id}]
    )

    roles_mock = _chain_mock()
    roles_mock.execute.return_value = MagicMock(
        data=[{"roles": {"slug": s}} for s in role_slugs]
    )

    return {"organization_members": org_mock, "user_roles": roles_mock}


# ============================================================================
# New endpoint: POST /api/invoices/{id}/procurement-unlock-request
# ============================================================================


class TestProcurementUnlockRequest:
    """Test the renamed request_procurement_unlock endpoint in api/invoices.py."""

    @pytest.mark.asyncio
    async def test_new_function_name_exists(self):
        """request_procurement_unlock function must exist in api/invoices."""
        from api.invoices import request_procurement_unlock

        assert callable(request_procurement_unlock)

    @pytest.mark.asyncio
    async def test_old_function_name_removed(self):
        """request_edit_approval must not exist anymore (fully renamed)."""
        from api import invoices as inv_mod

        assert not hasattr(inv_mod, "request_edit_approval"), (
            "request_edit_approval must be fully removed, not aliased"
        )

    @pytest.mark.asyncio
    async def test_creates_approval_with_new_type(self):
        """POST creates approval row with approval_type='edit_completed_procurement'."""
        user_id = make_uuid()
        org_id = "org-x"
        invoice_id = make_uuid()
        quote_id = make_uuid()
        api_user = _mock_api_user(user_id)

        mock_approval = MagicMock()
        mock_approval.id = make_uuid()

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])
            inv_mock = _chain_mock()
            inv_mock.execute.return_value = MagicMock(data=[{
                "id": invoice_id,
                "quote_id": quote_id,
                "invoice_number": "INV-01",
                "sent_at": "2026-04-10T10:00:00Z",
                "quotes": {"organization_id": org_id},
            }])
            tables["invoices"] = inv_mock
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with (
                patch(
                    "services.invoice_send_service.is_quote_procurement_locked",
                    return_value=True,
                ),
                patch(
                    "services.approval_service.create_approvals_for_role",
                    return_value=[mock_approval],
                ) as mock_create,
            ):
                from api.invoices import request_procurement_unlock

                request = _mock_request(
                    body={"reason": "Supplier changed prices after lock"},
                    api_user=api_user,
                )
                response = await request_procurement_unlock(request, invoice_id)

        assert response.status_code == 201
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["approval_type"] == "edit_completed_procurement"
        assert call_kwargs["approval_type"] != "edit_sent_invoice", (
            "Old approval_type literal must be replaced"
        )


# ============================================================================
# Route verification (paths only, via FastHTML/Starlette router)
# ============================================================================


class TestRoutePathsRenamed:
    """Verify main.py routing uses new paths and old paths are removed."""

    def test_new_unlock_request_route_registered(self):
        """/api/invoices/{id}/procurement-unlock-request must be reachable.

        Phase 6B-3: migrated from @rt in main.py to FastAPI sub-app router
        (api/routers/invoices.py). Route is no longer in main.app.routes
        directly; it resolves via the /api mount. Reachability check via
        TestClient confirms the route is wired end-to-end.
        """
        from starlette.testclient import TestClient
        import main

        client = TestClient(main.app)
        response = client.post(
            "/api/invoices/11111111-1111-1111-1111-111111111111"
            "/procurement-unlock-request",
            json={},
        )
        # Without auth, handler returns 401. 404 would mean the route is
        # not registered / not reachable through the mount.
        assert response.status_code != 404, (
            f"Route unreachable: POST /api/invoices/{{id}}/procurement-unlock-request "
            f"returned 404. Body: {response.text[:200]}"
        )

    def test_new_unlock_approve_route_registered(self):
        import main

        app = main.app
        paths = {getattr(r, "path", None) for r in app.routes}
        assert (
            "/api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/approve"
            in paths
        )

    def test_new_unlock_reject_route_registered(self):
        import main

        app = main.app
        paths = {getattr(r, "path", None) for r in app.routes}
        assert (
            "/api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/reject"
            in paths
        )

    def test_old_edit_request_approval_route_removed(self):
        """The Phase 4a /edit-request-approval path must not be routed anymore."""
        import main

        app = main.app
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/invoices/{invoice_id}/edit-request-approval" not in paths

    def test_old_edit_request_route_removed(self):
        """The Phase 5b /edit-request path must not be routed anymore."""
        import main

        app = main.app
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/invoices/{invoice_id}/edit-request" not in paths

    def test_old_edit_approval_approve_route_removed(self):
        import main

        app = main.app
        paths = {getattr(r, "path", None) for r in app.routes}
        assert (
            "/api/invoices/{invoice_id}/edit-approval/{approval_id}/approve"
            not in paths
        )

    def test_old_edit_approval_reject_route_removed(self):
        import main

        app = main.app
        paths = {getattr(r, "path", None) for r in app.routes}
        assert (
            "/api/invoices/{invoice_id}/edit-approval/{approval_id}/reject"
            not in paths
        )


# ============================================================================
# Approve / Reject handler renames in api/composition.py
# ============================================================================


class TestApproveRejectHandlersRenamed:
    """Verify composition.py approve/reject handlers have the new names."""

    def test_approve_function_renamed(self):
        """approve_invoice_edit → approve_procurement_unlock."""
        from api import composition

        assert hasattr(composition, "approve_procurement_unlock"), (
            "approve_procurement_unlock must exist"
        )
        assert not hasattr(composition, "approve_invoice_edit"), (
            "approve_invoice_edit must be fully renamed (no alias)"
        )

    def test_reject_function_renamed(self):
        """reject_invoice_edit → reject_procurement_unlock."""
        from api import composition

        assert hasattr(composition, "reject_procurement_unlock"), (
            "reject_procurement_unlock must exist"
        )
        assert not hasattr(composition, "reject_invoice_edit"), (
            "reject_invoice_edit must be fully renamed (no alias)"
        )


# ============================================================================
# Frontend URL update — mutations.ts references new path
# ============================================================================


class TestFrontendMutationsUsesNewPath:
    """Static check on frontend/src/entities/invoice/mutations.ts."""

    def test_mutation_uses_procurement_unlock_request_path(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(
            repo_root, "frontend", "src", "entities", "invoice", "mutations.ts"
        )
        with open(path, encoding="utf-8") as f:
            source = f.read()

        assert "procurement-unlock-request" in source, (
            "Frontend mutations.ts must use the new unlock path"
        )
        assert "edit-request-approval" not in source, (
            "Old edit-request-approval path must be removed from mutations.ts"
        )
