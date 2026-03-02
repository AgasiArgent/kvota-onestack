"""
Comment Service - CRUD operations for kvota.quote_comments table (Quote Chat)

Provides:
- get_comments_for_quote() -- fetch comments with author names, ordered ASC
- create_comment() -- insert a new comment with optional @mentions
- get_unread_count() -- count unread comments for a user on a quote
- mark_as_read() -- upsert read receipt for user+quote
- get_org_users_for_mentions() -- list org members for @mention dropdown
"""

from datetime import datetime, timezone
from typing import Optional, List
import logging

from services.database import get_supabase


logger = logging.getLogger(__name__)


def _get_supabase():
    """Get Supabase client. Wrapped for testability (tests mock this function)."""
    return get_supabase()


def get_comments_for_quote(quote_id: str) -> list:
    """
    Fetch all comments for a quote, ordered by created_at ASC (oldest first).

    Enriches with author_name from user_profiles (separate query, no FK join needed).

    Args:
        quote_id: UUID of the quote

    Returns:
        List of comment dicts with author_name enriched
    """
    client = _get_supabase()

    result = client.table("quote_comments") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at", desc=False) \
        .execute()

    comments = result.data or []
    if not comments:
        return comments

    # Collect unique user_ids to batch-fetch profiles
    user_ids = list({c.get("user_id") for c in comments if c.get("user_id")})

    # Fetch profiles for all comment authors in one query
    profiles_map = {}
    if user_ids:
        profiles_result = client.table("user_profiles") \
            .select("user_id, full_name") \
            .in_("user_id", user_ids) \
            .execute()
        for p in (profiles_result.data or []):
            profiles_map[p.get("user_id")] = p.get("full_name")

    # Enrich each comment with author_name
    for comment in comments:
        uid = comment.get("user_id", "")
        comment["author_name"] = profiles_map.get(uid) or (uid[:8] if uid else "Unknown")

    return comments


def create_comment(
    quote_id: str,
    user_id: str,
    body: str,
    mentions: Optional[List[str]] = None,
) -> dict:
    """
    Insert a new comment into quote_comments.

    Args:
        quote_id: UUID of the quote
        user_id: UUID of the comment author
        body: Comment text body
        mentions: Optional list of mentioned user UUIDs

    Returns:
        Created comment row dict with id and created_at
    """
    # Normalize mentions to a list
    if mentions is None:
        mentions = []
    elif not isinstance(mentions, list):
        mentions = list(mentions) if hasattr(mentions, '__iter__') and not isinstance(mentions, str) else []

    client = _get_supabase()

    result = client.table("quote_comments") \
        .insert({
            "quote_id": quote_id,
            "user_id": user_id,
            "body": body,
            "mentions": mentions,
        }) \
        .execute()

    data = result.data or []
    return data[0] if data else {}


def get_unread_count(quote_id: str, user_id: str) -> int:
    """
    Count unread comments for a user on a given quote.

    If the user has a read receipt, counts comments after last_read_at.
    If no read receipt exists, returns total comment count (all unread).

    Args:
        quote_id: UUID of the quote
        user_id: UUID of the user

    Returns:
        Integer count of unread comments (always >= 0)
    """
    client = _get_supabase()

    # Step 1: Look up the read receipt
    reads_result = client.table("quote_comment_reads") \
        .select("last_read_at") \
        .eq("quote_id", quote_id) \
        .eq("user_id", user_id) \
        .execute()

    reads_data = reads_result.data or []

    if reads_data:
        # User has a read receipt -- count comments after last_read_at
        last_read_at = reads_data[0].get("last_read_at", "")
        comments_result = client.table("quote_comments") \
            .select("id") \
            .eq("quote_id", quote_id) \
            .gt("created_at", last_read_at) \
            .execute()
        return len(comments_result.data or [])
    else:
        # No read receipt -- all comments are unread
        comments_result = client.table("quote_comments") \
            .select("id") \
            .eq("quote_id", quote_id) \
            .execute()
        return len(comments_result.data or [])


def mark_as_read(quote_id: str, user_id: str) -> None:
    """
    Upsert a read receipt for user+quote into quote_comment_reads.

    Sets last_read_at to current UTC timestamp. Idempotent via upsert.

    Args:
        quote_id: UUID of the quote
        user_id: UUID of the user
    """
    client = _get_supabase()

    now_iso = datetime.now(timezone.utc).isoformat()

    client.table("quote_comment_reads") \
        .upsert({
            "quote_id": quote_id,
            "user_id": user_id,
            "last_read_at": now_iso,
        }) \
        .execute()

    return None


def get_org_users_for_mentions(org_id: str) -> list:
    """
    Get list of organization members for @mention dropdown.

    Queries user_profiles which has organization_id and full_name.

    Args:
        org_id: UUID of the organization

    Returns:
        List of dicts with user_id and full_name
    """
    client = _get_supabase()

    result = client.table("user_profiles") \
        .select("user_id, full_name") \
        .eq("organization_id", org_id) \
        .execute()

    return result.data or []
