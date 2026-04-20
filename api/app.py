"""FastAPI sub-app for /api/* JSON endpoints.

Mounted in main.py at the /api prefix. Exists alongside FastHTML during the
strangler fig migration. Auto-generates OpenAPI at /api/openapi.json and
Swagger UI at /api/docs. Unlocks future MCP tool generation.

Path convention: router prefixes MUST NOT include /api/ — the mount adds it.
e.g., `@router.get("/health")` is served at `/api/health`.
"""

from fastapi import FastAPI

from api.routers import admin, public

api_app = FastAPI(
    title="OneStack API",
    version="1.0.0",
    docs_url="/docs",  # → /api/docs
    openapi_url="/openapi.json",  # → /api/openapi.json
    redoc_url=None,  # keep schema surface minimal
)

api_app.include_router(public.router)
api_app.include_router(admin.router, prefix="/admin")  # full path: /api/admin/*
