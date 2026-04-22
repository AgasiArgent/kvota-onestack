"""FastAPI application for OneStack.

Architecture (post-Phase 6C-3, 2026-04-21):
- Docker runs `uvicorn api.app:api_app`.
- ``api_app`` is the OUTER FastAPI app: owns middleware (Sentry, Session,
  ApiAuth) and mounts the router sub-app at ``/api``.
- ``api_sub_app`` is the INNER FastAPI app: owns all domain routers (quotes,
  admin, deals, ...). Its router paths DO NOT include ``/api/`` — the mount
  provides the prefix, so ``@router.get("/health")`` is served at
  ``/api/health``.

Splitting outer / inner lets us register middleware once on the outer app
without repeating it on every router, and keeps OpenAPI under
``/api/docs`` + ``/api/openapi.json`` (served by the sub-app).

Contracts preserved from the pre-6C-3 FastHTML era:
- ``/api/*`` URL prefix (Next.js, Caddy, docker-compose healthcheck, JWT guard)
- Session cookie auth (SessionMiddleware) — 9+ endpoints still read
  ``request.session`` during strangler fig dual-auth
- Sentry tracing starts at app startup (init MUST run before FastAPI() call)
"""

import os

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from api.auth import ApiAuthMiddleware
from api.routers import (
    admin,
    chat,
    cost_analysis,
    cron,
    customs,
    deals,
    documents,
    feedback,
    geo,
    integrations,
    invoices,
    logistics,
    notes,
    plan_fact,
    public,
    quotes,
)

load_dotenv()

# Sentry init — must run BEFORE any FastAPI() call so the SDK patches
# Starlette middleware during app construction.
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=True,
        traces_sample_rate=1.0,
        environment=os.getenv(
            "SENTRY_ENVIRONMENT",
            "production" if not os.getenv("DEBUG") else "development",
        ),
    )

# ---------------------------------------------------------------------------
# Inner sub-app: owns all routers. Mounted at /api on the outer app below.
# ---------------------------------------------------------------------------
api_sub_app = FastAPI(
    title="OneStack API",
    version="1.0.0",
    docs_url="/docs",  # → /api/docs
    openapi_url="/openapi.json",  # → /api/openapi.json
    redoc_url=None,
)

api_sub_app.include_router(public.router)
api_sub_app.include_router(admin.router, prefix="/admin")  # → /api/admin/*
api_sub_app.include_router(plan_fact.router, prefix="/plan-fact")  # → /api/plan-fact/*
api_sub_app.include_router(deals.router, prefix="/deals")  # → /api/deals
api_sub_app.include_router(quotes.router, prefix="/quotes")  # → /api/quotes/*
api_sub_app.include_router(
    cost_analysis.router, prefix="/quotes"
)  # → /api/quotes/{id}/cost-analysis
api_sub_app.include_router(invoices.router, prefix="/invoices")  # → /api/invoices/*
api_sub_app.include_router(cron.router, prefix="/cron")  # → /api/cron/*
api_sub_app.include_router(geo.router, prefix="/geo")  # → /api/geo/*
api_sub_app.include_router(chat.router, prefix="/chat")  # → /api/chat/*
api_sub_app.include_router(feedback.router, prefix="/feedback")  # → /api/feedback
api_sub_app.include_router(documents.router, prefix="/documents")  # → /api/documents/*
api_sub_app.include_router(customs.router, prefix="/customs")  # → /api/customs/*
api_sub_app.include_router(logistics.router, prefix="/logistics")  # → /api/logistics/*
api_sub_app.include_router(notes.router, prefix="/notes")  # → /api/notes
# integrations.router spans /telegram/* + /internal/* — no single prefix fits.
api_sub_app.include_router(integrations.router)

# ---------------------------------------------------------------------------
# Outer app: what Docker serves. Adds middleware + mounts the sub-app at /api.
# ---------------------------------------------------------------------------
api_app = FastAPI(
    title="OneStack",
    docs_url=None,  # docs live on the sub-app at /api/docs
    openapi_url=None,
    redoc_url=None,
)

# SessionMiddleware MUST be registered before routes run — 9+ /api/* handlers
# read ``request.session`` during the FastHTML→Next.js strangler fig migration.
api_app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("APP_SECRET", "dev-secret-change-in-production"),
)
api_app.add_middleware(ApiAuthMiddleware)

api_app.mount("/api", api_sub_app)
