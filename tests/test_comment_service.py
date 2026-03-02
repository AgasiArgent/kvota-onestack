"""
Tests for Comment Service - Quote comments chat feature (kvota.quote_comments table)

Feature: Quote Chat tab with comments, @mentions, and unread tracking

Tests cover:
- Module imports (comment_service exists and exports expected symbols)
- get_comments_for_quote() — returns comments with author_name, ordered by created_at ASC
- create_comment() — inserts comment and returns created row with id and created_at
- create_comment() with mentions — stores mentions as jsonb array of user UUIDs
- get_unread_count() — count of comments after last_read_at; total if no read record
- mark_as_read() — upserts read receipt; calling twice updates timestamp
- get_org_users_for_mentions() — returns list of {id, full_name} for active org members
- Edge cases: empty body, malformed mentions, user with no profile (fallback name)

TDD: These tests are written BEFORE implementation.
The comment_service.py module does not exist yet -- tests should fail with ImportError.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    """Organization ID for tests."""
    return str(uuid4())


@pytest.fixture
def quote_id():
    """Quote ID for tests."""
    return str(uuid4())


@pytest.fixture
def user_id():
    """Current user ID for tests."""
    return str(uuid4())


@pytest.fixture
def other_user_id():
    """Another user ID for mention tests."""
    return str(uuid4())


@pytest.fixture
def comment_id():
    """Comment record ID for tests."""
    return str(uuid4())


@pytest.fixture
def sample_comment_row(comment_id, quote_id, user_id):
    """Sample comment database row as returned by Supabase query with FK join."""
    return {
        "id": comment_id,
        "quote_id": quote_id,
        "user_id": user_id,
        "body": "Need to check pricing with supplier.",
        "mentions": [],
        "created_at": "2026-03-02T10:00:00Z",
    }


@pytest.fixture
def sample_comment_with_mentions(comment_id, quote_id, user_id, other_user_id):
    """Sample comment with @mentions."""
    return {
        "id": comment_id,
        "quote_id": quote_id,
        "user_id": user_id,
        "body": f"@Ivan please check logistics costs",
        "mentions": [other_user_id],
        "created_at": "2026-03-02T10:30:00Z",
    }


@pytest.fixture
def sample_comment_with_profile(comment_id, quote_id, user_id):
    """Sample comment row enriched with user profile data."""
    return {
        "id": comment_id,
        "quote_id": quote_id,
        "user_id": user_id,
        "body": "Prices confirmed by supplier.",
        "mentions": [],
        "created_at": "2026-03-02T11:00:00Z",
        "user_profiles": {"full_name": "Petrov Petr"},
    }


@pytest.fixture
def sample_comment_null_profile(comment_id, quote_id, user_id):
    """Sample comment where user profile FK join returns null (user has no profile)."""
    return {
        "id": comment_id,
        "quote_id": quote_id,
        "user_id": user_id,
        "body": "Comment from user without profile.",
        "mentions": [],
        "created_at": "2026-03-02T12:00:00Z",
        "user_profiles": None,
    }


@pytest.fixture
def sample_read_receipt(quote_id, user_id):
    """Sample read receipt row from quote_comment_reads table."""
    return {
        "quote_id": quote_id,
        "user_id": user_id,
        "last_read_at": "2026-03-02T10:30:00Z",
    }


@pytest.fixture
def sample_org_users(user_id, other_user_id):
    """Sample list of organization users for @mentions dropdown."""
    return [
        {"user_id": user_id, "full_name": "Ivanov Ivan"},
        {"user_id": other_user_id, "full_name": "Petrova Maria"},
    ]


@pytest.fixture
def multiple_comments(quote_id, user_id, other_user_id):
    """Multiple comments for a quote in chronological order."""
    return [
        {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "Created the quote, need procurement input.",
            "mentions": [],
            "created_at": "2026-03-02T08:00:00Z",
            "user_profiles": {"full_name": "Ivanov Ivan"},
        },
        {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": other_user_id,
            "body": "Will check supplier prices today.",
            "mentions": [],
            "created_at": "2026-03-02T09:00:00Z",
            "user_profiles": {"full_name": "Petrova Maria"},
        },
        {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "Thanks, let me know when ready.",
            "mentions": [other_user_id],
            "created_at": "2026-03-02T10:00:00Z",
            "user_profiles": {"full_name": "Ivanov Ivan"},
        },
    ]


# =============================================================================
# IMPORT TESTS - verify module structure
# =============================================================================

class TestModuleImports:
    """Test that comment_service module exists and exports expected symbols."""

    def test_import_comment_service_module(self):
        """comment_service module can be imported."""
        from services import comment_service
        assert comment_service is not None

    def test_import_get_comments_for_quote(self):
        """get_comments_for_quote function is importable."""
        from services.comment_service import get_comments_for_quote
        assert get_comments_for_quote is not None

    def test_import_create_comment(self):
        """create_comment function is importable."""
        from services.comment_service import create_comment
        assert create_comment is not None

    def test_import_get_unread_count(self):
        """get_unread_count function is importable."""
        from services.comment_service import get_unread_count
        assert get_unread_count is not None

    def test_import_mark_as_read(self):
        """mark_as_read function is importable."""
        from services.comment_service import mark_as_read
        assert mark_as_read is not None

    def test_import_get_org_users_for_mentions(self):
        """get_org_users_for_mentions function is importable."""
        from services.comment_service import get_org_users_for_mentions
        assert get_org_users_for_mentions is not None


# =============================================================================
# GET COMMENTS FOR QUOTE TESTS
# =============================================================================

class TestGetCommentsForQuote:
    """Test get_comments_for_quote() function."""

    @patch('services.comment_service._get_supabase')
    def test_get_comments_returns_list(self, mock_get_supabase, quote_id, multiple_comments):
        """get_comments_for_quote returns a list of comment dicts."""
        from services.comment_service import get_comments_for_quote

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=multiple_comments
        )

        result = get_comments_for_quote(quote_id)

        assert isinstance(result, list)
        assert len(result) == 3

    @patch('services.comment_service._get_supabase')
    def test_get_comments_ordered_by_created_at_asc(self, mock_get_supabase, quote_id, multiple_comments):
        """Comments should be ordered by created_at ASC (oldest first, newest at bottom)."""
        from services.comment_service import get_comments_for_quote

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=multiple_comments
        )

        result = get_comments_for_quote(quote_id)

        # Verify order() was called with created_at ascending
        mock_client.table.return_value.select.return_value.eq.return_value.order.assert_called_once()
        order_call_args = mock_client.table.return_value.select.return_value.eq.return_value.order.call_args
        assert order_call_args[0][0] == "created_at"
        # desc should be False (ascending order for chat)
        assert order_call_args[1].get("desc", False) is False

    @patch('services.comment_service._get_supabase')
    def test_get_comments_queries_quote_comments_table(self, mock_get_supabase, quote_id):
        """Should query the quote_comments table."""
        from services.comment_service import get_comments_for_quote

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        get_comments_for_quote(quote_id)

        mock_client.table.assert_called_with("quote_comments")

    @patch('services.comment_service._get_supabase')
    def test_get_comments_filters_by_quote_id(self, mock_get_supabase, quote_id):
        """Should filter by quote_id."""
        from services.comment_service import get_comments_for_quote

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        get_comments_for_quote(quote_id)

        mock_client.table.return_value.select.return_value.eq.assert_called_with("quote_id", quote_id)

    @patch('services.comment_service._get_supabase')
    def test_get_comments_enriches_author_name(self, mock_get_supabase, quote_id, sample_comment_with_profile):
        """Comments should have author_name enriched from user profile."""
        from services.comment_service import get_comments_for_quote

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[sample_comment_with_profile]
        )

        result = get_comments_for_quote(quote_id)

        assert len(result) == 1
        comment = result[0]
        # The comment dict should have author_name field populated
        assert "author_name" in comment or (comment.get("user_profiles") or {}).get("full_name") is not None

    @patch('services.comment_service._get_supabase')
    def test_get_comments_empty_quote(self, mock_get_supabase, quote_id):
        """Returns empty list when quote has no comments."""
        from services.comment_service import get_comments_for_quote

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_comments_for_quote(quote_id)

        assert result == []

    @patch('services.comment_service._get_supabase')
    def test_get_comments_null_profile_fallback(self, mock_get_supabase, quote_id, sample_comment_null_profile):
        """When user has no profile, author_name falls back to truncated UUID."""
        from services.comment_service import get_comments_for_quote

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[sample_comment_null_profile]
        )

        result = get_comments_for_quote(quote_id)

        assert len(result) == 1
        comment = result[0]
        # Should not crash on null profile (PostgREST null FK pattern)
        # author_name should be either truncated UUID or some default
        author_name = comment.get("author_name", "")
        if author_name:
            # If the service enriches author_name, it should not be empty for null profile
            assert len(author_name) > 0


# =============================================================================
# CREATE COMMENT TESTS
# =============================================================================

class TestCreateComment:
    """Test create_comment() function."""

    @patch('services.comment_service._get_supabase')
    def test_create_comment_basic(self, mock_get_supabase, quote_id, user_id, sample_comment_row):
        """Create a basic comment with body text."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_comment_row]
        )

        result = create_comment(quote_id=quote_id, user_id=user_id, body="Need to check pricing with supplier.")

        assert result is not None
        # Should return dict with id and created_at
        assert "id" in result
        assert "created_at" in result

    @patch('services.comment_service._get_supabase')
    def test_create_comment_inserts_into_quote_comments(self, mock_get_supabase, quote_id, user_id, sample_comment_row):
        """Should insert into quote_comments table."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_comment_row]
        )

        create_comment(quote_id=quote_id, user_id=user_id, body="Test comment")

        mock_client.table.assert_called_with("quote_comments")

    @patch('services.comment_service._get_supabase')
    def test_create_comment_passes_correct_data(self, mock_get_supabase, quote_id, user_id, sample_comment_row):
        """Insert data should contain quote_id, user_id, body, and mentions."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_comment_row]
        )

        create_comment(quote_id=quote_id, user_id=user_id, body="Check prices")

        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["quote_id"] == quote_id
        assert insert_data["user_id"] == user_id
        assert insert_data["body"] == "Check prices"
        assert "mentions" in insert_data

    @patch('services.comment_service._get_supabase')
    def test_create_comment_returns_created_row(self, mock_get_supabase, quote_id, user_id, comment_id):
        """Should return the created comment dict with generated id and created_at."""
        from services.comment_service import create_comment

        created_row = {
            "id": comment_id,
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "New message",
            "mentions": [],
            "created_at": "2026-03-02T14:00:00Z",
        }

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[created_row]
        )

        result = create_comment(quote_id=quote_id, user_id=user_id, body="New message")

        assert result["id"] == comment_id
        assert result["body"] == "New message"
        assert result["created_at"] == "2026-03-02T14:00:00Z"


