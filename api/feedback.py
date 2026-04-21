"""Feedback API — user-submitted feedback (bug reports, feature requests).

Handler module (not router). Registered via thin wrappers in
api/routers/feedback.py (public submit) and api/routers/integrations.py
(internal status updater). Moved verbatim from main.py
@rt("/api/feedback") in Phase 6B-7 and
@rt("/api/internal/feedback/{short_id}/status") in Phase 6B-8.

Supports dual body shapes on submit:
    - JSON (Next.js): application/json body → JSON response.
    - Form (legacy FastHTML): application/x-www-form-urlencoded → HTML response
      (the HTMX-triggered modal expects a ``Div(...)`` snippet).

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
from starlette.responses import HTMLResponse, JSONResponse

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


def _render_error_html(message: str, hint: str | None = None) -> HTMLResponse:
    """Render a legacy FastHTML error response for form submissions.

    The feedback modal uses HTMX to swap the response into ``#feedback-result``;
    the DOM shape returned here mirrors the original @rt handler so no
    frontend code needs to change.
    """
    from fasthtml.common import Div, P
    from api.ui_helpers import btn

    if hint is None:
        return HTMLResponse(str(Div(message, cls="text-error mt-2")))

    return HTMLResponse(
        str(
            Div(
                Div(message, cls="text-error font-medium"),
                P(hint, cls="text-sm text-gray-500 mt-1"),
                btn(
                    "Попробовать снова",
                    variant="secondary",
                    size="sm",
                    onclick="document.getElementById('feedback-result').innerHTML=''",
                    type="button",
                    cls="mt-2",
                ),
                cls="mt-2",
            )
        )
    )


def _render_success_html(short_id: str) -> HTMLResponse:
    """Render the legacy FastHTML success response for form submissions."""
    from fasthtml.common import Div, P
    from api.ui_helpers import btn

    return HTMLResponse(
        str(
            Div(
                Div(id="feedback-success-marker", style="display:none"),
                Div("Спасибо за обратную связь!", cls="text-success font-medium"),
                P(
                    f"Номер обращения: {short_id}",
                    cls="text-sm text-gray-500 mt-1 font-mono",
                ),
                btn(
                    "Закрыть",
                    variant="secondary",
                    size="sm",
                    onclick="closeFeedbackModal()",
                    type="button",
                ),
            )
        )
    )


async def submit_feedback(request: Request) -> JSONResponse | HTMLResponse:
    """Accept user feedback and fan out to ClickUp + Telegram admins.

    Path: POST /api/feedback
    Auth: dual — JWT (Next.js) first, then legacy session (FastHTML).
    Body: JSON (Next.js) OR form-encoded (FastHTML). Shared fields:
        feedback_type: str (default "bug")
        description: str (required, non-empty)
        page_url, page_title: str — originating page
        debug_context: JSON string or dict — runtime context snapshot
        screenshot: str — base64 data URI (prefix stripped before storage)
        screenshot_url: str — Supabase Storage URL (validated against
            SUPABASE_URL / PUBLIC_SUPABASE_URL prefixes to reject injection)
    Returns:
        JSON path → {success, data: {short_id}} or error envelope.
        Form path → an HTML fragment swapped into the feedback modal.
    Side Effects:
        - INSERT kvota.user_feedback (retries on short_id collision)
        - Optional ClickUp bug task creation + clickup_task_id backfill
        - Optional Telegram admin notification (best-effort, logged on fail)
    Roles: authenticated (JWT or session). Anonymous requests are rejected
        with 401 (JSON) or an HTML error snippet (form).
    """
    # Dual auth: JWT (Next.js) or session (FastHTML)
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

    # Reject unauthenticated requests (neither JWT nor session)
    if not user or not user.get("id"):
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
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
        return _render_error_html("Требуется авторизация")

    # Dual input: JSON (Next.js) or form (FastHTML)
    content_type = request.headers.get("content-type", "")
    is_json = "application/json" in content_type
    if is_json:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

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
        if is_json:
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
        return _render_error_html("Пожалуйста, опишите проблему")

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

        # Dual response: JSON (Next.js) or HTML (FastHTML)
        if is_json:
            return JSONResponse(
                {"success": True, "data": {"short_id": short_id}}
            )
        return _render_success_html(short_id)

    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        if is_json:
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
        return _render_error_html(
            "Ошибка при отправке",
            hint="Попробуйте ещё раз через несколько секунд",
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
