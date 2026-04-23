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

import hmac
import logging
import os

from fastapi import APIRouter
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.envelope import error_response, success_response
from api.models.journey import (
    JourneyNodeAggregated,
    JourneyNodeDetail,
    JourneyNodeHistoryEntry,
    JourneyNodeState,
    JourneyPing,
    JourneyStatePatchRequest,
    JourneySuccessEnvelope,
    PlaywrightWebhookRequest,
)

logger = logging.getLogger(__name__)

#: Env var holding the shared secret that Playwright must send in the
#: ``X-Journey-Webhook-Token`` header. Missing env var → the handler returns
#: 503 (we never fall back to an empty / default token — that would make the
#: webhook unauthenticated).
JOURNEY_WEBHOOK_TOKEN_ENV = "JOURNEY_WEBHOOK_TOKEN"

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


@router.get(
    "/nodes",
    response_model=JourneySuccessEnvelope[list[JourneyNodeAggregated]],
)
async def get_journey_nodes(request: Request) -> JSONResponse:
    """Return the canvas-level merged view for every journey node.

    Path: GET /api/journey/nodes
    Params: none (Task 10 — filter parameters deferred to future tasks).
    Returns:
        success: bool — ``true`` on success.
        data: list[JourneyNodeAggregated] — one entry per manifest node
            plus one per ``journey_ghost_nodes`` row, sorted by ``node_id``.
            Each entry carries the merged shape: route / cluster / title /
            roles from the manifest, impl/qa status + version from
            ``journey_node_state``, and scalar counts for stories, pins,
            feedback (filtered to the caller's visibility — Req 11.2).
    Side Effects: none.
    Roles: any authenticated user. Non-admin callers see ``feedback_count``
        filtered to rows they themselves submitted (mirrors the admin-only
        ``/admin/feedback`` gate in the frontend).

    Implementation:
        ``services.journey_service.get_nodes_aggregated`` owns the merge.
        The handler's job is auth-context extraction + envelope shaping,
        so Tasks 11 / 12 / 13 can reuse the same service module.
    """
    # Lazy import so tests can patch ``services.journey_service.get_supabase``
    # without provoking a circular load at module-import time.
    from services import journey_service

    api_user = getattr(request.state, "api_user", None)
    user_id, role_slugs = journey_service.resolve_caller_context(api_user)

    nodes = journey_service.get_nodes_aggregated(
        user_id=user_id,
        role_slugs=role_slugs,
    )

    return success_response([n.model_dump() for n in nodes])


@router.get(
    "/node/{node_id:path}/history",
    response_model=JourneySuccessEnvelope[list[JourneyNodeHistoryEntry]],
)
async def get_journey_node_history(node_id: str, request: Request) -> JSONResponse:
    """Return the audit log for a node, reverse-chronological, capped at 50.

    Path: GET /api/journey/node/{node_id}/history
    Params:
        node_id: stable node identifier — ``app:/route`` or ``ghost:slug``.
            The ``:path`` converter is required because ``app:`` ids contain
            ``/`` segments. This route is declared BEFORE
            ``GET /node/{node_id:path}`` so the longer literal suffix
            ``/history`` wins the match.
    Returns:
        200 ``{"success": true, "data": JourneyNodeHistoryEntry[]}`` — up to
            50 rows from ``kvota.journey_node_state_history`` ordered by
            ``changed_at`` DESC. Empty list if no history yet (valid result —
            no 404 for unknown nodes on history; the audit log is append-only
            and simply absent until first update).
    Side Effects: none.
    Roles: any authenticated user (same visibility as the state itself — the
        history is the same projection).
    """
    from services import journey_service

    entries = journey_service.get_node_history(node_id=node_id, limit=50)
    return success_response([e.model_dump() for e in entries])