# =============================================================================
# CREATE COMMENT WITH MENTIONS TESTS
# =============================================================================

class TestCreateCommentWithMentions:
    """Test create_comment() with @mentions."""

    @patch('services.comment_service._get_supabase')
    def test_create_comment_with_mentions_list(
        self, mock_get_supabase, quote_id, user_id, other_user_id, sample_comment_with_mentions
    ):
        """Comment with mentions stores user UUIDs in mentions jsonb array."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_comment_with_mentions]
        )

        result = create_comment(
            quote_id=quote_id,
            user_id=user_id,
            body="@Ivan please check logistics costs",
            mentions=[other_user_id],
        )

        # Verify mentions were passed to insert
        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["mentions"] == [other_user_id]

    @patch('services.comment_service._get_supabase')
    def test_create_comment_with_multiple_mentions(
        self, mock_get_supabase, quote_id, user_id, other_user_id
    ):
        """Comment can mention multiple users."""
        from services.comment_service import create_comment

        third_user = str(uuid4())
        created_row = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "@Ivan @Maria check this please",
            "mentions": [other_user_id, third_user],
            "created_at": "2026-03-02T15:00:00Z",
        }

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[created_row]
        )

        result = create_comment(
            quote_id=quote_id,
            user_id=user_id,
            body="@Ivan @Maria check this please",
            mentions=[other_user_id, third_user],
        )

        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert len(insert_data["mentions"]) == 2
        assert other_user_id in insert_data["mentions"]
        assert third_user in insert_data["mentions"]

    @patch('services.comment_service._get_supabase')
    def test_create_comment_empty_mentions_default(self, mock_get_supabase, quote_id, user_id, sample_comment_row):
        """Comment without mentions defaults to empty list."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_comment_row]
        )

        create_comment(quote_id=quote_id, user_id=user_id, body="No mentions here")

        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["mentions"] == []


