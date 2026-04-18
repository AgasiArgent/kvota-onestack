"""
Tests for Phase 4a API endpoints:
- GET /api/geo/vat-rate — VAT rate lookup
- PUT /api/admin/vat-rates — Admin rate CRUD
- POST /api/invoices/{id}/download-xls — XLS download + send commit
- GET/POST /api/invoices/{id}/letter-draft — Draft CRUD
- POST /api/invoices/{id}/letter-draft/send — Commit send
- DELETE /api/invoices/{id}/letter-draft/{draft_id} — Delete draft
- GET /api/invoices/{id}/letter-drafts/history — Send history
- POST /api/invoices/{id}/edit-request-approval — Edit approval request
- Edit-after-send guard on existing mutating endpoints
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import pytest


def _uuid() -> str:
    return str(uuid4())


# ============================================================================
# Shared helpers
# ============================================================================


def _mock_api_user(user_id: str | None = None):
    """Create a mock Supabase GoTrue User object."""
    if user_id is None:
        return None
    user = MagicMock()
    user.id = user_id
    user.email = "test@example.com"
    user.user_metadata = {"org_id": _uuid()}
    return user


def _mock_request(
    method: str = "GET",
    query_params: dict | None = None,
    body: dict | None = None,
    api_user=None,
):
    """Create a mock Starlette Request."""
    request = MagicMock()
    request.method = method
    request.query_params = query_params or {}
    request.state = MagicMock()
    request.state.api_user = api_user
    if body is not None:
        request.json = AsyncMock(return_value=body)
    else:
        request.json = AsyncMock(side_effect=Exception("No body"))
    return request


def _chain_mock():
    """Create a chainable mock that returns itself on method calls."""
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.gte.return_value = mock
    mock.single.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.delete.return_value = mock
    mock.upsert.return_value = mock
    mock.limit.return_value = mock
    mock.in_.return_value = mock
    mock.is_.return_value = mock
    mock.not_.return_value = mock
    mock.order.return_value = mock
    return mock


def _make_org_roles_mocks(sb_mock, user_id: str, org_id: str, role_slugs: list[str]):
    """Set up the standard org_members + user_roles Supabase mock chain.

    Returns sb_mock.table side_effect callable.
    """
    tables = {}

    # organization_members
    om_mock = _chain_mock()
    om_mock.execute.return_value = MagicMock(data=[{"organization_id": org_id}])
    tables["organization_members"] = om_mock

    # user_roles
    ur_mock = _chain_mock()
    ur_mock.execute.return_value = MagicMock(
        data=[{"roles": {"slug": s}} for s in role_slugs]
    )
    tables["user_roles"] = ur_mock

    return tables


# ============================================================================
# GET /api/geo/vat-rate
# ============================================================================


class TestGetVatRate:
    @pytest.mark.asyncio
    async def test_returns_rate_for_known_country(self):
        user_id = _uuid()
        org_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.geo.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch("services.vat_service.get_vat_rate", return_value=Decimal("0.00")):
                from api.geo import get_vat_rate

                request = _mock_request(
                    query_params={"country_code": "KZ"},
                    api_user=api_user,
                )
                response = await get_vat_rate(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["success"] is True
        assert data["data"]["country_code"] == "KZ"
        assert data["data"]["rate"] == 0.00

    @pytest.mark.asyncio
    async def test_returns_default_for_unknown_country(self):
        user_id = _uuid()
        org_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.geo.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["sales"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            with patch("services.vat_service.get_vat_rate", return_value=Decimal("20.00")):
                from api.geo import get_vat_rate

                request = _mock_request(
                    query_params={"country_code": "XX"},
                    api_user=api_user,
                )
                response = await get_vat_rate(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["data"]["rate"] == 20.00

    @pytest.mark.asyncio
    async def test_returns_400_on_missing_country_code(self):
        user_id = _uuid()
        org_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.geo.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["sales"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.geo import get_vat_rate

            request = _mock_request(
                query_params={},
                api_user=api_user,
            )
            response = await get_vat_rate(request)

        assert response.status_code == 400
        data = json.loads(response.body)
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_country_code(self):
        user_id = _uuid()
        org_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.geo.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["sales"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.geo import get_vat_rate

            request = _mock_request(
                query_params={"country_code": "123"},
                api_user=api_user,
            )
            response = await get_vat_rate(request)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_401_when_unauthenticated(self):
        from api.geo import get_vat_rate

        request = _mock_request(
            query_params={"country_code": "CN"},
            api_user=None,
        )
        response = await get_vat_rate(request)

        assert response.status_code == 401
        data = json.loads(response.body)
        assert data["error"]["code"] == "UNAUTHORIZED"


# ============================================================================
# PUT /api/admin/vat-rates
# ============================================================================


class TestUpdateVatRate:
    @pytest.mark.asyncio
    async def test_admin_can_update_rate(self):
        user_id = _uuid()
        org_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.geo.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["admin"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            upserted_row = {"country_code": "CN", "rate": 15.0, "updated_at": "2026-04-11T10:00:00Z"}
            with patch("services.vat_service.upsert_rate", return_value=upserted_row):
                from api.geo import update_vat_rate

                request = _mock_request(
                    method="PUT",
                    body={"country_code": "CN", "rate": 15.0, "notes": "Reduced rate"},
                    api_user=api_user,
                )
                response = await update_vat_rate(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["success"] is True
        assert data["data"]["rate"] == 15.0

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self):
        user_id = _uuid()
        org_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.geo.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.geo import update_vat_rate

            request = _mock_request(
                method="PUT",
                body={"country_code": "CN", "rate": 15.0},
                api_user=api_user,
            )
            response = await update_vat_rate(request)

        assert response.status_code == 403
        data = json.loads(response.body)
        assert data["error"]["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_rate(self):
        user_id = _uuid()
        org_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.geo.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb

            tables = _make_org_roles_mocks(sb, user_id, org_id, ["admin"])
            sb.table.side_effect = lambda name: tables.get(name, _chain_mock())

            from api.geo import update_vat_rate

            request = _mock_request(
                method="PUT",
                body={"country_code": "CN", "rate": 150.0},
                api_user=api_user,
            )
            response = await update_vat_rate(request)

        assert response.status_code == 400


# ============================================================================
# POST /api/invoices/{id}/download-xls
# ============================================================================


class TestDownloadInvoiceXls:

    def _setup_invoice_mocks(self, sb, user_id, org_id, invoice_id, quote_id):
        """Set up org + roles + invoice ownership mocks."""
        tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])

        # invoices table for ownership check
        inv_mock = _chain_mock()
        inv_mock.execute.return_value = MagicMock(data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "invoice_number": "INV-01-Q-001",
            "sent_at": None,
            "quotes": {"organization_id": org_id},
        }])
        tables["invoices"] = inv_mock

        sb.table.side_effect = lambda name: tables.get(name, _chain_mock())
        return tables

    @pytest.mark.asyncio
    async def test_generates_xls_and_commits(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_invoice_mocks(sb, user_id, org_id, invoice_id, quote_id)

            xls_bytes = b"fake-xls-content"
            with patch("services.xls_export_service.generate_invoice_xls", return_value=xls_bytes) as mock_gen, \
                 patch("services.invoice_send_service.commit_invoice_send", return_value={"id": _uuid()}) as mock_commit:
                from api.invoices import download_invoice_xls

                request = _mock_request(
                    method="POST",
                    query_params={"language": "ru"},
                    api_user=api_user,
                )
                response = await download_invoice_xls(request, invoice_id)

        assert response.status_code == 200
        assert response.body == xls_bytes
        assert "Content-Disposition" in response.headers
        assert "KP-" in response.headers["Content-Disposition"]
        mock_gen.assert_called_once_with(invoice_id=invoice_id, language="ru")
        mock_commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_401_when_unauthenticated(self):
        from api.invoices import download_invoice_xls

        request = _mock_request(method="POST", api_user=None)
        response = await download_invoice_xls(request, _uuid())
        assert response.status_code == 401


# ============================================================================
# GET/POST /api/invoices/{id}/letter-draft
# ============================================================================


class TestLetterDraft:

    def _setup_mocks(self, sb, user_id, org_id, invoice_id, quote_id):
        tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])

        inv_mock = _chain_mock()
        inv_mock.execute.return_value = MagicMock(data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "invoice_number": "INV-01",
            "sent_at": None,
            "quotes": {"organization_id": org_id},
        }])
        tables["invoices"] = inv_mock
        sb.table.side_effect = lambda name: tables.get(name, _chain_mock())
        return tables

    @pytest.mark.asyncio
    async def test_get_draft_returns_draft(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        draft_data = {
            "id": _uuid(),
            "invoice_id": invoice_id,
            "recipient_email": "supplier@example.com",
            "subject": "Test",
            "body_text": "Hello",
        }

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id)

            with patch("services.invoice_send_service.get_active_draft", return_value=draft_data):
                from api.invoices import get_letter_draft

                request = _mock_request(api_user=api_user)
                response = await get_letter_draft(request, invoice_id)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["data"]["recipient_email"] == "supplier@example.com"

    @pytest.mark.asyncio
    async def test_get_draft_returns_200_with_null_when_no_draft(self):
        """Per API contract: missing draft returns 200 + data:null, not 404.

        Frontend distinguishes "no draft yet" (empty form) from auth/ownership
        failures by relying on a 200 response body — a 404 forces it down the
        generic error path instead.
        """
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id)

            with patch("services.invoice_send_service.get_active_draft", return_value=None):
                from api.invoices import get_letter_draft

                request = _mock_request(api_user=api_user)
                response = await get_letter_draft(request, invoice_id)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["success"] is True
        assert data["data"] is None

    @pytest.mark.asyncio
    async def test_save_draft_creates_draft(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        saved = {"id": _uuid(), "invoice_id": invoice_id, "subject": "Test Subject"}

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id)

            with patch("services.invoice_send_service.save_draft", return_value=saved) as mock_save:
                from api.invoices import save_letter_draft

                request = _mock_request(
                    method="POST",
                    body={
                        "recipient_email": "s@example.com",
                        "subject": "Test Subject",
                        "body_text": "Body",
                        "language": "ru",
                    },
                    api_user=api_user,
                )
                response = await save_letter_draft(request, invoice_id)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["data"]["subject"] == "Test Subject"
        mock_save.assert_called_once()


# ============================================================================
# POST /api/invoices/{id}/letter-draft/send
# ============================================================================


class TestSendLetterDraft:

    def _setup_mocks(self, sb, user_id, org_id, invoice_id, quote_id):
        tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])

        inv_mock = _chain_mock()
        inv_mock.execute.return_value = MagicMock(data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "invoice_number": "INV-01",
            "sent_at": None,
            "quotes": {"organization_id": org_id},
        }])
        tables["invoices"] = inv_mock

        # For the delete of old draft after commit
        drafts_mock = _chain_mock()
        drafts_mock.execute.return_value = MagicMock(data=[])
        tables["invoice_letter_drafts"] = drafts_mock

        sb.table.side_effect = lambda name: tables.get(name, _chain_mock())
        return tables

    @pytest.mark.asyncio
    async def test_commits_active_draft(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        draft_id = _uuid()
        api_user = _mock_api_user(user_id)

        active_draft = {
            "id": draft_id,
            "invoice_id": invoice_id,
            "language": "ru",
            "recipient_email": "s@test.com",
            "subject": "Subj",
            "body_text": "Body",
        }
        committed = {"id": _uuid(), "sent_at": "2026-04-11T10:00:00Z"}

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id)

            with patch("services.invoice_send_service.get_active_draft", return_value=active_draft), \
                 patch("services.invoice_send_service.commit_invoice_send", return_value=committed) as mock_commit:
                from api.invoices import send_letter_draft

                request = _mock_request(method="POST", api_user=api_user)
                response = await send_letter_draft(request, invoice_id)

        assert response.status_code == 200
        mock_commit.assert_called_once_with(
            invoice_id=invoice_id,
            user_id=user_id,
            method="letter_draft",
            language="ru",
            recipient_email="s@test.com",
            subject="Subj",
            body_text="Body",
        )

    @pytest.mark.asyncio
    async def test_returns_404_when_no_active_draft(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id)

            with patch("services.invoice_send_service.get_active_draft", return_value=None):
                from api.invoices import send_letter_draft

                request = _mock_request(method="POST", api_user=api_user)
                response = await send_letter_draft(request, invoice_id)

        assert response.status_code == 404


# ============================================================================
# POST /api/invoices/{id}/edit-request-approval
# ============================================================================


class TestEditRequestApproval:

    def _setup_mocks(self, sb, user_id, org_id, invoice_id, quote_id, sent=True):
        tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])

        inv_mock = _chain_mock()
        inv_mock.execute.return_value = MagicMock(data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "invoice_number": "INV-01",
            "sent_at": "2026-04-10T10:00:00Z" if sent else None,
            "quotes": {"organization_id": org_id},
        }])
        tables["invoices"] = inv_mock

        sb.table.side_effect = lambda name: tables.get(name, _chain_mock())
        return tables

    @pytest.mark.asyncio
    async def test_creates_approval_for_sent_invoice(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        mock_approval = MagicMock()
        mock_approval.id = _uuid()

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id, sent=True)

            with patch("services.invoice_send_service.is_quote_procurement_locked", return_value=True), \
                 patch("services.approval_service.create_approvals_for_role", return_value=[mock_approval]) as mock_create:
                from api.invoices import request_edit_approval

                request = _mock_request(
                    method="POST",
                    body={"reason": "Need to fix price"},
                    api_user=api_user,
                )
                response = await request_edit_approval(request, invoice_id)

        assert response.status_code == 201
        data = json.loads(response.body)
        assert data["data"]["approvals_created"] == 1
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["approval_type"] == "edit_sent_invoice"
        assert call_kwargs["quote_id"] == quote_id

    @pytest.mark.asyncio
    async def test_returns_400_when_invoice_not_sent(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id, sent=False)

            with patch("services.invoice_send_service.is_quote_procurement_locked", return_value=False):
                from api.invoices import request_edit_approval

                request = _mock_request(method="POST", api_user=api_user)
                response = await request_edit_approval(request, invoice_id)

        assert response.status_code == 400
        data = json.loads(response.body)
        assert data["error"]["code"] == "NOT_LOCKED"


# ============================================================================
# Edit-after-send guard
# ============================================================================


class TestEditAfterSendGuard:
    """Test that existing mutating invoice endpoints respect the sent guard."""

    @pytest.mark.asyncio
    async def test_update_invoice_returns_403_when_sent(self):
        """The PATCH /api/procurement/{quote_id}/invoices/update endpoint
        should return 403 EDIT_REQUIRES_APPROVAL when invoice is sent
        and user has no override role."""
        from services.invoice_send_service import check_edit_permission

        # check_edit_permission returns False for sent invoice + non-override roles
        with patch("services.invoice_send_service.is_quote_procurement_locked", return_value=True):
            result = check_edit_permission("any-id", ["procurement"])
        assert result is False

    @pytest.mark.asyncio
    async def test_update_invoice_allowed_for_admin_on_sent(self):
        """Admin should bypass the sent guard."""
        from services.invoice_send_service import check_edit_permission

        with patch("services.invoice_send_service.is_quote_procurement_locked", return_value=True):
            result = check_edit_permission("any-id", ["admin"])
        assert result is True

    @pytest.mark.asyncio
    async def test_update_invoice_allowed_when_unsent(self):
        """Unsent invoices should be editable by anyone with procurement role."""
        from services.invoice_send_service import check_edit_permission

        with patch("services.invoice_send_service.is_quote_procurement_locked", return_value=False):
            result = check_edit_permission("any-id", ["procurement"])
        assert result is True


# ============================================================================
# GET /api/invoices/{id}/letter-drafts/history
# ============================================================================


class TestSendHistory:

    def _setup_mocks(self, sb, user_id, org_id, invoice_id, quote_id):
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
        return tables

    @pytest.mark.asyncio
    async def test_returns_send_history(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        api_user = _mock_api_user(user_id)

        history = [
            {"id": _uuid(), "method": "xls_download", "sent_at": "2026-04-10T10:00:00Z"},
            {"id": _uuid(), "method": "letter_draft", "sent_at": "2026-04-11T10:00:00Z"},
        ]

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id)

            with patch("services.invoice_send_service.get_send_history", return_value=history):
                from api.invoices import get_send_history

                request = _mock_request(api_user=api_user)
                response = await get_send_history(request, invoice_id)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert len(data["data"]) == 2
        assert data["data"][0]["method"] == "xls_download"


# ============================================================================
# DELETE /api/invoices/{id}/letter-draft/{draft_id}
# ============================================================================


class TestDeleteLetterDraft:

    def _setup_mocks(self, sb, user_id, org_id, invoice_id, quote_id, draft_id, sent_at=None):
        tables = _make_org_roles_mocks(sb, user_id, org_id, ["procurement"])

        inv_mock = _chain_mock()
        inv_mock.execute.return_value = MagicMock(data=[{
            "id": invoice_id,
            "quote_id": quote_id,
            "invoice_number": "INV-01",
            "sent_at": None,
            "quotes": {"organization_id": org_id},
        }])
        tables["invoices"] = inv_mock

        # invoice_letter_drafts for the draft lookup and delete
        drafts_mock = _chain_mock()
        drafts_mock.execute.return_value = MagicMock(data=[{
            "id": draft_id,
            "invoice_id": invoice_id,
            "sent_at": sent_at,
        }])
        tables["invoice_letter_drafts"] = drafts_mock

        sb.table.side_effect = lambda name: tables.get(name, _chain_mock())
        return tables

    @pytest.mark.asyncio
    async def test_deletes_unsent_draft(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        draft_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(sb, user_id, org_id, invoice_id, quote_id, draft_id)

            from api.invoices import delete_letter_draft

            request = _mock_request(method="DELETE", api_user=api_user)
            response = await delete_letter_draft(request, invoice_id, draft_id)

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_rejects_delete_of_sent_draft(self):
        user_id = _uuid()
        org_id = _uuid()
        invoice_id = _uuid()
        quote_id = _uuid()
        draft_id = _uuid()
        api_user = _mock_api_user(user_id)

        with patch("api.invoices.get_supabase") as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            self._setup_mocks(
                sb, user_id, org_id, invoice_id, quote_id, draft_id,
                sent_at="2026-04-10T10:00:00Z",
            )

            from api.invoices import delete_letter_draft

            request = _mock_request(method="DELETE", api_user=api_user)
            response = await delete_letter_draft(request, invoice_id, draft_id)

        assert response.status_code == 400
        data = json.loads(response.body)
        assert data["error"]["code"] == "ALREADY_SENT"