@router.patch(
    "/node/{node_id:path}/state",
    response_model=JourneySuccessEnvelope[JourneyNodeState],
)
async def patch_journey_node_state(
    node_id: str, request: Request
) -> JSONResponse:
    """Apply a field-aware, optimistic-concurrency PATCH to a node's state row.

    Path: PATCH /api/journey/node/{node_id}/state

    Declared AFTER ``GET /node/{node_id:path}/history`` on purpose — FastAPI's
    matcher prefers the longest literal suffix, so ``/history`` wins a GET,
    and this route handles PATCH on the same path prefix (including
    ``.../state``) without collisions. Moving this declaration before
    ``/history`` would not break GET (methods differ) but keeps the ordering
    intent explicit and consistent with the Task-13 handoff constraint.

    Params (body — ``JourneyStatePatchRequest``):
        version: int (required, ge=0) — last version the client saw.
        impl_status: ImplStatus | None — new value or null to leave untouched.
        qa_status: QaStatus | None — ditto.
        notes: str | None — ditto.
    Returns:
        200 ``{"success": true, "data": JourneyNodeState}`` on success.
        400 ``INVALID_PATCH`` on Pydantic validation failure (unknown field,
            negative version, wrong status literal).
        400 ``EMPTY_PATCH`` when every field is null (no write requested).
        401 ``UNAUTHORIZED`` when the caller has no JWT.
        403 ``FORBIDDEN_FIELD`` when the caller lacks write permission for
            any field in the patch (full rollback — no partial write).
        409 ``STALE_VERSION`` when stored version ≠ submitted version. The
            response body carries the current state under ``data`` so the UI
            can refresh without a second round-trip. This is the one place in
            this file where an error response also ships ``data``; see the
            explicit ``extra={"data": ...}`` branch below.
    Side Effects:
        UPDATE or INSERT on ``kvota.journey_node_state``. The AFTER UPDATE
        trigger from migration 500 copies the pre-image to
        ``journey_node_state_history``.
    Roles: enforced per-field via ``ROLE_FIELD_PERMISSIONS`` (Req 6.4 / 6.5 /
        6.8). ``top_manager`` is denied every field.
    """
    from pydantic import ValidationError  # local import — handler-only

    from services import journey_service

    # 1. Auth — Journey PATCH requires a caller identity for updated_by.
    api_user = getattr(request.state, "api_user", None)
    user_id, role_slugs = journey_service.resolve_caller_context(api_user)
    if not user_id:
        return error_response(
            code="UNAUTHORIZED",
            message="Journey state edits require an authenticated caller.",
            status_code=401,
        )

    # 2. Parse + validate body.
    try:
        raw_body = await request.json()
    except ValueError:
        return error_response(
            code="INVALID_PATCH",
            message="Request body is not valid JSON.",
            status_code=400,
        )
    try:
        patch = JourneyStatePatchRequest.model_validate(raw_body)
    except ValidationError as exc:
        return error_response(
            code="INVALID_PATCH",
            message=f"Invalid patch payload: {exc.errors()}",
            status_code=400,
        )

    # 3. Delegate to service. All domain errors raise JourneyStatePatchError.
    try:
        new_state = journey_service.patch_node_state(
            node_id=node_id,
            patch=patch,
            caller_user_id=user_id,
            caller_role_slugs=role_slugs,
        )
    except journey_service.JourneyStatePatchError as exc:
        # STALE_VERSION is the one error that also ships ``data`` — the
        # frontend uses it to reconcile without a second GET (Req 6.2). We
        # override the envelope helper's default (error-only) by threading
        # ``extra={"data": ...}``; status stays 409 and ``success=false`` so
        # the shape remains ``{success:false, error:{...}, data:{...}}``.
        extra = {"data": exc.data} if exc.data is not None else None
        return error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            extra=extra,
        )

    return success_response(new_state.model_dump())


