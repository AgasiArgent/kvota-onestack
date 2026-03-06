"""
Tests for Changelog Service — user-facing changelog page with unread tracking.

Feature: [86afz31pe] Create changelog page with sidebar link

Tests cover:
- Module imports (changelog_service exists and exports expected symbols)
- _parse_entry() correctly parses a well-formed markdown file with YAML frontmatter
- get_all_entries() returns entries in reverse chronological order
- Malformed file: entry with missing `date` in frontmatter is skipped (returns None)
- Empty directory: get_all_entries() returns empty list when no .md files exist
- count_unread_entries() returns total count when user has no last_read record (fresh user)
- count_unread_entries() only counts entries after last_read_date (returning user)
- mark_as_read() calls supabase upsert correctly

TDD: These tests are written BEFORE implementation.
The changelog_service.py module does not exist yet -- tests should fail with ImportError.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, date, timedelta, timezone
from uuid import uuid4
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def user_id():
    """Current user ID for tests."""
    return str(uuid4())


@pytest.fixture
def sample_changelog_md():
    """Well-formed changelog markdown content with YAML frontmatter."""
    return """---
title: Новый модуль логистики
date: 2026-03-01
category: feature
---

Добавлен полноценный модуль управления логистикой.

- Назначение маршрутов
- Отслеживание расходов
- Интеграция с таможней
"""


@pytest.fixture
def sample_changelog_md_no_date():
    """Malformed changelog markdown: missing `date` in frontmatter."""
    return """---
title: Broken entry without date
category: bugfix
---

This entry has no date field and should be skipped.
"""


@pytest.fixture
def sample_changelog_md_no_frontmatter():
    """Markdown file without YAML frontmatter at all."""
    return """# Just a heading

No frontmatter here, just plain markdown.
"""


@pytest.fixture
def sample_changelog_md_2():
    """Second changelog entry, older date."""
    return """---
title: Исправления в закупках
date: 2026-02-15
category: bugfix
---

Исправлена ошибка при сохранении валюты поставщика.
"""


@pytest.fixture
def sample_changelog_md_3():
    """Third changelog entry, newest date."""
    return """---
title: Экспорт валютных счетов
date: 2026-03-05
category: feature
---

Теперь можно экспортировать реестр валютных счетов в Excel.
"""


@pytest.fixture
def changelog_dir_with_entries(tmp_path, sample_changelog_md, sample_changelog_md_2, sample_changelog_md_3):
    """Temp directory with 3 valid changelog markdown files."""
    d = tmp_path / "changelog"
    d.mkdir()

    (d / "2026-03-01-logistics.md").write_text(sample_changelog_md, encoding="utf-8")
    (d / "2026-02-15-procurement-fix.md").write_text(sample_changelog_md_2, encoding="utf-8")
    (d / "2026-03-05-export.md").write_text(sample_changelog_md_3, encoding="utf-8")

    return d


@pytest.fixture
def changelog_dir_with_malformed(tmp_path, sample_changelog_md, sample_changelog_md_no_date):
    """Temp directory with one valid and one malformed (no date) markdown file."""
    d = tmp_path / "changelog"
    d.mkdir()

    (d / "2026-03-01-good.md").write_text(sample_changelog_md, encoding="utf-8")
    (d / "2026-02-20-bad.md").write_text(sample_changelog_md_no_date, encoding="utf-8")

    return d


@pytest.fixture
def changelog_dir_empty(tmp_path):
    """Empty temp directory with no .md files."""
    d = tmp_path / "changelog"
    d.mkdir()
    return d


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client for changelog read-tracking tests."""
    client = MagicMock()
    return client


# =============================================================================
# IMPORT TESTS — verify module structure
# =============================================================================

class TestModuleImports:
    """Test that changelog_service module exists and exports expected symbols."""

    def test_import_changelog_service_module(self):
        """changelog_service module can be imported."""
        from services import changelog_service
        assert changelog_service is not None

    def test_import_parse_entry(self):
        """_parse_entry function is importable."""
        from services.changelog_service import _parse_entry
        assert callable(_parse_entry)

    def test_import_get_all_entries(self):
        """get_all_entries function is importable."""
        from services.changelog_service import get_all_entries
        assert callable(get_all_entries)

    def test_import_count_unread_entries(self):
        """count_unread_entries function is importable."""
        from services.changelog_service import count_unread_entries
        assert callable(count_unread_entries)

    def test_import_mark_as_read(self):
        """mark_as_read function is importable."""
        from services.changelog_service import mark_as_read
        assert callable(mark_as_read)


# =============================================================================
# PARSING TESTS — _parse_entry()
# =============================================================================

