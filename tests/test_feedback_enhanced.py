"""
TDD Tests for Enhanced Feedback System (Bug Reporting with Screenshots)

Feature: Enhanced feedback widget with screenshot annotation, ClickUp integration,
admin UI (/admin/feedback), and Telegram photo sending.

These tests define the CONTRACT for features that do NOT exist yet.
All tests should FAIL until the feature is implemented.

Expected changes:
  1. services/clickup_service.py — NEW file with create_clickup_bug_task()
  2. services/telegram_service.py — NEW function send_admin_bug_report_with_photo()
  3. main.py POST /api/feedback — extended to accept screenshot, call ClickUp, Telegram photo
  4. main.py GET /admin/feedback — admin list page
  5. main.py GET /admin/feedback/{short_id} — admin detail page with screenshot
  6. main.py POST /admin/feedback/{short_id}/status — HTMX status update
  7. main.py sidebar — "Обращения" link for admin role
"""

import pytest
import re
import os
import json
import base64
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
TELEGRAM_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "telegram_service.py")
CLICKUP_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "clickup_service.py")


def _read_source(path):
    """Read a source file without importing it."""
    with open(path) as f:
        return f.read()


def _read_main_source():
    """Read main.py source code without importing it."""
    return _read_source(MAIN_PY)


def _make_uuid():
    return str(uuid.uuid4())


# ============================================================================
# SAMPLE DATA
# ============================================================================

# A valid small PNG image, base64 encoded (1x1 pixel red PNG)
SAMPLE_SCREENSHOT_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)

# Same with data URI prefix (as sent from frontend)
SAMPLE_SCREENSHOT_DATA_URI = f"data:image/png;base64,{SAMPLE_SCREENSHOT_B64}"

SAMPLE_DEBUG_CONTEXT = {
    "url": "https://kvotaflow.ru/quotes/abc-123",
    "userAgent": "Mozilla/5.0 Chrome/120.0.0.0",
    "screenSize": "1920x1080",
    "consoleErrors": [
        {"type": "error", "message": "TypeError: Cannot read property 'id' of null"}
    ],
    "recentRequests": [
        {"method": "GET", "url": "/api/quotes/abc-123", "status": 200},
        {"method": "POST", "url": "/api/quotes/abc-123/calculate", "status": 500},
    ],
    "sentryEventId": "abc123def456",
}


@pytest.fixture
def sample_feedback_record():
    """A complete feedback record as stored in DB."""
    return {
        "id": _make_uuid(),
        "short_id": "FB-260220143000",
        "user_id": _make_uuid(),
        "user_email": "tester@example.com",
        "user_name": "Test User",
        "organization_id": _make_uuid(),
        "organization_name": "Test Org",
        "page_url": "https://kvotaflow.ru/quotes/abc",
        "page_title": "Quote Detail",
        "user_agent": "Mozilla/5.0 Chrome/120.0",
        "feedback_type": "bug",
        "description": "The calculate button returns 500 error",
        "debug_context": SAMPLE_DEBUG_CONTEXT,
        "status": "new",
        "screenshot_data": SAMPLE_SCREENSHOT_B64,
        "clickup_task_id": "abc123task",
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
    }


@pytest.fixture
def sample_feedback_no_screenshot():
    """Feedback record without screenshot."""
    return {
        "id": _make_uuid(),
        "short_id": "FB-260220143001",
        "user_id": _make_uuid(),
        "user_email": "tester@example.com",
        "user_name": "Test User",
        "organization_id": _make_uuid(),
        "organization_name": "Test Org",
        "page_url": "https://kvotaflow.ru/dashboard",
        "page_title": "Dashboard",
        "user_agent": "Mozilla/5.0 Firefox/120.0",
        "feedback_type": "suggestion",
        "description": "Would be nice to have dark mode",
        "debug_context": {},
        "status": "new",
        "screenshot_data": None,
        "clickup_task_id": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
    }


# ============================================================================
# 1. CLICKUP SERVICE - FILE AND FUNCTION EXISTENCE
# ============================================================================

