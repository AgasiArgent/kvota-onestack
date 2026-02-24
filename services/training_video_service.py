"""
Training Video Service - CRUD operations for training_videos table

This module provides functions for managing training videos (Rutube, YouTube, Loom)
organized by categories. Used for the internal knowledge base at /training.

Features:
- Multi-platform URL parsing (auto-detect Rutube, YouTube from URL)
- CRUD operations for training videos
- Category listing with deduplication
- Organization-scoped queries
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import logging
import os
from urllib.parse import urlparse, parse_qs

from supabase import create_client, ClientOptions


logger = logging.getLogger(__name__)

# Initialize Supabase client with service role for admin operations
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _get_supabase():
    """Get Supabase client with service role key for admin operations - kvota schema."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY,
        options=ClientOptions(schema="kvota")
    )


@dataclass
class TrainingVideo:
    """
    Represents a training video record.

    Stores video embed information with category organization.
    Supports multiple platforms: Rutube, YouTube.
    Maps to training_videos table in database.
    """
    id: str
    organization_id: str
    title: str
    youtube_id: str
    category: str
    sort_order: int
    is_active: bool

    # Optional fields
    platform: str = "rutube"
    description: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _parse_video(data: dict) -> TrainingVideo:
    """Parse database row into TrainingVideo object."""
    return TrainingVideo(
        id=data["id"],
        organization_id=data["organization_id"],
        title=data["title"],
        youtube_id=data["youtube_id"],
        category=data.get("category", "Общее") or "Общее",
        sort_order=data.get("sort_order", 0) or 0,
        is_active=data.get("is_active", True) if data.get("is_active") is not None else True,
        platform=data.get("platform", "rutube"),
        description=data.get("description"),
        created_by=data.get("created_by"),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
    )


def extract_video_info(url_or_id: str) -> dict:
    """Auto-detect platform and extract video ID from URL.

    Returns: {"video_id": str, "platform": str}

    Supported:
    - Rutube: https://rutube.ru/video/HASH/ -> platform='rutube', video_id=HASH
    - YouTube: https://www.youtube.com/watch?v=ID -> platform='youtube', video_id=ID
    - YouTube short: https://youtu.be/ID -> platform='youtube', video_id=ID
    - YouTube embed: https://www.youtube.com/embed/ID -> platform='youtube', video_id=ID
    - Raw ID (default): assumes 'rutube' platform

    Args:
        url_or_id: Video URL or raw video ID

    Returns:
        Dict with 'video_id' and 'platform' keys.
        Returns empty video_id if input is empty/whitespace.
    """
    if not url_or_id:
        return {"video_id": "", "platform": "rutube"}

    s = url_or_id.strip()
    if not s:
        return {"video_id": "", "platform": "rutube"}

    # Rutube: /video/{hash} or /play/embed/{hash}
    if "rutube.ru" in s:
        parsed = urlparse(s)
        path_parts = parsed.path.rstrip("/").split("/")
        # /video/{hash}
        if len(path_parts) >= 3 and path_parts[1] == "video":
            return {"video_id": path_parts[2], "platform": "rutube"}
        # /play/embed/{hash}
        if len(path_parts) >= 4 and path_parts[1] == "play" and path_parts[2] == "embed":
            return {"video_id": path_parts[3], "platform": "rutube"}
        # Fallback: last path segment
        video_id = path_parts[-1] if path_parts else s
        return {"video_id": video_id, "platform": "rutube"}

    # YouTube - try to parse as URL
    try:
        parsed = urlparse(s)

        # Standard YouTube URL: youtube.com/watch?v=ID
        if parsed.hostname and "youtube.com" in parsed.hostname:
            if parsed.path == "/watch":
                qs = parse_qs(parsed.query)
                if "v" in qs:
                    return {"video_id": qs["v"][0], "platform": "youtube"}
            # Embed URL: youtube.com/embed/ID
            if parsed.path.startswith("/embed/"):
                video_id = parsed.path.split("/embed/")[1]
                if video_id:
                    return {"video_id": video_id.split("?")[0].split("/")[0], "platform": "youtube"}

        # Short URL: youtu.be/ID
        if parsed.hostname and "youtu.be" in parsed.hostname:
            video_id = parsed.path.lstrip("/")
            if video_id:
                return {"video_id": video_id.split("?")[0].split("/")[0], "platform": "youtube"}
    except Exception:
        pass

    # Raw ID - default to rutube (primary platform for Russian users)
    return {"video_id": s, "platform": "rutube"}


def extract_youtube_id(url_or_id: str) -> str:
    """Legacy wrapper - returns just the video ID.

    Kept for backward compatibility. Use extract_video_info() for new code.

    Supports:
    - Full URLs: https://www.youtube.com/watch?v=abc123
    - Short URLs: https://youtu.be/abc123
    - Embed URLs: https://www.youtube.com/embed/abc123
    - Rutube URLs: https://rutube.ru/video/HASH/
    - Raw IDs: abc123

    Args:
        url_or_id: Video URL or raw video ID

    Returns:
        Extracted video ID string, or empty string if input is empty/whitespace
    """
    return extract_video_info(url_or_id)["video_id"]