class TestParseEntry:
    """Test _parse_entry() correctly parses markdown files with YAML frontmatter."""

    def test_parse_well_formed_entry(self, tmp_path, sample_changelog_md):
        """_parse_entry() extracts title, date, category, and body from a valid markdown file."""
        from services.changelog_service import _parse_entry

        filepath = tmp_path / "2026-03-01-logistics.md"
        filepath.write_text(sample_changelog_md, encoding="utf-8")

        entry = _parse_entry(filepath)

        assert entry is not None
        assert entry["title"] == "Новый модуль логистики"
        # date can be a date object or a string — accept either, but it must represent 2026-03-01
        entry_date = entry["date"]
        if isinstance(entry_date, str):
            entry_date = date.fromisoformat(entry_date)
        assert entry_date == date(2026, 3, 1)
        assert entry["category"] == "feature"
        # Body should contain the markdown content after frontmatter
        assert "Назначение маршрутов" in entry["body"]
        assert "Интеграция с таможней" in entry["body"]

    def test_parse_entry_missing_date_returns_none(self, tmp_path, sample_changelog_md_no_date):
        """_parse_entry() returns None when frontmatter is missing the `date` field."""
        from services.changelog_service import _parse_entry

        filepath = tmp_path / "2026-02-20-bad.md"
        filepath.write_text(sample_changelog_md_no_date, encoding="utf-8")

        entry = _parse_entry(filepath)

        assert entry is None

    def test_parse_entry_no_frontmatter_returns_none(self, tmp_path, sample_changelog_md_no_frontmatter):
        """_parse_entry() returns None when file has no YAML frontmatter."""
        from services.changelog_service import _parse_entry

        filepath = tmp_path / "no-frontmatter.md"
        filepath.write_text(sample_changelog_md_no_frontmatter, encoding="utf-8")

        entry = _parse_entry(filepath)

        assert entry is None

    def test_parse_entry_includes_filename(self, tmp_path, sample_changelog_md):
        """_parse_entry() includes the source filename or slug in the result."""
        from services.changelog_service import _parse_entry

        filepath = tmp_path / "2026-03-01-logistics.md"
        filepath.write_text(sample_changelog_md, encoding="utf-8")

        entry = _parse_entry(filepath)

        assert entry is not None
        # The entry should contain some identifier — slug or filename
        has_identifier = "slug" in entry or "filename" in entry or "file" in entry
        assert has_identifier, "Entry should include a slug/filename identifier"

    def test_parse_entry_body_strips_frontmatter(self, tmp_path, sample_changelog_md):
        """_parse_entry() body does NOT contain frontmatter delimiters (---)."""
        from services.changelog_service import _parse_entry

        filepath = tmp_path / "2026-03-01-logistics.md"
        filepath.write_text(sample_changelog_md, encoding="utf-8")

        entry = _parse_entry(filepath)

        assert entry is not None
        # Body should not contain frontmatter markers
        assert not entry["body"].startswith("---")
        assert "title:" not in entry["body"]
        assert "category:" not in entry["body"]


# =============================================================================
# SORTING TESTS — get_all_entries()
# =============================================================================

class TestGetAllEntries:
    """Test get_all_entries() returns entries sorted in reverse chronological order."""

    def test_entries_sorted_reverse_chronological(self, changelog_dir_with_entries):
        """get_all_entries() returns newest entries first."""
        from services.changelog_service import get_all_entries

        entries = get_all_entries(str(changelog_dir_with_entries))

        assert len(entries) == 3

        # Convert dates to comparable format
        dates = []
        for e in entries:
            d = e["date"]
            if isinstance(d, str):
                d = date.fromisoformat(d)
            dates.append(d)

        # Should be: 2026-03-05, 2026-03-01, 2026-02-15
        assert dates[0] == date(2026, 3, 5), f"First entry should be newest, got {dates[0]}"
        assert dates[1] == date(2026, 3, 1), f"Second entry should be middle, got {dates[1]}"
        assert dates[2] == date(2026, 2, 15), f"Third entry should be oldest, got {dates[2]}"

    def test_entries_sorted_titles_match_dates(self, changelog_dir_with_entries):
        """Verify titles match the expected date ordering."""
        from services.changelog_service import get_all_entries

        entries = get_all_entries(str(changelog_dir_with_entries))

        assert entries[0]["title"] == "Экспорт валютных счетов"
        assert entries[1]["title"] == "Новый модуль логистики"
        assert entries[2]["title"] == "Исправления в закупках"

    def test_empty_directory_returns_empty_list(self, changelog_dir_empty):
        """get_all_entries() returns empty list when directory has no .md files."""
        from services.changelog_service import get_all_entries

        entries = get_all_entries(str(changelog_dir_empty))

        assert entries == []

    def test_malformed_entries_skipped(self, changelog_dir_with_malformed):
        """get_all_entries() skips entries where _parse_entry returns None (e.g., missing date)."""
        from services.changelog_service import get_all_entries

        entries = get_all_entries(str(changelog_dir_with_malformed))

        # Only the valid entry should be returned
        assert len(entries) == 1
        assert entries[0]["title"] == "Новый модуль логистики"

    def test_nonexistent_directory_returns_empty_list(self, tmp_path):
        """get_all_entries() returns empty list when directory does not exist."""
        from services.changelog_service import get_all_entries

        nonexistent = str(tmp_path / "does_not_exist")
        entries = get_all_entries(nonexistent)

        assert entries == []

    def test_directory_with_non_md_files_ignored(self, tmp_path):
        """get_all_entries() ignores non-.md files in the directory."""
        from services.changelog_service import get_all_entries

        d = tmp_path / "changelog"
        d.mkdir()
        (d / "readme.txt").write_text("not a changelog entry")
        (d / "notes.json").write_text('{"key": "value"}')
        (d / "image.png").write_bytes(b"\x89PNG")

        entries = get_all_entries(str(d))

        assert entries == []


