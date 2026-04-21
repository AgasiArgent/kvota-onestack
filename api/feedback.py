"""Feedback API — user-submitted feedback (bug reports, feature requests).

Handler module (not router). Registered via thin wrappers in
api/routers/feedback.py (public submit) and api/routers/integrations.py
(internal status updater).

Body: JSON only. The legacy FastHTML form-encoded + HTMX response path was
dropped in the Phase 6C-4 cleanup (2026-04-21) — the only live caller is
Next.js, which sends JSON.

Side effects (all best-effort, swallowed on failure):
    - Persist row in kvota.user_feedback.
    - Create a ClickUp bug task and stash its id on the feedback row.
    - Post a Telegram admin notification (with optional screenshot).
"""

from __future__ import annotations

import json as json_lib
import logging
import os
import uuid
from datetime import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse

from services.clickup_service import create_clickup_bug_task
from services.database import get_supabase
from services.telegram_service import send_admin_bug_report_with_photo

logger = logging.getLogger(__name__)

# Shared secret for internal CLI/admin tooling (e.g., /fix-bugs).
# Empty string disables the endpoint (always 401) — must be set in prod.
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def _generate_short_id() -> str:
    """Generate short ID: FB-YYMMDD-HHMMSS-xxxx (random hex suffix for uniqueness)."""
    now = datetime.now()
    suffix = uuid.uuid4().hex[:4]
    return f"FB-{now.strftime('%y%m%d')}-{now.strftime('%H%M%S')}-{suffix}"


async def submit_feedback(request: Request) -> JSONResponse:
    """Accept user feedback and fan out to ClickUp + Telegram admins.

    Path: POST /api/feedback
    Auth: JWT (Next.js). Session fallback retained for future internal tools
        that may call this endpoint from a browser with SessionMiddleware in
        scope; no such caller exists today.
    Body: JSON with fields:
        feedback_type: str (default "bug")
        description: str (required, non-empty)
        page_url, page_title: str — originating page
        debug_context: JSON string or dict — runtime context snapshot
        screenshot: str — base64 data URI (prefix stripped before storage)
        screenshot_url: str — Supabase Storage URL (validated against
            SUPABASE_URL / PUBLIC_SUPABASE_URL prefixes to reject injection)
    Returns:
        {success, data: {short_id}} on success, standard error envelope otherwise.
    Side Effects:
        - INSERT kvota.user_feedback (retries on short_id collision)
        - Optional ClickUp bug task creation + clickup_task_id backfill
        - Optional Telegram admin notification (best-effort, logged on fail)
    Roles: authenticated. Anonymous requests are rejected with 401.
    """
    api_user = getattr(request.state, "api_user", None)
    if api_user:
        user_meta = api_user.user_metadata or {}
        org_id = user_meta.get("org_id")
        if not org_id:
            try:
                sb = get_supabase()
                om = (
                    sb.table("organization_members")
                    .select("organization_id")
                    .eq("user_id", str(api_user.id))
                    .eq("status", "active")
                    .order("created_at")
                    .limit(1)
                    .execute()
                )
                if om.data:
                    org_id = om.data[0]["organization_id"]
            except Exception:
                pass
        user = {
            "id": str(api_user.id),
            "email": api_user.email or "",
            "name": user_meta.get("name", api_user.email or ""),
            "org_id": org_id,
            "org_name": user_meta.get("org_name", ""),
        }
    else:
        try:
            session = request.session
        except (AssertionError, AttributeError):
            session = None
        user = (session or {}).get("user", {}) if session else {}

    if not user or not user.get("id"):
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required",
                },
            },
            status_code=401,
        )

    body = await request.json()

    feedback_type = body.get("feedback_type", "bug")
    description = body.get("description", "").strip()
    page_url = body.get("page_url", "")
    page_title = body.get("page_title", "")
    debug_context_str = body.get("debug_context", "{}")
    screenshot_data = (
        body.get("screenshot", "").strip() if body.get("screenshot") else ""
    )
    screenshot_url_raw = (
        body.get("screenshot_url", "").strip()
        if body.get("screenshot_url")
        else ""
    )
    # Validate screenshot_url is a Supabase Storage URL (prevent arbitrary URL injection)
    supabase_url = os.getenv("SUPABASE_URL", "")
    public_supabase_url = os.getenv("PUBLIC_SUPABASE_URL", supabase_url)
    screenshot_url = ""
    if screenshot_url_raw and (
        screenshot_url_raw.startswith(f"{supabase_url}/storage/")
        or screenshot_url_raw.startswith(f"{public_supabase_url}/storage/")
    ):
        screenshot_url = screenshot_url_raw

    if not description:
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Description required",
                },
            },
            status_code=400,
        )

    try:
        debug_context = (
            json_lib.loads(debug_context_str)
            if isinstance(debug_context_str, str)
            else debug_context_str
        )
    except Exception:
        debug_context = {}

    short_id = _generate_short_id()
    supabase = get_supabase()

    # Strip data URI prefix for base64 storage
    screenshot_b64 = None
    if screenshot_data and screenshot_data.startswith("data:image"):
        screenshot_b64 = (
            screenshot_data.split(",", 1)[1] if "," in screenshot_data else None
        )

    try:
        org_id = user.get("org_id")
        try:
            if org_id:
                org_check = (
                    supabase.table("organizations")
                    .select("id")
                    .eq("id", org_id)
                    .limit(1)
                    .execute()
                )
                if not org_check.data:
                    org_id = None
        except Exception:
            pass

        insert_payload = {
            "short_id": short_id,
            "user_id": user.get("id"),
            "user_email": user.get("email"),
            "user_name": user.get("name", user.get("email", "Неизвестный")),
            "organization_id": org_id,
            "organization_name": user.get("org_name", ""),
            "page_url": page_url,
            "page_title": page_title,
            "user_agent": request.headers.get("user-agent", ""),
            "feedback_type": feedback_type,
            "description": description,
            "debug_context": debug_context,
        }
        if screenshot_b64:
            insert_payload["screenshot_data"] = screenshot_b64
        if screenshot_url:
            insert_payload["screenshot_url"] = screenshot_url

        # Retry with new short_id on UNIQUE constraint violation
        for attempt in range(3):
            try:
                supabase.table("user_feedback").insert(insert_payload).execute()
                break
            except Exception as insert_err:
                if "duplicate" in str(insert_err).lower() and attempt < 2:
                    short_id = _generate_short_id()
                    insert_payload["short_id"] = short_id
                    continue
                raise

        # ClickUp task (best-effort)
        clickup_task_id = None
        try:
            admin_url = (
                f"{os.getenv('APP_BASE_URL', 'https://kvotaflow.ru')}"
                f"/admin/feedback/{short_id}"
            )
            clickup_task_id = await create_clickup_bug_task(
                short_id=short_id,
                feedback_type=feedback_type,
                description=description,
                user_name=user.get("name", user.get("email", "Неизвестный")),
                user_email=user.get("email", ""),
                org_name=user.get("org_name", ""),
                page_url=page_url,
                debug_context=debug_context,
                admin_url=admin_url,
                has_screenshot=bool(screenshot_b64 or screenshot_url),
            )
            if clickup_task_id:
                supabase.table("user_feedback").update(
                    {"clickup_task_id": clickup_task_id}
                ).eq("short_id", short_id).execute()
        except Exception as e:
            logger.warning(f"ClickUp task creation failed for {short_id}: {e}")

        # Telegram notification (best-effort)
        try:
            clickup_url = (
                f"https://app.clickup.com/t/{clickup_task_id}"
                if clickup_task_id
                else None
            )
            await send_admin_bug_report_with_photo(
                short_id=short_id,
                user_name=user.get("name", user.get("email", "Неизвестный")),
                user_email=user.get("email", ""),
                org_name=user.get("org_name", ""),
                page_url=page_url,
                feedback_type=feedback_type,
                description=description,
                debug_context=debug_context,
                screenshot_b64=screenshot_b64,
                screenshot_url=screenshot_url,
                clickup_url=clickup_url,
            )
        except Exception as e:
            logger.warning(f"Telegram notification failed for {short_id}: {e}")

        return JSONResponse(
            {"success": True, "data": {"short_id": short_id}}
        )

    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to save feedback",
                },
            },
            status_code=500,
        )