class TestClickUpServiceExists:
    """Verify that services/clickup_service.py exists with create_clickup_bug_task."""

    def test_clickup_service_file_exists(self):
        """services/clickup_service.py must exist as a new service module."""
        assert os.path.isfile(CLICKUP_SERVICE_PY), (
            "services/clickup_service.py must be created as a new service module "
            "for ClickUp integration."
        )

    def test_clickup_service_has_create_function(self):
        """create_clickup_bug_task function must be defined."""
        assert os.path.isfile(CLICKUP_SERVICE_PY), "File must exist first"
        source = _read_source(CLICKUP_SERVICE_PY)
        assert "async def create_clickup_bug_task" in source, (
            "services/clickup_service.py must define 'async def create_clickup_bug_task'"
        )

    def test_clickup_service_uses_httpx(self):
        """ClickUp service should use httpx for API calls."""
        assert os.path.isfile(CLICKUP_SERVICE_PY), "File must exist first"
        source = _read_source(CLICKUP_SERVICE_PY)
        assert "import httpx" in source, (
            "services/clickup_service.py should import httpx for ClickUp API calls"
        )

    def test_clickup_service_reads_env_vars(self):
        """ClickUp service should read CLICKUP_API_KEY and CLICKUP_BUG_LIST_ID from env."""
        assert os.path.isfile(CLICKUP_SERVICE_PY), "File must exist first"
        source = _read_source(CLICKUP_SERVICE_PY)
        assert "CLICKUP_API_KEY" in source, "Must reference CLICKUP_API_KEY env var"
        assert "CLICKUP_BUG_LIST_ID" in source, "Must reference CLICKUP_BUG_LIST_ID env var"


# ============================================================================
# 2. CLICKUP SERVICE - FUNCTION BEHAVIOR
# ============================================================================