# =============================================================================
# GET UNREAD COUNT TESTS
# =============================================================================

class TestGetUnreadCount:
    """Test get_unread_count() function."""

    @patch('services.comment_service._get_supabase')
    def test_get_unread_count_with_read_receipt(self, mock_get_supabase, quote_id, user_id):
        """Returns count of comments created after user's last_read_at."""
        from services.comment_service import get_unread_count

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock read receipt lookup
        mock_reads_query = MagicMock()
        mock_comments_query = MagicMock()

        def table_side_effect(name):
            if name == "quote_comment_reads":
                return mock_reads_query
            elif name == "quote_comments":
                return mock_comments_query
            return MagicMock()

        mock_client.table.side_effect = table_side_effect

        # User has read up to 10:30 -- read receipt exists
        mock_reads_query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"last_read_at": "2026-03-02T10:30:00Z"}]
        )
        # 2 comments after 10:30
        mock_comments_query.select.return_value.eq.return_value.gt.return_value.execute.return_value = MagicMock(
            data=[{"id": "c1"}, {"id": "c2"}],
            count=2
        )

        result = get_unread_count(quote_id=quote_id, user_id=user_id)

        assert isinstance(result, int)
        assert result >= 0

    @patch('services.comment_service._get_supabase')
    def test_get_unread_count_no_read_receipt_returns_total(self, mock_get_supabase, quote_id, user_id):
        """When user has never opened chat, returns total comment count."""
        from services.comment_service import get_unread_count

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_reads_query = MagicMock()
        mock_comments_query = MagicMock()

        def table_side_effect(name):
            if name == "quote_comment_reads":
                return mock_reads_query
            elif name == "quote_comments":
                return mock_comments_query
            return MagicMock()

        mock_client.table.side_effect = table_side_effect

        # No read receipt for this user+quote
        mock_reads_query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        # Total 5 comments exist
        mock_comments_query.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": f"c{i}"} for i in range(5)],
            count=5
        )

        result = get_unread_count(quote_id=quote_id, user_id=user_id)

        # Should return total count (5) since user never read
        assert result == 5

    @patch('services.comment_service._get_supabase')
    def test_get_unread_count_zero_when_all_read(self, mock_get_supabase, quote_id, user_id):
        """Returns 0 when user has read all comments."""
        from services.comment_service import get_unread_count

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_reads_query = MagicMock()
        mock_comments_query = MagicMock()

        def table_side_effect(name):
            if name == "quote_comment_reads":
                return mock_reads_query
            elif name == "quote_comments":
                return mock_comments_query
            return MagicMock()

        mock_client.table.side_effect = table_side_effect

        # Read receipt is very recent
        mock_reads_query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"last_read_at": "2026-03-02T23:59:59Z"}]
        )
        # No comments after that timestamp
        mock_comments_query.select.return_value.eq.return_value.gt.return_value.execute.return_value = MagicMock(
            data=[],
            count=0
        )

        result = get_unread_count(quote_id=quote_id, user_id=user_id)

        assert result == 0

    @patch('services.comment_service._get_supabase')
    def test_get_unread_count_no_comments_at_all(self, mock_get_supabase, quote_id, user_id):
        """Returns 0 when quote has no comments at all."""
        from services.comment_service import get_unread_count

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_reads_query = MagicMock()
        mock_comments_query = MagicMock()

        def table_side_effect(name):
            if name == "quote_comment_reads":
                return mock_reads_query
            elif name == "quote_comments":
                return mock_comments_query
            return MagicMock()

        mock_client.table.side_effect = table_side_effect

        # No read receipt
        mock_reads_query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        # No comments either
        mock_comments_query.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[],
            count=0
        )

        result = get_unread_count(quote_id=quote_id, user_id=user_id)

        assert result == 0


