"""
Tests for Telegram notification when procurement completes an invoice.

TDD: Tests written FIRST before implementation.
Feature: Send Telegram notification to sales user (quote creator)
         when procurement completes an invoice.

Test Scenarios:
1. send_procurement_invoice_complete_notification exists and is callable
2. PROCUREMENT_INVOICE_COMPLETE exists in NotificationType enum
3. Partial completion: message contains invoice number + progress counter + "оценено"
4. All done case: message contains "Закупка полностью завершена"
5. Unavailable items shown when count > 0
6. Unavailable items NOT shown when count == 0
7. No Telegram linked: returns success=True, telegram_sent=False, channel=in_app
8. Quote creator is None: notification is not attempted (handler guard)
9. Bot exception: error is caught, does not crash, returns success with error
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the function under test with graceful fallback.
# Test 1 explicitly verifies importability. Tests 3-9 use the guarded reference
# so they fail with AssertionError (not ImportError) when function is missing.
try:
    from services.telegram_service import send_procurement_invoice_complete_notification
    _FUNCTION_AVAILABLE = True
except ImportError:
    send_procurement_invoice_complete_notification = None
    _FUNCTION_AVAILABLE = False

from services.telegram_service import NotificationType


# =============================================================================
# HELPER: run async functions in sync tests
# =============================================================================

def run_async(coro):
    """Run an async coroutine synchronously for testing."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Mark for behavioral tests: skip-free but with clear assertion message
_SKIP_REASON = "send_procurement_invoice_complete_notification not yet implemented"


def _require_function():
    """Assert that the function is available, producing a clear failure message."""
    assert _FUNCTION_AVAILABLE, (
        "send_procurement_invoice_complete_notification must be importable from "
        "services.telegram_service — function not yet implemented"
    )


# =============================================================================
# TEST 1: FUNCTION EXISTS AND IS CALLABLE
# =============================================================================

class TestFunctionExists:
    """Test that send_procurement_invoice_complete_notification is importable."""

    def test_send_procurement_invoice_complete_notification_exists(self):
        """send_procurement_invoice_complete_notification should be importable from telegram_service."""
        _require_function()
        assert callable(send_procurement_invoice_complete_notification)


# =============================================================================
# TEST 2: NOTIFICATION TYPE ENUM
# =============================================================================

class TestNotificationTypeEnum:
    """Test that PROCUREMENT_INVOICE_COMPLETE exists in NotificationType."""

    def test_procurement_invoice_complete_in_enum(self):
        """NotificationType should have PROCUREMENT_INVOICE_COMPLETE member."""
        assert hasattr(NotificationType, "PROCUREMENT_INVOICE_COMPLETE"), \
            "NotificationType enum must have PROCUREMENT_INVOICE_COMPLETE member"

    def test_procurement_invoice_complete_value(self):
        """PROCUREMENT_INVOICE_COMPLETE should have string value 'procurement_invoice_complete'."""
        assert hasattr(NotificationType, "PROCUREMENT_INVOICE_COMPLETE"), \
            "NotificationType enum must have PROCUREMENT_INVOICE_COMPLETE member"
        assert NotificationType.PROCUREMENT_INVOICE_COMPLETE.value == "procurement_invoice_complete"


# =============================================================================
# TEST 3: PARTIAL COMPLETION MESSAGE
# =============================================================================