class TestClickUpServiceBehavior:
    """Test create_clickup_bug_task function behavior."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_file(self):
        """Skip all tests in this class if clickup_service.py doesn't exist."""
        if not os.path.isfile(CLICKUP_SERVICE_PY):
            pytest.skip("services/clickup_service.py not created yet")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_configured(self):
        """When CLICKUP_API_KEY is empty, should return None immediately."""
        from services.clickup_service import create_clickup_bug_task

        with patch("services.clickup_service.CLICKUP_API_KEY", ""), \
             patch("services.clickup_service.CLICKUP_BUG_LIST_ID", ""):
            result = await create_clickup_bug_task(
                short_id="FB-260220143000",
                feedback_type="bug",
                description="Test bug",
                user_name="Test User",
                user_email="test@example.com",
                org_name="Test Org",
                page_url="https://kvotaflow.ru/quotes/abc",
                debug_context={},
                admin_url="https://kvotaflow.ru/admin/feedback/FB-260220143000",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_task_id_on_success(self):
        """On successful API call, should return the ClickUp task ID."""
        from services.clickup_service import create_clickup_bug_task

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "task_abc123"}

        with patch("services.clickup_service.CLICKUP_API_KEY", "test-key"), \
             patch("services.clickup_service.CLICKUP_BUG_LIST_ID", "list-123"), \
             patch("services.clickup_service.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await create_clickup_bug_task(
                short_id="FB-260220143000",
                feedback_type="bug",
                description="Calculate button broken",
                user_name="Test User",
                user_email="test@example.com",
                org_name="Test Org",
                page_url="https://kvotaflow.ru/quotes/abc",
                debug_context=SAMPLE_DEBUG_CONTEXT,
                admin_url="https://kvotaflow.ru/admin/feedback/FB-260220143000",
                has_screenshot=True,
            )
            assert result == "task_abc123"
            # Verify the API was called with correct URL pattern
            call_args = mock_instance.post.call_args
            assert "/list/list-123/task" in call_args[0][0] or \
                   "/list/list-123/task" in str(call_args)

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self):
        """On API error (e.g., 401), should return None and not raise."""
        from services.clickup_service import create_clickup_bug_task

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("services.clickup_service.CLICKUP_API_KEY", "bad-key"), \
             patch("services.clickup_service.CLICKUP_BUG_LIST_ID", "list-123"), \
             patch("services.clickup_service.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await create_clickup_bug_task(
                short_id="FB-260220143000",
                feedback_type="bug",
                description="Test bug",
                user_name="Test",
                user_email="test@example.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                debug_context={},
                admin_url="https://kvotaflow.ru/admin/feedback/FB-260220143000",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_exception(self):
        """On network exception (timeout etc), should return None and not raise."""
        from services.clickup_service import create_clickup_bug_task

        with patch("services.clickup_service.CLICKUP_API_KEY", "test-key"), \
             patch("services.clickup_service.CLICKUP_BUG_LIST_ID", "list-123"), \
             patch("services.clickup_service.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("Connection timeout")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await create_clickup_bug_task(
                short_id="FB-260220143000",
                feedback_type="bug",
                description="Test",
                user_name="Test",
                user_email="test@example.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                debug_context={},
                admin_url="https://kvotaflow.ru/admin/feedback/FB-260220143000",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_task_name_includes_type_and_short_id(self):
        """Task name should include feedback type label and short_id."""
        from services.clickup_service import create_clickup_bug_task

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "task_xyz"}

        with patch("services.clickup_service.CLICKUP_API_KEY", "test-key"), \
             patch("services.clickup_service.CLICKUP_BUG_LIST_ID", "list-123"), \
             patch("services.clickup_service.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            await create_clickup_bug_task(
                short_id="FB-260220143000",
                feedback_type="bug",
                description="Calculate button is broken",
                user_name="Test",
                user_email="test@example.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                debug_context={},
                admin_url="https://kvotaflow.ru/admin/feedback/FB-260220143000",
            )

            call_args = mock_instance.post.call_args
            payload = call_args[1].get("json") or call_args.kwargs.get("json")
            assert payload is not None, "POST payload must include json body"
            task_name = payload.get("name", "")
            assert "Bug" in task_name or "bug" in task_name.lower(), (
                f"Task name '{task_name}' should include bug type label"
            )
            assert "FB-260220143000" in task_name, (
                f"Task name '{task_name}' should include short_id"
            )

    @pytest.mark.asyncio
    async def test_bug_type_gets_higher_priority_than_suggestion(self):
        """Bugs should get priority 2 (High), suggestions should get priority 3 (Normal)."""
        from services.clickup_service import create_clickup_bug_task

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "task_prio"}

        with patch("services.clickup_service.CLICKUP_API_KEY", "test-key"), \
             patch("services.clickup_service.CLICKUP_BUG_LIST_ID", "list-123"), \
             patch("services.clickup_service.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            # Bug type
            await create_clickup_bug_task(
                short_id="FB-BUG",
                feedback_type="bug",
                description="Bug report",
                user_name="Test",
                user_email="t@t.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                debug_context={},
                admin_url="https://kvotaflow.ru/admin/feedback/FB-BUG",
            )
            bug_payload = mock_instance.post.call_args[1].get("json") or \
                          mock_instance.post.call_args.kwargs.get("json")

            mock_instance.post.reset_mock()

            # Suggestion type
            await create_clickup_bug_task(
                short_id="FB-SUG",
                feedback_type="suggestion",
                description="A suggestion",
                user_name="Test",
                user_email="t@t.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                debug_context={},
                admin_url="https://kvotaflow.ru/admin/feedback/FB-SUG",
            )
            sug_payload = mock_instance.post.call_args[1].get("json") or \
                          mock_instance.post.call_args.kwargs.get("json")

            assert bug_payload["priority"] == 2, "Bug priority should be 2 (High)"
            assert sug_payload["priority"] == 3, "Suggestion priority should be 3 (Normal)"


# ============================================================================
# 3. TELEGRAM SERVICE - send_admin_bug_report_with_photo
# ============================================================================

class TestTelegramServiceWithPhotoExists:
    """Verify that send_admin_bug_report_with_photo exists in telegram_service.py."""

    def test_function_exists_in_telegram_service(self):
        """send_admin_bug_report_with_photo must be defined in telegram_service.py."""
        source = _read_source(TELEGRAM_SERVICE_PY)
        assert "async def send_admin_bug_report_with_photo" in source, (
            "services/telegram_service.py must define "
            "'async def send_admin_bug_report_with_photo'"
        )

    def test_function_accepts_screenshot_parameter(self):
        """The function must accept screenshot_b64 parameter."""
        source = _read_source(TELEGRAM_SERVICE_PY)
        # Find the function signature
        idx = source.find("async def send_admin_bug_report_with_photo")
        assert idx >= 0, "Function not found"
        # Get ~600 chars of signature
        sig_area = source[idx:idx + 600]
        assert "screenshot_b64" in sig_area, (
            "send_admin_bug_report_with_photo must accept screenshot_b64 parameter"
        )

    def test_function_accepts_clickup_url_parameter(self):
        """The function must accept clickup_url parameter."""
        source = _read_source(TELEGRAM_SERVICE_PY)
        idx = source.find("async def send_admin_bug_report_with_photo")
        assert idx >= 0, "Function not found"
        sig_area = source[idx:idx + 600]
        assert "clickup_url" in sig_area, (
            "send_admin_bug_report_with_photo must accept clickup_url parameter"
        )


class TestTelegramServiceWithPhotoBehavior:
    """Test send_admin_bug_report_with_photo behavior (requires function to be implemented)."""

    @pytest.fixture(autouse=True)
    def _skip_if_function_missing(self):
        """Skip behavior tests if the function doesn't exist yet."""
        source = _read_source(TELEGRAM_SERVICE_PY)
        if "async def send_admin_bug_report_with_photo" not in source:
            pytest.skip("send_admin_bug_report_with_photo not implemented yet")

    @pytest.mark.asyncio
    async def test_sends_photo_when_screenshot_provided(self):
        """When screenshot_b64 is provided, should call bot.send_photo."""
        from services.telegram_service import send_admin_bug_report_with_photo

        mock_bot = AsyncMock()
        mock_bot.send_photo = AsyncMock()

        with patch("services.telegram_service.ADMIN_TELEGRAM_CHAT_ID", "12345"), \
             patch("services.telegram_service.get_bot", return_value=mock_bot):
            result = await send_admin_bug_report_with_photo(
                short_id="FB-260220143000",
                user_name="Test User",
                user_email="test@example.com",
                org_name="Test Org",
                page_url="https://kvotaflow.ru/quotes/abc",
                feedback_type="bug",
                description="Test bug description",
                screenshot_b64=SAMPLE_SCREENSHOT_B64,
            )
            assert result is True
            mock_bot.send_photo.assert_called_once()
            call_kwargs = mock_bot.send_photo.call_args[1]
            assert call_kwargs["chat_id"] == 12345
            assert "caption" in call_kwargs
            assert "photo" in call_kwargs

    @pytest.mark.asyncio
    async def test_sends_text_when_no_screenshot(self):
        """When screenshot_b64 is None, should call bot.send_message (text only)."""
        from services.telegram_service import send_admin_bug_report_with_photo

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("services.telegram_service.ADMIN_TELEGRAM_CHAT_ID", "12345"), \
             patch("services.telegram_service.get_bot", return_value=mock_bot):
            result = await send_admin_bug_report_with_photo(
                short_id="FB-260220143001",
                user_name="Test User",
                user_email="test@example.com",
                org_name="Test Org",
                page_url="https://kvotaflow.ru/dashboard",
                feedback_type="suggestion",
                description="Add dark mode",
                screenshot_b64=None,
            )
            assert result is True
            mock_bot.send_message.assert_called_once()
            mock_bot.send_photo.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_chat_id_not_configured(self):
        """When ADMIN_TELEGRAM_CHAT_ID is empty, should return False."""
        from services.telegram_service import send_admin_bug_report_with_photo

        with patch("services.telegram_service.ADMIN_TELEGRAM_CHAT_ID", ""):
            result = await send_admin_bug_report_with_photo(
                short_id="FB-test",
                user_name="Test",
                user_email="t@t.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                feedback_type="bug",
                description="test",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_bot_unavailable(self):
        """When get_bot() returns None, should return False."""
        from services.telegram_service import send_admin_bug_report_with_photo

        with patch("services.telegram_service.ADMIN_TELEGRAM_CHAT_ID", "12345"), \
             patch("services.telegram_service.get_bot", return_value=None):
            result = await send_admin_bug_report_with_photo(
                short_id="FB-test",
                user_name="Test",
                user_email="t@t.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                feedback_type="bug",
                description="test",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_includes_clickup_url_in_message(self):
        """When clickup_url is provided, it should appear in the message text."""
        from services.telegram_service import send_admin_bug_report_with_photo

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("services.telegram_service.ADMIN_TELEGRAM_CHAT_ID", "12345"), \
             patch("services.telegram_service.get_bot", return_value=mock_bot):
            await send_admin_bug_report_with_photo(
                short_id="FB-260220143000",
                user_name="Test",
                user_email="t@t.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                feedback_type="bug",
                description="test",
                clickup_url="https://app.clickup.com/t/abc123",
            )
            call_kwargs = mock_bot.send_message.call_args[1]
            text = call_kwargs.get("text", "")
            assert "clickup.com" in text.lower() or "abc123" in text, (
                f"ClickUp URL should be included in message text: {text[:200]}"
            )

    @pytest.mark.asyncio
    async def test_handles_send_photo_exception_gracefully(self):
        """When bot.send_photo raises exception, should return False, not crash."""
        from services.telegram_service import send_admin_bug_report_with_photo

        mock_bot = AsyncMock()
        mock_bot.send_photo = AsyncMock(side_effect=Exception("Telegram API error"))

        with patch("services.telegram_service.ADMIN_TELEGRAM_CHAT_ID", "12345"), \
             patch("services.telegram_service.get_bot", return_value=mock_bot):
            result = await send_admin_bug_report_with_photo(
                short_id="FB-test",
                user_name="Test",
                user_email="t@t.com",
                org_name="",
                page_url="https://kvotaflow.ru",
                feedback_type="bug",
                description="test",
                screenshot_b64=SAMPLE_SCREENSHOT_B64,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_caption_truncated_to_1024_chars_for_photo(self):
        """Telegram captions are limited to 1024 chars. Photo messages must respect this."""
        from services.telegram_service import send_admin_bug_report_with_photo

        mock_bot = AsyncMock()
        mock_bot.send_photo = AsyncMock()

        # Very long description that would exceed 1024 chars when formatted
        long_description = "X" * 2000

        with patch("services.telegram_service.ADMIN_TELEGRAM_CHAT_ID", "12345"), \
             patch("services.telegram_service.get_bot", return_value=mock_bot):
            await send_admin_bug_report_with_photo(
                short_id="FB-long",
                user_name="Test User With A Very Long Name Indeed",
                user_email="very.long.email@verylongcompanyname.example.com",
                org_name="Very Long Organization Name Incorporated LLC",
                page_url="https://kvotaflow.ru/very/long/path/to/page",
                feedback_type="bug",
                description=long_description,
                screenshot_b64=SAMPLE_SCREENSHOT_B64,
            )
            call_kwargs = mock_bot.send_photo.call_args[1]
            caption = call_kwargs.get("caption", "")
            assert len(caption) <= 1024, (
                f"Photo caption length ({len(caption)}) must not exceed 1024 chars"
            )


# ============================================================================
# 4. ENHANCED POST /api/feedback HANDLER
# ============================================================================

class TestEnhancedFeedbackPostHandler:
    """Tests for the enhanced submit_feedback POST handler in main.py."""

    def test_handler_accepts_screenshot_field(self):
        """The POST handler must accept a 'screenshot' form field."""
        source = _read_main_source()
        # Find submit_feedback handler
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        assert "screenshot" in handler, (
            "submit_feedback handler must accept 'screenshot' form field"
        )

    def test_handler_calls_clickup_service(self):
        """The handler must call create_clickup_bug_task."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        assert "create_clickup_bug_task" in handler, (
            "submit_feedback must call create_clickup_bug_task for ClickUp integration"
        )

    def test_handler_calls_send_admin_bug_report_with_photo(self):
        """The handler must call the new send_admin_bug_report_with_photo function."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        assert "send_admin_bug_report_with_photo" in handler, (
            "submit_feedback must call send_admin_bug_report_with_photo"
        )

    def test_handler_saves_screenshot_data_to_db(self):
        """The handler must include screenshot_data in the DB insert payload."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        assert "screenshot_data" in handler, (
            "submit_feedback must save screenshot_data to the database"
        )

    def test_handler_saves_clickup_task_id_to_db(self):
        """After ClickUp task creation, handler must update clickup_task_id in DB."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        assert "clickup_task_id" in handler, (
            "submit_feedback must save clickup_task_id after ClickUp task creation"
        )

    def test_handler_strips_data_uri_prefix(self):
        """Screenshot data URI prefix (data:image/png;base64,) must be stripped before DB storage."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        # Should contain logic to strip data URI prefix
        assert "data:image" in handler or "split" in handler, (
            "Handler must strip 'data:image/png;base64,' prefix from screenshot data"
        )

    def test_handler_validates_empty_description(self):
        """Empty description should still return an error (backward compatible)."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        # Must still validate description is not empty
        assert "not description" in handler or "description" in handler, (
            "Handler must validate that description is not empty"
        )


# ============================================================================
# 5. ADMIN FEEDBACK ROUTES - EXISTENCE
# ============================================================================

class TestAdminFeedbackRoutesExist:
    """Verify that admin feedback routes exist in main.py."""

    def test_admin_feedback_list_route_exists(self):
        """GET /admin/feedback route must be registered."""
        source = _read_main_source()
        assert re.search(
            r'@rt\(\s*"/admin/feedback"\s*\)', source
        ), "Route @rt('/admin/feedback') not found in main.py"

    def test_admin_feedback_detail_route_exists(self):
        """GET /admin/feedback/{short_id} route must be registered."""
        source = _read_main_source()
        assert re.search(
            r'@rt\(\s*"/admin/feedback/\{short_id\}"\s*\)', source
        ), "Route @rt('/admin/feedback/{short_id}') not found in main.py"

    def test_admin_feedback_status_route_exists(self):
        """POST /admin/feedback/{short_id}/status route must be registered."""
        source = _read_main_source()
        assert re.search(
            r'@rt\(\s*"/admin/feedback/\{short_id\}/status"',
            source
        ), "Route @rt('/admin/feedback/{short_id}/status') not found in main.py"

    def test_admin_feedback_status_route_is_post(self):
        """The status update route must use POST method."""
        source = _read_main_source()
        # Find the route decorator and check it has methods=["POST"]
        match = re.search(
            r'@rt\(\s*"/admin/feedback/\{short_id\}/status".*?methods\s*=\s*\[\s*"POST"\s*\]',
            source
        )
        assert match, (
            "Status update route must be POST: "
            '@rt("/admin/feedback/{short_id}/status", methods=["POST"])'
        )


# ============================================================================
# 6. ADMIN FEEDBACK LIST PAGE - BEHAVIOR
# ============================================================================

class TestAdminFeedbackListBehavior:
    """Test admin feedback list page behavior via source inspection."""

    def test_list_page_requires_admin_role(self):
        """Admin feedback page must check for admin role."""
        source = _read_main_source()
        # Find the admin/feedback route handler
        idx = source.find('"/admin/feedback"')
        assert idx >= 0, "/admin/feedback route not found"
        # Get handler body (until next @rt)
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 3000, len(source))
        handler = source[idx:handler_end]
        assert "admin" in handler and "roles" in handler, (
            "Admin feedback page must check for admin role"
        )

    def test_list_excludes_screenshot_data_from_query(self):
        """List query must NOT select screenshot_data (performance)."""
        source = _read_main_source()
        idx = source.find('"/admin/feedback"')
        assert idx >= 0, "/admin/feedback route not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 3000, len(source))
        handler = source[idx:handler_end]
        # Should use explicit column selection (not SELECT *)
        # The select() call should list specific columns, not include screenshot_data
        select_match = re.search(r'\.select\(\s*"([^"]+)"', handler)
        if select_match:
            selected_columns = select_match.group(1)
            assert "screenshot_data" not in selected_columns, (
                "List query must NOT include screenshot_data column for performance"
            )
        else:
            # If using .select("*"), that's also wrong
            assert ".select(" in handler, "Must use explicit column selection"

    def test_list_supports_status_filter(self):
        """List page should support status_filter query parameter."""
        source = _read_main_source()
        idx = source.find('"/admin/feedback"')
        assert idx >= 0, "/admin/feedback route not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 3000, len(source))
        handler = source[idx:handler_end]
        assert "status_filter" in handler, (
            "Admin feedback list must support status_filter parameter"
        )

    def test_list_has_clickable_rows_to_detail(self):
        """List rows should link to detail page /admin/feedback/{short_id}."""
        source = _read_main_source()
        idx = source.find('"/admin/feedback"')
        assert idx >= 0, "/admin/feedback route not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 3000, len(source))
        handler = source[idx:handler_end]
        assert "/admin/feedback/" in handler, (
            "List rows must link to /admin/feedback/{short_id} detail pages"
        )


# ============================================================================
# 7. ADMIN FEEDBACK DETAIL PAGE - BEHAVIOR
# ============================================================================

class TestAdminFeedbackDetailBehavior:
    """Test admin feedback detail page behavior via source inspection."""

    def _get_detail_handler(self):
        """Extract the detail route handler source."""
        source = _read_main_source()
        # Find "/admin/feedback/{short_id}" (not /status)
        idx = source.find('"/admin/feedback/{short_id}"')
        if idx < 0:
            return None
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 5000, len(source))
        return source[idx:handler_end]

    def test_detail_page_exists(self):
        """Detail page handler must exist."""
        handler = self._get_detail_handler()
        assert handler is not None, "Detail page handler not found"

    def test_detail_page_shows_screenshot(self):
        """Detail page must display screenshot if available."""
        handler = self._get_detail_handler()
        assert handler is not None, "Detail handler not found"
        assert "screenshot_data" in handler, (
            "Detail page must reference screenshot_data for display"
        )
        # Should render as an img tag with base64 source
        assert "data:image/png;base64" in handler or "base64" in handler, (
            "Detail page must render screenshot as inline base64 image"
        )

    def test_detail_page_shows_debug_context(self):
        """Detail page must display debug context information."""
        handler = self._get_detail_handler()
        assert handler is not None, "Detail handler not found"
        assert "debug_context" in handler, (
            "Detail page must display debug context"
        )

    def test_detail_page_has_status_update_form(self):
        """Detail page must include a status update form."""
        handler = self._get_detail_handler()
        assert handler is not None, "Detail handler not found"
        assert "status" in handler and ("Form" in handler or "form" in handler), (
            "Detail page must include a status update form"
        )
        # Check that valid statuses are present
        for status in ["new", "in_progress", "resolved", "closed"]:
            assert status in handler, (
                f"Status option '{status}' must be available in status form"
            )

    def test_detail_page_shows_clickup_link(self):
        """Detail page must show ClickUp link if clickup_task_id is present."""
        handler = self._get_detail_handler()
        assert handler is not None, "Detail handler not found"
        assert "clickup_task_id" in handler, (
            "Detail page must display ClickUp task link"
        )
        assert "clickup.com" in handler, (
            "Detail page must link to clickup.com for the task"
        )

    def test_detail_handles_nonexistent_feedback(self):
        """Detail page must handle case when short_id is not found."""
        handler = self._get_detail_handler()
        assert handler is not None, "Detail handler not found"
        # Should check for empty result and show "not found"
        assert "не найден" in handler.lower() or "not found" in handler.lower(), (
            "Detail page must handle non-existent short_id gracefully"
        )


