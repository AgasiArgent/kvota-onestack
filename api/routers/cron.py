"""Cron /api/cron/* endpoints — scheduled background tasks.

Called by external cron jobs with X-Cron-Secret header. Listed in
api.auth.PUBLIC_API_PATHS so JWT middleware passes through without auth.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.cron import cron_check_overdue as _cron_check_overdue

router = APIRouter(tags=["cron"])


@router.get("/check-overdue")
async def get_check_overdue(request: Request) -> JSONResponse:
    """Scheduled check for overdue quotes; triggered by cron with X-Cron-Secret."""
    return await _cron_check_overdue(request)