class TestPartialCompletionMessage:
    """Test notification for partial invoice completion (not all invoices done)."""

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_partial_completion_message_contains_invoice_number(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """Message should contain the invoice number for partial completion."""
        _require_function()

        mock_get_tg_id.return_value = 123456789
        mock_send.return_value = 42  # message_id
        mock_record.return_value = "notif-uuid"

        result = run_async(send_procurement_invoice_complete_notification(
            user_id="creator-uuid",
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-001",
            completed_count=1,
            total_count=3,
            unavailable_count=0,
            actor_name="Закупщик И.И."
        ))

        assert result["success"] is True
        assert result["telegram_sent"] is True

        # Verify the message sent to Telegram contains the invoice number
        send_call_args = mock_send.call_args
        # The notification should be called — check any arg contains invoice number
        call_kwargs = send_call_args[1] if send_call_args[1] else {}
        call_args = send_call_args[0] if send_call_args[0] else ()
        all_str_args = str(call_kwargs) + str(call_args)
        assert "INV-001" in all_str_args or mock_record.call_args is not None

        # Also check record_notification was called with message containing invoice number
        record_call = mock_record.call_args
        record_kwargs = record_call[1] if record_call and record_call[1] else {}
        record_args = record_call[0] if record_call and record_call[0] else ()
        all_record_str = str(record_kwargs) + str(record_args)
        assert "INV-001" in all_record_str

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_partial_completion_message_contains_progress_counter(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """Message should contain progress counter like '2 из 5 оценено'."""
        _require_function()

        mock_get_tg_id.return_value = 123456789
        mock_send.return_value = 42
        mock_record.return_value = "notif-uuid"

        result = run_async(send_procurement_invoice_complete_notification(
            user_id="creator-uuid",
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-002",
            completed_count=2,
            total_count=5,
            unavailable_count=0,
            actor_name="Закупщик И.И."
        ))

        assert result["success"] is True

        # Check the recorded message contains progress info
        record_call = mock_record.call_args
        all_record_str = str(record_call)
        # Should contain "2 из 5" and "оценено" (or similar wording)
        assert "2" in all_record_str
        assert "5" in all_record_str
        assert "оценено" in all_record_str.lower() or "оценен" in all_record_str.lower()


# =============================================================================
# TEST 4: ALL DONE CASE
# =============================================================================

class TestAllDoneCase:
    """Test notification when all invoices are completed."""

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_all_done_message_contains_completion_text(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """When completed_count == total_count, message should say 'Закупка полностью завершена'."""
        _require_function()

        mock_get_tg_id.return_value = 123456789
        mock_send.return_value = 42
        mock_record.return_value = "notif-uuid"

        result = run_async(send_procurement_invoice_complete_notification(
            user_id="creator-uuid",
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-003",
            completed_count=3,
            total_count=3,
            unavailable_count=0,
            actor_name="Закупщик И.И."
        ))

        assert result["success"] is True

        # Check message contains "Закупка полностью завершена"
        record_call = mock_record.call_args
        all_record_str = str(record_call)
        assert "Закупка полностью завершена" in all_record_str or \
               "закупка полностью завершена" in all_record_str.lower()


# =============================================================================
# TEST 5: UNAVAILABLE ITEMS SHOWN WHEN COUNT > 0
# =============================================================================

class TestUnavailableItemsShown:
    """Test that unavailable items count is shown in message when > 0."""

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_unavailable_items_shown_when_positive(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """Message should mention unavailable items when count > 0."""
        _require_function()

        mock_get_tg_id.return_value = 123456789
        mock_send.return_value = 42
        mock_record.return_value = "notif-uuid"

        result = run_async(send_procurement_invoice_complete_notification(
            user_id="creator-uuid",
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-004",
            completed_count=3,
            total_count=3,
            unavailable_count=2,
            actor_name="Закупщик И.И."
        ))

        assert result["success"] is True

        # Check that unavailable count is mentioned in the message
        record_call = mock_record.call_args
        all_record_str = str(record_call)
        # Should contain "2" (unavailable count) and some word about unavailability
        assert "недоступн" in all_record_str.lower() or \
               "unavailable" in all_record_str.lower() or \
               "отсутству" in all_record_str.lower()
        assert "2" in all_record_str


# =============================================================================
# TEST 6: UNAVAILABLE ITEMS NOT SHOWN WHEN COUNT == 0
# =============================================================================

class TestUnavailableItemsNotShown:
    """Test that unavailable items text is NOT shown when count is 0."""

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_unavailable_items_not_shown_when_zero(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """Message should NOT mention unavailable items when count == 0."""
        _require_function()

        mock_get_tg_id.return_value = 123456789
        mock_send.return_value = 42
        mock_record.return_value = "notif-uuid"

        result = run_async(send_procurement_invoice_complete_notification(
            user_id="creator-uuid",
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-005",
            completed_count=2,
            total_count=3,
            unavailable_count=0,
            actor_name="Закупщик И.И."
        ))

        assert result["success"] is True

        # Check that unavailable-related words are NOT in the message
        record_call = mock_record.call_args
        all_record_str = str(record_call)
        # None of the unavailability words should appear
        assert "недоступн" not in all_record_str.lower()
        assert "отсутству" not in all_record_str.lower()


# =============================================================================
# TEST 7: NO TELEGRAM LINKED
# =============================================================================

class TestNoTelegramLinked:
    """Test behavior when user has no linked Telegram account."""

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_no_telegram_returns_success_with_in_app(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """When user has no Telegram, should return success=True, telegram_sent=False."""
        _require_function()

        mock_get_tg_id.return_value = None  # No Telegram linked
        mock_record.return_value = "notif-uuid"

        result = run_async(send_procurement_invoice_complete_notification(
            user_id="creator-uuid",
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-006",
            completed_count=1,
            total_count=2,
            unavailable_count=0,
            actor_name="Закупщик И.И."
        ))

        # Notification is still recorded — just in-app only
        assert result["success"] is True
        assert result["telegram_sent"] is False

        # send_notification should NOT have been called (no telegram_id)
        mock_send.assert_not_called()

        # record_notification should have been called with channel="in_app"
        record_call = mock_record.call_args
        all_record_str = str(record_call)
        assert "in_app" in all_record_str


# =============================================================================
# TEST 8: QUOTE CREATOR IS NONE — HANDLER GUARD
# =============================================================================

class TestQuoteCreatorNone:
    """Test that when quote creator is None, notification is not attempted."""

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_none_user_id_skips_notification(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """If user_id is None, the function should skip and return early."""
        _require_function()

        result = run_async(send_procurement_invoice_complete_notification(
            user_id=None,
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-007",
            completed_count=1,
            total_count=2,
            unavailable_count=0,
            actor_name="Закупщик И.И."
        ))

        # Should return gracefully without attempting Telegram lookup
        assert result["success"] is True
        assert result.get("skipped") is True or result.get("telegram_sent") is False
        mock_get_tg_id.assert_not_called()
        mock_send.assert_not_called()
        mock_record.assert_not_called()


# =============================================================================
# TEST 9: BOT EXCEPTION HANDLING
# =============================================================================

class TestBotExceptionHandling:
    """Test that Telegram bot exceptions are caught and handled gracefully."""

    @patch('services.telegram_service.record_notification')
    @patch('services.telegram_service.send_notification', new_callable=AsyncMock)
    @patch('services.telegram_service.get_user_telegram_id', new_callable=AsyncMock)
    @patch('services.telegram_service.get_supabase')
    def test_bot_exception_does_not_crash(
        self, mock_supabase, mock_get_tg_id, mock_send, mock_record
    ):
        """If Telegram bot raises an exception, function should catch it and return success."""
        _require_function()

        mock_get_tg_id.return_value = 123456789
        mock_send.side_effect = Exception("Telegram API error: 403 Forbidden")
        mock_record.return_value = "notif-uuid"

        result = run_async(send_procurement_invoice_complete_notification(
            user_id="creator-uuid",
            quote_id="quote-uuid",
            quote_idn="КП-2026-001",
            customer_name="ООО Тест",
            invoice_number="INV-008",
            completed_count=1,
            total_count=2,
            unavailable_count=0,
            actor_name="Закупщик И.И."
        ))

        # Should NOT crash — returns success with error info
        assert result["success"] is True
        assert result["telegram_sent"] is False
        assert result.get("error") is not None
        assert "Telegram" in result["error"] or "403" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
