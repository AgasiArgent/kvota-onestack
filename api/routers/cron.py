"""Cron /api/cron/* endpoints — scheduled background tasks.

Called by external cron jobs with X-Cron-Secret header. Listed in
api.auth.PUBLIC_API_PATHS so JWT middleware passes through without auth.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.cron import (
    cron_check_overdue as _cron_check_overdue,
    cron_sla_check as _cron_sla_check,
)

router = APIRouter(tags=["cron"])


@router.get("/check-overdue")
async def get_check_overdue(request: Request) -> JSONResponse:
    """Scheduled check for overdue quotes; triggered by cron with X-Cron-Secret."""
    return await _cron_check_overdue(request)


@router.post("/sla-check")
async def post_sla_check(request: Request) -> JSONResponse:
    """Scheduled invoice SLA check — sends reminder/overdue Telegram pings.

    Called externally every ~10 min with X-Cron-Secret. Dedupe is enforced
    by UNIQUE(invoice_id, kind) in kvota.invoice_sla_notifications_sent
    (migration 295). Safe to re-run.
    """
    return await _cron_sla_check(request)
