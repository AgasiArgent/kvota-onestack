"""/api/journey/* router — Customer Journey Map scaffold (Task 9).

Mounted on the FastAPI sub-app in ``api/app.py`` with ``prefix="/journey"``;
combined with the ``/api`` mount on the outer app, routes here are served at
``/api/journey/*``.

This file is the Wave 4 entry point. Tasks 10 (aggregate read), 11 (node
detail), 12 (state PATCH), and 13 (Playwright webhook) each extend this
router with their own handlers via RED→GREEN cycles. The scaffold ships two
endpoints only:

- ``GET /ping`` — liveness probe. Proves the router is mounted. Returns the
  standard success envelope so Task 9 tests can lock in the shape.
- ``GET /_error-probe`` — deliberately-failing endpoint so the error envelope
  shape is exercised in tests. The leading underscore marks it as a
  debug-only / scaffold endpoint; it may be removed once Wave 4 ships real
  error paths (NOT_FOUND on ``GET /node/{id}`` etc.).

Envelope (Req 16.4): every handler returns
``{"success": true, "data": ...}`` or
``{"success": false, "error": {"code": "...", "message": "..."}}`` via the
helpers in ``api/envelope.py``.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import JSONResponse

from api.envelope import error_response, success_response
from api.models.journey import JourneyPing

router = APIRouter(tags=["journey"])


@router.get("/ping")
async def journey_ping() -> JSONResponse:
    """Liveness probe for the /api/journey/* router.

    Path: GET /api/journey/ping
    Params: none
    Returns:
        success: bool — always ``true``.
        data: {status: "ok"} — payload matching ``JourneyPing`` model.
    Side Effects: none.
    Roles: any authenticated user (``api.auth.ApiAuthMiddleware`` attaches
           ``request.state.api_user`` when a JWT is present; this endpoint
           itself is open — Wave 4 handlers will enforce ACLs per design §6).
    """
    return success_response(JourneyPing().model_dump())


@router.get("/_error-probe", include_in_schema=False)
async def journey_error_probe() -> JSONResponse:
    """Scaffold endpoint that always returns the standard error envelope.

    Path: GET /api/journey/_error-probe
    Params: none
    Returns:
        HTTP 500 with ``{"success": false, "error": {code, message}}``.
    Side Effects: none.
    Roles: any authenticated user — not registered in OpenAPI.

    Exists so ``tests/test_api_journey.py::test_envelope_error_shape`` can
    assert the error envelope shape without reaching into real business
    logic. Remove once Wave 4 endpoints ship real 4xx/5xx paths.
    """
    return error_response(
        code="NOT_IMPLEMENTED",
        message=(
            "Scaffold error probe — Wave 4 endpoints will replace this with "
            "real error paths (NOT_FOUND, STALE_VERSION, FORBIDDEN_FIELD)."
        ),
        status_code=500,
    )