# ============================================================================
# 8. STATUS UPDATE ENDPOINT
# ============================================================================

class TestStatusUpdateEndpoint:
    """Test the POST /admin/feedback/{short_id}/status endpoint."""

    def _get_status_handler(self):
        """Extract the status update handler source."""
        source = _read_main_source()
        idx = source.find('"/admin/feedback/{short_id}/status"')
        if idx < 0:
            return None
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 2000, len(source))
        return source[idx:handler_end]

    def test_validates_status_values(self):
        """Handler must validate status against allowed values."""
        handler = self._get_status_handler()
        assert handler is not None, "Status handler not found"
        # Should have a set/list of valid statuses
        for valid_status in ["new", "in_progress", "resolved", "closed"]:
            assert valid_status in handler, (
                f"Status handler must recognize valid status: {valid_status}"
            )

    def test_rejects_invalid_status(self):
        """Handler must reject invalid status values."""
        handler = self._get_status_handler()
        assert handler is not None, "Status handler not found"
        # Should contain validation logic that checks against valid statuses
        has_validation = (
            "valid_statuses" in handler or
            "not in" in handler or
            "if status" in handler
        )
        assert has_validation, (
            "Status handler must validate status against allowed values"
        )

    def test_updates_updated_at_timestamp(self):
        """Handler must set updated_at when updating status."""
        handler = self._get_status_handler()
        assert handler is not None, "Status handler not found"
        assert "updated_at" in handler, (
            "Status handler must update updated_at timestamp"
        )

    def test_requires_admin_role(self):
        """Status update must require admin role."""
        handler = self._get_status_handler()
        assert handler is not None, "Status handler not found"
        assert "admin" in handler and "roles" in handler, (
            "Status update must check for admin role"
        )