async def update_feedback_status(
    request: Request, short_id: str
) -> JSONResponse:
    """Internal API to update feedback status with notifications.

    Path: POST /api/internal/feedback/{short_id}/status
    Auth: X-Internal-Key header (shared secret, not JWT/session). Empty or
        mismatching key → 401. Used by CLI workflows (e.g., /fix-bugs) to
        ensure Telegram notifications fire when resolving feedback via
        automation.
    Query: status=resolved (default) | dismissed | ...
    Returns:
        JSON {success, message, telegram_notified, clickup_synced}.
        200 on success, 400 on business failure, 401 on auth failure.
    Side Effects:
        - UPDATE kvota.user_feedback.status (via feedback_service).
        - Optional Telegram notification to feedback author.
        - Optional ClickUp task status sync.
    Roles: internal (X-Internal-Key holders only).

    Usage:
        curl -X POST 'https://kvotaflow.ru/api/internal/feedback/FB-XXX/status?status=resolved' \\
             -H 'X-Internal-Key: <key>'
    """
    auth_key = request.headers.get("x-internal-key", "")
    if not INTERNAL_API_KEY or auth_key != INTERNAL_API_KEY:
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=401
        )

    status = request.query_params.get("status", "resolved")

    from services.feedback_service import (  # lazy import: avoid boot cost
        update_feedback_status as _svc_update_feedback_status,
    )

    result = await _svc_update_feedback_status(short_id, status)

    return JSONResponse(
        {
            "success": result.success,
            "message": result.message,
            "telegram_notified": result.telegram_notified,
            "clickup_synced": result.clickup_synced,
        },
        status_code=200 if result.success else 400,
    )