# =============================================================================
# UNREAD COUNT TESTS — count_unread_entries()
# =============================================================================

class TestCountUnreadEntries:
    """Test count_unread_entries() with fresh and returning users."""

    def test_fresh_user_all_entries_unread(self, user_id, changelog_dir_with_entries):
        """Fresh user (no last_read record) sees all entries as unread."""
        from services.changelog_service import count_unread_entries

        # Mock Supabase: no read record for this user
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        with patch("services.changelog_service._get_supabase", return_value=mock_client):
            count = count_unread_entries(
                user_id=user_id,
                changelog_dir=str(changelog_dir_with_entries),
            )

        # All 3 entries should be unread
        assert count == 3

    def test_returning_user_only_new_entries_unread(self, user_id, changelog_dir_with_entries):
        """Returning user only sees entries after their last_read_date as unread."""
        from services.changelog_service import count_unread_entries

        # User last read on 2026-03-01 — so only 2026-03-05 entry is unread
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{
            "user_id": user_id,
            "last_read_date": "2026-03-01",
        }])

        with patch("services.changelog_service._get_supabase", return_value=mock_client):
            count = count_unread_entries(
                user_id=user_id,
                changelog_dir=str(changelog_dir_with_entries),
            )

        # Only the 2026-03-05 entry is after 2026-03-01
        assert count == 1

    def test_returning_user_all_read(self, user_id, changelog_dir_with_entries):
        """Returning user who has read up to the newest entry sees 0 unread."""
        from services.changelog_service import count_unread_entries

        # User last read on 2026-03-05 — all entries are at or before that
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{
            "user_id": user_id,
            "last_read_date": "2026-03-05",
        }])

        with patch("services.changelog_service._get_supabase", return_value=mock_client):
            count = count_unread_entries(
                user_id=user_id,
                changelog_dir=str(changelog_dir_with_entries),
            )

        assert count == 0

    def test_fresh_user_empty_changelog_returns_zero(self, user_id, changelog_dir_empty):
        """Fresh user with empty changelog directory sees 0 unread."""
        from services.changelog_service import count_unread_entries

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        with patch("services.changelog_service._get_supabase", return_value=mock_client):
            count = count_unread_entries(
                user_id=user_id,
                changelog_dir=str(changelog_dir_empty),
            )

        assert count == 0


# =============================================================================
# MARK AS READ TESTS — mark_as_read()
# =============================================================================

class TestMarkAsRead:
    """Test mark_as_read() upserts the read receipt in Supabase."""

    def test_mark_as_read_calls_upsert(self, user_id):
        """mark_as_read() calls supabase upsert with correct table and data."""
        from services.changelog_service import mark_as_read

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        with patch("services.changelog_service._get_supabase", return_value=mock_client):
            mark_as_read(user_id=user_id)

        # Should call table() with the changelog reads table
        mock_client.table.assert_called_once()
        table_name = mock_client.table.call_args[0][0]
        assert "changelog" in table_name.lower(), f"Expected changelog-related table, got '{table_name}'"

        # Should call upsert
        mock_table.upsert.assert_called_once()
        upsert_data = mock_table.upsert.call_args[0][0]
        assert upsert_data["user_id"] == user_id

        # Should execute the query
        mock_table.execute.assert_called_once()

    def test_mark_as_read_includes_current_date(self, user_id):
        """mark_as_read() sets last_read_date to today's date (or current timestamp)."""
        from services.changelog_service import mark_as_read

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        with patch("services.changelog_service._get_supabase", return_value=mock_client):
            mark_as_read(user_id=user_id)

        upsert_data = mock_table.upsert.call_args[0][0]

        # Should have some date/timestamp field
        date_field = upsert_data.get("last_read_date") or upsert_data.get("last_read_at")
        assert date_field is not None, "Upsert data must include a date/timestamp field"

        # The value should represent today (as string or date object)
        today_str = date.today().isoformat()
        if isinstance(date_field, (date, datetime)):
            assert date_field.isoformat().startswith(today_str)
        else:
            assert today_str in str(date_field), (
                f"Expected today's date ({today_str}) in upsert data, got '{date_field}'"
            )

    def test_mark_as_read_idempotent(self, user_id):
        """Calling mark_as_read() twice should call upsert twice (idempotent via DB upsert)."""
        from services.changelog_service import mark_as_read

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        with patch("services.changelog_service._get_supabase", return_value=mock_client):
            mark_as_read(user_id=user_id)
            mark_as_read(user_id=user_id)

        assert mock_table.upsert.call_count == 2
