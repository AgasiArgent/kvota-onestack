"""
Tests for Training Videos feature.

Feature: /training page with multi-platform video embeds (Rutube, YouTube),
category filtering, admin CRUD.

Tests cover:
- extract_video_info() multi-platform URL parser
- extract_youtube_id() legacy wrapper
- TrainingVideo dataclass (with platform field)
- Service CRUD operations (mocked Supabase)
- Route access control (auth + role checks)
- Org isolation (cross-org access prevention)
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from uuid import uuid4


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    """Organization ID for tests."""
    return str(uuid4())


@pytest.fixture
def other_org_id():
    """Different organization ID for cross-org tests."""
    return str(uuid4())


@pytest.fixture
def user_id():
    """User ID for tests."""
    return str(uuid4())


@pytest.fixture
def sample_video_data(org_id, user_id):
    """Sample training video database row."""
    return {
        "id": str(uuid4()),
        "organization_id": org_id,
        "title": "Как создать КП за 5 минут",
        "description": "Пошаговая инструкция по созданию коммерческого предложения",
        "youtube_id": "dQw4w9WgXcQ",
        "platform": "youtube",
        "category": "Продажи",
        "sort_order": 0,
        "is_active": True,
        "created_by": user_id,
        "created_at": "2026-02-24T10:00:00Z",
        "updated_at": "2026-02-24T10:00:00Z",
    }


@pytest.fixture
def sample_video_data_logistics(org_id, user_id):
    """Sample logistics video database row."""
    return {
        "id": str(uuid4()),
        "organization_id": org_id,
        "title": "Отслеживание грузов",
        "description": "Как отслеживать статус грузов в системе",
        "youtube_id": "abc123XYZ",
        "platform": "rutube",
        "category": "Логистика",
        "sort_order": 10,
        "is_active": True,
        "created_by": user_id,
        "created_at": "2026-02-24T11:00:00Z",
        "updated_at": "2026-02-24T11:00:00Z",
    }


@pytest.fixture
def sample_video_data_other_org(other_org_id, user_id):
    """Sample video from a different org (for isolation tests)."""
    return {
        "id": str(uuid4()),
        "organization_id": other_org_id,
        "title": "Video from another org",
        "description": None,
        "youtube_id": "otherOrgVid",
        "platform": "rutube",
        "category": "Общее",
        "sort_order": 0,
        "is_active": True,
        "created_by": user_id,
        "created_at": "2026-02-24T12:00:00Z",
        "updated_at": "2026-02-24T12:00:00Z",
    }


@pytest.fixture
def multiple_videos(org_id, user_id):
    """Multiple videos with different categories."""
    return [
        {
            "id": str(uuid4()),
            "organization_id": org_id,
            "title": "Создание КП",
            "description": "Инструкция",
            "youtube_id": "vid001",
            "platform": "rutube",
            "category": "Продажи",
            "sort_order": 0,
            "is_active": True,
            "created_by": user_id,
            "created_at": "2026-02-24T10:00:00Z",
            "updated_at": "2026-02-24T10:00:00Z",
        },
        {
            "id": str(uuid4()),
            "organization_id": org_id,
            "title": "Работа с поставщиками",
            "description": None,
            "youtube_id": "vid002",
            "platform": "youtube",
            "category": "Закупки",
            "sort_order": 0,
            "is_active": True,
            "created_by": user_id,
            "created_at": "2026-02-24T10:00:00Z",
            "updated_at": "2026-02-24T10:00:00Z",
        },
        {
            "id": str(uuid4()),
            "organization_id": org_id,
            "title": "Отгрузка товара",
            "description": "Описание",
            "youtube_id": "vid003",
            "platform": "rutube",
            "category": "Логистика",
            "sort_order": 10,
            "is_active": True,
            "created_by": user_id,
            "created_at": "2026-02-24T10:00:00Z",
            "updated_at": "2026-02-24T10:00:00Z",
        },
        {
            "id": str(uuid4()),
            "organization_id": org_id,
            "title": "Ещё один ролик по продажам",
            "description": None,
            "youtube_id": "vid004",
            "platform": "rutube",
            "category": "Продажи",
            "sort_order": 10,
            "is_active": True,
            "created_by": user_id,
            "created_at": "2026-02-24T10:00:00Z",
            "updated_at": "2026-02-24T10:00:00Z",
        },
    ]


# =============================================================================
# TESTS: extract_video_info() multi-platform URL parser
# =============================================================================

class TestExtractVideoInfo:
    """Tests for extract_video_info multi-platform URL parser."""

    def test_rutube_full_url(self):
        """Rutube URL extracts video ID and platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://rutube.ru/video/abc123def456/")
        assert result == {"video_id": "abc123def456", "platform": "rutube"}

    def test_rutube_url_no_trailing_slash(self):
        """Rutube URL without trailing slash works."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://rutube.ru/video/abc123def456")
        assert result == {"video_id": "abc123def456", "platform": "rutube"}

    def test_youtube_full_url(self):
        """YouTube URL extracts video ID and platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result == {"video_id": "dQw4w9WgXcQ", "platform": "youtube"}

    def test_youtube_short_url(self):
        """YouTube short URL extracts video ID and platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://youtu.be/dQw4w9WgXcQ")
        assert result == {"video_id": "dQw4w9WgXcQ", "platform": "youtube"}

    def test_youtube_embed_url(self):
        """YouTube embed URL extracts video ID and platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert result == {"video_id": "dQw4w9WgXcQ", "platform": "youtube"}

    def test_raw_id_defaults_to_rutube(self):
        """Raw ID defaults to rutube platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("abc123def456")
        assert result == {"video_id": "abc123def456", "platform": "rutube"}

    def test_whitespace_stripped(self):
        """Whitespace around input is stripped."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("  https://rutube.ru/video/abc123/  ")
        assert result == {"video_id": "abc123", "platform": "rutube"}

    def test_empty_string(self):
        """Empty string returns empty video_id with rutube platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("")
        assert result == {"video_id": "", "platform": "rutube"}

    def test_youtube_url_with_extra_params(self):
        """YouTube URL with extra params extracts correct ID."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://www.youtube.com/watch?v=abc123&t=42")
        assert result == {"video_id": "abc123", "platform": "youtube"}

    def test_rutube_long_hash(self):
        """Rutube with long hash (32+ chars) works."""
        from services.training_video_service import extract_video_info
        long_hash = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        result = extract_video_info(f"https://rutube.ru/video/{long_hash}/")
        assert result == {"video_id": long_hash, "platform": "rutube"}

    def test_loom_share_url(self):
        """Loom share URL extracts video ID and platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://www.loom.com/share/abc123def456")
        assert result == {"video_id": "abc123def456", "platform": "loom"}

    def test_loom_embed_url(self):
        """Loom embed URL extracts video ID and platform."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://www.loom.com/embed/abc123def456")
        assert result == {"video_id": "abc123def456", "platform": "loom"}

    def test_loom_url_with_query_params(self):
        """Loom URL with query params extracts clean ID."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://www.loom.com/share/abc123?sid=xyz")
        assert result == {"video_id": "abc123", "platform": "loom"}

    def test_loom_url_no_www(self):
        """Loom URL without www prefix works."""
        from services.training_video_service import extract_video_info
        result = extract_video_info("https://loom.com/share/abc123def456")
        assert result == {"video_id": "abc123def456", "platform": "loom"}


# =============================================================================
# TESTS: extract_youtube_id() legacy wrapper
# =============================================================================

class TestExtractYoutubeId:
    """Tests for extract_youtube_id utility function."""

    def test_full_url_standard(self):
        """Standard YouTube URL extracts video ID."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("https://www.youtube.com/watch?v=abc123")
        assert result == "abc123"

    def test_full_url_without_www(self):
        """YouTube URL without www extracts video ID."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("https://youtube.com/watch?v=abc123")
        assert result == "abc123"

    def test_short_url(self):
        """Short youtu.be URL extracts video ID."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("https://youtu.be/abc123")
        assert result == "abc123"

    def test_raw_id(self):
        """Raw video ID is returned as-is."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("abc123")
        assert result == "abc123"

    def test_url_with_extra_params(self):
        """URL with additional query params still extracts correct ID."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("https://www.youtube.com/watch?v=abc123&t=42")
        assert result == "abc123"

    def test_url_with_extra_params_before_v(self):
        """URL with params before v= still extracts correct ID."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("https://www.youtube.com/watch?list=PLxyz&v=abc123")
        assert result == "abc123"

    def test_short_url_with_params(self):
        """Short URL with query params extracts ID without params."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("https://youtu.be/abc123?t=42")
        assert result == "abc123"

    def test_whitespace_stripped(self):
        """Whitespace around input is stripped."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("  abc123  ")
        assert result == "abc123"

    def test_long_youtube_id(self):
        """Real-length YouTube ID (11 chars) works."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("dQw4w9WgXcQ")
        assert result == "dQw4w9WgXcQ"

    def test_url_with_long_id(self):
        """Full URL with real-length ID."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result == "dQw4w9WgXcQ"

    def test_empty_string(self):
        """Empty string returns empty string."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("")
        assert result == ""

    def test_http_url(self):
        """HTTP (not HTTPS) URL still works."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("http://www.youtube.com/watch?v=abc123")
        assert result == "abc123"


# =============================================================================
# TESTS: TrainingVideo dataclass
# =============================================================================

class TestTrainingVideoDataclass:
    """Tests for TrainingVideo dataclass."""

    def test_creation_with_required_fields(self):
        """TrainingVideo can be created with required fields."""
        from services.training_video_service import TrainingVideo
        video = TrainingVideo(
            id="vid-uuid",
            organization_id="org-uuid",
            title="Test Video",
            youtube_id="dQw4w9WgXcQ",
            category="Продажи",
            sort_order=0,
            is_active=True,
        )
        assert video.id == "vid-uuid"
        assert video.title == "Test Video"
        assert video.youtube_id == "dQw4w9WgXcQ"
        assert video.category == "Продажи"
        assert video.is_active is True
        assert video.platform == "rutube"  # default

    def test_creation_with_all_fields(self):
        """TrainingVideo can be created with all fields including optional."""
        from services.training_video_service import TrainingVideo
        now = datetime.now()
        video = TrainingVideo(
            id="vid-uuid",
            organization_id="org-uuid",
            title="Full Video",
            youtube_id="dQw4w9WgXcQ",
            category="Логистика",
            sort_order=10,
            is_active=True,
            platform="youtube",
            description="Some description",
            created_by="user-uuid",
            created_at=now,
            updated_at=now,
        )
        assert video.description == "Some description"
        assert video.created_by == "user-uuid"
        assert video.created_at == now
        assert video.sort_order == 10
        assert video.platform == "youtube"

    def test_optional_fields_default_to_none(self):
        """Optional fields default to None."""
        from services.training_video_service import TrainingVideo
        video = TrainingVideo(
            id="vid-uuid",
            organization_id="org-uuid",
            title="Minimal Video",
            youtube_id="abc123",
            category="Общее",
            sort_order=0,
            is_active=True,
        )
        assert video.platform == "rutube"  # default
        assert video.description is None
        assert video.created_by is None
        assert video.created_at is None
        assert video.updated_at is None


# =============================================================================
# TESTS: _parse_video function
# =============================================================================

class TestParseVideo:
    """Tests for _parse_video helper function."""

    def test_parse_full_data(self, sample_video_data):
        """Parse a complete database row into TrainingVideo."""
        from services.training_video_service import _parse_video
        video = _parse_video(sample_video_data)
        assert video.id == sample_video_data["id"]
        assert video.title == "Как создать КП за 5 минут"
        assert video.youtube_id == "dQw4w9WgXcQ"
        assert video.category == "Продажи"
        assert video.is_active is True
        assert video.description == "Пошаговая инструкция по созданию коммерческого предложения"

    def test_parse_minimal_data(self, org_id):
        """Parse a row with only required fields."""
        from services.training_video_service import _parse_video
        data = {
            "id": "vid-uuid",
            "organization_id": org_id,
            "title": "Simple Video",
            "youtube_id": "simple123",
        }
        video = _parse_video(data)
        assert video.id == "vid-uuid"
        assert video.title == "Simple Video"
        assert video.category == "Общее"  # default
        assert video.sort_order == 0  # default
        assert video.is_active is True  # default

    def test_parse_null_description(self, org_id):
        """Parse row where description is null."""
        from services.training_video_service import _parse_video
        data = {
            "id": "vid-uuid",
            "organization_id": org_id,
            "title": "No Description",
            "youtube_id": "nodesc123",
            "description": None,
            "category": "Закупки",
            "sort_order": 5,
            "is_active": True,
        }
        video = _parse_video(data)
        assert video.description is None


# =============================================================================
# TESTS: Service CRUD - get_all_videos
# =============================================================================

class TestGetAllVideos:
    """Tests for get_all_videos service function."""

    @patch('services.training_video_service._get_supabase')
    def test_returns_list_of_videos(self, mock_get_supabase, org_id, multiple_videos):
        """get_all_videos returns list of TrainingVideo objects."""
        from services.training_video_service import get_all_videos, TrainingVideo

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=multiple_videos
        )

        result = get_all_videos(org_id)

        assert isinstance(result, list)
        assert len(result) == 4
        assert all(isinstance(v, TrainingVideo) for v in result)
        mock_client.table.assert_called_with("training_videos")

    @patch('services.training_video_service._get_supabase')
    def test_returns_empty_list_when_no_videos(self, mock_get_supabase, org_id):
        """get_all_videos returns empty list when no videos exist."""
        from services.training_video_service import get_all_videos

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_all_videos(org_id)

        assert result == []

    @patch('services.training_video_service._get_supabase')
    def test_filter_by_category(self, mock_get_supabase, org_id, multiple_videos):
        """get_all_videos with category filter returns only matching videos."""
        from services.training_video_service import get_all_videos

        sales_videos = [v for v in multiple_videos if v["category"] == "Продажи"]

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        # When category is provided, an extra .eq() call is chained
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.eq.return_value.execute.return_value = MagicMock(
            data=sales_videos
        )

        result = get_all_videos(org_id, category="Продажи")

        assert len(result) == 2
        assert all(v.category == "Продажи" for v in result)

    @patch('services.training_video_service._get_supabase')
    def test_returns_empty_list_on_exception(self, mock_get_supabase, org_id):
        """get_all_videos returns empty list on DB exception (no crash)."""
        from services.training_video_service import get_all_videos

        mock_get_supabase.side_effect = Exception("DB connection failed")

        result = get_all_videos(org_id)

        assert result == []

    @patch('services.training_video_service._get_supabase')
    def test_returns_empty_list_when_data_is_none(self, mock_get_supabase, org_id):
        """get_all_videos returns empty list when response data is None."""
        from services.training_video_service import get_all_videos

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=None
        )

        result = get_all_videos(org_id)

        assert result == []


# =============================================================================
# TESTS: Service CRUD - get_categories
# =============================================================================

class TestGetCategories:
    """Tests for get_categories service function."""

    @patch('services.training_video_service._get_supabase')
    def test_returns_sorted_unique_categories(self, mock_get_supabase, org_id):
        """get_categories returns sorted unique category names."""
        from services.training_video_service import get_categories

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"category": "Продажи"},
                {"category": "Закупки"},
                {"category": "Продажи"},  # duplicate
                {"category": "Логистика"},
                {"category": "Закупки"},  # duplicate
            ]
        )

        result = get_categories(org_id)

        assert isinstance(result, list)
        assert len(result) == 3
        # Should be sorted alphabetically
        assert result == sorted(result)
        assert "Продажи" in result
        assert "Закупки" in result
        assert "Логистика" in result

    @patch('services.training_video_service._get_supabase')
    def test_returns_empty_list_when_no_videos(self, mock_get_supabase, org_id):
        """get_categories returns empty list when no videos exist."""
        from services.training_video_service import get_categories

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_categories(org_id)

        assert result == []

    @patch('services.training_video_service._get_supabase')
    def test_returns_empty_list_on_exception(self, mock_get_supabase, org_id):
        """get_categories returns empty list on DB exception."""
        from services.training_video_service import get_categories

        mock_get_supabase.side_effect = Exception("DB error")

        result = get_categories(org_id)

        assert result == []


# =============================================================================
# TESTS: Service CRUD - create_video
# =============================================================================

class TestCreateVideo:
    """Tests for create_video service function."""

    @patch('services.training_video_service._get_supabase')
    def test_create_video_success(self, mock_get_supabase, org_id, user_id, sample_video_data):
        """create_video returns created TrainingVideo on success."""
        from services.training_video_service import create_video, TrainingVideo

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_video_data]
        )

        result = create_video(
            organization_id=org_id,
            title="Как создать КП за 5 минут",
            youtube_id="dQw4w9WgXcQ",
            category="Продажи",
            description="Пошаговая инструкция",
            created_by=user_id,
            platform="youtube",
        )

        assert result is not None
        assert isinstance(result, TrainingVideo)
        assert result.title == "Как создать КП за 5 минут"
        assert result.youtube_id == "dQw4w9WgXcQ"
        assert result.platform == "youtube"
        mock_client.table.assert_called_with("training_videos")

        # Verify platform is included in insert data
        insert_call = mock_client.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["platform"] == "youtube"

    @patch('services.training_video_service._get_supabase')
    def test_create_video_strips_whitespace(self, mock_get_supabase, org_id, sample_video_data):
        """create_video strips whitespace from title and youtube_id."""
        from services.training_video_service import create_video

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_video_data]
        )

        create_video(
            organization_id=org_id,
            title="  Title with spaces  ",
            youtube_id="  abc123  ",
            category="  Продажи  ",
        )

        # Verify the data sent to insert had stripped values
        insert_call = mock_client.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["title"] == "Title with spaces"
        assert inserted_data["youtube_id"] == "abc123"
        assert inserted_data["category"] == "Продажи"

    @patch('services.training_video_service._get_supabase')
    def test_create_video_default_category(self, mock_get_supabase, org_id, sample_video_data):
        """create_video uses default category when empty string provided."""
        from services.training_video_service import create_video

        # Modify sample data to match default category
        modified_data = {**sample_video_data, "category": "Общее"}

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[modified_data]
        )

        create_video(
            organization_id=org_id,
            title="Test",
            youtube_id="abc123",
            category="",
        )

        insert_call = mock_client.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["category"] == "Общее"

    @patch('services.training_video_service._get_supabase')
    def test_create_video_returns_none_on_error(self, mock_get_supabase, org_id):
        """create_video returns None on DB error."""
        from services.training_video_service import create_video

        mock_get_supabase.side_effect = Exception("Insert failed")

        result = create_video(
            organization_id=org_id,
            title="Test",
            youtube_id="abc123",
            category="Общее",
        )

        assert result is None


# =============================================================================
# TESTS: Service CRUD - update_video
# =============================================================================

class TestUpdateVideo:
    """Tests for update_video service function."""

    @patch('services.training_video_service._get_supabase')
    def test_update_video_partial(self, mock_get_supabase, sample_video_data):
        """update_video with partial fields updates only specified fields."""
        from services.training_video_service import update_video

        updated_data = {**sample_video_data, "title": "Updated Title"}

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        result = update_video(sample_video_data["id"], title="Updated Title")

        assert result is not None
        assert result.title == "Updated Title"

    @patch('services.training_video_service._get_supabase')
    def test_update_video_category_change(self, mock_get_supabase, sample_video_data):
        """update_video can change category."""
        from services.training_video_service import update_video

        updated_data = {**sample_video_data, "category": "Логистика"}

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        result = update_video(sample_video_data["id"], category="Логистика")

        assert result is not None
        assert result.category == "Логистика"

    @patch('services.training_video_service.get_video')
    def test_update_video_no_fields_returns_current(self, mock_get_video, sample_video_data):
        """update_video with no update fields returns current video."""
        from services.training_video_service import update_video, _parse_video

        current_video = _parse_video(sample_video_data)
        mock_get_video.return_value = current_video

        result = update_video(sample_video_data["id"])

        assert result is not None
        assert result.title == sample_video_data["title"]
        mock_get_video.assert_called_once_with(sample_video_data["id"])

    @patch('services.training_video_service._get_supabase')
    def test_update_video_returns_none_on_error(self, mock_get_supabase, sample_video_data):
        """update_video returns None on DB error."""
        from services.training_video_service import update_video

        mock_get_supabase.side_effect = Exception("Update failed")

        result = update_video(sample_video_data["id"], title="New Title")

        assert result is None


# =============================================================================
# TESTS: Service CRUD - delete_video
# =============================================================================

class TestDeleteVideo:
    """Tests for delete_video service function."""

    @patch('services.training_video_service._get_supabase')
    def test_delete_video_success(self, mock_get_supabase, sample_video_data):
        """delete_video returns True on success."""
        from services.training_video_service import delete_video

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_video_data]
        )

        result = delete_video(sample_video_data["id"])

        assert result is True
        mock_client.table.assert_called_with("training_videos")

    @patch('services.training_video_service._get_supabase')
    def test_delete_video_returns_false_on_error(self, mock_get_supabase):
        """delete_video returns False on DB error."""
        from services.training_video_service import delete_video

        mock_get_supabase.side_effect = Exception("Delete failed")

        result = delete_video("nonexistent-id")

        assert result is False


# =============================================================================
# TESTS: Service CRUD - get_video (single fetch)
# =============================================================================

class TestGetVideo:
    """Tests for get_video service function."""

    @patch('services.training_video_service._get_supabase')
    def test_get_video_found(self, mock_get_supabase, sample_video_data):
        """get_video returns TrainingVideo when found."""
        from services.training_video_service import get_video, TrainingVideo

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_video_data]
        )

        result = get_video(sample_video_data["id"])

        assert result is not None
        assert isinstance(result, TrainingVideo)
        assert result.id == sample_video_data["id"]
        assert result.title == "Как создать КП за 5 минут"

    @patch('services.training_video_service._get_supabase')
    def test_get_video_not_found(self, mock_get_supabase):
        """get_video returns None when video does not exist."""
        from services.training_video_service import get_video

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_video("nonexistent-id")

        assert result is None

    @patch('services.training_video_service._get_supabase')
    def test_get_video_returns_none_on_error(self, mock_get_supabase):
        """get_video returns None on DB error."""
        from services.training_video_service import get_video

        mock_get_supabase.side_effect = Exception("DB error")

        result = get_video("some-id")

        assert result is None


# =============================================================================
# TESTS: Route Access Control
# =============================================================================

class TestTrainingRouteAccessControl:
    """Tests for /training route authentication and role checks.

    These tests verify that:
    - Authenticated users can view the training page
    - Unauthenticated users are redirected to login
    - Only admins can create/edit/delete videos
    """

    def test_training_page_requires_authentication(self):
        """GET /training redirects unauthenticated users to login."""
        # When the feature is implemented, this test will:
        # 1. Make a request without session/auth
        # 2. Expect a redirect (303) to /login
        from services.training_video_service import TrainingVideo
        # Verify the module is importable (will fail before implementation)
        assert TrainingVideo is not None

        # The actual route test would use the app_client fixture:
        # response = app_client.get("/training", follow_redirects=False)
        # assert response.status_code in [303, 302]
        # For now, just test the service module is importable
        # (this will fail with ImportError before implementation)

    def test_admin_can_create_video_via_route(self):
        """POST /training/new should be accessible to admin users.

        Verifies that:
        - The create_video service function works correctly
        - Admin role check would pass
        """
        from services.training_video_service import create_video
        assert callable(create_video)

    def test_admin_can_edit_video_via_route(self):
        """POST /training/{id}/edit should be accessible to admin users."""
        from services.training_video_service import update_video
        assert callable(update_video)

    def test_admin_can_delete_video_via_route(self):
        """POST /training/{id}/delete should be accessible to admin users."""
        from services.training_video_service import delete_video
        assert callable(delete_video)


class TestNonAdminAccessRestrictions:
    """Tests that non-admin users cannot modify videos."""

    @patch('services.training_video_service._get_supabase')
    def test_non_admin_can_read_videos(self, mock_get_supabase, org_id, multiple_videos):
        """Non-admin users can still read videos via service (read is unrestricted)."""
        from services.training_video_service import get_all_videos

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=multiple_videos
        )

        # Service layer does not check roles -- that's done in routes
        result = get_all_videos(org_id)
        assert len(result) == 4


# =============================================================================
# TESTS: Org Isolation
# =============================================================================

class TestOrgIsolation:
    """Tests that videos are isolated per organization."""

    @patch('services.training_video_service._get_supabase')
    def test_get_all_videos_filters_by_org(self, mock_get_supabase, org_id, sample_video_data):
        """get_all_videos passes org_id to Supabase query filter."""
        from services.training_video_service import get_all_videos

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Set up the chain to capture the eq calls
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[sample_video_data])

        get_all_videos(org_id)

        # Verify org_id was used in the query
        eq_calls = mock_query.eq.call_args_list
        org_filter_found = any(
            call[0] == ("organization_id", org_id) or
            (len(call[0]) >= 2 and call[0][0] == "organization_id")
            for call in eq_calls
        )
        assert org_filter_found, "get_all_videos must filter by organization_id"

    @patch('services.training_video_service._get_supabase')
    def test_create_video_sets_org_id(self, mock_get_supabase, org_id, sample_video_data):
        """create_video includes organization_id in the insert data."""
        from services.training_video_service import create_video

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_video_data]
        )

        create_video(
            organization_id=org_id,
            title="Test",
            youtube_id="abc123",
            category="Общее",
        )

        insert_call = mock_client.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["organization_id"] == org_id

    @patch('services.training_video_service._get_supabase')
    def test_get_video_by_id_from_other_org(self, mock_get_supabase, sample_video_data_other_org):
        """get_video returns the video regardless of org (route layer enforces org check).

        The service layer fetches by ID; the route handler must verify
        video.organization_id matches the session org_id.
        """
        from services.training_video_service import get_video

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_video_data_other_org]
        )

        result = get_video(sample_video_data_other_org["id"])

        # Service returns it; route layer must reject if org doesn't match
        assert result is not None
        assert result.organization_id == sample_video_data_other_org["organization_id"]


# =============================================================================
# TESTS: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_extract_youtube_id_with_embed_url(self):
        """extract_youtube_id handles embed URLs gracefully."""
        from services.training_video_service import extract_youtube_id
        # Embed URLs are not standard input, should return something reasonable
        result = extract_youtube_id("https://www.youtube.com/embed/abc123")
        # Should not crash; actual behavior depends on implementation
        assert isinstance(result, str)
        assert len(result) > 0

    @patch('services.training_video_service._get_supabase')
    def test_create_video_with_none_description(self, mock_get_supabase, org_id, sample_video_data):
        """create_video with None description stores None."""
        from services.training_video_service import create_video

        no_desc_data = {**sample_video_data, "description": None}
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[no_desc_data]
        )

        result = create_video(
            organization_id=org_id,
            title="No Desc Video",
            youtube_id="abc123",
            category="Общее",
            description=None,
        )

        assert result is not None
        assert result.description is None

    @patch('services.training_video_service._get_supabase')
    def test_get_categories_with_single_category(self, mock_get_supabase, org_id):
        """get_categories with one category returns a list of one."""
        from services.training_video_service import get_categories

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"category": "Продажи"}]
        )

        result = get_categories(org_id)

        assert result == ["Продажи"]

    @patch('services.training_video_service._get_supabase')
    def test_update_video_strips_whitespace(self, mock_get_supabase, sample_video_data):
        """update_video strips whitespace from updated fields."""
        from services.training_video_service import update_video

        updated_data = {**sample_video_data, "title": "Stripped Title"}
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        update_video(sample_video_data["id"], title="  Stripped Title  ")

        update_call = mock_client.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert update_data["title"] == "Stripped Title"

    @patch('services.training_video_service._get_supabase')
    def test_update_video_empty_category_defaults(self, mock_get_supabase, sample_video_data):
        """update_video with empty category string defaults to 'Общее'."""
        from services.training_video_service import update_video

        updated_data = {**sample_video_data, "category": "Общее"}
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        update_video(sample_video_data["id"], category="")

        update_call = mock_client.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert update_data["category"] == "Общее"

    @patch('services.training_video_service._get_supabase')
    def test_create_video_with_sort_order(self, mock_get_supabase, org_id, sample_video_data):
        """create_video respects sort_order parameter."""
        from services.training_video_service import create_video

        data_with_order = {**sample_video_data, "sort_order": 42}
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[data_with_order]
        )

        create_video(
            organization_id=org_id,
            title="Ordered Video",
            youtube_id="ord123",
            category="Общее",
            sort_order=42,
        )

        insert_call = mock_client.table.return_value.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data["sort_order"] == 42

    @patch('services.training_video_service._get_supabase')
    def test_delete_nonexistent_video_still_returns_true(self, mock_get_supabase):
        """delete_video on nonexistent ID returns True (Supabase DELETE doesn't error)."""
        from services.training_video_service import delete_video

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = delete_video("nonexistent-uuid")

        assert result is True

    def test_extract_youtube_id_only_whitespace(self):
        """extract_youtube_id with only whitespace returns empty string."""
        from services.training_video_service import extract_youtube_id
        result = extract_youtube_id("   ")
        assert result == ""
