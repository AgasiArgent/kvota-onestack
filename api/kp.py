"""KP Builder API — render a heavy-machinery commercial proposal to PDF.

Handler module (no router). Registered via the thin wrapper in
``api/routers/kp.py`` and mounted on the FastAPI sub-app at ``/kp`` (full
path: ``/api/kp/render-pdf``).

Iteration 1 contract (REQ-14, REQ-18, REQ-19, REQ-20):
- JSON body, all fields optional, defaults to empty / empty list
- ``application/pdf`` response on success with date-stamped filename
- Auth: JWT only (no session fallback — this is a Next.js-only feature)
- No DB writes, no Supabase reads, no side effects beyond the structured log line
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from services.kp_export import (
    KpItem,
    KpPackagingItem,
    KpProposal,
    KpServices,
    render_proposal_pdf_async,
)

logger = logging.getLogger(__name__)


def _unauthorized(message: str = "Authentication required") -> JSONResponse:
    """Canonical 401 envelope. Inline to avoid pulling api.lib.errors when
    the only signal we need is the canonical body shape."""
    return JSONResponse(
        {
            "success": False,
            "error": {"code": "UNAUTHORIZED", "message": message},
        },
        status_code=401,
    )


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        {
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "message": message},
        },
        status_code=400,
    )


def _render_error(request_id: str) -> JSONResponse:
    return JSONResponse(
        {
            "success": False,
            "error": {
                "code": "RENDER_ERROR",
                "message": "PDF rendering failed",
                "request_id": request_id,
            },
        },
        status_code=500,
    )


def _require_user(request: Request):
    """Return the authenticated Supabase user or ``None``.

    The middleware (``ApiAuthMiddleware``) sets ``request.state.api_user`` to
    the JWT-verified user, or to ``None`` if the bearer token was missing /
    invalid. Iteration 1 of the KP Builder is JWT-only — no session
    fallback — so a missing user is a hard 401.
    """
    return getattr(request.state, "api_user", None)


def _build_proposal(body: Any) -> KpProposal:
    """Coerce a (possibly partial) JSON body into a ``KpProposal``.

    All fields are optional. The body shape is mirrored after the design's
    ``DEFAULT_DATA`` (camelCase ``priceIncludes`` mapped to snake_case
    ``price_includes``; everything else passes straight through).

    The function NEVER raises on missing / null / wrong-typed values — it
    coerces to safe defaults so a junior client doesn't crash the renderer
    by forgetting a field.
    """
    if not isinstance(body, dict):
        return KpProposal()

    def _s(key: str) -> str:
        v = body.get(key)
        return str(v) if v is not None else ""

    items_in = body.get("items") or []
    items = tuple(
        KpItem(
            name=str((i or {}).get("name", "") or ""),
            model=str((i or {}).get("model", "") or ""),
            qty=str((i or {}).get("qty", "") or ""),
            price=str((i or {}).get("price", "") or ""),
        )
        for i in items_in
        if isinstance(i, dict)
    )

    pkg_in = body.get("packaging") or []
    packaging = tuple(
        KpPackagingItem(
            text=str((p or {}).get("text", "") or ""),
            checked=bool((p or {}).get("checked", False)),
        )
        for p in pkg_in
        if isinstance(p, dict)
    )

    svc_in = body.get("services")
    if not isinstance(svc_in, dict):
        svc_in = {}
    services = KpServices(
        delivery=bool(svc_in.get("delivery", False)),
        training=bool(svc_in.get("training", False)),
        supervision=bool(svc_in.get("supervision", False)),
        warranty=bool(svc_in.get("warranty", False)),
        commissioning=bool(svc_in.get("commissioning", False)),
        service=bool(svc_in.get("service", False)),
    )

    # Accept either snake_case or camelCase for the one camelCase field.
    price_includes = _s("price_includes") or _s("priceIncludes")

    return KpProposal(
        subtitle=_s("subtitle"),
        supplier=_s("supplier"),
        manager=_s("manager"),
        phone=_s("phone"),
        email=_s("email"),
        address=_s("address"),
        basis=_s("basis"),
        payment=_s("payment"),
        date=_s("date"),
        lead=_s("lead"),
        amount=_s("amount"),
        price_includes=price_includes,
        items=items,
        notes=_s("notes"),
        specs=tuple(str(s) for s in (body.get("specs") or []) if s is not None),
        packaging=packaging,
        conditions=tuple(
            str(c) for c in (body.get("conditions") or []) if c is not None
        ),
        services=services,
        notes2=_s("notes2"),
        contact_phone=_s("contact_phone"),
        contact_email=_s("contact_email"),
        contact_site=_s("contact_site"),
        contact_address=_s("contact_address"),
        foot_phone=_s("foot_phone"),
        foot_site=_s("foot_site"),
        foot_email=_s("foot_email"),
        # Currency arrives as a 3-letter ISO code; the renderer falls back
        # to RUB on any unknown value, so we forward whatever the client
        # sends instead of validating an enum at this layer.
        currency=_s("currency") or "RUB",
    )


async def render_pdf(request: Request) -> Response:
    """Render a heavy-machinery commercial proposal as PDF.

    Path: POST /api/kp/render-pdf

    Params:
        body: KpProposalRequest (JSON, all fields optional) — see
            services.kp_export.KpProposal for the field shape. Missing or
            null fields default to empty strings / empty arrays so a
            minimal client can render an empty template.

    Returns:
        Binary PDF body with ``Content-Type: application/pdf`` and
        ``Content-Disposition: attachment; filename="kp-{YYYY-MM-DD}.pdf"``
        on success.

    Side Effects:
        None. The renderer never touches the database (REQ-20). The only
        observable side effect is a structured log line with request_id,
        user_id, org_id, payload size, render duration, and outcome.

    Roles: any authenticated user (no role gating in iteration 1, REQ-18.4).
    """
    user = _require_user(request)
    if user is None:
        return _unauthorized()

    request_id = str(uuid.uuid4())
    user_id = str(getattr(user, "id", "")) or ""
    user_metadata = getattr(user, "user_metadata", None) or {}
    org_id = user_metadata.get("org_id") if isinstance(user_metadata, dict) else None

    try:
        body = await request.json()
    except (ValueError, TypeError):
        logger.info(
            "kp.render_pdf rejected: malformed JSON body",
            extra={"request_id": request_id, "user_id": user_id, "org_id": org_id},
        )
        return _validation_error("Malformed JSON body")

    # Reject empty bodies — they otherwise produce a blank Master Bearing
    # template, which is almost never what the caller meant. Empty dict or
    # null both surface here.
    if not body:
        logger.info(
            "kp.render_pdf rejected: empty request body",
            extra={"request_id": request_id, "user_id": user_id, "org_id": org_id},
        )
        return _validation_error("Empty request body")

    proposal = _build_proposal(body)
    started = time.perf_counter()
    try:
        pdf_bytes = await render_proposal_pdf_async(proposal)
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "kp.render_pdf failed",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "org_id": org_id,
                "duration_ms": duration_ms,
            },
        )
        return _render_error(request_id)

    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "kp.render_pdf ok",
        extra={
            "request_id": request_id,
            "user_id": user_id,
            "org_id": org_id,
            "bytes": len(pdf_bytes),
            "duration_ms": duration_ms,
        },
    )

    filename = f"kp-{date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