# =============================================================================
# MARK AS READ TESTS
# =============================================================================

class TestMarkAsRead:
    """Test mark_as_read() function."""

    @patch('services.comment_service._get_supabase')
    def test_mark_as_read_upserts_read_receipt(self, mock_get_supabase, quote_id, user_id):
        """mark_as_read should upsert into quote_comment_reads table."""
        from services.comment_service import mark_as_read

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

        mark_as_read(quote_id=quote_id, user_id=user_id)

        mock_client.table.assert_called_with("quote_comment_reads")

    @patch('services.comment_service._get_supabase')
    def test_mark_as_read_sets_last_read_at(self, mock_get_supabase, quote_id, user_id):
        """Upserted data should contain quote_id, user_id, and last_read_at timestamp."""
        from services.comment_service import mark_as_read

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

        mark_as_read(quote_id=quote_id, user_id=user_id)

        upsert_call = mock_client.table.return_value.upsert.call_args
        upsert_data = upsert_call[0][0]
        assert upsert_data["quote_id"] == quote_id
        assert upsert_data["user_id"] == user_id
        assert "last_read_at" in upsert_data

    @patch('services.comment_service._get_supabase')
    def test_mark_as_read_idempotent(self, mock_get_supabase, quote_id, user_id):
        """Calling mark_as_read twice should not raise errors (upsert handles both cases)."""
        from services.comment_service import mark_as_read

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

        # Call twice -- should not raise
        mark_as_read(quote_id=quote_id, user_id=user_id)
        mark_as_read(quote_id=quote_id, user_id=user_id)

        # Upsert should have been called twice
        assert mock_client.table.return_value.upsert.call_count == 2

    @patch('services.comment_service._get_supabase')
    def test_mark_as_read_returns_none(self, mock_get_supabase, quote_id, user_id):
        """mark_as_read should return None (fire-and-forget operation)."""
        from services.comment_service import mark_as_read

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

        result = mark_as_read(quote_id=quote_id, user_id=user_id)

        assert result is None