def get_all_videos(org_id: str, category: str = None) -> list:
    """Get all active training videos for an organization.

    Args:
        org_id: Organization ID
        category: Optional category filter

    Returns:
        List of TrainingVideo objects, ordered by sort_order then created_at.
        Returns empty list on error.
    """
    try:
        client = _get_supabase()
        query = (
            client.table("training_videos")
            .select("*")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .order("sort_order")
            .order("created_at")
        )

        if category:
            query = query.eq("category", category)

        response = query.execute()
        data = response.data
        if not data:
            return []
        return [_parse_video(row) for row in data]
    except Exception as e:
        logger.error(f"Error fetching training videos: {e}")
        return []


def get_video(video_id: str) -> Optional[TrainingVideo]:
    """Get a single training video by ID.

    Args:
        video_id: Video UUID

    Returns:
        TrainingVideo object or None if not found/error
    """
    try:
        client = _get_supabase()
        response = (
            client.table("training_videos")
            .select("*")
            .eq("id", video_id)
            .execute()
        )
        if response.data:
            return _parse_video(response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error fetching training video {video_id}: {e}")
        return None


def get_categories(org_id: str) -> list:
    """Get sorted unique category names for an organization.

    Args:
        org_id: Organization ID

    Returns:
        Sorted list of unique category strings. Empty list on error.
    """
    try:
        client = _get_supabase()
        response = (
            client.table("training_videos")
            .select("category")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .execute()
        )
        data = response.data
        if not data:
            return []
        categories = sorted(set(row["category"] for row in data if row.get("category")))
        return categories
    except Exception as e:
        logger.error(f"Error fetching training video categories: {e}")
        return []


def create_video(
    organization_id: str,
    title: str,
    youtube_id: str,
    category: str = "Общее",
    description: str = None,
    created_by: str = None,
    sort_order: int = 0,
    platform: str = "rutube",
) -> Optional[TrainingVideo]:
    """Create a new training video.

    Args:
        organization_id: Organization ID
        title: Video title
        youtube_id: Video ID (extracted from URL)
        category: Video category (default: "Общее")
        description: Optional description
        created_by: User ID who created the video
        sort_order: Sort order within category (default: 0)
        platform: Video platform - 'rutube', 'youtube' (default: 'rutube')

    Returns:
        Created TrainingVideo object or None on error
    """
    try:
        client = _get_supabase()

        # Clean inputs
        title = title.strip() if title else title
        youtube_id = extract_youtube_id(youtube_id) if youtube_id else youtube_id
        category = category.strip() if category else ""
        if not category:
            category = "Общее"

        insert_data = {
            "organization_id": organization_id,
            "title": title,
            "youtube_id": youtube_id,
            "category": category,
            "sort_order": sort_order,
            "is_active": True,
            "platform": platform,
        }

        if description is not None:
            insert_data["description"] = description

        if created_by:
            insert_data["created_by"] = created_by

        response = client.table("training_videos").insert(insert_data).execute()
        if response.data:
            return _parse_video(response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error creating training video: {e}")
        return None


def update_video(
    video_id: str,
    title: str = None,
    youtube_id: str = None,
    category: str = None,
    description: str = None,
    sort_order: int = None,
    is_active: bool = None,
    platform: str = None,
) -> Optional[TrainingVideo]:
    """Update an existing training video.

    Only provided (non-None) fields are updated.
    If no fields are provided, returns the current video unchanged.

    Args:
        video_id: Video UUID
        title: New title (optional)
        youtube_id: New video ID or URL (optional)
        category: New category (optional)
        description: New description (optional)
        sort_order: New sort order (optional)
        is_active: New active status (optional)
        platform: New platform - 'rutube', 'youtube' (optional)

    Returns:
        Updated TrainingVideo object or None on error
    """
    try:
        update_data = {}

        if title is not None:
            update_data["title"] = title.strip()

        if youtube_id is not None:
            update_data["youtube_id"] = extract_youtube_id(youtube_id)

        if category is not None:
            cat = category.strip() if category else ""
            update_data["category"] = cat if cat else "Общее"

        if description is not None:
            update_data["description"] = description

        if sort_order is not None:
            update_data["sort_order"] = sort_order

        if is_active is not None:
            update_data["is_active"] = is_active

        if platform is not None:
            update_data["platform"] = platform

        # If nothing to update, return current video
        if not update_data:
            return get_video(video_id)

        client = _get_supabase()
        response = (
            client.table("training_videos")
            .update(update_data)
            .eq("id", video_id)
            .execute()
        )
        if response.data:
            return _parse_video(response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating training video {video_id}: {e}")
        return None


def delete_video(video_id: str) -> bool:
    """Delete a training video.

    Args:
        video_id: Video UUID

    Returns:
        True on success, False on error
    """
    try:
        client = _get_supabase()
        client.table("training_videos").delete().eq("id", video_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting training video {video_id}: {e}")
        return False
