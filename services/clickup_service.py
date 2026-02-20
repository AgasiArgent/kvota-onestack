"""
ClickUp Integration Service for OneStack

Handles creating bug report tasks in ClickUp via REST API.
Supports bidirectional status sync between admin panel and ClickUp.
Uses httpx (available as supabase dependency) for HTTP calls.

Required env vars:
    CLICKUP_API_KEY     - ClickUp personal API key
    CLICKUP_BUG_LIST_ID - List ID for bug reports
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CLICKUP_API_KEY = os.getenv("CLICKUP_API_KEY", "")
CLICKUP_BUG_LIST_ID = os.getenv("CLICKUP_BUG_LIST_ID", "")
CLICKUP_BASE_URL = "https://api.clickup.com/api/v2"

FEEDBACK_TYPE_LABELS = {
    "bug": "Bug",
    "suggestion": "Suggestion",
    "question": "Question",
}

# Mapping: admin status → ClickUp status
ADMIN_TO_CLICKUP_STATUS = {
    "new": "to do",
    "in_progress": "in progress",
    "resolved": "complete",
    "closed": "complete",
}

# Mapping: ClickUp status → admin status
CLICKUP_TO_ADMIN_STATUS = {
    "to do": "new",
    "in progress": "in_progress",
    "testing": "in_progress",
    "complete": "resolved",
}


async def create_clickup_bug_task(
    short_id: str,
    feedback_type: str,
    description: str,
    user_name: str,
    user_email: str,
    org_name: str,
    page_url: str,
    debug_context: dict,
    admin_url: str,
    has_screenshot: bool = False,
) -> Optional[str]:
    """
    Create a ClickUp task for a bug report.

    Returns:
        ClickUp task ID (string) on success, None on failure or if not configured.
    """
    if not CLICKUP_API_KEY or not CLICKUP_BUG_LIST_ID:
        logger.info("ClickUp not configured (CLICKUP_API_KEY or CLICKUP_BUG_LIST_ID missing), skipping")
        return None

    type_label = FEEDBACK_TYPE_LABELS.get(feedback_type, feedback_type)
    # Title: "[Bug] First 60 chars of description #short_id"
    title_desc = description[:60] + ("..." if len(description) > 60 else "")
    task_name = f"[{type_label}] {title_desc} #{short_id}"

    # Build markdown description for ClickUp task
    context_md_lines = [
        f"**ID:** `{short_id}`",
        f"**Type:** {type_label}",
        f"**User:** {user_name} ({user_email})",
        f"**Organization:** {org_name or '---'}",
        f"**Page:** {page_url}",
        f"**Screenshot:** {'Yes' if has_screenshot else 'No'}",
        "",
        "**Description:**",
        description,
        "",
        f"**Admin view:** {admin_url}",
    ]

    if debug_context:
        context_md_lines.append("")
        context_md_lines.append("**Context:**")
        ua = debug_context.get("userAgent", "")
        browser = "Chrome" if "Chrome" in ua else "Firefox" if "Firefox" in ua else "Safari" if "Safari" in ua else "Other"
        context_md_lines.append(f"- Browser: {browser}")
        if debug_context.get("screenSize"):
            context_md_lines.append(f"- Screen: {debug_context['screenSize']}")
        errors = debug_context.get("consoleErrors", [])
        if errors:
            context_md_lines.append(f"- Console errors: {len(errors)}")
            for err in errors[:3]:
                context_md_lines.append(f"  - {str(err.get('message', ''))[:100]}")
        requests_data = debug_context.get("recentRequests", [])
        failed = [r for r in requests_data if isinstance(r.get("status"), int) and r.get("status", 0) >= 400]
        if failed:
            context_md_lines.append(f"- Failed requests: {len(failed)}")
            for req in failed[:3]:
                context_md_lines.append(f"  - {req.get('method')} {req.get('url')}: {req.get('status')}")

    task_description = "\n".join(context_md_lines)

    payload = {
        "name": task_name,
        "description": task_description,
        "status": "to do",
        "priority": 2 if feedback_type == "bug" else 3,
        "tags": [feedback_type],
    }

    headers = {
        "Authorization": CLICKUP_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{CLICKUP_BASE_URL}/list/{CLICKUP_BUG_LIST_ID}/task",
                json=payload,
                headers=headers,
            )
            if response.status_code in (200, 201):
                data = response.json()
                task_id = data.get("id")
                logger.info(f"ClickUp task created: {task_id} for feedback {short_id}")
                return task_id
            else:
                logger.error(f"ClickUp API error {response.status_code}: {response.text[:200]}")
                return None
    except Exception as e:
        logger.error(f"ClickUp request failed for {short_id}: {e}")
        return None


async def update_clickup_task_status(task_id: str, admin_status: str) -> bool:
    """
    Update a ClickUp task status when admin changes feedback status.

    Args:
        task_id: ClickUp task ID
        admin_status: OneStack admin status (new, in_progress, resolved, closed)

    Returns:
        True on success, False on failure or if not configured.
    """
    if not CLICKUP_API_KEY or not task_id:
        return False

    clickup_status = ADMIN_TO_CLICKUP_STATUS.get(admin_status)
    if not clickup_status:
        logger.warning(f"No ClickUp mapping for admin status '{admin_status}'")
        return False

    headers = {
        "Authorization": CLICKUP_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{CLICKUP_BASE_URL}/task/{task_id}",
                json={"status": clickup_status},
                headers=headers,
            )
            if response.status_code == 200:
                logger.info(f"ClickUp task {task_id} status updated to '{clickup_status}'")
                return True
            else:
                logger.error(f"ClickUp status update failed {response.status_code}: {response.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"ClickUp status update request failed for {task_id}: {e}")
        return False


async def get_clickup_task_status(task_id: str) -> Optional[str]:
    """
    Get current ClickUp task status and return mapped admin status.

    Returns:
        Admin status string or None if not configured/failed.
    """
    if not CLICKUP_API_KEY or not task_id:
        return None

    headers = {"Authorization": CLICKUP_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{CLICKUP_BASE_URL}/task/{task_id}",
                headers=headers,
            )
            if response.status_code == 200:
                data = response.json()
                clickup_status = data.get("status", {}).get("status", "").lower()
                admin_status = CLICKUP_TO_ADMIN_STATUS.get(clickup_status)
                return admin_status
            else:
                logger.error(f"ClickUp get task failed {response.status_code}: {response.text[:200]}")
                return None
    except Exception as e:
        logger.error(f"ClickUp get task request failed for {task_id}: {e}")
        return None