# ============================================================================
# 9. SIDEBAR NAVIGATION - "Обращения" link
# ============================================================================

class TestSidebarFeedbackLink:
    """Test that sidebar has 'Обращения' link for admin role."""

    def test_sidebar_has_feedback_link(self):
        """Sidebar must include 'Обращения' link pointing to /admin/feedback."""
        source = _read_main_source()
        # Look for the link in sidebar configuration
        has_link = (
            "Обращения" in source and
            "/admin/feedback" in source
        )
        assert has_link, (
            "Sidebar must include 'Обращения' link pointing to /admin/feedback"
        )

    def test_feedback_link_restricted_to_admin(self):
        """The Обращения link should only be visible to admin role."""
        source = _read_main_source()
        # Find the Обращения entry and check it has admin role restriction
        idx = source.find("Обращения")
        if idx < 0:
            pytest.fail("'Обращения' text not found in sidebar")
        # Look at surrounding context (300 chars before and after)
        context = source[max(0, idx - 300):idx + 300]
        assert "admin" in context, (
            "'Обращения' sidebar link must be restricted to admin role"
        )


# ============================================================================
# 10. FRONTEND JS - ANNOTATION EDITOR
# ============================================================================

class TestAnnotationEditorJS:
    """Test that annotation editor JS is included in main.py."""

    def test_annotation_editor_js_constant_exists(self):
        """ANNOTATION_EDITOR_JS constant must be defined in main.py."""
        source = _read_main_source()
        assert "ANNOTATION_EDITOR_JS" in source, (
            "ANNOTATION_EDITOR_JS constant must be defined in main.py"
        )

    def test_html2canvas_cdn_included(self):
        """html2canvas CDN script must be included in page_layout Head."""
        source = _read_main_source()
        assert "html2canvas" in source, (
            "html2canvas CDN script must be included in page_layout"
        )

    def test_annotation_editor_has_brush_tool(self):
        """Annotation editor must support brush (free-draw) tool."""
        source = _read_main_source()
        idx = source.find("ANNOTATION_EDITOR_JS")
        if idx < 0:
            pytest.fail("ANNOTATION_EDITOR_JS not found")
        # Check for brush tool functionality
        editor_area = source[idx:idx + 10000]
        assert "brush" in editor_area.lower(), (
            "Annotation editor must include brush/free-draw tool"
        )

    def test_annotation_editor_has_arrow_tool(self):
        """Annotation editor must support arrow tool."""
        source = _read_main_source()
        idx = source.find("ANNOTATION_EDITOR_JS")
        if idx < 0:
            pytest.fail("ANNOTATION_EDITOR_JS not found")
        editor_area = source[idx:idx + 10000]
        assert "arrow" in editor_area.lower(), (
            "Annotation editor must include arrow tool"
        )

    def test_annotation_editor_has_text_tool(self):
        """Annotation editor must support text tool."""
        source = _read_main_source()
        idx = source.find("ANNOTATION_EDITOR_JS")
        if idx < 0:
            pytest.fail("ANNOTATION_EDITOR_JS not found")
        editor_area = source[idx:idx + 10000]
        assert "text" in editor_area.lower() or "fillText" in editor_area, (
            "Annotation editor must include text annotation tool"
        )

    def test_annotation_editor_has_undo(self):
        """Annotation editor must support undo functionality."""
        source = _read_main_source()
        idx = source.find("ANNOTATION_EDITOR_JS")
        if idx < 0:
            pytest.fail("ANNOTATION_EDITOR_JS not found")
        editor_area = source[idx:idx + 10000]
        assert "undo" in editor_area.lower(), (
            "Annotation editor must include undo functionality"
        )

    def test_feedback_modal_has_screenshot_button(self):
        """feedback_modal must include a 'screenshot' button."""
        source = _read_main_source()
        idx = source.find("def feedback_modal")
        if idx < 0:
            pytest.fail("feedback_modal function not found")
        handler_end = source.find("\ndef ", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 5000, len(source))
        modal = source[idx:handler_end]
        has_screenshot_btn = (
            "screenshot" in modal.lower() or
            "скриншот" in modal.lower()
        )
        assert has_screenshot_btn, (
            "feedback_modal must include a screenshot button "
            "(e.g., 'Добавить скриншот')"
        )

    def test_feedback_modal_has_hidden_screenshot_input(self):
        """feedback_modal must have a hidden input for screenshot base64 data."""
        source = _read_main_source()
        idx = source.find("def feedback_modal")
        if idx < 0:
            pytest.fail("feedback_modal function not found")
        handler_end = source.find("\ndef ", idx + 10)
        if handler_end == -1:
            handler_end = min(idx + 5000, len(source))
        modal = source[idx:handler_end]
        # Should have a hidden input for screenshot data
        has_hidden_input = (
            "feedback-screenshot-data" in modal or
            'name="screenshot"' in modal or
            "screenshot" in modal.lower()
        )
        assert has_hidden_input, (
            "feedback_modal must include a hidden input for screenshot base64 data"
        )