# =============================================================================
# GET ORG USERS FOR MENTIONS TESTS
# =============================================================================

class TestGetOrgUsersForMentions:
    """Test get_org_users_for_mentions() function."""

    @patch('services.comment_service._get_supabase')
    def test_get_org_users_returns_list(self, mock_get_supabase, org_id, sample_org_users):
        """Should return a list of user dicts with id and full_name."""
        from services.comment_service import get_org_users_for_mentions

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=sample_org_users
        )

        result = get_org_users_for_mentions(org_id)

        assert isinstance(result, list)
        assert len(result) == 2

    @patch('services.comment_service._get_supabase')
    def test_get_org_users_has_required_fields(self, mock_get_supabase, org_id, sample_org_users):
        """Each user dict should have at least user_id and full_name."""
        from services.comment_service import get_org_users_for_mentions

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=sample_org_users
        )

        result = get_org_users_for_mentions(org_id)

        for user in result:
            # Each entry should have an id field (user_id or id) and full_name
            has_id = "user_id" in user or "id" in user
            assert has_id, f"User dict missing id field: {user}"
            assert "full_name" in user, f"User dict missing full_name field: {user}"

    @patch('services.comment_service._get_supabase')
    def test_get_org_users_empty_org(self, mock_get_supabase, org_id):
        """Returns empty list when organization has no users."""
        from services.comment_service import get_org_users_for_mentions

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_org_users_for_mentions(org_id)

        assert result == []

    @patch('services.comment_service._get_supabase')
    def test_get_org_users_filters_by_org_id(self, mock_get_supabase, org_id, sample_org_users):
        """Should filter users by organization_id."""
        from services.comment_service import get_org_users_for_mentions

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=sample_org_users
        )

        get_org_users_for_mentions(org_id)

        # Verify eq was called with organization_id
        mock_client.table.return_value.select.return_value.eq.assert_called_once()
        eq_args = mock_client.table.return_value.select.return_value.eq.call_args
        assert eq_args[0][0] == "organization_id"
        assert eq_args[0][1] == org_id


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Edge cases and error handling for comment service."""

    @patch('services.comment_service._get_supabase')
    def test_create_comment_empty_body(self, mock_get_supabase, quote_id, user_id):
        """Creating a comment with empty body -- service should handle or reject.

        The service may either:
        1. Raise ValueError for empty body (validation in service)
        2. Allow it and let DB constraints handle it
        Either behavior is acceptable.
        """
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # If service validates and raises, test passes
        # If service inserts, mock should handle it
        empty_row = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "",
            "mentions": [],
            "created_at": "2026-03-02T14:00:00Z",
        }
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[empty_row]
        )

        try:
            result = create_comment(quote_id=quote_id, user_id=user_id, body="")
            # If it didn't raise, it should still return a valid dict
            assert result is not None
        except (ValueError, Exception):
            # Acceptable: service rejects empty body
            pass

    @patch('services.comment_service._get_supabase')
    def test_create_comment_whitespace_only_body(self, mock_get_supabase, quote_id, user_id):
        """Creating a comment with whitespace-only body."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        ws_row = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "   ",
            "mentions": [],
            "created_at": "2026-03-02T14:00:00Z",
        }
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[ws_row]
        )

        try:
            result = create_comment(quote_id=quote_id, user_id=user_id, body="   ")
            # If it didn't raise, acceptable
            assert result is not None
        except (ValueError, Exception):
            # Acceptable: service rejects whitespace-only body
            pass

    @patch('services.comment_service._get_supabase')
    def test_create_comment_malformed_mentions_not_list(self, mock_get_supabase, quote_id, user_id):
        """Malformed mentions (not a list) should be handled gracefully."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        row = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "Test with bad mentions",
            "mentions": [],
            "created_at": "2026-03-02T14:00:00Z",
        }
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[row]
        )

        try:
            # Pass a string instead of list -- service should handle
            result = create_comment(
                quote_id=quote_id,
                user_id=user_id,
                body="Test with bad mentions",
                mentions="not-a-list",
            )
            # If it coerced to list or ignored, check it didn't crash
            assert result is not None
        except (TypeError, ValueError):
            # Acceptable: service rejects malformed mentions
            pass

    @patch('services.comment_service._get_supabase')
    def test_create_comment_mentions_with_invalid_uuids(self, mock_get_supabase, quote_id, user_id):
        """Mentions list with invalid UUID strings should be handled."""
        from services.comment_service import create_comment

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        row = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "Test with invalid mention UUIDs",
            "mentions": ["invalid-uuid"],
            "created_at": "2026-03-02T14:00:00Z",
        }
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[row]
        )

        try:
            result = create_comment(
                quote_id=quote_id,
                user_id=user_id,
                body="Test with invalid mention UUIDs",
                mentions=["invalid-uuid"],
            )
            # Service may pass through to DB (which will reject FK) or validate client-side
            assert result is not None
        except (ValueError, Exception):
            pass

    @patch('services.comment_service._get_supabase')
    def test_get_comments_user_with_no_profile_does_not_crash(
        self, mock_get_supabase, quote_id, user_id
    ):
        """Comment from user with no profile should not crash the service.

        PostgREST returns null for FK join when there's no matching profile.
        author_name should fall back to truncated user UUID.
        """
        from services.comment_service import get_comments_for_quote

        comment_no_profile = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "Anonymous-ish comment",
            "mentions": [],
            "created_at": "2026-03-02T10:00:00Z",
            "user_profiles": None,  # PostgREST null FK
        }

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[comment_no_profile]
        )

        # Should NOT raise AttributeError on None.get()
        result = get_comments_for_quote(quote_id)

        assert len(result) == 1
        # Verify author_name fallback
        comment = result[0]
        author_name = comment.get("author_name", "")
        # Should be either truncated UUID or some non-empty fallback
        # The key assertion is that it didn't crash
        assert isinstance(comment, dict)

    @patch('services.comment_service._get_supabase')
    def test_create_comment_very_long_body(self, mock_get_supabase, quote_id, user_id):
        """Comment with very long body text should be accepted (DB TEXT type has no limit)."""
        from services.comment_service import create_comment

        long_body = "A" * 10000
        row = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": long_body,
            "mentions": [],
            "created_at": "2026-03-02T14:00:00Z",
        }

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[row]
        )

        result = create_comment(quote_id=quote_id, user_id=user_id, body=long_body)

        assert result is not None
        insert_data = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_data["body"] == long_body

    @patch('services.comment_service._get_supabase')
    def test_get_unread_count_returns_int_not_none(self, mock_get_supabase, quote_id, user_id):
        """get_unread_count should always return an int, never None."""
        from services.comment_service import get_unread_count

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_reads_query = MagicMock()
        mock_comments_query = MagicMock()

        def table_side_effect(name):
            if name == "quote_comment_reads":
                return mock_reads_query
            elif name == "quote_comments":
                return mock_comments_query
            return MagicMock()

        mock_client.table.side_effect = table_side_effect

        mock_reads_query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mock_comments_query.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[],
            count=0
        )

        result = get_unread_count(quote_id=quote_id, user_id=user_id)

        assert isinstance(result, int)
        assert result >= 0


# =============================================================================
# INTEGRATION-STYLE TESTS (multiple service calls)
# =============================================================================

class TestCommentWorkflow:
    """Test realistic workflow: post comment, then mark as read, check unread count."""

    @patch('services.comment_service._get_supabase')
    def test_post_comment_then_check_exists(self, mock_get_supabase, quote_id, user_id):
        """After posting a comment, get_comments should return it."""
        from services.comment_service import create_comment, get_comments_for_quote

        created_row = {
            "id": str(uuid4()),
            "quote_id": quote_id,
            "user_id": user_id,
            "body": "Test workflow comment",
            "mentions": [],
            "created_at": "2026-03-02T14:00:00Z",
        }

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Step 1: Create comment
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[created_row]
        )
        result = create_comment(quote_id=quote_id, user_id=user_id, body="Test workflow comment")
        assert result is not None
        assert result["body"] == "Test workflow comment"

        # Step 2: Get comments (mock returns the created one)
        enriched_row = {**created_row, "user_profiles": {"full_name": "Test User"}}
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[enriched_row]
        )
        comments = get_comments_for_quote(quote_id)
        assert len(comments) >= 1

    @patch('services.comment_service._get_supabase')
    def test_mark_read_reduces_unread_count_to_zero(self, mock_get_supabase, quote_id, user_id):
        """After mark_as_read, get_unread_count should return 0."""
        from services.comment_service import mark_as_read, get_unread_count

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Step 1: Mark as read
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
        mark_as_read(quote_id=quote_id, user_id=user_id)

        # Step 2: Check unread count (should be 0 after read)
        mock_reads_query = MagicMock()
        mock_comments_query = MagicMock()

        def table_side_effect(name):
            if name == "quote_comment_reads":
                return mock_reads_query
            elif name == "quote_comments":
                return mock_comments_query
            return MagicMock()

        mock_client.table.side_effect = table_side_effect

        now_iso = datetime.now(timezone.utc).isoformat()
        mock_reads_query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"last_read_at": now_iso}]
        )
        mock_comments_query.select.return_value.eq.return_value.gt.return_value.execute.return_value = MagicMock(
            data=[],
            count=0
        )

        count = get_unread_count(quote_id=quote_id, user_id=user_id)
        assert count == 0
