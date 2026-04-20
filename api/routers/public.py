"""Public /api/* endpoints that do not require authentication.

Currently hosts:
- GET /api/health    — liveness probe for Docker/Caddy/monitoring.
- GET /api/changelog — release notes (public, non-sensitive).

Both are listed in `api.auth.PUBLIC_API_PATHS` so the JWT middleware passes them
through without auth. Path convention: router paths do NOT include /api/ — the
mount in main.py adds it.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

router = APIRouter(tags=["public"])


@router.get("/health", include_in_schema=False)
async def health(request: Request) -> JSONResponse:
    """Liveness probe for Next.js frontend and infrastructure checks."""
    return JSONResponse({"success": True, "status": "ok"})


@router.get("/changelog")
async def get_changelog(request: Request) -> JSONResponse:
    """Return changelog entries as JSON.

    Path: GET /api/changelog
    Returns:
        success: bool
        data: list of {slug, title, date, category, version, body_html}
    Roles: public (no auth required) — release notes are not sensitive.
    """
    from services.changelog_service import get_all_entries, render_entry_html

    entries = get_all_entries()
    result = []
    for entry in entries:
        result.append(
            {
                "slug": entry["slug"],
                "title": entry["title"],
                "date": entry["date"].isoformat(),
                "category": entry.get("category", "update"),
                "version": entry.get("version"),
                "body_html": render_entry_html(entry),
            }
        )

    return JSONResponse({"success": True, "data": result})
