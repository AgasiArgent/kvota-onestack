"""JWT validation middleware for /api/* endpoints.

During the strangler fig migration (FastHTML → Next.js), API routes are called
by both frontends: HTMX uses session cookies, Next.js uses JWT Bearer tokens.

Default behavior is dual-auth: if a valid JWT is present, attach the user to
request.state; if not, pass through and let the handler check session auth.
Only paths in JWT_REQUIRED_PATHS strictly reject requests without a valid JWT.
"""

import asyncio
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from supabase_auth import SyncGoTrueClient

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Paths that skip auth entirely (health checks, webhooks)
PUBLIC_API_PATHS = {"/api/health", "/api/telegram/webhook", "/api/changelog"}

# Paths that STRICTLY require JWT (no session fallback).
# Add paths here only after the corresponding FastHTML route is fully removed.
JWT_REQUIRED_PATHS: set[str] = set()

# Module-level singleton — reused across requests
_gotrue_client: SyncGoTrueClient | None = None


def _get_gotrue_client() -> SyncGoTrueClient:
    global _gotrue_client
    if _gotrue_client is None:
        _gotrue_client = SyncGoTrueClient(
            url=f"{SUPABASE_URL}/auth/v1",
            headers={"apikey": SUPABASE_ANON_KEY},
        )
    return _gotrue_client


def get_user_from_token(auth_header: str):
    """Extract and validate Supabase JWT from Authorization header value."""
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    try:
        client = _get_gotrue_client()
        user = client.get_user(token)
        return user.user if user else None
    except Exception:
        return None


class ApiAuthMiddleware(BaseHTTPMiddleware):
    """Dual-auth middleware for /api/* routes during FastHTML → Next.js migration.

    - Public paths: pass through without auth
    - JWT-required paths: reject if no valid JWT
    - All other /api/* paths: attach JWT user if present, pass through otherwise
      (handler checks session auth for FastHTML HTMX requests)
    """

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Only apply to /api/* routes
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip public endpoints
        if path in PUBLIC_API_PATHS:
            return await call_next(request)

        # Validate JWT if Authorization header is present
        auth_header = request.headers.get("authorization", "")
        user = None
        if auth_header:
            user = await asyncio.get_event_loop().run_in_executor(
                None, get_user_from_token, auth_header
            )

        # JWT-required paths: reject if no valid JWT
        if path in JWT_REQUIRED_PATHS and not user:
            return JSONResponse(
                {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid or missing token"}},
                status_code=401,
            )

        # Attach JWT user (or None) — handlers use this or fall back to session
        request.state.api_user = user
        return await call_next(request)
