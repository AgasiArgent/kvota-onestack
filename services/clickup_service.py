"""
ClickUp Integration Service for OneStack

Handles creating bug report tasks in ClickUp via REST API.
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
        "status": "Open",
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