@router.post(
    "/playwright-webhook",
    response_model=None,
)
async def journey_playwright_webhook(request: Request) -> JSONResponse:
    """Accept a nightly batch of pin-bbox refreshes from the Playwright crawler.

    Path: POST /api/journey/playwright-webhook
    Auth: shared secret via ``X-Journey-Webhook-Token`` header, compared to
        the ``JOURNEY_WEBHOOK_TOKEN`` env var with ``hmac.compare_digest``
        (constant-time). Missing env var → 503 SERVICE_UNAVAILABLE (we refuse
        to run an unauthenticated webhook). Missing / mismatched header →
        401 UNAUTHORIZED.
    Params (body):
        updates: PlaywrightWebhookPinUpdate[] — each entry carries a ``pin_id``
            plus an optional ``bbox`` (rel_x/y/width/height, all 0.0–1.0).
            Null/absent bbox → pin is marked ``selector_broken=true`` and
            bbox fields are left untouched.
    Returns:
        200 ``{"success": true, "data": {"updated_count": int}}`` on success.
        400 VALIDATION_ERROR when the body fails Pydantic validation.
        401 UNAUTHORIZED when the header is missing or doesn't match.
        503 SERVICE_UNAVAILABLE when ``JOURNEY_WEBHOOK_TOKEN`` is unset.
    Side Effects:
        UPDATE on ``kvota.journey_pins`` for each entry in ``updates``. The
        batch is best-effort (supabase-py has no transaction wrapper) —
        idempotent by design, so re-running on partial failure is safe.
    Roles: service-role only (no per-user auth; the shared secret gates access).
    """
    from services import journey_service

    expected_token = os.environ.get(JOURNEY_WEBHOOK_TOKEN_ENV)
    if not expected_token:
        logger.error(
            "playwright webhook refused: %s env var is not set",
            JOURNEY_WEBHOOK_TOKEN_ENV,
        )
        return error_response(
            code="SERVICE_UNAVAILABLE",
            message=(
                f"Journey webhook is not configured: {JOURNEY_WEBHOOK_TOKEN_ENV} "
                "env var is missing on the server."
            ),
            status_code=503,
        )

    provided_token = request.headers.get("X-Journey-Webhook-Token", "")
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        return error_response(
            code="UNAUTHORIZED",
            message="Missing or invalid X-Journey-Webhook-Token header.",
            status_code=401,
        )

    try:
        raw_body = await request.json()
    except ValueError:
        return error_response(
            code="VALIDATION_ERROR",
            message="Request body is not valid JSON.",
            status_code=400,
        )

    try:
        payload = PlaywrightWebhookRequest.model_validate(raw_body)
    except ValidationError as exc:
        return error_response(
            code="VALIDATION_ERROR",
            message=f"Invalid webhook payload: {exc.errors()}",
            status_code=400,
        )

    updated = journey_service.apply_playwright_webhook_batch(payload.updates)
    return success_response({"updated_count": updated})


@router.get(
    "/node/{node_id:path}",
    response_model=JourneySuccessEnvelope[JourneyNodeDetail],
)
async def get_journey_node_detail(node_id: str, request: Request) -> JSONResponse:
    """Return the full drawer payload for a single journey node.

    Path: GET /api/journey/node/{node_id}
    Params:
        node_id: stable node identifier (``app:/route`` or ``ghost:slug``).
            Declared with a ``:path`` converter because ``app:`` ids contain
            ``/`` segments (e.g. ``app:/admin/users``) that would otherwise
            be split across path params.
    Returns:
        200 with ``{"success": true, "data": JourneyNodeDetail}`` — manifest
            fields + state + pins + latest verifications per pin + top-3
            feedback (access-filtered per Req 11.2).
        404 with ``{"success": false, "error": {"code": "NOT_FOUND", ...}}``
            when the node_id is absent from both the manifest and
            ``kvota.journey_ghost_nodes``.
    Side Effects: none.
    Roles: any authenticated user. Non-admin callers see only their own
        feedback rows in the ``feedback`` list (admin sees all).
    """
    # Lazy import — keeps tests' ``patch("services.journey_service.get_supabase")``
    # path stable and avoids circular-import risk at module load.
    from services import journey_service

    api_user = getattr(request.state, "api_user", None)
    user_id, role_slugs = journey_service.resolve_caller_context(api_user)

    detail = journey_service.get_node_detail(
        node_id=node_id,
        user_id=user_id,
        role_slugs=role_slugs,
    )
    if detail is None:
        return error_response(
            code="NOT_FOUND",
            message=f"Node {node_id!r} is not in the manifest or ghost-nodes table.",
            status_code=404,
        )

    return success_response(detail.model_dump())


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