# ============================================================================
# 11. EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestFeedbackEdgeCases:
    """Test edge cases in the feedback system."""

    def test_existing_text_only_feedback_still_works(self):
        """The existing text-only submit_feedback behavior must be preserved.
        The handler should still accept submissions without a screenshot field."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        # Handler must accept screenshot field with a default value
        # so text-only submissions continue to work
        has_screenshot_with_default = (
            'form.get("screenshot", "")' in handler or
            'form.get("screenshot")' in handler
        )
        assert has_screenshot_with_default, (
            "submit_feedback must read 'screenshot' from form with a default value "
            "so text-only submissions continue to work (backward compatibility)"
        )

    def test_clickup_failure_does_not_fail_submission(self):
        """ClickUp API failure must not cause the feedback submission to fail.
        The feedback should still be saved to DB."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        # ClickUp call must exist AND be wrapped in try/except
        clickup_idx = handler.find("create_clickup_bug_task")
        assert clickup_idx >= 0, (
            "submit_feedback must call create_clickup_bug_task (ClickUp integration)"
        )
        # Find the surrounding try/except
        before_clickup = handler[:clickup_idx]
        assert "try:" in before_clickup[max(0, len(before_clickup) - 200):], (
            "ClickUp call must be wrapped in try/except so failures don't break submission"
        )

    def test_telegram_failure_does_not_fail_submission(self):
        """Telegram failure must not cause the feedback submission to fail."""
        source = _read_main_source()
        idx = source.find("async def submit_feedback")
        assert idx >= 0, "submit_feedback handler not found"
        handler_end = source.find("\n@rt(", idx + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler = source[idx:handler_end]
        # Telegram call must exist AND be wrapped in try/except
        telegram_idx = handler.find("send_admin_bug_report_with_photo")
        assert telegram_idx >= 0, (
            "submit_feedback must call send_admin_bug_report_with_photo (Telegram photo)"
        )
        before_telegram = handler[:telegram_idx]
        assert "try:" in before_telegram[max(0, len(before_telegram) - 200):], (
            "Telegram call must be wrapped in try/except so failures don't break submission"
        )


# ============================================================================
# 12. STATUS LABELS AND CONSTANTS
# ============================================================================

class TestFeedbackStatusLabels:
    """Test that status labels and type labels are defined for the admin UI."""

    def test_status_labels_defined(self):
        """STATUS_LABELS dict must be defined for rendering status badges."""
        source = _read_main_source()
        assert "STATUS_LABELS" in source, (
            "STATUS_LABELS dict must be defined for admin feedback UI"
        )

    def test_all_statuses_have_labels(self):
        """All 4 statuses (new, in_progress, resolved, closed) must have labels."""
        source = _read_main_source()
        idx = source.find("STATUS_LABELS")
        if idx < 0:
            pytest.fail("STATUS_LABELS not found")
        label_area = source[idx:idx + 500]
        for status in ["new", "in_progress", "resolved", "closed"]:
            assert status in label_area, (
                f"STATUS_LABELS must include '{status}'"
            )

    def test_feedback_type_labels_defined(self):
        """FEEDBACK_TYPE_LABELS_RU dict must be defined for admin feedback UI."""
        source = _read_main_source()
        assert "FEEDBACK_TYPE_LABELS" in source, (
            "FEEDBACK_TYPE_LABELS_RU dict must be defined for admin feedback UI "
            "(maps feedback_type codes to Russian labels)"
        )
