"""Cron /api/cron/* endpoints — scheduled background tasks.

Called by external cron jobs with X-Cron-Secret header. Listed in
api.auth.PUBLIC_API_PATHS so JWT middleware passes through without auth.
"""

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.cron import (
    cron_check_overdue as _cron_check_overdue,
    cron_revalidate_rates as _cron_revalidate_rates,
    cron_sla_check as _cron_sla_check,
)
from services.alta_client import AltaClient, get_alta_client

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


@router.post("/revalidate-rates")
async def post_revalidate_rates(
    request: Request,
    alta_client: AltaClient = Depends(get_alta_client),
) -> JSONResponse:
    """Weekly customs rate revalidation — REQ-6 customs-phase-1.

    Called externally once a week with X-Cron-Secret. Picks the top-1000
    most-recently-used rates that are >7 days stale, re-fetches them from
    Alta, and upserts with ``source='alta-revalidate'``. Aborts and
    Telegram-alerts admins on insufficient funds (AltaApiError 140) or
    when packet_left drops below the floor.
    """
    return await _cron_revalidate_rates(request, alta_client)
