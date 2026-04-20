"""FastAPI sub-app for /api/* JSON endpoints.

Mounted in main.py at the /api prefix. Exists alongside FastHTML during the
strangler fig migration. Auto-generates OpenAPI at /api/openapi.json and
Swagger UI at /api/docs. Unlocks future MCP tool generation.

Path convention: router prefixes MUST NOT include /api/ — the mount adds it.
e.g., `@router.get("/health")` is served at `/api/health`.
"""

from fastapi import FastAPI

from api.routers import admin, cron, deals, geo, invoices, plan_fact, public, quotes

api_app = FastAPI(
    title="OneStack API",
    version="1.0.0",
    docs_url="/docs",  # → /api/docs
    openapi_url="/openapi.json",  # → /api/openapi.json
    redoc_url=None,  # keep schema surface minimal
)

api_app.include_router(public.router)
api_app.include_router(admin.router, prefix="/admin")  # → /api/admin/*
api_app.include_router(plan_fact.router, prefix="/plan-fact")  # → /api/plan-fact/*
api_app.include_router(deals.router, prefix="/deals")  # → /api/deals
api_app.include_router(quotes.router, prefix="/quotes")  # → /api/quotes/*
api_app.include_router(invoices.router, prefix="/invoices")  # → /api/invoices/*
api_app.include_router(cron.router, prefix="/cron")  # → /api/cron/*
api_app.include_router(geo.router, prefix="/geo")  # → /api/geo/*
