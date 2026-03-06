"""
Changelog Service - Parse markdown changelog entries and track user read status.

This module provides functions for:
- Parsing changelog markdown files with YAML frontmatter
- Listing entries in reverse chronological order
- Tracking per-user read status via Supabase changelog_reads table
- Counting unread entries for sidebar badge display

Feature: [86afz31pe] Create changelog page with sidebar link
"""

import os
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import frontmatter
import markdown as md_lib

from services.database import get_supabase

logger = logging.getLogger(__name__)


def _get_supabase():
    """Internal wrapper for get_supabase — makes mocking easy in tests."""
    return get_supabase()


def _parse_entry(filepath) -> Optional[Dict[str, Any]]:
    """Parse a single changelog markdown file with YAML frontmatter.

    Args:
        filepath: Path to the markdown file (str or Path).

    Returns:
        Dict with keys: title, date, category, body, slug
        or None if the file is malformed (missing date, no frontmatter, etc.)
    """
    filepath = Path(filepath)
    try:
        post = frontmatter.load(str(filepath))
    except Exception:
        logger.warning("Failed to parse frontmatter from %s", filepath)
        return None

    # Must have a date field in frontmatter
    entry_date = post.metadata.get("date")
    if entry_date is None:
        return None

    # Must have a title
    title = post.metadata.get("title")
    if title is None:
        return None

    # Normalize date to a date object
    if isinstance(entry_date, datetime):
        entry_date = entry_date.date()
    elif isinstance(entry_date, str):
        try:
            entry_date = date.fromisoformat(entry_date)
        except ValueError:
            logger.warning("Invalid date format in %s: %s", filepath, entry_date)
            return None
    elif not isinstance(entry_date, date):
        return None

    category = post.metadata.get("category", "update")
    version = post.metadata.get("version")
    body = post.content  # frontmatter library strips the YAML header

    # Generate slug from filename (without extension)
    slug = filepath.stem

    result = {
        "title": title,
        "date": entry_date,
        "category": category,
        "body": body,
        "slug": slug,
    }
    if version:
        result["version"] = version
    return result


def get_all_entries(changelog_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load and return all valid changelog entries, sorted newest-first.

    Args:
        changelog_dir: Path to the directory containing .md changelog files.
                      Defaults to the `changelog/` directory next to main.py.

    Returns:
        List of parsed entry dicts, sorted by date descending.
    """
    if changelog_dir is None:
        # Default: <project_root>/changelog/
        changelog_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "changelog"
        )

    dir_path = Path(changelog_dir)
    if not dir_path.exists() or not dir_path.is_dir():
        return []

    entries = []
    for md_file in dir_path.glob("*.md"):
        entry = _parse_entry(md_file)
        if entry is not None:
            entries.append(entry)

    # Sort by date descending (newest first)
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def get_user_last_read(user_id: str) -> Optional[date]:
    """Fetch the last-read date for a user from changelog_reads table.

    Args:
        user_id: UUID string of the user.

    Returns:
        date object of last read, or None if no record exists.
    """
    client = _get_supabase()
    result = (
        client.table("changelog_reads")
        .select("last_read_date")
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        return None

    raw = result.data[0].get("last_read_date")
    if raw is None:
        return None

    if isinstance(raw, date):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    return None


def count_unread_entries(
    user_id: str,
    changelog_dir: Optional[str] = None,
) -> int:
    """Count how many changelog entries are unread for a given user.

    Args:
        user_id: UUID string of the user.
        changelog_dir: Path to changelog directory (optional).

    Returns:
        Number of unread entries.
    """
    entries = get_all_entries(changelog_dir)
    if not entries:
        return 0

    last_read = get_user_last_read(user_id)
    if last_read is None:
        # Fresh user — all entries are unread
        return len(entries)

    # Count entries strictly after last_read_date
    return sum(1 for entry in entries if entry["date"] > last_read)


def mark_as_read(user_id: str) -> None:
    """Mark all changelog entries as read for the given user.

    Upserts a record in changelog_reads with today's date.

    Args:
        user_id: UUID string of the user.
    """
    client = _get_supabase()
    today = date.today().isoformat()

    client.table("changelog_reads").upsert(
        {
            "user_id": user_id,
            "last_read_date": today,
        }
    ).execute()


def render_entry_html(entry: Dict[str, Any]) -> str:
    """Render a changelog entry's markdown body to HTML.

    NOTE: Output is not sanitized. Changelog files are trusted admin-authored
    content from the filesystem only. Do NOT use for user-supplied markdown.

    Args:
        entry: Parsed changelog entry dict.

    Returns:
        HTML string of the rendered body.
    """
    return md_lib.markdown(entry["body"], extensions=["extra"])


# Russian month names for date formatting
RUSSIAN_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def format_date_russian_human(d: date) -> str:
    """Format a date in human-readable Russian: '6 марта 2026'.

    Note: Distinct from export_data_mapper.format_date_russian() which produces DD.MM.YYYY.
    """
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{d.day} {RUSSIAN_MONTHS[d.month]} {d.year}"
